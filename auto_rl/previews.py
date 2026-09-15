"""Preview real, already generated artifacts, including incomplete cycles."""
import json
from pathlib import Path
from urllib.parse import quote
from .storage import read_json

SUFFIXES={'.png','.jpg','.webp','.mp4','.npz','.wav','.glb','.txt','.py'}


def run_folder(state,run_id):
    root=(Path(state)/'runs').resolve();run=(root/run_id).resolve()
    if run.parent!=root or not (run/'config.json').is_file():raise ValueError('Cycle inconnu')
    return run


def sample_path(state,run_id,name):
    run=run_folder(state,run_id);path=(run/name).resolve()
    if not path.is_relative_to(run) or path.suffix not in SUFFIXES or not path.is_file():
        raise ValueError('Résultat absent ou hors du cycle')
    # Configuration, code and logs are not media artifacts.
    if Path(name).parts[0] not in {'train','self_play','audit'}:raise ValueError('Fichier non généré')
    return path


def samples(state,run_id):
    run=run_folder(state,run_id);result=[]
    for top in ('train','self_play','audit'):
        for p in sorted((run/top).rglob('*')):
            if not p.is_file() or p.suffix not in SUFFIXES or '_views' in str(p.relative_to(run)):continue
            if p.name in {'blender.log'}:continue
            name=str(p.relative_to(run));row=read_json(p.with_suffix('.evaluation.json'),{})
            url='/api/training/samples/'+quote(run_id,safe='')+'/asset?name='+quote(name,safe='')
            kind={'.npz':'animation','.glb':'3d','.wav':'audio','.mp4':'video','.webp':'video',
                  '.txt':'text','.py':'text'}.get(p.suffix,'image')
            result.append({'name':name,'url':url,'viewer':url+'&viewer=1' if kind in {'3d','animation'} else None,
                           'kind':kind,'prompt':row.get('prompt',p.stem),'judge':row.get('judge'),
                           'branch':str(p.relative_to(run)).split('/')[0],
                           'measured':bool(row),'bytes':p.stat().st_size})
    return result


def mesh_page(url):
    return '''<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#101723;color:#edf4ff;font:14px system-ui}canvas{display:block;width:100%;height:100vh}p{position:absolute;margin:12px;pointer-events:none}</style>
<p id="status">Chargement du vrai maillage…</p>
<script type="importmap">{"imports":{"three":"/api/training/viewer-lib/build/three.module.js"}}</script>
<script type="module">
import * as THREE from 'three';
import {GLTFLoader} from '/api/training/viewer-lib/examples/jsm/loaders/GLTFLoader.js';
import {OrbitControls} from '/api/training/viewer-lib/examples/jsm/controls/OrbitControls.js';
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(40,1,.001,1000);
const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));document.body.append(renderer.domElement);
renderer.setClearColor('#101723');scene.add(new THREE.HemisphereLight(0xffffff,0x637388,3));
const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(3,6,4);scene.add(light);
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
new GLTFLoader().load(ASSET,asset=>{scene.add(asset.scene);const box=new THREE.Box3().setFromObject(asset.scene),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3()).length()||1;
camera.position.copy(center).add(new THREE.Vector3(size,size*.6,size));camera.near=size/1000;camera.far=size*100;camera.updateProjectionMatrix();controls.target.copy(center);controls.update();document.querySelector('#status').textContent='Maillage généré · glisser pour tourner · molette pour zoomer';},undefined,e=>{document.querySelector('#status').textContent='Le maillage ne peut pas être affiché : '+e.message});
function draw(){const w=innerWidth,h=innerHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();controls.update();renderer.render(scene,camera);requestAnimationFrame(draw)}draw();
</script>'''.replace('ASSET',json.dumps(url).replace('<','\\u003c'))
