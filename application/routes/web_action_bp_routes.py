from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

web_action_bp = Blueprint('web_action_bp', __name__)

# =====================================================================
#  Web Action (Playwright visible pour le web automation interactif)
# =====================================================================

@web_action_bp.route("/api/web/action", methods=["POST"])
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


