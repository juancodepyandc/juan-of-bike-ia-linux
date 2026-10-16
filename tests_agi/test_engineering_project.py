import json
import zipfile
import numpy as np
import pytest
import trimesh
from application.engineering_project import build_project

def spec():return {'units':'mm','title':'Objet fonctionnel de test','objective':'Maintenir deux volumes séparés par une distance imposée.','bed_mm':[100,100,100],'parts':[{'id':'base','name':'Socle','file':'base.stl'},{'id':'support','file':'support.stl','assembly_matrix_mm':[[1,0,0,30],[0,1,0,0],[0,0,1,0],[0,0,0,1]]}],'bom':[{'name':'Matière PLA','quantity':1,'specification':'Filament 1,75 mm ; prototype sans charge certifiée','part_ids':['base','support']}],'assembly_steps':[{'instruction':'Positionner le support selon le placement rigide du fichier.','part_ids':['base','support']}],'assumptions':['Usage de prototype'],'blockers':[]}

def files(root):
    trimesh.creation.box([20,20,10]).export(root/'base.stl')
    trimesh.creation.cylinder(radius=5,height=20).export(root/'support.stl')

def test_generic_actual_parts_report_docs_figure_and_normalized_printable_zip(tmp_path):
    files(tmp_path);before=(tmp_path/'base.stl').read_bytes();result=build_project(spec(),tmp_path)
    assert result['measured_checks']['printer_fit'] and not result['physical_fit_validated']
    assert (tmp_path/'base.stl').read_bytes()==before
    for part in result['parts']:
        mesh=trimesh.load_mesh(tmp_path/part['file']);assert mesh.is_volume
        assert mesh.bounds[0]==pytest.approx([0,0,0],abs=1e-5)
        assert part['surface_area_mm2']>0 and part['estimated_mass_g']>0
        assert len(part['center_of_mass_mm'])==3 and len(part['explosion_vector_3d_mm'])==3
    assert result['assembly_precision']['total_estimated_mass_g']>0
    assert len(result['assembly_precision']['center_of_mass_mm'])==3
    assert result['assembly_precision']['interface_clearances']
    text=(tmp_path/'DOSSIER.md').read_text();assert '1,75 mm' in text and 'Socle' in text and 'Métrologie et précision d’assemblage' in text
    assert result['parts'][0]['color_rgba']!=result['parts'][1]['color_rgba']
    assert result['print_plates'] and len(result['print_plates'][0]['parts'])==2
    assert trimesh.load_mesh(tmp_path/result['print_plates'][0]['file']).is_volume
    assert '<polygon' in (tmp_path/'representation.svg').read_text()
    with zipfile.ZipFile(tmp_path/'engineering-project.zip') as z:
        assert z.testzip() is None and {'DOSSIER.md','DOSSIER.html','project.json','representation.svg','viewer.html','printable/piece_01.stl'}<=set(z.namelist())
    loaded=trimesh.load_scene(tmp_path/'assembled.glb')
    exploded=trimesh.load_scene(tmp_path/'exploded.glb')
    bounds=sorted([mesh.bounds for mesh in exploded.geometry.values()],key=lambda b:b[0,0])
    assert bounds[1][0,0]-bounds[0][1,0]>=.0099
    assert loaded.to_mesh().extents[0]==pytest.approx(.045,abs=1e-6)

@pytest.mark.parametrize('change,match',[({'units':'cm'},'units'),({'bom':[{'name':'Vis','quantity':1,'specification':''}]},'specification'),({'parts':[{'id':'bad','file':'../outside.stl'}]},'inside'),({'assembly_steps':[{'instruction':'Monter','part_ids':['unknown']}]},'existing')])
def test_invalid_or_unfounded_deliveries_refused(tmp_path,change,match):
    files(tmp_path)
    with pytest.raises(ValueError,match=match):build_project({**spec(),**change},tmp_path)

def test_infeasibility_produces_dossier_without_fake_parts(tmp_path):
    report=build_project({'units':'mm','title':'Étude','objective':'Objectif nécessitant une source d’énergie absente','parts':[],'bom':[],'assembly_steps':[],'blockers':['Aucune source d’énergie disponible.']},tmp_path)
    assert report['feasibility']=='requires_resolution'
    assert not (tmp_path/'assembled.glb').exists() and (tmp_path/'DOSSIER.md').is_file()


def test_physical_color_plan_separate_from_visual_part_colors(tmp_path):
    files(tmp_path);plan=spec()
    plan['parts'][0].update(filament='PLA rouge',filament_color='#ff0000')
    plan['parts'][1].update(filament='PLA bleu',filament_color='#0000ff')
    report=build_project(plan,tmp_path)
    assert len(report['print_plates'])==2
    assert {p['filament']['color'] for p in report['print_plates']}=={'#ff0000','#0000ff'}


def test_project_json_file_input_and_scope_guard(tmp_path):
    files(tmp_path);(tmp_path/'input.json').write_text(json.dumps(spec()))
    assert build_project('input.json',tmp_path)['parts']
    with pytest.raises(ValueError,match='inside'):
        build_project('../outside.json',tmp_path)


def test_normalized_cad_color_and_required_reproducible_sources(tmp_path):
    files(tmp_path);plan=spec();plan['parts'][0]['color_rgba']=[.8,.2,.2,1.]
    with pytest.raises(ValueError,match='design.py'):
        build_project(plan,tmp_path,require_sources=True)
    (tmp_path/'design.py').write_text('import trimesh\n')
    (tmp_path/'tests.py').write_text('assert True\n')
    assert build_project(plan,tmp_path,require_sources=True)['parts'][0]['color_rgba']==[204,51,51,255]


def test_purchased_component_envelope_is_not_printed_or_forced_into_bed(tmp_path):
    import trimesh
    from application.engineering_project import build_project
    trimesh.creation.box([20,20,10]).export(tmp_path/'bracket.stl')
    trimesh.creation.box([500,20,20]).export(tmp_path/'component.stl')
    spec={'units':'mm','title':'Component integration','objective':'Test physical roles','parts':[{'id':'bracket','file':'bracket.stl'},{'id':'component','file':'component.stl','manufacturing':'purchased','geometry_basis':'assumed_envelope','source_reference':'QA fixture; dimensions must be confirmed'}],'bom':[{'name':'Component','quantity':1,'specification':'QA envelope 500 × 20 × 20 mm, not a fabrication model','part_ids':['component']}]}
    report=build_project(spec,tmp_path)
    assert report['parts'][1]['file'].startswith('components/')
    assert len(report['filament_plan'])==1
    assert all(p['id']!='piece_02' for plate in report['print_plates'] for p in plate['parts'])
    assert 'exclu des plaques' in (tmp_path/'DOSSIER.md').read_text(encoding='utf-8')
