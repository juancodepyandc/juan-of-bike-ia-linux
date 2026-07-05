"""Procedural paraglider (Blender headless).

Wide arc-shaped wing made of 8 alternating orange/white "cells" + 6
suspension lines descending to a harness + pilot figure dangling.
Animation : wing cells subtly undulate in Z (thermal turbulence), and
the entire harness assembly swings as a pendulum under the wing.

CLI:
  python proc_paraglider.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "paraglider.glb"

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

mat_sky      = pbr_mat("sky",       (0.55, 0.78, 0.95), 0.00, 0.95)
mat_orange   = pbr_mat("orange",    (0.92, 0.50, 0.10), 0.05, 0.55)
mat_white    = pbr_mat("white",     (0.95, 0.95, 0.92), 0.05, 0.50)
mat_red      = pbr_mat("red",       (0.85, 0.18, 0.12), 0.10, 0.45)
mat_line     = pbr_mat("line",      (0.85, 0.85, 0.85), 0.10, 0.65)
mat_harness  = pbr_mat("harness",   (0.10, 0.10, 0.12), 0.05, 0.65)
mat_pilot_s  = pbr_mat("pilot_suit",(0.18, 0.30, 0.55), 0.05, 0.55)
mat_helmet   = pbr_mat("helmet",    (0.85, 0.85, 0.88), 0.20, 0.30)
mat_skin     = pbr_mat("skin",      (0.85, 0.65, 0.50), 0.00, 0.55)
mat_carab    = pbr_mat("carabiner", (0.65, 0.65, 0.68), 0.85, 0.35)

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

# Conventions : pilot at origin (z=0 chest level), wing high above. Up = +Z.

# --- distant ground "sky background" plate (just a faint blue plane to give context) ---
_box("sky_back", 5.0, 0.04, 4.0, (0, 2.5, 1.0), mat_sky)

# --- wing parent empty (so the whole wing curve can subtly bob too) ---
WING_Z = 2.50
WING_W = 3.20
N_CELLS = 8
WING_DEPTH = 0.50
WING_RIB = 0.10
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, WING_Z))
wing_root = bpy.context.active_object
wing_root.name = "wing_root"

# Build 8 wing cells arranged on a horizontal arc (curving toward the pilot
# in -Y direction). Each cell is an orange/white slab tilted along the arc.
wing_cells = []   # list of (obj, x_position_relative)
for i in range(N_CELLS):
    a = -math.pi * 0.35 + (math.pi * 0.70) * i / (N_CELLS - 1)
    # arc radius — the wing is a wide shallow arc
    R = WING_W * 0.5 / math.sin(math.pi * 0.35)
    cx = R * math.sin(a)
    cz = -R * (1 - math.cos(a)) + 0.10
    # cell width
    cell_w = WING_W / N_CELLS * 0.92
    # tilt cell around Y axis so it follows the arc
    rot_y = -a * 0.7  # slight follow of curve, exaggerated for visibility
    mat = mat_orange if i % 2 == 0 else mat_white
    cell = _box(f"wing_cell_{i}", cell_w, WING_DEPTH, WING_RIB,
                  (cx, 0, cz), mat, rot=(0, rot_y, 0))
    cell.parent = wing_root
    cell.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    wing_cells.append((cell, cz, rot_y))
    # rib divider between cells (a thin strip)
    if i < N_CELLS - 1:
        div_x = R * math.sin(-math.pi * 0.35 + math.pi * 0.70 * (i + 0.5) / (N_CELLS - 1))
        div_z = -R * (1 - math.cos(-math.pi * 0.35 + math.pi * 0.70 * (i + 0.5) / (N_CELLS - 1))) + 0.10
        div = _box(f"wing_rib_{i}", 0.012, WING_DEPTH * 0.95, WING_RIB * 1.1,
                     (div_x, 0, div_z), mat_red,
                     rot=(0, -(-math.pi * 0.35 + math.pi * 0.70 * (i + 0.5) / (N_CELLS - 1)) * 0.7, 0))
        div.parent = wing_root
        div.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- harness pivot : a single point under the wing center, all the
# lines + harness + pilot are children of this pivot ---
HARNESS_Z = 0.30
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, HARNESS_Z))
harness_pivot = bpy.context.active_object
harness_pivot.name = "harness_pivot"

# --- 6 suspension lines ---
# Lines go from the wing's underside (3 left + 3 right) to the harness top.
# In the harness frame, they converge at z ~ +0.5 (from harness pivot's perspective).
LINE_TOPS = []
for k in range(6):
    sx_idx = k % 3  # 0, 1, 2
    side = 1 if k < 3 else -1
    # attach point on wing : along X = side * (WING_W * 0.10 + sx_idx * 0.15)
    wing_attach_x = side * (WING_W * 0.10 + sx_idx * 0.15)
    # find approximate Z on the arc at that X
    # R from wing build = same as above
    R = WING_W * 0.5 / math.sin(math.pi * 0.35)
    a_attach = math.asin(min(0.99, wing_attach_x / R)) if R else 0
    wing_attach_z = WING_Z - R * (1 - math.cos(a_attach)) + 0.05
    # bottom anchor on the harness top
    harness_anchor_x = side * 0.08
    harness_anchor_z = HARNESS_Z + 0.15
    p0 = mathutils.Vector((wing_attach_x, 0, wing_attach_z))
    p1 = mathutils.Vector((harness_anchor_x, 0, harness_anchor_z))
    LINE_TOPS.append((p0, p1))
    d = p1 - p0
    L = d.length
    midp = (p0 + p1) * 0.5
    seg = _cyl(f"line_{k}", 0.003, 0.003, L, 'Z', (0,0,0), mat_line, segments=6)
    seg.location = midp
    direction = d.normalized()
    seg.rotation_mode = 'QUATERNION'
    seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
    # the line is parented to the harness pivot so it swings with it
    # (we ignore the wing-side end moving for simplicity — small visual cheat)
    seg.parent = harness_pivot
    # we need to compute its local position relative to harness_pivot
    # since pivot is at (0,0,HARNESS_Z), local = world - pivot
    seg.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    seg.location = (midp.x, midp.y, midp.z - HARNESS_Z)

# --- harness body ---
hb = _box("harness_body", 0.30, 0.25, 0.40,
            (0, 0, 0.05), mat_harness)
hb.parent = harness_pivot
hb.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# carabiners (chrome connectors at top of harness)
for sx in (-1, +1):
    cc = _sphere(f"carab_{sx}", 0.018,
                   (sx * 0.08, 0, 0.18), mat_carab)
    cc.parent = harness_pivot
    cc.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- pilot figure (very simple) ---
# torso
torso = _box("pilot_torso", 0.20, 0.18, 0.32,
               (0, 0, 0.30), mat_pilot_s)
torso.parent = harness_pivot
torso.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# head + helmet
helmet = _sphere("pilot_helmet", 0.10, (0, 0, 0.55), mat_helmet)
helmet.parent = harness_pivot
helmet.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# face
face = _sphere("pilot_face", 0.06, (0, -0.04, 0.53), mat_skin)
face.parent = harness_pivot
face.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 arms held up holding the brake toggles
for sx in (-1, +1):
    arm = _cyl(f"pilot_arm_{sx}", 0.020, 0.020, 0.30, 'Z',
                 (sx * 0.14, 0, 0.30), mat_pilot_s, segments=8)
    arm.rotation_euler = (0, sx * math.radians(20), 0)
    arm.parent = harness_pivot
    arm.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 legs forward
for sx in (-1, +1):
    leg = _cyl(f"pilot_leg_{sx}", 0.025, 0.025, 0.40, 'Z',
                 (sx * 0.06, -0.10, -0.05), mat_pilot_s, segments=8)
    leg.rotation_euler = (math.radians(-25), 0, 0)
    leg.parent = harness_pivot
    leg.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Wing cells undulate (each cell Z position bobs slightly with phase)
for idx, (cell, home_z, rot_y) in enumerate(wing_cells):
    phase = idx * math.pi / 4
    home_loc = cell.location.copy()
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        z_off = 0.020 * math.sin(2*math.pi*t * 1.0 + phase)
        cell.location = (home_loc.x, home_loc.y, home_loc.z + z_off)
        cell.keyframe_insert("location", frame=f)
    if cell.animation_data and cell.animation_data.action:
        for fc in cell.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

# Harness swings as a pendulum (rotation X around harness pivot)
PAD_AMP = math.radians(6)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    angle_y = math.radians(4) * math.sin(2*math.pi*t * 0.6)   # left-right sway
    angle_x = math.radians(3) * math.sin(2*math.pi*t * 0.8 + 1.0)  # forward-back
    harness_pivot.rotation_euler = (angle_x, angle_y, 0)
    harness_pivot.keyframe_insert("rotation_euler", frame=f)
if harness_pivot.animation_data and harness_pivot.animation_data.action:
    for fc in harness_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"PG_OK: {out_glb}", flush=True)
'''


def make_paraglider(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_pg_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "PG_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_paraglider(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
