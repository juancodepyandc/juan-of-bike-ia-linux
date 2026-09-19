from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

asset_bp = Blueprint('asset_bp', __name__)

# =====================================================================
#  Asset serving — pour telecharger les images generees sur le tel
# =====================================================================

def _resoudre_chemin_workspace(brut):
    """Rend un chemin ABSOLU existant, ou None.

    `/api/upload` renvoie un chemin RELATIF au workspace (`os.path.relpath`),
    mais les routes qui le consommaient testaient `os.path.isfile()` dessus tel
    quel: ca ne marchait que si le pont avait ete lance depuis le workspace.
    Sinon, « introuvable » alors que le fichier etait bien la — signale le
    03/09 sur le detourage. On essaie l'absolu, puis relatif au workspace.
    """
    brut = (str(brut or "")).strip()
    if not brut:
        return None
    for cand in (brut, os.path.join(WORKSPACE, brut.lstrip("/\\"))):
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    return None


@asset_bp.route("/api/3d/select-subject", methods=["POST"])
def three_d_select_subject():
    """31/07 (demande Juan): isoler le SUJET sur la photo avant reconstruction.

    Modes: auto (detourage du sujet principal), clic {x,y}, cadre
    {x0,y0,x1,y1} — coordonnees normalisees 0..1. Rend un PNG RGBA detoure
    dans output/context/ et son chemin (le meme circuit que les pieces
    jointes).
    """
    data = request.get_json(silent=True) or {}
    image_path = _resoudre_chemin_workspace(data.get("image_path"))
    if not image_path:
        return jsonify({"ok": False, "error": "image_path introuvable: %s"
                        % (data.get("image_path") or "")}), 400
    sortie = os.path.join(WORKSPACE, "output", "context",
                          "sujet_%d.png" % int(time.time() * 1000))
    cmd = [sys.executable,
           os.path.join(WORKSPACE, "python-services", "selection_sujet.py"),
           "--image", image_path, "--sortie", sortie]
    clic = data.get("clic")
    cadre = data.get("cadre")
    if isinstance(cadre, (list, tuple)) and len(cadre) == 4:
        cmd += ["--cadre", ",".join(str(float(v)) for v in cadre)]
    elif isinstance(clic, (list, tuple)) and len(clic) == 2:
        cmd += ["--clic", ",".join(str(float(v)) for v in clic)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                              env=_build_python_env())
        for line in reversed((proc.stdout or "").splitlines()):
            line = line.strip()
            if line.startswith("{"):
                res = json.loads(line)
                if res.get("ok"):
                    res["url"] = "/api/asset/" + os.path.relpath(sortie, WORKSPACE)
                return jsonify(res)
        return jsonify({"ok": False,
                        "error": (proc.stderr or "selection sans sortie")[-300:]}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "selection trop longue (300 s)"}), 504


@asset_bp.route("/aurora_viewer.html")
def aurora_viewer_page():
    # 31/07 (audit): le viewer de fin de run pointait sur un serveur 3009
    # que RIEN ne demarrait — ecran noir garanti apres chaque generation.
    # Le bridge le sert lui-meme, plus aucun serveur a lancer a la main.
    return send_file(os.path.join(WORKSPACE, "aurora_viewer.html"),
                     mimetype="text/html", conditional=True)


@asset_bp.route("/api/asset/<path:filepath>")
def serve_asset(filepath):
    """Sert un fichier genere (image, audio, etc.) pour le telephone."""
    # Chercher dans les repertoires de sortie connus
    cold_gallery_candidate = None
    if filepath.startswith("aurora-models/outputs/videos/"):
        gallery_name = pathlib.PurePosixPath(filepath).name
        if gallery_name == filepath.removeprefix("aurora-models/outputs/videos/"):
            manager = globals().get("_storage_manager")
            if manager is not None and manager.cold_mounted():
                cold_gallery_candidate = str(manager.cold_root / "outputs" / "videos" / gallery_name)
    candidates = [
        cold_gallery_candidate,
        os.path.join(WORKSPACE, filepath),
        os.path.join(WORKSPACE, "output", filepath),
        os.path.join(WORKSPACE, "temp", filepath),
        filepath,  # chemin absolu direct
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return send_file(candidate)
    abort(404)


@asset_bp.route("/api/download/<path:filepath>")
def download_asset(filepath):
    """Telecharger un fichier genere avec Content-Disposition attachment (force le telechargement sur mobile)."""
    candidates = [
        os.path.join(WORKSPACE, filepath),
        os.path.join(WORKSPACE, "output", filepath),
        os.path.join(WORKSPACE, "temp", filepath),
        filepath,
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return send_file(candidate, as_attachment=True, download_name=os.path.basename(candidate))
    abort(404)


@asset_bp.route("/api/generated-files")
def list_generated_files():
    """Liste tous les fichiers generes (images, videos, audio, 3D) pour le telephone."""
    files = []
    search_dirs = [
        os.path.join(WORKSPACE, "output"),
        os.path.join(WORKSPACE, "temp"),
    ]
    extensions = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.webm', '.wav', '.mp3', '.obj', '.glb', '.gltf'}
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for root, _dirs, filenames in os.walk(search_dir):
            for fname in filenames:
                if os.path.splitext(fname)[1].lower() in extensions:
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, WORKSPACE).replace("\\", "/")
                    stat = os.stat(full)
                    files.append({
                        "name": fname,
                        "path": rel,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "type": os.path.splitext(fname)[1].lower().lstrip("."),
                    })
    files.sort(key=lambda f: f["modified"], reverse=True)
    return jsonify(files[:100])


@asset_bp.route("/api/image/persist", methods=["POST"])
def persist_generated_image():
    """Sauvegarde un rendu d'image dans la structure output/image/<context>/<session>/<intent_slug>.png."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename")
    context = data.get("context", "ui")
    session_id = data.get("sessionId", "general")
    intent_mode = data.get("mode", "creation")
    prompt = data.get("prompt", "")

    safe_context = "tunnel" if context == "tunnel" else "cli" if context == "cli" else "ui"
    safe_session = re.sub(r'[^a-zA-Z0-9_.-]+', '_', session_id or "session")
    mode_slug = re.sub(r'[^a-zA-Z0-9]+', '_', intent_mode.lower())[:15] or "creation"
    prompt_slug = re.sub(r'[^a-zA-Z0-9]+', '_', prompt.lower())[:35].strip('_') or "image"
    ts = int(data.get("timestamp") or time.time() * 1000)

    target_dir = os.path.join(WORKSPACE, "output", "image", safe_context, safe_session)
    os.makedirs(target_dir, exist_ok=True)

    out_filename = f"{mode_slug}_{prompt_slug}_{ts}.png"
    out_path = os.path.join(target_dir, out_filename)

    if filename:
        comfy_path = os.path.join(COMFYUI_PATH or "", "output", filename)
        if os.path.isfile(comfy_path):
            import shutil
            shutil.copy2(comfy_path, out_path)
            rel = os.path.relpath(out_path, WORKSPACE).replace("\\", "/")
            return jsonify({"ok": True, "path": rel, "filename": out_filename})

    return jsonify({"ok": False, "error": "Fichier source introuvable"}), 404


