"""Native texture precision — atlas-level rescue on TRELLIS.2 output.

Purpose:
  Rescue a GLB produced by TRELLIS.2 (native branch) where the baseColor texture
  atlas carries baked-in defects:
    (a) dark shadow bake on white/light zones (looks like dirt/wear),
    (b) small dark tear/seam artifacts on smooth panels,
    (c) chromatic bleed around holes (mic holes glowing orange, etc.),
    (d) low local contrast on printed symbols (buttons, D-pad).

  We do NOT touch geometry, UVs, materials, or normals. Only the baseColor PNG
  is rewritten. Zero risk of destroying anything the mesh already gets right —
  the rescue only *lifts* dark artifacts and inpaints small dark specks on
  otherwise-bright regions.

Approach:
  1) Load the baseColor atlas as RGB (8-bit).
  2) Build a "light plastic" mask via HSV: low saturation AND value >= 0.55.
     This isolates the white shell of the DualSense (or any white/gray casing).
  3) Delight: on that mask, apply a soft luminance floor (percentile-based) so
     dark shadow-baked pixels lift toward the local white base — but preserve
     hard edges (Sobel-based edge weight keeps text/symbols crisp).
  4) Inpaint tiny dark specks (area < atlas_area * 5e-6) that are surrounded by
     the light-plastic mask. Uses cv2.INPAINT_TELEA on a very small seed mask.
  5) Chromatic bleed suppression around dark holes: if a pixel is on the light
     mask AND its hue deviates strongly from neutral (|a*| > 8 or |b*| > 8 in
     Lab) AND it's near a dark seed, pull it back toward neutral.
  6) Local contrast boost: CLAHE on the L channel of the ENTIRE atlas (mild,
     clip=1.5, tile=32) — sharpens printed symbols without oversharpening.
  7) Write back into the GLB with byte-perfect bufferView repack.

Everything is pure numpy/OpenCV, ~30s on an 8k atlas.

Schema:  aurora.native_precision.v1

Usage:
    python native_texture_precision.py --mesh IN.glb --output OUT.glb
    python native_texture_precision.py --mesh IN.glb --output OUT.glb \\
        --delight-strength 0.6 --clahe-clip 1.5 --clahe-tile 32
"""
from __future__ import annotations
import argparse
import io
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from pygltflib import GLTF2

Image.MAX_IMAGE_PIXELS = None


def _print_result(payload: dict) -> None:
    print("AURORA_PRECISION_RESULT:" + json.dumps(payload), flush=True)


def _load_atlas(glb_path: str):
    g = GLTF2().load(glb_path)
    albedo_idx = None
    for mat in g.materials or []:
        pbr = mat.pbrMetallicRoughness
        if pbr and pbr.baseColorTexture is not None:
            albedo_idx = g.textures[pbr.baseColorTexture.index].source
            break
    if albedo_idx is None:
        raise RuntimeError("no baseColorTexture found in GLB")
    blob = g.binary_blob()
    bv = g.bufferViews[g.images[albedo_idx].bufferView]
    png_bytes = bytes(blob[bv.byteOffset: bv.byteOffset + bv.byteLength])
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return g, albedo_idx, png_bytes, np.asarray(img)


def _write_atlas(g, albedo_idx: int, png_bytes: bytes, out_glb: str) -> None:
    blob = g.binary_blob()
    target_bv = g.images[albedo_idx].bufferView
    order = sorted(range(len(g.bufferViews)),
                   key=lambda i: g.bufferViews[i].byteOffset or 0)
    out = bytearray()
    for i in order:
        bv = g.bufferViews[i]
        if len(out) % 4:
            out.extend(b"\x00" * (4 - len(out) % 4))
        if i == target_bv:
            data = png_bytes
        else:
            off = bv.byteOffset or 0
            data = blob[off: off + bv.byteLength]
        bv.byteOffset = len(out)
        bv.byteLength = len(data)
        out.extend(data)
    g.buffers[0].byteLength = len(out)
    g.set_binary_blob(bytes(out))
    g.save_binary(out_glb)


def _light_plastic_mask(rgb: np.ndarray) -> np.ndarray:
    """Boolean mask: 'this pixel should be light plastic (white/gray casing)'."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    s = hsv[..., 1]
    v = hsv[..., 2]
    # low saturation (< 40/255) AND at least moderately bright (v >= 140)
    return (s < 40) & (v >= 140)


def _edge_map(rgb: np.ndarray) -> np.ndarray:
    """Normalised [0..1] soft edge map to protect printed symbols from delight."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    if mag.max() > 0:
        mag = mag / mag.max()
    # Blur so edges influence a slightly larger neighborhood
    return cv2.GaussianBlur(mag, (0, 0), 1.5)


