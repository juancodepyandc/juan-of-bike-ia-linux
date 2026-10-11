"""Local device approval. No email provider, copied key or public admin action."""
from __future__ import annotations
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlparse
from flask import jsonify, request, send_file

COOKIE = 'aurora_device'
BEARER_PREFIX = 'aurora_device:'
LOCK = threading.RLock()


def _path(workspace):
    path = Path(workspace)/'.aurora'/'devices.json'
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    return path


def _load(workspace):
    try: return json.loads(_path(workspace).read_text())
    except (OSError, ValueError): return {'devices': []}


def _save(workspace, data):
    path=_path(workspace); temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data),encoding='utf-8'); temporary.chmod(0o600); temporary.replace(path)


def device_auth(workspace):
    authorization=request.headers.get('Authorization','')
    bearer=authorization.startswith('Bearer '+BEARER_PREFIX)
    if authorization and not bearer:return None
    raw=authorization[len('Bearer '+BEARER_PREFIX):] if bearer else request.cookies.get(COOKIE,'')
    if not raw: return None
    # Browser cookies may authorize mutations only from this origin.
    if not bearer and request.method not in {'GET','HEAD','OPTIONS'}:
        origin=urlparse(request.headers.get('Origin',''))
        if origin.netloc.lower()!=request.host.lower() or origin.scheme not in {'http','https'}: return None
    digest=hashlib.sha256(raw.encode()).hexdigest()
    with LOCK:
        for device in _load(workspace).get('devices',[]):
            if hmac.compare_digest(device.get('hash',''),digest) and not device.get('revoked') and device.get('expires',0)>time.time():
                return device
    return None


def request_identity(workspace):
    device=device_auth(workspace)
    credential=request.headers.get('Authorization','')
    if credential and not device:return credential
    return 'device:'+device['id'] if device else ''


