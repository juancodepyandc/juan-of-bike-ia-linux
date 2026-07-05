"""Procedural retro arcade cabinet (Blender headless).

Tall wooden cabinet + emissive CRT screen + control panel + joystick +
4 colourful buttons + marquee + speaker grilles + coin slot. Animation
: the screen cycles between 4 emissive colours for a CRT-on-game look.

CLI:
  python proc_arcade_machine.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "arcade.glb"

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

mat_cabinet  = pbr_mat("cabinet",     (0.15, 0.05, 0.05), 0.10, 0.45)
mat_panel    = pbr_mat("panel_red",   (0.65, 0.08, 0.08), 0.10, 0.35)
mat_screen   = pbr_mat("screen",      (0.20, 0.20, 0.30), 0.00, 0.05,
                          emission=((0.30, 0.50, 1.00), 4.0))
mat_marquee  = pbr_mat("marquee_yel", (0.95, 0.85, 0.20), 0.10, 0.30,
                          emission=((1.00, 0.90, 0.30), 1.5))
mat_joystick = pbr_mat("joystick_red",(0.85, 0.15, 0.10), 0.10, 0.30)
mat_post     = pbr_mat("post_black",  (0.05, 0.05, 0.05), 0.30, 0.35)
mat_button_a = pbr_mat("button_red",  (0.92, 0.10, 0.10), 0.10, 0.30)
mat_button_b = pbr_mat("button_blue", (0.10, 0.30, 0.92), 0.10, 0.30)
mat_button_c = pbr_mat("button_green",(0.15, 0.78, 0.20), 0.10, 0.30)
mat_button_d = pbr_mat("button_yel",  (0.95, 0.85, 0.10), 0.10, 0.30)
mat_grille   = pbr_mat("grille",      (0.20, 0.20, 0.22), 0.30, 0.55)
mat_chrome   = pbr_mat("chrome",      (0.70, 0.72, 0.75), 1.00, 0.25)
mat_floor    = pbr_mat("floor",       (0.18, 0.18, 0.20), 0.00, 0.85)

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

def _cyl(name, R1, R2, depth, axis, location, mat, segments=16):
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

# --- floor -------------------------------------------------
_box("floor", 1.5, 1.5, 0.04, (0, 0, -0.04), mat_floor)

# --- main cabinet body (tall narrow box) ----------------
CAB_W = 0.50
CAB_D = 0.45
CAB_H = 1.60
_box("cabinet_body", CAB_W, CAB_D, CAB_H, (0, 0, CAB_H/2), mat_cabinet)

# --- side panels (slight red trim along the sides) ------
for sx in (-1, +1):
    _box(f"side_trim_{sx}", 0.015, CAB_D * 1.02, CAB_H * 0.95,
           (sx * (CAB_W/2 + 0.0075), 0, CAB_H/2), mat_panel)

# --- marquee (top yellow strip with "ARCADE" suggestion) ---
MARQUEE_Z = CAB_H + 0.12
_box("marquee", CAB_W * 1.05, CAB_D * 0.92, 0.15,
       (0, 0, MARQUEE_Z), mat_marquee)

# --- bezel (dark frame around the screen) ----------------
SCREEN_Z = CAB_H * 0.72
_box("bezel", CAB_W * 0.92, 0.04, 0.50,
       (0, -CAB_D/2 + 0.02, SCREEN_Z), mat_cabinet)

# --- screen (emissive cyan/blue) ------------------------
_box("screen", CAB_W * 0.78, 0.02, 0.38,
       (0, -CAB_D/2 + 0.02, SCREEN_Z), mat_screen)

# --- control panel (angled red surface below screen) ----
PANEL_Z = CAB_H * 0.45
_box("control_panel", CAB_W * 0.96, CAB_D * 0.80, 0.08,
       (0, -CAB_D/2 + CAB_D * 0.40, PANEL_Z), mat_panel)

# --- joystick + 4 buttons on the panel ------------------
JOY_X = -0.10
JOY_Y = -CAB_D/2 + CAB_D * 0.40
JOY_Z_BASE = PANEL_Z + 0.04
# joystick post
_cyl("joystick_post", 0.012, 0.012, 0.12, 'Z',
       (JOY_X, JOY_Y, JOY_Z_BASE + 0.06), mat_post)
# joystick ball
_sphere("joystick_ball", 0.030, (JOY_X, JOY_Y, JOY_Z_BASE + 0.13), mat_joystick)

# 4 buttons in a 2x2 grid
BTN_X0 = +0.08
BTN_MATS = [mat_button_a, mat_button_b, mat_button_c, mat_button_d]
for k in range(4):
    bx = BTN_X0 + (k % 2) * 0.07
    by = JOY_Y + ((k // 2) - 0.5) * 0.06
    _cyl(f"button_{k}", 0.022, 0.022, 0.015, 'Z',
           (bx, by, JOY_Z_BASE + 0.005), BTN_MATS[k])
    # button base ring (chrome)
    _cyl(f"button_ring_{k}", 0.028, 0.028, 0.005, 'Z',
           (bx, by, JOY_Z_BASE - 0.003), mat_chrome)

# --- speaker grilles (2 thin dark strips below screen)
for sx in (-1, +1):
    _box(f"speaker_{sx}", 0.04, 0.04, 0.06,
           (sx * 0.18, -CAB_D/2 + 0.02, SCREEN_Z - 0.30), mat_grille)

# --- coin slot + return on the front low ---------------
_box("coin_slot", 0.04, 0.04, 0.02,
       (0, -CAB_D/2 + 0.02, CAB_H * 0.15), mat_chrome)
_box("coin_return", 0.10, 0.04, 0.04,
       (0, -CAB_D/2 + 0.02, CAB_H * 0.07), mat_grille)

# --- animation : screen cycles emission colours -------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# cycle through 4 colours over the loop : blue, red, green, yellow
COLORS = [
    (0.30, 0.50, 1.00),
    (1.00, 0.30, 0.30),
    (0.30, 1.00, 0.40),
    (1.00, 0.95, 0.40),
]
bsdf = mat_screen.node_tree.nodes.get("Principled BSDF")
em_color = bsdf.inputs["Emission Color"]
em_str = bsdf.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    idx = int(t * len(COLORS)) % len(COLORS)
    em_color.default_value = (*COLORS[idx], 1.0)
    em_str.default_value = 3.0 + 1.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 12))
    bpy.context.scene.frame_set(f)
    em_color.keyframe_insert(data_path="default_value", frame=f)
    em_str.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"ARCADE_OK: {out_glb}", flush=True)
'''


def make_arcade(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_arcade_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "ARCADE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_arcade(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
