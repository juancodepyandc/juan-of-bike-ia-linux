"""Procedural sushi platter (Blender headless).

Rectangular wood tray + 8 nigiri sushi (rice base + coloured fish
topping in red/orange/pink/white) + 2 wooden chopsticks + black soy
sauce dish + green wasabi blob. Animation : the whole platter spins
slowly on a turntable.

CLI:
  python proc_sushi_platter.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "sushi.glb"

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

mat_tray    = pbr_mat("tray_wood",   (0.20, 0.10, 0.05), 0.00, 0.55)
mat_tray_lt = pbr_mat("tray_inset",  (0.42, 0.28, 0.15), 0.00, 0.60)
mat_rice    = pbr_mat("rice",        (0.96, 0.94, 0.88), 0.00, 0.50)
mat_salmon  = pbr_mat("salmon",      (0.92, 0.55, 0.25), 0.10, 0.30)
mat_tuna    = pbr_mat("tuna_red",    (0.78, 0.20, 0.18), 0.10, 0.30)
mat_white_f = pbr_mat("white_fish",  (0.92, 0.86, 0.78), 0.10, 0.40)
mat_eel     = pbr_mat("eel_brown",   (0.40, 0.22, 0.08), 0.20, 0.30)
mat_seaweed = pbr_mat("seaweed",     (0.05, 0.10, 0.05), 0.10, 0.50)
mat_stick   = pbr_mat("chopstick",   (0.45, 0.30, 0.15), 0.00, 0.55)
mat_soy     = pbr_mat("soy_sauce",   (0.10, 0.05, 0.02), 0.30, 0.20)
mat_dish    = pbr_mat("dish_black",  (0.05, 0.05, 0.06), 0.10, 0.30)
mat_wasabi  = pbr_mat("wasabi",      (0.55, 0.78, 0.20), 0.00, 0.55)
mat_table   = pbr_mat("table_wood",  (0.30, 0.18, 0.08), 0.00, 0.60)

def _cyl(name, R1, R2, depth, axis, location, mat, segments=20):
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

# --- table -------------------------------------------------
_box("table", 1.4, 1.4, 0.04, (0, 0, -0.04), mat_table)

# --- root empty for turntable spin -----------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
root = bpy.context.active_object
root.name = "platter_root"

# --- tray -----------------------------------------------
TRAY_W = 0.80
TRAY_D = 0.40
TRAY_H = 0.03
tray = _box("tray_outer", TRAY_W, TRAY_D, TRAY_H, (0, 0, TRAY_H/2), mat_tray)
tray.parent = root
tray.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# inner inset (slightly lighter band)
tray_in = _box("tray_inset", TRAY_W * 0.92, TRAY_D * 0.85, 0.005,
                  (0, 0, TRAY_H + 0.003), mat_tray_lt)
tray_in.parent = root
tray_in.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 8 nigiri sushi in 2 rows of 4 ---------------------
NIGIRI_TOPPINGS = [mat_salmon, mat_tuna, mat_white_f, mat_eel] * 2
NIGIRI_W = 0.075
NIGIRI_D = 0.045
NIGIRI_H = 0.025

for i in range(8):
    col = i % 4
    row = i // 4
    nx = (col - 1.5) * (NIGIRI_W * 1.5)
    ny = (row - 0.5) * (NIGIRI_D * 2.0)
    # rice base : a rounded mound
    rice = _box(f"rice_{i}", NIGIRI_W, NIGIRI_D, NIGIRI_H,
                  (nx, ny, TRAY_H + 0.013), mat_rice)
    rice.parent = root
    rice.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # fish topping : a thinner slab on top
    fish = _box(f"fish_{i}", NIGIRI_W * 1.05, NIGIRI_D * 1.05, 0.010,
                  (nx, ny, TRAY_H + NIGIRI_H + 0.006), NIGIRI_TOPPINGS[i])
    fish.parent = root
    fish.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # if eel, add a thin dark stripe (nori band) wrapping around
    if NIGIRI_TOPPINGS[i] is mat_eel:
        band = _box(f"nori_{i}", NIGIRI_W * 1.07, 0.005, NIGIRI_H + 0.012,
                       (nx, ny, TRAY_H + 0.015), mat_seaweed)
        band.parent = root
        band.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- soy sauce dish + wasabi -----------------------------
dish = _cyl("soy_dish", 0.06, 0.06, 0.015, 'Z',
              (TRAY_W/2 - 0.10, 0, TRAY_H + 0.008), mat_dish)
dish.parent = root
dish.matrix_parent_inverse = mathutils.Matrix.Identity(4)
soy = _cyl("soy_liquid", 0.05, 0.05, 0.005, 'Z',
             (TRAY_W/2 - 0.10, 0, TRAY_H + 0.014), mat_soy)
soy.parent = root
soy.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# wasabi blob (small irregular green sphere)
wasabi = _sphere("wasabi", 0.022, (TRAY_W/2 - 0.10, 0.12, TRAY_H + 0.022), mat_wasabi)
wasabi.scale = (1.2, 0.9, 0.8)
wasabi.parent = root
wasabi.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 2 chopsticks alongside the tray --------------------
for sy in (-1, +1):
    stick = _box(f"chopstick_{sy}", 0.28, 0.008, 0.008,
                   (0, sy * (TRAY_D/2 + 0.045), TRAY_H + 0.005), mat_stick)
    stick.parent = root
    stick.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : platter spins slowly ------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    root.rotation_euler = (0, 0, 2 * math.pi * t * 0.5)   # half turn per loop
    root.keyframe_insert("rotation_euler", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SUSHI_OK: {out_glb}", flush=True)
'''


def make_sushi(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_sushi_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SUSHI_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_sushi(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
