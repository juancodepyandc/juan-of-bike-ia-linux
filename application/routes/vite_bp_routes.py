from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
import threading as _threading
import time as _time
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL, _admin_ok

vite_bp = Blueprint('vite_bp', __name__)

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
@vite_bp.route("/api/admin/status", methods=["GET"])
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
        # iter32 SEC (D.12): le fichier à relancer est TOUJOURS bridge_server.py
        # à la racine du dossier application. Avant, Path(__file__) pointait
        # vers routes/vite_bp_routes.py → le restart relançait le module de
        # routes (sans Flast broche réelle) au lieu du process écoutant 3001.
        _application_dir = pathlib.Path(WORKSPACE).resolve()
        bridge_path = (_application_dir / "bridge_server.py").resolve()
        if not bridge_path.exists():
            raise FileNotFoundError(f"bridge introuvable: {bridge_path}")
        cwd = str(_application_dir)
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


@vite_bp.route("/api/admin/restart-bridge", methods=["POST", "GET"])
def admin_restart_bridge():
    if not _admin_ok():
        return jsonify({"error": "admin_refuse_tunnel", "détail": "local ou token admin requis"}), 403
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
@vite_bp.route("/api/3d/motion-compile", methods=["POST"])
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


@vite_bp.route("/api/3d/motion-resolve-prompt", methods=["POST"])
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


@vite_bp.route("/api/3d/motion-parser-self-test", methods=["GET"])
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


@vite_bp.route("/api/3d/motion-self-test", methods=["GET"])
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


@vite_bp.route("/api/3d/regression-suite", methods=["POST"])
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
    os.path.dirname(os.path.abspath(__file__)), "..", "..", ".claude", "agents",
)
_AGENT_DOCS = {"README.md", "EXAMPLES.md"}


@vite_bp.route("/api/3d/mesh-sharpen", methods=["POST"])
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


@vite_bp.route("/api/3d/run-pipeline", methods=["POST"])
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


@vite_bp.route("/api/3d/compose-scene", methods=["POST"])
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


@vite_bp.route("/api/code/visual-audit", methods=["POST"])
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


@vite_bp.route("/api/code/tooling-eval", methods=["POST"])
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


@vite_bp.route("/api/code/assets/generate", methods=["POST"])
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


@vite_bp.route("/api/code/assets/file/<path:asset_path>", methods=["GET"])
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


@vite_bp.route("/api/code/generate/stream", methods=["POST"])
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


@vite_bp.route("/api/aurora/<module>/<action>", methods=["POST"])
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


@vite_bp.route("/api/3d/run-index", methods=["GET"])
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


@vite_bp.route("/api/3d/score-history", methods=["GET"])
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


@vite_bp.route("/api/3d/mesh-compare", methods=["POST"])
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


@vite_bp.route("/api/3d/viewer-html", methods=["POST"])
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
@vite_bp.route("/draco/<path:relpath>", methods=["GET"])
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


@vite_bp.route("/api/agents/list", methods=["GET"])
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
        os.path.dirname(os.path.abspath(__file__)), "..", "..", ".claude",
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


@vite_bp.route("/api/agents/<name>", methods=["GET"])
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


@vite_bp.route("/api/3d/auto-rescue", methods=["POST"])
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


@vite_bp.route("/api/3d/bake-colors", methods=["POST"])
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


@vite_bp.route("/api/3d/color-diagnostic", methods=["POST"])
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


@vite_bp.route("/api/3d/auto-validate", methods=["POST"])
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


@vite_bp.route("/api/3d/mesh-score", methods=["POST"])
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


@vite_bp.route("/api/agents/watchdog", methods=["GET"])
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


@vite_bp.route("/api/agents/health", methods=["GET"])
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


@vite_bp.route("/api/agents/dispatches", methods=["GET"])
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


@vite_bp.route("/api/agents/coverage", methods=["GET"])
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


@vite_bp.route("/api/agents/metrics", methods=["GET"])
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


@vite_bp.route("/api/3d/motion-intent", methods=["POST"])
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


@vite_bp.route("/api/3d/custom-motion", methods=["POST"])
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


@vite_bp.route("/api/3d/auto-motion-bake", methods=["POST"])
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


@vite_bp.route("/api/admin/git-pull", methods=["POST", "GET"])
def admin_git_pull():
    if not _admin_ok():
        return jsonify({"error": "admin_refuse_tunnel", "détail": "local ou token admin requis"}), 403
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


@vite_bp.route("/api/admin/restart-vite", methods=["POST", "GET"])
def admin_restart_vite():
    if not _admin_ok():
        return jsonify({"error": "admin_refuse_tunnel", "détail": "local ou token admin requis"}), 403
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


@vite_bp.route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
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
    # Step 0 (iter32 SEC): le pseudo-protocole Vite /@fs/ permet de lire
    # n'importe quel fichier du répertoire du root dev (bridge_server.py,
    # output/**, python-services/**, scripts/**) et court-circuitait toutes
    # les blacklists ci-dessous car il était dans l'allow-list testée avant.
    # Aucun asset du build ne passe par /@fs/ (tout passe par /assets/ et
    # /src via le disque Vite) → on l'interdit en absolu, quelle que soit la
    # forme (canonicalized) de l'URL.
    if canonical.startswith("@fs/"):
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
        "src/", "@vite/", "@react-refresh", "@id/",
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


@vite_bp.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
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

