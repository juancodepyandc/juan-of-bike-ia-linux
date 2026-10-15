from flask import Flask, Blueprint, request
from agi_core.mission_store import MissionStore
from application.engineering_design_api import register_design_routes


def test_existing_cli_mesh_is_snapshotted_for_engineering_not_reinvented(tmp_path):
    import trimesh
    app=Flask(__name__);bp=Blueprint('source_design',__name__);store=MissionStore(tmp_path/'source.sqlite3');calls=[]
    parent=store.create({'request':'Figurine 3D','workspace':str(tmp_path),'model':'fixture'})[0]
    delivery=tmp_path/'.transfer_to_client'/parent['id'];delivery.mkdir(parents=True)
    trimesh.creation.icosphere().export(delivery/'original.glb');before=(delivery/'original.glb').read_bytes()
    register_design_routes(bp,tmp_path,local=lambda:True,extension=lambda:(False,None,None),model_default=lambda:'fixture',store=store,dispatch=lambda *args:calls.append(args) or True)
    app.register_blueprint(bp);c=app.test_client()
    data={'objective':'Préparer les couleurs et les interfaces internes de ce modèle.','request_id':'source-request-123','source':{'mission_id':parent['id'],'file':'original.glb'}}
    r=c.post('/api/3d/design',json=data);assert r.status_code==202
    folder=tmp_path/'output'/'engineering-design'/r.json['id']
    assert (folder/'source.glb').read_bytes()==before
    assert 'MODÈLE SOURCE IMMUTABLE' in store.get(r.json['mission_id'])['payload']['request']
    assert c.post('/api/3d/design',json=data).json['id']==r.json['id'] and len(calls)==1
    assert c.post('/api/3d/design',json={**data,'request_id':'bad-source-request','source':{'mission_id':parent['id'],'file':'../../private.glb'}}).status_code==400


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
    assert c.post('/api/3d/design/'+item['id']+'/insertion',json={}).status_code==403


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
    viewer=c.get(path).json['viewer_url']
    (folder/'viewer.html').write_text('<script>throw Error("legacy renderer must not execute")</script>')
    rendered=c.get(viewer)
    assert rendered.status_code==200 and b'legacy renderer' not in rendered.data
    assert 'Vérifier l’insertion'.encode() in rendered.data
    assert c.get(viewer.removesuffix('viewer.html')+'design.py').status_code==404
    assert c.get(viewer.removesuffix('viewer.html')+'assembled.glb').status_code==200
    simulation=c.post(path+'/simulate',json={})
    assert simulation.status_code==200 and simulation.json['dof']==0
    assert simulation.json['collisions']==[]
    assert c.post(path+'/simulate',json=[]).status_code==400
    assert c.post(path+'/simulate',json={'values':{'fake':1}}).status_code==400
    insertion=c.post(path+'/insertion',json={'part_id':'piece_01'})
    assert insertion.status_code==200 and insertion.json['continuous_collision_validated']
    assert not insertion.json['physical_fit_validated']
    assert c.post(path+'/insertion',json={'part_id':'invented'}).status_code==400
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


def test_stop_and_delete_preserve_active_work_and_retained_proofs(tmp_path):
    app=Flask(__name__);bp=Blueprint('lifecycle',__name__);store=MissionStore(tmp_path/'lifecycle.sqlite3');calls=[]
    register_design_routes(bp,tmp_path,local=lambda:True,extension=lambda:(False,None,None),model_default=lambda:'fixture',store=store,dispatch=lambda *args:calls.append(args) or True)
    app.register_blueprint(bp);client=app.test_client()
    item=client.post('/api/3d/design',json={'objective':'Conserver les preuves','request_id':'lifecycle-test-123'}).json
    path='/api/3d/design/'+item['id'];folder=tmp_path/'output/engineering-design'/item['id']
    proof=folder/'evidence.json';proof.write_text('{"actual":"retained"}')
    assert store.claim(item['mission_id'],'real-worker')
    assert client.post(path+'/delete',json={}).status_code==409
    assert client.get(path).json['state']=='running' and proof.is_file()
    stopped=client.post(path+'/stop',json={})
    assert stopped.status_code==202 and store.get(item['mission_id'])['status']=='stopping'
    assert calls[-1][0]=='mission.stop'
    store.append(item['mission_id'],{'type':'mission_complete','stopped':True,'result':'Stopped by actual worker'})
    assert client.post(path+'/delete',json={}).status_code==200
    assert client.get(path).status_code==404 and proof.is_file()


