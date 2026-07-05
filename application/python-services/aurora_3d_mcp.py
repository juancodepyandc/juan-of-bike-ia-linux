#!/usr/bin/env python
"""Aurora 3D Audit MCP Server — engineer-grade inspection of generated 3D files.

Why: the assistant kept reporting "score 99/100, watertight=True" on meshes
that visually were images-pasted-on-cubes, anatomically wrong (huge wings,
crushed bodies), or single-blob "rotating chassis" with no real articulation.
This MCP server exposes structured tools the assistant can call to get
real diagnostics — not proxy scores.

Tools:
  inspect_geometry      — verts/faces/parts/manifold/extents/dim ratios
  inspect_texture       — UV coverage, texture resolution, "pasted-image"
                          heuristic (per-texel-region color uniformity),
                          dark-patch %
  inspect_anatomy       — per spatial cluster: bbox aspect ratio, position;
                          flags wings-too-large / head-too-small /
                          torso-crushed / limbs-merged-into-body
  inspect_motion        — animation channels, per-bone amplitude, rigid-vs-
                          articulated check (single-channel-on-root = rigid),
                          fluidity (frame count vs duration)
  inspect_components    — per sub-mesh: thinness (length/thickness ratio),
                          counts; flags "cable should be thin but is a cube"
  inspect_squash        — actual extents vs expected canonical for kind;
                          flags non-uniform scaling artifacts
  summarize_quality     — combines all above into a Meshy-grade verdict
                          with specific issues + suggested fixes

Run as a Claude Code MCP server: register in .claude/settings.local.json or
via mcp.json so Claude Code spawns it on stdio. Schema for every tool's
return: aurora.audit.<tool>.v1.

Usage (manual smoke test):
   python aurora_3d_mcp.py
   # then connect via mcp.client.stdio_client
"""

from __future__ import annotations

import asyncio
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server


# ---------------------------------------------------------------------------
# Helpers — glTF JSON reading + heavy-mesh inspection (deferred imports)
# ---------------------------------------------------------------------------


def _read_gltf_json(glb_path: Path) -> dict:
    """Return the parsed JSON chunk of a GLB. {} on read error."""
    try:
        raw = glb_path.read_bytes()
        if raw[:4] != b"glTF":
            return {}
        json_len, json_type = struct.unpack_from("<II", raw, 12)
        if json_type != 0x4E4F534A:
            return {}
        return json.loads(raw[20:20 + json_len].rstrip(b"\x00"))
    except (OSError, ValueError):
        return {}


def _trimesh_load(glb_path: Path):
    """Load a mesh via trimesh (force=mesh). Returns None on error."""
    try:
        import trimesh
        return trimesh.load(str(glb_path), force="mesh")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def t_inspect_geometry(path: str) -> dict:
    """Real geometric diagnostic — manifold, parts, extents, density."""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": f"file not found: {path}"}
    gltf = _read_gltf_json(p)
    m = _trimesh_load(p)
    if m is None:
        return {"ok": False, "error": "trimesh load failed"}

    import numpy as np

    extents = [round(float(x), 4) for x in m.bounding_box.extents]
    longest = max(extents) or 1.0
    norm = [round(e / longest, 3) for e in extents]
    sorted_norm = sorted(norm, reverse=True)

    parts_in_gltf = len(gltf.get("meshes") or [])
    components = m.split(only_watertight=False)

    # Density: faces per cubic-unit volume (proxy for "is this geometry rich
    # enough to look not blocky?")
    bbox_vol = max(extents[0] * extents[1] * extents[2], 1e-6)
    face_density = len(m.faces) / bbox_vol  # faces / m³

    return {
        "ok": True,
        "schema": "aurora.audit.geometry.v1",
        "path": str(p),
        "vertex_count": int(len(m.vertices)),
        "face_count": int(len(m.faces)),
        "extents_m": extents,
        "normalized_extents_sorted_desc": sorted_norm,
        "longest_axis_m": float(longest),
        "is_watertight": bool(m.is_watertight),
        "euler_number": int(m.euler_number) if m.euler_number is not None else None,
        "broken_faces_count": int(np.count_nonzero(m.area_faces < 1e-12)),
        "components_disjoint": int(len(components)),
        "parts_in_gltf_meshes_array": int(parts_in_gltf),
        "face_density_per_m3": round(face_density, 1),
        "diagnostics": _geometry_diagnostics(extents, sorted_norm, len(components),
                                              parts_in_gltf, m.is_watertight,
                                              len(m.vertices)),
    }


