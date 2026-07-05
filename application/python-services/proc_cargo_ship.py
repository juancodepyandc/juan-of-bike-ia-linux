"""Procedural cargo container ship (Blender headless).

Elongated hull + tall rear bridge tower with windows + 30 stacked
colourful containers + 2 smokestacks + water plane. Animation : the
whole ship rolls and pitches gently as if on swell.

CLI:
  python proc_cargo_ship.py <output_glb>
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

random.seed(31)

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "cargo.glb"

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

mat_hull_red    = pbr_mat("hull_red",    (0.55, 0.10, 0.08), 0.30, 0.45)
mat_hull_dark   = pbr_mat("hull_dark",   (0.15, 0.15, 0.18), 0.30, 0.45)
mat_deck        = pbr_mat("deck_grey",   (0.30, 0.30, 0.32), 0.30, 0.55)
mat_bridge      = pbr_mat("bridge_white",(0.92, 0.92, 0.88), 0.10, 0.40)
mat_window      = pbr_mat("window",      (0.05, 0.20, 0.40), 0.00, 0.05)
mat_stack       = pbr_mat("stack_grey",  (0.45, 0.45, 0.47), 0.50, 0.35)
mat_water       = pbr_mat("water",       (0.05, 0.20, 0.30), 0.00, 0.12)

CONTAINER_PALETTE = [
    pbr_mat("c_red",    (0.78, 0.18, 0.10), 0.10, 0.45),
    pbr_mat("c_blue",   (0.10, 0.30, 0.78), 0.10, 0.45),
    pbr_mat("c_yellow", (0.95, 0.78, 0.18), 0.10, 0.40),
    pbr_mat("c_green",  (0.15, 0.62, 0.25), 0.10, 0.40),
    pbr_mat("c_orange", (0.92, 0.45, 0.10), 0.10, 0.40),
    pbr_mat("c_white",  (0.85, 0.85, 0.82), 0.10, 0.45),
]

def _box(name, sx, sy, sz, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj

def _cyl(name, R1, R2, depth, axis, location, mat, segments=20):
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

# --- water --------------------------------------------------
_box("water", 6.0, 3.0, 0.04, (0, 0, -0.05), mat_water)

# --- root empty for roll/pitch animation -------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
root = bpy.context.active_object
root.name = "ship_root"

# --- hull : tapered front, blocky back ---------------------
HULL_L = 3.2
HULL_W = 0.55
HULL_H = 0.30

# Build hull as a custom bmesh : 6 transverse rings tapering at the bow
# similar to the sailboat hull but more boxy and bigger
mesh_hull = bpy.data.meshes.new("hull")
hull = bpy.data.objects.new("hull", mesh_hull)
bpy.context.collection.objects.link(hull)
bm = bmesh.new()
sections = [
    (-HULL_L/2,            0.00,          0.10),                # bow tip
    (-HULL_L/2 + 0.40,    HULL_W * 0.55, HULL_H * 0.65),         # forward
    (-HULL_L/2 + 1.00,    HULL_W * 0.95, HULL_H * 0.85),         # mid front
    (+HULL_L/2 - 0.50,    HULL_W,        HULL_H),                # mid aft
    (+HULL_L/2,           HULL_W,        HULL_H * 0.95),         # stern transom
]
rings = []
for (x, hw, hh) in sections:
    p_tc = bm.verts.new((x, 0,         +hh))
    p_tr = bm.verts.new((x, +hw,       +hh * 0.92))
    p_br = bm.verts.new((x, +hw * 0.75, 0))
    p_bc = bm.verts.new((x, 0,         -hh * 0.45))
    p_bl = bm.verts.new((x, -hw * 0.75, 0))
    p_tl = bm.verts.new((x, -hw,       +hh * 0.92))
    rings.append([p_tc, p_tr, p_br, p_bc, p_bl, p_tl])
bm.verts.ensure_lookup_table()
N_RING = 6
for s in range(len(rings) - 1):
    r0, r1 = rings[s], rings[s+1]
    for i in range(N_RING):
        j = (i + 1) % N_RING
        try:
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
        except ValueError:
            pass
# bow cap
def _cap(ring):
    c = bm.verts.new(((ring[0].co + ring[3].co) / 2))
    for i in range(N_RING):
        j = (i + 1) % N_RING
        try:
            bm.faces.new((c, ring[i], ring[j]))
        except ValueError:
            pass
_cap(rings[0])
_cap(rings[-1])
bm.normal_update()
bm.to_mesh(mesh_hull); bm.free()
hull.data.materials.append(mat_hull_red)
hull.parent = root
hull.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# waterline stripe (dark grey running along the hull)
_box("waterline", HULL_L * 0.95, HULL_W * 2.1, 0.025,
       (0, 0, 0.005), mat_hull_dark).parent = root

# deck (grey flat top of the hull)
deck = _box("deck", HULL_L * 0.92, HULL_W * 1.85, 0.02,
              (0, 0, HULL_H + 0.01), mat_deck)
deck.parent = root
deck.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- bridge tower (multi-storey white box at the stern) -----
BRIDGE_W = 0.40
BRIDGE_D = HULL_W * 1.5
BRIDGE_H1 = 0.35   # main hull section
BRIDGE_X = HULL_L * 0.32

bridge_main = _box("bridge_main", BRIDGE_W, BRIDGE_D, BRIDGE_H1,
                     (BRIDGE_X, 0, HULL_H + 0.02 + BRIDGE_H1/2), mat_bridge)
bridge_main.parent = root
bridge_main.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# control room (smaller box on top)
ctrl = _box("ctrl_room", BRIDGE_W * 0.7, BRIDGE_D * 0.7, 0.20,
              (BRIDGE_X, 0, HULL_H + 0.02 + BRIDGE_H1 + 0.10), mat_bridge)
ctrl.parent = root
ctrl.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# control-room windows (dark band)
for sy in (-1, +1):
    w = _box(f"ctrl_window_{sy}", BRIDGE_W * 0.71, 0.01, 0.10,
               (BRIDGE_X, sy * BRIDGE_D * 0.36, HULL_H + 0.02 + BRIDGE_H1 + 0.12), mat_window)
    w.parent = root
    w.matrix_parent_inverse = mathutils.Matrix.Identity(4)
# front window of control room
fw = _box("ctrl_window_front", 0.01, BRIDGE_D * 0.71, 0.10,
            (BRIDGE_X - BRIDGE_W * 0.36, 0, HULL_H + 0.02 + BRIDGE_H1 + 0.12), mat_window)
fw.parent = root
fw.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# 2 smokestacks (red with dark top)
for sy in (-0.10, +0.10):
    stack = _cyl(f"stack_{sy}", 0.06, 0.05, 0.30, 'Z',
                   (BRIDGE_X + 0.05, sy, HULL_H + 0.02 + BRIDGE_H1 + 0.15), mat_hull_red)
    stack.parent = root
    stack.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    # dark top
    _cyl(f"stack_top_{sy}", 0.07, 0.07, 0.025, 'Z',
           (BRIDGE_X + 0.05, sy, HULL_H + 0.02 + BRIDGE_H1 + 0.31), mat_hull_dark).parent = root

# --- container stacks (30 containers, 3 wide x 2 high x 5 long) ---
CONTAINER_L = 0.30
CONTAINER_W = HULL_W * 0.50
CONTAINER_H = 0.20
n_long, n_wide, n_high = 5, 3, 2

stack_origin_x = -HULL_L/2 + 0.40   # behind the bow tip
stack_origin_y = -(n_wide - 1) * CONTAINER_W / 2

for i in range(n_long):
    for j in range(n_wide):
        for k in range(n_high):
            cx = stack_origin_x + i * (CONTAINER_L + 0.02) + CONTAINER_L/2
            cy = j * (CONTAINER_W * 0.55) - (n_wide - 1) * CONTAINER_W * 0.275
            cz = HULL_H + 0.03 + k * (CONTAINER_H + 0.01) + CONTAINER_H/2
            mat = CONTAINER_PALETTE[(i + j * 3 + k * 7) % len(CONTAINER_PALETTE)]
            c = _box(f"container_{i}_{j}_{k}", CONTAINER_L, CONTAINER_W * 0.55, CONTAINER_H,
                       (cx, cy, cz), mat)
            c.parent = root
            c.matrix_parent_inverse = mathutils.Matrix.Identity(4)

# --- animation : ship rolls + pitches gently ---------------
FPS = 30
DURATION = 5.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 3
for f in range(1, NFR + 1, KEY_EVERY):
    t = (f - 1) / NFR
    bpy.context.scene.frame_set(f)
    root.location = (0, 0, math.sin(2*math.pi*t * 0.7) * 0.015)
    root.rotation_euler = (math.sin(2*math.pi*t)         * math.radians(3),  # roll
                            math.cos(2*math.pi*t * 0.5)   * math.radians(2), # pitch
                            0)
    root.keyframe_insert("location", frame=f)
    root.keyframe_insert("rotation_euler", frame=f)
if root.animation_data and root.animation_data.action:
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"CARGO_OK: {out_glb}", flush=True)
'''


def make_cargo(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_cargo_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "CARGO_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_cargo(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