def test_queue_claim_race_does_not_fabricate_a_finished_stop(tmp_path):
    from unittest.mock import patch
    app=Flask(__name__);bp=Blueprint('claim_race',__name__);store=MissionStore(tmp_path/'race.sqlite3');calls=[]
    register_design_routes(bp,tmp_path,local=lambda:True,extension=lambda:(False,None,None),model_default=lambda:'fixture',store=store,dispatch=lambda *args:calls.append(args) or True)
    app.register_blueprint(bp);client=app.test_client()
    item=client.post('/api/3d/design',json={'objective':'Traiter la concurrence','request_id':'queue-claim-test-123'}).json
    def claimed(mid):
        assert store.claim(mid,'worker-that-claimed')
        return False
    with patch.object(store,'cancel_queued',side_effect=claimed):
        response=client.post('/api/3d/design/'+item['id']+'/stop',json={})
    assert response.status_code==202
    assert store.get(item['mission_id'])['status']=='stopping'
    assert not any(event.get('type')=='mission_complete' for _,event in store.events(item['mission_id']))


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


def test_design_telemetry_and_assembly_steps_enrichment(tmp_path):
    import json
    import trimesh
    from application.engineering_project import build_project
    app=Flask(__name__);bp=Blueprint('telemetry_design',__name__);store=MissionStore(tmp_path/'telemetry.sqlite3')
    register_design_routes(bp,tmp_path,local=lambda:True,extension=lambda:(False,None,None),model_default=lambda:'fixture',store=store,dispatch=lambda *a:True)
    app.register_blueprint(bp);c=app.test_client()
    d=c.post('/api/3d/design',json={
        'objective':'Mécanisme articulé 2 pièces avec visserie M3',
        'constraints':'Jeu 0,25 mm',
        'profile':{'name':'Prusa MK4','process':'FDM','bed_mm':[250,210,220],'clearance_mm':0.2,'wall_mm':2.0,'margin_mm':5.0},
        'request_id':'telemetry-req-1',
    }).json
    assert 'telemetry' in d
    assert d['telemetry']['profile_summary']['name']=='Prusa MK4'
    folder=tmp_path/'output'/'engineering-design'/d['id']
    trimesh.creation.box([30,20,10]).export(folder/'base.stl')
    trimesh.creation.box([20,10,8]).export(folder/'arm.stl')
    (folder/'design.py').write_text('import trimesh\n')
    (folder/'tests.py').write_text('assert True\n')
    build_project({
        'units':'mm',
        'title':'Bras articulé M3',
        'objective':'Mécanisme articulé 2 pièces',
        'parts':[
            {'id':'base','name':'Socle fixe','file':'base.stl'},
            {'id':'arm','name':'Bras mobile','file':'arm.stl','assembly_matrix_mm':[[1,0,0,0],[0,1,0,0],[0,0,1,15],[0,0,0,1]]},
        ],
        'mechanism_joints':[
            {'id':'pivot_1','type':'revolute','parent':'base','child':'arm','axis':[0,0,1],'origin_mm':[0,0,15],'limits_deg':[-90,90]},
        ],
        'bom':[{'name':'Vis CHC M3x16','quantity':2,'specification':'ISO 4762','part_ids':['base','arm']}],
        'assembly_steps':[
            {'description':'Poser le socle sur l’établi','part_ids':['base']},
            {'instruction':'Assembler le bras mobile sur le pivot avec les vis M3','part_ids':['base','arm']},
        ],
        'assumptions':['PLA 20 % remplissage gyroid'],
    },folder)
    store.append(d['mission_id'],{'type':'plan','criteria':['Cotes plateau vérifiées','Cinématique sans collision']})
    store.append(d['mission_id'],{'type':'criterion_verified','index':0})
    store.append(d['mission_id'],{'type':'mission_complete','result':'Projet validé'})
    res=c.get('/api/3d/design/'+d['id']).json
    assert res['ready'] is True
    tel=res['telemetry']
    assert tel['progress_pct']==100
    assert tel['stl_count']>=2
    assert tel['draft_summary']['part_count']==2
    assert tel['draft_summary']['joint_count']==1
    assert tel['draft_summary']['dof']==1
    assert tel['draft_summary']['bom'][0]['name']=='Vis CHC M3x16'
    assert len(tel['sub_agents'])==5
    assert [a['id'] for a in tel['sub_agents']]==['agent-kinematics','agent-cad-geometry','agent-gaussian-splat','agent-materials-pbr','agent-qa-assembly']
    assert all(a['status']=='done' and a['progress_pct']==100 for a in tel['sub_agents'])
    assembly_manifest=json.loads((folder/'assembly.json').read_text())
    assert assembly_manifest['title']=='Bras articulé M3'
    assert len(assembly_manifest['bom'])==1
    assert assembly_manifest['assembly_steps'][1]['resolved_part_ids']==['piece_01','piece_02']

