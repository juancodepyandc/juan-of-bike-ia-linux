"""Compare fastening proposals against actual geometry, never invent positions."""
from pathlib import Path
import math
import numpy as np
import trimesh


def _occluded(point,direction,triangles):
    # Vectorized Möller–Trumbore; independent of optional ray index dependencies.
    e1=triangles[:,1]-triangles[:,0];e2=triangles[:,2]-triangles[:,0]
    h=np.cross(np.broadcast_to(direction,e2.shape),e2);det=np.einsum('ij,ij->i',e1,h)
    valid=np.abs(det)>1e-9;inv=np.zeros_like(det);inv[valid]=1/det[valid]
    s=point-triangles[:,0];u=inv*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1)
    v=inv*(q@direction);distance=inv*np.einsum('ij,ij->i',e2,q)
    return bool(np.any(valid&(u>=-1e-8)&(v>=-1e-8)&(u+v<=1+1e-8)&(distance>1e-3)))


def rank_fastening_locations(parts,root,candidates,views):
    """Views point from a fastening surface toward the observer; weights are explicit."""
    if not isinstance(candidates,list) or len(candidates)>512 or not isinstance(views,list) or not views:raise ValueError('Candidate locations and intended viewing directions required.')
    root=Path(root).resolve();scene=[];ids=set()
    for part in parts:
        path=(root/part['file']).resolve()
        if not path.is_relative_to(root):raise ValueError('Geometry outside project.')
        mesh=trimesh.load_mesh(path);mesh.apply_transform(part['assembly_matrix_mm']);scene.append(mesh);ids.add(part['id'])
    triangles=np.concatenate([mesh.triangles for mesh in scene]) if scene else np.empty((0,3,3))
    normalized=[]
    for view in views:
        direction=np.asarray(view.get('direction'),dtype=float);weight=float(view.get('weight',1))
        if direction.shape!=(3,) or not np.isfinite(direction).all() or np.linalg.norm(direction)<1e-9 or not math.isfinite(weight) or weight<=0:raise ValueError('Finite view directions and positive weights required.')
        normalized.append((direction/np.linalg.norm(direction),weight))
    ranked=[]
    for candidate in candidates:
        if not isinstance(candidate,dict) or not isinstance(candidate.get('id'),str) or candidate.get('kind') not in {'screw','glue','clip','insert','interlock'}:raise ValueError('Named fastening candidate required.')
        if not isinstance(candidate.get('part_ids'),list) or len(candidate['part_ids'])<2 or any(p not in ids for p in candidate['part_ids']):raise ValueError('Connection must reference at least two real parts.')
        points=np.asarray(candidate.get('surface_samples_mm'),dtype=float)
        if points.ndim!=2 or points.shape[1]!=3 or not 1<=len(points)<=128 or not np.isfinite(points).all():raise ValueError('Actual proposed surface samples required.')
        visible=sum(weight*sum(not _occluded(p,direction,triangles) for p in points)/len(points) for direction,weight in normalized)/sum(weight for _,weight in normalized)
        clearance=None
        if candidate.get('tool_envelope_file'):
            path=(root/candidate['tool_envelope_file']).resolve()
            if not path.is_relative_to(root) or not path.is_file():raise ValueError('Tool access geometry must exist inside project.')
            envelope=trimesh.load_mesh(path)
            if not envelope.is_volume:raise ValueError('Closed tool access envelope required in assembly coordinates.')
            clearance=True
            for mesh in scene:
                if np.any(np.minimum(envelope.bounds[1],mesh.bounds[1])-np.maximum(envelope.bounds[0],mesh.bounds[0])<=0):continue
                try:
                    if trimesh.boolean.intersection([envelope,mesh],engine='manifold').volume>1e-5:clearance=False;break
                except Exception:clearance=None;break
        ranked.append({**candidate,'visible_sample_fraction':visible,'tool_clearance':clearance,'mechanical_strength_verified':False,'scope':'Visibility at supplied surface samples/views; tool access only when a measured envelope is supplied. Joint strength and fabrication tolerances require separate tests.'})
    return sorted(ranked,key=lambda item:(item['tool_clearance'] is False,item['visible_sample_fraction'],item['id']))
