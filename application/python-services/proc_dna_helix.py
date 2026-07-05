"""Procedural DNA double helix (Blender headless).

Two phosphate-sugar backbones (helically arranged spheres) + 16 base
pairs joining the strands (2 colored half-cylinders per pair: A=red /
T=yellow / G=blue / C=green). The whole helix is parented to a single
empty so we can rotate it slowly around Z. Each base material flickers
its emission strength to suggest molecular vibration.

CLI:
  python proc_dna_helix.py <output_glb>
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
import bpy, bmesh, math, mathutils, sys, random

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "dna.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0xDA1A)

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

mat_floor   = pbr_mat("floor", (0.08, 0.08, 0.10), 0.00, 0.85)
# 2 backbone shades (slightly distinct so the 2 strands read separately)
mat_bb_a    = pbr_mat("bb_strandA", (0.85, 0.45, 0.20), 0.50, 0.30,
                          emission=((1.00, 0.55, 0.25), 0.8))
mat_bb_b    = pbr_mat("bb_strandB", (0.20, 0.55, 0.85), 0.50, 0.30,
                          emission=((0.25, 0.60, 1.00), 0.8))
# 4 base colours, each with a small emission so they pop
mat_A = pbr_mat("base_A", (0.95, 0.20, 0.20), 0.10, 0.30,
                   emission=((1.00, 0.30, 0.25), 1.5))
mat_T = pbr_mat("base_T", (1.00, 0.90, 0.20), 0.10, 0.30,
                   emission=((1.00, 0.92, 0.30), 1.5))
mat_G = pbr_mat("base_G", (0.20, 0.40, 0.95), 0.10, 0.30,
                   emission=((0.30, 0.50, 1.00), 1.5))
mat_C = pbr_mat("base_C", (0.20, 0.85, 0.30), 0.10, 0.30,
                   emission=((0.30, 1.00, 0.40), 1.5))

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

def _cyl(name, R1, R2, depth, location, mat, segments=16, dir=None):
    """Cylinder centered at `location` oriented along `dir` (default +Z)."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                            radius1=R1, radius2=R2, depth=depth)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    if dir is not None:
        d = mathutils.Vector(dir).normalized()
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d)
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

# --- floor + pedestal ----------------------------
_box("floor", 2.4, 2.4, 0.04, (0, 0, -0.04), mat_floor)
# small dark pedestal
_cyl("pedestal", 0.20, 0.18, 0.06, (0, 0, 0.03), mat_bb_a, segments=24)

# --- DNA helix root -----------------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0.10))
helix = bpy.context.active_object
helix.name = "helix_pivot"

# Helix parameters
HELIX_R       = 0.18    # radius of each strand
HELIX_H       = 1.60    # total height
N_PAIRS       = 16      # number of base pairs (rungs)
TURNS         = 2.0     # how many full revolutions over HELIX_H
PHASE_OFFSET  = math.pi  # the two strands are diametrically opposite

# Base sequence chosen at random — each pair is one of (A,T), (T,A), (G,C), (C,G)
PAIR_TYPES = [("A","T"), ("T","A"), ("G","C"), ("C","G")]
BASE_MATS = {"A": mat_A, "T": mat_T, "G": mat_G, "C": mat_C}
base_mats_used = set()

def pos_on_strand(t, phase):
    """t in [0..1] along the helix. Returns (x,y,z) on the strand."""
    a = 2*math.pi * TURNS * t + phase
    x = HELIX_R * math.cos(a)
    y = HELIX_R * math.sin(a)
    z = t * HELIX_H
    return (x, y, z)

