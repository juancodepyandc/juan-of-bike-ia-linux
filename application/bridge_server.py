"""
Aurora Bridge Server — Point d'entree unique pour le telephone (telecommande).
Tourne sur le port 3001, proxy vers tous les services locaux.

Usage:
  python bridge_server.py
  cloudflared tunnel --url http://localhost:1420   (Vite proxy redirige /api et /proxy ici)
"""

from flask import Flask, request, jsonify, Response, send_file, abort, g, stream_with_context
from flask_cors import CORS
import subprocess
import threading
import time
import datetime
import uuid
import platform
import pathlib
import psutil
import os
import re
import shutil
import sys
import sysconfig
import json
import base64
import requests
import secrets as _secrets
import hashlib as _hashlib
import hmac as _hmac
from urllib.parse import parse_qs, quote, urlparse

app = Flask(__name__)
# CORS headers: expose picker telemetry (model, reason, history, coverage) + extraction stats.
# Lets extension clients correlate vision decisions across requests without parsing JSON body.
CORS(app, expose_headers=["X-Picker-Reason-Kind", "X-Free-Vram-Gb", "X-Picker-Model", "X-Picker-History-Count", "X-Picker-History-Maxlen", "X-Picker-History-Dominant-Kind", "X-Picker-History-Span-Seconds", "X-Picker-History-Distinct-Models", "X-Picker-History-Empty-Cells", "X-Picker-History-Coverage-Pct", "X-Picker-History-Coverage-Window-Seconds", "X-Picker-History-Coverage-Window-Delta-Pct", "X-Cards-Processed", "X-Items-Extracted", "X-Host-Yield-Delta-Pct", "ETag"])


# =====================================================================
#  Per-request logging
# =====================================================================

@app.before_request
def _req_start():
    g.start_time = time.perf_counter()


@app.after_request
def _req_log(response):
    duration_ms = round((time.perf_counter() - g.start_time) * 1000)
    if not request.path.startswith("/api/python/progress"):
        # ASCII-only arrow: bridge stdout can be redirected to a file whose
        # default encoding is cp1252 on Windows, which cannot encode "->".
        print(f"[bridge] {request.method} {request.path} -> {response.status_code} ({duration_ms}ms)", flush=True)
    return response

# Services locaux
OLLAMA_URL = "http://127.0.0.1:11434"
COMFYUI_URL = "http://127.0.0.1:8188"

# Repertoire de travail (la ou se trouve le bridge)
WORKSPACE = os.path.dirname(os.path.abspath(__file__))


def sortie_module(module: str, projet: str, sous_dossier: str | None = None) -> str:
    """Chemin de sortie CANONIQUE : output/<module>/<projet>/[<sous-dossier>].

    Le contrat est enonce dans `aurora_output_paths` : « Every module MUST place
    its outputs under application/output/<module_name>/<project_name>/ ...
    Nothing should ever be scattered at the root of output/ ». Plusieurs routes
    de ce pont l ecrivaient pourtant a la racine d un module, ou dans des
    dossiers hors nomenclature (`output/RESULTATS`, `output/temp_references`).
    Ce raccourci passe par le module de reference plutot que de recomposer un
    chemin a la main.
    """
    import sys as _sys
    chemin_services = os.path.join(WORKSPACE, "python-services")
    if chemin_services not in _sys.path:
        _sys.path.insert(0, chemin_services)
    from aurora_output_paths import get_module_output_dir
    return str(get_module_output_dir(module, project_name=projet,
                                     subfolder=sous_dossier, create=True))


def resolve_node_exe() -> str | None:
    """Localise l'executable Node, meme hors du PATH du process.

    POURQUOI CETTE FONCTION. Le pont resolvait Node par `shutil.which("node")`
    seul. Or il est lance par un service dont le PATH ne contient PAS les
    chemins charges par le profil interactif : sur un poste ou Node est
    installe via nvm — le cas ici, `/home/<user>/.nvm/versions/node/vXX/bin/node`
    — `which` rend None. Deux fonctionnalites vivantes rendaient alors
    « node introuvable » : la generation d'image par `image_cli.mjs` et le
    pipeline Code partage (`bridge_ndjson_runner.mjs`). Le defaut ne vient pas
    d'une absence de Node mais d'une difference d'environnement entre le shell
    et le service.

    Ordre de recherche : variable explicite, PATH, puis les emplacements
    d'installation usuels — nvm (version la plus recente), gestionnaires de
    paquets, et Program Files sous Windows.
    """
    explicite = os.environ.get("NODE_EXE")
    if explicite and os.path.isfile(explicite):
        return explicite

    trouve = shutil.which("node") or shutil.which("node.exe")
    if trouve:
        return trouve

    candidats: list[str] = []

    # nvm : on prend la version la plus recente, par tri numerique des
    # composants (un tri alphabetique placerait v9 apres v24).
    nvm = pathlib.Path.home() / ".nvm" / "versions" / "node"
    if nvm.is_dir():
        def cle(chemin: pathlib.Path):
            nom = chemin.name.lstrip("v")
            try:
                return tuple(int(x) for x in nom.split("."))
            except ValueError:
                return (0,)
        for version in sorted(nvm.iterdir(), key=cle, reverse=True):
            candidats.append(str(version / "bin" / "node"))

    candidats += [
        "/usr/local/bin/node", "/usr/bin/node", "/bin/node",
        "/opt/homebrew/bin/node", "/snap/bin/node",
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
    ]
    for chemin in candidats:
        if os.path.isfile(chemin) and os.access(chemin, os.X_OK):
            return chemin
    return None

