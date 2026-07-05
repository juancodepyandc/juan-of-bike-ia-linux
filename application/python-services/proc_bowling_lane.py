"""Procedural bowling lane (Blender headless).

Polished wooden lane with 39 wood-strip planks running lengthwise + 2
gutters on the sides + 10 white pins arranged in the standard triangle
+ a black bowling ball with 3 finger holes. Animation : ball rolls down
the lane toward the pins; once it reaches the front pin, the pins fall
backward (each rotation phased by distance from impact).

CLI:
  python proc_bowling_lane.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "bowling.glb"

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

mat_floor   = pbr_mat("floor",     (0.10, 0.10, 0.12), 0.00, 0.85)
mat_wood    = pbr_mat("wood",      (0.55, 0.32, 0.16), 0.05, 0.20)  # polished
mat_wood_lt = pbr_mat("wood_lt",   (0.72, 0.45, 0.20), 0.05, 0.20)
mat_gutter  = pbr_mat("gutter",    (0.18, 0.18, 0.22), 0.50, 0.30)
mat_pin     = pbr_mat("pin",       (0.95, 0.95, 0.90), 0.05, 0.30)
mat_pin_r   = pbr_mat("pin_red",   (0.85, 0.18, 0.12), 0.10, 0.30)
mat_ball    = pbr_mat("ball",      (0.10, 0.10, 0.12), 0.40, 0.18)
mat_ball_h  = pbr_mat("ball_hole", (0.05, 0.05, 0.06), 0.20, 0.45)

def _box(name, sx, sy, sz, location, mat, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    if rot is not None:
        obj.rotation_euler = rot
    obj.data.materials.append(mat)
    return obj

def _cyl(name, R1, R2, depth, axis, location, mat, segments=14, rot=None):
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
    if rot is not None:
        obj.rotation_euler = rot
    return obj

def _sphere(name, R, location, mat, u=16, v=12):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# Conventions : lane along +Y, pins at +Y end, bowler at -Y. Up = +Z.

# --- floor ---
_box("floor", 2.4, 6.0, 0.04, (0, 0, -0.04), mat_floor)

# Lane dimensions
LANE_W = 1.05
LANE_D = 5.20

# Lane planks : 21 wood strips along Y, alternating dark/light wood
N_PLANKS = 21
PLANK_W = LANE_W / N_PLANKS
for k in range(N_PLANKS):
    px = -LANE_W/2 + (k + 0.5) * PLANK_W
    mat = mat_wood if k % 2 == 0 else mat_wood_lt
    _box(f"plank_{k}", PLANK_W * 0.98, LANE_D, 0.025,
           (px, 0, 0.0125 + 0.04), mat)

# 2 gutters (sunken on either side of the lane)
for sx in (-1, +1):
    _box(f"gutter_{sx}", 0.15, LANE_D, 0.025,
           (sx * (LANE_W/2 + 0.075), 0, 0.005 + 0.04), mat_gutter)
    # gutter inner wall (a small ridge between gutter and lane)
    _box(f"gutter_wall_{sx}", 0.015, LANE_D, 0.020,
           (sx * (LANE_W/2 + 0.015), 0, 0.025 + 0.04), mat_wood)

# Foul line at -Y end (a thin red strip)
_box("foul_line", LANE_W, 0.020, 0.001,
       (0, -LANE_D/2 + 0.20, 0.040), mat_pin_r)

# --- 10 pins in triangle at the +Y end ---
PIN_R_BASE = 0.040
PIN_H = 0.20
PIN_Z = 0.04 + 0.025 + PIN_H/2  # sitting on the lane surface
PIN_FRONT_Y = LANE_D/2 - 0.30  # front pin (head pin)
PIN_SPACING = 0.10
# Standard arrangement : row 1 = 1 pin, row 2 = 2 pins, row 3 = 3 pins, row 4 = 4 pins
pin_positions = []
for row in range(4):
    n = row + 1
    y_off = row * PIN_SPACING * 0.866   # triangle vertical spacing
    for c in range(n):
        x = (c - (n-1)/2) * PIN_SPACING
        y = PIN_FRONT_Y + y_off
        pin_positions.append((x, y))

pin_pivots = []
for i, (px, py) in enumerate(pin_positions):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(px, py, PIN_Z - PIN_H/2))
    pv = bpy.context.active_object
    pv.name = f"pin_pivot_{i}"
    # body : tall pin shape approximated by 3 stacked cylinders of varying radii
    # base (slightly tapered)
    body1 = _cyl(f"pin_{i}_base", PIN_R_BASE, PIN_R_BASE * 0.7, PIN_H * 0.40, 'Z',
                   (0, 0, PIN_H * 0.20), mat_pin, segments=14)
    body1.parent = pv; body1.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # neck (narrow middle)
    body2 = _cyl(f"pin_{i}_neck", PIN_R_BASE * 0.7, PIN_R_BASE * 0.55, PIN_H * 0.30, 'Z',
                   (0, 0, PIN_H * 0.55), mat_pin, segments=14)
    body2.parent = pv; body2.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # head (rounded top)
    body3 = _cyl(f"pin_{i}_head", PIN_R_BASE * 0.55, PIN_R_BASE * 0.85, PIN_H * 0.20, 'Z',
                   (0, 0, PIN_H * 0.80), mat_pin, segments=14)
    body3.parent = pv; body3.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # rounded crown
    crown = _sphere(f"pin_{i}_crown", PIN_R_BASE * 0.55,
                      (0, 0, PIN_H * 0.95), mat_pin)
    crown.parent = pv; crown.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # red stripe ring near top
    stripe = _cyl(f"pin_{i}_stripe", PIN_R_BASE * 0.62, PIN_R_BASE * 0.62, PIN_H * 0.06, 'Z',
                    (0, 0, PIN_H * 0.78), mat_pin_r, segments=14)
    stripe.parent = pv; stripe.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    pin_pivots.append((pv, mathutils.Vector((px, py))))

# --- bowling ball (animated) ---
BALL_R = 0.10
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, -LANE_D/2 + 0.30, BALL_R + 0.065))
ball_pivot = bpy.context.active_object
ball_pivot.name = "ball_pivot"
ball = _sphere("ball", BALL_R, (0, 0, 0), mat_ball, u=20, v=14)
ball.parent = ball_pivot
ball.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 3 finger holes (small dark cylinders on top of the ball)
for k, (hx_off, hy_off) in enumerate([(0, 0), (-0.025, 0.020), (0.025, 0.020)]):
    hole = _cyl(f"ball_hole_{k}", 0.012, 0.012, 0.018, 'Z',
                  (hx_off, hy_off, BALL_R * 0.85),
                  mat_ball_h, segments=10)
    hole.parent = ball_pivot
    hole.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ---
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Ball rolls from start Y to just before the front pin
BALL_START_Y = -LANE_D/2 + 0.30
BALL_HIT_Y = PIN_FRONT_Y - BALL_R - 0.010
ROLL_END_T = 0.55  # ball reaches the pins at this t
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    if t < ROLL_END_T:
        u = t / ROLL_END_T
        # ease-out slightly (rolling friction)
        u_smooth = 1 - (1 - u)**1.5
        y = BALL_START_Y + (BALL_HIT_Y - BALL_START_Y) * u_smooth
        roll_x = -(y - BALL_START_Y) / BALL_R
    else:
        y = BALL_HIT_Y
        roll_x = -(BALL_HIT_Y - BALL_START_Y) / BALL_R
    ball_pivot.location = (0, y, BALL_R + 0.065)
    ball_pivot.rotation_euler = (roll_x, 0, 0)
    ball_pivot.keyframe_insert("location", frame=f)
    ball_pivot.keyframe_insert("rotation_euler", frame=f)
if ball_pivot.animation_data and ball_pivot.animation_data.action:
    for fc in ball_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Pins fall : starting at ROLL_END_T, each pin tips backward (rotates around X)
# with a delay proportional to distance from the impact point (head pin).
IMPACT_POS = mathutils.Vector((0, PIN_FRONT_Y))
for (pv, home) in pin_pivots:
    dist = (home - IMPACT_POS).length
    # delay : front pin falls first, back row last
    delay = dist * 0.30
    fall_start = ROLL_END_T + delay
    fall_end = min(0.95, fall_start + 0.25)
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        if t < fall_start:
            angle = 0.0
        elif t < fall_end:
            u = (t - fall_start) / (fall_end - fall_start)
            # gravity-like ease : u² acceleration
            angle = math.radians(-85) * u * u
        else:
            angle = math.radians(-85)
        pv.rotation_euler = (angle, 0, 0)
        pv.keyframe_insert("rotation_euler", frame=f)
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"BOWL_OK: {out_glb}", flush=True)
'''


def make_bowling(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_bowl_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "BOWL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
        elapsed = round(time.time() - t0, 1)
        if ok:
            return {"ok": True, "glb": out_glb_abs, "elapsed_s": elapsed, "size_bytes": os.path.getsize(out_glb_abs)}
        tail = "\n".join((proc.stdout or "").splitlines()[-30:] + (proc.stderr or "").splitlines()[-30:])
        return {"ok": False, "error": f"Blender exit {proc.returncode}", "log_tail": tail, "elapsed_s": elapsed}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("output", help="output GLB path")
    args = ap.parse_args()
    r = make_bowling(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
