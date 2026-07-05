"""Procedural grandfather clock with pendulum + hands (Blender headless).

Wooden case + clock face with 12 hour-markers + hour and minute hands +
pendulum (rod + brass bob) oscillating below. Animation : pendulum
swings, minute hand spins one full turn per loop, hour hand spins
1/12th of a turn per loop.

CLI:
  python proc_pendulum_clock.py <output_glb>
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_APP = _HERE.parent


def _find_blender() -> str | None:
    for sub in (_APP / "_blender").glob("blender-*-windows-x64"):
        exe = sub / "blender.exe"
        if exe.is_file():
            return str(exe)
    return shutil.which("blender")


_BLENDER_SCRIPT = r'''
import bpy, bmesh, math, mathutils, sys

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "clock.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
    return m

mat_wood     = pbr_mat("wood_case",  (0.32, 0.18, 0.08), 0.00, 0.60)
mat_wood_lt  = pbr_mat("wood_light", (0.55, 0.38, 0.20), 0.00, 0.55)
mat_face     = pbr_mat("face_cream", (0.92, 0.88, 0.78), 0.00, 0.55)
mat_hand     = pbr_mat("hand_black", (0.05, 0.05, 0.07), 0.20, 0.45)
mat_brass    = pbr_mat("brass",      (0.86, 0.62, 0.20), 1.00, 0.28)
mat_glass    = pbr_mat("dial_glass", (0.85, 0.86, 0.90), 0.00, 0.05)
# translucent glass
_bsdf = mat_glass.node_tree.nodes.get("Principled BSDF")
if _bsdf and "Alpha" in _bsdf.inputs:
    _bsdf.inputs["Alpha"].default_value = 0.30
mat_glass.blend_method = 'BLEND'
mat_marker   = pbr_mat("marker_black",(0.05, 0.05, 0.07), 0.10, 0.40)

def _cyl(name, R1, R2, depth, axis, location, mat, segments=32):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                            radius1=R1, radius2=R2, depth=depth)
    if axis == 'X':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'Y'), verts=bm.verts)
    elif axis == 'Y':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'X'), verts=bm.verts)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

# --- main case ---------------------------------------------------------
# Tall rectangular case + base + pediment (roof)
CASE_W = 0.55
CASE_D = 0.25
CASE_H = 1.80   # total height
BASE_H = 0.18

# base block
_box("base", CASE_W * 1.05, CASE_D * 1.1, BASE_H,
       (0, 0, BASE_H/2), mat_wood)

# main body (single back panel + 2 side panels + 1 front rail)
BODY_Z = BASE_H + (CASE_H - BASE_H - 0.20) / 2
BODY_H = CASE_H - BASE_H - 0.20

# back panel
_box("back_panel", CASE_W, 0.04, BODY_H,
       (0, -CASE_D/2 + 0.02, BODY_Z), mat_wood)
# left + right sides
for sx in (-1, 1):
    _box(f"side_{sx}", 0.04, CASE_D, BODY_H,
           (sx * (CASE_W/2 - 0.02), 0, BODY_Z), mat_wood)
# top + bottom of the body
_box("body_top", CASE_W, CASE_D, 0.04,
       (0, 0, BODY_Z + BODY_H/2 + 0.02), mat_wood_lt)
_box("body_bottom", CASE_W, CASE_D, 0.04,
       (0, 0, BODY_Z - BODY_H/2 - 0.02), mat_wood_lt)

# pediment (sloped roof)
_box("pediment_box", CASE_W * 1.05, CASE_D * 1.1, 0.10,
       (0, 0, CASE_H - 0.05), mat_wood_lt)

# decorative finial on top centre
_cyl("finial_post", 0.025, 0.015, 0.10, 'Z',
       (0, 0, CASE_H + 0.05), mat_brass)
mesh_ball = bpy.data.meshes.new("finial_ball")
ball = bpy.data.objects.new("finial_ball", mesh_ball)
bpy.context.collection.objects.link(ball)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=0.035)
bm.to_mesh(mesh_ball); bm.free()
ball.location = (0, 0, CASE_H + 0.13)
ball.data.materials.append(mat_brass)

# --- clock face (disc near the top of the body) ----------------------
FACE_Z = CASE_H - 0.40
FACE_R = 0.20

face = _cyl("face_disc", FACE_R, FACE_R, 0.015, 'Y',
              (0, -CASE_D/2 + 0.04, FACE_Z), mat_face)

# face frame (thin brass ring around it)
frame_ring = _cyl("face_frame", FACE_R * 1.08, FACE_R * 1.08, 0.025, 'Y',
                    (0, -CASE_D/2 + 0.06, FACE_Z), mat_brass)

# 12 hour markers
for k in range(12):
    a = k * math.pi / 6  # 0, 30, 60, ...
    mx = math.sin(a) * FACE_R * 0.85
    mz = math.cos(a) * FACE_R * 0.85
    _box(f"marker_{k}", 0.012, 0.018, 0.025,
           (mx, -CASE_D/2 + 0.05, FACE_Z + mz), mat_marker)
    # also need to position the marker correctly... wait the marker box
    # extends along Y (depth) by 0.018, but we want it to PROTRUDE from the face.
    # Actually box centred at (mx, -CASE_D/2 + 0.05, FACE_Z + mz) with scale
    # (0.012, 0.018, 0.025) -> box of width 0.012 (X), 0.018 (Y), 0.025 (Z).
    # That's a thin tall box. Need to rotate it tangentially to face the centre.
    obj = bpy.context.active_object
    obj.rotation_euler = (0, a, 0)

# --- clock hands (parented to a face-front pivot) ---------------------
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(0, -CASE_D/2 + 0.075, FACE_Z))
hands_pivot = bpy.context.active_object
hands_pivot.name = "hands_pivot"
# rotate the pivot so its local Z points along world -Y (out of the face)
hands_pivot.rotation_euler = (math.pi/2, 0, 0)

# minute hand : long thin box
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
min_pivot_obj = bpy.context.active_object
min_pivot_obj.name = "minute_hand_pivot"
min_pivot_obj.parent = hands_pivot
min_pivot_obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# rotate around its local Z axis (which is now along world -Y, i.e. coming out
# of the face).
min_pivot_obj.scale = (1, 1, 1)
bpy.ops.object.transform_apply(scale=True)
# Make it act as an Empty by clearing its mesh visual ... actually just rename
# and use as a parent group.
min_pivot_obj.hide_render = True
# instead build the minute-hand box itself as a child :
min_hand = _box("minute_hand", FACE_R * 0.90, 0.012, 0.010, (0, 0, 0), mat_hand)
min_hand.parent = min_pivot_obj
min_hand.matrix_parent_inverse = mathutils.Matrix.Identity(4)
min_hand.location = (FACE_R * 0.45, 0, 0)

# hour hand : shorter, thicker
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
hour_pivot_obj = bpy.context.active_object
hour_pivot_obj.name = "hour_hand_pivot"
hour_pivot_obj.parent = hands_pivot
hour_pivot_obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
hour_hand = _box("hour_hand", FACE_R * 0.60, 0.018, 0.012, (0, 0, 0), mat_hand)
hour_hand.parent = hour_pivot_obj
hour_hand.matrix_parent_inverse = mathutils.Matrix.Identity(4)
hour_hand.location = (FACE_R * 0.30, 0, 0)

# small central pin
_cyl("center_pin", 0.02, 0.02, 0.04, 'Y',
       (0, -CASE_D/2 + 0.10, FACE_Z), mat_brass)

# --- pendulum ---------------------------------------------------------
PEND_PIVOT_Z = FACE_Z - 0.30
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(0, -CASE_D/2 + 0.04, PEND_PIVOT_Z))
pend_pivot = bpy.context.active_object
pend_pivot.name = "pendulum_pivot"

pend_rod = _box("pendulum_rod", 0.012, 0.025, 0.70, (0, 0, 0), mat_brass)
pend_rod.parent = pend_pivot
pend_rod.matrix_parent_inverse = mathutils.Matrix.Identity(4)
pend_rod.location = (0, 0, -0.35)   # hangs down

pend_bob = _cyl("pendulum_bob", 0.07, 0.07, 0.035, 'Y',
                  (0, 0, 0), mat_brass)
pend_bob.parent = pend_pivot
pend_bob.matrix_parent_inverse = mathutils.Matrix.Identity(4)
pend_bob.location = (0, 0, -0.70)

# --- animation -------------------------------------------------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Pendulum : +/- 12 deg around Y (so it swings in the XZ plane, in front of
# the case)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    pend_pivot.rotation_euler = (0, math.sin(2*math.pi*t) * math.radians(12), 0)
    pend_pivot.keyframe_insert("rotation_euler", frame=f)
if pend_pivot.animation_data and pend_pivot.animation_data.action:
    for fc in pend_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Minute hand : 1 full turn per loop around local Z (which is world -Y after
# the hands_pivot rotation)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    min_pivot_obj.rotation_euler = (0, 0, -2 * math.pi * t)  # clockwise
    min_pivot_obj.keyframe_insert("rotation_euler", frame=f)
if min_pivot_obj.animation_data and min_pivot_obj.animation_data.action:
    for fc in min_pivot_obj.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Hour hand : 1/12 of a turn per loop
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    hour_pivot_obj.rotation_euler = (0, 0, -2 * math.pi * t / 12)
    hour_pivot_obj.keyframe_insert("rotation_euler", frame=f)
if hour_pivot_obj.animation_data and hour_pivot_obj.animation_data.action:
    for fc in hour_pivot_obj.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"CLOCK_OK: {out_glb}", flush=True)
'''


def make_clock(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_clock_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "CLOCK_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
        elapsed = round(time.time() - t0, 1)
        if ok:
            return {"ok": True, "glb": out_glb_abs, "elapsed_s": elapsed, "size_bytes": os.path.getsize(out_glb_abs)}
        tail = "\n".join((proc.stdout or "").splitlines()[-20:] + (proc.stderr or "").splitlines()[-20:])
        return {"ok": False, "error": f"Blender exit {proc.returncode}", "log_tail": tail, "elapsed_s": elapsed}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("output", help="output GLB path")
    args = ap.parse_args()
    r = make_clock(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
