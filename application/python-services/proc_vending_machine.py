"""Procedural soda vending machine (Blender headless).

Red-and-white tall body + large glass front + 6x4 = 24 colored bottles/cans
on inclined shelves + emissive logo panel + LCD price display + 12 keypad
buttons + coin slot + bill slot + return slot + collection drawer. Animation
: one can drops from row 2 through the chute (translation Z + slight roll)
+ LCD cycles price displays + logo panel pulses emission.

CLI:
  python proc_vending_machine.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "vending.glb"

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

mat_floor   = pbr_mat("floor",     (0.15, 0.15, 0.17), 0.00, 0.85)
mat_red     = pbr_mat("body_red",  (0.78, 0.10, 0.10), 0.10, 0.40)
mat_white   = pbr_mat("body_wht",  (0.92, 0.92, 0.90), 0.10, 0.40)
mat_dark    = pbr_mat("dark",      (0.08, 0.08, 0.09), 0.30, 0.40)
mat_chrome  = pbr_mat("chrome",    (0.78, 0.80, 0.83), 1.00, 0.18)
mat_glass   = pbr_mat("glass",     (0.55, 0.70, 0.78), 0.00, 0.05, alpha=0.18)
mat_shelf   = pbr_mat("shelf",     (0.60, 0.60, 0.62), 0.80, 0.30)
mat_logo    = pbr_mat("logo",      (1.00, 0.20, 0.20), 0.00, 0.10,
                          emission=((1.00, 0.25, 0.25), 6.0))
mat_logo_t  = pbr_mat("logo_txt",  (0.95, 0.92, 0.88), 0.00, 0.10,
                          emission=((1.00, 0.95, 0.90), 6.0))
mat_lcd     = pbr_mat("lcd",       (0.05, 0.05, 0.08), 0.00, 0.10,
                          emission=((0.30, 1.00, 0.45), 4.0))
mat_btn     = pbr_mat("button",    (0.20, 0.20, 0.22), 0.30, 0.35)
mat_btn_lit = pbr_mat("btn_lit",   (0.95, 0.85, 0.20), 0.10, 0.20,
                          emission=((1.00, 0.90, 0.30), 1.5))
# Can/bottle colours
CAN_COLORS = [
    (0.85, 0.10, 0.10),  # cola red
    (0.20, 0.20, 0.85),  # blue
    (0.95, 0.55, 0.10),  # orange
    (0.18, 0.65, 0.20),  # green soda
    (0.95, 0.85, 0.20),  # yellow lemon
    (0.55, 0.20, 0.65),  # grape
    (0.10, 0.10, 0.12),  # cola black
    (0.95, 0.45, 0.65),  # pink berry
]

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=16, rot=None):
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

# Conventions : machine facing -Y. User stands at -Y. Glass on -Y face.

# --- floor -----------------------------
_box("floor", 2.0, 1.6, 0.04, (0, 0, -0.04), mat_floor)

# Machine dims
M_W = 0.85
M_D = 0.80
M_H = 1.85
M_Z = M_H/2 + 0.05

# main red body
_box("body", M_W, M_D, M_H, (0, 0, M_Z), mat_red)
# white front panel area (front facing -Y, slightly forward)
_box("body_front", M_W * 0.96, 0.02, M_H * 0.96,
       (0, -M_D/2 + 0.011, M_Z), mat_red)

# --- top header (logo panel) -----------
HEADER_H = 0.20
HEADER_Z = M_Z + M_H/2 - HEADER_H/2
_box("header_bg", M_W * 0.98, 0.04, HEADER_H,
       (0, -M_D/2 + 0.001, HEADER_Z), mat_red)
# logo emissive panel
_box("logo_panel", M_W * 0.85, 0.005, HEADER_H * 0.85,
       (0, -M_D/2 - 0.0025, HEADER_Z), mat_logo)
# "SODA" lettering : 4 thin bars on the logo
for k in range(4):
    lx = -M_W * 0.30 + k * (M_W * 0.20)
    _box(f"logo_letter_{k}", 0.04, 0.001, HEADER_H * 0.45,
           (lx, -M_D/2 - 0.005, HEADER_Z), mat_logo_t)

# --- glass front window (covers most of the front, below header) ----
GLASS_W = M_W * 0.62
GLASS_D = 0.012
GLASS_H = M_H * 0.55
GLASS_Z = M_Z + 0.08
GLASS_X = -M_W * 0.16
# Glass center is offset to -X (left half) ; right half is for the keypad
_box("glass_front", GLASS_W, GLASS_D, GLASS_H,
       (GLASS_X, -M_D/2 + 0.012, GLASS_Z), mat_glass)
# glass bezel frame
_box("glass_bezel_top", GLASS_W + 0.04, 0.025, 0.03,
       (GLASS_X, -M_D/2 + 0.005, GLASS_Z + GLASS_H/2 + 0.015), mat_dark)
_box("glass_bezel_bot", GLASS_W + 0.04, 0.025, 0.03,
       (GLASS_X, -M_D/2 + 0.005, GLASS_Z - GLASS_H/2 - 0.015), mat_dark)
for sx in (-1, +1):
    _box(f"glass_bezel_side_{sx}", 0.025, 0.025, GLASS_H + 0.06,
           (GLASS_X + sx * (GLASS_W/2 + 0.012), -M_D/2 + 0.005, GLASS_Z), mat_dark)

# --- 6 inclined shelves with 4 cans each -----
N_ROWS = 6
N_COLS = 4
CAN_R = 0.030
CAN_H = 0.110
SHELF_TOP_Z = GLASS_Z + GLASS_H/2 - 0.02
SHELF_BOT_Z = GLASS_Z - GLASS_H/2 + 0.02
SHELF_DY = (SHELF_TOP_Z - SHELF_BOT_Z) / (N_ROWS - 1) if N_ROWS > 1 else 0
SHELF_INCLINE = math.radians(6)
DROP_CAN_INFO = None  # we'll record row=1, col=0 for the dropping can
cans_data = []
shelves_data = []
for r in range(N_ROWS):
    z = SHELF_TOP_Z - r * SHELF_DY
    # shelf slab (incline visible on the -Y side)
    s = _box(f"shelf_{r}", GLASS_W * 0.96, 0.30, 0.008,
               (GLASS_X, -M_D/2 + 0.18, z - 0.012), mat_shelf,
               rot=(SHELF_INCLINE, 0, 0))
    shelves_data.append(s)
    # 4 cans per shelf
    for c in range(N_COLS):
        cx = GLASS_X - GLASS_W/2 + 0.08 + c * (GLASS_W - 0.16) / (N_COLS - 1)
        cy = -M_D/2 + 0.13  # toward the front, just behind the glass
        cz = z + CAN_H/2 + 0.005
        color = CAN_COLORS[(r * N_COLS + c) % len(CAN_COLORS)]
        cm = pbr_mat(f"can_mat_{r}_{c}", color, 0.55, 0.25)
        can = _cyl(f"can_{r}_{c}", CAN_R, CAN_R, CAN_H, 'Z',
                     (cx, cy, cz), cm, segments=14)
        # cap (chrome on top)
        _cyl(f"can_cap_{r}_{c}", CAN_R * 0.95, CAN_R * 0.95, 0.006, 'Z',
               (cx, cy, cz + CAN_H/2 + 0.003), mat_chrome, segments=14)
        # label band (a thin chrome ring)
        _cyl(f"can_band_{r}_{c}", CAN_R * 1.005, CAN_R * 1.005, 0.012, 'Z',
               (cx, cy, cz - CAN_H * 0.25), mat_chrome, segments=14)
        cans_data.append((can, cx, cy, cz, r, c))
        if r == 1 and c == 0:
            DROP_CAN_INFO = (can, cx, cy, cz)

# --- control panel on the right side of the front -----
PANEL_X = M_W * 0.30
PANEL_W = M_W * 0.30
PANEL_H = GLASS_H * 0.85
PANEL_Z = GLASS_Z + 0.05
_box("panel_bg", PANEL_W, 0.02, PANEL_H,
       (PANEL_X, -M_D/2 + 0.011, PANEL_Z), mat_dark)
# LCD display at top of panel
LCD_W = PANEL_W * 0.80
LCD_H = 0.06
LCD_Z = PANEL_Z + PANEL_H/2 - 0.08
_box("lcd_bezel", LCD_W + 0.012, 0.005, LCD_H + 0.012,
       (PANEL_X, -M_D/2 + 0.013, LCD_Z), mat_chrome)
_box("lcd", LCD_W, 0.001, LCD_H,
       (PANEL_X, -M_D/2 - 0.0005, LCD_Z), mat_lcd)

# 12 keypad buttons : 4x3 grid
btn_y = -M_D/2 + 0.014
btn_W = 0.040
btn_z0 = LCD_Z - 0.10
for r in range(4):
    for c in range(3):
        bx = PANEL_X + (c - 1) * 0.055
        bz = btn_z0 - r * 0.060
        # the (1, 0) button is lit (the "buy" indicator)
        mat = mat_btn_lit if (r == 1 and c == 0) else mat_btn
        _cyl(f"keypad_{r}_{c}", 0.020, 0.020, 0.010, 'Y',
               (bx, btn_y, bz), mat, segments=14)
        # button label dot
        _cyl(f"keypad_label_{r}_{c}", 0.010, 0.010, 0.002, 'Y',
               (bx, btn_y - 0.005, bz), mat_white, segments=10)

# coin slot + bill slot below the keypad
COIN_Z = PANEL_Z - PANEL_H/2 + 0.12
_box("coin_slot", PANEL_W * 0.40, 0.005, 0.020,
       (PANEL_X, -M_D/2 - 0.0025, COIN_Z + 0.05), mat_chrome)
_box("bill_slot", PANEL_W * 0.55, 0.005, 0.020,
       (PANEL_X, -M_D/2 - 0.0025, COIN_Z), mat_chrome)

# coin return slot (under the bill slot)
_box("coin_return", PANEL_W * 0.50, 0.005, 0.025,
       (PANEL_X, -M_D/2 - 0.0025, COIN_Z - 0.05), mat_dark)

# --- collection drawer at the bottom front ----
DRAW_W = M_W * 0.55
DRAW_H = 0.18
DRAW_Z = M_Z - M_H/2 + DRAW_H/2 + 0.12
_box("drawer_frame", DRAW_W, 0.02, DRAW_H,
       (-M_W * 0.10, -M_D/2 + 0.011, DRAW_Z), mat_dark)
# drawer flap (lifts when can drops)
_box("drawer_flap", DRAW_W * 0.92, 0.012, DRAW_H * 0.80,
       (-M_W * 0.10, -M_D/2 + 0.001, DRAW_Z), mat_red)

# --- top accent stripe (white horizontal stripe across body) ---
_box("stripe_top", M_W * 0.98, 0.04, 0.04,
       (0, -M_D/2 + 0.001, HEADER_Z - HEADER_H/2 - 0.025), mat_white)

# --- animation -----------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Drop can : starts at shelf position, falls to drawer level, with slight
# rolling. The drop happens between t=0.20 and t=0.40, then can rests in
# drawer until t=1.0.
if DROP_CAN_INFO is not None:
    drop_can, dx, dy, dz0 = DROP_CAN_INFO
    drop_dz_end = DRAW_Z - 0.04
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        if t < 0.20:
            z = dz0
            roll = 0
        elif t < 0.40:
            u = (t - 0.20) / 0.20
            # quadratic ease (gravity acceleration)
            z = dz0 + (drop_dz_end - dz0) * (u * u)
            roll = u * math.pi * 1.5
        else:
            z = drop_dz_end
            roll = math.pi * 1.5
        drop_can.location = (dx, dy, z)
        drop_can.rotation_euler = (roll, 0, 0)
        drop_can.keyframe_insert("location", frame=f)
        drop_can.keyframe_insert("rotation_euler", frame=f)
    if drop_can.animation_data and drop_can.animation_data.action:
        for fc in drop_can.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

# LCD cycle 4 colours (price displays) and pulse
bsdf_lcd = mat_lcd.node_tree.nodes.get("Principled BSDF")
em_col = bsdf_lcd.inputs["Emission Color"]
em_str = bsdf_lcd.inputs["Emission Strength"]
LCD_COLORS = [
    (0.30, 1.00, 0.45),
    (1.00, 0.85, 0.20),
    (0.30, 0.55, 1.00),
    (1.00, 0.30, 0.30),
]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    idx = int(t * len(LCD_COLORS)) % len(LCD_COLORS)
    em_col.default_value = (*LCD_COLORS[idx], 1.0)
    em_str.default_value = 3.0 + 1.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 3.0))
    bpy.context.scene.frame_set(f)
    em_col.keyframe_insert(data_path="default_value", frame=f)
    em_str.keyframe_insert(data_path="default_value", frame=f)

# Logo panel pulses slowly
bsdf_logo = mat_logo.node_tree.nodes.get("Principled BSDF")
em_logo = bsdf_logo.inputs["Emission Strength"]
bsdf_logo_t = mat_logo_t.node_tree.nodes.get("Principled BSDF")
em_logo_t = bsdf_logo_t.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    val = 5.0 + 2.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.0))
    em_logo.default_value = val
    em_logo_t.default_value = val + 1.0
    bpy.context.scene.frame_set(f)
    em_logo.keyframe_insert(data_path="default_value", frame=f)
    em_logo_t.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"VEND_OK: {out_glb}", flush=True)
'''


def make_vending(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_vend_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "VEND_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_vending(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
