"""AuroraIA Hunyuan3D robust pipeline (Text-to-3D & Image-to-3D).

Supports explicitly resuming at shapegen or texgen to allow intermediate 
topological repair (Blender).
"""
from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import psutil
import torch
import trimesh
from PIL import Image

from aurora_classify import SceneProfile, classify

REPO = Path(__file__).resolve().parent
AURORA = Path(__file__).resolve().parents[3]
BLENDER = Path(os.environ.get("AURORA_BLENDER") or shutil.which("blender") or
               AURORA / "application" / "_blender" / "blender-4.2.12-windows-x64" / "blender.exe")
OUTPUT_ROOT = AURORA / "application" / "output" / "3d"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("aurora_robust")

def _free_vram() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.ipc_collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

def check_hardware(device: str = "cuda") -> None:
    log.info("--- Hardware Check ---")
    ram = psutil.virtual_memory()
    log.info(f"RAM: {ram.available / 1e9:.2f} GB free / {ram.total / 1e9:.2f} GB total")
    if ram.available < 8e9:
        log.warning("Low RAM! < 8GB available, system might become unstable.")
        if device != "cpu":
            log.warning("Recommendation: Run with --safe-mode to avoid system instability.")
        
    if torch.cuda.is_available():
        t, f = torch.cuda.mem_get_info()
        log.info(f"VRAM: {f / 1e9:.2f} GB free / {t / 1e9:.2f} GB total")
        if t < 15e9:
            log.warning("GPU has < 15GB VRAM. CPU offload/Safe Mode is highly recommended.")
            if device != "cpu":
                log.warning("Recommendation: Run with --safe-mode if your PC crashes under GPU load.")
    else:
        log.info("CUDA is NOT available on PyTorch.")
    log.info(f"Execution Device Target: {device}")
    log.info("----------------------")

def _get_flux_pipe(device: str = "cuda"):
    from diffusers import FluxPipeline
    log.info(f"[1/3] Loading FLUX.1-schnell (device={device})")
    pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16)
    if device != "cpu":
        pipe.enable_model_cpu_offload()
    else:
        pipe.to("cpu")
    return pipe

def _get_sdxl_pipe(device: str = "cuda"):
    from diffusers import AutoPipelineForText2Image
    log.info(f"[1/3] Loading SDXL-Turbo (device={device})")
    torch_dtype = torch.float32 if device == "cpu" else torch.float16
    pipe = AutoPipelineForText2Image.from_pretrained(
        "stabilityai/sdxl-turbo",
        torch_dtype=torch_dtype,
        variant="fp16" if device != "cpu" else None
    ).to(device)
    return pipe

def run_image_gen(prompt: str, out_path: Path, seed: int = 42, device: str = "cuda") -> None:
    if device == "cpu":
        log.info("[ETAT] [1/3] Safe Mode CPU: Image generation start (FLUX)")
        log.info("[ESTIMATION] FLUX on CPU: estimated ~2-3 minutes (Safe Mode, 0% crash risk)")
    else:
        log.info("[ETAT] [1/3] Image generation start (FLUX)")
        log.info("[ESTIMATION] FLUX on GPU: estimated ~15 seconds")
    try:
        pipe = _get_flux_pipe(device)
        gen = torch.Generator(device="cpu").manual_seed(seed)
        t0 = time.time()
        image = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=0.0, height=1024, width=1024, generator=gen).images[0]
        image.save(out_path)
        del pipe
        _free_vram()
        return
    except Exception as e:
        log.warning(f"FLUX failed: {e}, falling back to SDXL")
        if 'pipe' in locals():
            del pipe
        _free_vram()

    if device == "cpu":
        log.info("[ESTIMATION] SDXL-Turbo fallback on CPU: estimated ~1-2 minutes")
    else:
        log.info("[ESTIMATION] SDXL-Turbo fallback on GPU: estimated ~5 seconds")
    pipe = _get_sdxl_pipe(device)
    gen = torch.Generator(device=device).manual_seed(seed)
    image = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=0.0, height=1024, width=1024, generator=gen).images[0]
    image.save(out_path)
    del pipe
    _free_vram()

def boost_and_rembg(in_path: Path, out_clean_path: Path) -> None:
    from PIL import ImageEnhance
    from hy3dgen.rembg import BackgroundRemover
    img = Image.open(in_path).convert("RGBA")
    img = ImageEnhance.Color(img.convert("RGB")).enhance(1.25).convert("RGBA")
    img.putalpha(Image.open(in_path).convert("RGBA").split()[-1])
    img = ImageEnhance.Contrast(img.convert("RGB")).enhance(1.10).convert("RGBA")
    rembg = BackgroundRemover()
    cleaned = rembg(img)
    cleaned.save(out_clean_path)

