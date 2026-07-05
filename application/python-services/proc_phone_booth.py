"""Procedural British red telephone box (Blender headless).

K6-style London phone booth : concrete base + 4 red corner posts + glass
panes (5 small rectangles per side, 3 sides + door) + pyramidal red
roof + emissive "TELEPHONE" crown sign + chrome door handle + interior
black rotary phone with handset on cradle. Animation : crown light pulses
+ door swings ajar by 5° then closes + dial wobbles 10°.

CLI:
  python proc_phone_booth.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "phonebox.glb"

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

mat_floor    = pbr_mat("floor",     (0.25, 0.22, 0.20), 0.00, 0.85)
mat_pave     = pbr_mat("pave",      (0.40, 0.38, 0.35), 0.00, 0.85)
mat_red      = pbr_mat("red",       (0.55, 0.08, 0.06), 0.10, 0.40)
mat_red_d    = pbr_mat("red_dk",    (0.35, 0.04, 0.03), 0.10, 0.40)
mat_glass    = pbr_mat("glass",     (0.55, 0.65, 0.75), 0.00, 0.05, alpha=0.18)
mat_chrome   = pbr_mat("chrome",    (0.80, 0.82, 0.85), 1.00, 0.18)
mat_brass    = pbr_mat("brass",     (0.92, 0.72, 0.25), 1.00, 0.20)
mat_dark     = pbr_mat("dark",      (0.06, 0.06, 0.07), 0.30, 0.45)
mat_crown    = pbr_mat("crown",     (0.95, 0.92, 0.85), 0.10, 0.20,
                          emission=((1.00, 0.90, 0.65), 5.0))
mat_phone    = pbr_mat("phone",     (0.06, 0.06, 0.07), 0.10, 0.40)
mat_dial     = pbr_mat("dial",      (0.92, 0.90, 0.85), 0.10, 0.30)
mat_cradle   = pbr_mat("cradle",    (0.85, 0.85, 0.80), 0.20, 0.30)
mat_money    = pbr_mat("coin_slot", (0.40, 0.40, 0.42), 0.85, 0.30)

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

# Conventions : booth faces -Y (door on -Y side). Up = +Z.

# --- pavement ---------------------------
_box("floor", 2.2, 2.2, 0.04, (0, 0, -0.04), mat_floor)
_box("pavement_slab", 1.4, 1.4, 0.04, (0, 0, 0.02), mat_pave)

# Booth dims
B_W = 0.75   # X
B_D = 0.75   # Y
POST_H = 2.20
POST_W = 0.08

# --- concrete base plate -----
BASE_H = 0.05
BASE_Z = 0.04 + BASE_H/2
_box("base_plate", B_W + 0.02, B_D + 0.02, BASE_H, (0, 0, BASE_Z), mat_pave)

# --- 4 red corner posts ----
post_z = BASE_Z + BASE_H/2 + POST_H/2
for sx in (-1, +1):
    for sy in (-1, +1):
        _box(f"post_{sx}_{sy}", POST_W, POST_W, POST_H,
               (sx * (B_W/2 - POST_W/2), sy * (B_D/2 - POST_W/2), post_z),
               mat_red)

# --- horizontal panels (top + middle + bottom of each side, except door) ----
# Each side : 3 sides have 5 small glass panes (vertical), the front side
# has a door (mostly red panel + 3 small panes on top, 1 chrome handle).
# We'll build each side as a frame of horizontal red rails + vertical glass panels.

PANE_T = 0.012  # depth (toward outside)
PANE_W = (B_W - 2 * POST_W) / 5  # 5 panes per row width

def build_side(name_prefix, axis, sign, has_door):
    """axis = 'Y' (front/back) or 'X' (left/right). sign +1 or -1 is which face."""
    # determine span (along which axis the panes are arrayed)
    if axis == 'Y':
        span = B_W - 2*POST_W  # along X
        side_y = sign * (B_D/2 - PANE_T/2)
    else:
        span = B_D - 2*POST_W  # along Y
        side_x = sign * (B_W/2 - PANE_T/2)

    # frame rails (horizontal red bars at 3 heights)
    rail_zs = [
        BASE_Z + BASE_H/2 + 0.05,  # bottom rail
        BASE_Z + BASE_H/2 + POST_H * 0.45,  # middle rail
        BASE_Z + BASE_H/2 + POST_H - 0.15,  # top rail
    ]
    for rz in rail_zs:
        if axis == 'Y':
            r = _box(f"{name_prefix}_rail_z{rz:.2f}", span + POST_W * 0.4, 0.04, 0.04,
                       (0, side_y, rz), mat_red)
        else:
            r = _box(f"{name_prefix}_rail_z{rz:.2f}", 0.04, span + POST_W * 0.4, 0.04,
                       (side_x, 0, rz), mat_red)

    # 5 panes per "level" (we have 2 levels : between bottom-middle, and middle-top)
    LEVEL_DEFS = [
        (rail_zs[0] + 0.06, rail_zs[1] - 0.04),  # lower glass row
        (rail_zs[1] + 0.06, rail_zs[2] - 0.04),  # upper glass row
    ]
    n_panes = 5
    for lvl_idx, (z0, z1) in enumerate(LEVEL_DEFS):
        # if door : skip the lower level on the front side
        if has_door and lvl_idx == 0:
            continue
        pane_h = z1 - z0
        pane_zmid = (z0 + z1) / 2
        for k in range(n_panes):
            if axis == 'Y':
                px = -span/2 + (k + 0.5) * span / n_panes
                py = side_y
                _box(f"{name_prefix}_pane_{lvl_idx}_{k}",
                       PANE_W * 0.94, PANE_T, pane_h * 0.94,
                       (px, py, pane_zmid), mat_glass)
                # thin red mullion between panes
                if k < n_panes - 1:
                    _box(f"{name_prefix}_mull_{lvl_idx}_{k}",
                           0.015, 0.025, pane_h * 0.96,
                           (-span/2 + (k + 1) * span / n_panes, side_y, pane_zmid),
                           mat_red)
            else:
                py = -span/2 + (k + 0.5) * span / n_panes
                px = side_x
                _box(f"{name_prefix}_pane_{lvl_idx}_{k}",
                       PANE_T, PANE_W * 0.94, pane_h * 0.94,
                       (px, py, pane_zmid), mat_glass)
                if k < n_panes - 1:
                    _box(f"{name_prefix}_mull_{lvl_idx}_{k}",
                           0.025, 0.015, pane_h * 0.96,
                           (side_x, -span/2 + (k + 1) * span / n_panes, pane_zmid),
                           mat_red)

# left, right, and back sides (no door)
build_side("side_L", 'X', -1, False)
build_side("side_R", 'X', +1, False)
build_side("side_B", 'Y', +1, False)

# === Front side : door + upper glass row ===
# We'll build the door as a swinging child of a pivot empty
# (only its upper level has panes; the lower portion is solid red)
DOOR_W = (B_W - 2 * POST_W) - 0.02
DOOR_H = POST_H - 0.20
DOOR_X = 0
DOOR_Y = -B_D/2 + PANE_T/2
DOOR_Z_MID = BASE_Z + BASE_H/2 + 0.05 + DOOR_H/2  # bottom-aligned with bottom rail

# Hinge pivot on the -X side of the door
HINGE_X = -DOOR_W/2
HINGE_Y = DOOR_Y
HINGE_Z = DOOR_Z_MID
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(HINGE_X, HINGE_Y, HINGE_Z))
door_pivot = bpy.context.active_object
door_pivot.name = "door_pivot"

# Door body (solid red slab) — centered with the hinge on the -X edge
door_body = _box("door_body", DOOR_W, 0.025, DOOR_H,
                   (DOOR_W/2, 0, 0), mat_red)
door_body.parent = door_pivot
door_body.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 4 small glass panes on the upper half of the door
DOOR_GLASS_Z0 = DOOR_H * 0.10
DOOR_GLASS_Z1 = DOOR_H * 0.40
N_DOOR_PANES = 4
for k in range(N_DOOR_PANES):
    px = (k + 0.5) / N_DOOR_PANES * (DOOR_W - 0.04) + 0.02
    pn = _box(f"door_pane_{k}",
                DOOR_W / N_DOOR_PANES * 0.85, 0.020, (DOOR_GLASS_Z1 - DOOR_GLASS_Z0) * 0.95,
                (px, -0.005, (DOOR_GLASS_Z0 + DOOR_GLASS_Z1)/2), mat_glass)
    pn.parent = door_pivot
    pn.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# chrome door handle (vertical bar near the +X edge of the door)
handle = _box("door_handle", 0.012, 0.020, DOOR_H * 0.25,
                (DOOR_W - 0.04, -0.018, -DOOR_H * 0.05), mat_chrome)
handle.parent = door_pivot
handle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 small anchor knobs
for sz in (-1, +1):
    knob = _sphere(f"handle_knob_{sz}", 0.012,
                     (DOOR_W - 0.04, -0.014, -DOOR_H * 0.05 + sz * DOOR_H * 0.13), mat_chrome)
    knob.parent = door_pivot
    knob.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# === Top crown sign : "TELEPHONE" - emissive panel on all 4 sides ===
CROWN_Z = BASE_Z + BASE_H/2 + POST_H
CROWN_H = 0.18
# crown frame
_box("crown_frame", B_W + 0.04, B_D + 0.04, CROWN_H,
       (0, 0, CROWN_Z + CROWN_H/2), mat_red_d)
# 4 emissive "TELEPHONE" panels (one per side)
for axis, sign, sw, sd in (('Y', -1, B_W - 0.06, 0.005),
                              ('Y', +1, B_W - 0.06, 0.005),
                              ('X', -1, 0.005, B_D - 0.06),
                              ('X', +1, 0.005, B_D - 0.06)):
    if axis == 'Y':
        _box(f"crown_sign_Y{sign}", sw, sd, CROWN_H * 0.65,
               (0, sign * (B_D/2 + 0.024), CROWN_Z + CROWN_H/2), mat_crown)
    else:
        _box(f"crown_sign_X{sign}", sw, sd, CROWN_H * 0.65,
               (sign * (B_W/2 + 0.024), 0, CROWN_Z + CROWN_H/2), mat_crown)

# === Pyramidal roof on top of crown ===
# Build 4 sloped triangular faces meeting at apex
mesh = bpy.data.meshes.new("roof")
obj = bpy.data.objects.new("roof", mesh)
bpy.context.collection.objects.link(obj)
bm = bmesh.new()
ROOF_BASE_Z = CROWN_Z + CROWN_H
ROOF_TIP_Z = ROOF_BASE_Z + 0.30
ROOF_W = (B_W + 0.04) / 2 + 0.04
ROOF_D = (B_D + 0.04) / 2 + 0.04
v_apex = bm.verts.new((0, 0, ROOF_TIP_Z))
v_ne = bm.verts.new(( ROOF_W,  ROOF_D, ROOF_BASE_Z))
v_nw = bm.verts.new((-ROOF_W,  ROOF_D, ROOF_BASE_Z))
v_sw = bm.verts.new((-ROOF_W, -ROOF_D, ROOF_BASE_Z))
v_se = bm.verts.new(( ROOF_W, -ROOF_D, ROOF_BASE_Z))
bm.faces.new([v_apex, v_ne, v_nw])
bm.faces.new([v_apex, v_nw, v_sw])
bm.faces.new([v_apex, v_sw, v_se])
bm.faces.new([v_apex, v_se, v_ne])
# base square (closes the roof from below)
bm.faces.new([v_ne, v_se, v_sw, v_nw])
bm.to_mesh(mesh); bm.free()
obj.data.materials.append(mat_red)

# small brass orb finial on the apex
_sphere("roof_finial", 0.03, (0, 0, ROOF_TIP_Z + 0.025), mat_brass)

# === Interior : rotary telephone on a shelf inside the back wall ===
PHONE_X = 0
PHONE_Y = B_D/2 - 0.10
PHONE_Z = BASE_Z + BASE_H/2 + 1.10
# small chrome shelf
_box("phone_shelf", B_W * 0.55, 0.10, 0.012,
       (PHONE_X, PHONE_Y - 0.05, PHONE_Z - 0.05), mat_chrome)
# phone body (black rectangular base)
_box("phone_body", 0.16, 0.10, 0.05,
       (PHONE_X, PHONE_Y, PHONE_Z), mat_phone)
# rotary dial : white disc with finger holes
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(PHONE_X + 0.02, PHONE_Y, PHONE_Z + 0.030))
dial_pivot = bpy.context.active_object
dial_pivot.name = "dial_pivot"
disc = _cyl("dial_disc", 0.040, 0.040, 0.005, 'Z', (0, 0, 0), mat_dial)
disc.parent = dial_pivot
disc.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 10 finger holes (dark spheres at 10 angles)
for i in range(10):
    a = i * 2*math.pi/10
    hx = 0.030 * math.cos(a); hy = 0.030 * math.sin(a)
    h = _sphere(f"dial_hole_{i}", 0.005, (hx, hy, 0.003), mat_phone)
    h.parent = dial_pivot
    h.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# handset cradle (2 small chrome forks rising from the body)
for sx in (-1, +1):
    _box(f"cradle_{sx}", 0.014, 0.014, 0.020,
           (PHONE_X + sx * 0.05, PHONE_Y - 0.025, PHONE_Z + 0.035), mat_cradle)
# handset (a curved black bar sitting on the cradle)
_box("handset", 0.14, 0.022, 0.018,
       (PHONE_X, PHONE_Y - 0.025, PHONE_Z + 0.054), mat_phone)
# coin slot indicator
_box("coin_slot", 0.06, 0.005, 0.012,
       (PHONE_X, PHONE_Y + 0.052, PHONE_Z + 0.012), mat_money)

# --- animation ------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Crown lamps pulse
bsdf_cr = mat_crown.node_tree.nodes.get("Principled BSDF")
em_cr = bsdf_cr.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_cr.default_value = 4.0 + 2.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.0))
    bpy.context.scene.frame_set(f)
    em_cr.keyframe_insert(data_path="default_value", frame=f)

# Door wobbles ajar by 5° (someone is letting it open then closing)
def door_angle(t):
    # half-sin : open at t=0.3, close at t=0.5
    if t < 0.2 or t > 0.6:
        return 0.0
    return math.radians(5.0) * math.sin(math.pi * (t - 0.2) / 0.4)

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    door_pivot.rotation_euler = (0, 0, door_angle(t))
    door_pivot.keyframe_insert("rotation_euler", frame=f)
if door_pivot.animation_data and door_pivot.animation_data.action:
    for fc in door_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Rotary dial wobbles 10° during the dialing portion
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    dial_pivot.rotation_euler = (0, 0,
                                   math.radians(10) * math.sin(2*math.pi*t * 1.5))
    dial_pivot.keyframe_insert("rotation_euler", frame=f)
if dial_pivot.animation_data and dial_pivot.animation_data.action:
    for fc in dial_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"BOOTH_OK: {out_glb}", flush=True)
'''


def make_booth(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_booth_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "BOOTH_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_booth(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
