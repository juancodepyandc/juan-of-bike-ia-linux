from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

comfy_proxy_bp = Blueprint('comfy_proxy_bp', __name__)

# =====================================================================
#  ComfyUI Proxy
# =====================================================================

@comfy_proxy_bp.route("/proxy/comfy/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def comfyui_proxy(path):
    try:
        if path == "prompt" and request.method == "POST":
            from auto_rl.image_runtime import apply_validated_workflow
            data = request.get_json()
            data["prompt"] = apply_validated_workflow(apply_validated_workflow(data["prompt"]), "video")
            return _proxy(f"{COMFYUI_URL}/{path}", data_override=json.dumps(data).encode())
        return _proxy(f"{COMFYUI_URL}/{path}")
    except Exception as e:
        return jsonify({"error": f"ComfyUI non joignable: {e}"}), 504


