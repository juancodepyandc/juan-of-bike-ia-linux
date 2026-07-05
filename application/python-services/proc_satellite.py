"""Procedural satellite (Blender headless).

Cube body + 2 solar panel arrays (extending L/R via hinge arms) + parabolic
dish antenna + small thrusters. Animation : the whole satellite rotates
slowly around Y (yaw), the solar panels nod a few degrees to track the sun,
and the dish rotates around its mount axis.

CLI:
  python proc_satellite.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "satellite.glb"

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
        if emission is not None:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (*emission[0], 1.0)
                bsdf.inputs["Emission Strength"].default_value = emission[1]
    return m

mat_body    = pbr_mat("body_white",   (0.85, 0.85, 0.88), 0.20, 0.35)
mat_gold    = pbr_mat("gold_foil",    (0.86, 0.62, 0.20), 1.00, 0.20)
mat_panel   = pbr_mat("solar_panel",  (0.05, 0.08, 0.30), 0.40, 0.30)
mat_panel_cell = pbr_mat("solar_cell", (0.05, 0.18, 0.45), 0.40, 0.25)
mat_dish    = pbr_mat("dish_white",   (0.92, 0.92, 0.94), 0.10, 0.40)
mat_dark    = pbr_mat("dark_struct",  (0.18, 0.18, 0.20), 0.80, 0.45)
mat_thruster= pbr_mat("thruster_glow",(1.0, 0.55, 0.20), 0.30, 0.25,
                       emission=((1.0, 0.6, 0.2), 2.5))

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

def _cyl(name, R1, R2, depth, axis, location, mat, segments=32):
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

# --- root empty (whole-satellite yaw rotation animation) -----------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
root = bpy.context.active_object
root.name = "sat_root"

# --- body : main central cube + gold-foil wrapping accents -------------
body = _box("body_main", 0.40, 0.40, 0.50, (0, 0, 0), mat_body)
body.parent = root
body.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# gold foil top/bottom plates (thin)
foil_top = _box("foil_top", 0.41, 0.41, 0.02, (0, 0, 0.26), mat_gold)
foil_top.parent = root
foil_top.matrix_parent_inverse = mathutils.Matrix.Identity(4)
foil_bot = _box("foil_bot", 0.41, 0.41, 0.02, (0, 0, -0.26), mat_gold)
foil_bot.parent = root
foil_bot.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# antenna mount on top
mount_pole = _cyl("mount_pole", 0.025, 0.025, 0.12, 'Z', (0, 0, 0.33), mat_dark)
mount_pole.parent = root
mount_pole.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- parabolic dish (cone with flared end + small receiver in front) ----
# Dish itself : cone from small R near pole to wider R, opening upward
mesh_dish = bpy.data.meshes.new("dish_main")
dish = bpy.data.objects.new("dish_main", mesh_dish)
bpy.context.collection.objects.link(dish)
bm = bmesh.new()
# Use a UV sphere with the lower part deleted, scaled flat (gives a bowl).
bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.20)
# delete lower half + scale Z down to flatten
to_del = [v for v in bm.verts if v.co.z < -0.05]
bmesh.ops.delete(bm, geom=to_del, context='VERTS')
# scale Z to make it shallower
bmesh.ops.scale(bm, vec=(1.0, 1.0, 0.5), verts=bm.verts)
bm.to_mesh(mesh_dish); bm.free()
dish.location = (0, 0, 0.44)
dish.data.materials.append(mat_dish)
dish.parent = root
dish.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# receiver/feedhorn : small box in front of the dish
feedhorn = _box("feedhorn", 0.025, 0.025, 0.10, (0, 0, 0.55), mat_dark)
feedhorn.parent = root
feedhorn.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 2 solar panels with hinge arms (extending +X and -X) ---------------
PANEL_W = 0.45
PANEL_L = 1.10
PANEL_T = 0.020
HINGE_R = 0.020
HINGE_L = 0.18

panel_pivots = []
for side in (-1, +1):
    # Hinge arm extending from body to the panel start
    hinge = _cyl(f"hinge_{side}", HINGE_R, HINGE_R, HINGE_L, 'X',
                   (side * (0.20 + HINGE_L/2), 0, 0.05), mat_dark)
    hinge.parent = root
    hinge.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    # Panel pivot empty at the outer end of the hinge
    pivot_x = side * (0.20 + HINGE_L)
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(pivot_x, 0, 0.05))
    pivot = bpy.context.active_object
    pivot.name = f"panel_pivot_{side}"
    pivot.parent = root
    pivot.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    panel_pivots.append(pivot)

    # Panel : a flat box ; centred so its inner edge sits at the pivot
    # (panel half-extent in X = PANEL_L/2 after the _box scaling).
    panel = _box(f"panel_{side}", PANEL_L, PANEL_W, PANEL_T, (0, 0, 0), mat_panel)
    panel.parent = pivot
    panel.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # panel half-width along X = PANEL_L/2 -> place centre at side * PANEL_L/2 so
    # the inner edge lands exactly at the pivot origin
    panel.location = (side * PANEL_L / 2, 0, 0)

    # 3 cell dividers along the panel length (thin metal strips on top)
    for k in range(1, 4):
        cd = _box(f"panel_div_{side}_{k}", 0.006, PANEL_W - 0.01, PANEL_T * 1.4,
                    (0, 0, 0), mat_dark)
        cd.parent = pivot
        cd.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        # spread the 3 dividers evenly along the panel
        cd.location = (side * (k * PANEL_L / 4), 0, 0)

# --- thrusters (small cylinders at the bottom corners) -----------------
for sx in (-1, +1):
    for sy in (-1, +1):
        t = _cyl(f"thruster_{sx}_{sy}", 0.020, 0.012, 0.06, 'Z',
                   (sx * 0.15, sy * 0.15, -0.30), mat_thruster)
        t.parent = root
        t.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation -----------------------------------------------------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3

# Root : slow yaw rotation (1 full turn over 4 s) + slight pitch wobble
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    root.rotation_euler = (math.sin(2*math.pi*t) * math.radians(4),
                            2 * math.pi * t,
                            0)
    root.keyframe_insert("rotation_euler", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Panels : sun-tracking nod (+/- 25 deg around X)
for pivot in panel_pivots:
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        pivot.rotation_euler = (math.sin(2*math.pi*t) * math.radians(25),
                                  0, 0)
        pivot.keyframe_insert("rotation_euler", frame=f)
    if pivot.animation_data and pivot.animation_data.action:
        for fc in pivot.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SATELLITE_OK: {out_glb}", flush=True)
'''


def make_satellite(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_sat_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SATELLITE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_satellite(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
