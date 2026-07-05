"""Procedural slider-crank piston mechanism (Blender headless).

Kinematics : crankshaft (rotating around X axis) drives a connecting rod
which drives a piston sliding along Z. Exact slider-crank equations :

  pin_y = -R * sin(theta)
  pin_z = +R * cos(theta)
  z_p   = pin_z + sqrt(L^2 - pin_y^2)              piston pin Z (top)

Crank rotates one full turn per loop ; rod and piston positions are
key-framed every 2 frames so the motion is smooth.

CLI:
  python proc_piston_crank.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "piston.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"

def pbr_mat(name, color, metal, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
    return m

mat_steel       = pbr_mat("steel_polished", (0.62, 0.64, 0.66), 1.0, 0.18)
mat_brass       = pbr_mat("brass",          (0.86, 0.62, 0.20), 1.0, 0.28)
mat_steel_dark  = pbr_mat("steel_dark",     (0.30, 0.32, 0.34), 1.0, 0.40)
mat_red         = pbr_mat("red_paint",      (0.62, 0.10, 0.10), 0.0, 0.45)

R_CRANK = 0.30
L_ROD   = 0.85
PIST_R  = 0.18
PIST_H  = 0.16

def _cyl_obj(name, R, depth, axis, location, mat):
    """Cylinder oriented along given world axis ('X','Y','Z'), placed at location."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=64,
                            radius1=R, radius2=R, depth=depth)
    if axis == 'X':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'Y'), verts=bm.verts)
    elif axis == 'Y':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'X'), verts=bm.verts)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

def _cyl_local_obj(name, R, depth, axis, mat):
    """Cylinder oriented along axis, origin at mesh center (location=0)."""
    return _cyl_obj(name, R, depth, axis, (0,0,0), mat)

# --- base frame ------------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.10))
plate = bpy.context.active_object
plate.name = "base_plate"
plate.scale = (1.20, 0.80, 0.04)
bpy.ops.object.transform_apply(scale=True)
plate.data.materials.append(mat_steel_dark)

# Two vertical guide posts (suggest the cylinder bore)
for x_off in (-PIST_R - 0.04, +PIST_R + 0.04):
    p = _cyl_obj(f"guide_{'L' if x_off<0 else 'R'}", 0.025, 1.10, 'Z',
                  (x_off, 0, R_CRANK + 0.40), mat_steel_dark)

# --- crank assembly (pivot empty + shaft + offset disc + crank pin) -------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
crank_pivot = bpy.context.active_object
crank_pivot.name = "crank_pivot"

shaft = _cyl_obj("crank_shaft", 0.05, 0.70, 'X', (0, 0, 0), mat_steel_dark)
shaft.parent = crank_pivot
shaft.matrix_parent_inverse = crank_pivot.matrix_world.inverted()

# Crank disc (counterweight): a thick disc offset along X with the pin sticking out
crank_disc = _cyl_obj("crank_disc", 0.12, 0.06, 'X', (0.20, 0, 0), mat_red)
crank_disc.parent = crank_pivot
crank_disc.matrix_parent_inverse = crank_pivot.matrix_world.inverted()

# Crank pin : protrudes from the disc, offset by R_CRANK along +Z (initially)
crank_pin = _cyl_obj("crank_pin", 0.035, 0.12, 'X', (0.25, 0, R_CRANK), mat_brass)
crank_pin.parent = crank_pivot
crank_pin.matrix_parent_inverse = crank_pivot.matrix_world.inverted()

# --- piston (slides along Z) ----------------------------------------------
piston = _cyl_obj("piston", PIST_R, PIST_H, 'Z', (0, 0, R_CRANK + L_ROD - PIST_H/2), mat_brass)
piston_top = _cyl_obj("piston_cap", PIST_R * 1.05, 0.02, 'Z',
                       (0, 0, R_CRANK + L_ROD + 0.02), mat_steel_dark)

# --- connecting rod (vertical local +Z, length L_ROD) ---------------------
rod = _cyl_local_obj("connecting_rod", 0.022, L_ROD, 'Z', mat_steel)
rod.data.materials.clear()
rod.data.materials.append(mat_steel)
# small bulge at each end : just leave the cylinder simple

# --- animation ------------------------------------------------------------
FPS = 30
DURATION = 3.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

def piston_pin_z(theta):
    pin_y = -R_CRANK * math.sin(theta)
    pin_z = +R_CRANK * math.cos(theta)
    return pin_z + math.sqrt(L_ROD**2 - pin_y**2)

KEY_EVERY = 2
for f in range(1, NFR + 1, KEY_EVERY):
    theta = 2 * math.pi * (f - 1) / NFR
    bpy.context.scene.frame_set(f)

    # crank rotates around X
    crank_pivot.rotation_euler = (theta, 0, 0)
    crank_pivot.keyframe_insert("rotation_euler", frame=f)

    # piston slides along Z (piston body centre = pin Z - PIST_H/2)
    z_p = piston_pin_z(theta)
    piston.location = (0, 0, z_p - PIST_H/2)
    piston.keyframe_insert("location", frame=f)
    piston_top.location = (0, 0, z_p + 0.02)
    piston_top.keyframe_insert("location", frame=f)

    # rod position + rotation around X
    pin_y = -R_CRANK * math.sin(theta)
    pin_z = +R_CRANK * math.cos(theta)
    rod.location = (0, pin_y / 2, (z_p + pin_z) / 2)
    rod_angle = math.atan2(pin_y, z_p - pin_z)
    rod.rotation_euler = (rod_angle, 0, 0)
    rod.keyframe_insert("location", frame=f)
    rod.keyframe_insert("rotation_euler", frame=f)

# LINEAR interp on all keyframes
for o in (crank_pivot, piston, piston_top, rod):
    if o.animation_data and o.animation_data.action:
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"PISTON_OK: {out_glb}", flush=True)
'''


def make_piston(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_piston_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "PISTON_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_piston(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
