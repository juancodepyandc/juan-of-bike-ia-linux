"""Procedural traffic light (Blender headless).

Concrete base + tall steel pole + dark housing with 3 lenses (red / yellow
/ green) + 3 hood visors above each lens + small "STOP" sign + arm
extending for the signal controller box. Animation : standard traffic
cycle green (40%) -> yellow (10%) -> red (40%) -> yellow flash (10%)
with the active lens having full emission and the inactive ones near zero.

CLI:
  python proc_traffic_light.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "trafficlight.glb"

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

mat_floor    = pbr_mat("floor",     (0.18, 0.18, 0.20), 0.00, 0.85)
mat_pave     = pbr_mat("pave",      (0.40, 0.38, 0.35), 0.00, 0.85)
mat_steel    = pbr_mat("steel",     (0.40, 0.40, 0.42), 0.70, 0.30)
mat_dark     = pbr_mat("dark",      (0.06, 0.06, 0.07), 0.30, 0.45)
mat_yellow_p = pbr_mat("yellow_p",  (0.85, 0.75, 0.20), 0.10, 0.30)  # signpost yellow
mat_red_off  = pbr_mat("red_off",   (0.35, 0.05, 0.04), 0.05, 0.30,
                          emission=((1.00, 0.18, 0.10), 0.5))
mat_yel_off  = pbr_mat("yel_off",   (0.45, 0.40, 0.10), 0.05, 0.30,
                          emission=((1.00, 0.85, 0.20), 0.5))
mat_grn_off  = pbr_mat("grn_off",   (0.05, 0.35, 0.10), 0.05, 0.30,
                          emission=((0.20, 1.00, 0.30), 0.5))
mat_white    = pbr_mat("white",     (0.92, 0.92, 0.90), 0.00, 0.45)

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=20, rot=None):
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

def _sphere(name, R, location, mat, u=16, v=12, scale=(1,1,1)):
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

# Conventions : housing faces -Y. Up = +Z.

# --- pavement + concrete base ----------
_box("floor", 1.4, 1.4, 0.04, (0, 0, -0.04), mat_floor)
_box("pave_slab", 0.6, 0.6, 0.04, (0, 0, 0.02), mat_pave)
# concrete foundation
_cyl("concrete_base", 0.12, 0.12, 0.10, 'Z', (0, 0, 0.04 + 0.05), mat_pave, segments=18)

# --- main pole ----------------------
POLE_H = 2.40
POLE_BASE_Z = 0.10 + 0.04
_cyl("pole", 0.030, 0.030, POLE_H, 'Z', (0, 0, POLE_BASE_Z + POLE_H/2), mat_steel)
# decorative cap rings (3 small rings near the bottom of the pole)
for k, rz in enumerate((0.10, 0.20, 0.30)):
    _cyl(f"pole_ring_{k}", 0.038, 0.038, 0.010, 'Z',
           (0, 0, POLE_BASE_Z + rz), mat_dark, segments=20)

# --- arm extending forward (-Y direction) holds the housing ---
# The housing is mounted on the front (-Y side) of the pole near the top
HOUSING_Z = POLE_BASE_Z + POLE_H - 0.45
# horizontal mounting arm
_box("mount_arm", 0.025, 0.10, 0.025,
       (0, -0.08, HOUSING_Z + 0.10), mat_steel)
# backing plate behind the housing
_box("backing_plate", 0.16, 0.012, 0.50,
       (0, -0.12, HOUSING_Z), mat_dark)

# --- 3 traffic light lenses (red top, yellow mid, green bottom) ---
# Housing : a tall narrow box on the front of the backing plate
HOUSING_W = 0.14
HOUSING_D = 0.10
HOUSING_H = 0.46
HOUSING_Y = -0.18
_box("housing", HOUSING_W, HOUSING_D, HOUSING_H,
       (0, HOUSING_Y, HOUSING_Z), mat_dark)

# 3 circular lens recess discs, 3 hood visors
LENS_R = 0.040
LENS_Y = HOUSING_Y - HOUSING_D/2 - 0.002
LIGHTS = [
    ("red",    HOUSING_Z + 0.14, mat_red_off),
    ("yellow", HOUSING_Z,        mat_yel_off),
    ("green",  HOUSING_Z - 0.14, mat_grn_off),
]
for name, zc, mat in LIGHTS:
    # outer rim (slightly larger dark disc)
    _cyl(f"{name}_rim", LENS_R + 0.008, LENS_R + 0.008, 0.005, 'Y',
           (0, LENS_Y + 0.001, zc), mat_dark, segments=24)
    # lens (emissive, animated)
    _cyl(f"{name}_lens", LENS_R, LENS_R, 0.010, 'Y',
           (0, LENS_Y - 0.005, zc), mat, segments=24)
    # hood visor : a horizontal half-disc above the lens
    # implement as a thin curved box approximated by a flat slab tilted down
    visor = _box(f"{name}_hood", LENS_R * 2.4, LENS_R * 1.6, 0.005,
                   (0, LENS_Y - LENS_R * 0.7, zc + LENS_R * 0.7), mat_dark,
                   rot=(math.radians(-30), 0, 0))

# --- small "STOP" sign mounted further down on the pole ---
# Approximated as an octagonal disc (8-sided cylinder) painted red, white border
SIGN_Z = POLE_BASE_Z + POLE_H * 0.55
SIGN_Y = -0.15
# red octagon
_cyl("stop_sign", 0.09, 0.09, 0.008, 'Y',
       (0, SIGN_Y, SIGN_Z), mat_red_off, segments=8)
# white border (slightly bigger but thinner)
_cyl("stop_border", 0.095, 0.095, 0.004, 'Y',
       (0, SIGN_Y + 0.003, SIGN_Z), mat_white, segments=8)
# white "STOP" lettering : 4 small white bars on the octagon
for k in range(4):
    _box(f"stop_letter_{k}", 0.015, 0.001, 0.020,
           (-0.030 + k * 0.020, SIGN_Y - 0.005, SIGN_Z), mat_white)
# small mount bracket connecting sign to pole
_box("stop_bracket", 0.10, 0.025, 0.012,
       (0, -0.08, SIGN_Z), mat_steel)

# --- controller box at the base of the pole (the box housing the relays) ---
CTRL_Z = POLE_BASE_Z + 0.30
_box("controller", 0.18, 0.10, 0.30,
       (0.10, 0, CTRL_Z), mat_yellow_p)
# 4 cooling slats on the front of the controller
for k in range(4):
    _box(f"ctrl_slat_{k}", 0.005, 0.001, 0.06,
           (0.10, -0.052, CTRL_Z - 0.08 + k * 0.04), mat_dark)
# small handle / lock on the controller front
_cyl("ctrl_lock", 0.012, 0.012, 0.006, 'Y',
       (0.10, -0.053, CTRL_Z + 0.10), mat_dark)

# --- weather cap on top of pole (a small dome) -----
_sphere("pole_cap", 0.034, (0, 0, POLE_BASE_Z + POLE_H + 0.020), mat_steel,
         scale=(1.0, 1.0, 0.5))

# --- animation : cycle through phases ---
FPS = 30
DURATION = 8.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Phases (fractions of the loop) :
#   0.00 - 0.40 : GREEN
#   0.40 - 0.50 : YELLOW
#   0.50 - 0.90 : RED
#   0.90 - 1.00 : YELLOW flashing (caution)
# The active lens has emission ~15, inactive ~0.1.
def emissions_at(t):
    """Return (red, yellow, green) emission strengths."""
    if t < 0.40:
        return (0.3, 0.3, 15.0)
    elif t < 0.50:
        return (0.3, 15.0, 0.3)
    elif t < 0.90:
        return (15.0, 0.3, 0.3)
    else:
        # caution flash : yellow blinks at 4 Hz
        local = (t - 0.90) / 0.10
        flash = 1.0 if math.sin(local * 2*math.pi * 4) > 0 else 0.0
        return (0.3, 0.3 + flash * 14.0, 0.3)

bsdf_r = mat_red_off.node_tree.nodes.get("Principled BSDF")
bsdf_y = mat_yel_off.node_tree.nodes.get("Principled BSDF")
bsdf_g = mat_grn_off.node_tree.nodes.get("Principled BSDF")
em_r = bsdf_r.inputs["Emission Strength"]
em_y = bsdf_y.inputs["Emission Strength"]
em_g = bsdf_g.inputs["Emission Strength"]

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    er, ey, eg = emissions_at(t)
    bpy.context.scene.frame_set(f)
    em_r.default_value = er
    em_y.default_value = ey
    em_g.default_value = eg
    em_r.keyframe_insert(data_path="default_value", frame=f)
    em_y.keyframe_insert(data_path="default_value", frame=f)
    em_g.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"TL_OK: {out_glb}", flush=True)
'''


def make_tl(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_tl_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "TL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_tl(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
