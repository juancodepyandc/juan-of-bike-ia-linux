"""Procedural snow globe (Blender headless).

Translucent glass sphere on a turned wooden base, with a winter scene
inside : pine tree + gingerbread house + 20 snowflakes drifting in
spiraling paths. Animation : snowflakes descend in helical paths (each
flake at its own X cosine/Y sine radius + steady Z drop, wrapping back
to the top), and a small gold star at the apex pulses emission.

CLI:
  python proc_snow_globe.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "snow_globe.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0x5710)

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

mat_floor    = pbr_mat("floor",    (0.18, 0.16, 0.20), 0.00, 0.85)
mat_base_w   = pbr_mat("base_w",   (0.32, 0.18, 0.08), 0.05, 0.55)
mat_base_d   = pbr_mat("base_d",   (0.20, 0.10, 0.04), 0.05, 0.60)
mat_glass    = pbr_mat("glass",    (0.85, 0.92, 0.95), 0.00, 0.05, alpha=0.18)
mat_snow_g   = pbr_mat("snow_g",   (0.92, 0.92, 0.95), 0.00, 0.55)
mat_trunk    = pbr_mat("trunk",    (0.30, 0.18, 0.08), 0.05, 0.65)
mat_leaf     = pbr_mat("leaf",     (0.10, 0.45, 0.20), 0.00, 0.60)
mat_leaf_l   = pbr_mat("leaf_l",   (0.15, 0.55, 0.22), 0.00, 0.60)
mat_house_w  = pbr_mat("house_w",  (0.65, 0.40, 0.20), 0.05, 0.65)
mat_roof     = pbr_mat("roof",     (0.85, 0.18, 0.12), 0.10, 0.45)
mat_window   = pbr_mat("window",   (0.95, 0.85, 0.30), 0.00, 0.20,
                          emission=((1.00, 0.85, 0.30), 2.5))
mat_door     = pbr_mat("door",     (0.55, 0.18, 0.10), 0.05, 0.55)
mat_flake    = pbr_mat("flake",    (0.95, 0.95, 0.92), 0.00, 0.45)
mat_star     = pbr_mat("star",     (0.95, 0.85, 0.20), 1.00, 0.20,
                          emission=((1.00, 0.85, 0.30), 4.0))

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

# --- floor ---
_box("floor", 1.0, 1.0, 0.04, (0, 0, -0.04), mat_floor)

# --- wooden base : 2-tier turned shape ---
_cyl("base_lower", 0.32, 0.30, 0.06, 'Z', (0, 0, 0.05), mat_base_w, segments=24)
_cyl("base_upper", 0.28, 0.26, 0.04, 'Z', (0, 0, 0.10), mat_base_d, segments=24)
# decorative ring on top of base
_cyl("base_ring", 0.27, 0.27, 0.008, 'Z', (0, 0, 0.124), mat_base_d, segments=24)

# --- glass sphere ---
GLOBE_R = 0.32
GLOBE_Z = 0.13 + GLOBE_R
_sphere("globe", GLOBE_R, (0, 0, GLOBE_Z), mat_glass, u=32, v=20)

# --- snow ground inside the globe (a thin disc) ---
_cyl("snow_floor", GLOBE_R * 0.85, GLOBE_R * 0.85, 0.012, 'Z',
       (0, 0, GLOBE_Z - GLOBE_R + 0.025), mat_snow_g, segments=24)

# --- pine tree inside (on the -X side) ---
TREE_X = -0.10
TREE_Y = 0
TREE_BASE_Z = GLOBE_Z - GLOBE_R + 0.040
# trunk
_cyl("tree_trunk", 0.018, 0.014, 0.06, 'Z',
       (TREE_X, TREE_Y, TREE_BASE_Z + 0.03), mat_trunk, segments=8)
# 3 conical foliage layers stacked (cones via _cyl with R2=tip)
for k, (R, dz, mat) in enumerate([(0.10, 0.06, mat_leaf),
                                    (0.075, 0.13, mat_leaf_l),
                                    (0.05, 0.20, mat_leaf)]):
    _cyl(f"tree_cone_{k}", R, 0.005, 0.08, 'Z',
           (TREE_X, TREE_Y, TREE_BASE_Z + dz + 0.04), mat, segments=10)
# star on top (5-point approximation : a flattened sphere)
_sphere("tree_star", 0.022, (TREE_X, TREE_Y, TREE_BASE_Z + 0.28), mat_star,
         scale=(1.0, 1.0, 0.4))

# --- gingerbread house (on the +X side) ---
HOUSE_X = 0.10
HOUSE_Y = 0
HOUSE_BASE_Z = GLOBE_Z - GLOBE_R + 0.040
# main body (a brown box)
_box("house_body", 0.12, 0.10, 0.10,
       (HOUSE_X, HOUSE_Y, HOUSE_BASE_Z + 0.05), mat_house_w)
# pitched roof : 2 tilted slabs forming a triangular prism
for sy in (-1, +1):
    _box(f"house_roof_{sy}", 0.13, 0.06, 0.014,
           (HOUSE_X, HOUSE_Y + sy * 0.025, HOUSE_BASE_Z + 0.115),
           mat_roof, rot=(sy * math.radians(30), 0, 0))
# chimney
_box("house_chimney", 0.020, 0.020, 0.04,
       (HOUSE_X + 0.04, HOUSE_Y + 0.02, HOUSE_BASE_Z + 0.135), mat_house_w)
# small emissive window (yellow glow)
_box("house_window", 0.030, 0.0015, 0.030,
       (HOUSE_X, HOUSE_Y - 0.052, HOUSE_BASE_Z + 0.060), mat_window)
# door
_box("house_door", 0.020, 0.0015, 0.045,
       (HOUSE_X + 0.025, HOUSE_Y - 0.052, HOUSE_BASE_Z + 0.040), mat_door)

# --- 20 snowflakes (small spheres) drifting inside the globe ---
flakes = []
for i in range(20):
    # start position : random within sphere
    r = rng.uniform(0.06, GLOBE_R * 0.85)
    a = rng.uniform(0, 2*math.pi)
    px = r * math.cos(a)
    py = r * math.sin(a)
    pz_local = rng.uniform(-GLOBE_R * 0.6, GLOBE_R * 0.6)
    sphere = _sphere(f"flake_{i}", 0.008,
                       (px, py, GLOBE_Z + pz_local), mat_flake)
    flakes.append((sphere, px, py, pz_local, rng.uniform(0, 1.0)))

# --- animation -----------------
FPS = 30
DURATION = 8.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Each snowflake : descends in a helical pattern, wraps at the bottom
SNOW_DROP = GLOBE_R * 1.4
for (sp, ox, oy, oz, phase) in flakes:
    r_xy = math.sqrt(ox*ox + oy*oy)
    a0 = math.atan2(oy, ox)
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        # 2 cycles of descent per loop, with phase offset
        local_t = (t * 0.8 + phase) % 1.0
        # X/Y spiral : rotate angle slowly
        a = a0 + local_t * 2*math.pi * 0.6
        cur_r = r_xy * (0.6 + 0.4 * math.sin(local_t * 2*math.pi))
        x = cur_r * math.cos(a)
        y = cur_r * math.sin(a)
        # Z : descends linearly from GLOBE_Z + dz_max to GLOBE_Z - dz_max, wraps
        z_top = GLOBE_Z + GLOBE_R * 0.55
        z_bot = GLOBE_Z - GLOBE_R * 0.45
        z = z_top - local_t * (z_top - z_bot)
        bpy.context.scene.frame_set(f)
        sp.location = (x, y, z)
        sp.keyframe_insert("location", frame=f)
    if sp.animation_data and sp.animation_data.action:
        for fc in sp.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Tree star pulses emission
bsdf_s = mat_star.node_tree.nodes.get("Principled BSDF")
em_s = bsdf_s.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_s.default_value = 3.0 + 2.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.0))
    bpy.context.scene.frame_set(f)
    em_s.keyframe_insert(data_path="default_value", frame=f)

# House window glow flickers (warm hearth feel)
bsdf_w = mat_window.node_tree.nodes.get("Principled BSDF")
em_w = bsdf_w.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_w.default_value = 2.0 + 0.8 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.5))
    bpy.context.scene.frame_set(f)
    em_w.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SG_OK: {out_glb}", flush=True)
'''


def make_sg(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_sg_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SG_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_sg(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
