"""Procedural skate halfpipe ramp with skateboard (Blender headless).

Wooden plywood halfpipe : flat bottom + 2 quarter-pipes (curved ramps)
+ flat top platforms + metal coping rails on the edges + truck/ledge
graphics. A skateboard rolls back and forth across the pipe, hitting
each side and arcing over the coping in a kickflip-like spin. Animation
: skateboard follows the curve of the pipe, with wheels spinning and
the deck flipping at each apex.

CLI:
  python proc_skate_ramp.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "skateramp.glb"

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

mat_floor   = pbr_mat("floor",     (0.30, 0.25, 0.20), 0.00, 0.85)
mat_ply     = pbr_mat("plywood",   (0.55, 0.38, 0.20), 0.05, 0.55)
mat_ply_d   = pbr_mat("ply_dk",    (0.38, 0.22, 0.12), 0.05, 0.60)
mat_floor_p = pbr_mat("pipe_fl",   (0.45, 0.30, 0.18), 0.05, 0.60)
mat_steel   = pbr_mat("steel",     (0.70, 0.72, 0.75), 0.85, 0.30)
mat_coping  = pbr_mat("coping",    (0.80, 0.82, 0.85), 1.00, 0.25)
mat_deck    = pbr_mat("deck",      (0.18, 0.18, 0.22), 0.10, 0.50)
mat_deck_lt = pbr_mat("deck_lt",   (0.85, 0.18, 0.18), 0.10, 0.40)
mat_truck   = pbr_mat("truck",     (0.55, 0.55, 0.58), 0.80, 0.30)
mat_wheel   = pbr_mat("wheel",     (0.92, 0.92, 0.85), 0.05, 0.30)
mat_dark    = pbr_mat("dark",      (0.06, 0.06, 0.07), 0.30, 0.45)
mat_graf_a  = pbr_mat("graf_a",    (0.92, 0.40, 0.18), 0.05, 0.55)
mat_graf_b  = pbr_mat("graf_b",    (0.18, 0.55, 0.92), 0.05, 0.55)
mat_graf_c  = pbr_mat("graf_c",    (0.95, 0.85, 0.20), 0.05, 0.55)

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=16, rot=None):
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

# Conventions : halfpipe extends along Y (skater rolls in +/-X direction).
# Quarter-pipe walls are on the -X and +X sides. Up = +Z.

# Halfpipe dimensions
RAMP_R = 1.20       # radius of each quarter-pipe
PIPE_W = 2.40       # length along Y (skater's path direction is X, so this is the lateral width)
FLAT_W = 1.20       # flat bottom width (X)
PLAT_W = 0.50       # platform width on top of each side (X direction beyond the curve)

# --- floor / ground around the ramp ---
_box("floor", 5.5, 4.0, 0.04, (0, 0, -0.04), mat_floor)

# --- flat bottom of the halfpipe (a wide wooden floor) ---
_box("pipe_floor", FLAT_W, PIPE_W, 0.04,
       (0, 0, 0.02), mat_floor_p)

# --- 2 quarter-pipe walls (left -X, right +X) -----
# Each quarter-pipe is a curved wooden surface : we approximate it with
# vertical "ribs" arranged along the curve, then we add the deck rails on
# top of the curve.
def build_quarter(sign):
    """sign = -1 (left side) or +1 (right side). The curve goes from the
    flat bottom (at x = sign*FLAT_W/2) UP and OUTWARD to the platform top
    (at x = sign*(FLAT_W/2 + RAMP_R), z = RAMP_R)."""
    N_RIBS = 14   # number of vertical ribs across the Y span of the pipe
    rib_x_center = sign * (FLAT_W/2 + RAMP_R)
    rib_z_center = RAMP_R
    # For each rib (Y position), we build a vertical curtain following the
    # quarter circle. Approach : create a flat curved board per rib, then
    # plywood plank panels filling between ribs (we'll use 8 segment panels
    # along the arc, each a small box).
    N_ARC = 8
    # 8 arc panels per quarter
    for arc_idx in range(N_ARC):
        a0 = (math.pi/2) * arc_idx / N_ARC   # 0..pi/2
        a1 = (math.pi/2) * (arc_idx + 1) / N_ARC
        # midpoint of the arc segment (in local frame where 0,0 is the center of curvature)
        am = (a0 + a1) / 2
        # local (x,z) on the arc (x measured outward from the rib center)
        local_x = -RAMP_R * math.cos(am) * sign  # negative because curve goes inward toward bottom
        local_z = -RAMP_R * math.sin(am)
        # World position
        wx = rib_x_center + local_x
        wz = rib_z_center + local_z
        # the panel is a thin slab tangent to the curve at (wx, wz)
        # its width = arc length of this segment ~= RAMP_R * (a1 - a0)
        panel_w = RAMP_R * (math.pi/2) / N_ARC * 1.05  # slight overlap
        # panel orientation : its local Z (thickness direction) points
        # radially outward from the center of curvature
        # angle of the tangent : am + pi/2, but for placement we just rotate
        # the panel around Y axis by -am * sign (positive for left side)
        rot_y = -am if sign < 0 else am
        # Wait — left side : the arc starts at (x=-FLAT_W/2, z=0) going down
        # toward bottom. Actually a quarter-pipe is concave toward the
        # bottom of the pipe. Let's just place panels at the right (wx, wz)
        # and let Blender do the rotation for tangency.
        panel = _box(f"quarter_{sign}_panel_{arc_idx}",
                       panel_w, PIPE_W * 0.98, 0.025,
                       (wx, 0, wz), mat_ply,
                       rot=(0, rot_y, 0))
    # 2 end caps (left + right along Y) — vertical plywood walls forming the
    # quarter-pipe end profile
    for sy in (-1, +1):
        end_x = rib_x_center
        end_y = sy * PIPE_W / 2
        # approximate the end cap with a tall thin box that hides the open
        # cross-section. Use the radius as height + width = RAMP_R.
        cap = _box(f"quarter_{sign}_cap_{sy}",
                     RAMP_R + 0.10, 0.020, RAMP_R + 0.05,
                     (rib_x_center - sign * (RAMP_R/2 - 0.04), end_y, rib_z_center - RAMP_R/2 + 0.02),
                     mat_ply_d)
    # platform on top (a wooden deck above the curve)
    plat_x = sign * (FLAT_W/2 + RAMP_R + PLAT_W/2)
    plat_z = RAMP_R + 0.022
    _box(f"platform_{sign}", PLAT_W, PIPE_W, 0.04,
           (plat_x, 0, plat_z), mat_ply)
    # 2 support legs for the platform
    for sy in (-1, +1):
        _box(f"plat_leg_{sign}_{sy}", 0.05, 0.05, RAMP_R,
               (plat_x, sy * (PIPE_W/2 - 0.10), RAMP_R/2),
               mat_ply_d)
    # coping rail (chrome pipe along the top edge of the ramp, where
    # the curve meets the platform)
    cop_x = sign * (FLAT_W/2 + RAMP_R)
    cop_z = RAMP_R + 0.022
    _cyl(f"coping_{sign}", 0.020, 0.020, PIPE_W, 'Y',
           (cop_x, 0, cop_z), mat_coping, segments=12)

build_quarter(-1)
build_quarter(+1)

# 4 graffiti tags painted on the flat-pipe walls (2 per side, on the lower
# part of the curve where they'd be visible from above)
for sign, mat, offset_z in (
    (-1, mat_graf_a, 0.35),
    (-1, mat_graf_c, 0.65),
    (+1, mat_graf_b, 0.30),
    (+1, mat_graf_c, 0.55),
):
    # place a thin slab on the surface of the curve at the chosen z
    # solve for x : given z, a = asin(z / RAMP_R), x = FLAT_W/2 + RAMP_R - RAMP_R*cos(a)
    a = math.asin(min(0.99, offset_z / RAMP_R))
    wx = sign * (FLAT_W/2 + RAMP_R - RAMP_R * math.cos(a))
    wz = offset_z
    rot_y = -a if sign < 0 else a
    _box(f"graf_{sign}_{offset_z:.2f}", 0.20, 0.30, 0.003,
           (wx, 0.4 * (1 if sign > 0 else -1), wz),
           mat, rot=(0, rot_y, 0))

# --- skateboard (animated parent empty + 4 wheels + deck + 2 trucks) ---
SK_DECK_L = 0.45
SK_DECK_W = 0.13
SK_DECK_T = 0.014
SK_WHEEL_R = 0.018
SK_WHEEL_OFFSET_X = 0.16
SK_WHEEL_OFFSET_Y = SK_DECK_W * 0.45
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0.10))
sk_pivot = bpy.context.active_object
sk_pivot.name = "skateboard_pivot"
# deck (the wooden plank — slightly curved up at the ends but we'll just
# use a flat slab + 2 angled tips)
deck = _box("sk_deck", SK_DECK_L, SK_DECK_W, SK_DECK_T,
              (0, 0, SK_WHEEL_R + SK_DECK_T/2), mat_deck)
deck.parent = sk_pivot; deck.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 deck tips tilted up (nose + tail)
for sx in (-1, +1):
    tip = _box(f"sk_tip_{sx}", SK_DECK_L * 0.18, SK_DECK_W, SK_DECK_T,
                 (sx * SK_DECK_L * 0.55, 0, SK_WHEEL_R + SK_DECK_T/2 + 0.01),
                 mat_deck_lt, rot=(0, sx * math.radians(20), 0))
    tip.parent = sk_pivot; tip.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 trucks (axles)
for sx in (-1, +1):
    truck = _box(f"sk_truck_{sx}", 0.025, SK_DECK_W + 0.04, 0.012,
                   (sx * SK_WHEEL_OFFSET_X, 0, SK_WHEEL_R + 0.004),
                   mat_truck)
    truck.parent = sk_pivot; truck.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 4 wheels
for sx in (-1, +1):
    for sy in (-1, +1):
        wh = _cyl(f"sk_wheel_{sx}_{sy}", SK_WHEEL_R, SK_WHEEL_R, 0.012, 'Y',
                    (sx * SK_WHEEL_OFFSET_X, sy * SK_WHEEL_OFFSET_Y, SK_WHEEL_R),
                    mat_wheel, segments=12)
        wh.parent = sk_pivot; wh.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : skateboard rolls along the pipe, up the wall, spins, returns ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

def skate_pose(t):
    """t in [0,1]. Returns (x, z, roll_rotation_around_Y) for the skateboard.
    Cycle :
      t=[0.00, 0.25] : roll from x=-FLAT_W/2 to x=+FLAT_W/2 (across flat)
      t=[0.25, 0.40] : up the right quarter-pipe arc
      t=[0.40, 0.55] : peak / spin over the coping + brief air
      t=[0.55, 0.70] : back down the right quarter
      t=[0.70, 0.95] : roll back across the flat to the left
      t=[0.95, 1.00] : settle on the left side
    """
    # We'll use a single phase variable mapping to the position along the
    # pipe + height + skater orientation.
    if t < 0.25:
        u = t / 0.25
        x = -FLAT_W/2 + u * FLAT_W
        z = SK_WHEEL_R + 0.001
        roll = 0
    elif t < 0.40:
        u = (t - 0.25) / 0.15
        # parametric quarter-pipe : angle a from 0 (bottom) to pi/2 (top)
        a = u * math.pi / 2
        x = FLAT_W/2 + RAMP_R - RAMP_R * math.cos(a)
        z = RAMP_R - RAMP_R * math.cos(a)  # rises along the curve... actually no
        # better : z = RAMP_R * sin(a)? but that goes to RAMP_R at apex
        x = FLAT_W/2 + RAMP_R - RAMP_R * math.cos(a)
        z = SK_WHEEL_R + RAMP_R * math.sin(a)
        # the tangent angle to the curve (so the deck is parallel)
        roll = -a
    elif t < 0.55:
        u = (t - 0.40) / 0.15
        # at the top, do a small kickflip-like arc
        x = FLAT_W/2 + RAMP_R + (PLAT_W * 0.3) * math.sin(u * math.pi)
        z = RAMP_R + 0.25 * math.sin(u * math.pi)
        roll = -math.pi/2 + u * 2 * math.pi  # full 360 spin around Y
    elif t < 0.70:
        u = (t - 0.55) / 0.15
        # come back down the right quarter (reverse motion)
        a = (1.0 - u) * math.pi / 2
        x = FLAT_W/2 + RAMP_R - RAMP_R * math.cos(a)
        z = SK_WHEEL_R + RAMP_R * math.sin(a)
        roll = -a
    elif t < 0.95:
        u = (t - 0.70) / 0.25
        # roll back to the left
        x = FLAT_W/2 - u * FLAT_W
        z = SK_WHEEL_R + 0.001
        roll = 0
    else:
        x = -FLAT_W/2
        z = SK_WHEEL_R + 0.001
        roll = 0
    return x, z, roll

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    x, z, roll = skate_pose(t)
    bpy.context.scene.frame_set(f)
    sk_pivot.location = (x, 0, z)
    # heading along +X by default; orient deck along the curve by rolling around Y
    sk_pivot.rotation_euler = (0, roll, 0)
    sk_pivot.keyframe_insert("location", frame=f)
    sk_pivot.keyframe_insert("rotation_euler", frame=f)
if sk_pivot.animation_data and sk_pivot.animation_data.action:
    for fc in sk_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Wheels spin : we add a child rotation to each wheel based on linear speed
# But the trucks are parented to sk_pivot — the wheels' rotation around X
# (their local axle) would normally be in addition to the pivot's rotation.
# Simpler : add a separate rotation_euler animation on each wheel.
wheels = [bpy.data.objects.get(f"sk_wheel_{sx}_{sy}")
            for sx in (-1, +1) for sy in (-1, +1)]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    angle = 2*math.pi * 4 * t  # spin 4 times per loop
    for wh in wheels:
        if wh:
            wh.rotation_euler = (angle, 0, 0)
            wh.keyframe_insert("rotation_euler", frame=f)
for wh in wheels:
    if wh and wh.animation_data and wh.animation_data.action:
        for fc in wh.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"RAMP_OK: {out_glb}", flush=True)
'''


def make_ramp(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_ramp_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "RAMP_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_ramp(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
