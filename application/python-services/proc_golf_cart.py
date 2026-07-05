"""Procedural golf cart (Blender headless).

White chassis with curved nose + 4 black wheels + 2-seat bench (cushioned)
+ steering wheel + 4 corner posts holding a white canopy roof + dash
panel with small gauges + golf bag with 5 club heads protruding behind.
Animation : 4 wheels spin + steering wheel rotates back-and-forth slightly.

CLI:
  python proc_golf_cart.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "golfcart.glb"

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

mat_floor    = pbr_mat("floor",     (0.20, 0.40, 0.18), 0.00, 0.85)
mat_white    = pbr_mat("white",     (0.95, 0.95, 0.92), 0.20, 0.30)
mat_chrome   = pbr_mat("chrome",    (0.80, 0.82, 0.85), 1.00, 0.18)
mat_dark     = pbr_mat("dark",      (0.06, 0.06, 0.07), 0.30, 0.40)
mat_tire     = pbr_mat("tire",      (0.05, 0.05, 0.06), 0.05, 0.80)
mat_seat     = pbr_mat("seat",      (0.55, 0.42, 0.30), 0.05, 0.55)
mat_seat_bk  = pbr_mat("seat_back", (0.42, 0.30, 0.20), 0.05, 0.60)
mat_steer    = pbr_mat("steer",     (0.10, 0.10, 0.12), 0.20, 0.40)
mat_glass    = pbr_mat("glass",     (0.85, 0.95, 0.92), 0.00, 0.10)
mat_bag      = pbr_mat("bag",       (0.18, 0.18, 0.30), 0.10, 0.55)
mat_bag_t    = pbr_mat("bag_trim",  (0.85, 0.85, 0.20), 0.10, 0.45)
mat_club_h   = pbr_mat("club_head", (0.55, 0.55, 0.58), 0.85, 0.30)
mat_club_g   = pbr_mat("club_grip", (0.10, 0.10, 0.11), 0.05, 0.65)
mat_gauge    = pbr_mat("gauge",     (0.92, 0.92, 0.85), 0.00, 0.40)

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

def _sphere(name, R, location, mat, u=14, v=10):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# Conventions : cart along Y, front at -Y. Up = +Z.

# --- ground ---
_box("floor", 3.0, 4.0, 0.04, (0, 0, -0.04), mat_floor)

# Cart dims
BODY_W = 0.90
BODY_D = 1.80
WHEEL_R = 0.14
WHEEL_OFFSET_X = BODY_W/2 - 0.05
WHEEL_OFFSET_Y_F = -BODY_D * 0.30
WHEEL_OFFSET_Y_R = +BODY_D * 0.30
CHASSIS_Z = WHEEL_R + 0.03

# --- 4 wheels ---
wheels = []
for sx in (-1, +1):
    for sy_label, sy_val in (("F", WHEEL_OFFSET_Y_F), ("R", WHEEL_OFFSET_Y_R)):
        wh = _cyl(f"wheel_{sx}_{sy_label}", WHEEL_R, WHEEL_R, 0.10, 'X',
                    (sx * WHEEL_OFFSET_X, sy_val, WHEEL_R), mat_tire, segments=16)
        wheels.append(wh)
        # chrome hub (small disc)
        _cyl(f"hub_{sx}_{sy_label}", WHEEL_R * 0.55, WHEEL_R * 0.55, 0.012, 'X',
               (sx * (WHEEL_OFFSET_X + 0.052), sy_val, WHEEL_R),
               mat_chrome, segments=12)

# --- main chassis ---
# bottom plate
_box("chassis_plate", BODY_W, BODY_D - 0.20, 0.04,
       (0, 0, CHASSIS_Z), mat_white)
# rear cargo box / battery area
_box("rear_box", BODY_W * 0.92, 0.45, 0.18,
       (0, BODY_D/2 - 0.30, CHASSIS_Z + 0.11), mat_white)
# curved front (nose + hood) — approximated as 2 stepped boxes
_box("nose_low", BODY_W * 0.92, 0.30, 0.10,
       (0, -BODY_D/2 + 0.20, CHASSIS_Z + 0.07), mat_white)
_box("nose_top", BODY_W * 0.82, 0.40, 0.10,
       (0, -BODY_D/2 + 0.40, CHASSIS_Z + 0.16), mat_white)
# rounded windshield (a tall thin slab tilted forward)
_box("windshield", BODY_W * 0.85, 0.020, 0.45,
       (0, -BODY_D * 0.10, CHASSIS_Z + 0.45), mat_glass,
       rot=(math.radians(-12), 0, 0))

# --- 2-seat bench cushion + seatback ---
SEAT_Y = 0.05
SEAT_Z = CHASSIS_Z + 0.18
_box("seat_cushion", BODY_W * 0.88, 0.35, 0.08,
       (0, SEAT_Y, SEAT_Z), mat_seat)
# divider (small ridge in the middle of the cushion)
_box("seat_divider", 0.020, 0.35, 0.10,
       (0, SEAT_Y, SEAT_Z + 0.05), mat_seat_bk)
# seatback (vertical)
_box("seat_back", BODY_W * 0.88, 0.10, 0.42,
       (0, SEAT_Y + 0.20, SEAT_Z + 0.20), mat_seat,
       rot=(math.radians(-5), 0, 0))

# --- steering wheel + column on the left side ---
COLUMN_X = -BODY_W * 0.20
COLUMN_Y = -BODY_D * 0.15
COLUMN_Z = CHASSIS_Z + 0.30
# column shaft
_cyl("steer_column", 0.020, 0.020, 0.35, 'Z',
       (COLUMN_X, COLUMN_Y, COLUMN_Z + 0.175), mat_chrome, segments=10)
# steering wheel (a thin torus-ish ring) — approximated by a flat thick cyl
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(COLUMN_X, COLUMN_Y, COLUMN_Z + 0.40))
steer_pivot = bpy.context.active_object
steer_pivot.name = "steer_pivot"
ring = _cyl("steer_ring", 0.10, 0.10, 0.020, 'Z',
              (0, 0, 0), mat_steer, segments=20)
ring.parent = steer_pivot
ring.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 3 spokes
for i in range(3):
    ang = i * 2*math.pi/3
    sp = _box(f"steer_spoke_{i}", 0.18, 0.020, 0.008,
                (0, 0, 0), mat_steer,
                rot=(0, 0, ang))
    sp.parent = steer_pivot
    sp.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# central hub
hub_sw = _cyl("steer_hub", 0.025, 0.025, 0.020, 'Z',
                (0, 0, 0), mat_chrome, segments=10)
hub_sw.parent = steer_pivot
hub_sw.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- dashboard panel with 2 small gauges ---
DASH_Y = -BODY_D * 0.05
_box("dash_panel", BODY_W * 0.80, 0.10, 0.04,
       (0, DASH_Y, CHASSIS_Z + 0.30), mat_white)
# 2 round gauges
for sx in (-1, +1):
    _cyl(f"gauge_{sx}", 0.025, 0.025, 0.008, 'Y',
           (sx * 0.10, DASH_Y - 0.05, CHASSIS_Z + 0.30), mat_chrome, segments=14)
    _cyl(f"gauge_face_{sx}", 0.020, 0.020, 0.002, 'Y',
           (sx * 0.10, DASH_Y - 0.058, CHASSIS_Z + 0.30), mat_gauge, segments=14)

# --- canopy roof (white) + 4 posts ---
ROOF_Z = CHASSIS_Z + 1.10
# 4 corner posts
for sx in (-1, +1):
    for sy_val in (-BODY_D * 0.20, +BODY_D * 0.35):
        _cyl(f"roof_post_{sx}_{sy_val:.2f}", 0.020, 0.020, ROOF_Z - SEAT_Z - 0.20, 'Z',
               (sx * (BODY_W/2 - 0.04), sy_val,
                (ROOF_Z + SEAT_Z + 0.20) / 2),
               mat_white, segments=10)
# roof slab
_box("roof", BODY_W * 1.05, BODY_D * 0.70, 0.04,
       (0, BODY_D * 0.075, ROOF_Z), mat_white)
# roof edge trim (lighter underside hint)
_box("roof_underside", BODY_W * 1.00, BODY_D * 0.66, 0.002,
       (0, BODY_D * 0.075, ROOF_Z - 0.022), mat_chrome)

# --- golf bag behind the rear box ---
BAG_X = +0.10
BAG_Y = BODY_D/2 + 0.08
BAG_Z = CHASSIS_Z + 0.10
BAG_H = 0.50
BAG_R = 0.10
# bag body
_cyl("bag_body", BAG_R, BAG_R * 0.90, BAG_H, 'Z',
       (BAG_X, BAG_Y, BAG_Z + BAG_H/2), mat_bag, segments=18)
# bag trim band yellow
_cyl("bag_trim", BAG_R * 1.05, BAG_R * 1.05, 0.020, 'Z',
       (BAG_X, BAG_Y, BAG_Z + BAG_H * 0.85), mat_bag_t, segments=18)
# 5 club shafts + heads protruding from the top
CLUBS_TOP_Z = BAG_Z + BAG_H
for k in range(5):
    a = k * 2*math.pi/5 + 0.5
    sx_off = 0.04 * math.cos(a)
    sy_off = 0.04 * math.sin(a)
    # shaft (long thin chrome cylinder going up)
    shaft = _cyl(f"club_shaft_{k}", 0.005, 0.005, 0.40, 'Z',
                   (BAG_X + sx_off, BAG_Y + sy_off, CLUBS_TOP_Z + 0.20),
                   mat_chrome, segments=8)
    # grip (small dark cap on top)
    _cyl(f"club_grip_{k}", 0.010, 0.010, 0.06, 'Z',
           (BAG_X + sx_off, BAG_Y + sy_off, CLUBS_TOP_Z + 0.43),
           mat_club_g, segments=10)
    # head (offset, small)
    _box(f"club_head_{k}", 0.025, 0.040, 0.025,
           (BAG_X + sx_off, BAG_Y + sy_off - 0.020, CLUBS_TOP_Z - 0.005),
           mat_club_h)

# --- headlights (2 small chrome circles on the nose) ---
for sx in (-1, +1):
    _cyl(f"headlight_{sx}", 0.030, 0.030, 0.008, 'Y',
           (sx * BODY_W * 0.30, -BODY_D/2 + 0.18, CHASSIS_Z + 0.16),
           mat_chrome, segments=14)
    _cyl(f"headlight_face_{sx}", 0.025, 0.025, 0.002, 'Y',
           (sx * BODY_W * 0.30, -BODY_D/2 + 0.172, CHASSIS_Z + 0.16),
           mat_gauge, segments=14)

# --- animation ---
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Wheels spin at constant rate (2 turns per loop)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    angle = 2*math.pi * 2 * t
    for wh in wheels:
        wh.rotation_euler = (angle, 0, 0)
        wh.keyframe_insert("rotation_euler", frame=f)
for wh in wheels:
    if wh.animation_data and wh.animation_data.action:
        for fc in wh.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Steering wheel : oscillates ±20° around Z
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    angle = math.radians(20) * math.sin(2*math.pi*t * 1.5)
    steer_pivot.rotation_euler = (0, 0, angle)
    steer_pivot.keyframe_insert("rotation_euler", frame=f)
if steer_pivot.animation_data and steer_pivot.animation_data.action:
    for fc in steer_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"GOLFC_OK: {out_glb}", flush=True)
'''


def make_golfcart(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_gc_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "GOLFC_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_golfcart(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
