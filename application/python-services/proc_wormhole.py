"""Procedural wormhole tunnel (Blender headless).

Bright entry ring + 12 concentric tunnel rings receding inward (each
with its own color hue from cyan → magenta) + 30 swirling particles
spiraling toward the center + outer distortion halo + starfield. Animation
: each tunnel ring rotates at its own speed (creating a "warping" feel),
particles flow inward toward the singularity, the central core pulses.

CLI:
  python proc_wormhole.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "wormhole.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0xAA77)

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

mat_space   = pbr_mat("space",   (0.02, 0.02, 0.05), 0.00, 0.95)
mat_core    = pbr_mat("core",    (1.00, 0.95, 0.95), 0.00, 0.05,
                          emission=((1.00, 0.95, 0.95), 30.0))
mat_halo    = pbr_mat("halo",    (0.85, 0.45, 0.95), 0.00, 0.10,
                          alpha=0.20,
                          emission=((1.00, 0.55, 1.00), 6.0))
mat_part    = pbr_mat("particle",(1.00, 0.95, 0.85), 0.00, 0.10,
                          emission=((1.00, 0.95, 0.85), 8.0))
mat_star    = pbr_mat("star",    (1.00, 0.95, 0.85), 0.00, 0.10,
                          emission=((1.00, 0.95, 0.85), 6.0))

def lerp_color(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
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

def _torus(name, R_major, R_minor, location, mat, ms=36, mn=6, axis='Z'):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    verts = []
    for i in range(ms):
        ai = 2 * math.pi * i / ms
        ring = []
        for j in range(mn):
            aj = 2 * math.pi * j / mn
            x = (R_major + R_minor * math.cos(aj)) * math.cos(ai)
            y = (R_major + R_minor * math.cos(aj)) * math.sin(ai)
            z = R_minor * math.sin(aj)
            ring.append(bm.verts.new((x, y, z)))
        verts.append(ring)
    bm.verts.ensure_lookup_table()
    for i in range(ms):
        for j in range(mn):
            i2 = (i + 1) % ms
            j2 = (j + 1) % mn
            bm.faces.new([verts[i][j], verts[i2][j], verts[i2][j2], verts[i][j2]])
    if axis == 'X':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'Y'), verts=bm.verts)
    elif axis == 'Y':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'X'), verts=bm.verts)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- space + 40 background stars ---
_box("space_plate", 6.0, 6.0, 0.02, (0, 0, -2.5), mat_space)
for i in range(40):
    a = rng.uniform(0, 2*math.pi)
    r = rng.uniform(2.5, 3.2)
    z = rng.uniform(-2.0, 2.0)
    _sphere(f"star_{i}", rng.uniform(0.010, 0.025),
              (r * math.cos(a), r * math.sin(a), z), mat_star, u=8, v=6)

# --- bright core at the center (singularity) ---
_sphere("core", 0.15, (0, 0, 0), mat_core, u=20, v=14)
# halo
_sphere("halo", 0.18, (0, 0, 0), mat_halo, u=20, v=14, scale=(2.5, 2.5, 0.3))

# --- 12 concentric tunnel rings receding inward ---
# Each ring is a torus with axis Z (its plane is perpendicular to view).
# Colors gradient cyan → magenta as we go from outer to inner.
COLOR_OUTER = (0.30, 0.85, 1.00)
COLOR_INNER = (0.95, 0.30, 0.95)
N_RINGS = 12
ring_objs = []
ring_mats = []
for i in range(N_RINGS):
    u = i / (N_RINGS - 1)
    R_major = 1.40 - u * 1.10   # from 1.40 (outer) to 0.30 (inner)
    R_minor = 0.030 - u * 0.018
    color = lerp_color(COLOR_OUTER, COLOR_INNER, u)
    mat = pbr_mat(f"ring_mat_{i}", color, 0.00, 0.10,
                    emission=(color, 6.0 + i * 0.5))
    ring_mats.append(mat)
    # ring orientation : the rings are receding inward, but we want them
    # all in the same plane (Z=0) for top-down look. Vary their Z slightly
    # to add depth.
    z_off = -u * 0.20
    r = _torus(f"ring_{i}", R_major, R_minor, (0, 0, z_off), mat, ms=36, mn=6, axis='Z')
    ring_objs.append((r, i))

# --- 30 particles swirling inward (spiraling) ---
particles = []
for i in range(30):
    a0 = rng.uniform(0, 2*math.pi)
    r0 = rng.uniform(0.30, 1.50)
    z0 = rng.uniform(-0.10, 0.10)
    p = _sphere(f"particle_{i}", 0.015, (r0 * math.cos(a0), r0 * math.sin(a0), z0),
                  mat_part, u=8, v=6)
    particles.append((p, r0, a0, z0))

# --- animation ---
FPS = 30
DURATION = 8.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Each ring rotates at its own speed — inner ones faster
for (r, idx) in ring_objs:
    speed = 0.5 + idx * 0.25   # rad / loop
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        # rotate around Z; alternate direction by parity
        sign = 1 if idx % 2 == 0 else -1
        r.rotation_euler = (0, 0, sign * 2*math.pi * speed * t)
        r.keyframe_insert("rotation_euler", frame=f)
    if r.animation_data and r.animation_data.action:
        for fc in r.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Each ring's emission strength flickers with its own phase
for idx, mat in enumerate(ring_mats):
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    em = bsdf.inputs["Emission Strength"]
    phase = idx * 0.5
    base = 6.0 + idx * 0.5
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        em.default_value = base + 2.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.5 + phase))
        bpy.context.scene.frame_set(f)
        em.keyframe_insert(data_path="default_value", frame=f)

# Particles spiral inward
for i, (p, r0, a0, z0) in enumerate(particles):
    phase = i / 30.0
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        local = (t + phase) % 1.0
        # r shrinks from r0 to 0.05 over local, then wraps
        r_now = r0 * (1.0 - local) + 0.05 * local
        # angle increases (spiral)
        a_now = a0 + local * 2*math.pi * 3.0
        z_now = z0 * (1.0 - local) * 0.5
        x = r_now * math.cos(a_now)
        y = r_now * math.sin(a_now)
        bpy.context.scene.frame_set(f)
        p.location = (x, y, z_now)
        p.keyframe_insert("location", frame=f)
    if p.animation_data and p.animation_data.action:
        for fc in p.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Core pulses
bsdf_c = mat_core.node_tree.nodes.get("Principled BSDF")
em_c = bsdf_c.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_c.default_value = 25.0 + 10.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 2.0))
    bpy.context.scene.frame_set(f)
    em_c.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"WH_OK: {out_glb}", flush=True)
'''


def make_wh(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_wh_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "WH_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_wh(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
