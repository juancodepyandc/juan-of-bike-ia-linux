"""Procedural optical microscope (Blender headless).

Heavy steel base + arm + stage with sample slide + objective revolver
turret with 3 lenses + eyepiece tube + focus knobs. Animation : the
objective revolver rotates between positions, and the stage moves up
and down (Z focus) sin-wave style.

CLI:
  python proc_microscope.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "microscope.glb"

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

mat_body    = pbr_mat("body_grey",   (0.32, 0.32, 0.34), 0.30, 0.40)
mat_dark    = pbr_mat("dark_metal",  (0.12, 0.12, 0.14), 0.80, 0.35)
mat_brass   = pbr_mat("brass",       (0.86, 0.62, 0.20), 1.00, 0.28)
mat_glass   = pbr_mat("lens_glass",  (0.10, 0.20, 0.30), 0.00, 0.05)
mat_stage   = pbr_mat("stage_steel", (0.55, 0.57, 0.60), 1.00, 0.28)
mat_slide   = pbr_mat("slide_white", (0.92, 0.92, 0.90), 0.00, 0.10)
mat_sample  = pbr_mat("sample_red",  (0.78, 0.18, 0.18), 0.20, 0.40)
mat_bench   = pbr_mat("bench_wood",  (0.25, 0.15, 0.08), 0.00, 0.65)

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

# --- bench ----------------------------------------------------
_box("bench", 1.20, 0.80, 0.04, (0, 0, -0.04), mat_bench)

# --- heavy U-shape base + foot ------------------------------
_box("base_foot", 0.40, 0.50, 0.06, (0, 0.05, 0.03), mat_body)
# back of base (where the arm rises)
_box("base_back", 0.20, 0.18, 0.20, (0, 0.30, 0.16), mat_body)

# --- arm : curved S that goes back-up-and-forward ----------
ARM_BACK_Z = 0.25
ARM_TOP_Z  = 0.95
# vertical column
_box("column", 0.08, 0.12, ARM_TOP_Z - ARM_BACK_Z,
       (0, 0.30, (ARM_TOP_Z + ARM_BACK_Z)/2), mat_body)
# horizontal arm at top reaching forward
_box("arm_horizontal", 0.10, 0.30, 0.10,
       (0, 0.15, ARM_TOP_Z + 0.05), mat_body)

# --- focus knob (large brass ring on the side) ------------
_cyl("focus_knob_coarse", 0.08, 0.08, 0.04, 'X', (-0.25, 0.25, 0.20), mat_brass)
_cyl("focus_knob_fine",   0.05, 0.05, 0.035, 'X', (-0.25, 0.25, 0.32), mat_brass)

# --- stage : a horizontal platform with the sample slide ---
# stage has its own pivot for Z focus movement
STAGE_Z = 0.45
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, STAGE_Z))
stage_pivot = bpy.context.active_object
stage_pivot.name = "stage_pivot"

stage = _box("stage_plate", 0.32, 0.32, 0.025, (0, 0, 0), mat_stage)
stage.parent = stage_pivot
stage.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 2 small clip arms on the stage holding the slide
for sx in (-1, 1):
    clip = _box(f"clip_{sx}", 0.025, 0.18, 0.012,
                  (sx * 0.10, 0, 0.018), mat_brass)
    clip.parent = stage_pivot
    clip.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# slide (glass rectangle)
slide = _box("slide", 0.15, 0.06, 0.005, (0, 0, 0.018), mat_slide)
slide.parent = stage_pivot
slide.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# sample on the slide (small red dot)
sample = _box("sample", 0.02, 0.02, 0.004, (0, 0, 0.022), mat_sample)
sample.parent = stage_pivot
sample.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# stage center hole : a small black disc to suggest the light aperture
_cyl("aperture", 0.025, 0.025, 0.005, 'Z', (0, 0, 0.005), mat_dark).parent = stage_pivot

# --- objective revolver turret + 3 objective lenses --------
REVOLVER_Z = ARM_TOP_Z + 0.05 - 0.05   # just below the arm
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0.10, REVOLVER_Z))
revolver_pivot = bpy.context.active_object
revolver_pivot.name = "revolver_pivot"

# turret body (a thick disc oriented vertically)
turret = _cyl("turret", 0.10, 0.10, 0.04, 'Z', (0, 0, 0.0), mat_dark)
turret.parent = revolver_pivot
turret.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 3 objective lenses at 120 deg intervals around the revolver axis
# Each is a small cylinder pointing downward, with a brass collar.
OBJ_R = 0.07   # radial offset from revolver centre
for k in range(3):
    a = k * 2 * math.pi / 3 - math.pi/2   # one objective straight down
    cx = math.cos(a) * OBJ_R
    cy = math.sin(a) * OBJ_R
    # objective tube
    ot = _cyl(f"objective_{k}", 0.015, 0.013, 0.08, 'Z', (cx, cy, -0.06), mat_brass)
    ot.parent = revolver_pivot
    ot.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # lens glass at the tip
    ol = _cyl(f"obj_lens_{k}", 0.012, 0.012, 0.004, 'Z', (cx, cy, -0.105), mat_glass)
    ol.parent = revolver_pivot
    ol.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- eyepiece tube at the very top -----------------------
EYE_Z = ARM_TOP_Z + 0.30
_cyl("eyepiece_tube", 0.04, 0.035, 0.20, 'Z', (0, 0.10, EYE_Z), mat_body)
# eyepiece lens
_cyl("eyepiece_lens", 0.034, 0.034, 0.005, 'Z', (0, 0.10, EYE_Z + 0.105), mat_glass)
# eye cup (small brass collar)
_cyl("eye_cup", 0.038, 0.038, 0.012, 'Z', (0, 0.10, EYE_Z + 0.115), mat_brass)

# --- light source under the stage (small lamp box) -------
_box("light_box", 0.14, 0.14, 0.10, (0, 0, 0.25), mat_dark)
_cyl("light_window", 0.05, 0.05, 0.005, 'Z', (0, 0, 0.31), mat_slide)

# --- animation -------------------------------------------
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
# revolver : steps between 3 positions over the loop (snaps via step interp)
# Use 4 keyframes : 0 -> 120 -> 240 -> 360 deg, with each at t={0, 0.33, 0.67, 1.0}
revolver_keys = [
    (1,            0.0),
    (int(NFR * 0.33), math.radians(120)),
    (int(NFR * 0.67), math.radians(240)),
    (NFR,          math.radians(360)),
]
for (frame, angle) in revolver_keys:
    bpy.context.scene.frame_set(frame)
    revolver_pivot.rotation_euler = (0, 0, angle)
    revolver_pivot.keyframe_insert("rotation_euler", frame=frame)
# CONSTANT interpolation so the revolver snaps from one position to the next
if revolver_pivot.animation_data and revolver_pivot.animation_data.action:
    for fc in revolver_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# stage Z focus : +/- 1 cm Z sin wave (slow focus knob effect)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    stage_pivot.location = (0, 0, STAGE_Z + math.sin(2*math.pi*t * 2) * 0.008)
    stage_pivot.keyframe_insert("location", frame=f)
if stage_pivot.animation_data and stage_pivot.animation_data.action:
    for fc in stage_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"MICROSCOPE_OK: {out_glb}", flush=True)
'''


def make_microscope(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_micro_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "MICROSCOPE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_microscope(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
