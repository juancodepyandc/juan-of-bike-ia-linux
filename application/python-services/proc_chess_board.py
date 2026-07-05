"""Procedural chess board with full 32-piece set (Blender headless).

8x8 board with alternating dark/light squares + 16 white pieces +
16 black pieces. Each piece is a stack of simple cylinders forming
a recognisable silhouette. Animation : one pawn hovers up + down to
suggest a contemplated move.

CLI:
  python proc_chess_board.py <output_glb>
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

out_glb = _argv()[0] if _argv() else "chess.glb"

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

mat_light_sq  = pbr_mat("square_light",(0.90, 0.85, 0.72), 0.10, 0.35)
mat_dark_sq   = pbr_mat("square_dark", (0.35, 0.22, 0.10), 0.10, 0.45)
mat_white_pc  = pbr_mat("piece_white", (0.92, 0.88, 0.82), 0.10, 0.30)
mat_black_pc  = pbr_mat("piece_black", (0.12, 0.10, 0.08), 0.10, 0.35)
mat_floor     = pbr_mat("floor",       (0.30, 0.30, 0.32), 0.00, 0.85)
mat_frame     = pbr_mat("board_frame", (0.20, 0.12, 0.06), 0.20, 0.40)

def _cyl(name, R1, R2, depth, axis, location, mat, segments=16):
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

# --- floor + board frame ---------------------------------
_box("floor", 2.0, 2.0, 0.04, (0, 0, -0.04), mat_floor)
BOARD_W = 0.80
SQUARE = BOARD_W / 8
BOARD_Z = 0.02
FRAME_W = 0.06
_box("board_frame", BOARD_W + FRAME_W*2, BOARD_W + FRAME_W*2, BOARD_Z * 1.2,
       (0, 0, BOARD_Z * 0.6), mat_frame)

# --- 64 squares ------------------------------------------
for r in range(8):
    for c in range(8):
        cx = (c - 3.5) * SQUARE
        cy = (r - 3.5) * SQUARE
        mat = mat_light_sq if (r + c) % 2 == 0 else mat_dark_sq
        _box(f"sq_{r}_{c}", SQUARE * 0.98, SQUARE * 0.98, 0.018,
               (cx, cy, BOARD_Z + 0.011), mat)

# --- piece factories : stacks of cylinders forming a silhouette ---
def _piece(name_prefix, piece_type, mat, x, y):
    """piece_type in {pawn, rook, knight, bishop, queen, king}.
    Returns the bottom pivot for hover animation.
    """
    base_z = BOARD_Z + 0.025
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(x, y, base_z))
    pv = bpy.context.active_object
    pv.name = f"{name_prefix}_pivot"
    objs = []
    if piece_type == "pawn":
        # disc base + thinner stem + small spherical head
        objs.append(_cyl(f"{name_prefix}_base", 0.022, 0.018, 0.012, 'Z', (0, 0, 0.006), mat))
        objs.append(_cyl(f"{name_prefix}_stem", 0.010, 0.008, 0.030, 'Z', (0, 0, 0.030), mat))
        # sphere head
        mesh_h = bpy.data.meshes.new(f"{name_prefix}_head")
        h = bpy.data.objects.new(f"{name_prefix}_head", mesh_h)
        bpy.context.collection.objects.link(h)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.013)
        bmesh.ops.translate(bm, vec=(0, 0, 0.058), verts=bm.verts)
        bm.to_mesh(mesh_h); bm.free()
        h.data.materials.append(mat)
        objs.append(h)
    elif piece_type == "rook":
        objs.append(_cyl(f"{name_prefix}_base", 0.025, 0.020, 0.015, 'Z', (0, 0, 0.008), mat))
        objs.append(_cyl(f"{name_prefix}_body", 0.018, 0.020, 0.060, 'Z', (0, 0, 0.045), mat))
        objs.append(_cyl(f"{name_prefix}_top", 0.024, 0.024, 0.012, 'Z', (0, 0, 0.082), mat))
    elif piece_type == "knight":
        objs.append(_cyl(f"{name_prefix}_base", 0.025, 0.020, 0.015, 'Z', (0, 0, 0.008), mat))
        objs.append(_cyl(f"{name_prefix}_body", 0.018, 0.014, 0.055, 'Z', (0, 0, 0.043), mat))
        # tilted "horse head" box
        head = _box(f"{name_prefix}_head", 0.040, 0.020, 0.030, (0.012, 0, 0.080), mat)
        head.rotation_euler = (0, math.radians(-25), 0)
    elif piece_type == "bishop":
        objs.append(_cyl(f"{name_prefix}_base", 0.025, 0.020, 0.015, 'Z', (0, 0, 0.008), mat))
        objs.append(_cyl(f"{name_prefix}_body", 0.018, 0.012, 0.080, 'Z', (0, 0, 0.056), mat))
        # mitre top (small cone)
        mesh_top = bpy.data.meshes.new(f"{name_prefix}_mitre")
        t = bpy.data.objects.new(f"{name_prefix}_mitre", mesh_top)
        bpy.context.collection.objects.link(t)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=10,
                                radius1=0.015, radius2=0.002, depth=0.030)
        bmesh.ops.translate(bm, vec=(0, 0, 0.111), verts=bm.verts)
        bm.to_mesh(mesh_top); bm.free()
        t.data.materials.append(mat)
        objs.append(t)
    elif piece_type == "queen":
        objs.append(_cyl(f"{name_prefix}_base", 0.027, 0.022, 0.015, 'Z', (0, 0, 0.008), mat))
        objs.append(_cyl(f"{name_prefix}_body", 0.020, 0.016, 0.090, 'Z', (0, 0, 0.060), mat))
        objs.append(_cyl(f"{name_prefix}_collar", 0.022, 0.022, 0.012, 'Z', (0, 0, 0.111), mat))
        # spherical crown top
        mesh_c = bpy.data.meshes.new(f"{name_prefix}_crown")
        c = bpy.data.objects.new(f"{name_prefix}_crown", mesh_c)
        bpy.context.collection.objects.link(c)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.015)
        bmesh.ops.translate(bm, vec=(0, 0, 0.130), verts=bm.verts)
        bm.to_mesh(mesh_c); bm.free()
        c.data.materials.append(mat)
        objs.append(c)
    elif piece_type == "king":
        objs.append(_cyl(f"{name_prefix}_base", 0.027, 0.022, 0.015, 'Z', (0, 0, 0.008), mat))
        objs.append(_cyl(f"{name_prefix}_body", 0.020, 0.016, 0.095, 'Z', (0, 0, 0.063), mat))
        objs.append(_cyl(f"{name_prefix}_collar", 0.024, 0.024, 0.012, 'Z', (0, 0, 0.116), mat))
        # cross on top (2 small boxes)
        objs.append(_box(f"{name_prefix}_cross_v", 0.006, 0.006, 0.030, (0, 0, 0.140), mat))
        objs.append(_box(f"{name_prefix}_cross_h", 0.020, 0.006, 0.006, (0, 0, 0.135), mat))

    # parent all pieces to pivot
    for o in objs:
        o.parent = pv
        o.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    return pv

# --- place all 32 pieces -----------------------------------
PIECE_ROW = [
    "rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"
]

selected_pawn_pivot = None
for color, base_row, pawn_row, mat in [
    ("w", 0, 1, mat_white_pc),
    ("b", 7, 6, mat_black_pc),
]:
    for c in range(8):
        x = (c - 3.5) * SQUARE
        y = (pawn_row - 3.5) * SQUARE
        pv = _piece(f"{color}_p_{c}", "pawn", mat, x, y)
        if color == "w" and c == 4:
            selected_pawn_pivot = pv
        x_b = (c - 3.5) * SQUARE
        y_b = (base_row - 3.5) * SQUARE
        _piece(f"{color}_{PIECE_ROW[c]}_{c}", PIECE_ROW[c], mat, x_b, y_b)

# --- animation : selected pawn hovers up and down ----------
FPS = 30
DURATION = 4.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

KEY_EVERY = 2
if selected_pawn_pivot is not None:
    base = list(selected_pawn_pivot.location)
    for f in range(1, NFR + 1, KEY_EVERY):
        t = (f - 1) / NFR
        bpy.context.scene.frame_set(f)
        # hover above + tilt slightly
        z_off = max(0, math.sin(2*math.pi*t)) * 0.05
        selected_pawn_pivot.location = (base[0], base[1], base[2] + z_off)
        selected_pawn_pivot.keyframe_insert("location", frame=f)
    if selected_pawn_pivot.animation_data and selected_pawn_pivot.animation_data.action:
        for fc in selected_pawn_pivot.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"CHESS_OK: {out_glb}", flush=True)
'''


def make_chess(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_chess_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "CHESS_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
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
    r = make_chess(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
