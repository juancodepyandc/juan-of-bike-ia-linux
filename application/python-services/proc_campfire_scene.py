"""Procedural campfire scene with marshmallow stick (Blender headless).

Forest-floor patch + circular stone ring + ash bed + 4 stacked logs +
3 emissive flame cones + 2 wooden logs sliced flat as sitting stumps
on either side + a long stick reaching across the fire with a white
marshmallow on the tip. Animation : flames flicker (3 phases) + the
marshmallow stick rotates so the marshmallow turns over the fire +
marshmallow gradually browns (color shift via 2 mats blend isn't easy,
so we cycle emission strength on a separate "glow" sphere instead).

CLI:
  python proc_campfire_scene.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "campfire.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0xCAFE)

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

mat_floor    = pbr_mat("floor",     (0.20, 0.32, 0.14), 0.00, 0.85)
mat_dirt     = pbr_mat("dirt",      (0.28, 0.18, 0.10), 0.00, 0.85)
mat_stone    = pbr_mat("stone",     (0.45, 0.42, 0.38), 0.05, 0.80)
mat_ash      = pbr_mat("ash",       (0.18, 0.16, 0.14), 0.00, 0.90)
mat_log      = pbr_mat("log",       (0.30, 0.18, 0.08), 0.00, 0.65)
mat_log_g    = pbr_mat("log_glow",  (0.10, 0.06, 0.04), 0.05, 0.55,
                          emission=((1.00, 0.30, 0.10), 2.0))
mat_stump    = pbr_mat("stump",     (0.55, 0.32, 0.16), 0.05, 0.60)
mat_stump_t  = pbr_mat("stump_top", (0.65, 0.40, 0.20), 0.05, 0.55)
mat_stick    = pbr_mat("stick",     (0.20, 0.10, 0.06), 0.05, 0.55)
mat_marsh    = pbr_mat("marsh",     (0.95, 0.92, 0.85), 0.00, 0.45)
mat_marsh_g  = pbr_mat("marsh_glow",(0.92, 0.85, 0.60), 0.00, 0.45,
                          emission=((1.00, 0.55, 0.20), 1.0))

def make_flame_mat(name, base=8.0):
    return pbr_mat(name, (1.00, 0.50, 0.15), 0.00, 0.10,
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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=18, rot=None):
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

# Conventions : campfire at origin. Stumps on +X / -X. Up = +Z.

# --- ground + dirt patch ---
_box("floor", 4.0, 4.0, 0.04, (0, 0, -0.04), mat_floor)
_box("dirt_patch", 2.2, 2.2, 0.025, (0, 0, 0.013), mat_dirt)

# --- stone ring around the fire ---
N_STONES = 12
PIT_R = 0.45
for i in range(N_STONES):
    a = 2*math.pi * i / N_STONES
    cx = PIT_R * math.cos(a)
    cy = PIT_R * math.sin(a)
    R = 0.10 + rng.uniform(-0.02, 0.025)
    H = 0.16 + rng.uniform(-0.02, 0.03)
    st = _sphere(f"stone_{i}", R,
                   (cx, cy, H/2 + 0.005), mat_stone,
                   scale=(1.0, 0.9, H / R / 2.0))
    st.rotation_euler = (rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1),
                          rng.uniform(-0.4, 0.4))

# --- ash bed inside ---
_cyl("ash_bed", 0.36, 0.36, 0.025, 'Z', (0, 0, 0.025), mat_ash, segments=20)

# --- 4 stacked logs ---
LOG_R = 0.05
LOG_LEN = 0.50
# 2 logs in the bottom layer
for k, ang in enumerate((0, math.pi/3)):
    cx = 0.03 * math.cos(ang + math.pi/2)
    cy = 0.03 * math.sin(ang + math.pi/2)
    log = _cyl(f"log_b{k}", LOG_R, LOG_R, LOG_LEN, 'X',
                 (cx, cy, 0.07), mat_log, segments=14)
    log.rotation_euler = (0, 0, ang)
# 2 logs on top
for k, ang in enumerate((math.pi/2, math.pi/2 + math.pi/3)):
    cx = 0.03 * math.cos(ang + math.pi/2)
    cy = 0.03 * math.sin(ang + math.pi/2)
    log = _cyl(f"log_t{k}", LOG_R * 0.95, LOG_R * 0.95, LOG_LEN, 'X',
                 (cx, cy, 0.16), mat_log, segments=14)
    log.rotation_euler = (0, math.radians(5), ang)

# glowing log at bottom (emissive)
glow = _cyl("log_glow", LOG_R, LOG_R, LOG_LEN, 'X',
              (0, 0, 0.025 + 0.012), mat_log_g, segments=14)

# --- 3 flame cones ---
flame_mats = []
flame_objs = []
FLAME_BASE_Z = 0.20
for i in range(3):
    fm = make_flame_mat(f"flame_{i}_mat", base=7.0)
    flame_mats.append(fm)
    fx = (-0.10 + i * 0.10) + rng.uniform(-0.02, 0.02)
    fy = rng.uniform(-0.05, 0.05)
    fH = 0.30 + 0.05 * (i % 2)
    fl = _cyl(f"flame_{i}", 0.05, 0.005, fH, 'Z',
                (fx, fy, FLAME_BASE_Z + fH/2), fm, segments=14)
    flame_objs.append((fl, fH, i * 0.7))

# --- 2 sitting stumps on either side ---
for sx in (-1, +1):
    sx_pos = sx * 1.10
    # main stump body (vertical cylinder)
    _cyl(f"stump_{sx}", 0.16, 0.16, 0.35, 'Z',
           (sx_pos, 0, 0.04 + 0.175), mat_stump, segments=18)
    # darker top slab (where the person sits)
    _cyl(f"stump_top_{sx}", 0.17, 0.17, 0.015, 'Z',
           (sx_pos, 0, 0.04 + 0.357), mat_stump_t, segments=18)

# --- marshmallow stick (animated) ---
# Held by an imaginary person sitting on the +X stump. Stick reaches across.
STICK_BASE_X = +1.10
STICK_BASE_Z = 0.45
STICK_LEN = 0.90
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(STICK_BASE_X, 0, STICK_BASE_Z))
stick_pivot = bpy.context.active_object
stick_pivot.name = "stick_pivot"
stick_pivot.rotation_euler = (0, math.radians(-30), math.radians(-160))

# stick body (long thin cylinder along +Z in local frame, since rotation
# above will swing it forward)
stick = _cyl("stick", 0.008, 0.006, STICK_LEN, 'Z',
               (0, 0, STICK_LEN/2), mat_stick, segments=10)
stick.parent = stick_pivot
stick.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# marshmallow at the tip (white sphere) + smaller glow inner for "browning" hint
marsh = _sphere("marshmallow", 0.040,
                  (0, 0, STICK_LEN + 0.020), mat_marsh,
                  scale=(1.2, 1.2, 1.0))
marsh.parent = stick_pivot
marsh.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# inner glow (warmer color, smaller, behind the marshmallow)
glow_inner = _sphere("marsh_glow", 0.032,
                       (0, 0, STICK_LEN + 0.020), mat_marsh_g,
                       scale=(1.2, 1.2, 1.0))
glow_inner.parent = stick_pivot
glow_inner.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Flames flicker (each cone : scale + jitter + emission strength)
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
        em.default_value = max(2.0, 6.0 + 3.0 * (0.5 + 0.5 * math.sin(ang * 1.3)))
        em.keyframe_insert(data_path="default_value", frame=f)

# Stick rotates : the marshmallow turns over the fire
# We rotate around the local Z axis of the stick (which is the long axis)
# After the initial Y/Z rotations, local Z is roughly horizontal.
# Adding rotation X to the pivot will spin the marshmallow on its skewer.
HOME_ROT = stick_pivot.rotation_euler.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # spin around the stick's long axis (which after our base rotations is
    # roughly aligned with X-ish) — we rotate around X for the marshmallow
    # to turn over the fire
    twist = 2*math.pi * 1.0 * t   # 1 full turn per loop
    stick_pivot.rotation_euler = (HOME_ROT.x + twist, HOME_ROT.y, HOME_ROT.z)
    stick_pivot.keyframe_insert("rotation_euler", frame=f)
if stick_pivot.animation_data and stick_pivot.animation_data.action:
    for fc in stick_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Glowing log emission pulses slow
bsdf_lg = mat_log_g.node_tree.nodes.get("Principled BSDF")
em_lg = bsdf_lg.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_lg.default_value = 1.5 + 1.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 0.7))
    bpy.context.scene.frame_set(f)
    em_lg.keyframe_insert(data_path="default_value", frame=f)

# Marshmallow glow : intensifies over the loop (toasting)
bsdf_mg = mat_marsh_g.node_tree.nodes.get("Principled BSDF")
em_mg = bsdf_mg.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    # ramp 0.5 → 2.0 over the loop
    em_mg.default_value = 0.5 + 1.5 * t + 0.3 * math.sin(2*math.pi*t * 5)
    bpy.context.scene.frame_set(f)
    em_mg.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"CAMP_OK: {out_glb}", flush=True)
'''


def make_camp(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_camp_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "CAMP_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_camp(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
