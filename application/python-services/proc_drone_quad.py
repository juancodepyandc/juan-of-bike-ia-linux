"""Procedural quadcopter drone (Blender headless).

A four-rotor drone with X-frame, motor mounts, and 2-blade propellers.
2 props rotate CW, 2 CCW (diagonal pairs) — physically accurate stability
config. Body bobs slightly + tilts as it would in hover.

CLI:
  python proc_drone_quad.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "drone.glb"

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

mat_carbon  = pbr_mat("carbon_fiber", (0.08, 0.08, 0.10), 0.30, 0.42)
mat_red     = pbr_mat("accent_red",   (0.78, 0.10, 0.10), 0.10, 0.40)
mat_steel   = pbr_mat("steel_motor",  (0.55, 0.57, 0.60), 1.00, 0.28)
mat_blade   = pbr_mat("prop_grey",    (0.20, 0.22, 0.25), 0.20, 0.55)
mat_led     = pbr_mat("led_green",    (0.10, 0.95, 0.30), 0.00, 0.20)

def _add_box_obj(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

def _cyl(name, R, depth, axis, location, mat):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=40,
                            radius1=R, radius2=R, depth=depth)
    if axis == 'X':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'Y'), verts=bm.verts)
    elif axis == 'Y':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'X'), verts=bm.verts)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- root empty for body bob/tilt animation -------------------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
root = bpy.context.active_object
root.name = "drone_root"

# --- central body ---------------------------------------------------------
body = _add_box_obj("body", 0.18, 0.18, 0.06, (0, 0, 0), mat_carbon)
body.parent = root
body.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# Body top accent (red)
top = _add_box_obj("body_top", 0.14, 0.14, 0.02, (0, 0, 0.04), mat_red)
top.parent = root
top.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# Front-facing LED indicator
led = _cyl("led", 0.012, 0.012, 'Y', (0, -0.09, 0.02), mat_led)
led.parent = root
led.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 4 arms in X configuration --------------------------------------------
ARM_LEN  = 0.36
ARM_R    = 0.014
ARM_ANGLES = [math.radians(45), math.radians(135), math.radians(225), math.radians(315)]

motor_pivots = []
prop_dirs = [+1, -1, +1, -1]  # alternating CW/CCW per arm angle (diagonals match)

for i, a in enumerate(ARM_ANGLES):
    # arm = horizontal cylinder, originated at body centre, extends outward by ARM_LEN
    arm_x = math.cos(a) * ARM_LEN * 0.5
    arm_y = math.sin(a) * ARM_LEN * 0.5
    # build cylinder along its length axis
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=20,
                            radius1=ARM_R, radius2=ARM_R, depth=ARM_LEN)
    # orient along X then rotate around Z by a
    bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'Y'), verts=bm.verts)
    bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(a, 4, 'Z'), verts=bm.verts)
    mesh = bpy.data.meshes.new(f"arm_{i}")
    arm = bpy.data.objects.new(f"arm_{i}", mesh)
    bpy.context.collection.objects.link(arm)
    bm.to_mesh(mesh); bm.free()
    arm.location = (arm_x, arm_y, 0)
    arm.data.materials.append(mat_carbon)
    arm.parent = root
    arm.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    # motor housing at arm tip (cylinder pointing up)
    tip_x = math.cos(a) * ARM_LEN
    tip_y = math.sin(a) * ARM_LEN
    motor = _cyl(f"motor_{i}", 0.030, 0.045, 'Z', (tip_x, tip_y, 0.022), mat_steel)
    motor.parent = root
    motor.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    # motor base ring (red accent)
    ring = _cyl(f"motor_ring_{i}", 0.034, 0.010, 'Z', (tip_x, tip_y, 0.005), mat_red)
    ring.parent = root
    ring.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    # propeller pivot empty (animated)
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(tip_x, tip_y, 0.050))
    prop_pivot = bpy.context.active_object
    prop_pivot.name = f"prop_pivot_{i}"
    prop_pivot.parent = root
    prop_pivot.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    motor_pivots.append((prop_pivot, prop_dirs[i]))

    # propeller : 2 thin blades = elongated boxes, joined into the pivot frame
    BLADE_L, BLADE_W, BLADE_H = 0.13, 0.020, 0.004
    # Build both blades as a single bmesh centred at (0,0,0) so they spin
    # around the prop_pivot.
    mesh_prop = bpy.data.meshes.new(f"prop_{i}_mesh")
    prop = bpy.data.objects.new(f"prop_{i}", mesh_prop)
    bpy.context.collection.objects.link(prop)
    bm = bmesh.new()
    # Blade A : extends along +X, centred at (BLADE_L/2, 0, 0)
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(BLADE_L, BLADE_W, BLADE_H), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(BLADE_L/2 - 0.005, 0, 0), verts=bm.verts)
    # Blade B : second cube extending along -X
    verts_before = set(bm.verts)
    bmesh.ops.create_cube(bm, size=1.0)
    new_verts = [v for v in bm.verts if v not in verts_before]
    bmesh.ops.scale(bm, vec=(BLADE_L, BLADE_W, BLADE_H), verts=new_verts)
    bmesh.ops.translate(bm, vec=(-(BLADE_L/2 - 0.005), 0, 0), verts=new_verts)
    # hub
    verts_before2 = set(bm.verts)
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16,
                            radius1=0.012, radius2=0.012, depth=0.015)
    new_verts2 = [v for v in bm.verts if v not in verts_before2]
    bm.to_mesh(mesh_prop); bm.free()
    prop.data.materials.append(mat_blade)
    prop.parent = prop_pivot
    prop.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- landing skids --------------------------------------------------------
for sx in (-1, 1):
    # vertical strut
    _add_box_obj(f"skid_strut_{sx}", 0.012, 0.012, 0.08,
                  (sx * 0.10, 0, -0.04), mat_carbon).parent = root
    # horizontal foot
    foot = _add_box_obj(f"skid_foot_{sx}", 0.012, 0.24, 0.010,
                         (sx * 0.10, 0, -0.085), mat_carbon)
    foot.parent = root
    foot.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# Reset strut parent_inverse (the chained .parent = root above didn't set it)
for o in bpy.data.objects:
    if o.name.startswith("skid_strut_"):
        o.parent = root
        o.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        # restore its original world Z = -0.04 by keeping its current location
        # (which was set at creation before the parenting)

# --- animation ------------------------------------------------------------
FPS = 30
DURATION = 3.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

# Propellers : spin fast (10 turns per loop), alternating direction
KEY_EVERY = 2
for prop_pivot, dir_sign in motor_pivots:
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        angle = dir_sign * 10 * 2 * math.pi * t
        bpy.context.scene.frame_set(f)
        prop_pivot.rotation_euler = (0, 0, angle)
        prop_pivot.keyframe_insert("rotation_euler", frame=f)
    if prop_pivot.animation_data and prop_pivot.animation_data.action:
        for fc in prop_pivot.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Body bob/tilt : root translates vertically + tilts gently
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    root.location = (0, 0, 0.6 + math.sin(2 * math.pi * t) * 0.03)
    root.rotation_euler = (math.sin(2 * math.pi * t * 0.5) * math.radians(4),
                            math.cos(2 * math.pi * t * 0.5) * math.radians(3),
                            0)
    root.keyframe_insert("location", frame=f)
    root.keyframe_insert("rotation_euler", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"DRONE_OK: {out_glb}", flush=True)
'''


def make_drone(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_drone_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "DRONE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_drone(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
