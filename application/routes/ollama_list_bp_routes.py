from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

ollama_list_bp = Blueprint('ollama_list_bp', __name__)

# =====================================================================
#  Ollama model listing (pour le telephone — remplace invoke("ollama_list_models"))
# =====================================================================

@ollama_list_bp.route("/api/ollama/tags")
def ollama_tags():
    """Liste les modeles Ollama disponibles."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return Response(resp.content, content_type="application/json")
    except Exception as e:
        return jsonify({"models": [], "error": str(e)}), 504


