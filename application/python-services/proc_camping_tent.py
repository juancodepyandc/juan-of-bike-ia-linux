"""Procedural pyramidal camping tent (Blender headless).

4-sided pyramidal tent with green canvas walls + triangular door flap +
floor pad + 4 corner stakes + 4 guy lines to the stakes + a sleeping bag
peeking out of the open door. Animation : the door flap flutters open
+ closed gently as if a soft breeze is moving it.

CLI:
  python proc_camping_tent.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "tent.glb"

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

mat_grass    = pbr_mat("grass",    (0.20, 0.45, 0.18), 0.00, 0.85)
mat_canvas   = pbr_mat("canvas",   (0.18, 0.40, 0.20), 0.00, 0.75)  # forest green
mat_canvas_d = pbr_mat("canvas_d", (0.10, 0.28, 0.14), 0.00, 0.78)
mat_floor_t  = pbr_mat("floor_t",  (0.20, 0.18, 0.18), 0.00, 0.70)
mat_stake    = pbr_mat("stake",    (0.55, 0.55, 0.58), 0.85, 0.30)
mat_rope     = pbr_mat("rope",     (0.85, 0.85, 0.65), 0.10, 0.65)
mat_pole     = pbr_mat("pole",     (0.18, 0.18, 0.20), 0.50, 0.40)
mat_bag      = pbr_mat("bag",      (0.85, 0.18, 0.18), 0.05, 0.55)
mat_bag_inner= pbr_mat("bag_inner",(0.92, 0.92, 0.85), 0.00, 0.45)
mat_zipper   = pbr_mat("zipper",   (0.80, 0.82, 0.85), 1.00, 0.20)

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

def _sphere(name, R, location, mat, u=12, v=8):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# Conventions : tent at origin, door faces -Y. Apex on top. Up = +Z.

# --- grass ---
_box("floor_grass", 3.5, 3.5, 0.04, (0, 0, -0.04), mat_grass)

# Tent dims
T_W = 1.40   # base width X
T_D = 1.40   # base depth Y
T_H = 1.40   # apex height

# floor pad (a thin slab, slightly larger than the canvas base)
_box("floor_pad", T_W * 0.92, T_D * 0.92, 0.020, (0, 0, 0.012), mat_floor_t)

# --- 4 pyramidal canvas walls (triangles meeting at apex) ---
# Build each as a flat triangular box, tilted along its respective edge.
# We'll use a custom bmesh to make 4 triangles.
def make_wall_triangle(name, p_left, p_right, p_apex, mat):
    """Create a triangular face from 3 world-space points."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    v0 = bm.verts.new(p_left)
    v1 = bm.verts.new(p_right)
    v2 = bm.verts.new(p_apex)
    bm.faces.new([v0, v1, v2])
    bm.to_mesh(mesh); bm.free()
    obj.data.materials.append(mat)
    return obj

apex = (0, 0, T_H)
# 4 base corners
base_corners = [
    (-T_W/2, -T_D/2, 0.025),  # FL (front-left)
    (+T_W/2, -T_D/2, 0.025),  # FR
    (+T_W/2, +T_D/2, 0.025),  # BR
    (-T_W/2, +T_D/2, 0.025),  # BL
]

# left wall (BL -> FL -> apex)
make_wall_triangle("wall_left", base_corners[3], base_corners[0], apex, mat_canvas_d)
# right wall (FR -> BR -> apex)
make_wall_triangle("wall_right", base_corners[1], base_corners[2], apex, mat_canvas)
# back wall (BR -> BL -> apex)
make_wall_triangle("wall_back", base_corners[2], base_corners[3], apex, mat_canvas)
# Front face : split into 2 triangles (door is open) — we keep the left
# half (FL -> apex_below -> apex) and the right half is the open flap (animated)

# A "door frame" : top edge of the front face : from FL to FR via apex.
# We'll make 2 narrow side panels (slivers) on either side of the door.
# Left front sliver : from FL to apex via a vertical edge at x = -T_W/4 of the front
LEFT_SLIVER_FRONT_R = -T_W * 0.08
make_wall_triangle("front_left_sliver",
                     base_corners[0],
                     (LEFT_SLIVER_FRONT_R, -T_D/2, 0.025),
                     apex, mat_canvas)
RIGHT_SLIVER_FRONT_R = T_W * 0.08
make_wall_triangle("front_right_sliver",
                     (RIGHT_SLIVER_FRONT_R, -T_D/2, 0.025),
                     base_corners[1],
                     apex, mat_canvas)

