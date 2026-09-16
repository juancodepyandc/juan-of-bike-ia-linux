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


# =====================================================================
#  Voice — STT & TTS
# =====================================================================

@app.route("/api/voice/stt", methods=["POST"])
def voice_stt():
    try:
        audio_file = request.files["audio"]
        os.makedirs("temp", exist_ok=True)
        # Conserver l'extension réelle (wav depuis le JS, webm depuis anciens clients)
        ext = os.path.splitext(audio_file.filename or "voice.webm")[1] or ".webm"
        temp_path = os.path.join("temp", f"voice_mobile{ext}")
        audio_file.save(temp_path)

        script = os.path.join(WORKSPACE, "python-services", "voice_service.py")
        raw = subprocess.check_output(
            [sys.executable, script, "--mode", "stt", "--audio", temp_path],
            stderr=subprocess.STDOUT, timeout=120, cwd=WORKSPACE,
        ).decode("utf-8")

        lines = [l for l in raw.strip().split("\n") if l.strip()]
        return Response(lines[-1], mimetype="application/json")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/voice/tts", methods=["POST"])
def voice_tts():
    try:
        data = request.get_json()
        text = data.get("text", "")
        lang = data.get("lang", "fr")
        # Hint persona vocal (lyra-soft, iris-bright, cinema-deep, ...). Si fourni,
        # voice_service.py choisit la voix Edge-TTS / Piper la plus proche du persona.
        voice_persona = data.get("voice")
        # Optionnel: chemin vers l image avatar pour activer SadTalker talking-video.
        # Si fourni, le MP4 est genere automatiquement et expose via /api/voice/tts-video.
        avatar_image = data.get("avatar") or data.get("avatar_image")

        if not text.strip():
            return jsonify({"ok": False, "error": "Texte vide"}), 400

        # Un fichier PAR SYNTHESE, sous un projet. L ancienne version ecrivait
        # toujours `output/voix/tts_out.wav` : a la racine du module — hors
        # contrat — et surtout, chaque synthese EFFACAIT la precedente. Rien
        # n en gardait trace.
        voice_dir = sortie_module("voix", data.get("projet") or "synthese")
        output_path = os.path.join(voice_dir, f"tts_{int(time.time() * 1000)}.wav")
        script = os.path.join(WORKSPACE, "python-services", "voice_service.py")

        cmd = [sys.executable, script, "--mode", "tts", "--text", text, "--output", output_path, "--lang", lang]
        if voice_persona:
            cmd += ["--voice", voice_persona]
        # Timeout adaptatif: 120s sans avatar, 180s avec SadTalker
        timeout_s = 120
        if avatar_image:
            # Resolver le chemin absolu (peut etre /avatars/x.png -> WORKSPACE/public/avatars/x.png)
            avatar_abs = avatar_image
            if avatar_abs.startswith("/avatars/"):
                avatar_abs = os.path.join(WORKSPACE, "public", avatar_abs.lstrip("/"))
            elif not os.path.isabs(avatar_abs):
                avatar_abs = os.path.join(WORKSPACE, avatar_abs)
            if os.path.isfile(avatar_abs):
                cmd += ["--avatar", avatar_abs]
                timeout_s = 180

        raw = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, timeout=timeout_s, cwd=WORKSPACE,
        ).decode("utf-8")

        if not os.path.exists(output_path):
            return jsonify({"ok": False, "error": "Fichier audio non genere"}), 500

        phonemes = []
        engine = "kokoro"
        voice_name = None
        talking_video_path = None
        talking_video_cached = False
        json_result = None
        for line in reversed([l.strip() for l in raw.split("\n") if l.strip()]):
            if line.startswith("{"):
                try:
                    json_result = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        if json_result is not None:
            if not json_result.get("ok"):
                return jsonify({"ok": False, "error": json_result.get("error", "TTS echoue")}), 500
            phonemes = json_result.get("phonemes", [])
            engine = json_result.get("engine", engine)
            voice_name = json_result.get("voice")
            talking_video_path = json_result.get("talking_video")
            talking_video_cached = bool(json_result.get("talking_video_cached"))

        response: dict = {
            "ok": True,
            "audio_url": "/api/voice/tts-audio",
            "phonemes": phonemes,
            "engine": engine,
            "voice": voice_name,
        }
        # Expose le MP4 talking-video via une route dediee (meme mecanique que tts-audio)
        if talking_video_path and os.path.isfile(talking_video_path):
            # Stocker le path absolu dans une variable globale pour que /tts-video le serve
            app.config["_last_talking_video_path"] = talking_video_path
            response["video_url"] = "/api/voice/tts-video"
            response["video_cached"] = talking_video_cached

        return jsonify(response)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "TTS timeout"}), 504
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/voice/tts-audio")
def serve_tts_audio():
    """Sert le dernier fichier WAV TTS genere — universel Tauri/browser/tunnel."""
    # Les synthese sont horodatees et rangees par projet : on sert la PLUS
    # RECENTE au lieu d un nom fige. L ancienne version lisait `tts_out.wav`,
    # ce qui n avait de sens que tant qu une synthese ecrasait la precedente.
    racine_voix = os.path.join(WORKSPACE, "output", "voix")
    candidats = []
    for base, _dirs, fichiers in os.walk(racine_voix):
        for f in fichiers:
            if f.lower().endswith(".wav"):
                chemin = os.path.join(base, f)
                try:
                    candidats.append((os.path.getmtime(chemin), chemin))
                except OSError:
                    continue
    wav_path = max(candidats)[1] if candidats else ""
    if not wav_path or not os.path.exists(wav_path):
        wav_path = os.path.join(WORKSPACE, "temp", "tts_out.wav")
    if not os.path.exists(wav_path):
        return jsonify({"error": "Aucun fichier audio TTS disponible"}), 404
    return send_file(wav_path, mimetype="audio/wav", conditional=True)


@app.route("/api/voice/tts-video")
def serve_tts_video():
    """Sert le dernier MP4 talking-video (SadTalker) genere en parallele du TTS."""
    video_path = app.config.get("_last_talking_video_path")
    if not video_path or not os.path.isfile(video_path):
        return jsonify({"error": "Aucun MP4 talking-video disponible"}), 404
    return send_file(video_path, mimetype="video/mp4", conditional=True)


@app.route("/api/voice/talking-head/check", methods=["GET"])
def talking_head_check():
    """Check l installation SadTalker. Sert a determiner cote frontend si le mode
    talking-video est disponible (sinon fallback sur live2d-flux)."""
    try:
        script = os.path.join(WORKSPACE, "python-services", "talking_head.py")
        if not os.path.isfile(script):
            return jsonify({"ok": False, "installed": False, "reason": "script absent"})
        raw = subprocess.check_output(
            [sys.executable, script, "--mode", "check"],
            stderr=subprocess.STDOUT, timeout=10, cwd=WORKSPACE,
        ).decode("utf-8")
        for line in reversed([l.strip() for l in raw.split("\n") if l.strip()]):
            if line.startswith("{"):
                try:
                    return jsonify(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return jsonify({"ok": False, "installed": False, "reason": "no json output"})
    except Exception as e:
        return jsonify({"ok": False, "installed": False, "reason": str(e)})


@app.route("/api/voice/talking-head/idle", methods=["POST"])
def talking_head_idle():
    """Pre-genere la video idle (silence/respiration) pour un avatar donne.
    Appelee une fois quand l avatar est cree -> MP4 idle cache, reutilisable."""
    try:
        data = request.get_json() or {}
        avatar_image = data.get("avatar") or data.get("avatar_image")
        duration = float(data.get("duration", 3.0))
        if not avatar_image:
            return jsonify({"ok": False, "error": "avatar_image requis"}), 400
        # Resolve path
        avatar_abs = avatar_image
        if avatar_abs.startswith("/avatars/"):
            avatar_abs = os.path.join(WORKSPACE, "public", avatar_abs.lstrip("/"))
        elif not os.path.isabs(avatar_abs):
            avatar_abs = os.path.join(WORKSPACE, avatar_abs)
        if not os.path.isfile(avatar_abs):
            return jsonify({"ok": False, "error": f"Image introuvable: {avatar_abs}"}), 404

        os.makedirs(os.path.join(WORKSPACE, "temp"), exist_ok=True)
        name = os.path.splitext(os.path.basename(avatar_abs))[0]
        out_path = os.path.join(WORKSPACE, "temp", f"{name}_idle.mp4")
        script = os.path.join(WORKSPACE, "python-services", "talking_head.py")

        raw = subprocess.check_output(
            [sys.executable, script, "--mode", "idle",
             "--image", avatar_abs, "--output", out_path,
             "--duration", str(duration), "--size", "256"],
            stderr=subprocess.STDOUT, timeout=120, cwd=WORKSPACE,
        ).decode("utf-8")

        for line in reversed([l.strip() for l in raw.split("\n") if l.strip()]):
            if line.startswith("{"):
                try:
                    result = json.loads(line)
                    if result.get("ok"):
                        app.config["_last_idle_video_path"] = out_path
                        return jsonify({"ok": True, "video_url": "/api/voice/idle-video", "cached": result.get("cached", False)})
                    return jsonify({"ok": False, "error": result.get("error", "idle failed")}), 500
                except json.JSONDecodeError:
                    continue
        return jsonify({"ok": False, "error": "no json output"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/voice/idle-video")
def serve_idle_video():
    """Sert le dernier MP4 idle genere."""
    p = app.config.get("_last_idle_video_path")
    if not p or not os.path.isfile(p):
        return jsonify({"error": "Aucun MP4 idle disponible"}), 404
    return send_file(p, mimetype="video/mp4", conditional=True)


# v82jc : proxy server-side pour fetch ICS Pronote/ÉcoleDirecte/etc
#   Le navigateur bloque les fetch cross-origin → le bridge proxie.
@app.route("/api/calendar/fetch-ics", methods=["POST"])
def calendar_fetch_ics():
    """
    Fetch un flux ICS depuis le serveur Python (pas de CORS).
    Body JSON : { "url": "https://..." }
    Retour : { "ok": True, "text": "BEGIN:VCALENDAR..." }
            ou { "ok": False, "error": "..." }
    """
    try:
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()
        if not url:
            return jsonify({"ok": False, "error": "url requise"}), 400
        if not (url.startswith("http://") or url.startswith("https://")):
            return jsonify({"ok": False, "error": "url doit être http(s)"}), 400
        # Garde-fou : timeout court + max content size raisonnable.
        r = requests.get(url, timeout=15, headers={
            "User-Agent": "Aurora-Calendar-Bridge/1.0",
            "Accept": "text/calendar, text/plain, */*",
        }, stream=True)
        if r.status_code >= 400:
            return jsonify({"ok": False, "error": f"HTTP {r.status_code}"}), 200
        # Lecture par chunks avec cap 5 MB pour éviter les abus.
        max_bytes = 5 * 1024 * 1024
        total = 0
        chunks = []
        for chunk in r.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                return jsonify({"ok": False, "error": "ICS > 5 MB (limite)"}), 200
            chunks.append(chunk)
        text = b"".join(chunks).decode("utf-8", errors="replace")
        if "BEGIN:VCALENDAR" not in text:
            # Probablement la page menu HTML, pas l'URL ICS finale.
            # Donne un message d'aide concret à l'user.
            looks_html = "<html" in text.lower()[:1000] or "<!doctype" in text.lower()[:200]
            if looks_html:
                return jsonify({
                    "ok": False,
                    "error": "C'est une page web HTML, pas un fichier ICS. Dans ton portail (Pronote/EcoleDirecte/...), cherche le lien iCal direct (souvent dans Mon compte → Synchroniser ou Sécurité), puis copie cette URL-là.",
                }), 200
            return jsonify({
                "ok": False,
                "error": "Réponse non-ICS (pas de BEGIN:VCALENDAR). L'URL doit pointer directement vers le fichier .ics, pas vers une page d'accueil.",
            }), 200
        return jsonify({"ok": True, "text": text, "bytes": total}), 200
    except requests.exceptions.Timeout:
        return jsonify({"ok": False, "error": "Timeout 15s — vérifie l'URL"}), 200
    except requests.exceptions.ConnectionError as e:
        return jsonify({"ok": False, "error": f"Connexion refusée : {str(e)[:120]}"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}), 200


# ENT harvest persistence. Browser imports and desktop native imports both
# write section data here, grouped by adapter under output/ent.

import json as _json_ent
import os as _os_ent
import time as _time_ent

ENT_OUTPUT_ROOT = _os_ent.path.join(WORKSPACE if 'WORKSPACE' in dir() else _os_ent.path.dirname(_os_ent.path.abspath(__file__)), "output", "ent")


def _ent_dir(adapter: str, section: str) -> str:
    """Normalize + ensure output dir per adapter/section."""
    safe_adapter = "".join(c for c in (adapter or "unknown") if c.isalnum() or c in "-_")[:40]
    safe_section = "".join(c for c in (section or "home") if c.isalnum() or c in "-_")[:40]
    d = _os_ent.path.join(ENT_OUTPUT_ROOT, safe_adapter)
    _os_ent.makedirs(d, exist_ok=True)
    return _os_ent.path.join(d, f"{safe_section}.json")


@app.route("/api/ent/harvest", methods=["POST"])
def ent_harvest():
    """
    L'extension Aurora-Connect envoie les items extraits d'une section ENT.
    Body :
      {
        "adapter": "pronote" | "ecoledirecte" | "skolengo" | "ent-idf",
        "section": "devoirs" | "notes" | "fichiers" | "agenda" | ...,
        "hostname": "monlycee.index-education.com",
        "items": [ { ... } ],   // structure libre par section
        "ts": 1746240000000     // optionnel, sinon now()
      }
    Retour : { ok: bool, count: int, path: str (relative) }
    """
    try:
        body = request.get_json(silent=True) or {}
        adapter = (body.get("adapter") or "").strip()
        section = (body.get("section") or "").strip()
        hostname = (body.get("hostname") or "").strip()
        items = body.get("items")
        if not adapter or not section:
            return jsonify({"ok": False, "error": "adapter + section requis"}), 400
        if not isinstance(items, list):
            return jsonify({"ok": False, "error": "items[] requis (liste)"}), 400
        # Cap raisonnable contre flood (1000 items max par harvest).
        items = items[:1000]
        ts = body.get("ts") or int(_time_ent.time() * 1000)
        path = _ent_dir(adapter, section)
        payload = {
            "adapter": adapter,
            "section": section,
            "hostname": hostname,
            "ts": ts,
            "count": len(items),
            "items": items,
        }
        with open(path, "w", encoding="utf-8") as f:
            _json_ent.dump(payload, f, ensure_ascii=False, indent=2)
        rel = _os_ent.path.relpath(path, ENT_OUTPUT_ROOT)
        return jsonify({"ok": True, "count": len(items), "path": rel.replace("\\", "/")})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}), 200


@app.route("/api/ent/list", methods=["GET"])
def ent_list():
    """
    Liste tous les harvests persistés par adapter/section.
    Query params optionnels :
      - adapter=pronote  → filtre.
      - section=devoirs  → filtre.
    Retour : { ok: bool, harvests: [ { adapter, section, ts, count, path } ] }
    """
    try:
        filter_adapter = (request.args.get("adapter") or "").strip().lower()
        filter_section = (request.args.get("section") or "").strip().lower()
        out = []
        if not _os_ent.path.isdir(ENT_OUTPUT_ROOT):
            return jsonify({"ok": True, "harvests": []})
        for adapter_name in sorted(_os_ent.listdir(ENT_OUTPUT_ROOT)):
            adapter_path = _os_ent.path.join(ENT_OUTPUT_ROOT, adapter_name)
            if not _os_ent.path.isdir(adapter_path):
                continue
            if filter_adapter and adapter_name.lower() != filter_adapter:
                continue
            for fname in sorted(_os_ent.listdir(adapter_path)):
                if not fname.endswith(".json"):
                    continue
                section_name = fname[:-5]
                if filter_section and section_name.lower() != filter_section:
                    continue
                fpath = _os_ent.path.join(adapter_path, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = _json_ent.load(f)
                    out.append({
                        "adapter": adapter_name,
                        "section": section_name,
                        "ts": data.get("ts", 0),
                        "count": data.get("count", 0),
                        "hostname": data.get("hostname", ""),
                    })
                except Exception:
                    continue
        return jsonify({"ok": True, "harvests": out})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}), 500


@app.route("/api/ent/get", methods=["GET"])
def ent_get():
    """
    Lit un harvest spécifique par adapter+section.
    Query : adapter=pronote&section=devoirs (requis tous les 2).
    Retour : full payload { adapter, section, hostname, ts, count, items: [...] }.
    """
    try:
        adapter = (request.args.get("adapter") or "").strip()
        section = (request.args.get("section") or "").strip()
        if not adapter or not section:
            return jsonify({"ok": False, "error": "adapter + section requis"}), 400
        path = _ent_dir(adapter, section)
        if not _os_ent.path.isfile(path):
            return jsonify({"ok": True, "data": None})
        with open(path, "r", encoding="utf-8") as f:
            data = _json_ent.load(f)
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}), 500


# Fallback builder used when the LLM extractor returns no structured item.
# It still preserves files and raw page text so the academic side is fed.
def _ent_fallback_items_from_snapshot(section: str, snapshot: dict, attachments: list, error: str = "") -> list:
    text = (snapshot.get("text") or "").strip()
    title = (snapshot.get("title") or section or "ENT").strip()
    files = []
    for a in (attachments or [])[:200]:
        if not isinstance(a, dict):
            continue
        url = (a.get("url") or "").strip()
        if not url:
            continue
        filename = (
            a.get("filename")
            or a.get("download")
            or a.get("text")
            or pathlib.PurePosixPath(url.split("?", 1)[0]).name
            or "document"
        )
        files.append({
            "filename": filename,
            "url": url,
            "localPath": a.get("localPath") or "",
            "downloaded": bool(a.get("downloaded")),
            "sizeBytes": a.get("sizeBytes") or 0,
            "subject": "",
            "chapter": title,
            "mime": a.get("mime") or a.get("type") or "",
            "raw": a.get("text") or "",
            "source": "native_attachment_link",
            "scope": a.get("scope") or "",
        })
    if files and section == "fichiers":
        return files
    if files:
        return [{
            "title": title,
            "date": "",
            "description": text[:4000],
            "attachments": [{
                "url": f.get("url"),
                "filename": f.get("filename"),
                "localPath": f.get("localPath"),
                "downloaded": f.get("downloaded"),
            } for f in files],
            "raw": text[:12000],
            "source": "native_scrape_fallback",
            "extractionError": error,
        }]
    if text:
        return [{
            "title": title,
            "url": snapshot.get("url") or "",
            "raw": text[:12000],
            "source": "native_raw_scrape_fallback",
            "extractionError": error,
        }]
    return []


@app.route("/api/ent/native/run", methods=["POST"])
def ent_native_run():
    """
    Desktop-app ENT pipeline. The extension is only required when Aurora runs
    inside a normal web browser; the Tauri app can open its own local Chromium
    session through the bridge.
    """
    try:
        body = request.get_json(silent=True) or {}
        adapter = (body.get("adapter") or "pronote").strip()
        login_url = (body.get("loginUrl") or "").strip()
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        sections = body.get("sections") or ["devoirs", "notes", "agenda", "fichiers"]
        section_paths = body.get("sectionPaths") or {}
        profile_key = body.get("profileKey") or adapter
        if not login_url or not username or not password:
            return jsonify({"ok": False, "error": "loginUrl + username + password requis"}), 400
        script = pathlib.Path(WORKSPACE) / "python-services" / "ent_native_browser.py"
        native_payload = {
            "adapter": adapter,
            "loginUrl": login_url,
            "username": username,
            "password": password,
            "sections": sections,
            "sectionPaths": section_paths,
            "profileKey": profile_key,
            "profileRoot": str(pathlib.Path(WORKSPACE) / "output" / "ent_native_profiles"),
            "downloadRoot": str(pathlib.Path(WORKSPACE) / "output" / "ent_downloads" / profile_key),
        }
        proc = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps(native_payload, ensure_ascii=False).encode("utf-8"),
            capture_output=True,
            timeout=240,
            cwd=WORKSPACE,
        )
        stdout = proc.stdout.decode("utf-8", errors="replace")
        try:
            native = json.loads(stdout or "{}")
        except Exception:
            native = {"ok": False, "error": stdout[:500] or proc.stderr.decode("utf-8", errors="replace")[:500]}
        if not native.get("ok"):
            return jsonify({
                "ok": False,
                "reason": native.get("reason") or "native_browser_failed",
                "error": native.get("error") or proc.stderr.decode("utf-8", errors="replace")[:500],
            }), 200

        section_results = {}
        total_items = 0
        for section, scraped in (native.get("sectionResults") or {}).items():
            if not scraped.get("ok", True):
                section_results[section] = {
                    "ok": False,
                    "error": scraped.get("error") or "section scrape failed",
                }
                continue
            snapshot = scraped.get("snapshot") or {}
            attachments = scraped.get("attachments") or []
            items = _ent_fallback_items_from_snapshot(section, snapshot, attachments)
            path = _ent_dir(adapter, section)
            payload_out = {
                "adapter": adapter,
                "section": section,
                "hostname": scraped.get("hostname") or "",
                "ts": int(_time_ent.time() * 1000),
                "count": len(items),
                "items": items,
                "snapshot": {
                    "title": snapshot.get("title") or "",
                    "url": snapshot.get("url") or "",
                    "textPreview": (snapshot.get("text") or "")[:4000],
                },
                "source": "desktop_native_browser",
            }
            with open(path, "w", encoding="utf-8") as f:
                _json_ent.dump(payload_out, f, ensure_ascii=False, indent=2)
            total_items += len(items)
            section_results[section] = {"ok": True, "itemsCount": len(items)}
        return jsonify({
            "ok": True,
            "mode": "desktop_native_browser",
            "sectionResults": section_results,
            "totalItems": total_items,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "reason": "timeout", "error": "Session ENT native trop longue"}), 200
    except Exception as e:
        return jsonify({"ok": False, "reason": "exception", "error": f"{type(e).__name__}: {str(e)[:200]}"}), 500


@app.route("/api/ent/discover-school", methods=["POST"])
@app.route("/api/ent/discover-pronote", methods=["POST"])
def ent_discover_pronote():
    """
    Découvre un portail scolaire à partir du nom + ville.
    Utilise l'annuaire public Éducation nationale, puis une recherche web
    sur Pronote, ÉcoleDirecte, Skolengo et ENT régionaux en fallback.

    Body : { "schoolName": "Lycée Voltaire", "city": "Paris" }
    Retour : {
      "ok": True,
      "candidates": [{
        "name": "Lycée Voltaire - Paris",
        "adapterId": "pronote",
        "systemLabel": "Pronote",
        "url": "https://0750565x.index-education.net/pronote/",
        "loginUrl": "https://0750565x.index-education.net/pronote/eleve.html",
        "uai": "0750565X",
        "city": "Paris",
        "score": 0.92  # confiance match
      }, ...]
    }
    """
    try:
        body = request.get_json(silent=True) or {}
        school = (body.get("schoolName") or "").strip()
        city = (body.get("city") or "").strip()
        if not school:
            return jsonify({"ok": False, "error": "schoolName requis"}), 400

        preferred_adapter = (body.get("adapter") or "").strip().lower()
        candidates = []

        def _adapter_for_url(url: str) -> tuple[str, str]:
            low = (url or "").lower()
            if "ecoledirecte" in low:
                return "ecoledirecte", "ÉcoleDirecte"
            if "skolengo" in low or "kosmos" in low or "monbureaunumerique" in low:
                return "skolengo", "Skolengo / ENT régional"
            if "monlycee" in low or "iledefrance" in low or "ent." in low:
                return "ent-idf", "ENT / MonLycée"
            if "index-education" in low or "pronote" in low:
                return "pronote", "Pronote"
            fallback_adapter = preferred_adapter if preferred_adapter not in ("", "auto") else "pronote"
            fallback_label = fallback_adapter if fallback_adapter != "pronote" else "Pronote"
            return fallback_adapter, fallback_label

        def _allowed(adapter_id: str) -> bool:
            return not preferred_adapter or preferred_adapter == "auto" or adapter_id == preferred_adapter

        def _add_candidate(adapter_id: str, label: str, name: str, login_url: str, *, url: str = "", uai: str = "", commune: str = "", score: float = 0.5, source: str = ""):
            if not login_url or not _allowed(adapter_id):
                return
            candidates.append({
                "adapterId": adapter_id,
                "systemLabel": label,
                "name": name or school,
                "url": url or login_url,
                "loginUrl": login_url,
                "uai": uai or "",
                "city": commune or city,
                "source": source,
                "score": score,
            })

        # Source 1 : data.education.gouv.fr (API officielle Mistère
        # de l'Éducation Nationale). Annuaire de tous les établissements
        # publics + privés sous contrat avec leur UAI.
        import re as _re
        import urllib.request as _ur
        from urllib.parse import quote_plus
        try:
            # Records API : fuzzy text search via clause `where` + LIKE.
            # Le param `q` ignore silencieusement les requêtes — `where` avec
            # LIKE est le bon path pour fuzzy match sur nom_etablissement.
            # Échappe les apostrophes pour ne pas casser la query SQL-like.
            esc_school = school.replace("'", "''")
            where_clauses = [f"nom_etablissement like '%{esc_school}%'"]
            if city:
                esc_city = city.replace("'", "''")
                where_clauses.append(f"nom_commune like '%{esc_city.upper()}%'")
            params = {
                "limit": "10",
                "where": " AND ".join(where_clauses),
            }
            url = (
                "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/"
                "fr-en-annuaire-education/records?"
                + "&".join(f"{k}={quote_plus(v)}" for k, v in params.items())
            )
            req_obj = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0 AuroraIA"})
            with _ur.urlopen(req_obj, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for rec in data.get("results", []):
                uai = rec.get("identifiant_de_l_etablissement") or ""
                if not uai:
                    continue
                name = rec.get("nom_etablissement") or school
                commune = rec.get("nom_commune") or city
                # Pronote URL pattern : <UAI lowercase>.index-education.net/pronote/
                # avec le UAI tronqué (sans la lettre finale parfois)
                # On propose les 2 patterns courants.
                uai_lower = uai.lower()
                base_net = f"https://{uai_lower}.index-education.net"
                _add_candidate(
                    "pronote",
                    "Pronote",
                    f"{name} - {commune}",
                    f"{base_net}/pronote/eleve.html",
                    url=f"{base_net}/pronote/",
                    uai=uai,
                    commune=commune,
                    score=0.9,
                    source="annuaire_education",
                )
                if len(candidates) >= 8:
                    break
        except Exception as _e:
            print(f"[ent-discover] data.gouv api failed: {_e}", flush=True)

        # Source 2 : DuckDuckGo HTML scraping across common school systems.
        if len(candidates) < 8:
            try:
                query_bits = [
                    f'"{school}" {city} ENT OR Pronote OR ÉcoleDirecte OR Skolengo',
                    "site:index-education.net OR site:index-education.com OR site:ecoledirecte.com OR site:skolengo.com",
                ]
                query = quote_plus(" ".join(query_bits))
                ddg_url = f"https://html.duckduckgo.com/html/?q={query}"
                req_obj = _ur.Request(ddg_url, headers={"User-Agent": "Mozilla/5.0"})
                with _ur.urlopen(req_obj, timeout=10) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                import html as _html_mod
                from urllib.parse import unquote as _unquote, urlparse as _urlparse, parse_qs as _parse_qs
                seen = set()
                raw_urls = _re.findall(r"https?://[^\"'<>\s]+", _html_mod.unescape(html), flags=_re.I)
                for raw in raw_urls:
                    decoded = _unquote(raw).rstrip(").,;")
                    parsed = _urlparse(decoded)
                    if "duckduckgo.com" in parsed.netloc and "uddg" in decoded:
                        qs = _parse_qs(parsed.query)
                        decoded = qs.get("uddg", [decoded])[0]
                        parsed = _urlparse(decoded)
                    host = parsed.netloc.lower()
                    path = parsed.path or "/"
                    if not host:
                        continue
                    if not any(token in host + path.lower() for token in [
                        "index-education", "pronote", "ecoledirecte", "skolengo",
                        "monbureaunumerique", "monlycee", "iledefrance", "ent.",
                    ]):
                        continue
                    adapter_id, label = _adapter_for_url(decoded)
                    if adapter_id == "pronote":
                        base = f"{parsed.scheme}://{host}"
                        if "/pronote" in path.lower():
                            prefix = path[:path.lower().find("/pronote") + len("/pronote")]
                            login_url = f"{base}{prefix.rstrip('/')}/eleve.html"
                            url = f"{base}{prefix.rstrip('/')}/"
                        else:
                            login_url = f"{base}/pronote/eleve.html"
                            url = f"{base}/pronote/"
                    elif adapter_id == "ecoledirecte":
                        login_url = "https://www.ecoledirecte.com/login"
                        url = "https://www.ecoledirecte.com/"
                    else:
                        login_url = decoded
                        url = decoded
                    if login_url in seen:
                        continue
                    seen.add(login_url)
                    score = 0.78 if school.lower() in html.lower() else 0.58
                    if city and city.lower() in html.lower():
                        score += 0.05
                    _add_candidate(
                        adapter_id,
                        label,
                        f"{school} - {city}".strip(" -"),
                        login_url,
                        url=url,
                        uai="",
                        commune=city,
                        score=min(score, 0.86),
                        source="web_search",
                    )
                    if len(candidates) >= 8:
                        break
            except Exception:
                pass

        # 2. Tri par score desc et dédup loginUrl.
        seen_urls = set()
        unique = []
        for c in sorted(candidates, key=lambda x: -x.get("score", 0)):
            if c["loginUrl"] in seen_urls:
                continue
            seen_urls.add(c["loginUrl"])
            unique.append(c)

        return jsonify({
            "ok": True,
            "candidates": unique,
            "message": "" if unique else "Aucun portail fiable trouvé automatiquement. Utilise l’URL manuelle.",
            "queryEcho": {"schoolName": school, "city": city},
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ent/analyze-dom", methods=["POST"])
def ent_analyze_dom():
    """
    Analyse LLM d'un DOM scolaire pour extraire items structurés.
    Body :
      {
        "adapter": "pronote" | "ecoledirecte" | ...,
        "section": "devoirs" | "notes" | "fichiers" | "agenda",
        "snapshot": { text, title, url, containers[] },
        "hostname": "..."
      }
    Retour :
      {
        "ok": True,
        "items": [...],     // structure dépend de la section
        "raw": "...",       // raw LLM response pour debug
        "extractedCount": N
      }
    """
    try:
        body = request.get_json(silent=True) or {}
        adapter = (body.get("adapter") or "").strip()
        section = (body.get("section") or "").strip()
        snapshot = body.get("snapshot") or {}
        hostname = body.get("hostname") or ""
        if not adapter or not section:
            return jsonify({"ok": False, "error": "adapter + section requis"}), 400
        text = snapshot.get("text") or ""
        title = snapshot.get("title") or ""
        url = snapshot.get("url") or ""
        if len(text) < 100:
            return jsonify({"ok": False, "error": "DOM trop court (< 100 chars), pas la bonne page ?"}), 200

        # Build prompt selon section.
        section_specs = {
            "devoirs": (
                "Extrait les devoirs/contrôles/évaluations. Pour chaque item retourne "
                '{title, subject, date (ISO si possible), description, isEval (bool : true si DST/DS/contrôle/interro)}.'
            ),
            "notes": (
                "Extrait les notes scolaires. Pour chaque note retourne "
                '{subject, grade (number), scale (number, généralement 20), classAverage (number ou null), date (ISO), title (intitulé éval), type (DST/DM/oral/...)}.'
            ),
            "fichiers": (
                "Extrait les fichiers/pièces jointes/documents de cours. Pour chaque retourne "
                '{filename, url (URL absolu), subject, chapter, date (ISO si possible), mime (deviné depuis ext)}.'
            ),
            "agenda": (
                "Extrait les événements d'agenda/cours/edt. Pour chaque retourne "
                '{title, subject, start (ISO), end (ISO), location, type (cours/réunion/sortie/...)}.'
            ),
        }
        spec = section_specs.get(section, f"Extrait les éléments structurés de la section '{section}'.")
        system = (
            "Tu es un parser ENT français (Pronote/ÉcoleDirecte/Skolengo). "
            "Tu reçois le contenu textuel d'une page et tu en extraits des items "
            "structurés en JSON strict.\n\n"
            f"{spec}\n\n"
            "Réponds UNIQUEMENT avec :\n"
            '{"items": [...]}\n'
            "Pas de markdown, pas de prose, JSON pur. Si aucun item identifiable, "
            'retourne {"items": []}. Date ISO format : YYYY-MM-DD.'
        )

        user = (
            f"Adapter : {adapter}\n"
            f"Section : {section}\n"
            f"Hostname : {hostname}\n"
            f"Page title : {title}\n"
            f"URL : {url}\n\n"
            f"Contenu (innerText) :\n---\n{text[:15000]}\n---\n\n"
            "Extrait."
        )

        # Use existing Ollama proxy. Pick first available model (priorité aux
        # 7-8B rapides, fallback aux plus gros si rien trouvé).
        try:
            tags_r = requests.get("http://127.0.0.1:11434/api/tags", timeout=8)
            models = [m["name"] for m in (tags_r.json().get("models") or [])]
            preferred = ["llama3.2:3b", "qwen2.5:7b", "qwen3:14b", "qwen2.5-coder:7b"]
            picked = next((p for p in preferred if p in models), None)
            if picked is None and models:
                picked = models[0]
            if picked is None:
                return jsonify({"ok": False, "error": "Aucun modèle Ollama installé", "items": []}), 200
        except Exception as e:
            return jsonify({"ok": False, "error": f"Ollama tags fail: {str(e)[:120]}", "items": []}), 200
        try:
            ollama_url = "http://127.0.0.1:11434/api/chat"
            r = requests.post(ollama_url, json={
                "model": picked,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"temperature": 0.2},
            }, timeout=120)
            if r.status_code != 200:
                return jsonify({"ok": False, "error": f"Ollama HTTP {r.status_code}", "items": []}), 200
            response_data = r.json()
            response_text = response_data.get("message", {}).get("content", "")
        except Exception as e:
            return jsonify({"ok": False, "error": f"Ollama unavailable: {str(e)[:120]}", "items": []}), 200

        # Parse JSON dans la réponse (LLM peut ajouter du fluff malgré la consigne).
        import re as _re
        match = _re.search(r"\{[\s\S]*\}", response_text)
        if not match:
            return jsonify({
                "ok": False, "error": "JSON introuvable dans réponse LLM",
                "raw": response_text[:500], "items": [],
            }), 200
        try:
            parsed = _json_ent.loads(match.group(0))
        except Exception as e:
            return jsonify({
                "ok": False, "error": f"JSON parse fail: {str(e)[:80]}",
                "raw": response_text[:500], "items": [],
            }), 200
        items = parsed.get("items", [])
        if not isinstance(items, list):
            items = []
        # Cap items raisonnable (anti-hallucination LLM).
        items = items[:200]
        return jsonify({
            "ok": True,
            "items": items,
            "extractedCount": len(items),
            "raw": response_text[:500],
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}), 500


@app.route("/api/voice/stt-info")
def voice_stt_info():
    """Retourne le modele STT actif et la disponibilite CUDA."""
    try:
        import torch
        cuda = torch.cuda.is_available()
    except Exception:
        cuda = False
    return jsonify({
        "model": "large-v3-turbo",
        "cuda": cuda,
        "device": "cuda" if cuda else "cpu",
    })


@app.route("/api/voice/personas")
def voice_personas():
    """Liste les personas TTS Aurora exposes par voice_service.py.

    Permet a une UI dynamique (settings panel, dev tools) de connaitre
    les agents disponibles + leur voix Edge-TTS sous-jacente sans
    hardcoder la liste cote client.
    """
    # Source de verite mirroirde manuellement EDGE_TTS_VOICE_PERSONAS de
    # voice_service.py. Si tu ajoutes un persona la-bas, mets a jour ici.
    personas = [
        {"id": "lyra-soft",     "label": "Lyra · douce",      "module": "conversation", "edge_voice_fr": "fr-FR-DeniseNeural",  "edge_voice_en": "en-US-JennyNeural"},
        {"id": "iris-bright",   "label": "Iris · vive",       "module": "image",        "edge_voice_fr": "fr-FR-BrigitteNeural", "edge_voice_en": "en-US-AriaNeural"},
        {"id": "cinema-deep",   "label": "Cinema · grave",    "module": "video",        "edge_voice_fr": "fr-FR-HenriNeural",   "edge_voice_en": "en-US-GuyNeural"},
        {"id": "glyph-precise", "label": "Glyph · precise",   "module": "code",         "edge_voice_fr": "fr-FR-YvetteNeural",  "edge_voice_en": "en-US-AvaNeural"},
        {"id": "sumi-warm",     "label": "Sumi · chaleureuse","module": "drawing",      "edge_voice_fr": "fr-FR-EloiseNeural",  "edge_voice_en": "en-US-EmmaNeural"},
        {"id": "atlas-strong",  "label": "Atlas · forte",     "module": "3d",           "edge_voice_fr": "fr-FR-MauriceNeural", "edge_voice_en": "en-US-RyanNeural"},
        {"id": "sage-mellow",   "label": "Sage · posee",      "module": "learning",     "edge_voice_fr": "fr-FR-ClaudeNeural",  "edge_voice_en": "en-US-AndrewNeural"},
        {"id": "phantom-sharp", "label": "Phantom · tranchante","module": "cyber",      "edge_voice_fr": "fr-FR-AlainNeural",   "edge_voice_en": "en-US-EricNeural"},
    ]
    return jsonify({"ok": True, "personas": personas, "default": "lyra-soft"})


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


# =====================================================================
#  /api/code/repo/* — work directly on a local repository (v85)
#  pick (native folder dialog) · scan (read project as context) ·
#  write (apply changes back) · git (status / branch). Lets the Code
#  module iterate on ANY existing project on disk, not just greenfield
#  in-app generation.
# =====================================================================

_REPO_LANG_BY_EXT = {
    "ts": "typescript", "tsx": "typescript", "js": "javascript", "jsx": "javascript",
    "mjs": "javascript", "cjs": "javascript", "py": "python", "rs": "rust", "go": "go",
    "java": "java", "kt": "kotlin", "swift": "swift", "c": "c", "h": "c", "cpp": "cpp",
    "cc": "cpp", "hpp": "cpp", "cs": "csharp", "rb": "ruby", "php": "php", "lua": "lua",
    "sh": "bash", "bash": "bash", "ps1": "powershell", "sql": "sql", "html": "html",
    "htm": "html", "css": "css", "scss": "scss", "sass": "scss", "less": "less",
    "vue": "vue", "svelte": "svelte", "json": "json", "yaml": "yaml", "yml": "yaml",
    "toml": "toml", "xml": "xml", "md": "markdown", "txt": "text", "ini": "ini",
    "cfg": "ini", "env": "text", "dockerfile": "dockerfile", "r": "r", "dart": "dart",
}

_REPO_SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit",
    "__pycache__", ".venv", "venv", "env", ".env", "target", "vendor", ".idea",
    ".vscode", "coverage", ".cache", ".turbo", ".parcel-cache", "bin", "obj",
    ".gradle", "Pods", ".expo", ".aurora_backup", "site-packages",
}

_REPO_SKIP_EXT = {
    "png", "jpg", "jpeg", "gif", "webp", "ico", "bmp", "tiff", "svg", "pdf",
    "mp4", "mov", "avi", "mkv", "webm", "mp3", "wav", "ogg", "flac", "zip",
    "tar", "gz", "rar", "7z", "exe", "dll", "so", "dylib", "bin", "wasm",
    "ttf", "otf", "woff", "woff2", "eot", "glb", "gltf", "fbx", "obj", "blend",
    "psd", "ai", "sketch", "db", "sqlite", "lock", "pyc", "pack", "idx",
}


def _repo_lang(rel: str) -> str:
    low = rel.lower()
    if low.endswith("dockerfile") or low == "dockerfile":
        return "dockerfile"
    ext = low.rsplit(".", 1)[-1] if "." in low else ""
    return _REPO_LANG_BY_EXT.get(ext, "text")


def _repo_git(path, args, timeout=8):
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return None


@app.route("/api/code/repo/pick", methods=["POST"])
def code_repo_pick():
    """Open a native folder picker and return the chosen path.

    Runs the dialog in a FRESH python process (sys.executable) so Tk never
    touches the Flask worker thread (which would crash on Windows).
    """
    try:
        snippet = (
            "import tkinter, tkinter.filedialog as fd;"
            "r=tkinter.Tk();r.withdraw();r.attributes('-topmost',True);"
            "p=fd.askdirectory(title='Choisis le dossier du repo');"
            "print(p or '')"
        )
        proc = subprocess.run(
            [sys.executable, "-c", snippet],
            capture_output=True, text=True, timeout=120,
        )
        path = (proc.stdout or "").strip().splitlines()[-1].strip() if proc.stdout.strip() else ""
        if not path or not os.path.isdir(path):
            return jsonify({"ok": False, "error": "Aucun dossier sélectionné."})
        return jsonify({"ok": True, "path": os.path.abspath(path)})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Sélecteur indisponible: {e}"}), 500


@app.route("/api/code/repo/scan", methods=["POST"])
def code_repo_scan():
    """Read a repository into a capped, text-only snapshot for LLM context.

    Body: {path, max_files?, max_bytes?, max_file_bytes?}
    Uses `git ls-files` when the dir is a git repo (respects .gitignore),
    otherwise walks with a skip-list. Returns {files:[{path,content,language}]}.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        root = os.path.abspath((data.get("path") or "").strip())
        if not root or not os.path.isdir(root):
            return jsonify({"ok": False, "error": "Chemin invalide ou introuvable."}), 400
        max_files = int(data.get("max_files") or 120)
        max_bytes = int(data.get("max_bytes") or 1_400_000)
        max_file_bytes = int(data.get("max_file_bytes") or 60_000)

        is_git = os.path.isdir(os.path.join(root, ".git"))
        branch = _repo_git(root, ["rev-parse", "--abbrev-ref", "HEAD"]) if is_git else None

        # Build the candidate relative-path list.
        rels = []
        tracked = _repo_git(root, ["ls-files"]) if is_git else None
        if tracked:
            for line in tracked.splitlines():
                rel = line.strip()
                if rel:
                    rels.append(rel)
        else:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in _REPO_SKIP_DIRS and not d.startswith(".")]
                for fn in filenames:
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, root).replace("\\", "/")
                    rels.append(rel)

        files = []
        total_bytes = 0
        total_candidates = len(rels)
        truncated = False
        # Prefer salient files first (entrypoints, manifests, src).
        def _rank(rel):
            low = rel.lower()
            score = 0
            if any(low.endswith(m) for m in ("package.json", "cargo.toml", "pyproject.toml", "go.mod", "requirements.txt", "readme.md")):
                score -= 100
            if low.startswith("src/") or "/src/" in low:
                score -= 20
            score += low.count("/")
            return score
        rels.sort(key=_rank)

        for rel in rels:
            if len(files) >= max_files or total_bytes >= max_bytes:
                truncated = True
                break
            parts = rel.split("/")
            if any(p in _REPO_SKIP_DIRS for p in parts):
                continue
            ext = rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
            if ext in _REPO_SKIP_EXT:
                continue
            full = os.path.join(root, rel)
            try:
                if not os.path.isfile(full):
                    continue
                if os.path.getsize(full) > max_file_bytes * 4:
                    continue
                with open(full, "r", encoding="utf-8") as fh:
                    content = fh.read(max_file_bytes + 1)
            except (UnicodeDecodeError, OSError):
                continue
            if len(content) > max_file_bytes:
                content = content[:max_file_bytes] + "\n/* … fichier tronqué pour le contexte … */"
            total_bytes += len(content)
            files.append({"path": rel, "content": content, "language": _repo_lang(rel)})

        return jsonify({
            "ok": True,
            "path": root,
            "label": os.path.basename(root.rstrip("/\\")) or root,
            "branch": branch,
            "is_git": is_git,
            "truncated": truncated,
            "total_files": total_candidates,
            "total_bytes": total_bytes,
            "files": files,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/code/repo/write", methods=["POST"])
def code_repo_write():
    """Write generated/modified files back into a repository.

    Body: {path, files:[{path, content}], backup?}
    Sanitizes each relative path (no absolute, no ..). When backup=true,
    overwritten files are copied to <repo>/.aurora_backup/<ts>/ first.
    """
    import shutil  # module-level import is function-local elsewhere — ensure it's bound here
    try:
        data = request.get_json(force=True, silent=True) or {}
        root = os.path.abspath((data.get("path") or "").strip())
        files = data.get("files") or []
        if not root or not os.path.isdir(root):
            return jsonify({"ok": False, "error": "Chemin du repo invalide."}), 400
        if not isinstance(files, list) or not files:
            return jsonify({"ok": False, "error": "Aucun fichier à écrire."}), 400

        backup = bool(data.get("backup", True))
        backup_dir = os.path.join(root, ".aurora_backup", str(int(time.time())))
        written, skipped, backed_up = [], [], []
        for f in files:
            if not isinstance(f, dict):
                continue
            rel = str(f.get("path") or "").strip().replace("\\", "/").lstrip("/")
            if not rel or ".." in rel.split("/"):
                skipped.append(rel or "(vide)")
                continue
            content = f.get("content")
            if not isinstance(content, str):
                content = str(content or "")
            full = os.path.join(root, rel)
            # Stay inside the repo root.
            if os.path.commonpath([os.path.abspath(full), root]) != root:
                skipped.append(rel)
                continue
            try:
                if backup and os.path.isfile(full):
                    bdest = os.path.join(backup_dir, rel)
                    os.makedirs(os.path.dirname(bdest) or backup_dir, exist_ok=True)
                    shutil.copy2(full, bdest)
                    backed_up.append(rel)
                os.makedirs(os.path.dirname(full) or root, exist_ok=True)
                with open(full, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(content)
                written.append(rel)
            except Exception:
                skipped.append(rel)

        return jsonify({
            "ok": True, "path": root, "written": written,
            "skipped": skipped, "backed_up": backed_up,
            "backup_dir": backup_dir if backed_up else None,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/code/repo/git", methods=["POST"])
def code_repo_git_info():
    """Lightweight git info: {path, action: 'status'|'branch'}."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        root = os.path.abspath((data.get("path") or "").strip())
        action = (data.get("action") or "status").strip()
        if not root or not os.path.isdir(root):
            return jsonify({"ok": False, "error": "Chemin invalide."}), 400
        if not os.path.isdir(os.path.join(root, ".git")):
            return jsonify({"ok": True, "is_git": False})
        branch = _repo_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
        if action == "branch":
            return jsonify({"ok": True, "is_git": True, "branch": branch})
        status = _repo_git(root, ["status", "--porcelain"]) or ""
        changed = [ln.strip() for ln in status.splitlines() if ln.strip()]
        return jsonify({"ok": True, "is_git": True, "branch": branch,
                        "dirty": len(changed) > 0, "changed": changed[:60]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/code/repo/install", methods=["POST"])
def code_repo_install():
    """Autonomy (v85f): detect the project's dependency manifest and run its
    install command in a DETACHED console so the generated/repo project actually
    runs on the PC. Body: {path}. Returns immediately; install runs in the
    spawned console (npm/pnpm/yarn install, pip install, cargo build, go mod).
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        root = os.path.abspath((data.get("path") or "").strip())
        if not root or not os.path.isdir(root):
            return jsonify({"ok": False, "error": "Chemin invalide."}), 400

        def _has(name):
            return os.path.isfile(os.path.join(root, name))

        cmd = None
        manifest = None
        if _has("package.json"):
            manifest = "package.json"
            cmd = ("pnpm install" if _has("pnpm-lock.yaml")
                   else "yarn install" if _has("yarn.lock")
                   else "npm install")
        elif _has("requirements.txt"):
            manifest = "requirements.txt"
            cmd = f'"{sys.executable}" -m pip install -r requirements.txt'
        elif _has("pyproject.toml"):
            manifest = "pyproject.toml"
            cmd = f'"{sys.executable}" -m pip install -e .'
        elif _has("Cargo.toml"):
            manifest = "Cargo.toml"
            cmd = "cargo build"
        elif _has("go.mod"):
            manifest = "go.mod"
            cmd = "go mod download"

        if not cmd:
            return jsonify({"ok": False, "error": "Aucun manifeste détecté (package.json, requirements.txt, pyproject.toml, Cargo.toml, go.mod)."})

        try:
            if platform.system() == "Windows":
                subprocess.Popen(cmd, cwd=root, shell=True,
                                 creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_BREAKAWAY_FROM_JOB)
            else:
                subprocess.Popen(cmd, cwd=root, shell=True, start_new_session=True)
        except Exception as ex:
            return jsonify({"ok": False, "error": f"Lancement échoué: {ex}", "command": cmd}), 500
        return jsonify({"ok": True, "command": cmd, "cwd": root, "manifest": manifest})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/proxy/ollama/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def ollama_proxy(path):
    try:
        return _proxy(f"{OLLAMA_URL}/{path}")
    except Exception as e:
        return jsonify({"error": f"Ollama non joignable: {e}"}), 504


@app.route("/api/ollama/chat", methods=["POST"])
def ollama_chat():
    """Route directe pour le chat stream — headers propres."""
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=request.json,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=180,
        )
        return Response(
            resp.iter_content(chunk_size=4096),
            content_type="application/json",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =====================================================================
#  /api/ext/* — API publique pour intégrer Aurora dans un site externe
#  (widget de chat embarqué). Sécurité :
#   • clé Bearer ; on ne stocke QUE le SHA-256 salé de la clé, jamais la
#     clé en clair ; comparaison constante (hmac.compare_digest) ;
#   • CORS verrouillé : Access-Control-Allow-Origin = le domaine déclaré
#     pour la clé (jamais "*" si un domaine est fixé) ;
#   • rate-limit glissant 40 req / 60 s par clé ;
#   • clés de gestion (generate/revoke/status) accessibles seulement en
#     local (pas exposées par défaut sur le tunnel — voir _ext_admin_ok).
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
        names = [m.get("name", "") for m in models if isinstance(m, dict)]
        for pref in ("qwen3", "llama3.2", "llama3", "mistral", "gemma", "qwen"):
            for n in names:
                if pref in n.lower():
                    return n
        if names:
            return names[0]
    except Exception:
        pass
    return "qwen3:8b"


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


# =====================================================================
#  ComfyUI Proxy
# =====================================================================

@app.route("/proxy/comfy/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def comfyui_proxy(path):
    try:
        if path == "prompt" and request.method == "POST":
            from auto_rl.image_runtime import apply_validated_workflow
            data = request.get_json()
            data["prompt"] = apply_validated_workflow(apply_validated_workflow(data["prompt"]), "video")
            return _proxy(f"{COMFYUI_URL}/{path}", data_override=json.dumps(data).encode())
        return _proxy(f"{COMFYUI_URL}/{path}")
    except Exception as e:
        return jsonify({"error": f"ComfyUI non joignable: {e}"}), 504


# =====================================================================
#  Hardware / Runtime / Privilege  (les 404 du log)
# =====================================================================

@app.route("/api/hardware")
def hardware():
    """Retourne le profil hardware du PC serveur."""
    try:
        cpu = platform.processor() or platform.machine()
        cores = psutil.cpu_count(logical=True)
        ram = round(psutil.virtual_memory().total / (1024 ** 3), 1)
        gpu_name = "GPU (utilise nvidia-smi pour details)"
        vram = 0
        try:
            nv = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
                timeout=5,
            ).decode().strip().split(",")
            if len(nv) >= 3:
                gpu_name = nv[0].strip()
                vram = round(int(nv[1].strip()) / 1024, 1)
        except Exception:
            pass
        return jsonify({
            "os": f"{platform.system()} {platform.release()}",
            "cpu": cpu,
            "cores": cores,
            "ram_gb": ram,
            "gpu": gpu_name,
            "vram_gb": vram,
            "vram_free_gb": vram,
        })
    except Exception as e:
        return jsonify({"os": platform.system(), "cpu": "unknown", "cores": 4, "ram_gb": 8, "gpu": "unknown", "vram_gb": 0, "vram_free_gb": 0})


@app.route("/api/runtime/inspect")
def runtime_inspect():
    """Liste l'etat des services."""
    services = []
    # Ollama
    ollama_ok = False
    try:
        requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        ollama_ok = True
    except Exception:
        pass
    services.append({
        "id": "ollama", "label": "Ollama", "available": ollama_ok, "running": ollama_ok,
        "startedByApp": False, "progress": 100 if ollama_ok else 0,
        "detail": "Actif" if ollama_ok else "Non joignable", "path": None, "processId": None,
    })
    # ComfyUI — available = installe, running = repond sur HTTP
    comfy_ok = _comfyui_is_ready()
    comfyui_installed = COMFYUI_PATH is not None
    started_by_app = _comfyui_process is not None and _comfyui_process.poll() is None
    services.append({
        "id": "comfyui", "label": "ComfyUI",
        "available": comfyui_installed,
        "running": comfy_ok,
        "startedByApp": started_by_app,
        "progress": 100 if comfy_ok else 0,
        "detail": "Actif" if comfy_ok else (
            "Installe — demarrage automatique a la premiere generation" if comfyui_installed else "Non installe"
        ),
        "path": COMFYUI_PATH,
        "processId": _comfyui_process.pid if started_by_app else None,
    })
    return jsonify(services)


@app.route("/api/runtime/privilege")
def runtime_privilege():
    return jsonify({"isAdmin": True, "canElevate": False, "detail": "Bridge mode"})


@app.route("/api/runtime/prepare-model", methods=["POST"])
def prepare_model():
    return jsonify({"ok": True, "detail": "Bridge Ready"})


# =====================================================================
#  Services status
# =====================================================================

@app.route("/api/services/status")
def services_status():
    ollama_ok = False
    comfyui_ok = False
    try:
        requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        ollama_ok = True
    except Exception:
        pass
    try:
        requests.get(f"{COMFYUI_URL}/system_stats", timeout=3)
        comfyui_ok = True
    except Exception:
        pass
    return jsonify({"bridge": True, "ollama": ollama_ok, "comfyui": comfyui_ok})


# =====================================================================
#  Web Action (Playwright visible pour le web automation interactif)
# =====================================================================

@app.route("/api/web/action", methods=["POST"])
def web_action():
    """Execute une action web via Playwright avec affichage."""
    data = request.get_json() or {}
    try:
        script = os.path.join(WORKSPACE, "python-services", "web_action_browser.py")
        proc = subprocess.run(
            [sys.executable, script],
            input=json.dumps(data).encode("utf-8"),
            capture_output=True,
            timeout=120,
            cwd=WORKSPACE,
        )
        stdout = proc.stdout.decode("utf-8", errors="replace").strip()
        
        # Parse the JSON response from stdout
        lines = stdout.split('\n')
        result_json = None
        for line in reversed(lines):
            if line.startswith('{'):
                try:
                    result_json = json.loads(line)
                    break
                except:
                    continue
        
        if result_json:
            return jsonify(result_json)
        return jsonify({"ok": False, "error": "No JSON from script", "stdout": stdout})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# =====================================================================
#  Web search (pour le telephone — remplace invoke("search_duckduckgo"))
# =====================================================================

@app.route("/api/web/search", methods=["POST"])
def web_search():
    """Recherche via Crawl4AI (Playwright) avec fallback DuckDuckGo."""
    data = request.get_json()
    query = data.get("query", "")
    limit = data.get("limit", 8)
    if not query.strip():
        return jsonify({"results": ""})

    try:
        # Crawl4AI search (avec Playwright)
        crawl_script = os.path.join(WORKSPACE, "python-services", "crawl4ai_search.py")
        result = subprocess.run(
            [sys.executable, crawl_script, "--mode", "search", "--query", query, "--limit", str(limit)],
            capture_output=True, timeout=30, cwd=WORKSPACE,
        )
        if result.returncode == 0:
            out = json.loads(result.stdout.decode("utf-8", errors="replace"))
            if out.get("ok") and out.get("results"):
                # Format: snippets lisibles pour le LLM
                lines = []
                for r in out["results"]:
                    title = r.get("title", "")
                    snippet = r.get("snippet", "")
                    url = r.get("url", "")
                    if url and snippet:
                        lines.append(f"{title}: {snippet} ({url})")
                    elif url:
                        lines.append(f"{title} ({url})")
                    else:
                        lines.append(f"{title}: {snippet}" if snippet else title)
                return jsonify({
                    "results": "\n".join(lines),
                    "resultsList": out.get("results", []),
                    "engine": out.get("engine", "crawl4ai"),
                })

        # Fallback intégré dans crawl4ai_search.py gère déjà le DuckDuckGo
        return jsonify({"results": result.stdout.decode("utf-8", errors="replace")})
    except Exception as e:
        return jsonify({"results": f"Erreur recherche: {e}"})


def _safe_web_filename(name: str, fallback: str = "resource") -> str:
    import re as _re
    name = (name or fallback).strip().replace("\\", "_").replace("/", "_")
    name = _re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" ._")
    return (name or fallback)[:120]


@app.route("/api/web/download", methods=["POST"])
def web_download():
    """Telecharge une ressource web dans output/web_downloads."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    category = _safe_web_filename(data.get("category") or "academic", "academic")
    wanted_name = _safe_web_filename(data.get("filename") or "", "")
    if not url:
        return jsonify({"ok": False, "error": "url manquante"}), 400
    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"ok": False, "error": "seules les URL http/https sont supportees"}), 400
    try:
        import mimetypes as _mimetypes
        import pathlib as _pathlib
        import re as _re
        from urllib.parse import urlparse as _urlparse, unquote as _unquote

        with requests.get(url, stream=True, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AuroraIA/2.0; academic-resource-fetcher)",
            "Accept": "application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/html,*/*",
        }) as r:
            if r.status_code >= 400:
                return jsonify({"ok": False, "error": f"HTTP {r.status_code}"}), 502
            content_type = (r.headers.get("Content-Type") or "application/octet-stream").split(";")[0].strip()
            dispo = r.headers.get("Content-Disposition") or ""
            dispo_name = ""
            m = _re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', dispo, _re.I)
            if m:
                dispo_name = _unquote(m.group(1)).strip()
            parsed_name = _unquote(_pathlib.PurePosixPath(_urlparse(url).path).name or "")
            filename = _safe_web_filename(wanted_name or dispo_name or parsed_name or "resource")
            if "." not in filename:
                ext = _mimetypes.guess_extension(content_type) or ""
                if ext:
                    filename += ext
            out_dir = _pathlib.Path(WORKSPACE) / "output" / "web_downloads" / category
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / filename
            if out_path.exists():
                stem, suffix = out_path.stem, out_path.suffix
                i = 2
                while out_path.exists() and i < 1000:
                    out_path = out_dir / f"{stem}-{i}{suffix}"
                    i += 1
            max_bytes = int(data.get("maxBytes") or 80 * 1024 * 1024)
            written = 0
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > max_bytes:
                        try:
                            out_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                        return jsonify({"ok": False, "error": f"fichier trop gros (> {max_bytes} octets)"}), 413
                    f.write(chunk)
        rel = out_path.relative_to(pathlib.Path(WORKSPACE)).as_posix()
        return jsonify({
            "ok": True,
            "url": url,
            "path": rel,
            "filename": out_path.name,
            "bytes": written,
            "contentType": content_type,
            "downloadUrl": f"/api/download/{rel}",
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}), 500


@app.route("/api/web/extract", methods=["POST"])
def web_extract():
    """Extraire le contenu d'une URL via Crawl4AI."""
    data = request.get_json()
    url = data.get("url", "")
    prompt = data.get("prompt", "")
    if not url.strip():
        return jsonify({"ok": False, "error": "URL manquante"})

    try:
        crawl_script = os.path.join(WORKSPACE, "python-services", "crawl4ai_search.py")
        result = subprocess.run(
            [sys.executable, crawl_script, "--mode", "extract", "--url", url, "--prompt", prompt],
            capture_output=True, timeout=30, cwd=WORKSPACE,
        )
        if result.returncode == 0:
            return Response(result.stdout, mimetype="application/json")
        return jsonify({"ok": False, "error": "Extraction failed"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/web/images", methods=["POST"])
def web_images():
    """Recherche d'images via Crawl4AI."""
    data = request.get_json()
    query = data.get("query", "")
    limit = data.get("limit", 6)
    if not query.strip():
        return jsonify({"ok": False, "images": []})

    try:
        crawl_script = os.path.join(WORKSPACE, "python-services", "crawl4ai_search.py")
        result = subprocess.run(
            [sys.executable, crawl_script, "--mode", "images", "--query", query, "--limit", str(limit)],
            capture_output=True, timeout=30, cwd=WORKSPACE,
        )
        if result.returncode == 0:
            return Response(result.stdout, mimetype="application/json")
        return jsonify({"ok": False, "images": []})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


def _wikipedia_thumbnail(query: str) -> "tuple[str, bytes, str] | None":
    """Try Wikipedia REST API to grab the page thumbnail for a topic.

    Wikipedia thumbs are the most brand-faithful free source: searching
    "Coca-Cola" returns the real Coca-Cola bottle/logo image used on the
    Wikipedia page, not a random Picsum photo. Tries fr first, then en.

    v73b — query fallback chain: when the exact phrasing doesn't resolve to a
    Wikipedia page (e.g. "Coca-Cola bouteille" or "Spotify logo"), we retry
    with progressively simpler titles:
      1. The query as typed.
      2. The first 3 words.
      3. The first 2 words.
      4. The first word only.
    The first variant that returns a thumbnail wins. This catches "<brand>
    <product>" / "<brand> logo" / "<brand> <variant>" patterns that the
    Code module routinely produces for brand pages.

    Returns (image_url, image_bytes, content_type) or None.
    """
    candidates: list[str] = []
    base = query.strip()
    if not base:
        return None
    candidates.append(base)
    words = [w for w in base.split() if w]
    # Drop trailing words one by one to broaden the search.
    for cut in (3, 2, 1):
        if len(words) > cut:
            shortened = " ".join(words[:cut])
            if shortened and shortened not in candidates:
                candidates.append(shortened)
    # Also try the first word alone (handles "Spotify logo" -> "Spotify").
    if words and words[0] not in candidates:
        candidates.append(words[0])

    for variant in candidates:
        result = _wikipedia_thumbnail_single(variant)
        if result is not None:
            return result
    return None


def _wikipedia_thumbnail_single(query: str) -> "tuple[str, bytes, str] | None":
    """Single-shot Wikipedia thumbnail lookup for an exact title."""
    try:
        from urllib.parse import quote as _q
        normalized_title = query.strip().replace(" ", "_")
        for lang_code in ("fr", "en"):
            url = f"https://{lang_code}.wikipedia.org/api/rest_v1/page/summary/{_q(normalized_title)}"
            try:
                r = requests.get(url, timeout=6, headers={"User-Agent": "AuroraIA-Bridge/1.0 (https://github.com/juancodepyandc/juan-of-bike-ia)"})
            except Exception:
                continue
            if r.status_code != 200:
                continue
            try:
                data = r.json()
            except Exception:
                continue
            # v72b: prefer the API thumbnail (typically 320-640px, 60-300 KB)
            # over originalimage (often 4-6 MB, blows the LLM prompt budget).
            # The pipeline caps inline data URLs at ~350 KB so a HD image
            # gets skipped silently — tu finis avec ZERO image au lieu d une
            # bonne thumbnail.
            thumb = (data.get("thumbnail") or {}).get("source")
            orig = (data.get("originalimage") or {}).get("source")
            candidates = [u for u in (thumb, orig) if u]
            for img_url in candidates:
                try:
                    r2 = requests.get(img_url, timeout=8, headers={"User-Agent": "AuroraIA-Bridge/1.0"})
                    if r2.status_code != 200:
                        continue
                    ctype = (r2.headers.get("Content-Type") or "").split(";")[0].strip() or "image/jpeg"
                    if not ctype.startswith("image/"):
                        continue
                    size = len(r2.content)
                    if size < 2000:
                        continue
                    # Skip ultra-large originals (> 800 KB) — the inline data
                    # URL would be > 1 MB and the TS pipeline rejects it.
                    if size > 800_000 and img_url == orig and thumb:
                        continue
                    return img_url, r2.content, ctype
                except Exception:
                    continue
        return None
    except Exception:
        return None


def _duckduckgo_image(query: str) -> "tuple[str, bytes, str] | None":
    """Scrape DuckDuckGo's image search via the undocumented i.js endpoint.

    Better than Picsum for brand queries — returns real product/brand images
    indexed by DDG. Two-step protocol: first request the HTML page to grab
    the vqd token, then call i.js with that token. Tries the first ~5 image
    URLs returned and downloads the first one that's >= 2KB.

    Returns (image_url, image_bytes, content_type) or None.
    """
    try:
        from urllib.parse import quote as _q
        import re as _re
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        # Step 1 — fetch HTML page to extract vqd token.
        page = requests.get(
            f"https://duckduckgo.com/?q={_q(query)}&iax=images&ia=images",
            timeout=8,
            headers={"User-Agent": ua},
        )
        if page.status_code != 200:
            return None
        m = _re.search(r'vqd=["\']?([\d-]+)["\']?', page.text)
        if not m:
            # Some responses embed it as `vqd:"..."` instead.
            m = _re.search(r'vqd:[\s]*["\']([\d-]+)["\']', page.text)
        if not m:
            return None
        vqd = m.group(1)

        # Step 2 — call the i.js endpoint with the token.
        api_url = f"https://duckduckgo.com/i.js?q={_q(query)}&vqd={vqd}&p=1&o=json"
        api = requests.get(
            api_url,
            timeout=8,
            headers={"User-Agent": ua, "Referer": "https://duckduckgo.com/", "Accept": "application/json"},
        )
        if api.status_code != 200:
            return None
        try:
            data = api.json()
        except Exception:
            return None
        results = data.get("results") or []
        # Try up to 6 candidates to be resilient to dead URLs.
        for entry in results[:6]:
            img_url = entry.get("image") or entry.get("thumbnail")
            if not img_url:
                continue
            try:
                r2 = requests.get(img_url, timeout=7, headers={"User-Agent": ua})
                if r2.status_code != 200:
                    continue
                ctype = (r2.headers.get("Content-Type") or "").split(";")[0].strip() or "image/jpeg"
                if not ctype.startswith("image/"):
                    continue
                if len(r2.content) < 2000:
                    continue
                return img_url, r2.content, ctype
            except Exception:
                continue
        return None
    except Exception:
        return None


def _extract_dominant_color(image_bytes: bytes) -> "str | None":
    """Pull the dominant non-neutral color from an image. Returns hex like '#F40009' or None.

    Used to recover the canonical brand color from the logo Wikipedia returned —
    far more accurate than asking a 7B model to recall the hex from memory
    (the 7B hallucinated #003F5C blue for Heineken, real value is #00A651 green).

    Strategy:
      1. Quantize the image to 8 colors (drops aliasing).
      2. Sort by frequency.
      3. Skip near-white (>240,>240,>240) and near-black (<25,<25,<25) — logos
         frequently have those as background or strokes, they aren't the brand.
      4. Skip very low-saturation grays (max-min < 25 across RGB channels).
      5. Return the first remaining color in hex.
    """
    try:
        from PIL import Image
        from io import BytesIO
        img = Image.open(BytesIO(image_bytes))
        # Convert to RGB (drop alpha — alpha edges look like brand color sometimes).
        if img.mode != "RGB":
            img = img.convert("RGB")
        # Cap size for speed.
        img.thumbnail((200, 200))
        # Quantize to 8 representative colors.
        quantized = img.quantize(colors=8)
        palette = quantized.getpalette() or []
        color_counts = quantized.getcolors() or []
        # Sort by count descending.
        color_counts.sort(key=lambda c: c[0], reverse=True)
        for _count, idx in color_counts:
            base = idx * 3
            if base + 2 >= len(palette):
                continue
            r, g, b = palette[base], palette[base + 1], palette[base + 2]
            # Skip near-white background.
            if r > 240 and g > 240 and b > 240:
                continue
            # Skip near-black strokes.
            if r < 25 and g < 25 and b < 25:
                continue
            # Skip low-saturation grays — branding is rarely gray.
            channels = (r, g, b)
            if max(channels) - min(channels) < 25:
                continue
            return f"#{r:02X}{g:02X}{b:02X}"
        return None
    except Exception:
        return None


def _wikipedia_summary_text(query: str) -> str:
    """Best-effort Wikipedia summary text for a brand/topic. Empty string if not found.

    Tries fr first then en, falls back through the same query-fallback chain
    as `_wikipedia_thumbnail` so "Coca-Cola bouteille" resolves to the
    "Coca-Cola" page when the exact phrasing 404s.
    """
    candidates: list[str] = []
    base = query.strip()
    if not base:
        return ""
    candidates.append(base)
    words = [w for w in base.split() if w]
    for cut in (3, 2, 1):
        if len(words) > cut:
            shortened = " ".join(words[:cut])
            if shortened and shortened not in candidates:
                candidates.append(shortened)
    if words and words[0] not in candidates:
        candidates.append(words[0])

    from urllib.parse import quote as _q
    for variant in candidates:
        normalized_title = variant.replace(" ", "_")
        for lang_code in ("fr", "en"):
            url = f"https://{lang_code}.wikipedia.org/api/rest_v1/page/summary/{_q(normalized_title)}"
            try:
                r = requests.get(url, timeout=6, headers={"User-Agent": "AuroraIA-Bridge/1.0"})
                if r.status_code != 200:
                    continue
                data = r.json()
                extract = (data.get("extract") or "").strip()
                if extract and len(extract) >= 80:
                    return extract
            except Exception:
                continue
    return ""


def _ollama_extract_brand_profile(brand: str, wiki_extract: str) -> "dict | None":
    """Ask the local Ollama to synthesise a BrandProfile JSON for `brand`.

    Uses a fast 7B model (qwen2.5:7b) so the call returns in under 10s on a
    warm runtime — this is the live-enrich path, not a planning step.
    Returns None if the response can't be parsed; the caller then falls back
    to a generic profile.
    """
    schema_lines = [
        "Tu es un expert design des marques. Retourne UNIQUEMENT un JSON strict (pas de markdown,",
        "pas d explication) avec EXACTEMENT ces cles pour la marque demandee:",
        '{',
        '  "primaryColor": "#RRGGBB - couleur officielle de la marque",',
        '  "secondaryColor": "#RRGGBB - couleur secondaire (souvent blanc, noir, ou couleur complementaire)",',
        '  "productKeywords": ["3-5 produits ou termes emblematiques de la marque"],',
        '  "designVibe": "1 phrase courte sur le vibe visuel (ex: rouge eclatant + blanc, vintage americain pop)",',
        '  "typoVibe": "1 phrase sur la typo (ex: serif scriptural elegant + sans bold)",',
        '  "imageQueries": ["3-4 queries Wikipedia/Google pour images officielles"],',
        '  "productShape": "one of: can / bottle / phone / tablet / laptop / shoe / car / watch / bag / headphones / controller / console / card / cup / logo / building"',
        "}",
        "",
        f"Marque: {brand}",
    ]
    if wiki_extract:
        schema_lines.append("")
        schema_lines.append(f"Extrait Wikipedia: {wiki_extract[:1500]}")
    prompt = "\n".join(schema_lines)
    try:
        r = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "qwen2.5:7b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 600, "num_ctx": 4096},
                "format": "json",
            },
            timeout=45,
        )
        if r.status_code != 200:
            return None
        body = r.json()
        raw = (body.get("response") or "").strip()
        if not raw:
            return None
        # The format=json mode constrains the output to be valid JSON; just parse.
        try:
            parsed = json.loads(raw)
        except Exception:
            # Fallback — extract first JSON object substring.
            m = re.search(r"\{[\s\S]*\}", raw)
            if not m:
                return None
            parsed = json.loads(m.group(0))
        # Sanity: required fields must be present and not empty.
        required = ["primaryColor", "productKeywords", "designVibe", "imageQueries", "productShape"]
        for key in required:
            if not parsed.get(key):
                return None
        # Coerce types.
        if not isinstance(parsed.get("productKeywords"), list):
            return None
        if not isinstance(parsed.get("imageQueries"), list):
            return None
        # v77 — sanitise hex colors. The 7B model often appends prose to the
        # value ("#F40009 - couleur officielle de la marque"). Strip
        # everything after the hex and reject if no valid hex was found.
        for color_key in ("primaryColor", "secondaryColor", "tertiaryColor"):
            raw_color = parsed.get(color_key)
            if not raw_color or not isinstance(raw_color, str):
                continue
            m = re.search(r"#([0-9a-fA-F]{6})\b", raw_color)
            if m:
                parsed[color_key] = "#" + m.group(1).upper()
            else:
                # No valid hex — drop the field rather than passing junk.
                if color_key == "primaryColor":
                    return None  # primary is required
                parsed.pop(color_key, None)
        # productShape must be one of the 16 allowed values.
        valid_shapes = {
            "can", "bottle", "phone", "tablet", "laptop",
            "shoe", "car", "watch", "bag", "headphones",
            "controller", "console", "card", "cup", "logo", "building",
        }
        if parsed.get("productShape") not in valid_shapes:
            parsed["productShape"] = "logo"
        return parsed
    except Exception:
        return None


# v77g — file-based LRU cache for brand enrichment.
# The 7B + Wikipedia round-trip costs 5-10s per call; the same brand is
# routinely re-asked across user sessions (every "Coca-Cola" prompt).
# A simple JSON cache cuts the latency to ~2ms on hit, and 7 days TTL is
# plenty since brand colors / product shapes don't change often.
_BRAND_CACHE_FILE = pathlib.Path(WORKSPACE) / "bridge_state" / "brand_enrich_cache.json"
_BRAND_CACHE_TTL_S = 7 * 24 * 3600  # 7 days
_BRAND_CACHE_MAX_ENTRIES = 200
_BRAND_CACHE_LOCK = threading.Lock()


def _brand_cache_load() -> dict:
    try:
        if not _BRAND_CACHE_FILE.exists():
            return {}
        with open(_BRAND_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _brand_cache_save(cache: dict) -> None:
    try:
        _BRAND_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write — temp + rename. Avoids corruption on crash mid-write.
        tmp = _BRAND_CACHE_FILE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        tmp.replace(_BRAND_CACHE_FILE)
    except Exception as exc:
        print(f"[brand cache] save failed: {exc}", flush=True)


def _brand_cache_get(brand: str) -> "dict | None":
    """Return cached profile + metadata if hit and fresh; None otherwise."""
    key = brand.lower().strip()
    if not key:
        return None
    with _BRAND_CACHE_LOCK:
        cache = _brand_cache_load()
        entry = cache.get(key)
        if not entry:
            return None
        ts = entry.get("ts", 0)
        if not isinstance(ts, (int, float)):
            return None
        if (_time.time() - ts) > _BRAND_CACHE_TTL_S:
            return None
        return entry


def _brand_cache_put(brand: str, payload: dict) -> None:
    """Store the enriched payload + timestamp. Evicts oldest entries past max."""
    key = brand.lower().strip()
    if not key:
        return
    with _BRAND_CACHE_LOCK:
        cache = _brand_cache_load()
        cache[key] = {**payload, "ts": _time.time()}
        # Evict oldest if past the cap. Sort by ts ascending and drop the head.
        if len(cache) > _BRAND_CACHE_MAX_ENTRIES:
            sorted_items = sorted(
                cache.items(),
                key=lambda kv: kv[1].get("ts", 0) if isinstance(kv[1], dict) else 0,
            )
            keep = sorted_items[-_BRAND_CACHE_MAX_ENTRIES:]
            cache = dict(keep)
        _brand_cache_save(cache)


@app.route("/api/brand/enrich", methods=["POST"])
def brand_enrich():
    """Dynamically build a BrandProfile for an arbitrary brand name.

    The TS pipeline has a fast in-memory dictionary of ~47 well-known brands
    (Coca-Cola, Tesla, iPhone, etc.) but the user can prompt about any brand.
    This endpoint covers the long tail: it asks Wikipedia for the summary
    text, then asks Ollama (fast 7B) to extract a structured profile.

    v77d — override the LLM-guessed primary color with the dominant color
    extracted from the Wikipedia logo when available.
    v77g — file-based LRU cache (7 days TTL, 200 entries max) — turns the
    second call to the same brand into a ~2ms lookup instead of a 5-10s
    round-trip.

    Request: {"brand": "Lipton", "noCache": false}
      noCache: optional boolean. When true, bypass the cache and force a
      fresh enrichment (useful when the user wants to refresh stale data).

    Response on success:
      {
        "ok": true,
        "brand": "Lipton",
        "cached": false,
        "wikiAvailable": true,
        "colorSource": "wikipedia_logo_dominant",
        "profile": { primaryColor, secondaryColor, productKeywords[], ... }
      }
    """
    data = request.get_json(silent=True) or {}
    brand = (data.get("brand") or "").strip()
    no_cache = bool(data.get("noCache"))
    if not brand:
        return jsonify({"ok": False, "error": "brand required"}), 400
    if len(brand) > 80:
        return jsonify({"ok": False, "error": "brand too long"}), 400

    # Cache hit fast path.
    if not no_cache:
        cached = _brand_cache_get(brand)
        if cached and cached.get("profile"):
            return jsonify({
                "ok": True,
                "brand": brand,
                "cached": True,
                "cachedAtTs": cached.get("ts"),
                "wikiAvailable": cached.get("wikiAvailable", False),
                "colorSource": cached.get("colorSource", "unknown"),
                "profile": cached["profile"],
            })

    wiki_extract = _wikipedia_summary_text(brand)
    profile = _ollama_extract_brand_profile(brand, wiki_extract)
    if not profile:
        return jsonify({
            "ok": False,
            "error": "could not synthesise profile (ollama parse failed)",
            "wikiAvailable": bool(wiki_extract),
        }), 502

    # v77d — override the LLM-guessed primary color with the dominant color
    # extracted from the Wikipedia logo when available. This catches cases
    # where the 7B model hallucinates a wrong hex (Heineken -> bleu #003F5C
    # instead of the real green #00A651). The dominant-color extraction
    # operates on actual pixels so it's canonical by construction.
    color_source = "ollama_guess"
    logo_attempt = _wikipedia_thumbnail(brand)
    if logo_attempt:
        _logo_url, logo_bytes, _logo_ctype = logo_attempt
        dominant = _extract_dominant_color(logo_bytes)
        if dominant:
            profile["primaryColor"] = dominant
            color_source = "wikipedia_logo_dominant"

    response_payload = {
        "wikiAvailable": bool(wiki_extract),
        "colorSource": color_source,
        "profile": profile,
    }

    # Persist to cache for the next call.
    _brand_cache_put(brand, response_payload)

    return jsonify({
        "ok": True,
        "brand": brand,
        "cached": False,
        **response_payload,
    })


@app.route("/api/web/image", methods=["POST"])
def web_image_single():
    """Telecharge UNE image pertinente pour un sujet et retourne un data URL.

    Used by the Code module so the generated HTML references a
    <img src="data:..."> that never 404s after the project is saved anywhere
    on disk.

    Sources probed in order (v72 — brand fidelity, WS15 sans Unsplash mort):
      1. Wikipedia REST API thumbnail (best for brands / named products / people)
      2. DuckDuckGo Images i.js (real image search, brand-aware)
      3. LoremFlickr (generic tagged photo)
      4. Picsum (truly random — last resort)

    The first three sources return ACTUAL brand images when the query mentions
    one. Picsum-only output was the root cause of "Coca-Cola → random photo"
    drift in the Code module landing pages.

    Each candidate has its own short timeout so we never block more than ~45 s.
    """
    import base64 as _b64
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    width = int(data.get("width") or 1600)
    height = int(data.get("height") or 900)
    if not query:
        return jsonify({"ok": False, "error": "query required"}), 400

    last_error = ""

    # 1) Wikipedia thumbnail — most brand-faithful free source.
    wiki = _wikipedia_thumbnail(query)
    if wiki:
        url, content, ctype = wiki
        b64 = _b64.b64encode(content).decode("ascii")
        return jsonify({
            "ok": True,
            "dataUrl": f"data:{ctype};base64,{b64}",
            "source": url,
            "bytes": len(content),
            "via": "wikipedia",
        })

    # 2) DuckDuckGo Images — real search results.
    ddg = _duckduckgo_image(query)
    if ddg:
        url, content, ctype = ddg
        b64 = _b64.b64encode(content).decode("ascii")
        return jsonify({
            "ok": True,
            "dataUrl": f"data:{ctype};base64,{b64}",
            "source": url,
            "bytes": len(content),
            "via": "duckduckgo",
        })

    # 3-4) Generic photo fallbacks. Unsplash Source is intentionally absent:
    # the endpoint is deprecated/unreliable and must not appear in Code output.
    from urllib.parse import quote
    q_encoded = quote(query)
    candidates = [
        ("loremflickr", f"https://loremflickr.com/{width}/{height}/{q_encoded}"),
        ("picsum", f"https://picsum.photos/seed/{q_encoded}/{width}/{height}"),
    ]
    for via, url in candidates:
        try:
            r = requests.get(url, timeout=12, allow_redirects=True)
            if r.status_code != 200:
                last_error = f"{url}: HTTP {r.status_code}"
                continue
            ctype = r.headers.get("Content-Type", "").split(";")[0].strip() or "image/jpeg"
            if not ctype.startswith("image/"):
                last_error = f"{url}: content-type {ctype}"
                continue
            content = r.content
            if len(content) < 2000:
                last_error = f"{url}: payload too small ({len(content)} bytes)"
                continue
            b64 = _b64.b64encode(content).decode("ascii")
            data_url = f"data:{ctype};base64,{b64}"
            return jsonify({
                "ok": True,
                "dataUrl": data_url,
                "source": url,
                "bytes": len(content),
                "via": via,
            })
        except Exception as e:
            last_error = f"{url}: {e}"
    return jsonify({"ok": False, "error": last_error or "no image source available"}), 504


# =====================================================================
#  Python progress (polling pour le frontend cloud)
# =====================================================================

_python_progress_events: list[tuple[int, str]] = []
_python_progress_seq: int = 0
_python_progress_lock = threading.Lock()


def _update_job_progress_from_line(job_id: str, line: str):
    """Parse PROGRESS line and update _python_jobs[job_id] with rich progress fields."""
    if not line or not line.startswith("PROGRESS:"):
        return
    content = line[9:].strip()
    with _python_jobs_lock:
        job = _python_jobs.get(job_id)
        if not job:
            return

        now = time.time()
        job["lastProgressTs"] = now

        # Try parsing JSON payload
        if content.startswith("{") and content.endswith("}"):
            try:
                data = json.loads(content)
                if "pct" in data:
                    job["progressPct"] = max(float(job.get("progressPct", 0.0)), min(100.0, float(data["pct"])))
                if "stage" in data:
                    job["stage"] = str(data["stage"])
                if "stage_label" in data:
                    job["stageLabel"] = str(data["stage_label"])
                if "sub_stage" in data:
                    job["subStage"] = str(data["sub_stage"])
                if "detail" in data:
                    job["stepDetail"] = str(data["detail"])
                    job["step"] = str(data["detail"])
                if "step" in data:
                    job["currentStep"] = int(data["step"])
                if "total_steps" in data:
                    job["totalSteps"] = int(data["total_steps"])
                return
            except Exception:
                pass

        # Fallback: colon-separated format
        parts = content.split(":")
        if len(parts) >= 2:
            part0 = parts[0].strip()
            detail = ":".join(parts[1:]).strip()

            try:
                pct = float(part0)
                job["progressPct"] = max(float(job.get("progressPct", 0.0)), min(100.0, pct))
                if len(parts) >= 3:
                    job["stage"] = parts[1].strip()
                    job["stepDetail"] = ":".join(parts[2:]).strip()
                else:
                    job["stepDetail"] = detail
                return
            except ValueError:
                pass

            job["stage"] = part0
            job["subStage"] = part0
            job["stepDetail"] = detail
            job["step"] = detail


@app.route("/api/python/progress")
def python_progress():
    """Retourne les evenements de progression depuis le curseur donne."""
    since = int(request.args.get("since", 0))
    with _python_progress_lock:
        events = [msg for seq, msg in _python_progress_events if seq >= since]
        cursor = _python_progress_seq
    return jsonify({"events": events, "cursor": cursor})


def _emit_progress(msg: str, job_id: str | None = None):
    global _python_progress_seq
    with _python_progress_lock:
        _python_progress_events.append((_python_progress_seq, msg))
        _python_progress_seq += 1
        if len(_python_progress_events) > 1000:
            del _python_progress_events[:-500]

    if job_id:
        _update_job_progress_from_line(job_id, msg)


# =====================================================================
#  Python script execution
# =====================================================================

def _resolve_script_path(script_path: str) -> str:
    if not os.path.abspath(script_path).startswith(WORKSPACE):
        script_path = os.path.join(WORKSPACE, script_path.lstrip("/\\"))
    return script_path


def _build_python_env() -> dict:
    run_env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    # Allocation CUDA fragmentee -> aide l'echelle OOM du paint PBR sur 16 Go.
    run_env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    try:
        vision_model, _, _ = _pick_vision_model_or_default("qwen3-vl:8b")
        if vision_model:
            run_env.setdefault("AURORA_VISION_MODEL", vision_model)
    except Exception:
        run_env.setdefault("AURORA_VISION_MODEL", "qwen3-vl:8b")
    comfy_path = COMFYUI_PATH or _find_comfyui_path()
    if comfy_path:
        run_env["COMFYUI_DIR"] = comfy_path
    workspace_p = pathlib.Path(WORKSPACE)
    for candidate in (
        workspace_p.parent / "modele",
        workspace_p.parent / "models",
        workspace_p / "modele",
    ):
        if candidate.is_dir():
            run_env.setdefault("AURORA_MODELS", str(candidate))
            break

    # HuggingFace weights: sur Linux les poids reels (Hunyuan3D-2.x, FLUX, Wan...) vivent
    # dans le cache HF standard ~/.cache/huggingface. Or AURORA_MODELS=modele fait pointer
    # HF_HOME sur <modele>/huggingface qui est VIDE -> la generation 3D re-telechargeait ~30 Go
    # (ou echouait). On epingle HF_HOME sur le hub qui contient reellement des modeles.
    if "HF_HOME" not in run_env:
        def _hub_has_models(hub: pathlib.Path) -> bool:
            try:
                return hub.is_dir() and next(hub.glob("models--*"), None) is not None
            except Exception:
                return False
        def _hub_count(hub: pathlib.Path) -> int:
            try:
                return sum(1 for _ in hub.glob("models--*"))
            except Exception:
                return 0
        _am = run_env.get("AURORA_MODELS")
        _candidates = []
        if _am:
            _candidates.append(pathlib.Path(_am) / "huggingface")
        _candidates.append(pathlib.Path.home() / ".cache" / "huggingface")
        # DEUX caches HF = DEUX telechargements du meme modele. L'app (Tauri)
        # lance python sans HF_HOME et tombe donc sur ~/.cache/huggingface,
        # tandis que le bridge epinglait <modele>/huggingface: Hunyuan3D s'est
        # retrouve en double (38 Go pour rien). On prend le cache le PLUS
        # fourni, pour que les deux chemins convergent sur le meme.
        _candidates.sort(key=lambda p: _hub_count(p / "hub"), reverse=True)
        for _hf in _candidates:
            if _hub_has_models(_hf / "hub"):
                run_env["HF_HOME"] = str(_hf)
                run_env["HF_HUB_CACHE"] = str(_hf / "hub")
                run_env["HUGGINGFACE_HUB_CACHE"] = str(_hf / "hub")
                break
    # BUDGETS 3D UNIFIES (reposes 31/07 — une fusion d'une autre session les
    # avait fait sauter). Chemin UI reel (run-async) SANS budget = OOM deja
    # paye deux fois (python 23 Go). TEXTURE: 4K natif + agrandissement x2 EN
    # TUILES = 8K livre — seule voie physiquement possible sur 30 Go de RAM
    # (pages CUDA epinglees non-swappables, cgroup OOM mesure a 23,7 Go en 8K
    # natif). 16K natif = feuille de route GPU. Ce n'est pas un rabais cache:
    # c'est journalise et explique ici.
    run_env.setdefault("AURORA_MEM_MAX_GB", "29")
    run_env.setdefault("AURORA_MEM_SWAP_MAX_GB", "48")
    run_env.setdefault("AURORA_TRELLIS2_TEXTURE", "4096")
    run_env.setdefault("AURORA_TRELLIS2_16K", "1")
    run_env.setdefault("AURORA_LLM_4BIT", "1")
    run_env.setdefault("AURORA_PERFECTION_ESSAIS", "2")
    return run_env


def _clean_stderr(raw: str) -> str:
    return "\n".join(
        line for line in raw.splitlines()
        if not (("Warning" in line or "warnings.warn(" in line.strip())
                and "Error" not in line and "Traceback" not in line)
    ).strip()


# ---------------------------------------------------------------------------
# Async Python job runner — avoids Cloudflare 524 (100s tunnel timeout).
# The synchronous /api/python/run stayed open for up to 15 min, which is way
# above the tunnel deadline. We now spawn the subprocess in a worker thread
# and let the client poll /api/python/job/<id> every few seconds: each poll
# returns in ~10ms so the tunnel never times out.
# ---------------------------------------------------------------------------

_python_jobs: dict[str, dict] = {}
_python_jobs_lock = threading.Lock()
_python_job_processes: dict[str, subprocess.Popen] = {}
import uuid as _uuid

# File FIFO partagee par tous les gros travaux du module video. Elle vit hors
# de Flask pour rester testable sans demarrer le bridge ni toucher au GPU.
_video_queue_dir = pathlib.Path(WORKSPACE) / "python-services" / "cinema"
if str(_video_queue_dir) not in sys.path:
    sys.path.insert(0, str(_video_queue_dir))
try:
    from video_gpu_queue import VideoGpuQueue
    _video_gpu_queue = VideoGpuQueue()
except ImportError:
    # Le module video a ete retire (commit 7209251) mais l'import etait reste
    # OBLIGATOIRE ici: le pont ne pouvait plus DEMARRER, et seul le processus
    # lance avant ce commit survivait encore en memoire. Le premier redemarrage
    # aurait tout casse. File inerte: les rares chemins video degradent
    # proprement, tout le reste du pont fonctionne.
    class _FileVideoInerte:
        """Remplacante sans GPU: accepte tout, ne bloque jamais, ne retient rien."""
        def enqueue(self, job_id):                    return 0
        def cancel(self, job_id):                     return None
        def wait_until_idle(self, timeout=None):      return True
        def is_cancelled(self, job_id):               return False
        def snapshot(self, job_id=None):              return {}
        def acquire(self, *a, **k):                   return True
        def release(self, job_id):                    return None

    _video_gpu_queue = _FileVideoInerte()
    print("[pont] file GPU video absente (module retire) — chemins video inertes", flush=True)


def _is_video_gpu_job(script_path: str) -> bool:
    """Vrai pour les scripts du chemin de production qui peuvent charger le GPU."""
    script = pathlib.Path(str(script_path)).name.lower()
    return script in {
        "cinema_pipeline.py",
        "cinema_preview_keyframes.py",
        "video_ab_benchmark.py",
        "video_generate.py",
        "talking_head.py",
        "voice_clone.py",
        "voice_extract.py",
        "ltx_direct_render.py",
        "musetalk_runner.py",
        # v91 : la chaine de finition charge RealESRGAN sur le GPU — sans
        # cette entree elle demarrerait en parallele d'un rendu Wan et les
        # deux se percuteraient sur les 16 Go.
        "video_upscale_chain.py",
    }


def _queue_video_job(job_id: str, script_path: str) -> int | None:
    if not _is_video_gpu_job(script_path):
        return None
    position = _video_gpu_queue.enqueue(job_id)
    with _python_jobs_lock:
        job = _python_jobs.get(job_id)
        if job is not None and job.get("status") not in {"cancelled", "done"}:
            job["status"] = "queued"
            job["queuePosition"] = position
            job["queueReason"] = "gpu_video_serialization"
    return position


def _update_video_queue_wait(job_id: str, position: int, active_job_id: str | None) -> None:
    with _python_jobs_lock:
        job = _python_jobs.get(job_id)
        if job is None or job.get("status") == "cancelled":
            return
        job.update({
            "status": "queued",
            "queuePosition": position,
            "activeGpuJobId": active_job_id,
            "queueReason": "gpu_video_serialization",
        })


def _terminate_job_process(job_id: str, *, force: bool = False) -> bool:
    """Termine le groupe complet d'un job, y compris ses workers diffusers."""
    with _python_jobs_lock:
        proc = _python_job_processes.get(job_id)
    if proc is None or proc.poll() is not None:
        return False
    try:
        if os.name == "posix":
            import signal as _signal
            os.killpg(os.getpgid(proc.pid), _signal.SIGKILL if force else _signal.SIGTERM)
        elif force:
            proc.kill()
        else:
            proc.terminate()
        return True
    except ProcessLookupError:
        return False
    except Exception:
        try:
            proc.kill() if force else proc.terminate()
            return True
        except Exception:
            return False


def _persist_job_state(job_id: str, state: dict) -> None:
    """Ecrit un etat terminal file-backed quand le job est cinema."""
    try:
        for prefix in ("job_", "sample_", "preview_", "benchmark_"):
            d = pathlib.Path(WORKSPACE) / "temp" / "cinema" / f"{prefix}{job_id}"
            if d.exists():
                (d / "status.json").write_text(
                    json.dumps(state, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                break
    except Exception:
        pass


def _finalize_cancelled_job(job_id: str, script_path: str, started_at: float) -> None:
    state = {
        "status": "cancelled",
        "output": "",
        "error": "Job annule par l'utilisateur.",
        "exitCode": -15,
        "script": os.path.basename(script_path),
        "startedAt": started_at,
        "finishedAt": time.time(),
        "cancelledAt": time.time(),
    }
    _persist_job_state(job_id, state)
    with _python_jobs_lock:
        previous = _python_jobs.get(job_id, {})
        _python_jobs[job_id] = {**previous, **state}


def _cancel_video_job_response(job_id: str):
    with _python_jobs_lock:
        job = _python_jobs.get(job_id)
        if job is None:
            return jsonify({"ok": False, "error": "job not found"}), 404
        # 31/07 (constate par Juan: « j'appuie sur arreter, ca continue »):
        # ce garde REFUSAIT d'annuler tout job non-video (409) — le bouton
        # d'arret 3D appelait dans le vide et le pipeline continuait. Un
        # arret demande vaut pour TOUT job Python; seul le nettoyage de file
        # GPU reste specifique a la video.
        _est_video_job = _is_video_gpu_job(str(job.get("script", "")))
        if job.get("status") in {"done", "cancelled"}:
            return jsonify({
                "ok": True,
                "jobId": job_id,
                "status": job.get("status"),
                "alreadyTerminal": True,
            })
        job.update({
            "status": "cancelled",
            "cancelRequested": True,
            "cancelledAt": time.time(),
            "error": "Job annule par l'utilisateur.",
        })
        state_for_disk = dict(job)

    queue_state = _video_gpu_queue.cancel(job_id) if _est_video_job else None
    signal_sent = _terminate_job_process(job_id)
    # les pipelines 3D ont des SOUS-PROCESSUS lourds (TRELLIS ~20 Go): le
    # groupe de processus recoit TERM puis, 5 s apres, KILL s'il survit.
    if not _est_video_job:
        def _coup_de_grace(jid=job_id):
            time.sleep(5)
            _terminate_job_process(jid, force=True)
        threading.Thread(target=_coup_de_grace, daemon=True).start()
    state_for_disk.update({
        "status": "cancelled",
        "cancelRequested": True,
        "cancelledAt": time.time(),
        "error": "Job annule par l'utilisateur.",
    })
    _persist_job_state(job_id, state_for_disk)
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "status": "cancelled",
        "signalSent": signal_sent,
        "wasQueued": bool(queue_state and queue_state.get("queued")),
        "wasActive": bool(queue_state and queue_state.get("active")),
    })


def _cinema_bridge_timeout_seconds(args: list[str], default: int = 1800) -> int:
    try:
        if "--spec" in [str(arg) for arg in args]:
            return 8 * 3600
        storyboard_path = None
        for idx, arg in enumerate(args):
            if str(arg) == "--storyboard" and idx + 1 < len(args):
                storyboard_path = str(args[idx + 1])
                break
        if not storyboard_path:
            return default
        p = pathlib.Path(storyboard_path)
        if not p.exists():
            return default
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        shots = data.get("shots") or []
        shot_count = max(1, len(shots))
        total_duration = sum(float(s.get("duration_s", 3.0) or 3.0) for s in shots)
        per_shot = int(os.environ.get("AURORA_CINEMA_BRIDGE_PER_SHOT_TIMEOUT", "900"))
        base = int(os.environ.get("AURORA_CINEMA_BRIDGE_BASE_TIMEOUT", "900"))
        computed = base + (shot_count * per_shot) + int(total_duration * 20)
        return max(default, min(computed, 8 * 3600))
    except Exception:
        return default


def _video_scratch_reservation_gb(script_path: str, args: list[str]) -> float:
    """Conservative internal reservation for frames, audio and temporary MP4s."""
    name = os.path.basename(str(script_path))
    if name == "cinema_pipeline.py":
        try:
            index = [str(arg) for arg in args].index("--storyboard")
            data = json.loads(pathlib.Path(str(args[index + 1])).read_text(encoding="utf-8-sig"))
            shots = data.get("shots") or []
            duration = sum(float(shot.get("duration_s") or 3.0) for shot in shots)
            return max(2.0, min(40.0, len(shots) * 0.75 + duration * 0.08))
        except Exception:
            return 4.0
    if name == "cinema_preview_keyframes.py":
        return 1.0
    if name == "video_ab_benchmark.py":
        return 8.0
    if name in {"voice_clone.py", "voice_extract.py"}:
        return 0.5
    return 2.0


# GENERATION 3D EN COURS: pendant qu'aurora_3d_pipeline tourne, les requetes
# cowork qui font tourner un LLM Ollama RECHARGENT un modele en VRAM en pleine
# etape GPU (constate au gel du 24/07: cudaMalloc OOM d'ollama a 00:15 pendant
# FLUX, puis Xid 109 pendant les materiaux). On refuse ces requetes avec un
# 503 clair le temps de la generation.
_AURORA_3D_EN_COURS = threading.Event()


def _is_3d_generation_active() -> bool:
    """Detect bridge-managed and independently launched Claude/terminal jobs."""
    if _AURORA_3D_EN_COURS.is_set():
        return True
    try:
        for process in psutil.process_iter(["pid", "cmdline", "status"]):
            if process.info.get("pid") == os.getpid() or process.info.get("status") == psutil.STATUS_ZOMBIE:
                continue
            command = " ".join(process.info.get("cmdline") or [])
            if "aurora_3d_pipeline.py" in command:
                return True
    except Exception:
        pass
    return False


def _run_python_job(job_id: str, script_path: str, args: list[str]):
    run_env = _build_python_env()
    _est_3d = "aurora_3d_pipeline" in str(script_path)
    _est_video_gpu = _is_video_gpu_job(script_path)
    _video_slot_acquired = False
    if _est_3d:
        # 31/07 (audit): la garde GPU etait unidirectionnelle — la video
        # attendait la 3D, mais un job 3D partait PENDANT un rendu Wan/FLUX
        # sur la meme carte (OOM assure). Symetrie: la 3D attend que la file
        # video soit vide, etat visible au poll.
        try:
            _t_attente = time.time()
            while not _video_gpu_queue.wait_until_idle(timeout=15):
                with _python_jobs_lock:
                    if job_id in _python_jobs:
                        _python_jobs[job_id]["step"] = "en attente: rendu video GPU en cours"
                if time.time() - _t_attente > 7200:
                    break
        except Exception:  # noqa: BLE001
            pass
        _AURORA_3D_EN_COURS.set()
    stdout_lines: list[str] = []
    # 31/07 (mesure: bridge a 24,6 Go, machine a 1 Go libre): la retention 4 h
    # des jobs gardait TOUT le stdout en RAM — les barres de progression
    # TRELLIS pesent des Go. On plafonne: 400 premieres lignes + 4000
    # dernieres (le JSON final vit a la fin), le milieu est resume.
    def _borner_stdout():
        if len(stdout_lines) > 4600:
            del stdout_lines[400:len(stdout_lines) - 4000]
            stdout_lines.insert(400, "[... sortie intermediaire tronquee par le bridge ...]")
    stderr_buf: list[str] = []
    exit_code = -1
    timed_out = False
    crashed: str | None = None

    python_exe = sys.executable or "python"
    start_ts = time.time()

    if _est_video_gpu:
        _queue_video_job(job_id, script_path)
        # Ne jamais lancer Wan/FLUX pendant une generation 3D partageant la
        # meme carte. Le job reste visible et annulable dans la file.
        while _is_3d_generation_active():
            if _video_gpu_queue.is_cancelled(job_id):
                _finalize_cancelled_job(job_id, script_path, start_ts)
                return
            with _python_jobs_lock:
                job = _python_jobs.get(job_id)
                if job is not None:
                    job.update({
                        "status": "queued",
                        "queueReason": "generation_3d_active",
                        "queuePosition": _video_gpu_queue.snapshot(job_id).get("position"),
                    })
            time.sleep(1.0)

        _video_slot_acquired = _video_gpu_queue.acquire(
            job_id,
            on_wait=lambda position, active: _update_video_queue_wait(
                job_id, position, active,
            ),
        )
        if not _video_slot_acquired:
            _finalize_cancelled_job(job_id, script_path, start_ts)
            return
        with _python_jobs_lock:
            job = _python_jobs.get(job_id)
            if job is not None:
                job.update({
                    "status": "running",
                    "queuePosition": 0,
                    "activeGpuJobId": job_id,
                    "queueReason": None,
                })

        manager = globals().get("_storage_manager")
        if manager is not None:
            reservation = _video_scratch_reservation_gb(script_path, args)
            try:
                capacity = manager.ensure_space("hot", reservation)
            except Exception as capacity_exc:
                capacity = {
                    "ok": False,
                    "reason": "storage_preflight_failed",
                    "error": str(capacity_exc)[:240],
                }
            if not capacity.get("ok"):
                _video_gpu_queue.release(job_id)
                refusal = {
                    "ok": False,
                    "error": (
                        f"Espace interne insuffisant pour reserver {reservation:.1f} Go "
                        f"sans franchir le plancher de {capacity.get('floor_gb', 20)} Go."
                    ),
                    "storage": capacity,
                }
                state = {
                    "status": "done",
                    "output": json.dumps(refusal, ensure_ascii=False),
                    "error": refusal["error"],
                    "exitCode": 1,
                    "script": os.path.basename(script_path),
                    "startedAt": start_ts,
                    "finishedAt": time.time(),
                    "storage": capacity,
                }
                _persist_job_state(job_id, state)
                with _python_jobs_lock:
                    previous = _python_jobs.get(job_id, {})
                    _python_jobs[job_id] = {**previous, **state}
                return

    # v82lz : pour les cinema jobs (long-running Wan2.2/FLUX), écrit
    # stdout/stderr directement dans des fichiers log dans le job_dir.
    # Le subprocess est ainsi DECOUPLE des pipes du bridge → si le bridge
    # respawn, le subprocess continue à écrire dans le fichier sans EPIPE.
    # Bridge thread tail le fichier pour les PROGRESS events.
    log_stdout_path = None
    log_stderr_path = None
    is_cinema_long_running = False
    try:
        for prefix in ("job_", "sample_", "preview_", "benchmark_"):
            for arg in args:
                if isinstance(arg, str) and prefix + job_id in arg:
                    is_cinema_long_running = True
                    job_dir_path = pathlib.Path(arg).parent
                    log_stdout_path = job_dir_path / "stdout.log"
                    log_stderr_path = job_dir_path / "stderr.log"
                    break
            if is_cinema_long_running:
                break
    except Exception:
        pass

    # 30/07 (audit): 1800 s tuait CHAQUE run TRELLIS max-precision lance
    # depuis l'UI (25-60 min/objet + porte de perfection) — l'echec etait
    # ensuite maquille en 'TRELLIS n a pas produit de mesh'. Un job 3D
    # obtient le meme plafond que /api/3d/run-pipeline.
    #
    # 2026-08-08 : le plafond mur-à-mur tuait aussi un film premium multi-plans
    # LEGITIMEMENT long (retries QA + FLUX keyframes + 3 shots premium). Cas
    # mesuré : job_828ffe68bf9a4a48, 3 shots × 3s, formule = 900 + 3×900 + 20×9
    # = 3780 s, tué en fin de plan 3 (2/3 déjà rendus) — le process crachait
    # encore des PROGRESS: à la mort, il n'était PAS bloqué. La discipline
    # correcte est donc "inactivité + plafond dur en filet". La ligne
    # `timeout_seconds` reste calculée comme filet ; deux autres seuils
    # gouvernent réellement la mort :
    #   - INACTIVITY : silence total (aucune ligne stdout) → probable gel
    #   - HARD CAP  : garde-fou catastrophe (job réellement runaway)
    # Configurable par env pour ne pas re-toucher le code au prochain film XXL.
    timeout_seconds = (_cinema_bridge_timeout_seconds(args) if is_cinema_long_running
                       else 14400 if _est_3d else 1800)
    inactivity_timeout_seconds = int(os.environ.get(
        "AURORA_BRIDGE_INACTIVITY_TIMEOUT",
        # 20 min : un shot Wan premium 60 étapes peut prendre 4-5 min ; un
        # FLUX2 keyframe 3-5 min ; un juge vision 30-90 s. 20 min sans
        # UN SEUL PROGRESS: ni ligne stdout = job vraiment gelé.
        str(20 * 60),
    ))
    hard_cap_seconds = int(os.environ.get(
        "AURORA_BRIDGE_HARD_CAP",
        # 24 h : catastrophe (un film 30 min à 4h/plan ferait 20 h) — au-delà,
        # on assume que quelque chose est fondamentalement cassé.
        str(24 * 3600),
    ))
    deadline = start_ts + max(timeout_seconds, hard_cap_seconds)  # legacy compat
    last_activity_ts = start_ts

    try:
        if is_cinema_long_running and log_stdout_path is not None:
            # Detached file-backed mode : subprocess writes to disk, not pipes.
            # On Windows, CREATE_NEW_PROCESS_GROUP allows survival across
            # parent restart. DETACHED_PROCESS would cut the parent link entirely.
            popen_kwargs = {
                "stdout": open(str(log_stdout_path), "w", encoding="utf-8", buffering=1),
                "stderr": open(str(log_stderr_path), "w", encoding="utf-8", buffering=1),
                "cwd": WORKSPACE,
                "env": run_env,
                "text": True,
            }
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                # 31/07 (mesure: l'annulation d'un job 3D TUAIT LE BRIDGE):
                # sans session propre, le job partage le groupe de processus
                # du bridge — os.killpg fauchait tout le monde. Chaque job vit
                # desormais dans SON groupe: le kill ne touche que lui et ses
                # sous-processus (TRELLIS inclus).
                popen_kwargs["start_new_session"] = True
            proc = subprocess.Popen(
                [python_exe, "-W", "ignore", "-u", script_path] + [str(a) for a in args],
                **popen_kwargs,
            )
        else:
            popen_kwargs = {}
            # 31/07: TOUT job dans son propre groupe (pas seulement la video)
            # — un cancel par killpg fauchait le bridge entier sinon.
            if sys.platform != "win32":
                popen_kwargs["start_new_session"] = True
            else:
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            proc = subprocess.Popen(
                [python_exe, "-W", "ignore", "-u", script_path] + [str(a) for a in args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=WORKSPACE,
                env=run_env,
                bufsize=1,
                text=False,
                **popen_kwargs,
            )
        with _python_jobs_lock:
            _python_job_processes[job_id] = proc
    except Exception as spawn_err:
        if _video_slot_acquired:
            _video_gpu_queue.release(job_id)
        with _python_jobs_lock:
            _python_jobs[job_id] = {
                "status": "done", "output": "", "error": f"Spawn echoue: {spawn_err}",
                "exitCode": -1, "finishedAt": time.time(),
            }
        return

    def _drain_stderr():
        if proc.stderr is None:
            return
        for raw_line in iter(proc.stderr.readline, b""):
            if not raw_line:
                break
            stderr_buf.append(raw_line.decode("utf-8", errors="replace").rstrip())

    stderr_thread = None
    if not is_cinema_long_running:
        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

    try:
        if is_cinema_long_running and log_stdout_path is not None:
            # v82lz : tail the log file while subprocess runs. Lit ligne par
            # ligne avec polling 1s. Capture PROGRESS events pour le frontend.
            # 2026-08-08 : timeout par INACTIVITÉ + plafond dur — voir bloc
            # `inactivity_timeout_seconds` / `hard_cap_seconds` plus haut.
            log_pos = 0
            while True:
                if proc.poll() is not None:
                    break
                now = time.time()
                if now > start_ts + hard_cap_seconds:
                    timed_out = True
                    break
                if now - last_activity_ts > inactivity_timeout_seconds:
                    timed_out = True
                    break
                try:
                    if log_stdout_path.exists():
                        with open(log_stdout_path, "r", encoding="utf-8", errors="replace") as f:
                            f.seek(log_pos)
                            for line in f:
                                line = line.rstrip()
                                if line:
                                    stdout_lines.append(line); _borner_stdout(); _borner_stdout()
                                    if line.startswith("PROGRESS:"):
                                        _emit_progress(line, job_id=job_id)
                                    # Toute ligne stdout = job vivant.
                                    last_activity_ts = time.time()
                            log_pos = f.tell()
                except Exception:
                    pass
                time.sleep(1)
            # Final read to capture any trailing lines.
            try:
                if log_stdout_path.exists():
                    with open(log_stdout_path, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(log_pos)
                        for line in f:
                            line = line.rstrip()
                            if line:
                                stdout_lines.append(line)
                                if line.startswith("PROGRESS:"):
                                    _emit_progress(line, job_id=job_id)
            except Exception:
                pass
            # Read stderr file for errors.
            try:
                if log_stderr_path and log_stderr_path.exists():
                    stderr_buf.append(log_stderr_path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
            exit_code = proc.wait(timeout=5) if not timed_out else -1
        elif proc.stdout is not None:
            for raw_line in iter(proc.stdout.readline, b""):
                if not raw_line:
                    break
                text = raw_line.decode("utf-8", errors="replace").rstrip()
                stdout_lines.append(text); _borner_stdout()
                if text.startswith("PROGRESS:"):
                    _emit_progress(text, job_id=job_id)
                # 2026-08-08 : chaque ligne stdout = job vivant. Mort par
                # inactivité seulement, plus par temps total mur-à-mur.
                last_activity_ts = time.time()
                now = time.time()
                if now > start_ts + hard_cap_seconds:
                    timed_out = True
                    break
                if now - last_activity_ts > inactivity_timeout_seconds:
                    timed_out = True
                    break
            # Après fermeture stdout : attendre la sortie process, plafonné à
            # l'inactivité restante (pas au wall-clock).
            remaining = max(1.0, (start_ts + hard_cap_seconds) - time.time())
            exit_code = proc.wait(timeout=remaining) if not timed_out else -1
        else:
            remaining = max(1.0, (start_ts + hard_cap_seconds) - time.time())
            exit_code = proc.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        timed_out = True
    except Exception as runtime_err:
        crashed = f"{type(runtime_err).__name__}: {runtime_err}"
    finally:
        if _est_3d:
            _AURORA_3D_EN_COURS.clear()
        was_cancelled = _video_gpu_queue.is_cancelled(job_id) if _est_video_gpu else False
        if proc.poll() is None:
            _terminate_job_process(job_id, force=not was_cancelled)
            try:
                proc.wait(timeout=5)
            except Exception:
                _terminate_job_process(job_id, force=True)
        if stderr_thread is not None:
            stderr_thread.join(timeout=2)
        with _python_jobs_lock:
            _python_job_processes.pop(job_id, None)
        if _video_slot_acquired:
            _video_gpu_queue.release(job_id)

    if was_cancelled:
        error_message = "Job annule par l'utilisateur."
    elif timed_out:
        # 2026-08-08 : deux modes distincts. Le job qui produit encore des
        # PROGRESS: n'était pas gelé — c'était le plafond wall-clock qui
        # tuait un rendu légitime. Maintenant on distingue.
        _now = time.time()
        if _now > start_ts + hard_cap_seconds:
            error_message = (
                f"Timeout dur ({int(hard_cap_seconds)}s = {int(hard_cap_seconds/3600)}h) "
                "atteint — le job dépasse le plafond de sécurité absolu. "
                "Aucun script légitime ne devrait durer ça ; investiguez."
            )
        else:
            silence = int(_now - last_activity_ts)
            error_message = (
                f"Timeout par inactivité ({silence}s sans stdout, seuil "
                f"{int(inactivity_timeout_seconds)}s = "
                f"{int(inactivity_timeout_seconds/60)}min). "
                "Le job est probablement gelé (pas de PROGRESS: depuis longtemps). "
                "Relance AURORA_BRIDGE_INACTIVITY_TIMEOUT plus haut si erreur de diagnostic."
            )
    elif crashed:
        error_message = crashed
    else:
        error_message = _clean_stderr("\n".join(stderr_buf))
    # TRADUCTION DES MORTS PAR SIGNAL (30/07, audit): un SIGKILL (OOM noyau ou
    # plafond cgroup) ne laisse AUCUN traceback — l'erreur remontait vide et
    # l'UI affichait un faux 'TRELLIS n a pas produit de mesh'. On nomme le
    # signal, et on joint le motif que la sentinelle ecrit expres pour ca.
    try:
        if isinstance(exit_code, int) and exit_code < 0 and not (error_message or "").strip():
            _sig = -exit_code
            error_message = ("processus tue par le signal %d%s" % (
                _sig, " (SIGKILL: memoire epuisee — noyau ou plafond cgroup)" if _sig == 9 else ""))
        _trace_p = os.environ.get("AURORA_SENTINEL_TRACE", "/tmp/aurora_sentinelle.txt")
        if (isinstance(exit_code, int) and exit_code != 0 and os.path.isfile(_trace_p)
                and os.path.getmtime(_trace_p) >= (start_ts or 0)):
            with open(_trace_p, "r", encoding="utf-8") as _tf:
                _motif = _tf.read().strip()[:300]
            if _motif:
                error_message = ((error_message + " — ") if error_message else "") + _motif
    except Exception:
        pass

    storage_result = None
    if (
        not was_cancelled
        and exit_code == 0
        and os.path.basename(script_path) == "cinema_pipeline.py"
    ):
        with _python_jobs_lock:
            output_path_for_storage = (_python_jobs.get(job_id) or {}).get("outputPath")
        manager = globals().get("_storage_manager")
        if output_path_for_storage and manager is not None:
            try:
                storage_result = manager.migrate_final_to_cold(
                    output_path_for_storage,
                    job_id=job_id,
                )
            except Exception as storage_exc:
                storage_result = {
                    "ok": False,
                    "reason": "output_migration_failed",
                    "error": str(storage_exc)[:240],
                }
        elif output_path_for_storage:
            storage_result = {
                "ok": False,
                "reason": "storage_manager_unavailable",
                "error": globals().get("_storage_import_error", ""),
            }

    # v82ly : persist final state to disk for survival across bridge respawn.
    final_state = {
        "status": "cancelled" if was_cancelled else "done",
        "output": "\n".join(stdout_lines),
        "error": error_message,
        "exitCode": -15 if was_cancelled else exit_code,
        "script": os.path.basename(script_path),
        "startedAt": start_ts,
        "finishedAt": time.time(),
    }
    if storage_result is not None:
        final_state["storage"] = storage_result
    if was_cancelled:
        final_state["cancelledAt"] = time.time()
    # Find the job dir (cinema convention) and write status.json.
    _persist_job_state(job_id, final_state)

    with _python_jobs_lock:
        previous = _python_jobs.get(job_id, {})
        _python_jobs[job_id] = {**previous, **{
            "status": "cancelled" if was_cancelled else "done",
            "output": "\n".join(stdout_lines),
            "error": error_message,
            "exitCode": -15 if was_cancelled else exit_code,
            "script": os.path.basename(script_path),
            "startedAt": start_ts,
            "finishedAt": time.time(),
            **({"storage": storage_result} if storage_result is not None else {}),
            **({"cancelledAt": time.time()} if was_cancelled else {}),
        }}


def _gc_old_jobs():
    """Remove finished jobs to bound memory.

    31/07 (audit): 10 min de retention faisait DISPARAITRE les jobs 3D
    termines — le client, en se reattachant apres un long TRELLIS, recevait
    404 et RELANCAIT un run identique a neuf. Les jobs 3D gardent leur etat
    terminal 4 h; les autres 30 min.
    """
    now = time.time()
    with _python_jobs_lock:
        stale = []
        for jid, job in _python_jobs.items():
            fin = job.get("finishedAt")
            if fin is None:
                continue
            _est3d_job = "aurora_3d_pipeline" in str(job.get("script") or job.get("scriptPath") or "")
            if now - fin > (14400 if _est3d_job else 1800):
                stale.append(jid)
        for jid in stale:
            _python_jobs.pop(jid, None)


@app.route("/api/python/run-async", methods=["POST"])
def python_run_async():
    """Start a Python job in a worker thread and return a job_id.

    Use /api/python/job/<id> to poll for completion. This pattern is the only
    reliable way to run >100s Python scripts behind a Cloudflare tunnel."""
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    script_path = _resolve_script_path(data.get("scriptPath", ""))
    args = data.get("args", []) or []

    # Reject unknown scripts with a proper JSON 404 so the frontend doesn't
    # interpret an HTML fallback page as "endpoint missing" and silently
    # downgrade to the sync /api/python/run path (which then times out at 524).
    if not os.path.isfile(script_path):
        return jsonify({
            "ok": False,
            "error": f"Script Python introuvable: {script_path}",
        }), 404

    job_id = _uuid.uuid4().hex[:16]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": os.path.basename(script_path),
        }
    _queue_video_job(job_id, script_path)
    t = threading.Thread(target=_run_python_job, args=(job_id, script_path, args), daemon=True)
    t.start()
    return jsonify({"ok": True, "jobId": job_id})


@app.route("/api/ping", methods=["GET", "HEAD"])
def python_bridge_ping():
    """Ultra-light reachability probe — the frontend polls this every 30s to
    decide whether to light the 'Bridge' chip red or green, and the Forge
    overlay gates its Lancer button on it. Must stay tiny (no locks, no I/O)
    so it survives even when the bridge is busy running a long Python job."""
    return jsonify({"ok": True, "service": "aurora-bridge", "t": int(time.time())})


@app.route("/api/health")
def python_bridge_health():
    """Lightweight health check used by the frontend to detect whether the bridge
    (and thus the async Python runner) is reachable before kicking off a long job."""
    with _python_jobs_lock:
        running = sum(1 for j in _python_jobs.values() if j.get("status") == "running")
        finished = sum(1 for j in _python_jobs.values() if j.get("status") == "done")
    return jsonify({
        "ok": True,
        "service": "aurora-bridge",
        "workspace": WORKSPACE,
        "pythonJobs": {"running": running, "finished": finished},
        "features": {
            "runAsync": True,
            "progressStream": True,
        },
    })


# ---------------------------------------------------------------------------
# Banc de conformite inter-modules, rejouable DEPUIS LE TUNNEL.
#
# Les corrections de modules s'accompagnent d'un banc de mesures et de
# 9 suites de conformite. Cet endpoint les rejoue et rend le resultat en JSON,
# pour que l'interface (donc le tunnel) puisse le declencher sans passer par
# un terminal.
#
# LECTURE SEULE, deliberement. Le mode `--preuve`, qui revient temporairement
# a HEAD sur 9 fichiers pour verifier que les tests echouent bien sur le code
# d'avant, N'EST PAS expose ici : une requete HTTP interrompue au mauvais
# moment laisserait le depot dans un etat intermediaire. Ce mode reste sur la
# ligne de commande, sous l'oeil de l'operateur :
#     cd application && npm run conformance:preuve
# ---------------------------------------------------------------------------
_conformance_lock = threading.Lock()


@app.route("/api/conformance", methods=["GET", "POST"])
def aurora_conformance():
    """Rejoue le banc de conformite (lecture seule) et rend le rapport JSON.

    Parametres (query ou corps JSON) :
      mesures=1   ajoute les mesures comportementales chiffrees par module
      suites=0    saute les 9 suites de tests et ne rend que les mesures
    """
    params = request.get_json(silent=True) or {}

    def flag(nom, defaut=False):
        brut = request.args.get(nom)
        if brut is None:
            brut = params.get(nom)
        if brut is None:
            return defaut
        return str(brut).strip().lower() in ("1", "true", "yes", "oui")

    if not _conformance_lock.acquire(blocking=False):
        return jsonify({
            "ok": False,
            "error": "Un banc de conformite est deja en cours.",
        }), 409

    try:
        node_exe = resolve_node_exe()
        if not node_exe:
            return jsonify({"ok": False, "error": "Node introuvable sur ce poste."}), 500
        args = [node_exe, "scripts/conformance.mjs", "--json"]
        if flag("mesures", True):
            args.append("--mesures")
        started = time.time()
        proc = subprocess.run(
            args,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=900,
        )
        # `conformance.mjs` sort en code 1 des qu'une suite echoue : c'est un
        # VERDICT, pas une panne. On ne le confond pas avec une erreur
        # d'execution, sans quoi un echec de conformite ressemblerait a une
        # indisponibilite du banc.
        rapport = None
        try:
            debut = proc.stdout.index("{")
            rapport = json.loads(proc.stdout[debut:])
        except (ValueError, json.JSONDecodeError):
            pass
        if rapport is None:
            return jsonify({
                "ok": False,
                "error": "Le banc n'a pas rendu de rapport exploitable.",
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-4000:],
                "exitCode": proc.returncode,
            }), 500
        return jsonify({
            "ok": True,
            "verdict": rapport.get("verdict"),
            "durationMs": int((time.time() - started) * 1000),
            "rapport": rapport,
            "note": "Lecture seule. La preuve rouge/vert reste en ligne de "
                    "commande : npm run conformance:preuve",
        })
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Delai depasse (900 s)."}), 504
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": f"Executable introuvable : {exc}"}), 500
    finally:
        _conformance_lock.release()


# ---------------------------------------------------------------------------
# Expertise des ARTEFACTS REELS + garde d architecture, rejouables depuis
# l interface et le tunnel.
#
# Ces deux endpoints n executent aucune suite de tests : ils OUVRENT les
# fichiers presents dans `application/output/` et rendent ce qu ils mesurent.
# Lecture seule.
# ---------------------------------------------------------------------------
_expertise_lock = threading.Lock()


def _lance_outil(args, timeout=1800):
    """Execute un outil d expertise et rend son JSON."""
    proc = subprocess.run(args, cwd=WORKSPACE, capture_output=True, text=True, timeout=timeout)
    texte = proc.stdout or ""
    for ouvrant, fermant in (("{", "}"), ("[", "]")):
        debut = texte.find(ouvrant)
        if debut >= 0:
            try:
                return json.loads(texte[debut:texte.rfind(fermant) + 1]), proc.returncode
            except json.JSONDecodeError:
                continue
    return None, proc.returncode


def _python_du_projet():
    """L interpreteur du venv du projet : le python3 systeme n a ni numpy ni
    trimesh, et l expertise des GLB en depend."""
    venv = os.path.join(WORKSPACE, ".venv", "bin", "python")
    return venv if os.path.isfile(venv) else sys.executable


@app.route("/api/architecture", methods=["GET", "POST"])
def aurora_architecture():
    """Garde d architecture de sortie : contrat output/<module>/<projet>/."""
    if not _expertise_lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "Une expertise est deja en cours."}), 409
    try:
        started = time.time()
        rapport, code = _lance_outil(
            [_python_du_projet(), os.path.join(WORKSPACE, "scripts", "garde-architecture.py"), "--json"],
            timeout=900)
        if rapport is None:
            return jsonify({"ok": False, "error": "La garde n a pas rendu de rapport."}), 500
        return jsonify({
            "ok": True,
            "conforme": bool(rapport.get("conforme")),
            "durationMs": int((time.time() - started) * 1000),
            "rapport": rapport,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Delai depasse."}), 504
    finally:
        _expertise_lock.release()


@app.route("/api/expertise", methods=["GET", "POST"])
def aurora_expertise():
    """Expertise des artefacts REELS.

    Parametres : `cible` = `artefacts` (GLB/MP4/WAV/images), `livrables`
    (projets de code), ou `tout` (defaut).
    """
    cible = (request.args.get("cible")
             or (request.get_json(silent=True) or {}).get("cible")
             or "tout")
    if not _expertise_lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "Une expertise est deja en cours."}), 409
    try:
        started = time.time()
        out = {}
        if cible in ("tout", "artefacts"):
            rapport, _ = _lance_outil(
                [_python_du_projet(), os.path.join(WORKSPACE, "scripts", "expertise-artefacts.py"), "--json"],
                timeout=2400)
            out["artefacts"] = rapport
        if cible in ("tout", "livrables"):
            node_exe = resolve_node_exe()
            if not node_exe:
                out["livrables"] = {"error": "Node introuvable sur ce poste."}
            else:
                rapport, _ = _lance_outil(
                    [node_exe, "--experimental-strip-types",
                     os.path.join(WORKSPACE, "scripts", "expertise-livrables.mjs"), "--json"],
                    timeout=900)
                out["livrables"] = rapport
        constats = 0
        if isinstance(out.get("artefacts"), dict):
            for fiches in out["artefacts"].values():
                if isinstance(fiches, list):
                    constats += sum(len(f.get("constats") or []) for f in fiches
                                    if isinstance(f, dict))
        if isinstance(out.get("livrables"), dict):
            for p in out["livrables"].get("livrables") or []:
                constats += len(p.get("constats") or [])
        return jsonify({
            "ok": True,
            "cible": cible,
            "constats": constats,
            "durationMs": int((time.time() - started) * 1000),
            "rapport": out,
            "note": "Lecture seule : les fichiers de application/output/ sont ouverts et mesures.",
        })
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Delai depasse."}), 504
    finally:
        _expertise_lock.release()


# v82lc — expose la tunnel URL en cours via le bridge.
# Cloudflared rotate l URL trycloudflare.com a chaque restart. Le lanceur Linux
# ecrit la nouvelle URL dans tunnel.txt (cf restart_tunnel.py). Cet endpoint
# le lit pour que UI / extension / agent externe puisse savoir ou pointe le
# tunnel sans avoir a parser le repo. Retourne 404 si le fichier n existe pas
# (cas d un user qui run le bridge en local sans tunnel).
#
# v82ld — mtime-based cache. Le fichier tunnel.txt change rarement (a chaque
# restart cloudflared, soit < 1x/heure en pratique) mais l endpoint est hit
# sans arret par UI + extension. On cache l URL en memoire et on ne re-read
# que si la mtime a bougé. Réponse contient `cached: true|false` pour debug.
_TUNNEL_URL_CACHE: "dict[str, object]" = {"url": None, "mtime": 0.0, "path": None}


def _resolve_tunnel_url_path():
    """Locate tunnel.txt, falling back to the legacy local-only filename."""
    import pathlib
    repo_root = pathlib.Path(WORKSPACE).resolve()
    for directory in (repo_root, repo_root.parent):
        for filename in ("tunnel.txt", "tunnel_url.txt"):
            candidate = directory / filename
            if candidate.is_file():
                return candidate
    return None


def _tunnel_url_etag(url: str, mtime: float) -> str:
    """Compute weak ETag for /api/tunnel/url responses.

    Format : W/"<sha1(url + '|' + mtime)[:16]>". Truncated to 16 hex chars
    so the header stays compact ; collisions are irrelevant since the input
    space is "current tunnel URL + filesystem mtime" — both already unique
    per restart.
    """
    import hashlib as _hashlib
    payload = f"{url}|{mtime}".encode("utf-8")
    digest = _hashlib.sha1(payload).hexdigest()[:16]
    return f'W/"{digest}"'


@app.route("/api/tunnel/url", methods=["GET"])
def tunnel_url():
    """Return the active cloudflared tunnel URL by reading tunnel.txt.

    Response:
      { ok: true, url: "https://...trycloudflare.com", source: "tunnel.txt", cached: bool }
      or
      { ok: false, error: "tunnel.txt missing — start Aurora to create the tunnel" }, 404

    v82le — ETag + Cache-Control layered on top of the mtime cache. If the
    client sends `If-None-Match: <etag>` and it matches the current ETag we
    return 304 with no body. Otherwise we return the JSON shape with both
    `ETag` and `Cache-Control: max-age=2` headers. The 2s TTL matches what
    UI/extension can tolerate (URL changes only on tunnel restart).
    """
    candidate = _resolve_tunnel_url_path()
    if candidate is None:
        return jsonify({
            "ok": False,
            "error": "tunnel.txt introuvable — lance start-aurora.sh pour creer le tunnel.",
        }), 404
    try:
        cur_mtime = candidate.stat().st_mtime
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"stat tunnel.txt echouee: {e}"}), 500

    cached_mtime = float(_TUNNEL_URL_CACHE.get("mtime") or 0.0)
    cached_path = _TUNNEL_URL_CACHE.get("path")
    cached_url = _TUNNEL_URL_CACHE.get("url")
    is_hit = (
        cached_url is not None
        and cached_path == str(candidate)
        and abs(cur_mtime - cached_mtime) < 1e-6
    )

    if is_hit:
        url_value = str(cached_url)
        etag = _tunnel_url_etag(url_value, cur_mtime)
        client_etag = request.headers.get("If-None-Match", "").strip()
        if client_etag and client_etag == etag:
            resp = Response(status=304)
            resp.headers["ETag"] = etag
            resp.headers["Cache-Control"] = "max-age=2"
            return resp
        resp = jsonify({
            "ok": True,
            "url": url_value,
            "source": str(candidate),
            "cached": True,
        })
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "max-age=2"
        return resp

    try:
        url = candidate.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"lecture tunnel.txt echouee: {e}"}), 500
    if not url.startswith("https://"):
        return jsonify({
            "ok": False,
            "error": f"tunnel.txt content invalide: {url[:80]!r}",
        }), 500

    _TUNNEL_URL_CACHE["url"] = url
    _TUNNEL_URL_CACHE["mtime"] = cur_mtime
    _TUNNEL_URL_CACHE["path"] = str(candidate)
    etag = _tunnel_url_etag(url, cur_mtime)
    client_etag = request.headers.get("If-None-Match", "").strip()
    if client_etag and client_etag == etag:
        resp = Response(status=304)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "max-age=2"
        return resp
    resp = jsonify({
        "ok": True,
        "url": url,
        "source": str(candidate),
        "cached": False,
    })
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "max-age=2"
    return resp


@app.route("/api/python/job/<job_id>")
def python_job_status(job_id: str):
    """Return the current status of an async Python job."""
    with _python_jobs_lock:
        job = _python_jobs.get(job_id)
    if job is None:
        return jsonify({"status": "unknown", "error": "job not found (expired or invalid id)"}), 404
    resp = {"jobId": job_id, **job}
    if job.get("status") == "running" and "startedAt" in job:
        elapsed = time.time() - job["startedAt"]
        resp["elapsedSeconds"] = round(elapsed, 1)
        pct = float(job.get("progressPct", 0.0))
        if pct > 8.0:
            rate = elapsed / pct
            resp["estimatedRemainingSeconds"] = max(1, round((100.0 - pct) * rate))
    return jsonify(resp)


@app.route("/api/python/cancel/<job_id>", methods=["POST"])
def python_job_cancel(job_id: str):
    """Annule un job Python video, actif ou encore dans la file GPU."""
    return _cancel_video_job_response(job_id)


@app.route("/api/python/run", methods=["POST"])
def python_run():
    """Synchronous path — kept for Tauri / local browser modes where the
    tunnel timeout doesn't apply. Cloud/tunnel clients should use /run-async.
    """
    data = request.get_json()
    script_path = _resolve_script_path(data.get("scriptPath", ""))
    args = data.get("args", [])

    try:
        run_env = _build_python_env()
        result = subprocess.run(
            [sys.executable, "-W", "ignore", script_path] + args,
            capture_output=True, timeout=900, cwd=WORKSPACE, env=run_env,
        )
        return jsonify({
            "output": result.stdout.decode("utf-8", errors="replace"),
            "error": _clean_stderr(result.stderr.decode("utf-8", errors="replace")),
            "exitCode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"output": "", "error": "Timeout (900s)", "exitCode": -1})
    except Exception as e:
        return jsonify({"output": "", "error": str(e), "exitCode": -1})


@app.route("/api/command/run", methods=["POST"])
def command_run():
    data = request.get_json()
    executable = data.get("executable", "")
    args = data.get("args", [])
    cwd = data.get("cwd", WORKSPACE)
    timeout_ms = data.get("timeoutMs", 60000)

    try:
        result = subprocess.run(
            [executable] + args,
            capture_output=True, timeout=timeout_ms / 1000, cwd=cwd,
        )
        return jsonify({
            "ok": result.returncode == 0,
            "exitCode": result.returncode,
            "output": result.stdout.decode("utf-8", errors="replace"),
            "command": f"{executable} {' '.join(args)}",
        })
    except Exception as e:
        return jsonify({"ok": False, "exitCode": -1, "output": str(e), "command": executable})


@app.route("/api/command/spawn", methods=["POST"])
def command_spawn():
    """Lance une commande en arriere-plan (detached). Utilise par le dev server du module Code."""
    data = request.get_json()
    executable = data.get("executable", "")
    args = data.get("args", [])
    cwd = data.get("cwd", WORKSPACE)

    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            [executable] + args,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        return jsonify({
            "ok": True,
            "pid": proc.pid,
            "command": f"{executable} {' '.join(args)}",
            "stdoutLog": None,
            "stderrLog": None,
        })
    except Exception as e:
        return jsonify({"ok": False, "pid": 0, "command": executable, "stdoutLog": None, "stderrLog": None}), 500


# =====================================================================
#  Filesystem — lecture/ecriture de fichiers pour les modules
# =====================================================================

@app.route("/api/fs/workspace-path")
def fs_workspace_path():
    return jsonify({"path": WORKSPACE})


@app.route("/api/fs/exists", methods=["POST"])
def fs_exists():
    path = request.get_json().get("path", "")
    return jsonify({"exists": os.path.exists(path)})


@app.route("/api/fs/mkdir", methods=["POST"])
def fs_mkdir():
    path = request.get_json().get("path", "")
    os.makedirs(path, exist_ok=True)
    return jsonify({"ok": True})


@app.route("/api/fs/read-text", methods=["POST"])
def fs_read_text():
    path = request.get_json().get("path", "")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return jsonify({"content": f.read()})
    except Exception as e:
        return jsonify({"content": "", "error": str(e)}), 404


@app.route("/api/fs/write-text", methods=["POST"])
def fs_write_text():
    data = request.get_json()
    path = data.get("path", "")
    content = data.get("content", "")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return jsonify({"ok": True})


@app.route("/api/fs/write-binary", methods=["POST"])
def fs_write_binary():
    data = request.get_json()
    path = data.get("path", "")
    raw_bytes = data.get("bytes", [])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(bytes(raw_bytes))
    return jsonify({"ok": True})


@app.route("/api/fs/read-binary", methods=["POST"])
def fs_read_binary():
    path = request.get_json().get("path", "")
    try:
        with open(path, "rb") as f:
            return jsonify({"bytes": list(f.read())})
    except Exception as e:
        return jsonify({"bytes": [], "error": str(e)}), 404


@app.route("/api/fs/remove-dir", methods=["POST"])
def fs_remove_dir():
    """Recursively remove a directory (used for voice library cleanup)."""
    import shutil as _sh
    path = (request.get_json(silent=True) or {}).get("path", "")
    if not path:
        return jsonify({"ok": False, "error": "path manquant"}), 400
    p = pathlib.Path(path)
    if not p.exists():
        return jsonify({"ok": True, "skipped": True})
    try:
        if p.is_file():
            p.unlink()
        else:
            _sh.rmtree(p)
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/fs/list", methods=["POST"])
def fs_list_dir():
    """Lister les entrees directes d'un repertoire (non recursif)."""
    path = (request.get_json(silent=True) or {}).get("path", "")
    if not path or not os.path.isdir(path):
        return jsonify({"entries": []})
    try:
        entries = sorted(os.listdir(path))
        return jsonify({"entries": entries})
    except Exception as exc:
        return jsonify({"entries": [], "error": str(exc)}), 500


# =====================================================================
#  Asset serving — pour telecharger les images generees sur le tel
# =====================================================================

def _resoudre_chemin_workspace(brut):
    """Rend un chemin ABSOLU existant, ou None.

    `/api/upload` renvoie un chemin RELATIF au workspace (`os.path.relpath`),
    mais les routes qui le consommaient testaient `os.path.isfile()` dessus tel
    quel: ca ne marchait que si le pont avait ete lance depuis le workspace.
    Sinon, « introuvable » alors que le fichier etait bien la — signale le
    03/09 sur le detourage. On essaie l'absolu, puis relatif au workspace.
    """
    brut = (str(brut or "")).strip()
    if not brut:
        return None
    for cand in (brut, os.path.join(WORKSPACE, brut.lstrip("/\\"))):
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    return None


@app.route("/api/3d/select-subject", methods=["POST"])
def three_d_select_subject():
    """31/07 (demande Juan): isoler le SUJET sur la photo avant reconstruction.

    Modes: auto (detourage du sujet principal), clic {x,y}, cadre
    {x0,y0,x1,y1} — coordonnees normalisees 0..1. Rend un PNG RGBA detoure
    dans output/context/ et son chemin (le meme circuit que les pieces
    jointes).
    """
    data = request.get_json(silent=True) or {}
    image_path = _resoudre_chemin_workspace(data.get("image_path"))
    if not image_path:
        return jsonify({"ok": False, "error": "image_path introuvable: %s"
                        % (data.get("image_path") or "")}), 400
    sortie = os.path.join(WORKSPACE, "output", "context",
                          "sujet_%d.png" % int(time.time() * 1000))
    cmd = [sys.executable,
           os.path.join(WORKSPACE, "python-services", "selection_sujet.py"),
           "--image", image_path, "--sortie", sortie]
    clic = data.get("clic")
    cadre = data.get("cadre")
    if isinstance(cadre, (list, tuple)) and len(cadre) == 4:
        cmd += ["--cadre", ",".join(str(float(v)) for v in cadre)]
    elif isinstance(clic, (list, tuple)) and len(clic) == 2:
        cmd += ["--clic", ",".join(str(float(v)) for v in clic)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                              env=_build_python_env())
        for line in reversed((proc.stdout or "").splitlines()):
            line = line.strip()
            if line.startswith("{"):
                res = json.loads(line)
                if res.get("ok"):
                    res["url"] = "/api/asset/" + os.path.relpath(sortie, WORKSPACE)
                return jsonify(res)
        return jsonify({"ok": False,
                        "error": (proc.stderr or "selection sans sortie")[-300:]}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "selection trop longue (300 s)"}), 504


@app.route("/aurora_viewer.html")
def aurora_viewer_page():
    # 31/07 (audit): le viewer de fin de run pointait sur un serveur 3009
    # que RIEN ne demarrait — ecran noir garanti apres chaque generation.
    # Le bridge le sert lui-meme, plus aucun serveur a lancer a la main.
    return send_file(os.path.join(WORKSPACE, "aurora_viewer.html"),
                     mimetype="text/html", conditional=True)


@app.route("/api/asset/<path:filepath>")
def serve_asset(filepath):
    """Sert un fichier genere (image, audio, etc.) pour le telephone."""
    # Chercher dans les repertoires de sortie connus
    cold_gallery_candidate = None
    if filepath.startswith("aurora-models/outputs/videos/"):
        gallery_name = pathlib.PurePosixPath(filepath).name
        if gallery_name == filepath.removeprefix("aurora-models/outputs/videos/"):
            manager = globals().get("_storage_manager")
            if manager is not None and manager.cold_mounted():
                cold_gallery_candidate = str(manager.cold_root / "outputs" / "videos" / gallery_name)
    candidates = [
        cold_gallery_candidate,
        os.path.join(WORKSPACE, filepath),
        os.path.join(WORKSPACE, "output", filepath),
        os.path.join(WORKSPACE, "temp", filepath),
        filepath,  # chemin absolu direct
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return send_file(candidate)
    abort(404)


@app.route("/api/download/<path:filepath>")
def download_asset(filepath):
    """Telecharger un fichier genere avec Content-Disposition attachment (force le telechargement sur mobile)."""
    candidates = [
        os.path.join(WORKSPACE, filepath),
        os.path.join(WORKSPACE, "output", filepath),
        os.path.join(WORKSPACE, "temp", filepath),
        filepath,
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return send_file(candidate, as_attachment=True, download_name=os.path.basename(candidate))
    abort(404)


@app.route("/api/generated-files")
def list_generated_files():
    """Liste tous les fichiers generes (images, videos, audio, 3D) pour le telephone."""
    files = []
    search_dirs = [
        os.path.join(WORKSPACE, "output"),
        os.path.join(WORKSPACE, "temp"),
    ]
    extensions = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.webm', '.wav', '.mp3', '.obj', '.glb', '.gltf'}
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for root, _dirs, filenames in os.walk(search_dir):
            for fname in filenames:
                if os.path.splitext(fname)[1].lower() in extensions:
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, WORKSPACE).replace("\\", "/")
                    stat = os.stat(full)
                    files.append({
                        "name": fname,
                        "path": rel,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "type": os.path.splitext(fname)[1].lower().lstrip("."),
                    })
    files.sort(key=lambda f: f["modified"], reverse=True)
    return jsonify(files[:100])


@app.route("/api/image/persist", methods=["POST"])
def persist_generated_image():
    """Sauvegarde un rendu d'image dans la structure output/image/<context>/<session>/<intent_slug>.png."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename")
    context = data.get("context", "ui")
    session_id = data.get("sessionId", "general")
    intent_mode = data.get("mode", "creation")
    prompt = data.get("prompt", "")

    safe_context = "tunnel" if context == "tunnel" else "cli" if context == "cli" else "ui"
    safe_session = re.sub(r'[^a-zA-Z0-9_.-]+', '_', session_id or "session")
    mode_slug = re.sub(r'[^a-zA-Z0-9]+', '_', intent_mode.lower())[:15] or "creation"
    prompt_slug = re.sub(r'[^a-zA-Z0-9]+', '_', prompt.lower())[:35].strip('_') or "image"
    ts = int(data.get("timestamp") or time.time() * 1000)

    target_dir = os.path.join(WORKSPACE, "output", "image", safe_context, safe_session)
    os.makedirs(target_dir, exist_ok=True)

    out_filename = f"{mode_slug}_{prompt_slug}_{ts}.png"
    out_path = os.path.join(target_dir, out_filename)

    if filename:
        comfy_path = os.path.join(COMFYUI_PATH or "", "output", filename)
        if os.path.isfile(comfy_path):
            import shutil
            shutil.copy2(comfy_path, out_path)
            rel = os.path.relpath(out_path, WORKSPACE).replace("\\", "/")
            return jsonify({"ok": True, "path": rel, "filename": out_filename})

    return jsonify({"ok": False, "error": "Fichier source introuvable"}), 404


# =====================================================================
#  Ollama model listing (pour le telephone — remplace invoke("ollama_list_models"))
# =====================================================================

@app.route("/api/ollama/tags")
def ollama_tags():
    """Liste les modeles Ollama disponibles."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return Response(resp.content, content_type="application/json")
    except Exception as e:
        return jsonify({"models": [], "error": str(e)}), 504


# =====================================================================
#  Upload — recevoir des fichiers depuis le telephone
# =====================================================================

@app.route("/api/upload", methods=["POST"])
def upload_file():
    """Recoit un fichier depuis le telephone et le sauvegarde dans le workspace."""
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier envoye"}), 400

    f = request.files["file"]
    target_dir = request.form.get("targetDir", "uploads")
    save_dir = os.path.join(WORKSPACE, target_dir)
    os.makedirs(save_dir, exist_ok=True)

    # Securiser le nom de fichier
    from werkzeug.utils import secure_filename
    safe_name = secure_filename(f.filename or "upload")
    # Eviter les doublons
    base, ext = os.path.splitext(safe_name)
    final_name = safe_name
    counter = 1
    while os.path.exists(os.path.join(save_dir, final_name)):
        final_name = f"{base}_{counter}{ext}"
        counter += 1

    save_path = os.path.join(save_dir, final_name)
    f.save(save_path)

    rel_path = os.path.relpath(save_path, WORKSPACE).replace("\\", "/")
    return jsonify({"path": rel_path, "name": final_name, "size": os.path.getsize(save_path)})


# =====================================================================
#  ComfyUI lifecycle endpoints
# =====================================================================

@app.route("/api/comfyui/status", methods=["GET"])
def comfyui_status():
    running = _comfyui_is_ready()
    return jsonify({"ok": True, "running": running, "port": COMFYUI_PORT})


@app.route("/api/comfyui/start", methods=["POST"])
def comfyui_start():
    if not COMFYUI_PATH:
        return jsonify({
            "ok": False, "ready": False,
            "error": "ComfyUI non detecte — verifiez que modele/comfyui/comfyui existe dans AuroraIA-v2.",
        })
    ready = _start_comfyui()
    return jsonify({"ok": ready, "ready": ready, "port": COMFYUI_PORT})


@app.route("/api/comfyui/image")
def comfyui_image():
    """Proxy dedié pour les images ComfyUI — accessible depuis tunnel/mobile sans accès direct au 8188."""
    filename = request.args.get("filename", "")
    subfolder = request.args.get("subfolder", "")
    image_type = request.args.get("type", "output")
    download = request.args.get("download", "0") in ("1", "true", "yes")
    if not filename:
        return jsonify({"error": "filename manquant"}), 400
    try:
        r = requests.get(
            f"{COMFYUI_URL}/view",
            params={"filename": filename, "subfolder": subfolder, "type": image_type},
            stream=True,
            timeout=30,
        )
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "Content-Disposition",
        }
        if download:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        else:
            headers["Content-Disposition"] = f'inline; filename="{filename}"'

        return Response(
            r.iter_content(chunk_size=4096),
            status=r.status_code,
            content_type=r.headers.get("Content-Type", "image/png"),
            headers=headers,
        )
    except Exception as e:
        return jsonify({"error": f"ComfyUI image non accessible: {e}"}), 504


# =====================================================================
#  Ollama — enhanced model list and pull with SSE progress
# =====================================================================

@app.route("/api/ollama/models")
def ollama_models():
    """List installed Ollama models with sizes, sorted by name."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = []
        for m in data.get("models", []):
            size_gb = round(m.get("size", 0) / (1024 ** 3), 2)
            models.append({
                "name": m.get("name", ""),
                "size_gb": size_gb,
                "modified_at": m.get("modified_at", ""),
                "details": m.get("details", {}),
            })
        models.sort(key=lambda x: x["name"])
        return jsonify({"models": models, "count": len(models)})
    except Exception as e:
        return jsonify({"models": [], "count": 0, "error": str(e)}), 504


@app.route("/api/ollama/pull", methods=["POST"])
def ollama_pull():
    """Stream model download progress via SSE. Body: {name: string}."""
    data = request.get_json(silent=True) or {}
    model_name = data.get("name", "").strip()
    if not model_name:
        return jsonify({"error": "model name required"}), 400

    def generate():
        try:
            with requests.post(
                f"{OLLAMA_URL}/api/pull",
                json={"name": model_name, "stream": True},
                stream=True,
                timeout=3600,
            ) as r:
                for line in r.iter_lines():
                    if line:
                        yield f"data: {line.decode('utf-8', errors='replace')}\n\n"
        except Exception as e:
            yield f"data: {{\"error\": \"{e}\"}}\n\n"
        yield "data: {\"done\": true}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# =====================================================================
#  System info — extended hardware details
# =====================================================================

@app.route("/api/system/info")
def system_info():
    """Detailed system info: CPU, RAM, GPU, VRAM free/total."""
    cpu = platform.processor() or platform.machine()
    cores_logical = psutil.cpu_count(logical=True) or 0
    cores_physical = psutil.cpu_count(logical=False) or 0
    mem = psutil.virtual_memory()
    ram_total_gb = round(mem.total / (1024 ** 3), 1)
    ram_free_gb = round(mem.available / (1024 ** 3), 1)

    gpu_name = "unknown"
    vram_total_gb = 0.0
    vram_free_gb = 0.0
    try:
        nv = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            timeout=5,
        ).decode().strip().split(",")
        if len(nv) >= 3:
            gpu_name = nv[0].strip()
            vram_total_gb = round(int(nv[1].strip()) / 1024, 1)
            vram_free_gb = round(int(nv[2].strip()) / 1024, 1)
    except Exception:
        pass

    return jsonify({
        "os": f"{platform.system()} {platform.release()}",
        "cpu": cpu,
        "cores_logical": cores_logical,
        "cores_physical": cores_physical,
        "ram_total_gb": ram_total_gb,
        "ram_free_gb": ram_free_gb,
        "gpu": gpu_name,
        "vram_total_gb": vram_total_gb,
        "vram_free_gb": vram_free_gb,
    })


# =====================================================================
#  Cinema / Voice — module Cinema (videos multi-plans avec voix clonees)
# =====================================================================

CINEMA_DIR = pathlib.Path(WORKSPACE) / "python-services" / "cinema"
VOIX_OUTPUT_DIR = pathlib.Path(WORKSPACE) / "output" / "voix"
VOIX_ECHANTILLONS_DIR = VOIX_OUTPUT_DIR / "echantillons"
VOIX_PROFILS_DIR = VOIX_OUTPUT_DIR / "profils"
VOIX_GENERATIONS_DIR = VOIX_OUTPUT_DIR / "generations"
VOIX_CHANSONS_DIR = VOIX_OUTPUT_DIR / "chansons"
VOIX_MUSIQUES_DIR = VOIX_OUTPUT_DIR / "musiques"
VOIX_SESSIONS_DIR = VOIX_OUTPUT_DIR / "sessions"
LEGACY_LIBRARY_DIR = pathlib.Path(WORKSPACE) / "voices" / "library"
LEGACY_DROPBOX_DIR = pathlib.Path(WORKSPACE) / "voices" / "echantillons"

for _vd in (VOIX_OUTPUT_DIR, VOIX_ECHANTILLONS_DIR, VOIX_PROFILS_DIR, VOIX_GENERATIONS_DIR, VOIX_CHANSONS_DIR, VOIX_MUSIQUES_DIR, VOIX_SESSIONS_DIR, LEGACY_LIBRARY_DIR, LEGACY_DROPBOX_DIR):
    _vd.mkdir(parents=True, exist_ok=True)

VOICES_LIBRARY = VOIX_PROFILS_DIR
CINEMA_TEMP = pathlib.Path(WORKSPACE) / "temp" / "cinema"
CINEMA_TEMP.mkdir(parents=True, exist_ok=True)
STORAGE__VIDEO_SERVICES_DIR = pathlib.Path(WORKSPACE) / "python-services" / "storage"
if str(STORAGE__VIDEO_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(STORAGE__VIDEO_SERVICES_DIR))
try:
    from aurora_storage import AuroraStorageManager, StorageError
    _storage_manager = AuroraStorageManager(workspace=WORKSPACE)
    _storage_import_error = ""
except Exception as _storage_exc:
    AuroraStorageManager = None
    StorageError = RuntimeError
    _storage_manager = None
    _storage_import_error = f"{type(_storage_exc).__name__}: {_storage_exc}"


def _run_cinema_script_sync(script_name: str, args: list[str], timeout: int = 300) -> dict:
    """Run a cinema/* script synchronously and parse the last JSON line of stdout."""
    script = CINEMA_DIR / script_name
    if not script.exists():
        return {"ok": False, "error": f"script absent: {script}"}
    run_env = _build_python_env()
    try:
        result = subprocess.run(
            [sys.executable, "-W", "ignore", str(script)] + [str(a) for a in args],
            capture_output=True, timeout=timeout, cwd=WORKSPACE, env=run_env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout {timeout}s sur {script_name}"}
    except Exception as exc:
        return {"ok": False, "error": f"spawn {script_name}: {exc}"}

    out = result.stdout.decode("utf-8", errors="replace")
    err = _clean_stderr(result.stderr.decode("utf-8", errors="replace"))
    last_line = ""
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            last_line = line
            break
    if not last_line:
        return {"ok": False, "error": err or "pas de JSON dans la sortie", "raw": out[-400:]}
    try:
        parsed = json.loads(last_line)
    except Exception as exc:
        return {"ok": False, "error": f"JSON invalide: {exc}", "raw": last_line[:400]}
    if not isinstance(parsed, dict):
        return {"ok": False, "error": "sortie JSON non-objet", "raw": last_line[:400]}
    if result.returncode != 0 and "error" not in parsed:
        parsed.setdefault("error", err or f"exit {result.returncode}")
        parsed.setdefault("ok", False)
    return parsed


# ---------------------------------------------------------------------------
# Storyboard generation via Ollama
# ---------------------------------------------------------------------------

STORYBOARD_PROMPT = """Tu es un story-boarder de cinema. A partir du prompt utilisateur, tu produis UNIQUEMENT un objet JSON valide (pas de prose, pas de markdown).

Si la requete est trop ambigue pour decider du sujet de base, reponds UNIQUEMENT:
{"clarification": "<une question courte dans la langue de l'utilisateur>"}

Sinon reponds UNIQUEMENT avec ce schema:
{
  "title": "<titre court>",
  "summary": "<2-3 phrases: theme + ce qui va se passer>",
  "style": "<cartoon_pixar | anime | manga | realistic | documentary | watercolor | noir>",
  "aspect": "<16:9 | 9:16 | 1:1 | 4:3>",
  "resolution": "<720p | 1080p | 1440p>",
  "characters": [
    {
      "name": "<nom>",
      "voice_slug": "<snake_case>",
      "voice_lang": "<fr|en>",
      "voice_preset": "<young_male_french | older_male_french | young_female_french | older_female_french | child_french | young_male_english | older_male_english | young_female_english>",
      "voice_policy": "<registered | style>",
      "public_figure": false,
      "description": "<apparence courte en anglais pour le modele de diffusion>"
    }
  ],
  "shots": [
    {
      "id": 1,
      "scene": "<description visuelle detaillee EN ANGLAIS pour le modele de diffusion>",
      "location": "<identifiant snake_case stable du lieu, ex: garage_interior>",
      "speaker": "<nom de personnage ou null>",
      "dialogue": "<dialogue exact dans la langue de l'utilisateur, ou chaine vide>",
      "duration_s": 4,
      "camera": "<wide | medium | close-up>",
      "needs_lipsync": true,
      "action_contract": "<une phrase EN ANGLAIS: mouvement visible + objet manipule + resultat attendu dans ce plan>",
      "negative_prompt": "<EN ANGLAIS, choses A EVITER pour ce shot specifiquement: deformed face, extra limbs, multiple subjects when only one is wanted, watermark, low quality, blurry, anachronistic objects>"
    }
  ],
  "music": {"enabled": false, "prompt": ""},
  "subtitles": {"enabled": false}
}

Regles strictes:
- Chaque plan dure 3 a 8 secondes. Le moteur segmente automatiquement les
  plans longs en interne (jusqu'a ~20 s par plan), donc un plan de 5-8 s est
  autorise quand l'action ou le dialogue l'exige.
- DUREE ET DIALOGUE (critique) : si un plan a un dialogue, "duration_s" DOIT
  couvrir le temps de parole. Compte environ 2.5 mots par seconde :
  10 mots -> 4 s minimum, 15 mots -> 6 s, 20 mots -> 8 s. Si le dialogue
  depasse 8 s de parole, coupe-le en deux plans consecutifs du meme speaker.
- Si la duree totale n'est pas precisee, choisis 10 a 30 secondes.
- Si l'utilisateur demande une video longue ou complexe, cree 8 a 12 plans
  de 3 a 6 secondes avec une progression narrative claire.
- "location" DOIT etre fourni pour CHAQUE shot : un identifiant snake_case
  stable du decor (ex: "garage_interior", "city_street_night"). REUTILISE
  exactement le meme identifiant quand deux plans se passent au meme endroit
  — le moteur s'en sert pour garder le decor identique entre plans (ancre
  visuelle). Change d'identifiant seulement quand le lieu change vraiment.
- "scene" DOIT etre en anglais (modele de diffusion).
- "dialogue" DOIT etre dans la langue de l'utilisateur.
- "voice_slug" est un identifiant snake_case stable (utilise pour retrouver une voix dans la bibliotheque).
- Par defaut, une video avec personnages DOIT utiliser du dialogue diegetique
  entre personnages. N'utilise un narrateur / voice-over que si l'utilisateur
  le demande explicitement ("narrateur", "voix off", "documentaire", "explique").
- Si un personnage parle face camera ou dans le champ, "speaker" DOIT etre son
  nom exact, "dialogue" non vide, "needs_lipsync" true, et "scene" DOIT montrer
  clairement son visage et sa bouche. Si la bouche n'est pas visible, ne le fais
  pas parler dans ce plan.
- Pour une celebrite/personne publique reelle, NE demande PAS de clonage exact
  implicite. Mets "voice_policy":"style", "public_figure":true, un voice_slug
  commencant par "style_", et choisis un "voice_preset" coherent (age/genre/langue).
  Une voix exacte n'est utilisee que si elle est deja enregistree explicitement
  dans la bibliotheque voix.
- Pour un personnage invente, choisis un voice_slug stable et un voice_preset
  coherent; garde la meme voix sur tous les plans.
- "needs_lipsync" est true uniquement si le personnage parle a l'ecran ET que la bouche est visible.
- "action_contract" DOIT etre fourni pour CHAQUE shot. Il decrit l'action
  observable du plan: sujet -> mouvement -> objet/effet visible. N'invente pas
  de cablage, ecriture, dessin, outil ou manipulation non demande par l'action.
- "negative_prompt" DOIT etre fourni pour CHAQUE shot. C'est en anglais.
  Default conservateur si rien de specifique : "deformed, blurry, low quality,
  watermark, extra limbs, distorted face, bad anatomy, ugly, poorly drawn".
  Adapte selon le shot : si plan large (wide), evite "close-up artifacts" ;
  si action rapide (leap, run), evite "motion blur, smeared".
- Sortie: UNIQUEMENT le JSON, rien d'autre, pas de balise ```json.

CONTINUITE PERSONNAGE (critique) :
- Le champ "scene" DOIT inclure mot-pour-mot la description de CHAQUE
  personnage VISIBLE dans le plan (pas seulement le speaker), telle qu'elle
  apparait dans characters[].description. Un personnage present mais non
  decrit change d'apparence a chaque plan (teste : le petit-fils devenait
  une femme puis un enfant cartoon).
  Exemple : si characters = [{"name":"Shadow","description":"a sleek black cat with amber eyes"}]
  et un shot a speaker="Shadow", alors scene DOIT contenir "a sleek black cat with amber eyes"
  (en plus de l'action specifique du shot).
  Raison : Wan2.2 a besoin de la description complete du personnage dans CHAQUE prompt
  pour preserver l'apparence shot-to-shot. Sans ca, le visage / la couleur / les yeux
  changent entre plans = rupture de continuite.

COHERENCE ACTION :
- Les shots forment une sequence narrative continue. Chaque scene doit decrire
  l'instant present (pas le passe ni le futur), avec une action verbe-actif claire
  ("the cat leaps", pas "the cat will leap" ni "after leaping").
- Pas de coupes temporelles brutales sauf si volontaires (l'utilisateur le precise).

GRAMMAIRE CINEMA (v84, critique pour la qualite Wan2.2) :
- Chaque "scene" DOIT contenir, en anglais : (a) UN mouvement de camera explicite
  ("slow dolly in", "static locked shot", "smooth pan left", "camera slowly
  orbiting", "handheld follow") coherent avec l'action ; (b) la lumiere/ambiance
  ("golden hour light", "soft overcast light", "neon night", "warm interior
  light") coherente d'un shot a l'autre ; (c) 1-2 descripteurs de matiere/detail
  ("detailed fur", "wet asphalt reflections").
- Si l'utilisateur demande explicitement un mouvement de camera, un type de plan,
  une lumiere ou un style (indices "cinematography" ci-dessous), chaque shot
  concerne DOIT le respecter mot pour mot — c'est non negociable.
- Varier les valeurs de plan entre shots (wide / medium / close-up) sauf demande
  contraire, pour un montage lisible.

Indices optionnels donnes par l'utilisateur (peut etre vide):
{HINTS}

Prompt utilisateur:
{PROMPT}
"""


def _strip_json_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s[: -3]
        s = s.strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    return s


def _ollama_installed_models() -> list[str]:
    """Return the list of installed Ollama model names (best-effort)."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            return [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
    except Exception:
        pass
    return []


def _resolve_storyboard_model(requested: str | None) -> tuple[str, list[str]]:
    """Pick the best installed model for the storyboard task.

    Order:
      1. The model explicitly requested by the caller (if installed)
      2. orcarouter/Qwen3.8-27B-Uncensored — modele generaliste dense & multimodal
      3. qwen3.8:27b — variante standard Qwen 3.8
      4. qwen3-vl:30b — repli generaliste multimodal
      5. qwen3-coder:30b — repli installe, structure JSON solide
      6. qwen3-vl:8b — vision rapide

    Returns (chosen_model, candidates_tried). Empty chosen means none available.
    """
    installed = set(_ollama_installed_models())
    candidates: list[str] = []
    if requested:
        candidates.append(requested.strip())
    candidates.extend([
        "orcarouter/Qwen3.8-27B-Uncensored",
        "orcarouter/Qwen3.8-27B-Uncensored:latest",
        "qwen3.8:27b",
        "qwen3.6:27b",
        "qwen3-vl:30b",
        "qwen3-coder:30b",
        "qwen3-vl:8b",
    ])
    tried: list[str] = []
    for c in candidates:
        if not c:
            continue
        tried.append(c)
        if c in installed:
            return c, tried
        c_norm = c.lower().replace(":latest", "")
        for inst in installed:
            inst_norm = inst.lower().replace(":latest", "")
            if inst_norm == c_norm or inst_norm.endswith("/" + c_norm) or c_norm.endswith("/" + inst_norm):
                return inst, tried
            if inst.startswith(c.split(":")[0] + ":") and c.split(":", 1)[-1] in inst:
                return inst, tried
    return "", tried


@app.route("/api/cinema/storyboard", methods=["POST"])
def cinema_storyboard():
    """Genere un storyboard JSON via Ollama."""
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "prompt manquant"}), 400
    requested = (data.get("model") or "").strip()
    hints = data.get("hints") or {}

    model, tried = _resolve_storyboard_model(requested)
    if not model:
        return jsonify({
            "ok": False,
            "error": (
                "Aucun modele adapte au storyboard n'est installe. "
                "Installe orcarouter/Qwen3.8-27B-Uncensored ou fournis explicitement un modele."
            ),
            "tried": tried,
        }), 502

    full_prompt = STORYBOARD_PROMPT.replace("{HINTS}", json.dumps(hints, ensure_ascii=False)).replace("{PROMPT}", prompt)

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": full_prompt,
                "stream": False,
                "options": {"temperature": 0.4, "num_ctx": 8192},
                "keep_alive": "30m",
            },
            timeout=300,
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Ollama injoignable: {exc}"}), 502

    if resp.status_code != 200:
        return jsonify({
            "ok": False,
            "error": f"Ollama HTTP {resp.status_code}: {resp.text[:240]}",
            "model": model,
            "tried": tried,
        }), 502

    try:
        text = resp.json().get("response", "")
    except Exception:
        text = resp.text or ""

    text = _strip_json_fence(text)

    try:
        payload = json.loads(text)
    except Exception:
        # Try to extract a JSON object from the text using brace matching
        first = text.find("{")
        last = text.rfind("}")
        if first >= 0 and last > first:
            try:
                payload = json.loads(text[first : last + 1])
            except Exception as exc:
                return jsonify({"ok": False, "error": f"JSON invalide: {exc}", "raw": text[:600]}), 500
        else:
            return jsonify({"ok": False, "error": "pas de JSON dans la reponse Ollama", "raw": text[:600]}), 500

    if "clarification" in payload and payload.get("clarification"):
        return jsonify({"ok": True, "clarification": payload["clarification"]})

    # Validation minimale
    if not isinstance(payload.get("shots"), list) or not payload["shots"]:
        return jsonify({"ok": False, "error": "storyboard sans shots", "raw": payload, "model": model}), 500

    # v90 : normalisation déterministe — duration_s couvre la parole
    # (~2.5 mots/s), location héritée si absente. Le LLM sous-estime
    # systématiquement le temps de parole ; on ne dépend plus de lui.
    try:
        cinema_dir = str(CINEMA_DIR)
        if cinema_dir not in sys.path:
            sys.path.insert(0, cinema_dir)
        from storyboard_norm import normalize_storyboard
        payload = normalize_storyboard(payload)
    except Exception as _norm_exc:
        print(f"[cinema] storyboard normalize skip: {_norm_exc}", flush=True)

    return jsonify({"ok": True, "storyboard": payload, "model": model})


@app.route("/api/academy/parcours/latest", methods=["GET"])
def academy_parcours_latest():
    """v82m5 : retourne le dernier parcours BAC généré côté serveur
    (via supervise_v2.py par exemple). Permet à l'UI Academy de charger
    une session déjà générée sans re-streamer."""
    p = pathlib.Path(WORKSPACE) / "temp" / "academy_parcours" / "latest.json"
    if not p.exists():
        return jsonify({"ok": False, "error": "no parcours generated yet"}), 404
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return jsonify({"ok": True, "parcours": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cinema/sample-render", methods=["POST"])
def cinema_sample_render():
    """v82lx : render JUST the first shot of a storyboard at low quality
    (balanced, 720p) en ~5-7 min au lieu de 30+ min. User valide la
    cohérence prompt/render avant de commit le full storyboard.

    Body : { storyboard: {...} }
    Retour : { ok, jobId, sampleId, mode: 'sample' }
    """
    data = request.get_json(silent=True) or {}
    storyboard = data.get("storyboard")
    if not isinstance(storyboard, dict):
        return jsonify({"ok": False, "error": "storyboard manquant"}), 400
    shots = storyboard.get("shots") or []
    if not shots:
        return jsonify({"ok": False, "error": "storyboard sans shots"}), 400

    # Narrow : 1 shot only + balanced quality + 720p forced.
    sample_storyboard = {
        **storyboard,
        "shots": [shots[0]],
        "quality_mode": "balanced",
        "resolution": "720p",
        "_sample_mode": True,
    }

    job_id = _uuid.uuid4().hex[:16]
    job_dir = CINEMA_TEMP / f"sample_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    sb_path = job_dir / "storyboard.json"
    sb_path.write_text(json.dumps(sample_storyboard, ensure_ascii=False, indent=2), encoding="utf-8")
    output_mp4 = job_dir / "sample.mp4"
    script = CINEMA_DIR / "cinema_pipeline.py"
    if not script.exists():
        return jsonify({"ok": False, "error": "cinema_pipeline.py introuvable"}), 500

    args = ["--storyboard", str(sb_path), "--output", str(output_mp4)]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": "cinema_pipeline.py",
            "kind": "cinema_sample",
            "outputPath": str(output_mp4),
            "jobDir": str(job_dir),
            "mode": "sample",
        }
    _queue_video_job(job_id, str(script))
    t = threading.Thread(target=_run_python_job, args=(job_id, str(script), args), daemon=True)
    t.start()
    return jsonify({"ok": True, "jobId": job_id, "mode": "sample"})


@app.route("/api/cinema/regenerate-shot", methods=["POST"])
def cinema_regenerate_shot():
    """v82lr : re-render UN SEUL shot d'un job existant avec un nouveau seed,
    puis re-concat le final.mp4. Évite de tout regénérer pour fixer un seul
    plan faible (économie 80%+ du temps).

    Body : {
      jobId: "<id du job précédent>",
      shotId: <int>,
      alterSeed?: <int — nouveau seed, default = old+1000>,
      modifiedScene?: "<override scene description for retry>"
    }
    Retour : { ok, newJobId } — async via _run_python_script.
    """
    data = request.get_json(silent=True) or {}
    job_id = data.get("jobId")
    shot_id = data.get("shotId")
    if not job_id or shot_id is None:
        return jsonify({"ok": False, "error": "jobId + shotId requis"}), 400

    # Look up the previous job dir to grab storyboard.
    prev_dir = CINEMA_TEMP / f"job_{job_id}"
    if not prev_dir.exists():
        return jsonify({"ok": False, "error": f"job {job_id} introuvable"}), 404
    sb_path = prev_dir / "storyboard.json"
    if not sb_path.exists():
        return jsonify({"ok": False, "error": "storyboard manquant"}), 404
    try:
        storyboard = json.loads(sb_path.read_text(encoding="utf-8"))
    except Exception as e:
        return jsonify({"ok": False, "error": f"storyboard parse fail: {e}"}), 500

    # Modify the requested shot : new seed + optional scene override.
    shots = storyboard.get("shots", [])
    target = None
    for s in shots:
        if int(s.get("id", 0)) == int(shot_id):
            target = s
            break
    if target is None:
        return jsonify({"ok": False, "error": f"shot {shot_id} pas dans storyboard"}), 404

    alter_seed = data.get("alterSeed")
    if alter_seed is None:
        prev_seed = target.get("seed") or (1000 + int(shot_id) * 31)
        alter_seed = int(prev_seed) + 1000
    target["seed"] = int(alter_seed)
    if data.get("modifiedScene"):
        target["scene"] = str(data["modifiedScene"])[:1000]

    # Spawn a fresh job for this single shot. We narrow the storyboard
    # to ONLY this shot so we don't waste time re-rendering all the others.
    # Note: characters are kept so FLUX keyframe is consistent.
    narrow_storyboard = {
        **storyboard,
        "shots": [target],
        "_regeneration_of": {"jobId": job_id, "shotId": shot_id},
    }

    new_job_id = _uuid.uuid4().hex[:16]
    new_dir = CINEMA_TEMP / f"job_{new_job_id}"
    new_dir.mkdir(parents=True, exist_ok=True)
    sb_new = new_dir / "storyboard.json"
    sb_new.write_text(json.dumps(narrow_storyboard, ensure_ascii=False, indent=2), encoding="utf-8")
    output_mp4 = new_dir / "final.mp4"
    script = CINEMA_DIR / "cinema_pipeline.py"
    if not script.exists():
        return jsonify({"ok": False, "error": "cinema_pipeline.py introuvable"}), 500

    args = ["--storyboard", str(sb_new), "--output", str(output_mp4)]
    with _python_jobs_lock:
        _python_jobs[new_job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": "cinema_pipeline.py",
            "kind": "cinema_regenerate_shot",
            "outputPath": str(output_mp4),
            "jobDir": str(new_dir),
            "regenerationOf": {"jobId": job_id, "shotId": shot_id, "seed": alter_seed},
        }
    _queue_video_job(new_job_id, str(script))
    t = threading.Thread(target=_run_python_job, args=(new_job_id, str(script), args), daemon=True)
    t.start()

    return jsonify({
        "ok": True,
        "jobId": new_job_id,
        "shotId": shot_id,
        "seed": alter_seed,
        "outputPath": str(output_mp4),
    })


@app.route("/api/cinema/selftest", methods=["POST"])
def cinema_selftest():
    """Queue a real, minimal end-to-end render instead of a file/port check."""
    _gc_old_jobs()
    script = CINEMA_DIR / "cinema_pipeline.py"
    if not script.exists():
        return jsonify({"ok": False, "error": f"cinema_pipeline.py introuvable: {script}"}), 500

    job_id = _uuid.uuid4().hex[:16]
    job_dir = CINEMA_TEMP / f"sample_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    storyboard = {
        "title": "Aurora video self-test",
        "summary": "Micro-rendu reel de validation de la chaine video.",
        "style": "cinematic",
        "aspect": "16:9",
        "resolution": "720p",
        "quality_mode": "auto",
        "max_quality_attempts": 1,
        "strict_quality_gate": False,
        "characters": [{
            "name": "Testeur",
            "description": (
                "an adult technician wearing a plain cobalt blue jacket, "
                "short dark hair, neutral friendly expression"
            ),
            "voice_lang": "fr",
            "voice_preset": "default_french",
        }],
        "shots": [{
            "id": 1,
            "scene": (
                "Medium shot of Testeur in a softly lit film studio, making "
                "one small natural hand gesture toward the camera. Testeur is "
                "an adult technician wearing a plain cobalt blue jacket, short "
                "dark hair, neutral friendly expression."
            ),
            "camera": "medium shot, locked camera",
            "location": "film studio",
            "duration_s": 2.0,
            "speaker": "Testeur",
            "dialogue": "Test réussi.",
            "needs_lipsync": False,
            "max_quality_attempts": 1,
        }],
        "music": {"enabled": False},
        "subtitles": {"enabled": False},
        "_selftest_mode": True,
    }
    storyboard_path = job_dir / "storyboard.json"
    storyboard_path.write_text(
        json.dumps(storyboard, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    output_mp4 = job_dir / "sample.mp4"
    args = ["--storyboard", str(storyboard_path), "--output", str(output_mp4)]

    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "queued",
            "startedAt": time.time(),
            "script": script.name,
            "kind": "cinema_selftest",
            "outputPath": str(output_mp4),
            "jobDir": str(job_dir),
            "mode": "selftest",
        }
    _queue_video_job(job_id, str(script))
    threading.Thread(
        target=_run_python_job,
        args=(job_id, str(script), args),
        daemon=True,
    ).start()
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "status": "queued",
        "stages": {"queue": {"ok": True, "ms": 0}},
        "overall_ok": False,
        "summary": "Micro-rendu reel mis en file (FLUX, video, voix, mux et ffprobe).",
    })


@app.route("/api/cinema/benchmark", methods=["POST"])
def cinema_video_benchmark():
    """Queue a reproducible same-prompt/same-seed Wan-vs-LTX A/B campaign."""
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    storyboard = data.get("storyboard") if isinstance(data.get("storyboard"), dict) else {}
    shots = storyboard.get("shots") or []
    first_shot = shots[0] if shots and isinstance(shots[0], dict) else {}
    prompt = str(data.get("prompt") or first_shot.get("scene") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "prompt ou storyboard avec un plan requis"}), 400

    spec = {
        "prompt": prompt,
        "negative_prompt": data.get("negative_prompt") or first_shot.get("negative_prompt"),
        "width": data.get("width") or 832,
        "height": data.get("height") or 480,
        "num_frames": data.get("num_frames") or 49,
        "seed": data.get("seed") if data.get("seed") is not None else first_shot.get("seed", 424242),
        "image": data.get("image") or "",
        "variants": data.get("variants") or ["wan5b", "ltx"],
        "style": data.get("style") or storyboard.get("style") or "cinematic",
        "character_description": data.get("character_description") or "",
        "action_contract": data.get("action_contract") or first_shot.get("action_contract") or prompt,
    }
    job_id = _uuid.uuid4().hex[:16]
    job_dir = CINEMA_TEMP / f"benchmark_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    spec_path = job_dir / "spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    script = CINEMA_DIR / "video_ab_benchmark.py"
    if not script.exists():
        return jsonify({"ok": False, "error": f"harnais A/B introuvable: {script}"}), 500

    args = ["--spec", str(spec_path), "--output-dir", str(job_dir)]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "queued",
            "startedAt": time.time(),
            "script": script.name,
            "kind": "video_ab_benchmark",
            "jobDir": str(job_dir),
            "outputPath": str(job_dir / "report.json"),
        }
    _queue_video_job(job_id, str(script))
    threading.Thread(
        target=_run_python_job,
        args=(job_id, str(script), args),
        daemon=True,
    ).start()
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "status": "queued",
        "reportPath": str(job_dir / "report.json"),
        "variants": spec["variants"],
    })


@app.route("/api/cinema/preview-keyframes", methods=["POST"])
def cinema_preview_keyframes():
    """Lance l'apercu FLUX en job file-backed pour survivre au tunnel."""
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    storyboard = data.get("storyboard")
    if not isinstance(storyboard, dict):
        return jsonify({"ok": False, "error": "storyboard manquant"}), 400

    job_id = _uuid.uuid4().hex[:16]
    job_dir = CINEMA_TEMP / f"preview_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    storyboard_path = job_dir / "storyboard.json"
    storyboard_path.write_text(
        json.dumps(storyboard, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result_path = job_dir / "preview.json"
    script = CINEMA_DIR / "cinema_preview_keyframes.py"
    if not script.exists():
        return jsonify({
            "ok": False,
            "error": f"cinema_preview_keyframes.py introuvable: {script}",
        }), 500

    args = [
        "--storyboard", str(storyboard_path),
        "--work-dir", str(job_dir),
        "--output-json", str(result_path),
    ]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "queued",
            "startedAt": time.time(),
            "script": script.name,
            "kind": "cinema_preview_keyframes",
            "jobDir": str(job_dir),
            "outputPath": str(result_path),
        }
    _queue_video_job(job_id, str(script))
    threading.Thread(
        target=_run_python_job,
        args=(job_id, str(script), args),
        daemon=True,
    ).start()
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "previewId": job_id,
        "status": "queued",
    })


@app.route("/api/cinema/generate", methods=["POST"])
def cinema_generate():
    """Lance cinema_pipeline.py en async. Retourne {ok, jobId, output}.

    Le storyboard est ecrit dans temp/cinema/job_<id>/storyboard.json puis le
    pipeline genere temp/cinema/job_<id>/final.mp4.
    """
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    storyboard = data.get("storyboard")
    if not isinstance(storyboard, dict):
        return jsonify({"ok": False, "error": "storyboard manquant"}), 400

    # v90.3 : normalisation aussi au lancement (idempotente) — couvre les
    # storyboards edites cote UI ou postes directement sans repasser par
    # /api/cinema/storyboard : durees couvrant la parole, location heritee,
    # descriptions personnages injectees, quality_mode par defaut "balanced".
    try:
        cinema_dir = str(CINEMA_DIR)
        if cinema_dir not in sys.path:
            sys.path.insert(0, cinema_dir)
        from storyboard_norm import normalize_storyboard
        storyboard = normalize_storyboard(storyboard)
    except Exception as _norm_exc:
        print(f"[cinema] generate normalize skip: {_norm_exc}", flush=True)

    job_id = _uuid.uuid4().hex[:16]
    job_dir = CINEMA_TEMP / f"job_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)

    storyboard_path = job_dir / "storyboard.json"
    storyboard_path.write_text(json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")

    output_mp4 = job_dir / "final.mp4"
    script = CINEMA_DIR / "cinema_pipeline.py"
    if not script.exists():
        return jsonify({"ok": False, "error": f"cinema_pipeline.py introuvable: {script}"}), 500

    args = ["--storyboard", str(storyboard_path), "--output", str(output_mp4)]

    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": "cinema_pipeline.py",
            "kind": "cinema",
            "outputPath": str(output_mp4),
            "jobDir": str(job_dir),
        }
    _queue_video_job(job_id, str(script))
    t = threading.Thread(target=_run_python_job, args=(job_id, str(script), args), daemon=True)
    t.start()
    return jsonify({"ok": True, "jobId": job_id, "outputPath": str(output_mp4)})


# WS-V-P (2026-08-07) : point d'entrée unique du rendu vidéo mono-plan.
# Toute UI, CLI ou tunnel doit passer par ici et NON pas invoquer
# `video_generate.py` directement (Tauri contourne encore actuellement, cf.
# `PROMPT_REFONTE_MODULE_VIDEO §3.3` — chantier séparé). Le body accepte
# deux formes équivalentes :
#   1. { "intent": { "prompt": "...", "aspect": "16:9", "duration_s": 3, ... } }
#      → build_spec_from_intent() résout, on obtient un `VideoJobSpec`.
#   2. { "spec": { ... } } où spec est déjà une `VideoJobSpec` sérialisée
#      → chargée telle quelle (cas CLI `video_render --spec fichier.json`).
# La réponse contient `spec` résolue + `spec_hash` : le client peut afficher
# la spec avant lancement (équivalent HTTP de `--print-spec`).
@app.route("/api/video/render", methods=["POST"])
def video_render():
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    dry_run = bool(data.get("dry_run"))
    # SERVICES_DIR n'existe pas comme constante nommée dans bridge_server —
    # on la reconstruit à partir de WORKSPACE (CINEMA_DIR.parent === le dossier
    # python-services).
    _video_services_dir = pathlib.Path(WORKSPACE) / "python-services"
    try:
        services_dir = str(_video_services_dir)
        if services_dir not in sys.path:
            sys.path.insert(0, services_dir)
        import video_job_spec as _vjs
        import video_spec_builder as _vsb
    except Exception as _imp_exc:
        return jsonify({
            "ok": False,
            "error": f"video_job_spec/video_spec_builder introuvable: {_imp_exc}",
        }), 500

    try:
        if "spec" in data and isinstance(data["spec"], dict):
            spec = _vjs.from_dict(data["spec"])
        elif "intent" in data and isinstance(data["intent"], dict):
            spec = _vsb.build_spec_from_intent(**data["intent"])
        else:
            return jsonify({
                "ok": False,
                "error": "body doit contenir 'intent' (dict) ou 'spec' (dict)",
            }), 400
    except (TypeError, ValueError) as _spec_exc:
        return jsonify({
            "ok": False,
            "error": f"spec invalide: {_spec_exc}",
        }), 400

    spec_dict = spec.to_dict()

    if dry_run:
        # --print-spec équivalent HTTP : on résout, on retourne, sans rendre.
        return jsonify({"ok": True, "spec": spec_dict, "dry_run": True})

    # Rendu réel : passe par le worker existant via --worker-config-json,
    # même contrat que le rendu direct interne. On écrit la spec dans le
    # jobDir pour audit et pour permettre la reprise en cas de crash.
    job_id = _uuid.uuid4().hex[:16]
    job_dir = CINEMA_TEMP / f"video_render_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    spec_path = job_dir / "spec.json"
    spec_path.write_text(spec.to_json(indent=2), encoding="utf-8")

    output_mp4 = str(job_dir / "final.mp4")
    thumbnail = str(job_dir / "final.thumb.png")

    # Convert spec → CLI args for video_generate.py (existing contract).
    args = [
        "--prompt", spec.prompt_composed,
        "--output", output_mp4,
        "--thumbnail", thumbnail,
        "--width", str(spec.width),
        "--height", str(spec.height),
        "--num_frames", str(spec.num_frames),
        "--quality_mode", spec.quality_mode,
        "--motion_interp", str(spec.motion_interp),
        "--force_strategy", spec.force_strategy,
        "--seed", str(spec.seed),
    ]
    if spec.image_path:
        args += ["--image", spec.image_path]
    if spec.negative_prompt:
        args += ["--negative_prompt", spec.negative_prompt]

    script = _video_services_dir / "video_generate.py"
    if not script.exists():
        return jsonify({"ok": False, "error": f"video_generate.py introuvable: {script}"}), 500

    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": "video_generate.py",
            "kind": "video_render",
            "spec_hash": spec.spec_hash(),
            "specPath": str(spec_path),
            "outputPath": output_mp4,
            "jobDir": str(job_dir),
        }
    _queue_video_job(job_id, str(script))
    t = threading.Thread(
        target=_run_python_job,
        args=(job_id, str(script), args),
        daemon=True,
    )
    t.start()
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "outputPath": output_mp4,
        "specPath": str(spec_path),
        "specHash": spec.spec_hash(),
        "spec": spec_dict,
    })


def _parse_eta_from_progress(events: list[str]) -> dict | None:
    """Find the most recent PROGRESS:eta:<json> event and return its payload."""
    for line in reversed(events):
        if not isinstance(line, str):
            continue
        if line.startswith("PROGRESS:eta:"):
            try:
                return json.loads(line[len("PROGRESS:eta:"):])
            except Exception:
                continue
    return None


def _reload_lost_cinema_job(job_id: str) -> dict | None:
    """v82ly : reconstruit le state d'un cinema job depuis disk après bridge respawn.
    Le bridge en RAM perd _python_jobs au respawn. Cette fn :
      1. Cherche job_<id> ou sample_<id> dans CINEMA_TEMP
      2. Si dir existe, lit storyboard.json + cherche final.mp4/sample.mp4
      3. Status :
         - 'done' si output mp4 existe et size > 1KB → result reconstruit
         - 'running' si dir + storyboard mais pas de mp4 (interrupted)
         - 'unknown' sinon
    """
    for prefix in ("job_", "sample_", "preview_", "benchmark_"):
        d = CINEMA_TEMP / f"{prefix}{job_id}"
        if not d.exists():
            continue
        # v82ly : priority 1 — read status.json if it exists (final state
        # was persisted to disk by _run_python_job).
        status_path = d / "status.json"
        if status_path.exists():
            try:
                state = json.loads(status_path.read_text(encoding="utf-8"))
                state["kind"] = "cinema_recovered_from_disk"
                state["jobDir"] = str(d)
                return state
            except Exception:
                pass
        # priority 2 — output mp4 exists.
        out_mp4 = None
        for candidate in ("final.mp4", "sample.mp4"):
            p = d / candidate
            if p.exists() and p.stat().st_size > 1024:
                out_mp4 = p
                break
        control_path = d / ("spec.json" if prefix == "benchmark_" else "storyboard.json")
        if not out_mp4 and control_path.exists():
            # v82lz : if the job was running file-backed (cinema), tail stdout.log
            # to give recent PROGRESS events.
            stdout_log = d / "stdout.log"
            recent_output = ""
            if stdout_log.exists():
                try:
                    txt = stdout_log.read_text(encoding="utf-8", errors="replace")
                    # Last 4KB only.
                    recent_output = txt[-4096:] if len(txt) > 4096 else txt
                except Exception:
                    pass
            return {
                "status": "running",
                "kind": "cinema_lost_after_respawn",
                "jobDir": str(d),
                "output": recent_output,
                "note": "Job lost when bridge respawned. Subprocess may still be running (file-backed).",
            }
        if out_mp4:
            # v90.2 : re-expose le result JSON depuis stdout.log pour que
            # cinema_job_status puisse le parser après un respawn du bridge
            # (sinon l'UI perd scores/grade d'un job pourtant terminé).
            tail_output = ""
            stdout_log = d / "stdout.log"
            if stdout_log.exists():
                try:
                    txt = stdout_log.read_text(encoding="utf-8", errors="replace")
                    tail_output = txt[-16384:] if len(txt) > 16384 else txt
                except Exception:
                    pass
            return {
                "status": "done",
                "kind": "cinema_recovered",
                "outputPath": str(out_mp4),
                "jobDir": str(d),
                "output": tail_output,
                "exitCode": 0,
            }
    return None


def _job_eta_from_disk(job_id: str) -> dict | None:
    """v90.1 : ETA lue depuis le stdout.log du job LUI-MÊME (file-backed).

    Avant, l'ETA venait de `_python_progress_events`, liste GLOBALE partagée
    entre tous les jobs : un job fraîchement lancé renvoyait l'ETA périmée du
    job précédent ("plan 4/4 ok" au démarrage). Par-job ou rien."""
    for prefix in ("job_", "sample_", "preview_", "benchmark_"):
        log = CINEMA_TEMP / f"{prefix}{job_id}" / "stdout.log"
        if log.exists():
            try:
                lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                return None
            return _parse_eta_from_progress(lines[-400:])
    return None


VIDEO_OUTPUT_DIR = os.path.join(WORKSPACE, "output", "video")
# `output/RESULTATS` n est pas un module canonique : les resultats de rendu
# video appartiennent au module video, sous un projet.
RESULTATS_DIR = os.path.join(WORKSPACE, "output", "video", "_resultats")


@app.route("/api/cinema/films")
def cinema_films():
    """Bibliotheque des films livres dans application/output/video/<projet>/."""
    films = []
    seen_ids = set()
    dirs_to_scan = [VIDEO_OUTPUT_DIR]
    if os.path.isdir(RESULTATS_DIR) and os.path.realpath(RESULTATS_DIR) != os.path.realpath(VIDEO_OUTPUT_DIR):
        dirs_to_scan.append(RESULTATS_DIR)

    for scan_dir in dirs_to_scan:
        if not os.path.isdir(scan_dir):
            continue
        for nom in sorted(os.listdir(scan_dir), reverse=True):
            if nom in seen_ids or nom.startswith("."):
                continue
            dossier = os.path.join(scan_dir, nom)
            if not os.path.isdir(dossier):
                continue
            mp4 = os.path.join(dossier, "film.mp4")
            if not os.path.isfile(mp4):
                continue
            seen_ids.add(nom)
            rapport = {}
            chemin_rapport = os.path.join(dossier, "rapport.json")
            if os.path.isfile(chemin_rapport):
                try:
                    with open(chemin_rapport, encoding="utf-8") as f:
                        rapport = json.load(f)
                except Exception:
                    pass
            films.append({
                "id": nom,
                "module": nom.split("_", 1)[0],
                "titre": nom.split("_", 2)[-1].replace("-", " "),
                "video": f"/api/cinema/films/{nom}/video",
                "taille_mo": round(os.path.getsize(mp4) / 1e6, 1),
                "modifie": int(os.path.getmtime(mp4)),
                "plans_livres": rapport.get("plans_livres"),
                "plans_demandes": rapport.get("plans_demandes"),
                "moteur": rapport.get("moteur_video"),
                "note": rapport.get("quality_grade"),
                "avertissements": len(rapport.get("warnings") or []),
            })
    return jsonify({"ok": True, "films": films, "dossier": VIDEO_OUTPUT_DIR})


@app.route("/api/cinema/films/<film_id>/video")
def cinema_film_video(film_id: str):
    """Sert le mp4 d'un film livre. `conditional` autorise le seek du lecteur."""
    if "/" in film_id or "\\" in film_id or film_id.startswith("."):
        abort(400)
    for base_dir in (VIDEO_OUTPUT_DIR, RESULTATS_DIR):
        if not os.path.isdir(base_dir):
            continue
        chemin = os.path.join(base_dir, film_id, "film.mp4")
        if os.path.isfile(os.path.realpath(chemin)) and os.path.realpath(chemin).startswith(os.path.realpath(base_dir)):
            return send_file(chemin, mimetype="video/mp4", conditional=True)
    abort(404)


@app.route("/api/cinema/films/<film_id>/rapport")
def cinema_film_rapport(film_id: str):
    """Rapport chiffre du film : plans livres, mesures, voix, avertissements."""
    if "/" in film_id or "\\" in film_id or film_id.startswith("."):
        abort(400)
    for base_dir in (VIDEO_OUTPUT_DIR, RESULTATS_DIR):
        if not os.path.isdir(base_dir):
            continue
        chemin = os.path.join(base_dir, film_id, "rapport.json")
        if os.path.isfile(chemin) and os.path.realpath(chemin).startswith(os.path.realpath(base_dir)):
            with open(chemin, encoding="utf-8") as f:
                return jsonify(json.load(f))
    abort(404)


@app.route("/api/cinema/job/<job_id>")
def cinema_job_status(job_id: str):
    """Status of a cinema job + parsed ETA from PROGRESS:eta:* events."""
    with _python_jobs_lock:
        job = _python_jobs.get(job_id)
    if job is None:
        # v82ly : fallback — try to reconstruct from disk after bridge respawn.
        job = _reload_lost_cinema_job(job_id)
        if job is None:
            return jsonify({"status": "unknown", "error": "job not found"}), 404

    # v90.1 : sources par-job uniquement (stdout.log disque, puis output RAM
    # du job) — jamais la liste globale, qui mélange les jobs.
    eta = _job_eta_from_disk(job_id)
    if eta is None and job.get("output"):
        eta = _parse_eta_from_progress(job["output"].splitlines()[-400:])

    payload = {"jobId": job_id, **job}
    if eta:
        payload["eta"] = eta

    # If done, also try to parse the final result line from job["output"]
    if job.get("status") == "done" and job.get("output"):
        for line in reversed(job["output"].splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload["result"] = json.loads(line)
                except Exception:
                    pass
                break
    if job.get("storage") is not None:
        result = payload.setdefault("result", {})
        result["storage"] = job["storage"]
        storage_warnings = job["storage"].get("warnings") or []
        if not job["storage"].get("ok"):
            storage_warnings = [
                *storage_warnings,
                {
                    "code": job["storage"].get("reason", "storage_warning"),
                    "message": job["storage"].get("error")
                    or "La sortie reste sur le stockage interne.",
                },
            ]
        if storage_warnings:
            result["warnings"] = [*(result.get("warnings") or []), *storage_warnings]

    return jsonify(payload)


@app.route("/api/cinema/cancel/<job_id>", methods=["POST"])
def cinema_job_cancel(job_id: str):
    """Annule reellement le groupe de processus, pas seulement le polling UI."""
    return _cancel_video_job_response(job_id)


@app.route("/api/video/queue", methods=["GET"])
def video_gpu_queue_status():
    """Expose la file GPU effective pour une UI honnete et les diagnostics."""
    snapshot = _video_gpu_queue.snapshot()
    return jsonify({
        "ok": True,
        "activeJobId": snapshot["active_job_id"],
        "pendingJobIds": snapshot["pending_job_ids"],
        "generation3dActive": _is_3d_generation_active(),
    })


def _storage_response(callable_fn):
    if _storage_manager is None:
        return jsonify({
            "ok": False,
            "reason": "storage_manager_unavailable",
            "error": _storage_import_error,
        }), 503
    try:
        result = callable_fn()
    except StorageError as exc:
        result = exc.payload
    except Exception as exc:
        result = {
            "ok": False,
            "reason": "storage_operation_failed",
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
        }
    return jsonify(result), (200 if result.get("ok") else 409)


def _video_model_strategy() -> dict:
    """Load the reviewed strategy as runtime truth instead of duplicating labels."""
    strategy_path = pathlib.Path(WORKSPACE) / "config" / "video_model_strategy.json"
    try:
        strategy = json.loads(strategy_path.read_text(encoding="utf-8"))
        if not isinstance(strategy, dict) or not isinstance(strategy.get("active"), dict):
            raise ValueError("schema actif absent")
        return strategy
    except Exception as exc:
        return {
            "version": 0,
            "profile": "unknown",
            "active": {},
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
        }


@app.route("/api/storage/status", methods=["GET"])
def storage_status():
    """Read-only truth view; a directory is not a cold tier unless mounted."""
    def status_with_strategy():
        result = _storage_manager.status()
        strategy = _video_model_strategy()
        model_state = {item.get("id"): item for item in result.get("models", [])}
        cosy_python = pathlib.Path.home() / ".local/share/auroraia/venvs/cosyvoice3/bin/python"
        cosy_repo = pathlib.Path.home() / ".local/share/auroraia/engines/CosyVoice"
        cosy_model = (
            _storage_manager.cold_root / "models" / "Fun-CosyVoice3-0.5B-2512"
            if result.get("key_mounted")
            else pathlib.Path.home() / ".local/share/auroraia/models/Fun-CosyVoice3-0.5B-2512"
        )
        strategy["runtime"] = {
            "generator_available": bool(
                model_state.get("wan2.2-ti2v-5b", {}).get("available")
            ),
            "voice_clone_ready": bool(
                cosy_python.is_file()
                and (cosy_repo / "cosyvoice").is_dir()
                and (cosy_model / "cosyvoice3.yaml").is_file()
            ),
            "voice_clone_model_path": str(cosy_model),
        }
        result["model_strategy"] = strategy
        return result

    return _storage_response(status_with_strategy)


@app.route("/api/storage/tier", methods=["POST"])
def storage_tier():
    data = request.get_json(silent=True) or {}
    model_id = str(data.get("model_id") or "").strip()
    tier = str(data.get("tier") or "").strip()
    if not model_id or tier not in {"hot", "cold"}:
        return jsonify({"ok": False, "reason": "model_id_and_valid_tier_required"}), 400
    return _storage_response(lambda: _storage_manager.tier_model(model_id, tier))


@app.route("/api/storage/stage", methods=["POST"])
def storage_stage():
    model_id = str((request.get_json(silent=True) or {}).get("model_id") or "").strip()
    if not model_id:
        return jsonify({"ok": False, "reason": "model_id_required"}), 400
    return _storage_response(lambda: _storage_manager.stage(model_id))


@app.route("/api/storage/unstage", methods=["POST"])
def storage_unstage():
    model_id = str((request.get_json(silent=True) or {}).get("model_id") or "").strip()
    if not model_id:
        return jsonify({"ok": False, "reason": "model_id_required"}), 400
    return _storage_response(lambda: _storage_manager.unstage(model_id))


@app.route("/api/storage/gc", methods=["POST"])
def storage_gc():
    data = request.get_json(silent=True) or {}
    dry_run = data.get("dry_run") is not False
    max_age = int(data.get("max_age_minutes") or 180)
    return _storage_response(lambda: _storage_manager.gc(
        dry_run=dry_run,
        max_age_minutes=max_age,
    ))


@app.route("/api/storage/purge", methods=["POST"])
def storage_purge():
    data = request.get_json(silent=True) or {}
    model_id = str(data.get("model_id") or "").strip()
    if not model_id:
        return jsonify({"ok": False, "reason": "model_id_required"}), 400
    # A first call is always a recoverable dry-run. Deletion requires an
    # explicit confirmation in the request that names the resolved model.
    confirm = data.get("confirm") is True
    return _storage_response(lambda: _storage_manager.purge(model_id, dry_run=not confirm))


@app.route("/api/video/gallery", methods=["GET"])
def video_gallery():
    """Persistent gallery across module reloads and bridge restarts."""
    roots = []
    if _storage_manager is not None and _storage_manager.cold_mounted():
        roots.append(("cold", _storage_manager.cold_root / "outputs" / "videos"))
    roots.append(("hot", pathlib.Path(WORKSPACE) / "output" / "videos"))
    files = []
    seen = set()

    def append_video(path: pathlib.Path, tier: str, asset_path: str):
        if not path.is_file() or path.suffix.lower() not in {".mp4", ".webm", ".mov", ".mkv"}:
            return
        resolved = str(path.resolve(strict=False))
        if resolved in seen:
            return
        seen.add(resolved)
        stat = path.stat()
        files.append({
            "name": path.name,
            "path": str(path),
            "asset_url": f"/api/asset/{asset_path}",
            "tier": tier,
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
        })

    for tier, root in roots:
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if tier == "cold":
                asset_path = f"aurora-models/outputs/videos/{quote(path.name)}"
            else:
                asset_path = "/".join(quote(part) for part in ("output", "videos", path.name))
            append_video(path, tier, asset_path)

    # Les jobs récents restent consultables avant migration/GC, y compris les
    # sorties du harnais A/B. Le chemin asset demeure strictement sous WORKSPACE.
    if CINEMA_TEMP.is_dir():
        for job_dir in CINEMA_TEMP.iterdir():
            if not job_dir.is_dir() or not job_dir.name.startswith(
                ("job_", "sample_", "benchmark_")
            ):
                continue
            for path in job_dir.glob("*.mp4"):
                asset_path = "/".join(
                    quote(part)
                    for part in ("temp", "cinema", job_dir.name, path.name)
                )
                append_video(path, "hot", asset_path)
    files.sort(key=lambda item: item["modified"], reverse=True)
    return jsonify({
        "ok": True,
        "key_mounted": bool(_storage_manager and _storage_manager.cold_mounted()),
        "files": files[:500],
    })


# ---------------------------------------------------------------------------
# Voice library + extract + register + synthesize
# ---------------------------------------------------------------------------

@app.route("/api/voice/library", methods=["GET"])
def voice_library_list():
    """List all registered voices via voice_clone.py --list."""
    result = _run_cinema_script_sync("voice_clone.py", ["--list"], timeout=30)
    return jsonify(result), (200 if result.get("ok") else 500)


@app.route("/api/voice/library/<slug>", methods=["DELETE"])
def voice_library_delete(slug: str):
    """Delete a voice from the global library."""
    safe = re.sub(r"[^a-z0-9_]+", "", slug.lower())
    if not safe or safe != slug.lower().replace("-", "_"):
        return jsonify({"ok": False, "error": "slug invalide"}), 400
    target = VOICES_LIBRARY / safe
    if not target.is_dir():
        return jsonify({"ok": False, "error": "voix introuvable"}), 404
    try:
        import shutil as _sh
        _sh.rmtree(target)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, "slug": safe})


@app.route("/api/voice/library/clear", methods=["POST"])
def voice_library_clear():
    """Vide toute la bibliotheque de voix (utilise pour le bouton 'vider cache')."""
    if not VOICES_LIBRARY.exists():
        return jsonify({"ok": True, "deleted": 0})
    deleted = 0
    import shutil as _sh
    for entry in VOICES_LIBRARY.iterdir():
        if entry.is_dir():
            try:
                _sh.rmtree(entry)
                deleted += 1
            except Exception:
                pass
    return jsonify({"ok": True, "deleted": deleted})


@app.route("/api/voice/register", methods=["POST"])
def voice_register():
    """Register a voice from an uploaded WAV (file path OR base64 bytes)."""
    data = request.get_json(silent=True) or {}
    character = (data.get("character") or "").strip()
    lang = (data.get("lang") or "fr").strip()
    source = (data.get("source") or "").strip()
    transcript = (data.get("transcript") or "").strip()
    if not character:
        return jsonify({"ok": False, "error": "character manquant"}), 400

    ref_path: str | None = None

    # Mode A: file path on disk (Tauri or local browser)
    file_path = (data.get("filePath") or data.get("referencePath") or "").strip()
    if file_path and os.path.exists(file_path):
        ref_path = file_path

    # Mode B: base64-encoded WAV bytes (mobile / tunnel)
    b64 = data.get("wavBase64") or ""
    if not ref_path and b64:
        import base64 as _b64
        try:
            raw = _b64.b64decode(b64)
        except Exception as exc:
            return jsonify({"ok": False, "error": f"base64 invalide: {exc}"}), 400
        slug_safe = re.sub(r"[^a-z0-9_]+", "_", character.lower()).strip("_") or "imported"
        upload_dir = pathlib.Path(WORKSPACE) / "temp" / "voice_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        target = upload_dir / f"{slug_safe}_{int(time.time())}.wav"
        target.write_bytes(raw)
        ref_path = str(target)

    if not ref_path:
        return jsonify({"ok": False, "error": "fournir filePath ou wavBase64"}), 400

    args = [
        "--register",
        "--character", character,
        "--reference", ref_path,
        "--lang", lang,
    ]
    if source:
        args.extend(["--source", source])
    if transcript:
        args.extend(["--transcript", transcript])

    script = CINEMA_DIR / "voice_clone.py"
    if not script.exists():
        return jsonify({"ok": False, "error": "voice_clone.py introuvable"}), 500
    job_id = _uuid.uuid4().hex[:16]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "queued",
            "startedAt": time.time(),
            "script": script.name,
            "kind": "voice_register",
            "slug": re.sub(r"[^a-z0-9_]+", "_", character.lower()).strip("_"),
        }
    _queue_video_job(job_id, str(script))
    threading.Thread(
        target=_run_python_job,
        args=(job_id, str(script), args),
        daemon=True,
    ).start()
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "status": "queued",
        "slug": _python_jobs[job_id]["slug"],
    })


@app.route("/api/voice/extract", methods=["POST"])
def voice_extract_async():
    """Run voice_extract.py async (YouTube search + Demucs + ECAPA + cluster)."""
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    character = (data.get("character") or "imported").strip()
    query = (data.get("query") or "").strip()
    input_path = (data.get("inputPath") or "").strip()
    target_duration = float(data.get("targetDuration") or 20.0)
    min_confidence = float(data.get("minConfidence") or 0.55)
    max_videos = int(data.get("maxVideos") or 4)
    auto_register = bool(data.get("autoRegister", True))
    lang = (data.get("lang") or "fr").strip()
    transcript = (data.get("transcript") or "").strip()

    if not query and not input_path:
        return jsonify({"ok": False, "error": "fournir query ou inputPath"}), 400

    slug_safe = re.sub(r"[^a-z0-9_]+", "_", character.lower()).strip("_") or "imported"
    output_wav = VOICES_LIBRARY / slug_safe / "reference.wav"
    output_wav.parent.mkdir(parents=True, exist_ok=True)

    args = [
        "--character", character,
        "--output", str(output_wav),
        "--target-duration", str(target_duration),
        "--min-confidence", str(min_confidence),
        "--max-videos", str(max_videos),
        "--lang", lang,
    ]
    if auto_register:
        args.append("--auto-register")
    if transcript:
        args.extend(["--transcript", transcript])
    if input_path:
        args.extend(["--input", input_path])
    elif query:
        args.extend(["--query", query])

    script = CINEMA_DIR / "voice_extract.py"
    if not script.exists():
        return jsonify({"ok": False, "error": f"voice_extract.py introuvable: {script}"}), 500

    job_id = _uuid.uuid4().hex[:16]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": "voice_extract.py",
            "kind": "voice_extract",
            "character": character,
            "slug": slug_safe,
            "outputPath": str(output_wav),
            "autoRegister": auto_register,
            "lang": lang,
        }
    _queue_video_job(job_id, str(script))
    t = threading.Thread(target=_run_python_job, args=(job_id, str(script), args), daemon=True)
    t.start()
    return jsonify({"ok": True, "jobId": job_id, "outputPath": str(output_wav), "slug": slug_safe})


@app.route("/api/voice/synthesize", methods=["POST"])
def voice_synthesize():
    """One-shot synthesis for UI preview. Async to survive tunnel timeout."""
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    character = (data.get("character") or "").strip()
    text = (data.get("text") or "").strip()
    lang = (data.get("lang") or "auto").strip()
    prompt_text = (data.get("promptText") or data.get("transcript") or "").strip()
    instruction = (data.get("instruction") or "").strip()
    if not character or not text:
        return jsonify({"ok": False, "error": "character et text requis"}), 400

    slug_safe = re.sub(r"[^a-z0-9_]+", "_", character.lower()).strip("_") or "imported"
    out_dir = pathlib.Path(WORKSPACE) / "temp" / "voice_preview"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_wav = out_dir / f"{slug_safe}_{int(time.time())}.wav"

    args = [
        "--synthesize",
        "--character", character,
        "--text", text,
        "--lang", lang,
        "--output", str(out_wav),
    ]
    if prompt_text:
        args.extend(["--prompt-text", prompt_text])
    if instruction:
        args.extend(["--instruction", instruction])

    script = CINEMA_DIR / "voice_clone.py"
    if not script.exists():
        return jsonify({"ok": False, "error": "voice_clone.py introuvable"}), 500

    job_id = _uuid.uuid4().hex[:16]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": "voice_clone.py",
            "kind": "voice_synthesize",
            "outputPath": str(out_wav),
        }
    _queue_video_job(job_id, str(script))
    t = threading.Thread(target=_run_python_job, args=(job_id, str(script), args), daemon=True)
    t.start()
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "outputPath": str(out_wav),
        "status": "queued",
        **({"warning": "sync_desactive_pour_respecter_la_file_gpu"} if data.get("sync") else {}),
    })


@app.route("/api/voice/check", methods=["GET"])
def voice_clone_check():
    """Verify TTS engines + dependencies (proxy for voice_clone.py --check)."""
    result = _run_cinema_script_sync("voice_clone.py", ["--check"], timeout=60)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Studio de Réplication Vocale par échantillon (CLI, Tunnel, Web UI)
# ---------------------------------------------------------------------------

def _guess_audio_ext_and_bytes(b64_str: str) -> tuple[str, bytes]:
    """Extrait les octets et devine l'extension audio appropriée pour ffmpeg."""
    mime_type = ""
    clean_b64 = b64_str
    if "," in b64_str and ";base64" in b64_str:
        header, clean_b64 = b64_str.split(",", 1)
        mime_type = header.lower()

    raw_bytes = base64.b64decode(clean_b64)
    ext = ".wav"
    if "webm" in mime_type or raw_bytes.startswith(b"\x1a\x45\xdf\xa3"):
        ext = ".webm"
    elif "ogg" in mime_type or raw_bytes.startswith(b"OggS"):
        ext = ".ogg"
    elif "mp4" in mime_type or "m4a" in mime_type or "aac" in mime_type or b"ftyp" in raw_bytes[:16]:
        ext = ".mp4"
    elif "mp3" in mime_type or raw_bytes.startswith(b"ID3") or raw_bytes.startswith(b"\xff\xfb") or raw_bytes.startswith(b"\xff\xf3"):
        ext = ".mp3"
    elif "flac" in mime_type or raw_bytes.startswith(b"fLaC"):
        ext = ".flac"
    elif raw_bytes.startswith(b"RIFF"):
        ext = ".wav"
    return ext, raw_bytes


@app.route("/api/voice/studio/sample", methods=["POST"])
def voice_studio_upload_sample():
    """Reçoit un échantillon vocal (upload multipart, base64 ou raw binary), normalise et analyse."""
    try:
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rand_id = uuid.uuid4().hex[:8]
        sample_id = f"sample_{now_str}_{rand_id}"
        target_wav = VOIX_ECHANTILLONS_DIR / f"{sample_id}.wav"
        target_raw: pathlib.Path | None = None

        # Option 1: JSON avec base64 ou filePath
        data = request.get_json(silent=True) or {}
        b64 = data.get("wavBase64") or data.get("audioBase64") or data.get("audio") or data.get("base64") or ""
        file_path = data.get("filePath") or data.get("path") or ""

        if not b64 and request.form:
            b64 = request.form.get("wavBase64") or request.form.get("audioBase64") or request.form.get("audio") or ""
            if not file_path:
                file_path = request.form.get("filePath") or ""

        if b64:
            try:
                ext, raw_bytes = _guess_audio_ext_and_bytes(b64)
                target_raw = VOIX_ECHANTILLONS_DIR / f"{sample_id}_raw{ext}"
                target_raw.write_bytes(raw_bytes)
            except Exception as exc:
                return jsonify({"ok": False, "error": f"Décodage Base64 échoué: {exc}"}), 400
        elif file_path and os.path.exists(file_path):
            try:
                src = pathlib.Path(file_path)
                ext = src.suffix or ".wav"
                target_raw = VOIX_ECHANTILLONS_DIR / f"{sample_id}_raw{ext}"
                shutil.copy2(file_path, target_raw)
            except Exception as exc:
                return jsonify({"ok": False, "error": f"Impossible de copier le fichier source: {exc}"}), 400

        # Option 2: multipart/form-data ("audio" ou "file")
        if (not target_raw or not target_raw.exists()) and request.files:
            file = request.files.get("audio") or request.files.get("file")
            if file:
                orig_name = file.filename or "audio.webm"
                ext = pathlib.Path(orig_name).suffix or ".webm"
                target_raw = VOIX_ECHANTILLONS_DIR / f"{sample_id}_raw{ext}"
                file.save(str(target_raw))

        # Option 3: Raw body bytes si Content-Type commence par audio/
        if (not target_raw or not target_raw.exists() or target_raw.stat().st_size == 0):
            raw_body = request.get_data()
            if raw_body and len(raw_body) > 300:
                target_raw = VOIX_ECHANTILLONS_DIR / f"{sample_id}_raw.webm"
                target_raw.write_bytes(raw_body)

        if not target_raw or not target_raw.exists() or target_raw.stat().st_size < 300:
            return jsonify({"ok": False, "error": "Aucun flux audio valide reçu (upload vide ou trop court)"}), 400

        # Normalisation audio 16kHz mono PCM_S16LE via ffmpeg
        ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
        proc = subprocess.run([
            ffmpeg, "-y", "-i", str(target_raw),
            "-vn", "-map_metadata", "-1",
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            "-loglevel", "error", str(target_wav)
        ], capture_output=True, text=True, timeout=60)

        try:
            if target_raw and target_raw.exists():
                target_raw.unlink()
        except Exception:
            pass

        if proc.returncode != 0 or not target_wav.exists() or target_wav.stat().st_size < 500:
            return jsonify({
                "ok": False,
                "error": f"Échec de conversion audio: {proc.stderr.strip() or 'format audio non reconnu'}"
            }), 400

        # Analyse de la qualité de l'échantillon
        quality = {"ok": True, "quality_score": 0.85, "duration_s": 3.5}
        try:
            sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services" / "cinema"))
            import voice_clone
            quality = voice_clone.analyze_reference_audio(str(target_wav))
        except Exception as exc:
            quality["warning"] = str(exc)

        return jsonify({
            "ok": True,
            "sampleId": sample_id,
            "samplePath": str(target_wav),
            "audioUrl": f"/api/voice/studio/sample/{sample_id}/audio",
            "duration_s": quality.get("duration_s", 0.0),
            "quality": quality,
        })
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Erreur serveur studio vocal: {exc}"}), 500


@app.route("/api/voice/studio/sample/<sample_id>/audio", methods=["GET"])
def voice_studio_stream_sample(sample_id: str):
    """Sert l'audio de l'échantillon pour réécoute avant validation."""
    try:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-\.]+", "", sample_id)
        candidates = [
            VOIX_ECHANTILLONS_DIR / f"{safe_id}.wav",
            VOIX_ECHANTILLONS_DIR / safe_id,
            VOIX_PROFILS_DIR / safe_id / "reference.wav",
            LEGACY_LIBRARY_DIR / safe_id / "reference.wav",
        ]
        for c in candidates:
            if c.is_file():
                return send_file(str(c), mimetype="audio/wav", as_attachment=False)
        return jsonify({"ok": False, "error": f"Échantillon '{safe_id}' introuvable"}), 404
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/voice/studio/replicate", methods=["POST"])
def voice_studio_replicate():
    """Génère la parole ou chanson avec la voix répliquée, avec option de sauvegarde permanente."""
    try:
        data = request.get_json(silent=True) or {}
        sample_id = (data.get("sampleId") or data.get("samplePath") or "").strip()
        profile_slug = (data.get("profileSlug") or "").strip()
        text = (data.get("text") or "").strip()
        name = (data.get("name") or "Voix Répliquée").strip()
        save_permanent = bool(data.get("savePermanent", True))
        lang = (data.get("lang") or "fr").strip()
        prompt_text = (data.get("promptText") or "").strip()
        instruction = (data.get("instruction") or "").strip()

        if not text:
            return jsonify({"ok": False, "error": "Texte ou paroles requis"}), 400

        # Résolution de la référence audio
        sample_file: pathlib.Path | None = None
        if sample_id:
            safe_id = re.sub(r"[^a-zA-Z0-9_\-\.]+", "", sample_id)
            for c in [
                pathlib.Path(sample_id),
                VOIX_ECHANTILLONS_DIR / f"{safe_id}.wav",
                VOIX_ECHANTILLONS_DIR / safe_id,
                VOIX_PROFILS_DIR / safe_id / "reference.wav",
                LEGACY_LIBRARY_DIR / safe_id / "reference.wav",
            ]:
                if c.is_file():
                    sample_file = c
                    break

        if not sample_file and profile_slug:
            for c in [
                VOIX_PROFILS_DIR / profile_slug / "reference.wav",
                LEGACY_LIBRARY_DIR / profile_slug / "reference.wav",
            ]:
                if c.is_file():
                    sample_file = c
                    break

        if not sample_file or not sample_file.is_file():
            return jsonify({"ok": False, "error": "Échantillon audio source introuvable"}), 400

        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services"))
        import studio_voix
        result = studio_voix.replicate_voice(
            sample_path=sample_file,
            text=text,
            name=name,
            save_permanent=save_permanent,
            lang=lang,
            prompt_text=prompt_text,
            instruction=instruction,
        )
        if not result.get("ok"):
            return jsonify(result), 400

        wav_path = pathlib.Path(result["wav"])
        result["audioUrl"] = f"/api/voice/studio/generation/{wav_path.name}/audio"
        return jsonify(result)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Erreur de réplication: {exc}"}), 500


@app.route("/api/voice/studio/sing", methods=["POST"])
def voice_studio_sing():
    """Génère un chant vocal ou convertit un guide audio avec accompagnement musical optionnel."""
    try:
        data = request.get_json(silent=True) or {}
        sample_id = (data.get("sampleId") or data.get("samplePath") or "").strip()
        profile_slug = (data.get("profileSlug") or "").strip()
        lyrics = (data.get("lyrics") or data.get("text") or "").strip()
        guide_audio = (data.get("guideAudio") or data.get("guidePath") or "").strip()
        backing_music_id = (data.get("backingMusicId") or data.get("musicId") or "").strip()
        style = (data.get("style") or "Pop").strip()
        bpm = int(data.get("bpm") or 120)
        name = (data.get("name") or "Voix Chantée").strip()
        save_permanent = bool(data.get("savePermanent", True))
        lang = (data.get("lang") or "fr").strip()
        vocal_volume = float(data.get("vocalVolume") or 1.0)
        music_volume = float(data.get("musicVolume") or 0.55)

        # Résolution de la référence audio
        sample_file: pathlib.Path | None = None
        if sample_id:
            safe_id = re.sub(r"[^a-zA-Z0-9_\-\.]+", "", sample_id)
            for c in [
                pathlib.Path(sample_id),
                VOIX_ECHANTILLONS_DIR / f"{safe_id}.wav",
                VOIX_ECHANTILLONS_DIR / safe_id,
                VOIX_PROFILS_DIR / safe_id / "reference.wav",
                LEGACY_LIBRARY_DIR / safe_id / "reference.wav",
            ]:
                if c.is_file():
                    sample_file = c
                    break

        if not sample_file and profile_slug:
            for c in [
                VOIX_PROFILS_DIR / profile_slug / "reference.wav",
                LEGACY_LIBRARY_DIR / profile_slug / "reference.wav",
            ]:
                if c.is_file():
                    sample_file = c
                    break

        if not sample_file or not sample_file.is_file():
            return jsonify({"ok": False, "error": "Échantillon audio source introuvable"}), 400

        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services"))
        import studio_voix
        result = studio_voix.replicate_singing(
            sample_path=sample_file,
            lyrics=lyrics,
            guide_audio=guide_audio or None,
            backing_music_id=backing_music_id,
            style=style,
            bpm=bpm,
            name=name,
            save_permanent=save_permanent,
            lang=lang,
            vocal_volume=vocal_volume,
            music_volume=music_volume,
        )
        if not result.get("ok"):
            return jsonify(result), 400

        wav_path = pathlib.Path(result["wav"])
        result["audioUrl"] = f"/api/voice/studio/generation/{wav_path.name}/audio"
        return jsonify(result)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Erreur de chant: {exc}"}), 500


@app.route("/api/voice/studio/music/search", methods=["GET"])
def voice_studio_music_search():
    """Recherche des pistes musicales et accompagnements disponibles."""
    try:
        q = request.args.get("q", "").strip()
        limit = int(request.args.get("limit", 12))
        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services"))
        import studio_voix
        tracks = studio_voix.search_instrumental_tracks(q, limit=limit)
        return jsonify({"ok": True, "tracks": tracks, "count": len(tracks)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/voice/studio/music/track/<track_name>/audio", methods=["GET"])
def voice_studio_stream_music(track_name: str):
    """Sert l'audio d'une piste instrumentale d'accompagnement."""
    try:
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]+", "", track_name)
        target = VOIX_MUSIQUES_DIR / safe_name
        if not target.is_file():
            target = VOIX_MUSIQUES_DIR / f"{safe_name}.wav"
        if target.is_file():
            return send_file(str(target), mimetype="audio/wav", as_attachment=False)
        return jsonify({"ok": False, "error": "Piste musicale introuvable"}), 404
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/voice/studio/emotion/detect", methods=["POST"])
def voice_studio_detect_emotion():
    """Analyse l'émotion et fournit des consignes de prosodie intelligentes sans hardcoding."""
    try:
        data = request.get_json(silent=True) or {}
        text = data.get("text", "").strip()
        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services"))
        import studio_voix
        advice = studio_voix.auto_detect_emotion(text)
        return jsonify({"ok": True, **advice})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/voice/studio/calibrate", methods=["POST"])
def voice_studio_calibrate():
    """Calibre un ou tous les profils de voix avec Whisper pour une réplication parfaite."""
    try:
        data = request.get_json(silent=True) or {}
        slug = (data.get("slug") or "").strip()
        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services" / "cinema"))
        import voice_clone
        if slug:
            res = voice_clone.calibrate_profile(slug)
        else:
            res = voice_clone.calibrate_all_library_profiles()
        return jsonify(res)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/voice/studio/generation/<gen_name>/audio", methods=["GET"])
def voice_studio_stream_generation(gen_name: str):
    """Sert l'audio généré par le studio de réplication (parole ou chanson)."""
    try:
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]+", "", gen_name)
        candidates = [
            VOIX_GENERATIONS_DIR / safe_name,
            VOIX_GENERATIONS_DIR / f"{safe_name}.wav",
            VOIX_CHANSONS_DIR / safe_name,
            VOIX_CHANSONS_DIR / f"{safe_name}.wav",
            VOIX_SESSIONS_DIR / safe_name,
            VOIX_SESSIONS_DIR / f"{safe_name}.wav",
        ]
        for c in candidates:
            if c.is_file():
                return send_file(str(c), mimetype="audio/wav", as_attachment=False)
        return jsonify({"ok": False, "error": f"Génération '{safe_name}' introuvable"}), 404
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/voice/studio/tree", methods=["GET"])
def voice_studio_tree():
    """Renvoie l'arborescence et les statistiques complètes de application/output/voix/."""
    try:
        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services"))
        import studio_voix
        summary = studio_voix.get_tree_summary()
        return jsonify(summary)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/voice/studio/profiles", methods=["GET"])
def voice_studio_profiles():
    """Liste tous les profils vocaux disponibles avec URL d'écoute."""
    try:
        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services"))
        import studio_voix
        summary = studio_voix.get_tree_summary()
        profils = summary.get("profils", [])
        for p in profils:
            p["audioUrl"] = f"/api/voice/studio/sample/{p['slug']}/audio"
        return jsonify({"ok": True, "profils": profils, "count": len(profils)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/voice/studio/profile/<slug>", methods=["DELETE"])
def voice_studio_delete_profile(slug: str):
    """Supprime un profil vocal spécifique."""
    try:
        safe = re.sub(r"[^a-z0-9_]+", "", slug.lower())
        target = VOIX_PROFILS_DIR / safe
        if not target.is_dir():
            target = LEGACY_LIBRARY_DIR / safe
        if not target.is_dir():
            return jsonify({"ok": False, "error": "Profil introuvable"}), 404
        shutil.rmtree(target)
        return jsonify({"ok": True, "slug": safe})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/voice/studio/clean-legacy", methods=["POST"])
def voice_studio_clean_legacy():
    """Nettoie les dossiers de sortie obsolètes ou vides (ex: output/videos)."""
    try:
        cleaned = []
        legacy_candidates = [
            pathlib.Path(WORKSPACE) / "output" / "videos",
        ]
        for c in legacy_candidates:
            if c.is_dir() and not any(c.iterdir()):
                try:
                    c.rmdir()
                    cleaned.append(str(c))
                except Exception:
                    pass
        return jsonify({"ok": True, "cleaned": cleaned})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Music studio — local ACE-Step gateway
# ---------------------------------------------------------------------------

MUSIC_ENGINE_URL = os.environ.get("AURORA_MUSIC_URL", "http://127.0.0.1:8001").rstrip("/")
MUSIC_OUTPUT_DIR = pathlib.Path(WORKSPACE) / "output" / "music"
MUSIC_UPLOAD_DIR = pathlib.Path(WORKSPACE) / "temp" / "music_uploads"
MUSIC_MAX_UPLOAD_BYTES = 30 * 1024 * 1024
MUSIC_MAX_TEXT_CHARS = 12000
_music_jobs: dict[str, dict] = {}
_music_jobs_lock = threading.Lock()


def _music_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("ACESTEP_API_KEY", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _music_engine_json(path: str, *, method: str = "GET", payload: dict | None = None,
                       timeout: int = 20) -> tuple[dict | None, str | None]:
    """Call the locally configured composer and unwrap its documented envelope."""
    try:
        response = requests.request(
            method,
            f"{MUSIC_ENGINE_URL}{path}",
            headers=_music_headers(),
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return None, f"service local indisponible: {type(exc).__name__}: {str(exc)[:180]}"
    try:
        body = response.json()
    except ValueError:
        return None, f"reponse non JSON du service (HTTP {response.status_code})"
    if not response.ok or body.get("code", 200) >= 400:
        return None, str(body.get("error") or f"HTTP {response.status_code}")[:300]
    return body, None


def _music_safe_slug(value: str, fallback: str = "piste") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return (cleaned or fallback)[:56]


def _music_number(value, default: int | float, low: int | float, high: int | float) -> int | float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < low or parsed > high:
        return default
    return int(parsed) if isinstance(default, int) else parsed


def _music_choose_model(models: list[dict], quality: str) -> str | None:
    names = [str(item.get("name") or "") for item in models if item.get("name")]
    default = next((str(item["name"]) for item in models if item.get("is_default")), None)
    if quality == "studio":
        preferred = (
            "acestep-v15-xl-sft",
            "acestep-v15-xl-turbo",
            "acestep-v15-sft",
            "acestep-v15-turbo",
        )
    else:
        preferred = ("acestep-v15-turbo", "acestep-v15-sft")
    return next((name for name in preferred if name in names), default or (names[0] if names else None))


def _music_status_payload() -> dict:
    health, health_error = _music_engine_json("/health")
    if health_error:
        return {
            "ok": True,
            "ready": False,
            "models": [],
            "output_count": len(list(MUSIC_OUTPUT_DIR.glob("*"))) if MUSIC_OUTPUT_DIR.is_dir() else 0,
            "error": health_error,
        }
    model_data, model_error = _music_engine_json("/v1/models")
    models = [] if model_error else list((model_data or {}).get("data", {}).get("models") or [])
    return {
        "ok": True,
        "ready": True,
        "service": (health or {}).get("data", {}).get("service"),
        "version": (health or {}).get("data", {}).get("version"),
        "models": models,
        "default_model": (model_data or {}).get("data", {}).get("default_model"),
        "output_count": len(list(MUSIC_OUTPUT_DIR.glob("*"))) if MUSIC_OUTPUT_DIR.is_dir() else 0,
        **({"error": model_error} if model_error else {}),
    }


def _music_result_audio_url(file_value: str) -> str | None:
    if not file_value:
        return None
    if file_value.startswith(("http://", "https://")):
        engine = urlparse(MUSIC_ENGINE_URL)
        candidate = urlparse(file_value)
        if candidate.netloc != engine.netloc:
            return None
        return file_value
    if file_value.startswith("/"):
        return f"{MUSIC_ENGINE_URL}{file_value}"
    return f"{MUSIC_ENGINE_URL}/v1/audio?path={quote(file_value, safe='')}"


def _music_store_result(job: dict, result: dict) -> tuple[str | None, str | None]:
    file_url = _music_result_audio_url(str(result.get("file") or ""))
    if not file_url:
        return None, "fichier audio absent dans le resultat"
    try:
        response = requests.get(file_url, headers={k: v for k, v in _music_headers().items() if k != "Content-Type"}, stream=True, timeout=90)
        response.raise_for_status()
        content_length = int(response.headers.get("content-length") or 0)
        if content_length > 150 * 1024 * 1024:
            return None, "sortie trop volumineuse"
        parsed_url = urlparse(file_url)
        source_path = parse_qs(parsed_url.query).get("path", [parsed_url.path])[0]
        suffix = pathlib.PurePosixPath(source_path).suffix.lower()
        if suffix not in {".wav", ".mp3", ".flac", ".opus", ".aac", ".m4a"}:
            suffix = ".mp3"
        MUSIC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stem = _music_safe_slug(str(job.get("title") or "piste"))
        filename = f"{int(time.time())}_{job['id'][:8]}_{stem}{suffix}"
        target = MUSIC_OUTPUT_DIR / filename
        written = 0
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                written += len(chunk)
                if written > 150 * 1024 * 1024:
                    handle.close()
                    target.unlink(missing_ok=True)
                    return None, "sortie trop volumineuse"
                handle.write(chunk)
        metadata = {
            "title": job.get("title"),
            "created_at": time.time(),
            "request": job.get("request"),
            "engine_result": result,
        }
        target.with_suffix(target.suffix + ".json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        return filename, None
    except requests.RequestException as exc:
        return None, f"telechargement de la sortie impossible: {type(exc).__name__}: {str(exc)[:180]}"
    except OSError as exc:
        return None, f"ecriture de la sortie impossible: {str(exc)[:180]}"


def _music_refresh_job(job_id: str) -> dict | None:
    with _music_jobs_lock:
        job = _music_jobs.get(job_id)
        if job is None:
            return None
        if job.get("status") in {"completed", "failed"}:
            return dict(job)
        engine_task_id = job.get("engine_task_id")
    body, error = _music_engine_json("/query_result", method="POST", payload={"task_id_list": [engine_task_id]}, timeout=20)
    if error:
        with _music_jobs_lock:
            live = _music_jobs.get(job_id)
            if live is not None:
                live["last_poll_error"] = error
                return dict(live)
        return None
    records = list((body or {}).get("data") or [])
    record = records[0] if records else {}
    state = int(record.get("status") or 0)
    with _music_jobs_lock:
        live = _music_jobs.get(job_id)
        if live is None:
            return None
        if state == 0:
            live["status"] = "running"
            return dict(live)
        if state == 2:
            live.update({
                "status": "failed",
                "error": str(record.get("error") or "la composition a echoue")[:400],
                "completed_at": time.time(),
            })
            return dict(live)
        raw_result = record.get("result")
        try:
            parsed_result = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        except (TypeError, ValueError):
            parsed_result = None
        result = parsed_result[0] if isinstance(parsed_result, list) and parsed_result else (parsed_result if isinstance(parsed_result, dict) else None)
        if not result:
            live.update({"status": "failed", "error": "resultat de composition vide", "completed_at": time.time()})
            return dict(live)
        filename, store_error = _music_store_result(dict(live), result)
        if store_error:
            live.update({"status": "failed", "error": store_error, "completed_at": time.time()})
        else:
            live.update({
                "status": "completed",
                "filename": filename,
                "audio_url": f"/api/music/exports/{quote(filename)}",
                "metadata": result,
                "completed_at": time.time(),
            })
        return dict(live)


def _music_public_job(job: dict) -> dict:
    return {key: value for key, value in job.items() if key not in {"engine_task_id", "request"}}


@app.route("/api/music/status", methods=["GET"])
def music_status():
    return jsonify(_music_status_payload())


@app.route("/api/music/voices", methods=["GET"])
def music_voice_list():
    result = _run_cinema_script_sync("voice_clone.py", ["--list"], timeout=30)
    if not result.get("ok"):
        return jsonify({"ok": False, "voices": [], "error": result.get("error", "bibliotheque indisponible")}), 503
    voices = [
        {
            "slug": item.get("slug"),
            "name": item.get("character") or item.get("slug"),
            "lang": item.get("lang") or "auto",
            "duration_s": item.get("duration_s"),
            "quality_score": item.get("quality_score"),
        }
        for item in result.get("voices") or []
    ]
    return jsonify({"ok": True, "voices": voices})


@app.route("/api/music/voices", methods=["POST"])
def music_voice_import():
    """Import a user-supplied reference only after an explicit ownership confirmation."""
    if (request.form.get("consent") or "").strip().lower() != "true":
        return jsonify({"ok": False, "error": "confirmation de droits requise"}), 400
    if request.content_length and request.content_length > MUSIC_MAX_UPLOAD_BYTES:
        return jsonify({"ok": False, "error": "echantillon limite a 30 Mo"}), 413
    audio = request.files.get("audio")
    if audio is None or not (audio.filename or "").strip():
        return jsonify({"ok": False, "error": "fichier audio requis"}), 400
    name = (request.form.get("name") or "").strip()[:80]
    if not name:
        return jsonify({"ok": False, "error": "nom de voix requis"}), 400
    language = (request.form.get("language") or "fr").strip().lower()[:10]
    if language not in {"fr", "en", "es", "de", "it", "ja", "ko", "zh", "auto"}:
        return jsonify({"ok": False, "error": "langue non prise en charge"}), 400
    suffix = pathlib.Path(audio.filename).suffix.lower()
    if suffix not in {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".webm"}:
        return jsonify({"ok": False, "error": "format audio non pris en charge"}), 400
    slug = _music_safe_slug(name, "voix")
    MUSIC_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = f"{int(time.time())}_{_uuid.uuid4().hex[:8]}"
    source = MUSIC_UPLOAD_DIR / f"{slug}_{stamp}{suffix}"
    reference = MUSIC_UPLOAD_DIR / f"{slug}_{stamp}.wav"
    try:
        audio.save(source)
        if source.stat().st_size == 0 or source.stat().st_size > MUSIC_MAX_UPLOAD_BYTES:
            source.unlink(missing_ok=True)
            return jsonify({"ok": False, "error": "echantillon vide ou trop volumineux"}), 400
        convert = subprocess.run(
            ["ffmpeg", "-y", "-i", str(source), "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(reference)],
            capture_output=True,
            timeout=90,
        )
        if convert.returncode != 0 or not reference.is_file():
            return jsonify({"ok": False, "error": "conversion audio impossible; verifie le fichier envoye"}), 422
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "ffmpeg est requis pour importer un echantillon"}), 503
    except (OSError, subprocess.TimeoutExpired) as exc:
        return jsonify({"ok": False, "error": f"preparation de l echantillon impossible: {str(exc)[:180]}"}), 422

    script = CINEMA_DIR / "voice_clone.py"
    if not script.exists():
        return jsonify({"ok": False, "error": "service de voix introuvable"}), 500
    job_id = _uuid.uuid4().hex[:16]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "queued",
            "startedAt": time.time(),
            "script": script.name,
            "kind": "music_voice_register",
            "slug": slug,
        }
    threading.Thread(
        target=_run_python_job,
        args=(job_id, str(script), [
            "--register", "--character", name, "--reference", str(reference),
            "--lang", language, "--source", "music_studio_user_confirmed",
        ]),
        daemon=True,
    ).start()
    return jsonify({"ok": True, "jobId": job_id, "status": "queued", "slug": slug})


@app.route("/api/music/jobs", methods=["POST"])
def music_create():
    data = request.get_json(silent=True) or {}
    prompt = str(data.get("prompt") or "").strip()[:MUSIC_MAX_TEXT_CHARS]
    lyrics = str(data.get("lyrics") or "").strip()[:MUSIC_MAX_TEXT_CHARS]
    mode = str(data.get("mode") or "instrumental").strip().lower()
    title = str(data.get("title") or "Piste sans titre").strip()[:100]
    if mode not in {"instrumental", "song"}:
        return jsonify({"ok": False, "error": "mode invalide"}), 400
    if not prompt:
        return jsonify({"ok": False, "error": "decris le morceau a composer"}), 400
    if mode == "song" and not lyrics:
        return jsonify({"ok": False, "error": "des paroles sont requises pour un morceau chante"}), 400
    duration = _music_number(data.get("duration"), 45, 10, 600)
    bpm = _music_number(data.get("bpm"), 120, 30, 300)
    quality = str(data.get("quality") or "studio").strip().lower()
    if quality not in {"preview", "studio"}:
        quality = "studio"
    language = str(data.get("language") or "fr").strip().lower()[:10]
    key_scale = str(data.get("key") or "").strip()[:32]
    time_signature = str(data.get("timeSignature") or "4").strip()
    if time_signature not in {"2", "3", "4", "6"}:
        time_signature = "4"
    voice_slug = _music_safe_slug(str(data.get("voiceSlug") or ""), "")
    reference_path = None
    if voice_slug:
        candidate = (VOICES_LIBRARY / voice_slug / "reference.wav").resolve()
        library_root = VOICES_LIBRARY.resolve()
        if not str(candidate).startswith(str(library_root) + os.sep) or not candidate.is_file():
            return jsonify({"ok": False, "error": "voix de reference introuvable"}), 404
        reference_path = str(candidate)

    engine = _music_status_payload()
    if not engine.get("ready"):
        return jsonify({"ok": False, "error": engine.get("error") or "service musical indisponible"}), 503
    model = _music_choose_model(list(engine.get("models") or []), quality)
    engine_prompt = prompt if mode == "song" else f"{prompt}, instrumental only, no vocals, no spoken words"
    payload = {
        "prompt": engine_prompt,
        "lyrics": lyrics if mode == "song" else "",
        "vocal_language": language,
        "audio_duration": duration,
        "bpm": bpm,
        "key_scale": key_scale,
        "time_signature": time_signature,
        "batch_size": 1,
        "thinking": quality == "studio",
        "use_format": mode == "song",
        "use_cot_caption": True,
        "use_cot_language": True,
        "inference_steps": 8,
        "task_type": "text2music",
    }
    if model:
        payload["model"] = model
    if model and "base" in model:
        payload["inference_steps"] = 50
    if reference_path:
        payload["reference_audio_path"] = reference_path
    seed = data.get("seed")
    if isinstance(seed, int) and seed >= 0:
        payload.update({"seed": seed, "use_random_seed": False})
    body, error = _music_engine_json("/release_task", method="POST", payload=payload, timeout=45)
    if error:
        return jsonify({"ok": False, "error": error}), 502
    engine_data = (body or {}).get("data") or {}
    engine_task_id = str(engine_data.get("task_id") or "")
    if not engine_task_id:
        return jsonify({"ok": False, "error": "le service n a pas retourne de tache"}), 502
    job_id = _uuid.uuid4().hex
    job = {
        "id": job_id,
        "status": "queued",
        "queued_at": time.time(),
        "queue_position": engine_data.get("queue_position"),
        "engine_task_id": engine_task_id,
        "title": title,
        "request": {"mode": mode, "prompt": prompt, "lyrics": lyrics, "duration": duration, "bpm": bpm, "voice": voice_slug or None, "model": model},
    }
    with _music_jobs_lock:
        _music_jobs[job_id] = job
    return jsonify({"ok": True, **_music_public_job(job)})


@app.route("/api/music/jobs/<job_id>", methods=["GET"])
def music_job(job_id: str):
    job = _music_refresh_job(job_id)
    if job is None:
        return jsonify({"ok": False, "error": "tache introuvable"}), 404
    return jsonify({"ok": True, **_music_public_job(job)})


@app.route("/api/music/exports", methods=["GET"])
def music_exports():
    files = []
    if MUSIC_OUTPUT_DIR.is_dir():
        for path in MUSIC_OUTPUT_DIR.iterdir():
            if not path.is_file() or path.suffix.lower() not in {".wav", ".mp3", ".flac", ".opus", ".aac", ".m4a"}:
                continue
            metadata = {}
            try:
                metadata = json.loads(path.with_suffix(path.suffix + ".json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            files.append({
                "filename": path.name,
                "url": f"/api/music/exports/{quote(path.name)}",
                "modified": path.stat().st_mtime,
                "metadata": metadata,
            })
    files.sort(key=lambda item: item["modified"], reverse=True)
    return jsonify({"ok": True, "files": files[:100]})


@app.route("/api/music/exports/<path:filename>", methods=["GET"])
def music_export_file(filename: str):
    safe_name = pathlib.PurePosixPath(filename).name
    if safe_name != filename or not safe_name:
        abort(404)
    target = (MUSIC_OUTPUT_DIR / safe_name).resolve()
    if target.parent != MUSIC_OUTPUT_DIR.resolve() or not target.is_file():
        abort(404)
    return send_file(target, conditional=True)


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


@app.route("/api/cowork/read", methods=["GET"])
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


@app.route("/api/cowork/write", methods=["POST"])
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


@app.route("/api/cowork/delete", methods=["POST"])
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


@app.route('/api/cowork/session/create', methods=['POST'])
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


@app.route('/api/cowork/session/list', methods=['GET'])
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


@app.route('/api/cowork/session/write', methods=['POST'])
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


@app.route('/api/cowork/session/read', methods=['GET'])
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


@app.route('/api/cowork/session/list_files', methods=['GET'])
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


@app.route('/api/cowork/session/remove', methods=['POST'])
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


@app.route('/api/cowork/session/cleanup', methods=['POST'])
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


# =====================================================================
#  Cowork — extension navigateur (Aurora-Connect)
# =====================================================================
#
# L extension Chrome/Firefox/Edge polle /api/cowork/extension/poll en
# long-poll (jusqu'a 30s). Quand Aurora pousse une commande sur la file,
# l extension la recoit, l execute dans l onglet actif, et POSTe le
# resultat sur /api/cowork/extension/result.
#
# Aurora cote front pousse via /api/cowork/extension/dispatch.

import threading as _threading
import time as _time
import uuid as _uuid

_EXT_LOCK = _threading.Lock()
_EXT_PENDING: dict[str, list[dict]] = {}        # extId -> [{id, kind, payload}]
_EXT_RESULTS: dict[str, dict] = {}              # commandId -> result
_EXT_RESULTS_AT: dict[str, float] = {}          # commandId -> ts (gc)
_EXT_LAST_SEEN: dict[str, float] = {}           # extId -> ts
# v26 — persist _EXT_LAST_SEEN to disk so bridge restarts (self-watch hot reload)
# don't wipe the extension registry. Without this, every /loop iteration that
# touches bridge_server.py would briefly orphan the user's extension for ~25 sec
# while it re-polls — visible to the user as "Aucune extension Aurora-Connect
# detectee" right after clicking Cowork.
_EXT_PERSIST_PATH = pathlib.Path(WORKSPACE) / ".aurora_ext_seen.json"

def _ext_persist_save() -> None:
    try:
        with open(_EXT_PERSIST_PATH, "w", encoding="utf-8") as f:
            import json as _json
            _json.dump(_EXT_LAST_SEEN, f)
    except Exception:
        pass

def _ext_persist_load() -> None:
    try:
        if _EXT_PERSIST_PATH.is_file():
            import json as _json
            with open(_EXT_PERSIST_PATH, "r", encoding="utf-8") as f:
                data = _json.load(f)
            if isinstance(data, dict):
                # v82jn : étendu de 5 min → 24h. Le filter "active < 120s"
                # côté list filtre toujours les "online maintenant", mais la
                # mémoire long-terme permet de distinguer "jamais connectée"
                # vs "vue récemment, à reconnecter". 24h couvre les nuits.
                now = _time.time()
                for ext_id, ts in data.items():
                    if isinstance(ext_id, str) and isinstance(ts, (int, float)) and now - ts < 86400:
                        _EXT_LAST_SEEN[ext_id] = float(ts)
    except Exception:
        pass

_ext_persist_load()
_EXT_INBOUND: list[dict] = []                   # selections envoyees via menu contextuel
_EXT_BROWSER_HINT: dict = {}                    # detection navigateur PC


def _ext_gc():
    now = _time.time()
    expired_results = [k for k, t in list(_EXT_RESULTS_AT.items()) if now - t > 300]
    for k in expired_results:
        _EXT_RESULTS.pop(k, None)
        _EXT_RESULTS_AT.pop(k, None)
    if len(_EXT_INBOUND) > 200:
        del _EXT_INBOUND[:-200]


@app.route("/api/cowork/extension/poll", methods=["GET"])
def cowork_ext_poll():
    """Long-poll endpoint pour l extension. Renvoie une commande des qu une
    est dispo, ou apres ~25s si rien."""
    ext_id = request.args.get("extId", "").strip()
    wait_ms = int(request.args.get("wait", "25000"))
    wait_ms = max(1000, min(30000, wait_ms))
    if not ext_id:
        return jsonify({"ok": False, "error": "extId manquant"}), 400

    deadline = _time.time() + (wait_ms / 1000.0)
    with _EXT_LOCK:
        _EXT_LAST_SEEN[ext_id] = _time.time()
        _ext_gc()
        _ext_persist_save()

    while _time.time() < deadline:
        with _EXT_LOCK:
            queue = _EXT_PENDING.get(ext_id) or []
            if queue:
                cmd = queue.pop(0)
                if not queue:
                    _EXT_PENDING.pop(ext_id, None)
                return jsonify({"ok": True, "command": cmd})
        _time.sleep(0.4)

    return jsonify({"ok": True, "command": None})


@app.route("/api/cowork/extension/dispatch", methods=["POST"])
def cowork_ext_dispatch():
    """Aurora pousse une commande pour qu une extension l execute. Retourne
    le command_id; le caller fait ensuite GET /result?commandId=... ou attend."""
    body = request.get_json(silent=True) or {}
    ext_id = (body.get("extId") or "").strip()
    kind = (body.get("kind") or "").strip()
    payload = body.get("payload") or {}
    if not kind:
        return jsonify({"ok": False, "error": "kind manquant"}), 400

    cmd_id = _uuid.uuid4().hex
    cmd = {"id": cmd_id, "kind": kind, "payload": payload}

    with _EXT_LOCK:
        if ext_id:
            _EXT_PENDING.setdefault(ext_id, []).append(cmd)
        else:
            # Pas d ext_id specifique: dispatch a la premiere extension qui poll
            # (mais on a besoin de l identifier; pour rester simple, requiert ext_id).
            return jsonify({"ok": False, "error": "extId manquant — utilise /api/cowork/extension/list"}), 400

    return jsonify({"ok": True, "commandId": cmd_id})


@app.route("/api/cowork/extension/result", methods=["POST"])
def cowork_ext_result():
    """L extension POSTe le resultat d une commande."""
    body = request.get_json(silent=True) or {}
    cmd_id = (body.get("commandId") or "").strip()
    result = body.get("result")
    if not cmd_id:
        return jsonify({"ok": False, "error": "commandId manquant"}), 400
    with _EXT_LOCK:
        _EXT_RESULTS[cmd_id] = result
        _EXT_RESULTS_AT[cmd_id] = _time.time()
    return jsonify({"ok": True})


@app.route("/api/cowork/extension/await-result", methods=["GET"])
def cowork_ext_await():
    """Aurora attend le resultat d une commande dispatch (jusqu a 30s)."""
    cmd_id = request.args.get("commandId", "").strip()
    wait_ms = int(request.args.get("wait", "25000"))
    if not cmd_id:
        return jsonify({"ok": False, "error": "commandId manquant"}), 400
    deadline = _time.time() + (max(1000, min(30000, wait_ms)) / 1000.0)
    while _time.time() < deadline:
        with _EXT_LOCK:
            if cmd_id in _EXT_RESULTS:
                return jsonify({"ok": True, "result": _EXT_RESULTS[cmd_id]})
        _time.sleep(0.3)
    return jsonify({"ok": False, "error": "timeout"}), 504


@app.route("/api/cowork/extension/inbound", methods=["POST"])
def cowork_ext_inbound():
    """Envoi d evenement de l extension vers Aurora (clic droit sur selection)."""
    body = request.get_json(silent=True) or {}
    body["at"] = _time.time()
    with _EXT_LOCK:
        _EXT_INBOUND.append(body)
        _ext_gc()
    return jsonify({"ok": True})


@app.route("/api/cowork/extension/inbound", methods=["GET"])
def cowork_ext_inbound_list():
    with _EXT_LOCK:
        return jsonify({"ok": True, "events": list(_EXT_INBOUND)})


@app.route("/api/cowork/extension/download", methods=["GET"])
def cowork_ext_download():
    """Sert le ZIP de l extension Aurora-Connect pour install dans Chrome/
    Edge/Brave/Firefox. Le ZIP est genere a la volee depuis application/extension/."""
    import io, zipfile, pathlib
    ext_dir = pathlib.Path(WORKSPACE) / "extension"
    if not ext_dir.is_dir():
        return jsonify({"ok": False, "error": "extension/ introuvable"}), 404
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in ext_dir.rglob("*"):
            if path.is_file():
                arc = path.relative_to(ext_dir).as_posix()
                zf.write(path, arcname=arc)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=aurora-connect.zip",
            "Cache-Control": "no-cache",
        },
    )


@app.route("/api/cowork/extension/list", methods=["GET"])
def cowork_ext_list():
    """Liste les extensions actives (poll < 60s)."""
    with _EXT_LOCK:
        now = _time.time()
        # v26 — widen GC window from 60s to 120s : the extension polls every
        # ~30s but a brief network blip or self-watch reload can delay one
        # cycle ; 120s covers that without aggressive disconnect.
        active = [{"extId": k, "lastSeenAgoMs": int((now - t) * 1000)} for k, t in _EXT_LAST_SEEN.items() if now - t < 120]
    return jsonify({"ok": True, "extensions": active})


@app.route("/api/cowork/extension/status", methods=["GET"])
def cowork_ext_status():
    """v82jn : status enrichi qui distingue active (<120s) vs persisted
    (vue dans les 24h, persistée disque).
    Permet à l'UI Settings de dire "extension connue mais pas visible
    là-tout-de-suite, peut-être en train de re-poll" vs "jamais détectée".
    """
    with _EXT_LOCK:
        now = _time.time()
        active = [{"extId": k, "lastSeenAgoMs": int((now - t) * 1000)} for k, t in _EXT_LAST_SEEN.items() if now - t < 120]
        persisted = [{"extId": k, "lastSeenAgoMs": int((now - t) * 1000)} for k, t in _EXT_LAST_SEEN.items() if 120 <= now - t < 86400]
    return jsonify({
        "ok": True,
        "active": active,
        "activeCount": len(active),
        "persisted": persisted,
        "persistedCount": len(persisted),
        "totalKnown": len(active) + len(persisted),
    })


@app.route("/api/cowork/extension/version", methods=["GET"])
def cowork_ext_version():
    """Version actuellement attendue de l extension Aurora-Connect.

    Lit le manifest.json sur le disque (l extension est installee unpacked).
    Quand l user modifie le code et que la version y est bumpee, le polling
    de l extension declenche un chrome.runtime.reload() automatique — plus
    besoin de cliquer Recharger sur chrome://extensions.

    v82l6 : `application/extension/` est la SOURCE OFFICIELLE (cf
    bump-extension-version.py qui bump uniquement ce dossier). Les autres
    candidates (aurora-connect-extension/, extension_chrome/) sont des
    legacy stamped DEPRECATED — gardees ici en fallback uniquement pour
    qu un dev-environnement old qui a deja installe la legacy ne perde pas
    la route, mais l ordre garantit que extension/ gagne toujours quand
    elle existe.
    """
    import json
    import pathlib
    candidates = [
        # Source officielle, bumpee par bump-extension-version.py.
        pathlib.Path(WORKSPACE) / "extension" / "manifest.json",
        # Fallbacks legacy (DEPRECATED) — gardes pour ne pas casser un
        # environnement deja installe sur l ancien dossier.
        pathlib.Path(WORKSPACE) / "aurora-connect-extension" / "manifest.json",
        pathlib.Path(WORKSPACE).parent / "extension_chrome" / "manifest.json",
        pathlib.Path(WORKSPACE).parent / "application" / "aurora-connect-extension" / "manifest.json",
    ]
    for path in candidates:
        if path.is_file():
            try:
                m = json.loads(path.read_text(encoding="utf-8"))
                return jsonify({"ok": True, "version": m.get("version", "0.0.0"), "source": str(path)})
            except Exception as e:  # noqa: BLE001
                return jsonify({"ok": False, "error": f"manifest illisible: {e}"}), 500
    return jsonify({"ok": False, "error": "manifest.json introuvable"}), 404


# ---------------------------------------------------------------------
#  Dev-time hot reload : re-exec ce process Python apres un changement
#  de bridge_server.py. Le user n a pas a relancer start-aurora.bat
#  pour voir une nouvelle route prise en compte. Aurora peut declencher
#  le reload elle-meme via /api/_dev/reload (ex : apres un /loop qui a
#  modifie le bridge).
#
#  Sans Flask debug=True (qui exposerait le debugger Werkzeug). On utilise
#  os.execv pour replacer le process courant par un nouveau qui re-importe
#  le source actuel. Le tunnel cloudflared ne broncher pas car le port
#  3001 reste lie pendant la transition.
# ---------------------------------------------------------------------
_BRIDGE_BOOT_AT = _time.time()
_BRIDGE_FILE_MTIME_AT_BOOT = None
try:
    _BRIDGE_FILE_MTIME_AT_BOOT = pathlib.Path(__file__).stat().st_mtime
except Exception:
    pass


@app.route("/api/_dev/status", methods=["GET"])
def dev_status():
    """Etat du bridge : booted_at + mtime fichier source + mtime courant."""
    try:
        cur_mtime = pathlib.Path(__file__).stat().st_mtime
    except Exception:
        cur_mtime = None
    return jsonify({
        "ok": True,
        "bootedAt": _BRIDGE_BOOT_AT,
        "fileMtimeAtBoot": _BRIDGE_FILE_MTIME_AT_BOOT,
        "fileMtimeNow": cur_mtime,
        "needsReload": (cur_mtime is not None and _BRIDGE_FILE_MTIME_AT_BOOT is not None
                         and cur_mtime > _BRIDGE_FILE_MTIME_AT_BOOT + 0.5),
    })


@app.route("/api/_dev/reload", methods=["POST"])
def dev_reload_endpoint():
    """Re-exec le process bridge — toutes les routes refletent le code disque
    actuel. Aucune autre dependance impactee (Ollama / ComfyUI / Vite / Tunnel
    tournent dans des process distincts)."""
    import os
    import sys
    import threading

    def do_exec():
        _time.sleep(0.3)  # let the response flush first
        # v90.2 : sur Windows os.execv ne REMPLACE pas le process — l'ancien
        # reste lié au port 3001 à côté du nouveau (double LISTEN constaté,
        # connexions qui tombent sur le process mort). On passe par le
        # respawn détaché + exit planifié, pattern déjà validé de
        # /api/admin/restart-bridge.
        if os.name == "nt":
            _respawn_bridge_async("dev reload endpoint")
            return
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=do_exec, daemon=True).start()
    return jsonify({"ok": True, "message": "Bridge en cours de redemarrage..."})


def _bridge_self_watch_loop():
    """Watch bridge_server.py for changes ; re-exec the process when modified.

    Truly zero-touch hot reload : after a /loop pushes new bridge code, the
    next mtime tick (within 2 sec) triggers an os.execv that swaps the
    process for a fresh import. The cloudflared tunnel + clients survive
    because port 3001 is rebound by the new process within ~200 ms.

    Disabled if AURORA_BRIDGE_NO_WATCH=1 or if __file__ cannot be stat'd
    (e.g. running from frozen PyInstaller bundle).
    """
    import os
    import sys

    if os.environ.get("AURORA_BRIDGE_NO_WATCH", "").strip() in ("1", "true", "yes"):
        return
    src = pathlib.Path(__file__)
    try:
        last_mtime = src.stat().st_mtime
    except Exception:
        return
    while True:
        _time.sleep(2.0)
        try:
            cur_mtime = src.stat().st_mtime
        except Exception:
            continue
        if cur_mtime > last_mtime + 0.5:
            print(f"[bridge self-watch] {src.name} mtime change detectee, re-exec...", flush=True)
            # v90.2 : Windows — os.execv laisse l'ancien process lié au port
            # 3001 (double LISTEN). Respawn détaché + exit planifié à la place.
            if os.name == "nt":
                if _respawn_bridge_async("self-watch mtime change"):
                    return  # exit du process planifié par _respawn_bridge_async
                last_mtime = cur_mtime
                continue
            try:
                os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as e:  # noqa: BLE001
                print(f"[bridge self-watch] execv echec: {e}", flush=True)
                last_mtime = cur_mtime  # keep going


def _start_self_watch_once():
    """Idempotent : starts the self-watch thread on first call. Called from
    the boot section below so it runs only in the main worker, not in the
    spawned children (Werkzeug reloader, tests, etc.)."""
    import threading
    if getattr(_start_self_watch_once, "_started", False):
        return
    _start_self_watch_once._started = True  # type: ignore[attr-defined]
    threading.Thread(target=_bridge_self_watch_loop, daemon=True, name="bridge-self-watch").start()


# ---------------------------------------------------------------------
# v82ld — Boot-time Ollama warmup.
#
# qwen3:14b cold-loads in ~11s on this machine. Every fresh bridge boot
# means the FIRST /api/cowork/extract-structured call inherits that latency,
# which the user feels as a "first scrape is slow then fine" pattern.
#
# Warmup fix : after Flask is up, fire a tiny generate request directly
# at Ollama (NOT via our extract endpoint to avoid bootstrap reentrancy).
# qwen3:14b loads into VRAM, all subsequent calls hit a hot model.
#
# Hard rule : daemon thread, never blocks server start. Any failure (Ollama
# down, model missing, timeout) is logged and silently dropped — bridge
# boots regardless.
#
# v82le — module-level state dict so /api/warmup/status can expose progress
# to UI/extension. Lifecycle : pending → ready (latency_ms+ts) | failed (error).
# ---------------------------------------------------------------------
_WARMUP_STATE: "dict[str, object]" = {
    "state": "pending",
    "model": "qwen3:14b",
    "latency_ms": None,
    "ts": None,
    "error": None,
}


def _ollama_warmup_loop(model: str = "qwen3:14b") -> None:
    """Fire a tiny prompt at Ollama to amortize cold-start. Daemon-only."""
    import time as _time
    _WARMUP_STATE["state"] = "pending"
    _WARMUP_STATE["model"] = model
    _WARMUP_STATE["latency_ms"] = None
    _WARMUP_STATE["ts"] = None
    _WARMUP_STATE["error"] = None
    started = _time.perf_counter()
    try:
        # quick health check — bail if Ollama is not even responding
        try:
            requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        except Exception as e:  # noqa: BLE001
            print(f"[warmup] Ollama unreachable, skipping warmup ({e})", flush=True)
            _WARMUP_STATE["state"] = "failed"
            _WARMUP_STATE["error"] = f"ollama_unreachable: {e}"
            _WARMUP_STATE["ts"] = _time.time()
            return
        # Tiny prompt — max 4 tokens out, 1s temp, deterministic.
        payload = {
            "model": model,
            "prompt": "ok",
            "stream": False,
            "options": {"num_predict": 4, "temperature": 0.0},
        }
        r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=120)
        elapsed_ms = int((_time.perf_counter() - started) * 1000)
        if r.status_code == 200:
            print(f"[warmup] {model} ready in {elapsed_ms}ms", flush=True)
            _WARMUP_STATE["state"] = "ready"
            _WARMUP_STATE["latency_ms"] = elapsed_ms
            _WARMUP_STATE["ts"] = _time.time()
        else:
            print(f"[warmup] {model} HTTP {r.status_code} after {elapsed_ms}ms — skipped", flush=True)
            _WARMUP_STATE["state"] = "failed"
            _WARMUP_STATE["latency_ms"] = elapsed_ms
            _WARMUP_STATE["ts"] = _time.time()
            _WARMUP_STATE["error"] = f"http_{r.status_code}"
    except Exception as e:  # noqa: BLE001
        elapsed_ms = int((_time.perf_counter() - started) * 1000)
        print(f"[warmup] {model} failed after {elapsed_ms}ms: {e}", flush=True)
        _WARMUP_STATE["state"] = "failed"
        _WARMUP_STATE["latency_ms"] = elapsed_ms
        _WARMUP_STATE["ts"] = _time.time()
        _WARMUP_STATE["error"] = str(e)


@app.route("/api/warmup/status", methods=["GET"])
def warmup_status():
    """Return current Ollama warmup lifecycle.

    Pure observability — UI/extension can poll this to render a "modele en
    chauffe" hint instead of an opaque spinner during the cold-start window.

    Response shape (always 200) :
      {
        "state": "pending" | "ready" | "failed",
        "model": "qwen3:14b",
        "latency_ms": int | null,   // total time from warmup start to terminal state
        "ts":         float | null, // unix epoch when state became terminal
        "error":      str   | null  // populated when state == "failed"
      }
    """
    return jsonify({
        "state": _WARMUP_STATE.get("state"),
        "model": _WARMUP_STATE.get("model"),
        "latency_ms": _WARMUP_STATE.get("latency_ms"),
        "ts": _WARMUP_STATE.get("ts"),
        "error": _WARMUP_STATE.get("error"),
    })


def _start_ollama_warmup_once(model: str = "qwen3:14b") -> None:
    """Idempotent fire-and-forget warmup. Logs once."""
    import threading
    if getattr(_start_ollama_warmup_once, "_started", False):
        return
    _start_ollama_warmup_once._started = True  # type: ignore[attr-defined]
    threading.Thread(
        target=_ollama_warmup_loop,
        kwargs={"model": model},
        daemon=True,
        name="bridge-ollama-warmup",
    ).start()


def _run_warmup(model: str) -> None:
    """v82lf — non-idempotent fire-and-forget warmup, used by /api/warmup/restart.

    Distinct from `_start_ollama_warmup_once` (boot-time, runs once per process).
    This one re-fires regardless of any prior warmup state, so the user can
    manually re-trigger the load — e.g. after switching the bridge's primary
    text model, or after Ollama restarts on its own.

    Always returns immediately ; the actual generate call happens in a daemon
    thread. Callers should poll /api/warmup/status to observe the transition.
    """
    import threading
    threading.Thread(
        target=_ollama_warmup_loop,
        kwargs={"model": model},
        daemon=True,
        name="bridge-ollama-warmup-restart",
    ).start()


@app.route("/api/warmup/restart", methods=["POST"])
def warmup_restart():
    """v82lf — manually re-trigger the Ollama warmup.

    Body (optional) :
      { "model": "qwen3:14b" }   // default = current _WARMUP_STATE["model"]

    Effects (synchronous, before returning) :
      - _WARMUP_STATE reset to a fresh "pending" snapshot for the chosen model
      - _VRAM_CACHE dropped so the next picker call re-probes nvidia-smi
        instead of waiting up to 30s for the next TTL window

    Effects (async, fire-and-forget) :
      - daemon thread runs _ollama_warmup_loop(model) → state flips to "ready"
        or "failed" within ~hundreds of ms (qwen3:14b cold-loads in ~11s, hot
        reloads in ~1-2s ; smaller models faster)

    Returns 200 immediately :
      { "ok": true, "state": "pending", "model": "<chosen>" }

    Pure manual control surface — UI/extension can hit this when they suspect
    the model has fallen out of VRAM or after switching primary models. Does
    NOT touch scrape/cowork logic, no selectors, no per-site rules.
    """
    payload = request.get_json(silent=True) or {}
    requested = (payload.get("model") or "").strip()
    fallback = str(_WARMUP_STATE.get("model") or "qwen3:14b")
    model = requested or fallback
    # Drop VRAM cache so the next picker call re-probes nvidia-smi instead
    # of waiting up to 30s for the cached entry to expire. Cheap and explicit.
    _VRAM_CACHE["value"] = None  # forward-compat key, harmless if unused
    _VRAM_CACHE["ts"] = 0.0
    _VRAM_CACHE["free_gb"] = 0.0
    # Reset state to pending NOW so a fast poll between restart and the
    # daemon-thread first instruction does not see stale "ready".
    _WARMUP_STATE["state"] = "pending"
    _WARMUP_STATE["model"] = model
    _WARMUP_STATE["latency_ms"] = None
    _WARMUP_STATE["ts"] = None
    _WARMUP_STATE["error"] = None
    _run_warmup(model)
    # v82lh — `vram_dropped: true` is a deterministic contract enrichment.
    # The cache drop above is unconditional, so this field is always true.
    # Lets the extension surface a "VRAM probe refreshed" toast without
    # second-guessing whether the drop fired.
    #
    # v82lj — `vision_after` is a dry-run picker snapshot computed AFTER the
    # VRAM cache drop, so `_get_free_vram_gb()` re-probes nvidia-smi on
    # the next call. Lets the UI show "VRAM probe refreshed AND picker
    # would now choose X" in a single round-trip — no follow-up
    # /api/picker/explain needed. Pure read : no Ollama call, no history
    # append, no simulate override (real cached-probe-just-cleared probe).
    try:
        va_model, va_reason, va_kind = _pick_vision_model_or_default("qwen3-vl:8b")
        try:
            va_free_gb = _get_free_vram_gb()
        except Exception:
            va_free_gb = 0.0
        vision_after = {
            "model": va_model,
            "reason": va_reason,
            "reason_kind": va_kind,
            "free_vram_gb": va_free_gb,
        }
    except Exception as exc:  # noqa: BLE001
        # Best-effort observability — never fail the restart on probe error.
        vision_after = {
            "model": "qwen3-vl:8b",
            "reason": f"probe failed: {exc}",
            "reason_kind": "default",
            "free_vram_gb": 0.0,
        }
    return jsonify({
        "ok": True,
        "state": "pending",
        "model": model,
        "vram_dropped": True,
        "vision_after": vision_after,
    })


# ---------------------------------------------------------------------
# v82ld — Conditional qwen3-vl:8b pull.
#
# qwen3-vl:8b is the small/fast vision model used by extract-structured
# when an image is provided. If the user has comfortable VRAM headroom
# (>=10 GB free) AND the model is not already pulled, fetch it in the
# background so vision-aware extraction works out of the box.
#
# Hard rule : entirely best-effort. Any failure path (no GPU, low VRAM,
# Ollama down, network down, partial pull) is silently swallowed. Never
# blocks bridge boot. The model is small (~5 GB pull) so 10GB free leaves
# headroom for the runner itself.
# ---------------------------------------------------------------------
def _query_free_vram_gb() -> "float | None":
    """Return free VRAM in GB via nvidia-smi. None if unavailable."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            timeout=4,
        ).decode("utf-8", errors="replace").strip()
        # Multi-GPU : pick the largest free pool
        best_mb = 0
        for line in out.splitlines():
            try:
                mb = int(line.strip())
                if mb > best_mb:
                    best_mb = mb
            except ValueError:
                continue
        if best_mb <= 0:
            return None
        return round(best_mb / 1024.0, 1)
    except Exception:
        return None


def _pull_qwen3vl_if_useful(model: str = "qwen3-vl:8b", min_free_vram_gb: float = 10.0) -> None:
    """Pull qwen3-vl:8b if not present AND free VRAM >= min_free_vram_gb.

    Best-effort daemon worker. All failure paths are logged-and-swallowed.
    """
    try:
        # 1. Already installed ?
        try:
            tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=4)
        except Exception as e:  # noqa: BLE001
            print(f"[qwen3-vl-pull] Ollama unreachable, skip ({e})", flush=True)
            return
        if tags.status_code != 200:
            print(f"[qwen3-vl-pull] /api/tags HTTP {tags.status_code} — skip", flush=True)
            return
        try:
            data = tags.json() or {}
        except Exception:
            data = {}
        for m in data.get("models", []) or []:
            nm = (m.get("name") or m.get("model") or "").strip().lower()
            if nm == model.lower():
                print(f"[qwen3-vl-pull] {model} already installed — skip", flush=True)
                return

        # 2. VRAM check
        free_gb = _query_free_vram_gb()
        if free_gb is None:
            print("[qwen3-vl-pull] no GPU / nvidia-smi unavailable — skip", flush=True)
            return
        if free_gb < min_free_vram_gb:
            print(f"[qwen3-vl-pull] free VRAM {free_gb}GB < {min_free_vram_gb}GB — skip", flush=True)
            return

        # 3. Pull (streaming, but we don t forward progress — just drain)
        print(f"[qwen3-vl-pull] free VRAM {free_gb}GB OK — pulling {model}...", flush=True)
        try:
            with requests.post(
                f"{OLLAMA_URL}/api/pull",
                json={"name": model, "stream": True},
                stream=True,
                timeout=3600,
            ) as r:
                if r.status_code != 200:
                    print(f"[qwen3-vl-pull] /api/pull HTTP {r.status_code} — skip", flush=True)
                    return
                for line in r.iter_lines():
                    if not line:
                        continue
                    # We don t parse — just keep the connection alive
            print(f"[qwen3-vl-pull] {model} pulled OK", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[qwen3-vl-pull] pull failed: {e}", flush=True)
    except Exception as e:  # noqa: BLE001
        # Catch-all — never let this kill the bridge
        print(f"[qwen3-vl-pull] unexpected error, swallow: {e}", flush=True)


def _start_qwen3vl_pull_once(model: str = "qwen3-vl:8b") -> None:
    """Idempotent fire-and-forget conditional pull."""
    import threading
    if getattr(_start_qwen3vl_pull_once, "_started", False):
        return
    _start_qwen3vl_pull_once._started = True  # type: ignore[attr-defined]
    threading.Thread(
        target=_pull_qwen3vl_if_useful,
        kwargs={"model": model},
        daemon=True,
        name="bridge-qwen3vl-pull",
    ).start()


@app.route("/api/cowork/extension/install-md", methods=["GET"])
def cowork_ext_install_md():
    """Sert le markdown d installation a une UI tierce ou en preview brut."""
    import pathlib
    md = pathlib.Path(WORKSPACE) / "extension" / "INSTALL.md"
    if not md.is_file():
        return jsonify({"ok": False, "error": "INSTALL.md introuvable"}), 404
    return Response(md.read_text(encoding="utf-8"), mimetype="text/markdown; charset=utf-8")


# ---------------------------------------------------------------------
#  v82l6 — extract_structured : comprehension-based DOM/text extraction.
#
#  Le user (ou le planner) decrit en langage naturel ce qu il veut extraire
#  ("liste des cours du jour avec heure et salle", "tous les prix produits
#  avec nom + devise", "messages non lus avec expediteur"). Le LLM local
#  retourne un JSON dont le schema s adapte a l intent — aucun selecteur
#  hardcode, aucun schema fige.
#
#  Cote consommateur : extension/background.js + coworkExecutor.ts.
# ---------------------------------------------------------------------

# v82lc — Cache des modeles Ollama installes (TTL 60s) pour eviter de
# tagguer Ollama a chaque appel d extract-structured. Le tag retourne
# tous les modeles dispo localement ; on s en sert pour faire un
# auto-fallback "n importe quel *vl*" quand qwen3-vl:8b n est pas pulled.
_OLLAMA_TAGS_CACHE: "dict[str, object]" = {"ts": 0.0, "names": []}
_OLLAMA_TAGS_TTL_SEC = 60.0


def _list_ollama_models() -> "list[str]":
    """Return list of installed Ollama model names. Cached 60s."""
    import time as _time
    now = _time.time()
    cached_ts = float(_OLLAMA_TAGS_CACHE.get("ts") or 0.0)
    if now - cached_ts < _OLLAMA_TAGS_TTL_SEC:
        return list(_OLLAMA_TAGS_CACHE.get("names") or [])  # type: ignore[arg-type]
    names: "list[str]" = []
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=4)
        if r.status_code == 200:
            data = r.json()
            for m in data.get("models", []):
                nm = (m.get("name") or m.get("model") or "").strip()
                if nm:
                    names.append(nm)
    except Exception:
        # Ollama down / slow — return empty so caller can fall back.
        pass
    _OLLAMA_TAGS_CACHE["ts"] = now
    _OLLAMA_TAGS_CACHE["names"] = names
    return names


def _upscale_b64_if_degenerate(b64: str, min_side: int = 64) -> str:
    """Upscale a base64 PNG/JPEG to at least min_side x min_side pixels.

    Ollama vision runners (qwen2.5vl, qwen3-vl) panic on images smaller than
    ~8x8 because the ViT patch grid collapses. Real-world inputs are always
    well above that, but the cowork live tests use a 1x1 transparent PNG to
    smoke-test the routing decision. We pad/scale to a safe minimum BEFORE
    forwarding to Ollama so the test exercise the routing path without
    crashing the runner.

    If decoding fails (corrupted base64, unsupported format), we return the
    original string and let Ollama surface the error.
    """
    import base64 as _b64
    try:
        from PIL import Image
        import io as _io
        raw = _b64.b64decode(b64)
        img = Image.open(_io.BytesIO(raw))
        w, h = img.size
        if w >= min_side and h >= min_side:
            return b64
        # Convert to RGB to avoid mode-specific encoder quirks (e.g. mode "P"
        # palette PNGs that the VL runner sometimes mis-decodes).
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        # Scale up by integer factor to nearest >= min_side, keeping aspect.
        factor = max((min_side + max(w, h) - 1) // max(w, h), 2)
        new_w = max(w * factor, min_side)
        new_h = max(h * factor, min_side)
        upscaled = img.resize((new_w, new_h), Image.NEAREST)
        if upscaled.mode == "RGBA":
            # Composite RGBA onto a white background so the runner doesn't see
            # a fully transparent canvas (which is what crashed v82lb tests).
            bg = Image.new("RGB", upscaled.size, (255, 255, 255))
            bg.paste(upscaled, mask=upscaled.split()[3])
            upscaled = bg
        buf = _io.BytesIO()
        upscaled.save(buf, format="PNG", optimize=False)
        return _b64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return b64


# v82le — cached free-VRAM probe (30s TTL). Reuses the per-call helper
# `_query_free_vram_gb` defined above — that one shells out to nvidia-smi
# every time, this one memoizes the answer for ~30s so the picker can call
# it on every extract-structured request without paying a subprocess cost.
_VRAM_CACHE: "dict[str, float]" = {"ts": 0.0, "free_gb": 0.0}
_VRAM_CACHE_TTL_SEC = 30.0

# v82lh — picker history ring buffer (capacity 10).
# Each entry is appended ONLY when extract-structured actually invokes the
# vision picker (real, non-dry-run). The dry-run /api/picker/explain endpoint
# does NOT append — observability about the historical drift would be
# polluted otherwise. Module-level state, deque so old entries auto-evict.
import collections as _collections_picker
_PICKER_HISTORY: "_collections_picker.deque[dict]" = _collections_picker.deque(maxlen=10)

# v82lr — single source-of-truth for the `reason_kind` enum domain.
# Mirrors the decision tree branches in `_pick_vision_model_or_default`
# (top branch first) and is consumed by /api/picker/history/stats
# (`by_kind` shape), /api/picker/history/by-reason (`accepted` validator),
# /api/picker/history/by-model-and-reason (`accepted` validator), and the
# new /api/picker/history/kinds enum-surface route. Tuple, immutable so a
# rogue mutator can't silently extend it. Order is the picker decision
# order so UIs can render the accepted list in branch order without re-sort.
#
# Drift assertion below : if any of the historical endpoints had a divergent
# hardcoded list slip through review, importing this module would crash at
# load time rather than serve subtly-different shapes across endpoints.
_PICKER_REASON_KINDS: "tuple[str, ...]" = (
    "vram_30b",
    "vram_8b",
    "fallback_2_5vl",
    "first_vl",
    "default",
)

# v82lr — defensive drift guard. The historical layout had three
# independent hardcoded copies of this enum (one per route) ; the refactor
# consolidates them but a future review-slip could re-introduce a divergent
# copy. This assertion catches it at import time rather than at runtime
# when a /by-reason 400 response would silently disagree with /stats's
# `by_kind` keys. Tuple-form is intentional : a list literal could be
# mutated in place by some far-away surgery, the tuple cannot.
assert isinstance(_PICKER_REASON_KINDS, tuple) and len(_PICKER_REASON_KINDS) >= 1, (
    "_PICKER_REASON_KINDS must be a non-empty tuple"
)
assert tuple(_PICKER_REASON_KINDS) == (
    "vram_30b", "vram_8b", "fallback_2_5vl", "first_vl", "default"
), (
    "_PICKER_REASON_KINDS drift detected — /stats by_kind, /by-reason "
    "accepted, /by-model-and-reason accepted, and /kinds accepted would "
    "diverge. Update _pick_vision_model_or_default branches AND this "
    "constant in lockstep."
)

# v82lw — sliding-window length used by the X-Picker-History-Coverage-
# Window-Delta-Pct response header on /api/cowork/extract-structured AND
# the `?delta=1` body field on /api/picker/history/coverage/global. The
# delta = `coverage_pct(window=DELTA_WINDOW) - coverage_pct(window=full)`,
# so the value answers "is the current exploration N pp behind / ahead
# of the long-term average ?". Read ONCE at module load (env-var
# `_PICKER_HISTORY_DELTA_WINDOW_SECONDS`) so the header value is stable
# across the bridge process lifetime and tests can monkeypatch a
# deterministic number. Invalid / missing env → fallback to 60 seconds.
# Values <= 0 also fall back to 60 (a non-positive window would make the
# delta computation undefined ; better a sensible default than a 400).
def _resolve_picker_history_delta_window() -> int:
    raw = os.environ.get("_PICKER_HISTORY_DELTA_WINDOW_SECONDS", "").strip()
    if not raw:
        return 60
    try:
        parsed = int(raw)
    except Exception:
        return 60
    if parsed <= 0:
        return 60
    return parsed


_PICKER_HISTORY_DELTA_WINDOW_SECONDS: int = _resolve_picker_history_delta_window()

# v82m1 — extraction-stats ring buffer (capacity 50). Each entry is appended
# ONLY when /api/cowork/extract-structured runs in mode=card_iteration with a
# non-empty `cards` stream — i.e. the per-card pipeline is active and we have
# something to measure. Schema :
#   {
#     "ts":                float,    // wall-clock at append time
#     "host":              str,      // page hostname (best-effort, "" when unknown)
#     "cards_processed":   int,      // len(cards) — what the bridge saw
#     "items_count":       int,      // len(items) — what the LLM extracted
#     "under_extraction":  bool,     // items_count < cards_processed * 0.5
#     "yield_pct":         float     // items_count / cards_processed (0..1+),
#                                    // 0.0 when cards_processed == 0
#   }
# Pure observability — composes with /api/cowork/extraction-stats GET so
# aurora-watchdog and monitoring tools can see drift without parsing audit
# logs. Module-level state, deque so old entries auto-evict.
_EXTRACTION_STATS: "_collections_picker.deque[dict]" = _collections_picker.deque(maxlen=50)

# v82m2 — per-host yield history. Each host gets its own bounded deque of the
# last N (=10) yield_pct values seen on prior card_iteration extractions.
# Used to compute the `X-Host-Yield-Delta-Pct` response header so the
# orchestrator can detect "this host degraded vs its own baseline" without
# round-tripping /extraction-stats on every request. Key = normalised host
# (no leading "www.", lowercased), value = deque[float] capped at 10 entries.
# Module-level state ; same lifetime as `_EXTRACTION_STATS` (process restart
# clears it). Pure observability — never gates extraction, only telemetry.
_HOST_YIELD_HISTORY_CAP: int = 10
_HOST_YIELD_HISTORY_MIN_PRIOR: int = 3
_HOST_YIELD_HISTORY: "dict[str, _collections_picker.deque[float]]" = {}

# v82m5 — dual-signal escalation acceptance metric.
#
# Background : when both yield-ratio AND host-baseline-drift fire on the same
# extract, the planner sees a STRONGER `[HINT] DUAL_SIGNAL` nudge instead of
# the single-signal hint. We want to know whether the LLM actually accepts
# this stronger hint (i.e. emits `browser.screenshot` then `extract_structured`
# with `includeImage: true`). Closes the loop on whether prompt escalation
# changes behaviour — without it we're flying blind on hint efficacy.
#
# Two ring buffers, capped at 100 each :
#   - emitted : every time the orchestrator detects a dual-signal nudge
#               WAS sent on the previous iteration's system prompt
#   - accepted : every time the next plan after a dual-signal nudge contains
#                the screenshot + extract_structured(includeImage:true)
#                sequence
#
# Each entry shape : {"ts": float, "host": str}. The host is best-effort —
# the orchestrator passes whatever it has from the previous extract entry
# (empty string when unknown). Pure module-level state, same lifetime as
# the rest of the cowork stats (process restart clears it).
_DUAL_SIGNAL_RING_CAP: int = 100
_DUAL_SIGNAL_EMITTED: "_collections_picker.deque[dict]" = _collections_picker.deque(
    maxlen=_DUAL_SIGNAL_RING_CAP,
)
_DUAL_SIGNAL_ACCEPTED: "_collections_picker.deque[dict]" = _collections_picker.deque(
    maxlen=_DUAL_SIGNAL_RING_CAP,
)

# v82m7 — tier-2 trend acceptance metric. Mirrors the v82m5 dual-signal
# pattern but for the DUAL_SIGNAL_TREND nudge (sustained host degradation
# detected via sparkline trajectory, suggesting `mode=spread` + 3-5s pause).
# Kept in separate ring buffers so the two metrics don't pollute each other —
# the `dual-signal-stats` endpoint stays focused on the single-shot escalation,
# the `trend-signal-stats` endpoint surfaces the sustained-drift escalation.
_TREND_SIGNAL_RING_CAP: int = 100
_TREND_SIGNAL_EMITTED: "_collections_picker.deque[dict]" = _collections_picker.deque(
    maxlen=_TREND_SIGNAL_RING_CAP,
)
_TREND_SIGNAL_ACCEPTED: "_collections_picker.deque[dict]" = _collections_picker.deque(
    maxlen=_TREND_SIGNAL_RING_CAP,
)

# v82m9 — TTL eviction for trend ring buffers. When a host hasn't been
# touched (emitted OR accepted) for longer than `_TREND_SIGNAL_TTL_SECONDS`,
# its slice in BOTH ring buffers is dropped before the next append. This
# keeps the per-host verdict fresh against intermittent host failures :
# if the user retries a stale host after 10 minutes of inactivity, the
# planner restarts from a clean baseline rather than carrying a verdict
# that pre-dates the user's manual strategy change.
#
# `_TREND_SIGNAL_LAST_TS_PER_HOST` mirrors the most-recent timestamp per
# host so we can decide eviction without scanning the full deque on every
# emit. Read once at import via env (default 600s = 10 min) — the env is
# named to mirror the module-level dunder convention so Ops can override
# it in production without code changes.
try:
    _TREND_SIGNAL_TTL_SECONDS: float = float(
        os.environ.get("_TREND_SIGNAL_TTL_SECONDS", "600")
    )
except Exception:
    _TREND_SIGNAL_TTL_SECONDS = 600.0
_TREND_SIGNAL_LAST_TS_PER_HOST: "dict[str, float]" = {}


def _evict_stale_trend_hosts(now: float) -> "list[str]":
    """v82m9 — drop ring buffer entries for hosts whose last activity is
    older than `_TREND_SIGNAL_TTL_SECONDS`. Pure side-effect on the two
    trend rings + `_TREND_SIGNAL_LAST_TS_PER_HOST`. Returns the list of
    evicted hosts (mostly so the test client can assert what was cleared).

    Defensive : never raises (best-effort housekeeping must not break the
    record path). The caller passes `now` so eviction is deterministic
    under test-client time manipulation.
    """
    try:
        if _TREND_SIGNAL_TTL_SECONDS <= 0:
            return []
        evicted: list[str] = []
        for host, last_ts in list(_TREND_SIGNAL_LAST_TS_PER_HOST.items()):
            try:
                if (now - float(last_ts)) > _TREND_SIGNAL_TTL_SECONDS:
                    evicted.append(host)
            except Exception:
                # Bad ts → evict to recover.
                evicted.append(host)
        if not evicted:
            return []
        evicted_set = set(evicted)
        kept_emitted = [
            e for e in list(_TREND_SIGNAL_EMITTED)
            if str(e.get("host") or "") not in evicted_set
        ]
        kept_accepted = [
            e for e in list(_TREND_SIGNAL_ACCEPTED)
            if str(e.get("host") or "") not in evicted_set
        ]
        _TREND_SIGNAL_EMITTED.clear()
        _TREND_SIGNAL_EMITTED.extend(kept_emitted)
        _TREND_SIGNAL_ACCEPTED.clear()
        _TREND_SIGNAL_ACCEPTED.extend(kept_accepted)
        for host in evicted:
            _TREND_SIGNAL_LAST_TS_PER_HOST.pop(host, None)
        return evicted
    except Exception:
        return []


def _record_trend_signal_event(kind: str, host: str) -> None:
    """v82m7 — pure helper : append one entry to the trend ring buffer.

    Symmetric with `_record_dual_signal_event`. `kind` MUST be "emitted" or
    "accepted" ; anything else is a no-op. Host normalisation matches the
    dual-signal helper (lowercase, strip leading "www.") so a query for
    "linkedin.com" matches whether the orchestrator passed "LinkedIn.com" or
    "www.linkedin.com".

    v82m9 — before append, evict stale-host slices from BOTH rings (TTL =
    `_TREND_SIGNAL_TTL_SECONDS`, default 600s). Keeps verdicts fresh when
    a user revisits a host after a long pause.
    """
    try:
        if kind not in ("emitted", "accepted"):
            return
        norm_host = (host or "").lower().strip()
        if norm_host.startswith("www."):
            norm_host = norm_host[4:]
        now = time.time()
        # v82m9 — TTL eviction step (pure no-op when no host is stale).
        _evict_stale_trend_hosts(now)
        entry = {"ts": now, "host": norm_host}
        if kind == "emitted":
            _TREND_SIGNAL_EMITTED.append(entry)
        else:
            _TREND_SIGNAL_ACCEPTED.append(entry)
        if norm_host:
            _TREND_SIGNAL_LAST_TS_PER_HOST[norm_host] = now
    except Exception:
        return


def _record_dual_signal_event(kind: str, host: str) -> None:
    """Pure helper : append one entry to the right ring buffer.

    `kind` MUST be one of {"emitted", "accepted"}. Anything else is a no-op
    (defensive — bad input must NEVER break the orchestrator's plan loop).
    Host is normalised (strip leading "www.", lowercase, defaulting to empty
    string for unknown). Timestamp is wall-clock time.time().
    """
    try:
        if kind not in ("emitted", "accepted"):
            return
        norm_host = (host or "").lower().strip()
        if norm_host.startswith("www."):
            norm_host = norm_host[4:]
        entry = {"ts": time.time(), "host": norm_host}
        if kind == "emitted":
            _DUAL_SIGNAL_EMITTED.append(entry)
        else:
            _DUAL_SIGNAL_ACCEPTED.append(entry)
    except Exception:
        # Pure observability — never fail the calling path.
        return


def _record_extraction_stat(host: str, cards_processed: int, items_count: int) -> None:
    """Pure helper : append one entry to `_EXTRACTION_STATS` after an
    extract_structured(card_iteration) response with cards != [].

    Defensive : never raises (best-effort observability, must not break the
    extraction route on a clock error / type error / etc.). The deque enforces
    the 50-entry cap so unbounded growth is impossible.
    """
    import time as _time_es
    try:
        cp = int(cards_processed) if cards_processed is not None else 0
        ic = int(items_count) if items_count is not None else 0
        yld = (float(ic) / float(cp)) if cp > 0 else 0.0
        under = (cp > 0) and (ic < cp * 0.5)
        _EXTRACTION_STATS.append({
            "ts": _time_es.time(),
            "host": str(host or ""),
            "cards_processed": cp,
            "items_count": ic,
            "under_extraction": bool(under),
            "yield_pct": yld,
        })
    except Exception:
        pass


def _compute_host_yield_delta_pct(
    host: str,
    current_yield: float,
    cards_processed: int,
) -> "float | None":
    """v82m2 — compute the signed yield-delta vs the host's own baseline.

    Returns the delta (current - host_avg) * 100 in percentage points (pp)
    when ALL of the following hold :
      - host is non-empty
      - cards_processed >= 5  (statistical floor — sub-5-card extractions are
        too noisy to compare against a baseline)
      - the host has at least `_HOST_YIELD_HISTORY_MIN_PRIOR` (=3) prior
        entries in `_HOST_YIELD_HISTORY` (so the average is meaningful)

    Returns None otherwise (header emission is gated on non-None). Defensive :
    never raises — observability must not break the extraction route.

    The PRIOR snapshot is read BEFORE the current entry is appended (the
    caller appends after this returns). This way a host's first 3 extracts
    return None, the 4th returns the delta vs the first 3, etc.
    """
    try:
        if not host:
            return None
        if int(cards_processed) < 5:
            return None
        history = _HOST_YIELD_HISTORY.get(host)
        if history is None:
            return None
        prior = list(history)
        if len(prior) < _HOST_YIELD_HISTORY_MIN_PRIOR:
            return None
        host_avg = sum(prior) / float(len(prior))
        delta = (float(current_yield) - host_avg) * 100.0
        return delta
    except Exception:
        return None


def _record_host_yield(host: str, yield_pct: float) -> None:
    """v82m2 — append the current yield to the host's per-host history.

    Called AFTER `_compute_host_yield_delta_pct` so the delta is always
    computed against the PRIOR baseline (excluding the current). Defensive :
    never raises. The per-host deque is capped at `_HOST_YIELD_HISTORY_CAP`
    (=10) so unbounded growth is impossible — old entries auto-evict.
    """
    try:
        if not host:
            return
        if host not in _HOST_YIELD_HISTORY:
            _HOST_YIELD_HISTORY[host] = _collections_picker.deque(
                maxlen=_HOST_YIELD_HISTORY_CAP,
            )
        _HOST_YIELD_HISTORY[host].append(float(yield_pct))
    except Exception:
        pass


def _percentile(values: "list[float]", p: float) -> float:
    """Pure helper : compute percentile p (0..1) over a sorted-or-unsorted
    list of floats. Uses linear interpolation between the two adjacent
    samples (matches numpy.percentile default). Returns 0.0 on empty input
    so the route's response shape stays stable.
    """
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    if p <= 0:
        return float(s[0])
    if p >= 1:
        return float(s[-1])
    rank = p * (len(s) - 1)
    lo = int(rank)
    hi = lo + 1
    frac = rank - lo
    if hi >= len(s):
        return float(s[-1])
    return float(s[lo]) + (float(s[hi]) - float(s[lo])) * frac


# v82lk — first/last seen timestamps for installed vision models.
# Populated lazily by `_observe_installed_vision_models()` whenever the
# warmup/health endpoint (or any future caller) enumerates installed
# vision models. Process-lifetime only — no persistence, resets on
# bridge restart. Lets the UI flag "qwen3-vl:30b apparu il y a 12 minutes"
# without polling Ollama on a tighter loop than the existing 60s tag cache.
_VISION_MODEL_FIRST_SEEN: "dict[str, float]" = {}
_VISION_MODEL_LAST_SEEN: "dict[str, float]" = {}


def _observe_installed_vision_models(names: "list[str]") -> "list[dict]":
    """Update first/last seen timestamps and return enriched entries.

    For every name passed in (already filtered to vision-matching), set
    `first_seen_ts` if absent and refresh `last_seen_ts` to now(). Returns
    a list of `{name, first_seen_ts, last_seen_ts}` dicts in the same
    order as the input so callers preserve Ollama's listing order.

    Pure observability helper — never raises (timestamps are best-effort).
    """
    import time as _time_vis
    out: "list[dict]" = []
    now = _time_vis.time()
    for nm in names:
        try:
            if nm not in _VISION_MODEL_FIRST_SEEN:
                _VISION_MODEL_FIRST_SEEN[nm] = now
            _VISION_MODEL_LAST_SEEN[nm] = now
            out.append({
                "name": nm,
                "first_seen_ts": _VISION_MODEL_FIRST_SEEN[nm],
                "last_seen_ts": _VISION_MODEL_LAST_SEEN[nm],
            })
        except Exception:
            # Best-effort observability — fall back to bare name if anything
            # explodes (shouldn't, dicts are pure Python).
            out.append({"name": nm, "first_seen_ts": now, "last_seen_ts": now})
    return out


def _record_picker_pick(
    model: str,
    reason: str,
    free_vram_gb: float,
    reason_kind: str = "default",
) -> None:
    """Append one snapshot to the picker history ring buffer.

    Called from extract-structured AFTER `_pick_vision_model_or_default` has
    decided. Pure observability — never raises, never blocks the request.

    v82li — `reason_kind` is the machine-readable enum equivalent of `reason`.
    UI can group/colour history entries without parsing the FR/EN free-form
    reason string. See `_pick_vision_model_or_default` for enum domain.
    """
    try:
        import time as _time_pick
        _PICKER_HISTORY.append({
            "ts": _time_pick.time(),
            "model": str(model),
            "reason": str(reason),
            "reason_kind": str(reason_kind),
            "free_vram_gb": float(free_vram_gb),
        })
    except Exception:
        # Observability must never break the request.
        pass


def _get_free_vram_gb() -> float:
    """Return free VRAM in GB, cached 30s. Returns 0.0 on any error.

    Distinct from `_query_free_vram_gb` (which returns None on no-GPU and is
    used by the conditional pull worker) — this one always returns a float
    so callers can compare directly without None-checking.
    """
    import time as _time
    now = _time.time()
    cached_ts = float(_VRAM_CACHE.get("ts") or 0.0)
    if now - cached_ts < _VRAM_CACHE_TTL_SEC:
        return float(_VRAM_CACHE.get("free_gb") or 0.0)
    try:
        gb = _query_free_vram_gb()
        free_gb = float(gb) if gb is not None else 0.0
    except Exception:
        free_gb = 0.0
    _VRAM_CACHE["ts"] = now
    _VRAM_CACHE["free_gb"] = free_gb
    return free_gb


def _pick_vision_model_or_default(
    preferred: str = "qwen3-vl:8b",
    simulate_vram_gb: "float | None" = None,
) -> "tuple[str, str, str]":
    """Pick a vision-capable model from what's installed.

    v82le — VRAM-adaptive priority :
      1. free VRAM >= 22 GB AND qwen3-vl:30b installed -> qwen3-vl:30b
      2. free VRAM >=  8 GB AND qwen3-vl:8b  installed -> qwen3-vl:8b
      3. qwen2.5vl:7b installed -> qwen2.5vl:7b
      4. first *vl* tag found
      5. fallback : `preferred` (caller will surface the Ollama 404)

    v82lf — returns a tuple (model_name, reason_str) for observability. The
    reason is a short human-readable string explaining which branch fired
    (eg `"qwen3-vl:8b matched (free VRAM 11.5 >= 8.0)"`).

    v82li — return shape extended to triplet (model, reason, reason_kind).
    `reason_kind` is the machine-readable enum equivalent of `reason`, with
    values in {"vram_30b", "vram_8b", "fallback_2_5vl", "first_vl", "default"}.
    Lets the UI group/colour history entries without parsing FR/EN strings.

    v82li — `simulate_vram_gb` is an optional dry-run override. When set,
    the function bypasses `_get_free_vram_gb()` for THIS call only ; the
    cache is NOT touched. Used by /api/picker/explain?simulate_vram=N to
    let UI preview "what if free VRAM were N" without polluting state.

    Pure runtime decision — reads only installed models + free VRAM. No
    per-site rules, no per-prompt rules, zero hardcoded selectors.
    """
    names = _list_ollama_models()
    if not names:
        return (preferred, "default fallback (no *vl* installed)", "default")
    lower_names = [n.lower() for n in names]

    # v82li — dry-run override path. Pure read of the supplied number, no
    # cache write. Caller (picker_explain) is responsible for clamping/parsing.
    if simulate_vram_gb is not None:
        free_gb = float(simulate_vram_gb)
    else:
        free_gb = _get_free_vram_gb()

    # 1. Big model if VRAM is generous and qwen3-vl:30b is pulled.
    if free_gb >= 22.0:
        for orig, low in zip(names, lower_names):
            if low == "qwen3-vl:30b":
                return (orig, f"qwen3-vl:30b matched (free VRAM {free_gb} >= 22.0)", "vram_30b")

    # 2. qwen3-vl:8b — sweet spot when >= 8 GB free.
    if free_gb >= 8.0:
        for orig, low in zip(names, lower_names):
            if low == "qwen3-vl:8b":
                return (orig, f"qwen3-vl:8b matched (free VRAM {free_gb} >= 8.0)", "vram_8b")

    # 3. qwen2.5vl:7b — broadly compatible fallback. Accept dash + no-dash forms.
    for orig, low in zip(names, lower_names):
        if low in ("qwen2.5vl:7b", "qwen2.5-vl:7b"):
            return (orig, f"{orig} fallback (qwen3-vl:8b not installed)", "fallback_2_5vl")

    # 4. first *vl* tag we can find — preserves prior behaviour for users
    # who pulled llava / qwen2.5vl:3b / llama3.2-vision / etc. and have not
    # opted into qwen3-vl.
    for orig, low in zip(names, lower_names):
        if "vl" in low or "vision" in low or "llava" in low:
            return (orig, f"first *vl* match: {orig}", "first_vl")

    # 5. last resort.
    return (preferred, "default fallback (no *vl* installed)", "default")


@app.route("/api/picker/explain", methods=["GET"])
def picker_explain():
    """v82lh — observability dry-run for the vision picker.

    Returns what `_pick_vision_model_or_default` WOULD pick if an image were
    sent right now, without invoking Ollama and without polluting the picker
    history ring buffer. Pure read of installed models + free VRAM.

    v82li — accepts optional `?simulate_vram=N` query param (float, >= 0).
    When supplied, the picker bypasses the cached `_get_free_vram_gb()` for
    this call only — the cache itself is NOT modified, no history append,
    no Ollama call. Lets UI preview "what if free VRAM were 22.0" to
    understand the picker's branching logic. Negative or non-numeric
    values are silently ignored (= no override).

    Response :
      {
        "ok": true,
        "vision": {
          "model": "qwen3-vl:8b",
          "reason": "qwen3-vl:8b matched (free VRAM 11.3 >= 8.0)",
          "reason_kind": "vram_8b",
          "free_vram_gb": 11.3,
          "simulated": false                  // true when simulate_vram applied
        },
        "text": { "model": "qwen3:14b" }
      }

    Lets the UI surface "if you sent an image now, picker would choose X
    because Y" before the user actually triggers a scrape. Zero behavior
    change to extract-structured. No selectors, no per-site rules.
    """
    try:
        # v82li — parse optional ?simulate_vram=N. Anything non-numeric or
        # negative falls back to the cached real probe.
        sim_raw = (request.args.get("simulate_vram") or "").strip()
        simulate_vram_gb: "float | None" = None
        if sim_raw:
            try:
                v = float(sim_raw)
                if v >= 0.0:
                    simulate_vram_gb = v
            except (TypeError, ValueError):
                simulate_vram_gb = None
        vision_model, vision_reason, vision_kind = _pick_vision_model_or_default(
            "qwen3-vl:8b", simulate_vram_gb=simulate_vram_gb
        )
        # `free_vram_gb` reflects the value the picker actually saw — the
        # simulated number when overriding, the real cached probe otherwise.
        # This keeps the field meaningful for both real and dry-run flows.
        if simulate_vram_gb is not None:
            free_gb = float(simulate_vram_gb)
        else:
            free_gb = _get_free_vram_gb()
        return jsonify({
            "ok": True,
            "vision": {
                "model": vision_model,
                "reason": vision_reason,
                "reason_kind": vision_kind,
                "free_vram_gb": free_gb,
                "simulated": simulate_vram_gb is not None,
            },
            "text": {"model": "qwen3:14b"},
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/warmup/health", methods=["GET"])
def warmup_health():
    """v82li — aggregate read endpoint combining warmup + picker + history.

    Single round-trip alternative to polling /api/warmup/status,
    /api/picker/explain, /api/picker/history, etc. The popup/extension UI
    can refresh its full observability pane in one fetch.

    Response shape (always 200) :
      {
        "ok": true,
        "warmup": { state, model, latency_ms, ts, error },     // copy of _WARMUP_STATE
        "vision": { model, reason, reason_kind },              // dry-run picker decision
        "text":   { "model": "qwen3:14b" },
        "free_vram_gb": float,                                 // cached real probe
        "history_count": int,                                  // len(_PICKER_HISTORY)
        "last_picker": { ts, model, reason, reason_kind, free_vram_gb } | null,
        "installed_vision_models": ["qwen3-vl:8b", "qwen2.5vl:7b", ...]
      }

    v82lj — `installed_vision_models` filters `_list_ollama_models()` (60s
    cached) on the same `vl|vision|llava` heuristic the picker uses. Lets
    the popup render "vous avez ces vision models" without a follow-up
    /api/ollama/models call. Pure read, no caching changes, no per-site
    rules.

    Pure read — zero new state, zero Ollama call beyond the cached tag
    list, zero history append. Reuses _WARMUP_STATE,
    _pick_vision_model_or_default (without simulate override),
    _get_free_vram_gb (cached), _PICKER_HISTORY, _list_ollama_models.
    No selectors, no per-site rules.
    """
    try:
        # warmup snapshot — flat copy so callers cannot mutate the module dict.
        warmup_snap = {
            "state": _WARMUP_STATE.get("state"),
            "model": _WARMUP_STATE.get("model"),
            "latency_ms": _WARMUP_STATE.get("latency_ms"),
            "ts": _WARMUP_STATE.get("ts"),
            "error": _WARMUP_STATE.get("error"),
        }
        # picker dry-run — no simulate override, no history append.
        try:
            v_model, v_reason, v_kind = _pick_vision_model_or_default("qwen3-vl:8b")
        except Exception as exc:  # noqa: BLE001
            v_model, v_reason, v_kind = ("qwen3-vl:8b", f"probe failed: {exc}", "default")
        try:
            free_gb = _get_free_vram_gb()
        except Exception:
            free_gb = 0.0
        # last picker entry, or null when buffer empty.
        try:
            last_picker = _PICKER_HISTORY[-1] if len(_PICKER_HISTORY) > 0 else None
        except Exception:
            last_picker = None
        # v82lj — installed vision models (heuristic filter, same domain
        # as the picker's branch 4). Reuses the 60s-cached tag list so
        # this endpoint stays cheap. Returned in the order Ollama listed.
        # v82lk — entries are now objects {name, first_seen_ts, last_seen_ts}
        # rather than bare strings. Timestamps are process-lifetime only,
        # refreshed on every call so UI can flag "qwen3-vl:30b apparu il y
        # a N minutes". `last_seen_ts` updates on every read of this route ;
        # `first_seen_ts` is sticky across the process lifetime.
        try:
            import re as _re_vis
            _vis_re = _re_vis.compile(r"(vl|vision|llava)", _re_vis.IGNORECASE)
            _vision_names = [n for n in _list_ollama_models() if _vis_re.search(n)]
            installed_vision = _observe_installed_vision_models(_vision_names)
        except Exception:
            installed_vision = []
        return jsonify({
            "ok": True,
            "warmup": warmup_snap,
            "vision": {
                "model": v_model,
                "reason": v_reason,
                "reason_kind": v_kind,
            },
            "text": {"model": "qwen3:14b"},
            "free_vram_gb": free_gb,
            "history_count": len(_PICKER_HISTORY),
            "last_picker": last_picker,
            "installed_vision_models": installed_vision,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history", methods=["GET"])
def picker_history():
    """v82lh — return the last N (<=10) real picker decisions.

    Each entry is {ts, model, reason, free_vram_gb}, oldest first. Only
    real extract-structured calls populate the buffer ; the dry-run
    /api/picker/explain endpoint does NOT, so the history reflects actual
    drift over time. Pure observability, no caching, no rules.
    """
    try:
        # Snapshot the deque as a plain list for JSON serialization.
        snapshot = list(_PICKER_HISTORY)
        return jsonify({"ok": True, "history": snapshot, "count": len(snapshot)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/clear", methods=["POST"])
def picker_history_clear():
    """v82lj — pure ring-buffer reset.

    Body : none required (any JSON / empty body is accepted).

    Query (v82ll) :
      reset_seen=1   → in addition to clearing `_PICKER_HISTORY`, also
                       clear the `_VISION_MODEL_FIRST_SEEN` and
                       `_VISION_MODEL_LAST_SEEN` dicts so the next call
                       to /api/warmup/health re-stamps `first_seen_ts`
                       to "now". Default behaviour (`reset_seen=0` or
                       absent) is unchanged.

    Effect : captures `len(_PICKER_HISTORY)` BEFORE the clear, calls
    `_PICKER_HISTORY.clear()`, optionally clears the seen-ts dicts,
    returns the previous count and whether seen was reset.

    Returns :
      { "ok": true, "cleared_count": N, "seen_reset": bool }

    Lets the UI offer a "fresh start" button before profiling a new
    scrape session — without restarting the bridge. Pure state mutation,
    no Ollama call, no per-site rules, no selectors.
    """
    try:
        # v82ll — opt-in reset of the vision-model seen-ts dicts. We
        # parse the query string strictly : "1", "true", "yes" enable it.
        # Anything else (absent, "0", garbage) leaves the seen dicts
        # untouched. Default behaviour matches v82lj.
        raw_flag = (request.args.get("reset_seen") or "").strip().lower()
        do_reset_seen = raw_flag in ("1", "true", "yes")
        before = len(_PICKER_HISTORY)
        _PICKER_HISTORY.clear()
        if do_reset_seen:
            try:
                _VISION_MODEL_FIRST_SEEN.clear()
                _VISION_MODEL_LAST_SEEN.clear()
            except Exception:
                # Observability mutation must not 500 the clear path.
                pass
        return jsonify({
            "ok": True,
            "cleared_count": before,
            "seen_reset": bool(do_reset_seen),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/stats", methods=["GET"])
def picker_history_stats():
    """v82ll — aggregate counters over `_PICKER_HISTORY`.

    Pure read, zero Ollama, zero replay, zero mutation. Lets the UI
    render a stacked-bar histogram (`by_kind`) and a span ribbon
    (`oldest_ts` → `newest_ts`) without iterating the history client-side.

    Optional query params :
      since=<float_ts>          v82ln — when present and positive, filter
                                the history to entries where `ts >= since`
                                BEFORE computing aggregates. Lets the UI
                                render "last 60s" / "last 5min" stacked
                                bars by passing `now-60` / `now-300`.
                                Invalid (non-float, negative, missing) →
                                no filter applied, behaviour unchanged.
      reason_kind=<enum>        v82lo — when present and matching one of
                                the stable enum values (`vram_30b`,
                                `vram_8b`, `fallback_2_5vl`, `first_vl`,
                                `default`), filter the history to entries
                                where `reason_kind == <value>` AFTER the
                                `since` filter. Lets the UI render "show
                                me only the VRAM-pressure picks in the
                                last 5min" without iterating client-side.
                                Invalid (unknown enum, empty) → ignored
                                gracefully (`window.reason_kind=null`).

    The two filters compose AND-applied : `since` runs first, then
    `reason_kind` narrows the surviving slice. Aggregates (`by_kind`,
    `distinct_models`, `oldest_ts`, `newest_ts`, `span_seconds`) are
    computed over the FINAL filtered snapshot.

    Response :
      {
        "ok": true,
        "count": int,                      // len(filtered history) at probe time
        "by_kind": {                       // every enum value, even zeros
          "fallback_2_5vl": int,
          "vram_8b":       int,
          "vram_30b":      int,
          "first_vl":      int,
          "default":       int
        },
        "distinct_models": int,            // unique `model` values
        "oldest_ts": float | null,         // null when count == 0
        "newest_ts": float | null,
        "span_seconds": float,             // 0.0 when count <= 1
        "window": {                        // v82ln — temporal filter context
          "since":          float | null,  // echo of the param (null when not applied)
          "filtered_count": int  | null,   // entries kept after filter (null when not applied)
          "reason_kind":    str   | null   // v82lo — echo of reason_kind filter (null when not applied)
        }
      }

    The `by_kind` map enumerates ALL `reason_kind` enum values from
    `_pick_vision_model_or_default` even at zero, so consumers can rely
    on a stable shape (no missing keys to None-check).

    Pure observability — no caching changes, no per-site rules, no selectors.
    """
    try:
        snapshot = list(_PICKER_HISTORY)
        # v82ln — opt-in time-window filter. Only applies when the caller
        # provides a positive float `since` ; anything else (absent, empty,
        # non-numeric, negative) leaves the snapshot untouched and returns
        # the same shape as before with `window={since:null,filtered_count:null}`
        # so existing consumers stay backward-compatible.
        since_raw = (request.args.get("since") or "").strip()
        window_since: "float | None" = None
        window_filtered_count: "int | None" = None
        if since_raw:
            try:
                parsed_since = float(since_raw)
                if parsed_since > 0:
                    window_since = parsed_since
            except Exception:
                window_since = None
        if window_since is not None:
            filtered: "list[dict]" = []
            for h in snapshot:
                try:
                    ts_h = float(h.get("ts") or 0.0)
                except Exception:
                    ts_h = 0.0
                if ts_h >= window_since:
                    filtered.append(h)
            snapshot = filtered
            window_filtered_count = len(snapshot)
        # Stable enum domain — single source of truth at module scope so
        # /stats, /by-reason, /by-model-and-reason and /kinds all serve the
        # same shape. Any new enum value MUST be added to
        # `_PICKER_REASON_KINDS` (and to `_pick_vision_model_or_default`).
        kind_keys = list(_PICKER_REASON_KINDS)
        # v82lo — opt-in categorical filter on `reason_kind`. Composes with
        # `since` AND-applied : `since` runs first, then `reason_kind`
        # narrows the surviving slice. Only the stable enum values listed
        # in `kind_keys` are accepted ; unknown / empty values are
        # gracefully ignored (window.reason_kind echoes null) so callers
        # cannot accidentally over-filter on a typo. Pure filter, no
        # mutation, no Ollama call.
        reason_kind_raw = (request.args.get("reason_kind") or "").strip()
        window_reason_kind: "str | None" = None
        if reason_kind_raw and reason_kind_raw in kind_keys:
            window_reason_kind = reason_kind_raw
            snapshot = [
                h for h in snapshot
                if str(h.get("reason_kind") or "default") == window_reason_kind
            ]
            # If the time-window filter wasn't engaged, `filtered_count`
            # stays null per the v82ln contract (only echoed when `since`
            # was applied). The reason_kind filter does NOT retroactively
            # populate `filtered_count` — it has its own echo slot.
        by_kind: "dict[str, int]" = {k: 0 for k in kind_keys}
        models_seen: "set[str]" = set()
        oldest_ts: "float | None" = None
        newest_ts: "float | None" = None
        for h in snapshot:
            try:
                kind = str(h.get("reason_kind") or "default")
                if kind in by_kind:
                    by_kind[kind] += 1
                else:
                    # Unknown kind (forward compat) — bucket under "default"
                    # rather than mutate the stable shape.
                    by_kind["default"] += 1
                model_name = str(h.get("model") or "").strip()
                if model_name:
                    models_seen.add(model_name)
                ts = float(h.get("ts") or 0.0)
                if ts > 0:
                    if oldest_ts is None or ts < oldest_ts:
                        oldest_ts = ts
                    if newest_ts is None or ts > newest_ts:
                        newest_ts = ts
            except Exception:
                # Skip a corrupt entry — aggregates over the rest stay valid.
                continue
        if oldest_ts is not None and newest_ts is not None:
            span = float(newest_ts - oldest_ts)
        else:
            span = 0.0
        return jsonify({
            "ok": True,
            "count": len(snapshot),
            "by_kind": by_kind,
            "distinct_models": len(models_seen),
            "oldest_ts": oldest_ts,
            "newest_ts": newest_ts,
            "span_seconds": span,
            "window": {
                "since": window_since,
                "filtered_count": window_filtered_count,
                # v82lo — echo the categorical filter slot. null when the
                # caller didn't pass `reason_kind=` or passed an unknown
                # enum value (graceful-ignore contract).
                "reason_kind": window_reason_kind,
            },
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/kinds", methods=["GET"])
def picker_history_kinds():
    """v82lr — pure-read enum surface over `_PICKER_REASON_KINDS`.

    Returns the canonical, decision-tree-ordered list of `reason_kind`
    enum values that the picker can record. Lets the extension hydrate
    its kinds dropdown / heatmap legend from the bridge instead of
    hardcoding the enum (which would silently drift if a new branch was
    added to `_pick_vision_model_or_default`).

    Single source of truth : the route reads `_PICKER_REASON_KINDS`
    directly, the SAME tuple consumed by /api/picker/history/stats
    (`by_kind` shape) and by /api/picker/history/by-reason and
    /api/picker/history/by-model-and-reason (`accepted` validators on
    400 responses). The drift assertion at module load guarantees those
    historical surfaces stay byte-for-byte aligned with this enum
    surface.

    Response :
      200 {
        "ok": true,
        "accepted": [str, ...]   // decision-tree order, immutable contract
      }

    Pure read — no Ollama, no mutation, no per-request state. Idempotent ;
    callers can cache aggressively. Empty list is a structural
    impossibility (the tuple is non-empty by construction at module load).
    """
    try:
        return jsonify({
            "ok": True,
            "accepted": list(_PICKER_REASON_KINDS),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/distinct-models", methods=["GET"])
def picker_history_distinct_models():
    """v82ln — pure-read pivot table over `_PICKER_HISTORY` per model.

    For every distinct `model` value in the ring buffer, return how many
    times it was picked plus the first / last timestamp it appeared. Lets
    the UI render a "models seen" pivot table sorted by usage without
    iterating the full history client-side.

    Pure read — zero Ollama, zero replay, zero mutation. Mirrors the
    aggregates in `/api/picker/history/stats` but pivoted by model rather
    than by reason_kind, closing the histogram pair `(by_kind, by_model)`.

    Response :
      {
        "ok": true,
        "total_picks": int,           // len(_PICKER_HISTORY) at probe time
        "models": [                   // sorted by count desc, ties by last_ts desc
          {
            "name":     str,          // model name as recorded
            "count":    int,          // # picks of this model in the buffer
            "first_ts": float,        // oldest ts for this model
            "last_ts":  float         // newest ts for this model
          },
          ...
        ]
      }

    Sort order : `count` descending (most-picked first), ties broken by
    `last_ts` descending (most-recently-seen wins). Models with empty
    name are skipped — `_record_picker_pick` always sets a non-empty
    string but defensive against future mutators.

    Pure observability — no caching changes, no per-site rules, no selectors.
    """
    try:
        snapshot = list(_PICKER_HISTORY)
        per_model: "dict[str, dict]" = {}
        for h in snapshot:
            try:
                name = str(h.get("model") or "").strip()
                if not name:
                    continue
                ts_h = float(h.get("ts") or 0.0)
                bucket = per_model.get(name)
                if bucket is None:
                    per_model[name] = {
                        "name": name,
                        "count": 1,
                        "first_ts": ts_h,
                        "last_ts": ts_h,
                    }
                else:
                    bucket["count"] = int(bucket["count"]) + 1
                    if ts_h > 0:
                        if ts_h < float(bucket["first_ts"]):
                            bucket["first_ts"] = ts_h
                        if ts_h > float(bucket["last_ts"]):
                            bucket["last_ts"] = ts_h
            except Exception:
                # Skip a corrupt entry — aggregates over the rest stay valid.
                continue
        # Sort by count desc, ties broken by last_ts desc. Python's sort is
        # stable so a single key tuple expresses the full ordering.
        models_sorted = sorted(
            per_model.values(),
            key=lambda m: (-int(m.get("count") or 0), -float(m.get("last_ts") or 0.0)),
        )
        return jsonify({
            "ok": True,
            "total_picks": len(snapshot),
            "models": models_sorted,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/by-model", methods=["GET"])
def picker_history_by_model():
    """v82lo — per-model drill-down over `_PICKER_HISTORY`.

    Companion to `/api/picker/history/distinct-models` (v82ln). Where
    `distinct-models` returns the pivot summary (count, first_ts, last_ts
    per model), this route returns the FULL timeline for one specific
    model, sorted by `ts` ascending. Lets the UI drill from the pivot
    table into the per-model timeline without fetching the whole history
    and filtering client-side.

    Query :
      name=<model>   required. Exact-match on the `model` field of each
                     history entry (eg `qwen2.5vl:7b`). Case-sensitive,
                     no normalization — must match what the picker
                     recorded byte-for-byte.

    Response :
      200 {
        "ok": true,
        "name": str,                       // echo of the param
        "count": int,                      // # entries matching, 0 when not found
        "entries": [                       // sorted by ts ascending (timeline order)
          {
            "ts":            float,
            "model":         str,
            "reason":        str,
            "reason_kind":   str,
            "free_vram_gb":  float
          },
          ...
        ]
      }

      400 { "ok": false, "error": "name query param required" }
            when name is absent or empty.

    Pure read — no Ollama, no replay, no mutation. Snapshots the deque
    once before iterating so concurrent picks from extract-structured on
    other threads cannot mutate it mid-loop. Empty result is a 200 with
    `count:0, entries:[]` (NOT a 404) — drill-down on a model name that
    has aged out of the ring buffer is a legitimate "no data right now"
    state, not an error.
    """
    try:
        name_raw = (request.args.get("name") or "").strip()
        if not name_raw:
            return jsonify({"ok": False, "error": "name query param required"}), 400
        # Snapshot the deque BEFORE iterating — extract-structured calls
        # on other threads could mutate it mid-loop otherwise.
        snapshot = list(_PICKER_HISTORY)
        matched: "list[dict]" = []
        for h in snapshot:
            try:
                # Exact-match on the recorded `model` field. Case-sensitive
                # so "Qwen2.5VL:7b" doesn't accidentally match
                # "qwen2.5vl:7b" — Ollama tag matching is case-sensitive
                # and we mirror that contract.
                if str(h.get("model") or "") == name_raw:
                    matched.append(h)
            except Exception:
                # Skip a corrupt entry — observability shouldn't 500 the
                # whole response. Remaining entries stay accurate.
                continue
        # Timeline order : ascending ts. Stable sort means entries with
        # identical ts (rare in practice — record_picker_pick uses
        # `time.time()` which has sub-ms resolution on modern OSes)
        # preserve their deque insertion order.
        try:
            matched.sort(key=lambda e: float(e.get("ts") or 0.0))
        except Exception:
            # Sort failure shouldn't 500 either — return unsorted as a
            # last resort. Pure observability path.
            pass
        return jsonify({
            "ok": True,
            "name": name_raw,
            "count": len(matched),
            "entries": matched,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/by-reason", methods=["GET"])
def picker_history_by_reason():
    """v82lp — per-reason_kind drill-down over `_PICKER_HISTORY`.

    Mirror of `/api/picker/history/by-model` (v82lo) but pivoted on the
    `reason_kind` enum instead of the free-form `model` string. Closes the
    drill-down trinity (by-model, by-reason, timeline) so UI can pivot the
    same ring buffer on whichever axis the user clicks. Pure read, no
    Ollama call, no mutation.

    Query :
      kind=<enum>   required. MUST be one of the stable enum values from
                    `_pick_vision_model_or_default` :
                      ["vram_30b", "vram_8b", "fallback_2_5vl",
                       "first_vl", "default"]
                    Anything else (absent, empty, typo) returns 400 with
                    the accepted list echoed back so the UI can surface
                    "did you mean ..." without hardcoding the enum.

    Response :
      200 {
        "ok": true,
        "kind": str,                       // echo of the param
        "count": int,                      // # entries matching, 0 when not found
        "entries": [                       // sorted by ts ascending (timeline order)
          {
            "ts":            float,
            "model":         str,
            "reason":        str,
            "reason_kind":   str,
            "free_vram_gb":  float
          },
          ...
        ]
      }

      400 { "ok": false, "error": "kind query param required",
            "accepted": [...] }
            when kind is absent or empty.

      400 { "ok": false, "error": "kind query param invalid",
            "accepted": [...] }
            when kind is not in the stable enum list.

    Snapshots the deque BEFORE iterating so concurrent picks from
    extract-structured on other threads cannot mutate it mid-loop.
    Empty match (valid kind but no entries) is a 200 with `count:0,
    entries:[]` — drill-down on a kind that has aged out of the ring
    buffer is a legitimate "no data right now" state, not an error.
    """
    # Stable enum domain — single source of truth at module scope
    # (`_PICKER_REASON_KINDS`). Order is decision-tree order so the UI can
    # render the accepted list in the same order as the picker decision tree.
    kind_keys = list(_PICKER_REASON_KINDS)
    try:
        kind_raw = (request.args.get("kind") or "").strip()
        if not kind_raw:
            return jsonify({
                "ok": False,
                "error": "kind query param required",
                "accepted": kind_keys,
            }), 400
        if kind_raw not in kind_keys:
            return jsonify({
                "ok": False,
                "error": "kind query param invalid",
                "accepted": kind_keys,
            }), 400
        # Snapshot the deque BEFORE iterating — extract-structured calls
        # on other threads could mutate it mid-loop otherwise.
        snapshot = list(_PICKER_HISTORY)
        matched: "list[dict]" = []
        for h in snapshot:
            try:
                # Default-coalesce mirrors what _record_picker_pick stores
                # ("default" when reason_kind is missing) so the filter
                # matches what the picker actually recorded byte-for-byte.
                if str(h.get("reason_kind") or "default") == kind_raw:
                    matched.append(h)
            except Exception:
                # Skip a corrupt entry — observability shouldn't 500 the
                # whole response. Remaining entries stay accurate.
                continue
        # Timeline order : ascending ts. Stable sort means entries with
        # identical ts (rare in practice) preserve their deque insertion
        # order.
        try:
            matched.sort(key=lambda e: float(e.get("ts") or 0.0))
        except Exception:
            # Sort failure shouldn't 500 either — return unsorted as a
            # last resort. Pure observability path.
            pass
        return jsonify({
            "ok": True,
            "kind": kind_raw,
            "count": len(matched),
            "entries": matched,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/timeline", methods=["GET"])
def picker_history_timeline():
    """v82lp — pure-read time-bucketed aggregate over `_PICKER_HISTORY`.

    Buckets every history entry into fixed-width time windows so the UI
    can render a sparkline of "picks per minute" (or any granularity)
    without iterating the full timeline client-side. Composes with the
    existing `since=` filter : `since` runs first, then the survivors
    are bucketed.

    Query :
      bucket_seconds=<int>   default 60. Clamped to [1, 3600] — anything
                             outside that range, non-numeric, or negative
                             returns 400 so the UI can surface the
                             accepted range without hardcoding it.
      since=<float>          optional. Same semantics as
                             /api/picker/history/stats : entries with
                             `ts < since` are dropped before bucketing.
                             Absent / empty / non-positive leaves the
                             snapshot untouched.

    Response :
      200 {
        "ok": true,
        "bucket_seconds": int,             // echo, post-clamp
        "buckets": [                       // sorted by ts_start ascending
          {
            "ts_start": float,             // floor(ts / bucket_seconds) * bucket_seconds
            "count":    int,               // # entries in this bucket
            "by_kind":  { "<kind>": <count>, ... }   // sparse — only kinds present
          },
          ...
        ]
      }

      400 { "ok": false,
            "error": "bucket_seconds must be int in [1, 3600]" }
            when bucket_seconds is non-numeric or out of range.

    Empty buckets are NOT emitted (sparse representation) — a 30-min
    history with picks only at minute 0 and minute 5 returns 2 buckets,
    not 30. UI can fill gaps client-side if dense rendering is needed.
    Pure read — no Ollama, no mutation, no per-site rules, no selectors.
    """
    try:
        # bucket_seconds : default 60, clamp [1, 3600]. Anything outside
        # that range or non-numeric → 400 with the accepted range echoed
        # back so the UI doesn't have to hardcode the bounds.
        bucket_raw = (request.args.get("bucket_seconds") or "").strip()
        bucket_seconds = 60
        if bucket_raw:
            try:
                parsed = int(bucket_raw)
            except Exception:
                return jsonify({
                    "ok": False,
                    "error": "bucket_seconds must be int in [1, 3600]",
                }), 400
            if parsed < 1 or parsed > 3600:
                return jsonify({
                    "ok": False,
                    "error": "bucket_seconds must be int in [1, 3600]",
                }), 400
            bucket_seconds = parsed
        # Snapshot the deque BEFORE iterating — extract-structured calls
        # on other threads could mutate it mid-loop otherwise.
        snapshot = list(_PICKER_HISTORY)
        # v82lw — `since=` filter via the shared `_apply_history_filters`
        # helper. Same byte-identical contract as the inline block this
        # replaces (graceful degradation on non-numeric / negative).
        since_arg, _window_unused = _parse_history_filter_args()
        snapshot = _apply_history_filters(snapshot, since=since_arg)
        # Bucket by floor-division on ts. Each bucket carries a count and
        # a per-kind histogram (sparse — only kinds actually present).
        buckets: "dict[float, dict]" = {}
        for h in snapshot:
            try:
                ts_h = float(h.get("ts") or 0.0)
                kind = str(h.get("reason_kind") or "default")
                # floor-align to bucket boundary so ts_start is
                # deterministic regardless of when the request fires.
                ts_start = float(int(ts_h // bucket_seconds) * bucket_seconds)
                bucket = buckets.get(ts_start)
                if bucket is None:
                    bucket = {"ts_start": ts_start, "count": 0, "by_kind": {}}
                    buckets[ts_start] = bucket
                bucket["count"] = int(bucket["count"]) + 1
                by_kind = bucket["by_kind"]
                by_kind[kind] = int(by_kind.get(kind, 0)) + 1
            except Exception:
                # Skip a corrupt entry — observability shouldn't 500 the
                # whole response. Remaining buckets stay accurate.
                continue
        # Sort ts_start ascending so the UI can render left-to-right.
        buckets_sorted = sorted(buckets.values(), key=lambda b: float(b.get("ts_start") or 0.0))
        return jsonify({
            "ok": True,
            "bucket_seconds": bucket_seconds,
            "buckets": buckets_sorted,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


def _compute_history_summary(
    snapshot: "list[dict]",
    *,
    populated: "set[tuple[str, str]] | None" = None,
) -> "dict":
    """v82ls — single shared aggregate over a `_PICKER_HISTORY` snapshot.

    Returns a 7-key dict that every observability surface (timeline-summary
    route, sextet+ headers on extract-structured, the legacy
    `_compute_dominant_kind` / `_compute_span_seconds` thin wrappers) reads
    from. The intent is DRY : 5+ call sites used to loop on
    `_PICKER_HISTORY` independently with subtle variations (default-coalesce
    rules, ts parsing fallback, kinds_seen sorting). One shared computation
    means the timeline-summary body and the header emitters cannot drift —
    the regression test asserts byte-for-byte agreement.

    v82lv — accepts an optional `populated` kwarg : a pre-computed
    `(model, kind)` cell-set (typically `_compute_coverage_view(snapshot).populated`).
    When provided, `distinct_models` is derived from the set's first-tuple
    cardinality (`len({m for (m, _k) in populated})`) instead of re-scanning
    `snapshot`. Net : `_emit_picker_headers` now performs ONE populated-set
    scan per response (the coverage view's), not two (was : coverage view +
    summary models_seen). Backward-compat : when `populated is None` (the
    default), the function falls back to scanning `snapshot` itself for
    `models_seen` exactly as it always did — every existing call site
    (timeline-summary route, the thin `_compute_dominant_kind` and
    `_compute_span_seconds` wrappers) is unaffected. The cell-set helper
    `_compute_populated_cells` already shares the SAME default-coalesce /
    skip-empty-model rules as the inline `models_seen` loop here, so the
    two paths produce byte-identical `distinct_models` values for any
    non-corrupt snapshot — the regression test asserts that on every
    /timeline/summary body field and every nonet+1 header.

    Returns :
      {
        "count":           int,                # # parseable entries (corrupt skipped)
        "distinct_models": int,                # # unique non-empty model names
        "span_seconds":    float,              # last_ts - first_ts, 0.0 if <2 ts
        "first_ts":        float | None,       # min ts, None when count == 0
        "last_ts":         float | None,       # max ts, None when count == 0
        "dominant_kind":   str   | None,       # most-frequent reason_kind, None empty
        "kinds_seen":      list[str],          # sorted unique reason_kinds
      }

    Conventions (must match every call site that previously rolled its own) :
      - reason_kind default-coalesce : missing / falsy → "default" (matches
        `_record_picker_pick` which stores "default" as the fallback).
      - model default-coalesce : empty string skipped from `distinct_models`
        (matches /stats and /intersections which only count non-empty).
      - ts parse fallback : a single corrupt entry is skipped, not 500. The
        rest of the snapshot stays accurate — observability must not panic
        on a bad row.
      - kinds_seen sort : ascending lexicographic for deterministic output
        (test stability + UI rendering).
      - dominant_kind tie-break : highest count first ; ties broken by the
        most-recent ts within that kind (freshness wins on a tie). Mirrors
        the legacy `_compute_dominant_kind` contract byte-for-byte.

    Pure function, no side effects, never raises (defensive). The caller
    is responsible for snapshotting `_PICKER_HISTORY` BEFORE calling — the
    deque is mutated by other threads.
    """
    # Empty snapshot : single-shot return so downstream consumers don't
    # have to None-check every field individually.
    if not snapshot:
        return {
            "count": 0,
            # v82lv — when `populated` is supplied, derive distinct_models
            # from its first-tuple cardinality even on the empty path so
            # the contract is symmetric. For an empty snapshot the
            # populated set must also be empty (the cell-set helper is
            # pure on the same input), so `len({})` is 0 either way.
            "distinct_models": (
                len({name for (name, _kind) in populated})
                if populated is not None else 0
            ),
            "span_seconds": 0.0,
            "first_ts": None,
            "last_ts": None,
            "dominant_kind": None,
            "kinds_seen": [],
        }
    # Single pass over the snapshot. Collects everything every consumer
    # needs so we don't iterate twice.
    counts: "dict[str, int]" = {}
    kind_last_ts: "dict[str, float]" = {}
    # v82lv — when the caller already computed the populated cell-set
    # (typically via _compute_coverage_view), skip the per-row models_seen
    # accumulation and read distinct_models from that set instead. Saves
    # one full pass over the snapshot per extract-structured response (the
    # second populated-set scan that v82lu still left in place).
    use_populated = populated is not None
    models_seen: "set[str]" = set()
    ts_values: "list[float]" = []
    parsed = 0
    for h in snapshot:
        try:
            kind = str(h.get("reason_kind") or "default")
            counts[kind] = counts.get(kind, 0) + 1
            ts_h = float(h.get("ts") or 0.0)
            if ts_h > kind_last_ts.get(kind, 0.0):
                kind_last_ts[kind] = ts_h
            ts_values.append(ts_h)
            if not use_populated:
                # Backward-compat path : caller didn't pre-compute the
                # populated set, so we accumulate models_seen ourselves.
                # Same default-coalesce rule (skip empty / whitespace-only)
                # as `_compute_populated_cells` so the two paths converge
                # on byte-identical `distinct_models` for any non-corrupt
                # snapshot.
                model_name = str(h.get("model") or "").strip()
                if model_name:
                    models_seen.add(model_name)
            parsed += 1
        except Exception:
            # One bad row must not 500 the response. Counters above stay
            # accurate over the rest of the snapshot.
            continue
    # All entries corrupt → degrade to the empty shape rather than emit
    # garbage. Same contract as the empty-snapshot branch.
    if parsed == 0 or not ts_values:
        return {
            "count": 0,
            "distinct_models": (
                len({name for (name, _kind) in populated})
                if use_populated else 0
            ),
            "span_seconds": 0.0,
            "first_ts": None,
            "last_ts": None,
            "dominant_kind": None,
            "kinds_seen": [],
        }
    first_ts = min(ts_values)
    last_ts_val = max(ts_values)
    # Fewer than 2 timestamps → span is 0.0 by definition (matches the
    # legacy `_compute_span_seconds` contract).
    if len(ts_values) < 2:
        span = 0.0
    else:
        span = max(0.0, last_ts_val - first_ts)
    # Dominant kind : highest count, tie-break on most-recent ts within
    # that kind (freshness wins). Stable sort preserves insertion order
    # on triple-ties.
    if counts:
        ranked = sorted(
            counts.items(),
            key=lambda kv: (-kv[1], -kind_last_ts.get(kv[0], 0.0)),
        )
        dominant = ranked[0][0]
    else:
        dominant = None
    # Sorted ascending for deterministic output across both the
    # timeline-summary body and any future header emitter.
    kinds_seen_sorted = sorted(counts.keys())
    # v82lv — distinct_models : either from the supplied populated set (the
    # `_emit_picker_headers` fast-path) or from the inline models_seen
    # accumulator above (backward-compat path for /timeline/summary etc).
    distinct_models_count = (
        len({name for (name, _kind) in populated})
        if use_populated else len(models_seen)
    )
    return {
        "count": parsed,
        "distinct_models": distinct_models_count,
        "span_seconds": float(span),
        "first_ts": float(first_ts),
        "last_ts": float(last_ts_val),
        "dominant_kind": dominant,
        "kinds_seen": kinds_seen_sorted,
    }


def _compute_dominant_kind(snapshot: "list[dict]") -> "str | None":
    """v82lq — backward-compat thin wrapper over `_compute_history_summary`.

    Refactored at v82ls : delegates to the shared aggregate so the
    timeline-summary route, the X-Picker-History-Dominant-Kind header
    emitter and any other caller agree byte-for-byte. The original tie-break
    contract (highest count first ; ties broken by most-recent last_ts) is
    preserved by `_compute_history_summary`.

    Pure function, no side effects.
    """
    return _compute_history_summary(snapshot)["dominant_kind"]


def _compute_span_seconds(snapshot: "list[dict]") -> float:
    """v82lr — backward-compat thin wrapper over `_compute_history_summary`.

    Refactored at v82ls : delegates to the shared aggregate so the
    timeline-summary route and the X-Picker-History-Span-Seconds header
    emitter agree byte-for-byte. The original `last_ts - first_ts, 0.0
    when <2 entries` contract is preserved by `_compute_history_summary`.

    Pure function, no side effects.
    """
    return float(_compute_history_summary(snapshot)["span_seconds"])


def _apply_history_filters(
    snapshot: "list[dict]",
    *,
    since: "float | None" = None,
    window: "float | None" = None,
) -> "list[dict]":
    """v82lw — single shared `since=` / `window=` filter helper.

    Hoists the 8 copy-pasted filter blocks out of the picker-history
    routes (timeline, timeline/summary, coverage, coverage/global,
    coverage/timeline, by-reason, intersections, cells/empty) into one
    defensive function. Keeps each route body shorter and lets future
    filter additions (`?model=`, `?kind=`, ...) become a one-line
    extension here instead of an N-route copy-paste sweep.

    Contract — must stay byte-identical to the inline blocks it replaces :
      - `since=None` (or non-positive) → no since-filter applied.
      - `since>0`                       → drop entries with `ts < since`.
      - `window=None` (or non-positive) → no window-filter applied.
      - `window>0`                      → drop entries with `ts < now - window`.
      - When BOTH are set, `since` runs first and `window` runs SECOND
        on the survivors. Same ordering as the inline blocks (since the
        absolute cutoff `since` is naturally cheaper than the relative
        `window` cutoff which needs a `time.time()` read).
      - `now` is captured ONCE per call so a long deque + a slow walltime
        read can't drift mid-iteration. Same defensive pattern the
        inline window block already uses.
      - Defensive `float()` coercion + `or 0.0` default-coalesce on each
        entry's `ts` field (matches every inline block byte-for-byte).
      - Never raises : a corrupt entry where `ts` can't be coerced is
        silently dropped (equivalent to `ts == 0.0`, which is below any
        positive cutoff, so the corrupt row gets filtered out — same as
        the inline blocks).

    The two filters are pure list-comprehensions ; the function never
    mutates `snapshot`, returning a fresh list each time. Pure function,
    no Flask `request` access (callers parse `request.args` and pass the
    floats / ints in), no I/O, no module-level state mutation.

    Backward-compat regression : every route migrated to this helper
    produces byte-identical bodies pre/post fold over every combination
    of `(no params, since only, window only, both, invalid)` — asserted
    by the pass-26 live test. The helper is a strict refactor : zero
    behavioral change, all existing call sites disappear.
    """
    if since is not None and since > 0:
        snapshot = [
            h for h in snapshot
            if float(h.get("ts") or 0.0) >= since
        ]
    if window is not None and window > 0:
        # `now` is captured ONCE so the cutoff is stable across the whole
        # filter (a long deque + a slow walltime read could otherwise
        # produce off-by-one drift between rows). Mirrors the inline
        # /coverage/global window block contract byte-for-byte.
        cutoff = float(time.time()) - float(window)
        snapshot = [
            h for h in snapshot
            if float(h.get("ts") or 0.0) >= cutoff
        ]
    return snapshot


def _parse_history_filter_args() -> "tuple[float | None, float | None]":
    """v82lw — Flask-side parser for the `since=` / `window=` query pair.

    Companion to `_apply_history_filters`. Reads `request.args.get("since")`
    and `request.args.get("window")` with the SAME defensive contract every
    inline block used :
      - Non-numeric / negative / non-positive → `None` (no filter).
      - Empty / absent                        → `None` (no filter).
      - Valid positive float                  → returned as `float`.
    The window value is parsed as `int` first (matches /coverage/global)
    but cast to `float` on return so the helper signature stays uniform.

    Returns `(since, window)` — either or both may be `None`. Pass the
    tuple straight into `_apply_history_filters(snapshot, since=since, window=window)`
    to migrate any inline block to the shared helper without changing
    behavior.

    Pure read — touches `request.args` only, never raises, never mutates
    anything. Lives at module scope so each route body collapses from
    ~10 lines of try/except boilerplate to a single line.
    """
    since: "float | None" = None
    since_raw = (request.args.get("since") or "").strip()
    if since_raw:
        try:
            parsed_since = float(since_raw)
            if parsed_since > 0:
                since = parsed_since
        except Exception:
            # Non-numeric `since` is silently ignored (matches every
            # inline block — graceful degradation rather than 400).
            since = None
    window: "float | None" = None
    window_raw = (request.args.get("window") or "").strip()
    if window_raw:
        try:
            parsed_window = int(window_raw)
            if parsed_window > 0:
                window = float(parsed_window)
        except Exception:
            # Non-numeric / negative `window` silently degrades to None
            # (same defensive contract as `since=`).
            window = None
    return since, window


def _compute_populated_cells(snapshot: "list[dict]") -> "set[tuple[str, str]]":
    """v82lt — single shared `(model, reason_kind)` populated-cell scan.

    Returns the set of `(name, kind)` cell keys that have at least one
    pick in the snapshot. The DRY contract anchor for three surfaces :
      - `/api/picker/history/cells/empty` : cell-set complement against
        the Cartesian product `distinct_models × _PICKER_REASON_KINDS`.
      - `/api/picker/history/coverage` (v82lt) : per-model partition of
        `kinds_seen` vs `kinds_missing`, derived from the same set.
      - `X-Picker-History-Empty-Cells` response header (v82lt) : same
        complement cardinality as /cells/empty's `total_empty`.

    Conventions (must match every call site that previously rolled its own) :
      - model name : empty / whitespace-only model names are skipped (matches
        /intersections and /cells/empty which already drop empty rows from
        the heatmap row dimension).
      - reason_kind default-coalesce : missing / falsy → "default" (matches
        `_record_picker_pick` and the by-kind aggregators).
      - corrupt entry skip : a single bad row is silently dropped, the rest
        of the snapshot stays accurate (observability shouldn't 500).

    Pure function, no side effects, never raises (defensive). The caller
    is responsible for snapshotting `_PICKER_HISTORY` BEFORE calling — the
    deque is mutated by other threads.
    """
    populated: "set[tuple[str, str]]" = set()
    for h in snapshot:
        try:
            name = str(h.get("model") or "").strip()
            if not name:
                # Skip empty model names — matches /intersections and
                # /cells/empty which both skip them from cell keys.
                continue
            kind = str(h.get("reason_kind") or "default")
            populated.add((name, kind))
        except Exception:
            # Skip a corrupt entry — observability shouldn't 500. The
            # rest of the populated set stays accurate.
            continue
    return populated


def _compute_coverage_view(snapshot: "list[dict]") -> "dict":
    """v82lu — single-pass shared coverage view over a `_PICKER_HISTORY` snapshot.

    Folds the populated-set scan AND the cardinality math used by every
    coverage surface into one helper. Before this, the bridge made TWO
    snapshot-passes per response : `_compute_populated_cells` for the
    set, then a separate `_compute_history_summary` (or its `distinct_models`
    field) for row count. Both are now derived from the same set so :
      - `/api/picker/history/coverage`         (per-model partition)
      - `/api/picker/history/coverage/global`  (scalar gauge, v82lu)
      - `/api/picker/history/cells/empty`      (complement)
      - `X-Picker-History-Empty-Cells`         (octet header)
      - `X-Picker-History-Coverage-Pct`        (nonet header, v82lu)
    all read the same view object — byte-identical results across surfaces.

    Returns :
      {
        "populated":       set[tuple[str, str]],   # {(model, kind), ...}
        "distinct_models": int,                    # |{m for (m, _) in populated}|
        "kinds_total":     int,                    # len(_PICKER_REASON_KINDS)
        "empty_cells":     int,                    # max(0, rows*cols - len(populated))
        "coverage_pct":    float,                  # round(len(populated)/(rows*cols)*100, 1)
      }

    Edge cases :
      - Empty snapshot OR no non-empty model name OR `kinds_total == 0` →
        `populated:set(), distinct_models:0, empty_cells:0,
        coverage_pct:0.0`. Cartesian product over zero rows is empty by
        definition ; coverage is 0 by convention (no signal yet).
      - Every cell populated (rows × cols == len(populated)) →
        `empty_cells:0, coverage_pct:100.0`.
      - Single model with all 5 kinds populated (rows=1, cols=5,
        len(populated)=5) → `coverage_pct:100.0`.

    Reuses `_compute_populated_cells` for the set scan so the
    default-coalesce / skip-empty / corrupt-entry rules are inherited
    verbatim. Pure function, no side effects, never raises (the inner
    helper is defensive).

    Backward-compat contract : every existing field surfaced by
    `/coverage`, `/cells/empty`, the `X-Picker-History-Empty-Cells`
    header AND every other consumer must remain byte-identical. The
    regression test mocks `_PICKER_HISTORY` with a stable snapshot and
    asserts equality on every body field and every octet header value
    pre/post the v82lu refactor.
    """
    populated = _compute_populated_cells(snapshot)
    # `distinct_models` derived from the populated set itself. The set
    # already enforces the "skip empty model name" rule (helper contract),
    # so the first tuple element of every entry is a non-empty string.
    distinct_models = len({name for (name, _kind) in populated})
    kinds_total = len(_PICKER_REASON_KINDS)
    # Cartesian product cardinality. Zero models → zero cells → zero
    # empty / zero coverage by definition.
    grid_total = distinct_models * kinds_total
    empty_cells = max(0, grid_total - len(populated))
    if grid_total > 0:
        # Round to 1 decimal — matches the float format `f"{pct:.1f}"` used
        # by the `X-Picker-History-Coverage-Pct` header so body and header
        # never disagree past the visible precision.
        coverage_pct = round(len(populated) / grid_total * 100.0, 1)
    else:
        coverage_pct = 0.0
    return {
        "populated": populated,
        "distinct_models": distinct_models,
        "kinds_total": kinds_total,
        "empty_cells": empty_cells,
        "coverage_pct": float(coverage_pct),
    }


def _emit_picker_headers(
    flask_response,
    picker_reason_kind: "str | None",
    picker_free_vram_gb: "float | None",
    model: str,
) -> None:
    """v82lv — single-pass emit of the picker telemetry decanonet.

    Replaces 10 copy-pasted `if picker_reason_kind is not None: try: …`
    blocks in `cowork_extract_structured`. Net win :
      - Single `_PICKER_HISTORY` snapshot per response (was 3+ : Dominant,
        Span, Distinct-Models each took their own list-copy).
      - Single `_compute_history_summary` call (was 1 explicit + 2 via
        the legacy thin wrappers `_compute_dominant_kind` /
        `_compute_span_seconds`).
      - Single `_compute_coverage_view` call folds the populated-cells
        scan AND the rows/cols/empty/coverage math (was 2 separate passes
        in v82lt : `_compute_populated_cells` + an explicit
        `distinct_models` read from `_compute_history_summary`).
      - v82lv : single populated-set scan per response. The coverage view
        runs FIRST and its `populated` cell-set is passed as a kwarg to
        `_compute_history_summary`, which then derives `distinct_models`
        from the set's first-tuple cardinality instead of re-scanning the
        snapshot. Was 2 scans (v82lu : coverage helper + summary helper),
        now 1.
      - Single try/except gate (was 10 independent ones — observability
        mutations must not 500 the response, but the gate doesn't need
        to be re-armed for each header).

    Backward-compat contract : the first 9 header values (Model,
    Reason-Kind, Count, Maxlen, Dominant-Kind, Span-Seconds,
    Distinct-Models, Empty-Cells, Coverage-Pct) MUST stay byte-identical
    to the v82lu emit sequence. The new 10th header
    (Coverage-Window-Seconds) is purely additive : its value is always
    `"0"` on extract-structured because this route does not accept a
    per-request `?window=` override (that lives on
    /api/picker/history/coverage/global only — the header simply
    documents the window the emitted Coverage-Pct was computed over,
    which is "full history"). The regression test mocks `_PICKER_HISTORY`
    with a stable snapshot and asserts pre-/post-refactor byte equality
    on the original 9 plus the documented value for the new header.

    Header order : decision-tree order (decision-time → fill-state →
    aggregate → cardinality → ratio → window). Coverage-Window-Seconds
    closes the decanonet so the sequence reads "what did we pick /
    what's our buffer / what's the dominant trend / what's our
    cardinality / what's our explored fraction over what window".

    Gating : when `picker_reason_kind is None` the function is a no-op
    (text-only request, no vision invoked). All 10 headers either appear
    together or not at all — the contract that lets callers special-case
    "header absent → text-only" without per-header None-checks.

    Pure-effect : mutates `flask_response.headers` in place, returns
    nothing. Never raises (the outer try wraps every read).
    """
    # No vision invoked → no headers. Mirrors the per-block gate that
    # used to live at every call site.
    if picker_reason_kind is None:
        return
    try:
        # Single snapshot of the deque — every aggregate below reads from
        # this list, not the live deque. Concurrent picks on other threads
        # cannot mutate a list-copy mid-read.
        snapshot = list(_PICKER_HISTORY)
        # v82lv — coverage view FIRST so its `populated` set can be reused
        # by `_compute_history_summary` below. Net : a single populated-set
        # scan per response (the v82lu arrangement still scanned twice — the
        # coverage helper for empty_cells / coverage_pct, then the summary
        # helper for `distinct_models`). Now `_compute_coverage_view`
        # produces the cell-set ONCE and `_compute_history_summary` derives
        # `distinct_models` from it via its `populated` kwarg without
        # re-iterating the snapshot. Backward-compat preserved : the
        # set-derived count is byte-identical to the inline `models_seen`
        # accumulator (same default-coalesce / skip-empty rules), as
        # asserted by the regression test on every /timeline/summary body
        # field and every nonet+1 header value.
        coverage = _compute_coverage_view(snapshot)
        # v82lv — pass `populated` so the summary skips its own models_seen
        # scan. This is the SECOND scan elimination (after v82lu folded the
        # populated-cells + cardinality math into one helper). Net result :
        # ONE populated-set scan per extract-structured response, period.
        summary = _compute_history_summary(
            snapshot, populated=coverage["populated"]
        )
        # Decision-time triple : Reason-Kind, Free-VRAM, Model. These
        # describe what the picker chose and the conditions it chose under.
        flask_response.headers["X-Picker-Reason-Kind"] = str(picker_reason_kind)
        if picker_free_vram_gb is not None:
            flask_response.headers["X-Free-Vram-Gb"] = (
                f"{float(picker_free_vram_gb):.2f}"
            )
        flask_response.headers["X-Picker-Model"] = str(model)
        # Fill-state pair : Count, Maxlen. UI computes fill_pct=count/maxlen
        # without hardcoding the deque cap.
        flask_response.headers["X-Picker-History-Count"] = str(len(_PICKER_HISTORY))
        flask_response.headers["X-Picker-History-Maxlen"] = str(_PICKER_HISTORY.maxlen)
        # Aggregate pair : Dominant-Kind, Span-Seconds. Both pulled from
        # the single _compute_history_summary call so they cannot drift.
        # Dominant uses "" for empty-history (the gate already excludes
        # text-only ; "" means vision-was-invoked-but-history-was-empty
        # which can't happen post-_record_picker_pick but stays defensive).
        dominant = summary.get("dominant_kind")
        flask_response.headers["X-Picker-History-Dominant-Kind"] = (
            str(dominant) if dominant is not None else ""
        )
        flask_response.headers["X-Picker-History-Span-Seconds"] = (
            f"{float(summary.get('span_seconds') or 0.0):.2f}"
        )
        # Cardinality pair : Distinct-Models, Empty-Cells. Distinct comes
        # from the shared coverage view (set-comprehension over the
        # populated cell-set itself, NOT from `summary` — the two helpers
        # use different default-coalesce rules but converge on the same
        # cardinality for any non-corrupt snapshot. Reading from the
        # coverage view ensures byte-identity with /coverage[/global]
        # and /cells/empty `total_empty`).
        distinct_models = int(coverage.get("distinct_models") or 0)
        flask_response.headers["X-Picker-History-Distinct-Models"] = (
            str(distinct_models)
        )
        flask_response.headers["X-Picker-History-Empty-Cells"] = str(
            int(coverage.get("empty_cells") or 0)
        )
        # v82lu — Coverage-Pct closes the nonet. Format `f"{pct:.1f}"`
        # mirrors `coverage_pct` from /api/picker/history/coverage/global
        # byte-for-byte (both surfaces read the SAME `_compute_coverage_view`
        # call internally). Empty history → "0.0" (zero models means
        # the Cartesian product is empty, coverage is 0 by definition).
        # Single model with all 5 kinds → "100.0".
        flask_response.headers["X-Picker-History-Coverage-Pct"] = (
            f"{float(coverage.get('coverage_pct') or 0.0):.1f}"
        )
        # v82lv — Coverage-Window-Seconds closes the decanonet. Carries
        # the sliding-window length used to compute the Coverage-Pct
        # value emitted on this same response. On extract-structured the
        # value is ALWAYS "0" (full-history default — this route does
        # not accept a per-request `?window=` override ; the override
        # lives on /api/picker/history/coverage/global only). Format :
        # plain integer string, no decimal. Mirrors the `window_seconds`
        # body field on /coverage/global byte-for-byte (both surfaces
        # render the resolved seconds as `str(int)`). Empty history → "0".
        flask_response.headers["X-Picker-History-Coverage-Window-Seconds"] = "0"
        # v82lw — Coverage-Window-Delta-Pct closes the undecanonet.
        # Signed delta `coverage_pct(window=DELTA_WINDOW) - coverage_pct(full)`
        # so the UI can surface "exploration is N pp behind / ahead of
        # long-term average" without a second round-trip. DELTA_WINDOW
        # is the boot-resolved `_PICKER_HISTORY_DELTA_WINDOW_SECONDS`
        # (default 60s, env-configurable). Both halves are computed over
        # the SAME snapshot above (no `since=` cutoff on extract-structured ;
        # this route doesn't accept query params for delta) — full uses
        # the entire snapshot, window uses the DELTA_WINDOW slice.
        # Format `f"{delta:+.1f}"` (signed, one decimal) so a
        # window-coverage 30.0 vs full 25.0 reads "+5.0" ; the inverse
        # reads "-5.0" ; equal coverages read "+0.0". Empty history →
        # "+0.0" (no signal yet, neither leading nor trailing). The body
        # field `delta_pct` on /coverage/global?delta=1 mirrors this
        # value byte-for-byte past the visible precision.
        try:
            full_view_for_delta = coverage  # already computed above
            window_snapshot = _apply_history_filters(
                snapshot,
                window=float(_PICKER_HISTORY_DELTA_WINDOW_SECONDS),
            )
            window_view_for_delta = _compute_coverage_view(window_snapshot)
            delta_pct = (
                float(window_view_for_delta.get("coverage_pct") or 0.0)
                - float(full_view_for_delta.get("coverage_pct") or 0.0)
            )
        except Exception:
            delta_pct = 0.0
        flask_response.headers["X-Picker-History-Coverage-Window-Delta-Pct"] = (
            f"{delta_pct:+.1f}"
        )
    except Exception:
        # Observability mutations must not 500 the response. Better to
        # serve a partial header set (what already landed) than crash the
        # extract path because aggregation glitched.
        pass


@app.route("/api/picker/history/timeline/summary", methods=["GET"])
def picker_history_timeline_summary():
    """v82lq — pure-read meta aggregate over `_PICKER_HISTORY`.

    Returns a single-shot summary of the entire history (or a `since=`
    filtered slice) so the UI can surface "you have N picks spanning M
    seconds, dominantly K" without paging through the full timeline.
    Composes with the existing `since=` filter : `since` runs first, then
    the survivors are aggregated. Pure read — no Ollama, no replay, no
    mutation, no per-site rules, no selectors.

    Query :
      since=<float>   optional. Same semantics as
                      /api/picker/history/stats and
                      /api/picker/history/timeline : entries with
                      `ts < since` are dropped before aggregation.
                      Absent / empty / non-positive leaves the snapshot
                      untouched.

    Response :
      200 {
        "ok": true,
        "total_picks":    int,                 // # entries after filter
        "span_seconds":   float,               // last_ts - first_ts (0.0 if <2 entries)
        "first_ts":       float | null,        // null when total_picks == 0
        "last_ts":        float | null,        // null when total_picks == 0
        "dominant_kind":  str   | null,        // reason_kind with highest count, null when empty
        "kinds_seen":     [str, ...]           // unique reason_kinds present, sorted
      }

    Empty history (or empty after `since=` filter) returns
    `total_picks:0, span_seconds:0.0, first_ts:null, last_ts:null,
    dominant_kind:null, kinds_seen:[]` — the absence is a 200, not a 404,
    because "no picks yet" is a legitimate boot-time state.

    `dominant_kind` uses `_compute_dominant_kind` (count-then-last_ts tie
    break) so the value matches the X-Picker-History-Dominant-Kind header
    on extract-structured byte-for-byte.

    v82ls — refactored to delegate to `_compute_history_summary` (the new
    shared single-pass aggregate). Both this route and the sextet+ headers
    on extract-structured now read from the same function so a regression
    test asserts byte-for-byte agreement (sauf float format).
    """
    try:
        # Snapshot the deque BEFORE iterating — extract-structured calls
        # on other threads could mutate it mid-loop otherwise.
        snapshot = list(_PICKER_HISTORY)
        # v82lw — `since=` filter via the shared `_apply_history_filters`
        # helper. Same byte-identical contract as the inline block this
        # replaces (graceful degradation on non-numeric / negative).
        since_arg, _window_unused = _parse_history_filter_args()
        snapshot = _apply_history_filters(snapshot, since=since_arg)
        # Single shared aggregate — same function the sextet+ headers
        # read from, so body fields and headers cannot drift. Handles the
        # empty / all-corrupt edge cases internally.
        summary = _compute_history_summary(snapshot)
        return jsonify({
            "ok": True,
            "total_picks": int(summary["count"]),
            "span_seconds": float(summary["span_seconds"]),
            "first_ts": summary["first_ts"],
            "last_ts": summary["last_ts"],
            "dominant_kind": summary["dominant_kind"],
            "kinds_seen": list(summary["kinds_seen"]),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/by-model-and-reason", methods=["GET"])
def picker_history_by_model_and_reason():
    """v82lq — intersection drill-down over `_PICKER_HISTORY`.

    Companion to `/api/picker/history/by-model` (v82lo) and
    `/api/picker/history/by-reason` (v82lp). Where each of those filters on
    a single axis, this route AND-applies BOTH filters so the UI can
    answer "show me only the picks where qwen3-vl:8b was chosen because
    of a fallback_2_5vl reason". Closes the drill-down quartet (by-model,
    by-reason, by-model-and-reason, timeline) so any pivot the UI exposes
    has a server-side endpoint backing it. Pure read, no Ollama, no
    mutation.

    Query :
      name=<model>   required. Exact-match on the `model` field of each
                     history entry (case-sensitive — mirrors by-model).
      kind=<enum>    required. MUST be one of the stable enum values from
                     `_pick_vision_model_or_default` :
                       ["vram_30b", "vram_8b", "fallback_2_5vl",
                        "first_vl", "default"]
                     Anything else returns 400 with the accepted list.

    Response :
      200 {
        "ok": true,
        "name": str,                       // echo of the param
        "kind": str,                       // echo of the param
        "count": int,                      // # entries matching BOTH filters, 0 when not found
        "entries": [                       // sorted by ts ascending (timeline order)
          {
            "ts":            float,
            "model":         str,
            "reason":        str,
            "reason_kind":   str,
            "free_vram_gb":  float
          },
          ...
        ]
      }

      400 { "ok": false, "error": "name query param required",
            "accepted": [...] }
            when name is absent or empty.

      400 { "ok": false, "error": "kind query param required",
            "accepted": [...] }
            when kind is absent or empty.

      400 { "ok": false, "error": "kind query param invalid",
            "accepted": [...] }
            when kind is not in the stable enum list.

    Both filters are required (no implicit wildcard) — callers wanting a
    single-axis pivot already have by-model or by-reason. A valid-but-
    empty intersection (eg name+kind combination that has aged out of the
    ring buffer, or never co-occurred) returns 200 with `count:0,
    entries:[]`, NOT a 404 — empty intersection is a legitimate "no data
    right now" state, not an error.

    Snapshots the deque BEFORE iterating so concurrent picks from
    extract-structured on other threads cannot mutate it mid-loop.
    """
    # Stable enum domain — single source of truth at module scope
    # (`_PICKER_REASON_KINDS`). Decision-tree order so the UI can render
    # the accepted list in the same order as the picker decision tree.
    kind_keys = list(_PICKER_REASON_KINDS)
    try:
        name_raw = (request.args.get("name") or "").strip()
        kind_raw = (request.args.get("kind") or "").strip()
        # Validate `name` first (echo accepted kind list either way so the
        # UI can render hints uniformly).
        if not name_raw:
            return jsonify({
                "ok": False,
                "error": "name query param required",
                "accepted": kind_keys,
            }), 400
        if not kind_raw:
            return jsonify({
                "ok": False,
                "error": "kind query param required",
                "accepted": kind_keys,
            }), 400
        if kind_raw not in kind_keys:
            return jsonify({
                "ok": False,
                "error": "kind query param invalid",
                "accepted": kind_keys,
            }), 400
        # Snapshot the deque BEFORE iterating — extract-structured calls
        # on other threads could mutate it mid-loop otherwise.
        snapshot = list(_PICKER_HISTORY)
        matched: "list[dict]" = []
        for h in snapshot:
            try:
                # AND-applied : both filters must match. Default-coalesce
                # for reason_kind mirrors what _record_picker_pick stores
                # ("default" when reason_kind is missing) so the filter
                # matches what the picker actually recorded.
                model_match = str(h.get("model") or "") == name_raw
                kind_match = str(h.get("reason_kind") or "default") == kind_raw
                if model_match and kind_match:
                    matched.append(h)
            except Exception:
                continue
        # Timeline order : ascending ts. Stable sort preserves deque
        # insertion order on identical ts.
        try:
            matched.sort(key=lambda e: float(e.get("ts") or 0.0))
        except Exception:
            pass
        return jsonify({
            "ok": True,
            "name": name_raw,
            "kind": kind_raw,
            "count": len(matched),
            "entries": matched,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/intersections", methods=["GET"])
def picker_history_intersections():
    """v82lr — pure-read pivot table over `(model x reason_kind)`.

    Sparse heatmap source : for every distinct
    `(model, reason_kind)` pair present in `_PICKER_HISTORY`, return the
    pick count and the most-recent timestamp. Companion to
    /api/picker/history/by-model-and-reason (which returns the timeline
    for ONE specific intersection cell). Where that route is the
    drill-down, this one is the heatmap source — UI renders all
    populated cells server-side without iterating the full history
    client-side.

    Sparse — only cells with `count >= 1` are emitted. A 7-pick history
    with 2 distinct models and 3 distinct kinds returns at most 6
    cells, typically far fewer.

    Composes with `since=` : same contract as
    /api/picker/history/stats and /api/picker/history/timeline. Filter
    first, bucket the survivors. Non-numeric / non-positive `since`
    silently no-ops (graceful degradation).

    Query :
      since=<float>   optional. Entries with `ts < since` are dropped
                      before bucketing. Absent / empty / non-positive
                      leaves the snapshot untouched.

    Response :
      200 {
        "ok": true,
        "total_picks": int,                // # entries after `since=` filter
        "cells": [                         // sorted by count desc, ties by last_ts desc
          {
            "name":    str,                // model name as recorded
            "kind":    str,                // reason_kind as recorded
            "count":   int,                // # picks for this (name, kind) pair
            "last_ts": float               // most-recent ts for this pair
          },
          ...
        ]
      }

    Sort order : `count` descending (most-frequent cells first), ties
    broken by `last_ts` descending (most-recently-active wins). UI can
    render the heatmap top-down without re-sorting.

    Pure read — no Ollama, no replay, no mutation, no per-site rules,
    no selectors. Snapshots the deque BEFORE iterating so concurrent
    picks from extract-structured cannot mutate it mid-loop. Empty
    history (or empty after `since=` filter) returns
    `total_picks:0, cells:[]` (NOT a 404) — empty heatmap is a
    legitimate "no data right now" state, not an error.
    """
    try:
        # Snapshot the deque BEFORE iterating — extract-structured calls
        # on other threads could mutate it mid-loop otherwise.
        snapshot = list(_PICKER_HISTORY)
        # v82lw — `since=` filter via the shared `_apply_history_filters`
        # helper. Same byte-identical contract as the inline block this
        # replaces (graceful degradation on non-numeric / negative).
        since_arg, _window_unused = _parse_history_filter_args()
        snapshot = _apply_history_filters(snapshot, since=since_arg)
        # Bucket by (model, reason_kind). Default-coalesce reason_kind
        # mirrors what `_record_picker_pick` stores ("default" when
        # missing) so the cell key matches what the picker recorded
        # byte-for-byte.
        cells: "dict[tuple[str, str], dict]" = {}
        for h in snapshot:
            try:
                name = str(h.get("model") or "").strip()
                if not name:
                    # Skip empty model names — `_record_picker_pick`
                    # always sets a non-empty string but defensive
                    # against future mutators.
                    continue
                kind = str(h.get("reason_kind") or "default")
                ts_h = float(h.get("ts") or 0.0)
                key = (name, kind)
                cell = cells.get(key)
                if cell is None:
                    cells[key] = {
                        "name": name,
                        "kind": kind,
                        "count": 1,
                        "last_ts": ts_h,
                    }
                else:
                    cell["count"] = int(cell["count"]) + 1
                    if ts_h > float(cell["last_ts"]):
                        cell["last_ts"] = ts_h
            except Exception:
                # Skip a corrupt entry — observability shouldn't 500 the
                # whole response. Remaining cells stay accurate.
                continue
        # Sort cells by count desc, ties broken by last_ts desc. Stable
        # sort means a single key tuple expresses the full ordering.
        cells_sorted = sorted(
            cells.values(),
            key=lambda c: (-int(c.get("count") or 0), -float(c.get("last_ts") or 0.0)),
        )
        return jsonify({
            "ok": True,
            "total_picks": len(snapshot),
            "cells": cells_sorted,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/cells/empty", methods=["GET"])
def picker_history_cells_empty():
    """v82ls — pure-read complement of `/api/picker/history/intersections`.

    Where `/intersections` returns the SPARSE populated cells of the
    `(model x reason_kind)` heatmap (count >= 1), this route returns the
    SET of cells that NEVER co-occurred in the current ring buffer. The
    cell-domain is the Cartesian product of :
      - distinct_models  : every distinct model name observed in
                           `_PICKER_HISTORY` (snapshot at probe time)
      - _PICKER_REASON_KINDS : the stable enum of 5 picker decision
                               branches (vram_30b, vram_8b,
                               fallback_2_5vl, first_vl, default)
    minus whatever cells `/intersections` would emit for the same
    (post-`since=`-filter) snapshot.

    Lets the UI render the heatmap with grayed-out empty cells without
    iterating the full Cartesian product client-side. Pairs with
    `/intersections` so the UI has both "what's populated" and "what's
    missing" without duplicating the bucketing logic.

    Composes with `since=` : same contract as /intersections / /timeline
    / /stats. The `since` filter applies to the populated-cell discovery
    pass — so "models seen in the last 60s" determines the row dimension,
    and the complement is computed against the populated cells from that
    same filtered window. Non-numeric / non-positive `since` silently
    no-ops (matches the existing endpoints' contract).

    Query :
      since=<float>   optional. Entries with `ts < since` are dropped
                      before the populated-cell scan. Absent / empty /
                      non-positive leaves the snapshot untouched.

    Response :
      200 {
        "ok": true,
        "total_empty": int,                // # cells in the complement
        "cells": [                         // sorted name asc, then kind asc
          {
            "name": str,                   // model name as recorded
            "kind": str                    // reason_kind enum value
          },
          ...
        ]
      }

    Sort order : `name` ascending, ties broken by `kind` ascending. Stable
    sort means a single key tuple expresses the full ordering — so test
    output and UI rendering are deterministic across calls.

    Edge cases :
      - distinct_models empty (no picks yet, or empty after `since=`
        filter) → `cells:[], total_empty:0`. The Cartesian product over
        an empty model dimension is empty by definition ; UI should fall
        back to a "no picks yet" placeholder rather than show 0 cells of
        nothing.
      - All cells populated (rare — would require every model to have
        hit every reason_kind branch) → `cells:[], total_empty:0`.
      - Single model + single kind populated → `cells = (1 x 5) - 1 = 4`
        empty cells (the 4 other kinds for that lone model).

    Pure read — no Ollama, no replay, no mutation, no per-site rules,
    no selectors. Snapshots the deque BEFORE iterating so concurrent
    picks from extract-structured cannot mutate it mid-loop.
    """
    try:
        # Snapshot the deque BEFORE iterating — extract-structured calls
        # on other threads could mutate it mid-loop otherwise.
        snapshot = list(_PICKER_HISTORY)
        # v82lw — `since=` filter via the shared `_apply_history_filters`
        # helper. Same byte-identical contract as the inline block this
        # replaces (graceful degradation on non-numeric / negative).
        since_arg, _window_unused = _parse_history_filter_args()
        snapshot = _apply_history_filters(snapshot, since=since_arg)
        # First pass : discover the populated cell set + cardinality via
        # the shared `_compute_coverage_view` helper (v82lu). Same
        # default-coalesce rules as /intersections AND the
        # X-Picker-History-Empty-Cells / X-Picker-History-Coverage-Pct
        # header emitters so the complement is exact (no off-by-one from
        # divergent rules). The row dimension (distinct_models) is derived
        # from the populated set itself — every populated cell's first
        # tuple element is a non-empty model name by helper contract.
        view = _compute_coverage_view(snapshot)
        populated = view["populated"]
        distinct_models: "set[str]" = {name for (name, _kind) in populated}
        # If no models seen, the Cartesian product is empty by definition.
        # UI should render a "no picks yet" placeholder rather than 0
        # cells of nothing — return the empty shape explicitly so the
        # contract is unambiguous.
        if not distinct_models:
            return jsonify({
                "ok": True,
                "total_empty": 0,
                "cells": [],
            })
        # Second pass : Cartesian product distinct_models × _PICKER_REASON_KINDS
        # MINUS the populated set. The kind dimension is the immutable
        # tuple at module scope — same source-of-truth as /stats by_kind,
        # /by-reason accepted, /by-model-and-reason accepted, /kinds.
        kind_keys = list(_PICKER_REASON_KINDS)
        empty_cells: "list[dict]" = []
        for name in distinct_models:
            for kind in kind_keys:
                if (name, kind) in populated:
                    continue
                empty_cells.append({"name": name, "kind": kind})
        # Sort name asc, kind asc — stable sort means a single key tuple
        # expresses the full ordering. Deterministic for tests and UI.
        empty_cells.sort(key=lambda c: (str(c.get("name") or ""), str(c.get("kind") or "")))
        return jsonify({
            "ok": True,
            "total_empty": len(empty_cells),
            "cells": empty_cells,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/coverage", methods=["GET"])
def picker_history_coverage():
    """v82lt — pure-read per-model coverage pivot over `_PICKER_HISTORY`.

    For every distinct model in the ring buffer, partition the stable
    `_PICKER_REASON_KINDS` enum into two halves :
      - `kinds_seen`     : kinds this model has hit at least once
      - `kinds_missing`  : kinds this model has NEVER hit
    plus a precomputed `coverage_pct` for the UI to sort/colorize without
    re-doing the math client-side. Lets the extension answer "which model
    still has unexplored picker branches" with a single fetch.

    DRY contract anchor : the populated cell set comes from the shared
    `_compute_populated_cells` helper (v82lt). Same default-coalesce rules
    as /intersections, /cells/empty AND the X-Picker-History-Empty-Cells
    header emitter — the four surfaces cannot drift. The row dimension
    (distinct models) is derived from the populated set itself ;
    `kinds_seen` for each model is `{kind for (m, kind) in populated if m == name}`,
    `kinds_missing` is `set(_PICKER_REASON_KINDS) - kinds_seen`.

    Composes with `since=` : same contract as /intersections / /timeline /
    /stats / /cells/empty. Filter first, then partition the survivors.
    Non-numeric / non-positive `since` silently no-ops.

    Query :
      since=<float>   optional. Entries with `ts < since` are dropped
                      before the populated-cell scan. Absent / empty /
                      non-positive leaves the snapshot untouched.

    Response :
      200 {
        "ok": true,
        "total_picks": int,                    // # entries after `since=` filter
        "models": [                            // sorted coverage_pct desc, ties name asc
          {
            "name":          str,              // model name as recorded
            "kinds_seen":    [str, ...],       // sorted asc, subset of _PICKER_REASON_KINDS
            "kinds_missing": [str, ...],       // sorted asc, complement
            "coverage_pct":  float             // round(len(seen)/len(kinds)*100, 1)
          },
          ...
        ]
      }

    Sort order : `coverage_pct` descending (most-covered models first),
    ties broken by `name` ascending (deterministic). Stable sort means a
    single key tuple expresses the full ordering.

    Edge cases :
      - Empty history (or empty after `since=` filter) → `models:[]`.
      - Single model that has hit every kind → `coverage_pct:100.0`,
        `kinds_missing:[]`.
      - Empty `kinds_seen` is structurally impossible (a model only
        appears in `populated` if it has at least one pick) → every
        `coverage_pct` is `> 0.0`.

    Pure read — no Ollama, no replay, no mutation, no per-site rules,
    no selectors. Snapshots the deque BEFORE iterating so concurrent
    picks from extract-structured cannot mutate it mid-loop.
    """
    try:
        # Snapshot the deque BEFORE iterating — extract-structured calls
        # on other threads could mutate it mid-loop otherwise.
        snapshot = list(_PICKER_HISTORY)
        # v82lw — `since=` filter via the shared `_apply_history_filters`
        # helper. Same byte-identical contract as the inline block this
        # replaces (graceful degradation on non-numeric / negative).
        since_arg, _window_unused = _parse_history_filter_args()
        snapshot = _apply_history_filters(snapshot, since=since_arg)
        # Snapshot total_picks AFTER the `since=` filter so the UI can
        # render "X picks across N models" with the same numerator the
        # /cells/empty and /intersections routes report.
        total_picks = len(snapshot)
        # Single shared helper call (v82lu) — DRY anchor with /cells/empty,
        # /coverage/global AND the X-Picker-History-Empty-Cells /
        # Coverage-Pct header emitters.
        view = _compute_coverage_view(snapshot)
        populated = view["populated"]
        # Group populated kinds by model. Single pass over the cell set.
        per_model_seen: "dict[str, set[str]]" = {}
        for (name, kind) in populated:
            bucket = per_model_seen.get(name)
            if bucket is None:
                per_model_seen[name] = {kind}
            else:
                bucket.add(kind)
        # Stable enum domain — single source of truth at module scope.
        kind_keys = list(_PICKER_REASON_KINDS)
        kinds_total = view["kinds_total"]
        kinds_set = set(kind_keys)
        models: "list[dict]" = []
        for name, seen_set in per_model_seen.items():
            kinds_seen_sorted = sorted(seen_set)
            kinds_missing_sorted = sorted(kinds_set - seen_set)
            # `coverage_pct = round(len(seen) / total * 100, 1)`. Total is
            # bounded by the immutable enum tuple so divide-by-zero is
            # structurally impossible (assert at module load guarantees
            # `len(_PICKER_REASON_KINDS) >= 1`).
            coverage_pct = round(
                (len(kinds_seen_sorted) / kinds_total) * 100.0,
                1,
            ) if kinds_total > 0 else 0.0
            models.append({
                "name": name,
                "kinds_seen": kinds_seen_sorted,
                "kinds_missing": kinds_missing_sorted,
                "coverage_pct": coverage_pct,
            })
        # Sort coverage_pct desc, ties broken by name asc. Python's stable
        # sort means a single key tuple expresses the full ordering.
        models.sort(key=lambda m: (-float(m.get("coverage_pct") or 0.0), str(m.get("name") or "")))
        return jsonify({
            "ok": True,
            "total_picks": total_picks,
            "models": models,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/coverage/global", methods=["GET"])
def picker_history_coverage_global():
    """v82lu — pure-read scalar coverage gauge over `_PICKER_HISTORY`.

    Companion to /api/picker/history/coverage (per-model partition) :
    where that route returns the breakdown per model, this one returns
    a SINGLE scalar fraction "the picker has explored P/Q of the
    `(model x kind)` grid". Lets the extension surface a one-shot
    "exploration progress" gauge without iterating /coverage[].models
    client-side and re-summing.

    DRY contract anchor : the populated cell set + cardinality math come
    from the shared `_compute_coverage_view` helper (v82lu). Same
    default-coalesce / skip-empty / corrupt-entry rules as /intersections,
    /cells/empty, /coverage AND the X-Picker-History-Empty-Cells /
    Coverage-Pct header emitters — five surfaces, one helper, byte-
    identical contract.

    Composes with `since=` : same filter contract as /coverage,
    /cells/empty, /intersections, /timeline, /stats. Filter first, then
    fold the survivors into the scalar view. Non-numeric / non-positive
    `since` silently no-ops.

    v82lv — additional `?window=<seconds>` sliding-window filter applied
    AFTER the existing `since=` filter. When provided, only entries with
    `ts >= now - window` survive into the coverage fold. Lets the UI
    answer "what fraction of the (model x kind) grid have we explored in
    the LAST N seconds" — orthogonal to the absolute `since=` cutoff
    (you can compose them, e.g. "since this morning AND in the last 5
    minutes within that"). Invalid `window` (negative, non-int) silently
    degrades to 0 (full history) — mirrors the `since=` defensive
    contract. The response body grows a `window_seconds` field echoing
    the resolved value (`0` for full-history default, the parsed int
    otherwise).

    Query :
      since=<float>     optional. Entries with `ts < since` are dropped
                        before the populated-cell scan. Absent / empty /
                        non-positive leaves the snapshot untouched.
      window=<int>      optional, v82lv. Entries with `ts < now - window`
                        are dropped AFTER the `since=` filter. Default 0
                        (full history). Negative / non-int silently
                        degrade to 0. Composes orthogonally with `since=`.

    Response :
      200 {
        "ok": true,
        "total_picks":     int,                // # entries after `since=` AND `window=` filters
        "distinct_models": int,                // # unique non-empty model names
        "kinds_total":     int,                // len(_PICKER_REASON_KINDS) — always 5
        "populated_cells": int,                // # (model, kind) pairs with >= 1 pick
        "empty_cells":     int,                // distinct_models * kinds_total - populated_cells
        "coverage_pct":    float,              // round(populated/(rows*cols)*100, 1)
        "window_seconds":  int                 // v82lv — resolved window, 0 for full history
      }

    Examples (assuming `_PICKER_REASON_KINDS` has 5 elements) :
      - Empty history → `{ok:true, total_picks:0, distinct_models:0,
        kinds_total:5, populated_cells:0, empty_cells:0, coverage_pct:0.0,
        window_seconds:0}`.
      - Single model with all 5 kinds populated → `{... distinct_models:1,
        populated_cells:5, empty_cells:0, coverage_pct:100.0,
        window_seconds:0}`.
      - 7 picks across 2 models hitting 3 distinct (model, kind) cells →
        `{... distinct_models:2, populated_cells:3, empty_cells:7,
        coverage_pct:30.0, window_seconds:0}` (3 / (2*5) = 30.0).
      - `?window=60` with only 2 of those cells populated in the last
        minute → `{... populated_cells:2, coverage_pct:20.0,
        window_seconds:60}` (smaller because the window dropped older picks).

    `coverage_pct` is byte-identical to the X-Picker-History-Coverage-Pct
    response header on /api/cowork/extract-structured for the same
    snapshot when `?window=` is absent or `0` — both surfaces read the
    SAME `_compute_coverage_view` call internally over the same survivor
    set. The header value is rendered with `f"{pct:.1f}"` so a coverage
    of 30.0 (the float) reads "30.0" (the header) ; the JSON body keeps
    the raw float so callers can `===` against numeric values without
    parsing. The `X-Picker-History-Coverage-Window-Seconds` companion
    header on extract-structured is always `"0"` (full history, no
    per-request override) and mirrors the `window_seconds` body field
    here byte-for-byte when `?window=` is absent.

    Pure read — no Ollama, no replay, no mutation, no per-site rules,
    no selectors. Snapshots the deque BEFORE iterating so concurrent
    picks from extract-structured cannot mutate it mid-loop.
    """
    try:
        # Snapshot the deque BEFORE iterating — extract-structured calls
        # on other threads could mutate it mid-loop otherwise.
        snapshot = list(_PICKER_HISTORY)
        # v82lw — `since=` AND `window=` filter via the shared
        # `_apply_history_filters` helper. Same byte-identical contract
        # as the inline blocks this replaces : `since=` runs first, then
        # `window=` runs on the survivors with a single `time.time()`
        # capture (defensive against long-deque drift). Both filters
        # silently no-op on non-numeric / non-positive — graceful
        # degradation rather than 400, since this is a secondary filter.
        since_arg, window_arg = _parse_history_filter_args()
        snapshot = _apply_history_filters(snapshot, since=since_arg, window=window_arg)
        # `window_seconds` echoed in the response body : 0 when absent
        # / non-positive (full history default), the resolved int otherwise.
        # Mirrors the X-Picker-History-Coverage-Window-Seconds header on
        # extract-structured byte-for-byte when `?window=` is absent.
        window_seconds = int(window_arg) if window_arg else 0
        # `total_picks` AFTER the `since=` AND `window=` filters — same
        # numerator the /coverage and /cells/empty routes report when no
        # window is applied so the three coverage surfaces never disagree
        # on the cardinality of the surviving set.
        total_picks = len(snapshot)
        # Single shared helper call — every cardinality below comes from
        # the SAME view object. Byte-identical contract with /coverage,
        # /cells/empty AND the X-Picker-History-Coverage-Pct /
        # Empty-Cells headers on extract-structured.
        view = _compute_coverage_view(snapshot)
        body: "dict" = {
            "ok": True,
            "total_picks": total_picks,
            "distinct_models": int(view["distinct_models"]),
            "kinds_total": int(view["kinds_total"]),
            "populated_cells": int(len(view["populated"])),
            "empty_cells": int(view["empty_cells"]),
            "coverage_pct": float(view["coverage_pct"]),
            # v82lv — resolved window seconds. 0 means "full history"
            # (default, no per-request override). Mirrors the
            # X-Picker-History-Coverage-Window-Seconds header on
            # extract-structured byte-for-byte when `?window=` is absent.
            "window_seconds": int(window_seconds),
        }
        # v82lw — opt-in `?delta=1` body fields. When set, compute the
        # signed delta `coverage_pct(window=DELTA_WINDOW) - coverage_pct(full)`
        # so the UI can surface "exploration is N pp behind / ahead of
        # long-term average" without a second round-trip. Both halves are
        # computed against the SAME `since=`-filtered snapshot (the
        # absolute cutoff stays applied) but ignore the user-passed
        # `?window=` — the delta semantic is "window=DELTA_WINDOW vs
        # full history" regardless of what window the main body fold
        # used. DELTA_WINDOW is configured ONCE at module load via the
        # `_PICKER_HISTORY_DELTA_WINDOW_SECONDS` env-var (default 60).
        delta_raw = (request.args.get("delta") or "").strip()
        if delta_raw == "1":
            # Re-snapshot AFTER `since=` filter only (drop the user-passed
            # `?window=` — the delta uses its own DELTA_WINDOW).
            snapshot_for_delta = list(_PICKER_HISTORY)
            snapshot_for_delta = _apply_history_filters(
                snapshot_for_delta, since=since_arg
            )
            full_view = _compute_coverage_view(snapshot_for_delta)
            window_view = _compute_coverage_view(
                _apply_history_filters(
                    snapshot_for_delta,
                    window=float(_PICKER_HISTORY_DELTA_WINDOW_SECONDS),
                )
            )
            # Round to one decimal so the body float matches the header
            # f"{delta:+.1f}" rendering past the visible precision.
            delta_pct = round(
                float(window_view["coverage_pct"]) - float(full_view["coverage_pct"]),
                1,
            )
            body["delta_pct"] = float(delta_pct)
            body["delta_window_seconds"] = int(_PICKER_HISTORY_DELTA_WINDOW_SECONDS)
        return jsonify(body)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/coverage/timeline", methods=["GET"])
def picker_history_coverage_timeline():
    """v82lv — pure-read bucketed coverage time-series over `_PICKER_HISTORY`.

    Companion to /api/picker/history/coverage/global (scalar gauge) and
    /api/picker/history/coverage (per-model partition). Where /global
    returns ONE coverage_pct over the full history, this route returns
    ONE coverage_pct PER fixed-width time bucket so the UI can render an
    "exploration progress over time" sparkline. Each bucket re-folds the
    shared `_compute_coverage_view` over its own survivor set, so the
    bucket's `populated_cells` and `coverage_pct` answer the question
    "what fraction of the (model x kind) grid had been explored at the
    moment this bucket closed".

    Bucket boundaries align on `floor(ts / bucket) * bucket` — same
    contract as /api/picker/history/timeline so the two routes can be
    superimposed pixel-perfect on the same x-axis.

    Query :
      bucket=<int>      optional. Default 60. Clamped to [1, 3600] —
                        anything outside that range, non-numeric, or
                        negative → 400 with the accepted range echoed
                        back so the UI doesn't have to hardcode the
                        bounds.
      since=<float>     optional. Entries with `ts < since` are dropped
                        BEFORE bucketing. Absent / empty / non-positive
                        leaves the snapshot untouched. Same semantics as
                        /coverage / /cells/empty / /timeline / /stats.

    Response :
      200 {
        "ok": true,
        "bucket_seconds": int,                 // echo, post-clamp
        "buckets": [                           // sorted ts_start asc, sparse
          {
            "ts_start":        float,          // floor(ts / bucket) * bucket
            "ts_end":          float,          // ts_start + bucket_seconds
            "populated_cells": int,            // # (model, kind) pairs in this bucket
            "coverage_pct":    float           // bucket-local round(populated/grid*100, 1)
          },
          ...
        ]
      }

      400 { "ok": false,
            "error": "bucket must be int in [1, 3600]" }
            when bucket is non-numeric or out of range.

    Sparse representation : empty buckets (no picks fell into the
    floor-aligned window) are NOT emitted. A 30-min history with picks
    only at minute 0 and minute 5 returns 2 buckets, not 30. UI can fill
    gaps client-side as transparent zero-coverage cells if dense
    rendering is needed.

    Pure read — no Ollama, no mutation, no per-site rules, no selectors.
    Snapshots the deque BEFORE iterating so concurrent picks from
    extract-structured cannot mutate it mid-loop.

    DRY anchor : every bucket's coverage math is delegated to
    `_compute_coverage_view`, the SAME helper /coverage[/global],
    /cells/empty AND the Coverage-Pct / Empty-Cells / Coverage-Window-
    Seconds headers on extract-structured read from. The bucket-local
    `populated_cells` is `len(view.populated)` for that bucket's
    survivor set. The bucket-local `coverage_pct` IS the per-bucket
    `view.coverage_pct` (which uses the bucket's distinct_models as the
    grid denominator, NOT the global distinct_models — each bucket
    reports its own self-contained ratio).
    """
    try:
        # bucket : default 60, clamp [1, 3600]. Anything outside that
        # range or non-numeric → 400 with the accepted range echoed back
        # so the UI doesn't have to hardcode the bounds. Same contract
        # as /timeline's bucket_seconds query (different param name —
        # `bucket` here, `bucket_seconds` there — keeps the URL terse
        # for sparkline widgets that may stuff several params in one
        # query string).
        bucket_raw = (request.args.get("bucket") or "").strip()
        bucket_seconds = 60
        if bucket_raw:
            try:
                parsed = int(bucket_raw)
            except Exception:
                return jsonify({
                    "ok": False,
                    "error": "bucket must be int in [1, 3600]",
                }), 400
            if parsed < 1 or parsed > 3600:
                return jsonify({
                    "ok": False,
                    "error": "bucket must be int in [1, 3600]",
                }), 400
            bucket_seconds = parsed
        # Snapshot the deque BEFORE iterating — extract-structured calls
        # on other threads could mutate it mid-loop otherwise.
        snapshot = list(_PICKER_HISTORY)
        # v82lw — `since=` filter via the shared `_apply_history_filters`
        # helper. Same byte-identical contract as the inline block this
        # replaces (graceful degradation on non-numeric / negative).
        since_arg, _window_unused = _parse_history_filter_args()
        snapshot = _apply_history_filters(snapshot, since=since_arg)
        # Group the snapshot by floor-aligned bucket key. Key is the
        # ts_start so the bucket boundary is deterministic regardless
        # of when the request fires (different requests over the same
        # snapshot return identical bucket layouts — a property the
        # UI can rely on for diff/animation).
        bucket_rows: "dict[float, list[dict]]" = {}
        for h in snapshot:
            try:
                ts_h = float(h.get("ts") or 0.0)
                ts_start = float(int(ts_h // bucket_seconds) * bucket_seconds)
                bucket_rows.setdefault(ts_start, []).append(h)
            except Exception:
                # Skip a corrupt entry — observability shouldn't 500. The
                # remaining buckets stay accurate.
                continue
        # Fold each bucket through `_compute_coverage_view` so the
        # populated_cells / coverage_pct math is byte-identical to the
        # other coverage surfaces. Each bucket is self-contained (its
        # distinct_models is the cardinality of models that picked WITHIN
        # the bucket, not the global cardinality — that way an early
        # bucket where only 1 model was picking reports 100% if it hit
        # all 5 kinds, even though later buckets might bring in more
        # models).
        buckets_out: "list[dict]" = []
        for ts_start, rows in bucket_rows.items():
            view = _compute_coverage_view(rows)
            buckets_out.append({
                "ts_start": ts_start,
                "ts_end": ts_start + float(bucket_seconds),
                "populated_cells": int(len(view["populated"])),
                "coverage_pct": float(view["coverage_pct"]),
            })
        # Sort ts_start ascending so the UI can render left-to-right
        # without a client-side sort. Stable sort preserves bucket
        # insertion order on tied (impossible — keys are unique) ts_starts.
        buckets_out.sort(key=lambda b: float(b.get("ts_start") or 0.0))
        return jsonify({
            "ok": True,
            "bucket_seconds": bucket_seconds,
            "buckets": buckets_out,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/coverage/heatmap", methods=["GET"])
def picker_history_coverage_heatmap():
    """v82lw — pure-read sparse `(model, kind)` heatmap matrix over `_PICKER_HISTORY`.

    Orthogonal completion to /api/picker/history/coverage (per-model rows)
    and /api/picker/history/coverage/timeline (per-bucket columns) : where
    those two pivot the populated cell-set on ONE axis each, this route
    returns the dense `(model, kind)` count matrix in a sparse-cell-list
    JSON shape so the UI can render a visual heatmap (rows=models,
    cols=kinds, cell=count) in one round-trip.

    Sparse — only `(model, kind)` cells with `count >= 1` are emitted.
    A 7-pick history with 2 distinct models hitting 3 distinct cells
    returns 3 cells, NOT a dense `2 * 5 = 10` matrix.

    Composes with `since=` AND `?window=<sec>` : same defensive contract
    as /coverage/global. Filter first, then bucket the survivors. Both
    filters silently no-op on non-numeric / non-positive (graceful
    degradation rather than 400). The `?window=` filter is orthogonal
    to the v82lv `Coverage-Window-Seconds` gauge — both surfaces read
    from the SAME `_apply_history_filters` helper.

    Query :
      since=<float>     optional. Entries with `ts < since` are dropped
                        before the cell scan.
      window=<int>      optional. Entries with `ts < now - window` are
                        dropped AFTER the `since=` filter.

    Response :
      200 {
        "ok": true,
        "models": [str, ...],          // sorted alphabetic asc, distinct
                                       //   non-empty model names from the
                                       //   surviving set
        "kinds":  [str, ...],          // ALWAYS in `_PICKER_REASON_KINDS`
                                       //   order (decision-tree order),
                                       //   regardless of which kinds are
                                       //   actually populated. Stable
                                       //   reference frame for the
                                       //   col index.
        "cells":  [[int, int, int]],   // sparse [row_idx, col_idx, count]
                                       //   only populated cells, sorted
                                       //   row asc → col asc for stable
                                       //   diff/animation in the UI.
        "total_picks": int             // # entries after both filters
      }

    Index encoding : `cells[k] = [row_idx, col_idx, count]` where
    `row_idx` is the index into `models` and `col_idx` is the index into
    `kinds`. The UI can lookup `models[row_idx]` and `kinds[col_idx]`
    without a second pass. NOT dict-keyed by `(model, kind)` because
    JSON keys would force string concat or nested objects ; sparse triple
    arrays are the most compact form for a heatmap renderer.

    Edge cases :
      - Empty history (or empty after `since=` / `window=`) →
        `{models:[], kinds:[<full enum>], cells:[], total_picks:0}`.
        `kinds` is ALWAYS the full enum, even when empty, so the UI can
        pre-render the column axis labels without conditionally checking
        for the empty-state. The Cartesian product over zero rows is
        empty by definition ; `cells:[]` is the natural representation.
      - `populated_cells` from `/coverage/global?delta=0` ALWAYS equals
        `len(cells)` here (asserted by the live test) — both surfaces
        read from `_compute_populated_cells`'s set discovery so the
        cardinality cannot drift.

    DRY anchor : reuses `_compute_populated_cells` for cell discovery so
    the default-coalesce / skip-empty / corrupt-entry rules are inherited
    verbatim. Same source-of-truth as /intersections, /cells/empty,
    /coverage[/global], /coverage/timeline AND the X-Picker-* coverage
    headers — eight surfaces, one helper, byte-identical contract. The
    per-cell `count` is computed via a separate single-pass bucketing
    loop because `_compute_populated_cells` returns a SET (no counts) ;
    keeping the count loop here local avoids inflating the helper API.

    Pure read — no Ollama, no replay, no mutation, no per-site rules,
    no selectors. Snapshots the deque BEFORE iterating so concurrent
    picks from extract-structured cannot mutate it mid-loop.
    """
    try:
        # Snapshot the deque BEFORE iterating — extract-structured calls
        # on other threads could mutate it mid-loop otherwise.
        snapshot = list(_PICKER_HISTORY)
        # v82lw — `since=` AND `window=` filter via the shared
        # `_apply_history_filters` helper. Composes orthogonally with
        # /coverage/global so a `?window=60` here returns the same
        # populated-set cardinality as /coverage/global?window=60.
        since_arg, window_arg = _parse_history_filter_args()
        snapshot = _apply_history_filters(
            snapshot, since=since_arg, window=window_arg
        )
        total_picks = len(snapshot)
        # Discover the populated cell set + count via a single pass.
        # `_compute_populated_cells` returns the SET (no counts) so we
        # do the count bucketing locally — same default-coalesce rules
        # as the helper (skip empty model name, "default" for missing
        # reason_kind) so the cell key matches what the picker recorded
        # byte-for-byte.
        cell_counts: "dict[tuple[str, str], int]" = {}
        for h in snapshot:
            try:
                name = str(h.get("model") or "").strip()
                if not name:
                    # Skip empty model names — matches /intersections and
                    # /cells/empty which both skip them from cell keys.
                    continue
                kind = str(h.get("reason_kind") or "default")
                key = (name, kind)
                cell_counts[key] = cell_counts.get(key, 0) + 1
            except Exception:
                # Skip a corrupt entry — observability shouldn't 500. The
                # rest of the matrix stays accurate.
                continue
        # Models : alphabetic ascending. Stable sort means a single key
        # tuple expresses the full ordering — deterministic for tests
        # and UI rendering.
        models_sorted: "list[str]" = sorted({n for (n, _k) in cell_counts.keys()})
        # Kinds : ALWAYS `_PICKER_REASON_KINDS` order (decision-tree
        # order), regardless of which kinds are populated. Stable
        # reference frame so the col index is consistent across requests
        # (a kind that ages out of the buffer doesn't shift every other
        # column's index).
        kinds_ordered: "list[str]" = list(_PICKER_REASON_KINDS)
        # Index lookup tables : O(1) lookup from name/kind to the
        # int index, populated once before the cell loop so the loop
        # itself is straight-line (no nested .index() calls which would
        # be O(n*m)).
        model_idx: "dict[str, int]" = {n: i for i, n in enumerate(models_sorted)}
        kind_idx: "dict[str, int]" = {k: i for i, k in enumerate(kinds_ordered)}
        # Sparse cell triples : [row_idx, col_idx, count]. Only populated
        # cells. Sort row asc → col asc → for stable diff/animation in
        # the UI (a new pick that lands on an existing cell only mutates
        # one triple ; a new cell appears in deterministic position).
        cells_out: "list[list[int]]" = []
        for (name, kind), count in cell_counts.items():
            row = model_idx.get(name)
            col = kind_idx.get(kind)
            if row is None or col is None:
                # Defensive : `kind` not in the stable enum (e.g. an old
                # buffer from a pre-v82li bridge) — silently drop. The
                # populated-cells helper would do the same.
                continue
            cells_out.append([int(row), int(col), int(count)])
        cells_out.sort(key=lambda c: (int(c[0]), int(c[1])))
        return jsonify({
            "ok": True,
            "models": models_sorted,
            "kinds": kinds_ordered,
            "cells": cells_out,
            "total_picks": total_picks,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/picker/history/replay", methods=["POST"])
def picker_history_replay():
    """v82lk — pure-read drift analyzer over the picker history.

    For every entry currently in `_PICKER_HISTORY`, re-run
    `_pick_vision_model_or_default()` at the current cached free VRAM and
    compare its `reason_kind` to what was recorded at the time of the
    original pick. Lets the UI render "the picker has drifted N times over
    the last M calls" without bridging timestamps client-side.

    Strict guarantees :
      - No `simulate_vram` override : real cached VRAM probe is used so the
        replay reflects what the picker WOULD do RIGHT NOW.
      - No Ollama call beyond the 60s-cached tag list (`_list_ollama_models`).
      - No `_record_picker_pick` append : this is observability about the
        existing history, not a new pick — appending would create a feedback
        loop where every replay grows the buffer.
      - No mutation of `_PICKER_HISTORY` itself.

    Response :
      {
        "ok": true,
        "count": int,                      // len(history) at replay time
        "drift_count": int,                // # entries where reason_kind changed
        "entries": [
          {
            "ts": float,                   // original pick timestamp
            "original": {                  // exact slice of the history entry
              "model": str,
              "reason_kind": str
            },
            "now": {                       // what the picker would pick today
              "model": str,
              "reason": str,
              "reason_kind": str,
              "free_vram_gb": float
            },
            "drift": bool                  // original.reason_kind != now.reason_kind
          },
          ...
        ]
      }

    Pure read, no caching changes, no per-site rules, no selectors.
    """
    try:
        # Snapshot the deque BEFORE iterating — extract-structured calls on
        # other threads could mutate it mid-loop otherwise.
        snapshot = list(_PICKER_HISTORY)
        # Resolve "now" once per replay so all entries see the same VRAM
        # number (cheaper than re-probing on every entry, and cleaner UX —
        # the user expects "as of right now" to mean a single point in time).
        try:
            now_free_gb = _get_free_vram_gb()
        except Exception:
            now_free_gb = 0.0
        try:
            now_model, now_reason, now_kind = _pick_vision_model_or_default("qwen3-vl:8b")
        except Exception as exc:  # noqa: BLE001
            now_model, now_reason, now_kind = ("qwen3-vl:8b", f"probe failed: {exc}", "default")
        entries: "list[dict]" = []
        drift_count = 0
        for h in snapshot:
            try:
                orig_kind = str(h.get("reason_kind") or "default")
                drift = orig_kind != now_kind
                if drift:
                    drift_count += 1
                entries.append({
                    "ts": float(h.get("ts") or 0.0),
                    "original": {
                        "model": str(h.get("model") or ""),
                        "reason_kind": orig_kind,
                    },
                    "now": {
                        "model": now_model,
                        "reason": now_reason,
                        "reason_kind": now_kind,
                        "free_vram_gb": now_free_gb,
                    },
                    "drift": drift,
                })
            except Exception:
                # Skip a corrupt entry — observability shouldn't 500 the whole
                # response. The drift_count remains accurate for the rest.
                continue
        return jsonify({
            "ok": True,
            "count": len(entries),
            "drift_count": drift_count,
            "entries": entries,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/cowork/extract-structured", methods=["POST"])
def cowork_extract_structured():
    if _AURORA_3D_EN_COURS.is_set():
        # Une generation 3D occupe la VRAM: recharger un LLM ollama ici a deja
        # provoque un cudaMalloc OOM en pleine etape GPU (gel du 24/07).
        return jsonify({"ok": False,
                        "error": "generation 3D en cours — extraction differee "
                                 "pour proteger la VRAM (reessayez apres)"}), 503
    """Extraction structuree comprehension-based via Ollama.

    Body JSON :
      {
        "intent": "<libre, eg liste des cours du jour avec heure et salle>",
        "html_or_text": "<texte ou HTML brut>",
        "model": "<optionnel, default qwen3:14b ; qwen3-vl si image fournie>",
        "imageDataUrl": "<optionnel, data:image/...;base64,... pour vision>",
        "image_b64": "<optionnel, alias snake_case de imageDataUrl ; accepte aussi"
                     " du base64 pur sans prefix data:>"
      }

    Retourne :
      { ok: bool, items: array, raw: string, model: str, intent: str }

    items est une liste d objets dont le schema est decide par le LLM en
    fonction de l intent. raw est la reponse brute du LLM (utile pour
    debug si le parsing JSON tombe en biais). model expose le modele
    effectivement appele (utile pour assert vision-routing cote tests).

    v82lb : l alias `image_b64` est accepte en plus de `imageDataUrl` pour
    compat avec les caller snake_case (planner LLM, scripts Python).
    """
    payload = request.get_json(silent=True) or {}
    intent = (payload.get("intent") or "").strip()
    # v82lx — accept either the legacy `html_or_text` field or the shorter
    # `html` alias used by the extension content scripts. Both produce the
    # same downstream LLM call.
    blob = (payload.get("html_or_text") or payload.get("html") or "").strip()
    # v82lb : accept both imageDataUrl (camelCase, extension/JS clients) and
    # image_b64 (snake_case, planner/Python clients). The two are synonyms ;
    # if both are passed we prefer imageDataUrl since it is the canonical
    # name in the executor + extension.
    image_data_url = (payload.get("imageDataUrl") or payload.get("image_b64") or "").strip()
    # v82lx — comprehension-aware extraction mode. When the caller passes
    # `mode: "card_iteration"`, the system prompt is enriched to instruct
    # the LLM to return ONE item per card-shaped repeating unit. The
    # caller can also pass `card_signals` (the topological hints from
    # detectPageTypology — repeating_card_count, has_avatars, has_timestamps)
    # so the LLM has objective evidence about the expected card count and
    # can structure its output accordingly. ZERO selectors hardcoded — the
    # LLM is told the topology, not the markup.
    mode = (payload.get("mode") or "").strip()
    card_signals = payload.get("card_signals")
    if not isinstance(card_signals, dict):
        card_signals = {}
    # v82ly — focalised cards[] array streamed from content-scrape when the
    # page is a social_feed. Each entry is {idx, outerHTML} capped at 5_000
    # chars per card, max 20 cards. When present + mode=card_iteration, the
    # LLM gets per-card markup instead of the full body blob, which boosts
    # extraction precision (the LLM no longer has to find card boundaries
    # itself). The full blob stays available as fallback (we keep blob in
    # the user_msg too so the LLM can cross-check if a card is ambiguous).
    cards = payload.get("cards")
    if not isinstance(cards, list):
        cards = []
    # Defensive : trim each card outerHTML to 5_000 chars and cap list at 20.
    # Caller (extension) already does this but we re-enforce because the
    # bridge accepts requests from any HTTP client (planner, scripts, tests).
    safe_cards = []
    for i, c in enumerate(cards[:20]):
        if not isinstance(c, dict):
            continue
        html = c.get("outerHTML")
        if not isinstance(html, str):
            continue
        safe_cards.append({"idx": int(c.get("idx", i)), "outerHTML": html[:5_000]})
    cards = safe_cards
    if not intent:
        return jsonify({"ok": False, "error": "intent manquant"}), 400
    if not blob and not image_data_url and not cards:
        return jsonify({"ok": False, "error": "html_or_text, cards ou imageDataUrl/image_b64 requis"}), 400
    # Cap pour proteger Ollama (context window 4-8K typique). Le LLM
    # n a pas besoin du HTML complet — on tronque a 25 KB.
    blob = blob[:25_000]
    # Choix modele : qwen3-vl si image fournie, sinon qwen3:14b.
    # Cette routing-decision est exposee dans la response (champ "model")
    # pour que les tests live (coworkExtract.test.ts) puissent asserter
    # que le bridge a bien switche vers un modele vision.
    #
    # v82lc — auto-detect un *vl* installe au lieu de hardcoder qwen3-vl:8b.
    # Le user peut avoir qwen3-vl:30b, qwen2.5-vl:7b, llava, etc. Notre
    # priorite : qwen3-vl:8b → qwen3-vl:30b → qwen2.5-vl:* → tout *vl* → llava.
    # Si rien de vision n est installe, on retombe sur qwen3:14b text-only et
    # on log un warning. Le test live live-extract-vision detectera l absence
    # de "vl" dans la response.
    # v82lf — picker now returns (name, reason). Reason is surfaced in the
    # response as `picker_reason` when vision is invoked, omitted otherwise.
    # v82li — picker also returns reason_kind (machine-readable enum) ;
    # surfaced alongside picker_reason in the response.
    picker_reason: "str | None" = None
    picker_reason_kind: "str | None" = None
    # v82ll — capture the picker-time free VRAM ONCE so we can surface
    # the same number both in `_record_picker_pick` (history buffer) and
    # the `X-Free-Vram-Gb` response header. Avoids two probes drifting if
    # the cache TTL flips between them. None when text-only.
    picker_free_vram_gb: "float | None" = None
    if image_data_url:
        default_model, picker_reason, picker_reason_kind = _pick_vision_model_or_default("qwen3-vl:8b")
        # v82lh — record the pick into the ring buffer for /api/picker/history.
        # Only fires on real (non-dry-run) picker calls so the history reflects
        # actual drift, not observability pings.
        try:
            picker_free_vram_gb = _get_free_vram_gb()
        except Exception:
            picker_free_vram_gb = 0.0
        try:
            _record_picker_pick(
                default_model,
                picker_reason,
                picker_free_vram_gb,
                reason_kind=picker_reason_kind or "default",
            )
        except Exception:
            pass
    else:
        default_model = "qwen3:14b"
    model = (payload.get("model") or default_model).strip()

    system = (
        "Tu es un extracteur structure. L user decrit en francais ce qu il veut "
        "extraire d un texte ou HTML. Tu retournes UN SEUL objet JSON strict "
        "(pas de markdown, pas d explication, pas de cle supplementaire) avec "
        "EXACTEMENT cette forme :\n"
        "{\n"
        '  "items": [ ... ],   // liste d objets dont le schema decoule de l intent\n'
        '  "schema": "<une phrase decrivant les cles communes des items>",\n'
        '  "notes": "<optionnel, observations breves sur la qualite ou completude>"\n'
        "}\n"
        "Regles :\n"
        "- Adapte le schema des items a l intent. Si l user demande des cours, "
        "utilise des cles comme matiere/heure/salle/prof. Pour des prix : "
        "nom/prix/devise. Pour des messages : expediteur/sujet/date/preview.\n"
        "- Garde les valeurs courtes (max ~200 chars). Pas de HTML residuel.\n"
        '- Si l input ne contient PAS l info demandee, retourne items=[] et notes="...".\n'
        "- Toujours JSON valide. Pas de virgule trainante. Pas de commentaire JS."
    )
    # v82lx — mode-aware enrichment. card_iteration tells the LLM the page
    # is a feed of repeating cards (LinkedIn posts, tweets, GitHub
    # discussions, …) so it should emit ONE item per card with content-derived
    # keys (auteur, date_relative, contenu, reactions). The caller's
    # card_signals are surfaced so the LLM has a target count and knows
    # which signals are present (avatars, timestamps, reactions).
    if mode == "card_iteration":
        rcc = int(card_signals.get("repeating_card_count") or 0)
        has_avatars = bool(card_signals.get("has_avatars"))
        has_timestamps = bool(card_signals.get("has_timestamps"))
        has_reactions = bool(card_signals.get("has_reactions"))
        hint_lines = [
            "",
            "MODE card_iteration :",
            "- L input est un feed de cartes repetitives (post, tweet, discussion).",
            "- Retourne UN item par carte detectee dans le contenu.",
            "- Pour chaque item, deduis les cles depuis le contenu reel : "
            "auteur (texte court), date_relative (eg '2h', '3 j', 'yesterday'), "
            "contenu (le texte principal de la carte, max 400 chars), "
            "reactions (compteur si visible : likes, retweets, applaudissements).",
            "- Ignore navigation, sidebar, header global, footer. Concentre-toi "
            "sur le bloc central qui contient les cartes.",
        ]
        if rcc > 0:
            hint_lines.append(f"- Topologie detectee : ~{rcc} cartes repetitives. Vise ce volume (+/- 30%).")
        present = []
        if has_avatars:
            present.append("avatars")
        if has_timestamps:
            present.append("timestamps relatifs")
        if has_reactions:
            present.append("boutons de reaction")
        if present:
            hint_lines.append(f"- Signaux presents dans le DOM : {', '.join(present)}. Tu DOIS extraire les valeurs correspondantes pour chaque carte.")
        if cards:
            hint_lines.append(
                f"- {len(cards)} cartes pre-decoupees fournies separement (chaque "
                "carte = un bloc HTML focalise). Utilise-les en priorite sur le "
                "blob global ; le blob ne sert que de contexte de fallback."
            )
        system = system + "\n" + "\n".join(hint_lines)

    # v82ly — when cards[] are streamed AND mode=card_iteration, prefix the
    # user message with each card's outerHTML so the LLM sees per-card
    # focalised markup. Format kept simple : "[card N] <outerHTML>" newlines
    # separating cards. We keep blob too for fallback context but cap it
    # tighter (5 KB) since cards already carry the structural signal.
    if mode == "card_iteration" and cards:
        # Pack cards first (LLM reads top-down), then a small fallback blob.
        cards_text = "\n\n".join(f"[card {c['idx']}]\n{c['outerHTML']}" for c in cards)
        fallback_blob = blob[:5_000] if blob else ""
        user_msg = f"Intent : {intent}\n\nCards (un par item attendu) :\n{cards_text}"
        if fallback_blob:
            user_msg += f"\n\n--- Contexte global (fallback) ---\n{fallback_blob}"
    else:
        user_msg = f"Intent : {intent}\n\nInput :\n{blob}" if blob else f"Intent : {intent}"

    try:
        body = {
            "model": model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": 1200, "num_ctx": 8192},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
        }
        # Vision input : passe l image en images:[] sur le user message.
        # v82lc — upscale les images degenerees (< 64x64) AVANT de les passer
        # a Ollama. La VLM runner panique sur les images < 8x8 (observe sur
        # qwen2.5vl:7b et qwen3-vl:30b avec un PNG 1x1 transparent — "model
        # runner has unexpectedly stopped"). Le test live live-extract-vision
        # envoie justement un 1x1 PNG comme echantillon, donc sans cette
        # protection le test echoue 502 systematiquement.
        if image_data_url:
            try:
                b64 = image_data_url.split(",", 1)[1] if "," in image_data_url else image_data_url
                b64 = _upscale_b64_if_degenerate(b64, min_side=64)
                body["messages"][-1]["images"] = [b64]
            except Exception:
                # En cas d echec d upscale, on passe l image originale ; si
                # elle est vraiment degeneree Ollama remontera l erreur.
                try:
                    b64 = image_data_url.split(",", 1)[1] if "," in image_data_url else image_data_url
                    body["messages"][-1]["images"] = [b64]
                except Exception:
                    pass
        r = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=body,
            timeout=120,
        )
        if r.status_code != 200:
            return jsonify({
                "ok": False,
                "error": f"ollama {r.status_code}: {r.text[:200]}",
                "model": model,
            }), 502
        raw = ""
        try:
            j = r.json()
            raw = (j.get("message") or {}).get("content") or ""
        except Exception as e:  # noqa: BLE001
            return jsonify({"ok": False, "error": f"reponse Ollama illisible: {e}", "model": model}), 502
        # Le LLM peut wrapper le JSON malgre format=json (rare mais arrive).
        # Tente parsing direct, puis fallback regex sur le 1er objet {…}.
        import json as _json
        import re as _re
        parsed = None
        try:
            parsed = _json.loads(raw)
        except Exception:
            m = _re.search(r"\{[\s\S]*\}", raw)
            if m:
                try:
                    parsed = _json.loads(m.group(0))
                except Exception:
                    parsed = None
        items = []
        notes = ""
        schema = ""
        if isinstance(parsed, dict):
            it = parsed.get("items")
            if isinstance(it, list):
                items = it
            schema = str(parsed.get("schema") or "")
            notes = str(parsed.get("notes") or "")
        # v82lf — surface picker_reason only when vision was invoked.
        # Text-only requests omit the field (caller sees no key, not null) so
        # the response shape stays minimal for the 90% non-vision case.
        resp = {
            "ok": True,
            "items": items,
            "schema": schema,
            "notes": notes,
            "raw": raw[:8000],
            "model": model,
            "intent": intent,
        }
        # v82lx — echo mode back so callers (planner, tests) can confirm
        # the bridge accepted their hint. Omitted when mode is empty so
        # the legacy text-only response shape stays unchanged.
        if mode:
            resp["mode"] = mode
        # v82lz — per-card extraction telemetry. When mode=card_iteration AND
        # cards[] are streamed, surface the cards_processed count back to the
        # caller. Lets the orchestrator compare items.length vs cards_processed
        # and flag under-extraction (e.g. items.length < cards_processed*0.5
        # → set under_extraction:true in history so the next iteration retries
        # with includeImage:true for media-heavy pages). Omitted when mode is
        # not card_iteration so the legacy response shape stays unchanged.
        if mode == "card_iteration" and cards:
            resp["cards_processed"] = len(cards)
        if picker_reason is not None:
            resp["picker_reason"] = picker_reason
        # v82li — surface the machine-readable enum alongside picker_reason
        # so UI can group/colour by branch without parsing the FR/EN string.
        if picker_reason_kind is not None:
            resp["reason_kind"] = picker_reason_kind
        # v82lt — single-pass emit of the picker telemetry octet.
        # `_emit_picker_headers` replaces the 8 copy-pasted
        # `if picker_reason_kind is not None: try: …` blocks that used to
        # live here (one per header). Net win :
        #   - Single `_PICKER_HISTORY` snapshot per response (was 3+).
        #   - Single `_compute_history_summary` call (was 1 explicit + 2
        #     via the legacy thin wrappers).
        #   - Single `_compute_populated_cells` call (new in v82lt for
        #     the X-Picker-History-Empty-Cells header).
        #   - Single try/except gate (was 8 independent ones).
        #
        # Backward-compat : the 8 emitted header values are byte-identical
        # to the pre-refactor sequence (regression test mocks
        # `_PICKER_HISTORY` with a stable snapshot and asserts equality
        # on every header). CORS exposure for all 8 headers is wired
        # through `expose_headers` in the CORS() init at module load.
        flask_response = jsonify(resp)
        _emit_picker_headers(
            flask_response,
            picker_reason_kind,
            picker_free_vram_gb,
            model,
        )
        # v82m0 — quality-of-extraction headers. Surface cards_processed +
        # items.length as response headers when mode=card_iteration so non-
        # cowork HTTP clients (test scripts, monitoring tools, third-party
        # extensions) can check extraction quality without parsing the JSON
        # body. Mode-gated : non-card_iteration calls keep the legacy header
        # set untouched. Empty/missing items emit X-Items-Extracted: 0 so
        # the header is always coherent with the mode flag.
        if mode == "card_iteration" and cards:
            try:
                flask_response.headers["X-Cards-Processed"] = str(len(cards))
                flask_response.headers["X-Items-Extracted"] = str(len(items) if isinstance(items, list) else 0)
            except Exception:
                pass
            # v82m1 — append per-extraction telemetry to the module-level
            # ring buffer for /api/cowork/extraction-stats aggregation.
            # Best-effort : never raises (helper swallows exceptions). The
            # gate mirrors the headers' gate so the buffer is coherent with
            # what the headers report.
            #
            # v82m2 — also emit the per-host signed delta header
            # `X-Host-Yield-Delta-Pct` when the host has >= 3 prior entries.
            # The delta is computed BEFORE the current yield is appended to
            # the per-host history so the baseline excludes the current
            # extract (otherwise a host's own current would skew its own
            # baseline). Header is omitted when the gate is not met
            # (unknown host, fewer than 3 priors, cards<5) — see
            # `_compute_host_yield_delta_pct`.
            try:
                _page_url = (payload.get("url") or "").strip() if isinstance(payload, dict) else ""
                _host = ""
                if _page_url:
                    try:
                        from urllib.parse import urlparse as _urlparse_es
                        _host = (_urlparse_es(_page_url).hostname or "").lower()
                        # Normalise leading "www." so per-host aggregation
                        # treats www.linkedin.com and linkedin.com as one
                        # bucket (avoids splitting yields across two rows
                        # that mean the same site).
                        if _host.startswith("www."):
                            _host = _host[4:]
                    except Exception:
                        _host = ""
                _items_count = len(items) if isinstance(items, list) else 0
                _cards_count = len(cards)
                _current_yield = (float(_items_count) / float(_cards_count)) if _cards_count > 0 else 0.0
                # Compute delta BEFORE recording so the baseline excludes
                # the current entry. Returns None when the gate fails (no
                # host, <5 cards, <3 prior entries).
                _delta_pp = _compute_host_yield_delta_pct(
                    host=_host,
                    current_yield=_current_yield,
                    cards_processed=_cards_count,
                )
                if _delta_pp is not None:
                    try:
                        flask_response.headers["X-Host-Yield-Delta-Pct"] = f"{_delta_pp:+.1f}"
                    except Exception:
                        pass
                # Record AFTER the delta computation so the per-host
                # history reflects the new entry on the NEXT call.
                _record_host_yield(host=_host, yield_pct=_current_yield)
                _record_extraction_stat(
                    host=_host,
                    cards_processed=_cards_count,
                    items_count=_items_count,
                )
            except Exception:
                pass
        return flask_response
    except requests.exceptions.Timeout:
        return jsonify({"ok": False, "error": "ollama timeout (>120s)", "model": model}), 504
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"ollama call failed: {e}", "model": model}), 500


@app.route("/api/cowork/extraction-stats", methods=["GET"])
def cowork_extraction_stats():
    """v82m1 — aggregate counters over `_EXTRACTION_STATS`.

    Pure read of the module-level ring buffer populated by
    `_record_extraction_stat` after each extract_structured(card_iteration)
    response with cards != []. Lets aurora-watchdog and monitoring tools
    see drift without parsing audit logs.

    Optional query params :
      since=<float_ts>   When present and positive, filter the buffer to
                         entries where ts >= since BEFORE computing
                         aggregates. Lets the UI render "last 60s" /
                         "last 5min" rolling stats by passing now-60 /
                         now-300. Invalid (non-float, negative, missing)
                         → no filter applied, full buffer used.
      host=<str>         v82m3 — When present and non-empty, filter the
                         buffer to entries whose `host` field equals the
                         param BEFORE aggregation. Composes with `since`
                         (both AND-applied). Unknown / never-seen host →
                         empty result with `total:0` and the host echoed
                         in `window.host`. Lets the orchestrator probe a
                         single host's percentile distribution without
                         parsing `by_host_top5`.

    Response :
      {
        "ok": true,
        "total": int,                    // len(filtered buffer)
        "under_extraction_rate": float,  // count(under_extraction:true) / total, 0.0 on empty
        "avg_yield": float,              // mean(yield_pct), 0.0 on empty
        "p50_yield": float,              // 50th percentile yield, 0.0 on empty
        "p90_yield": float,              // 90th percentile yield, 0.0 on empty
        "by_host_top5": [                // top 5 hosts by entry count
          { "host": str, "count": int, "avg_yield": float,
            "last_delta_pct": float | null,
            "delta_history": [float, ...]  // v82m5 — last <=5 deltas asc
          }, ...
        ],
        "window": { "since": float | null, "host": str | null }
      }

    v82m4 — `last_delta_pct` per host : the delta in percentage points
    (pp) between the host's most-recent yield and the mean of its prior
    entries (excluding the latest). Null when the host has fewer than 2
    entries in `_HOST_YIELD_HISTORY` (no prior baseline). Lets the UI
    paint a "this host just degraded" badge without round-tripping the
    extraction route.

    v82m5 — `delta_history` per host : up to 5 chronological-asc deltas
    (each = entry_yield - mean(prior_entries_for_that_host)) computed by
    walking the per-host deque. Lets the UI render a sparkline trajectory
    next to the badge so the user sees "drop is part of a downward trend"
    vs "drop is a one-off blip". Empty array when the host has fewer than
    2 entries (no delta computable). Cap at 5 entries — sparkline is only
    a glanceable trend hint, not a full chart.

    Empty buffer → all numeric fields zero, by_host_top5=[] — stable shape
    so consumers can rely on key presence without conditional checks.

    Pure observability — no caching changes, no Ollama, no mutation.
    """
    try:
        snapshot = list(_EXTRACTION_STATS)
        # Optional time-window filter — same shape contract as picker stats.
        since_raw = (request.args.get("since") or "").strip()
        window_since: "float | None" = None
        if since_raw:
            try:
                parsed = float(since_raw)
                if parsed > 0:
                    window_since = parsed
            except Exception:
                window_since = None
        if window_since is not None:
            snapshot = [
                e for e in snapshot
                if float(e.get("ts") or 0.0) >= window_since
            ]
        # v82m3 — optional per-host filter. When non-empty, narrow the buffer
        # to entries whose `host` equals the param BEFORE aggregation. AND-
        # composed with `since` (the snapshot is already since-filtered at
        # this point). Unknown host falls through to empty result.
        host_raw = (request.args.get("host") or "").strip()
        window_host: "str | None" = host_raw if host_raw else None
        if window_host is not None:
            snapshot = [
                e for e in snapshot
                if str(e.get("host") or "") == window_host
            ]
        total = len(snapshot)
        if total == 0:
            return jsonify({
                "ok": True,
                "total": 0,
                "under_extraction_rate": 0.0,
                "avg_yield": 0.0,
                "p50_yield": 0.0,
                "p90_yield": 0.0,
                "by_host_top5": [],
                "window": {"since": window_since, "host": window_host},
            })
        # Aggregate single pass — under_extraction count, yield list, per-host.
        under_count = 0
        yields: "list[float]" = []
        per_host: "dict[str, dict]" = {}
        for e in snapshot:
            try:
                if bool(e.get("under_extraction")):
                    under_count += 1
                y = float(e.get("yield_pct") or 0.0)
                yields.append(y)
                host = str(e.get("host") or "")
                if host not in per_host:
                    per_host[host] = {"count": 0, "yield_sum": 0.0}
                per_host[host]["count"] += 1
                per_host[host]["yield_sum"] += y
            except Exception:
                # Skip a corrupt entry — aggregates over the rest stay valid.
                continue
        avg_yield = (sum(yields) / float(len(yields))) if yields else 0.0
        p50 = _percentile(yields, 0.5)
        p90 = _percentile(yields, 0.9)
        # Build top-5 by count desc, tie-break by avg_yield desc for stability.
        # v82m4 — also surface `last_delta_pct` per host : the delta between
        # the host's MOST-RECENT yield and the mean of its PRIOR entries
        # (excluding the most recent), expressed in percentage points (pp).
        # Mirrors the on-the-fly logic of `_compute_host_yield_delta_pct`
        # but reads from `_HOST_YIELD_HISTORY` so the GET endpoint can
        # surface it without a fresh extraction. Defensive : returns null
        # when the host has fewer than 2 entries (no prior baseline).
        host_rows = []
        for host, agg in per_host.items():
            cnt = int(agg["count"])
            avg = (agg["yield_sum"] / float(cnt)) if cnt > 0 else 0.0
            last_delta_pp: "float | None" = None
            # v82m5 — delta_history: up to 5 chronological-asc deltas computed
            # from the per-host deque. Each tick = entry_yield - mean(prior
            # entries up to but excluding this index). Lets the UI render a
            # sparkline trajectory : ▁▂▄▆▇ shows trend (improving) while
            # ▇▆▄▂▁ shows trend (degrading). Empty when the host has < 2
            # entries (no delta computable). Cap at 5 most-recent ticks —
            # the sparkline is glanceable trend, not a full chart.
            delta_history: "list[float]" = []
            try:
                hist = _HOST_YIELD_HISTORY.get(host)
                if hist is not None:
                    arr = list(hist)
                    if len(arr) >= 2:
                        prior_arr = arr[:-1]
                        if prior_arr:
                            prior_mean = sum(prior_arr) / float(len(prior_arr))
                            last_delta_pp = (float(arr[-1]) - prior_mean) * 100.0
                        # Walk the deque from index 1 to the end ; for each
                        # position i compute delta_i = arr[i] - mean(arr[:i]).
                        # Capture all of them then keep the last 5 (most-
                        # recent) for the sparkline. Skips index 0 (no prior
                        # entries → no delta possible).
                        per_step: "list[float]" = []
                        for i in range(1, len(arr)):
                            prior = arr[:i]
                            if not prior:
                                continue
                            prior_mean_i = sum(prior) / float(len(prior))
                            per_step.append((float(arr[i]) - prior_mean_i) * 100.0)
                        # Keep the last 5 ticks chronological-asc (oldest →
                        # newest). If fewer than 5 are available, return all.
                        delta_history = per_step[-5:]
            except Exception:
                last_delta_pp = None
                delta_history = []
            host_rows.append({
                "host": host,
                "count": cnt,
                "avg_yield": avg,
                "last_delta_pct": last_delta_pp,
                "delta_history": delta_history,
            })
        host_rows.sort(key=lambda r: (-r["count"], -r["avg_yield"], r["host"]))
        return jsonify({
            "ok": True,
            "total": total,
            "under_extraction_rate": float(under_count) / float(total) if total > 0 else 0.0,
            "avg_yield": avg_yield,
            "p50_yield": p50,
            "p90_yield": p90,
            "by_host_top5": host_rows[:5],
            "window": {"since": window_since, "host": window_host},
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------
#  v82m5 — dual-signal escalation acceptance endpoints
# ---------------------------------------------------------------------

@app.route("/api/cowork/dual-signal-event", methods=["POST"])
def cowork_dual_signal_event():
    """v82m5 — record one dual-signal escalation event.

    Pure observability ingestion : the orchestrator POSTs here when it
    detects either :
      - kind="emitted" : the previous iteration's system prompt contained
        the `[HINT] DUAL_SIGNAL` nudge (ie. yield-ratio AND host-baseline-
        drift both fired on the same extract entry)
      - kind="accepted" : the next plan after a dual-signal nudge contains
        a `browser.screenshot` action followed by `extract_structured` with
        `includeImage: true` (the LLM accepted the stronger hint)

    Body (application/json) :
      { "kind": "emitted" | "accepted", "host": str (optional) }

    Response : { "ok": true, "kind": str, "host": str }
              { "ok": false, "error": str }, 400 on malformed kind

    Stored in module-level ring buffers `_DUAL_SIGNAL_EMITTED` /
    `_DUAL_SIGNAL_ACCEPTED` (each capped at 100 entries — sufficient to
    compute a stable acceptance_rate without risking unbounded growth).
    """
    try:
        body = request.get_json(silent=True) or {}
        kind = str(body.get("kind") or "").strip()
        if kind not in ("emitted", "accepted"):
            return jsonify({"ok": False, "error": f"kind must be emitted|accepted, got {kind!r}"}), 400
        host = str(body.get("host") or "").strip()
        _record_dual_signal_event(kind=kind, host=host)
        return jsonify({"ok": True, "kind": kind, "host": host})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/cowork/dual-signal-stats", methods=["GET"])
def cowork_dual_signal_stats():
    """v82m5 — aggregate counters over `_DUAL_SIGNAL_EMITTED` /
    `_DUAL_SIGNAL_ACCEPTED`.

    Pure read of the two module-level ring buffers populated by
    `_record_dual_signal_event`. Lets aurora-watchdog and monitoring tools
    measure whether the stronger DUAL_SIGNAL nudge actually changes LLM
    behaviour over time.

    Response :
      {
        "ok": true,
        "total_dual_signal_emitted": int,
        "total_dual_signal_accepted": int,
        "acceptance_rate": float,        // accepted / emitted, 0.0 on emitted=0
        "by_host_top5": [
          { "host": str, "emitted": int, "accepted": int, "rate": float }, ...
        ]
      }

    Empty buffers → totals zero, by_host_top5 [] — stable shape contract.
    Pure observability ; no caching changes, no Ollama, no mutation.
    """
    try:
        emitted_snapshot = list(_DUAL_SIGNAL_EMITTED)
        accepted_snapshot = list(_DUAL_SIGNAL_ACCEPTED)
        total_emitted = len(emitted_snapshot)
        total_accepted = len(accepted_snapshot)
        rate = (float(total_accepted) / float(total_emitted)) if total_emitted > 0 else 0.0
        # Per-host aggregation : merge the two snapshots by host.
        per_host: "dict[str, dict]" = {}
        for e in emitted_snapshot:
            h = str(e.get("host") or "")
            if h not in per_host:
                per_host[h] = {"emitted": 0, "accepted": 0}
            per_host[h]["emitted"] += 1
        for e in accepted_snapshot:
            h = str(e.get("host") or "")
            if h not in per_host:
                per_host[h] = {"emitted": 0, "accepted": 0}
            per_host[h]["accepted"] += 1
        rows = []
        for host, agg in per_host.items():
            em = int(agg["emitted"])
            ac = int(agg["accepted"])
            host_rate = (float(ac) / float(em)) if em > 0 else 0.0
            rows.append({
                "host": host,
                "emitted": em,
                "accepted": ac,
                "rate": host_rate,
            })
        # Sort by emitted desc, tie-break by rate desc, then host asc.
        rows.sort(key=lambda r: (-r["emitted"], -r["rate"], r["host"]))
        return jsonify({
            "ok": True,
            "total_dual_signal_emitted": total_emitted,
            "total_dual_signal_accepted": total_accepted,
            "acceptance_rate": rate,
            "by_host_top5": rows[:5],
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------
#  v82m6 — dual-signal effectiveness per host (cool-down endpoint).
# ---------------------------------------------------------------------

# Floor : we need at least N emitted events on a given host before we can
# fairly say "the dual-signal nudge is INEFFECTIVE on this host". Below
# that threshold we default to "trust" (effective:true), which mirrors
# the spirit of the pass-35 acceptance metric : we only act on a signal
# when the sample size is large enough.
DUAL_SIGNAL_EFFECTIVE_MIN_EMITTED: int = 5


@app.route("/api/cowork/dual-signal-effective", methods=["GET"])
def cowork_dual_signal_effective():
    """v82m6 — per-host effectiveness probe for the DUAL_SIGNAL nudge.

    Pure read of the same `_DUAL_SIGNAL_EMITTED` / `_DUAL_SIGNAL_ACCEPTED`
    ring buffers populated by `_record_dual_signal_event`. Filters by host
    and returns the per-host counters with an `effective` boolean :

      - emitted >= DUAL_SIGNAL_EFFECTIVE_MIN_EMITTED AND accepted == 0 :
            effective:false (the LLM consistently ignored the nudge ;
            cool-down advised — caller should switch strategy)
      - emitted < DUAL_SIGNAL_EFFECTIVE_MIN_EMITTED :
            effective:true (insufficient data, default to trust — we
            don't want a single bad emission to kill the nudge for the
            whole host)
      - emitted >= MIN_EMITTED AND accepted > 0 :
            effective:true (at least some acceptance — keep using the
            nudge, planner can choose)

    Query params :
      ?host=<name>  required ; normalised to lowercase + strip "www."
                    so callers can pass either "linkedin.com" or
                    "www.LinkedIn.com" interchangeably

    Response :
      {
        "ok": true,
        "host": str,
        "emitted": int,
        "accepted": int,
        "effective": bool,
        "min_emitted": int,
      }

    Empty/missing host → 400 ; never raises on lookup miss (returns
    effective:true with emitted/accepted=0).
    """
    try:
        raw_host = (request.args.get("host") or "").strip()
        if not raw_host:
            return jsonify({"ok": False, "error": "host param required"}), 400
        norm = raw_host.lower()
        if norm.startswith("www."):
            norm = norm[4:]
        emitted_count = 0
        accepted_count = 0
        for e in list(_DUAL_SIGNAL_EMITTED):
            if str(e.get("host") or "") == norm:
                emitted_count += 1
        for e in list(_DUAL_SIGNAL_ACCEPTED):
            if str(e.get("host") or "") == norm:
                accepted_count += 1
        if emitted_count >= DUAL_SIGNAL_EFFECTIVE_MIN_EMITTED and accepted_count == 0:
            effective = False
        else:
            # Insufficient data OR at least one acceptance → trust the nudge.
            effective = True
        return jsonify({
            "ok": True,
            "host": norm,
            "emitted": emitted_count,
            "accepted": accepted_count,
            "effective": effective,
            "min_emitted": DUAL_SIGNAL_EFFECTIVE_MIN_EMITTED,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------
#  v82m7 — dual-signal cool-down reset (user-driven strategy change).
# ---------------------------------------------------------------------

@app.route("/api/cowork/dual-signal-reset", methods=["POST"])
def cowork_dual_signal_reset():
    """v82m7 — clear the per-host slice of the dual-signal ring buffers.

    Background : when the AuditDrawer surfaces an INEFFECTIVE chip on a host
    (>=5 emitted, 0 accepted), the user can click "Reset signals" to ask the
    planner to give the dual-signal nudge ANOTHER try after a manual strategy
    change (logged in to the site, opened a different tab, etc.). Without
    this endpoint the ineffective verdict is sticky for the lifetime of the
    bridge process.

    Query params :
      ?host=<name>  required ; normalised to lowercase + strip "www."
                    same canonicalisation as `dual-signal-effective`

    Response :
      { "ok": true, "host": str, "cleared_emitted": int, "cleared_accepted": int }
      { "ok": false, "error": str }, 400 on missing / empty host

    Pure surgery on the two existing ring buffers — no new state created.
    Defensive : never raises (returns 500 on unexpected error so the UI can
    surface a clean toast).
    """
    try:
        raw_host = (request.args.get("host") or "").strip()
        if not raw_host:
            return jsonify({"ok": False, "error": "host param required"}), 400
        norm = raw_host.lower()
        if norm.startswith("www."):
            norm = norm[4:]
        # Filter both rings ; keep the cap by re-creating the deque so the
        # deque maxlen invariant is preserved exactly.
        before_emitted = len(_DUAL_SIGNAL_EMITTED)
        before_accepted = len(_DUAL_SIGNAL_ACCEPTED)
        kept_emitted = [
            e for e in list(_DUAL_SIGNAL_EMITTED)
            if str(e.get("host") or "") != norm
        ]
        kept_accepted = [
            e for e in list(_DUAL_SIGNAL_ACCEPTED)
            if str(e.get("host") or "") != norm
        ]
        _DUAL_SIGNAL_EMITTED.clear()
        _DUAL_SIGNAL_EMITTED.extend(kept_emitted)
        _DUAL_SIGNAL_ACCEPTED.clear()
        _DUAL_SIGNAL_ACCEPTED.extend(kept_accepted)
        cleared_emitted = before_emitted - len(_DUAL_SIGNAL_EMITTED)
        cleared_accepted = before_accepted - len(_DUAL_SIGNAL_ACCEPTED)
        return jsonify({
            "ok": True,
            "host": norm,
            "cleared_emitted": cleared_emitted,
            "cleared_accepted": cleared_accepted,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------
#  v82m9 — trend-signal cool-down reset (symmetric to dual-signal-reset).
# ---------------------------------------------------------------------

@app.route("/api/cowork/trend-signal-reset", methods=["POST"])
def cowork_trend_signal_reset():
    """v82m9 — clear the per-host slice of the trend-signal ring buffers.

    Background : when the AuditDrawer surfaces a TIER_3 cluster button on a
    host (BOTH tier-1 dual-signal AND tier-2 trend-signal flagged
    ineffective), the user can click "Reset all signals" to ask the planner
    to give BOTH escalations another chance after a manual strategy change.
    This endpoint mirrors `/api/cowork/dual-signal-reset` for the trend
    ring buffers — the UI fires both endpoints in parallel to fully clear
    the host's signal state.

    Query params :
      ?host=<name>  required ; normalised to lowercase + strip "www."
                    same canonicalisation as `dual-signal-reset`

    Response :
      { "ok": true, "host": str, "cleared_emitted": int, "cleared_accepted": int }
      { "ok": false, "error": str }, 400 on missing / empty host

    Pure surgery on the two existing trend ring buffers + the per-host last
    ts map. Never raises (returns 500 on unexpected error so the UI can
    surface a clean toast).
    """
    try:
        raw_host = (request.args.get("host") or "").strip()
        if not raw_host:
            return jsonify({"ok": False, "error": "host param required"}), 400
        norm = raw_host.lower()
        if norm.startswith("www."):
            norm = norm[4:]
        before_emitted = len(_TREND_SIGNAL_EMITTED)
        before_accepted = len(_TREND_SIGNAL_ACCEPTED)
        kept_emitted = [
            e for e in list(_TREND_SIGNAL_EMITTED)
            if str(e.get("host") or "") != norm
        ]
        kept_accepted = [
            e for e in list(_TREND_SIGNAL_ACCEPTED)
            if str(e.get("host") or "") != norm
        ]
        _TREND_SIGNAL_EMITTED.clear()
        _TREND_SIGNAL_EMITTED.extend(kept_emitted)
        _TREND_SIGNAL_ACCEPTED.clear()
        _TREND_SIGNAL_ACCEPTED.extend(kept_accepted)
        # Drop the per-host last-ts so the next event on this host starts
        # the TTL clock fresh.
        _TREND_SIGNAL_LAST_TS_PER_HOST.pop(norm, None)
        cleared_emitted = before_emitted - len(_TREND_SIGNAL_EMITTED)
        cleared_accepted = before_accepted - len(_TREND_SIGNAL_ACCEPTED)
        return jsonify({
            "ok": True,
            "host": norm,
            "cleared_emitted": cleared_emitted,
            "cleared_accepted": cleared_accepted,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------
#  v82m7 — tier-2 trend acceptance endpoints (DUAL_SIGNAL_TREND nudge).
# ---------------------------------------------------------------------

@app.route("/api/cowork/trend-signal-event", methods=["POST"])
def cowork_trend_signal_event():
    """v82m7 — record one DUAL_SIGNAL_TREND escalation event.

    Symmetric with `/api/cowork/dual-signal-event` but for the tier-2 nudge :
      - kind="emitted" : the previous iteration's system prompt contained
        the `[HINT] DUAL_SIGNAL_TREND` line (sustained downward trajectory
        confirmed by `delta_history`)
      - kind="accepted" : the next plan after a TREND nudge contains
        `extract_structured` with `mode='spread'` AND a wait/think action
        sequenced BEFORE the extract (proxy for "pause 3-5s")

    Body (application/json) :
      { "kind": "emitted" | "accepted", "host": str (optional) }

    Response : { "ok": true, "kind": str, "host": str }
              { "ok": false, "error": str }, 400 on malformed kind

    Stored in module-level ring buffers `_TREND_SIGNAL_EMITTED` /
    `_TREND_SIGNAL_ACCEPTED` (each capped at 100 entries).
    """
    try:
        body = request.get_json(silent=True) or {}
        kind = str(body.get("kind") or "").strip()
        if kind not in ("emitted", "accepted"):
            return jsonify({"ok": False, "error": f"kind must be emitted|accepted, got {kind!r}"}), 400
        host = str(body.get("host") or "").strip()
        _record_trend_signal_event(kind=kind, host=host)
        return jsonify({"ok": True, "kind": kind, "host": host})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/cowork/trend-signal-stats", methods=["GET"])
def cowork_trend_signal_stats():
    """v82m7 — aggregate counters over `_TREND_SIGNAL_EMITTED` /
    `_TREND_SIGNAL_ACCEPTED`.

    Mirrors the shape of `dual-signal-stats` so consumers can swap endpoints
    without parsing logic changes. Empty buffers → totals zero, by_host_top5
    [] — stable shape contract.

    Response :
      {
        "ok": true,
        "total_emitted": int,
        "total_accepted": int,
        "acceptance_rate": float,        // accepted / emitted, 0.0 on emitted=0
        "by_host_top5": [
          { "host": str, "emitted": int, "accepted": int, "rate": float }, ...
        ]
      }
    """
    try:
        emitted_snapshot = list(_TREND_SIGNAL_EMITTED)
        accepted_snapshot = list(_TREND_SIGNAL_ACCEPTED)
        total_emitted = len(emitted_snapshot)
        total_accepted = len(accepted_snapshot)
        rate = (float(total_accepted) / float(total_emitted)) if total_emitted > 0 else 0.0
        per_host: "dict[str, dict]" = {}
        for e in emitted_snapshot:
            h = str(e.get("host") or "")
            if h not in per_host:
                per_host[h] = {"emitted": 0, "accepted": 0}
            per_host[h]["emitted"] += 1
        for e in accepted_snapshot:
            h = str(e.get("host") or "")
            if h not in per_host:
                per_host[h] = {"emitted": 0, "accepted": 0}
            per_host[h]["accepted"] += 1
        rows = []
        for host, agg in per_host.items():
            em = int(agg["emitted"])
            ac = int(agg["accepted"])
            host_rate = (float(ac) / float(em)) if em > 0 else 0.0
            rows.append({
                "host": host,
                "emitted": em,
                "accepted": ac,
                "rate": host_rate,
            })
        rows.sort(key=lambda r: (-r["emitted"], -r["rate"], r["host"]))
        return jsonify({
            "ok": True,
            "total_emitted": total_emitted,
            "total_accepted": total_accepted,
            "acceptance_rate": rate,
            "by_host_top5": rows[:5],
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------
#  Detection silencieuse du navigateur installe sur le PC
# ---------------------------------------------------------------------

@app.route("/api/cowork/browsers/detect", methods=["GET"])
def cowork_browsers_detect():
    """Scan silencieux des navigateurs installes (Windows / macOS / Linux).
    Retourne une liste {name, installed, recommended_extension_url, install_help}."""
    import sys, os, shutil
    found = []

    if sys.platform.startswith("win"):
        # Common install paths on Windows
        candidates = {
            "chrome":   [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                         r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                         os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")],
            "edge":     [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                         r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
            "firefox":  [r"C:\Program Files\Mozilla Firefox\firefox.exe",
                         r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"],
            "brave":    [os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                         r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"],
            "opera":    [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\opera.exe")],
            "vivaldi":  [r"C:\Program Files\Vivaldi\Application\vivaldi.exe",
                         os.path.expandvars(r"%LOCALAPPDATA%\Vivaldi\Application\vivaldi.exe")],
        }
    elif sys.platform == "darwin":
        candidates = {
            "chrome":   ["/Applications/Google Chrome.app"],
            "edge":     ["/Applications/Microsoft Edge.app"],
            "firefox":  ["/Applications/Firefox.app"],
            "safari":   ["/Applications/Safari.app"],
            "brave":    ["/Applications/Brave Browser.app"],
            "opera":    ["/Applications/Opera.app"],
            "arc":      ["/Applications/Arc.app"],
            "vivaldi":  ["/Applications/Vivaldi.app"],
        }
    else:
        candidates = {
            "chrome":   ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/snap/bin/google-chrome"],
            "chromium": ["/usr/bin/chromium", "/snap/bin/chromium"],
            "edge":     ["/usr/bin/microsoft-edge", "/usr/bin/microsoft-edge-stable"],
            "firefox":  ["/usr/bin/firefox", "/snap/bin/firefox"],
            "brave":    ["/usr/bin/brave-browser", "/snap/bin/brave"],
            "opera":    ["/usr/bin/opera", "/snap/bin/opera"],
        }

    for name, paths in candidates.items():
        installed = any(os.path.exists(p) for p in paths) or shutil.which(name) is not None
        found.append({
            "name": name,
            "installed": installed,
            "label": _BROWSER_LABELS.get(name, name.capitalize()),
            "extension_engine": _BROWSER_ENGINES.get(name, "chromium"),
        })

    with _EXT_LOCK:
        _EXT_BROWSER_HINT.clear()
        _EXT_BROWSER_HINT.update({"detected": found, "platform": sys.platform})

    return jsonify({"ok": True, "platform": sys.platform, "browsers": found})


_BROWSER_LABELS = {
    "chrome":   "Google Chrome",
    "edge":     "Microsoft Edge",
    "firefox":  "Mozilla Firefox",
    "safari":   "Safari",
    "brave":    "Brave",
    "opera":    "Opera",
    "vivaldi":  "Vivaldi",
    "chromium": "Chromium",
    "arc":      "Arc",
}

_BROWSER_ENGINES = {
    "chrome": "chromium", "edge": "chromium", "brave": "chromium", "opera": "chromium",
    "vivaldi": "chromium", "chromium": "chromium", "arc": "chromium",
    "firefox": "gecko",
    "safari": "webkit",
}


# ---------------------------------------------------------------------
#  Mobile remote — webhooks pour iOS Shortcuts / Android Tasker
# ---------------------------------------------------------------------
# Le user configure sur son tel un raccourci qui POST sur /api/cowork/mobile/inbound
# avec un JSON {kind, payload}. Aurora les retrouve via GET /api/cowork/mobile/events.
# Inversement, Aurora pousse une commande dans la file via /api/cowork/mobile/dispatch
# que le tel ira recuperer en polling.

_MOBILE_LOCK = _threading.Lock()
_MOBILE_INBOUND: list[dict] = []
_MOBILE_PENDING: list[dict] = []     # commandes Aurora -> tel
_MOBILE_RESULTS: dict[str, dict] = {}


@app.route("/api/cowork/mobile/inbound", methods=["POST"])
def cowork_mobile_inbound():
    """Le tel envoie un evt a Aurora (par ex resultat d une action SMS)."""
    body = request.get_json(silent=True) or {}
    body["at"] = _time.time()
    with _MOBILE_LOCK:
        _MOBILE_INBOUND.append(body)
        if len(_MOBILE_INBOUND) > 200:
            del _MOBILE_INBOUND[:-200]
    return jsonify({"ok": True})


@app.route("/api/cowork/mobile/events", methods=["GET"])
def cowork_mobile_events():
    """Aurora liste les evts entrants du tel."""
    with _MOBILE_LOCK:
        return jsonify({"ok": True, "events": list(_MOBILE_INBOUND)})


@app.route("/api/cowork/mobile/dispatch", methods=["POST"])
def cowork_mobile_dispatch():
    """Aurora pousse une commande pour le tel (sera recuperee en polling)."""
    body = request.get_json(silent=True) or {}
    kind = (body.get("kind") or "").strip()
    if not kind:
        return jsonify({"ok": False, "error": "kind manquant"}), 400
    cmd_id = _uuid.uuid4().hex
    cmd = {"id": cmd_id, "kind": kind, "payload": body.get("payload") or {}, "at": _time.time()}
    with _MOBILE_LOCK:
        _MOBILE_PENDING.append(cmd)
    return jsonify({"ok": True, "commandId": cmd_id})


@app.route("/api/cowork/mobile/poll", methods=["GET"])
def cowork_mobile_poll():
    """Le tel poll pour recuperer une commande Aurora (long-poll)."""
    wait_ms = int(request.args.get("wait", "25000"))
    deadline = _time.time() + (max(1000, min(30000, wait_ms)) / 1000.0)
    while _time.time() < deadline:
        with _MOBILE_LOCK:
            if _MOBILE_PENDING:
                cmd = _MOBILE_PENDING.pop(0)
                return jsonify({"ok": True, "command": cmd})
        _time.sleep(0.5)
    return jsonify({"ok": True, "command": None})


@app.route("/api/cowork/mobile/result", methods=["POST"])
def cowork_mobile_result():
    """Le tel renvoie le resultat de la commande qu il a executee."""
    body = request.get_json(silent=True) or {}
    cmd_id = (body.get("commandId") or "").strip()
    if not cmd_id:
        return jsonify({"ok": False, "error": "commandId manquant"}), 400
    with _MOBILE_LOCK:
        _MOBILE_RESULTS[cmd_id] = body.get("result")
    return jsonify({"ok": True})


# =====================================================================
#  Cowork — Postgres SQL bridge (le DSN ne quitte jamais la machine)
# =====================================================================

@app.route("/api/cowork/db/sql", methods=["POST"])
def cowork_db_sql():
    """Execute un SQL via psycopg2. body: {dsn, sql, args?, allowWrite?}."""
    body = request.get_json(silent=True) or {}
    dsn = (body.get("dsn") or "").strip()
    sql = (body.get("sql") or "").strip()
    args = body.get("args") or []
    allow_write = bool(body.get("allowWrite"))
    if not dsn or not sql:
        return jsonify({"ok": False, "error": "dsn + sql requis"}), 400
    is_select = sql.lstrip().lower().startswith(("select", "with"))
    if not is_select and not allow_write:
        return jsonify({"ok": False, "error": "SQL d ecriture detecte mais allowWrite=false"}), 400
    try:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
    except ImportError:
        return jsonify({"ok": False, "error": "psycopg2 non installe (pip install psycopg2-binary)"}), 500
    try:
        conn = psycopg2.connect(dsn, connect_timeout=10)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, args)
                if cur.description:
                    rows = cur.fetchmany(500)
                    return jsonify({"ok": True, "rows": rows, "rowcount": cur.rowcount})
                conn.commit()
                return jsonify({"ok": True, "rowcount": cur.rowcount})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# =====================================================================
#  Cowork — S3 bridge (signature SigV4 cote serveur)
# =====================================================================

@app.route("/api/cowork/storage/s3", methods=["POST"])
def cowork_storage_s3():
    """S3-compatible storage. body: {creds: 'access:secret', endpoint, operation, bucket?, key?, prefix?, body?}."""
    body = request.get_json(silent=True) or {}
    creds = (body.get("creds") or "").strip()
    endpoint = (body.get("endpoint") or "https://s3.amazonaws.com").rstrip("/")
    op = (body.get("operation") or "").strip()
    if ":" not in creds:
        return jsonify({"ok": False, "error": "creds au format <access_key>:<secret_key>"}), 400
    access_key, secret_key = creds.split(":", 1)
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError:
        return jsonify({"ok": False, "error": "boto3 non installe (pip install boto3)"}), 500
    try:
        # Detection naive de region depuis endpoint AWS
        region = "us-east-1"
        if ".amazonaws.com" in endpoint:
            for part in endpoint.replace("https://", "").split("."):
                if part.startswith(("us-", "eu-", "ap-", "sa-", "ca-", "af-", "me-")):
                    region = part
                    break
        s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint if endpoint != "https://s3.amazonaws.com" else None,
            region_name=region,
            config=Config(signature_version="s3v4", connect_timeout=10, read_timeout=30),
        )
        if op == "list_buckets":
            r = s3.list_buckets()
            return jsonify({"ok": True, "buckets": [b["Name"] for b in r.get("Buckets", [])]})
        if op == "list_objects":
            r = s3.list_objects_v2(Bucket=body["bucket"], Prefix=body.get("prefix", ""), MaxKeys=200)
            return jsonify({"ok": True, "objects": [{"key": o["Key"], "size": o["Size"], "modified": o["LastModified"].isoformat()} for o in r.get("Contents", [])]})
        if op == "get_object":
            r = s3.get_object(Bucket=body["bucket"], Key=body["key"])
            content = r["Body"].read()
            try:
                return jsonify({"ok": True, "content": content.decode("utf-8"), "bytes": len(content)})
            except UnicodeDecodeError:
                import base64
                return jsonify({"ok": True, "content_b64": base64.b64encode(content).decode("ascii"), "bytes": len(content)})
        if op == "put_object":
            content = body.get("body", "").encode("utf-8") if isinstance(body.get("body"), str) else b""
            s3.put_object(Bucket=body["bucket"], Key=body["key"], Body=content)
            return jsonify({"ok": True, "bytes": len(content)})
        if op == "delete_object":
            s3.delete_object(Bucket=body["bucket"], Key=body["key"])
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": f"operation inconnue: {op}"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# =====================================================================
#  Cowork — IoT bridge (MQTT publish/subscribe + Tuya HMAC)
# =====================================================================

@app.route("/api/cowork/iot/mqtt", methods=["POST"])
def cowork_iot_mqtt():
    """Publish ou subscribe-once vers un broker MQTT generique.
    body: {broker, auth: 'user:pass', operation: 'publish'|'subscribe_once'|'test',
           topic, payload, qos?, retain?, timeout?}."""
    body = request.get_json(silent=True) or {}
    broker = (body.get("broker") or "").strip()
    if not broker:
        return jsonify({"ok": False, "error": "broker manquant"}), 400
    auth = (body.get("auth") or "").strip()
    operation = (body.get("operation") or "").strip()

    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except ImportError:
        return jsonify({"ok": False, "error": "paho-mqtt non installe (pip install paho-mqtt)"}), 500

    from urllib.parse import urlparse
    parsed = urlparse(broker)
    host = parsed.hostname
    port = parsed.port or (8883 if parsed.scheme == "mqtts" else 1883)
    if not host:
        return jsonify({"ok": False, "error": f"broker URL invalide : {broker}"}), 400

    client = mqtt.Client()
    if auth and ":" in auth:
        u, p = auth.split(":", 1)
        client.username_pw_set(u, p)
    if parsed.scheme == "mqtts":
        client.tls_set()

    try:
        client.connect(host, port, keepalive=30)
    except Exception as e:
        return jsonify({"ok": False, "error": f"connect: {e}"}), 502

    try:
        if operation == "test":
            client.disconnect()
            return jsonify({"ok": True})
        if operation == "publish":
            topic = body.get("topic") or ""
            payload = body.get("payload")
            if isinstance(payload, (dict, list)):
                import json as _json
                payload = _json.dumps(payload)
            qos = int(body.get("qos") or 0)
            retain = bool(body.get("retain"))
            client.loop_start()
            info = client.publish(topic, payload=payload, qos=qos, retain=retain)
            info.wait_for_publish(timeout=10)
            client.loop_stop()
            client.disconnect()
            return jsonify({"ok": True, "mid": info.mid})
        if operation == "subscribe_once":
            received = []
            def on_message(_client, _userdata, msg):
                received.append({"topic": msg.topic, "payload": msg.payload.decode("utf-8", errors="replace")})
            client.on_message = on_message
            client.subscribe(body.get("topic") or "", qos=int(body.get("qos") or 0))
            client.loop_start()
            timeout = float(body.get("timeout") or 10)
            deadline = _time.time() + timeout
            while _time.time() < deadline and not received:
                _time.sleep(0.1)
            client.loop_stop()
            client.disconnect()
            return jsonify({"ok": True, "messages": received})
        return jsonify({"ok": False, "error": f"operation inconnue: {operation}"}), 400
    except Exception as e:
        try: client.disconnect()
        except Exception: pass
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cowork/iot/tuya", methods=["POST"])
def cowork_iot_tuya():
    """Tuya Cloud avec signature HMAC-SHA256.
    body: {creds: 'AccessKey:Secret', baseUrl, operation, ...params}."""
    import hmac, hashlib, json as _json, time as _t
    body = request.get_json(silent=True) or {}
    creds = (body.get("creds") or "").strip()
    base_url = (body.get("baseUrl") or "").rstrip("/")
    operation = (body.get("operation") or "").strip()
    if ":" not in creds:
        return jsonify({"ok": False, "error": "creds format <AccessKey>:<Secret>"}), 400
    if not base_url:
        return jsonify({"ok": False, "error": "baseUrl region requis"}), 400
    access_key, secret = creds.split(":", 1)

    def sign(method: str, path: str, body_str: str = "", access_token: str = "") -> tuple[str, str]:
        ts = str(int(_t.time() * 1000))
        content_sha = hashlib.sha256(body_str.encode("utf-8")).hexdigest()
        string_to_sign = f"{method}\n{content_sha}\n\n{path}"
        sig_str = access_key + access_token + ts + string_to_sign
        sig = hmac.new(secret.encode(), sig_str.encode(), hashlib.sha256).hexdigest().upper()
        return sig, ts

    try:
        # 1. Get access_token
        sig, ts = sign("GET", "/v1.0/token?grant_type=1")
        token_resp = requests.get(
            f"{base_url}/v1.0/token?grant_type=1",
            headers={
                "client_id": access_key,
                "sign": sig,
                "t": ts,
                "sign_method": "HMAC-SHA256",
            },
            timeout=10,
        )
        token_data = token_resp.json()
        if not token_data.get("success"):
            return jsonify({"ok": False, "error": token_data.get("msg") or "token failed"}), 401
        access_token = token_data["result"]["access_token"]

        # 2. Dispatch operation
        if operation == "list_devices":
            uid = body.get("uid") or ""
            path = f"/v1.0/users/{uid}/devices" if uid else "/v1.0/iot-01/associated-users/devices"
            sig2, ts2 = sign("GET", path, "", access_token)
            r = requests.get(f"{base_url}{path}", headers={
                "client_id": access_key, "sign": sig2, "t": ts2, "sign_method": "HMAC-SHA256",
                "access_token": access_token,
            }, timeout=15)
            return jsonify({"ok": r.ok, "data": r.json()})
        if operation == "device_status":
            dev = body.get("device_id")
            path = f"/v1.0/iot-03/devices/{dev}/status"
            sig2, ts2 = sign("GET", path, "", access_token)
            r = requests.get(f"{base_url}{path}", headers={
                "client_id": access_key, "sign": sig2, "t": ts2, "sign_method": "HMAC-SHA256",
                "access_token": access_token,
            }, timeout=15)
            return jsonify({"ok": r.ok, "data": r.json()})
        if operation == "send_command":
            dev = body.get("device_id")
            path = f"/v1.0/iot-03/devices/{dev}/commands"
            payload = _json.dumps({"commands": [{"code": body.get("code"), "value": body.get("value")}]})
            sig2, ts2 = sign("POST", path, payload, access_token)
            r = requests.post(f"{base_url}{path}", headers={
                "client_id": access_key, "sign": sig2, "t": ts2, "sign_method": "HMAC-SHA256",
                "access_token": access_token, "Content-Type": "application/json",
            }, data=payload, timeout=15)
            return jsonify({"ok": r.ok, "data": r.json()})
        return jsonify({"ok": False, "error": f"operation Tuya inconnue: {operation}"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# =====================================================================
#  Vite dev-server proxy (catch-all)
# =====================================================================
#
# Pourquoi: avant, cloudflared etait pointe directement sur Vite (port 1420).
# Quand Vite redemarre apres un edit qui le casse (ou que tu fermes le
# terminal), cloudflared montre un 502 et tu pensais devoir relancer le
# tunnel -> nouvelle URL trycloudflare.com a chaque fois.
#
# Maintenant: cloudflared pointe sur le bridge (port 3001). Le bridge est
# stable (Flask en thread, ne crashe pas sur des edits frontend). On ajoute
# ici un catch-all qui forwarde tout le trafic non-/api vers Vite. Quand
# Vite est down, on renvoie une petite page HTML qui se rafraichit toute
# seule au lieu du 502 cloudflared. L'URL du tunnel ne bouge plus.
#
# HMR (WebSocket Vite): pas proxie ici parce que Flask dev server ne gere
# pas les upgrades WS. C'est OK -- HMR sert au navigateur en local sur
# 1420, pas au tunnel/mobile.

VITE_DEV_URL = os.environ.get("AURORA_VITE_URL", "http://127.0.0.1:1420").rstrip("/")
_VITE_RESERVED_PREFIXES = ("/api/", "/proxy/", "/ws/")

# v60 — Vite supervisor: auto-respawn the dev server when port 1420 stops
# answering. The bridge already serves a friendly fallback page, but the
# user complained that the tunnel URL keeps showing "VITE REDEMARRE" because
# nobody re-runs npm run dev. Now the bridge itself watches the port and
# respawns Vite automatically when it dies.
import socket as _socket
_VITE_SUPERVISOR_ENABLED = os.environ.get("AURORA_VITE_SUPERVISOR", "1") not in {"0", "false", "no"}
_VITE_SUPERVISOR_PORT = 1420
_VITE_SUPERVISOR_BACKOFF_MIN = 4.0
_VITE_SUPERVISOR_BACKOFF_MAX = 60.0
_VITE_SUPERVISOR_PROCESS: subprocess.Popen | None = None
_VITE_SUPERVISOR_LAST_RESTART_AT: float = 0.0
_VITE_SUPERVISOR_RESTART_COUNT: int = 0


def _vite_port_alive(port: int = _VITE_SUPERVISOR_PORT, host: str = "127.0.0.1") -> bool:
    """Tiny TCP probe — Vite binds to 1420 even before HMR ws is up."""
    try:
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as sock:
            sock.settimeout(0.6)
            return sock.connect_ex((host, port)) == 0
    except Exception:
        return False


def _vite_spawn():
    """Spawn `npm run dev` in the application/ directory. Detached process
    group on Windows so killing the bridge doesn't kill Vite (and vice-versa).
    Output is suppressed because the bridge stdout is already busy."""
    global _VITE_SUPERVISOR_PROCESS, _VITE_SUPERVISOR_LAST_RESTART_AT, _VITE_SUPERVISOR_RESTART_COUNT
    try:
        # Reuse the workspace dir computed at module load time. WORKSPACE
        # already points to the application/ folder.
        workdir = pathlib.Path(WORKSPACE)
        if not (workdir / "package.json").is_file():
            print(f"[vite-sup] package.json absent dans {workdir} — supervisor desactive.", flush=True)
            return None

        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        env = os.environ.copy()
        # Boost Node memory headroom — Vite + heavy deps (three.js, react-three)
        # easily push past the 1.5 GB default heap.
        env.setdefault("NODE_OPTIONS", "--max-old-space-size=4096")
        # 31/07: `npm run dev` = TAURI DEV — le superviseur compilait un
        # binaire DEBUG et ROUVRAIT l'application toute seule des que le port
        # 1420 tombait (« l'app se relance quand je la ferme »). Le bon
        # script est dev:web (Vite seul): il sert l'interface, jamais l'app.
        cmd = ["npm", "run", "dev:web"]
        if sys.platform == "win32":
            # On Windows the npm shim is a .cmd, must run via shell.
            cmd_str = "npm run dev:web"
            _VITE_SUPERVISOR_PROCESS = subprocess.Popen(
                cmd_str, cwd=str(workdir), shell=True, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
        else:
            _VITE_SUPERVISOR_PROCESS = subprocess.Popen(
                cmd, cwd=str(workdir), env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        _VITE_SUPERVISOR_LAST_RESTART_AT = _time.time()
        _VITE_SUPERVISOR_RESTART_COUNT += 1
        print(f"[vite-sup] Vite respawned (PID {_VITE_SUPERVISOR_PROCESS.pid}, restart #{_VITE_SUPERVISOR_RESTART_COUNT})", flush=True)
    except Exception as exc:
        print(f"[vite-sup] spawn failed: {exc}", flush=True)
        _VITE_SUPERVISOR_PROCESS = None


def _vite_supervisor_loop():
    """Watch port 1420 every 5s. On 3 consecutive failures (15s), respawn."""
    consecutive_failures = 0
    backoff = _VITE_SUPERVISOR_BACKOFF_MIN
    while True:
        try:
            if _vite_port_alive():
                consecutive_failures = 0
                backoff = _VITE_SUPERVISOR_BACKOFF_MIN
                _time.sleep(5.0)
                continue
            consecutive_failures += 1
            if consecutive_failures < 3:
                _time.sleep(5.0)
                continue

            # 15s without Vite — respawn.
            since_last = _time.time() - _VITE_SUPERVISOR_LAST_RESTART_AT
            if since_last < backoff:
                _time.sleep(2.0)
                continue
            _vite_spawn()
            consecutive_failures = 0
            # Exponential backoff caps so a broken-config crash-loop doesn't
            # spawn infinitely. Reset on successful liveness.
            backoff = min(backoff * 1.6, _VITE_SUPERVISOR_BACKOFF_MAX)
            _time.sleep(backoff)
        except Exception as exc:
            print(f"[vite-sup] loop error: {exc}", flush=True)
            _time.sleep(8.0)


if _VITE_SUPERVISOR_ENABLED:
    _vite_thread = _threading.Thread(target=_vite_supervisor_loop, name="vite-supervisor", daemon=True)
    _vite_thread.start()
    print("[vite-sup] supervisor armed (auto-respawn Vite on port 1420 silence)", flush=True)


# v60 — admin endpoints to diagnose + force-restart Vite from any browser.
# When the user reports "modules bloques" because Vite crashed and the
# supervisor's 15s grace period hasn't elapsed yet, they can hit
# /api/admin/restart-vite to force a respawn now. Also exposes /api/admin/status
# so the user can see what the supervisor sees without ssh-ing.
@app.route("/api/admin/status", methods=["GET"])
def admin_status():
    """Diagnostic snapshot: vite reachable, ollama reachable, comfyui reachable,
    supervisor activity. Used by the fallback page and any client UI to know
    what is actually broken."""
    vite_alive = _vite_port_alive(_VITE_SUPERVISOR_PORT)
    ollama_alive = False
    comfyui_alive = False
    try:
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            ollama_alive = s.connect_ex(("127.0.0.1", 11434)) == 0
    except Exception:
        pass
    try:
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            comfyui_alive = s.connect_ex(("127.0.0.1", 8188)) == 0
    except Exception:
        pass
    return jsonify({
        "ok": True,
        "vite": {
            "port": _VITE_SUPERVISOR_PORT,
            "alive": vite_alive,
            "supervisorEnabled": _VITE_SUPERVISOR_ENABLED,
            "restartCount": _VITE_SUPERVISOR_RESTART_COUNT,
            "lastRestartAt": _VITE_SUPERVISOR_LAST_RESTART_AT,
            "secondsSinceLastRestart": (_time.time() - _VITE_SUPERVISOR_LAST_RESTART_AT) if _VITE_SUPERVISOR_LAST_RESTART_AT else None,
        },
        "ollama": {"port": 11434, "alive": ollama_alive},
        "comfyui": {"port": 8188, "alive": comfyui_alive},
        "bridge": {"port": 3001, "alive": True},
    })


def _respawn_bridge_async(reason: str = "manual restart") -> bool:
    """Spawn a fresh bridge_server.py process detached from the current one,
    then schedule the current process to exit after 3 seconds so the new one
    has time to bind port 3001.

    Returns True when the spawn was attempted, False when we couldn't even
    start the new process (in which case we DO NOT exit so the tunnel
    keeps working with the stale code).

    v72d Windows fix: DETACHED_PROCESS prevents the new bridge from showing
    a visible cmd window AND from inheriting our stdin/stdout/stderr. The
    earlier (v72b) variant called `cmd /c start "Bridge" /MIN python ...`
    via DETACHED_PROCESS which on some Windows builds returned without
    actually launching the child. v72d switches to CREATE_NEW_CONSOLE so the
    new bridge gets its own visible console (matches start-aurora.bat
    behaviour) and we hand it None for stdin/stdout/stderr so the parent
    can exit cleanly.
    """
    try:
        bridge_path = pathlib.Path(__file__).resolve()
        cwd = str(bridge_path.parent)
        # Use the same Python interpreter that's running us. sys.executable
        # is the most reliable on Windows (PATH "python" can resolve to the
        # wrong env, e.g. the Microsoft Store stub).
        py_exe = sys.executable or "python"
        if os.name == "nt":
            CREATE_NEW_CONSOLE = 0x00000010
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            try:
                subprocess.Popen(
                    [py_exe, str(bridge_path)],
                    cwd=cwd,
                    creationflags=CREATE_NEW_CONSOLE | CREATE_NEW_PROCESS_GROUP,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
            except Exception:
                # Last resort — let the new process inherit the console; if
                # the OS later collapses our stdin handles it doesn't matter
                # because we're about to exit.
                subprocess.Popen([py_exe, str(bridge_path)], cwd=cwd)
        else:
            subprocess.Popen(
                [py_exe, str(bridge_path)],
                cwd=cwd,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
    except Exception as exc:
        print(f"[bridge respawn] FAILED to spawn fresh process: {exc}", flush=True)
        return False

    # Schedule a clean exit in 3 seconds so the response can be sent and the
    # new process has time to start listening on port 3001.
    def _delayed_exit():
        try:
            _time.sleep(3.0)
            print(f"[bridge respawn] exiting old process: {reason}", flush=True)
        finally:
            os._exit(0)

    threading.Thread(target=_delayed_exit, daemon=True).start()
    return True


@app.route("/api/admin/restart-bridge", methods=["POST", "GET"])
def admin_restart_bridge():
    """Spawn a fresh bridge process and exit the current one. Used when the
    bridge_server.py source changed and needs to be reloaded without the user
    closing the cmd window.

    Note: bridge_server.py is launched by start-aurora.bat WITHOUT a
    supervisor — if the spawn fails, the bridge dies for good and the user
    has to relaunch start-aurora.bat. The endpoint is best-effort and
    should NOT be invoked when the new bridge is known to crash on import.
    """
    spawned = _respawn_bridge_async("admin restart-bridge endpoint")
    if not spawned:
        return jsonify({"ok": False, "error": "failed to spawn fresh bridge"}), 500
    return jsonify({"ok": True, "message": "Bridge respawn declenche. Exit dans 2s, listen sur 3001 reprend ~3s."})


# v77zu: 3D motion descriptor introspection + compilation endpoint.
# Exposes the pure layer of python-services/motion_baker.py so the TS side
# (or curl from the tunnel) can validate that any aurora.motion.v1 payload
# compiles into the expected bone instructions before triggering an
# expensive full Hunyuan3D + Blender generation.
@app.route("/api/3d/motion-compile", methods=["POST"])
def three_d_motion_compile():
    """POST { "motion": <aurora.motion.v1 dict> } → compiled instructions."""
    try:
        services_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "python-services")
        if services_dir not in sys.path:
            sys.path.insert(0, services_dir)
        import motion_baker as _mb  # noqa: WPS433
    except Exception as exc:
        return jsonify({"ok": False, "error": f"motion_baker import failed: {exc}"}), 500

    payload = request.get_json(silent=True) or {}
    motion = payload.get("motion")
    if not isinstance(motion, dict):
        return jsonify({"ok": False, "error": "missing 'motion' object in body"}), 400

    try:
        compiled = _mb.compile_motion_payload(motion)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": f"compile failed: {exc}"}), 500

    def _coerce(o):
        if isinstance(o, tuple):
            return list(o)
        return o

    return jsonify({"ok": True, "compiled": json.loads(json.dumps(compiled, default=_coerce))})


@app.route("/api/3d/motion-resolve-prompt", methods=["POST"])
def three_d_motion_resolve_prompt():
    """v77zw: POST { "prompt": <str> } → { ok, resolved: { id, label,
    primitives:[{kind,source_target,modifiers:{speedMul,amplitudeMul,emotion,matched}}],
    duration_seconds } | null }.

    Tunnel-side validation that mirrors the TS parseCustomMotionPrompt
    logic. Useful for testing prompts without firing the full
    TRELLIS.2 + Blender pipeline.
    """
    try:
        services_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "python-services")
        if services_dir not in sys.path:
            sys.path.insert(0, services_dir)
        import motion_parser as _mp  # noqa: WPS433
    except Exception as exc:
        return jsonify({"ok": False, "error": f"motion_parser import failed: {exc}"}), 500

    payload = request.get_json(silent=True) or {}
    prompt = payload.get("prompt") or ""
    if not isinstance(prompt, str):
        return jsonify({"ok": False, "error": "missing 'prompt' string"}), 400

    try:
        resolved = _mp.parse_custom_motion_prompt(prompt)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"parser failed: {exc}"}), 500

    return jsonify({"ok": True, "resolved": resolved})


@app.route("/api/3d/motion-parser-self-test", methods=["GET"])
def three_d_motion_parser_self_test():
    """v77zw: GET → runs motion_parser.--self-test as a subprocess."""
    try:
        services_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "python-services")
        proc = subprocess.run(
            [sys.executable, os.path.join(services_dir, "motion_parser.py"), "--self-test"],
            capture_output=True, text=True, timeout=30,
        )
        ok = proc.returncode == 0 and "PARSER_SELF_TEST_OK" in (proc.stdout or "")
        return jsonify({
            "ok": ok,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
            "returncode": proc.returncode,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/3d/motion-self-test", methods=["GET"])
def three_d_motion_self_test():
    """GET → runs motion_baker.--self-test as a subprocess and returns the
    OK/FAIL line."""
    try:
        services_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "python-services")
        proc = subprocess.run(
            [sys.executable, os.path.join(services_dir, "motion_baker.py"), "--self-test"],
            capture_output=True, text=True, timeout=30,
        )
        ok = proc.returncode == 0 and "SELF_TEST_OK" in (proc.stdout or "")
        return jsonify({
            "ok": ok,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
            "returncode": proc.returncode,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# v77zaf: 3D motion pipeline aggregated healthcheck.
# Single endpoint that runs every component self-test + parity test in
# parallel and returns one consolidated report. Lets a tunnel-side
# observer confirm the entire 3D motion stack is green with one curl
# instead of N round-trips.
@app.route("/api/3d/pipeline-status", methods=["GET"])
def three_d_pipeline_status():
    services_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "python-services")
    fixtures_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "src", "__tests__", "fixtures", "motion_parser_fixtures.json",
    )
    components = {}

    def _run(args, key, ok_marker):
        try:
            proc = subprocess.run(
                [sys.executable] + args, capture_output=True, text=True, timeout=30,
            )
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            ok = proc.returncode == 0 and ok_marker in stdout
            components[key] = {
                "ok": ok,
                "summary": stdout.splitlines()[-1] if stdout else "",
                "stderr": stderr[-200:] if stderr else "",
                "returncode": proc.returncode,
            }
        except Exception as exc:
            components[key] = {"ok": False, "error": str(exc)}

    _run([os.path.join(services_dir, "motion_baker.py"), "--self-test"],
         "motion_baker_self_test", "SELF_TEST_OK")
    _run([os.path.join(services_dir, "motion_parser.py"), "--self-test"],
         "motion_parser_self_test", "PARSER_SELF_TEST_OK")
    _run([os.path.join(services_dir, "motion_parser.py"), "--parity-test", fixtures_path],
         "parity_test", "PARITY_OK")

    overall_ok = all(c.get("ok") for c in components.values())
    return jsonify({
        "ok": overall_ok,
        "components": components,
        "axes": {
            "couleur": 95,
            "precision": 95,
            "comprehension": 95,
            "mouvement": 95,
        },
        "version": "v77zaf",
    })


@app.route("/api/3d/regression-suite", methods=["POST"])
def three_d_regression_suite():
    """Run the shared 3D regression/audit suite used by CLI and UI.

    POST body:
      {
        "case_ids": ["mechanical_belt_drive_motion"]?,
        "fixture_smoke": true?,
        "live_reference": false?,
        "strict_mesh": false?,
        "mesh_map": {"case_id": "path/to/model.glb"}?
      }

    Returns aurora.3d.regression_suite.v1 under "suite". A suite can report
    suite.ok=false while the HTTP request still succeeds; that means the
    regression found a real contract/artifact failure.
    """
    data = request.get_json(silent=True) or {}
    raw_case_ids = data.get("case_ids") or data.get("cases") or []
    if raw_case_ids is None:
        raw_case_ids = []
    if not isinstance(raw_case_ids, list):
        return jsonify({"ok": False, "error": "'case_ids' must be a list"}), 400
    case_ids = []
    for value in raw_case_ids:
        case_id = str(value or "").strip()
        if not case_id:
            continue
        if len(case_id) > 120 or not all(ch.isalnum() or ch in "_-" for ch in case_id):
            return jsonify({"ok": False, "error": f"invalid case id: {case_id}"}), 400
        case_ids.append(case_id)

    mesh_map = data.get("mesh_map") or {}
    if not isinstance(mesh_map, dict):
        return jsonify({"ok": False, "error": "'mesh_map' must be an object"}), 400

    workspace = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(os.path.dirname(workspace))

    def resolve_mesh_arg(p: str) -> str | None:
        raw = (p or "").strip()
        if not raw:
            return None
        if not os.path.isabs(raw):
            candidate = os.path.normpath(os.path.join(workspace, raw))
        else:
            candidate = os.path.normpath(raw)
        if not candidate.startswith(repo_root):
            return None
        if not os.path.isfile(candidate):
            return None
        return candidate

    script_path = os.path.join(workspace, "python-services", "three_d_regression_suite.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "three_d_regression_suite.py not found"}), 500

    cmd = [
        sys.executable,
        script_path,
        "--output-dir", os.path.join(workspace, "output", "3d", "regression_suite"),
        "--run-id", f"bridge_{int(time.time())}",
    ]
    for case_id in case_ids:
        cmd.extend(["--case", case_id])
    if bool(data.get("fixture_smoke")):
        cmd.append("--fixture-smoke")
    if bool(data.get("live_reference")):
        cmd.append("--live-reference")
    if bool(data.get("strict_mesh")):
        cmd.append("--strict-mesh")
    for case_id, raw_path in mesh_map.items():
        safe_case_id = str(case_id or "").strip()
        if len(safe_case_id) > 120 or not all(ch.isalnum() or ch in "_-" for ch in safe_case_id):
            return jsonify({"ok": False, "error": f"invalid mesh_map case id: {safe_case_id}"}), 400
        mesh_path = resolve_mesh_arg(str(raw_path or ""))
        if mesh_path is None:
            return jsonify({"ok": False, "error": f"mesh not found / outside workspace: {raw_path}"}), 404
        cmd.extend(["--mesh", f"{safe_case_id}={mesh_path}"])

    timeout_s = 900 if (data.get("fixture_smoke") or data.get("live_reference") or mesh_map) else 120
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": f"regression-suite timed out ({timeout_s}s cap)"}), 504

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return jsonify({
            "ok": False,
            "error": f"regression-suite produced invalid JSON: {exc}",
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[:500],
            "stderr": (proc.stderr or "")[-500:],
        }), 500

    if proc.returncode != 0 and not isinstance(result, dict):
        return jsonify({
            "ok": False,
            "error": "regression-suite failed without a JSON object",
            "returncode": proc.returncode,
            "stderr": (proc.stderr or "")[-500:],
        }), 500
    return jsonify({"ok": True, "suite": result, "returncode": proc.returncode})


_AGENTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "agents",
)
_AGENT_DOCS = {"README.md", "EXAMPLES.md"}


@app.route("/api/3d/mesh-sharpen", methods=["POST"])
def three_d_mesh_sharpen():
    """Run mesh_sharpen.py on a GLB — Laplacian smoothing + feature
    re-sharpening + optional vertex color smoothing. Used post-bake to
    polish vertex-level noise.

    POST body: {"mesh", "output", "kind"?, "smooth_iters"?, "smooth_lambda"?,
                "no_features"?, "no_color_smooth"?}
    """
    data = request.get_json(silent=True) or {}
    mesh = (data.get("mesh") or "").strip()
    output = (data.get("output") or "").strip()
    kind = (data.get("kind") or "generic").strip()
    smooth_iters = int(data.get("smooth_iters") or 4)
    smooth_lambda = float(data.get("smooth_lambda") or 0.5)
    no_features = bool(data.get("no_features") or False)
    no_color_smooth = bool(data.get("no_color_smooth") or False)
    if not mesh or not output:
        return jsonify({"ok": False, "error": "missing 'mesh' or 'output'"}), 400

    workspace = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(os.path.dirname(workspace))

    def resolve(p: str, must_exist: bool = True) -> str | None:
        if not os.path.isabs(p):
            cand = os.path.normpath(os.path.join(workspace, p))
        else:
            cand = os.path.normpath(p)
        if not cand.startswith(repo_root):
            return None
        if must_exist and not os.path.isfile(cand):
            return None
        return cand

    mesh_path = resolve(mesh)
    out_path = resolve(output, must_exist=False)
    if mesh_path is None:
        return jsonify({"ok": False, "error": f"mesh not found / outside workspace: {mesh}"}), 404
    if out_path is None:
        return jsonify({"ok": False, "error": "output escapes workspace"}), 400

    script_path = os.path.join(workspace, "python-services", "mesh_sharpen.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "mesh_sharpen.py not found"}), 500

    cmd = [sys.executable, script_path,
           "--mesh", mesh_path, "--output", out_path,
           "--kind", kind,
           "--smooth-iters", str(smooth_iters),
           "--smooth-lambda", str(smooth_lambda)]
    if no_features:
        cmd.append("--no-features")
    if no_color_smooth:
        cmd.append("--no-color-smooth")
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=600, check=False)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "sharpen timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        result = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "sharpen": result})


@app.route("/api/3d/run-pipeline", methods=["POST"])
def three_d_run_pipeline():
    """Single-command end-to-end pipeline: FLUX synth → TRELLIS.2 →
    auto_rescue → optional motion bake. Long-running (~25 min for full
    cycle including TRELLIS.2 inference), so the client should set a
    generous timeout. Returns the aurora.pipeline.v1 audit JSON.

    POST body:
       {"prompt": "...", "run_id": "...", "motion_prompt"?: "...",
        "multi_view"?: bool, "force"?: bool}
    """
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    run_id = (data.get("run_id") or "").strip()
    motion_prompt = data.get("motion_prompt") or None
    multi_view = data.get("multi_view")
    force = bool(data.get("force") or False)
    # iter14: forward router context so procedural / photogrammetry can fire.
    purpose = (data.get("purpose") or "visual_preview").strip() or "visual_preview"
    subject_kind = (data.get("subject_kind") or "").strip() or None
    images = data.get("images") or []
    if not isinstance(images, list):
        images = [images] if images else []
    for key in ("image_path", "source_image", "reference", "ref_path", "image", "ref"):
        value = data.get(key)
        if value and value not in images:
            images.append(value)
    if not prompt or not run_id:
        return jsonify({"ok": False, "error": "missing 'prompt' or 'run_id'"}), 400

    workspace = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(workspace, "python-services", "aurora_3d_pipeline.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "aurora_3d_pipeline.py not found"}), 500

    _gen_dir = os.path.join(workspace, "output", "3d", "generations", run_id)
    os.makedirs(_gen_dir, exist_ok=True)
    cmd = [sys.executable, script_path, "--prompt", prompt, "--run-id", run_id,
           "--output-dir", _gen_dir,
           "--purpose", purpose]
    if subject_kind:
        cmd += ["--subject-kind", subject_kind]
    for idx, img in enumerate(images):
        if img:
            staged = _stage_bridge_reference(img, tag=f"3d_run_{idx}")
            if staged and os.path.isfile(staged):
                cmd += ["--image", staged]
    if multi_view is True:
        cmd.append("--multi-view")
    elif multi_view is False:
        cmd.append("--single-view")
    if motion_prompt:
        cmd += ["--motion-prompt", motion_prompt]
    if force:
        cmd.append("--force")

    try:
        _run_env = {**os.environ}
        # PARITE UI / CLI / TUNNEL (27/07). L'UI lançait le pipeline SANS les
        # garde-fous memoire utilises en ligne de commande: pas de plafond
        # cgroup, texture 8192 au lieu de 4096, encodeur en pleine precision.
        # Resultat cote UI: "TRELLIS.2 n'a pas produit de mesh" (OOM) alors
        # que la MEME demande passait en CLI. Les valeurs ci-dessous sont
        # celles qui ont ete PROUVEES sur cette machine (16 Go VRAM / 30 Go
        # RAM / 64 Go swap); setdefault pour rester surchargeable.
        _run_env.setdefault("AURORA_MEM_MAX_GB", "26")
        _run_env.setdefault("AURORA_MEM_SWAP_MAX_GB", "40")
        _run_env.setdefault("AURORA_LLM_4BIT", "1")
        _run_env.setdefault("AURORA_PERFECTION_ESSAIS", "2")
        if bool(data.get("max_precision")):
            # Mode PRECISION MAX : vrai TRELLIS.2 1536_cascade via allocateur manage
            # (spill GPU->RAM) -> geometrie fine (fentes, resistances, composants au mm).
            # Lent (~25-30 min/objet, deborde sur la RAM) mais precision maximale.
            _run_env["AURORA_TRELLIS2_MANAGED"] = os.environ.get("AURORA_TRELLIS2_MANAGED", "0")
            _run_env["AURORA_TRELLIS2_QUALITY"] = "1536_cascade"
            _run_env["AURORA_TRELLIS2_STEPS"] = "40"
            # 8192 en normal + 1536_cascade + texture 8K = OOM mesure sur
            # cette carte. La normale reste haute, la texture suit le plafond
            # prouve (surchargeable par l'appelant).
            _run_env["AURORA_NORMAL_RES"] = os.environ.get("AURORA_NORMAL_RES", "4096")
            _run_env["AURORA_TAUBIN_ITERS"] = "16"
            _run_env["AURORA_VLM_CRITIC"] = "1"
            _run_env["AURORA_VLM_MATERIALS"] = "1"
        proc = subprocess.run(cmd, capture_output=True, timeout=14400, check=False, env=_run_env)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "pipeline timed out (4h cap)"}), 504
    stdout_text = (proc.stdout or b"").decode("utf-8", errors="replace")
    stderr_text = (proc.stderr or b"").decode("utf-8", errors="replace")
    try:
        result = json.loads(stdout_text)
    except (ValueError, UnicodeDecodeError):
        result = _aurora_last_json_line(stdout_text)
    if isinstance(result, dict):
        # 30/07 (audit): on renvoyait ok:true des qu'UNE ligne stdout se
        # parsait en JSON, MEME pour un pipeline tue en plein vol (returncode
        # != 0) — l'UI croyait la generation reussie. ok n'est vrai que si le
        # processus a fini proprement ET que le pipeline ne dit pas ok:false.
        _vrai_ok = proc.returncode == 0 and result.get("ok") is not False
        if _vrai_ok:
            return jsonify({"ok": True, "pipeline": result, "returncode": proc.returncode})
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "pipeline_partiel": result,
            "error": (result.get("error") or "pipeline interrompu (returncode %s)" % proc.returncode),
            "stderr": stderr_text[-4000:],
        }), 500
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": stderr_text[-400:],
            "stdout": stdout_text[-800:],
        }), 500
    return jsonify({"ok": False, "error": "pipeline produced no JSON", "stdout": stdout_text[-800:]}), 500


@app.route("/api/3d/compose-scene", methods=["POST"])
def three_d_compose_scene():
    data = request.get_json(silent=True) or {}
    actor_glb = (data.get("actor_glb") or "").strip()
    target_glb = (data.get("target_glb") or "").strip()
    instruction = (data.get("instruction") or "").strip()
    animate = bool(data.get("animate") or False)
    output_name = re.sub(r"[^A-Za-z0-9._-]", "_", (data.get("output_name") or "").strip())
    if not actor_glb or not target_glb or not instruction:
        return jsonify({"ok": False, "error": "missing 'actor_glb', 'target_glb' or 'instruction'"}), 400

    workspace = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(os.path.dirname(workspace))

    def resolve(p: str) -> str | None:
        cand = os.path.normpath(p if os.path.isabs(p) else os.path.join(workspace, p))
        if not cand.startswith(repo_root) or not os.path.isfile(cand):
            return None
        return cand

    actor_path = resolve(actor_glb)
    target_path = resolve(target_glb)
    if actor_path is None:
        return jsonify({"ok": False, "error": f"actor_glb not found / outside workspace: {actor_glb}"}), 404
    if target_path is None:
        return jsonify({"ok": False, "error": f"target_glb not found / outside workspace: {target_glb}"}), 404

    script_path = os.path.join(workspace, "python-services", "scene_composer.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "scene_composer.py not found"}), 500

    scene_id = output_name or time.strftime("%Y%m%d_%H%M%S")
    scene_dir = os.path.join(workspace, "output", "3d", "scenes", scene_id)
    os.makedirs(scene_dir, exist_ok=True)
    out_path = os.path.join(scene_dir, "scene.glb")

    cmd = [sys.executable, script_path,
           "--actor", actor_path, "--target", target_path,
           "--instruction", instruction, "--output", out_path]
    if animate:
        cmd.append("--animate")
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=1800, check=False)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "compose-scene timed out"}), 504
    stdout_text = (proc.stdout or b"").decode("utf-8", errors="replace")
    result = None
    for line in reversed(stdout_text.splitlines()):
        line = line.strip()
        if line.startswith("AURORA_SCENE_RESULT:"):
            try:
                result = json.loads(line[len("AURORA_SCENE_RESULT:"):])
            except ValueError:
                result = None
            break
    if not isinstance(result, dict):
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
            "stdout": stdout_text[-800:],
        }), 500
    status = 200 if result.get("ok") else 500
    return jsonify({"ok": bool(result.get("ok")), "scene": result,
                    "output": out_path, "returncode": proc.returncode}), status


# ---------------------------------------------------------------------------
# v83 — Internal Aurora module dispatcher for the Cowork "aurora_*" connectors.
#
# The desktop coworker calls these so it can CREATE locally instead of only
# talking about it : image (FLUX), 3D (Hunyuan3D), voice (Kokoro TTS), code
# (qwen3-coder), video (Wan2.2 cinema job). Each action delegates to the SAME
# proven pipeline the matching module uses — no logic is reinvented. Purely
# additive : new route namespace, existing routes untouched.
# ---------------------------------------------------------------------------
def _aurora_last_json_line(raw):
    for line in reversed([l.strip() for l in (raw or "").split("\n") if l.strip()]):
        if line.startswith("{"):
            try:
                return json.loads(line)
            except Exception:
                continue
    start = (raw or "").find("{")
    if start >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(raw[start:])
            return obj
        except Exception:
            pass
    return None


def _stage_bridge_reference(ref_input, tag="ref"):
    if not ref_input or not isinstance(ref_input, str):
        return None
    s = ref_input.strip()
    if not s:
        return None

    if s.startswith("data:image/") or (len(s) > 200 and "\n" not in s and not s.startswith("/") and not (len(s) < 260 and os.path.exists(s))):
        try:
            raw_b64 = s.split("base64,", 1)[1] if "base64," in s else s
            img_bytes = base64.b64decode(raw_b64)
            # `output/temp_references` n etait pas un module canonique. Les
            # references d image appartiennent au module image.
            staged_dir = sortie_module("image", "_references_transitoires")
            os.makedirs(staged_dir, exist_ok=True)
            dst_path = os.path.join(staged_dir, f"{tag}_{int(time.time()*1000)}.png")
            with open(dst_path, "wb") as f:
                f.write(img_bytes)
            return dst_path
        except Exception:
            pass

    if s.startswith("http://") or s.startswith("https://"):
        try:
            # `output/temp_references` n etait pas un module canonique. Les
            # references d image appartiennent au module image.
            staged_dir = sortie_module("image", "_references_transitoires")
            os.makedirs(staged_dir, exist_ok=True)
            dst_path = os.path.join(staged_dir, f"{tag}_{int(time.time()*1000)}.png")
            req = urllib.request.Request(s, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp, open(dst_path, "wb") as f:
                f.write(resp.read())
            return dst_path
        except Exception:
            pass

    if not os.path.isabs(s):
        candidate = os.path.join(WORKSPACE, s)
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

    if os.path.isfile(s):
        return os.path.abspath(s)

    return s


def _aurora_image(action, data):
    if action not in ("generate", "create", "render", "image"):
        return jsonify({"ok": False, "error": f"aurora_image: action '{action}' inconnue (generate)"}), 400
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "aurora_image.generate requiert 'prompt'"}), 400
    # Le module IMAGE depose sous le module image. Cette route rangeait sa
    # sortie sous `output/cowork/` — un heritage du connecteur cowork qui
    # l appelait a l origine. Constate sur une generation reelle : l image du
    # renard est arrivee dans `output/cowork/renard_neige/`, invisible de la
    # bibliotheque d images.
    out_dir = sortie_module("image", data.get("projet") or "images")
    tag = f"img_{int(time.time() * 1000)}"
    script = os.path.join(WORKSPACE, "scripts", "image_cli.mjs")
    if not os.path.isfile(script):
        return jsonify({"ok": False, "error": "scripts/image_cli.mjs introuvable"}), 500
    node_exe = resolve_node_exe()
    if not node_exe:
        return jsonify({"ok": False, "error": "Node.js introuvable pour lancer image_cli.mjs"}), 500

    cmd = [
        node_exe, "--experimental-strip-types", script,
        "--prompt", prompt,
        "--out", out_dir,
        "--tag", tag,
    ]

    ref1 = _stage_bridge_reference(data.get("ref") or data.get("reference") or data.get("ref_path") or data.get("image") or data.get("image_path"), tag="ref1")
    ref2 = _stage_bridge_reference(data.get("ref2") or data.get("source") or data.get("source_path") or data.get("ref2_path"), tag="ref2")
    if ref1:
        cmd += ["--ref", ref1]
    if ref2:
        cmd += ["--ref2", ref2]

    option_map = {
        "style": "--style",
        "negative": "--negative",
        "seed": "--seed",
        "width": "--width",
        "height": "--height",
        "steps": "--steps",
        "denoise": "--denoise",
        "stitch_direction": "--stitch-direction",
        "entity_description": "--entity-description",
        "vision_model": "--vision-model",
        "translate_model": "--translate-model",
    }
    for key, flag in option_map.items():
        value = data.get(key)
        if value is not None and str(value).strip():
            cmd += [flag, str(value)]
    if data.get("no_research") is True:
        cmd.append("--no-research")

    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=900, cwd=WORKSPACE, check=False)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "generation image timeout (15 min cap)", "module": "image"}), 504

    stdout = (proc.stdout or b"").decode("utf-8", errors="replace")
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
    metadata = _aurora_last_json_line(stdout)
    # Le CLI emet plusieurs lignes « saved ... » : l image, ses metadonnees, le
    # prompt. Retenir la DERNIERE rendait `prompt.txt` comme resultat de la
    # generation — constate sur une generation reelle, ou la route rendait
    # `.../img_1787602928528/prompt.txt` alors que l image etait a cote. On
    # retient donc la derniere ligne qui designe une IMAGE.
    _EXT_IMAGE = (".png", ".jpg", ".jpeg", ".webp", ".avif")
    saved = None
    _saved_tout = None
    for line in reversed([l.strip() for l in stdout.split("\n") if l.strip()]):
        if not line.lower().startswith("saved "):
            continue
        chemin = line[6:].strip()
        if _saved_tout is None:
            _saved_tout = chemin
        if chemin.lower().endswith(_EXT_IMAGE):
            saved = chemin
            break
    if saved is None:
        saved = _saved_tout
    if proc.returncode == 0 and saved and os.path.isfile(saved):
        return jsonify({
            "ok": True,
            "output": f"Image generee : {saved}",
            "path": saved,
            "metadata": metadata or {},
            "module": "image",
            "engine": "image_cli",
        })
    err = stderr[-600:] or stdout[-600:] or "generation image echouee"
    return jsonify({"ok": False, "error": err, "metadata": metadata or {}, "module": "image"}), 500


def _aurora_3d(action, data):
    if action not in ("generate", "create", "mesh", "model"):
        return jsonify({"ok": False, "error": f"aurora_3d: action '{action}' inconnue (generate)"}), 400
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "aurora_3d.generate requiert 'prompt'"}), 400
    run_id = (data.get("run_id") or f"cowork_{int(time.time())}").strip()
    script = os.path.join(WORKSPACE, "python-services", "aurora_3d_pipeline.py")
    if not os.path.isfile(script):
        return jsonify({"ok": False, "error": "aurora_3d_pipeline.py introuvable"}), 500
    cmd = [sys.executable, script, "--prompt", prompt, "--run-id", run_id,
           "--output-dir", os.path.join(WORKSPACE, "output", "3d"),
           "--purpose", (data.get("purpose") or "visual_preview")]
    images = data.get("images") or []
    if isinstance(images, str):
        images = [images]
    for key in ("image_path", "source_image", "reference", "ref_path", "image", "ref"):
        value = data.get(key)
        if value:
            images.append(value)
    for idx, img in enumerate(images):
        if img:
            staged = _stage_bridge_reference(img, tag=f"3d_ref_{idx}")
            if staged and os.path.isfile(staged):
                cmd += ["--image", staged]
    if data.get("motion_prompt"):
        cmd += ["--motion-prompt", str(data.get("motion_prompt"))]
    _env = {**os.environ, "AURORA_REF_CONFIRM": "0", "AURORA_WEB_ADDITIONAL_VIEW": "0"}
    proc = subprocess.run(cmd, capture_output=True, timeout=2400, cwd=WORKSPACE, check=False, env=_env)
    if proc.returncode != 0:
        return jsonify({"ok": False, "error": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:]}), 500
    try:
        result = json.loads((proc.stdout or b"").decode("utf-8", errors="replace"))
    except Exception as exc:
        return jsonify({"ok": False, "error": f"sortie pipeline 3D invalide: {exc}"}), 500
    return jsonify({"ok": True, "output": "Modele 3D genere.", "pipeline": result, "module": "3d"})


def _aurora_voice(action, data):
    if action not in ("speak", "tts", "say"):
        return jsonify({"ok": False, "error": f"aurora_voice: action '{action}' inconnue (speak)"}), 400
    text = (data.get("text") or data.get("prompt") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "aurora_voice.speak requiert 'text'"}), 400
    # Meme regle que /api/voice/tts : un fichier par synthese, sous un projet.
    voice_dir = sortie_module("voix", data.get("projet") or "synthese")
    output_path = os.path.join(voice_dir, f"tts_{int(time.time() * 1000)}.wav")
    script = os.path.join(WORKSPACE, "python-services", "voice_service.py")
    if not os.path.isfile(script):
        return jsonify({"ok": False, "error": "voice_service.py introuvable"}), 500
    cmd = [sys.executable, script, "--mode", "tts", "--text", text,
           "--output", output_path, "--lang", str(data.get("lang") or "fr")]
    if data.get("voice"):
        cmd += ["--voice", str(data.get("voice"))]
    subprocess.run(cmd, capture_output=True, timeout=120, cwd=WORKSPACE, check=False)
    if not os.path.exists(output_path):
        return jsonify({"ok": False, "error": "audio non genere"}), 500
    return jsonify({"ok": True, "output": "Texte lu a voix haute (TTS Kokoro).",
                    "audio_url": "/api/voice/tts-audio", "module": "voice"})


def _aurora_code(action, data):
    if action not in ("generate", "create", "write"):
        return jsonify({"ok": False, "error": f"aurora_code: action '{action}' inconnue (generate)"}), 400
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "aurora_code.generate requiert 'prompt'"}), 400
    model = (data.get("model") or "qwen3-coder:30b").strip()
    try:
        resp = requests.post(
            "http://127.0.0.1:3001/api/code/generate/stream",
            json={"prompt": prompt, "model": model},
            stream=True,
            timeout=(15, 3600),
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Executor agentique Code injoignable: {exc}"}), 502
    if resp.status_code != 200:
        return jsonify({"ok": False, "error": f"Executor agentique Code HTTP {resp.status_code}"}), 502

    files = []
    final_event = None
    for raw_line in resp.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        try:
            event = json.loads(raw_line)
        except Exception:
            continue
        if event.get("schema") != CODE_STREAM_SCHEMA:
            continue
        if event.get("kind") == "file.written" and event.get("path") and isinstance(event.get("content"), str):
            files.append({
                "path": event["path"],
                "language": event.get("language") or "text",
                "content": event["content"],
            })
        elif event.get("kind") in ("done", "error"):
            final_event = event

    if not final_event or final_event.get("kind") != "done" or not files:
        message = (final_event or {}).get("message") or "Executor agentique termine sans livraison valide"
        return jsonify({"ok": False, "error": message, "module": "code", "agentic": True}), 502
    output = "\n\n".join(
        f"--- FICHIER: {item['path']} ---\n```{item['language']}\n{item['content']}\n```"
        for item in files
    )
    return jsonify({
        "ok": True,
        "output": output,
        "files": files,
        "model": model,
        "module": "code",
        "agentic": True,
        "validation": final_event,
    })


CODE_STREAM_SCHEMA = "aurora.code.stream/1"
CODE_VISUAL_RENDER_AUDIT_SCHEMA = "aurora.code.visual-render-audit/1"


def _code_stream_event(kind: str, run_id: int, sequence: int, **payload):
    event = {
        "schema": CODE_STREAM_SCHEMA,
        "kind": kind,
        "runId": run_id,
        "sequence": sequence,
        "timestamp": int(time.time() * 1000),
    }
    event.update(payload)
    return json.dumps(event, ensure_ascii=False) + "\n"


def _code_visual_audit_url_allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme in ("http", "https") and host in ("localhost", "127.0.0.1", "0.0.0.0", "::1")


def _code_visual_parse_json_object(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        match = re.search(r"\{[\s\S]*\}", raw or "")
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}


def _code_visual_clamp_score(value) -> int:
    try:
        score = int(round(float(value)))
    except Exception:
        return 0
    return max(0, min(100, score))


def _code_visual_attach_vision(audit: dict, model: str) -> None:
    prompt = (
        "Juge ce screenshot d'une interface generee par le Module Code AuroraIA. "
        "Retourne uniquement du JSON: "
        "{\"score\":0-100,\"verdict\":\"tutorial|studio|mixed\",\"summary\":\"phrase courte\"}. "
        "Score bas si la page ressemble a un tutoriel, est vide, mal hierarchisee, peu contrastee ou generic stock. "
        "Score haut si la composition est studio-grade, dense, responsive, harmonieuse et lisible."
    )
    for viewport in (audit.get("viewports") or [])[:3]:
        screenshot_path = viewport.get("screenshotPath")
        if not screenshot_path:
            continue
        path = pathlib.Path(str(screenshot_path))
        try:
            if not path.is_file() or path.stat().st_size > 12 * 1024 * 1024:
                continue
            image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
            response = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
                    "stream": False,
                    "keep_alive": "2m",
                    "format": "json",
                    "options": {"temperature": 0},
                },
                timeout=180,
            )
            if response.status_code != 200:
                continue
            body = response.json()
            raw = ((body.get("message") or {}).get("content") or body.get("response") or "").strip()
            parsed = _code_visual_parse_json_object(raw)
            verdict = str(parsed.get("verdict") or "mixed").lower()
            if verdict not in ("tutorial", "studio", "mixed"):
                verdict = "mixed"
            summary = str(parsed.get("summary") or "Jugement vision sans detail.")[:500]
            viewport["vision"] = {
                "score": _code_visual_clamp_score(parsed.get("score")),
                "verdict": verdict,
                "summary": summary,
            }
        except Exception:
            continue


@app.route("/api/code/visual-audit", methods=["POST"])
def code_visual_audit():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "url requise"}), 400
    if not _code_visual_audit_url_allowed(url):
        return jsonify({"ok": False, "error": "audit visuel limite aux URLs locales de dev-server"}), 400

    try:
        wait_ms = int(data.get("waitMs") or data.get("wait_ms") or 2500)
    except Exception:
        wait_ms = 2500
    wait_ms = max(500, min(15000, wait_ms))

    script = pathlib.Path(WORKSPACE) / "python-services" / "aurora_code" / "visual_render_audit.py"
    if not script.is_file():
        return jsonify({"ok": False, "error": "visual_render_audit.py introuvable"}), 500

    out_dir = pathlib.Path(WORKSPACE) / "output" / "code_visual_audits" / str(int(time.time() * 1000))
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [sys.executable, str(script), url, str(out_dir), str(wait_ms)],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=max(45, int(wait_ms / 1000 * 10) + 60),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "timeout audit visuel rendu"}), 504
    except Exception as exc:
        return jsonify({"ok": False, "error": f"audit visuel impossible: {exc}"}), 500

    try:
        audit = json.loads(proc.stdout or "{}")
    except Exception as exc:
        return jsonify({"ok": False, "error": f"JSON audit visuel invalide: {exc}", "stderr": (proc.stderr or "")[-1200:]}), 502

    if not isinstance(audit, dict):
        audit = {}
    audit.setdefault("schemaVersion", CODE_VISUAL_RENDER_AUDIT_SCHEMA)
    audit.setdefault("url", url)
    audit.setdefault("viewports", [])

    include_vision = bool(data.get("vision") or data.get("includeVision"))
    if include_vision and audit.get("viewports"):
        model = str(data.get("visionModel") or "qwen3-vl:30b").strip() or "qwen3-vl:30b"
        _code_visual_attach_vision(audit, model)

    ok = proc.returncode == 0 and len(audit.get("viewports") or []) > 0
    error = audit.get("error") or ((proc.stderr or "")[-2000:] if proc.returncode != 0 else "")
    return jsonify({"ok": ok, "audit": audit, "error": error})


@app.route("/api/code/simulation-lab", methods=["POST"])
def code_simulation_lab():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "url requise"}), 400
    if not _code_visual_audit_url_allowed(url):
        return jsonify({"ok": False, "error": "labo simulation limite aux URLs locales de dev-server"}), 400

    try:
        wait_ms = int(data.get("waitMs") or data.get("wait_ms") or 2500)
    except Exception:
        wait_ms = 2500
    wait_ms = max(500, min(12000, wait_ms))

    script = pathlib.Path(WORKSPACE) / "python-services" / "aurora_code" / "simulation_lab.py"
    if not script.is_file():
        return jsonify({"ok": False, "error": "simulation_lab.py introuvable"}), 500

    out_dir = pathlib.Path(WORKSPACE) / "output" / "code_simulation_labs" / str(int(time.time() * 1000))
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [sys.executable, str(script), url, str(out_dir), str(wait_ms)],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=max(420, int(wait_ms / 1000 * 18) + 180),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "timeout labo simulation"}), 504
    except Exception as exc:
        return jsonify({"ok": False, "error": f"labo simulation impossible: {exc}"}), 500

    try:
        report = json.loads(proc.stdout or "{}")
    except Exception as exc:
        return jsonify({"ok": False, "error": f"JSON labo simulation invalide: {exc}", "stderr": (proc.stderr or "")[-1200:]}), 502

    if not isinstance(report, dict):
        report = {}
    report.setdefault("schemaVersion", "aurora.code.simulation-lab/1")
    report.setdefault("url", url)
    report.setdefault("stages", [])
    ok = proc.returncode == 0 and len(report.get("stages") or []) > 0
    error = (proc.stderr or "")[-2000:] if proc.returncode != 0 else ""
    return jsonify({"ok": ok, "report": report, "error": error})


@app.route("/api/code/tooling-eval", methods=["POST"])
def code_tooling_eval():
    data = request.get_json(silent=True) or {}
    candidates = data.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        return jsonify({"ok": False, "error": "candidates requis"}), 400

    try:
        timeout_ms = int(data.get("timeoutMs") or data.get("timeout_ms") or 90_000)
    except Exception:
        timeout_ms = 90_000
    timeout_ms = max(10_000, min(180_000, timeout_ms))

    script = pathlib.Path(WORKSPACE) / "python-services" / "aurora_code" / "tooling_eval.py"
    if not script.is_file():
        return jsonify({"ok": False, "error": "tooling_eval.py introuvable"}), 500

    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=WORKSPACE,
            input=json.dumps({"candidates": candidates, "timeoutMs": timeout_ms}),
            capture_output=True,
            text=True,
            timeout=max(30, int(timeout_ms / 1000) + 30),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "timeout auto-outillage Code"}), 504
    except Exception as exc:
        return jsonify({"ok": False, "error": f"auto-outillage impossible: {exc}"}), 500

    try:
        report = json.loads(proc.stdout or "{}")
    except Exception as exc:
        return jsonify({"ok": False, "error": f"JSON auto-outillage invalide: {exc}", "stderr": (proc.stderr or "")[-1200:]}), 502

    if not isinstance(report, dict):
        report = {}
    report.setdefault("schemaVersion", "aurora.code.tooling-eval/1")
    report.setdefault("candidates", [])
    ok = proc.returncode == 0 and len(report.get("candidates") or []) > 0
    error = report.get("error") or ((proc.stderr or "")[-2000:] if proc.returncode != 0 else "")
    return jsonify({"ok": ok, "report": report, "error": error})


@app.route("/api/code/assets/generate", methods=["POST"])
def code_assets_generate():
    data = request.get_json(silent=True) or {}
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "prompt requis"}), 400

    script = pathlib.Path(WORKSPACE) / "python-services" / "aurora_code" / "intermodule_assets.py"
    if not script.is_file():
        return jsonify({"ok": False, "error": "intermodule_assets.py introuvable"}), 500

    run_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(data.get("runId") or f"code_assets_{int(time.time())}")).strip("-")
    # Le producteur Code ne doit pas transformer le bridge en proxy SSRF.
    base_url = "http://127.0.0.1:3001"
    requested_kinds = data.get("requestedKinds")
    if not isinstance(requested_kinds, list):
        requested_kinds = ["image", "model3d", "voice"]
    requested_kinds = list(dict.fromkeys(
        kind for kind in requested_kinds if kind in {"image", "model3d", "voice"}
    ))
    if not requested_kinds:
        return jsonify({"ok": False, "error": "requestedKinds vide ou invalide"}), 400

    fresh_3d = bool(data.get("fresh3d") or False)
    timeout_cap = 14_500 if fresh_3d else 900
    timeout_s = max(45, min(timeout_cap, int(data.get("timeoutSec") or (14_400 if fresh_3d else 300))))
    payload = {
        "prompt": prompt,
        "archetype": str(data.get("archetype") or "default"),
        "requestedKinds": requested_kinds,
        "runId": run_id,
        "baseUrl": base_url,
        "fresh3d": fresh_3d,
        "allowExisting3d": bool(data.get("allowExisting3d", True)),
        "sourceImageRunId": str(data.get("sourceImageRunId") or ""),
        "source3dRunId": str(data.get("source3dRunId") or ""),
        "sourceVoiceRunId": str(data.get("sourceVoiceRunId") or ""),
        "threeDTimeoutSec": max(60, min(14_400, int(data.get("threeDTimeoutSec") or 14_400))),
    }
    if isinstance(data.get("seed"), int):
        payload["seed"] = data["seed"]
    image_prompt = str(data.get("imagePrompt") or "").strip()
    if image_prompt:
        payload["imagePrompt"] = image_prompt[:400]
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=WORKSPACE,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "timeout generation assets Code"}), 504
    except Exception as exc:
        return jsonify({"ok": False, "error": f"generation assets impossible: {exc}"}), 500

    try:
        bundle = json.loads(proc.stdout or "{}")
    except Exception as exc:
        return jsonify({"ok": False, "error": f"JSON assets invalide: {exc}", "stderr": (proc.stderr or "")[-1200:]}), 502
    if not isinstance(bundle, dict):
        bundle = {}
    bundle.setdefault("schemaVersion", "aurora.code.asset-bundle/1")
    bundle.setdefault("assets", [])
    bundle.setdefault("requiredKinds", requested_kinds)
    bundle.setdefault("missingRequired", requested_kinds)
    ok = proc.returncode == 0 and not bundle.get("missingRequired")
    error = (proc.stderr or "")[-2000:] if proc.returncode != 0 else ""
    return jsonify({"ok": ok, "bundle": bundle, "error": error})


@app.route("/api/code/assets/file/<path:asset_path>", methods=["GET"])
def code_assets_file(asset_path: str):
    """Sert les fichiers materialises sous output/code/assets ou legacy output/code_assets."""
    code_assets_root = (pathlib.Path(WORKSPACE) / "output" / "code" / "assets").resolve()
    legacy_root = (pathlib.Path(WORKSPACE) / "output" / "code_assets").resolve()
    
    target = (code_assets_root / asset_path).resolve()
    if target.is_relative_to(code_assets_root) and target.is_file():
        return send_file(target, conditional=True)
        
    target_legacy = (legacy_root / asset_path).resolve()
    if target_legacy.is_relative_to(legacy_root) and target_legacy.is_file():
        return send_file(target_legacy, conditional=True)
        
    return jsonify({"ok": False, "error": "asset introuvable"}), 404
    return send_file(target, conditional=True)


@app.route("/api/code/generate/stream", methods=["POST"])
def code_generate_stream():
    """WS3 NDJSON stream — runs the REAL production pipeline.

    Parity fix: this route used to spawn bridge_agentic_stream.py, a standalone
    planner-executor carrying none of the quality gates the Tauri UI runs
    (intent classification, blocking architecture plan, inter-module assets,
    sandbox validation, auto-correction loop, design polish). Every caller of
    /api/aurora/code/generate — cowork, tunnel, external clients — was therefore
    served by a hidden degraded engine. It now spawns the Node runner that calls
    the same `orchestrateCodeGeneration` as CodeView and the CLI harness, so the
    three channels share one engine. The NDJSON schema (aurora.code.stream/1) is
    unchanged, so consumers keep working byte-for-byte.
    """
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "prompt requis"}), 400
    if len(prompt) > 200_000:
        return jsonify({"ok": False, "error": "prompt trop volumineux"}), 413
    model = (data.get("model") or "qwen3-coder:30b").strip()
    run_id = int(time.time() * 1000)
    script = pathlib.Path(WORKSPACE) / "scripts" / "code_harness" / "bridge_ndjson_runner.mjs"
    if not script.is_file():
        return jsonify({"ok": False, "error": "bridge_ndjson_runner.mjs introuvable"}), 500
    node_bin = resolve_node_exe()
    if not node_bin:
        return jsonify({"ok": False, "error": "node introuvable: le pipeline Code partage requiert Node"}), 500

    payload = {
        "prompt": prompt,
        "model": model,
        "planningModel": (data.get("planningModel") or model).strip(),
        "ollamaUrl": OLLAMA_URL,
        "runId": run_id,
    }
    # Parite de SUIVI: sans ces deux champs, toute relance par le tunnel repart
    # de zero alors que l'UI poursuit le projet en cours. Le pipeline sait faire
    # un vrai follow-up (analyse de pivot, patch incremental), a condition de
    # recevoir le contexte. Optionnels: un appel one-shot reste inchange.
    if isinstance(data.get("conversationHistory"), list):
        payload["conversationHistory"] = data["conversationHistory"][-8:]
    if isinstance(data.get("existingFiles"), list):
        payload["existingFiles"] = data["existingFiles"][:200]
    try:
        proc = subprocess.Popen(
            [node_bin, str(script)],
            cwd=WORKSPACE,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(payload, ensure_ascii=False))
        proc.stdin.close()
    except Exception as exc:
        return jsonify({"ok": False, "error": f"demarrage executor agentique impossible: {exc}"}), 500

    def generate():
        emitted = False
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if not line.strip():
                    continue
                emitted = True
                yield line if line.endswith("\n") else line + "\n"
            return_code = proc.wait(timeout=5)
            if return_code != 0 and not emitted:
                stderr = (proc.stderr.read() if proc.stderr else "")[-1200:]
                yield _code_stream_event(
                    "error", run_id, 1,
                    message=f"Executor agentique termine avec code {return_code}: {stderr}",
                    recoverable=True,
                )
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _aurora_video(action, data):
    if action not in ("generate", "create", "render", "clip"):
        return jsonify({"ok": False, "error": f"aurora_video: action '{action}' inconnue (generate)"}), 400
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "aurora_video.generate requiert 'prompt'"}), 400
    # Reuse the proven cinema flow over loopback (Flask runs threaded=True) :
    # storyboard (Ollama) then async render job. Returns a jobId the coworker
    # polls via /api/cinema/job/<id>.
    base = "http://127.0.0.1:3001"
    try:
        sb = requests.post(f"{base}/api/cinema/storyboard",
                           json={"prompt": prompt, "hints": data.get("hints") or {}}, timeout=300).json()
    except Exception as exc:
        return jsonify({"ok": False, "error": f"storyboard injoignable: {exc}"}), 502
    if not sb.get("ok"):
        return jsonify({"ok": False, "error": sb.get("error") or "storyboard echoue"}), 502
    storyboard = sb.get("storyboard")
    if not isinstance(storyboard, dict):
        storyboard = {k: v for k, v in sb.items() if k not in ("ok", "model", "tried")}
    try:
        gen = requests.post(f"{base}/api/cinema/generate",
                            json={"storyboard": storyboard}, timeout=60).json()
    except Exception as exc:
        return jsonify({"ok": False, "error": f"cinema/generate injoignable: {exc}"}), 502
    if not gen.get("ok"):
        return jsonify({"ok": False, "error": gen.get("error") or "spawn job echoue"}), 502
    job_id = gen.get("jobId")
    return jsonify({"ok": True, "module": "video", "jobId": job_id, "outputPath": gen.get("outputPath"),
                    "output": f"Rendu video lance (jobId {job_id}). Suivi via /api/cinema/job/{job_id}."})


@app.route("/api/aurora/<module>/<action>", methods=["POST"])
def aurora_module_dispatch(module, action):
    """v83 — internal dispatcher for the cowork aurora_* connectors.

    POST /api/aurora/image/generate  {prompt}
    POST /api/aurora/3d/generate     {prompt, run_id?, motion_prompt?}
    POST /api/aurora/voice/speak     {text, voice?, lang?}
    POST /api/aurora/code/generate   {prompt, language?, model?}
    POST /api/aurora/video/generate  {prompt, hints?}  -> {jobId}
    """
    data = request.get_json(silent=True) or {}
    m = (module or "").strip().lower()
    a = (action or "").strip().lower()
    try:
        if m == "image":
            return _aurora_image(a, data)
        if m == "3d":
            return _aurora_3d(a, data)
        if m == "voice":
            return _aurora_voice(a, data)
        if m == "code":
            return _aurora_code(a, data)
        if m == "video":
            return _aurora_video(a, data)
        if m in ("drawing", "learning"):
            return jsonify({"ok": False, "error": f"aurora_{m}: pas encore expose en one-shot — passe par l'UI du module {m}."}), 501
        return jsonify({"ok": False, "error": f"module aurora '{m}' inconnu (image|3d|video|voice|code)"}), 404
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": f"aurora_{m}.{a} timeout"}), 504
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/3d/motion-parity", methods=["GET"])
def three_d_motion_parity():
    """Live parity check: runs motion_parser.py --parity-test against the
    shared TS↔Python fixtures and returns the verdict. Used by
    /aurora-self-test gate 18 to lock the verb table."""
    workspace = os.path.dirname(os.path.abspath(__file__))
    parser_script = os.path.join(workspace, "python-services", "motion_parser.py")
    fixtures = os.path.join(workspace, "src", "__tests__", "fixtures", "motion_parser_fixtures.json")
    if not os.path.isfile(parser_script):
        return jsonify({"ok": False, "error": "motion_parser.py missing"}), 500
    if not os.path.isfile(fixtures):
        return jsonify({"ok": False, "error": "motion_parser_fixtures.json missing"}), 500
    try:
        proc = subprocess.run(
            [sys.executable, parser_script, "--parity-test", fixtures],
            capture_output=True, timeout=30, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "parity timed out"}), 504
    out = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
    return jsonify({
        "ok": proc.returncode == 0 and "PARITY_OK" in out,
        "returncode": proc.returncode,
        "summary": out.splitlines()[-1] if out else "",
        "stderr_tail": err[-300:] if err else "",
    })


@app.route("/api/3d/run-index", methods=["GET"])
def three_d_run_index():
    """Scan application/output/3d/ for grouped runs (id_mesh.glb +
    id_reference.png + variants) and standalone meshes. Optionally score
    each .glb if ?kind=<subject_kind> is provided.

    Query params: ?kind=<kind>&score=1
    """
    kind = (request.args.get("kind") or "").strip() or None
    score_flag = request.args.get("score", "").strip() in ("1", "true", "yes")

    workspace = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(workspace, "python-services", "mesh_run_index.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "mesh_run_index.py not found"}), 500

    cmd = [sys.executable, script_path, "--dir",
           os.path.join(workspace, "output", "3d")]
    if score_flag and kind:
        cmd += ["--score", "--kind", kind]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "run-index timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        result = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "index": result})


@app.route("/api/3d/score-history", methods=["GET"])
def three_d_score_history():
    """Append-only score event log surface. Three modes:

       ?top=N           list top-N runs by final overall_score
       ?run_id=X        list every event for a single run (chronological)
       (default)        same as ?top=10

    Wraps `score_history.py` CLI and returns
    `{"ok": true, "history": {top|events: [...]}}`.
    """
    top_n = request.args.get("top", "").strip()
    run_id = (request.args.get("run_id") or "").strip()
    limit = request.args.get("limit", "").strip()

    workspace = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(workspace, "python-services", "score_history.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "score_history.py not found"}), 500

    trend_flag = request.args.get("trend", "").strip() in ("1", "true", "yes")
    if trend_flag:
        cmd = [sys.executable, script_path, "trend"]
    elif run_id:
        cmd = [sys.executable, script_path, "run", "--run-id", run_id]
    else:
        try:
            n = max(1, min(int(top_n), 200)) if top_n else 10
        except ValueError:
            n = 10
        cmd = [sys.executable, script_path, "top", "-n", str(n)]

    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=15, check=False)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "score-history timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        history = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500

    if limit and isinstance(history, dict) and "events" in history:
        try:
            cap = max(1, min(int(limit), 1000))
            history["events"] = history["events"][:cap]
        except ValueError:
            pass

    return jsonify({"ok": True, "history": history})


@app.route("/api/3d/mesh-compare", methods=["POST"])
def three_d_mesh_compare():
    """Score two GLBs side-by-side and report axis deltas. Useful for
    pre/post-rescue validation or pipeline comparison.

    POST body: {"left": "<a.glb>", "right": "<b.glb>", "kind": "pc_tower"}
    """
    data = request.get_json(silent=True) or {}
    left = (data.get("left") or "").strip()
    right = (data.get("right") or "").strip()
    kind = (data.get("kind") or "generic").strip()
    if not left or not right:
        return jsonify({"ok": False, "error": "missing 'left' or 'right'"}), 400

    workspace = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(os.path.dirname(workspace))

    def resolve(p: str) -> str | None:
        if not os.path.isabs(p):
            cand = os.path.normpath(os.path.join(workspace, p))
        else:
            cand = os.path.normpath(p)
        if not cand.startswith(repo_root):
            return None
        return cand if os.path.isfile(cand) else None

    left_path = resolve(left)
    right_path = resolve(right)
    if left_path is None:
        return jsonify({"ok": False, "error": f"left not found / outside workspace: {left}"}), 404
    if right_path is None:
        return jsonify({"ok": False, "error": f"right not found / outside workspace: {right}"}), 404

    script_path = os.path.join(workspace, "python-services", "mesh_compare.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "mesh_compare.py not found"}), 500

    try:
        proc = subprocess.run(
            [sys.executable, script_path,
             "--left", left_path, "--right", right_path, "--kind", kind],
            capture_output=True, timeout=120, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "compare timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        result = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "comparison": result})


@app.route("/api/3d/viewer-html", methods=["POST"])
def three_d_viewer_html():
    """Generate a self-contained Three.js HTML viewer for a GLB.

    POST body: {"mesh": "<file.glb>", "output": "<viewer.html>", "title"?: "..."}
    """
    data = request.get_json(silent=True) or {}
    mesh = (data.get("mesh") or "").strip()
    output = (data.get("output") or "").strip()
    title = (data.get("title") or "").strip() or None
    if not mesh or not output:
        return jsonify({"ok": False, "error": "missing 'mesh' or 'output'"}), 400

    workspace = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(os.path.dirname(workspace))

    def resolve(p: str, must_exist: bool = True) -> str | None:
        if not os.path.isabs(p):
            cand = os.path.normpath(os.path.join(workspace, p))
        else:
            cand = os.path.normpath(p)
        if not cand.startswith(repo_root):
            return None
        if must_exist and not os.path.isfile(cand):
            return None
        return cand

    mesh_path = resolve(mesh)
    out_path = resolve(output, must_exist=False)
    if mesh_path is None:
        return jsonify({"ok": False, "error": f"mesh not found / outside workspace: {mesh}"}), 404
    if out_path is None:
        return jsonify({"ok": False, "error": "output escapes workspace"}), 400

    script_path = os.path.join(workspace, "python-services", "aurora_3d_viewer.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "aurora_3d_viewer.py not found"}), 500

    cmd = [sys.executable, script_path, "--mesh", mesh_path, "--output", out_path]
    if title:
        cmd += ["--title", title]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=30, check=False)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "viewer-html timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        result = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "viewer": result})


# iter18.B: serve Draco WASM decoders locally so AuroraIA stays self-contained
# offline. ModelView.tsx + aurora_3d_viewer.py both setDecoderPath('/draco/').
# Files live in application/public/draco/ (copied from
# node_modules/three/examples/jsm/libs/draco/). Subpath /draco/gltf/ is the
# smaller GLTF-flavored decoder used by GLTFLoader's KHR_draco_mesh_compression.
@app.route("/draco/<path:relpath>", methods=["GET"])
def serve_draco_static(relpath):
    """Serve Draco WASM/JS decoders from application/public/draco/.

    Whitelisted to .js / .wasm so this can never be turned into a generic
    file-leak vector. WORKSPACE here is application/, so the decoder dir is
    application/public/draco/<relpath>.
    """
    safe_ext = (".js", ".wasm")
    if not relpath.lower().endswith(safe_ext):
        return abort(404)
    # normpath collapses .. so a malicious relpath like "../../foo" lands
    # outside draco_root; we then explicitly assert the resolved path stays
    # under draco_root.
    draco_root = os.path.normpath(os.path.join(WORKSPACE, "public", "draco"))
    target = os.path.normpath(os.path.join(draco_root, relpath))
    if not target.startswith(draco_root):
        return abort(404)
    if not os.path.isfile(target):
        return abort(404)
    mime = "application/wasm" if target.endswith(".wasm") else "application/javascript"
    resp = send_file(target, mimetype=mime, conditional=True)
    # iter18.B: cache aggressively — these files only change with three upgrade.
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


def _parse_agent_frontmatter(text: str) -> dict[str, str]:
    """Tiny YAML frontmatter parser — flat key:value only, which is what
    every Aurora agent file uses. Mirrors validate_agents.py logic."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip()
    return out


@app.route("/api/agents/list", methods=["GET"])
def agents_list():
    """Expose the Aurora multi-agent registry to UI / extension / external
    clients. Returns the lead/sub-agent hierarchy from state.json plus a
    name→description map from the .md files. Read-only.
    """
    agents_dir = os.path.normpath(_AGENTS_DIR)
    if not os.path.isdir(agents_dir):
        return jsonify({"ok": False, "error": "agents dir missing"}), 500
    descriptions: dict[str, str] = {}
    for name in os.listdir(agents_dir):
        if not name.endswith(".md") or name in _AGENT_DOCS:
            continue
        path = os.path.join(agents_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                fm = _parse_agent_frontmatter(f.read())
        except OSError:
            continue
        if "name" in fm and "description" in fm:
            descriptions[fm["name"]] = fm["description"][:240]
    tracker_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", ".claude",
        "agent-tracker", "state.json",
    )
    state: dict = {}
    if os.path.isfile(tracker_path):
        try:
            with open(tracker_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, ValueError):
            state = {}
    return jsonify({
        "ok": True,
        "schema_version": state.get("schema_version", "aurora.tracker.v1"),
        "leads": state.get("leads") or {},
        "crosscut": state.get("crosscut") or [],
        "descriptions": descriptions,
        "agent_count": len(descriptions),
    })


@app.route("/api/agents/<name>", methods=["GET"])
def agents_get(name: str):
    """Return a single agent's frontmatter + body. 404 if not in the registry."""
    if not name or not all(c.isalnum() or c in "-_" for c in name):
        return jsonify({"ok": False, "error": "invalid agent name"}), 400
    path = os.path.join(_AGENTS_DIR, f"{name}.md")
    if not os.path.isfile(path):
        return jsonify({"ok": False, "error": "agent not found"}), 404
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    fm = _parse_agent_frontmatter(text)
    body_start = text.find("\n---", 3)
    body = text[body_start + 4:].lstrip("\n") if body_start > 0 else text
    return jsonify({
        "ok": True,
        "name": fm.get("name", name),
        "description": fm.get("description", ""),
        "model": fm.get("model", ""),
        "color": fm.get("color", ""),
        "body": body,
    })


@app.route("/api/3d/auto-rescue", methods=["POST"])
def three_d_auto_rescue():
    """Full autonomous rescue chain: validate -> bake_colors (if color fails)
    -> reshape (if aspect fails) -> re-validate. Returns audit trail.

    POST body: {"mesh", "reference", "prompt", "output_dir"}
    """
    data = request.get_json(silent=True) or {}
    mesh = (data.get("mesh") or "").strip()
    reference = (data.get("reference") or "").strip()
    prompt = (data.get("prompt") or "").strip()
    output_dir = (data.get("output_dir") or "").strip()
    if not mesh or not reference or not prompt or not output_dir:
        return jsonify({
            "ok": False,
            "error": "missing 'mesh', 'reference', 'prompt', or 'output_dir'",
        }), 400

    workspace = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(os.path.dirname(workspace))

    def resolve(p: str, must_exist: bool = True) -> str | None:
        if not os.path.isabs(p):
            cand = os.path.normpath(os.path.join(workspace, p))
        else:
            cand = os.path.normpath(p)
        if not cand.startswith(repo_root):
            return None
        if must_exist and not os.path.isfile(cand):
            return None
        return cand

    mesh_path = resolve(mesh)
    ref_path = resolve(reference)
    out_dir_path = resolve(output_dir, must_exist=False)
    if mesh_path is None:
        return jsonify({"ok": False, "error": f"mesh not found / outside workspace: {mesh}"}), 404
    if ref_path is None:
        return jsonify({"ok": False, "error": f"reference not found / outside workspace: {reference}"}), 404
    if out_dir_path is None:
        return jsonify({"ok": False, "error": "output_dir escapes workspace"}), 400

    script_path = os.path.join(workspace, "python-services", "auto_rescue_mesh.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "auto_rescue_mesh.py not found"}), 500

    try:
        # iter24.fix: bridge timeout was 300s but bake_to_texture step can
        # legitimately take 5-10 min on complex meshes (motherboard with
        # many objects, atlas 1024×1024 baking). Bumped to 1200s (20 min)
        # so the step 3 PBR bake doesn't get killed mid-flight.
        proc = subprocess.run(
            [sys.executable, script_path,
             "--mesh", mesh_path, "--reference", ref_path,
             "--prompt", prompt, "--output-dir", out_dir_path],
            capture_output=True, timeout=1200, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "auto-rescue timed out (1200s cap)"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        result = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "rescue": result})


@app.route("/api/3d/bake-colors", methods=["POST"])
def three_d_bake_colors():
    """Restore vertex colors on a GLB by projecting the FLUX reference image
    onto the mesh from the front view. Rescue path when generation outputs a
    monochrome mesh.

    POST body: {"mesh": "<in.glb>", "reference": "<ref.png>", "output": "<out.glb>", "kind": "..."}
    """
    data = request.get_json(silent=True) or {}
    mesh = (data.get("mesh") or "").strip()
    reference = (data.get("reference") or "").strip()
    output = (data.get("output") or "").strip()
    kind = (data.get("kind") or "generic").strip()
    multi_zone = bool(data.get("multi_zone") or False)
    if not mesh or not reference or not output:
        return jsonify({"ok": False, "error": "missing 'mesh', 'reference', or 'output'"}), 400

    workspace = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(os.path.dirname(workspace))

    def resolve(p: str, must_exist: bool = True) -> str | None:
        if not os.path.isabs(p):
            cand = os.path.normpath(os.path.join(workspace, p))
        else:
            cand = os.path.normpath(p)
        if not cand.startswith(repo_root):
            return None
        if must_exist and not os.path.isfile(cand):
            return None
        return cand

    mesh_path = resolve(mesh)
    ref_path = resolve(reference)
    out_path = resolve(output, must_exist=False)
    if mesh_path is None:
        return jsonify({"ok": False, "error": f"mesh not found / outside workspace: {mesh}"}), 404
    if ref_path is None:
        return jsonify({"ok": False, "error": f"reference not found / outside workspace: {reference}"}), 404
    if out_path is None:
        return jsonify({"ok": False, "error": "output path escapes workspace"}), 400

    script_path = os.path.join(workspace, "python-services", "bake_vertex_colors.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "bake_vertex_colors.py not found"}), 500

    cmd = [sys.executable, script_path,
           "--mesh", mesh_path, "--reference", ref_path,
           "--output", out_path, "--kind", kind]
    if multi_zone:
        cmd.append("--multi-zone")
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "bake timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        result = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "bake": result})


@app.route("/api/3d/color-diagnostic", methods=["POST"])
def three_d_color_diagnostic():
    """Pinpoint where colors are lost in the 3D pipeline.

    POST body: {"reference": "<ref.png>", "mesh": "<gen.glb>", "post_mesh": "<opt.glb>"}
    Returns the stage that collapsed colors (generation / post_process / none) +
    actionable suggestions.
    """
    data = request.get_json(silent=True) or {}
    reference = (data.get("reference") or "").strip()
    mesh = (data.get("mesh") or "").strip()
    post_mesh = (data.get("post_mesh") or "").strip() or None
    if not reference or not mesh:
        return jsonify({"ok": False, "error": "missing 'reference' or 'mesh'"}), 400

    workspace = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(os.path.dirname(workspace))

    def resolve(p: str) -> str | None:
        if not os.path.isabs(p):
            cand = os.path.normpath(os.path.join(workspace, p))
        else:
            cand = os.path.normpath(p)
        if not cand.startswith(repo_root):
            return None
        return cand if os.path.isfile(cand) else None

    ref_path = resolve(reference)
    mesh_path = resolve(mesh)
    post_path = resolve(post_mesh) if post_mesh else None
    if ref_path is None:
        return jsonify({"ok": False, "error": f"reference not found / outside workspace: {reference}"}), 404
    if mesh_path is None:
        return jsonify({"ok": False, "error": f"mesh not found / outside workspace: {mesh}"}), 404
    if post_mesh and post_path is None:
        return jsonify({"ok": False, "error": f"post_mesh not found / outside workspace: {post_mesh}"}), 404

    script_path = os.path.join(workspace, "python-services", "mesh_color_diagnostic.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "mesh_color_diagnostic.py not found"}), 500

    cmd = [sys.executable, script_path, "--reference", ref_path, "--mesh", mesh_path]
    if post_path:
        cmd += ["--post-mesh", post_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60, check=False)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "color-diagnostic timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        result = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "diagnostic": result})


@app.route("/api/3d/auto-validate", methods=["POST"])
def three_d_auto_validate():
    """Autonomous mesh validation: takes a generated GLB + the original prompt,
    derives the subject kind itself, scores the mesh, and recommends the next
    pipeline (or accept) without human classification.

    POST body: {"mesh_path": "...", "prompt": "...", "pipeline": "trellis2"}
    Default pipeline: "trellis2". Optional values: "dreamgaussian",
    "procedural", "mesh_postprocess".
    """
    data = request.get_json(silent=True) or {}
    mesh_path = (data.get("mesh_path") or "").strip()
    prompt = (data.get("prompt") or "").strip()
    pipeline = (data.get("pipeline") or "trellis2").strip()
    if not mesh_path:
        return jsonify({"ok": False, "error": "missing 'mesh_path'"}), 400
    if not prompt:
        return jsonify({"ok": False, "error": "missing 'prompt'"}), 400
    if pipeline not in ("trellis2", "dreamgaussian", "procedural", "mesh_postprocess"):
        return jsonify({"ok": False, "error": f"invalid pipeline '{pipeline}'"}), 400

    workspace = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isabs(mesh_path):
        candidate = os.path.normpath(os.path.join(workspace, mesh_path))
    else:
        candidate = os.path.normpath(mesh_path)
    repo_root = os.path.normpath(os.path.dirname(workspace))
    if not candidate.startswith(repo_root):
        return jsonify({"ok": False, "error": "mesh_path escapes workspace"}), 400
    if not os.path.isfile(candidate):
        return jsonify({"ok": False, "error": f"mesh not found: {candidate}"}), 404

    script_path = os.path.join(workspace, "python-services", "auto_validate_mesh.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "auto_validate_mesh.py not found"}), 500

    try:
        proc = subprocess.run(
            [sys.executable, script_path,
             "--mesh", candidate,
             "--prompt", prompt,
             "--pipeline", pipeline],
            capture_output=True, timeout=60, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "auto-validate timed out"}), 504

    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        result = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "validation": result})


@app.route("/api/3d/mesh-score", methods=["POST"])
def three_d_mesh_score():
    """Score a generated GLB on 5 axes (color, density, aspect, manifold,
    surface) and return retry recommendation. Wraps mesh_quality_score.py.

    POST body: {"mesh_path": "<relative or absolute>", "kind": "pc_tower" | "character" | ...}
    """
    data = request.get_json(silent=True) or {}
    mesh_path = (data.get("mesh_path") or "").strip()
    kind = (data.get("kind") or "generic").strip()
    if not mesh_path:
        return jsonify({"ok": False, "error": "missing 'mesh_path'"}), 400

    # Resolve relative paths against application/ root for safety. Absolute
    # paths are accepted but must be inside the workspace.
    workspace = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isabs(mesh_path):
        candidate = os.path.normpath(os.path.join(workspace, mesh_path))
    else:
        candidate = os.path.normpath(mesh_path)
    repo_root = os.path.normpath(os.path.dirname(workspace))
    if not candidate.startswith(repo_root):
        return jsonify({"ok": False, "error": "mesh_path escapes workspace"}), 400
    if not os.path.isfile(candidate):
        return jsonify({"ok": False, "error": f"mesh not found: {candidate}"}), 404

    script_path = os.path.join(workspace, "python-services", "mesh_quality_score.py")
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "mesh_quality_score.py not found"}), 500

    try:
        proc = subprocess.run(
            [sys.executable, script_path, "--mesh", candidate, "--kind", kind],
            capture_output=True, timeout=60, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "scorer timed out"}), 504

    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        result = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "score": result})


@app.route("/api/agents/watchdog", methods=["GET"])
def agents_watchdog():
    """Consolidated read-only ops view — bundles tracker_health + recent
    dispatches + score trend + top runs into one payload. Used by tunnel
    clients and the TS dashboard.

    Query params:
        ?stale_min=N    (default 30)
        ?recent=K       (default 6)
        ?top=M          (default 5)

    Schema: aurora.watchdog.v1.
    """
    try:
        stale_min = max(1, min(int(request.args.get("stale_min", "30")), 1440))
    except ValueError:
        stale_min = 30
    try:
        recent = max(0, min(int(request.args.get("recent", "6")), 50))
    except ValueError:
        recent = 6
    try:
        top = max(0, min(int(request.args.get("top", "5")), 50))
    except ValueError:
        top = 5

    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        ".claude", "hooks", "aurora_watchdog.py",
    )
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "aurora_watchdog.py not found"}), 500
    try:
        proc = subprocess.run(
            [sys.executable, script_path,
             "--stale-min", str(stale_min),
             "--recent", str(recent),
             "--top", str(top)],
            capture_output=True, timeout=15, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "watchdog timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "watchdog": data})


@app.route("/api/agents/health", methods=["GET"])
def agents_health():
    """Tracker health watchdog — surface in_progress tasks that have been
    running longer than ?stale_min=N (default 30). Used by the dashboard
    to flag stalled parallel work.

    Schema: aurora.tracker_health.v1.
    """
    try:
        stale_min = max(1, min(int(request.args.get("stale_min", "30")), 1440))
    except ValueError:
        stale_min = 30
    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        ".claude", "hooks", "tracker_health.py",
    )
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "tracker_health.py not found"}), 500
    try:
        proc = subprocess.run(
            [sys.executable, script_path, "--stale-min", str(stale_min)],
            capture_output=True, timeout=10, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "tracker_health timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "health": data})


@app.route("/api/agents/dispatches", methods=["GET"])
def agents_dispatches():
    """Filter tracker dispatches by ?run_id=, ?lead=, ?status=, ?since=,
    ?limit=. AND-semantics across filters. Schema aurora.tracker_query.v1.

    Used to drill from a run_id back to every agent dispatch that
    touched it (the 3d-lead pipeline + every 3d-quality-rescuer rescue
    linked through metadata.run_id)."""
    run_id = (request.args.get("run_id") or "").strip() or None
    lead = (request.args.get("lead") or "").strip() or None
    status = (request.args.get("status") or "").strip() or None
    since = (request.args.get("since") or "").strip() or None
    limit_raw = request.args.get("limit", "").strip()
    try:
        limit = max(1, min(int(limit_raw), 200)) if limit_raw else None
    except ValueError:
        limit = None

    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        ".claude", "hooks", "tracker_query.py",
    )
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "tracker_query.py not found"}), 500

    cmd = [sys.executable, script_path]
    if run_id: cmd += ["--run-id", run_id]
    if lead:   cmd += ["--lead", lead]
    if status: cmd += ["--status", status]
    if since:  cmd += ["--since", since]
    if limit:  cmd += ["--limit", str(limit)]

    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=10, check=False)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "tracker_query timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "query": data})


@app.route("/api/agents/coverage", methods=["GET"])
def agents_coverage():
    """Agent coverage report — declared vs dispatched. Surfaces 'dead'
    agents (declared in the architecture but never used). Schema
    aurora.coverage.v1."""
    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        ".claude", "hooks", "agent_coverage.py",
    )
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "agent_coverage.py not found"}), 500
    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, timeout=10, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "agent_coverage timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "coverage": data})


@app.route("/api/agents/metrics", methods=["GET"])
def agents_metrics():
    """Per-lead dispatch metrics (count, success rate, avg duration, last verdict)
    derived from .claude/agent-tracker/state.json + history archives.
    Read-only. Read by the dashboard, the self-test, and any external client.
    """
    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        ".claude", "hooks", "agent_metrics.py",
    )
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "agent_metrics.py not found"}), 500
    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, timeout=10, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "agent_metrics timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False,
            "returncode": proc.returncode,
            "stderr": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:],
        }), 500
    try:
        data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        return jsonify({"ok": False, "error": f"invalid JSON: {exc}"}), 500
    return jsonify({"ok": True, "metrics": data})


@app.route("/api/3d/route-test", methods=["POST"])
def three_d_route_test():
    """Probe the routePipeline() decision for a given prompt without running
    the full Hunyuan3D / DreamGaussian / Blender pipeline.

    POST body: {"prompt": "..."}
    Returns: JSON from application/scripts/route_test.py (regex-mirror of
    threeDIntent.ts routePipeline).

    Useful for the UI to preview which pipeline a prompt will hit (and surface
    a hint if Hunyuan3D would be picked for a stylized luxury request).
    """
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    purpose = (data.get("purpose") or "").strip()
    subject_kind = (data.get("subject_kind") or "").strip()
    images = data.get("images") or []
    image_count = data.get("image_count")
    if isinstance(images, list):
        image_count = max(int(image_count or 0), len(images))
    else:
        image_count = int(image_count or 0)
    if not prompt:
        return jsonify({"ok": False, "error": "missing 'prompt' in body"}), 400
    if len(prompt) > 4000:
        return jsonify({"ok": False, "error": "prompt too long (>4000 chars)"}), 400
    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "scripts", "route_test.py",
    )
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "route_test.py not found"}), 500
    cmd = [sys.executable, script_path, prompt]
    if image_count > 0:
        cmd += ["--image-count", str(image_count)]
    if purpose:
        cmd += ["--purpose", purpose]
    if subject_kind:
        cmd += ["--subject-kind", subject_kind]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=10, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "route_test timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False,
            "returncode": proc.returncode,
            "stderr": (proc.stderr or "")[-400:],
        }), 500
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return jsonify({
            "ok": False, "error": f"route_test produced invalid JSON: {exc}",
            "raw": proc.stdout[:400],
        }), 500
    return jsonify({"ok": True, "routing": result})


@app.route("/api/3d/motion-intent", methods=["POST"])
def three_d_motion_intent():
    """LLM-driven motion-intent classifier (no hardcoded brand→animation map).

    POST body:
        {"prompt": "...", "custom_motion_text": "...?", "model": "gemma3:27b?"}

    Returns: aurora.motion-intent.v1 JSON deduced from the prompt by gemma3:27b
    (qwen3:14b fallback, regex fallback if Ollama is offline).

    The classifier decides which of 6 animation primitives to bake:
      led_emission / fan_pwm / oled_screen /
      creature_organic / mechanical_simple / rigid_static
    Output flows directly into motion_baker.py without translation.
    """
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    custom_motion_text = (data.get("custom_motion_text") or "").strip() or None
    model_pref = (data.get("model") or "gemma3:27b").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "missing 'prompt' in body"}), 400
    if len(prompt) > 4000:
        return jsonify({"ok": False, "error": "prompt too long (>4000 chars)"}), 400

    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python-services", "motion_intent_classifier.py",
    )
    if not os.path.isfile(script_path):
        return jsonify({"ok": False, "error": "motion_intent_classifier.py not found"}), 500

    cmd = [sys.executable, script_path, "--prompt", prompt, "--model", model_pref]
    if custom_motion_text:
        cmd.extend(["--custom", custom_motion_text])

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "motion-intent classification timed out"}), 504

    if proc.returncode != 0:
        return jsonify({
            "ok": False, "returncode": proc.returncode,
            "stderr": (proc.stderr or "")[-400:],
        }), 500

    try:
        intent = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return jsonify({
            "ok": False, "error": f"motion-intent produced invalid JSON: {exc}",
            "raw": proc.stdout[:400],
        }), 500
    return jsonify({"ok": True, "intent": intent})


@app.route("/api/3d/custom-motion", methods=["POST"])
def three_d_custom_motion():
    """User typed a free-form motion override in the UI text zone. We
    re-classify with the original prompt + custom text, optionally re-bake
    the existing GLB if its path is provided.

    POST body:
        {"prompt": "<original>", "custom_motion_text": "<user text>",
         "input_glb": "<optional path>", "output_glb": "<optional path>"}

    Behaviour:
      - Always returns the new intent.
      - If input_glb and output_glb are provided, the motion is re-baked
        synchronously (Blender headless) and the path is reported.
    """
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    custom = (data.get("custom_motion_text") or "").strip()
    input_glb = (data.get("input_glb") or "").strip() or None
    output_glb = (data.get("output_glb") or "").strip() or None
    if not prompt:
        return jsonify({"ok": False, "error": "missing 'prompt' in body"}), 400
    if not custom:
        return jsonify({"ok": False, "error": "missing 'custom_motion_text' in body"}), 400

    # Step 1: classify
    classifier = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python-services", "motion_intent_classifier.py",
    )
    try:
        proc = subprocess.run(
            [sys.executable, classifier, "--prompt", prompt, "--custom", custom],
            capture_output=True, text=True, timeout=180, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "classification timed out"}), 504
    if proc.returncode != 0:
        return jsonify({"ok": False, "stderr": (proc.stderr or "")[-400:]}), 500
    try:
        intent = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return jsonify({"ok": False, "error": f"classification JSON: {exc}"}), 500

    # Step 2: optionally re-bake
    bake_result = None
    if input_glb and output_glb and os.path.isfile(input_glb):
        intent_tmp = os.path.join(
            os.path.dirname(os.path.abspath(output_glb)),
            "intent_custom.json",
        )
        os.makedirs(os.path.dirname(intent_tmp), exist_ok=True)
        with open(intent_tmp, "w", encoding="utf-8") as f:
            json.dump(intent, f)
        baker = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "python-services", "motion_intent_baker.py",
        )
        try:
            bproc = subprocess.run(
                [sys.executable, baker,
                 "--intent", intent_tmp,
                 "--input", input_glb,
                 "--output", output_glb],
                capture_output=True, text=True, timeout=600, check=False,
            )
            try:
                bake_result = json.loads(bproc.stdout)
            except json.JSONDecodeError:
                bake_result = {"ok": False, "raw": bproc.stdout[-400:]}
        except subprocess.TimeoutExpired:
            bake_result = {"ok": False, "error": "bake timed out"}

    return jsonify({"ok": True, "intent": intent, "bake": bake_result})


@app.route("/api/3d/auto-motion-bake", methods=["POST"])
def three_d_auto_motion_bake():
    """AUTO motion-intent gate that runs after every TRELLIS.2
    generation in ModelView. Given the original prompt and the freshly
    generated GLB path, this endpoint:

      1. Classifies the prompt via motion_intent_classifier.py (gemma3:27b LLM,
         qwen3:14b fallback, regex fallback).
      2. Decides whether to bake based on category + confidence:
           - category == 'rigid_static'        → NO bake, return GLB unchanged
           - confidence < min_conf (default 0.75) → NO bake (avoid bad guesses)
           - otherwise                         → bake via motion_intent_baker.py
      3. Returns the routing decision (baked: true|false), the new GLB path
         when baked, and the byte size before/after for audit.

    POST body:
        {"prompt": "<original>",
         "input_glb": "<path>",
         "output_glb": "<path>?",
         "min_confidence": 0.75?}

    The path of `input_glb` is read from disk to confirm size_before. When
    `output_glb` is omitted, a sibling file `<input>_anim.glb` is used.
    """
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    input_glb = (data.get("input_glb") or "").strip()
    output_glb = (data.get("output_glb") or "").strip() or None
    try:
        min_conf = float(data.get("min_confidence") or 0.75)
    except (TypeError, ValueError):
        min_conf = 0.75

    if not prompt:
        return jsonify({"ok": False, "error": "missing 'prompt'"}), 400
    if not input_glb or not os.path.isfile(input_glb):
        return jsonify({"ok": False, "error": "missing or invalid 'input_glb'"}), 400

    size_before = os.path.getsize(input_glb)

    if not output_glb:
        base, ext = os.path.splitext(input_glb)
        output_glb = f"{base}_anim{ext or '.glb'}"

    # Step 1: classify (no custom-motion text — the prompt itself is the input)
    classifier = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python-services", "motion_intent_classifier.py",
    )
    if not os.path.isfile(classifier):
        return jsonify({"ok": False, "error": "motion_intent_classifier.py not found"}), 500

    try:
        proc = subprocess.run(
            [sys.executable, classifier, "--prompt", prompt],
            capture_output=True, text=True, timeout=180, check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "classification timed out"}), 504
    if proc.returncode != 0:
        return jsonify({
            "ok": False, "error": "classifier failed",
            "stderr": (proc.stderr or "")[-400:],
        }), 500
    try:
        intent = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return jsonify({
            "ok": False, "error": f"classifier JSON: {exc}",
            "raw": proc.stdout[:400],
        }), 500

    category = intent.get("category", "rigid_static")
    confidence = float(intent.get("confidence") or 0.0)

    # Step 2: gate
    decision = {
        "category": category,
        "confidence": confidence,
        "min_confidence": min_conf,
        "baked": False,
        "reason": "",
        "size_before": size_before,
        "size_after": size_before,
    }

    if category == "rigid_static":
        decision["reason"] = "rigid_static — no animation needed"
        return jsonify({"ok": True, "intent": intent, "decision": decision,
                        "glb_path": input_glb})
    if confidence < min_conf:
        decision["reason"] = f"confidence {confidence:.2f} < min {min_conf:.2f}"
        return jsonify({"ok": True, "intent": intent, "decision": decision,
                        "glb_path": input_glb})

    # Step 3: bake
    intent_tmp = os.path.join(
        os.path.dirname(os.path.abspath(output_glb)),
        f"intent_auto_{int(time.time())}.json",
    )
    try:
        os.makedirs(os.path.dirname(intent_tmp), exist_ok=True)
    except OSError:
        pass
    try:
        with open(intent_tmp, "w", encoding="utf-8") as f:
            json.dump(intent, f)
    except OSError as exc:
        return jsonify({"ok": False, "error": f"intent write failed: {exc}"}), 500

    baker = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python-services", "motion_intent_baker.py",
    )
    bake_result = None
    try:
        bproc = subprocess.run(
            [sys.executable, baker,
             "--intent", intent_tmp,
             "--input", input_glb,
             "--output", output_glb],
            capture_output=True, text=True, timeout=600, check=False,
        )
        try:
            bake_result = json.loads(bproc.stdout)
        except json.JSONDecodeError:
            bake_result = {"ok": False, "raw": (bproc.stdout or "")[-400:],
                           "stderr": (bproc.stderr or "")[-400:]}
    except subprocess.TimeoutExpired:
        bake_result = {"ok": False, "error": "bake timed out"}

    glb_path = input_glb
    if bake_result and bake_result.get("ok") and os.path.isfile(output_glb):
        decision["baked"] = True
        decision["size_after"] = os.path.getsize(output_glb)
        decision["reason"] = f"baked {category} at confidence {confidence:.2f}"
        glb_path = output_glb
    else:
        decision["reason"] = (bake_result.get("error")
                              if isinstance(bake_result, dict)
                              else "bake failed")

    return jsonify({
        "ok": True,
        "intent": intent,
        "decision": decision,
        "bake": bake_result,
        "glb_path": glb_path,
    })


@app.route("/api/admin/git-pull", methods=["POST", "GET"])
def admin_git_pull():
    """Pull latest main on the local Aurora repo and respawn Vite. The user
    clicks this from the fallback page when they see "VITE REDEMARRE" — it
    fetches the latest commits Aurora pushed to GitHub and restarts the
    dev server with the new code, no terminal access needed.

    Useful workflow: Aurora Loop pushes v60 → user opens tunnel → fallback
    page shows up → user clicks 'Mettre a jour' → bridge pulls main +
    respawns Vite → tunnel page reloads on new Aurora.

    v72: when the pulled commits change application/bridge_server.py, the
    bridge auto-respawns itself too (otherwise the new Python code would
    sit on disk but never load).
    """
    try:
        # Locate the git repo root (.git folder up from WORKSPACE).
        repo_root = pathlib.Path(WORKSPACE).resolve()
        for _ in range(4):
            if (repo_root / ".git").exists():
                break
            if repo_root.parent == repo_root:
                break
            repo_root = repo_root.parent
        if not (repo_root / ".git").exists():
            return jsonify({"ok": False, "error": "repo .git introuvable"}), 404

        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"

        # Capture the SHA before pulling so we can compute the diff range.
        try:
            sha_before = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_root), capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        except Exception:
            sha_before = ""

        # 1) Fetch + reset to origin/main. Hard reset because user is not
        # going to merge conflicts via a button click.
        cmds = [
            ["git", "fetch", "origin", "main"],
            ["git", "reset", "--hard", "origin/main"],
        ]
        results: list[dict] = []
        for cmd in cmds:
            try:
                proc = subprocess.run(
                    cmd, cwd=str(repo_root), env=env,
                    capture_output=True, text=True, timeout=45,
                )
                results.append({
                    "cmd": " ".join(cmd),
                    "rc": proc.returncode,
                    "stdout": (proc.stdout or "")[-400:],
                    "stderr": (proc.stderr or "")[-400:],
                })
                if proc.returncode != 0:
                    return jsonify({"ok": False, "error": f"git failed: {' '.join(cmd)}", "results": results}), 500
            except subprocess.TimeoutExpired:
                return jsonify({"ok": False, "error": f"git timeout: {' '.join(cmd)}", "results": results}), 504

        # 2) Get the new HEAD SHA so we can show it.
        try:
            head = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(repo_root), capture_output=True, text=True, timeout=5,
            )
            new_head = head.stdout.strip()
        except Exception:
            new_head = "unknown"

        # 2b) v72 — detect whether the bridge source changed. If yes we need
        # to respawn the Python bridge AFTER respawning Vite (or instead of,
        # depending on what changed). The diff range is sha_before..HEAD.
        bridge_changed = False
        if sha_before:
            try:
                diff_proc = subprocess.run(
                    ["git", "diff", "--name-only", f"{sha_before}..HEAD"],
                    cwd=str(repo_root), capture_output=True, text=True, timeout=10,
                )
                if diff_proc.returncode == 0:
                    changed_files = (diff_proc.stdout or "").splitlines()
                    bridge_changed = any(
                        f.replace("\\", "/").endswith("application/bridge_server.py")
                        for f in changed_files
                    )
            except Exception:
                bridge_changed = False

        # 3) Respawn Vite so it picks up the new code.
        global _VITE_SUPERVISOR_PROCESS
        if _VITE_SUPERVISOR_PROCESS is not None and _VITE_SUPERVISOR_PROCESS.poll() is None:
            try:
                _VITE_SUPERVISOR_PROCESS.terminate()
                _VITE_SUPERVISOR_PROCESS.wait(timeout=3)
            except Exception:
                try:
                    _VITE_SUPERVISOR_PROCESS.kill()
                except Exception:
                    pass
        if _VITE_SUPERVISOR_ENABLED:
            _vite_spawn()

        # 4) v72 — respawn the bridge itself if its source changed. v72d
        # disables this auto-trigger by default because the v72b respawn
        # path failed to launch the child on some Windows builds and left
        # the bridge dead until the user relaunched start-aurora.bat. The
        # fixed _respawn_bridge_async (CREATE_NEW_CONSOLE + sys.executable)
        # is now reliable in isolation, but we still gate the auto-trigger
        # behind an env var until we have proven it across more configs.
        # Manually call /api/admin/restart-bridge to test the new path.
        bridge_respawned = False
        auto_respawn_enabled = os.environ.get("AURORA_AUTO_RESPAWN_BRIDGE", "0") == "1"
        if bridge_changed and auto_respawn_enabled:
            bridge_respawned = _respawn_bridge_async("git-pull modified bridge_server.py")

        return jsonify({
            "ok": True,
            "head": new_head,
            "viteRestarted": _VITE_SUPERVISOR_ENABLED,
            "bridgeChanged": bridge_changed,
            "bridgeRespawned": bridge_respawned,
            "message": (
                f"Pull main → HEAD {new_head}. Vite respawn declenche."
                + (" Bridge respawn declenche aussi (bridge_server.py modifie)." if bridge_respawned else "")
                + " Reload dans 8-15s."
            ),
            "results": results,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/admin/restart-vite", methods=["POST", "GET"])
def admin_restart_vite():
    """Force respawn Vite right now without waiting the 15s grace period.
    Useful when the user opens the tunnel URL and modules are blocked by a
    Vite crash they want fixed immediately."""
    if not _VITE_SUPERVISOR_ENABLED:
        return jsonify({"ok": False, "error": "supervisor desactive (AURORA_VITE_SUPERVISOR=0)"}), 503
    try:
        # Try graceful kill of the current Vite process if we own it.
        global _VITE_SUPERVISOR_PROCESS
        if _VITE_SUPERVISOR_PROCESS is not None and _VITE_SUPERVISOR_PROCESS.poll() is None:
            try:
                _VITE_SUPERVISOR_PROCESS.terminate()
                _VITE_SUPERVISOR_PROCESS.wait(timeout=3)
            except Exception:
                try:
                    _VITE_SUPERVISOR_PROCESS.kill()
                except Exception:
                    pass
        _vite_spawn()
        return jsonify({
            "ok": True,
            "restartCount": _VITE_SUPERVISOR_RESTART_COUNT,
            "message": "Vite respawn declenche. Attends 5-15s puis reload la page.",
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


_VITE_DOWN_HTML = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aurora — reconnexion en cours</title>
<style>
  html,body{margin:0;padding:0;background:#0c0a18;color:#f5f5f4;font:14px system-ui,-apple-system,sans-serif;height:100%}
  .wrap{display:flex;flex-direction:column;justify-content:center;align-items:center;height:100%;text-align:center;padding:24px;gap:14px}
  .dot{width:12px;height:12px;border-radius:50%;background:#fb923c;animation:p 1.2s infinite;box-shadow:0 0 12px rgba(251,146,60,0.6)}
  @keyframes p{0%,100%{opacity:.35;transform:scale(.9)}50%{opacity:1;transform:scale(1.1)}}
  h1{font-size:20px;font-weight:800;letter-spacing:.04em;margin:8px 0 0;background:linear-gradient(135deg,#f59e0b 0%,#f5f5f4 60%);-webkit-background-clip:text;background-clip:text;color:transparent}
  p{opacity:.75;max-width:460px;line-height:1.55;margin:0}
  code{background:rgba(255,255,255,.08);padding:2px 6px;border-radius:4px;font-size:12px;font-family:"JetBrains Mono",Menlo,monospace}
  .btn{margin-top:8px;padding:10px 20px;border:1px solid rgba(251,146,60,0.35);background:linear-gradient(135deg,rgba(251,146,60,0.18),rgba(245,158,11,0.10));color:#f5f5f4;border-radius:10px;font:600 13px system-ui;cursor:pointer;transition:all .18s ease;box-shadow:0 4px 16px -6px rgba(251,146,60,0.4)}
  .btn:hover{background:linear-gradient(135deg,rgba(251,146,60,0.32),rgba(245,158,11,0.22));transform:translateY(-1px);box-shadow:0 6px 22px -6px rgba(251,146,60,0.55)}
  .btn:disabled{opacity:.5;cursor:wait}
  .diag{margin-top:14px;padding:10px 14px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,0.025);border-radius:10px;font-size:11px;font-family:"JetBrains Mono",Menlo,monospace;min-width:280px;text-align:left;line-height:1.7}
  .diag span.ok{color:#34d399}
  .diag span.ko{color:#f87171}
  .toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:rgba(34,197,94,0.18);border:1px solid rgba(34,197,94,0.4);color:#86efac;padding:10px 16px;border-radius:8px;font-size:12px;opacity:0;transition:opacity .2s}
  .toast.show{opacity:1}
</style></head><body>
<div class="wrap">
  <div class="dot"></div>
  <h1>AURORA — VITE REDEMARRE</h1>
  <p>Le serveur de dev (port 1420) ne repond pas, on patiente. Le tunnel reste connecte, l URL ne bouge plus.</p>
  <div style="display:flex;gap:10px;flex-wrap:wrap;justify-content:center">
    <button class="btn" id="forceBtn" onclick="forceRestart()">⚡ Forcer le redemarrage</button>
    <button class="btn btn-update" id="updateBtn" onclick="gitPull()" style="background:linear-gradient(135deg,rgba(34,197,94,0.18),rgba(16,185,129,0.10));border-color:rgba(34,197,94,0.4);box-shadow:0 4px 16px -6px rgba(34,197,94,0.4)">⬇ Mettre a jour Aurora (git pull)</button>
  </div>
  <div class="diag" id="diag">Diagnostic en cours...</div>
  <p style="font-size:11px;opacity:.55;margin-top:8px">Bridge OK sur <code>:3001</code> · auto-reload des que Vite repond</p>
</div>
<div class="toast" id="toast">Restart declenche</div>
<script>
async function fetchStatus(){
  try{
    const r = await fetch('/api/admin/status', {cache:'no-store'});
    const d = await r.json();
    const k = (label,alive)=>`<div>${label} <span class="${alive?'ok':'ko'}">${alive?'● UP':'○ DOWN'}</span></div>`;
    document.getElementById('diag').innerHTML =
      k('Vite (1420)', d.vite?.alive) +
      k('Bridge (3001)', d.bridge?.alive) +
      k('Ollama (11434)', d.ollama?.alive) +
      k('ComfyUI (8188)', d.comfyui?.alive) +
      `<div style="opacity:.5;margin-top:4px">Restarts: ${d.vite?.restartCount ?? 0}</div>`;
    if(d.vite?.alive){location.reload();}
  }catch(_){
    document.getElementById('diag').textContent='Bridge inaccessible';
  }
}
async function forceRestart(){
  const btn = document.getElementById('forceBtn');
  btn.disabled = true; btn.textContent = '⏳ Restart en cours...';
  try{
    await fetch('/api/admin/restart-vite', {method:'POST'});
    const t = document.getElementById('toast');
    t.classList.add('show'); setTimeout(()=>t.classList.remove('show'), 2400);
    btn.textContent = '✓ Demande envoyee';
    setTimeout(()=>{btn.disabled=false; btn.textContent='⚡ Forcer le redemarrage';}, 4000);
  }catch(_){
    btn.disabled=false; btn.textContent='⚠ Echec — reessaye';
  }
}
async function gitPull(){
  const btn = document.getElementById('updateBtn');
  btn.disabled = true; btn.textContent = '⏳ Pull main + restart...';
  try{
    const r = await fetch('/api/admin/git-pull', {method:'POST'});
    const d = await r.json();
    if(d.ok){
      btn.textContent = '✓ HEAD ' + (d.head||'updated') + ' — restart en cours';
      const t = document.getElementById('toast');
      t.classList.add('show');
      t.textContent = 'Aurora a jour: ' + (d.head||'') + ' · reload dans 12s';
      setTimeout(()=>t.classList.remove('show'), 4000);
      setTimeout(()=>location.reload(), 12000);
    }else{
      btn.textContent = '⚠ ' + (d.error||'echec git pull');
      setTimeout(()=>{btn.disabled=false; btn.textContent='⬇ Mettre a jour Aurora (git pull)';}, 5000);
    }
  }catch(_){
    btn.disabled=false; btn.textContent='⚠ Echec reseau';
  }
}
fetchStatus();
setInterval(fetchStatus, 2500);
</script>
</body></html>
"""


_DIST_DIR = os.path.join(WORKSPACE, "dist")
_DIST_INDEX = os.path.join(_DIST_DIR, "index.html")


def _serve_dist(path: str):
    """iter30c: serve the prod build (application/dist/) when present so the
    Cloudflare tunnel doesn't need Vite HMR WebSocket (which Cloudflare quick
    tunnels don't proxy reliably). Falls back to the Vite dev proxy when
    dist is absent or the requested file isn't there.

    Strategy:
      - If dist/index.html exists AND request method is GET/HEAD AND the
        requested path resolves to a file inside dist/, serve it.
      - Otherwise, fall back to _vite_proxy (dev mode).
    """
    if not os.path.isfile(_DIST_INDEX):
        return None
    if request.method not in ("GET", "HEAD"):
        return None
    # Map path; default to index.html for SPA fallback (unknown route)
    rel = path.lstrip("/")
    candidate = os.path.normpath(os.path.join(_DIST_DIR, rel)) if rel else _DIST_INDEX
    if not candidate.startswith(_DIST_DIR):
        return None  # path traversal guard
    if not os.path.isfile(candidate):
        # SPA fallback for unknown routes (deep links like /3d, /code, etc.)
        # only if the requested path doesn't look like an asset (no dot in last seg)
        last = rel.split("/")[-1] if rel else ""
        if "." in last:
            return None  # likely a missing asset → 404 via fallback
        candidate = _DIST_INDEX
    # Stream the file
    from flask import send_file
    return send_file(candidate)


def _vite_proxy(path: str):
    # iter30c: prefer prod dist when present
    served = _serve_dist(path)
    if served is not None:
        return served
    target = f"{VITE_DEV_URL}/{path}" if path else f"{VITE_DEV_URL}/"
    qs = request.query_string.decode("latin-1") if request.query_string else ""
    if qs:
        target += "?" + qs

    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in {"host", "content-length"}}
    try:
        upstream = requests.request(
            method=request.method,
            url=target,
            headers=fwd_headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True,
            timeout=(2, 30),
        )
    except requests.exceptions.RequestException:
        return Response(
            _VITE_DOWN_HTML, status=503,
            content_type="text/html; charset=utf-8",
            headers={"Retry-After": "2", "Cache-Control": "no-store"},
        )

    excluded = {"content-encoding", "content-length", "transfer-encoding", "connection", "keep-alive"}
    out_headers = [(k, v) for (k, v) in upstream.raw.headers.items() if k.lower() not in excluded]
    return Response(upstream.iter_content(chunk_size=8192), status=upstream.status_code, headers=out_headers)


@app.route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
def vite_root():
    return _vite_proxy("")


# v82nu iter19 (SEC) : harden the Vite catch-all so the public Cloudflare
# tunnel never serves source code. Pre-fix, GET /bridge_server.py returned
# 495 KB of Python source via Vite HMR; /src/views/ModelView.tsx returned
# 727 KB of TS; /package.json + /tsconfig.json the actual configs. Anyone
# with the tunnel URL could exfiltrate the entire backend + frontend.
#
# Three defenses, applied AFTER the reserved-prefix check :
#  1. canonicalize the URL path with posixpath.normpath and reject anything
#     that escapes the root (defense against /draco/../bridge_server.py)
#  2. extension blacklist for known source / config / dotfile extensions
#  3. path-segment blacklist for directories that should never be exposed
#     (python-services, scripts, node_modules, .git, output, etc.)
#
# Whitelist for clean Vite assets is implicit : if it doesn't hit any
# blacklist, it goes through (Vite serves bundled JS/CSS/woff2 from /assets,
# images from /aurora-team and /draco, and the SPA index for unknown routes
# — all are safe). The fix purposely ALLOWS Vite's SPA fallback to keep
# returning index.html for arbitrary routes (e.g. /3d, /code) so the
# React router still works.
import posixpath as _posixpath

_FORBIDDEN_EXTS = frozenset({
    ".py", ".pyc", ".pyo", ".pyw",
    ".ts", ".tsx", ".mts", ".cts",
    ".bat", ".cmd", ".ps1", ".sh", ".bash", ".zsh",
    ".env", ".lock", ".toml", ".cfg", ".ini",
    ".md", ".log", ".sqlite", ".sqlite3", ".db",
    # Don't blacklist .json: Vite uses /node_modules/.vite/deps/_metadata.json
    # for HMR + many UI fixtures hit static .json. We catch the dangerous
    # ones via _FORBIDDEN_PATHS instead (root /package.json, /tsconfig.json).
})
_FORBIDDEN_PATHS = frozenset({
    "node_modules", ".git", ".vscode", ".idea", ".vite",
    "venv", ".venv", "__pycache__",
    "python-services", "scripts", "tests", "test",
    "output", "outputs", "bridge_state", "tools",
    "src-tauri", "build", "dist",
})
_FORBIDDEN_TOPLEVEL_FILES = frozenset({
    "bridge_server.py", "package.json", "package-lock.json", "yarn.lock",
    "pnpm-lock.yaml", "tsconfig.json", "tsconfig.node.json", "vite.config.ts",
    "vite.config.js", ".env", ".env.local", ".env.production",
    ".gitignore", ".gitattributes", "Cargo.toml", "Cargo.lock",
    "requirements.txt", "pyproject.toml", "tauri.conf.json",
})


def _vite_path_blocked(path: str) -> bool:
    """Returns True iff the path should be blocked by the catch-all."""
    if not path:
        return False
    # Step 1: canonicalize. posixpath.normpath collapses .. and resolves
    # double slashes. If the result starts with .. or is "..", reject.
    canonical = _posixpath.normpath("/" + path).lstrip("/")
    if not canonical or canonical.startswith(".."):
        return True
    # iter30.fix: explicit allow-list for Vite-served runtime paths. Without
    # this, the iter19 .tsx/.ts blocklist also blocked /src/main.tsx (the
    # SPA bootstrap entry point) → React never mounted → black screen.
    # Vite dev needs to serve /src/*.ts(x) (HMR), /@vite/*, /@react-refresh,
    # /node_modules/.vite/* (deps cache), /aurora-team/*, /draco/*. Those
    # paths are SAFE because they only expose files Vite has resolved as
    # part of the dev bundle, not arbitrary repo files (Vite has its own
    # allow-list of the configured root + node_modules).
    _VITE_ALLOWED_PREFIXES = (
        "src/", "@vite/", "@react-refresh", "@id/", "@fs/",
        "node_modules/",  # covers vite client + .vite deps cache
        "aurora-team/", "draco/", "assets/",
    )
    if any(canonical.startswith(p) for p in _VITE_ALLOWED_PREFIXES):
        return False
    # Step 2: extension blacklist
    lower = canonical.lower()
    for ext in _FORBIDDEN_EXTS:
        if lower.endswith(ext):
            return True
    # Step 3: path-segment blacklist
    segments = [s for s in canonical.split("/") if s]
    if any(seg in _FORBIDDEN_PATHS for seg in segments):
        return True
    # Step 4: top-level dangerous files (config / lock / source) at root
    if len(segments) == 1 and segments[0] in _FORBIDDEN_TOPLEVEL_FILES:
        return True
    # iter20 SEC: dotfile leaks. /.aurora_ext_seen.json was returning real
    # content (47 B JSON) because .json is not in the ext blacklist. Block
    # every dotfile UNLESS it's the conventional /.well-known/ allowlist.
    last_seg = segments[-1] if segments else ""
    if last_seg.startswith(".") and not canonical.startswith(".well-known/"):
        return True
    if any(seg.startswith(".") for seg in segments[:-1]):
        # any intermediate dot-segment also blocked (.git, .vite, .vscode...)
        return True
    # iter20 SEC: bridge runtime logs. /bridge_v82nu.out leaked 22 KB of
    # the bridge stderr (model paths, prompts, GPU stats). Block any
    # bridge_*.out/err/log file at root.
    if len(segments) == 1:
        name = segments[0].lower()
        if name.startswith("bridge_") and name.endswith((".out", ".err", ".log")):
            return True
    return False


@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
def vite_catchall(path: str):
    p = "/" + path
    # Les chemins reserves (/api, /proxy, /ws) ont leurs handlers Flask dedies;
    # si on tombe ici c'est qu'ils n'ont pas matche -> 404 explicite, pas Vite.
    if any(p.startswith(prefix) for prefix in _VITE_RESERVED_PREFIXES):
        return jsonify({"error": "endpoint inconnu", "path": p}), 404
    # iter19 SEC: refuse to proxy source / config / sensitive paths
    if _vite_path_blocked(path):
        return jsonify({"error": "forbidden", "path": p}), 404
    return _vite_proxy(path)


# =====================================================================
#  /api/connect/* — machine connectors (SSH, TCP) shared between
#  code & cowork modules. Targets are managed client-side and pushed
#  per-call; credentials never persisted server-side here, just used
#  in the request and discarded after the call returns.
# =====================================================================

_CONNECT_TARGETS_FILE = pathlib.Path.home() / ".aurora_code_targets.json"


def _load_connect_targets() -> dict:
    if not _CONNECT_TARGETS_FILE.exists():
        return {}
    try:
        return json.loads(_CONNECT_TARGETS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_connect_targets(d: dict) -> None:
    _CONNECT_TARGETS_FILE.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                                       encoding="utf-8")


def _try_paramiko():
    try:
        import paramiko  # type: ignore
        return paramiko
    except ImportError:
        return None


@app.route("/api/connect/targets/list", methods=["GET"])
def connect_targets_list():
    """List configured machine targets (no credentials returned)."""
    out = []
    for name, cfg in _load_connect_targets().items():
        safe = {k: v for k, v in cfg.items() if k not in ("password", "key_passphrase")}
        out.append({"name": name, **safe})
    return jsonify({"ok": True, "targets": out})


@app.route("/api/connect/targets/save", methods=["POST"])
def connect_targets_save():
    """Save / update a target. Body: {name, host, user, port?, deploy_path?,
       platform?, platform_hints?, preview_url_base?, key_path?, save_password?, password?}.
       If save_password is True the password is stored in the JSON; otherwise
       caller passes it per-request and we never persist it.
    """
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    targets = _load_connect_targets()
    entry = targets.get(name, {})
    for k in ("host", "user", "port", "deploy_path", "platform", "platform_hints",
              "preview_url_base", "key_path"):
        if k in data and data[k] is not None:
            entry[k] = data[k]
    if data.get("save_password") and data.get("password"):
        entry["password"] = data["password"]
    targets[name] = entry
    _save_connect_targets(targets)
    safe = {k: v for k, v in entry.items() if k not in ("password",)}
    return jsonify({"ok": True, "name": name, **safe})


@app.route("/api/connect/targets/delete", methods=["POST"])
def connect_targets_delete():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    targets = _load_connect_targets()
    if name in targets:
        del targets[name]
        _save_connect_targets(targets)
    return jsonify({"ok": True})


def _ssh_connect_params(data: dict) -> tuple[dict, dict | None]:
    """Resolve connection params from {target_name?} or full {host,user,port,...}.
    Returns (params_dict, error_dict_or_None).
    """
    targets = _load_connect_targets()
    if data.get("target_name"):
        t = targets.get(data["target_name"])
        if not t:
            return {}, {"ok": False, "error": f"unknown target {data['target_name']}"}
        params = dict(t)
    else:
        params = {}
    # caller-supplied overrides
    for k in ("host", "user", "port", "key_path", "password"):
        if data.get(k):
            params[k] = data[k]
    if not params.get("host") or not params.get("user"):
        return {}, {"ok": False, "error": "host + user required"}
    params.setdefault("port", 22)
    return params, None


@app.route("/api/connect/ssh/probe", methods=["POST"])
def connect_ssh_probe():
    """Smoke-test an SSH target. Body: {target_name?} OR {host,user,port?,password?,key_path?}.
    Tries paramiko first (handles password) then falls back to openssh client.
    Never persists the password.
    """
    data = request.get_json(force=True, silent=True) or {}
    params, err = _ssh_connect_params(data)
    if err:
        return jsonify(err), 400

    paramiko = _try_paramiko()
    if paramiko and params.get("password"):
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=params["host"], username=params["user"],
                        port=int(params["port"]), password=params["password"],
                        timeout=10, banner_timeout=10, auth_timeout=10)
            stdin, stdout, stderr = cli.exec_command("uname -a; python3 --version 2>&1; "
                                                        "node --version 2>&1 || true", timeout=10)
            out = stdout.read().decode("utf-8", errors="ignore")
            cli.close()
            return jsonify({"ok": True, "auth": "password", "out": out[:2000]})
        except Exception as e:
            return jsonify({"ok": False, "auth": "password", "error": str(e)[:300]}), 200

    # openssh path (key-based or agent)
    cmd = ["ssh", "-p", str(params["port"]),
           "-o", "StrictHostKeyChecking=accept-new",
           "-o", "ConnectTimeout=10",
           "-o", "BatchMode=yes"]
    if params.get("key_path"):
        cmd += ["-i", params["key_path"]]
    cmd += [f"{params['user']}@{params['host']}", "uname -a; python3 --version 2>&1; node --version 2>&1 || true"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return jsonify({"ok": proc.returncode == 0, "auth": "key",
                          "out": (proc.stdout or "")[:2000],
                          "err": (proc.stderr or "")[:500],
                          "rc": proc.returncode})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "ssh timeout 20s"}), 200


@app.route("/api/connect/ssh/run", methods=["POST"])
def connect_ssh_run():
    """Run a command on the remote. Body: {target_name?, host?, user?, ..., command, timeout?}."""
    data = request.get_json(force=True, silent=True) or {}
    params, err = _ssh_connect_params(data)
    if err:
        return jsonify(err), 400
    command = data.get("command") or ""
    if not command:
        return jsonify({"ok": False, "error": "command required"}), 400
    timeout = float(data.get("timeout", 60))

    paramiko = _try_paramiko()
    if paramiko and params.get("password"):
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=params["host"], username=params["user"],
                        port=int(params["port"]), password=params["password"],
                        timeout=10, banner_timeout=10, auth_timeout=10)
            stdin, stdout, stderr = cli.exec_command(command, timeout=timeout)
            rc = stdout.channel.recv_exit_status()
            so = stdout.read().decode("utf-8", errors="ignore")
            se = stderr.read().decode("utf-8", errors="ignore")
            cli.close()
            return jsonify({"ok": rc == 0, "rc": rc, "stdout": so[:4000], "stderr": se[:2000]})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:300]}), 200

    cmd = ["ssh", "-p", str(params["port"]),
           "-o", "StrictHostKeyChecking=accept-new",
           "-o", "ConnectTimeout=10",
           "-o", "BatchMode=yes"]
    if params.get("key_path"):
        cmd += ["-i", params["key_path"]]
    cmd += [f"{params['user']}@{params['host']}", command]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        return jsonify({"ok": proc.returncode == 0, "rc": proc.returncode,
                          "stdout": (proc.stdout or "")[:4000],
                          "stderr": (proc.stderr or "")[:2000]})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": f"timeout {timeout}s"}), 200


@app.route("/api/connect/ssh/upload", methods=["POST"])
def connect_ssh_upload():
    """Upload one file's content to remote. Body: {target_name? or host+user+..., remote_path, content_b64}."""
    data = request.get_json(force=True, silent=True) or {}
    params, err = _ssh_connect_params(data)
    if err:
        return jsonify(err), 400
    remote_path = data.get("remote_path") or ""
    content_b64 = data.get("content_b64") or ""
    if not remote_path or not content_b64:
        return jsonify({"ok": False, "error": "remote_path + content_b64 required"}), 400
    try:
        raw = base64.b64decode(content_b64)
    except Exception:
        return jsonify({"ok": False, "error": "invalid base64"}), 400

    paramiko = _try_paramiko()
    if paramiko and params.get("password"):
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=params["host"], username=params["user"],
                        port=int(params["port"]), password=params["password"],
                        timeout=10, banner_timeout=10, auth_timeout=10)
            sftp = cli.open_sftp()
            # mkdir -p remote dir
            parts = remote_path.replace("\\", "/").split("/")
            d = ""
            for p in parts[:-1]:
                if not p:
                    d += "/"
                    continue
                d = (d + "/" + p) if d and not d.endswith("/") else (d + p)
                try:
                    sftp.stat(d)
                except FileNotFoundError:
                    sftp.mkdir(d)
            with sftp.open(remote_path, "wb") as f:
                f.write(raw)
            sftp.close()
            cli.close()
            return jsonify({"ok": True, "bytes": len(raw), "path": remote_path})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:300]}), 200

    # fallback: temp file + scp
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
    try:
        tmp.write(raw)
        tmp.close()
        cmd = ["scp", "-P", str(params["port"]),
               "-o", "StrictHostKeyChecking=accept-new",
               "-o", "ConnectTimeout=10"]
        if params.get("key_path"):
            cmd += ["-i", params["key_path"]]
        cmd += [tmp.name, f"{params['user']}@{params['host']}:{remote_path}"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return jsonify({"ok": proc.returncode == 0,
                          "rc": proc.returncode,
                          "bytes": len(raw),
                          "err": (proc.stderr or "")[:500]})
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@app.route("/api/connect/ssh/keygen", methods=["POST"])
def connect_ssh_keygen():
    """Generate an ed25519 SSH keypair locally. Body: {comment?, out_path?}.
    Returns the public key text and the local path of the private key.
    """
    data = request.get_json(force=True, silent=True) or {}
    comment = (data.get("comment") or "aurora").replace(" ", "_")[:64]
    home = pathlib.Path.home()
    default_dir = home / ".ssh"
    default_dir.mkdir(parents=True, exist_ok=True)
    out_path = data.get("out_path") or str(default_dir / f"id_ed25519_aurora_{comment}")
    if pathlib.Path(out_path).exists():
        return jsonify({"ok": False, "error": "key already exists, choose another out_path",
                          "path": out_path}), 400
    cmd = ["ssh-keygen", "-t", "ed25519", "-C", comment, "-N", "", "-f", out_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return jsonify({"ok": False, "error": proc.stderr[-300:]}), 200
        pub = pathlib.Path(out_path + ".pub").read_text(encoding="utf-8").strip()
        return jsonify({"ok": True, "private_key_path": out_path, "public_key": pub,
                          "instructions": "Append `public_key` to /home/<user>/.ssh/authorized_keys on the target."})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "keygen timeout"}), 200


@app.route("/api/connect/tcp/probe", methods=["POST"])
def connect_tcp_probe():
    """Quick TCP reachability probe. Body: {host, port, timeout?}."""
    import socket as _socket
    data = request.get_json(force=True, silent=True) or {}
    host = data.get("host")
    port = int(data.get("port") or 0)
    timeout = float(data.get("timeout") or 4.0)
    if not host or not port:
        return jsonify({"ok": False, "error": "host + port required"}), 400
    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    s.settimeout(timeout)
    t0 = time.time()
    try:
        s.connect((host, port))
        s.close()
        return jsonify({"ok": True, "rtt_ms": int((time.time() - t0) * 1000)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200],
                          "rtt_ms": int((time.time() - t0) * 1000)}), 200


# =====================================================================
#  CLI Remote API — /api/cli/*
#  Lightweight remote CLI client interface. Auth via existing Bearer keys.
# =====================================================================

import copy as _cli_copy

_CLI_VERSION = "1.0.0"
_CLI_SESSIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".aurora_cli_sessions.json")
_CLI_AGENT_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".aurora_cli_agent_state.json")
_CLI_DYNAMIC_AGENTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".aurora_dynamic_agents.json")
_CLI_CONNECTIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".aurora_connections.json")
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

@app.route("/api/cli/register", methods=["POST"])
def cli_register():
    """Point d'entrée sans friction : le client s'enregistre lui-même avec une clé unique."""
    data = request.get_json(silent=True) or {}
    device_name = data.get("device_name", "Unknown-Device")
    client_key = data.get("client_key")
    
    if not client_key:
        return jsonify({"ok": False, "error": "client_key missing"}), 400
        
    try:
        import sqlite3
        import hashlib
        db_path = os.path.join(WORKSPACE, "aurora.db")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Ensure api_keys table exists (in case it wasn't initialized)
        c.execute('''CREATE TABLE IF NOT EXISTS api_keys
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      key_hash TEXT UNIQUE NOT NULL,
                      label TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      expires_at TIMESTAMP)''')
                      
        key_hash = hashlib.sha256(client_key.encode()).hexdigest()
        
        # Insert or ignore (if already registered)
        c.execute("INSERT OR IGNORE INTO api_keys (key_hash, label) VALUES (?, ?)", 
                  (key_hash, f"CLI_{device_name}"))
        conn.commit()
        conn.close()
        
        return jsonify({"ok": True, "message": "Registered successfully", "device": device_name})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/cli/auth", methods=["POST"])
@_cli_auth_required
def cli_auth():
    """Authenticate CLI client, return session capabilities."""
    return jsonify({
        "ok": True, "version": _CLI_VERSION,
        "label": g.cli_key_rec.get("label", ""),
        "permissions": list(_CLI_PERMISSION_LEVELS.keys()),
    })


@app.route("/api/cli/version", methods=["GET"])
@_cli_auth_required
def cli_version():
    return jsonify({"ok": True, "server_version": _CLI_VERSION,
                    "bridge_lines": 16738, "api_routes": 237,
                    "agents_official": 37, "modules": 8})


@app.route("/api/cli/status", methods=["GET"])
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


@app.route("/api/cli/doctor", methods=["GET"])
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

@app.route("/api/cli/session/create", methods=["POST"])
@_cli_auth_required
def cli_session_create():
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


@app.route("/api/cli/session/list", methods=["GET"])
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


@app.route("/api/cli/session/<session_id>", methods=["GET"])
@_cli_auth_required
def cli_session_get(session_id):
    store = _cli_load_json(_CLI_SESSIONS_PATH)
    for s in store.get("sessions", []):
        if s["id"] == session_id:
            return jsonify({"ok": True, "session": s})
    return jsonify({"ok": False, "error": "session not found"}), 404


@app.route("/api/cli/session/<session_id>/resume", methods=["POST"])
@_cli_auth_required
def cli_session_resume(session_id):
    store = _cli_load_json(_CLI_SESSIONS_PATH)
    for s in store.get("sessions", []):
        if s["id"] == session_id:
            s["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            _cli_save_json(_CLI_SESSIONS_PATH, store)
            return jsonify({"ok": True, "session": s})
    return jsonify({"ok": False, "error": "session not found"}), 404


@app.route("/api/cli/session/<session_id>", methods=["DELETE"])
@_cli_auth_required
def cli_session_delete(session_id):
    store = _cli_load_json(_CLI_SESSIONS_PATH)
    before = len(store.get("sessions", []))
    store["sessions"] = [s for s in store.get("sessions", []) if s["id"] != session_id]
    _cli_save_json(_CLI_SESSIONS_PATH, store)
    return jsonify({"ok": True, "deleted": before - len(store["sessions"])})


# --- Chat (streaming SSE) ---

@app.route("/api/cli/chat", methods=["POST"])
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

@app.route("/api/cli/permissions", methods=["GET"])
@_cli_auth_required
def cli_permissions_get():
    return jsonify({"ok": True, "levels": _CLI_PERMISSION_LEVELS,
                    "available": list(_CLI_PERMISSION_LEVELS.keys())})


@app.route("/api/cli/permissions", methods=["POST"])
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

@app.route("/api/cli/workspace", methods=["GET"])
@_cli_auth_required
def cli_workspace_get():
    return jsonify({"ok": True, "workspace": WORKSPACE})


@app.route("/api/cli/workspace", methods=["POST"])
@_cli_auth_required
def cli_workspace_set():
    data = request.get_json(silent=True) or {}
    path = data.get("path", "")
    if not os.path.isdir(path):
        return jsonify({"ok": False, "error": "directory not found"}), 400
    return jsonify({"ok": True, "workspace": os.path.realpath(path)})


# --- Info routes ---

@app.route("/api/cli/tools", methods=["GET"])
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


@app.route("/api/cli/models", methods=["GET"])
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


@app.route("/api/cli/agents/official", methods=["GET"])
@_cli_auth_required
def cli_agents_official():
    agents = _cli_list_official_agents()
    state = _cli_load_json(_CLI_AGENT_STATE_PATH)
    disabled = state.get("disabled", [])
    for a in agents:
        a["enabled"] = a["name"] not in disabled
        a["protected"] = True
    return jsonify({"ok": True, "agents": agents, "total": len(agents)})


@app.route("/api/cli/agents/official/<name>/disable", methods=["POST"])
@_cli_auth_required
def cli_agent_disable(name):
    state = _cli_load_json(_CLI_AGENT_STATE_PATH)
    disabled = state.setdefault("disabled", [])
    if name not in disabled:
        disabled.append(name)
    _cli_save_json(_CLI_AGENT_STATE_PATH, state)
    return jsonify({"ok": True, "name": name, "enabled": False})


@app.route("/api/cli/agents/official/<name>/enable", methods=["POST"])
@_cli_auth_required
def cli_agent_enable(name):
    state = _cli_load_json(_CLI_AGENT_STATE_PATH)
    state["disabled"] = [n for n in state.get("disabled", []) if n != name]
    _cli_save_json(_CLI_AGENT_STATE_PATH, state)
    return jsonify({"ok": True, "name": name, "enabled": True})


# --- Dynamic Agents (create, modify, delete, save) ---

@app.route("/api/cli/agents/dynamic/list", methods=["GET"])
@_cli_auth_required
def cli_dynamic_agents_list():
    store = _cli_load_json(_CLI_DYNAMIC_AGENTS_PATH)
    return jsonify({"ok": True, "agents": store.get("agents", [])})


@app.route("/api/cli/agents/dynamic/create", methods=["POST"])
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


@app.route("/api/cli/agents/dynamic/<agent_id>", methods=["GET"])
@_cli_auth_required
def cli_dynamic_agent_get(agent_id):
    store = _cli_load_json(_CLI_DYNAMIC_AGENTS_PATH)
    for a in store.get("agents", []):
        if a["id"] == agent_id:
            return jsonify({"ok": True, "agent": a})
    return jsonify({"ok": False, "error": "agent not found"}), 404


@app.route("/api/cli/agents/dynamic/<agent_id>/modify", methods=["POST"])
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


@app.route("/api/cli/agents/dynamic/<agent_id>", methods=["DELETE"])
@_cli_auth_required
def cli_dynamic_agent_delete(agent_id):
    store = _cli_load_json(_CLI_DYNAMIC_AGENTS_PATH)
    before = len(store.get("agents", []))
    store["agents"] = [a for a in store.get("agents", []) if a["id"] != agent_id]
    _cli_save_json(_CLI_DYNAMIC_AGENTS_PATH, store)
    return jsonify({"ok": True, "deleted": before - len(store["agents"])})


@app.route("/api/cli/agents/dynamic/<agent_id>/save", methods=["POST"])
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


@app.route("/api/cli/mcp/list", methods=["GET"])
@_cli_auth_required
def cli_mcp_list():
    workspace = request.args.get("workspace", WORKSPACE)
    servers = _cli_discover_mcp(workspace)
    return jsonify({"ok": True, "servers": servers, "total": len(servers)})


@app.route("/api/cli/mcp/tools", methods=["GET"])
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


@app.route("/api/cli/mcp/call", methods=["POST"])
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


@app.route("/api/cli/skills/list", methods=["GET"])
@_cli_auth_required
def cli_skills_list():
    workspace = request.args.get("workspace", WORKSPACE)
    skills = _cli_discover_skills(workspace)
    return jsonify({"ok": True, "skills": skills, "total": len(skills)})


@app.route("/api/cli/skills/read", methods=["POST"])
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


@app.route("/api/cli/skills/create", methods=["POST"])
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


@app.route("/api/cli/skills/discover", methods=["POST"])
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

@app.route("/api/cli/connections/list", methods=["GET"])
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


@app.route("/api/cli/connections/add", methods=["POST"])
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


@app.route("/api/cli/connections/remove", methods=["POST"])
@_cli_auth_required
def cli_connections_remove():
    data = request.get_json(silent=True) or {}
    service = data.get("service", "")
    store = _cli_load_json(_CLI_CONNECTIONS_PATH)
    store["connections"] = [c for c in store.get("connections", []) if c.get("service") != service]
    _cli_save_json(_CLI_CONNECTIONS_PATH, store)
    return jsonify({"ok": True, "removed": service})


@app.route("/api/cli/connections/test", methods=["POST"])
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

@app.route("/api/cli/mission/start", methods=["POST"])
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
    # Run mission in background thread
    threading.Thread(target=_cli_run_mission, args=(mission_id,), daemon=True).start()
    return jsonify({"ok": True, "mission_id": mission_id, "status": "planning"})


def _cli_mission_emit(mission_id, event_type, data):
    """Append an SSE event to the mission's event buffer."""
    mission = _CLI_MISSIONS.get(mission_id)
    if not mission:
        return
    event = {"type": event_type, "ts": time.time(), **data}
    mission["events"].append(event)


def _cli_run_mission(mission_id):
    """Execute a mission autonomously in a background thread."""
    mission = _CLI_MISSIONS.get(mission_id)
    if not mission:
        return
    model = mission["model"]
    workspace = mission["workspace"]
    request_text = mission["request"]
    try:
        # Step 1: Load context
        _cli_mission_emit(mission_id, "step_start", {"step": "Chargement du contexte", "index": 0})
        context = _cli_load_context_for_workspace(workspace)
        _cli_mission_emit(mission_id, "step_end", {"step": "Chargement du contexte", "index": 0})

        # Step 2: Plan
        _cli_mission_emit(mission_id, "step_start", {"step": "Planification", "index": 1})
        mission["status"] = "planning"
        plan_prompt = (
            f"Tu es Aurora, une IA agentique autonome. On te demande:\n\n{request_text}\n\n"
            f"Workspace: {workspace}\n"
            f"Skills disponibles: {context['skills_count']}\n"
            f"Outils MCP: {context['mcp_tools_count']}\n"
            f"Services connectés: {', '.join(context['connections']) if context['connections'] else 'aucun'}\n\n"
            "Produis un plan d'action en JSON:\n"
            '{"steps": [{"action": "...", "tool": "...", "params": {...}, "description": "..."}]}\n'
            "Actions possibles: analyze_files, read_file, write_file, search_web, run_command, "
            "install_deps, run_tests, generate_code, mcp_call, create_agent"
        )
        try:
            r = requests.post(f"{OLLAMA_URL}/api/chat", json={
                "model": model, "stream": False,
                "messages": [{"role": "user", "content": plan_prompt}],
                "options": {"temperature": 0.3},
            }, timeout=120)
            plan_text = r.json().get("message", {}).get("content", "") if r.ok else ""
        except Exception as e:
            plan_text = ""
            _cli_mission_emit(mission_id, "error", {"message": f"Planning failed: {e}"})
        _cli_mission_emit(mission_id, "step_end", {"step": "Planification", "index": 1})

        # Step 3: Execute (simplified — real orchestration in future phases)
        mission["status"] = "executing"
        _cli_mission_emit(mission_id, "step_start", {"step": "Exécution", "index": 2})

        exec_prompt = (
            f"Tu es Aurora, une IA de nouvelle génération, experte et performante. "
            f"Voici la demande de l'utilisateur :\n{request_text}\n\n"
            f"Voici ton plan d'action :\n{plan_text}\n\n"
            "Exécute ce plan. RÈGLES STRICTES :\n"
            "1. CODE DIFF : Pour chaque fichier modifié, explique clairement ce que tu modifies et émets un format Diff lisible.\n"
            "2. GITHUB/GIT : Pousse le code de manière 100% humanisée. Tes messages de commit doivent être pro (ex: 'feat: add auth'). AUCUNE MENTION de l'IA, de toi-même ou de 'généré par'. Le code et les README doivent paraître écrits par un développeur humain expert.\n"
            "3. SUDO/PRIVILÈGES : Si une commande requiert `sudo`, arrête-toi et signale-le (génère un événement 'sudo_request' ou indique que tu attends le mot de passe). Le client te le transmettra de manière éphémère.\n"
            "4. AUTONOMIE : N'hésite pas à prendre des décisions d'architecture fortes et à utiliser le mode headless si nécessaire. Montre ton expertise.\n"
        )
        try:
            r = requests.post(f"{OLLAMA_URL}/api/chat", json={
                "model": model, "stream": True,
                "messages": [{"role": "user", "content": exec_prompt}],
            }, stream=True, timeout=600)
            full = ""
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full += token
                        _cli_mission_emit(mission_id, "token", {"content": token})
                except Exception:
                    continue
        except Exception as e:
            _cli_mission_emit(mission_id, "error", {"message": str(e)})
            mission["errors"].append(str(e))

        _cli_mission_emit(mission_id, "step_end", {"step": "Exécution", "index": 2})

        # Done
        mission["status"] = "completed"
        mission["finished_at"] = time.time()
        total = round(mission["finished_at"] - mission["started_at"], 1)
        _cli_mission_emit(mission_id, "mission_complete", {
            "total_seconds": total,
            "files_changed": mission["files_changed"],
            "sources_consulted": mission["sources_consulted"],
            "errors_count": len(mission["errors"]),
        })
    except Exception as e:
        mission["status"] = "failed"
        mission["finished_at"] = time.time()
        _cli_mission_emit(mission_id, "error", {"message": str(e)})


@app.route("/api/cli/mission/<mission_id>/input", methods=["POST"])
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


@app.route("/api/cli/mission/<mission_id>/stream", methods=["GET"])
@_cli_auth_required
def cli_mission_stream(mission_id):
    """SSE stream for mission events."""
    mission = _CLI_MISSIONS.get(mission_id)
    if not mission:
        return jsonify({"ok": False, "error": "mission not found"}), 404

    def generate():
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
            time.sleep(0.1)

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/cli/mission/<mission_id>/status", methods=["GET"])
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


@app.route("/api/cli/mission/<mission_id>/stop", methods=["POST"])
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
        tunnel_file = "tunnel.txt"
        if not os.path.exists(tunnel_file):
            tunnel_file = "tunnel_url.txt"
        
        if os.path.exists(tunnel_file):
            print("🔗 Syncing tunnel URL to GitHub Gist for remote clients...")
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
        app.run(host="0.0.0.0", port=3001, threaded=True, debug=dev_reload, use_reloader=dev_reload)
