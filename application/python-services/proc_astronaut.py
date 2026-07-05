"""Procedural astronaut on EVA (Blender headless).

Full white EVA spacesuit : helmet sphere with gold visor + cylindrical
torso + PLSS backpack + jointed arms (shoulder + forearm) + jointed legs
+ boots + small US flag patch on left shoulder + chest controls box.
Animation : astronaut bobs vertically (zero-g float feel) + left arm
waves slowly.

CLI:
  python proc_astronaut.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "astronaut.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0xA570)

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

mat_space    = pbr_mat("space",    (0.02, 0.02, 0.05), 0.00, 0.95)
mat_suit     = pbr_mat("suit",     (0.95, 0.95, 0.92), 0.10, 0.55)
mat_suit_d   = pbr_mat("suit_d",   (0.78, 0.78, 0.75), 0.10, 0.55)
mat_helmet   = pbr_mat("helmet",   (0.92, 0.92, 0.92), 0.20, 0.20)
mat_visor    = pbr_mat("visor",    (0.85, 0.65, 0.18), 1.00, 0.15,
                          emission=((1.00, 0.85, 0.30), 0.6))
mat_glove    = pbr_mat("glove",    (0.92, 0.92, 0.88), 0.05, 0.65)
mat_boot     = pbr_mat("boot",     (0.85, 0.85, 0.80), 0.10, 0.60)
mat_plss     = pbr_mat("plss",     (0.85, 0.85, 0.85), 0.10, 0.50)
mat_chest    = pbr_mat("chest",    (0.18, 0.18, 0.22), 0.30, 0.40)
mat_flag_r   = pbr_mat("flag_red", (0.85, 0.18, 0.18), 0.05, 0.55)
mat_flag_w   = pbr_mat("flag_wht", (0.95, 0.95, 0.92), 0.05, 0.55)
mat_flag_b   = pbr_mat("flag_blu", (0.18, 0.30, 0.65), 0.05, 0.55)
mat_strap    = pbr_mat("strap",    (0.65, 0.55, 0.45), 0.10, 0.55)
mat_star     = pbr_mat("star",     (1.00, 0.95, 0.85), 0.00, 0.10,
                          emission=((1.00, 0.95, 0.85), 6.0))

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=16, rot=None):
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

def _sphere(name, R, location, mat, u=20, v=14, scale=(1,1,1)):
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

# --- space + stars ---
_box("space_plate", 5.0, 5.0, 0.02, (0, 0, -3.0), mat_space)
for i in range(40):
    a = rng.uniform(0, 2*math.pi)
    r = rng.uniform(2.2, 3.0)
    z = rng.uniform(-2.0, 2.0)
    _sphere(f"star_{i}", rng.uniform(0.010, 0.025),
              (r * math.cos(a), r * math.sin(a), z), mat_star, u=8, v=6)

# --- astronaut pivot (anim float) ---
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
astro = bpy.context.active_object
astro.name = "astronaut_pivot"

# --- torso ---
torso = _cyl("torso", 0.16, 0.14, 0.40, 'Z', (0, 0, 0), mat_suit, segments=20)
torso.parent = astro; torso.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# torso accent (belt)
belt = _cyl("belt", 0.165, 0.165, 0.025, 'Z', (0, 0, -0.18), mat_suit_d, segments=20)
belt.parent = astro; belt.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- pelvis / hip ---
pelvis = _sphere("pelvis", 0.13, (0, 0, -0.24), mat_suit, u=18, v=12,
                   scale=(1.0, 1.0, 0.7))
pelvis.parent = astro; pelvis.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- helmet ---
helmet = _sphere("helmet", 0.14, (0, 0, 0.30), mat_helmet, u=24, v=16)
helmet.parent = astro; helmet.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# gold visor (a smaller golden patch on the front)
visor = _sphere("visor", 0.13, (0, -0.025, 0.30), mat_visor, u=20, v=14,
                  scale=(0.85, 0.5, 0.7))
visor.parent = astro; visor.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# helmet ring at neck
neck_ring = _cyl("neck_ring", 0.13, 0.13, 0.020, 'Z', (0, 0, 0.20),
                   mat_suit_d, segments=20)
neck_ring.parent = astro; neck_ring.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- PLSS backpack ---
backpack = _box("plss", 0.22, 0.10, 0.32, (0, 0.16, 0.02), mat_plss)
backpack.parent = astro; backpack.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 small antennas on the backpack
for sx in (-1, +1):
    _cyl(f"antenna_{sx}", 0.005, 0.005, 0.06, 'Z',
           (sx * 0.08, 0.20, 0.20), mat_suit_d, segments=8).parent = astro

# --- chest controls box ---
chest = _box("chest_controls", 0.14, 0.04, 0.10, (0, -0.16, 0.05), mat_chest)
chest.parent = astro; chest.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 4 small button dots
for k in range(4):
    bx = -0.05 + (k % 2) * 0.10
    bz = 0.08 - (k // 2) * 0.04
    _sphere(f"chest_btn_{k}", 0.008, (bx, -0.18, bz),
              mat_flag_r if k % 2 == 0 else mat_flag_b, u=8, v=6).parent = astro

# --- right arm (shoulder pivot, simple) ---
# upper arm
_cyl("upper_R", 0.045, 0.045, 0.20, 'Z', (0.16, 0, 0.10), mat_suit,
        segments=14).parent = astro
# elbow joint
_sphere("elbow_R", 0.045, (0.16, 0, 0), mat_suit_d, u=12, v=8).parent = astro
# forearm
_cyl("forearm_R", 0.040, 0.040, 0.18, 'Z', (0.16, 0, -0.10), mat_suit,
        segments=14).parent = astro
# glove
_sphere("glove_R", 0.050, (0.16, 0, -0.20), mat_glove, u=14, v=10).parent = astro

# --- left arm (animated, parented to shoulder pivot empty) ---
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(-0.16, 0, 0.18))
arm_L_pivot = bpy.context.active_object
arm_L_pivot.name = "arm_L_pivot"
arm_L_pivot.parent = astro
arm_L_pivot.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# upper arm (extends down from shoulder)
upper_L = _cyl("upper_L", 0.045, 0.045, 0.20, 'Z', (0, 0, -0.10), mat_suit, segments=14)
upper_L.parent = arm_L_pivot; upper_L.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# elbow
elbow_L = _sphere("elbow_L", 0.045, (0, 0, -0.20), mat_suit_d, u=12, v=8)
elbow_L.parent = arm_L_pivot; elbow_L.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# forearm
forearm_L = _cyl("forearm_L", 0.040, 0.040, 0.18, 'Z', (0, 0, -0.30), mat_suit, segments=14)
forearm_L.parent = arm_L_pivot; forearm_L.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# glove
glove_L = _sphere("glove_L", 0.050, (0, 0, -0.40), mat_glove, u=14, v=10)
glove_L.parent = arm_L_pivot; glove_L.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# US flag patch on left shoulder
# red stripes
for k in range(5):
    py = -0.035 + k * 0.014
    _box(f"flag_red_{k}", 0.040, 0.005, 0.008,
           (-0.13, py, 0.15), mat_flag_r).parent = astro
# white stripes (between red)
for k in range(4):
    py = -0.028 + k * 0.014
    _box(f"flag_wht_{k}", 0.040, 0.005, 0.008,
           (-0.13, py, 0.15), mat_flag_w).parent = astro
# blue canton (top-left of flag)
_box("flag_blue", 0.018, 0.005, 0.020, (-0.135, -0.030, 0.158), mat_flag_b).parent = astro

# --- legs ---
for sx in (-1, +1):
    # upper leg
    _cyl(f"upper_leg_{sx}", 0.055, 0.055, 0.25, 'Z',
           (sx * 0.07, 0, -0.40), mat_suit, segments=14).parent = astro
    # knee
    _sphere(f"knee_{sx}", 0.055, (sx * 0.07, 0, -0.52), mat_suit_d, u=12, v=8).parent = astro
    # lower leg
    _cyl(f"lower_leg_{sx}", 0.050, 0.050, 0.22, 'Z',
           (sx * 0.07, 0, -0.64), mat_suit, segments=14).parent = astro
    # boot
    _box(f"boot_{sx}", 0.080, 0.13, 0.06,
           (sx * 0.07, -0.02, -0.78), mat_boot).parent = astro

# --- straps (small dark straps on chest) ---
for k, sx in enumerate((-1, +1)):
    strap = _box(f"strap_{k}", 0.020, 0.04, 0.30,
                   (sx * 0.05, -0.13, 0.05), mat_strap)
    strap.parent = astro
    strap.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Astronaut floats (Z bob) + slight Y sway
HOME_LOC = astro.location.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    z_off = 0.08 * math.sin(2*math.pi*t * 0.4)
    y_off = 0.04 * math.sin(2*math.pi*t * 0.3 + 1.0)
    rot_z = math.radians(5) * math.sin(2*math.pi*t * 0.5)
    astro.location = (HOME_LOC.x, HOME_LOC.y + y_off, HOME_LOC.z + z_off)
    astro.rotation_euler = (0, 0, rot_z)
    astro.keyframe_insert("location", frame=f)
    astro.keyframe_insert("rotation_euler", frame=f)
if astro.animation_data and astro.animation_data.action:
    for fc in astro.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Left arm waves : rotation around X at the shoulder
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # raise arm 90° forward then back
    angle = math.radians(-30) + math.radians(70) * (0.5 + 0.5 * math.sin(2*math.pi*t * 0.7))
    arm_L_pivot.rotation_euler = (angle, 0, math.radians(-15))
    arm_L_pivot.keyframe_insert("rotation_euler", frame=f)
if arm_L_pivot.animation_data and arm_L_pivot.animation_data.action:
    for fc in arm_L_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"AST_OK: {out_glb}", flush=True)
'''


def make_ast(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_ast_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "AST_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_ast(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
