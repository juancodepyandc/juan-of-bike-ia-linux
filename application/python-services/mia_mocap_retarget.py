"""mia_mocap_retarget.py — Blender headless: retarget a MoMask BVH onto a
MIA-rigged (Mixamo) GLB and export the animated GLB.

This is the GENUINE motion path (vs a hand-authored procedural walk): the motion
comes from MoMask text-to-motion (any described motion), is retargeted onto the
Mixamo skeleton via retarget_bvh (MakeWalk), and the Mixamo spine over-rotation
is bake-clamped (see mocap_bake_bpy._clamp_mixamo_spine) so the waist doesn't
shatter. Works for walk/run/dance/wave/etc. — whatever MoMask produced.

Usage: blender -b -P mia_mocap_retarget.py -- IN_RIGGED.glb BVH.bvh OUT.glb
Emits: MIA_MOCAP_OK glb=<OUT> frames=<N>  or  MIA_MOCAP_FAIL: <reason>
"""
from __future__ import annotations

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 3:
    print("MIA_MOCAP_FAIL: usage IN.glb BVH OUT.glb", flush=True)
    sys.exit(2)
IN_GLB, BVH, OUT_GLB = argv[0], argv[1], argv[2]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=IN_GLB)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
if not arms:
    print("MIA_MOCAP_FAIL: no armature", flush=True)
    sys.exit(3)
rig = next((a for a in arms if any("mixamo" in b.name.lower() for b in a.data.bones)), arms[0])

# ground z = mesh minimum (world)
ground_z = 0.0
try:
    zs = []
    for m in meshes:
        for c in m.bound_box:
            zs.append((m.matrix_world @ __import__("mathutils").Vector(c)).z)
    ground_z = min(zs) if zs else 0.0
except Exception:
    ground_z = 0.0

try:
    import mocap_bake_bpy as mb
    rep = mb.run_mocap_bake(rig, BVH, [m.name for m in meshes], ground_z,
                            mesh_fallback=meshes[0] if meshes else None)
    print("MIA_MOCAP_STEPS", list(rep.get("steps", {}).keys()), flush=True)
except Exception as e:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    print("MIA_MOCAP_FAIL: retarget exception: %s" % e, flush=True)
    sys.exit(4)

act = rig.animation_data.action if rig.animation_data else None
if act is None:
    print("MIA_MOCAP_FAIL: no action after retarget", flush=True)
    sys.exit(5)
try:
    nf = int(act.frame_range[1] - act.frame_range[0])
except Exception:
    nf = 0

bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")
rig.select_set(True)
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.gltf(filepath=OUT_GLB, use_selection=True,
                          export_animations=True, export_animation_mode="ACTIONS")
print("MIA_MOCAP_OK glb=%s frames=%d" % (OUT_GLB, nf), flush=True)
