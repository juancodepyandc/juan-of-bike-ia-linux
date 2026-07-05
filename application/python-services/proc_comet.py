"""Procedural comet with twin tails (Blender headless).

Rocky/icy nucleus (irregular grey sphere) + bright coma halo + 2 tails :
a wider dust tail (yellow-white) trailing in one direction and a
narrower, straighter ion tail (blue) in another + 30 small trailing
particles spread along both tails + background starfield. Animation :
the comet pivot rotates slightly + the trailing particles cycle along
their tails (location moves backward over the cycle then resets).

CLI:
  python proc_comet.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "comet.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0xC03E)

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

mat_space   = pbr_mat("space",     (0.02, 0.02, 0.05), 0.00, 0.95)
mat_nucleus = pbr_mat("nucleus",   (0.30, 0.28, 0.32), 0.20, 0.65)
mat_coma    = pbr_mat("coma",      (0.95, 0.92, 0.85), 0.00, 0.10,
                          alpha=0.25,
                          emission=((1.00, 0.95, 0.85), 3.0))
mat_dust    = pbr_mat("dust",      (1.00, 0.85, 0.55), 0.00, 0.10,
                          alpha=0.40,
                          emission=((1.00, 0.85, 0.50), 2.5))
mat_ion     = pbr_mat("ion",       (0.45, 0.65, 1.00), 0.00, 0.10,
                          alpha=0.50,
                          emission=((0.55, 0.75, 1.00), 4.0))
mat_dust_p  = pbr_mat("dust_p",    (1.00, 0.90, 0.65), 0.00, 0.10,
                          alpha=0.55,
                          emission=((1.00, 0.85, 0.50), 4.0))
mat_ion_p   = pbr_mat("ion_p",     (0.55, 0.75, 1.00), 0.00, 0.10,
                          alpha=0.60,
                          emission=((0.65, 0.80, 1.00), 6.0))
mat_star    = pbr_mat("star",      (1.00, 0.95, 0.85), 0.00, 0.10,
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

# --- space + stars ---
_box("space_plate", 7.0, 7.0, 0.02, (0, 0, -2.0), mat_space)
for i in range(50):
    a = rng.uniform(0, 2*math.pi)
    r = rng.uniform(2.5, 3.5)
    z = rng.uniform(-2.0, 2.0)
    _sphere(f"star_{i}", rng.uniform(0.010, 0.025),
              (r * math.cos(a), r * math.sin(a), z), mat_star, u=8, v=6)

# Comet pivot — comet at origin, tails extending toward +Y (away from "sun" at -Y)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(-0.50, 0, 0))
comet_pivot = bpy.context.active_object
comet_pivot.name = "comet_pivot"

# --- nucleus (irregular dark sphere) ---
nucleus = _sphere("nucleus", 0.12, (0, 0, 0), mat_nucleus, u=18, v=14,
                    scale=(1.0, 0.85, 1.05))
nucleus.parent = comet_pivot
nucleus.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# small crater spots
for k in range(5):
    a = rng.uniform(0, 2*math.pi)
    el = rng.uniform(-math.pi/2, math.pi/2)
    crater_pos = (0.115 * math.cos(el) * math.cos(a),
                    0.110 * math.cos(el) * math.sin(a) * 0.85,
                    0.120 * math.sin(el) * 1.05)
    cr = _sphere(f"crater_{k}", 0.020, crater_pos, mat_nucleus,
                   u=8, v=6, scale=(1.0, 1.0, 0.3))
    cr.parent = comet_pivot
    cr.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- coma halo (a larger glowing sphere around the nucleus) ---
coma = _sphere("coma", 0.22, (0, 0, 0), mat_coma, u=20, v=14)
coma.parent = comet_pivot
coma.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- dust tail : a wide cone extending in +Y, curved ---
# Build as a cone with R1=0.18 at the head, R2=0.005 at the far end
DUST_LEN = 2.20
dust_tail = _cyl("dust_tail", 0.18, 0.005, DUST_LEN, 'Y',
                   (0, DUST_LEN/2 + 0.10, 0), mat_dust, segments=20)
dust_tail.rotation_euler = (0, 0, math.radians(-8))  # slight curve
dust_tail.parent = comet_pivot
dust_tail.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- ion tail : narrower, straighter, blue, extending more upward ---
ION_LEN = 2.50
ion_tail = _cyl("ion_tail", 0.10, 0.003, ION_LEN, 'Y',
                  (0, ION_LEN/2 + 0.10, 0.30), mat_ion, segments=18)
ion_tail.rotation_euler = (math.radians(15), 0, 0)
ion_tail.parent = comet_pivot
ion_tail.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 30 trailing particles : 15 in dust tail + 15 in ion tail ---
dust_particles = []
for i in range(15):
    # particle home position along the dust tail
    t_along = (i + 1) / 16   # 0..1
    px = 0
    py = 0.10 + t_along * DUST_LEN
    pz = -t_along * 0.10   # slight curve down
    p = _sphere(f"dust_p_{i}", 0.020 + 0.030 * (1 - t_along),
                  (px, py, pz), mat_dust_p, u=8, v=6)
    p.parent = comet_pivot
    p.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    dust_particles.append((p, py, pz))

ion_particles = []
for i in range(15):
    t_along = (i + 1) / 16
    px = 0
    py = 0.10 + t_along * ION_LEN
    pz = 0.30 + t_along * 0.10   # slight upward curve
    p = _sphere(f"ion_p_{i}", 0.012 + 0.020 * (1 - t_along),
                  (px, py, pz), mat_ion_p, u=8, v=6)
    p.parent = comet_pivot
    p.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    ion_particles.append((p, py, pz))

# --- animation ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# comet rotates very slowly (subtle wobble)
HOME_LOC = comet_pivot.location.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    rot_z = math.radians(8) * math.sin(2*math.pi*t * 0.3)
    comet_pivot.rotation_euler = (0, 0, rot_z)
    comet_pivot.keyframe_insert("rotation_euler", frame=f)
if comet_pivot.animation_data and comet_pivot.animation_data.action:
    for fc in comet_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Dust particles : cycle along tail
for i, (p, base_y, base_z) in enumerate(dust_particles):
    phase = i / 15.0
    home_pz = base_z
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        local = (t + phase) % 1.0
        # particle moves backward along the tail (Y grows then wraps)
        y_off = local * 0.30
        # slight wobble in Z and X
        z_w = home_pz + 0.020 * math.sin(local * 8 + phase * 6.28)
        x_w = 0.020 * math.cos(local * 6 + phase * 6.28)
        bpy.context.scene.frame_set(f)
        p.location = (x_w, base_y + y_off, z_w)
        p.keyframe_insert("location", frame=f)
    if p.animation_data and p.animation_data.action:
        for fc in p.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Ion particles : faster cycle
for i, (p, base_y, base_z) in enumerate(ion_particles):
    phase = i / 15.0
    home_pz = base_z
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        local = (t * 1.5 + phase) % 1.0
        y_off = local * 0.40
        z_w = home_pz + 0.010 * math.sin(local * 10 + phase * 6.28)
        x_w = 0.015 * math.cos(local * 8 + phase * 6.28)
        bpy.context.scene.frame_set(f)
        p.location = (x_w, base_y + y_off, z_w)
        p.keyframe_insert("location", frame=f)
    if p.animation_data and p.animation_data.action:
        for fc in p.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Coma pulses
bsdf_c = mat_coma.node_tree.nodes.get("Principled BSDF")
em_c = bsdf_c.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_c.default_value = 2.5 + 1.2 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.0))
    bpy.context.scene.frame_set(f)
    em_c.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"COMET_OK: {out_glb}", flush=True)
'''


def make_comet(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_comet_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "COMET_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_comet(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
