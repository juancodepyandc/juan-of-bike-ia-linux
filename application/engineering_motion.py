"""Constrained forward kinematics and measured solid penetration, in millimetres."""
from pathlib import Path
import math
import numpy as np
import trimesh


def validate_joints(parts, joints):
    if not isinstance(joints,list) or len(joints)>64:raise ValueError('At most 64 mechanism joints required.')
    ids={p['id'] for p in parts};children=set();names=set();result=[]
    for j in joints:
        if not isinstance(j,dict):raise ValueError('Joint object required.')
        name=j.get('id');parent=j.get('parent');child=j.get('child');kind=j.get('kind')
        if not isinstance(name,str) or not name or name in names or parent not in ids or child not in ids or parent==child or child in children:raise ValueError('Unique joints, known parts and one parent per child required.')
        if kind not in {'fixed','revolute','prismatic','helical'}:raise ValueError('Unsupported joint; closed loops and free bodies need a separate solver.')
        names.add(name);children.add(child)
        axis=np.asarray(j.get('axis',[0,0,1]),dtype=float);origin=np.asarray(j.get('origin_mm',[0,0,0]),dtype=float)
        if axis.shape!=(3,) or origin.shape!=(3,) or not np.isfinite(axis).all() or not np.isfinite(origin).all() or np.linalg.norm(axis)<1e-8:raise ValueError('Finite origin and nonzero joint axis required.')
        limits=np.asarray(j.get('limits',[0,0] if kind=='fixed' else []),dtype=float);home=float(j.get('home',0))
        if limits.shape!=(2,) or not np.isfinite(limits).all() or limits[0]>limits[1] or not math.isfinite(home) or not limits[0]<=home<=limits[1]:raise ValueError('Finite joint limits containing home required.')
        pitch=float(j.get('pitch_mm',0))
        if not math.isfinite(pitch) or kind=='helical' and pitch==0:raise ValueError('Helical joints require a nonzero finite pitch.')
        result.append({**j,'axis':(axis/np.linalg.norm(axis)).tolist(),'origin_mm':origin.tolist(),'limits':limits.tolist(),'home':home,'pitch_mm':pitch,'unit':'mm' if kind=='prismatic' else 'deg','dof':0 if kind=='fixed' else 1})
    parents={j['child']:j['parent'] for j in result}
    for child in parents:
        visited=set();node=child
        while node in parents:
            if node in visited:raise ValueError('Closed kinematic loops require a dedicated constraint solver.')
            visited.add(node);node=parents[node]
    return result


def poses(parts,joints,values=None):
    joints=validate_joints(parts,joints);values=values or {}
    if not isinstance(values,dict) or set(values)-{j['id'] for j in joints}:raise ValueError('Unknown joint control.')
    rest={p['id']:np.asarray(p['assembly_matrix_mm'],dtype=float) for p in parts};current={};bychild={j['child']:j for j in joints}
    def resolve(node):
        if node in current:return current[node]
        j=bychild.get(node)
        if not j:current[node]=rest[node];return current[node]
        q=float(values.get(j['id'],j['home']))
        if not math.isfinite(q) or not j['limits'][0]<=q<=j['limits'][1] or j['kind']=='fixed' and q!=j['home']:raise ValueError('Joint value outside its allowed travel.')
        parent=j['parent'];delta=q-j['home'];motion=np.eye(4)
        if j['kind'] in {'revolute','helical'}:motion=trimesh.transformations.rotation_matrix(math.radians(delta),j['axis'],j['origin_mm'])
        if j['kind'] in {'prismatic','helical'}:motion[:3,3]+=np.asarray(j['axis'])*(delta if j['kind']=='prismatic' else delta*j['pitch_mm']/360)
        current[node]=resolve(parent)@np.linalg.inv(rest[parent])@motion@rest[node]
        return current[node]
    for node in rest:resolve(node)
    return current


def simulate(report,root,values=None):
    parts=report['parts'];joints=report.get('mechanism_joints',[]);transforms=poses(parts,joints,values);meshes={};root=Path(root).resolve()
    total_faces=0
    for p in parts:
        path=(root/p['file']).resolve()
        if not path.is_relative_to(root):raise ValueError('Part path outside project.')
        mesh=trimesh.load_mesh(path);total_faces+=len(mesh.faces)
        if total_faces>300000:raise ValueError('Simulation interactive limitée à 300 000 faces ; fournir une géométrie de collision simplifiée et documentée.')
        mesh.apply_transform(transforms[p['id']]);meshes[p['id']]=mesh
    collisions=[];uncertain=[];keys=list(meshes);checked=0
    for i,a in enumerate(keys):
        for b in keys[i+1:]:
            ma,mb=meshes[a],meshes[b]
            if np.any(np.minimum(ma.bounds[1],mb.bounds[1])-np.maximum(ma.bounds[0],mb.bounds[0])<=0):continue
            if checked>=128:
                uncertain.append([a,b]);continue
            checked+=1
            try:
                overlap=trimesh.boolean.intersection([ma,mb],engine='manifold');volume=float(overlap.volume)
                if not math.isfinite(volume):raise ValueError('Nonfinite intersection')
                if volume>1e-5:collisions.append({'parts':[a,b],'penetration_mm3':volume})
            except Exception:uncertain.append([a,b])
    return {'transforms_mm':{k:v.tolist() for k,v in transforms.items()},'collisions':collisions,'uncertain_pairs':uncertain,'dof':sum(j['dof'] for j in validate_joints(parts,joints)),'scope':'Current pose only; no continuous collision, forces, friction, cable flex or deformation validation.','collision_status':'uncertain' if uncertain else 'penetration' if collisions else 'no_penetration_at_this_pose'}
