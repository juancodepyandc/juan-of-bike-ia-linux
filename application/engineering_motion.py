"""Constrained forward kinematics and measured solid penetration, in millimetres."""
from pathlib import Path
import math
import hashlib
import json
import os
from functools import lru_cache
import numpy as np
import trimesh


def validate_joints(parts, joints):
    if not isinstance(joints,list) or len(joints)>int(os.environ.get('AURORA_ENGINEERING_MAX_PARTS','512')):raise ValueError('Mechanism exceeds configured capacity.')
    ids={p['id'] for p in parts};children=set();names=set();result=[]
    for j in joints:
        if not isinstance(j,dict):raise ValueError('Joint object required.')
        name=j.get('id');parent=j.get('parent');child=j.get('child');kind=j.get('kind')
        if not isinstance(name,str) or not name or name in names or parent not in ids or child not in ids or parent==child or child in children:raise ValueError('Unique joints, known parts and one parent per child required.')
        if kind not in {'fixed','revolute','prismatic','helical','compound'}:raise ValueError('Unsupported joint; closed loops and free bodies need a separate solver.')
        names.add(name);children.add(child)
        if kind=='compound':
            coords=j.get('coordinates')
            if not isinstance(coords,list) or not 1<=len(coords)<=6:raise ValueError('Compound joints require one to six declared coordinates.')
            controls=[];seen=set()
            for c in coords:
                if not isinstance(c,dict) or not isinstance(c.get('id'),str) or not c['id'] or c['id'] in seen or c.get('kind') not in {'revolute','prismatic','helical'} or 'axis' not in c:raise ValueError('Unique coordinate names, physical motion type and explicit axes required.')
                seen.add(c['id']);local_id=c.get('coordinate_id',c['id'])
                if not isinstance(local_id,str) or not local_id:raise ValueError('Invalid coordinate name.')
                controls.extend(validate_joints(parts,[{**c,'coordinate_id':local_id,'id':name+':'+local_id,'parent':parent,'child':child,'origin_mm':c.get('origin_mm',j.get('origin_mm',[0,0,0])),'passive':c.get('passive',j.get('passive',False))}]))
            result.append({**j,'coordinates':controls,'dof':sum(c['dof'] for c in controls)})
            continue
        axis=np.asarray(j.get('axis',[0,0,1]),dtype=float);origin=np.asarray(j.get('origin_mm',[0,0,0]),dtype=float)
        if axis.shape!=(3,) or origin.shape!=(3,) or not np.isfinite(axis).all() or not np.isfinite(origin).all() or np.linalg.norm(axis)<1e-8:raise ValueError('Finite origin and nonzero joint axis required.')
        limits=np.asarray(j.get('limits',[0,0] if kind=='fixed' else []),dtype=float);home=float(j.get('home',0))
        if limits.shape!=(2,) or not np.isfinite(limits).all() or limits[0]>limits[1] or not math.isfinite(home) or not limits[0]<=home<=limits[1]:raise ValueError('Finite joint limits containing home required.')
        pitch=float(j.get('pitch_mm',0))
        if not math.isfinite(pitch) or kind=='helical' and pitch==0:raise ValueError('Helical joints require a nonzero finite pitch.')
        result.append({**j,'axis':(axis/np.linalg.norm(axis)).tolist(),'origin_mm':origin.tolist(),'limits':limits.tolist(),'home':home,'pitch_mm':pitch,'unit':'mm' if kind=='prismatic' else 'deg','dof':0 if kind=='fixed' or limits[0]==limits[1] else 1})
    parents={j['child']:j['parent'] for j in result}
    for child in parents:
        visited=set();node=child
        while node in parents:
            if node in visited:raise ValueError('Closed kinematic loops require a dedicated constraint solver.')
            visited.add(node);node=parents[node]
    return result


def coordinates(joints):
    return [c for j in joints for c in (j['coordinates'] if j['kind']=='compound' else [j])]


