"""Procedural painter's easel with canvas + palette + brushes + paint
tubes (Blender headless).

Wooden tripod (3 angled legs) + horizontal crossbar + ledge supporting
a stretched canvas with a layered abstract painting + a wooden palette
on a small side stand + a ceramic pot holding 3 brushes + 8 paint
tubes laid in 2 rows next to the easel. Animation : one brush lifts
from the pot, travels in an arc to the canvas, dabs the canvas, and
returns to the pot.

CLI:
  python proc_easel.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "easel.glb"

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

mat_floor    = pbr_mat("floor",      (0.55, 0.45, 0.30), 0.00, 0.85)  # wood floor
mat_wood     = pbr_mat("wood",       (0.45, 0.28, 0.10), 0.00, 0.55)
mat_wood_lt  = pbr_mat("wood_lt",    (0.65, 0.45, 0.20), 0.00, 0.45)
mat_canvas   = pbr_mat("canvas",     (0.92, 0.88, 0.78), 0.00, 0.80)
mat_p_blue   = pbr_mat("paint_blue", (0.20, 0.40, 0.85), 0.00, 0.45)
mat_p_red    = pbr_mat("paint_red",  (0.85, 0.18, 0.18), 0.00, 0.45)
mat_p_yel    = pbr_mat("paint_yel",  (0.95, 0.85, 0.20), 0.00, 0.45)
mat_p_grn    = pbr_mat("paint_grn",  (0.18, 0.60, 0.20), 0.00, 0.45)
mat_p_org    = pbr_mat("paint_org",  (0.95, 0.55, 0.18), 0.00, 0.45)
mat_p_pur    = pbr_mat("paint_pur",  (0.55, 0.20, 0.65), 0.00, 0.45)
mat_p_blk    = pbr_mat("paint_blk",  (0.06, 0.06, 0.07), 0.00, 0.50)
mat_p_wht    = pbr_mat("paint_wht",  (0.92, 0.92, 0.90), 0.00, 0.50)
mat_palette  = pbr_mat("palette",    (0.60, 0.38, 0.18), 0.00, 0.50)
mat_pot      = pbr_mat("pot",        (0.88, 0.86, 0.80), 0.00, 0.45)
mat_brush_h  = pbr_mat("brush_handle",(0.30, 0.18, 0.08), 0.00, 0.45)
mat_brush_f  = pbr_mat("brush_ferrule",(0.78, 0.80, 0.83), 1.00, 0.20)
mat_brush_b  = pbr_mat("brush_bristle",(0.35, 0.28, 0.20), 0.00, 0.65)
mat_tube     = pbr_mat("tube",       (0.85, 0.85, 0.88), 0.40, 0.35)
mat_tube_cap = pbr_mat("tube_cap",   (0.20, 0.20, 0.22), 0.10, 0.35)

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

# --- floor -----------------------------
_box("floor", 2.6, 2.0, 0.04, (0, 0, -0.04), mat_floor)

# --- easel : 3 legs in a tripod ---------
# 2 front legs angled outward (-Y direction), 1 rear support leg (+Y)
LEG_H = 1.55
LEG_BASE_R = 0.42
def make_leg(name, base_x, base_y, tilt_x_deg, tilt_y_deg):
    leg = _cyl(name, 0.020, 0.018, LEG_H, 'Z',
                 (0, 0, LEG_H/2), mat_wood)
    leg.location = (base_x, base_y, LEG_H/2)
    leg.rotation_euler = (math.radians(tilt_x_deg), math.radians(tilt_y_deg), 0)
    return leg

# Front-left and front-right legs : straight up but tipped outward
make_leg("leg_FL", -0.20, -0.05, -8, -4)  # tilt back + outward
make_leg("leg_FR", +0.20, -0.05, -8, +4)
# Rear support leg : behind, tilted forward
make_leg("leg_RR",  0.00, +0.18, +12, 0)

# horizontal crossbar near mid-height
CB_Z = 0.55
_box("crossbar", 0.55, 0.02, 0.025, (0, -0.05, CB_Z), mat_wood)

# top knob (chrome wing-nut style)
_sphere("top_knob", 0.018, (0, -0.05, LEG_H * 0.92), mat_brush_f)

# canvas ledge (small horizontal shelf supporting the canvas bottom)
LEDGE_Z = 0.75
_box("ledge", 0.50, 0.05, 0.015, (0, -0.07, LEDGE_Z), mat_wood)
# 2 small pegs that hold the canvas in place
for sx in (-1, +1):
    _cyl(f"ledge_peg_{sx}", 0.006, 0.006, 0.04, 'Z',
           (sx * 0.18, -0.05, LEDGE_Z + 0.02), mat_wood_lt)

# --- canvas (a slab with an abstract layered paint surface) ---
CANV_W = 0.50
CANV_H = 0.65
CANV_Z = LEDGE_Z + 0.012 + CANV_H/2 + 0.01
CANV_Y = -0.07
canvas_obj = _box("canvas", CANV_W, 0.015, CANV_H,
                    (0, CANV_Y, CANV_Z), mat_canvas)
# wooden inner frame around the canvas
_box("canvas_frame_top",    CANV_W + 0.04, 0.022, 0.025,
       (0, CANV_Y - 0.003, CANV_Z + CANV_H/2 + 0.012), mat_wood_lt)
_box("canvas_frame_bot",    CANV_W + 0.04, 0.022, 0.025,
       (0, CANV_Y - 0.003, CANV_Z - CANV_H/2 - 0.012), mat_wood_lt)
for sx in (-1, +1):
    _box(f"canvas_frame_side_{sx}", 0.020, 0.022, CANV_H,
           (sx * (CANV_W/2 + 0.010), CANV_Y - 0.003, CANV_Z), mat_wood_lt)

# abstract painting layers (sticking 2 mm in front of the canvas)
def paint_layer(name, sx, sy, sz, lx, lz, mat):
    _box(name, sx, sy, sz,
           (lx, CANV_Y - 0.0085, lz), mat)
# background wash : warm yellow patch upper-left
paint_layer("paint_bg", CANV_W * 0.55, 0.001, CANV_H * 0.40,
             -CANV_W * 0.18, CANV_Z + CANV_H * 0.18, mat_p_yel)
# blue rectangle lower-right
paint_layer("paint_blue", CANV_W * 0.35, 0.001, CANV_H * 0.30,
             CANV_W * 0.20, CANV_Z - CANV_H * 0.15, mat_p_blue)
# red brushstroke
paint_layer("paint_red", CANV_W * 0.40, 0.0015, 0.04,
             -CANV_W * 0.05, CANV_Z + 0.05, mat_p_red)
# green diagonal
paint_layer("paint_grn", CANV_W * 0.25, 0.0015, 0.20,
             CANV_W * 0.25, CANV_Z + CANV_H * 0.20, mat_p_grn)
# 3 dots
for k, (mx, mz, mat) in enumerate(((0.10, 0.10, mat_p_blk),
                                    (-0.18, -0.08, mat_p_org),
                                    (0.0, -0.05, mat_p_wht))):
    _cyl(f"paint_dot_{k}", 0.025, 0.025, 0.002, 'Y',
           (mx, CANV_Y - 0.0093, CANV_Z + mz), mat, segments=14)

# --- side tray with palette + pot + brushes -----
TRAY_X = 0.65
TRAY_Z = 0.50
# small wood stool/table
_box("tray_top", 0.42, 0.32, 0.025, (TRAY_X, 0.08, TRAY_Z), mat_wood)
for sx in (-1, +1):
    for sy in (-1, +1):
        _box(f"tray_leg_{sx}_{sy}", 0.02, 0.02, TRAY_Z,
               (TRAY_X + sx * 0.18, 0.08 + sy * 0.14, TRAY_Z/2), mat_wood)

# palette : oval flat board with a thumb-hole
# implemented as a slightly oblong cylinder lying flat
palette = _cyl("palette", 0.16, 0.16, 0.012, 'Z',
                 (TRAY_X - 0.05, 0.05, TRAY_Z + 0.02), mat_palette, segments=24)
# thumb-hole : a small dark cylinder near one edge
_cyl("palette_hole", 0.022, 0.022, 0.014, 'Z',
       (TRAY_X - 0.13, 0.05, TRAY_Z + 0.020), mat_wood)
# 8 blobs of paint on the palette in a ring
PAL_CX, PAL_CY = TRAY_X - 0.04, 0.06
for k, mat in enumerate([mat_p_blue, mat_p_red, mat_p_yel, mat_p_grn,
                          mat_p_org, mat_p_pur, mat_p_blk, mat_p_wht]):
    a = k * 2*math.pi/8
    bx = PAL_CX + 0.095 * math.cos(a)
    by = PAL_CY + 0.095 * math.sin(a)
    _sphere(f"palette_blob_{k}", 0.018,
              (bx, by, TRAY_Z + 0.022),
              mat, scale=(1.0, 1.0, 0.4))

# brush pot (cylindrical ceramic pot)
POT_X = TRAY_X + 0.13
POT_Y = 0.10
POT_Z_BASE = TRAY_Z + 0.012
_cyl("pot", 0.045, 0.040, 0.10, 'Z',
       (POT_X, POT_Y, POT_Z_BASE + 0.05), mat_pot, segments=20)
# 3 brushes in the pot, tilted slightly
def make_brush(name, base_loc, tilt_x_deg, tilt_y_deg, length=0.20):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=base_loc)
    pv = bpy.context.active_object
    pv.name = name + "_pivot"
    handle = _cyl(name + "_handle", 0.006, 0.005, length, 'Z',
                    (0, 0, length/2), mat_brush_h, segments=10)
    handle.parent = pv; handle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    ferrule = _cyl(name + "_ferrule", 0.007, 0.007, 0.018, 'Z',
                     (0, 0, length + 0.009), mat_brush_f, segments=10)
    ferrule.parent = pv; ferrule.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    bristle = _cyl(name + "_bristle", 0.007, 0.004, 0.020, 'Z',
                     (0, 0, length + 0.028), mat_brush_b, segments=10)
    bristle.parent = pv; bristle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    pv.rotation_euler = (math.radians(tilt_x_deg), math.radians(tilt_y_deg), 0)
    return pv

brush_pot_2 = make_brush("brush_pot_2",
                            (POT_X + 0.012, POT_Y - 0.012, POT_Z_BASE),
                            -8, -4)
brush_pot_3 = make_brush("brush_pot_3",
                            (POT_X - 0.014, POT_Y + 0.010, POT_Z_BASE),
                            +6, +8)
# the animated brush : starts in the pot pointing up
brush_main_home = (POT_X, POT_Y, POT_Z_BASE)
brush_main = make_brush("brush_main", brush_main_home, 0, 0)

# --- 8 paint tubes laid in 2 rows on the floor next to the easel ---
TUBE_X0 = -0.85
TUBE_Y0 = 0.30
TUBE_LEN = 0.10
TUBE_MATS = [mat_p_blue, mat_p_red, mat_p_yel, mat_p_grn,
              mat_p_org, mat_p_pur, mat_p_blk, mat_p_wht]
for k, mat in enumerate(TUBE_MATS):
    row = k // 4
    col = k % 4
    tx = TUBE_X0 + col * 0.10
    ty = TUBE_Y0 + row * 0.06
    # tube body
    _cyl(f"tube_{k}_body", 0.020, 0.018, TUBE_LEN, 'X',
           (tx, ty, 0.018), mat_tube, segments=12)
    # cap (small dark cyl on +X end)
    _cyl(f"tube_{k}_cap", 0.020, 0.020, 0.018, 'X',
           (tx + TUBE_LEN/2 + 0.008, ty, 0.018), mat_tube_cap, segments=12)
    # paint colour stripe (a thin slab on the body indicating colour)
    _box(f"tube_{k}_label", 0.06, 0.018, 0.002,
           (tx, ty, 0.030), mat)
    # tail crimp (a flat band at -X end)
    _box(f"tube_{k}_tail", 0.012, 0.024, 0.022,
           (tx - TUBE_LEN/2 - 0.005, ty, 0.018), mat_tube)

# --- animation : brush_main travels from pot -> canvas -> pot ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# Three key locations :
#  - HOME : in the pot, standing up
#  - DAB  : at the canvas, tip touching the paint
#  - VIA  : an in-between arc top
HOME = mathutils.Vector(brush_main_home)
DAB  = mathutils.Vector((0, CANV_Y - 0.02, CANV_Z + 0.05))
VIA  = mathutils.Vector((TRAY_X * 0.6, (POT_Y + CANV_Y) / 2,
                          POT_Z_BASE + 0.40))

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # phases : 0..0.30 lift+travel to DAB ; 0.30..0.45 dab on canvas ;
    #          0.45..0.75 travel back to pot ; 0.75..1.00 stays in pot.
    if t < 0.30:
        u = t / 0.30
        # quadratic Bezier HOME -> VIA -> DAB
        a = HOME.lerp(VIA, u); b = VIA.lerp(DAB, u)
        pos = a.lerp(b, u)
        rot_x = math.radians(-80 * u)   # tilt forward as it approaches canvas
    elif t < 0.45:
        # dab : small Y wiggle against canvas
        local_t = (t - 0.30) / 0.15
        wiggle_x = 0.020 * math.sin(local_t * 2*math.pi * 4)
        wiggle_z = 0.020 * math.cos(local_t * 2*math.pi * 3)
        pos = DAB + mathutils.Vector((wiggle_x, 0.001, wiggle_z))
        rot_x = math.radians(-80)
    elif t < 0.75:
        u = (t - 0.45) / 0.30
        a = DAB.lerp(VIA, u); b = VIA.lerp(HOME, u)
        pos = a.lerp(b, u)
        rot_x = math.radians(-80 * (1.0 - u))
    else:
        # rest in pot
        pos = HOME
        rot_x = 0.0
    brush_main.location = pos
    brush_main.rotation_euler = (rot_x, 0, 0)
    brush_main.keyframe_insert("location", frame=f)
    brush_main.keyframe_insert("rotation_euler", frame=f)
if brush_main.animation_data and brush_main.animation_data.action:
    for fc in brush_main.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"EASEL_OK: {out_glb}", flush=True)
'''


def make_easel(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_easel_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "EASEL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_easel(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