# --- door flap : a triangular piece that pivots from the top edge ---
# Hinge at the apex (or top corner), flap extends down to the bottom door edge
# Build as a child of door_pivot for animation
DOOR_BASE_L = (LEFT_SLIVER_FRONT_R, -T_D/2, 0.025)
DOOR_BASE_R = (RIGHT_SLIVER_FRONT_R, -T_D/2, 0.025)
# door hinges at the top — we'll use a virtual hinge slightly down from apex
HINGE = (0, -T_D/2 + 0.01, T_H * 0.85)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=HINGE)
door_pivot = bpy.context.active_object
door_pivot.name = "door_pivot"
# door flap mesh (build with the pivot as origin)
mesh = bpy.data.meshes.new("door_flap")
flap = bpy.data.objects.new("door_flap", mesh)
bpy.context.collection.objects.link(flap)
bm = bmesh.new()
# 4 points : top-left, top-right, bottom-right, bottom-left (in local frame, pivot at origin)
v0 = bm.verts.new((LEFT_SLIVER_FRONT_R - HINGE[0], 0, HINGE[2] * 0.12))   # near hinge, left
v1 = bm.verts.new((RIGHT_SLIVER_FRONT_R - HINGE[0], 0, HINGE[2] * 0.12))  # near hinge, right
v2 = bm.verts.new((RIGHT_SLIVER_FRONT_R - HINGE[0], 0, -HINGE[2] * 0.85)) # bottom right
v3 = bm.verts.new((LEFT_SLIVER_FRONT_R - HINGE[0], 0, -HINGE[2] * 0.85))  # bottom left
bm.faces.new([v0, v1, v2, v3])
bm.to_mesh(mesh); bm.free()
flap.data.materials.append(mat_canvas_d)
flap.parent = door_pivot
flap.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# zipper line down the middle of the door
zipper = _box("door_zipper", 0.005, 0.002, T_H * 0.50,
                (0, 0, -T_H * 0.40), mat_zipper)
zipper.parent = door_pivot
zipper.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 4 corner stakes + guy lines from apex to each stake ---
for k, (cx, cy, _) in enumerate(base_corners):
    # stake (small pole driven into ground)
    sx_offset = math.copysign(0.20, cx)
    sy_offset = math.copysign(0.20, cy)
    stake_x = cx + sx_offset
    stake_y = cy + sy_offset
    _cyl(f"stake_{k}", 0.012, 0.005, 0.16, 'Z',
           (stake_x, stake_y, 0.05), mat_stake, segments=8)
    # guy line from apex to stake top
    p0 = mathutils.Vector(apex)
    p1 = mathutils.Vector((stake_x, stake_y, 0.10))
    d = p1 - p0
    midp = (p0 + p1) * 0.5
    seg = _cyl(f"guy_line_{k}", 0.004, 0.004, d.length, 'Z', (0,0,0), mat_rope, segments=6)
    seg.location = midp
    direction = d.normalized()
    seg.rotation_mode = 'QUATERNION'
    seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)

# --- apex cap (a small dark sphere at the top) ---
_sphere("apex_cap", 0.04, apex, mat_pole)

# --- sleeping bag peeking out the door ---
BAG_X = 0
BAG_Y = -T_D/2 - 0.15
BAG_Z = 0.05
_cyl("bag_body", 0.18, 0.18, 0.50, 'Y',
       (BAG_X, BAG_Y, BAG_Z), mat_bag, segments=16)
# bag opening at the +Y end (inside the tent — but we see it from outside as a darker rim)
_cyl("bag_open", 0.18, 0.18, 0.020, 'Y',
       (BAG_X, BAG_Y + 0.25, BAG_Z), mat_bag_inner, segments=16)
# 2 small zipper strips on top of the bag
for sx_z in (-1, +1):
    _box(f"bag_zip_{sx_z}", 0.005, 0.40, 0.005,
           (BAG_X + sx_z * 0.04, BAG_Y, BAG_Z + 0.16), mat_zipper)

# --- animation : door flap flutters ---
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# door_pivot rotates around X (the hinge axis is X at the top of the door)
FLAP_AMP = math.radians(18)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # primary slow flap + faster small jitter
    angle = math.radians(8) + FLAP_AMP * math.sin(2*math.pi*t * 0.7)
    angle += math.radians(4) * math.sin(2*math.pi*t * 2.3)
    door_pivot.rotation_euler = (angle, 0, 0)
    door_pivot.keyframe_insert("rotation_euler", frame=f)
if door_pivot.animation_data and door_pivot.animation_data.action:
    for fc in door_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"TENT_OK: {out_glb}", flush=True)
'''


def make_tent(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_tent_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "TENT_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_tent(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
