import hashlib
import io
import json
import time
import zipfile

from flask import Blueprint, Flask
import pytest
import trimesh

from application.engineering_api import register_engineering_routes
from test_engineering_mesh import config


@pytest.fixture
def client(tmp_path):
    app=Flask(__name__);bp=Blueprint('engineering_test',__name__)
    register_engineering_routes(bp,tmp_path);app.register_blueprint(bp)
    return app.test_client()


def finish(client,job,headers):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        response=client.get('/api/3d/engineering/'+job,headers=headers)
        status=response.get_json()
        if status.get('state')!='running':return status
        time.sleep(0.05)
    pytest.fail('Export did not finish')


def test_actual_subprocess_upload_poll_owner_and_verified_zip(client):
    raw=trimesh.creation.box([120,60,40]).export(file_type='stl')
    headers={'Authorization':'Bearer fixture'}
    response=client.post('/api/3d/engineering',headers=headers,data={
        'mesh':(io.BytesIO(raw),'source.stl'),'settings':json.dumps(config())})
    assert response.status_code==202
    job=response.get_json()['job_id']
    assert client.get('/api/3d/engineering/'+job,headers={'Authorization':'Bearer other'}).status_code==404
    status=finish(client,job,headers)
    assert status['ok'] and status['state']=='done' and status['report']['piece_count']==2
    downloaded=client.get(status['download_url'],headers=headers)
    assert downloaded.status_code==200
    assert hashlib.sha256(downloaded.data).hexdigest()==status['archive_sha256']
    with zipfile.ZipFile(io.BytesIO(downloaded.data)) as archive:
        assert archive.testzip() is None and 'piece_01.stl' in archive.namelist()
    assert client.get(status['download_url'],headers={'Authorization':'Bearer other'}).status_code==404


def test_open_mesh_never_gets_a_download_receipt(client):
    mesh=trimesh.creation.box();mesh.update_faces(list(range(len(mesh.faces)-1)))
    response=client.post('/api/3d/engineering',data={
        'mesh':(io.BytesIO(mesh.export(file_type='stl')),'broken.stl'),'settings':json.dumps(config())})
    job=response.get_json()['job_id'];status=finish(client,job,{})
    assert status['state']=='error' and not status['ok'] and 'volume fermé' in status['error']
    assert client.get('/api/3d/engineering/'+job+'/download').status_code==404


@pytest.mark.parametrize('settings', [{'size_mm':True},{'size_mm':200,'mode':'assembly'},{}])
def test_invalid_settings_are_rejected_before_job(client,settings):
    response=client.post('/api/3d/engineering',data={
        'mesh':(io.BytesIO(b'fixture'),'source.glb'),'settings':json.dumps(settings)})
    assert response.status_code==400 and not response.get_json()['ok']
