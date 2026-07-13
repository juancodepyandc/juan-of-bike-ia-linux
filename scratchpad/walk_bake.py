"""walk_bake.py — Blender headless: apply a procedural walk to a MIA-rigged GLB
and render Cycles profile frames.

Design principles (per pipeline-deformation-3d memory):
  1. Skin='keep' — do NOT re-bind, do NOT add Corrective Smooth (produces speckling).
  2. Input GLB is at scale ~1 (FBX2glTF native), so DO NOT apply parent transforms —
     that would break the Armature-modifier bind and shatter the mesh.
  3. The rig is a Mixamo 52-bone skeleton (mixamorig:Hips, mixamorig:Spine,
     mixamorig:LeftShoulder, mixamorig:LeftArm, mixamorig:LeftForeArm, ...,
     with 30 finger bones). Arm swing bones = mixamorig:LeftArm / mixamorig:RightArm
     (upper arm), which is the correct target for the "manche" defect (arm bone
     rotation drives sleeve/shoulder skinning).

Usage:
  blender --background --python walk_bake.py -- \
      <input.glb> <output_dir> <label> [n_frames=8] [swing_deg=45]

Emits:
  <output_dir>/<label>_frame_00.png .. _frame_NN.png
  <output_dir>/<label>_animated.glb        (with baked walk action)
"""
from __future__ import annotations

import math
import os
import sys
from typing import Sequence

import bpy
from mathutils import Vector, Euler


# --------------------------- CLI ---------------------------
argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
else:
    argv = []
if len(argv) < 3:
    print("USAGE: blender -b -P walk_bake.py -- IN.glb OUT_DIR LABEL [FRAMES=8] [SWING=45]", flush=True)
    sys.exit(2)

INPUT_GLB = argv[0]
OUT_DIR = argv[1]
LABEL = argv[2]
N_FRAMES = int(argv[3]) if len(argv) > 3 else 8
SWING_DEG = float(argv[4]) if len(argv) > 4 else 45.0
os.makedirs(OUT_DIR, exist_ok=True)


# --------------------------- Scene reset ---------------------------
bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.mode != "OBJECT" else None
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False, confirm=False)


