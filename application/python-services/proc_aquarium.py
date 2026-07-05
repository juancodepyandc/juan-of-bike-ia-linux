"""Procedural tropical aquarium (Blender headless).

Glass tank (translucent box) + dark base cabinet + metal lid + sand
substrate + 4 vertical green plants + pink coral cluster + 5 fish
(ellipsoid body + 3 triangular fins each) + 12 rising air bubbles
positioned at 3 distinct streams. Animation : each fish swims along its
own elliptical / sinusoidal path inside the tank + every bubble rises
linearly along Z and resets at top.

CLI:
  python proc_aquarium.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "aquarium.glb"

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

mat_floor    = pbr_mat("floor",       (0.18, 0.16, 0.18), 0.00, 0.85)
mat_cabinet  = pbr_mat("cabinet",     (0.15, 0.10, 0.08), 0.05, 0.55)
mat_lid      = pbr_mat("lid",         (0.18, 0.18, 0.20), 0.85, 0.25)
mat_glass    = pbr_mat("glass",       (0.55, 0.75, 0.85), 0.00, 0.05, alpha=0.18)
mat_water    = pbr_mat("water",       (0.25, 0.55, 0.75), 0.05, 0.05, alpha=0.30)
mat_sand     = pbr_mat("sand",        (0.85, 0.78, 0.55), 0.00, 0.85)
mat_plant_a  = pbr_mat("plant_a",     (0.18, 0.55, 0.20), 0.00, 0.55)
mat_plant_b  = pbr_mat("plant_b",     (0.10, 0.40, 0.15), 0.00, 0.60)
mat_coral_p  = pbr_mat("coral_pink",  (0.92, 0.40, 0.55), 0.00, 0.45)
mat_coral_o  = pbr_mat("coral_orng",  (0.95, 0.55, 0.20), 0.00, 0.45)
mat_rock     = pbr_mat("rock",        (0.30, 0.28, 0.25), 0.05, 0.75)
mat_fish_a   = pbr_mat("fish_orange", (0.95, 0.45, 0.10), 0.05, 0.30,
                          emission=((0.95, 0.45, 0.10), 0.6))
mat_fish_b   = pbr_mat("fish_blue",   (0.20, 0.55, 0.92), 0.05, 0.30,
                          emission=((0.20, 0.55, 0.92), 0.5))
mat_fish_c   = pbr_mat("fish_yellow", (1.00, 0.90, 0.20), 0.05, 0.30,
                          emission=((1.00, 0.90, 0.20), 0.5))
mat_fish_d   = pbr_mat("fish_pink",   (0.95, 0.40, 0.60), 0.05, 0.30,
                          emission=((0.95, 0.40, 0.60), 0.5))
mat_fish_e   = pbr_mat("fish_white",  (0.92, 0.92, 0.90), 0.05, 0.30)
mat_bubble   = pbr_mat("bubble",      (0.90, 0.95, 1.00), 0.00, 0.05, alpha=0.45)

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

# --- floor + cabinet ----------------------------------
_box("floor", 2.0, 1.4, 0.04, (0, 0, -0.04), mat_floor)

CAB_W, CAB_D, CAB_H = 0.90, 0.40, 0.55
_box("cabinet", CAB_W, CAB_D, CAB_H, (0, 0, CAB_H/2), mat_cabinet)
# decorative trim at top
_box("cab_trim", CAB_W + 0.02, CAB_D + 0.02, 0.02,
       (0, 0, CAB_H + 0.01), mat_cabinet)

# --- aquarium tank -----------------------------------
TANK_W, TANK_D, TANK_H = 0.85, 0.36, 0.40
TANK_Z = CAB_H + 0.02 + TANK_H/2
# Build the tank as 5 glass slabs (4 sides + bottom). Skip the top so the
# lid sits as a separate metal piece.
T = 0.008  # glass thickness
# bottom
_box("glass_bot", TANK_W, TANK_D, T,
       (0, 0, TANK_Z - TANK_H/2 + T/2), mat_glass)
# front
_box("glass_front", TANK_W, T, TANK_H,
       (0, -TANK_D/2 + T/2, TANK_Z), mat_glass)
# back
_box("glass_back", TANK_W, T, TANK_H,
       (0, TANK_D/2 - T/2, TANK_Z), mat_glass)
# left
_box("glass_left", T, TANK_D, TANK_H,
       (-TANK_W/2 + T/2, 0, TANK_Z), mat_glass)
# right
_box("glass_right", T, TANK_D, TANK_H,
       (TANK_W/2 - T/2, 0, TANK_Z), mat_glass)

# water volume (slightly under the rim, translucent blue)
WATER_H = TANK_H * 0.92
_box("water", TANK_W - 2*T - 0.005, TANK_D - 2*T - 0.005, WATER_H,
       (0, 0, TANK_Z - TANK_H/2 + T + WATER_H/2 + 0.001), mat_water)

# metal lid on top
LID_H = 0.04
_box("lid", TANK_W + 0.02, TANK_D + 0.02, LID_H,
       (0, 0, TANK_Z + TANK_H/2 + LID_H/2 + 0.002), mat_lid)
# lid handle
_cyl("lid_handle", 0.012, 0.012, 0.10, 'X',
       (0, 0, TANK_Z + TANK_H/2 + LID_H + 0.012), mat_lid)
# 2 LED lights under the lid (small emissive spots)
mat_led = pbr_mat("led_white", (1.0, 0.98, 0.92), 0.00, 0.10,
                    emission=((1.0, 0.98, 0.92), 8.0))
for sx in (-1, +1):
    _sphere(f"led_{sx}", 0.012,
              (sx * TANK_W * 0.25, 0, TANK_Z + TANK_H/2 - 0.005), mat_led)

# --- sand substrate ----------------------------------
SAND_H = 0.04
SAND_Z = TANK_Z - TANK_H/2 + T + SAND_H/2 + 0.0005
_box("sand", TANK_W - 2*T - 0.005, TANK_D - 2*T - 0.005, SAND_H,
       (0, 0, SAND_Z), mat_sand)

# --- rocks --------------------------------------------
ROCK_DATA = [
    (-0.32, 0.05, 0.05),
    (-0.28, -0.06, 0.04),
    (0.28, 0.04, 0.05),
    (0.32, -0.08, 0.06),
    (0.0,  0.08, 0.04),
]
for i, (rx, ry, rR) in enumerate(ROCK_DATA):
    _sphere(f"rock_{i}", rR,
              (rx, ry, SAND_Z + SAND_H/2 + rR * 0.6),
              mat_rock, scale=(1.0, 0.9, 0.7))

# --- plants (4 stalks of green leaves) -----------
PLANT_DATA = [
    (-0.25, 0.10, 0.20, mat_plant_a),
    (-0.15, -0.08, 0.18, mat_plant_b),
    (0.20, 0.08, 0.22, mat_plant_a),
    (0.30, -0.05, 0.16, mat_plant_b),
]
for i, (px, py, ph, mat) in enumerate(PLANT_DATA):
    # main stem
    _cyl(f"stem_{i}", 0.006, 0.004, ph, 'Z',
           (px, py, SAND_Z + SAND_H/2 + ph/2), mat)
    # 4 leaves along the stem
    for k in range(4):
        kz = SAND_Z + SAND_H/2 + (k + 0.5) * ph / 4
        ang = k * math.pi/2 + i * 0.5
        ox = math.cos(ang) * 0.018
        oy = math.sin(ang) * 0.018
        _box(f"leaf_{i}_{k}", 0.024, 0.005, 0.045,
               (px + ox, py + oy, kz + 0.01), mat,
               rot=(0, ang * 0.5, 0))

# --- coral cluster (pink + orange) -----------------
CORAL_CENTER = (0.10, 0.12)
# pink branches : 5 small cones
for i in range(5):
    a = i * 2*math.pi/5
    cx = CORAL_CENTER[0] + 0.04 * math.cos(a)
    cy = CORAL_CENTER[1] + 0.04 * math.sin(a)
    h = 0.06 + 0.02 * (i % 3)
    _cyl(f"coral_p_{i}", 0.012, 0.003, h, 'Z',
           (cx, cy, SAND_Z + SAND_H/2 + h/2),
           mat_coral_p, segments=10)
# orange ball on top
_sphere("coral_o_ball", 0.025,
          (CORAL_CENTER[0], CORAL_CENTER[1], SAND_Z + SAND_H/2 + 0.09),
          mat_coral_o, scale=(1.2, 1.0, 0.8))

# --- fish builder -----------------------------------
def add_fish(name, body_mat, body_R=0.030, fin_mat=None):
    """Return (pivot, body_R) for later animation parenting."""
    if fin_mat is None: fin_mat = body_mat
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
    pv = bpy.context.active_object
    pv.name = name
    # body : flattened ellipsoid
    body = _sphere(name + "_body", body_R, (0, 0, 0), body_mat,
                     scale=(1.6, 0.6, 0.8))
    body.parent = pv; body.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # tail fin : a small triangle approximated as a flat box, behind the body
    tail = _box(name + "_tail", body_R * 0.7, 0.003, body_R * 1.1,
                  (-body_R * 1.6, 0, 0), fin_mat)
    tail.parent = pv; tail.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # dorsal fin on top
    top_fin = _box(name + "_top", body_R * 0.7, 0.003, body_R * 0.6,
                     (0, 0, body_R * 0.5), fin_mat,
                     rot=(0, math.radians(-15), 0))
    top_fin.parent = pv; top_fin.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # side fin (single, attached on -Y face to suggest a pectoral)
    side_fin = _box(name + "_side", body_R * 0.5, 0.003, body_R * 0.3,
                      (body_R * 0.2, -body_R * 0.5, -body_R * 0.1), fin_mat,
                      rot=(math.radians(45), 0, 0))
    side_fin.parent = pv; side_fin.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # tiny eye (small dark sphere)
    eye = _sphere(name + "_eye", 0.004,
                    (body_R * 1.2, body_R * 0.25, body_R * 0.18),
                    mat_fish_e if body_mat is not mat_fish_e else mat_coral_o)
    eye.parent = pv; eye.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    return pv

# Define 5 fish + their orbit centers + amplitudes + periods + altitudes
fish_defs = [
    # (name, mat, body_R, x_amp, y_amp, z_off, period, phase, z_amp)
    ("fish_0", mat_fish_a, 0.030, 0.30, 0.10, 0.18, 5.0, 0.0,  0.04),
    ("fish_1", mat_fish_b, 0.027, 0.25, 0.08, 0.10, 6.0, 1.0,  0.05),
    ("fish_2", mat_fish_c, 0.024, 0.20, 0.06, 0.22, 4.5, 2.0,  0.03),
    ("fish_3", mat_fish_d, 0.026, 0.30, 0.09, 0.06, 5.5, 3.0,  0.04),
    ("fish_4", mat_fish_e, 0.022, 0.18, 0.07, 0.14, 7.0, 0.5,  0.05),
]
fish_objs = []
for (name, mat, R, ax, ay, zo, period, phase, az) in fish_defs:
    pv = add_fish(name, mat, body_R=R)
    fish_objs.append((pv, ax, ay, zo, period, phase, az))

# --- bubbles : 3 streams of 4 bubbles each ---------
BUBBLE_STREAMS = [
    (-0.30, -0.08),  # x, y
    (0.18, 0.10),
    (0.32, -0.10),
]
bubbles = []  # (obj, stream_x, stream_y, phase)
for s, (sx, sy) in enumerate(BUBBLE_STREAMS):
    for k in range(4):
        b = _sphere(f"bubble_{s}_{k}", 0.008,
                      (sx, sy, SAND_Z + SAND_H/2 + 0.01),
                      mat_bubble)
        bubbles.append((b, sx, sy, k / 4.0))

# --- animation ------------------------------------
FPS = 30
DURATION = 8.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# Fish swim on elliptical paths, facing direction of motion. Centre of
# each fish path is the tank centre.
center_z = SAND_Z + SAND_H/2 + 0.10
tank_cx, tank_cy = 0.0, 0.0
for (pv, ax, ay, zo, period, phase, az) in fish_objs:
    cycles = DURATION / period
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        a = 2*math.pi * cycles * t + phase
        x = tank_cx + ax * math.cos(a)
        y = tank_cy + ay * math.sin(a)
        z = center_z + zo + az * math.sin(a * 2)
        # heading : tangent vector (-ax*sin, ay*cos)
        dx = -ax * math.sin(a)
        dy =  ay * math.cos(a)
        heading = math.atan2(dy, dx)
        bpy.context.scene.frame_set(f)
        pv.location = (x, y, z)
        pv.rotation_euler = (0, 0, heading)
        pv.keyframe_insert("location", frame=f)
        pv.keyframe_insert("rotation_euler", frame=f)
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Bubbles rise and reset
BUB_BOT = SAND_Z + SAND_H/2 + 0.01
BUB_TOP = TANK_Z + TANK_H/2 - 0.02
for (b, sx, sy, ph) in bubbles:
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        # cycle position : 0..1 with phase offset, wraps via modulo
        local_t = (t * 2 + ph) % 1.0   # 2 rises per loop
        z = BUB_BOT + (BUB_TOP - BUB_BOT) * local_t
        # slight horizontal wobble
        wx = 0.010 * math.sin(2*math.pi * local_t * 4 + ph * 6.28)
        wy = 0.008 * math.cos(2*math.pi * local_t * 4 + ph * 6.28)
        bpy.context.scene.frame_set(f)
        b.location = (sx + wx, sy + wy, z)
        b.keyframe_insert("location", frame=f)
    if b.animation_data and b.animation_data.action:
        for fc in b.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"AQUA_OK: {out_glb}", flush=True)
'''


def make_aquarium(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_aqua_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "AQUA_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_aquarium(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
