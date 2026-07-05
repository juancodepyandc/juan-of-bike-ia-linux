"""Procedural medieval castle (Blender headless).

4 corner towers with crenellations + connecting walls + gatehouse +
flag on the tallest tower that oscillates. PBR stone + wood + red
flag.

CLI:
  python proc_castle.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "castle.glb"

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

mat_stone     = pbr_mat("stone",       (0.50, 0.48, 0.44), 0.00, 0.78)
mat_stone_dk  = pbr_mat("stone_dark",  (0.36, 0.34, 0.32), 0.00, 0.82)
mat_roof_red  = pbr_mat("roof_red",    (0.55, 0.12, 0.10), 0.10, 0.50)
mat_wood      = pbr_mat("wood_door",   (0.30, 0.18, 0.08), 0.00, 0.65)
mat_grass     = pbr_mat("grass",       (0.18, 0.30, 0.12), 0.00, 0.85)
mat_flag      = pbr_mat("flag_red",    (0.80, 0.12, 0.12), 0.00, 0.40)
mat_pole      = pbr_mat("pole_brass",  (0.86, 0.62, 0.20), 1.00, 0.30)

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

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

# --- ground / courtyard --------------------------------------------
_box("grass_field", 5.0, 5.0, 0.04, (0, 0, -0.04), mat_grass)
# courtyard plate inside the castle (darker, on top of grass)
_box("courtyard", 1.20, 1.20, 0.02, (0, 0, 0.005), mat_stone_dk)

# --- 4 corner towers -----------------------------------------------
TOWER_R = 0.22
TOWER_H = 1.20
TOWER_TOP = TOWER_H
CORNER = 0.80   # half-distance between opposite corners
HIGH_TOWER_BONUS = 0.40  # one tower is taller (the keep)

tower_positions = [
    (-CORNER, -CORNER, 0.0),                  # SW (regular)
    (+CORNER, -CORNER, 0.0),                  # SE (regular)
    (-CORNER, +CORNER, 0.0),                  # NW (regular)
    (+CORNER, +CORNER, HIGH_TOWER_BONUS),     # NE (tall keep with flag)
]

def _build_tower(idx, cx, cy, extra_h):
    H = TOWER_H + extra_h
    # main shaft
    _cyl(f"tower_{idx}", TOWER_R, TOWER_R, H, 'Z', (cx, cy, H/2), mat_stone)
    # base flare (wider ring at bottom)
    _cyl(f"tower_{idx}_base", TOWER_R * 1.15, TOWER_R, 0.15, 'Z',
           (cx, cy, 0.075), mat_stone_dk)
    # parapet : a slightly larger ring at the top
    parapet_z = H
    _cyl(f"tower_{idx}_parapet", TOWER_R * 1.10, TOWER_R * 1.10, 0.06, 'Z',
           (cx, cy, parapet_z + 0.03), mat_stone)
    # crenellations : 8 small notched blocks evenly around the top
    for k in range(8):
        a = k * 2 * math.pi / 8
        mx = math.cos(a) * TOWER_R * 1.05
        my = math.sin(a) * TOWER_R * 1.05
        b = _box(f"tower_{idx}_battlement_{k}",
                   0.045, 0.045, 0.07,
                   (cx + mx, cy + my, parapet_z + 0.10), mat_stone)
        b.rotation_euler = (0, 0, a)
    # if this is the tall keep, add a conical roof
    if extra_h > 0:
        _cyl(f"tower_{idx}_roof", TOWER_R * 1.15, 0.05, 0.30, 'Z',
               (cx, cy, parapet_z + 0.30), mat_roof_red)
    return parapet_z, H

parapets = []
for idx, (cx, cy, eh) in enumerate(tower_positions):
    parapet_z, H = _build_tower(idx, cx, cy, eh)
    parapets.append((cx, cy, parapet_z, eh))

# --- walls connecting adjacent corners (4 walls forming a square) ---
WALL_H = TOWER_H * 0.70
WALL_THICK = 0.12

def _build_wall(idx, p0, p1):
    """Wall between p0 and p1 in the XY plane."""
    p0v = mathutils.Vector(p0)
    p1v = mathutils.Vector(p1)
    direction = p1v - p0v
    length = direction.length - 2 * TOWER_R * 0.85   # don't overlap towers
    if length < 0.1:
        return
    direction.normalize()
    mid = (p0v + p1v) / 2
    yaw = math.atan2(direction.y, direction.x)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(mid.x, mid.y, WALL_H/2))
    w = bpy.context.active_object
    w.name = f"wall_{idx}"
    w.scale = (length, WALL_THICK, WALL_H)
    bpy.ops.object.transform_apply(scale=True)
    w.rotation_euler = (0, 0, yaw)
    w.data.materials.append(mat_stone)
    # crenellations on top of the wall
    n_crens = max(3, int(length / 0.18))
    for k in range(n_crens):
        t = (k + 0.5) / n_crens
        cx = p0v.x + (p1v.x - p0v.x) * (TOWER_R * 0.85 / (p1v - p0v).length +
                                          t * (length / (p1v - p0v).length))
        cy = p0v.y + (p1v.y - p0v.y) * (TOWER_R * 0.85 / (p1v - p0v).length +
                                          t * (length / (p1v - p0v).length))
        if k % 2 == 1:
            continue   # skip every other to make the notches
        b = _box(f"wall_{idx}_cren_{k}", 0.08, WALL_THICK * 1.05, 0.08,
                   (cx, cy, WALL_H + 0.04), mat_stone)
        b.rotation_euler = (0, 0, yaw)

# 4 walls (skip the south wall which will have the gatehouse)
corners_xy = [(cx, cy) for (cx, cy, _) in tower_positions]
_build_wall(0, corners_xy[0], corners_xy[2])  # west wall (SW to NW)
_build_wall(1, corners_xy[2], corners_xy[3])  # north wall (NW to NE)
_build_wall(2, corners_xy[3], corners_xy[1])  # east wall (NE to SE)
# (no south wall - gate is there)

# --- gatehouse + gate -----------------------------------------------
# south side : between SW (-CORNER, -CORNER) and SE (+CORNER, -CORNER)
# build the south wall in 2 halves with a gap for the gate in the middle
GATE_W = 0.35
half_south = (CORNER - TOWER_R * 0.85 - GATE_W / 2) / 2 + (TOWER_R * 0.85 + GATE_W / 2) / 2
# left half south wall (from SW tower edge to -GATE_W/2)
left_p0 = (-CORNER + TOWER_R * 0.85, -CORNER, 0)
left_p1 = (-GATE_W/2, -CORNER, 0)
bpy.ops.mesh.primitive_cube_add(size=1,
    location=((left_p0[0] + left_p1[0]) / 2, -CORNER, WALL_H / 2))
w = bpy.context.active_object
w.name = "south_wall_left"
w.scale = (left_p1[0] - left_p0[0], WALL_THICK, WALL_H)
bpy.ops.object.transform_apply(scale=True)
w.data.materials.append(mat_stone)
# right half
right_p0 = (GATE_W/2, -CORNER, 0)
right_p1 = (CORNER - TOWER_R * 0.85, -CORNER, 0)
bpy.ops.mesh.primitive_cube_add(size=1,
    location=((right_p0[0] + right_p1[0]) / 2, -CORNER, WALL_H / 2))
w = bpy.context.active_object
w.name = "south_wall_right"
w.scale = (right_p1[0] - right_p0[0], WALL_THICK, WALL_H)
bpy.ops.object.transform_apply(scale=True)
w.data.materials.append(mat_stone)

# gatehouse arch (a slightly taller block above the gate gap)
_box("gatehouse", GATE_W + 0.12, WALL_THICK + 0.04, 0.30,
       (0, -CORNER, WALL_H + 0.05), mat_stone_dk)

# wooden gate door (in the gap, ground-level)
_box("gate_door", GATE_W * 0.95, 0.04, WALL_H * 0.85,
       (0, -CORNER, WALL_H * 0.85 / 2), mat_wood)

# --- flag on the tall keep (NE corner) --------------------------------
keep_cx, keep_cy, keep_parapet, keep_eh = parapets[3]
KEEP_TOP = TOWER_H + keep_eh + 0.30 + 0.30  # parapet + roof + half-roof
FLAG_BASE_Z = KEEP_TOP + 0.10

# flag pole (brass)
_cyl("flag_pole", 0.012, 0.012, 0.50, 'Z',
       (keep_cx, keep_cy, FLAG_BASE_Z + 0.25), mat_pole)

# flag itself (rectangle that flaps via animated Y rotation around the pole)
bpy.ops.object.empty_add(type='PLAIN_AXES',
                          location=(keep_cx, keep_cy, FLAG_BASE_Z + 0.45))
flag_pivot = bpy.context.active_object
flag_pivot.name = "flag_pivot"

# flag cloth : a thin box extending +X from the pole
flag_cloth = _box("flag_cloth", 0.30, 0.005, 0.20,
                    (keep_cx + 0.15, keep_cy, FLAG_BASE_Z + 0.45), mat_flag)
flag_cloth.parent = flag_pivot
flag_cloth.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : flag rotates back-and-forth around the pole + courtyard ground stays still
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    flag_pivot.rotation_euler = (0, 0, math.sin(2*math.pi*t) * math.radians(35))
    flag_pivot.keyframe_insert("rotation_euler", frame=f)
if flag_pivot.animation_data and flag_pivot.animation_data.action:
    for fc in flag_pivot.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"CASTLE_OK: {out_glb}", flush=True)
'''


def make_castle(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_castle_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "CASTLE_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_castle(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
