"""Procedural mini solar system (Blender headless).

Emissive yellow sun at the centre + 3 orbiting planets : Earth (blue +
green continents), Mars (red), Jupiter (banded orange-brown + ring).
Each planet is parented to its own orbit pivot ; the pivots rotate at
Kepler-like speeds (closer planet -> faster orbit). Each planet also
spins on its own axis.

CLI:
  python proc_solar_system.py <output_glb>
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
import bpy, bmesh, math, mathutils, random, sys

random.seed(13)

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "solar.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough, emission=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if emission is not None and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission[0], 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission[1]
    return m

mat_sun       = pbr_mat("sun_yellow", (1.00, 0.85, 0.15), 0.00, 0.10,
                          emission=((1.00, 0.85, 0.30), 6.0))
mat_earth_oc  = pbr_mat("earth_ocean",(0.10, 0.30, 0.65), 0.05, 0.30)
mat_earth_ld  = pbr_mat("earth_land", (0.20, 0.55, 0.20), 0.00, 0.55)
mat_mars      = pbr_mat("mars_red",   (0.65, 0.20, 0.08), 0.05, 0.55)
mat_jupiter_a = pbr_mat("jupiter_lt", (0.85, 0.70, 0.50), 0.05, 0.50)
mat_jupiter_b = pbr_mat("jupiter_dk", (0.65, 0.45, 0.25), 0.05, 0.55)
mat_ring      = pbr_mat("ring_dust",  (0.70, 0.65, 0.55), 0.20, 0.55)
mat_orbit     = pbr_mat("orbit_line", (0.40, 0.40, 0.45), 0.00, 0.80)
mat_starfield = pbr_mat("space",      (0.02, 0.02, 0.05), 0.00, 1.00)

# (Backdrop sphere removed in v2 : the viewer auto-fits to the model's
#  bounding box, and a 4 m backdrop made everything inside it microscopic.)

# --- sun --------------------------------------------------------
SUN_R = 0.50
mesh_sun = bpy.data.meshes.new("sun")
sun = bpy.data.objects.new("sun", mesh_sun)
bpy.context.collection.objects.link(sun)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=SUN_R)
bm.to_mesh(mesh_sun); bm.free()
sun.data.materials.append(mat_sun)

# --- helper : make a sphere planet ------------------------------
def _planet_sphere(name, R, mat, u=24, v=16):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.data.materials.append(mat)
    return obj

def _planet_with_continents(name, R, ocean_mat, land_mat, n_clusters=5, u=24, v=16):
    obj = _planet_sphere(name, R, ocean_mat, u=u, v=v)
    obj.data.materials.append(land_mat)
    polys = obj.data.polygons
    n_polys = len(polys)
    centres = []
    for p in polys:
        cx = sum(obj.data.vertices[i].co.x for i in p.vertices) / len(p.vertices)
        cy = sum(obj.data.vertices[i].co.y for i in p.vertices) / len(p.vertices)
        cz = sum(obj.data.vertices[i].co.z for i in p.vertices) / len(p.vertices)
        centres.append((cx, cy, cz))
    seeds = random.sample(range(n_polys), n_clusters)
    land = set(seeds)
    for s in seeds:
        sc = centres[s]
        dists = sorted(range(n_polys),
                        key=lambda k: (centres[k][0]-sc[0])**2 + (centres[k][1]-sc[1])**2 + (centres[k][2]-sc[2])**2)
        land.update(dists[:random.randint(15, 30)])
    for i, p in enumerate(polys):
        p.material_index = 1 if i in land else 0
    return obj

def _planet_with_bands(name, R, mat_lt, mat_dk, u=32, v=20):
    obj = _planet_sphere(name, R, mat_lt, u=u, v=v)
    obj.data.materials.append(mat_dk)
    for i, p in enumerate(obj.data.polygons):
        cz = sum(obj.data.vertices[j].co.z for j in p.vertices) / len(p.vertices)
        # bands : alternate light / dark based on Z bands (latitude)
        band = int((cz + R) / (2 * R) * 7)  # 7 bands
        p.material_index = band % 2
    return obj

# --- 3 planets : Earth, Mars, Jupiter ---------------------------
PLANETS = [
    # (name, R_orbit, R_planet, mat_or_pair, has_ring, period_s, axis_spin_s)
    ("earth",   0.95, 0.18, ("continents", mat_earth_oc, mat_earth_ld), False, 2.0, 1.5),
    ("mars",    1.40, 0.13, ("solid",      mat_mars,     None),         False, 3.5, 2.0),
    ("jupiter", 2.10, 0.32, ("bands",      mat_jupiter_a, mat_jupiter_b),True,  6.0, 1.0),
]

# Build a thin ring of small dots for orbital path visualisation
def _build_orbit_ring(name, R, segments=64):
    mesh = bpy.data.meshes.new(name + "_orbit")
    obj = bpy.data.objects.new(name + "_orbit", mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    # very thin torus, mostly transparent : approximate with 64 small dots
    for k in range(segments):
        a = k * 2 * math.pi / segments
        bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=0.012)
        # the verts of the last-added sphere are the latest ones
        v_count = len(bm.verts)
        new_verts = list(bm.verts)[-(6*4 + 2):]   # approximate count
        bmesh.ops.translate(bm,
            vec=(math.cos(a) * R, math.sin(a) * R, 0),
            verts=new_verts)
    bm.to_mesh(mesh); bm.free()
    obj.data.materials.append(mat_orbit)
    return obj

planet_data = []   # (orbit_pivot, planet_obj, ring_obj)
for (name, R_orb, R_pl, mat_spec, has_ring, period, spin_s) in PLANETS:
    # build orbit ring (static, mostly decorative)
    _build_orbit_ring(name, R_orb)

    # orbit pivot at sun centre
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
    orbit_pivot = bpy.context.active_object
    orbit_pivot.name = f"{name}_orbit_pivot"

    # planet itself
    if mat_spec[0] == "continents":
        planet = _planet_with_continents(name, R_pl, mat_spec[1], mat_spec[2])
    elif mat_spec[0] == "bands":
        planet = _planet_with_bands(name, R_pl, mat_spec[1], mat_spec[2])
    else:
        planet = _planet_sphere(name, R_pl, mat_spec[1])
    # planet sits at distance R_orb along +X relative to orbit_pivot
    planet.parent = orbit_pivot
    planet.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    planet.location = (R_orb, 0, 0)

    ring_obj = None
    if has_ring:
        # Saturn-style ring : a flat torus around the planet axis
        mesh_r = bpy.data.meshes.new(name + "_ring")
        ring_obj = bpy.data.objects.new(name + "_ring", mesh_r)
        bpy.context.collection.objects.link(ring_obj)
        bm = bmesh.new()
        N_MAJ, N_MIN = 48, 6
        ring_R = R_pl * 1.8
        ring_t = R_pl * 0.05
        for i in range(N_MAJ):
            a = i * 2 * math.pi / N_MAJ
            for j in range(N_MIN):
                b = j * 2 * math.pi / N_MIN
                bm.verts.new((
                    (ring_R + math.cos(b) * ring_t) * math.cos(a),
                    (ring_R + math.cos(b) * ring_t) * math.sin(a),
                    math.sin(b) * ring_t * 0.3
                ))
        bm.verts.ensure_lookup_table()
        for i in range(N_MAJ):
            ni = (i + 1) % N_MAJ
            for j in range(N_MIN):
                nj = (j + 1) % N_MIN
                bm.faces.new((
                    bm.verts[i * N_MIN + j],
                    bm.verts[i * N_MIN + nj],
                    bm.verts[ni * N_MIN + nj],
                    bm.verts[ni * N_MIN + j],
                ))
        bm.normal_update()
        bm.to_mesh(mesh_r); bm.free()
        ring_obj.data.materials.append(mat_ring)
        ring_obj.parent = orbit_pivot
        ring_obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        ring_obj.location = (R_orb, 0, 0)
        ring_obj.rotation_euler = (math.radians(15), 0, 0)   # tilt the ring

    planet_data.append((orbit_pivot, planet, ring_obj, period, spin_s))

# --- animation -------------------------------------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
for (pivot, planet, ring, period, spin_s) in planet_data:
    # how many full orbits per loop ?  = DURATION / period
    orbits = DURATION / period
    spins  = DURATION / spin_s
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        pivot.rotation_euler = (0, 0, orbits * 2 * math.pi * t)
        pivot.keyframe_insert("rotation_euler", frame=f)
        # spin the planet on its own axis (around its local Z)
        planet.rotation_euler = (0, 0, spins * 2 * math.pi * t)
        planet.keyframe_insert("rotation_euler", frame=f)
    if pivot.animation_data and pivot.animation_data.action:
        for fc in pivot.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    if planet.animation_data and planet.animation_data.action:
        for fc in planet.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# sun spins slowly
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    sun.rotation_euler = (0, 0, 2 * math.pi * t * 0.3)
    sun.keyframe_insert("rotation_euler", frame=f)
if sun.animation_data and sun.animation_data.action:
    for fc in sun.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SOLAR_OK: {out_glb}", flush=True)
'''


def make_solar(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_solar_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SOLAR_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
        elapsed = round(time.time() - t0, 1)
        if ok:
            return {"ok": True, "glb": out_glb_abs, "elapsed_s": elapsed, "size_bytes": os.path.getsize(out_glb_abs)}
        tail = "\n".join((proc.stdout or "").splitlines()[-20:] + (proc.stderr or "").splitlines()[-20:])
        return {"ok": False, "error": f"Blender exit {proc.returncode}", "log_tail": tail, "elapsed_s": elapsed}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("output", help="output GLB path")
    args = ap.parse_args()
    r = make_solar(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
