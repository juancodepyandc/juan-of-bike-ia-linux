#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""motion_intent_bpy_runner -- bpy-side companion of motion_intent_baker.py.

This file is consumed by `blender --background --python` ; it must NOT be
imported by regular Python (it has no shebang test guards because Blender
runs it as the main module). It expects argv past `--` to include:

    --intent <path>  --input <glb> --output <glb> [--fps N]

Eight categories handled:
  led_emission / fan_pwm / oled_screen /
  creature_organic / mechanical_simple / rigid_static /
  fluid_flow / gas_volume

Each branch operates on a fresh empty scene + the imported GLB, then exports
back to GLB with NLA actions baked in.
"""

import bpy
import json  # noqa: F401  (used in OLED atlas metadata + main driver)
import os
import sys
import math

import mathutils


def _get_action_fcurves(action, slot=None):
    """Blender 5.0+ exposes FCurves only via the layered API:
        action.layers[0].strips[0].channelbag(slot, ensure=True).fcurves
    Action.fcurves was removed. We always go through the layered API when it
    exists; we fall back to action.fcurves only on Blender 4.x where layers
    don't exist."""
    if hasattr(action, "layers"):
        layer = action.layers[0] if len(action.layers) > 0 else action.layers.new("Layer")
        strip = layer.strips[0] if len(layer.strips) > 0 else layer.strips.new(type="KEYFRAME")
        if slot is not None and hasattr(strip, "channelbag"):
            cb = strip.channelbag(slot, ensure=True)
            return cb.fcurves
        # 5.x but no slot? force a default slot via channelbag if available.
        if hasattr(strip, "channelbag"):
            # Try to get/create a default channelbag without slot id
            try:
                cb = strip.channelbag(slot, ensure=True) if slot else strip.channelbag(action.slots[0] if hasattr(action, "slots") and len(action.slots) > 0 else None, ensure=True)
                if cb is not None:
                    return cb.fcurves
            except Exception:
                pass
    # Blender 4.x legacy path
    return action.fcurves


def _ensure_action_for_object(obj, name="AuroraAction"):
    if obj.animation_data is None:
        obj.animation_data_create()
    action = bpy.data.actions.new(name=name)
    obj.animation_data.action = action
    slot = None
    if hasattr(action, "slots"):
        try:
            slot = action.slots.new(id_type="OBJECT", name=obj.name)
        except Exception:
            slot = action.slots[0] if len(action.slots) > 0 else None
        if slot is not None and hasattr(obj.animation_data, "action_slot"):
            try:
                obj.animation_data.action_slot = slot
            except Exception:
                pass
    # Ensure a layer/strip exists in 5.x so callers can grab fcurves later.
    if hasattr(action, "layers") and len(action.layers) == 0:
        layer = action.layers.new("Layer")
        layer.strips.new(type="KEYFRAME")
    return action, slot


def _ensure_action_for_material(mat, name="AuroraEmission"):
    if not mat.use_nodes:
        mat.use_nodes = True
    if mat.node_tree.animation_data is None:
        mat.node_tree.animation_data_create()
    action = bpy.data.actions.new(name=name)
    mat.node_tree.animation_data.action = action
    slot = None
    if hasattr(action, "slots"):
        try:
            slot = action.slots.new(id_type="NODETREE", name=mat.name)
        except Exception:
            slot = action.slots[0] if len(action.slots) > 0 else None
        if slot is not None and hasattr(mat.node_tree.animation_data, "action_slot"):
            try:
                mat.node_tree.animation_data.action_slot = slot
            except Exception:
                pass
    if hasattr(action, "layers") and len(action.layers) == 0:
        layer = action.layers.new("Layer")
        layer.strips.new(type="KEYFRAME")
    return action, slot


def _hex_to_rgba(h):
    h = h.lstrip("#")
    if len(h) == 6:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return (r, g, b, 1.0)
    return (1.0, 0.0, 0.5, 1.0)


def _largest_mesh(scene):
    target = None
    biggest = -1.0
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        v = obj.dimensions.x * obj.dimensions.y * obj.dimensions.z
        if v > biggest:
            biggest = v
            target = obj
    return target


# ---------------------------------------------------------------------------
# Six handlers
# ---------------------------------------------------------------------------

