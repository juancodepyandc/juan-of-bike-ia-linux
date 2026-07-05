#!/usr/bin/env python
"""Heavy Blender CLI test for AuroraIA's 3D module.

This runner intentionally does not call the AI mesh generator. It exercises the
local Blender toolchain directly and produces a full animated scene with:

- coherent 3D text labels embedded as glTF node extras,
- multi-part hard-surface geometry,
- real glTF animation channels,
- an embedded texture signal for the acceptance gate,
- still renders, optional MP4 preview, and JSON audits.

Usage:
    python application/python-services/three_d_blender_heavy_test.py --pretty
    python application/python-services/three_d_blender_heavy_test.py --render-video --pretty
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SERVICES_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "application" / "output" / "3d" / "blender_heavy"

if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

EXPECTED_TEXT_LABELS = [
    "AURORA 3D MODULE",
    "BLENDER 5.1 CLI",
    "TEXT COHERENCE OK",
    "ANIMATION TIMELINE",
    "BELT DRIVE 2:1",
    "ROBOT ARM",
    "DRONE LIFT",
    "VERIFY BEFORE ACCEPT",
]

SCENE_PROMPT = (
    "Aurora full Blender 5.1 CLI coherent animated 3D scene with PBR materials, "
    "embedded readable labels, belt drive ratio 2:1, robot arm, lifting drone, "
    "data portal, timeline marker, no cube placeholder, verify before accept"
)

MOTION_PROMPT = (
    "pulleys rotate continuously, robot arm articulates, drone propellers spin "
    "and lift, data portal pulses, timeline marker moves"
)


def _find_blender() -> str | None:
    try:
        from blender_bridge import find_blender as bridge_find_blender

        found = bridge_find_blender()
        if found and Path(found).is_file():
            return found
    except Exception:
        pass

    env_path = os.environ.get("BLENDER_BIN") or os.environ.get("BLENDER_EXE")
    if env_path and Path(env_path).is_file():
        return env_path

    which = shutil.which("blender") or shutil.which("blender.exe")
    if which:
        return which

    candidates = []
    if os.name == "nt":
        root = Path(r"C:\Program Files\Blender Foundation")
        if root.is_dir():
            candidates.extend(sorted(root.glob("Blender */blender.exe"), reverse=True))
        candidates.extend(
            Path(path)
            for path in [
                r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
                r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
                r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
                r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
                r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
            ]
        )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _read_gltf_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        raw = p.read_bytes()
        if raw[:4] != b"glTF":
            if p.suffix.lower() == ".gltf":
                return json.loads(raw.decode("utf-8", errors="replace"))
            return {}
        json_len, json_type = struct.unpack_from("<II", raw, 12)
        if json_type != 0x4E4F534A:
            return {}
        return json.loads(raw[20 : 20 + json_len].rstrip(b"\x00"))
    except Exception:
        return {}


def _text_audit(glb_path: str | Path) -> dict[str, Any]:
    gltf = _read_gltf_json(glb_path)
    found: list[str] = []
    for node in gltf.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        extras = node.get("extras") or {}
        value = extras.get("aurora_text")
        if isinstance(value, str):
            found.append(value)
    missing = [label for label in EXPECTED_TEXT_LABELS if label not in found]
    return {
        "ok": not missing,
        "expected": EXPECTED_TEXT_LABELS,
        "found": found,
        "missing": missing,
        "count": len(found),
    }


def _animation_audit(glb_path: str | Path) -> dict[str, Any]:
    gltf = _read_gltf_json(glb_path)
    nodes = gltf.get("nodes") or []
    accessors = gltf.get("accessors") or []
    animations = gltf.get("animations") or []
    total_channels = 0
    target_nodes: set[int] = set()
    target_paths: set[str] = set()
    keyframe_counts: list[int] = []
    target_names: list[str] = []

    for anim in animations:
        for sampler in anim.get("samplers") or []:
            input_idx = sampler.get("input")
            if isinstance(input_idx, int) and 0 <= input_idx < len(accessors):
                count = (accessors[input_idx] or {}).get("count")
                if isinstance(count, int):
                    keyframe_counts.append(count)
        for channel in anim.get("channels") or []:
            total_channels += 1
            target = channel.get("target") or {}
            node_idx = target.get("node")
            if isinstance(node_idx, int):
                target_nodes.add(node_idx)
            path = target.get("path")
            if isinstance(path, str):
                target_paths.add(path)

    for node_idx in sorted(target_nodes):
        if 0 <= node_idx < len(nodes):
            target_names.append(str((nodes[node_idx] or {}).get("name") or f"node_{node_idx}"))

    return {
        "ok": bool(animations) and total_channels >= 10 and len(target_nodes) >= 6,
        "animation_count": len(animations),
        "total_channels": total_channels,
        "unique_target_nodes": len(target_nodes),
        "target_paths": sorted(target_paths),
        "target_names": target_names[:32],
        "max_keyframes": max(keyframe_counts) if keyframe_counts else 0,
        "keyframe_counts": keyframe_counts[:32],
    }


def _pixel_audit(paths: list[str]) -> dict[str, Any]:
    try:
        from PIL import Image, ImageStat
    except Exception as exc:
        return {"ok": False, "error": f"PIL unavailable: {exc}"}

    reports: list[dict[str, Any]] = []
    for item in paths:
        p = Path(item)
        if not p.is_file():
            reports.append({"path": str(p), "ok": False, "error": "missing"})
            continue
        try:
            with Image.open(p) as im:
                rgb = im.convert("RGB").resize((96, 54))
                stat = ImageStat.Stat(rgb)
                variance = float(max(stat.var))
                mean = sum(stat.mean) / 3.0
            reports.append({
                "path": str(p),
                "ok": variance > 4.0,
                "variance": round(variance, 3),
                "mean": round(mean, 3),
            })
        except Exception as exc:
            reports.append({"path": str(p), "ok": False, "error": str(exc)})
    failed = [item for item in reports if not item.get("ok")]
    return {"ok": not failed and bool(reports), "images": reports, "failed": failed}


def _build_contact_sheet(images: list[dict[str, Any]], out_path: Path) -> dict[str, Any]:
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        return {"ok": False, "error": f"PIL unavailable: {exc}"}

    valid = [item for item in images if Path(str(item.get("path") or "")).is_file()]
    if not valid:
        return {"ok": False, "error": "no images"}
    tile_w, tile_h, label_h = 320, 240, 28
    cols = 3
    rows = (len(valid) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile_w, rows * (tile_h + label_h)), (18, 20, 24))
    draw = ImageDraw.Draw(sheet)
    for index, shot in enumerate(valid):
        path = Path(str(shot.get("path")))
        try:
            img = Image.open(path).convert("RGB")
            img.thumbnail((tile_w, tile_h))
        except Exception:
            continue
        x = (index % cols) * tile_w
        y = (index // cols) * (tile_h + label_h)
        label = str(shot.get("view") or path.stem)
        draw.text((x + 8, y + 7), label, fill=(235, 239, 245))
        paste_x = x + (tile_w - img.width) // 2
        paste_y = y + label_h + (tile_h - img.height) // 2
        sheet.paste(img, (paste_x, paste_y))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return {"ok": True, "path": str(out_path)}


def _render_mesh_screenshots(glb_path: str | Path, out_dir: Path) -> dict[str, Any]:
    try:
        from mesh_screenshot import render_mesh_screenshots
    except Exception as exc:
        return {"ok": False, "error": f"mesh_screenshot unavailable: {exc}"}

    out_dir.mkdir(parents=True, exist_ok=True)
    views = ["front", "front_3q", "left", "right", "back", "back_3q", "top", "iso"]
    result = render_mesh_screenshots(
        str(glb_path),
        str(out_dir / "audit_view.png"),
        views=views,
        resolution=(768, 768),
    )
    if result.get("ok"):
        pixel_paths = [str(item.get("path")) for item in result.get("screenshots") or []]
        result["pixel_audit"] = _pixel_audit(pixel_paths)
        result["contact_sheet"] = _build_contact_sheet(
            result.get("screenshots") or [],
            out_dir / "contact_sheet.png",
        )
    return result


BLENDER_SCENE_SCRIPT = r'''
import json
import math
import os
import random
import sys

import bpy
import mathutils


def _argv():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


argv = _argv()
paths = json.loads(argv[0]) if argv else {}
settings = json.loads(argv[1]) if len(argv) > 1 else {}

out_glb = paths["glb"]
out_blend = paths["blend"]
render_dir = paths["render_dir"]
preview_mp4 = paths["preview_mp4"]
texture_path = paths["texture_path"]
render_video = bool(settings.get("render_video", False))
fps = int(settings.get("fps", 24))
frame_end = int(settings.get("frame_end", 144))

os.makedirs(render_dir, exist_ok=True)
os.makedirs(os.path.dirname(out_glb), exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = frame_end
scene.render.fps = fps
scene.render.resolution_x = int(settings.get("width", 1280))
scene.render.resolution_y = int(settings.get("height", 720))
scene.render.film_transparent = False

try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
try:
    scene.eevee.taa_render_samples = 64
except Exception:
    pass
try:
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
except Exception:
    pass

rng = random.Random(7331)


def set_world():
    world = scene.world or bpy.data.worlds.new("AuroraHeavyWorld")
    scene.world = world
    world.color = (0.025, 0.035, 0.052)


def make_mat(name, color, metallic=0.0, roughness=0.5, emission=None, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], alpha)
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if alpha < 1.0 and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
            mat.blend_method = "BLEND"
            mat.use_screen_refraction = True
        if emission:
            em_color, strength = emission
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (em_color[0], em_color[1], em_color[2], 1.0)
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = (em_color[0], em_color[1], em_color[2], 1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def make_status_image():
    w, h = 512, 256
    img = bpy.data.images.new("Aurora_Status_Texture", w, h, alpha=True, float_buffer=False)
    pixels = [0.0] * (w * h * 4)
    for y in range(h):
        for x in range(w):
            row = y / max(1, h - 1)
            col = x / max(1, w - 1)
            base = (0.02, 0.05, 0.09)
            if 35 < x < 477 and (48 < y < 76 or 118 < y < 146 or 188 < y < 216):
                base = (0.05 + 0.15 * col, 0.28 + 0.35 * row, 0.42 + 0.35 * col)
            if (x // 18 + y // 18) % 2 == 0:
                base = tuple(min(1.0, c + 0.035) for c in base)
            # Three deterministic graph lines.
            line_y = int(58 + 18 * math.sin(x * 0.035))
            line_y2 = int(128 + 14 * math.sin(x * 0.052 + 1.5))
            line_y3 = int(198 + 12 * math.sin(x * 0.071 + 0.8))
            if abs(y - line_y) <= 2:
                base = (0.20, 0.95, 0.72)
            if abs(y - line_y2) <= 2:
                base = (0.95, 0.66, 0.24)
            if abs(y - line_y3) <= 2:
                base = (0.54, 0.68, 1.0)
            idx = (y * w + x) * 4
            pixels[idx:idx + 4] = [base[0], base[1], base[2], 1.0]
    img.pixels.foreach_set(pixels)
    img.filepath_raw = texture_path
    img.file_format = "PNG"
    img.save()
    img.pack()
    return img


def make_texture_mat(name, image, emission_strength=0.4):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if "Emission Color" in bsdf.inputs:
        links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.36
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


set_world()
status_img = make_status_image()

mat_floor = make_texture_mat("Mat_embedded_grid_texture", status_img, 0.05)
mat_wall = make_mat("Mat_wall_graphite", (0.075, 0.088, 0.105), 0.0, 0.62)
mat_table = make_mat("Mat_table_burnished_wood", (0.34, 0.20, 0.10), 0.0, 0.48)
mat_dark = make_mat("Mat_anodized_black", (0.015, 0.017, 0.021), 0.35, 0.34)
mat_steel = make_mat("Mat_brushed_steel", (0.58, 0.62, 0.67), 0.9, 0.22)
mat_brass = make_mat("Mat_ratio_brass", (0.92, 0.66, 0.22), 0.85, 0.26)
mat_belt = make_mat("Mat_runtime_belt_scroll", (0.018, 0.018, 0.021), 0.0, 0.72)
mat_belt["aurora_belt_scroll"] = {"schema": "aurora.belt-scroll.v1", "speed": 1.2, "axis": "u", "ratio": "2:1"}
mat_red = make_mat("Mat_safety_red", (0.78, 0.08, 0.07), 0.05, 0.43)
mat_blue = make_mat("Mat_scanner_blue", (0.10, 0.42, 0.96), 0.1, 0.28, emission=((0.10, 0.42, 0.96), 1.4))
mat_green = make_mat("Mat_verified_green", (0.10, 0.86, 0.52), 0.0, 0.35, emission=((0.10, 0.86, 0.52), 1.2))
mat_orange = make_mat("Mat_motion_orange", (1.0, 0.46, 0.12), 0.05, 0.32, emission=((1.0, 0.36, 0.08), 1.6))
mat_text = make_mat("Mat_text_clear_white", (0.90, 0.96, 1.0), 0.0, 0.27, emission=((0.55, 0.85, 1.0), 0.9))
mat_text_green = make_mat("Mat_text_green_ok", (0.52, 1.0, 0.78), 0.0, 0.25, emission=((0.24, 1.0, 0.58), 1.2))
mat_glass = make_mat("Mat_portal_glass", (0.22, 0.58, 1.0), 0.0, 0.08, emission=((0.08, 0.38, 1.0), 0.8), alpha=0.38)


def apply_bevel(obj, amount=0.015, segments=2):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bevel = obj.modifiers.new("production_bevel", "BEVEL")
    bevel.width = amount
    bevel.segments = segments
    bevel.affect = "EDGES"
    weighted = obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    try:
        bpy.ops.object.shade_smooth()
        bpy.ops.object.modifier_apply(modifier=bevel.name)
        bpy.ops.object.modifier_apply(modifier=weighted.name)
    except Exception:
        pass
    obj.select_set(False)
    return obj


def box(name, loc, scale, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    if bevel > 0:
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        apply_bevel(obj, bevel, 3)
    return obj


def cyl(name, loc, radius, depth, mat, vertices=64, rotation=(0, 0, 0), bevel=False):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    if bevel:
        apply_bevel(obj, 0.008, 2)
    return obj


def sphere(name, loc, radius, mat, segments=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=max(8, segments // 2), radius=radius, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    return obj


def torus(name, loc, major, minor, mat, rotation=(0, 0, 0), major_segments=96, minor_segments=12):
    bpy.ops.mesh.primitive_torus_add(
        major_segments=major_segments,
        minor_segments=minor_segments,
        major_radius=major,
        minor_radius=minor,
        location=loc,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    return obj


def uv_plane(name, loc, sx, sz, mat, rotation=(math.radians(90), 0, 0)):
    mesh = bpy.data.meshes.new(name + "Mesh")
    verts = [(-sx / 2, -sz / 2, 0), (sx / 2, -sz / 2, 0), (sx / 2, sz / 2, 0), (-sx / 2, sz / 2, 0)]
    faces = [(0, 1, 2, 3)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    uv = mesh.uv_layers.new(name="UVMap")
    coords = [(0, 0), (1, 0), (1, 1), (0, 1)]
    for loop_index, uv_coord in enumerate(coords):
        uv.data[loop_index].uv = uv_coord
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = rotation
    obj.data.materials.append(mat)
    return obj


def add_text(name, body, loc, size, mat, rotation=(math.radians(90), 0, 0)):
    curve = bpy.data.curves.new(name + "Curve", "FONT")
    curve.body = body
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.space_character = 1.08
    curve.space_word = 1.12
    curve.extrude = size * 0.035
    curve.resolution_u = 16
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = rotation
    obj.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    mesh_obj = bpy.context.object
    mesh_obj.name = name
    mesh_obj["aurora_text"] = body
    mesh_obj["aurora_text_contract"] = "exact"
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    return mesh_obj


def key_linear(obj):
    if obj.animation_data and obj.animation_data.action:
        for fcurve in obj.animation_data.action.fcurves:
            for kp in fcurve.keyframe_points:
                kp.interpolation = "LINEAR"


def look_at(obj, target):
    direction = mathutils.Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def animate_rotation(obj, axis, turns, start=1, end=frame_end):
    obj.rotation_mode = "XYZ"
    base = list(obj.rotation_euler)
    obj.keyframe_insert("rotation_euler", frame=start)
    base[axis] += turns * math.tau
    obj.rotation_euler = base
    obj.keyframe_insert("rotation_euler", frame=end)
    key_linear(obj)


# Environment and lab shell.
floor = uv_plane("Textured_Floor_Embedded_UV", (0, 0, 0), 5.6, 4.0, mat_floor, rotation=(0, 0, 0))
back_wall = uv_plane("Back_Wall_Status_Texture", (0, 1.92, 1.35), 5.6, 2.6, mat_floor, rotation=(math.radians(90), 0, 0))
box("Workbench_Wood_Slab", (0, -0.1, 0.58), (2.8, 1.05, 0.10), mat_table, 0.018)
for x in (-1.25, 1.25):
    for y in (-0.55, 0.35):
        box("Workbench_Leg", (x, y, 0.29), (0.08, 0.08, 0.55), mat_dark, 0.01)

for i, x in enumerate([-2.35, -1.65, -0.95, -0.25, 0.45, 1.15, 1.85, 2.55]):
    panel = box(f"Rear_Panel_{i}", (x, 1.86, 0.72), (0.022, 0.035, 0.72), mat_wall, 0.006)
    panel["aurora_scene_role"] = "structured background panel"

add_text("Label_Aurora_Module", "AURORA 3D MODULE", (0.0, 1.825, 2.18), 0.145, mat_text)
add_text("Label_Blender_CLI", "BLENDER 5.1 CLI", (-1.92, 1.82, 1.82), 0.078, mat_text)
add_text("Label_Text_OK", "TEXT COHERENCE OK", (1.62, 1.82, 1.82), 0.070, mat_text_green)
add_text("Label_Animation_Timeline", "ANIMATION TIMELINE", (0, -1.45, 0.092), 0.074, mat_text, rotation=(0, 0, 0))
add_text("Label_Verify", "VERIFY BEFORE ACCEPT", (1.25, 1.82, 0.42), 0.062, mat_text_green)

# Animated belt drive with real ratio.
drive_x, driven_x = -0.76, 0.42
pulley_z, pulley_y = 0.84, -0.34
pulley_a = torus("Belt_Drive_Driver_Pulley_2turns", (drive_x, pulley_y, pulley_z), 0.155, 0.022, mat_brass, rotation=(0, 0, 0))
pulley_b = torus("Belt_Drive_Driven_Pulley_1turn", (driven_x, pulley_y, pulley_z), 0.235, 0.026, mat_steel, rotation=(0, 0, 0))
cyl("Driver_Axle", (drive_x, pulley_y, pulley_z), 0.028, 0.24, mat_steel, vertices=48, rotation=(math.radians(90), 0, 0), bevel=True)
cyl("Driven_Axle", (driven_x, pulley_y, pulley_z), 0.034, 0.24, mat_steel, vertices=48, rotation=(math.radians(90), 0, 0), bevel=True)
torus("Belt_Wrap_Driver_Runtime", (drive_x, pulley_y, pulley_z), 0.177, 0.012, mat_belt, rotation=(0, 0, 0), major_segments=96, minor_segments=8)
torus("Belt_Wrap_Driven_Runtime", (driven_x, pulley_y, pulley_z), 0.258, 0.012, mat_belt, rotation=(0, 0, 0), major_segments=96, minor_segments=8)
box("Belt_Top_Span_Runtime", (-0.17, pulley_y, pulley_z + 0.245), (1.25, 0.035, 0.023), mat_belt, 0.01)
box("Belt_Bottom_Span_Runtime", (-0.17, pulley_y, pulley_z - 0.245), (1.25, 0.035, 0.023), mat_belt, 0.01)
add_text("Label_Belt_Ratio", "BELT DRIVE 2:1", (-1.08, 1.82, 1.04), 0.064, mat_text)
animate_rotation(pulley_a, 2, 2.0)
animate_rotation(pulley_b, 2, -1.0)

# Robot arm rig.
add_text("Label_Robot_Arm", "ROBOT ARM", (1.36, 1.82, 1.04), 0.064, mat_text)
cyl("Robot_Base", (1.28, -0.04, 0.66), 0.12, 0.16, mat_dark, vertices=64, bevel=True)
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(1.28, -0.04, 0.75))
j1 = bpy.context.object
j1.name = "RobotArm_Joint1_Yaw"
seg1 = box("RobotArm_Upper_Link", (0, 0, 0.30), (0.065, 0.085, 0.34), mat_steel, 0.015)
seg1.parent = j1
seg1.matrix_parent_inverse = mathutils.Matrix.Identity(4)
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0.62))
j2 = bpy.context.object
j2.name = "RobotArm_Joint2_Shoulder"
j2.parent = j1
j2.matrix_parent_inverse = mathutils.Matrix.Identity(4)
seg2 = box("RobotArm_Forearm_Link", (0, 0, 0.25), (0.052, 0.075, 0.29), mat_brass, 0.014)
seg2.parent = j2
seg2.matrix_parent_inverse = mathutils.Matrix.Identity(4)
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0.52))
j3 = bpy.context.object
j3.name = "RobotArm_Joint3_Wrist"
j3.parent = j2
j3.matrix_parent_inverse = mathutils.Matrix.Identity(4)
tool = box("RobotArm_Verifier_Toolhead", (0, 0, 0.11), (0.16, 0.045, 0.055), mat_green, 0.01)
tool.parent = j3
tool.matrix_parent_inverse = mathutils.Matrix.Identity(4)
for f, yaw, shoulder, wrist in [(1, -22, 0, -14), (48, 18, 20, 24), (96, -14, -16, -22), (144, -22, 0, -14)]:
    scene.frame_set(f)
    j1.rotation_euler = (0, 0, math.radians(yaw))
    j2.rotation_euler = (math.radians(shoulder), 0, 0)
    j3.rotation_euler = (math.radians(wrist), math.radians(wrist * 0.35), 0)
    j1.keyframe_insert("rotation_euler", frame=f)
    j2.keyframe_insert("rotation_euler", frame=f)
    j3.keyframe_insert("rotation_euler", frame=f)
for obj in (j1, j2, j3):
    key_linear(obj)

# Drone with propellers and lift.
add_text("Label_Drone_Lift", "DRONE LIFT", (-2.12, 1.82, 1.36), 0.064, mat_text)
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(-1.45, -1.00, 1.24))
drone = bpy.context.object
drone.name = "Drone_Lift_Rig"
body = box("Drone_Body_Inspector", (0, 0, 0), (0.22, 0.14, 0.055), mat_dark, 0.018)
body.parent = drone
body.matrix_parent_inverse = mathutils.Matrix.Identity(4)
propellers = []
for sx in (-1, 1):
    for sy in (-1, 1):
        arm = box("Drone_Carbon_Arm", (sx * 0.28, sy * 0.20, 0.0), (0.25, 0.018, 0.018), mat_steel, 0.006)
        arm.rotation_euler.z = math.atan2(sy * 0.20, sx * 0.28)
        arm.parent = drone
        arm.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        rotor = torus("Drone_Propeller_Spin_Target", (sx * 0.38, sy * 0.27, 0.035), 0.072, 0.005, mat_blue, major_segments=48, minor_segments=6)
        blade1 = box("Drone_Propeller_Blade_A", (sx * 0.38, sy * 0.27, 0.035), (0.16, 0.014, 0.004), mat_blue, 0.004)
        blade2 = box("Drone_Propeller_Blade_B", (sx * 0.38, sy * 0.27, 0.035), (0.014, 0.16, 0.004), mat_blue, 0.004)
        for child in (rotor, blade1, blade2):
            child.parent = drone
            child.matrix_parent_inverse = mathutils.Matrix.Identity(4)
            propellers.append(child)
for f, zoff in [(1, 0.0), (48, 0.16), (96, -0.02), (144, 0.0)]:
    scene.frame_set(f)
    drone.location = (-1.45, -1.00, 1.24 + zoff)
    drone.rotation_euler = (math.radians(2 * math.sin(f)), math.radians(3 * math.cos(f)), 0)
    drone.keyframe_insert("location", frame=f)
    drone.keyframe_insert("rotation_euler", frame=f)
key_linear(drone)
for idx, prop in enumerate(propellers):
    animate_rotation(prop, 2, 14.0 if idx % 2 == 0 else -14.0)

# Data portal with orbiting validation beads.
portal = torus("Data_Portal_Pulsing_Ring", (0.18, 1.08, 1.17), 0.42, 0.018, mat_glass, rotation=(math.radians(90), 0, 0), major_segments=128, minor_segments=12)
animate_rotation(portal, 2, 0.45)
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0.18, 1.08, 1.17))
orbit = bpy.context.object
orbit.name = "DataOrbit_Rig"
for i in range(18):
    a = i * math.tau / 18
    bead = sphere(f"Validation_Bead_{i:02d}", (0.18 + 0.47 * math.cos(a), 1.08, 1.17 + 0.47 * math.sin(a)), 0.025, mat_green if i % 3 else mat_orange, 16)
    bead.parent = orbit
    bead.matrix_parent_inverse = orbit.matrix_world.inverted()
animate_rotation(orbit, 1, 1.0)

# Timeline marker and coherence screen.
screen = uv_plane("Coherent_Status_Screen_Texture", (0.0, 1.80, 1.15), 1.58, 0.72, make_texture_mat("Mat_status_screen_texture", status_img, 0.8), rotation=(math.radians(90), 0, 0))
screen["aurora_screen_contract"] = "status graph texture embedded in GLB"
marker = sphere("Timeline_Marker_Moving_Verification", (-2.1, -1.45, 0.11), 0.055, mat_orange, 24)
for f, x in [(1, -2.1), (72, 0.0), (144, 2.1)]:
    scene.frame_set(f)
    marker.location = (x, -1.45, 0.11)
    marker.keyframe_insert("location", frame=f)
key_linear(marker)

# Additional scene detail: rails, bolts, and inspection samples.
for x in (-2.25, 2.25):
    box("Timeline_End_Stop", (x, -1.45, 0.08), (0.035, 0.16, 0.09), mat_steel, 0.006)
box("Timeline_Rail", (0, -1.45, 0.06), (4.5, 0.026, 0.024), mat_steel, 0.004)
for i in range(28):
    x = -2.05 + i * (4.1 / 27)
    sphere(f"Floor_Fastener_{i:02d}", (x, 0.76 + 0.05 * math.sin(i), 0.035), 0.018, mat_steel, 12)

# Lighting and camera.
def add_area(name, loc, target, size, energy, color):
    data = bpy.data.lights.new(name, type="AREA")
    data.size = size
    data.energy = energy
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    look_at(obj, target)
    return obj


add_area("Key_Light_Softbox", (1.5, -3.0, 3.0), (0, 0, 0.8), 4.0, 720, (1.0, 0.94, 0.86))
add_area("Blue_Rim_Light", (-2.8, 0.9, 2.1), (0, 0, 1.0), 2.0, 380, (0.35, 0.62, 1.0))
add_area("Green_Verify_Light", (2.3, 1.0, 1.7), (0.6, 0, 0.8), 1.4, 250, (0.3, 1.0, 0.66))

cam_data = bpy.data.cameras.new("Aurora_Animated_Camera")
camera = bpy.data.objects.new("Aurora_Animated_Camera", cam_data)
bpy.context.collection.objects.link(camera)
scene.camera = camera
cam_data.lens = 30
cam_data.dof.use_dof = True
cam_data.dof.focus_distance = 4.5
cam_data.dof.aperture_fstop = 7.0
camera_path = [
    (1, (3.25, -4.25, 2.05), (0.0, -0.05, 0.98)),
    (48, (2.10, -3.20, 1.52), (-0.25, -0.28, 0.92)),
    (96, (-2.62, -3.18, 1.75), (-0.55, -0.38, 1.12)),
    (144, (3.25, -4.25, 2.05), (0.0, -0.05, 0.98)),
]
for f, loc, target in camera_path:
    scene.frame_set(f)
    camera.location = loc
    look_at(camera, target)
    camera.keyframe_insert("location", frame=f)
    camera.keyframe_insert("rotation_euler", frame=f)
key_linear(camera)

# Animate emissive material strengths where possible.
for mat, base, peak in [(mat_green, 0.8, 2.2), (mat_orange, 1.1, 2.8), (mat_blue, 0.8, 2.4)]:
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf and "Emission Strength" in bsdf.inputs:
        inp = bsdf.inputs["Emission Strength"]
        for f in (1, 36, 72, 108, 144):
            t = (f - 1) / max(1, frame_end - 1)
            inp.default_value = base + (peak - base) * (0.5 + 0.5 * math.sin(t * math.tau * 2.0))
            inp.keyframe_insert("default_value", frame=f)

# Metadata contract on root objects.
for obj in bpy.context.scene.objects:
    if obj.type in {"MESH", "EMPTY", "FONT"}:
        obj["aurora_heavy_test"] = "blender_full_scene_animation"

scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=out_blend)

export_kwargs = dict(
    filepath=out_glb,
    export_format="GLB",
    export_animations=True,
    export_extras=True,
    export_yup=True,
    export_cameras=True,
    export_lights=True,
)
try:
    export_kwargs.update(dict(
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=5,
        export_draco_position_quantization=14,
        export_draco_normal_quantization=10,
        export_draco_texcoord_quantization=12,
    ))
    bpy.ops.export_scene.gltf(**export_kwargs)
except TypeError:
    for key in list(export_kwargs):
        if key.startswith("export_draco_"):
            del export_kwargs[key]
    bpy.ops.export_scene.gltf(**export_kwargs)

still_frames = [1, 48, 96, 144]
still_paths = []
for frame in still_frames:
    scene.frame_set(frame)
    path = os.path.join(render_dir, f"frame_{frame:03d}.png")
    scene.render.filepath = path
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    still_paths.append(path)

video_ok = False
video_error = None
if render_video:
    try:
        scene.frame_start = 1
        scene.frame_end = min(frame_end, 96)
        scene.render.filepath = preview_mp4
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.ffmpeg.ffmpeg_preset = "GOOD"
        bpy.ops.render.render(animation=True)
        video_ok = os.path.isfile(preview_mp4)
    except Exception as exc:
        video_error = str(exc)

meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
result = {
    "ok": True,
    "glb_path": out_glb,
    "blend_path": out_blend,
    "texture_path": texture_path,
    "still_frames": still_paths,
    "preview_mp4": preview_mp4 if video_ok else None,
    "video_error": video_error,
    "frame_start": 1,
    "frame_end": frame_end,
    "fps": fps,
    "object_count": len(bpy.context.scene.objects),
    "mesh_count": len(meshes),
    "material_count": len(bpy.data.materials),
    "animation_actions": len(bpy.data.actions),
    "blender_version": bpy.app.version_string,
}
print(json.dumps(result))
'''


def _run_blender(
    blender: str,
    out_dir: Path,
    *,
    run_id: str,
    render_video: bool,
    timeout_s: int,
) -> dict[str, Any]:
    paths = {
        "glb": str(out_dir / f"{run_id}_full_scene_animated.glb"),
        "blend": str(out_dir / f"{run_id}_full_scene.blend"),
        "render_dir": str(out_dir / "renders"),
        "preview_mp4": str(out_dir / f"{run_id}_preview.mp4"),
        "texture_path": str(out_dir / f"{run_id}_embedded_status_texture.png"),
    }
    settings = {
        "render_video": render_video,
        "fps": 24,
        "frame_end": 144,
        "width": 1280,
        "height": 720,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    script_path = None
    started = time.time()
    try:
        with tempfile.NamedTemporaryFile("w", suffix="_aurora_blender_heavy.py", encoding="utf-8", delete=False) as fh:
            fh.write(BLENDER_SCENE_SCRIPT)
            script_path = fh.name
        cmd = [
            blender,
            "--background",
            "--factory-startup",
            "--python",
            script_path,
            "--",
            json.dumps(paths),
            json.dumps(settings),
        ]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"Blender heavy test timed out after {timeout_s}s",
            "elapsed_s": round(time.time() - started, 1),
            "paths": paths,
        }
    finally:
        if script_path:
            try:
                os.remove(script_path)
            except OSError:
                pass

    elapsed = round(time.time() - started, 1)
    (out_dir / "blender_stdout.log").write_text(proc.stdout or "", encoding="utf-8", errors="replace")
    (out_dir / "blender_stderr.log").write_text(proc.stderr or "", encoding="utf-8", errors="replace")

    parsed = None
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
                break
            except json.JSONDecodeError:
                pass
    if proc.returncode != 0 or not parsed or not Path(paths["glb"]).is_file():
        return {
            "ok": False,
            "error": f"Blender exited with rc={proc.returncode}",
            "elapsed_s": elapsed,
            "paths": paths,
            "stdout_tail": (proc.stdout or "")[-1500:],
            "stderr_tail": (proc.stderr or "")[-1500:],
        }
    parsed["elapsed_s"] = elapsed
    parsed["paths"] = paths
    return parsed


def _run_acceptance(glb_path: str) -> dict[str, Any]:
    try:
        from mesh_acceptance_gate import evaluate_acceptance

        return evaluate_acceptance(glb_path, SCENE_PROMPT, "mechanism", MOTION_PROMPT)
    except Exception as exc:
        return {"ok": False, "error": f"acceptance gate failed: {type(exc).__name__}: {exc}"}


def _run_visual_quality(glb_path: str) -> dict[str, Any]:
    report: dict[str, Any] = {}
    try:
        from mesh_visual_audit import audit as visual_audit

        report["visual"] = visual_audit(Path(glb_path))
    except Exception as exc:
        report["visual"] = {"ok": False, "error": f"visual audit failed: {exc}"}
    try:
        from mesh_quality_score import score_mesh

        report["quality"] = score_mesh(glb_path, "mechanism")
    except Exception as exc:
        report["quality"] = {"ok": False, "error": f"quality score failed: {exc}"}
    return report


def run_heavy_test(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    run_id: str | None = None,
    render_video: bool = False,
    timeout_s: int = 1800,
) -> dict[str, Any]:
    run_id = run_id or datetime.now(timezone.utc).strftime("blender_heavy_%Y%m%d_%H%M%S")
    base = Path(output_dir)
    if not base.is_absolute():
        base = REPO_ROOT / base
    out_dir = base / run_id
    blender = _find_blender()
    if not blender:
        return {
            "ok": False,
            "schema": "aurora.blender_heavy_test.v1",
            "error": "Blender executable not found",
            "run_id": run_id,
            "output_dir": str(out_dir),
        }

    generation = _run_blender(
        blender,
        out_dir,
        run_id=run_id,
        render_video=render_video,
        timeout_s=timeout_s,
    )
    if not generation.get("ok"):
        report = {
            "ok": False,
            "schema": "aurora.blender_heavy_test.v1",
            "run_id": run_id,
            "output_dir": str(out_dir),
            "blender": blender,
            "generation": generation,
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
        return report

    glb_path = generation["glb_path"]
    text = _text_audit(glb_path)
    motion = _animation_audit(glb_path)
    still_pixel = _pixel_audit([str(p) for p in generation.get("still_frames") or []])
    screenshots = _render_mesh_screenshots(glb_path, out_dir / "mesh_views")
    acceptance = _run_acceptance(glb_path)
    visual_quality = _run_visual_quality(glb_path)

    checks = {
        "glb_exists": Path(glb_path).is_file() and Path(glb_path).stat().st_size > 50_000,
        "blend_exists": Path(generation.get("blend_path", "")).is_file(),
        "text_contract": text.get("ok", False),
        "animation_contract": motion.get("ok", False),
        "still_renders_nonblank": still_pixel.get("ok", False),
        "mesh_view_renders_nonblank": bool((screenshots.get("pixel_audit") or {}).get("ok")),
        "acceptance_gate": bool(acceptance.get("acceptance_ok")),
    }
    report = {
        "ok": all(checks.values()),
        "schema": "aurora.blender_heavy_test.v1",
        "run_id": run_id,
        "prompt": SCENE_PROMPT,
        "motion_prompt": MOTION_PROMPT,
        "output_dir": str(out_dir),
        "blender": blender,
        "generation": generation,
        "checks": checks,
        "text_audit": text,
        "motion_audit": motion,
        "still_pixel_audit": still_pixel,
        "mesh_screenshots": screenshots,
        "acceptance": acceptance,
        "visual_quality": visual_quality,
    }
    (out_dir / "audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    manifest = {
        "schema": "aurora.blender_heavy_manifest.v1",
        "run_id": run_id,
        "ok": report["ok"],
        "main_result": glb_path,
        "blend": generation.get("blend_path"),
        "preview_mp4": generation.get("preview_mp4"),
        "still_frames": generation.get("still_frames"),
        "mesh_contact_sheet": (screenshots.get("contact_sheet") or {}).get("path"),
        "audit_json": str(out_dir / "audit.json"),
        "checks": checks,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
    return report


def render_pretty(report: dict[str, Any]) -> str:
    if not report.get("ok"):
        lines = [
            "Aurora Blender heavy test: FAIL",
            f"Run: {report.get('run_id')}  output={report.get('output_dir')}",
        ]
        error = report.get("error") or (report.get("generation") or {}).get("error")
        if error:
            lines.append(f"Error: {error}")
        checks = report.get("checks") or {}
        for name, ok in checks.items():
            lines.append(f"- {name}: {'OK' if ok else 'FAIL'}")
        return "\n".join(lines) + "\n"

    gen = report["generation"]
    screenshots = report.get("mesh_screenshots") or {}
    contact = screenshots.get("contact_sheet") or {}
    lines = [
        "Aurora Blender heavy test: OK",
        f"Run: {report.get('run_id')}",
        f"Output: {report.get('output_dir')}",
        f"GLB: {gen.get('glb_path')}",
        f"Blend: {gen.get('blend_path')}",
        f"Preview MP4: {gen.get('preview_mp4') or 'not requested/generated'}",
        f"Contact sheet: {contact.get('path') or 'unavailable'}",
        f"Audit: {Path(report.get('output_dir', '.')) / 'audit.json'}",
        "",
        "Checks:",
    ]
    for name, ok in (report.get("checks") or {}).items():
        lines.append(f"- {name}: {'OK' if ok else 'FAIL'}")
    motion = report.get("motion_audit") or {}
    lines.append(
        f"Animation: {motion.get('total_channels')} channels, "
        f"{motion.get('unique_target_nodes')} animated nodes, "
        f"max {motion.get('max_keyframes')} keyframes"
    )
    acceptance = report.get("acceptance") or {}
    lines.append(
        f"Acceptance: {acceptance.get('verdict')} "
        f"grade={acceptance.get('engineer_grade')}/{acceptance.get('threshold')}"
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Aurora's heavy Blender 3D scene test")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--render-video", action="store_true", help="Render a short MP4 preview in addition to GLB animation")
    parser.add_argument("--timeout-s", type=int, default=1800)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    report = run_heavy_test(
        output_dir=args.output_dir,
        run_id=args.run_id,
        render_video=args.render_video,
        timeout_s=args.timeout_s,
    )
    if args.pretty:
        sys.stdout.write(render_pretty(report))
    else:
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