def _find_comfyui_path() -> str | None:
    """Detect the ComfyUI installation directory for model path resolution.

    Priority order:
    1. Explicit env vars COMFYUI_DIR / COMFYUI_PATH
    2. AuroraIA-v2 project layout: WORKSPACE/../modele/comfyui/comfyui
       (bridge lives in application/, ComfyUI is in modele/comfyui/comfyui)
    3. AURORA_MODELS env var + comfyui/comfyui subdirectory
    4. Linux/cloud fallback paths (/workspace/comfyui, etc.)
    """
    def _is_comfyui(p: pathlib.Path) -> bool:
        return p.is_dir() and ((p / "main.py").exists() or (p / "models").is_dir())

    # 1. Explicit env var (set by user or start.sh)
    for envvar in ("COMFYUI_DIR", "COMFYUI_PATH"):
        candidate = os.environ.get(envvar, "").strip()
        if candidate and _is_comfyui(pathlib.Path(candidate)):
            return candidate

    # 2. AuroraIA-v2 project structure: bridge is in application/,
    #    ComfyUI lives in modele/comfyui/comfyui (sibling of application/)
    workspace_path = pathlib.Path(WORKSPACE)
    for subpath in ("modele/comfyui/comfyui", "modele/comfyui"):
        p = (workspace_path.parent / subpath).resolve()
        if _is_comfyui(p):
            return str(p)

    # 3. AURORA_MODELS env var (may be set externally or by a parent process)
    aurora_models = os.environ.get("AURORA_MODELS", "").strip()
    if aurora_models:
        for subpath in ("comfyui/comfyui", "comfyui"):
            p = pathlib.Path(aurora_models, subpath)
            if _is_comfyui(p):
                return str(p)

    # 4. Linux / cloud paths (RunPod, Docker)
    for path_str in ("/workspace/comfyui", "/workspace/ComfyUI", "/opt/comfyui", "/opt/ComfyUI"):
        p = pathlib.Path(path_str)
        if _is_comfyui(p):
            return str(p)

    # 5. Recursive scan under modele/ (handles non-standard subdirectory layouts)
    modele_dir = workspace_path.parent / "modele"
    if modele_dir.is_dir():
        for p in sorted(modele_dir.rglob("main.py")):
            candidate = p.parent
            if (candidate / "models").is_dir():
                return str(candidate)

    return None


COMFYUI_PATH = _find_comfyui_path()

# =====================================================================
#  ComfyUI process manager — auto-start on demand
# =====================================================================

COMFYUI_PORT = 8188
_comfyui_process: subprocess.Popen | None = None
_comfyui_lock = threading.Lock()


def _comfyui_is_ready() -> bool:
    # 6s timeout instead of 2s so we don't incorrectly report ComfyUI as down
    # while it is busy loading FLUX models or mid-generation. A shorter timeout
    # made the whole pipeline falsely think ComfyUI was unreachable and drown
    # the user in "ComfyUI local ne repond pas" loops.
    try:
        r = requests.get(f"http://127.0.0.1:{COMFYUI_PORT}/system_stats", timeout=6)
        return r.status_code == 200
    except Exception:
        return False