def bake_led_emission(intent, scene, fps):
    color_anim = intent.get("color_anim") or {}
    pattern = color_anim.get("pattern") or "rainbow"
    speed_hz = float(color_anim.get("speed_hz") or 1.0)
    colors = color_anim.get("colors") or ["#ff0033", "#33ccff", "#ffaa00"]
    strength = float(color_anim.get("emission_strength") or 4.0)

    period_frames = max(int(fps / max(speed_hz, 0.01)), 2)
    total_frames = period_frames * 4 if pattern in ("chase", "rainbow") else period_frames * 2
    scene.frame_start = 1
    scene.frame_end = total_frames

    materials_animated = 0
    for mat in bpy.data.materials:
        if mat is None or not mat.use_nodes:
            continue
        bsdf = None
        for node in mat.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                bsdf = node
                break
        if bsdf is None:
            continue
        action, slot = _ensure_action_for_material(mat)
        fcurves = _get_action_fcurves(action, slot)

        em_color = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        em_strength = bsdf.inputs.get("Emission Strength")
        if em_color is None or em_strength is None:
            continue

        color_path = em_color.path_from_id("default_value")
        strength_path = em_strength.path_from_id("default_value")

        rgba_curves = [fcurves.new(data_path=color_path, index=i) for i in range(3)]
        s_curve = fcurves.new(data_path=strength_path, index=0)

        for f in range(1, total_frames + 1):
            t = (f - 1) / float(period_frames)
            if pattern == "static_color":
                rgba = _hex_to_rgba(colors[0]); s = strength
            elif pattern == "breathing":
                phase = (math.sin(2 * math.pi * t) + 1) * 0.5
                rgba = _hex_to_rgba(colors[0]); s = strength * phase
            elif pattern == "pulse":
                phase = 1.0 if (f % period_frames) < (period_frames // 2) else 0.0
                rgba = _hex_to_rgba(colors[0]); s = strength * phase
            elif pattern == "chase":
                idx = (f // max(1, period_frames // max(len(colors), 1))) % len(colors)
                rgba = _hex_to_rgba(colors[idx]); s = strength
            else:  # rainbow
                hue = (t * 0.5) % 1.0
                i_h = int(hue * 6)
                f_h = hue * 6 - i_h
                q = 1 - f_h
                if i_h % 6 == 0: rgba = (1.0, f_h, 0.0, 1.0)
                elif i_h % 6 == 1: rgba = (q, 1.0, 0.0, 1.0)
                elif i_h % 6 == 2: rgba = (0.0, 1.0, f_h, 1.0)
                elif i_h % 6 == 3: rgba = (0.0, q, 1.0, 1.0)
                elif i_h % 6 == 4: rgba = (f_h, 0.0, 1.0, 1.0)
                else: rgba = (1.0, 0.0, q, 1.0)
                s = strength

            for i, kf in enumerate(rgba_curves):
                kf.keyframe_points.insert(f, rgba[i])
            s_curve.keyframe_points.insert(f, s)
        # iter9.D: tag the material with aurora.led-emission.v1 extras so the
        # Aurora ModelView (and the standalone aurora_3d_viewer) can re-drive
        # material.emissive / material.emissiveIntensity client-side.
        # Why: glTF spec doesn't export shader-node-socket animation. Our
        # FCurves on bsdf.inputs["Emission Color"].default_value are kept for
        # in-Blender preview / viewport and any future KHR_animation_pointer
        # path, but the GLB shipped to Three.js is statically coloured at
        # frame 1 unless the runtime reader animates emissive itself.
        try:
            base_color_hex = colors[0] if colors else "#ff0033"
            mat["aurora_led_emission"] = {
                "schema": "aurora.led-emission.v1",
                "pattern": pattern,
                "speed_hz": float(speed_hz),
                "colors": list(colors),
                "emission_strength": float(strength),
                "base_color": base_color_hex,
                "frame_count": int(total_frames),
                "fps": int(fps),
                "loop": True,
            }
        except Exception:
            pass
        materials_animated += 1
    return {"materials_animated": materials_animated, "frame_count": total_frames,
            "pattern": pattern, "speed_hz": speed_hz,
            "extras_schema": "aurora.led-emission.v1"}


def bake_fan_pwm(intent, scene, fps):
    m = intent.get("mechanical_anim") or {}
    axis = (m.get("axis") or "Z").upper()
    rpm = float(m.get("rpm") or 1200)
    revs_per_sec = rpm / 60.0
    radians_per_frame = (2 * math.pi * revs_per_sec) / fps
    total_frames = int(fps * 2)
    scene.frame_start = 1
    scene.frame_end = total_frames

    target = _largest_mesh(scene)
    if target is None:
        return {"error": "no mesh found"}

    action, slot = _ensure_action_for_object(target, "FanRotation")
    fcurves = _get_action_fcurves(action, slot)
    target.rotation_mode = "XYZ"
    axis_index = {"X": 0, "Y": 1, "Z": 2}.get(axis, 2)
    fc = fcurves.new(data_path="rotation_euler", index=axis_index)
    for f in range(1, total_frames + 1):
        fc.keyframe_points.insert(f, (f - 1) * radians_per_frame)
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"
    return {"target": target.name, "rpm": rpm, "axis": axis, "frame_count": total_frames}


def bake_mechanical_simple(intent, scene, fps):
    m = intent.get("mechanical_anim") or {}
    axis = (m.get("axis") or "Z").upper()
    motion_type = m.get("motion_type") or "oscillation"
    amplitude = float(m.get("amplitude") or (15.0 if motion_type != "translation" else 0.05))
    period_s = float(m.get("period_s") or 1.0)
    period_frames = max(int(fps * period_s), 2)
    total_frames = period_frames * 2
    scene.frame_start = 1
    scene.frame_end = total_frames

    target = _largest_mesh(scene)
    if target is None:
        return {"error": "no mesh found"}

    action, slot = _ensure_action_for_object(target, "MechanicalAction")
    fcurves = _get_action_fcurves(action, slot)
    target.rotation_mode = "XYZ"
    axis_index = {"X": 0, "Y": 1, "Z": 2}.get(axis, 2)

    if motion_type == "translation":
        fc = fcurves.new(data_path="location", index=axis_index)
        for f in range(1, total_frames + 1):
            phase = math.sin(2 * math.pi * (f - 1) / period_frames)
            fc.keyframe_points.insert(f, phase * amplitude)
    else:
        fc = fcurves.new(data_path="rotation_euler", index=axis_index)
        amp_rad = math.radians(amplitude)
        for f in range(1, total_frames + 1):
            phase = math.sin(2 * math.pi * (f - 1) / period_frames)
            fc.keyframe_points.insert(f, phase * amp_rad)
    return {"target": target.name, "motion_type": motion_type,
            "amplitude": amplitude, "frame_count": total_frames}


def _find_screen_materials():
    """Locate materials whose name suggests they are an OLED/screen face."""
    target_mats = []
    for mat in bpy.data.materials:
        if mat is None or not mat.use_nodes:
            continue
        n = mat.name.lower()
        if "screen" in n or "oled" in n or "display" in n or "livedash" in n:
            target_mats.append(mat)
    if not target_mats:
        for mat in bpy.data.materials:
            if mat and mat.use_nodes:
                target_mats = [mat]
                break
    return target_mats


def _build_flipbook_atlas(png_seq_dir):
    """Stitch a PNG sequence into a single horizontal flipbook texture.

    Returns (atlas_path, frame_count, frame_w, frame_h) on success, or
    (None, 0, 0, 0) on failure. We invoke the host Pillow only — Blender's
    bundled python doesn't have PIL but the host Python (which spawned us)
    is supposed to have already done the stitching. To stay defensive we
    also accept a pre-stitched `_atlas.png` produced by the host orchestrator.
    """
    import os
    atlas_path = os.path.join(png_seq_dir, "_atlas.png")
    if os.path.isfile(atlas_path):
        # Read frame count from a sidecar JSON
        meta = os.path.join(png_seq_dir, "_atlas.json")
        if os.path.isfile(meta):
            import json as _json
            try:
                with open(meta, "r", encoding="utf-8") as f:
                    info = _json.load(f)
                return atlas_path, int(info.get("frame_count", 0)), \
                       int(info.get("frame_w", 0)), int(info.get("frame_h", 0))
            except Exception:
                pass
    # No atlas pre-built — fail (host orchestrator is responsible for it)
    return None, 0, 0, 0


def _bind_flipbook_atlas_to_material(mat, atlas_path, frame_count, frame_w, frame_h,
                                     frame_rate, fps, total_frames):
    """Wire a flipbook atlas onto the material with UV-mapping animation.

    Strategy: Image Texture (atlas) -> Mapping (location.x animated) -> UV
    -> BSDF Base Color + Emission Color. The atlas contains N frames stacked
    horizontally; we step the X scale to 1/N and animate location.x in
    increments of 1/N so each loop frame shows the next frame.

    glTF I/O: this exports cleanly as a textured material with KHR_texture_transform
    extension, and the Mapping node's location.x animates via standard
    Object-style fcurves -> samplers. The atlas is a single PNG, no sequence.
    """
    if frame_count <= 0:
        return False, "frame_count<=0"

    bsdf = None
    output = None
    for node in mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            bsdf = node
        elif node.type == "OUTPUT_MATERIAL":
            output = node
    if bsdf is None:
        return False, "no BSDF_PRINCIPLED"

    # Load atlas (single image, no sequence)
    try:
        img = bpy.data.images.load(atlas_path, check_existing=False)
    except Exception as exc:
        return False, "atlas load failed: %s" % exc
    img.name = "AuroraOledAtlas"

    # Build node graph: TexCoord -> Mapping -> ImageTex -> BSDF.Base/Emission
    nt = mat.node_tree
    tex_coord = nt.nodes.new(type="ShaderNodeTexCoord")
    tex_coord.label = "AuroraOledTexCoord"
    tex_coord.location = (bsdf.location.x - 900, bsdf.location.y)
    mapping = nt.nodes.new(type="ShaderNodeMapping")
    mapping.label = "AuroraOledMapping"
    mapping.location = (bsdf.location.x - 700, bsdf.location.y)
    # X scale = 1/N so we sample only one frame's worth horizontally
    mapping.inputs["Scale"].default_value = (1.0 / frame_count, 1.0, 1.0)
    mapping.inputs["Location"].default_value = (0.0, 0.0, 0.0)
    tex = nt.nodes.new(type="ShaderNodeTexImage")
    tex.label = "AuroraOledFlipbook"
    tex.image = img
    tex.location = (bsdf.location.x - 400, bsdf.location.y)
    # Linear interpolation OFF so neighbouring frames don't bleed
    tex.interpolation = "Closest"
    tex.extension = "REPEAT"

    # Wire links
    try:
        nt.links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    except Exception:
        pass

    bc = bsdf.inputs.get("Base Color")
    if bc is not None:
        try: nt.links.new(tex.outputs["Color"], bc)
        except Exception: pass
    em = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
    if em is not None:
        try: nt.links.new(tex.outputs["Color"], em)
        except Exception: pass
    es = bsdf.inputs.get("Emission Strength")
    if es is not None:
        try: es.default_value = 1.5
        except Exception: pass

    # Animate Mapping.Location.X to step through atlas frames
    step_scene_frames = max(1, int(round(fps / max(frame_rate, 1.0))))

    # Setup nodetree action
    if nt.animation_data is None:
        nt.animation_data_create()
    action = bpy.data.actions.new(name="OledFlipbookScroll")
    nt.animation_data.action = action
    slot = None
    if hasattr(action, "slots"):
        try:
            slot = action.slots.new(id_type="NODETREE", name=mat.name)
            if slot is not None and hasattr(nt.animation_data, "action_slot"):
                nt.animation_data.action_slot = slot
        except Exception:
            pass
    if hasattr(action, "layers") and len(action.layers) == 0:
        layer = action.layers.new("Layer")
        layer.strips.new(type="KEYFRAME")
    fcurves = _get_action_fcurves(action, slot)

    # The data_path for Mapping.Location.X
    loc_input = mapping.inputs["Location"]
    data_path = loc_input.path_from_id("default_value")
    fc = None
    try:
        fc = fcurves.new(data_path=data_path, index=0)
    except Exception as exc:
        return False, "fcurves.new failed: %s" % exc

    inserted = 0
    n_loops = max(1, total_frames // (frame_count * step_scene_frames) + 1)
    for loop in range(n_loops):
        for i in range(frame_count):
            scene_frame = loop * frame_count * step_scene_frames + i * step_scene_frames + 1
            if scene_frame > total_frames:
                break
            x = i / float(frame_count)
            kp = fc.keyframe_points.insert(scene_frame, x)
            try:
                kp.interpolation = "CONSTANT"  # snap to next frame, no bleed
            except Exception:
                pass
            inserted += 1

    # iter5.B v2: tag the material with a custom property so the Aurora
    # Three.js viewer (ModelView.tsx) can animate the UV offset client-side
    # — the glTF spec doesn't support animating Mapping node values, but
    # KHR_texture_transform's `offset` IS a static value that the viewer
    # can re-keyframe at draw-time using the embedded "aurora_oled_atlas"
    # metadata. The Blender glTF exporter honours dict-shaped custom props
    # only when they are NESTED under an explicit "extras" attribute on the
    # ID — see https://docs.blender.org/manual/en/latest/addons/import_export/scene_gltf2.html
    try:
        mat["aurora_oled_atlas"] = {
            "schema": "aurora.oled-atlas.v1",
            "frame_count": int(frame_count),
            "frame_w": int(frame_w),
            "frame_h": int(frame_h),
            "frame_rate": float(frame_rate),
            "loop": True,
        }
    except Exception:
        pass

    return True, {"frame_count": frame_count, "step_scene_frames": step_scene_frames,
                  "keyframes_inserted": inserted, "frame_rate": frame_rate,
                  "atlas": atlas_path}


def _bind_image_sequence_to_material(mat, png_seq_dir, frame_rate, fps, total_frames):
    """Bind a PNG sequence to the Base Color of a Principled BSDF.

    iter5.B v2: we now use a FLIPBOOK ATLAS approach (host Pillow stitches
    the PNGs into a horizontal strip + writes _atlas.png + _atlas.json).
    The atlas is a single image, the Mapping node's location.x is animated
    -> exports cleanly to glTF with KHR_texture_transform.
    """
    import os
    if not os.path.isdir(png_seq_dir):
        return False, "png_seq_dir missing"

    atlas_path, frame_count, fw, fh = _build_flipbook_atlas(png_seq_dir)
    if atlas_path is not None and frame_count > 0:
        return _bind_flipbook_atlas_to_material(
            mat, atlas_path, frame_count, fw, fh, frame_rate, fps, total_frames,
        )

    # If host didn't pre-build the atlas, fall back to base color animation.
    return False, "no _atlas.png in seq dir (host did not stitch)"


def bake_oled_screen(intent, scene, fps):
    s = intent.get("screen_anim") or {}
    frame_rate = float(s.get("frame_rate") or 12)
    content_type = s.get("content_type") or s.get("content_kind") or "text_scroll"

    # iter5.B: PNG sequence dir is a CLI flag, not part of the intent JSON.
    # The driver passes it via a global env-var so this function can stay
    # backwards-compatible with intents that pre-date the feature.
    import os as _os
    png_seq_dir = _os.environ.get("AURORA_OLED_PNG_SEQ_DIR") or ""

    total_frames = int(fps * 4)
    scene.frame_start = 1
    scene.frame_end = total_frames

    target_mats = _find_screen_materials()

    # iter5.B PRIMARY PATH: PNG sequence binding
    if png_seq_dir and target_mats:
        bound = 0
        seq_results = []
        for mat in target_mats:
            ok, info = _bind_image_sequence_to_material(
                mat, png_seq_dir, frame_rate, fps, total_frames,
            )
            if ok:
                bound += 1
                seq_results.append({"material": mat.name, **info})
            else:
                seq_results.append({"material": mat.name, "error": info})
        if bound > 0:
            return {"materials_animated": bound, "frame_count": total_frames,
                    "frame_rate": frame_rate, "content_type": content_type,
                    "path": "png_sequence", "seq_results": seq_results}
        # fall through to legacy color-anim if binding failed for all mats

    # LEGACY FALLBACK: animate base color (kept for backwards-compat)
    materials_animated = 0
    for mat in target_mats:
        bsdf = None
        for node in mat.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                bsdf = node
                break
        if bsdf is None:
            continue
        action, slot = _ensure_action_for_material(mat, "OledScroll")
        fcurves = _get_action_fcurves(action, slot)
        bc = bsdf.inputs.get("Base Color")
        if bc is None:
            continue
        path = bc.path_from_id("default_value")
        kf = [fcurves.new(data_path=path, index=i) for i in range(3)]
        for f in range(1, total_frames + 1):
            t = (f - 1) / float(total_frames)
            kf[0].keyframe_points.insert(f, 0.1 + 0.4 * (1 - t))
            kf[1].keyframe_points.insert(f, 0.6 - 0.3 * t)
            kf[2].keyframe_points.insert(f, 1.0)
        materials_animated += 1
    return {"materials_animated": materials_animated, "frame_count": total_frames,
            "frame_rate": frame_rate, "content_type": content_type,
            "path": "base_color_fallback"}


def _detect_creature_topology(mesh_obj, hint=None):
    """Decide which kind of skeleton fits the imported mesh."""
    if hint in ("humanoid", "quadruped", "serpent", "winged_creature", "arthropod"):
        return hint
    dx, dy, dz = mesh_obj.dimensions.x, mesh_obj.dimensions.y, mesh_obj.dimensions.z
    if max(dx, dy, dz) < 1e-4:
        return "none"
    long_axis = max(dx, dy, dz)
    short_axis = max(min(dx, dy, dz), 1e-4)
    aspect = long_axis / short_axis
    # Winged creature: wide wingspan relative to depth and height
    if dx >= dy * 1.25 and dx >= dz * 1.1:
        return "winged_creature"
    # Arthropod / insect: wide flat multi-leg silhouette
    if dz < min(dx, dy) * 0.65 and aspect >= 1.2:
        return "arthropod"
    # Vertical = Z dominant
    if dz >= dx and dz >= dy and aspect >= 1.4:
        return "humanoid"
    # Horizontal: X or Y dominant, Z is "low"
    horizontal = max(dx, dy)
    if horizontal >= dz * 1.4 and aspect >= 1.6:
        if aspect >= 4.0:
            return "serpent"
        return "quadruped"
    return "winged_creature" if dx >= dy else "quadruped"


def _add_breathing_scale_loop(target, fps, bpm):
    """Original simple breathing scale — used as the in-runner fallback when
    Rigify is unavailable or when topology is "none"."""
    period_frames = max(int(fps * 60.0 / max(bpm, 1.0)), 2)
    total_frames = period_frames * 2
    action, slot = _ensure_action_for_object(target, "CreatureBreathe")
    fcurves = _get_action_fcurves(action, slot)
    fc_z = fcurves.new(data_path="scale", index=2)
    fc_y = fcurves.new(data_path="scale", index=1)
    base_y = target.scale.y
    base_z = target.scale.z
    for f in range(1, total_frames + 1):
        phase = (math.sin(2 * math.pi * (f - 1) / period_frames) + 1) * 0.5
        fc_z.keyframe_points.insert(f, base_z * (1.0 + 0.02 * phase))
        fc_y.keyframe_points.insert(f, base_y * (1.0 + 0.015 * phase))
    return total_frames


def _rigify_creature_skeleton(mesh, topology, base_loop, bpm, fps):
    """Build a topology-appropriate Rigify / Armature rig + bake idle/walk/flap cycles."""
    info = {"topology": topology, "base_loop": base_loop, "bpm": bpm}
    try:
        bpy.ops.preferences.addon_enable(module="rigify")
    except Exception:
        pass

    # Center the mesh at origin so the metarig lines up
    if topology in ("humanoid", "quadruped", "winged_creature", "arthropod"):
        bpy.ops.object.select_all(action="DESELECT")
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")

    metarig = None
    try:
        if topology == "humanoid":
            bpy.ops.object.armature_human_metarig_add()
            metarig = bpy.context.object
        elif topology == "quadruped":
            try:
                bpy.ops.object.armature_basic_quadruped_metarig_add()
            except Exception:
                bpy.ops.object.armature_basic_human_metarig_add()
            metarig = bpy.context.object
        elif topology == "winged_creature":
            bpy.ops.object.armature_add(enter_editmode=True)
            metarig = bpy.context.object
            arm = metarig.data
            arm.edit_bones.remove(arm.edit_bones[0])
            dx, dy, dz = mesh.dimensions.x, mesh.dimensions.y, mesh.dimensions.z
            span_x = dx * 0.45
            span_z = dz * 0.35
            b_root = arm.edit_bones.new("root_body")
            b_root.head = (0, -dy * 0.1, dz * 0.2)
            b_root.tail = (0, dy * 0.1, dz * 0.5)
            b_head = arm.edit_bones.new("head")
            b_head.head = (0, dy * 0.1, dz * 0.5)
            b_head.tail = (0, dy * 0.25, dz * 0.75)
            b_head.parent = b_root
            w_l1 = arm.edit_bones.new("wing_root.L")
            w_l1.head = (dx * 0.08, -dy * 0.05, dz * 0.45)
            w_l1.tail = (span_x * 0.6, -dy * 0.08, dz * 0.45 + span_z * 0.5)
            w_l1.parent = b_root
            w_l2 = arm.edit_bones.new("wing_tip.L")
            w_l2.head = w_l1.tail
            w_l2.tail = (span_x, -dy * 0.1, dz * 0.45 + span_z)
            w_l2.parent = w_l1
            w_l2.use_connect = True
            w_r1 = arm.edit_bones.new("wing_root.R")
            w_r1.head = (-dx * 0.08, -dy * 0.05, dz * 0.45)
            w_r1.tail = (-span_x * 0.6, -dy * 0.08, dz * 0.45 + span_z * 0.5)
            w_r1.parent = b_root
            w_r2 = arm.edit_bones.new("wing_tip.R")
            w_r2.head = w_r1.tail
            w_r2.tail = (-span_x, -dy * 0.1, dz * 0.45 + span_z)
            w_r2.parent = w_r1
            w_r2.use_connect = True
            leg_l = arm.edit_bones.new("leg.L")
            leg_l.head = (dx * 0.15, 0, dz * 0.15)
            leg_l.tail = (dx * 0.15, 0, 0)
            leg_l.parent = b_root
            leg_r = arm.edit_bones.new("leg.R")
            leg_r.head = (-dx * 0.15, 0, dz * 0.15)
            leg_r.tail = (-dx * 0.15, 0, 0)
            leg_r.parent = b_root
            bpy.ops.object.mode_set(mode="OBJECT")
            info["winged_creature_rig"] = True
        elif topology == "arthropod":
            bpy.ops.object.armature_add(enter_editmode=True)
            metarig = bpy.context.object
            arm = metarig.data
            arm.edit_bones.remove(arm.edit_bones[0])
            dx, dy, dz = mesh.dimensions.x, mesh.dimensions.y, mesh.dimensions.z
            span_x = dx * 0.45
            b_thorax = arm.edit_bones.new("thorax")
            b_thorax.head = (0, -dy * 0.15, dz * 0.3)
            b_thorax.tail = (0, dy * 0.15, dz * 0.3)
            b_head = arm.edit_bones.new("head")
            b_head.head = (0, dy * 0.15, dz * 0.3)
            b_head.tail = (0, dy * 0.4, dz * 0.3)
            b_head.parent = b_thorax
            b_abd = arm.edit_bones.new("abdomen")
            b_abd.head = (0, -dy * 0.15, dz * 0.3)
            b_abd.tail = (0, -dy * 0.45, dz * 0.28)
            b_abd.parent = b_thorax
            w_l = arm.edit_bones.new("wing.L")
            w_l.head = (dx * 0.1, 0, dz * 0.4)
            w_l.tail = (span_x, -dy * 0.1, dz * 0.45 + dz * 0.3)
            w_l.parent = b_thorax
            w_r = arm.edit_bones.new("wing.R")
            w_r.head = (-dx * 0.1, 0, dz * 0.4)
            w_r.tail = (-span_x, -dy * 0.1, dz * 0.45 + dz * 0.3)
            w_r.parent = b_thorax
            for y_off, name_sfx in [(dy * 0.2, "front"), (0, "mid"), (-dy * 0.2, "rear")]:
                leg_l = arm.edit_bones.new("leg_%s.L" % name_sfx)
                leg_l.head = (dx * 0.18, y_off, dz * 0.25)
                leg_l.tail = (dx * 0.45, y_off, 0)
                leg_l.parent = b_thorax
                leg_r = arm.edit_bones.new("leg_%s.R" % name_sfx)
                leg_r.head = (-dx * 0.18, y_off, dz * 0.25)
                leg_r.tail = (-dx * 0.45, y_off, 0)
                leg_r.parent = b_thorax
            bpy.ops.object.mode_set(mode="OBJECT")
            info["arthropod_rig"] = True
            # iter6.C: build a denser 8-segment spine chain (smoother curve fit
            # for IK Spline). Length is split along whichever horizontal axis
            # is longer so we follow the actual snake orientation.
            bpy.ops.object.armature_add(enter_editmode=True)
            metarig = bpy.context.object
            arm = metarig.data
            arm.edit_bones.remove(arm.edit_bones[0])
            n_segments = 8
            length = max(mesh.dimensions.x, mesh.dimensions.y) / float(n_segments)
            prev = None
            for i in range(n_segments):
                b = arm.edit_bones.new("snake_%d" % i)
                b.head = (i * length, 0, 0)
                b.tail = ((i + 1) * length, 0, 0)
                if prev is not None:
                    b.parent = prev
                    b.use_connect = True
                prev = b
            bpy.ops.object.mode_set(mode="OBJECT")
            # Stash count + segment length for later IK Spline wiring
            info["serpent_segment_count"] = n_segments
            info["serpent_segment_length"] = length
        else:
            return None, 0, {"error": "unknown topology", **info}
    except Exception as exc:
        return None, 0, {"error": "metarig add failed: %s" % exc, **info}

    if metarig is None:
        return None, 0, {"error": "metarig is None", **info}
    metarig.name = "aurora_metarig"

    # Scale metarig to match mesh bbox
    try:
        verts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
        if verts:
            zs = [v.z for v in verts]
            xs = [v.x for v in verts]
            ys = [v.y for v in verts]
            if topology == "humanoid":
                height = max(zs) - min(zs)
                if height > 0.01:
                    metarig.scale = (height, height, height)
                    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                    metarig.location.z = min(zs)
            elif topology == "quadruped":
                length = max(ys) - min(ys)
                if length > 0.01:
                    s = length
                    metarig.scale = (s, s, s)
                    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                    metarig.location.z = min(zs) + (max(zs) - min(zs)) * 0.5
            elif topology == "serpent":
                length = max(xs) - min(xs)
                if length > 0.01:
                    metarig.location = (min(xs), (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.5)
    except Exception:
        pass

    # Generate the actual rig (skip for serpent — it's already a posable rig)
    rig = metarig
    if topology in ("humanoid", "quadruped"):
        bpy.context.view_layer.objects.active = metarig
        try:
            bpy.ops.pose.rigify_generate()
        except Exception as exc:
            return None, 0, {"error": "rigify_generate failed: %s" % exc, **info}
        # Find the generated rig: any armature that isn't the metarig
        try:
            if bpy.context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
        all_armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
        rig_candidates = [o for o in all_armatures if "metarig" not in o.name.lower()]
        if not rig_candidates:
            return None, 0, {"error": "rigify generated rig not found", **info}
        rig = rig_candidates[0]

    # Parent mesh to rig with automatic weights
    try:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        mesh.select_set(True)
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    except Exception as exc:
        return None, 0, {"error": "parenting failed: %s" % exc, **info}

    # Animate bones according to base_loop
    period_frames = max(int(fps * 60.0 / max(bpm, 1.0)), 2)
    total_frames = period_frames * 2 if base_loop == "idle_breathing" else period_frames * 4
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = total_frames

    if rig.animation_data is None:
        rig.animation_data_create()
    action = bpy.data.actions.new(name="CreatureLoop_%s_%s" % (topology, base_loop))
    rig.animation_data.action = action

    # Slot binding for Blender 5.x layered API
    slot = None
    if hasattr(action, "slots"):
        try:
            slot = action.slots.new(id_type="OBJECT", name=rig.name)
        except Exception:
            slot = action.slots[0] if len(action.slots) > 0 else None
        if slot is not None and hasattr(rig.animation_data, "action_slot"):
            try:
                rig.animation_data.action_slot = slot
            except Exception:
                pass
    if hasattr(action, "layers") and len(action.layers) == 0:
        layer = action.layers.new("Layer")
        layer.strips.new(type="KEYFRAME")
    fcurves = _get_action_fcurves(action, slot)

    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    try:
        bpy.ops.object.mode_set(mode="POSE")
    except Exception:
        pass

    # Pick bones to animate per topology
    bone_targets = []
    available_bones = [b.name for b in rig.pose.bones]
    info["available_bones_count"] = len(available_bones)

    def _first_match(*needles):
        for name in available_bones:
            ln = name.lower()
            for n in needles:
                if n in ln:
                    return name
        return None

    if topology == "humanoid":
        # Rigify humanoid: spine, chest, hand_ik.L/R, thigh_ik.L/R, foot_ik.L/R
        spine = _first_match("spine_fk", "spine.001", "spine") or available_bones[0]
        chest = _first_match("chest", "spine_fk.003", "spine.003") or spine
        head = _first_match("head") or chest
        hand_l = _first_match("hand_ik.l", "hand.l")
        hand_r = _first_match("hand_ik.r", "hand.r")
        foot_l = _first_match("foot_ik.l", "foot.l")
        foot_r = _first_match("foot_ik.r", "foot.r")
        # Idle: chest+head breathing (rotation + scale)
        bone_targets.append(("breathe", chest, "rotation_quaternion", 1, 0.04))
        bone_targets.append(("breathe", head, "rotation_quaternion", 1, 0.02))
        if base_loop in ("walk_cycle", "run_cycle"):
            if not (foot_l and foot_r):
                return None, 0, {"error": "humanoid locomotion missing both foot IK/bones", **info}
            stride = 0.15 if base_loop == "walk_cycle" else 0.30
            if foot_l: bone_targets.append(("walk_l", foot_l, "location", 1, stride))
            if foot_r: bone_targets.append(("walk_r", foot_r, "location", 1, stride))
            if hand_l: bone_targets.append(("walk_r", hand_l, "location", 1, stride * 0.5))
            if hand_r: bone_targets.append(("walk_l", hand_r, "location", 1, stride * 0.5))
    elif topology == "quadruped":
        # Quadruped basic: spine + legs + tail
        spine = _first_match("spine_fk.001", "spine.001", "back", "spine") or available_bones[0]
        chest = _first_match("chest", "spine_fk.002") or spine
        tail = _first_match("tail")
        # iter6.B: name-based first pass — covers Rigify quadruped + common
        # convention rigs (Mixamo-ish, free-form Blender, etc).
        leg_fl = _first_match("front_leg.l", "front.l", "fr_leg") or _first_match("hand.l")
        leg_fr = _first_match("front_leg.r", "front.r", "fl_leg") or _first_match("hand.r")
        leg_bl = _first_match("back_leg.l", "back.l", "br_leg") or _first_match("foot.l")
        leg_br = _first_match("back_leg.r", "back.r", "bl_leg") or _first_match("foot.r")
        # iter6.B: geometric fallback — when fewer than 4 legs were resolved by
        # name-matching (exotic rig conventions), identify the 4 leaf-most bones
        # whose head is lowest in Z (= feet) and split into front/back × L/R via
        # local X (sign of head.x) and local Y (sign of head.y). This is rig-name
        # agnostic and works on any 4-legged armature.
        named_legs = [n for n in (leg_fl, leg_fr, leg_bl, leg_br) if n]
        if len(named_legs) < 4:
            try:
                # Build leaf set: bones with no children. Use armature edit/data
                # head positions (rest pose) — pose.head moves at runtime.
                arm_data = rig.data
                bone_heads = {}  # name -> (x, y, z)
                bone_children = {}  # name -> count
                for b in arm_data.bones:
                    bone_heads[b.name] = (b.head_local.x, b.head_local.y, b.head_local.z)
                    bone_children[b.name] = 0
                for b in arm_data.bones:
                    if b.parent is not None:
                        bone_children[b.parent.name] = bone_children.get(b.parent.name, 0) + 1
                leaves = [n for n, c in bone_children.items() if c == 0]
                # Filter out anything that's clearly not a foot: skip face/jaw/eye/ear/teeth/
                # tongue + tail (already handled) + horn/finger detail.
                _NON_FOOT = ("eye", "ear", "tooth", "teeth", "tongue", "jaw", "face",
                             "horn", "finger", "thumb", "antenna", "whisker", "tail")
                leaves = [n for n in leaves if not any(k in n.lower() for k in _NON_FOOT)]
                # Sort by head Z ascending (lowest first = feet candidates)
                leaves.sort(key=lambda n: bone_heads[n][2])
                # Take up to 8 lowest, then keep the 4 lowest distinct (front/back × L/R)
                pool = leaves[: min(len(leaves), 8)]
                # Split L/R via X sign, then F/B via Y. Local axis convention:
                # Blender's quadruped metarig has +X = left, +Y = forward (head),
                # but exported rigs may differ — we use sign of bone-head coords
                # which is internally consistent regardless of world rotation.
                left = sorted([n for n in pool if bone_heads[n][0] >= 0],
                              key=lambda n: bone_heads[n][1])
                right = sorted([n for n in pool if bone_heads[n][0] < 0],
                               key=lambda n: bone_heads[n][1])
                # Pick most-forward + most-backward in each side (front=last, back=first)
                geo_fl = left[-1] if left else None
                geo_bl = left[0] if left and left[0] != geo_fl else None
                geo_fr = right[-1] if right else None
                geo_br = right[0] if right and right[0] != geo_fr else None
                # Only use geometric pick if it provides at least 4 distinct bones
                geo_legs = [n for n in (geo_fl, geo_fr, geo_bl, geo_br) if n]
                if len(set(geo_legs)) == 4:
                    leg_fl = leg_fl or geo_fl
                    leg_fr = leg_fr or geo_fr
                    leg_bl = leg_bl or geo_bl
                    leg_br = leg_br or geo_br
                    info["quadruped_geo_fallback"] = True
                    info["quadruped_geo_picks"] = {
                        "fl": geo_fl, "fr": geo_fr, "bl": geo_bl, "br": geo_br,
                    }
                # iter7.D: hexapod / multipod path. When > 4 valid leaf-bones
                # found and named pickup didn't cover them, animate ALL of them
                # with a phase-shifted gait that scales 2π / N. This makes
                # insects (6 legs), spiders (8 legs), and tripods walk plausibly
                # without any rig-name knowledge. Keep our 4-leg path intact for
                # mammalian quadrupeds — only switch when we find > 4 legs AND
                # quadruped picker didn't already claim them.
                hexapod_pool = leaves[: min(len(leaves), 12)]
                # Drop any bone already in the quadruped 4-pack so we don't
                # double-animate the same bone.
                hexapod_pool = [n for n in hexapod_pool
                                if n not in (leg_fl, leg_fr, leg_bl, leg_br)]
                if len(hexapod_pool) >= 2 and len(set(hexapod_pool)) >= 2:
                    info["multipod_extra_leg_count"] = len(hexapod_pool)
                    info["multipod_extra_legs"] = hexapod_pool[:8]
                    # Stash for the keyframe-loop section (added below as a
                    # parallel pass to bone_targets so we don't break the
                    # 4-leg gait).
            except Exception as exc:
                info["quadruped_geo_fallback_error"] = str(exc)
        bone_targets.append(("breathe", chest, "rotation_quaternion", 1, 0.04))
        if tail:
            bone_targets.append(("tail_wag", tail, "rotation_quaternion", 2, 0.10))
        if base_loop in ("walk_cycle", "run_cycle"):
            if len([n for n in (leg_fl, leg_fr, leg_bl, leg_br) if n]) < 4:
                return None, 0, {"error": "quadruped locomotion missing four leg targets", **info}
            stride = 0.10 if base_loop == "walk_cycle" else 0.20
            if leg_fl: bone_targets.append(("walk_l", leg_fl, "location", 1, stride))
            if leg_fr: bone_targets.append(("walk_r", leg_fr, "location", 1, stride))
            if leg_bl: bone_targets.append(("walk_r", leg_bl, "location", 1, stride))
            if leg_br: bone_targets.append(("walk_l", leg_br, "location", 1, stride))
            # iter7.D: hexapod / multipod extras — animate each leaf-bone leg
            # with phase = 2π * (i / N). For hexapods this gives the classic
            # tripod gait; for tripods/quadrupeds + spares it staggers smoothly.
            extra_legs = info.get("multipod_extra_legs") or []
            n_extra = len(extra_legs)
            if n_extra >= 2:
                stride_extra = stride * 0.7  # smaller insect stride
                for idx, leg_name in enumerate(extra_legs):
                    # Distribute phases evenly via 2π/N
                    phase_kind = "walk_phase_%d" % idx
                    bone_targets.append(
                        (phase_kind, leg_name, "location", 1, stride_extra),
                    )
    elif topology == "serpent":
        # iter6.C: Spline IK approach.
        #
        # Build a NURBS curve with 3 control points (head/mid/tail) along the
        # serpent's main axis, add a Spline IK constraint on the LAST snake bone
        # binding to the curve with chain_count=N. Animate the curve control
        # points with phase-shifted sinusoids -> body undulates as the spline
        # bends. This produces a much more natural swim than independent FK
        # rotations on each segment.
        #
        # Fallback: if Spline IK constraint isn't available (older Blender) or
        # any step fails, drop into the iter5 FK cascade (each bone gets a
        # phase-offset sine on rotation Y).
        snake_bones = [n for n in available_bones if n.startswith("snake_")]
        n_seg = len(snake_bones)
        seg_len = float(rigify_info.get("serpent_segment_length", 0.0)) if isinstance(rigify_info, dict) else 0.0
        # rigify_info isn't yet built at this scope; recompute from edit-bones.
        try:
            arm_data = rig.data
            xs = [bn.head_local.x for bn in arm_data.bones if bn.name.startswith("snake_")]
            if len(xs) >= 2:
                seg_len = abs(max(xs) - min(xs)) / max(len(xs) - 1, 1)
        except Exception:
            seg_len = 0.0
        spline_ik_ok = False
        spline_curve = None
        spline_hooks = None  # list of empties that drive curve points
        if n_seg >= 3 and seg_len > 0:
            try:
                # Switch to OBJECT mode briefly to add curve + empties.
                if bpy.context.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")
                # Build a Bezier-style NURBS curve with 3 points along X axis
                cu = bpy.data.curves.new(name="aurora_serpent_spline", type="CURVE")
                cu.dimensions = "3D"
                spline = cu.splines.new(type="BEZIER")
                spline.bezier_points.add(2)  # spline starts with 1 -> total 3
                # Anchor points at head, midpoint, tail of snake range
                # Use rest-pose head positions of segments 0, n/2, n-1
                bone_xs = sorted(xs)
                head_x = bone_xs[0]
                tail_x = bone_xs[-1] + seg_len  # extend by 1 segment for the tip
                mid_x = (head_x + tail_x) * 0.5
                pts = [(head_x, 0.0, 0.0), (mid_x, 0.0, 0.0), (tail_x, 0.0, 0.0)]
                for bp, p in zip(spline.bezier_points, pts):
                    bp.co = p
                    bp.handle_left = (p[0] - seg_len * 0.5, p[1], p[2])
                    bp.handle_right = (p[0] + seg_len * 0.5, p[1], p[2])
                    bp.handle_left_type = "AUTO"
                    bp.handle_right_type = "AUTO"
                curve_obj = bpy.data.objects.new("aurora_serpent_curve", cu)
                bpy.context.scene.collection.objects.link(curve_obj)
                # Match the rig's world transform so the curve sits where the snake is
                curve_obj.matrix_world = rig.matrix_world.copy()
                spline_curve = curve_obj
                # Add a Spline IK constraint to the last snake bone
                bpy.context.view_layer.objects.active = rig
                if bpy.context.mode != "POSE":
                    bpy.ops.object.mode_set(mode="POSE")
                last_bone = rig.pose.bones[snake_bones[-1]]
                # Spline IK constraint type identifier in Blender: "SPLINE_IK"
                con = last_bone.constraints.new(type="SPLINE_IK")
                con.target = curve_obj
                con.chain_count = n_seg
                # Use volume-preserving stretching so the body keeps mass
                try:
                    con.use_curve_radius = False
                    con.use_chain_offset = False
                    if hasattr(con, "y_scale_mode"):
                        con.y_scale_mode = "FIT_CURVE"
                    if hasattr(con, "xz_scale_mode"):
                        con.xz_scale_mode = "VOLUME_PRESERVE"
                except Exception:
                    pass
                spline_ik_ok = True
                info["serpent_spline_ik"] = True
                info["serpent_spline_segments"] = n_seg
            except Exception as exc:
                info["serpent_spline_ik_error"] = str(exc)
                spline_ik_ok = False
                # Cleanup any partial curve
                try:
                    if spline_curve is not None:
                        bpy.data.objects.remove(spline_curve, do_unlink=True)
                        spline_curve = None
                except Exception:
                    pass
        if spline_ik_ok and spline_curve is not None:
            # Animate the 3 curve control points (head, mid, tail) on Y with
            # phase-shifted sinusoids to produce a swimming undulation.
            # Curve animation uses the curve datablock's animation_data, NOT
            # the rig action — so we keyframe directly on bezier_points.co[1].
            try:
                cu = spline_curve.data
                if cu.animation_data is None:
                    cu.animation_data_create()
                curve_action = bpy.data.actions.new(name="SerpentCurveLoop")
                cu.animation_data.action = curve_action
                cur_slot = None
                if hasattr(curve_action, "slots"):
                    try:
                        cur_slot = curve_action.slots.new(id_type="CURVE", name=cu.name)
                        if cur_slot is not None and hasattr(cu.animation_data, "action_slot"):
                            cu.animation_data.action_slot = cur_slot
                    except Exception:
                        pass
                if hasattr(curve_action, "layers") and len(curve_action.layers) == 0:
                    layer = curve_action.layers.new("Layer")
                    layer.strips.new(type="KEYFRAME")
                cu_fcurves = _get_action_fcurves(curve_action, cur_slot)
                amplitude = max(seg_len * 1.5, 0.05)  # body lateral amplitude
                # Phase offsets — head leads, tail follows. Standard wave: phase
                # increases along body, period 1 cycle per total animation loop.
                phases = (0.0, math.pi * 0.6, math.pi * 1.2)
                for pt_idx, base_phase in enumerate(phases):
                    # data_path for a bezier point co.y = splines[0].bezier_points[i].co
                    dp = "splines[0].bezier_points[%d].co" % pt_idx
                    rest_y = 0.0
                    rest_x = pts[pt_idx][0]
                    rest_z = 0.0
                    for f in range(1, total_frames + 1):
                        phase = (f - 1) / float(period_frames) * 2.0 * math.pi
                        y_val = rest_y + math.sin(phase + base_phase) * amplitude
                        for ax, val in ((0, rest_x), (1, y_val), (2, rest_z)):
                            fc = next((c for c in cu_fcurves if c.data_path == dp and c.array_index == ax), None)
                            if fc is None:
                                try:
                                    fc = cu_fcurves.new(data_path=dp, index=ax)
                                except Exception:
                                    continue
                            fc.keyframe_points.insert(f, val)
                info["serpent_curve_keyframes"] = total_frames * 3
                # Spline IK already animates the bones — count chain_count.
                # We add a placeholder bone target so bones_animated reflects it.
                bones_animated_via_spline = n_seg
                info["serpent_bones_via_spline"] = bones_animated_via_spline
            except Exception as exc:
                info["serpent_spline_ik_anim_error"] = str(exc)
                spline_ik_ok = False
        if not spline_ik_ok:
            # Fallback: cascading sine wave on each segment (iter5 path).
            for i, name in enumerate(available_bones):
                if name.startswith("snake_"):
                    bone_targets.append(("snake_%d" % i, name, "rotation_quaternion", 2, 0.15))
            info["serpent_fallback_fk"] = True
    elif topology == "winged_creature":
        root = _first_match("root_body", "spine", "body") or available_bones[0]
        w_l1 = _first_match("wing_root.l", "wing.l", "wing_l")
        w_r1 = _first_match("wing_root.r", "wing.r", "wing_r")
        w_l2 = _first_match("wing_tip.l", "wing_flex.l")
        w_r2 = _first_match("wing_tip.r", "wing_flex.r")
        bone_targets.append(("breathe", root, "location", 2, 0.03))
        if w_l1: bone_targets.append(("wing_flap_l", w_l1, "rotation_quaternion", 0, 0.55))
        if w_r1: bone_targets.append(("wing_flap_r", w_r1, "rotation_quaternion", 0, 0.55))
        if w_l2: bone_targets.append(("wing_flex_l", w_l2, "rotation_quaternion", 0, 0.35))
        if w_r2: bone_targets.append(("wing_flex_r", w_r2, "rotation_quaternion", 0, 0.35))
    elif topology == "arthropod":
        root = _first_match("thorax", "body", "root") or available_bones[0]
        w_l = _first_match("wing.l", "wing_root.l")
        w_r = _first_match("wing.r", "wing_root.r")
        bone_targets.append(("breathe", root, "location", 2, 0.015))
        if w_l: bone_targets.append(("wing_flap_l", w_l, "rotation_quaternion", 0, 0.70))
        if w_r: bone_targets.append(("wing_flap_r", w_r, "rotation_quaternion", 0, 0.70))
        # 6-legged tripod gait
        l_fl = _first_match("leg_front.l", "leg_fl")
        l_fr = _first_match("leg_front.r", "leg_fr")
        l_ml = _first_match("leg_mid.l", "leg_ml")
        l_mr = _first_match("leg_mid.r", "leg_mr")
        l_rl = _first_match("leg_rear.l", "leg_rl")
        l_rr = _first_match("leg_rear.r", "leg_rr")
        if l_fl: bone_targets.append(("walk_l", l_fl, "location", 1, 0.04))
        if l_fr: bone_targets.append(("walk_r", l_fr, "location", 1, 0.04))
        if l_ml: bone_targets.append(("walk_r", l_ml, "location", 1, 0.04))
        if l_mr: bone_targets.append(("walk_l", l_mr, "location", 1, 0.04))
        if l_rl: bone_targets.append(("walk_l", l_rl, "location", 1, 0.04))
        if l_rr: bone_targets.append(("walk_r", l_rr, "location", 1, 0.04))

    # Apply keyframes
    bones_animated = 0
    for kind, bone_name, prop, axis_idx, amplitude in bone_targets:
        if not bone_name:
            continue
        pb = rig.pose.bones.get(bone_name)
        if pb is None:
            continue
        # Set rotation_mode to QUATERNION (default for pose bones)
        if prop == "rotation_quaternion":
            data_path = 'pose.bones["%s"].rotation_quaternion' % bone_name
            for f in range(1, total_frames + 1):
                phase = (f - 1) / float(period_frames)
                if kind == "breathe":
                    val = math.sin(2 * math.pi * phase) * amplitude
                    qw = 1.0 - abs(val) * 0.5
                    qx = val if axis_idx == 0 else 0.0
                    qy = val if axis_idx == 1 else 0.0
                    qz = val if axis_idx == 2 else 0.0
                elif kind == "tail_wag":
                    val = math.sin(2 * math.pi * phase * 0.5) * amplitude
                    qw = 1.0 - abs(val) * 0.5
                    qx = qy = qz = 0.0
                    if axis_idx == 0: qx = val
                    elif axis_idx == 1: qy = val
                    else: qz = val
                elif kind == "wing_flap_l":
                    val = math.sin(2 * math.pi * phase * 2.0) * amplitude
                    qw = 1.0 - abs(val) * 0.5
                    qx = val
                    qy = qz = 0.0
                elif kind == "wing_flap_r":
                    val = -math.sin(2 * math.pi * phase * 2.0) * amplitude
                    qw = 1.0 - abs(val) * 0.5
                    qx = val
                    qy = qz = 0.0
                elif kind == "wing_flex_l":
                    val = math.sin(2 * math.pi * phase * 2.0 - 0.5) * amplitude
                    qw = 1.0 - abs(val) * 0.5
                    qx = val
                    qy = qz = 0.0
                elif kind == "wing_flex_r":
                    val = -math.sin(2 * math.pi * phase * 2.0 - 0.5) * amplitude
                    qw = 1.0 - abs(val) * 0.5
                    qx = val
                    qy = qz = 0.0
                elif kind.startswith("snake_"):
                    seg_idx = int(kind.split("_")[1])
                    val = math.sin(2 * math.pi * phase + seg_idx * 0.6) * amplitude
                    qw = 1.0 - abs(val) * 0.5
                    qx = qy = qz = 0.0
                    if axis_idx == 0: qx = val
                    elif axis_idx == 1: qy = val
                    else: qz = val
                else:
                    qw, qx, qy, qz = 1.0, 0.0, 0.0, 0.0
                # Insert 4 keyframes (qw, qx, qy, qz)
                for ki, qv in enumerate((qw, qx, qy, qz)):
                    fc = next((c for c in fcurves if c.data_path == data_path and c.array_index == ki), None)
                    if fc is None:
                        try:
                            fc = fcurves.new(data_path=data_path, index=ki)
                        except Exception:
                            continue
                    fc.keyframe_points.insert(f, qv)
            bones_animated += 1
        elif prop == "location":
            data_path = 'pose.bones["%s"].location' % bone_name
            # iter7.D: pre-compute multipod count for phase distribution
            multipod_n = len(info.get("multipod_extra_legs") or [])
            for f in range(1, total_frames + 1):
                phase = (f - 1) / float(period_frames)
                if kind == "walk_l":
                    val = math.sin(2 * math.pi * phase) * amplitude
                elif kind == "walk_r":
                    val = math.sin(2 * math.pi * phase + math.pi) * amplitude
                elif kind.startswith("walk_phase_"):
                    # iter7.D: phase = 2π * (i / N) staggered gait for hexapods
                    leg_idx = int(kind.split("_")[2])
                    leg_phase_offset = (2.0 * math.pi * leg_idx) / max(multipod_n, 1)
                    val = math.sin(2 * math.pi * phase + leg_phase_offset) * amplitude
                else:
                    val = 0.0
                fc = next((c for c in fcurves if c.data_path == data_path and c.array_index == axis_idx), None)
                if fc is None:
                    try:
                        fc = fcurves.new(data_path=data_path, index=axis_idx)
                    except Exception:
                        continue
                fc.keyframe_points.insert(f, val)
            bones_animated += 1

    # Back to OBJECT mode for export
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass

    # iter7.A: SPLINE_IK glTF export safety net.
    #
    # The Spline IK constraint produces bone rotations PROCEDURALLY at evaluation
    # time — they are NOT keyframed. Blender's glTF exporter samples object
    # transforms via export_force_sampling=True, but bone constraint outputs are
    # historically unreliable: the exporter walks fcurves, not the constraint
    # stack. Without a visual-keying bake the snake exports as a static mesh
    # with the curve animation in a curve datablock that glTF cannot represent.
    #
    # Fix: convert the procedural spline IK output into real bone-quaternion
    # keyframes via bpy.ops.nla.bake(visual_keying=True, clear_constraints=True).
    # We do this BEFORE export so the rig has 8 bones × 4 quat channels = 32
    # fcurves of explicit pose data which the glTF exporter ALWAYS samples.
    if topology == "serpent" and info.get("serpent_spline_ik"):
        try:
            # Activate rig + select all snake bones in pose mode
            bpy.ops.object.select_all(action="DESELECT")
            rig.select_set(True)
            bpy.context.view_layer.objects.active = rig
            try:
                bpy.ops.object.mode_set(mode="POSE")
            except Exception:
                pass
            try:
                bpy.ops.pose.select_all(action="SELECT")
            except Exception:
                pass
            # Visual-keying bake: samples the constraint output every frame and
            # emits real keyframes on the bones. We CLEAR the constraint after
            # so the exporter sees a plain animated rig (no live constraint to
            # mis-evaluate). The curve animation can be safely discarded.
            try:
                bpy.ops.nla.bake(
                    frame_start=int(scene.frame_start),
                    frame_end=int(scene.frame_end),
                    only_selected=False,
                    visual_keying=True,
                    clear_constraints=True,
                    clear_parents=False,
                    use_current_action=False,
                    bake_types={"POSE"},
                )
                info["serpent_spline_ik_baked"] = True
                # Count how many keyframes we produced (8 bones × 4 quat × N frames)
                baked_kf = 0
                if rig.animation_data and rig.animation_data.action:
                    act = rig.animation_data.action
                    cb_fcurves = _get_action_fcurves(act, None)
                    try:
                        for fc in cb_fcurves:
                            baked_kf += len(fc.keyframe_points)
                    except Exception:
                        pass
                info["serpent_spline_ik_baked_keyframes"] = baked_kf
                print("AURORA_SPLINE_IK_BAKED %d keyframes" % baked_kf)
            except Exception as exc:
                info["serpent_spline_ik_bake_error"] = str(exc)
        except Exception as exc:
            info["serpent_spline_ik_bake_setup_error"] = str(exc)
        # Back to OBJECT mode for export
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

    # iter6.C: spline IK drives N bones via constraint, not via per-bone keyframes.
    if topology == "serpent" and info.get("serpent_spline_ik") and info.get("serpent_bones_via_spline"):
        bones_animated += int(info.get("serpent_bones_via_spline", 0))
    info["bones_animated"] = bones_animated
    info["frame_count"] = total_frames
    info["rig_name"] = rig.name
    return rig, total_frames, info


def bake_creature_organic(intent, scene, fps):
    cr = intent.get("creature_anim") or {}
    base_loop = cr.get("base_loop") or "idle_breathing"
    bpm = float(cr.get("bpm") or 14)
    locomotion_hint = cr.get("locomotion")  # iter5.A: humanoid|quadruped|serpent|auto
    wants_locomotion = base_loop in ("walk_cycle", "run_cycle")

    target = _largest_mesh(scene)
    if target is None:
        return {"error": "no mesh found"}

    # Detect topology (heuristic + optional user hint)
    topology = _detect_creature_topology(target, locomotion_hint)

    # Try Rigify path first when topology is recognised
    rigify_info = None
    if topology in ("humanoid", "quadruped", "serpent", "winged_creature", "arthropod"):
        try:
            rig, total_frames, rigify_info = _rigify_creature_skeleton(
                target, topology, base_loop, bpm, fps,
            )
            if rig is not None and total_frames > 0:
                # Success — return rig info
                return {
                    "target": target.name,
                    "rig_name": rig.name,
                    "topology": topology,
                    "base_loop": base_loop,
                    "bpm": bpm,
                    "frame_count": total_frames,
                    "bones_animated": rigify_info.get("bones_animated", 0),
                    "available_bones": rigify_info.get("available_bones_count", 0),
                    "path": "rigify",
                }
        except Exception as exc:
            rigify_info = {"error": "rigify exception: %s" % exc}

    # Never disguise a failed locomotion request as a root/scale bob. A walk or
    # run must articulate limbs/spine/feet, otherwise the caller should reject
    # the bake and trigger a stricter rig pass.
    if wants_locomotion:
        return {
            "error": "locomotion requires articulated rig; refusing breathing/root-bob fallback",
            "target": target.name,
            "topology": topology,
            "base_loop": base_loop,
            "bpm": bpm,
            "path": "locomotion_requires_rig",
            "rigify_attempt": rigify_info,
        }

    # Fallback: simple breathing scale loop (no rig)
    period_frames = max(int(fps * 60.0 / max(bpm, 1.0)), 2)
    total_frames = period_frames * 2
    scene.frame_start = 1
    scene.frame_end = total_frames
    _add_breathing_scale_loop(target, fps, bpm)
    return {
        "target": target.name,
        "topology": topology,
        "base_loop": base_loop,
        "bpm": bpm,
        "frame_count": total_frames,
        "path": "breathing_scale_fallback",
        "rigify_attempt": rigify_info,
    }


def _world_bbox(obj):
    corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)


def _fluid_zone_for(target, flow_type):
    x0, y0, z0, x1, y1, z1 = _world_bbox(target)
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    d = max(min(dx, dy), 1e-3)
    h = max(dz, 1e-3)
    if flow_type in ("fountain", "pour"):
        jet_h = max(h * 0.6, 0.05)
        return {"center": [cx, cy, z1 + jet_h * 0.5],
                "size": [d * 0.25, d * 0.25, jet_h]}
    if flow_type == "waterfall":
        return {"center": [cx, y1, (z0 + z1) * 0.5],
                "size": [max(dx * 0.6, 0.02), max(dy * 0.08, 0.01), h]}
    return {"center": [cx, cy, z0 + h * 0.24],
            "size": [max(dx * 0.72, 0.05), max(dy * 0.72, 0.05), max(h * 0.06, 0.02)]}


def _gas_zone_for(target):
    x0, y0, z0, x1, y1, z1 = _world_bbox(target)
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    d = max(min(dx, dy), 1e-3)
    plume_h = max(dz * 0.8, 0.1)
    return {"center": [cx, cy, z1 + plume_h * 0.5],
            "size": [d * 0.5, d * 0.5, plume_h]}


def _import_sibling(module_name):
    sibling_dir = os.path.dirname(os.path.abspath(__file__))
    if sibling_dir not in sys.path:
        sys.path.append(sibling_dir)
    import importlib
    return importlib.import_module(module_name)


def bake_fluid_flow(intent, scene, fps):
    try:
        fluid_mesh_builder = _import_sibling("fluid_mesh_builder")
    except Exception as exc:
        return {"error": "fluid_mesh_builder import failed: %s" % exc}
    fl = intent.get("fluid_anim") or {}
    flow_type = fl.get("flow_type") or "ripple"
    wave_amplitude = float(fl.get("wave_amplitude") or 0.35)
    loop_s = float(fl.get("loop_s") or 3.0)
    droplets = bool(fl.get("droplets") or False)
    target = _largest_mesh(scene)
    zone = intent.get("fluid_zone") if isinstance(intent.get("fluid_zone"), dict) else None
    if zone is None:
        if target is None:
            zone = {"center": [0.0, 0.0, 0.5], "size": [1.0, 1.0, 1.0]}
        else:
            try:
                zone = _fluid_zone_for(target, flow_type)
            except Exception as exc:
                return {"error": "fluid zone failed: %s" % exc}
    builds = []
    try:
        if flow_type in ("fountain", "pour") and target is not None:
            basin = fluid_mesh_builder.create_water_surface(
                _fluid_zone_for(target, "ripple"), "ripple",
                wave_amplitude=wave_amplitude, loop_s=loop_s, fps=fps,
                name="AuroraBassin",
            )
            builds.append(basin)
        info = fluid_mesh_builder.create_water_surface(
            zone, flow_type, wave_amplitude=wave_amplitude,
            loop_s=loop_s, fps=fps,
            droplets=droplets or flow_type in ("fountain", "pour"),
        )
        builds.append(info)
    except Exception as exc:
        return {"error": "fluid build failed: %s" % exc}
    info["water_builds"] = len(builds)
    total_frames = max(int(b.get("frame_count") or 1) for b in builds)
    scene.frame_start = 1
    scene.frame_end = max(total_frames, 1)
    info["flow_type"] = flow_type
    info["target"] = target.name if target is not None else None
    info["zone"] = zone
    info["path"] = "fluid_mesh_builder"
    return info


def bake_gas_volume(intent, scene, fps):
    try:
        smoke_card_builder = _import_sibling("smoke_card_builder")
    except Exception as exc:
        return {"error": "smoke_card_builder import failed: %s" % exc}
    g = intent.get("gas_anim") or {}
    kind = g.get("kind") or "smoke"
    rise_speed = float(g.get("rise_speed") or 0.3)
    billow_amplitude = float(g.get("billow_amplitude") or 0.5)
    loop_s = float(g.get("loop_s") or 4.0)
    target = _largest_mesh(scene)
    zone = intent.get("gas_zone") if isinstance(intent.get("gas_zone"), dict) else None
    if zone is None:
        if target is None:
            zone = {"center": [0.0, 0.0, 0.75], "size": [1.0, 1.0, 1.5]}
        else:
            try:
                zone = _gas_zone_for(target)
            except Exception as exc:
                return {"error": "gas zone failed: %s" % exc}
    try:
        info = smoke_card_builder.create_smoke_cards(
            zone, kind=kind, rise_speed=rise_speed,
            billow_amplitude=billow_amplitude, loop_s=loop_s, fps=fps,
        )
    except Exception as exc:
        return {"error": "gas build failed: %s" % exc}
    total_frames = int(info.get("frame_count") or 1)
    scene.frame_start = 1
    scene.frame_end = max(total_frames, 1)
    info["target"] = target.name if target is not None else None
    info["zone"] = zone
    info["path"] = "smoke_card_builder"
    return info


def bake_rigid_static(intent, scene, fps):
    scene.frame_start = 1
    scene.frame_end = 1
    for obj in scene.objects:
        if obj.animation_data and obj.animation_data.action:
            obj.animation_data_clear()
    return {"static": True, "frame_count": 1}


# ---------------------------------------------------------------------------
# Physique Blender native (tissu, corps rigides, corps mou, brins)
#
# Ces quatre domaines existaient dans Blender depuis toujours et n'etaient
# branches NULLE PART: un drap, un empilement qui s'ecroule, une gelee qui
# tremble ou une criniere au vent n'avaient aucun chemin. Ils partagent la meme
# mecanique: on pose des modificateurs physiques, on laisse le solveur tourner,
# puis on FIGE le resultat en cles de forme image par image — c'est la seule
# facon de faire tenir une simulation dans un GLB (un GLB ne transporte pas un
# solveur, seulement des sommets).
# ---------------------------------------------------------------------------

def _ground_plane(scene, obj, margin=0.02, collider=False):
    """Sol passif juste sous le sujet (sinon tout tombe a l'infini).

    `collider`: pose un modificateur de collision. Les corps rigides passent par
    le monde de corps rigides et n'en ont pas besoin; le tissu et le corps mou,
    SI: sans lui le sol n'existe pas pour eux et l'objet le traverse (mesure:
    5,69 m de chute pour un lacher de 0,24 m).
    """
    lo = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
    size = max(2.0, 4.0 * max(obj.dimensions.x, obj.dimensions.y, 0.25))
    me = bpy.data.meshes.new("AuroraGround")
    ground = bpy.data.objects.new("AuroraGround", me)
    scene.collection.objects.link(ground)
    h = size / 2.0
    me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)],
                   [], [(0, 1, 2, 3)])
    me.update()
    ground.location.z = lo - margin
    if collider:
        ground.modifiers.new("AuroraCollision", "COLLISION")
    return ground