# --------------------------- Import GLB ---------------------------
print(f"[walk_bake] importing {INPUT_GLB}", flush=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
if not meshes:
    raise SystemExit("WALK_ERROR: no mesh in GLB")
if not arms:
    raise SystemExit("WALK_ERROR: no armature in GLB")

# There should be exactly ONE armature (the MIA one). If more, pick the one
# with a bone containing "mixamorig".
def _is_mia_rig(a) -> bool:
    return any("mixamo" in b.name.lower() for b in a.data.bones)

mia_arms = [a for a in arms if _is_mia_rig(a)]
if mia_arms:
    arm = mia_arms[0]
else:
    arm = arms[0]
print(f"[walk_bake] using armature: {arm.name} ({len(arm.data.bones)} bones)", flush=True)

# Scale check — GOTCHA 2: never transform_apply on a scale=1 rig
scale_vec = arm.matrix_world.to_scale()
print(f"[walk_bake] armature scale={scale_vec} (should be 1,1,1 for FBX2glTF native)", flush=True)


# --------------------------- Bone lookup ---------------------------
# MIA bone names have the prefix "mixamorig:" (some importers strip the colon).
# Handle both "mixamorig:LeftArm" and "mixamorigLeftArm" and pure "LeftArm".
def find_bone(arm_obj, *candidates):
    for c in candidates:
        if c in arm_obj.pose.bones:
            return arm_obj.pose.bones[c]
    # Loose match: strip prefix + case-insensitive
    lc = {b.name.lower().replace("mixamorig:", "").replace("mixamorig", ""): b for b in arm_obj.pose.bones}
    for c in candidates:
        key = c.lower().replace("mixamorig:", "").replace("mixamorig", "")
        if key in lc:
            return lc[key]
    return None


# Skeleton kind: MIA/Mixamo uses "mixamorig:LeftArm" style; Rigify uses "upper_arm_fk.L"
_rig_kind = "mia" if any(b.name.startswith("mixamorig") for b in arm.data.bones) else "rigify"
print(f"[walk_bake] detected rig kind: {_rig_kind}", flush=True)

if _rig_kind == "mia":
    BONE_HIPS = find_bone(arm, "mixamorig:Hips", "mixamorigHips", "Hips")
    BONE_SPINE = find_bone(arm, "mixamorig:Spine", "mixamorigSpine", "Spine")
    BONE_L_ARM = find_bone(arm, "mixamorig:LeftArm", "mixamorigLeftArm", "LeftArm")
    BONE_R_ARM = find_bone(arm, "mixamorig:RightArm", "mixamorigRightArm", "RightArm")
    BONE_L_FOREARM = find_bone(arm, "mixamorig:LeftForeArm", "mixamorigLeftForeArm", "LeftForeArm")
    BONE_R_FOREARM = find_bone(arm, "mixamorig:RightForeArm", "mixamorigRightForeArm", "RightForeArm")
    BONE_L_UPLEG = find_bone(arm, "mixamorig:LeftUpLeg", "mixamorigLeftUpLeg", "LeftUpLeg")
    BONE_R_UPLEG = find_bone(arm, "mixamorig:RightUpLeg", "mixamorigRightUpLeg", "RightUpLeg")
    BONE_L_LEG = find_bone(arm, "mixamorig:LeftLeg", "mixamorigLeftLeg", "LeftLeg")
    BONE_R_LEG = find_bone(arm, "mixamorig:RightLeg", "mixamorigRightLeg", "RightLeg")
else:  # rigify
    # This particular Rigify rig has NO constraint chain on DEF bones (checked:
    # both ORG-upper_arm.L and DEF-upper_arm.L have zero constraints). The FK
    # bones therefore drive nothing. Rotate the DEF bones directly since those
    # are what own the vertex weights.
    BONE_HIPS = find_bone(arm, "DEF-spine", "hips", "torso")
    BONE_SPINE = find_bone(arm, "DEF-spine.001", "spine_fk", "spine")
    BONE_L_ARM = find_bone(arm, "DEF-upper_arm.L", "upper_arm_fk.L", "upper_arm.L")
    BONE_R_ARM = find_bone(arm, "DEF-upper_arm.R", "upper_arm_fk.R", "upper_arm.R")
    BONE_L_FOREARM = find_bone(arm, "DEF-forearm.L", "forearm_fk.L", "forearm.L")
    BONE_R_FOREARM = find_bone(arm, "DEF-forearm.R", "forearm_fk.R", "forearm.R")
    BONE_L_UPLEG = find_bone(arm, "DEF-thigh.L", "thigh_fk.L", "thigh.L")
    BONE_R_UPLEG = find_bone(arm, "DEF-thigh.R", "thigh_fk.R", "thigh.R")
    BONE_L_LEG = find_bone(arm, "DEF-shin.L", "shin_fk.L", "shin.L")
    BONE_R_LEG = find_bone(arm, "DEF-shin.R", "shin_fk.R", "shin.R")

for label, b in (
    ("Hips", BONE_HIPS),
    ("Spine", BONE_SPINE),
    ("L Arm", BONE_L_ARM),
    ("R Arm", BONE_R_ARM),
    ("L UpLeg", BONE_L_UPLEG),
    ("R UpLeg", BONE_R_UPLEG),
):
    print(f"[walk_bake] bone {label}: {b.name if b else 'NOT FOUND'}", flush=True)

if not (BONE_L_ARM and BONE_R_ARM):
    print("[walk_bake] WARNING: arm bones not found — walk animation will have NO arm swing.", flush=True)


# --------------------------- Author walk keyframes ---------------------------
# We author matrix_basis rotations directly (no NLA, no action mixing). The MIA
# rest pose is A-pose forced to T-pose (reset_to_rest=1), so:
#   - LeftArm rest = pointing along +X (left, world)
#   - RightArm rest = pointing along -X (right, world)
# In a Mixamo rig, the LOCAL X axis of an arm bone runs along the bone. Rotating
# the upper arm bone around its LOCAL Z axis lifts/lowers it in the frontal
# plane; rotating around its LOCAL X axis rolls the arm; rotating around LOCAL
# Y axis swings forward/backward. In the T-pose rest, we want a SAGITTAL swing
# (forward/back around the shoulder) — that's local Y in Mixamo convention.

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="POSE")