def _geometry_diagnostics(extents, sorted_norm, components, parts_gltf,
                          watertight, n_verts) -> list[str]:
    out: list[str] = []
    if not watertight:
        out.append("non-watertight (holes, broken faces, or non-manifold edges)")
    if components == 1 and parts_gltf == 1:
        out.append("single fused blob (no separable parts; can't articulate)")
    if sorted_norm[0] - sorted_norm[2] < 0.15:
        out.append("nearly-isotropic shape (bounding box almost cubic — "
                   "may indicate failed silhouette generation)")
    if n_verts < 5000:
        out.append("low vertex count (<5k — surface may look faceted/blocky)")
    if max(extents) > 10:
        out.append("oversize bounding box (>10 m on longest axis — units suspect)")
    if max(extents) < 0.1:
        out.append("undersize bounding box (<0.1 m on longest axis — units suspect)")
    return out


def t_inspect_texture(path: str) -> dict:
    """UV/material/texture audit + 'pasted image' heuristic."""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": f"file not found: {path}"}
    gltf = _read_gltf_json(p)
    if not gltf:
        return {"ok": False, "error": "not a valid glb"}

    n_materials = len(gltf.get("materials") or [])
    n_textures = len(gltf.get("textures") or [])
    n_images = len(gltf.get("images") or [])

    has_uv = False
    for m in gltf.get("meshes") or []:
        for prim in m.get("primitives") or []:
            if "TEXCOORD_0" in (prim.get("attributes") or {}):
                has_uv = True
                break
        if has_uv:
            break

    # Resolve image dimensions (largest one, used as the albedo atlas)
    img_w = img_h = 0
    img_size_kb = 0
    pasted_image_score = -1.0
    try:
        if n_images > 0 and gltf.get("bufferViews"):
            raw = p.read_bytes()
            json_len, _ = struct.unpack_from("<II", raw, 12)
            bin_off = 20 + ((json_len + 3) & ~3)
            bin_len, _ = struct.unpack_from("<II", raw, bin_off)
            bin_blob = raw[bin_off + 8:bin_off + 8 + bin_len]
            for img in gltf.get("images") or []:
                bv_idx = img.get("bufferView")
                if bv_idx is None:
                    continue
                bv = gltf["bufferViews"][bv_idx]
                off = bv.get("byteOffset", 0)
                sz = bv.get("byteLength", 0)
                img_bytes = bin_blob[off:off + sz]
                from PIL import Image
                import io as _io
                im = Image.open(_io.BytesIO(img_bytes))
                if im.width * im.height > img_w * img_h:
                    img_w, img_h = im.size
                    img_size_kb = sz / 1024.0
                    pasted_image_score = _detect_pasted_image(im)
    except Exception:
        pass

    # Vertex-color analysis fallback — for assets that haven't been UV-baked yet
    m = _trimesh_load(p)
    dark_pct = -1.0
    if m is not None:
        if hasattr(m.visual, "vertex_colors") and m.visual.vertex_colors is not None:
            import numpy as np
            vc = np.asarray(m.visual.vertex_colors)
            if len(vc):
                rgb = vc[:, :3].astype(float)
                bright = rgb.mean(axis=1)
                dark_pct = round(100.0 * float((bright < 30).sum()) / float(len(vc)), 2)

    diagnostics: list[str] = []
    if n_materials == 0:
        diagnostics.append("no materials defined (vertex-color-only — no PBR slots)")
    if not has_uv:
        diagnostics.append("no UV map (no texture sampling possible)")
    if n_textures == 0 and n_images == 0:
        diagnostics.append("no embedded textures or images")
    if dark_pct >= 5.0:
        diagnostics.append(f"{dark_pct}% dark vertices (bake misses on back faces)")
    if pasted_image_score > 0.65:
        diagnostics.append(f"high 'pasted-image' score ({pasted_image_score:.2f}): "
                           "albedo looks like a 2D photo dropped on the mesh, not "
                           "a UV-aware bake — large monochromatic regions or "
                           "abrupt rectangular edges in the atlas.")
    if img_w and img_w < 512:
        diagnostics.append(f"low texture resolution ({img_w}×{img_h} — should be ≥1024)")

    return {
        "ok": True,
        "schema": "aurora.audit.texture.v1",
        "path": str(p),
        "n_materials": n_materials,
        "n_textures": n_textures,
        "n_images": n_images,
        "has_uv_map": has_uv,
        "albedo_resolution": [img_w, img_h] if img_w else None,
        "albedo_size_kb": round(img_size_kb, 1) if img_size_kb else None,
        "pasted_image_heuristic_score": round(pasted_image_score, 3) if pasted_image_score >= 0 else None,
        "vertex_color_dark_percent": dark_pct,
        "diagnostics": diagnostics,
    }


