"""Blender headless animator: reads a SceneProfile JSON + GLB and renders
adaptive animations + hero stills. Designed to be invoked as:

    blender --background --python aurora_animate.py -- <glb> <profile.json> <out_dir>

Output (in <out_dir>):
    hero.png            still 1024x1024 PBR render, three-quarter view
    orbit.mp4           360 deg orbit (always, regardless of animation type)
    animated.mp4        animation-driven render (if profile.has_animation)
    render_meta.json    per-frame meta (counts of objects/lights/particles)

Animation handlers are data-driven from profile["animations"][i].type. Unknown
types are logged and skipped (no failure). The script never aborts on missing
features; instead it falls back to beauty_turntable.
"""
from __future__ import annotations

import json
import math
import os
import sys
import traceback
from typing import Any

import bpy
from mathutils import Vector


def _parse_args() -> tuple[str, str, str]:
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        args = sys.argv[idx + 1 :]
    else:
        args = sys.argv[1:]
    if len(args) < 3:
        raise SystemExit(f"usage: blender --background --python aurora_animate.py -- <glb> <profile.json> <out_dir>; got {args}")
    return args[0], args[1], args[2]


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path: str) -> bpy.types.Object:
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"no mesh imported from {path}")
    obj = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for m in meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    return obj


def normalize_to_unit(obj: bpy.types.Object) -> tuple[Vector, float]:
    verts = obj.data.vertices
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    cz = (min(zs) + max(zs)) / 2
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    obj.location = (-cx, -cy, -cz)
    bpy.context.view_layer.update()
    if size > 0.01:
        target = 1.5
        obj.scale = (target / size,) * 3
        bpy.context.view_layer.update()
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)
    return Vector((0, 0, 0)), 1.5


_HDRI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hdri")

_HDRI_BY_MOOD = {
    "studio_clean": ("studio_small_09_1k.hdr", 1.0),
    "dramatic_night": ("moonless_golf_1k.hdr", 0.8),
    "cyberpunk": ("neon_photostudio_1k.hdr", 0.9),
    "golden_hour": ("venice_sunset_1k.hdr", 1.0),
    "underwater": ("underwater_1k.hdr", 0.9),
    "winter_cold": ("snowy_field_1k.hdr", 1.1),
    "desert_hot": ("venice_sunset_1k.hdr", 1.1),
    "lush_forest": ("abandoned_workshop_1k.hdr", 0.8),
    "fantasy_magic": ("neon_photostudio_1k.hdr", 0.7),
    "neutral": ("studio_small_09_1k.hdr", 1.0),
}

_COLOR_FALLBACKS = {
    "dramatic_night": ((0.02, 0.03, 0.06, 1), 0.6),
    "golden_hour": ((0.95, 0.65, 0.4, 1), 1.0),
    "studio_clean": ((0.85, 0.85, 0.88, 1), 1.5),
    "fantasy_magic": ((0.2, 0.05, 0.3, 1), 0.8),
    "cyberpunk": ((0.05, 0.0, 0.15, 1), 0.6),
    "underwater": ((0.0, 0.15, 0.3, 1), 0.5),
    "winter_cold": ((0.7, 0.8, 0.95, 1), 1.2),
    "desert_hot": ((1.0, 0.7, 0.45, 1), 1.4),
    "lush_forest": ((0.1, 0.2, 0.1, 1), 0.9),
    "neutral": ((0.5, 0.5, 0.5, 1), 1.0),
}


def setup_world(mood: str) -> None:
    """HDRI environment map keyed by mood; falls back to a flat color when the
    HDRI file is missing. The HDRI gives realistic reflections + ambient,
    which makes metallic/glass materials look properly photoreal.
    """
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(bg.outputs[0], out.inputs[0])

    hdri_name, strength = _HDRI_BY_MOOD.get(mood, _HDRI_BY_MOOD["neutral"])
    hdri_path = os.path.join(_HDRI_DIR, hdri_name)
    if os.path.exists(hdri_path):
        env_tex = nt.nodes.new("ShaderNodeTexEnvironment")
        env_tex.image = bpy.data.images.load(hdri_path)
        mapping = nt.nodes.new("ShaderNodeMapping")
        tex_coord = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"], env_tex.inputs["Vector"])
        nt.links.new(env_tex.outputs["Color"], bg.inputs[0])
        bg.inputs[1].default_value = strength
        print(f"[animate] world: HDRI {hdri_name} strength={strength}")
    else:
        color, strength = _COLOR_FALLBACKS.get(mood, _COLOR_FALLBACKS["neutral"])
        bg.inputs[0].default_value = color
        bg.inputs[1].default_value = strength
        print(f"[animate] world: solid color fallback (HDRI not found at {hdri_path})")

try:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    import motion_intent_bpy_runner
except ImportError as e:
    print(f"Failed to import motion_intent_bpy_runner: {e}")
    motion_intent_bpy_runner = None


def setup_lights(mood: str, size: float) -> None:
    """Directional key + fill on top of HDRI ambient. Energies are lower than
    pre-HDRI defaults because the environment map already supplies global
    illumination; these lights just sculpt the subject.
    """
    key = bpy.data.lights.new("Key", type="AREA")
    key.size = size * 2
    key.energy = 600
    obj = bpy.data.objects.new("Key", key)
    bpy.context.collection.objects.link(obj)
    obj.location = (size, -size, size * 1.4)
    obj.rotation_euler = (math.radians(50), 0, math.radians(30))

    fill = bpy.data.lights.new("Fill", type="AREA")
    fill.size = size * 3
    fill.energy = 200
    obj2 = bpy.data.objects.new("Fill", fill)
    bpy.context.collection.objects.link(obj2)
    obj2.location = (-size, size * 0.6, size * 0.6)

    if mood in ("dramatic_night", "cyberpunk"):
        rim = bpy.data.lights.new("Rim", type="AREA")
        rim.size = size
        rim.energy = 400
        rim.color = (0.3, 0.6, 1.0) if mood == "cyberpunk" else (0.6, 0.7, 1.0)
        obj3 = bpy.data.objects.new("Rim", rim)
        bpy.context.collection.objects.link(obj3)
        obj3.location = (0, size * 1.5, size * 0.5)
    elif mood == "golden_hour":
        sun = bpy.data.lights.new("Sun", type="SUN")
        sun.energy = 2
        sun.color = (1.0, 0.85, 0.55)
        obj3 = bpy.data.objects.new("Sun", sun)
        bpy.context.collection.objects.link(obj3)
        obj3.rotation_euler = (math.radians(60), 0, math.radians(45))


def setup_camera(size: float, angle_deg: float = 30, elev_deg: float = 18) -> bpy.types.Object:
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    dist = size * 2.6
    yaw = math.radians(angle_deg)
    elev = math.radians(elev_deg)
    cam.location = (math.sin(yaw) * dist * math.cos(elev), -math.cos(yaw) * dist * math.cos(elev), dist * math.sin(elev))
    direction = -Vector(cam.location)
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam.rotation_euler = rot_quat.to_euler()
    bpy.context.scene.camera = cam
    return cam


def configure_render(out_path: str, resolution: int = 1024, samples: int = 64, frames: int = 1, fps: int = 24) -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.device = "GPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "CUDA"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type in {"CUDA", "OPTIX"} or d.type == "CPU"
    except Exception:
        pass
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = max(1, frames)
    scene.render.image_settings.file_format = "PNG" if frames == 1 else "FFMPEG"
    if frames > 1:
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = out_path


def render_to(out_path: str, frames: int = 1) -> None:
    configure_render(out_path, frames=frames)
    bpy.ops.render.render(animation=frames > 1, write_still=frames == 1)


def add_keyframe_rotate_y(obj: bpy.types.Object, frames: int, period_frames: float) -> None:
    obj.rotation_mode = "XYZ"
    cycles = frames / max(1, period_frames)
    obj.keyframe_insert("rotation_euler", index=2, frame=1)
    obj.rotation_euler[2] = math.radians(360 * cycles)
    obj.keyframe_insert("rotation_euler", index=2, frame=frames)
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            if fc.data_path == "rotation_euler" and fc.array_index == 2:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"


def add_keyframe_hover(obj: bpy.types.Object, frames: int, amplitude: float, period_frames: float) -> None:
    base_z = obj.location.z
    step = max(1, int(period_frames / 8))
    for f in range(1, frames + 1, step):
        phase = (f - 1) / period_frames * 2 * math.pi
        obj.location.z = base_z + amplitude * math.sin(phase)
        obj.keyframe_insert("location", index=2, frame=f)
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            if fc.data_path == "location" and fc.array_index == 2:
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"


