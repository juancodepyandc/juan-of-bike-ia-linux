"""Procedural hammock between 2 trees (Blender headless).

2 tree trunks with foliage canopies + multicolor-striped hammock canvas
sagging between them in a U-curve (8 segments) + ropes at each end +
small wooden frame "spreader bars" at each end + a few grass tufts +
ground patch. Animation : the hammock swings gently back and forth as
a pendulum (rotation Y around the line between the trees' anchor points).

CLI:
  python proc_hammock.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "hammock.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0xBEEF)

def pbr_mat(name, color, metal, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
    return m

mat_grass    = pbr_mat("grass",    (0.20, 0.45, 0.18), 0.00, 0.85)
mat_dirt     = pbr_mat("dirt",     (0.30, 0.20, 0.10), 0.00, 0.85)
mat_bark     = pbr_mat("bark",     (0.30, 0.18, 0.08), 0.05, 0.70)
mat_bark_d   = pbr_mat("bark_dk",  (0.20, 0.12, 0.05), 0.05, 0.75)
mat_leaf_a   = pbr_mat("leaf_a",   (0.18, 0.50, 0.20), 0.00, 0.65)
mat_leaf_b   = pbr_mat("leaf_b",   (0.30, 0.55, 0.18), 0.00, 0.60)
mat_rope     = pbr_mat("rope",     (0.55, 0.42, 0.20), 0.10, 0.65)
mat_wood     = pbr_mat("wood",     (0.55, 0.32, 0.16), 0.05, 0.55)
mat_h_red    = pbr_mat("h_red",    (0.85, 0.18, 0.12), 0.05, 0.55)
mat_h_yel    = pbr_mat("h_yel",    (0.95, 0.85, 0.20), 0.05, 0.55)
mat_h_blu    = pbr_mat("h_blu",    (0.18, 0.45, 0.85), 0.05, 0.55)
mat_h_grn    = pbr_mat("h_grn",    (0.18, 0.60, 0.30), 0.05, 0.55)
mat_h_org    = pbr_mat("h_org",    (0.95, 0.55, 0.18), 0.05, 0.55)
mat_h_pur    = pbr_mat("h_pur",    (0.55, 0.18, 0.65), 0.05, 0.55)

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

# Conventions : 2 trees on -X and +X, hammock spans X axis. Up = +Z.

# --- ground ---
_box("floor", 4.5, 3.5, 0.04, (0, 0, -0.04), mat_grass)
# dirt patches near tree bases
for sx in (-1, +1):
    _cyl(f"dirt_{sx}", 0.25, 0.25, 0.020, 'Z',
           (sx * 1.50, 0, 0.010), mat_dirt, segments=18)

# --- 2 trees ---
TREE_X = 1.50
TREE_H = 2.20
TRUNK_R = 0.12
for sx in (-1, +1):
    # trunk
    _cyl(f"trunk_{sx}", TRUNK_R * 1.1, TRUNK_R * 0.9, TREE_H, 'Z',
           (sx * TREE_X, 0, TREE_H/2 + 0.02), mat_bark, segments=14)
    # bark details (3 darker vertical stripes)
    for k in range(3):
        a = k * 2*math.pi / 3 + rng.uniform(-0.3, 0.3)
        bx = sx * TREE_X + (TRUNK_R * 0.95) * math.cos(a)
        by = (TRUNK_R * 0.95) * math.sin(a)
        _box(f"bark_strip_{sx}_{k}", 0.008, 0.004, TREE_H * 0.85,
               (bx, by, TREE_H/2 + 0.02), mat_bark_d)
    # foliage : 4 overlapping spheres forming a cluster canopy
    canopy_z = TREE_H + 0.05
    for k in range(4):
        a = k * math.pi/2 + 0.4
        cx = sx * TREE_X + 0.30 * math.cos(a)
        cy = 0.30 * math.sin(a)
        cz = canopy_z + (k % 2) * 0.15
        mat = mat_leaf_a if k % 2 == 0 else mat_leaf_b
        _sphere(f"foliage_{sx}_{k}", 0.45,
                  (cx, cy, cz), mat, u=18, v=12,
                  scale=(1.0, 1.0, 0.85))

# --- hammock pivot for animation ---
# We hang the hammock from points at (TREE_X - TRUNK_R) on each tree, at height ANCHOR_Z
ANCHOR_Z = 1.45
LEFT_ANCHOR = mathutils.Vector((-TREE_X + TRUNK_R, 0, ANCHOR_Z))
RIGHT_ANCHOR = mathutils.Vector((TREE_X - TRUNK_R, 0, ANCHOR_Z))
# pivot at midpoint of the anchor line
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(LEFT_ANCHOR + RIGHT_ANCHOR) * 0.5)
hammock_pivot = bpy.context.active_object
hammock_pivot.name = "hammock_pivot"

# rope segments from each anchor to the spreader bars
# Spreader bars sit ~50 cm below the anchor in rest pose, ~30 cm short of the anchors
SPREAD_DROP = 0.50
LEFT_SPREAD = LEFT_ANCHOR + mathutils.Vector((0.25, 0, -SPREAD_DROP))
RIGHT_SPREAD = RIGHT_ANCHOR + mathutils.Vector((-0.25, 0, -SPREAD_DROP))

# in the local frame of hammock_pivot, anchors are above and to the sides
# we need to compute local positions
PIV_LOC = (LEFT_ANCHOR + RIGHT_ANCHOR) * 0.5
def to_local(p):
    return p - PIV_LOC

# 2 ropes per anchor (3 each : Y front-back fanning into the spreader)
for side, anchor, spread in (("L", LEFT_ANCHOR, LEFT_SPREAD), ("R", RIGHT_ANCHOR, RIGHT_SPREAD)):
    for k, sy_off in enumerate((-0.15, 0, +0.15)):
        # rope from anchor to spread + sy_off
        p_anchor = anchor
        p_spread = spread + mathutils.Vector((0, sy_off, 0))
        p_anchor_loc = to_local(p_anchor)
        p_spread_loc = to_local(p_spread)
        d = p_spread_loc - p_anchor_loc
        L = d.length
        midp = (p_anchor_loc + p_spread_loc) * 0.5
        seg = _cyl(f"rope_{side}_{k}", 0.005, 0.005, L, 'Z', (0,0,0), mat_rope, segments=6)
        seg.location = midp
        direction = d.normalized()
        seg.rotation_mode = 'QUATERNION'
        seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
        seg.parent = hammock_pivot
        seg.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# spreader bars (wooden bars across at each end)
SPREAD_W = 0.50
for side, spread in (("L", LEFT_SPREAD), ("R", RIGHT_SPREAD)):
    bar = _cyl(f"spread_{side}", 0.012, 0.012, SPREAD_W, 'Y',
                 (0, 0, 0), mat_wood, segments=10)
    bar.location = to_local(spread)
    bar.parent = hammock_pivot
    bar.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- hammock canvas : 8 horizontal stripe segments forming a U-curve ---
# The curve dips down from each spreader to a sag point in the middle.
# Parametric : z = -sag * (1 - (2x/span)²) along x. Build as 8 stripes (slabs) along X.
SAG_Z = 0.45
HAMMOCK_LEN = (RIGHT_SPREAD - LEFT_SPREAD).length
N_STRIPES = 8
STRIPE_COLORS = [mat_h_red, mat_h_yel, mat_h_blu, mat_h_grn,
                  mat_h_org, mat_h_pur, mat_h_red, mat_h_yel]
for i in range(N_STRIPES):
    u_start = i / N_STRIPES
    u_end = (i + 1) / N_STRIPES
    u_mid = (u_start + u_end) * 0.5
    # x position in local frame (centered at pivot)
    x_local = (u_mid - 0.5) * HAMMOCK_LEN
    # z dip (parabolic from 0 at edges to -SAG_Z at middle)
    # we use u_mid * 2 - 1 in [-1, 1] then square
    centered = (u_mid - 0.5) * 2
    z_local = (LEFT_SPREAD.z - PIV_LOC.z) - SAG_Z * (1 - centered**2)
    # tilt the slab along Y to follow the curve : slope = d(z)/d(x)
    slope = SAG_Z * 4 * centered / HAMMOCK_LEN
    rot_y = -math.atan(slope)
    # stripe slab
    stripe_w = HAMMOCK_LEN / N_STRIPES * 1.02
    stripe = _box(f"stripe_{i}", stripe_w, SPREAD_W * 1.05, 0.010,
                    (0, 0, 0), STRIPE_COLORS[i],
                    rot=(0, rot_y, 0))
    stripe.location = (x_local, 0, z_local)
    stripe.parent = hammock_pivot
    stripe.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : hammock swings ---
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Hammock swings around X axis (the line between the tree anchors)
# Wait : the line between LEFT_ANCHOR and RIGHT_ANCHOR is along X, so a pendulum
# swing around that axis means rotation around X.
SWING_AMP = math.radians(12)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    angle = SWING_AMP * math.sin(2*math.pi*t * 0.7)
    hammock_pivot.rotation_euler = (angle, 0, 0)
    hammock_pivot.keyframe_insert("rotation_euler", frame=f)
if hammock_pivot.animation_data and hammock_pivot.animation_data.action:
    for fc in hammock_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"HAMM_OK: {out_glb}", flush=True)
'''


def make_hammock(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_hamm_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "HAMM_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_hammock(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