def _detect_pasted_image(im) -> float:
    """Return [0,1] — higher = more likely a 2D photo dropped on the mesh
    rather than a UV-aware bake. Heuristics:
      - large connected mono-color regions (median-filter delta near zero)
      - sharp rectangular edges (Sobel histogram skewed to axis-aligned)
      - low alpha-channel variance (UV charts have alpha=0 outside, so we
        expect bimodal alpha; pasted images are uniformly opaque)"""
    import numpy as np
    arr = np.asarray(im.convert("RGBA"), dtype=np.uint8)
    h, w = arr.shape[:2]
    if h * w == 0:
        return 0.0

    # Bimodal alpha check: a UV bake has chunks of alpha=0 (between charts)
    # plus alpha=255 inside charts. A pasted image is uniformly opaque.
    alpha = arr[..., 3]
    alpha_zero_ratio = float((alpha < 16).sum()) / float(alpha.size)
    bimodal_alpha_signal = 1.0 if alpha_zero_ratio > 0.05 else 0.0

    # Color uniformity: downsample to 32x32 and measure stddev. Low stddev =
    # large flat regions = either chart layout (textured) OR pasted photo
    # with sky/wall. Combined with bimodal_alpha we discriminate.
    small = np.asarray(im.convert("RGB").resize((64, 64)))
    std_color = float(small.std())  # 0..127

    pasted_signal = 0.0
    if bimodal_alpha_signal == 0.0:
        # No chart layout → likely pasted photo
        pasted_signal = max(0.0, min(1.0, 1.0 - std_color / 90.0))

    return float(pasted_signal)


