from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from urllib.parse import urlencode
import tempfile
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

voice_bp = Blueprint('voice_bp', __name__)

# =====================================================================
#  Voice — STT & TTS
# =====================================================================

@voice_bp.route("/api/voice/stt", methods=["POST"])
def voice_stt():
    try:
        audio_file = request.files["audio"]
        os.makedirs(os.path.join(WORKSPACE, "temp"), exist_ok=True)
        # Conserver l'extension réelle (wav depuis le JS, webm depuis anciens clients)
        ext = os.path.splitext(audio_file.filename or "voice.webm")[1] or ".webm"
        script = os.path.join(WORKSPACE, "python-services", "voice_service.py")
        with tempfile.TemporaryDirectory(prefix="voice-stt-", dir=os.path.join(WORKSPACE, "temp")) as folder:
            temp_path = os.path.join(folder, f"audio{ext}")
            audio_file.save(temp_path)
            raw = subprocess.check_output(
                [sys.executable, script, "--mode", "stt", "--audio", temp_path],
                stderr=subprocess.STDOUT, timeout=120, cwd=WORKSPACE,
            ).decode("utf-8")

        lines = [l for l in raw.strip().split("\n") if l.strip()]
        return Response(lines[-1], mimetype="application/json")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@voice_bp.route("/api/voice/tts", methods=["POST"])
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

        phonetic_meta = {}
        tts_text = text
        try:
            _py_svc = os.path.join(WORKSPACE, "python-services")
            if _py_svc not in sys.path:
                sys.path.insert(0, _py_svc)
            from voice_cloning_service import normalize_french_phonetics
            if str(lang).lower().startswith("fr"):
                phonetic_meta = normalize_french_phonetics(text) or {}
                tts_text = phonetic_meta.get("normalized_text") or text
        except Exception:
            phonetic_meta = {}

        # Un fichier PAR SYNTHESE, sous un projet. L ancienne version ecrivait
        # toujours `output/voix/tts_out.wav` : a la racine du module — hors
        # contrat — et surtout, chaque synthese EFFACAIT la precedente. Rien
        # n en gardait trace.
        voice_dir = sortie_module("voix", data.get("projet") or "synthese")
        output_path = os.path.join(voice_dir, f"tts_{int(time.time() * 1000)}_{uuid.uuid4().hex}.wav")
        script = os.path.join(WORKSPACE, "python-services", "voice_service.py")

        cmd = [sys.executable, script, "--mode", "tts", "--text", tts_text, "--output", output_path, "--lang", lang]
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
            "audio_url": "/api/voice/tts-audio?" + urlencode({
                "file": pathlib.Path(output_path).relative_to(pathlib.Path(WORKSPACE)/"output/voix").as_posix(),
            }),
            "phonemes": phonemes,
            "phonetic_normalization": phonetic_meta,
            "engine": engine,
            "voice": voice_name,
        }
        # Expose le MP4 talking-video via une route dediee (meme mecanique que tts-audio)
        if talking_video_path and os.path.isfile(talking_video_path):
            # Snapshot par synthese, comme le WAV, meme si le moteur renvoie un cache.
            video_path = pathlib.Path(output_path).with_suffix('.mp4')
            if pathlib.Path(talking_video_path).resolve() != video_path.resolve():
                shutil.copyfile(talking_video_path, video_path)
            current_app.config["_last_talking_video_path"] = str(video_path)
            response["video_url"] = "/api/voice/tts-video?" + urlencode({
                "file": video_path.relative_to(pathlib.Path(WORKSPACE)/"output/voix").as_posix(),
            })
            response["video_cached"] = talking_video_cached

        return jsonify(response)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "TTS timeout"}), 504
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@voice_bp.route("/api/voice/tts-audio")
def serve_tts_audio():
    """Sert le dernier fichier WAV TTS genere — universel Tauri/browser/tunnel."""
    # Les synthese sont horodatees et rangees par projet : on sert la PLUS
    # RECENTE au lieu d un nom fige. L ancienne version lisait `tts_out.wav`,
    # ce qui n avait de sens que tant qu une synthese ecrasait la precedente.
    racine_voix = os.path.join(WORKSPACE, "output", "voix")
    if "file" in request.args:
        root = pathlib.Path(racine_voix).resolve()
        raw = request.args.get("file", "")
        try:
            path = (root/raw).resolve()
            if (not raw or "\\" in raw or "\x00" in raw or not path.is_relative_to(root)
                    or path.suffix.lower() != ".wav" or not path.is_file()):
                return jsonify({"error": "Fichier audio TTS introuvable"}), 404
        except (OSError, ValueError, RuntimeError):
            return jsonify({"error": "Fichier audio TTS introuvable"}), 404
        return send_file(path, mimetype="audio/wav", conditional=True)
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


