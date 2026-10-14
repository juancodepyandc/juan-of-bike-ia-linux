import importlib.util
from pathlib import Path
import trimesh


def test_delivered_model_contains_meshes_not_reference_or_preview_photos(tmp_path,monkeypatch):
    services=Path(__file__).resolve().parents[1]/'application/python-services'
    monkeypatch.syspath_prepend(str(services))
    spec=importlib.util.spec_from_file_location('delivery_layout',services/'livraison_organisee.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    root=tmp_path/'run';work=root/'work';work.mkdir(parents=True)
    mesh=work/'run_mesh.glb';trimesh.creation.icosphere(subdivisions=1).export(mesh)
    reference=work/'run_reference.png';reference.write_bytes(b'reference fixture')
    (root/'run_GEOMETRIE.png').write_bytes(b'preview fixture')
    result=module.organiser(root,'run',final_mesh=str(mesh),front_reference=str(reference))
    assert result['ok'],result
    assert (root/'reference/face.png').exists()
    assert (root/'apercus/GEOMETRIE.png').exists()
    assert (root/'modele/modele_couleurs.glb').exists()
    assert (root/'modele/modele_geometrie.glb').exists()
    assert not list((root/'modele').glob('*.png'))