def _start_comfyui() -> bool:
    """Lance ComfyUI si pas deja en cours. Retourne True quand pret (max 60s)."""
    global _comfyui_process

    if _comfyui_is_ready():
        return True

    with _comfyui_lock:
        if _comfyui_is_ready():
            return True

        comfyui_dir = pathlib.Path(COMFYUI_PATH) if COMFYUI_PATH else None
        if not comfyui_dir or not (comfyui_dir / "main.py").exists():
            return False

        python_exe = comfyui_dir / "venv" / "Scripts" / "python.exe"  # Windows
        if not python_exe.exists():
            python_exe = comfyui_dir / "venv" / "bin" / "python"       # Linux
        if not python_exe.exists():
            python_exe = pathlib.Path(sys.executable)                   # fallback systeme

        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        _comfyui_process = subprocess.Popen(
            [str(python_exe), str(comfyui_dir / "main.py"),
             "--listen", "127.0.0.1", "--port", str(COMFYUI_PORT)],
            cwd=str(comfyui_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )

        for _ in range(60):
            time.sleep(1)
            if _comfyui_is_ready():
                return True
            if _comfyui_process.poll() is not None:
                return False  # processus quitte de lui-meme

        return False


# =====================================================================
#  Helpers
# =====================================================================

def _clean_headers():
    """Headers propres pour proxier vers les services locaux.
    On retire Origin/Referer/Cookie pour eviter les 403 CORS d'Ollama."""
    return {"Content-Type": request.content_type or "application/json"}


def _proxy(target_url, stream=True, timeout=180, data_override=None):
    """Proxy generique vers un service local.
    Forward aussi les query parameters (filename, subfolder, type, etc.)."""
    resp = requests.request(
        method=request.method,
        url=target_url,
        params=request.args,  # Forward query string (?filename=x&type=output...)
        data=request.get_data() if data_override is None else data_override,
        headers=_clean_headers(),
        stream=stream,
        timeout=timeout,
    )
    return Response(
        resp.iter_content(chunk_size=4096),
        status=resp.status_code,
        content_type=resp.headers.get("Content-Type"),
    )



# --- Refactored to application/routes/voice_bp_routes.py ---
# =====================================================================
#  Ollama Proxy  (headers nettoyes → plus de 403)
# =====================================================================

# v82nd : write generated code files to disk + open in detected editor.
# User asked for a "Open in VSCode" button so they can iterate on
# generated code without copy-pasting fence by fence.
def _detect_code_editor():
    """Find the first installed code editor on this machine.
    Order: VSCode → Cursor → Sublime Text → fallback Explorer/Finder.
    Returns dict {name, command} or fallback {name:'explorer', command:'explorer'}."""
    import shutil as _sh
    candidates = [
        ("VSCode", "code"),
        ("VSCode Insiders", "code-insiders"),
        ("Cursor", "cursor"),
        ("Windsurf", "windsurf"),
        ("Sublime Text", "subl"),
        ("WebStorm", "webstorm"),
        ("Atom", "atom"),
    ]
    for name, cmd in candidates:
        if _sh.which(cmd):
            return {"name": name, "command": cmd}
    # Fallback: OS file manager
    if platform.system() == "Windows":
        return {"name": "Explorer Windows", "command": "explorer"}
    if platform.system() == "Darwin":
        return {"name": "Finder", "command": "open"}
    return {"name": "File Manager", "command": "xdg-open"}


@app.route("/api/code/install-model", methods=["POST"])
def code_install_model():
    """Fire-and-forget Ollama pull. Cloudflare cuts at 125s so we
    spawn `ollama pull <name>` as a detached subprocess and return
    immediately. The user can then poll /proxy/ollama/api/tags to
    check when it's done.

    Body: {model: "gemma3:27b"}
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        model = (data.get("model") or "").strip()
        if not model or not all(c.isalnum() or c in ":-._/" for c in model):
            return jsonify({"ok": False, "error": "invalid model name"}), 400
        # Spawn detached so the bridge doesn't hang on the multi-GB pull
        try:
            if platform.system() == "Windows":
                subprocess.Popen(
                    ["ollama", "pull", model],
                    creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_BREAKAWAY_FROM_JOB,
                    shell=True,
                )
            else:
                subprocess.Popen(
                    ["ollama", "pull", model],
                    start_new_session=True,
                )
        except Exception as ex:
            return jsonify({"ok": False, "error": f"spawn failed: {ex}"}), 500
        return jsonify({
            "ok": True,
            "model": model,
            "message": f"pull de {model} lancé en background. Vérifie via /proxy/ollama/api/tags dans quelques minutes.",
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/code/detect-editor", methods=["GET"])
def code_detect_editor():
    """Returns which code editor is installed (for the UI button label)."""
    try:
        editor = _detect_code_editor()
        return jsonify({"ok": True, "editor": editor})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/code/open-folder", methods=["POST"])
def code_open_folder():
    """Write parsed files to a workspace dir and open in detected editor.

    Body: {files: [{path, content}, ...], project_name?: str}
    Writes under {WORKSPACE}/aurora-code-out/{project_name | aurora-N}/
    then spawns the editor as a detached process.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        files = data.get("files") or []
        if not isinstance(files, list) or len(files) == 0:
            return jsonify({"ok": False, "error": "no files"}), 400
        project_name = data.get("project_name") or f"aurora-{int(time.time())}"
        # Sanitize project name (no path traversal)
        safe = "".join(c for c in str(project_name) if c.isalnum() or c in "-_") or "aurora-out"

        # Resolve workspace root: prefer env, fallback to user Desktop/AuroraOut
        ws_root = os.environ.get("AURORA_CODE_WORKSPACE")
        if not ws_root:
            home = os.path.expanduser("~")
            ws_root = os.path.join(home, "Desktop", "AuroraCodeOut")
        try:
            os.makedirs(ws_root, exist_ok=True)
        except Exception:
            ws_root = os.path.join(os.getcwd(), "aurora-code-out")
            os.makedirs(ws_root, exist_ok=True)
        project_dir = os.path.join(ws_root, safe)
        os.makedirs(project_dir, exist_ok=True)

        # Write files (sanitize path: no absolute, no ..)
        written = []
        for f in files:
            if not isinstance(f, dict):
                continue
            rel = str(f.get("path") or "").strip().replace("\\", "/").lstrip("/")
            if not rel or ".." in rel.split("/"):
                continue
            content = f.get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            full = os.path.join(project_dir, rel)
            os.makedirs(os.path.dirname(full) or project_dir, exist_ok=True)
            try:
                with open(full, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(content)
                written.append(rel)
            except Exception:
                pass

        # Detect editor and spawn it on the project dir (detached so the
        # bridge doesn't hang on Code/Cursor lifetime).
        editor = _detect_code_editor()
        try:
            if platform.system() == "Windows":
                subprocess.Popen(
                    [editor["command"], project_dir],
                    creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_BREAKAWAY_FROM_JOB,
                    shell=True,
                )
            else:
                subprocess.Popen(
                    [editor["command"], project_dir],
                    start_new_session=True,
                )
        except Exception as ex:
            return jsonify({
                "ok": False,
                "error": f"editor spawn failed: {ex}",
                "project_dir": project_dir,
                "editor": editor,
                "written": written,
            }), 500

        return jsonify({
            "ok": True,
            "project_dir": project_dir,
            "editor": editor,
            "written": written,
            "count": len(written),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500



# --- Refactored to application/routes/repo_bp_routes.py ---

# --- Refactored to application/routes/ext_bp_routes.py ---
# =====================================================================

_EXT_KEYS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".aurora_ext_keys.json")
_EXT_RATE = {}  # key_hash -> [timestamps]


def _ext_load():
    try:
        with open(_EXT_KEYS_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _ext_save(d):
    try:
        with open(_EXT_KEYS_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _ext_hash(raw):
    return _hashlib.sha256(("aurora-ext-key-v1::" + raw).encode("utf-8")).hexdigest()


def _ext_admin_ok():
    """Gestion de clé (generate/revoke/status). Comme TOUT le bridge, la
    protection de base est « l'URL du tunnel est le secret + c'est la machine
    de l'utilisateur ». On autorise donc la gestion depuis l'app Aurora (qu'elle
    soit ouverte en localhost ou via le tunnel). La CLÉ elle-même, elle, est
    durcie : hash salé stocké (jamais en clair), compare_digest, origin-lock,
    rate-limit. (Si tu veux verrouiller aussi la gestion, ajoute un token de
    setup imprimé dans la console du bridge — laissé en TODO.)"""
    return True


def _ext_get_raw_key():
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        v = auth[7:].strip()
        if v:
            return v
    v = (request.args.get("key") or "").strip()
    if v:
        return v
    try:
        body = request.get_json(silent=True) or {}
        v = str(body.get("key") or "").strip()
        if v:
            return v
    except Exception:
        pass
    return ""


def _ext_auth():
    """→ (ok: bool, record: dict|None, err: str|None)"""
    raw = _ext_get_raw_key()
    if not raw:
        return False, None, "clé manquante (Authorization: Bearer <clé>)"
    h = _ext_hash(raw)
    store = _ext_load()
    for rec in store.get("keys", []):
        if _hmac.compare_digest(str(rec.get("hash", "")), h):
            if rec.get("revoked"):
                return False, None, "clé révoquée"
            return True, rec, None
    return False, None, "clé invalide"


def _ext_origin_for(rec):
    """Origin à autoriser pour cette clé. '' = bloqué.
    `origin` de la clé peut être : vide (tous), un domaine exact, un wildcard
    *.domaine.tld, ou plusieurs séparés par des virgules / espaces (ex:
    'https://site-rep.vercel.app, http://localhost:3000, *.vercel.app')."""
    allowed_raw = (rec or {}).get("origin", "").strip()
    origin = request.headers.get("Origin", "")
    if not allowed_raw:
        return origin or "*"
    for allowed in [a.strip() for a in allowed_raw.replace(",", " ").split() if a.strip()]:
        if allowed == origin:
            return origin
        if allowed.startswith("*.") and origin.endswith(allowed[1:]):
            return origin
    return ""


def _ext_cors(resp, rec=None):
    o = _ext_origin_for(rec)
    if o:
        resp.headers["Access-Control-Allow-Origin"] = o
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        resp.headers["Access-Control-Max-Age"] = "600"
    return resp


def _ext_rate_ok(key_hash):
    now = time.time()
    bucket = _EXT_RATE.setdefault(key_hash, [])
    while bucket and now - bucket[0] > 60:
        bucket.pop(0)
    if len(bucket) >= 40:
        return False
    bucket.append(now)
    return True


def _ext_default_model():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=6)
        models = r.json().get("models", []) if r.ok else []
        candidates = []
        for m in models:
            if not isinstance(m, dict):
                continue
            name = m.get("name", "")
            if "embed" in name.lower():
                continue
            candidates.append(name)
        for pref in ("qwen3-coder-next:q4_K_M", "qwen-cyber:latest", "deepseek-r1:32b", "qwen3-coder:30b", "orcarouter", "qwen3-vl:8b"):
            for n in candidates:
                if pref.lower() in n.lower():
                    return n
        if candidates:
            return candidates[0]
    except Exception:
        pass
    return "qwen3-coder-next:q4_K_M"


# --- gestion de clé (LOCAL only) — plusieurs clés actives possibles
#     (ex: une clé "prod" verrouillée sur ton domaine + une clé "dev"). ---
def _ext_key_public(k):
    return {"label": k.get("label", ""), "origin": k.get("origin", ""),
            "created": k.get("created", ""), "prefix": k.get("prefix", "")}


@app.route("/api/ext/key/status", methods=["GET"])
def ext_key_status():
    if not _ext_admin_ok():
        return jsonify({"error": "gestion de clé accessible uniquement en local"}), 403
    active = [k for k in _ext_load().get("keys", []) if not k.get("revoked")]
    return jsonify({
        "exists": len(active) > 0,
        "count": len(active),
        "keys": [_ext_key_public(k) for k in active],
        # compat champ "à plat" = la plus récente
        **(_ext_key_public(active[-1]) if active else {}),
    })


@app.route("/api/ext/key/generate", methods=["POST"])
def ext_key_generate():
    if not _ext_admin_ok():
        return jsonify({"error": "gestion de clé accessible uniquement en local"}), 403
    body = request.get_json(silent=True) or {}
    origin = str(body.get("origin") or "").strip()
    label = (str(body.get("label") or "site externe").strip())[:60] or "site externe"
    replace_all = bool(body.get("replace_all"))  # si true → révoque toutes les anciennes
    raw = "aur_" + _secrets.token_urlsafe(32)
    h = _ext_hash(raw)
    store = _ext_load()
    keys = store.get("keys", [])
    if replace_all:
        for k in keys:
            k["revoked"] = True
    keys.append({
        "hash": h,
        "prefix": raw[:11] + "…",
        "origin": origin,
        "label": label,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "revoked": False,
    })
    _ext_save({"keys": keys})
    return jsonify({"ok": True, "key": raw, "origin": origin, "label": label})


@app.route("/api/ext/key/revoke", methods=["POST"])
def ext_key_revoke():
    if not _ext_admin_ok():
        return jsonify({"error": "gestion de clé accessible uniquement en local"}), 403
    body = request.get_json(silent=True) or {}
    prefix = str(body.get("prefix") or "").strip()  # si fourni → ne révoque QUE celle-là
    store = _ext_load()
    keys = store.get("keys", [])
    n = 0
    for k in keys:
        if (not prefix or k.get("prefix") == prefix) and not k.get("revoked"):
            k["revoked"] = True
            n += 1
    _ext_save({"keys": keys})
    return jsonify({"ok": True, "revoked": n})


# --- endpoints publics (auth Bearer + CORS verrouillé) ---
@app.route("/api/ext/ping", methods=["GET", "OPTIONS"])
def ext_ping():
    if request.method == "OPTIONS":
        return _ext_cors(Response(status=204))
    ok, rec, err = _ext_auth()
    if not ok:
        return _ext_cors(jsonify({"ok": False, "error": err})), 401
    if not _ext_origin_for(rec):
        return jsonify({"ok": False, "error": "origin non autorisé pour cette clé"}), 403
    return _ext_cors(jsonify({"ok": True, "model": _ext_default_model()}), rec)


@app.route("/api/ext/chat", methods=["POST", "OPTIONS"])
def ext_chat():
    if request.method == "OPTIONS":
        return _ext_cors(Response(status=204))
    ok, rec, err = _ext_auth()
    if not ok:
        return _ext_cors(jsonify({"error": err})), 401
    if not _ext_origin_for(rec):
        return jsonify({"error": "origin non autorisé pour cette clé"}), 403
    if not _ext_rate_ok(str(rec.get("hash", ""))):
        return _ext_cors(jsonify({"error": "trop de requêtes — réessaie dans une minute"}), rec), 429
    body = request.get_json(silent=True) or {}
    msgs = body.get("messages")
    if not isinstance(msgs, list) or not msgs:
        p = str(body.get("prompt") or "").strip()
        if not p:
            return _ext_cors(jsonify({"error": "champ 'messages' (liste) ou 'prompt' (texte) requis"}), rec), 400
        msgs = [{"role": "user", "content": p}]
    clean = []
    for m in msgs[-20:]:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role not in ("user", "assistant", "system"):
            role = "user"
        content = str(m.get("content") or "")[:8000]
        if content:
            clean.append({"role": role, "content": content})
    if not clean:
        return _ext_cors(jsonify({"error": "aucun message valide"}), rec), 400
    label = rec.get("label") or "ce site"
    system = (
        "Tu es l'assistant IA local d'Aurora, intégré dans le site « " + label + " ». "
        "Tu es exécuté en local chez l'utilisateur (modèle Ollama). Réponds de façon "
        "concise, utile, chaleureuse et directe. Si on te demande quelque chose qui "
        "sort du contexte du site, réponds quand même utilement."
    )
    payload = {
        "model": str(body.get("model") or "").strip() or _ext_default_model(),
        "messages": [{"role": "system", "content": system}] + clean,
        "stream": False,
        "options": {"temperature": max(0.0, min(1.5, float(body.get("temperature", 0.7) or 0.7)))},
    }
    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=180)
        data = r.json() if r.ok else {}
        reply = ""
        if isinstance(data, dict):
            reply = (data.get("message") or {}).get("content", "") or data.get("response", "")
        if not reply:
            return _ext_cors(jsonify({"error": "réponse vide du modèle"}), rec), 502
        return _ext_cors(jsonify({"reply": reply, "model": payload["model"]}), rec)
    except Exception as e:
        return _ext_cors(jsonify({"error": f"modèle non joignable: {e}"}), rec), 502


# --- 3D via API : génère un GLB (boîtier, composant…) à partir d'un prompt.
#     Asynchrone (le pipeline FLUX→TRELLIS.2→auto_rescue prend des minutes) :
#     POST /api/ext/3d/generate → {job_id}
#     GET  /api/ext/3d/status/<job_id> → {state, elapsed_s, step, glb_url?, audit?}
#     L'auto_rescue interne du pipeline corrige déjà la géométrie ; si le score
#     final reste sous le seuil, on retente UNE fois automatiquement, sinon
#     l'état passe "failed" (le consommateur peut relancer generate). Priorité
#     PRÉCISION / réalisme du rendu — pas la vitesse.
_EXT_3D_JOBS = {}  # job_id -> {state, started, finished, step, prompt, run_id, glb, glb_url, audit, error, attempts}
_EXT_3D_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "3d")
_EXT_3D_MIN_SCORE = 70  # seuil de "rendu correct" — sinon retry auto


def _ext_3d_pick_glb(run_id):
    """Trouve le .glb produit pour run_id dans output/3d/."""
    try:
        cands = []
        for fn in os.listdir(_EXT_3D_DIR):
            if fn.endswith(".glb") and run_id in fn:
                cands.append(fn)
        if not cands:
            return None
        # préfère le *_mesh.glb / le plus récent
        cands.sort(key=lambda f: (0 if "mesh" in f else 1, -os.path.getmtime(os.path.join(_EXT_3D_DIR, f))))
        return cands[0]
    except Exception:
        return None


def _ext_3d_score(audit):
    """Extrait un score 0-100 de l'audit aurora.pipeline.v1 (best effort)."""
    if not isinstance(audit, dict):
        return None
    for path in (("quality", "score"), ("score",), ("rescue", "final_score"), ("audit", "score"), ("final", "score")):
        node = audit
        ok = True
        for k in path:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                ok = False
                break
        if ok and isinstance(node, (int, float)):
            return float(node) if node > 1 else float(node) * 100.0
    return None


def _ext_3d_worker(job_id):
    job = _EXT_3D_JOBS.get(job_id)
    if not job:
        return
    workspace = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(workspace, "python-services", "aurora_3d_pipeline.py")
    if not os.path.isfile(script_path):
        job["state"] = "failed"; job["error"] = "aurora_3d_pipeline.py introuvable"; job["finished"] = time.time()
        return
    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        job["attempts"] = attempt
        job["state"] = "running"
        job["step"] = ("synthèse référence → TRELLIS.2 → post-traitement / rescue" if attempt == 1
                       else "rendu insuffisant — nouvelle passe automatique")
        run_id = job["run_id"] if attempt == 1 else (job["run_id"] + f"_r{attempt}")
        cmd = [sys.executable, script_path, "--prompt", job["prompt"], "--run-id", run_id,
               "--output-dir", _EXT_3D_DIR, "--purpose", "visual_preview"]
        if job.get("subject_kind"):
            cmd += ["--subject-kind", job["subject_kind"]]
        if job.get("force") or attempt > 1:
            cmd.append("--force")
        try:
            # MEME PARITE que /api/3d/run-pipeline: sans ces budgets, la voie
            # extension/tunnel tombait en OOM TRELLIS la ou le CLI passait.
            _env_ext = {**os.environ}
            _env_ext.setdefault("AURORA_MEM_MAX_GB", "26")
            _env_ext.setdefault("AURORA_MEM_SWAP_MAX_GB", "40")
            _env_ext.setdefault("AURORA_LLM_4BIT", "1")
            proc = subprocess.run(cmd, capture_output=True, timeout=2400,
                                  check=False, env=_env_ext)
        except subprocess.TimeoutExpired:
            job["state"] = "failed"; job["error"] = "pipeline timeout (40 min)"; job["finished"] = time.time()
            return
        audit = None
        if proc.returncode == 0:
            try:
                audit = json.loads(proc.stdout.decode("utf-8", errors="replace"))
            except Exception:
                audit = None
        else:
            job["last_stderr"] = (proc.stderr or b"").decode("utf-8", errors="replace")[-400:]
        glb = _ext_3d_pick_glb(run_id) or (_ext_3d_pick_glb(job["run_id"]) if attempt == 1 else None)
        score = _ext_3d_score(audit)
        job["audit"] = audit
        job["score"] = score
        if glb and (score is None or score >= _EXT_3D_MIN_SCORE):
            job["glb"] = glb
            job["glb_url"] = f"/api/3d/file/{glb}"  # servi par la route fichiers 3D existante
            job["state"] = "done"
            job["finished"] = time.time()
            return
        # sinon : si on a un GLB mais score trop bas → retry ; si pas de GLB → retry
        if attempt >= max_attempts:
            job["state"] = "failed"
            # 30/07 (audit): le motif REEL (stderr) etait garde en interne
            # mais jamais expose — l'utilisateur tunnel ne voyait qu'un
            # « aucun GLB produit » indiagnosticable.
            _stderr_reel = (job.get("last_stderr") or "").strip()
            job["error"] = ("rendu rejeté (score %s < %s) après %d passes" % (round(score) if score else "?", _EXT_3D_MIN_SCORE, attempt)
                            if glb else ("aucun GLB produit après %d passes" % attempt
                                         + (" — cause: " + _stderr_reel[-300:] if _stderr_reel else "")))
            if glb:
                job["glb"] = glb; job["glb_url"] = f"/api/3d/file/{glb}"  # on l'expose quand même (best effort)
            job["finished"] = time.time()
            return
        # else loop → nouvelle passe


@app.route("/api/ext/3d/generate", methods=["POST", "OPTIONS"])
def ext_3d_generate():
    if request.method == "OPTIONS":
        return _ext_cors(Response(status=204))
    ok, rec, err = _ext_auth()
    if not ok:
        return _ext_cors(jsonify({"error": err})), 401
    if not _ext_origin_for(rec):
        return jsonify({"error": "origin non autorisé pour cette clé"}), 403
    if not _ext_rate_ok(str(rec.get("hash", ""))):
        return _ext_cors(jsonify({"error": "trop de requêtes — réessaie dans une minute"}), rec), 429
    body = request.get_json(silent=True) or {}
    prompt = (str(body.get("prompt") or "")).strip()
    if not prompt:
        return _ext_cors(jsonify({"error": "champ 'prompt' requis (ex: 'boîtier industriel IP65 avec écran LCD 3.5\" et 4 LED status')"}), rec), 400
    prompt = prompt[:600]
    job_id = "ext3d_" + _secrets.token_hex(6)
    run_id = "ext_" + time.strftime("%Y%m%d_%H%M%S") + "_" + _secrets.token_hex(3)
    _EXT_3D_JOBS[job_id] = {
        "state": "queued", "started": time.time(), "finished": None,
        "step": "en file", "prompt": prompt, "run_id": run_id,
        "subject_kind": (str(body.get("subject_kind") or "").strip() or None),
        "force": bool(body.get("force") or False),
        "glb": None, "glb_url": None, "audit": None, "score": None,
        "error": None, "attempts": 0, "label": rec.get("label"),
    }
    threading.Thread(target=_ext_3d_worker, args=(job_id,), daemon=True).start()
    return _ext_cors(jsonify({"ok": True, "job_id": job_id, "poll": f"/api/ext/3d/status/{job_id}"}), rec)


@app.route("/api/ext/3d/status/<job_id>", methods=["GET", "OPTIONS"])
def ext_3d_status(job_id):
    if request.method == "OPTIONS":
        return _ext_cors(Response(status=204))
    ok, rec, err = _ext_auth()
    if not ok:
        return _ext_cors(jsonify({"error": err})), 401
    if not _ext_origin_for(rec):
        return jsonify({"error": "origin non autorisé pour cette clé"}), 403
    job = _EXT_3D_JOBS.get(job_id)
    if not job:
        return _ext_cors(jsonify({"error": "job inconnu (expiré ?)"}), rec), 404
    now = time.time()
    elapsed = round((job["finished"] or now) - job["started"], 1)
    out = {
        "job_id": job_id, "state": job["state"], "elapsed_s": elapsed,
        "step": job["step"], "attempts": job["attempts"],
        "score": (round(job["score"]) if isinstance(job.get("score"), (int, float)) else None),
    }
    if job["state"] == "done":
        out["glb_url"] = job["glb_url"]
        out["audit"] = job["audit"]
    elif job["state"] == "failed":
        out["error"] = job["error"]
        if job.get("glb_url"):
            out["glb_url"] = job["glb_url"]  # best-effort, à inspecter
            out["audit"] = job["audit"]
    return _ext_cors(jsonify(out), rec)


# --- /api/ext/do — endpoint UNIVERSEL : tu envoies une demande en langage
#     naturel, il classe (chat / code / mesh3d) et dispatche vers le bon
#     traitement. "Plug and play" pour : Q&R, génération de code (sketch
#     Arduino .ino, firmware ESP/PlatformIO, scripts, configs, code dans
#     ~tous langages…), et mesh 3D. Les capacités lourdes hors-API (image
#     FLUX, vidéo Wan2.2, simulateur physique/chimie) renvoient un pointeur
#     vers l'app Aurora — pas (encore) exécutables via l'API.
_DO_CLASSIFY_SYS = (
    "Tu es un routeur. On te donne une demande utilisateur. Réponds UNIQUEMENT "
    "par un seul mot parmi : chat | code | mesh3d | image | video | sim | other. "
    "code = écrire/générer du code, un sketch Arduino, un firmware ESP, un script, "
    "une config, une 'création d'OS'/firmware embarqué (= écrire le code), etc. "
    "mesh3d = créer/générer un objet/modèle 3D, un boîtier, un composant en 3D, un GLB. "
    "image = générer une image 2D. video = générer une vidéo. sim = simulation physique/chimie. "
    "chat = question, explication, conseil, conversation. other = rien de ce qui précède. "
    "Un seul mot, en minuscules, rien d'autre."
)
_DO_CODE_SYS = (
    "Tu es l'ingénieur d'Aurora (module Code, niveau expert). On te donne une demande. "
    "Produis du code idiomatique, complet, prêt à compiler/flasher/exécuter — y compris : "
    "sketch Arduino (.ino), firmware ESP32/ESP8266 (Arduino-core OU PlatformIO), scripts "
    "Python/JS/Bash, configs, code C/C++/Rust, etc. Si c'est de l'embarqué, indique la carte "
    "cible, les libs requises, le câblage et comment flasher (arduino-cli / pio / esptool). "
    "Réponds en Markdown : un court paragraphe d'explication, puis le(s) bloc(s) de code "
    "fence-és avec le bon langage et un commentaire de nom de fichier en tête de chaque bloc."
)


@app.route("/api/ext/do", methods=["POST", "OPTIONS"])
def ext_do():
    if request.method == "OPTIONS":
        return _ext_cors(Response(status=204))
    ok, rec, err = _ext_auth()
    if not ok:
        return _ext_cors(jsonify({"error": err})), 401
    if not _ext_origin_for(rec):
        return jsonify({"error": "origin non autorisé pour cette clé"}), 403
    if not _ext_rate_ok(str(rec.get("hash", ""))):
        return _ext_cors(jsonify({"error": "trop de requêtes — réessaie dans une minute"}), rec), 429
    body = request.get_json(silent=True) or {}
    req_text = str(body.get("request") or body.get("prompt") or "").strip()[:2000]
    if not req_text:
        return _ext_cors(jsonify({"error": "champ 'request' (ta demande en langage naturel) requis"}), rec), 400
    forced = str(body.get("kind") or "").strip().lower()
    kind = forced if forced in ("chat", "code", "mesh3d", "image", "video", "sim", "other") else None
    model = _ext_default_model()
    # 1) classification (sauf si forcée)
    if not kind:
        try:
            r = requests.post(f"{OLLAMA_URL}/api/chat", json={
                "model": model, "stream": False,
                "messages": [{"role": "system", "content": _DO_CLASSIFY_SYS}, {"role": "user", "content": req_text}],
                "options": {"temperature": 0.0},
            }, timeout=60)
            raw = ((r.json().get("message") or {}).get("content", "") if r.ok else "").strip().lower()
            for k in ("mesh3d", "code", "image", "video", "sim", "chat", "other"):
                if k in raw:
                    kind = k
                    break
        except Exception:
            kind = None
        if not kind:
            kind = "chat"
    # 2) dispatch
    if kind == "mesh3d":
        job_id = "ext3d_" + _secrets.token_hex(6)
        run_id = "ext_" + time.strftime("%Y%m%d_%H%M%S") + "_" + _secrets.token_hex(3)
        _EXT_3D_JOBS[job_id] = {
            "state": "queued", "started": time.time(), "finished": None, "step": "en file",
            "prompt": req_text, "run_id": run_id, "subject_kind": None, "force": False,
            "glb": None, "glb_url": None, "audit": None, "score": None, "error": None,
            "attempts": 0, "label": rec.get("label"),
        }
        threading.Thread(target=_ext_3d_worker, args=(job_id,), daemon=True).start()
        return _ext_cors(jsonify({"kind": "mesh3d", "job_id": job_id, "poll": f"/api/ext/3d/status/{job_id}",
                                  "note": "génération 3D asynchrone — poll le statut (~20-30 min, refait auto si rendu rejeté)."}), rec)
    if kind == "code":
        try:
            r = requests.post(f"{OLLAMA_URL}/api/chat", json={
                "model": model, "stream": False,
                "messages": [{"role": "system", "content": _DO_CODE_SYS}, {"role": "user", "content": req_text}],
                "options": {"temperature": 0.4},
            }, timeout=300)
            content = ((r.json().get("message") or {}).get("content", "") if r.ok else "")
            if not content:
                return _ext_cors(jsonify({"error": "réponse vide du modèle"}), rec), 502
            return _ext_cors(jsonify({"kind": "code", "model": model, "result": content,
                                      "note": "code généré (Markdown avec blocs fence-és + noms de fichiers). Compile/flash côté toi (arduino-cli, pio, esptool…)."}), rec)
        except Exception as e:
            return _ext_cors(jsonify({"error": f"modèle non joignable: {e}"}), rec), 502
    if kind in ("image", "video", "sim"):
        return _ext_cors(jsonify({"kind": kind, "supported": False,
                                  "note": f"« {kind} » n'est pas (encore) exécutable via l'API publique — utilise l'app Aurora (modules Image / Vidéo / Simulateur). L'API gère : chat, code, mesh3d."}), rec)
    # chat / other → on répond comme un assistant
    try:
        sysmsg = ("Tu es l'assistant IA local d'Aurora intégré au site « " + (rec.get("label") or "ce site") +
                  " ». Réponds de façon concise, utile, chaleureuse, directe.")
        r = requests.post(f"{OLLAMA_URL}/api/chat", json={
            "model": model, "stream": False,
            "messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": req_text}],
            "options": {"temperature": 0.7},
        }, timeout=180)
        reply = ((r.json().get("message") or {}).get("content", "") if r.ok else "")
        if not reply:
            return _ext_cors(jsonify({"error": "réponse vide du modèle"}), rec), 502
        return _ext_cors(jsonify({"kind": "chat", "model": model, "reply": reply}), rec)
    except Exception as e:
        return _ext_cors(jsonify({"error": f"modèle non joignable: {e}"}), rec), 502


