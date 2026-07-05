"""Procedural basketball hoop with ball (Blender headless).

Filled base + tall steel pole + 2 support arms + rectangular plexiglass
backboard + painted rectangle aiming square + orange rim + chain/string
net (12 segments around the rim, each going down + outward) + animated
basketball that arcs through the rim. Animation : ball follows a 3-point
arc from far out to swish through the net + net ripples on impact.

CLI:
  python proc_basketball_hoop.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "basketball.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough, alpha=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if alpha is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
            m.blend_method = 'BLEND'
    return m

mat_floor   = pbr_mat("floor",     (0.55, 0.42, 0.28), 0.00, 0.85)  # asphalt-ish
mat_lines   = pbr_mat("lines",     (0.92, 0.92, 0.88), 0.00, 0.55)
mat_steel   = pbr_mat("steel",     (0.45, 0.45, 0.48), 0.85, 0.30)
mat_dark    = pbr_mat("dark",      (0.08, 0.08, 0.09), 0.40, 0.40)
mat_plexi   = pbr_mat("plexi",     (0.85, 0.92, 0.95), 0.00, 0.10, alpha=0.30)
mat_white   = pbr_mat("white",     (0.95, 0.95, 0.92), 0.00, 0.45)
mat_orange  = pbr_mat("orange",    (0.95, 0.45, 0.10), 0.10, 0.35)
mat_net     = pbr_mat("net",       (0.92, 0.90, 0.85), 0.00, 0.55)
mat_ball    = pbr_mat("ball",      (0.85, 0.45, 0.18), 0.00, 0.55)
mat_ball_ln = pbr_mat("ball_lines",(0.10, 0.06, 0.04), 0.00, 0.55)

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=18, rot=None):
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

def _sphere(name, R, location, mat, u=20, v=14):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

def _torus(name, R_major, R_minor, location, mat, ms=20, mn=8, axis='Z'):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    verts = []
    for i in range(ms):
        ai = 2 * math.pi * i / ms
        ring = []
        for j in range(mn):
            aj = 2 * math.pi * j / mn
            x = (R_major + R_minor * math.cos(aj)) * math.cos(ai)
            y = (R_major + R_minor * math.cos(aj)) * math.sin(ai)
            z = R_minor * math.sin(aj)
            ring.append(bm.verts.new((x, y, z)))
        verts.append(ring)
    bm.verts.ensure_lookup_table()
    for i in range(ms):
        for j in range(mn):
            i2 = (i + 1) % ms
            j2 = (j + 1) % mn
            bm.faces.new([verts[i][j], verts[i2][j], verts[i2][j2], verts[i][j2]])
    if axis == 'X':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'Y'), verts=bm.verts)
    elif axis == 'Y':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'X'), verts=bm.verts)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# Conventions : hoop faces -Y (player shoots from -Y). Up = +Z.

# --- court floor + free-throw line ---
_box("floor", 4.5, 5.0, 0.04, (0, 0, -0.04), mat_floor)
# free-throw line (painted strip)
_box("ft_line", 1.0, 0.05, 0.005, (0, -2.0, 0.001), mat_lines)
# key (painted rectangle)
_box("key_outline_L", 0.04, 4.0, 0.005, (-0.5, -1.0, 0.001), mat_lines)
_box("key_outline_R", 0.04, 4.0, 0.005, ( 0.5, -1.0, 0.001), mat_lines)
_box("key_outline_F", 1.0, 0.04, 0.005, (0, -3.0, 0.001), mat_lines)

# --- base (filled box at the rear) ---
BASE_W = 0.50
BASE_D = 0.40
BASE_H = 0.18
_box("base", BASE_W, BASE_D, BASE_H, (0, 1.10, BASE_H/2 + 0.01), mat_dark)
# 4 wheels (small black cylinders for mobility — typical home hoop)
for sx in (-1, +1):
    for sy in (-1, +1):
        _cyl(f"base_wheel_{sx}_{sy}", 0.030, 0.030, 0.020, 'X',
               (sx * (BASE_W/2 - 0.03), 1.10 + sy * (BASE_D/2 - 0.04), 0.03),
               mat_dark, segments=14)

# --- pole (vertical) ---
POLE_H = 2.50
POLE_X = 0
POLE_Y = 1.10
POLE_BASE_Z = BASE_H + 0.01
_cyl("pole", 0.040, 0.038, POLE_H, 'Z',
       (POLE_X, POLE_Y, POLE_BASE_Z + POLE_H/2), mat_steel, segments=18)

# --- top horizontal arm extending forward toward -Y ---
ARM_LEN = 0.80
ARM_Z = POLE_BASE_Z + POLE_H - 0.20
_cyl("arm_top", 0.030, 0.030, ARM_LEN, 'Y',
       (POLE_X, POLE_Y - ARM_LEN/2 + 0.05, ARM_Z), mat_steel)
# diagonal support brace from mid-pole to the arm
brace_pts = [
    mathutils.Vector((POLE_X, POLE_Y, POLE_BASE_Z + POLE_H * 0.65)),
    mathutils.Vector((POLE_X, POLE_Y - ARM_LEN * 0.7, ARM_Z - 0.02)),
]
d = brace_pts[1] - brace_pts[0]
brace = _cyl("brace", 0.018, 0.018, d.length, 'Z',
               (0,0,0), mat_steel, segments=14)
brace.location = (brace_pts[0] + brace_pts[1]) * 0.5
brace.rotation_mode = 'QUATERNION'
brace.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d.normalized())

# --- backboard (rectangular plexiglass) ---
BB_W = 1.20
BB_H = 0.80
BB_Y = POLE_Y - ARM_LEN + 0.04
BB_Z = ARM_Z + 0.10
BB_T = 0.025
_box("backboard", BB_W, BB_T, BB_H, (0, BB_Y, BB_Z), mat_plexi)
# white frame around the backboard (4 strips)
FRAME_T = 0.012
_box("bb_frame_top", BB_W + 0.02, FRAME_T, FRAME_T,
       (0, BB_Y - 0.001, BB_Z + BB_H/2 + FRAME_T/2), mat_white)
_box("bb_frame_bot", BB_W + 0.02, FRAME_T, FRAME_T,
       (0, BB_Y - 0.001, BB_Z - BB_H/2 - FRAME_T/2), mat_white)
for sx in (-1, +1):
    _box(f"bb_frame_side_{sx}", FRAME_T, FRAME_T, BB_H + FRAME_T * 2,
           (sx * (BB_W/2 + FRAME_T/2), BB_Y - 0.001, BB_Z), mat_white)

# painted aim square (smaller white rectangle on the backboard, above the rim)
SQ_W = 0.40
SQ_H = 0.32
_box("aim_square_top", SQ_W, 0.001, 0.012,
       (0, BB_Y - BB_T/2 - 0.001, BB_Z - 0.08 + SQ_H/2), mat_white)
_box("aim_square_bot", SQ_W, 0.001, 0.012,
       (0, BB_Y - BB_T/2 - 0.001, BB_Z - 0.08 - SQ_H/2), mat_white)
for sx in (-1, +1):
    _box(f"aim_square_side_{sx}", 0.012, 0.001, SQ_H,
           (sx * SQ_W/2, BB_Y - BB_T/2 - 0.001, BB_Z - 0.08), mat_white)

# --- rim (orange torus) hanging forward off the backboard ---
RIM_R = 0.225
RIM_Y = BB_Y - BB_T/2 - RIM_R - 0.04
RIM_Z = BB_Z - 0.08 - SQ_H/2 - 0.08
rim = _torus("rim", RIM_R, 0.012, (0, RIM_Y, RIM_Z), mat_orange,
               ms=24, mn=6, axis='Z')

# bracket connecting rim to backboard (small steel piece)
_box("rim_bracket", 0.06, RIM_R + 0.05, 0.018,
       (0, BB_Y - RIM_R/2 - 0.015, RIM_Z + 0.005), mat_orange)

# --- net : 12 segments from the rim going down + slightly outward ---
N_NET = 12
NET_DEPTH = 0.40
for i in range(N_NET):
    a = 2*math.pi * i / N_NET
    rx = RIM_R * math.cos(a)
    ry = RIM_Y + RIM_R * math.sin(a)
    # outer pt at top + slightly contracted at bottom
    p0 = mathutils.Vector((rx, ry, RIM_Z - 0.005))
    p1 = mathutils.Vector((rx * 0.70, RIM_Y + (ry - RIM_Y) * 0.70, RIM_Z - NET_DEPTH))
    d = p1 - p0
    midp = (p0 + p1) * 0.5
    seg = _cyl(f"net_{i}", 0.0035, 0.0035, d.length, 'Z',
                 (0,0,0), mat_net, segments=6)
    seg.location = midp
    direction = d.normalized()
    seg.rotation_mode = 'QUATERNION'
    seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
# 2 horizontal binding rings (small torus on top + bottom of the net)
_torus("net_ring_top", RIM_R * 0.98, 0.003, (0, RIM_Y, RIM_Z - 0.012),
         mat_net, ms=20, mn=6, axis='Z')
_torus("net_ring_bot", RIM_R * 0.72, 0.003,
         (0, RIM_Y, RIM_Z - NET_DEPTH + 0.005),
         mat_net, ms=16, mn=6, axis='Z')

# --- basketball (animated, parented to a pivot empty) ---
BALL_R = 0.12
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, -2.0, 1.5))
ball_pivot = bpy.context.active_object
ball_pivot.name = "ball_pivot"
ball = _sphere("ball", BALL_R, (0, 0, 0), mat_ball)
ball.parent = ball_pivot
ball.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 4 dark lines on the ball (3 vertical hoops + 1 horizontal seam approximation)
for ang in (0, math.pi/2, math.pi/4, 3*math.pi/4):
    ln = _box(f"ball_line_{ang:.2f}", 0.002, 0.002, BALL_R * 2,
                (0, 0, 0), mat_ball_ln,
                rot=(0, ang, 0))
    ln.parent = ball_pivot
    ln.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# equator
ln_eq = _box("ball_line_eq", BALL_R * 2, 0.002, 0.002, (0, 0, 0), mat_ball_ln)
ln_eq.parent = ball_pivot
ln_eq.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation -----------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Ball trajectory : Bezier from far-out start to the rim, then drops
# straight down through the net, then ends below.
BALL_START = mathutils.Vector((0, -2.5, 1.6))   # player's hand
BALL_TOP   = mathutils.Vector((0, -1.5, 3.4))   # peak of the arc
BALL_RIM   = mathutils.Vector((0, RIM_Y, RIM_Z + 0.02))   # entering the rim
BALL_END   = mathutils.Vector((0, RIM_Y, RIM_Z - NET_DEPTH - 0.05))   # exited the net

def bezier_quadratic(P0, P1, P2, t):
    u = 1.0 - t
    return u*u*P0 + 2*u*t*P1 + t*t*P2

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    if t < 0.65:
        # arc from start to rim
        u = t / 0.65
        pos = bezier_quadratic(BALL_START, BALL_TOP, BALL_RIM, u)
    elif t < 0.85:
        # drop through the net
        u = (t - 0.65) / 0.20
        # ease-in (gravity acceleration)
        u = u * u
        pos = BALL_RIM.lerp(BALL_END, u)
    else:
        pos = BALL_END
    ball_pivot.location = (pos.x, pos.y, pos.z)
    # rotation : spin around X axis (forward roll feel)
    ball_pivot.rotation_euler = (2*math.pi * 2 * t, 0, 0.4 * math.sin(2*math.pi*t * 4))
    ball_pivot.keyframe_insert("location", frame=f)
    ball_pivot.keyframe_insert("rotation_euler", frame=f)
if ball_pivot.animation_data and ball_pivot.animation_data.action:
    for fc in ball_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"HOOP_OK: {out_glb}", flush=True)
'''


def make_hoop(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_hoop_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "HOOP_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_hoop(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
