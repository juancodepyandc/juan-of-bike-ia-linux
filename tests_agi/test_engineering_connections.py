import numpy as np
import trimesh
from application.engineering_connections import rank_fastening_locations


def test_hidden_location_ranked_by_real_occlusion_not_arbitrary_id(tmp_path):
    mesh=trimesh.creation.box([10,10,10]);mesh.export(tmp_path/'housing.stl')
    other=trimesh.creation.box([1,1,1]);other.apply_translation([20,0,0]);other.export(tmp_path/'part.stl')
    parts=[{'id':name,'file':name+'.stl','assembly_matrix_mm':np.eye(4).tolist()} for name in ['housing','part']]
    proposals=[{'id':'front','kind':'screw','part_ids':['housing','part'],'surface_samples_mm':[[0,0,5]]},{'id':'rear','kind':'glue','part_ids':['housing','part'],'surface_samples_mm':[[0,0,-5]]}]
    ranked=rank_fastening_locations(parts,tmp_path,proposals,[{'direction':[0,0,1]}])
    assert ranked[0]['id']=='rear' and ranked[0]['visible_sample_fraction']==0
    assert ranked[1]['visible_sample_fraction']==1
    assert all(not c['mechanical_strength_verified'] for c in ranked)


def test_collision_of_actual_tool_access_envelope(tmp_path):
    trimesh.creation.box([10,10,10]).export(tmp_path/'host.stl')
    trimesh.creation.box([2,2,2]).export(tmp_path/'tool.stl')
    part={'id':'host','file':'host.stl','assembly_matrix_mm':np.eye(4).tolist()}
    other={**part,'id':'other'}
    proposal={'id':'blocked','kind':'screw','part_ids':['host','other'],'surface_samples_mm':[[0,0,-5]],'tool_envelope_file':'tool.stl'}
    assert rank_fastening_locations([part,other],tmp_path,[proposal],[{'direction':[0,0,1]}])[0]['tool_clearance'] is False