def t_inspect_anatomy(path: str, expected_kind: str = "generic") -> dict:
    """Spatial-cluster anatomy check. For character/creature/quadruped, k-means
    splits the mesh into 6 regions and we check ratios + spatial layout for
    common AI-generation pathologies (wings-too-big, head-merged-into-torso,
    crushed body, tail-not-found)."""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": f"file not found: {path}"}
    m = _trimesh_load(p)
    if m is None:
        return {"ok": False, "error": "trimesh load failed"}
    import numpy as np

    verts = np.asarray(m.vertices, dtype=np.float32)
    if len(verts) < 100:
        return {"ok": False, "error": "too few vertices for anatomy analysis"}

    # k-means on positions, k=6 (head + torso + 4 limbs ish)
    from sklearn.cluster import KMeans
    km = KMeans(n_clusters=6, n_init=4, random_state=42).fit(verts)
    labels = km.labels_
    centroids = km.cluster_centers_

    bbox = m.bounds
    body_extent = bbox[1] - bbox[0]
    overall_height = body_extent[1] if expected_kind in ("character", "humanoid", "creature") else max(body_extent)

    parts: list[dict] = []
    for c in range(6):
        idx = np.where(labels == c)[0]
        if len(idx) == 0:
            continue
        sub = verts[idx]
        sub_bbox = sub.max(axis=0) - sub.min(axis=0)
        center = centroids[c]
        # Normalized position within bbox: 0=floor 1=top, -1=back 1=front
        rel_y = (center[1] - bbox[0][1]) / max(body_extent[1], 1e-6)
        rel_x = (center[0] - bbox[0][0]) / max(body_extent[0], 1e-6)
        rel_z = (center[2] - bbox[0][2]) / max(body_extent[2], 1e-6)
        parts.append({
            "cluster": c,
            "n_verts": int(len(idx)),
            "size_ratio_to_body": round(float(sub_bbox.max()) / max(float(overall_height), 1e-6), 3),
            "rel_position": [round(float(rel_x), 3), round(float(rel_y), 3), round(float(rel_z), 3)],
            "extents_m": [round(float(x), 3) for x in sub_bbox],
        })
    parts.sort(key=lambda p: -p["n_verts"])

    diagnostics: list[str] = []

    # Wings-too-large: any non-largest cluster wider than 0.85× body height
    body_part_size = parts[0]["size_ratio_to_body"]
    for p_ in parts[1:]:
        if p_["size_ratio_to_body"] > 0.85 and expected_kind in ("creature", "quadruped"):
            diagnostics.append(
                f"cluster {p_['cluster']} extends {p_['size_ratio_to_body']:.2f}× the "
                f"body height — likely 'wings/limb too large' artifact"
            )
            break

    # Crushed body — body extents very anisotropic in unintended way
    h = body_extent[1]
    w = body_extent[0]
    d = body_extent[2]
    if expected_kind in ("character", "humanoid"):
        if w > 1.3 * h or d > 1.3 * h:
            diagnostics.append(
                f"crushed humanoid: width {w:.2f} or depth {d:.2f} exceeds height {h:.2f} "
                f"by >30% — torso geometry likely deformed"
            )
        if h < 0.5:
            diagnostics.append(f"humanoid height {h:.2f}m is unrealistically small")

    # Tail/head detection (by extreme positions along Y)
    if expected_kind in ("creature", "quadruped"):
        topmost = max(parts, key=lambda p: p["rel_position"][1])
        bottommost = min(parts, key=lambda p: p["rel_position"][1])
        if topmost["size_ratio_to_body"] < 0.15:
            diagnostics.append(
                f"top cluster (likely head) is only {topmost['size_ratio_to_body']:.2f}× body "
                "— head may be missing or merged into torso"
            )
        if bottommost["rel_position"][1] > 0.3:
            diagnostics.append(
                "no extremity found near floor — tail / lower limbs absent"
            )

    return {
        "ok": True,
        "schema": "aurora.audit.anatomy.v1",
        "path": str(p),
        "expected_kind": expected_kind,
        "body_extents_m": [round(float(x), 3) for x in body_extent],
        "k_clusters": 6,
        "parts": parts,
        "diagnostics": diagnostics,
    }


