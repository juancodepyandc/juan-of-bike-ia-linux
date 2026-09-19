from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

cowork_file_bp = Blueprint('cowork_file_bp', __name__)

# =====================================================================
#  Cowork — file ops + delete via the bridge
# =====================================================================
#
# Pourquoi: l app web (desktop ou mobile) n a pas acces direct au filesystem
# local. Quand le user tourne dans un navigateur, l overlay Cowork passe par
# ces routes pour lire/ecrire/supprimer des fichiers depuis le bridge.
#
# Securite: tous les chemins sont resolus a l interieur de WORKSPACE. Si la
# resolution sort du workspace -> 403. Limite de taille a 5 MB par fichier.
# Mode mobile detecte via le header X-Cowork-Runtime: web-mobile -> les
# routes destructives renvoient 403.

_COWORK_MAX_BYTES = 5 * 1024 * 1024


def _cowork_resolve_path(raw_path: str) -> tuple[str | None, str | None]:
    """Resolve a Cowork-supplied path to an absolute path INSIDE the
    workspace. Returns (absolute_path, error). Error is non-None when the
    resolved path escapes the workspace or is empty."""
    if not raw_path:
        return None, "path manquant"
    candidate = raw_path
    if not os.path.isabs(candidate):
        candidate = os.path.join(WORKSPACE, candidate)
    try:
        resolved = os.path.realpath(candidate)
        ws_real = os.path.realpath(WORKSPACE)
    except Exception as e:
        return None, f"path invalide: {e}"
    if not (resolved == ws_real or resolved.startswith(ws_real + os.sep)):
        return None, f"path hors workspace: {resolved}"
    return resolved, None


def _cowork_is_mobile() -> bool:
    rt = (request.headers.get("X-Cowork-Runtime") or "").strip().lower()
    if rt == "web-mobile":
        return True
    ua = (request.headers.get("User-Agent") or "").lower()
    return any(s in ua for s in ("iphone", "ipad", "ipod", "android"))


