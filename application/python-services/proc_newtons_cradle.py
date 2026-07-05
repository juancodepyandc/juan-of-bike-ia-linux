"""Procedural Newton's cradle (Blender headless).

Wood base + 4 brass corner posts + 2 top horizontal bars + 5 steel
balls suspended by V-strings. Animation : the left ball swings out
+30 deg ; on the return strike, the right ball swings out +30 deg ;
middle 3 balls stay still (the classic Newton's cradle energy-transfer
cycle).

CLI:
  python proc_newtons_cradle.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "newton.glb"

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

mat_wood    = pbr_mat("wood",      (0.30, 0.18, 0.08), 0.00, 0.60)
mat_brass   = pbr_mat("brass",     (0.86, 0.62, 0.20), 1.00, 0.28)
mat_steel   = pbr_mat("ball_steel",(0.75, 0.77, 0.80), 1.00, 0.10)
mat_string  = pbr_mat("string",    (0.15, 0.15, 0.18), 0.10, 0.55)
mat_floor   = pbr_mat("floor",     (0.30, 0.30, 0.32), 0.00, 0.85)

def _cyl(name, R1, R2, depth, axis, location, mat, segments=16):
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

# --- floor ---------------------------------------------
_box("floor", 1.5, 1.5, 0.04, (0, 0, -0.04), mat_floor)

# --- wood base -----------------------------------------
BASE_W = 0.80
BASE_D = 0.35
BASE_H = 0.06
_box("base", BASE_W, BASE_D, BASE_H, (0, 0, BASE_H/2), mat_wood)

# --- 4 brass posts at the corners ----------------------
POST_H = 0.55
POST_X = BASE_W * 0.45
POST_Y = BASE_D * 0.35
for sx in (-1, 1):
    for sy in (-1, 1):
        _cyl(f"post_{sx}_{sy}", 0.018, 0.018, POST_H, 'Z',
               (sx * POST_X, sy * POST_Y, BASE_H + POST_H/2), mat_brass)

# --- 2 top horizontal bars connecting the posts (along X axis) ---
TOP_Z = BASE_H + POST_H
for sy in (-1, 1):
    _cyl(f"top_bar_{sy}", 0.012, 0.012, POST_X * 2, 'X',
           (0, sy * POST_Y, TOP_Z), mat_brass)

# --- 5 steel balls with V-strings to top bars ----------
BALL_R = 0.038
N_BALLS = 5
BALL_SPACING = BALL_R * 2.0 + 0.003   # nearly touching
BALL_Z_REST = BASE_H + POST_H - 0.32   # how low the balls hang
total_span = (N_BALLS - 1) * BALL_SPACING

ball_pivots = []
for i in range(N_BALLS):
    bx = -total_span/2 + i * BALL_SPACING
    # Pivot empty at the TOP of the strings (where they attach to the bars)
    # but offset between the 2 top bars : we pivot at (bx, 0, TOP_Z).
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(bx, 0, TOP_Z))
    pv = bpy.context.active_object
    pv.name = f"ball_pivot_{i}"

    # ball (parented to pivot, hanging below)
    ball = _sphere(f"ball_{i}", BALL_R, (0, 0, BALL_Z_REST - TOP_Z), mat_steel)
    ball.parent = pv
    ball.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    # 2 V-strings from ball to the 2 top bars
    string_len = math.hypot(POST_Y, TOP_Z - BALL_Z_REST)
    for sy in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, sy * POST_Y / 2,
                                                            (TOP_Z + BALL_Z_REST)/2 - TOP_Z))
        s = bpy.context.active_object
        s.name = f"string_{i}_{sy}"
        s.scale = (0.004, 0.004, string_len)
        bpy.ops.object.transform_apply(scale=True)
        # rotate to align Z axis with the string direction
        s.rotation_euler = (sy * math.atan2(POST_Y, TOP_Z - BALL_Z_REST), 0, 0)
        s.data.materials.append(mat_string)
        s.parent = pv
        s.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    ball_pivots.append(pv)

# --- animation : classic Newton's cradle cycle ----------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 1

# The left ball (0) swings out then returns ; the middle 3 stay still ; the
# right ball (4) swings out at the moment the left ball hits the row.  After
# the right swings back, the left swings out again.  We approximate with
# rotation_euler.y on the leftmost + rightmost pivots, opposite-phase.
SWING_AMP = math.radians(35)

def lerp_keys(pv, keys):
    """keys = list of (frame, angle_y)."""
    for (frame, angle) in keys:
        bpy.context.scene.frame_set(frame)
        pv.rotation_euler = (0, angle, 0)
        pv.keyframe_insert("rotation_euler", frame=frame)

# Half a cycle (left side dominates) over t = 0..0.5, then right side over 0.5..1.0.
# Left ball : starts at +SWING_AMP, swings down to 0 (impact at t=0.20),
# then stays at 0 until t=0.80 when it's struck back to +SWING_AMP and back.
# Right ball : starts at 0, swings to -SWING_AMP at t=0.30 (impact), stays
# until t=0.70 then swings back to 0.

f_quarter   = int(0.20 * NFR)
f_three_q   = int(0.30 * NFR)
f_five_eq   = int(0.50 * NFR)
f_seven_q   = int(0.70 * NFR)
f_nine_q    = int(0.80 * NFR)

lerp_keys(ball_pivots[0], [
    (1,              +SWING_AMP),
    (f_quarter,       0),
    (f_nine_q,        0),
    (NFR,            +SWING_AMP),
])
lerp_keys(ball_pivots[4], [
    (1,              0),
    (f_three_q,      -SWING_AMP),
    (f_seven_q,      -SWING_AMP),
    (NFR,            0),
])
# middle 3 stay at rest
for i in (1, 2, 3):
    bpy.context.scene.frame_set(1)
    ball_pivots[i].rotation_euler = (0, 0, 0)
    ball_pivots[i].keyframe_insert("rotation_euler", frame=1)
    bpy.context.scene.frame_set(NFR)
    ball_pivots[i].rotation_euler = (0, 0, 0)
    ball_pivots[i].keyframe_insert("rotation_euler", frame=NFR)

# Use BEZIER for smooth pendulum motion (eases in/out)
for pv in ball_pivots:
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"NEWTON_OK: {out_glb}", flush=True)
'''


def make_newton(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_newton_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "NEWTON_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_newton(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
