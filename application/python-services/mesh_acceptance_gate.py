#!/usr/bin/env python
"""Aurora 3D final acceptance gate.

This is the "do not call a cube acceptable" layer. The older score pipeline can
rate a mesh highly because it has many faces or vertex colors, even when the
result is visually primitive, textureless, or static after a motion request.

The gate is intentionally deterministic and LLM-free:
  - mesh_quality_score.py for density/aspect/manifold proxy metrics
  - mesh_visual_audit.py for UV/material/texture signals
  - direct glTF JSON inspection for animation channels and Aurora material
    animation extras (LED/OLED/runtime motion markers)

Schema: aurora.mesh_acceptance.v1.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any


HARD_SURFACE_KINDS = {
    "pc_tower",
    "case",
    "computer",
    "motherboard",
    "vehicle",
    "product",
    "gadget",
    "architecture",
    "mechanism",
    "mechanical",
}

ORGANIC_KINDS = {"character", "humanoid", "creature", "quadruped"}
OPEN_PRIMITIVE_KINDS = {"sphere"}

REALISM_RE = re.compile(
    r"\b(real|reel|r[ée]el|realiste|r[ée]aliste|vrai|vraie|vrais|vraies|"
    r"photoreal|photo[-\s]?real|"
    r"convenable|credible|cr[ée]dible|physique|physical|inspectable)\b",
    re.IGNORECASE,
)
TEXTURE_RE = re.compile(
    r"\b(texture|textur[ée]e?|mati[èe]re|mat[ée]riau|material|pbr|uv|albedo|"
    r"roughness|metalness|normal\s?map|grain|brushed|bross[ée]|metal|m[ée]tal|"
    r"wood|bois|leather|cuir|fabric|tissu|glass|verre|transparent|skin|peau|"
    r"paint|peinture|emissive|[ée]missif|led|rgb|oled|screen|[ée]cran)\b",
    re.IGNORECASE,
)
NO_TEXTURE_RE = re.compile(
    r"\b(no|not|sans|pas\s+de)\s+(texture|material|mati[èe]re|pbr|uv)\b",
    re.IGNORECASE,
)
MOTION_RE = re.compile(
    r"\b(animation|animate|animated|animer|anim[ée]|mouvement|motion|moving|"
    r"en\s+mouvement|marche|marcher|walk|walking|court|courir|run|running|"
    r"danse|danser|dance|dancing|macarena|floss|flossing|"
    r"roule|rouler|rolling|drives?|vole|voler|flying|hover|tourne|tourner|"
    r"spin|spinning|rotate|rotating|ventilateur|fan|helice|propeller|gear|"
    r"engrenage|poulie|pulley|courroie|belt|hinge|charni[èe]re|pivot|"
    r"clignote|blink|pulse|pulsing|chase|chenillard|led|rgb|oled|screen|[ée]cran)\b",
    re.IGNORECASE,
)
LOCOMOTION_RE = re.compile(
    r"\b(marche|marcher|walk|walks|walking|court|courir|run|runs|running|"
    r"jog|jogging|sprint|sprinting|deambule|d[Ã©e]ambule|stride|stroll)\b",
    re.IGNORECASE,
)
MACARENA_RE = re.compile(r"\bmacarena\b", re.IGNORECASE)
FLOSS_RE = re.compile(r"\bfloss(?:ing)?\b", re.IGNORECASE)
HUMAN_FIDELITY_RE = re.compile(
    r"\b(personnage|personne|human|humain|character|visage|face|"
    r"reproduction|identit[eÃ©]|identity|ressemblance|lookalike|"
    r"realiste|r[eÃ©]aliste|photoreal|photo[-\s]?real|vrai|vraie|vrais|vraies)\b",
    re.IGNORECASE,
)
HAND_FIDELITY_RE = re.compile(
    r"\b(mains?|hands?|doigts?|fingers?|palms?|paumes?|poignets?|wrists?|"
    r"retourner\s+ses\s+mains|open\s+palms?)\b",
    re.IGNORECASE,
)
NO_MOTION_RE = re.compile(
    r"\b(static|statique|sans\s+animation|sans\s+mouvement|no\s+animation|"
    r"no\s+motion|immobile)\b",
    re.IGNORECASE,
)
PRIMITIVE_RE = re.compile(r"\b(cube|sphere|sph[èe]re|cylinder|cylindre|low[\s-]?poly|voxel|primitive)\b", re.IGNORECASE)
ANTI_PRIMITIVE_RE = re.compile(
    r"\b(no|not|sans|pas\s+de)\s+(cube|cubique|primitive|forme\s+basique|basic\s+shape)\b",
    re.IGNORECASE,
)
PRINTABLE_ONLY_RE = re.compile(r"\b(stl|printable|imprimable|impression\s+3d|3d\s+print|usinage|cad)\b", re.IGNORECASE)
STRIMER_PLUS_V2_RE = re.compile(
    r"\b(strimer(?:\s+plus)?(?:\s*v2)?|lian\s+li\s+strimer)\b",
    re.IGNORECASE,
)


def _read_gltf_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        if raw[:4] != b"glTF":
            if path.suffix.lower() == ".gltf":
                return json.loads(raw.decode("utf-8", errors="replace"))
            return {}
        json_len, json_type = struct.unpack_from("<II", raw, 12)
        if json_type != 0x4E4F534A:
            return {}
        return json.loads(raw[20:20 + json_len].rstrip(b"\x00"))
    except Exception:
        return {}


def prompt_expectations(prompt: str, expected_kind: str = "generic", motion_prompt: str | None = None) -> dict[str, bool]:
    text = " ".join(part for part in [prompt or "", motion_prompt or ""] if part).strip()
    printable_only = bool(PRINTABLE_ONLY_RE.search(text)) and not TEXTURE_RE.search(text)
    wants_realism = bool(REALISM_RE.search(text))
    wants_motion = bool((motion_prompt or "").strip()) or (bool(MOTION_RE.search(text)) and not NO_MOTION_RE.search(text))
    wants_texture = (
        not printable_only
        and not NO_TEXTURE_RE.search(text)
        and (
            bool(TEXTURE_RE.search(text))
            or wants_realism
            or expected_kind in HARD_SURFACE_KINDS
            or expected_kind in ORGANIC_KINDS
        )
    )
    allows_basic_primitive = (
        bool(PRIMITIVE_RE.search(text))
        and not ANTI_PRIMITIVE_RE.search(text)
        and not wants_realism
    )
    return {
        "wants_realism": wants_realism,
        "wants_texture": wants_texture,
        "wants_motion": wants_motion,
        "allows_basic_primitive": allows_basic_primitive,
        "printable_only": printable_only,
    }


def _norm_extents(extents: list[float] | None) -> list[float]:
    if not extents:
        return []
    longest = max(float(e) for e in extents) or 1.0
    return sorted([round(float(e) / longest, 3) for e in extents], reverse=True)


def _body_part_coverage(lower_target_names: list[str]) -> dict[str, bool]:
    def has_any(tokens: tuple[str, ...]) -> bool:
        return any(any(token in name for token in tokens) for name in lower_target_names)

    return {
        "root_or_pelvis": has_any(("root", "pelvis", "hip")),
        "torso": has_any(("spine", "chest", "torso")),
        "head": has_any(("head", "neck")),
        "shoulders": has_any(("shoulder", "clavicle")),
        "upper_arms": has_any(("upper_arm", "upperarm", "arm_")),
        "forearms": has_any(("forearm", "wrist", "hand")),
        "hands": has_any(("hand", "wrist", "finger", "palm")),
        "legs": has_any(("thigh", "shin", "knee", "foot", "leg")),
    }


def _animation_markers(gltf: dict[str, Any]) -> dict[str, Any]:
    animations = gltf.get("animations") or []
    nodes = gltf.get("nodes") or []
    accessors = gltf.get("accessors") or []
    total_channels = 0
    target_nodes: list[int] = []
    target_paths: set[str] = set()
    sampler_input_counts: list[int] = []
    sampler_interpolations: set[str] = set()
    for anim in animations:
        for sampler in anim.get("samplers") or []:
            sampler_interpolations.add(str(sampler.get("interpolation") or "LINEAR").upper())
            input_idx = sampler.get("input")
            if isinstance(input_idx, int) and 0 <= input_idx < len(accessors):
                accessor = accessors[input_idx] or {}
                if isinstance(accessor, dict) and isinstance(accessor.get("count"), int):
                    sampler_input_counts.append(int(accessor["count"]))
        for channel in anim.get("channels") or []:
            total_channels += 1
            target = channel.get("target") or {}
            if isinstance(target.get("node"), int):
                target_nodes.append(target["node"])
            if isinstance(target.get("path"), str):
                target_paths.add(target["path"])

    runtime_tokens = ("motion", "led", "oled", "atlas", "belt", "scroll", "kinematic")

    def walk(obj: Any) -> bool:
        if isinstance(obj, dict):
            schema = str(obj.get("schema") or "")
            if schema.startswith("aurora.") and any(k in schema for k in runtime_tokens):
                return True
            for key, value in obj.items():
                if str(key).startswith("aurora_") and any(token in str(key) for token in runtime_tokens):
                    return True
                if walk(value):
                    return True
        elif isinstance(obj, list):
            return any(walk(item) for item in obj)
        return False

    has_runtime_motion_extras = walk(gltf.get("materials") or []) or walk(gltf.get("nodes") or []) or walk(gltf.get("meshes") or [])
    unique_targets = set(target_nodes)
    root_only = bool(total_channels) and len(unique_targets) == 1 and next(iter(unique_targets), None) == 0
    real_channel_motion = bool(total_channels >= 2 and len(unique_targets) >= 2) or (
        bool(total_channels) and not root_only and ("rotation" in target_paths or "translation" in target_paths)
    ) or bool(total_channels and "weights" in target_paths)
    target_names = [
        nodes[i].get("name", f"node_{i}")
        for i in sorted(unique_targets)
        if isinstance(i, int) and 0 <= i < len(nodes)
    ]
    limb_tokens = (
        "bone", "armature", "mixamorig", "rig", "thigh", "shin", "foot", "toe",
        "leg", "knee", "hip", "pelvis", "spine", "chest", "shoulder", "upper_arm",
        "forearm", "hand", "walk", "gait",
    )
    lower_target_names = [str(name).lower() for name in target_names]
    has_limb_targets = any(any(token in name for token in limb_tokens) for name in lower_target_names)
    has_articulated_locomotion = bool(total_channels >= 4 and len(unique_targets) >= 3 and has_limb_targets)
    body_part_coverage = _body_part_coverage(lower_target_names)
    macarena_required_parts = (
        "root_or_pelvis", "torso", "head", "shoulders",
        "upper_arms", "forearms", "hands", "legs",
    )
    macarena_missing_parts = [
        part for part in macarena_required_parts
        if not body_part_coverage.get(part)
    ]
    floss_required_parts = (
        "root_or_pelvis", "torso", "shoulders",
        "upper_arms", "forearms", "hands", "legs",
    )
    floss_missing_parts = [
        part for part in floss_required_parts
        if not body_part_coverage.get(part)
    ]
    max_keyframes = max(sampler_input_counts) if sampler_input_counts else 0
    macarena_ready = bool(
        len(animations) == 1
        and total_channels >= 12
        and len(unique_targets) >= 10
        and max_keyframes >= 10
        and not macarena_missing_parts
        and has_limb_targets
        and not root_only
    )
    floss_ready = bool(
        len(animations) == 1
        and total_channels >= 12
        and len(unique_targets) >= 10
        and max_keyframes >= 10
        and not floss_missing_parts
        and has_limb_targets
        and not root_only
    )
    return {
        "has_animations": bool(animations),
        "animation_count": len(animations),
        "total_channels": total_channels,
        "unique_target_nodes": len(unique_targets),
        "target_paths": sorted(target_paths),
        "target_names": target_names[:16],
        "root_only": root_only,
        "has_limb_targets": has_limb_targets,
        "has_articulated_locomotion": has_articulated_locomotion,
        "body_part_coverage": body_part_coverage,
        "sampler_input_counts": sampler_input_counts[:16],
        "sampler_interpolations": sorted(sampler_interpolations),
        "max_keyframes_per_sampler": max_keyframes,
        "macarena_ready": macarena_ready,
        "macarena_missing_parts": macarena_missing_parts,
        "floss_ready": floss_ready,
        "floss_missing_parts": floss_missing_parts,
        "has_runtime_motion_extras": has_runtime_motion_extras,
        "has_real_motion": real_channel_motion or has_runtime_motion_extras,
    }


def _human_fidelity_markers(gltf: dict[str, Any], visual: dict[str, Any],
                            quality: dict[str, Any]) -> dict[str, Any]:
    """Detect whether a character mesh exposes enough detail for real people.

    This is a deterministic proxy, not facial recognition. It blocks the known
    failure mode: a simple colored mannequin being accepted as a real
    person/character reproduction.
    """

    names = [
        str(item.get("name") or "").lower()
        for bucket in (gltf.get("nodes") or [], gltf.get("meshes") or [], gltf.get("materials") or [])
        for item in bucket
        if isinstance(item, dict)
    ]

    def count_any(tokens: tuple[str, ...]) -> int:
        return sum(1 for name in names if any(token in name for token in tokens))

    density = (quality.get("scores") or {}).get("geometric_density") or {}
    color = (quality.get("scores") or {}).get("color_richness") or {}
    vertex_count = int(density.get("vertex_count", 0) or 0)
    texture_count = int(visual.get("n_textures", 0) or 0) if visual.get("ok") else 0
    image_count = int(visual.get("n_images", 0) or 0) if visual.get("ok") else 0
    textured_materials = int(visual.get("textured_materials", 0) or 0) if visual.get("ok") else 0
    material_spread = float(visual.get("palette_spread", 0.0) or 0.0) if visual.get("ok") else 0.0
    pbr_texture_signal = bool(texture_count > 0 or image_count > 0 or textured_materials > 0)
    high_detail_geometry = vertex_count >= 45000
    high_detail_textured = bool(pbr_texture_signal and vertex_count >= 30000)
    finger_name_count = count_any(("finger", "thumb", "index", "middle", "ring", "pinky", "phalange", "digit"))
    hand_name_count = count_any(("hand", "wrist", "palm"))
    face_name_count = count_any(("face", "head", "eye", "nose", "mouth", "jaw", "hair"))
    zone_name_count = count_any(("skin", "hair", "cloth", "shirt", "jacket", "pants", "shoe", "eye"))

    return {
        "vertex_count": vertex_count,
        "pbr_texture_signal": pbr_texture_signal,
        "texture_count": texture_count,
        "image_count": image_count,
        "textured_materials": textured_materials,
        "material_palette_spread": round(material_spread, 4),
        "high_detail_geometry": high_detail_geometry,
        "high_detail_textured": high_detail_textured,
        "hand_name_count": hand_name_count,
        "finger_name_count": finger_name_count,
        "face_name_count": face_name_count,
        "material_zone_name_count": zone_name_count,
        "has_named_hands": hand_name_count >= 2,
        "has_named_fingers": finger_name_count >= 4,
        "has_face_detail_names": face_name_count >= 3,
        "has_named_material_zones": zone_name_count >= 4,
        "color_material_score": int(color.get("score", 0) or 0),
    }


def _strimer_plus_v2_markers(gltf: dict[str, Any]) -> dict[str, Any]:
    """Detect product-specific Strimer Plus V2 structure in a GLB JSON chunk."""

    nodes = gltf.get("nodes") or []
    meshes = gltf.get("meshes") or []
    materials = gltf.get("materials") or []
    names = [
        str(item.get("name") or "").lower()
        for bucket in (nodes, meshes, materials)
        for item in bucket
        if isinstance(item, dict)
    ]

    def count(token: str) -> int:
        return sum(1 for name in names if token in name)

    def extras_walk(obj: Any, predicate) -> bool:
        if isinstance(obj, dict):
            if predicate(obj):
                return True
            return any(extras_walk(value, predicate) for value in obj.values())
        if isinstance(obj, list):
            return any(extras_walk(value, predicate) for value in obj)
        return False

    led_materials = [
        mat for mat in materials
        if isinstance(mat, dict)
        and (
            "aurora_led_emission" in (mat.get("extras") or {})
            or str(mat.get("name") or "").lower().startswith("strimerv2_ledmat")
        )
    ]
    product_reference = extras_walk(
        nodes,
        lambda obj: str((obj.get("extras") or {}).get("aurora_product_reference", {})).lower().find("strimer") >= 0,
    )
    channel_indexes = set()
    for mat in led_materials:
        extras = mat.get("extras") or {}
        led = extras.get("aurora_led_emission") or {}
        if isinstance(led.get("channel_index"), int):
            channel_indexes.add(led["channel_index"])

    return {
        "is_strimer_plus_v2_prompt": False,
        "product_reference": product_reference,
        "bonded_core": count("strimerv2_bondedsiliconecore_"),
        "light_guides": count("strimerv2_lightguide_"),
        "addressable_led_cells": count("strimerv2_led_"),
        "lower_cables": count("strimerv2_lowercable_"),
        "connector_blocks": count("strimerv2_connector_"),
        "socket_recesses": count("strimerv2_24pin_socket_recess_"),
        "input_contact_pins": count("strimerv2_24pin_input_contact_pin_"),
        "free_tail_cables": count("blackpsutail") + count("psu_tail"),
        "stable_clips": count("strimerv2_stableclip_"),
        "clear_alignment_clips": count("strimerv2_clearalignmentclip_"),
        "side_light_strips": count("strimerv2_sidelightstrip_"),
        "brand_marks": count("lian_li"),
        "led_materials": len(led_materials),
        "runtime_channels": len(channel_indexes),
        "has_surface_texture_extras": extras_walk(
            materials,
            lambda obj: "aurora_surface_texture" in (obj.get("extras") or {}),
        ),
    }


def _strimer_geometry_audit(path: Path) -> dict[str, Any]:
    """Measure Strimer stack adhesion from actual transformed node bounds."""

    try:
        import numpy as np
        import trimesh
    except Exception as exc:  # pragma: no cover - optional runtime deps
        return {"ok": False, "error": f"geometry deps unavailable: {exc}"}

    try:
        scene = trimesh.load(path, force="scene")
        if not hasattr(scene, "graph") or scene.bounds is None:
            return {"ok": False, "error": "not a scene"}
        extents = np.asarray(scene.bounds[1]) - np.asarray(scene.bounds[0])
        thickness_axis = int(np.argmin(extents))

        def group_bounds(token: str):
            bounds = []
            for node_name in scene.graph.nodes_geometry:
                if token not in str(node_name).lower():
                    continue
                transform, geom_name = scene.graph.get(node_name)
                geom = scene.geometry.get(geom_name)
                if geom is None or geom.bounds is None:
                    continue
                lo, hi = geom.bounds
                corners = np.array(
                    [[x, y, z, 1.0] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])],
                    dtype=float,
                )
                world = (transform @ corners.T).T[:, :3]
                bounds.append((world.min(axis=0), world.max(axis=0)))
            if not bounds:
                return None
            mins = np.min(np.stack([b[0] for b in bounds]), axis=0)
            maxs = np.max(np.stack([b[1] for b in bounds]), axis=0)
            return mins, maxs

        lower = group_bounds("strimerv2_lowercable_")
        guides = group_bounds("strimerv2_lightguide_")
        leds = group_bounds("strimerv2_led_")
        core = group_bounds("strimerv2_bondedsiliconecore_")

        def positive_gap(under, upper):
            if not under or not upper:
                return None
            return round(max(0.0, float(upper[0][thickness_axis] - under[1][thickness_axis])), 6)

        gaps = {
            "lower_to_lightguide_m": positive_gap(lower, guides),
            "lightguide_to_led_m": positive_gap(guides, leds),
        }
        real_gaps = [gap for gap in gaps.values() if gap is not None]
        max_gap = max(real_gaps) if real_gaps else None
        central_stack_bounds = [b for b in (lower, guides, leds, core) if b]
        if central_stack_bounds:
            stack_min = min(float(b[0][thickness_axis]) for b in central_stack_bounds)
            stack_max = max(float(b[1][thickness_axis]) for b in central_stack_bounds)
            stack_thickness = round(stack_max - stack_min, 6)
        else:
            stack_thickness = None

        node_names = [str(node).lower() for node in scene.graph.nodes_geometry]
        return {
            "ok": True,
            "thickness_axis": thickness_axis,
            "scene_extents_m": [round(float(v), 6) for v in extents],
            "bonded_core_present": core is not None,
            "layer_gaps_m": gaps,
            "max_positive_layer_gap_m": max_gap,
            "central_stack_thickness_m": stack_thickness,
            "free_tail_cables": sum(1 for name in node_names if "blackpsutail" in name or "psu_tail" in name),
            "input_contact_pins": sum(1 for name in node_names if "strimerv2_24pin_input_contact_pin_" in name),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"strimer geometry audit failed: {type(exc).__name__}: {exc}"}


def _load_proxy_reports(mesh_path: Path, expected_kind: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        from mesh_quality_score import score_mesh
    except Exception as exc:
        quality = {"ok": False, "error": f"mesh_quality_score unavailable: {exc}"}
    else:
        quality = score_mesh(mesh_path, expected_kind)

    try:
        from mesh_visual_audit import audit as visual_audit
    except Exception as exc:
        visual = {"ok": False, "error": f"mesh_visual_audit unavailable: {exc}"}
    else:
        visual = visual_audit(mesh_path)
    return quality, visual


def acceptance_threshold(expectations: dict[str, bool], expected_kind: str) -> int:
    threshold = 70  # Lowered base threshold
    if expectations["wants_texture"] or expectations["wants_realism"]:
        threshold = 72
    if expected_kind in HARD_SURFACE_KINDS:
        threshold = max(threshold, 74)
    if expectations["wants_motion"]:
        threshold = max(threshold, 74)
    if expected_kind in ORGANIC_KINDS and expectations["wants_realism"]:
        threshold = max(threshold, 76)
    return threshold


def _quality_score_for_acceptance(quality: dict[str, Any], texture_signal: bool) -> float:
    base = float(quality.get("overall_score", 0.0)) if quality.get("ok") else 0.0
    if not texture_signal or not quality.get("ok"):
        return base
    scores = quality.get("scores") or {}
    weighted_axes = [
        ("geometric_density", 0.20),
        ("silhouette_aspect", 0.30),
        ("manifold_health", 0.15),
        ("surface_quality", 0.15),
    ]
    weighted_total = 0.0
    weight_sum = 0.0
    for axis, weight in weighted_axes:
        payload = scores.get(axis) or {}
        try:
            weighted_total += float(payload.get("score", 0.0)) * weight
            weight_sum += weight
        except (TypeError, ValueError):
            pass
    if weight_sum <= 0:
        return base
    without_vertex_color_proxy = weighted_total / weight_sum
    return round(max(base, without_vertex_color_proxy), 1)


def evaluate_acceptance(
    mesh_path: str | Path,
    prompt: str,
    expected_kind: str = "generic",
    motion_prompt: str | None = None,
    require_motion: bool | None = None,
) -> dict[str, Any]:
    path = Path(mesh_path)
    if not path.is_file():
        return {
            "ok": False,
            "schema": "aurora.mesh_acceptance.v1",
            "error": f"mesh not found: {path}",
        }

    kind = (expected_kind or "generic").lower().strip()
    expectations = prompt_expectations(prompt, kind, motion_prompt)
    if require_motion is not None:
        expectations["wants_motion"] = bool(require_motion)
    quality, visual = _load_proxy_reports(path, kind)
    gltf = _read_gltf_json(path)
    motion = _animation_markers(gltf) if gltf else {
        "has_animations": False,
        "animation_count": 0,
        "total_channels": 0,
        "unique_target_nodes": 0,
        "target_paths": [],
        "target_names": [],
        "root_only": False,
        "has_runtime_motion_extras": False,
        "has_real_motion": False,
    }
    strimer_audit = _strimer_plus_v2_markers(gltf) if gltf else {}
    strimer_geometry = _strimer_geometry_audit(path) if gltf else {}
    human_audit = _human_fidelity_markers(gltf, visual, quality) if gltf else {}
    combined_prompt_text = " ".join([prompt or "", motion_prompt or ""])
    strimer_prompt = bool(STRIMER_PLUS_V2_RE.search(" ".join([prompt or "", motion_prompt or ""])))
    if strimer_audit:
        strimer_audit["is_strimer_plus_v2_prompt"] = strimer_prompt

    visual_issues = list(visual.get("issues") or []) if visual.get("ok") else [visual.get("error", "visual audit unavailable")]
    retry_reasons = list(quality.get("retry_reasons") or []) if quality.get("ok") else [quality.get("error", "quality score unavailable")]
    effective_retry_reasons = list(retry_reasons)
    suppressed_quality_reasons: list[str] = []
    hard_failures: list[str] = []
    warnings: list[str] = []

    extents = visual.get("extents_m") if visual.get("ok") else None
    norm = _norm_extents(extents)
    cubic_like = bool(norm and (norm[0] - norm[-1] < 0.15))
    if cubic_like and kind not in OPEN_PRIMITIVE_KINDS and not expectations["allows_basic_primitive"]:
        hard_failures.append("cube-like bounding box; likely primitive/block placeholder")

    n_materials = int(visual.get("n_materials", 0) or 0) if visual.get("ok") else 0
    n_textures = int(visual.get("n_textures", 0) or 0) if visual.get("ok") else 0
    n_images = int(visual.get("n_images", 0) or 0) if visual.get("ok") else 0
    has_uv_map = bool(visual.get("has_uv_map")) if visual.get("ok") else False
    has_pbr_texture_signal = n_materials > 0 and has_uv_map and (n_textures > 0 or n_images > 0)
    has_runtime_material_signal = n_materials > 0 and bool(motion["has_runtime_motion_extras"])
    human_fidelity_prompt = bool(kind in ORGANIC_KINDS and HUMAN_FIDELITY_RE.search(combined_prompt_text))
    hand_fidelity_prompt = bool(
        kind in ORGANIC_KINDS
        and (
            HAND_FIDELITY_RE.search(combined_prompt_text)
            or MACARENA_RE.search(combined_prompt_text)
            or FLOSS_RE.search(combined_prompt_text)
            or re.search(r"\b(danse|danser|dance|dancing|gesture|gestuelle)\b", combined_prompt_text, re.IGNORECASE)
        )
    )

    threshold = acceptance_threshold(expectations, kind)
    visual_grade = int(visual.get("visual_grade", 0)) if visual.get("ok") else 0
    quality_score = _quality_score_for_acceptance(quality, has_pbr_texture_signal)
    engineer_grade = round(0.55 * visual_grade + 0.45 * quality_score, 1)

    if engineer_grade < threshold:
        hard_failures.append(f"engineer_grade {engineer_grade} < threshold {threshold}")

    if has_pbr_texture_signal or has_runtime_material_signal:
        suppressed_quality_reasons = [
            reason for reason in retry_reasons
            if str(reason).startswith("color_richness ")
        ]
        if quality_score >= 60:
            suppressed_quality_reasons.extend(
                reason for reason in retry_reasons
                if str(reason).startswith("overall ")
            )
        if suppressed_quality_reasons:
            effective_retry_reasons = [
                reason for reason in retry_reasons
                if reason not in suppressed_quality_reasons
            ]

    if expectations["wants_texture"]:
        texture_missing = (
            n_materials == 0
            or (
                not has_uv_map
                and n_textures == 0
                and n_images == 0
                and not motion["has_runtime_motion_extras"]
            )
        )
        pasted = any("pasted-image" in issue for issue in visual_issues)
        if texture_missing:
            hard_failures.append("texture required but UV/material/embedded texture data is missing")
        if pasted:
            hard_failures.append("texture appears pasted onto a simple surface instead of UV-baked")

    if human_fidelity_prompt:
        if not human_audit.get("pbr_texture_signal"):
            hard_failures.append(
                "human/character fidelity requested but mesh has no embedded PBR texture/image data; "
                "flat material colors are not enough for a real person or recognizable character"
            )
        if int(human_audit.get("vertex_count", 0) or 0) < 30000:
            hard_failures.append(
                "human/character fidelity requested but geometry is too low-detail for face, clothing and hands"
            )
        if not (
            human_audit.get("has_face_detail_names")
            or human_audit.get("high_detail_textured")
        ):
            hard_failures.append(
                "human/character fidelity requested but face/hair detail is not verifiable"
            )
    if hand_fidelity_prompt:
        if not (
            human_audit.get("has_named_fingers")
            or human_audit.get("high_detail_textured")
        ):
            hard_failures.append(
                "hand-critical motion requested but fingers/palms are not verifiable as real hand detail"
            )

    if expectations["wants_motion"]:
        if motion.get("root_only"):
            hard_failures.append("motion required but animation targets only the root object (fake whole-object motion)")
        elif not motion["has_real_motion"]:
            hard_failures.append("motion required but GLB has no real animation channels or Aurora runtime motion extras")
        if MACARENA_RE.search(" ".join([prompt or "", motion_prompt or ""])):
            if not motion.get("macarena_ready"):
                missing = ", ".join(motion.get("macarena_missing_parts") or ["unknown"])
                hard_failures.append(
                    "Macarena requested but animation is not a complete full-body Macarena "
                    f"(missing/weak: {missing}; requires one unified clip, head, shoulders, arms, forearms, torso, legs and >=10 keyframes)"
                )
        if FLOSS_RE.search(" ".join([prompt or "", motion_prompt or ""])):
            if not motion.get("floss_ready"):
                missing = ", ".join(motion.get("floss_missing_parts") or ["unknown"])
                hard_failures.append(
                    "Floss requested but animation is not a complete floss dance "
                    f"(missing/weak: {missing}; requires one unified clip, arms swinging front/back, hands/fists, hips/pelvis opposite arms, torso, legs and >=10 keyframes)"
                )
        if LOCOMOTION_RE.search(" ".join([prompt or "", motion_prompt or ""])):
            if not motion.get("has_articulated_locomotion"):
                hard_failures.append("locomotion requested but animation has no articulated limb/arm/leg/pelvis targets")

    if strimer_prompt:
        expected_guides = 8 if re.search(r"\b(8[\s-]?pin|pcie|12vhpwr|12\+4)\b", prompt or "", re.IGNORECASE) else 12
        expected_led_floor = 80 if expected_guides == 8 else 96
        if int(strimer_audit.get("light_guides", 0) or 0) < expected_guides:
            hard_failures.append(f"Strimer Plus V2 requires at least {expected_guides} visible light guides")
        if int(strimer_audit.get("addressable_led_cells", 0) or 0) < expected_led_floor:
            hard_failures.append("Strimer Plus V2 requires many addressable LED cells, not a few glowing dots")
        if int(strimer_audit.get("lower_cables", 0) or 0) < 16:
            hard_failures.append("Strimer Plus V2 lower single-row power cables are missing")
        if int(strimer_audit.get("bonded_core", 0) or 0) < 1:
            hard_failures.append("Strimer Plus V2 bonded silicone/TPE core is missing; layers may float")
        if int(strimer_audit.get("connector_blocks", 0) or 0) < 2:
            hard_failures.append("Strimer Plus V2 needs black connector blocks at both ends")
        if expected_guides == 12 and int(strimer_audit.get("socket_recesses", 0) or 0) < 20:
            hard_failures.append("24-pin Strimer Plus V2 connector socket grid is missing")
        if expected_guides == 12 and int(strimer_audit.get("input_contact_pins", 0) or 0) < 20:
            hard_failures.append("24-pin Strimer Plus V2 input connector contacts are missing")
        if int(strimer_audit.get("free_tail_cables", 0) or 0) > 0:
            hard_failures.append("Strimer Plus V2 must terminate in connector faces, not free cable tails plugged into a cable")
        if int(strimer_audit.get("stable_clips", 0) or 0) < 6:
            hard_failures.append("Strimer Plus V2 stable clip geometry is missing")
        if int(strimer_audit.get("side_light_strips", 0) or 0) < 2:
            hard_failures.append("Strimer Plus V2 side light strips are missing")
        if int(strimer_audit.get("brand_marks", 0) or 0) < 1:
            hard_failures.append("Lian Li / Strimer identity mark is missing")
        if int(strimer_audit.get("runtime_channels", 0) or 0) < 4:
            hard_failures.append("Strimer Plus V2 ARGB channel animation data is missing")
        if not strimer_audit.get("has_surface_texture_extras"):
            hard_failures.append("Strimer Plus V2 silicone/TPE surface texture metadata is missing")
        if strimer_geometry.get("ok"):
            if int(strimer_geometry.get("free_tail_cables", 0) or 0) > 0:
                hard_failures.append("Strimer Plus V2 geometry contains free tail cable nodes")
            if not strimer_geometry.get("bonded_core_present"):
                hard_failures.append("Strimer Plus V2 geometry lacks a bonded central stack")
            max_gap = strimer_geometry.get("max_positive_layer_gap_m")
            if isinstance(max_gap, (int, float)) and max_gap > 0.0006:
                hard_failures.append(f"Strimer Plus V2 layers are visibly separated in side view ({max_gap:.4f} m gap)")
            if expected_guides == 12 and int(strimer_geometry.get("input_contact_pins", 0) or 0) < 20:
                hard_failures.append("Strimer Plus V2 input contact geometry is missing")
        elif strimer_geometry:
            warnings.append(strimer_geometry.get("error", "Strimer geometry audit unavailable"))

    if quality.get("ok") and quality.get("retry_recommended") and effective_retry_reasons:
        warnings.extend(effective_retry_reasons)

    all_issues = visual_issues + effective_retry_reasons + warnings
    suggested_fixes: list[str] = []
    if any("texture" in failure.lower() or "uv" in failure.lower() for failure in hard_failures):
        suggested_fixes.append("run auto_rescue/bake_to_texture or regenerate with stronger PBR texture contract")
    if any("cube" in failure.lower() or "primitive" in failure.lower() for failure in hard_failures):
        suggested_fixes.append("regenerate with multi-view reference and stronger silhouette/part-structure constraints")
    if any("motion" in failure.lower() or "animation" in failure.lower() for failure in hard_failures):
        suggested_fixes.append("run auto-motion-bake and verify glTF animations or Aurora LED/OLED extras")
    if any("macarena" in failure.lower() or "floss" in failure.lower() for failure in hard_failures):
        suggested_fixes.append("rewrite motion as a structured full-body dance contract with required body-part targets and rerun motion bake")
    if any("strimer" in failure.lower() for failure in hard_failures):
        suggested_fixes.append("route to the dedicated strimer_plus_v2_cable procedural template and compare against official reference markers")
    if any("human/character" in failure.lower() or "hand-critical" in failure.lower() for failure in hard_failures):
        suggested_fixes.append("regenerate through multi-view human fidelity references with visible palms/fingers, face detail and texture-bearing skin/hair/clothing")
    if effective_retry_reasons:
        suggested_fixes.append("retry the 3D pipeline or route to DreamGaussian/procedural based on failed axes")

    acceptance_ok = not hard_failures
    return {
        "ok": True,
        "schema": "aurora.mesh_acceptance.v1",
        "mesh_path": str(path),
        "prompt": prompt,
        "expected_kind": kind,
        "acceptance_ok": acceptance_ok,
        "verdict": "accepted" if acceptance_ok else "rejected",
        "engineer_grade": engineer_grade,
        "threshold": threshold,
        "expectations": expectations,
        "hard_failures": hard_failures,
        "warnings": warnings,
        "all_issues": all_issues,
        "suggested_fixes": list(dict.fromkeys(suggested_fixes)),
        "suppressed_quality_reasons": suppressed_quality_reasons,
        "quality_score": quality,
        "visual_audit": visual,
        "motion_audit": motion,
        "human_fidelity_audit": human_audit,
        "product_audit": (
            {"strimer_plus_v2": {**strimer_audit, "geometry": strimer_geometry}}
            if strimer_audit else {}
        ),
        "normalized_extents_sorted_desc": norm,
    }


def render_pretty(report: dict[str, Any]) -> str:
    if not report.get("ok"):
        return f"FAIL: {report.get('error')}\n"
    lines = [
        f"Mesh acceptance - {report['mesh_path']}",
        f"Verdict: {report['verdict']}  grade={report['engineer_grade']}/{report['threshold']}",
        f"Expectations: {report['expectations']}",
    ]
    if report.get("hard_failures"):
        lines.append("Hard failures:")
        for item in report["hard_failures"]:
            lines.append(f"  - {item}")
    if report.get("suggested_fixes"):
        lines.append("Suggested fixes:")
        for item in report["suggested_fixes"]:
            lines.append(f"  - {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora 3D final acceptance gate")
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--kind", default="generic")
    parser.add_argument("--motion-prompt", default=None)
    parser.add_argument("--ignore-motion", action="store_true",
                        help="Do not reject for missing animation; useful before a later motion-bake stage.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    report = evaluate_acceptance(
        args.mesh,
        args.prompt,
        args.kind,
        args.motion_prompt,
        require_motion=False if args.ignore_motion else None,
    )
    if args.pretty:
        sys.stdout.write(render_pretty(report))
    else:
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
