"""Procedural Victorian street lamp (Blender headless).

Ornate cast-iron base + tall central column + 2 S-shaped scroll arms +
2 caged lantern fixtures with glass panes + emissive bulb inside each +
crown finial + a faint translucent halo of mist around each lantern.
Animation : warm-white bulbs pulse gently (gas-lamp flicker) + the
translucent halo brightens / dims in sync.

CLI:
  python proc_street_lamp.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "streetlamp.glb"

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

mat_floor    = pbr_mat("floor",     (0.10, 0.10, 0.13), 0.00, 0.85)
mat_pave     = pbr_mat("pave",      (0.30, 0.28, 0.26), 0.00, 0.85)
mat_iron     = pbr_mat("iron",      (0.10, 0.10, 0.11), 0.50, 0.45)
mat_iron_d   = pbr_mat("iron_dk",   (0.06, 0.06, 0.07), 0.40, 0.50)
mat_brass    = pbr_mat("brass",     (0.88, 0.65, 0.18), 1.00, 0.25)
mat_glass    = pbr_mat("glass",     (0.85, 0.85, 0.75), 0.00, 0.05, alpha=0.32)
mat_bulb     = pbr_mat("bulb",      (1.00, 0.90, 0.60), 0.00, 0.10,
                          emission=((1.00, 0.78, 0.35), 15.0))
mat_halo     = pbr_mat("halo",      (1.00, 0.85, 0.55), 0.00, 0.10,
                          alpha=0.10,
                          emission=((1.00, 0.78, 0.35), 0.8))

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

def _cyl(name, R1, R2, depth, axis, location, mat, segments=16, rot=None):
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

def _sphere(name, R, location, mat, u=16, v=12, scale=(1,1,1)):
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

# --- pavement -----------------------
_box("floor", 2.0, 2.0, 0.04, (0, 0, -0.04), mat_floor)
_box("pave_slab", 0.7, 0.7, 0.04, (0, 0, 0.02), mat_pave)

# --- ornate base : 3 stacked tiers
_box("base_tier1", 0.30, 0.30, 0.10, (0, 0, 0.05 + 0.04), mat_iron)
_box("base_tier2", 0.24, 0.24, 0.08, (0, 0, 0.14 + 0.04), mat_iron)
_cyl("base_tier3", 0.10, 0.08, 0.08, 'Z', (0, 0, 0.22 + 0.04), mat_iron, segments=18)

# --- main central column (tapered) -----
COL_BASE_Z = 0.30
COL_H = 2.20
_cyl("column", 0.045, 0.030, COL_H, 'Z',
       (0, 0, COL_BASE_Z + COL_H/2), mat_iron, segments=18)
# 3 decorative rings on the column (small horizontal disks)
for k, rz in enumerate((0.10, COL_H * 0.50, COL_H - 0.15)):
    R = 0.055 - k * 0.005
    _cyl(f"col_ring_{k}", R, R, 0.012, 'Z',
           (0, 0, COL_BASE_Z + rz), mat_brass, segments=18)

# --- horizontal scroll arm node : at the top of the column ---
NODE_Z = COL_BASE_Z + COL_H - 0.20
# central decorative ball
_sphere("col_node", 0.05, (0, 0, NODE_Z), mat_iron)

# --- 2 S-shaped scroll arms, one on -X and one on +X -----
# Each arm is approximated by 4 short curved cylinder segments forming an
# S-curve : starts horizontal, curves down, then curves up and out.
def make_scroll_arm(name, sign):
    """sign = -1 (left, -X) or +1 (right, +X)."""
    # control points (in local frame, origin = node) along the S
    pts = [
        (0.0,         0, 0.0),
        (sign * 0.12, 0, -0.02),
        (sign * 0.20, 0, -0.12),
        (sign * 0.32, 0, -0.06),
        (sign * 0.40, 0, +0.04),
    ]
    for k in range(len(pts) - 1):
        p0 = mathutils.Vector(pts[k])
        p1 = mathutils.Vector(pts[k+1])
        mid = (p0 + p1) * 0.5
        d = p1 - p0
        L = d.length
        seg = _cyl(f"{name}_seg_{k}", 0.014, 0.012, L, 'Z', (0,0,0), mat_iron, segments=12)
        seg.location = (0 + mid.x, 0 + mid.y, NODE_Z + mid.z)
        direction = d.normalized()
        seg.rotation_mode = 'QUATERNION'
        seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)
    # decorative scroll curl at the inner end (a small brass sphere)
    _sphere(f"{name}_scroll_inner", 0.014,
              (sign * 0.04, 0, NODE_Z - 0.02), mat_brass)
    # end ring where the lantern hangs (at the outer end of the arm)
    end_pt = pts[-1]
    _cyl(f"{name}_end_ring", 0.024, 0.024, 0.018, 'Z',
           (sign * end_pt[0], 0, NODE_Z + end_pt[2]), mat_iron, segments=14)
    return (sign * end_pt[0], NODE_Z + end_pt[2])

LEFT_END = make_scroll_arm("arm_L", -1)
RIGHT_END = make_scroll_arm("arm_R", +1)

# --- lantern builder : caged glass box with bulb inside ---
def make_lantern(name, x, z_top):
    """Build a caged lantern hanging from (x, 0, z_top). Returns (bulb_mat,
    halo_mat) so we can animate them per-lantern... but here we share the
    global mats so just return None."""
    # short hanging cylinder (chain attachment)
    _cyl(f"{name}_chain", 0.005, 0.005, 0.06, 'Z',
           (x, 0, z_top - 0.03), mat_iron, segments=10)
    # top cap (small chrome/brass dome)
    LANTERN_W = 0.10
    LANTERN_H = 0.18
    LANTERN_Z = z_top - 0.06 - LANTERN_H/2
    _cyl(f"{name}_top_cap", LANTERN_W * 0.60, LANTERN_W * 0.55, 0.020, 'Z',
           (x, 0, LANTERN_Z + LANTERN_H/2 + 0.010), mat_brass, segments=14)
    # 4 vertical iron bars (the cage frame)
    for sx_off in (-1, +1):
        for sy_off in (-1, +1):
            _cyl(f"{name}_bar_{sx_off}_{sy_off}",
                   0.004, 0.004, LANTERN_H + 0.01, 'Z',
                   (x + sx_off * LANTERN_W/2, sy_off * LANTERN_W/2, LANTERN_Z),
                   mat_iron, segments=8)
    # 4 horizontal top rails
    for sy_off in (-1, +1):
        _cyl(f"{name}_top_X_{sy_off}",
               LANTERN_W, 0.004 * 0.5, 0.004, 'X',  # use depth as size hack
               (x, sy_off * LANTERN_W/2, LANTERN_Z + LANTERN_H/2),
               mat_iron, segments=8)
        _cyl(f"{name}_top_Y_{sy_off}",
               LANTERN_W, 0.004 * 0.5, 0.004, 'Y',
               (x + sy_off * LANTERN_W/2, 0, LANTERN_Z + LANTERN_H/2),
               mat_iron, segments=8)
    # 4 horizontal bottom rails
    for sy_off in (-1, +1):
        _cyl(f"{name}_bot_X_{sy_off}",
               LANTERN_W, 0.004 * 0.5, 0.004, 'X',
               (x, sy_off * LANTERN_W/2, LANTERN_Z - LANTERN_H/2),
               mat_iron, segments=8)
        _cyl(f"{name}_bot_Y_{sy_off}",
               LANTERN_W, 0.004 * 0.5, 0.004, 'Y',
               (x + sy_off * LANTERN_W/2, 0, LANTERN_Z - LANTERN_H/2),
               mat_iron, segments=8)
    # 4 glass panes (one per face, slightly inside the cage)
    PANE_T = 0.003
    for axis_kind in ('+X', '-X', '+Y', '-Y'):
        if axis_kind == '+X':
            _box(f"{name}_glass_pX", PANE_T, LANTERN_W * 0.92, LANTERN_H * 0.92,
                   (x + LANTERN_W/2 - PANE_T, 0, LANTERN_Z), mat_glass)
        elif axis_kind == '-X':
            _box(f"{name}_glass_mX", PANE_T, LANTERN_W * 0.92, LANTERN_H * 0.92,
                   (x - LANTERN_W/2 + PANE_T, 0, LANTERN_Z), mat_glass)
        elif axis_kind == '+Y':
            _box(f"{name}_glass_pY", LANTERN_W * 0.92, PANE_T, LANTERN_H * 0.92,
                   (x, LANTERN_W/2 - PANE_T, LANTERN_Z), mat_glass)
        else:
            _box(f"{name}_glass_mY", LANTERN_W * 0.92, PANE_T, LANTERN_H * 0.92,
                   (x, -LANTERN_W/2 + PANE_T, LANTERN_Z), mat_glass)
    # bulb (emissive sphere inside)
    _sphere(f"{name}_bulb", 0.024, (x, 0, LANTERN_Z), mat_bulb)
    # halo (a slightly larger semi-transparent emissive sphere around the
    # bulb, gives "fog/glow" effect)
    _sphere(f"{name}_halo", 0.060, (x, 0, LANTERN_Z), mat_halo,
              scale=(1.0, 1.0, 1.2))
    # roof finial (small brass cone above the lantern)
    _cyl(f"{name}_finial", 0.020, 0.001, 0.040, 'Z',
           (x, 0, LANTERN_Z + LANTERN_H/2 + 0.025), mat_brass, segments=12)
    return LANTERN_Z

make_lantern("lantern_L", LEFT_END[0], LEFT_END[1])
make_lantern("lantern_R", RIGHT_END[0], RIGHT_END[1])

# --- crown finial on top of column -----
COL_TOP_Z = COL_BASE_Z + COL_H
_cyl("crown_disc", 0.030, 0.020, 0.030, 'Z',
       (0, 0, COL_TOP_Z + 0.020), mat_brass, segments=14)
_sphere("crown_ball", 0.024, (0, 0, COL_TOP_Z + 0.060), mat_brass)
# small spike on top
_cyl("crown_spike", 0.005, 0.001, 0.060, 'Z',
       (0, 0, COL_TOP_Z + 0.100), mat_brass, segments=8)

# --- animation -----------------
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2

# Bulb : gentle gas-lamp flicker ~ 15 ± 4 strength
bsdf_b = mat_bulb.node_tree.nodes.get("Principled BSDF")
em_b = bsdf_b.inputs["Emission Strength"]
bsdf_h = mat_halo.node_tree.nodes.get("Principled BSDF")
em_h = bsdf_h.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    # primary slow pulse + secondary fast jitter
    val = 13.0 + 4.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 1.5))
    val += 1.5 * math.sin(2*math.pi*t * 7.0)
    em_b.default_value = max(5.0, val)
    em_h.default_value = max(0.3, val * 0.05)
    bpy.context.scene.frame_set(f)
    em_b.keyframe_insert(data_path="default_value", frame=f)
    em_h.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"LAMP_OK: {out_glb}", flush=True)
'''


def make_lamp(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_lamp_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "LAMP_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_lamp(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
