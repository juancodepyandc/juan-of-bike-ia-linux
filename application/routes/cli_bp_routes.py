from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL, _ext_load, _ext_save, _ext_auth, _ext_default_model, _ext_default_model_diagnostics, _comfyui_is_ready
import secrets as _secrets
import time as _time
import hashlib as _hashlib

cli_bp = Blueprint('cli_bp', __name__)

# =====================================================================
#  CLI Remote API — /api/cli/*
#  Lightweight remote CLI client interface. Auth via existing Bearer keys.
# =====================================================================

import copy as _cli_copy

_CLI_VERSION = "1.3.0"

# --- Migration vers XDG Base Directory Specification ---
from agi_core.context import data_dir as _aurora_data_dir
_AURORA_DATA_DIR = str(_aurora_data_dir())
os.makedirs(_AURORA_DATA_DIR, exist_ok=True)

_CLI_SESSIONS_PATH = os.path.join(_AURORA_DATA_DIR, "cli_sessions.json")
_CLI_AGENT_STATE_PATH = os.path.join(_AURORA_DATA_DIR, "cli_agent_state.json")
_CLI_DYNAMIC_AGENTS_PATH = os.path.join(_AURORA_DATA_DIR, "dynamic_agents.json")
_CLI_CONNECTIONS_PATH = os.path.join(_AURORA_DATA_DIR, "connections.json")

# Migration automatique depuis l'ancien emplacement (dossier source)
_old_dir = os.path.dirname(os.path.abspath(__file__))
for old_name, new_path in [
    (".aurora_cli_sessions.json", _CLI_SESSIONS_PATH),
    (".aurora_cli_agent_state.json", _CLI_AGENT_STATE_PATH),
    (".aurora_dynamic_agents.json", _CLI_DYNAMIC_AGENTS_PATH),
    (".aurora_connections.json", _CLI_CONNECTIONS_PATH)
]:
    old_path = os.path.join(_old_dir, old_name)
    if os.path.exists(old_path) and not os.path.exists(new_path):
        import shutil
        shutil.move(old_path, new_path)
# --------------------------------------------------------

_CLI_PERMISSION_LEVELS = {
    "SAFE": {
        "read_files": True, "write_files": False, "delete_files": False,
        "execute_commands": False, "install_deps": False, "install_software": False,
        "internet_access": False, "download_files": False, "browser_access": False,
        "use_tools": False, "access_outside_ws": False, "access_other_proj": False,
        "create_subagents": False, "system_resources": False,
    },
    "STANDARD": {
        "read_files": True, "write_files": True, "delete_files": False,
        "execute_commands": True, "install_deps": False, "install_software": False,
        "internet_access": False, "download_files": False, "browser_access": False,
        "use_tools": True, "access_outside_ws": False, "access_other_proj": False,
        "create_subagents": False, "system_resources": False,
    },
    "AUTONOMOUS": {
        "read_files": True, "write_files": True, "delete_files": True,
        "execute_commands": True, "install_deps": True, "install_software": False,
        "internet_access": True, "download_files": True, "browser_access": True,
        "use_tools": True, "access_outside_ws": False, "access_other_proj": False,
        "create_subagents": True, "system_resources": False,
    },
    "FULL": {
        "read_files": True, "write_files": True, "delete_files": True,
        "execute_commands": True, "install_deps": True, "install_software": True,
        "internet_access": True, "download_files": True, "browser_access": True,
        "use_tools": True, "access_outside_ws": True, "access_other_proj": True,
        "create_subagents": True, "system_resources": True,
    },
}

_SUPPORTED_SERVICES = {
    "github": {"name": "GitHub", "auth_type": "token", "fields": ["token", "username"], "caps": ["repos", "issues", "prs", "actions"]},
    "canva": {"name": "Canva", "auth_type": "api_key", "fields": ["api_key"], "caps": ["designs", "templates", "export"]},
    "figma": {"name": "Figma", "auth_type": "token", "fields": ["token"], "caps": ["files", "components", "export"]},
    "vercel": {"name": "Vercel", "auth_type": "token", "fields": ["token", "team_id"], "caps": ["deploy", "domains", "env"]},
    "docker_hub": {"name": "Docker Hub", "auth_type": "token", "fields": ["username", "token"], "caps": ["images", "push", "pull"]},
    "npm": {"name": "npm", "auth_type": "token", "fields": ["token"], "caps": ["publish", "packages"]},
    "pypi": {"name": "PyPI", "auth_type": "token", "fields": ["token"], "caps": ["publish", "packages"]},
    "huggingface": {"name": "Hugging Face", "auth_type": "token", "fields": ["token"], "caps": ["models", "datasets", "spaces"]},
    "slack": {"name": "Slack", "auth_type": "webhook", "fields": ["webhook_url"], "caps": ["messages", "notifications"]},
    "notion": {"name": "Notion", "auth_type": "token", "fields": ["token"], "caps": ["pages", "databases", "search"]},
    "supabase": {"name": "Supabase", "auth_type": "api_key", "fields": ["url", "anon_key"], "caps": ["database", "auth", "storage"]},
}


def _cli_auth_required(f):
    """Decorator: require valid Bearer key for CLI routes."""
    import functools
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        ok, rec, err = _ext_auth()
        if not ok:
            return jsonify({"ok": False, "error": err}), 401
        g.cli_key_rec = rec
        return f(*args, **kwargs)
    return wrapper


_CLI_JSON_LOCKS = {}

def _cli_json_lock(path):
    lock = _CLI_JSON_LOCKS.get(path)
    if lock is None:
        lock = _CLI_JSON_LOCKS.setdefault(path, threading.RLock())
    return lock


def _cli_load_json(path):
    try:
        with _cli_json_lock(path), open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _cli_save_json(path, data):
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with _cli_json_lock(path):
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
    except Exception:
        pass


# --- Auth & Status ---

