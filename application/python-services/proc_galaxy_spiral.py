"""Procedural galaxy spiral (Blender headless).

Top-down spiral galaxy : ~200 emissive star spheres arranged on 2
logarithmic spiral arms, with colors graded from white-hot at the
center to orange / yellow / red at the outer rim, plus 80 background
"dust cloud" spheres in a wide disk + a bright nucleus + a thin disc
plane to suggest the galactic plane. Animation : the whole galaxy
rotates slowly + 12 randomly chosen stars pulse with their own emission
phase.

CLI:
  python proc_galaxy_spiral.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "galaxy.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0xA51A)

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

mat_void = pbr_mat("void", (0.02, 0.02, 0.05), 0.00, 0.95)
# Pre-made tinted emissive materials for distance bands
mat_star_white  = pbr_mat("star_w",  (1.00, 1.00, 0.95), 0.00, 0.10,
                              emission=((1.00, 1.00, 0.95), 12.0))
mat_star_yellow = pbr_mat("star_y",  (1.00, 0.90, 0.45), 0.00, 0.10,
                              emission=((1.00, 0.85, 0.40), 8.0))
mat_star_orange = pbr_mat("star_o",  (1.00, 0.55, 0.20), 0.00, 0.10,
                              emission=((1.00, 0.55, 0.20), 6.0))
mat_star_red    = pbr_mat("star_r",  (1.00, 0.30, 0.18), 0.00, 0.10,
                              emission=((1.00, 0.30, 0.20), 4.0))
mat_star_blue   = pbr_mat("star_b",  (0.55, 0.75, 1.00), 0.00, 0.10,
                              emission=((0.55, 0.78, 1.00), 8.0))
mat_dust_blue   = pbr_mat("dust_b",  (0.20, 0.35, 0.85), 0.00, 0.10,
                              alpha=0.10,
                              emission=((0.30, 0.50, 1.00), 0.5))
mat_dust_purple = pbr_mat("dust_p",  (0.55, 0.20, 0.75), 0.00, 0.10,
                              alpha=0.12,
                              emission=((0.65, 0.30, 0.85), 0.4))
mat_nucleus     = pbr_mat("nucleus", (1.00, 0.95, 0.65), 0.00, 0.05,
                              emission=((1.00, 0.95, 0.65), 30.0))

def _sphere(name, R, location, mat, u=10, v=8, scale=(1,1,1)):
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

# --- void background plate ---
def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj
_box("void_plate", 6.0, 6.0, 0.02, (0, 0, -0.5), mat_void)

# Galaxy parent empty
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
galaxy = bpy.context.active_object
galaxy.name = "galaxy_pivot"

# --- 80 dust clouds (background, low-density translucent purple/blue spheres) ---
for i in range(80):
    a = rng.uniform(0, 2*math.pi)
    r = rng.uniform(0.5, 3.0)
    z = rng.uniform(-0.10, 0.10)
    x = r * math.cos(a)
    y = r * math.sin(a)
    dust_mat = mat_dust_blue if i % 3 != 0 else mat_dust_purple
    dust = _sphere(f"dust_{i}", rng.uniform(0.15, 0.30),
                     (x, y, z), dust_mat, u=8, v=6,
                     scale=(1.0, 1.0, rng.uniform(0.2, 0.4)))
    dust.parent = galaxy
    dust.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 2 logarithmic spiral arms with stars ---
# Logarithmic spiral : r = a * exp(b * theta)
SPIRAL_A = 0.18
SPIRAL_B = 0.22
N_STARS_PER_ARM = 100
pulsing_stars = []   # list of (obj, unique_mat) for animation
for arm in range(2):
    arm_offset = arm * math.pi  # 2 arms diametrically offset
    for i in range(N_STARS_PER_ARM):
        # parameter t in [0..1] along the arm
        t = i / N_STARS_PER_ARM
        theta = t * 4.5 * math.pi + arm_offset
        r = SPIRAL_A * math.exp(SPIRAL_B * theta * 0.7)
        # cap radius
        if r > 3.5:
            continue
        # add jitter perpendicular to the arm direction
        jitter_a = rng.uniform(-0.10, 0.10)
        jitter_r = rng.uniform(-0.08, 0.08)
        x = (r + jitter_r) * math.cos(theta) + jitter_a * math.cos(theta + math.pi/2)
        y = (r + jitter_r) * math.sin(theta) + jitter_a * math.sin(theta + math.pi/2)
        z = rng.uniform(-0.05, 0.05)
        # color by distance from center
        if r < 0.4:
            mat = mat_star_white
            star_R = rng.uniform(0.020, 0.040)
        elif r < 0.9:
            mat = mat_star_yellow
            star_R = rng.uniform(0.018, 0.035)
        elif r < 1.6:
            mat = mat_star_blue if rng.random() < 0.25 else mat_star_yellow
            star_R = rng.uniform(0.018, 0.030)
        elif r < 2.4:
            mat = mat_star_orange
            star_R = rng.uniform(0.016, 0.028)
        else:
            mat = mat_star_red
            star_R = rng.uniform(0.014, 0.024)
        s = _sphere(f"star_{arm}_{i}", star_R, (x, y, z), mat, u=8, v=6)
        s.parent = galaxy
        s.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        # 1 in 16 chance to be a "pulsar" with unique material
        if rng.random() < 0.06 and len(pulsing_stars) < 12:
            # give it its own emissive material so we can keyframe just this one
            color = mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value
            ump = pbr_mat(f"pulse_mat_{arm}_{i}",
                            (color[0], color[1], color[2]), 0.00, 0.10,
                            emission=((color[0], color[1], color[2]), 6.0))
            s.data.materials.clear()
            s.data.materials.append(ump)
            pulsing_stars.append((s, ump))

# --- bright nucleus (the galactic core) ---
nucleus = _sphere("nucleus", 0.20, (0, 0, 0), mat_nucleus, u=24, v=16,
                    scale=(1.0, 1.0, 0.45))
nucleus.parent = galaxy
nucleus.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# inner bright core halo (small bright disc)
core_halo = _sphere("core_halo", 0.10, (0, 0, 0), mat_nucleus, u=16, v=12,
                      scale=(2.4, 2.4, 0.2))
core_halo.parent = galaxy
core_halo.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# bar across the nucleus (a thin elongated emissive shape)
bar = _sphere("nucleus_bar", 0.20, (0, 0, 0), mat_nucleus, u=20, v=14,
                scale=(2.5, 0.6, 0.2))
bar.parent = galaxy
bar.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ---
FPS = 30
DURATION = 10.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# galaxy rotates slowly (0.5 turn per loop)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    galaxy.rotation_euler = (0, 0, math.pi * t)
    galaxy.keyframe_insert("rotation_euler", frame=f)
if galaxy.animation_data and galaxy.animation_data.action:
    for fc in galaxy.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Pulsing stars : each gets its own pulse rate
for idx, (s, ump) in enumerate(pulsing_stars):
    bsdf = ump.node_tree.nodes.get("Principled BSDF")
    em = bsdf.inputs["Emission Strength"]
    phase = idx * 0.7
    freq = 1.5 + (idx % 4) * 0.5
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        val = 5.0 + 6.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * freq + phase))
        em.default_value = val
        bpy.context.scene.frame_set(f)
        em.keyframe_insert(data_path="default_value", frame=f)

# Nucleus throbs gently
bsdf_n = mat_nucleus.node_tree.nodes.get("Principled BSDF")
em_n = bsdf_n.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_n.default_value = 25.0 + 10.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 0.4))
    bpy.context.scene.frame_set(f)
    em_n.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"GAL_OK: {out_glb}", flush=True)
'''


def make_galaxy(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_gal_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "GAL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_galaxy(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
