#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""motion_intent_bpy_runner -- bpy-side companion of motion_intent_baker.py.

This file is consumed by `blender --background --python` ; it must NOT be
imported by regular Python (it has no shebang test guards because Blender
runs it as the main module). It expects argv past `--` to include:

    --intent <path>  --input <glb> --output <glb> [--fps N]

Six categories handled:
  led_emission / fan_pwm / oled_screen /
  creature_organic / mechanical_simple / rigid_static

Each branch operates on a fresh empty scene + the imported GLB, then exports
back to GLB with NLA actions baked in.
"""

import bpy
import json  # noqa: F401  (used in OLED atlas metadata + main driver)
import sys
import math


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
    """Decide which kind of skeleton fits the imported mesh.

    Cheap heuristic: bbox aspect ratio + symmetry hint.
      - height >> width   -> humanoid (vertical biped)
      - width  >> height  -> quadruped (horizontal animal)
      - length >> all     -> serpent (long/snake-like)
      - flat/cube         -> none (fallback breathing)

    The user-provided hint (creature_anim.locomotion) wins when it is one of
    {humanoid, quadruped, serpent}; "auto" or missing -> heuristic.
    """
    if hint in ("humanoid", "quadruped", "serpent"):
        return hint
    dx, dy, dz = mesh_obj.dimensions.x, mesh_obj.dimensions.y, mesh_obj.dimensions.z
    if max(dx, dy, dz) < 1e-4:
        return "none"
    long_axis = max(dx, dy, dz)
    short_axis = max(min(dx, dy, dz), 1e-4)
    aspect = long_axis / short_axis
    # Vertical = Z dominant
    if dz >= dx and dz >= dy and aspect >= 1.6:
        return "humanoid"
    # Horizontal: X or Y dominant, Z is "low"
    horizontal = max(dx, dy)
    if horizontal >= dz * 1.4 and aspect >= 1.6:
        # Long thin -> serpent, otherwise quadruped
        if aspect >= 4.0:
            return "serpent"
        return "quadruped"
    return "none"


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
    """Build a topology-appropriate Rigify rig + bake idle/walk cycles.

    Returns (rig_obj_or_none, total_frames, info_dict). On any Rigify error
    returns (None, 0, {error}); the caller is expected to graceful-degrade.

    Rigify ships with three relevant metarig presets:
      - `armature_human_metarig_add`     (humanoid)
      - `armature_basic_quadruped_metarig_add` (quadruped)
      - For serpent we manually build a 6-bone spline chain (rigify has no
        snake metarig as of 5.1 — snakes need spine.basic_chain via the
        rigify_types module which is overkill for a baked NLA cycle).
    """
    info = {"topology": topology, "base_loop": base_loop, "bpm": bpm}
    try:
        bpy.ops.preferences.addon_enable(module="rigify")
    except Exception as exc:
        return None, 0, {"error": "rigify enable failed: %s" % exc, **info}

    # Center the mesh at origin so the metarig lines up
    if topology in ("humanoid", "quadruped"):
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
            # Rigify quadruped operator (Blender 4.x+)
            try:
                bpy.ops.object.armature_basic_quadruped_metarig_add()
            except Exception:
                # Some builds register it under a different name
                bpy.ops.object.armature_basic_human_metarig_add()
            metarig = bpy.context.object
        elif topology == "serpent":
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
    if topology in ("humanoid", "quadruped", "serpent"):
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


def bake_rigid_static(intent, scene, fps):
    scene.frame_start = 1
    scene.frame_end = 1
    for obj in scene.objects:
        if obj.animation_data and obj.animation_data.action:
            obj.animation_data_clear()
    return {"static": True, "frame_count": 1}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

HANDLERS = {
    "led_emission":      bake_led_emission,
    "fan_pwm":           bake_fan_pwm,
    "oled_screen":       bake_oled_screen,
    "creature_organic":  bake_creature_organic,
    "mechanical_simple": bake_mechanical_simple,
    "rigid_static":      bake_rigid_static,
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
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
        export_draco_position_quantization=14,
        export_draco_normal_quantization=10,
        export_draco_texcoord_quantization=12,
        export_draco_color_quantization=8,
        export_draco_generic_quantization=12,
        export_optimize_animation_size=True,
    )
    try:
        bpy.ops.export_scene.gltf(**export_kwargs)
        result["exported"] = output_path
        result["compression"] = "draco"
    except TypeError as exc:
        # Older Blender (< 2.95 or no libdraco): retry without Draco kwargs.
        try:
            for k in list(export_kwargs):
                if k.startswith("export_draco_") or k == "export_optimize_animation_size":
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
