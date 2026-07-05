"""Procedural DSLR camera (Blender headless).

Black plastic body with right-hand grip + telescoping zoom lens (mount +
3 rings + glass element) + rear LCD screen (emissive, cycling colours)
+ top viewfinder prism hump + pop-up flash + 2 chrome control buttons +
mode dial + a short shoulder strap loop on each side. Animation : lens
extends / retracts (zoom-in / zoom-out, scale along Y) + LCD cycles
hue (preview-image flicker) + flash fires briefly mid-loop.

CLI:
  python proc_dslr_camera.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "dslr.glb"

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

mat_floor   = pbr_mat("floor",     (0.18, 0.18, 0.20), 0.00, 0.85)
mat_body    = pbr_mat("body",      (0.08, 0.08, 0.09), 0.10, 0.45)
mat_body_t  = pbr_mat("body_text", (0.04, 0.04, 0.05), 0.10, 0.70)  # textured grip
mat_chrome  = pbr_mat("chrome",    (0.78, 0.80, 0.83), 1.00, 0.18)
mat_red_dot = pbr_mat("red_dot",   (0.95, 0.10, 0.10), 0.00, 0.20)
mat_lens    = pbr_mat("lens",      (0.06, 0.06, 0.08), 0.30, 0.35)
mat_lens_rg = pbr_mat("lens_rng",  (0.10, 0.10, 0.11), 0.85, 0.25)
mat_lens_g  = pbr_mat("lens_glass",(0.10, 0.18, 0.25), 0.00, 0.10, alpha=0.55)
mat_lcd     = pbr_mat("lcd",       (0.05, 0.05, 0.08), 0.00, 0.10,
                          emission=((0.30, 0.50, 1.00), 3.0))
mat_button  = pbr_mat("button",    (0.50, 0.50, 0.55), 0.80, 0.30)
mat_strap   = pbr_mat("strap",     (0.10, 0.07, 0.05), 0.05, 0.65)
mat_flash   = pbr_mat("flash",     (0.92, 0.92, 0.95), 0.00, 0.20,
                          emission=((1.00, 0.98, 0.92), 0.0))

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

# Conventions : camera body roughly faces -Y (lens points along -Y, photographer
# stands at +Y). Up is +Z.

# --- floor ---------------------------------------------
_box("floor", 1.5, 1.5, 0.04, (0, 0, -0.04), mat_floor)

# --- main body block ----------------------------------
BODY_W = 0.16
BODY_D = 0.08
BODY_H = 0.10
BODY_Z = 0.05 + BODY_H/2
_box("body", BODY_W, BODY_D, BODY_H, (0, 0, BODY_Z), mat_body)

# right-hand grip (a slightly taller block on the +X side)
GRIP_W = 0.05
GRIP_X = BODY_W/2 + GRIP_W/2 - 0.005
_box("grip", GRIP_W, BODY_D * 1.1, BODY_H * 1.10,
       (GRIP_X, 0.005, BODY_Z), mat_body_t)
# leatherette panel on the front of the grip
_box("grip_panel", 0.012, BODY_D * 0.85, BODY_H * 0.90,
       (GRIP_X + GRIP_W/2 - 0.006, -BODY_D/2 + 0.02, BODY_Z), mat_body_t)

# small red accent line at the bottom-right corner (brand colour)
_box("red_accent", 0.018, 0.004, 0.014,
       (GRIP_X + GRIP_W/2 - 0.012, -BODY_D/2 + 0.001, BODY_Z + BODY_H/2 - 0.018),
       mat_red_dot)

# --- viewfinder prism hump on top --------------------
HUMP_W = 0.05
HUMP_D = BODY_D * 0.85
HUMP_H = 0.025
HUMP_Z = BODY_Z + BODY_H/2 + HUMP_H/2
_box("prism", HUMP_W, HUMP_D, HUMP_H, (-0.02, 0, HUMP_Z), mat_body)
# brand label (a tiny chrome strip on the front of the hump)
_box("brand_label", 0.025, 0.002, 0.006,
       (-0.02, -HUMP_D/2 - 0.001, HUMP_Z), mat_chrome)
# hot shoe (a small chrome U-shape on top of the hump)
_box("shoe_base", 0.025, 0.022, 0.004,
       (-0.02, 0, HUMP_Z + HUMP_H/2 + 0.002), mat_chrome)
for sy in (-1, +1):
    _box(f"shoe_rail_{sy}", 0.025, 0.003, 0.008,
           (-0.02, sy * 0.011, HUMP_Z + HUMP_H/2 + 0.008), mat_chrome)

# pop-up flash (a small box on the back-left of the hump that "fires"
# by pulsing the emission of mat_flash)
_box("flash_unit", 0.030, 0.018, 0.012,
       (-0.06, 0, HUMP_Z + 0.005), mat_flash)

# --- mode dial on top-right ------------------------
DIAL_X = GRIP_X - 0.003
DIAL_Z = BODY_Z + BODY_H/2 + 0.006
_cyl("mode_dial", 0.018, 0.018, 0.012, 'Z', (DIAL_X, 0.01, DIAL_Z), mat_body)
_cyl("mode_dial_top", 0.018, 0.016, 0.003, 'Z',
       (DIAL_X, 0.01, DIAL_Z + 0.0075), mat_chrome)

# shutter release button (slightly forward of the dial, on the grip top)
_cyl("shutter_btn", 0.008, 0.008, 0.005, 'Z',
       (GRIP_X, -BODY_D/2 + 0.018, DIAL_Z + 0.003), mat_button)

# secondary control button on the top-left
_cyl("ctrl_btn_2", 0.006, 0.006, 0.004, 'Z',
       (-0.06, 0.02, BODY_Z + BODY_H/2 + 0.002), mat_button)

# --- LCD screen on the back of the body ----------
LCD_W = BODY_W * 0.70
LCD_H = BODY_H * 0.72
_box("lcd_frame", LCD_W + 0.005, 0.004, LCD_H + 0.005,
       (0.005, BODY_D/2 + 0.002, BODY_Z), mat_body)
_box("lcd", LCD_W, 0.0015, LCD_H,
       (0.005, BODY_D/2 + 0.0044, BODY_Z), mat_lcd)
# 4 small buttons to the right of the LCD
for k in range(4):
    bz = BODY_Z + LCD_H/2 - 0.012 - k * 0.018
    _cyl(f"lcd_btn_{k}", 0.005, 0.005, 0.004, 'Y',
           (BODY_W/2 - 0.015, BODY_D/2 + 0.002, bz), mat_button)

# --- lens : mount + 3 telescoping rings + glass ---
# Lens points along -Y. Build it as a parent empty so we can animate the
# extension distance by scaling the empty's Y. The rings overlap a little
# so the result looks like a sliding zoom lens.

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(-0.02, -BODY_D/2 - 0.001, BODY_Z))
lens = bpy.context.active_object
lens.name = "lens"

# mount ring (sits against the body face)
mount = _cyl("lens_mount", 0.030, 0.030, 0.012, 'Y',
               (0, -0.006, 0), mat_lens_rg, segments=28)
mount.parent = lens; mount.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# release button (small red square on the mount)
_box("lens_release", 0.005, 0.004, 0.005, (0.030, -0.006, 0), mat_red_dot)

# ring 1 (closest to body, widest)
r1 = _cyl("lens_r1", 0.028, 0.026, 0.022, 'Y',
            (0, -0.022, 0), mat_lens, segments=28)
r1.parent = lens; r1.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# ridged grip texture on ring 1 (4 grooves)
for k in range(4):
    g = _cyl(f"r1_groove_{k}", 0.029, 0.029, 0.0015, 'Y',
               (0, -0.013 - k * 0.005, 0), mat_lens_rg, segments=28)
    g.parent = lens; g.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# ring 2 (zoom ring, middle)
r2 = _cyl("lens_r2", 0.026, 0.024, 0.022, 'Y',
            (0, -0.043, 0), mat_lens, segments=28)
r2.parent = lens; r2.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# focus ring 3 (front, narrowest)
r3 = _cyl("lens_r3", 0.024, 0.022, 0.020, 'Y',
            (0, -0.064, 0), mat_lens, segments=28)
r3.parent = lens; r3.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# front bezel (chrome rim)
bz = _cyl("lens_bezel", 0.023, 0.023, 0.003, 'Y',
            (0, -0.075, 0), mat_chrome, segments=28)
bz.parent = lens; bz.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# lens glass element (translucent blue disc at the front)
gl = _cyl("lens_glass", 0.020, 0.020, 0.004, 'Y',
            (0, -0.077, 0), mat_lens_g, segments=28)
gl.parent = lens; gl.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- strap loops (2 small "D-rings" on either side of the body) ---
for sx in (-1, +1):
    loop = _cyl(f"strap_loop_{sx}", 0.008, 0.008, 0.002, 'X',
                  (sx * (BODY_W/2 + 0.004), 0.005, BODY_Z + BODY_H/2 - 0.005),
                  mat_chrome)
# short black strap on each side (just a hint, not a full strap)
for sx in (-1, +1):
    _box(f"strap_{sx}", 0.005, 0.015, 0.04,
           (sx * (BODY_W/2 + 0.008), 0.005, BODY_Z + BODY_H/2 - 0.025),
           mat_strap)

# --- animation -------------------------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Lens zooms : scale.y oscillates 1.0 .. 1.7 .. 1.0 over the loop.
# We scale the lens empty, which propagates to all its children. Since
# children are positioned at negative Y offsets, scaling Y > 1 extends
# them outward (i.e. lens grows toward -Y). The mount ring (closest to
# y=0) stays mostly attached to the body face.
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    s = 1.0 + 0.7 * (0.5 - 0.5 * math.cos(2*math.pi*t))
    lens.scale = (1.0, s, 1.0)
    lens.keyframe_insert("scale", frame=f)
if lens.animation_data and lens.animation_data.action:
    for fc in lens.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# LCD cycles colour (preview-image effect) — cycle through 5 colours
bsdf_lcd = mat_lcd.node_tree.nodes.get("Principled BSDF")
em_col = bsdf_lcd.inputs["Emission Color"]
em_str = bsdf_lcd.inputs["Emission Strength"]
COLORS = [
    (0.30, 0.50, 1.00),
    (1.00, 0.45, 0.20),
    (0.30, 1.00, 0.45),
    (1.00, 0.20, 0.55),
    (1.00, 0.85, 0.30),
]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    idx = int(t * len(COLORS)) % len(COLORS)
    em_col.default_value = (*COLORS[idx], 1.0)
    em_str.default_value = 2.5 + 1.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 8))
    bpy.context.scene.frame_set(f)
    em_col.keyframe_insert(data_path="default_value", frame=f)
    em_str.keyframe_insert(data_path="default_value", frame=f)

# Flash : 50 ms emission burst mid-loop (t = 0.5 .. 0.55)
bsdf_fl = mat_flash.node_tree.nodes.get("Principled BSDF")
fl_str = bsdf_fl.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    if 0.50 <= t <= 0.55:
        phase = (t - 0.50) / 0.05  # 0..1
        # triangle pulse
        val = 30.0 * (1.0 - abs(2.0*phase - 1.0))
    else:
        val = 0.0
    fl_str.default_value = val
    bpy.context.scene.frame_set(f)
    fl_str.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"DSLR_OK: {out_glb}", flush=True)
'''


def make_dslr(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_dslr_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "DSLR_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_dslr(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
