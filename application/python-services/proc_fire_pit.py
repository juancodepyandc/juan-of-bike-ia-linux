"""Procedural outdoor fire pit (Blender headless).

Grassy ground + circular stone ring (16 rough stones) + iron grate +
ash bed + 6 logs stacked in a teepee/criss-cross pattern + 5 emissive
flame cones rising from the pile + 10 spark spheres ascending. Animation
: flame cones scale Z + rotate slightly while pulsing emission strength
(each on its own phase) + sparks rise linearly and reset.

CLI:
  python proc_fire_pit.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "firepit.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0xF1AE)

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

mat_grass    = pbr_mat("grass",     (0.18, 0.30, 0.12), 0.00, 0.85)
mat_dirt     = pbr_mat("dirt",      (0.30, 0.20, 0.10), 0.00, 0.85)
mat_stone    = pbr_mat("stone",     (0.45, 0.42, 0.40), 0.05, 0.80)
mat_stone_d  = pbr_mat("stone_dk",  (0.30, 0.28, 0.25), 0.05, 0.85)
mat_grate    = pbr_mat("grate",     (0.18, 0.18, 0.20), 0.85, 0.30)
mat_log      = pbr_mat("log_wood",  (0.30, 0.18, 0.08), 0.00, 0.65)
mat_log_b    = pbr_mat("log_burnt", (0.10, 0.06, 0.04), 0.05, 0.55,
                          emission=((1.00, 0.30, 0.10), 1.5))
mat_ash      = pbr_mat("ash",       (0.20, 0.18, 0.16), 0.00, 0.90)

def make_flame_mat(name, base_em=8.0):
    return pbr_mat(name, (1.00, 0.50, 0.15), 0.00, 0.10,
                      alpha=0.80,
                      emission=((1.00, 0.55, 0.20), base_em))

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

def _sphere(name, R, location, mat, u=12, v=8, scale=(1,1,1)):
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

# --- grass + dirt patch ----------------------
_box("grass", 3.5, 3.5, 0.04, (0, 0, -0.04), mat_grass)
# dirt circle inside the stone ring
_cyl("dirt", 0.55, 0.55, 0.015, 'Z', (0, 0, 0.0075), mat_dirt, segments=32)

# --- stone ring : 16 rough stones around the perimeter ---
N_STONES = 16
PIT_R = 0.55
for i in range(N_STONES):
    a = 2*math.pi * i / N_STONES
    cx = PIT_R * math.cos(a); cy = PIT_R * math.sin(a)
    # vary size & height slightly via rng
    R = 0.10 + rng.uniform(-0.02, 0.03)
    H = 0.16 + rng.uniform(-0.02, 0.04)
    # alternate stone shade
    mat = mat_stone if i % 2 == 0 else mat_stone_d
    st = _sphere(f"stone_{i}", R,
                   (cx, cy, H/2 + 0.005),
                   mat, scale=(1.0, 0.9, H / R / 2.0))
    # small random tilt
    st.rotation_euler = (rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1),
                          rng.uniform(-0.5, 0.5))

# --- ash bed inside the pit ----------------
_cyl("ash_bed", 0.42, 0.42, 0.025, 'Z', (0, 0, 0.025), mat_ash, segments=24)

# --- iron grate (4 crossing bars) ----------
GRATE_Z = 0.05
for i in range(4):
    a = i * math.pi/4
    bx = 0.0; by = 0.0
    # rotate the bar around Z by a
    bar = _box(f"grate_bar_{i}", 0.85, 0.012, 0.008,
                 (bx, by, GRATE_Z), mat_grate,
                 rot=(0, 0, a))
# small ring rim
_cyl("grate_rim", 0.44, 0.44, 0.006, 'Z', (0, 0, GRATE_Z - 0.002), mat_grate, segments=32)

# --- logs : 6 logs in a teepee / criss-cross pile -----
LOG_R = 0.045
LOG_LEN = 0.65
LOG_Z = GRATE_Z + 0.05
# 3 logs in one direction at the base
for k, ang in enumerate((0, math.pi/3, -math.pi/3)):
    cx = 0.04 * math.cos(ang + math.pi/2)
    cy = 0.04 * math.sin(ang + math.pi/2)
    log = _cyl(f"log_base_{k}", LOG_R, LOG_R, LOG_LEN, 'X',
                 (cx, cy, LOG_Z + 0.005), mat_log, segments=14)
    log.rotation_euler = (0, 0, ang)
# 3 logs crossing on top (rotated 90 deg + a small tilt up for teepee)
for k, ang in enumerate((math.pi/2, math.pi/2 + math.pi/3, math.pi/2 - math.pi/3)):
    cx = 0.04 * math.cos(ang + math.pi/2)
    cy = 0.04 * math.sin(ang + math.pi/2)
    log = _cyl(f"log_top_{k}", LOG_R * 0.95, LOG_R * 0.95, LOG_LEN, 'X',
                 (cx, cy, LOG_Z + 0.10), mat_log, segments=14)
    log.rotation_euler = (0, math.radians(8), ang)
# a burnt/glowing log at the bottom
glow_log = _cyl("log_glow", LOG_R, LOG_R, LOG_LEN, 'X',
                  (0, 0, GRATE_Z + 0.012), mat_log_b, segments=14)

# --- flame cones (5 emissive cones rising from the pile) ----
flame_mats = []
flame_objs = []
FLAME_BASE_Z = LOG_Z + 0.12
FLAME_DEFS = [
    # (cx, cy, base_R, height, period, phase)
    (0.00,  0.00, 0.10, 0.35, 1.2, 0.0),
    (0.06,  0.03, 0.07, 0.28, 1.5, 0.7),
    (-0.05, 0.04, 0.06, 0.26, 1.3, 1.4),
    (0.04, -0.06, 0.06, 0.24, 1.7, 2.0),
    (-0.04,-0.04, 0.07, 0.30, 1.4, 0.5),
]
for i, (fx, fy, fR, fH, fPer, fPh) in enumerate(FLAME_DEFS):
    fm = make_flame_mat(f"flame_{i}_mat", base_em=8.0)
    flame_mats.append(fm)
    fl = _cyl(f"flame_{i}", fR, 0.005, fH, 'Z',
                (fx, fy, FLAME_BASE_Z + fH/2), fm, segments=14)
    flame_objs.append((fl, fPer, fPh, fH))

# --- sparks : 10 small emissive spheres rising ------
mat_spark = pbr_mat("spark", (1.00, 0.85, 0.30), 0.00, 0.10,
                      emission=((1.00, 0.70, 0.20), 15.0))
sparks = []
for i in range(10):
    a = 2*math.pi * i / 10 + rng.uniform(0, 0.5)
    r = rng.uniform(0.02, 0.20)
    sx = r * math.cos(a)
    sy = r * math.sin(a)
    sp = _sphere(f"spark_{i}", 0.008,
                   (sx, sy, FLAME_BASE_Z + 0.10),
                   mat_spark)
    sparks.append((sp, sx, sy, rng.uniform(0, 1.0)))  # phase offset 0..1

# --- animation -----------------------------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Flames : scale Z oscillates + slight Z rotation jitter + emission flicker.
for i, (fl, period, phase, baseH) in enumerate(flame_objs):
    fm = flame_mats[i]
    bsdf = fm.node_tree.nodes.get("Principled BSDF")
    em = bsdf.inputs["Emission Strength"]
    cycles = DURATION / period
    home_loc = fl.location.copy()
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        ang = 2*math.pi*cycles*t + phase
        s_z = 0.7 + 0.35 * (0.5 + 0.5 * math.sin(ang))
        # secondary fast jitter
        s_z += 0.10 * math.sin(ang * 3.7)
        s_xy = 0.85 + 0.15 * (0.5 + 0.5 * math.sin(ang + 1.0))
        fl.scale = (s_xy, s_xy, s_z)
        fl.rotation_euler = (0, 0, 0.08 * math.sin(ang * 1.5))
        # location follows the scale Z so the base stays planted
        fl.location.z = home_loc.z + (s_z - 1.0) * baseH / 2.0
        fl.keyframe_insert("scale", frame=f)
        fl.keyframe_insert("rotation_euler", frame=f)
        fl.keyframe_insert("location", frame=f)
        em_val = 6.5 + 3.5 * (0.5 + 0.5 * math.sin(ang * 1.3 + 0.3))
        em_val += 1.0 * math.sin(ang * 5.0)
        em.default_value = max(2.0, em_val)
        em.keyframe_insert(data_path="default_value", frame=f)
    if fl.animation_data and fl.animation_data.action:
        for fc in fl.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

# Sparks : Z rises linearly then resets ; emission fades out near the top.
mat_spark_bsdf = mat_spark.node_tree.nodes.get("Principled BSDF")
mat_spark_em = mat_spark_bsdf.inputs["Emission Strength"]
SPARK_BOT = FLAME_BASE_Z + 0.05
SPARK_TOP = FLAME_BASE_Z + 0.80
for (sp, sx, sy, ph) in sparks:
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        local_t = (t * 1.5 + ph) % 1.0
        z = SPARK_BOT + (SPARK_TOP - SPARK_BOT) * local_t
        # slight horizontal drift
        wx = sx + 0.02 * math.sin(2*math.pi * local_t * 3.0 + ph * 6.28)
        wy = sy + 0.02 * math.cos(2*math.pi * local_t * 3.0 + ph * 6.28)
        bpy.context.scene.frame_set(f)
        sp.location = (wx, wy, z)
        sp.keyframe_insert("location", frame=f)
    if sp.animation_data and sp.animation_data.action:
        for fc in sp.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# global spark emission flicker (single shared material, not per-spark, but
# adds a nice flame-tied glow)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    val = 12.0 + 5.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 8.0))
    mat_spark_em.default_value = val
    mat_spark_em.keyframe_insert(data_path="default_value", frame=f)

# glow log : emission strength pulses slow
bsdf_g = mat_log_b.node_tree.nodes.get("Principled BSDF")
em_g = bsdf_g.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_g.default_value = 1.2 + 0.8 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.0))
    bpy.context.scene.frame_set(f)
    em_g.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"PIT_OK: {out_glb}", flush=True)
'''


def make_firepit(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_pit_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "PIT_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_firepit(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