def add_keyframe_shake(obj: bpy.types.Object, frames: int, amplitude: float, freq_hz: float, fps: int) -> None:
    import random
    rng = random.Random(42)
    bx, by, bz = obj.location.x, obj.location.y, obj.location.z
    step = max(1, int(fps / max(0.5, freq_hz)))
    for f in range(1, frames + 1, step):
        obj.location.x = bx + rng.uniform(-amplitude, amplitude)
        obj.location.y = by + rng.uniform(-amplitude, amplitude)
        obj.location.z = bz + rng.uniform(-amplitude, amplitude)
        obj.keyframe_insert("location", frame=f)


def find_or_make_emission(obj: bpy.types.Object) -> bpy.types.ShaderNodeEmission | None:
    if not obj.data.materials:
        return None
    mat = obj.data.materials[0]
    if not mat.use_nodes:
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return None
    if "Emission Color" in bsdf.inputs and "Emission Strength" in bsdf.inputs:
        if bsdf.inputs["Emission Color"].is_linked:
            return bsdf
        base_color = bsdf.inputs["Base Color"].default_value
        bsdf.inputs["Emission Color"].default_value = base_color
        return bsdf
    return None


def animate_emission_pulse(obj: bpy.types.Object, frames: int, fps: int, freq_hz: float, mn: float, mx: float) -> None:
    bsdf = find_or_make_emission(obj)
    if bsdf is None or "Emission Strength" not in bsdf.inputs:
        return
    strength = bsdf.inputs["Emission Strength"]
    step = max(1, int(fps / max(0.5, freq_hz * 4)))
    for f in range(1, frames + 1, step):
        t = (f - 1) / fps
        v = mn + (mx - mn) * (0.5 + 0.5 * math.sin(2 * math.pi * freq_hz * t))
        strength.default_value = v
        strength.keyframe_insert("default_value", frame=f)


def make_particle_emitter(center: Vector, size: float, kind: str, count: int, params: dict[str, Any], frames: int) -> None:
    if kind == "rain" or kind == "snow":
        plane_size = size * 4
        bpy.ops.mesh.primitive_plane_add(size=plane_size, location=(center.x, center.y, center.z + size * 1.6))
        emitter = bpy.context.active_object
    elif kind == "fire" or kind == "sparks":
        bpy.ops.mesh.primitive_circle_add(radius=size * 0.3, fill_type="NGON", location=(center.x, center.y, center.z - size * 0.5))
        emitter = bpy.context.active_object
    elif kind == "smoke" or kind == "dust":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=size * 0.4, location=(center.x, center.y, center.z))
        emitter = bpy.context.active_object
    else:
        bpy.ops.mesh.primitive_plane_add(size=size * 2, location=(center.x, center.y, center.z + size))
        emitter = bpy.context.active_object
    emitter.hide_render = True
    psys_mod = emitter.modifiers.new("Particles", "PARTICLE_SYSTEM")
    psys = emitter.particle_systems[-1]
    s = psys.settings
    s.count = count
    s.frame_start = 1
    s.frame_end = frames
    s.lifetime = frames
    s.emit_from = "FACE"
    s.physics_type = "NEWTON"
    s.particle_size = size * 0.012
    wind = params.get("wind_xy", [0, 0])
    s.effector_weights.gravity = 1.0 if kind in {"rain", "snow", "dust"} else -0.3 if kind in {"fire", "sparks", "smoke"} else 0.0
    s.normal_factor = 0.0
    s.factor_random = 0.3 * size
    s.object_align_factor = (wind[0] * size, wind[1] * size, params.get("rise_z", 0) * size)
    s.render_type = "HALO"
    color = {
        "rain": (0.6, 0.7, 0.9, 1.0),
        "snow": (1.0, 1.0, 1.0, 1.0),
        "fire": (1.0, 0.5, 0.1, 1.0),
        "sparks": (1.0, 0.8, 0.2, 1.0),
        "smoke": (0.5, 0.5, 0.5, 1.0),
        "dust": (0.7, 0.6, 0.45, 1.0),
    }.get(kind, (1, 1, 1, 1))
    mat = bpy.data.materials.new(f"PMat_{kind}")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if kind in {"fire", "sparks", "smoke", "dust"}:
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs[0].default_value = color
        em.inputs[1].default_value = 3.0 if kind in {"fire", "sparks"} else 0.5
        nt.links.new(em.outputs[0], out.inputs[0])
    else:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.1 if kind == "rain" else 0.4
        nt.links.new(bsdf.outputs[0], out.inputs[0])
    emitter.data.materials.append(mat)


