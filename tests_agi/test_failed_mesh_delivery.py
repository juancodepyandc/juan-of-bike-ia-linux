import importlib.util
from pathlib import Path
import ast
import numpy as np
import trimesh


def services(monkeypatch):
    root=Path(__file__).resolve().parents[1]/'application/python-services'
    monkeypatch.syspath_prepend(str(root))
    import pipeline_delivery
    return root,pipeline_delivery


def test_failed_quality_delivers_actual_mesh_without_claiming_success(tmp_path,monkeypatch):
    root,module=services(monkeypatch)
    work=tmp_path/'juan_bike_123'/'work';work.mkdir(parents=True)
    path=work/'juan_bike_123_mesh.glb'
    mesh=trimesh.creation.icosphere(subdivisions=1)
    mesh.visual.vertex_colors=np.tile([20,100,230,255],(len(mesh.vertices),1))
    mesh.export(path)
    result=module.preserve_failed_mesh({'ok':False,'error':'pose mismatch','final_mesh':str(path)},work,'juan_bike_123')
    assert not result['ok'] and result['error']=='pose mismatch'
    assert result['mesh_produced'] and result['validation_status']=='failed'
    assert Path(result['final_mesh']).is_file() and Path(result['final_mesh']).parent.name=='modele'
    assert module.valid_mesh(result['final_mesh'])
    import glb_io
    colored,_=glb_io.load(result['final_mesh'])
    pure,_=glb_io.load(result['livraison']['modele_geometrie'])
    assert any('COLOR_0' in p['attributes'] for m in colored['meshes'] for p in m['primitives'])
    assert all('COLOR_0' not in p['attributes'] for m in pure['meshes'] for p in m['primitives'])
    # Execute the real color detector without loading any model/pipeline imports.
    tree=ast.parse((root/'aurora_3d_pipeline.py').read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_a_de_la_couleur')
    scope={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'color','exec'),scope)
    assert scope['_a_de_la_couleur'](result['final_mesh'])
    assert not scope['_a_de_la_couleur'](result['livraison']['modele_geometrie'])


def test_no_mesh_truncation_and_external_file_are_not_relabelled_as_delivery(tmp_path,monkeypatch):
    _,module=services(monkeypatch)
    work=tmp_path/'juan_bike_123'/'work';work.mkdir(parents=True)
    outside=tmp_path/'outside.glb';trimesh.creation.box().export(outside)
    bad=work/'juan_bike_123_mesh.glb';bad.write_bytes(outside.read_bytes()[:-20])
    assert not module.valid_mesh(bad)
    result=module.preserve_failed_mesh({'ok':False,'error':'no output','final_mesh':str(outside)},work,'juan_bike_123')
    assert not result['mesh_produced'] and outside.exists()
    assert not (work.parent/'modele').exists()


def test_terminal_receipt_binds_organized_delivery_not_deleted_work_directory(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from agi_core.operation_receipts import write_receipt,receipt_path,sha256_file
    root,module=services(monkeypatch)
    run_id='juan_bike_123';work=tmp_path/run_id/'work';work.mkdir(parents=True)
    mesh=work/(run_id+'_mesh.glb');trimesh.creation.box().export(mesh)
    result=module.preserve_failed_mesh({'ok':False,'error':'not yet faithful','final_mesh':str(mesh)},work,run_id)
    source=root/'aurora_3d_pipeline.py';tree=ast.parse(source.read_text())
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    block=next(n for n in ast.walk(main) if isinstance(n,ast.Try) and any(isinstance(v,ast.Call) and isinstance(v.func,ast.Name) and v.func.id=='write_receipt' for statement in n.body for v in ast.walk(statement)))
    scope={'Path':Path,'args':SimpleNamespace(output_dir=str(work),run_id=run_id,prompt='subject'),
           '_producer_sha256':sha256_file(source),'result':result,'write_receipt':write_receipt}
    exec(compile(ast.Module(body=[block],type_ignores=[]),str(source),'exec'),scope)
    import json
    receipt=json.loads(receipt_path(work.parent,run_id).read_text())
    assert receipt['status']=='failed' and not receipt['result']['ok']
    assert receipt['artifacts'][0]['path']=='modele/modele_couleurs.glb'
    assert receipt['artifacts'][0]['sha256']==sha256_file(result['final_mesh'])
