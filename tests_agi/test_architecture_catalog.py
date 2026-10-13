import importlib.util
from pathlib import Path
import subprocess

MODULE=Path(__file__).resolve().parents[1]/'scripts/documentation/architecture_catalog.py'
spec=importlib.util.spec_from_file_location('architecture_catalog_test',MODULE)
catalog=importlib.util.module_from_spec(spec);spec.loader.exec_module(catalog)


def test_catalog_reads_indexed_sources_without_publishing_unstaged_drafts_or_weights(tmp_path):
    subprocess.run(['git','init','--quiet',str(tmp_path)],check=True)
    (tmp_path/'service.py').write_text('raise RuntimeError("must not import")\n')
    (tmp_path/'model.safetensors').write_bytes(b'weights')
    (tmp_path/'status.json').write_text('{"online":true}')
    subprocess.run(['git','add','service.py','model.safetensors','status.json'],cwd=tmp_path,check=True)
    (tmp_path/'service.py').write_text('private unstaged draft\n')
    assert list(catalog.indexed_sources(tmp_path))==[('service.py',b'raise RuntimeError("must not import")\n')]


def test_route_inventory_is_literal_and_does_not_execute_decorators():
    source=b'''@bp.route('/api/real', methods=['POST'])
def handler():
    raise RuntimeError('not executed')
@bp.get('/api/read/<id>')
async def read(id): pass
@bp.route(dynamic_path())
def dynamic(): pass
'''
    routes,scope=catalog.python_routes(source)
    assert [(r['path'],r['methods']) for r in routes]==[('/api/real',['POST']),('/api/read/<id>',['GET'])]
    assert scope=='static_decorators_only'
