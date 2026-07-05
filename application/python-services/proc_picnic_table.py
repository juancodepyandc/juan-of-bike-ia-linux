"""Procedural picnic table (Blender headless).

Classic wooden picnic table : top plank surface + 2 bench seats on either
side + 2 A-frame leg supports + checkered tablecloth + 2 plates + 1 glass
+ 1 sandwich. Animation : a small butterfly flies in a circle around
the table.

CLI:
  python proc_picnic_table.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "picnic.glb"

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

mat_grass    = pbr_mat("grass",    (0.20, 0.45, 0.18), 0.00, 0.85)
mat_wood     = pbr_mat("wood",     (0.55, 0.32, 0.16), 0.05, 0.55)
mat_wood_lt  = pbr_mat("wood_lt",  (0.65, 0.40, 0.18), 0.05, 0.50)
mat_cloth_r  = pbr_mat("cloth_red",(0.85, 0.18, 0.12), 0.00, 0.70)
mat_cloth_w  = pbr_mat("cloth_wht",(0.95, 0.92, 0.88), 0.00, 0.70)
mat_plate    = pbr_mat("plate",    (0.95, 0.95, 0.92), 0.00, 0.40)
mat_glass    = pbr_mat("glass",    (0.85, 0.92, 0.95), 0.00, 0.10, alpha=0.35)
mat_liquid   = pbr_mat("liquid",   (0.85, 0.45, 0.18), 0.00, 0.40)
mat_bread    = pbr_mat("bread",    (0.78, 0.55, 0.28), 0.00, 0.60)
mat_filling  = pbr_mat("filling",  (0.18, 0.55, 0.20), 0.00, 0.55)
mat_butterfly_a = pbr_mat("butter_a",(0.95, 0.55, 0.18), 0.00, 0.55)
mat_butterfly_b = pbr_mat("butter_b",(0.18, 0.30, 0.85), 0.00, 0.55)
mat_butterfly_body = pbr_mat("bf_body",(0.10, 0.06, 0.04), 0.00, 0.65)

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

# Conventions : table along Y, bench seats on +X and -X. Up = +Z.

# --- grass ---
_box("floor", 4.0, 3.5, 0.04, (0, 0, -0.04), mat_grass)

# Dimensions
TABLE_W = 1.80   # length along Y
TABLE_D = 0.80   # depth (X)
TABLE_TOP_Z = 0.75
BENCH_D = 0.30
BENCH_Z = 0.45
BENCH_OFFSET_X = 0.80    # bench seat sits at +/-X from table center

# --- table top : 5 wood planks along Y ---
N_PLANKS = 5
for k in range(N_PLANKS):
    px = -TABLE_D/2 + 0.02 + k * (TABLE_D - 0.04) / (N_PLANKS - 1)
    mat = mat_wood if k % 2 == 0 else mat_wood_lt
    _box(f"top_plank_{k}", (TABLE_D - 0.04) / N_PLANKS * 0.94, TABLE_W, 0.030,
           (px, 0, TABLE_TOP_Z), mat)

# --- 2 bench planks (3 planks each, narrower) ---
for sx in (-1, +1):
    for k in range(3):
        px_off = -BENCH_D/2 + 0.015 + k * (BENCH_D - 0.03) / 2
        mat = mat_wood_lt if k % 2 == 0 else mat_wood
        _box(f"bench_{sx}_{k}",
               (BENCH_D - 0.03) / 3 * 0.95, TABLE_W, 0.025,
               (sx * BENCH_OFFSET_X + px_off, 0, BENCH_Z), mat)

# --- 2 A-frame leg supports under the table ---
# Each support : 2 angled legs forming an "A" + a horizontal cross brace
LEG_W = 0.04
for k, ly in enumerate((-TABLE_W * 0.35, +TABLE_W * 0.35)):
    # 2 diagonal legs (one going to each bench foot)
    for sx in (-1, +1):
        p0 = mathutils.Vector((sx * (BENCH_OFFSET_X + BENCH_D/2), ly, 0.04))
        p1 = mathutils.Vector((0, ly, TABLE_TOP_Z - 0.02))
        d = p1 - p0
        mid = (p0 + p1) * 0.5
        leg = _cyl(f"leg_{k}_{sx}", LEG_W * 0.45, LEG_W * 0.45, d.length, 'Z',
                     (0,0,0), mat_wood, segments=10)
        leg.location = mid
        leg.rotation_mode = 'QUATERNION'
        leg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d.normalized())
    # horizontal cross brace at bench-seat height
    _box(f"brace_{k}", BENCH_OFFSET_X * 2 + BENCH_D, 0.04, 0.025,
           (0, ly, BENCH_Z + 0.012), mat_wood)
    # vertical bench leg supports (small posts under each bench plank near this Y)
    for sx in (-1, +1):
        _box(f"bench_leg_{k}_{sx}", LEG_W, 0.04, BENCH_Z - 0.02,
               (sx * BENCH_OFFSET_X, ly, BENCH_Z / 2),
               mat_wood_lt)

# --- red-and-white checkered tablecloth (a slab with sub-pieces) ---
# We'll model the cloth as a thin red base + 18 white squares in a 3x6 grid
CLOTH_W = TABLE_D - 0.04
CLOTH_L = TABLE_W - 0.10
CLOTH_Z = TABLE_TOP_Z + 0.018
# red base
_box("cloth_base", CLOTH_W, CLOTH_L, 0.002, (0, 0, CLOTH_Z), mat_cloth_r)
# white check squares
N_CX = 4
N_CY = 12
for ix in range(N_CX):
    for iy in range(N_CY):
        if (ix + iy) % 2 == 0:
            continue
        cx = -CLOTH_W/2 + (ix + 0.5) * CLOTH_W / N_CX
        cy = -CLOTH_L/2 + (iy + 0.5) * CLOTH_L / N_CY
        _box(f"check_{ix}_{iy}",
               CLOTH_W / N_CX * 0.92, CLOTH_L / N_CY * 0.92, 0.001,
               (cx, cy, CLOTH_Z + 0.002), mat_cloth_w)

# --- 2 plates on the table ---
for k, (px, py) in enumerate([(0, -TABLE_W * 0.25), (0, TABLE_W * 0.25)]):
    _cyl(f"plate_{k}", 0.10, 0.10, 0.012, 'Z',
           (px, py, CLOTH_Z + 0.010), mat_plate, segments=20)
    # plate inner ring (decorative)
    _cyl(f"plate_rim_{k}", 0.085, 0.085, 0.002, 'Z',
           (px, py, CLOTH_Z + 0.016), mat_cloth_r, segments=20)

# --- 1 glass on the table ---
GL_X = 0.20
GL_Y = 0
GL_Z = CLOTH_Z + 0.005
_cyl("glass_body", 0.030, 0.030, 0.10, 'Z',
       (GL_X, GL_Y, GL_Z + 0.05), mat_glass, segments=18)
# liquid inside
_cyl("glass_liquid", 0.028, 0.028, 0.07, 'Z',
       (GL_X, GL_Y, GL_Z + 0.035), mat_liquid, segments=18)

# --- 1 sandwich (2 bread slices + green filling) ---
SAND_X = -0.18
SAND_Y = 0
SAND_Z_BASE = CLOTH_Z + 0.020
_box("sand_bottom", 0.10, 0.10, 0.030,
       (SAND_X, SAND_Y, SAND_Z_BASE + 0.015), mat_bread)
_box("sand_filling", 0.10, 0.10, 0.020,
       (SAND_X, SAND_Y, SAND_Z_BASE + 0.030 + 0.010), mat_filling)
_box("sand_top", 0.10, 0.10, 0.030,
       (SAND_X, SAND_Y, SAND_Z_BASE + 0.060 + 0.015), mat_bread)

# --- butterfly (animated, parented to pivot empty) ---
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0.5, 0.5, 1.2))
butterfly_pivot = bpy.context.active_object
butterfly_pivot.name = "butterfly_pivot"
# body
body = _cyl("bf_body", 0.005, 0.003, 0.030, 'Y', (0, 0, 0), mat_butterfly_body, segments=8)
body.parent = butterfly_pivot
body.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 4 wings (2 upper + 2 lower), parented to body so they flap
for sx in (-1, +1):
    upper = _box(f"bf_upper_{sx}", 0.040, 0.001, 0.030,
                   (sx * 0.030, 0, 0.005), mat_butterfly_a)
    upper.parent = butterfly_pivot
    upper.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    lower = _box(f"bf_lower_{sx}", 0.030, 0.001, 0.025,
                   (sx * 0.025, 0.010, -0.010), mat_butterfly_b)
    lower.parent = butterfly_pivot
    lower.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# antennae
for sx in (-1, +1):
    ant = _box(f"bf_ant_{sx}", 0.001, 0.012, 0.001,
                 (sx * 0.003, -0.012, 0.005), mat_butterfly_body,
                 rot=(0, 0, sx * math.radians(15)))
    ant.parent = butterfly_pivot
    ant.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : butterfly flies in a circle ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

CIRCLE_R = 0.80
CIRCLE_Z = 1.20
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    a = 2*math.pi * t
    bx = CIRCLE_R * math.cos(a)
    by = CIRCLE_R * math.sin(a)
    bz = CIRCLE_Z + 0.10 * math.sin(2*math.pi*t * 2)
    butterfly_pivot.location = (bx, by, bz)
    # heading : tangent to the circle
    butterfly_pivot.rotation_euler = (0, 0, a + math.pi/2)
    butterfly_pivot.keyframe_insert("location", frame=f)
    butterfly_pivot.keyframe_insert("rotation_euler", frame=f)
if butterfly_pivot.animation_data and butterfly_pivot.animation_data.action:
    for fc in butterfly_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"PIC_OK: {out_glb}", flush=True)
'''


def make_picnic(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_pic_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "PIC_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_picnic(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
