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
    assert [j['hole_diameter_mm'] for j in joints] == pytest.approx([5.4,4.4])
    assert np.linalg.norm(np.array(joints[0]['center_mm']) - joints[1]['center_mm']) > 9
    for pin in pins:
        assert pin.extents[actual_axis] == pytest.approx(15.6)
        for piece in pieces:
            overlap = trimesh.boolean.intersection([piece, pin], engine='manifold')
            assert overlap.is_empty or overlap.volume < 1e-4
    # Independently integrate the cylindrical bore and two conical lead-ins.
    n=48
    def socket_volume(r):
        lead=.2
        cylindrical=2*8*r*r
        conical_extra=2*lead*((r*r+r*(r+lead)+(r+lead)**2)/3-r*r)
        return (cylindrical+conical_extra)*n*np.sin(2*np.pi/n)/2
    assert sum(p.volume for p in pieces) == pytest.approx(mesh.volume-socket_volume(2.7)-socket_volume(2.2),abs=.02)



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


def test_ranked_pair_is_widely_separated_and_prescribed_pair_is_verified():
    parts,pins,joints,*_=build_assembly(box(),settings(config()))
    assert joints[0]['baseline_mm'] > 55
    assert joints[0]['placement']=='maximum_verified_baseline'
    pair=[[60,20,15],[60,40,25]]
    _,_,manual,*_=build_assembly(box(),settings(config(connector_centers_mm=[pair])))
    assert [j['center_mm'] for j in manual]==pair
    assert all(j['placement']=='prescribed_verified' for j in manual)
    for bad in [[[60,1,1],[60,40,25]],[[59,20,15],[60,40,25]],[[60,20,15],[60,21,15]]]:
        with pytest.raises(ValueError):
            build_assembly(box(),settings(config(connector_centers_mm=[bad])))
    with pytest.raises(ValueError,match='chaque jonction'):
        build_assembly(box(),settings(config(cuts_mm=[],connector_centers_mm=[pair],
                                           profile={**config()['profile'],'bed_mm':[150]*3})))


def test_protected_functional_zone_moves_automatic_positions_and_rejects_manual():
    zone=[[[49,0,0],[71,15,15]]]
    _,_,joints,*_=build_assembly(box(),settings(config(protected_zones_mm=zone)))
    assert all(not (j['center_mm'][1]<15 and j['center_mm'][2]<15) for j in joints)
    assert all(j['protected_zones_checked']==1 for j in joints)
    with pytest.raises(ValueError,match='zone protégée'):
        build_assembly(box(),settings(config(protected_zones_mm=zone,
            connector_centers_mm=[[[60,6,6],[60,45,25]]])))
    with pytest.raises(ValueError,match='zone protégée'):
        build_assembly(box(),settings(config(protected_zones_mm=[[[40,0,0],[80,60,40]]])))


def branched_mesh():
    # Fork: one connected left trunk, two detached right arms after the cut.
    trunk=trimesh.creation.box([40,80,30]);trunk.apply_translation([20,40,15])
    lower=trimesh.creation.box([100,30,30]);lower.apply_translation([70,15,15])
    upper=lower.copy();upper.apply_translation([0,50,0])
    return trimesh.boolean.union([trunk,lower,upper],engine='manifold')


def test_every_branch_receives_its_own_verified_connector_pair(tmp_path):
    c=config();c['profile']['bed_mm']=[100]*3
    mesh=branched_mesh()
    parts,pins,joints,*_=build_assembly(mesh,settings(c))
    assert len(parts)==3 and len(pins)==4
    assert {tuple(j['pieces']) for j in joints}=={(1,2),(1,3)}
    assert all(len([j for j in joints if i in j['pieces']])>=2 for i in [1,2,3])
    assert all(part.is_volume for part in parts)
    for pin in pins:
        for part in parts:
            hit=trimesh.boolean.intersection([part,pin],engine='manifold')
            assert hit.is_empty or hit.volume<1e-4
    mesh.export(tmp_path/'fork.stl');report=export_package(tmp_path/'fork.stl',tmp_path/'fork',c)
    assert report['piece_count']==3
    # Print-to-assembly transforms reproduce the real pin centroids and axes.
    for part in report['parts']:
        loaded=trimesh.load_mesh(tmp_path/'fork'/part['file'])
        loaded.apply_transform(part['print_to_assembly_matrix_mm'])
        if part['id'].startswith('pin'):
            joint=next(j for j in report['joints'] if j['id']==part['joint'])
            assert loaded.centroid==pytest.approx(joint['center_mm'],abs=1e-5)