# Nuke any pre-existing action on the armature. The humain_final_materials.glb
# already ships with a 36-frame Rigify walk baked in (rotation_quaternion fcurves
# on hundreds of bones); if we don't clear it, our keyframes on rotation_euler
# are shadowed by the existing quaternion action.
if arm.animation_data is not None and arm.animation_data.action is not None:
    old = arm.animation_data.action
    print(f"[walk_bake] clearing pre-existing action '{old.name}' ({len(old.fcurves)} fcurves)", flush=True)
    arm.animation_data.action = None
    try:
        bpy.data.actions.remove(old, do_unlink=True)
    except Exception:
        pass
# Reset every pose bone to identity so residuals don't fight our animation
for b in arm.pose.bones:
    b.rotation_mode = "XYZ"
    b.rotation_euler = Euler((0, 0, 0), "XYZ")
    b.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    b.location = Vector((0, 0, 0))

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = N_FRAMES

SWING_RAD = math.radians(SWING_DEG)
LEG_LIFT_RAD = math.radians(28.0)
LEG_FWD_RAD = math.radians(22.0)


def _lerp(a, b, t):
    return a + (b - a) * t


def _cycle(t: float, amp: float, phase: float = 0.0) -> float:
    """Sinusoidal cycle: t in [0,1) → [-amp, +amp]."""
    return amp * math.sin(2 * math.pi * (t + phase))


def _clear_all_pose():
    for b in arm.pose.bones:
        b.rotation_mode = "XYZ"
        b.rotation_euler = Euler((0, 0, 0), "XYZ")
        b.location = Vector((0, 0, 0))


def _set_arm_swing(b, angle_deg: float, axis: str = "Z"):
    """Sagittal swing of the upper arm.
    We rotate around the bone's local Z (forward/backward in the frontal plane when
    the arm is along X). For a T-pose arm along +X, positive Z rotation swings the
    arm forward (into +Y in world). We use the -Z side to swing backward. Sign is
    mirrored between left and right so a positive `angle_deg` means "left arm
    swings forward".
    """
    b.rotation_mode = "XYZ"
    r = math.radians(angle_deg)
    if axis == "Z":
        b.rotation_euler = Euler((0, 0, r), "XYZ")
    elif axis == "Y":
        b.rotation_euler = Euler((0, r, 0), "XYZ")
    else:
        b.rotation_euler = Euler((r, 0, 0), "XYZ")


def _keyframe_bone(b, frame: int):
    b.keyframe_insert(data_path="rotation_euler", frame=frame)
    b.keyframe_insert(data_path="location", frame=frame)


# We build a 1-cycle walk over N_FRAMES frames. Each frame is a distinct pose in
# the cycle (t=i/N). The Mixamo T-pose arms extend horizontally; a sagittal swing
# in the walking plane is a rotation around the bone's LOCAL Y-axis when the arm
# is aligned with world X. But Mixamo bone axes vary — safer: try Y first, fall
# back to Z, and let the render tell us which one moves.
#
# Empirically for a Mixamo T-pose skeleton with arm bone rolls at default:
#   L/R Upper arm sagittal swing ≈ rotation around LOCAL Z axis (negative for
#   forward on the left side, positive forward on right).
#
# We compute a symmetric swing: at t=0 left arm forward, right arm back; at
# t=0.5 the reverse; at t=1.0 back to start.

# Which local axis of the upper arm drives sagittal swing:
#   MIA/Mixamo T-pose arm along +X world → local Z rotates arm in sagittal plane
#   Rigify A-pose arm along -Y world (down) → local X rotates arm in sagittal plane
if _rig_kind == "mia":
    ARM_AXIS = 2   # Z
    LEG_AXIS = 0   # X
    _sign_L, _sign_R = -1.0, +1.0
else:
    ARM_AXIS = 0   # X
    LEG_AXIS = 0   # X
    _sign_L, _sign_R = +1.0, -1.0

def _euler_for_axis(axis: int, val: float) -> Euler:
    v = [0.0, 0.0, 0.0]
    v[axis] = val
    return Euler(tuple(v), "XYZ")

