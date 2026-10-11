"""Authenticated gateway to a PC-owned frontend session; no client controls URLs."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import subprocess
import threading
import time
import requests
from flask import Response, jsonify, request, send_file


def register_workspace_routes(bp, workspace, *, local, admin, extension, node):
    state = Path(os.environ.get('AURORA_WORKSPACE_STATE') or Path(workspace) / '.aurora' / 'persistent-workspace')
    service = 'http://127.0.0.1:' + str(int(os.environ.get('AURORA_WORKSPACE_PORT', '3034')))
    lock = threading.Lock()
    child = None

    def headers():
        # Paired devices explicitly approved on this PC share its workspace.
        is_local=local(); is_admin=admin(); ext_ok,record,_=extension()
        if not is_local and not is_admin and not ext_ok: return None
        credential=request.headers.get('Authorization','')
        owner=hashlib.sha256((credential or 'local-workspace').encode()).hexdigest()
        if ext_ok and (record or {}).get('workspace_owner'): owner=record['workspace_owner']
        try:
            token = (state / 'token').read_text().strip()
        except OSError:
            token = ''
        return {'X-Aurora-Workspace-Token': token,
                'X-Aurora-Workspace-Owner': owner}

    def ensure():
        nonlocal child
        with lock:
            try:
                token = (state / 'token').read_text().strip()
                response = requests.get(service + '/health', headers={'X-Aurora-Workspace-Token': token}, timeout=1)
                if response.ok and response.json().get('service') == 'aurora-persistent-workspace':
                    return
            except (OSError, requests.RequestException, ValueError):
                pass
            state.mkdir(parents=True, exist_ok=True)
            # A separate user service survives bridge restarts. Portable fallback uses Node.
            started = False
            if os.name == 'posix' and os.environ.get('XDG_RUNTIME_DIR'):
                try:
                    started = subprocess.run(['systemctl', '--user', 'start', 'aurora-workspace.service'],
                                             capture_output=True, timeout=5).returncode == 0
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if not started and (child is None or child.poll() is not None):
                with (state / 'service.log').open('ab') as log:
                    child = subprocess.Popen([node(), str(Path(__file__).parent / 'scripts' / 'persistent-workspace.mjs')],
                                             cwd=Path(__file__).parent, stdout=log, stderr=log,
                                             start_new_session=os.name == 'posix')
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                try:
                    token = (state / 'token').read_text().strip()
                    response = requests.get(service + '/health', headers={'X-Aurora-Workspace-Token': token}, timeout=1)
                    if response.ok and response.json().get('service') == 'aurora-persistent-workspace':
                        return
                except (OSError, requests.RequestException, ValueError):
                    pass
                time.sleep(.2)
            raise RuntimeError('workspace unavailable')

    @bp.route('/workspace', methods=['GET'])
    def workspace_page():
        return send_file(Path(__file__).with_name('persistent_workspace.html'), max_age=0)

    @bp.route('/api/workspace-session', methods=['POST'])
    @bp.route('/api/workspace-session/frame', methods=['GET'])
    @bp.route('/api/workspace-session/action', methods=['POST'])
    @bp.route('/api/workspace-session/download/<file_id>', methods=['GET'])
    def workspace_gateway(file_id=None):
        authenticated = headers()
        if authenticated is None:
            return jsonify(ok=False, error='forbidden_public', detail='Connectez cet appareil depuis votre PC Aurora.'), 403
        if request.content_length and request.content_length > 170 * 1024 * 1024:
            return jsonify(ok=False, error='Fichiers trop volumineux.'), 413
        try:
            if request.path == '/api/workspace-session':
                ensure()
                authenticated = headers()
                target = '/session'
            elif file_id:
                # Node maps this ID to a download owned by the credential; no filesystem path.
                if len(file_id) > 80:
                    return jsonify(ok=False, error='Fichier introuvable.'), 404
                target = '/download/' + file_id
            else:
                target = '/' + request.path.rsplit('/', 1)[-1]
            result = requests.request(request.method, service + target, headers=authenticated,
                                      json=request.get_json(silent=True) if request.method == 'POST' else None,
                                      timeout=40)
            response = Response(result.content, status=result.status_code,
                                content_type=result.headers.get('Content-Type', 'application/json'))
            response.headers['Cache-Control'] = 'no-store'
            if file_id:
                response.headers['Content-Disposition'] = result.headers.get('Content-Disposition', 'attachment')
            return response
        except (OSError, RuntimeError, requests.RequestException):
            return jsonify(ok=False, error='PC momentanément injoignable. Reconnectez l’espace sans relancer votre génération.'), 503
