"""Procedural home treadmill (Blender headless).

Inclined steel chassis + rubber running belt over 2 rollers + side rails
+ U-shaped console handlebar with safety key lanyard + emissive LCD
console + 6 control buttons + heart-rate hand-grip sensors. Animation :
running belt scrolls toward -Y (segments translate + recycle) +
LCD digits cycle colour (workout-mode flash) + safety key dangles
slightly.

CLI:
  python proc_treadmill.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "treadmill.glb"

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

mat_floor    = pbr_mat("floor",    (0.20, 0.20, 0.22), 0.00, 0.85)
mat_steel    = pbr_mat("steel",    (0.70, 0.72, 0.75), 0.85, 0.30)
mat_dark     = pbr_mat("dark",     (0.10, 0.10, 0.11), 0.50, 0.40)
mat_belt     = pbr_mat("belt",     (0.06, 0.06, 0.07), 0.05, 0.75)
mat_belt_ln  = pbr_mat("belt_ln",  (0.12, 0.12, 0.13), 0.05, 0.65)
mat_rubber   = pbr_mat("rubber",   (0.08, 0.08, 0.09), 0.05, 0.85)
mat_rail     = pbr_mat("rail",     (0.55, 0.20, 0.20), 0.10, 0.40)
mat_grip     = pbr_mat("grip",     (0.18, 0.18, 0.20), 0.10, 0.55)
mat_grip_red = pbr_mat("grip_red", (0.85, 0.18, 0.18), 0.10, 0.45)
mat_lcd      = pbr_mat("lcd",      (0.05, 0.05, 0.08), 0.00, 0.10,
                          emission=((0.20, 0.55, 1.00), 4.0))
mat_btn      = pbr_mat("button",   (0.20, 0.20, 0.22), 0.30, 0.35)
mat_btn_red  = pbr_mat("btn_red",  (0.85, 0.18, 0.18), 0.10, 0.30)
mat_btn_grn  = pbr_mat("btn_grn",  (0.18, 0.75, 0.30), 0.10, 0.30)
mat_lanyard  = pbr_mat("lanyard",  (0.85, 0.18, 0.18), 0.05, 0.65)
mat_key      = pbr_mat("safety_key",(0.92, 0.85, 0.30), 0.10, 0.30)

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

# Conventions : the treadmill faces -Y (user runs facing +Y from -Y end).
# The chassis is slightly inclined : back (+Y, near console) higher.

INCLINE = math.radians(6)  # slight incline

# --- floor -----------------------------------
_box("floor", 2.4, 2.6, 0.04, (0, 0, -0.04), mat_floor)

# --- chassis pivot (tilted base) -------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0.02))
chassis = bpy.context.active_object
chassis.name = "chassis_pivot"
chassis.rotation_euler = (INCLINE, 0, 0)

# main running deck (a wide low box)
DECK_W = 0.55
DECK_D = 1.40
DECK_T = 0.03
deck = _box("deck", DECK_W, DECK_D, DECK_T, (0, 0, DECK_T/2), mat_dark)
deck.parent = chassis; deck.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 2 side rails (red plastic) running along the deck edges
for sx in (-1, +1):
    rail = _box(f"rail_{sx}", 0.05, DECK_D, 0.10,
                  (sx * (DECK_W/2 + 0.02), 0, 0.05), mat_rail)
    rail.parent = chassis; rail.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- belt + rollers --------------------------
BELT_W = DECK_W * 0.78
BELT_D = DECK_D - 0.18
BELT_Z = DECK_T + 0.005
# belt slab (a thin dark rubber sheet)
belt_slab = _box("belt_slab", BELT_W, BELT_D, 0.008, (0, 0, BELT_Z + 0.004), mat_belt)
belt_slab.parent = chassis; belt_slab.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 2 rollers at each end (front + rear)
ROLLER_R = 0.04
for sy in (-1, +1):
    rr = _cyl(f"roller_{sy}", ROLLER_R, ROLLER_R, BELT_W + 0.02, 'X',
                (0, sy * (BELT_D/2 + ROLLER_R/2), BELT_Z + 0.004),
                mat_steel, segments=18)
    rr.parent = chassis; rr.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    for sx in (-1, +1):
        cap = _cyl(f"roller_cap_{sy}_{sx}", ROLLER_R * 1.15, ROLLER_R * 1.15,
                     0.012, 'X',
                     (sx * (BELT_W/2 + 0.018), sy * (BELT_D/2 + ROLLER_R/2),
                      BELT_Z + 0.004),
                     mat_dark, segments=18)
        cap.parent = chassis; cap.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 8 belt segments laid along Y to suggest a tread surface; animate by
# translating their Y, wrapping around when they reach the end.
belt_segments = []
N_SEGS = 8
SEG_LEN = (BELT_D - 0.05) / N_SEGS
BELT_Z_TOP = BELT_Z + 0.013
for i in range(N_SEGS):
    y = -BELT_D/2 + (i + 0.5) * SEG_LEN
    s = _box(f"belt_line_{i}", BELT_W * 0.92, 0.012, 0.003,
               (0, y, BELT_Z_TOP), mat_belt_ln)
    s.parent = chassis; s.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    belt_segments.append((s, y))

# --- console upright posts (2 posts rising from the front of the deck) ---
POST_BASE_Y = BELT_D/2 + ROLLER_R + 0.06
for sx in (-1, +1):
    post = _cyl(f"post_{sx}", 0.020, 0.020, 0.80, 'Z',
                  (sx * (DECK_W/2 - 0.04), POST_BASE_Y, 0.40), mat_steel,
                  segments=14)
    post.parent = chassis; post.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- handlebars : U-shape horizontal bar at the top of the posts ---
HB_Z = 0.78
HB_Y = POST_BASE_Y
# horizontal bar across the front
hb_top = _cyl("hb_top", 0.020, 0.020, DECK_W - 0.04, 'X',
                (0, HB_Y - 0.10, HB_Z), mat_steel)
hb_top.parent = chassis; hb_top.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 horizontal grip extensions going back toward the user
for sx in (-1, +1):
    grip = _cyl(f"hb_grip_{sx}", 0.018, 0.018, 0.25, 'Y',
                  (sx * (DECK_W/2 - 0.04), HB_Y - 0.04, HB_Z), mat_grip)
    grip.parent = chassis; grip.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # heart-rate red pad on the grip
    pad = _box(f"hb_pad_{sx}", 0.025, 0.10, 0.006,
                 (sx * (DECK_W/2 - 0.04), HB_Y - 0.04, HB_Z + 0.020), mat_grip_red)
    pad.parent = chassis; pad.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- console (LCD + buttons) ---------------
CON_W = DECK_W - 0.08
CON_H = 0.20
CON_Y = HB_Y - 0.04
CON_Z = HB_Z + 0.04 + CON_H/2
# tilted backwards toward the user
con_tilt = math.radians(-22)
console = _box("console", CON_W, 0.03, CON_H,
                 (0, CON_Y, CON_Z), mat_dark,
                 rot=(con_tilt, 0, 0))
console.parent = chassis; console.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# LCD on the upper half of the console
lcd = _box("lcd_screen", CON_W * 0.85, 0.001, CON_H * 0.50,
             (0, CON_Y - 0.018, CON_Z + 0.025), mat_lcd,
             rot=(con_tilt, 0, 0))
lcd.parent = chassis; lcd.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 6 buttons in 2 rows below the LCD
for r in range(2):
    for c in range(3):
        bx = -CON_W/2 + 0.05 + c * (CON_W - 0.10) / 2
        by = CON_Y - 0.018
        bz = CON_Z - 0.04 - r * 0.04
        if r == 0 and c == 0:
            mat = mat_btn_grn   # start
        elif r == 1 and c == 2:
            mat = mat_btn_red   # stop
        else:
            mat = mat_btn
        btn = _box(f"btn_{r}_{c}", 0.04, 0.005, 0.025,
                     (bx, by, bz), mat, rot=(con_tilt, 0, 0))
        btn.parent = chassis; btn.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- safety-key lanyard hanging from the console -----
LANY_X = -0.05
LANY_Y = CON_Y - 0.04
LANY_Z = CON_Z - 0.12
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(LANY_X, LANY_Y, LANY_Z))
lanyard_pivot = bpy.context.active_object
lanyard_pivot.name = "lanyard_pivot"
lanyard_pivot.parent = chassis
lanyard_pivot.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# cord segments (3 short cylinders)
for k in range(3):
    seg = _cyl(f"lanyard_seg_{k}", 0.003, 0.003, 0.07, 'Z',
                 (0, 0, -k * 0.07 - 0.035), mat_lanyard, segments=8)
    seg.parent = lanyard_pivot
    seg.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# safety key (yellow square clip)
key = _box("safety_key", 0.020, 0.005, 0.030, (0, 0, -0.26), mat_key)
key.parent = lanyard_pivot
key.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ------------------------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Belt segments : scroll toward -Y, wrap at -BELT_D/2
SCROLL_SPEED = (BELT_D - 0.05) / DURATION * 2.0  # 2 full cycles per loop
for (seg, y0) in belt_segments:
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        offset = -SCROLL_SPEED * t * DURATION
        # wrap : modulo the belt length
        wrapped = ((y0 + offset) - (-BELT_D/2)) % (BELT_D - 0.05)
        new_y = -BELT_D/2 + wrapped
        seg.location = (0, new_y, BELT_Z_TOP)
        seg.keyframe_insert("location", frame=f)
    if seg.animation_data and seg.animation_data.action:
        for fc in seg.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# LCD cycles colour (workout mode flash : blue / cyan / green / yellow)
bsdf_lcd = mat_lcd.node_tree.nodes.get("Principled BSDF")
em_col = bsdf_lcd.inputs["Emission Color"]
em_str = bsdf_lcd.inputs["Emission Strength"]
COLORS = [
    (0.20, 0.55, 1.00),
    (0.30, 1.00, 0.85),
    (0.30, 1.00, 0.30),
    (1.00, 0.85, 0.20),
]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    idx = int(t * len(COLORS)) % len(COLORS)
    em_col.default_value = (*COLORS[idx], 1.0)
    em_str.default_value = 3.5 + 1.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 4.0))
    bpy.context.scene.frame_set(f)
    em_col.keyframe_insert(data_path="default_value", frame=f)
    em_str.keyframe_insert(data_path="default_value", frame=f)

# lanyard sways gently
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    lanyard_pivot.rotation_euler = (math.radians(6 * math.sin(2*math.pi*t * 1.5)), 0,
                                      math.radians(4 * math.sin(2*math.pi*t * 1.3 + 1.0)))
    lanyard_pivot.keyframe_insert("rotation_euler", frame=f)
if lanyard_pivot.animation_data and lanyard_pivot.animation_data.action:
    for fc in lanyard_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"TREAD_OK: {out_glb}", flush=True)
'''


def make_treadmill(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_tread_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "TREAD_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_treadmill(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