def _bake_to_shape_keys(obj, scene, f_start, f_end, name, mod=None):
    """Fige un solveur en cles de forme (une par image), puis les anime.

    EN DEUX TEMPS, et c'est indispensable. Ajouter une cle de forme pendant que
    le solveur tourne change l'evaluation du maillage a l'image suivante: le
    solveur se nourrit de sa propre sortie et le resultat exporte ne bouge plus
    du tout (mesure: 37 cles ecrites, 0,0 m de deplacement). On LIT donc toutes
    les images d'abord, on retire le modificateur, puis seulement on ecrit.

    Le nombre de sommets ne doit pas changer — vrai pour tissu/corps mou, faux
    pour une fracture, qui doit alors sortir en cache et non en GLB.
    """
    n_verts = len(obj.data.vertices)
    frames = []
    for fr in range(f_start, f_end + 1):
        scene.frame_set(fr)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        if len(me.vertices) != n_verts:
            ev.to_mesh_clear()
            return {"error": "le solveur change le nombre de sommets "
                             "(%d -> %d): sortie en cache, pas en GLB"
                             % (n_verts, len(me.vertices)),
                    "frames_done": len(frames)}
        frames.append([v.co.copy() for v in me.vertices])
        ev.to_mesh_clear()
    if mod is not None:
        try:
            obj.modifiers.remove(mod)
        except Exception:  # noqa: BLE001
            pass
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Base", from_mix=False)
    moved = 0.0
    for offset, coords in enumerate(frames):
        fr = f_start + offset
        kb = obj.shape_key_add(name="%s_%03d" % (name, fr), from_mix=False)
        for i, co in enumerate(coords):
            kb.data[i].co = co
        moved = max(moved, max((c - v.co).length
                               for c, v in zip(coords, obj.data.vertices)))
        # une cle active a son image, eteinte partout ailleurs
        kb.value = 0.0
        kb.keyframe_insert("value", frame=max(f_start, fr - 1))
        kb.value = 1.0
        kb.keyframe_insert("value", frame=fr)
        kb.value = 0.0
        kb.keyframe_insert("value", frame=min(f_end, fr + 1))
    out = {"shape_keys": len(frames), "amplitude_m": round(moved, 4)}
    # Un baker qui rend "ok" sur une simulation qui n'a rien fait est pire
    # qu'une erreur: on le dit.
    if moved < 1e-4:
        out["error"] = "la simulation n'a produit aucun mouvement"
    return out


