"""Procedural studio microphone (Blender headless).

Heavy round floor base + vertical chrome pole + horizontal boom arm with
counterweight + suspension shock-mount oval ring + 4 elastic bands +
cardioid mic capsule (cylindrical body + grille head) + pop filter
(round mesh frame + thin gooseneck). Animation : whole shock-mount +
mic assembly oscillates ±2 deg around the boom-arm pivot for a subtle
"hanging on elastics" feel.

CLI:
  python proc_studio_microphone.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "mic.glb"

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

mat_floor    = pbr_mat("floor",      (0.12, 0.12, 0.14), 0.00, 0.90)
mat_base     = pbr_mat("base_iron",  (0.08, 0.08, 0.09), 0.85, 0.30)
mat_chrome   = pbr_mat("chrome",     (0.78, 0.80, 0.83), 1.00, 0.18)
mat_dark     = pbr_mat("dark_metal", (0.10, 0.10, 0.11), 0.85, 0.30)
mat_grille   = pbr_mat("grille",     (0.55, 0.55, 0.58), 1.00, 0.45)
mat_capsule  = pbr_mat("capsule",    (0.18, 0.18, 0.20), 0.65, 0.35)
mat_elastic  = pbr_mat("elastic",    (0.55, 0.45, 0.18), 0.05, 0.55)
mat_mesh     = pbr_mat("pop_mesh",   (0.10, 0.10, 0.12), 0.10, 0.55, alpha=0.55)
mat_ring     = pbr_mat("pop_ring",   (0.20, 0.20, 0.22), 0.85, 0.30)
mat_led      = pbr_mat("led_red",    (0.95, 0.18, 0.12), 0.00, 0.10,
                          emission=((1.00, 0.20, 0.10), 8.0))
mat_cable    = pbr_mat("cable",      (0.06, 0.06, 0.07), 0.05, 0.65)

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

def _sphere(name, R, location, mat, u=18, v=12):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=R)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

def _torus(name, R_major, R_minor, location, mat, ms=24, mn=10, axis='Z'):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=False, segments=mn, radius=R_minor)
    # build via spin on the Z=0 plane, then transform the result by axis
    # using a simpler approach : build torus directly using a math param
    bm.free()
    mesh2 = bpy.data.meshes.new(name + "_data")
    bm = bmesh.new()
    verts = []
    for i in range(ms):
        ai = 2 * math.pi * i / ms
        ring = []
        for j in range(mn):
            aj = 2 * math.pi * j / mn
            x = (R_major + R_minor * math.cos(aj)) * math.cos(ai)
            y = (R_major + R_minor * math.cos(aj)) * math.sin(ai)
            z = R_minor * math.sin(aj)
            ring.append(bm.verts.new((x, y, z)))
        verts.append(ring)
    bm.verts.ensure_lookup_table()
    for i in range(ms):
        for j in range(mn):
            i2 = (i + 1) % ms
            j2 = (j + 1) % mn
            bm.faces.new([verts[i][j], verts[i2][j], verts[i2][j2], verts[i][j2]])
    if axis == 'X':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'Y'), verts=bm.verts)
    elif axis == 'Y':
        bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.pi/2, 4, 'X'), verts=bm.verts)
    bm.to_mesh(mesh); bm.free()
    obj.location = location
    obj.data.materials.append(mat)
    return obj

# --- studio floor --------------------------------------------------
_box("floor", 2.2, 2.2, 0.04, (0, 0, -0.04), mat_floor)

# --- heavy round base ---------------------------------------------
BASE_R = 0.28
_cyl("base_disc",  BASE_R, BASE_R, 0.045, 'Z', (0, 0, 0.0225), mat_base, segments=40)
_cyl("base_rim",   BASE_R * 0.95, BASE_R * 0.95, 0.012, 'Z',
       (0, 0, 0.045 + 0.006), mat_chrome, segments=40)

# --- vertical pole (chrome cylinder, ~1.25 m tall) ----------------
POLE_H = 1.25
POLE_Z = 0.045 + POLE_H/2
_cyl("pole",       0.018, 0.018, POLE_H, 'Z', (0, 0, POLE_Z), mat_chrome, segments=20)
# height-adjust collar (small dark ring at mid-pole)
_cyl("collar",     0.024, 0.024, 0.025, 'Z', (0, 0, 0.045 + POLE_H * 0.55), mat_dark, segments=20)
_cyl("collar_screw", 0.006, 0.006, 0.035, 'X',
       (0.024, 0, 0.045 + POLE_H * 0.55), mat_chrome)

# --- boom-arm pivot at top of pole (empty so we can hang the whole mic) ---
PIVOT_Z = 0.045 + POLE_H
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, PIVOT_Z))
boom_pivot = bpy.context.active_object
boom_pivot.name = "boom_pivot"

# pivot knuckle (a sphere wrapping the pivot)
_sphere("boom_knuckle", 0.035, (0, 0, PIVOT_Z), mat_dark)

# horizontal boom arm pointing +X
BOOM_LEN = 0.55
boom_arm = _cyl("boom_arm", 0.014, 0.014, BOOM_LEN, 'X',
                  (BOOM_LEN/2, 0, 0), mat_chrome, segments=20)
boom_arm.parent = boom_pivot
boom_arm.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# counterweight at the rear (-X end)
counterweight = _cyl("counterweight", 0.045, 0.045, 0.08, 'X',
                       (-0.05, 0, 0), mat_dark)
counterweight.parent = boom_pivot
counterweight.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# end knuckle at the front of the boom (+X end)
end_knuckle = _sphere("boom_end_knuckle", 0.025, (BOOM_LEN, 0, 0), mat_dark)
end_knuckle.parent = boom_pivot
end_knuckle.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- shock-mount pivot : hangs off the front of the boom, points down ---
# The shock-mount is what oscillates ; it's parented to the boom_pivot
# AND has its own sub-pivot so we can keyframe a small ±2 deg sway.
MOUNT_HOME_X = BOOM_LEN
MOUNT_HOME_Z = -0.12
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(MOUNT_HOME_X, 0, MOUNT_HOME_Z))
mount_pivot = bpy.context.active_object
mount_pivot.name = "mount_pivot"
mount_pivot.parent = boom_pivot
mount_pivot.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# yoke (a short vertical bar from boom_end_knuckle down to the shock-mount)
yoke = _cyl("yoke", 0.010, 0.010, 0.12, 'Z', (MOUNT_HOME_X, 0, -0.06), mat_dark)
yoke.parent = boom_pivot
yoke.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- shock-mount oval ring (a torus in the YZ plane) --------------
# axis='X' gives a ring whose normal is along +X, i.e. it sits like a
# vertical oval facing the +X end of the boom — exactly what a real
# shock-mount looks like from the side.
RING_R = 0.085
ring = _torus("mount_ring", RING_R, 0.006, (0, 0, 0), mat_dark,
                ms=28, mn=8, axis='X')
ring.parent = mount_pivot
ring.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 4 elastic suspension bands : go from ring to a small inner cradle
# (a smaller ring inside). Represented as thin cylinders at +/-45 deg.
INNER_R = 0.04
inner_ring = _torus("mount_inner", INNER_R, 0.004, (0, 0, 0), mat_dark,
                      ms=20, mn=6, axis='X')
inner_ring.parent = mount_pivot
inner_ring.matrix_parent_inverse = mathutils.Matrix.Identity(4)

for i, ang_deg in enumerate((45, 135, 225, 315)):
    a = math.radians(ang_deg)
    # outer point (on the large ring)
    ox = 0.0
    oy = RING_R * math.cos(a)
    oz = RING_R * math.sin(a)
    # inner point (on the inner ring)
    ix = 0.0
    iy = INNER_R * math.cos(a)
    iz = INNER_R * math.sin(a)
    mx = (ox + ix) / 2
    my = (oy + iy) / 2
    mz = (oz + iz) / 2
    length = math.sqrt((oy - iy)**2 + (oz - iz)**2)
    # angle of the band in the YZ plane (rotation about X)
    band_ang = math.atan2(oz - iz, oy - iy)
    band = _cyl(f"elastic_{i}", 0.003, 0.003, length, 'Y', (mx, my, mz), mat_elastic)
    band.rotation_euler = (band_ang, 0, 0)
    band.parent = mount_pivot
    band.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- microphone capsule : a cylinder pointing along +X with a grille ---
# capsule body
mic_body = _cyl("mic_body", 0.022, 0.022, 0.10, 'X',
                  (0.05, 0, 0), mat_capsule)
mic_body.parent = mount_pivot
mic_body.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# grille head : slightly larger cylinder at the +X end
mic_grille = _cyl("mic_grille", 0.028, 0.028, 0.055, 'X',
                    (0.12, 0, 0), mat_grille)
mic_grille.parent = mount_pivot
mic_grille.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# spherical end-cap on the grille
mic_cap = _sphere("mic_cap", 0.028, (0.148, 0, 0), mat_grille)
mic_cap.parent = mount_pivot
mic_cap.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# small LED on the body
mic_led = _sphere("mic_led", 0.006, (0.025, 0, 0.020), mat_led)
mic_led.parent = mount_pivot
mic_led.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- pop filter : round mesh disc + bracket + thin gooseneck ----
# bracket : a short clamp on the pole
POP_POLE_Z = 0.045 + POLE_H * 0.85
_box("pop_clamp", 0.04, 0.04, 0.025, (0, 0, POP_POLE_Z), mat_dark)
# gooseneck : 3 short cylinder segments connecting clamp -> filter
GN_PTS = [
    (0.0,  0.00, POP_POLE_Z),
    (0.10, 0.00, POP_POLE_Z + 0.04),
    (0.22, 0.00, POP_POLE_Z + 0.02),
    (0.32, 0.00, POP_POLE_Z - 0.02),
]
for i in range(len(GN_PTS) - 1):
    p0 = GN_PTS[i]; p1 = GN_PTS[i+1]
    mx = (p0[0]+p1[0])/2; my = (p0[1]+p1[1])/2; mz = (p0[2]+p1[2])/2
    dx, dy, dz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
    L = math.sqrt(dx*dx + dy*dy + dz*dz)
    # rotation : align +Z to direction (dx,dy,dz)
    seg = _cyl(f"gn_seg_{i}", 0.008, 0.008, L, 'Z', (0,0,0), mat_dark)
    seg.location = (mx, my, mz)
    # quaternion from Z to direction
    direction = mathutils.Vector((dx, dy, dz)).normalized()
    seg.rotation_mode = 'QUATERNION'
    seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)

# pop filter ring (vertical disc, facing the mic, at the end of the gooseneck)
POP_X = GN_PTS[-1][0] + 0.06
POP_Z = GN_PTS[-1][2]
pop_outer = _torus("pop_ring", 0.075, 0.006, (POP_X, 0, POP_Z), mat_ring,
                     ms=24, mn=6, axis='X')
# mesh disc inside the ring (a thin translucent cylinder along X)
pop_mesh = _cyl("pop_mesh", 0.072, 0.072, 0.004, 'X',
                  (POP_X, 0, POP_Z), mat_mesh, segments=24)

# --- cable hanging from the boom end down to the floor ---------
# represented as 3 vertical-ish cylinder segments
CAB_PTS = [
    (BOOM_LEN, 0, PIVOT_Z - 0.18),
    (BOOM_LEN + 0.05, 0.02, PIVOT_Z - 0.45),
    (BOOM_LEN + 0.08, 0.05, PIVOT_Z - 0.80),
    (BOOM_LEN + 0.10, 0.10, 0.02),
]
for i in range(len(CAB_PTS) - 1):
    p0 = CAB_PTS[i]; p1 = CAB_PTS[i+1]
    mx = (p0[0]+p1[0])/2; my = (p0[1]+p1[1])/2; mz = (p0[2]+p1[2])/2
    dx, dy, dz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
    L = math.sqrt(dx*dx + dy*dy + dz*dz)
    seg = _cyl(f"cable_seg_{i}", 0.006, 0.006, L, 'Z', (0,0,0), mat_cable)
    seg.location = (mx, my, mz)
    direction = mathutils.Vector((dx, dy, dz)).normalized()
    seg.rotation_mode = 'QUATERNION'
    seg.rotation_quaternion = mathutils.Vector((0,0,1)).rotation_difference(direction)

# --- animation : mount_pivot sways ±2 deg around X axis -----------
# Also a faint Z bob (±5 mm) to suggest the elastic dynamics.
FPS = 30
DURATION = 6.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
SWAY_DEG = 2.5
BOB_M    = 0.006
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    sway = math.radians(SWAY_DEG) * math.sin(2*math.pi*t * 1.0)
    bob  = BOB_M * math.sin(2*math.pi*t * 2.0 + 1.1)
    mount_pivot.rotation_euler = (sway, 0, 0)
    mount_pivot.location = (MOUNT_HOME_X, 0, MOUNT_HOME_Z + bob)
    mount_pivot.keyframe_insert("rotation_euler", frame=f)
    mount_pivot.keyframe_insert("location", frame=f)
if mount_pivot.animation_data and mount_pivot.animation_data.action:
    for fc in mount_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

# LED throbs gently while we're at it
bsdf = mat_led.node_tree.nodes.get("Principled BSDF")
em_str = bsdf.inputs["Emission Strength"]
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    em_str.default_value = 6.0 + 4.0 * (0.5 + 0.5 * math.sin(2*math.pi*t * 2.0))
    bpy.context.scene.frame_set(f)
    em_str.keyframe_insert(data_path="default_value", frame=f)

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"MIC_OK: {out_glb}", flush=True)
'''


def make_mic(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_mic_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "MIC_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_mic(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
