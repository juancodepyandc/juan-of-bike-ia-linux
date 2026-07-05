"""Procedural gear-train generator (Blender headless).

Builds 3 meshed gears (24 / 16 / 12 teeth) with synced opposite rotation.
Tooth counts give exact LCM(24,16,12)=48 -> A rotates 2 turns, B 3 turns,
C 4 turns per loop = perfect periodic 3 s animation. Pitch radii share the
same pitch (2*pi*R/N) so teeth mesh visually.

CLI:
  python proc_gear_train.py <output_glb>
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
import bpy, bmesh, math, sys

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "gear_train.glb"

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

mat_brass = pbr_mat("brass",          (0.86, 0.62, 0.20), 1.0, 0.28)
mat_steel = pbr_mat("steel_polished", (0.62, 0.64, 0.66), 1.0, 0.18)
mat_plate = pbr_mat("steel_plate",    (0.40, 0.40, 0.42), 1.0, 0.40)

# --- base plate ------------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0.43, 0, -0.10))
plate = bpy.context.active_object
plate.name = "base_plate"
plate.scale = (1.30, 0.80, 0.05)
bpy.ops.object.transform_apply(scale=True)
plate.data.materials.append(mat_plate)

# --- gear builder via bmesh (single mesh, no joins, no op cascades) -------
DEPTH = 0.06
TOOTH_H = 0.045
TOOTH_W = 0.040


def _add_box_local(bm, cx, cy, cz, hx, hy, hz, rad_x, rad_y, tan_x, tan_y):
    """Add an axis-rotated box to bmesh.
       cx,cy,cz : centre in mesh-local frame
       hx,hy,hz : half-extents along (radial, tangential, depth)
       rad_*, tan_* : unit radial / tangential vectors (in XY plane)
    """
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                vx = cx + sx*hx*rad_x + sy*hy*tan_x
                vy = cy + sx*hx*rad_y + sy*hy*tan_y
                vz = cz + sz*hz
                corners.append(bm.verts.new((vx, vy, vz)))
    bm.verts.ensure_lookup_table()
    c = corners  # idx by (sx,sy,sz) bits : 0=---,1=--+,2=-+-,3=-++,4=+--,5=+-+,6=++-,7=+++
    bm.faces.new((c[0], c[4], c[6], c[2]))  # bottom z=-
    bm.faces.new((c[1], c[3], c[7], c[5]))  # top    z=+
    bm.faces.new((c[0], c[1], c[5], c[4]))  # y=- (tangential -)
    bm.faces.new((c[2], c[6], c[7], c[3]))  # y=+
    bm.faces.new((c[0], c[2], c[3], c[1]))  # x=- (radial -)
    bm.faces.new((c[4], c[5], c[7], c[6]))  # x=+


def make_gear(name, teeth, R, mat, location):
    """Build a gear as a single mesh via bmesh: cylinder body + N rotated
    boxes (teeth) + central hub. Place the resulting object at `location`.
    Single mesh, single object, no joins -> no transform-apply pitfalls.
    """
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()

    # body cylinder, centred at mesh origin
    bmesh.ops.create_cone(bm,
        cap_ends=True, cap_tris=False, segments=96,
        radius1=R, radius2=R, depth=DEPTH)

    # teeth (axis-aligned rotation per i)
    hx, hy, hz = TOOTH_H * 0.5, TOOTH_W * 0.5, DEPTH * 0.46
    for i in range(teeth):
        a = i * 2 * math.pi / teeth
        rad_x, rad_y = math.cos(a), math.sin(a)
        tan_x, tan_y = -math.sin(a), math.cos(a)
        cx = rad_x * (R + hx)
        cy = rad_y * (R + hx)
        _add_box_local(bm, cx, cy, 0.0, hx, hy, hz, rad_x, rad_y, tan_x, tan_y)

    # central hub : a taller, thinner cylinder
    hub_offset = bmesh.ops.create_cone(bm,
        cap_ends=True, cap_tris=False, segments=24,
        radius1=R * 0.16, radius2=R * 0.16, depth=DEPTH * 1.5)
    # create_cone places the new geom centred at origin -- exactly what we want.

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- 3 gears (centres collinear so teeth mesh) -----------------------------
R_A, N_A = 0.30, 24
R_B, N_B = 0.20, 16
R_C, N_C = 0.15, 12

x_A = 0.0
x_B = x_A + R_A + R_B    # 0.50
x_C = x_B + R_B + R_C    # 0.85

# initial rotation phase to make teeth interlock cleanly
# Adjacent gears must have teeth offset by half a tooth pitch (so tooth fits
# in the gap). Computed per pair.
gear_A = make_gear("gear_A_brass",  N_A, R_A, mat_brass, (x_A, 0, 0))
gear_B = make_gear("gear_B_steel",  N_B, R_B, mat_steel, (x_B, 0, 0))
gear_C = make_gear("gear_C_brass",  N_C, R_C, mat_brass, (x_C, 0, 0))

# Phase offsets so teeth interlock at frame 1
gear_A.rotation_euler = (0, 0, 0)
gear_B.rotation_euler = (0, 0, math.pi / N_B)        # half-tooth shift
gear_C.rotation_euler = (0, 0, 0)                     # B already shifted -> C aligns naturally

# --- animation : LCM(24,16,12)=48 teeth advance per loop -------------------
# -> A=2 turns, B=3 turns (opposite direction), C=4 turns over 3 s.
FPS = 30
DURATION = 3.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

def animate_gear(g, total_turns_signed, base_phase=0.0):
    g.keyframe_insert("rotation_euler", frame=1)
    g.rotation_euler = (g.rotation_euler.x, g.rotation_euler.y,
                         base_phase + total_turns_signed * 2 * math.pi)
    g.keyframe_insert("rotation_euler", frame=NFR)
    if g.animation_data and g.animation_data.action:
        for fc in g.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# A : +2 turns (CCW)
animate_gear(gear_A, +2.0, base_phase=0.0)
# B : -3 turns (CW)
animate_gear(gear_B, -3.0, base_phase=math.pi / N_B)
# C : +4 turns (CCW)
animate_gear(gear_C, +4.0, base_phase=0.0)

# --- export ----------------------------------------------------------------
bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"GEARS_OK: {out_glb}", flush=True)
'''


def make_gear_train(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_gears_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "GEARS_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_gear_train(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
