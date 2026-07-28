#!/usr/bin/env python3
"""Generation pilotee par CONTROLE (Wan 2.2 Fun-Control) — mouvement ET identite.

LE MUR QUE CE MODULE LEVE
-------------------------
Mesure sur un plan reel « Natsu roule a velo » :
  - avec ancre i2v  : identite parfaite, mais le personnage reste DEBOUT,
    velo a l'arret (phys=3/10). Le conditionnement verrouille la pose de
    depart et le modele translate un bloc immobile.
  - sans ancre (t2v): le mouvement devient juste (phys=8/10), mais l'identite
    se perd — « hair color differs between frames (dark vs pink) ».
Aucun reglage ne donne les deux, parce que la meme entree porte les deux
informations.

Fun-Control les SEPARE : `control_video` porte le MOUVEMENT (depth/pose extraits
d'une vraie video), `ref_image` porte l'IDENTITE. Le modele n'a plus a choisir.

Le pipeline reste en deux experts MoE (high noise = composition et mouvement,
low noise = detail), charges sequentiellement — jamais ensemble, sinon 16 Go de
VRAM n'y suffisent pas.

Usage :
  python vace_control.py --check
  python vace_control.py --control marche.mp4 --ref natsu.png \
      --output plan.mp4 --prompt "..." --control-type depth
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

HIGH = "Wan2.2-Fun-A14B-Control_HighNoise-Q4_K_M.gguf"
LOW = "Wan2.2-Fun-A14B-Control_LowNoise-Q4_K_M.gguf"
TEXT_ENCODER = "umt5-xxl-encoder-Q5_K_M.gguf"
VAE = "wan_2.1_vae.safetensors"

# Preprocesseurs de comfyui_controlnet_aux
PREPROC = {
    "depth": "DepthAnythingV2Preprocessor",
    "pose": "DWPreprocessor",
    "canny": "CannyEdgePreprocessor",
}

NEGATIVE = (
    "static, frozen, motionless, sliding sideways, deformed, morphing, "
    "extra limbs, text, watermark, letters"
)


def emit(stage, detail=""):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def check():
    paths = {
        "high": os.path.join(MODELS, "unet", HIGH),
        "low": os.path.join(MODELS, "unet", LOW),
        "text_encoder": os.path.join(MODELS, "text_encoders", TEXT_ENCODER),
        "vae": os.path.join(MODELS, "vae", VAE),
    }
    missing = [k for k, p in paths.items() if not os.path.exists(p)]
    nodes_ok, have = False, []
    try:
        with urllib.request.urlopen(f"{COMFY}/object_info", timeout=20) as r:
            info = json.loads(r.read().decode())
        need = ["Wan22FunControlToVideo", "UnetLoaderGGUF", "CLIPLoaderGGUF",
                "VAELoader", "KSamplerAdvanced", "VAEDecode", "SaveImage",
                "VHS_LoadVideoPath"]
        have = [n for n in need if n in info]
        preproc_have = [v for v in PREPROC.values() if v in info]
        nodes_ok = len(have) >= 7 and bool(preproc_have)
    except Exception:
        preproc_have = []
    return {"ok": not missing and nodes_ok, "missing_weights": missing,
            "nodes_found": have, "preprocessors": preproc_have}


def build_workflow(control_frames_dir, ref_image, prompt, ctrl_type,
                   width, height, length, steps, cfg, seed, out_prefix):
    """Graphe en deux passes MoE : high noise puis low noise.

    KSamplerAdvanced permet de couper le debruitage en deux : l'expert high
    traite les premiers pas (structure, mouvement), l'expert low les derniers
    (texture, detail). C'est le fonctionnement natif de l'A14B ; enchainer deux
    KSampler simples donnerait un resultat nettement inferieur.
    """
    boundary = max(1, int(steps * 0.5))
    pre = PREPROC.get(ctrl_type, PREPROC["depth"])
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": HIGH}},
        "2": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": LOW}},
        "3": {"class_type": "CLIPLoaderGGUF",
              "inputs": {"clip_name": TEXT_ENCODER, "type": "wan"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "5": {"class_type": "VHS_LoadVideoPath",
              "inputs": {"video": control_frames_dir, "force_rate": 16,
                         "force_size": "Disabled", "custom_width": width,
                         "custom_height": height, "frame_load_cap": length,
                         "skip_first_frames": 0, "select_every_nth": 1}},
        "6": {"class_type": pre,
              "inputs": {"image": ["5", 0], "resolution": max(width, height)}},
        "7": {"class_type": "LoadImage",
              "inputs": {"image": os.path.basename(ref_image)}},
        "8": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["3", 0], "text": prompt}},
        "9": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["3", 0], "text": NEGATIVE}},
        "10": {"class_type": "Wan22FunControlToVideo",
               "inputs": {"positive": ["8", 0], "negative": ["9", 0],
                          "vae": ["4", 0], "width": width, "height": height,
                          "length": length, "batch_size": 1,
                          "ref_image": ["7", 0], "control_video": ["6", 0]}},
        "11": {"class_type": "KSamplerAdvanced",
               "inputs": {"model": ["1", 0], "add_noise": "enable",
                          "noise_seed": seed, "steps": steps, "cfg": cfg,
                          "sampler_name": "uni_pc", "scheduler": "simple",
                          "positive": ["10", 0], "negative": ["10", 1],
                          "latent_image": ["10", 2],
                          "start_at_step": 0, "end_at_step": boundary,
                          "return_with_leftover_noise": "enable"}},
        "12": {"class_type": "KSamplerAdvanced",
               "inputs": {"model": ["2", 0], "add_noise": "disable",
                          "noise_seed": seed, "steps": steps, "cfg": cfg,
                          "sampler_name": "uni_pc", "scheduler": "simple",
                          "positive": ["10", 0], "negative": ["10", 1],
                          "latent_image": ["11", 0],
                          "start_at_step": boundary, "end_at_step": steps,
                          "return_with_leftover_noise": "disable"}},
        "13": {"class_type": "VAEDecode",
               "inputs": {"samples": ["12", 0], "vae": ["4", 0]}},
        "14": {"class_type": "SaveImage",
               "inputs": {"images": ["13", 0], "filename_prefix": out_prefix}},
    }


def _comfy_dir(name):
    for cand in (os.path.join(COMFY_DIR, name),
                 os.path.join(COMFY_DIR, "comfyui", name)):
        if os.path.isdir(cand):
            return cand
    d = os.path.join(COMFY_DIR, name)
    os.makedirs(d, exist_ok=True)
    return d


def run(control_video, ref_image, output_mp4, prompt, ctrl_type="depth",
        width=832, height=480, length=81, steps=20, cfg=4.5, seed=42,
        fps=16, timeout=14400):
    st = check()
    if not st["ok"]:
        return {"ok": False, "error": f"Fun-Control indisponible: {st}"}

    inp = _comfy_dir("input")
    tag = uuid.uuid4().hex[:10]
    ref_dst = os.path.join(inp, f"vace_ref_{tag}.png")
    shutil.copy2(ref_image, ref_dst)
    ctrl_dst = os.path.join(inp, f"vace_ctrl_{tag}.mp4")
    shutil.copy2(control_video, ctrl_dst)

    prefix = f"aurora_vace_{tag}"
    wf = build_workflow(ctrl_dst, ref_dst, prompt, ctrl_type,
                        width, height, length, steps, cfg, seed, prefix)
    emit("vace", f"{ctrl_type} {width}x{height}, {length} frames, "
                 f"{steps} steps (MoE high+low)")

    req = urllib.request.Request(
        f"{COMFY}/prompt", data=json.dumps({"prompt": wf}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            pid = json.loads(r.read().decode()).get("prompt_id")
    except Exception as exc:
        return {"ok": False, "error": f"soumission refusee: {exc}"}

    t0 = time.time()
    images = []
    while time.time() - t0 < timeout:
        time.sleep(8)
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
                if m[0] == "execution_error":
                    d = m[1]
                    return {"ok": False,
                            "error": f"{d.get('node_type')}: "
                                     f"{str(d.get('exception_message'))[:300]}"}
            return {"ok": False, "error": "erreur ComfyUI sans detail"}
        node = (entry.get("outputs") or {}).get("14") or {}
        if node.get("images"):
            images = node["images"]
            break
    if not images:
        return {"ok": False, "error": f"aucune image en {timeout}s"}

    out_root = _comfy_dir("output")
    frame_dir = os.path.join(out_root, images[0].get("subfolder") or "")
    ff = shutil.which("ffmpeg") or "ffmpeg"
    proc = subprocess.run(
        [ff, "-v", "error", "-y", "-framerate", str(fps),
         "-i", os.path.join(frame_dir, f"{prefix}_%05d_.png"),
         "-c:v", "libx264", "-crf", "16", "-preset", "slow",
         "-pix_fmt", "yuv420p", output_mp4],
        capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0 or not os.path.exists(output_mp4):
        return {"ok": False, "error": f"ffmpeg: {(proc.stderr or '')[-300:]}"}

    for p in (ref_dst, ctrl_dst):
        try:
            os.remove(p)
        except OSError:
            pass
    return {"ok": True, "mp4": output_mp4, "engine": f"wan2.2-fun-control-{ctrl_type}",
            "frames": len(images), "elapsed_s": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--control")
    ap.add_argument("--ref")
    ap.add_argument("--output")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--control-type", default="depth", choices=sorted(PREPROC))
    ap.add_argument("--width", type=int, default=832)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--length", type=int, default=81)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--cfg", type=float, default=4.5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.check:
        print(json.dumps(check(), ensure_ascii=False))
        return 0
    if not (args.control and args.ref and args.output):
        print(json.dumps({"ok": False,
                          "error": "--control, --ref et --output requis"}))
        return 1
    res = run(args.control, args.ref, args.output, args.prompt,
              args.control_type, args.width, args.height, args.length,
              args.steps, args.cfg, args.seed)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
