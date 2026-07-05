"""Procedural playground slide (Blender headless).

Vertical ladder (2 rails + 5 rungs) leading to a wooden platform at the
top, then a curved slide (6 arc panels) descending to a flat run-out at
ground level. Plus side rails on the platform, 2 handle bars at the top
of the ladder, and a sand patch underneath. Animation : a small colored
ball slides from the top of the ladder, across the platform, and down
the slide following the arc to the bottom.

CLI:
  python proc_playground_slide.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "slide.glb"

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

mat_grass    = pbr_mat("grass",     (0.20, 0.45, 0.18), 0.00, 0.85)
mat_sand     = pbr_mat("sand",      (0.85, 0.78, 0.55), 0.00, 0.85)
mat_steel    = pbr_mat("steel",     (0.55, 0.55, 0.58), 0.85, 0.30)
mat_wood     = pbr_mat("wood",      (0.55, 0.32, 0.16), 0.05, 0.55)
mat_wood_lt  = pbr_mat("wood_lt",   (0.75, 0.45, 0.20), 0.05, 0.50)
mat_red      = pbr_mat("red",       (0.85, 0.18, 0.12), 0.10, 0.40)
mat_blue     = pbr_mat("blue",      (0.20, 0.50, 0.92), 0.10, 0.40)
mat_yellow   = pbr_mat("yellow",    (0.95, 0.85, 0.20), 0.10, 0.40)
mat_dark     = pbr_mat("dark",      (0.08, 0.08, 0.09), 0.30, 0.45)

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

# Conventions : ladder on -Y end, platform on top, slide descending toward +Y.
# Up = +Z.

# --- ground -----------------------
_box("floor", 4.0, 5.5, 0.04, (0, 0, -0.04), mat_grass)
_box("sand_patch", 1.6, 4.0, 0.025, (0, 0.5, 0.013), mat_sand)

# --- ladder on -Y side -----------
LADDER_Y = -1.20
LADDER_W = 0.45
LADDER_H = 1.60
PLAT_Z = 1.60
for sx in (-1, +1):
    _cyl(f"ladder_rail_{sx}", 0.025, 0.025, LADDER_H, 'Z',
           (sx * LADDER_W/2, LADDER_Y, PLAT_Z - LADDER_H/2 + 0.05),
           mat_steel, segments=12)
# 5 rungs
for k in range(5):
    rz = 0.30 + k * (PLAT_Z - 0.30) / 4
    _cyl(f"ladder_rung_{k}", 0.015, 0.015, LADDER_W, 'X',
           (0, LADDER_Y, rz), mat_steel, segments=10)

# --- platform top (wooden deck) ---
PLAT_W = 0.60
PLAT_D = 0.80
PLAT_Y = -0.80
_box("platform", PLAT_W, PLAT_D, 0.04,
       (0, PLAT_Y, PLAT_Z), mat_wood)
# 4 support legs for the platform
for sx in (-1, +1):
    for sy in (-1, +1):
        _cyl(f"plat_leg_{sx}_{sy}", 0.025, 0.025, PLAT_Z, 'Z',
               (sx * (PLAT_W/2 - 0.03), PLAT_Y + sy * (PLAT_D/2 - 0.05),
                PLAT_Z/2),
               mat_steel, segments=10)

# --- side guard rails on the platform (left + right + back, NOT front toward
# slide entry) ---
RAIL_H = 0.45
for sx in (-1, +1):
    _cyl(f"plat_rail_top_{sx}", 0.020, 0.020, PLAT_D + 0.04, 'Y',
           (sx * (PLAT_W/2 - 0.02), PLAT_Y, PLAT_Z + RAIL_H), mat_steel)
    _cyl(f"plat_post_back_{sx}", 0.022, 0.022, RAIL_H, 'Z',
           (sx * (PLAT_W/2 - 0.02), PLAT_Y - PLAT_D/2 + 0.02, PLAT_Z + RAIL_H/2),
           mat_steel)
    _cyl(f"plat_post_front_{sx}", 0.022, 0.022, RAIL_H, 'Z',
           (sx * (PLAT_W/2 - 0.02), PLAT_Y + PLAT_D/2 - 0.02, PLAT_Z + RAIL_H/2),
           mat_steel)
# back rail
_cyl("plat_rail_back", 0.020, 0.020, PLAT_W, 'X',
       (0, PLAT_Y - PLAT_D/2 + 0.02, PLAT_Z + RAIL_H), mat_steel)

# 2 handle bars at the top of the ladder (for kids to grab as they step up)
for sx in (-1, +1):
    _cyl(f"handle_bar_{sx}", 0.018, 0.018, 0.30, 'Y',
           (sx * LADDER_W/2, LADDER_Y + 0.10, PLAT_Z + 0.20), mat_yellow)
    # vertical post connecting handle to platform rail
    _cyl(f"handle_post_{sx}", 0.018, 0.018, 0.20, 'Z',
           (sx * LADDER_W/2, LADDER_Y + 0.20, PLAT_Z + 0.10), mat_yellow)

# --- slide : curve descending from front of platform (+Y side) to ground ---
# Parametric : the slide is a curved surface. Build it as 8 arc panels.
SLIDE_R = 1.40  # radius of curvature
SLIDE_W = 0.50
SLIDE_TOP_Y = PLAT_Y + PLAT_D/2
SLIDE_TOP_Z = PLAT_Z
# Center of the curvature : behind and below the bottom of the slide
# We want the slide to start tangent to the platform (horizontal at top) and
# end tangent to the ground (horizontal at bottom). So it's a quarter arc.
N_PANELS = 8
slide_color = mat_red
for i in range(N_PANELS):
    a0 = (math.pi/2) * i / N_PANELS
    a1 = (math.pi/2) * (i + 1) / N_PANELS
    am = (a0 + a1) / 2
    # position on the quarter arc (measured from horizontal at top)
    # the center of the arc is at (0, SLIDE_TOP_Y + SLIDE_R, SLIDE_TOP_Z - SLIDE_R)? Actually
    # we want : at i=0 (a=0), the panel is at the top edge of the platform,
    # tangent horizontal. At i=N (a=pi/2), the panel is at the ground level.
    # Center of curvature : (0, SLIDE_TOP_Y, SLIDE_TOP_Z - SLIDE_R)
    cy = 0  # x is unused along the slide
    yc = SLIDE_TOP_Y + SLIDE_R * math.sin(am)
    zc = SLIDE_TOP_Z - SLIDE_R + SLIDE_R * math.cos(am)
    panel_len = SLIDE_R * (math.pi/2) / N_PANELS * 1.05
    panel = _box(f"slide_panel_{i}", SLIDE_W, panel_len, 0.025,
                   (0, yc, zc), slide_color,
                   rot=(am, 0, 0))
# 2 side walls of the slide (small lateral rails, also red, curved)
for sx in (-1, +1):
    for i in range(N_PANELS):
        a0 = (math.pi/2) * i / N_PANELS
        a1 = (math.pi/2) * (i + 1) / N_PANELS
        am = (a0 + a1) / 2
        yc = SLIDE_TOP_Y + SLIDE_R * math.sin(am)
        zc = SLIDE_TOP_Z - SLIDE_R + SLIDE_R * math.cos(am)
        panel_len = SLIDE_R * (math.pi/2) / N_PANELS * 1.05
        _box(f"slide_wall_{sx}_{i}", 0.025, panel_len, 0.12,
               (sx * SLIDE_W/2, yc, zc + 0.07), slide_color,
               rot=(am, 0, 0))

# flat run-out at the bottom (red slab, ~30 cm extension)
RUNOUT_Y = SLIDE_TOP_Y + SLIDE_R + 0.15
_box("slide_runout", SLIDE_W, 0.40, 0.025,
       (0, RUNOUT_Y, 0.04), slide_color)
for sx in (-1, +1):
    _box(f"runout_wall_{sx}", 0.025, 0.40, 0.10,
           (sx * SLIDE_W/2, RUNOUT_Y, 0.085), slide_color)

# --- toy ball (animated) ----
BALL_R = 0.08
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, PLAT_Y, PLAT_Z + BALL_R))
ball_pivot = bpy.context.active_object
ball_pivot.name = "ball_pivot"
ball = _sphere("ball", BALL_R, (0, 0, 0), mat_blue, u=16, v=12)
ball.parent = ball_pivot
ball.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# yellow stripe (a thin ring across the ball)
stripe = _cyl("ball_stripe", BALL_R * 0.98, BALL_R * 0.98, 0.020, 'Z',
                (0, 0, 0), mat_yellow, segments=14)
stripe.parent = ball_pivot
stripe.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : ball travels platform → top of slide → down the curve → runout ---
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

def ball_pose(t):
    """t in [0,1]. Returns (y, z, rot_x_around_X) for ball traversing the slide."""
    if t < 0.20:
        # roll across platform toward the slide entry
        u = t / 0.20
        y = PLAT_Y + u * (SLIDE_TOP_Y - PLAT_Y)
        z = PLAT_Z + BALL_R + 0.04 / 2
        return y, z, 0
    elif t < 0.85:
        # slide down the curve
        u = (t - 0.20) / 0.65
        # ease-in : ball accelerates as it goes down
        u_smooth = u * u
        a = (math.pi/2) * u_smooth
        y = SLIDE_TOP_Y + SLIDE_R * math.sin(a)
        z = SLIDE_TOP_Z - SLIDE_R + SLIDE_R * math.cos(a) + BALL_R + 0.04
        # ball rolls along the slide surface — rotation around X
        return y, z, -a * 4
    else:
        # roll along the runout to the end
        u = (t - 0.85) / 0.15
        y0 = SLIDE_TOP_Y + SLIDE_R
        y1 = RUNOUT_Y + 0.10
        y = y0 + u * (y1 - y0)
        z = 0.04 + BALL_R + 0.025
        return y, z, -math.pi/2 * 4 - u * 6.28

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    y, z, rot_x = ball_pose(t)
    bpy.context.scene.frame_set(f)
    ball_pivot.location = (0, y, z)
    ball_pivot.rotation_euler = (rot_x, 0, 0)
    ball_pivot.keyframe_insert("location", frame=f)
    ball_pivot.keyframe_insert("rotation_euler", frame=f)
if ball_pivot.animation_data and ball_pivot.animation_data.action:
    for fc in ball_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SLIDE_OK: {out_glb}", flush=True)
'''


def make_slide(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_slide_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SLIDE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_slide(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
