from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL
from bridge_server import COMFYUI_PATH, _comfyui_is_ready, _start_comfyui, _comfyui_start_diagnostics

comfy_life_bp = Blueprint('comfy_life_bp', __name__)

# =====================================================================
#  ComfyUI lifecycle endpoints
# =====================================================================

@comfy_life_bp.route("/api/comfyui/status", methods=["GET"])
def comfyui_status():
    running = _comfyui_is_ready()
    return jsonify({"ok": True, "running": running, "port": COMFYUI_PORT,
                    "startup": _comfyui_start_diagnostics()})


@comfy_life_bp.route("/api/comfyui/start", methods=["POST"])
def comfyui_start():
    ready = _start_comfyui()
    diagnostics = _comfyui_start_diagnostics()
    return jsonify({**diagnostics, "ok": ready, "ready": ready, "port": COMFYUI_PORT})


_PIXEL_PERFECT_IMAGE_CACHE = {}

@comfy_life_bp.route("/api/comfyui/image")
def comfyui_image():
    """Proxy dédié pour les images ComfyUI — applique le raffinement optique Pixel-Perfect en Modèle renforcé."""
    filename = request.args.get("filename", "")
    subfolder = request.args.get("subfolder", "")
    image_type = request.args.get("type", "output")
    download = request.args.get("download", "0") in ("1", "true", "yes")
    if not filename:
        return jsonify({"error": "filename manquant"}), 400
    try:
        from auto_rl.versions import preference
        is_reinforced = (preference("image") == "validated")
    except Exception:
        is_reinforced = True

    cache_key = (filename, subfolder, image_type, is_reinforced)
    try:
        if is_reinforced and image_type == "output" and cache_key in _PIXEL_PERFECT_IMAGE_CACHE:
            cached_bytes, cached_cert = _PIXEL_PERFECT_IMAGE_CACHE[cache_key]
            headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Expose-Headers": "Content-Disposition, X-Aurora-Model-Variant, X-Aurora-Pixel-Perfect",
                "X-Aurora-Model-Variant": "renforce",
                "X-Aurora-Pixel-Perfect": "certified",
                "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{filename}"',
            }
            return Response(cached_bytes, status=200, content_type="image/png", headers=headers)

        r = requests.get(
            f"{COMFYUI_URL}/view",
            params={"filename": filename, "subfolder": subfolder, "type": image_type},
            stream=not (is_reinforced and image_type == "output"),
            timeout=30,
        )
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "Content-Disposition, X-Aurora-Model-Variant, X-Aurora-Pixel-Perfect",
            "X-Aurora-Model-Variant": "renforce" if is_reinforced else "base",
        }
        if download:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        else:
            headers["Content-Disposition"] = f'inline; filename="{filename}"'

        if is_reinforced and image_type == "output" and r.status_code == 200:
            try:
                import io
                import numpy as np
                from PIL import Image
                py_srv = str(WORKSPACE / "application" / "python-services")
                if py_srv not in sys.path:
                    sys.path.insert(0, py_srv)
                from pixel_perfect_optical_engine import apply_pixel_perfect_optical_refinement
                img_pil = Image.open(io.BytesIO(r.content)).convert("RGB")
                arr = np.asarray(img_pil, dtype=np.uint8)
                pp_res = apply_pixel_perfect_optical_refinement(arr, is_uv_texture=False)
                out_pil = Image.fromarray(pp_res["image"], mode="RGB")
                buf = io.BytesIO()
                out_pil.save(buf, format="PNG", compress_level=3)
                refined_bytes = buf.getvalue()
                if len(_PIXEL_PERFECT_IMAGE_CACHE) > 32:
                    _PIXEL_PERFECT_IMAGE_CACHE.clear()
                _PIXEL_PERFECT_IMAGE_CACHE[cache_key] = (refined_bytes, pp_res.get("certificate", {}))
                headers["X-Aurora-Pixel-Perfect"] = "certified"
                return Response(refined_bytes, status=200, content_type="image/png", headers=headers)
            except Exception:
                return Response(
                    r.content,
                    status=r.status_code,
                    content_type=r.headers.get("Content-Type", "image/png"),
                    headers=headers,
                )

        return Response(
            r.iter_content(chunk_size=4096) if hasattr(r, "iter_content") else r.content,
            status=r.status_code,
            content_type=r.headers.get("Content-Type", "image/png"),
            headers=headers,
        )
    except Exception as e:
        return jsonify({"error": f"ComfyUI image non accessible: {e}"}), 504
