"""Procedural US suburban mailbox (Blender headless).

Half-cylinder metal body on a wooden post + rectangular hinged door
with chrome handle + red signal flag on a pivot arm + house number
plate + 2 envelopes peeking out of the door. Animation : red flag
raises from horizontal to vertical (mail has been delivered).

CLI:
  python proc_mailbox.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "mailbox.glb"

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

mat_floor    = pbr_mat("floor",     (0.18, 0.30, 0.14), 0.00, 0.85)
mat_dirt     = pbr_mat("dirt",      (0.32, 0.22, 0.14), 0.00, 0.85)
mat_wood     = pbr_mat("wood",      (0.32, 0.20, 0.10), 0.05, 0.55)
mat_wood_lt  = pbr_mat("wood_lt",   (0.42, 0.28, 0.14), 0.05, 0.50)
mat_metal    = pbr_mat("metal",     (0.55, 0.55, 0.58), 0.85, 0.30)
mat_metal_d  = pbr_mat("metal_dk",  (0.30, 0.30, 0.32), 0.85, 0.30)
mat_chrome   = pbr_mat("chrome",    (0.80, 0.82, 0.85), 1.00, 0.18)
mat_red      = pbr_mat("red",       (0.85, 0.15, 0.12), 0.10, 0.30)
mat_white    = pbr_mat("white",     (0.92, 0.92, 0.88), 0.00, 0.45)
mat_dark     = pbr_mat("dark",      (0.06, 0.06, 0.07), 0.10, 0.55)
mat_envelope = pbr_mat("envelope",  (0.90, 0.86, 0.78), 0.00, 0.55)
mat_stamp    = pbr_mat("stamp",     (0.85, 0.18, 0.18), 0.00, 0.45)

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=20, rot=None):
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

def _half_cyl(name, R, depth, axis, location, mat, segments=20, rot=None):
    """A half-cylinder : upper half (top dome shape) along the given axis."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    # Build full cylinder oriented along Z, then we'll mask its bottom by
    # only keeping verts with z >= 0 + caps.
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                            radius1=R, radius2=R, depth=depth)
    # Delete verts with z < 0 (this leaves an open arc).
    verts_to_del = [v for v in bm.verts if v.co.z < -1e-5]
    bmesh.ops.delete(bm, geom=verts_to_del, context='VERTS')
    # axis transform
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

# Conventions : mailbox on a yard. Door faces -Y. The half-cyl body is
# oriented with its axis along Y (so the arch is visible from -Y or +Y).

# --- yard ---------------------
_box("floor", 1.4, 1.2, 0.04, (0, 0, -0.04), mat_floor)
_box("dirt_patch", 0.45, 0.30, 0.025, (0, 0.05, 0.013), mat_dirt)

# --- post ---------------------
POST_H = 1.10
POST_BASE_Z = 0.025
POST_W = 0.06
_box("post", POST_W, POST_W, POST_H, (0, 0, POST_BASE_Z + POST_H/2), mat_wood)
# decorative cap at the top (slightly larger)
_box("post_cap", POST_W * 1.20, POST_W * 1.20, 0.025,
       (0, 0, POST_BASE_Z + POST_H + 0.012), mat_wood_lt)

# --- support arm (horizontal wooden plank extending forward -Y) ---
ARM_LEN = 0.32
ARM_Y = -ARM_LEN/2 + 0.02
_box("support_arm", POST_W * 0.8, ARM_LEN, 0.025,
       (0, ARM_Y, POST_BASE_Z + POST_H - 0.05), mat_wood)
# small diagonal brace
brace = _box("brace", POST_W * 0.6, 0.014, 0.30,
               (0, -0.14, POST_BASE_Z + POST_H * 0.72), mat_wood,
               rot=(math.radians(35), 0, 0))

# --- mailbox body (half-cylinder along Y) on top of the arm ---
BODY_R = 0.10
BODY_LEN = 0.30
BODY_Z = POST_BASE_Z + POST_H + 0.02 + BODY_R
BODY_Y = -ARM_LEN + 0.10
_half_cyl("body", BODY_R, BODY_LEN, 'Y',
            (0, BODY_Y, BODY_Z - BODY_R), mat_metal, segments=24)
# bottom flat plate (closes the half cyl underneath since we cut z<0)
_box("body_floor", BODY_R * 2 - 0.005, BODY_LEN, 0.008,
       (0, BODY_Y, BODY_Z - BODY_R), mat_metal)
# back wall (sealed +Y end)
_cyl("body_back", BODY_R, BODY_R, 0.012, 'Y',
       (0, BODY_Y + BODY_LEN/2 - 0.006, BODY_Z - BODY_R), mat_metal,
       segments=20, rot=None)
# Build a half-disc on the back actually by clipping the disc — simpler :
# leave the back fully visible as a disc (looks fine, ends with a circular
# cap whose lower half is hidden by the wooden arm below)