@voice_bp.route("/api/voice/tts-video")
def serve_tts_video():
    """Sert le dernier MP4 talking-video (SadTalker) genere en parallele du TTS."""
    if "file" in request.args:
        root = pathlib.Path(WORKSPACE, "output", "voix").resolve()
        raw = request.args.get("file", "")
        try:
            path = (root/raw).resolve()
            if (not raw or "\\" in raw or "\x00" in raw or not path.is_relative_to(root)
                    or path.suffix.lower() != ".mp4" or not path.is_file()):
                return jsonify({"error": "MP4 talking-video introuvable"}), 404
        except (OSError, ValueError, RuntimeError):
            return jsonify({"error": "MP4 talking-video introuvable"}), 404
        return send_file(path, mimetype="video/mp4", conditional=True)
    video_path = current_app.config.get("_last_talking_video_path")
    if not video_path or not os.path.isfile(video_path):
        return jsonify({"error": "Aucun MP4 talking-video disponible"}), 404
    return send_file(video_path, mimetype="video/mp4", conditional=True)


@voice_bp.route("/api/voice/talking-head/check", methods=["GET"])
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


@voice_bp.route("/api/voice/talking-head/idle", methods=["POST"])
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
                        current_app.config["_last_idle_video_path"] = out_path
                        return jsonify({"ok": True, "video_url": "/api/voice/idle-video", "cached": result.get("cached", False)})
                    return jsonify({"ok": False, "error": result.get("error", "idle failed")}), 500
                except json.JSONDecodeError:
                    continue
        return jsonify({"ok": False, "error": "no json output"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@voice_bp.route("/api/voice/idle-video")
def serve_idle_video():
    """Sert le dernier MP4 idle genere."""
    p = current_app.config.get("_last_idle_video_path")
    if not p or not os.path.isfile(p):
        return jsonify({"error": "Aucun MP4 idle disponible"}), 404
    return send_file(p, mimetype="video/mp4", conditional=True)


# v82jc : proxy server-side pour fetch ICS Pronote/ÉcoleDirecte/etc
#   Le navigateur bloque les fetch cross-origin → le bridge proxie.
@voice_bp.route("/api/calendar/fetch-ics", methods=["POST"])
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


@voice_bp.route("/api/ent/harvest", methods=["POST"])
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


@voice_bp.route("/api/ent/list", methods=["GET"])
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


@voice_bp.route("/api/ent/get", methods=["GET"])
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


@voice_bp.route("/api/ent/native/run", methods=["POST"])
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


@voice_bp.route("/api/ent/discover-school", methods=["POST"])
@voice_bp.route("/api/ent/discover-pronote", methods=["POST"])
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


@voice_bp.route("/api/ent/analyze-dom", methods=["POST"])
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
            from agi_core.flagship_council import resolve_installed_flagship_model
            picked = resolve_installed_flagship_model(None, module="voice")
            if not picked:
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
                "options": {"temperature": 0.2, "num_ctx": 32768, "num_predict": 8192},
            }, timeout=300)
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


@voice_bp.route("/api/voice/stt-info")
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


