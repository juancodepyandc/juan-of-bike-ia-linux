"""Procedural fortune-teller's crystal ball (Blender headless).

Brass 3-claw stand + translucent glass sphere + 3 emissive inner orbs
that orbit on tilted planes. Each orb has its own colour + rotation
speed.

CLI:
  python proc_crystal_ball.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "ball.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough, emission=None, alpha=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if emission is not None and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission[0], 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission[1]
        if alpha is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
            m.blend_method = 'BLEND'
    return m

mat_brass    = pbr_mat("brass",        (0.86, 0.62, 0.20), 1.00, 0.28)
mat_glass    = pbr_mat("crystal_glass",(0.92, 0.94, 1.00), 0.00, 0.04, alpha=0.20)
mat_orb_blue = pbr_mat("orb_blue",     (0.20, 0.40, 1.00), 0.00, 0.10,
                          emission=((0.30, 0.50, 1.00), 4.0))
mat_orb_pink = pbr_mat("orb_pink",     (1.00, 0.30, 0.60), 0.00, 0.10,
                          emission=((1.00, 0.40, 0.70), 4.0))
mat_orb_gold = pbr_mat("orb_gold",     (1.00, 0.78, 0.30), 0.00, 0.10,
                          emission=((1.00, 0.85, 0.40), 4.0))
mat_cloth    = pbr_mat("table_cloth",  (0.45, 0.08, 0.12), 0.00, 0.65)
mat_floor    = pbr_mat("floor",        (0.10, 0.10, 0.12), 0.00, 0.85)

def _cyl(name, R1, R2, depth, axis, location, mat, segments=20):
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
    return obj

def _sphere(name, R, location, mat, u=20, v=14):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- floor + table cloth -----------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
fl = bpy.context.active_object; fl.name = "floor"
fl.scale = (2.0, 2.0, 0.04); bpy.ops.object.transform_apply(scale=True)
fl.data.materials.append(mat_floor)

# table cloth (a wide thin disc with a stand on top)
_cyl("cloth", 0.55, 0.55, 0.02, 'Z', (0, 0, 0.01), mat_cloth, segments=32)

# --- brass 3-claw stand ------------------------------------
STAND_Z = 0.02
BALL_R = 0.18
BALL_Z = STAND_Z + 0.12 + BALL_R   # ball sits on top of the claws

# central post
_cyl("stand_post", 0.025, 0.025, 0.12, 'Z',
       (0, 0, STAND_Z + 0.06), mat_brass)
# 3 curved claws (approximate with thin boxes angled upward)
for k in range(3):
    a = k * 2 * math.pi / 3
    cx = math.cos(a) * 0.07
    cy = math.sin(a) * 0.07
    # claw goes from post top to slightly higher than ball bottom on the
    # outward side
    end_x = math.cos(a) * (BALL_R * 0.95)
    end_y = math.sin(a) * (BALL_R * 0.95)
    end_z = STAND_Z + 0.12 + BALL_R * 0.30
    mid = ((cx + end_x) / 2, (cy + end_y) / 2,
            (STAND_Z + 0.10 + end_z) / 2)
    bpy.ops.mesh.primitive_cube_add(size=1, location=mid)
    claw = bpy.context.active_object
    claw.name = f"claw_{k}"
    length = math.hypot(end_x - cx, end_y - cy)
    claw.scale = (length * 1.2, 0.018, 0.018)
    bpy.ops.object.transform_apply(scale=True)
    yaw = math.atan2(end_y - cy, end_x - cx)
    pitch = -math.atan2(end_z - (STAND_Z + 0.10),
                          math.hypot(end_x - cx, end_y - cy))
    claw.rotation_euler = (0, pitch, yaw)
    claw.data.materials.append(mat_brass)

# decorative ring around the stand top
_cyl("stand_ring", 0.10, 0.10, 0.012, 'Z',
       (0, 0, STAND_Z + 0.11), mat_brass)
# base disc at the bottom of the post
_cyl("stand_base", 0.07, 0.07, 0.018, 'Z',
       (0, 0, STAND_Z + 0.009), mat_brass)

# --- crystal ball (translucent glass sphere) ------------------
ball = _sphere("crystal_ball", BALL_R, (0, 0, BALL_Z), mat_glass, u=32, v=20)

# --- 3 inner orbs orbiting around the ball centre -------------
# Each orb is parented to its own pivot empty centred at the ball centre,
# and the pivot rotates around its tilted local axis.
orb_data = []   # (pivot, orb)
ORB_CONFIGS = [
    (mat_orb_blue, 0.08, math.radians( 12), math.radians(  0), 1.0),
    (mat_orb_pink, 0.10, math.radians( 65), math.radians(120), -0.7),
    (mat_orb_gold, 0.07, math.radians(110), math.radians(230), 1.4),
]
for (mat, orbit_R, tilt_x, tilt_z, signed_turns_per_loop) in ORB_CONFIGS:
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, BALL_Z))
    pv = bpy.context.active_object
    pv.name = f"orb_pivot_{mat.name}"
    pv.rotation_euler = (tilt_x, 0, tilt_z)

    orb = _sphere(f"orb_{mat.name}", 0.022, (0, 0, 0), mat, u=14, v=10)
    orb.parent = pv
    orb.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    orb.location = (orbit_R, 0, 0)

    orb_data.append((pv, signed_turns_per_loop))

# --- animation -------------------------------------------
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# Each pivot rotates around its LOCAL Z axis (the orbit axis after the tilt)
for (pv, turns) in orb_data:
    base_x, base_y, _ = pv.rotation_euler
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        pv.rotation_euler = (base_x, base_y, turns * 2 * math.pi * t)
        pv.keyframe_insert("rotation_euler", frame=f)
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# orbs' emission pulses (3 different phases)
for k, (mat, _, _, _, _) in enumerate(ORB_CONFIGS):
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    em = bsdf.inputs["Emission Strength"]
    phase = k * 2 * math.pi / 3
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        em.default_value = 2.5 + 2.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 2 + phase))
        bpy.context.scene.frame_set(f)
        em.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"BALL_OK: {out_glb}", flush=True)
'''


def make_ball(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_cball_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "BALL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
        elapsed = round(time.time() - t0, 1)
        if ok:
            return {"ok": True, "glb": out_glb_abs, "elapsed_s": elapsed, "size_bytes": os.path.getsize(out_glb_abs)}
        tail = "\n".join((proc.stdout or "").splitlines()[-20:] + (proc.stderr or "").splitlines()[-20:])
        return {"ok": False, "error": f"Blender exit {proc.returncode}", "log_tail": tail, "elapsed_s": elapsed}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("output", help="output GLB path")
    args = ap.parse_args()
    r = make_ball(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
