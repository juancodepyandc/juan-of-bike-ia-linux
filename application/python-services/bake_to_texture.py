#!/usr/bin/env python
"""Aurora — bake per-vertex colors into a real UV-mapped texture.

bake_vertex_colors.py stores colors in the GLB's per-vertex COLOR_0
attribute. mesh_visual_audit reports such files as visual_grade ≤ 20
because there's no UV map, no material, no texture, no PBR. A viewer
with vertex-color support still renders something but loses every
PBR-ready slot (roughness, normal, ambient occlusion, …).

This module generates a proper texture-mapped GLB:
  1. xatlas unwrap → per-vertex UV0 atlas (charts packed into [0,1]²)
  2. Rasterize each triangle into the atlas image:
       for each pixel inside the projected UV triangle:
           barycentric interp the 3 vertex colors → pixel RGB
  3. Write atlas as PNG, embed in GLB as image + texture + material
  4. Output GLB now has: meshes=1, materials=1, textures=1, images=1,
     COLOR_0 dropped, TEXCOORD_0 added, baseColorTexture set.

Schema: aurora.bake_to_texture.v1.

Usage:
    python bake_to_texture.py --input mesh_baked.glb \\
        --output mesh_textured.glb --atlas-size 1024 --pretty
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


def _emit_glb(gltf: dict, bin_blob: bytes, output_path: Path) -> int:
    new_json = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - (len(new_json) % 4)) % 4
    new_json_padded = new_json + (b" " * json_pad)
    bin_pad = (4 - (len(bin_blob) % 4)) % 4
    new_bin_padded = bin_blob + (b"\x00" * bin_pad)
    total = 12 + 8 + len(new_json_padded) + 8 + len(new_bin_padded)
    out = bytearray()
    out += b"glTF"
    out += struct.pack("<II", 2, total)
    out += struct.pack("<II", len(new_json_padded), 0x4E4F534A)
    out += new_json_padded
    out += struct.pack("<II", len(new_bin_padded), 0x004E4942)
    out += new_bin_padded
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(out))
    return total


def bake(input_path: Path, output_path: Path,
         atlas_size: int = 1024) -> dict:
    """Generate a UV-mapped textured GLB from a vertex-colored input.
    Returns a report dict; never raises."""
    if not input_path.is_file():
        return {"ok": False, "error": f"input not found: {input_path}"}
    try:
        import trimesh
        import numpy as np
        import xatlas
        from PIL import Image
    except ImportError as exc:
        return {"ok": False, "error": f"missing dep: {exc}"}

    try:
        mesh = trimesh.load(input_path, force="mesh")
    except Exception as exc:
        return {"ok": False, "error": f"load failed: {exc}"}

    verts = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.uint32)
    if verts.size == 0 or faces.size == 0:
        return {"ok": False, "error": "empty mesh"}

    # Per-vertex RGBA from the visual layer; fall back to neutral grey if missing
    if hasattr(mesh.visual, "vertex_colors") and mesh.visual.vertex_colors is not None:
        vcol = np.asarray(mesh.visual.vertex_colors, dtype=np.uint8)
        if vcol.shape[1] == 4:
            vcol = vcol[:, :3]
    else:
        vcol = np.full((len(verts), 3), 200, dtype=np.uint8)

    # Step 1 — xatlas UV unwrap. xatlas may return more vertices than input
    # (charts split shared vertices). It produces a remap (vmap) and per-face
    # vertex indices in the new domain.
    try:
        vmap, indices_atlas, uvs = xatlas.parametrize(verts, faces)
    except Exception as exc:
        return {"ok": False, "error": f"xatlas failed: {exc}"}

    # Step 2 — rasterize each triangle into the atlas, interpolating colors.
    W = H = int(atlas_size)
    atlas = np.zeros((H, W, 4), dtype=np.uint8)  # RGBA, alpha=0 outside charts

    # UVs are in [0,1]. Map to pixel space (with vertical flip — image origin
    # is top-left, UV origin bottom-left).
    px = (uvs[:, 0] * (W - 1)).astype(np.int32)
    py = ((1.0 - uvs[:, 1]) * (H - 1)).astype(np.int32)

    # xatlas returns indices already as Nx3 (one row per triangle).
    if indices_atlas.ndim == 1:
        indices_atlas = indices_atlas.reshape(-1, 3)
    n_faces = len(indices_atlas)

    # Each atlas vertex traces back to an input vertex via vmap → use vmap
    # to look up the source color.
    atlas_colors = vcol[vmap]   # shape (n_atlas_verts, 3)

    # Triangle rasterization with barycentric interpolation. For atlas sizes
    # 512-1024 this is tolerable in pure numpy if we vectorize per-triangle.
    # Bottleneck on 500k-face meshes: ~30-60s on Cat 1. Acceptable for an
    # offline bake step.
    for tri_idx in range(n_faces):
        i0, i1, i2 = indices_atlas[tri_idx]
        x0, y0 = px[i0], py[i0]
        x1, y1 = px[i1], py[i1]
        x2, y2 = px[i2], py[i2]
        c0, c1, c2 = atlas_colors[i0], atlas_colors[i1], atlas_colors[i2]

        # Bounding box of the triangle (clamped to atlas)
        xmin = max(0, min(x0, x1, x2))
        xmax = min(W - 1, max(x0, x1, x2))
        ymin = max(0, min(y0, y1, y2))
        ymax = min(H - 1, max(y0, y1, y2))
        if xmax < xmin or ymax < ymin:
            continue

        # Mesh grid for the bbox
        xs = np.arange(xmin, xmax + 1, dtype=np.float32)
        ys = np.arange(ymin, ymax + 1, dtype=np.float32)
        gx, gy = np.meshgrid(xs, ys)

        # Barycentric coordinates
        denom = ((y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2))
        if abs(denom) < 1e-6:
            continue
        l1 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / denom
        l2 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / denom
        l3 = 1.0 - l1 - l2

        # Mask: pixel is inside iff all bary >= 0
        inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        if not np.any(inside):
            continue

        # Interpolate colors per-pixel
        rgb = (
            l1[..., None] * c0[None, None, :].astype(np.float32)
            + l2[..., None] * c1[None, None, :].astype(np.float32)
            + l3[..., None] * c2[None, None, :].astype(np.float32)
        )
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)

        # Bake into the atlas slice
        ymin_, ymax_ = int(ymin), int(ymax + 1)
        xmin_, xmax_ = int(xmin), int(xmax + 1)
        chunk = atlas[ymin_:ymax_, xmin_:xmax_]
        m3 = inside[..., None]
        chunk[..., :3] = np.where(m3, rgb, chunk[..., :3])
        chunk[..., 3]  = np.where(inside, 255, chunk[..., 3])

    # Save PNG (we'll embed the bytes into the GLB next)
    import io as _io
    buf = _io.BytesIO()
    Image.fromarray(atlas, mode="RGBA").save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()

    # Step 3 — assemble new GLB. We rebuild from scratch with TEXCOORD_0,
    # an embedded image, a texture, and a material referencing it.
    n_atlas_verts = len(vmap)
    # Re-shuffle positions in the atlas-vertex domain
    atlas_verts = verts[vmap]

    # glTF buffer layout (all little-endian floats / uint32):
    #   POSITION    (n_atlas_verts × 3 × float32)
    #   TEXCOORD_0  (n_atlas_verts × 2 × float32)
    #   INDICES     (n_faces × 3 × uint32)
    #   IMAGE       (PNG bytes)
    pos_bytes = atlas_verts.astype(np.float32).tobytes()
    uv_bytes = uvs.astype(np.float32).tobytes()
    idx_bytes = indices_atlas.astype(np.uint32).tobytes()

    bin_parts: list[bytes] = []
    offsets: list[int] = []
    sizes: list[int] = []

    def _add(buf: bytes) -> tuple[int, int]:
        # Pad to 4-byte alignment for accessor compatibility
        pad = (4 - (len(buf) % 4)) % 4
        offset = sum(len(p) for p in bin_parts)
        bin_parts.append(buf)
        if pad:
            bin_parts.append(b"\x00" * pad)
        return offset, len(buf)

    pos_off, pos_size = _add(pos_bytes)
    uv_off,  uv_size  = _add(uv_bytes)
    idx_off, idx_size = _add(idx_bytes)
    img_off, img_size = _add(png_bytes)

    bin_blob = b"".join(bin_parts)

    bvs = [
        {"buffer": 0, "byteOffset": pos_off, "byteLength": pos_size},
        {"buffer": 0, "byteOffset": uv_off,  "byteLength": uv_size},
        {"buffer": 0, "byteOffset": idx_off, "byteLength": idx_size},
        {"buffer": 0, "byteOffset": img_off, "byteLength": img_size},
    ]
    accs = [
        {"bufferView": 0, "componentType": 5126, "count": n_atlas_verts,
         "type": "VEC3",
         "min": atlas_verts.min(axis=0).tolist(),
         "max": atlas_verts.max(axis=0).tolist()},
        {"bufferView": 1, "componentType": 5126, "count": n_atlas_verts, "type": "VEC2"},
        {"bufferView": 2, "componentType": 5125, "count": n_faces * 3, "type": "SCALAR"},
    ]
    images = [{"bufferView": 3, "mimeType": "image/png"}]
    samplers = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]
    textures = [{"sampler": 0, "source": 0}]
    materials = [{
        "name": "aurora_baked_albedo",
        "pbrMetallicRoughness": {
            "baseColorTexture": {"index": 0, "texCoord": 0},
            "metallicFactor": 0.0,
            "roughnessFactor": 0.85,
        },
    }]
    meshes = [{
        "primitives": [{
            "attributes": {"POSITION": 0, "TEXCOORD_0": 1},
            "indices": 2,
            "material": 0,
            "mode": 4,
        }],
    }]
    nodes = [{"mesh": 0}]
    scenes = [{"nodes": [0]}]
    gltf = {
        "asset": {"version": "2.0", "generator": "aurora.bake_to_texture.v1"},
        "scene": 0,
        "scenes": scenes,
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "textures": textures,
        "samplers": samplers,
        "images": images,
        "accessors": accs,
        "bufferViews": bvs,
        "buffers": [{"byteLength": len(bin_blob)}],
    }

    size = _emit_glb(gltf, bin_blob, output_path)

    # Coverage stat: percentage of atlas pixels that received a triangle
    coverage = float((atlas[..., 3] > 0).sum()) / float(W * H)
    return {
        "ok": True,
        "schema": "aurora.bake_to_texture.v1",
        "input": str(input_path),
        "output": str(output_path),
        "atlas_size": int(W),
        "n_atlas_verts": int(n_atlas_verts),
        "n_input_verts": int(len(verts)),
        "n_faces": int(n_faces),
        "atlas_coverage_pct": round(100.0 * coverage, 2),
        "png_bytes": int(len(png_bytes)),
        "size_bytes": int(size),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Aurora UV-mapped texture bake")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--atlas-size", type=int, default=1024)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    res = bake(Path(args.input), Path(args.output), args.atlas_size)
    if args.pretty and res.get("ok"):
        sys.stdout.write(
            f"OK · {res['n_atlas_verts']:,} atlas verts · "
            f"{res['n_faces']:,} faces · "
            f"atlas {res['atlas_size']}² · "
            f"coverage {res['atlas_coverage_pct']}% · "
            f"png {res['png_bytes'] / 1024:.0f} KB · "
            f"out {res['size_bytes'] / 1e6:.1f} MB\n  → {res['output']}\n"
        )
    else:
        sys.stdout.write(json.dumps(res, indent=2, ensure_ascii=True) + "\n")
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
