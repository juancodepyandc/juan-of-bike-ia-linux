"""Procedural hourglass with animated sand flow (Blender headless).

Wooden frame + 2 glass bulbs (upper + lower, joined by a narrow neck) +
sand inside both bulbs (a cone in each) + a thin falling-sand stream
through the neck. Animation : the upper sand cone shrinks (Z scale and
location keyframes) while the lower one grows ; the stream stays
visible the whole loop. When the upper bulb empties, the loop restarts.

CLI:
  python proc_hourglass.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "hourglass.glb"

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

mat_wood     = pbr_mat("wood_frame", (0.40, 0.25, 0.10), 0.00, 0.65)
mat_glass    = pbr_mat("bulb_glass", (0.90, 0.92, 0.94), 0.00, 0.05)
# Make glass translucent : Alpha=0.25 + blend BLEND mode
_bsdf = mat_glass.node_tree.nodes.get("Principled BSDF")
if _bsdf and "Alpha" in _bsdf.inputs:
    _bsdf.inputs["Alpha"].default_value = 0.25
mat_glass.blend_method = 'BLEND'
mat_sand     = pbr_mat("sand_gold",  (0.90, 0.70, 0.30), 0.10, 0.55)
mat_table    = pbr_mat("table_dark", (0.20, 0.16, 0.10), 0.00, 0.80)

def _cyl(name, R1, R2, depth, axis, location, mat, segments=32):
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

# --- table top ---------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.025))
table = bpy.context.active_object
table.name = "table"
table.scale = (1.4, 1.4, 0.05)
bpy.ops.object.transform_apply(scale=True)
table.data.materials.append(mat_table)

# --- frame plates (top + bottom of the hourglass case) ----------------
FRAME_HALF_W = 0.32   # width of the top/bottom wooden plates
FRAME_HALF_D = 0.32
TOP_Z = 1.05
BOT_Z = 0.10
PLATE_T = 0.04

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, BOT_Z))
bot = bpy.context.active_object; bot.name = "frame_bottom"
bot.scale = (FRAME_HALF_W * 2, FRAME_HALF_D * 2, PLATE_T)
bpy.ops.object.transform_apply(scale=True)
bot.data.materials.append(mat_wood)

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, TOP_Z))
top = bpy.context.active_object; top.name = "frame_top"
top.scale = (FRAME_HALF_W * 2, FRAME_HALF_D * 2, PLATE_T)
bpy.ops.object.transform_apply(scale=True)
top.data.materials.append(mat_wood)

# 4 vertical posts at the corners
post_h = TOP_Z - BOT_Z - PLATE_T
for sx in (-1, 1):
    for sy in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=1,
            location=(sx * (FRAME_HALF_W - 0.04), sy * (FRAME_HALF_D - 0.04),
                       (TOP_Z + BOT_Z) / 2))
        p = bpy.context.active_object
        p.name = f"post_{sx}_{sy}"
        p.scale = (0.04, 0.04, post_h)
        bpy.ops.object.transform_apply(scale=True)
        p.data.materials.append(mat_wood)

# --- glass bulbs : 2 conic shapes meeting at the neck ----------------
NECK_Z = (TOP_Z + BOT_Z) / 2
BULB_R = 0.20
NECK_R = 0.025

# Upper bulb : cone tapering from BULB_R (top) to NECK_R (neck)
upper_bulb_h = (TOP_Z - PLATE_T/2) - NECK_Z - 0.01
_cyl("upper_bulb_glass", BULB_R, NECK_R, upper_bulb_h, 'Z',
       (0, 0, NECK_Z + upper_bulb_h / 2 + 0.005), mat_glass)

# Lower bulb : cone tapering from NECK_R (neck) to BULB_R (bottom)
lower_bulb_h = NECK_Z - (BOT_Z + PLATE_T/2) - 0.01
_cyl("lower_bulb_glass", NECK_R, BULB_R, lower_bulb_h, 'Z',
       (0, 0, NECK_Z - lower_bulb_h / 2 - 0.005), mat_glass)

# Neck (very short narrow cylinder where the two bulbs meet)
_cyl("neck_glass", NECK_R, NECK_R, 0.025, 'Z',
       (0, 0, NECK_Z), mat_glass)

# --- sand ------------------------------------------------------------
# Upper sand cone : sits inside the upper bulb, animated to shrink.
# We build it slightly smaller than the bulb so it's visible inside.
SAND_TOP_R = BULB_R * 0.92
upper_sand = _cyl("upper_sand", SAND_TOP_R, NECK_R * 1.5, upper_bulb_h * 0.95,
                    'Z', (0, 0, NECK_Z + upper_bulb_h / 2 + 0.005),
                    mat_sand)

# Lower sand cone : inverted (small radius at top, big at bottom), starts small
SAND_BOT_R = BULB_R * 0.92
lower_sand = _cyl("lower_sand", NECK_R * 1.5, SAND_BOT_R, lower_bulb_h * 0.95,
                    'Z', (0, 0, NECK_Z - lower_bulb_h / 2 - 0.005),
                    mat_sand)

# Stream : thin sand cylinder through the neck (constant)
_cyl("sand_stream", 0.004, 0.004, 0.30, 'Z',
       (0, 0, NECK_Z - 0.05), mat_sand)

# --- animation -------------------------------------------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
# Linear drain : t=0 -> upper full, lower empty.  t=1 -> upper empty, lower full.
# The upper sand cone shrinks via Z scale (anchored at its bottom near the neck).
# The lower sand grows via Z scale (anchored at its bottom on the bulb floor).
#
# We achieve "anchored bottom" by also keyframing location.z so the mesh stays
# attached to its anchor : the upper sand's local pivot is at its centre, so
# as Z-scale shrinks, the top moves DOWN by (scale - 1) * height / 2 ; we need
# to also LOWER the cone by the same amount to keep its bottom at the neck.

# Actually simpler : just animate location.z so the upper cone "drops" toward
# the neck as it shrinks. Same for lower cone : as it grows, its centre rises.
UH = upper_bulb_h * 0.95
LH = lower_bulb_h * 0.95
UPPER_BASE_Z = NECK_Z + upper_bulb_h / 2 + 0.005   # initial centre of upper
LOWER_BASE_Z = NECK_Z - lower_bulb_h / 2 - 0.005   # initial centre of lower

for f in range(1, NFR + 1, KEY_EVERY):
    raw_t = (f - 1) / NFR
    # cyclic loop : 0 -> 1 -> reset to 0
    t = raw_t                                  # 0..1 -> drains over the loop
    bpy.context.scene.frame_set(f)

    # Upper sand shrinks Z to (1 - t).  Anchor its bottom (near the neck).
    s_upper = max(0.001, 1 - t)
    upper_sand.scale = (1, 1, s_upper)
    # New height = UH * s_upper.  Bottom should remain at (NECK_Z + 0.01).
    # Centre Z = bottom + UH * s_upper / 2
    upper_sand.location.z = NECK_Z + 0.01 + UH * s_upper / 2
    upper_sand.keyframe_insert("scale", frame=f)
    upper_sand.keyframe_insert("location", frame=f)

    # Lower sand grows Z to t.  Anchor its TOP near the neck.
    s_lower = max(0.001, t)
    lower_sand.scale = (1, 1, s_lower)
    # New height = LH * s_lower.  Top should remain at (NECK_Z - 0.01).
    # Centre Z = top - LH * s_lower / 2
    lower_sand.location.z = NECK_Z - 0.01 - LH * s_lower / 2
    lower_sand.keyframe_insert("scale", frame=f)
    lower_sand.keyframe_insert("location", frame=f)

for o in (upper_sand, lower_sand):
    if o.animation_data and o.animation_data.action:
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"HOURGLASS_OK: {out_glb}", flush=True)
'''


def make_hourglass(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_hg_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "HOURGLASS_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_hourglass(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