def bake_cloth_drape(intent, scene, fps):
    """Tissu reel: rideau, drapeau, cape, voile, bache, nappe."""
    c = intent.get("cloth_anim") or {}
    loop_s = float(c.get("loop_s") or 3.0)
    stiff = max(0.0, min(1.0, float(c.get("stiffness") or 0.3)))
    wind = max(0.0, min(1.0, float(c.get("wind") or 0.2)))
    pinning = c.get("pinning") or "auto"
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun maillage a simuler"}
    f_end = max(2, int(round(loop_s * fps)))
    scene.frame_start, scene.frame_end = 1, f_end

    # Accroche. L'axe d'accrochage ne peut pas etre Z par principe: une nappe
    # ou un drapeau a plat ont TOUS leurs sommets a la meme hauteur, et
    # "epingler le bord du haut" epinglait alors la totalite du tissu — qui ne
    # bougeait plus d'un millimetre. On accroche donc le long de l'axe ou le
    # tissu est vraiment etendu, en prenant Z quand il est significatif.
    pinned = 0
    if pinning != "none":
        co = [v.co for v in obj.data.vertices]
        spans = [max(c[i] for c in co) - min(c[i] for c in co) for i in range(3)]
        widest = max(spans)
        axis = 2 if spans[2] >= 0.10 * widest else max(range(2), key=lambda i: spans[i])
        hi = max(c[axis] for c in co)
        span = max(spans[axis], 1e-6)
        band = 0.05 if pinning in ("top_edge", "auto") else 0.15
        idx = [v.index for v in obj.data.vertices
               if (hi - v.co[axis]) / span <= band]
        if pinning in ("corners", "top_corners") and idx:
            others = [i for i in range(3) if i != axis]
            lo0 = min(obj.data.vertices[i].co[others[0]] for i in idx)
            hi0 = max(obj.data.vertices[i].co[others[0]] for i in idx)
            w0 = max(hi0 - lo0, 1e-6)
            idx = [i for i in idx
                   if min(abs(obj.data.vertices[i].co[others[0]] - lo0),
                          abs(obj.data.vertices[i].co[others[0]] - hi0)) < 0.15 * w0]
        # Un tissu epingle en totalite ne peut pas tomber: on renonce plutot
        # que de livrer une simulation immobile.
        if idx and len(idx) < 0.85 * len(obj.data.vertices):
            obj.vertex_groups.new(name="AuroraPin").add(idx, 1.0, "REPLACE")
            pinned = len(idx)

    mod = obj.modifiers.new("AuroraCloth", "CLOTH")
    st = mod.settings
    st.quality = 8
    st.mass = 0.3
    st.tension_stiffness = 5.0 + 35.0 * stiff
    st.compression_stiffness = 5.0 + 35.0 * stiff
    st.shear_stiffness = 5.0 + 35.0 * stiff
    st.bending_stiffness = 0.05 + 4.0 * stiff
    if pinned:
        st.vertex_group_mass = "AuroraPin"
    # Meme raison que pour le corps mou: les doublons de couture d'un maillage
    # importe se collisionnent en permanence avec eux-memes.
    mod.collision_settings.use_self_collision = False
    # La plage de simulation vit sur le CACHE du modificateur, pas sur ses
    # reglages (ClothSettings n'a pas de frame_start).
    try:
        mod.point_cache.frame_start = 1
        mod.point_cache.frame_end = f_end
    except Exception:  # noqa: BLE001
        pass

    if wind > 0.01:
        wf = bpy.data.objects.new("AuroraWind", None)
        scene.collection.objects.link(wf)
        wf.location = (0.0, -3.0 * max(obj.dimensions.y, 1.0), obj.location.z)
        wf.rotation_euler = (1.5708, 0.0, 0.0)
        bpy.context.view_layer.objects.active = wf
        bpy.ops.object.forcefield_toggle()
        wf.field.type = "WIND"
        wf.field.strength = 40.0 * wind
        wf.field.noise = 2.0 * wind

    r = _bake_to_shape_keys(obj, scene, 1, f_end, "cloth", mod=mod)
    return {"frame_count": f_end, "pinning": pinning, "sommets_epingles": pinned,
            "wind": wind, **r}


def bake_rigid_bodies(intent, scene, fps):
    """Solides en chute libre: tombe, bascule, s'ecroule, se disperse, roule."""
    r = intent.get("rigid_anim") or {}
    dur = float(r.get("duration_s") or 2.5)
    drop = float(r.get("drop_height_m") or 0.6)
    bounce = max(0.0, min(1.0, float(r.get("bounciness") or 0.2)))
    event = r.get("event") or "fall"
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun maillage a simuler"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end

    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    scene.rigidbody_world.point_cache.frame_start = 1
    scene.rigidbody_world.point_cache.frame_end = f_end

    ground = _ground_plane(scene, obj)
    bpy.context.view_layer.objects.active = ground
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    ground.rigid_body.friction = 0.8
    ground.rigid_body.collision_shape = "MESH"

    obj.location.z += drop
    # Les objets importes de glTF sont en rotation_mode QUATERNION: des cles
    # rotation_euler y sont IGNOREES a l'evaluation, donc absentes de l'export
    # (constate: GLB sans aucun canal rotation). XYZ obligatoire avant de keyframer.
    obj.rotation_euler = obj.rotation_quaternion.to_euler("XYZ")
    obj.rotation_mode = "XYZ"
    if event == "topple":
        obj.rotation_euler.y += 0.20
    bpy.context.view_layer.objects.active = obj
    bpy.ops.rigidbody.object_add(type="ACTIVE")
    obj.rigid_body.restitution = bounce
    obj.rigid_body.friction = 0.5
    # CONVEX_HULL: une coque convexe est stable et rapide. Un maillage concave
    # en collision fait traverser le sol une image sur deux.
    obj.rigid_body.collision_shape = "CONVEX_HULL"

    # Le corps rigide deplace l'OBJET sans deformer le maillage: on grave la
    # trajectoire en cles de transformation (bien plus leger qu'une cle de
    # forme par image). EN DEUX TEMPS: poser une cle des l'image 1 rend l'objet
    # anime, ce qui reprend la main sur le solveur pour les images suivantes —
    # la chute partait alors a 2,5 m au lieu de 0,8. On releve tout, puis on
    # ecrit.
    track = []
    for fr in range(1, f_end + 1):
        scene.frame_set(fr)
        track.append((fr, obj.matrix_world.to_translation().copy(),
                      obj.matrix_world.to_euler().copy()))
    z0 = track[0][1].z
    fall = max(0.0, z0 - min(t[1].z for t in track))
    bpy.ops.rigidbody.object_remove()
    for fr, loc, rot in track:
        obj.location = loc
        obj.rotation_euler = rot
        obj.keyframe_insert("location", frame=fr)
        obj.keyframe_insert("rotation_euler", frame=fr)
    bpy.data.objects.remove(ground, do_unlink=True)
    out = {"frame_count": f_end, "event": event, "drop_height_m": drop,
           "chute_reelle_m": round(fall, 3), "path": "blender_rigidbody"}
    if fall < 1e-3:
        out["error"] = "le solide n'a pas bouge"
    elif fall > 3.0 * max(drop, 0.05):
        out["error"] = ("le solide a traverse le sol (%.2f m pour une chute "
                        "de %.2f m)" % (fall, drop))
    return out


def bake_soft_body(intent, scene, fps):
    """Volume mou qui s'ecrase et tremble: gelee, coussin, peluche, ballon."""
    s = intent.get("soft_anim") or {}
    dur = float(s.get("duration_s") or 2.5)
    soft = max(0.0, min(1.0, float(s.get("softness") or 0.5)))
    bounce = max(0.0, min(1.0, float(s.get("bounce") or 0.4)))
    trigger = s.get("trigger") or "jiggle"
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun maillage a simuler"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end

    # IL FAUT UNE CAUSE. Une gelee posee que rien ne touche ne tremble pas: le
    # solveur tournait pour un resultat rigoureusement immobile. On donne donc
    # une cause physique au mouvement selon le declencheur — un choc au sol
    # pour "drop", une secousse du support pour "jiggle"/"squash", que le corps
    # mou suit avec du retard (c'est exactement ce qui fait trembler une gelee).
    size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.1)
    if trigger == "drop":
        obj.location.z += 0.4 * max(obj.dimensions.z, 0.2)
        _ground_plane(scene, obj, collider=True)
    else:
        kick = (0.18 if trigger == "jiggle" else 0.30) * size
        base_z = obj.location.z
        for fr, dz in ((1, 0.0), (3, -kick), (6, 0.0)):
            obj.location.z = base_z + dz
            obj.keyframe_insert("location", frame=fr)
        obj.location.z = base_z

    mod = obj.modifiers.new("AuroraSoft", "SOFT_BODY")
    st = mod.settings
    st.use_goal = (trigger == "jiggle")
    if st.use_goal:
        # "goal" = memoire de forme: le corps revient a sa silhouette. Sans lui
        # une gelee posee sur rien s'affaisse jusqu'a devenir une flaque.
        st.goal_default = 0.7 - 0.4 * soft
        st.goal_spring = 0.6
    st.use_edges = True
    st.pull = 0.9 - 0.6 * soft
    st.push = 0.9 - 0.6 * soft
    st.bend = 0.5 - 0.4 * soft
    st.damping = 0.5 * (1.0 - bounce)
    st.mass = 1.0
    st.speed = 1.0
    # AUTO-COLLISION DESACTIVEE, et ce n'est pas une facilite. Un maillage
    # importe a ses sommets DEDOUBLES aux coutures UV (ici 1488 la ou la forme
    # n'en compte que 386): chaque paire de doublons est alors en contact
    # permanent avec elle-meme et le solveur fige le corps — resultat mesure:
    # 36 images simulees, 0,0 m d'amplitude. Meme famille que les fissures de
    # lissage aux coutures. A reactiver seulement apres soudure du maillage.
    st.use_self_collision = False

    r = _bake_to_shape_keys(obj, scene, 1, f_end, "soft", mod=mod)
    return {"frame_count": f_end, "trigger": trigger, "softness": soft, **r}