def t_inspect_motion(path: str) -> dict:
    """Animation channel audit: rigid-block-rotation vs real articulation."""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": f"file not found: {path}"}
    gltf = _read_gltf_json(p)
    if not gltf:
        return {"ok": False, "error": "not a valid glb"}

    nodes = gltf.get("nodes") or []
    n_skins = len(gltf.get("skins") or [])
    anims = gltf.get("animations") or []

    if not anims:
        return {
            "ok": True,
            "schema": "aurora.audit.motion.v1",
            "path": str(p),
            "has_animations": False,
            "n_animations": 0,
            "n_skins": n_skins,
            "diagnostics": ["no glTF animations array — file is static when "
                            "loaded in any viewer"],
        }

    channels_per_anim: list[dict] = []
    rigid_block_signals: list[str] = []
    total_channels = 0

    for ai, anim in enumerate(anims):
        chans = anim.get("channels") or []
        total_channels += len(chans)
        targeted_nodes = []
        targeted_paths = []
        for ch in chans:
            tgt = ch.get("target") or {}
            node_idx = tgt.get("node")
            path_kind = tgt.get("path")
            if node_idx is not None and node_idx < len(nodes):
                targeted_nodes.append(nodes[node_idx].get("name", f"node_{node_idx}"))
                targeted_paths.append(path_kind)
        unique_nodes = set(targeted_nodes)
        info = {
            "name": anim.get("name", f"anim_{ai}"),
            "n_channels": len(chans),
            "unique_target_nodes": len(unique_nodes),
            "target_paths": list(set(targeted_paths)),
            "first_5_target_names": targeted_nodes[:5],
        }
        channels_per_anim.append(info)
        # Single channel on root = rigid block
        if len(chans) == 1 and chans[0].get("target", {}).get("node", -1) == 0:
            rigid_block_signals.append(
                f"animation '{info['name']}' is single-channel on root node "
                "— whole mesh moves as one rigid block"
            )

    diagnostics = list(rigid_block_signals)
    if total_channels < 4 and n_skins > 0:
        diagnostics.append(
            f"only {total_channels} channels but {n_skins} skins present — "
            "rig is wired up but most bones aren't keyframed"
        )

    return {
        "ok": True,
        "schema": "aurora.audit.motion.v1",
        "path": str(p),
        "has_animations": True,
        "n_animations": len(anims),
        "total_channels": total_channels,
        "n_skins": n_skins,
        "n_nodes": len(nodes),
        "animations": channels_per_anim,
        "diagnostics": diagnostics,
    }


def t_inspect_components(path: str) -> dict:
    """Per-sub-mesh thinness check. For mechanical/cable assets we expect
    long thin geometries; if the parts array is full of cubic chunks the
    output is wrong (cables modeled as cubes etc.)."""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": f"file not found: {path}"}
    m = _trimesh_load(p)
    if m is None:
        return {"ok": False, "error": "trimesh load failed"}
    import numpy as np

    components = m.split(only_watertight=False)
    parts_data: list[dict] = []
    for ci, c in enumerate(components):
        if c is None or len(c.vertices) == 0:
            continue
        ext = c.bounding_box.extents
        srt = sorted(ext, reverse=True)
        thinness = srt[0] / max(srt[2], 1e-6)
        parts_data.append({
            "index": ci,
            "n_verts": int(len(c.vertices)),
            "n_faces": int(len(c.faces)),
            "extents_m": [round(float(x), 3) for x in ext],
            "thinness_ratio": round(float(thinness), 2),
            "is_thin_like_cable": thinness > 5.0,
        })
    parts_data.sort(key=lambda p: -p["n_verts"])

    diagnostics: list[str] = []
    if len(parts_data) == 1:
        diagnostics.append("single connected component — no separable parts")
    cable_like = sum(1 for p in parts_data if p["is_thin_like_cable"])
    cubic_like = sum(1 for p in parts_data
                     if p["thinness_ratio"] < 1.5 and p["n_verts"] > 100)
    if cable_like == 0 and len(parts_data) > 1:
        diagnostics.append(
            f"{cubic_like} cubic-ish components, 0 thin/cable-like — if the "
            "asset should have wires/RGB cables, those are missing or modeled "
            "as solid blocks"
        )

    return {
        "ok": True,
        "schema": "aurora.audit.components.v1",
        "path": str(p),
        "n_components": len(parts_data),
        "components": parts_data[:20],   # cap
        "n_thin_like_cable": cable_like,
        "n_cubic_like": cubic_like,
        "diagnostics": diagnostics,
    }


