"""Aurora texture rebake (B): color-grade a GLB's textures to match the
source image's saturation/contrast, persisting richer colors in the file.

Hunyuan3D-Paint averages multi-view samples and tends to flatten saturation
(steampunk_dragon was tan instead of brass; samurai was pink instead of gold).
This module reads the FLUX/SDXL input image, measures its mean saturation +
contrast, then applies a matching PIL enhancement to every base-color texture
in the GLB. Optionally also sharpens slightly. Writes a new GLB next to the
original.

Usage:
    python aurora_rebake.py <pack_dir>

Reads pack_dir/pbr_<name>_proc.glb + pack_dir/input.png,
writes pack_dir/pbr_<name>_proc_rebake.glb.
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageEnhance

log = logging.getLogger("rebake")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _rgb_to_lab(rgb_uint8: np.ndarray) -> np.ndarray:
    import cv2
    return cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2LAB).astype(np.float32)


def _lab_to_rgb(lab_f32: np.ndarray) -> np.ndarray:
    import cv2
    clipped = np.clip(lab_f32, 0, 255).astype(np.uint8)
    return cv2.cvtColor(clipped, cv2.COLOR_LAB2RGB)


def reinhard_color_transfer(target_rgb: np.ndarray, source_rgb: np.ndarray,
                              source_mask: np.ndarray | None = None,
                              mix: float = 0.85) -> np.ndarray:
    """Match target's LAB mean+std to source's, ignoring source background if
    a mask is supplied. `mix` blends transferred (1.0) vs original (0.0).
    Reinhard 2001, standard implementation. Operates on uint8 RGB arrays.
    """
    tgt = _rgb_to_lab(target_rgb)
    src = _rgb_to_lab(source_rgb)
    src_flat = src.reshape(-1, 3)
    if source_mask is not None:
        m = source_mask.reshape(-1) > 0
        src_flat = src_flat[m]
    s_mean = src_flat.mean(axis=0)
    s_std = src_flat.std(axis=0) + 1e-6
    t_mean = tgt.reshape(-1, 3).mean(axis=0)
    t_std = tgt.reshape(-1, 3).std(axis=0) + 1e-6
    transferred = (tgt - t_mean) * (s_std / t_std) + s_mean
    blended = mix * transferred + (1 - mix) * tgt
    return _lab_to_rgb(blended)


def enhance_image(tex_img: Image.Image, src_img: Image.Image) -> tuple[Image.Image, dict]:
    """Apply Reinhard LAB color transfer from src_img to tex_img, ignoring the
    background pixels of src_img (estimated from corners). Adds a small
    saturation kick + sharpness for the perceived 'crispness' Meshy-grade
    renders tend to have.
    """
    src_rgb = np.asarray(src_img.convert("RGB"))
    # Compute bg mask from source corners (already used in critic)
    h, w = src_rgb.shape[:2]
    corners = np.concatenate([
        src_rgb[:8, :8].reshape(-1, 3),
        src_rgb[:8, -8:].reshape(-1, 3),
        src_rgb[-8:, :8].reshape(-1, 3),
        src_rgb[-8:, -8:].reshape(-1, 3),
    ])
    bg_color = np.median(corners, axis=0)
    diff = np.abs(src_rgb.astype(np.int32) - bg_color.astype(np.int32)).sum(axis=-1)
    fg_mask = (diff > 40).astype(np.uint8) * 255

    tex_rgb = np.asarray(tex_img.convert("RGB"))
    transferred = reinhard_color_transfer(tex_rgb, src_rgb, source_mask=fg_mask, mix=0.85)
    transferred_pil = Image.fromarray(transferred)
    transferred_pil = ImageEnhance.Color(transferred_pil).enhance(1.10)
    transferred_pil = ImageEnhance.Sharpness(transferred_pil).enhance(1.35)

    if tex_img.mode == "RGBA":
        rgba_split = tex_img.split()
        out = Image.merge("RGBA", (*transferred_pil.split(), rgba_split[-1]))
    else:
        out = transferred_pil.convert("RGBA")
    return out, {"bg_color": bg_color.tolist(), "fg_pixels": int(fg_mask.sum() / 255)}


def rebake(pack_dir: Path) -> dict:
    glb_files = list(pack_dir.glob("pbr_*_proc.glb"))
    if not glb_files:
        raise FileNotFoundError(f"no pbr_*_proc.glb found in {pack_dir}")
    glb_in = glb_files[0]
    input_png = pack_dir / "input.png"
    if not input_png.exists():
        raise FileNotFoundError(f"no input.png in {pack_dir}")
    glb_out = glb_in.with_name(glb_in.stem + "_rebake.glb")

    src_img = Image.open(input_png).convert("RGB")

    scene = trimesh.load(str(glb_in), force=None)
    if isinstance(scene, trimesh.Scene):
        geometries = list(scene.geometry.values())
    else:
        geometries = [scene]

    n_textures = 0
    summary = {"textures_modified": 0, "geometries": len(geometries), "details": []}
    for geo in geometries:
        visual = getattr(geo, "visual", None)
        if visual is None or not hasattr(visual, "material"):
            continue
        mat = visual.material
        if hasattr(mat, "baseColorTexture") and mat.baseColorTexture is not None:
            tex = mat.baseColorTexture
            if isinstance(tex, Image.Image):
                log.info(f"transferring colors source -> texture (size {tex.size})")
                enhanced, info = enhance_image(tex, src_img)
                summary["details"].append(info)
                mat.baseColorTexture = enhanced
                n_textures += 1
    summary["textures_modified"] = n_textures

    if isinstance(scene, trimesh.Scene):
        scene.export(str(glb_out))
    else:
        scene.export(str(glb_out))
    log.info(f"wrote {glb_out} ({glb_out.stat().st_size / 1e6:.2f} MB), {n_textures} textures modified")
    (pack_dir / "rebake_meta.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pack", type=Path)
    args = ap.parse_args()
    summary = rebake(args.pack)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
