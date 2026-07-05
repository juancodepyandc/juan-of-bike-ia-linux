"""Procedural park bench (Blender headless).

Cast-iron S-curve frame on each end + 5 wooden slats for the seat + 4
wooden slats for the back + small trash can to one side + paved tile.
Animation : a sheet of newspaper / leaf flies in an arc above the bench
(Bezier path), gently rotating as it goes.

CLI:
  python proc_park_bench.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "bench.glb"

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

mat_floor   = pbr_mat("floor",     (0.20, 0.22, 0.18), 0.00, 0.85)
mat_pave    = pbr_mat("pave",      (0.38, 0.36, 0.32), 0.00, 0.85)
mat_iron    = pbr_mat("iron",      (0.10, 0.10, 0.11), 0.50, 0.45)
mat_iron_d  = pbr_mat("iron_dk",   (0.06, 0.06, 0.07), 0.40, 0.50)
mat_wood    = pbr_mat("wood",      (0.32, 0.18, 0.08), 0.05, 0.55)
mat_wood_lt = pbr_mat("wood_lt",   (0.42, 0.24, 0.10), 0.05, 0.50)
mat_paper   = pbr_mat("paper",     (0.92, 0.90, 0.85), 0.00, 0.55)
mat_dark    = pbr_mat("dark",      (0.08, 0.08, 0.09), 0.10, 0.55)

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

def _sphere(name, R, location, mat, u=12, v=8, scale=(1,1,1)):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    if scale != (1,1,1):
        bmesh.ops.scale(bm, vec=mathutils.Vector(scale), verts=bm.verts)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# Conventions : bench faces -Y (seat is on -Y side of the backrest). Up = +Z.

# --- ground -----------------------
_box("floor", 2.6, 1.8, 0.04, (0, 0, -0.04), mat_floor)
_box("pave_slab", 2.4, 1.5, 0.04, (0, 0, 0.02), mat_pave)

# Bench dims
B_W = 1.80   # length (X)
SEAT_D = 0.42
SEAT_Z = 0.42
BACK_H = 0.55

# --- 2 cast-iron end frames (S-curve scrolls on each end) ---
def make_end_frame(name, x):
    """Build one end frame at the given X."""
    # ground plate
    _box(f"{name}_foot", 0.06, 0.45, 0.012,
           (x, 0, 0.046), mat_iron)
    # 2 vertical posts (front + back of the seat area)
    for sy, label in ((-0.18, "F"), (+0.18, "B")):
        _cyl(f"{name}_post_{label}", 0.020, 0.020, SEAT_Z, 'Z',
               (x, sy, 0.052 + SEAT_Z/2), mat_iron)
    # back support : tall post extending up from the back of the seat
    _cyl(f"{name}_back_post", 0.022, 0.022, BACK_H, 'Z',
           (x, 0.18, 0.052 + SEAT_Z + BACK_H/2), mat_iron)
    # 4 S-scroll segments below the seat (decorative): a small curve connecting
    # the 2 posts at the bottom. Implement as a small arc of 3 cyl segments.
    arc_pts = [
        (x, -0.18, 0.052),
        (x, -0.10, 0.020),
        (x,  0.10, 0.020),
        (x,  0.18, 0.052),
    ]
    for k in range(len(arc_pts) - 1):
        p0 = mathutils.Vector(arc_pts[k])
        p1 = mathutils.Vector(arc_pts[k+1])
        d = p1 - p0
        L = d.length
        midp = (p0 + p1) * 0.5
        seg = _cyl(f"{name}_scroll_bot_{k}", 0.012, 0.012, L, 'Z', (0,0,0), mat_iron_d, segments=8)
        seg.location = midp
        direction = d.normalized()
        seg.rotation_mode = 'QUATERNION'
        seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
    # decorative scroll above the seat-back junction (a curl on the back-top)
    scroll_pts = [
        (x, 0.18, 0.052 + SEAT_Z),
        (x, 0.10, 0.052 + SEAT_Z + 0.20),
        (x, -0.02, 0.052 + SEAT_Z + 0.30),
        (x, 0.10, 0.052 + SEAT_Z + 0.40),
        (x, 0.18, 0.052 + SEAT_Z + BACK_H * 0.9),
    ]
    for k in range(len(scroll_pts) - 1):
        p0 = mathutils.Vector(scroll_pts[k])
        p1 = mathutils.Vector(scroll_pts[k+1])
        d = p1 - p0
        L = d.length
        midp = (p0 + p1) * 0.5
        seg = _cyl(f"{name}_scroll_top_{k}", 0.012, 0.012, L, 'Z', (0,0,0), mat_iron_d, segments=8)
        seg.location = midp
        direction = d.normalized()
        seg.rotation_mode = 'QUATERNION'
        seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
    # tiny brass cap on top of back post
    _sphere(f"{name}_cap", 0.022, (x, 0.18, 0.052 + SEAT_Z + BACK_H), mat_iron_d)

make_end_frame("frame_L", -B_W/2 + 0.03)
make_end_frame("frame_R", +B_W/2 - 0.03)

# --- 5 seat slats (wood) running across X --------
SLAT_W = B_W - 0.06
SLAT_T = 0.020
SLAT_D = 0.06
SEAT_TOP_Z = 0.052 + SEAT_Z
for k in range(5):
    sy = -SEAT_D/2 + 0.04 + k * (SEAT_D - 0.08) / 4
    mat = mat_wood if k % 2 == 0 else mat_wood_lt
    _box(f"seat_slat_{k}", SLAT_W, SLAT_D, SLAT_T,
           (0, sy, SEAT_TOP_Z), mat)

# --- 4 backrest slats running across X, tilted slightly back ----
BACK_TILT = math.radians(-10)
for k in range(4):
    # vertically distributed on the back posts
    bz_local = 0.06 + k * (BACK_H - 0.10) / 3  # 0..BACK_H
    by_offset = bz_local * math.sin(-BACK_TILT) + 0.18
    bz_world  = 0.052 + SEAT_Z + bz_local * math.cos(-BACK_TILT)
    mat = mat_wood if k % 2 == 1 else mat_wood_lt
    s = _box(f"back_slat_{k}", SLAT_W, SLAT_D, SLAT_T,
               (0, by_offset, bz_world), mat,
               rot=(BACK_TILT, 0, 0))

# --- a small trash bin to the right of the bench ----
BIN_X = B_W/2 + 0.30
BIN_R = 0.16
BIN_H = 0.65
# bin body (a cylinder with a flared top)
_cyl("bin_body", BIN_R, BIN_R * 1.05, BIN_H, 'Z',
       (BIN_X, 0, 0.04 + BIN_H/2), mat_iron, segments=24)
# rim
_cyl("bin_rim", BIN_R * 1.10, BIN_R * 1.10, 0.020, 'Z',
       (BIN_X, 0, 0.04 + BIN_H + 0.010), mat_iron_d, segments=24)
# inner dark recess
_cyl("bin_inner", BIN_R * 0.92, BIN_R * 0.92, 0.020, 'Z',
       (BIN_X, 0, 0.04 + BIN_H + 0.005), mat_dark, segments=18)
# brand cylinder ring around the middle
_cyl("bin_band", BIN_R + 0.005, BIN_R + 0.005, 0.020, 'Z',
       (BIN_X, 0, 0.04 + BIN_H * 0.50), mat_iron_d, segments=24)
# 4 vertical accent ridges
for i in range(8):
    a = i * 2*math.pi / 8
    rx = BIN_X + BIN_R * 1.03 * math.cos(a)
    ry = BIN_R * 1.03 * math.sin(a)
    _box(f"bin_ridge_{i}", 0.004, 0.004, BIN_H * 0.92,
           (rx, ry, 0.04 + BIN_H/2), mat_iron_d,
           rot=(0, 0, a))

# --- newspaper sheet (animated) ---
# parented to a pivot empty so we can animate location + rotation
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(-1.0, 0.5, 0.6))
paper_pivot = bpy.context.active_object
paper_pivot.name = "paper_pivot"
sheet = _box("paper_sheet", 0.16, 0.001, 0.22, (0, 0, 0), mat_paper)
sheet.parent = paper_pivot
sheet.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# a few thin black lines on the paper (column rules)
for k in range(3):
    ln = _box(f"paper_line_{k}", 0.12, 0.0005, 0.002,
                (0, 0.001, 0.06 - k * 0.04), mat_dark)
    ln.parent = paper_pivot
    ln.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# a title-like dark block
title = _box("paper_title", 0.10, 0.0005, 0.020,
               (0, 0.001, 0.08), mat_dark)
title.parent = paper_pivot
title.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : paper flies in an arc + rotates ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# Bezier control points for an arc above the bench
P0 = mathutils.Vector((-1.2, 0.5, 0.50))   # start (left of bench)
P1 = mathutils.Vector((-0.3, 0.4, 1.30))   # rising
P2 = mathutils.Vector(( 0.4, 0.3, 1.50))   # peak
P3 = mathutils.Vector(( 1.2, 0.5, 0.80))   # falling toward right

def bezier_cubic(P0, P1, P2, P3, t):
    u = 1.0 - t
    return (u**3) * P0 + 3 * (u**2) * t * P1 + 3 * u * (t**2) * P2 + (t**3) * P3

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    pos = bezier_cubic(P0, P1, P2, P3, t)
    paper_pivot.location = (pos.x, pos.y, pos.z)
    # rotation : tumble around X (front-to-back flip) + slight Y spin
    paper_pivot.rotation_euler = (
        2*math.pi * t * 0.8,
        math.radians(20) * math.sin(2*math.pi*t * 4.0),
        math.radians(15) * math.sin(2*math.pi*t * 1.5),
    )
    paper_pivot.keyframe_insert("location", frame=f)
    paper_pivot.keyframe_insert("rotation_euler", frame=f)
if paper_pivot.animation_data and paper_pivot.animation_data.action:
    for fc in paper_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"BENCH_OK: {out_glb}", flush=True)
'''


def make_bench(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_bench_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "BENCH_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_bench(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
