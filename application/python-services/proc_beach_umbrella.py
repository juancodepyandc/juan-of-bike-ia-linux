"""Procedural beach umbrella with deck chair (Blender headless).

Tilted center pole + canopy made of 8 alternating red/white sectors
forming an octagonal-cone parasol + small finial tip + sand patch + a
striped deck chair lounge nearby + folded beach towel. Animation : the
canopy gently rotates around Z and tilts slightly as if in a sea breeze.

CLI:
  python proc_beach_umbrella.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "umbrella.glb"

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

mat_sand    = pbr_mat("sand",    (0.92, 0.82, 0.55), 0.00, 0.85)
mat_sand_d  = pbr_mat("sand_dk", (0.78, 0.65, 0.40), 0.00, 0.88)
mat_pole    = pbr_mat("pole",    (0.65, 0.45, 0.20), 0.10, 0.40)
mat_red     = pbr_mat("red",     (0.85, 0.18, 0.12), 0.05, 0.55)
mat_white   = pbr_mat("white",   (0.95, 0.95, 0.92), 0.05, 0.50)
mat_chair_w = pbr_mat("chair_w", (0.55, 0.32, 0.16), 0.05, 0.55)
mat_chair_s = pbr_mat("chair_s", (0.85, 0.18, 0.12), 0.00, 0.65)
mat_chair_s2= pbr_mat("chair_s2",(0.95, 0.85, 0.20), 0.00, 0.65)
mat_towel_a = pbr_mat("towel_a", (0.20, 0.50, 0.92), 0.00, 0.70)
mat_towel_b = pbr_mat("towel_b", (0.95, 0.95, 0.92), 0.00, 0.70)
mat_finial  = pbr_mat("finial",  (0.85, 0.65, 0.25), 1.00, 0.25)

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

def _sphere(name, R, location, mat, u=14, v=10):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- sand ---
_box("sand_base", 4.0, 4.0, 0.04, (0, 0, -0.04), mat_sand)
# darker sand patch where the umbrella shadow falls
_cyl("sand_shade", 1.2, 1.2, 0.012, 'Z', (0, 0, 0.012), mat_sand_d, segments=24)

# Umbrella pivot — slight tilt
TILT_Y = math.radians(-8)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
um_root = bpy.context.active_object
um_root.name = "umbrella_root"
um_root.rotation_euler = (0, TILT_Y, 0)

POLE_H = 1.80
POLE_R = 0.025
# pole
pole = _cyl("pole", POLE_R, POLE_R, POLE_H, 'Z',
              (0, 0, POLE_H/2 + 0.02), mat_pole, segments=14)
pole.parent = um_root
pole.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# decorative ferrule near the top
fer = _cyl("pole_ferrule", POLE_R * 1.5, POLE_R * 1.5, 0.025, 'Z',
             (0, 0, POLE_H + 0.02 - 0.06), mat_finial, segments=14)
fer.parent = um_root
fer.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- canopy : 8 alternating red/white sectors (triangular slabs forming an octagonal cone) ---
# canopy_pivot child so we can spin it during animation
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, POLE_H))
canopy_pivot = bpy.context.active_object
canopy_pivot.name = "canopy_pivot"
canopy_pivot.parent = um_root
canopy_pivot.matrix_parent_inverse = mathutils.Matrix.Identity(4)

CANOPY_R = 1.30
CANOPY_DROP = 0.30
N_SEGS = 8
for i in range(N_SEGS):
    a0 = 2*math.pi * i / N_SEGS
    a1 = 2*math.pi * (i + 1) / N_SEGS
    mat = mat_red if i % 2 == 0 else mat_white
    # build a triangle per sector via bmesh : apex at (0,0,0.10) (slightly
    # above tip), 2 base verts on the circle
    mesh = bpy.data.meshes.new(f"canopy_seg_{i}")
    obj = bpy.data.objects.new(f"canopy_seg_{i}", mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    apex = bm.verts.new((0, 0, 0.10))
    # subdivide the arc into 4 short segments
    arc_verts = []
    SUB = 4
    for k in range(SUB + 1):
        ak = a0 + (a1 - a0) * (k / SUB)
        x = CANOPY_R * math.cos(ak)
        y = CANOPY_R * math.sin(ak)
        arc_verts.append(bm.verts.new((x, y, -CANOPY_DROP)))
    for k in range(SUB):
        bm.faces.new([apex, arc_verts[k], arc_verts[k+1]])
    bm.to_mesh(mesh); bm.free()
    obj.data.materials.append(mat)
    obj.parent = canopy_pivot
    obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# decorative finial tip on top
tip = _sphere("canopy_tip", 0.035, (0, 0, 0.15), mat_finial)
tip.parent = canopy_pivot
tip.matrix_parent_inverse = mathutils.Matrix.Identity(4)
tip_spike = _cyl("canopy_spike", 0.008, 0.001, 0.08, 'Z',
                   (0, 0, 0.20), mat_finial, segments=8)
tip_spike.parent = canopy_pivot
tip_spike.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- deck chair nearby (on +Y side) ---
CHAIR_X = 0.5
CHAIR_Y = 1.5
CHAIR_Z = 0.04
# 2 wooden side rails forming the recline angle
RECL = math.radians(-30)  # back tilts back
# horizontal seat section + tilted back section
# Seat
_box("chair_seat", 0.55, 0.55, 0.025,
       (CHAIR_X, CHAIR_Y, 0.20), mat_chair_w)
# 4 legs (low for a beach lounger)
for sx in (-1, +1):
    for sy in (-1, +1):
        _box(f"chair_leg_{sx}_{sy}", 0.020, 0.020, 0.18,
               (CHAIR_X + sx * 0.25, CHAIR_Y + sy * 0.25, 0.10),
               mat_chair_w)
# Backrest (tilted)
_box("chair_back", 0.50, 0.04, 0.55,
       (CHAIR_X, CHAIR_Y - 0.27, 0.40), mat_chair_w,
       rot=(RECL, 0, 0))
# Striped seat fabric (3 stripes)
for k, mat in enumerate([mat_chair_s, mat_chair_s2, mat_chair_s]):
    _box(f"chair_fabric_{k}", 0.50, 0.15, 0.005,
           (CHAIR_X, CHAIR_Y - 0.20 + k * 0.18, 0.215), mat)
# Striped back fabric (3 stripes, tilted)
for k, mat in enumerate([mat_chair_s, mat_chair_s2, mat_chair_s]):
    _box(f"back_fabric_{k}", 0.45, 0.15, 0.005,
           (CHAIR_X, CHAIR_Y - 0.27 + 0.005 * math.sin(RECL),
            0.40 + (k - 1) * 0.13 * math.cos(RECL)),
           mat, rot=(RECL, 0, 0))

# --- folded beach towel near chair ---
TOWEL_X = -0.6
TOWEL_Y = 1.0
_box("towel_blue", 0.40, 0.50, 0.025,
       (TOWEL_X, TOWEL_Y, 0.06), mat_towel_a)
# white stripe across
_box("towel_white", 0.40, 0.10, 0.027,
       (TOWEL_X, TOWEL_Y, 0.06), mat_towel_b)
# rolled corner (small cylinder)
_cyl("towel_roll", 0.035, 0.035, 0.40, 'Y',
       (TOWEL_X - 0.18, TOWEL_Y, 0.07), mat_towel_a, segments=12)

# --- animation ---
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# canopy gently rotates around Z + slight Y tilt sway (breeze)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    spin = math.radians(8) * math.sin(2*math.pi*t * 0.5)
    tilt = math.radians(3) * math.sin(2*math.pi*t * 0.7 + 1.0)
    canopy_pivot.rotation_euler = (tilt, 0, spin)
    canopy_pivot.keyframe_insert("rotation_euler", frame=f)
if canopy_pivot.animation_data and canopy_pivot.animation_data.action:
    for fc in canopy_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"UMB_OK: {out_glb}", flush=True)
'''


def make_umbrella(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_umb_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "UMB_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_umbrella(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
