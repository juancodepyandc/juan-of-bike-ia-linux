from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

ollama_enh_bp = Blueprint('ollama_enh_bp', __name__)

# =====================================================================
#  Ollama — enhanced model list and pull with SSE progress
# =====================================================================

@ollama_enh_bp.route("/api/ollama/models")
def ollama_models():
    """List installed Ollama models with sizes, sorted by name."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = []
        for m in data.get("models", []):
            size_gb = round(m.get("size", 0) / (1024 ** 3), 2)
            models.append({
                "name": m.get("name", ""),
                "size_gb": size_gb,
                "modified_at": m.get("modified_at", ""),
                "details": m.get("details", {}),
            })
        models.sort(key=lambda x: x["name"])
        return jsonify({"models": models, "count": len(models)})
    except Exception as e:
        return jsonify({"models": [], "count": 0, "error": str(e)}), 504


@ollama_enh_bp.route("/api/ollama/pull", methods=["POST"])
def ollama_pull():
    """Stream model download progress via SSE. Body: {name: string}."""
    data = request.get_json(silent=True) or {}
    model_name = data.get("name", "").strip()
    if not model_name:
        return jsonify({"error": "model name required"}), 400

    def generate():
        try:
            with requests.post(
                f"{OLLAMA_URL}/api/pull",
                json={"name": model_name, "stream": True},
                stream=True,
                timeout=3600,
            ) as r:
                for line in r.iter_lines():
                    if line:
                        yield f"data: {line.decode('utf-8', errors='replace')}\n\n"
        except Exception as e:
            yield f"data: {{\"error\": \"{e}\"}}\n\n"
        yield "data: {\"done\": true}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


