from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

upload_bp = Blueprint('upload_bp', __name__)

# =====================================================================
#  Upload — recevoir des fichiers depuis le telephone
# =====================================================================

@upload_bp.route("/api/upload", methods=["POST"])
def upload_file():
    """Recoit un fichier depuis le telephone et le sauvegarde dans le workspace."""
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier envoye"}), 400

    f = request.files["file"]
    target_dir = request.form.get("targetDir", "uploads")
    save_dir = os.path.join(WORKSPACE, target_dir)
    os.makedirs(save_dir, exist_ok=True)

    # Securiser le nom de fichier
    from werkzeug.utils import secure_filename
    safe_name = secure_filename(f.filename or "upload")
    # Eviter les doublons
    base, ext = os.path.splitext(safe_name)
    final_name = safe_name
    counter = 1
    while os.path.exists(os.path.join(save_dir, final_name)):
        final_name = f"{base}_{counter}{ext}"
        counter += 1

    save_path = os.path.join(save_dir, final_name)
    f.save(save_path)

    rel_path = os.path.relpath(save_path, WORKSPACE).replace("\\", "/")
    return jsonify({"path": rel_path, "name": final_name, "size": os.path.getsize(save_path)})


