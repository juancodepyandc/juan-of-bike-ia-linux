"""Procedural jet ski / wave-runner (Blender headless).

Sleek red sport-class hull with curved nose + saddle seat + chrome
handlebars + black instrument pod + rear jet nozzle + 5 white spray
spheres trailing as wake + translucent blue water plane. Animation :
the ski bobs on the water (location Z sin) and pitches forward when
accelerating; the wake spheres expand and trail behind.

CLI:
  python proc_jet_ski.py <output_glb>
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
import bpy, bmesh, math, mathutils, sys

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "jetski.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough, alpha=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if alpha is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
            m.blend_method = 'BLEND'
    return m

mat_water  = pbr_mat("water",   (0.10, 0.40, 0.65), 0.05, 0.10, alpha=0.55)
mat_red    = pbr_mat("red",     (0.85, 0.10, 0.10), 0.10, 0.30)
mat_white  = pbr_mat("white",   (0.95, 0.95, 0.92), 0.10, 0.30)
mat_dark   = pbr_mat("dark",    (0.06, 0.06, 0.07), 0.30, 0.40)
mat_chrome = pbr_mat("chrome",  (0.80, 0.82, 0.85), 1.00, 0.18)
mat_seat   = pbr_mat("seat",    (0.10, 0.10, 0.12), 0.05, 0.55)
mat_spray  = pbr_mat("spray",   (0.95, 0.95, 0.92), 0.00, 0.50, alpha=0.55)
mat_stripe = pbr_mat("stripe",  (0.20, 0.20, 0.85), 0.10, 0.35)

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=16, rot=None):
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

# Conventions : ski along Y, nose at -Y. Up = +Z.

# --- water plane ---
_box("water_plane", 4.0, 5.0, 0.04, (0, 0, -0.04), mat_water)

# Ski dims
SKI_LEN = 2.20
SKI_W = 0.60
SKI_H = 0.30

# --- main hull (flattened ellipsoid, red) ---
hull_pivot_loc = mathutils.Vector((0, 0, 0.15))
bpy.ops.object.empty_add(type='PLAIN_AXES', location=hull_pivot_loc)
ski_pivot = bpy.context.active_object
ski_pivot.name = "ski_pivot"

# main body (red)
body = _sphere("hull_body", 0.30, (0, 0, 0), mat_red, u=24, v=16,
                 scale=(SKI_W / 2 / 0.30, SKI_LEN / 2 / 0.30, SKI_H / 2 / 0.30))
body.parent = ski_pivot
body.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# white belly (smaller white ellipsoid below)
belly = _sphere("hull_belly", 0.30, (0, 0, -SKI_H * 0.18), mat_white, u=20, v=14,
                  scale=(SKI_W * 0.85 / 2 / 0.30, SKI_LEN * 0.80 / 2 / 0.30, SKI_H * 0.45 / 2 / 0.30))
belly.parent = ski_pivot
belly.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# pointed nose (smaller red ellipsoid forward)
nose = _sphere("hull_nose", 0.30, (0, -SKI_LEN * 0.50, 0.04), mat_red, u=18, v=12,
                 scale=(SKI_W * 0.45 / 2 / 0.30, 0.30 / 2 / 0.30, SKI_H * 0.40 / 2 / 0.30))
nose.parent = ski_pivot
nose.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# blue stripe along the sides
for sx in (-1, +1):
    str_side = _box(f"stripe_{sx}", 0.008, SKI_LEN * 0.85, 0.030,
                      (sx * SKI_W * 0.45, 0, 0.02), mat_stripe)
    str_side.parent = ski_pivot
    str_side.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- saddle seat (long black cushion on top) ---
seat = _box("seat", SKI_W * 0.45, SKI_LEN * 0.55, 0.06,
              (0, 0.10, SKI_H * 0.50), mat_seat)
seat.parent = ski_pivot
seat.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- handlebars + instrument pod on the front ---
# instrument pod (a tilted black wedge)
pod = _box("pod", SKI_W * 0.50, 0.30, 0.10,
             (0, -SKI_LEN * 0.20, SKI_H * 0.55), mat_dark,
             rot=(math.radians(-25), 0, 0))
pod.parent = ski_pivot
pod.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 small chrome handlebar grips
for sx in (-1, +1):
    grip = _cyl(f"handlebar_grip_{sx}", 0.018, 0.018, 0.18, 'X',
                  (sx * 0.18, -SKI_LEN * 0.20, SKI_H * 0.65),
                  mat_chrome, segments=10)
    grip.parent = ski_pivot
    grip.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # grip tip
    tip = _sphere(f"handlebar_tip_{sx}", 0.022,
                    (sx * 0.27, -SKI_LEN * 0.20, SKI_H * 0.65),
                    mat_red)
    tip.parent = ski_pivot
    tip.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# steering column (vertical bar to pod)
_cyl("steer_column", 0.015, 0.015, 0.10, 'Z',
       (0, -SKI_LEN * 0.20, SKI_H * 0.60), mat_chrome).parent = ski_pivot

# small instrument gauge (a dark disc on the pod)
gauge = _cyl("gauge", 0.040, 0.040, 0.005, 'Y',
               (0, -SKI_LEN * 0.20 - 0.16, SKI_H * 0.50),
               mat_chrome, segments=14)
gauge.parent = ski_pivot
gauge.matrix_parent_inverse = mathutils.Matrix.Identity(4)
gauge_face = _cyl("gauge_face", 0.035, 0.035, 0.002, 'Y',
                    (0, -SKI_LEN * 0.20 - 0.165, SKI_H * 0.50),
                    mat_white, segments=14)
gauge_face.parent = ski_pivot
gauge_face.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- rear jet nozzle (dark cylinder protruding from +Y end) ---
nozzle = _cyl("nozzle", 0.06, 0.04, 0.08, 'Y',
                (0, SKI_LEN * 0.50 + 0.02, 0), mat_dark, segments=14)
nozzle.parent = ski_pivot
nozzle.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 5 spray spheres trailing behind, animated to scale + recede ---
sprays = []
for i in range(5):
    sx_off = (i - 2) * 0.08
    sy_off = SKI_LEN * 0.50 + 0.10 + i * 0.18
    sz_off = 0.05 + 0.03 * math.sin(i)
    sp = _sphere(f"spray_{i}", 0.06,
                   hull_pivot_loc + mathutils.Vector((sx_off, sy_off, sz_off)),
                   mat_spray,
                   scale=(1.0, 1.0, 0.7))
    sprays.append(sp)

# --- animation ---
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# ski_pivot bobs on water (Z) and pitches slightly (X rotation)
HOME_LOC = ski_pivot.location.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # Z bob : ±3 cm at 1 Hz
    z_off = 0.025 * math.sin(2*math.pi*t * 1.0)
    # X pitch : -5° base + ±3° (sin)
    pitch = math.radians(-3) + math.radians(4) * math.sin(2*math.pi*t * 1.3)
    # Y roll : slight ±2° lean
    roll = math.radians(2) * math.sin(2*math.pi*t * 1.1 + 0.5)
    ski_pivot.location = (HOME_LOC.x, HOME_LOC.y, HOME_LOC.z + z_off)
    ski_pivot.rotation_euler = (pitch, roll, 0)
    ski_pivot.keyframe_insert("location", frame=f)
    ski_pivot.keyframe_insert("rotation_euler", frame=f)
if ski_pivot.animation_data and ski_pivot.animation_data.action:
    for fc in ski_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# spray spheres : each grows from small to larger and recedes back (cycle)
for i, sp in enumerate(sprays):
    sx_off = (i - 2) * 0.08
    sy_off_base = SKI_LEN * 0.50 + 0.10 + i * 0.18
    sz_off = 0.05 + 0.03 * math.sin(i)
    phase = i / 5.0
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        local = (t * 2.0 + phase) % 1.0
        scale = 0.4 + 1.5 * (1 - local)  # large near hull, small far away
        # extra Y offset over the cycle (recedes back over time)
        y_extra = local * 0.6
        # fade alpha-equivalent by scaling close to 0 at end (visual hint)
        sp.scale = (scale, scale, scale * 0.7)
        sp.location = (HOME_LOC.x + sx_off, HOME_LOC.y + sy_off_base + y_extra, HOME_LOC.z + sz_off)
        sp.keyframe_insert("scale", frame=f)
        sp.keyframe_insert("location", frame=f)
    if sp.animation_data and sp.animation_data.action:
        for fc in sp.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"JS_OK: {out_glb}", flush=True)
'''


def make_jetski(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_js_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "JS_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_jetski(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
