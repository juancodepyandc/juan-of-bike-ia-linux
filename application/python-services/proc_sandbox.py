"""Procedural children's sandbox with toys (Blender headless).

Square wooden frame (4 thick wooden border planks) filled with sand,
4 corner seats (small triangular blocks for kids to sit on), and 3
toys : a red bucket + a blue shovel + a 3-tier sand castle. Animation
: the blue shovel rises from rest, arcs over to the castle area, and
plants its tip down into the sand (Bezier path + tilt).

CLI:
  python proc_sandbox.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "sandbox.glb"

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

mat_grass    = pbr_mat("grass",     (0.20, 0.45, 0.18), 0.00, 0.85)
mat_sand     = pbr_mat("sand",      (0.85, 0.78, 0.55), 0.00, 0.85)
mat_sand_d   = pbr_mat("sand_dk",   (0.65, 0.58, 0.38), 0.00, 0.85)
mat_wood     = pbr_mat("wood",      (0.55, 0.32, 0.16), 0.05, 0.55)
mat_wood_lt  = pbr_mat("wood_lt",   (0.75, 0.45, 0.20), 0.05, 0.50)
mat_red      = pbr_mat("red",       (0.85, 0.18, 0.12), 0.10, 0.40)
mat_blue     = pbr_mat("blue",      (0.20, 0.50, 0.92), 0.10, 0.40)
mat_chrome   = pbr_mat("chrome",    (0.80, 0.82, 0.85), 1.00, 0.18)
mat_yellow   = pbr_mat("yellow",    (0.95, 0.85, 0.20), 0.10, 0.40)

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=16, rot=None):
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

def _sphere(name, R, location, mat, u=14, v=10, scale=(1,1,1)):
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

# Conventions : sandbox square in XY plane. Up = +Z.

# --- grass ---
_box("floor", 3.5, 3.5, 0.04, (0, 0, -0.04), mat_grass)

# Sandbox dimensions
SB_W = 1.80   # outer X
SB_D = 1.80   # outer Y
BORDER_T = 0.10
BORDER_H = 0.18

# --- 4 wooden border planks (square frame) ---
# North + South borders span SB_W along X
for sy in (-1, +1):
    _box(f"border_{sy}_Y", SB_W, BORDER_T, BORDER_H,
           (0, sy * (SB_D/2 - BORDER_T/2), 0.04 + BORDER_H/2), mat_wood_lt)
# East + West borders span (SB_D - 2*BORDER_T) along Y
for sx in (-1, +1):
    _box(f"border_{sx}_X", BORDER_T, SB_D - 2*BORDER_T, BORDER_H,
           (sx * (SB_W/2 - BORDER_T/2), 0, 0.04 + BORDER_H/2), mat_wood_lt)

# --- 4 corner seats (triangular wedges) ---
SEAT_W = 0.30
for sx in (-1, +1):
    for sy in (-1, +1):
        # small wooden block on the corner, slightly higher than the border
        _box(f"corner_seat_{sx}_{sy}", SEAT_W, SEAT_W, 0.06,
               (sx * (SB_W/2 - SEAT_W/2), sy * (SB_D/2 - SEAT_W/2),
                0.04 + BORDER_H + 0.03), mat_wood)
        # darker wood band on top
        _box(f"corner_band_{sx}_{sy}", SEAT_W * 0.85, SEAT_W * 0.85, 0.008,
               (sx * (SB_W/2 - SEAT_W/2), sy * (SB_D/2 - SEAT_W/2),
                0.04 + BORDER_H + 0.063), mat_wood)

# --- sand surface (inside the borders) ---
SAND_W = SB_W - 2 * BORDER_T - 0.005
SAND_D = SB_D - 2 * BORDER_T - 0.005
SAND_TOP_Z = 0.04 + BORDER_H * 0.65
_box("sand", SAND_W, SAND_D, 0.04, (0, 0, SAND_TOP_Z / 2 + 0.04), mat_sand)

# --- 3-tier sand castle (top-right corner of the box) ---
CASTLE_X = 0.35
CASTLE_Y = 0.35
CASTLE_BASE_Z = SAND_TOP_Z + 0.005

# tier 1 (largest, base)
_cyl("castle_t1", 0.16, 0.16, 0.10, 'Z',
       (CASTLE_X, CASTLE_Y, CASTLE_BASE_Z + 0.05), mat_sand_d, segments=8)
# tier 2 (medium)
_cyl("castle_t2", 0.12, 0.12, 0.08, 'Z',
       (CASTLE_X, CASTLE_Y, CASTLE_BASE_Z + 0.10 + 0.04), mat_sand_d, segments=8)
# tier 3 (smallest, on top)
_cyl("castle_t3", 0.08, 0.08, 0.06, 'Z',
       (CASTLE_X, CASTLE_Y, CASTLE_BASE_Z + 0.10 + 0.08 + 0.03), mat_sand_d, segments=8)
# small flag-pole on top (yellow flag)
_cyl("castle_pole", 0.005, 0.005, 0.12, 'Z',
       (CASTLE_X, CASTLE_Y, CASTLE_BASE_Z + 0.24 + 0.06), mat_chrome)
_box("castle_flag", 0.001, 0.04, 0.04,
       (CASTLE_X, CASTLE_Y + 0.022, CASTLE_BASE_Z + 0.24 + 0.10), mat_yellow)

# --- red bucket (cylinder + handle), in the corner opposite the castle ---
BUCKET_X = -0.40
BUCKET_Y = -0.30
BUCKET_R = 0.075
BUCKET_H = 0.13
# bucket body (red cylinder, slightly tapered)
_cyl("bucket_body", BUCKET_R, BUCKET_R * 0.85, BUCKET_H, 'Z',
       (BUCKET_X, BUCKET_Y, SAND_TOP_Z + 0.005 + BUCKET_H/2), mat_red, segments=18)
# bucket rim
_cyl("bucket_rim", BUCKET_R * 1.05, BUCKET_R * 1.05, 0.010, 'Z',
       (BUCKET_X, BUCKET_Y, SAND_TOP_Z + 0.010 + BUCKET_H), mat_red, segments=18)
# bucket handle (a thin arc from one side to the other)
for k in range(6):
    a = math.pi * (k + 0.5) / 6
    hx = BUCKET_R * math.cos(a)
    hz = 0.06 * math.sin(a) + BUCKET_R * math.cos(a) * 0  # use cos for X, sin for Z extra
    hx_w = BUCKET_X + hx
    hy_w = BUCKET_Y
    hz_w = SAND_TOP_Z + 0.010 + BUCKET_H + 0.04 * math.sin(a)
    # short link
    if k < 5:
        a2 = math.pi * (k + 1.5) / 6
        nx = BUCKET_R * math.cos(a2)
        nz_offset = 0.04 * math.sin(a2)
        nx_w = BUCKET_X + nx
        nz_w = SAND_TOP_Z + 0.010 + BUCKET_H + nz_offset
        d = mathutils.Vector((nx_w - hx_w, 0, nz_w - hz_w))
        L = d.length
        mid = mathutils.Vector(((hx_w + nx_w)/2, hy_w, (hz_w + nz_w)/2))
        seg = _cyl(f"bucket_handle_{k}", 0.005, 0.005, L, 'Z', (0,0,0), mat_chrome, segments=8)
        seg.location = mid
        seg.rotation_mode = 'QUATERNION'
        seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d.normalized())

# --- blue shovel (animated, parented to a pivot empty) ---
# Resting pose : lying flat on the sand near the bucket
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(-0.20, -0.05, SAND_TOP_Z + 0.025))
shovel_pivot = bpy.context.active_object
shovel_pivot.name = "shovel_pivot"
# handle (long cylinder along +Y direction in local frame)
handle = _cyl("shovel_handle", 0.012, 0.010, 0.35, 'Y',
                (0, 0.10, 0), mat_blue, segments=10)
handle.parent = shovel_pivot
handle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# grip at the rear (+Y end)
grip = _cyl("shovel_grip", 0.018, 0.018, 0.04, 'Y',
              (0, 0.30, 0), mat_red, segments=10)
grip.parent = shovel_pivot
grip.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# scoop blade (flat triangular wedge at the -Y end)
blade = _box("shovel_blade", 0.10, 0.14, 0.012,
               (0, -0.10, 0), mat_blue)
blade.parent = shovel_pivot
blade.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# blade rim (slightly raised edge on the front)
blade_rim = _box("shovel_blade_rim", 0.10, 0.014, 0.020,
                   (0, -0.17, 0.004), mat_blue)
blade_rim.parent = shovel_pivot
blade_rim.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : shovel arcs over to the castle and digs in ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Key poses
HOME_POS = mathutils.Vector((-0.20, -0.05, SAND_TOP_Z + 0.025))
HOME_ROT = (0, 0, 0)
LIFT_POS = mathutils.Vector((-0.20, -0.05, SAND_TOP_Z + 0.30))
LIFT_ROT = (math.radians(-30), 0, 0)
VIA_POS  = mathutils.Vector((0.05, 0.15, SAND_TOP_Z + 0.40))
VIA_ROT  = (math.radians(-50), 0, math.radians(20))
DIG_POS  = mathutils.Vector((0.10, 0.10, SAND_TOP_Z + 0.05))
DIG_ROT  = (math.radians(-60), 0, math.radians(30))

def shovel_pose(t):
    if t < 0.20:
        u = t / 0.20
        pos = HOME_POS.lerp(LIFT_POS, u)
        rot = tuple(HOME_ROT[i] + (LIFT_ROT[i] - HOME_ROT[i]) * u for i in range(3))
    elif t < 0.50:
        u = (t - 0.20) / 0.30
        pos = LIFT_POS.lerp(VIA_POS, u)
        rot = tuple(LIFT_ROT[i] + (VIA_ROT[i] - LIFT_ROT[i]) * u for i in range(3))
    elif t < 0.70:
        u = (t - 0.50) / 0.20
        # accelerate downward
        u2 = u * u
        pos = VIA_POS.lerp(DIG_POS, u2)
        rot = tuple(VIA_ROT[i] + (DIG_ROT[i] - VIA_ROT[i]) * u for i in range(3))
    elif t < 0.85:
        # rest in dig position
        pos = DIG_POS
        rot = DIG_ROT
    else:
        # return home
        u = (t - 0.85) / 0.15
        pos = DIG_POS.lerp(HOME_POS, u)
        rot = tuple(DIG_ROT[i] + (HOME_ROT[i] - DIG_ROT[i]) * u for i in range(3))
    return pos, rot

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    pos, rot = shovel_pose(t)
    bpy.context.scene.frame_set(f)
    shovel_pivot.location = (pos.x, pos.y, pos.z)
    shovel_pivot.rotation_euler = rot
    shovel_pivot.keyframe_insert("location", frame=f)
    shovel_pivot.keyframe_insert("rotation_euler", frame=f)
if shovel_pivot.animation_data and shovel_pivot.animation_data.action:
    for fc in shovel_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SBOX_OK: {out_glb}", flush=True)
'''


def make_sandbox(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_sbox_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SBOX_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_sandbox(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
