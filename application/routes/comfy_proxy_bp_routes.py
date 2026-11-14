from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, io, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from PIL import Image, ImageOps
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

comfy_proxy_bp = Blueprint('comfy_proxy_bp', __name__)

COMFY_INPUT_DIR = pathlib.Path(WORKSPACE).parent / "modele" / "comfyui" / "input"


def _validate_and_save_comfy_input_png(raw_bytes: bytes, requested_name: str) -> str:
    """
    Valide strictement que `raw_bytes` est une vraie image matricielle décodable par PIL
    (rejette tout PDF/HTML/SVG déguisé en .png), applique l'orientation EXIF et l'enregistre
    en PNG 8-bit propre dans `/home/juan/AuroraIA/modele/comfyui/input/`.
    """
    if not raw_bytes or len(raw_bytes) < 32:
        raise ValueError("Fichier image vide ou tronqué")
    header = raw_bytes[:16]
    if header.startswith(b"%PDF-") or header.lstrip().startswith((b"<!DOC", b"<html", b"<HTML", b"<?xml", b"<svg")):
        raise ValueError("Document non-matriciel (PDF/HTML/SVG) rejeté pour ComfyUI LoadImage")

    with Image.open(io.BytesIO(raw_bytes)) as img:
        img.load()
        img = ImageOps.exif_transpose(img)
        if img.width < 16 or img.height < 16:
            raise ValueError(f"Dimensions d'image invalides ({img.width}x{img.height})")
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")
        out_buf = io.BytesIO()
        img.save(out_buf, format="PNG", compress_level=1)
        clean_png_bytes = out_buf.getvalue()

    safe_stem = re.sub(r"[^a-zA-Z0-9._-]", "_", pathlib.Path(requested_name or f"aurora_ref_{int(time.time()*1000)}.png").stem)
    if not safe_stem:
        safe_stem = f"aurora_ref_{int(time.time()*1000)}"
    clean_filename = f"{safe_stem}.png"

    COMFY_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    target_path = COMFY_INPUT_DIR / clean_filename
    target_path.write_bytes(clean_png_bytes)
    return clean_filename