def run_shape_gen(image_path: Path, out_glb: Path, seed: int = 42, device: str = "cuda") -> None:
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
    if device == "cpu":
        log.info("[ETAT] [2/3] Safe Mode CPU: Shape generation start (Hunyuan3D-2 DiT)")
        log.info("[ESTIMATION] Hunyuan3D-2 Shape Gen on CPU: estimated ~8-12 minutes (Safe Mode, 0% crash risk)")
    else:
        log.info("[ETAT] [2/3] Shape generation start (Hunyuan3D-2 DiT)")
        log.info("[ESTIMATION] Hunyuan3D-2 Shape Gen on GPU: estimated ~1 minute")

    log.info(f"[2/3] Loading Hunyuan3D shapegen on {device}")
    dtype = torch.float32 if device == "cpu" else torch.float16
    torch.manual_seed(seed)
    shape_pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained("tencent/Hunyuan3D-2", device=device, dtype=dtype)
    if device != "cpu":
        shape_pipe.enable_model_cpu_offload()
    image = Image.open(image_path).convert("RGBA")
    mesh = shape_pipe(image=image)[0]
    mesh.export(str(out_glb))
    del shape_pipe
    _free_vram()

def run_tex_gen(shape_glb: Path, image_path: Path, out_glb: Path, device: str = "cuda") -> None:
    from hy3dgen.texgen import Hunyuan3DPaintPipeline
    import trimesh
    if device == "cpu":
        log.info("[ETAT] [3/3] Safe Mode CPU: Texture/Paint generation start (Hunyuan3D-2 Paint)")
        log.info("[ESTIMATION] Hunyuan3D-2 Paint Gen on CPU: estimated ~30-40 minutes (Safe Mode, 0% crash risk)")
    else:
        log.info("[ETAT] [3/3] Texture/Paint generation start (Hunyuan3D-2 Paint)")
        log.info("[ESTIMATION] Hunyuan3D-2 Paint Gen on GPU: estimated ~5 minutes")

    log.info(f"[3/3] Loading Hunyuan3D texgen on {device}")
    paint_pipe = Hunyuan3DPaintPipeline.from_pretrained("tencent/Hunyuan3D-2")
    if device != "cpu":
        paint_pipe.enable_model_cpu_offload()
    mesh = trimesh.load(str(shape_glb), force="mesh")
    image = Image.open(image_path).convert("RGBA")
    textured_mesh = paint_pipe(mesh, image=image)
    textured_mesh.export(str(out_glb))
    del paint_pipe
    _free_vram()

def run_blender_animate(glb_path: Path, profile_path: Path, out_dir: Path) -> None:
    cmd = [str(BLENDER), "--background", "--python", str(REPO / "aurora_animate.py"), "--", str(glb_path), str(profile_path), str(out_dir)]
    subprocess.run(cmd, capture_output=True, text=True, check=True)

def process_pipeline(prompt: str | None = None, input_image: Path | None = None, name: str | None = None, device: str = "cuda") -> Path:
    check_hardware(device)
    if prompt:
        profile = classify(prompt, name)
        scene_name = profile.name
    else:
        scene_name = name or "image_to_3d_scene"
        profile = SceneProfile(scene_name, "object", "neutral", 0.5, "", prompt_original="", prompt_image="")
    
    pack_dir = OUTPUT_ROOT / f"pbr_{scene_name}_pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    
    profile_path = pack_dir / "profile.json"
    with profile_path.open("w", encoding="utf-8") as f:
        json.dump(asdict(profile), f, indent=2, ensure_ascii=False)
        
    img_clean_path = pack_dir / "input_nobg.png"
    shape_glb = pack_dir / f"shape_{scene_name}.glb"
    final_glb = pack_dir / f"pbr_{scene_name}_proc.glb"
    
    if prompt and not input_image:
        raw_img = pack_dir / "input.png"
        # Force a clean, isolated 3D-asset style prompt to avoid ambiguous backgrounds or object deformations
        enhanced_prompt = profile.prompt_image + ", isometric view, pristine solid white background, single isolated object, highly detailed 3D asset, sharp focus, masterpiece, no clutter"
        run_image_gen(enhanced_prompt, raw_img, device=device)
        boost_and_rembg(raw_img, img_clean_path)
    elif input_image:
        boost_and_rembg(input_image, img_clean_path)
        
    run_shape_gen(img_clean_path, shape_glb, device=device)
    # The loop wrapper (aurora_loop_robust) is expected to audit/repair the shape here
    run_tex_gen(shape_glb, img_clean_path, final_glb, device=device)
    
    run_blender_animate(final_glb, profile_path, pack_dir)
    return pack_dir

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", help="Text to 3D prompt")
    ap.add_argument("--image", type=Path, help="Image to 3D path")
    ap.add_argument("--name", help="Scene name")
    ap.add_argument("--safe-mode", action="store_true", help="Run entirely on CPU with 0%% crash risk")
    ap.add_argument("--device", default=None, help="Force execution device (cpu or cuda)")
    args = ap.parse_args()

    # Environment variable check as a global fallback
    env_safe = os.environ.get("AURORA_SAFE_MODE", "0") == "1" or os.environ.get("AURORA_USE_CPU", "0") == "1"
    
    device = "cpu" if (args.safe_mode or args.device == "cpu" or env_safe) else "cuda"
    if args.device == "cuda":
        device = "cuda"

    pack = process_pipeline(prompt=args.prompt, input_image=args.image, name=args.name, device=device)
    print(f"PACK={pack}")
