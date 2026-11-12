"""Bridge routes of the professor autopilot: the interface starts, stops and follows it.

Every route, reading included, is guarded by the bridge's device check (``allowed``): the state names the Kaggle
account, and starting spends Kaggle quota and may switch the Ollama tag the application uses. State-changing
routes also refuse cross-site requests. The runner is a separate process (``python -m auto_rl.professor.autopilot
run``) that survives a bridge restart; the routes only read its state file and write its stop request.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]


def missing_requirements():
    """What the PC lacks to run the autopilot, in French, or an empty list."""
    problems = []
    for package in ("kaggle", "datasets"):
        if importlib.util.find_spec(package) is None:
            problems.append(f"paquet Python « {package} » absent (pip install kaggle datasets)")
    home = Path.home() / ".kaggle"
    credential = (os.environ.get("KAGGLE_API_TOKEN") or (os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))
                  or (home / "kaggle.json").is_file() or (home / "access_token").is_file())
    if not credential:
        problems.append("identifiants Kaggle absents (%USERPROFILE%\\.kaggle\\kaggle.json)")
    return problems


def spawn_runner(*, activate=True):
    """Start the runner detached from the bridge, its output appended to the autopilot log."""
    from . import autopilot
    autopilot.AUTOPILOT.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "auto_rl.professor.autopilot", "run"] + ([] if activate else ["--no-activate"])
    options = {"cwd": str(ROOT), "stdin": subprocess.DEVNULL, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        options["start_new_session"] = True
    with open(autopilot.LOG_FILE, "ab") as log:
        process = subprocess.Popen(command, stdout=log, **options)
    return process.pid


def register_routes(app, *, allowed):
    from flask import jsonify, request
    from . import autopilot

    def same_origin():
        origin = request.headers.get("Origin")
        if not origin:
            return True
        parsed = urlsplit(origin)
        local = {request.host, "127.0.0.1:1420", "localhost:1420", "127.0.0.1:3001", "localhost:3001", "localhost", "tauri.localhost"}
        return parsed.scheme in {"http", "https", "tauri"} and parsed.netloc in local

    def refused():
        if not allowed():
            return jsonify({"error": "forbidden_public"}), 403
        if request.method == "POST" and not same_origin():
            return jsonify({"error": "Requête refusée : origine inconnue."}), 403
        return None

    @app.get("/api/professor/autopilot")
    def professor_autopilot_status():
        blocked = refused()
        if blocked:
            return blocked
        problems = missing_requirements()
        status = autopilot.status()
        return jsonify({**status, "supported": not problems, "error": " ; ".join(problems) or None})

    @app.post("/api/professor/autopilot/start")
    def professor_autopilot_start():
        blocked = refused()
        if blocked:
            return blocked
        problems = missing_requirements()
        if problems:
            return jsonify({"error": "Autopilote impossible sur ce PC : " + " ; ".join(problems)}), 503
        state = autopilot.load()
        if autopilot.runner_alive(state):
            return jsonify({"error": "L'autopilote tourne déjà.", "running": True}), 409
        payload = request.get_json(silent=True) or {}
        pid = spawn_runner(activate=payload.get("activate", True) is not False)
        return jsonify({"started": True, "pid": pid})

    @app.post("/api/professor/autopilot/stop")
    def professor_autopilot_stop():
        blocked = refused()
        if blocked:
            return blocked
        return jsonify(autopilot.stop())

    @app.post("/api/professor/autopilot/resume")
    def professor_autopilot_resume():
        blocked = refused()
        if blocked:
            return blocked
        student = (request.get_json(silent=True) or {}).get("student")
        if student not in (autopilot.load().get("order") or autopilot.STUDENTS):
            return jsonify({"error": "Modèle inconnu de l'autopilote."}), 400
        autopilot.resume(student)
        return jsonify({"resumed": student})
