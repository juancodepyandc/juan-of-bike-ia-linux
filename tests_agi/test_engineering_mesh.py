import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pytest
import trimesh

from application.engineering_mesh import build_assembly, export_package, settings


def config(**changes):
    return {'mode': 'assembly', 'size_mm': 120, 'axis': 'x', 'cuts_mm': [60],
            'profile': {'name': 'Fixture printer', 'process': 'FDM', 'bed_mm': [80, 80, 80],
                        'margin_mm': 2, 'clearance_mm': 0.2, 'wall_mm': 2,
                        'pin_diameter_mm': 5, 'pin_depth_mm': 8}, **changes}


def box():
    mesh = trimesh.creation.box([120, 60, 40]); mesh.apply_translation(-mesh.bounds[0]); return mesh


@pytest.mark.parametrize('axis', ['x', 'y', 'z'])
def test_real_closed_cut_and_paired_holes_without_pin_interference(axis):
    mesh = trimesh.creation.box([120, 120, 120]); mesh.apply_translation(-mesh.bounds[0])
    c = config(axis=axis); c['profile']['bed_mm'] = [140, 140, 140]
    pieces, pins, joints, actual_axis, cuts = build_assembly(mesh, settings(c))
    assert cuts == [60] and actual_axis == 'xyz'.index(axis)
    assert len(pieces) == len(pins) == len(joints) == 2
    assert all(p.is_volume and len(p.split()) == 1 for p in pieces)
    assert all(j['hole_diameter_mm'] == pytest.approx(5.4) for j in joints)
    assert np.linalg.norm(np.array(joints[0]['center_mm']) - joints[1]['center_mm']) > 9
    for pin in pins:
        assert pin.extents[actual_axis] == pytest.approx(15.6)
        for piece in pieces:
            overlap = trimesh.boolean.intersection([piece, pin], engine='manifold')
            assert overlap.is_empty or overlap.volume < 1e-4
    # Independently account for the removed polygonal cylindrical bore volume.
    hole = trimesh.creation.cylinder(radius=2.7, height=16, sections=48)
    assert sum(p.volume for p in pieces) == pytest.approx(mesh.volume - 2*hole.volume, abs=0.02)


def test_real_stl_export_profile_coordinates_volume_and_source_preserved(tmp_path):
    source = tmp_path/'box.stl'; box().export(source); before = source.read_bytes()
    output = tmp_path/'package'
    report = export_package(source, output, config())
    assert report['piece_count'] == 2 and report['pin_count'] == 2
    assert source.read_bytes() == before
    assert report['source_sha256'] == hashlib.sha256(before).hexdigest()
    for entry in report['parts']:
        mesh = trimesh.load_mesh(output/entry['file'])
        assert mesh.is_volume and mesh.bounds[0] == pytest.approx([0, 0, 0], abs=1e-5)
        assert mesh.extents == pytest.approx(entry['dimensions_mm'], abs=1e-5)
        assert np.all(mesh.extents <= np.array([76, 76, 76])+1e-5)
    with zipfile.ZipFile(output.with_suffix('.zip')) as z:
        assert z.testzip() is None
        assert {'piece_01.stl','piece_02.stl','pin_01.stl','pin_02.stl', 'assembled.glb','exploded.glb','assembly.json'} <= set(z.namelist())
        assert json.loads(z.read('assembly.json'))['profile']['name'] == 'Fixture printer'
    assembled = trimesh.load_scene(output/'assembled.glb')
    assert len(assembled.geometry) == 4
    assert len(trimesh.load_scene(output/'exploded.glb').geometry) == 4
    assert assembled.to_mesh().extents == pytest.approx([0.12,0.06,0.04], abs=1e-6)
    assert report['physical_fit_validated'] is False


def test_auto_cuts_and_no_unnecessary_cut(tmp_path):
    source=tmp_path/'source.stl';box().export(source)
    report=export_package(source,tmp_path/'auto',config(axis='auto', cuts_mm=[]))
    assert report['cuts_mm'] == [60] and report['piece_count'] == 2
    c=config(axis='auto',cuts_mm=[]);c['profile']['bed_mm']=[150]*3
    report=export_package(source,tmp_path/'single',c)
    assert report['cuts_mm'] == [] and report['piece_count'] == 1 and report['pin_count'] == 0


def test_multiple_cuts_do_not_connect_holes_across_middle_piece():
    c=config(cuts_mm=[40,80]);parts,pins,joints,*_=build_assembly(box(),settings(c))
    assert len(parts)==3 and len(pins)==4 and len(joints)==4
    assert all(p.is_volume for p in parts)
    c=config(cuts_mm=[50,65])
    with pytest.raises(ValueError,match='trop mince'):
        build_assembly(box(),settings(c))


@pytest.mark.parametrize('change,match', [({'cuts_mm':[60,60]},'distinctes'),({'cuts_mm':[140]},'intérieur'),
                                      ({'axis':'z','cuts_mm':[20]},'Plusieurs axes')])
def test_bad_cuts_refused(change,match):
    with pytest.raises(ValueError,match=match): build_assembly(box(),settings(config(**change)))


def test_open_mesh_and_thin_joint_are_refused():
    mesh=box();mesh.update_faces(np.arange(len(mesh.faces)-1))
    with pytest.raises(ValueError,match='volume fermé'):build_assembly(mesh,settings(config()))
    mesh=trimesh.creation.box([120,4,4]);mesh.apply_translation(-mesh.bounds[0])
    with pytest.raises(ValueError,match='deux raccords'):build_assembly(mesh,settings(config()))


def test_texture_original_bytes_and_geometry_separate(tmp_path):
    from PIL import Image
    mesh=box()
    mesh.visual=trimesh.visual.texture.TextureVisuals(uv=np.zeros((len(mesh.vertices),2)),image=Image.new('RGB',(4,4),'red'))
    source=tmp_path/'texture.glb';mesh.export(source);raw=source.read_bytes()
    report=export_package(source,tmp_path/'texture',config(mode='textured'))
    assert (tmp_path/'texture/textured_original.glb').read_bytes()==raw and not report['size_applied']
    export_package(source,tmp_path/'geo',config(mode='geometry'))
    loaded=trimesh.load_scene(tmp_path/'geo/geometry.glb')
    assert all(g.visual.kind!='texture' for g in loaded.geometry.values())


@pytest.mark.parametrize('value', [True, float('nan'),float('inf'),0,5000,'200'])
def test_invalid_scale_never_enters_engine(value):
    with pytest.raises(ValueError): settings(config(size_mm=value))
