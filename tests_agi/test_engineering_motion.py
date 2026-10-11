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
