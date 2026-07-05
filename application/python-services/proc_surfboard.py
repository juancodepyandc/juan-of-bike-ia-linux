"""Procedural surfboard on a wave (Blender headless).

Long pointed-nose surfboard with painted red + blue stripe + traction
pad on tail + 3 thruster fins + leash trailing behind. Sits on a
sculpted wave : 3 levels of wave segments creating a curl + foam at the
crest. Animation : surfboard tilts forward + back along its wave path
to simulate riding, plus the wave crests rise and fall slightly.

CLI:
  python proc_surfboard.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "surfboard.glb"

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

mat_sand    = pbr_mat("sand",      (0.92, 0.82, 0.55), 0.00, 0.85)
mat_water_d = pbr_mat("water_dk",  (0.10, 0.40, 0.65), 0.05, 0.10, alpha=0.55)
mat_water_l = pbr_mat("water_lt",  (0.30, 0.65, 0.85), 0.05, 0.10, alpha=0.50)
mat_foam    = pbr_mat("foam",      (0.95, 0.95, 0.92), 0.00, 0.50, alpha=0.85)
mat_white   = pbr_mat("white",     (0.95, 0.95, 0.92), 0.10, 0.30)
mat_red     = pbr_mat("red",       (0.85, 0.18, 0.12), 0.10, 0.35)
mat_blue    = pbr_mat("blue",      (0.20, 0.50, 0.92), 0.10, 0.35)
mat_dark    = pbr_mat("dark",      (0.08, 0.08, 0.09), 0.30, 0.45)
mat_pad     = pbr_mat("pad",       (0.20, 0.25, 0.30), 0.00, 0.85)
mat_leash   = pbr_mat("leash",     (0.40, 0.30, 0.20), 0.10, 0.60)

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

# Conventions : wave breaks toward -Y, board points -Y (nose). Up = +Z.

# --- sand beach background ---
_box("sand_beach", 5.0, 1.6, 0.04, (0, -2.2, 0.02), mat_sand)

# --- wave : 3 horizontal slabs creating tiers + foam crest ---
# Bottom wave layer (largest, base)
_box("wave_base", 4.5, 3.0, 0.30, (0, 0.5, 0.15), mat_water_d)
# Mid wave layer (slightly higher peak toward player)
_box("wave_mid", 4.0, 2.6, 0.20, (0, 0.30, 0.40), mat_water_l)
# Top wave (the curl, peaked)
_box("wave_top", 3.5, 1.4, 0.25, (0, 0.05, 0.65), mat_water_l,
       rot=(math.radians(-15), 0, 0))
# Foam crest (a tilted thin slab at the top of the wave)
foam = _box("wave_foam", 3.4, 0.4, 0.12, (0, -0.20, 0.85), mat_foam,
              rot=(math.radians(-30), 0, 0))
# 5 small foam spheres along the crest (irregular shape)
for k in range(5):
    fx = -1.4 + k * 0.7
    _sphere(f"foam_blob_{k}", 0.08, (fx, -0.30, 0.90), mat_foam,
              scale=(1.2, 0.8, 0.6))

# --- surfboard (animated, parented to a pivot empty) ---
BOARD_L = 1.80   # length along Y
BOARD_W = 0.35   # width along X
BOARD_T = 0.04   # thickness
# Rider position : on the rising face of the wave
RIDER_Y = 0.10
RIDER_Z = 0.60
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, RIDER_Y, RIDER_Z))
board_pivot = bpy.context.active_object
board_pivot.name = "board_pivot"

# main body (white slab)
deck = _box("board_deck", BOARD_W, BOARD_L, BOARD_T,
              (0, 0, 0), mat_white)
deck.parent = board_pivot
deck.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# pointed nose (smaller block on the front)
nose = _box("board_nose", BOARD_W * 0.6, 0.25, BOARD_T,
              (0, -BOARD_L/2 - 0.10, 0), mat_white)
nose.parent = board_pivot
nose.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# narrower tip
tip = _box("board_tip", BOARD_W * 0.3, 0.15, BOARD_T,
             (0, -BOARD_L/2 - 0.28, 0), mat_white)
tip.parent = board_pivot
tip.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# red stripe on top
red_stripe = _box("board_stripe_red", BOARD_W * 0.20, BOARD_L * 0.9, 0.003,
                    (0, 0, BOARD_T/2 + 0.002), mat_red)
red_stripe.parent = board_pivot
red_stripe.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# blue stripe (offset)
blue_stripe = _box("board_stripe_blue", BOARD_W * 0.06, BOARD_L * 0.9, 0.003,
                     (BOARD_W * 0.15, 0, BOARD_T/2 + 0.002), mat_blue)
blue_stripe.parent = board_pivot
blue_stripe.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# traction pad on tail
pad = _box("board_pad", BOARD_W * 0.85, 0.30, 0.008,
             (0, BOARD_L/2 - 0.20, BOARD_T/2 + 0.005), mat_pad)
pad.parent = board_pivot
pad.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 3 thruster fins on the bottom
FIN_POS = [(-0.10, BOARD_L/2 - 0.20),
            (+0.10, BOARD_L/2 - 0.20),
            (0.00,  BOARD_L/2 - 0.05)]
for k, (fx, fy) in enumerate(FIN_POS):
    fin = _box(f"fin_{k}", 0.020, 0.10, 0.07,
                 (fx, fy, -BOARD_T/2 - 0.035), mat_white)
    fin.parent = board_pivot
    fin.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# leash : 4 segments trailing from the tail
LEASH_PTS = [
    (0, BOARD_L/2 + 0.05, 0),
    (0.05, BOARD_L/2 + 0.20, -0.10),
    (0.10, BOARD_L/2 + 0.40, -0.20),
    (0.15, BOARD_L/2 + 0.60, -0.30),
]
for i in range(len(LEASH_PTS) - 1):
    p0 = mathutils.Vector(LEASH_PTS[i])
    p1 = mathutils.Vector(LEASH_PTS[i+1])
    d = p1 - p0
    L = d.length
    midp = (p0 + p1) * 0.5
    seg = _cyl(f"leash_{i}", 0.006, 0.006, L, 'Z', (0,0,0), mat_leash, segments=6)
    seg.location = midp
    direction = d.normalized()
    seg.rotation_mode = 'QUATERNION'
    seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
    seg.parent = board_pivot
    seg.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ---
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Board pitches forward and back as it rides
# Also translates slightly forward (-Y) over the wave
HOME_LOC = mathutils.Vector((0, RIDER_Y, RIDER_Z))
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # X position : sway laterally as if carving
    x_off = 0.15 * math.sin(2*math.pi*t * 1.0)
    # pitch (X rotation) : forward when accelerating, back when slowing
    pitch = math.radians(-15) + math.radians(10) * math.sin(2*math.pi*t * 1.2)
    # roll (Y rotation) : tilt left/right
    roll = math.radians(8) * math.sin(2*math.pi*t * 1.0 + 0.5)
    board_pivot.location = (HOME_LOC.x + x_off, HOME_LOC.y, HOME_LOC.z + 0.03 * math.sin(2*math.pi*t * 1.5))
    board_pivot.rotation_euler = (pitch, roll, 0)
    board_pivot.keyframe_insert("location", frame=f)
    board_pivot.keyframe_insert("rotation_euler", frame=f)
if board_pivot.animation_data and board_pivot.animation_data.action:
    for fc in board_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Foam crest scales Z slightly to simulate the wave's energy
home_foam_loc = foam.location.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    s = 1.0 + 0.15 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.5))
    foam.scale = (1, 1, s)
    foam.location = (home_foam_loc.x, home_foam_loc.y, home_foam_loc.z + 0.04 * (s - 1) / 0.15)
    foam.keyframe_insert("scale", frame=f)
    foam.keyframe_insert("location", frame=f)
if foam.animation_data and foam.animation_data.action:
    for fc in foam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SURF_OK: {out_glb}", flush=True)
'''


def make_surf(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_surf_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SURF_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_surf(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
