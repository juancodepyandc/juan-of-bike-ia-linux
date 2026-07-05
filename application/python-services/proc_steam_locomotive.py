"""Procedural steam locomotive (Blender headless).

Cylindrical boiler + cab + smokestack + 6 wheels with connecting rods
that oscillate as the wheels turn. Animation : wheels rotate, rods
follow the rod-mount circle on each wheel (staying horizontal so they
oscillate together), and a steam puff sphere rises + scales above the
smokestack.

CLI:
  python proc_steam_locomotive.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "loco.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough, emission=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if emission is not None and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission[0], 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission[1]
    return m

mat_boiler  = pbr_mat("boiler_green", (0.10, 0.25, 0.15), 0.30, 0.45)
mat_cab     = pbr_mat("cab_red",      (0.55, 0.10, 0.10), 0.20, 0.45)
mat_iron    = pbr_mat("iron_dark",    (0.15, 0.15, 0.17), 0.90, 0.45)
mat_wheel   = pbr_mat("wheel_black",  (0.10, 0.10, 0.12), 0.20, 0.50)
mat_red_rim = pbr_mat("wheel_red_rim",(0.78, 0.10, 0.10), 0.20, 0.40)
mat_brass   = pbr_mat("brass",        (0.86, 0.62, 0.20), 1.00, 0.28)
mat_track   = pbr_mat("track_gravel", (0.30, 0.30, 0.30), 0.00, 0.90)
mat_steam   = pbr_mat("steam",        (0.95, 0.95, 0.96), 0.00, 0.90,
                       emission=((0.95, 0.95, 0.96), 0.5))

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

def _cyl(name, R1, R2, depth, axis, location, mat, segments=32):
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

# --- ground / track ----------------------------------------------------
_box("ground", 4.5, 1.6, 0.04, (0, 0, -0.06), mat_track)
# 2 rails (long thin red iron strips)
for sy in (-1, 1):
    _box(f"rail_{sy}", 4.5, 0.025, 0.02, (0, sy * 0.38, -0.020), mat_iron)
# sleepers (8 evenly spaced)
for k in range(-3, 4):
    _box(f"sleeper_{k}", 0.12, 0.95, 0.025, (k * 0.55, 0, -0.045), mat_iron)

# --- main loco chassis frame ------------------------------------------
frame = _box("frame", 1.80, 0.55, 0.06, (0, 0, 0.10), mat_iron)

# --- 6 wheels (3 per side) -- only the 2 large drive wheels get rods --
DRIVE_R = 0.18
SMALL_R = 0.12
# wheel positions (X, Y, Z is determined by radius)
WHEELS = [
    # (x, y_side, R, label)
    (-0.65, -0.32, SMALL_R, "rear_L"),
    (-0.65,  0.32, SMALL_R, "rear_R"),
    ( 0.00, -0.32, DRIVE_R, "drive_L"),
    ( 0.00,  0.32, DRIVE_R, "drive_R"),
    ( 0.65, -0.32, DRIVE_R, "drive2_L"),
    ( 0.65,  0.32, DRIVE_R, "drive2_R"),
]
ROD_OFFSET = 0.10   # distance from wheel centre to rod-mount on the drive wheels
wheel_pivots = []   # only the drive-wheels' pivots are returned for rod-tracking

for (wx, wy, R, lbl) in WHEELS:
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(wx, wy, R))
    pv = bpy.context.active_object
    pv.name = f"wheel_pivot_{lbl}"

    # tyre (cylinder along Y) + red rim ring
    tyre = _cyl(f"tyre_{lbl}", R, R, 0.06, 'Y', (0, 0, 0), mat_wheel)
    tyre.parent = pv
    tyre.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    rim = _cyl(f"rim_{lbl}", R * 0.62, R * 0.62, 0.065, 'Y', (0, 0, 0), mat_red_rim)
    rim.parent = pv
    rim.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    # rod-mount peg : a small brass cylinder protruding outward along +Y,
    # offset by ROD_OFFSET from the centre (only on drive wheels)
    if R > 0.15 and wy > 0:
        peg = _cyl(f"rod_peg_{lbl}", 0.018, 0.018, 0.05, 'Y',
                     (ROD_OFFSET, 0.04, 0), mat_brass)
        peg.parent = pv
        peg.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        wheel_pivots.append((pv, lbl, wx, wy))
    elif R > 0.15 and wy < 0:
        peg = _cyl(f"rod_peg_{lbl}", 0.018, 0.018, 0.05, 'Y',
                     (ROD_OFFSET, -0.04, 0), mat_brass)
        peg.parent = pv
        peg.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- connecting rods (1 per side, links the 2 drive wheels) -----------
# The rod stays parallel to itself. As wheels rotate, the rod's centre
# follows the same circle the rod-peg traces on each wheel.
# We use 2 separate rod objects (one per side), animated together.

# Drive wheels are at world X = 0 and 0.65 ; rod connects their peg points
rod_R = math.hypot(ROD_OFFSET, 0)  # 0.10
rod_length = 0.65 - 0.0 + 0.06     # distance between drive wheel centres + extra

rods = []
for side in (-1, 1):
    rod_y = side * 0.36  # outside the wheels
    # rod is a thin box along X, length 0.71
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.325, rod_y, 0.18))
    rod = bpy.context.active_object
    rod.name = f"connecting_rod_{side}"
    rod.scale = (rod_length, 0.025, 0.025)
    bpy.ops.object.transform_apply(scale=True)
    rod.data.materials.append(mat_brass)
    rods.append((rod, side))

# --- boiler (horizontal cylinder along X) -----------------------------
BOILER_R = 0.28
boiler = _cyl("boiler", BOILER_R, BOILER_R, 1.30, 'X', (0.10, 0, 0.45), mat_boiler)
# nose dome at the front
front_dome = _cyl("front_dome", BOILER_R, BOILER_R, 0.10, 'X',
                    (0.85, 0, 0.45), mat_iron)
front_dome2 = _cyl("front_dome2", BOILER_R * 1.05, BOILER_R * 1.05, 0.04, 'X',
                     (0.92, 0, 0.45), mat_iron)
# headlamp on the front
lamp = _cyl("headlamp", 0.05, 0.05, 0.08, 'X', (0.96, 0, 0.45), mat_brass)

# --- smokestack ------------------------------------------------------
stack = _cyl("smokestack_lower", 0.07, 0.07, 0.16, 'Z',
               (0.45, 0, 0.45 + BOILER_R + 0.08), mat_iron)
stack_top = _cyl("smokestack_top", 0.10, 0.08, 0.04, 'Z',
                   (0.45, 0, 0.45 + BOILER_R + 0.18), mat_iron)

# steam dome / sand dome
dome = _cyl("steam_dome", 0.10, 0.10, 0.08, 'Z',
              (0.10, 0, 0.45 + BOILER_R + 0.04), mat_brass)

# --- cab (at the back) -----------------------------------------------
cab_body = _box("cab", 0.40, 0.50, 0.45, (-0.60, 0, 0.45 + BOILER_R - 0.05), mat_cab)
cab_roof = _box("cab_roof", 0.45, 0.55, 0.04,
                  (-0.60, 0, 0.45 + BOILER_R + 0.20), mat_iron)
# cab window holes : just add 2 small dark boxes on the cab sides (visual cue)
for sy in (-1, 1):
    _box(f"cab_window_{sy}", 0.02, 0.18, 0.16,
           (-0.60, sy * 0.25, 0.45 + BOILER_R + 0.05), mat_iron)

# --- steam puff (small emissive sphere above the stack) --------------
mesh_steam = bpy.data.meshes.new("steam_puff")
steam = bpy.data.objects.new("steam_puff", mesh_steam)
bpy.context.collection.objects.link(steam)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=0.12)
bm.to_mesh(mesh_steam); bm.free()
steam.data.materials.append(mat_steam)
steam.location = (0.45, 0, 0.45 + BOILER_R + 0.30)

# --- animation -------------------------------------------------------
FPS = 30
DURATION = 3.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Find all wheel pivots created earlier
all_wheel_pivots = [obj for obj in bpy.data.objects if obj.name.startswith("wheel_pivot_")]

# Wheels rotate around Y (axle direction) ; 3 turns per loop
for pv in all_wheel_pivots:
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        pv.rotation_euler = (0, -3 * 2 * math.pi * t, 0)  # negative -> rolling forward (+X)
        pv.keyframe_insert("rotation_euler", frame=f)
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Connecting rods : track the rod-mount-peg circle on the wheel
# As the wheel rotates by theta, the peg at (ROD_OFFSET, 0) on the wheel moves
# to (ROD_OFFSET*cos(theta), 0, ROD_OFFSET*sin(theta)) RELATIVE TO WHEEL CENTRE.
# We want the rod's centre to track this offset (the rod stays parallel to X).
# The wheel centre is at world (0.325, side*0.32, DRIVE_R = 0.18).
# Rod centre = (0.325, side*0.36, 0.18) + (ROD_OFFSET*cos, 0, ROD_OFFSET*sin)
# where theta = -3*2*pi*t (same as the wheel)

DRIVE_CENTRE_X = 0.325
DRIVE_CENTRE_Z = DRIVE_R  # 0.18
for rod, side in rods:
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        theta = -3 * 2 * math.pi * t
        rod_x = DRIVE_CENTRE_X + ROD_OFFSET * math.cos(theta)
        rod_z = DRIVE_CENTRE_Z + ROD_OFFSET * math.sin(theta)
        rod_y = side * 0.36
        bpy.context.scene.frame_set(f)
        rod.location = (rod_x, rod_y, rod_z)
        rod.keyframe_insert("location", frame=f)
    if rod.animation_data and rod.animation_data.action:
        for fc in rod.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Steam puff : rises + scales up + fades (we approximate fade with scale - it
# will visibly grow then snap back).  Use scale + location keyframes only.
STACK_X = 0.45
STACK_Z = 0.45 + BOILER_R + 0.36
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    # cyclic 0 -> 1 -> 0 over the loop
    cycle = (t * 2) % 1.0   # 2 puffs per loop
    bpy.context.scene.frame_set(f)
    steam.location = (STACK_X, 0, STACK_Z + cycle * 0.45)
    s = 0.3 + cycle * 1.4
    steam.scale = (s, s, s)
    steam.keyframe_insert("location", frame=f)
    steam.keyframe_insert("scale", frame=f)
if steam.animation_data and steam.animation_data.action:
    for fc in steam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"LOCO_OK: {out_glb}", flush=True)
'''


def make_loco(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_loco_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "LOCO_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_loco(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
