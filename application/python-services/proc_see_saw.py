"""Procedural see-saw / teeter-totter (Blender headless).

Concrete base + 2 angled wooden pivot supports forming an A-frame +
horizontal axle + a long wooden plank alternating red/yellow stripes
+ 2 chrome handle grips at each end + 2 curved wooden seats + small
spring shock-absorbers under the seat ends + sand patch around. Animation
: plank rotates around X axis around the central pivot in a slow
oscillation (sin ±20°).

CLI:
  python proc_see_saw.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "seesaw.glb"

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
mat_concrete = pbr_mat("concrete",  (0.45, 0.43, 0.40), 0.00, 0.85)
mat_wood     = pbr_mat("wood",      (0.45, 0.28, 0.12), 0.05, 0.55)
mat_wood_lt  = pbr_mat("wood_lt",   (0.60, 0.38, 0.18), 0.05, 0.50)
mat_red      = pbr_mat("red",       (0.85, 0.18, 0.12), 0.10, 0.40)
mat_yellow   = pbr_mat("yellow",    (0.95, 0.85, 0.20), 0.10, 0.40)
mat_chrome   = pbr_mat("chrome",    (0.80, 0.82, 0.85), 1.00, 0.18)
mat_dark     = pbr_mat("dark",      (0.08, 0.08, 0.09), 0.30, 0.45)
mat_steel    = pbr_mat("steel",     (0.55, 0.55, 0.58), 0.85, 0.30)

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

def _sphere(name, R, location, mat, u=12, v=8):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# Conventions : see-saw axle runs along X (plank extends along Y from -PLANK/2 to +PLANK/2).
# Up = +Z.

# --- ground -----------------
_box("floor", 3.5, 4.0, 0.04, (0, 0, -0.04), mat_grass)
_box("sand_patch", 2.4, 3.0, 0.025, (0, 0, 0.013), mat_sand)

# --- concrete pad under the pivot ---
_box("concrete_pad", 0.50, 0.50, 0.04, (0, 0, 0.04), mat_concrete)

# --- 2 A-frame angled wooden supports ---
PIVOT_Z = 0.60
PIVOT_X_SPREAD = 0.30  # the base of the A is this wide
for sx in (-1, +1):
    p0 = mathutils.Vector((sx * PIVOT_X_SPREAD, 0, 0.06))
    p1 = mathutils.Vector((0, 0, PIVOT_Z))
    d = p1 - p0
    mid = (p0 + p1) * 0.5
    sup = _cyl(f"support_{sx}", 0.035, 0.035, d.length, 'Z',
                 (0,0,0), mat_wood, segments=12)
    sup.location = mid
    sup.rotation_mode = 'QUATERNION'
    sup.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d.normalized())
# small base shoes
for sx in (-1, +1):
    _box(f"support_shoe_{sx}", 0.10, 0.10, 0.015,
           (sx * PIVOT_X_SPREAD, 0, 0.063), mat_dark)

# horizontal axle bar (the pivot point)
_cyl("axle", 0.035, 0.035, 0.20, 'X',
       (0, 0, PIVOT_Z), mat_chrome)

# --- plank (animated, parented to pivot empty) ---
PLANK_LEN = 2.40
PLANK_W = 0.18
PLANK_T = 0.04
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, PIVOT_Z))
plank_pivot = bpy.context.active_object
plank_pivot.name = "plank_pivot"
# main plank (yellow base)
plank = _box("plank", PLANK_W, PLANK_LEN, PLANK_T,
               (0, 0, PLANK_T/2 + 0.005), mat_yellow)
plank.parent = plank_pivot
plank.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 4 red stripes alternating along the length
N_STRIPES = 4
for k in range(N_STRIPES):
    sy = -PLANK_LEN/2 + 0.15 + k * (PLANK_LEN - 0.30) / (N_STRIPES - 1)
    stripe = _box(f"plank_stripe_{k}", PLANK_W + 0.001, 0.10, PLANK_T + 0.001,
                    (0, sy, PLANK_T/2 + 0.005), mat_red)
    stripe.parent = plank_pivot
    stripe.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 2 curved wooden seats at each end (slightly raised + curved-looking via 2 boxes)
for sy in (-1, +1):
    # main seat slab
    seat = _box(f"seat_{sy}", PLANK_W + 0.04, 0.30, PLANK_T,
                  (0, sy * (PLANK_LEN/2 - 0.20), PLANK_T + 0.025), mat_wood_lt)
    seat.parent = plank_pivot
    seat.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # raised back-stop (a small block at the very end to prevent slipping back)
    back = _box(f"seat_back_{sy}", PLANK_W + 0.04, 0.04, 0.08,
                  (0, sy * (PLANK_LEN/2 - 0.05), PLANK_T + 0.060), mat_wood)
    back.parent = plank_pivot
    back.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 2 chrome handle grips at each end (curved bars children would hold)
for sy in (-1, +1):
    # handle base post
    post = _cyl(f"handle_post_{sy}", 0.012, 0.012, 0.30, 'Z',
                  (0, sy * (PLANK_LEN/2 - 0.30), PLANK_T + 0.150),
                  mat_chrome)
    post.parent = plank_pivot
    post.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # cross handle (a horizontal bar at the top of the post)
    handle = _cyl(f"handle_bar_{sy}", 0.012, 0.012, PLANK_W * 1.6, 'X',
                    (0, sy * (PLANK_LEN/2 - 0.30), PLANK_T + 0.300),
                    mat_chrome)
    handle.parent = plank_pivot
    handle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # 2 grip caps on the handle ends
    for sx in (-1, +1):
        cap = _sphere(f"handle_cap_{sy}_{sx}", 0.018,
                        (sx * PLANK_W * 0.8, sy * (PLANK_LEN/2 - 0.30),
                         PLANK_T + 0.300),
                        mat_red)
        cap.parent = plank_pivot
        cap.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 2 spring shock-absorbers under each end (visible from outside the seat,
# they compress when the seat hits the ground)
for sy in (-1, +1):
    # spring : a helical-ish stack of small tori but simpler — a short
    # cylinder painted dark with a brass collar
    spring = _cyl(f"spring_{sy}", 0.025, 0.025, 0.10, 'Z',
                    (0, sy * (PLANK_LEN/2 + 0.05), 0.05 + 0.05),
                    mat_steel, segments=10)
    spring.parent = plank_pivot
    spring.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # rubber tip on the bottom (where it touches ground)
    tip = _cyl(f"spring_tip_{sy}", 0.030, 0.030, 0.012, 'Z',
                 (0, sy * (PLANK_LEN/2 + 0.05), 0.018),
                 mat_dark, segments=10)
    tip.parent = plank_pivot
    tip.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : plank rotates around X (axle) ---
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Amplitude : ±20° around X, simple sine
SEESAW_AMP = math.radians(20)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    angle = SEESAW_AMP * math.sin(2*math.pi*t * 1.0)
    plank_pivot.rotation_euler = (angle, 0, 0)
    plank_pivot.keyframe_insert("rotation_euler", frame=f)
if plank_pivot.animation_data and plank_pivot.animation_data.action:
    for fc in plank_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SEESAW_OK: {out_glb}", flush=True)
'''


def make_seesaw(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_ss_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SEESAW_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_seesaw(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
