"""Procedural front-load washing machine (Blender headless).

White cabinet + circular glass porthole with rubber gasket + visible
chrome drum behind the door + 6 coloured clothing balls tumbling inside
+ top control panel with LCD timer + 4 push buttons + program selector
dial + detergent drawer at top. Animation : drum (and the clothing
inside) spins at high speed, LCD timer cycles colours indicating the
program is running.

CLI:
  python proc_washing_machine.py <output_glb>
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
import bpy, bmesh, math, mathutils, sys, random

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "washing.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0xFA571)

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

mat_floor    = pbr_mat("floor",     (0.55, 0.55, 0.55), 0.00, 0.85)
mat_body     = pbr_mat("body",      (0.95, 0.95, 0.93), 0.10, 0.30)
mat_dark     = pbr_mat("dark",      (0.10, 0.10, 0.11), 0.40, 0.40)
mat_chrome   = pbr_mat("chrome",    (0.78, 0.80, 0.83), 1.00, 0.18)
mat_glass    = pbr_mat("glass",     (0.45, 0.55, 0.65), 0.00, 0.05, alpha=0.20)
mat_gasket   = pbr_mat("gasket",    (0.10, 0.10, 0.11), 0.00, 0.85)
mat_drum     = pbr_mat("drum",      (0.55, 0.55, 0.58), 1.00, 0.20)
mat_drum_hole= pbr_mat("drum_hole", (0.04, 0.04, 0.04), 0.00, 0.85)
mat_water    = pbr_mat("water",     (0.40, 0.65, 0.85), 0.00, 0.10, alpha=0.35)
mat_lcd      = pbr_mat("lcd",       (0.05, 0.05, 0.10), 0.00, 0.10,
                          emission=((0.20, 0.55, 1.00), 4.0))
mat_btn      = pbr_mat("button",    (0.20, 0.20, 0.22), 0.30, 0.35)
mat_btn_lit  = pbr_mat("btn_green", (0.30, 0.85, 0.40), 0.10, 0.20,
                          emission=((0.40, 1.00, 0.50), 1.5))
mat_dial     = pbr_mat("dial",      (0.18, 0.18, 0.20), 0.60, 0.30)
mat_dial_top = pbr_mat("dial_top",  (0.92, 0.92, 0.90), 0.10, 0.35)
mat_drawer   = pbr_mat("drawer",    (0.78, 0.78, 0.80), 0.50, 0.30)
# Clothes : 6 distinct fabric colours
CLOTH_COLORS = [
    (0.85, 0.18, 0.18),
    (0.18, 0.30, 0.85),
    (0.95, 0.85, 0.25),
    (0.20, 0.70, 0.30),
    (0.85, 0.45, 0.85),
    (0.95, 0.55, 0.20),
]
cloth_mats = [pbr_mat(f"cloth_{i}", c, 0.00, 0.65) for i, c in enumerate(CLOTH_COLORS)]

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

# Conventions : washer faces -Y. Door is on -Y face. Up = +Z.

# --- floor -----------------------
_box("floor", 1.6, 1.6, 0.04, (0, 0, -0.04), mat_floor)

# Machine dims
W_W = 0.62
W_D = 0.62
W_H = 0.86
W_Z = W_H/2 + 0.04
# main body
_box("body", W_W, W_D, W_H, (0, 0, W_Z), mat_body)
# 4 feet
for sx in (-1, +1):
    for sy in (-1, +1):
        _cyl(f"foot_{sx}_{sy}", 0.020, 0.020, 0.020, 'Z',
               (sx * (W_W/2 - 0.06), sy * (W_D/2 - 0.06), 0.010),
               mat_dark)

# --- top control panel area ---
PANEL_Z = W_Z + W_H/2 - 0.10
_box("panel_recess", W_W * 0.96, 0.04, 0.10,
       (0, -W_D/2 + 0.005, PANEL_Z), mat_dark)
# detergent drawer on left
DRAW_W = W_W * 0.40
_box("detergent_drawer", DRAW_W, 0.04, 0.08,
       (-W_W/2 + DRAW_W/2 + 0.02, -W_D/2 - 0.010, PANEL_Z), mat_drawer)
# 2 drawer handles (small chrome bars)
for sx in (-1, +1):
    _box(f"drawer_handle_{sx}", 0.06, 0.005, 0.012,
           (-W_W/2 + DRAW_W/2 + 0.02 + sx * 0.08, -W_D/2 - 0.018, PANEL_Z), mat_chrome)

# program selector dial on right of panel
DIAL_X = W_W * 0.28
DIAL_Z = PANEL_Z
_cyl("prog_dial_body", 0.040, 0.040, 0.025, 'Y',
       (DIAL_X, -W_D/2 - 0.010, DIAL_Z), mat_dial)
_cyl("prog_dial_top", 0.040, 0.035, 0.005, 'Y',
       (DIAL_X, -W_D/2 - 0.024, DIAL_Z), mat_dial_top)
# pointer line on the dial (a chrome strip)
_box("dial_pointer", 0.004, 0.002, 0.024,
       (DIAL_X, -W_D/2 - 0.028, DIAL_Z + 0.012), mat_chrome)

# LCD display in middle of panel
LCD_W = 0.16
LCD_H = 0.05
LCD_X = -W_W * 0.05
_box("lcd_bezel", LCD_W + 0.012, 0.005, LCD_H + 0.012,
       (LCD_X, -W_D/2 - 0.010, PANEL_Z), mat_chrome)
_box("lcd", LCD_W, 0.001, LCD_H,
       (LCD_X, -W_D/2 - 0.014, PANEL_Z), mat_lcd)

# 4 control buttons : right of LCD
for k in range(4):
    bx = LCD_X + 0.12 + (k % 2) * 0.03
    bz = PANEL_Z - 0.005 + (1 - k // 2) * 0.03
    mat = mat_btn_lit if k == 0 else mat_btn
    _cyl(f"btn_{k}", 0.012, 0.012, 0.006, 'Y',
           (bx, -W_D/2 - 0.010, bz), mat, segments=12)

# --- circular porthole door on the front face ---
DOOR_R = 0.20
DOOR_Y = -W_D/2 - 0.010
DOOR_Z = W_Z + 0.00
# gasket ring (black rubber)
_cyl("door_gasket", DOOR_R + 0.022, DOOR_R + 0.022, 0.015, 'Y',
       (0, DOOR_Y + 0.005, DOOR_Z), mat_gasket, segments=32)
# glass porthole (visible interior)
_cyl("door_glass", DOOR_R, DOOR_R, 0.010, 'Y',
       (0, DOOR_Y, DOOR_Z), mat_glass, segments=32)
# outer frame (chrome ring)
_cyl("door_frame", DOOR_R + 0.012, DOOR_R + 0.012, 0.025, 'Y',
       (0, DOOR_Y - 0.005, DOOR_Z), mat_chrome, segments=32)
# door hinge (small box on the left)
_box("door_hinge", 0.025, 0.025, 0.06,
       (-W_W/2 + 0.02, DOOR_Y - 0.005, DOOR_Z), mat_chrome)
# door handle (a chrome lever on the right)
_box("door_handle", 0.018, 0.018, 0.07,
       (DOOR_R + 0.04, DOOR_Y - 0.005, DOOR_Z), mat_chrome)

# --- drum (rotates) + clothes inside ---
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(0, DOOR_Y + 0.16, DOOR_Z))
drum = bpy.context.active_object
drum.name = "drum_pivot"

# drum cylinder (chrome interior visible through glass), oriented along -Y
DRUM_R = DOOR_R - 0.02
DRUM_DEPTH = 0.22
drum_cyl = _cyl("drum_cyl", DRUM_R, DRUM_R, DRUM_DEPTH, 'Y',
                  (0, 0, 0), mat_drum, segments=32)
drum_cyl.parent = drum; drum_cyl.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# drum holes : 30 small dark dots on the inner wall to suggest perforations
for i in range(30):
    a = 2*math.pi * i / 30
    hx = (DRUM_R - 0.001) * math.cos(a)
    hz = (DRUM_R - 0.001) * math.sin(a)
    hy = rng.uniform(-DRUM_DEPTH/2 + 0.02, DRUM_DEPTH/2 - 0.02)
    hole = _sphere(f"drum_hole_{i}", 0.008, (hx, hy, hz), mat_drum_hole)
    hole.parent = drum; hole.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 6 clothes (small irregular ellipsoid shapes inside the drum), parented
# so they tumble with the drum
clothes = []
for i in range(6):
    a = 2*math.pi * i / 6 + rng.uniform(-0.2, 0.2)
    r = DRUM_R * (0.55 + rng.uniform(-0.10, 0.15))
    cx = r * math.cos(a)
    cz = r * math.sin(a)
    cy = rng.uniform(-DRUM_DEPTH/2 + 0.04, DRUM_DEPTH/2 - 0.04)
    sphR = 0.025 + rng.uniform(-0.005, 0.010)
    sx = 1.0 + rng.uniform(-0.2, 0.4)
    sy = 1.0 + rng.uniform(-0.2, 0.4)
    sz = 1.0 + rng.uniform(-0.2, 0.4)
    cl = _sphere(f"cloth_{i}", sphR, (cx, cy, cz),
                   cloth_mats[i % len(cloth_mats)],
                   scale=(sx, sy, sz))
    cl.parent = drum; cl.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    clothes.append(cl)

# water sloshing pool inside the drum (a thin translucent slab)
_cyl("drum_water", DRUM_R * 0.95, DRUM_R * 0.95, 0.04, 'Y',
       (0, 0, -DRUM_R * 0.55), mat_water, segments=24)

# --- LED status light below the door (small dot) ----
_sphere("status_led", 0.008, (DOOR_R + 0.04, DOOR_Y - 0.012, DOOR_Z - DOOR_R - 0.03),
          mat_btn_lit)

# --- brand label below the door ----
_box("brand", 0.08, 0.004, 0.012,
       (0, DOOR_Y - 0.005, DOOR_Z - DOOR_R - 0.06), mat_chrome)

# --- animation -----------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Drum spins around Y (the axis of the porthole / drum) at high speed.
# 3 turns per loop, but during the last 25% it slows down (rinse end).
def drum_angle(t):
    if t < 0.75:
        u = t / 0.75
        return 2*math.pi * 3.0 * u
    else:
        # ease-out from current angle to the same angle + 0.5 turn
        local = (t - 0.75) / 0.25
        u = 1.0 - (1.0 - local)**2
        return 2*math.pi * 3.0 + 2*math.pi * 0.5 * u

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    drum.rotation_euler = (0, drum_angle(t), 0)
    drum.keyframe_insert("rotation_euler", frame=f)
if drum.animation_data and drum.animation_data.action:
    for fc in drum.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# LCD cycles colour (timer countdown progression)
bsdf_lcd = mat_lcd.node_tree.nodes.get("Principled BSDF")
em_col = bsdf_lcd.inputs["Emission Color"]
em_str = bsdf_lcd.inputs["Emission Strength"]
LCD_COLORS = [
    (0.20, 0.55, 1.00),
    (0.30, 1.00, 0.45),
    (1.00, 0.85, 0.20),
]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    idx = int(t * len(LCD_COLORS)) % len(LCD_COLORS)
    em_col.default_value = (*LCD_COLORS[idx], 1.0)
    em_str.default_value = 3.0 + 1.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.0))
    bpy.context.scene.frame_set(f)
    em_col.keyframe_insert(data_path="default_value", frame=f)
    em_str.keyframe_insert(data_path="default_value", frame=f)

# Status LED blinks (lit during cycle)
bsdf_led = mat_btn_lit.node_tree.nodes.get("Principled BSDF")
em_led = bsdf_led.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    val = 1.0 + 0.6 * (0.5 + 0.5 * math.sin(2*math.pi*t * 2.0))
    em_led.default_value = val
    bpy.context.scene.frame_set(f)
    em_led.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"WASH_OK: {out_glb}", flush=True)
'''


def make_washing(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_wash_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "WASH_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_washing(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
