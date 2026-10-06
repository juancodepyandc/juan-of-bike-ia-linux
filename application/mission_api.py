"""Authenticated durable mission API, testable without starting inference services."""
from __future__ import annotations
import hashlib
import logging
import os
import re
import time
from uuid import uuid4

from flask import Response, jsonify, request, stream_with_context
from agi_core.mission_store import MissionStore, TERMINAL

logger = logging.getLogger(__name__)


def register_mission_routes(blueprint, auth, *, workspace, model_default, publish,
                            history_loader=lambda _: [], on_accepted=lambda *_: None,
                            on_completed=lambda *_: None, store=None):
    store = store or MissionStore()

    def notify(callback, *args):
        try:
            callback(*args)
        except Exception:
            logger.exception('Legacy dialogue synchronization failed; durable mission state is retained')

    def public(item, detail=False):
        if item['status'] in TERMINAL:
            notify(on_completed,item)
        value = {'id':item['id'],'status':item['status'],'request':item['payload']['request'],
                 'model':item['payload'].get('model',''),'workspace':item['payload'].get('workspace',''),
                 'started_at':item['created'],'finished_at':item['finished'],
                 'elapsed_seconds':max(0,(item['finished'] or time.time())-item['created']),
                 'steps':item['steps'],'files_changed':item['files'],'errors':item['errors'],
                 'last_event_id':item['last_event_id'],'stream_start_cursor':item['replay_from'],'result':item['result']}
        if detail:
            checkpoint = store.checkpoint(item['id']) or {}
            value.update(plan=checkpoint.get('plan',[]),criteria=checkpoint.get('criteria',[]),
                         verified=checkpoint.get('verified',[]),
                         evidence=[{'id':e['id'],'tool':e['tool'],'ok':e['ok'],
                                    'elapsed_seconds':e['elapsed_seconds']} for e in checkpoint.get('evidence',[])],
                         pending=bool(checkpoint.get('pending')))
        return value

    def dispatch(item, **extra):
        mid = item['id']
        if not publish('mission.start',{'mission_id':mid,**item['payload']}):
            store.append(mid,{'type':'error','message':'Mission daemon unavailable; accepted request retained for explicit resume'})
            return jsonify(ok=False,mission_id=mid,error='mission daemon unavailable',**extra),503
        return jsonify(ok=True,mission_id=mid,status='planning',**extra)

    @blueprint.route('/api/cli/mission/start',methods=['POST'])
    @auth
    def cli_mission_start():
        data = request.get_json(silent=True)
        if not isinstance(data,dict):
            return jsonify(ok=False,error='JSON object required'),400
        text = data.get('request','')
        if not isinstance(text,str) or not text.strip():
            return jsonify(ok=False,error='request text required'),400
        if len(text) > int(os.environ.get('AURORA_MAX_REQUEST_CHARS','65536')):
            return jsonify(ok=False,error='request exceeds configured character limit'),400
        for field in ('workspace','permissions','model','session_id','idempotency_key'):
            if field in data and not isinstance(data[field],str):
                return jsonify(ok=False,error=f'{field} must be text'),400
        level = data.get('permissions','AUTONOMOUS')
        if level not in {'SAFE','STANDARD','AUTONOMOUS','FULL'}:
            return jsonify(ok=False,error='unknown permission level'),400
        key = request.headers.get('Idempotency-Key') or data.get('idempotency_key','')
        if key and not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}',key):
            return jsonify(ok=False,error='invalid idempotency key'),400
        if key:
            scope = hashlib.sha256(request.headers.get('Authorization','').encode()).hexdigest()
            key = scope+':'+key
        session_id = data.get('session_id','')
        history = data.get('history')
        if history is not None:
            if (not isinstance(history,list) or len(history)>20 or any(
                    not isinstance(m,dict) or m.get('role') not in {'user','assistant'}
                    or not isinstance(m.get('content'),str) for m in history)):
                return jsonify(ok=False,error='History must contain at most 20 user/assistant text messages'),400
            if sum(len(m['content']) for m in history)>60000:
                return jsonify(ok=False,error='History exceeds the context transfer limit'),400
            history = [{'role':m['role'],'content':m['content']} for m in history]
        elif session_id:
            history = history_loader(session_id)
        try:
            selected_model = data.get('model') or model_default()
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc), error_kind='model_unavailable'),503
        payload = {'request':text,'workspace':data.get('workspace') or workspace,
                   'permissions':level,'model':selected_model,
                   'requested_model':data.get('model',''),
                   'session_id':session_id,'history':history or []}
        try:
            item, created = store.create(payload,key)
        except ValueError as exc:
            return jsonify(ok=False,error=str(exc)),409
        if not created:
            return jsonify(ok=True,mission_id=item['id'],status=item['status'],replayed=True,cursor=item['replay_from'])
        store.prune(int(os.environ.get('AURORA_MISSION_RETENTION_SECONDS',str(14*24*3600))))
        notify(on_accepted,item['id'],payload)
        return dispatch(item)

    @blueprint.route('/api/cli/missions',methods=['GET'])
    @auth
    def cli_missions_list():
        return jsonify(ok=True,missions=[public(item) for item in store.list()])

    @blueprint.route('/api/cli/mission/<mission_id>/status',methods=['GET'])
    @auth
    def cli_mission_status(mission_id):
        item = store.get(mission_id)
        if not item:
            return jsonify(ok=False,error='mission not found'),404
        return jsonify(ok=True,**public(item,detail=True))

    @blueprint.route('/api/cli/mission/<mission_id>/resume',methods=['POST'])
    @auth
    def cli_mission_resume(mission_id):
        data = request.get_json(silent=True) or {}
        if not isinstance(data,dict) or ('model' in data and not isinstance(data['model'],str)):
            return jsonify(ok=False,error='Resume model must be text'),400
        try:
            item,cursor = store.resume(mission_id,data.get('model'))
        except KeyError:
            return jsonify(ok=False,error='mission not found'),404
        except ValueError as exc:
            return jsonify(ok=False,error=str(exc)),409
        store.append(mission_id,{'type':'mission_resumed','event_id':uuid4().hex,
                                 'message':'Resume from checkpoint; inspect any action with unknown outcome before replay'})
        return dispatch(item,cursor=cursor)

    @blueprint.route('/api/cli/mission/<mission_id>/stop',methods=['POST'])
    @auth
    def cli_mission_stop(mission_id):
        item = store.get(mission_id)
        if not item:
            return jsonify(ok=False,error='mission not found'),404
        if item['status'] in TERMINAL:
            return jsonify(ok=True,status=item['status'])
        if item['status']=='interrupted' or item['owner'] is None:
            store.append(mission_id,{'type':'mission_complete','stopped':True,'result':'Interrupted mission stopped; checkpoint retained'})
            publish('mission.stop',{'mission_id':mission_id})
            return jsonify(ok=True,status='stopped')
        store.stop_requested(mission_id)
        delivered = publish('mission.stop',{'mission_id':mission_id})
        # The durable flag is also observed by the daemon's lease heartbeat.
        return jsonify(ok=True,status='stopping',signal_delivered=delivered),202

    @blueprint.route('/api/cli/mission/<mission_id>/input',methods=['POST'])
    @auth
    def cli_mission_input(mission_id):
        return jsonify(ok=False,error='Interactive input is unsupported; credentials must not be sent to a mission'),400

    @blueprint.route('/api/cli/mission/<mission_id>/events',methods=['GET'])
    @auth
    def cli_mission_events(mission_id):
        """Finite JSON polling for proxies that do not support SSE."""
        item = store.get(mission_id)
        if not item:
            return jsonify(ok=False,error='mission not found'),404
        cursor = request.headers.get('Last-Event-ID','0')
        if not re.fullmatch(r'[0-9]{1,20}',cursor):
            return jsonify(ok=False,error='invalid Last-Event-ID'),400
        cursor = int(cursor)
        if cursor>item['last_event_id']:
            return jsonify(ok=False,error='Last-Event-ID exceeds mission history'),409
        try:
            wait = int(request.args.get('wait','20'))
        except ValueError:
            return jsonify(ok=False,error='wait must be an integer from 0 to 20'),400
        if not 0<=wait<=20:
            return jsonify(ok=False,error='wait must be an integer from 0 to 20'),400
        deadline = time.monotonic()+wait
        while True:
            rows = store.events(mission_id,cursor)
            current = store.get(mission_id)
            if not rows and current['status']=='interrupted':
                seq = store.append(mission_id,{'type':'mission_interrupted',
                    'event_id':f"expired:{current['lease']}",
                    'message':'Execution lease expired; checkpoint is available for explicit resume'})
                if seq:
                    rows = store.events(mission_id,cursor)
                    current = store.get(mission_id)
            terminal = current['status'] in TERMINAL or current['status']=='interrupted'
            if rows or terminal or time.monotonic()>=deadline:
                if current['status'] in TERMINAL and (rows[-1][0] if rows else cursor)>=current['last_event_id']:
                    notify(on_completed,current)
                response = jsonify(ok=True,events=[{'id':seq,'event':event} for seq,event in rows],
                    cursor=rows[-1][0] if rows else cursor,
                    terminal=terminal and (rows[-1][0] if rows else cursor)>=current['last_event_id'])
                response.headers['Cache-Control'] = 'no-store'
                return response
            time.sleep(min(.25,max(0,deadline-time.monotonic())))

    @blueprint.route('/api/cli/mission/<mission_id>/stream',methods=['GET'])
    @auth
    def cli_mission_stream(mission_id):
        item = store.get(mission_id)
        if not item:
            return jsonify(ok=False,error='mission not found'),404
        cursor = request.headers.get('Last-Event-ID','0')
        if not re.fullmatch(r'[0-9]{1,20}',cursor):
            return jsonify(ok=False,error='invalid Last-Event-ID'),400
        cursor = int(cursor)
        if cursor>item['last_event_id']:
            return jsonify(ok=False,error='Last-Event-ID exceeds mission history'),409
        def generate():
            position = cursor
            yield ': durable mission stream\n\n'
            while True:
                for seq,event in store.events(mission_id,position):
                    import json
                    yield f'id: {seq}\ndata: {json.dumps(event,ensure_ascii=False)}\n\n'
                    position = seq
                current = store.get(mission_id)
                if current['status'] in TERMINAL and position>=current['last_event_id']:
                    notify(on_completed,current)
                    return
                if current['status']=='interrupted':
                    import json
                    event = {'type':'mission_interrupted','event_id':f"expired:{current['lease']}",
                             'message':'Execution lease expired; checkpoint is available for explicit resume'}
                    seq = store.append(mission_id,event)
                    if seq and seq>position:
                        yield f'id: {seq}\ndata: {json.dumps(event)}\n\n'
                    return
                import json
                yield 'data: '+json.dumps({'type':'heartbeat','elapsed':time.time()-current['created']})+'\n\n'
                time.sleep(1)
        return Response(stream_with_context(generate()),mimetype='text/event-stream',
                        headers={'Cache-Control':'no-cache, no-transform','X-Accel-Buffering':'no'})

    return store
