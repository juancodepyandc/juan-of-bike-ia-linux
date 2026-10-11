"""Objective-driven engineering missions using Aurora's durable tool agent."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re
import socket
import sys
import threading
import zipfile
from flask import jsonify, request, send_file
from agi_core.mission_store import MissionStore
from application.device_pairing import request_identity,device_auth

CONTRACT = '''Tu es chargé de concevoir ce projet à partir de son objectif, pas de choisir un exemple prédéfini.
Décompose les fonctions, interfaces, éléments fixes/mobiles, transmissions, énergie, signal, accès de montage, fabrication et maintenance selon les besoins réels du projet.
L'utilisateur peut imposer des composants. Respecte leurs fiches techniques, leurs dimensions et leurs limites ; cherche des sources primaires si nécessaire. Sinon, propose toi-même les composants, fixations, fils/câbles et matières nécessaires, avec quantités et spécifications utiles (diamètre, longueur, tension, courant, couple, section, tolérance, etc. uniquement lorsque pertinent).
Procède avec des hypothèses explicites raisonnables plutôt que demander chaque choix. Si une inconnue rend une conclusion impossible ou un objectif techniquement irréalisable, démontre le blocage et propose une alternative compatible, sans prétendre avoir fabriqué une solution impossible.
Utilise les outils : établis un plan et des critères mesurables, produis du code paramétrique, exécute des calculs et des tests adaptés, consulte les preuves et corrige les défauts. Ne confonds pas un calcul à paramètres supposés et une mesure réelle ; aucune certification mécanique, électrique ou ajustement imprimé ne peut être inventée.
Livrables : design.py reproductible, tests.py ou scripts équivalents exécutés, pièces STL fermées en mm, placements rigides, project_spec.json, archive engineering-project.zip avec dossier de montage (MD et HTML imprimable PDF), nomenclature, représentation des géométries et viewer.
La bibliothèque fabrication.py est disponible pour vérifier et empaqueter les pièces réellement produites. Utilise build_project(spec, '.') pour produire le dossier et l'archive. Corrige les pièces qui ne tiennent pas dans l'imprimante (orientation ou découpe), ne remplace pas le profil fourni. Des exigences irréalisables peuvent produire un dossier de faisabilité avec blockers et aucune pièce.
La forme de spec est : units='mm', title, objective, bed_mm, margin_mm, printer_name, constraints (liste texte), assumptions (liste texte), blockers (liste texte), parts (liste de {id,name,file STL local,assembly_matrix_mm matrice rigide 4x4,color_rgba}), bom (liste de {name,quantity entier,specification texte détaillé,part_ids}), assembly_steps (liste de {instruction,part_ids}), tests (liste avec résultats et fichiers de preuves), sources (liste).
La validité automatique de la bibliothèque porte sur les solides, leurs dimensions et références ; elle ne vérifie pas les promesses de résistance ni de comportement. Teste indépendamment les contraintes propres au projet. N'ajoute pas systématiquement un moteur, un capteur ou un câble à un projet qui n'en a pas besoin.
N'utilise pas de services payants, ne contacte personne, ne publie rien, ne lis aucune clé, ne modifie aucun autre projet et n'installe pas de logiciels système. Travail limité à ce dossier. Les prérequis nécessaires doivent être identifiés comme tels si absents.
Vérifie les octets de l'archive et les critères avant de conclure ; indique les limites techniques restantes.
'''


def publish(event,payload):
    try:
        with socket.create_connection(('127.0.0.1',3002),timeout=2) as conn:
            conn.sendall((json.dumps({'action':'publish','event_type':event,'payload':payload})+'\n').encode())
        return True
    except OSError:return False


def register_design_routes(bp,workspace,*,local,extension,model_default,store=None,dispatch=publish):
    store=store or MissionStore()
    root=Path(workspace)/'output'/'engineering-design'
    private=Path(workspace)/'.aurora'/'engineering-design';private.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=threading.Lock()
    verified={}
    def owner():
        device=device_auth(workspace)
        if device and not request.headers.get('Authorization'):return device['workspace_owner']
        identity=request_identity(workspace) or 'local-workspace'
        return hashlib.sha256(identity.encode()).hexdigest()
    def allowed():return local() or extension()[0]
    def receipt(did):
        if not re.fullmatch(r'design_[0-9a-f]{32}',did):return None
        try:
            rec=json.loads((private/(did+'.json')).read_text())
            return rec if rec['owner']==owner() else None
        except (OSError,ValueError,KeyError,TypeError):return None
    def response(rec):
        item=store.get(rec['mission_id'])
        if not item:return {'ok':False,'error':'Mission introuvable.'}
        folder=root/rec['id'];archive=folder/'engineering-project.zip';report_path=folder/'project.json'
        complete=False; report=None
        if item['status']=='completed':
            try:
                report=json.loads(report_path.read_text())
                parts=report.get('parts',[])
                if report.get('schema')!='aurora.engineering-project.v1' or not isinstance(parts,list) or len(parts)>64:raise ValueError('schema')
                paths=[archive,report_path,folder/'DOSSIER.md',folder/'DOSSIER.html',folder/'representation.svg']
                for part in parts:
                    path=(folder/part['file']).resolve()
                    if not path.is_relative_to(folder.resolve()):raise ValueError('part path')
                    paths.append(path)
                signature=tuple((str(p),p.stat().st_size,p.stat().st_mtime_ns) for p in paths)
                if verified.get(rec['id'])!=signature:
                    import numpy as np
                    import trimesh
                    with zipfile.ZipFile(archive) as bundle:
                        required={'DOSSIER.md','DOSSIER.html','representation.svg','project.json'}
                        if not required.issubset(bundle.namelist()) or bundle.testzip():raise ValueError('archive')
                        if json.loads(bundle.read('project.json'))!=report:raise ValueError('manifest')
                        if not parts and not report.get('blockers'):raise ValueError('empty')
                        for part in parts:
                            path=(folder/part['file']).resolve()
                            if part['file'] not in bundle.namelist() or bundle.read(part['file'])!=path.read_bytes():raise ValueError('changed part')
                            mesh=trimesh.load_mesh(path)
                            if not mesh.is_volume or not np.isfinite(mesh.vertices).all() or not np.allclose(mesh.extents,part['dimensions_mm'],atol=1e-4):raise ValueError('actual geometry')
                    verified[rec['id']]=signature
                complete=True
            except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile):pass
        result={'ok':True,'id':rec['id'],'mission_id':item['id'],'state':item['status'],'result':item.get('result',''),'steps':item['steps'],'errors':item['errors'],'ready':complete}
        if item['status']=='completed' and not complete:result.update(state='incomplete',error='Le dossier vérifiable manque. Consulter le résultat et reprendre la mission.')
        if complete:
            result['report']=report
            result['download_url']=f"/api/3d/design/{rec['id']}/download"
            result['dossier_url']=f"/api/3d/design/{rec['id']}/dossier"
            if (folder/'viewer.html').is_file(): result['viewer_url']=f"/api/asset/output/engineering-design/{rec['id']}/viewer.html"
        return result
    @bp.route('/api/3d/design',methods=['GET'])
    def list_designs():
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        items=[]
        for path in sorted(private.glob('design_*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]:
            rec=receipt(path.stem)
            if rec:items.append(response(rec))
        return jsonify(ok=True,projects=items[:30])
    @bp.route('/api/3d/design',methods=['POST'])
    def start_design():
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or not isinstance(data.get('objective'),str) or not 1<=len(data['objective'].strip())<=12000:return jsonify(ok=False,error='Décrivez l’objectif du projet (12 000 caractères maximum).'),400
        request_id=data.get('request_id','')
        if not isinstance(request_id,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}',request_id):return jsonify(ok=False,error='Identifiant de demande requis.'),400
        constraints=data.get('constraints','')
        if not isinstance(constraints,str) or len(constraints)>12000:return jsonify(ok=False,error='Contraintes texte invalides.'),400
        profile=data.get('profile',{})
        if not isinstance(profile,dict):return jsonify(ok=False,error='Profil imprimante invalide.'),400
        if 'bed_mm' in profile:
            bed=profile['bed_mm'];margin=profile.get('margin_mm',5)
            if not isinstance(bed,list) or len(bed)!=3 or any(type(v) not in {int,float} or not math.isfinite(v) or not 10<=v<=2000 for v in bed) or type(margin) not in {int,float} or not math.isfinite(margin) or margin<0 or 2*margin>=min(bed):
                return jsonify(ok=False,error='Volume utile ou marge imprimante invalide.'),400
        did='design_'+hashlib.sha256((owner()+':'+request_id).encode()).hexdigest()[:32]
        fingerprint=hashlib.sha256(json.dumps({k:data.get(k) for k in ['objective','constraints','profile']},sort_keys=True).encode()).hexdigest()
        with lock:
            old=receipt(did)
            if old:
                if old.get('fingerprint')!=fingerprint:return jsonify(ok=False,error='Cette demande a déjà été utilisée pour un autre objectif.'),409
                return jsonify(response(old)),200
            # One active engineering mission per owner protects resources without replay.
            for path in private.glob('design_*.json'):
                try:
                    previous=json.loads(path.read_text());item=store.get(previous['mission_id'])
                    if previous['owner']==owner() and item and item['status'] in {'planning','running','stopping'}:
                        return jsonify(ok=False,error='Un projet est déjà en cours.',id=previous['id']),409
                except (OSError,ValueError,KeyError):pass
            try:model=model_default()
            except ValueError as e:return jsonify(ok=False,error=str(e)),503
            folder=root/did;folder.mkdir(parents=True,exist_ok=True)
            repo=Path(__file__).resolve().parents[1]
            seed='import sys\nsys.path.insert(0, '+repr(str(repo))+')\nfrom application.engineering_project import build_project\n'
            (folder/'fabrication.py').write_text(seed,encoding='utf-8')
            (folder/'OBJECTIF.json').write_text(json.dumps({'objective':data['objective'],'constraints':constraints,'profile':profile},ensure_ascii=False,indent=2),encoding='utf-8')
            text=CONTRACT+'\nOBJECTIF UTILISATEUR :\n'+data['objective']+'\nCONTRAINTES FOURNIES :\n'+(constraints or 'Aucune pièce imposée : déterminer les éléments nécessaires.')+'\nPROFIL IMPRIMANTE :\n'+json.dumps(profile,ensure_ascii=False)+'\nPython disponible pour géométrie et tests : '+sys.executable+'\nDossier de travail : '+str(folder)
            payload={'request':text,'workspace':str(folder),'permissions':'AUTONOMOUS','model':model,'requested_model':'','session_id':'','history':[]}
            item,created=store.create(payload,'design:'+did)
            rec={'id':did,'owner':owner(),'mission_id':item['id'],'fingerprint':fingerprint}
            path=private/(did+'.json');path.write_text(json.dumps(rec));path.chmod(0o600)
            if created and not dispatch('mission.start',{'mission_id':item['id'],**payload}):store.append(item['id'],{'type':'error','message':'Daemon indisponible ; demande conservée pour reprise explicite.'})
            return jsonify(response(rec)),202
    @bp.route('/api/3d/design/<did>',methods=['GET'])
    def status_design(did):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        rec=receipt(did)
        return (jsonify(response(rec)),200) if rec else (jsonify(ok=False,error='Projet introuvable.'),404)
    @bp.route('/api/3d/design/<did>/resume',methods=['POST'])
    def resume_design(did):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        rec=receipt(did)
        if not rec:return jsonify(ok=False,error='Projet introuvable.'),404
        try:item,_cursor=store.resume(rec['mission_id'])
        except ValueError as e:return jsonify(ok=False,error=str(e)),409
        if not dispatch('mission.start',{'mission_id':item['id'],**item['payload']}):return jsonify(ok=False,error='Daemon indisponible. La demande reste conservée.'),503
        return jsonify(response(rec))
    @bp.route('/api/3d/design/<did>/download',methods=['GET'])
    @bp.route('/api/3d/design/<did>/dossier',methods=['GET'])
    def file_design(did):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        rec=receipt(did)
        if not rec or not response(rec).get('ready'):return jsonify(ok=False,error='Dossier pas encore livré.'),404
        name='DOSSIER.html' if request.path.endswith('/dossier') else 'engineering-project.zip'
        return send_file(root/did/name,as_attachment=name.endswith('.zip'),max_age=0)
