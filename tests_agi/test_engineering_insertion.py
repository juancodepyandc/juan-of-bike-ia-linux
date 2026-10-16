import numpy as np
import pytest
import trimesh

from application.engineering_insertion import evaluate_insertion, verify_translation


def assembly(root, geometries):
    parts=[]
    for name,mesh,position in geometries:
        mesh.export(root/(name+'.stl'))
        parts.append({'id':name,'file':name+'.stl','assembly_matrix_mm':trimesh.transformations.translation_matrix(position).tolist()})
    return {'units':'mm','parts':parts}


def test_continuous_sweep_detects_thin_obstacle_between_clear_endpoints(tmp_path):
    report=assembly(tmp_path,[('moving',trimesh.creation.box([1,1,1]),[0,0,0]),
                              ('wall',trimesh.creation.box([.01,2,2]),[3,0,0])])
    result=evaluate_insertion(report,tmp_path,'moving',[10,0,0])
    assert result['status']=='blocked' and not result['continuous_collision_validated']
    assert result['blocked_by'][0]['swept_envelope_intersection_mm3']==pytest.approx(.01,abs=1e-5)
    assert set(result['geometry_sha256'])=={'moving','wall'}
    # Another direction is actually clear; no project-category refusal.
    clear=evaluate_insertion(report,tmp_path,'moving',[0,10,0])
    assert clear['status']=='clear' and clear['continuous_collision_validated']
    assert not clear['physical_fit_validated']


def test_concave_envelope_overlap_is_inconclusive_not_false_collision(tmp_path):
    a=trimesh.creation.box([1,1,1]);a.apply_translation([0,2,0])
    b=a.copy();b.apply_translation([0,-4,0])
    report=assembly(tmp_path,[('moving',trimesh.util.concatenate([a,b]),[0,0,0]),
                              ('obstacle',trimesh.creation.box([1,1,1]),[4,0,0])])
    result=evaluate_insertion(report,tmp_path,'moving',[10,0,0])
    assert not result['moving_solid_convex']
    assert result['status']=='inconclusive' and result['uncertain_pairs']
    assert not result['blocked_by'] and not result['continuous_collision_validated']


def test_batches_cannot_approve_before_last_obstacle(tmp_path):
    torus=trimesh.creation.torus(major_radius=2,minor_radius=.25)
    report=assembly(tmp_path,[('moving',trimesh.creation.box([1,1,1]),[0,0,0]),
                              ('hole',torus,[0,0,3]),('wall',trimesh.creation.box([2,2,.01]),[0,0,7])])
    first=verify_translation(report,tmp_path,'moving',[0,0,10],batch_size=1)
    assert first['status']=='pending' and not first['continuous_collision_validated']
    second=verify_translation(report,tmp_path,'moving',[0,0,10],cursor=1,batch_size=1)
    assert second['status']=='blocked' and second['batch']['complete']
    assert first['batch']['fingerprint']==second['batch']['fingerprint']
    assert evaluate_insertion(report,tmp_path,'moving',[0,0,10])['status']=='blocked'


def test_generated_directions_and_exit_length_come_from_actual_geometry(tmp_path):
    report=assembly(tmp_path,[('moving',trimesh.creation.box([2,2,2]),[0,0,0]),
                              ('other',trimesh.creation.box([2,2,2]),[20,0,0])])
    result=evaluate_insertion(report,tmp_path,'moving',direction_index=1)
    assert result['status']=='clear' and result['translation_mm'][0]<0
    assert 6<=result['direction_count']<=12
    with pytest.raises(ValueError):verify_translation(report,tmp_path,'moving',direction_index=999)
    with pytest.raises(ValueError):verify_translation(report,tmp_path,'moving',[float('nan'),0,0])
    report['parts'][0]['assembly_matrix_mm'][0][0]=2
    with pytest.raises(ValueError,match='Rigid'):verify_translation(report,tmp_path,'moving',[1,0,0])


def test_part_reference_cannot_escape_and_missing_geometry_is_not_substituted(tmp_path):
    report=assembly(tmp_path,[('moving',trimesh.creation.box([1,1,1]),[0,0,0])])
    report['parts'][0]['file']='../outside.stl'
    with pytest.raises(ValueError,match='escapes'):verify_translation(report,tmp_path,'moving',[1,0,0])


def test_cli_compares_actual_paths_and_writes_reusable_proof(tmp_path):
    import json,subprocess,sys
    from pathlib import Path
    report=assembly(tmp_path,[('moving',trimesh.creation.box([1,1,1]),[0,0,0]),
                              ('wall',trimesh.creation.box([.01,2,2]),[3,0,0])])
    manifest=tmp_path/'project.json';manifest.write_text(json.dumps(report))
    output=tmp_path/'insertion-proof.json'
    script=Path(__file__).resolve().parents[1]/'application/python-services/engineering_insertion_path.py'
    completed=subprocess.run([sys.executable,str(script),'--manifest',str(manifest),'--part','moving','--output',str(output)],capture_output=True,text=True,timeout=30)
    assert completed.returncode==0,completed.stderr
    proof=json.loads(output.read_text())
    assert proof['selected']['continuous_collision_validated']
    assert any(c['status']=='blocked' for c in proof['candidates'])
    clear=[c for c in proof['candidates'] if c['status']=='clear']
    assert np.linalg.norm(proof['selected']['translation_mm'])==min(np.linalg.norm(c['translation_mm']) for c in clear)


def test_degenerate_surface_faces_cannot_propose_a_zero_length_insertion():
    from application.engineering_insertion import insertion_directions
    mesh=trimesh.creation.box();mesh.vertices[0]=mesh.vertices[1]
    assert np.any(mesh.area_faces==0)
    assert all(np.isclose(np.linalg.norm(direction),1.) for direction in insertion_directions(mesh))


def test_large_world_coordinates_do_not_erase_a_thin_collision(tmp_path):
    report=assembly(tmp_path,[('moving',trimesh.creation.box([1,1,1]),[0,0,0]),
                              ('wall',trimesh.creation.box([.01,2,2]),[3,0,0])])
    local=evaluate_insertion(report,tmp_path,'moving',[10,0,0])
    for part in report['parts']:
        for axis in range(3):part['assembly_matrix_mm'][axis][3]+=400_000_000
    distant=evaluate_insertion(report,tmp_path,'moving',[10,0,0])
    assert local['status']==distant['status']=='blocked'
    assert distant['blocked_by'][0]['swept_envelope_intersection_mm3']==pytest.approx(local['blocked_by'][0]['swept_envelope_intersection_mm3'],abs=1e-8)
    assert distant['verification_precision']=='float64'
    assert distant['verification_origin_mm']==[400_000_000]*3


def test_find_clear_insertion_explores_diagonal_candidates(tmp_path):
    from application.engineering_insertion import find_clear_insertion
    # Block +X and -X, leave other directions clear
    report=assembly(tmp_path,[('moving',trimesh.creation.box([1,1,1]),[0,0,0]),
                              ('wall_pos_x',trimesh.creation.box([.1,4,4]),[3,0,0]),
                              ('wall_neg_x',trimesh.creation.box([.1,4,4]),[-3,0,0])])
    summary=find_clear_insertion(report,tmp_path,'moving')
    assert summary['direction_count']==12
    assert summary['clear_count']>=4
    assert summary['selected']['status']=='clear'
    assert summary['selected']['continuous_collision_validated'] is True