@cli_bp.route("/api/cli/register", methods=["POST"])
@_cli_auth_required
def cli_register():
    """Register a device using an already authorized bridge key."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "JSON object required"}), 400
    device_name = data.get("device_name", "Unknown-Device")
    client_key = data.get("client_key")

    if not isinstance(client_key, str) or not 1 <= len(client_key) <= 256:
        return jsonify({"ok": False, "error": "client_key must contain 1 to 256 characters"}), 400
    if not isinstance(device_name, str) or len(device_name) > 128:
        return jsonify({"ok": False, "error": "device_name must be a string of at most 128 characters"}), 400
        
    try:
        # Ensure it registers properly in the JSON store used by _ext_auth
        import hashlib
        
        # We reuse the server's internal hashing function
        h = _hashlib.sha256(("aurora-ext-key-v1::" + client_key).encode("utf-8")).hexdigest()
        
        store = _ext_load()
        if "keys" not in store:
            store["keys"] = []
            
        # Check if already registered
        exists = any(rec.get("hash") == h for rec in store["keys"])
        if not exists:
            store["keys"].append({
                "hash": h,
                "label": f"CLI_{device_name}",
                "origin": "",
                "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z"
            })
            _ext_save(store)
        
        return jsonify({"ok": True, "message": "Registered successfully", "device": device_name})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@cli_bp.route("/api/cli/auth", methods=["POST"])
@_cli_auth_required
def cli_auth():
    """Authenticate CLI client, return session capabilities."""
    return jsonify({
        "ok": True, "version": _CLI_VERSION,
        "label": g.cli_key_rec.get("label", ""),
        "permissions": list(_CLI_PERMISSION_LEVELS.keys()),
    })


@cli_bp.route("/api/cli/version", methods=["GET"])
@_cli_auth_required
def cli_version():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_server.py"),
                  "r", encoding="utf-8") as f:
            bridge_lines = len(f.readlines())
    except Exception:
        bridge_lines = 0
    return jsonify({
        "ok": True, "server_version": _CLI_VERSION,
        "bridge_lines": bridge_lines,
        "api_routes": len(list(current_app.url_map.iter_rules())),
        "agents_official": len(_cli_list_official_agents()),
        "modules": 8,
    })


@cli_bp.route("/api/cli/status", methods=["GET"])
@_cli_auth_required
def cli_status():
    """Comprehensive server status for CLI banner."""
    ollama_ok = False
    models = []
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if r.ok:
            ollama_ok = True
            models = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        pass
    comfy_ok = _comfyui_is_ready()
    hw = {}
    try:
        nv = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            timeout=5).decode().strip().split(",")
        if len(nv) >= 3:
            hw = {"gpu": nv[0].strip(), "vram_total_gb": round(int(nv[1]) / 1024, 1),
                  "vram_free_gb": round(int(nv[2]) / 1024, 1)}
    except Exception:
        hw = {"gpu": "N/A", "vram_total_gb": 0, "vram_free_gb": 0}
    hw["cpu"] = platform.processor() or platform.machine()
    hw["ram_gb"] = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    hw["os"] = f"{platform.system()} {platform.release()}"
    # Count skills, MCP, connections
    skills = _cli_discover_skills(WORKSPACE)
    mcp = _cli_discover_mcp(WORKSPACE)
    conns = _cli_load_json(_CLI_CONNECTIONS_PATH).get("connections", [])
    active_conns = [c for c in conns if c.get("active")]
    return jsonify({
        "ok": True, "bridge": True, "ollama": ollama_ok, "comfyui": comfy_ok,
        "models": models, "models_count": len(models),
        "hardware": hw,
        "agents_official": len(_cli_list_official_agents()),
        "agents_dynamic_saved": len(_cli_load_json(_CLI_DYNAMIC_AGENTS_PATH).get("agents", [])),
        "skills_count": len(skills),
        "mcp_servers": len(mcp),
        "mcp_tools": sum(len(s.get("tools", [])) for s in mcp),
        "connections": [c.get("service") for c in active_conns],
        "connections_count": len(active_conns),
        "hostname": platform.node(),
    })


@cli_bp.route("/api/cli/doctor", methods=["GET"])
@_cli_auth_required
def cli_doctor():
    """Full diagnostic for 'aurora doctor'."""
    checks = []
    # Bridge
    checks.append({"name": "CLI installé", "ok": True})
    checks.append({"name": "Connexion réseau", "ok": True})
    checks.append({"name": "Serveur Aurora accessible", "ok": True})
    checks.append({"name": "Authentification", "ok": True, "detail": g.cli_key_rec.get("label", "")})
    # Ollama
    ollama_ok = False
    observed_models = []
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        ollama_ok = r.ok
        if r.ok:
            observed_models = r.json().get("models", [])
    except Exception:
        pass
    checks.append({"name": "Ollama", "ok": ollama_ok, "detail": f"{OLLAMA_URL}"})
    # ComfyUI
    checks.append({"name": "ComfyUI", "ok": _comfyui_is_ready(), "detail": f"{COMFYUI_URL}"})
    # GPU
    gpu_ok = False
    vram_bytes = 0
    try:
        memory = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.total",
            "--format=csv,noheader,nounits"], timeout=5, text=True)
        capacities = [int(line.strip()) for line in memory.splitlines() if line.strip().isdigit()]
        vram_bytes = max(capacities, default=0) * 1024 ** 2
        gpu_ok = vram_bytes > 0
    except Exception:
        pass
    checks.append({"name": "GPU", "ok": gpu_ok})
    ram_total, ram_available = None, None
    try:
        memory = psutil.virtual_memory()
        ram_total, ram_available = memory.total, memory.available
    except Exception:
        pass
    hardware = {"ram_gb": round(ram_total / 1024 ** 3, 1) if ram_total else None,
                "ram_available_gb": round(ram_available / 1024 ** 3, 1) if ram_available is not None else None,
                "vram_total_gb": round(vram_bytes / 1024 ** 3, 1)}
    selected_model, model_error = "", ""
    try:
        selected_model = _ext_default_model(models=observed_models,
            resources={"ram_total_bytes": ram_total, "nvidia_vram_bytes": vram_bytes})
    except (ValueError, TypeError) as exc:
        model_error = str(exc)
    checks.append({"name": "Modèle de mission", "ok": bool(selected_model),
                   "detail": selected_model or model_error or "aucun modèle sélectionné"})
    # Tunnel
    tun = ""
    try:
        tun = open(os.path.join(os.path.dirname(WORKSPACE), "tunnel.txt")).read().strip()
    except Exception:
        pass
    checks.append({"name": "Tunnel Cloudflare", "ok": None, "status": "unverified",
                   "detail": f"adresse enregistrée, disponibilité non vérifiée : {tun}" if tun else "non configuré"})
    # Daemon AGI (bus IPC 3002) — readiness réelle pour les missions
    from agi_core.bus import probe_sync
    health = probe_sync()
    daemon_ok = health["ok"] and health["mission_ready"]
    checks.append({"name": "Daemon AGI (bus IPC 3002)", "ok": daemon_ok,
                   "detail": "abonné et joignable" if daemon_ok else "indisponible : missions impossibles"})
    # Permissions — le compte suit la constante, pas une valeur écrite en dur
    checks.append({"name": "Permissions", "ok": True,
                   "detail": f"{len(_CLI_PERMISSION_LEVELS)} niveaux disponibles"})
    # MCP
    mcp = _cli_discover_mcp(WORKSPACE)
    checks.append({"name": "MCP Servers", "ok": len(mcp) > 0, "detail": f"{len(mcp)} serveur(s)"})
    # Skills
    skills = _cli_discover_skills(WORKSPACE)
    checks.append({"name": "Skills", "ok": True, "detail": f"{len(skills)} skill(s)"})
    # Version
    checks.append({"name": "Version serveur", "ok": True, "detail": _CLI_VERSION})
    # Streaming (le transport SSE est le flux mission ; sa readiness dépend du daemon)
    checks.append({"name": "Streaming SSE de bout en bout", "ok": None, "status": "unverified",
                   "detail": "nécessite une mission réelle depuis le client ; aucun flux testé par ce diagnostic"})
    ready = ollama_ok and daemon_ok and bool(selected_model)
    models = [{"name": item.get("name", ""), "size": item.get("size", 0)}
              for item in observed_models if isinstance(item, dict)] if isinstance(observed_models, list) else []
    return jsonify({"ok": ready, "ready": ready, "gpu_ready": gpu_ok, "checks": checks,
                    "hardware": hardware, "default_model": selected_model, "models": models,
                    "model_selection": _ext_default_model_diagnostics()})


# --- Sessions ---

@cli_bp.route("/api/cli/session/create", methods=["POST"])
@_cli_auth_required
def cli_session_create():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        sid = "ses_" + _secrets.token_hex(8)
        now = datetime.datetime.utcnow().isoformat() + "Z"
        session = {
            "id": sid, "created_at": now, "updated_at": now,
            "workspace": data.get("workspace", WORKSPACE),
            "permissions": data.get("permissions", "AUTONOMOUS"),
            "messages": [], "files_changed": [], "sources_consulted": [],
            "timing": {}, "mission_state": None,
        }
        store = _cli_load_json(_CLI_SESSIONS_PATH)
        store.setdefault("sessions", []).append(session)
        _cli_save_json(_CLI_SESSIONS_PATH, store)
        return jsonify({"ok": True, "session": session})
    except Exception as e:
        return jsonify({"ok": False, "error": f"session create failed: {e}"}), 500


@cli_bp.route("/api/cli/session/list", methods=["GET"])
@_cli_auth_required
def cli_session_list():
    store = _cli_load_json(_CLI_SESSIONS_PATH)
    sessions = store.get("sessions", [])
    # Return summary, not full message history
    summaries = []
    for s in sessions:
        if not isinstance(s, dict):
            continue
        summaries.append({
            "id": s.get("id", ""), "created_at": s.get("created_at", ""), "updated_at": s.get("updated_at", ""),
            "workspace": s.get("workspace", ""), "permissions": s.get("permissions", ""),
            "message_count": len(s.get("messages", [])),
            "has_mission": s.get("mission_state") is not None,
        })
    return jsonify({"ok": True, "sessions": summaries})


@cli_bp.route("/api/cli/session/<session_id>", methods=["GET"])
@_cli_auth_required
def cli_session_get(session_id):
    store = _cli_load_json(_CLI_SESSIONS_PATH)
    for s in store.get("sessions", []):
        if isinstance(s, dict) and s.get("id") == session_id:
            return jsonify({"ok": True, "session": s})
    return jsonify({"ok": False, "error": "session not found"}), 404


@cli_bp.route("/api/cli/session/<session_id>/resume", methods=["POST"])
@_cli_auth_required
def cli_session_resume(session_id):
    store = _cli_load_json(_CLI_SESSIONS_PATH)
    for s in store.get("sessions", []):
        if isinstance(s, dict) and s.get("id") == session_id:
            s["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            _cli_save_json(_CLI_SESSIONS_PATH, store)
            return jsonify({"ok": True, "session": s})
    return jsonify({"ok": False, "error": "session not found"}), 404


@cli_bp.route("/api/cli/session/<session_id>", methods=["DELETE"])
@_cli_auth_required
def cli_session_delete(session_id):
    store = _cli_load_json(_CLI_SESSIONS_PATH)
    before = len(store.get("sessions", []))
    store["sessions"] = [s for s in store.get("sessions", []) if isinstance(s, dict) and s.get("id") != session_id]
    _cli_save_json(_CLI_SESSIONS_PATH, store)
    return jsonify({"ok": True, "deleted": before - len(store["sessions"])})


# --- Chat (streaming SSE) ---

@cli_bp.route("/api/cli/chat", methods=["POST"])
@_cli_auth_required
def cli_chat():
    """Streaming chat via SSE. Proxies to Ollama with streaming."""
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    try:
        model = data.get("model") or _ext_default_model()
        if not model:
            raise ValueError("Aucun modèle de conversation sélectionné")
    except (ValueError, requests.RequestException) as exc:
        return jsonify({"ok": False, "error_kind": "model_unavailable",
                        "error": str(exc) or "Modèle de conversation indisponible"}), 503
    session_id = data.get("session_id")
    workspace = data.get("workspace", WORKSPACE)

    # Build system prompt with skills & MCP context
    context = _cli_load_context_for_workspace(workspace)
    system_msg = (
        "Tu es Aurora, une IA agentique autonome. Tu as accès aux outils suivants:\n"
        f"- {context['mcp_tools_count']} outils MCP\n"
        f"- {context['skills_count']} skills chargés\n"
        f"- {context['connections_count']} services connectés\n"
        "Réponds de façon utile, précise et professionnelle. "
        "Si la tâche nécessite des actions (fichiers, commandes, web), décris les étapes."
    )
    if context.get("skills_summary"):
        system_msg += f"\n\nSkills actifs:\n{context['skills_summary']}"

    full_messages = [{"role": "system", "content": system_msg}] + messages

    def generate():
        try:
            r = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={"model": model, "messages": full_messages, "stream": True},
                stream=True, timeout=300,
            )
            r.raise_for_status()
            full_response = ""
            complete = False
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    if chunk.get("error"):
                        raise RuntimeError(str(chunk["error"]))
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full_response += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                    if chunk.get("done"):
                        complete = True
                        yield f"data: {json.dumps({'type': 'done', 'model': model, 'total_duration': chunk.get('total_duration', 0)})}\n\n"
                except json.JSONDecodeError:
                    continue
            if not complete:
                raise RuntimeError("Ollama a interrompu la conversation avant le resultat final")
            # Save to session if provided
            if session_id:
                _cli_session_append_message(session_id, messages[-1] if messages else {}, {"role": "assistant", "content": full_response})
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        finally:
            if 'r' in locals():
                r.close()

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _cli_session_append_message(session_id, user_msg, assistant_msg):
    store = _cli_load_json(_CLI_SESSIONS_PATH)
    for s in store.get("sessions", []):
        if isinstance(s, dict) and s.get("id") == session_id:
            if user_msg:
                s.setdefault("messages", []).append(user_msg)
            s.setdefault("messages", []).append(assistant_msg)
            s["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            break
    _cli_save_json(_CLI_SESSIONS_PATH, store)


# --- Permissions ---

@cli_bp.route("/api/cli/permissions", methods=["GET"])
@_cli_auth_required
def cli_permissions_get():
    return jsonify({"ok": True, "levels": _CLI_PERMISSION_LEVELS,
                    "available": list(_CLI_PERMISSION_LEVELS.keys())})


@cli_bp.route("/api/cli/permissions", methods=["POST"])
@_cli_auth_required
def cli_permissions_set():
    data = request.get_json(silent=True) or {}
    level = data.get("level", "").upper()
    session_id = data.get("session_id")
    if level not in _CLI_PERMISSION_LEVELS:
        return jsonify({"ok": False, "error": f"Unknown level. Use: {list(_CLI_PERMISSION_LEVELS.keys())}"}), 400
    if session_id:
        store = _cli_load_json(_CLI_SESSIONS_PATH)
        for s in store.get("sessions", []):
            if isinstance(s, dict) and s.get("id") == session_id:
                s["permissions"] = level
                break
        _cli_save_json(_CLI_SESSIONS_PATH, store)
    return jsonify({"ok": True, "level": level, "permissions": _CLI_PERMISSION_LEVELS[level]})


# --- Workspace ---

@cli_bp.route("/api/cli/workspace", methods=["GET"])
@_cli_auth_required
def cli_workspace_get():
    return jsonify({"ok": True, "workspace": WORKSPACE})


@cli_bp.route("/api/cli/workspace", methods=["POST"])
@_cli_auth_required
def cli_workspace_set():
    data = request.get_json(silent=True) or {}
    path = data.get("path", "")
    if not os.path.isdir(path):
        return jsonify({"ok": False, "error": "directory not found"}), 400
    return jsonify({"ok": True, "workspace": os.path.realpath(path)})


# --- Info routes ---

@cli_bp.route("/api/cli/tools", methods=["GET"])
@_cli_auth_required
def cli_tools():
    tools = [
        {"name": "web_search", "desc": "Recherche web (Crawl4AI + DuckDuckGo)"},
        {"name": "web_extract", "desc": "Extraction de contenu web"},
        {"name": "web_download", "desc": "Téléchargement de fichiers"},
        {"name": "web_action", "desc": "Actions Playwright (navigateur)"},
        {"name": "file_read", "desc": "Lecture de fichiers"},
        {"name": "file_write", "desc": "Écriture de fichiers"},
        {"name": "file_delete", "desc": "Suppression de fichiers"},
        {"name": "dir_list", "desc": "Liste de répertoires"},
        {"name": "command_run", "desc": "Exécution de commandes shell"},
        {"name": "python_run", "desc": "Exécution de scripts Python"},
        {"name": "git_ops", "desc": "Opérations Git"},
        {"name": "ollama_chat", "desc": "Chat avec LLM (Ollama)"},
        {"name": "image_generate", "desc": "Génération d'images (FLUX/ComfyUI)"},
        {"name": "3d_pipeline", "desc": "Pipeline 3D (Hunyuan3D/TRELLIS)"},
        {"name": "voice_stt", "desc": "Speech-to-Text (Voxtral)"},
        {"name": "voice_tts", "desc": "Text-to-Speech (Kokoro)"},
        {"name": "code_generate", "desc": "Génération de code multi-langages"},
        {"name": "code_sandbox", "desc": "Exécution en sandbox (Podman)"},
    ]
    # Add MCP tools
    mcp = _cli_discover_mcp(WORKSPACE)
    for server in mcp:
        for tool in server.get("tools", []):
            tools.append({"name": f"mcp:{server['name']}:{tool['name']}", "desc": tool.get("description", ""),
                          "source": "mcp", "server": server["name"]})
    return jsonify({"ok": True, "tools": tools, "total": len(tools)})


@cli_bp.route("/api/cli/models", methods=["GET"])
@_cli_auth_required
def cli_models():
    models = []
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if r.ok:
            for m in r.json().get("models", []):
                models.append({
                    "name": m.get("name", ""), "size": m.get("size", 0),
                    "modified": m.get("modified_at", ""),
                    "family": m.get("details", {}).get("family", ""),
                    "parameters": m.get("details", {}).get("parameter_size", ""),
                })
    except Exception:
        pass
    return jsonify({"ok": True, "models": models, "total": len(models)})


# --- Official Agents (immutable, only enable/disable) ---

def _cli_list_official_agents():
    from agent_registry import list_agents
    return list_agents()


@cli_bp.route("/api/cli/agents/official", methods=["GET"])
@_cli_auth_required
def cli_agents_official():
    agents = _cli_list_official_agents()
    state = _cli_load_json(_CLI_AGENT_STATE_PATH)
    disabled = state.get("disabled", [])
    for a in agents:
        a["enabled"] = a["name"] not in disabled
        a["protected"] = True
    return jsonify({"ok": True, "agents": agents, "total": len(agents)})


@cli_bp.route("/api/cli/agents/official/<name>/disable", methods=["POST"])
@_cli_auth_required
def cli_agent_disable(name):
    state = _cli_load_json(_CLI_AGENT_STATE_PATH)
    disabled = state.setdefault("disabled", [])
    if name not in disabled:
        disabled.append(name)
    _cli_save_json(_CLI_AGENT_STATE_PATH, state)
    return jsonify({"ok": True, "name": name, "enabled": False})


@cli_bp.route("/api/cli/agents/official/<name>/enable", methods=["POST"])
@_cli_auth_required
def cli_agent_enable(name):
    state = _cli_load_json(_CLI_AGENT_STATE_PATH)
    state["disabled"] = [n for n in state.get("disabled", []) if n != name]
    _cli_save_json(_CLI_AGENT_STATE_PATH, state)
    return jsonify({"ok": True, "name": name, "enabled": True})


# --- Dynamic Agents (create, modify, delete, save) ---

@cli_bp.route("/api/cli/agents/dynamic/list", methods=["GET"])
@_cli_auth_required
def cli_dynamic_agents_list():
    store = _cli_load_json(_CLI_DYNAMIC_AGENTS_PATH)
    return jsonify({"ok": True, "agents": store.get("agents", [])})


@cli_bp.route("/api/cli/agents/dynamic/create", methods=["POST"])
@_cli_auth_required
def cli_dynamic_agent_create():
    data = request.get_json(silent=True) or {}
    try:
        model = data.get("model") or _ext_default_model()
        if not model:
            raise ValueError("Aucun modèle d'agent sélectionné")
    except (ValueError, requests.RequestException) as exc:
        return jsonify({"ok": False, "error_kind": "model_unavailable",
                        "error": str(exc) or "Modèle d'agent indisponible"}), 503
    agent = {
        "id": "dyn_" + _secrets.token_hex(6),
        "name": data.get("name", "Agent"),
        "role": data.get("role", ""),
        "type": data.get("type", "temporary"),
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "created_by": data.get("mission_id", "manual"),
        "model": model,
        "system_prompt": data.get("system_prompt", ""),
        "tools": data.get("tools", []),
        "permissions": data.get("permissions", "STANDARD"),
        "status": "idle",
        "runtime_seconds": 0,
        "results": [],
    }
    store = _cli_load_json(_CLI_DYNAMIC_AGENTS_PATH)
    store.setdefault("agents", []).append(agent)
    _cli_save_json(_CLI_DYNAMIC_AGENTS_PATH, store)
    return jsonify({"ok": True, "agent": agent})


@cli_bp.route("/api/cli/agents/dynamic/<agent_id>", methods=["GET"])
@_cli_auth_required
def cli_dynamic_agent_get(agent_id):
    store = _cli_load_json(_CLI_DYNAMIC_AGENTS_PATH)
    for a in store.get("agents", []):
        if a["id"] == agent_id:
            return jsonify({"ok": True, "agent": a})
    return jsonify({"ok": False, "error": "agent not found"}), 404


@cli_bp.route("/api/cli/agents/dynamic/<agent_id>/modify", methods=["POST"])
@_cli_auth_required
def cli_dynamic_agent_modify(agent_id):
    data = request.get_json(silent=True) or {}
    store = _cli_load_json(_CLI_DYNAMIC_AGENTS_PATH)
    for a in store.get("agents", []):
        if a["id"] == agent_id:
            for k in ("name", "role", "model", "system_prompt", "tools", "permissions"):
                if k in data:
                    a[k] = data[k]
            _cli_save_json(_CLI_DYNAMIC_AGENTS_PATH, store)
            return jsonify({"ok": True, "agent": a})
    return jsonify({"ok": False, "error": "agent not found"}), 404


@cli_bp.route("/api/cli/agents/dynamic/<agent_id>", methods=["DELETE"])
@_cli_auth_required
def cli_dynamic_agent_delete(agent_id):
    store = _cli_load_json(_CLI_DYNAMIC_AGENTS_PATH)
    before = len(store.get("agents", []))
    store["agents"] = [a for a in store.get("agents", []) if a["id"] != agent_id]
    _cli_save_json(_CLI_DYNAMIC_AGENTS_PATH, store)
    return jsonify({"ok": True, "deleted": before - len(store["agents"])})


@cli_bp.route("/api/cli/agents/dynamic/<agent_id>/save", methods=["POST"])
@_cli_auth_required
def cli_dynamic_agent_save(agent_id):
    store = _cli_load_json(_CLI_DYNAMIC_AGENTS_PATH)
    for a in store.get("agents", []):
        if a["id"] == agent_id:
            a["type"] = "saved"
            _cli_save_json(_CLI_DYNAMIC_AGENTS_PATH, store)
            return jsonify({"ok": True, "agent": a})
    return jsonify({"ok": False, "error": "agent not found"}), 404


# --- MCP Servers ---

def _cli_discover_mcp(workspace_path):
    """Discover MCP server configs from .mcp.json files."""
    servers = []
    search_paths = [
        os.path.join(workspace_path, ".mcp.json"),
        os.path.join(os.path.dirname(workspace_path), ".mcp.json"),
    ]
    seen = set()
    for p in search_paths:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, cfg in data.get("mcpServers", {}).items():
                if name in seen:
                    continue
                seen.add(name)
                servers.append({
                    "name": name, "command": cfg.get("command", ""),
                    "args": cfg.get("args", []), "env": cfg.get("env", {}),
                    "source": p, "tools": [],
                })
        except Exception:
            continue
    return servers


_CLI_MCP_SPAWN_TIMEOUT = 12.0  # seconds for init + one JSON-RPC round-trip

def _cli_mcp_rpc(server, method, params, timeout=_CLI_MCP_SPAWN_TIMEOUT, cwd=None):
    """Run one JSON-RPC request against an MCP stdio server with a bounded wait.

    Never leaves a spawned process alive on failure and never blocks a Flask
    thread indefinitely. Returns (result_or_None, error_or_None)."""
    cmd = [server["command"]] + list(server.get("args", []))
    if not cmd or not cmd[0]:
        return None, "MCP server command is empty"
    env = {**os.environ, **server.get("env", {})}
    proc = None
    reader = None
    try:
        import errno as _errno
        import select as _select
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, env=env, cwd=cwd or os.getcwd())
        reader = proc.stdout
        reader_fd = reader.fileno()
        deadline = time.monotonic() + timeout

        def request(mid, method, params):
            payload = json.dumps({"jsonrpc": "2.0", "id": mid, "method": method,
                                  "params": params}) + "\n"
            if proc.stdin is None or proc.stdin.closed:
                raise OSError("MCP stdin closed")
            proc.stdin.write(payload.encode())
            proc.stdin.flush()

        request(1, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                  "clientInfo": {"name": "aurora-cli", "version": _CLI_VERSION}})
        request(2, method, params)
        buf = b""
        while True:
            while b"\n" in buf:
                line, _, buf = buf.partition(b"\n")
                try:
                    msg = json.loads(line.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                if isinstance(msg, dict) and msg.get("id") == 2:
                    return msg, None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None, "MCP server timed out (no response)"
            ready, _, _ = _select.select([reader_fd], [], [], min(remaining, 5.0))
            if not ready:
                continue
            chunk = os.read(reader_fd, 65536)
            if not chunk:
                return None, "MCP server closed while waiting for response"
            buf += chunk
            if len(buf) > 1_000_000:
                return None, "MCP server response too large"
    except OSError as e:
        return None, f"MCP request failed: {e}"
    finally:
        try:
            if reader is not None and not reader.closed:
                reader.close()
        except Exception:
            pass
        try:
            if proc is not None:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=2.0)
        except Exception:
            pass


@cli_bp.route("/api/cli/mcp/list", methods=["GET"])
@_cli_auth_required
def cli_mcp_list():
    workspace = request.args.get("workspace", WORKSPACE)
    servers = _cli_discover_mcp(workspace)
    return jsonify({"ok": True, "servers": servers, "total": len(servers)})


@cli_bp.route("/api/cli/mcp/tools", methods=["GET"])
@_cli_auth_required
def cli_mcp_tools():
    """List tools from all MCP servers (spawns each, sends tools/list)."""
    workspace = request.args.get("workspace") or WORKSPACE
    servers = _cli_discover_mcp(workspace)
    all_tools = []
    errors = []
    for srv in servers:
        resp, err = _cli_mcp_rpc(srv, "tools/list", {}, cwd=workspace)
        if err:
            errors.append({"server": srv["name"], "error": err})
            continue
        try:
            for t in resp.get("result", {}).get("tools", []):
                all_tools.append({"server": srv["name"], "name": t.get("name", ""),
                                  "description": t.get("description", ""),
                                  "schema": t.get("inputSchema", {})})
        except AttributeError:
            pass
    return jsonify({"ok": True, "tools": all_tools, "total": len(all_tools), "errors": errors})


@cli_bp.route("/api/cli/mcp/call", methods=["POST"])
@_cli_auth_required
def cli_mcp_call():
    """Call an MCP tool by server name + tool name."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "JSON object required"}), 400
    server_name = data.get("server", "")
    tool_name = data.get("tool", "")
    arguments = data.get("arguments", {})
    if not isinstance(arguments, dict):
        return jsonify({"ok": False, "error": "arguments must be an object"}), 400
    workspace = data.get("workspace") or WORKSPACE
    servers = _cli_discover_mcp(workspace)
    srv = next((s for s in servers if s["name"] == server_name), None)
    if not srv:
        return jsonify({"ok": False, "error": f"MCP server '{server_name}' not found"}), 404
    resp, err = _cli_mcp_rpc(srv, "tools/call", {"name": tool_name, "arguments": arguments},
                             cwd=workspace)
    if err:
        return jsonify({"ok": False, "error": err}), 504
    if resp is None:
        return jsonify({"ok": False, "error": "empty MCP response"}), 502
    return jsonify({"ok": True, "result": resp.get("result", {})})


