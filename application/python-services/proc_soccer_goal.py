"""Procedural soccer goal with ball (Blender headless).

2 vertical white posts + horizontal crossbar + back / side frame +
back-net mesh built as a 12x6 grid of thin cylinders (vertical + horizontal
strands) + a soccer ball that arcs into the back of the net. Animation :
ball follows Bezier curve into the net, the net segments closest to the
impact briefly bulge backward (-Y), then return.

CLI:
  python proc_soccer_goal.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "soccergoal.glb"

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

mat_grass   = pbr_mat("grass",     (0.18, 0.45, 0.18), 0.00, 0.85)
mat_line    = pbr_mat("line",      (0.92, 0.92, 0.88), 0.00, 0.55)
mat_post    = pbr_mat("post",      (0.95, 0.95, 0.93), 0.20, 0.30)
mat_net     = pbr_mat("net",       (0.85, 0.85, 0.82), 0.00, 0.55)
mat_ball_w  = pbr_mat("ball_w",    (0.95, 0.95, 0.92), 0.00, 0.45)
mat_ball_b  = pbr_mat("ball_b",    (0.08, 0.08, 0.09), 0.00, 0.55)

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=12, rot=None):
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

def _sphere(name, R, location, mat, u=18, v=14):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# Conventions : goal opens toward -Y. Ball comes from -Y direction. Up = +Z.
# Posts span X-axis. Goal "back" is at +Y.

# --- grass + goal area lines ---
_box("grass", 4.0, 4.0, 0.04, (0, 0, -0.04), mat_grass)
# goal line under the goal (white)
_box("goal_line", 3.5, 0.05, 0.004, (0, 0, 0.001), mat_line)
# penalty arc — represented by a few short arc segments along Y=-1
for k in range(7):
    a = -math.pi/2 + k * math.pi/6
    ax = 0.6 * math.cos(a)
    ay = -1.5 + 0.6 * math.sin(a)
    _box(f"arc_{k}", 0.05, 0.05, 0.002, (ax, ay, 0.001), mat_line)

# --- goal frame -------------------
GOAL_W = 2.40   # width along X
GOAL_H = 1.20   # height
GOAL_D = 0.80   # depth into the net (along +Y)
POST_R = 0.025
# 2 vertical posts (front of the goal at Y=0)
for sx in (-1, +1):
    _cyl(f"post_{sx}", POST_R, POST_R, GOAL_H, 'Z',
           (sx * GOAL_W/2, 0, GOAL_H/2), mat_post)
# crossbar
_cyl("crossbar", POST_R, POST_R, GOAL_W, 'X',
       (0, 0, GOAL_H), mat_post)
# 2 back posts (at Y=+GOAL_D, slightly lower for slanted look)
BACK_H = GOAL_H * 0.30
for sx in (-1, +1):
    _cyl(f"back_post_{sx}", POST_R * 0.7, POST_R * 0.7, BACK_H, 'Z',
           (sx * GOAL_W/2, GOAL_D, BACK_H/2), mat_post)
# back-top rail (connecting the 2 back posts at their top)
_cyl("back_top_rail", POST_R * 0.7, POST_R * 0.7, GOAL_W, 'X',
       (0, GOAL_D, BACK_H), mat_post)
# 2 slanted top rails from each front-top corner to the back-top corner
for sx in (-1, +1):
    p0 = mathutils.Vector((sx * GOAL_W/2, 0, GOAL_H))
    p1 = mathutils.Vector((sx * GOAL_W/2, GOAL_D, BACK_H))
    d = p1 - p0
    mid = (p0 + p1) * 0.5
    sl = _cyl(f"slant_{sx}", POST_R * 0.7, POST_R * 0.7, d.length, 'Z',
                (0,0,0), mat_post, segments=10)
    sl.location = mid
    sl.rotation_mode = 'QUATERNION'
    sl.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d.normalized())
# 2 ground rails (along Y, from front-bottom to back-bottom on each side)
for sx in (-1, +1):
    _cyl(f"ground_rail_{sx}", POST_R * 0.7, POST_R * 0.7, GOAL_D, 'Y',
           (sx * GOAL_W/2, GOAL_D/2, POST_R), mat_post)

# --- net : 12 vertical strands x 6 horizontal strands at the BACK face ---
# The back face is the slanted plane from front-top to back-top + back posts.
# For simplicity, we'll fill the rectangular back panel (at Y=GOAL_D, from
# z=0 to z=BACK_H, x=-W/2 to +W/2), the TOP panel (top crossbar to back-top
# rail), and the 2 SIDE panels (triangular).
#
# Net segments are short thin cylinders. We'll build a grid on the BACK face.
N_V = 12   # vertical strands across X
N_H = 6    # horizontal strands across Z
# net pivots — each strand parent so we can vibrate it on impact
net_segments = []   # list of (obj, home_loc, bulge_factor)
for i in range(N_V):
    x = -GOAL_W/2 + 0.04 + i * (GOAL_W - 0.08) / (N_V - 1)
    # vertical strand on back panel
    seg = _box(f"netV_{i}", 0.005, 0.005, BACK_H,
                 (x, GOAL_D, BACK_H/2), mat_net)
    # bulge factor : closer to the impact point (center) = larger
    dist = abs(x) / (GOAL_W/2)
    bulge = max(0.0, 1.0 - dist)
    net_segments.append((seg, mathutils.Vector((x, GOAL_D, BACK_H/2)), bulge))
for j in range(N_H):
    z = 0.05 + j * (BACK_H - 0.10) / (N_H - 1)
    seg = _box(f"netH_{j}", GOAL_W - 0.08, 0.005, 0.005,
                 (0, GOAL_D, z), mat_net)
    bulge = max(0.0, 1.0 - abs(z - BACK_H/2) / (BACK_H/2))
    net_segments.append((seg, mathutils.Vector((0, GOAL_D, z)), bulge))

# Top net (slanted panel from top crossbar to back rail)
# 8 strands along X going from front-top to back-top
N_TOP = 8
for i in range(N_TOP):
    x = -GOAL_W/2 + 0.04 + i * (GOAL_W - 0.08) / (N_TOP - 1)
    p0 = mathutils.Vector((x, 0.01, GOAL_H - 0.01))
    p1 = mathutils.Vector((x, GOAL_D - 0.01, BACK_H + 0.01))
    d = p1 - p0
    mid = (p0 + p1) * 0.5
    sl = _cyl(f"netTop_{i}", 0.004, 0.004, d.length, 'Z', (0,0,0), mat_net, segments=6)
    sl.location = mid
    sl.rotation_mode = 'QUATERNION'
    sl.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d.normalized())

# 2 side nets (triangular panels), 5 strands each
for sx in (-1, +1):
    for k in range(5):
        # k goes from 1 (near front) to 5 (near back)
        y0 = (k + 1) / 6 * GOAL_D
        # height at this Y, interpolating between GOAL_H at Y=0 and BACK_H at Y=GOAL_D
        z_top = GOAL_H + (BACK_H - GOAL_H) * (y0 / GOAL_D)
        p0 = mathutils.Vector((sx * GOAL_W/2, y0, 0))
        p1 = mathutils.Vector((sx * GOAL_W/2, y0, z_top))
        d = p1 - p0
        mid = (p0 + p1) * 0.5
        sl = _cyl(f"netSide_{sx}_{k}", 0.004, 0.004, d.length, 'Z', (0,0,0), mat_net, segments=6)
        sl.location = mid
        sl.rotation_mode = 'QUATERNION'
        sl.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d.normalized())

# --- ball (animated) ----
BALL_R = 0.11
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(-1.0, -2.5, 0.20))
ball_pivot = bpy.context.active_object
ball_pivot.name = "ball_pivot"
ball = _sphere("ball_white", BALL_R, (0, 0, 0), mat_ball_w, u=20, v=14)
ball.parent = ball_pivot
ball.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 5 black pentagonal patches on the ball (approximated as small dark spheres)
for i in range(5):
    a = i * 2*math.pi/5
    bx = BALL_R * 0.85 * math.cos(a)
    by = BALL_R * 0.85 * math.sin(a)
    p = _sphere(f"ball_patch_{i}", BALL_R * 0.30, (bx, by, BALL_R * 0.30), mat_ball_b)
    p.parent = ball_pivot
    p.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# bottom patch
p_b = _sphere("ball_patch_bot", BALL_R * 0.30, (0, 0, -BALL_R * 0.80), mat_ball_b)
p_b.parent = ball_pivot
p_b.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation -----------------
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Ball arcs from (-1.5, -2.5, 0.20) to (0, GOAL_D - 0.1, BACK_H * 0.5)
# (i.e. into the net).
BALL_START = mathutils.Vector((-1.5, -2.5, 0.20))
BALL_PEAK  = mathutils.Vector((-0.5, -1.0, 1.20))
BALL_NET   = mathutils.Vector((0.0, GOAL_D * 0.85, BACK_H * 0.55))
BALL_REST  = mathutils.Vector((0.0, GOAL_D * 0.50, 0.12))

def bezier_quadratic(P0, P1, P2, t):
    u = 1.0 - t
    return u*u*P0 + 2*u*t*P1 + t*t*P2

# Impact time : when the ball hits the net
IMPACT_T = 0.55
def ball_pose(t):
    if t < IMPACT_T:
        u = t / IMPACT_T
        return bezier_quadratic(BALL_START, BALL_PEAK, BALL_NET, u)
    elif t < 0.75:
        # ball bounces backward then drops
        u = (t - IMPACT_T) / 0.20
        # ease-out backward
        offset = (1 - u) * 0.4
        pos = BALL_NET + mathutils.Vector((0, -offset * 0.5, -offset * 0.3))
        return pos
    else:
        u = (t - 0.75) / 0.25
        return BALL_NET.lerp(BALL_REST, u)

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    pos = ball_pose(t)
    bpy.context.scene.frame_set(f)
    ball_pivot.location = (pos.x, pos.y, pos.z)
    # spin
    ball_pivot.rotation_euler = (2*math.pi * 3 * t, 0, 0.6 * math.sin(2*math.pi*t * 4))
    ball_pivot.keyframe_insert("location", frame=f)
    ball_pivot.keyframe_insert("rotation_euler", frame=f)
if ball_pivot.animation_data and ball_pivot.animation_data.action:
    for fc in ball_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Net : segments closer to the impact point bulge backward when the ball
# hits. We use a Gaussian falloff in space and time.
IMPACT_POS = BALL_NET
for (seg, home, bulge_static) in net_segments:
    # spatial falloff : Gaussian around IMPACT_POS
    dist = (home - IMPACT_POS).length
    falloff = math.exp(-(dist * 1.8)**2)
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        # temporal pulse : peak at IMPACT_T, decay over the next 0.25
        local = t - IMPACT_T
        if local < -0.02 or local > 0.40:
            bulge_y = 0
            ripple_z = 0
        else:
            if local < 0.05:
                u = (local + 0.02) / 0.07
                amp = u
            else:
                amp = math.exp(-(local - 0.05) * 6.0)
            bulge_y = 0.18 * falloff * amp
            ripple_z = 0.015 * falloff * amp * math.sin(local * 2*math.pi * 8)
        seg.location = (home.x, home.y + bulge_y, home.z + ripple_z)
        seg.keyframe_insert("location", frame=f)
    if seg.animation_data and seg.animation_data.action:
        for fc in seg.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"GOAL_OK: {out_glb}", flush=True)
'''


def make_goal(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_goal_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "GOAL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_goal(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
