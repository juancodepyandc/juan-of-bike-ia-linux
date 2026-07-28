#!/usr/bin/env python3
"""Lipsync par REGENERATION audio-conditionnee (Wan 2.2 S2V), via ComfyUI.

POURQUOI PAS UN PATCH DE BOUCHE
--------------------------------
Les moteurs classiques (MuseTalk, LatentSync, Wav2Lip) repeignent la seule
boite bouche/menton d'une video existante. Cela corrige « la bouche ne suit pas
la voix », mais PAS « la tete se deforme quand il parle » : la zone repeinte
devient stable pendant que le crane continue de fondre autour, ce qui donne un
effet de masque flottant, souvent pire que le defaut d'origine.

S2V prend l'audio comme CONDITION de generation : le plan est reproduit avec la
parole comme entree, donc levres, machoire, tete et epaules sont coherents par
construction. C'est la seule facon de traiter les deux defauts d'un meme geste.

CE QUI EST DEJA LA
------------------
ComfyUI 0.27 embarque les noeuds nativement — rien a installer :
  WanSoundImageToVideo   (comfy_extras/nodes_wan.py)
  AudioEncoderLoader / AudioEncoderEncode (nodes_audio_encoder.py)
Poids telecharges dans modele/comfyui/models/ :
  unet/Wan2.2-S2V-14B-Q5_K_M.gguf        15,0 Go
  text_encoders/umt5-xxl-encoder-Q5_K_M.gguf  4,1 Go
  audio_encoders/wav2vec2_large_english_fp16.safetensors  0,6 Go
  vae/wan_2.1_vae.safetensors            0,25 Go
Licence Wan 2.2 : Apache 2.0 — utilisable commercialement, contrairement a
Wav2Lip (S-Lab non-commercial), Sonic, FLOAT ou KDTalker.

Usage :
  python s2v_lipsync.py --check
  python s2v_lipsync.py --image ref.png --audio voix.wav --output plan.mp4 \
      --prompt "a young man speaking to camera, anime style"
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

COMFY = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMFY_DIR = os.path.join(os.path.dirname(ROOT), "modele", "comfyui")
MODELS = os.path.join(COMFY_DIR, "models")

DIT = "Wan2.2-S2V-14B-Q5_K_M.gguf"
TEXT_ENCODER = "umt5-xxl-encoder-Q5_K_M.gguf"
AUDIO_ENCODER = "wav2vec2_large_english_fp16.safetensors"
VAE = "wan_2.1_vae.safetensors"

NEGATIVE = (
    "deformed face, melting face, morphing head, distorted facial features, "
    "asymmetric eyes, merged eyes, warped mouth, closed mouth while speaking, "
    "changing identity, extra limbs, text, watermark, letters"
)


def emit(stage, detail=""):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def _weights_status():
    return {
        "dit": os.path.join(MODELS, "unet", DIT),
        "text_encoder": os.path.join(MODELS, "text_encoders", TEXT_ENCODER),
        "audio_encoder": os.path.join(MODELS, "audio_encoders", AUDIO_ENCODER),
        "vae": os.path.join(MODELS, "vae", VAE),
    }


def check():
    paths = _weights_status()
    missing = {k: p for k, p in paths.items() if not os.path.exists(p)}
    comfy_up = False
    try:
        with urllib.request.urlopen(f"{COMFY}/system_stats", timeout=6):
            comfy_up = True
    except Exception:
        pass
    return {
        "ok": not missing and comfy_up,
        "comfyui": comfy_up,
        "missing": list(missing),
        "weights": {k: (os.path.getsize(p) if os.path.exists(p) else 0)
                    for k, p in paths.items()},
    }


def build_workflow(image_path, audio_path, prompt, width, height, length,
                   steps, cfg, seed, out_prefix):
    """Graphe ComfyUI en format API.

    Chaine : GGUF DiT + umt5 -> conditionnement texte ; wav2vec2 -> encodage
    audio ; WanSoundImageToVideo assemble image de reference + audio en latent ;
    KSampler debruite ; VAEDecode -> images -> mp4.
    """
    return {
        "1": {"class_type": "UnetLoaderGGUF",
              "inputs": {"unet_name": DIT}},
        "2": {"class_type": "CLIPLoaderGGUF",
              "inputs": {"clip_name": TEXT_ENCODER, "type": "wan"}},
        "3": {"class_type": "VAELoader",
              "inputs": {"vae_name": VAE}},
        "4": {"class_type": "AudioEncoderLoader",
              "inputs": {"audio_encoder_name": AUDIO_ENCODER}},
        "5": {"class_type": "LoadAudio",
              "inputs": {"audio": os.path.basename(audio_path)}},
        "6": {"class_type": "AudioEncoderEncode",
              "inputs": {"audio_encoder": ["4", 0], "audio": ["5", 0]}},
        "7": {"class_type": "LoadImage",
              "inputs": {"image": os.path.basename(image_path)}},
        "8": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": prompt}},
        "9": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": NEGATIVE}},
        "10": {"class_type": "WanSoundImageToVideo",
               "inputs": {
                   "positive": ["8", 0], "negative": ["9", 0], "vae": ["3", 0],
                   "width": width, "height": height, "length": length,
                   "batch_size": 1,
                   "audio_encoder_output": ["6", 0],
                   "ref_image": ["7", 0],
               }},
        "11": {"class_type": "KSampler",
               "inputs": {
                   "model": ["1", 0],
                   "positive": ["10", 0], "negative": ["10", 1],
                   "latent_image": ["10", 2],
                   "seed": seed, "steps": steps, "cfg": cfg,
                   "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0,
               }},
        "12": {"class_type": "VAEDecode",
               "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage",
               "inputs": {"images": ["12", 0], "filename_prefix": out_prefix}},
    }


def _comfy_input_dir():
    """Dossier d'entree de ComfyUI (LoadImage/LoadAudio y lisent)."""
    for cand in (os.path.join(COMFY_DIR, "input"),
                 os.path.join(COMFY_DIR, "comfyui", "input")):
        if os.path.isdir(cand):
            return cand
    d = os.path.join(COMFY_DIR, "input")
    os.makedirs(d, exist_ok=True)
    return d


