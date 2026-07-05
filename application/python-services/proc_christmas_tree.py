"""Procedural decorated Christmas tree (Blender headless).

Wooden trunk on a base + 4 stacked conical foliage layers + 12 colored
ornaments + 8 fairy lights along the branches (emissive, flicker in a
chain) + a 5-point gold star at the apex + 3 wrapped gift boxes piled
at the foot. Animation : fairy lights flicker in sequence (chained
delay) + star pulses + a single ornament rotates slowly.

CLI:
  python proc_christmas_tree.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "xmas.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0xCE1E)

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

mat_floor    = pbr_mat("floor",    (0.45, 0.25, 0.12), 0.00, 0.85)
mat_carpet   = pbr_mat("carpet",   (0.55, 0.10, 0.10), 0.00, 0.75)
mat_base     = pbr_mat("base",     (0.30, 0.18, 0.08), 0.05, 0.55)
mat_trunk    = pbr_mat("trunk",    (0.30, 0.18, 0.08), 0.05, 0.65)
mat_leaf_a   = pbr_mat("leaf_a",   (0.10, 0.45, 0.20), 0.00, 0.65)
mat_leaf_b   = pbr_mat("leaf_b",   (0.15, 0.55, 0.22), 0.00, 0.60)
mat_orn_r    = pbr_mat("orn_r",    (0.85, 0.18, 0.12), 0.85, 0.15)
mat_orn_g    = pbr_mat("orn_g",    (0.18, 0.65, 0.25), 0.85, 0.15)
mat_orn_b    = pbr_mat("orn_b",    (0.20, 0.45, 0.92), 0.85, 0.15)
mat_orn_y    = pbr_mat("orn_y",    (0.95, 0.85, 0.20), 0.85, 0.15)
mat_orn_pur  = pbr_mat("orn_pur",  (0.55, 0.20, 0.65), 0.85, 0.15)
mat_orn_pink = pbr_mat("orn_pink", (0.95, 0.45, 0.65), 0.85, 0.15)
mat_star     = pbr_mat("star",     (0.95, 0.85, 0.20), 1.00, 0.20,
                          emission=((1.00, 0.85, 0.30), 5.0))
mat_gift_a   = pbr_mat("gift_a",   (0.85, 0.18, 0.12), 0.10, 0.45)
mat_gift_b   = pbr_mat("gift_b",   (0.20, 0.45, 0.92), 0.10, 0.45)
mat_gift_c   = pbr_mat("gift_c",   (0.20, 0.65, 0.25), 0.10, 0.45)
mat_ribbon   = pbr_mat("ribbon",   (0.95, 0.85, 0.20), 0.05, 0.45)

# fairy light materials (one shared base, but emission strength keyframed)
mat_light_red    = pbr_mat("light_red",    (1.00, 0.20, 0.20), 0.00, 0.10,
                              emission=((1.00, 0.25, 0.20), 0.0))
mat_light_yellow = pbr_mat("light_yellow", (1.00, 0.85, 0.20), 0.00, 0.10,
                              emission=((1.00, 0.85, 0.30), 0.0))
mat_light_green  = pbr_mat("light_green",  (0.30, 1.00, 0.40), 0.00, 0.10,
                              emission=((0.40, 1.00, 0.50), 0.0))
mat_light_blue   = pbr_mat("light_blue",   (0.30, 0.55, 1.00), 0.00, 0.10,
                              emission=((0.40, 0.65, 1.00), 0.0))

LIGHT_MATS = [mat_light_red, mat_light_yellow, mat_light_green, mat_light_blue]

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

def _sphere(name, R, location, mat, u=18, v=14, scale=(1,1,1)):
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

# --- floor + carpet ---
_box("floor", 3.0, 3.0, 0.04, (0, 0, -0.04), mat_floor)
_cyl("carpet", 1.40, 1.40, 0.020, 'Z', (0, 0, 0.010), mat_carpet, segments=32)

# --- base stand + trunk ---
_cyl("tree_base", 0.20, 0.20, 0.06, 'Z', (0, 0, 0.05), mat_base, segments=18)
TRUNK_H = 0.25
_cyl("trunk", 0.040, 0.035, TRUNK_H, 'Z',
       (0, 0, 0.08 + TRUNK_H/2), mat_trunk, segments=14)

# --- 4 stacked foliage cones (decreasing radius, alternating shade) ---
FOLIAGE_BASE_Z = 0.08 + TRUNK_H
LAYERS = [
    (0.60, 0.50, 0.50, mat_leaf_a),   # (R_base, R_tip, height, mat)
    (0.45, 0.35, 0.45, mat_leaf_b),
    (0.32, 0.22, 0.40, mat_leaf_a),
    (0.20, 0.005, 0.40, mat_leaf_b),
]
running_z = FOLIAGE_BASE_Z
LAYER_INFO = []   # collected R for placing ornaments
for k, (R_b, R_t, H, mat) in enumerate(LAYERS):
    z_mid = running_z + H/2
    _cyl(f"foliage_{k}", R_b, R_t, H, 'Z', (0, 0, z_mid), mat, segments=24)
    LAYER_INFO.append((R_b, R_t, z_mid - H/2, z_mid + H/2))
    running_z += H * 0.7  # overlap layers
TREE_TOP_Z = running_z + 0.10

# --- 12 ornament balls hanging on the lower 3 layers ---
ORN_MATS = [mat_orn_r, mat_orn_g, mat_orn_b, mat_orn_y, mat_orn_pur, mat_orn_pink]
ornament_objs = []
for i in range(12):
    layer_idx = i % 3  # spread across lower 3 layers
    R_b, R_t, z_lo, z_hi = LAYER_INFO[layer_idx]
    # angle around the tree
    a = i * 2*math.pi/12 + (layer_idx * 0.3)
    # find a position on the cone surface (linear interp R_b → R_t at random Z)
    u = rng.uniform(0.2, 0.8)
    z = z_lo + u * (z_hi - z_lo)
    r_here = R_b + (R_t - R_b) * u
    ox = r_here * 1.02 * math.cos(a)
    oy = r_here * 1.02 * math.sin(a)
    orn_mat = ORN_MATS[i % len(ORN_MATS)]
    orn = _sphere(f"ornament_{i}", 0.035, (ox, oy, z), orn_mat,
                    u=14, v=10)
    ornament_objs.append(orn)
    # small chrome cap on top of ornament
    _cyl(f"orn_cap_{i}", 0.012, 0.012, 0.012, 'Z',
           (ox, oy, z + 0.040), mat_orn_y, segments=8)

# --- 8 fairy lights along the foliage (spiraling around) ---
light_objs = []
for i in range(8):
    a = i * 2*math.pi/8 * 1.5  # spiral angle
    layer_idx = i % 4
    R_b, R_t, z_lo, z_hi = LAYER_INFO[layer_idx]
    u = (i / 8)  # height progresses up the tree
    z = FOLIAGE_BASE_Z + 0.08 + u * (TREE_TOP_Z - FOLIAGE_BASE_Z - 0.15)
    # radius at that height : linear interp between layer Rs (approximate)
    r_here = R_b * (1 - u) + 0.05 * u
    lx = r_here * 1.05 * math.cos(a)
    ly = r_here * 1.05 * math.sin(a)
    mat = LIGHT_MATS[i % len(LIGHT_MATS)]
    light = _sphere(f"light_{i}", 0.018, (lx, ly, z), mat, u=10, v=8)
    light_objs.append((light, mat, i))

# --- gold star on top ---
# approximated as a flattened sphere (visible from a distance as a 5-point shape)
_sphere("tree_star", 0.06, (0, 0, TREE_TOP_Z + 0.08), mat_star, u=14, v=10,
         scale=(1.0, 0.3, 1.0))
# 4 spike arms (small boxes radiating)
for i in range(4):
    a = i * math.pi/2
    sp = _box(f"star_spike_{i}", 0.018, 0.005, 0.09,
                (0, 0, TREE_TOP_Z + 0.08), mat_star,
                rot=(0, a, 0))

# --- 3 wrapped gift boxes at the base ---
GIFT_DEFS = [
    (-0.50, 0.20, 0, 0.30, 0.20, 0.15, mat_gift_a),
    (+0.40, 0.30, 0, 0.25, 0.25, 0.20, mat_gift_b),
    (-0.10, -0.40, 0, 0.20, 0.30, 0.18, mat_gift_c),
]
for k, (gx, gy, gz_off, gw, gd, gh, gmat) in enumerate(GIFT_DEFS):
    _box(f"gift_{k}", gw, gd, gh, (gx, gy, gh/2 + 0.025), gmat)
    # ribbon : 2 perpendicular strips
    _box(f"ribbon_{k}_X", gw + 0.005, 0.020, gh + 0.005,
           (gx, gy, gh/2 + 0.025), mat_ribbon)
    _box(f"ribbon_{k}_Y", 0.020, gd + 0.005, gh + 0.005,
           (gx, gy, gh/2 + 0.025), mat_ribbon)
    # bow (small sphere on top)
    _sphere(f"ribbon_bow_{k}", 0.035, (gx, gy, gh + 0.025), mat_ribbon,
              u=12, v=10, scale=(1.0, 1.0, 0.5))

# --- animation ---
FPS = 30
DURATION = 8.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Fairy lights : chained delay flicker
# Each light_i has phase = i/8 (so lights "travel" around the tree)
# Each light gets its own material (4 mats shared between 8 lights) — we
# animate the per-material emission strength for each unique material.
# But since 2 lights share each mat, we need per-light emission. Solution:
# create unique materials per light index.

# Re-do : create 8 separate materials for individual flicker control
unique_light_mats = []
for i in range(8):
    color_base = LIGHT_MATS[i % 4].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value
    mat_u = pbr_mat(f"light_unique_{i}",
                      (color_base[0], color_base[1], color_base[2]), 0.00, 0.10,
                      emission=((color_base[0], color_base[1], color_base[2]), 0.0))
    unique_light_mats.append(mat_u)
    # reassign the material on the light_i object
    light_obj = light_objs[i][0]
    light_obj.data.materials.clear()
    light_obj.data.materials.append(mat_u)

for i, mat_u in enumerate(unique_light_mats):
    bsdf = mat_u.node_tree.nodes.get("Principled BSDF")
    em = bsdf.inputs["Emission Strength"]
    phase = i / 8.0
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        # 4 cycles per loop, each light wave-shifted by its phase
        local = (t * 4 + phase) % 1.0
        val = 1.0 + 8.0 * math.exp(-((local - 0.5) * 4)**2)  # gaussian pulse
        em.default_value = val
        bpy.context.scene.frame_set(f)
        em.keyframe_insert(data_path="default_value", frame=f)

# Star pulses
bsdf_s = mat_star.node_tree.nodes.get("Principled BSDF")
em_s = bsdf_s.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_s.default_value = 4.0 + 2.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.0))
    bpy.context.scene.frame_set(f)
    em_s.keyframe_insert(data_path="default_value", frame=f)

# One ornament rotates slowly
if ornament_objs:
    rot_orn = ornament_objs[0]
    home_loc = rot_orn.location.copy()
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        rot_orn.rotation_euler = (0, 0, 2*math.pi * t)
        rot_orn.keyframe_insert("rotation_euler", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"XMAS_OK: {out_glb}", flush=True)
'''


def make_xmas(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_xmas_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "XMAS_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_xmas(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
