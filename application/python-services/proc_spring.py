"""Procedural helical spring with animated compression (Blender headless).

Builds a polyline helix swept with a bevel-circle (gives a tube around the
helix), converts to mesh, adds a shape key "Compressed" (each vertex's Z
multiplied by 0.45), and animates the shape-key weight as a cosine wave
0 -> 1 -> 0 over the loop. A top plate rides on the spring so the
compression is visually anchored.

glTF morph targets export Blender shape keys correctly, so the animation
plays in three.js / any glTF viewer.

CLI:
  python proc_spring.py <output_glb>
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
import bpy, math, sys

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "spring.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30  # match the FPS used in the animation math

def pbr_mat(name, color, metal, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
    return m

mat_steel = pbr_mat("steel_spring", (0.62, 0.64, 0.66), 1.0, 0.18)
mat_dark  = pbr_mat("steel_dark",   (0.22, 0.22, 0.24), 1.0, 0.42)

# --- helix curve ------------------------------------------------------------
N_COILS = 8
H        = 0.80
R_HELIX  = 0.18
WIRE_R   = 0.025
N_PTS    = N_COILS * 24

crv = bpy.data.curves.new("spring_curve", 'CURVE')
crv.dimensions = '3D'
crv.bevel_depth = WIRE_R
crv.bevel_resolution = 6
crv.use_fill_caps = True

spline = crv.splines.new('POLY')
spline.points.add(N_PTS - 1)
for i in range(N_PTS):
    t = i / (N_PTS - 1)
    angle = 2 * math.pi * N_COILS * t
    spline.points[i].co = (R_HELIX * math.cos(angle),
                            R_HELIX * math.sin(angle),
                            H * t, 1.0)

obj = bpy.data.objects.new("spring", crv)
bpy.context.collection.objects.link(obj)
obj.data.materials.append(mat_steel)

# Convert curve to mesh -> shape keys can be added
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.convert(target='MESH')

# Shape keys : Basis (rest) + Compressed (Z * 0.45)
basis      = obj.shape_key_add(name="Basis",      from_mix=False)
compressed = obj.shape_key_add(name="Compressed", from_mix=False)
for i, v in enumerate(compressed.data):
    z0 = basis.data[i].co.z
    compressed.data[i].co.x = basis.data[i].co.x
    compressed.data[i].co.y = basis.data[i].co.y
    compressed.data[i].co.z = z0 * 0.45

# --- floor + moving top plate ---------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
floor = bpy.context.active_object
floor.name = "floor_plate"
floor.scale = (0.55, 0.55, 0.04)
bpy.ops.object.transform_apply(scale=True)
floor.data.materials.append(mat_dark)

# (top plate omitted in v2 : its translation animation didn't track
#  the shape-key compression in three.js, leaving a misleading gap)

# --- animation : shape-key weight + top-plate Z --------------------------
FPS = 30
DURATION = 3.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

key_block = obj.data.shape_keys.key_blocks["Compressed"]

KEY_EVERY = 2
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    weight = 0.5 - 0.5 * math.cos(2 * math.pi * t)  # 0 -> 1 -> 0
    bpy.context.scene.frame_set(f)

    key_block.value = weight
    key_block.keyframe_insert("value", frame=f)

# LINEAR on all keyframes
def _lin(ad):
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

_lin(obj.data.shape_keys.animation_data if obj.data.shape_keys else None)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SPRING_OK: {out_glb}", flush=True)
'''


def make_spring(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_spring_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SPRING_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_spring(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
