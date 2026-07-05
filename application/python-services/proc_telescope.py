"""Procedural telescope on a tripod (Blender headless).

Tripod (3 legs converging at top) + altazimuth yoke mount + main optical
tube + parallel finder scope + eyepiece + counterweight. Animation :
the yoke rotates in azimuth (around Z), the tube tilts in altitude
(around Y of the yoke's local frame), giving the classic sky-scanning
sweep.

CLI:
  python proc_telescope.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "telescope.glb"

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

mat_tube    = pbr_mat("tube_white",   (0.92, 0.92, 0.88), 0.10, 0.32)
mat_dark    = pbr_mat("dark_metal",   (0.15, 0.15, 0.18), 0.90, 0.40)
mat_brass   = pbr_mat("brass_knob",   (0.86, 0.62, 0.20), 1.00, 0.28)
mat_glass   = pbr_mat("lens_glass",   (0.10, 0.18, 0.30), 0.00, 0.05)
mat_ground  = pbr_mat("ground_plate", (0.30, 0.30, 0.32), 0.00, 0.85)
mat_wood    = pbr_mat("tripod_wood",  (0.42, 0.27, 0.13), 0.00, 0.65)

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

# --- ground -----------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
g = bpy.context.active_object
g.name = "ground"
g.scale = (3.0, 3.0, 0.04)
bpy.ops.object.transform_apply(scale=True)
g.data.materials.append(mat_ground)

# --- tripod : 3 legs converging at top (0, 0, MOUNT_Z) ----------------
MOUNT_Z = 0.95
LEG_BASE_R = 0.55   # foot radius from centre
for k in range(3):
    a = k * 2 * math.pi / 3
    fx = math.cos(a) * LEG_BASE_R
    fy = math.sin(a) * LEG_BASE_R
    _box_along(f"leg_{k}",
                (fx, fy, 0.0),
                (0.0, 0.0, MOUNT_Z),
                0.022, mat_wood)
    # rubber foot
    _cyl(f"foot_{k}", 0.045, 0.045, 0.025, 'Z', (fx, fy, 0.012), mat_dark)

# tripod head : a small disc + collar
_cyl("tripod_head", 0.09, 0.09, 0.04, 'Z', (0, 0, MOUNT_Z - 0.02), mat_dark)

# --- altazimuth yoke : pivot empty (rotates around Z), holding tube --
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, MOUNT_Z))
azimuth_pivot = bpy.context.active_object
azimuth_pivot.name = "azimuth_pivot"

# yoke body (a small box at the top of the tripod, rotates with azimuth)
yoke = _cyl("yoke_collar", 0.07, 0.07, 0.05, 'Z', (0, 0, 0.03), mat_dark)
yoke.parent = azimuth_pivot
yoke.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# yoke arms : 2 vertical struts forming a U-shape holding the altitude axis
for sy in (-1, 1):
    arm = _box_along(f"yoke_arm_{sy}",
                       (0, sy * 0.10, 0.06),
                       (0.05, sy * 0.10, 0.20),
                       0.015, mat_dark)
    arm.parent = azimuth_pivot
    arm.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- altitude pivot (child of azimuth_pivot, rotates around its own Y) -
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0.05, 0, 0.20))
altitude_pivot = bpy.context.active_object
altitude_pivot.name = "altitude_pivot"
altitude_pivot.parent = azimuth_pivot
altitude_pivot.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- main telescope tube (along altitude_pivot's local +X axis) -------
mesh_tube = bpy.data.meshes.new("main_tube")
tube = bpy.data.objects.new("main_tube", mesh_tube)
bpy.context.collection.objects.link(tube)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32,
                        radius1=0.08, radius2=0.08, depth=0.85)
bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'Y'), verts=bm.verts)
bm.to_mesh(mesh_tube); bm.free()
tube.data.materials.append(mat_tube)
tube.parent = altitude_pivot
tube.matrix_parent_inverse = mathutils.Matrix.Identity(4)
tube.location = (0.20, 0, 0)   # the tube's centre is 0.20 forward of the pivot

# objective lens (glass disc at the front of the tube)
obj_lens = _cyl("objective_lens", 0.075, 0.075, 0.008, 'X', (0.62, 0, 0), mat_glass)
obj_lens.parent = altitude_pivot
obj_lens.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# eyepiece (small dark cylinder at the back, perpendicular to the tube)
eyepiece_base = _cyl("eyepiece_base", 0.035, 0.035, 0.04, 'Z',
                       (-0.20, 0, 0.10), mat_dark)
eyepiece_base.parent = altitude_pivot
eyepiece_base.matrix_parent_inverse = mathutils.Matrix.Identity(4)

eyepiece = _cyl("eyepiece", 0.025, 0.020, 0.06, 'Z', (-0.20, 0, 0.14), mat_brass)
eyepiece.parent = altitude_pivot
eyepiece.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# focus knob (small brass cylinder on the side)
focus_knob = _cyl("focus_knob", 0.022, 0.022, 0.04, 'Y',
                    (-0.20, 0.09, 0.05), mat_brass)
focus_knob.parent = altitude_pivot
focus_knob.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# finder scope (smaller parallel cylinder above)
finder = _cyl("finder_scope", 0.022, 0.022, 0.30, 'X', (0.15, 0, 0.13), mat_tube)
finder.parent = altitude_pivot
finder.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# finder lens (smaller glass disc at the finder's front)
finder_lens = _cyl("finder_lens", 0.021, 0.021, 0.005, 'X', (0.30, 0, 0.13), mat_glass)
finder_lens.parent = altitude_pivot
finder_lens.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 2 finder mounting rings (small brass collars)
for k in (0, 1):
    ring = _cyl(f"finder_ring_{k}", 0.028, 0.028, 0.012, 'X',
                  (0.05 + k * 0.20, 0, 0.13), mat_brass)
    ring.parent = altitude_pivot
    ring.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# counterweight on the back (balances the tube)
cw = _cyl("counterweight", 0.06, 0.06, 0.10, 'X', (-0.45, 0, 0), mat_dark)
cw.parent = altitude_pivot
cw.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation -------------------------------------------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
# Slow sky scan : azimuth sweeps a 90 deg arc, altitude tilts +/- 25 deg
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    azimuth_pivot.rotation_euler = (0, 0, math.sin(2*math.pi*t) * math.radians(45))
    azimuth_pivot.keyframe_insert("rotation_euler", frame=f)

    altitude_pivot.rotation_euler = (0,
                                       math.cos(2*math.pi*t) * math.radians(25),
                                       0)
    altitude_pivot.keyframe_insert("rotation_euler", frame=f)

for o in (azimuth_pivot, altitude_pivot):
    if o.animation_data and o.animation_data.action:
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"TELESCOPE_OK: {out_glb}", flush=True)
'''


def make_telescope(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_tel_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "TELESCOPE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_telescope(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