# Sert un fichier .glb de output/3d/ (réutilisé par le widget et le site).
def _chemin_3d_sur(rel: str):
    """Resout un chemin RELATIF sous output/3d en refusant toute evasion.

    Avant (03/09): la route appliquait os.path.basename(), donc SEULE la racine
    de output/3d etait servie — tout modele range dans un sous-dossier etait
    inatteignable depuis le visualiseur. On accepte desormais les sous-chemins,
    en verifiant par realpath que la cible reste bien sous output/3d (les liens
    symboliques sont resolus, donc un lien qui sort de l'arbre est refuse).
    """
    racine = os.path.realpath(_EXT_3D_DIR)
    cible = os.path.realpath(os.path.join(_EXT_3D_DIR, rel.lstrip("/")))
    if cible != racine and not cible.startswith(racine + os.sep):
        return None
    return cible


@app.route("/api/3d/list", methods=["GET"])
def three_d_list():
    """Inventaire RECURSIF des GLB sous output/3d, pour le visualiseur.

    Le visualiseur construisait sa liste en grattant un listing de repertoire
    Vite, qui ne le sert pas (404). D'ou une colonne « aucun GLB trouve » alors
    que les modeles existaient.
    """
    racine = os.path.realpath(_EXT_3D_DIR)
    # Par defaut: GLB seuls — le visualiseur charge des modeles, pas des images.
    # `?images=1` ajoute les references PNG pour une galerie.
    _avec_images = request.args.get("images") in ("1", "true", "oui")
    _exts = ((".glb", ".gltf", ".png", ".jpg", ".jpeg", ".webp")
             if _avec_images else (".glb", ".gltf"))
    items = []
    for dossier, sous, fichiers in os.walk(racine, followlinks=False):
        sous[:] = [d for d in sous if not d.startswith(".")]
        for f in fichiers:
            if not f.lower().endswith(_exts):
                continue
            plein = os.path.join(dossier, f)
            try:
                st = os.stat(plein)
            except OSError:
                continue
            rel = os.path.relpath(plein, racine).replace(os.sep, "/")
            items.append({
                "nom": f,
                "chemin": rel,
                "dossier": os.path.dirname(rel) or ".",
                "url": "/api/3d/file/" + rel,
                "octets": st.st_size,
                "modifie": int(st.st_mtime),
            })
    items.sort(key=lambda x: (-x["modifie"], x["chemin"]))
    resp = jsonify({"ok": True, "racine": "output/3d", "total": len(items), "modeles": items})
    resp.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    return resp


