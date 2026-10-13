"""Objective-driven engineering missions using Aurora's durable tool agent."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import sys
import threading
import zipfile
import struct
from flask import jsonify, request, send_file
from agi_core.mission_store import MissionStore
from application.device_pairing import request_identity,device_auth

CONTRACT = '''Tu es chargé de concevoir ce projet à partir de son objectif, pas de choisir un exemple prédéfini.
Décompose les fonctions, interfaces, éléments fixes/mobiles, transmissions, énergie, signal, accès de montage, fabrication et maintenance selon les besoins réels du projet.
L'utilisateur peut imposer des composants. Respecte leurs fiches techniques, leurs dimensions et leurs limites ; cherche des sources primaires si nécessaire. Sinon, propose toi-même les composants, fixations, fils/câbles et matières nécessaires, avec quantités et spécifications utiles (diamètre, longueur, tension, courant, couple, section, tolérance, etc. uniquement lorsque pertinent).
Procède avec des hypothèses explicites raisonnables plutôt que demander chaque choix. Si une inconnue rend une conclusion impossible ou un objectif techniquement irréalisable, démontre le blocage et propose une alternative compatible, sans prétendre avoir fabriqué une solution impossible.
Utilise les outils : établis un plan et des critères mesurables, produis du code paramétrique, exécute des calculs et des tests adaptés, consulte les preuves et corrige les défauts. Ne confonds pas un calcul à paramètres supposés et une mesure réelle ; aucune certification mécanique, électrique ou ajustement imprimé ne peut être inventée.
Pour les mécanismes, renseigner mechanism_joints : id, parent/child (IDs des pièces), kind fixed/revolute/prismatic/helical, axis et origin_mm dans le repère mondial au repos, limits et home (degrés ou mm), pitch_mm pour une vis hélicoïdale. Pour une articulation à plusieurs degrés, utiliser kind compound avec coordinates ordonnées : chaque coordonnée a id, kind revolute/prismatic/helical, axis, origin_mm, limits, home, passive si nécessaire. Le produit ordonné des transformations calcule une rotule, un plan ou une liaison spatiale selon les axes effectivement fournis, sans pièces virtuelles imprimables ni animation prédéfinie. Les commandes utilisent joint_id:coordinate_id. Ne pas inventer de mobilité pour des fixations statiques. Une boucle fermée peut être représentée par un arbre de joints et closure_constraints (liste) : kind coincident ou distance, parent/child, parent_anchor_mm et child_anchor_mm dans les repères locaux des STL sources, distance_mm si pertinent. Déclarer passive=true sur les articulations résolues et tester convergence, singularités, branches et limites ; une absence de convergence ne prouve pas une impossibilité physique. Les efforts, câbles flexibles et déformations demandent des données et un solveur adaptés.
Livrables : design.py reproductible, tests.py exécuté (peut appeler des scripts supplémentaires), pièces STL fermées en mm, placements rigides, project_spec.json, archive engineering-project.zip avec dossier de montage (MD et HTML imprimable PDF), nomenclature, représentation des géométries et viewer.
Produis réellement les maillages (sommets/faces, par exemple avec trimesh/manifold installés) et exporte les STL sur disque. Une description JSON de primitive, un dictionnaire de cotes ou un message de succès ne constitue jamais une pièce. Les tests doivent charger et mesurer les fichiers réellement exportés, pas tester seulement des valeurs recopiées.
La bibliothèque fabrication.py est un module Python local, pas un outil agent. Pour créer les scripts, utilise les outils réels write_file et run_command avec le Python indiqué ; consulte list_tools si tu ignores un outil, n'invente pas de nom d'outil. Elle est disponible pour vérifier et empaqueter les pièces réellement produites. spec peut être un dictionnaire Python ou le chemin local project_spec.json. Utilise build_project(spec, '.') pour produire le dossier et l'archive. Corrige les pièces qui ne tiennent pas dans l'imprimante (orientation ou découpe), ne remplace pas le profil fourni. Des exigences irréalisables peuvent produire un dossier de faisabilité avec blockers et aucune pièce.
La forme de spec est : units='mm', title, objective, bed_mm, margin_mm, printer_name, constraints (liste texte), assumptions (liste texte), blockers (liste texte), parts (liste de {id,name,file STL local,assembly_matrix_mm matrice rigide 4x4,color_rgba pour le repérage,manufacturing print ou purchased,geometry_basis manufacturer_cad/measured/assumed_envelope et source_reference obligatoires pour un composant acheté,filament et filament_color=#RRGGBB facultatifs pour la matière/couleur physique}), bom (liste de {name,quantity entier,specification texte détaillé,part_ids}), assembly_steps (liste de {instruction,part_ids}), tests (liste avec résultats et fichiers de preuves), sources (liste).
La validité automatique de la bibliothèque porte sur les solides, leurs dimensions et références ; elle ne vérifie pas les promesses de résistance ni de comportement. Teste indépendamment les contraintes propres au projet. Les composants achetés avec enveloppe CAD participent aux collisions et à la vue d’assemblage, mais sont exclus des plaques et des contraintes de taille de l’imprimante ; les référencer dans bom. Les enveloppes supposées sont des hypothèses, jamais une mesure validée. N'ajoute pas systématiquement un moteur, un capteur ou un câble à un projet qui n'en a pas besoin. Si plusieurs couleurs sont souhaitées sur une imprimante monocolore, conçois des pièces séparées par couleur et des interfaces de montage justifiées, sans supposer une impression multicolore en un seul bloc.
N'utilise pas de services payants, ne contacte personne, ne publie rien, ne lis aucune clé, ne modifie aucun autre projet et n'installe pas de logiciels système. Travail limité à ce dossier. Les prérequis nécessaires doivent être identifiés comme tels si absents.
Les helpers engineering_motion.simulate, path_sample et evaluate_motion_case(report, root, from_values, to_values, start_sample=0, sample_batch=32) permettent des essais géométriques et des trajectoires échantillonnées ; evaluate_motion_case fournit une couverture reprenable par lots : poursuivre next_sample jusqu’à complete en transmettant continuation_values au lot suivant pour initialiser les coordonnées passives depuis la position résolue précédente, agréger toutes les erreurs et vérifier la couverture avant toute approbation ; enregistrer les valeurs, résidus et collisions réellement calculés dans un JSON de preuve. Pour comparer les emplacements de fixations, engineering_connections.rank_fastening_locations(parts, root, candidates, views) calcule l’occlusion sur les STL : candidates={id,kind screw/glue/clip/insert/interlock,part_ids,surface_samples_mm en coordonnées assemblage,tool_envelope_file optionnel STL en coordonnées assemblage}, views={direction vers l’observateur,weight}. Comparer de vraies positions et enveloppes d’accès, puis produire les logements retenus dans le CAD ; aucune résistance ne découle de ce classement. Ces modules Python sont importables depuis le dossier de fabrication.
Le contrôle engineering_insertion.evaluate_insertion(report, root, part_id, translation_mm=None, direction_index=0) vérifie tout le trajet d’une translation rigide contre les autres STL au repos, avec enveloppe balayée conservatrice et empreintes des géométries. Le script engineering_insertion_path.py --manifest project.json --part ID --output insertion-proof.json compare les directions issues des surfaces réelles et choisit le plus court trajet vérifié parmi celles testées. L’intersection d’une enveloppe non convexe est indéterminée, pas une impossibilité : affiner la décomposition, modifier l’ordre de montage ou rechercher une trajectoire avec rotations. Inclure la preuve dans les livrables et conserver les blocages d’ajustement, d’accès, de matériaux et d’efforts tant qu’ils ne sont pas vérifiés.
Pour les fixations, comparer des alternatives pertinentes (colle, vis cachées, inserts, clips, emboîtements selon le projet). Privilégier lignes naturelles, dessous, intérieur ou surfaces peu visibles, sans sacrifier résistance, accès de l’outil, démontage requis, épaisseur des parois et tolérances. Justifier le choix avec géométrie, fiches techniques et tests ; ne pas déclarer une résistance d’adhésif sans surface, matière et données. Réserver les passages et dégagements de vis, câbles et pièces mobiles.
Après une défaillance, conserver erreur et preuves, formuler une hypothèse, faire un essai discriminant, modifier la cause puis rejouer les mêmes critères. Réviser la méthode ou déléguer des sous-ensembles si nécessaire ; ne pas abandonner un projet à cause de sa catégorie ni remplacer une vraie preuve par un message de succès.
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
        if device:return device['workspace_owner']
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
        folder=(root/rec['id']).resolve();archive=folder/'engineering-project.zip';report_path=folder/'project.json'
        complete=False; report=None
        if item['status'] in {'completed','failed','stopped','blocked','interrupted'}:
            try:
                report=json.loads(report_path.read_text(encoding='utf-8'))
                parts=report.get('parts',[])
                if not isinstance(report.get('bom',[]),list) or any(not isinstance(entry,dict) for entry in report.get('bom',[])):raise ValueError('BOM schema')
                if report.get('schema')!='aurora.engineering-project.v1' or not isinstance(parts,list) or len(parts)>int(os.environ.get('AURORA_ENGINEERING_MAX_PARTS','512')):raise ValueError('schema')
                paths=[archive,report_path,folder/'DOSSIER.md',folder/'DOSSIER.html',folder/'representation.svg']
                for part in parts:
                    path=(folder/part['file']).resolve()
                    if not path.is_relative_to(folder.resolve()):raise ValueError('part path')
                    paths.append(path)
                if parts:paths.extend([folder/'design.py',folder/'tests.py',folder/'project_spec.json'])
                signature=tuple((str(p),p.stat().st_size,p.stat().st_mtime_ns) for p in paths)
                if verified.get(rec['id'])!=signature:
                    import numpy as np
                    import trimesh
                    with zipfile.ZipFile(archive) as bundle:
                        required={'DOSSIER.md','DOSSIER.html','representation.svg','project.json'}
                        if not required.issubset(bundle.namelist()) or bundle.testzip():raise ValueError('archive')
                        if json.loads(bundle.read('project.json'))!=report:raise ValueError('manifest')
                        if not parts and not report.get('blockers'):raise ValueError('empty')
                        if report.get('units')!='mm' or report.get('physical_fit_validated') is not False:raise ValueError('unsupported validation')
                        profile=rec.get('profile',{})
                        bed=np.asarray(profile.get('bed_mm',[220,220,250]),dtype=float)
                        usable=bed-2*profile.get('margin_mm',5)
                        if parts and not {'design.py','tests.py','project_spec.json'}.issubset(bundle.namelist()):raise ValueError('reproducibility')
                        for path in paths[2:]:
                            name=path.relative_to(folder.resolve()).as_posix() if path.is_absolute() else path.relative_to(folder).as_posix()
                            if name not in bundle.namelist() or bundle.read(name)!=path.read_bytes():raise ValueError('changed dossier or source')
                        for part in parts:
                            role=part.get('manufacturing','print')
                            if role not in {'print','purchased'}:raise ValueError('manufacturing role')
                            if role=='purchased' and (part.get('geometry_basis') not in {'manufacturer_cad','measured','assumed_envelope'} or not isinstance(part.get('source_reference'),str) or not part['source_reference'].strip() or not any(part.get('design_id') in entry.get('part_ids',[]) for entry in report.get('bom',[]))):raise ValueError('purchased component provenance')
                            path=(folder/part['file']).resolve()
                            if part['file'] not in bundle.namelist() or bundle.read(part['file'])!=path.read_bytes():raise ValueError('changed part')
                            mesh=trimesh.load_mesh(path)
                            if not mesh.is_volume or not np.isfinite(mesh.vertices).all() or not np.allclose(mesh.extents,part['dimensions_mm'],atol=1e-4) or (part.get('manufacturing','print')=='print' and np.any(mesh.extents>usable+1e-4)) or not np.isclose(mesh.volume,part['volume_mm3'],rtol=1e-4):raise ValueError('actual geometry')
                            matrix=np.asarray(part['assembly_matrix_mm'],dtype=float)
                            if matrix.shape!=(4,4) or not np.isfinite(matrix).all() or not np.allclose(matrix[3],[0,0,0,1]) or not np.allclose(matrix[:3,:3].T@matrix[:3,:3],np.eye(3),atol=1e-6) or not np.isclose(np.linalg.det(matrix[:3,:3]),1):raise ValueError('rigid placement')
                    from application.engineering_motion import validate_joints,solve_closures,coordinates
                    joints=validate_joints(parts,report.get('mechanism_joints',[]))
                    _,homes,closure=solve_closures(parts,joints,{},report.get('closure_constraints',[]))
                    if not closure['converged'] or any(abs(homes.get(j['id'],j['home'])-j['home'])>1e-4 for j in coordinates(joints)):raise ValueError('rest mechanism coherence')
                    verified[rec['id']]=signature
                complete=True
            except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile):pass
        result={'ok':True,'id':rec['id'],'mission_id':item['id'],'state':item['status'],'objective':rec.get('objective',''),'request_id':rec.get('request_id',''),'result':item.get('result',''),'steps':item['steps'],'errors':item['errors'],'scheduling':store.scheduling(item['id']),'ready':complete and item['status']=='completed','artifacts_available':complete,'partial':complete and item['status']!='completed'}
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
        fingerprint_data={k:data.get(k) for k in ['objective','constraints','profile']}
        source=data.get('source')
        if source is not None:
            if not isinstance(source,dict) or not re.fullmatch(r'mis_[a-f0-9]{16}',str(source.get('mission_id',''))) or not isinstance(source.get('file'),str):return jsonify(ok=False,error='Référence au modèle source invalide.'),400
            fingerprint_data['source']={k:source[k] for k in ['mission_id','file']}
        fingerprint=hashlib.sha256(json.dumps(fingerprint_data,sort_keys=True).encode()).hexdigest()
        with lock:
            old=receipt(did)
            if old:
                if old.get('fingerprint')!=fingerprint:return jsonify(ok=False,error='Cette demande a déjà été utilisée pour un autre objectif.'),409
                return jsonify(response(old)),200
            source_bytes=None
            if source is not None:
                parent=store.get(source['mission_id'])
                if not parent or not parent['payload'].get('workspace'):return jsonify(ok=False,error='Projet source introuvable.'),404
                delivery=(Path(parent['payload']['workspace'])/'.transfer_to_client'/parent['id']).resolve()
                file=(delivery/source['file']).resolve()
                if not file.is_relative_to(delivery) or file.suffix.lower()!='.glb' or not file.is_file() or file.stat().st_size>120*1024*1024:return jsonify(ok=False,error='Maillage source indisponible ou hors du dossier du projet.'),400
                source_bytes=file.read_bytes()
                if len(source_bytes)<28:return jsonify(ok=False,error='Maillage source encore incomplet.'),409
                magic,version,size=struct.unpack('<4sII',source_bytes[:12])
                if magic!=b'glTF' or version!=2 or size!=len(source_bytes):return jsonify(ok=False,error='Maillage source encore incomplet ou invalide.'),409
            try:model=model_default()
            except ValueError as e:return jsonify(ok=False,error=str(e)),503
            folder=root/did;folder.mkdir(parents=True,exist_ok=True)
            source_note=''
            if source_bytes is not None:
                (folder/'source.glb').write_bytes(source_bytes)
                source_note='\nMODÈLE SOURCE IMMUTABLE : source.glb, SHA256 '+hashlib.sha256(source_bytes).hexdigest()+'. Préserver sa silhouette et son apparence ; ce modèle doit être utilisé, pas remplacé par des primitives. Inspecter les couleurs et régions réelles. engineering_color_parts.py peut dériver des inserts fermés depuis une palette mesurée ; vérifier ensuite épaisseurs locales, jeux, trajectoires d’insertion et fixation. Inclure source.glb et les preuves dans source_assets du dossier final. Choisir la taille physique selon les contraintes et le profil, et documenter cette décision.'
            repo=Path(__file__).resolve().parents[1]
            seed='import sys\nsys.path.insert(0, '+repr(str(repo))+')\nfrom application.engineering_project import build_project as _build_project\ndef build_project(spec, root="."):\n    return _build_project(spec, root, require_sources=True)\n'
            (folder/'fabrication.py').write_text(seed,encoding='utf-8')
            (folder/'OBJECTIF.json').write_text(json.dumps({'objective':data['objective'],'constraints':constraints,'profile':profile},ensure_ascii=False,indent=2),encoding='utf-8')
            text=CONTRACT+'\nOBJECTIF UTILISATEUR :\n'+data['objective']+'\nCONTRAINTES FOURNIES :\n'+(constraints or 'Aucune pièce imposée : déterminer les éléments nécessaires.')+'\nPROFIL IMPRIMANTE :\n'+json.dumps(profile,ensure_ascii=False)+source_note+'\nPython disponible pour géométrie et tests : '+sys.executable+'\nDossier de travail : '+str(folder)
            payload={'request':text,'workspace':str(folder),'permissions':'AUTONOMOUS','model':model,'requested_model':'','session_id':'','history':[],'context_tokens':8192,'project_kind':'engineering','project_title':data['objective'][:160]}
            item,created=store.create(payload,'design:'+did,queued=True)
            rec={'id':did,'owner':owner(),'mission_id':item['id'],'fingerprint':fingerprint,'profile':profile,'objective':data['objective'],'request_id':request_id}
            path=private/(did+'.json');path.write_text(json.dumps(rec));path.chmod(0o600)
            if created:dispatch('mission.start',{'mission_id':item['id'],**payload})
            return jsonify(response(rec)),202
    @bp.route('/api/3d/design/<did>',methods=['GET'])
    def status_design(did):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        rec=receipt(did)
        return (jsonify(response(rec)),200) if rec else (jsonify(ok=False,error='Projet introuvable.'),404)
    @bp.route('/api/3d/design/<did>/simulate',methods=['POST'])
    def simulate_design(did):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        rec=receipt(did)
        if not rec or not response(rec).get('artifacts_available'):return jsonify(ok=False,error='Géométrie vérifiée indisponible.'),404
        from application.engineering_motion import simulate,path_sample
        try:
            report=json.loads((root/did/'project.json').read_text(encoding='utf-8'))
            data=request.get_json(silent=True)
            if not isinstance(data,dict):raise ValueError('Objet de paramètres requis.')
            path=data.get('path');values=data.get('values',{});metadata=None
            if path is not None:
                if not isinstance(path,dict):raise ValueError('Trajet invalide.')
                values,metadata=path_sample(report['parts'],report.get('mechanism_joints',[]),path.get('from',{}),path.get('to',{}),path.get('sample',0),seed=path.get('seed'))
            result=simulate(report,root/did,values,cursor=data.get('cursor',0))
            if metadata:result['path']=metadata
            return jsonify(result)
        except (ValueError,TypeError,KeyError) as exc:return jsonify(ok=False,error=str(exc)),400
    @bp.route('/api/3d/design/<did>/insertion',methods=['POST'])
    def insertion_design(did):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        rec=receipt(did)
        if not rec or not response(rec).get('artifacts_available'):return jsonify(ok=False,error='Géométrie vérifiée indisponible.'),404
        from application.engineering_insertion import verify_translation
        try:
            report=json.loads((root/did/'project.json').read_text(encoding='utf-8'))
            data=request.get_json(silent=True)
            if not isinstance(data,dict):raise ValueError('Objet de paramètres requis.')
            result=verify_translation(report,root/did,data.get('part_id'),data.get('translation_mm'),
                                      direction_index=data.get('direction_index',0),cursor=data.get('cursor',0))
            return jsonify(result)
        except (OSError,ValueError,TypeError,KeyError) as exc:return jsonify(ok=False,error=str(exc)),400
    @bp.route('/api/3d/design/<did>/resume',methods=['POST'])
    def resume_design(did):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        rec=receipt(did)
        if not rec:return jsonify(ok=False,error='Projet introuvable.'),404
        try:item,_cursor=store.resume(rec['mission_id'])
        except ValueError as e:return jsonify(ok=False,error=str(e)),409
        store.enqueue(item['id'])
        if not dispatch('mission.start',{'mission_id':item['id'],**item['payload']}):
            return jsonify(response(rec)),202
        return jsonify(response(rec))

    @bp.route('/api/3d/design/<did>/stop',methods=['POST'])
    def stop_design(did):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        rec=receipt(did)
        if not rec:return jsonify(ok=False,error='Projet introuvable.'),404
        item = store.get(rec['mission_id'])
        if not item: return jsonify(ok=False,error='Mission introuvable.'),404
        if item['status'] in {'completed','failed','stopped','blocked'}: return jsonify(ok=True,status=item['status'])
        if item['status']=='interrupted' or item['owner'] is None:
            store.append(item['id'],{'type':'mission_complete','stopped':True,'result':'Interrupted mission stopped; checkpoint retained'})
            dispatch('mission.stop',{'mission_id':item['id']})
            return jsonify(ok=True,status='stopped')
        store.stop_requested(item['id'])
        delivered = dispatch('mission.stop',{'mission_id':item['id']})
        return jsonify(ok=True,status='stopping',signal_delivered=delivered),202

    @bp.route('/api/3d/design/<did>/delete',methods=['POST'])
    def delete_design(did):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        rec=receipt(did)
        if not rec:return jsonify(ok=False,error='Projet introuvable.'),404
        item = store.get(rec['mission_id'])
        if not item: return jsonify(ok=False,error='Mission introuvable.'),404
        if item['status'] == 'queued':
            store.cancel_queued(item['id'])
        # Also clean up receipt file
        path = private / (did + '.json')
        if path.exists():
            path.unlink()
        return jsonify(ok=True)

    @bp.route('/api/3d/design/<did>/download',methods=['GET'])
    @bp.route('/api/3d/design/<did>/dossier',methods=['GET'])
    def file_design(did):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        rec=receipt(did)
        if not rec or not response(rec).get('artifacts_available'):return jsonify(ok=False,error='Dossier pas encore livré.'),404
        name='DOSSIER.html' if request.path.endswith('/dossier') else 'engineering-project.zip'
        return send_file(root/did/name,as_attachment=name.endswith('.zip'),max_age=0)
