from flask import Flask,Blueprint
from agi_core.mission_store import MissionStore
from application.projects_api import register_project_routes


def make(tmp_path,allowed=True):
    app=Flask(__name__);bp=Blueprint('projects',__name__);store=MissionStore(tmp_path/'projects.sqlite3');register_project_routes(bp,allowed=lambda:allowed,store=store);app.register_blueprint(bp);return app.test_client(),store


def test_public_admission_and_history_forbidden(tmp_path):
    c,_=make(tmp_path,False)
    assert c.get('/api/projects').status_code==403
    assert c.post('/api/projects/admission',json={}).status_code==403


def test_all_managed_modules_share_admission_with_engineering_and_keep_fifo(tmp_path):
    c,store=make(tmp_path);payload={'request_id':'request-one','title':'Image contrôlée','module':'image','model':'fixture'}
    first=c.post('/api/projects/admission',json=payload).json
    assert c.post('/api/projects/admission',json=payload).json['id']==first['id']
    second=c.post('/api/projects/admission',json={**payload,'request_id':'request-two','module':'video'}).json
    assert c.post('/api/projects/'+first['id']+'/admission',json={}).json['status']=='running'
    assert c.post('/api/projects/'+second['id']+'/admission',json={}).json['status']=='queued'
    engineering=store.create({'request':'Engineering','model':'fixture','project_kind':'engineering'},queued=True)[0]
    assert not store.claim(engineering['id'],'daemon',serialize=True)
    assert c.post('/api/projects/'+first['id']+'/finish',json={'status':'completed'}).json['status']=='completed'
    assert not store.claim(engineering['id'],'daemon',serialize=True)  # Older queued video goes first.
    assert c.post('/api/projects/'+second['id']+'/admission',json={}).json['status']=='running'
    assert c.post('/api/projects/'+second['id']+'/finish',json={'status':'failed'}).json['status']=='failed'
    assert store.claim(engineering['id'],'daemon',serialize=True)
    assert all(m['payload'].get('project_kind')!='frontend' for m in store.queued())
    assert len(c.get('/api/projects').json['projects'])==3


def test_conflicting_idempotence_and_nonfrontend_finish_are_rejected(tmp_path):
    c,store=make(tmp_path);payload={'request_id':'request-one','title':'Project','module':'3d'}
    c.post('/api/projects/admission',json=payload)
    assert c.post('/api/projects/admission',json={**payload,'title':'Changed'}).status_code==409
    mission=store.create({'request':'Actual mission','model':'fixture'},queued=True)[0]
    assert c.post('/api/projects/'+mission['id']+'/finish',json={'status':'completed'}).status_code==404
    assert c.post('/api/projects/admission',json={'request_id':'invalid','title':'P','module':'unknown'}).status_code==400


def test_cancel_is_atomic_before_start_and_never_releases_running_work(tmp_path):
    c,store=make(tmp_path)
    first=c.post('/api/projects/admission',json={'request_id':'request-one','title':'P','module':'image'}).json
    assert c.post('/api/projects/'+first['id']+'/cancel',json={}).status_code==200
    assert c.post('/api/projects/'+first['id']+'/admission',json={}).json['status']=='stopped'
    second=c.post('/api/projects/admission',json={'request_id':'request-two','title':'P2','module':'image'}).json
    assert c.post('/api/projects/'+second['id']+'/admission',json={}).json['status']=='running'
    assert c.post('/api/projects/'+second['id']+'/cancel',json={}).status_code==409
    assert store.get(second['id'])['status']=='running'


def test_repeated_ticket_never_grants_two_frontend_executors(tmp_path):
    c,store=make(tmp_path);p=c.post('/api/projects/admission',json={'request_id':'request-same','title':'P','module':'3d'}).json
    url='/api/projects/'+p['id']+'/admission'
    assert c.post(url,json={'executor':'a'*32}).json['granted']
    assert not c.post(url,json={'executor':'b'*32}).json['granted']
    assert c.post('/api/projects/'+p['id']+'/finish',json={'status':'completed','executor':'b'*32}).status_code==409
    assert store.get(p['id'])['status']=='running'
    assert c.post('/api/projects/'+p['id']+'/finish',json={'status':'completed','executor':'a'*32}).status_code==200


