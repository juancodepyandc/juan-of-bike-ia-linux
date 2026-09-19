from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

status_bp = Blueprint('status_bp', __name__)

# =====================================================================
#  Services status
# =====================================================================

@status_bp.route("/api/services/status")
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


