"""Procedural pinball machine (Blender headless).

Tilted playfield + 4 emissive round bumpers + 2 flippers in front + side
plunger + tall back-glass (emissive purple/yellow gradient) + 4 wooden
legs + glass cover hinted by a translucent slab. Animation : flippers
swing ±25 deg alternately + bumpers pulse their emission strength
together.

CLI:
  python proc_pinball_machine.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "pinball.glb"

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

mat_floor      = pbr_mat("floor",       (0.10, 0.10, 0.12), 0.00, 0.85)
mat_wood       = pbr_mat("cab_wood",    (0.18, 0.08, 0.05), 0.05, 0.55)
mat_wood_lt    = pbr_mat("cab_wood_lt", (0.30, 0.14, 0.06), 0.05, 0.50)
mat_play       = pbr_mat("play_green",  (0.10, 0.30, 0.16), 0.00, 0.60)
mat_chrome     = pbr_mat("chrome",      (0.78, 0.80, 0.83), 1.00, 0.18)
mat_ball       = pbr_mat("ball",        (0.85, 0.85, 0.88), 1.00, 0.12)
mat_red        = pbr_mat("red_plastic", (0.92, 0.10, 0.10), 0.10, 0.30)
mat_yellow     = pbr_mat("yel_plastic", (0.95, 0.85, 0.10), 0.10, 0.30)
mat_purple     = pbr_mat("purple",      (0.55, 0.15, 0.65), 0.10, 0.30)
mat_glass      = pbr_mat("glass",       (0.80, 0.85, 0.90), 0.00, 0.10, alpha=0.18)
mat_back_glass = pbr_mat("back_glass",  (0.05, 0.02, 0.10), 0.00, 0.10,
                            emission=((1.00, 0.20, 0.50), 5.0))
mat_bumper_a   = pbr_mat("bumper_a",    (0.10, 0.10, 0.15), 0.10, 0.30,
                            emission=((1.00, 0.20, 0.20), 4.0))
mat_bumper_b   = pbr_mat("bumper_b",    (0.10, 0.10, 0.15), 0.10, 0.30,
                            emission=((0.20, 0.55, 1.00), 4.0))
mat_bumper_c   = pbr_mat("bumper_c",    (0.10, 0.10, 0.15), 0.10, 0.30,
                            emission=((0.20, 1.00, 0.35), 4.0))
mat_bumper_d   = pbr_mat("bumper_d",    (0.10, 0.10, 0.15), 0.10, 0.30,
                            emission=((1.00, 0.85, 0.20), 4.0))

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

def _sphere(name, R, location, mat, u=16, v=10):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- floor -------------------------------------------------------
_box("floor", 1.6, 1.6, 0.04, (0, 0, -0.04), mat_floor)

# --- 4 wooden legs ----------------------------------------------
LEG_H = 0.78
LEG_W = 0.04
CAB_W = 0.62  # playfield width (X)
CAB_D = 1.10  # playfield depth (Y)
for sx in (-1, +1):
    for sy in (-1, +1):
        _box(f"leg_{sx}_{sy}", LEG_W, LEG_W, LEG_H,
               (sx * (CAB_W/2 - LEG_W), sy * (CAB_D/2 - LEG_W), LEG_H/2),
               mat_wood)

# --- cabinet body (the wooden box that holds the playfield) -----
CAB_Z = LEG_H + 0.04
_box("cab_body", CAB_W, CAB_D, 0.10, (0, 0, CAB_Z + 0.05), mat_wood_lt)
# side rails (light wood trim)
for sx in (-1, +1):
    _box(f"side_rail_{sx}", 0.02, CAB_D, 0.14,
           (sx * (CAB_W/2 + 0.005), 0, CAB_Z + 0.07), mat_wood)
_box("front_rail", CAB_W + 0.04, 0.025, 0.14,
       (0, -CAB_D/2 - 0.012, CAB_Z + 0.07), mat_wood)
_box("back_rail",  CAB_W + 0.04, 0.025, 0.14,
       (0, +CAB_D/2 + 0.012, CAB_Z + 0.07), mat_wood)

# --- playfield (tilted green surface) ----------------------------
# Playfield tilts ~7 deg : back side (+Y) higher than front (-Y)
TILT = math.radians(7)
play_y_offset = 0.0
play_z = CAB_Z + 0.13
playfield = _box("playfield", CAB_W * 0.96, CAB_D * 0.96, 0.012,
                   (0, play_y_offset, play_z), mat_play,
                   rot=(TILT, 0, 0))

# --- 4 bumpers on the playfield ---------------------------------
# Their (x,y) is on the local playfield; we apply the same tilt
# transform so they sit on the surface.
def on_play(x_local, y_local, h_above):
    """Convert local (x,y) on the tilted playfield to world (x,y,z)."""
    # tilt is around X, so y' = y*cos - z*sin ; z' = y*sin + z*cos
    z_local = 0.012/2 + h_above
    yw = y_local * math.cos(TILT) - z_local * math.sin(TILT)
    zw = y_local * math.sin(TILT) + z_local * math.cos(TILT)
    return (x_local, play_y_offset + yw, play_z + zw)

BUMPERS = [
    (-0.18,  0.20, mat_bumper_a),
    ( 0.18,  0.20, mat_bumper_b),
    (-0.18, -0.05, mat_bumper_c),
    ( 0.18, -0.05, mat_bumper_d),
]
bumper_mats = []
for i, (bx, by, bm_mat) in enumerate(BUMPERS):
    loc = on_play(bx, by, 0.04)
    bp = _cyl(f"bumper_{i}", 0.055, 0.045, 0.04, 'Z', loc, bm_mat, segments=18)
    bp.rotation_euler = (TILT, 0, 0)
    # chrome cap on top
    cap_loc = on_play(bx, by, 0.06)
    cap = _cyl(f"bumper_cap_{i}", 0.055, 0.030, 0.012, 'Z', cap_loc, mat_chrome, segments=18)
    cap.rotation_euler = (TILT, 0, 0)
    bumper_mats.append(bm_mat)

# --- 2 flippers at the bottom of the playfield -----------------
# Each flipper is a tapered box pivoting at one end.
FLIP_LEN = 0.13
FLIP_W   = 0.025
FLIP_T   = 0.012
# Pivots at the bottom of the playfield, on either side of the drain gap
FLIP_PIVOT_X = 0.08
FLIP_PIVOT_Y = -0.34

def make_flipper(name, side):
    # build a small box centered on (FLIP_LEN/2, 0, 0) so its rear is at x=0
    bpy.ops.mesh.primitive_cube_add(size=1, location=(FLIP_LEN/2, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (FLIP_LEN, FLIP_W, FLIP_T)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat_yellow)
    # parent to an empty positioned at the pivot, with playfield tilt
    pivot_world = on_play(side * FLIP_PIVOT_X, FLIP_PIVOT_Y, 0.012)
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=pivot_world)
    pv = bpy.context.active_object
    pv.name = name + "_pivot"
    pv.rotation_euler = (TILT, 0, 0)
    # If on the right (side=+1), the flipper points toward -X (mirrored).
    # We bake the mirror into the child's mesh rotation, NOT the pivot, so
    # animation of the pivot is clean.
    obj.rotation_euler = (0, 0, math.pi if side > 0 else 0)
    obj.parent = pv
    obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    return pv

flip_l = make_flipper("flipper_L", -1)
flip_r = make_flipper("flipper_R", +1)

# --- plunger (right side of cabinet, between front and middle) ---
plunger_base = _cyl("plunger_base", 0.025, 0.025, 0.06, 'Y',
                      (CAB_W/2 - 0.04, -CAB_D/2 + 0.18, CAB_Z + 0.10),
                      mat_chrome)
plunger_rod  = _cyl("plunger_rod", 0.012, 0.012, 0.16, 'Y',
                      (CAB_W/2 - 0.04, -CAB_D/2 + 0.30, CAB_Z + 0.10),
                      mat_chrome)
plunger_knob = _sphere("plunger_knob", 0.022,
                         (CAB_W/2 - 0.04, -CAB_D/2 + 0.40, CAB_Z + 0.10),
                         mat_red)

# --- pinball (steel ball resting on the playfield) ---------------
ball_loc = on_play(-0.05, -0.20, 0.02)
_sphere("ball", 0.020, ball_loc, mat_ball)

# --- back-glass : tall emissive panel behind the playfield ----
BG_H = 0.50
BG_W = CAB_W + 0.04
# the back-glass leans forward slightly toward the player
BG_Y = CAB_D/2 + 0.05
BG_Z = CAB_Z + 0.18 + BG_H/2
back = _box("back_glass", BG_W, 0.04, BG_H, (0, BG_Y, BG_Z), mat_back_glass,
              rot=(math.radians(-12), 0, 0))
# back-glass frame (dark wood)
_box("back_frame_top",    BG_W + 0.04, 0.06, 0.05,
       (0, BG_Y - 0.02, BG_Z + BG_H/2 + 0.03), mat_wood,
       rot=(math.radians(-12), 0, 0))
_box("back_frame_bottom", BG_W + 0.04, 0.06, 0.05,
       (0, BG_Y - 0.02, BG_Z - BG_H/2 - 0.03), mat_wood,
       rot=(math.radians(-12), 0, 0))
for sx in (-1, +1):
    _box(f"back_frame_side_{sx}", 0.04, 0.06, BG_H + 0.10,
           (sx * (BG_W/2 + 0.02), BG_Y - 0.02, BG_Z), mat_wood,
           rot=(math.radians(-12), 0, 0))

# --- thin translucent glass cover over the playfield -----------
glass_z = play_z + 0.10
_box("playfield_glass", CAB_W * 0.94, CAB_D * 0.94, 0.005,
       (0, play_y_offset, glass_z), mat_glass, rot=(TILT, 0, 0))

# --- animation -------------------------------------------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Flippers : alternate swing ±25 deg
FLIP_DEG = 25
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # 2 cycles per loop, opposite phase between L and R
    sL = math.radians(FLIP_DEG) * (0.5 + 0.5 * math.sin(2*math.pi*t*2))
    sR = math.radians(FLIP_DEG) * (0.5 + 0.5 * math.sin(2*math.pi*t*2 + math.pi))
    # rotation is around the (already-tilted) pivot's Z axis, but in the
    # parent's local frame this is just rotation_euler.z relative to the
    # baseline. The pivot itself has the playfield tilt baked in, so adding
    # rotation around Z makes the flipper swing in the playfield plane.
    flip_l.rotation_euler = (TILT, 0,  sL)
    flip_r.rotation_euler = (TILT, 0, -sR + math.pi)  # mirror still pointing inward
    flip_l.keyframe_insert("rotation_euler", frame=f)
    flip_r.keyframe_insert("rotation_euler", frame=f)
for pv in (flip_l, flip_r):
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

# Bumpers : pulse emission strength in sync
em_inputs = []
for bm_mat in bumper_mats:
    bsdf = bm_mat.node_tree.nodes.get("Principled BSDF")
    em_inputs.append(bsdf.inputs["Emission Strength"])
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    val = 2.5 + 3.5 * (0.5 + 0.5 * math.sin(2*math.pi*t*3))
    bpy.context.scene.frame_set(f)
    for em in em_inputs:
        em.default_value = val
        em.keyframe_insert(data_path="default_value", frame=f)

# back-glass pulses gently, twice slower
bsdf_bg = mat_back_glass.node_tree.nodes.get("Principled BSDF")
em_bg = bsdf_bg.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_bg.default_value = 4.0 + 2.5 * (0.5 + 0.5 * math.sin(2*math.pi*t*1.5))
    bpy.context.scene.frame_set(f)
    em_bg.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"PINBALL_OK: {out_glb}", flush=True)
'''


def make_pinball(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_pin_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "PINBALL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_pinball(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
