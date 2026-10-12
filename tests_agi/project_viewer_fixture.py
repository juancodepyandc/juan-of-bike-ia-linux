"""Real GLB and Flask routes for browser contract tests; no neural inference."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import trimesh
from flask import Flask,Blueprint
from werkzeug.serving import make_server
from agi_core.mission_store import MissionStore
from application.projects_api import register_project_routes

with TemporaryDirectory(prefix='aurora-project-viewer-') as temp:
    root=Path(temp);store=MissionStore(root/'missions.sqlite3')
    mission=store.create({'request':'Inspection de géométrie 3D contrôlée','workspace':str(root),'model':'QA-no-inference'})[0]
    folder=root/'.transfer_to_client'/mission['id'];folder.mkdir(parents=True)
    scene=trimesh.Scene()
    sphere=trimesh.creation.icosphere(subdivisions=2);sphere.visual.face_colors=[170,70,160,255]
    torus=trimesh.creation.torus(major_radius=1.3,minor_radius=.15);torus.visual.face_colors=[80,170,220,255]
    scene.add_geometry(sphere,node_name='closed-sphere');scene.add_geometry(torus,node_name='closed-torus')
    marker=trimesh.creation.box(extents=[.4,.5,.7]);marker.apply_translation([1.6,.4,.3]);marker.visual.face_colors=[240,160,40,255]
    scene.add_geometry(marker,node_name='asymmetric-inspection-marker')
    scene.export(folder/'measured.glb')
    store.append(mission['id'],{'type':'mission_complete','result':'Controlled geometry fixture'})
    app=Flask(__name__);bp=Blueprint('projects_fixture',__name__)
    register_project_routes(bp,allowed=lambda:True,store=store);app.register_blueprint(bp)
    server=make_server('127.0.0.1',0,app,threaded=True)
    print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}/api/projects/{mission["id"]}/viewer/viewer.html'}),flush=True)
    server.serve_forever()
