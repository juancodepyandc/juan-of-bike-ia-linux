"""AuroraIA Hunyuan3D realistic pipeline (single scene).

text prompt -> classified profile -> SDXL-Turbo image -> rembg -> Hunyuan3D shape+paint GLB
            -> Blender adaptive animator -> output pack in AuroraIA-v2/application/output/3d/

Run:
    python pipeline_hunyuan_realistic.py "a glowing crystal lantern in fog at night" lantern_fog

VRAM mgmt: each model stage loads, runs, unloads (del + torch.cuda.empty_cache).
Models exceed 16 GB combined so cohabitation is impossible on the 5070 Ti.
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
import torch
from PIL import Image

from aurora_classify import SceneProfile, classify

REPO = Path(__file__).resolve().parent
AURORA = Path(r"C:\Users\Juan\Desktop\ia\AuroraIA-v2")
BLENDER = AURORA / "application" / "_blender" / "blender-4.2.12-windows-x64" / "blender.exe"
OUTPUT_ROOT = AURORA / "application" / "output" / "3d"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("aurora")


def _free_vram() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


# Module-level cache so multi-scene loops do not reload FLUX (24 GB on CPU)
# between every scene. Hunyuan3D pipes still load/free per call because they
# live entirely in VRAM and must stay there exclusively.
_FLUX_PIPE = None
_SDXL_PIPE = None


def _get_flux_pipe(device: str = "cuda"):
    global _FLUX_PIPE
    if _FLUX_PIPE is not None:
        return _FLUX_PIPE
    from diffusers import FluxPipeline
    log.info(f"[1/3] Loading FLUX.1-schnell into module cache (device={device})")
    pipe = FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-schnell",
        torch_dtype=torch.bfloat16,
    )
    if device != "cpu":
        pipe.enable_model_cpu_offload()
    else:
        pipe.to("cpu")
    pipe.set_progress_bar_config(disable=True)
    _FLUX_PIPE = pipe
    return pipe


def _get_sdxl_pipe(device: str = "cuda"):
    global _SDXL_PIPE
    if _SDXL_PIPE is not None:
        return _SDXL_PIPE
    from diffusers import AutoPipelineForText2Image
    log.info(f"[1/3] Loading SDXL-Turbo into module cache (device={device})")
    torch_dtype = torch.float32 if device == "cpu" else torch.float16
    pipe = AutoPipelineForText2Image.from_pretrained(
        "stabilityai/sdxl-turbo",
        torch_dtype=torch_dtype,
        variant="fp16" if device != "cpu" else None,
    ).to(device)
    pipe.set_progress_bar_config(disable=True)
    _SDXL_PIPE = pipe
    return pipe


def generate_image(prompt: str, out_path: Path, seed: int = 42, device: str = "cuda") -> None:
    """FLUX.1-schnell with CPU offload, SDXL-Turbo fallback. Both pipes are
    cached at module level so a multi-scene loop reuses them across scenes
    instead of re-allocating 24 GB of FLUX weights per iteration.
    """
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
        image = pipe(
            prompt=prompt,
            num_inference_steps=4,
            guidance_scale=0.0,
            height=1024,
            width=1024,
            max_sequence_length=256,
            generator=gen,
        ).images[0]
        if device != "cpu" and torch.cuda.is_available():
            log.info(f"[1/3] FLUX image done in {time.time() - t0:.1f}s, "
                     f"free VRAM {torch.cuda.mem_get_info()[0] / 1e9:.2f} GB")
        else:
            log.info(f"[1/3] FLUX image done in {time.time() - t0:.1f}s (CPU)")
        image.save(out_path)
        _free_vram()
        return
    except (RuntimeError, ImportError, OSError, MemoryError) as e:
        log.warning(f"[1/3] FLUX failed ({type(e).__name__}: {str(e)[:200]}), "
                    f"falling back to SDXL-Turbo")
        global _FLUX_PIPE
        _FLUX_PIPE = None
        _free_vram()

    if device == "cpu":
        log.info("[ESTIMATION] SDXL-Turbo fallback on CPU: estimated ~1-2 minutes")
    else:
        log.info("[ESTIMATION] SDXL-Turbo fallback on GPU: estimated ~5 seconds")
    pipe = _get_sdxl_pipe(device)
    gen = torch.Generator(device=device).manual_seed(seed)
    log.info(f"[1/3] SDXL-Turbo generating (4 steps) on {device}")
    t0 = time.time()
    image = pipe(
        prompt=prompt,
        num_inference_steps=4,
        guidance_scale=0.0,
        height=1024,
        width=1024,
        generator=gen,
    ).images[0]
    if device != "cpu" and torch.cuda.is_available():
        log.info(f"[1/3] SDXL-Turbo done in {time.time() - t0:.1f}s, "
                  f"free VRAM {torch.cuda.mem_get_info()[0] / 1e9:.2f} GB")
    else:
        log.info(f"[1/3] SDXL-Turbo done in {time.time() - t0:.1f}s (CPU)")
    image.save(out_path)
    _free_vram()


def boost_saturation(in_path: Path, out_path: Path, sat_factor: float = 1.25,
                       contrast_factor: float = 1.10) -> None:
    """Slightly saturate + contrast-boost before Hunyuan3D so PBR paint keeps
    richer per-region colors. Conservative factors to avoid posterisation.
    """
    from PIL import ImageEnhance
    img = Image.open(in_path).convert("RGBA")
    img = ImageEnhance.Color(img.convert("RGB")).enhance(sat_factor).convert("RGBA")
    img.putalpha(Image.open(in_path).convert("RGBA").split()[-1])
    img = ImageEnhance.Contrast(img.convert("RGB")).enhance(contrast_factor).convert("RGBA")
    img.save(out_path)


def remove_background(in_path: Path, out_path: Path) -> None:
    from hy3dgen.rembg import BackgroundRemover
    img = Image.open(in_path).convert("RGBA")
    rembg = BackgroundRemover()
    cleaned = rembg(img)
    cleaned.save(out_path)


def _drop_tiny_components(mesh, min_face_ratio: float = 0.01):
    """Keep only the largest connected component if a mesh has been blown up
    by decimation into thousands of tiny floaters. Returns the cleaned mesh
    and the count of components dropped.
    """
    import trimesh as tm
    components = mesh.split(only_watertight=False)
    if len(components) <= 1:
        return mesh, 0
    main = max(components, key=lambda c: len(c.faces))
    main_n = len(main.faces)
    keep = [c for c in components if len(c.faces) >= main_n * min_face_ratio]
    if len(keep) == len(components):
        return mesh, 0
    cleaned = tm.util.concatenate(keep) if len(keep) > 1 else keep[0]
    cleaned.visual = mesh.visual
    return cleaned, len(components) - len(keep)


def decimate_mesh(mesh, target_faces: int) -> tuple:
    """Quadric edge-collapse decimation toward target_faces, with post-cleanup
    to drop tiny floaters that pymeshlab's decimation sometimes creates.
    Falls back to pymeshlab if trimesh's fast_simplification path is missing.
    Returns (mesh, was_decimated).
    """
    current = len(mesh.faces)
    if current <= target_faces * 1.1:
        return mesh, False
    out_mesh = None
    try:
        decimated = mesh.simplify_quadric_decimation(target_faces)
        if decimated is not None and len(decimated.faces) > 0:
            out_mesh = decimated
    except Exception as e:
        log.warning(f"trimesh decimation failed: {e}")
    if out_mesh is None:
        try:
            import pymeshlab
            import trimesh as tm
            ms = pymeshlab.MeshSet()
            ms.add_mesh(pymeshlab.Mesh(
                vertex_matrix=np.asarray(mesh.vertices),
                face_matrix=np.asarray(mesh.faces),
            ))
            ms.meshing_decimation_quadric_edge_collapse(
                targetfacenum=target_faces,
                preserveboundary=True,
                preservenormal=True,
                preservetopology=True,
                optimalplacement=True,
                planarquadric=True,
                qualitythr=0.4,
            )
            m2 = ms.current_mesh()
            out_mesh = tm.Trimesh(
                vertices=m2.vertex_matrix(),
                faces=m2.face_matrix(),
                process=False,
                visual=mesh.visual,
            )
        except Exception as e:
            log.warning(f"pymeshlab decimation failed: {e}; keeping original")
            return mesh, False
    out_mesh, dropped = _drop_tiny_components(out_mesh, min_face_ratio=0.005)
    if dropped > 0:
        log.info(f"  cleaned: dropped {dropped} tiny components")
    return out_mesh, True


def _decimation_target(profile: dict) -> int:
    """Per-category face budget. Mechanical/architecture get more, simple objects less."""
    cat = profile.get("category", "object")
    return {
        "character": 180_000,
        "creature": 180_000,
        "vehicle": 220_000,
        "mechanical": 260_000,
        "architecture": 240_000,
        "nature": 150_000,
        "object": 140_000,
        "scenery_landscape": 220_000,
    }.get(cat, 160_000)


def generate_mesh(image_path: Path, glb_path: Path, model_path: str = "tencent/Hunyuan3D-2",
                    paint_subfolder: str = "hunyuan3d-paint-v2-0",
                    decimate_target: int | None = None, device: str = "cuda") -> dict:
    """Hunyuan3D shape + paint. Uses NON-turbo paint variant for richer textures.
    Each stage loads / runs / frees so a 16 GB GPU can host the whole flow.
    """
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    if device == "cpu":
        log.info("[ETAT] [2/3] Safe Mode CPU: Shape generation start (Hunyuan3D-2 DiT)")
        log.info("[ESTIMATION] Hunyuan3D-2 Shape Gen on CPU: estimated ~8-12 minutes (Safe Mode, 0% crash risk)")
    else:
        log.info("[ETAT] [2/3] Shape generation start (Hunyuan3D-2 DiT)")
        log.info("[ESTIMATION] Hunyuan3D-2 Shape Gen on GPU: estimated ~1 minute")

    log.info(f"[2/3] Loading Hunyuan3D shapegen on {device}")
    dtype = torch.float32 if device == "cpu" else torch.float16
    shape_pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(model_path, device=device, dtype=dtype)
    if device != "cpu":
        shape_pipe.enable_model_cpu_offload()
    t0 = time.time()
    image = Image.open(image_path).convert("RGBA")
    mesh = shape_pipe(image=image, octree_resolution=512)[0]
    shape_t = time.time() - t0
    raw_faces = len(mesh.faces)
    log.info(f"[2/3] Shape done in {shape_t:.1f}s verts={len(mesh.vertices)} faces={raw_faces}")
    del shape_pipe
    _free_vram()

    decim_t = 0.0
    decimated = False
    if decimate_target is not None and decimate_target > 0:
        t_dec = time.time()
        log.info(f"[2/3] Decimating mesh to ~{decimate_target} faces")
        mesh, decimated = decimate_mesh(mesh, decimate_target)
        decim_t = time.time() - t_dec
        log.info(f"[2/3] Decimation done in {decim_t:.1f}s faces={len(mesh.faces)} (was {raw_faces})")

    from hy3dgen.texgen import Hunyuan3DPaintPipeline

    if device == "cpu":
        log.info("[ETAT] [2/3] Safe Mode CPU: Texture/Paint generation start (Hunyuan3D-2 Paint)")
        log.info("[ESTIMATION] Hunyuan3D-2 Paint Gen on CPU: estimated ~30-40 minutes (Safe Mode, 0% crash risk)")
    else:
        log.info("[ETAT] [2/3] Texture/Paint generation start (Hunyuan3D-2 Paint)")
        log.info("[ESTIMATION] Hunyuan3D-2 Paint Gen on GPU: estimated ~5 minutes")

    log.info(f"[2/3] Loading Hunyuan3D texgen on {device} (subfolder={paint_subfolder})")
    try:
        paint_pipe = Hunyuan3DPaintPipeline.from_pretrained(model_path)
    except TypeError as e:
        log.warning(f"[2/3] paint pipeline init failed ({e}); retrying without specific options")
        paint_pipe = Hunyuan3DPaintPipeline.from_pretrained(model_path)

    if device != "cpu":
        paint_pipe.enable_model_cpu_offload()

    paint_pipe.config.render_size = 4096
    paint_pipe.config.texture_size = 4096

    t1 = time.time()
    mesh = paint_pipe(mesh, image=image)
    paint_t = time.time() - t1
    log.info(f"[2/3] Texture done in {paint_t:.1f}s")
    del paint_pipe
    _free_vram()

    mesh.export(str(glb_path))
    log.info(f"[2/3] Exported {glb_path} ({glb_path.stat().st_size / 1e6:.2f} MB)")
    return {
        "verts": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "raw_faces": int(raw_faces),
        "decimated": bool(decimated),
        "shape_s": round(shape_t, 1),
        "decim_s": round(decim_t, 1),
        "paint_s": round(paint_t, 1),
        "glb_mb": round(glb_path.stat().st_size / 1e6, 2),
        "paint_variant": paint_subfolder,
    }


def run_blender_animate(glb_path: Path, profile_path: Path, out_dir: Path) -> None:
    if not BLENDER.exists():
        raise FileNotFoundError(f"blender not found at {BLENDER}")
    cmd = [
        str(BLENDER), "--background", "--python", str(REPO / "aurora_animate.py"),
        "--", str(glb_path), str(profile_path), str(out_dir),
    ]
    log.info(f"[3/3] Blender animate -> {out_dir}")
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    log.info(f"[3/3] Blender done in {time.time() - t0:.1f}s rc={res.returncode}")
    if res.returncode != 0:
        log.error(f"[3/3] Blender stderr (tail):\n{res.stderr[-2000:]}")
        raise RuntimeError(f"blender failed rc={res.returncode}")
    log.info(f"[3/3] Blender stdout (tail):\n{res.stdout[-1500:]}")


def check_hardware(device: str = "cuda") -> None:
    log.info("--- Hardware Check ---")
    import psutil
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


def run_one(prompt: str, name: str | None = None, device: str = "cuda") -> Path:
    check_hardware(device)
    profile = classify(prompt, name)
    log.info(f"Classified: name={profile.name} category={profile.category} mood={profile.mood} "
             f"animations={[a['type'] for a in profile.animations]} confidence={profile.confidence}")

    pack_dir = OUTPUT_ROOT / f"pbr_{profile.name}_pack"
    pack_dir.mkdir(parents=True, exist_ok=True)

    profile_path = pack_dir / "profile.json"
    with profile_path.open("w", encoding="utf-8") as f:
        json.dump(asdict(profile), f, indent=2, ensure_ascii=False)

    img_path = pack_dir / "input.png"
    img_clean_path = pack_dir / "input_nobg.png"
    glb_path = pack_dir / f"pbr_{profile.name}_proc.glb"
    mesh_meta_path = pack_dir / "mesh_meta.json"

    img_boosted_path = pack_dir / "input_boosted.png"

    if not img_path.exists():
        enhanced_prompt = profile.prompt_image + ", isometric view, pristine solid white background, single isolated object, highly detailed 3D asset, sharp focus, masterpiece, no clutter"
        generate_image(enhanced_prompt, img_path, device=device)
    else:
        log.info(f"[1/3] Skipping img gen, exists: {img_path}")

    if not img_boosted_path.exists():
        boost_saturation(img_path, img_boosted_path)
        log.info(f"[1/3] Saturation+contrast boosted -> {img_boosted_path}")

    if not img_clean_path.exists():
        remove_background(img_boosted_path, img_clean_path)

    if not glb_path.exists():
        target_faces = _decimation_target(asdict(profile))
        mesh_meta = generate_mesh(img_clean_path, glb_path, decimate_target=target_faces, device=device)
        with mesh_meta_path.open("w", encoding="utf-8") as f:
            json.dump(mesh_meta, f, indent=2)
    else:
        log.info(f"[2/3] Skipping mesh gen, exists: {glb_path}")

    run_blender_animate(glb_path, profile_path, pack_dir)

    log.info(f"=== [done] pack at {pack_dir} ===")
    log.info("OUTPUTS:")
    for item in sorted(pack_dir.iterdir()):
        if item.is_file():
            size_mb = item.stat().st_size / 1e6
            log.info(f"  {item}  ({size_mb:.2f} MB)")
    return pack_dir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", help="free-form scene prompt")
    ap.add_argument("name", nargs="?", default=None, help="optional slug; default derived from prompt")
    ap.add_argument("--safe-mode", action="store_true", help="Run entirely on CPU with 0%% crash risk")
    ap.add_argument("--device", default=None, help="Force execution device (cpu or cuda)")
    args = ap.parse_args()

    # Environment variable check as a global fallback
    env_safe = os.environ.get("AURORA_SAFE_MODE", "0") == "1" or os.environ.get("AURORA_USE_CPU", "0") == "1"
    
    device = "cpu" if (args.safe_mode or args.device == "cpu" or env_safe) else "cuda"
    if args.device == "cuda":
        device = "cuda"

    try:
        pack = run_one(args.prompt, args.name, device=device)
        print(f"PACK={pack}")
        return 0
    except Exception as e:
        log.exception("pipeline failed")
        print(f"FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
