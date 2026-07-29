#!/usr/bin/env python3
"""Generation video par HunyuanVideo 1.5, via les noeuds natifs de ComfyUI.

POURQUOI CE MOTEUR
------------------
Wan 2.2 TI2V-5B compresse en 4x16x16 puis patchifie en 2x2, soit un jeton latent
de 32x32 pixels : a 1280x704 le debruiteur ne voit que ~880 jetons spatiaux. Une
structure fine, rigide et periodique — un cadre de velo, une jante — tombe sous
cette densite et se deforme. C'est une limite de CAPACITE, pas de reglage : elle
ne se rattrape ni par un meilleur prompt ni par plus de pas.

HunyuanVideo 1.5 est un 8,3 B concu pour les cartes grand public, avec une
super-resolution dediee 720p -> 1080p. En fp8 il tient en ~8,3 Go, ce qui laisse
la place au VAE et a l'encodeur sur 16 Go.

CE QUI EST DEJA LA
------------------
ComfyUI 0.27 embarque les noeuds nativement — rien a installer :
  HunyuanVideo15ImageToVideo, HunyuanVideo15SuperResolution,
  EmptyHunyuanVideo15Latent, HunyuanVideo15LatentUpscaleWithModel

LICENCE
-------
Tencent Hunyuan Community License. Sa clause territoriale exclut l'Union
europeenne (« THIS LICENSE AGREEMENT DOES NOT APPLY IN THE EUROPEAN UNION »,
§4(c) couvrant les Outputs). Ce module est cable a la demande explicite de
l'utilisateur, qui a pris cette decision en connaissance de cause apres avoir
ecrit a Tencent. Le fait est consigne ici pour qu'aucune session future ne le
redecouvre ni ne l'ignore.

Usage :
  python hunyuan15_render.py --check
  python hunyuan15_render.py --image ancre.png --output plan.mp4 \
      --prompt "..." --duration 4 --sr
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

COMFY = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
COMFY_DIR = ROOT.parent / "modele" / "comfyui"
MODELS = COMFY_DIR / "models"

DIT_I2V = "hunyuanvideo1.5_720p_i2v_cfg_distilled_fp8_scaled.safetensors"
DIT_SR = "hunyuanvideo1.5_720p_sr_distilled_fp8_scaled.safetensors"
TEXT_ENCODER = "qwen_2.5_vl_7b_fp8_scaled.safetensors"
VAE = "hunyuanvideo15_vae_fp16.safetensors"
CLIP_VISION = "sigclip_vision_patch14_384.safetensors"
BYT5 = "byt5_small_glyphxl_fp16.safetensors"

# Resolution native 720p du modele et cadence d'entrainement.
NATIF_PAYSAGE = (1280, 704)
NATIF_PORTRAIT = (704, 1280)
FPS = 24
# Contrainte du noeud : longueur en 4k+1.
LONGUEUR_MAX = 121

NEGATIF = (
    "deformed, morphing, melting, warping geometry, extra limbs, extra wheels, "
    "duplicated object, floating object, static frame, frozen, "
    "text, watermark, letters, subtitles, blurry, low detail, "
    "style drift, inconsistent style"
)


def emit(stage: str, detail: str = ""):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def _poids() -> dict:
    return {
        "dit_i2v": MODELS / "diffusion_models" / DIT_I2V,
        "dit_sr": MODELS / "diffusion_models" / DIT_SR,
        "text_encoder": MODELS / "text_encoders" / TEXT_ENCODER,
        "vae": MODELS / "vae" / VAE,
        "clip_vision": MODELS / "clip_vision" / CLIP_VISION,
        "byt5": MODELS / "text_encoders" / BYT5,
    }


def check() -> dict:
    p = _poids()
    manquants = [k for k, v in p.items() if not v.exists()]
    noeuds_requis = ["HunyuanVideo15ImageToVideo", "HunyuanVideo15SuperResolution",
                     "EmptyHunyuanVideo15Latent", "UNETLoader", "DualCLIPLoader",
                     "VAELoader", "CLIPVisionLoader", "CLIPVisionEncode",
                     "KSampler", "VAEDecode"]
    trouves, comfy_up = [], False
    try:
        with urllib.request.urlopen(f"{COMFY}/object_info", timeout=25) as r:
            info = json.loads(r.read().decode())
        comfy_up = True
        trouves = [n for n in noeuds_requis if n in info]
    except Exception as exc:
        return {"ok": False, "comfyui": False, "error": str(exc)[:140]}
    return {
        "ok": not manquants and len(trouves) == len(noeuds_requis),
        "comfyui": comfy_up,
        "poids_manquants": manquants,
        "noeuds_manquants": [n for n in noeuds_requis if n not in trouves],
        "tailles_go": {k: round(v.stat().st_size / 1e9, 2)
                       for k, v in p.items() if v.exists()},
    }


def longueur_valide(duree_s: float) -> int:
    """Longueur en images, contrainte 4k+1, bornee a la fenetre native.

    On ne chaine JAMAIS : au-dela de la fenetre, le plan est raccourci et le
    dit — un raccord fabrique trois pertes composees (aller-retour VAE,
    reencodage chroma, changement de graine) et c'est la cause n°1 de derive.
    """
    n = int(round(max(0.5, float(duree_s)) * FPS))
    n = ((n - 1) // 4) * 4 + 1
    return max(13, min(n, LONGUEUR_MAX))


def build_workflow(image_path: str, prompt: str, width: int, height: int,
                   length: int, steps: int, cfg: float, seed: int,
                   prefix: str, super_resolution: bool) -> dict:
    """Graphe ComfyUI natif : i2v puis, optionnellement, super-resolution.

    Les deux DiT ne sont jamais charges ensemble : ComfyUI decharge le premier
    avant le second, ce qui est la seule facon de tenir 16 Go.
    """
    wf = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": DIT_I2V, "weight_dtype": "default"}},
        # HunyuanVideo 1.5 attend DEUX encodeurs de texte, pas un :
        # Qwen2.5-VL 7B porte la semantique, byt5-small le rendu des glyphes.
        # C'est `DualCLIPLoader` avec le type `hunyuan_video_15` — le simple
        # `CLIPLoader` n'expose meme pas ce type, un graphe ecrit avec lui
        # echouerait au premier rendu.
        "2": {"class_type": "DualCLIPLoader",
              "inputs": {"clip_name1": TEXT_ENCODER, "clip_name2": BYT5,
                         "type": "hunyuan_video_15", "device": "cpu"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "4": {"class_type": "CLIPVisionLoader",
              "inputs": {"clip_name": CLIP_VISION}},
        "5": {"class_type": "LoadImage",
              "inputs": {"image": os.path.basename(image_path)}},
        "6": {"class_type": "CLIPVisionEncode",
              "inputs": {"clip_vision": ["4", 0], "image": ["5", 0],
                         "crop": "center"}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": prompt}},
        "8": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": NEGATIF}},
        "9": {"class_type": "HunyuanVideo15ImageToVideo",
              "inputs": {"positive": ["7", 0], "negative": ["8", 0],
                         "vae": ["3", 0], "width": width, "height": height,
                         "length": length, "batch_size": 1,
                         "start_image": ["5", 0],
                         "clip_vision_output": ["6", 0]}},
        "10": {"class_type": "KSampler",
               "inputs": {"model": ["1", 0], "seed": seed, "steps": steps,
                          "cfg": cfg, "sampler_name": "euler",
                          "scheduler": "simple", "denoise": 1.0,
                          "positive": ["9", 0], "negative": ["9", 1],
                          "latent_image": ["9", 2]}},
    }
    latent_final = ["10", 0]

    if super_resolution:
        wf["11"] = {"class_type": "UNETLoader",
                    "inputs": {"unet_name": DIT_SR, "weight_dtype": "default"}}
        wf["12"] = {"class_type": "HunyuanVideo15SuperResolution",
                    "inputs": {"positive": ["7", 0], "negative": ["8", 0],
                               "latent": ["10", 0], "noise_augmentation": 0.7,
                               "vae": ["3", 0], "start_image": ["5", 0],
                               "clip_vision_output": ["6", 0]}}
        wf["13"] = {"class_type": "KSampler",
                    "inputs": {"model": ["11", 0], "seed": seed,
                               "steps": max(6, steps // 2), "cfg": cfg,
                               "sampler_name": "euler", "scheduler": "simple",
                               "denoise": 1.0,
                               "positive": ["12", 0], "negative": ["12", 1],
                               "latent_image": ["12", 2]}}
        latent_final = ["13", 0]

    wf["20"] = {"class_type": "VAEDecode",
                "inputs": {"samples": latent_final, "vae": ["3", 0]}}
    wf["21"] = {"class_type": "SaveImage",
                "inputs": {"images": ["20", 0], "filename_prefix": prefix}}
    return wf


def _comfy_dir(nom: str) -> Path:
    for cand in (COMFY_DIR / nom, COMFY_DIR / "comfyui" / nom):
        if cand.is_dir():
            return cand
    d = COMFY_DIR / nom
    d.mkdir(parents=True, exist_ok=True)
    return d


def _liberer_vram() -> None:
    """Evince les modeles Ollama avant de charger 8,3 Go de DiT.

    Mesure : le juge de vision (11,8 Go) reste resident 10 min apres son dernier
    appel ; sans cette eviction, le chargement echoue en « Got an OOM ».
    """
    base = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        with urllib.request.urlopen(f"{base}/api/ps", timeout=8) as r:
            charges = json.loads(r.read().decode()).get("models", [])
        for m in charges:
            req = urllib.request.Request(
                f"{base}/api/generate",
                data=json.dumps({"model": m.get("name"), "keep_alive": 0}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=20).read()
        if charges:
            emit("vram_free", f"{len(charges)} modele(s) Ollama decharges")
    except Exception:
        pass


def run(image_path: str, output_mp4: str, prompt: str, duree_s: float = 4.0,
        width: int = 0, height: int = 0, steps: int = 20, cfg: float = 1.0,
        seed: int = 42, super_resolution: bool = True,
        timeout: int = 10800) -> dict:
    etat = check()
    if not etat.get("ok"):
        return {"ok": False, "error": f"HunyuanVideo 1.5 indisponible: {etat}"}

    if not width or not height:
        width, height = NATIF_PAYSAGE
    # Le noeud exige des multiples de 16.
    width = max(256, (int(width) // 16) * 16)
    height = max(256, (int(height) // 16) * 16)
    length = longueur_valide(duree_s)
    if length < int(round(duree_s * FPS)):
        emit("plan_raccourci",
             f"{duree_s:.1f}s demande -> {length / FPS:.2f}s "
             f"(fenetre native {LONGUEUR_MAX / FPS:.1f}s). Pour tenir la duree, "
             f"decoupe en deux plans : un raccord deforme.")

    _liberer_vram()

    inp = _comfy_dir("input")
    tag = uuid.uuid4().hex[:10]
    src = Path(image_path)
    if not src.is_file():
        return {"ok": False, "error": f"image d'ancre absente: {image_path}"}
    nom = f"hy15_{tag}{src.suffix.lower() or '.png'}"
    shutil.copy2(src, inp / nom)

    prefix = f"aurora_hy15_{tag}"
    wf = build_workflow(str(inp / nom), prompt, width, height, length,
                        steps, cfg, seed, prefix, super_resolution)
    emit("hy15", f"{width}x{height}, {length} images ({length / FPS:.2f}s), "
                 f"{steps} pas" + (" + super-resolution" if super_resolution else ""))

    req = urllib.request.Request(
        f"{COMFY}/prompt", data=json.dumps({"prompt": wf}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            pid = json.loads(r.read().decode()).get("prompt_id")
    except Exception as exc:
        return {"ok": False, "error": f"soumission refusee: {exc}"}
    if not pid:
        return {"ok": False, "error": "ComfyUI n'a pas renvoye de prompt_id"}

    t0 = time.time()
    images = []
    while time.time() - t0 < timeout:
        time.sleep(6)
        try:
            with urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=30) as r:
                hist = json.loads(r.read().decode())
        except Exception:
            continue
        entry = hist.get(pid)
        if not entry:
            continue
        status = entry.get("status") or {}
        if status.get("status_str") == "error":
            for m in status.get("messages", []):
                if m and m[0] == "execution_error":
                    d = m[1]
                    return {"ok": False,
                            "error": f"{d.get('node_type')}: "
                                     f"{str(d.get('exception_message'))[:300]}"}
            return {"ok": False, "error": "erreur ComfyUI sans detail"}
        node = (entry.get("outputs") or {}).get("21") or {}
        if node.get("images"):
            images = node["images"]
            break
    if not images:
        return {"ok": False, "error": f"aucune image en {timeout}s"}

    out_root = _comfy_dir("output")
    frame_dir = out_root / (images[0].get("subfolder") or "")
    ff = shutil.which("ffmpeg") or "ffmpeg"
    Path(output_mp4).parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [ff, "-v", "error", "-y", "-framerate", str(FPS),
         "-i", str(frame_dir / f"{prefix}_%05d_.png"),
         "-c:v", "libx264", "-crf", "16", "-preset", "slow",
         # Plage et espace colorimetrique DECLARES : leur absence est la
         # signature de la derive chaude constatee sur les rendus chaines.
         "-color_range", "tv", "-colorspace", "bt709",
         "-color_primaries", "bt709", "-color_trc", "bt709",
         "-pix_fmt", "yuv420p", str(output_mp4)],
        capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0 or not Path(output_mp4).exists():
        return {"ok": False, "error": f"ffmpeg: {(proc.stderr or '')[-300:]}"}

    try:
        (inp / nom).unlink()
    except OSError:
        pass

    return {"ok": True, "mp4": output_mp4, "engine": "hunyuanvideo-1.5-720p-i2v",
            "width": width, "height": height, "frames": len(images),
            "fps": FPS, "duree_s": round(len(images) / FPS, 2),
            "super_resolution": super_resolution,
            "elapsed_s": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--image")
    ap.add_argument("--output")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--duration", type=float, default=4.0)
    ap.add_argument("--width", type=int, default=0)
    ap.add_argument("--height", type=int, default=0)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--cfg", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sr", dest="sr", action="store_true", default=True)
    ap.add_argument("--no-sr", dest="sr", action="store_false")
    args = ap.parse_args()

    if args.check:
        print(json.dumps(check(), ensure_ascii=False), flush=True)
        return 0
    if not (args.image and args.output):
        print(json.dumps({"ok": False, "error": "--image et --output requis"}),
              flush=True)
        return 1
    res = run(args.image, args.output, args.prompt, args.duration,
              args.width, args.height, args.steps, args.cfg, args.seed, args.sr)
    print(json.dumps(res, ensure_ascii=False), flush=True)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
