from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL
from bridge_server import COMFYUI_PATH, _comfyui_is_ready, _start_comfyui

comfy_life_bp = Blueprint('comfy_life_bp', __name__)

# =====================================================================
#  ComfyUI lifecycle endpoints
# =====================================================================

@comfy_life_bp.route("/api/comfyui/status", methods=["GET"])
def comfyui_status():
    running = _comfyui_is_ready()
    return jsonify({"ok": True, "running": running, "port": COMFYUI_PORT})


@comfy_life_bp.route("/api/comfyui/start", methods=["POST"])
def comfyui_start():
    if not COMFYUI_PATH:
        return jsonify({
            "ok": False, "ready": False,
            "error": "ComfyUI non detecte — verifiez que modele/comfyui/comfyui existe dans AuroraIA-v2.",
        })
    ready = _start_comfyui()
    return jsonify({"ok": ready, "ready": ready, "port": COMFYUI_PORT})


@comfy_life_bp.route("/api/comfyui/image")
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

