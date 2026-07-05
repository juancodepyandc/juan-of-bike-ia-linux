"""Procedural bicycle (Blender headless).

Classic diamond frame + 2 spoked wheels + handlebars + saddle + crank
arms + pedals. Animation : both wheels spin, pedal crank rotates at
half the wheel speed (typical gear ratio).

CLI:
  python proc_bicycle.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "bicycle.glb"

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

mat_frame_blue = pbr_mat("frame_blue", (0.10, 0.30, 0.75), 0.30, 0.30)
mat_tyre       = pbr_mat("tyre_black", (0.05, 0.05, 0.07), 0.10, 0.65)
mat_rim        = pbr_mat("rim_chrome", (0.62, 0.64, 0.66), 1.00, 0.18)
mat_spoke      = pbr_mat("spoke_steel",(0.55, 0.57, 0.60), 1.00, 0.25)
mat_saddle     = pbr_mat("saddle_brown",(0.30, 0.18, 0.10), 0.00, 0.45)
mat_grip       = pbr_mat("grip_black", (0.15, 0.15, 0.15), 0.00, 0.60)
mat_pedal      = pbr_mat("pedal_grey", (0.25, 0.25, 0.27), 0.30, 0.40)
mat_ground     = pbr_mat("ground",     (0.32, 0.32, 0.34), 0.00, 0.85)

def _cyl(name, R1, R2, depth, axis, location, mat, segments=24):
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

def _box_along(name, p0, p1, R, mat):
    p0v = mathutils.Vector(p0); p1v = mathutils.Vector(p1)
    direction = p1v - p0v
    length = direction.length
    if length < 1e-6:
        return None
    direction.normalize()
    mid = (p0v + p1v) / 2
    bpy.ops.mesh.primitive_cube_add(size=1, location=mid)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (length, R*2, R*2)
    bpy.ops.object.transform_apply(scale=True)
    yaw = math.atan2(direction.y, direction.x)
    pitch = -math.asin(direction.z)
    obj.rotation_euler = (0, pitch, yaw)
    obj.data.materials.append(mat)
    return obj

# --- ground ----------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
g = bpy.context.active_object
g.name = "ground"
g.scale = (3.0, 1.5, 0.04)
bpy.ops.object.transform_apply(scale=True)
g.data.materials.append(mat_ground)

# --- key anchor points (in the bike's side view, X along travel, Z up) -
WHEEL_R = 0.33
BB_X    = 0.0        # bottom-bracket X (centre of pedal crank)
BB_Z    = WHEEL_R    # bottom bracket sits at wheel-axle height
REAR_AXLE_X  = -0.55
FRONT_AXLE_X = +0.55
HEAD_TUBE_TOP_X = 0.42
HEAD_TUBE_TOP_Z = 0.95
SEAT_TUBE_TOP_X = -0.22
SEAT_TUBE_TOP_Z = 1.00

# --- wheels (each with pivot empty for animation) -------------------
def _build_wheel(name, cx, cz):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, 0, cz))
    pv = bpy.context.active_object
    pv.name = f"{name}_pivot"

    tyre = _cyl(f"{name}_tyre", WHEEL_R, WHEEL_R, 0.035, 'Y', (0, 0, 0), mat_tyre)
    tyre.parent = pv
    tyre.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    rim = _cyl(f"{name}_rim", WHEEL_R * 0.92, WHEEL_R * 0.92, 0.040, 'Y',
                 (0, 0, 0), mat_rim)
    rim.parent = pv
    rim.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    hub = _cyl(f"{name}_hub", 0.04, 0.04, 0.05, 'Y', (0, 0, 0), mat_spoke)
    hub.parent = pv
    hub.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    # 8 spokes radiating from hub to rim
    for k in range(8):
        a = k * math.pi / 4
        ex = math.cos(a) * (WHEEL_R * 0.90)
        ez = math.sin(a) * (WHEEL_R * 0.90)
        s = _box_along(f"{name}_spoke_{k}", (0, 0, 0), (ex, 0, ez), 0.004, mat_spoke)
        s.parent = pv
        s.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    return pv

rear_pivot  = _build_wheel("rear",  REAR_AXLE_X,  WHEEL_R)
front_pivot = _build_wheel("front", FRONT_AXLE_X, WHEEL_R)

# --- frame (diamond : top tube + down tube + seat tube + chain stays + seat stays)
# Top tube : HEAD_TUBE_TOP to SEAT_TUBE_TOP
_box_along("top_tube",
            (HEAD_TUBE_TOP_X, 0, HEAD_TUBE_TOP_Z * 0.85),
            (SEAT_TUBE_TOP_X, 0, SEAT_TUBE_TOP_Z * 0.92),
            0.022, mat_frame_blue)
# Down tube : HEAD_TUBE_TOP to BB
_box_along("down_tube",
            (HEAD_TUBE_TOP_X * 0.95, 0, HEAD_TUBE_TOP_Z * 0.85 - 0.02),
            (BB_X, 0, BB_Z + 0.01),
            0.022, mat_frame_blue)
# Seat tube : SEAT_TUBE_TOP to BB
_box_along("seat_tube",
            (SEAT_TUBE_TOP_X, 0, SEAT_TUBE_TOP_Z * 0.92 - 0.02),
            (BB_X, 0, BB_Z + 0.01),
            0.022, mat_frame_blue)
# Chain stays (2 per side) : BB to rear axle
for sy in (-1, 1):
    _box_along(f"chain_stay_{sy}",
                (BB_X, sy * 0.025, BB_Z),
                (REAR_AXLE_X, sy * 0.025, WHEEL_R),
                0.014, mat_frame_blue)
# Seat stays : seat tube top to rear axle
for sy in (-1, 1):
    _box_along(f"seat_stay_{sy}",
                (SEAT_TUBE_TOP_X, sy * 0.025, SEAT_TUBE_TOP_Z * 0.92 - 0.02),
                (REAR_AXLE_X, sy * 0.025, WHEEL_R),
                0.014, mat_frame_blue)
# Head tube : a short vertical segment around HEAD_TUBE_TOP
_box_along("head_tube",
            (HEAD_TUBE_TOP_X, 0, HEAD_TUBE_TOP_Z - 0.10),
            (HEAD_TUBE_TOP_X, 0, HEAD_TUBE_TOP_Z + 0.05),
            0.025, mat_frame_blue)

# --- fork (from head tube down to front axle, 2 thin tubes) ---------
for sy in (-1, 1):
    _box_along(f"fork_{sy}",
                (HEAD_TUBE_TOP_X, sy * 0.025, HEAD_TUBE_TOP_Z - 0.05),
                (FRONT_AXLE_X,    sy * 0.025, WHEEL_R),
                0.016, mat_frame_blue)

# --- handlebars (above head tube) ----------------------------------
HB_Z = HEAD_TUBE_TOP_Z + 0.10
# stem
_box_along("stem",
            (HEAD_TUBE_TOP_X, 0, HEAD_TUBE_TOP_Z + 0.02),
            (HEAD_TUBE_TOP_X + 0.04, 0, HB_Z),
            0.016, mat_frame_blue)
# bar (horizontal cylinder along Y)
hb = _cyl("handlebar", 0.014, 0.014, 0.40, 'Y',
            (HEAD_TUBE_TOP_X + 0.04, 0, HB_Z), mat_frame_blue)
# 2 grips
for sy in (-1, 1):
    _cyl(f"grip_{sy}", 0.018, 0.018, 0.10, 'Y',
           (HEAD_TUBE_TOP_X + 0.04, sy * 0.18, HB_Z), mat_grip)

# --- seat / saddle ------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(SEAT_TUBE_TOP_X - 0.05,
                                                   0,
                                                   SEAT_TUBE_TOP_Z + 0.03))
saddle = bpy.context.active_object
saddle.name = "saddle"
saddle.scale = (0.20, 0.10, 0.05)
bpy.ops.object.transform_apply(scale=True)
saddle.data.materials.append(mat_saddle)

# seat post (short tube above seat tube top)
_box_along("seat_post",
            (SEAT_TUBE_TOP_X, 0, SEAT_TUBE_TOP_Z * 0.92),
            (SEAT_TUBE_TOP_X - 0.02, 0, SEAT_TUBE_TOP_Z + 0.03),
            0.014, mat_frame_blue)

# --- pedal crank assembly (rotates around BB) --------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(BB_X, 0, BB_Z))
crank_pivot = bpy.context.active_object
crank_pivot.name = "crank_pivot"

# chainring (small black disc)
chainring = _cyl("chainring", 0.10, 0.10, 0.012, 'Y',
                   (0, 0.04, 0), mat_pedal)
chainring.parent = crank_pivot
chainring.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 2 crank arms (180 deg apart)
CRANK_L = 0.16
for sign in (-1, +1):
    # crank arm extends along +X at angle 0 (then animated)
    arm_x = sign * CRANK_L * 0.5
    bpy.ops.mesh.primitive_cube_add(size=1, location=(arm_x, sign * 0.06, 0))
    arm = bpy.context.active_object
    arm.name = f"crank_arm_{sign}"
    arm.scale = (CRANK_L, 0.02, 0.018)
    bpy.ops.object.transform_apply(scale=True)
    arm.data.materials.append(mat_frame_blue)
    arm.parent = crank_pivot
    arm.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # pedal at the tip of each arm
    pedal = _cyl(f"pedal_{sign}", 0.03, 0.03, 0.08, 'Y',
                   (sign * CRANK_L, sign * 0.12, 0), mat_pedal)
    pedal.parent = crank_pivot
    pedal.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation -----------------------------------------------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# wheels spin around Y (axle) ; 2 turns per loop
for pv in (rear_pivot, front_pivot):
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        pv.rotation_euler = (0, -2 * 2 * math.pi * t, 0)  # rolling forward (+X)
        pv.keyframe_insert("rotation_euler", frame=f)
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# crank : 1 turn per loop (half wheel speed = typical gear ratio)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    crank_pivot.rotation_euler = (0, -2 * math.pi * t, 0)
    crank_pivot.keyframe_insert("rotation_euler", frame=f)
if crank_pivot.animation_data and crank_pivot.animation_data.action:
    for fc in crank_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"BICYCLE_OK: {out_glb}", flush=True)
'''


def make_bicycle(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_bike_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "BICYCLE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_bicycle(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
