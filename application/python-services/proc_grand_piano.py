"""Procedural grand piano (Blender headless).

Curved black-glossy body + 3 tapered legs + lid raised at angle on a
prop stick + keyboard with 21 white keys + 15 black keys + bench.
Animation : 6 random keys press down sequentially through the loop
(visible "playing" effect).

CLI:
  python proc_grand_piano.py <output_glb>
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

random.seed(7)

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "piano.glb"

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

mat_body    = pbr_mat("piano_black",  (0.02, 0.02, 0.03), 0.10, 0.10)
mat_white   = pbr_mat("ivory_white",  (0.92, 0.90, 0.86), 0.00, 0.30)
mat_black   = pbr_mat("ebony_black",  (0.04, 0.04, 0.05), 0.10, 0.25)
mat_floor   = pbr_mat("floor_wood",   (0.30, 0.20, 0.10), 0.00, 0.55)
mat_bench   = pbr_mat("bench_dark",   (0.15, 0.10, 0.08), 0.05, 0.35)
mat_pedal   = pbr_mat("pedal_brass",  (0.86, 0.62, 0.20), 1.00, 0.28)

def _box(name, sx, sy, sz, location, mat, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    if parent is not None:
        obj.parent = parent
        obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        obj.location = location  # preserve world coords as local from parent at origin
    return obj

def _cyl(name, R1, R2, depth, axis, location, mat, segments=20):
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

# --- floor ---------------------------------------------------------
_box("floor", 3.5, 2.6, 0.04, (0, 0, -0.04), mat_floor)

# --- body : a tapered egg-shape made via bmesh manual extrusion ---
# Approximation : a 5-section tapered prism with cross-section that gets
# narrower toward the back. Outline points (in XY plane, viewed from above):
#   front-left, front-right, mid-right, back-right (curve), tail
# We mirror Y -> -Y to get back-left.
BODY_THICK = 0.10
BODY_Z = 0.85   # height of the top surface
# 2D outline (Y is "left/right", X is "front to back")
outline = [
    (-0.70,  0.65),  # front-left corner
    (-0.70, -0.65),  # front-right corner
    ( 0.25, -0.75),  # mid-right wider
    ( 0.70, -0.55),  # back-right curve
    ( 0.85, -0.30),  # tail-right
    ( 0.92,  0.00),  # tail tip
    ( 0.85,  0.30),  # tail-left
    ( 0.70,  0.55),  # back-left curve
    ( 0.25,  0.75),  # mid-left wider
]
mesh_body = bpy.data.meshes.new("piano_body")
body = bpy.data.objects.new("piano_body", mesh_body)
bpy.context.collection.objects.link(body)
bm = bmesh.new()
# bottom + top rings, then stitch
bot_verts = [bm.verts.new((x, y, BODY_Z - BODY_THICK)) for (x, y) in outline]
top_verts = [bm.verts.new((x, y, BODY_Z)) for (x, y) in outline]
bm.verts.ensure_lookup_table()
N = len(outline)
# top face
bm.faces.new(top_verts)
# bottom face (reversed for outward normals)
bm.faces.new(list(reversed(bot_verts)))
# side faces
for i in range(N):
    j = (i + 1) % N
    bm.faces.new((bot_verts[i], bot_verts[j], top_verts[j], top_verts[i]))
bm.normal_update()
bm.to_mesh(mesh_body); bm.free()
body.data.materials.append(mat_body)

# --- 3 legs (tapered cylinders) ------------------------------------
LEG_BASE = 0.05
LEG_TOP  = 0.04
LEG_H    = BODY_Z - BODY_THICK
for (lx, ly) in [(-0.55, +0.55), (-0.55, -0.55), (+0.70, 0.0)]:
    _cyl(f"leg_{lx}_{ly}", LEG_BASE, LEG_TOP, LEG_H, 'Z',
           (lx, ly, LEG_H/2), mat_body)

# --- 3 brass pedals at the front -----------------------------------
for px in (-0.05, 0.0, 0.05):
    _box(f"pedal_{px}", 0.025, 0.06, 0.018,
           (-0.65, px, 0.02), mat_pedal)

# --- lid : a flat slab raised at angle on a prop stick ------------
# the lid pivots around the back-right corner area ; we represent it
# raised at 45 deg via a rotated thin box
mesh_lid = bpy.data.meshes.new("lid")
lid = bpy.data.objects.new("lid", mesh_lid)
bpy.context.collection.objects.link(lid)
bm = bmesh.new()
# build a flat slab matching the body outline (slightly smaller)
shrink = 0.95
top_pts = [(x * shrink, y * shrink, 0.0) for (x, y) in outline]
top_pts_above = [(x, y, 0.02) for (x, y, _) in top_pts]
bot_verts = [bm.verts.new(p) for p in top_pts]
top_verts = [bm.verts.new(p) for p in top_pts_above]
bm.verts.ensure_lookup_table()
N = len(outline)
bm.faces.new(top_verts)
bm.faces.new(list(reversed(bot_verts)))
for i in range(N):
    j = (i + 1) % N
    bm.faces.new((bot_verts[i], bot_verts[j], top_verts[j], top_verts[i]))
bm.normal_update()
bm.to_mesh(mesh_lid); bm.free()
lid.data.materials.append(mat_body)
# place + rotate the lid : pivot on the back-LEFT edge (y=+0.65, x ~ -0.70..0.25)
lid.location = (-0.10, 0.55, BODY_Z + 0.01)
lid.rotation_euler = (math.radians(-45), 0, 0)

# prop stick (short cylinder)
_cyl("prop_stick", 0.012, 0.012, 0.50, 'Z',
       (0.10, 0.20, BODY_Z + 0.25), mat_body)

# --- keyboard : 21 white keys + 15 black keys ---------------------
KEY_W = 0.045        # width per white key
KEY_L = 0.13         # length (back-to-front)
KEY_T = 0.010        # thickness
KEYBOARD_FRONT_X = -0.65 - KEY_L / 2 - 0.02  # front edge of the keys
KEYBOARD_Z       = BODY_Z + 0.005
N_WHITE = 21
TOTAL_W = N_WHITE * KEY_W
KEYBOARD_START_Y = -TOTAL_W / 2

key_pivots = []
for i in range(N_WHITE):
    ky = KEYBOARD_START_Y + (i + 0.5) * KEY_W
    bpy.ops.object.empty_add(type='PLAIN_AXES',
                              location=(KEYBOARD_FRONT_X, ky, KEYBOARD_Z))
    pv = bpy.context.active_object
    pv.name = f"white_pivot_{i}"
    white = _box(f"white_key_{i}", KEY_L, KEY_W * 0.95, KEY_T,
                   (0, 0, 0), mat_white)
    white.parent = pv
    white.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    white.location = (0, 0, 0)
    key_pivots.append(("white", pv, i))

# Black keys : positions in a piano octave (between certain white keys).
# In a single octave : black keys sit at white-key positions 0, 1, 3, 4, 5.
# Across 3 octaves (21 white = 3 octaves) : duplicate the pattern.
BLACK_PATTERN = [0, 1, 3, 4, 5]
black_offsets_in_octave = BLACK_PATTERN
n_octaves = N_WHITE // 7
for oct in range(n_octaves):
    for off in BLACK_PATTERN:
        wi = oct * 7 + off
        if wi + 1 >= N_WHITE:
            break
        # black key sits between white wi and wi+1
        ky = KEYBOARD_START_Y + (wi + 1) * KEY_W
        bpy.ops.object.empty_add(type='PLAIN_AXES',
                                  location=(KEYBOARD_FRONT_X - 0.025, ky, KEYBOARD_Z + 0.012))
        pv = bpy.context.active_object
        pv.name = f"black_pivot_{oct}_{off}"
        black = _box(f"black_key_{oct}_{off}", KEY_L * 0.65, KEY_W * 0.55, KEY_T * 1.4,
                       (0, 0, 0), mat_black)
        black.parent = pv
        black.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        black.location = (0, 0, 0)
        key_pivots.append(("black", pv, len(key_pivots)))

# --- bench (a short rectangular stool in front) -------------------
_box("bench_top", 0.18, 0.45, 0.04, (-1.20, 0, 0.45), mat_bench)
for sx in (-1, 1):
    for sy in (-1, 1):
        _box(f"bench_leg_{sx}_{sy}", 0.028, 0.028, 0.45,
               (-1.20 + sx * 0.06, sy * 0.18, 0.225), mat_bench)

# --- animation : 6 keys press down at staggered times -------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# pick 6 random keys to press, each gets a 0.5 s press window staggered
press_keys = random.sample(key_pivots, 6)
PRESS_WINDOW_FR = int(0.5 * FPS)
for slot, (typ, pv, _idx) in enumerate(press_keys):
    start_f = int(slot * (NFR - PRESS_WINDOW_FR) / 5) + 1
    end_f   = start_f + PRESS_WINDOW_FR
    # rest at frame 1
    pv.keyframe_insert("rotation_euler", frame=1)
    # at start_f : begin tilt
    bpy.context.scene.frame_set(start_f)
    pv.rotation_euler = (0, 0, 0)
    pv.keyframe_insert("rotation_euler", frame=start_f)
    # at mid : pressed
    bpy.context.scene.frame_set((start_f + end_f) // 2)
    pv.rotation_euler = (0, math.radians(4), 0)  # tilt forward
    pv.keyframe_insert("rotation_euler", frame=(start_f + end_f) // 2)
    # at end : back to rest
    bpy.context.scene.frame_set(end_f)
    pv.rotation_euler = (0, 0, 0)
    pv.keyframe_insert("rotation_euler", frame=end_f)
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"PIANO_OK: {out_glb}", flush=True)
'''


def make_piano(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_piano_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "PIANO_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_piano(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