def poses(parts,joints,values=None):
    joints=validate_joints(parts,joints);values=values or {}
    if not isinstance(values,dict) or set(values)-{j['id'] for j in coordinates(joints)}:raise ValueError('Unknown joint control.')
    rest={p['id']:np.asarray(p['assembly_matrix_mm'],dtype=float) for p in parts};current={};bychild={j['child']:j for j in joints}
    def resolve(node):
        if node in current:return current[node]
        j=bychild.get(node)
        if not j:current[node]=rest[node];return current[node]
        parent=j['parent'];motion=np.eye(4)
        for c in coordinates([j]):
            q=float(values.get(c['id'],c['home']))
            if not math.isfinite(q) or not c['limits'][0]<=q<=c['limits'][1] or c['kind']=='fixed' and q!=c['home']:raise ValueError('Joint value outside its allowed travel.')
            delta=q-c['home'];step=np.eye(4)
            if c['kind'] in {'revolute','helical'}:step=trimesh.transformations.rotation_matrix(math.radians(delta),c['axis'],c['origin_mm'])
            if c['kind'] in {'prismatic','helical'}:step[:3,3]+=np.asarray(c['axis'])*(delta if c['kind']=='prismatic' else delta*c['pitch_mm']/360)
            motion=motion@step
        current[node]=resolve(parent)@np.linalg.inv(rest[parent])@motion@rest[node]
        return current[node]
    for node in rest:resolve(node)
    return current


def solve_closures(parts,joints,values,constraints):
    """Numerical closure of a declared spanning tree; residuals remain explicit."""
    if not constraints:return poses(parts,joints,values),dict(values or {}),{'required':False,'converged':True,'max_residual_mm':0.0}
    ids={p['id'] for p in parts}
    if not isinstance(constraints,list) or len(constraints)>128:raise ValueError('Invalid closure constraints.')
    for c in constraints:
        if not isinstance(c,dict) or c.get('kind') not in {'coincident','distance'} or c.get('parent') not in ids or c.get('child') not in ids:raise ValueError('Closure requires known parts and coincident/distance anchors.')
        for key in ['parent_anchor_mm','child_anchor_mm']:
            anchor=np.asarray(c.get(key),dtype=float)
            if anchor.shape!=(3,) or not np.isfinite(anchor).all():raise ValueError('Finite closure anchors required in each printable part local frame.')
        if c['kind']=='distance' and (not math.isfinite(float(c.get('distance_mm',-1))) or float(c.get('distance_mm',-1))<0):raise ValueError('Finite nonnegative closure distance required.')
    joints=validate_joints(parts,joints);passive=[j for j in coordinates(joints) if j.get('passive') and j['dof']]
    commands=dict(values or {});q=np.array([float(commands.get(j['id'],j['home'])) for j in passive])
    limits=np.array([j['limits'] for j in passive]);q=np.clip(q,limits[:,0],limits[:,1]) if passive else q
    def evaluate(x):
        trial={**commands,**{j['id']:float(v) for j,v in zip(passive,x)}};transforms=poses(parts,joints,trial);residual=[]
        for c in constraints:
            a=trimesh.transformations.transform_points([c['parent_anchor_mm']],transforms[c['parent']])[0]
            b=trimesh.transformations.transform_points([c['child_anchor_mm']],transforms[c['child']])[0]
            residual.extend((a-b).tolist() if c['kind']=='coincident' else [float(np.linalg.norm(a-b))-float(c['distance_mm'])])
        return np.asarray(residual),transforms,trial
    iterations=0
    for iterations in range(80):
        residual,transforms,trial=evaluate(q)
        if np.max(np.abs(residual))<=1e-4 or not passive:break
        columns=[]
        for i,j in enumerate(passive):
            step=max(1e-5,(j['limits'][1]-j['limits'][0])*1e-6);shift=q.copy();shift[i]=min(q[i]+step,j['limits'][1])
            if shift[i]==q[i]:shift[i]=max(q[i]-step,j['limits'][0])
            columns.append((evaluate(shift)[0]-residual)/(shift[i]-q[i]) if shift[i]!=q[i] else np.zeros_like(residual))
        jacobian=np.array(columns).T
        update=np.linalg.lstsq(jacobian.T@jacobian+np.eye(len(q))*1e-6,-jacobian.T@residual,rcond=None)[0]
        changed=False
        for scale in [1,.5,.25,.125,.0625]:
            candidate=np.clip(q+scale*update,limits[:,0],limits[:,1])
            if np.linalg.norm(evaluate(candidate)[0])<np.linalg.norm(residual):q=candidate;changed=True;break
        if not changed:break
    residual,transforms,trial=evaluate(q);maximum=float(np.max(np.abs(residual)))
    free=[j for j in coordinates(joints) if j['dof']];rank=None
    if len(free)<=64:
        columns=[]
        def constraint_error(pose):
            values=[]
            for c in constraints:
                a=trimesh.transformations.transform_points([c['parent_anchor_mm']],pose[c['parent']])[0]
                b=trimesh.transformations.transform_points([c['child_anchor_mm']],pose[c['child']])[0]
                values.extend((a-b).tolist() if c['kind']=='coincident' else [float(np.linalg.norm(a-b))-float(c['distance_mm'])])
            return np.asarray(values)
        for j in free:
            value=float(trial.get(j['id'],j['home']));span=j['limits'][1]-j['limits'][0];step=max(1e-5,span*1e-6)
            low=max(j['limits'][0],value-step);high=min(j['limits'][1],value+step)
            r0=constraint_error(poses(parts,joints,{**trial,j['id']:low}));r1=constraint_error(poses(parts,joints,{**trial,j['id']:high}))
            columns.append((r1-r0)/(high-low)*span)
        matrix=np.asarray(columns).T
        if columns:
            singular=np.linalg.svd(matrix,compute_uv=False);rank=int(np.count_nonzero(singular>max(1e-8,float(singular.max())*1e-6)))
        else:rank=0
    return transforms,trial,{'required':True,'converged':maximum<=1e-4,'max_residual_mm':maximum,'iterations':iterations+1,'local_constraint_rank_estimate':rank,'local_dof':len(free)-rank if rank is not None else None,'scope':'Numerical local mobility of ideal declared joints; singularities, other branches and physical compliance are not certified.'}



