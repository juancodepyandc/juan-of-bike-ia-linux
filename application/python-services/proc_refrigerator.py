"""Procedural side-by-side refrigerator (Blender headless).

Tall stainless body + 2 vertical doors (left freezer + right fridge) +
emissive LCD touchscreen + ice / water dispenser recess + chrome vertical
handles. The right door opens 25° revealing 3 shelves and 6 colored
food items inside. Animation : right door swings open then closed +
LCD cycles temperature readouts + interior light glows when door is
open.

CLI:
  python proc_refrigerator.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "fridge.glb"

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

mat_floor    = pbr_mat("floor",     (0.20, 0.16, 0.12), 0.00, 0.85)
mat_body     = pbr_mat("body",      (0.75, 0.76, 0.78), 0.85, 0.20)
mat_door     = pbr_mat("door",      (0.78, 0.80, 0.82), 0.85, 0.18)
mat_dark     = pbr_mat("dark",      (0.08, 0.08, 0.09), 0.40, 0.40)
mat_chrome   = pbr_mat("chrome",    (0.85, 0.86, 0.88), 1.00, 0.12)
mat_interior = pbr_mat("interior",  (0.92, 0.92, 0.90), 0.40, 0.40,
                          emission=((1.00, 0.95, 0.85), 0.2))
mat_shelf    = pbr_mat("shelf",     (0.85, 0.90, 0.95), 0.00, 0.10, alpha=0.45)
mat_drawer   = pbr_mat("drawer",    (0.70, 0.72, 0.75), 0.40, 0.30, alpha=0.55)
mat_lcd      = pbr_mat("lcd",       (0.05, 0.05, 0.10), 0.00, 0.10,
                          emission=((0.30, 0.55, 1.00), 4.0))
mat_disp     = pbr_mat("dispenser", (0.10, 0.10, 0.11), 0.30, 0.40)
mat_btn      = pbr_mat("button",    (0.20, 0.20, 0.22), 0.30, 0.35)
mat_btn_lit  = pbr_mat("btn_blue",  (0.30, 0.55, 1.00), 0.10, 0.20,
                          emission=((0.40, 0.65, 1.00), 1.5))
# Food colours (jars, packets, fruit, etc.)
FOOD_COLORS = [
    (0.85, 0.18, 0.18),  # tomato
    (0.18, 0.55, 0.25),  # broccoli green
    (0.95, 0.85, 0.30),  # cheese yellow
    (0.45, 0.20, 0.65),  # eggplant purple
    (0.95, 0.55, 0.18),  # carrot orange
    (0.55, 0.30, 0.18),  # bread brown
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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=18, rot=None):
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

# Conventions : fridge faces -Y. Up = +Z. Doors hinge on outer edges.

# --- floor -------------------------
_box("floor", 1.6, 1.4, 0.04, (0, 0, -0.04), mat_floor)

# fridge dimensions (side-by-side : wider than tall)
F_W = 0.90   # X span
F_D = 0.65   # Y span
F_H = 1.80   # height
F_Z = F_H/2 + 0.04
_box("body", F_W, F_D, F_H, (0, 0, F_Z), mat_body)

# top bezel (chrome strip running across top of body)
_box("top_bezel", F_W + 0.01, F_D + 0.01, 0.02,
       (0, 0, F_Z + F_H/2 + 0.01), mat_chrome)

# vertical seam between the 2 doors
_box("door_seam", 0.012, 0.02, F_H * 0.95,
       (0, -F_D/2 + 0.002, F_Z), mat_dark)

# === LEFT DOOR (freezer half) — STATIC ===
LD_X = -F_W * 0.25
LD_W = F_W * 0.48
LD_H = F_H * 0.96
LD_Y = -F_D/2 + 0.006
LD_T = 0.04
_box("door_L", LD_W, LD_T, LD_H, (LD_X, LD_Y, F_Z), mat_door)

# left door chrome handle (vertical bar on outer/left edge of left door)
_box("handle_L", 0.015, 0.02, LD_H * 0.55,
       (LD_X - LD_W/2 + 0.04, LD_Y - 0.02, F_Z), mat_chrome)
# two short anchors at top + bottom
for sz in (-1, +1):
    _box(f"handle_L_anchor_{sz}", 0.015, 0.015, 0.020,
           (LD_X - LD_W/2 + 0.04, LD_Y - 0.011, F_Z + sz * LD_H * 0.27), mat_chrome)

# ice/water dispenser on left door (a recessed dark panel)
DISP_X = LD_X
DISP_Z = F_Z + LD_H * 0.10
_box("dispenser_recess", LD_W * 0.55, 0.03, 0.22,
       (DISP_X, LD_Y - 0.014, DISP_Z), mat_disp)
# emissive LCD touchscreen above the dispenser
LCD_X = DISP_X
LCD_Z = F_Z + LD_H * 0.30
_box("lcd_bezel", LD_W * 0.55 + 0.01, 0.005, 0.10,
       (LCD_X, LD_Y - 0.018, LCD_Z), mat_chrome)
_box("lcd", LD_W * 0.50, 0.001, 0.08,
       (LCD_X, LD_Y - 0.0205, LCD_Z), mat_lcd)
# 2 lit buttons on the dispenser
for k in range(2):
    bx = DISP_X - 0.06 + k * 0.12
    _cyl(f"disp_btn_{k}", 0.012, 0.012, 0.008, 'Y',
           (bx, LD_Y - 0.020, DISP_Z + 0.06), mat_btn_lit, segments=12)
# coffee-glass-sized cup recess at the bottom of the dispenser
_box("disp_cup_recess", LD_W * 0.30, 0.022, 0.06,
       (DISP_X, LD_Y - 0.012, DISP_Z - 0.08), mat_dark)
# small grille at the bottom (a few horizontal bars)
for k in range(3):
    _box(f"disp_grille_{k}", LD_W * 0.20, 0.001, 0.005,
           (DISP_X, LD_Y - 0.020, DISP_Z - 0.07 - k * 0.012), mat_chrome)

# === RIGHT DOOR (fridge half) — ANIMATED open/close ===
RD_X_HOME = F_W * 0.25
RD_W = F_W * 0.48
RD_H = F_H * 0.96
RD_Y = -F_D/2 + 0.006
RD_T = 0.04
# The pivot is at the inner edge (the seam side) so the door hinges
# outward (-X direction is "inner", +X direction is "outer"). With the
# door on the right half, hinge is at x = +0.006 (just right of the seam).
HINGE_X = 0.006 + RD_W/2 - RD_W/2  # the inner edge of right door = x=0.006
# Actually compute properly : right door spans from x=0.006 (inner) to x=0.006+RD_W (outer)
RD_INNER_X = 0.012
RD_OUTER_X = RD_INNER_X + RD_W
HINGE_LOC = (RD_OUTER_X, -F_D/2 + 0.006, F_Z)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=HINGE_LOC)
door_R = bpy.context.active_object
door_R.name = "door_R_pivot"

# door slab : built relative to the hinge (mesh extends -X from the pivot)
slab_R = _box("door_R_slab", RD_W, RD_T, RD_H,
                (-RD_W/2, 0, 0), mat_door)
slab_R.parent = door_R
slab_R.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# right door handle (vertical chrome bar on the outer edge = at x ≈ 0)
handle_R = _box("handle_R", 0.015, 0.02, RD_H * 0.55,
                  (-RD_W + 0.04, -0.02, 0), mat_chrome)
handle_R.parent = door_R; handle_R.matrix_parent_inverse = mathutils.Matrix.Identity(4)
for sz in (-1, +1):
    a = _box(f"handle_R_anchor_{sz}", 0.015, 0.015, 0.020,
               (-RD_W + 0.04, -0.011, sz * RD_H * 0.27), mat_chrome)
    a.parent = door_R; a.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# === INTERIOR (visible when right door opens) ===
# Inner cavity is on the right half of the fridge body, behind the door
INT_X = RD_X_HOME
INT_Y = 0  # centered along Y inside the body
INT_Z = F_Z + 0.05
INT_W = RD_W - 0.04
INT_D = F_D * 0.7
INT_H = RD_H * 0.94
# back wall (the visible back of the cavity)
_box("interior_back", INT_W, 0.02, INT_H,
       (INT_X, F_D/2 - 0.03, F_Z), mat_interior)
# 3 glass shelves
SHELF_T = 0.008
for r in range(3):
    sz = F_Z + RD_H * 0.30 - r * RD_H * 0.25
    _box(f"shelf_{r}", INT_W, INT_D * 0.7, SHELF_T,
           (INT_X, 0.04, sz), mat_shelf)

# 6 colored food items distributed on the shelves
FOOD_DEFS = [
    (0, 0, FOOD_COLORS[0]),   # top shelf, left
    (0, 1, FOOD_COLORS[1]),   # top shelf, right
    (1, 0, FOOD_COLORS[2]),
    (1, 1, FOOD_COLORS[3]),
    (2, 0, FOOD_COLORS[4]),
    (2, 1, FOOD_COLORS[5]),
]
for i, (shelf_idx, col_idx, color) in enumerate(FOOD_DEFS):
    sz = F_Z + RD_H * 0.30 - shelf_idx * RD_H * 0.25
    sx = INT_X + (col_idx - 0.5) * INT_W * 0.45
    food_mat = pbr_mat(f"food_{i}", color, 0.00, 0.55)
    # alternate shapes : cube, cyl, sphere
    if i % 3 == 0:
        _box(f"food_{i}", 0.06, 0.06, 0.07,
               (sx, 0.04, sz + 0.045), food_mat)
    elif i % 3 == 1:
        _cyl(f"food_{i}", 0.030, 0.030, 0.10, 'Z',
               (sx, 0.04, sz + 0.060), food_mat, segments=14)
    else:
        _sphere(f"food_{i}", 0.035,
                  (sx, 0.04, sz + 0.045), food_mat,
                  scale=(1.0, 1.0, 0.85))

# drawer at the bottom (a translucent drawer)
DRAW_Z = F_Z - RD_H * 0.35
_box("crisper_drawer", INT_W * 0.95, INT_D * 0.85, 0.15,
       (INT_X, 0.04, DRAW_Z), mat_drawer)
# 2 colored fruits inside
for k in range(2):
    fc = FOOD_COLORS[(k + 4) % len(FOOD_COLORS)]
    fm = pbr_mat(f"fruit_{k}", fc, 0.00, 0.55)
    _sphere(f"fruit_{k}", 0.035,
              (INT_X + (k - 0.5) * 0.12, 0.04, DRAW_Z + 0.04), fm)

# === bottom kick-plate ===
_box("kick_plate", F_W, F_D + 0.005, 0.04,
       (0, 0, 0.020), mat_dark)

# brand label
_box("brand", 0.08, 0.004, 0.012,
       (F_W * 0.30, -F_D/2 - 0.005, F_Z + F_H/2 - 0.04), mat_chrome)

# --- animation -----------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Right door swings open (rotation Z) :
#   t = [0.00, 0.10] : closed
#   t = [0.10, 0.30] : opens to 25 deg
#   t = [0.30, 0.65] : stays open
#   t = [0.65, 0.85] : closes back
#   t = [0.85, 1.00] : closed
OPEN_DEG = 25
def door_angle(t):
    if t < 0.10:
        return 0.0
    elif t < 0.30:
        u = (t - 0.10) / 0.20
        # ease-in-out
        u = u*u*(3 - 2*u)
        return math.radians(OPEN_DEG * u)
    elif t < 0.65:
        return math.radians(OPEN_DEG)
    elif t < 0.85:
        u = (t - 0.65) / 0.20
        u = u*u*(3 - 2*u)
        return math.radians(OPEN_DEG * (1.0 - u))
    else:
        return 0.0

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    door_R.rotation_euler = (0, 0, door_angle(t))
    door_R.keyframe_insert("rotation_euler", frame=f)
if door_R.animation_data and door_R.animation_data.action:
    for fc in door_R.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Interior light glows when door is open (i.e. when angle > 5 deg)
bsdf_int = mat_interior.node_tree.nodes.get("Principled BSDF")
em_int = bsdf_int.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    ang = door_angle(t)
    if ang > math.radians(3):
        # gradually intensifies as door opens
        ratio = min(1.0, ang / math.radians(OPEN_DEG))
        em_val = 0.2 + 2.5 * ratio
    else:
        em_val = 0.2
    bpy.context.scene.frame_set(f)
    em_int.default_value = em_val
    em_int.keyframe_insert(data_path="default_value", frame=f)

# LCD cycles temperature readouts (4 colors representing different modes)
bsdf_lcd = mat_lcd.node_tree.nodes.get("Principled BSDF")
em_col = bsdf_lcd.inputs["Emission Color"]
em_str = bsdf_lcd.inputs["Emission Strength"]
LCD_COLORS = [
    (0.30, 0.55, 1.00),
    (0.30, 1.00, 0.50),
    (1.00, 0.85, 0.30),
    (0.55, 0.30, 1.00),
]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    idx = int(t * len(LCD_COLORS)) % len(LCD_COLORS)
    em_col.default_value = (*LCD_COLORS[idx], 1.0)
    em_str.default_value = 3.5 + 1.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 2.0))
    bpy.context.scene.frame_set(f)
    em_col.keyframe_insert(data_path="default_value", frame=f)
    em_str.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"FRIDGE_OK: {out_glb}", flush=True)
'''


def make_fridge(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_fridge_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "FRIDGE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_fridge(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
