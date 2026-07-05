"""Procedural Earth globe on a stand (Blender headless).

Sphere (ocean blue + 5 continent patches in green via vertex-group
material assignment) on a tilted axis (23.4 deg) through a brass
meridian ring, mounted on a wood base. Animation : the globe spins
around its tilted axis.

CLI:
  python proc_globe.py <output_glb>
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

random.seed(11)

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "globe.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
    return m

mat_ocean    = pbr_mat("ocean_blue",  (0.10, 0.30, 0.65), 0.05, 0.30)
mat_land     = pbr_mat("land_green",  (0.20, 0.55, 0.20), 0.00, 0.55)
mat_ring     = pbr_mat("brass_ring",  (0.86, 0.62, 0.20), 1.00, 0.28)
mat_wood     = pbr_mat("base_wood",   (0.30, 0.18, 0.08), 0.00, 0.60)
mat_axle     = pbr_mat("axle_steel",  (0.50, 0.52, 0.55), 1.00, 0.30)
mat_floor    = pbr_mat("floor",       (0.30, 0.30, 0.32), 0.00, 0.85)

def _cyl(name, R1, R2, depth, axis, location, mat, segments=24):
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
    return obj

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

# --- floor ---------------------------------------------------------
_box("floor", 2.4, 2.4, 0.04, (0, 0, -0.04), mat_floor)

# --- wood base + pedestal -----------------------------------------
BASE_H = 0.08
_cyl("base_disc", 0.32, 0.34, BASE_H, 'Z', (0, 0, BASE_H/2), mat_wood)
_cyl("base_disc_top", 0.30, 0.30, 0.02, 'Z', (0, 0, BASE_H + 0.01), mat_wood)
_cyl("pedestal", 0.06, 0.05, 0.30, 'Z', (0, 0, BASE_H + 0.15), mat_wood)
_cyl("pedestal_collar", 0.10, 0.10, 0.025, 'Z', (0, 0, BASE_H + 0.30 + 0.013), mat_brass := mat_ring)

# --- brass meridian ring (tilted) ---------------------------------
# Build a torus oriented in the YZ plane (a vertical ring around the X-Z plane).
# Then tilt by 23.4 deg around Y so the axis of the globe inside is tilted.
GLOBE_R = 0.40
RING_R_MAJOR = GLOBE_R * 1.05
RING_R_MINOR = 0.018
mesh_ring = bpy.data.meshes.new("meridian_ring")
ring = bpy.data.objects.new("meridian_ring", mesh_ring)
bpy.context.collection.objects.link(ring)
bm = bmesh.new()
N_MAJ, N_MIN = 48, 10
for i in range(N_MAJ):
    a = i * 2 * math.pi / N_MAJ
    cx = math.cos(a) * RING_R_MAJOR
    cy = math.sin(a) * RING_R_MAJOR
    for j in range(N_MIN):
        b = j * 2 * math.pi / N_MIN
        # minor circle in the plane perpendicular to the major direction
        radial = (math.cos(a), math.sin(a))
        r_rad = math.cos(b) * RING_R_MINOR
        rz    = math.sin(b) * RING_R_MINOR
        bm.verts.new((cx + radial[0] * r_rad,
                       cy + radial[1] * r_rad,
                       rz))
bm.verts.ensure_lookup_table()
for i in range(N_MAJ):
    ni = (i + 1) % N_MAJ
    for j in range(N_MIN):
        nj = (j + 1) % N_MIN
        a_idx = i * N_MIN + j
        b_idx = i * N_MIN + nj
        c_idx = ni * N_MIN + nj
        d_idx = ni * N_MIN + j
        bm.faces.new((bm.verts[a_idx], bm.verts[b_idx],
                       bm.verts[c_idx], bm.verts[d_idx]))
bm.normal_update()
# rotate ring 90 deg around X so its plane is vertical
bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'X'), verts=bm.verts)
bm.to_mesh(mesh_ring); bm.free()
ring.data.materials.append(mat_ring)
ring.location = (0, 0, BASE_H + 0.30 + GLOBE_R + 0.05)
ring.rotation_euler = (0, math.radians(23.4), 0)   # 23.4 deg axial tilt

# --- axle (a small cylinder through the globe along its rotation axis) -
# axle runs through the globe along its local Z (after the tilt)
axle = _cyl("axle", 0.012, 0.012, GLOBE_R * 2.3, 'Z',
              (0, 0, BASE_H + 0.30 + GLOBE_R + 0.05), mat_axle)
axle.rotation_euler = (0, math.radians(23.4), 0)

# --- globe pivot (rotates around the tilted axis) -----------------
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(0, 0, BASE_H + 0.30 + GLOBE_R + 0.05))
globe_pivot = bpy.context.active_object
globe_pivot.name = "globe_pivot"
globe_pivot.rotation_euler = (0, math.radians(23.4), 0)

# --- Earth sphere : blue ocean + green "continent" patches via wedge faces
mesh_globe = bpy.data.meshes.new("earth_sphere")
earth = bpy.data.objects.new("earth_sphere", mesh_globe)
bpy.context.collection.objects.link(earth)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=GLOBE_R)
bm.to_mesh(mesh_globe); bm.free()
earth.data.materials.append(mat_ocean)
earth.data.materials.append(mat_land)
# Assign land material to a few random clusters of polygons (5 continents)
n_polys = len(earth.data.polygons)
random.seed(11)
# Pick 5 seed polygon indices, mark them + their immediate neighbours
seeds = random.sample(range(n_polys), 5)
land_polys = set(seeds)
# Expand each seed by 1-2 hops in the adjacency graph (approx via near
# neighbours by polygon-centre distance)
centres = []
for p in earth.data.polygons:
    cx = sum(earth.data.vertices[i].co.x for i in p.vertices) / len(p.vertices)
    cy = sum(earth.data.vertices[i].co.y for i in p.vertices) / len(p.vertices)
    cz = sum(earth.data.vertices[i].co.z for i in p.vertices) / len(p.vertices)
    centres.append((cx, cy, cz))
# for each seed, add the closest 20-40 polygons
for seed in seeds:
    sc = centres[seed]
    dists = sorted(range(n_polys),
                    key=lambda k: (centres[k][0]-sc[0])**2 + (centres[k][1]-sc[1])**2 + (centres[k][2]-sc[2])**2)
    cluster_size = random.randint(20, 45)
    land_polys.update(dists[:cluster_size])

for i, p in enumerate(earth.data.polygons):
    p.material_index = 1 if i in land_polys else 0

earth.parent = globe_pivot
earth.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : globe pivot rotates around its LOCAL Z (the tilted axis)
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
base_rot = list(globe_pivot.rotation_euler)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # Add rotation around LOCAL Z. With XYZ Euler order, setting
    # rotation_euler.z accumulates on top of the existing (0, 23.4, 0) tilt.
    globe_pivot.rotation_euler = (base_rot[0], base_rot[1], 2 * math.pi * t)
    globe_pivot.keyframe_insert("rotation_euler", frame=f)
if globe_pivot.animation_data and globe_pivot.animation_data.action:
    for fc in globe_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"GLOBE_OK: {out_glb}", flush=True)
'''


def make_globe(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_globe_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "GLOBE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_globe(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