def register_device_routes(bp,workspace,*,local,notifier=None):
    pending={}; rates={}
    def lookup(identity):
        with LOCK:
            item=pending.get(identity)
            return dict(item) if item and item['expires']>time.time() else None
    def approve(identity,code):
        with LOCK:
            item=pending.get(identity)
            if item and item['expires']>time.time() and isinstance(code,str) and len(code)==6 and code.isascii() and code.isdigit() and hmac.compare_digest(item['code'],code):
                item['approved']=True
                return True
            return False
    def decline(identity):
        with LOCK:pending.pop(identity,None)
    if notifier is None:
        from application.desktop_pairing import DesktopApproval
        notifier=DesktopApproval(lookup,approve,decline).request
    def local_manager():
        if not local(): return False
        if request.method in {'GET','HEAD'}: return True
        origin=urlparse(request.headers.get('Origin',''))
        return origin.scheme in {'http','https'} and origin.hostname in {'localhost','127.0.0.1','::1'}
    def clean():
        now=time.time()
        for key in list(pending):
            if pending[key]['expires']<now: del pending[key]
        for ip in list(rates):
            rates[ip]=[t for t in rates[ip] if now-t<60]
            if not rates[ip]: del rates[ip]
    @bp.route('/connect')
    def connect_page(): return send_file(Path(__file__).with_name('device_connect.html'),max_age=0)
    @bp.route('/devices')
    def devices_page():
        if not local_manager(): return jsonify(ok=False,error='Ouvrir cette page sur le PC Aurora.'),403
        return send_file(Path(__file__).with_name('device_manager.html'),max_age=0)
    @bp.route('/api/devices/session')
    def session():
        device=device_auth(workspace)
        return jsonify(ok=True,connected=bool(device) or local(),name=device['name'] if device else 'Ce PC' if local() else None)
    @bp.route('/api/devices/pair',methods=['POST'])
    def pair():
        data=request.get_json(silent=True) or {}
        if not isinstance(data,dict): return jsonify(ok=False,error='Paramètres invalides.'),400
        name=data.get('name','Mon téléphone')
        if not isinstance(name,str) or not 1<=len(name.strip())<=80: return jsonify(ok=False,error='Nom d’appareil requis (80 caractères maximum).'),400
        transport=data.get('transport','browser')
        if transport not in {'browser','cli'}:return jsonify(ok=False,error='Transport invalide.'),400
        # No client-chosen code, no approval through the public tunnel.
        ip=hashlib.sha256((request.headers.get('X-Forwarded-For') or request.remote_addr or '').encode()).hexdigest()
        with LOCK:
            clean()
            if len(pending)>=20 or len(rates.get(ip,[]))>=5: return jsonify(ok=False,error='Trop de demandes. Réessayez dans une minute.'),429
            secret=secrets.token_urlsafe(32); code=str(secrets.randbelow(900000)+100000)
            while any(p['code']==code for p in pending.values()): code=str(secrets.randbelow(900000)+100000)
            identity=hashlib.sha256(secret.encode()).hexdigest()
            pending[identity]={'code':code,'name':name.strip(),'expires':time.time()+300,'approved':False,'transport':transport}
            rates.setdefault(ip,[]).append(time.time())
        notifier(identity)
        return jsonify(ok=True,claim=secret,code=code,expires_in=300)
    @bp.route('/api/devices/claim',methods=['POST'])
    def claim():
        data=request.get_json(silent=True) or {}
        if not isinstance(data,dict) or not isinstance(data.get('claim'),str) or len(data['claim'])>200: return jsonify(ok=False,error='Demande invalide.'),400
        with LOCK:
            clean(); digest=hashlib.sha256(data['claim'].encode()).hexdigest(); item=pending.get(digest)
            if not item: return jsonify(ok=False,error='Demande expirée. Recommencez la connexion.'),410
            if not item['approved']: return jsonify(ok=True,connected=False)
            raw=secrets.token_urlsafe(48); device={'id':secrets.token_hex(16),'hash':hashlib.sha256(raw.encode()).hexdigest(),
                'name':item['name'],'created':time.time(),'expires':time.time()+180*86400,'revoked':False,
                'workspace_owner':hashlib.sha256(b'local-workspace').hexdigest()}
            store=_load(workspace);store.setdefault('devices',[]).append(device);_save(workspace,store);del pending[digest]
        response=jsonify(ok=True,connected=True,name=device['name'],**({'credential':BEARER_PREFIX+raw} if item.get('transport')=='cli' else {}))
        response.set_cookie(COOKIE,raw,max_age=180*86400,httponly=True,secure=not local(),samesite='Strict',path='/')
        response.headers['Cache-Control']='no-store'
        return response
    @bp.route('/api/devices/manage',methods=['GET','POST'])
    def manage():
        if not local_manager(): return jsonify(ok=False,error='Validation uniquement sur le PC Aurora.'),403
        with LOCK:
            clean()
            if request.method=='POST':
                data=request.get_json(silent=True) or {}
                if not isinstance(data,dict): return jsonify(ok=False,error='Paramètres invalides.'),400
                if data.get('action')=='approve':
                    matches=[p for p in pending.values() if p['code']==data.get('code')]
                    if not matches:return jsonify(ok=False,error='Demande expirée.'),404
                    matches[0]['approved']=True
                elif data.get('action')=='revoke':
                    store=_load(workspace)
                    for d in store.get('devices',[]):
                        if d['id']==data.get('id'): d['revoked']=True
                    _save(workspace,store)
                else:return jsonify(ok=False,error='Action inconnue.'),400
            return jsonify(ok=True,pending=[{k:p[k] for k in ['code','name','expires','approved']} for p in pending.values()],
                devices=[{k:d[k] for k in ['id','name','created','expires','revoked']} for d in _load(workspace).get('devices',[])])
    @bp.route('/api/devices/logout',methods=['POST'])
    def logout():
        if not device_auth(workspace): return jsonify(ok=False,error='Appareil non connecté.'),403
        response=jsonify(ok=True);response.delete_cookie(COOKIE,path='/');return response
