"""Procedural rocket on launchpad (Blender headless).

Concrete pad + lattice service tower + rocket (body + nose cone + 4
fins + engine bell + emissive flame). Animation : flame scale flickers,
rocket subtly bobs.

CLI:
  python proc_rocket_launchpad.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "rocket.glb"

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

mat_body     = pbr_mat("body_white",  (0.92, 0.92, 0.92), 0.30, 0.35)
mat_red      = pbr_mat("accent_red",  (0.78, 0.10, 0.08), 0.20, 0.40)
mat_dark     = pbr_mat("dark_metal",  (0.15, 0.15, 0.18), 0.90, 0.40)
mat_concrete = pbr_mat("concrete",    (0.50, 0.50, 0.50), 0.00, 0.85)
mat_tower    = pbr_mat("tower_red",   (0.65, 0.20, 0.08), 0.30, 0.45)
mat_flame    = pbr_mat("flame",       (1.00, 0.50, 0.10), 0.00, 0.10,
                          emission=((1.00, 0.55, 0.15), 6.0))

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

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

# --- ground + concrete launchpad ----------------------------
_box("ground", 4.0, 4.0, 0.04, (0, 0, -0.04), pbr_mat("ground",(0.32,0.32,0.32),0,0.85))
PAD_R = 0.50
_cyl("launchpad", PAD_R, PAD_R, 0.06, 'Z', (0, 0, 0.03), mat_concrete)

# --- service tower (lattice red) -----------------------------
TOWER_X = 0.65
TOWER_H = 2.20
for sx in (-1, 1):
    for sy in (-1, 1):
        _box(f"tower_leg_{sx}_{sy}", 0.025, 0.025, TOWER_H,
               (TOWER_X + sx * 0.10, sy * 0.10, TOWER_H/2), mat_tower)
# horizontal cross-bars at multiple levels
for i in range(8):
    z = (i + 0.5) * TOWER_H / 8
    for sy in (-1, 1):
        _box(f"tower_hbar_x_{sy}_{i}", 0.20, 0.018, 0.018,
               (TOWER_X, sy * 0.10, z), mat_tower)
    for sx in (-1, 1):
        _box(f"tower_hbar_y_{sx}_{i}", 0.018, 0.20, 0.018,
               (TOWER_X + sx * 0.10, 0, z), mat_tower)

# --- root empty for rocket bob ------------------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
root = bpy.context.active_object
root.name = "rocket_root"

# --- rocket body ---------------------------------------------
BODY_R = 0.22
BODY_H = 1.50
ENGINE_BELL_H = 0.18
body = _cyl("body", BODY_R, BODY_R, BODY_H, 'Z', (0, 0, 0.06 + ENGINE_BELL_H + BODY_H/2),
              mat_body)
body.parent = root
body.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# red stripes on the body (2 narrow rings)
for sz in (0.30, 0.60):
    _cyl(f"stripe_{sz}", BODY_R * 1.02, BODY_R * 1.02, 0.05, 'Z',
           (0, 0, 0.06 + ENGINE_BELL_H + sz), mat_red).parent = root

# black "USA"-style band (a wider dark ring at the top)
_cyl("dark_band", BODY_R * 1.02, BODY_R * 1.02, 0.08, 'Z',
       (0, 0, 0.06 + ENGINE_BELL_H + BODY_H - 0.10), mat_dark).parent = root

# nose cone
nose = _cyl("nose", BODY_R, 0.01, 0.40, 'Z',
              (0, 0, 0.06 + ENGINE_BELL_H + BODY_H + 0.20), mat_body)
nose.parent = root
nose.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 4 fins around the base
for k in range(4):
    a = k * math.pi / 2
    fin_x = math.cos(a) * BODY_R * 0.9
    fin_y = math.sin(a) * BODY_R * 0.9
    bpy.ops.mesh.primitive_cube_add(size=1, location=(fin_x, fin_y, 0.06 + ENGINE_BELL_H + 0.12))
    f = bpy.context.active_object
    f.name = f"fin_{k}"
    f.scale = (0.14, 0.025, 0.24)
    bpy.ops.object.transform_apply(scale=True)
    f.rotation_euler = (0, 0, a)
    f.data.materials.append(mat_red)
    f.parent = root
    f.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# engine bell (flared cone at the bottom)
bell = _cyl("engine_bell", BODY_R * 0.85, BODY_R * 0.55, ENGINE_BELL_H, 'Z',
              (0, 0, 0.06 + ENGINE_BELL_H/2), mat_dark)
bell.parent = root
bell.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# flame (emissive cone pointing down from the bell)
flame = _cyl("flame", BODY_R * 0.55, 0.02, 0.40, 'Z',
               (0, 0, 0.06 - 0.20), mat_flame)
flame.parent = root
flame.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : rocket subtle bob + flame flicker ---------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    root.location = (0, 0, math.sin(2*math.pi*t) * 0.01)
    root.keyframe_insert("location", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    s = 0.6 + 0.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 6))
    flame.scale = (s, s, s)
    flame.keyframe_insert("scale", frame=f)
if flame.animation_data and flame.animation_data.action:
    for fc in flame.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"ROCKET_OK: {out_glb}", flush=True)
'''


def make_rocket(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_rocket_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "ROCKET_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_rocket(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
