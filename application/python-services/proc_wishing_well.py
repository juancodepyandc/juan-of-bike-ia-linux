"""Procedural wishing well (Blender headless).

Stone cylinder base with water inside + 4 wood corner posts + pyramidal
wood-shingle roof + horizontal axle bar + bucket suspended by rope +
crank handle on the side. Animation : crank rotates, axle rotates with
it, bucket bobs up + down.

CLI:
  python proc_wishing_well.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "well.glb"

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

mat_stone   = pbr_mat("stone",     (0.45, 0.42, 0.38), 0.00, 0.85)
mat_wood    = pbr_mat("wood",      (0.30, 0.18, 0.08), 0.00, 0.65)
mat_wood_lt = pbr_mat("wood_lt",   (0.45, 0.28, 0.12), 0.00, 0.60)
mat_water   = pbr_mat("water",     (0.20, 0.45, 0.65), 0.05, 0.15, alpha=0.55)
mat_iron    = pbr_mat("iron",      (0.20, 0.20, 0.22), 0.80, 0.45)
mat_grass   = pbr_mat("grass",     (0.18, 0.30, 0.12), 0.00, 0.85)
mat_rope    = pbr_mat("rope",      (0.55, 0.40, 0.20), 0.00, 0.70)

def _cyl(name, R1, R2, depth, axis, location, mat, segments=20):
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

# --- grass + stone base ----------------------------------
_box("grass", 2.5, 2.5, 0.04, (0, 0, -0.04), mat_grass)

WELL_R = 0.45
WELL_H = 0.40
# wall : 2 concentric cylinders giving a hollow ring (outer + inner-cut)
_cyl("wall_outer", WELL_R, WELL_R, WELL_H, 'Z', (0, 0, WELL_H/2), mat_stone)
# inner cut : a smaller cylinder of slightly different colour (the inside
# of the well) - effectively a dark water surface visible from above
WATER_R = WELL_R * 0.75
_cyl("water_surface", WATER_R, WATER_R, 0.015, 'Z',
       (0, 0, WELL_H * 0.45), mat_water)
# inner stone bottom (a darker disc below the water)
_cyl("inner_bottom", WATER_R, WATER_R, 0.02, 'Z',
       (0, 0, WELL_H * 0.40), mat_stone)

# stone rim (slightly larger disc on top)
_cyl("rim", WELL_R * 1.05, WELL_R * 1.05, 0.04, 'Z',
       (0, 0, WELL_H + 0.02), mat_stone)

# --- 4 wood posts at +/- X (along the axle direction Y) -
POST_H = 0.85
POST_X = WELL_R * 1.05
for sx in (-1, +1):
    _box(f"post_{sx}", 0.06, 0.06, POST_H,
           (sx * POST_X, 0, WELL_H + POST_H/2), mat_wood)
# top crossbeam connecting the 2 posts (along X)
TOP_Z = WELL_H + POST_H
_box("top_beam", POST_X * 2 + 0.10, 0.08, 0.06, (0, 0, TOP_Z + 0.03), mat_wood)

# --- pyramidal shingle roof (a tall narrow box rotated 45 deg)
# simpler : 2 sloped boxes forming a triangular prism
ROOF_Z = TOP_Z + 0.18
for sy in (-1, +1):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, ROOF_Z))
    r = bpy.context.active_object
    r.name = f"roof_{sy}"
    r.scale = (POST_X * 2 + 0.20, 0.04, 0.42)
    bpy.ops.object.transform_apply(scale=True)
    r.rotation_euler = (sy * math.radians(25), 0, 0)
    r.location = (0, sy * 0.10, ROOF_Z)
    r.data.materials.append(mat_wood_lt)

# --- crank pivot (axle) : an empty at the centre of the top beam
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, TOP_Z))
crank_pivot = bpy.context.active_object
crank_pivot.name = "crank_pivot"

# axle cylinder running along X
axle = _cyl("axle", 0.04, 0.04, POST_X * 2, 'X', (0, 0, 0), mat_wood_lt)
axle.parent = crank_pivot
axle.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# crank handle (L-shape : short post + perpendicular grip) at one side
handle_x = POST_X + 0.08
handle_offset_y = 0.10  # the handle sticks out radially from the axle
handle = _cyl("crank_arm", 0.02, 0.02, handle_offset_y, 'Y',
                (handle_x, handle_offset_y/2, 0), mat_iron)
handle.parent = crank_pivot
handle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
grip = _cyl("crank_grip", 0.025, 0.025, 0.08, 'X',
             (handle_x + 0.04, handle_offset_y, 0), mat_wood)
grip.parent = crank_pivot
grip.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- rope + bucket : the bucket hangs below the axle, ----
# rope length varies with crank rotation
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, TOP_Z))
bucket_pivot = bpy.context.active_object
bucket_pivot.name = "bucket_pivot"

# rope (thin vertical cylinder)
rope = _box("rope", 0.008, 0.008, 0.60, (0, 0, -0.30), mat_rope)
rope.parent = bucket_pivot
rope.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# bucket (small open cylinder with bottom)
bucket_body = _cyl("bucket", 0.07, 0.06, 0.10, 'Z', (0, 0, -0.65), mat_iron)
bucket_body.parent = bucket_pivot
bucket_body.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# bucket handle (small wire loop above)
bucket_handle = _box("bucket_handle", 0.005, 0.10, 0.005,
                       (0, 0, -0.58), mat_iron)
bucket_handle.parent = bucket_pivot
bucket_handle.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ------------------------------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# crank rotates 1 full turn per loop around X
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    crank_pivot.rotation_euler = (2 * math.pi * t, 0, 0)
    crank_pivot.keyframe_insert("rotation_euler", frame=f)
if crank_pivot.animation_data and crank_pivot.animation_data.action:
    for fc in crank_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# bucket : Z position oscillates +/- 0.20 m so it appears to dip into the
# well water and come back up
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    z_off = -0.20 * (0.5 + 0.5 * math.sin(2*math.pi*t))  # 0 .. -0.20
    bucket_pivot.location = (0, 0, TOP_Z + z_off)
    bucket_pivot.keyframe_insert("location", frame=f)
if bucket_pivot.animation_data and bucket_pivot.animation_data.action:
    for fc in bucket_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"WELL_OK: {out_glb}", flush=True)
'''


def make_well(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_well_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "WELL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_well(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
