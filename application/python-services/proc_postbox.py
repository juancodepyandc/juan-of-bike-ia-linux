"""Procedural British cylindrical post box (Blender headless).

Pillar-style Royal Mail post box : circular concrete base + tall red
cylindrical body + slot for letters + access door with chrome padlock
+ collection times plaque + domed cap with finial + ROYAL MAIL letters.
Animation : letter envelope slides into the slot (translation -Y + tilt
into slot) then disappears + access door vibrates slightly when letter
lands inside.

CLI:
  python proc_postbox.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "postbox.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough, emission=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if emission is not None and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission[0], 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission[1]
    return m

mat_floor    = pbr_mat("floor",     (0.25, 0.24, 0.22), 0.00, 0.85)
mat_pave     = pbr_mat("pave",      (0.45, 0.43, 0.40), 0.00, 0.85)
mat_red      = pbr_mat("red",       (0.55, 0.08, 0.06), 0.10, 0.40)
mat_red_d    = pbr_mat("red_dk",    (0.35, 0.04, 0.03), 0.10, 0.45)
mat_dark     = pbr_mat("dark",      (0.06, 0.06, 0.07), 0.30, 0.45)
mat_chrome   = pbr_mat("chrome",    (0.80, 0.82, 0.85), 1.00, 0.18)
mat_gold     = pbr_mat("gold",      (0.95, 0.80, 0.30), 1.00, 0.25,
                          emission=((1.00, 0.85, 0.40), 1.5))
mat_white    = pbr_mat("white",     (0.95, 0.93, 0.88), 0.00, 0.45)
mat_envelope = pbr_mat("envelope",  (0.92, 0.90, 0.82), 0.00, 0.55)
mat_stamp    = pbr_mat("stamp",     (0.85, 0.18, 0.18), 0.00, 0.45)

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=24, rot=None):
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

def _sphere(name, R, location, mat, u=16, v=12, scale=(1,1,1)):
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

# Conventions : postbox faces -Y (slot + door on -Y side). Up = +Z.

# --- pavement ----------------------
_box("floor", 1.6, 1.4, 0.04, (0, 0, -0.04), mat_floor)
_cyl("pave_disc", 0.55, 0.55, 0.025, 'Z', (0, 0, 0.013), mat_pave, segments=32)

# --- concrete base / collar ---------
BASE_Z = 0.026
BASE_H = 0.05
_cyl("base_collar", 0.34, 0.34, BASE_H, 'Z',
       (0, 0, BASE_Z + BASE_H/2), mat_pave, segments=32)

# --- main cylindrical body ---------
BODY_R = 0.30
BODY_H = 1.40
BODY_Z = BASE_Z + BASE_H + BODY_H/2
_cyl("body", BODY_R, BODY_R, BODY_H, 'Z', (0, 0, BODY_Z), mat_red, segments=40)

# small ring at top of body (where dome cap meets)
_cyl("body_top_ring", BODY_R * 1.04, BODY_R * 1.04, 0.025, 'Z',
       (0, 0, BODY_Z + BODY_H/2 + 0.012), mat_red_d, segments=40)

# small ring at bottom (transition to base)
_cyl("body_bot_ring", BODY_R * 1.04, BODY_R * 1.04, 0.025, 'Z',
       (0, 0, BODY_Z - BODY_H/2 - 0.012), mat_red_d, segments=40)

# --- letter slot (a horizontal recess on -Y side, upper portion) ---
SLOT_W = 0.36
SLOT_H = 0.04
SLOT_Z = BODY_Z + BODY_H * 0.20
SLOT_Y = -BODY_R - 0.005
# the recess : a thin dark box
_box("slot_recess", SLOT_W, 0.03, SLOT_H,
       (0, SLOT_Y, SLOT_Z), mat_dark)
# slot lip frame (chrome ring around the slot)
_box("slot_lip_top", SLOT_W + 0.04, 0.005, 0.012,
       (0, SLOT_Y - 0.012, SLOT_Z + SLOT_H/2 + 0.006), mat_chrome)
_box("slot_lip_bot", SLOT_W + 0.04, 0.005, 0.012,
       (0, SLOT_Y - 0.012, SLOT_Z - SLOT_H/2 - 0.006), mat_chrome)
for sx in (-1, +1):
    _box(f"slot_lip_side_{sx}", 0.012, 0.005, SLOT_H + 0.024,
           (sx * (SLOT_W/2 + 0.012), SLOT_Y - 0.012, SLOT_Z), mat_chrome)

# slot label "POST OFFICE" or "LETTERS" : gold strip above the slot
_box("slot_label", SLOT_W * 0.6, 0.003, 0.025,
       (0, SLOT_Y - 0.018, SLOT_Z + SLOT_H/2 + 0.040), mat_gold)

# --- access door (large rectangular door on -Y side, lower portion) ----
# This is a static panel with hinge bumps + chrome padlock
DOOR_W = 0.42
DOOR_H = 0.65
DOOR_Y = -BODY_R + 0.001  # slightly inset into the cylinder
DOOR_Z = BODY_Z - BODY_H * 0.12
# door panel parented to a pivot so we can vibrate it slightly when letter lands
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(0, DOOR_Y, DOOR_Z))
door_pivot = bpy.context.active_object
door_pivot.name = "door_pivot"

door_body = _box("door_body", DOOR_W, 0.015, DOOR_H,
                   (0, -0.008, 0), mat_red_d)
door_body.parent = door_pivot
door_body.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 2 hinge bumps on the -X edge of the door
for sz in (-1, +1):
    h = _box(f"door_hinge_{sz}", 0.018, 0.012, 0.030,
               (-DOOR_W/2 + 0.009, -0.014, sz * DOOR_H * 0.30), mat_dark)
    h.parent = door_pivot
    h.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# chrome padlock on the +X side of the door
lock_body = _box("padlock_body", 0.030, 0.022, 0.040,
                   (DOOR_W/2 - 0.025, -0.020, 0), mat_chrome)
lock_body.parent = door_pivot; lock_body.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# shackle (a U-shape : 2 verticals + 1 horizontal)
for sx in (-1, +1):
    sh = _cyl(f"shackle_v_{sx}", 0.0035, 0.0035, 0.025, 'Z',
                (DOOR_W/2 - 0.025 + sx * 0.010, -0.020, 0.026), mat_chrome, segments=10)
    sh.parent = door_pivot
    sh.matrix_parent_inverse = mathutils.Matrix.Identity(4)
sh_top = _cyl("shackle_top", 0.0035, 0.0035, 0.020, 'X',
                (DOOR_W/2 - 0.025, -0.020, 0.038), mat_chrome, segments=10)
sh_top.parent = door_pivot
sh_top.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# small keyhole
_cyl("keyhole", 0.004, 0.004, 0.001, 'Y',
       (DOOR_W/2 - 0.025, -0.026, 0), mat_dark, segments=10)

# --- collection times plaque (small white rectangle below the slot, above the door) ---
PLAQUE_Z = BODY_Z + BODY_H * 0.05
_box("plaque", 0.16, 0.005, 0.06,
       (0, -BODY_R - 0.0025, PLAQUE_Z), mat_white)
# 2 horizontal black lines on the plaque (suggesting times)
for k in range(2):
    _box(f"plaque_line_{k}", 0.10, 0.001, 0.003,
           (0, -BODY_R - 0.006, PLAQUE_Z + 0.012 - k * 0.018), mat_dark)

# --- ROYAL MAIL / GR letters in gold around the top of the body ---
# Implement as a single gold band with a few raised cylindrical "letters"
_cyl("brand_band", BODY_R + 0.005, BODY_R + 0.005, 0.05, 'Z',
       (0, 0, BODY_Z + BODY_H * 0.40), mat_gold, segments=40)

# 4 small raised letters (E R II R cypher feel) around the band, only on -Y face
for k, off in enumerate((-0.10, -0.035, 0.035, 0.10)):
    a = math.pi + off  # near -Y direction
    bx = (BODY_R + 0.008) * math.cos(a)
    by = (BODY_R + 0.008) * math.sin(a)
    _box(f"cypher_{k}", 0.012, 0.004, 0.025,
           (bx, by, BODY_Z + BODY_H * 0.40), mat_red_d,
           rot=(0, 0, a))

# --- domed top cap with finial ---
DOME_BASE_Z = BODY_Z + BODY_H/2 + 0.024
# 3 stacked discs forming a stepped dome
_cyl("dome_step1", BODY_R * 1.06, BODY_R * 1.06, 0.04, 'Z',
       (0, 0, DOME_BASE_Z + 0.02), mat_red, segments=40)
_cyl("dome_step2", BODY_R * 0.92, BODY_R * 0.92, 0.04, 'Z',
       (0, 0, DOME_BASE_Z + 0.05), mat_red, segments=40)
# domed top : half-sphere
_sphere("dome_top", BODY_R * 0.80, (0, 0, DOME_BASE_Z + 0.08), mat_red,
         u=24, v=14, scale=(1.0, 1.0, 0.55))
# brass finial cap on top
_sphere("dome_finial", 0.04, (0, 0, DOME_BASE_Z + 0.16), mat_gold)
_cyl("finial_post", 0.012, 0.012, 0.04, 'Z',
       (0, 0, DOME_BASE_Z + 0.13), mat_gold)

# --- envelope (white rectangle with a red stamp) — parented to anim pivot ---
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(0, -BODY_R - 0.30, SLOT_Z + 0.08))
env_pivot = bpy.context.active_object
env_pivot.name = "envelope_pivot"

env_body = _box("envelope_body", 0.18, 0.005, 0.12,
                  (0, 0, 0), mat_envelope)
env_body.parent = env_pivot
env_body.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# red stamp in top-right corner
env_stamp = _box("env_stamp", 0.03, 0.001, 0.035,
                   (0.06, -0.0035, 0.035), mat_stamp)
env_stamp.parent = env_pivot
env_stamp.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 3 thin lines suggesting address
for k in range(3):
    ln = _box(f"env_line_{k}", 0.08, 0.0005, 0.002,
                (-0.03, -0.0035, -0.005 - k * 0.012), mat_dark)
    ln.parent = env_pivot
    ln.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation -----------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Envelope animation phases :
#   t=[0.00, 0.15] : envelope idle outside (visible)
#   t=[0.15, 0.45] : envelope slides toward slot (Y goes from -0.30 to 0) + tilts forward
#   t=[0.45, 0.55] : envelope disappears inside (Y stays, Z drops below slot)
#   t=[0.55, 1.00] : envelope hidden inside (scale 0 or below slot)
ENV_START = mathutils.Vector((0, -BODY_R - 0.30, SLOT_Z + 0.08))
ENV_SLOT  = mathutils.Vector((0, -BODY_R + 0.01, SLOT_Z))
ENV_INSIDE= mathutils.Vector((0, -BODY_R + 0.10, SLOT_Z - 0.30))

def env_pose(t):
    if t < 0.15:
        return ENV_START, 0.0
    elif t < 0.45:
        u = (t - 0.15) / 0.30
        # ease-in
        u = u * u
        pos = ENV_START.lerp(ENV_SLOT, u)
        return pos, math.radians(-25 * u)
    elif t < 0.55:
        u = (t - 0.45) / 0.10
        pos = ENV_SLOT.lerp(ENV_INSIDE, u)
        return pos, math.radians(-25 * (1 - u * 0.5))
    else:
        return ENV_INSIDE, math.radians(-50)

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    pos, rot_x = env_pose(t)
    bpy.context.scene.frame_set(f)
    env_pivot.location = pos
    env_pivot.rotation_euler = (rot_x, 0, 0)
    env_pivot.keyframe_insert("location", frame=f)
    env_pivot.keyframe_insert("rotation_euler", frame=f)
if env_pivot.animation_data and env_pivot.animation_data.action:
    for fc in env_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Door vibrates briefly when letter lands (t ≈ 0.50)
def door_vibrate(t):
    if t < 0.50 or t > 0.65:
        return 0.0
    # damped oscillation
    local = (t - 0.50) / 0.15
    amp = 0.012 * math.exp(-local * 5.0)
    return amp * math.sin(local * 2*math.pi * 8.0)

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    door_pivot.location = (0, DOOR_Y + door_vibrate(t), DOOR_Z)
    door_pivot.keyframe_insert("location", frame=f)
if door_pivot.animation_data and door_pivot.animation_data.action:
    for fc in door_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Gold band / label slowly pulse for a "still vital postbox" feel
bsdf_g = mat_gold.node_tree.nodes.get("Principled BSDF")
em_g = bsdf_g.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_g.default_value = 1.0 + 0.7 * (0.5 + 0.5 * math.sin(2*math.pi*t * 0.5))
    bpy.context.scene.frame_set(f)
    em_g.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"POST_OK: {out_glb}", flush=True)
'''


def make_postbox(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_post_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "POST_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_postbox(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
