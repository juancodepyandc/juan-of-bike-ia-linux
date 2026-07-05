"""Procedural Japanese bonsai (Blender headless).

Ceramic pot + twisted trunk built recursively with curving branches +
dense green foliage cluster blobs. Animation : gentle global sway.

CLI:
  python proc_bonsai.py <output_glb>
"""
from __future__ import annotations
import argparse, json, os, random, shutil, subprocess, sys, tempfile, time
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
import bpy, bmesh, math, mathutils, random, sys

random.seed(37)

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "bonsai.glb"

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

mat_pot      = pbr_mat("ceramic",   (0.18, 0.10, 0.05), 0.10, 0.40)
mat_pot_edge = pbr_mat("ceramic_edge",(0.28, 0.18, 0.10), 0.10, 0.35)
mat_soil     = pbr_mat("soil",      (0.18, 0.10, 0.05), 0.00, 0.85)
mat_bark     = pbr_mat("bark",      (0.30, 0.18, 0.10), 0.00, 0.75)
mat_leaf_a   = pbr_mat("leaf_dark", (0.12, 0.30, 0.10), 0.00, 0.55)
mat_leaf_b   = pbr_mat("leaf_lt",   (0.20, 0.45, 0.16), 0.00, 0.50)
mat_floor    = pbr_mat("floor",     (0.45, 0.40, 0.35), 0.00, 0.75)

# --- floor / tatami ----------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
fl = bpy.context.active_object; fl.name = "floor"
fl.scale = (1.8, 1.8, 0.04); bpy.ops.object.transform_apply(scale=True)
fl.data.materials.append(mat_floor)

# --- ceramic pot (rectangular shallow) ---------------------
POT_W, POT_D, POT_H = 0.42, 0.30, 0.10
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, POT_H/2))
pot = bpy.context.active_object; pot.name = "pot"
pot.scale = (POT_W, POT_D, POT_H); bpy.ops.object.transform_apply(scale=True)
pot.data.materials.append(mat_pot)

# pot rim (slightly wider thin slab)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, POT_H + 0.012))
rim = bpy.context.active_object; rim.name = "pot_rim"
rim.scale = (POT_W * 1.08, POT_D * 1.08, 0.025); bpy.ops.object.transform_apply(scale=True)
rim.data.materials.append(mat_pot_edge)

# soil (thin dark surface on top of the pot)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, POT_H + 0.005))
soil = bpy.context.active_object; soil.name = "soil"
soil.scale = (POT_W * 0.92, POT_D * 0.92, 0.02); bpy.ops.object.transform_apply(scale=True)
soil.data.materials.append(mat_soil)

# --- root empty for sway animation --------------------------
TRUNK_BASE_Z = POT_H + 0.015
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, TRUNK_BASE_Z))
root = bpy.context.active_object
root.name = "bonsai_root"

# --- helper : add segment of trunk (capped tapered cylinder)
bm_trunk = bmesh.new()
bm_leaf  = bmesh.new()

def add_capsule(bm, p0, p1, r0, r1, segments=10):
    p0v = mathutils.Vector(p0); p1v = mathutils.Vector(p1)
    direction = p1v - p0v
    length = direction.length
    if length < 1e-6:
        return
    direction.normalize()
    up = mathutils.Vector((0, 0, 1)) if abs(direction.z) < 0.95 else mathutils.Vector((1, 0, 0))
    side = direction.cross(up).normalized()
    fwd = direction.cross(side).normalized()
    ring0, ring1 = [], []
    for i in range(segments):
        a = i * 2 * math.pi / segments
        off = side * math.cos(a) + fwd * math.sin(a)
        ring0.append(bm.verts.new(p0v + off * r0))
        ring1.append(bm.verts.new(p1v + off * r1))
    bm.verts.ensure_lookup_table()
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new((ring0[i], ring1[i], ring1[j], ring0[j]))

