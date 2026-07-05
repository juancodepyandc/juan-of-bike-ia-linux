"""Procedural Weber-style charcoal BBQ grill (Blender headless).

Domed black kettle on 3 angled legs + dome lid hovering above + interior
grill grate visible through the gap + thermometer dial on the lid + 4
hot dogs / sausages on the grate + emissive flames + smoke trail. Animation
: dome lid hovers up + down + flames flicker + smoke spheres rise.

CLI:
  python proc_bbq_grill.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "bbq.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough, alpha=None, emission=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if alpha is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
            m.blend_method = 'BLEND'
        if emission is not None and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission[0], 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission[1]
    return m

mat_floor    = pbr_mat("floor",     (0.42, 0.40, 0.36), 0.00, 0.85)
mat_black    = pbr_mat("black",     (0.06, 0.06, 0.07), 0.30, 0.40)
mat_black_l  = pbr_mat("black_l",   (0.12, 0.12, 0.13), 0.30, 0.40)
mat_chrome   = pbr_mat("chrome",    (0.78, 0.80, 0.83), 1.00, 0.20)
mat_red      = pbr_mat("red",       (0.85, 0.18, 0.12), 0.10, 0.40)
mat_white    = pbr_mat("white",     (0.92, 0.92, 0.88), 0.00, 0.45)
mat_grate    = pbr_mat("grate",     (0.55, 0.55, 0.58), 1.00, 0.30)
mat_sausage  = pbr_mat("sausage",   (0.55, 0.18, 0.08), 0.00, 0.55)
mat_steak    = pbr_mat("steak",     (0.42, 0.18, 0.10), 0.00, 0.50)
mat_coal     = pbr_mat("coal",      (0.18, 0.10, 0.08), 0.05, 0.55,
                          emission=((1.00, 0.30, 0.10), 2.0))
mat_smoke    = pbr_mat("smoke",     (0.85, 0.85, 0.85), 0.00, 0.55, alpha=0.30)

def make_flame_mat(name, base=6.0):
    return pbr_mat(name, (1.00, 0.50, 0.15), 0.00, 0.10,
                      alpha=0.80,
                      emission=((1.00, 0.55, 0.20), base))

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

def _sphere(name, R, location, mat, u=18, v=14, scale=(1,1,1)):
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

# Conventions : BBQ on patio, lid faces +Z. Up = +Z.

# --- floor ---
_box("floor", 2.4, 2.4, 0.04, (0, 0, -0.04), mat_floor)

# Kettle dims
KETTLE_R = 0.36
KETTLE_H = 0.30
KETTLE_Z = 0.55  # center of the kettle bowl

# --- 3 angled legs forming a tripod ---
LEG_H = 0.55
for k in range(3):
    a = k * 2*math.pi/3
    foot_x = 0.50 * math.cos(a)
    foot_y = 0.50 * math.sin(a)
    p0 = mathutils.Vector((foot_x, foot_y, 0.04))
    p1 = mathutils.Vector((KETTLE_R * 0.7 * math.cos(a),
                            KETTLE_R * 0.7 * math.sin(a),
                            KETTLE_Z - 0.05))
    d = p1 - p0
    midp = (p0 + p1) * 0.5
    leg = _cyl(f"leg_{k}", 0.015, 0.015, d.length, 'Z', (0,0,0), mat_black_l, segments=10)
    leg.location = midp
    leg.rotation_mode = 'QUATERNION'
    leg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d.normalized())
    # small foot pad
    _cyl(f"leg_pad_{k}", 0.025, 0.025, 0.012, 'Z',
           (foot_x, foot_y, 0.046), mat_black)

# --- kettle (lower bowl) : half-sphere ---
_sphere("kettle_bowl", KETTLE_R,
          (0, 0, KETTLE_Z), mat_black,
          u=24, v=14, scale=(1.0, 1.0, 0.70))
# bottom plate of bowl
_cyl("kettle_bottom", KETTLE_R * 0.85, KETTLE_R * 0.85, 0.012, 'Z',
       (0, 0, KETTLE_Z - 0.12), mat_black, segments=20)

# --- dome lid : a top half-sphere that hovers (animated) ---
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, KETTLE_Z + 0.05))
lid_pivot = bpy.context.active_object
lid_pivot.name = "lid_pivot"
lid = _sphere("lid_dome", KETTLE_R * 1.02,
                (0, 0, 0.18), mat_black,
                u=24, v=14, scale=(1.0, 1.0, 0.75))
lid.parent = lid_pivot
lid.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# lid handle (small chrome bar on top)
handle = _box("lid_handle", 0.15, 0.018, 0.012,
                (0, 0, KETTLE_R * 1.02 * 0.75 + 0.20), mat_chrome)
handle.parent = lid_pivot
handle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# 2 handle stands
for sx in (-1, +1):
    _box(f"lid_handle_stand_{sx}", 0.012, 0.012, 0.025,
           (sx * 0.06, 0, KETTLE_R * 1.02 * 0.75 + 0.17), mat_chrome).parent = lid_pivot

# thermometer on the lid (small chrome disc with red dial)
thermo = _cyl("thermometer", 0.030, 0.030, 0.012, 'Y',
                (0, KETTLE_R * 0.85, KETTLE_R * 1.02 * 0.70),
                mat_chrome, segments=14)
thermo.parent = lid_pivot
thermo.matrix_parent_inverse = mathutils.Matrix.Identity(4)
thermo_face = _cyl("thermo_face", 0.025, 0.025, 0.003, 'Y',
                     (0, KETTLE_R * 0.85 + 0.008, KETTLE_R * 1.02 * 0.70),
                     mat_white, segments=14)
thermo_face.parent = lid_pivot
thermo_face.matrix_parent_inverse = mathutils.Matrix.Identity(4)
thermo_needle = _box("thermo_needle", 0.002, 0.001, 0.022,
                       (0, KETTLE_R * 0.85 + 0.011, KETTLE_R * 1.02 * 0.70 + 0.008),
                       mat_red,
                       rot=(math.radians(20), 0, 0))
thermo_needle.parent = lid_pivot
thermo_needle.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- grill grate inside the kettle (visible when lid is up) ---
GRATE_Z = KETTLE_Z - 0.02
# 8 parallel rods + 8 cross rods
N_RODS = 8
for k in range(N_RODS):
    x = -KETTLE_R * 0.78 + k * (KETTLE_R * 1.56) / (N_RODS - 1)
    _cyl(f"grate_X_{k}", 0.004, 0.004, KETTLE_R * 1.40, 'Y',
           (x, 0, GRATE_Z), mat_grate, segments=8)
    y = -KETTLE_R * 0.78 + k * (KETTLE_R * 1.56) / (N_RODS - 1)
    _cyl(f"grate_Y_{k}", 0.004, 0.004, KETTLE_R * 1.40, 'X',
           (0, y, GRATE_Z), mat_grate, segments=8)

# --- coal bed at the bottom (emissive) ---
_cyl("coal_bed", KETTLE_R * 0.75, KETTLE_R * 0.75, 0.020, 'Z',
       (0, 0, KETTLE_Z - 0.10), mat_coal, segments=24)

# --- 4 sausages + 1 steak on the grate ---
SAUSAGE_LEN = 0.18
for k in range(4):
    sx_off = (k - 1.5) * 0.06
    _cyl(f"sausage_{k}", 0.024, 0.024, SAUSAGE_LEN, 'Y',
           (sx_off, -0.06, GRATE_Z + 0.025), mat_sausage, segments=14)
# steak (a rounded slab)
_sphere("steak", 0.10, (0.04, 0.12, GRATE_Z + 0.020),
          mat_steak, scale=(1.5, 1.2, 0.30))

# --- 3 flame cones ---
flame_mats = []
flame_objs = []
FLAME_BASE_Z = KETTLE_Z - 0.08
for i in range(3):
    fm = make_flame_mat(f"bbq_flame_{i}_mat", base=5.0)
    flame_mats.append(fm)
    fx = (-0.10 + i * 0.10)
    fy = 0
    fH = 0.18 + 0.04 * (i % 2)
    fl = _cyl(f"flame_{i}", 0.04, 0.005, fH, 'Z',
                (fx, fy, FLAME_BASE_Z + fH/2), fm, segments=12)
    flame_objs.append((fl, fH, i * 0.5))

# --- smoke spheres rising from above the dome ---
smokes = []
for i in range(5):
    s = _sphere(f"smoke_{i}", 0.08,
                  (0, 0, KETTLE_Z + 0.40 + i * 0.10),
                  mat_smoke,
                  scale=(1.2, 1.0, 1.0))
    smokes.append(s)

# --- animation ---
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Lid pivot hovers (Z bob) slowly
HOME_LID_LOC = lid_pivot.location.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    z_off = 0.06 * (0.5 + 0.5 * math.sin(2*math.pi*t * 0.5))
    lid_pivot.location = (HOME_LID_LOC.x, HOME_LID_LOC.y, HOME_LID_LOC.z + z_off)
    lid_pivot.keyframe_insert("location", frame=f)
if lid_pivot.animation_data and lid_pivot.animation_data.action:
    for fc in lid_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# Flames flicker
for i, (fl, baseH, ph) in enumerate(flame_objs):
    fm = flame_mats[i]
    bsdf = fm.node_tree.nodes.get("Principled BSDF")
    em = bsdf.inputs["Emission Strength"]
    freq = 3.5 + (i % 3) * 1.2
    home = fl.location.copy()
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        ang = 2*math.pi*t * freq + ph
        sz = 0.7 + 0.4 * (0.5 + 0.5 * math.sin(ang))
        sxy = 0.85 + 0.15 * (0.5 + 0.5 * math.sin(ang + 1.0))
        fl.scale = (sxy, sxy, sz)
        fl.location.z = home.z + (sz - 1.0) * baseH / 2.0
        fl.keyframe_insert("scale", frame=f)
        fl.keyframe_insert("location", frame=f)
        em.default_value = max(2.0, 4.5 + 2.5 * (0.5 + 0.5 * math.sin(ang * 1.3)))
        em.keyframe_insert(data_path="default_value", frame=f)

# Coal bed pulses
bsdf_c = mat_coal.node_tree.nodes.get("Principled BSDF")
em_c = bsdf_c.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_c.default_value = 1.5 + 0.8 * (0.5 + 0.5 * math.sin(2*math.pi*t * 0.8))
    bpy.context.scene.frame_set(f)
    em_c.keyframe_insert(data_path="default_value", frame=f)

# Smoke spheres rise + grow + fade (scale)
for i, sp in enumerate(smokes):
    phase = i / 5.0
    home_z = KETTLE_Z + 0.40 + i * 0.10
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        local = (t * 1.5 + phase) % 1.0
        z = home_z + local * 0.80
        scale = 1.0 + local * 0.8  # grow as it rises
        sp.location = (0.02 * math.sin(local * 8 + phase * 6), 0, z)
        sp.scale = (1.2 * scale, scale, scale)
        bpy.context.scene.frame_set(f)
        sp.keyframe_insert("location", frame=f)
        sp.keyframe_insert("scale", frame=f)
    if sp.animation_data and sp.animation_data.action:
        for fc in sp.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"BBQ_OK: {out_glb}", flush=True)
'''


def make_bbq(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_bbq_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "BBQ_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_bbq(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
