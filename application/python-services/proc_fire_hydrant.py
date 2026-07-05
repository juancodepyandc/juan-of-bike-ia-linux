"""Procedural American fire hydrant (Blender headless).

Hexagonal red base + cylindrical red barrel + bonnet cap + 2 side
discharge outlets with chrome caps + chains tethering the caps + main
operating nut on top + a side jet of water spraying when in use.
Animation : water jet emerges from the +X outlet with scale Y oscillating
+ 6 splash droplets fly off in arcs.

CLI:
  python proc_fire_hydrant.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "hydrant.glb"

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

mat_floor   = pbr_mat("floor",     (0.32, 0.30, 0.28), 0.00, 0.85)
mat_pave    = pbr_mat("pave",      (0.42, 0.40, 0.36), 0.00, 0.85)
mat_red     = pbr_mat("red",       (0.78, 0.12, 0.10), 0.15, 0.35)
mat_red_d   = pbr_mat("red_dk",    (0.55, 0.06, 0.04), 0.15, 0.40)
mat_yellow  = pbr_mat("yellow",    (0.92, 0.78, 0.18), 0.20, 0.30)
mat_chrome  = pbr_mat("chrome",    (0.80, 0.82, 0.85), 1.00, 0.18)
mat_chain   = pbr_mat("chain",     (0.55, 0.55, 0.58), 0.90, 0.30)
mat_dark    = pbr_mat("dark",      (0.08, 0.08, 0.09), 0.30, 0.45)
mat_water   = pbr_mat("water",     (0.55, 0.78, 0.92), 0.05, 0.10, alpha=0.40,
                          emission=((0.55, 0.78, 0.95), 0.4))

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=20, rot=None):
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

# Conventions : hydrant on the pavement. Outlets face +X / -X. Up = +Z.

# --- pavement ----------------------
_box("floor", 1.4, 1.4, 0.04, (0, 0, -0.04), mat_floor)
_box("pave_slab", 0.7, 0.7, 0.04, (0, 0, 0.02), mat_pave)

# --- hexagonal base flange (6-segment cylinder) ----
BASE_R = 0.18
BASE_H = 0.08
_cyl("base_flange", BASE_R, BASE_R, BASE_H, 'Z',
       (0, 0, 0.04 + BASE_H/2), mat_red_d, segments=6)
# 6 bolt heads on the flange (small chrome cylinders at 6 vertices)
for k in range(6):
    a = k * math.pi/3 + math.pi/6
    bx = (BASE_R - 0.025) * math.cos(a)
    by = (BASE_R - 0.025) * math.sin(a)
    _cyl(f"bolt_{k}", 0.013, 0.013, 0.014, 'Z',
           (bx, by, 0.04 + BASE_H + 0.005), mat_chrome, segments=10)

# --- main barrel (red cylinder) ---
BARREL_R = 0.10
BARREL_H = 0.40
BARREL_Z = 0.04 + BASE_H + BARREL_H/2
_cyl("barrel", BARREL_R, BARREL_R, BARREL_H, 'Z',
       (0, 0, BARREL_Z), mat_red, segments=30)

# 2 decorative red rings at top and bottom of barrel
for rz in (BARREL_Z - BARREL_H/2 + 0.02, BARREL_Z + BARREL_H/2 - 0.02):
    _cyl(f"barrel_ring_{rz:.2f}", BARREL_R * 1.08, BARREL_R * 1.08, 0.015, 'Z',
           (0, 0, rz), mat_red_d, segments=30)

# --- 2 side discharge outlets (chrome) ---
OUTLET_R = 0.045
OUTLET_LEN = 0.10
OUTLET_Z = BARREL_Z + 0.02
for sx in (-1, +1):
    # outlet pipe extending in +X / -X
    _cyl(f"outlet_{sx}", OUTLET_R, OUTLET_R, OUTLET_LEN, 'X',
           (sx * (BARREL_R + OUTLET_LEN/2 - 0.005), 0, OUTLET_Z),
           mat_red, segments=18)
    # threaded chrome ring at the end
    _cyl(f"outlet_thread_{sx}", OUTLET_R * 1.08, OUTLET_R * 1.08, 0.010, 'X',
           (sx * (BARREL_R + OUTLET_LEN - 0.005), 0, OUTLET_Z),
           mat_chrome, segments=18)

# Cap on the -X outlet (still attached) — chrome 5-spoke
LEFT_CAP_X = -(BARREL_R + OUTLET_LEN + 0.012)
_cyl("cap_L_body", OUTLET_R * 1.10, OUTLET_R * 1.10, 0.018, 'X',
       (LEFT_CAP_X, 0, OUTLET_Z), mat_chrome, segments=18)
# 5 short spokes on the cap face
for k in range(5):
    a = k * 2*math.pi / 5
    sy_o = OUTLET_R * 0.85 * math.sin(a)
    sz_o = OUTLET_R * 0.85 * math.cos(a)
    _box(f"cap_L_spoke_{k}", 0.020, 0.004, 0.004,
           (LEFT_CAP_X - 0.005, sy_o/2, OUTLET_Z + sz_o/2),
           mat_chrome, rot=(a, 0, 0))

# Cap on the +X outlet : we'll keep it but show the water jet too (cap is
# hanging slightly off to the side via the chain). Build the cap a bit off
# axis.
RIGHT_CAP_HOME = mathutils.Vector((BARREL_R + OUTLET_LEN + 0.012, 0, OUTLET_Z))
RIGHT_CAP_OFFSET = mathutils.Vector((0.08, 0.05, -0.05))
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=RIGHT_CAP_HOME + RIGHT_CAP_OFFSET)
cap_R_pivot = bpy.context.active_object
cap_R_pivot.name = "cap_R_pivot"
cap_R = _cyl("cap_R_body", OUTLET_R * 1.10, OUTLET_R * 1.10, 0.018, 'X',
               (0, 0, 0), mat_chrome, segments=18)
cap_R.parent = cap_R_pivot
cap_R.matrix_parent_inverse = mathutils.Matrix.Identity(4)
for k in range(5):
    a = k * 2*math.pi / 5
    sy_o = OUTLET_R * 0.85 * math.sin(a)
    sz_o = OUTLET_R * 0.85 * math.cos(a)
    sp = _box(f"cap_R_spoke_{k}", 0.020, 0.004, 0.004,
                (0.005, sy_o/2, sz_o/2), mat_chrome,
                rot=(a, 0, 0))
    sp.parent = cap_R_pivot
    sp.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- chain from the +X outlet to its cap (4 small chain links) ---
chain_pts = [
    (BARREL_R + 0.005, 0, OUTLET_Z + 0.025),  # anchor on hydrant body
    (BARREL_R + 0.06, -0.02, OUTLET_Z + 0.010),
    (BARREL_R + 0.10, +0.02, OUTLET_Z - 0.005),
    RIGHT_CAP_HOME + RIGHT_CAP_OFFSET + mathutils.Vector((-0.012, 0, 0)),
]
for i in range(len(chain_pts) - 1):
    p0 = mathutils.Vector(chain_pts[i])
    p1 = mathutils.Vector(chain_pts[i+1])
    d = p1 - p0
    L = d.length
    midp = (p0 + p1) * 0.5
    seg = _cyl(f"chain_R_{i}", 0.005, 0.005, L, 'Z', (0,0,0), mat_chain, segments=8)
    seg.location = midp
    direction = d.normalized()
    seg.rotation_mode = 'QUATERNION'
    seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)

# similar chain on -X (cap stays on)
chain_pts_L = [
    (-(BARREL_R + 0.005), 0, OUTLET_Z + 0.025),
    (-(BARREL_R + 0.06), -0.02, OUTLET_Z + 0.005),
    (-(BARREL_R + 0.10), 0.02, OUTLET_Z - 0.005),
    (LEFT_CAP_X + 0.012, 0, OUTLET_Z),
]
for i in range(len(chain_pts_L) - 1):
    p0 = mathutils.Vector(chain_pts_L[i])
    p1 = mathutils.Vector(chain_pts_L[i+1])
    d = p1 - p0
    L = d.length
    midp = (p0 + p1) * 0.5
    seg = _cyl(f"chain_L_{i}", 0.005, 0.005, L, 'Z', (0,0,0), mat_chain, segments=8)
    seg.location = midp
    direction = d.normalized()
    seg.rotation_mode = 'QUATERNION'
    seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)

# --- bonnet (the top dome) ---
BONNET_Z = BARREL_Z + BARREL_H/2 + 0.025
_cyl("bonnet_step", BARREL_R * 1.08, BARREL_R * 1.10, 0.030, 'Z',
       (0, 0, BARREL_Z + BARREL_H/2 + 0.015), mat_yellow, segments=30)
_sphere("bonnet_dome", BARREL_R * 1.05, (0, 0, BONNET_Z), mat_yellow,
         u=24, v=14, scale=(1.0, 1.0, 0.40))

# --- operating nut (the pentagon nut on top) ---
NUT_Z = BONNET_Z + 0.035
_cyl("op_nut", 0.030, 0.025, 0.025, 'Z',
       (0, 0, NUT_Z), mat_dark, segments=5)
# tiny chrome center
_cyl("op_nut_center", 0.010, 0.010, 0.030, 'Z',
       (0, 0, NUT_Z + 0.002), mat_chrome, segments=10)

# --- identification plate on the front of the barrel (yellow square with text marks) ---
_box("ID_plate", 0.025, 0.005, 0.06,
       (0, -BARREL_R - 0.005, BARREL_Z - 0.05), mat_yellow)
for k in range(3):
    _box(f"ID_mark_{k}", 0.015, 0.0005, 0.004,
           (0, -BARREL_R - 0.010, BARREL_Z - 0.06 + k * 0.012), mat_dark)

# --- water jet emerging from +X outlet (cone-shaped translucent emissive) ---
JET_LEN = 0.45
JET_X = BARREL_R + OUTLET_LEN + JET_LEN/2 + 0.020
jet = _cyl("water_jet", 0.020, 0.060, JET_LEN, 'X',
             (JET_X, 0, OUTLET_Z), mat_water, segments=18)

# 6 splash droplets (small water spheres) flying off in arcs
splash = []
for i in range(6):
    s = _sphere(f"droplet_{i}", 0.015,
                  (JET_X + JET_LEN/2 + 0.05 + i * 0.04, 0, OUTLET_Z),
                  mat_water)
    splash.append(s)

# --- animation ------------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# water_jet : scale Y/Z pulse + slight X stretch
home_jet_loc = jet.location.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    sx = 1.0 + 0.10 * math.sin(2*math.pi*t * 3.0)
    sy = 1.0 + 0.15 * math.sin(2*math.pi*t * 4.0 + 0.5)
    sz = 1.0 + 0.15 * math.cos(2*math.pi*t * 4.0)
    jet.scale = (sx, sy, sz)
    jet.keyframe_insert("scale", frame=f)
if jet.animation_data and jet.animation_data.action:
    for fc in jet.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# droplets : each follows a small projectile arc
for i, sp in enumerate(splash):
    phase = i / 6.0
    base_y = (i - 2.5) * 0.04   # spread laterally
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        # each droplet has its own local time wrapped
        local = (t * 2.0 + phase) % 1.0
        # ballistic arc : x increases linearly, z follows -gravity·t²
        x = JET_X + JET_LEN/2 + 0.05 + local * 0.5
        z = OUTLET_Z + 0.20 * math.sin(local * math.pi) - 0.08 * local
        y = base_y + 0.02 * math.sin(2*math.pi*local * 6 + phase * 6.28)
        bpy.context.scene.frame_set(f)
        sp.location = (x, y, z)
        sp.keyframe_insert("location", frame=f)
    if sp.animation_data and sp.animation_data.action:
        for fc in sp.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

# cap_R sways slightly on its chain
home_cap_loc = cap_R_pivot.location.copy()
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    cap_R_pivot.location = (home_cap_loc.x,
                              home_cap_loc.y + 0.010 * math.sin(2*math.pi*t * 1.8),
                              home_cap_loc.z + 0.008 * math.cos(2*math.pi*t * 1.8))
    cap_R_pivot.keyframe_insert("location", frame=f)
if cap_R_pivot.animation_data and cap_R_pivot.animation_data.action:
    for fc in cap_R_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"HYD_OK: {out_glb}", flush=True)
'''


def make_hydrant(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_hyd_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "HYD_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_hydrant(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
