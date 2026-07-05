"""Procedural low-poly car (Blender headless, bmesh + parent empties).

A stylised low-poly hatchback : chassis + cabin + 4 wheels (rotating with
phase-shifted suspension bob) + headlights + tail lights. Body painted
red, wheels black with chrome hubs.

CLI:
  python proc_car_lowpoly.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "car.glb"

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

mat_paint   = pbr_mat("car_paint_red", (0.70, 0.08, 0.08), 0.20, 0.32)
mat_glass   = pbr_mat("car_glass",     (0.10, 0.12, 0.16), 0.00, 0.05)
mat_tyre    = pbr_mat("tyre_rubber",   (0.05, 0.05, 0.05), 0.00, 0.70)
mat_chrome  = pbr_mat("chrome_hub",    (0.78, 0.80, 0.82), 1.00, 0.16)
mat_head    = pbr_mat("headlight",     (1.00, 0.95, 0.70), 0.30, 0.20)
mat_tail    = pbr_mat("taillight",     (0.85, 0.10, 0.10), 0.30, 0.25)
mat_road    = pbr_mat("asphalt",       (0.18, 0.18, 0.19), 0.00, 0.85)

# --- road plane (visual ground reference) -----------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.05))
road = bpy.context.active_object
road.name = "road"
road.scale = (3.5, 1.6, 0.04)
bpy.ops.object.transform_apply(scale=True)
road.data.materials.append(mat_road)

# --- root empty (suspension bob target) -------------------------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
root = bpy.context.active_object
root.name = "car_root"

def _add_box_obj(name, sx, sy, sz, location, mat, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    if parent is not None:
        obj.parent = parent
        obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        # rebase the location as local relative to parent (assuming parent at origin)
        obj.location = location
    return obj

def _cyl(name, R, depth, axis, location, mat, parent=None):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32,
                            radius1=R, radius2=R, depth=depth)
    if axis == 'X':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'Y'), verts=bm.verts)
    elif axis == 'Y':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'X'), verts=bm.verts)
    bm.to_mesh(mesh); bm.free()
    obj.data.materials.append(mat)
    if parent is not None:
        obj.parent = parent
        obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    obj.location = location
    return obj

# --- chassis (lower body) ---------------------------------------------------
chassis = _add_box_obj("chassis", 2.10, 0.95, 0.32, (0, 0, 0.32), mat_paint, parent=root)
front_grille = _add_box_obj("front_grille", 0.06, 0.65, 0.10,
                              (1.08, 0, 0.22), mat_chrome, parent=root)

# --- cabin (upper, smaller, set back from the front) -----------------------
cabin = _add_box_obj("cabin", 1.10, 0.85, 0.30, (-0.05, 0, 0.62), mat_paint, parent=root)
# Windshield front (angled : we approximate with a tilted thin box)
# Use a regular box for simplicity
windshield = _add_box_obj("windshield", 0.06, 0.78, 0.26,
                            (0.50, 0, 0.62), mat_glass, parent=root)
windshield_rear = _add_box_obj("windshield_rear", 0.06, 0.78, 0.26,
                                  (-0.60, 0, 0.62), mat_glass, parent=root)
# Side windows
for sy in (-1, 1):
    _add_box_obj(f"side_window_{sy}", 0.95, 0.04, 0.22,
                   (-0.05, sy * 0.43, 0.64), mat_glass, parent=root)

# --- headlights & taillights -----------------------------------------------
for sy in (-1, 1):
    _cyl(f"headlight_{sy}", 0.07, 0.04, 'X', (1.06, sy * 0.30, 0.30), mat_head, parent=root)
for sy in (-1, 1):
    _add_box_obj(f"taillight_{sy}", 0.04, 0.16, 0.08,
                   (-1.06, sy * 0.32, 0.34), mat_tail, parent=root)

# --- 4 wheels (rotation animated, each parented to a per-wheel pivot) -----
WHEEL_R = 0.20
WHEEL_W = 0.12
WHEEL_POSITIONS = [
    ( 0.75,  0.50),  # FR
    ( 0.75, -0.50),  # FL
    (-0.75,  0.50),  # RR
    (-0.75, -0.50),  # RL
]
wheel_pivots = []
for i, (wx, wy) in enumerate(WHEEL_POSITIONS):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(wx, wy, WHEEL_R))
    pv = bpy.context.active_object
    pv.name = f"wheel_pivot_{i}"
    pv.parent = root
    pv.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    wheel_pivots.append(pv)

    # tyre (cylinder along Y axis = wheel spin axis)
    tyre = _cyl(f"tyre_{i}", WHEEL_R, WHEEL_W, 'Y', (0, 0, 0), mat_tyre, parent=pv)
    # chrome hub (small disc inset)
    hub = _cyl(f"hub_{i}", WHEEL_R * 0.55, WHEEL_W * 1.05, 'Y', (0, 0, 0), mat_chrome, parent=pv)

# --- animation -------------------------------------------------------------
FPS = 30
DURATION = 3.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# wheels : spin around Y (axle axis) at 3 turns per loop
for pv in wheel_pivots:
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        angle = -3 * 2 * math.pi * t   # negative -> rolling forward (X+)
        bpy.context.scene.frame_set(f)
        pv.rotation_euler = (0, angle, 0)
        pv.keyframe_insert("rotation_euler", frame=f)
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Body : subtle suspension bob (sin Z) + tiny roll (Y)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    root.location = (0, 0, math.sin(2 * math.pi * t * 2) * 0.012)
    root.rotation_euler = (0,
                            math.sin(2 * math.pi * t) * math.radians(1.5),
                            0)
    root.keyframe_insert("location", frame=f)
    root.keyframe_insert("rotation_euler", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"CAR_OK: {out_glb}", flush=True)
'''


def make_car(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_car_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "CAR_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_car(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
