"""A PC-approved project dashboard, with real admission and measured estimates."""
import os
import hashlib
import re
from flask import jsonify,request,send_file
from pathlib import Path
import json
import struct
import time
from urllib.parse import quote
from agi_core.mission_store import MissionStore
from agi_core.mission_routing import mission_module


def register_project_routes(bp,*,allowed,store=None,work_idle=lambda: False):
    store=store or MissionStore()
    def reconcile():
        # An expired UI lease is not proof that its detached subprocess stopped.
        with store.connect() as db:
            expired = db.execute("SELECT 1 FROM missions WHERE status IN ('running','stopping') AND COALESCE(lease,0)<? AND json_extract(payload,'$.project_kind')='frontend' LIMIT 1", (time.time(),)).fetchone()
        if expired and work_idle():
            return store.reconcile_idle_frontend()
        return []

    @bp.route('/api/projects/reconcile',methods=['POST'])
    def reconcile_projects():
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        return jsonify(ok=True,released=reconcile())
    def delivery(item):
        return (Path(item['payload']['workspace'])/'.transfer_to_client'/item['id']).resolve()
    def complete_glb(path):
        try:
            with path.open('rb') as stream:header=stream.read(12)
            magic,version,size=struct.unpack('<4sII',header)
            return magic==b'glTF' and version==2 and size>=28 and size==path.stat().st_size
        except (OSError,ValueError,struct.error):return False
    def assemblies(item):
        if not item['payload'].get('workspace'):return []
        root=delivery(item);result=[]
        for manifest in sorted(root.rglob('assembly.json'))[:30]:
            if not manifest.resolve().is_relative_to(root):continue
            try:
                report=json.loads(manifest.read_text(encoding='utf-8'))
                if report.get('mode')!='assembly' or not report.get('parts') or report.get('piece_count')!=len(report['parts']):continue
                directory=manifest.parent.relative_to(root).as_posix()
                prefix='' if directory=='.' else directory+'/'
                result.append({'directory':directory,'name':report.get('profile',{}).get('name','Assemblage'),'url':'/api/projects/'+item['id']+'/assembly/'+quote(prefix)+'viewer.html'})
            except (OSError,ValueError,TypeError):continue
        return result
    def outputs(item):
        if not item['payload'].get('workspace'):return []
        root=delivery(item)
        if not root.is_dir():return []
        manufacturing={a['directory'] for a in assemblies(item)}
        return [{'name':p.relative_to(root).as_posix(),'url':'/api/projects/'+item['id']+'/files/'+quote(p.relative_to(root).as_posix())}
                for p in sorted(root.rglob('*.glb'))[:30] if p.is_file() and p.resolve().is_relative_to(root)
                and complete_glb(p) and p.parent.relative_to(root).as_posix() not in manufacturing]
    @bp.route('/api/projects',methods=['GET'])
    def projects():
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        items=[]
        for item in store.list(100):
            checkpoint=store.checkpoint(item['id']) or {};payload=item['payload']
            title=payload.get('project_title') or payload.get('request','')
            if 'OBJECTIF UTILISATEUR :\n' in title:title=title.split('OBJECTIF UTILISATEUR :\n',1)[1].split('\nCONTRAINTES FOURNIES',1)[0]
            did=(item.get('idem') or '').removeprefix('design:') if (item.get('idem') or '').startswith('design:') else None
            meshes=outputs(item) if mission_module(payload)=='3d' else []
            items.append({'id':item['id'],'design_id':did,'title':title[:160],'module':mission_module(payload),'assemblies':assemblies(item) if mission_module(payload)=='3d' else [],'meshes':meshes,'viewer_url':'/api/projects/'+item['id']+'/viewer/viewer.html' if meshes else None,'status':item['status'],'result':item.get('result'),'resumable':payload.get('project_kind')!='frontend' and item['status'] in {'failed','stopped','blocked','interrupted'},'created':item['created'],'started_at':item['started_at'],'finished_at':item['finished'],'steps':item['steps'],'criteria_count':len(checkpoint.get('criteria',[])),'verified_count':len(checkpoint.get('verified',[])),'scheduling':store.scheduling(item['id'])})
        return jsonify(ok=True,projects=items,concurrency=int(os.environ.get('AURORA_CONCURRENT_MISSIONS','1')),scope='Durable project admission; the pipeline executor retains its own outputs and checkpoints.')

    @bp.route('/api/projects/<mid>/resume',methods=['POST'])
    def resume_project(mid):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        item=store.get(mid)
        if not item:return jsonify(ok=False,error='Projet introuvable.'),404
        if item['payload'].get('project_kind')=='frontend':return jsonify(ok=False,error='Vérifier les résultats et le contrôleur PC de ce pipeline avant reprise.'),409
        try:item,_=store.resume(mid)
        except ValueError as e:return jsonify(ok=False,error=str(e)),409
        store.enqueue(mid)
        from application.engineering_design_api import publish
        publish('mission.start',{'mission_id':mid,**item['payload']})
        return jsonify(ok=True,id=mid,status=store.get(mid)['status']),202

    @bp.route('/api/projects/<mid>/files/<path:name>',methods=['GET'])
    def project_file(mid,name):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        item=store.get(mid)
        if not item or not item['payload'].get('workspace'):return jsonify(ok=False,error='Fichier introuvable.'),404
        root=delivery(item)
        path=(root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in {'.glb','.gltf','.bin','.png','.jpg','.jpeg','.webp','.stl','.zip','.md','.pdf','.json'}:return jsonify(ok=False,error='Fichier introuvable.'),404
        return send_file(path,conditional=True,max_age=0)

    @bp.route('/api/projects/<mid>/viewer/<path:name>',methods=['GET'])
    def project_viewer(mid,name):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        item=store.get(mid)
        if not item or not item['payload'].get('workspace'):return jsonify(ok=False,error='Projet introuvable.'),404
        base=Path(__file__).parent
        if name=='viewer.html':return send_file(base/'project_viewer.html',max_age=0)
        if name=='meshes.json':return jsonify(meshes=outputs(item),status=item['status'],title=(item['payload'].get('project_title') or item['payload'].get('request',''))[:500])
        if name.startswith('viewer_assets/'):
            assets=(base/'engineering_viewer_assets').resolve();path=(assets/name.removeprefix('viewer_assets/')).resolve()
            if path.is_relative_to(assets) and path.is_file():return send_file(path,max_age=3600)
        return jsonify(ok=False,error='Ressource introuvable.'),404

    @bp.route('/api/projects/<mid>/assembly/<path:name>',methods=['GET'])
    def project_assembly(mid,name):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        item=store.get(mid)
        if not item or not item['payload'].get('workspace'):return jsonify(ok=False,error='Projet introuvable.'),404
        base=Path(__file__).parent
        if 'viewer_assets/' in name:
            assets=(base/'engineering_viewer_assets').resolve();path=(assets/name.split('viewer_assets/',1)[1]).resolve()
            if path.is_relative_to(assets) and path.is_file():return send_file(path,max_age=3600)
            return jsonify(ok=False,error='Ressource introuvable.'),404
        root=delivery(item);path=(root/name).resolve()
        if not path.is_relative_to(root):return jsonify(ok=False,error='Ressource introuvable.'),404
        directory=path.parent.relative_to(root).as_posix()
        if not any(a['directory']=='.' or directory==a['directory'] or directory.startswith(a['directory']+'/') for a in assemblies(item)):return jsonify(ok=False,error='Assemblage indisponible.'),404
        if path.name=='viewer.html':return send_file(base/'engineering_viewer.html',max_age=0)
        if path.is_file() and path.suffix.lower() in {'.glb','.json','.stl','.png','.jpg','.webp'}:return send_file(path,conditional=True,max_age=0)
        return jsonify(ok=False,error='Ressource introuvable.'),404

    @bp.route('/api/projects/admission',methods=['POST'])
    def admit():
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        reconcile()
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,150}',str(data.get('request_id',''))) or data.get('module') not in {'conversation','image','code','video','drawing','3d','learning','cyber','voice'} or not isinstance(data.get('title'),str) or not 1<=len(data['title'])<=500:return jsonify(ok=False,error='Demande de calcul invalide.'),400
        payload={'project_kind':'frontend','request':data['title'],'project_title':data['title'],'module':data['module'],'model':str(data.get('model',''))[:200]}
        try:item,_=store.create(payload,'frontend:'+data['request_id'],queued=True)
        except ValueError as e:return jsonify(ok=False,error=str(e)),409
        return jsonify(ok=True,id=item['id'],status=item['status'],scheduling=store.scheduling(item['id']))

    @bp.route('/api/projects/<mid>/admission',methods=['POST'])
    def claim_admission(mid):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        reconcile()
        item=store.get(mid)
        if not item or item['payload'].get('project_kind')!='frontend':return jsonify(ok=False,error='Projet introuvable.'),404
        data=request.get_json(silent=True) or {}
        executor=data.get('executor') if isinstance(data,dict) else None
        if executor is not None and (not isinstance(executor,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,100}',executor)):return jsonify(ok=False,error='Exécutant invalide.'),400
        token='frontend-'+(hashlib.sha256(executor.encode()).hexdigest() if executor else mid)
        if item['owner']==token:
            store.renew(mid,token,90)
        elif item['status']=='queued':store.claim(mid,token,90,serialize=True)
        item=store.get(mid)
        return jsonify(ok=True,id=mid,status=item['status'],granted=item['owner']==token and item['status']=='running',scheduling=store.scheduling(mid))

    @bp.route('/api/projects/<mid>/finish',methods=['POST'])
    def finish_admission(mid):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        item=store.get(mid)
        if not item or item['payload'].get('project_kind')!='frontend':return jsonify(ok=False,error='Projet introuvable.'),404
        data=request.get_json(silent=True) or {}
        if not isinstance(data,dict) or data.get('status') not in {'completed','failed','stopped'}:return jsonify(ok=False,error='Résultat invalide.'),400
        executor=data.get('executor')
        if executor is not None and (not isinstance(executor,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,100}',executor)):return jsonify(ok=False,error='Exécutant invalide.'),400
        if item['status'] in {'completed','failed','stopped','blocked'}:
            if item['status']==data['status']:return jsonify(ok=True,status=item['status'])
            return jsonify(ok=False,error='Ce projet possède déjà un résultat final conservé.'),409
        token='frontend-'+(hashlib.sha256(executor.encode()).hexdigest() if isinstance(executor,str) else mid)
        if not item['owner'] or item['owner']!=token:return jsonify(ok=False,error='Ce calcul appartient à un autre exécutant ou n’a pas démarré. Ne pas le rejouer.'),409
        if data['status'] in {'stopped','failed'} and not work_idle():
            return jsonify(ok=False,error='Les processus terminent encore leur arrêt.',code='workers_stopping'),409
        store.append(mid,{'type':'error' if data['status']=='failed' else 'mission_complete','stopped':data['status']=='stopped','result':'Arrêt confirmé ; place libérée.' if data['status']=='stopped' else 'Le pipeline a terminé.' if data['status']=='completed' else 'Pipeline en erreur ; consulter ses preuves.'})
        return jsonify(ok=True,status=store.get(mid)['status'])

    @bp.route('/api/projects/<mid>/cancel',methods=['POST'])
    def cancel_queued(mid):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        if store.cancel_queued(mid):
            return jsonify(ok=True,status='stopped')
        data=request.get_json(silent=True) or {}
        item=store.get(mid)
        if isinstance(data,dict) and data.get('force') is True and item and item['payload'].get('project_kind')=='frontend' and item['status'] in {'running','planning','stopping'}:
            store.append(mid,{'type':'mission_complete','stopped':True,'result':'Arrêt immédiat demandé par l’utilisateur ; file libérée.'})
            return jsonify(ok=True,status='stopped')
        return jsonify(ok=False,error='Le projet a déjà démarré. Utilisez son module pour contrôler son arrêt.'),409

    @bp.route('/api/image/persist',methods=['POST'])
    def persist_image():
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        data=request.get_json(silent=True) or {}
        if not isinstance(data,dict):return jsonify(ok=False,error='Requête invalide.'),400
        raw_filename=Path(str(data.get('filename',''))).name
        data_url=str(data.get('data_url','')).strip()
        if not raw_filename and data_url.startswith('data:image/'):
            raw_filename='creation.png'
        if not raw_filename or not raw_filename.lower().endswith(('.png','.jpg','.jpeg','.webp')):
            return jsonify(ok=False,error='Nom de fichier image invalide.'),400
        mode_raw=str(data.get('mode','creation')).strip().lower()
        is_mod=bool(data.get('is_modification')) or (mode_raw not in {'','creation','new','text2img'})
        folder_name='modifications' if is_mod else 'creations'
        prompt_text=str(data.get('prompt','')).strip()
        slug=re.sub(r'[^a-z0-9]+','_',prompt_text.lower()).strip('_')[:42] or ('modification' if is_mod else 'creation')
        ts_str=time.strftime('%Y-%m-%d_%H%M%S')
        app_root=Path(__file__).resolve().parent
        target_dir=(app_root/'output'/'image'/folder_name).resolve()
        target_dir.mkdir(parents=True,exist_ok=True)
        dest_name=f'{ts_str}_{slug}{Path(raw_filename).suffix.lower()}'
        dest_path=target_dir/dest_name
        # Cherche le fichier produit par ComfyUI (disque local, data_url ou API /view)
        candidates=[
            app_root.parent/'modele'/'comfyui'/'comfyui'/'output'/raw_filename,
            app_root.parent/'modele'/'comfyui'/'output'/raw_filename,
            Path('/workspace/comfyui/output')/raw_filename,
            Path('/workspace/ComfyUI/output')/raw_filename,
        ]
        copied=False
        for cand in candidates:
            try:
                if cand.is_file():
                    import shutil
                    shutil.copy2(cand,dest_path)
                    copied=True
                    break
            except OSError:
                pass
        if not copied and data_url.startswith('data:image/') and ',' in data_url:
            try:
                import base64
                dest_path.write_bytes(base64.b64decode(data_url.split(',',1)[1]))
                copied=True
            except Exception:
                pass
        if not copied:
            try:
                import urllib.request
                comfy_url=os.environ.get('COMFYUI_URL','http://127.0.0.1:8188').rstrip('/')
                with urllib.request.urlopen(f'{comfy_url}/view?filename={quote(raw_filename)}&type=output',timeout=8) as resp:
                    if resp.status==200:
                        dest_path.write_bytes(resp.read())
                        copied=True
            except Exception:
                pass
        if copied:
            try:
                meta_path=dest_path.with_suffix('.json')
                meta_path.write_text(json.dumps({
                    'filename':dest_name,
                    'source_filename':raw_filename,
                    'prompt':prompt_text,
                    'mode':mode_raw or 'creation',
                    'folder':folder_name,
                    'is_modification':is_mod,
                    'session_id':str(data.get('sessionId','general')),
                    'context':str(data.get('context','ui')),
                    'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                },ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError:
                pass
        saved_rel=f'output/image/{folder_name}/{dest_name}' if copied else f'output/image/{folder_name}/'
        return jsonify(ok=True,copied=copied,folder=folder_name,saved_rel=saved_rel,saved_path=str(dest_path) if copied else None)