@lru_cache(maxsize=1024)
def _bounds(path, size, modified):
    bounds=trimesh.load_mesh(path).bounds.copy()
    digest=hashlib.sha256()
    with open(path,'rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return bounds,digest.hexdigest()


def simulate(report,root,values=None,*,cursor=0,batch_size=None):
    """Bounded collision batches, resumable without substituting invented geometry."""
    parts=report['parts'];joints=report.get('mechanism_joints',[]);transforms,resolved,closure=solve_closures(parts,joints,values,report.get('closure_constraints',[]));root=Path(root).resolve()
    batch_size=batch_size or int(os.environ.get('AURORA_SIMULATION_PAIR_BATCH','128'))
    if type(cursor)!=int or cursor<0 or type(batch_size)!=int or not 1<=batch_size<=1024:raise ValueError('Invalid collision batch.')
    paths={};bounds={};versions=[]
    for p in parts:
        path=(root/p['file']).resolve()
        if not path.is_relative_to(root):raise ValueError('Part path outside project.')
        stat=path.stat();box,digest=_bounds(str(path),stat.st_size,stat.st_mtime_ns)
        versions.append([p['id'],digest]);low,high=box
        corners=np.array([[x,y,z] for x in [low[0],high[0]] for y in [low[1],high[1]] for z in [low[2],high[2]]])
        world=trimesh.transformations.transform_points(corners,transforms[p['id']])
        bounds[p['id']]=np.array([world.min(axis=0),world.max(axis=0)]);paths[p['id']]=path
    candidates=[];keys=list(paths)
    for i,a in enumerate(keys):
        for b in keys[i+1:]:
            ba,bb=bounds[a],bounds[b]
            if np.all(np.minimum(ba[1],bb[1])-np.maximum(ba[0],bb[0])>0):candidates.append([a,b])
    if cursor>len(candidates):raise ValueError('Cursor outside collision sequence.')
    collisions=[];uncertain=[]
    for a,b in candidates[cursor:cursor+batch_size]:
        try:
            ma=trimesh.load_mesh(paths[a]);mb=trimesh.load_mesh(paths[b])
            ma.apply_transform(transforms[a]);mb.apply_transform(transforms[b])
            overlap=trimesh.boolean.intersection([ma,mb],engine='manifold');volume=float(overlap.volume)
            if not math.isfinite(volume):raise ValueError('Nonfinite intersection')
            if volume>1e-5:collisions.append({'parts':[a,b],'penetration_mm3':volume})
        except Exception:uncertain.append([a,b])
    next_cursor=min(cursor+batch_size,len(candidates));complete=next_cursor==len(candidates)
    fingerprint=hashlib.sha256(json.dumps([versions,{k:v.tolist() for k,v in transforms.items()}],sort_keys=True).encode()).hexdigest()
    return {'assumed_envelopes':[p['id'] for p in parts if p.get('geometry_basis')=='assumed_envelope'],'geometry_sha256':dict(versions),'resolved_values':resolved,'closure':closure,'transforms_mm':{k:v.tolist() for k,v in transforms.items()},'collisions':collisions,'uncertain_pairs':uncertain,'declared_coordinates':sum(j['dof'] for j in validate_joints(parts,joints)),'dof':closure.get('local_dof',sum(j['dof'] for j in validate_joints(parts,joints))),'scope':'Sampled pose only; no continuous collision, forces, friction, cable flex or deformation validation.','collision_status':'kinematically_invalid' if not closure['converged'] else 'uncertain' if uncertain else 'penetration' if collisions else 'no_penetration_at_this_pose' if complete and cursor==0 else 'pending','collision_batch':{'cursor':cursor,'next_cursor':next_cursor,'candidate_pairs':len(candidates),'complete':complete,'fingerprint':fingerprint}}


def path_sample(parts,joints,start,target,index,*,angular_step_deg=5,linear_step_mm=1,seed=None):
    joints=validate_joints(parts,joints)
    poses(parts,joints,start);poses(parts,joints,target)
    if type(index)!=int or index<0 or not all(math.isfinite(float(v)) and float(v)>0 for v in [angular_step_deg,linear_step_mm]):raise ValueError('Invalid motion sampling parameters.')
    active=[j for j in coordinates(joints) if j['dof'] and not j.get('passive')]
    samples=max([1]+[math.ceil(abs(float(target.get(j['id'],j['home']))-float(start.get(j['id'],j['home'])))/(linear_step_mm if j['kind']=='prismatic' else angular_step_deg)) for j in active])
    if index>samples:raise ValueError('Sample outside planned motion.')
    values={j['id']:float(start.get(j['id'],j['home']))+(float(target.get(j['id'],j['home']))-float(start.get(j['id'],j['home'])))*index/samples for j in active}
    if seed is not None and not isinstance(seed,dict):raise ValueError('Invalid continuation values.')
    continuation=start if seed is None else seed
    values.update({j['id']:float(continuation.get(j['id'],start.get(j['id'],j['home']))) for j in coordinates(joints) if j.get('passive')})
    poses(parts,joints,values)  # Continuation must obey the same finite joint limits.
    return values,{'sample':index,'last_sample':samples,'angular_step_deg':angular_step_deg,'linear_step_mm':linear_step_mm,'continuous_collision_validated':False,'trajectory':'Linear interpolation of commanded coordinates; passive coordinates solved at each sample.'}


def evaluate_motion_case(report,root,start,target,*,start_sample=0,sample_batch=32,continuation_values=None):
    """Executable test of intended travel, with resumable coverage and real results."""
    if type(sample_batch)!=int or not 1<=sample_batch<=256:raise ValueError('Invalid sample batch.')
    results=[];last=start_sample;fingerprint=None;seed=continuation_values
    for index in range(start_sample,start_sample+sample_batch):
        values,coverage=path_sample(report['parts'],report.get('mechanism_joints',[]),start,target,index,seed=seed)
        collisions=[];uncertain=[];cursor=0;fingerprint=None
        while True:
            result=simulate(report,root,values,cursor=cursor)
            collisions.extend(result['collisions']);uncertain.extend(result['uncertain_pairs'])
            if fingerprint is not None and fingerprint!=result['collision_batch']['fingerprint']:raise ValueError('Geometry changed during verification.')
            fingerprint=result['collision_batch']['fingerprint'];cursor=result['collision_batch']['next_cursor']
            if result['collision_batch']['complete']:break
        seed=result['resolved_values']
        results.append({'sample':index,'values':result['resolved_values'],'closure':result['closure'],'collisions':collisions,'uncertain_pairs':uncertain,'geometry_pose_fingerprint':fingerprint,'geometry_sha256':result['geometry_sha256']})
        last=coverage['last_sample']
        if index==last:break
    complete=results[-1]['sample']==last
    return {'samples':results,'next_sample':results[-1]['sample']+1,'continuation_values':seed,'last_sample':last,'complete':complete,'batch_passed':all(r['closure']['converged'] and not r['collisions'] and not r['uncertain_pairs'] for r in results),'continuous_collision_validated':False,'scope':'Measured sampled geometry only; continue with returned values, combine every batch and verify coverage. Numerical branch continuation is not a physical or continuous-collision guarantee.'}
