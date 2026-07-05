"""Procedural lighthouse with rotating light beam (Blender headless).

Rocky base + tapered tower with alternating red/white bands + glass lantern
room + roof dome + a long thin emissive beam that rotates around the tower
axis. The beam reveals the lighthouse silhouette while sweeping the scene.

CLI:
  python proc_lighthouse.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "lighthouse.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

def pbr_mat(name, color, metal, rough, emission=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if emission is not None:
            # Blender 4.x : "Emission Color" + "Emission Strength" inputs
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (*emission[0], 1.0)
                bsdf.inputs["Emission Strength"].default_value = emission[1]
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = (*emission[0], 1.0)
    return m

mat_rock   = pbr_mat("rock",          (0.30, 0.30, 0.32), 0.00, 0.85)
mat_white  = pbr_mat("white_band",    (0.92, 0.92, 0.90), 0.00, 0.45)
mat_red    = pbr_mat("red_band",      (0.70, 0.10, 0.10), 0.00, 0.40)
mat_glass  = pbr_mat("lantern_glass", (0.80, 0.80, 0.92), 0.00, 0.05)
mat_brass  = pbr_mat("brass_dome",    (0.86, 0.62, 0.20), 1.00, 0.28)
mat_beam   = pbr_mat("light_beam",    (1.00, 0.95, 0.55), 0.00, 0.10,
                       emission=((1.00, 0.95, 0.55), 3.0))
mat_water  = pbr_mat("water",         (0.05, 0.20, 0.30), 0.00, 0.15)

def _cyl(name, R1, R2, depth, location, mat):
    """Tapered cylinder along Z, optionally tapered (R1 bottom -> R2 top)."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=48,
                            radius1=R1, radius2=R2, depth=depth)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

def _hemisphere(name, R, location, mat):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=R)
    # delete lower half
    to_del = [v for v in bm.verts if v.co.z < -1e-6]
    bmesh.ops.delete(bm, geom=to_del, context='VERTS')
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

# --- water + rock plinth ---------------------------------------------------
_box("water", 4.0, 4.0, 0.04, (0, 0, -0.10), mat_water)
# Rocky base : 3 stacked irregular discs (just stacked cylinders for simplicity)
_cyl("rock_base_low", 0.80, 0.72, 0.18, (0, 0, 0.0),    mat_rock)
_cyl("rock_base_mid", 0.65, 0.55, 0.14, (0, 0, 0.16),   mat_rock)

# --- tower : tapered cylinder + alternating bands -------------------------
TOWER_BASE_R = 0.42
TOWER_TOP_R  = 0.30
TOWER_H      = 1.80
TOWER_Z0     = 0.30  # tower base above the rocks
TOWER_TOP_Z  = TOWER_Z0 + TOWER_H

# Build the body as a single tapered cylinder (covered by 4 alternating bands
# of slightly larger radius for visual contrast)
_cyl("tower_body", TOWER_BASE_R, TOWER_TOP_R, TOWER_H,
       (0, 0, TOWER_Z0 + TOWER_H/2), mat_white)

N_BANDS = 4
BAND_H = TOWER_H / N_BANDS
for i in range(N_BANDS):
    if i % 2 == 1:
        # Red band : a slightly wider cylinder section sitting on the tower
        # at fraction i / N_BANDS up.
        z0 = TOWER_Z0 + i * BAND_H
        z1 = z0 + BAND_H
        r0 = TOWER_BASE_R + (TOWER_TOP_R - TOWER_BASE_R) * (i / N_BANDS)
        r1 = TOWER_BASE_R + (TOWER_TOP_R - TOWER_BASE_R) * ((i+1) / N_BANDS)
        # 2 % wider so the band visually sits over the white body
        _cyl(f"tower_band_red_{i}", r0 * 1.02, r1 * 1.02, BAND_H,
               (0, 0, (z0 + z1) / 2), mat_red)