def add_volumetric_gas_domain(center: Vector, size: float, frames: int, density: float = 2.0, color: tuple[float, float, float, float] = (0.2, 0.5, 1.0, 1.0)) -> None:
    """Create a Blender domain with Principled Volume shader for volumetric gas, smoke, plasma or aura."""
    bpy.ops.mesh.primitive_cube_add(size=size * 2.5, location=(center.x, center.y, center.z + size * 0.2))
    domain = bpy.context.active_object
    domain.name = "GasVolumeDomain"
    mat = bpy.data.materials.new("VolumetricGasMaterial")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = density
    vol.inputs["Color"].default_value = color
    vol.inputs["Emission Strength"].default_value = 1.2
    vol.inputs["Emission Color"].default_value = color
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    domain.data.materials.append(mat)

    # Animate volume density fluctuation (sine wave)
    for f in range(1, frames + 1, 4):
        phase = (f - 1) / frames * 4 * math.pi
        vol.inputs["Density"].default_value = max(0.2, density * (0.8 + 0.4 * math.sin(phase)))
        vol.inputs["Density"].keyframe_insert("default_value", frame=f)



def add_camera_orbit(cam: bpy.types.Object, target: Vector, frames: int, radius: float) -> None:
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=tuple(target))
    pivot = bpy.context.active_object
    pivot.name = "OrbitPivot"
    cam.parent = pivot
    cam.matrix_parent_inverse = pivot.matrix_world.inverted()
    pivot.rotation_mode = "XYZ"
    pivot.keyframe_insert("rotation_euler", index=2, frame=1)
    pivot.rotation_euler[2] = math.radians(360)
    pivot.keyframe_insert("rotation_euler", index=2, frame=frames)
    if pivot.animation_data and pivot.animation_data.action:
        for fc in pivot.animation_data.action.fcurves:
            if fc.data_path == "rotation_euler" and fc.array_index == 2:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"


def rig_and_walk(obj: bpy.types.Object, frames: int, out_glb_path: str) -> None:
    # 1. Create a minimal biped armature
    bpy.ops.object.armature_add(enter_editmode=True, align='WORLD', location=(0, 0, 0))
    armature = bpy.context.active_object
    armature.name = "GoldoRig"
    
    # Measure mesh to scale the rig
    verts = obj.data.vertices
    zs = [v.co.z for v in verts]
    height = max(zs) - min(zs) if len(zs) > 0 else 1.5
    
    bpy.ops.armature.select_all(action='SELECT')
    bpy.ops.armature.delete()
    
    amt = armature.data
    # Create bones (Z-up, Y-forward)
    spine = amt.edit_bones.new('spine')
    spine.head = (0, 0, height * 0.4)
    spine.tail = (0, 0, height * 0.7)
    
    thigh_l = amt.edit_bones.new('thigh.L')
    thigh_l.head = (height * 0.15, 0, height * 0.4)
    thigh_l.tail = (height * 0.15, 0, height * 0.2)
    thigh_l.parent = spine
    
    shin_l = amt.edit_bones.new('shin.L')
    shin_l.head = (height * 0.15, 0, height * 0.2)
    shin_l.tail = (height * 0.15, 0, 0)
    shin_l.parent = thigh_l
    
    thigh_r = amt.edit_bones.new('thigh.R')
    thigh_r.head = (-height * 0.15, 0, height * 0.4)
    thigh_r.tail = (-height * 0.15, 0, height * 0.2)
    thigh_r.parent = spine
    
    shin_r = amt.edit_bones.new('shin.R')
    shin_r.head = (-height * 0.15, 0, height * 0.2)
    shin_r.tail = (-height * 0.15, 0, 0)
    shin_r.parent = thigh_r

    arm_l = amt.edit_bones.new('arm.L')
    arm_l.head = (height * 0.3, 0, height * 0.65)
    arm_l.tail = (height * 0.3, 0, height * 0.45)
    arm_l.parent = spine
    
    arm_r = amt.edit_bones.new('arm.R')
    arm_r.head = (-height * 0.3, 0, height * 0.65)
    arm_r.tail = (-height * 0.3, 0, height * 0.45)
    arm_r.parent = spine

    bpy.ops.object.mode_set(mode='OBJECT')
    
    # 2. Parent mesh to armature with automatic weights
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    
    # 3. Animate the walk cycle
    bpy.ops.object.mode_set(mode='POSE')
    pose_bones = armature.pose.bones
    period = 24  # frames per cycle
    
    # Keyframe insertion helper
    def kf(bone_name, axis, val, frame):
        if bone_name in pose_bones:
            pose_bones[bone_name].rotation_mode = 'XYZ'
            pose_bones[bone_name].rotation_euler[axis] = val
            pose_bones[bone_name].keyframe_insert(data_path="rotation_euler", index=axis, frame=frame)
            
    for f in range(1, frames + 1):
        phase = (f / period) * 2 * math.pi
        
        # Thighs (X-axis rotation)
        kf('thigh.L', 0, math.sin(phase) * 0.6, f)
        kf('thigh.R', 0, math.sin(phase + math.pi) * 0.6, f)
        
        # Shins (X-axis, must bend backward, so > 0 or < 0 depending on Blender coords)
        kf('shin.L', 0, (math.sin(phase - math.pi/2) + 1) * 0.5, f)
        kf('shin.R', 0, (math.sin(phase + math.pi/2) + 1) * 0.5, f)
        
        # Arms (X-axis, opposite to legs)
        kf('arm.L', 0, math.sin(phase + math.pi) * 0.5, f)
        kf('arm.R', 0, math.sin(phase) * 0.5, f)
        
        # Slight spine bobbing
        kf('spine', 1, math.sin(phase * 2) * 0.05, f)

    bpy.ops.object.mode_set(mode='OBJECT')
    
    # 4. Export Animated GLB
    bpy.ops.export_scene.gltf(
        filepath=out_glb_path,
        export_format='GLB',
        use_selection=True,
        export_animations=True,
        export_apply=True
    )
    print(f"[animate] wrote rigged/animated GLB to {out_glb_path}")