@app.route("/api/3d/file/<path:fname>", methods=["GET"])
def three_d_file(fname):
    # Les REFERENCES sont des PNG. Sans elles ici, l'interface n'avait aucune
    # route pour les afficher et montrait un point d'interrogation (03/09).
    _types = {".glb": "model/gltf-binary", ".gltf": "model/gltf+json",
              ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".webp": "image/webp"}
    _ext = os.path.splitext(fname.lower())[1]
    if _ext not in _types:
        return jsonify({"error": "type non autorisé"}), 400
    path = _chemin_3d_sur(fname)
    if path is None:
        return jsonify({"error": "chemin hors de output/3d"}), 403
    if not os.path.isfile(path):
        return jsonify({"error": "introuvable"}), 404
    resp = send_file(path, mimetype=_types[_ext], conditional=True)
    resp.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


# La doc d'intégration API site externe. Route explicite car le catch-all Vite
# bloque l'extension .md (anti-leak de source). Accessible à <tunnel>/aurora-api.md.
@app.route("/aurora-api.md", methods=["GET", "OPTIONS"])
def aurora_api_doc():
    if request.method == "OPTIONS":
        r = Response(status=204); r.headers["Access-Control-Allow-Origin"] = "*"; return r
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "public", "aurora-api.md"), os.path.join(here, "dist", "aurora-api.md")):
        if os.path.isfile(cand):
            resp = send_file(cand, mimetype="text/markdown; charset=utf-8", conditional=True)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Cache-Control"] = "public, max-age=300"
            return resp
    return jsonify({"error": "aurora-api.md introuvable"}), 404



