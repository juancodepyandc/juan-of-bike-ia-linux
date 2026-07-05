"""Procedural workbench composite scene (Blender headless).

A wooden workbench with three small mechanisms running on it :
  - mini 3-gear train (scaled down)
  - small slider-crank piston (vertical)
  - articulated 3-segment lamp arm

All animated synchronously. Demonstrates that the procedural primitives
compose into multi-mechanism scenes with shared timeline + shared base.

CLI:
  python proc_workbench_scene.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "workbench.glb"

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

mat_wood        = pbr_mat("wood_oak",      (0.42, 0.27, 0.13), 0.0, 0.65)
mat_wood_dark   = pbr_mat("wood_dark",     (0.22, 0.13, 0.07), 0.0, 0.70)
mat_brass       = pbr_mat("brass",         (0.86, 0.62, 0.20), 1.0, 0.28)
mat_steel       = pbr_mat("steel",         (0.62, 0.64, 0.66), 1.0, 0.22)
mat_steel_dark  = pbr_mat("steel_dark",    (0.30, 0.32, 0.34), 1.0, 0.40)
mat_red         = pbr_mat("red_paint",     (0.62, 0.10, 0.10), 0.0, 0.45)
mat_yellow      = pbr_mat("yellow_lamp",   (0.95, 0.85, 0.10), 0.10, 0.30)

FPS, DURATION = 30, 3.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

def _cyl_local(name, R, depth, axis, mat, location=(0,0,0)):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=48,
                            radius1=R, radius2=R, depth=depth)
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

# ============================================================
# WORKBENCH TABLE (wooden top + 4 legs)
# ============================================================
TABLE_W, TABLE_D, TABLE_H = 2.40, 1.20, 0.05
TABLE_Z = 0.90                                # top surface at z = TABLE_Z

table_top = _box("table_top", TABLE_W, TABLE_D, TABLE_H,
                  (0, 0, TABLE_Z - TABLE_H/2), mat_wood)

LEG_W = 0.08
LEG_H = TABLE_Z - TABLE_H
for sx in (-1, 1):
    for sy in (-1, 1):
        _box(f"leg_{('R' if sx>0 else 'L')}{('F' if sy>0 else 'B')}",
              LEG_W, LEG_W, LEG_H,
              (sx * (TABLE_W/2 - 0.10),
               sy * (TABLE_D/2 - 0.10),
               LEG_H / 2),
              mat_wood_dark)

# ============================================================
# MINI GEAR TRAIN (on the left side of the table)
# ============================================================
GR_PIVOT_X = -0.65
GR_PIVOT_Y = 0.00
GR_Z = TABLE_Z + 0.03  # gears float just above the table surface

def _build_gear(name, teeth, R, mat, location):
    """Single-mesh gear via bmesh : body + N teeth + hub."""
    DEPTH, TOOTH_H, TOOTH_W = 0.045, 0.030, 0.028
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=72,
                            radius1=R, radius2=R, depth=DEPTH)
    hx, hy, hz = TOOTH_H * 0.5, TOOTH_W * 0.5, DEPTH * 0.45
    for i in range(teeth):
        a = i * 2 * math.pi / teeth
        rad_x, rad_y = math.cos(a), math.sin(a)
        tan_x, tan_y = -math.sin(a), math.cos(a)
        cx, cy = rad_x * (R + hx), rad_y * (R + hx)
        corners = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    vx = cx + sx*hx*rad_x + sy*hy*tan_x
                    vy = cy + sx*hx*rad_y + sy*hy*tan_y
                    vz = sz * hz
                    corners.append(bm.verts.new((vx, vy, vz)))
        bm.verts.ensure_lookup_table()
        c = corners
        bm.faces.new((c[0], c[4], c[6], c[2]))
        bm.faces.new((c[1], c[3], c[7], c[5]))
        bm.faces.new((c[0], c[1], c[5], c[4]))
        bm.faces.new((c[2], c[6], c[7], c[3]))
        bm.faces.new((c[0], c[2], c[3], c[1]))
        bm.faces.new((c[4], c[5], c[7], c[6]))
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=20,
                            radius1=R*0.16, radius2=R*0.16, depth=DEPTH*1.4)
    bm.normal_update()
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    # rotate so the gear lies flat (axis along Z) -> default cylinder is along Z, OK
    # We want the gear's spin axis to be vertical (along Z) so it spins around Z.
    return obj

R_A, N_A = 0.15, 24
R_B, N_B = 0.10, 16
R_C, N_C = 0.075, 12
gA = _build_gear("wb_gear_A", N_A, R_A, mat_brass, (GR_PIVOT_X,            GR_PIVOT_Y, GR_Z))
gB = _build_gear("wb_gear_B", N_B, R_B, mat_steel, (GR_PIVOT_X + R_A + R_B, GR_PIVOT_Y, GR_Z))
gC = _build_gear("wb_gear_C", N_C, R_C, mat_brass, (GR_PIVOT_X + R_A + 2*R_B + R_C, GR_PIVOT_Y, GR_Z))
# half-tooth phase offset on gear B
gB.rotation_euler = (0, 0, math.pi / N_B)

# gear animation : A=2 turns CCW, B=3 turns CW, C=4 turns CCW per loop
def _animate_rot(obj, axis_idx, base_phase, turns_signed):
    base = list(obj.rotation_euler)
    obj.keyframe_insert("rotation_euler", frame=1)
    base[axis_idx] = base_phase + turns_signed * 2 * math.pi
    obj.rotation_euler = base
    obj.keyframe_insert("rotation_euler", frame=NFR)
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

_animate_rot(gA, 2, 0.0,               +2.0)
_animate_rot(gB, 2, math.pi / N_B,     -3.0)
_animate_rot(gC, 2, 0.0,               +4.0)

# ============================================================
# MINI PISTON-CRANK (centre-right, vertical, sits ON the table)
# ============================================================
PC_X = 0.45
PC_Y = 0.10
PC_Z = TABLE_Z + 0.05  # crank centre just above the table surface so
                       # the rod + piston rise upward from the table

R_CRANK = 0.10
L_ROD   = 0.30
PIST_R  = 0.06

# crank pivot empty (rotates around X)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(PC_X, PC_Y, PC_Z))
crank_pivot = bpy.context.active_object
crank_pivot.name = "wb_crank_pivot"
crank_pivot.rotation_euler = (0, 0, math.pi/2)  # face the camera (crank axis becomes Y)

shaft = _cyl_local("wb_crank_shaft", 0.025, 0.25, 'X', mat_steel_dark)
shaft.parent = crank_pivot
shaft.matrix_parent_inverse = mathutils.Matrix.Identity(4)
disc = _cyl_local("wb_crank_disc", 0.05, 0.025, 'X', mat_red, location=(0.08, 0, 0))
disc.parent = crank_pivot
disc.matrix_parent_inverse = mathutils.Matrix.Identity(4)
pin = _cyl_local("wb_crank_pin", 0.015, 0.04, 'X', mat_brass, location=(0.10, 0, R_CRANK))
pin.parent = crank_pivot
pin.matrix_parent_inverse = mathutils.Matrix.Identity(4)

piston = _cyl_local("wb_piston", PIST_R, 0.07, 'Z', mat_brass,
                     location=(PC_X, PC_Y, PC_Z + R_CRANK + L_ROD/2))
rod = _cyl_local("wb_rod", 0.010, L_ROD, 'Z', mat_steel)
rod.location = (PC_X, PC_Y, PC_Z + R_CRANK + L_ROD/2)

# piston/rod kinematic keyframes
KEY_EVERY = 2
for f in range(1, NFR + 1, KEY_EVERY):
    theta = 2 * math.pi * (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    crank_pivot.rotation_euler = (theta, 0, math.pi/2)
    crank_pivot.keyframe_insert("rotation_euler", frame=f)

    pin_y = -R_CRANK * math.sin(theta)
    pin_z = +R_CRANK * math.cos(theta)
    z_p = pin_z + math.sqrt(L_ROD**2 - pin_y**2)

    piston.location = (PC_X, PC_Y, PC_Z + z_p - 0.035)
    piston.keyframe_insert("location", frame=f)
    rod.location = (PC_X, PC_Y + pin_y/2, PC_Z + (z_p + pin_z)/2)
    rod.rotation_euler = (math.atan2(pin_y, z_p - pin_z), 0, 0)
    rod.keyframe_insert("location", frame=f)
    rod.keyframe_insert("rotation_euler", frame=f)

for o in (crank_pivot, piston, rod):
    if o.animation_data and o.animation_data.action:
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# ============================================================
# ARTICULATED LAMP (back-right corner of the table)
# ============================================================
LAMP_BASE_X = 0.90
LAMP_BASE_Y = 0.40
LAMP_Z = TABLE_Z

# base
_cyl_local("wb_lamp_base", 0.06, 0.025, 'Z', mat_steel_dark,
            location=(LAMP_BASE_X, LAMP_BASE_Y, LAMP_Z + 0.013))

# joint 1 at base
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(LAMP_BASE_X, LAMP_BASE_Y, LAMP_Z + 0.03))
j1 = bpy.context.active_object
j1.name = "wb_lamp_j1"
seg1 = _cyl_local("wb_lamp_seg1", 0.018, 0.30, 'Z', mat_steel)
seg1.parent = j1
seg1.matrix_parent_inverse = mathutils.Matrix.Identity(4)
seg1.location = (0, 0, 0.15)

# joint 2 at top of seg1
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0.30))
j2 = bpy.context.active_object
j2.name = "wb_lamp_j2"
j2.parent = j1
j2.matrix_parent_inverse = mathutils.Matrix.Identity(4)
seg2 = _cyl_local("wb_lamp_seg2", 0.016, 0.25, 'Z', mat_steel)
seg2.parent = j2
seg2.matrix_parent_inverse = mathutils.Matrix.Identity(4)
seg2.location = (0, 0, 0.125)

# lamp head (cone-ish : use a small UV sphere)
mesh_head = bpy.data.meshes.new("wb_lamp_head")
head = bpy.data.objects.new("wb_lamp_head", mesh_head)
bpy.context.collection.objects.link(head)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=0.07)
bm.to_mesh(mesh_head); bm.free()
head.data.materials.append(mat_yellow)
head.parent = j2
head.matrix_parent_inverse = mathutils.Matrix.Identity(4)
head.location = (0, 0, 0.30)

# lamp animation : gentle nodding
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    j1.rotation_euler = (math.sin(2*math.pi*t) * math.radians(10),
                          0,
                          math.cos(2*math.pi*t) * math.radians(20))
    j1.keyframe_insert("rotation_euler", frame=f)
    j2.rotation_euler = (math.sin(2*math.pi*t + math.pi/3) * math.radians(15), 0, 0)
    j2.keyframe_insert("rotation_euler", frame=f)

for o in (j1, j2):
    if o.animation_data and o.animation_data.action:
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# ============================================================
# EXPORT
# ============================================================
bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"WORKBENCH_OK: {out_glb}", flush=True)
'''


def make_workbench(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_workbench_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "WORKBENCH_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_workbench(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
