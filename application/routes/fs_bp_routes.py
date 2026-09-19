from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

fs_bp = Blueprint('fs_bp', __name__)

# =====================================================================
#  Filesystem — lecture/ecriture de fichiers pour les modules
# =====================================================================

@fs_bp.route("/api/fs/workspace-path")
def fs_workspace_path():
    return jsonify({"path": WORKSPACE})


@fs_bp.route("/api/fs/exists", methods=["POST"])
def fs_exists():
    path = request.get_json().get("path", "")
    return jsonify({"exists": os.path.exists(path)})


@fs_bp.route("/api/fs/mkdir", methods=["POST"])
def fs_mkdir():
    path = request.get_json().get("path", "")
    os.makedirs(path, exist_ok=True)
    return jsonify({"ok": True})


@fs_bp.route("/api/fs/read-text", methods=["POST"])
def fs_read_text():
    path = request.get_json().get("path", "")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return jsonify({"content": f.read()})
    except Exception as e:
        return jsonify({"content": "", "error": str(e)}), 404


@fs_bp.route("/api/fs/write-text", methods=["POST"])
def fs_write_text():
    data = request.get_json()
    path = data.get("path", "")
    content = data.get("content", "")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return jsonify({"ok": True})


@fs_bp.route("/api/fs/write-binary", methods=["POST"])
def fs_write_binary():
    data = request.get_json()
    path = data.get("path", "")
    raw_bytes = data.get("bytes", [])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(bytes(raw_bytes))
    return jsonify({"ok": True})


@fs_bp.route("/api/fs/read-binary", methods=["POST"])
def fs_read_binary():
    path = request.get_json().get("path", "")
    try:
        with open(path, "rb") as f:
            return jsonify({"bytes": list(f.read())})
    except Exception as e:
        return jsonify({"bytes": [], "error": str(e)}), 404


@fs_bp.route("/api/fs/remove-dir", methods=["POST"])
def fs_remove_dir():
    """Recursively remove a directory (used for voice library cleanup)."""
    import shutil as _sh
    path = (request.get_json(silent=True) or {}).get("path", "")
    if not path:
        return jsonify({"ok": False, "error": "path manquant"}), 400
    p = pathlib.Path(path)
    if not p.exists():
        return jsonify({"ok": True, "skipped": True})
    try:
        if p.is_file():
            p.unlink()
        else:
            _sh.rmtree(p)
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@fs_bp.route("/api/fs/list", methods=["POST"])
def fs_list_dir():
    """Lister les entrees directes d'un repertoire (non recursif)."""
    path = (request.get_json(silent=True) or {}).get("path", "")
    if not path or not os.path.isdir(path):
        return jsonify({"entries": []})
    try:
        entries = sorted(os.listdir(path))
        return jsonify({"entries": entries})
    except Exception as exc:
        return jsonify({"entries": [], "error": str(exc)}), 500


