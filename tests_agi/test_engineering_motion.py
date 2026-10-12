import numpy as np
import pytest
import trimesh
from application.engineering_motion import poses, simulate, validate_joints


def parts():
    a=np.eye(4);b=np.eye(4);b[0,3]=10
    return [{'id':'base','file':'base.stl','assembly_matrix_mm':a.tolist()},{'id':'arm','file':'arm.stl','assembly_matrix_mm':b.tolist()}]


def joint(kind='revolute', **kwargs):
    return {'id':'hinge','parent':'base','child':'arm','kind':kind,'axis':[0,0,1],'origin_mm':[0,0,0],'limits':[-180,180],'home':0,**kwargs}


def test_rotation_is_about_declared_world_axis():
    p=poses(parts(),[joint()],{'hinge':90})
    assert np.allclose(p['arm'][:3,3],[0,10,0],atol=1e-8)
    assert np.allclose(p['base'],np.eye(4))


def test_static_and_limits():
    assert np.allclose(poses(parts(),[])['arm'][:3,3],[10,0,0])
    with pytest.raises(ValueError):poses(parts(),[joint()],{'hinge':181})
    with pytest.raises(ValueError):poses(parts(),[joint()],{'invented':1})
    with pytest.raises(ValueError):poses(parts(),[joint('fixed',limits=[0,0])],{'hinge':1})


def test_cycles_rejected():
    with pytest.raises(ValueError):validate_joints(parts(),[joint(),joint(id='other',parent='arm',child='base')])


def test_helical_pitch_and_chain():
    pose=poses(parts(),[joint('helical',pitch_mm=2,limits=[0,360])],{'hinge':180})['arm']
    assert np.allclose(pose[:3,3],[-10,0,1],atol=1e-8)
    ps=parts()+[{'id':'tip','assembly_matrix_mm':trimesh.transformations.translation_matrix([20,0,0]).tolist()}]
    js=[joint(),joint(id='second',parent='arm',child='tip',origin_mm=[10,0,0])]
    assert np.allclose(poses(ps,js,{'hinge':90,'second':90})['tip'][:3,3],[-10,10,0])


def test_actual_solid_penetration(tmp_path):
    for name in ['base','arm']:trimesh.creation.box(extents=[2,2,2]).export(tmp_path/(name+'.stl'))
    report={'parts':parts(),'mechanism_joints':[joint('prismatic',axis=[1,0,0],limits=[-10,0])]}
    assert simulate(report,tmp_path)['collision_status']=='no_penetration_at_this_pose'
    collision=simulate(report,tmp_path,{'hinge':-10})
    assert collision['collision_status']=='penetration'
    assert collision['collisions'][0]['penetration_mm3']==pytest.approx(8)
    assert simulate(report,tmp_path,{'hinge':-8})['collisions']==[]  # touching faces ≠ penetration


def test_passive_closure_solved_from_measured_constraints():
    from application.engineering_motion import solve_closures
    js=[joint('prismatic',axis=[1,0,0],limits=[-10,0],passive=True)]
    closure=[{'kind':'coincident','parent':'base','child':'arm','parent_anchor_mm':[2,0,0],'child_anchor_mm':[0,0,0]}]
    transforms,values,proof=solve_closures(parts(),js,{},closure)
    assert proof['converged'] and values['hinge']==pytest.approx(-8,abs=1e-4)
    assert proof['local_dof']==0 and proof['local_constraint_rank_estimate']==1
    assert np.allclose(transforms['arm'][:3,3],[2,0,0],atol=1e-4)
    js[0]['limits']=[-2,0]
    _,_,proof=solve_closures(parts(),js,{},closure)
    assert not proof['converged'] and proof['max_residual_mm']>5


def test_collision_batches_resume_without_fabricating_a_clear_verdict(tmp_path):
    ps=[]
    for i in range(4):
        name='p'+str(i);trimesh.creation.box([2,2,2]).export(tmp_path/(name+'.stl'))
        ps.append({'id':name,'file':name+'.stl','assembly_matrix_mm':np.eye(4).tolist()})
    report={'parts':ps};a=simulate(report,tmp_path,batch_size=2)
    b=simulate(report,tmp_path,cursor=2,batch_size=2);c=simulate(report,tmp_path,cursor=4,batch_size=2)
    assert not a['collision_batch']['complete'] and c['collision_batch']['complete']
    assert a['collision_batch']['fingerprint']==b['collision_batch']['fingerprint']==c['collision_batch']['fingerprint']
    assert len(a['collisions']+b['collisions']+c['collisions'])==6


def test_sampled_path_exposes_intermediate_collision_without_canned_animation(tmp_path):
    from application.engineering_motion import path_sample
    for name in ['base','arm']:trimesh.creation.box([2,2,2]).export(tmp_path/(name+'.stl'))
    js=[joint('prismatic',axis=[1,0,0],limits=[-20,0])];report={'parts':parts(),'mechanism_joints':js}
    assert simulate(report,tmp_path,{'hinge':0})['collisions']==[]
    assert simulate(report,tmp_path,{'hinge':-20})['collisions']==[]
    values,metadata=path_sample(parts(),js,{}, {'hinge':-20},10)
    assert metadata['last_sample']==20 and not metadata['continuous_collision_validated']
    assert simulate(report,tmp_path,values)['collisions'][0]['penetration_mm3']==pytest.approx(8)


def test_motion_case_batches_cover_full_intended_travel(tmp_path):
    from application.engineering_motion import evaluate_motion_case
    for name in ['base','arm']:trimesh.creation.box([2,2,2]).export(tmp_path/(name+'.stl'))
    js=[joint('prismatic',axis=[1,0,0],limits=[-20,0])];report={'parts':parts(),'mechanism_joints':js}
    first=evaluate_motion_case(report,tmp_path,{}, {'hinge':-20},sample_batch=8)
    second=evaluate_motion_case(report,tmp_path,{}, {'hinge':-20},start_sample=first['next_sample'],sample_batch=8)
    third=evaluate_motion_case(report,tmp_path,{}, {'hinge':-20},start_sample=second['next_sample'],sample_batch=8)
    assert not first['complete'] and third['complete']
    assert [r['sample'] for b in [first,second,third] for r in b['samples']]==list(range(21))
    assert not second['batch_passed'] and any(r['collisions'] for r in second['samples'])


def test_arbitrary_compound_joint_uses_ordered_axes_without_dummy_parts():
    compound={'id':'socket','kind':'compound','parent':'base','child':'arm','coordinates':[
        {'id':'yaw','kind':'revolute','axis':[0,0,1],'origin_mm':[0,0,0],'limits':[-90,90],'home':0},
        {'id':'pitch','kind':'revolute','axis':[0,1,0],'origin_mm':[0,0,0],'limits':[-90,90],'home':0}]}
    actual=poses(parts(),[compound],{'socket:yaw':90,'socket:pitch':90})['arm']
    assert np.allclose(actual[:3,3],[0,0,-10],atol=1e-8)
    normalized=validate_joints(parts(),[compound])
    assert normalized[0]['dof']==2 and validate_joints(parts(),normalized)==normalized
    assert np.allclose(poses(parts(),normalized,{'socket:yaw':90,'socket:pitch':90})['arm'],actual)
    with pytest.raises(ValueError):poses(parts(),[compound],{'socket:pitch':100})
