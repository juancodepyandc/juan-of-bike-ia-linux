"""Procedural 16mm film projector (Blender headless).

Dark metal body + 2 reels (feed top + take-up bottom) + film loop joining
them + lens barrel + lamp housing in back + visible emissive lamp + a
translucent yellow cone of projected light extending forward. Mounted on
a small table. Animation : both reels spin (take-up at 1.4x feed
speed) + lamp pulses subtly + projected light cone pulses brightness.

CLI:
  python proc_film_projector.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "projector.glb"

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

mat_floor   = pbr_mat("floor",      (0.12, 0.12, 0.14), 0.00, 0.85)
mat_table   = pbr_mat("table",      (0.25, 0.14, 0.08), 0.05, 0.55)
mat_body    = pbr_mat("body",       (0.10, 0.10, 0.11), 0.60, 0.35)
mat_chrome  = pbr_mat("chrome",     (0.78, 0.80, 0.83), 1.00, 0.18)
mat_reel    = pbr_mat("reel",       (0.18, 0.18, 0.20), 0.80, 0.32)
mat_film    = pbr_mat("film",       (0.05, 0.05, 0.06), 0.05, 0.40)
mat_lens    = pbr_mat("lens",       (0.10, 0.15, 0.20), 0.05, 0.15, alpha=0.65)
mat_lamp    = pbr_mat("lamp",       (1.00, 0.95, 0.75), 0.00, 0.10,
                         emission=((1.00, 0.92, 0.65), 25.0))
mat_beam    = pbr_mat("beam",       (1.00, 0.90, 0.50), 0.00, 0.10, alpha=0.18,
                         emission=((1.00, 0.92, 0.60), 1.6))
mat_screw   = pbr_mat("screw",      (0.55, 0.50, 0.45), 0.60, 0.40)

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

def _sphere(name, R, location, mat, u=14, v=10):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- floor + table ----------------------------------------
_box("floor", 3.2, 3.2, 0.04, (0, 0, -0.04), mat_floor)
# table : a low wooden stand
TABLE_H = 0.45
_box("table_top", 0.95, 0.55, 0.04, (0, 0, TABLE_H), mat_table)
for sx in (-1, +1):
    for sy in (-1, +1):
        _box(f"table_leg_{sx}_{sy}", 0.03, 0.03, TABLE_H,
               (sx * 0.42, sy * 0.22, TABLE_H/2), mat_table)

# --- main body of the projector ------------------------
# It points along -Y (projection beam comes out of -Y face).
BODY_W = 0.32
BODY_D = 0.50
BODY_H = 0.24
BODY_Z = TABLE_H + 0.04 + BODY_H/2  # sit on the table
_box("body", BODY_W, BODY_D, BODY_H, (0, 0, BODY_Z), mat_body)
# accent stripe (chrome on the side)
for sx in (-1, +1):
    _box(f"body_stripe_{sx}", 0.005, BODY_D * 0.7, 0.015,
           (sx * (BODY_W/2 + 0.0025), 0, BODY_Z), mat_chrome)
# corner screws (4 chrome dots on each side)
for sx in (-1, +1):
    for sy in (-1, +1):
        _sphere(f"body_screw_{sx}_{sy}", 0.006,
                  (sx * (BODY_W/2 + 0.001), sy * (BODY_D/2 - 0.04), BODY_Z + 0.08), mat_screw)

# --- lens barrel (sticks out the front, -Y direction) -----
LENS_R = 0.05
LENS_LEN = 0.20
LENS_Y = -BODY_D/2 - LENS_LEN/2
# barrel base (mounted to body)
_cyl("lens_mount", LENS_R + 0.015, LENS_R + 0.015, 0.04, 'Y',
       (0, -BODY_D/2 - 0.02, BODY_Z), mat_body)
# barrel
_cyl("lens_barrel", LENS_R, LENS_R, LENS_LEN, 'Y',
       (0, LENS_Y, BODY_Z), mat_body)
# barrel ridge rings (2 chrome rings near the front)
for k, frac in enumerate((0.35, 0.7)):
    yz = LENS_Y - LENS_LEN/2 + frac * LENS_LEN
    _cyl(f"lens_ring_{k}", LENS_R + 0.008, LENS_R + 0.008, 0.012, 'Y',
           (0, yz, BODY_Z), mat_chrome)
# the actual lens glass at the front face
_cyl("lens_glass", LENS_R - 0.005, LENS_R - 0.005, 0.01, 'Y',
       (0, LENS_Y - LENS_LEN/2, BODY_Z), mat_lens)

# --- back lamp housing (sticks out the rear, +Y) -------
LAMP_R = 0.07
LAMP_LEN = 0.16
LAMP_Y = BODY_D/2 + LAMP_LEN/2
_cyl("lamp_housing", LAMP_R + 0.005, LAMP_R + 0.005, LAMP_LEN, 'Y',
       (0, LAMP_Y, BODY_Z), mat_body)
# emissive lamp bulb visible through a small port on the front of the
# housing (we just put a sphere at the +Y end pointing outward)
_sphere("lamp_bulb", 0.035, (0, LAMP_Y + LAMP_LEN/2 - 0.02, BODY_Z), mat_lamp)

# --- top + bottom reels ------------------------------
# Reels are vertical discs (axis = Y), mounted on the front face of the body
# Top reel : x=0, y just behind front, z above body
REEL_R = 0.13
REEL_T = 0.012
HUB_R  = 0.04
def make_reel(name, z, mat_body_disc):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, -BODY_D/2 + 0.02, z))
    pv = bpy.context.active_object
    pv.name = name + "_pivot"
    # front side disc
    front = _cyl(name + "_front", REEL_R, REEL_R, REEL_T, 'Y',
                   (0, 0, 0), mat_body_disc, segments=32)
    front.parent = pv; front.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # film wound on the reel : a slightly smaller wider cylinder
    film_disc = _cyl(name + "_film", REEL_R * 0.9, REEL_R * 0.9, 0.025, 'Y',
                       (0, -0.018, 0), mat_film, segments=32)
    film_disc.parent = pv; film_disc.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # back disc
    back = _cyl(name + "_back", REEL_R, REEL_R, REEL_T, 'Y',
                  (0, -0.035, 0), mat_body_disc, segments=32)
    back.parent = pv; back.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # central hub (chrome)
    hub = _cyl(name + "_hub", HUB_R, HUB_R, 0.05, 'Y',
                 (0, -0.015, 0), mat_chrome, segments=20)
    hub.parent = pv; hub.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # 6 cross arms (small boxes radiating out from the hub on the front face)
    for i in range(6):
        a = i * math.pi/3
        cx = (HUB_R + REEL_R) / 2 * math.cos(a)
        cz = (HUB_R + REEL_R) / 2 * math.sin(a)
        arm = _box(name + f"_arm_{i}", 0.006, 0.002, REEL_R - HUB_R - 0.005,
                     (cx, 0.005, cz), mat_body_disc,
                     rot=(0, 0, a + math.pi/2))
        arm.parent = pv; arm.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    return pv

reel_top    = make_reel("reel_top",    BODY_Z + BODY_H/2 + REEL_R - 0.02, mat_reel)
reel_bottom = make_reel("reel_bottom", BODY_Z - BODY_H/2 - REEL_R + 0.02, mat_reel)

# --- film loop : 2 thin strips connecting the two reels ----
# We just draw a thin vertical strip at +REEL_R - 0.02 on each reel
# circumference (the outer edge), in front of the body.
for sx in (-1, +1):
    fy = -BODY_D/2 + 0.02
    strip = _box(f"film_strip_{sx}", 0.012, 0.002, BODY_H + 0.18,
                   (sx * (REEL_R - 0.02), fy + 0.015, BODY_Z), mat_film)

# --- focus knob on the side ---------------------
_cyl("focus_knob", 0.02, 0.02, 0.04, 'X',
       (BODY_W/2 + 0.02, -BODY_D * 0.15, BODY_Z + 0.04), mat_chrome)
_cyl("focus_inner", 0.014, 0.014, 0.01, 'X',
       (BODY_W/2 + 0.041, -BODY_D * 0.15, BODY_Z + 0.04), mat_body)

# --- projection beam (translucent emissive cone -Y) -----
# A cone whose tip is at the lens and base is far ahead.
BEAM_LEN = 1.20
beam = _cyl("beam_cone", 0.04, 0.45, BEAM_LEN, 'Y',
              (0, LENS_Y - LENS_LEN/2 - BEAM_LEN/2, BODY_Z), mat_beam, segments=24)

# --- power cord (cable from base of housing curving down to the table) ---
CAB_PTS = [
    (0,  LAMP_Y + LAMP_LEN/2 + 0.02, BODY_Z - 0.05),
    (0,  LAMP_Y + LAMP_LEN/2 + 0.08, BODY_Z - 0.15),
    (0,  LAMP_Y + LAMP_LEN/2 + 0.14, TABLE_H + 0.06),
    (0.08, LAMP_Y + LAMP_LEN/2 + 0.18, TABLE_H + 0.04),
]
for i in range(len(CAB_PTS) - 1):
    p0 = CAB_PTS[i]; p1 = CAB_PTS[i+1]
    mx = (p0[0]+p1[0])/2; my = (p0[1]+p1[1])/2; mz = (p0[2]+p1[2])/2
    dx, dy, dz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
    L = math.sqrt(dx*dx + dy*dy + dz*dz)
    seg = _cyl(f"cable_{i}", 0.006, 0.006, L, 'Z', (0,0,0), mat_body)
    seg.location = (mx, my, mz)
    direction = mathutils.Vector((dx, dy, dz)).normalized()
    seg.rotation_mode = 'QUATERNION'
    seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)

# --- animation -----------------------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# Top reel spins around Y at constant speed (1 turn / loop = clockwise viewed
# from -Y). Bottom reel = 1.4x take-up speed in same direction.
TOP_TURNS    = 1.0
BOTTOM_TURNS = 1.4
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    reel_top.rotation_euler    = (0, 2 * math.pi * TOP_TURNS    * t, 0)
    reel_bottom.rotation_euler = (0, 2 * math.pi * BOTTOM_TURNS * t, 0)
    reel_top.keyframe_insert("rotation_euler",    frame=f)
    reel_bottom.keyframe_insert("rotation_euler", frame=f)
for pv in (reel_top, reel_bottom):
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# lamp + beam pulse (24 Hz shutter-like flicker)
bsdf_l = mat_lamp.node_tree.nodes.get("Principled BSDF")
em_l = bsdf_l.inputs["Emission Strength"]
bsdf_b = mat_beam.node_tree.nodes.get("Principled BSDF")
em_b = bsdf_b.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    # 24-fps shutter feel : a tooth-shaped pulse, not just sin
    phase = (t * 24.0) % 1.0
    flicker = 0.55 + 0.45 * (1.0 - phase if phase > 0.2 else 1.0)
    em_l.default_value = 18.0 * flicker + 8.0
    em_b.default_value = 1.4 * flicker + 0.4
    bpy.context.scene.frame_set(f)
    em_l.keyframe_insert(data_path="default_value", frame=f)
    em_b.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"PROJ_OK: {out_glb}", flush=True)
'''


def make_projector(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_proj_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "PROJ_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_projector(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
