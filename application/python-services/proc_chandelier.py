"""Procedural baroque chandelier (Blender headless).

Ceiling plate + hanging chain + central brass column with 3 bobeche
discs + 8 curved arms ending in bobeches + 8 candle cylinders + 8 flame
emissives + 24 crystal teardrop pendants on the lower bobeche.
Animation : whole chandelier rotates slowly + each flame's emission
strength flickers on its own phase + crystals subtly catch light pulses.

CLI:
  python proc_chandelier.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "chandelier.glb"

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

mat_ceiling = pbr_mat("ceiling",     (0.85, 0.83, 0.78), 0.00, 0.70)
mat_brass   = pbr_mat("brass",       (0.92, 0.72, 0.25), 1.00, 0.20)
mat_brass_d = pbr_mat("brass_dark",  (0.55, 0.40, 0.10), 0.80, 0.35)
mat_chain   = pbr_mat("chain",       (0.65, 0.55, 0.30), 0.90, 0.30)
mat_candle  = pbr_mat("candle_wax",  (0.95, 0.92, 0.85), 0.00, 0.45)
mat_crystal = pbr_mat("crystal",     (0.92, 0.94, 0.95), 0.05, 0.08, alpha=0.55)

def make_flame_mat(name):
    return pbr_mat(name, (1.00, 0.75, 0.30), 0.00, 0.10,
                      alpha=0.85,
                      emission=((1.00, 0.65, 0.15), 8.0))

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

def _sphere(name, R, location, mat, u=14, v=10, scale=(1,1,1)):
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

# --- ceiling plate (fixed, NOT under the rotating pivot) -------
CEIL_Z = 2.20
_box("ceiling_plane", 2.4, 2.4, 0.02, (0, 0, CEIL_Z), mat_ceiling)
_cyl("ceiling_cap", 0.08, 0.06, 0.02, 'Z', (0, 0, CEIL_Z - 0.02), mat_brass)

# --- chain (8 short links of brass torus-like rings — approximated
# with thin cylinders, alternating axis to suggest interlocking) -----
N_LINKS = 8
CHAIN_TOP_Z = CEIL_Z - 0.04
CHAIN_BOT_Z = 1.50
for i in range(N_LINKS):
    z = CHAIN_TOP_Z - (i + 0.5) * (CHAIN_TOP_Z - CHAIN_BOT_Z) / N_LINKS
    axis = 'X' if i % 2 == 0 else 'Y'
    _cyl(f"chain_{i}", 0.022, 0.022, 0.006, axis, (0, 0, z), mat_chain, segments=12)

# --- rotating chandelier pivot -----------------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, CHAIN_BOT_Z))
chandel = bpy.context.active_object
chandel.name = "chandelier_pivot"

# central brass column (vertical body) - parented to pivot
COL_H = 0.55
col = _cyl("center_col", 0.04, 0.04, COL_H, 'Z', (0, 0, -COL_H/2), mat_brass, segments=20)
col.parent = chandel; col.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# central ornament : 3 stacked spheres along the column
for k, (sz, z) in enumerate([(0.06, -0.08), (0.08, -0.26), (0.05, -COL_H + 0.04)]):
    ball = _sphere(f"col_ball_{k}", sz, (0, 0, z), mat_brass)
    ball.parent = chandel; ball.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# upper bobeche disc (decorative ring near the top of the body)
upper_disc = _cyl("upper_disc", 0.10, 0.08, 0.012, 'Z',
                    (0, 0, -0.18), mat_brass_d, segments=20)
upper_disc.parent = chandel; upper_disc.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# arms ring : where the 8 candle arms attach
ARM_HUB_Z = -COL_H + 0.10
hub = _cyl("arm_hub", 0.10, 0.10, 0.015, 'Z',
             (0, 0, ARM_HUB_Z), mat_brass, segments=20)
hub.parent = chandel; hub.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# lower bobeche disc (where crystals hang) — slightly larger, lower
LOWER_DISC_Z = -COL_H - 0.02
lower_disc = _cyl("lower_disc", 0.36, 0.34, 0.015, 'Z',
                    (0, 0, LOWER_DISC_Z), mat_brass_d, segments=32)
lower_disc.parent = chandel; lower_disc.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# bottom finial under the column
final_ball = _sphere("final_ball", 0.05,
                       (0, 0, LOWER_DISC_Z - 0.05), mat_brass)
final_ball.parent = chandel
final_ball.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 8 curved arms with candles ----------------------
N_ARMS = 8
ARM_R   = 0.38  # how far the candle sits out from the column
ARM_UP  = 0.16  # vertical rise of the bobeche above the hub
N_SEGS  = 4     # arm sub-segments to approximate the curve

flame_mats = []  # one mat per candle, so we can flicker individually

for i in range(N_ARMS):
    a = 2*math.pi * i / N_ARMS
    cos_a = math.cos(a); sin_a = math.sin(a)
    # build the arm as a polyline of 4 short cylinders following a 1/4 arc
    # in the radial-vertical plane (r,z).
    arm_pts = []
    for k in range(N_SEGS + 1):
        u = k / N_SEGS  # 0..1
        # parametric : starts at (r=0.10, z=ARM_HUB_Z), curves out and up
        # following sqrt-like profile
        r = 0.10 + (ARM_R - 0.10) * u
        z = ARM_HUB_Z + ARM_UP * (1.0 - (1.0 - u)**2)
        arm_pts.append((r * cos_a, r * sin_a, z))
    for k in range(N_SEGS):
        p0 = arm_pts[k]; p1 = arm_pts[k+1]
        mx = (p0[0]+p1[0])/2; my = (p0[1]+p1[1])/2; mz = (p0[2]+p1[2])/2
        dx, dy, dz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
        L = math.sqrt(dx*dx + dy*dy + dz*dz)
        seg = _cyl(f"arm_{i}_seg_{k}", 0.014, 0.014, L, 'Z', (0,0,0), mat_brass)
        seg.location = (mx, my, mz)
        direction = mathutils.Vector((dx, dy, dz)).normalized()
        seg.rotation_mode = 'QUATERNION'
        seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
        seg.parent = chandel; seg.matrix_parent_inverse = mathutils.Matrix.Identity(4)

    # bobeche cup at the candle base
    bob_x, bob_y, bob_z = arm_pts[-1]
    bobeche = _cyl(f"bobeche_{i}", 0.03, 0.024, 0.012, 'Z',
                     (bob_x, bob_y, bob_z + 0.006), mat_brass_d, segments=12)
    bobeche.parent = chandel; bobeche.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # candle wax cylinder
    candle = _cyl(f"candle_{i}", 0.012, 0.012, 0.08, 'Z',
                    (bob_x, bob_y, bob_z + 0.052), mat_candle, segments=12)
    candle.parent = chandel; candle.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # wick (thin dark cyl on top)
    wick = _cyl(f"wick_{i}", 0.0015, 0.0015, 0.010, 'Z',
                  (bob_x, bob_y, bob_z + 0.097), mat_brass_d, segments=6)
    wick.parent = chandel; wick.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # flame : a small flattened sphere (UV scaled into a teardrop), emissive
    fm = make_flame_mat(f"flame_mat_{i}")
    flame_mats.append(fm)
    flame = _sphere(f"flame_{i}", 0.012,
                      (bob_x, bob_y, bob_z + 0.110), fm,
                      scale=(1.0, 1.0, 1.7))
    flame.parent = chandel; flame.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- 24 crystal teardrop pendants on the lower bobeche ---
N_CRYSTALS = 24
for i in range(N_CRYSTALS):
    a = 2*math.pi * i / N_CRYSTALS
    cos_a = math.cos(a); sin_a = math.sin(a)
    r = 0.34
    cx = r * cos_a; cy = r * sin_a
    # short brass connector
    conn = _cyl(f"crystal_conn_{i}", 0.003, 0.003, 0.012, 'Z',
                  (cx, cy, LOWER_DISC_Z - 0.012), mat_brass)
    conn.parent = chandel; conn.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # crystal teardrop (squashed sphere)
    cr = _sphere(f"crystal_{i}", 0.018,
                   (cx, cy, LOWER_DISC_Z - 0.034), mat_crystal,
                   scale=(0.7, 0.7, 1.4))
    cr.parent = chandel; cr.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation -------------------------------------
FPS = 30
DURATION = 8.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
# chandelier rotates 0.25 turn per loop (very slow)
TURNS = 0.25
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    chandel.rotation_euler = (0, 0, 2*math.pi * TURNS * t)
    chandel.keyframe_insert("rotation_euler", frame=f)
if chandel.animation_data and chandel.animation_data.action:
    for fc in chandel.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Each flame flickers individually : emission strength oscillates around
# a base value with its own phase + frequency.
for i, fm in enumerate(flame_mats):
    bsdf = fm.node_tree.nodes.get("Principled BSDF")
    em = bsdf.inputs["Emission Strength"]
    phase = i * 2*math.pi / N_ARMS + 0.7
    freq  = 5.0 + (i % 3) * 1.5  # Hz
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        val = 6.0 + 2.5 * (0.5 + 0.5 * math.sin(2*math.pi*t * freq + phase))
        # add a smaller faster jitter
        val += 0.8 * math.sin(2*math.pi*t * (freq * 3.7) + phase * 2.0)
        em.default_value = max(0.5, val)
        bpy.context.scene.frame_set(f)
        em.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"CHANDEL_OK: {out_glb}", flush=True)
'''


def make_chandelier(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_chandel_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "CHANDEL_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_chandelier(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
