"""Procedural supernova explosion (Blender headless).

Central collapsed star (bright emissive sphere) + 3 concentric expanding
shock waves (translucent spheres with growing scale) + 50 ejecta fragments
dispersed radially + colored remnant nebula clouds + starfield. Animation
: shock waves expand outward, fragments fly out radially with scale ramp,
star pulses intensely.

CLI:
  python proc_supernova.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "supernova.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0x5470A)

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
mat_core     = pbr_mat("core",     (1.00, 0.95, 0.85), 0.00, 0.10,
                          emission=((1.00, 0.95, 0.85), 30.0))
mat_shock_a  = pbr_mat("shock_a",  (1.00, 0.55, 0.20), 0.00, 0.10,
                          alpha=0.18,
                          emission=((1.00, 0.55, 0.20), 6.0))
mat_shock_b  = pbr_mat("shock_b",  (0.95, 0.45, 0.45), 0.00, 0.10,
                          alpha=0.14,
                          emission=((0.95, 0.45, 0.45), 4.0))
mat_shock_c  = pbr_mat("shock_c",  (0.55, 0.45, 0.95), 0.00, 0.10,
                          alpha=0.10,
                          emission=((0.55, 0.45, 0.95), 3.0))
mat_ejecta_w = pbr_mat("ejecta_w", (1.00, 0.95, 0.75), 0.00, 0.10,
                          emission=((1.00, 0.95, 0.75), 8.0))
mat_ejecta_o = pbr_mat("ejecta_o", (1.00, 0.55, 0.20), 0.00, 0.10,
                          emission=((1.00, 0.55, 0.20), 6.0))
mat_ejecta_r = pbr_mat("ejecta_r", (1.00, 0.30, 0.30), 0.00, 0.10,
                          emission=((1.00, 0.30, 0.30), 5.0))
mat_neb_a    = pbr_mat("neb_a",    (0.65, 0.20, 0.85), 0.00, 0.10,
                          alpha=0.20,
                          emission=((0.70, 0.30, 0.95), 2.0))
mat_neb_b    = pbr_mat("neb_b",    (0.20, 0.55, 0.85), 0.00, 0.10,
                          alpha=0.20,
                          emission=((0.30, 0.65, 1.00), 2.0))
mat_star     = pbr_mat("star",     (1.00, 0.95, 0.85), 0.00, 0.10,
                          emission=((1.00, 0.95, 0.85), 6.0))

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
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

# --- space + distant stars ---
_box("space_plate", 8.0, 8.0, 0.02, (0, 0, -3.0), mat_space)
for i in range(60):
    a = rng.uniform(0, 2*math.pi)
    r = rng.uniform(3.0, 4.0)
    z = rng.uniform(-2.5, 2.5)
    _sphere(f"star_{i}", rng.uniform(0.010, 0.025),
              (r * math.cos(a), r * math.sin(a), z), mat_star, u=8, v=6)

# --- collapsed core (the bright remnant) ---
core = _sphere("core", 0.18, (0, 0, 0), mat_core, u=24, v=16)

# --- 3 expanding shock waves (concentric, anim scale) ---
shock_objs = []
SHOCK_DEFS = [
    (0.40, mat_shock_a, 0.5),    # (start_R, mat, phase_offset)
    (0.55, mat_shock_b, 0.20),
    (0.30, mat_shock_c, 0.65),
]
for k, (R_start, mat, phase) in enumerate(SHOCK_DEFS):
    s = _sphere(f"shock_{k}", R_start, (0, 0, 0), mat, u=20, v=14)
    shock_objs.append((s, R_start, phase))

# --- 50 ejecta fragments dispersed radially ---
ejecta = []
EJECTA_MATS = [mat_ejecta_w, mat_ejecta_o, mat_ejecta_r]
for i in range(50):
    # random direction on unit sphere
    theta = rng.uniform(0, 2*math.pi)
    phi = math.acos(rng.uniform(-1, 1))
    dir_x = math.sin(phi) * math.cos(theta)
    dir_y = math.sin(phi) * math.sin(theta)
    dir_z = math.cos(phi)
    R = rng.uniform(0.020, 0.050)
    mat = EJECTA_MATS[i % 3]
    # start near the core
    start_dist = rng.uniform(0.20, 0.30)
    pos = (dir_x * start_dist, dir_y * start_dist, dir_z * start_dist)
    e = _sphere(f"ejecta_{i}", R, pos, mat, u=8, v=6)
    ejecta.append((e, (dir_x, dir_y, dir_z), start_dist, rng.uniform(0, 1.0)))

# --- nebula remnant clouds (8 large translucent spheres in 2 colors) ---
for i in range(8):
    a = rng.uniform(0, 2*math.pi)
    r = rng.uniform(0.8, 1.8)
    z = rng.uniform(-0.6, 0.6)
    cx = r * math.cos(a)
    cy = r * math.sin(a)
    mat = mat_neb_a if i % 2 == 0 else mat_neb_b
    _sphere(f"neb_{i}", rng.uniform(0.40, 0.80),
              (cx, cy, z), mat, u=12, v=10,
              scale=(1.0, 1.0, rng.uniform(0.4, 0.8)))

# --- animation ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Core pulses intensely
bsdf_core = mat_core.node_tree.nodes.get("Principled BSDF")
em_core = bsdf_core.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_core.default_value = 25.0 + 15.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 2.0))
    bpy.context.scene.frame_set(f)
    em_core.keyframe_insert(data_path="default_value", frame=f)

# Shock waves expand outward (scale ramp + emission fade)
for (s, R0, phase) in shock_objs:
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        local = (t + phase) % 1.0
        # expand from 1.0 to 5.0 then reset
        scale_factor = 1.0 + local * 4.0
        # fade emission as it expands
        s.scale = (scale_factor, scale_factor, scale_factor)
        bpy.context.scene.frame_set(f)
        s.keyframe_insert("scale", frame=f)
    if s.animation_data and s.animation_data.action:
        for fc in s.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Ejecta fragments fly outward (location + scale ramp)
for (e, direction, start_dist, phase) in ejecta:
    dx, dy, dz = direction
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        local = (t + phase) % 1.0
        # distance grows from start_dist to 3.5
        dist = start_dist + local * 3.0
        # slight tumble rotation
        x = dx * dist
        y = dy * dist
        z = dz * dist
        # scale fades slightly as it travels (cooling)
        sf = 1.0 - local * 0.4
        e.location = (x, y, z)
        e.scale = (sf, sf, sf)
        bpy.context.scene.frame_set(f)
        e.keyframe_insert("location", frame=f)
        e.keyframe_insert("scale", frame=f)
    if e.animation_data and e.animation_data.action:
        for fc in e.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SN_OK: {out_glb}", flush=True)
'''


def make_sn(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_sn_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SN_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_sn(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
