#!/usr/bin/env python
"""Aurora — honest visual-quality audit (complement to mesh_quality_score).

mesh_quality_score measures *proxy* signals: color richness = unique RGB count,
silhouette = L1 distance on bbox aspect, etc. A mesh can score 99/100 while
visually being a colored blob that only resembles its reference because it
has many unique color samples and roughly the right bounding box.

This module measures what an artist actually cares about:

   has_materials      — was a real material defined? (False = vertex-color hack)
   has_uv_map         — is there a UV unwrap? (False = no texture sampling)
   has_textures       — are albedo/roughness/normal textures embedded?
   parts_count        — how many separable sub-meshes? (1 = unsplittable blob)
   dark_patches_pct   — % of vertices whose mean RGB < 30/255 (bake misses)
   aspect_deviation_l1— same metric as quality_score but reported separately

Each is reported alongside the "score" so the gap between proxy quality and
actual quality is explicit.

Schema: aurora.visual_audit.v1.

Usage:
    python mesh_visual_audit.py --mesh out.glb --pretty
    python mesh_visual_audit.py --mesh out.glb --json
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


def _read_gltf_json(glb_path: Path) -> dict:
    """Return the parsed JSON chunk of a GLB. Returns {} on read error."""
    try:
        with open(glb_path, "rb") as f:
            magic = f.read(4)
            if magic != b"glTF":
                return {}
            f.read(8)  # version + total length
            json_len, json_type = struct.unpack("<II", f.read(8))
            if json_type != 0x4E4F534A:
                return {}
            return json.loads(f.read(json_len).rstrip(b"\x00"))
    except (OSError, ValueError):
        return {}


def _material_palette_stats(gltf: dict) -> dict:
    colors: list[tuple[float, float, float]] = []
    textured_materials = 0
    for mat in gltf.get("materials") or []:
        pbr = mat.get("pbrMetallicRoughness") or {}
        if pbr.get("baseColorTexture") is not None:
            textured_materials += 1
        factor = pbr.get("baseColorFactor")
        if isinstance(factor, list) and len(factor) >= 3:
            try:
                colors.append((float(factor[0]), float(factor[1]), float(factor[2])))
            except (TypeError, ValueError):
                pass

    if not colors:
        return {
            "base_color_count": 0,
            "textured_materials": textured_materials,
            "palette_spread": -1.0,
            "low_contrast_on_light_ratio": -1.0,
        }

    channels = list(zip(*colors))
    spread = sum((max(channel) - min(channel)) for channel in channels) / 3.0
    low_contrast = 0
    for r, g, b in colors:
        brightness = (r + g + b) / 3.0
        chroma = max(r, g, b) - min(r, g, b)
        if brightness > 0.82 and chroma < 0.10:
            low_contrast += 1
    return {
        "base_color_count": len(colors),
        "textured_materials": textured_materials,
        "palette_spread": round(float(spread), 4),
        "low_contrast_on_light_ratio": round(float(low_contrast) / float(len(colors)), 3),
    }


def audit(mesh_path: Path) -> dict:
    """Return a visual quality report for a GLB. Never raises."""
    if not mesh_path.is_file():
        return {"ok": False, "error": f"mesh not found: {mesh_path}"}

    gltf = _read_gltf_json(mesh_path)

    n_materials = len(gltf.get("materials") or [])
    n_textures  = len(gltf.get("textures") or [])
    n_images    = len(gltf.get("images") or [])
    palette_stats = _material_palette_stats(gltf)

    # UV map present if any primitive has a TEXCOORD_0 attribute
    has_uv = False
    for m in gltf.get("meshes") or []:
        for p in m.get("primitives") or []:
            attrs = p.get("attributes") or {}
            if "TEXCOORD_0" in attrs:
                has_uv = True
                break
        if has_uv:
            break

    # Parts count = unique mesh indices referenced by nodes (a proxy for
    # how "articulatable" the asset is — 1 means single merged blob).
    parts_count = len(gltf.get("meshes") or []) or 0

    # Vertex-color analysis (dark-patch percentage)
    dark_patches_pct = -1.0
    has_vcol = False
    aspect_extents = None
    try:
        import trimesh
        import numpy as np
        m = trimesh.load(mesh_path, force="mesh")
        aspect_extents = [round(float(x), 4) for x in m.bounding_box.extents]
        if hasattr(m.visual, "vertex_colors") and m.visual.vertex_colors is not None:
            vc = np.asarray(m.visual.vertex_colors)
            if len(vc):
                has_vcol = True
                rgb = vc[:, :3].astype(float)
                brightness = rgb.mean(axis=1)
                dark = (brightness < 30).sum()
                dark_patches_pct = round(100.0 * float(dark) / float(len(vc)), 2)
    except Exception:
        pass

    # Honest verdict aggregating the binary signals
    issues: list[str] = []
    if n_materials == 0:
        issues.append("zero materials (vertex-color-only — no PBR)")
    if not has_uv:
        issues.append("no UV map (no texture sampling possible)")
    if n_textures == 0 and n_images == 0:
        issues.append("zero textures/images embedded")
    if parts_count <= 1:
        issues.append("single merged mesh (no articulatable parts)")
    if dark_patches_pct >= 5.0:
        issues.append(f"{dark_patches_pct}% dark vertices (bake misses)")
    if (
        n_materials > 0
        and n_textures == 0
        and n_images == 0
        and palette_stats["palette_spread"] >= 0
        and palette_stats["palette_spread"] < 0.08
    ):
        issues.append("material palette is nearly monochrome and has no texture")
    if (
        n_materials > 0
        and n_textures == 0
        and n_images == 0
        and palette_stats["low_contrast_on_light_ratio"] >= 0.8
    ):
        issues.append("materials are low-contrast on light background")

    # Compute a "visual_grade" 0-100 that actually penalizes these issues.
    # Each binary issue costs 20 pts; dark patches cost up to 20 pts pro-rata.
    grade = 100
    if n_materials == 0:        grade -= 20
    if not has_uv:              grade -= 20
    if n_textures == 0 and n_images == 0: grade -= 20
    if parts_count <= 1:        grade -= 20
    if dark_patches_pct >= 0:
        grade -= int(min(20.0, dark_patches_pct * 2))
    if "material palette is nearly monochrome and has no texture" in issues:
        grade -= 20
    if "materials are low-contrast on light background" in issues:
        grade -= 15
    grade = max(0, grade)

    return {
        "ok": True,
        "schema": "aurora.visual_audit.v1",
        "mesh_path": str(mesh_path),
        "size_bytes": mesh_path.stat().st_size,
        "extents_m": aspect_extents,
        "n_materials": n_materials,
        "n_textures": n_textures,
        "n_images": n_images,
        **palette_stats,
        "has_uv_map": has_uv,
        "has_vertex_colors": has_vcol,
        "parts_count": parts_count,
        "dark_patches_pct": dark_patches_pct,
        "issues": issues,
        "visual_grade": grade,
    }


def render_pretty(report: dict) -> str:
    if not report.get("ok"):
        return f"FAIL: {report.get('error')}\n"
    lines = [
        f"Visual audit — {report['mesh_path']}",
        f"  size: {report['size_bytes'] / 1e6:.1f} MB · extents={report['extents_m']}",
        f"  materials={report['n_materials']} textures={report['n_textures']} "
        f"images={report['n_images']} parts={report['parts_count']}",
        f"  palette: base_colors={report.get('base_color_count')} "
        f"textured_materials={report.get('textured_materials')} "
        f"spread={report.get('palette_spread')} "
        f"low_light_ratio={report.get('low_contrast_on_light_ratio')}",
        f"  has_uv_map={report['has_uv_map']} "
        f"has_vertex_colors={report['has_vertex_colors']} "
        f"dark_patches_pct={report['dark_patches_pct']}",
        f"  visual_grade: {report['visual_grade']}/100",
    ]
    if report["issues"]:
        lines.append("  Issues:")
        for issue in report["issues"]:
            lines.append(f"    - {issue}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora honest visual audit")
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    res = audit(Path(args.mesh))
    if args.pretty:
        sys.stdout.write(render_pretty(res))
    else:
        sys.stdout.write(json.dumps(res, indent=2, ensure_ascii=True) + "\n")
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
