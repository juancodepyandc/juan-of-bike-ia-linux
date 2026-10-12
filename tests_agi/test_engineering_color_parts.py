import numpy as np
import pytest
import trimesh
import subprocess,sys,zipfile
from application.engineering_color_parts import color_parts
from application.engineering_project import build_project

PALETTE=[{'name':'PLA rouge','color':'#ff0000'},{'name':'PLA bleu','color':'#0000ff'}]

def source(root):
    mesh=trimesh.creation.box([2,2,2]);colors=np.tile([255,0,0,255],(len(mesh.faces),1))
    colors[mesh.face_normals[:,2]>.9]=[0,0,255,255]
    # GLB stores vertex colors. Separate color-boundary vertices so export
    # does not average a blue face into its five neighboring red faces.
    mesh=trimesh.Trimesh(vertices=mesh.vertices[mesh.faces].reshape((-1,3)),faces=np.arange(len(mesh.faces)*3).reshape((-1,3)),process=False)
    mesh.visual.vertex_colors=np.repeat(colors,3,axis=0)
    path=root/'source.glb';mesh.export(path);return path

def test_closed_color_inlays_preserve_measured_surface_and_hidden_interfaces(tmp_path):
    original=source(tmp_path);before=original.read_bytes();folder=tmp_path/'manufacturing'
    result=color_parts(original,folder,palette=PALETTE,size_mm=40,shell_mm=3,profile={'bed_mm':[220,220,250],'color_capability':'single','wall_mm':.8})
    assert len(result['spec']['parts'])==2
    assert original.read_bytes()==before
    assert result['proof']['volume_residual_mm3']<.1
    assert not result['proof']['physical_fit_validated']
    meshes=[trimesh.load_mesh(folder/p['file']) for p in result['spec']['parts']]
    assert all(m.is_volume for m in meshes)
    intersection=trimesh.boolean.intersection(meshes,engine='manifold')
    assert intersection.is_empty or intersection.volume==pytest.approx(0,abs=1e-5)
    assert sum(m.volume for m in meshes)==pytest.approx(40**3,abs=.1)
    subprocess.run([sys.executable,'tests.py'],cwd=folder,check=True,capture_output=True)
    report=build_project(result['spec'],folder,require_sources=True)
    assert len(report['print_plates'])==2
    assert {p['filament_color'] for p in result['spec']['parts']}=={'#ff0000','#0000ff'}
    assert report['blockers'] and not report['physical_fit_validated']
    with zipfile.ZipFile(folder/'engineering-project.zip') as z:
        assert {'source.glb','color-input.json','color-proof.json','design.py','tests.py'}<=set(z.namelist())
    before_script=(folder/'design.py').read_bytes()
    subprocess.run([sys.executable,'design.py'],cwd=folder,check=True,capture_output=True)
    assert (folder/'design.py').read_bytes()==before_script

def test_color_partition_never_silently_rescales_to_fit_printer(tmp_path):
    original=source(tmp_path)
    with pytest.raises(ValueError,match='exceeds the printer bed'):
        color_parts(original,tmp_path/'large',palette=PALETTE,size_mm=300,shell_mm=3,profile={'bed_mm':[220,220,250],'wall_mm':.8})

def test_unmeasured_palette_color_and_thin_inlay_require_revision(tmp_path):
    original=source(tmp_path)
    with pytest.raises(ValueError,match='no measured surface'):
        color_parts(original,tmp_path/'unused',palette=PALETTE+[{'name':'Vert','color':'#00ff00'}],size_mm=40,shell_mm=3)
    with pytest.raises(ValueError,match='wall requirement'):
        color_parts(original,tmp_path/'thin',palette=PALETTE,size_mm=40,shell_mm=.05)

def test_curved_surface_partition_is_derived_from_real_faces(tmp_path):
    mesh=trimesh.creation.icosphere(subdivisions=3)
    colors=np.tile([255,0,0,255],(len(mesh.faces),1));colors[mesh.triangles_center[:,2]>.4]=[0,0,255,255]
    flat=trimesh.Trimesh(vertices=mesh.vertices[mesh.faces].reshape((-1,3)),faces=np.arange(len(mesh.faces)*3).reshape((-1,3)),process=False)
    flat.visual.vertex_colors=np.repeat(colors,3,axis=0);path=tmp_path/'curved.glb';flat.export(path)
    result=color_parts(path,tmp_path/'curved-parts',palette=PALETTE,size_mm=150,shell_mm=3,profile={'bed_mm':[220,220,250]})
    assert len(result['spec']['parts'])==2
    assert result['proof']['volume_residual_mm3']<result['proof']['source_volume_mm3']*1e-5
    assert result['proof']['color_regions'][0]['source_face_count']>100