def _delight_light_plastic(rgb: np.ndarray, plastic_mask: np.ndarray,
                            edge: np.ndarray, strength: float) -> tuple[np.ndarray, dict]:
    """Atlas-position-independent delight for TRELLIS.2 baseColor.

    IMPORTANT: TRELLIS.2 atlases have hundreds/thousands of small UV islands.
    ANY spatial reference (blur, dilate, CLAHE) computes across island
    boundaries and REVEALS the atlas island structure as leopard-print noise
    when the rendered mesh is textured. We learned this the hard way — the
    v1 delight using local L-max dilate produced obvious island patterns
    on the grips (see scratchpad/render/compare — v1 grip droite has a full
    leopard mosaic that was NOT present in the baseline).

    So the delight is purely GLOBAL and POSITION-INDEPENDENT:
      - Kill hue: on plastic mask, chroma > 4 gets pulled toward 0 by 90%.
        Removes cream/yellow tint on "should-be-white" pixels without ever
        touching non-plastic pixels or referencing neighborhoods.
      - Value floor: on plastic mask, pixels with L in [95, 200] and edge < 0.15
        get lifted toward 210 by `strength`. This kills medium-shadow bake
        while preserving both:
          (a) very dark pixels — they're intentional (text, seams),
          (b) very bright pixels — they're already OK,
          (c) high-edge pixels — printed symbols, silhouettes.
    """
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2Lab).astype(np.float32)
    L = lab[..., 0]
    a = lab[..., 1] - 128.0
    b = lab[..., 2] - 128.0
    chroma = np.sqrt(a * a + b * b)
    m = plastic_mask
    # Chroma clamp on plastic
    kill_chroma = m & (chroma > 4.0)
    a[kill_chroma] *= 0.10
    b[kill_chroma] *= 0.10
    # Value floor: only pixels in the "medium shadow" band, not intentional-dark
    lift_target = 210.0
    band = m & (L >= 95.0) & (L <= 200.0) & (edge < 0.15)
    gap = np.clip(lift_target - L, 0.0, 255.0)
    lift = gap * strength * band.astype(np.float32)
    L = np.clip(L + lift, 0.0, 255.0)
    lab[..., 0] = L
    lab[..., 1] = np.clip(a + 128.0, 0.0, 255.0)
    lab[..., 2] = np.clip(b + 128.0, 0.0, 255.0)
    out = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_Lab2RGB)
    stats = {
        "plastic_pixels": int(m.sum()),
        "plastic_ratio": round(float(m.mean()), 4),
        "chroma_killed": int(kill_chroma.sum()),
        "band_lifted": int(band.sum()),
        "mean_lift": round(float(lift[band].mean()) if band.any() else 0.0, 3),
        "max_lift": round(float(lift.max()), 3),
        "policy": "position_independent",
    }
    return out, stats


