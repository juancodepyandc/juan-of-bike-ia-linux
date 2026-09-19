from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

hardware_bp = Blueprint('hardware_bp', __name__)

# =====================================================================
#  Hardware / Runtime / Privilege  (les 404 du log)
# =====================================================================

@hardware_bp.route("/api/hardware")
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


@hardware_bp.route("/api/runtime/inspect")
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


@hardware_bp.route("/api/runtime/privilege")
def runtime_privilege():
    return jsonify({"isAdmin": True, "canElevate": False, "detail": "Bridge mode"})


@hardware_bp.route("/api/runtime/prepare-model", methods=["POST"])
def prepare_model():
    return jsonify({"ok": True, "detail": "Bridge Ready"})


