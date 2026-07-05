"""Procedural 2-slot pop-up toaster (Blender headless).

Chrome body with brushed accent stripe + 2 horizontal slots on top + 2
bread slices that pop in and out + emissive red heating elements
visible inside + side lever + browning dial + 4 mode buttons + status
LED + drip tray underneath. Animation : bread starts down (cooking), pops
up at t=0.55, dial mode highlights at the same time, heating elements
glow throughout but flicker subtly.

CLI:
  python proc_toaster.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "toaster.glb"

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

mat_floor   = pbr_mat("floor",     (0.40, 0.32, 0.22), 0.00, 0.80)
mat_chrome  = pbr_mat("chrome",    (0.82, 0.84, 0.87), 1.00, 0.12)
mat_chrome2 = pbr_mat("chrome_bru",(0.65, 0.65, 0.68), 0.85, 0.40)
mat_dark    = pbr_mat("dark",      (0.10, 0.10, 0.11), 0.40, 0.40)
mat_slot    = pbr_mat("slot_dk",   (0.04, 0.04, 0.05), 0.20, 0.50)
mat_bread   = pbr_mat("bread",     (0.85, 0.65, 0.30), 0.00, 0.65)
mat_bread_t = pbr_mat("toasted",   (0.45, 0.20, 0.08), 0.00, 0.60)
mat_elem    = pbr_mat("element",   (0.40, 0.05, 0.02), 0.10, 0.30,
                          emission=((1.00, 0.20, 0.05), 8.0))
mat_dial    = pbr_mat("dial",      (0.18, 0.18, 0.20), 0.60, 0.30)
mat_dial_t  = pbr_mat("dial_top",  (0.85, 0.85, 0.87), 1.00, 0.20)
mat_lever   = pbr_mat("lever",     (0.92, 0.92, 0.90), 0.10, 0.30)
mat_lever_k = pbr_mat("lever_knob",(0.10, 0.10, 0.11), 0.10, 0.45)
mat_btn     = pbr_mat("button",    (0.20, 0.20, 0.22), 0.30, 0.35)
mat_btn_lit = pbr_mat("btn_red",   (0.85, 0.18, 0.18), 0.10, 0.20,
                          emission=((1.00, 0.25, 0.20), 2.0))
mat_led     = pbr_mat("led",       (0.85, 0.18, 0.18), 0.10, 0.20,
                          emission=((1.00, 0.20, 0.10), 4.0))

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

def _sphere(name, R, location, mat, u=12, v=8):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# Conventions : toaster faces -Y. Slots are on top, parallel to X.

# --- counter -----------------------
_box("floor", 0.80, 0.60, 0.04, (0, 0, -0.04), mat_floor)

# Toaster dims (W along X, D along Y, H along Z)
T_W = 0.32
T_D = 0.18
T_H = 0.20
T_Z = T_H/2 + 0.02
_box("body", T_W, T_D, T_H, (0, 0, T_Z), mat_chrome)
# brushed accent stripe (horizontal mid-section)
_box("stripe_mid", T_W + 0.004, T_D + 0.004, 0.020,
       (0, 0, T_Z + 0.005), mat_chrome2)

# 4 rubber feet
for sx in (-1, +1):
    for sy in (-1, +1):
        _cyl(f"foot_{sx}_{sy}", 0.012, 0.012, 0.014, 'Z',
               (sx * (T_W/2 - 0.04), sy * (T_D/2 - 0.04), 0.014/2),
               mat_dark)

# --- 2 slots on the top --------------
TOP_Z = T_Z + T_H/2
SLOT_W = 0.10
SLOT_D = T_D - 0.04
for sx in (-1, +1):
    slot_x = sx * 0.07
    _box(f"slot_{sx}", SLOT_W, SLOT_D, 0.015,
           (slot_x, 0, TOP_Z - 0.0075), mat_slot)
    # slot rim (chrome surround)
    _box(f"slot_rim_top_{sx}", SLOT_W + 0.012, SLOT_D + 0.012, 0.003,
           (slot_x, 0, TOP_Z + 0.0015), mat_chrome2)

# --- 2 bread slices (parented to pivots so they pop up/down) ----
def make_bread(name, slot_x, toasted_amt):
    """Bread is a slightly rounded slab. toasted_amt 0..1 darkens it."""
    bpy.ops.object.empty_add(type='PLAIN_AXES',
                              location=(slot_x, 0, T_Z))
    pv = bpy.context.active_object
    pv.name = name + "_pivot"
    # bread slab (its mesh goes from -0.04 below to +0.05 above the empty)
    # The bread is L=0.085 wide, D=0.075 deep, H=0.09 tall.
    body = _box(name, 0.085, 0.075, 0.09, (0, 0, 0.045), mat_bread)
    body.parent = pv; body.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # toast browning layer (thin slab on top half, sitting just above the bread)
    if toasted_amt > 0:
        crust = _box(name + "_crust", 0.082, 0.072, 0.012,
                       (0, 0, 0.090), mat_bread_t)
        crust.parent = pv; crust.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    return pv

bread_L = make_bread("bread_L", -0.07, 1)
bread_R = make_bread("bread_R", +0.07, 1)

# --- heating elements (4 thin emissive cylinders inside, between the bread)
# Each cylinder is along Y, sitting at fixed X positions.
ELEM_Y = 0  # centered along Y, but the cylinder spans Y depth
ELEM_LEN = SLOT_D - 0.02
for k, (ex, ez) in enumerate(((-0.115, T_Z + 0.04),
                                (-0.025, T_Z + 0.04),
                                ( 0.025, T_Z + 0.04),
                                ( 0.115, T_Z + 0.04))):
    _cyl(f"element_{k}", 0.004, 0.004, ELEM_LEN, 'Y',
           (ex, ELEM_Y, ez), mat_elem, segments=10)

# --- lever on the right side (the push-down handle) ----
LEVER_X = T_W/2 + 0.005
LEVER_Y = T_D/2 - 0.05
LEVER_Z_TOP = T_Z + T_H/2 - 0.02
LEVER_Z_BOT = T_Z - T_H/2 + 0.02
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(LEVER_X, LEVER_Y, LEVER_Z_BOT))
lever_pivot = bpy.context.active_object
lever_pivot.name = "lever_pivot"
# vertical lever bar (a slot/track really, but here a thin chrome bar)
_box("lever_track", 0.015, 0.004, T_H * 0.80,
       (LEVER_X, LEVER_Y, T_Z), mat_chrome2)
# lever knob (the part that goes down) — parented to lever_pivot so we can
# slide it up/down by translating the pivot's Z.
knob = _box("lever_knob", 0.022, 0.012, 0.030,
              (0, 0, 0.015), mat_lever_k)
knob.parent = lever_pivot
knob.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# small white indicator on the front of the knob
_box("lever_indicator", 0.018, 0.001, 0.005,
       (0, -0.007, 0.015), mat_lever)  # parented later

# --- browning dial on the front of the body (along -Y face) ---
DIAL_X = 0.00
DIAL_Y = -T_D/2 - 0.010
DIAL_Z = T_Z - T_H * 0.20
_cyl("dial_body", 0.025, 0.025, 0.010, 'Y',
       (DIAL_X, DIAL_Y, DIAL_Z), mat_dial, segments=18)
_cyl("dial_top", 0.025, 0.020, 0.005, 'Y',
       (DIAL_X, DIAL_Y - 0.0075, DIAL_Z), mat_dial_t, segments=18)
# dial pointer (a chrome line on the front)
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(DIAL_X, DIAL_Y - 0.011, DIAL_Z))
dial_pivot = bpy.context.active_object
dial_pivot.name = "dial_pivot"
dial_pivot.rotation_euler = (math.radians(-30), 0, 0)
ptr = _box("dial_pointer", 0.002, 0.001, 0.018, (0, 0, 0.010), mat_chrome)
ptr.parent = dial_pivot
ptr.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 4 mode buttons (small round buttons on the front face) ----
for k in range(4):
    bx = -T_W * 0.32 + k * (T_W * 0.16)
    bz = T_Z - T_H * 0.32
    if k == 0:
        mat = mat_btn_lit
    else:
        mat = mat_btn
    _cyl(f"mode_btn_{k}", 0.010, 0.010, 0.008, 'Y',
           (bx, -T_D/2 - 0.0055, bz), mat, segments=10)

# --- LED status light (small dot on the front) ----
_sphere("led", 0.006, (T_W * 0.40, -T_D/2 - 0.006, T_Z - T_H * 0.10), mat_led)

# --- drip tray (a thin chrome slab sticking out the back) ---
_box("drip_tray", T_W - 0.04, 0.03, 0.012,
       (0, T_D/2 + 0.018, T_Z - T_H/2 + 0.012), mat_chrome2)

# --- cord (a thin black cord coming out the back, drooping down) ---
CORD_PTS = [
    (T_W * 0.20, T_D/2 + 0.001, T_Z - T_H * 0.20),
    (T_W * 0.22, T_D/2 + 0.05, T_Z - T_H * 0.30),
    (T_W * 0.25, T_D/2 + 0.10, 0.04),
]
for i in range(len(CORD_PTS) - 1):
    p0 = CORD_PTS[i]; p1 = CORD_PTS[i+1]
    mx = (p0[0]+p1[0])/2; my = (p0[1]+p1[1])/2; mz = (p0[2]+p1[2])/2
    dx, dy, dz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
    L = math.sqrt(dx*dx + dy*dy + dz*dz)
    seg = _cyl(f"cord_seg_{i}", 0.005, 0.005, L, 'Z', (0,0,0), mat_dark)
    seg.location = (mx, my, mz)
    direction = mathutils.Vector((dx, dy, dz)).normalized()
    seg.rotation_mode = 'QUATERNION'
    seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)

# --- animation ---------------------
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Bread + lever cycle :
#  - t = [0.00, 0.55] : bread is DOWN (inside the toaster), lever is at bottom
#  - t = [0.55, 0.62] : bread POPS UP quickly (with a small overshoot), lever
#                       slides up
#  - t = [0.62, 1.00] : bread is UP, idle
BREAD_DOWN = 0.0     # delta Z from rest = 0 (already at rest position)
BREAD_UP   = 0.085   # rises 8.5 cm
LEVER_DOWN_DZ = 0.0
LEVER_UP_DZ   = T_H * 0.55

def cycle(t):
    if t < 0.55:
        return 0.0
    elif t < 0.62:
        u = (t - 0.55) / 0.07
        # ease-out with small overshoot at end
        y = 1.0 - (1.0 - u)**2
        if u > 0.85:
            # add a tiny bounce
            y += 0.06 * math.sin((u - 0.85) / 0.15 * math.pi)
        return y
    else:
        return 1.0

# Bread pivots
for pv in (bread_L, bread_R):
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        c = cycle(t)
        bpy.context.scene.frame_set(f)
        pv.location = (pv.location.x, pv.location.y,
                        T_Z + c * BREAD_UP)
        pv.keyframe_insert("location", frame=f)
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

# Lever
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    c = cycle(t)
    bpy.context.scene.frame_set(f)
    lever_pivot.location = (LEVER_X, LEVER_Y, LEVER_Z_BOT + c * LEVER_UP_DZ)
    lever_pivot.keyframe_insert("location", frame=f)
if lever_pivot.animation_data and lever_pivot.animation_data.action:
    for fc in lever_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Heating elements glow strongly during cooking (t < 0.55), fade out after
bsdf_el = mat_elem.node_tree.nodes.get("Principled BSDF")
em_el = bsdf_el.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    if t < 0.55:
        base = 7.0 + 2.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 6.0))
        base += 1.0 * math.sin(2*math.pi*t * 11.0)  # flicker
    elif t < 0.75:
        u = (t - 0.55) / 0.20
        base = 7.0 * (1.0 - u)
    else:
        base = 0.0
    bpy.context.scene.frame_set(f)
    em_el.default_value = max(0.0, base)
    em_el.keyframe_insert(data_path="default_value", frame=f)

# Status LED stays on during cooking, then blinks ready after
bsdf_led = mat_led.node_tree.nodes.get("Principled BSDF")
em_led = bsdf_led.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    if t < 0.55:
        val = 3.5 + 0.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 4.0))
    else:
        val = 1.0 + 3.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 8.0))
    bpy.context.scene.frame_set(f)
    em_led.default_value = val
    em_led.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"TOAST_OK: {out_glb}", flush=True)
'''


def make_toaster(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_toast_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "TOAST_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_toaster(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
