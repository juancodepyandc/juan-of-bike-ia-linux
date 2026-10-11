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
    text=(tmp_path/'DOSSIER.md').read_text();assert '1,75 mm' in text and 'Socle' in text
    assert '<polygon' in (tmp_path/'representation.svg').read_text()
    with zipfile.ZipFile(tmp_path/'engineering-project.zip') as z:
        assert z.testzip() is None and {'DOSSIER.md','DOSSIER.html','project.json','representation.svg','viewer.html','printable/piece_01.stl'}<=set(z.namelist())
    loaded=trimesh.load_scene(tmp_path/'assembled.glb')
    assert loaded.to_mesh().extents[0]==pytest.approx(.045,abs=1e-6)

@pytest.mark.parametrize('change,match',[({'units':'cm'},'units'),({'bom':[{'name':'Vis','quantity':1,'specification':''}]},'specification'),({'parts':[{'id':'bad','file':'../outside.stl'}]},'inside'),({'assembly_steps':[{'instruction':'Monter','part_ids':['unknown']}]},'existing')])
def test_invalid_or_unfounded_deliveries_refused(tmp_path,change,match):
    files(tmp_path)
    with pytest.raises(ValueError,match=match):build_project({**spec(),**change},tmp_path)

def test_infeasibility_produces_dossier_without_fake_parts(tmp_path):
    report=build_project({'units':'mm','title':'Étude','objective':'Objectif nécessitant une source d’énergie absente','parts':[],'bom':[],'assembly_steps':[],'blockers':['Aucune source d’énergie disponible.']},tmp_path)
    assert report['feasibility']=='requires_resolution'
    assert not (tmp_path/'assembled.glb').exists() and (tmp_path/'DOSSIER.md').is_file()