# --- gallery walkway at the top of the tower body -------------------------
_cyl("gallery_floor", TOWER_TOP_R * 1.35, TOWER_TOP_R * 1.35, 0.04,
       (0, 0, TOWER_TOP_Z + 0.02), mat_brass)
# 8 small vertical balustrade posts around the gallery
for k in range(12):
    a = k * 2 * math.pi / 12
    px = math.cos(a) * TOWER_TOP_R * 1.30
    py = math.sin(a) * TOWER_TOP_R * 1.30
    _cyl(f"baluster_{k}", 0.012, 0.012, 0.12, (px, py, TOWER_TOP_Z + 0.10), mat_brass)
# top railing ring
_cyl("railing", TOWER_TOP_R * 1.32, TOWER_TOP_R * 1.32, 0.018,
       (0, 0, TOWER_TOP_Z + 0.18), mat_brass)

# --- lantern room (glass cylinder + brass cap) ----------------------------
LANT_R = TOWER_TOP_R * 0.85
LANT_H = 0.30
LANT_Z = TOWER_TOP_Z + 0.20 + LANT_H / 2
_cyl("lantern_glass", LANT_R, LANT_R, LANT_H, (0, 0, LANT_Z), mat_glass)

# brass dome on top
DOME_R = LANT_R * 1.05
DOME_Z = LANT_Z + LANT_H / 2
_hemisphere("dome", DOME_R, (0, 0, DOME_Z), mat_brass)

# small finial on top of dome
_cyl("finial_post", 0.012, 0.012, 0.15, (0, 0, DOME_Z + DOME_R + 0.07), mat_brass)
# small sphere ball atop the finial
mesh_ball = bpy.data.meshes.new("finial_ball")
ball = bpy.data.objects.new("finial_ball", mesh_ball)
bpy.context.collection.objects.link(ball)
bm_tmp = bmesh.new()
bmesh.ops.create_uvsphere(bm_tmp, u_segments=14, v_segments=8, radius=0.025)
bm_tmp.to_mesh(mesh_ball); bm_tmp.free()
ball.location = (0, 0, DOME_Z + DOME_R + 0.16)
ball.data.materials.append(mat_brass)

# --- rotating light beam --------------------------------------------------
# The beam pivots around the vertical Z axis at the centre of the lantern
# room. We anchor it with an Empty parent.
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, LANT_Z))
beam_pivot = bpy.context.active_object
beam_pivot.name = "beam_pivot"

# Beam shape : long thin trapezoidal-ish cone extending out from the pivot
# along +X. We build it as a wide flat cone.
beam_mesh = bpy.data.meshes.new("light_beam_mesh")
beam_obj = bpy.data.objects.new("light_beam", beam_mesh)
bpy.context.collection.objects.link(beam_obj)
bm = bmesh.new()
# Cone of length 3.0 along Z (R1 small at origin, R2 wider at far end),
# then rotate it 90 deg around Y so it points along world +X.
bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=10,
                        radius1=0.03, radius2=0.18, depth=2.5)
bmesh.ops.translate(bm, vec=(0, 0, 2.5/2), verts=bm.verts)  # origin at near end
bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'Y'), verts=bm.verts)
bm.to_mesh(beam_mesh); bm.free()
beam_obj.data.materials.append(mat_beam)
beam_obj.parent = beam_pivot
beam_obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : beam_pivot rotates 1 full turn / 3 s --------------------
FPS = 30
DURATION = 3.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

beam_pivot.keyframe_insert("rotation_euler", frame=1)
beam_pivot.rotation_euler = (0, 0, 2 * math.pi)
beam_pivot.keyframe_insert("rotation_euler", frame=NFR)
if beam_pivot.animation_data and beam_pivot.animation_data.action:
    for fc in beam_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"LIGHTHOUSE_OK: {out_glb}", flush=True)
'''


def make_lighthouse(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_lh_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "LIGHTHOUSE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_lighthouse(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
