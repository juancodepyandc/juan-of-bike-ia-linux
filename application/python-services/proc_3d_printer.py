"""Procedural 3D printer (Blender headless).

Cube frame + heated print bed + X/Y print head carriage + filament spool +
a slowly-growing test print object. Animation : the print head moves
along X/Y at different frequencies (raster-style), the print object
grows in height over the loop, and the spool rotates as filament feeds.

CLI:
  python proc_3d_printer.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "printer.glb"

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

mat_frame    = pbr_mat("frame_dark", (0.10, 0.10, 0.12), 0.50, 0.42)
mat_bed      = pbr_mat("bed_black",  (0.05, 0.05, 0.06), 0.20, 0.45)
mat_rail     = pbr_mat("rail_steel", (0.62, 0.64, 0.66), 1.00, 0.22)
mat_head     = pbr_mat("head_grey",  (0.45, 0.45, 0.47), 0.40, 0.40)
mat_nozzle   = pbr_mat("nozzle_orange", (0.85, 0.40, 0.10), 0.30, 0.30,
                        emission=((1.0, 0.6, 0.2), 0.8))
mat_filament = pbr_mat("filament_red", (0.85, 0.10, 0.10), 0.20, 0.30)
mat_print    = pbr_mat("print_obj",   (0.85, 0.10, 0.10), 0.20, 0.35)
mat_ground   = pbr_mat("ground_grey", (0.32, 0.32, 0.34), 0.00, 0.85)

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

def _cyl(name, R1, R2, depth, axis, location, mat, segments=24):
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

# --- ground -----------------------------------------------------------
_box("ground", 2.4, 1.8, 0.04, (0, 0, -0.04), mat_ground)

# --- frame : cube with 4 corner posts + top frame --------------------
FRAME_W = 0.80
FRAME_D = 0.70
FRAME_H = 0.90
POST_R  = 0.02

# 4 vertical posts at the corners
for sx in (-1, 1):
    for sy in (-1, 1):
        _box(f"post_{sx}_{sy}", POST_R*2, POST_R*2, FRAME_H,
               (sx * FRAME_W/2, sy * FRAME_D/2, FRAME_H/2), mat_frame)

# top horizontal cross-bars (X-direction front + back, Y-direction left + right)
for sy in (-1, 1):
    _box(f"top_x_{sy}", FRAME_W, POST_R*2, POST_R*2,
           (0, sy * FRAME_D/2, FRAME_H), mat_frame)
for sx in (-1, 1):
    _box(f"top_y_{sx}", POST_R*2, FRAME_D, POST_R*2,
           (sx * FRAME_W/2, 0, FRAME_H), mat_frame)

# bottom frame bars (so it sits properly on the ground)
for sy in (-1, 1):
    _box(f"bot_x_{sy}", FRAME_W, POST_R*2, POST_R*2,
           (0, sy * FRAME_D/2, 0.02), mat_frame)

# --- heated bed (slides along Y) ------------------------------------
BED_W = FRAME_W * 0.75
BED_D = FRAME_D * 0.65
BED_Z = 0.10
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, BED_Z))
bed_pivot = bpy.context.active_object
bed_pivot.name = "bed_pivot"

bed = _box("bed", BED_W, BED_D, 0.03, (0, 0, 0), mat_bed)
bed.parent = bed_pivot
bed.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# Print object on the bed (a small cone "vase" being printed)
mesh_print = bpy.data.meshes.new("print_object")
print_obj = bpy.data.objects.new("print_object", mesh_print)
bpy.context.collection.objects.link(print_obj)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=24,
                        radius1=0.08, radius2=0.05, depth=0.30)
bmesh.ops.translate(bm, vec=(0, 0, 0.15), verts=bm.verts)
bm.to_mesh(mesh_print); bm.free()
print_obj.data.materials.append(mat_print)
print_obj.parent = bed_pivot
print_obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
print_obj.location = (0, 0, 0.015)  # just above bed surface

# --- X-axis carriage : a horizontal bar that the print head rides on
#     (and itself slides along Y between the front + back top rails)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, FRAME_H - 0.05))
y_carriage = bpy.context.active_object
y_carriage.name = "y_carriage"

# X rail bar
x_rail = _box("x_rail", FRAME_W, 0.03, 0.03, (0, 0, 0), mat_rail)
x_rail.parent = y_carriage
x_rail.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- print head (slides along X on the carriage) -------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
head_pivot = bpy.context.active_object
head_pivot.name = "head_pivot"
head_pivot.parent = y_carriage
head_pivot.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# head body
head = _box("print_head", 0.08, 0.10, 0.10, (0, 0, -0.06), mat_head)
head.parent = head_pivot
head.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# heated nozzle (small glowing cone pointing down)
nozzle = _cyl("nozzle", 0.020, 0.005, 0.04, 'Z', (0, 0, -0.135), mat_nozzle)
nozzle.parent = head_pivot
nozzle.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- filament spool (on the side of the frame) ----------------------
spool_x = -(FRAME_W/2 + 0.18)
spool_z = FRAME_H * 0.7
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(spool_x, 0, spool_z))
spool_pivot = bpy.context.active_object
spool_pivot.name = "spool_pivot"

# spool body (a cylinder along X)
spool_body = _cyl("spool_body", 0.12, 0.12, 0.06, 'X', (0, 0, 0), mat_head)
spool_body.parent = spool_pivot
spool_body.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# filament wrapped around the spool : a smaller cylinder
spool_filament = _cyl("spool_filament", 0.105, 0.105, 0.055, 'X', (0, 0, 0), mat_filament)
spool_filament.parent = spool_pivot
spool_filament.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# mounting bracket
_box("spool_bracket", 0.04, 0.06, 0.35,
       (spool_x + 0.08, 0, spool_z - 0.05), mat_frame)

# filament going from spool to head : a thin red line (static)
# (we approximate by a thin cylinder going from spool top to head top)
_box("filament_line", 0.005, 0.005, 0.40,
       ((spool_x + 0) / 2 - 0.08, 0, FRAME_H - 0.20), mat_filament)

# --- animation ----------------------------------------------------
FPS = 30
DURATION = 6.0   # slow so the motion reads
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# Print head : raster motion along X (fast) and Y carriage along Y (slow)
HEAD_X_RANGE = FRAME_W * 0.35
Y_CARR_RANGE = FRAME_D * 0.30

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # head sweeps X at 4 cycles per loop
    head_pivot.location = (math.sin(2*math.pi*t*4) * HEAD_X_RANGE, 0, 0)
    head_pivot.keyframe_insert("location", frame=f)
    # carriage sweeps Y at 1 cycle per loop
    y_carriage.location = (0, math.sin(2*math.pi*t) * Y_CARR_RANGE,
                            FRAME_H - 0.05)
    y_carriage.keyframe_insert("location", frame=f)
    # spool rotates as filament feeds
    spool_pivot.rotation_euler = (-2 * math.pi * t * 2, 0, 0)
    spool_pivot.keyframe_insert("rotation_euler", frame=f)
    # print object slowly scales up its Z height (grows as it prints)
    print_obj.scale = (1, 1, 0.1 + 0.9 * t)
    print_obj.keyframe_insert("scale", frame=f)

for o in (head_pivot, y_carriage, spool_pivot, print_obj):
    if o.animation_data and o.animation_data.action:
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"PRINTER_OK: {out_glb}", flush=True)
'''


def make_printer(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_3dp_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "PRINTER_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_printer(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
