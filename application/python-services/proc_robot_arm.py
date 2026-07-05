"""Procedural 6-DOF robotic arm (Blender headless, bmesh + parent empties).

6 revolute joints connecting 5 segments + an end-effector. Each joint is an
empty parented to the previous segment; each segment is a cylinder along
its parent's local +Z. Animation : each joint oscillates with a phase-shifted
sin (amplitude decreasing up the chain) so the arm sweeps a "reach"
trajectory in 3 s.

CLI:
  python proc_robot_arm.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "robot.glb"

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

mat_orange = pbr_mat("orange_industrial", (0.82, 0.40, 0.10), 0.10, 0.45)
mat_steel  = pbr_mat("steel_brushed",     (0.55, 0.57, 0.60), 1.00, 0.30)
mat_dark   = pbr_mat("dark_steel",        (0.18, 0.18, 0.20), 1.00, 0.42)
mat_yellow = pbr_mat("end_effector",      (0.95, 0.85, 0.10), 0.50, 0.30)

# --- base plate (ground anchor) --------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
plate = bpy.context.active_object
plate.name = "base_plate"
plate.scale = (0.80, 0.80, 0.06)
bpy.ops.object.transform_apply(scale=True)
plate.data.materials.append(mat_dark)

# --- helpers ---------------------------------------------------------------
def _cyl(name, R, length, mat):
    """Cylinder of radius R extending along +Z from 0 to length (origin at base)."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    # Build cylinder centred at origin, then translate so base is at z=0
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=48,
                            radius1=R, radius2=R, depth=length)
    bmesh.ops.translate(bm, vec=(0, 0, length / 2), verts=bm.verts)
    bm.to_mesh(mesh); bm.free()
    obj.data.materials.append(mat)
    return obj

def _sphere(name, R, mat):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.data.materials.append(mat)
    return obj

# --- arm hierarchy ---------------------------------------------------------
# Each joint is an Empty whose rotation drives the segment + everything above.
# Segment i is parented to joint_i and visually extends from 0 to L_i in
# joint_i's local +Z. Joint_(i+1) is parented to joint_i and translated
# (0,0,L_i) so it sits at the segment's tip.

SEGS = [
    # (L, R, mat, joint_axis, amplitude_deg, phase_rad)
    (0.40, 0.08, mat_orange, 'Z', 70.0,  0.00),               # base yaw
    (0.45, 0.07, mat_steel,  'X', 50.0,  math.pi / 3),        # shoulder pitch
    (0.35, 0.06, mat_orange, 'X', 65.0,  2 * math.pi / 3),    # elbow pitch
    (0.22, 0.05, mat_steel,  'X', 45.0,  math.pi),            # wrist pitch
    (0.12, 0.045, mat_orange,'Z', 60.0,  4 * math.pi / 3),    # wrist yaw
    (0.10, 0.04, mat_yellow, 'Y', 90.0,  5 * math.pi / 3),    # end roll (tool mount)
]

joints = []
segments = []
parent_joint = None  # for the first joint: parent to plate

for i, (L, R, mat, axis, amp, phase) in enumerate(SEGS):
    # joint empty
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
    jt = bpy.context.active_object
    jt.name = f"joint_{i+1}"
    if parent_joint is not None:
        jt.parent = parent_joint
        jt.matrix_parent_inverse = parent_joint.matrix_world.inverted()
        # Translate to the tip of the previous segment in the previous joint's local +Z
        jt.location = (0, 0, SEGS[i-1][0])
    joints.append(jt)

    # joint visualisation : a small sphere at the joint
    sph = _sphere(f"joint_{i+1}_pivot", R * 1.15, mat_dark)
    sph.parent = jt
    sph.matrix_parent_inverse = jt.matrix_world.inverted()
    segments.append(sph)

    # segment cylinder (extends +Z by L)
    seg = _cyl(f"segment_{i+1}", R, L, mat)
    seg.parent = jt
    seg.matrix_parent_inverse = jt.matrix_world.inverted()
    segments.append(seg)

    parent_joint = jt

# End-effector visual : a small box at the tip of the last segment
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
ee = bpy.context.active_object
ee.name = "end_effector"
ee.scale = (0.06, 0.06, 0.06)
bpy.ops.object.transform_apply(scale=True)
ee.data.materials.append(mat_yellow)
ee.parent = parent_joint
ee.matrix_parent_inverse = parent_joint.matrix_world.inverted()
ee.location = (0, 0, SEGS[-1][0] + 0.05)

# --- animation -------------------------------------------------------------
FPS = 30
DURATION = 3.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
for i, (L, R, mat, axis, amp, phase) in enumerate(SEGS):
    jt = joints[i]
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        angle = math.radians(amp) * math.sin(2 * math.pi * t + phase)
        bpy.context.scene.frame_set(f)
        rx, ry, rz = jt.rotation_euler
        if axis == 'X':
            jt.rotation_euler = (angle, ry, rz)
        elif axis == 'Y':
            jt.rotation_euler = (rx, angle, rz)
        else:  # Z
            jt.rotation_euler = (rx, ry, angle)
        jt.keyframe_insert("rotation_euler", frame=f)
    if jt.animation_data and jt.animation_data.action:
        for fc in jt.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"ROBOT_OK: {out_glb}", flush=True)
'''


def make_robot(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_robot_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "ROBOT_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_robot(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
