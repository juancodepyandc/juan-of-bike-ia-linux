"""Procedural playground swing set (Blender headless).

Inverted-A steel frame (2 pairs of inclined legs + horizontal top bar)
+ 2 swings hanging on chains : red wooden plank seats + 4 chain strands
(2 per swing) + sand patch underneath + small wood border. Animation :
2 swings oscillate in opposite phase (pendulum sine), each swinging
rotation around the top bar.

CLI:
  python proc_playground_swing.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "swing.glb"

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

mat_grass    = pbr_mat("grass",     (0.20, 0.45, 0.18), 0.00, 0.85)
mat_sand     = pbr_mat("sand",      (0.85, 0.78, 0.55), 0.00, 0.85)
mat_wood     = pbr_mat("wood",      (0.38, 0.22, 0.10), 0.05, 0.55)
mat_steel    = pbr_mat("steel",     (0.55, 0.55, 0.58), 0.85, 0.30)
mat_steel_d  = pbr_mat("steel_dk",  (0.28, 0.28, 0.30), 0.70, 0.40)
mat_red      = pbr_mat("red",       (0.85, 0.18, 0.12), 0.10, 0.40)
mat_red_d    = pbr_mat("red_dk",    (0.60, 0.10, 0.06), 0.10, 0.45)
mat_chain    = pbr_mat("chain",     (0.45, 0.45, 0.48), 0.80, 0.35)

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=14, rot=None):
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

def _sphere(name, R, location, mat, u=10, v=8):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# Conventions : swing set faces -Y (kids swing toward -Y). Top bar along
# the X axis. Up = +Z.

# --- grass + sand --------
_box("floor", 4.0, 3.0, 0.04, (0, 0, -0.04), mat_grass)
_box("sand_patch", 2.8, 1.6, 0.025, (0, 0, 0.013), mat_sand)
# wood border around the sand
for sy in (-1, +1):
    _box(f"sand_border_X_{sy}", 2.8, 0.05, 0.05,
           (0, sy * 0.80, 0.025), mat_wood)
for sx in (-1, +1):
    _box(f"sand_border_Y_{sx}", 0.05, 1.6, 0.05,
           (sx * 1.40, 0, 0.025), mat_wood)

# --- inverted-A steel frame -------
# Top bar along X
TOP_Z = 2.30
TOP_W = 2.40
top_bar = _cyl("top_bar", 0.030, 0.030, TOP_W, 'X', (0, 0, TOP_Z), mat_steel)

# 4 legs : 2 pairs in inverted-V configuration, one pair at each end of
# the top bar. Each pair splays apart in the Y direction.
LEG_BOT_Y = 0.65    # how far each leg's bottom extends in Y
LEG_HEIGHT = TOP_Z - 0.05
for sx in (-1, +1):
    for sy in (-1, +1):
        # the leg goes from (sx*TOP_W/2, 0, TOP_Z) to (sx*TOP_W/2, sy*LEG_BOT_Y, 0.05)
        p0 = mathutils.Vector((sx * TOP_W/2, 0, TOP_Z))
        p1 = mathutils.Vector((sx * TOP_W/2, sy * LEG_BOT_Y, 0.05))
        d = p1 - p0
        L = d.length
        mid = (p0 + p1) * 0.5
        leg = _cyl(f"leg_{sx}_{sy}", 0.025, 0.025, L, 'Z', (0,0,0), mat_steel, segments=12)
        leg.location = mid
        leg.rotation_mode = 'QUATERNION'
        leg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(d.normalized())
        # foot anchor (small square plate buried in sand)
        _box(f"leg_foot_{sx}_{sy}", 0.10, 0.10, 0.020,
               (sx * TOP_W/2, sy * LEG_BOT_Y, 0.012), mat_steel_d)

# small chain link hooks where the swings attach to the top bar (4 chains
# in total, 2 per swing)
SWING_X = [-0.55, +0.55]    # X positions of the 2 swings
CHAIN_X_OFFSET = 0.18       # the 2 chains of one swing are this far apart in X

# --- 2 swings --------
swing_pivots = []
for swing_idx, cx in enumerate(SWING_X):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, 0, TOP_Z))
    sw = bpy.context.active_object
    sw.name = f"swing_{swing_idx}_pivot"
    swing_pivots.append(sw)
    # 2 chains
    SEAT_DROP = 1.50   # how far below the top bar the seat sits when at rest
    for sx_off in (-1, +1):
        chain_x = sx_off * CHAIN_X_OFFSET / 2
        # The chain hangs straight down — implement as 6 short cylinder
        # segments stacked
        N_LINKS = 6
        link_len = SEAT_DROP / N_LINKS
        for k in range(N_LINKS):
            seg = _cyl(f"swing_{swing_idx}_chain_{sx_off}_{k}",
                         0.006, 0.006, link_len * 0.85, 'Z',
                         (chain_x, 0, -(k + 0.5) * link_len),
                         mat_chain, segments=8)
            seg.parent = sw
            seg.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # seat (red wooden plank)
    seat = _box(f"swing_{swing_idx}_seat", CHAIN_X_OFFSET + 0.08, 0.18, 0.025,
                  (0, 0, -SEAT_DROP), mat_red)
    seat.parent = sw
    seat.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # seat trim (darker red along edges)
    for sy_t in (-1, +1):
        trim = _box(f"swing_{swing_idx}_seat_trim_{sy_t}",
                      CHAIN_X_OFFSET + 0.08, 0.015, 0.025,
                      (0, sy_t * 0.085, -SEAT_DROP), mat_red_d)
        trim.parent = sw
        trim.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # 2 small connecting eye-bolts (top of each chain at the bar)
    for sx_off in (-1, +1):
        eye = _sphere(f"swing_{swing_idx}_eye_{sx_off}", 0.015,
                        (sx_off * CHAIN_X_OFFSET / 2, 0, -0.018),
                        mat_steel)
        eye.parent = sw
        eye.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : 2 swings oscillate around X (swinging in YZ plane), opposite phase ---
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Amplitude : ±35° from vertical
SWING_AMP = math.radians(35)
# Frequency : 1 full oscillation per loop (i.e. 2π rad per loop)
for idx, sw in enumerate(swing_pivots):
    phase = idx * math.pi  # opposite phase between left and right
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        angle = SWING_AMP * math.sin(2*math.pi*t * 1.0 + phase)
        sw.rotation_euler = (angle, 0, 0)
        sw.keyframe_insert("rotation_euler", frame=f)
    if sw.animation_data and sw.animation_data.action:
        for fc in sw.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SWING_OK: {out_glb}", flush=True)
'''


def make_swing(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_swing_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SWING_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_swing(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