def add_sphere(bm, centre, R, u=10, v=6):
    tmp = bmesh.new()
    bmesh.ops.create_uvsphere(tmp, u_segments=u, v_segments=v, radius=R)
    bmesh.ops.translate(tmp, vec=centre, verts=tmp.verts)
    vmap = {}
    for v_ in tmp.verts:
        vmap[v_] = bm.verts.new(v_.co.copy())
    bm.verts.ensure_lookup_table()
    for f in tmp.faces:
        try:
            bm.faces.new([vmap[v_] for v_ in f.verts])
        except ValueError:
            pass
    tmp.free()

def grow(p0, direction, length, radius, depth, max_depth=4):
    """Recursive trunk that twists left/right at each segment."""
    direction = mathutils.Vector(direction).normalized()
    # twist : rotate direction by random small angle around a perpendicular
    if depth > 0:
        twist_axis = mathutils.Vector((random.uniform(-1, 1),
                                          random.uniform(-1, 1),
                                          0)).normalized()
        twist_angle = random.uniform(0.15, 0.40)
        if random.random() < 0.5:
            twist_angle = -twist_angle
        direction.rotate(mathutils.Matrix.Rotation(twist_angle, 3, twist_axis))
        direction.normalize()
    p_end = mathutils.Vector(p0) + direction * length
    add_capsule(bm_trunk, p0, tuple(p_end), radius, radius * 0.70)

    if depth >= max_depth:
        # foliage cluster (multiple small spheres)
        for _ in range(6):
            jitter = (random.uniform(-0.10, 0.10),
                       random.uniform(-0.10, 0.10),
                       random.uniform(-0.05, 0.10))
            add_sphere(bm_leaf,
                        (p_end.x + jitter[0],
                         p_end.y + jitter[1],
                         p_end.z + jitter[2]),
                        random.uniform(0.06, 0.09),
                        u=8, v=5)
        return

    # branch into 2-3 sub-branches
    n_sub = random.choice([2, 2, 3])
    for _ in range(n_sub):
        tilt_deg = random.uniform(30, 55)
        azi = random.uniform(0, 2 * math.pi)
        up = mathutils.Vector((0, 0, 1)) if abs(direction.z) < 0.95 else mathutils.Vector((1, 0, 0))
        side = direction.cross(up).normalized()
        fwd = direction.cross(side).normalized()
        rot_axis = side * math.cos(azi) + fwd * math.sin(azi)
        new_dir = direction.copy()
        new_dir.rotate(mathutils.Matrix.Rotation(math.radians(tilt_deg), 3, rot_axis))
        new_length = length * random.uniform(0.60, 0.78)
        new_radius = radius * 0.70
        grow(tuple(p_end), tuple(new_dir),
              new_length, new_radius, depth + 1, max_depth)

# build the trunk + branches
grow((0, 0, 0), (0, 0, 1), 0.20, 0.045, 0, max_depth=3)

bm_trunk.normal_update()
bm_leaf.normal_update()

mesh_trunk = bpy.data.meshes.new("bonsai_trunk")
trunk = bpy.data.objects.new("bonsai_trunk", mesh_trunk)
bpy.context.collection.objects.link(trunk)
bm_trunk.to_mesh(mesh_trunk); bm_trunk.free()
trunk.data.materials.append(mat_bark)
trunk.parent = root
trunk.matrix_parent_inverse = mathutils.Matrix.Identity(4)

mesh_leaf = bpy.data.meshes.new("bonsai_leaves")
leaf = bpy.data.objects.new("bonsai_leaves", mesh_leaf)
bpy.context.collection.objects.link(leaf)
bm_leaf.to_mesh(mesh_leaf); bm_leaf.free()
leaf.data.materials.append(mat_leaf_a)
leaf.parent = root
leaf.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : root sways gently --------------------------
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    root.rotation_euler = (math.sin(2*math.pi*t)         * math.radians(2),
                            math.cos(2*math.pi*t * 0.7)   * math.radians(2),
                            0)
    root.keyframe_insert("rotation_euler", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"BONSAI_OK: {out_glb}", flush=True)
'''


def make_bonsai(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_bonsai_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "BONSAI_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_bonsai(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
