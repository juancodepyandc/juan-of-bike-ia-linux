"""Procedural black hole with accretion disc (Blender headless).

Spherical event horizon (deep black non-emissive) + a glowing accretion
disc (3 concentric rings of orange→white emission spiralling around) +
gravitational lensing halo + 2 polar relativistic jets shooting up/down
+ distant starfield background. Animation : the disc rotates fast, the
halo pulses, and the polar jets flicker with bright pulses.

CLI:
  python proc_black_hole.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "blackhole.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

rng = random.Random(0x8146)

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

mat_space   = pbr_mat("space",     (0.02, 0.02, 0.04), 0.00, 0.95)
mat_horizon = pbr_mat("horizon",   (0.00, 0.00, 0.00), 0.00, 0.95)
mat_disc_a  = pbr_mat("disc_a",    (1.00, 0.55, 0.18), 0.00, 0.10,
                          emission=((1.00, 0.55, 0.18), 8.0))
mat_disc_b  = pbr_mat("disc_b",    (1.00, 0.85, 0.30), 0.00, 0.10,
                          emission=((1.00, 0.85, 0.30), 12.0))
mat_disc_c  = pbr_mat("disc_c",    (1.00, 0.30, 0.20), 0.00, 0.10,
                          emission=((1.00, 0.30, 0.20), 6.0))
mat_halo    = pbr_mat("halo",      (1.00, 0.85, 0.55), 0.00, 0.10,
                          alpha=0.18,
                          emission=((1.00, 0.85, 0.55), 4.0))
mat_jet     = pbr_mat("jet",       (0.55, 0.78, 1.00), 0.00, 0.10,
                          alpha=0.55,
                          emission=((0.45, 0.65, 1.00), 12.0))
mat_jet_tip = pbr_mat("jet_tip",   (1.00, 0.95, 0.85), 0.00, 0.10,
                          emission=((1.00, 0.95, 0.85), 18.0))
mat_star    = pbr_mat("star",      (1.00, 0.95, 0.85), 0.00, 0.10,
                          emission=((1.00, 0.95, 0.85), 6.0))

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

def _sphere(name, R, location, mat, u=24, v=16, scale=(1,1,1)):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    if scale != (1,1,1):
        bmesh.ops.scale(bm, vec=mathutils.Vector(scale), verts=bm.verts)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

def _cyl(name, R1, R2, depth, axis, location, mat, segments=24, rot=None):
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

def _torus(name, R_major, R_minor, location, mat, ms=48, mn=6):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    verts = []
    for i in range(ms):
        ai = 2 * math.pi * i / ms
        ring = []
        for j in range(mn):
            aj = 2 * math.pi * j / mn
            x = (R_major + R_minor * math.cos(aj)) * math.cos(ai)
            y = (R_major + R_minor * math.cos(aj)) * math.sin(ai)
            z = R_minor * math.sin(aj)
            ring.append(bm.verts.new((x, y, z)))
        verts.append(ring)
    bm.verts.ensure_lookup_table()
    for i in range(ms):
        for j in range(mn):
            i2 = (i + 1) % ms
            j2 = (j + 1) % mn
            bm.faces.new([verts[i][j], verts[i2][j], verts[i2][j2], verts[i][j2]])
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- space background ---
_box("space_plate", 6.0, 6.0, 0.02, (0, 0, -2.5), mat_space)

# 40 background stars
for i in range(40):
    a = rng.uniform(0, 2*math.pi)
    r = rng.uniform(2.0, 3.0)
    z = rng.uniform(-2.0, 2.0)
    _sphere(f"star_{i}", rng.uniform(0.010, 0.025),
              (r * math.cos(a), r * math.sin(a), z), mat_star, u=8, v=6)

# --- event horizon (pure black sphere) ---
HORIZON_R = 0.30
_sphere("horizon", HORIZON_R, (0, 0, 0), mat_horizon, u=32, v=20)

# --- accretion disc (3 concentric rings) — anim spin pivot ---
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
disc_pivot = bpy.context.active_object
disc_pivot.name = "disc_pivot"

# 3 ring discs (squashed toroids)
DISC_DEFS = [
    (HORIZON_R * 1.3, 0.010, mat_disc_b),
    (HORIZON_R * 1.7, 0.012, mat_disc_a),
    (HORIZON_R * 2.2, 0.014, mat_disc_c),
]
for k, (Rm, Rmn, mat) in enumerate(DISC_DEFS):
    ring = _torus(f"disc_{k}", Rm, Rmn, (0, 0, 0), mat, ms=48, mn=6)
    # squash to flat disc
    for v in ring.data.vertices:
        v.co.z *= 0.18
    ring.parent = disc_pivot
    ring.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- gravitational lensing halo (a larger translucent sphere) ---
_sphere("halo", HORIZON_R * 1.05, (0, 0, 0), mat_halo, u=24, v=16,
         scale=(2.5, 2.5, 0.3))

# --- 2 polar jets (cone going up + down) ---
JET_LEN = 1.40
# upper jet
upper_jet = _cyl("jet_upper", 0.02, 0.10, JET_LEN, 'Z',
                   (0, 0, JET_LEN/2 + HORIZON_R * 0.5), mat_jet, segments=20)
# lower jet (flipped)
lower_jet = _cyl("jet_lower", 0.02, 0.10, JET_LEN, 'Z',
                   (0, 0, -JET_LEN/2 - HORIZON_R * 0.5), mat_jet, segments=20)
# jet tips (bright bulb at the end)
upper_tip = _sphere("jet_tip_up", 0.08, (0, 0, JET_LEN + HORIZON_R * 0.5 + 0.04),
                      mat_jet_tip, u=14, v=10, scale=(1.0, 1.0, 0.6))
lower_tip = _sphere("jet_tip_low", 0.08, (0, 0, -JET_LEN - HORIZON_R * 0.5 - 0.04),
                      mat_jet_tip, u=14, v=10, scale=(1.0, 1.0, 0.6))

# --- animation ---
FPS = 30
DURATION = 8.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# disc rotates fast : 3 turns per loop
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    disc_pivot.rotation_euler = (0, 0, 2*math.pi * 3 * t)
    disc_pivot.keyframe_insert("rotation_euler", frame=f)
if disc_pivot.animation_data and disc_pivot.animation_data.action:
    for fc in disc_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# 3 disc rings pulse different emission rates
for k, (_, _, mat) in enumerate(DISC_DEFS):
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    em = bsdf.inputs["Emission Strength"]
    base = {0: 12.0, 1: 8.0, 2: 6.0}[k]
    freq = 2.0 + k * 0.5
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        val = base + 3.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * freq + k))
        em.default_value = val
        bpy.context.scene.frame_set(f)
        em.keyframe_insert(data_path="default_value", frame=f)

# halo throbs slow
bsdf_h = mat_halo.node_tree.nodes.get("Principled BSDF")
em_h = bsdf_h.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_h.default_value = 3.0 + 1.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * 0.6))
    bpy.context.scene.frame_set(f)
    em_h.keyframe_insert(data_path="default_value", frame=f)

# jets pulse with sharp bright peaks
bsdf_j = mat_jet.node_tree.nodes.get("Principled BSDF")
em_j = bsdf_j.inputs["Emission Strength"]
bsdf_jt = mat_jet_tip.node_tree.nodes.get("Principled BSDF")
em_jt = bsdf_jt.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    # pulsing : multiple sharp peaks per cycle
    pulse = math.exp(-((math.sin(2*math.pi*t * 4) - 0.7) * 5)**2) if math.sin(2*math.pi*t * 4) > 0 else 0
    em_j.default_value = 8.0 + 10.0 * pulse
    em_jt.default_value = 14.0 + 12.0 * pulse
    bpy.context.scene.frame_set(f)
    em_j.keyframe_insert(data_path="default_value", frame=f)
    em_jt.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"BH_OK: {out_glb}", flush=True)
'''


def make_bh(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_bh_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "BH_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_bh(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