def test_finish_requires_execution_and_preserves_terminal_outcome(tmp_path):
    c,store=make(tmp_path)
    p=c.post('/api/projects/admission',json={'request_id':'request-final','title':'P','module':'image'}).json
    finish='/api/projects/'+p['id']+'/finish'
    assert c.post(finish,json={'status':'completed'}).status_code==409
    assert store.get(p['id'])['status']=='queued'
    assert c.post('/api/projects/'+p['id']+'/admission',json={'executor':'a'*32}).json['granted']
    assert c.post(finish,json={'status':'completed','executor':'a'*32}).status_code==200
    assert c.post(finish,json={'status':'completed','executor':'a'*32}).status_code==200
    assert c.post(finish,json={'status':'failed','executor':'a'*32}).status_code==409
    assert store.get(p['id'])['status']=='completed'


def test_expired_unknown_execution_survives_reopen_without_second_executor(tmp_path):
    c,store=make(tmp_path)
    first=c.post('/api/projects/admission',json={'request_id':'request-expired','title':'P','module':'image'}).json
    assert c.post('/api/projects/'+first['id']+'/admission',json={'executor':'a'*32}).json['granted']
    # Simulate a lost controller / PC restart after the pipeline started.
    import sqlite3
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE missions SET lease=0 WHERE id=?',(first['id'],))
    c,reopened=make(tmp_path)
    assert reopened.get(first['id'])['status']=='interrupted'
    assert not c.post('/api/projects/'+first['id']+'/admission',json={'executor':'b'*32}).json['granted']
    second=c.post('/api/projects/admission',json={'request_id':'request-after','title':'P2','module':'video'}).json
    assert c.post('/api/projects/'+second['id']+'/admission',json={'executor':'b'*32}).json['status']=='queued'
    blockers=reopened.scheduling(second['id'])['blockers']
    assert blockers[0]['id']==first['id'] and blockers[0]['status']=='interrupted'
    # Only the original executor may report the actual outcome, even after reconnect.
    assert c.post('/api/projects/'+first['id']+'/finish',json={'status':'failed','executor':'a'*32}).status_code==200
    assert c.post('/api/projects/'+second['id']+'/admission',json={'executor':'b'*32}).json['granted']


def test_legacy_cli_3d_has_resume_and_authenticated_mesh_viewer(tmp_path,monkeypatch):
    from pathlib import Path
    import trimesh
    c,store=make(tmp_path)
    item=store.create({'request':'Une figurine 3D','workspace':str(tmp_path),'model':'fixture'})[0]
    store.append(item['id'],{'type':'error','message':'Observed missing tool'})
    folder=tmp_path/'.transfer_to_client'/item['id'];folder.mkdir(parents=True)
    trimesh.creation.icosphere().export(folder/'actual.glb')
    (folder/'private.py').write_text('private')
    (folder/'unfinished.glb').write_bytes(b'partially written output')
    (folder/'escape.glb').symlink_to(tmp_path/'outside.glb')
    (tmp_path/'outside.glb').write_bytes(b'outside')
    project=c.get('/api/projects').json['projects'][0]
    assert project['module']=='3d' and project['resumable']
    assert len(project['meshes'])==1
    assert c.get(project['meshes'][0]['url']).status_code==200
    assert c.get(project['viewer_url']).status_code==200
    assert c.get('/api/projects/'+item['id']+'/files/private.py').status_code==404
    assert c.get('/api/projects/'+item['id']+'/files/escape.glb').status_code==404
    monkeypatch.setattr('application.engineering_design_api.publish',lambda *args:True)
    assert c.post('/api/projects/'+item['id']+'/resume',json={}).status_code==202
    assert store.get(item['id'])['status']=='queued'
    assert c.post('/api/projects/'+item['id']+'/resume',json={}).status_code==409
    denied,_=make(tmp_path,False)
    assert denied.get(project['viewer_url']).status_code==403
    assert denied.get(project['meshes'][0]['url']).status_code==403
    assert denied.post('/api/projects/'+item['id']+'/resume',json={}).status_code==403