def render_scene(obj: bpy.types.Object, profile: dict[str, Any], out_dir: str) -> dict[str, Any]:
    mood = profile.get("mood", "neutral")
    fps = int(profile.get("fps", 24))
    duration_s = float(profile.get("duration_s", 6.0))
    frames = max(1, int(duration_s * fps))

    meta = {"mode": "hero", "fps": fps, "frames": frames, "applied": []}

    os.makedirs(out_dir, exist_ok=True)
    reset_scene()
    obj_imported = import_glb(profile["__glb"])
    _, size = normalize_to_unit(obj_imported)
    setup_world(mood)
    setup_lights(mood, size)
    cam = setup_camera(size, angle_deg=35, elev_deg=22)
    hero_path = os.path.join(out_dir, "hero.png")
    configure_render(hero_path, samples=96, frames=1)
    bpy.ops.render.render(write_still=True)
    print(f"[animate] wrote hero {hero_path}")

    reset_scene()
    obj_orbit = import_glb(profile["__glb"])
    _, size_o = normalize_to_unit(obj_orbit)
    setup_world(mood)
    setup_lights(mood, size_o)
    cam_o = setup_camera(size_o, angle_deg=0, elev_deg=18)
    add_camera_orbit(cam_o, Vector((0, 0, 0)), frames, size_o)
    orbit_path = os.path.join(out_dir, "orbit.mp4")
    configure_render(orbit_path, resolution=720, samples=32, frames=frames, fps=fps)
    bpy.ops.render.render(animation=True)
    print(f"[animate] wrote orbit {orbit_path}")
    meta["orbit"] = orbit_path

    if profile.get("has_animation"):
        reset_scene()
        obj_a = import_glb(profile["__glb"])
        center, size_a = normalize_to_unit(obj_a)
        setup_world(mood)
        setup_lights(mood, size_a)
        cam_a = setup_camera(size_a, angle_deg=30, elev_deg=20)

        for entry in profile.get("animations", []):
            atype = entry.get("type", "")
            params = entry.get("params", {})
            try:
                if atype == "rotate_y":
                    add_keyframe_rotate_y(obj_a, frames, params.get("period_s", 6) * fps)
                    meta["applied"].append(atype)
                elif atype == "hover_float":
                    add_keyframe_hover(obj_a, frames, params.get("amplitude", 0.08), params.get("period_s", 4) * fps)
                    meta["applied"].append(atype)
                elif atype == "shake_vibrate":
                    add_keyframe_shake(obj_a, frames, params.get("amplitude", 0.01), params.get("freq_hz", 12), fps)
                    meta["applied"].append(atype)
                elif atype == "emission_pulse":
                    animate_emission_pulse(obj_a, frames, fps, params.get("freq_hz", 0.3),
                                            params.get("min_strength", 0.4), params.get("max_strength", 3.5))
                    meta["applied"].append(atype)
                elif atype == "volumetric_gas" or atype == "gas_smoke" or atype == "aura_glow":
                    add_volumetric_gas_domain(center, size_a, frames, params.get("density", 2.0))
                    meta["applied"].append(atype)
                elif atype.startswith("particles_"):
                    kind = atype.split("_", 1)[1]
                    make_particle_emitter(center, size_a, kind, params.get("count", 2000), params, frames)
                    meta["applied"].append(atype)
                elif atype == "mechanical_articulate" or atype == "character_motion":
                    prompt = profile.get("prompt_original", "").lower()
                    if "walk" in prompt or "marche" in prompt or atype == "character_motion":
                        if motion_intent_bpy_runner:
                            # Use native aurora system
                            loop = "walk_cycle"
                            if "run" in prompt or "court" in prompt or "course" in prompt:
                                loop = "run_cycle"
                            elif "jump" in prompt or "saute" in prompt:
                                loop = "hover" # Fallback since jump isn't natively supported by rigify locomotion yet
                                
                            intent = {"creature_anim": {"base_loop": loop, "bpm": 14}}
                            res = motion_intent_bpy_runner.bake_creature_organic(intent, bpy.context.scene, fps)
                            if "error" not in res:
                                rig_glb = os.path.join(out_dir, "animated.glb")
                                bpy.ops.export_scene.gltf(filepath=rig_glb, export_format="GLB", export_apply=True, export_animations=True)
                                meta["applied"].append(f"creature_organic({loop})")
                                meta["animated_glb"] = rig_glb
                            else:
                                print(f"[animate] RIGIFY FAILED: {res['error']}")
                                add_keyframe_rotate_y(obj_a, frames, params.get("period_s", 4) * fps)
                                meta["applied"].append("mechanical_articulate(as rotate_y fallback)")
                        else:
                            add_keyframe_rotate_y(obj_a, frames, params.get("period_s", 4) * fps)
                            meta["applied"].append("mechanical_articulate(as rotate_y no-runner)")
                    else:
                        add_keyframe_rotate_y(obj_a, frames, params.get("period_s", 4) * fps)
                        meta["applied"].append("mechanical_articulate(as rotate_y)")
                elif atype == "fluid_flow":
                    obj_a.modifiers.new("Wave", "WAVE")
                    wave = obj_a.modifiers[-1]
                    wave.height = params.get("strength", 0.05)
                    wave.speed = params.get("freq_hz", 1.0) * 0.5
                    meta["applied"].append(atype)
                elif atype == "drift_orbit":
                    add_camera_orbit(cam_a, Vector((0, 0, 0)), frames, size_a * params.get("radius", 0.3))
                    meta["applied"].append(atype)
                elif atype == "beauty_turntable":
                    add_keyframe_rotate_y(obj_a, frames, params.get("period_s", 6) * fps)
                    meta["applied"].append(atype)
                elif atype == "walk_cycle" or atype == "walk":
                    add_keyframe_hover(obj_a, frames, 0.05, 12)  # Visual bobbing for mp4
                    rig_glb = os.path.join(out_dir, "animated.glb")
                    rig_and_walk(obj_a, frames, rig_glb)
                    meta["applied"].append(atype)
                    meta["animated_glb"] = rig_glb
                else:
                    print(f"[animate] unhandled animation type {atype}")
            except Exception as e:
                print(f"[animate] ERR applying {atype}: {e}")
                traceback.print_exc()

        anim_path = os.path.join(out_dir, "animated.mp4")
        configure_render(anim_path, resolution=720, samples=32, frames=frames, fps=fps)
        bpy.ops.render.render(animation=True)
        print(f"[animate] wrote animated {anim_path}")
        meta["animated"] = anim_path

    meta_path = os.path.join(out_dir, "render_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[animate] wrote meta {meta_path}")
    return meta


def main() -> int:
    glb_path, profile_path, out_dir = _parse_args()
    with open(profile_path, encoding="utf-8") as f:
        profile = json.load(f)
    profile["__glb"] = glb_path
    try:
        render_scene(None, profile, out_dir)
    except Exception as e:
        print(f"[animate] FAILED: {e}")
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