# --- Refactored to application/routes/comfy_proxy_bp_routes.py ---

# --- Refactored to application/routes/hardware_bp_routes.py ---

# --- Refactored to application/routes/status_bp_routes.py ---

# --- Refactored to application/routes/web_action_bp_routes.py ---

# --- Refactored to application/routes/web_search_bp_routes.py ---

# --- Refactored to application/routes/python_prog_bp_routes.py ---

# --- Refactored to application/routes/asset_bp_routes.py ---

# --- Refactored to application/routes/ollama_list_bp_routes.py ---

# --- Refactored to application/routes/upload_bp_routes.py ---

# --- Refactored to application/routes/comfy_life_bp_routes.py ---

# --- Refactored to application/routes/ollama_enh_bp_routes.py ---

# --- Refactored to application/routes/sysinfo_bp_routes.py ---

# --- Refactored to application/routes/cowork_file_bp_routes.py ---

# --- Refactored to application/routes/cowork_ext_bp_routes.py ---
# =====================================================================
#  Entrypoint
# =====================================================================

# Audited local adapters use the same bridge as the UI and tunnel.
import sys as _training_sys
from pathlib import Path as _TrainingPath
_training_sys.path.insert(0, str(_TrainingPath(__file__).resolve().parent.parent))
from auto_rl.integration import register_routes as _register_training_routes
_register_training_routes(app, _proxy)