# --- Skills ---

def _cli_discover_skills(workspace_path):
    """Discover skills from project, user, and global directories."""
    skills = []
    search_dirs = [
        os.path.join(workspace_path, ".aurora", "skills"),
        os.path.join(os.path.dirname(workspace_path), ".aurora", "skills"),
        os.path.expanduser("~/.aurora/skills"),
    ]
    if platform.system() != "Windows":
        search_dirs.append("/etc/aurora/skills")
    seen_names = set()
    for level, base in zip(["project", "project", "user", "global"], search_dirs):
        if not os.path.isdir(base):
            continue
        for entry in os.listdir(base):
            skill_dir = os.path.join(base, entry)
            skill_file = os.path.join(skill_dir, "SKILL.md")
            if not os.path.isfile(skill_file):
                continue
            if entry in seen_names:
                continue
            seen_names.add(entry)
            # Parse YAML frontmatter
            meta = {"name": entry, "description": "", "triggers": []}
            try:
                with open(skill_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        for line in parts[1].strip().split("\n"):
                            if line.startswith("name:"):
                                meta["name"] = line.split(":", 1)[1].strip().strip('"').strip("'")
                            elif line.startswith("description:"):
                                meta["description"] = line.split(":", 1)[1].strip().strip('"').strip("'")
                            elif line.startswith("  - "):
                                meta["triggers"].append(line.strip().lstrip("- ").strip('"').strip("'"))
            except Exception:
                pass
            skills.append({**meta, "level": level, "path": skill_dir, "file": skill_file})
    return skills


@cli_bp.route("/api/cli/skills/list", methods=["GET"])
@_cli_auth_required
def cli_skills_list():
    workspace = request.args.get("workspace", WORKSPACE)
    skills = _cli_discover_skills(workspace)
    return jsonify({"ok": True, "skills": skills, "total": len(skills)})


@cli_bp.route("/api/cli/skills/read", methods=["POST"])
@_cli_auth_required
def cli_skills_read():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    workspace = data.get("workspace", WORKSPACE)
    skills = _cli_discover_skills(workspace)
    skill = next((s for s in skills if s["name"] == name), None)
    if not skill:
        return jsonify({"ok": False, "error": f"Skill '{name}' not found"}), 404
    try:
        with open(skill["file"], "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"ok": True, "skill": skill, "content": content})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _cli_safe_skill_name(name):
    """Normalize a skill name to [a-z0-9_-], forbidding path traversal."""
    if not isinstance(name, str):
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", name).strip("-")
    if not cleaned or name != cleaned or cleaned in (".", ".."):
        return ""
    return cleaned[:80]


@cli_bp.route("/api/cli/skills/create", methods=["POST"])
@_cli_auth_required
def cli_skills_create():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "JSON object required"}), 400
    name = _cli_safe_skill_name(data.get("name", "new-skill"))
    if not name:
        return jsonify({"ok": False, "error": "Invalid skill name (only letters, digits, '-', '_')"}), 400
    level = data.get("level", "user")
    if level not in ("project", "user", "global"):
        return jsonify({"ok": False, "error": "Invalid level (project|user|global)"}), 400
    description = data.get("description", "")
    triggers = data.get("triggers", [])
    if not isinstance(triggers, list) or not all(isinstance(t, str) for t in triggers):
        return jsonify({"ok": False, "error": "triggers must be a list of strings"}), 400
    if level == "project":
        base = os.path.join(WORKSPACE, ".aurora", "skills")
    elif level == "global" and platform.system() != "Windows":
        base = "/etc/aurora/skills"
    else:
        base = os.path.expanduser("~/.aurora/skills")
    skill_dir = os.path.join(base, name)
    os.makedirs(skill_dir, exist_ok=True)
    triggers_yaml = "\n".join(f'  - "{t}"' for t in triggers) if triggers else '  - "*"'
    content = f"""---
name: {name}
description: {description}
triggers:
{triggers_yaml}
---

# {name}

{description}

## Instructions

<!-- Add instructions here for Aurora to follow when working with this type of project -->

"""
    skill_file = os.path.join(skill_dir, "SKILL.md")
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(content)
    return jsonify({"ok": True, "path": skill_dir, "file": skill_file})


