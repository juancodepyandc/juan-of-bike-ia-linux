"""Gateway authorization: reconnect, frames and downloads must share the same guard."""
import hashlib
from pathlib import Path
from unittest.mock import Mock
from flask import Blueprint, Flask
import pytest
from application.persistent_workspace_api import register_workspace_routes

@pytest.fixture
def gateway(tmp_path,monkeypatch):
    token_dir=tmp_path/'.aurora/persistent-workspace';token_dir.mkdir(parents=True)
    (token_dir/'token').write_text('internal-fixture-token')
    app=Flask(__name__);bp=Blueprint('workspace',__name__)
    from flask import request
    register_workspace_routes(bp,tmp_path,local=lambda:False,admin=lambda:False,
        extension=lambda:(request.headers.get('Authorization')=='Bearer owner',None,None),node=lambda:'node')
    app.register_blueprint(bp)
    upstream=Mock(status_code=200,content=b'{"ok":true}',headers={'Content-Type':'application/json'},ok=True)
    upstream.json.return_value={'ok':True,'service':'aurora-persistent-workspace'}
    calls=Mock(return_value=upstream)
    monkeypatch.setattr('application.persistent_workspace_api.requests.request',calls)
    monkeypatch.setattr('application.persistent_workspace_api.requests.get',Mock(return_value=upstream))
    return app.test_client(),calls

@pytest.mark.parametrize('method,path',[('post','/api/workspace-session'),('get','/api/workspace-session/frame'),('post','/api/workspace-session/action'),('get','/api/workspace-session/download/example')])
def test_public_cannot_control_read_or_download_without_credential(gateway,method,path):
    client,calls=gateway
    assert getattr(client,method)(path,json={} if method=='post' else None).status_code==403
    assert not calls.called

@pytest.mark.parametrize('method,path',[('post','/api/workspace-session'),('get','/api/workspace-session/frame'),('post','/api/workspace-session/action'),('get','/api/workspace-session/download/example')])
def test_owner_hash_not_client_supplied_session_id(gateway,method,path):
    client,calls=gateway
    r=getattr(client,method)(path,headers={'Authorization':'Bearer owner','X-Aurora-Workspace-Owner':'forged'},json={} if method=='post' else None)
    assert r.status_code==200 and r.headers['Cache-Control']=='no-store'
    headers=calls.call_args.kwargs['headers']
    assert headers['X-Aurora-Workspace-Owner']==hashlib.sha256(b'Bearer owner').hexdigest()
    assert headers['X-Aurora-Workspace-Token']=='internal-fixture-token'
