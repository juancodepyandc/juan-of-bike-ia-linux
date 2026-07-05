"""Procedural ringed planet à la Saturn (Blender headless).

Cream/orange-banded planet sphere + 5 concentric ring discs (with subtle
gaps) + 3 orbiting moons (each on a tilted orbital plane) + faint dust
particles in the background + a few distant stars. Animation : the
planet rotates around its tilted axis, each moon orbits at its own
speed + radius + plane, and rings remain stationary relative to the
planet (parented to it).

CLI:
  python proc_ringed_planet.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "saturn.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0x5A75)

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
mat_p_cream = pbr_mat("p_cream", (0.92, 0.82, 0.58), 0.00, 0.65)
mat_p_band1 = pbr_mat("p_band1", (0.85, 0.62, 0.32), 0.00, 0.65)
mat_p_band2 = pbr_mat("p_band2", (0.75, 0.50, 0.25), 0.00, 0.70)
mat_p_band3 = pbr_mat("p_band3", (0.95, 0.85, 0.65), 0.00, 0.65)
mat_ring_a  = pbr_mat("ring_a",  (0.85, 0.78, 0.55), 0.10, 0.45, alpha=0.65)
mat_ring_b  = pbr_mat("ring_b",  (0.65, 0.55, 0.35), 0.10, 0.50, alpha=0.55)
mat_ring_c  = pbr_mat("ring_c",  (0.75, 0.65, 0.45), 0.10, 0.50, alpha=0.45)
mat_moon_a  = pbr_mat("moon_a",  (0.70, 0.65, 0.58), 0.00, 0.85)
mat_moon_b  = pbr_mat("moon_b",  (0.55, 0.45, 0.35), 0.00, 0.85)
mat_moon_c  = pbr_mat("moon_c",  (0.80, 0.78, 0.72), 0.00, 0.85)
mat_star    = pbr_mat("star",    (1.00, 0.95, 0.85), 0.00, 0.10,
                          emission=((1.00, 0.95, 0.85), 8.0))

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
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

def _torus(name, R_major, R_minor, location, mat, ms=48, mn=4, axis='Z'):
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

# --- space background plate ---
_box("space_plate", 6.0, 6.0, 0.02, (0, 0, -2.0), mat_space)

# --- 30 distant stars in the background ---
for i in range(30):
    a = rng.uniform(0, 2*math.pi)
    r = rng.uniform(2.2, 2.8)
    z = rng.uniform(-1.5, 1.5)
    star = _sphere(f"star_{i}", rng.uniform(0.010, 0.025),
                     (r * math.cos(a), r * math.sin(a), z),
                     mat_star, u=8, v=6)

# --- planet (rotating pivot) ---
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
planet_pivot = bpy.context.active_object
planet_pivot.name = "planet_pivot"
# tilt the axis (Saturn ~26.7°)
planet_pivot.rotation_euler = (math.radians(26.7), 0, 0)

PLANET_R = 0.55
planet = _sphere("planet_body", PLANET_R, (0, 0, 0), mat_p_cream, u=32, v=20)
planet.parent = planet_pivot
planet.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# atmospheric bands : 5 colored thin spheres slightly larger
# build as flat rings via scaled spheres but a simpler approach :
# overlay 5 horizontal "stripe" sphere caps via flattening + offset
BAND_DEFS = [
    (mat_p_band1, 0.85,  0.20),
    (mat_p_band2, 0.55, 0.15),
    (mat_p_band3, 0.20, 0.20),
    (mat_p_band2, -0.20, 0.18),
    (mat_p_band1, -0.55, 0.18),
]
for k, (mat, z_pos, h) in enumerate(BAND_DEFS):
    # use a thin sphere mat overlay (sphere R slightly larger, scaled vertically)
    band = _sphere(f"band_{k}", PLANET_R * 1.005,
                     (0, 0, z_pos * PLANET_R * 0.6), mat,
                     u=24, v=14,
                     scale=(1.0, 1.0, h / (PLANET_R * 2)))
    band.parent = planet_pivot
    band.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 5 concentric ring discs (toroidal but thin) parented to planet pivot ---
# So the rings tilt with the planet's axis
RING_DEFS = [
    (PLANET_R * 1.30, 0.005, mat_ring_a),
    (PLANET_R * 1.45, 0.005, mat_ring_b),
    (PLANET_R * 1.65, 0.005, mat_ring_c),
    (PLANET_R * 1.85, 0.005, mat_ring_a),
    (PLANET_R * 2.05, 0.005, mat_ring_b),
]
for k, (R_major, R_minor, mat) in enumerate(RING_DEFS):
    ring = _torus(f"ring_{k}", R_major, R_minor, (0, 0, 0), mat, ms=48, mn=4)
    # squash vertically to make it look like a thin disc instead of round torus
    for v in ring.data.vertices:
        v.co.z *= 0.20
    ring.parent = planet_pivot
    ring.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 3 moons (each on its own orbital empty) ---
moon_pivots = []
MOON_DEFS = [
    # (orbit_radius, moon_radius, color, orbit_speed, tilt_x_deg, tilt_y_deg)
    (1.50, 0.07, mat_moon_a, 1.0, 5, 8),
    (2.20, 0.05, mat_moon_b, 0.6, -10, 15),
    (1.85, 0.04, mat_moon_c, 1.4, 3, -12),
]
for i, (r_orb, r_moon, mat, speed, tx, ty) in enumerate(MOON_DEFS):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
    pv = bpy.context.active_object
    pv.name = f"moon_orbit_{i}"
    pv.rotation_euler = (math.radians(tx), math.radians(ty), 0)
    moon = _sphere(f"moon_{i}", r_moon, (r_orb, 0, 0), mat, u=14, v=10)
    moon.parent = pv
    moon.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    moon_pivots.append((pv, speed))

# --- animation ---
FPS = 30
DURATION = 10.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Planet rotates around its tilted axis (Z in pivot's local frame)
# We can't easily animate the local Z while keeping the X tilt baked in,
# so we'll spin the planet_body itself (not the pivot), keeping the
# pivot's tilt static.
# But planet_body is parented to planet_pivot. Animating its local Z
# rotation while pivot tilts X gives proper "tilted spin" effect.
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    planet.rotation_euler = (0, 0, 2*math.pi * t)
    planet.keyframe_insert("rotation_euler", frame=f)
if planet.animation_data and planet.animation_data.action:
    for fc in planet.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# 3 moons orbit each at their own speed
for pv, speed in moon_pivots:
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        # preserve tilt rotation_x and rotation_y, animate Z spin
        rx = pv.rotation_euler.x
        ry = pv.rotation_euler.y
        pv.rotation_euler = (rx, ry, 2*math.pi * speed * t)
        pv.keyframe_insert("rotation_euler", frame=f)
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SAT_OK: {out_glb}", flush=True)
'''


def make_saturn(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_sat_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SAT_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_saturn(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