@cli_bp.route("/api/cli/skills/discover", methods=["POST"])
@_cli_auth_required
def cli_skills_discover():
    """Auto-discover which skills are relevant for a workspace."""
    data = request.get_json(silent=True) or {}
    workspace = data.get("workspace", WORKSPACE)
    skills = _cli_discover_skills(workspace)
    # Match triggers against workspace files
    extensions = set()
    names = set()
    for dirpath, dirnames, filenames in os.walk(workspace):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
        for fn in filenames[:200]:  # cap
            ext = os.path.splitext(fn)[1]
            if ext:
                extensions.add(ext)
            names.add(fn.lower())
        if len(extensions) > 50:
            break
    matched = []
    for skill in skills:
        for trigger in skill.get("triggers", []):
            t = trigger.lower()
            if t.startswith("*.") and t in {f"*{e}" for e in extensions}:
                matched.append(skill)
                break
            if t in names:
                matched.append(skill)
                break
    return jsonify({"ok": True, "matched": matched, "total_skills": len(skills),
                    "extensions_found": sorted(extensions)[:30]})


# --- Service Connections ---

@cli_bp.route("/api/cli/connections/list", methods=["GET"])
@_cli_auth_required
def cli_connections_list():
    store = _cli_load_json(_CLI_CONNECTIONS_PATH)
    conns = store.get("connections", [])
    # Mask tokens in response
    safe = []
    for c in conns:
        sc = {k: v for k, v in c.items() if k != "credentials"}
        sc["configured"] = bool(c.get("credentials"))
        safe.append(sc)
    return jsonify({"ok": True, "connections": safe, "supported": _SUPPORTED_SERVICES})


