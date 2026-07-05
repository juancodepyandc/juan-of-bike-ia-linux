"""Procedural fantasy sword (Blender headless).

Floating sword : pommel with glowing red gem + leather-wrapped grip +
brass cross-guard + tapered double-edged blade with central fuller +
display stand below. Animation : sword turntables slowly + gem pulses.

CLI:
  python proc_sword.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "sword.glb"

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

mat_blade   = pbr_mat("blade_steel",  (0.78, 0.80, 0.82), 1.00, 0.10)
mat_brass   = pbr_mat("brass",        (0.86, 0.62, 0.20), 1.00, 0.28)
mat_grip    = pbr_mat("leather_grip", (0.30, 0.18, 0.08), 0.00, 0.55)
mat_gem     = pbr_mat("gem_ruby",     (0.85, 0.10, 0.10), 0.30, 0.15,
                        emission=((1.00, 0.30, 0.20), 4.0))
mat_stand   = pbr_mat("stand_wood",   (0.25, 0.15, 0.07), 0.00, 0.60)
mat_floor   = pbr_mat("floor_dark",   (0.15, 0.15, 0.17), 0.00, 0.85)

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

# --- floor ---------------------------------------------------
_box("floor", 2.0, 2.0, 0.04, (0, 0, -0.04), mat_floor)

# --- root empty (drives whole-sword rotation) ---------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0.85))
root = bpy.context.active_object
root.name = "sword_root"

# --- BLADE (long tapered shape via bmesh) -------------------
# blade orientation : along the sword's local +Z, tapering to a point.
# We build it as a 2D outline extruded to give a flat blade with fuller.
BLADE_LEN = 1.20
BLADE_W   = 0.05      # half-width at the base
BLADE_T   = 0.012     # half-thickness
mesh_blade = bpy.data.meshes.new("blade")
blade = bpy.data.objects.new("blade", mesh_blade)
bpy.context.collection.objects.link(blade)
bm = bmesh.new()
# 5 sections along the blade: base, body 1, body 2, body 3, tip
sections = [
    (0,             BLADE_W * 0.85, BLADE_T),
    (BLADE_LEN*0.20, BLADE_W,        BLADE_T),
    (BLADE_LEN*0.55, BLADE_W * 0.95, BLADE_T * 0.95),
    (BLADE_LEN*0.85, BLADE_W * 0.70, BLADE_T * 0.85),
    (BLADE_LEN,     0.005,           0.005),  # tip
]
rings = []
for (z, w, t) in sections:
    # 6 verts per ring: top, top-front-edge, top-front-mid, bottom-front-mid, bottom-front-edge, bottom
    # Actually use 4 verts per ring : front-edge, back-edge, mid-top, mid-bottom for the diamond cross-section
    front = bm.verts.new(( w, 0, z))
    back  = bm.verts.new((-w, 0, z))
    up    = bm.verts.new(( 0,  t, z))
    down  = bm.verts.new(( 0, -t, z))
    rings.append([front, up, back, down])
bm.verts.ensure_lookup_table()
# Stitch consecutive rings (4 quads between each pair)
for i in range(len(rings) - 1):
    r0, r1 = rings[i], rings[i+1]
    for k in range(4):
        nk = (k + 1) % 4
        bm.faces.new((r0[k], r0[nk], r1[nk], r1[k]))
# Cap the base (the first ring closes to the cross-guard)
bm.faces.new(rings[0])
bm.normal_update()
bm.to_mesh(mesh_blade); bm.free()
blade.data.materials.append(mat_blade)
blade.parent = root
blade.matrix_parent_inverse = mathutils.Matrix.Identity(4)
blade.location = (0, 0, 0)   # base at root origin, tip up

# --- CROSS-GUARD (brass cross-bar) --------------------------
guard = _box("guard", 0.16, 0.04, 0.025, (0, 0, -0.012), mat_brass)
guard.parent = root
guard.matrix_parent_inverse = mathutils.Matrix.Identity(4)
guard.location = (0, 0, -0.012)
# add 2 small decorative tips on the guard ends
for sx in (-1, 1):
    tip = _cyl(f"guard_tip_{sx}", 0.025, 0.015, 0.03, 'X',
                 (sx * 0.085, 0, -0.012), mat_brass)
    tip.parent = root
    tip.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- GRIP (leather-wrapped cylinder) ------------------------
GRIP_LEN = 0.20
grip = _cyl("grip", 0.018, 0.022, GRIP_LEN, 'Z', (0, 0, -0.025 - GRIP_LEN/2), mat_grip)
grip.parent = root
grip.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- POMMEL (brass sphere) + GEM (glowing red sphere inside) ---
POMMEL_R = 0.040
mesh_pommel = bpy.data.meshes.new("pommel")
pommel = bpy.data.objects.new("pommel", mesh_pommel)
bpy.context.collection.objects.link(pommel)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=18, v_segments=12, radius=POMMEL_R)
bm.to_mesh(mesh_pommel); bm.free()
pommel.data.materials.append(mat_brass)
pommel.parent = root
pommel.matrix_parent_inverse = mathutils.Matrix.Identity(4)
pommel.location = (0, 0, -0.025 - GRIP_LEN - POMMEL_R * 0.7)

# gem (smaller sphere protruding from the pommel)
GEM_R = 0.018
mesh_gem = bpy.data.meshes.new("gem")
gem = bpy.data.objects.new("gem", mesh_gem)
bpy.context.collection.objects.link(gem)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=GEM_R)
bm.to_mesh(mesh_gem); bm.free()
gem.data.materials.append(mat_gem)
gem.parent = root
gem.matrix_parent_inverse = mathutils.Matrix.Identity(4)
gem.location = (0, 0, -0.025 - GRIP_LEN - POMMEL_R * 0.7 - POMMEL_R * 0.85)

# --- display stand below ------------------------------------
STAND_Z = -0.025 - GRIP_LEN - POMMEL_R * 1.8
stand_loc_z_world = 0.85 + STAND_Z - 0.05
# stand_base is in world space, NOT parented to root, so it stays still
_box("stand_base", 0.30, 0.20, 0.04, (0, 0, stand_loc_z_world), mat_stand)
_cyl("stand_post", 0.025, 0.025, 0.10, 'Z',
       (0, 0, stand_loc_z_world + 0.05 + 0.05), mat_stand)
# the sword "floats" just above the stand post

# --- animation : turntable + gem emission pulse ------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    root.rotation_euler = (0, 0, 2 * math.pi * t)
    root.keyframe_insert("rotation_euler", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# gem pulse
bsdf = mat_gem.node_tree.nodes.get("Principled BSDF")
em = bsdf.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em.default_value = 2.0 + 3.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 2))
    bpy.context.scene.frame_set(f)
    em.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SWORD_OK: {out_glb}", flush=True)
'''


def make_sword(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_sword_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SWORD_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_sword(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
