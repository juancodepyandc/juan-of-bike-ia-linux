"""Procedural domino cascade (Blender headless).

Wood table + 20 white dominos standing in a row + pusher ball at one
end. Animation : the ball rolls toward the first domino, then each
domino falls in sequence (staggered timing). Each domino pivots
around its base front edge so the fall looks physical.

CLI:
  python proc_domino_chain.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "dominos.glb"

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

mat_table  = pbr_mat("table_wood",  (0.30, 0.18, 0.08), 0.00, 0.60)
mat_domino = pbr_mat("domino_white",(0.90, 0.89, 0.86), 0.05, 0.30)
mat_dot    = pbr_mat("dot_black",   (0.05, 0.05, 0.05), 0.10, 0.45)
mat_ball   = pbr_mat("ball_red",    (0.80, 0.10, 0.10), 0.10, 0.30)

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

def _sphere(name, R, location, mat, u=18, v=12):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- table ----------------------------------------------------
_box("table", 2.5, 0.50, 0.04, (0, 0, -0.04), mat_table)

# --- 20 dominos in a row ------------------------------------
N_DOMINOS    = 20
DOMINO_W     = 0.04          # thickness (X direction = travel direction)
DOMINO_D     = 0.10          # depth (Y direction)
DOMINO_H     = 0.20          # height
DOMINO_SPACE = 0.075         # X spacing between dominos (so each can tip
                              # forward and just barely hit the next one)
START_X      = -0.80

domino_pivots = []
for i in range(N_DOMINOS):
    x = START_X + i * DOMINO_SPACE
    # pivot is at the BASE FRONT EDGE of the domino (the edge that stays on the
    # table while the rest tips forward).
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(x + DOMINO_W/2, 0, 0))
    pv = bpy.context.active_object
    pv.name = f"domino_pivot_{i}"

    # the domino mesh : centred ABOVE the pivot, offset back by DOMINO_W/2 in X
    # and up by DOMINO_H/2 in Z, so when the pivot rotates +Y the domino
    # tilts forward toward +X.
    body = _box(f"domino_{i}", DOMINO_W, DOMINO_D, DOMINO_H,
                  (0, 0, 0), mat_domino)
    body.parent = pv
    body.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    body.location = (-DOMINO_W/2, 0, DOMINO_H/2)

    # 4 black dots on the visible face (the side facing the camera = +Y)
    dot_R = 0.008
    for dot_x in (-DOMINO_H * 0.25, +DOMINO_H * 0.25):
        for dot_z in (-DOMINO_H * 0.25, +DOMINO_H * 0.25):
            d = _box(f"dot_{i}_{dot_x}_{dot_z}", 0.006, 0.002, 0.006,
                       (0, DOMINO_D/2 + 0.002, DOMINO_H/2 + dot_z),
                       mat_dot)
            d.location = (-DOMINO_W/2 + dot_x * 0.4, DOMINO_D/2 + 0.002, DOMINO_H/2 + dot_z)
            d.parent = pv
            d.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    domino_pivots.append(pv)

# --- pusher ball at the start --------------------------------
BALL_R = 0.06
ball = _sphere("pusher_ball", BALL_R, (START_X - 0.30, 0, BALL_R), mat_ball)

# --- animation ----------------------------------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 1   # snap precision for the fall onset

# Ball : rolls from (-1.10, 0, BALL_R) to (START_X - BALL_R, 0, BALL_R) over
# the first 0.5 s of the loop, then stays put.
BALL_HIT_TIME = 0.5   # seconds
BALL_HIT_FR   = int(BALL_HIT_TIME * FPS)
BALL_START_X  = START_X - 0.30
BALL_END_X    = START_X - BALL_R
ball_x_keys = [(1, BALL_START_X), (BALL_HIT_FR, BALL_END_X), (NFR, BALL_END_X)]
for (frame, x) in ball_x_keys:
    bpy.context.scene.frame_set(frame)
    ball.location = (x, 0, BALL_R)
    ball.keyframe_insert("location", frame=frame)
# also rotate the ball as it rolls (R = BALL_R, distance = 0.30 - BALL_R)
rolled_distance = BALL_END_X - BALL_START_X
rolls = rolled_distance / (2 * math.pi * BALL_R)
ball_rot_keys = [(1, 0), (BALL_HIT_FR, -rolls * 2 * math.pi), (NFR, -rolls * 2 * math.pi)]
for (frame, ang) in ball_rot_keys:
    bpy.context.scene.frame_set(frame)
    ball.rotation_euler = (0, ang, 0)
    ball.keyframe_insert("rotation_euler", frame=frame)
if ball.animation_data and ball.animation_data.action:
    for fc in ball.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Dominos : each starts falling at t = BALL_HIT_TIME + i * FALL_DELAY,
# completes its fall over FALL_DURATION seconds, then stays flat.
FALL_DELAY    = 0.15   # seconds between domino i and i+1
FALL_DURATION = 0.30   # how long each domino takes to fall

for i, pv in enumerate(domino_pivots):
    t_start = BALL_HIT_TIME + i * FALL_DELAY
    t_end   = t_start + FALL_DURATION
    start_fr = max(1, int(t_start * FPS))
    end_fr   = min(NFR, int(t_end * FPS))
    # rest at frame 1 + at start_fr
    bpy.context.scene.frame_set(1)
    pv.rotation_euler = (0, 0, 0)
    pv.keyframe_insert("rotation_euler", frame=1)
    bpy.context.scene.frame_set(start_fr)
    pv.rotation_euler = (0, 0, 0)
    pv.keyframe_insert("rotation_euler", frame=start_fr)
    # fully fallen at end_fr (rotated ~85 deg around Y so it lies on its face)
    bpy.context.scene.frame_set(end_fr)
    pv.rotation_euler = (0, math.radians(85), 0)
    pv.keyframe_insert("rotation_euler", frame=end_fr)
    # stay fallen
    bpy.context.scene.frame_set(NFR)
    pv.rotation_euler = (0, math.radians(85), 0)
    pv.keyframe_insert("rotation_euler", frame=NFR)
    # BEZIER ease so the fall accelerates - matches a real gravity fall feel
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"DOMINOS_OK: {out_glb}", flush=True)
'''


def make_dominos(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_dom_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "DOMINOS_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_dominos(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
