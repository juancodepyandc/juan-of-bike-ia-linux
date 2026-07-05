"""Procedural tower crane (Blender headless).

Lattice mast + operator cabin + main jib + counter-jib + counterweight +
trolley running along the main jib + hook on a cable. Animation : the
whole jib + cabin slews around the mast, the trolley translates along
the jib, and the hook swings below the trolley.

CLI:
  python proc_tower_crane.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "crane.glb"

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

mat_yellow  = pbr_mat("crane_yellow", (0.92, 0.75, 0.10), 0.20, 0.35)
mat_steel   = pbr_mat("steel",        (0.55, 0.57, 0.60), 1.00, 0.35)
mat_dark    = pbr_mat("steel_dark",   (0.15, 0.15, 0.18), 0.90, 0.40)
mat_cable   = pbr_mat("cable",        (0.20, 0.20, 0.22), 0.50, 0.45)
mat_ground  = pbr_mat("ground",       (0.32, 0.32, 0.34), 0.00, 0.85)
mat_glass   = pbr_mat("cab_glass",    (0.10, 0.30, 0.50), 0.00, 0.10)
mat_concrete = pbr_mat("concrete",    (0.50, 0.50, 0.50), 0.00, 0.85)

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

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

# --- ground / concrete pad ----------------------------------------
_box("ground", 3.5, 3.5, 0.04, (0, 0, -0.04), mat_ground)
_box("concrete_pad", 0.50, 0.50, 0.05, (0, 0, 0.025), mat_concrete)

# --- lattice mast (a stacked column of 4-leg rungs) ------------
MAST_BASE_Z = 0.05
MAST_TOP_Z  = 1.80
MAST_W      = 0.20
N_RUNGS     = 8

# 4 vertical legs (corner posts)
for sx in (-1, 1):
    for sy in (-1, 1):
        _box(f"leg_{sx}_{sy}", 0.022, 0.022, MAST_TOP_Z - MAST_BASE_Z,
               (sx * MAST_W/2, sy * MAST_W/2, (MAST_BASE_Z + MAST_TOP_Z)/2), mat_yellow)

# horizontal cross-bars at each rung level
for i in range(N_RUNGS):
    z = MAST_BASE_Z + (i + 0.5) * (MAST_TOP_Z - MAST_BASE_Z) / N_RUNGS
    # X-direction bars (front + back)
    for sy in (-1, 1):
        _box(f"hbar_x_{sy}_{i}", MAST_W, 0.018, 0.018,
               (0, sy * MAST_W/2, z), mat_yellow)
    # Y-direction bars (left + right)
    for sx in (-1, 1):
        _box(f"hbar_y_{sx}_{i}", 0.018, MAST_W, 0.018,
               (sx * MAST_W/2, 0, z), mat_yellow)
    # diagonal X-bracing on the front + back face (visual hint of lattice)
    if i % 2 == 0:
        for sy in (-1, 1):
            _box(f"diag_{sy}_{i}", MAST_W * 1.05, 0.012, 0.012,
                   (0, sy * MAST_W/2, z + 0.06), mat_yellow).rotation_euler = (0, math.radians(30), 0)

# --- slewing pivot (everything above the mast rotates around Z) -----
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, MAST_TOP_Z))
slew_pivot = bpy.context.active_object
slew_pivot.name = "slew_pivot"

# operator cabin
cabin = _box("cabin_body", 0.20, 0.18, 0.18, (0, 0, 0.08), mat_yellow)
cabin.parent = slew_pivot
cabin.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# glass front of cabin
cab_glass = _box("cabin_glass", 0.16, 0.02, 0.12, (0, 0.09, 0.10), mat_glass)
cab_glass.parent = slew_pivot
cab_glass.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- main jib (yellow lattice extending +Y) ------------------------
JIB_L = 1.40
JIB_W = 0.10
JIB_H = 0.12
# top + bottom chord
for sz in (1, -1):
    _b = _box(f"jib_chord_top_{sz}", 0.03, JIB_L, 0.03,
                (0, JIB_L/2, 0.08 + sz * JIB_H/2 + 0.06), mat_yellow)
    _b.parent = slew_pivot
    _b.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 6 cross struts along the jib
for k in range(6):
    z_offset = 0.08 + 0.06
    y_offset = (k + 0.5) * JIB_L / 6
    for diag in (1, -1):
        s = _box(f"jib_diag_{k}_{diag}", 0.020, 0.020, JIB_H,
                   (0, y_offset, z_offset), mat_yellow)
        s.rotation_euler = (math.radians(diag * 30), 0, 0)
        s.parent = slew_pivot
        s.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# tip pulley
tip_pulley = _cyl("jib_tip_pulley", 0.04, 0.04, 0.02, 'X',
                    (0, JIB_L - 0.05, 0.08 + JIB_H/2), mat_dark)
tip_pulley.parent = slew_pivot
tip_pulley.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- counter-jib (shorter, extending -Y) ---------------------------
CJ_L = 0.55
for sz in (1, -1):
    _b = _box(f"cjib_chord_{sz}", 0.025, CJ_L, 0.025,
                (0, -CJ_L/2, 0.08 + sz * JIB_H/2 + 0.06), mat_yellow)
    _b.parent = slew_pivot
    _b.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 3 vertical struts on the counter-jib
for k in range(3):
    s = _box(f"cjib_strut_{k}", 0.02, 0.02, JIB_H,
               (0, -(k + 0.5) * CJ_L / 3, 0.08 + 0.06), mat_yellow)
    s.parent = slew_pivot
    s.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# counterweight (heavy concrete block at the back of the counter-jib)
counterweight = _box("counterweight", 0.18, 0.20, 0.18,
                        (0, -CJ_L + 0.04, 0.08), mat_concrete)
counterweight.parent = slew_pivot
counterweight.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# tie-bars (suspension cables from cabin top to jib tips)
for jib_y, jib_label in [(JIB_L, "jib"), (-CJ_L, "cjib")]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, jib_y/2, 0.30))
    tie = bpy.context.active_object
    tie.name = f"tie_{jib_label}"
    length = math.hypot(abs(jib_y), 0.30 - 0.08)
    tie.scale = (0.008, length, 0.008)
    bpy.ops.object.transform_apply(scale=True)
    angle = math.atan2(0.30 - 0.08, jib_y) - math.pi/2 if jib_y > 0 else \
            math.atan2(0.30 - 0.08, jib_y) - math.pi/2
    # actually for tie above jib pointing from cabin top (0, 0, 0.30) to tip (0, jib_y, 0.08)
    # direction along Y = jib_y, along Z = 0.08 - 0.30 = -0.22
    dz = 0.08 - 0.30
    yaw = math.atan2(dz, jib_y)
    tie.rotation_euler = (yaw, 0, 0)
    tie.location = (0, jib_y/2, (0.30 + 0.08)/2)
    tie.data.materials.append(mat_yellow)
    tie.parent = slew_pivot
    tie.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# cabin "mast top" : a small vertical pole rising above the cabin where the
# tie-bars converge
top_pole = _box("top_pole", 0.04, 0.04, 0.30, (0, 0, 0.30), mat_yellow)
top_pole.parent = slew_pivot
top_pole.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- trolley + hook -----------------------------------------------
# trolley slides along the jib (Y between 0.20 and JIB_L - 0.10)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0.50, 0.08))
trolley_pivot = bpy.context.active_object
trolley_pivot.name = "trolley_pivot"
trolley_pivot.parent = slew_pivot
trolley_pivot.matrix_parent_inverse = mathutils.Matrix.Identity(4)

trolley_box = _box("trolley", 0.10, 0.12, 0.06, (0, 0, 0), mat_dark)
trolley_box.parent = trolley_pivot
trolley_box.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# hook cable
HOOK_DROP = 0.85
cable = _box("hook_cable", 0.005, 0.005, HOOK_DROP,
               (0, 0, -HOOK_DROP/2), mat_cable)
cable.parent = trolley_pivot
cable.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# hook itself (a small inverted U-shape approximation : just a box)
hook = _box("hook", 0.05, 0.05, 0.06, (0, 0, -HOOK_DROP - 0.03), mat_dark)
hook.parent = trolley_pivot
hook.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ---------------------------------------------------
FPS = 30
DURATION = 8.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
# slew_pivot rotates +/- 35 deg around Z (slewing motion)
# trolley translates along Y from 0.30 to JIB_L - 0.10 sin wave
# hook (via cable) swings around the trolley (pendulum in YZ plane)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    slew_pivot.rotation_euler = (0, 0, math.sin(2*math.pi*t) * math.radians(35))
    slew_pivot.keyframe_insert("rotation_euler", frame=f)

    trolley_y = 0.30 + (JIB_L - 0.40) * (0.5 + 0.5 * math.sin(2*math.pi*t * 2))
    trolley_pivot.location = (0, trolley_y, 0.08)
    trolley_pivot.keyframe_insert("location", frame=f)
    # gentle pendulum sway of the hook (rotation around X local)
    trolley_pivot.rotation_euler = (math.sin(2*math.pi*t * 3) * math.radians(8), 0, 0)
    trolley_pivot.keyframe_insert("rotation_euler", frame=f)

for o in (slew_pivot, trolley_pivot):
    if o.animation_data and o.animation_data.action:
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"CRANE_OK: {out_glb}", flush=True)
'''


def make_crane(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_crane_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "CRANE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_crane(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
