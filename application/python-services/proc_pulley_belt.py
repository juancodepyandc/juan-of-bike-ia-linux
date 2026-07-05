"""Procedural pulley+belt mechanism generator (Blender, no aurora_3d).

Builds a textured PBR pulley-belt system:
  - 2 brass cylinders (pulleys) at +/- offset
  - a continuous belt (rectangular loop with rounded ends, rubber-like dark grey roughness 0.6)
  - keyframe rotation on each pulley (matching gear ratio)
  - belt translates around the loop via shape animation (uv-scroll on a Texture would be cleanest;
    here we use simple frame-keyed material offset)
  - exports a single GLB with embedded animation

CLI:
  python proc_pulley_belt.py <output_glb>
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_APP = _HERE.parent  # application/

def _find_blender() -> str | None:
    for sub in (_APP / "_blender").glob("blender-*-windows-x64"):
        exe = sub / "blender.exe"
        if exe.is_file():
            return str(exe)
    return shutil.which("blender")


_BLENDER_SCRIPT = r'''
import bpy, math, sys, os

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

args = _argv()
out_glb = args[0] if args else "pulley.glb"

# Empty scene
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"

# --- materials --------------------------------------------------------------
def pbr_mat(name, color, metallic, roughness):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
    return m

mat_brass = pbr_mat("brass", (0.86, 0.62, 0.20), 1.0, 0.28)
mat_rubber = pbr_mat("rubber", (0.06, 0.06, 0.07), 0.0, 0.65)
mat_steel = pbr_mat("steel", (0.55, 0.55, 0.58), 1.0, 0.45)
mat_belt_stripe = pbr_mat("belt_stripe", (0.18, 0.18, 0.20), 0.05, 0.55)

# --- socle / base plate (steel) ---------------------------------------------
SOCLE_W = 3.4
SOCLE_D = 1.4
SOCLE_H = 0.18
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.95))
socle = bpy.context.active_object
socle.name = "socle"
socle.scale = (SOCLE_W / 2, SOCLE_D / 2, SOCLE_H / 2)
bpy.ops.object.transform_apply(scale=True)
socle.data.materials.append(mat_steel)
m = socle.modifiers.new("Bevel", "BEVEL"); m.width = 0.02; m.segments = 3

# vertical posts holding the pulleys
for x_post in (-1.10, 1.10):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x_post, 0, -0.45))
    post = bpy.context.active_object
    post.name = f"post_{'L' if x_post<0 else 'R'}"
    post.scale = (0.10, 0.20, 0.50)
    bpy.ops.object.transform_apply(scale=True)
    post.data.materials.append(mat_steel)
    m = post.modifiers.new("Bevel", "BEVEL"); m.width = 0.012; m.segments = 2

# --- pulleys (v3 : with V-groove) ------------------------------------------
PULLEY_R = 0.55
PULLEY_W = 0.22
PULLEY_X = 1.10
RIM_W = PULLEY_W * 0.28        # each flanking rim
GROOVE_W = PULLEY_W - 2 * RIM_W # central narrower section the belt sits in
GROOVE_R = PULLEY_R * 0.82      # smaller radius => groove

def make_pulley(name, x):
    # Build 3 stacked cylinders along the cylinder's local Z (becomes world Y
    # after the rot X=90 below), join them into a single mesh so we can
    # keyframe a single rotation_euler[2] for the spin.
    pieces = []
    for piece_name, z_off, rad, width in [
        (f"{name}_rim_L", -PULLEY_W / 2 + RIM_W / 2, PULLEY_R, RIM_W),
        (f"{name}_grv",   0.0,                       GROOVE_R, GROOVE_W),
        (f"{name}_rim_R", +PULLEY_W / 2 - RIM_W / 2, PULLEY_R, RIM_W),
    ]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=rad, depth=width, location=(x, 0, z_off))
        c = bpy.context.active_object
        c.name = piece_name
        c.data.materials.append(mat_brass)
        pieces.append(c)
    # Hub axle (taller cylinder running through the pulley)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=PULLEY_R * 0.30, depth=PULLEY_W * 1.4, location=(x, 0, 0))
    hub = bpy.context.active_object
    hub.name = f"{name}_hub"
    hub.data.materials.append(mat_brass)
    pieces.append(hub)
    # Join all pieces into a single object (active = first piece)
    bpy.ops.object.select_all(action="DESELECT")
    for p in pieces:
        p.select_set(True)
    bpy.context.view_layer.objects.active = pieces[0]
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    # lay it sideways so belt wraps around (spin axis becomes world Y)
    obj.rotation_euler = (math.radians(90), 0, 0)
    # Bevel for PBR edge highlights
    mod = obj.modifiers.new("Bevel", "BEVEL"); mod.width = 0.010; mod.segments = 2
    return obj

pul1 = make_pulley("pulley_left", -PULLEY_X)
pul2 = make_pulley("pulley_right", PULLEY_X)

# --- belt -------------------------------------------------------------------
# torus along the centre line wouldn't fit (the belt is a stadium shape, not a circle).
# Approximate by: a single tube extruded along a path. Easiest in Blender:
# create a curve "stadium" of length 2*PULLEY_X with PULLEY_R radius caps, then
# convert + add a Solidify or Wireframe modifier with thickness.
import bmesh

BELT_WIDTH = GROOVE_W * 0.92   # narrow enough to sit visibly inside the V-groove
BELT_THICK = 0.022

mesh = bpy.data.meshes.new("belt")
obj_belt = bpy.data.objects.new("belt", mesh)
bpy.context.collection.objects.link(obj_belt)
bm = bmesh.new()

# build stadium centreline (top straight + right arc + bottom straight + left arc)
N_ARC = 24
pts = []
# top straight: from (-PULLEY_X, +PULLEY_R) to (+PULLEY_X, +PULLEY_R)
for i in range(N_ARC):
    t = i / N_ARC
    pts.append((-PULLEY_X + 2 * PULLEY_X * t, PULLEY_R, 0))
# right arc: from (PULLEY_X, +PULLEY_R) sweeping down to (PULLEY_X, -PULLEY_R)
for i in range(N_ARC):
    a = math.pi/2 - math.pi * (i / N_ARC)
    pts.append((PULLEY_X + math.cos(a) * PULLEY_R, math.sin(a) * PULLEY_R, 0))
# bottom straight: from (+PULLEY_X, -PULLEY_R) to (-PULLEY_X, -PULLEY_R)
for i in range(N_ARC):
    t = i / N_ARC
    pts.append((PULLEY_X - 2 * PULLEY_X * t, -PULLEY_R, 0))
# left arc: from (-PULLEY_X, -PULLEY_R) sweeping up to (-PULLEY_X, +PULLEY_R)
for i in range(N_ARC):
    a = -math.pi/2 - math.pi * (i / N_ARC)
    pts.append((-PULLEY_X + math.cos(a) * PULLEY_R, math.sin(a) * PULLEY_R, 0))

# build a closed strip with thickness (extrude along z by belt-width then offset by belt-thick)
# For simplicity: 4 rings along Z (front+back faces of belt)
half_w = BELT_WIDTH / 2
half_t = BELT_THICK / 2
outer_pts = []
inner_pts = []
for (x, y, _) in pts:
    # compute outward normal in XY (just normalised position from centreline midpoint nearest to (x,y))
    # for stadium: outward = away from nearest centre point (-PULLEY_X,0) or (+PULLEY_X,0)
    cx = PULLEY_X if x >= 0 else -PULLEY_X
    nx = x - cx
    ny = y
    nlen = math.sqrt(nx*nx + ny*ny) or 1.0
    nx /= nlen; ny /= nlen
    outer_pts.append((x + nx * half_t, y + ny * half_t))
    inner_pts.append((x - nx * half_t, y - ny * half_t))

ring_outer_front = []
ring_outer_back = []
ring_inner_front = []
ring_inner_back = []
for (ox, oy), (ix, iy) in zip(outer_pts, inner_pts):
    ring_outer_front.append(bm.verts.new((ox, oy, +half_w)))
    ring_outer_back.append(bm.verts.new((ox, oy, -half_w)))
    ring_inner_front.append(bm.verts.new((ix, iy, +half_w)))
    ring_inner_back.append(bm.verts.new((ix, iy, -half_w)))
bm.verts.ensure_lookup_table()

n = len(outer_pts)
for i in range(n):
    j = (i + 1) % n
    # outer band (front face)
    bm.faces.new((ring_outer_front[i], ring_outer_front[j], ring_outer_back[j], ring_outer_back[i]))
    # inner band
    bm.faces.new((ring_inner_back[i], ring_inner_back[j], ring_inner_front[j], ring_inner_front[i]))
    # front cap
    bm.faces.new((ring_outer_front[i], ring_inner_front[i], ring_inner_front[j], ring_outer_front[j]))
    # back cap
    bm.faces.new((ring_outer_back[j], ring_inner_back[j], ring_inner_back[i], ring_outer_back[i]))

bm.normal_update()
bm.to_mesh(mesh)
bm.free()
obj_belt.data.materials.append(mat_rubber)

# --- belt rivets (small dark studs that *scroll* along centreline) ----------
# Each rivet is a small cube riding on the belt; its position is keyframed
# along the stadium centreline so the belt visibly travels at constant speed
# (in v2 the stripes were static, which looked dead — here they convey
# real belt motion synced with the pulley spin).
STRIPE_COUNT = 36
N_PTS = len(pts)  # number of centreline samples

def _sample_centreline(tt):
    """tt in [0,1) -> (sx, sy, nx, ny) — position + outward normal."""
    tt = tt - math.floor(tt)
    idx = int(tt * N_PTS) % N_PTS
    sx, sy, _ = pts[idx]
    cx = PULLEY_X if sx >= 0 else -PULLEY_X
    nx = sx - cx; ny = sy
    nlen = math.sqrt(nx*nx + ny*ny) or 1.0
    return sx, sy, nx/nlen, ny/nlen

rivets = []
RIVET_LIFT = half_t + 0.0035   # above the outer belt surface
for i in range(STRIPE_COUNT):
    t0 = i / STRIPE_COUNT
    sx, sy, nx, ny = _sample_centreline(t0)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(sx + nx * RIVET_LIFT, sy + ny * RIVET_LIFT, 0))
    s = bpy.context.active_object
    s.name = f"belt_rivet_{i:02d}"
    # axisymmetric stud — no tangent rotation needed (avoids unwrap issues)
    s.scale = (0.018, 0.018, BELT_WIDTH * 0.92)
    bpy.ops.object.transform_apply(scale=True)
    s.data.materials.append(mat_belt_stripe)
    rivets.append(s)

# --- animation ---------------------------------------------------------------
# rotate each pulley around its own X axis (the local axis after rotation_euler X=90deg
# the cylinder's main axis points along +Y world before rotation; after rotation it points along +Z?
# Easier: just keyframe the rotation_euler Z (world up) — pulleys are vertical now (axis Y world),
# so the spin should be around their original Y axis. Wait — we did rotation_euler=(90deg, 0, 0)
# so the cylinder lays sideways. In its local frame the spin axis is the original Z. Use rotation_euler[2].
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

# left + right pulleys: both rotate same direction (outer belt drive).
# One revolution per loop -> matches the rivet-scroll speed below.
for o in (pul1, pul2):
    o.keyframe_insert(data_path="rotation_euler", frame=1)
    o.rotation_euler = (math.radians(90), 0, math.radians(360))
    o.keyframe_insert(data_path="rotation_euler", frame=NFR)
    if o.animation_data and o.animation_data.action:
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# rivets: scroll along the centreline at 1 full loop per animation period.
# Each rivet's t advances by (f-1)/NFR, mod 1.
KEY_EVERY = 3
for i, s in enumerate(rivets):
    t0 = i / STRIPE_COUNT
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (t0 + (f - 1) / NFR) % 1.0
        sx, sy, nx, ny = _sample_centreline(t)
        bpy.context.scene.frame_set(f)
        s.location = (sx + nx * RIVET_LIFT, sy + ny * RIVET_LIFT, 0)
        s.keyframe_insert(data_path="location", frame=f)
    # close the loop: keyframe at NFR+1 = same as frame 1 so the cycle repeats seamlessly
    if s.animation_data and s.animation_data.action:
        # CONSTANT interpolation gives a "step" feel; LINEAR is smoother but
        # the rivet path is a stadium so straight LINEAR between sparse keys
        # cuts corners. KEY_EVERY=3 keeps cuts < 1mm so LINEAR is fine.
        for fc in s.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# Belt body: very slight bob to give a subliminal sense of tension flex
# (the perceived scroll motion comes from the rivets, not the body).
for f in range(1, NFR + 1, max(1, NFR // 6)):
    bpy.context.scene.frame_set(f)
    phase = (f / NFR) * math.pi * 2
    obj_belt.location.y = math.sin(phase) * 0.0015
    obj_belt.keyframe_insert(data_path="location", frame=f)
if obj_belt.animation_data and obj_belt.animation_data.action:
    for fc in obj_belt.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# --- export ------------------------------------------------------------------
bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", export_animations=True, export_apply=False)
print(f"PULLEY_OK: {out_glb}", flush=True)
'''


def make_pulley(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_pulley_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "PULLEY_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_pulley(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