def _sanitize_workflow_load_image_nodes(prompt_graph: dict) -> dict:
    """
    Vérifie chaque nœud `LoadImage` du graphe ComfyUI avant exécution.
    Si un fichier référencé dans `LoadImage` est absent ou corrompu (ex. ancien PDF déguisé),
    débranche proprement les `ReferenceLatent` associés et bascule le latent sur `EmptyFlux2LatentImage`
    afin que ComfyUI ne plante jamais avec `cannot identify image file`.
    """
    if not isinstance(prompt_graph, dict):
        return prompt_graph

    invalid_load_ids: set[str] = set()
    for node_id, node in list(prompt_graph.items()):
        if not isinstance(node, dict) or node.get("class_type") != "LoadImage":
            continue
        img_name = (node.get("inputs") or {}).get("image", "")
        clean_name = str(img_name).replace("\\", "/").split("/")[-1]
        img_path = COMFY_INPUT_DIR / clean_name
        is_valid = False
        if clean_name and img_path.is_file():
            try:
                with Image.open(img_path) as im:
                    im.verify()
                is_valid = True
            except Exception:
                try:
                    img_path.unlink()
                except Exception:
                    pass
        if not is_valid:
            invalid_load_ids.add(str(node_id))

    if not invalid_load_ids:
        return prompt_graph

    # Trouver toute la chaîne (ImageScale / ImageScaleToTotalPixels -> VAEEncode) issue des LoadImage invalides
    invalid_scale_ids: set[str] = set()
    for node_id, node in list(prompt_graph.items()):
        if not isinstance(node, dict):
            continue
        if node.get("class_type") in ("ImageScale", "ImageScaleToTotalPixels"):
            src = (node.get("inputs") or {}).get("image")
            if isinstance(src, list) and str(src[0]) in invalid_load_ids:
                invalid_scale_ids.add(str(node_id))

    invalid_encode_ids: set[str] = set()
    for node_id, node in list(prompt_graph.items()):
        if not isinstance(node, dict):
            continue
        if node.get("class_type") == "VAEEncode":
            src = (node.get("inputs") or {}).get("pixels")
            if isinstance(src, list) and (str(src[0]) in invalid_scale_ids or str(src[0]) in invalid_load_ids):
                invalid_encode_ids.add(str(node_id))

    # Rebrancher ReferenceLatent sur son conditioning parent et SamplerCustomAdvanced sur EmptyFlux2LatentImage
    for node_id, node in list(prompt_graph.items()):
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") or {}
        if node.get("class_type") == "ReferenceLatent":
            lat_src = inputs.get("latent")
            cond_src = inputs.get("conditioning")
            if isinstance(lat_src, list) and str(lat_src[0]) in invalid_encode_ids and isinstance(cond_src, list):
                # Remplacer toute référence à ce ReferenceLatent par cond_src
                for other in prompt_graph.values():
                    if not isinstance(other, dict):
                        continue
                    o_in = other.get("inputs") or {}
                    for k, v in list(o_in.items()):
                        if isinstance(v, list) and str(v[0]) == str(node_id):
                            o_in[k] = cond_src
                prompt_graph.pop(node_id, None)

    # Si SamplerCustomAdvanced utilisait directement l'encode_id comme latent_image, créer un EmptyFlux2LatentImage
    for node_id, node in list(prompt_graph.items()):
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") or {}
        if node.get("class_type") == "SamplerCustomAdvanced":
            lat_in = inputs.get("latent_image")
            if isinstance(lat_in, list) and str(lat_in[0]) in invalid_encode_ids:
                empty_id = "998"
                prompt_graph[empty_id] = {
                    "class_type": "EmptyFlux2LatentImage",
                    "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
                }
                inputs["latent_image"] = [empty_id, 0]

    for dead_id in (invalid_load_ids | invalid_scale_ids | invalid_encode_ids):
        prompt_graph.pop(dead_id, None)

    return prompt_graph


@comfy_proxy_bp.route("/api/comfyui/upload", methods=["POST"])
def comfyui_validated_upload():
    try:
        uploaded = request.files.get("image")
        if not uploaded:
            return jsonify({"error": "Aucun fichier image fourni"}), 400
        raw_bytes = uploaded.read()
        clean_name = _validate_and_save_comfy_input_png(raw_bytes, uploaded.filename or "aurora_ref.png")
        return jsonify({"name": clean_name, "subfolder": "", "type": "input"})
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 415
    except Exception as e:
        return jsonify({"error": f"Erreur validation image ComfyUI: {e}"}), 500


# =====================================================================
#  ComfyUI Proxy
# =====================================================================

@comfy_proxy_bp.route("/proxy/comfy/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def comfyui_proxy(path):
    try:
        if path == "upload/image" and request.method == "POST":
            uploaded = request.files.get("image")
            if uploaded:
                try:
                    raw_bytes = uploaded.read()
                    clean_name = _validate_and_save_comfy_input_png(raw_bytes, uploaded.filename or "aurora_ref.png")
                    return jsonify({"name": clean_name, "subfolder": "", "type": "input"})
                except ValueError as ve:
                    return jsonify({"error": str(ve)}), 415
        if path == "prompt" and request.method == "POST":
            from auto_rl.image_runtime import apply_validated_workflow
            data = request.get_json()
            prompt_graph = _sanitize_workflow_load_image_nodes(data.get("prompt") or {})
            data["prompt"] = apply_validated_workflow(apply_validated_workflow(prompt_graph), "video")
            return _proxy(f"{COMFYUI_URL}/{path}", data_override=json.dumps(data).encode())
        return _proxy(f"{COMFYUI_URL}/{path}")
    except Exception as e:
        return jsonify({"error": f"ComfyUI non joignable: {e}"}), 504



