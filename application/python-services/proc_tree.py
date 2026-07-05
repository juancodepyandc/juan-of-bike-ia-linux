"""Procedural stylised tree (Blender headless, recursive L-system-ish).

Trunk + recursive branches (3 levels) + foliage clusters (green spheres at
leaf nodes). Whole tree sways via a gentle root rotation animation.

CLI:
  python proc_tree.py <output_glb>
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

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "tree.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.render.fps = 30

random.seed(42)  # deterministic tree shape

def pbr_mat(name, color, metal, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
    return m

mat_bark    = pbr_mat("bark_brown",   (0.25, 0.15, 0.08), 0.00, 0.78)
mat_leaf_a  = pbr_mat("leaf_dark",    (0.13, 0.32, 0.10), 0.00, 0.55)
mat_leaf_b  = pbr_mat("leaf_light",   (0.22, 0.50, 0.16), 0.00, 0.50)
mat_ground  = pbr_mat("grass_ground", (0.18, 0.30, 0.12), 0.00, 0.85)

# --- ground -----------------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.05))
ground = bpy.context.active_object
ground.name = "ground"
ground.scale = (3.5, 3.5, 0.06)
bpy.ops.object.transform_apply(scale=True)
ground.data.materials.append(mat_ground)

# --- root empty (swaying anchor) -------------------------------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
root = bpy.context.active_object
root.name = "tree_root"

# --- merged bark bmesh (single mesh holding all branches) -------------------
mesh_bark = bpy.data.meshes.new("tree_bark")
bark_obj = bpy.data.objects.new("tree_bark", mesh_bark)
bpy.context.collection.objects.link(bark_obj)
bm_bark = bmesh.new()

# --- merged foliage bmesh ---------------------------------------------------
mesh_leaf_a = bpy.data.meshes.new("tree_leaves_dark")
leaf_a_obj = bpy.data.objects.new("tree_leaves_dark", mesh_leaf_a)
bpy.context.collection.objects.link(leaf_a_obj)
bm_leaf_a = bmesh.new()

mesh_leaf_b = bpy.data.meshes.new("tree_leaves_light")
leaf_b_obj = bpy.data.objects.new("tree_leaves_light", mesh_leaf_b)
bpy.context.collection.objects.link(leaf_b_obj)
bm_leaf_b = bmesh.new()


def add_segment(bm, p0, p1, r0, r1, segments=10):
    """Add a tapered cylinder from p0 (radius r0) to p1 (radius r1) into bmesh."""
    p0v = mathutils.Vector(p0)
    p1v = mathutils.Vector(p1)
    direction = p1v - p0v
    length = direction.length
    if length < 1e-6:
        return
    direction.normalize()
    # local frame perpendicular to direction
    up = mathutils.Vector((0, 0, 1)) if abs(direction.z) < 0.95 else mathutils.Vector((1, 0, 0))
    side = direction.cross(up).normalized()
    fwd = direction.cross(side).normalized()
    # build 2 rings + faces
    ring0, ring1 = [], []
    for i in range(segments):
        a = i * 2 * math.pi / segments
        offset = side * math.cos(a) + fwd * math.sin(a)
        ring0.append(bm.verts.new(p0v + offset * r0))
        ring1.append(bm.verts.new(p1v + offset * r1))
    bm.verts.ensure_lookup_table()
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new((ring0[i], ring1[i], ring1[j], ring0[j]))


def add_foliage_cluster(bm, centre, scatter_R, n_blobs, blob_R):
    """Add several uv-sphere blobs in a sphere of radius scatter_R around `centre`."""
    for _ in range(n_blobs):
        # uniform random offset
        u = random.uniform(0, 2 * math.pi)
        v = math.acos(1 - 2 * random.random())
        r = scatter_R * random.uniform(0.4, 1.0)
        ox = r * math.sin(v) * math.cos(u)
        oy = r * math.sin(v) * math.sin(u)
        oz = r * math.cos(v)
        pos = (centre[0] + ox, centre[1] + oy, centre[2] + oz)
        # add a low-poly sphere
        bmesh_tmp = bmesh.new()
        bmesh.ops.create_uvsphere(bmesh_tmp, u_segments=10, v_segments=6,
                                   radius=blob_R)
        bmesh.ops.translate(bmesh_tmp, vec=pos, verts=bmesh_tmp.verts)
        # merge into target
        bmesh_tmp.to_mesh(mesh_for(bm))
        bmesh_tmp.free()


# Helper : we need to merge bmesh into existing object's mesh data.
# Simpler approach : just add geometry directly to bm.
def add_sphere(bm, centre, R, u_seg=10, v_seg=6):
    bmesh_tmp = bmesh.new()
    bmesh.ops.create_uvsphere(bmesh_tmp, u_segments=u_seg, v_segments=v_seg, radius=R)
    bmesh.ops.translate(bmesh_tmp, vec=centre, verts=bmesh_tmp.verts)
    # transfer verts/faces from bmesh_tmp to bm
    vert_map = {}
    for v in bmesh_tmp.verts:
        vert_map[v] = bm.verts.new(v.co.copy())
    bm.verts.ensure_lookup_table()
    for f in bmesh_tmp.faces:
        try:
            bm.faces.new([vert_map[v] for v in f.verts])
        except ValueError:
            pass  # face already exists, ignore
    bmesh_tmp.free()


def grow(bm_bark, bm_leaf, p_start, direction, length, radius, depth, max_depth=4):
    """Recursive L-system : build a branch from p_start of given length/radius
    in `direction`, then split into 2-3 sub-branches with shorter/thinner geom.
    """
    direction = mathutils.Vector(direction).normalized()
    p_end = mathutils.Vector(p_start) + direction * length
    add_segment(bm_bark, p_start, tuple(p_end), radius, radius * 0.70)

    if depth >= max_depth:
        # leaf : 1-2 clusters of foliage spheres around p_end
        for _ in range(2):
            jitter = (random.uniform(-0.10, 0.10),
                       random.uniform(-0.10, 0.10),
                       random.uniform(-0.10, 0.10))
            centre = (p_end.x + jitter[0], p_end.y + jitter[1], p_end.z + jitter[2])
            target = bm_leaf if random.random() < 0.6 else bm_leaf_b
            for _ in range(3):
                offset = (random.uniform(-0.12, 0.12),
                           random.uniform(-0.12, 0.12),
                           random.uniform(-0.12, 0.12))
                add_sphere(target,
                            (centre[0]+offset[0], centre[1]+offset[1], centre[2]+offset[2]),
                            random.uniform(0.10, 0.16),
                            u_seg=8, v_seg=5)
        return

    # branch into 2 or 3 sub-branches
    n_sub = random.choice([2, 2, 3])
    for _ in range(n_sub):
        # tilt direction by 20-45 deg in a random azimuth
        tilt_deg = random.uniform(25, 50)
        azi = random.uniform(0, 2 * math.pi)
        # rotate `direction` by tilt_deg around a perpendicular axis
        # choose a perpendicular axis using the azimuth
        up = mathutils.Vector((0, 0, 1)) if abs(direction.z) < 0.95 else mathutils.Vector((1, 0, 0))
        side = direction.cross(up).normalized()
        fwd = direction.cross(side).normalized()
        rot_axis = side * math.cos(azi) + fwd * math.sin(azi)
        new_dir = direction.copy()
        new_dir.rotate(mathutils.Matrix.Rotation(math.radians(tilt_deg), 3, rot_axis))
        new_length = length * random.uniform(0.65, 0.82)
        new_radius = radius * 0.70
        grow(bm_bark, bm_leaf, tuple(p_end), tuple(new_dir),
              new_length, new_radius, depth + 1, max_depth)


# Build the tree (trunk + recursive growth)
grow(bm_bark, bm_leaf_a, (0, 0, 0), (0, 0, 1), 0.85, 0.075, 0, max_depth=3)

# normals + transfer to mesh data
for bm in (bm_bark, bm_leaf_a, bm_leaf_b):
    bm.normal_update()

bm_bark.to_mesh(mesh_bark); bm_bark.free()
bm_leaf_a.to_mesh(mesh_leaf_a); bm_leaf_a.free()
bm_leaf_b.to_mesh(mesh_leaf_b); bm_leaf_b.free()

bark_obj.data.materials.append(mat_bark)
leaf_a_obj.data.materials.append(mat_leaf_a)
leaf_b_obj.data.materials.append(mat_leaf_b)

bark_obj.parent = root
bark_obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
leaf_a_obj.parent = root
leaf_a_obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
leaf_b_obj.parent = root
leaf_b_obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : gentle global sway ---------------------------------------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    root.rotation_euler = (math.sin(2*math.pi*t) * math.radians(4),
                            math.cos(2*math.pi*t*0.7) * math.radians(3),
                            0)
    root.keyframe_insert("rotation_euler", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"TREE_OK: {out_glb}", flush=True)
'''


def make_tree(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_tree_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "TREE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_tree(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
