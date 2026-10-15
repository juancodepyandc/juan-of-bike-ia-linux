import base64
import hashlib
from pathlib import Path

from flask import Blueprint, Flask, jsonify, request
import pytest

from agi_core.mission_store import MissionStore
from application.cli_inputs import InputStore
from application.mission_api import register_mission_routes


@pytest.fixture
def server(tmp_path):
    import functools
    app=Flask(__name__);bp=Blueprint('input_fixture',__name__)
    inputs=InputStore(tmp_path/'private-inputs');store=MissionStore(tmp_path/'missions.sqlite')
    workspace=tmp_path/'workspace';workspace.mkdir();dispatches=[]
    def auth(fn):
        @functools.wraps(fn)
        def wrapped(*args,**kwargs):
            if request.headers.get('Authorization') not in {'Bearer one','Bearer two'}:
                return jsonify(ok=False,error='Unauthorized'),401
            return fn(*args,**kwargs)
        return wrapped
    register_mission_routes(bp,auth,workspace=str(workspace),model_default=lambda:'fixture',
                            publish=lambda topic,payload:dispatches.append(payload) or True,
                            store=store,input_store=inputs)
    app.register_blueprint(bp)
    return app.test_client(),inputs,store,workspace,dispatches


def encoded(content=b'CLIENT_REFERENCE\n'):
    return dict(filename='reference.txt',size=len(content),sha256=hashlib.sha256(content).hexdigest(),
                data=base64.b64encode(content).decode())


def test_real_input_transfers_before_dispatch_and_same_key_never_dispatches_twice(server):
    client,inputs,store,workspace,dispatches=server
    headers={'Authorization':'Bearer one'}
    receipt=client.post('/api/cli/inputs',json=encoded(),headers=headers).get_json()
    assert receipt['ok'] and not dispatches
    payload=dict(request='Inspect my client reference',model='fixture',permissions='SAFE',idempotency_key='same',
                 references=[dict(id=receipt['id'],label='C:\\Users\\Client\\reference.txt')])
    first=client.post('/api/cli/mission/start',json=payload,headers=headers).get_json()
    second=client.post('/api/cli/mission/start',json=payload,headers=headers).get_json()
    assert first['mission_id']==second['mission_id'] and len(dispatches)==1
    manifest=dispatches[0]['input_manifest'][0]
    actual=Path(manifest['server_path'])
    assert actual.is_relative_to(workspace) and actual.read_bytes()==b'CLIENT_REFERENCE\n'
    assert manifest['sha256']==encoded()['sha256']
    assert actual.as_posix() in dispatches[0]['request']


def test_auth_and_owner_are_required_before_using_receipt(server):
    client,inputs,store,workspace,dispatches=server
    assert client.post('/api/cli/inputs',json=encoded()).status_code==401
    receipt=client.post('/api/cli/inputs',json=encoded(),headers={'Authorization':'Bearer one'}).get_json()
    result=client.post('/api/cli/mission/start',json={'request':'Inspect', 'references':[dict(id=receipt['id'],label='ref')]},
                       headers={'Authorization':'Bearer two'})
    assert result.status_code==400 and not dispatches


@pytest.mark.parametrize('changes',[{'size':1},{'sha256':'0'*64},{'data':'invalid!'}, {'filename':'../file\x00'},
                                   {'size':True}, {'size':100_000_000}])
def test_corrupt_or_oversize_transfer_never_receives_receipt(server,changes):
    client,*_=server
    result=client.post('/api/cli/inputs',json={**encoded(),**changes},headers={'Authorization':'Bearer one'})
    assert result.status_code==400 and not result.get_json()['ok']


def test_tampered_stored_reference_prevents_dispatch(server):
    client,inputs,store,workspace,dispatches=server;headers={'Authorization':'Bearer one'}
    receipt=client.post('/api/cli/inputs',json=encoded(),headers=headers).get_json()
    (inputs.root/inputs.scope('Bearer one')/receipt['id']).write_bytes(b'tampered')
    result=client.post('/api/cli/mission/start',json={'request':'Inspect', 'references':[dict(id=receipt['id'],label='ref')]},headers=headers)
    assert result.status_code==400 and not dispatches


def test_workspace_input_symlink_cannot_escape(server,tmp_path):
    client,inputs,store,workspace,dispatches=server;headers={'Authorization':'Bearer one'}
    outside=tmp_path/'outside';outside.mkdir()
    try:
        (workspace/'.aurora').symlink_to(outside,target_is_directory=True)
    except OSError:
        pytest.skip('Symlinks unavailable on this host')
    receipt=client.post('/api/cli/inputs',json=encoded(),headers=headers).get_json()
    result=client.post('/api/cli/mission/start',json={'request':'Inspect','references':[dict(id=receipt['id'],label='ref')]},headers=headers)
    assert result.status_code==400 and not dispatches and not list(outside.iterdir())
