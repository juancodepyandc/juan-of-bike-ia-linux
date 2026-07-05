"""Procedural xylophone (Blender headless).

Wood frame with 2 rails + 7 colourful bars of decreasing length +
2 mallets above the bars. Animation : mallets strike the bars in
sequence ; each bar bobs slightly after being struck.

CLI:
  python proc_xylophone.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "xylo.glb"

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

mat_wood    = pbr_mat("wood",        (0.32, 0.18, 0.08), 0.00, 0.60)
mat_rail    = pbr_mat("rail",        (0.40, 0.25, 0.12), 0.20, 0.55)
mat_handle  = pbr_mat("mallet_wood", (0.55, 0.35, 0.15), 0.00, 0.55)
mat_tip     = pbr_mat("mallet_tip",  (0.95, 0.88, 0.82), 0.00, 0.40)
mat_floor   = pbr_mat("floor",       (0.32, 0.32, 0.34), 0.00, 0.85)

BAR_COLORS = [
    pbr_mat("bar_red",    (0.85, 0.15, 0.10), 0.20, 0.35),
    pbr_mat("bar_orange", (0.95, 0.55, 0.10), 0.20, 0.35),
    pbr_mat("bar_yellow", (0.95, 0.85, 0.15), 0.20, 0.35),
    pbr_mat("bar_green",  (0.18, 0.65, 0.20), 0.20, 0.35),
    pbr_mat("bar_blue",   (0.12, 0.35, 0.85), 0.20, 0.35),
    pbr_mat("bar_indigo", (0.30, 0.20, 0.75), 0.20, 0.35),
    pbr_mat("bar_violet", (0.65, 0.20, 0.80), 0.20, 0.35),
]

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

# --- floor ---------------------------------------------
_box("floor", 1.6, 1.2, 0.04, (0, 0, -0.04), mat_floor)

# --- wood frame : 2 trapezoidal side rails -----------
N_BARS = 7
BAR_MAX = 0.70    # longest bar
BAR_MIN = 0.40    # shortest bar
BAR_W   = 0.07    # width of each bar
BAR_T   = 0.018   # thickness
BAR_SPACING = 0.085
TOTAL_SPAN = (N_BARS - 1) * BAR_SPACING

# 2 side rails (slanted to suggest the tapering of bar lengths)
for sy_sign in (-1, +1):
    # rail position : extends from far bar end to near bar end
    # bars are centred in Y at 0, but their length tapers from BAR_MAX (left)
    # to BAR_MIN (right). The rail follows the half-length at each X.
    # For simplicity: each rail is a thin box angled.
    rail_x = 0
    bpy.ops.mesh.primitive_cube_add(size=1, location=(rail_x, sy_sign * BAR_MAX/2 * 0.85, 0.04))
    r = bpy.context.active_object
    r.name = f"rail_{sy_sign}"
    rail_len = TOTAL_SPAN + 0.10
    r.scale = (rail_len, 0.03, 0.04)
    bpy.ops.object.transform_apply(scale=True)
    # rotate around Z so the rail tapers toward the shorter bars (right side)
    angle = math.atan2((BAR_MIN - BAR_MAX) / 2, TOTAL_SPAN)
    r.rotation_euler = (0, 0, sy_sign * angle)
    r.data.materials.append(mat_rail)

# 2 short crossbars connecting the rails at each end
_box("crossbar_left",  0.04, BAR_MAX, 0.03, (-TOTAL_SPAN/2 - 0.04, 0, 0.04), mat_wood)
_box("crossbar_right", 0.04, BAR_MIN, 0.03, (+TOTAL_SPAN/2 + 0.04, 0, 0.04), mat_wood)

# --- 7 bars (each with its own pivot for bob animation) -----
bar_pivots = []
for i in range(N_BARS):
    bar_x = -TOTAL_SPAN/2 + i * BAR_SPACING
    bar_y_len = BAR_MAX + (BAR_MIN - BAR_MAX) * (i / (N_BARS - 1))
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(bar_x, 0, 0.075))
    pv = bpy.context.active_object
    pv.name = f"bar_pivot_{i}"
    bar = _box(f"bar_{i}", BAR_W, bar_y_len, BAR_T, (0, 0, 0), BAR_COLORS[i])
    bar.parent = pv
    bar.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    bar_pivots.append(pv)

# --- 2 mallets (each parented to its own pivot for the strike animation)
def _make_mallet(name, side):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, side * 0.55, 0.30))
    pv = bpy.context.active_object
    pv.name = f"mallet_pivot_{name}"
    # handle (cylinder along Y)
    h = _cyl(f"mallet_handle_{name}", 0.008, 0.008, 0.40, 'Y', (0, 0, 0), mat_handle)
    h.parent = pv
    h.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    h.location = (0, -side * 0.20, 0)
    # mallet head (white sphere)
    head = _sphere(f"mallet_head_{name}", 0.025, (0, 0, 0), mat_tip)
    head.parent = pv
    head.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    head.location = (0, -side * 0.42, 0)
    return pv

mallet_L = _make_mallet("L", +1)
mallet_R = _make_mallet("R", -1)

# --- animation ---------------------------------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 1

# Each bar is struck once during the loop, in sequence from left (0) to
# right (6).  Mallet L strikes bars 0, 2, 4, 6 ; mallet R strikes 1, 3, 5.
def strike_schedule():
    """Return list of (t_strike, bar_index, mallet) at which strikes happen."""
    schedule = []
    for i in range(N_BARS):
        t = (i + 1) / (N_BARS + 1)   # spaced through the loop
        mallet = mallet_L if i % 2 == 0 else mallet_R
        schedule.append((t, i, mallet))
    return schedule

schedule = strike_schedule()

# Mallet animation : approach bar -> tap -> retract.  We key the mallet's
# pivot location.x to centre over the bar, and its z to drop + retract.
for (t_strike, bar_i, mallet) in schedule:
    f_pre  = int((t_strike - 0.06) * NFR)
    f_hit  = int(t_strike * NFR)
    f_post = int((t_strike + 0.10) * NFR)
    f_pre = max(1, f_pre); f_post = min(NFR, f_post)
    bar_x = -TOTAL_SPAN/2 + bar_i * BAR_SPACING

    # rest position (off to side, raised)
    rest_loc = list(mallet.location)
    bpy.context.scene.frame_set(max(1, f_pre - 5))
    mallet.location = (rest_loc[0], rest_loc[1], 0.30)
    mallet.keyframe_insert("location", frame=max(1, f_pre - 5))
    # approach over bar at full height
    bpy.context.scene.frame_set(f_pre)
    mallet.location = (bar_x, rest_loc[1] * 0.8, 0.22)
    mallet.keyframe_insert("location", frame=f_pre)
    # strike : lower to bar height
    bpy.context.scene.frame_set(f_hit)
    mallet.location = (bar_x, rest_loc[1] * 0.6, 0.10)
    mallet.keyframe_insert("location", frame=f_hit)
    # retract
    bpy.context.scene.frame_set(f_post)
    mallet.location = (bar_x, rest_loc[1] * 0.8, 0.22)
    mallet.keyframe_insert("location", frame=f_post)
    # back to rest
    bpy.context.scene.frame_set(min(NFR, f_post + 8))
    mallet.location = rest_loc
    mallet.keyframe_insert("location", frame=min(NFR, f_post + 8))

# Bar bob : when struck, the bar drops 5 mm + springs back over the next 0.30 s
for (t_strike, bar_i, mallet) in schedule:
    pv = bar_pivots[bar_i]
    f_hit  = int(t_strike * NFR)
    f_end  = min(NFR, int((t_strike + 0.30) * NFR))
    bpy.context.scene.frame_set(max(1, f_hit - 1))
    pv.location.z = 0.075
    pv.keyframe_insert("location", frame=max(1, f_hit - 1))
    bpy.context.scene.frame_set(f_hit)
    pv.location.z = 0.075 - 0.006
    pv.keyframe_insert("location", frame=f_hit)
    bpy.context.scene.frame_set(min(NFR, f_hit + 4))
    pv.location.z = 0.075 + 0.003
    pv.keyframe_insert("location", frame=min(NFR, f_hit + 4))
    bpy.context.scene.frame_set(f_end)
    pv.location.z = 0.075
    pv.keyframe_insert("location", frame=f_end)

# LINEAR everywhere
for o in list(bar_pivots) + [mallet_L, mallet_R]:
    if o.animation_data and o.animation_data.action:
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"XYLO_OK: {out_glb}", flush=True)
'''


def make_xylo(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_xylo_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "XYLO_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_xylo(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
