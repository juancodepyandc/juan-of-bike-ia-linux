"""Procedural antique gramophone (Blender headless).

Wood base box + circular platter + vinyl record on top + tonearm with
needle pointing onto the record + tall brass horn beside the platter
+ crank handle on the side. Animation : record spins, tonearm bobs.

CLI:
  python proc_gramophone.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "gramo.glb"

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

mat_wood       = pbr_mat("wood",        (0.32, 0.18, 0.08), 0.00, 0.50)
mat_wood_dk    = pbr_mat("wood_dark",   (0.20, 0.10, 0.05), 0.00, 0.55)
mat_brass      = pbr_mat("brass",       (0.86, 0.62, 0.20), 1.00, 0.20)
mat_vinyl      = pbr_mat("vinyl",       (0.05, 0.05, 0.05), 0.10, 0.45)
mat_label      = pbr_mat("vinyl_label", (0.78, 0.55, 0.20), 0.00, 0.55)
mat_platter    = pbr_mat("platter",     (0.40, 0.40, 0.42), 0.50, 0.35)
mat_needle     = pbr_mat("needle",      (0.55, 0.57, 0.60), 1.00, 0.25)
mat_table      = pbr_mat("table",       (0.45, 0.35, 0.25), 0.00, 0.60)

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

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

# --- table ----------------------------------------------
_box("table", 1.2, 1.0, 0.04, (0, 0, -0.04), mat_table)

# --- wood base box ---------------------------------------
BASE_W = 0.55
BASE_D = 0.55
BASE_H = 0.10
_box("base", BASE_W, BASE_D, BASE_H, (0, 0, BASE_H/2), mat_wood)
# darker trim around the top
_box("base_trim_top", BASE_W * 1.02, BASE_D * 1.02, 0.02,
       (0, 0, BASE_H + 0.005), mat_wood_dk)

# --- platter (rotating disc) ---------------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, BASE_H + 0.02))
platter_pivot = bpy.context.active_object
platter_pivot.name = "platter_pivot"

PLATTER_R = 0.20
PLATTER_T = 0.015
platter = _cyl("platter", PLATTER_R, PLATTER_R, PLATTER_T, 'Z', (0, 0, 0), mat_platter)
platter.parent = platter_pivot
platter.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# vinyl record (slightly smaller, sits on platter)
vinyl = _cyl("vinyl", PLATTER_R * 0.95, PLATTER_R * 0.95, 0.006, 'Z',
               (0, 0, PLATTER_T/2 + 0.003), mat_vinyl)
vinyl.parent = platter_pivot
vinyl.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# label (orange/brass colored centre)
label = _cyl("vinyl_label", PLATTER_R * 0.30, PLATTER_R * 0.30, 0.008, 'Z',
               (0, 0, PLATTER_T/2 + 0.005), mat_label)
label.parent = platter_pivot
label.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# centre spindle (tiny brass post)
spindle = _cyl("spindle", 0.005, 0.005, 0.04, 'Z',
                 (0, 0, PLATTER_T/2 + 0.02), mat_brass)
spindle.parent = platter_pivot
spindle.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- tonearm pivot (mounted at back-right of base) ----
TONEARM_BASE_X = +0.18
TONEARM_BASE_Y = +0.18
TONEARM_BASE_Z = BASE_H + 0.04
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(TONEARM_BASE_X, TONEARM_BASE_Y, TONEARM_BASE_Z))
tonearm_pivot = bpy.context.active_object
tonearm_pivot.name = "tonearm_pivot"

# tonearm pivot post (short brass cylinder)
_cyl("tonearm_post", 0.025, 0.025, 0.06, 'Z',
       (TONEARM_BASE_X, TONEARM_BASE_Y, BASE_H + 0.03), mat_brass)

# tonearm itself (a thin curved-ish bar - approximate with 2 segments)
# Build as a child of tonearm_pivot, extending from origin out toward the vinyl
arm1 = _box("tonearm_arm1", 0.24, 0.015, 0.012, (-0.12, 0, 0.04), mat_brass)
arm1.parent = tonearm_pivot
arm1.matrix_parent_inverse = mathutils.Matrix.Identity(4)
arm1.location = (-0.12, 0, 0.04)
# needle holder (small box at the end of the arm)
holder = _box("needle_holder", 0.04, 0.030, 0.025, (-0.24, 0, 0.03), mat_brass)
holder.parent = tonearm_pivot
holder.matrix_parent_inverse = mathutils.Matrix.Identity(4)
holder.location = (-0.24, 0, 0.03)
# needle (tiny cone pointing down)
needle = _cyl("needle", 0.005, 0.001, 0.018, 'Z', (-0.24, 0, 0.01), mat_needle)
needle.parent = tonearm_pivot
needle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
needle.location = (-0.24, 0, 0.01)

# --- brass horn (large flared cone on the side) -------
# Horn flares from a small mouth (near base back-left) up + out
HORN_BASE = (-0.20, -0.20, BASE_H + 0.06)
# build as a cone with R1 small and R2 large, oriented mostly +Z
horn = _cyl("horn", 0.04, 0.28, 0.50, 'Z',
              (HORN_BASE[0], HORN_BASE[1], HORN_BASE[2] + 0.25), mat_brass)
# tilt the horn outward (positive X tilt + negative Y so the bell faces up+out)
horn.rotation_euler = (math.radians(15), 0, math.radians(-30))

# horn neck : a short cylinder connecting horn to base
neck = _cyl("horn_neck", 0.025, 0.025, 0.10, 'Z',
              (HORN_BASE[0], HORN_BASE[1], HORN_BASE[2] - 0.05), mat_brass)

# --- crank handle on the right side ----------------------
crank_x = BASE_W/2 + 0.02
crank = _cyl("crank_arm", 0.012, 0.012, 0.10, 'X',
               (crank_x, 0, BASE_H/2 + 0.04), mat_brass)
crank_grip = _cyl("crank_grip", 0.020, 0.020, 0.06, 'Y',
                    (crank_x + 0.07, 0, BASE_H/2 + 0.04), mat_wood)

# --- animation -------------------------------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# platter spins : 78 RPM real, but we slow for visibility - 3 turns per 6 s
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    platter_pivot.rotation_euler = (0, 0, 3 * 2 * math.pi * t)
    platter_pivot.keyframe_insert("rotation_euler", frame=f)
if platter_pivot.animation_data and platter_pivot.animation_data.action:
    for fc in platter_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# tonearm subtle drift inward (rotation Z) + slight bob (rotation X)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # drift -10 deg over the loop (mimics the needle moving inward as the
    # record plays) ; then reset at the end
    drift_z = -10 * math.sin(2*math.pi*t * 0.5) * math.pi / 180
    bob_x = math.sin(2*math.pi*t * 3) * math.radians(0.5)
    tonearm_pivot.rotation_euler = (bob_x, 0, drift_z)
    tonearm_pivot.keyframe_insert("rotation_euler", frame=f)
if tonearm_pivot.animation_data and tonearm_pivot.animation_data.action:
    for fc in tonearm_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"GRAMO_OK: {out_glb}", flush=True)
'''


def make_gramo(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_gramo_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "GRAMO_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_gramo(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
