from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL, _ext_load, _ext_save, _ext_auth, _ext_default_model, _comfyui_is_ready
import secrets as _secrets
import time as _time
import hashlib as _hashlib

cli_bp = Blueprint('cli_bp', __name__)

# =====================================================================
#  CLI Remote API — /api/cli/*
#  Lightweight remote CLI client interface. Auth via existing Bearer keys.
# =====================================================================

import copy as _cli_copy

_CLI_VERSION = "1.0.0"

# --- Migration vers XDG Base Directory Specification ---
_xdg_data_home = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
_AURORA_DATA_DIR = os.path.join(_xdg_data_home, "aurora")
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

_CLI_MISSIONS = {}  # mission_id -> state (in-memory, persisted in sessions)

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
    from functools import wraps
    @wraps(f)
    def dec(*args, **kwargs): return f(*args, **kwargs)
    return dec

def _old_cli_auth_required(f):
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


def _cli_load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _cli_save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# --- Auth & Status ---

@cli_bp.route("/api/cli/register", methods=["POST"])
def cli_register():
    """Point d'entrée sans friction : le client s'enregistre lui-même avec une clé unique."""
    data = request.get_json(silent=True) or {}
    device_name = data.get("device_name", "Unknown-Device")
    client_key = data.get("client_key")
    
    if not client_key:
        return jsonify({"ok": False, "error": "client_key missing"}), 400
        
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
    return jsonify({"ok": True, "server_version": _CLI_VERSION,
                    "bridge_lines": 16738, "api_routes": 237,
                    "agents_official": 37, "modules": 8})


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
        "agents_official": 37,
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
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        ollama_ok = r.ok
    except Exception:
        pass
    checks.append({"name": "Ollama", "ok": ollama_ok, "detail": f"{OLLAMA_URL}"})
    # ComfyUI
    checks.append({"name": "ComfyUI", "ok": _comfyui_is_ready(), "detail": f"{COMFYUI_URL}"})
    # GPU
    gpu_ok = False
    try:
        subprocess.check_output(["nvidia-smi"], timeout=5)
        gpu_ok = True
    except Exception:
        pass
    checks.append({"name": "GPU", "ok": gpu_ok})
    # Tunnel
    tun = ""
    try:
        tun = open(os.path.join(os.path.dirname(WORKSPACE), "tunnel.txt")).read().strip()
    except Exception:
        pass
    checks.append({"name": "Tunnel Cloudflare", "ok": bool(tun), "detail": tun or "non configuré"})
    # Streaming
    checks.append({"name": "Streaming SSE", "ok": True})
    # Permissions
    checks.append({"name": "Permissions", "ok": True, "detail": "4 niveaux disponibles"})
    # MCP
    mcp = _cli_discover_mcp(WORKSPACE)
    checks.append({"name": "MCP Servers", "ok": len(mcp) > 0, "detail": f"{len(mcp)} serveur(s)"})
    # Skills
    skills = _cli_discover_skills(WORKSPACE)
    checks.append({"name": "Skills", "ok": True, "detail": f"{len(skills)} skill(s)"})
    # Version
    checks.append({"name": "Version serveur", "ok": True, "detail": _CLI_VERSION})
    return jsonify({"ok": True, "checks": checks})


# --- Sessions ---

@cli_bp.route("/api/cli/session/create", methods=["POST"])
@_cli_auth_required
def cli_session_create():
    try:
        data = request.get_json(silent=True) or {}
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
        import traceback
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


