"""Procedural ferris wheel (Blender headless).

Two A-frame supports + axle + circular rim with 8 spokes + 8 hanging
cabins that stay gravity-aligned (vertical) as the wheel turns. The
cabin's pivot point follows the rim angularly via direct keyframes
(so they don't inherit the wheel's rotation; the wheel and cabins are
two separate animated systems).

CLI:
  python proc_ferris_wheel.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "ferris.glb"

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

mat_steel    = pbr_mat("steel_struct", (0.55, 0.57, 0.60), 1.00, 0.30)
mat_dark     = pbr_mat("dark_steel",   (0.20, 0.20, 0.22), 1.00, 0.42)
mat_ground   = pbr_mat("ground_plaza", (0.45, 0.42, 0.38), 0.00, 0.85)
mat_red      = pbr_mat("cabin_red",    (0.78, 0.10, 0.10), 0.10, 0.40)
mat_blue     = pbr_mat("cabin_blue",   (0.10, 0.30, 0.78), 0.10, 0.40)
mat_yellow   = pbr_mat("cabin_yellow", (0.95, 0.78, 0.18), 0.10, 0.45)
mat_green    = pbr_mat("cabin_green",  (0.15, 0.62, 0.25), 0.10, 0.40)

# --- ground -------------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.05))
g = bpy.context.active_object
g.name = "ground"
g.scale = (4.5, 4.5, 0.06)
bpy.ops.object.transform_apply(scale=True)
g.data.materials.append(mat_ground)

# --- A-frame supports ---------------------------------------------------
# 2 supports at y = +/- 0.50, each is 2 angled legs converging to the axle.
WHEEL_R    = 1.10
AXLE_Z     = 1.40
AXLE_HALF_Y = 0.55     # half distance between the 2 frames

def _box_along(name, p0, p1, R, mat):
    """A thin box from p0 to p1 of half-thickness R."""
    p0v = mathutils.Vector(p0); p1v = mathutils.Vector(p1)
    direction = p1v - p0v
    length = direction.length
    if length < 1e-6:
        return None
    direction.normalize()
    mid = (p0v + p1v) / 2
    bpy.ops.mesh.primitive_cube_add(size=1, location=mid)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (length, R*2, R*2)
    bpy.ops.object.transform_apply(scale=True)
    # rotate so local X aligns with the direction
    # compute Euler from direction
    yaw = math.atan2(direction.y, direction.x)
    pitch = -math.asin(direction.z)
    obj.rotation_euler = (0, pitch, yaw)
    obj.data.materials.append(mat)
    return obj

# Two A-frames : on each side, 2 legs from base feet to axle
for side in (-1, 1):
    y_axle = side * AXLE_HALF_Y
    # 2 base feet at +/- 0.7 x-offset
    for fx in (-0.7, +0.7):
        _box_along(f"leg_{side}_{'L' if fx<0 else 'R'}",
                    (fx, y_axle, 0.0),
                    (0.0, y_axle, AXLE_Z),
                    0.030, mat_steel)
    # horizontal base bar between feet
    _box_along(f"base_bar_{side}",
                (-0.7, y_axle, 0.04),
                (+0.7, y_axle, 0.04),
                0.025, mat_dark)

# --- axle (long horizontal cylinder through both A-frame tops) ---------
mesh_axle = bpy.data.meshes.new("axle")
axle = bpy.data.objects.new("axle", mesh_axle)
bpy.context.collection.objects.link(axle)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=20,
                        radius1=0.05, radius2=0.05, depth=AXLE_HALF_Y * 2 + 0.20)
bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'X'), verts=bm.verts)
bm.to_mesh(mesh_axle); bm.free()
axle.location = (0, 0, AXLE_Z)
axle.data.materials.append(mat_dark)

# --- wheel rim + spokes (parented to a rotating empty) -----------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, AXLE_Z))
wheel_pivot = bpy.context.active_object
wheel_pivot.name = "wheel_pivot"

# rim : torus
mesh_rim = bpy.data.meshes.new("rim")
rim = bpy.data.objects.new("rim", mesh_rim)
bpy.context.collection.objects.link(rim)
bm = bmesh.new()
# torus oriented in XZ plane (axle along Y)
import importlib
bmesh.ops.create_uvsphere(bm, u_segments=4, v_segments=2, radius=0.001)  # placeholder to free
bm.clear()
# Build torus manually : major ring R=WHEEL_R, minor R=0.04, oriented around Y
N_MAJ, N_MIN = 48, 10
for i in range(N_MAJ):
    a = i * 2 * math.pi / N_MAJ
    cx = math.cos(a) * WHEEL_R
    cz = math.sin(a) * WHEEL_R
    for j in range(N_MIN):
        b = j * 2 * math.pi / N_MIN
        # minor circle perpendicular to the major direction in the XZ plane
        # the minor ring lies in the Y-radial plane
        ry = math.cos(b) * 0.04
        r_rad = math.sin(b) * 0.04
        bm.verts.new((cx + math.cos(a) * r_rad,
                       ry,
                       cz + math.sin(a) * r_rad))
bm.verts.ensure_lookup_table()
verts = bm.verts[:]
for i in range(N_MAJ):
    ni = (i + 1) % N_MAJ
    for j in range(N_MIN):
        nj = (j + 1) % N_MIN
        a = i * N_MIN + j
        b = i * N_MIN + nj
        c = ni * N_MIN + nj
        d = ni * N_MIN + j
        bm.faces.new((verts[a], verts[b], verts[c], verts[d]))
bm.normal_update()
bm.to_mesh(mesh_rim); bm.free()
rim.data.materials.append(mat_steel)
rim.parent = wheel_pivot
rim.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# central hub disc
mesh_hub = bpy.data.meshes.new("wheel_hub")
hub = bpy.data.objects.new("wheel_hub", mesh_hub)
bpy.context.collection.objects.link(hub)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=24,
                        radius1=0.12, radius2=0.12, depth=0.18)
bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'X'), verts=bm.verts)
bm.to_mesh(mesh_hub); bm.free()
hub.data.materials.append(mat_dark)
hub.parent = wheel_pivot
hub.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 8 spokes
N_SPOKES = 8
for k in range(N_SPOKES):
    a = k * 2 * math.pi / N_SPOKES
    ex = math.cos(a) * WHEEL_R
    ez = math.sin(a) * WHEEL_R
    s = _box_along(f"spoke_{k}", (0, 0, 0), (ex, 0, ez), 0.012, mat_steel)
    s.parent = wheel_pivot
    s.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 8 cabins (NOT parented to wheel : their position is keyframed
#     independently so they stay gravity-aligned) ----------------------
N_CABINS = 8
CABIN_COLORS = [mat_red, mat_blue, mat_yellow, mat_green,
                  mat_red, mat_blue, mat_yellow, mat_green]
cabin_pivots = []
for k in range(N_CABINS):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, AXLE_Z))
    cp = bpy.context.active_object
    cp.name = f"cabin_pivot_{k}"
    cabin_pivots.append(cp)

    # Cabin body : a small box with a slightly arched roof
    body = bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    body_obj = bpy.context.active_object
    body_obj.name = f"cabin_{k}"
    body_obj.scale = (0.24, 0.30, 0.20)
    bpy.ops.object.transform_apply(scale=True)
    body_obj.data.materials.append(CABIN_COLORS[k])
    body_obj.parent = cp
    body_obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    body_obj.location = (0, 0, -0.18)  # hang the body below the pivot

    # arched roof : a slightly larger thin box above
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    roof = bpy.context.active_object
    roof.name = f"cabin_roof_{k}"
    roof.scale = (0.27, 0.33, 0.025)
    bpy.ops.object.transform_apply(scale=True)
    roof.data.materials.append(mat_dark)
    roof.parent = cp
    roof.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    roof.location = (0, 0, -0.07)

    # small mounting bar from pivot to cabin roof
    bar = _box_along(f"cabin_bar_{k}", (0, 0, 0), (0, 0, -0.07), 0.010, mat_dark)
    bar.parent = cp
    bar.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    bar.location = (0, 0, 0)

# --- animation ----------------------------------------------------------
FPS = 30
DURATION = 6.0   # slower so the cabins are easy to see
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

# Wheel rotation : 1 full turn around Y axis over the loop
KEY_EVERY = 2
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    wheel_pivot.rotation_euler = (0, 2 * math.pi * t, 0)
    wheel_pivot.keyframe_insert("rotation_euler", frame=f)
if wheel_pivot.animation_data and wheel_pivot.animation_data.action:
    for fc in wheel_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Cabins : position keyframed along the rim, rotation locked to identity.
# At time t, the wheel has rotated by theta(t) = 2*pi*t. The cabin k sits
# at the wheel angle alpha_k(t) = k * 2*pi/N + theta(t).
# But we want the CABIN to follow this position WITHOUT itself rotating.
for k, cp in enumerate(cabin_pivots):
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        alpha = k * 2 * math.pi / N_CABINS + 2 * math.pi * t
        # position on the rim (in the XZ plane around the axle)
        cx = math.cos(alpha) * WHEEL_R
        cz = AXLE_Z + math.sin(alpha) * WHEEL_R
        bpy.context.scene.frame_set(f)
        cp.location = (cx, 0, cz)
        cp.rotation_euler = (0, 0, 0)  # gravity-aligned
        cp.keyframe_insert("location", frame=f)
        cp.keyframe_insert("rotation_euler", frame=f)
    if cp.animation_data and cp.animation_data.action:
        for fc in cp.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"FERRIS_OK: {out_glb}", flush=True)
'''


def make_ferris(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_fw_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "FERRIS_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_ferris(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
