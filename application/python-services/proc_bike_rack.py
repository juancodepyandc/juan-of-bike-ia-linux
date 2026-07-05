"""Procedural city bike rack (Blender headless).

Concrete pad + 5 U-shaped steel rails (inverted-U "Sheffield stand") +
3 vintage bicycles parked at 3 of the rails. Each bike has frame + 2
wheels + saddle + handlebar + crankset + chain + pedals + (one) chain
lock. Animation : the middle bike sways gently (slight wind / impact)
and its chain lock vibrates.

CLI:
  python proc_bike_rack.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "bikerack.glb"

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

mat_floor   = pbr_mat("floor",     (0.18, 0.18, 0.20), 0.00, 0.85)
mat_pave    = pbr_mat("pave",      (0.42, 0.40, 0.36), 0.00, 0.85)
mat_steel   = pbr_mat("steel",     (0.65, 0.66, 0.68), 0.85, 0.30)
mat_chrome  = pbr_mat("chrome",    (0.80, 0.82, 0.85), 1.00, 0.18)
mat_dark    = pbr_mat("dark",      (0.08, 0.08, 0.09), 0.40, 0.40)
mat_tire    = pbr_mat("tire",      (0.05, 0.05, 0.06), 0.05, 0.80)
mat_frame_R = pbr_mat("frame_red", (0.65, 0.18, 0.18), 0.15, 0.35)
mat_frame_B = pbr_mat("frame_blu", (0.18, 0.30, 0.65), 0.15, 0.35)
mat_frame_G = pbr_mat("frame_grn", (0.18, 0.45, 0.20), 0.15, 0.35)
mat_saddle  = pbr_mat("saddle",    (0.30, 0.18, 0.10), 0.00, 0.55)
mat_grip    = pbr_mat("grip",      (0.10, 0.10, 0.11), 0.00, 0.65)
mat_chain_y = pbr_mat("chain_yel", (0.92, 0.85, 0.20), 0.10, 0.30)

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

def _sphere(name, R, location, mat, u=10, v=8):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

def make_arc(name, start, end, R, mat, n_segs=8, parent=None):
    """Draw a half-circle arc from start to end with given peak R, lying in the XZ plane (Y axis = bend axis)."""
    p0 = mathutils.Vector(start); p1 = mathutils.Vector(end)
    mid = (p0 + p1) * 0.5
    horiz = p1 - p0
    L = horiz.length
    horiz_n = horiz.normalized()
    up = mathutils.Vector((0, 0, 1))
    perp = up - horiz_n * horiz_n.dot(up)
    perp.normalize()
    # 8 short cylinder segments approximating a semi-circle on the side
    prev = p0
    for i in range(1, n_segs + 1):
        u = i / n_segs
        # position : along the chord + perpendicular offset = R*sin(pi*u)
        a = math.pi * u
        pos = p0 + horiz * u + perp * (R * math.sin(a))
        d = pos - prev
        L_seg = d.length
        if L_seg < 1e-5:
            prev = pos
            continue
        midp = (prev + pos) * 0.5
        seg = _cyl(f"{name}_{i}", 0.012, 0.012, L_seg, 'Z', (0,0,0), mat, segments=8)
        seg.location = midp
        direction = d.normalized()
        seg.rotation_mode = 'QUATERNION'
        seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
        if parent:
            seg.parent = parent
            seg.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        prev = pos

# --- pavement ----------------------
_box("floor", 2.6, 1.8, 0.04, (0, 0, -0.04), mat_floor)
_box("pave_slab", 2.0, 1.0, 0.04, (0, 0, 0.02), mat_pave)

# --- 5 Sheffield U-rails along X axis ---
# Each rail is a steel inverted-U arch ~ 60 cm wide, 70 cm tall.
RAIL_W = 0.60
RAIL_H = 0.70
RAIL_Y = 0
RAIL_SPACING = 0.40
N_RAILS = 5
rail_xs = []
for k in range(N_RAILS):
    rx = (k - (N_RAILS - 1)/2) * RAIL_SPACING
    rail_xs.append(rx)
    # 2 vertical posts (small steel cylinders going down to a base foot)
    for sy in (-1, +1):
        py = sy * RAIL_W/2 * 0.18  # narrow rail (along Y is the front-back depth)
        # wait : Sheffield stands run perpendicular to bikes. Bikes lean
        # against them across Y. So the rail itself is in the XZ plane,
        # extending in X is wrong — let me re-orient : rail extends in Y
        # (front-back), bikes park along it lengthwise. We'll re-define :
        # rail is the U shape lying in the YZ plane, extending in Y.
        pass
    # Implementation : rail is a U in YZ plane. 2 vertical posts at
    # (rx, -RAIL_W/2, 0..RAIL_H) and (rx, +RAIL_W/2, 0..RAIL_H), connected
    # by a horizontal top at z=RAIL_H.
    for sy in (-1, +1):
        # foot anchor (small flat plate)
        _box(f"rail_{k}_foot_{sy}", 0.04, 0.06, 0.012,
               (rx, sy * RAIL_W/2, 0.04 + 0.006), mat_steel)
        # vertical post
        _cyl(f"rail_{k}_post_{sy}", 0.020, 0.020, RAIL_H, 'Z',
               (rx, sy * RAIL_W/2, 0.04 + 0.012 + RAIL_H/2), mat_steel)
    # top horizontal bar
    _cyl(f"rail_{k}_top", 0.020, 0.020, RAIL_W, 'Y',
           (rx, 0, 0.04 + 0.012 + RAIL_H), mat_steel)
    # rounded corners (small spheres at each corner to suggest welded curves)
    for sy in (-1, +1):
        _sphere(f"rail_{k}_corner_{sy}", 0.022,
                  (rx, sy * RAIL_W/2, 0.04 + 0.012 + RAIL_H), mat_steel)

# --- 3 bikes parked at rails 0, 2, 4 (skipping 1 and 3) ---
def make_bike(name, x_at_rail, frame_color, rotate_z=0, parent_to=None):
    """Build a bike leaning against a Sheffield rail centered at x_at_rail.
    The bike is constructed in its local frame oriented along Y (forward),
    then rotated by rotate_z around Z. The whole bike is parented to a
    pivot empty at the rail position so we can sway one of them."""
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(x_at_rail, 0, 0))
    bike = bpy.context.active_object
    bike.name = name + "_pivot"
    if parent_to:
        bike.parent = parent_to
    bike.rotation_euler = (0, 0, rotate_z)

    # Wheels : 2 thin tori (approximated with thin cylinders)
    WHEEL_R = 0.30
    WHEEL_Y_F = +0.55  # front wheel +Y
    WHEEL_Y_B = -0.55  # back wheel
    GROUND_Z = WHEEL_R + 0.04
    for wy, label in ((WHEEL_Y_F, "front"), (WHEEL_Y_B, "back")):
        # tire (a thin disc with X-axis horizontal)
        tire = _cyl(f"{name}_tire_{label}", WHEEL_R, WHEEL_R, 0.04, 'X',
                      (0, wy, GROUND_Z), mat_tire, segments=20)
        tire.parent = bike; tire.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        # rim (inside, slightly smaller)
        rim = _cyl(f"{name}_rim_{label}", WHEEL_R * 0.85, WHEEL_R * 0.85, 0.022, 'X',
                     (0, wy, GROUND_Z), mat_chrome, segments=18)
        rim.parent = bike; rim.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        # 6 spokes
        for s in range(6):
            ang = s * math.pi / 6
            sp = _box(f"{name}_spoke_{label}_{s}", 0.002, WHEEL_R * 1.7, 0.002,
                        (0, wy, GROUND_Z), mat_chrome, rot=(ang, 0, 0))
            sp.parent = bike; sp.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        # hub
        _sphere(f"{name}_hub_{label}", 0.020, (0, wy, GROUND_Z), mat_chrome)

    # frame triangle : top tube + down tube + seat tube + head tube
    BB_Y = 0.0; BB_Z = GROUND_Z + 0.05  # bottom-bracket
    HEAD_Y = WHEEL_Y_F * 0.55; HEAD_Z = GROUND_Z + 0.55  # head tube top
    SEAT_Y = WHEEL_Y_B * 0.55; SEAT_Z = GROUND_Z + 0.60  # seat tube top
    # down tube (BB -> HEAD)
    def tube(name_t, p0, p1, R=0.012, mat=frame_color):
        d = mathutils.Vector(p1) - mathutils.Vector(p0)
        L = d.length
        mid = (mathutils.Vector(p0) + mathutils.Vector(p1)) * 0.5
        seg = _cyl(name_t, R, R, L, 'Z', (0,0,0), mat, segments=10)
        seg.location = mid
        direction = d.normalized()
        seg.rotation_mode = 'QUATERNION'
        seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
        seg.parent = bike; seg.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        return seg

    tube(f"{name}_dt",   (0, BB_Y, BB_Z), (0, HEAD_Y, HEAD_Z))
    tube(f"{name}_st",   (0, BB_Y, BB_Z), (0, SEAT_Y, SEAT_Z))
    tube(f"{name}_tt",   (0, HEAD_Y, HEAD_Z), (0, SEAT_Y, SEAT_Z))
    # chainstays + seatstays
    tube(f"{name}_cs1",  (0, BB_Y, BB_Z), (0, WHEEL_Y_B, GROUND_Z), R=0.008)
    tube(f"{name}_ss1",  (0, SEAT_Y, SEAT_Z), (0, WHEEL_Y_B, GROUND_Z), R=0.008)
    # fork (HEAD -> front wheel hub)
    tube(f"{name}_fork", (0, HEAD_Y, HEAD_Z), (0, WHEEL_Y_F, GROUND_Z), R=0.010)
    # head tube post above (steerer for handlebar)
    tube(f"{name}_stem", (0, HEAD_Y, HEAD_Z), (0, HEAD_Y, HEAD_Z + 0.12), R=0.012, mat=mat_dark)
    # handlebar
    hb = _cyl(f"{name}_handlebar", 0.012, 0.012, 0.42, 'X',
                (0, HEAD_Y, HEAD_Z + 0.12), mat_dark)
    hb.parent = bike; hb.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # grips (2 short cylinders at handle ends)
    for sx in (-1, +1):
        gp = _cyl(f"{name}_grip_{sx}", 0.014, 0.014, 0.10, 'X',
                    (sx * 0.21, HEAD_Y, HEAD_Z + 0.12), mat_grip, segments=10)
        gp.parent = bike; gp.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # seat post + saddle
    tube(f"{name}_seatpost", (0, SEAT_Y, SEAT_Z), (0, SEAT_Y, SEAT_Z + 0.10), R=0.010, mat=mat_dark)
    saddle = _box(f"{name}_saddle", 0.07, 0.20, 0.025,
                    (0, SEAT_Y, SEAT_Z + 0.12), mat_saddle)
    saddle.parent = bike; saddle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # crankset + 2 pedals
    cr = _cyl(f"{name}_crank", 0.025, 0.025, 0.012, 'X', (0, BB_Y, BB_Z), mat_chrome, segments=14)
    cr.parent = bike; cr.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # crank arms (left + right at opposite angles)
    for sx, ang in ((-1, 0), (+1, math.pi)):
        ca = _box(f"{name}_crankarm_{sx}",
                    0.005, 0.012, 0.14,
                    (sx * 0.05, BB_Y + 0.06 * math.cos(ang), BB_Z + 0.06 * math.sin(ang)),
                    mat_dark, rot=(ang, 0, 0))
        ca.parent = bike; ca.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        # pedal at the end of each arm
        pe = _box(f"{name}_pedal_{sx}", 0.040, 0.030, 0.008,
                    (sx * 0.07, BB_Y + 0.12 * math.cos(ang), BB_Z + 0.12 * math.sin(ang)),
                    mat_dark)
        pe.parent = bike; pe.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # chain : a short dark band from crank to rear hub (visual hint)
    tube(f"{name}_chain", (0, BB_Y + 0.05, BB_Z), (0, WHEEL_Y_B + 0.05, GROUND_Z), R=0.005, mat=mat_dark)

    return bike

# place 3 bikes : at rails 0, 2, 4. Each bike rotated 90° around Z (frame
# along Y is what we built; we want it leaning along the rail which runs
# along Y, so no rotation needed - bikes go along +Y direction).
# But to make them lean against the rails, we tilt them slightly.

# Bike L at rail 0 (left-most)
bike_L = make_bike("bike_L", rail_xs[0], mat_frame_R, rotate_z=0)
bike_L.rotation_euler = (math.radians(-6), 0, 0)  # tilt toward rail (+Y)
bike_L.location = (rail_xs[0], -0.05, 0)

# Bike M at rail 2 (middle, the one we animate)
bike_M_root = make_bike("bike_M", rail_xs[2], mat_frame_B, rotate_z=0)
bike_M_root.rotation_euler = (math.radians(-5), 0, 0)
bike_M_root.location = (rail_xs[2], -0.05, 0)

# Bike R at rail 4
bike_R = make_bike("bike_R", rail_xs[4], mat_frame_G, rotate_z=0)
bike_R.rotation_euler = (math.radians(-7), 0, 0)
bike_R.location = (rail_xs[4], -0.05, 0)

# --- chain lock (yellow chain wrapped around middle bike + rail) ---
# We'll just draw a chain bend approximated by 5 short yellow cyl segments
# around the front wheel hub, parented to bike_M_root so it sways with the bike.
LOCK_POINTS = [
    (-0.05,  0.55, 0.40),
    (-0.10,  0.45, 0.30),
    (-0.12,  0.35, 0.22),
    (-0.10,  0.25, 0.18),
    (-0.05,  0.12, 0.20),
    ( 0.05,  0.00, 0.30),
]
for i in range(len(LOCK_POINTS) - 1):
    p0 = mathutils.Vector(LOCK_POINTS[i])
    p1 = mathutils.Vector(LOCK_POINTS[i+1])
    d = p1 - p0
    L = d.length
    midp = (p0 + p1) * 0.5
    seg = _cyl(f"lock_seg_{i}", 0.010, 0.010, L, 'Z', (0,0,0), mat_chain_y, segments=8)
    seg.location = midp
    direction = d.normalized()
    seg.rotation_mode = 'QUATERNION'
    seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
    seg.parent = bike_M_root
    seg.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# chain lock padlock body
lock_body = _box("lock_body", 0.025, 0.018, 0.030, LOCK_POINTS[-1], mat_chrome)
lock_body.parent = bike_M_root
lock_body.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ------------------
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Middle bike sways : rotation about Y axis (left-right rocking), small range
HOME_ROT = (math.radians(-5), 0, 0)
home_loc = bike_M_root.location.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    sway_y = math.radians(3.0) * math.sin(2*math.pi*t * 1.2)
    bike_M_root.rotation_euler = (HOME_ROT[0], sway_y, 0)
    # small vertical bob too
    bike_M_root.location = (home_loc.x,
                              home_loc.y,
                              home_loc.z + 0.005 * math.sin(2*math.pi*t * 2.4))
    bike_M_root.keyframe_insert("rotation_euler", frame=f)
    bike_M_root.keyframe_insert("location", frame=f)
if bike_M_root.animation_data and bike_M_root.animation_data.action:
    for fc in bike_M_root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"RACK_OK: {out_glb}", flush=True)
'''


def make_rack(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_rack_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "RACK_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_rack(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
