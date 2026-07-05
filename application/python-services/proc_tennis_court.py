"""Procedural tennis court with bouncing ball (Blender headless).

Green hard court + white painted lines (baselines, service lines,
singles + doubles sidelines, center mark, T) + central net : 2 posts +
top tape + mesh of vertical + horizontal strands. A yellow tennis ball
bounces back and forth across the court following a 4-segment Bezier
trajectory with realistic gravity arc + hit ping-pong style on each side.

CLI:
  python proc_tennis_court.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "tennis.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough, emission=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if emission is not None and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission[0], 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission[1]
    return m

mat_floor   = pbr_mat("floor",     (0.10, 0.10, 0.12), 0.00, 0.85)
mat_court   = pbr_mat("court",     (0.18, 0.45, 0.30), 0.00, 0.70)
mat_line    = pbr_mat("line",      (0.95, 0.95, 0.92), 0.00, 0.55)
mat_post    = pbr_mat("post",      (0.06, 0.06, 0.07), 0.30, 0.45)
mat_net     = pbr_mat("net",       (0.06, 0.06, 0.07), 0.05, 0.65)
mat_tape    = pbr_mat("tape",      (0.95, 0.95, 0.92), 0.00, 0.55)
mat_ball    = pbr_mat("ball",      (0.85, 0.95, 0.20), 0.00, 0.55,
                          emission=((0.90, 1.00, 0.30), 1.5))
mat_ball_ln = pbr_mat("ball_ln",   (0.92, 0.92, 0.88), 0.00, 0.55)

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

def _sphere(name, R, location, mat, u=18, v=12):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# Conventions : court along Y, baseline at -Y and +Y, net at Y=0. Up = +Z.
# Standard ITF dimensions (scaled to ~3:1 aspect on our viewer) :
#   Singles court : 8.23 m × 23.77 m → 0.823 × 2.377 (scaled)
# Use full-size proportions but smaller numbers.
COURT_W = 1.00   # singles + doubles width
COURT_D = 2.40   # baseline to baseline
LINE_T  = 0.012  # line thickness
LINE_H  = 0.005  # line height (painted line, just on surface)

# --- background ---
_box("floor", 4.0, 3.6, 0.04, (0, 0, -0.04), mat_floor)

# --- court playing surface (green) ---
COURT_OUTER_W = COURT_W * 1.20
COURT_OUTER_D = COURT_D * 1.15
_box("court", COURT_OUTER_W, COURT_OUTER_D, 0.04, (0, 0, 0.02), mat_court)

# --- white lines ---
COURT_TOP_Z = 0.045
# 2 baselines (along X, at +/- COURT_D/2)
for sy in (-1, +1):
    _box(f"baseline_{sy}", COURT_W + LINE_T*2, LINE_T, LINE_H,
           (0, sy * COURT_D/2, COURT_TOP_Z), mat_line)
# 2 singles sidelines (along Y, at +/- COURT_W/2)
for sx in (-1, +1):
    _box(f"sideline_{sx}", LINE_T, COURT_D + LINE_T*2, LINE_H,
           (sx * COURT_W/2, 0, COURT_TOP_Z), mat_line)
# 2 doubles sidelines (slightly outside the singles)
DOUBLE_X = COURT_W/2 + 0.08
for sx in (-1, +1):
    _box(f"doubles_{sx}", LINE_T, COURT_D + LINE_T*2, LINE_H,
           (sx * DOUBLE_X, 0, COURT_TOP_Z), mat_line)
# 2 service lines (parallel to baselines, at +/- COURT_D * 0.21 from center)
for sy in (-1, +1):
    _box(f"service_{sy}", COURT_W + LINE_T*2, LINE_T, LINE_H,
           (0, sy * COURT_D * 0.21, COURT_TOP_Z), mat_line)
# center service line (from each service line to the net)
_box("center_service", LINE_T, COURT_D * 0.42, LINE_H,
       (0, 0, COURT_TOP_Z), mat_line)
# 2 center marks on baselines (small short lines crossing the baseline)
for sy in (-1, +1):
    _box(f"center_mark_{sy}", LINE_T * 3, LINE_T * 6, LINE_H,
           (0, sy * COURT_D/2, COURT_TOP_Z), mat_line)

# --- net (at Y = 0) ----------
NET_POST_X = COURT_OUTER_W/2 + 0.03
NET_H = 0.20   # height at posts (scaled for visibility)
NET_CENTER_H = 0.16   # slightly lower at center
# 2 posts
for sx in (-1, +1):
    _cyl(f"net_post_{sx}", 0.020, 0.020, NET_H + 0.10, 'Z',
           (sx * NET_POST_X, 0, 0.045 + (NET_H + 0.10)/2),
           mat_post, segments=12)
    # cap
    _sphere(f"net_cap_{sx}", 0.025,
              (sx * NET_POST_X, 0, 0.045 + NET_H + 0.10),
              mat_post)
# white tape at top of net (sags slightly in the middle — 5 short segments)
N_TAPE = 5
for k in range(N_TAPE):
    x_left  = -NET_POST_X + k * (2 * NET_POST_X) / N_TAPE
    x_right = -NET_POST_X + (k + 1) * (2 * NET_POST_X) / N_TAPE
    # compute height at each end of the segment via a parabola : net sags
    # in the middle. Profile : z = NET_H - (NET_H - NET_CENTER_H) * (1 - (x/NET_POST_X)²)
    def net_top_z(x):
        u = abs(x) / NET_POST_X
        return NET_H * u**2 + NET_CENTER_H * (1 - u**2) + 0.045
    z0 = net_top_z(x_left); z1 = net_top_z(x_right)
    L = math.sqrt((x_right - x_left)**2 + (z1 - z0)**2)
    midp = ((x_left + x_right) / 2, 0, (z0 + z1) / 2)
    seg = _cyl(f"tape_{k}", 0.008, 0.008, L, 'Z', (0,0,0), mat_tape, segments=8)
    seg.location = midp
    d = mathutils.Vector((x_right - x_left, 0, z1 - z0)).normalized()
    seg.rotation_mode = 'QUATERNION'
    seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d)
# net mesh : 12 vertical strands + 4 horizontal strands
N_V = 12
N_H = 4
for i in range(N_V):
    x = -NET_POST_X + 0.05 + i * (2 * NET_POST_X - 0.10) / (N_V - 1)
    z_top = NET_H * (abs(x)/NET_POST_X)**2 + NET_CENTER_H * (1 - (abs(x)/NET_POST_X)**2) + 0.045
    z_bot = 0.045
    _cyl(f"net_v_{i}", 0.0035, 0.0035, z_top - z_bot, 'Z',
           (x, 0, (z_top + z_bot)/2), mat_net, segments=6)
for j in range(N_H):
    z = 0.060 + j * (NET_CENTER_H - 0.020) / (N_H - 1)
    _cyl(f"net_h_{j}", 0.0035, 0.0035, 2 * NET_POST_X - 0.04, 'X',
           (0, 0, z), mat_net, segments=6)

# --- tennis ball (animated) -------
BALL_R = 0.045
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, -COURT_D * 0.40, BALL_R + 0.05))
ball_pivot = bpy.context.active_object
ball_pivot.name = "ball_pivot"
ball = _sphere("ball", BALL_R, (0, 0, 0), mat_ball, u=16, v=12)
ball.parent = ball_pivot
ball.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 white curved lines on the ball (approximated as thin arc cylinders)
for k in range(2):
    ln = _cyl(f"ball_seam_{k}", BALL_R + 0.001, BALL_R + 0.001, 0.003, 'Z',
                (0, 0, 0), mat_ball_ln, segments=20, rot=(k * math.pi/2, 0, 0))
    ln.parent = ball_pivot
    ln.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : ball bounces back and forth (2 hits per loop) ---
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Define 2 arc segments :
#   t=[0.00, 0.50] : ball arcs from -Y baseline area to +Y baseline area
#   t=[0.50, 1.00] : ball arcs back from +Y to -Y
HIT_Y_LO = -COURT_D * 0.40
HIT_Y_HI = +COURT_D * 0.40
PEAK_Z = 0.55

def ball_pose(t):
    if t < 0.50:
        u = t / 0.50
        # quadratic Bezier with peak at center (Y=0, Z=PEAK_Z)
        y = HIT_Y_LO + u * (HIT_Y_HI - HIT_Y_LO)
        z = (BALL_R + 0.05) + (PEAK_Z - (BALL_R + 0.05)) * (1 - (2*u - 1)**2)
    else:
        u = (t - 0.50) / 0.50
        y = HIT_Y_HI - u * (HIT_Y_HI - HIT_Y_LO)
        z = (BALL_R + 0.05) + (PEAK_Z - (BALL_R + 0.05)) * (1 - (2*u - 1)**2)
    return y, z

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    y, z = ball_pose(t)
    bpy.context.scene.frame_set(f)
    ball_pivot.location = (0, y, z)
    # spin : forward roll based on Y direction
    ball_pivot.rotation_euler = (2*math.pi * 4 * t, 0, 0)
    ball_pivot.keyframe_insert("location", frame=f)
    ball_pivot.keyframe_insert("rotation_euler", frame=f)
if ball_pivot.animation_data and ball_pivot.animation_data.action:
    for fc in ball_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"TENNIS_OK: {out_glb}", flush=True)
'''


def make_tennis(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_tennis_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "TENNIS_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_tennis(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
