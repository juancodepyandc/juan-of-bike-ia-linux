"""Procedural hot air balloon (Blender headless).

Stretched-sphere balloon (red+white vertical stripes via 2 alternating
materials on a UV sphere split into 12 segments) + wicker basket below
+ 4 ropes + emissive flame at the basket centre. Animation : balloon
bobs vertically, flame scales (flicker), root sways gently.

CLI:
  python proc_hot_air_balloon.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "balloon.glb"

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

mat_red    = pbr_mat("balloon_red",   (0.78, 0.10, 0.10), 0.10, 0.40)
mat_white  = pbr_mat("balloon_white", (0.95, 0.94, 0.90), 0.10, 0.40)
mat_wicker = pbr_mat("wicker_brown",  (0.45, 0.30, 0.16), 0.00, 0.65)
mat_rope   = pbr_mat("rope_dark",     (0.20, 0.15, 0.10), 0.00, 0.75)
mat_flame  = pbr_mat("flame_orange",  (1.00, 0.50, 0.10), 0.00, 0.20,
                       emission=((1.00, 0.60, 0.15), 4.0))
mat_ground = pbr_mat("ground",        (0.20, 0.32, 0.14), 0.00, 0.85)

def _cyl(name, R1, R2, depth, axis, location, mat, segments=24):
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

# --- ground -----------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.05))
g = bpy.context.active_object
g.name = "ground"
g.scale = (4.0, 4.0, 0.05)
bpy.ops.object.transform_apply(scale=True)
g.data.materials.append(mat_ground)

# --- root empty (drives the overall sway + bob) -----------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 1.7))
root = bpy.context.active_object
root.name = "balloon_root"

# --- balloon : stretched UV sphere split into 12 vertical wedges
#     with alternating red/white materials so the wedges read as
#     vertical stripes -----------------------------------------
mesh_balloon = bpy.data.meshes.new("balloon")
balloon = bpy.data.objects.new("balloon", mesh_balloon)
bpy.context.collection.objects.link(balloon)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=12, radius=0.65)
# stretch vertically + flatten bottom a bit (balloon shape)
for v in bm.verts:
    v.co.z *= 1.25
    if v.co.z < -0.30:
        # taper the bottom toward a smaller radius (more "balloon" shape)
        f = (-v.co.z - 0.30) / 0.50
        v.co.x *= max(0.4, 1.0 - 0.55 * f)
        v.co.y *= max(0.4, 1.0 - 0.55 * f)
bm.to_mesh(mesh_balloon); bm.free()
balloon.location = (0, 0, 0)
# 2 materials on the balloon : assign alternating wedges using
# material_index per face
balloon.data.materials.append(mat_red)
balloon.data.materials.append(mat_white)
# Re-open the mesh to assign per-face material_index by azimuthal wedge.
for poly in balloon.data.polygons:
    cx = sum(balloon.data.vertices[i].co.x for i in poly.vertices) / len(poly.vertices)
    cy = sum(balloon.data.vertices[i].co.y for i in poly.vertices) / len(poly.vertices)
    angle = math.atan2(cy, cx)
    wedge = int((angle + math.pi) * 6 / math.pi) % 12   # 12 wedges
    poly.material_index = wedge % 2  # alternate red/white
balloon.parent = root
balloon.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# Crown ring at the very top
_top = _cyl("balloon_crown", 0.08, 0.08, 0.025, 'Z', (0, 0, 0.85), mat_red)
_top.parent = root
_top.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- basket : wicker cube hanging below -----------------------
BASKET_W = 0.30
BASKET_H = 0.22
BASKET_Z = -0.95
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, BASKET_Z))
basket = bpy.context.active_object
basket.name = "basket"
basket.scale = (BASKET_W, BASKET_W, BASKET_H)
bpy.ops.object.transform_apply(scale=True)
basket.data.materials.append(mat_wicker)
basket.parent = root
basket.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# top rim of basket (slightly larger)
_rim = _cyl("basket_rim", BASKET_W * 0.75, BASKET_W * 0.75, 0.025, 'Z',
              (0, 0, BASKET_Z + BASKET_H/2 + 0.01), mat_wicker)
_rim.parent = root
_rim.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 4 ropes from balloon bottom to basket rim ---------------
def _box_along(name, p0, p1, R, mat, parent):
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
    yaw = math.atan2(direction.y, direction.x)
    pitch = -math.asin(direction.z)
    obj.rotation_euler = (0, pitch, yaw)
    obj.data.materials.append(mat)
    obj.parent = parent
    obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    return obj

for k, a in enumerate([math.pi/4, 3*math.pi/4, 5*math.pi/4, 7*math.pi/4]):
    bx = math.cos(a) * 0.45
    by = math.sin(a) * 0.45
    bz = -0.40   # bottom of balloon, on the taper
    rx = math.cos(a) * BASKET_W * 0.5
    ry = math.sin(a) * BASKET_W * 0.5
    rz = BASKET_Z + BASKET_H/2
    _box_along(f"rope_{k}", (bx, by, bz), (rx, ry, rz), 0.006, mat_rope, root)

# --- flame at the basket top (cone with emission) ------------
mesh_flame = bpy.data.meshes.new("flame")
flame = bpy.data.objects.new("flame", mesh_flame)
bpy.context.collection.objects.link(flame)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16,
                        radius1=0.06, radius2=0.005, depth=0.16)
bmesh.ops.translate(bm, vec=(0, 0, 0.08), verts=bm.verts)
bm.to_mesh(mesh_flame); bm.free()
flame.data.materials.append(mat_flame)
flame.parent = root
flame.matrix_parent_inverse = mathutils.Matrix.Identity(4)
flame.location = (0, 0, BASKET_Z + BASKET_H/2 + 0.02)

# --- animation -----------------------------------------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# Root sways + bobs : Z bob +/- 5 cm, tilt 2 deg around X and Y
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    root.location = (0, 0, 1.7 + math.sin(2*math.pi*t) * 0.05)
    root.rotation_euler = (math.sin(2*math.pi*t)         * math.radians(2),
                            math.cos(2*math.pi*t * 0.7)   * math.radians(2),
                            0)
    root.keyframe_insert("location", frame=f)
    root.keyframe_insert("rotation_euler", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Flame flicker : scale 0.7 -> 1.3 at 4 Hz
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    s = 0.7 + 0.3 * (0.5 + 0.5 * math.sin(2*math.pi*t * 8))
    flame.scale = (s, s, s)
    flame.keyframe_insert("scale", frame=f)
if flame.animation_data and flame.animation_data.action:
    for fc in flame.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"BALLOON_OK: {out_glb}", flush=True)
'''


def make_balloon(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_balloon_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "BALLOON_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_balloon(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
