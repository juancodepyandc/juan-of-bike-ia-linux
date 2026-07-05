"""Procedural Italian espresso machine (Blender headless).

Polished stainless body + 2 round group-head boilers + portafilter with
2-spout + steam wand pivoting on the right + pressure gauge with a
needle + 2 illuminated buttons + cup grille + drip tray + ceramic
demitasse + saucer below the spouts. Animation : espresso stream pours
into the cup (a brown emissive cylinder scales Z), the manometer needle
sweeps from rest to 9 bar, steam wand emits a translucent steam plume.

CLI:
  python proc_espresso_machine.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "espresso.glb"

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

mat_floor   = pbr_mat("floor",    (0.30, 0.22, 0.16), 0.00, 0.85)
mat_body    = pbr_mat("body",     (0.85, 0.85, 0.88), 0.85, 0.18)
mat_dark    = pbr_mat("dark",     (0.08, 0.08, 0.09), 0.40, 0.40)
mat_brass   = pbr_mat("brass",    (0.92, 0.72, 0.25), 1.00, 0.20)
mat_chrome  = pbr_mat("chrome",   (0.78, 0.80, 0.83), 1.00, 0.18)
mat_gauge_b = pbr_mat("gauge_bg", (0.92, 0.90, 0.85), 0.00, 0.35)
mat_needle  = pbr_mat("needle",   (0.85, 0.10, 0.10), 0.05, 0.30)
mat_button1 = pbr_mat("btn_blue", (0.20, 0.60, 1.00), 0.10, 0.20,
                          emission=((0.20, 0.55, 1.00), 4.0))
mat_button2 = pbr_mat("btn_red",  (0.95, 0.20, 0.20), 0.10, 0.20,
                          emission=((1.00, 0.30, 0.20), 4.0))
mat_grille  = pbr_mat("grille",   (0.20, 0.20, 0.22), 0.85, 0.30)
mat_tray    = pbr_mat("drip",     (0.55, 0.55, 0.58), 0.85, 0.25)
mat_cup     = pbr_mat("cup",      (0.92, 0.92, 0.90), 0.00, 0.40)
mat_saucer  = pbr_mat("saucer",   (0.90, 0.88, 0.85), 0.00, 0.40)
mat_coffee  = pbr_mat("coffee",   (0.18, 0.08, 0.04), 0.00, 0.30,
                          alpha=0.92)
mat_stream  = pbr_mat("stream",   (0.30, 0.14, 0.05), 0.05, 0.25,
                          alpha=0.85,
                          emission=((0.45, 0.18, 0.08), 0.6))
mat_steam   = pbr_mat("steam",    (0.95, 0.95, 0.98), 0.00, 0.10,
                          alpha=0.18,
                          emission=((1.00, 1.00, 1.00), 1.5))
mat_lcd     = pbr_mat("lcd",      (0.10, 0.10, 0.15), 0.00, 0.10,
                          emission=((0.30, 1.00, 0.45), 3.5))

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=20, rot=None):
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

def _sphere(name, R, location, mat, u=14, v=10, scale=(1,1,1)):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    if scale != (1,1,1):
        bmesh.ops.scale(bm, vec=mathutils.Vector(scale), verts=bm.verts)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# Conventions : machine faces -Y (user stands at -Y, the cup goes
# under the portafilter on the -Y side)

# --- counter ----------------------------
_box("floor", 1.6, 1.4, 0.04, (0, 0, -0.04), mat_floor)

# --- main body ----------------------------
BODY_W = 0.50
BODY_D = 0.42
BODY_H = 0.42
BODY_Z = BODY_H/2 + 0.04
_box("body_main", BODY_W, BODY_D, BODY_H, (0, 0.04, BODY_Z), mat_body)
# 4 rubber feet
for sx in (-1, +1):
    for sy in (-1, +1):
        _cyl(f"foot_{sx}_{sy}", 0.012, 0.012, 0.012, 'Z',
               (sx * (BODY_W/2 - 0.04), 0.04 + sy * (BODY_D/2 - 0.04), 0.006),
               mat_dark)

# water reservoir bulge on top (a dome cap)
_cyl("res_top", BODY_W * 0.50, BODY_W * 0.45, 0.04, 'Z',
       (0, 0.04, BODY_Z + BODY_H/2 + 0.02), mat_body)

# 2 group-head boilers : round chrome cylinders on the front face
GROUP_Z = BODY_Z - BODY_H * 0.05
for sx in (-1, +1):
    gx = sx * 0.10
    # outer cap (the dome part sticking out at -Y)
    _cyl(f"group_dome_{sx}", 0.06, 0.06, 0.05, 'Y',
           (gx, -BODY_D/2 + 0.02, GROUP_Z), mat_chrome)
    # inner ring (brass collar)
    _cyl(f"group_ring_{sx}", 0.065, 0.065, 0.015, 'Y',
           (gx, -BODY_D/2 - 0.005, GROUP_Z), mat_brass)
    # central nut
    _sphere(f"group_nut_{sx}", 0.022,
              (gx, -BODY_D/2 - 0.018, GROUP_Z), mat_chrome)

# 2 illuminated buttons on the right of the front face
for k, mat in enumerate((mat_button1, mat_button2)):
    bx = 0.20
    bz = BODY_Z + 0.04 - k * 0.05
    _cyl(f"btn_{k}", 0.020, 0.020, 0.008, 'Y',
           (bx, -BODY_D/2 - 0.005, bz), mat, segments=14)

# small LCD on the upper-left of the front face
_box("lcd_bezel", 0.10, 0.005, 0.04,
       (-0.18, -BODY_D/2 - 0.0025, BODY_Z + 0.06), mat_dark)
_box("lcd_screen", 0.092, 0.001, 0.032,
       (-0.18, -BODY_D/2 - 0.005, BODY_Z + 0.06), mat_lcd)

# --- portafilter : a parent empty holding the handle + filter + 2 spouts ---
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(-0.10, -BODY_D/2 - 0.06, GROUP_Z))
pf_pivot = bpy.context.active_object
pf_pivot.name = "portafilter_pivot"
# handle (long horizontal cyl extending -Y from the body)
handle = _cyl("pf_handle", 0.012, 0.012, 0.20, 'Y',
                (0, -0.10, 0), mat_dark)
handle.parent = pf_pivot; handle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# handle ferrule (chrome ring)
fer = _cyl("pf_ferrule", 0.016, 0.016, 0.020, 'Y',
             (0, -0.01, 0), mat_chrome)
fer.parent = pf_pivot; fer.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# filter basket (a thicker chrome cylinder)
basket = _cyl("pf_basket", 0.040, 0.040, 0.030, 'Z',
                (0, 0, -0.02), mat_chrome)
basket.parent = pf_pivot; basket.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# coffee puck (dark disc inside)
puck = _cyl("pf_puck", 0.038, 0.038, 0.008, 'Z',
              (0, 0, -0.018), mat_dark)
puck.parent = pf_pivot; puck.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 spouts (small chrome cylinders under the basket)
SPOUT_Z = -0.04
for sx in (-1, +1):
    sp = _cyl(f"pf_spout_{sx}", 0.006, 0.005, 0.025, 'Z',
                (sx * 0.012, 0, SPOUT_Z), mat_chrome)
    sp.parent = pf_pivot; sp.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- steam wand (a chrome cylinder pivoting on the right) -----
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(BODY_W/2 + 0.005, -BODY_D/2 + 0.04, BODY_Z + 0.05))
wand_pivot = bpy.context.active_object
wand_pivot.name = "wand_pivot"
wand_pivot.rotation_euler = (math.radians(-35), 0, 0)
# wand body
wand = _cyl("wand", 0.008, 0.008, 0.20, 'Z',
              (0, 0, -0.10), mat_chrome)
wand.parent = wand_pivot; wand.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# wand tip nozzle
tip = _cyl("wand_tip", 0.012, 0.008, 0.025, 'Z',
             (0, 0, -0.215), mat_chrome)
tip.parent = wand_pivot; tip.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# wand handle valve (a small ball at the top)
_sphere("wand_valve", 0.018,
          (BODY_W/2 + 0.005, -BODY_D/2 + 0.04, BODY_Z + 0.08), mat_dark)

# steam plume (semi-transparent emissive cone above the tip)
# the plume is parented to the wand pivot so it follows orientation
steam = _cyl("steam_plume", 0.018, 0.06, 0.20, 'Z',
               (0, 0, -0.33), mat_steam, segments=14)
steam.parent = wand_pivot; steam.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- pressure gauge on the front (round white face with red needle) ---
GAUGE_X = -0.18
GAUGE_Z = BODY_Z - 0.02
_cyl("gauge_outer", 0.045, 0.045, 0.010, 'Y',
       (GAUGE_X, -BODY_D/2 - 0.001, GAUGE_Z), mat_chrome)
_cyl("gauge_face", 0.040, 0.040, 0.005, 'Y',
       (GAUGE_X, -BODY_D/2 - 0.008, GAUGE_Z), mat_gauge_b)
# needle : a thin rectangle pivoted at the gauge center
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(GAUGE_X, -BODY_D/2 - 0.011, GAUGE_Z))
needle_pivot = bpy.context.active_object
needle_pivot.name = "needle_pivot"
needle_pivot.rotation_euler = (math.radians(180 - 60), 0, 0)  # ~rest at -60° from horizontal
needle = _box("gauge_needle", 0.002, 0.001, 0.035,
                (0, 0, 0.0175), mat_needle)
needle.parent = needle_pivot
needle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# central pivot dot
_sphere("gauge_pin", 0.005,
          (GAUGE_X, -BODY_D/2 - 0.014, GAUGE_Z), mat_dark)

# --- drip tray + grille + cup + saucer below the portafilter ---
TRAY_Z = 0.06
_box("drip_tray", 0.36, 0.16, 0.025,
       (0, -BODY_D/2 + 0.08, TRAY_Z), mat_tray)
# grille on top of tray : 7 narrow slats
for k in range(7):
    sx = -0.16 + k * 0.05
    _box(f"grille_slat_{k}", 0.012, 0.14, 0.006,
           (sx, -BODY_D/2 + 0.08, TRAY_Z + 0.015), mat_grille)
# saucer + cup centered under the spouts
CUP_X = -0.10
CUP_Y = -BODY_D/2 - 0.08
# saucer
_cyl("saucer", 0.045, 0.045, 0.008, 'Z',
       (CUP_X, CUP_Y, TRAY_Z + 0.020), mat_saucer, segments=20)
# cup body (a slightly tapered ceramic cylinder)
_cyl("cup_body", 0.030, 0.028, 0.05, 'Z',
       (CUP_X, CUP_Y, TRAY_Z + 0.045 + 0.025), mat_cup, segments=20)
# cup inner cavity (a darker thinner cylinder inside, mostly aesthetic)
_cyl("cup_inner", 0.025, 0.023, 0.040, 'Z',
       (CUP_X, CUP_Y, TRAY_Z + 0.050 + 0.020), mat_dark, segments=20)
# cup handle (a small torus-like ring)
_cyl("cup_handle", 0.012, 0.012, 0.015, 'Y',
       (CUP_X + 0.034, CUP_Y, TRAY_Z + 0.045 + 0.025), mat_cup)

# espresso stream : a thin emissive brown cylinder from the spout to the cup
STREAM_X = CUP_X
STREAM_Y = CUP_Y
STREAM_TOP_Z = GROUP_Z + SPOUT_Z - 0.015
STREAM_BOT_Z = TRAY_Z + 0.080
STREAM_H = STREAM_TOP_Z - STREAM_BOT_Z
stream = _cyl("stream", 0.004, 0.004, STREAM_H, 'Z',
                (STREAM_X, STREAM_Y, (STREAM_TOP_Z + STREAM_BOT_Z) / 2),
                mat_stream, segments=10)

# liquid surface inside the cup (a thin disc that rises)
liquid = _cyl("cup_liquid", 0.023, 0.023, 0.003, 'Z',
                (CUP_X, CUP_Y, TRAY_Z + 0.080), mat_coffee, segments=18)

# --- top-mounted accessory : small chrome cup-warmer rail on top
for k in range(3):
    rx = -0.15 + k * 0.15
    _cyl(f"warmer_rail_{k}", 0.006, 0.006, BODY_D * 0.6, 'Y',
           (rx, 0.04, BODY_Z + BODY_H/2 + 0.015), mat_chrome)

# --- animation -----------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Stream : scale Z from 0 to 1 over t=[0.10, 0.20] (start pouring), stays
# at 1 until t=0.85, then 1 -> 0 over [0.85, 0.95].
home_z = stream.location.z
home_loc = stream.location.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    if t < 0.10:
        s = 0.0
    elif t < 0.20:
        s = (t - 0.10) / 0.10
    elif t < 0.85:
        s = 1.0
    elif t < 0.95:
        s = 1.0 - (t - 0.85) / 0.10
    else:
        s = 0.0
    # the cylinder is centered at home_loc; if we want the top to stay
    # anchored at STREAM_TOP_Z, scaling Z by s shrinks toward the centre,
    # so we adjust location to keep top fixed.
    new_z_mid = STREAM_TOP_Z - (STREAM_H * s) / 2.0
    stream.scale = (1.0, 1.0, s if s > 0 else 0.001)
    stream.location = (home_loc.x, home_loc.y, new_z_mid)
    stream.keyframe_insert("scale", frame=f)
    stream.keyframe_insert("location", frame=f)
if stream.animation_data and stream.animation_data.action:
    for fc in stream.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Liquid in cup rises while the stream is on
LIQ_Z0 = TRAY_Z + 0.080
LIQ_Z1 = TRAY_Z + 0.082 + 0.035
LIQ_HOME = liquid.location.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    if t < 0.10:
        z = LIQ_Z0
    elif t < 0.85:
        u = (t - 0.10) / 0.75
        z = LIQ_Z0 + (LIQ_Z1 - LIQ_Z0) * u
    else:
        z = LIQ_Z1
    bpy.context.scene.frame_set(f)
    liquid.location = (LIQ_HOME.x, LIQ_HOME.y, z)
    liquid.keyframe_insert("location", frame=f)
if liquid.animation_data and liquid.animation_data.action:
    for fc in liquid.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Pressure gauge needle : -60° rest -> +60° (9 bar) over t=[0.10, 0.25],
# stays until 0.85, returns to rest over [0.85, 1.00]
def gauge_angle(t):
    if t < 0.10:
        return math.radians(120)  # rest
    elif t < 0.25:
        u = (t - 0.10) / 0.15
        return math.radians(120 + 120 * u)  # sweep up
    elif t < 0.85:
        return math.radians(240)  # pegged at high
    else:
        u = (t - 0.85) / 0.15
        return math.radians(240 - 120 * u)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    needle_pivot.rotation_euler = (gauge_angle(t), 0, 0)
    needle_pivot.keyframe_insert("rotation_euler", frame=f)
if needle_pivot.animation_data and needle_pivot.animation_data.action:
    for fc in needle_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# steam plume : grow + flicker emission
bsdf_st = mat_steam.node_tree.nodes.get("Principled BSDF")
em_st = bsdf_st.inputs["Emission Strength"]
steam_home = steam.location.copy()
STEAM_HOME_SCALE = (1.0, 1.0, 1.0)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    s = 0.8 + 0.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 3.0))
    sxy = 0.85 + 0.2 * (0.5 + 0.5 * math.sin(2*math.pi*t * 2.0 + 1.0))
    steam.scale = (sxy, sxy, s)
    steam.keyframe_insert("scale", frame=f)
    em_st.default_value = 1.0 + 0.8 * (0.5 + 0.5 * math.sin(2*math.pi*t * 4.0))
    em_st.keyframe_insert(data_path="default_value", frame=f)

# LCD cycle : 3 colors (idle / brewing / ready)
bsdf_lcd = mat_lcd.node_tree.nodes.get("Principled BSDF")
em_col = bsdf_lcd.inputs["Emission Color"]
em_str = bsdf_lcd.inputs["Emission Strength"]
LCD_COLORS = [
    (0.30, 1.00, 0.45),  # idle green
    (1.00, 0.85, 0.20),  # brewing yellow
    (1.00, 0.30, 0.20),  # ready red
]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    idx = int(t * len(LCD_COLORS)) % len(LCD_COLORS)
    em_col.default_value = (*LCD_COLORS[idx], 1.0)
    em_str.default_value = 2.5 + 1.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 3.0))
    bpy.context.scene.frame_set(f)
    em_col.keyframe_insert(data_path="default_value", frame=f)
    em_str.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"ESPR_OK: {out_glb}", flush=True)
'''


def make_espresso(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_espr_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "ESPR_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_espresso(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