@cli_bp.route("/api/cli/connections/add", methods=["POST"])
@_cli_auth_required
def cli_connections_add():
    data = request.get_json(silent=True) or {}
    service = data.get("service", "")
    if service not in _SUPPORTED_SERVICES:
        return jsonify({"ok": False, "error": f"Unknown service. Supported: {list(_SUPPORTED_SERVICES.keys())}"}), 400
    creds = data.get("credentials", {})
    store = _cli_load_json(_CLI_CONNECTIONS_PATH)
    conns = store.setdefault("connections", [])
    # Update or add
    existing = next((c for c in conns if c.get("service") == service), None)
    if existing:
        existing["credentials"] = creds
        existing["active"] = True
        existing["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    else:
        conns.append({
            "service": service, "name": _SUPPORTED_SERVICES[service]["name"],
            "credentials": creds, "active": True,
            "capabilities": _SUPPORTED_SERVICES[service]["caps"],
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        })
    _cli_save_json(_CLI_CONNECTIONS_PATH, store)
    return jsonify({"ok": True, "service": service, "name": _SUPPORTED_SERVICES[service]["name"]})


@cli_bp.route("/api/cli/connections/remove", methods=["POST"])
@_cli_auth_required
def cli_connections_remove():
    data = request.get_json(silent=True) or {}
    service = data.get("service", "")
    store = _cli_load_json(_CLI_CONNECTIONS_PATH)
    store["connections"] = [c for c in store.get("connections", []) if c.get("service") != service]
    _cli_save_json(_CLI_CONNECTIONS_PATH, store)
    return jsonify({"ok": True, "removed": service})


@cli_bp.route("/api/cli/connections/test", methods=["POST"])
@_cli_auth_required
def cli_connections_test():
    data = request.get_json(silent=True) or {}
    service = data.get("service", "")
    store = _cli_load_json(_CLI_CONNECTIONS_PATH)
    conn = next((c for c in store.get("connections", []) if c.get("service") == service), None)
    if not conn:
        return jsonify({"ok": False, "error": "connection not configured"}), 404
    # Quick test per service type
    ok = False
    detail = ""
    try:
        if service == "github":
            token = conn.get("credentials", {}).get("token", "")
            r = requests.get("https://api.github.com/user", headers={"Authorization": f"token {token}"}, timeout=10)
            ok = r.ok
            detail = r.json().get("login", "") if r.ok else r.text[:100]
        elif service == "huggingface":
            token = conn.get("credentials", {}).get("token", "")
            r = requests.get("https://huggingface.co/api/whoami-v2", headers={"Authorization": f"Bearer {token}"}, timeout=10)
            ok = r.ok
            detail = r.json().get("name", "") if r.ok else ""
        else:
            ok = True
            detail = "credentials stored (live test not implemented for this service)"
    except Exception as e:
        detail = str(e)[:200]
    return jsonify({"ok": ok, "service": service, "detail": detail})


# --- Workspace context loader (for mission/chat enrichment) ---

def _cli_load_context_for_workspace(workspace_path):
    """Load full context (skills, MCP, connections, agents) for a workspace."""
    from agi_core.context import load_context
    context = load_context(workspace_path)
    official = _cli_list_official_agents()
    state = _cli_load_json(_CLI_AGENT_STATE_PATH)
    disabled = state.get("disabled", [])
    enabled_officials = [a for a in official if a["name"] not in disabled]
    dynamic_saved = [a for a in _cli_load_json(_CLI_DYNAMIC_AGENTS_PATH).get("agents", []) if a.get("type") == "saved"]
    return {**context,
        "official_agents": len(enabled_officials), "dynamic_agents_saved": len(dynamic_saved),
    }


# --- Mission system (autonomous mode) ---

@cli_bp.route("/api/cli/artifacts/<token>", methods=["GET"])
@_cli_auth_required
def cli_artifact_download(token):
    from cli_artifacts import load_artifact
    try:
        path, metadata = load_artifact(token)
    except (OSError, ValueError, KeyError):
        return jsonify({"ok": False, "error": "artifact not found"}), 404
    return send_file(
        path, as_attachment=True, download_name=pathlib.PurePosixPath(metadata["filename"]).name,
        conditional=True, etag=metadata["sha256"], max_age=0,
    )

# The execution journal is shared with the daemon; SSE does not rely on this process's RAM.
import socket
from mission_api import register_mission_routes


def _cli_publish_ipc(event_type,payload):
    try:
        with socket.create_connection(('127.0.0.1',3002),timeout=2) as connection:
            connection.sendall((json.dumps({"action":"publish","event_type":event_type,"payload":payload})+"\n").encode())
        return True
    except OSError:
        return False


def _mission_history(session_id):
    for session in _cli_load_json(_CLI_SESSIONS_PATH).get('sessions',[]):
        if session.get('id')==session_id:
            return [{"role":m.get('role','user'),"content":m.get('content','')[:3000]+('\n[historique tronqué]' if len(m.get('content',''))>3000 else '')}
                    for m in session.get('messages',[])[-10:] if m.get('content')]
    return []


def _mission_accepted(mid,payload):
    if not payload.get('session_id'):
        return
    with _cli_json_lock(_CLI_SESSIONS_PATH):
        store = _cli_load_json(_CLI_SESSIONS_PATH)
        for session in store.get('sessions',[]):
            if session.get('id')==payload['session_id']:
                session.setdefault('messages',[]).append({'role':'user','content':payload['request'],'mission_id':mid,'ts':time.time()})
                session['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
                _cli_save_json(_CLI_SESSIONS_PATH,store)
                break


def _mission_completed(item):
    session_id = item['payload'].get('session_id')
    if not session_id or not item.get('result'):
        return
    with _cli_json_lock(_CLI_SESSIONS_PATH):
        store = _cli_load_json(_CLI_SESSIONS_PATH)
        for session in store.get('sessions',[]):
            if session.get('id') != session_id:
                continue
            messages = session.setdefault('messages',[])
            if not any(m.get('mission_id')==item['id'] and m.get('role')=='assistant'
                       and m.get('content')==item['result'] for m in messages):
                messages.append({'role':'assistant','content':item['result'],
                                 'mission_id':item['id'],'ts':time.time(),
                                 'status':item['status']})
                session['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
                _cli_save_json(_CLI_SESSIONS_PATH,store)
            break


_MISSION_STORE = register_mission_routes(
    cli_bp,_cli_auth_required,workspace=WORKSPACE,model_default=_ext_default_model,
    publish=_cli_publish_ipc,history_loader=_mission_history,on_accepted=_mission_accepted,
    on_completed=_mission_completed)