# --- backbones : a sphere at each base position + thin cylinders linking
# consecutive spheres ----------------------------
# Use N = N_PAIRS spheres per strand (one per rung), plus a few in-between
# spheres to make the backbone smoother.
BB_STEPS = N_PAIRS * 3  # 3 backbone spheres per rung
prev_a = None; prev_b = None
for k in range(BB_STEPS + 1):
    t = k / BB_STEPS
    pa = pos_on_strand(t, 0.0)
    pb = pos_on_strand(t, PHASE_OFFSET)
    sa = _sphere(f"bb_a_{k}", 0.022, pa, mat_bb_a)
    sb = _sphere(f"bb_b_{k}", 0.022, pb, mat_bb_b)
    sa.parent = helix; sa.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    sb.parent = helix; sb.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    if prev_a is not None:
        # cylinder from prev_a to pa
        for (start, end, mat, label) in (
            (prev_a, pa, mat_bb_a, f"bb_a_link_{k}"),
            (prev_b, pb, mat_bb_b, f"bb_b_link_{k}"),
        ):
            d = (end[0]-start[0], end[1]-start[1], end[2]-start[2])
            L = math.sqrt(d[0]**2 + d[1]**2 + d[2]**2)
            mid = ((end[0]+start[0])/2, (end[1]+start[1])/2, (end[2]+start[2])/2)
            cyl = _cyl(label, 0.012, 0.012, L, mid, mat, segments=10, dir=d)
            cyl.parent = helix; cyl.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    prev_a = pa; prev_b = pb

# --- base pairs : 16 rungs ---------------------
# Each rung is a 2-segment cylinder coloured by its 2 nucleotides + a
# small connecting sphere at the centre.
for i in range(N_PAIRS):
    t = (i + 0.5) / N_PAIRS  # center of each segment
    pa = pos_on_strand(t, 0.0)
    pb = pos_on_strand(t, PHASE_OFFSET)
    pair = PAIR_TYPES[i % 4]
    nucleotide_a, nucleotide_b = pair
    base_mats_used.add(nucleotide_a); base_mats_used.add(nucleotide_b)
    mat_a_color = BASE_MATS[nucleotide_a]
    mat_b_color = BASE_MATS[nucleotide_b]
    # midpoint between the 2 strand positions
    mp = ((pa[0]+pb[0])/2, (pa[1]+pb[1])/2, (pa[2]+pb[2])/2)
    # cyl from pa to mp coloured A
    for (start, end, mat, label) in (
        (pa, mp, mat_a_color, f"base_{i}_a"),
        (mp, pb, mat_b_color, f"base_{i}_b"),
    ):
        d = (end[0]-start[0], end[1]-start[1], end[2]-start[2])
        L = math.sqrt(d[0]**2 + d[1]**2 + d[2]**2)
        mid = ((end[0]+start[0])/2, (end[1]+start[1])/2, (end[2]+start[2])/2)
        cyl = _cyl(label, 0.014, 0.014, L, mid, mat, segments=12, dir=d)
        cyl.parent = helix; cyl.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # central H-bond marker (a small lighter sphere at mp)
    hb = _sphere(f"hbond_{i}", 0.010, mp, mat_bb_a)
    hb.parent = helix; hb.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- top + bottom caps (small chrome rings hinting at the helix ends) ---
for z_end, label in ((0.0, "cap_bot"), (HELIX_H, "cap_top")):
    cap = _cyl(label, HELIX_R + 0.025, HELIX_R + 0.025, 0.006,
                 (0, 0, z_end), mat_bb_a, segments=24)
    cap.parent = helix; cap.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation -----------------------------------
FPS = 30
DURATION = 8.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# helix rotates slowly around Z (0.5 turn / loop)
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    helix.rotation_euler = (0, 0, math.pi * t)
    helix.keyframe_insert("rotation_euler", frame=f)
if helix.animation_data and helix.animation_data.action:
    for fc in helix.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Each base material pulses its emission strength (4 materials)
for idx, key in enumerate(["A", "T", "G", "C"]):
    if key not in base_mats_used: continue
    m = BASE_MATS[key]
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    em = bsdf.inputs["Emission Strength"]
    phase = idx * math.pi / 2
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        val = 1.2 + 0.7 * (0.5 + 0.5 * math.sin(2*math.pi*t * 2.0 + phase))
        em.default_value = val
        bpy.context.scene.frame_set(f)
        em.keyframe_insert(data_path="default_value", frame=f)

# Backbones pulse softly
for m in (mat_bb_a, mat_bb_b):
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    em = bsdf.inputs["Emission Strength"]
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        em.default_value = 0.6 + 0.3 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.0))
        bpy.context.scene.frame_set(f)
        em.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"DNA_OK: {out_glb}", flush=True)
'''


def make_dna(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_dna_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "DNA_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_dna(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
