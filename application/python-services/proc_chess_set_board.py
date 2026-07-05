"""
proc_chess_set_board.py — 149e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué.

Jeu d'échecs complet avec 32 pièces sur échiquier :
- échiquier 64 cases damier black/white bevelé
- bordure bois bevelée
- 32 pièces toutes détaillées :
  * 2 rois avec couronne (1 blanc + 1 noir)
  * 2 reines avec couronne pointu
  * 4 fous avec mitre tilted
  * 4 cavaliers avec tête de cheval
  * 4 tours créneaux carrés
  * 16 pions sphériques sur tige
- bougeoir avec flamme pulse
- 2 tasses de thé
- horloge échecs vintage avec pendule
- table en chêne smooth
- ciel coucher fenêtre

Animations multi-axes :
- 1 cavalier saute en L (translate XY arc)
- 1 pion avance d'une case
- bougie flamme pulse
- horloge pendule oscille
- soleil pulse à travers fenêtre

Sortie : output/3d/pbr_chess_proc.glb.
"""
import bmesh
import bpy
import math
import os
import random

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 180
scene.render.fps = 30

CWD = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_chess_proc.glb"))

random.seed(0xCAFED7)

# --- helpers ----------------------------------------------------------------

def make_mat(name, base, metallic=0.0, roughness=0.6, alpha=1.0, emi=(0, 0, 0), emi_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Alpha"].default_value = alpha
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*emi, 1.0)
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = emi_strength
    return mat


def add_obj(name, mesh, parent=None):
    o = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(o)
    if parent:
        o.parent = parent
    return o