def test_cli_assembly_and_plate_views_are_separate_from_original(tmp_path):
    import json
    import trimesh
    c,store=make(tmp_path)
    item=store.create({'request':'Figurine 3D imprimable','workspace':str(tmp_path),'model':'fixture'})[0]
    root=tmp_path/'.transfer_to_client'/item['id'];folder=root/'manufacturing';folder.mkdir(parents=True)
    mesh=trimesh.creation.box()
    mesh.export(root/'original.glb');mesh.export(folder/'assembled.glb');mesh.export(folder/'plate-1.glb')
    (folder/'assembly.json').write_text(json.dumps({'mode':'assembly','piece_count':2,'parts':[{'id':'one'},{'id':'two'}],'profile':{'name':'Single filament'}}))
    (folder/'textures').mkdir();(folder/'textures'/'color.png').write_bytes(b'fixture')
    project=c.get('/api/projects').json['projects'][0]
    assert [m['name'] for m in project['meshes']]==['original.glb']
    assembly=project['assemblies'][0]['url']
    assert c.get(assembly).status_code==200
    assert b'Assemblage 3D' in c.get(assembly).data
    assert c.get(assembly.replace('viewer.html','plate-1.glb')).status_code==200
    assert c.get(assembly.replace('viewer.html','textures/color.png')).status_code==200
    assert c.get(assembly.replace('viewer.html','../../outside.py')).status_code==404


def test_stop_running_admission_releases_queue_and_is_idempotent(tmp_path):
    c,store=make(tmp_path)
    first=c.post('/api/projects/admission',json={'request_id':'request-stop-active','title':'P','module':'3d'}).json
    second=c.post('/api/projects/admission',json={'request_id':'request-stop-next','title':'Next','module':'3d'}).json
    executor='a'*32
    assert c.post('/api/projects/'+first['id']+'/admission',json={'executor':executor}).json['granted']
    assert c.post('/api/projects/'+second['id']+'/admission',json={'executor':'b'*32}).json['status']=='queued'
    path='/api/projects/'+first['id']+'/finish'
    assert c.post(path,json={'status':'stopped','executor':'b'*32}).status_code==409
    assert c.post(path,json={'status':'stopped','executor':executor}).json['status']=='stopped'
    assert c.post(path,json={'status':'stopped','executor':executor}).json['status']=='stopped'
    assert c.post(path,json={'status':'completed','executor':executor}).status_code==409
    assert c.post('/api/projects/'+second['id']+'/admission',json={'executor':'b'*32}).json['granted']


def test_stop_does_not_release_reservation_before_workers_exit(tmp_path):
    app=Flask(__name__);bp=Blueprint('stop_projects',__name__);store=MissionStore(tmp_path/'stop.sqlite3')
    idle=[False]
    register_project_routes(bp,allowed=lambda:True,store=store,work_idle=lambda:idle[0])
    app.register_blueprint(bp);c=app.test_client()
    item=c.post('/api/projects/admission',json={'request_id':'request-workers','title':'P','module':'3d'}).json
    c.post('/api/projects/'+item['id']+'/admission',json={'executor':'a'*32})
    path='/api/projects/'+item['id']+'/finish'
    response=c.post(path,json={'status':'stopped','executor':'a'*32})
    assert response.status_code==409 and response.json['code']=='workers_stopping'
    assert store.get(item['id'])['status']=='running'
    idle[0]=True
    assert c.post(path,json={'status':'stopped','executor':'a'*32}).json['status']=='stopped'