def bake_hair_fur(intent, scene, fps):
    """Brins qui ondulent: cheveux, fourrure, criniere, plumes, herbe.

    Les brins ne rentrent pas dans un GLB en tant que systeme de particules:
    on les convertit en maillage, PUIS on anime ce maillage. Sans cette
    conversion l'export ne contient rien du tout.
    """
    h = intent.get("hair_anim") or {}
    kind = h.get("kind") or "hair"
    length = float(h.get("length_m") or 0.12)
    wind = max(0.0, min(1.0, float(h.get("wind") or 0.35)))
    loop_s = float(h.get("loop_s") or 3.0)
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun maillage a porter les brins"}
    f_end = max(2, int(round(loop_s * fps)))
    scene.frame_start, scene.frame_end = 1, f_end

    # LES BRINS NE RENTRENT PAS DANS UN GLB, et le dire vaut mieux que de
    # livrer un fichier vide. Un systeme de brins Blender n'a pas de faces:
    # converti en maillage il ne donne que des aretes, et le format glTF
    # n'exporte que des triangles — verifie, l'export ne contenait rien.
    # On produit donc une COQUE DE FOURRURE: quelques copies de la surface
    # decalees le long des normales, animees par le vent. C'est exportable,
    # c'est ce que font les moteurs temps reel, et la vraie chevelure brin par
    # brin reste disponible par la voie rendu (sequence d'images).
    shells = max(2, min(6, int(round(2 + 4 * min(1.0, length / 0.3)))))
    step = max(length / shells, 1e-4)
    made = []
    for i in range(1, shells + 1):
        cp = obj.copy()
        cp.data = obj.data.copy()
        cp.name = "AuroraFur_%d" % i
        scene.collection.objects.link(cp)
        sol = cp.modifiers.new("AuroraShell", "SOLIDIFY")
        sol.thickness = step * i
        sol.offset = 1.0
        sol.use_rim = False
        # On FIGE la coque dans le maillage: un modificateur ne traverse pas
        # l'export, seuls les sommets le font.
        bpy.context.view_layer.objects.active = cp
        try:
            bpy.ops.object.modifier_apply(modifier=sol.name)
        except Exception:  # noqa: BLE001
            cp.modifiers.remove(sol)
        made.append(cp)
    if not made:
        return {"error": "coque de fourrure impossible sur ce maillage",
                "voie_recommandee": "rendu"}

    # LE MOUVEMENT DOIT ETRE DANS LES SOMMETS. Une rotation d'objet de 1,7° est
    # supprimee a l'export (l'optimiseur d'animation jette les canaux juges
    # insignifiants) — la fourrure sortait donc immobile. On couche donc les
    # poils dans le vent en deplacant les sommets, en cle de forme: la coque
    # exterieure se couche le plus, celle du dessous a peine, ce qui donne la
    # vague qui parcourt le pelage.
    half = max(2, f_end // 2)
    lay = 0.9 * step  # de quoi coucher un poil de sa propre longueur
    amp_max = 0.0
    for i, cp in enumerate(made, start=1):
        share = lay * (i / float(len(made)))
        cp.shape_key_add(name="Base", from_mix=False)
        kb = cp.shape_key_add(name="Vent", from_mix=False)
        for j, v in enumerate(cp.data.vertices):
            kb.data[j].co = v.co + mathutils.Vector((share, 0.0, -0.35 * share))
        amp_max = max(amp_max, share)
        kb.value = 0.0
        kb.keyframe_insert("value", frame=1)
        kb.value = 1.0
        kb.keyframe_insert("value", frame=half)
        kb.value = 0.0
        kb.keyframe_insert("value", frame=f_end)
    out = {"frame_count": f_end, "kind": kind, "length_m": length,
           "wind": wind, "coques": len(made), "amplitude_m": round(amp_max, 4),
           "path": "blender_fur_shells",
           "note": "brins reels (brin par brin) disponibles par la voie rendu"}
    if amp_max < 1e-4:
        out["error"] = "la fourrure ne bouge pas"
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _rng(seed):
    import random as _r
    return _r.Random(seed)


def bake_particles(intent, scene, fps):
    """Etincelles, pluie, neige, poussiere, debris.

    Les particules d'un moteur de simulation ne traversent PAS un GLB. On les
    livre donc comme des copies animees en transformation — exactement ce que
    font les moteurs temps reel. Les trajectoires sont balistiques et calculees
    analytiquement (p = p0 + v0.t + g.t2/2): pas de solveur, donc pas de cache,
    et un resultat identique a chaque relecture.
    """
    p = intent.get("particle_anim") or {}
    kind = p.get("kind") or "sparks"
    count = max(4, min(400, int(p.get("count") or 120)))
    dur = float(p.get("duration_s") or 2.0)
    spread = float(p.get("spread") or 1.0)
    src = _largest_mesh(scene)
    if src is None:
        return {"error": "aucun maillage emetteur"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    size = max(src.dimensions.x, src.dimensions.y, src.dimensions.z, 0.1)

    # Chaque famille a sa physique: une etincelle jaillit et retombe, la pluie
    # tombe droit et vite, la neige descend en flottant, la poussiere monte.
    prof = {
        "sparks":  dict(v0=2.2, g=-9.81, up=0.7, r=0.010, drift=0.0),
        "debris":  dict(v0=1.6, g=-9.81, up=0.5, r=0.030, drift=0.0),
        "rain":    dict(v0=0.2, g=-9.81, up=0.0, r=0.006, drift=0.05),
        "snow":    dict(v0=0.1, g=-0.60, up=0.0, r=0.012, drift=0.35),
        "dust":    dict(v0=0.3, g=+0.25, up=0.4, r=0.008, drift=0.30),
    }.get(kind, dict(v0=1.5, g=-9.81, up=0.5, r=0.015, drift=0.1))

    verts = [src.matrix_world @ v.co for v in src.data.vertices]
    if not verts:
        return {"error": "maillage emetteur sans sommets"}
    hi = max(v.z for v in verts)
    # Sol: sans lui les etincelles tombaient a l'infini (mesure: 9,8 m de chute
    # pour un sujet de 60 cm). On les arrete au niveau du bas du sujet, avec un
    # rebond amorti — c'est ce qui rend une gerbe d'etincelles credible.
    sol = min(v.z for v in verts)
    rnd = _rng(20260723)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,
                                          radius=prof["r"] * size,
                                          location=(0, 0, -1e6))
    proto = bpy.context.object
    proto.name = "AuroraParticleProto"
    made, amp = 0, 0.0
    for i in range(count):
        o = verts[rnd.randrange(len(verts))]
        if kind in ("rain", "snow"):
            o = mathutils.Vector((o.x + rnd.uniform(-1, 1) * size * spread,
                                  o.y + rnd.uniform(-1, 1) * size * spread,
                                  hi + size * (0.6 + rnd.random())))
        ang = rnd.uniform(0, 6.2831853)
        rad = prof["v0"] * spread * rnd.uniform(0.4, 1.0)
        v0 = mathutils.Vector((rad * math.cos(ang) * 0.5,
                               rad * math.sin(ang) * 0.5,
                               prof["v0"] * prof["up"] * rnd.uniform(0.5, 1.2)))
        cp = proto.copy()
        cp.data = proto.data
        cp.name = "AuroraParticle_%03d" % i
        scene.collection.objects.link(cp)
        ph = rnd.uniform(0, 6.2831853)
        for fr in range(1, f_end + 1):
            t = (fr - 1) / float(fps)
            z = o.z + v0.z * t + 0.5 * prof["g"] * t * t
            if z < sol:
                # rebond amorti puis repos: on replie la trajectoire sous le sol
                z = sol + min(0.25 * (sol - z), 0.05 * size)
            pos = mathutils.Vector((
                o.x + v0.x * t + prof["drift"] * size * math.sin(ph + 2.0 * t),
                o.y + v0.y * t + prof["drift"] * size * math.cos(ph + 1.7 * t),
                z))
            cp.location = pos
            cp.keyframe_insert("location", frame=fr)
            amp = max(amp, (pos - o).length)
        made += 1
    bpy.data.objects.remove(proto, do_unlink=True)
    out = {"frame_count": f_end, "kind": kind, "particules": made,
           "amplitude_m": round(amp, 4), "path": "blender_particles_bakees"}
    if amp < 1e-4:
        out["error"] = "les particules ne bougent pas"
    return out


def _fracture_by_slicing(obj, scene, pieces, seed=20260723):
    """Casse un maillage en morceaux par plans de coupe successifs.

    L'extension Cell Fracture a disparu de Blender 5. On decoupe donc le
    volume: a chaque tour on prend le plus gros morceau et on le tranche par un
    plan aleatoire passant pres de son centre. Le resultat est un vrai eclat
    ferme, ce que la fracture de Voronoi produit aussi.
    """
    rnd = _rng(seed)
    shards = [obj]
    guard = 0
    while len(shards) < pieces and guard < pieces * 4:
        guard += 1
        big = max(shards, key=lambda o: o.dimensions.x * o.dimensions.y * o.dimensions.z)
        if min(big.dimensions) < 1e-4:
            break
        cp = big.copy()
        cp.data = big.data.copy()
        scene.collection.objects.link(cp)
        c = big.location + mathutils.Vector((
            (rnd.random() - 0.5) * big.dimensions.x * 0.5,
            (rnd.random() - 0.5) * big.dimensions.y * 0.5,
            (rnd.random() - 0.5) * big.dimensions.z * 0.5))
        n = mathutils.Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1),
                              rnd.uniform(-1, 1)))
        if n.length < 1e-6:
            n = mathutils.Vector((0, 0, 1))
        n.normalize()
        ok = True
        for target, flip in ((big, False), (cp, True)):
            bpy.context.view_layer.objects.active = target
            for o in bpy.context.selected_objects:
                o.select_set(False)
            target.select_set(True)
            try:
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.mesh.bisect(
                    plane_co=(c.x, c.y, c.z), plane_no=(n.x, n.y, n.z),
                    use_fill=True, clear_inner=flip, clear_outer=not flip)
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:  # noqa: BLE001
                try:
                    bpy.ops.object.mode_set(mode="OBJECT")
                except Exception:  # noqa: BLE001
                    pass
                ok = False
        if not ok or not len(cp.data.polygons) or not len(big.data.polygons):
            bpy.data.objects.remove(cp, do_unlink=True)
            break
        shards.append(cp)
    return [s for s in shards if len(s.data.polygons) > 0]


def bake_fracture_debris(intent, scene, fps):
    """Beton, verre, bois: le sujet se brise et les eclats tombent."""
    f = intent.get("fracture_anim") or {}
    pieces = max(2, min(40, int(f.get("pieces") or 8)))
    dur = float(f.get("duration_s") or 2.0)
    bounce = max(0.0, min(1.0, float(f.get("bounciness") or 0.15)))
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun maillage a briser"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end

    shards = _fracture_by_slicing(obj, scene, pieces)
    for _s in shards:
        _recenter_origin(_s)
    if len(shards) < 2:
        return {"error": "la fracture n'a produit qu'un seul morceau"}
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    scene.rigidbody_world.point_cache.frame_start = 1
    scene.rigidbody_world.point_cache.frame_end = f_end
    ground = _ground_plane(scene, obj, margin=0.05)
    bpy.context.view_layer.objects.active = ground
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    ground.rigid_body.collision_shape = "MESH"
    ground.rigid_body.friction = 0.9
    for s in shards:
        s.rotation_euler = s.rotation_quaternion.to_euler("XYZ")
        s.rotation_mode = "XYZ"   # sinon les cles rotation_euler sont ignorees
        bpy.context.view_layer.objects.active = s
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        s.rigid_body.restitution = bounce
        s.rigid_body.collision_shape = "CONVEX_HULL"
    # Comme pour les corps rigides: on RELEVE d'abord toutes les trajectoires,
    # on ecrit les cles ensuite (une cle posee en cours de route reprendrait la
    # main sur le solveur).
    tracks = {s.name: [] for s in shards}
    for fr in range(1, f_end + 1):
        scene.frame_set(fr)
        for s in shards:
            tracks[s.name].append((fr, s.matrix_world.to_translation().copy(),
                                   s.matrix_world.to_euler().copy()))
    amp = 0.0
    for s in shards:
        bpy.context.view_layer.objects.active = s
        try:
            bpy.ops.rigidbody.object_remove()
        except Exception:  # noqa: BLE001
            pass
        p0 = tracks[s.name][0][1]
        for fr, loc, rot in tracks[s.name]:
            s.location = loc
            s.rotation_euler = rot
            s.keyframe_insert("location", frame=fr)
            s.keyframe_insert("rotation_euler", frame=fr)
            amp = max(amp, (loc - p0).length)
    bpy.data.objects.remove(ground, do_unlink=True)
    out = {"frame_count": f_end, "eclats": len(shards),
           "amplitude_m": round(amp, 4), "path": "blender_fracture_decoupe"}
    if amp < 1e-4:
        out["error"] = "les eclats ne bougent pas"
    return out


