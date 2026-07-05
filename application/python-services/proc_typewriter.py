"""Procedural vintage typewriter (Blender headless).

Cream metal body + roller / platen + paper sheet rising from the platen
+ 4 rows of round keys (40+ pieces) + space bar + 2 spool covers + a
carriage frame that slides + 6 type bars (the strikers) that swing
toward the paper in sequence. Animation : carriage slides X right -> left
+ 6 type bars rotate up alternately so it looks like someone is typing.

CLI:
  python proc_typewriter.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "typewriter.glb"

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

mat_floor   = pbr_mat("floor",     (0.18, 0.14, 0.12), 0.00, 0.85)
mat_body    = pbr_mat("body_crm",  (0.78, 0.72, 0.58), 0.35, 0.40)
mat_dark    = pbr_mat("body_dk",   (0.10, 0.10, 0.11), 0.50, 0.40)
mat_chrome  = pbr_mat("chrome",    (0.78, 0.80, 0.83), 1.00, 0.18)
mat_key_w   = pbr_mat("key_white", (0.92, 0.90, 0.85), 0.05, 0.30)
mat_key_b   = pbr_mat("key_black", (0.10, 0.10, 0.11), 0.05, 0.30)
mat_letter  = pbr_mat("key_letter",(0.05, 0.05, 0.06), 0.00, 0.45)
mat_paper   = pbr_mat("paper",     (0.96, 0.94, 0.88), 0.00, 0.55)
mat_platen  = pbr_mat("platen",    (0.20, 0.10, 0.06), 0.05, 0.50)
mat_ribbon  = pbr_mat("ribbon",    (0.15, 0.08, 0.06), 0.05, 0.45)
mat_bar     = pbr_mat("type_bar",  (0.20, 0.18, 0.16), 0.75, 0.32)
mat_letter_face = pbr_mat("letter_face", (0.05, 0.05, 0.05), 0.20, 0.30)

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

# --- floor + desk ----------------------------------
_box("floor", 2.0, 1.6, 0.04, (0, 0, -0.04), mat_floor)

# --- main body (curved cream-coloured chassis) ---
# Roughly the shape of a 1940s portable typewriter : a wider flat keyboard
# area at the front (low Y), and a taller back where the platen sits.
BODY_W = 0.62
BODY_D = 0.42
# front keyboard slab
front_slab_z = 0.06
front_slab = _box("body_front", BODY_W, BODY_D * 0.55, front_slab_z * 2,
                    (0, -BODY_D/2 + (BODY_D * 0.55)/2, front_slab_z), mat_body)
# back rise (where the platen rises)
back_rise_h = 0.20
back_rise = _box("body_back", BODY_W, BODY_D * 0.40, back_rise_h,
                   (0, BODY_D/2 - (BODY_D * 0.40)/2, back_rise_h/2), mat_body)
# side cheeks (flank the platen)
for sx in (-1, +1):
    _box(f"cheek_{sx}", 0.04, BODY_D * 0.45, 0.14,
           (sx * (BODY_W/2 - 0.02), BODY_D * 0.06, 0.10), mat_body)
# dark base plate just visible
_box("base_plate", BODY_W + 0.02, BODY_D + 0.02, 0.012,
       (0, 0, 0.006), mat_dark)

# --- carriage : a horizontal frame holding the platen + paper ----
# The carriage CAN slide along X ; we parent the platen + paper to it.
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, BODY_D/2 - 0.08, 0.22))
carriage = bpy.context.active_object
carriage.name = "carriage"

# carriage rails (thin chrome bar that the platen slides on)
rail = _cyl("rail", 0.008, 0.008, BODY_W * 0.88, 'X', (0, 0, -0.03), mat_chrome)
rail.parent = carriage
rail.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# platen = rubber roller along X
PLATEN_R = 0.04
PLATEN_LEN = 0.45
platen = _cyl("platen", PLATEN_R, PLATEN_R, PLATEN_LEN, 'X',
                (0, 0, 0), mat_platen, segments=24)
platen.parent = carriage
platen.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# platen end knobs (chrome)
for sx in (-1, +1):
    knob = _cyl(f"platen_knob_{sx}", PLATEN_R * 1.1, PLATEN_R * 0.9, 0.02, 'X',
                  (sx * (PLATEN_LEN/2 + 0.012), 0, 0), mat_chrome, segments=18)
    knob.parent = carriage
    knob.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# paper sheet (a tall thin slab rising vertically from behind the platen)
paper = _box("paper", PLATEN_LEN * 0.85, 0.005, 0.18,
               (0, -0.005, 0.09 + PLATEN_R), mat_paper)
paper.parent = carriage
paper.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# paper guide bar (thin chrome bar across the front of the paper)
guide = _cyl("paper_guide", 0.005, 0.005, PLATEN_LEN * 0.6, 'X',
               (0, -0.03, 0.08), mat_chrome)
guide.parent = carriage
guide.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# return lever (small chrome arm on the left side of the carriage)
lever = _cyl("return_lever", 0.005, 0.005, 0.12, 'Y',
               (-PLATEN_LEN/2 - 0.025, -0.04, 0.04), mat_chrome)
lever.parent = carriage
lever.matrix_parent_inverse = mathutils.Matrix.Identity(4)
lever_grip = _sphere("lever_grip", 0.01,
                       (-PLATEN_LEN/2 - 0.025, -0.10, 0.04), mat_dark)
lever_grip.parent = carriage
lever_grip.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- type bars : 6 strikers that swing toward the paper ----
# Pivot is on a horizontal line just in front of the carriage, low.
# When idle, bars rest at ~-70 deg (pointing toward the operator).
# When firing, they swing up to ~0 deg (pointing at the platen).
# They are parented to fixed empties (NOT to the carriage), and each empty
# is positioned along X between -0.18 and +0.18.
type_bars = []
TYPEBAR_X_RANGE = (-0.18, 0.18)
NBARS = 6
for i in range(NBARS):
    x = TYPEBAR_X_RANGE[0] + (TYPEBAR_X_RANGE[1] - TYPEBAR_X_RANGE[0]) * (i / (NBARS - 1))
    bpy.ops.object.empty_add(type='PLAIN_AXES',
                              location=(x, BODY_D * 0.08, 0.14))
    pv = bpy.context.active_object
    pv.name = f"typebar_pivot_{i}"
    # Arm itself : a thin tall box sticking up from the pivot. Its mesh
    # extends from y=0 (the pivot) up along its local +Z axis, with the
    # letter face at the top.
    arm = _box(f"typebar_arm_{i}", 0.008, 0.008, 0.13,
                 (0, 0, 0.065), mat_bar)
    arm.parent = pv
    arm.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # letter face at the top
    face = _box(f"typebar_face_{i}", 0.014, 0.012, 0.014,
                  (0, 0, 0.135), mat_letter_face)
    face.parent = pv
    face.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # rest pose : tilted back ~70 deg around X
    pv.rotation_euler = (math.radians(-70), 0, 0)
    type_bars.append(pv)

# --- keys : 4 rows of round keys ----------------------
# Keys are short cylinders on the front slab. Row layout : 10/10/10/10 keys
# in a staggered arrangement, slight perspective via Z stagger.
KEY_RADIUS = 0.014
KEY_H = 0.012
KEY_ROWS = [
    # (count, y_offset, z_offset)
    (10, -BODY_D/2 + 0.08, front_slab_z * 2 + 0.012),
    (10, -BODY_D/2 + 0.13, front_slab_z * 2 + 0.018),
    (10, -BODY_D/2 + 0.18, front_slab_z * 2 + 0.024),
    (10, -BODY_D/2 + 0.23, front_slab_z * 2 + 0.030),
]
key_count = 0
for row_idx, (n, y, z) in enumerate(KEY_ROWS):
    for k in range(n):
        # row gets a slight X offset for "staggered" layout
        x_offset = (row_idx % 2) * 0.018
        x = -BODY_W * 0.40 + x_offset + k * (BODY_W * 0.80 / (n - 1))
        # alternate black-rim / white-face look : white-cap with thin
        # black ring below
        ring = _cyl(f"key_ring_{row_idx}_{k}",
                      KEY_RADIUS + 0.001, KEY_RADIUS + 0.001, 0.003, 'Z',
                      (x, y, z - 0.001), mat_dark, segments=14)
        cap = _cyl(f"key_cap_{row_idx}_{k}",
                     KEY_RADIUS, KEY_RADIUS * 0.95, KEY_H, 'Z',
                     (x, y, z + KEY_H/2), mat_key_w, segments=14)
        # small dark spot in the centre suggesting the letter
        dot = _cyl(f"key_dot_{row_idx}_{k}",
                     KEY_RADIUS * 0.45, KEY_RADIUS * 0.45, 0.002, 'Z',
                     (x, y, z + KEY_H + 0.001), mat_letter, segments=10)
        key_count += 1

# --- space bar (long flat bar across the bottom row) -----
SBAR_Y = -BODY_D/2 + 0.04
_box("space_bar", BODY_W * 0.55, 0.04, 0.012,
       (0, SBAR_Y, front_slab_z * 2 + 0.009), mat_dark)

# --- spool covers (2 round metal discs flanking the back, behind the
# platen, where the ink ribbon is stored) -----
for sx in (-1, +1):
    cv = _cyl(f"spool_cover_{sx}", 0.045, 0.045, 0.025, 'Z',
                (sx * 0.20, BODY_D/2 - 0.06, back_rise_h + 0.012), mat_chrome,
                segments=20)
    # ribbon thread between them (thin black strip from one to the other)
_box("ribbon", 0.42, 0.006, 0.006,
       (0, BODY_D/2 - 0.06, back_rise_h + 0.018), mat_ribbon)

# --- brand label (a small chrome plate on the back rise) --
_box("label", 0.18, 0.005, 0.04,
       (0, BODY_D/2 - 0.005, back_rise_h - 0.05), mat_chrome)

# --- animation ------------------------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# Carriage slides : starts at +0.08 (right), ends at -0.08 (left), then a
# fast snap back to the right at the very end (return-lever motion).
CARR_RIGHT = +0.08
CARR_LEFT  = -0.08
home = mathutils.Vector((0, BODY_D/2 - 0.08, 0.22))
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # 90 % of the loop slides, last 10 % snaps back
    if t < 0.9:
        u = t / 0.9
        x = CARR_RIGHT + (CARR_LEFT - CARR_RIGHT) * u
    else:
        u = (t - 0.9) / 0.1
        x = CARR_LEFT + (CARR_RIGHT - CARR_LEFT) * u
    carriage.location = (home.x + x, home.y, home.z)
    carriage.keyframe_insert("location", frame=f)
if carriage.animation_data and carriage.animation_data.action:
    for fc in carriage.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Type bars : each fires once during the loop in a staggered order,
# i.e. type_bars[i] strikes at time = i/NBARS (very short impulse).
# Striking = rotation from -70 deg to 0 deg and back in ~0.10 s.
STRIKE_WINDOW = 0.10
for i, pv in enumerate(type_bars):
    t_strike = (i + 0.5) / NBARS - STRIKE_WINDOW * 0.5
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        if t < t_strike or t > t_strike + STRIKE_WINDOW:
            rot = math.radians(-70)
        else:
            phase = (t - t_strike) / STRIKE_WINDOW  # 0..1
            # tent function : 0 -> -70 -> 0 -> -70
            tri = 1.0 - abs(2.0 * phase - 1.0)  # 0..1..0
            rot = math.radians(-70) + math.radians(70) * tri
        pv.rotation_euler = (rot, 0, 0)
        pv.keyframe_insert("rotation_euler", frame=f)
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"TYPE_OK: {out_glb}", flush=True)
'''


def make_typewriter(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_type_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "TYPE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_typewriter(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
