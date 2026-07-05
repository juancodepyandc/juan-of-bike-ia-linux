"""Procedural helicopter (Blender headless).

Tapered fuselage + cockpit bubble + main rotor (4 blades) + tail boom +
tail rotor (2 blades) + landing skids. Animation : main rotor spins
around Z, tail rotor spins around X (perpendicular to the tail boom),
fuselage bobs and tilts slightly.

CLI:
  python proc_helicopter.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "helicopter.glb"

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

mat_body    = pbr_mat("body_red",    (0.72, 0.10, 0.10), 0.20, 0.30)
mat_glass   = pbr_mat("cockpit_glass",(0.10, 0.18, 0.30), 0.00, 0.05)
mat_blade   = pbr_mat("blade",       (0.18, 0.18, 0.22), 0.20, 0.50)
mat_dark    = pbr_mat("dark_struct", (0.20, 0.20, 0.22), 0.80, 0.40)
mat_skid    = pbr_mat("skid_steel",  (0.55, 0.57, 0.60), 1.00, 0.30)

def _box_along(name, p0, p1, R, mat):
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
    return obj

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

# --- root empty (drives whole-helicopter bob) ---------------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0.7))
root = bpy.context.active_object
root.name = "heli_root"

# --- fuselage : tapered ellipsoid built from a UV sphere ---------------
mesh_fuse = bpy.data.meshes.new("fuselage")
fuse = bpy.data.objects.new("fuselage", mesh_fuse)
bpy.context.collection.objects.link(fuse)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.30)
# Stretch X (forward) -> elongated egg
bmesh.ops.scale(bm, vec=(1.6, 1.0, 0.85), verts=bm.verts)
bm.to_mesh(mesh_fuse); bm.free()
fuse.location = (0.05, 0, 0)
fuse.data.materials.append(mat_body)
fuse.parent = root
fuse.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- cockpit bubble : a smaller UV sphere at the front -----------------
mesh_cock = bpy.data.meshes.new("cockpit")
cock = bpy.data.objects.new("cockpit", mesh_cock)
bpy.context.collection.objects.link(cock)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=0.22)
bmesh.ops.scale(bm, vec=(1.0, 0.95, 0.95), verts=bm.verts)
# slice off the rear so it sits flush against the fuselage
to_del = [v for v in bm.verts if v.co.x < -0.05]
bmesh.ops.delete(bm, geom=to_del, context='VERTS')
bm.to_mesh(mesh_cock); bm.free()
cock.location = (0.45, 0, 0.04)
cock.data.materials.append(mat_glass)
cock.parent = root
cock.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- tail boom : long thin cylinder extending behind ------------------
tail_boom = _cyl("tail_boom", 0.05, 0.03, 0.90, 'X', (-0.85, 0, 0.04), mat_body)
tail_boom.parent = root
tail_boom.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- tail fin (vertical stabiliser) -----------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(-1.25, 0, 0.18))
fin = bpy.context.active_object
fin.name = "tail_fin"
fin.scale = (0.10, 0.020, 0.22)
bpy.ops.object.transform_apply(scale=True)
fin.data.materials.append(mat_body)
fin.parent = root
fin.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- tail rotor (parented to its own pivot, rotates around X) ---------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(-1.30, -0.08, 0.06))
tail_rotor_pivot = bpy.context.active_object
tail_rotor_pivot.name = "tail_rotor_pivot"
tail_rotor_pivot.parent = root
tail_rotor_pivot.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 2 thin blade boxes joined into a single bmesh
mesh_tr = bpy.data.meshes.new("tail_rotor")
tr = bpy.data.objects.new("tail_rotor", mesh_tr)
bpy.context.collection.objects.link(tr)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=(0.005, 0.005, 0.30), verts=bm.verts)
v_before = set(bm.verts)
bmesh.ops.create_cube(bm, size=1.0)
new_verts = [v for v in bm.verts if v not in v_before]
bmesh.ops.scale(bm, vec=(0.005, 0.30, 0.005), verts=new_verts)
# small hub
v_before2 = set(bm.verts)
bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.022)
bm.to_mesh(mesh_tr); bm.free()
tr.data.materials.append(mat_blade)
tr.parent = tail_rotor_pivot
tr.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- main rotor mast + pivot + 4 blades -----------------------------
mast = _cyl("rotor_mast", 0.035, 0.025, 0.18, 'Z', (0, 0, 0.35), mat_dark)
mast.parent = root
mast.matrix_parent_inverse = mathutils.Matrix.Identity(4)

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0.45))
main_rotor_pivot = bpy.context.active_object
main_rotor_pivot.name = "main_rotor_pivot"
main_rotor_pivot.parent = root
main_rotor_pivot.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# Build the 4 blades as a single bmesh
mesh_mr = bpy.data.meshes.new("main_rotor")
mr = bpy.data.objects.new("main_rotor", mesh_mr)
bpy.context.collection.objects.link(mr)
bm = bmesh.new()
BLADE_L = 0.80
for i in range(4):
    angle = i * math.pi / 2
    v_before = set(bm.verts)
    bmesh.ops.create_cube(bm, size=1.0)
    new_verts = [v for v in bm.verts if v not in v_before]
    bmesh.ops.scale(bm, vec=(BLADE_L, 0.06, 0.010), verts=new_verts)
    bmesh.ops.translate(bm, vec=(BLADE_L/2, 0, 0), verts=new_verts)
    rot = mathutils.Matrix.Rotation(angle, 4, 'Z')
    bmesh.ops.transform(bm, matrix=rot, verts=new_verts)
# central hub
v_before = set(bm.verts)
bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=0.05)
bm.to_mesh(mesh_mr); bm.free()
mr.data.materials.append(mat_blade)
mr.parent = main_rotor_pivot
mr.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- landing skids ---------------------------------------------------
for sy in (-1, 1):
    # 2 vertical struts per skid
    for sx in (-1, 1):
        _box_along(f"skid_strut_{sy}_{sx}",
                    (sx * 0.20, sy * 0.25, -0.20),
                    (sx * 0.20, sy * 0.25, -0.35),
                    0.018, mat_skid).parent = root
    # horizontal rail
    rail = _cyl(f"skid_rail_{sy}", 0.022, 0.022, 0.70, 'X',
                  (0, sy * 0.25, -0.36), mat_skid)
    rail.parent = root
    rail.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ------------------------------------------------------
FPS = 30
DURATION = 3.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Main rotor : 8 turns per loop (fast)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    main_rotor_pivot.rotation_euler = (0, 0, 8 * 2 * math.pi * t)
    main_rotor_pivot.keyframe_insert("rotation_euler", frame=f)
if main_rotor_pivot.animation_data and main_rotor_pivot.animation_data.action:
    for fc in main_rotor_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Tail rotor : 16 turns per loop (much faster, around X axis -> blades sweep YZ)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    tail_rotor_pivot.rotation_euler = (16 * 2 * math.pi * t, 0, 0)
    tail_rotor_pivot.keyframe_insert("rotation_euler", frame=f)
if tail_rotor_pivot.animation_data and tail_rotor_pivot.animation_data.action:
    for fc in tail_rotor_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Body : gentle bob + slight tilt
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    root.location = (0, 0, 0.70 + math.sin(2*math.pi*t) * 0.03)
    root.rotation_euler = (math.sin(2*math.pi*t * 0.5) * math.radians(2),
                            math.cos(2*math.pi*t * 0.5) * math.radians(3),
                            0)
    root.keyframe_insert("location", frame=f)
    root.keyframe_insert("rotation_euler", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"HELI_OK: {out_glb}", flush=True)
'''


def make_helicopter(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_heli_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "HELI_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_helicopter(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