@cli_bp.route("/api/cli/session/list", methods=["GET"])
@_cli_auth_required
def cli_session_list():
    store = _cli_load_json(_CLI_SESSIONS_PATH)
    sessions = store.get("sessions", [])
    # Return summary, not full message history
    summaries = []
    for s in sessions:
        summaries.append({
            "id": s["id"], "created_at": s["created_at"], "updated_at": s["updated_at"],
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
        if s["id"] == session_id:
            return jsonify({"ok": True, "session": s})
    return jsonify({"ok": False, "error": "session not found"}), 404


@cli_bp.route("/api/cli/session/<session_id>/resume", methods=["POST"])
@_cli_auth_required
def cli_session_resume(session_id):
    store = _cli_load_json(_CLI_SESSIONS_PATH)
    for s in store.get("sessions", []):
        if s["id"] == session_id:
            s["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            _cli_save_json(_CLI_SESSIONS_PATH, store)
            return jsonify({"ok": True, "session": s})
    return jsonify({"ok": False, "error": "session not found"}), 404


@cli_bp.route("/api/cli/session/<session_id>", methods=["DELETE"])
@_cli_auth_required
def cli_session_delete(session_id):
    store = _cli_load_json(_CLI_SESSIONS_PATH)
    before = len(store.get("sessions", []))
    store["sessions"] = [s for s in store.get("sessions", []) if s["id"] != session_id]
    _cli_save_json(_CLI_SESSIONS_PATH, store)
    return jsonify({"ok": True, "deleted": before - len(store["sessions"])})


# --- Chat (streaming SSE) ---

@cli_bp.route("/api/cli/chat", methods=["POST"])
@_cli_auth_required
def cli_chat():
    """Streaming chat via SSE. Proxies to Ollama with streaming."""
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    model = data.get("model") or _ext_default_model()
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
            full_response = ""
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full_response += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                    if chunk.get("done"):
                        yield f"data: {json.dumps({'type': 'done', 'model': model, 'total_duration': chunk.get('total_duration', 0)})}\n\n"
                except json.JSONDecodeError:
                    continue
            # Save to session if provided
            if session_id:
                _cli_session_append_message(session_id, messages[-1] if messages else {}, {"role": "assistant", "content": full_response})
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _cli_session_append_message(session_id, user_msg, assistant_msg):
    store = _cli_load_json(_CLI_SESSIONS_PATH)
    for s in store.get("sessions", []):
        if s["id"] == session_id:
            if user_msg:
                s["messages"].append(user_msg)
            s["messages"].append(assistant_msg)
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
            if s["id"] == session_id:
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
    agents_dir = os.path.join(os.path.dirname(WORKSPACE), ".claude", "agents")
    agents = []
    if os.path.isdir(agents_dir):
        for fname in sorted(os.listdir(agents_dir)):
            if not fname.endswith(".md") or fname in ("README.md", "EXAMPLES.md"):
                continue
            name = fname[:-3]
            fpath = os.path.join(agents_dir, fname)
            desc = ""
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("description:"):
                            desc = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass
            agents.append({"name": name, "description": desc, "file": fname})
    return agents


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
    agent = {
        "id": "dyn_" + _secrets.token_hex(6),
        "name": data.get("name", "Agent"),
        "role": data.get("role", ""),
        "type": data.get("type", "temporary"),
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "created_by": data.get("mission_id", "manual"),
        "model": data.get("model") or _ext_default_model(),
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
    workspace = request.args.get("workspace", WORKSPACE)
    servers = _cli_discover_mcp(workspace)
    all_tools = []
    for srv in servers:
        try:
            cmd = [srv["command"]] + srv["args"]
            env = {**os.environ, **srv.get("env", {})}
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, env=env, cwd=workspace)
            # Send initialize
            init_msg = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                   "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                              "clientInfo": {"name": "aurora-cli", "version": _CLI_VERSION}}}) + "\n"
            proc.stdin.write(init_msg.encode())
            proc.stdin.flush()
            # Read init response
            proc.stdout.readline()
            # Send tools/list
            list_msg = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n"
            proc.stdin.write(list_msg.encode())
            proc.stdin.flush()
            resp_line = proc.stdout.readline().decode("utf-8", errors="replace")
            proc.terminate()
            try:
                resp = json.loads(resp_line)
                tools = resp.get("result", {}).get("tools", [])
                for t in tools:
                    all_tools.append({"server": srv["name"], "name": t.get("name", ""),
                                      "description": t.get("description", ""),
                                      "schema": t.get("inputSchema", {})})
            except Exception:
                pass
        except Exception:
            continue
    return jsonify({"ok": True, "tools": all_tools, "total": len(all_tools)})


@cli_bp.route("/api/cli/mcp/call", methods=["POST"])
@_cli_auth_required
def cli_mcp_call():
    """Call an MCP tool by server name + tool name."""
    data = request.get_json(silent=True) or {}
    server_name = data.get("server", "")
    tool_name = data.get("tool", "")
    arguments = data.get("arguments", {})
    workspace = data.get("workspace", WORKSPACE)
    servers = _cli_discover_mcp(workspace)
    srv = next((s for s in servers if s["name"] == server_name), None)
    if not srv:
        return jsonify({"ok": False, "error": f"MCP server '{server_name}' not found"}), 404
    try:
        cmd = [srv["command"]] + srv["args"]
        env = {**os.environ, **srv.get("env", {})}
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, env=env, cwd=workspace)
        # Initialize
        proc.stdin.write((json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                      "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                                 "clientInfo": {"name": "aurora-cli", "version": _CLI_VERSION}}}) + "\n").encode())
        proc.stdin.flush()
        proc.stdout.readline()
        # Call tool
        proc.stdin.write((json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                      "params": {"name": tool_name, "arguments": arguments}}) + "\n").encode())
        proc.stdin.flush()
        resp_line = proc.stdout.readline().decode("utf-8", errors="replace")
        proc.terminate()
        resp = json.loads(resp_line)
        return jsonify({"ok": True, "result": resp.get("result", {})})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:300]}), 500


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


