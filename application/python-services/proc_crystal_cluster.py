"""Procedural amethyst-crystal cluster (Blender headless).

Rocky base + 8 hexagonal-prism crystals pointing up at varied tilts,
translucent purple with strong emission. Animation : the whole cluster
slowly rotates and the emission strength pulses.

CLI:
  python proc_crystal_cluster.py <output_glb>
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

random.seed(19)

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "crystals.glb"

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

mat_rock     = pbr_mat("rock",        (0.30, 0.28, 0.26), 0.00, 0.85)
mat_crystal  = pbr_mat("amethyst",    (0.45, 0.20, 0.65), 0.00, 0.10,
                          emission=((0.65, 0.30, 0.95), 2.5), alpha=0.65)
mat_crystal_b = pbr_mat("amethyst_dk",(0.30, 0.15, 0.50), 0.00, 0.15,
                          emission=((0.45, 0.20, 0.75), 1.5), alpha=0.75)
mat_ground   = pbr_mat("ground",      (0.18, 0.18, 0.20), 0.00, 0.90)

def _hex_prism(name, R, H, mat):
    """Hexagonal prism : 6-sided base + 6-sided top + 6 side faces + cap."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    # 6 base verts at z=0, 6 top verts at z=H (slightly smaller for taper)
    base, top = [], []
    for k in range(6):
        a = k * math.pi / 3
        base.append(bm.verts.new((math.cos(a) * R, math.sin(a) * R, 0)))
        top.append(bm.verts.new((math.cos(a) * R * 0.75, math.sin(a) * R * 0.75, H * 0.85)))
    # peak (a single vertex above the top hex for the pyramidal cap)
    peak = bm.verts.new((0, 0, H))
    bm.verts.ensure_lookup_table()
    # base face (downward)
    bm.faces.new(list(reversed(base)))
    # 6 side faces (each is a quad)
    for k in range(6):
        nk = (k + 1) % 6
        bm.faces.new((base[k], base[nk], top[nk], top[k]))
    # 6 triangle faces for the pyramidal cap
    for k in range(6):
        nk = (k + 1) % 6
        bm.faces.new((top[k], top[nk], peak))
    bm.normal_update()
    bm.to_mesh(mesh); bm.free()
    obj.data.materials.append(mat)
    return obj

# --- ground ----------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.05))
g = bpy.context.active_object
g.name = "ground"
g.scale = (2.0, 2.0, 0.05)
bpy.ops.object.transform_apply(scale=True)
g.data.materials.append(mat_ground)

# --- rocky base ------------------------------------------------
mesh_rock = bpy.data.meshes.new("rock_base")
rock = bpy.data.objects.new("rock_base", mesh_rock)
bpy.context.collection.objects.link(rock)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=0.35)
# squash the sphere into a flat-ish boulder
for v in bm.verts:
    v.co.z *= 0.45
    if v.co.z < 0:
        v.co.z *= 0.2
    # jitter to make it look irregular
    v.co.x += (random.random() - 0.5) * 0.04
    v.co.y += (random.random() - 0.5) * 0.04
bm.to_mesh(mesh_rock); bm.free()
rock.data.materials.append(mat_rock)
rock.location = (0, 0, 0.08)

# --- root empty for whole-cluster rotation animation ----------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
root = bpy.context.active_object
root.name = "cluster_root"

# --- 8 hexagonal crystals at varied positions + tilts ---------
N_CRYSTALS = 8
crystals = []
for i in range(N_CRYSTALS):
    a = i * 2 * math.pi / N_CRYSTALS + random.uniform(-0.3, 0.3)
    radial = random.uniform(0.05, 0.22)
    cx = math.cos(a) * radial
    cy = math.sin(a) * radial
    R = random.uniform(0.04, 0.09)
    H = random.uniform(0.30, 0.60)
    mat = mat_crystal if i % 2 == 0 else mat_crystal_b
    c = _hex_prism(f"crystal_{i}", R, H, mat)
    c.location = (cx, cy, 0.10)
    # tilt outward : small random tilt so crystals don't all point straight up
    tilt = random.uniform(0.08, 0.22)
    tilt_dir = math.atan2(cy, cx)
    c.rotation_euler = (tilt * math.sin(tilt_dir), -tilt * math.cos(tilt_dir), 0)
    c.parent = root
    c.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    crystals.append(c)

# --- animation : whole cluster rotates slowly + emission pulses -
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    root.rotation_euler = (0, 0, 2 * math.pi * t * 0.3)  # slow turntable
    root.keyframe_insert("rotation_euler", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Emission pulse : animate the material's Emission Strength via the
# Principled BSDF node input.
# Blender API : drive node.input.default_value via keyframes.
for mat in (mat_crystal, mat_crystal_b):
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if not bsdf or "Emission Strength" not in bsdf.inputs:
        continue
    em_input = bsdf.inputs["Emission Strength"]
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        # pulse between 1.0 and 4.0 (slightly out of phase between the 2 mats)
        phase = 0.0 if mat is mat_crystal else 0.3
        em_input.default_value = 1.0 + 3.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 2 + phase))
        bpy.context.scene.frame_set(f)
        em_input.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"CRYSTAL_OK: {out_glb}", flush=True)
'''


def make_crystals(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_crystal_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "CRYSTAL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_crystals(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
