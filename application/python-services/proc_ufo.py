"""Procedural UFO flying saucer (Blender headless).

Classic flying saucer : flat metallic disc body + 6 emissive viewports
around the perimeter + transparent dome on top + 3 thruster glow orbs
underneath + a translucent abduction beam shining downward + a ground
puddle. Animation : disc rotates around its vertical axis, viewports
cycle through 4 colors in sequence, thrusters pulse, abduction beam
flickers.

CLI:
  python proc_ufo.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "ufo.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

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

mat_floor    = pbr_mat("floor",    (0.10, 0.18, 0.10), 0.00, 0.85)
mat_grass    = pbr_mat("grass",    (0.15, 0.30, 0.12), 0.00, 0.85)
mat_hull     = pbr_mat("hull",     (0.55, 0.55, 0.60), 1.00, 0.20)
mat_hull_d   = pbr_mat("hull_d",   (0.30, 0.30, 0.35), 1.00, 0.30)
mat_dome     = pbr_mat("dome",     (0.55, 0.85, 0.95), 0.00, 0.05, alpha=0.30)
mat_pilot    = pbr_mat("pilot",    (0.30, 0.85, 0.35), 0.00, 0.55,
                          emission=((0.40, 1.00, 0.50), 3.0))
mat_view     = pbr_mat("view",     (1.00, 0.85, 0.30), 0.00, 0.10,
                          emission=((1.00, 0.85, 0.30), 6.0))
mat_thrust   = pbr_mat("thrust",   (0.55, 0.85, 1.00), 0.00, 0.10,
                          emission=((0.55, 0.85, 1.00), 10.0))
mat_beam     = pbr_mat("beam",     (1.00, 0.95, 0.65), 0.00, 0.10,
                          alpha=0.22,
                          emission=((1.00, 0.95, 0.65), 5.0))
mat_puddle   = pbr_mat("puddle",   (1.00, 0.95, 0.65), 0.00, 0.10,
                          alpha=0.45,
                          emission=((1.00, 0.95, 0.65), 1.5))

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

def _cyl(name, R1, R2, depth, axis, location, mat, segments=24, rot=None):
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

# --- ground ---
_box("floor", 4.0, 4.0, 0.04, (0, 0, -0.04), mat_floor)
# grass patch in the spotlight
_cyl("grass_lit", 1.0, 1.0, 0.020, 'Z', (0, 0, 0.012), mat_grass, segments=32)
# illuminated puddle/circle on the ground (where the beam lands)
_cyl("beam_puddle", 0.45, 0.45, 0.005, 'Z', (0, 0, 0.025), mat_puddle, segments=32)

# UFO hovers at this Z
UFO_Z = 1.40
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, UFO_Z))
ufo_pivot = bpy.context.active_object
ufo_pivot.name = "ufo_pivot"

# --- main disc body : 2 flat cones stacked (lens shape) ---
DISC_R = 0.70
# upper half (cone tapering up)
upper = _cyl("disc_upper", DISC_R, 0.30, 0.12, 'Z', (0, 0, 0.06), mat_hull, segments=32)
upper.parent = ufo_pivot
upper.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# lower half (cone tapering down)
lower = _cyl("disc_lower", DISC_R, 0.40, 0.10, 'Z', (0, 0, -0.05), mat_hull_d, segments=32)
lower.parent = ufo_pivot
lower.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# central edge ring (a thin disc at the widest point)
edge = _cyl("disc_edge", DISC_R + 0.01, DISC_R + 0.01, 0.020, 'Z',
              (0, 0, 0.005), mat_hull_d, segments=32)
edge.parent = ufo_pivot
edge.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 6 viewport lights around the edge ---
view_objs = []
view_mats = []
for i in range(6):
    a = 2*math.pi * i / 6
    vx = (DISC_R + 0.005) * math.cos(a)
    vy = (DISC_R + 0.005) * math.sin(a)
    # each viewport gets its own emissive material for individual flicker
    base_col = (1.00, 0.85, 0.30)
    mat_u = pbr_mat(f"view_unique_{i}", base_col, 0.00, 0.10,
                      emission=(base_col, 6.0))
    view_mats.append(mat_u)
    # small flattened sphere
    v = _sphere(f"view_{i}", 0.045, (vx, vy, 0.005), mat_u,
                  u=12, v=10, scale=(0.8, 0.8, 1.4))
    # rotate it so its long axis aligns radially (cosmetic)
    v.rotation_euler = (0, 0, a + math.pi/2)
    v.parent = ufo_pivot
    v.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    view_objs.append(v)

# --- transparent dome on top ---
dome = _sphere("dome", 0.30, (0, 0, 0.12), mat_dome, u=24, v=14,
                 scale=(1.0, 1.0, 0.7))
dome.parent = ufo_pivot
dome.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# little green alien pilot inside (small sphere)
pilot = _sphere("pilot", 0.07, (0, 0, 0.10), mat_pilot, u=14, v=10,
                  scale=(1.0, 1.0, 1.3))
pilot.parent = ufo_pivot
pilot.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 3 thrusters underneath (small emissive orbs) ---
thrust_objs = []
for i in range(3):
    a = 2*math.pi * i / 3
    tx = 0.30 * math.cos(a)
    ty = 0.30 * math.sin(a)
    th = _sphere(f"thrust_{i}", 0.05, (tx, ty, -0.13), mat_thrust,
                   u=12, v=10, scale=(1.0, 1.0, 0.6))
    th.parent = ufo_pivot
    th.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    thrust_objs.append(th)

# --- abduction beam : a tapered translucent cone from disc bottom to ground ---
beam = _cyl("beam", 0.20, 0.45, UFO_Z - 0.05, 'Z',
              (0, 0, -(UFO_Z - 0.05)/2 - 0.10), mat_beam, segments=24)
beam.parent = ufo_pivot
beam.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# UFO rotates around Z + slight Z bob
HOME_LOC = ufo_pivot.location.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    z_off = 0.04 * math.sin(2*math.pi*t * 0.6)
    ufo_pivot.location = (HOME_LOC.x, HOME_LOC.y, HOME_LOC.z + z_off)
    ufo_pivot.rotation_euler = (0, 0, 2*math.pi * 0.5 * t)
    ufo_pivot.keyframe_insert("location", frame=f)
    ufo_pivot.keyframe_insert("rotation_euler", frame=f)
if ufo_pivot.animation_data and ufo_pivot.animation_data.action:
    for fc in ufo_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# 6 viewports : cycle through 4 colors with chained delay
COLORS = [
    (1.00, 0.85, 0.30),   # warm yellow
    (0.30, 0.85, 1.00),   # cyan
    (0.95, 0.30, 0.95),   # magenta
    (0.30, 1.00, 0.40),   # green
]
for i, mat_u in enumerate(view_mats):
    bsdf = mat_u.node_tree.nodes.get("Principled BSDF")
    em_col = bsdf.inputs["Emission Color"]
    em_str = bsdf.inputs["Emission Strength"]
    phase = i / 6.0
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        local = (t + phase) % 1.0
        idx = int(local * len(COLORS)) % len(COLORS)
        em_col.default_value = (*COLORS[idx], 1.0)
        em_str.default_value = 4.0 + 4.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 4 + phase * 6.28))
        bpy.context.scene.frame_set(f)
        em_col.keyframe_insert(data_path="default_value", frame=f)
        em_str.keyframe_insert(data_path="default_value", frame=f)

# 3 thrusters pulse
bsdf_th = mat_thrust.node_tree.nodes.get("Principled BSDF")
em_th = bsdf_th.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_th.default_value = 8.0 + 5.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 6))
    bpy.context.scene.frame_set(f)
    em_th.keyframe_insert(data_path="default_value", frame=f)

# Beam flickers
bsdf_b = mat_beam.node_tree.nodes.get("Principled BSDF")
em_b = bsdf_b.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_b.default_value = 4.0 + 2.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 3))
    bpy.context.scene.frame_set(f)
    em_b.keyframe_insert(data_path="default_value", frame=f)

# Puddle pulse with beam
bsdf_p = mat_puddle.node_tree.nodes.get("Principled BSDF")
em_p = bsdf_p.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_p.default_value = 1.0 + 1.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 3 + 0.5))
    bpy.context.scene.frame_set(f)
    em_p.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"UFO_OK: {out_glb}", flush=True)
'''


def make_ufo(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_ufo_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "UFO_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_ufo(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