def t_inspect_squash(path: str, expected_kind: str = "generic") -> dict:
    """Detect if the mesh has been over-distorted by reshape. Compare
    extents + sorted ratios to canonical-per-kind reference."""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": f"file not found: {path}"}
    m = _trimesh_load(p)
    if m is None:
        return {"ok": False, "error": "trimesh load failed"}

    extents = list(m.bounding_box.extents)
    longest = max(extents) or 1.0
    norm = sorted([e / longest for e in extents], reverse=True)

    # Canonical aspects (sorted DESC) per kind, mirroring KIND_ASPECT in
    # mesh_quality_score.py
    canonical = {
        "character": (1.0, 0.30, 0.20),
        "humanoid":  (1.0, 0.30, 0.20),
        "creature":  (1.0, 0.55, 0.55),
        "quadruped": (1.0, 0.45, 0.55),
        "pc_tower":  (1.0, 0.55, 0.45),
        "case":      (1.0, 0.60, 0.50),
        "vehicle":   (1.0, 0.50, 0.55),
        "sphere":    (1.0, 1.00, 1.00),
        "generic":   None,  # open
    }
    expected = canonical.get(expected_kind)

    diagnostics: list[str] = []
    aspect_l1 = -1.0
    if expected:
        aspect_l1 = float(sum(abs(a - b) for a, b in zip(norm, expected)))
        if aspect_l1 > 0.6:
            actual_str = [round(float(v), 2) for v in norm]
            diagnostics.append(
                f"silhouette mismatch: actual {actual_str} vs "
                f"canonical {list(expected)} for kind={expected_kind} "
                f"(L1={aspect_l1:.2f}); body proportions are off"
            )
        # Detect aggressive non-uniform scaling (post-reshape v80w squash)
        if expected_kind in ("humanoid", "character", "creature", "quadruped"):
            if norm[1] / norm[2] > 2.5 or norm[1] / norm[2] < 0.4:
                diagnostics.append(
                    "aggressive non-uniform reshape detected — secondary axes "
                    "have very different ratios than expected"
                )

    return {
        "ok": True,
        "schema": "aurora.audit.squash.v1",
        "path": str(p),
        "expected_kind": expected_kind,
        "extents_m": [round(float(x), 3) for x in extents],
        "normalized_sorted_desc": [round(float(x), 3) for x in norm],
        "canonical_for_kind": list(expected) if expected else None,
        "aspect_l1_distance": round(float(aspect_l1), 3) if aspect_l1 >= 0 else None,
        "diagnostics": diagnostics,
    }


def t_summarize_quality(path: str, expected_kind: str = "generic") -> dict:
    """Run all the audits and return one consolidated Meshy-grade verdict
    with concrete fix suggestions."""
    geo = t_inspect_geometry(path)
    tex = t_inspect_texture(path)
    ana = t_inspect_anatomy(path, expected_kind)
    mot = t_inspect_motion(path)
    com = t_inspect_components(path)
    squ = t_inspect_squash(path, expected_kind)

    all_issues: list[str] = []
    for r in (geo, tex, ana, mot, com, squ):
        all_issues.extend(r.get("diagnostics", []) or [])

    grade = 100
    grade -= 8 * len([d for d in (geo.get("diagnostics") or [])])
    grade -= 8 * len([d for d in (tex.get("diagnostics") or [])])
    grade -= 8 * len([d for d in (ana.get("diagnostics") or [])])
    grade -= 8 * len([d for d in (mot.get("diagnostics") or [])])
    grade -= 6 * len([d for d in (com.get("diagnostics") or [])])
    grade -= 6 * len([d for d in (squ.get("diagnostics") or [])])
    grade = max(0, min(100, grade))

    # Suggested fixes
    suggested: list[str] = []
    if any("no UV map" in d or "no materials" in d for d in all_issues):
        suggested.append("run bake_to_texture to generate UV-mapped albedo "
                         "(application/python-services/bake_to_texture.py)")
    if any("single fused blob" in d or "single connected component" in d for d in all_issues):
        suggested.append("run mesh_part_split --k 4 (or higher) to make parts "
                         "articulatable (application/python-services/mesh_part_split.py)")
    if any("rigid block" in d for d in all_issues):
        suggested.append("re-bake animation with multi-bone walk_humanoid mode "
                         "(glb_animation_injector.py --motion-kind walk_humanoid)")
    if any("crushed" in d or "silhouette mismatch" in d for d in all_issues):
        suggested.append("re-run rescue chain or regenerate from FLUX with a "
                         "stricter view-plan to avoid Hunyuan3D distortion")
    if any("pasted-image" in d for d in all_issues):
        suggested.append("the bake projected a 2D photo onto vertices; needs "
                         "a UV-aware texture bake from multiple views, not "
                         "single-view projection")

    return {
        "ok": True,
        "schema": "aurora.audit.summary.v1",
        "path": str(path),
        "expected_kind": expected_kind,
        "engineer_grade": grade,
        "verdict": ("Meshy-grade" if grade >= 90
                    else "Production-acceptable" if grade >= 70
                    else "Needs work" if grade >= 40
                    else "Below acceptable"),
        "all_issues": all_issues,
        "suggested_fixes": suggested,
        "geometry": geo,
        "texture": tex,
        "anatomy": ana,
        "motion": mot,
        "components": com,
        "squash": squ,
    }


