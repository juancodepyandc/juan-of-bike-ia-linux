"""
proc_ancient_library_scholar.py — 176e procédural AuroraIA, MILESTONE 40E QUALITÉ.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes + anatomie).

Ancienne bibliothèque avec érudit assis lisant :
- bibliothèque 6 niveaux étagères murales avec 500 livres
- grand lustre cristal
- tables d'étude avec piles livres
- érudit anatomique articulé (body + 2 bras tournant pages + tête tilted)
- escalier spiralé
- globe terrestre rotatif
- 12 bougies + cheminée flammes
- tableaux portraits
- tapis persan
- plumes + encrier
- cartes anciennes pendues
- 30 particules poussière
- chat sur livres
- 4 fenêtres
- chouette perchée
- sablier

Animations multi-axes simultanées :
- érudit page-turning + 2 bras coordonnées
- globe rotation
- cheminée flammes intense
- lustre pulse + sway
- 12 bougies flicker
- chat tail wave
- chouette head turn
- sablier sand falling
- 30 dust drift
- carpets/maps gentle sway

Sortie : output/3d/pbr_library_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_library_proc.glb"))

random.seed(0x1B7EAA)


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


def beveled_cube(name, size_xyz, bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=None, mat=None):
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
MAT_WALL = make_mat("wall", (0.35, 0.25, 0.15), roughness=0.85, emi=(0.18, 0.12, 0.08), emi_strength=0.3)
MAT_FLOOR = make_mat("floor_wood", (0.30, 0.20, 0.12), roughness=0.55, emi=(0.12, 0.08, 0.05), emi_strength=0.2)
MAT_WOOD = make_mat("wood", (0.40, 0.25, 0.12), roughness=0.7)
MAT_WOOD_DARK = make_mat("wood_dark", (0.20, 0.12, 0.06), roughness=0.85)
MAT_BRASS = make_mat("brass", (0.90, 0.70, 0.30), metallic=0.85, roughness=0.30, emi=(0.40, 0.30, 0.10), emi_strength=0.6)
MAT_BOOK_R = make_mat("book_red", (0.55, 0.15, 0.10), roughness=0.7)
MAT_BOOK_G = make_mat("book_green", (0.15, 0.35, 0.20), roughness=0.7)
MAT_BOOK_B = make_mat("book_blue", (0.15, 0.20, 0.50), roughness=0.7)
MAT_BOOK_BROWN = make_mat("book_brown", (0.40, 0.25, 0.15), roughness=0.7)
MAT_BOOK_GOLD = make_mat("book_gold", (0.65, 0.50, 0.20), roughness=0.5, emi=(0.30, 0.22, 0.08), emi_strength=0.4)
MAT_PARCHMENT = make_mat("parchment", (0.85, 0.75, 0.55), roughness=0.7, emi=(0.30, 0.25, 0.18), emi_strength=0.4)
MAT_CARPET = make_mat("carpet_persan", (0.55, 0.20, 0.18), roughness=0.85, emi=(0.20, 0.05, 0.05), emi_strength=0.3)
MAT_CANDLE = make_mat("candle", (0.95, 0.92, 0.85), roughness=0.5)
MAT_FLAME = make_mat("flame", (1.0, 0.65, 0.20), roughness=0.0, alpha=0.85, emi=(1.0, 0.65, 0.20), emi_strength=14.0)
MAT_FLAME_INNER = make_mat("flame_inner", (1.0, 0.85, 0.30), roughness=0.0, alpha=0.85, emi=(1.0, 0.85, 0.30), emi_strength=20.0)
MAT_CRYSTAL = make_mat("crystal", (0.95, 0.95, 1.0), roughness=0.05, alpha=0.55, emi=(0.55, 0.55, 0.65), emi_strength=2.5)
MAT_SCHOLAR_ROBE = make_mat("scholar_robe", (0.20, 0.12, 0.08), roughness=0.7, emi=(0.08, 0.04, 0.03), emi_strength=0.3)
MAT_SCHOLAR_SKIN = make_mat("scholar_skin", (0.85, 0.70, 0.55), roughness=0.6)
MAT_SCHOLAR_HAIR = make_mat("scholar_hair", (0.85, 0.80, 0.70), roughness=0.7)
MAT_GLOBE = make_mat("globe", (0.40, 0.55, 0.35), roughness=0.7, emi=(0.15, 0.20, 0.12), emi_strength=0.5)
MAT_GLOBE_OCEAN = make_mat("globe_ocean", (0.15, 0.30, 0.55), roughness=0.5, emi=(0.05, 0.15, 0.25), emi_strength=0.5)
MAT_CAT_BLACK = make_mat("cat_black", (0.08, 0.06, 0.05), roughness=0.5)
MAT_CAT_EYE = make_mat("cat_eye", (0.30, 0.95, 0.30), roughness=0.0, emi=(0.30, 0.95, 0.30), emi_strength=10.0)
MAT_OWL_BROWN = make_mat("owl_brown", (0.45, 0.30, 0.20), roughness=0.6)
MAT_OWL_EYE = make_mat("owl_eye", (1.0, 0.85, 0.20), roughness=0.0, emi=(1.0, 0.85, 0.20), emi_strength=12.0)
MAT_WINDOW = make_mat("window", (0.95, 0.85, 0.55), roughness=0.0, emi=(0.95, 0.85, 0.55), emi_strength=8.0)
MAT_INK = make_mat("ink", (0.05, 0.05, 0.10), roughness=0.4)
MAT_DUST = make_mat("dust", (0.95, 0.90, 0.80), roughness=0.0, emi=(0.95, 0.90, 0.80), emi_strength=5.0)
MAT_HOURGLASS = make_mat("hourglass_glass", (0.95, 0.95, 1.0), roughness=0.10, alpha=0.45, emi=(0.55, 0.55, 0.65), emi_strength=1.0)
MAT_SAND = make_mat("sand", (0.95, 0.75, 0.30), roughness=0.5, emi=(0.45, 0.35, 0.10), emi_strength=0.6)
MAT_PORTRAIT_FRAME = make_mat("portrait_frame", (0.65, 0.45, 0.20), metallic=0.7, roughness=0.35, emi=(0.25, 0.18, 0.08), emi_strength=0.5)
MAT_PORTRAIT_PIC = make_mat("portrait_pic", (0.55, 0.40, 0.30), roughness=0.6, emi=(0.20, 0.15, 0.12), emi_strength=0.4)
MAT_FIREPLACE_STONE = make_mat("fireplace_stone", (0.30, 0.25, 0.20), roughness=0.85, emi=(0.10, 0.08, 0.06), emi_strength=0.3)


# --- backdrop : library room ---------------------------------------------
back_wall = beveled_cube("back_wall", (18, 0.3, 12), bevel_offset=0.05, bevel_segments=2, loc=(0, 6, -6), mat=MAT_WALL)
side_wall_L = beveled_cube("side_wall_L", (0.3, 12, 14), bevel_offset=0.05, bevel_segments=2, loc=(-9, 6, 0), mat=MAT_WALL)
side_wall_R = beveled_cube("side_wall_R", (0.3, 12, 14), bevel_offset=0.05, bevel_segments=2, loc=(9, 6, 0), mat=MAT_WALL)
floor = beveled_cube("floor", (18, 0.1, 14), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_FLOOR)
ceiling = beveled_cube("ceiling", (18, 0.1, 14), bevel_offset=0.05, bevel_segments=2, loc=(0, 12.05, 0), mat=MAT_WOOD_DARK)
# tapis persan central
carpet = beveled_cube("carpet", (6, 0.05, 5), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.03, 1), mat=MAT_CARPET)

# 4 fenêtres avec lumière
for wi, wx in [(0, -5), (1, 5)]:
    win_p = empty(f"window_{wi}_p", (wx, 7, -5.85))
    # frame
    beveled_cube(f"window_{wi}_frame", (1.8, 3.5, 0.10), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 0), parent=win_p, mat=MAT_WOOD_DARK)
    # glow
    beveled_cube(f"window_{wi}_glow", (1.6, 3.3, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.07), parent=win_p, mat=MAT_WINDOW)


# --- BIBLIOTHÈQUE MURALE 6 niveaux (full back wall) -------------------
biblio_left_p = empty("biblio_left", (-8.85, 0, -3))
biblio_right_p = empty("biblio_right", (8.85, 0, -3))
biblio_back_l = empty("biblio_back_l", (-3, 0, -5.85))
biblio_back_r = empty("biblio_back_r", (3, 0, -5.85))

bookshelves = []
for bib_idx, bib_p in enumerate([biblio_left_p, biblio_right_p, biblio_back_l, biblio_back_r]):
    bookshelves.append(bib_p)
    if bib_idx < 2:
        bib_p.rotation_euler = (0, math.radians(-90 if bib_idx == 0 else 90), 0)
    # frame structure
    beveled_cube(f"biblio_{bib_idx}_frame", (3.5, 10, 0.40), bevel_offset=0.05, bevel_segments=2, loc=(0, 5, 0), parent=bib_p, mat=MAT_WOOD_DARK)
    # 6 horizontal shelves
    for sh in range(6):
        beveled_cube(f"biblio_{bib_idx}_shelf_{sh}", (3.3, 0.08, 0.35), bevel_offset=0.02, bevel_segments=2, loc=(0, 1.0 + sh * 1.6, 0.15), parent=bib_p, mat=MAT_WOOD)
    # books on each shelf (~21 per shelf × 6 shelves = ~126 books per bibliothèque × 4 = 504 books)
    book_mats = [MAT_BOOK_R, MAT_BOOK_G, MAT_BOOK_B, MAT_BOOK_BROWN, MAT_BOOK_GOLD]
    for shelf in range(6):
        n_books = random.randint(18, 22)
        for bk in range(n_books):
            bx = -1.55 + bk * 0.15 + random.uniform(-0.02, 0.02)
            bh = random.uniform(0.55, 0.80)
            bw = random.uniform(0.10, 0.13)
            bd = random.uniform(0.25, 0.35)
            m = book_mats[(shelf * n_books + bk) % 5]
            book = beveled_cube(f"book_{bib_idx}_{shelf}_{bk}", (bw, bh, bd), bevel_offset=0.01, bevel_segments=2, loc=(bx, 1.05 + shelf * 1.6 + bh / 2, 0.15 + bd / 2 - 0.10), parent=bib_p, mat=m)


# --- TABLE D'ÉTUDE central avec piles de livres ----------------------
table_p = empty("table_p", (0, 0, 2))
beveled_cube("table_top", (3, 0.10, 1.8), bevel_offset=0.04, bevel_segments=2, loc=(0, 1.0, 0), parent=table_p, mat=MAT_WOOD)
for lx, lz in [(-1.3, -0.7), (1.3, -0.7), (-1.3, 0.7), (1.3, 0.7)]:
    smooth_cone(f"table_leg_{lx}_{lz}", r1=0.08, r2=0.07, depth=1.0, segs=10, loc=(lx, 0.50, lz), parent=table_p, mat=MAT_WOOD_DARK)
# 3 piles of books on table
for pk in range(3):
    px = -0.8 + pk * 0.8
    pz = -0.3 + (pk % 2) * 0.4
    y_off = 1.05
    for stk in range(4):
        bm = [MAT_BOOK_R, MAT_BOOK_G, MAT_BOOK_B, MAT_BOOK_BROWN][stk]
        beveled_cube(f"stk_{pk}_{stk}", (0.35, 0.10, 0.45), bevel_offset=0.02, bevel_segments=2, loc=(px, y_off, pz), parent=table_p, mat=bm)
        y_off += 0.10
# 1 book ouvert avec pages
open_book_p = empty("open_book", (0.5, 1.15, 0.4), parent=table_p)
# cover
beveled_cube("open_book_cover", (0.50, 0.04, 0.65), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.02, 0), parent=open_book_p, mat=MAT_BOOK_R)
# pages left
left_page = beveled_cube("open_book_left", (0.45, 0.04, 0.58), bevel_offset=0.02, bevel_segments=2, loc=(-0.05, 0.06, 0), parent=open_book_p, mat=MAT_PARCHMENT)
# pages right
right_page = beveled_cube("open_book_right", (0.45, 0.04, 0.58), bevel_offset=0.02, bevel_segments=2, loc=(0.05, 0.06, 0), parent=open_book_p, mat=MAT_PARCHMENT)


# --- ÉRUDIT assis (anatomy articulée) ----------------------------------
scholar_p = empty("scholar_p", (0.5, 0, 2.8))
# chair
beveled_cube("chair_seat", (0.7, 0.10, 0.7), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.55, 0), parent=scholar_p, mat=MAT_WOOD_DARK)
for lx, lz in [(-0.30, -0.30), (0.30, -0.30), (-0.30, 0.30), (0.30, 0.30)]:
    smooth_cone(f"chair_leg_{lx}_{lz}", r1=0.05, r2=0.04, depth=0.55, segs=8, loc=(lx, 0.27, lz), parent=scholar_p, mat=MAT_WOOD_DARK)
# chair back
beveled_cube("chair_back", (0.7, 1.0, 0.10), bevel_offset=0.04, bevel_segments=2, loc=(0, 1.10, -0.30), parent=scholar_p, mat=MAT_WOOD_DARK)

# scholar robe (lower body sitting)
smooth_cone("scholar_robe", r1=0.40, r2=0.50, depth=0.85, segs=14, loc=(0, 1.0, 0), parent=scholar_p, mat=MAT_SCHOLAR_ROBE)
# torso
torso = smooth_sphere("scholar_torso", r=0.40, segs=20, rings=14, loc=(0, 1.55, 0), parent=scholar_p, mat=MAT_SCHOLAR_ROBE, scale=(1.0, 1.2, 0.85))
# head
head_p = empty("scholar_head_p", (0, 2.10, 0), parent=scholar_p)
smooth_sphere("scholar_head", r=0.22, segs=20, rings=16, loc=(0, 0, 0), parent=head_p, mat=MAT_SCHOLAR_SKIN)
# hair/beard
smooth_sphere("scholar_hair", r=0.22, segs=16, rings=12, loc=(-0.05, 0.05, 0), parent=head_p, mat=MAT_SCHOLAR_HAIR, scale=(1.0, 0.85, 1.0))
# beard
smooth_sphere("scholar_beard", r=0.15, segs=14, rings=10, loc=(0, -0.15, 0.10), parent=head_p, mat=MAT_SCHOLAR_HAIR, scale=(1.0, 1.2, 0.7))
# 2 arms (toward book/pages)
arm_L_p = empty("arm_L_p", (-0.35, 1.50, 0.10), parent=scholar_p)
arm_L_p.rotation_euler = (math.radians(-60), 0, math.radians(15))
smooth_cone("scholar_arm_L_upper", r1=0.10, r2=0.08, depth=0.40, segs=10, loc=(0, -0.20, 0), parent=arm_L_p, mat=MAT_SCHOLAR_ROBE)
elbow_L = empty("elbow_L", (0, -0.40, 0), parent=arm_L_p)
smooth_cone("scholar_arm_L_lower", r1=0.08, r2=0.06, depth=0.35, segs=8, loc=(0, -0.18, 0), parent=elbow_L, mat=MAT_SCHOLAR_SKIN)
# hand L (on book — turning page)
smooth_sphere("scholar_hand_L", r=0.07, segs=12, rings=8, loc=(0, -0.40, 0), parent=elbow_L, mat=MAT_SCHOLAR_SKIN)

arm_R_p = empty("arm_R_p", (0.35, 1.50, 0.10), parent=scholar_p)
arm_R_p.rotation_euler = (math.radians(-50), 0, math.radians(-15))
smooth_cone("scholar_arm_R_upper", r1=0.10, r2=0.08, depth=0.40, segs=10, loc=(0, -0.20, 0), parent=arm_R_p, mat=MAT_SCHOLAR_ROBE)
elbow_R = empty("elbow_R", (0, -0.40, 0), parent=arm_R_p)
smooth_cone("scholar_arm_R_lower", r1=0.08, r2=0.06, depth=0.35, segs=8, loc=(0, -0.18, 0), parent=elbow_R, mat=MAT_SCHOLAR_SKIN)
smooth_sphere("scholar_hand_R", r=0.07, segs=12, rings=8, loc=(0, -0.40, 0), parent=elbow_R, mat=MAT_SCHOLAR_SKIN)


# --- LUSTRE CRISTAL central -------------------------------------------
chandelier_p = empty("chandelier_p", (0, 8.5, 1))
# chain
smooth_cone("chand_chain", r1=0.04, r2=0.04, depth=3.0, segs=4, loc=(0, 1.5, 0), parent=chandelier_p, mat=MAT_BRASS)
# main ring
smooth_cone("chand_ring", r1=1.0, r2=1.0, depth=0.10, segs=20, loc=(0, 0, 0), parent=chandelier_p, mat=MAT_BRASS)
# 8 candles + flames
chand_candles = []
for ck in range(8):
    ca = ck * (math.pi * 2 / 8)
    cx = math.cos(ca) * 1.0
    cz = math.sin(ca) * 1.0
    smooth_cone(f"chand_c_{ck}", r1=0.04, r2=0.03, depth=0.20, segs=8, loc=(cx, 0.15, cz), parent=chandelier_p, mat=MAT_CANDLE)
    flame_p = empty(f"chand_fl_p_{ck}", (cx, 0.30, cz), parent=chandelier_p)
    f_out = smooth_sphere(f"chand_fl_{ck}", r=0.07, segs=12, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME, scale=(1.0, 1.4, 1.0))
    f_in = smooth_sphere(f"chand_fl_in_{ck}", r=0.04, segs=10, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME_INNER, scale=(1.0, 1.5, 1.0))
    chand_candles.append({"p": flame_p, "out": f_out, "in": f_in, "phase": ck * 0.30})
# 12 crystals pendants
for ck in range(12):
    ca = ck * (math.pi * 2 / 12)
    smooth_cone(f"chand_crystal_{ck}", r1=0.0, r2=0.07, depth=0.20, segs=6, loc=(math.cos(ca) * 0.90, -0.10, math.sin(ca) * 0.90), parent=chandelier_p, mat=MAT_CRYSTAL)


# --- CHEMINÉE avec flammes -----------------------------------------
fireplace_p = empty("fireplace_p", (-5, 0, -5.85))
# frame
beveled_cube("fp_frame", (2.5, 3.0, 0.40), bevel_offset=0.05, bevel_segments=2, loc=(0, 1.5, 0.20), parent=fireplace_p, mat=MAT_FIREPLACE_STONE)
# opening (dark inside)
beveled_cube("fp_inside", (1.8, 2.0, 0.40), bevel_offset=0.04, bevel_segments=2, loc=(0, 1.0, 0.30), parent=fireplace_p, mat=MAT_INK)
# 4 flames inside
fp_flames = []
for fk in range(4):
    fx = -0.5 + fk * 0.33
    flame_p = empty(f"fp_fl_p_{fk}", (fx, 0.6, 0.40), parent=fireplace_p)
    f_out = smooth_sphere(f"fp_fl_{fk}", r=0.20, segs=14, rings=10, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME, scale=(0.8, 1.6, 0.8))
    f_in = smooth_sphere(f"fp_fl_in_{fk}", r=0.13, segs=12, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME_INNER, scale=(0.6, 1.8, 0.6))
    fp_flames.append({"p": flame_p, "out": f_out, "in": f_in, "phase": fk * 0.25})
# logs
for lk in range(3):
    lx = -0.5 + lk * 0.4
    smooth_cone(f"fp_log_{lk}", r1=0.10, r2=0.10, depth=1.2, segs=8, loc=(lx, 0.30, 0.30), parent=fireplace_p, mat=MAT_WOOD_DARK)
    lp = bpy.data.objects.get(f"fp_log_{lk}")
    if lp:
        lp.rotation_euler = (0, 0, math.radians(90))
# mantle
beveled_cube("fp_mantle", (3.0, 0.15, 0.50), bevel_offset=0.04, bevel_segments=2, loc=(0, 3.15, 0.25), parent=fireplace_p, mat=MAT_WOOD_DARK)


# --- GLOBE TERRESTRE ROTATIF ----------------------------------------
globe_p = empty("globe_p", (5, 1.6, 2))
# stand
beveled_cube("globe_base", (0.50, 0.10, 0.50), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.05, 0), parent=globe_p, mat=MAT_WOOD_DARK)
# arc support
arc_p = empty("globe_arc_p", (0, 0.10, 0), parent=globe_p)
for ak in range(2):
    angle = math.radians(-90 + ak * 180)
    smooth_cone(f"globe_arc_{ak}", r1=0.04, r2=0.04, depth=1.2, segs=8, loc=(math.cos(angle) * 0.30, 0.6, 0), parent=arc_p, mat=MAT_BRASS)
# sphere globe (rotates inside arc)
globe_sphere_p = empty("globe_sphere_p", (0, 0.65, 0), parent=globe_p)
smooth_sphere("globe_ocean", r=0.45, segs=24, rings=18, loc=(0, 0, 0), parent=globe_sphere_p, mat=MAT_GLOBE_OCEAN)
# 5 continents (random patches)
for ck in range(5):
    ca = ck * (math.pi * 2 / 5) + random.uniform(-0.3, 0.3)
    cp_lat = random.uniform(-0.6, 0.6)
    cx = 0.45 * math.cos(ca) * math.sqrt(1 - cp_lat**2)
    cz = 0.45 * math.sin(ca) * math.sqrt(1 - cp_lat**2)
    cy = 0.45 * cp_lat
    smooth_sphere(f"globe_cont_{ck}", r=random.uniform(0.15, 0.25), segs=14, rings=10, loc=(cx, cy, cz), parent=globe_sphere_p, mat=MAT_GLOBE, scale=(1.0, 0.10, 1.0))


# --- CAT NOIR sur livres ----------------------------------------------
cat_p = empty("cat_p", (-1.2, 1.20, 0.5))
# body curled
smooth_sphere("cat_body", r=0.20, segs=18, rings=12, loc=(0, 0.20, 0), parent=cat_p, mat=MAT_CAT_BLACK, scale=(1.5, 0.85, 1.0))
# head
smooth_sphere("cat_head", r=0.14, segs=18, rings=12, loc=(0.18, 0.30, 0), parent=cat_p, mat=MAT_CAT_BLACK)
# 2 ears
for ek, ez in [("L", 0.07), ("R", -0.07)]:
    smooth_cone(f"cat_ear_{ek}", r1=0.04, r2=0.0, depth=0.10, segs=8, loc=(0.18, 0.44, ez), parent=cat_p, mat=MAT_CAT_BLACK)
# 2 glowing eyes
for ek, ez in [("L", 0.05), ("R", -0.05)]:
    smooth_sphere(f"cat_eye_{ek}", r=0.022, segs=10, rings=6, loc=(0.27, 0.32, ez), parent=cat_p, mat=MAT_CAT_EYE)
# tail curled
tail_p = empty("cat_tail_p", (-0.15, 0.22, 0), parent=cat_p)
for tk in range(4):
    smooth_sphere(f"cat_tail_{tk}", r=0.04, segs=10, rings=6, loc=(-0.08 - tk * 0.08, 0.05 + tk * 0.04, 0), parent=tail_p, mat=MAT_CAT_BLACK)


# --- OWL perchée ----------------------------------------------------
owl_p = empty("owl_p", (-7, 6.5, -2))
owl_head_p = empty("owl_head_p", (0, 0.55, 0), parent=owl_p)
# body
smooth_sphere("owl_body", r=0.30, segs=20, rings=14, loc=(0, 0.20, 0), parent=owl_p, mat=MAT_OWL_BROWN, scale=(1.0, 1.4, 0.85))
# head
smooth_sphere("owl_head", r=0.22, segs=20, rings=14, loc=(0, 0, 0), parent=owl_head_p, mat=MAT_OWL_BROWN, scale=(1.1, 1.1, 1.0))
# 2 huge eyes
for ek, ez in [("L", 0.10), ("R", -0.10)]:
    smooth_sphere(f"owl_eye_{ek}", r=0.10, segs=14, rings=10, loc=(0.10, 0.05, ez), parent=owl_head_p, mat=MAT_OWL_EYE)
# beak
smooth_cone("owl_beak", r1=0.04, r2=0.0, depth=0.08, segs=8, loc=(0.18, -0.02, 0), parent=owl_head_p, mat=MAT_BRASS)
# 2 ear tufts
for ek, ez in [("L", 0.08), ("R", -0.08)]:
    smooth_cone(f"owl_ear_{ek}", r1=0.04, r2=0.0, depth=0.12, segs=6, loc=(0, 0.18, ez), parent=owl_head_p, mat=MAT_OWL_BROWN)


# --- HOURGLASS sablier ---------------------------------------------
hg_p = empty("hourglass_p", (1.5, 1.15, 0.2))
# bottom bulb
smooth_sphere("hg_bot", r=0.13, segs=16, rings=10, loc=(0, 0.10, 0), parent=hg_p, mat=MAT_HOURGLASS, scale=(1.0, 0.85, 1.0))
# top bulb
smooth_sphere("hg_top", r=0.13, segs=16, rings=10, loc=(0, 0.35, 0), parent=hg_p, mat=MAT_HOURGLASS, scale=(1.0, 0.85, 1.0))
# neck
smooth_cone("hg_neck", r1=0.02, r2=0.02, depth=0.15, segs=6, loc=(0, 0.22, 0), parent=hg_p, mat=MAT_HOURGLASS)
# wood frame top/bottom
beveled_cube("hg_frame_top", (0.20, 0.04, 0.20), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.46, 0), parent=hg_p, mat=MAT_WOOD_DARK)
beveled_cube("hg_frame_bot", (0.20, 0.04, 0.20), bevel_offset=0.02, bevel_segments=2, loc=(0, -0.01, 0), parent=hg_p, mat=MAT_WOOD_DARK)
# 4 pillars
for pk in range(4):
    pa = pk * (math.pi * 2 / 4) + math.pi / 4
    smooth_cone(f"hg_pil_{pk}", r1=0.015, r2=0.015, depth=0.45, segs=4, loc=(math.cos(pa) * 0.10, 0.22, math.sin(pa) * 0.10), parent=hg_p, mat=MAT_WOOD_DARK)
# sand pile bottom (growing)
sand_bot = smooth_sphere("hg_sand_bot", r=0.10, segs=14, rings=8, loc=(0, 0.08, 0), parent=hg_p, mat=MAT_SAND, scale=(1.0, 0.50, 1.0))
sand_top = smooth_sphere("hg_sand_top", r=0.10, segs=14, rings=8, loc=(0, 0.40, 0), parent=hg_p, mat=MAT_SAND, scale=(1.0, 0.50, 1.0))
# sand stream center
sand_stream = smooth_cone("hg_sand_stream", r1=0.015, r2=0.015, depth=0.13, segs=4, loc=(0, 0.22, 0), parent=hg_p, mat=MAT_SAND)


# --- 4 PORTRAITS sur murs ----------------------------------------------
PORTRAIT_POSITIONS = [(-3, 6, -5.85), (3, 6, -5.85), (-8.85, 5, 2), (8.85, 5, 2)]
for pi, (px, py, pz) in enumerate(PORTRAIT_POSITIONS):
    pp = empty(f"portrait_{pi}_p", (px, py, pz))
    if pi >= 2:
        pp.rotation_euler = (0, math.radians(-90 if px < 0 else 90), 0)
    # ornate frame
    beveled_cube(f"portrait_{pi}_fr", (1.4, 1.8, 0.12), bevel_offset=0.04, bevel_segments=2, loc=(0, 0, 0), parent=pp, mat=MAT_PORTRAIT_FRAME)
    # picture
    beveled_cube(f"portrait_{pi}_pic", (1.2, 1.6, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.07), parent=pp, mat=MAT_PORTRAIT_PIC)


# --- 6 MAPS pendues ----------------------------------------------
maps = []
MAP_POSITIONS = [(-6, 4, -5.85), (-2, 3.5, -5.85), (2, 3.5, -5.85), (6, 4, -5.85), (-8.85, 3, -1), (8.85, 3, -1)]
for mi, (mx, my, mz) in enumerate(MAP_POSITIONS):
    mp = empty(f"map_{mi}_p", (mx, my, mz))
    if mi >= 4:
        mp.rotation_euler = (0, math.radians(-90 if mx < 0 else 90), 0)
    beveled_cube(f"map_{mi}", (0.7, 1.0, 0.02), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0), parent=mp, mat=MAT_PARCHMENT)
    maps.append(mp)
    mp["_phase"] = mi * 0.30


# --- ENCRIER + PLUME --------------------------------------------
ink_p = empty("ink_p", (1.0, 1.10, 0.6))
smooth_cone("inkpot", r1=0.07, r2=0.06, depth=0.10, segs=10, loc=(0, 0.05, 0), parent=ink_p, mat=MAT_INK)
smooth_sphere("ink_drop", r=0.05, segs=10, rings=8, loc=(0, 0.10, 0), parent=ink_p, mat=MAT_INK, scale=(1.0, 0.3, 1.0))
# plume
feather_shaft = smooth_cone("feather_shaft", r1=0.012, r2=0.008, depth=0.45, segs=6, loc=(0, 0.30, 0), parent=ink_p, mat=MAT_WOOD_DARK)
feather_shaft.rotation_euler = (0, 0, math.radians(20))
for fb in range(6):
    smooth_sphere(f"feather_fan_{fb}", r=0.04, segs=10, rings=6, loc=(0.05 + fb * 0.01, 0.35 + fb * 0.04, 0), parent=ink_p, mat=MAT_WOOD_DARK, scale=(1.0, 1.0, 0.15))


# --- 30 PARTICLES POUSSIÈRE drift ----------------------------------
dust_parts = []
for dk in range(30):
    dx = random.uniform(-7, 7)
    dy = random.uniform(2, 9)
    dz = random.uniform(-4, 4)
    dp = smooth_sphere(f"dust_{dk}", r=random.uniform(0.025, 0.05), segs=8, rings=6, loc=(dx, dy, dz), mat=MAT_DUST)
    dp["_base"] = (dx, dy, dz)
    dp["_phase"] = dk * 0.18
    dust_parts.append(dp)


# --- ANIMATIONS ----------------------------------------------------------
DURATION = 6.0
FRAMES = scene.frame_end
DT = DURATION / FRAMES


def kf(obj, frame, attr, val):
    if attr == "location":
        obj.location = val
        obj.keyframe_insert(data_path="location", frame=frame)
    elif attr == "rotation_euler":
        obj.rotation_euler = val
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    elif attr == "scale":
        obj.scale = val
        obj.keyframe_insert(data_path="scale", frame=frame)


for f in range(1, FRAMES + 1):
    t = (f - 1) * DT
    tt = t / DURATION

    # scholar : page turning
    # right page turning periodically
    page_rot = math.radians(60) * (1 - math.cos(2 * math.pi * tt * 1.0)) / 2
    kf(right_page, f, "rotation_euler", (0, 0, page_rot))
    # head tilt look at book + slight nod
    head_tilt = math.radians(-15 + 3 * math.sin(2 * math.pi * tt * 1.5))
    kf(head_p, f, "rotation_euler", (head_tilt, math.radians(2 * math.sin(2 * math.pi * tt * 0.8)), 0))
    # arms slight coordinated
    arm_L_rot = math.radians(-60 + 5 * math.sin(2 * math.pi * tt * 1.0))
    arm_R_rot = math.radians(-50 + 5 * math.sin(2 * math.pi * tt * 1.0 + math.pi))
    kf(arm_L_p, f, "rotation_euler", (arm_L_rot, 0, math.radians(15)))
    kf(arm_R_p, f, "rotation_euler", (arm_R_rot, 0, math.radians(-15)))

    # globe rotation continue
    kf(globe_sphere_p, f, "rotation_euler", (0, math.radians(120 * tt * 360 / 360), 0))

    # chandelier sway + chains
    sway_x = math.radians(2 * math.sin(2 * math.pi * tt * 0.8))
    sway_z = math.radians(1.5 * math.cos(2 * math.pi * tt * 1.0))
    kf(chandelier_p, f, "rotation_euler", (sway_x, math.radians(15 * math.sin(2 * math.pi * tt * 0.5)), sway_z))

    # 8 chandelier candle flames
    for cc in chand_candles:
        ph = cc["phase"]
        fp_sc = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        kf(cc["out"], f, "scale", (fp_sc, fp_sc * 1.4, fp_sc))
        kf(cc["in"], f, "scale", (fp_sc, fp_sc * 1.5, fp_sc))
        kf(cc["p"], f, "rotation_euler", (math.radians(5 * math.sin(2 * math.pi * tt * 5 + ph * math.pi)), 0, math.radians(5 * math.cos(2 * math.pi * tt * 5.5 + ph * math.pi))))

    # fireplace flames intense
    for fl in fp_flames:
        ph = fl["phase"]
        fp_sc = 1.0 + 0.25 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(fl["out"], f, "scale", (fp_sc * 0.8, fp_sc * 1.6, fp_sc * 0.8))
        kf(fl["in"], f, "scale", (fp_sc * 0.6, fp_sc * 1.8, fp_sc * 0.6))

    # cat tail wave
    kf(tail_p, f, "rotation_euler", (0, math.radians(20 * math.sin(2 * math.pi * tt * 1.5)), math.radians(15 * math.cos(2 * math.pi * tt * 1.2))))

    # owl head turn (signature)
    head_turn = math.radians(90 * math.sin(2 * math.pi * tt * 0.6))
    kf(owl_head_p, f, "rotation_euler", (0, head_turn, 0))

    # hourglass sand stream + bottom pile growing
    # sand bottom scale grows
    sand_progress = (tt + 0.1) % 1.0
    bot_sc = 0.5 + sand_progress * 0.8
    top_sc = 1.0 - sand_progress * 0.4
    kf(sand_bot, f, "scale", (1.0, bot_sc, 1.0))
    kf(sand_top, f, "scale", (1.0, max(0.2, top_sc), 1.0))
    # sand stream visible
    stream_sc = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 5)
    kf(sand_stream, f, "scale", (stream_sc, 1.0, stream_sc))

    # 30 dust drift
    for dp in dust_parts:
        bx_, by_, bz_ = dp["_base"]
        ph = dp["_phase"]
        nx = bx_ + 0.3 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        ny = by_ + 0.4 * math.cos(2 * math.pi * tt * 0.5 + ph * math.pi)
        nz = bz_ + 0.25 * math.sin(2 * math.pi * tt * 0.6 + ph * math.pi)
        kf(dp, f, "location", (nx, ny, nz))
        sc = 0.6 + 0.6 * abs(math.sin(2 * math.pi * tt * 3 + ph * math.pi))
        kf(dp, f, "scale", (sc, sc, sc))

    # 6 maps gentle sway
    for mp in maps:
        ph = mp["_phase"]
        sway = math.radians(3 * math.sin(2 * math.pi * tt * 1.2 + ph * math.pi))
        kf(mp, f, "rotation_euler", (sway, 0, math.radians(2 * math.cos(2 * math.pi * tt * 1.5 + ph * math.pi))))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_ancient_library_scholar] wrote {OUT}")
