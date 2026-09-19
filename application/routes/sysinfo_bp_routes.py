from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

sysinfo_bp = Blueprint('sysinfo_bp', __name__)

# =====================================================================
#  System info — extended hardware details
# =====================================================================

@sysinfo_bp.route("/api/system/info")
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



# --- Refactored to application/routes/cinema_bp_routes.py ---
