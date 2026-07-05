"""Procedural windmill (Blender headless).

Octagonal stone base + cylindrical white tower + red conical cap +
4 rotating lattice sails around a central hub. The sails spin around
the cap-front axis once every 3 s.

CLI:
  python proc_windmill.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "windmill.glb"

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

mat_stone   = pbr_mat("stone_base",  (0.42, 0.40, 0.36), 0.00, 0.80)
mat_white   = pbr_mat("white_tower", (0.94, 0.93, 0.88), 0.00, 0.55)
mat_red_cap = pbr_mat("red_cap",     (0.60, 0.10, 0.10), 0.00, 0.45)
mat_wood    = pbr_mat("wood_sail",   (0.40, 0.27, 0.13), 0.00, 0.65)
mat_canvas  = pbr_mat("canvas",      (0.88, 0.84, 0.74), 0.00, 0.70)
mat_brass   = pbr_mat("brass_hub",   (0.86, 0.62, 0.20), 1.00, 0.28)
mat_grass   = pbr_mat("grass",       (0.18, 0.30, 0.12), 0.00, 0.85)

def _cyl(name, R1, R2, depth, location, mat, segments=48):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                            radius1=R1, radius2=R2, depth=depth)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

# --- ground ---------------------------------------------------------------
_box("grass_ground", 4.0, 4.0, 0.04, (0, 0, -0.04), mat_grass)

# --- octagonal stone base (cylinder with 8 segments = octagon) -----------
_cyl("stone_base", 0.55, 0.50, 0.30, (0, 0, 0.13), mat_stone, segments=8)

# --- tower (tapered white cylinder) --------------------------------------
TOWER_BASE_R = 0.40
TOWER_TOP_R  = 0.32
TOWER_H      = 1.50
TOWER_Z0     = 0.28
TOWER_TOP_Z  = TOWER_Z0 + TOWER_H

_cyl("tower", TOWER_BASE_R, TOWER_TOP_R, TOWER_H,
       (0, 0, TOWER_Z0 + TOWER_H/2), mat_white)

# --- door frame (small box on the tower front, low) ----------------------
_box("door", 0.04, 0.12, 0.30, (TOWER_BASE_R - 0.01, 0, 0.28 + 0.15), mat_wood)

# --- 4 small windows around the tower at mid-height ----------------------
for k, a in enumerate([0, math.pi/2, math.pi, 3*math.pi/2]):
    if k == 0:
        continue  # skip front (door is there)
    R_at_height = TOWER_BASE_R + (TOWER_TOP_R - TOWER_BASE_R) * 0.4
    wx = math.cos(a) * (R_at_height - 0.005)
    wy = math.sin(a) * (R_at_height - 0.005)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(wx, wy, 0.28 + 0.60))
    w = bpy.context.active_object
    w.name = f"window_{k}"
    w.scale = (0.04, 0.04, 0.10)
    bpy.ops.object.transform_apply(scale=True)
    w.rotation_euler = (0, 0, a)
    w.data.materials.append(mat_wood)

# --- red conical cap on top -----------------------------------------------
CAP_R = TOWER_TOP_R * 1.10
CAP_H = 0.30
_cyl("red_cap", CAP_R, 0.05, CAP_H, (0, 0, TOWER_TOP_Z + CAP_H/2), mat_red_cap, segments=24)

# --- sails hub : pivot empty at the front-top of the cap ----------------
# The sails rotate around the +X axis (cap-front).
HUB_X = TOWER_TOP_R * 1.05
HUB_Z = TOWER_TOP_Z + 0.08
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(HUB_X, 0, HUB_Z))
sails_pivot = bpy.context.active_object
sails_pivot.name = "sails_pivot"

# brass hub disc
hub = _cyl("hub", 0.08, 0.08, 0.05, (HUB_X, 0, HUB_Z), mat_brass)
# orient along X
hub.rotation_euler = (0, math.pi/2, 0)

# --- 4 sails (each is a long rectangular frame with lattice slats) ------
# Each sail extends from the hub outward along its local +Z (which we rotate
# around the hub's X axis at 90 deg intervals).
SAIL_L = 1.05      # length out from hub
SAIL_W = 0.20      # width of the lattice
SAIL_T = 0.025     # depth thickness

def _build_sail_bmesh(bm, L, W, T):
    """Sail with main spar along +Z (extending up from hub) + 5 cross-slats.
    Rotated per-sail around the X axis (world +X = axle) to fan into 4.
    """
    bmesh.ops.create_cube(bm, size=1.0)
    spar = list(bm.verts)[-8:]
    bmesh.ops.scale(bm, vec=(T * 1.5, T * 1.5, L), verts=spar)
    bmesh.ops.translate(bm, vec=(0, 0, L/2), verts=spar)
    for k in range(5):
        z = (k + 1) / 6 * L
        v_before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        new_verts = [v for v in bm.verts if v not in v_before]
        bmesh.ops.scale(bm, vec=(W, T, T*2.0), verts=new_verts)
        bmesh.ops.translate(bm, vec=(0, 0, z), verts=new_verts)

# Build the 4 sails. Each sail's spar starts along +Z ; we rotate each
# bmesh by i * pi/2 around the X axis so the 4 sails fan out in the YZ
# plane (perpendicular to world +X which will be the axle direction).
for i in range(4):
    angle = i * math.pi / 2
    mesh_s = bpy.data.meshes.new(f"sail_{i}")
    sail = bpy.data.objects.new(f"sail_{i}", mesh_s)
    bpy.context.collection.objects.link(sail)
    bm = bmesh.new()
    _build_sail_bmesh(bm, SAIL_L, SAIL_W, SAIL_T)
    rot = mathutils.Matrix.Rotation(angle, 4, 'X')
    bmesh.ops.transform(bm, matrix=rot, verts=bm.verts)
    bm.to_mesh(mesh_s); bm.free()
    sail.data.materials.append(mat_wood)
    sail.parent = sails_pivot
    sail.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# No initial pivot rotation : sails already form the X pattern in YZ plane.
# Animation rotates the pivot around its local X axis (= world +X, the axle).
sails_pivot.rotation_euler = (0, 0, 0)

# --- animation : sails spin around their hub axis ----------------------
FPS = 30
DURATION = 3.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

# sails_pivot rotates around its local X axis (the hub axle = world +X).
# One full turn per loop.
KEY_EVERY = 2
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    sails_pivot.rotation_euler = (2 * math.pi * t, 0, 0)
    bpy.context.scene.frame_set(f)
    sails_pivot.keyframe_insert("rotation_euler", frame=f)
if sails_pivot.animation_data and sails_pivot.animation_data.action:
    for fc in sails_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"WINDMILL_OK: {out_glb}", flush=True)
'''


def make_windmill(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_wm_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "WINDMILL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_windmill(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
