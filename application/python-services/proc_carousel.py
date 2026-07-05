"""Procedural carousel / merry-go-round (Blender headless).

Round platform + 4 horse stand-ins (simplified body+head+legs) on
vertical brass poles + 4 outer ornamental poles + tall central column +
striped conical roof + finial spire. Animation : entire carousel spins
1 turn / 8 s + each horse bobs vertically on its pole (sin, offset by
90 deg between horses for the classic galloping illusion).

CLI:
  python proc_carousel.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "carousel.glb"

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

mat_floor   = pbr_mat("floor",      (0.20, 0.20, 0.22), 0.00, 0.85)
mat_plat    = pbr_mat("platform",   (0.65, 0.20, 0.20), 0.05, 0.40)
mat_plat_lt = pbr_mat("plat_band",  (0.95, 0.85, 0.55), 0.10, 0.35)
mat_brass   = pbr_mat("brass",      (0.92, 0.72, 0.25), 1.00, 0.20)
mat_red     = pbr_mat("red_stripe", (0.85, 0.10, 0.10), 0.05, 0.35)
mat_white   = pbr_mat("white_stripe",(0.92, 0.92, 0.90),0.05, 0.35)
mat_pole    = pbr_mat("center_pole",(0.55, 0.10, 0.10), 0.10, 0.40)
mat_horse_w = pbr_mat("horse_white",(0.92, 0.90, 0.85), 0.05, 0.35)
mat_horse_p = pbr_mat("horse_paint",(0.18, 0.10, 0.06), 0.05, 0.45)
mat_horse_m = pbr_mat("horse_mane", (0.60, 0.20, 0.10), 0.05, 0.50)
mat_saddle  = pbr_mat("saddle_red", (0.75, 0.18, 0.18), 0.05, 0.35)
mat_bulb    = pbr_mat("bulb",       (1.00, 0.90, 0.60), 0.00, 0.10,
                          emission=((1.00, 0.85, 0.40), 12.0))

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=20):
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

def _sphere(name, R, location, mat, u=16, v=10):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- floor -------------------------------------------------
_box("floor", 3.5, 3.5, 0.04, (0, 0, -0.04), mat_floor)

# --- main rotating pivot at origin -----------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
carousel = bpy.context.active_object
carousel.name = "carousel_pivot"

# --- platform (round red disc with light wood band) ---
PLAT_R = 1.20
PLAT_H = 0.10
plat = _cyl("platform", PLAT_R, PLAT_R, PLAT_H, 'Z',
              (0, 0, PLAT_H/2), mat_plat, segments=48)
plat.parent = carousel; plat.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# decorative top band (a thin lighter ring)
band = _cyl("plat_band", PLAT_R * 1.02, PLAT_R * 1.02, 0.015, 'Z',
              (0, 0, PLAT_H + 0.0075), mat_plat_lt, segments=48)
band.parent = carousel; band.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# bottom rim (darker)
bot = _cyl("plat_bot", PLAT_R * 0.95, PLAT_R * 0.95, 0.04, 'Z',
             (0, 0, -0.02), mat_plat, segments=48)
bot.parent = carousel; bot.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- central column --------------------------------------
COL_H = 1.70
COL_Z = PLAT_H + COL_H/2
col = _cyl("center_col", 0.10, 0.10, COL_H, 'Z', (0, 0, COL_Z), mat_pole, segments=20)
col.parent = carousel; col.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# brass collars at top and bottom of column
for z_off in (0.06, COL_H - 0.06):
    coll = _cyl(f"col_collar_{z_off:.2f}", 0.12, 0.12, 0.04, 'Z',
                  (0, 0, PLAT_H + z_off), mat_brass, segments=20)
    coll.parent = carousel; coll.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- conical roof + alternating stripes ---------------
# We approximate stripes by 8 wedge sectors alternating red/white.
ROOF_BASE_Z = PLAT_H + COL_H
ROOF_R = PLAT_R * 0.95
ROOF_TIP_Z = ROOF_BASE_Z + 0.50
SECTORS = 8
for i in range(SECTORS):
    a0 = 2*math.pi * i / SECTORS
    a1 = 2*math.pi * (i+1) / SECTORS
    mat = mat_red if i % 2 == 0 else mat_white
    # build a wedge mesh : triangle from center-top (apex) to two base points
    mesh = bpy.data.meshes.new(f"roof_{i}")
    obj = bpy.data.objects.new(f"roof_{i}", mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    apex = bm.verts.new((0, 0, ROOF_TIP_Z))
    # 4 verts along the arc, so each sector looks curved
    SUB = 5
    arc_verts = []
    for k in range(SUB + 1):
        ak = a0 + (a1 - a0) * (k / SUB)
        x = ROOF_R * math.cos(ak); y = ROOF_R * math.sin(ak)
        arc_verts.append(bm.verts.new((x, y, ROOF_BASE_Z)))
    # fan triangles
    for k in range(SUB):
        bm.faces.new([apex, arc_verts[k], arc_verts[k+1]])
    # a small base triangle to close the underside
    bm.to_mesh(mesh); bm.free()
    obj.data.materials.append(mat)
    obj.parent = carousel; obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- finial spire on top of the roof ----------------
spire = _cyl("spire", 0.04, 0.001, 0.30, 'Z',
              (0, 0, ROOF_TIP_Z + 0.15), mat_brass, segments=12)
spire.parent = carousel; spire.matrix_parent_inverse = mathutils.Matrix.Identity(4)
spire_ball = _sphere("spire_ball", 0.05, (0, 0, ROOF_TIP_Z + 0.06), mat_brass)
spire_ball.parent = carousel; spire_ball.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- horse builder ------------------------------------
HORSE_R = 0.78  # radial distance from center

def add_horse(name, angle, phase, body_mat, mane_mat):
    """A simplified horse made of boxes : body + neck + head + 4 legs.
    Returned bob_pivot is an empty whose Z is animated."""
    cos_a = math.cos(angle); sin_a = math.sin(angle)
    px = HORSE_R * cos_a; py = HORSE_R * sin_a
    # pole (brass cylinder from platform to roof base)
    pole_z = (PLAT_H + ROOF_BASE_Z) / 2
    pole_h = ROOF_BASE_Z - PLAT_H + 0.10
    pole = _cyl(f"{name}_pole", 0.018, 0.018, pole_h, 'Z',
                  (px, py, pole_z), mat_brass)
    pole.parent = carousel; pole.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # bob_pivot : an empty positioned at "horse height" — animation will
    # offset this in Z and the whole horse goes with it.
    bob_z0 = PLAT_H + 0.55
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(px, py, bob_z0))
    bp = bpy.context.active_object
    bp.name = f"{name}_bob"
    bp.parent = carousel; bp.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # rotate the horse so it faces tangentially (perpendicular to radial)
    bp.rotation_euler = (0, 0, angle + math.pi/2)

    # body : rounded box
    body = _box(f"{name}_body", 0.42, 0.16, 0.20, (0, 0, 0), body_mat)
    body.parent = bp; body.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # neck (tilted up)
    neck = _box(f"{name}_neck", 0.10, 0.10, 0.20, (0.18, 0, 0.14), body_mat,
                  rot=(0, math.radians(-30), 0))
    neck.parent = bp; neck.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # head
    head = _box(f"{name}_head", 0.16, 0.08, 0.10, (0.27, 0, 0.24), body_mat,
                  rot=(0, math.radians(-15), 0))
    head.parent = bp; head.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # ears (2 small triangles, approximated as boxes)
    for sy in (-1, +1):
        ear = _box(f"{name}_ear_{sy}", 0.02, 0.02, 0.04,
                     (0.27, sy * 0.03, 0.30), body_mat)
        ear.parent = bp; ear.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # mane (4 small flames on the neck/head)
    for k in range(4):
        mx = 0.10 + k * 0.04
        mh = _box(f"{name}_mane_{k}", 0.02, 0.04, 0.06,
                    (mx, 0, 0.18 + k * 0.01), mane_mat)
        mh.parent = bp; mh.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # tail
    tail = _box(f"{name}_tail", 0.04, 0.04, 0.16, (-0.22, 0, 0.04), mane_mat,
                  rot=(0, math.radians(20), 0))
    tail.parent = bp; tail.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # 4 legs
    for sx, sy in ((-0.14, -0.08), (0.14, -0.08), (-0.14, 0.08), (0.14, 0.08)):
        leg = _box(f"{name}_leg_{sx:+.2f}_{sy:+.2f}", 0.03, 0.03, 0.18,
                     (sx, sy, -0.18), body_mat)
        leg.parent = bp; leg.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # saddle (small red box on the back)
    sad = _box(f"{name}_saddle", 0.22, 0.16, 0.04, (0, 0, 0.12), mat_saddle)
    sad.parent = bp; sad.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # bulb (small emissive ball above the horse, mounted near the pole)
    bulb = _sphere(f"{name}_bulb", 0.025, (-0.05, 0, 0.40), mat_bulb)
    bulb.parent = bp; bulb.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    return bp, bob_z0, phase

# add 4 horses 90 deg apart, alternating colors and phases
HORSE_DEFS = [
    (math.radians(0),    0.00, mat_horse_w, mat_horse_m),
    (math.radians(90),   math.pi/2, mat_horse_p, mat_horse_m),
    (math.radians(180),  math.pi,   mat_horse_w, mat_horse_m),
    (math.radians(270),  3*math.pi/2, mat_horse_p, mat_horse_m),
]
horses = []
for i, (ang, ph, body_mat, mane_mat) in enumerate(HORSE_DEFS):
    horses.append(add_horse(f"horse_{i}", ang, ph, body_mat, mane_mat))

# --- outer light strands (8 small bulbs around the platform edge) ---
for i in range(8):
    a = 2*math.pi * i / 8
    bx = (PLAT_R * 1.05) * math.cos(a)
    by = (PLAT_R * 1.05) * math.sin(a)
    bulb = _sphere(f"edge_bulb_{i}", 0.025, (bx, by, PLAT_H + 0.10), mat_bulb)
    bulb.parent = carousel; bulb.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation -------------------------------------------------
FPS = 30
DURATION = 8.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# carousel rotates 1 full turn per loop
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    carousel.rotation_euler = (0, 0, 2*math.pi * t)
    carousel.keyframe_insert("rotation_euler", frame=f)
if carousel.animation_data and carousel.animation_data.action:
    for fc in carousel.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# each horse bobs vertically with its phase
BOB_AMP = 0.10
for (bp, z0, phase) in horses:
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        z = z0 + BOB_AMP * math.sin(2*math.pi*t*2 + phase)
        # bp.location.x/y must remain unchanged (set in add_horse via location)
        bp.location.z = z
        bp.keyframe_insert("location", frame=f)
    if bp.animation_data and bp.animation_data.action:
        for fc in bp.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

# bulbs throb (mat_bulb emission strength)
bsdf_b = mat_bulb.node_tree.nodes.get("Principled BSDF")
em_b = bsdf_b.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_b.default_value = 10.0 + 5.0 * (0.5 + 0.5 * math.sin(2*math.pi*t*3))
    bpy.context.scene.frame_set(f)
    em_b.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"CAROUSEL_OK: {out_glb}", flush=True)
'''


def make_carousel(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_carousel_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "CAROUSEL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_carousel(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
