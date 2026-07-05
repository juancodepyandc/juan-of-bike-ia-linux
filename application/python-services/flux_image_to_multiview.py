#!/usr/bin/env python3
"""
flux_image_to_multiview.py
Takes a reference image (e.g. from web_reference_search) and uses FLUX Image-to-Image
with a low denoise strength to standardize it (clean background, match art style)
so it can be safely used as a back/side view in Hunyuan3D.
"""

import sys
import json
import argparse
import time
from pathlib import Path
from random import randint

# Re-use helpers from flux_reference_synth
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from flux_reference_synth import (
        COMFY_BASE, DEFAULT_CLIP_L, DEFAULT_CLIP_T5, DEFAULT_UNET, DEFAULT_VAE,
        DEFAULT_OUTPUT_DIR, post_prompt, output_path_from_history, fetch_to, poll_history
    )
except ImportError:
    pass

import urllib.request
import urllib.parse
import shutil

COMFY_INPUT_DIR = Path(__file__).resolve().parents[2] / "modele" / "comfyui" / "comfyui" / "input"

def build_img2img_workflow(prompt: str, input_image_name: str, width: int = 1024, height: int = 1024,
                           steps: int = 25, denoise: float = 0.55, seed: int | None = None,
                           filename_prefix: str = "aurora_flux_i2i") -> dict:
    if seed is None:
        seed = randint(1, 2**32 - 1)
        
    return {
        "11": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": DEFAULT_CLIP_T5, "clip_name2": DEFAULT_CLIP_L, "type": "flux"}},
        "12": {"class_type": "UNETLoader", "inputs": {"unet_name": DEFAULT_UNET, "weight_dtype": "fp8_e4m3fn"}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": DEFAULT_VAE}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["11", 0], "text": prompt}},
        "33": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["11", 0], "text": ""}},
        "26": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["6", 0], "guidance": 3.5}},
        "40": {"class_type": "LoadImage", "inputs": {"image": input_image_name}},
        "41": {"class_type": "VAEEncode", "inputs": {"pixels": ["40", 0], "vae": ["10", 0]}},
        "31": {"class_type": "KSampler", "inputs": {
            "model": ["12", 0],
            "positive": ["26", 0],
            "negative": ["33", 0],
            "latent_image": ["41", 0],
            "seed": seed,
            "steps": steps,
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": denoise
        }},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["31", 0], "vae": ["10", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": filename_prefix}}
    }

def synth_view_from_image(prompt: str, run_id: str, view: str, source_image_path: Path,
                          output_dir: Path = DEFAULT_OUTPUT_DIR,
                          denoise: float = 0.6) -> dict:
    # 1. Copy image to ComfyUI input dir
    comfy_img_name = f"aurora_i2i_{run_id}_{view}_{source_image_path.name}"
    target_img_path = COMFY_INPUT_DIR / comfy_img_name
    COMFY_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_image_path, target_img_path)
    
    # Enforce strict view constraints so Img2Img actually changes the pose
    view_prompts = {
        "back": "back view, seen from behind, back profile",
        "left": "left side profile view, looking left",
        "right": "right side profile view, looking right"
    }
    enriched_prompt = f"{prompt}, {view_prompts.get(view, '')}, STRICT SINGLE-VIEW RECONSTRUCTION REFERENCE, one full-body subject only, exact same character"
    
    # 2. Build workflow
    wf = build_img2img_workflow(enriched_prompt, comfy_img_name, denoise=denoise, filename_prefix=f"aurora_{run_id}_{view}")
    
    try:
        pid = post_prompt(wf, COMFY_BASE)
    except Exception as e:
        return {"ok": False, "error": f"ComfyUI /prompt failed: {e}"}
        
    hist = poll_history(pid, comfy_base=COMFY_BASE)
    if not hist:
        return {"ok": False, "error": "ComfyUI generation timeout"}
        
    comfy_out_path = output_path_from_history(hist, comfy_base=COMFY_BASE)
    if not comfy_out_path:
        return {"ok": False, "error": "No image in ComfyUI history"}
        
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / f"{run_id}_reference_{view}.png"
    
    try:
        fetch_to(comfy_out_path, final_path)
        return {"ok": True, "path": str(final_path)}
    except Exception as e:
        return {"ok": False, "error": f"Failed to download from ComfyUI: {e}"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--view", required=True, choices=["back", "left", "right"])
    parser.add_argument("--source-image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--denoise", type=float, default=0.6)
    args = parser.parse_args()
    
    result = synth_view_from_image(args.prompt, args.run_id, args.view, Path(args.source_image), Path(args.output_dir), args.denoise)
    print(json.dumps(result))

if __name__ == "__main__":
    main()