for i in range(N_FRAMES):
    t = i / max(1, N_FRAMES)
    scene.frame_set(i + 1)
    swing = _cycle(t, SWING_RAD)

    # Arms: sagittal swing
    if BONE_L_ARM:
        BONE_L_ARM.rotation_mode = "XYZ"
        BONE_L_ARM.rotation_euler = _euler_for_axis(ARM_AXIS, _sign_L * swing)
        _keyframe_bone(BONE_L_ARM, i + 1)
    if BONE_R_ARM:
        BONE_R_ARM.rotation_mode = "XYZ"
        BONE_R_ARM.rotation_euler = _euler_for_axis(ARM_AXIS, _sign_R * swing)
        _keyframe_bone(BONE_R_ARM, i + 1)

    # Forearms: modest bend (natural walk carry)
    fbend = math.radians(10.0) + abs(_cycle(t, math.radians(6.0)))
    if BONE_L_FOREARM:
        BONE_L_FOREARM.rotation_mode = "XYZ"
        BONE_L_FOREARM.rotation_euler = _euler_for_axis(ARM_AXIS, -fbend * _sign_L)
        _keyframe_bone(BONE_L_FOREARM, i + 1)
    if BONE_R_FOREARM:
        BONE_R_FOREARM.rotation_mode = "XYZ"
        BONE_R_FOREARM.rotation_euler = _euler_for_axis(ARM_AXIS, -fbend * _sign_R)
        _keyframe_bone(BONE_R_FOREARM, i + 1)

    # Legs: opposite phase to arms (left arm forward + right leg forward)
    if BONE_L_UPLEG:
        BONE_L_UPLEG.rotation_mode = "XYZ"
        leg = _cycle(t, LEG_FWD_RAD, phase=0.5)
        BONE_L_UPLEG.rotation_euler = _euler_for_axis(LEG_AXIS, -leg)
        _keyframe_bone(BONE_L_UPLEG, i + 1)
    if BONE_R_UPLEG:
        BONE_R_UPLEG.rotation_mode = "XYZ"
        leg = _cycle(t, LEG_FWD_RAD, phase=0.0)
        BONE_R_UPLEG.rotation_euler = _euler_for_axis(LEG_AXIS, -leg)
        _keyframe_bone(BONE_R_UPLEG, i + 1)

    if BONE_L_LEG:
        BONE_L_LEG.rotation_mode = "XYZ"
        bend = max(0.0, _cycle(t, LEG_LIFT_RAD, phase=0.75))
        BONE_L_LEG.rotation_euler = _euler_for_axis(LEG_AXIS, bend)
        _keyframe_bone(BONE_L_LEG, i + 1)
    if BONE_R_LEG:
        BONE_R_LEG.rotation_mode = "XYZ"
        bend = max(0.0, _cycle(t, LEG_LIFT_RAD, phase=0.25))
        BONE_R_LEG.rotation_euler = _euler_for_axis(LEG_AXIS, bend)
        _keyframe_bone(BONE_R_LEG, i + 1)

    # Hip vertical bounce
    if BONE_HIPS:
        BONE_HIPS.rotation_mode = "XYZ"
        BONE_HIPS.location = Vector((0.0, 0.0, 0.02 * math.cos(4 * math.pi * t)))
        _keyframe_bone(BONE_HIPS, i + 1)


bpy.ops.object.mode_set(mode="OBJECT")


# --------------------------- Camera (profile) ---------------------------
# 90° side view — camera along +X, looking at the character (facing -Y).
# For a Mixamo rig, the character usually faces +Z after MIA. We compute bbox
# from the mesh(es) to get a robust framing.
# Recompute bbox at frame 1 (some rigs have shape keys / drivers that shift bounds)
scene.frame_set(1)
bpy.context.view_layer.update()
bbox_min = Vector((1e9, 1e9, 1e9))
bbox_max = Vector((-1e9, -1e9, -1e9))
for m in meshes:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    m_eval = m.evaluated_get(depsgraph)
    for corner in m_eval.bound_box:
        wp = m.matrix_world @ Vector(corner)
        for i in range(3):
            bbox_min[i] = min(bbox_min[i], wp[i])
            bbox_max[i] = max(bbox_max[i], wp[i])
