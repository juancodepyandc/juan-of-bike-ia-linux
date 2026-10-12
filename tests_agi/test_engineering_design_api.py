from flask import Flask, Blueprint, request
from agi_core.mission_store import MissionStore
from application.engineering_design_api import register_design_routes


def test_durable_idempotent_owned_mission_and_invalid_delivery(tmp_path):
    app=Flask(__name__);bp=Blueprint('design',__name__);store=MissionStore(tmp_path/'missions.sqlite3');calls=[]
    register_design_routes(bp,tmp_path,local=lambda:False,extension=lambda:(request.headers.get('Authorization')=='Bearer owner',None,None),model_default=lambda:'fixture-model',store=store,dispatch=lambda event,payload:calls.append((event,payload)) or True)
    app.register_blueprint(bp);c=app.test_client();headers={'Authorization':'Bearer owner'}
    data={'objective':'Concevoir un support selon ses efforts et interfaces.','request_id':'request-12345'}
    assert c.post('/api/3d/design',json=data).status_code==403
    first=c.post('/api/3d/design',json=data,headers=headers);assert first.status_code==202
    item=first.json;assert not item['ready'] and len(calls)==1
    assert c.post('/api/3d/design',json=data,headers=headers).json['id']==item['id'] and len(calls)==1
    assert c.post('/api/3d/design',json={**data,'objective':'Autre objectif'},headers=headers).status_code==409
    assert c.get('/api/3d/design',headers=headers).json['projects'][0]['id']==item['id']
    folder=tmp_path/'output'/'engineering-design'/item['id'];(folder/'project.json').write_text('{}');(folder/'engineering-project.zip').write_text('fake archive')
    store.append(item['mission_id'],{'type':'mission_complete','result':'Terminé'})
    result=c.get('/api/3d/design/'+item['id'],headers=headers).json
    assert result['state']=='incomplete' and not result['ready']
    assert c.get('/api/3d/design/'+item['id']+'/download',headers=headers).status_code==404
    assert c.get('/api/3d/design/'+item['id']).status_code==403
    assert c.post('/api/3d/design/'+item['id']+'/simulate',json={}).status_code==403


def test_delivery_checks_actual_geometry_and_changed_archive(tmp_path):
    import trimesh
    import json
    from application.engineering_project import build_project
    app=Flask(__name__);bp=Blueprint('design_ready',__name__);store=MissionStore(tmp_path/'missions.sqlite3')
    register_design_routes(bp,tmp_path,local=lambda:True,extension=lambda:(False,None,None),model_default=lambda:'fixture',store=store,dispatch=lambda *a:True)
    app.register_blueprint(bp);c=app.test_client()
    d=c.post('/api/3d/design',json={'objective':'Objectif de test indépendant','request_id':'delivery-123'}).json
    folder=tmp_path/'output'/'engineering-design'/d['id'];trimesh.creation.box([20,15,10]).export(folder/'source.stl')
    (folder/'design.py').write_text('import trimesh\n')
    (folder/'tests.py').write_text('assert 20 < 220\n')
    build_project({'units':'mm','title':'Prototype','objective':'Tester les preuves réelles','parts':[{'id':'one','file':'source.stl'}]},folder)
    store.append(d['mission_id'],{'type':'mission_complete','result':'preuves'})
    path='/api/3d/design/'+d['id']
    assert c.get(path).json['ready']
    assert c.get(path+'/download').status_code==200
    simulation=c.post(path+'/simulate',json={})
    assert simulation.status_code==200 and simulation.json['dof']==0
    assert simulation.json['collisions']==[]
    assert c.post(path+'/simulate',json=[]).status_code==400
    assert c.post(path+'/simulate',json={'values':{'fake':1}}).status_code==400
    trimesh.creation.box([30,15,10]).export(folder/'printable'/'piece_01.stl')
    assert not c.get(path).json['ready']


def test_resume_when_daemon_offline_retains_retryable_state(tmp_path):
    app=Flask(__name__);bp=Blueprint('offline',__name__);store=MissionStore(tmp_path/'missions.sqlite3');availability=iter([False,False,True])
    register_design_routes(bp,tmp_path,local=lambda:True,extension=lambda:(False,None,None),model_default=lambda:'fixture',store=store,dispatch=lambda *a:next(availability))
    app.register_blueprint(bp);c=app.test_client();d=c.post('/api/3d/design',json={'objective':'Projet durable','request_id':'offline-123'}).json
    assert d['state']=='queued'
    path='/api/3d/design/'+d['id']
    assert c.post(path+'/resume',json={}).status_code==409
    assert c.get(path).json['state']=='queued'
    other=c.post('/api/3d/design',json={'objective':'Second projet','request_id':'offline-456'}).json
    assert other['state']=='queued' and other['scheduling']['queue_position']==2
    assert c.get(path).json['mission_id']==d['mission_id']


def test_verified_prototype_available_without_claiming_mission_success(tmp_path):
    import trimesh
    from application.engineering_project import build_project
    app=Flask(__name__);bp=Blueprint('partial',__name__);store=MissionStore(tmp_path/'missions.sqlite3')
    register_design_routes(bp,tmp_path,local=lambda:True,extension=lambda:(False,None,None),model_default=lambda:'fixture',store=store,dispatch=lambda *a:True)
    app.register_blueprint(bp);c=app.test_client();d=c.post('/api/3d/design',json={'objective':'Prototype partiel','request_id':'partial-123'}).json
    folder=tmp_path/'output'/'engineering-design'/d['id'];trimesh.creation.box([20,15,10]).export(folder/'source.stl')
    (folder/'design.py').write_text('import trimesh\n');(folder/'tests.py').write_text('assert True\n')
    build_project({'units':'mm','title':'Prototype','objective':'Étude','parts':[{'id':'one','file':'source.stl'}]},folder)
    store.append(d['mission_id'],{'type':'error','message':'Validation finale incomplète'})
    path='/api/3d/design/'+d['id'];result=c.get(path).json
    assert result['state']=='failed' and not result['ready']
    assert result['artifacts_available'] and result['partial']
    assert c.get(path+'/download').status_code==200