# --- door on -Y face (slightly recessed, with chrome handle) ---
DOOR_Y = BODY_Y - BODY_LEN/2 - 0.005
DOOR_R = BODY_R - 0.006
# door pivot at the hinge (bottom edge)
HINGE_Z = BODY_Z - BODY_R + 0.005
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, DOOR_Y, HINGE_Z))
door_pivot = bpy.context.active_object
door_pivot.name = "door_pivot"
door_pivot.rotation_euler = (0, 0, 0)  # closed
# door slab (a small disc facing -Y, parented so we could animate, but we'll
# leave it closed for this static look)
door_slab = _half_cyl("door_slab", DOOR_R, 0.008, 'Y',
                        (0, -0.004, BODY_R - 0.005), mat_metal, segments=20)
door_slab.parent = door_pivot
door_slab.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# door bottom plate
door_bot = _box("door_bot", DOOR_R * 2 - 0.005, 0.008, 0.008,
                  (0, -0.004, 0), mat_metal)
door_bot.parent = door_pivot
door_bot.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# chrome handle (a small horizontal bar at top of door)
handle = _cyl("door_handle", 0.005, 0.005, 0.040, 'X',
                (0, -0.012, BODY_R - 0.02), mat_chrome, segments=10)
handle.parent = door_pivot
handle.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 2 envelopes peeking out the bottom of the door (between door & body floor) ---
# They lean forward a bit
for k in range(2):
    ex = (k - 0.5) * 0.07
    env = _box(f"envelope_{k}", 0.06, 0.08, 0.020,
                 (ex, DOOR_Y - 0.005, BODY_Z - BODY_R + 0.015 + k * 0.004),
                 mat_envelope,
                 rot=(math.radians(-15), 0, 0))
    # red stamp on each
    _box(f"env_stamp_{k}", 0.015, 0.005, 0.012,
           (ex + 0.018, DOOR_Y - 0.014, BODY_Z - BODY_R + 0.022 + k * 0.004),
           mat_stamp, rot=(math.radians(-15), 0, 0))

# --- red signal flag on the right side (+X) ---
# Pivot at the side of the body, on the body's surface
FLAG_X = BODY_R + 0.012
FLAG_Y = BODY_Y - BODY_LEN * 0.15
FLAG_Z = BODY_Z - 0.02
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(FLAG_X, FLAG_Y, FLAG_Z))
flag_pivot = bpy.context.active_object
flag_pivot.name = "flag_pivot"
flag_pivot.rotation_euler = (0, math.radians(-90), 0)  # start horizontal pointing -Y

# flag post (a thin metal rod extending from pivot)
flag_post = _cyl("flag_post", 0.004, 0.004, 0.16, 'Z', (0, 0, 0.08), mat_metal_d)
flag_post.parent = flag_pivot
flag_post.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# flag rectangle (red, attached to top of post)
flag_rect = _box("flag_rect", 0.005, 0.08, 0.04, (0, 0.04, 0.14), mat_red)
flag_rect.parent = flag_pivot
flag_rect.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# small white border on the flag (a thin slab in front)
flag_white = _box("flag_white", 0.006, 0.04, 0.006, (0, 0.06, 0.14), mat_white)
flag_white.parent = flag_pivot
flag_white.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- house number plate (small white rectangle on the side of the body) ---
NUM_X = BODY_R + 0.001
NUM_Y = BODY_Y + BODY_LEN * 0.30
NUM_Z = BODY_Z - 0.04
_box("num_plate", 0.005, 0.07, 0.035, (NUM_X, NUM_Y, NUM_Z), mat_white)
# 3 dark digits (small rectangles)
for k in range(3):
    _box(f"num_digit_{k}", 0.003, 0.012, 0.015,
           (NUM_X + 0.002, NUM_Y - 0.025 + k * 0.020, NUM_Z), mat_dark)

# --- animation ---------------
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Flag : starts horizontal (Y=-90°) at t=0, raises to vertical (Y=0°) over
# t=[0.30, 0.50], then stays raised.
def flag_angle(t):
    if t < 0.30:
        return math.radians(-90)
    elif t < 0.50:
        u = (t - 0.30) / 0.20
        # ease-out
        u = 1.0 - (1.0 - u)**3
        return math.radians(-90 + 90 * u)
    elif t < 0.85:
        # tiny wiggle when raised
        local = (t - 0.50) / 0.35
        return math.radians(-2 + 4 * math.sin(local * 2*math.pi * 1.5))
    else:
        # falls back slowly for next cycle
        u = (t - 0.85) / 0.15
        return math.radians(0 - 90 * u)

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    flag_pivot.rotation_euler = (0, flag_angle(t), 0)
    flag_pivot.keyframe_insert("rotation_euler", frame=f)
if flag_pivot.animation_data and flag_pivot.animation_data.action:
    for fc in flag_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"MBOX_OK: {out_glb}", flush=True)
'''


def make_mailbox(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_mbox_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "MBOX_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_mailbox(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
