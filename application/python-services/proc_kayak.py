"""Procedural kayak with double paddle (Blender headless).

Tapered red-orange hull with pointed bow + stern + cockpit opening +
headrest + 2 deck cargo bungee straps + double paddle with 2 blue
blades. The kayak sits on a translucent blue water plane. Animation :
the double paddle alternates side-to-side stroking : Z rotation around
its own axis + dip/lift around X, simulating the rower's cadence.

CLI:
  python proc_kayak.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "kayak.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough, alpha=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if alpha is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
            m.blend_method = 'BLEND'
    return m

mat_water    = pbr_mat("water",     (0.10, 0.35, 0.55), 0.05, 0.10, alpha=0.55)
mat_hull     = pbr_mat("hull",      (0.95, 0.45, 0.10), 0.05, 0.35)
mat_hull_d   = pbr_mat("hull_dk",   (0.65, 0.25, 0.05), 0.05, 0.40)
mat_cockpit  = pbr_mat("cockpit",   (0.10, 0.10, 0.12), 0.20, 0.45)
mat_seat     = pbr_mat("seat",      (0.18, 0.18, 0.20), 0.05, 0.55)
mat_strap    = pbr_mat("strap",     (0.25, 0.25, 0.28), 0.05, 0.65)
mat_paddle_s = pbr_mat("paddle_sh", (0.18, 0.10, 0.05), 0.05, 0.55)
mat_paddle_b = pbr_mat("paddle_bl", (0.18, 0.50, 0.92), 0.10, 0.30)

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

# Conventions : kayak along Y, bow at -Y (forward). Up = +Z.

# --- water plane ---
_box("water_plane", 4.0, 5.0, 0.04, (0, 0, -0.04), mat_water)

# Kayak dims
HULL_LEN = 3.20
HULL_W = 0.45
HULL_H = 0.18

# --- hull main body (a flattened ellipsoid)
_sphere("hull_body", 0.30, (0, 0, HULL_H/2),
         mat_hull, u=24, v=16,
         scale=(HULL_W / 2 / 0.30, HULL_LEN / 2 / 0.30, HULL_H / 2 / 0.30))

# pointed bow extension (front, -Y)
_sphere("hull_bow", 0.30, (0, -HULL_LEN/2 + 0.10, HULL_H/2),
         mat_hull, u=18, v=12,
         scale=(HULL_W * 0.55 / 0.60, 0.55 / 0.30, HULL_H * 0.6 / 0.60))
# pointed stern extension (back, +Y)
_sphere("hull_stern", 0.30, (0, HULL_LEN/2 - 0.10, HULL_H/2),
         mat_hull, u=18, v=12,
         scale=(HULL_W * 0.55 / 0.60, 0.55 / 0.30, HULL_H * 0.6 / 0.60))

# darker stripe along the side waterline
_box("hull_stripe_L", 0.005, HULL_LEN * 0.85, 0.02,
       (-HULL_W/2 - 0.001, 0, HULL_H * 0.40), mat_hull_d)
_box("hull_stripe_R", 0.005, HULL_LEN * 0.85, 0.02,
       (+HULL_W/2 + 0.001, 0, HULL_H * 0.40), mat_hull_d)

# --- cockpit opening (oval recess on top, slightly forward of center) ---
COCK_Y = -0.10
COCK_W = HULL_W * 0.60
COCK_D = 0.55
COCK_Z = HULL_H + 0.02
# rim
_sphere("cockpit_rim", 0.30, (0, COCK_Y, COCK_Z),
          mat_hull_d, u=20, v=14,
          scale=(COCK_W / 2 / 0.30, COCK_D / 2 / 0.30, 0.05))
# inner dark hole
_sphere("cockpit_inner", 0.30, (0, COCK_Y, COCK_Z + 0.008),
          mat_cockpit, u=20, v=14,
          scale=((COCK_W - 0.05) / 2 / 0.30, (COCK_D - 0.05) / 2 / 0.30, 0.04))
# seat at the bottom of the cockpit (a small dark slab inside)
_sphere("seat", 0.30, (0, COCK_Y, COCK_Z - 0.005),
          mat_seat, u=16, v=12,
          scale=((COCK_W - 0.10) / 2 / 0.30, (COCK_D - 0.20) / 2 / 0.30, 0.02))

# headrest behind the seat (small wedge at +Y end of cockpit)
_box("headrest", COCK_W * 0.5, 0.08, 0.06,
       (0, COCK_Y + COCK_D/2 - 0.10, COCK_Z + 0.04), mat_seat,
       rot=(math.radians(-15), 0, 0))

# --- 2 deck cargo bungee straps on the front deck ---
DECK_FRONT_Y = -0.80
for k, ystrap in enumerate((DECK_FRONT_Y, DECK_FRONT_Y - 0.20)):
    # cross strap : 4 short cyl segments making an X pattern
    for sx in (-1, +1):
        # diagonal strap from one side to the other
        p0 = mathutils.Vector((-sx * HULL_W * 0.35, ystrap, HULL_H + 0.012))
        p1 = mathutils.Vector((+sx * HULL_W * 0.35, ystrap + 0.08, HULL_H + 0.012))
        d = p1 - p0
        L = d.length
        mid = (p0 + p1) * 0.5
        seg = _cyl(f"strap_{k}_{sx}", 0.004, 0.004, L, 'Z', (0,0,0), mat_strap, segments=6)
        seg.location = mid
        direction = d.normalized()
        seg.rotation_mode = 'QUATERNION'
        seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
    # 4 strap anchor points (small spheres at the deck edges)
    for sx in (-1, +1):
        for sy in (-1, +1):
            _sphere(f"strap_anchor_{k}_{sx}_{sy}", 0.008,
                      (sx * HULL_W * 0.35, ystrap + sy * 0.04, HULL_H + 0.012),
                      mat_strap)

# --- double paddle (animated) ---
# Paddle is centered at the rower's hands (above the cockpit), with 2
# blades on each end of a 1.6 m shaft.
PADDLE_LEN = 1.80
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, COCK_Y - 0.10, COCK_Z + 0.30))
paddle_pivot = bpy.context.active_object
paddle_pivot.name = "paddle_pivot"
# shaft along X
shaft = _cyl("paddle_shaft", 0.018, 0.018, PADDLE_LEN, 'X',
               (0, 0, 0), mat_paddle_s, segments=12)
shaft.parent = paddle_pivot
shaft.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 grip wraps (where rower holds)
for sx in (-1, +1):
    grip = _cyl(f"paddle_grip_{sx}", 0.022, 0.022, 0.10, 'X',
                  (sx * 0.18, 0, 0), mat_paddle_s, segments=12)
    grip.parent = paddle_pivot
    grip.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 blades at the ends (flat blue paddles)
for sx in (-1, +1):
    blade = _box(f"paddle_blade_{sx}", 0.18, 0.030, 0.005,
                   (sx * (PADDLE_LEN/2 + 0.08), 0, 0), mat_paddle_b)
    blade.parent = paddle_pivot
    blade.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # blade tip (slightly tapered)
    tip = _box(f"paddle_tip_{sx}", 0.12, 0.030, 0.005,
                 (sx * (PADDLE_LEN/2 + 0.20), 0, 0), mat_paddle_b)
    tip.parent = paddle_pivot
    tip.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation -----------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Paddle alternates : left blade dips down + back, right blade lifts up + forward,
# then swap. This is rotation around Y (Y-axis is forward).
HOME_LOC = paddle_pivot.location.copy()
PAD_AMP = math.radians(40)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # Y rotation : alternates between -PAD_AMP and +PAD_AMP at 1 Hz
    roll_y = PAD_AMP * math.sin(2*math.pi*t * 1.0)
    # X tilt : as left blade dips, paddle tilts forward slightly
    pitch_x = math.radians(8) * math.sin(2*math.pi*t * 1.0 + math.pi/2)
    # location bob slightly (rower's body sways)
    bob_z = 0.02 * math.sin(2*math.pi*t * 2.0)
    paddle_pivot.location = (HOME_LOC.x, HOME_LOC.y, HOME_LOC.z + bob_z)
    paddle_pivot.rotation_euler = (pitch_x, roll_y, 0)
    paddle_pivot.keyframe_insert("location", frame=f)
    paddle_pivot.keyframe_insert("rotation_euler", frame=f)
if paddle_pivot.animation_data and paddle_pivot.animation_data.action:
    for fc in paddle_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"KAYAK_OK: {out_glb}", flush=True)
'''


def make_kayak(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_kayak_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "KAYAK_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_kayak(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
