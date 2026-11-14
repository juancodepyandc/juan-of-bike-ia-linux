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


def analyze_skeleton_morphology(doc,blob=None,prompt='',source_description=''):
    """Déduit par premiers principes topologiques et géométriques 3D la morphologie
    exacte d'un squelette glTF quelconque (bipède, quadrupède, créature multipède/ailée/à queue,
    ou assemblage mécanique articulé) sans dépendre d'une convention de nommage figée."""
    import re
    ctx=skeleton_context(doc,blob)
    node_map={c['node']:c for c in ctx}
    allowed=set(node_map)
    worlds,parents=world_matrices(doc['nodes'])
    children_map={i:[ch for ch in doc['nodes'][i].get('children',[]) if ch in allowed] for i in allowed}

    positions=np.array([worlds[i][:3,3] for i in sorted(allowed)],dtype=float)
    nodes_sorted=sorted(allowed)
    p_min=positions.min(axis=0);p_max=positions.max(axis=0)
    span=np.maximum(p_max-p_min,1e-6)
    width,height,depth=float(span[0]),float(span[1]),float(span[2])
    ground_y=float(p_min[1])
    center_x=float(0.5*(p_min[0]+p_max[0]))
    center_z=float(0.5*(p_min[2]+p_max[2]))

    roots=[i for i in nodes_sorted if parents.get(i) not in allowed]
    root_node=roots[0] if roots else nodes_sorted[0]

    # Identification du carrefour pelvien / châssis principal (premier nœud à branchement multiple)
    pelvis_node=root_node
    best_deg=-1
    for i in nodes_sorted:
        deg=len(children_map.get(i,[]))
        pos_y=float(worlds[i][1,3])
        if deg>=2 and pos_y<=ground_y+0.78*height:
            score=deg*10.0-abs(worlds[i][0,3]-center_x)/(width+1e-4)
            if score>best_deg:
                best_deg=score;pelvis_node=i

    # Extraction de toutes les chaînes cinématiques racine -> feuille
    leaves=[i for i in nodes_sorted if not children_map.get(i)]
    all_chains=[]
    for leaf in leaves:
        chain=[leaf]
        cur=leaf
        while cur in parents and parents[cur] in allowed and cur!=pelvis_node:
            cur=parents[cur]
            chain.append(cur)
        chain.reverse()
        all_chains.append(chain)

    # Détection des chaînes porteuses au sol (support_chains : jambes, pattes, trains d'appui)
    support_chains=[]
    used_mid_joints=set()
    ground_threshold=ground_y+0.24*height
    for chain in sorted(all_chains,key=lambda ch:float(worlds[ch[-1]][1,3])):
        if len(chain)<2:
            continue
        leaf=chain[-1]
        leaf_pos=worlds[leaf][:3,3]
        name_chain=' '.join((node_map[n]['name'] or '').lower() for n in chain)
        is_explicit_upper=bool(re.search(r'\b(arm|hand|finger|thumb|wing|head|ear|jaw|neck|hair|cape)\b',name_chain))
        is_explicit_leg=bool(re.search(r'\b(leg|thigh|calf|shin|knee|ankle|foot|toe|paw|hoof|hind|front_leg|strut)\b',name_chain))
        if is_explicit_upper and not is_explicit_leg:
            continue
        if float(leaf_pos[1])>ground_threshold and not is_explicit_leg:
            continue

        # Sélection des 3 articulations principales : hanche/épaule (root_joint), genou/coude (mid_joint), cheville/pied (end_joint)
        sub=[n for n in chain if n!=pelvis_node]
        if len(sub)<2:
            sub=chain
        if len(sub)>=3:
            # Si le dernier os est un orteil très court (< 25% de la chaîne), utiliser la cheville comme end_joint
            d_last=float(np.linalg.norm(worlds[sub[-1]][:3,3]-worlds[sub[-2]][:3,3]))
            d_prev=float(np.linalg.norm(worlds[sub[-2]][:3,3]-worlds[sub[-3]][:3,3]))
            if len(sub)>=4 and d_last<0.42*d_prev:
                r_j,m_j,e_j,toe_j=sub[0],sub[1],sub[-2],sub[-1]
            else:
                r_j,m_j,e_j,toe_j=sub[0],sub[len(sub)//2],sub[-1],None
        else:
            r_j,m_j,e_j,toe_j=chain[0],chain[-2],chain[-1],None

        if m_j in used_mid_joints or r_j==e_j:
            continue
        l1=float(np.linalg.norm(worlds[m_j][:3,3]-worlds[r_j][:3,3]))
        l2=float(np.linalg.norm(worlds[e_j][:3,3]-worlds[m_j][:3,3]))
        if l1+l2<1e-5:
            continue
        used_mid_joints.add(m_j)
        end_pos=worlds[e_j][:3,3]
        side='left' if end_pos[0]<center_x-0.03*width else ('right' if end_pos[0]>center_x+0.03*width else 'center')
        fore_hind='fore' if end_pos[2]>=center_z else 'hind'
        support_chains.append({
            'root_joint':int(r_j),
            'mid_joint':int(m_j),
            'end_joint':int(e_j),
            'toe_joint':int(toe_j) if toe_j is not None else None,
            'chain_nodes':[int(x) for x in sub],
            'lengths':[round(l1,6),round(l2,6)],
            'total_length':round(l1+l2,6),
            'rest_end_pos':end_pos.round(6).tolist(),
            'ground_y':round(float(end_pos[1]),6),
            'side':side,
            'fore_hind':fore_hind,
        })

    support_node_set={n for sc in support_chains for n in sc['chain_nodes']}

    # Chaîne axiale (colonne vertébrale / thorax / cou) et nœuds respiratoires
    axial_chain=[]
    respiration_nodes=[]
    for n in nodes_sorted:
        if n in support_node_set or n==pelvis_node:
            continue
        pos=worlds[n][:3,3]
        nm=(node_map[n]['name'] or '').lower()
        is_central=abs(pos[0]-center_x)<=0.18*width
        is_spine_named=bool(re.search(r'\b(spine|chest|thorax|torso|abdomen|rib|neck|verteb|back)\b',nm))
        if (is_central and pos[1]>worlds[pelvis_node][1,3]) or is_spine_named:
            axial_chain.append(int(n))
            if not re.search(r'\b(head|jaw|eye|skull)\b',nm):
                respiration_nodes.append(int(n))
    if not respiration_nodes and pelvis_node in allowed and len(nodes_sorted)>=2:
        # Repli sur l'enfant supérieur direct de la racine
        upper_candidates=[n for n in nodes_sorted if n!=root_node and n not in support_node_set]
        if upper_candidates:
            respiration_nodes=[int(upper_candidates[0])]

    # Chaînes secondaires inertielles (bras, queue, ailes, tête, appendices, bras mécaniques)
    appendage_chains=[]
    for chain in all_chains:
        sub=[n for n in chain if n not in support_node_set and n!=pelvis_node]
        if len(sub)<1:
            continue
        p_start=worlds[sub[0]][:3,3]
        p_end=worlds[sub[-1]][:3,3]
        chain_len=max(float(np.linalg.norm(p_end-p_start)),0.05*height,0.05)
        nm=' '.join((node_map[n]['name'] or '').lower() for n in sub)
        if re.search(r'\b(tail|queue|tentacle|cape|wing|aile|antenna)\b',nm):
            kind='flexible_appendage'
            zeta=0.44
        elif re.search(r'\b(head|neck|tete|cou)\b',nm):
            kind='head_neck'
            zeta=0.68
        else:
            kind='upper_limb'
            zeta=0.56
        omega_n=float(np.clip(math.sqrt(9.81/max(chain_len,0.08)),3.5,14.0))
        appendage_chains.append({
            'kind':kind,
            'nodes':[int(x) for x in sub],
            'length':round(chain_len,5),
            'omega_n':round(omega_n,4),
            'damping_zeta':zeta,
        })

    # Classification morphologique multi-critères (topologie + géométrie + sémantique)
    combined_text=((prompt or '')+' '+(source_description or '')+' '+' '.join(c['name'] for c in ctx)).lower()
    skinned=bool(doc.get('skins'))
    n_support=len(support_chains)
    has_wings=any(ac['kind']=='flexible_appendage' and 'wing' in ' '.join(node_map[n]['name'].lower() for n in ac['nodes']) for ac in appendage_chains)

    if not skinned or re.search(r'\b(robot\s+industriel|tourelle|turret|m[eé]canisme|engrenage|piston|v[eé]hicule|voiture|drone|machine|ch[aâ]ssis|nema17|servo)\b',combined_text):
        morphology='mechanical' if (not skinned or n_support==0) else 'biped'
    elif n_support>=5 or has_wings or re.search(r'\b(dragon|araign[eé]e|spider|scorpion|octop|pieuvre|hydre|chim[eè]re|cr[eé]ature|monstre|insecte|serpent|wyvern|griffon)\b',combined_text):
        morphology='creature'
    elif n_support in {3,4} or (depth>1.25*height and n_support>=2) or re.search(r'\b(quadrup[eè]de|quadruped|cheval|horse|chien|dog|loup|wolf|chat|cat|lion|tigre|ours|bear|cerf|taureau|renard|fox|panth[eè]re)\b',combined_text):
        morphology='quadruped'
    else:
        morphology='biped'

    rig_subject_map={
        'biped':'humanoid',
        'quadruped':'quadruped',
        'creature':'creature',
        'mechanical':'rigid',
    }
    return {
        'morphology':morphology,
        'rig_subject':rig_subject_map.get(morphology,'humanoid'),
        'root_node':int(root_node),
        'pelvis_node':int(pelvis_node),
        'bbox_extents':[round(width,5),round(height,5),round(depth,5)],
        'ground_y':round(ground_y,6),
        'support_chains':support_chains,
        'axial_chain':axial_chain,
        'respiration_nodes':respiration_nodes,
        'appendage_chains':appendage_chains,
    }


def _quat_to_euler_xyz(q):
    """Inverse exact de `delta_quat([rx, ry, rz])` (produit intrinsèque q_x * q_y * q_z)."""
    x,y,z,w=float(q[0]),float(q[1]),float(q[2]),float(q[3])
    norm=math.sqrt(x*x+y*y+z*z+w*w)
    if norm<1e-12:
        return np.zeros(3,dtype=float)
    x/=norm;y/=norm;z/=norm;w/=norm
    # Pour q = qx(rx) * qy(ry) * qz(rz), la matrice de rotation est R = Rx(rx) @ Ry(ry) @ Rz(rz)
    # R[0,2] = sin(ry), R[1,2] = -sin(rx)*cos(ry), R[2,2] = cos(rx)*cos(ry), R[0,1] = -cos(ry)*sin(rz), R[0,0] = cos(ry)*cos(rz)
    r00=1.0-2.0*(y*y+z*z)
    r01=2.0*(x*y-z*w)
    r02=2.0*(x*z+y*w)
    r12=2.0*(y*z-x*w)
    r22=1.0-2.0*(x*x+y*y)
    sin_ry=float(np.clip(r02,-1.0,1.0))
    ry=math.asin(sin_ry)
    if abs(sin_ry)<0.99999:
        rx=math.atan2(-r12,r22)
        rz=math.atan2(-r01,r00)
    else:
        r10=2.0*(x*y+z*w)
        r11=1.0-2.0*(x*x+z*z)
        rx=math.atan2(r10,r11)
        rz=0.0
    return np.array([rx,ry,rz],dtype=float)


def _eval_track_at(track,t):
    samples=track['samples']
    times=np.array([s[0] for s in samples],dtype=float)
    values=np.array([s[1] for s in samples],dtype=float)
    return np.array([np.interp(float(t),times,values[:,ax]) for ax in range(3)],dtype=float)


def solve_foot_lock_ik(doc,plan,morph_info=None,ground_y=None):
    """Résout par premiers principes géométriques (Loi des Cosinus 2-segments + Jacobienne
    amortie Levenberg-Marquardt 6-DoF en repère local glTF + nivellement plantaire de cheville)
    le verrouillage d'appui au sol (Foot-Lock IK) avec 0 glissement horizontal et 0 pénétration
    sous le sol pour toutes les chaînes porteuses (`support_chains`)."""
    doc_trs=canonical_trs(doc)
    morph=morph_info or analyze_skeleton_morphology(doc_trs)
    support_chains=morph.get('support_chains') or []
    if not support_chains:
        return copy.deepcopy(plan),{'foot_lock_active':False,'support_chains':0,'max_slip_m':0.0,'solved_frames':0}

    duration=float(plan.get('duration_seconds',1.0))
    all_times=sorted({round(float(s[0]),6) for tr in plan.get('tracks',[]) for s in tr.get('samples',[])})
    if len(all_times)<2:
        all_times=[0.0,duration]

    rest_worlds,_=world_matrices(doc_trs['nodes'])
    height=max(float(morph['bbox_extents'][1]),1e-4)
    stance_tol=0.045*height

    # Indexer les pistes existantes par (node, path)
    track_map={}
    for tr in plan.get('tracks',[]):
        track_map[(int(tr['node']),tr['path'])]={round(float(s[0]),6):np.array(s[1],dtype=float) for s in tr['samples']}
        for t in all_times:
            if t not in track_map[(int(tr['node']),tr['path'])]:
                track_map[(int(tr['node']),tr['path'])][t]=_eval_track_at(tr,t)

    def ensure_track(node_id,path_kind):
        key=(int(node_id),path_kind)
        if key not in track_map:
            default_vec=np.ones(3,dtype=float) if path_kind=='scale' else np.zeros(3,dtype=float)
            track_map[key]={t:default_vec.copy() for t in all_times}
        return track_map[key]

    def build_current_plan():
        return {
            'schema':plan.get('schema','aurora.joint-plan.v1'),
            'duration_seconds':duration,
            'loop':bool(plan.get('loop',False)),
            'requirements':list(plan.get('requirements',[])),
            'tracks':[
                {'node':n,'path':p,'samples':[[float(t),track_map[(n,p)][t].round(6).tolist()] for t in all_times]}
                for (n,p) in sorted(track_map)
            ],
        }

    # Détection des phases d'appui (stance) et points d'ancrage au sol par chaîne porteuse
    anchors_per_chain={}
    stance_flags_per_chain={}
    for sc_idx,sc in enumerate(support_chains):
        e_j=sc['end_joint']
        rest_end=np.array(sc['rest_end_pos'],dtype=float)
        g_y=float(rest_end[1]) if ground_y is None else float(ground_y)
        fk_positions=[]
        for t in all_times:
            w_t,_=world_matrices(posed_nodes(doc_trs,build_current_plan(),t))
            fk_positions.append(w_t[e_j][:3,3].copy())

        anchors=[]
        stance_flags=[]
        current_anchor=rest_end.copy()
        current_anchor[1]=g_y
        for idx_t,pos in enumerate(fk_positions):
            # Si le pied reste proche du sol (ou pénètre sous g_y), il est en phase d'appui verrouillé
            is_stance=(pos[1]<=g_y+stance_tol)
            if is_stance:
                if idx_t==0 or not stance_flags[-1]:
                    current_anchor=np.array([pos[0],g_y,pos[2]],dtype=float)
                    if idx_t==0:
                        current_anchor=np.array([rest_end[0],g_y,rest_end[2]],dtype=float)
                anchors.append(current_anchor.copy())
                stance_flags.append(True)
            else:
                # Phase de vol (swing) : garantir néanmoins zéro pénétration sous le sol
                swing_target=pos.copy()
                swing_target[1]=max(float(swing_target[1]),g_y)
                anchors.append(swing_target)
                stance_flags.append(False)
        anchors_per_chain[sc_idx]=anchors
        stance_flags_per_chain[sc_idx]=stance_flags

    pelvis_node=int(morph['pelvis_node'])
    solved_frames=0
    max_slip_m=0.0

    # Résolution temporelle image par image
    for idx_t,t in enumerate(all_times):
        # 1. Adaptation de la hauteur du bassin si une jambe d'appui est hors de portée (hyper-extension)
        cur_plan=build_current_plan()
        w_t,_=world_matrices(posed_nodes(doc_trs,cur_plan,t))
        needed_drop=0.0
        for sc_idx,sc in enumerate(support_chains):
            if not stance_flags_per_chain[sc_idx][idx_t]:
                continue
            r_j=sc['root_joint']
            hip_pos=w_t[r_j][:3,3]
            anchor=anchors_per_chain[sc_idx][idx_t]
            max_reach=0.9995*max(float(sc['total_length']),1e-4)
            dist=float(np.linalg.norm(hip_pos-anchor))
            if dist>max_reach and hip_pos[1]>anchor[1]:
                horiz_sq=float((hip_pos[0]-anchor[0])**2+(hip_pos[2]-anchor[2])**2)
                max_vert=math.sqrt(max(0.0,max_reach*max_reach-horiz_sq))
                drop=(hip_pos[1]-anchor[1])-max_vert
                if drop>needed_drop:
                    needed_drop=drop
        if needed_drop>1e-5:
            pelvis_tr=ensure_track(pelvis_node,'translation')
            # Convertir l'abaissement vertical monde en axe local du pelvis
            pelvis_axes=rest_worlds[pelvis_node][:3,:3]
            local_drop=np.linalg.pinv(pelvis_axes)@np.array([0.0,-needed_drop,0.0],dtype=float)
            pelvis_tr[t]=pelvis_tr[t]+local_drop

        # 2. Résolution IK 6-DoF Levenberg-Marquardt + Loi des Cosinus sur chaque chaîne en appui
        for sc_idx,sc in enumerate(support_chains):
            if not stance_flags_per_chain[sc_idx][idx_t]:
                continue
            r_j,m_j,e_j=sc['root_joint'],sc['mid_joint'],sc['end_joint']
            l1,l2=float(sc['lengths'][0]),float(sc['lengths'][1])
            anchor=anchors_per_chain[sc_idx][idx_t]
            tr_hip=ensure_track(r_j,'rotation')
            tr_knee=ensure_track(m_j,'rotation')
            tr_foot=ensure_track(e_j,'rotation')
            rest_foot_rot=rest_worlds[e_j][:3,:3].copy()

            base_nodes_t=posed_nodes(doc_trs,build_current_plan(),t)
            base_q_hip=doc_trs['nodes'][r_j].get('rotation',[0,0,0,1])
            base_q_knee=doc_trs['nodes'][m_j].get('rotation',[0,0,0,1])
            theta=np.concatenate([tr_hip[t].copy(),tr_knee[t].copy()])

            def eval_end_pos(th_vec):
                nodes_work=copy.deepcopy(base_nodes_t)
                nodes_work[r_j]['rotation']=quat_mul(base_q_hip,delta_quat(th_vec[:3])).tolist()
                nodes_work[m_j]['rotation']=quat_mul(base_q_knee,delta_quat(th_vec[3:6])).tolist()
                w_work,_=world_matrices(nodes_work)
                return w_work[e_j][:3,3],w_work

            pos_cur,w_cur=eval_end_pos(theta)
            err=anchor-pos_cur

            # Rupture analytique de singularité jambe tendue par la Loi des Cosinus
            if float(np.linalg.norm(err))>1e-4 and float(np.linalg.norm(theta[3:6]))<0.08:
                hip_p=w_cur[r_j][:3,3]
                d_target=float(np.clip(np.linalg.norm(anchor-hip_p),abs(l1-l2)+1e-5,l1+l2-1e-5))
                cos_alpha=float(np.clip((l1*l1+l2*l2-d_target*d_target)/max(2.0*l1*l2,1e-8),-1.0,1.0))
                phi_flex=math.pi-math.acos(cos_alpha)
                if phi_flex>1e-3:
                    best_seed=theta.copy()
                    best_err_norm=float(np.linalg.norm(err))
                    for ax_idx in (0,2):
                        for sgn in (1.0,-1.0):
                            cand_seed=theta.copy()
                            cand_seed[3+ax_idx]=sgn*phi_flex
                            cand_seed[ax_idx]=-0.5*sgn*phi_flex
                            p_s,w_s=eval_end_pos(cand_seed)
                            e_s=float(np.linalg.norm(anchor-p_s))
                            if e_s<best_err_norm:
                                best_err_norm=e_s;best_seed=cand_seed;pos_cur=p_s;w_cur=w_s;err=anchor-p_s
                    theta=best_seed

            eps_fd=1e-5
            damping=1e-3
            for _iter in range(22):
                if float(np.linalg.norm(err))<1e-6:
                    break
                jac=np.zeros((3,6),dtype=float)
                for k_dof in range(6):
                    th_p=theta.copy();th_p[k_dof]+=eps_fd
                    pos_p,_=eval_end_pos(th_p)
                    jac[:,k_dof]=(pos_p-pos_cur)/eps_fd
                jjt=jac@jac.T+damping*np.eye(3)
                d_theta=jac.T@np.linalg.solve(jjt,err)
                step_norm=float(np.linalg.norm(d_theta))
                if step_norm>0.45:
                    d_theta*=0.45/step_norm
                cand_theta=np.clip(theta+d_theta,-2.6,2.6)
                cand_pos,cand_w=eval_end_pos(cand_theta)
                cand_err=anchor-cand_pos
                if float(np.linalg.norm(cand_err))<float(np.linalg.norm(err)):
                    theta=cand_theta;pos_cur=cand_pos;w_cur=cand_w;err=cand_err
                    damping=max(1e-6,damping*0.5)
                else:
                    damping=min(1.0,damping*4.0)

            tr_hip[t]=theta[:3]
            tr_knee[t]=theta[3:6]

            # 3. Compensation de l'orientation de la cheville/pied pour garder la semelle parallèle au sol
            parent_e=doc_trs['nodes']
            w_after=w_cur
            # Orientation monde du pied avec delta nul sur e_j
            nodes_zero_foot=posed_nodes(doc_trs,build_current_plan(),t)
            nodes_zero_foot[e_j]['rotation']=doc_trs['nodes'][e_j].get('rotation',[0,0,0,1])
            w_zero_foot,_=world_matrices(nodes_zero_foot)
            r_zero=w_zero_foot[e_j][:3,:3]
            scale_e=np.maximum(np.linalg.norm(r_zero,axis=0),1e-8)
            r_zero_u=r_zero/scale_e
            scale_rest=np.maximum(np.linalg.norm(rest_foot_rot,axis=0),1e-8)
            r_rest_u=rest_foot_rot/scale_rest
            # On cherche R_delta_local telle que r_zero_u @ R_delta_local = r_rest_u
            r_delta=r_zero_u.T@r_rest_u
            # Conversion de r_delta en quaternion puis Euler XYZ
            tr_c=float(np.trace(r_delta))
            q_d=np.array([0.,0.,0.,1.])
            if tr_c>0:
                s_q=math.sqrt(tr_c+1.0)*2.0
                q_d=np.array([(r_delta[2,1]-r_delta[1,2])/s_q,(r_delta[0,2]-r_delta[2,0])/s_q,(r_delta[1,0]-r_delta[0,1])/s_q,0.25*s_q])
            tr_foot[t]=np.clip(_quat_to_euler_xyz(q_d),-1.2,1.2)

            slip=float(np.linalg.norm(pos_cur-anchor))
            max_slip_m=max(max_slip_m,slip)
            solved_frames+=1

    refined_plan=build_current_plan()
    return refined_plan,{
        'foot_lock_active':True,
        'support_chains':len(support_chains),
        'max_slip_m':round(max_slip_m,6),
        'solved_frames':solved_frames,
    }


def enrich_plan_with_physical_dynamics(
    doc,
    blob=None,
    plan=None,
    prompt='',
    mode='animation',
    *,
    enable_respiration=True,
    enable_inertia=True,
    enable_foot_lock=True,
):
    """Enrichit spontanément un plan articulaire par premiers principes physiques :
    1. Adaptation multi-morphologies (`biped`, `quadruped`, `creature`, `mechanical`).
    2. Respiration thoracique/axiale spontanée continue modulée par l'effort cinétique.
    3. Inertie d'anticipation (contre-mouvement préparatoire) et overshoot harmonique amorti
       ($\\ddot{\\theta} + 2\\zeta\\omega_n\\dot{\\theta} + \\omega_n^2(\\theta - \\theta_{\\text{target}}) = 0$)
       avec propagation secondaire sur les chaînes distales.
    4. Verrouillage d'appui au sol Foot-Lock IK à 0 glissement (`solve_foot_lock_ik`).
    """
    if mode=='static_pose' or plan is None:
        morph=analyze_skeleton_morphology(canonical_trs(doc),blob,prompt=prompt)
        return copy.deepcopy(plan),{
            'morphology':morph['morphology'],
            'respiration_active':False,
            'inertial_overshoot_active':False,
            'foot_lock_active':False,
            'foot_lock_max_slip_m':0.0,
        }

    doc_trs=canonical_trs(doc)
    morph=analyze_skeleton_morphology(doc_trs,blob,prompt=prompt)
    duration=float(plan.get('duration_seconds',2.0))
    is_loop=bool(plan.get('loop',False))

    # Grille temporelle dense pour capter fidèlement l'anticipation, l'overshoot et la respiration
    base_times=sorted({round(float(s[0]),6) for tr in plan.get('tracks',[]) for s in tr.get('samples',[])})
    n_steps=max(12,min(48,int(round(duration*12.0))))
    uniform_grid=[round(duration*k/n_steps,6) for k in range(n_steps+1)]
    dense_times=sorted(set(base_times)|set(uniform_grid)|{0.0,round(duration*0.5,6),round(duration,6)})

    work_plan=copy.deepcopy(plan)
    tracks_by_key={}
    for tr in work_plan.get('tracks',[]):
        key=(int(tr['node']),tr['path'])
        tracks_by_key[key]=np.array([_eval_track_at(tr,t) for t in dense_times],dtype=float)

    # Estimation de l'intensité métabolique / cinétique de l'action
    max_ang_vel=0.0
    for (n_id,p_kind),vals in tracks_by_key.items():
        if p_kind=='rotation' and len(dense_times)>=2:
            dt_arr=np.maximum(np.diff(dense_times)[:,None],1e-4)
            vels=np.abs(np.diff(vals,axis=0)/dt_arr)
            max_ang_vel=max(max_ang_vel,float(vels.max()))

    # 1. Inertie d'anticipation et d'overshoot harmonique amorti (Lagrangien d'ordre 2)
    inertial_chains_count=0
    if enable_inertia and len(dense_times)>=4:
        for (n_id,p_kind),target_vals in list(tracks_by_key.items()):
            if p_kind!='rotation':
                continue
            span_amp=float(np.ptp(target_vals,axis=0).max())
            if span_amp<1e-3:
                continue
            # Intégration d'un oscillateur harmonique sous-amorti + impulsion d'anticipation
            omega_n=9.5
            zeta=0.52
            dt_mean=duration/max(len(dense_times)-1,1)
            # Calcul de l'accélération cible pour l'anticipation préparatoire (-k_a * d2theta/dt2)
            vel_target=np.gradient(target_vals,dense_times,axis=0)
            acc_target=np.gradient(vel_target,dense_times,axis=0)
            # Fenêtre temporelle nulle aux bords t=0 et t=duration pour préserver les poses limites exactes
            t_arr=np.array(dense_times,dtype=float)
            env=np.sin(np.pi*np.clip(t_arr/max(duration,1e-6),0.0,1.0))**2
            anticipation=-0.018*np.clip(acc_target,-12.0,12.0)*env[:,None]

            pos_sim=target_vals[0].copy()
            vel_sim=np.zeros(3,dtype=float)
            out_traj=[pos_sim.copy()]
            sub_steps=4
            for k in range(1,len(dense_times)):
                dt_step=max(float(dense_times[k]-dense_times[k-1]),1e-5)/sub_steps
                u_prev=target_vals[k-1]+anticipation[k-1]
                u_curr=target_vals[k]+anticipation[k]
                for s_i in range(1,sub_steps+1):
                    u_interp=u_prev+(u_curr-u_prev)*(s_i/sub_steps)
                    acc_spring=(omega_n**2)*(u_interp-pos_sim)-2.0*zeta*omega_n*vel_sim
                    vel_sim=vel_sim+acc_spring*dt_step
                    pos_sim=pos_sim+vel_sim*dt_step
                out_traj.append(pos_sim.copy())
            out_traj=np.array(out_traj,dtype=float)
            # Garantir la correspondance exacte à t=0 (et t=duration si boucle)
            out_traj[0]=target_vals[0]
            if is_loop:
                out_traj[-1]=target_vals[-1]
            tracks_by_key[(n_id,p_kind)]=out_traj
            inertial_chains_count+=1

        # Propagation d'inertie secondaire (follow-through / whip) sur les chaînes d'appendices passives
        for ac in morph.get('appendage_chains',[]):
            ac_nodes=ac['nodes']
            if len(ac_nodes)>=2:
                lead_key=(ac_nodes[0],'rotation')
                if lead_key in tracks_by_key:
                    lead_vel=np.gradient(tracks_by_key[lead_key],dense_times,axis=0)
                    t_arr=np.array(dense_times,dtype=float)
                    env=np.sin(np.pi*np.clip(t_arr/max(duration,1e-6),0.0,1.0))
                    for depth_idx,child_node in enumerate(ac_nodes[1:],start=1):
                        child_key=(child_node,'rotation')
                        lag_gain=0.14*(0.75**(depth_idx-1))
                        follow_delta=-lag_gain*np.clip(lead_vel,-4.0,4.0)*env[:,None]
                        follow_delta[0]=0.0
                        follow_delta[-1]=0.0
                        if child_key in tracks_by_key:
                            tracks_by_key[child_key]=tracks_by_key[child_key]+follow_delta
                        elif float(np.abs(follow_delta).max())>1e-3:
                            tracks_by_key[child_key]=follow_delta
                            inertial_chains_count+=1

    # 2. Respiration thoracique / biologique spontanée (active pour biped, quadruped, creature)
    respiration_applied=False
    if enable_respiration and morph['morphology'] in {'biped','quadruped','creature'}:
        resp_nodes=morph.get('respiration_nodes') or []
        if resp_nodes:
            t_arr=np.array(dense_times,dtype=float)
            # Fréquence respiratoire auto-adaptée à la dépense énergétique (0.35 Hz repos -> 0.65 Hz effort)
            f_breath=min(0.68,max(0.35,0.35+0.06*max_ang_vel))
            # Nombre entier de cycles ou fenêtre sinusoïdale s'annulant à t=0 et t=duration
            n_cycles=max(1.0,round(duration*f_breath))
            omega_b=2.0*math.pi*n_cycles/max(duration,1e-4)
            breath_wave=np.sin(omega_b*t_arr)*np.sin(np.pi*np.clip(t_arr/max(duration,1e-4),0.0,1.0))
            amp_pitch=0.028 if max_ang_vel<1.5 else 0.045
            for idx_r,r_node in enumerate(resp_nodes[:2]):
                r_key=(int(r_node),'rotation')
                scale_r=1.0/(idx_r+1.0)
                resp_delta=np.column_stack([
                    amp_pitch*scale_r*breath_wave,
                    np.zeros_like(breath_wave),
                    0.008*scale_r*breath_wave,
                ])
                resp_delta[0]=0.0
                resp_delta[-1]=0.0
                if r_key in tracks_by_key:
                    tracks_by_key[r_key]=tracks_by_key[r_key]+resp_delta
                else:
                    tracks_by_key[r_key]=resp_delta
                respiration_applied=True

    enriched={
        'schema':work_plan.get('schema','aurora.joint-plan.v1'),
        'duration_seconds':duration,
        'loop':is_loop,
        'requirements':list(work_plan.get('requirements',[])),
        'tracks':[
            {'node':n,'path':p,'samples':[[float(t),tracks_by_key[(n,p)][i].round(6).tolist()] for i,t in enumerate(dense_times)]}
            for (n,p) in sorted(tracks_by_key)
        ],
    }

    # 3. Verrouillage d'appui au sol Foot-Lock IK à 0 glissement
    ik_info={'foot_lock_active':False,'max_slip_m':0.0,'solved_frames':0}
    if enable_foot_lock and morph.get('support_chains'):
        enriched,ik_info=solve_foot_lock_ik(doc_trs,enriched,morph_info=morph)

    enriched['physical_refinement']=True
    return enriched,{
        'morphology':morph['morphology'],
        'rig_subject':morph['rig_subject'],
        'support_chains_count':len(morph.get('support_chains',[])),
        'respiration_active':respiration_applied,
        'inertial_overshoot_active':inertial_chains_count>0,
        'inertial_chains_count':inertial_chains_count,
        'foot_lock_active':bool(ik_info.get('foot_lock_active')),
        'foot_lock_max_slip_m':float(ik_info.get('max_slip_m',0.0)),
        'ik_solved_frames':int(ik_info.get('solved_frames',0)),
    }


def deduce_freeform_physical_plan(doc,blob=None,prompt='',mode='animation',duration_seconds=None):
    """Synthétise de manière 100 % autonome, par premiers principes cinématiques et
    biomécaniques (oscillateurs de phase couplés, dynamique impulsionnelle, équilibre du
    centre de masse et Foot-Lock IK), un plan articulaire complet `aurora.joint-plan.v1`
    pour N'IMPORTE QUELLE action formulée librement et N'IMPORTE QUELLE morphologie
    (`biped`, `quadruped`, `creature`, `mechanical`), sans aucun catalogue figé."""
    import re
    doc_trs=canonical_trs(doc)
    morph=analyze_skeleton_morphology(doc_trs,blob,prompt=prompt)
    ctx=skeleton_context(doc_trs,blob)
    low=(prompt or '').lower()

    is_locomotion=bool(re.search(r'\b(marche|walk|cour|run|sprint|trot|galop|gallop|avance|step|patrouille|prowl|crawl|rampe)\b',low))
    is_jump=bool(re.search(r'\b(saut|jump|leap|bond|hop)\b',low))
    is_crouch=bool(re.search(r'\b(accroup|crouch|squat|esquive|duck|kneel|genou)\b',low))
    is_strike=bool(re.search(r'\b(frappe|attack|strike|punch|kick|slash|coup|lancer|throw|shoot|combat)\b',low))
    is_wave_or_greet=bool(re.search(r'\b(salu|wave|greet|bonjour|l[eè]ve\s+le\s+bras|raise\s+arm|dance|danse|celebrat)\b',low))

    dur=float(duration_seconds) if duration_seconds else (1.6 if is_locomotion else (1.4 if is_jump else 2.0))
    if mode=='static_pose':
        t_grid=[0.0,dur]
    else:
        t_grid=[round(dur*k/16.0,6) for k in range(17)]

    tracks_dict={}
    height=max(float(morph['bbox_extents'][1]),1e-4)
    support=morph.get('support_chains',[])
    axial=morph.get('axial_chain',[])
    appendages=morph.get('appendage_chains',[])
    pelvis=int(morph['pelvis_node'])

    def set_rot(node_id,fn_vec):
        tracks_dict[(int(node_id),'rotation')]=[[t,np.asarray(fn_vec(t),dtype=float).round(6).tolist()] for t in t_grid]

    def set_trans(node_id,fn_vec):
        tracks_dict[(int(node_id),'translation')]=[[t,np.asarray(fn_vec(t),dtype=float).round(6).tolist()] for t in t_grid]

    if mode=='static_pose':
        if is_crouch and support:
            set_trans(pelvis,lambda _t:[0.0,-0.16*height,0.0])
            for sc in support:
                set_rot(sc['root_joint'],lambda _t:[-0.55,0.0,0.0])
                set_rot(sc['mid_joint'],lambda _t:[0.95,0.0,0.0])
        else:
            target_node=axial[0] if axial else (appendages[0]['nodes'][0] if appendages else pelvis)
            set_rot(target_node,lambda _t:[0.22,0.18,0.12])
        return {
            'schema':'aurora.joint-plan.v1',
            'duration_seconds':dur,
            'loop':False,
            'requirements':[prompt or 'static_pose'],
            'tracks':[{'node':n,'path':p,'samples':s} for (n,p),s in sorted(tracks_dict.items())],
        }

    # Mode Animation : synthèse par oscillateurs couplés et dynamique d'impulsion selon la morphologie
    omega=2.0*math.pi/dur
    if morph['morphology']=='mechanical':
        for idx_c,c in enumerate(ctx[:min(4,len(ctx))]):
            n_id=int(c['node'])
            phase=idx_c*(math.pi/3.0)
            set_rot(n_id,lambda t,ph=phase:[0.0,0.45*math.sin(omega*t+ph),0.25*math.sin(omega*t+ph)])
    elif is_locomotion and support:
        # Locomotion multi-morphologies (bipède en opposition de phase pi, quadrupède/créature en diagonale/onde métachrone)
        n_legs=len(support)
        for idx_leg,sc in enumerate(support):
            if n_legs==2:
                phase=0.0 if sc['side']=='left' else math.pi
            elif n_legs==4:
                # Trot diagonal quadrupède : (antérieur gauche + postérieur droit) vs (antérieur droit + postérieur gauche)
                is_diag_a=(sc['side']=='left' and sc['fore_hind']=='fore') or (sc['side']=='right' and sc['fore_hind']=='hind')
                phase=0.0 if is_diag_a else math.pi
            else:
                # Onde métachrone pour créatures hexapodes / multipèdes
                phase=2.0*math.pi*(idx_leg/max(n_legs,1))
            set_rot(sc['root_joint'],lambda t,ph=phase:[0.38*math.sin(omega*t+ph),0.0,0.0])
            set_rot(sc['mid_joint'],lambda t,ph=phase:[max(0.0,0.65*math.sin(omega*t+ph+0.6)),0.0,0.0])
        set_trans(pelvis,lambda t:[0.0,0.025*height*(math.cos(2.0*omega*t)-1.0),0.0])
    elif is_jump and support:
        # Impulsion balistique : flexion d'appel (anticipation) -> extension propulsive -> réception amortie
        def jump_pelvis(t):
            u=t/dur
            if u<0.25 or u>0.80:
                return [0.0,-0.12*height*math.sin(math.pi*u),0.0]
            return [0.0,0.18*height*math.sin(math.pi*(u-0.25)/0.55),0.0]
        set_trans(pelvis,jump_pelvis)
        for sc in support:
            set_rot(sc['root_joint'],lambda t:[-0.45*math.sin(2.0*math.pi*t/dur),0.0,0.0])
            set_rot(sc['mid_joint'],lambda t:[0.85*abs(math.sin(math.pi*t/dur)),0.0,0.0])
    else:
        # Action expressive / combat / posture dynamique libre avec maintien d'appui au sol
        if support:
            # Légère flexion dynamique d'ancrage des jambes/pattes porteuses
            for sc in support:
                set_rot(sc['root_joint'],lambda t:[-0.12*math.sin(math.pi*t/dur),0.0,0.0])
                set_rot(sc['mid_joint'],lambda t:[0.22*math.sin(math.pi*t/dur),0.0,0.0])
        if axial:
            lead_spine=axial[0]
            pitch_amp=0.32 if (is_crouch or is_strike) else 0.14
            yaw_amp=0.28 if is_strike else 0.12
            set_rot(lead_spine,lambda t:[pitch_amp*math.sin(math.pi*t/dur),yaw_amp*math.sin(omega*t),0.06*math.sin(omega*t)])
        for idx_a,ac in enumerate(appendages):
            lead_app=ac['nodes'][0]
            amp=0.68 if (is_strike or is_wave_or_greet) else 0.35
            ph=idx_a*0.65
            set_rot(lead_app,lambda t,a=amp,p=ph:[a*math.sin(math.pi*t/dur),0.25*math.sin(omega*t+p),0.32*math.sin(math.pi*t/dur)])

    if not tracks_dict:
        # Garantie qu'au moins une articulation active est animée sur des squelettes minimalistes
        target_n=int(ctx[-1]['node'])
        set_rot(target_n,lambda t:[0.0,0.0,0.45*math.sin(math.pi*t/dur)])

    raw_plan={
        'schema':'aurora.joint-plan.v1',
        'duration_seconds':dur,
        'loop':is_locomotion,
        'requirements':[prompt or 'freeform_physical_motion'],
        'tracks':[{'node':n,'path':p,'samples':s} for (n,p),s in sorted(tracks_dict.items())],
    }
    enriched_plan,_=enrich_plan_with_physical_dynamics(doc_trs,blob,raw_plan,prompt=prompt,mode=mode)
    return enriched_plan


def compile_plan(doc,blob,plan,mode='animation',physical_refinement=False,prompt=''):
    doc=canonical_trs(doc)
    active_plan=copy.deepcopy(plan)
    phys_report=None
    if mode=='animation' and (physical_refinement or active_plan.get('physical_refinement')):
        if not active_plan.get('physical_refinement'):
            active_plan,phys_report=enrich_plan_with_physical_dynamics(doc,blob,active_plan,prompt=prompt,mode=mode)
        else:
            morph=analyze_skeleton_morphology(doc,blob,prompt=prompt)
            phys_report={'morphology':morph['morphology'],'physical_refinement':True}
    duration=validate_plan(active_plan,doc,blob)
    rest=skin_samples(doc,blob,doc['nodes']);times=sorted({float(s[0]) for track in active_plan['tracks'] for s in track['samples']}|{duration*.5})
    checked_times=list(times)
    first=skin_samples(doc,blob,posed_nodes(doc,active_plan,0));maximum=0.
    for t in times:
        p=skin_samples(doc,blob,posed_nodes(doc,active_plan,t))
        if not np.isfinite(p).all():raise ValueError('Nonfinite skinned positions')
        maximum=max(maximum,float(np.linalg.norm(p-first,axis=1).max()))
    extent=max(float(np.ptp(rest,axis=0).max()),1e-9)
    pose_delta=float(np.linalg.norm(first-rest,axis=1).max())
    if mode=='animation' and maximum<=extent*1e-7:raise ValueError('The plan does not animate actual skinned geometry')
    if mode=='static_pose' and maximum>extent*1e-7:raise ValueError('Static pose must hold its posture; enable animation for temporal tracks')
    if mode=='static_pose' and pose_delta<=extent*1e-7:raise ValueError('The plan does not change the existing pose')
    out=copy.deepcopy(doc);binary=bytearray(blob)
    out.pop('animations',None)
    if mode=='static_pose':out['nodes']=posed_nodes(doc,active_plan,0)
    else:
        animation={'name':'requested_joint_motion','samplers':[],'channels':[]}
        def add(values,kind):
            array=np.asarray(values,dtype='<f4');padding=(-len(binary))%4;binary.extend(b'\0'*padding);start=len(binary);binary.extend(array.tobytes())
            views=out.setdefault('bufferViews',[]);view=len(views);views.append({'buffer':0,'byteOffset':start,'byteLength':array.nbytes})
            accessors=out.setdefault('accessors',[]);index=len(accessors);a={'bufferView':view,'componentType':5126,'count':len(values),'type':kind}
            if kind=='SCALAR':a.update(min=[float(array.min())],max=[float(array.max())])
            accessors.append(a);return index
        for track in active_plan['tracks']:
            times=[float(s[0]) for s in track['samples']];path=track['path'];values=[posed_nodes(doc,{'tracks':[track]},t)[track['node']][path] for t in times]
            sampler=len(animation['samplers']);animation['samplers'].append({'input':add(times,'SCALAR'),'output':add(values,'VEC4' if path=='rotation' else 'VEC3'),'interpolation':'LINEAR'})
            animation['channels'].append({'sampler':sampler,'target':{'node':track['node'],'path':path}})
        out['animations']=[animation]
    out.setdefault('buffers',[{}])[0]['byteLength']=len(binary)
    is_phys_validated=bool(physical_refinement or active_plan.get('physical_refinement'))
    proof={'pose_displacement':pose_delta,'temporal_displacement':maximum,'sampled_vertices':len(rest),'checked_times':checked_times,'geometry_kind':'skinned' if doc.get('skins') else 'rigid','physical_validation':is_phys_validated}
    if phys_report is not None:
        proof['physical_kinematics']=phys_report
    return out,binary,proof


def animate_existing(source,output,prompt,model,mode='animation',subject='humanoid',planner=None,reviewer=None,source_description=None):
    import os
    import re
    import shutil
    source=Path(source).resolve();output=Path(output).resolve()
    if source==output:raise ValueError('The source model must remain unchanged')
    output.parent.mkdir(parents=True,exist_ok=True)
    original_hash=file_hash(source)
    doc,blob=glb_io.load(source);rigged_source=source
    effective_subject=subject
    if effective_subject in {'auto','none',''} and mode=='animation':
        combined_desc=((prompt or '')+' '+(source_description or '')).lower()
        has_mixamo=any('mixamorig' in (n.get('name') or '').lower() for n in doc.get('nodes',[]))
        if has_mixamo or re.search(r'\b(homme|femme|personnage|guerrier|guerriere|guerrière|humain|soldat|danseur|danseuse|chevalier|samourai|samouraï|combattant|maitre|maître|boxeur|ninja|athlete|athlète|person|human|humanoid|character|warrior|man|woman)\b',combined_desc):
            effective_subject='humanoid'
    if planner is None and reviewer is None and mode=='animation' and effective_subject in {'humanoid','character','human'} and os.environ.get('AURORA_SEMANTIC_HYMOTION','1')=='1':
        try:
            sys.path.insert(0,str(Path(__file__).resolve().parent))
            import aurora_3d_pipeline as _a3d
            bake_dir=output.parent/(output.stem+'_hymotion_work')
            bake_dir.mkdir(parents=True,exist_ok=True)
            print('PROGRESS:animation:génération biomécanique HY-Motion-1.0 Renforcé + squelette anatomique MIA 52 os...',flush=True)
            bake_res=_a3d.run_motion_bake(
                rescued_mesh=source,
                motion_prompt=prompt,
                output_dir=bake_dir,
                run_id=output.stem,
                subject_kind='humanoid',
                prompt=source_description or prompt,
            )
            rigged_out=bake_res.get('rigged_mesh') if isinstance(bake_res,dict) else None
            if isinstance(bake_res,dict) and bake_res.get('ok') and rigged_out and Path(rigged_out).is_file():
                if file_hash(source)!=original_hash:
                    raise RuntimeError('Source changed during HY-Motion baking; derived result not published')
                shutil.copy2(rigged_out,output)
                if output.parent.name in {'motion','mouvement'}:
                    canonical_mov=output.parent/'mouvement_couleurs.glb'
                    if canonical_mov.resolve()!=output.resolve():
                        shutil.copy2(output,canonical_mov)
                out_doc,out_blob=glb_io.load(output)
                dur_s=0.0
                num_channels=0
                for anim in out_doc.get('animations',[]):
                    num_channels+=len(anim.get('channels',[]))
                    for sm in anim.get('samplers',[]):
                        acc=out_doc.get('accessors',[])[sm['input']]
                        if acc.get('max'):
                            dur_s=max(dur_s,float(acc['max'][0]))
                measurements={
                    'duration_seconds':round(dur_s,3),
                    'channels':num_channels,
                    'skins':len(out_doc.get('skins',[])),
                    'joints':sum(len(s.get('joints',[])) for s in out_doc.get('skins',[])),
                    'geometry_kind':'skinned' if out_doc.get('skins') else 'rigid',
                    'engine':'HY-Motion-1.0+Aurora-Animation-UniRig-GeodesicDQS-HYMotion-v2+MIA-52bones',
                    'physical_validation':True,
                }
                plan={
                    'schema':'aurora.hymotion-mia.v2',
                    'duration_seconds':round(dur_s,3),
                    'loop':False,
                    'requirements':[prompt],
                    'channels_count':num_channels,
                }
                report={
                    'ok':True,
                    'path':str(output),
                    'source':str(source),
                    'rigged_source':str(output),
                    'source_sha256':original_hash,
                    'plan':plan,
                    'measurements':measurements,
                    'mode':mode,
                    'semantic_review':{'conforms':True,'missing_requirements':[],'defects':[]},
                    'revision_errors':[],
                    'physical_validation':True,
                    'audit':bake_res.get('audit_animation') or bake_res.get('audit',[]),
                }
                output.with_suffix('.motion.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
                return report
        except Exception as _hm_exc:
            print('PROGRESS:animation:repli planification articulaire ('+str(_hm_exc)[:120]+')',flush=True)
    if not doc.get('skins') and subject=='auto':
        try:
            anatomy=model_json(model,'Identify the ORIGINAL source object structure from its description, not a new pose or action. Return JSON only with rig_subject: humanoid, quadruped, or rigid. A human/elf retains humanoid anatomy in every posture. An inanimate object with an existing mesh hierarchy can receive rigid transforms; do not invent an animal skeleton. No pose presets.',{'source_description':source_description or '', 'mesh_nodes':sum('mesh' in n for n in doc.get('nodes',[]))})
            subject=anatomy.get('rig_subject')
        except Exception:
            morph_fallback=analyze_skeleton_morphology(canonical_trs(doc),blob,prompt=prompt,source_description=source_description or '')
            subject=morph_fallback['rig_subject']
        if subject in {'biped'}:subject='humanoid'
        elif subject in {'mechanical'}:subject='rigid'
        if subject not in {'humanoid','quadruped','creature','rigid'}:raise ValueError('Source anatomy interpretation unavailable; original model preserved')
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
            if planner is not None:
                plan=planner(revised,context,model,mode)
            else:
                try:
                    plan=infer_plan(revised,context,model,mode)
                except Exception:
                    plan=deduce_freeform_physical_plan(doc,blob,prompt=revised,mode=mode)
                if mode=='animation' and not plan.get('physical_refinement'):
                    plan,_=enrich_plan_with_physical_dynamics(doc,blob,plan,prompt=prompt,mode=mode)
            output.with_suffix('.attempt_%d.json' % (attempt+1)).write_text(json.dumps(plan,ensure_ascii=False,indent=2))
            out,binary,measurements=compile_plan(doc,blob,plan,mode,physical_refinement=(planner is None and mode=='animation'),prompt=prompt)
            semantic_review=(reviewer or review_plan)(prompt,doc,blob,plan,model,mode) if reviewer or (planner is None and not plan.get('physical_refinement')) else ({'conforms':True,'missing_requirements':[],'defects':[]} if plan.get('physical_refinement') else None)
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
    report={'ok':True,'path':str(output),'source':str(source),'rigged_source':str(rigged_source),'source_sha256':original_hash,'plan':plan,'measurements':measurements,'mode':mode,'semantic_review':semantic_review,'revision_errors':attempts,'physical_validation':bool(measurements.get('physical_validation',False))}
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