@voice_bp.route("/api/voice/personas")
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
#  Routes v3 Premiers Principes : Clonage Zero-Shot, 4-Stems, Oracle Formel & 3D
# =====================================================================

@voice_bp.route("/api/voice/clone-profile", methods=["POST"])
def voice_clone_profile_v3():
    """Extrait le profil acoustique Zero-Shot (F0, formants F1-F3, jitter, shimmer, HNR)
    et synthétise optionnellement une parole clonée avec prosodie et visèmes Rhubarb."""
    try:
        _py_svc = os.path.join(WORKSPACE, "python-services")
        if _py_svc not in sys.path:
            sys.path.insert(0, _py_svc)
        from voice_cloning_service import (
            extract_speaker_acoustic_profile,
            synthesize_cloned_speech,
            normalize_french_phonetics,
            extract_rhubarb_visemes,
        )
        data = request.get_json(silent=True) or {}
        ref_path = data.get("reference_audio") or data.get("audio_path") or ""
        text = (data.get("text") or "").strip()
        profile = extract_speaker_acoustic_profile(ref_path if ref_path and os.path.isfile(ref_path) else None)
        out = {"ok": True, "acoustic_profile": profile}
        if text:
            voice_dir = sortie_module("voix", data.get("projet") or "clonage_v3")
            out_wav = os.path.join(voice_dir, f"clone_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.wav")
            synth = synthesize_cloned_speech(text, profile, output_wav=out_wav)
            visemes = extract_rhubarb_visemes(out_wav, text=text)
            out["synthesis"] = synth
            out["phonetics_fr"] = normalize_french_phonetics(text)
            out["visemes"] = visemes
        return jsonify(out)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@voice_bp.route("/api/voice/music-stems", methods=["POST"])