@cowork_file_bp.route("/api/cowork/read", methods=["GET"])
def cowork_read_file():
    raw = request.args.get("path", "")
    resolved, err = _cowork_resolve_path(raw)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    if not os.path.exists(resolved):
        return jsonify({"ok": False, "error": f"fichier introuvable: {resolved}"}), 404
    if not os.path.isfile(resolved):
        return jsonify({"ok": False, "error": f"pas un fichier: {resolved}"}), 400
    try:
        size = os.path.getsize(resolved)
        if size > _COWORK_MAX_BYTES:
            return jsonify({"ok": False, "error": f"fichier trop gros ({size} > {_COWORK_MAX_BYTES})"}), 413
        with open(resolved, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        return jsonify({"ok": True, "content": content, "bytes": len(content), "path": resolved})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@cowork_file_bp.route("/api/cowork/write", methods=["POST"])
def cowork_write_file():
    if _cowork_is_mobile():
        return jsonify({"ok": False, "error": "ecriture interdite en mode mobile"}), 403
    body = request.get_json(silent=True) or {}
    raw = (body.get("path") or "").strip()
    content = body.get("content")
    if not isinstance(content, str):
        return jsonify({"ok": False, "error": "content doit etre une string"}), 400
    if len(content) > _COWORK_MAX_BYTES:
        return jsonify({"ok": False, "error": f"contenu trop volumineux ({len(content)} > {_COWORK_MAX_BYTES})"}), 413
    resolved, err = _cowork_resolve_path(raw)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    try:
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as fh:
            fh.write(content)
        return jsonify({"ok": True, "bytes": len(content), "path": resolved})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@cowork_file_bp.route("/api/cowork/delete", methods=["POST"])
def cowork_delete_path():
    if _cowork_is_mobile():
        return jsonify({"ok": False, "error": "suppression interdite en mode mobile"}), 403
    body = request.get_json(silent=True) or {}
    raw = (body.get("path") or "").strip()
    resolved, err = _cowork_resolve_path(raw)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    if resolved == os.path.realpath(WORKSPACE):
        return jsonify({"ok": False, "error": "suppression de la racine workspace interdite"}), 403
    if not os.path.exists(resolved):
        return jsonify({"ok": True, "path": resolved, "noop": True})
    try:
        if os.path.isdir(resolved):
            import shutil
            shutil.rmtree(resolved)
        else:
            os.remove(resolved)
        return jsonify({"ok": True, "path": resolved})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------------------------------------------------------------------
# Cowork session temporary storage (sessions + per-session temp files)
# Endpoints provide warnings but do not block actions. Audit entries are
# appended to a simple log under the sessions base directory.
# ---------------------------------------------------------------------

SESSIONS_BASE = pathlib.Path(WORKSPACE) / 'application' / 'temp-sessions'
SESSIONS_AUDIT = SESSIONS_BASE / 'session_audit.log'

def _ensure_sessions_base() -> None:
    try:
        SESSIONS_BASE.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

def _safe_session_id(raw: str) -> str | None:
    # Accept only hex-like ids generated by the server (alnum _-)
    if not raw or not isinstance(raw, str):
        return None
    if all(c.isalnum() or c in ('_', '-') for c in raw):
        return raw
    return None

def _session_dir(session_id: str) -> pathlib.Path:
    return SESSIONS_BASE / session_id

def _audit_append(action: str, session_id: str | None, detail: str) -> None:
    try:
        _ensure_sessions_base()
        ts = int(time.time())
        ip = request.remote_addr or 'unknown'
        with open(SESSIONS_AUDIT, 'a', encoding='utf-8') as f:
            f.write(f"{ts}\t{ip}\t{action}\t{session_id or ''}\t{detail}\n")
    except Exception:
        pass


@cowork_file_bp.route('/api/cowork/session/create', methods=['POST'])
def cowork_session_create():
    body = request.get_json(silent=True) or {}
    title = (body.get('title') or '').strip()[:200]
    import uuid
    sid = f"sess_{uuid.uuid4().hex}"
    try:
        _ensure_sessions_base()
        d = _session_dir(sid)
        d.mkdir(exist_ok=True)
        meta = {'id': sid, 'title': title, 'createdAt': int(time.time())}
        with open(d / 'metadata.json', 'w', encoding='utf-8') as fh:
            import json
            json.dump(meta, fh)
        _audit_append('create', sid, title)
        warnings = [f"Session {sid} created under workspace: {str(d)}. Files may persist until removed."]
        return jsonify({'ok': True, 'sessionId': sid, 'path': str(d), 'warnings': warnings})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@cowork_file_bp.route('/api/cowork/session/list', methods=['GET'])
def cowork_session_list():
    try:
        _ensure_sessions_base()
        out = []
        for p in SESSIONS_BASE.iterdir():
            if not p.is_dir():
                continue
            meta = {'id': p.name, 'path': str(p)}
            try:
                mfile = p / 'metadata.json'
                if mfile.is_file():
                    import json
                    with open(mfile, 'r', encoding='utf-8') as fh:
                        mm = json.load(fh)
                        meta.update(mm)
            except Exception:
                pass
            out.append(meta)
        return jsonify({'ok': True, 'sessions': out})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@cowork_file_bp.route('/api/cowork/session/write', methods=['POST'])
def cowork_session_write():
    body = request.get_json(silent=True) or {}
    sid = (body.get('sessionId') or '').strip()
    filename = (body.get('filename') or '').strip()
    content = body.get('content')
    encoding = (body.get('encoding') or 'utf8')
    if not _safe_session_id(sid):
        return jsonify({'ok': False, 'error': 'sessionId invalide'}), 400
    if not filename:
        return jsonify({'ok': False, 'error': 'filename manquant'}), 400
    try:
        d = _session_dir(sid)
        d.mkdir(parents=True, exist_ok=True)
        safe = pathlib.Path(filename).name
        dest = d / safe
        if encoding == 'base64':
            import base64
            data = base64.b64decode(content or '')
            with open(dest, 'wb') as fh:
                fh.write(data)
        else:
            if not isinstance(content, str):
                return jsonify({'ok': False, 'error': 'content doit etre string'}), 400
            with open(dest, 'w', encoding='utf-8') as fh:
                fh.write(content)
        _audit_append('write', sid, safe)
        warnings = [f"Ecriture: le fichier {safe} est stocke dans la session {sid}. Veillez a supprimer la session si nécessaire."]
        return jsonify({'ok': True, 'path': str(dest), 'warnings': warnings})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@cowork_file_bp.route('/api/cowork/session/read', methods=['GET'])
def cowork_session_read():
    sid = (request.args.get('sessionId') or '').strip()
    filename = (request.args.get('filename') or '').strip()
    encoding = (request.args.get('encoding') or 'utf8')
    if not _safe_session_id(sid):
        return jsonify({'ok': False, 'error': 'sessionId invalide'}), 400
    if not filename:
        return jsonify({'ok': False, 'error': 'filename manquant'}), 400
    try:
        d = _session_dir(sid)
        safe = pathlib.Path(filename).name
        fpath = d / safe
        if not fpath.is_file():
            return jsonify({'ok': False, 'error': 'fichier introuvable'}), 404
        if encoding == 'base64':
            import base64
            data = base64.b64encode(fpath.read_bytes()).decode('ascii')
            out = {'ok': True, 'content': data, 'encoding': 'base64'}
        else:
            txt = fpath.read_text(encoding='utf-8', errors='replace')
            out = {'ok': True, 'content': txt, 'encoding': 'utf8'}
        _audit_append('read', sid, safe)
        out['warnings'] = [f"Lecture: le fichier {safe} provient d'une session temporaire sous {str(d)}."]
        return jsonify(out)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@cowork_file_bp.route('/api/cowork/session/list_files', methods=['GET'])
def cowork_session_list_files():
    sid = (request.args.get('sessionId') or '').strip()
    if not _safe_session_id(sid):
        return jsonify({'ok': False, 'error': 'sessionId invalide'}), 400
    try:
        d = _session_dir(sid)
        if not d.is_dir():
            return jsonify({'ok': True, 'files': []})
        files = [p.name for p in d.iterdir() if p.is_file()]
        _audit_append('list_files', sid, '')
        return jsonify({'ok': True, 'files': files})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@cowork_file_bp.route('/api/cowork/session/remove', methods=['POST'])
def cowork_session_remove():
    body = request.get_json(silent=True) or {}
    sid = (body.get('sessionId') or '').strip()
    if not _safe_session_id(sid):
        return jsonify({'ok': False, 'error': 'sessionId invalide'}), 400
    try:
        d = _session_dir(sid)
        if d.exists():
            import shutil
            shutil.rmtree(d)
            _audit_append('remove', sid, '')
            warnings = [f"La session {sid} et ses fichiers ont ete supprimes."]
            return jsonify({'ok': True, 'removed': True, 'warnings': warnings})
        else:
            return jsonify({'ok': True, 'removed': False, 'noop': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@cowork_file_bp.route('/api/cowork/session/cleanup', methods=['POST'])
def cowork_session_cleanup():
    body = request.get_json(silent=True) or {}
    days = int(body.get('days') or 30)
    if days < 1 or days > 3650:
        return jsonify({'ok': False, 'error': 'days invalide'}), 400
    try:
        _ensure_sessions_base()
        cutoff = time.time() - (days * 86400)
        removed = []
        for p in SESSIONS_BASE.iterdir():
            try:
                if not p.is_dir():
                    continue
                mtime = p.stat().st_mtime
                if mtime < cutoff:
                    import shutil
                    shutil.rmtree(p)
                    removed.append(p.name)
                    _audit_append('cleanup_remove', p.name, f'older_than={days}')
            except Exception:
                pass
        return jsonify({'ok': True, 'removed': removed, 'warnings': [f"Nettoyage supprime {len(removed)} sessions plus anciennes que {days} jours."]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


