"""Procedural Italian wood-fired pizza oven (Blender headless).

Stone hearth base + arched dome of red bricks (built by rotating brick
rows around a half-sphere) + arched opening + chimney + 6 firewood logs
stacked at the back + 3 flame cones licking up + emissive glow at the
mouth + small pizza on a wooden peel resting against the front.
Animation : flames flicker + mouth glow pulses + peel handle bobs
slightly.

CLI:
  python proc_pizza_oven.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "pizzaoven.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0xB17A)

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

mat_floor    = pbr_mat("floor",     (0.30, 0.22, 0.18), 0.00, 0.85)
mat_stone    = pbr_mat("stone",     (0.45, 0.42, 0.38), 0.00, 0.85)
mat_stone_d  = pbr_mat("stone_dk",  (0.32, 0.28, 0.24), 0.00, 0.85)
mat_brick_a  = pbr_mat("brick_red", (0.55, 0.18, 0.10), 0.00, 0.75)
mat_brick_b  = pbr_mat("brick_bgn", (0.65, 0.30, 0.15), 0.00, 0.75)
mat_brick_c  = pbr_mat("brick_dk",  (0.42, 0.14, 0.08), 0.00, 0.78)
mat_mortar   = pbr_mat("mortar",    (0.65, 0.60, 0.50), 0.00, 0.85)
mat_hearth   = pbr_mat("hearth_fl", (0.30, 0.15, 0.08), 0.00, 0.65,
                          emission=((1.00, 0.30, 0.10), 1.0))
mat_glow     = pbr_mat("mouth_glow",(1.00, 0.40, 0.12), 0.00, 0.10,
                          emission=((1.00, 0.45, 0.15), 6.0))
mat_log      = pbr_mat("log",       (0.30, 0.18, 0.08), 0.00, 0.65)
mat_log_g    = pbr_mat("log_glow",  (0.10, 0.06, 0.04), 0.05, 0.55,
                          emission=((1.00, 0.30, 0.10), 2.5))
mat_pizza    = pbr_mat("pizza",     (0.85, 0.55, 0.25), 0.00, 0.55)
mat_cheese   = pbr_mat("cheese",    (0.92, 0.88, 0.55), 0.00, 0.45)
mat_tomato   = pbr_mat("tomato",    (0.85, 0.15, 0.10), 0.00, 0.40)
mat_basil    = pbr_mat("basil",     (0.18, 0.50, 0.20), 0.00, 0.55)
mat_peel_h   = pbr_mat("peel_handle",(0.40, 0.25, 0.10), 0.00, 0.55)
mat_peel_p   = pbr_mat("peel_plate",(0.55, 0.40, 0.20), 0.00, 0.50)

def make_flame_mat(name, base=8.0):
    return pbr_mat(name, (1.00, 0.45, 0.15), 0.00, 0.10,
                      alpha=0.80,
                      emission=((1.00, 0.55, 0.20), base))

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

# --- floor + stone hearth base ----------------
_box("floor", 3.0, 2.5, 0.04, (0, 0, -0.04), mat_floor)
# stone pedestal base
PED_W, PED_D, PED_H = 1.40, 1.20, 0.40
_box("pedestal", PED_W, PED_D, PED_H, (0, 0, PED_H/2), mat_stone_d)
# 4 stones suggesting masonry texture (small bumps)
for i in range(6):
    sx = rng.uniform(-PED_W/2 + 0.10, PED_W/2 - 0.10)
    sy = rng.uniform(-PED_D/2 + 0.05, -0.10)  # front face
    sz = rng.uniform(0.05, PED_H - 0.05)
    _sphere(f"masonry_{i}", 0.05,
              (sx, sy - PED_D/2 - 0.005, sz), mat_stone)

# hearth top slab (flat stone where the pizza sits inside the oven)
HEARTH_Z = PED_H + 0.02
_box("hearth_slab", PED_W * 0.85, PED_D * 0.85, 0.04,
       (0, 0, HEARTH_Z), mat_stone)
# emissive hearth FLOOR (visible through the mouth, dark + warm glow)
_cyl("hearth_floor", 0.55, 0.55, 0.005, 'Z',
       (0, 0.05, HEARTH_Z + 0.025), mat_hearth, segments=40)

# --- dome of red bricks ----------------------
DOME_R   = 0.65
DOME_Z0  = HEARTH_Z + 0.04  # base of dome on the slab
N_ROWS   = 6
N_BRICKS_PER_ROW = 28
BRICK_H  = 0.07
BRICK_T  = 0.08
# We skip bricks where the mouth opening will sit (front, -Y direction)
MOUTH_HALF_DEG = 36  # angle on each side of -Y kept clear
MOUTH_TOP_ROW  = 2   # rows 0..2 (low) have the mouth opening
brick_mats = [mat_brick_a, mat_brick_b, mat_brick_c]
for r in range(N_ROWS):
    # row latitude angle on the half-sphere (0=base, pi/2=apex)
    lat0 = math.pi/2 * (r / N_ROWS)
    lat1 = math.pi/2 * ((r + 1) / N_ROWS)
    z_mid = DOME_Z0 + DOME_R * (math.sin((lat0 + lat1)/2))
    row_R = DOME_R * math.cos((lat0 + lat1)/2)
    row_h = DOME_R * (math.sin(lat1) - math.sin(lat0))
    for i in range(N_BRICKS_PER_ROW):
        ang = 2*math.pi * i / N_BRICKS_PER_ROW
        # if this is a low row AND the angle is near -Y (i.e. angle = 3π/2),
        # skip the brick to make the arched mouth opening
        if r <= MOUTH_TOP_ROW:
            # angle relative to -Y direction
            relative = (ang - 3*math.pi/2) % (2*math.pi)
            if relative > math.pi:
                relative -= 2*math.pi
            if abs(math.degrees(relative)) < MOUTH_HALF_DEG:
                continue
        bx = row_R * math.cos(ang)
        by = row_R * math.sin(ang)
        # brick is a small box tangent to the dome surface
        bm_mat = brick_mats[(r + i) % 3]
        # width adapts to the row circumference
        bw = max(0.04, 2*math.pi * row_R / N_BRICKS_PER_ROW * 0.92)
        b = _box(f"brick_{r}_{i}", BRICK_T, bw, row_h * 0.95,
                   (bx, by, z_mid), bm_mat)
        # rotate the brick so it faces outward (Z up, X = radial out)
        b.rotation_euler = (0, 0, ang)

# small keystone at apex
_sphere("apex", 0.06, (0, 0, DOME_Z0 + DOME_R + 0.005), mat_brick_a)

# arch frame around the mouth (a darker brick arc)
ARCH_R = DOME_R * 0.55
ARCH_Y = -DOME_R + 0.04
N_ARCH = 12
for k in range(N_ARCH):
    ang = math.pi * k / (N_ARCH - 1)  # 0..pi (half circle)
    ax = ARCH_R * math.cos(ang)
    az = DOME_Z0 + 0.05 + ARCH_R * math.sin(ang)
    bm_mat = mat_brick_c if k % 2 == 0 else mat_brick_b
    b = _box(f"arch_brick_{k}", 0.05, 0.10, 0.07,
               (ax, ARCH_Y, az), bm_mat)
    b.rotation_euler = (0, ang, 0)

# glow rectangle in the mouth opening (a slab that's emissive)
_box("mouth_glow", ARCH_R * 1.6, 0.012, ARCH_R * 1.4,
       (0, ARCH_Y - 0.02, DOME_Z0 + 0.05 + ARCH_R * 0.55), mat_glow)

# --- chimney on top of dome ---------------------
CHIM_Z = DOME_Z0 + DOME_R + 0.04
CHIM_H = 0.45
_box("chimney_body", 0.20, 0.20, CHIM_H,
       (0, 0.10, CHIM_Z + CHIM_H/2), mat_brick_a)
# chimney cap (slightly wider)
_box("chimney_cap", 0.26, 0.26, 0.04,
       (0, 0.10, CHIM_Z + CHIM_H + 0.02), mat_stone)

# --- 6 firewood logs stacked next to the oven ----
WOOD_X = 0.95
WOOD_Y = 0.20
# 3 logs in a row at the bottom + 2 + 1 (pyramid stack)
LOG_LEN = 0.42
LOG_R   = 0.045
def add_log(name, x, y, z, mat=mat_log):
    return _cyl(name, LOG_R, LOG_R, LOG_LEN, 'Y',
                  (x, y, z), mat, segments=14)
# bottom row : 3
for k in range(3):
    add_log(f"log_b{k}", WOOD_X, WOOD_Y, LOG_R + 0.005)
# 2 row spacing
for k in range(3):
    add_log(f"log_b2_{k}", WOOD_X + (LOG_R * 2 + 0.005), WOOD_Y, LOG_R + 0.005, mat=mat_log)
# stack of 2 on top
for k in range(2):
    add_log(f"log_t{k}", WOOD_X + LOG_R + k * (LOG_R*2 + 0.005),
              WOOD_Y, LOG_R * 3 + 0.005, mat=mat_log)
# 1 on the very top
add_log("log_top", WOOD_X + LOG_R * 2 + 0.005, WOOD_Y,
           LOG_R * 5 + 0.005, mat=mat_log)

# 2 glowing logs INSIDE the oven (visible through the mouth)
glow1 = _cyl("inside_log_a", LOG_R, LOG_R, 0.30, 'X',
                (-0.10, 0.05, HEARTH_Z + 0.06), mat_log_g, segments=14)
glow2 = _cyl("inside_log_b", LOG_R, LOG_R, 0.28, 'X',
                ( 0.10, 0.08, HEARTH_Z + 0.06), mat_log_g, segments=14)

# --- 3 flames behind the mouth -----------------
flame_mats = []
flame_objs = []
for i in range(3):
    fm = make_flame_mat(f"flame_{i}_mat", base=7.0)
    flame_mats.append(fm)
    fx = (-0.15 + i * 0.15) + rng.uniform(-0.02, 0.02)
    fy = 0.05
    fH = 0.30 + 0.05 * (i % 2)
    fl = _cyl(f"flame_{i}", 0.06, 0.005, fH, 'Z',
                (fx, fy, HEARTH_Z + 0.05 + fH/2), fm, segments=14)
    flame_objs.append((fl, fH, i * 0.7))

# --- pizza peel leaning against the oven front -----
# peel = long wooden handle + flat round plate
PEEL_Y = -PED_D/2 - 0.30
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0.30, PEEL_Y, 0.55))
peel_pivot = bpy.context.active_object
peel_pivot.name = "peel_pivot"
peel_pivot.rotation_euler = (math.radians(-65), 0, math.radians(15))

# handle (long thin cylinder along +Z from pivot)
handle = _cyl("peel_handle", 0.012, 0.012, 0.65, 'Z',
                (0, 0, -0.30), mat_peel_h, segments=10)
handle.parent = peel_pivot; handle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# plate at the tip (-Z end)
plate = _cyl("peel_plate", 0.18, 0.18, 0.008, 'Z',
               (0, 0, -0.65), mat_peel_p, segments=20)
plate.parent = peel_pivot; plate.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# pizza on the plate (a thin orange disc + cheese yellow + 5 tomato red dots
# + 3 small basil green dots)
pizza = _cyl("pizza", 0.16, 0.16, 0.012, 'Z',
                (0, 0, -0.66), mat_pizza, segments=24)
pizza.parent = peel_pivot; pizza.matrix_parent_inverse = mathutils.Matrix.Identity(4)
cheese = _cyl("cheese", 0.14, 0.14, 0.004, 'Z',
                  (0, 0, -0.66 + 0.008), mat_cheese, segments=24)
cheese.parent = peel_pivot; cheese.matrix_parent_inverse = mathutils.Matrix.Identity(4)
for i in range(5):
    a = i * 2*math.pi/5
    tx = 0.09 * math.cos(a); ty = 0.09 * math.sin(a)
    tom = _cyl(f"tomato_{i}", 0.022, 0.022, 0.003, 'Z',
                 (tx, ty, -0.66 + 0.010), mat_tomato, segments=12)
    tom.parent = peel_pivot; tom.matrix_parent_inverse = mathutils.Matrix.Identity(4)
for i in range(3):
    a = i * 2*math.pi/3 + 0.6
    bx = 0.04 * math.cos(a); by = 0.04 * math.sin(a)
    bsl = _box(f"basil_{i}", 0.022, 0.014, 0.003,
                 (bx, by, -0.66 + 0.012), mat_basil)
    bsl.parent = peel_pivot; bsl.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ----------------------------------
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Flames flicker (3 cones, each with own phase + freq)
for i, (fl, baseH, ph) in enumerate(flame_objs):
    fm = flame_mats[i]
    bsdf = fm.node_tree.nodes.get("Principled BSDF")
    em = bsdf.inputs["Emission Strength"]
    freq = 4.0 + (i % 3) * 1.2
    home = fl.location.copy()
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        ang = 2*math.pi*t * freq + ph
        sz = 0.7 + 0.4 * (0.5 + 0.5 * math.sin(ang))
        sxy = 0.85 + 0.15 * (0.5 + 0.5 * math.sin(ang + 1.0))
        fl.scale = (sxy, sxy, sz)
        fl.location.z = home.z + (sz - 1.0) * baseH / 2.0
        fl.keyframe_insert("scale", frame=f)
        fl.keyframe_insert("location", frame=f)
        em_val = 5.5 + 3.5 * (0.5 + 0.5 * math.sin(ang * 1.3))
        em.default_value = max(2.0, em_val)
        em.keyframe_insert(data_path="default_value", frame=f)
    if fl.animation_data and fl.animation_data.action:
        for fc in fl.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

# mouth glow pulses
bsdf_g = mat_glow.node_tree.nodes.get("Principled BSDF")
em_g = bsdf_g.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_g.default_value = 4.5 + 2.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.5))
    bpy.context.scene.frame_set(f)
    em_g.keyframe_insert(data_path="default_value", frame=f)

# inside_log glow pulses
bsdf_lg = mat_log_g.node_tree.nodes.get("Principled BSDF")
em_lg = bsdf_lg.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_lg.default_value = 2.0 + 1.2 * (0.5 + 0.5 * math.sin(2*math.pi*t * 0.7))
    bpy.context.scene.frame_set(f)
    em_lg.keyframe_insert(data_path="default_value", frame=f)

# hearth floor glow pulses slow
bsdf_h = mat_hearth.node_tree.nodes.get("Principled BSDF")
em_h = bsdf_h.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_h.default_value = 0.8 + 0.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 0.5))
    bpy.context.scene.frame_set(f)
    em_h.keyframe_insert(data_path="default_value", frame=f)

# peel handle bobs slightly (rotation Z ±3 deg)
home_rot = peel_pivot.rotation_euler.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    peel_pivot.rotation_euler = (home_rot.x,
                                  home_rot.y,
                                  home_rot.z + math.radians(3.0) * math.sin(2*math.pi*t * 0.5))
    peel_pivot.keyframe_insert("rotation_euler", frame=f)
if peel_pivot.animation_data and peel_pivot.animation_data.action:
    for fc in peel_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"OVEN_OK: {out_glb}", flush=True)
'''


def make_oven(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_oven_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "OVEN_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_oven(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
