from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

cowork_ext_bp = Blueprint('cowork_ext_bp', __name__)

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


@cowork_ext_bp.route("/api/cowork/extension/poll", methods=["GET"])
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


@cowork_ext_bp.route("/api/cowork/extension/dispatch", methods=["POST"])
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


@cowork_ext_bp.route("/api/cowork/extension/result", methods=["POST"])
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


@cowork_ext_bp.route("/api/cowork/extension/await-result", methods=["GET"])
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


@cowork_ext_bp.route("/api/cowork/extension/inbound", methods=["POST"])
def cowork_ext_inbound():
    """Envoi d evenement de l extension vers Aurora (clic droit sur selection)."""
    body = request.get_json(silent=True) or {}
    body["at"] = _time.time()
    with _EXT_LOCK:
        _EXT_INBOUND.append(body)
        _ext_gc()
    return jsonify({"ok": True})


@cowork_ext_bp.route("/api/cowork/extension/inbound", methods=["GET"])
def cowork_ext_inbound_list():
    with _EXT_LOCK:
        return jsonify({"ok": True, "events": list(_EXT_INBOUND)})


@cowork_ext_bp.route("/api/cowork/extension/download", methods=["GET"])
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


@cowork_ext_bp.route("/api/cowork/extension/list", methods=["GET"])
def cowork_ext_list():
    """Liste les extensions actives (poll < 60s)."""
    with _EXT_LOCK:
        now = _time.time()
        # v26 — widen GC window from 60s to 120s : the extension polls every
        # ~30s but a brief network blip or self-watch reload can delay one
        # cycle ; 120s covers that without aggressive disconnect.
        active = [{"extId": k, "lastSeenAgoMs": int((now - t) * 1000)} for k, t in _EXT_LAST_SEEN.items() if now - t < 120]
    return jsonify({"ok": True, "extensions": active})


@cowork_ext_bp.route("/api/cowork/extension/status", methods=["GET"])
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


@cowork_ext_bp.route("/api/cowork/extension/version", methods=["GET"])
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


@cowork_ext_bp.route("/api/_dev/status", methods=["GET"])
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


@cowork_ext_bp.route("/api/_dev/reload", methods=["POST"])
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


@cowork_ext_bp.route("/api/warmup/status", methods=["GET"])
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


@cowork_ext_bp.route("/api/warmup/restart", methods=["POST"])
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


@cowork_ext_bp.route("/api/cowork/extension/install-md", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/explain", methods=["GET"])
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


@cowork_ext_bp.route("/api/warmup/health", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/clear", methods=["POST"])
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


@cowork_ext_bp.route("/api/picker/history/stats", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/kinds", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/distinct-models", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/by-model", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/by-reason", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/timeline", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/timeline/summary", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/by-model-and-reason", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/intersections", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/cells/empty", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/coverage", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/coverage/global", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/coverage/timeline", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/coverage/heatmap", methods=["GET"])
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


@cowork_ext_bp.route("/api/picker/history/replay", methods=["POST"])
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


@cowork_ext_bp.route("/api/cowork/extract-structured", methods=["POST"])
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


@cowork_ext_bp.route("/api/cowork/extraction-stats", methods=["GET"])
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

@cowork_ext_bp.route("/api/cowork/dual-signal-event", methods=["POST"])
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


@cowork_ext_bp.route("/api/cowork/dual-signal-stats", methods=["GET"])
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


@cowork_ext_bp.route("/api/cowork/dual-signal-effective", methods=["GET"])
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

@cowork_ext_bp.route("/api/cowork/dual-signal-reset", methods=["POST"])
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

@cowork_ext_bp.route("/api/cowork/trend-signal-reset", methods=["POST"])
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

@cowork_ext_bp.route("/api/cowork/trend-signal-event", methods=["POST"])
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


@cowork_ext_bp.route("/api/cowork/trend-signal-stats", methods=["GET"])
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

@cowork_ext_bp.route("/api/cowork/browsers/detect", methods=["GET"])
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


@cowork_ext_bp.route("/api/cowork/mobile/inbound", methods=["POST"])
def cowork_mobile_inbound():
    """Le tel envoie un evt a Aurora (par ex resultat d une action SMS)."""
    body = request.get_json(silent=True) or {}
    body["at"] = _time.time()
    with _MOBILE_LOCK:
        _MOBILE_INBOUND.append(body)
        if len(_MOBILE_INBOUND) > 200:
            del _MOBILE_INBOUND[:-200]
    return jsonify({"ok": True})


@cowork_ext_bp.route("/api/cowork/mobile/events", methods=["GET"])
def cowork_mobile_events():
    """Aurora liste les evts entrants du tel."""
    with _MOBILE_LOCK:
        return jsonify({"ok": True, "events": list(_MOBILE_INBOUND)})


@cowork_ext_bp.route("/api/cowork/mobile/dispatch", methods=["POST"])
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


@cowork_ext_bp.route("/api/cowork/mobile/poll", methods=["GET"])
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


@cowork_ext_bp.route("/api/cowork/mobile/result", methods=["POST"])
def cowork_mobile_result():
    """Le tel renvoie le resultat de la commande qu il a executee."""
    body = request.get_json(silent=True) or {}
    cmd_id = (body.get("commandId") or "").strip()
    if not cmd_id:
        return jsonify({"ok": False, "error": "commandId manquant"}), 400
    with _MOBILE_LOCK:
        _MOBILE_RESULTS[cmd_id] = body.get("result")
    return jsonify({"ok": True})



# --- Refactored to application/routes/postgres_bp_routes.py ---

# --- Refactored to application/routes/s3_bp_routes.py ---

# --- Refactored to application/routes/iot_bp_routes.py ---

# --- Refactored to application/routes/vite_bp_routes.py ---

# --- Refactored to application/routes/connect_bp_routes.py ---
