"""Joint-space plans for an existing GLB. No catalogue of poses or actions.

The language model proposes declarative local joint deltas. The compiler checks
actual targets, times and finite values, emits standard glTF animation channels,
and measures deformation on skin-weighted vertices. These checks do not certify
contacts, balance, collisions or semantic correctness of the proposed movement.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
import urllib.request
import numpy as np
import glb_io


def file_hash(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def quat_mul(a,b):
    ax,ay,az,aw=a;bx,by,bz,bw=b
    return np.array([aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz])


def delta_quat(euler):
    q=np.array([0.,0.,0.,1.])
    for axis,angle in enumerate(euler):
        r=np.array([0.,0.,0.,math.cos(angle/2)]);r[axis]=math.sin(angle/2);q=quat_mul(q,r)
    return q/np.linalg.norm(q)


def transform(node):
    if 'matrix' in node:return np.array(node['matrix'],float).reshape(4,4).T
    x,y,z,w=node.get('rotation',[0,0,0,1]);norm=math.sqrt(x*x+y*y+z*z+w*w)
    if norm==0:raise ValueError('Zero quaternion')
    x,y,z,w=np.array([x,y,z,w])/norm
    m=np.eye(4);m[:3,:3]=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
    m[:3,:3] = m[:3,:3] @ np.diag(node.get('scale',[1,1,1]));m[:3,3]=node.get('translation',[0,0,0]);return m


def world_matrices(nodes):
    parents={child:i for i,n in enumerate(nodes) for child in n.get('children',[])};cache={}
    def world(i,visiting=None):
        visiting=set() if visiting is None else visiting
        if i in visiting:raise ValueError('Cyclic skeleton hierarchy')
        if i not in cache:cache[i]=(world(parents[i],visiting|{i}) if i in parents else np.eye(4))@transform(nodes[i])
        return cache[i]
    return [world(i) for i in range(len(nodes))],parents


def canonical_trs(doc):
    """Convert equivalent affine node matrices before emitting glTF TRS channels."""
    doc=copy.deepcopy(doc)
    for node in doc.get('nodes',[]):
        if 'matrix' not in node:continue
        matrix=transform(node);basis=matrix[:3,:3];scale=np.linalg.norm(basis,axis=0)
        if np.any(scale<1e-12):raise ValueError('Collapsed transform cannot be animated')
        rotation=basis/scale
        if np.linalg.det(rotation)<0:
            axis=int(np.argmax(scale));scale[axis]*=-1;rotation[:,axis]*=-1
        if not np.allclose(rotation.T@rotation,np.eye(3),atol=1e-6):raise ValueError('Sheared transform requires geometry conversion before animation')
        trace=float(np.trace(rotation));q=np.zeros(4)
        if trace>0:
            k=math.sqrt(trace+1)*2;q[3]=k/4
            q[:3]=[(rotation[2,1]-rotation[1,2])/k,(rotation[0,2]-rotation[2,0])/k,(rotation[1,0]-rotation[0,1])/k]
        else:
            i=int(np.argmax(np.diag(rotation)));j=(i+1)%3;k=(i+2)%3
            factor=math.sqrt(max(0,1+rotation[i,i]-rotation[j,j]-rotation[k,k]))*2
            q[i]=factor/4;q[j]=(rotation[j,i]+rotation[i,j])/factor;q[k]=(rotation[k,i]+rotation[i,k])/factor;q[3]=(rotation[k,j]-rotation[j,k])/factor
        node.pop('matrix');node['translation']=matrix[:3,3].tolist();node['scale']=scale.tolist();node['rotation']=(q/np.linalg.norm(q)).tolist()
    return doc


def skeleton_context(doc,blob=None):
    skinned=bool(doc.get('skins'))
    joints={j for skin in doc.get('skins',[]) for j in skin.get('joints',[])} if skinned else {i for i,node in enumerate(doc.get('nodes',[])) if 'mesh' in node}
    if not joints:raise ValueError('No geometric nodes available for transform planning')
    influence={}
    if blob is not None and skinned:
        for mesh_node in doc['nodes']:
            if 'mesh' not in mesh_node or 'skin' not in mesh_node:continue
            joint_nodes=doc['skins'][mesh_node['skin']]['joints']
            for primitive in doc['meshes'][mesh_node['mesh']]['primitives']:
                attrs=primitive.get('attributes',{})
                if not all(k in attrs for k in ('JOINTS_0','WEIGHTS_0')):continue
                slots=glb_io.accessor(doc,blob,attrs['JOINTS_0']).astype(int)
                weights=glb_io.accessor(doc,blob,attrs['WEIGHTS_0'])
                for slot,count in zip(*np.unique(slots[weights>1e-6],return_counts=True)):
                    if slot<0 or slot>=len(joint_nodes):raise ValueError('Invalid weighted joint index')
                    node=joint_nodes[slot];influence[node]=influence.get(node,0)+int(count)
        joints=set(influence)
        if not joints:raise ValueError('No vertices are actually bound to this skeleton')
    world,parents=world_matrices(doc['nodes']);allowed=set(joints)
    for joint in list(joints):
        while joint in parents:joint=parents[joint];allowed.add(joint)
    return [{'node':i,'name':doc['nodes'][i].get('name',str(i)),'parent':parents.get(i),
             'world_position':world[i][:3,3].round(6).tolist(),'local_axes_world':world[i][:3,:3].round(6).tolist(),
             'translation':doc['nodes'][i].get('translation',[0,0,0]),'rotation_xyzw':doc['nodes'][i].get('rotation',[0,0,0,1]),
             'is_skin_joint':skinned and i in joints,'rigid_mesh':not skinned and 'mesh' in doc['nodes'][i],'weighted_vertices':influence.get(i) if blob is not None and skinned else None} for i in sorted(allowed)]


SYSTEM="""Compute a pose/motion plan for the supplied ACTUAL skeleton and COMPLETE final user request. Return a JSON object with:
- schema: string aurora.joint-plan.v1
- duration_seconds: positive finite number chosen for the requested movement
- loop: boolean
- requirements: list of actual user clauses covered, not placeholders
- tracks: list of objects with node (actual integer index), path (rotation, translation or scale), samples (ordered [time, vector] pairs). Each vector contains three finite numbers, not strings.
Derive the necessary nonzero joint changes from the requested result and measured skeleton. Do not list unchanged joints or emit a rest-pose placeholder. Do not choose a stock action. Combine held postures and simultaneous motions on the SAME timeline. Preserve unspecified details. Read bone positions and hierarchy to locate anatomy; numbered spine segments near the top are not the pelvis. Use enough joints to achieve the ENTIRE posture, including support and root height based on measured bone lengths. Merely rotating a torso cannot establish a posture of the full body.
Values are LOCAL DELTAS relative to the existing GLB. Rotation is XYZ Euler radians, translation uses asset units, scale is multiplicative. World Y is up. Each track starts at time zero and ends at duration_seconds. A held posture has constant NONZERO deltas; an animation must also have changing channels affecting the requested moving parts. Static_pose mode only holds the new pose. Consider where the joints will actually be after transformations, not only their names. There are no Blender constraints in glTF; only the actual parent hierarchy acts. No code, camera-only animation, marker or unmodified default as a substitute. Do not claim physical validation."""


def model_json(model,system,prompt):
    request=urllib.request.Request('http://127.0.0.1:11434/api/generate',data=json.dumps({'model':model,'system':system,'prompt':json.dumps(prompt,ensure_ascii=False,separators=(',',':')),'format':'json','think':False,'stream':False,'options':{'temperature':.1,'num_predict':8192,'num_ctx':32768}}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=600) as response:payload=json.load(response)
    if payload.get('error'):raise RuntimeError('Planning model service failed: '+json.dumps(payload['error'],ensure_ascii=False))
    text=payload.get('response','').strip()
    if not text:raise RuntimeError('Planning model returned no final answer; no pose was approved')
    if text.startswith('```'):text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    result=json.loads(text)
    if isinstance(result,dict) and result.get('error'):raise RuntimeError('Planning model reported an error: '+json.dumps(result['error'],ensure_ascii=False))
    return result


def infer_plan(prompt,context,model,mode):
    return model_json(model,SYSTEM,{'actual_skeleton':context,'coordinates':'glTF right-handed; world Y is up. XYZ rotation deltas use LOCAL axes, columns of local_axes_world.','mode':mode,'request':prompt})


def review_plan(prompt,doc,blob,plan,model,mode):
    context=skeleton_context(doc,blob)
    compact=[{k:c[k] for k in ('node','name','parent','world_position','is_skin_joint')} for c in context]
    axes={str(c['node']):c['local_axes_world'] for c in context if any(t['node']==c['node'] for t in plan['tracks'])}
    observed=[]
    duration=float(plan['duration_seconds'])
    for t in [0,duration*.25,duration*.5,duration*.75,duration]:
        worlds,_=world_matrices(posed_nodes(doc,plan,t))
        observed.append({'time':t,'joint_world_positions':{str(c['node']):worlds[c['node']][:3,3].round(5).tolist() for c in context}})
    system='''Review the COMPLETE requested pose/movement using the ACTUAL skeleton, local channels and numerically observed joint trajectories. Return JSON only: {"conforms":boolean,"missing_requirements":["..."],"defects":["..."]}. Check every requested part and simultaneous action; identify wrong joints, insufficient posture change, incorrect axes, unchanged limbs, wrong root height and unintended body movement. Nonzero skin movement does NOT prove the requested motion. Names may be numbered spine bones: infer anatomical location from world positions and hierarchy. Head rotation may leave its origin fixed; inspect rotation channels too. Blender constraints do not exist in glTF: only hierarchy and listed channels act. World Y is up. Listing a requirement does not prove its achievement. This is semantic review, not contact/collision certification. Fail when channels plainly omit a requested part or posture. Do not demand changes to unspecified parts.'''
    result=model_json(model,system,{'request':prompt,'mode':mode,'skeleton':compact,'tracked_local_axes':axes,'plan':plan,'observed':observed})
    if type(result.get('conforms')) is not bool or not isinstance(result.get('missing_requirements'),list) or not isinstance(result.get('defects'),list):raise ValueError('Invalid semantic motion review')
    if not result['conforms'] or result['missing_requirements'] or result['defects']:raise ValueError('Semantic joint review: '+json.dumps(result,ensure_ascii=False))
    return result


def validate_plan(plan,doc,blob=None):
    if plan.get('schema')!='aurora.joint-plan.v1':raise ValueError('Invalid joint plan schema')
    duration=float(plan.get('duration_seconds',0))
    if not math.isfinite(duration) or duration<=0:raise ValueError('Invalid motion duration')
    allowed={x['node'] for x in skeleton_context(doc,blob)};seen=set()
    tracks=plan.get('tracks',[])
    if not tracks:raise ValueError('No joint channels were proposed')
    for track in tracks:
        node=track.get('node');path=track.get('path')
        if type(node) is not int or node not in allowed or path not in {'rotation','translation','scale'}:raise ValueError('Joint/channel not present in the actual skeleton')
        if 'matrix' in doc['nodes'][node]:raise ValueError('Matrix-only joint needs an explicit TRS conversion before planning')
        if (node,path) in seen:raise ValueError('Conflicting joint channels')
        seen.add((node,path));previous=-1.;samples=track.get('samples',[])
        if len(samples)<2:raise ValueError('A channel needs ordered start and end samples')
        for sample in samples:
            t=float(sample[0]);v=np.array(sample[1],float)
            if not math.isfinite(t) or t<=previous or not 0<=t<=duration or v.shape!=(3,) or not np.isfinite(v).all():raise ValueError('Invalid sample for node %s %s, duration %s: %s' % (node,path,duration,sample))
            if path=='scale' and (v<=0).any():raise ValueError('Nonpositive scale collapses or mirrors the skin')
            previous=t
        if abs(samples[0][0])>1e-6 or abs(samples[-1][0]-duration)>1e-6:raise ValueError('Every track must cover the complete timeline')
    return duration


def posed_nodes(doc,plan,t):
    nodes=copy.deepcopy(doc['nodes'])
    for track in plan['tracks']:
        samples=track['samples'];times=np.array([s[0] for s in samples],float);values=np.array([s[1] for s in samples],float)
        v=np.array([np.interp(t,times,values[:,axis]) for axis in range(3)])
        target=nodes[track['node']];path=track['path']
        if path=='rotation':
            # glTF LINEAR rotation is shortest-path quaternion interpolation.
            right=min(int(np.searchsorted(times,t,side='right')),len(times)-1);left=max(0,right-1)
            qa=quat_mul(target.get(path,[0,0,0,1]),delta_quat(values[left]));qb=quat_mul(target.get(path,[0,0,0,1]),delta_quat(values[right]))
            alpha=float(np.clip((t-times[left])/max(times[right]-times[left],1e-12),0,1));dot=float(np.dot(qa,qb))
            if dot<0:qb=-qb;dot=-dot
            if dot>.9995:q=qa+alpha*(qb-qa);q/=np.linalg.norm(q)
            else:
                theta=math.acos(float(np.clip(dot,-1,1)));q=(math.sin((1-alpha)*theta)*qa+math.sin(alpha*theta)*qb)/math.sin(theta)
            target[path]=q.tolist()
        elif path=='translation':target[path]=(np.array(target.get(path,[0,0,0]))+v).tolist()
        else:target[path]=(np.array(target.get(path,[1,1,1]))*v).tolist()
    return nodes


def skin_samples(doc,blob,nodes):
    worlds,_=world_matrices(nodes);points=[]
    for node_index,mesh_node in enumerate(doc['nodes']):
        if 'mesh' not in mesh_node:continue
        if 'skin' not in mesh_node:
            if doc.get('skins'):continue
            for primitive in doc['meshes'][mesh_node['mesh']]['primitives']:
                vertices=glb_io.accessor(doc,blob,primitive['attributes']['POSITION'])
                indices=np.linspace(0,len(vertices)-1,min(512,len(vertices)),dtype=int)
                points.append((worlds[node_index]@np.c_[vertices[indices],np.ones(len(indices))].T).T[:,:3])
            continue
        skin=doc['skins'][mesh_node['skin']];joints=skin['joints']
        inverse=glb_io.accessor(doc,blob,skin['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1) if 'inverseBindMatrices' in skin else np.tile(np.eye(4),(len(joints),1,1))
        matrices=np.array([worlds[j]@inverse[i] for i,j in enumerate(joints)])
        for primitive in doc['meshes'][mesh_node['mesh']]['primitives']:
            attributes=primitive.get('attributes',{})
            if not all(k in attributes for k in ('POSITION','JOINTS_0','WEIGHTS_0')):continue
            vertices=glb_io.accessor(doc,blob,attributes['POSITION']);indices=np.linspace(0,len(vertices)-1,min(512,len(vertices)),dtype=int)
            v=np.c_[vertices[indices],np.ones(len(indices))];joint_indices=glb_io.accessor(doc,blob,attributes['JOINTS_0'])[indices].astype(int)
            weights=glb_io.accessor(doc,blob,attributes['WEIGHTS_0'])[indices].astype(float);weights/=np.maximum(weights.sum(axis=1,keepdims=True),1e-12)
            if joint_indices.max()>=len(joints):raise ValueError('Invalid skin weight joint index')
            transformed=np.einsum('nvij,nj->nvi',matrices[joint_indices],v)
            points.append((transformed*weights[:,:,None]).sum(axis=1)[:,:3])
    if not points:raise ValueError('No bound or rigid geometry to verify')
    return np.concatenate(points)


def compile_plan(doc,blob,plan,mode='animation'):
    doc=canonical_trs(doc)
    duration=validate_plan(plan,doc,blob)
    rest=skin_samples(doc,blob,doc['nodes']);times=sorted({float(s[0]) for track in plan['tracks'] for s in track['samples']}|{duration*.5})
    checked_times=list(times)
    first=skin_samples(doc,blob,posed_nodes(doc,plan,0));maximum=0.
    for t in times:
        p=skin_samples(doc,blob,posed_nodes(doc,plan,t))
        if not np.isfinite(p).all():raise ValueError('Nonfinite skinned positions')
        maximum=max(maximum,float(np.linalg.norm(p-first,axis=1).max()))
    extent=max(float(np.ptp(rest,axis=0).max()),1e-9)
    pose_delta=float(np.linalg.norm(first-rest,axis=1).max())
    if mode=='animation' and maximum<=extent*1e-7:raise ValueError('The plan does not animate actual skinned geometry')
    if mode=='static_pose' and maximum>extent*1e-7:raise ValueError('Static pose must hold its posture; enable animation for temporal tracks')
    if mode=='static_pose' and pose_delta<=extent*1e-7:raise ValueError('The plan does not change the existing pose')
    out=copy.deepcopy(doc);binary=bytearray(blob)
    out.pop('animations',None)
    if mode=='static_pose':out['nodes']=posed_nodes(doc,plan,0)
    else:
        animation={'name':'requested_joint_motion','samplers':[],'channels':[]}
        def add(values,kind):
            array=np.asarray(values,dtype='<f4');padding=(-len(binary))%4;binary.extend(b'\0'*padding);start=len(binary);binary.extend(array.tobytes())
            views=out.setdefault('bufferViews',[]);view=len(views);views.append({'buffer':0,'byteOffset':start,'byteLength':array.nbytes})
            accessors=out.setdefault('accessors',[]);index=len(accessors);a={'bufferView':view,'componentType':5126,'count':len(values),'type':kind}
            if kind=='SCALAR':a.update(min=[float(array.min())],max=[float(array.max())])
            accessors.append(a);return index
        for track in plan['tracks']:
            times=[float(s[0]) for s in track['samples']];path=track['path'];values=[posed_nodes(doc,{'tracks':[track]},t)[track['node']][path] for t in times]
            sampler=len(animation['samplers']);animation['samplers'].append({'input':add(times,'SCALAR'),'output':add(values,'VEC4' if path=='rotation' else 'VEC3'),'interpolation':'LINEAR'})
            animation['channels'].append({'sampler':sampler,'target':{'node':track['node'],'path':path}})
        out['animations']=[animation]
    out.setdefault('buffers',[{}])[0]['byteLength']=len(binary)
    return out,binary,{'pose_displacement':pose_delta,'temporal_displacement':maximum,'sampled_vertices':len(rest),'checked_times':checked_times,'geometry_kind':'skinned' if doc.get('skins') else 'rigid','physical_validation':False}


def animate_existing(source,output,prompt,model,mode='animation',subject='humanoid',planner=None,reviewer=None,source_description=None):
    source=Path(source).resolve();output=Path(output).resolve()
    if source==output:raise ValueError('The source model must remain unchanged')
    output.parent.mkdir(parents=True,exist_ok=True)
    original_hash=file_hash(source)
    doc,blob=glb_io.load(source);rigged_source=source
    if not doc.get('skins') and subject=='auto':
        anatomy=model_json(model,'Identify the ORIGINAL source object structure from its description, not a new pose or action. Return JSON only with rig_subject: humanoid, quadruped, or rigid. A human/elf retains humanoid anatomy in every posture. An inanimate object with an existing mesh hierarchy can receive rigid transforms; do not invent an animal skeleton. No pose presets.',{'source_description':source_description or '', 'mesh_nodes':sum('mesh' in n for n in doc.get('nodes',[]))})
        subject=anatomy.get('rig_subject')
        if subject not in {'humanoid','quadruped','rigid'}:raise ValueError('Source anatomy interpretation unavailable; original model preserved')
    if not doc.get('skins') and subject in {'humanoid','creature','quadruped'}:
        command=[sys.executable,str(Path(__file__).with_name('blender_bridge.py')),'--mode','rig','--mesh',str(source),'--rig-system','rigify','--subject-kind',subject,'--style','realistic','--output-dir',str(output.parent),'--run-id',output.stem+'_rig']
        print('PROGRESS:rig:construction du squelette, sans mouvement prédéfini',flush=True)
        run=subprocess.run(command,capture_output=True,text=True,check=False)
        records=[]
        for line in run.stdout.splitlines():
            try:
                record=json.loads(line)
                if isinstance(record,dict):records.append(record)
            except ValueError:pass
        result=next((r for r in reversed(records) if r.get('ok') and r.get('outputPath')),None)
        if not result:raise RuntimeError('Rigging did not produce an animatable skin: '+(run.stderr or run.stdout)[-800:])
        rigged_source=Path(result['outputPath']);doc,blob=glb_io.load(rigged_source)
    doc=canonical_trs(doc)
    context=skeleton_context(doc,blob)
    print('PROGRESS:animation:planification sur les articulations réelles du GLB',flush=True)
    attempts=[]
    for attempt in range(3):
        revised=prompt if not attempts else prompt+'\nPrevious plan failed measured compilation: '+attempts[-1]+'. Revise against the actual skeleton. Preserve the full request.'
        try:
            plan=(planner or infer_plan)(revised,context,model,mode)
            output.with_suffix('.attempt_%d.json' % (attempt+1)).write_text(json.dumps(plan,ensure_ascii=False,indent=2))
            out,binary,measurements=compile_plan(doc,blob,plan,mode)
            semantic_review=(reviewer or review_plan)(prompt,doc,blob,plan,model,mode) if reviewer or planner is None else None
            break
        except (ValueError,KeyError,TypeError,IndexError) as exc:
            attempts.append(str(exc))
            if attempt==2:raise ValueError('Joint planning failed after measured revisions: '+'; '.join(attempts)) from exc
            print('PROGRESS:animation:révision du plan après contrôle — '+str(exc),flush=True)
    for key in ('meshes','materials','images','textures','skins'):
        if out.get(key)!=doc.get(key):raise RuntimeError('Animation would alter source geometry or visual channels')
    if bytes(binary[:len(blob)])!=bytes(blob):raise RuntimeError('Animation altered existing binary data')
    if file_hash(source)!=original_hash:raise RuntimeError('Source changed during planning; derived result not published')
    glb_io.save(output,out,binary)
    report={'ok':True,'path':str(output),'source':str(source),'rigged_source':str(rigged_source),'source_sha256':original_hash,'plan':plan,'measurements':measurements,'mode':mode,'semantic_review':semantic_review,'revision_errors':attempts,'physical_validation':False}
    output.with_suffix('.motion.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return report


def deliver_existing(source,run_root,run_id,prompt,model,mode,subject='humanoid',planner=None,source_description=None):
    """Keep the input intact and publish a separate, recoverable derived run."""
    import shutil
    root=Path(run_root).resolve();source=Path(source).resolve()
    if source.is_relative_to(root):raise ValueError('Derived run must not contain its source')
    producer_hash=file_hash(__file__)
    work=root/'work';work.mkdir(parents=True,exist_ok=True)
    report=animate_existing(source,work/'requested.glb',prompt,model,mode,subject,planner,source_description=source_description)
    from livraison_organisee import organiser
    if mode=='animation':
        retained=work/'source.glb';shutil.copy2(source,retained)
        delivery=organiser(root,run_id,final_mesh=str(retained),rigged_mesh=report['path'])
    else:delivery=organiser(root,run_id,final_mesh=report['path'])
    if not delivery.get('ok'):raise RuntimeError('Packaging failed: '+str(delivery.get('error')))
    report['livraison']=delivery['livraison']
    report['path']=report['final_mesh']=report['livraison']['mouvement_couleurs' if mode=='animation' else 'modele_couleurs']
    # Preserve the plan and measured checks alongside the canonical deliverable.
    journal=root/'journal';journal.mkdir(exist_ok=True)
    (journal/'joint-plan.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from agi_core.operation_receipts import write_receipt
    write_receipt(root,run_id,prompt,producer_hash,report,[report['final_mesh']])
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True);parser.add_argument('--output');parser.add_argument('--run-root');parser.add_argument('--run-id')
    parser.add_argument('--prompt',required=True);parser.add_argument('--model',required=True)
    parser.add_argument('--mode',choices=['animation','static_pose'],default='animation');parser.add_argument('--subject',default='auto');parser.add_argument('--source-description')
    args=parser.parse_args()
    try:
        if args.run_root and args.run_id:result=deliver_existing(args.input,args.run_root,args.run_id,args.prompt,args.model,args.mode,args.subject,source_description=args.source_description)
        elif args.output:result=animate_existing(args.input,args.output,args.prompt,args.model,args.mode,args.subject,source_description=args.source_description)
        else:raise ValueError('Output or dedicated run root and ID required')
    except Exception as exc:result={'ok':False,'error':str(exc),'source_preserved':True}
    print(json.dumps(result,ensure_ascii=False));return 0 if result['ok'] else 1


if __name__=='__main__':sys.exit(main())
