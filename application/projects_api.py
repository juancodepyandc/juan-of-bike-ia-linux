"""A PC-approved project dashboard, with real admission and measured estimates."""
import os
import hashlib
import re
from flask import jsonify,request
from agi_core.mission_store import MissionStore


def register_project_routes(bp,*,allowed,store=None):
    store=store or MissionStore()
    @bp.route('/api/projects',methods=['GET'])
    def projects():
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        items=[]
        for item in store.list(100):
            checkpoint=store.checkpoint(item['id']) or {};payload=item['payload']
            title=payload.get('project_title') or payload.get('request','')
            if 'OBJECTIF UTILISATEUR :\n' in title:title=title.split('OBJECTIF UTILISATEUR :\n',1)[1].split('\nCONTRAINTES FOURNIES',1)[0]
            did=(item.get('idem') or '').removeprefix('design:') if (item.get('idem') or '').startswith('design:') else None
            items.append({'id':item['id'],'design_id':did,'title':title[:160],'module':payload.get('module'),'status':item['status'],'created':item['created'],'started_at':item['started_at'],'finished_at':item['finished'],'steps':item['steps'],'criteria_count':len(checkpoint.get('criteria',[])),'verified_count':len(checkpoint.get('verified',[])),'scheduling':store.scheduling(item['id'])})
        return jsonify(ok=True,projects=items,concurrency=int(os.environ.get('AURORA_CONCURRENT_MISSIONS','1')),scope='Durable project admission; the pipeline executor retains its own outputs and checkpoints.')

    @bp.route('/api/projects/admission',methods=['POST'])
    def admit():
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,150}',str(data.get('request_id',''))) or data.get('module') not in {'conversation','image','code','video','drawing','3d','learning','cyber','voice'} or not isinstance(data.get('title'),str) or not 1<=len(data['title'])<=500:return jsonify(ok=False,error='Demande de calcul invalide.'),400
        payload={'project_kind':'frontend','request':data['title'],'project_title':data['title'],'module':data['module'],'model':str(data.get('model',''))[:200]}
        try:item,_=store.create(payload,'frontend:'+data['request_id'],queued=True)
        except ValueError as e:return jsonify(ok=False,error=str(e)),409
        return jsonify(ok=True,id=item['id'],status=item['status'],scheduling=store.scheduling(item['id']))

    @bp.route('/api/projects/<mid>/admission',methods=['POST'])
    def claim_admission(mid):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
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
        if not isinstance(data,dict) or data.get('status') not in {'completed','failed'}:return jsonify(ok=False,error='Résultat invalide.'),400
        executor=data.get('executor')
        if executor is not None and (not isinstance(executor,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,100}',executor)):return jsonify(ok=False,error='Exécutant invalide.'),400
        if item['status'] in {'completed','failed','stopped','blocked'}:
            if item['status']==data['status']:return jsonify(ok=True,status=item['status'])
            return jsonify(ok=False,error='Ce projet possède déjà un résultat final conservé.'),409
        token='frontend-'+(hashlib.sha256(executor.encode()).hexdigest() if isinstance(executor,str) else mid)
        if not item['owner'] or item['owner']!=token:return jsonify(ok=False,error='Ce calcul appartient à un autre exécutant ou n’a pas démarré. Ne pas le rejouer.'),409
        store.append(mid,{'type':'mission_complete' if data['status']=='completed' else 'error','result':'Le pipeline a terminé.' if data['status']=='completed' else 'Pipeline en erreur ; consulter ses preuves.'})
        return jsonify(ok=True,status=store.get(mid)['status'])

    @bp.route('/api/projects/<mid>/cancel',methods=['POST'])
    def cancel_queued(mid):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        if not store.cancel_queued(mid):return jsonify(ok=False,error='Le projet a déjà démarré. Utilisez son module pour contrôler son arrêt.'),409
        return jsonify(ok=True,status='stopped')

    @bp.route('/api/projects/<mid>',methods=['DELETE'])
    def delete_project(mid):
        if not allowed():return jsonify(ok=False,error='forbidden_public'),403
        item = store.get(mid)
        if not item: return jsonify(ok=False,error='Projet introuvable.'),404
        # We can only delete if it's already terminal, but let's allow it in terminal states
        if item['status'] not in {'completed','failed','stopped','blocked','interrupted'}:
            return jsonify(ok=False,error='Impossible de supprimer un projet en cours.'),409
        # Currently the backend doesn't have a strict delete feature for missions, but we can purge the UI by removing it from the DB.
        with store.connect(write=True) as db:
            db.execute("DELETE FROM events WHERE mission=?", (mid,))
            db.execute("DELETE FROM missions WHERE id=?", (mid,))
        return jsonify(ok=True)