def sync_tunnel_url_to_gist():
    import subprocess, os
    try:
        # Il FAUT utiliser WORKSPACE car bridge_server tourne dans 'application/'
        tunnel_file = os.path.join(WORKSPACE, "tunnel.txt")
        if not os.path.exists(tunnel_file):
            tunnel_file = os.path.join(WORKSPACE, "tunnel_url.txt")
        
        if os.path.exists(tunnel_file):
            print(f"🔗 Syncing tunnel URL from {tunnel_file} to GitHub Gist for remote clients...")
            subprocess.run(["gh", "gist", "edit", "4510a5d538cef3e262ec38b6acc5bde0", "-a", "tunnel_sync.txt", tunnel_file], 
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✅ Tunnel URL synced to Gist.")
    except Exception as e:
        pass


if __name__ == "__main__":
    sync_tunnel_url_to_gist()
    print("=" * 60)
    print("  BRIDGE AURORA — Port 3001")
    print("=" * 60)
    print("  Voice:    /api/voice/stt, /api/voice/tts, /api/voice/tts-audio, /api/voice/stt-info")
    print("  Ollama:   /proxy/ollama/*, /api/ollama/chat, /api/ollama/models, /api/ollama/pull")
    print("  ComfyUI:  /proxy/comfy/*, /api/comfyui/status, /api/comfyui/start, /api/comfyui/image")
    print("  Runtime:  /api/hardware, /api/runtime/inspect, /api/system/info")
    print("  FS:       /api/fs/*, /api/asset/*")
    print("  Python:   /api/python/run, /api/python/run-async, /api/python/job/<id>")
    print("  Cinema:   /api/cinema/storyboard, /api/cinema/generate, /api/cinema/job/<id>")
    print("  Voice:    /api/voice/library, /api/voice/extract, /api/voice/register, /api/voice/synthesize")
    print("  Cowork:   /api/cowork/read, /api/cowork/write, /api/cowork/delete (workspace-bound)")
    print("=" * 60)
    _expected = str(pathlib.Path(WORKSPACE).parent / "modele" / "comfyui" / "comfyui")
    print(f"  WORKSPACE       = {WORKSPACE}", flush=True)
    print(f"  ComfyUI cherche = {_expected}", flush=True)
    print(f"  COMFYUI_PATH    = {COMFYUI_PATH or 'NON DETECTE'}", flush=True)
    # Dev auto-reload: set AURORA_BRIDGE_DEV=1 to get Flask to reload this file
    # when it changes. Off by default so the production start.bat isn't noisy.
    dev_reload = os.environ.get("AURORA_BRIDGE_DEV", "").strip() in ("1", "true", "yes")
    if dev_reload:
        print("  DEV RELOAD       = ON  (AURORA_BRIDGE_DEV=1)")
    # Self-watch : when bridge_server.py is overwritten on disk (e.g. by a
    # /loop iteration), re-exec the process so the new routes are live
    # without any user action. Disabled with AURORA_BRIDGE_NO_WATCH=1.
    from routes.cowork_ext_bp_routes import _start_self_watch_once, _start_ollama_warmup_once, _start_qwen3vl_pull_once, _pick_vision_model_or_default, _get_free_vram_gb
    _start_self_watch_once()
    print("  SELF-WATCH       = ON  (auto re-exec sur changement de bridge_server.py)")
    # v82ld — fire-and-forget warmup of qwen3:14b so the first extract-structured
    # request doesn t pay the ~11s cold-load. Daemon thread, never blocks boot.
    _start_ollama_warmup_once("qwen3:14b")
    print("  WARMUP           = qwen3:14b (background, non-blocking)")
    # v82ld — best-effort conditional pull of qwen3-vl:8b for vision extract.
    # Skips silently on low VRAM / no GPU / no Ollama / already installed.
    _start_qwen3vl_pull_once("qwen3-vl:8b")
    print("  QWEN3-VL PULL    = conditional (skip if low VRAM / already installed)")
    # v82le — log the adaptive vision-picker decision once, so the user can see
    # which vision model the bridge would pick if extract-structured were
    # called with an image right now. Pure observability, zero side effects.
    try:
        _vision_pick, _vision_reason, _vision_kind = _pick_vision_model_or_default("qwen3-vl:8b")
        _free_gb = _get_free_vram_gb()
        print(f"  VISION PICKER    = {_vision_pick} (free VRAM ~{_free_gb} GB)")
        print(f"  VISION REASON    = {_vision_reason} [{_vision_kind}]")
    except Exception as _e:  # noqa: BLE001
        print(f"  VISION PICKER    = (probe failed: {_e})")
    print("=" * 60)
    try:
        from routes.voice_bp_routes import voice_bp
        app.register_blueprint(voice_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.fs_bp_routes import fs_bp
        app.register_blueprint(fs_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.cinema_bp_routes import cinema_bp
        app.register_blueprint(cinema_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.python_bp_routes import python_bp
        app.register_blueprint(python_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.cli_bp_routes import cli_bp
        app.register_blueprint(cli_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.postgres_bp_routes import postgres_bp
        app.register_blueprint(postgres_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.s3_bp_routes import s3_bp
        app.register_blueprint(s3_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.iot_bp_routes import iot_bp
        app.register_blueprint(iot_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.vite_bp_routes import vite_bp
        app.register_blueprint(vite_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.connect_bp_routes import connect_bp
        app.register_blueprint(connect_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.repo_bp_routes import repo_bp
        app.register_blueprint(repo_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.ext_bp_routes import ext_bp
        app.register_blueprint(ext_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.comfy_proxy_bp_routes import comfy_proxy_bp
        app.register_blueprint(comfy_proxy_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.hardware_bp_routes import hardware_bp
        app.register_blueprint(hardware_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.status_bp_routes import status_bp
        app.register_blueprint(status_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.web_action_bp_routes import web_action_bp
        app.register_blueprint(web_action_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.web_search_bp_routes import web_search_bp
        app.register_blueprint(web_search_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.python_prog_bp_routes import python_prog_bp
        app.register_blueprint(python_prog_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.asset_bp_routes import asset_bp
        app.register_blueprint(asset_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.ollama_list_bp_routes import ollama_list_bp
        app.register_blueprint(ollama_list_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.upload_bp_routes import upload_bp
        app.register_blueprint(upload_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.comfy_life_bp_routes import comfy_life_bp
        app.register_blueprint(comfy_life_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.ollama_enh_bp_routes import ollama_enh_bp
        app.register_blueprint(ollama_enh_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.sysinfo_bp_routes import sysinfo_bp
        app.register_blueprint(sysinfo_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.cowork_file_bp_routes import cowork_file_bp
        app.register_blueprint(cowork_file_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    try:
        from routes.cowork_ext_bp_routes import cowork_ext_bp
        app.register_blueprint(cowork_ext_bp)
    except Exception as e:
        print(f'Registration failed for {mod_name}: {e}')
    app.run(host="0.0.0.0", port=3001, threaded=True, debug=dev_reload, use_reloader=dev_reload)