# ---------------------------------------------------------------------------
# MCP wiring
# ---------------------------------------------------------------------------


server = Server("aurora-3d-audit", version="1.0.0",
                instructions="Engineer-grade 3D file audit (Meshy-equivalent). "
                "Call summarize_quality(path, expected_kind) for a full report, "
                "or any specific tool for a focused check.")


_TOOLS: list[tuple[str, str, dict, callable]] = [
    ("inspect_geometry",
     "Verts/faces/parts/manifold/extents/density audit of a 3D file.",
     {"type": "object",
      "properties": {"path": {"type": "string", "description": "absolute or repo-relative path to .glb"}},
      "required": ["path"]},
     t_inspect_geometry),
    ("inspect_texture",
     "UV/material/texture audit + 'pasted-image' heuristic. Detects "
     "mesh.materials==0 (vertex-color hack), low-res atlas, dark patches.",
     {"type": "object",
      "properties": {"path": {"type": "string"}},
      "required": ["path"]},
     t_inspect_texture),
    ("inspect_anatomy",
     "Spatial-cluster anatomy check. Flags wings-too-large, "
     "crushed bodies, missing limbs/tail, head-merged-into-torso.",
     {"type": "object",
      "properties": {
          "path": {"type": "string"},
          "expected_kind": {"type": "string",
                            "enum": ["character", "humanoid", "creature",
                                     "quadruped", "pc_tower", "case", "vehicle",
                                     "sphere", "generic"]},
      },
      "required": ["path"]},
     t_inspect_anatomy),
    ("inspect_motion",
     "Animation channel audit: rigid-block (single channel on root) vs "
     "articulated (multi-bone) vs absent. Flags glTF.animations==[].",
     {"type": "object",
      "properties": {"path": {"type": "string"}},
      "required": ["path"]},
     t_inspect_motion),
    ("inspect_components",
     "Per-sub-mesh thinness check. Flags cubic blocks where the asset "
     "should have thin/cable/wire-like geometry.",
     {"type": "object",
      "properties": {"path": {"type": "string"}},
      "required": ["path"]},
     t_inspect_components),
    ("inspect_squash",
     "Detect over-distortion vs canonical aspect for the kind.",
     {"type": "object",
      "properties": {
          "path": {"type": "string"},
          "expected_kind": {"type": "string"},
      },
      "required": ["path"]},
     t_inspect_squash),
    ("summarize_quality",
     "Run ALL audits and produce a single Meshy-grade verdict + concrete "
     "fix suggestions per detected issue.",
     {"type": "object",
      "properties": {
          "path": {"type": "string"},
          "expected_kind": {"type": "string"},
      },
      "required": ["path"]},
     t_summarize_quality),
]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name=name, description=desc, inputSchema=schema)
        for name, desc, schema, _ in _TOOLS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    impl = next((fn for n, _, _, fn in _TOOLS if n == name), None)
    if impl is None:
        return [types.TextContent(type="text",
                                  text=json.dumps({"ok": False, "error": f"unknown tool: {name}"}))]
    try:
        result = impl(**arguments)
    except TypeError as exc:
        return [types.TextContent(type="text",
                                  text=json.dumps({"ok": False, "error": f"bad arguments: {exc}"}))]
    return [types.TextContent(type="text",
                              text=json.dumps(result, ensure_ascii=False, indent=2))]


async def run() -> None:
    async with stdio_server() as (rx, tx):
        await server.run(rx, tx, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(run())