def test_textured_boolean_preserves_uv_seams_materials_and_neutral_caps(tmp_path):
    from PIL import Image
    mesh=box()
    # Duplicate every triangle's corners: glTF UV seams are not open geometry.
    original=mesh.triangles.reshape((-1,3))
    faces=np.arange(len(original)).reshape((-1,3))
    uv=original[:,1:]/[60,40]
    mesh=trimesh.Trimesh(original,faces,process=False)
    mesh.visual=trimesh.visual.texture.TextureVisuals(uv=uv,image=Image.new('RGB',(4,4),'red'))
    source=tmp_path/'uv-seams.glb';mesh.export(source);before=source.read_bytes()
    report=export_package(source,tmp_path/'assembly',config())
    assert report['textured_assembly_available'] and source.read_bytes()==before
    loaded=trimesh.load_scene(tmp_path/'assembly/assembled_textured.glb')
    textured=[g for g in loaded.geometry.values() if g.visual.kind=='texture']
    neutral=[g for n,g in loaded.geometry.items() if n.startswith('piece') and g.visual.kind!='texture']
    assert len(textured)==2 and neutral
    for g in textured:
        assert g.visual.material.baseColorTexture.getpixel((0,0))[:3]==(255,0,0)
        # Original linear UV field remains correct at newly interpolated vertices.
        assert g.visual.uv==pytest.approx(g.vertices[:,1:]*1000/[60,40],abs=1e-5)
    assert loaded.to_mesh().extents==pytest.approx([.12,.06,.04],abs=1e-5)
    exploded=trimesh.load_scene(tmp_path/'assembly/exploded_textured.glb')
    assert exploded.to_mesh().extents[0]>.12
    with zipfile.ZipFile((tmp_path/'assembly').with_suffix('.zip')) as archive:
        assert {'viewer.html','viewer_assets/build/three.core.min.js','viewer_assets/addons/loaders/GLTFLoader.js'}<=set(archive.namelist())


@pytest.mark.parametrize('rules', [
    {'protected_zones_mm':[[[0,0,0],[0,1,1]]]},
    {'connector_centers_mm':[[[60,20,15]]]},
    {'protected_zones_mm':[[[0,0,float('nan')],[1,1,1]]]},
])
def test_invalid_constraints_never_enter_geometry_engine(rules):
    with pytest.raises(ValueError):settings(config(**rules))


def test_keyed_pair_cannot_be_swapped_and_chamfers_have_declared_dimensions():
    parts,pins,joints,*_=build_assembly(box(),settings(config()))
    assert [j['pin_diameter_mm'] for j in joints]==[5,4]
    assert all(j['keyed_pair'] and j['lead_in_mm']==.2 for j in joints)
    swapped=pins[0].copy();swapped.apply_translation(np.array(joints[1]['center_mm'])-joints[0]['center_mm'])
    # Independent boolean check: the large pin collides with the small socket.
    overlap=trimesh.boolean.intersection([parts[0],swapped],engine='manifold')
    assert overlap.volume>1
    c=config();c['profile'].update(keyed_pins=False,lead_in_mm=0)
    _,pins,joints,*_=build_assembly(box(),settings(c))
    assert [j['pin_diameter_mm'] for j in joints]==[5,5]
    assert all(not j['keyed_pair'] and j['lead_in_mm']==0 for j in joints)
    for changes in [dict(keyed_pins='yes'),dict(lead_in_mm=3),dict(lead_in_mm=2),dict(clearance_mm=.6)]:
        c=config();c['profile'].update(changes)
        with pytest.raises(ValueError):settings(c)
