"""comfy_supervisor — keeps ComfyUI alive, restarts it on crash.

Runs as a sidecar daemon next to bridge_server.py :
  - probes http://127.0.0.1:8188/system_stats every 6s
  - if 3 consecutive failures → spawns ComfyUI again via its venv
  - persists PID in /tmp/comfy_supervisor.pid for external monitoring
  - logs transitions on stderr so the bridge can surface them

Exit with Ctrl+C. The child process is killed too.

Usage :
  python comfy_supervisor.py [--comfy-root PATH] [--port 8188]
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_COMFY_ROOT = r"C:\Users\Juan\Desktop\ia\AuroraIA-v2\modele\comfyui\comfyui"

_stop = threading.Event()


def log(msg: str) -> None:
    print(f"[comfy_supervisor] {time.strftime('%H:%M:%S')} {msg}", file=sys.stderr, flush=True)


def comfy_alive(port: int) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/system_stats")
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def spawn_comfy(comfy_root: str, port: int) -> subprocess.Popen | None:
    venv_py = Path(comfy_root) / "venv" / "Scripts" / "python.exe"
    main_py = Path(comfy_root) / "main.py"
    if not venv_py.exists() or not main_py.exists():
        log(f"ComfyUI missing at {comfy_root} (venv_py={venv_py.exists()}, main_py={main_py.exists()})")
        return None
    env = os.environ.copy()
    # Redirect stdout/stderr to rolling logs so we can diagnose crashes
    log_path = Path(comfy_root) / "comfyui_supervised.log"
    lf = open(log_path, "ab", buffering=0)
    try:
        proc = subprocess.Popen(
            [str(venv_py), "-u", "main.py", "--listen", "0.0.0.0", "--port", str(port)],
            cwd=comfy_root, env=env,
            stdout=lf, stderr=lf,
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0),
        )
        log(f"spawned pid={proc.pid} → {log_path}")
        return proc
    except Exception as e:
        log(f"spawn failed: {e}")
        lf.close()
        return None


def terminate_comfy(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        log(f"terminating pid={proc.pid}")
        if os.name == 'nt':
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        try:
            proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception as e:
        log(f"terminate error: {e}")


def on_sigint(*_args: object) -> None:
    log("signal received, stopping")
    _stop.set()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--comfy-root", default=DEFAULT_COMFY_ROOT)
    ap.add_argument("--port", type=int, default=8188)
    ap.add_argument("--poll-sec", type=float, default=6.0)
    ap.add_argument("--max-fails", type=int, default=3,
                    help="consecutive health-check failures before restart")
    ap.add_argument("--status-file", default=str(Path(os.environ.get("TEMP", "/tmp")) / "comfy_supervisor.json"),
                    help="JSON status written to this path every tick")
    args = ap.parse_args()

    signal.signal(signal.SIGINT, on_sigint)
    signal.signal(signal.SIGTERM, on_sigint)

    proc: subprocess.Popen | None = None
    fails = 0
    restarts = 0

    # Emit startup status
    Path(args.status_file).write_text(json.dumps({"status": "starting", "restarts": 0}))

    while not _stop.is_set():
        alive = comfy_alive(args.port)
        if alive:
            fails = 0
            if proc is None or proc.poll() is not None:
                # External ComfyUI is running — adopt it, don't spawn
                pass
        else:
            fails += 1
            if fails >= args.max_fails:
                log(f"ComfyUI unresponsive for {fails} checks → (re)starting")
                terminate_comfy(proc)
                proc = spawn_comfy(args.comfy_root, args.port)
                restarts += 1
                fails = 0
                # Give it some slack to come back up
                time.sleep(8)
        # Persist status
        try:
            Path(args.status_file).write_text(json.dumps({
                "status": "ok" if alive else "degraded",
                "restarts": restarts,
                "fails_since_ok": fails,
                "pid": (proc.pid if proc and proc.poll() is None else None),
                "at": time.time(),
            }))
        except Exception:
            pass
        _stop.wait(args.poll_sec)

    terminate_comfy(proc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
