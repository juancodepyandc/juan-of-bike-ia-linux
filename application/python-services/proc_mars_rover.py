"""Procedural Mars rover (Curiosity / Perseverance-style) (Blender headless).

White-ish boxy chassis on 6 wheels (rocker-bogie suspension hinted) +
camera mast with stereo cameras + RTG box on the back + jointed robotic
arm with drill + wheel tracks on dusty mars soil + 2 rocks. Animation
: all 6 wheels spin, the camera mast rotates back and forth, the arm
extends and retracts.

CLI:
  python proc_mars_rover.py <output_glb>
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
import bpy, bmesh, math, mathutils, sys, random

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "rover.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0x4A55)

def pbr_mat(name, color, metal, rough, alpha=None, emission=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if alpha is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
            m.blend_method = 'BLEND'
        if emission is not None and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission[0], 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission[1]
    return m

mat_mars     = pbr_mat("mars",     (0.55, 0.30, 0.18), 0.00, 0.95)
mat_mars_d   = pbr_mat("mars_d",   (0.45, 0.22, 0.12), 0.00, 0.95)
mat_chassis  = pbr_mat("chassis",  (0.85, 0.82, 0.75), 0.10, 0.55)
mat_dark     = pbr_mat("dark",     (0.10, 0.10, 0.12), 0.30, 0.45)
mat_silver   = pbr_mat("silver",   (0.65, 0.65, 0.68), 0.85, 0.30)
mat_tire     = pbr_mat("tire",     (0.08, 0.08, 0.09), 0.05, 0.85)
mat_solar    = pbr_mat("solar",    (0.10, 0.10, 0.40), 0.30, 0.25,
                          emission=((0.20, 0.30, 0.85), 0.5))
mat_rtg      = pbr_mat("rtg",      (0.85, 0.82, 0.78), 0.20, 0.40)
mat_drill    = pbr_mat("drill",    (0.45, 0.45, 0.50), 0.85, 0.30)
mat_camera   = pbr_mat("camera",   (0.10, 0.10, 0.12), 0.30, 0.30,
                          emission=((0.30, 0.55, 1.00), 1.5))
mat_rock     = pbr_mat("rock",     (0.40, 0.25, 0.18), 0.00, 0.90)

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

def _sphere(name, R, location, mat, u=14, v=10, scale=(1,1,1)):
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

# --- mars ground + 2 rocks + wheel tracks ---
_box("mars_ground", 4.0, 3.0, 0.04, (0, 0, -0.04), mat_mars)
# wheel tracks (dark thin lines behind the rover)
for sx in (-1, +1):
    for k in range(5):
        ty = 0.6 + k * 0.30
        _box(f"track_{sx}_{k}", 0.10, 0.20, 0.005,
               (sx * 0.30, ty, 0.022), mat_mars_d)
# 2 rocks
_sphere("rock_1", 0.18, (-1.0, 0.5, 0.10), mat_rock, u=12, v=10,
         scale=(1.4, 1.0, 0.6))
_sphere("rock_2", 0.10, (0.9, 0.7, 0.05), mat_rock, u=10, v=8,
         scale=(1.2, 1.4, 0.5))

# --- main chassis + RTG ---
CHASSIS_Y = -0.30
CHASSIS_Z = 0.20
_box("chassis_box", 0.50, 0.65, 0.20, (0, CHASSIS_Y, CHASSIS_Z), mat_chassis)
# top deck (slightly raised)
_box("deck", 0.45, 0.55, 0.025, (0, CHASSIS_Y, CHASSIS_Z + 0.115), mat_chassis)
# RTG (cylindrical dome on the back)
_cyl("rtg_body", 0.10, 0.10, 0.18, 'Y',
       (0, CHASSIS_Y + 0.40, CHASSIS_Z + 0.05), mat_rtg, segments=14)
# RTG fins (4 radial fins)
for k in range(4):
    a = k * math.pi/2
    sin_a = math.sin(a)
    cos_a = math.cos(a)
    _box(f"rtg_fin_{k}", 0.02, 0.18, 0.04,
           (cos_a * 0.11, CHASSIS_Y + 0.40, CHASSIS_Z + 0.05 + sin_a * 0.04),
           mat_silver, rot=(a, 0, 0))

# --- 6 wheels (3 per side, rocker-bogie hinted with brackets) ---
WHEEL_R = 0.12
WHEEL_W = 0.10
wheels = []
WHEEL_Y_POSITIONS = [-0.50, -0.10, +0.30]
for sx in (-1, +1):
    for i, wy in enumerate(WHEEL_Y_POSITIONS):
        wh = _cyl(f"wheel_{sx}_{i}", WHEEL_R, WHEEL_R, WHEEL_W, 'X',
                    (sx * 0.32, CHASSIS_Y + wy, WHEEL_R), mat_tire, segments=14)
        wheels.append(wh)
        # hub (small chrome disc visible from outside)
        _cyl(f"hub_{sx}_{i}", WHEEL_R * 0.45, WHEEL_R * 0.45, 0.015, 'X',
               (sx * (0.32 + WHEEL_W/2 + 0.005), CHASSIS_Y + wy, WHEEL_R), mat_silver)
        # bracket (small support box from chassis to wheel)
        _box(f"bracket_{sx}_{i}", 0.04, 0.04, 0.10,
               (sx * 0.27, CHASSIS_Y + wy, WHEEL_R + 0.05), mat_dark)

# --- camera mast (vertical pole with stereo cameras on top) ---
MAST_X = 0.0
MAST_Y = CHASSIS_Y - 0.20
MAST_Z_BASE = CHASSIS_Z + 0.13
# pivot for mast rotation
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(MAST_X, MAST_Y, MAST_Z_BASE))
mast_pivot = bpy.context.active_object
mast_pivot.name = "mast_pivot"
# mast pole
pole = _cyl("mast_pole", 0.020, 0.020, 0.45, 'Z',
              (0, 0, 0.225), mat_silver, segments=10)
pole.parent = mast_pivot
pole.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# camera head (rectangular box on top)
head = _box("mast_head", 0.18, 0.08, 0.06, (0, 0, 0.45 + 0.03), mat_dark)
head.parent = mast_pivot
head.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 stereo camera lenses
for sx_h in (-1, +1):
    lens = _cyl(f"cam_lens_{sx_h}", 0.022, 0.022, 0.010, 'Y',
                  (sx_h * 0.06, -0.045, 0.48), mat_camera, segments=12)
    lens.parent = mast_pivot
    lens.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# laser indicator
_sphere("laser_dot", 0.008, (0, -0.045, 0.51),
          pbr_mat("laser", (1.0, 0.30, 0.30), 0.0, 0.10,
                    emission=((1.0, 0.30, 0.30), 6.0))).parent = mast_pivot

# --- robotic arm : 3 segments + drill at the tip (anim extend/retract) ---
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, CHASSIS_Y - 0.30, CHASSIS_Z + 0.05))
arm_pivot = bpy.context.active_object
arm_pivot.name = "arm_pivot"
# segment 1
seg1 = _cyl("arm_seg1", 0.025, 0.025, 0.20, 'Y',
              (0, -0.10, 0), mat_silver, segments=10)
seg1.parent = arm_pivot
seg1.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# joint 1
_sphere("arm_joint1", 0.035, (0, -0.20, 0), mat_dark, u=12, v=8).parent = arm_pivot
# segment 2 (also parented to arm_pivot to keep it simple)
seg2 = _cyl("arm_seg2", 0.020, 0.020, 0.18, 'Y',
              (0, -0.30, 0), mat_silver, segments=10)
seg2.parent = arm_pivot
seg2.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# joint 2
_sphere("arm_joint2", 0.030, (0, -0.40, 0), mat_dark, u=12, v=8).parent = arm_pivot
# drill at the tip
drill_body = _cyl("drill_body", 0.030, 0.025, 0.10, 'Y',
                    (0, -0.46, 0), mat_drill, segments=12)
drill_body.parent = arm_pivot
drill_body.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# drill bit (spiral cylinder)
drill_bit = _cyl("drill_bit", 0.012, 0.005, 0.06, 'Y',
                   (0, -0.54, 0), mat_silver, segments=10)
drill_bit.parent = arm_pivot
drill_bit.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- antennas on the deck ---
_cyl("antenna_pole", 0.005, 0.005, 0.15, 'Z',
       (0.18, CHASSIS_Y - 0.10, CHASSIS_Z + 0.20), mat_silver, segments=8)
_sphere("antenna_disc", 0.025, (0.18, CHASSIS_Y - 0.10, CHASSIS_Z + 0.28),
          mat_silver, u=12, v=10, scale=(1.0, 1.0, 0.3))

# --- animation ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# 6 wheels : spin at constant rate (2 turns / loop)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    angle = 2*math.pi * 2 * t
    for wh in wheels:
        wh.rotation_euler = (angle, 0, 0)
        wh.keyframe_insert("rotation_euler", frame=f)
for wh in wheels:
    if wh.animation_data and wh.animation_data.action:
        for fc in wh.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Camera mast rotates back and forth ±60° around Z
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    mast_pivot.rotation_euler = (0, 0, math.radians(60) * math.sin(2*math.pi*t * 0.6))
    mast_pivot.keyframe_insert("rotation_euler", frame=f)
if mast_pivot.animation_data and mast_pivot.animation_data.action:
    for fc in mast_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Robotic arm : extends and retracts (rotation X around its base)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # rotation X around the arm base : -30° rest → -60° extended → -30°
    angle = math.radians(-30) + math.radians(-35) * (0.5 + 0.5 * math.sin(2*math.pi*t * 0.4))
    arm_pivot.rotation_euler = (angle, 0, 0)
    arm_pivot.keyframe_insert("rotation_euler", frame=f)
if arm_pivot.animation_data and arm_pivot.animation_data.action:
    for fc in arm_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"ROVER_OK: {out_glb}", flush=True)
'''


def make_rover(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_rov_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "ROVER_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_rover(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