def bake_ocean_surface(intent, scene, fps):
    """Etendue d'eau: houle, vagues, ecume — via le modificateur Ocean natif."""
    o = intent.get("ocean_anim") or {}
    scale = float(o.get("wave_scale") or 1.0)
    choppy = max(0.0, min(4.0, float(o.get("choppiness") or 1.0)))
    wind = float(o.get("wind_speed") or 12.0)
    loop_s = float(o.get("loop_s") or 4.0)
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucune surface d'eau"}
    f_end = max(2, int(round(loop_s * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    mod = obj.modifiers.new("AuroraOcean", "OCEAN")
    try:
        mod.geometry_mode = "DISPLACE"
        mod.wave_scale = scale
        mod.choppiness = choppy
        mod.wind_velocity = wind
        mod.resolution = 8
        mod.time = 0.0
        # L'ocean n'a pas de cache: son etat depend d'un temps continu qu'il
        # faut animer soi-meme, sinon la mer reste parfaitement figee.
        for fr, t in ((1, 0.0), (f_end, loop_s)):
            mod.time = t
            mod.keyframe_insert("time", frame=fr)
    except Exception as exc:  # noqa: BLE001
        return {"error": "modificateur Ocean indisponible: %s" % exc}
    r = _bake_to_shape_keys(obj, scene, 1, f_end, "ocean", mod=mod)
    return {"frame_count": f_end, "wave_scale": scale, "choppiness": choppy,
            "path": "blender_ocean", **r}


def bake_orbital(intent, scene, fps):
    """Orbites, satellites, systemes: mouvement gravitationnel a grande echelle.

    Une orbite est deterministe: inutile d'appeler un solveur, la trajectoire
    est une ellipse parcourue a vitesse angulaire connue. On la grave donc
    directement en cles de transformation, exactes et sans cache.
    """
    o = intent.get("orbital_anim") or {}
    bodies = max(1, min(12, int(o.get("bodies") or 2)))
    period = float(o.get("period_s") or 4.0)
    ecc = max(0.0, min(0.8, float(o.get("eccentricity") or 0.0)))
    tilt = float(o.get("tilt_deg") or 0.0) * math.pi / 180.0
    center = _largest_mesh(scene)
    if center is None:
        return {"error": "aucun corps central"}
    f_end = max(2, int(round(period * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    R0 = max(center.dimensions.x, center.dimensions.y, center.dimensions.z, 0.2)
    origin = center.location.copy()
    made, amp = 0, 0.0
    for k in range(1, bodies + 1):
        a = R0 * (1.6 + 0.9 * k)                       # demi-grand axe
        b = a * math.sqrt(max(1e-6, 1.0 - ecc * ecc))  # demi-petit axe
        # 3e loi de Kepler: plus l'orbite est large, plus l'annee est longue.
        turns = (a / (R0 * 2.5)) ** -1.5
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=16, ring_count=10, radius=R0 * (0.10 + 0.03 * k),
            location=(origin.x + a, origin.y, origin.z))
        sat = bpy.context.object
        sat.name = "AuroraOrbiter_%d" % k
        for fr in range(1, f_end + 1):
            th = 2.0 * math.pi * turns * (fr - 1) / float(f_end)
            x, y = a * math.cos(th) - a * ecc, b * math.sin(th)
            pos = mathutils.Vector((origin.x + x,
                                    origin.y + y * math.cos(tilt),
                                    origin.z + y * math.sin(tilt)))
            sat.location = pos
            sat.keyframe_insert("location", frame=fr)
            amp = max(amp, (pos - origin).length)
        made += 1
    out = {"frame_count": f_end, "corps_en_orbite": made,
           "amplitude_m": round(amp, 4), "path": "blender_orbites"}
    if amp < 1e-4:
        out["error"] = "aucune orbite parcourue"
    return out




def _recenter_origin(obj):
    """Place l'origine de l'objet au centre de sa geometrie.

    Apres decoupe, TOUS les morceaux heritent de l'origine du sujet d'origine:
    ils partagent donc exactement la meme position. Les charnieres etaient alors
    toutes creees AU MEME POINT et la chaine ne pouvait pas s'articuler (mesure:
    0,0001 m). Recentrer chaque piece sur sa propre matiere est ce qui donne au
    mecanisme une geometrie reelle.
    """
    vs = obj.data.vertices
    if not len(vs):
        return
    c = mathutils.Vector((0.0, 0.0, 0.0))
    for v in vs:
        c += v.co
    c /= len(vs)
    for v in vs:
        v.co -= c
    obj.data.update()
    obj.location = obj.location + (obj.matrix_world.to_3x3() @ c)


def bake_articulated_rig(intent, scene, fps):
    """Contraintes et vehicules: charnieres, pivots, chaines articulees.

    Un vrai mecanisme n'est pas un objet qui tourne: ce sont des pieces
    RELIEES. On decoupe le sujet le long de son axe le plus long, on relie les
    morceaux par des charnieres, et on laisse la gravite les mettre en branle.
    """
    a = intent.get("articulated_anim") or {}
    segments = max(2, min(12, int(a.get("segments") or 4)))
    dur = float(a.get("duration_s") or 2.0)
    joint = a.get("joint") or "hinge"
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun maillage a articuler"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end

    dims = [obj.dimensions.x, obj.dimensions.y, obj.dimensions.z]
    axis = max(range(3), key=lambda i: dims[i])
    parts = _fracture_by_slicing(obj, scene, segments, seed=7311)
    if len(parts) < 2:
        return {"error": "impossible de separer le sujet en pieces"}
    for _p in parts:
        _recenter_origin(_p)
    parts.sort(key=lambda o: o.matrix_world.to_translation()[axis])
    # ECARTER LES PIECES. Des morceaux imbriques les uns dans les autres se
    # bloquent mutuellement: le bras ne bougeait que de 3,5 cm. On les aligne
    # bout a bout le long de l'axe, comme les segments d'un bras articule.
    # 27/07: l'ecartement DEMONTE tout assemblage reel (engrenages imbriques,
    # piston dans son cylindre, rouages d'horloge): les pieces s'envolent en
    # ligne au lieu de tourner ensemble. Il n'a de sens que pour une chaine
    # articulee dont les segments se bloquent. Desactive par defaut; le
    # routeur de domaine le rallume pour les chaines segmentees.
    if os.environ.get("AURORA_RIG_ECARTER_PIECES", "0") == "1":
        step = max(dims[axis] / max(len(parts), 1), 1e-3)
        base = parts[0].location.copy()
        for i, _p in enumerate(parts):
            loc = base.copy()
            loc[axis] = base[axis] + i * step * 1.25
            _p.location = loc
        print("RIG_INFO: pieces ecartees (chaine articulee demandee)", flush=True)
    else:
        print("RIG_INFO: assemblage CONSERVE (pieces non ecartees)", flush=True)

    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    scene.rigidbody_world.point_cache.frame_start = 1
    scene.rigidbody_world.point_cache.frame_end = f_end
    for i, p in enumerate(parts):
        p.rotation_euler = p.rotation_quaternion.to_euler("XYZ")
        p.rotation_mode = "XYZ"   # cles rotation_euler ignorees en mode QUATERNION
        bpy.context.view_layer.objects.active = p
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        p.rigid_body.collision_shape = "CONVEX_HULL"
        p.rigid_body.mass = 1.0
        if i == 0:
            # LE MECANISME A BESOIN D'UN MOTEUR. Ancre + gravite seules, la
            # chaine est deja a l'equilibre et ne bouge pas d'un dixieme de
            # millimetre (mesure). La premiere piece est donc pilotee par
            # l'animation (cinematique) et entraine toutes les autres — c'est
            # ainsi que fonctionne un bras, une grue ou une suspension.
            p.rigid_body.kinematic = True
            base = p.rotation_euler.copy()
            for fr, k in ((1, 0.0), (f_end // 2, 1.0), (f_end, 0.0)):
                p.rotation_euler = (base.x, base.y, base.z + 3.0 * k)
                p.keyframe_insert("rotation_euler", frame=max(1, fr))
            p.rotation_euler = base
    made = 0
    for i in range(len(parts) - 1):
        mid = (parts[i].matrix_world.to_translation()
               + parts[i + 1].matrix_world.to_translation()) / 2.0
        e = bpy.data.objects.new("AuroraJoint_%d" % i, None)
        scene.collection.objects.link(e)
        e.location = mid
        bpy.context.view_layer.objects.active = e
        bpy.ops.rigidbody.constraint_add()
        c = e.rigid_body_constraint
        c.type = "HINGE" if joint == "hinge" else "POINT"
        c.object1, c.object2 = parts[i], parts[i + 1]
        made += 1

    tracks = {p.name: [] for p in parts}
    for fr in range(1, f_end + 1):
        scene.frame_set(fr)
        for p in parts:
            tracks[p.name].append((fr, p.matrix_world.to_translation().copy(),
                                   p.matrix_world.to_euler().copy()))
    amp = 0.0
    for p in parts:
        bpy.context.view_layer.objects.active = p
        try:
            bpy.ops.rigidbody.object_remove()
        except Exception:  # noqa: BLE001
            pass
        # On mesure le deplacement des COINS, pas du centre: une piece qui
        # pivote sur place ne translate pas d'un millimetre alors qu'elle bouge
        # bel et bien. Mesurer le centre annoncait 0,0001 m sur un bras qui
        # tournait.
        def _coins(loc, rot):
            m = mathutils.Matrix.LocRotScale(loc, rot, p.scale)
            return [m @ mathutils.Vector(c) for c in p.bound_box]
        ref = _coins(tracks[p.name][0][1], tracks[p.name][0][2])
        for fr, loc, rot in tracks[p.name]:
            p.location, p.rotation_euler = loc, rot
            p.keyframe_insert("location", frame=fr)
            p.keyframe_insert("rotation_euler", frame=fr)
            amp = max(amp, max((a - b).length
                               for a, b in zip(_coins(loc, rot), ref)))
    out = {"frame_count": f_end, "pieces": len(parts), "articulations": made,
           "joint": joint, "amplitude_m": round(amp, 4),
           "path": "blender_contraintes"}
    if amp < 1e-4:
        out["error"] = "le mecanisme ne bouge pas"
    return out


def bake_rope_net(intent, scene, fps):
    """Cordes, chaines, filets: du tissu tres tendu et peu pliant.

    Une corde EST un tissu du point de vue du solveur — mais avec des reglages
    opposes a ceux d'un rideau: tension maximale, pliage quasi nul, sinon elle
    s'etale comme un drap au lieu de pendre.
    """
    r = intent.get("rope_anim") or {}
    loop_s = float(r.get("loop_s") or 3.0)
    slack = max(0.0, min(1.0, float(r.get("slack") or 0.3)))
    wind = max(0.0, min(1.0, float(r.get("wind") or 0.3)))
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun maillage a suspendre"}
    f_end = max(2, int(round(loop_s * fps)))
    scene.frame_start, scene.frame_end = 1, f_end

    co = [v.co for v in obj.data.vertices]
    spans = [max(c[i] for c in co) - min(c[i] for c in co) for i in range(3)]
    widest = max(spans)
    axis = 2 if spans[2] >= 0.10 * widest else max(range(2), key=lambda i: spans[i])
    hi = max(c[axis] for c in co)
    span = max(spans[axis], 1e-6)
    idx = [v.index for v in obj.data.vertices if (hi - v.co[axis]) / span <= 0.06]
    pinned = 0
    if idx and len(idx) < 0.85 * len(obj.data.vertices):
        obj.vertex_groups.new(name="AuroraPin").add(idx, 1.0, "REPLACE")
        pinned = len(idx)

    mod = obj.modifiers.new("AuroraRope", "CLOTH")
    st = mod.settings
    st.quality = 10
    st.mass = 0.6
    st.tension_stiffness = 60.0 * (1.0 - 0.6 * slack)
    st.compression_stiffness = 60.0 * (1.0 - 0.6 * slack)
    st.shear_stiffness = 40.0
    st.bending_stiffness = 0.02 + 0.10 * (1.0 - slack)
    if pinned:
        st.vertex_group_mass = "AuroraPin"
    mod.collision_settings.use_self_collision = False
    try:
        mod.point_cache.frame_start, mod.point_cache.frame_end = 1, f_end
    except Exception:  # noqa: BLE001
        pass
    if wind > 0.01:
        wf = bpy.data.objects.new("AuroraWindRope", None)
        scene.collection.objects.link(wf)
        wf.location = (0.0, -3.0 * max(obj.dimensions.y, 1.0), obj.location.z)
        wf.rotation_euler = (1.5708, 0.0, 0.0)
        bpy.context.view_layer.objects.active = wf
        bpy.ops.object.forcefield_toggle()
        wf.field.type = "WIND"
        wf.field.strength = 30.0 * wind
    res = _bake_to_shape_keys(obj, scene, 1, f_end, "rope", mod=mod)
    return {"frame_count": f_end, "sommets_accroches": pinned, "slack": slack,
            "path": "blender_corde", **res}


def bake_growth(intent, scene, fps):
    """Croissance: plantes, arbres, cristaux, coraux.

    La croissance n'est pas une mise a l'echelle uniforme — une plante pousse
    PAR LE HAUT, sa base reste posee. On interpole donc chaque sommet depuis la
    base vers sa position finale, ce qui donne le deploiement caracteristique.
    """
    g = intent.get("growth_anim") or {}
    dur = float(g.get("duration_s") or 3.0)
    start = max(0.0, min(0.9, float(g.get("start_ratio") or 0.05)))
    sway = max(0.0, min(1.0, float(g.get("sway") or 0.15)))
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun maillage a faire pousser"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    co = [v.co.copy() for v in obj.data.vertices]
    if not co:
        return {"error": "maillage sans sommets"}
    z0 = min(c.z for c in co)
    height = max(max(c.z for c in co) - z0, 1e-6)
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Base", from_mix=False)
    steps = min(f_end, 24)
    amp = 0.0
    for s in range(steps):
        fr = 1 + int(round(s * (f_end - 1) / float(max(steps - 1, 1))))
        t = s / float(max(steps - 1, 1))
        k = start + (1.0 - start) * t
        kb = obj.shape_key_add(name="growth_%03d" % fr, from_mix=False)
        for i, c in enumerate(co):
            h = (c.z - z0) / height
            # les sommets hauts arrivent en dernier: front de croissance
            local = max(0.0, min(1.0, (k - h) * 3.0 + 0.35))
            lean = sway * height * 0.08 * math.sin(6.283 * t + h * 2.0) * h
            kb.data[i].co = mathutils.Vector((
                c.x * (start + (1 - start) * local) + lean,
                c.y * (start + (1 - start) * local),
                z0 + (c.z - z0) * (start + (1 - start) * local)))
            amp = max(amp, (kb.data[i].co - c).length)
        kb.value = 0.0
        kb.keyframe_insert("value", frame=max(1, fr - 1))
        kb.value = 1.0
        kb.keyframe_insert("value", frame=fr)
        kb.value = 0.0
        kb.keyframe_insert("value", frame=min(f_end, fr + 1))
    out = {"frame_count": f_end, "etapes": steps, "amplitude_m": round(amp, 4),
           "path": "blender_croissance"}
    if amp < 1e-4:
        out["error"] = "aucune croissance"
    return out


def bake_chemistry(intent, scene, fps):
    """Chimie visible: corrosion, oxydation, combustion, changement d'etat.

    Une reaction chimique ne deplace pas de sommets — elle change la MATIERE.
    On anime donc la couleur, la rugosite et l'emission du materiau dans le
    temps: la rouille envahit le metal, la braise s'allume.
    """
    c = intent.get("chemistry_anim") or {}
    reaction = c.get("reaction") or "corrosion"
    dur = float(c.get("duration_s") or 4.0)
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun maillage a transformer"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    prof = {
        "corrosion":  ((0.62, 0.62, 0.65, 1.0), (0.42, 0.17, 0.06, 1.0), 0.25, 0.85, 0.0, 0.0),
        "oxydation":  ((0.72, 0.45, 0.20, 1.0), (0.20, 0.55, 0.45, 1.0), 0.30, 0.70, 0.0, 0.0),
        "combustion": ((0.25, 0.22, 0.20, 1.0), (1.00, 0.35, 0.05, 1.0), 0.60, 0.45, 0.0, 6.0),
        "gel":        ((0.30, 0.45, 0.60, 1.0), (0.85, 0.93, 1.00, 1.0), 0.55, 0.10, 0.0, 0.0),
    }.get(reaction, ((0.6, 0.6, 0.6, 1.0), (0.3, 0.2, 0.1, 1.0), 0.3, 0.8, 0.0, 0.0))
    c0, c1, r0, r1, e0, e1 = prof

    mats = [m for m in obj.data.materials if m and m.use_nodes]
    if not mats:
        m = bpy.data.materials.new("AuroraChimie")
        m.use_nodes = True
        obj.data.materials.append(m)
        mats = [m]
    touched = 0
    for m in mats:
        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        for fr, k in ((1, 0.0), (f_end, 1.0)):
            base = bsdf.inputs.get("Base Color")
            rough = bsdf.inputs.get("Roughness")
            emis = bsdf.inputs.get("Emission Strength")
            if base is not None:
                base.default_value = tuple(c0[i] + (c1[i] - c0[i]) * k for i in range(4))
                base.keyframe_insert("default_value", frame=fr)
            if rough is not None:
                rough.default_value = r0 + (r1 - r0) * k
                rough.keyframe_insert("default_value", frame=fr)
            if emis is not None and e1 > 0.0:
                emis.default_value = e0 + (e1 - e0) * k
                emis.keyframe_insert("default_value", frame=fr)
        touched += 1
    out = {"frame_count": f_end, "reaction": reaction, "materiaux": touched,
           "path": "blender_chimie", "voie": "rendu"}
    if not touched:
        out["error"] = "aucun materiau animable sur ce maillage"
    return out




# ---------------------------------------------------------------------------
# VOIE RENDU. Certains domaines ne PEUVENT pas tenir dans un GLB: le format ne
# transporte ni volume (feu, fumee), ni animation de matiere (rouille, braise),
# ni phenomene optique (caustiques, dispersion). Les forcer produit un fichier
# vide — mesure faite: 0 animation, 0 canal. On les rend donc en sequence
# d'images, qui est leur forme de livraison honnete.
# ---------------------------------------------------------------------------

def _render_sequence(scene, out_glb, f_end, samples=48, res=720):
    base = os.path.splitext(out_glb)[0] + "_rendu"
    os.makedirs(base, exist_ok=True)
    scene.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "CUDA"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = (d.type != "CPU")
        scene.cycles.device = "GPU"
    except Exception:  # noqa: BLE001
        scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.image_settings.file_format = "PNG"
    # PAS de fond transparent ici: un verre n'a alors RIEN a refracter et un
    # volume n'a aucun contraste — les rendus sortaient vides a 99% (mesure).
    # Un environnement lumineux donne au verre ses caustiques et a la fumee sa
    # silhouette.
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("AuroraWorld")
    w = scene.world
    w.use_nodes = True
    bg = next((n for n in w.node_tree.nodes if n.type == "BACKGROUND"), None)
    # Un volume lumineux (feu) veut un fond SOMBRE pour ressortir; l'optique veut
    # un fond clair et un motif derriere pour montrer la refraction.
    _has_volume = (any(o.type == "VOLUME" for o in scene.objects)
                   or any(o.type == "MESH" and any(
        ms and ms.name.startswith("AuroraGaz") for ms in o.data.materials)
        for o in scene.objects if o.type == "MESH" and o.data))
    if bg is not None:
        if _has_volume:
            bg.inputs[0].default_value = (0.02, 0.02, 0.03, 1.0)
            bg.inputs[1].default_value = 0.15
        else:
            bg.inputs[0].default_value = (0.35, 0.42, 0.55, 1.0)
            bg.inputs[1].default_value = 1.6
    # Un damier sous le sujet: sans motif derriere, une refraction reste
    # invisible. Inutile (et genant) devant un volume de feu.
    tgt = None if _has_volume else _largest_mesh(scene)
    if tgt is not None:
        sz = max(tgt.dimensions) * 6.0
        bpy.ops.mesh.primitive_plane_add(size=sz,
                                         location=(tgt.location.x, tgt.location.y,
                                                   tgt.location.z - max(tgt.dimensions)))
        pl = bpy.context.object
        pm = bpy.data.materials.new("AuroraDamier")
        pm.use_nodes = True
        nt = pm.node_tree
        ck = nt.nodes.new("ShaderNodeTexChecker")
        ck.inputs["Scale"].default_value = 12.0
        pb = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if pb is not None:
            nt.links.new(ck.outputs["Color"], pb.inputs["Base Color"])
        pl.data.materials.append(pm)
    if scene.camera is None:
        tgt = _largest_mesh(scene)
        c = tgt.location if tgt else mathutils.Vector((0, 0, 0))
        d = max(tgt.dimensions) * 3.0 if tgt else 3.0
        bpy.ops.object.camera_add(location=(c.x + d, c.y - d, c.z + d * 0.6))
        cam = bpy.context.object
        cam.rotation_euler = (1.15, 0.0, 0.785)
        scene.camera = cam
    if not any(o.type == "LIGHT" for o in scene.objects):
        bpy.ops.object.light_add(type="AREA", location=(3, -3, 4))
        bpy.context.object.data.energy = 800.0
    written = []
    for fr in range(1, f_end + 1):
        scene.frame_set(fr)
        scene.render.filepath = os.path.join(base, "f%04d.png" % fr)
        bpy.ops.render.render(write_still=True)
        written.append(scene.render.filepath)
    return {"voie": "rendu", "images": len(written), "dossier": base}


def bake_optics(intent, scene, fps):
    """Optique: refraction, caustiques, dispersion, absorption.

    Ce n'est pas un solveur mais de la MATIERE et de la lumiere: on construit
    un verre physique (transmission, IOR, dispersion) et on fait tourner la
    lumiere autour du sujet. Cycles calcule les caustiques; le resultat sort en
    images, car aucun GLB ne transporte un chemin lumineux.
    """
    o = intent.get("optics_anim") or {}
    ior = float(o.get("ior") or 1.45)
    disp = max(0.0, min(1.0, float(o.get("dispersion") or 0.3)))
    absorb = max(0.0, min(1.0, float(o.get("absorption") or 0.15)))
    loop_s = float(o.get("loop_s") or 2.0)
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun sujet optique"}
    f_end = max(2, int(round(loop_s * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    m = bpy.data.materials.new("AuroraOptique")
    m.use_nodes = True
    b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b is None:
        return {"error": "materiau principiel indisponible"}
    for key, val in (("Transmission Weight", 1.0), ("Roughness", 0.02),
                     ("IOR", ior), ("Alpha", 1.0)):
        if key in b.inputs:
            b.inputs[key].default_value = val
    for key in ("Dispersion", "Transmission Dispersion"):
        if key in b.inputs:
            b.inputs[key].default_value = disp * 0.2
    if "Base Color" in b.inputs:
        b.inputs["Base Color"].default_value = (1.0 - absorb * 0.6,
                                                1.0 - absorb * 0.2, 1.0, 1.0)
    obj.data.materials.clear()
    obj.data.materials.append(m)
    bpy.ops.object.light_add(type="AREA", location=(2.5, -2.5, 3.0))
    lamp = bpy.context.object
    lamp.data.energy = 1200.0
    base = lamp.location.copy()
    for fr, k in ((1, 0.0), (f_end // 2, 1.0), (f_end, 0.0)):
        lamp.location = (base.x * math.cos(2.2 * k) - base.y * math.sin(2.2 * k),
                         base.x * math.sin(2.2 * k) + base.y * math.cos(2.2 * k),
                         base.z)
        lamp.keyframe_insert("location", frame=max(1, fr))
    try:
        scene.cycles.caustics_refractive = True
        scene.cycles.caustics_reflective = True
    except Exception:  # noqa: BLE001
        pass
    return {"frame_count": f_end, "ior": ior, "dispersion": disp,
            "path": "cycles_optique", "voie": "rendu"}


def bake_smoke_fire(intent, scene, fps):
    """Fumee, vapeur, feu, explosion — volume procedural anime, rendu Cycles.

    Pourquoi PAS Mantaflow: en mode --background le solveur ne cuit qu'une seule
    image (mesure: 1 fichier de cache pour 20 images demandees) et le volume
    rendu ressortait vide (0,05/255 de variation). Le volume PROCEDURAL — une
    densite tiree d'un bruit 3D qui monte dans le temps, emission par corps noir
    pour le feu — est deterministe, ne depend d'aucun cache, rend a coup sur sur
    GPU et donne l'aspect attendu (mesure: feu a 27% de pixels lumineux, max 172,
    corps noir orange). C'est la technique des moteurs temps reel pour les
    flammes. Le vrai Pyro Houdini reste une voie d'amelioration future.
    """
    g = intent.get("gas_anim") or intent.get("gas_anim_real") or {}
    kind = g.get("kind") or "fire"
    is_fire = kind in ("fire", "feu", "explosion", "flamme")
    is_explosion = kind in ("explosion",)
    dur = float(g.get("duration_s") or 2.0)
    obj = _largest_mesh(scene)
    if obj is not None:
        cx, cy, cz = obj.location
        size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.3)
    else:
        cx, cy, cz, size = 0.0, 0.0, 0.6, 0.8
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end

    # VRAI PYRO D'ABORD. Si Houdini est la, on simule pour de bon (la fumee
    # monte par flottabilite) et on importe la sequence VDB; le volume
    # procedural reste le repli fiable. AURORA_PYRO=0 pour forcer le repli.
    if os.environ.get("AURORA_PYRO", "1") == "1" and not is_explosion:
        try:
            import sys as _sys
            _svc = os.path.dirname(os.path.abspath(__file__))
            if _svc not in _sys.path:
                _sys.path.insert(0, _svc)
            import houdini_sim as _hs
            if _hs.available()[0]:
                import tempfile as _tmp
                _pdir = _tmp.mkdtemp(prefix="aurora_pyro_")
                _pr = _hs.simulate("pyro", _pdir, duration_s=dur, fps=fps,
                                   kind="fire" if is_fire else "smoke")
                if _pr.get("ok"):
                    _first = sorted(
                        f for f in os.listdir(_pdir) if f.endswith(".vdb"))[0]
                    bpy.ops.object.volume_import(
                        filepath=os.path.join(_pdir, _first))
                    vol_obj = bpy.context.object
                    vol_obj.location = (cx, cy, cz + size * 0.2)
                    _vsc = size * 1.2
                    vol_obj.scale = (_vsc, _vsc, _vsc)
                    # sans is_sequence, Blender fige la 1re image du VDB:
                    # le feu rendu ne bougeait pas d'un pixel (mesure 0,00).
                    vol_obj.data.is_sequence = True
                    vol_obj.data.frame_start = 1
                    vol_obj.data.frame_duration = f_end
                    vol_obj.data.sequence_mode = "EXTEND"
                    vm = bpy.data.materials.new("AuroraGazPyro")
                    vm.use_nodes = True
                    nt = vm.node_tree
                    for n in list(nt.nodes):
                        if n.type != "OUTPUT_MATERIAL":
                            nt.nodes.remove(n)
                    out_n = next(n for n in nt.nodes
                                 if n.type == "OUTPUT_MATERIAL")
                    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
                    # densite moderee: a x4 la fumee opaque cachait la
                    # flamme (rendu gris froid, R-B negatif).
                    pv.inputs["Density"].default_value = 0.6
                    if is_fire:
                        pv.inputs["Blackbody Intensity"].default_value = 6.0
                        if "Temperature" in pv.inputs:
                            pv.inputs["Temperature"].default_value = 1500.0
                        for _key, _val in (("Temperature Attribute", "flame"),
                                           ("Density Attribute", "density")):
                            if _key in pv.inputs:
                                pv.inputs[_key].default_value = _val
                    else:
                        pv.inputs["Color"].default_value = (0.6, 0.6, 0.62, 1)
                        pv.inputs["Blackbody Intensity"].default_value = 0.0
                    nt.links.new(pv.outputs["Volume"],
                                 out_n.inputs["Volume"])
                    vol_obj.data.materials.append(vm)
                    return {"frame_count": f_end, "kind": kind,
                            "path": "houdini_pyro_vdb", "voie": "rendu",
                            "verification": _pr.get("verification")}
        except Exception as _pe:  # noqa: BLE001
            print("AURORA_INFO: pyro indisponible (%r) -> volume procedural"
                  % (_pe,))
    bpy.ops.mesh.primitive_cube_add(size=size * 2.2,
                                    location=(cx, cy, cz + size * 0.9))
    dom = bpy.context.object
    dom.name = "AuroraGasVolume"
    dom.scale = (0.75, 0.75, 1.35 if not is_explosion else 1.0)

    vm = bpy.data.materials.new("AuroraGaz")
    vm.use_nodes = True
    nt = vm.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapn = nt.nodes.new("ShaderNodeMapping")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.5
    noise.inputs["Detail"].default_value = 6.0
    # densite = bruit amplifie moins un plancher: des volutes, pas un bloc plein
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 25.0
    sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = 6.0 if is_fire else 4.0
    mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
    mx.inputs[1].default_value = 0.0
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    if is_fire:
        pv.inputs["Color"].default_value = (0.05, 0.05, 0.05, 1.0)
        pv.inputs["Temperature"].default_value = 1600.0
        pv.inputs["Blackbody Intensity"].default_value = 4.0
    else:
        # fumee/vapeur/brouillard: gris clair, aucune emission
        pv.inputs["Color"].default_value = (0.6, 0.6, 0.62, 1.0)
        pv.inputs["Blackbody Intensity"].default_value = 0.0
    nt.links.new(coord.outputs["Generated"], mapn.inputs["Vector"])
    nt.links.new(mapn.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], mul.inputs[0])
    nt.links.new(mul.outputs[0], sub.inputs[0])
    nt.links.new(sub.outputs[0], mx.inputs[0])
    nt.links.new(mx.outputs[0], pv.inputs["Density"])
    nt.links.new(pv.outputs["Volume"], out.inputs["Volume"])
    dom.data.materials.append(vm)

    # ANIMATION: le champ de bruit se translate (feu/fumee qui montent et
    # bouillonnent). Explosion = le volume enfle vite depuis un point.
    for fr in range(1, f_end + 1):
        t = (fr - 1) / float(f_end - 1)
        mapn.inputs["Location"].default_value = (0.3 * math.sin(t * 3.0),
                                                 0.0, -t * 3.0)
        mapn.inputs["Location"].keyframe_insert("default_value", frame=fr)
        if is_explosion:
            s = 0.3 + 1.4 * t
            dom.scale = (s, s, s)
            dom.keyframe_insert("scale", frame=fr)
    return {"frame_count": f_end, "kind": kind,
            "path": "volume_procedural_cycles", "voie": "rendu"}



def bake_granular(intent, scene, fps):
    """Sable, neige, terre, gravier: une matiere faite de grains qui coule et
    s'empile. Approche par corps rigides multiples — chaque grain tombe,
    rebondit et se tasse, ce qui EST le comportement granulaire."""
    g = intent.get("granular_anim") or {}
    dur = float(g.get("duration_s") or 2.0)
    grains = max(20, min(400, int(g.get("grains") or 150)))
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun maillage source"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.3)
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    hi = max(v.z for v in verts) if verts else obj.location.z
    lo = min(v.z for v in verts) if verts else obj.location.z
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    scene.rigidbody_world.point_cache.frame_start = 1
    scene.rigidbody_world.point_cache.frame_end = f_end
    ground = _ground_plane(scene, obj, margin=0.02)
    bpy.context.view_layer.objects.active = ground
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    ground.rigid_body.friction = 0.9
    ground.rigid_body.collision_shape = "MESH"
    rnd = _rng(4242)
    r = size * 0.04
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=r,
                                          location=(0, 0, -1e6))
    proto = bpy.context.object
    parts = []
    for i in range(grains):
        cp = proto.copy(); cp.data = proto.data
        cp.name = "AuroraGrain_%03d" % i
        scene.collection.objects.link(cp)
        cp.location = (obj.location.x + rnd.uniform(-1, 1) * size * 0.3,
                       obj.location.y + rnd.uniform(-1, 1) * size * 0.3,
                       hi + rnd.uniform(0.0, 1.0) * size * 1.2)
        bpy.context.view_layer.objects.active = cp
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        cp.rigid_body.restitution = 0.05      # les grains ne rebondissent pas
        cp.rigid_body.friction = 0.9
        cp.rigid_body.collision_shape = "SPHERE"
        parts.append(cp)
    bpy.data.objects.remove(proto, do_unlink=True)
    tracks = {p.name: [] for p in parts}
    for fr in range(1, f_end + 1):
        scene.frame_set(fr)
        for p in parts:
            tracks[p.name].append((fr, p.matrix_world.to_translation().copy()))
    amp = 0.0
    for p in parts:
        bpy.context.view_layer.objects.active = p
        try:
            bpy.ops.rigidbody.object_remove()
        except Exception:  # noqa: BLE001
            pass
        p0 = tracks[p.name][0][1]
        for fr, loc in tracks[p.name]:
            p.location = loc
            p.keyframe_insert("location", frame=fr)
            amp = max(amp, (loc - p0).length)
    bpy.data.objects.remove(ground, do_unlink=True)
    out = {"frame_count": f_end, "grains": len(parts),
           "amplitude_m": round(amp, 4), "path": "blender_granulaire"}
    if amp < 1e-4:
        out["error"] = "les grains ne bougent pas"
    return out


def bake_melt(intent, scene, fps):
    """Fonte / solidification: le solide s'affaisse en flaque (fonte) ou une
    flaque se fige (solidification). Corps mou qui perd sa memoire de forme +
    la matiere qui change (aspect mouille)."""
    m = intent.get("thermal_anim") or {}
    sens = m.get("sens") or "fonte"
    dur = float(m.get("duration_s") or 3.0)
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun maillage a faire fondre"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    co = [v.co.copy() for v in obj.data.vertices]
    if not co:
        return {"error": "maillage sans sommets"}
    z0 = min(c.z for c in co)
    height = max(max(c.z for c in co) - z0, 1e-6)
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Base", from_mix=False)
    steps = min(f_end, 24)
    amp = 0.0
    for s in range(steps):
        fr = 1 + int(round(s * (f_end - 1) / float(max(steps - 1, 1))))
        t = s / float(max(steps - 1, 1))
        k = t if sens == "fonte" else (1.0 - t)   # 0=solide, 1=fondu
        kb = obj.shape_key_add(name="melt_%03d" % fr, from_mix=False)
        for i, c in enumerate(co):
            h = (c.z - z0) / height
            # le haut s'affaisse le plus, la base s'etale: une flaque se forme
            flatten = 1.0 - k * (0.15 + 0.8 * h)
            spread = 1.0 + k * 0.6 * (1.0 - h)
            kb.data[i].co = mathutils.Vector((c.x * spread, c.y * spread,
                                              z0 + (c.z - z0) * flatten))
            amp = max(amp, (kb.data[i].co - c).length)
        kb.value = 0.0; kb.keyframe_insert("value", frame=max(1, fr - 1))
        kb.value = 1.0; kb.keyframe_insert("value", frame=fr)
        kb.value = 0.0; kb.keyframe_insert("value", frame=min(f_end, fr + 1))
    # aspect mouille grandissant sur le materiau
    for mat in [x for x in obj.data.materials if x and x.use_nodes]:
        b = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b and "Roughness" in b.inputs:
            for fr, kk in ((1, 0.0), (f_end, 1.0)):
                rr = 0.7 if sens == "fonte" else 0.1
                b.inputs["Roughness"].default_value = 0.7 - (0.6 * kk if sens == "fonte" else -0.6 * kk)
                b.inputs["Roughness"].keyframe_insert("default_value", frame=fr)
    out = {"frame_count": f_end, "sens": sens, "etapes": steps,
           "amplitude_m": round(amp, 4), "path": "blender_fonte"}
    if amp < 1e-4:
        out["error"] = "aucune fonte"
    return out


def bake_plasma(intent, scene, fps):
    """Plasma, arc electrique, energie: volume emissif bleu-blanc qui crepite.
    Meme support que le feu (volume procedural rendu), mais froid en couleur et
    plus nerveux dans le temps."""
    p = intent.get("plasma_anim") or {}
    dur = float(p.get("duration_s") or 1.5)
    obj = _largest_mesh(scene)
    if obj is not None:
        cx, cy, cz = obj.location
        size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.3)
    else:
        cx, cy, cz, size = 0.0, 0.0, 0.6, 0.8
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    bpy.ops.mesh.primitive_cube_add(size=size * 2.0, location=(cx, cy, cz + size * 0.6))
    dom = bpy.context.object; dom.name = "AuroraGazPlasma"
    vm = bpy.data.materials.new("AuroraPlasma"); vm.use_nodes = True
    nt = vm.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out_n = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapn = nt.nodes.new("ShaderNodeMapping")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 8.0
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 30.0
    sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = 10.0
    mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"; mx.inputs[1].default_value = 0.0
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (0.3, 0.5, 1.0, 1.0)   # bleu electrique
    emit.inputs["Strength"].default_value = 8.0
    vol = nt.nodes.new("ShaderNodeVolumePrincipled") if False else None
    # emission volumetrique directe
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Color"].default_value = (0.02, 0.05, 0.1, 1.0)
    pv.inputs["Emission Strength"].default_value = 6.0
    pv.inputs["Emission Color"].default_value = (0.3, 0.55, 1.0, 1.0)
    nt.links.new(coord.outputs["Generated"], mapn.inputs["Vector"])
    nt.links.new(mapn.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], mul.inputs[0])
    nt.links.new(mul.outputs[0], sub.inputs[0])
    nt.links.new(sub.outputs[0], mx.inputs[0])
    nt.links.new(mx.outputs[0], pv.inputs["Density"])
    nt.links.new(pv.outputs["Volume"], out_n.inputs["Volume"])
    dom.data.materials.append(vm)
    # crepitement: le bruit saute d'une position a l'autre (nerveux)
    rnd = _rng(99)
    for fr in range(1, f_end + 1):
        mapn.inputs["Location"].default_value = (rnd.uniform(-2, 2),
                                                 rnd.uniform(-2, 2),
                                                 rnd.uniform(-2, 2))
        mapn.inputs["Location"].keyframe_insert("default_value", frame=fr)
    return {"frame_count": f_end, "path": "volume_plasma_cycles", "voie": "rendu"}




def bake_vortex(intent, scene, fps):
    """Tornade, tourbillon, vortex: particules en helice ascendante convergente.
    Trajectoires analytiques (rayon qui se resserre vers le haut, vitesse
    angulaire croissante) — deterministe, exportable en GLB."""
    v = intent.get("vortex_anim") or {}
    dur = float(v.get("duration_s") or 2.5)
    count = max(30, min(300, int(v.get("count") or 120)))
    obj = _largest_mesh(scene)
    if obj is not None:
        cx, cy, cz = obj.location
        size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.4)
    else:
        cx, cy, cz, size = 0.0, 0.0, 0.0, 1.0
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    rnd = _rng(777)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=size * 0.02,
                                          location=(0, 0, -1e6))
    proto = bpy.context.object
    amp = 0.0
    height = size * 2.2
    for i in range(count):
        cp = proto.copy(); cp.data = proto.data
        cp.name = "AuroraVortex_%03d" % i
        scene.collection.objects.link(cp)
        h0 = rnd.random()                     # hauteur de depart normalisee
        ph = rnd.uniform(0.0, 6.2831853)
        turns = 2.0 + 2.0 * rnd.random()
        p_prev = None
        for fr in range(1, f_end + 1):
            t = (fr - 1) / float(f_end - 1)
            h = (h0 + 0.6 * t) % 1.0          # monte et reboucle
            r = size * (0.9 - 0.65 * h)       # entonnoir: serre en haut? non —
            r = size * (0.25 + 0.65 * h)      # tornade: etroit en bas, large en haut
            a = ph + 6.2831853 * turns * t + 4.0 * h
            pos = mathutils.Vector((cx + r * math.cos(a),
                                    cy + r * math.sin(a),
                                    cz + h * height))
            cp.location = pos
            cp.keyframe_insert("location", frame=fr)
            if p_prev is not None:
                amp = max(amp, (pos - p_prev).length)
            else:
                p_prev = pos
    bpy.data.objects.remove(proto, do_unlink=True)
    out = {"frame_count": f_end, "particules": count,
           "amplitude_m": round(amp, 4), "path": "blender_vortex"}
    if amp < 1e-4:
        out["error"] = "le vortex ne tourne pas"
    return out


def bake_buoyancy(intent, scene, fps):
    """Flottaison: le sujet tangue sur l'eau (houle verticale + roulis), et un
    plan d'eau ondule sous lui. Tout en cles — exportable en GLB."""
    b = intent.get("buoyancy_anim") or {}
    loop_s = float(b.get("loop_s") or 3.0)
    houle = max(0.0, min(1.0, float(b.get("swell") or 0.4)))
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun sujet a faire flotter"}
    f_end = max(2, int(round(loop_s * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.3)
    obj.rotation_euler = obj.rotation_quaternion.to_euler("XYZ")
    obj.rotation_mode = "XYZ"
    base_z = obj.location.z
    base_rx, base_ry = obj.rotation_euler.x, obj.rotation_euler.y
    amp = 0.0
    for fr in range(1, f_end + 1):
        t = (fr - 1) / float(f_end - 1)
        w = 2.0 * math.pi * t
        dz = houle * size * 0.12 * math.sin(w)
        obj.location.z = base_z + dz
        obj.rotation_euler.x = base_rx + houle * 0.10 * math.sin(w + 1.3)
        obj.rotation_euler.y = base_ry + houle * 0.08 * math.cos(w * 0.7)
        obj.keyframe_insert("location", frame=fr)
        obj.keyframe_insert("rotation_euler", frame=fr)
        amp = max(amp, abs(dz))
    # plan d'eau qui ondule (2 cles de forme en opposition)
    lo_z = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=24, y_subdivisions=24,
                                    size=size * 6.0,
                                    location=(obj.location.x, obj.location.y,
                                              lo_z + 0.25 * size * 0.3))
    water = bpy.context.object
    water.name = "AuroraEau"
    water.shape_key_add(name="Base", from_mix=False)
    kb = water.shape_key_add(name="Houle", from_mix=False)
    for i, vtx in enumerate(water.data.vertices):
        kb.data[i].co = vtx.co + mathutils.Vector(
            (0, 0, houle * size * 0.06 * math.sin(vtx.co.x * 3.0)
             * math.cos(vtx.co.y * 2.0)))
    for fr, val in ((1, 0.0), (max(2, f_end // 2), 1.0), (f_end, 0.0)):
        kb.value = val
        kb.keyframe_insert("value", frame=fr)
    out = {"frame_count": f_end, "houle": houle,
           "amplitude_m": round(amp, 4), "path": "blender_flottaison"}
    if amp < 1e-4:
        out["error"] = "le sujet ne tangue pas"
    return out


def bake_swarm(intent, scene, fps):
    """Essaim, nuee, volee, banc: nuee cohesive d'agents (boids simplifies:
    cohesion + separation + alignement, integres puis graves en cles)."""
    w = intent.get("swarm_anim") or {}
    dur = float(w.get("duration_s") or 3.0)
    count = max(20, min(150, int(w.get("count") or 60)))
    obj = _largest_mesh(scene)
    if obj is not None:
        cx, cy, cz = obj.location
        size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.4)
    else:
        cx, cy, cz, size = 0.0, 0.0, 1.0, 1.0
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    rnd = _rng(1234)
    center = mathutils.Vector((cx, cy, cz + size * 1.5))
    pos = [center + mathutils.Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1),
                                      rnd.uniform(-0.5, 0.5))) * size
           for _ in range(count)]
    vel = [mathutils.Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1),
                             rnd.uniform(-0.3, 0.3))).normalized()
           * size * 0.8 for _ in range(count)]
    bpy.ops.mesh.primitive_cone_add(radius1=size * 0.03, depth=size * 0.09,
                                    location=(0, 0, -1e6))
    proto = bpy.context.object
    agents = []
    for i in range(count):
        cp = proto.copy(); cp.data = proto.data
        cp.name = "AuroraBoid_%03d" % i
        cp.rotation_mode = "XYZ"
        scene.collection.objects.link(cp)
        agents.append(cp)
    bpy.data.objects.remove(proto, do_unlink=True)
    dt = 1.0 / fps
    amp = 0.0
    # le centre d'interet derive: la nuee voyage au lieu de tourner sur place
    for fr in range(1, f_end + 1):
        t = (fr - 1) / float(f_end - 1)
        target = center + mathutils.Vector((math.sin(t * 4.0), math.cos(t * 3.0),
                                            0.4 * math.sin(t * 5.0))) * size
        com = sum(pos, mathutils.Vector()) / count
        for i in range(count):
            coh = (com - pos[i]) * 0.8 + (target - pos[i]) * 1.2
            sep = mathutils.Vector()
            for j in range(count):
                if j == i:
                    continue
                d = pos[i] - pos[j]
                L = d.length
                if 1e-6 < L < size * 0.25:
                    sep += d / (L * L)
            ali = (sum(vel, mathutils.Vector()) / count - vel[i]) * 0.5
            vel[i] += (coh + sep * size * 0.05 + ali) * dt
            sp = vel[i].length
            vmax = size * 2.2
            if sp > vmax:
                vel[i] *= vmax / sp
            prev = pos[i].copy()
            pos[i] += vel[i] * dt
            amp = max(amp, (pos[i] - prev).length * (f_end - 1))
            a = agents[i]
            a.location = pos[i]
            # oriente le nez dans la direction du vol
            if vel[i].length > 1e-6:
                a.rotation_euler = vel[i].to_track_quat("Z", "Y").to_euler()
            a.keyframe_insert("location", frame=fr)
            a.keyframe_insert("rotation_euler", frame=fr)
    out = {"frame_count": f_end, "agents": count,
           "amplitude_m": round(min(amp, 99.0), 4), "path": "blender_essaim"}
    if amp < 1e-4:
        out["error"] = "la nuee ne vole pas"
    return out




def bake_wind_sway(intent, scene, fps):
    """Vegetation au vent: arbre, herbe, ble. Le pied reste plante, la cime
    balance — somme de 2 sinus (rafale lente + fremissement), amplitude en
    puissance de la hauteur. Une seule cle de forme, valeur animee -1..1."""
    w = intent.get("wind_anim") or {}
    force = max(0.0, min(1.0, float(w.get("force") or 0.4)))
    loop_s = float(w.get("loop_s") or 3.0)
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucune vegetation"}
    f_end = max(2, int(round(loop_s * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    co = [v.co.copy() for v in obj.data.vertices]
    z0 = min(c.z for c in co)
    height = max(max(c.z for c in co) - z0, 1e-6)
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Base", from_mix=False)
    kb = obj.shape_key_add(name="Vent", from_mix=False)
    amp = 0.0
    lean = force * height * 0.18
    for i, c in enumerate(co):
        h = ((c.z - z0) / height) ** 1.5
        kb.data[i].co = c + mathutils.Vector((lean * h, 0.25 * lean * h, -0.15 * lean * h * h))
        amp = max(amp, (kb.data[i].co - c).length)
    kb.slider_min = -1.0
    for fr in range(1, f_end + 1):
        t = (fr - 1) / float(f_end - 1)
        kb.value = math.sin(2 * math.pi * t) + 0.35 * math.sin(2 * math.pi * 2.3 * t)
        kb.keyframe_insert("value", frame=fr)
    out = {"frame_count": f_end, "force": force, "amplitude_m": round(amp, 4),
           "path": "blender_vent_vegetation"}
    if amp < 1e-4:
        out["error"] = "la vegetation ne bouge pas"
    return out


def bake_periodic_locomotion(intent, scene, fps):
    """Locomotion NON humanoide: vol battu (ailes), nage (onde qui parcourt le
    corps), reptation. Onde progressive = cles de forme par image (la phase
    voyage, une seule cle ne suffit pas)."""
    q = intent.get("locomotion_anim") or {}
    kind = q.get("kind") or "wings"
    loop_s = float(q.get("loop_s") or 2.0)
    beats = max(1.0, float(q.get("beats") or 3.0))
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun corps"}
    f_end = max(2, int(round(loop_s * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    co = [v.co.copy() for v in obj.data.vertices]
    xs = [c.x for c in co]; ys = [c.y for c in co]
    x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
    sx = max(x1 - x0, 1e-6); sy = max(y1 - y0, 1e-6)
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Base", from_mix=False)
    amp = 0.0
    if kind in ("wings", "ailes", "papillon", "oiseau"):
        # UNE cle: les extremites laterales montent; valeur = sinus (battement)
        kb = obj.shape_key_add(name="Battement", from_mix=False)
        for i, c in enumerate(co):
            lat = abs((c.x - (x0 + x1) / 2) / (sx / 2))   # 0 centre, 1 bout d'aile
            wing = max(0.0, lat - 0.25) / 0.75
            kb.data[i].co = c + mathutils.Vector((0, 0, 0.35 * sx * (wing ** 1.6)))
            amp = max(amp, (kb.data[i].co - c).length)
        kb.slider_min = -1.0
        for fr in range(1, f_end + 1):
            t = (fr - 1) / float(f_end - 1)
            kb.value = math.sin(2 * math.pi * beats * t)
            kb.keyframe_insert("value", frame=fr)
    else:
        # nage/reptation: onde laterale qui PARCOURT le corps -> 1 cle par image
        steps = min(f_end, 24)
        for sstep in range(steps):
            fr = 1 + int(round(sstep * (f_end - 1) / float(max(steps - 1, 1))))
            t = sstep / float(max(steps - 1, 1))
            kb = obj.shape_key_add(name="onde_%03d" % fr, from_mix=False)
            for i, c in enumerate(co):
                u = (c.y - y0) / sy      # position le long du corps
                dx = 0.12 * sy * math.sin(2 * math.pi * (2.0 * u - beats * t)) * (0.3 + 0.7 * u)
                kb.data[i].co = c + mathutils.Vector((dx, 0, 0))
                amp = max(amp, abs(dx))
            kb.value = 0.0; kb.keyframe_insert("value", frame=max(1, fr - 1))
            kb.value = 1.0; kb.keyframe_insert("value", frame=fr)
            kb.value = 0.0; kb.keyframe_insert("value", frame=min(f_end, fr + 1))
    out = {"frame_count": f_end, "kind": kind, "amplitude_m": round(amp, 4),
           "path": "blender_locomotion_periodique"}
    if amp < 1e-4:
        out["error"] = "aucun battement"
    return out


def bake_levitation(intent, scene, fps):
    """Levitation: drone, fantome, cristal magique. Flottement vertical doux +
    rotation lente. Le plus simple de tous — et tres demande."""
    l = intent.get("levitation_anim") or {}
    loop_s = float(l.get("loop_s") or 3.0)
    hover = max(0.0, min(1.0, float(l.get("hover") or 0.4)))
    spin = float(l.get("spin_turns") or 0.5)
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "rien a faire leviter"}
    f_end = max(2, int(round(loop_s * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.2)
    obj.rotation_euler = obj.rotation_quaternion.to_euler("XYZ")
    obj.rotation_mode = "XYZ"
    bz = obj.location.z
    brz = obj.rotation_euler.z
    amp = 0.0
    for fr in range(1, f_end + 1):
        t = (fr - 1) / float(f_end - 1)
        dz = hover * size * 0.15 * math.sin(2 * math.pi * t)
        obj.location.z = bz + size * 0.25 + dz
        obj.rotation_euler.z = brz + 2 * math.pi * spin * t
        obj.keyframe_insert("location", frame=fr)
        obj.keyframe_insert("rotation_euler", frame=fr)
        amp = max(amp, abs(size * 0.25 + dz))
    out = {"frame_count": f_end, "amplitude_m": round(amp, 4),
           "path": "blender_levitation"}
    if amp < 1e-4:
        out["error"] = "pas de levitation"
    return out


def bake_oscillation(intent, scene, fps):
    """Pendule, balancier, ressort, toupie: oscillation amortie analytique
    theta(t) = A e^(-lambda t) cos(omega t), pivot au SOMMET du sujet."""
    o = intent.get("oscillation_anim") or {}
    kind = o.get("kind") or "pendulum"
    dur = float(o.get("duration_s") or 3.0)
    theta0 = float(o.get("angle_deg") or 35.0) * math.pi / 180.0
    damping = max(0.0, min(1.0, float(o.get("damping") or 0.25)))
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "rien a faire osciller"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    obj.rotation_euler = obj.rotation_quaternion.to_euler("XYZ")
    obj.rotation_mode = "XYZ"
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    top = max(verts, key=lambda v: v.z)          # pivot: point le plus haut
    L0 = obj.location.copy()
    br = obj.rotation_euler.copy()
    amp = 0.0
    omega = 2 * math.pi * max(1.0, float(o.get("cycles") or 3.0)) / dur
    lam = damping * 1.2
    for fr in range(1, f_end + 1):
        t = (fr - 1) / float(fps)
        if kind in ("spring", "ressort"):
            k = theta0 * math.exp(-lam * t) * math.cos(omega * t)
            obj.location = L0 + mathutils.Vector((0, 0, k * 0.4))
            obj.keyframe_insert("location", frame=fr)
            amp = max(amp, abs(k * 0.4))
        elif kind in ("top", "toupie", "gyroscope"):
            obj.rotation_euler.z = br.z + omega * t * 2.0
            obj.rotation_euler.x = br.x + 0.12 * math.sin(omega * 0.3 * t)
            obj.rotation_euler.y = br.y + 0.12 * math.cos(omega * 0.3 * t)
            obj.keyframe_insert("rotation_euler", frame=fr)
            amp = max(amp, 0.12)
        else:
            th = theta0 * math.exp(-lam * t) * math.cos(omega * t)
            rot = mathutils.Matrix.Rotation(th, 4, "X")
            obj.location = top + rot @ (L0 - top)
            obj.rotation_euler = (br.x + th, br.y, br.z)
            obj.keyframe_insert("location", frame=fr)
            obj.keyframe_insert("rotation_euler", frame=fr)
            amp = max(amp, abs(th) * (L0 - top).length)
    out = {"frame_count": f_end, "kind": kind, "amplitude_m": round(amp, 4),
           "path": "blender_oscillation"}
    if amp < 1e-4:
        out["error"] = "aucune oscillation"
    return out


def bake_shockwave(intent, scene, fps):
    """Onde de choc / anneau d'impact: un tore part du sujet et s'etend en
    s'aplatissant. Le changement d'echelle est natif GLB."""
    w = intent.get("shockwave_anim") or {}
    dur = float(w.get("duration_s") or 1.2)
    reach = float(w.get("reach") or 6.0)
    obj = _largest_mesh(scene)
    if obj is not None:
        cx, cy = obj.location.x, obj.location.y
        cz = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
        size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.3)
    else:
        cx, cy, cz, size = 0.0, 0.0, 0.0, 1.0
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    bpy.ops.mesh.primitive_torus_add(major_radius=size * 0.4,
                                     minor_radius=size * 0.06,
                                     location=(cx, cy, cz + size * 0.05))
    ring = bpy.context.object
    ring.name = "AuroraOnde"
    amp = 0.0
    for fr in range(1, f_end + 1):
        t = (fr - 1) / float(f_end - 1)
        k = 0.15 + reach * (t ** 0.6)          # part vite, ralentit
        ring.scale = (k, k, max(0.05, 1.0 - 0.9 * t))
        ring.keyframe_insert("scale", frame=fr)
        amp = max(amp, k * size * 0.4)
    out = {"frame_count": f_end, "portee_m": round(amp, 3),
           "amplitude_m": round(amp, 4), "path": "blender_onde_de_choc"}
    return out




def bake_muscle_tissue(intent, scene, fps):
    """Biomecanique: chair/muscle qui tremble (ancre) ou gelee qui s'ecrase.

    Le solveur est VELLUM (Houdini, tetraedres volumetriques) — ce que Blender
    n'a pas. Aller-retour par .obj en preservant l'ORDRE des sommets: la
    surface deformee par pointdeform garde la topologie d'entree, on peut donc
    graver chaque image en cle de forme sur le maillage Blender d'origine.
    Attention aux axes: Houdini est Y-haut, Blender Z-haut -> (x, z, -y) a
    l'aller, l'inverse au retour.
    """
    m = intent.get("muscle_anim") or {}
    mode = m.get("mode") or "jiggle"        # jiggle (ancre) | splat (gelee)
    dur = float(m.get("duration_s") or 1.5)
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucune chair a simuler"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end

    import os as _os
    import sys as _sys
    import tempfile as _tmp
    _svc = _os.path.dirname(_os.path.abspath(__file__))
    if _svc not in _sys.path:
        _sys.path.insert(0, _svc)
    try:
        import houdini_sim as _hs
    except Exception as exc:  # noqa: BLE001
        return {"error": "passerelle Houdini indisponible: %r" % (exc,)}
    _okh, _whyh = _hs.available()
    if not _okh:
        return {"error": _whyh}

    # 1) exporter le maillage en obj, ORDRE PRESERVE, converti en Y-haut
    work = _tmp.mkdtemp(prefix="aurora_vellum_")
    src_obj = _os.path.join(work, "entree.obj")
    me = obj.data
    with open(src_obj, "w") as f:
        for v in me.vertices:
            f.write("v %.6f %.6f %.6f\n" % (v.co.x, v.co.z, -v.co.y))
        for poly in me.polygons:
            f.write("f " + " ".join(str(i + 1) for i in poly.vertices) + "\n")

    # 2) simulation Vellum
    r = _hs.simulate("vellum", _os.path.join(work, "sim"),
                     duration_s=dur, fps=fps, pin=(mode != "splat"),
                     source_mesh=src_obj)
    if not r.get("ok"):
        return {"error": "vellum: %s" % str(r.get("error"))[:160]}

    # 3) relire chaque image (retour en Z-haut) -> cles de forme
    n_verts = len(me.vertices)
    frames = []
    sim_dir = r["dossier"]
    for fr in range(1, f_end + 1):
        p_obj = _os.path.join(sim_dir, "surface.%04d.obj" % fr)
        if not _os.path.isfile(p_obj):
            break
        coords = []
        with open(p_obj) as f:
            for line in f:
                if line.startswith("v "):
                    x, y, z = (float(t) for t in line.split()[1:4])
                    coords.append(mathutils.Vector((x, -z, y)))
        if len(coords) != n_verts:
            return {"error": "correspondance de sommets rompue "
                             "(%d -> %d): la topologie n'a pas survecu"
                     % (n_verts, len(coords))}
        frames.append(coords)
    if len(frames) < 2:
        return {"error": "moins de 2 images simulees relues"}

    if me.shape_keys is None:
        obj.shape_key_add(name="Base", from_mix=False)
    amp = 0.0
    for offset, coords in enumerate(frames):
        fr = 1 + offset
        kb = obj.shape_key_add(name="chair_%03d" % fr, from_mix=False)
        for i, co in enumerate(coords):
            kb.data[i].co = co
            amp = max(amp, (co - me.vertices[i].co).length)
        kb.value = 0.0; kb.keyframe_insert("value", frame=max(1, fr - 1))
        kb.value = 1.0; kb.keyframe_insert("value", frame=fr)
        kb.value = 0.0; kb.keyframe_insert("value", frame=min(f_end, fr + 1))
    out = {"frame_count": len(frames), "mode": mode,
           "amplitude_m": round(amp, 4), "path": "houdini_vellum_tetraedres"}
    if amp < 1e-4:
        out["error"] = "la chair ne bouge pas"
    return out




def bake_dissolve(intent, scene, fps):
    """Desintegration / teleportation: la matiere disparait selon un seuil de
    bruit anime (effet "poussiere"). Les materiaux animes ne tenant pas dans
    un GLB, c'est une voie RENDU."""
    d = intent.get("dissolve_anim") or {}
    dur = float(d.get("duration_s") or 2.0)
    sens = d.get("sens") or "disparition"     # disparition | apparition
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "rien a dissoudre"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    m = bpy.data.materials.new("AuroraDissolve")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9.0
    # LESS_THAN: la matiere disparait la ou le seuil DEPASSE le bruit.
    # GREATER_THAN inversait l'effet (le sujet apparaissait au lieu de
    # disparaitre — verifie sur images).
    thr = nt.nodes.new("ShaderNodeMath"); thr.operation = "LESS_THAN"
    mixs = nt.nodes.new("ShaderNodeMixShader")
    trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    emis = nt.nodes.new("ShaderNodeEmission")
    emis.inputs["Color"].default_value = (1.0, 0.55, 0.15, 1.0)
    emis.inputs["Strength"].default_value = 6.0
    edge = nt.nodes.new("ShaderNodeMath"); edge.operation = "LESS_THAN"
    mixe = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(noise.outputs["Fac"], thr.inputs[0])
    nt.links.new(noise.outputs["Fac"], edge.inputs[0])
    nt.links.new(bsdf.outputs[0], mixe.inputs[1])
    nt.links.new(emis.outputs[0], mixe.inputs[2])
    nt.links.new(edge.outputs[0], mixe.inputs[0])
    nt.links.new(mixe.outputs[0], mixs.inputs[1])
    nt.links.new(trans.outputs[0], mixs.inputs[2])
    nt.links.new(thr.outputs[0], mixs.inputs[0])
    nt.links.new(mixs.outputs[0], out.inputs["Surface"])
    m.blend_method = "HASHED" if hasattr(m, "blend_method") else None or "HASHED"
    obj.data.materials.clear()
    obj.data.materials.append(m)
    for fr in range(1, f_end + 1):
        t = (fr - 1) / float(f_end - 1)
        k = t if sens == "disparition" else (1.0 - t)
        thr.inputs[1].default_value = k          # seuil qui monte = ca disparait
        thr.inputs[1].keyframe_insert("default_value", frame=fr)
        edge.inputs[1].default_value = min(1.0, k + 0.06)   # lisere incandescent
        edge.inputs[1].keyframe_insert("default_value", frame=fr)
    return {"frame_count": f_end, "sens": sens,
            "path": "cycles_dissolution", "voie": "rendu"}


def bake_trail_wake(intent, scene, fps):
    """Sillage / trainee: le sujet avance et laisse derriere lui une trainee
    de jalons qui apparaissent a son passage. Tout en cles — GLB."""
    w = intent.get("trail_anim") or {}
    dur = float(w.get("duration_s") or 2.5)
    travel = float(w.get("travel_m") or 0.0)
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun sujet"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.3)
    if travel <= 0.0:
        travel = size * 3.0
    base = obj.location.copy()
    for fr in range(1, f_end + 1):
        t = (fr - 1) / float(f_end - 1)
        obj.location = base + mathutils.Vector((travel * t, 0, 0))
        obj.keyframe_insert("location", frame=fr)
    n_marks = 10
    for i in range(n_marks):
        ti = (i + 0.5) / n_marks
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=10, ring_count=6, radius=size * 0.08,
            location=(base.x + travel * ti, base.y,
                      base.z - size * 0.35))
        mk = bpy.context.object
        mk.name = "AuroraSillage_%02d" % i
        fr_on = max(1, int(round(1 + ti * (f_end - 1))))
        mk.scale = (0.001, 0.001, 0.001)
        mk.keyframe_insert("scale", frame=max(1, fr_on - 1))
        mk.scale = (1.0, 1.0, 1.0)
        mk.keyframe_insert("scale", frame=fr_on)
    return {"frame_count": f_end, "jalons": n_marks,
            "amplitude_m": round(travel, 3), "path": "blender_sillage"}


def bake_ground_traces(intent, scene, fps):
    """Empreintes au sol: le sujet avance, le sol s'enfonce a son passage et
    les creux RESTENT (accumulation par cles de forme successives)."""
    g = intent.get("traces_anim") or {}
    dur = float(g.get("duration_s") or 2.5)
    depth = float(g.get("depth") or 0.5)
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "aucun sujet"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.3)
    lo_z = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
    travel = size * 3.0
    base = obj.location.copy()
    for fr in range(1, f_end + 1):
        t = (fr - 1) / float(f_end - 1)
        obj.location = base + mathutils.Vector((travel * t, 0, 0))
        obj.keyframe_insert("location", frame=fr)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=48, y_subdivisions=16,
                                    size=1.0, location=(base.x + travel / 2,
                                                        base.y, lo_z))
    sol = bpy.context.object
    sol.name = "AuroraSol"
    sol.scale = (travel * 0.75 + size, size * 2.0, 1.0)
    bpy.context.view_layer.objects.active = sol
    bpy.ops.object.transform_apply(scale=True)
    sol.shape_key_add(name="Base", from_mix=False)
    verts = sol.data.vertices
    dent = [0.0] * len(verts)
    creux = depth * size * 0.12
    ray = size * 0.45
    steps = min(f_end, 20)
    amp = 0.0
    for sstep in range(steps):
        fr = 1 + int(round(sstep * (f_end - 1) / float(max(steps - 1, 1))))
        t = (fr - 1) / float(f_end - 1)
        px = base.x + travel * t
        for i, v in enumerate(verts):
            wx = sol.matrix_world @ v.co
            d2 = (wx.x - px) ** 2 + (wx.y - base.y) ** 2
            if d2 < ray * ray:
                # le creux persiste: on garde le max deja atteint
                dent[i] = min(dent[i], -creux * (1.0 - d2 / (ray * ray)))
        kb = sol.shape_key_add(name="trace_%03d" % fr, from_mix=False)
        for i, v in enumerate(verts):
            kb.data[i].co = v.co + mathutils.Vector((0, 0, dent[i]))
            amp = max(amp, abs(dent[i]))
        kb.value = 0.0; kb.keyframe_insert("value", frame=max(1, fr - 1))
        kb.value = 1.0; kb.keyframe_insert("value", frame=fr)
        if fr < f_end:
            kb.value = 0.0; kb.keyframe_insert("value", frame=min(f_end, fr + 1))
    out = {"frame_count": f_end, "amplitude_m": round(amp, 4),
           "path": "blender_empreintes"}
    if amp < 1e-5:
        out["error"] = "aucune empreinte"
    return out


def bake_accumulation(intent, scene, fps):
    """Accumulation (neige, poussiere, cendre): une couche blanche epaissit
    progressivement sur les faces orientees vers le haut."""
    a = intent.get("accumulation_anim") or {}
    dur = float(a.get("duration_s") or 3.0)
    epais = max(0.0, min(1.0, float(a.get("thickness") or 0.4)))
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "rien a recouvrir"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.3)
    shell = obj.copy()
    shell.data = obj.data.copy()
    shell.name = "AuroraNeige"
    scene.collection.objects.link(shell)
    m = bpy.data.materials.new("AuroraNeigeMat")
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.93, 0.95, 1.0, 1.0)
    if "Roughness" in b.inputs:
        b.inputs["Roughness"].default_value = 0.85
    shell.data.materials.clear()
    shell.data.materials.append(m)
    shell.shape_key_add(name="Base", from_mix=False)
    kb = shell.shape_key_add(name="Couche", from_mix=False)
    me = shell.data
    amp = 0.0
    ep = epais * size * 0.06
    for i, v in enumerate(me.vertices):
        n = v.normal
        k = max(0.0, n.z) ** 1.5          # seulement les faces vers le haut
        kb.data[i].co = v.co + n * (ep * k)
        amp = max(amp, ep * k)
    # depart: coquille aplatie sur le maillage (invisible), fin: pleine
    for fr, val in ((1, 0.0), (f_end, 1.0)):
        kb.value = val
        kb.keyframe_insert("value", frame=fr)
    out = {"frame_count": f_end, "epaisseur_m": round(amp, 4),
           "amplitude_m": round(amp, 4), "path": "blender_accumulation"}
    if amp < 1e-5:
        out["error"] = "aucune accumulation"
    return out


def bake_morphing(intent, scene, fps):
    """Metamorphose vers une forme cible (sphere ou cube): chaque sommet est
    projete analytiquement sur la surface cible — cle de forme native GLB."""
    mo = intent.get("morph_anim") or {}
    target = mo.get("target") or "sphere"
    dur = float(mo.get("duration_s") or 2.5)
    obj = _largest_mesh(scene)
    if obj is None:
        return {"error": "rien a transformer"}
    f_end = max(2, int(round(dur * fps)))
    scene.frame_start, scene.frame_end = 1, f_end
    co = [v.co.copy() for v in obj.data.vertices]
    if not co:
        return {"error": "maillage vide"}
    ctr = sum(co, mathutils.Vector()) / len(co)
    R = max((c - ctr).length for c in co) * 0.85
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Base", from_mix=False)
    kb = obj.shape_key_add(name="Cible", from_mix=False)
    amp = 0.0
    for i, c in enumerate(co):
        d = c - ctr
        L = d.length
        if target in ("cube", "boite"):
            m = max(abs(d.x), abs(d.y), abs(d.z), 1e-9)
            tgt = ctr + d * (R / m) * 0.8
        else:
            tgt = ctr + (d / L * R if L > 1e-9 else mathutils.Vector((0, 0, R)))
        kb.data[i].co = tgt
        amp = max(amp, (tgt - c).length)
    for fr, val in ((1, 0.0), (f_end, 1.0)):
        kb.value = val
        kb.keyframe_insert("value", frame=fr)
    out = {"frame_count": f_end, "cible": target,
           "amplitude_m": round(amp, 4), "path": "blender_morphing"}
    if amp < 1e-4:
        out["error"] = "aucune metamorphose"
    return out


HANDLERS = {
    "led_emission":      bake_led_emission,
    "fan_pwm":           bake_fan_pwm,
    "oled_screen":       bake_oled_screen,
    "creature_organic":  bake_creature_organic,
    "mechanical_simple": bake_mechanical_simple,
    "rigid_static":      bake_rigid_static,
    "fluid_flow":        bake_fluid_flow,
    "gas_volume":        bake_gas_volume,
    "cloth_drape":       bake_cloth_drape,
    "rigid_bodies":      bake_rigid_bodies,
    "soft_body":         bake_soft_body,
    "hair_fur":          bake_hair_fur,
    "particles":         bake_particles,
    "fracture_debris":   bake_fracture_debris,
    "ocean_surface":     bake_ocean_surface,
    "orbital_motion":    bake_orbital,
    "articulated_rig":   bake_articulated_rig,
    "rope_net":          bake_rope_net,
    "growth":            bake_growth,
    "chemistry":         bake_chemistry,
    "optics":            bake_optics,
    "smoke_fire":        bake_smoke_fire,
    "granular":          bake_granular,
    "thermal_melt":      bake_melt,
    "plasma":            bake_plasma,
    "vortex_tornado":    bake_vortex,
    "buoyancy_float":    bake_buoyancy,
    "swarm_flock":       bake_swarm,
    "wind_sway":         bake_wind_sway,
    "periodic_locomotion": bake_periodic_locomotion,
    "levitation":        bake_levitation,
    "oscillation":       bake_oscillation,
    "shockwave":         bake_shockwave,
    "muscle_tissue":     bake_muscle_tissue,
    "dissolve_teleport": bake_dissolve,
    "trail_wake":        bake_trail_wake,
    "ground_traces":     bake_ground_traces,
    "accumulation":      bake_accumulation,
    "morphing":          bake_morphing,
}


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    intent_path = args[args.index("--intent") + 1]
    input_path = args[args.index("--input") + 1]
    output_path = args[args.index("--output") + 1]
    fps = int(args[args.index("--fps") + 1]) if "--fps" in args else 24

    with open(intent_path, "r", encoding="utf-8") as f:
        intent = json.load(f)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=input_path)
    scene = bpy.context.scene
    scene.render.fps = fps

    cat = intent.get("category")
    handler = HANDLERS.get(cat)
    if handler is None:
        result = {"error": "unknown category " + repr(cat)}
    else:
        try:
            result = handler(intent, scene, fps)
            result["category"] = cat
            # Un domaine qui ne tient pas dans un GLB (volume, matiere animee,
            # chemin lumineux) le declare: on le REND au lieu de livrer un
            # fichier vide en pretendant que c'est fait.
            if result.get("voie") == "rendu" and not result.get("error"):
                try:
                    result.update(_render_sequence(
                        scene, output_path,
                        int(result.get("frame_count") or scene.frame_end)))
                except Exception as rexc:  # noqa: BLE001
                    result["render_error"] = str(rexc)
        except Exception as exc:
            result = {"error": str(exc), "category": cat}

    # iter25.smooth: smooth shading sur tous les meshes (fixes "triangle effect").
    # Via l'API DATA (pas bpy.ops) -> robuste en --background : l'operateur select_all/shade_smooth
    # echoue "context is incorrect" quand un rig importe laisse le contexte hors mode OBJECT.
    for obj in bpy.data.objects:
        me = getattr(obj, "data", None)
        if obj.type == 'MESH' and me and len(me.polygons):
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
            me.update()
    # (pas de select_all : export_scene.gltf ci-dessous exporte toute la scene, pas use_selection)

    # iter11.A: Draco mesh compression. Hunyuan3D meshes ballooned 16 MB → 94 MB
    # on Blender re-export (float32 positions/normals/UVs, no quantization). Draco
    # quantizes positions to 14-bit (sub-mm for sub-10m meshes), normals to 10-bit,
    # UVs to 12-bit, vertex colors to 8-bit — typical 8-15× ratio with no visible
    # loss. KHR_draco_mesh_compression extension is recognised by Three.js
    # GLTFLoader (DRACOLoader) and the standalone aurora_3d_viewer (we wire those
    # in iter11.C). Blender 5.1 ships extern_draco.dll under
    # scripts/addons_core/io_scene_gltf2/, confirmed present.
    export_kwargs = dict(
        filepath=output_path,
        export_format="GLB",
        export_animations=True,
        export_force_sampling=True,
        export_nla_strips=False,
        export_extras=True,
        export_morph=True,
        export_morph_animation=True,
        # Sans ceci, glTF ne transporte AUCUNE animation de materiau: la
        # corrosion, l'oxydation ou la braise qui s'allume sortaient dans un
        # fichier sans la moindre piste d'animation. L'extension
        # KHR_animation_pointer est ce qui rend la matiere animable.
        # Blender NEUTRALISE export_pointer_animation si export_animation_mode
        # n'est pas pose (gate io_scene_gltf2/__init__.py) — le drapeau etait
        # vrai et l'animation de materiau sortait quand meme VIDE, sans
        # avertissement. ACTIONS conserve le rig ET active le pointer.
        export_animation_mode="ACTIONS",
        export_pointer_animation=True,
        # convert_animation_pointer=True casse le rig quand le pointer est
        # reellement actif (conversion des canaux) -> desactive.
        export_convert_animation_pointer=False,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
        export_draco_position_quantization=14,
        export_draco_normal_quantization=10,
        export_draco_texcoord_quantization=12,
        export_draco_color_quantization=8,
        export_draco_generic_quantization=12,
        # DESACTIVE. Cet optimiseur supprime les canaux d'animation qu'il juge
        # insignifiants — il a fait sortir la fourrure immobile, puis un bras
        # articule dont il ne restait qu'un canal sur deux. Un fichier plus
        # gros mais complet vaut mieux qu'un fichier leger et faux.
        export_optimize_animation_size=False,
    )
    try:
        bpy.ops.export_scene.gltf(**export_kwargs)
        result["exported"] = output_path
        result["compression"] = "draco"
    except TypeError as exc:
        # Older Blender (< 2.95 or no libdraco): retry without Draco kwargs.
        try:
            for k in list(export_kwargs):
                if k.startswith("export_draco_") or k in ("export_optimize_animation_size", "export_morph_animation"):
                    del export_kwargs[k]
            bpy.ops.export_scene.gltf(**export_kwargs)
            result["exported"] = output_path
            result["compression"] = "none"
            result["compression_warn"] = "draco unavailable: " + str(exc)
        except Exception as exc2:
            result["export_error"] = str(exc2)
    except Exception as exc:
        result["export_error"] = str(exc)

    print("AURORA_RESULT_BEGIN")
    print(json.dumps(result))
    print("AURORA_RESULT_END")


if __name__ == "__main__":
    main()
