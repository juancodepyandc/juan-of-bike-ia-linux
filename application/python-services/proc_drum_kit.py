"""Procedural 5-piece drum kit (Blender headless).

Kick + snare + 2 toms + floor tom + hi-hat (pair of cymbals) + crash +
ride + stands. Animation : a different drum bobs each beat over a 4 s
loop suggesting a drum pattern.

CLI:
  python proc_drum_kit.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "drums.glb"

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

mat_shell_red  = pbr_mat("drum_red",   (0.62, 0.08, 0.08), 0.10, 0.30)
mat_skin       = pbr_mat("drum_skin",  (0.92, 0.90, 0.85), 0.05, 0.40)
mat_chrome     = pbr_mat("chrome",     (0.78, 0.80, 0.82), 1.00, 0.18)
mat_brass      = pbr_mat("brass_cym",  (0.86, 0.62, 0.20), 1.00, 0.20)
mat_stick      = pbr_mat("stick_wood", (0.55, 0.40, 0.20), 0.00, 0.55)
mat_floor      = pbr_mat("floor",      (0.20, 0.20, 0.22), 0.00, 0.85)
mat_throne     = pbr_mat("throne",     (0.10, 0.10, 0.12), 0.30, 0.35)

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

def _drum(name, R, H, axis, location):
    """Build a drum : shell + 2 skin discs at the ends + 6 chrome lugs."""
    pv_loc = location
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=pv_loc)
    pv = bpy.context.active_object
    pv.name = f"{name}_pivot"
    shell = _cyl(f"{name}_shell", R, R, H, axis, (0, 0, 0), mat_shell_red)
    shell.parent = pv
    shell.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # 2 skin discs (flat at the ends)
    half = H / 2 - 0.005
    for sign in (-1, +1):
        skin_loc = (sign * half, 0, 0) if axis == 'X' else \
                    (0, sign * half, 0) if axis == 'Y' else \
                    (0, 0, sign * half)
        sk = _cyl(f"{name}_skin_{sign}", R * 0.98, R * 0.98, 0.005, axis,
                    skin_loc, mat_skin)
        sk.parent = pv
        sk.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # 6 chrome lugs around the rim
    for k in range(6):
        a = k * 2 * math.pi / 6
        if axis == 'Z':
            lug_pos = (math.cos(a) * R, math.sin(a) * R, 0)
        elif axis == 'X':
            lug_pos = (0, math.cos(a) * R, math.sin(a) * R)
        else:
            lug_pos = (math.cos(a) * R, 0, math.sin(a) * R)
        lug = _cyl(f"{name}_lug_{k}", 0.008, 0.008, H * 0.85,
                     axis, lug_pos, mat_chrome)
        lug.parent = pv
        lug.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    return pv

# --- floor + throne ---------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
fl = bpy.context.active_object
fl.name = "floor"
fl.scale = (2.5, 2.5, 0.04); bpy.ops.object.transform_apply(scale=True)
fl.data.materials.append(mat_floor)

# throne (drummer's stool)
_cyl("throne_seat", 0.16, 0.14, 0.04, 'Z', (-0.70, 0, 0.55), mat_throne)
_cyl("throne_post", 0.025, 0.025, 0.55, 'Z', (-0.70, 0, 0.275), mat_chrome)
for k in range(3):
    a = k * 2 * math.pi / 3
    leg_end_x = math.cos(a) * 0.20
    leg_end_y = math.sin(a) * 0.20
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.70 + leg_end_x/2, leg_end_y/2, 0.025))
    leg = bpy.context.active_object
    leg.name = f"throne_leg_{k}"
    leg.scale = (math.hypot(leg_end_x, 0), 0.020, 0.025)
    bpy.ops.object.transform_apply(scale=True)
    leg.rotation_euler = (0, 0, a)
    leg.data.materials.append(mat_chrome)

# --- kick drum (large, lying on its side) ----------------
kick = _drum("kick", 0.30, 0.32, 'Y', (0.10, 0.10, 0.32))

# --- snare (on stand) -----------------------------------
snare = _drum("snare", 0.15, 0.08, 'Z', (-0.22, 0.15, 0.62))
# snare stand (3 legs + central post)
_cyl("snare_post", 0.018, 0.018, 0.55, 'Z', (-0.22, 0.15, 0.30), mat_chrome)
for k in range(3):
    a = k * 2 * math.pi / 3
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.22 + math.cos(a) * 0.10,
                                                       0.15 + math.sin(a) * 0.10,
                                                       0.025))
    leg = bpy.context.active_object
    leg.name = f"snare_leg_{k}"
    leg.scale = (0.22, 0.015, 0.020)
    bpy.ops.object.transform_apply(scale=True)
    leg.rotation_euler = (0, 0, a)
    leg.data.materials.append(mat_chrome)

# --- 2 toms on top of the kick --------------------------
tom_hi = _drum("tom_hi", 0.10, 0.12, 'Z', (-0.05, 0.0, 0.70))
tom_lo = _drum("tom_lo", 0.13, 0.14, 'Z', (+0.18, 0.0, 0.68))

# --- floor tom (on the right) ----------------------------
ftom = _drum("floor_tom", 0.16, 0.18, 'Z', (0.45, 0.20, 0.40))
# 3 floor tom legs (chrome rods)
for k in range(3):
    a = k * 2 * math.pi / 3
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.45 + math.cos(a) * 0.18,
                                                       0.20 + math.sin(a) * 0.18,
                                                       0.18))
    leg = bpy.context.active_object
    leg.name = f"ftom_leg_{k}"
    leg.scale = (0.025, 0.025, 0.40)
    bpy.ops.object.transform_apply(scale=True)
    leg.data.materials.append(mat_chrome)

# --- hi-hat (2 cymbals on stand) ------------------------
HH_X, HH_Y, HH_Z = -0.55, 0.05, 0.80
_cyl("hh_post", 0.018, 0.018, HH_Z + 0.02, 'Z', (HH_X, HH_Y, HH_Z/2), mat_chrome)
_cyl("hh_bottom", 0.13, 0.13, 0.008, 'Z', (HH_X, HH_Y, HH_Z), mat_brass)
_cyl("hh_top", 0.13, 0.13, 0.008, 'Z', (HH_X, HH_Y, HH_Z + 0.025), mat_brass)
# hi-hat tripod
for k in range(3):
    a = k * 2 * math.pi / 3
    bpy.ops.mesh.primitive_cube_add(size=1, location=(HH_X + math.cos(a) * 0.10,
                                                       HH_Y + math.sin(a) * 0.10,
                                                       0.025))
    leg = bpy.context.active_object
    leg.name = f"hh_leg_{k}"
    leg.scale = (0.20, 0.015, 0.020)
    bpy.ops.object.transform_apply(scale=True)
    leg.rotation_euler = (0, 0, a)
    leg.data.materials.append(mat_chrome)

# --- crash + ride cymbals --------------------------------
def _cymbal_stand(name, cx, cy, top_z, R_cym):
    _cyl(f"{name}_post", 0.020, 0.020, top_z + 0.02, 'Z',
           (cx, cy, top_z/2), mat_chrome)
    _cyl(f"{name}_cymbal", R_cym, R_cym, 0.006, 'Z',
           (cx, cy, top_z), mat_brass)
    for k in range(3):
        a = k * 2 * math.pi / 3
        bpy.ops.mesh.primitive_cube_add(size=1, location=(cx + math.cos(a) * 0.12,
                                                           cy + math.sin(a) * 0.12,
                                                           0.025))
        leg = bpy.context.active_object
        leg.name = f"{name}_leg_{k}"
        leg.scale = (0.24, 0.015, 0.020)
        bpy.ops.object.transform_apply(scale=True)
        leg.rotation_euler = (0, 0, a)
        leg.data.materials.append(mat_chrome)

_cymbal_stand("crash", -0.20, -0.30, 1.10, 0.20)
_cymbal_stand("ride", 0.60, -0.20, 1.00, 0.24)

# --- 2 drumsticks held just above snare/toms ------------
def _drumstick(name, x, y, z, yaw):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    s = bpy.context.active_object
    s.name = name
    s.scale = (0.30, 0.012, 0.012); bpy.ops.object.transform_apply(scale=True)
    s.rotation_euler = (0, math.radians(-25), yaw)
    s.data.materials.append(mat_stick)
    return s

stick_L = _drumstick("stick_L", -0.10, 0.15, 0.85, math.radians(20))
stick_R = _drumstick("stick_R", +0.10, 0.15, 0.85, math.radians(-20))

# --- animation : drum pivots bob when struck -----------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 1

# Drum pattern : 8 hits per loop
# beat times in [0,1] : kick on 0, 0.5 ; snare on 0.25, 0.75 ;
# tom_hi on 0.125, 0.625 ; tom_lo on 0.375, 0.875
hits = [
    (0.000, kick,    0.020),
    (0.125, tom_hi,  0.012),
    (0.250, snare,   0.012),
    (0.375, tom_lo,  0.014),
    (0.500, kick,    0.020),
    (0.625, tom_hi,  0.012),
    (0.750, snare,   0.012),
    (0.875, tom_lo,  0.014),
]

# bob each drum : drop by drop_amt at strike time, return over 0.10 s
for (t_strike, drum_pv, drop_amt) in hits:
    base_z = drum_pv.location.z
    f_pre  = max(1, int((t_strike - 0.02) * NFR))
    f_hit  = max(1, int(t_strike * NFR))
    f_back = min(NFR, int((t_strike + 0.08) * NFR))
    bpy.context.scene.frame_set(f_pre)
    drum_pv.location.z = base_z
    drum_pv.keyframe_insert("location", frame=f_pre)
    bpy.context.scene.frame_set(f_hit)
    drum_pv.location.z = base_z - drop_amt
    drum_pv.keyframe_insert("location", frame=f_hit)
    bpy.context.scene.frame_set(f_back)
    drum_pv.location.z = base_z
    drum_pv.keyframe_insert("location", frame=f_back)

# LINEAR keys
for pv in [kick, snare, tom_hi, tom_lo, ftom]:
    if pv.animation_data and pv.animation_data.action:
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"DRUMS_OK: {out_glb}", flush=True)
'''


def make_drums(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_drums_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "DRUMS_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_drums(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
