"""Continuous conservative clearance of rigid straight assembly translations.

The convex hull of both endpoint meshes contains every intermediate translated
mesh. Disjointness proves clearance for this path, within numeric tolerance.
Intersection is a proven obstruction only for a convex moving solid; otherwise
it is inconclusive, not evidence of impossibility. No forces or fit are certified.
"""
from pathlib import Path
import hashlib
import json

import numpy as np
import trimesh

from agi_core.operation_receipts import sha256_file


def _meshes(report, root):
    root=Path(root).resolve();parts=report.get('parts')
    if report.get('units','mm')!='mm' or not isinstance(parts,list) or not parts:
        raise ValueError('Actual assembly parts in millimetres are required')
    meshes={};versions={};assumed=[]
    for part in parts:
        name=part['id']
        if not isinstance(name,str) or not name or name in meshes:raise ValueError('Unique part IDs are required')
        path=(root/part['file']).resolve()
        if not path.is_relative_to(root):raise ValueError('Part path escapes the project')
        before=path.stat();mesh=trimesh.load_mesh(path)
        digest=sha256_file(path);after=path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Geometry changed during verification')
        if not mesh.is_volume or not np.isfinite(mesh.vertices).all():raise ValueError('Closed finite solid geometry is required')
        matrix=np.asarray(part['assembly_matrix_mm'],dtype=float)
        if matrix.shape!=(4,4) or not np.isfinite(matrix).all() or not np.allclose(matrix[3],[0,0,0,1]) or not np.allclose(matrix[:3,:3].T@matrix[:3,:3],np.eye(3),atol=1e-6) or not np.isclose(np.linalg.det(matrix[:3,:3]),1):raise ValueError('Rigid assembly placement required')
        mesh.apply_transform(matrix);meshes[name]=mesh;versions[name]=digest
        if part.get('geometry_basis')=='assumed_envelope':assumed.append(name)
    return meshes,versions,assumed


def insertion_directions(mesh, limit=12):
    """Axes plus dominant surface normals, ranked deterministically by real area."""
    directions=[np.eye(3)[i]*sign for i in range(3) for sign in [1,-1]]
    # Cap candidate research; more directions or curved paths need a planner.
    indices=np.argsort(-mesh.area_faces,kind='stable')[:256]
    for index in indices:
        candidate=mesh.face_normals[index]
        for value in [candidate,-candidate]:
            if not any(np.dot(value,existing)>1-1e-5 for existing in directions):directions.append(value.copy())
            if len(directions)>=limit:return directions
    return directions


def verify_translation(report, root, part_id, translation_mm=None, *, direction_index=0, cursor=0, batch_size=32):
    if type(cursor)!=int or cursor<0 or type(batch_size)!=int or not 1<=batch_size<=128:raise ValueError('Invalid verification batch')
    meshes,versions,assumed=_meshes(report,root)
    if part_id not in meshes:raise ValueError('Unknown moving part')
    moving=meshes[part_id];obstacles={k:v for k,v in meshes.items() if k!=part_id}
    directions=insertion_directions(moving)
    if translation_mm is None:
        if type(direction_index)!=int or not 0<=direction_index<len(directions):raise ValueError('Direction outside candidate sequence')
        direction=directions[direction_index]
        end=max([float(np.max(mesh.vertices@direction)) for mesh in obstacles.values()]+[float(np.max(moving.vertices@direction))])
        distance=max(1.,end-float(np.min(moving.vertices@direction))+1.)
        translation=direction*distance
    else:
        translation=np.asarray(translation_mm,dtype=float)
        if translation.shape!=(3,) or not np.isfinite(translation).all() or not np.linalg.norm(translation)>0:raise ValueError('Finite nonzero translation in millimetres required')
    hull=trimesh.convex.convex_hull(np.vstack([moving.vertices,moving.vertices+translation]))
    candidates=[name for name,mesh in obstacles.items() if np.all(np.minimum(hull.bounds[1],mesh.bounds[1])-np.maximum(hull.bounds[0],mesh.bounds[0])>0)]
    if cursor>len(candidates):raise ValueError('Cursor outside candidate sequence')
    convex=bool(moving.is_convex);blocked=[];uncertain=[];tolerance=1e-5
    for name in candidates[cursor:cursor+batch_size]:
        try:
            intersection=trimesh.boolean.intersection([hull,obstacles[name]],engine='manifold')
            volume=float(intersection.volume) if len(intersection.faces) else 0.
            if not np.isfinite(volume):raise ValueError('Nonfinite swept intersection')
            if volume>tolerance:
                item={'part':name,'swept_envelope_intersection_mm3':volume}
                (blocked if convex else uncertain).append(item)
        except Exception as exc:
            uncertain.append({'part':name,'reason':type(exc).__name__})
    next_cursor=min(cursor+batch_size,len(candidates));complete=next_cursor==len(candidates)
    fingerprint=hashlib.sha256(json.dumps([versions,[(p['id'],p['assembly_matrix_mm']) for p in report['parts']],part_id,translation.tolist()],sort_keys=True,allow_nan=False).encode()).hexdigest()
    status='blocked' if blocked else 'inconclusive' if uncertain else 'clear' if complete and cursor==0 else 'pending'
    return {'part_id':part_id,'translation_mm':translation.tolist(),'direction_index':direction_index,'direction_count':len(directions),
            'geometry_sha256':versions,'assumed_envelopes':assumed,'moving_solid_convex':convex,
            'blocked_by':blocked,'uncertain_pairs':uncertain,'status':status,
            'continuous_collision_validated':status=='clear','physical_fit_validated':False,
            'penetration_tolerance_mm3':tolerance,
            'batch':{'cursor':cursor,'next_cursor':next_cursor,'candidate_pairs':len(candidates),'complete':complete,'fingerprint':fingerprint},
            'scope':'Ideal rigid straight translation against all supplied parts at rest. Convex swept envelope proves clearance only when disjoint within numeric tolerance. Nonconvex envelope overlap is inconclusive. No rotating path, clearance compensation, deformation, forces or assembly-order proof.'}


def evaluate_insertion(report, root, part_id, translation_mm=None, *, direction_index=0):
    """Aggregate every batch, bind fingerprints and never approve partial coverage."""
    cursor=0;fingerprint=None;blocked=[];uncertain=[]
    while True:
        result=verify_translation(report,root,part_id,translation_mm,direction_index=direction_index,cursor=cursor)
        current=result['batch']['fingerprint']
        if fingerprint is not None and fingerprint!=current:raise ValueError('Geometry changed between verification batches')
        fingerprint=current;blocked+=result['blocked_by'];uncertain+=result['uncertain_pairs']
        cursor=result['batch']['next_cursor']
        if result['batch']['complete']:break
    result.update(blocked_by=blocked,uncertain_pairs=uncertain,
                  status='blocked' if blocked else 'inconclusive' if uncertain else 'clear',
                  continuous_collision_validated=not blocked and not uncertain)
    return result
