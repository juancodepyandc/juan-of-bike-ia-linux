"""Procedural lava lamp (Blender headless).

Wood base + glass cylinder (translucent) + 5 emissive orange lava
blobs that bob up and down inside the cylinder + bright bulb at the
bottom + brass cap on top. Animation : each blob has its own Z
oscillation period + small scale wobble.

CLI:
  python proc_lava_lamp.py <output_glb>
"""
from __future__ import annotations
import argparse, json, os, random, shutil, subprocess, sys, tempfile, time
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
import bpy, bmesh, math, mathutils, random, sys

random.seed(23)

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "lavalamp.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough, emission=None, alpha=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if emission is not None and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission[0], 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission[1]
        if alpha is not None and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
            m.blend_method = 'BLEND'
    return m

mat_wood    = pbr_mat("base_wood",  (0.35, 0.22, 0.10), 0.00, 0.65)
mat_glass   = pbr_mat("glass",      (0.85, 0.88, 0.95), 0.00, 0.05, alpha=0.20)
mat_lava    = pbr_mat("lava",       (0.95, 0.30, 0.10), 0.10, 0.20,
                        emission=((1.00, 0.50, 0.10), 3.0))
mat_liquid  = pbr_mat("liquid_amber",(0.85, 0.50, 0.20), 0.05, 0.10, alpha=0.40)
mat_brass   = pbr_mat("brass_cap",  (0.86, 0.62, 0.20), 1.00, 0.28)
mat_bulb    = pbr_mat("bulb_glow",  (1.00, 0.80, 0.40), 0.00, 0.10,
                        emission=((1.00, 0.85, 0.45), 5.0))
mat_floor   = pbr_mat("floor",      (0.18, 0.18, 0.20), 0.00, 0.85)

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

def _sphere(name, R, location, mat, u=20, v=14):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- floor ----------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
fl = bpy.context.active_object
fl.name = "floor"
fl.scale = (1.5, 1.5, 0.04)
bpy.ops.object.transform_apply(scale=True)
fl.data.materials.append(mat_floor)

# --- wood base ------------------------------------------------
BASE_R_BOT = 0.18
BASE_R_TOP = 0.12
BASE_H     = 0.18
_cyl("base", BASE_R_BOT, BASE_R_TOP, BASE_H, 'Z', (0, 0, BASE_H/2), mat_wood)

# --- emissive bulb at the bottom of the glass tube -----------
_sphere("bulb", 0.05, (0, 0, BASE_H + 0.06), mat_bulb, u=18, v=10)

# --- glass cylinder + amber liquid inside ---------------------
GLASS_R   = 0.13
GLASS_H   = 0.85
GLASS_Z0  = BASE_H + 0.02
GLASS_Z1  = GLASS_Z0 + GLASS_H
glass = _cyl("glass_tube", GLASS_R, GLASS_R * 0.95, GLASS_H, 'Z',
                (0, 0, (GLASS_Z0 + GLASS_Z1)/2), mat_glass)

# amber liquid (slightly smaller cylinder, translucent)
liquid = _cyl("liquid", GLASS_R * 0.95, GLASS_R * 0.90, GLASS_H * 0.95, 'Z',
                (0, 0, (GLASS_Z0 + GLASS_Z1)/2), mat_liquid)

# --- brass cap on top ----------------------------------------
_cyl("cap", GLASS_R * 1.10, GLASS_R * 0.95, 0.05, 'Z',
       (0, 0, GLASS_Z1 + 0.025), mat_brass)
_cyl("cap_finial", 0.025, 0.020, 0.04, 'Z',
       (0, 0, GLASS_Z1 + 0.075), mat_brass)

# --- 5 lava blobs (UV spheres scattered in Z) ----------------
N_BLOBS = 5
blob_data = []   # (obj, start_z, period_s)
for i in range(N_BLOBS):
    R = random.uniform(0.025, 0.055)
    z0 = GLASS_Z0 + 0.08 + random.uniform(0, 1) * (GLASS_H - 0.16)
    x = random.uniform(-0.04, 0.04)
    y = random.uniform(-0.04, 0.04)
    period = random.uniform(2.5, 4.5)
    b = _sphere(f"blob_{i}", R, (x, y, z0), mat_lava, u=14, v=8)
    blob_data.append((b, z0, period, x, y))

# --- animation -----------------------------------------------
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
# Each blob translates +/- 0.25 in Z over its own period, sin-wave
for (obj, z0, period, x, y) in blob_data:
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        # z range : keep blobs inside the glass tube
        z = z0 + math.sin(2*math.pi*t * (DURATION/period)) * 0.20
        z = max(GLASS_Z0 + 0.07, min(GLASS_Z1 - 0.07, z))
        obj.location = (x, y, z)
        # scale wobble : 0.85 .. 1.15
        s = 0.85 + 0.30 * (0.5 + 0.5 * math.sin(2*math.pi*t * (DURATION/period) * 1.7))
        obj.scale = (s, s, s)
        obj.keyframe_insert("location", frame=f)
        obj.keyframe_insert("scale", frame=f)
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"LAVALAMP_OK: {out_glb}", flush=True)
'''


def make_lavalamp(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_lava_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "LAVALAMP_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_lavalamp(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
