"""Procedural Apollo Lunar Module (Blender headless).

Iconic LM : octagonal descent stage (gold-foil base) + 4 landing legs
with circular footpads + ascent stage with angular crew cabin + 2
triangular windows + RCS thruster quads + antenna dish + small US flag
planted in lunar soil + cratered ground. Animation : 4 RCS thrusters
periodically pulse with bright flame, the flag sways slightly.

CLI:
  python proc_moon_lander.py <output_glb>
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
import bpy, bmesh, math, mathutils, sys, random

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "moonlander.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0x10D6)

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

mat_moon     = pbr_mat("moon",     (0.55, 0.52, 0.48), 0.00, 0.95)
mat_moon_d   = pbr_mat("moon_d",   (0.40, 0.38, 0.36), 0.00, 0.95)
mat_gold     = pbr_mat("gold",     (0.92, 0.72, 0.20), 0.30, 0.40)
mat_silver   = pbr_mat("silver",   (0.72, 0.72, 0.75), 0.85, 0.30)
mat_dark     = pbr_mat("dark",     (0.10, 0.10, 0.11), 0.30, 0.45)
mat_window   = pbr_mat("window",   (0.20, 0.30, 0.45), 0.30, 0.20,
                          emission=((0.25, 0.45, 0.65), 1.0))
mat_flag_r   = pbr_mat("flag_red", (0.85, 0.18, 0.18), 0.05, 0.55)
mat_flag_w   = pbr_mat("flag_wht", (0.95, 0.95, 0.92), 0.05, 0.55)
mat_flag_b   = pbr_mat("flag_blu", (0.18, 0.30, 0.65), 0.05, 0.55)
mat_pole     = pbr_mat("pole",     (0.78, 0.78, 0.80), 0.85, 0.30)
mat_thrust   = pbr_mat("thrust",   (1.00, 0.65, 0.20), 0.00, 0.10,
                          emission=((1.00, 0.65, 0.20), 8.0))
mat_star     = pbr_mat("star",     (1.00, 0.95, 0.85), 0.00, 0.10,
                          emission=((1.00, 0.95, 0.85), 6.0))

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

def _sphere(name, R, location, mat, u=14, v=10, scale=(1,1,1)):
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

# --- moon surface + craters + space + stars ---
_box("moon_ground", 4.0, 4.0, 0.04, (0, 0, -0.04), mat_moon)
# 8 small craters
for i in range(8):
    a = rng.uniform(0, 2*math.pi)
    r = rng.uniform(0.6, 1.6)
    cx = r * math.cos(a); cy = r * math.sin(a)
    R = rng.uniform(0.10, 0.20)
    _cyl(f"crater_{i}", R, R * 0.8, 0.015, 'Z',
           (cx, cy, 0.012), mat_moon_d, segments=18)
# space backdrop with stars
_box("space_back", 4.5, 0.04, 3.0, (0, 2.2, 1.5), pbr_mat("space_bg", (0.02, 0.02, 0.05), 0.0, 0.95))
for i in range(30):
    sx = rng.uniform(-2.0, 2.0)
    sz = rng.uniform(0.2, 2.8)
    _sphere(f"star_{i}", rng.uniform(0.012, 0.025),
              (sx, 2.18, sz), mat_star, u=8, v=6)

# Lander dimensions
DESCENT_R = 0.45
DESCENT_H = 0.18
DESCENT_Z = 0.20

# --- descent stage (gold-foil octagonal box) ---
_cyl("descent_stage", DESCENT_R, DESCENT_R * 0.92, DESCENT_H, 'Z',
       (0, 0, DESCENT_Z), mat_gold, segments=8)
# top plate
_cyl("descent_top", DESCENT_R * 0.85, DESCENT_R * 0.85, 0.020, 'Z',
       (0, 0, DESCENT_Z + DESCENT_H/2 + 0.012), mat_silver, segments=8)
# descent engine bell underneath (central)
_cyl("descent_engine", 0.10, 0.16, 0.12, 'Z',
       (0, 0, DESCENT_Z - DESCENT_H/2 - 0.04), mat_dark, segments=16)

# --- 4 landing legs ---
for i in range(4):
    a = i * math.pi/2 + math.pi/4
    foot_dist = 0.85
    fx = foot_dist * math.cos(a)
    fy = foot_dist * math.sin(a)
    # leg from descent corner to foot
    p0 = mathutils.Vector((DESCENT_R * 0.85 * math.cos(a), DESCENT_R * 0.85 * math.sin(a),
                            DESCENT_Z - DESCENT_H/2))
    p1 = mathutils.Vector((fx, fy, 0.025))
    d = p1 - p0
    midp = (p0 + p1) * 0.5
    leg = _cyl(f"leg_{i}", 0.018, 0.018, d.length, 'Z', (0,0,0), mat_silver, segments=10)
    leg.location = midp
    leg.rotation_mode = 'QUATERNION'
    leg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d.normalized())
    # footpad (small flat disc)
    _cyl(f"footpad_{i}", 0.08, 0.08, 0.012, 'Z', (fx, fy, 0.018),
           mat_silver, segments=14)
    # cross brace strut
    p_brace_0 = mathutils.Vector((DESCENT_R * 0.85 * math.cos(a), DESCENT_R * 0.85 * math.sin(a),
                                    DESCENT_Z - DESCENT_H/2 - 0.01))
    p_brace_1 = mathutils.Vector((fx * 0.6, fy * 0.6, 0.05))
    d2 = p_brace_1 - p_brace_0
    midb = (p_brace_0 + p_brace_1) * 0.5
    brace = _cyl(f"brace_{i}", 0.010, 0.010, d2.length, 'Z', (0,0,0), mat_silver, segments=8)
    brace.location = midb
    brace.rotation_mode = 'QUATERNION'
    brace.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d2.normalized())

# --- ascent stage (angular crew cabin) ---
ASCENT_Z = DESCENT_Z + DESCENT_H/2 + 0.14
# main cabin (a cylinder for body)
_cyl("ascent_body", 0.30, 0.30, 0.20, 'Z', (0, 0, ASCENT_Z), mat_silver, segments=12)
# front cabin section (angular, where windows are)
_box("ascent_front", 0.30, 0.18, 0.18,
       (0, -0.20, ASCENT_Z), mat_silver,
       rot=(math.radians(8), 0, 0))
# 2 triangular windows (small emissive blue panels)
for sx in (-1, +1):
    _box(f"window_{sx}", 0.10, 0.005, 0.10,
           (sx * 0.10, -0.295, ASCENT_Z + 0.02), mat_window,
           rot=(math.radians(8), 0, 0))
# top dome / hatch
_cyl("ascent_top", 0.25, 0.20, 0.05, 'Z',
       (0, 0, ASCENT_Z + 0.12), mat_silver, segments=12)
# ascent engine bell (centered underneath ascent stage)
_cyl("ascent_engine", 0.06, 0.10, 0.07, 'Z',
       (0, 0, DESCENT_Z + DESCENT_H/2 + 0.04), mat_dark, segments=16)

# --- 4 RCS thruster quads (small clusters at ascent stage corners) ---
thrust_quads = []
for i in range(4):
    a = i * math.pi/2 + math.pi/4
    tq_x = 0.30 * math.cos(a)
    tq_y = 0.30 * math.sin(a)
    # 4 thruster nozzles per quad (pointing in 4 directions)
    quad_objs = []
    for d in range(4):
        d_ang = d * math.pi/2
        nx = tq_x + 0.025 * math.cos(d_ang)
        ny = tq_y + 0.025 * math.sin(d_ang)
        # nozzle body
        noz = _cyl(f"rcs_{i}_{d}", 0.010, 0.005, 0.025, 'Z',
                     (nx, ny, ASCENT_Z + 0.05), mat_dark, segments=8)
        # thruster flame (only on a few — but emissive material shared, animated)
        quad_objs.append(noz)
    # one bright thruster flame per quad
    flame = _sphere(f"thrust_flame_{i}", 0.018,
                      (tq_x, tq_y, ASCENT_Z + 0.02), mat_thrust,
                      u=10, v=8, scale=(1.0, 1.0, 1.6))
    thrust_quads.append(flame)

# --- antenna dish on top ---
_cyl("antenna_pole", 0.008, 0.008, 0.12, 'Z',
       (0.10, 0.15, ASCENT_Z + 0.22), mat_silver, segments=8)
_sphere("antenna_dish", 0.05, (0.10, 0.15, ASCENT_Z + 0.30), mat_silver,
          u=14, v=10, scale=(1.0, 1.0, 0.4))

# --- US flag planted in soil ---
FLAG_X = -1.20
FLAG_Y = 0.40
# pole
_cyl("flag_pole", 0.012, 0.012, 0.80, 'Z',
       (FLAG_X, FLAG_Y, 0.40), mat_pole, segments=10)
# flag pivot (anim sway)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(FLAG_X, FLAG_Y, 0.75))
flag_pivot = bpy.context.active_object
flag_pivot.name = "flag_pivot"
# 5 red stripes + 4 white stripes
for k in range(5):
    pz = -0.06 + k * 0.020
    f_r = _box(f"flag_red_{k}", 0.25, 0.005, 0.018,
                 (0.13, 0, pz), mat_flag_r)
    f_r.parent = flag_pivot
    f_r.matrix_parent_inverse = mathutils.Matrix.Identity(4)
for k in range(4):
    pz = -0.05 + k * 0.020
    f_w = _box(f"flag_wht_{k}", 0.25, 0.005, 0.018,
                 (0.13, 0, pz), mat_flag_w)
    f_w.parent = flag_pivot
    f_w.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# blue canton
canton = _box("flag_canton", 0.10, 0.005, 0.045,
                (0.075, 0, 0.025), mat_flag_b)
canton.parent = flag_pivot
canton.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ---
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# 4 RCS thrusters : each fires in a sequenced pulse (chained)
bsdf_t = mat_thrust.node_tree.nodes.get("Principled BSDF")
em_t = bsdf_t.inputs["Emission Strength"]
# We can't really animate per-flame independently since they share the material.
# Animate the shared emission strength + scale of each flame individually.
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    pulse = math.exp(-((math.sin(2*math.pi*t * 6) - 0.7) * 6)**2) if math.sin(2*math.pi*t * 6) > 0 else 0
    em_t.default_value = 4.0 + 8.0 * pulse
    bpy.context.scene.frame_set(f)
    em_t.keyframe_insert(data_path="default_value", frame=f)

# Each flame sphere scales individually with offset phase
for i, flame in enumerate(thrust_quads):
    phase = i * 0.25
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        local = (t + phase) % 1.0
        scale = 0.3 + 1.5 * math.exp(-((local - 0.2) * 8)**2)
        bpy.context.scene.frame_set(f)
        flame.scale = (scale, scale, scale * 1.6)
        flame.keyframe_insert("scale", frame=f)
    if flame.animation_data and flame.animation_data.action:
        for fc in flame.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

# Flag sways (rotation around Z)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    flag_pivot.rotation_euler = (0, 0, math.radians(8) * math.sin(2*math.pi*t * 0.5))
    flag_pivot.keyframe_insert("rotation_euler", frame=f)
if flag_pivot.animation_data and flag_pivot.animation_data.action:
    for fc in flag_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"LM_OK: {out_glb}", flush=True)
'''


def make_lm(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_lm_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "LM_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_lm(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