def run(image_path, audio_path, output_mp4, prompt, width=832, height=480,
        steps=20, cfg=4.5, seed=42, fps=16, timeout=7200):
    st = check()
    if not st["ok"]:
        return {"ok": False, "error": f"S2V indisponible: {st}"}

    inp = _comfy_input_dir()
    tag = uuid.uuid4().hex[:10]
    img_dst = os.path.join(inp, f"s2v_{tag}.png")
    aud_dst = os.path.join(inp, f"s2v_{tag}.wav")
    shutil.copy2(image_path, img_dst)
    shutil.copy2(audio_path, aud_dst)

    # longueur en frames : contrainte du noeud = multiple de 4, +1
    try:
        import wave
        with wave.open(audio_path) as w:
            dur = w.getnframes() / float(w.getframerate())
    except Exception:
        dur = 5.0
    length = max(9, int(round(dur * fps)))
    length = ((length - 1) // 4) * 4 + 1

    prefix = f"aurora_s2v_{tag}"
    wf = build_workflow(img_dst, aud_dst, prompt, width, height, length,
                        steps, cfg, seed, prefix)

    emit("s2v", f"{width}x{height}, {length} frames ({dur:.1f}s audio), "
                f"{steps} steps")
    req = urllib.request.Request(
        f"{COMFY}/prompt",
        data=json.dumps({"prompt": wf}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            pid = json.loads(r.read().decode()).get("prompt_id")
    except Exception as exc:
        return {"ok": False, "error": f"soumission ComfyUI refusee: {exc}"}
    if not pid:
        return {"ok": False, "error": "ComfyUI n'a pas renvoye de prompt_id"}

    t0 = time.time()
    images = []
    while time.time() - t0 < timeout:
        time.sleep(5)
        try:
            with urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=30) as r:
                hist = json.loads(r.read().decode())
        except Exception:
            continue
        entry = hist.get(pid)
        if not entry:
            continue
        status = (entry.get("status") or {})
        if status.get("status_str") == "error":
            return {"ok": False, "error": f"ComfyUI: {json.dumps(status)[:400]}"}
        outs = entry.get("outputs") or {}
        node = outs.get("13") or {}
        if node.get("images"):
            images = node["images"]
            break
    if not images:
        return {"ok": False, "error": f"aucune image produite en {timeout}s"}

    out_root = None
    for cand in (os.path.join(COMFY_DIR, "output"),
                 os.path.join(COMFY_DIR, "comfyui", "output")):
        if os.path.isdir(cand):
            out_root = cand
            break
    if not out_root:
        return {"ok": False, "error": "dossier de sortie ComfyUI introuvable"}

    first = images[0]
    frame_dir = os.path.join(out_root, first.get("subfolder") or "")
    pattern = os.path.join(frame_dir, f"{prefix}_%05d_.png")
    ff = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ff, "-v", "error", "-y", "-framerate", str(fps), "-i", pattern,
           "-i", audio_path, "-c:v", "libx264", "-crf", "16", "-preset", "slow",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
           output_mp4]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0 or not os.path.exists(output_mp4):
        return {"ok": False, "error": f"assemblage ffmpeg: {(proc.stderr or '')[-400:]}"}

    for p in (img_dst, aud_dst):
        try:
            os.remove(p)
        except OSError:
            pass

    return {"ok": True, "mp4": output_mp4, "engine": "wan2.2-s2v-14b-q5",
            "frames": len(images), "elapsed_s": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--image")
    ap.add_argument("--audio")
    ap.add_argument("--output")
    ap.add_argument("--prompt", default="a character speaking to the camera")
    ap.add_argument("--width", type=int, default=832)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--cfg", type=float, default=4.5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.check:
        print(json.dumps(check(), ensure_ascii=False))
        return 0
    if not (args.image and args.audio and args.output):
        print(json.dumps({"ok": False, "error": "--image, --audio et --output requis"}))
        return 1
    res = run(args.image, args.audio, args.output, args.prompt,
              args.width, args.height, args.steps, args.cfg, args.seed)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