center = (bbox_min + bbox_max) / 2
size = bbox_max - bbox_min
print(f"[walk_bake] bbox min={bbox_min} max={bbox_max} size={size}", flush=True)

# For consistent comparison across rigs (Rigify height ~1.75, MIA normalized ~2.0),
# use a fixed camera distance scaled by the tallest dimension.
H = max(size.z, size.x, size.y)
CAM_DIST = H * 2.4
cam_data = bpy.data.cameras.new("ProfileCam")
cam_data.lens = 50.0
cam = bpy.data.objects.new("ProfileCam", cam_data)
bpy.context.scene.collection.objects.link(cam)
# Position: +X of the character, at mid-height
cam.location = Vector((center.x + CAM_DIST, center.y, center.z))
# Point at center
direction = (center - cam.location).normalized()
cam.rotation_mode = "XYZ"
# Use track_to via matrix
up = Vector((0, 0, 1))
right = direction.cross(up).normalized()
new_up = right.cross(direction).normalized()
import mathutils

mat = mathutils.Matrix((
    (right.x, new_up.x, -direction.x, cam.location.x),
    (right.y, new_up.y, -direction.y, cam.location.y),
    (right.z, new_up.z, -direction.z, cam.location.z),
    (0, 0, 0, 1),
))
cam.matrix_world = mat
scene.camera = cam
print(f"[walk_bake] camera at {cam.location} looking at {center}", flush=True)


# --------------------------- Ground plane ---------------------------
bpy.ops.mesh.primitive_plane_add(size=max(size.x, size.y) * 6, location=(center.x, center.y, bbox_min.z - 0.001))
ground = bpy.context.object
ground.name = "GroundPlane"
mat_g = bpy.data.materials.new("Ground")
mat_g.use_nodes = True
bsdf = mat_g.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.55, 0.53, 0.50, 1.0)
bsdf.inputs["Roughness"].default_value = 0.85
ground.data.materials.append(mat_g)


# --------------------------- Lighting ---------------------------
# Three-point rig
def add_light(name, kind, energy, loc, rot):
    ld = bpy.data.lights.new(name, kind)
    if kind == "SUN":
        ld.energy = energy
        ld.angle = math.radians(2.0)
    else:
        ld.energy = energy
    lo = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(lo)
    lo.location = Vector(loc)
    lo.rotation_euler = Euler(rot, "XYZ")
    return lo


add_light("KeySun", "SUN", 3.0, (center.x + 1.5, center.y - 1.5, center.z + 2.5), (math.radians(50), math.radians(-25), math.radians(30)))
add_light("Fill", "AREA", 200.0, (center.x - 1.0, center.y + 2.0, center.z + 0.5), (math.radians(60), math.radians(15), 0))

# World: neutral grey
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg is not None:
    bg.inputs[0].default_value = (0.62, 0.66, 0.72, 1.0)
    bg.inputs[1].default_value = 1.2


# --------------------------- Cycles settings ---------------------------
scene.render.engine = "CYCLES"
scene.cycles.device = "GPU"
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "CUDA"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = ("CUDA" in d.type) or (d.type == "CPU")
except Exception as e:
    print(f"[walk_bake] cycles device setup: {e}", flush=True)
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.resolution_x = 720
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "Filmic"


# --------------------------- Render loop ---------------------------
for i in range(N_FRAMES):
    scene.frame_set(i + 1)
    out = os.path.join(OUT_DIR, f"{LABEL}_frame_{i:02d}.png")
    scene.render.filepath = out
    print(f"[walk_bake] rendering frame {i+1}/{N_FRAMES} -> {out}", flush=True)
    bpy.ops.render.render(write_still=True)


# --------------------------- Export animated GLB ---------------------------
out_glb = os.path.join(OUT_DIR, f"{LABEL}_animated.glb")
# Select the armature + all meshes for export
bpy.ops.object.select_all(action="DESELECT")
arm.select_set(True)
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.gltf(
    filepath=out_glb,
    use_selection=True,
    export_animations=True,
    export_animation_mode="ACTIONS",
    export_apply=False,
)
print(f"WALK_OK glb={out_glb}", flush=True)
