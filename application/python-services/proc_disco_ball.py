"""Procedural disco ball (Blender headless).

Icosphere with subdivision-2 (320 mirror facets) + cord suspending it
from a ceiling fixture + ~12 random accent facets that pulse-emissive.
Animation : the ball rotates around its vertical axis.

CLI:
  python proc_disco_ball.py <output_glb>
"""
from __future__ import annotations
import argparse, json, os, random, shutil, subprocess, sys, tempfile, time
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
import bpy, bmesh, math, mathutils, random, sys

random.seed(29)

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "disco.glb"

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

mat_mirror   = pbr_mat("mirror",      (0.95, 0.95, 0.96), 1.00, 0.02)
mat_pink     = pbr_mat("accent_pink", (1.00, 0.30, 0.60), 1.00, 0.05,
                          emission=((1.00, 0.35, 0.70), 2.0))
mat_blue     = pbr_mat("accent_blue", (0.30, 0.55, 1.00), 1.00, 0.05,
                          emission=((0.40, 0.60, 1.00), 2.0))
mat_yellow   = pbr_mat("accent_yel",  (1.00, 0.95, 0.30), 1.00, 0.05,
                          emission=((1.00, 0.95, 0.45), 2.0))
mat_dark     = pbr_mat("dark_steel",  (0.15, 0.15, 0.17), 0.90, 0.40)
mat_cord     = pbr_mat("cord",        (0.30, 0.30, 0.30), 0.10, 0.55)
mat_ground   = pbr_mat("floor",       (0.08, 0.08, 0.10), 0.00, 0.85)

# --- floor (dark dance-floor) ---------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
fl = bpy.context.active_object
fl.name = "dance_floor"
fl.scale = (2.0, 2.0, 0.04)
bpy.ops.object.transform_apply(scale=True)
fl.data.materials.append(mat_ground)

# --- ceiling fixture + cord ------------------------------------
CEIL_Z = 1.85
BALL_R = 0.30
BALL_Z = 0.95
_box_args = lambda n, sx, sy, sz, loc, mat: (
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc),
    bpy.context.active_object,
)
def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

_box("ceiling_plate", 0.18, 0.18, 0.04, (0, 0, CEIL_Z), mat_dark)

# cord between ceiling and ball top
cord_len = CEIL_Z - (BALL_Z + BALL_R) - 0.02
_box("cord", 0.008, 0.008, cord_len,
       (0, 0, BALL_Z + BALL_R + cord_len/2 + 0.01), mat_cord)

# --- disco ball : ICOsphere with 2 subdivisions (320 facets) ---
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, BALL_Z))
ball_pivot = bpy.context.active_object
ball_pivot.name = "ball_pivot"

mesh_ball = bpy.data.meshes.new("disco_ball")
ball = bpy.data.objects.new("disco_ball", mesh_ball)
bpy.context.collection.objects.link(ball)
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=2, radius=BALL_R)
bm.to_mesh(mesh_ball); bm.free()
ball.data.materials.append(mat_mirror)
ball.data.materials.append(mat_pink)
ball.data.materials.append(mat_blue)
ball.data.materials.append(mat_yellow)

# assign ~12 random faces to one of the 3 accent colours (cycling)
n_polys = len(ball.data.polygons)
accent_indices = random.sample(range(n_polys), min(12, n_polys))
accent_palette = [1, 2, 3]  # pink, blue, yellow
for i, p in enumerate(ball.data.polygons):
    if i in accent_indices:
        p.material_index = accent_palette[i % 3]
    else:
        p.material_index = 0

ball.parent = ball_pivot
ball.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- mounting cap on top of the ball (small dark disc) -------
mesh_cap = bpy.data.meshes.new("ball_cap")
cap = bpy.data.objects.new("ball_cap", mesh_cap)
bpy.context.collection.objects.link(cap)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16,
                        radius1=0.035, radius2=0.025, depth=0.025)
bmesh.ops.translate(bm, vec=(0, 0, BALL_R), verts=bm.verts)
bm.to_mesh(mesh_cap); bm.free()
cap.data.materials.append(mat_dark)
cap.parent = ball_pivot
cap.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : ball spins around Z + accent emission flickers --
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    ball_pivot.rotation_euler = (0, 0, 2 * math.pi * t)
    ball_pivot.keyframe_insert("rotation_euler", frame=f)
if ball_pivot.animation_data and ball_pivot.animation_data.action:
    for fc in ball_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Accent emission flickers : 3 different phases for the 3 colours
for mat, phase in [(mat_pink, 0.0), (mat_blue, 0.33), (mat_yellow, 0.66)]:
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    em = bsdf.inputs["Emission Strength"]
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        em.default_value = 1.5 + 1.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 4 + phase * 2*math.pi))
        bpy.context.scene.frame_set(f)
        em.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"DISCO_OK: {out_glb}", flush=True)
'''


def make_disco(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_disco_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "DISCO_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_disco(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
