"""Procedural sailboat (Blender headless).

Hull (tapered bmesh) + mast + mainsail + jib + boom + water plane.
The whole boat rocks (pitch + roll sin waves) with the sails sharing
the same root so they tilt together. The mainsail has a shape key for
subtle wind flutter.

CLI:
  python proc_sailboat.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "sailboat.glb"

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

mat_hull_white = pbr_mat("hull_white",  (0.94, 0.93, 0.88), 0.00, 0.35)
mat_hull_red   = pbr_mat("hull_red",    (0.60, 0.10, 0.10), 0.00, 0.40)
mat_deck       = pbr_mat("deck_teak",   (0.40, 0.27, 0.13), 0.00, 0.55)
mat_mast       = pbr_mat("mast_wood",   (0.55, 0.40, 0.22), 0.00, 0.55)
mat_sail       = pbr_mat("sail_canvas", (0.92, 0.90, 0.84), 0.00, 0.60)
mat_water      = pbr_mat("water_deep",  (0.05, 0.20, 0.30), 0.00, 0.12)

# --- water plane ----------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.10))
water = bpy.context.active_object
water.name = "water"
water.scale = (5.0, 5.0, 0.06)
bpy.ops.object.transform_apply(scale=True)
water.data.materials.append(mat_water)

# --- root empty (drives the rocking animation) ----------------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
root = bpy.context.active_object
root.name = "boat_root"

# --- hull (tapered front/back) -------------------------------------------
# Build via bmesh : a stretched box that tapers along X.
HULL_L, HULL_W, HULL_H = 1.80, 0.40, 0.25
mesh_hull = bpy.data.meshes.new("hull")
hull = bpy.data.objects.new("hull", mesh_hull)
bpy.context.collection.objects.link(hull)
bm = bmesh.new()

# 4 transverse rings : front-point, front-bulge, back-bulge, back-point
sections = [
    (-HULL_L/2,        0.00,           0.0),                 # bow tip
    (-HULL_L/2 + 0.30, HULL_W/2 * 0.7, HULL_H * 0.5),         # forward bulge
    (-HULL_L/2 + 0.85, HULL_W/2,        HULL_H * 0.7),        # mid front
    (+HULL_L/2 - 0.50, HULL_W/2,        HULL_H * 0.65),       # mid aft
    (+HULL_L/2 - 0.10, HULL_W/2 * 0.85, HULL_H * 0.55),       # stern bulge
    (+HULL_L/2,        HULL_W/2 * 0.4,  HULL_H * 0.40),       # stern transom
]
rings = []
for (x, half_w, half_h) in sections:
    # ring of 6 points : top centre, top sides, bottom sides, bottom centre
    p_tc = bm.verts.new((x, 0,         +half_h))
    p_tr = bm.verts.new((x, +half_w,   +half_h * 0.85))
    p_br = bm.verts.new((x, +half_w * 0.6, -half_h * 0.85))
    p_bc = bm.verts.new((x, 0,         -half_h))
    p_bl = bm.verts.new((x, -half_w * 0.6, -half_h * 0.85))
    p_tl = bm.verts.new((x, -half_w,   +half_h * 0.85))
    rings.append([p_tc, p_tr, p_br, p_bc, p_bl, p_tl])
bm.verts.ensure_lookup_table()
N_RING = 6
for s in range(len(rings) - 1):
    r0 = rings[s]
    r1 = rings[s+1]
    for i in range(N_RING):
        j = (i + 1) % N_RING
        try:
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
        except ValueError:
            pass  # already exists
# cap ends with triangle fans
def _cap(ring):
    centre = bm.verts.new(((ring[0].co + ring[3].co) / 2))
    for i in range(N_RING):
        j = (i + 1) % N_RING
        try:
            bm.faces.new((centre, ring[i], ring[j]))
        except ValueError:
            pass
_cap(rings[0])
_cap(rings[-1])
bm.normal_update()
bm.to_mesh(mesh_hull); bm.free()
hull.data.materials.append(mat_hull_white)
hull.location = (0, 0, 0)
hull.parent = root
hull.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- red waterline stripe (a long thin red box just below mid-hull) -----
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.03))
stripe = bpy.context.active_object
stripe.name = "waterline_stripe"
stripe.scale = (HULL_L * 0.95, HULL_W * 1.02, 0.02)
bpy.ops.object.transform_apply(scale=True)
stripe.data.materials.append(mat_hull_red)
stripe.parent = root
stripe.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- deck (small wood plank in the middle) -----------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, HULL_H * 0.50))
deck = bpy.context.active_object
deck.name = "deck"
deck.scale = (HULL_L * 0.85, HULL_W * 0.85, 0.02)
bpy.ops.object.transform_apply(scale=True)
deck.data.materials.append(mat_deck)
deck.parent = root
deck.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- mast (tall vertical cylinder) -------------------------------------
mesh_mast = bpy.data.meshes.new("mast")
mast = bpy.data.objects.new("mast", mesh_mast)
bpy.context.collection.objects.link(mast)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=20,
                        radius1=0.025, radius2=0.020, depth=1.40)
bmesh.ops.translate(bm, vec=(0, 0, 1.40/2), verts=bm.verts)
bm.to_mesh(mesh_mast); bm.free()
mast.location = (0, 0, HULL_H * 0.55)
mast.data.materials.append(mat_mast)
mast.parent = root
mast.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- main sail (triangle) ----------------------------------------------
# vertices : top of mast (0, 0, 1.45 m above hull), bottom of mast (boom
# height ~0.10 above deck), boom tip at +X 0.85.
mesh_main = bpy.data.meshes.new("mainsail")
mainsail = bpy.data.objects.new("mainsail", mesh_main)
bpy.context.collection.objects.link(mainsail)
bm = bmesh.new()
v_top   = bm.verts.new((0,    0,   1.30))   # top
v_btm   = bm.verts.new((0,    0,   0.10))   # base at boom level
v_aft   = bm.verts.new((0.85, 0,   0.10))   # rear bottom corner
# slight curve : pull middle of the leech (top-to-aft edge) outward
v_mid_leech = bm.verts.new((0.55, 0.08, 0.72))  # bulge to +Y to simulate camber
bm.faces.new((v_top, v_btm, v_aft))
bm.faces.new((v_top, v_aft, v_mid_leech))
# also a small mirror for back side of the sail to look fuller
bm.normal_update()
bm.to_mesh(mesh_main); bm.free()
mainsail.location = (0, 0, HULL_H * 0.55)
mainsail.data.materials.append(mat_sail)
mainsail.parent = root
mainsail.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- boom (horizontal pole at the bottom of the mainsail) -------------
mesh_boom = bpy.data.meshes.new("boom")
boom = bpy.data.objects.new("boom", mesh_boom)
bpy.context.collection.objects.link(boom)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16,
                        radius1=0.020, radius2=0.020, depth=0.85)
bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'Y'), verts=bm.verts)
bmesh.ops.translate(bm, vec=(0.85/2, 0, 0), verts=bm.verts)
bm.to_mesh(mesh_boom); bm.free()
boom.location = (0, 0, HULL_H * 0.55 + 0.10)
boom.data.materials.append(mat_mast)
boom.parent = root
boom.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- jib (small triangular front sail) ---------------------------------
mesh_jib = bpy.data.meshes.new("jib")
jib = bpy.data.objects.new("jib", mesh_jib)
bpy.context.collection.objects.link(jib)
bm = bmesh.new()
v_t = bm.verts.new((-0.10, 0, 1.20))   # top
v_b = bm.verts.new((-0.75, 0, 0.12))   # bow tack
v_a = bm.verts.new(( 0.00, 0, 0.20))   # aft (at the mast)
v_m = bm.verts.new((-0.42, -0.06, 0.66))  # bulge to -Y
bm.faces.new((v_t, v_b, v_a))
bm.faces.new((v_t, v_a, v_m))
bm.normal_update()
bm.to_mesh(mesh_jib); bm.free()
jib.location = (0, 0, HULL_H * 0.55)
jib.data.materials.append(mat_sail)
jib.parent = root
jib.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : boat rocks ---------------------------------------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    # heave (Z bob), pitch (around Y), roll (around X)
    root.location = (0, 0, 0.02 * math.sin(2*math.pi*t))
    root.rotation_euler = (math.sin(2*math.pi*t)         * math.radians(4),  # roll
                            math.cos(2*math.pi*t * 0.5)   * math.radians(3), # pitch
                            0)
    root.keyframe_insert("location", frame=f)
    root.keyframe_insert("rotation_euler", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"SAILBOAT_OK: {out_glb}", flush=True)
'''


def make_sailboat(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_sb_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "SAILBOAT_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_sailboat(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
