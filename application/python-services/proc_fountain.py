"""Procedural garden fountain (Blender headless).

Circular stone basin + tiered central column + central decorative ball
on top + 5 vertical water jets that bob their heights. Animation : each
jet scales Z up + down on its own period, so they look like dancing
water.

CLI:
  python proc_fountain.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "fountain.glb"

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

mat_stone   = pbr_mat("stone",     (0.55, 0.52, 0.48), 0.00, 0.85)
mat_stone_d = pbr_mat("stone_dk",  (0.40, 0.38, 0.35), 0.00, 0.90)
mat_water   = pbr_mat("water",     (0.30, 0.55, 0.85), 0.05, 0.12, alpha=0.45)
mat_jet     = pbr_mat("jet_water", (0.55, 0.78, 0.95), 0.05, 0.10, alpha=0.55)
mat_brass   = pbr_mat("brass",     (0.86, 0.62, 0.20), 1.00, 0.28)
mat_grass   = pbr_mat("grass",     (0.18, 0.30, 0.12), 0.00, 0.85)

def _cyl(name, R1, R2, depth, axis, location, mat, segments=32):
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

# --- grass ------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
g = bpy.context.active_object
g.name = "grass"
g.scale = (3.5, 3.5, 0.04); bpy.ops.object.transform_apply(scale=True)
g.data.materials.append(mat_grass)

# --- basin : large stone disc with low rim --------
BASIN_R = 0.95
BASIN_H = 0.08
RIM_H   = 0.10
RIM_T   = 0.10
# bottom of basin (slightly recessed)
_cyl("basin_floor", BASIN_R, BASIN_R, BASIN_H, 'Z', (0, 0, BASIN_H/2), mat_stone_d)
# basin rim : thick ring around the edge
# implement as a ring of small box segments (or use a torus)
# Use a torus-like ring via 2 cylinders : outer + inner cut
_cyl("rim_outer", BASIN_R + RIM_T, BASIN_R + RIM_T, RIM_H, 'Z',
       (0, 0, BASIN_H + RIM_H/2), mat_stone)
_cyl("rim_inner_cut", BASIN_R, BASIN_R, RIM_H + 0.01, 'Z',
       (0, 0, BASIN_H + RIM_H/2), mat_stone_d)
# water surface (translucent disc filling the basin)
_cyl("water_surface", BASIN_R - 0.02, BASIN_R - 0.02, 0.015, 'Z',
       (0, 0, BASIN_H + 0.02), mat_water)

# --- central column : 3 tiered stone discs ---------
COL_H = 0.55
COL_Z0 = BASIN_H
_cyl("col_t1", 0.18, 0.16, 0.18, 'Z', (0, 0, COL_Z0 + 0.09), mat_stone)
_cyl("col_t2", 0.14, 0.12, 0.16, 'Z', (0, 0, COL_Z0 + 0.18 + 0.08), mat_stone)
_cyl("col_t3", 0.10, 0.08, 0.14, 'Z', (0, 0, COL_Z0 + 0.34 + 0.07), mat_stone)

# decorative brass ball on top of the column
_sphere("decor_ball", 0.06, (0, 0, COL_Z0 + 0.41 + 0.07 + 0.05), mat_brass)

# --- 5 vertical water jets around the column -----
# 4 outer jets at 90 deg apart, 1 central tall jet through the ball
JET_DATA = [
    # (cx, cy, base_R, top_R, base_z, max_height, period_s)
    (0.45, 0,    0.04, 0.01, BASIN_H + 0.03, 0.50, 1.6),
    (-0.45, 0,   0.04, 0.01, BASIN_H + 0.03, 0.55, 2.0),
    (0, 0.45,    0.04, 0.01, BASIN_H + 0.03, 0.48, 1.8),
    (0, -0.45,   0.04, 0.01, BASIN_H + 0.03, 0.52, 1.9),
    (0, 0,       0.05, 0.005, COL_Z0 + 0.55, 0.70, 2.4),
]
jets = []
for i, (cx, cy, R_b, R_t, base_z, max_h, period) in enumerate(JET_DATA):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, base_z))
    pv = bpy.context.active_object
    pv.name = f"jet_pivot_{i}"
    jet = _cyl(f"jet_{i}", R_b, R_t, max_h, 'Z', (0, 0, max_h/2), mat_jet)
    jet.parent = pv
    jet.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    jets.append((pv, period))

# --- animation : each jet scales Z up/down ---------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
for (pv, period) in jets:
    # scale Z bobs between 0.25 and 1.0 over the period
    cycles = DURATION / period
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        s = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(2*math.pi*t * cycles))
        pv.scale = (1, 1, s)
        pv.keyframe_insert("scale", frame=f)
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"FOUNTAIN_OK: {out_glb}", flush=True)
'''


def make_fountain(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_fount_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "FOUNTAIN_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_fountain(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