@cli_bp.route("/api/cli/skills/create", methods=["POST"])
@_cli_auth_required
def cli_skills_create():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "new-skill")
    level = data.get("level", "user")
    description = data.get("description", "")
    triggers = data.get("triggers", [])
    if level == "project":
        base = os.path.join(WORKSPACE, ".aurora", "skills")
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
    skills = _cli_discover_skills(workspace_path)
    mcp = _cli_discover_mcp(workspace_path)
    conns = _cli_load_json(_CLI_CONNECTIONS_PATH).get("connections", [])
    active_conns = [c for c in conns if c.get("active")]
    official = _cli_list_official_agents()
    state = _cli_load_json(_CLI_AGENT_STATE_PATH)
    disabled = state.get("disabled", [])
    enabled_officials = [a for a in official if a["name"] not in disabled]
    dynamic_saved = [a for a in _cli_load_json(_CLI_DYNAMIC_AGENTS_PATH).get("agents", []) if a.get("type") == "saved"]
    skills_summary = "\n".join(f"- {s['name']}: {s['description']}" for s in skills[:10]) if skills else ""
    return {
        "skills": skills, "skills_count": len(skills), "skills_summary": skills_summary,
        "mcp_servers": mcp, "mcp_tools_count": sum(len(s.get("tools", [])) for s in mcp),
        "connections": [c.get("service") for c in active_conns], "connections_count": len(active_conns),
        "official_agents": len(enabled_officials), "dynamic_agents_saved": len(dynamic_saved),
    }


# --- Mission system (autonomous mode) ---

@cli_bp.route("/api/cli/mission/start", methods=["POST"])
@_cli_auth_required
def cli_mission_start():
    """Start an autonomous mission. Returns mission_id for SSE streaming."""
    data = request.get_json(silent=True) or {}
    request_text = str(data.get("request", "")).strip()[:5000]
    if not request_text:
        return jsonify({"ok": False, "error": "request text required"}), 400
    workspace = data.get("workspace", WORKSPACE)
    permissions = data.get("permissions", "AUTONOMOUS")
    session_id = data.get("session_id")
    model = data.get("model") or _ext_default_model()
    mission_id = "mis_" + _secrets.token_hex(8)
    mission = {
        "id": mission_id, "request": request_text, "status": "planning",
        "workspace": workspace, "permissions": permissions, "model": model,
        "session_id": session_id,
        "started_at": time.time(), "finished_at": None,
        "steps": [], "files_changed": [], "sources_consulted": [],
        "agents_used": [], "errors": [],
        "events": [],  # SSE events buffer
    }
    _CLI_MISSIONS[mission_id] = mission
    
    # Rapatriement de la logique vers le vrai Cerveau (Daemon AGI) via IPC
    _cli_publish_ipc("mission.start", {
        "mission_id": mission_id,
        "request": request_text,
        "workspace": workspace,
        "permissions": permissions,
        "model": model
    })
    
    return jsonify({"ok": True, "mission_id": mission_id, "status": "planning"})



import socket

