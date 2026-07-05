"""Procedural pool / billiards table (Blender headless).

Wooden frame + green felt slate + 4 carved legs + 6 corner / side pockets
+ leather cushion rails + 15 numbered colored balls in a triangular rack
+ a cue ball + 2 wooden cues laid on the table + a triangle rack frame.
Animation : cue ball rolls toward the rack along +Y, lightly nudges the
rack as it arrives. Balls in the rack jiggle subtly on impact.

CLI:
  python proc_billiard_table.py <output_glb>
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
import bpy, bmesh, math, mathutils, sys, random

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "billiard.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0xB1110)

def pbr_mat(name, color, metal, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
    return m

mat_floor   = pbr_mat("floor",      (0.10, 0.10, 0.12), 0.00, 0.85)
mat_wood    = pbr_mat("wood",       (0.18, 0.08, 0.04), 0.05, 0.50)
mat_wood_lt = pbr_mat("wood_lt",    (0.32, 0.16, 0.06), 0.05, 0.45)
mat_felt    = pbr_mat("felt",       (0.10, 0.45, 0.18), 0.00, 0.85)
mat_rail    = pbr_mat("leather",    (0.20, 0.08, 0.04), 0.00, 0.65)
mat_pocket  = pbr_mat("pocket",     (0.04, 0.04, 0.04), 0.00, 0.90)
mat_brass   = pbr_mat("brass",      (0.92, 0.72, 0.25), 1.00, 0.20)
mat_chrome  = pbr_mat("chrome",     (0.78, 0.80, 0.83), 1.00, 0.18)
mat_white   = pbr_mat("ball_white", (0.95, 0.92, 0.88), 0.05, 0.20)
mat_black   = pbr_mat("ball_black", (0.05, 0.05, 0.05), 0.05, 0.20)
mat_band    = pbr_mat("ball_band",  (0.92, 0.90, 0.85), 0.05, 0.20)

# Pool ball colours (1..15)
BALL_COLOURS = [
    (0.95, 0.85, 0.10),   # 1 yellow
    (0.10, 0.20, 0.85),   # 2 blue
    (0.92, 0.18, 0.10),   # 3 red
    (0.45, 0.10, 0.65),   # 4 purple
    (0.95, 0.50, 0.10),   # 5 orange
    (0.10, 0.45, 0.20),   # 6 green
    (0.55, 0.18, 0.10),   # 7 maroon
    (0.05, 0.05, 0.05),   # 8 black
    (0.95, 0.85, 0.10),   # 9 yellow stripe
    (0.10, 0.20, 0.85),   # 10 blue stripe
    (0.92, 0.18, 0.10),   # 11 red stripe
    (0.45, 0.10, 0.65),   # 12 purple stripe
    (0.95, 0.50, 0.10),   # 13 orange stripe
    (0.10, 0.45, 0.20),   # 14 green stripe
    (0.55, 0.18, 0.10),   # 15 maroon stripe
]

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=18, rot=None):
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

def _sphere(name, R, location, mat, u=18, v=12):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- floor ----------------------------------------
_box("floor", 3.5, 2.4, 0.04, (0, 0, -0.04), mat_floor)

# Table dimensions (a 9-foot pool table proportionally) :
TABLE_W = 1.40   # X span
TABLE_D = 2.50   # Y span
TABLE_H = 0.80   # height to felt
LEG_H   = 0.74   # legs below felt
LEG_W   = 0.10
FRAME_H = 0.07   # the wooden rail height above felt

# --- 4 carved wooden legs ----------------------
for sx in (-1, +1):
    for sy in (-1, +1):
        lx = sx * (TABLE_W/2 - LEG_W/2 - 0.04)
        ly = sy * (TABLE_D/2 - LEG_W/2 - 0.04)
        _box(f"leg_{sx}_{sy}", LEG_W, LEG_W, LEG_H,
               (lx, ly, LEG_H/2), mat_wood)
        # decorative cap (smaller wider block on top)
        _box(f"leg_cap_{sx}_{sy}", LEG_W * 1.20, LEG_W * 1.20, 0.05,
               (lx, ly, LEG_H + 0.025), mat_wood_lt)
        # decorative claw foot (slightly larger block under)
        _box(f"leg_foot_{sx}_{sy}", LEG_W * 1.30, LEG_W * 1.30, 0.05,
               (lx, ly, 0.025), mat_wood_lt)

# --- table frame (rectangular wooden surround) -----
FELT_Z = LEG_H + 0.04  # top of slate / felt
# the slate underneath the felt (just a darker slab)
_box("slate", TABLE_W * 0.97, TABLE_D * 0.97, 0.04,
       (0, 0, FELT_Z - 0.02), mat_wood)
# wooden rail around the edge
_box("rail_long_L", 0.10, TABLE_D + 0.02, FRAME_H,
       (-TABLE_W/2 + 0.05, 0, FELT_Z + FRAME_H/2), mat_wood_lt)
_box("rail_long_R", 0.10, TABLE_D + 0.02, FRAME_H,
       (TABLE_W/2 - 0.05, 0, FELT_Z + FRAME_H/2), mat_wood_lt)
_box("rail_short_F", TABLE_W + 0.02, 0.10, FRAME_H,
       (0, -TABLE_D/2 + 0.05, FELT_Z + FRAME_H/2), mat_wood_lt)
_box("rail_short_B", TABLE_W + 0.02, 0.10, FRAME_H,
       (0, TABLE_D/2 - 0.05, FELT_Z + FRAME_H/2), mat_wood_lt)

# inner leather cushions (a thin pad on the inside of each rail)
CUSH_T = 0.03
_box("cush_L", CUSH_T, TABLE_D - 0.30, 0.05,
       (-TABLE_W/2 + 0.10 + CUSH_T/2, 0, FELT_Z + 0.025), mat_rail)
_box("cush_R", CUSH_T, TABLE_D - 0.30, 0.05,
       (TABLE_W/2 - 0.10 - CUSH_T/2, 0, FELT_Z + 0.025), mat_rail)
_box("cush_F", TABLE_W - 0.30, CUSH_T, 0.05,
       (0, -TABLE_D/2 + 0.10 + CUSH_T/2, FELT_Z + 0.025), mat_rail)
_box("cush_B", TABLE_W - 0.30, CUSH_T, 0.05,
       (0, TABLE_D/2 - 0.10 - CUSH_T/2, FELT_Z + 0.025), mat_rail)

# --- green felt playing surface ----------------
felt = _box("felt", TABLE_W - 0.22, TABLE_D - 0.22, 0.005,
              (0, 0, FELT_Z + 0.0025), mat_felt)

# --- 6 pockets (corners + 2 mid-side) ----------
POCKET_R = 0.045
POCKET_LOCS = [
    # corners
    (-TABLE_W/2 + 0.10, -TABLE_D/2 + 0.10),
    ( TABLE_W/2 - 0.10, -TABLE_D/2 + 0.10),
    (-TABLE_W/2 + 0.10,  TABLE_D/2 - 0.10),
    ( TABLE_W/2 - 0.10,  TABLE_D/2 - 0.10),
    # side
    (-TABLE_W/2 + 0.10, 0),
    ( TABLE_W/2 - 0.10, 0),
]
for k, (px, py) in enumerate(POCKET_LOCS):
    # dark pocket hole
    _cyl(f"pocket_{k}", POCKET_R, POCKET_R, 0.012, 'Z',
           (px, py, FELT_Z + 0.011), mat_pocket, segments=18)
    # brass ring around the pocket
    _cyl(f"pocket_ring_{k}", POCKET_R * 1.18, POCKET_R * 1.18, 0.008, 'Z',
           (px, py, FELT_Z + 0.014), mat_brass, segments=18)

# --- triangle rack (15 balls + the rack frame) -----
BALL_R = 0.028
RACK_FRONT_Y = TABLE_D * 0.20   # apex of the rack is here
# Build 5 rows pointing toward -Y (apex at +Y, base at -Y wait — actually
# convention : apex toward the cue ball end (-Y). We'll put the apex at
# -Y end so the rack opens toward +Y... but better : put the rack at +Y
# half of the table, apex pointing toward -Y so the cue ball rolls from
# -Y to +Y and hits the apex.
RACK_APEX_Y = TABLE_D * 0.20
# rows go from row 0 (1 ball at apex) ... row 4 (5 balls at the back)
balls_in_rack = []
for row in range(5):
    n = row + 1
    y = RACK_APEX_Y + row * (BALL_R * 2 * 0.866)  # 0.866 = sqrt(3)/2 packed
    for c in range(n):
        x = (c - (n-1)/2) * BALL_R * 2
        idx = row * (row + 1) // 2 + c   # 0..14
        if idx >= 15:
            continue
        # ball index 1..15 maps to BALL_COLOURS[idx]
        color = BALL_COLOURS[idx]
        bm_mat = pbr_mat(f"ball_{idx+1}_mat", color, 0.05, 0.20)
        # parent each ball to its own empty so we can wiggle on impact
        bpy.ops.object.empty_add(type='PLAIN_AXES',
                                  location=(x, y, FELT_Z + BALL_R + 0.005))
        pv = bpy.context.active_object
        pv.name = f"ball_pivot_{idx+1}"
        sp = _sphere(f"ball_{idx+1}", BALL_R,
                       (0, 0, 0), bm_mat)
        sp.parent = pv; sp.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        # for striped balls (idx >= 8), add a white band ring
        if idx >= 8:
            band = _cyl(f"ball_band_{idx+1}", BALL_R * 0.96, BALL_R * 0.96,
                          BALL_R * 0.7, 'Z', (0, 0, 0), mat_band, segments=14)
            band.parent = pv; band.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        balls_in_rack.append((pv, x, y, idx))

# triangle rack frame around the balls
RACK_FRAME_T = 0.008
RACK_BACK_Y = RACK_APEX_Y + 4 * (BALL_R * 2 * 0.866)
APEX = mathutils.Vector((0, RACK_APEX_Y - BALL_R * 0.4, FELT_Z + 0.012))
BL = mathutils.Vector((-5 * BALL_R - BALL_R * 0.4, RACK_BACK_Y, FELT_Z + 0.012))
BR = mathutils.Vector((+5 * BALL_R + BALL_R * 0.4, RACK_BACK_Y, FELT_Z + 0.012))

def add_frame_edge(name, p0, p1):
    mid = (p0 + p1) * 0.5
    d = p1 - p0
    L = d.length
    obj = _cyl(name, RACK_FRAME_T, RACK_FRAME_T, L, 'Z',
                 (0, 0, 0), mat_wood_lt, segments=10)
    obj.location = mid
    direction = d.normalized()
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
    return obj

add_frame_edge("rack_apex_L", APEX, BL)
add_frame_edge("rack_apex_R", APEX, BR)
add_frame_edge("rack_back",   BL, BR)

# --- cue ball (a parent empty so we can animate it rolling) -----
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(0, -TABLE_D * 0.30, FELT_Z + BALL_R + 0.005))
cue_ball = bpy.context.active_object
cue_ball.name = "cue_ball_pivot"
cb = _sphere("cue_ball", BALL_R, (0, 0, 0), mat_white)
cb.parent = cue_ball
cb.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 2 cues laid on the table near the front edge -----
def add_cue(name, x_offset, angle):
    bpy.ops.object.empty_add(type='PLAIN_AXES',
                              location=(x_offset, -TABLE_D * 0.36, FELT_Z + 0.012))
    pv = bpy.context.active_object
    pv.name = name + "_pivot"
    # cue handle (longer, slightly larger)
    handle = _cyl(name + "_handle", 0.012, 0.008, 1.30, 'Y',
                    (0, 0, 0), mat_wood, segments=10)
    handle.parent = pv; handle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # ferrule + tip (small white + brown at +Y end)
    fer = _cyl(name + "_ferrule", 0.009, 0.009, 0.04, 'Y',
                 (0, 0.66, 0), mat_chrome, segments=10)
    fer.parent = pv; fer.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    tip = _cyl(name + "_tip", 0.008, 0.008, 0.015, 'Y',
                 (0, 0.69, 0), mat_rail, segments=10)
    tip.parent = pv; tip.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # butt cap
    cap = _cyl(name + "_butt", 0.012, 0.010, 0.03, 'Y',
                 (0, -0.66, 0), mat_brass, segments=10)
    cap.parent = pv; cap.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    pv.rotation_euler = (0, 0, angle)
    return pv

add_cue("cue_L", -0.35, math.radians(5))
add_cue("cue_R",  0.35, math.radians(-5))

# --- animation ------------------------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Cue ball rolls from y=-0.75 to y=+0.50 then stops.
CUE_START_Y = -TABLE_D * 0.30
CUE_HIT_Y   = RACK_APEX_Y - BALL_R - 0.005
# It travels over the first 60% of the loop, sits still for the last 40%.
TRAVEL_END = 0.55
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    if t < TRAVEL_END:
        u = t / TRAVEL_END
        # ease : faster at start, slows near impact (ease-out)
        u_smooth = 1.0 - (1.0 - u)**2
        y = CUE_START_Y + (CUE_HIT_Y - CUE_START_Y) * u_smooth
    else:
        y = CUE_HIT_Y
    cue_ball.location = (0, y, FELT_Z + BALL_R + 0.005)
    # rolling rotation around X (forward roll)
    distance_traveled = y - CUE_START_Y
    roll_angle = -distance_traveled / BALL_R
    cue_ball.rotation_euler = (roll_angle, 0, 0)
    cue_ball.keyframe_insert("location", frame=f)
    cue_ball.keyframe_insert("rotation_euler", frame=f)
if cue_ball.animation_data and cue_ball.animation_data.action:
    for fc in cue_ball.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Rack balls jiggle on impact : starting at t = TRAVEL_END, each ball
# wiggles its location (x,y) by a tiny amount (proportional to its
# distance from the apex). Decay over the remaining 0.45 of the loop.
IMPACT_T = TRAVEL_END
for pv, x0, y0, idx in balls_in_rack:
    # distance from apex (in lattice units)
    dy = (y0 - RACK_APEX_Y) / (BALL_R * 2)
    dx = abs(x0) / (BALL_R * 2)
    dist = math.sqrt(dx*dx + dy*dy)
    # delay : balls further back jiggle later
    delay = dist * 0.04
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        local = t - (IMPACT_T + delay)
        if local <= 0:
            ox = 0; oy = 0
        else:
            # exponential decay of a damped oscillation
            amp = 0.006 * math.exp(-local * 4.0) * (1.0 / (1.0 + dist))
            phase_x = 12.0 + (idx % 3) * 1.5
            phase_y = 14.0 + (idx % 4) * 1.2
            ox = amp * math.sin(local * phase_x * 2*math.pi)
            oy = amp * math.cos(local * phase_y * 2*math.pi)
        bpy.context.scene.frame_set(f)
        pv.location = (x0 + ox, y0 + oy, FELT_Z + BALL_R + 0.005)
        pv.keyframe_insert("location", frame=f)
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"BILL_OK: {out_glb}", flush=True)
'''


def make_billiard(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_bill_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "BILL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_billiard(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
