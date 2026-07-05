"""
proc_classical_violin.py — 148e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué.

Violon classique avec archet sur partition :
- corps violon courbé bevelé en forme d'amande
- 4 cordes tendues émissives
- chevalet + cordier + bouton + 4 chevilles
- touche + 4 frettes
- manche + crosse spirale (volute)
- 2 ouïes f-holes
- archet en crin avec poignée + frog
- résine bloc
- partition ouverte avec notes
- chandelier 3 bougies émissives
- bibliothèque arrière (5 étagères + livres)
- table en bois
- tasse de thé
- sol parquet damier

Animations multi-axes simultanées :
- archet : glisse va-et-vient sur cordes
- 4 cordes : vibrent (subtle scale)
- 3 bougies : flammes pulse intense
- volute spirale subtile rotation
- partition : pages tournent à intervalle

Sortie : output/3d/pbr_violin_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_violin_proc.glb"))

random.seed(0xCAFEC5)

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
    if alpha < 1.0:
        mat.blend_method = 'BLEND'
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


def beveled_cube(name, size_xyz, bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=None, mat=None, smooth=True):
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
MAT_WALL = make_mat("wall", (0.30, 0.22, 0.18), roughness=0.6,
                     emi=(0.10, 0.08, 0.06), emi_strength=0.2)
MAT_FLOOR_LIGHT = make_mat("floor_light", (0.65, 0.45, 0.25), roughness=0.4,
                             emi=(0.20, 0.15, 0.08), emi_strength=0.25)
MAT_FLOOR_DARK = make_mat("floor_dark", (0.30, 0.20, 0.10), roughness=0.5)
MAT_VIOLIN_BODY = make_mat("violin_body", (0.55, 0.20, 0.08), metallic=0.30, roughness=0.20,
                             emi=(0.20, 0.07, 0.03), emi_strength=0.30)
MAT_VIOLIN_DARK = make_mat("violin_dark", (0.25, 0.10, 0.05), roughness=0.30)
MAT_VIOLIN_LIGHT = make_mat("violin_light", (0.85, 0.55, 0.25), metallic=0.20, roughness=0.30,
                              emi=(0.30, 0.18, 0.08), emi_strength=0.25)
MAT_STRING = make_mat("string", (0.85, 0.85, 0.92), metallic=0.95, roughness=0.10,
                        emi=(0.40, 0.40, 0.42), emi_strength=0.40)
MAT_BOW_HORSEHAIR = make_mat("bow_hair", (0.95, 0.90, 0.80), roughness=0.5,
                               emi=(0.35, 0.32, 0.25), emi_strength=0.25)
MAT_BOW_WOOD = make_mat("bow_wood", (0.30, 0.18, 0.08), roughness=0.55)
MAT_ROSIN = make_mat("rosin", (0.85, 0.55, 0.20), roughness=0.4,
                       emi=(0.40, 0.25, 0.08), emi_strength=0.3)
MAT_PAPER = make_mat("paper", (0.95, 0.92, 0.85), roughness=0.5,
                       emi=(0.35, 0.32, 0.28), emi_strength=0.4)
MAT_INK = make_mat("ink", (0.10, 0.08, 0.06), roughness=0.4)
MAT_CANDLE_WAX = make_mat("candle_wax", (0.95, 0.92, 0.85), roughness=0.4,
                            emi=(0.40, 0.38, 0.32), emi_strength=0.3)
MAT_FLAME = make_mat("flame", (1.0, 0.65, 0.20), roughness=0.0, alpha=0.85,
                       emi=(1.0, 0.65, 0.20), emi_strength=12.0)
MAT_FLAME_CORE = make_mat("flame_core", (1.0, 0.95, 0.40), roughness=0.0,
                            emi=(1.0, 0.95, 0.40), emi_strength=14.0)
MAT_CANDLE_HOLDER = make_mat("candle_holder", (0.85, 0.70, 0.30), metallic=0.95, roughness=0.20,
                               emi=(0.30, 0.25, 0.08), emi_strength=0.30)
MAT_TABLE_WOOD = make_mat("table_wood", (0.40, 0.25, 0.15), roughness=0.5,
                            emi=(0.12, 0.08, 0.05), emi_strength=0.2)
MAT_BOOK_R = make_mat("book_r", (0.55, 0.15, 0.10), roughness=0.5,
                        emi=(0.20, 0.05, 0.05), emi_strength=0.3)
MAT_BOOK_G = make_mat("book_g", (0.15, 0.45, 0.20), roughness=0.5,
                        emi=(0.05, 0.20, 0.08), emi_strength=0.3)
MAT_BOOK_B = make_mat("book_b", (0.15, 0.20, 0.55), roughness=0.5,
                        emi=(0.05, 0.10, 0.30), emi_strength=0.3)
MAT_BOOK_Y = make_mat("book_y", (0.75, 0.55, 0.20), roughness=0.5,
                        emi=(0.40, 0.25, 0.08), emi_strength=0.3)
MAT_TEA_CUP = make_mat("tea_cup", (0.95, 0.95, 0.96), roughness=0.4,
                         emi=(0.40, 0.40, 0.42), emi_strength=0.3)
MAT_TEA = make_mat("tea", (0.45, 0.25, 0.10), roughness=0.3,
                     emi=(0.25, 0.15, 0.05), emi_strength=0.4)
MAT_STEAM = make_mat("steam", (0.90, 0.92, 0.95), roughness=1.0, alpha=0.55,
                       emi=(0.80, 0.85, 0.90), emi_strength=1.5)
MAT_BRASS = make_mat("brass", (1.0, 0.85, 0.30), metallic=0.95, roughness=0.20,
                       emi=(0.50, 0.40, 0.10), emi_strength=0.5)

# --- room (cozy salon) ---------------------------------------------
# floor (parquet damier)
N_CHECK = 6
CELL = 1.8
for i in range(N_CHECK):
    for j in range(N_CHECK):
        x = -N_CHECK * CELL / 2 + i * CELL + CELL / 2
        z = -N_CHECK * CELL / 2 + j * CELL + CELL / 2
        mat = MAT_FLOOR_LIGHT if (i + j) % 2 == 0 else MAT_FLOOR_DARK
        beveled_cube(f"floor_{i}_{j}", (CELL * 0.48, 0.04, CELL * 0.48), bevel_offset=0.02, bevel_segments=2, loc=(x, 0, z), mat=mat)
floor_base = beveled_cube("floor_base", (12, 0.05, 12), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.04, 0), mat=MAT_FLOOR_DARK)

# back wall
back_wall = beveled_cube("back_wall", (12, 6, 0.3), bevel_offset=0.05, bevel_segments=2, loc=(0, 3, -5.5), mat=MAT_WALL)
# 2 side walls
for side, dx in [("L", -6), ("R", 6)]:
    w = beveled_cube(f"wall_{side}", (0.3, 6, 12), bevel_offset=0.05, bevel_segments=2, loc=(dx, 3, 0), mat=MAT_WALL)
# ceiling
ceiling = beveled_cube("ceiling", (12, 0.3, 12), bevel_offset=0.05, bevel_segments=2, loc=(0, 6, 0), mat=MAT_WALL)

# --- bibliothèque (5 étagères avec livres) -----------------------
bookshelf_p = empty("bookshelf", (-5.5, 0, -3))
bookshelf_p.rotation_euler = (0, math.radians(20), 0)
# main frame
shelf_back = beveled_cube("shelf_back", (0.10, 4.5, 1.8), bevel_offset=0.05, bevel_segments=3, loc=(0, 2.25, 0), parent=bookshelf_p, mat=MAT_TABLE_WOOD)
# 5 horizontal shelves
for k in range(5):
    ky = 0.50 + k * 0.85
    shelf = beveled_cube(f"shelf_{k}", (0.10, 0.06, 1.8), bevel_offset=0.02, bevel_segments=2, loc=(0.10, ky, 0), parent=bookshelf_p, mat=MAT_TABLE_WOOD)
    # 6 books per shelf
    book_colors = [MAT_BOOK_R, MAT_BOOK_G, MAT_BOOK_B, MAT_BOOK_Y]
    for b in range(6):
        bx = -0.75 + b * 0.30
        bh = 0.50 + random.uniform(-0.08, 0.10)
        bw = 0.10 + random.uniform(-0.02, 0.04)
        book = beveled_cube(f"shelf_{k}_book_{b}", (0.12, bh, bw), bevel_offset=0.01, bevel_segments=2, loc=(0.15, ky + 0.25 + (bh - 0.50) / 2, bx), parent=bookshelf_p, mat=random.choice(book_colors))

# --- table en bois ------------------------------------------------
table_p = empty("table", (0, 0, 0))
# top
table_top = beveled_cube("table_top", (3.5, 0.10, 1.8), bevel_offset=0.06, bevel_segments=3, loc=(0, 0.80, 0), parent=table_p, mat=MAT_TABLE_WOOD)
# 4 legs
for i, (lx, lz) in enumerate([(1.55, 0.80), (-1.55, 0.80), (1.55, -0.80), (-1.55, -0.80)]):
    leg = beveled_cube(f"table_leg_{i}", (0.10, 0.80, 0.10), bevel_offset=0.03, bevel_segments=2, loc=(lx, 0.40, lz), parent=table_p, mat=MAT_TABLE_WOOD)

# --- VIOLON --------------------------------------------------
violin = empty("violin", (0, 0.92, -0.20))
violin.rotation_euler = (math.radians(15), math.radians(-10), math.radians(-5))

# body principal (forme d'amande/violon via 2 sphères fusionnées)
def make_violin_body(name, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    # lower bout (larger)
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=0.45)
    bmesh.ops.scale(bm, vec=(1.4, 0.20, 1.0), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (-0.4, 0, 0)
    me.materials.append(MAT_VIOLIN_BODY)
    smooth_shade(me)
    return o

lower_bout = make_violin_body("lower_bout", violin)

# upper bout (smaller, towards neck)
upper_bout = smooth_sphere("upper_bout", r=0.35, segs=28, rings=18, loc=(0.5, 0, 0), parent=violin, mat=MAT_VIOLIN_BODY, scale=(1.2, 0.20, 0.8))

# waist (middle narrow connection)
waist = smooth_sphere("waist", r=0.20, segs=24, rings=16, loc=(0.0, 0, 0), parent=violin, mat=MAT_VIOLIN_BODY, scale=(1.5, 0.18, 0.5))

# 2 f-holes (decorative cuts as dark spheres)
for side, dz in [("L", 0.18), ("R", -0.18)]:
    fhole = smooth_cone(f"fhole_{side}", r1=0.04, r2=0.04, depth=0.12, segs=8, loc=(-0.20, 0.10, dz), parent=violin, mat=MAT_VIOLIN_DARK)
    fhole.rotation_euler = (math.radians(90), 0, math.radians(15 if side == "L" else -15))

# chevalet (bridge sur le body)
bridge = beveled_cube("bridge", (0.10, 0.08, 0.30), bevel_offset=0.02, bevel_segments=3, loc=(-0.30, 0.18, 0), parent=violin, mat=MAT_VIOLIN_LIGHT)

# cordier (tailpiece, dark at bottom)
tailpiece = beveled_cube("tailpiece", (0.30, 0.05, 0.18), bevel_offset=0.04, bevel_segments=3, loc=(-0.85, 0.12, 0), parent=violin, mat=MAT_VIOLIN_DARK)

# bouton (end button)
end_button = smooth_sphere("end_button", r=0.05, segs=12, rings=8, loc=(-1.10, 0.10, 0), parent=violin, mat=MAT_VIOLIN_DARK)

# touche (fingerboard, dark)
fingerboard = beveled_cube("fingerboard", (1.40, 0.04, 0.16), bevel_offset=0.02, bevel_segments=2, loc=(0.70, 0.16, 0), parent=violin, mat=MAT_VIOLIN_DARK)

# 4 frettes (small marks on fingerboard)
for k in range(4):
    kx = 0.30 + k * 0.30
    fret = beveled_cube(f"fret_{k}", (0.02, 0.02, 0.14), bevel_offset=0.005, bevel_segments=2, loc=(kx, 0.19, 0), parent=violin, mat=MAT_BRASS)

# manche (neck)
neck = beveled_cube("neck", (0.50, 0.06, 0.12), bevel_offset=0.03, bevel_segments=3, loc=(1.40, 0.16, 0), parent=violin, mat=MAT_VIOLIN_BODY)

# crosse (peg box + spiral volute)
peg_box = beveled_cube("peg_box", (0.20, 0.10, 0.12), bevel_offset=0.02, bevel_segments=3, loc=(1.75, 0.20, 0), parent=violin, mat=MAT_VIOLIN_BODY)
# spiral volute (head)
volute_p = empty("volute_p", (1.95, 0.22, 0), parent=violin)
# spiral = 3 small spheres stacked in tight curl
for k in range(4):
    a = k * (math.pi / 2) + math.pi / 4
    r = 0.08 - k * 0.013
    sx = math.cos(a) * 0.07 + 0.03 * k
    sy = math.sin(a) * 0.07
    spiral = smooth_sphere(f"volute_{k}", r=r, segs=14, rings=10, loc=(sx, sy, 0), parent=volute_p, mat=MAT_VIOLIN_BODY)

# 4 chevilles (pegs)
for k in range(4):
    side = k % 2
    pair = k // 2
    dx = 1.65 + pair * 0.10
    dz = 0.10 if side == 0 else -0.10
    # peg shaft
    peg = smooth_cone(f"peg_{k}", r1=0.025, r2=0.020, depth=0.20, segs=10, loc=(dx, 0.20, dz), parent=violin, mat=MAT_VIOLIN_DARK)
    peg.rotation_euler = (math.radians(90), 0, 0)
    # peg head (ball)
    peg_head = smooth_sphere(f"peg_head_{k}", r=0.04, segs=12, rings=10, loc=(dx, 0.20, dz + (0.12 if side == 0 else -0.12)), parent=violin, mat=MAT_VIOLIN_DARK)

# 4 cordes tendues (between bridge and peg box)
strings = []
for k in range(4):
    dz = -0.06 + k * 0.04
    # 4 strings from tailpiece to pegs, going over bridge
    string = beveled_cube(f"string_{k}", (2.10, 0.012, 0.012), bevel_offset=0.002, bevel_segments=2, loc=(0.55, 0.21, dz), parent=violin, mat=MAT_STRING)
    strings.append(string)

# --- archet (bow) -------------------------------------------
bow_p = empty("bow_p", (-0.20, 1.15, 0.5), parent=table_p)
bow_p.rotation_euler = (math.radians(10), 0, math.radians(75))
# stick (long curved wood rod)
bow_stick = smooth_cone("bow_stick", r1=0.018, r2=0.015, depth=1.8, segs=10, loc=(0, 0, 0), parent=bow_p, mat=MAT_BOW_WOOD)
bow_stick.rotation_euler = (0, 0, math.radians(90))
# frog (dark end)
frog = beveled_cube("bow_frog", (0.12, 0.05, 0.06), bevel_offset=0.02, bevel_segments=2, loc=(0.85, 0, 0), parent=bow_p, mat=MAT_VIOLIN_DARK)
# tip (small end)
bow_tip = beveled_cube("bow_tip", (0.06, 0.04, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(-0.85, 0, 0), parent=bow_p, mat=MAT_VIOLIN_DARK)
# horsehair (parallel to stick)
horsehair = beveled_cube("horsehair", (1.7, 0.025, 0.025), bevel_offset=0.005, bevel_segments=2, loc=(0, -0.07, 0), parent=bow_p, mat=MAT_BOW_HORSEHAIR)
# screw at frog
screw = smooth_sphere("bow_screw", r=0.025, segs=10, rings=8, loc=(0.95, 0, 0), parent=bow_p, mat=MAT_BRASS)

# --- rosin (block of rosin) -----------------------------------
rosin = beveled_cube("rosin", (0.10, 0.04, 0.08), bevel_offset=0.02, bevel_segments=2, loc=(0.8, 0.87, -0.45), parent=table_p, mat=MAT_ROSIN)

# --- partition ouverte --------------------------------------
sheet_p = empty("sheet_music", (0, 0.92, 0.6), parent=table_p)
# left page
page_L = beveled_cube("page_L", (0.50, 0.02, 0.65), bevel_offset=0.02, bevel_segments=2, loc=(-0.25, 0, 0), parent=sheet_p, mat=MAT_PAPER)
# right page (slightly tilted - like a flipping page)
page_R_p = empty("page_R_p", (0.0, 0, 0), parent=sheet_p)
page_R = beveled_cube("page_R", (0.50, 0.02, 0.65), bevel_offset=0.02, bevel_segments=2, loc=(0.25, 0, 0), parent=page_R_p, mat=MAT_PAPER)
# 8 musical notes (stylized dots) on each page
for side, base_x in [("L", -0.40), ("R", 0.40)]:
    for k in range(8):
        kz = -0.25 + (k % 4) * 0.15
        ky = 0.025 + (k // 4) * 0.10
        # note head (ellipse)
        note = smooth_sphere(f"note_{side}_{k}", r=0.020, segs=10, rings=8, loc=(base_x, ky, kz), parent=page_L if side == "L" else page_R_p, mat=MAT_INK, scale=(1.2, 1.0, 0.7))
        # stem
        stem = beveled_cube(f"note_stem_{side}_{k}", (0.006, 0.04, 0.005), bevel_offset=0.001, bevel_segments=2, loc=(base_x + 0.02, ky + 0.03, kz), parent=page_L if side == "L" else page_R_p, mat=MAT_INK)
# 5 horizontal staff lines per page
for side, base_x in [("L", -0.40), ("R", 0.40)]:
    for k in range(5):
        ky = 0.020 + k * 0.020
        for half in [-0.1, 0.1]:
            line = beveled_cube(f"staff_{side}_{k}_{half}", (0.45, 0.004, 0.005), bevel_offset=0.001, bevel_segments=2, loc=(base_x, ky, half), parent=page_L if side == "L" else page_R_p, mat=MAT_INK)

# --- chandelier avec 3 bougies ---------------------------------
chandelier_p = empty("chandelier", (1.5, 0.92, -0.6), parent=table_p)
# base (brass plate)
base = smooth_cone("chand_base", r1=0.18, r2=0.16, depth=0.04, segs=20, loc=(0, 0, 0), parent=chandelier_p, mat=MAT_CANDLE_HOLDER)
base.rotation_euler = (math.radians(90), 0, 0)
# central column
column = smooth_cone("chand_col", r1=0.04, r2=0.04, depth=0.15, segs=10, loc=(0, 0.10, 0), parent=chandelier_p, mat=MAT_CANDLE_HOLDER)
column.rotation_euler = (math.radians(90), 0, 0)
# 3 arms with candles
flames_main = []
flames_core = []
for k in range(3):
    a = k * (math.pi * 2 / 3)
    arm_p = empty(f"chand_arm_{k}", (0, 0.17, 0), parent=chandelier_p)
    arm_p.rotation_euler = (0, a, 0)
    # arm (curving up)
    arm = smooth_cone(f"chand_arm_{k}_b", r1=0.02, r2=0.02, depth=0.25, segs=8, loc=(0.10, 0.05, 0), parent=arm_p, mat=MAT_CANDLE_HOLDER)
    arm.rotation_euler = (math.radians(60), 0, 0)
    # candle cup
    cup = smooth_cone(f"chand_cup_{k}", r1=0.05, r2=0.04, depth=0.04, segs=12, loc=(0.20, 0.18, 0), parent=arm_p, mat=MAT_CANDLE_HOLDER)
    cup.rotation_euler = (math.radians(90), 0, 0)
    # candle wax
    candle = smooth_cone(f"candle_{k}", r1=0.035, r2=0.035, depth=0.20, segs=12, loc=(0.20, 0.30, 0), parent=arm_p, mat=MAT_CANDLE_WAX)
    candle.rotation_euler = (math.radians(90), 0, 0)
    # wick
    wick = smooth_cone(f"wick_{k}", r1=0.005, r2=0.005, depth=0.04, segs=6, loc=(0.20, 0.42, 0), parent=arm_p, mat=MAT_INK)
    wick.rotation_euler = (math.radians(90), 0, 0)
    # flame (main emissive)
    flame = smooth_sphere(f"flame_{k}", r=0.06, segs=14, rings=10, loc=(0.20, 0.50, 0), parent=arm_p, mat=MAT_FLAME, scale=(1.0, 1.8, 1.0))
    flames_main.append(flame)
    # flame core
    flame_core = smooth_sphere(f"flame_core_{k}", r=0.025, segs=10, rings=8, loc=(0.20, 0.45, 0), parent=arm_p, mat=MAT_FLAME_CORE, scale=(1.0, 1.5, 1.0))
    flames_core.append(flame_core)

# --- tasse de thé avec vapeur -------------------------------
tea_p = empty("tea_cup_p", (-1.5, 0.92, 0.3), parent=table_p)
# cup body
cup_body = smooth_cone("cup_body", r1=0.10, r2=0.13, depth=0.15, segs=20, loc=(0, 0.08, 0), parent=tea_p, mat=MAT_TEA_CUP)
cup_body.rotation_euler = (math.radians(180), 0, 0)
# tea inside (top liquid disc)
tea_liquid = smooth_cone("tea_liquid", r1=0.11, r2=0.11, depth=0.02, segs=18, loc=(0, 0.14, 0), parent=tea_p, mat=MAT_TEA)
tea_liquid.rotation_euler = (math.radians(90), 0, 0)
# saucer
saucer = smooth_cone("saucer", r1=0.20, r2=0.18, depth=0.03, segs=20, loc=(0, 0, 0), parent=tea_p, mat=MAT_TEA_CUP)
saucer.rotation_euler = (math.radians(90), 0, 0)
# handle
handle_p = empty("cup_handle_p", (0.14, 0.10, 0), parent=tea_p)
for k in range(4):
    a = k * (math.pi / 3) - math.pi / 6
    h = smooth_sphere(f"cup_handle_{k}", r=0.015, segs=10, rings=8, loc=(math.cos(a) * 0.04, math.sin(a) * 0.04, 0), parent=handle_p, mat=MAT_TEA_CUP)
# 3 steam puffs rising
steam_puffs = []
for k in range(3):
    py = 0.20 + k * 0.10
    pr = 0.05 + k * 0.02
    puff = smooth_sphere(f"steam_{k}", r=pr, segs=14, rings=10, loc=(0, py, 0), parent=tea_p, mat=MAT_STEAM)
    steam_puffs.append((puff, k))

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

# bow glides back and forth on strings
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    # back and forth motion (using triangular wave for natural look)
    slide = 0.5 * math.sin(tt * math.pi * 4.0)
    base_x = -0.20 + slide
    by = 1.15
    bz = 0.30 + 0.2 * math.cos(tt * math.pi * 4.0)
    kf_loc(bow_p, f, (base_x, by, bz))
    # slight rotation during slide
    rot = math.radians(75) + math.radians(8) * math.sin(tt * math.pi * 4.0)
    kf_rot(bow_p, f, (math.radians(10), 0, rot))

# 4 strings vibrate (subtle scale Z pulse)
for k, string in enumerate(strings):
    phase = k * 0.5
    base_z_scale = 1.0
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.4 * math.sin(tt * math.pi * 30.0 + phase)  # high freq vibration
        kf_scale(string, f, (1.0, 1.0, s))

# 3 candle flames pulse intense
for k, flame in enumerate(flames_main):
    phase = k * 0.4
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.35 * math.sin(tt * math.pi * 10.0 + phase)
        kf_scale(flame, f, (s, 1.8 * s, s))

for k, core in enumerate(flames_core):
    phase = k * 0.4
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 12.0 + phase)
        kf_scale(core, f, (s, 1.5 * s, s))

# volute spiral rotate subtle
for f in range(1, FRAMES + 1, 5):
    tt = (f - 1) / (FRAMES - 1)
    rot = math.radians(5) * math.sin(tt * math.pi * 2.0)
    kf_rot(volute_p, f, (rot, 0, 0))

# right page of sheet music turns
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    # cycle : flat 0→0.5, lift 0.5→0.7, return 0.7→1.0
    local = (tt * 2.0) % 1.0
    if local < 0.5:
        angle = 0
    elif local < 0.7:
        angle = (local - 0.5) / 0.2 * math.radians(150)
    else:
        angle = (1.0 - local) / 0.3 * math.radians(150)
    kf_rot(page_R_p, f, (0, 0, -angle))

# 3 steam puffs rise + scale grow
for puff, k in steam_puffs:
    base_y = 0.20 + k * 0.10
    phase = k * 12
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 50
        lt = local_f / 50
        dy = base_y + lt * 0.30
        dx = math.sin(lt * math.pi * 3.0) * 0.04
        kf_loc(puff, f, (dx, dy, 0))
        s = 0.5 + lt * 1.5
        kf_scale(puff, f, (s, s, s))

# violin subtle bob (resting)
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    by = 0.92 + 0.005 * math.sin(tt * math.pi * 4.0)
    kf_loc(violin, f, (0, by, -0.20))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_violin] wrote {OUT}")