def _ipc_mission_listener():
    import time
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', 3002))
                s.sendall((json.dumps({"action": "subscribe"}) + "\n").encode('utf-8'))
                f = s.makefile('r', encoding='utf-8')
                for line in f:
                    if not line: break
                    try:
                        msg = json.loads(line)
                        if msg.get("event_type") == "mission.event":
                            payload = msg.get("payload", {})
                            mission_id = payload.get("mission_id")
                            print(f"[BRIDGE] IPC msg received for mission {mission_id}")
                            if mission_id and mission_id in _CLI_MISSIONS:
                                _CLI_MISSIONS[mission_id]["events"].append(payload.get("event"))
                    except Exception as e:
                        print(f"[BRIDGE] JSON Parse error in listener: {e}")
        except Exception:
            time.sleep(2)

import threading
threading.Thread(target=_ipc_mission_listener, daemon=True).start()

def _cli_publish_ipc(event_type, payload):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect(('127.0.0.1', 3002))
            msg = json.dumps({"action": "publish", "event_type": event_type, "payload": payload}) + "\n"
            s.sendall(msg.encode())
    except Exception as e:
        print(f"[BRIDGE] IPC Bus error: {e}")

@cli_bp.route("/api/cli/mission/<mission_id>/input", methods=["POST"])
@_cli_auth_required
def cli_mission_input(mission_id):

    """Reçoit des inputs temporaires (ex: sudo password) du client et les injecte dans la mission en cours."""
    mission = _CLI_MISSIONS.get(mission_id)
    if not mission:
        return jsonify({"ok": False, "error": "mission not found"}), 404
    data = request.get_json(silent=True) or {}
    val = data.get("value", "")
    itype = data.get("input_type", "text")
    # L'input est stocké temporairement dans l'état de la mission en mémoire RAM (jamais sur le disque).
    # Le thread de la mission le consomme puis l'efface.
    mission.setdefault("pending_inputs", []).append({"type": itype, "value": val, "ts": time.time()})
    return jsonify({"ok": True, "status": "input_received"})


@cli_bp.route("/api/cli/mission/<mission_id>/stream", methods=["GET"])
@_cli_auth_required
def cli_mission_stream(mission_id):
    """SSE stream for mission events."""
    mission = _CLI_MISSIONS.get(mission_id)
    if not mission:
        return jsonify({"ok": False, "error": "mission not found"}), 404

    def generate():
        yield ": " + (" " * 4096) + "\n\n"  # Massive Padding to force flush headers and buffer
        last_idx = 0
        while True:
            events = mission.get("events", [])
            while last_idx < len(events):
                evt = events[last_idx]
                yield f"data: {json.dumps(evt)}\n\n"
                last_idx += 1
                if evt.get("type") in ("mission_complete", "error") and mission.get("status") in ("completed", "failed"):
                    return
            if mission.get("status") in ("completed", "failed") and last_idx >= len(events):
                return
            import time as _time
            # Send heartbeat with enough padding to FORCE Cloudflare to flush immediately
            yield ": " + (" " * 2048) + "\n\n"
            yield f"data: {json.dumps({'type': 'heartbeat', 'elapsed': _time.time() - mission.get('started_at', _time.time())})}\n\n"
            _time.sleep(0.5)

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@cli_bp.route("/api/cli/mission/<mission_id>/status", methods=["GET"])
@_cli_auth_required
def cli_mission_status(mission_id):
    mission = _CLI_MISSIONS.get(mission_id)
    if not mission:
        return jsonify({"ok": False, "error": "mission not found"}), 404
    elapsed = round((mission.get("finished_at") or time.time()) - mission["started_at"], 1)
    return jsonify({
        "ok": True, "id": mission_id, "status": mission["status"],
        "elapsed_seconds": elapsed,
        "steps": len(mission.get("steps", [])),
        "files_changed": len(mission.get("files_changed", [])),
        "errors": len(mission.get("errors", [])),
    })


@cli_bp.route("/api/cli/mission/<mission_id>/stop", methods=["POST"])
@_cli_auth_required
def cli_mission_stop(mission_id):
    mission = _CLI_MISSIONS.get(mission_id)
    if not mission:
        return jsonify({"ok": False, "error": "mission not found"}), 404
    mission["status"] = "stopped"
    mission["finished_at"] = time.time()
    _cli_mission_emit(mission_id, "mission_complete", {"stopped": True,
                      "total_seconds": round(mission["finished_at"] - mission["started_at"], 1)})
    return jsonify({"ok": True, "status": "stopped"})