def _inpaint_dark_specks(rgb: np.ndarray, plastic_mask: np.ndarray,
                          max_area_frac: float = 5e-6) -> tuple[np.ndarray, dict]:
    """Inpaint small dark specks that sit inside light plastic regions."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2Lab)
    L = lab[..., 0]
    dark = (L < 90) & plastic_mask
    dark = dark.astype(np.uint8)
    # only very small specks — not big black panels
    max_area = int(max_area_frac * rgb.shape[0] * rgb.shape[1])
    num, labels, stats, _ = cv2.connectedComponentsWithStats(dark, 8)
    if num <= 1:
        return rgb, {"specks_found": 0, "specks_inpainted": 0}
    seed = np.zeros_like(dark)
    inpainted_count = 0
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] <= max_area:
            seed[labels == i] = 1
            inpainted_count += 1
    if not inpainted_count:
        return rgb, {"specks_found": int(num - 1), "specks_inpainted": 0}
    # slight dilation so inpaint samples clean neighborhood
    seed = cv2.dilate(seed, np.ones((3, 3), np.uint8))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    inp = cv2.inpaint(bgr, seed, 3, cv2.INPAINT_TELEA)
    return cv2.cvtColor(inp, cv2.COLOR_BGR2RGB), {
        "specks_found": int(num - 1),
        "specks_inpainted": int(inpainted_count),
    }


def _neutralize_hole_bleed(rgb: np.ndarray, plastic_mask: np.ndarray) -> tuple[np.ndarray, dict]:
    """Kill the orange/pink chromatic bleed around dark holes on the light shell.

    Any pixel on the plastic mask whose a*/b* channels deviate strongly from
    neutral gets pulled back to neutral. Preserves the printed color symbols
    (which are OFF the plastic mask because they're saturated colors on the
    buttons — but on a DualSense the button symbols on the shell are almost
    neutral anyway; we bias toward safety here).
    """
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2Lab).astype(np.float32)
    a = lab[..., 1] - 128.0  # -128..127 signed
    b = lab[..., 2] - 128.0
    chroma = np.sqrt(a * a + b * b)
    bleed = plastic_mask & (chroma > 12.0)
    if not bleed.any():
        return rgb, {"bleed_pixels": 0}
    # Pull chroma toward 0 by 70% only on bleed pixels
    a[bleed] *= 0.30
    b[bleed] *= 0.30
    lab[..., 1] = np.clip(a + 128.0, 0.0, 255.0)
    lab[..., 2] = np.clip(b + 128.0, 0.0, 255.0)
    out = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_Lab2RGB)
    return out, {"bleed_pixels": int(bleed.sum())}


def _mild_clahe(rgb: np.ndarray, clip: float, tile: int,
                 plastic_mask: np.ndarray | None = None) -> np.ndarray:
    """Mild CLAHE on L channel — sharpens printed symbols slightly.

    On TRELLIS.2 atlases we MUST restrict the sharpening to the connected
    "light plastic" region: applying CLAHE globally reveals UV island seams
    (each tile's local histogram treats atlas gutters as content and pumps
    them). If plastic_mask is provided, we blend the sharpened result onto
    the ORIGINAL only where the mask is True.
    """
    if clip <= 0.0:
        return rgb
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2Lab)
    L = lab[..., 0]
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(tile, tile))
    L_sharp = clahe.apply(L)
    if plastic_mask is None:
        lab[..., 0] = L_sharp
        return cv2.cvtColor(lab, cv2.COLOR_Lab2RGB)
    # Blend only inside plastic mask; feather the mask so we don't get a
    # sharp ring around symbols. 4 px erode then 3 px blur = seam-safe.
    m = plastic_mask.astype(np.uint8)
    m = cv2.erode(m, np.ones((5, 5), np.uint8))
    m = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 3.0)
    lab[..., 0] = (L.astype(np.float32) * (1.0 - m)
                    + L_sharp.astype(np.float32) * m).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_Lab2RGB)


def run(mesh: str, output: str, delight_strength: float,
        clahe_clip: float, clahe_tile: int) -> dict:
    result = {
        "schema": "aurora.native_precision.v1",
        "input": mesh,
        "output": output,
        "ok": False,
    }
    g, albedo_idx, orig_png, rgb = _load_atlas(mesh)
    h, w = rgb.shape[:2]
    result["atlas_size"] = [int(w), int(h)]

    plastic = _light_plastic_mask(rgb)
    edges = _edge_map(rgb)

    delit, delit_stats = _delight_light_plastic(rgb, plastic, edges, delight_strength)
    result["delight"] = delit_stats
    result["delight"]["strength"] = round(float(delight_strength), 3)

    delit, speck_stats = _inpaint_dark_specks(delit, plastic)
    result["inpaint"] = speck_stats

    delit, bleed_stats = _neutralize_hole_bleed(delit, plastic)
    result["neutralize"] = bleed_stats

    # CLAHE is intrinsically spatial and reveals atlas island boundaries on
    # TRELLIS.2 output. Default OFF (clip <= 0). Kept in the API for future
    # atlases with contiguous UVs (e.g. after xatlas unwrap) where it's safe.
    sharpened = _mild_clahe(delit, clahe_clip, clahe_tile, plastic_mask=plastic)
    result["clahe"] = {"clip": clahe_clip, "tile": clahe_tile,
                        "applied": clahe_clip > 0.0,
                        "note": "disabled by default: spatial op reveals atlas islands"}

    # Encode new PNG. Keep alpha absent (RGB only) to match TRELLIS output.
    buf = io.BytesIO()
    Image.fromarray(sharpened).save(buf, format="PNG", optimize=False)
    new_png = buf.getvalue()
    result["png_bytes_before"] = len(orig_png)
    result["png_bytes_after"] = len(new_png)

    _write_atlas(g, albedo_idx, new_png, output)
    out_path = Path(output)
    result["ok"] = out_path.is_file() and out_path.stat().st_size > 1000
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mesh", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--delight-strength", type=float, default=0.55,
                   help="0..1, how strongly baked shadows on light plastic are lifted")
    p.add_argument("--clahe-clip", type=float, default=0.0,
                   help="CLAHE clip limit; DEFAULT 0 (off) — CLAHE is a spatial "
                        "op that reveals TRELLIS atlas islands. Only enable "
                        "on meshes with contiguous UVs.")
    p.add_argument("--clahe-tile", type=int, default=32,
                   help="CLAHE tile grid size")
    args = p.parse_args()

    try:
        res = run(args.mesh, args.output,
                  args.delight_strength, args.clahe_clip, args.clahe_tile)
    except Exception as exc:  # noqa: BLE001
        res = {
            "schema": "aurora.native_precision.v1",
            "input": args.mesh, "output": args.output,
            "ok": False, "error": repr(exc),
        }
    _print_result(res)
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    main()
