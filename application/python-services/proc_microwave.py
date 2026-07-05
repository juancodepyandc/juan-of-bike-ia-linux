"""Procedural countertop microwave oven (Blender headless).

White / stainless-steel body + glass door with a metallic mesh grille +
emissive LCD control panel + 10 control buttons + rotating glass turntable
+ ceramic plate + sandwich/food prop inside + handle on the door. Animation
: turntable spins, LCD cycles through 4 colours showing a fake timer
flashing, interior light glows.

CLI:
  python proc_microwave.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "microwave.glb"

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

mat_floor    = pbr_mat("floor",     (0.55, 0.50, 0.45), 0.00, 0.80)
mat_body     = pbr_mat("body",      (0.78, 0.78, 0.80), 0.55, 0.30)
mat_dark     = pbr_mat("dark_trim", (0.10, 0.10, 0.11), 0.40, 0.45)
mat_chrome   = pbr_mat("chrome",    (0.78, 0.80, 0.83), 1.00, 0.18)
mat_glass    = pbr_mat("glass",     (0.20, 0.22, 0.25), 0.00, 0.10, alpha=0.32)
mat_glass_t  = pbr_mat("turntable", (0.85, 0.92, 0.95), 0.00, 0.05, alpha=0.50)
mat_interior = pbr_mat("interior",  (0.80, 0.78, 0.72), 0.20, 0.55,
                          emission=((1.00, 0.90, 0.70), 1.5))
mat_grille   = pbr_mat("grille",    (0.05, 0.05, 0.06), 0.85, 0.30)
mat_lcd      = pbr_mat("lcd",       (0.05, 0.05, 0.10), 0.00, 0.10,
                          emission=((0.20, 1.00, 0.40), 4.0))
mat_btn      = pbr_mat("button",    (0.30, 0.30, 0.33), 0.20, 0.35)
mat_btn_red  = pbr_mat("btn_red",   (0.85, 0.15, 0.15), 0.10, 0.30)
mat_plate    = pbr_mat("plate",     (0.92, 0.92, 0.90), 0.00, 0.45)
mat_food     = pbr_mat("food",      (0.88, 0.72, 0.30), 0.00, 0.55)

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

# Conventions : microwave faces -Y (door is on -Y side, user stands at -Y)

# --- floor counter ---------------------------------
_box("floor", 1.6, 1.0, 0.04, (0, 0, -0.04), mat_floor)

# --- main body : box -----------------------------
BODY_W = 0.62
BODY_D = 0.48
BODY_H = 0.36
BODY_Z = BODY_H/2 + 0.01
_box("body", BODY_W, BODY_D, BODY_H, (0, 0, BODY_Z), mat_body)
# 4 short rubber feet
for sx in (-1, +1):
    for sy in (-1, +1):
        _cyl(f"foot_{sx}_{sy}", 0.014, 0.014, 0.010, 'Z',
               (sx * (BODY_W/2 - 0.04), sy * (BODY_D/2 - 0.04), 0.005),
               mat_dark)

# --- interior recess (lighter back wall behind the glass door) ----
INT_W = BODY_W * 0.62
INT_D = 0.04
INT_H = BODY_H * 0.78
# back wall (visible through glass): emissive interior
_box("interior_back", INT_W, INT_D, INT_H,
       (-0.04, BODY_D/2 - 0.04 - INT_D/2 - 0.20, BODY_Z), mat_interior)
# ceiling of cavity (a slab inside)
_box("cavity_top", INT_W, 0.30, 0.012,
       (-0.04, BODY_D/2 - 0.20, BODY_Z + INT_H/2 - 0.01), mat_body)
# floor of cavity (where turntable sits)
_box("cavity_floor", INT_W, 0.30, 0.012,
       (-0.04, BODY_D/2 - 0.20, BODY_Z - INT_H/2 + 0.01), mat_body)

# --- door (frame + glass + grille of dots + handle) -----
DOOR_W = BODY_W * 0.70
DOOR_H = BODY_H * 0.85
DOOR_Y = -BODY_D/2 - 0.012
DOOR_X = -0.04
_box("door_frame", DOOR_W + 0.04, 0.024, DOOR_H + 0.04,
       (DOOR_X, DOOR_Y, BODY_Z), mat_dark)
# glass panel inside the frame
_box("door_glass", DOOR_W, 0.012, DOOR_H,
       (DOOR_X, DOOR_Y + 0.008, BODY_Z), mat_glass)
# grille : 7x5 dots on the glass surface (suggesting the metal mesh)
GRILLE_COLS = 8
GRILLE_ROWS = 6
GRILLE_W = DOOR_W * 0.85
GRILLE_H = DOOR_H * 0.80
for r in range(GRILLE_ROWS):
    for c in range(GRILLE_COLS):
        gx = DOOR_X - GRILLE_W/2 + (c + 0.5) * GRILLE_W / GRILLE_COLS
        gz = BODY_Z - GRILLE_H/2 + (r + 0.5) * GRILLE_H / GRILLE_ROWS
        _sphere(f"grille_{r}_{c}", 0.005, (gx, DOOR_Y + 0.012, gz), mat_grille)

# door handle (a chrome bar along the -X edge of the door, vertical)
HANDLE_X = DOOR_X - DOOR_W/2 - 0.02
_cyl("handle_top", 0.010, 0.010, 0.04, 'Y',
       (HANDLE_X, DOOR_Y + 0.006, BODY_Z + DOOR_H/2 - 0.04), mat_chrome)
_cyl("handle_bot", 0.010, 0.010, 0.04, 'Y',
       (HANDLE_X, DOOR_Y + 0.006, BODY_Z - DOOR_H/2 + 0.04), mat_chrome)
_cyl("handle_bar", 0.010, 0.010, DOOR_H - 0.10, 'Z',
       (HANDLE_X - 0.02, DOOR_Y + 0.006, BODY_Z), mat_chrome)

# --- control panel on the right side --------------
PANEL_X = BODY_W/2 - 0.10
PANEL_W = 0.14
PANEL_H = DOOR_H * 0.96
_box("panel_bg", PANEL_W, 0.022, PANEL_H,
       (PANEL_X, -BODY_D/2 - 0.011, BODY_Z), mat_dark)
# LCD display (emissive, top of the panel)
LCD_W = PANEL_W * 0.85
LCD_H = 0.05
LCD_Z = BODY_Z + PANEL_H/2 - 0.06
_box("lcd_bezel", LCD_W + 0.008, 0.001, LCD_H + 0.008,
       (PANEL_X, -BODY_D/2 - 0.022, LCD_Z), mat_body)
_box("lcd", LCD_W, 0.001, LCD_H,
       (PANEL_X, -BODY_D/2 - 0.023, LCD_Z), mat_lcd)

# 10 control buttons : a 5x2 grid below the LCD
btn_y = -BODY_D/2 - 0.024
btn_W = 0.024
btn_z0 = LCD_Z - 0.07
for r in range(5):
    for c in range(2):
        bx = PANEL_X + (c - 0.5) * 0.05
        bz = btn_z0 - r * 0.040
        mat = mat_btn_red if (r == 4 and c == 1) else mat_btn
        _box(f"btn_{r}_{c}", btn_W, 0.005, 0.018,
               (bx, btn_y, bz), mat)

# --- turntable + plate + food ------------------
TT_R = 0.16
TT_X = -0.04
TT_Y = BODY_D/2 - 0.20
TT_Z = BODY_Z - INT_H/2 + 0.04
# rotating pivot under the turntable
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(TT_X, TT_Y, TT_Z))
turntable = bpy.context.active_object
turntable.name = "turntable_pivot"

# central spindle (small triangular hub) -- 3 short bars in a Y shape
for i in range(3):
    a = i * 2*math.pi/3
    bx = 0.025 * math.cos(a)
    by = 0.025 * math.sin(a)
    spoke = _box(f"spindle_spoke_{i}", 0.02, 0.005, 0.006,
                   (bx, by, 0.003), mat_dark,
                   rot=(0, 0, a))
    spoke.parent = turntable
    spoke.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# glass turntable disc
plate = _cyl("turntable_glass", TT_R, TT_R, 0.008, 'Z',
               (0, 0, 0.011), mat_glass_t, segments=32)
plate.parent = turntable
plate.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# ceramic plate on top
ceramic = _cyl("ceramic_plate", TT_R * 0.78, TT_R * 0.78, 0.010, 'Z',
                 (0, 0, 0.022), mat_plate, segments=24)
ceramic.parent = turntable
ceramic.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# food on the plate : a stack of 2 boxes simulating a slice of casserole
food = _box("food_main", 0.10, 0.08, 0.030, (0.01, 0.01, 0.040), mat_food)
food.parent = turntable
food.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# small bowl
bowl = _cyl("bowl", 0.04, 0.04, 0.025, 'Z', (-0.06, -0.04, 0.038), mat_plate, segments=14)
bowl.parent = turntable
bowl.matrix_parent_inverse = mathutils.Matrix.Identity(4)
bowl_inner = _cyl("bowl_inner", 0.035, 0.035, 0.022, 'Z',
                    (-0.06, -0.04, 0.040), mat_food, segments=14)
bowl_inner.parent = turntable
bowl_inner.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- top brand label (small chrome strip on top of body) ---
_box("brand_strip", 0.10, 0.005, 0.008,
       (0.10, -BODY_D/2 + 0.04, BODY_Z + BODY_H/2 - 0.025), mat_chrome)

# --- animation -----------------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# turntable spins (1.5 turns/loop)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    turntable.rotation_euler = (0, 0, 2*math.pi * 1.5 * t)
    turntable.keyframe_insert("rotation_euler", frame=f)
if turntable.animation_data and turntable.animation_data.action:
    for fc in turntable.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# LCD cycles 4 colours
bsdf_lcd = mat_lcd.node_tree.nodes.get("Principled BSDF")
em_col = bsdf_lcd.inputs["Emission Color"]
em_str = bsdf_lcd.inputs["Emission Strength"]
COLORS = [
    (0.20, 1.00, 0.40),  # green countdown
    (1.00, 0.85, 0.20),  # yellow warning
    (1.00, 0.20, 0.20),  # red ready
    (0.30, 0.50, 1.00),  # blue defrost
]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    idx = int(t * len(COLORS)) % len(COLORS)
    em_col.default_value = (*COLORS[idx], 1.0)
    # flash digit pulse at 2 Hz
    em_str.default_value = 3.5 + 1.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 2.0))
    bpy.context.scene.frame_set(f)
    em_col.keyframe_insert(data_path="default_value", frame=f)
    em_str.keyframe_insert(data_path="default_value", frame=f)

# interior light pulse
bsdf_i = mat_interior.node_tree.nodes.get("Principled BSDF")
em_i = bsdf_i.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_i.default_value = 1.2 + 0.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.0))
    bpy.context.scene.frame_set(f)
    em_i.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"MICROW_OK: {out_glb}", flush=True)
'''


def make_microwave(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_microw_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "MICROW_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_microwave(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
