"""mia_walk_apply.py — bake a procedural locomotion cycle onto a MIA-rigged GLB.

Make-It-Animatable rigs a human with a Mixamo skeleton (mixamorig:Hips, ...,
mixamorig:LeftUpLeg, ...) and anatomical skinning weights, but it does NOT apply
any animation. Aurora's `motion_baker` presets target Rigify bone names
(DEF-thigh.L, hand_ik.L, ...) with IK controls, which do not exist on a pure-FK
Mixamo skeleton — so applying them yields ZERO animation ("exported no glTF
animations"). This module bakes a self-contained FK walk cycle DIRECTLY on the
Mixamo bones (arm/forearm/thigh/shin swing in opposite phase + a hip bounce),
which is the proven method (scratchpad/walk_bake.py A/B: MIA + this walk = clean
sleeve, credible gait). Runs headless under Blender, no rendering.

Usage:
  blender -b -P mia_walk_apply.py -- IN.glb OUT.glb [N_FRAMES=36] [SWING_DEG=40] [SPEED_MUL=1.0]
Emits on stdout: MIA_WALK_OK glb=<OUT.glb>  (or MIA_WALK_FAIL: <reason>)
"""
from __future__ import annotations

import math
import sys

import bpy
from mathutils import Vector, Euler

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 2:
    print("MIA_WALK_FAIL: usage IN.glb OUT.glb [frames] [swing] [speed]", flush=True)
    sys.exit(2)
IN_GLB = argv[0]
OUT_GLB = argv[1]
N_FRAMES = max(8, int(float(argv[2]))) if len(argv) > 2 else 36
SWING_DEG = float(argv[3]) if len(argv) > 3 else 40.0
SPEED_MUL = float(argv[4]) if len(argv) > 4 else 1.0

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=IN_GLB)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
if not arms:
    print("MIA_WALK_FAIL: no armature", flush=True)
    sys.exit(3)


def _is_mia(a):
    return any("mixamo" in b.name.lower() for b in a.data.bones)


arm = next((a for a in arms if _is_mia(a)), arms[0])
if not _is_mia(arm):
    print("MIA_WALK_FAIL: armature is not a Mixamo/MIA skeleton", flush=True)
    sys.exit(4)


def find_bone(a, *cands):
    for c in cands:
        if c in a.pose.bones:
            return a.pose.bones[c]
    lc = {b.name.lower().replace("mixamorig:", "").replace("mixamorig", ""): b for b in a.pose.bones}
    for c in cands:
        k = c.lower().replace("mixamorig:", "").replace("mixamorig", "")
        if k in lc:
            return lc[k]
    return None


B_HIPS = find_bone(arm, "mixamorig:Hips", "Hips")
B_L_ARM = find_bone(arm, "mixamorig:LeftArm", "LeftArm")
B_R_ARM = find_bone(arm, "mixamorig:RightArm", "RightArm")
B_L_FA = find_bone(arm, "mixamorig:LeftForeArm", "LeftForeArm")
B_R_FA = find_bone(arm, "mixamorig:RightForeArm", "RightForeArm")
B_L_UPLEG = find_bone(arm, "mixamorig:LeftUpLeg", "LeftUpLeg")
B_R_UPLEG = find_bone(arm, "mixamorig:RightUpLeg", "RightUpLeg")
B_L_LEG = find_bone(arm, "mixamorig:LeftLeg", "LeftLeg")
B_R_LEG = find_bone(arm, "mixamorig:RightLeg", "RightLeg")

if not (B_L_UPLEG and B_R_UPLEG):
    print("MIA_WALK_FAIL: leg bones not found (not a standard Mixamo rig)", flush=True)
    sys.exit(5)

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="POSE")

# Clear any residual action so our euler keys aren't shadowed by quaternion fcurves.
if arm.animation_data and arm.animation_data.action:
    old = arm.animation_data.action
    arm.animation_data.action = None
    try:
        bpy.data.actions.remove(old, do_unlink=True)
    except Exception:
        pass
for b in arm.pose.bones:
    b.rotation_mode = "XYZ"
    b.rotation_euler = Euler((0, 0, 0), "XYZ")
    b.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    b.location = Vector((0, 0, 0))

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = N_FRAMES

SWING = math.radians(SWING_DEG)
LEG_FWD = math.radians(22.0)
LEG_LIFT = math.radians(28.0)
ARM_AXIS, LEG_AXIS = 2, 0   # Mixamo T-pose: arm sagittal swing = local Z, leg = local X
_sign_L, _sign_R = -1.0, +1.0


def _cycle(t, amp, phase=0.0):
    return amp * math.sin(2 * math.pi * (t + phase))


def _eul(axis, val):
    v = [0.0, 0.0, 0.0]
    v[axis] = val
    return Euler(tuple(v), "XYZ")


def _kf(b, f):
    b.keyframe_insert(data_path="rotation_euler", frame=f)
    b.keyframe_insert(data_path="location", frame=f)


for i in range(N_FRAMES):
    t = i / max(1, N_FRAMES)
    scene.frame_set(i + 1)
    swing = _cycle(t, SWING)
    if B_L_ARM:
        B_L_ARM.rotation_euler = _eul(ARM_AXIS, _sign_L * swing); _kf(B_L_ARM, i + 1)
    if B_R_ARM:
        B_R_ARM.rotation_euler = _eul(ARM_AXIS, _sign_R * swing); _kf(B_R_ARM, i + 1)
    fbend = math.radians(10.0) + abs(_cycle(t, math.radians(6.0)))
    if B_L_FA:
        B_L_FA.rotation_euler = _eul(ARM_AXIS, -fbend * _sign_L); _kf(B_L_FA, i + 1)
    if B_R_FA:
        B_R_FA.rotation_euler = _eul(ARM_AXIS, -fbend * _sign_R); _kf(B_R_FA, i + 1)
    if B_L_UPLEG:
        B_L_UPLEG.rotation_euler = _eul(LEG_AXIS, -_cycle(t, LEG_FWD, phase=0.5)); _kf(B_L_UPLEG, i + 1)
    if B_R_UPLEG:
        B_R_UPLEG.rotation_euler = _eul(LEG_AXIS, -_cycle(t, LEG_FWD, phase=0.0)); _kf(B_R_UPLEG, i + 1)
    if B_L_LEG:
        B_L_LEG.rotation_euler = _eul(LEG_AXIS, max(0.0, _cycle(t, LEG_LIFT, phase=0.75))); _kf(B_L_LEG, i + 1)
    if B_R_LEG:
        B_R_LEG.rotation_euler = _eul(LEG_AXIS, max(0.0, _cycle(t, LEG_LIFT, phase=0.25))); _kf(B_R_LEG, i + 1)
    if B_HIPS:
        B_HIPS.location = Vector((0.0, 0.0, 0.02 * math.cos(4 * math.pi * t))); _kf(B_HIPS, i + 1)

bpy.ops.object.mode_set(mode="OBJECT")

bpy.ops.object.select_all(action="DESELECT")
arm.select_set(True)
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.gltf(
    filepath=OUT_GLB, use_selection=True,
    export_animations=True, export_animation_mode="ACTIONS", export_apply=False,
)
print("MIA_WALK_OK glb=%s frames=%d" % (OUT_GLB, N_FRAMES), flush=True)