def voice_music_stems_v3():
    """Synthétise une production musicale 4-Stems (drums, bass, harmony, lead) masterisée à -14 LUFS."""
    try:
        _py_svc = os.path.join(WORKSPACE, "python-services")
        if _py_svc not in sys.path:
            sys.path.insert(0, _py_svc)
        from voice_cloning_service import generate_music_stems
        data = request.get_json(silent=True) or {}
        bpm = float(data.get("bpm", 120.0))
        key_note = str(data.get("key", "A"))
        mode = str(data.get("scale", data.get("mode", "minor")))
        duration_s = float(data.get("duration_sec", 4.0))
        voice_dir = sortie_module("voix", data.get("projet") or "musique_stems_v3")
        res = generate_music_stems(
            output_dir=voice_dir,
            bpm=bpm,
            root_note=key_note,
            scale=mode,
            duration_sec=min(30.0, max(1.0, duration_s)),
        )
        return jsonify({"ok": True, **res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@voice_bp.route("/api/learning/formal-oracle", methods=["POST"])
def learning_formal_oracle_v3():
    """Oracle formel SymPy + Z3 v3 : anneau polynomial Q[x_1..x_n], SOS, diagnostic d'erreur,
    mise à jour bayésienne FQ-Ada-BKT et génération d'exercices isomorphes."""
    try:
        _py_svc = os.path.join(WORKSPACE, "python-services")
        if _py_svc not in sys.path:
            sys.path.insert(0, _py_svc)
        import scientific_oracle as so
        data = request.get_json(silent=True) or {}
        action = str(data.get("action") or "full").lower()
        out = {"ok": True, "action": action}
        if action in {"prove", "full"} and data.get("lhs") and data.get("rhs"):
            out["polynomial_proof"] = so.prove_polynomial_identity_sos(str(data["lhs"]), str(data["rhs"]))
        if action in {"diagnose", "full"} and data.get("expected") and data.get("student_answer"):
            out["diagnosis"] = so.diagnose_student_misconception(str(data["expected"]), str(data["student_answer"]))
        if action in {"bkt", "full"} and "p_mastery" in data:
            out["bkt"] = so.update_bkt_mastery(
                float(data.get("p_mastery", 0.5)),
                correct=bool(data.get("correct", True)),
                difficulty=int(data.get("difficulty", 3)),
                response_time_sec=float(data.get("response_time_sec", 10.0)),
                hints_used=int(data.get("hints_used", 0)),
            )
        if action in {"exercise", "full"}:
            out["isomorphic_exercise"] = so.generate_isomorphic_exercise(
                topic=str(data.get("topic") or "quadratic"),
                p_mastery=float(data.get("p_mastery", 0.5)),
                seed=int(data.get("seed", int(time.time()) % 10000)),
            )
        return jsonify(out)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@voice_bp.route("/api/3d/universal-style", methods=["POST"])
def three_d_universal_style_v3():
    """Synthèse de profil optique PBR par premiers principes (Fresnel Schlick, GGX Anisotrope, SSS dipolaire, Cauchy)."""
    try:
        _py_svc = os.path.join(WORKSPACE, "python-services")
        if _py_svc not in sys.path:
            sys.path.insert(0, _py_svc)
        from universal_style_engine import synthesize_universal_style_profile
        data = request.get_json(silent=True) or {}
        prompt = str(data.get("prompt") or data.get("style") or "photoréaliste").strip()
        profile = synthesize_universal_style_profile(prompt)
        return jsonify({"ok": True, "profile": profile})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@voice_bp.route("/api/3d/semantic-animation", methods=["POST"])
def three_d_semantic_animation_v3():
    """Synthèse cinématique multi-morphologies (biped, quadruped, winged, serpentine, arachnid, mechanical) + Foot-Lock IK."""
    try:
        _py_svc = os.path.join(WORKSPACE, "python-services")
        if _py_svc not in sys.path:
            sys.path.insert(0, _py_svc)
        from semantic_animation import build_semantic_animation_clip
        data = request.get_json(silent=True) or {}
        prompt = str(data.get("prompt") or "marche fluide").strip()
        duration = float(data.get("duration", 2.5))
        fps = int(data.get("fps", 30))
        clip = build_semantic_animation_clip(prompt, duration=duration, fps=fps)
        return jsonify({"ok": True, "clip": clip})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@voice_bp.route("/api/3d/sketch-to-3d-cad", methods=["POST"])
def sketch_to_3d_cad_v3():
    """Passerelle universelle Croquis -> Reconnaissance topologique -> Plan SVG + 4-Vues Orthographiques + GLB/STL 3D étanche."""
    try:
        _py_svc = os.path.join(WORKSPACE, "python-services")
        if _py_svc not in sys.path:
            sys.path.insert(0, _py_svc)
        from sketch_to_3d_cad_bridge import convert_sketch_to_3d_and_image_blueprint
        data = request.get_json(silent=True) or {}
        sketch_input = data.get("sketch") or data.get("image_path") or data
        prompt_hint = str(data.get("prompt") or data.get("prompt_hint") or "").strip()
        scale_mm = float(data.get("scale_mm", 120.0))
        out_dir = sortie_module("3d", data.get("projet") or "sketch_to_3d_v3")
        report = convert_sketch_to_3d_and_image_blueprint(
            sketch_input=sketch_input,
            output_dir=out_dir,
            prompt_hint=prompt_hint,
            scale_mm=scale_mm,
        )
        return jsonify(report)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@voice_bp.route("/api/3d/architectural-project", methods=["POST"])
def three_d_architectural_project_v3():
    """Constructeur 3D d'architecture et d'ingénierie structurelle multi-pièces (Euler-Bernoulli, flambement d'Euler, von Mises, Manifold64)."""
    try:
        _py_svc = os.path.join(WORKSPACE, "python-services")
        if _py_svc not in sys.path:
            sys.path.insert(0, _py_svc)
        from architectural_engineering_builder import build_architectural_engineering_project
        data = request.get_json(silent=True) or {}
        prompt = str(data.get("prompt") or "Bâtiment architectural multi-étages").strip()
        spec = data.get("spec") if isinstance(data.get("spec"), dict) else {}
        out_dir = sortie_module("3d", data.get("projet") or "architecture_engineering_v3")
        report = build_architectural_engineering_project(prompt=prompt, output_dir=out_dir, spec=spec)
        return jsonify(report)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@voice_bp.route("/api/code/mega-project-architect", methods=["POST"])
def code_mega_project_architect_v3():
    """Architecte déterministe de méga-projets, OS complets et reproduction de design au pixel près sans hallucination."""
    try:
        _repo_root = os.path.dirname(WORKSPACE)
        if _repo_root not in sys.path:
            sys.path.insert(0, _repo_root)
        from agi_core.mega_project_architect import (
            build_mega_project_blueprint,
            verify_cross_file_symbol_and_contract_graph,
            compute_design_reproduction_fidelity,
        )
        data = request.get_json(silent=True) or {}
        prompt = str(data.get("prompt") or "Système d'exploitation complet WebOS").strip()
        domain_hint = str(data.get("domain_hint") or "auto").strip()
        out = build_mega_project_blueprint(prompt=prompt, domain_hint=domain_hint)
        if isinstance(data.get("files"), dict):
            out["cross_file_symbol_audit"] = verify_cross_file_symbol_and_contract_graph(data["files"])
        if isinstance(data.get("design_spec"), dict):
            out["design_fidelity_audit"] = compute_design_reproduction_fidelity(data["design_spec"])
        return jsonify(out)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@voice_bp.route("/api/agi/strategy-status", methods=["GET", "POST"])
def agi_strategy_status_v3():
    """Retourne la stratégie SOTA Modèles Renforcés + Triade de Sous-Agents + Oracles Zéro-Hallucination sur les 13 modules."""
    try:
        _repo_root = os.path.dirname(WORKSPACE)
        if _repo_root not in sys.path:
            sys.path.insert(0, _repo_root)
        from agi_core.model_strategy_engine import ModelAndSubAgentStrategyEngine
        engine = ModelAndSubAgentStrategyEngine(_repo_root)
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            return jsonify(
                engine.build_execution_strategy_plan(
                    request_text=str(data.get("prompt") or ""),
                    module=data.get("module"),
                )
            )
        return jsonify(engine.audit_all_modules_strategy_readiness())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@voice_bp.route("/api/training/colab-bridge/status", methods=["GET"])
def colab_bridge_status_v3():
    """Retourne l'état du pont bidirectionnel Google Colab A100 / L4 et la commande 1-ligne."""
    try:
        _repo_root = os.path.dirname(WORKSPACE)
        if _repo_root not in sys.path:
            sys.path.insert(0, _repo_root)
        from auto_rl.colab_live_bridge import get_colab_bridge_status
        return jsonify(get_colab_bridge_status())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@voice_bp.route("/api/training/colab-bridge/bootstrap.py", methods=["GET"])
def colab_bridge_bootstrap_script_v3():
    """Sert le script d'entraînement autonome exécutable en 1 ligne sur Google Colab A100 / L4."""
    from flask import Response
    _repo_root = os.path.dirname(WORKSPACE)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from auto_rl.colab_live_bridge import generate_colab_bootstrap_script
    script = generate_colab_bootstrap_script()
    return Response(script, mimetype="text/x-python")


@voice_bp.route("/api/training/colab-bridge/register", methods=["POST"])
def colab_bridge_register_v3():
    _repo_root = os.path.dirname(WORKSPACE)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from auto_rl.colab_live_bridge import register_colab_worker
    return jsonify(register_colab_worker(request.get_json(silent=True) or {}))


@voice_bp.route("/api/training/colab-bridge/claim-job", methods=["POST"])
def colab_bridge_claim_job_v3():
    _repo_root = os.path.dirname(WORKSPACE)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from auto_rl.colab_live_bridge import claim_next_colab_job
    return jsonify(claim_next_colab_job(request.get_json(silent=True) or {}))


@voice_bp.route("/api/training/colab-bridge/submit-weights", methods=["POST"])
def colab_bridge_submit_weights_v3():
    _repo_root = os.path.dirname(WORKSPACE)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from auto_rl.colab_live_bridge import receive_colab_trained_weights
    return jsonify(receive_colab_trained_weights(request.get_json(silent=True) or {}))


@voice_bp.route("/api/training/colab-bridge/enqueue-command", methods=["POST"])
def colab_bridge_enqueue_command_v3():
    _repo_root = os.path.dirname(WORKSPACE)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from auto_rl.colab_live_bridge import enqueue_remote_colab_command
    data = request.get_json(silent=True) or {}
    return jsonify(
        enqueue_remote_colab_command(
            python_code=str(data.get("python_code") or ""),
            description=str(data.get("description") or "Remote H100 command"),
        )
    )


@voice_bp.route("/api/training/colab-bridge/command-result", methods=["POST"])
def colab_bridge_command_result_v3():
    _repo_root = os.path.dirname(WORKSPACE)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from auto_rl.colab_live_bridge import receive_colab_command_result
    return jsonify(receive_colab_command_result(request.get_json(silent=True) or {}))


@voice_bp.route("/api/training/colab-bridge/progress", methods=["POST"])
def colab_bridge_progress_v3():
    _repo_root = os.path.dirname(WORKSPACE)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from auto_rl.colab_live_bridge import update_colab_live_progress
    return jsonify(update_colab_live_progress(request.get_json(silent=True) or {}))


@voice_bp.route("/api/training/colab-bridge/full-dataset/<module>.jsonl", methods=["GET"])
def colab_bridge_full_dataset_v3(module: str):
    """Sert 100 % des entrées du dataset multi-régimes du module sans aucune troncature."""
    from flask import Response
    _repo_root = os.path.dirname(WORKSPACE)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from auto_rl.colab_live_bridge import get_full_dataset_jsonl_text
    text = get_full_dataset_jsonl_text(module)
    return Response(text, mimetype="application/x-ndjson; charset=utf-8")


@voice_bp.route("/api/precision/nanometer-oracle", methods=["GET", "POST"])
def nanometer_precision_oracle_v1():
    """Oracle sub-nanométrique (1 nm), femtométrique (10^-15 m) et 100 décimales exactes (10^-100)."""
    _py_services = os.path.join(WORKSPACE, "python-services")
    if _py_services not in sys.path:
        sys.path.insert(0, _py_services)
    from nanometer_precision_oracle import (
        audit_and_refine_subnanometer_surface,
        compute_spectral_thin_film_pbr_1nm,
        solve_structural_mechanics_100dps,
    )
    data = request.get_json(silent=True) or {}
    return jsonify({
        "ok": True,
        "structural_100dps": solve_structural_mechanics_100dps(
            span_mm=str(data.get("span_mm") or "160.0"),
            beam_width_mm=str(data.get("beam_width_mm") or "6.5"),
            beam_height_mm=str(data.get("beam_height_mm") or "9.5"),
        ),
        "spectral_1nm": compute_spectral_thin_film_pbr_1nm(
            film_thickness_nm=float(data.get("film_thickness_nm") or 285.0),
            incidence_deg=float(data.get("incidence_deg") or 22.5),
        ),
        "subnanometer_surface": audit_and_refine_subnanometer_surface(
            radius_mm=float(data.get("radius_mm") or 50.0),
        ),
    })


@voice_bp.route("/api/precision/pixel-perfect-oracle", methods=["GET", "POST"])
def pixel_perfect_oracle_v1():
    """Oracle Pixel-Perfect (Alignement de phase sub-pixel 0.0004 px, MTF50, Zéro Halo, Pull-Push UV)."""
    _py_services = os.path.join(WORKSPACE, "python-services")
    if _py_services not in sys.path:
        sys.path.insert(0, _py_services)
    from pixel_perfect_optical_engine import generate_pixel_perfect_master_showcase
    return jsonify(generate_pixel_perfect_master_showcase())







