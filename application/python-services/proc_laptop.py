"""Procedural open laptop (Blender headless).

Aluminum chassis with hinged lid open at ~110°. Lid contains an
emissive LCD that cycles through 5 wallpaper colours. Base contains a
64-key keyboard (4 rows of 14 keys + 1 row of 8 + spacebar approximation),
trackpad, ports on the side, and a small emissive logo on the back of
the lid that pulses. Animation : LCD cycles + logo pulses + 5 random
keys flash subtly (typing illusion).

CLI:
  python proc_laptop.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "laptop.glb"

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

mat_floor    = pbr_mat("floor",     (0.40, 0.35, 0.30), 0.00, 0.85)
mat_alum     = pbr_mat("alum",      (0.70, 0.72, 0.75), 0.85, 0.30)
mat_alum_d   = pbr_mat("alum_dk",   (0.18, 0.18, 0.20), 0.60, 0.40)
mat_chrome   = pbr_mat("chrome",    (0.82, 0.84, 0.87), 1.00, 0.18)
mat_key      = pbr_mat("key",       (0.06, 0.06, 0.07), 0.10, 0.45)
mat_key_legend = pbr_mat("key_legend",(0.78, 0.78, 0.80), 0.00, 0.45)
mat_screen   = pbr_mat("screen",    (0.05, 0.05, 0.08), 0.00, 0.05,
                          emission=((0.30, 0.55, 1.00), 4.0))
mat_bezel    = pbr_mat("bezel",     (0.05, 0.05, 0.06), 0.10, 0.40)
mat_logo     = pbr_mat("logo",      (0.92, 0.92, 0.95), 0.00, 0.30,
                          emission=((1.00, 1.00, 1.00), 3.0))
mat_trackpad = pbr_mat("trackpad",  (0.30, 0.30, 0.33), 0.50, 0.25)
mat_port     = pbr_mat("port",      (0.04, 0.04, 0.05), 0.20, 0.50)
# 5 keys flashing material (single shared, animated)
mat_key_lit  = pbr_mat("key_lit",   (0.20, 0.20, 0.22), 0.10, 0.35,
                          emission=((0.30, 1.00, 0.50), 0.0))

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

# Conventions : laptop sits flat on the desk with the spacebar end facing -Y.
# Up = +Z. Lid hinges at the back (+Y end) and tilts back at 110° open.

# --- desk ----------------------
_box("floor", 1.0, 0.8, 0.04, (0, 0, -0.04), mat_floor)

# Base dims (aluminum chassis)
B_W = 0.34
B_D = 0.24
B_H = 0.014
B_Z = B_H/2 + 0.001
_box("base", B_W, B_D, B_H, (0, 0, B_Z), mat_alum)
# rubber feet (4)
for sx in (-1, +1):
    for sy in (-1, +1):
        _cyl(f"foot_{sx}_{sy}", 0.008, 0.008, 0.003, 'Z',
               (sx * (B_W/2 - 0.025), sy * (B_D/2 - 0.025), 0.0015),
               mat_alum_d)

# keyboard recess (a darker thin slab inset into the base)
KEY_RECESS_W = B_W - 0.04
KEY_RECESS_D = B_D * 0.55
KEY_RECESS_Y = -B_D * 0.10  # toward the -Y (operator) side
_box("kbd_recess", KEY_RECESS_W, KEY_RECESS_D, 0.004,
       (0, KEY_RECESS_Y, B_Z + B_H/2 + 0.002), mat_alum_d)

# 64 keys : 4 rows x 14 + 1 row x 8 (function keys) approximated
KEY_W = 0.018
KEY_T = 0.005
ROW_DEFS = [
    # (n_keys, y_offset_from_recess_center, z_offset_from_recess_top)
    (14, +KEY_RECESS_D * 0.35, 0),  # function row
    (14, +KEY_RECESS_D * 0.18, 0),
    (14, +KEY_RECESS_D * 0.02, 0),
    (13, -KEY_RECESS_D * 0.14, 0),
    ( 8, -KEY_RECESS_D * 0.30, 0),  # space-bar row (1 long key + 7 modifiers)
]
flashing_keys = []   # we'll pick 5 keys to animate
total_index = 0
for row_idx, (n, y_off, z_off) in enumerate(ROW_DEFS):
    for k in range(n):
        # space out keys evenly along X within the recess
        spacing = (KEY_RECESS_W - 0.02) / max(n - 1, 1)
        kx = -KEY_RECESS_W/2 + 0.01 + k * spacing
        ky = KEY_RECESS_Y + y_off
        kz = B_Z + B_H/2 + 0.005
        # space-bar row : key 3 is the spacebar (longer)
        if row_idx == 4 and k == 3:
            key_w = KEY_W * 4
        else:
            key_w = KEY_W
        # pick 5 keys to flash : index 7, 23, 38, 51, 60 (spread across rows)
        is_flash = total_index in (7, 23, 38, 51, 60)
        mat_kb = mat_key_lit if is_flash else mat_key
        kb = _box(f"key_{row_idx}_{k}", key_w, KEY_W, KEY_T,
                    (kx, ky, kz + KEY_T/2), mat_kb)
        # tiny lighter legend dot in the middle of the key
        _box(f"key_legend_{row_idx}_{k}", key_w * 0.4, KEY_W * 0.4, 0.001,
               (kx, ky, kz + KEY_T + 0.0005), mat_key_legend)
        if is_flash:
            flashing_keys.append(kb)
        total_index += 1

# trackpad (a smooth grey rectangle at the front of the base)
TP_Y = -B_D * 0.38
_box("trackpad", KEY_RECESS_W * 0.55, 0.05, 0.001,
       (0, TP_Y, B_Z + B_H/2 + 0.001), mat_trackpad)
# small thin notch above the trackpad (the speaker/mic grille)
for sx in (-1, +1):
    _box(f"speaker_grille_{sx}", 0.08, 0.005, 0.001,
           (sx * (KEY_RECESS_W * 0.40), KEY_RECESS_Y + KEY_RECESS_D * 0.42 - 0.012,
            B_Z + B_H/2 + 0.001), mat_alum_d)

# ports on the side (3 small dark rectangles on +X side of the base)
for k in range(3):
    pz = B_Z
    py = -B_D * 0.30 + k * 0.07
    _box(f"port_{k}", 0.001, 0.008, 0.006,
           (B_W/2 + 0.0005, py, pz), mat_port)
# 1 power port on the -X side
_box("power_port", 0.001, 0.014, 0.005,
       (-B_W/2 - 0.0005, B_D * 0.10, B_Z), mat_port)

# --- hinge + lid ---
# Hinge axis runs along X at the back edge of the base (+Y end).
HINGE_Y = B_D/2 - 0.005
HINGE_Z = B_Z + B_H/2 + 0.001
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(0, HINGE_Y, HINGE_Z))
lid_pivot = bpy.context.active_object
lid_pivot.name = "lid_pivot"
# lid tilts back ~110° (so +Z toward camera becomes ~+Y away)
lid_pivot.rotation_euler = (math.radians(110), 0, 0)

# Lid slab (the screen panel). It extends from y=0 (the hinge) to y=+B_D
# in the unrotated frame, which after rotation becomes mostly +Z (raised
# screen). The lid is the same width as the base, slightly thinner.
LID_W = B_W
LID_D = B_D * 0.96
LID_T = 0.008
lid_slab = _box("lid_back", LID_W, LID_T, LID_D,
                  (0, -LID_T/2, LID_D/2), mat_alum)
lid_slab.parent = lid_pivot
lid_slab.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# Emissive logo on the BACK of the lid (visible when lid is open)
logo = _cyl("logo", 0.022, 0.022, 0.0015, 'Y',
              (0, -LID_T - 0.0005, LID_D * 0.5), mat_logo, segments=24)
logo.parent = lid_pivot
logo.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# Bezel frame on the front of the lid (toward the operator after opening)
BEZEL_T = 0.012
_box("bezel_top",    LID_W - 0.01, 0.002, BEZEL_T,
       (0, 0.002, LID_D - BEZEL_T/2), mat_bezel)
_box("bezel_bot",    LID_W - 0.01, 0.002, BEZEL_T,
       (0, 0.002, BEZEL_T/2), mat_bezel)
for sx in (-1, +1):
    _box(f"bezel_side_{sx}", BEZEL_T, 0.002, LID_D - 0.01,
           (sx * (LID_W/2 - BEZEL_T/2), 0.002, LID_D/2), mat_bezel)
# attach the 4 bezel pieces to the lid pivot
for o in (
    bpy.data.objects.get("bezel_top"),
    bpy.data.objects.get("bezel_bot"),
    bpy.data.objects.get("bezel_side_-1"),
    bpy.data.objects.get("bezel_side_1"),
):
    if o:
        o.parent = lid_pivot
        o.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# Screen LCD (emissive panel inset within bezel)
SCREEN_W = LID_W - 0.025
SCREEN_D = LID_D - 0.025 - BEZEL_T
SCREEN_Z = (LID_D + BEZEL_T - (LID_D - BEZEL_T)) / 2  # center
screen = _box("screen", SCREEN_W, 0.001, SCREEN_D,
                (0, 0.0015, LID_D/2), mat_screen)
screen.parent = lid_pivot
screen.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# small camera notch in the top bezel
cam = _cyl("webcam", 0.003, 0.003, 0.001, 'Y',
             (0, 0.002, LID_D - BEZEL_T/2), mat_port, segments=10)
cam.parent = lid_pivot
cam.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation ---------------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# LCD cycles 5 wallpaper colours
bsdf_scr = mat_screen.node_tree.nodes.get("Principled BSDF")
em_col = bsdf_scr.inputs["Emission Color"]
em_str = bsdf_scr.inputs["Emission Strength"]
LCD_COLORS = [
    (0.30, 0.55, 1.00),  # blue desktop
    (0.30, 1.00, 0.55),  # green
    (1.00, 0.85, 0.30),  # warm yellow
    (0.85, 0.30, 0.55),  # magenta
    (0.55, 0.30, 1.00),  # violet
]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    idx = int(t * len(LCD_COLORS)) % len(LCD_COLORS)
    em_col.default_value = (*LCD_COLORS[idx], 1.0)
    em_str.default_value = 3.5 + 1.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 2.0))
    bpy.context.scene.frame_set(f)
    em_col.keyframe_insert(data_path="default_value", frame=f)
    em_str.keyframe_insert(data_path="default_value", frame=f)

# Logo on the back pulses
bsdf_lg = mat_logo.node_tree.nodes.get("Principled BSDF")
em_lg = bsdf_lg.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_lg.default_value = 2.0 + 1.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.0))
    bpy.context.scene.frame_set(f)
    em_lg.keyframe_insert(data_path="default_value", frame=f)

# 5 flashing keys : shared emission material, brief pulses at random-ish times
bsdf_kl = mat_key_lit.node_tree.nodes.get("Principled BSDF")
em_kl = bsdf_kl.inputs["Emission Strength"]
# Build a series of "keystroke" pulses spread across the loop
KEYSTROKE_TIMES = [0.10, 0.20, 0.32, 0.45, 0.58, 0.68, 0.80, 0.90]
def keystroke_strength(t):
    """Sum of triangle pulses at each keystroke time, width 0.05."""
    s = 0.0
    for kt in KEYSTROKE_TIMES:
        if abs(t - kt) < 0.04:
            phase = (t - kt) / 0.04
            s += 1.5 * (1.0 - abs(phase))
    return s
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    em_kl.default_value = max(0.0, keystroke_strength(t))
    em_kl.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"LAP_OK: {out_glb}", flush=True)
'''


def make_laptop(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_laptop_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "LAP_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_laptop(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