def empty(name, location=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.location = location
    scene.collection.objects.link(e)
    if parent:
        e.parent = parent
    return e


def smooth_shade(mesh):
    for poly in mesh.polygons:
        poly.use_smooth = True
    try:
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(40)
    except AttributeError:
        pass


def beveled_cube(name, size_xyz, bevel_offset=0.04, bevel_segments=3, loc=(0, 0, 0), parent=None, mat=None, smooth=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(size_xyz[0], size_xyz[1], size_xyz[2]), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=bevel_offset, segments=bevel_segments, profile=0.5, affect='EDGES')
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    if smooth:
        smooth_shade(me)
    return o


def smooth_sphere(name, r=1.0, segs=32, rings=20, loc=(0, 0, 0), parent=None, mat=None, scale=(1, 1, 1)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    if scale != (1, 1, 1):
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    smooth_shade(me)
    return o


def smooth_cone(name, r1=1.0, r2=0.0, depth=1.0, segs=24, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    smooth_shade(me)
    return o


# --- materials --------------------------------------------------------------
MAT_WALL = make_mat("wall", (0.30, 0.25, 0.20), roughness=0.6, emi=(0.12, 0.10, 0.08), emi_strength=0.2)
MAT_TABLE = make_mat("table", (0.35, 0.20, 0.10), roughness=0.45, emi=(0.10, 0.05, 0.03), emi_strength=0.2)
MAT_BOARD_LIGHT = make_mat("board_light", (0.90, 0.80, 0.60), metallic=0.10, roughness=0.30, emi=(0.30, 0.25, 0.18), emi_strength=0.3)
MAT_BOARD_DARK = make_mat("board_dark", (0.20, 0.12, 0.06), metallic=0.10, roughness=0.40, emi=(0.05, 0.03, 0.01), emi_strength=0.2)
MAT_BOARD_FRAME = make_mat("board_frame", (0.25, 0.15, 0.08), roughness=0.5, emi=(0.08, 0.05, 0.03), emi_strength=0.2)
MAT_PIECE_WHITE = make_mat("piece_white", (0.95, 0.92, 0.85), metallic=0.20, roughness=0.30, emi=(0.30, 0.28, 0.22), emi_strength=0.3)
MAT_PIECE_BLACK = make_mat("piece_black", (0.10, 0.08, 0.06), metallic=0.20, roughness=0.35, emi=(0.04, 0.03, 0.02), emi_strength=0.2)
MAT_CANDLE_WAX = make_mat("candle_wax", (0.95, 0.92, 0.85), roughness=0.4, emi=(0.40, 0.38, 0.32), emi_strength=0.3)
MAT_FLAME = make_mat("flame", (1.0, 0.65, 0.20), roughness=0.0, alpha=0.85, emi=(1.0, 0.65, 0.20), emi_strength=12.0)
MAT_FLAME.blend_method = 'BLEND'
MAT_FLAME_CORE = make_mat("flame_core", (1.0, 0.95, 0.45), roughness=0.0, emi=(1.0, 0.95, 0.45), emi_strength=14.0)
MAT_BRASS = make_mat("brass", (1.0, 0.85, 0.30), metallic=0.95, roughness=0.20, emi=(0.50, 0.40, 0.10), emi_strength=0.5)
MAT_TEA_CUP = make_mat("tea_cup", (0.95, 0.95, 0.96), roughness=0.4, emi=(0.40, 0.40, 0.42), emi_strength=0.3)
MAT_TEA = make_mat("tea", (0.45, 0.25, 0.10), roughness=0.3, emi=(0.25, 0.15, 0.05), emi_strength=0.4)
MAT_CLOCK_FACE = make_mat("clock_face", (0.95, 0.92, 0.85), roughness=0.5, emi=(0.85, 0.80, 0.70), emi_strength=1.5)
MAT_CLOCK_HAND = make_mat("clock_hand", (0.10, 0.08, 0.05), roughness=0.4)
MAT_WINDOW_GLOW = make_mat("window", (1.0, 0.70, 0.30), roughness=0.0, alpha=0.85, emi=(1.0, 0.70, 0.30), emi_strength=6.0)
MAT_WINDOW_GLOW.blend_method = 'BLEND'

# --- room (cozy chess room) -------------------------------------
back_wall = beveled_cube("back_wall", (12, 6, 0.3), bevel_offset=0.05, bevel_segments=2, loc=(0, 3, -4), mat=MAT_WALL)
for side, dx in [("L", -5), ("R", 5)]:
    w = beveled_cube(f"wall_{side}", (0.3, 6, 8), bevel_offset=0.05, bevel_segments=2, loc=(dx, 3, -1), mat=MAT_WALL)
ceiling = beveled_cube("ceiling", (12, 0.3, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, 6, -1), mat=MAT_WALL)
floor = beveled_cube("floor", (12, 0.05, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.04, -1), mat=MAT_TABLE)

# fenêtre (sunset view)
window_frame = beveled_cube("window_frame", (3.5, 2.5, 0.05), bevel_offset=0.05, bevel_segments=3, loc=(0, 3, -3.85), mat=MAT_BOARD_FRAME)
window_glow = beveled_cube("window_glow", (3.2, 2.2, 0.02), bevel_offset=0.03, bevel_segments=2, loc=(0, 3, -3.80), mat=MAT_WINDOW_GLOW)
# 2 horizontal + 1 vertical bar (croix)
for k in range(2):
    bar_h = beveled_cube(f"win_bar_h_{k}", (3.2, 0.04, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0, 2.3 + k * 1.0, -3.78), mat=MAT_BOARD_FRAME)
bar_v = beveled_cube("win_bar_v", (0.04, 2.2, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0, 3, -3.78), mat=MAT_BOARD_FRAME)

# --- table en chêne -----------------------------------------------
table_p = empty("table_p", (0, 0, 0))
table_top = beveled_cube("table_top", (5.0, 0.12, 3.5), bevel_offset=0.08, bevel_segments=3, loc=(0, 0.95, 0), parent=table_p, mat=MAT_TABLE)
for i, (lx, lz) in enumerate([(2.3, 1.5), (-2.3, 1.5), (2.3, -1.5), (-2.3, -1.5)]):
    leg = beveled_cube(f"table_leg_{i}", (0.15, 0.95, 0.15), bevel_offset=0.04, bevel_segments=2, loc=(lx, 0.475, lz), parent=table_p, mat=MAT_TABLE)

# --- échiquier (chess board) ----------------------------------
board_p = empty("board_p", (0, 1.07, 0))

# frame around the board
board_frame_size = 2.6
frame_w = 0.18
# 4 frame bars
for side, dx, dy, sx, sz in [
    ("F", 0, 1.30, board_frame_size, frame_w),
    ("B", 0, -1.30, board_frame_size, frame_w),
    ("L", -1.30, 0, frame_w, board_frame_size),
    ("R", 1.30, 0, frame_w, board_frame_size),
]:
    bar = beveled_cube(f"board_frame_{side}", (sx, 0.10, sz), bevel_offset=0.03, bevel_segments=2, loc=(dx, 0.05, dy), parent=board_p, mat=MAT_BOARD_FRAME)

# 64 cells (8x8 checkerboard)
CELL = 0.30
cells = {}  # (file, rank) → cell obj for piece position reference
for file in range(8):
    for rank in range(8):
        x = -3.5 * CELL + file * CELL
        z = -3.5 * CELL + rank * CELL
        mat = MAT_BOARD_LIGHT if (file + rank) % 2 == 0 else MAT_BOARD_DARK
        cell = beveled_cube(f"cell_{file}_{rank}", (CELL * 0.96, 0.04, CELL * 0.96), bevel_offset=0.01, bevel_segments=2, loc=(x, 0, z), parent=board_p, mat=mat)
        cells[(file, rank)] = (x, z)

# --- 32 pieces ---------------------------------------------------------------

def make_pawn(name, x, z, mat, parent):
    p = empty(name, (x, 1.10, z), parent=parent)
    # base (flat disc)
    base = smooth_cone(f"{name}_base", r1=0.07, r2=0.07, depth=0.02, segs=18, loc=(0, 0, 0), parent=p, mat=mat)
    base.rotation_euler = (math.radians(90), 0, 0)
    # stem (cone tapered)
    stem = smooth_cone(f"{name}_stem", r1=0.06, r2=0.04, depth=0.10, segs=14, loc=(0, 0.07, 0), parent=p, mat=mat)
    stem.rotation_euler = (math.radians(90), 0, 0)
    # head (sphere on top)
    head = smooth_sphere(f"{name}_head", r=0.05, segs=18, rings=12, loc=(0, 0.16, 0), parent=p, mat=mat)
    return p

def make_rook(name, x, z, mat, parent):
    p = empty(name, (x, 1.10, z), parent=parent)
    base = smooth_cone(f"{name}_base", r1=0.085, r2=0.085, depth=0.02, segs=18, loc=(0, 0, 0), parent=p, mat=mat)
    base.rotation_euler = (math.radians(90), 0, 0)
    body = smooth_cone(f"{name}_body", r1=0.07, r2=0.075, depth=0.16, segs=14, loc=(0, 0.10, 0), parent=p, mat=mat)
    body.rotation_euler = (math.radians(90), 0, 0)
    top_ring = smooth_cone(f"{name}_ring", r1=0.085, r2=0.085, depth=0.025, segs=18, loc=(0, 0.20, 0), parent=p, mat=mat)
    top_ring.rotation_euler = (math.radians(90), 0, 0)
    # 4 crenels (square notches)
    for k in range(4):
        a = k * (math.pi / 2)
        cr = beveled_cube(f"{name}_cr_{k}", (0.035, 0.05, 0.035), bevel_offset=0.005, bevel_segments=2, loc=(math.cos(a) * 0.055, 0.245, math.sin(a) * 0.055), parent=p, mat=mat)
    return p

def make_knight(name, x, z, mat, parent, facing=0):
    p = empty(name, (x, 1.10, z), parent=parent)
    p.rotation_euler = (0, facing, 0)
    base = smooth_cone(f"{name}_base", r1=0.085, r2=0.085, depth=0.02, segs=18, loc=(0, 0, 0), parent=p, mat=mat)
    base.rotation_euler = (math.radians(90), 0, 0)
    body = smooth_cone(f"{name}_body", r1=0.07, r2=0.06, depth=0.14, segs=14, loc=(0, 0.09, 0), parent=p, mat=mat)
    body.rotation_euler = (math.radians(90), 0, 0)
    # horse head : tilted oval body
    head_p = empty(f"{name}_head_p", (0.05, 0.22, 0), parent=p)
    head_p.rotation_euler = (0, 0, math.radians(-20))
    head = smooth_sphere(f"{name}_head", r=0.07, segs=18, rings=12, loc=(0, 0, 0), parent=head_p, mat=mat, scale=(1.4, 1.0, 0.7))
    # nose extension
    nose = smooth_cone(f"{name}_nose", r1=0.055, r2=0.035, depth=0.08, segs=12, loc=(0.10, -0.02, 0), parent=head_p, mat=mat)
    nose.rotation_euler = (0, math.radians(90), 0)
    # 2 ears
    for side, dz in [("L", 0.03), ("R", -0.03)]:
        ear = smooth_cone(f"{name}_ear_{side}", r1=0.015, r2=0.0, depth=0.04, segs=6, loc=(-0.04, 0.06, dz), parent=head_p, mat=mat)
        ear.rotation_euler = (math.radians(-30), 0, 0)
    # 1 eye
    eye = smooth_sphere(f"{name}_eye", r=0.012, segs=8, rings=6, loc=(0.045, 0.015, 0.04), parent=head_p, mat=MAT_PIECE_BLACK if mat == MAT_PIECE_WHITE else MAT_PIECE_WHITE)
    # mane (back of head, 3 small bumps)
    for k in range(3):
        ky = 0.04 - k * 0.04
        mn = smooth_sphere(f"{name}_mane_{k}", r=0.018, segs=10, rings=8, loc=(-0.07, ky, 0), parent=head_p, mat=mat)
    return p

def make_bishop(name, x, z, mat, parent):
    p = empty(name, (x, 1.10, z), parent=parent)
    base = smooth_cone(f"{name}_base", r1=0.085, r2=0.085, depth=0.02, segs=18, loc=(0, 0, 0), parent=p, mat=mat)
    base.rotation_euler = (math.radians(90), 0, 0)
    body = smooth_cone(f"{name}_body", r1=0.07, r2=0.04, depth=0.20, segs=14, loc=(0, 0.12, 0), parent=p, mat=mat)
    body.rotation_euler = (math.radians(90), 0, 0)
    # ring before head
    ring = smooth_cone(f"{name}_ring", r1=0.06, r2=0.06, depth=0.015, segs=14, loc=(0, 0.23, 0), parent=p, mat=mat)
    ring.rotation_euler = (math.radians(90), 0, 0)
    # mitre (cone pointed up, tilted)
    mitre = smooth_cone(f"{name}_mitre", r1=0.045, r2=0.005, depth=0.12, segs=14, loc=(0, 0.30, 0), parent=p, mat=mat)
    mitre.rotation_euler = (math.radians(0), 0, math.radians(5))
    # finial ball
    finial = smooth_sphere(f"{name}_finial", r=0.020, segs=12, rings=8, loc=(0.01, 0.39, 0), parent=p, mat=mat)
    return p

def make_queen(name, x, z, mat, parent):
    p = empty(name, (x, 1.10, z), parent=parent)
    base = smooth_cone(f"{name}_base", r1=0.10, r2=0.10, depth=0.025, segs=20, loc=(0, 0, 0), parent=p, mat=mat)
    base.rotation_euler = (math.radians(90), 0, 0)
    body = smooth_cone(f"{name}_body", r1=0.08, r2=0.05, depth=0.24, segs=14, loc=(0, 0.14, 0), parent=p, mat=mat)
    body.rotation_euler = (math.radians(90), 0, 0)
    # crown base
    crown_base = smooth_cone(f"{name}_crown_base", r1=0.075, r2=0.075, depth=0.02, segs=14, loc=(0, 0.27, 0), parent=p, mat=mat)
    crown_base.rotation_euler = (math.radians(90), 0, 0)
    # 8 spikes around crown
    for k in range(8):
        a = k * (math.pi / 4)
        spike = smooth_cone(f"{name}_spike_{k}", r1=0.015, r2=0.0, depth=0.06, segs=6, loc=(math.cos(a) * 0.065, 0.31, math.sin(a) * 0.065), parent=p, mat=mat)
    # central pointed pinnacle
    center = smooth_cone(f"{name}_center", r1=0.025, r2=0.0, depth=0.07, segs=10, loc=(0, 0.33, 0), parent=p, mat=mat)
    return p

def make_king(name, x, z, mat, parent):
    p = empty(name, (x, 1.10, z), parent=parent)
    base = smooth_cone(f"{name}_base", r1=0.10, r2=0.10, depth=0.025, segs=20, loc=(0, 0, 0), parent=p, mat=mat)
    base.rotation_euler = (math.radians(90), 0, 0)
    body = smooth_cone(f"{name}_body", r1=0.08, r2=0.05, depth=0.28, segs=14, loc=(0, 0.16, 0), parent=p, mat=mat)
    body.rotation_euler = (math.radians(90), 0, 0)
    # crown ring
    crown = smooth_cone(f"{name}_crown", r1=0.08, r2=0.08, depth=0.025, segs=14, loc=(0, 0.31, 0), parent=p, mat=mat)
    crown.rotation_euler = (math.radians(90), 0, 0)
    # cross on top (vertical + horizontal bar)
    cross_v = beveled_cube(f"{name}_cross_v", (0.018, 0.10, 0.018), bevel_offset=0.005, bevel_segments=2, loc=(0, 0.37, 0), parent=p, mat=mat)
    cross_h = beveled_cube(f"{name}_cross_h", (0.06, 0.018, 0.018), bevel_offset=0.005, bevel_segments=2, loc=(0, 0.39, 0), parent=p, mat=mat)
    return p

# Layout chess starting position
# White pieces (rank 0 = back row, rank 1 = pawns)
# Black pieces (rank 7 = back row, rank 6 = pawns)
white_pieces_layout = [
    (0, 0, "rook"), (1, 0, "knight"), (2, 0, "bishop"), (3, 0, "queen"),
    (4, 0, "king"), (5, 0, "bishop"), (6, 0, "knight"), (7, 0, "rook"),
]
for file, rank, kind in white_pieces_layout:
    x, z = cells[(file, rank)]
    if kind == "rook":
        make_rook(f"w_rook_{file}", x, z, MAT_PIECE_WHITE, board_p)
    elif kind == "knight":
        facing = math.pi if file == 1 else 0
        make_knight(f"w_knight_{file}", x, z, MAT_PIECE_WHITE, board_p, facing)
    elif kind == "bishop":
        make_bishop(f"w_bishop_{file}", x, z, MAT_PIECE_WHITE, board_p)
    elif kind == "queen":
        make_queen(f"w_queen", x, z, MAT_PIECE_WHITE, board_p)
    elif kind == "king":
        make_king(f"w_king", x, z, MAT_PIECE_WHITE, board_p)
# White pawns rank 1
white_pawns = []
for file in range(8):
    x, z = cells[(file, 1)]
    p = make_pawn(f"w_pawn_{file}", x, z, MAT_PIECE_WHITE, board_p)
    white_pawns.append(p)

# Black pieces
black_pieces_layout = [
    (0, 7, "rook"), (1, 7, "knight"), (2, 7, "bishop"), (3, 7, "queen"),
    (4, 7, "king"), (5, 7, "bishop"), (6, 7, "knight"), (7, 7, "rook"),
]
animated_knight = None
for file, rank, kind in black_pieces_layout:
    x, z = cells[(file, rank)]
    if kind == "rook":
        make_rook(f"b_rook_{file}", x, z, MAT_PIECE_BLACK, board_p)
    elif kind == "knight":
        facing = 0 if file == 1 else math.pi
        kp = make_knight(f"b_knight_{file}", x, z, MAT_PIECE_BLACK, board_p, facing)
        if file == 1:
            animated_knight = kp
    elif kind == "bishop":
        make_bishop(f"b_bishop_{file}", x, z, MAT_PIECE_BLACK, board_p)
    elif kind == "queen":
        make_queen(f"b_queen", x, z, MAT_PIECE_BLACK, board_p)
    elif kind == "king":
        make_king(f"b_king", x, z, MAT_PIECE_BLACK, board_p)
# Black pawns rank 6
black_pawns = []
for file in range(8):
    x, z = cells[(file, 6)]
    p = make_pawn(f"b_pawn_{file}", x, z, MAT_PIECE_BLACK, board_p)
    black_pawns.append(p)

# One white pawn that moves forward (e2 = file 4, rank 1 → e4 = file 4, rank 3)
animated_pawn = white_pawns[4]
pawn_origin = cells[(4, 1)]
pawn_target = cells[(4, 3)]

# --- bougeoir avec flamme -------------------------------------
candle_p = empty("candle_p", (-2.0, 1.07, 0.6))
holder = smooth_cone("candle_holder_base", r1=0.10, r2=0.08, depth=0.04, segs=16, loc=(0, 0, 0), parent=candle_p, mat=MAT_BRASS)
holder.rotation_euler = (math.radians(90), 0, 0)
holder_col = smooth_cone("candle_holder_col", r1=0.04, r2=0.04, depth=0.10, segs=10, loc=(0, 0.07, 0), parent=candle_p, mat=MAT_BRASS)
holder_col.rotation_euler = (math.radians(90), 0, 0)
holder_cup = smooth_cone("candle_holder_cup", r1=0.06, r2=0.05, depth=0.04, segs=14, loc=(0, 0.14, 0), parent=candle_p, mat=MAT_BRASS)
holder_cup.rotation_euler = (math.radians(90), 0, 0)
candle_wax = smooth_cone("candle_wax", r1=0.035, r2=0.035, depth=0.20, segs=14, loc=(0, 0.28, 0), parent=candle_p, mat=MAT_CANDLE_WAX)
candle_wax.rotation_euler = (math.radians(90), 0, 0)
wick = smooth_cone("wick", r1=0.005, r2=0.005, depth=0.03, segs=6, loc=(0, 0.40, 0), parent=candle_p, mat=MAT_CLOCK_HAND)
wick.rotation_euler = (math.radians(90), 0, 0)
flame = smooth_sphere("flame", r=0.06, segs=14, rings=10, loc=(0, 0.47, 0), parent=candle_p, mat=MAT_FLAME, scale=(1.0, 1.8, 1.0))
flame_core = smooth_sphere("flame_core", r=0.025, segs=10, rings=8, loc=(0, 0.43, 0), parent=candle_p, mat=MAT_FLAME_CORE, scale=(1.0, 1.5, 1.0))

# --- 2 tasses de thé ----------------------------------------
for i, (cx, cz) in enumerate([(2.0, 0.8), (2.0, -0.8)]):
    tea_p = empty(f"tea_{i}", (cx, 1.07, cz))
    saucer = smooth_cone(f"saucer_{i}", r1=0.15, r2=0.13, depth=0.02, segs=20, loc=(0, 0, 0), parent=tea_p, mat=MAT_TEA_CUP)
    saucer.rotation_euler = (math.radians(90), 0, 0)
    cup = smooth_cone(f"cup_{i}", r1=0.08, r2=0.10, depth=0.10, segs=20, loc=(0, 0.06, 0), parent=tea_p, mat=MAT_TEA_CUP)
    cup.rotation_euler = (math.radians(180), 0, 0)
    tea = smooth_cone(f"tea_liquid_{i}", r1=0.085, r2=0.085, depth=0.015, segs=18, loc=(0, 0.10, 0), parent=tea_p, mat=MAT_TEA)
    tea.rotation_euler = (math.radians(90), 0, 0)

# --- horloge échecs vintage avec pendule ----------------------
clock_p = empty("chess_clock", (1.5, 1.07, -1.0))
clock_p.rotation_euler = (0, math.radians(-15), 0)
# main body box
clock_body = beveled_cube("clock_body", (0.6, 0.35, 0.20), bevel_offset=0.04, bevel_segments=3, loc=(0, 0.18, 0), parent=clock_p, mat=MAT_TABLE)
# 2 clock faces (left + right)
for side, dx in [("L", -0.18), ("R", 0.18)]:
    face = smooth_cone(f"clock_face_{side}", r1=0.10, r2=0.10, depth=0.04, segs=24, loc=(dx, 0.20, 0.105), parent=clock_p, mat=MAT_CLOCK_FACE)
    face.rotation_euler = (math.radians(90), 0, 0)
    # 12 hour marks
    for k in range(12):
        a = k * (math.pi / 6) - math.pi / 2
        mx = dx + math.cos(a) * 0.08
        my = 0.20 + math.sin(a) * 0.08
        mark = beveled_cube(f"clock_mark_{side}_{k}", (0.012, 0.012, 0.005), bevel_offset=0.002, bevel_segments=2, loc=(mx, my, 0.13), parent=clock_p, mat=MAT_CLOCK_HAND)
    # hour hand
    hh = beveled_cube(f"clock_hh_{side}", (0.005, 0.04, 0.005), bevel_offset=0.001, bevel_segments=2, loc=(dx, 0.22, 0.135), parent=clock_p, mat=MAT_CLOCK_HAND)
    # minute hand (animated)
    mh_p = empty(f"clock_mh_p_{side}", (dx, 0.20, 0.14), parent=clock_p)
    mh = beveled_cube(f"clock_mh_{side}", (0.004, 0.06, 0.004), bevel_offset=0.001, bevel_segments=2, loc=(0, 0.03, 0), parent=mh_p, mat=MAT_CLOCK_HAND)
# 2 plungers on top
for side, dx in [("L", -0.18), ("R", 0.18)]:
    plunger = smooth_cone(f"plunger_{side}", r1=0.025, r2=0.020, depth=0.05, segs=10, loc=(dx, 0.45, 0), parent=clock_p, mat=MAT_BRASS)
    plunger.rotation_euler = (math.radians(90), 0, 0)

# Pendulum hanging below clock body
pendulum_p = empty("pendulum_p", (0, 0.05, 0.10), parent=clock_p)
pendulum_bar = beveled_cube("pendulum_bar", (0.01, 0.20, 0.01), bevel_offset=0.002, bevel_segments=2, loc=(0, -0.10, 0), parent=pendulum_p, mat=MAT_CLOCK_HAND)
pendulum_bob = smooth_sphere("pendulum_bob", r=0.03, segs=14, rings=10, loc=(0, -0.22, 0), parent=pendulum_p, mat=MAT_BRASS)

# --- animation --------------------------------------------------------------

def kf_loc(o, f, l):
    o.location = l
    o.keyframe_insert(data_path="location", frame=f)


def kf_scale(o, f, s):
    o.scale = s
    o.keyframe_insert(data_path="scale", frame=f)


def kf_rot(o, f, r):
    o.rotation_euler = r
    o.keyframe_insert(data_path="rotation_euler", frame=f)


FRAMES = 180

# Flame pulse intense
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.30 * math.sin(tt * math.pi * 10.0)
    kf_scale(flame, f, (s, 1.8 * s, s))
    s2 = 1.0 + 0.25 * math.sin(tt * math.pi * 12.0)
    kf_scale(flame_core, f, (s2, 1.5 * s2, s2))

# Knight (b1 = file 1, rank 7) jumps in L : rank 7 → rank 5, file 1 → file 2
if animated_knight:
    knight_origin = cells[(1, 7)]
    knight_target = cells[(2, 5)]
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        # 2 full move cycles
        local = (tt * 2.0) % 1.0
        # L-shape : phase 1 (0→0.3 : forward in z), phase 2 (0.3→0.6 : sideways in x), phase 3 stay (return)
        if local < 0.3:
            t = local / 0.3
            x = knight_origin[0]
            z = knight_origin[1] + (knight_target[1] - knight_origin[1]) * t * 0.6
            y = 1.10 + math.sin(t * math.pi) * 0.20  # hop
        elif local < 0.6:
            t = (local - 0.3) / 0.3
            x = knight_origin[0] + (knight_target[0] - knight_origin[0]) * t
            z = knight_origin[1] + (knight_target[1] - knight_origin[1]) * (0.6 + t * 0.4)
            y = 1.10 + math.sin((0.5 + t * 0.5) * math.pi) * 0.20
        elif local < 0.7:
            x = knight_target[0]
            z = knight_target[1]
            y = 1.10
        elif local < 1.0:
            # return to origin
            t = (local - 0.7) / 0.3
            x = knight_target[0] + (knight_origin[0] - knight_target[0]) * t
            z = knight_target[1] + (knight_origin[1] - knight_target[1]) * t
            y = 1.10 + math.sin(t * math.pi) * 0.10
        kf_loc(animated_knight, f, (x, y, z))

# White pawn (e2 → e4 → back to e2 cyclically)
if animated_pawn:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        local = (tt * 2.0) % 1.0
        if local < 0.4:
            t = local / 0.4
            x = pawn_origin[0] + (pawn_target[0] - pawn_origin[0]) * t
            z = pawn_origin[1] + (pawn_target[1] - pawn_origin[1]) * t
            y = 1.10 + math.sin(t * math.pi) * 0.05
        elif local < 0.6:
            x = pawn_target[0]
            z = pawn_target[1]
            y = 1.10
        else:
            t = (local - 0.6) / 0.4
            x = pawn_target[0] + (pawn_origin[0] - pawn_target[0]) * t
            z = pawn_target[1] + (pawn_origin[1] - pawn_target[1]) * t
            y = 1.10 + math.sin(t * math.pi) * 0.05
        kf_loc(animated_pawn, f, (x, y, z))

# Pendulum oscillates
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    swing = math.radians(20) * math.sin(tt * math.pi * 6.0)
    kf_rot(pendulum_p, f, (0, 0, swing))

# Clock minute hands rotate
for side, dx in [("L", -0.18), ("R", 0.18)]:
    mh_p = bpy.data.objects.get(f"clock_mh_p_{side}")
    if mh_p:
        for f in range(1, FRAMES + 1, 3):
            tt = (f - 1) / (FRAMES - 1)
            kf_rot(mh_p, f, (0, 0, -tt * math.pi * 2.0))

# Window glow pulse subtle (sunset)
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.10 * math.sin(tt * math.pi * 3.0)
    kf_scale(window_glow, f, (s, s, 1.0))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_chess] wrote {OUT}")
