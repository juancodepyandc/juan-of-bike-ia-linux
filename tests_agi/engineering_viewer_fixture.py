"""Owned Flask engineering API and real packaged STL/GLB browser fixture."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import Flask,Blueprint,send_from_directory
from werkzeug.serving import make_server
import trimesh

from agi_core.mission_store import MissionStore
from application.engineering_design_api import register_design_routes
from application.engineering_project import build_project


with TemporaryDirectory(prefix='aurora-insertion-viewer-') as temporary:
    root=Path(temporary);store=MissionStore(root/'missions.sqlite3')
    app=Flask(__name__);bp=Blueprint('engineering_fixture',__name__)
    register_design_routes(bp,root,local=lambda:True,extension=lambda:(False,None,None),model_default=lambda:'QA-no-inference',store=store,dispatch=lambda *args:True)
    app.register_blueprint(bp)
    @app.route('/api/asset/output/engineering-design/<project>/<path:name>')
    def asset(project,name):
        if project!=did:return '',404
        return send_from_directory(folder,name)
    item=app.test_client().post('/api/3d/design',json={'objective':'Measured translation browser fixture','request_id':'browser-insertion-fixture'}).json
    did=item['id'];folder=root/'output'/'engineering-design'/did
    trimesh.creation.box([20,20,20]).export(folder/'moving.stl')
    trimesh.creation.box([.1,40,40]).export(folder/'wall.stl')
    (folder/'design.py').write_text('# Controlled geometry fixture, no neural generation\n')
    (folder/'tests.py').write_text('# Tested independently by browser and geometry tests\n')
    build_project({'units':'mm','title':'Insertion contrôlée','objective':'Compare actual swept paths',
                   'parts':[{'id':'moving','file':'moving.stl'},
                            {'id':'wall','file':'wall.stl','assembly_matrix_mm':trimesh.transformations.translation_matrix([60,0,0]).tolist()}],
                   'blockers':['Physical strength and printer calibration have not been tested.']},folder)
    store.append(item['mission_id'],{'type':'mission_complete','result':'Controlled geometry fixture only'})
    server=make_server('127.0.0.1',0,app,threaded=True)
    viewer=app.test_client().get('/api/3d/design/'+did).json['viewer_url']
    print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}'+viewer}),flush=True)
    server.serve_forever()
