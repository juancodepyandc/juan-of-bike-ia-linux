"""Procedural mill water wheel (Blender headless).

Wood frame + horizontal axle + spoked wheel with 12 paddles + cascading
water stream from above. Animation : wheel rotates continuously, water
falls in a perpetual stream.

CLI:
  python proc_water_wheel.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "wheel.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough, alpha=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if alpha is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
            m.blend_method = 'BLEND'
    return m

mat_wood     = pbr_mat("wood",       (0.32, 0.18, 0.08), 0.00, 0.65)
mat_wood_dk  = pbr_mat("wood_dark",  (0.20, 0.10, 0.05), 0.00, 0.70)
mat_paddle   = pbr_mat("paddle",     (0.45, 0.28, 0.12), 0.00, 0.60)
mat_axle     = pbr_mat("axle_steel", (0.45, 0.42, 0.40), 0.80, 0.45)
mat_water    = pbr_mat("water",      (0.40, 0.60, 0.85), 0.05, 0.15, alpha=0.45)
mat_stone    = pbr_mat("stone",      (0.40, 0.40, 0.42), 0.00, 0.85)
mat_grass    = pbr_mat("grass",      (0.18, 0.30, 0.12), 0.00, 0.85)

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

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

# --- grass ground ------------------------------------------
_box("grass_ground", 3.5, 3.0, 0.04, (0, 0, -0.04), mat_grass)

# --- stone river bed under the wheel ----------------------
_box("river_bed", 0.85, 1.2, 0.02, (0, 0, 0.01), mat_stone)

# --- 2 wood support posts on each side of the wheel -------
WHEEL_R = 0.85
WHEEL_Y = 0  # along world Y axis (axle direction)
WHEEL_Z = WHEEL_R + 0.05
POST_HALF_Y = 0.50
for sy in (-1, +1):
    _box(f"post_{sy}", 0.10, 0.06, WHEEL_Z + 0.20,
           (0, sy * POST_HALF_Y, (WHEEL_Z + 0.20)/2), mat_wood_dk)
# top crossbeam
_box("top_beam", 0.40, POST_HALF_Y * 2 + 0.10, 0.06,
       (0, 0, WHEEL_Z + 0.20 + 0.03), mat_wood_dk)

# --- axle (horizontal cylinder along Y, parented to the wheel pivot)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, WHEEL_Z))
wheel_pivot = bpy.context.active_object
wheel_pivot.name = "wheel_pivot"

axle = _cyl("axle", 0.05, 0.05, POST_HALF_Y * 2 + 0.05, 'Y', (0, 0, 0), mat_axle)
axle.parent = wheel_pivot
axle.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 2 wheel discs (one near each side) + rim torus -----
for sy_disc in (-1, +1):
    disc = _cyl(f"wheel_disc_{sy_disc}", WHEEL_R, WHEEL_R, 0.03, 'Y',
                  (0, sy_disc * (POST_HALF_Y * 0.65), 0), mat_wood)
    disc.parent = wheel_pivot
    disc.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # 8 spokes per disc
    for k in range(8):
        a = k * math.pi / 4
        sx_end = math.cos(a) * (WHEEL_R * 0.95)
        sz_end = math.sin(a) * (WHEEL_R * 0.95)
        bpy.ops.mesh.primitive_cube_add(size=1,
            location=(sx_end/2, sy_disc * (POST_HALF_Y * 0.65), sz_end/2))
        s = bpy.context.active_object
        s.name = f"spoke_{sy_disc}_{k}"
        s.scale = (math.hypot(sx_end, sz_end) * 1.05, 0.020, 0.020)
        bpy.ops.object.transform_apply(scale=True)
        s.rotation_euler = (0, -math.atan2(sz_end, sx_end), 0)
        s.data.materials.append(mat_wood_dk)
        s.parent = wheel_pivot
        s.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 12 paddles around the rim (boxes spanning both wheel discs) ----
N_PAD = 12
PAD_W = POST_HALF_Y * 2 * 0.75
PAD_T = 0.04
PAD_H = 0.14
for k in range(N_PAD):
    a = k * 2 * math.pi / N_PAD
    px = math.cos(a) * (WHEEL_R - 0.02)
    pz = math.sin(a) * (WHEEL_R - 0.02)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(px, 0, pz))
    p = bpy.context.active_object
    p.name = f"paddle_{k}"
    p.scale = (PAD_H, PAD_W, PAD_T)
    bpy.ops.object.transform_apply(scale=True)
    # rotate paddle so its long face points outward
    p.rotation_euler = (0, -a, 0)
    p.data.materials.append(mat_paddle)
    p.parent = wheel_pivot
    p.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- water cascade : a translucent rectangular sheet --------
# Falls from the top crossbeam down past the upper paddles, into a
# pool below.
_box("water_fall", 0.18, POST_HALF_Y * 1.6, 1.50,
       (-WHEEL_R + 0.05, 0, WHEEL_Z + 0.20 - 1.50/2 - 0.10),
       mat_water)

# splash pool at the base (a thin water disc)
_cyl("pool", 0.75, 0.65, 0.04, 'Z', (-0.05, 0, 0.04), mat_water)

# --- animation : wheel rotates around Y axis --------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # 1 turn per loop (slow), rotating in +X direction (paddles cup the
    # falling water on the left side)
    wheel_pivot.rotation_euler = (0, 2 * math.pi * t, 0)
    wheel_pivot.keyframe_insert("rotation_euler", frame=f)
if wheel_pivot.animation_data and wheel_pivot.animation_data.action:
    for fc in wheel_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"WHEEL_OK: {out_glb}", flush=True)
'''


def make_wheel(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_ww_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "WHEEL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_wheel(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
