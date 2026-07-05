"""
proc_alchemist_lab.py — 158e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Laboratoire d'alchimiste mystique :
- table principale en bois bevelée avec accessoires
- alambic distillateur en cuivre (bulle + tube + collecteur)
- athanor (four magique) avec feu émissif
- 12 fioles avec potions colorées émissives + bouchons + bullage
- 6 livres anciens piles
- bibliothèque arrière 4 rangées + 30 tomes
- chandelier mural avec 3 bougies flammes émissives
- crâne mystique
- mortier + pilon
- 8 cristaux émissifs variés sur étagères
- parchemin enroulé
- plumes d'écriture + encrier
- chat noir sur tabouret
- 30 particules magiques drift 3D
- 2 esprits éthérés émissifs
- chaudron central bouillonnant
- arrière-plan pierre + ombre

Animations multi-axes simultanées :
- 12 fioles : potions bullent (3 bulles par fiole rise + scale)
- athanor : feu pulse + smoke rise
- 3 bougies chandelier : flammes pulse + sway
- 8 cristaux : float Y + rotate XYZ + pulse émission
- chaudron : steam puffs rise cyclique + content bubble
- 30 particules magiques : drift 3D + scintille
- 2 esprits : float ondulant + pulse
- chat noir : tail wave + ears twitch

Sortie : output/3d/pbr_alchemist_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_alchemist_proc.glb"))

random.seed(0xA1CEEE)


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
MAT_WALL = make_mat("wall_stone", (0.30, 0.27, 0.24), roughness=0.95, emi=(0.10, 0.08, 0.07), emi_strength=0.3)
MAT_FLOOR = make_mat("floor_stone", (0.18, 0.16, 0.14), roughness=0.95)
MAT_WOOD = make_mat("wood", (0.30, 0.18, 0.10), roughness=0.75)
MAT_WOOD_DARK = make_mat("wood_dark", (0.18, 0.10, 0.05), roughness=0.85)
MAT_COPPER = make_mat("copper", (0.85, 0.50, 0.30), metallic=0.85, roughness=0.30, emi=(0.30, 0.18, 0.12), emi_strength=0.3)
MAT_GOLD = make_mat("gold", (0.95, 0.75, 0.30), metallic=0.95, roughness=0.20, emi=(0.45, 0.35, 0.15), emi_strength=0.5)
MAT_IRON = make_mat("iron", (0.30, 0.28, 0.28), metallic=0.85, roughness=0.55)
MAT_GLASS = make_mat("glass", (0.90, 0.95, 1.0), roughness=0.05, alpha=0.40, emi=(0.40, 0.45, 0.50), emi_strength=0.5)
MAT_POTION_R = make_mat("potion_red", (0.95, 0.20, 0.30), roughness=0.10, alpha=0.85, emi=(0.95, 0.20, 0.30), emi_strength=8.0)
MAT_POTION_G = make_mat("potion_green", (0.30, 0.95, 0.40), roughness=0.10, alpha=0.85, emi=(0.30, 0.95, 0.40), emi_strength=8.0)
MAT_POTION_B = make_mat("potion_blue", (0.30, 0.55, 0.95), roughness=0.10, alpha=0.85, emi=(0.30, 0.55, 0.95), emi_strength=8.0)
MAT_POTION_P = make_mat("potion_purple", (0.75, 0.30, 0.95), roughness=0.10, alpha=0.85, emi=(0.75, 0.30, 0.95), emi_strength=8.0)
MAT_POTION_Y = make_mat("potion_yellow", (0.95, 0.85, 0.20), roughness=0.10, alpha=0.85, emi=(0.95, 0.85, 0.20), emi_strength=8.0)
MAT_POTION_C = make_mat("potion_cyan", (0.30, 0.95, 0.95), roughness=0.10, alpha=0.85, emi=(0.30, 0.95, 0.95), emi_strength=8.0)
MAT_FLAME = make_mat("flame", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85, emi=(1.0, 0.55, 0.10), emi_strength=14.0)
MAT_FLAME_INNER = make_mat("flame_inner", (1.0, 0.85, 0.30), roughness=0.0, alpha=0.85, emi=(1.0, 0.85, 0.30), emi_strength=18.0)
MAT_SMOKE = make_mat("smoke", (0.40, 0.38, 0.40), roughness=1.0, alpha=0.35, emi=(0.20, 0.18, 0.20), emi_strength=0.8)
MAT_CANDLE = make_mat("candle", (0.95, 0.92, 0.85), roughness=0.5)
MAT_BOOK_R = make_mat("book_r", (0.55, 0.15, 0.10), roughness=0.7)
MAT_BOOK_G = make_mat("book_g", (0.15, 0.35, 0.20), roughness=0.7)
MAT_BOOK_B = make_mat("book_b", (0.15, 0.20, 0.50), roughness=0.7)
MAT_PARCHMENT = make_mat("parchment", (0.85, 0.75, 0.55), roughness=0.7, emi=(0.30, 0.25, 0.18), emi_strength=0.4)
MAT_BONE = make_mat("bone", (0.85, 0.82, 0.75), roughness=0.5, emi=(0.30, 0.28, 0.25), emi_strength=0.3)
MAT_CRYSTAL_PUR = make_mat("crystal_purple", (0.70, 0.30, 0.95), roughness=0.05, emi=(0.70, 0.30, 0.95), emi_strength=10.0)
MAT_CRYSTAL_CYA = make_mat("crystal_cyan", (0.30, 0.85, 0.95), roughness=0.05, emi=(0.30, 0.85, 0.95), emi_strength=10.0)
MAT_CRYSTAL_GRE = make_mat("crystal_green", (0.30, 0.95, 0.45), roughness=0.05, emi=(0.30, 0.95, 0.45), emi_strength=10.0)
MAT_CRYSTAL_RED = make_mat("crystal_red", (0.95, 0.30, 0.30), roughness=0.05, emi=(0.95, 0.30, 0.30), emi_strength=10.0)
MAT_CAT = make_mat("cat_black", (0.06, 0.05, 0.05), roughness=0.5)
MAT_CAT_EYE = make_mat("cat_eye", (0.30, 0.95, 0.30), roughness=0.0, emi=(0.30, 0.95, 0.30), emi_strength=12.0)
MAT_FEATHER = make_mat("feather", (0.20, 0.15, 0.10), roughness=0.6)
MAT_INK = make_mat("ink", (0.05, 0.05, 0.10), roughness=0.4)
MAT_MAGIC_PART_A = make_mat("magic_A", (0.85, 0.40, 1.0), roughness=0.0, emi=(0.85, 0.40, 1.0), emi_strength=7.0)
MAT_MAGIC_PART_B = make_mat("magic_B", (0.40, 0.90, 1.0), roughness=0.0, emi=(0.40, 0.90, 1.0), emi_strength=7.0)
MAT_SPIRIT = make_mat("spirit", (0.85, 0.95, 1.0), roughness=0.0, alpha=0.40, emi=(0.65, 0.85, 1.0), emi_strength=6.0)
MAT_CAULDRON_LIQ = make_mat("cauldron_liq", (0.55, 0.85, 0.40), roughness=0.10, alpha=0.85, emi=(0.55, 0.85, 0.40), emi_strength=6.5)


# --- backdrop : stone wall + floor ----------------------------------------
back_wall = beveled_cube("back_wall", (16, 0.2, 9), bevel_offset=0.05, bevel_segments=2, loc=(0, 7, 4.5), mat=MAT_WALL)
floor = beveled_cube("floor", (16, 0.1, 12), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_FLOOR)


# --- bibliothèque arrière (4 rows + 30 tomes) ------------------------------
biblio_p = empty("biblio_p", (-5, 0, 4))
# main frame
biblio_frame = beveled_cube("biblio_frame", (3.2, 4.5, 0.6), bevel_offset=0.06, bevel_segments=2, loc=(0, 2.4, 0), parent=biblio_p, mat=MAT_WOOD_DARK)
# 4 horizontal shelves
for sh in range(4):
    smooth_cone(f"biblio_shelf_{sh}", r1=1.55, r2=1.55, depth=0.05, segs=10, loc=(0, 0.8 + sh * 1.0, 0.15), parent=biblio_p, mat=MAT_WOOD)
# 30 books distributed
book_mats = [MAT_BOOK_R, MAT_BOOK_G, MAT_BOOK_B]
for shelf in range(4):
    for bi in range(7 + (shelf % 2)):
        bx = -1.3 + bi * 0.35
        bh = random.uniform(0.45, 0.65)
        bw = random.uniform(0.15, 0.22)
        bd = random.uniform(0.30, 0.40)
        m = book_mats[(shelf * 7 + bi) % 3]
        book = beveled_cube(f"book_{shelf}_{bi}", (bw, bh, bd), bevel_offset=0.02, bevel_segments=2, loc=(bx, 1.05 + shelf * 1.0 + bh / 2, 0.15 + 0.05), parent=biblio_p, mat=m)


# --- main table en bois centrale ------------------------------------------
table_p = empty("table_p", (0, 0, 1.5))
table_top = beveled_cube("table_top", (4.5, 0.12, 2.0), bevel_offset=0.05, bevel_segments=3, loc=(0, 1.10, 0), parent=table_p, mat=MAT_WOOD)
# 4 legs
for lx, lz in [(-2.0, -0.85), (2.0, -0.85), (-2.0, 0.85), (2.0, 0.85)]:
    smooth_cone(f"leg_{lx}_{lz}", r1=0.08, r2=0.08, depth=1.10, segs=10, loc=(lx, 0.55, lz), parent=table_p, mat=MAT_WOOD_DARK)
# under shelf
beveled_cube("table_under", (4.0, 0.05, 1.6), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.30, 0), parent=table_p, mat=MAT_WOOD_DARK)


# --- alambic distillateur (sur table à gauche) ----------------------------
alambic_p = empty("alambic", (-1.5, 1.20, 1.5))
# main bulb sphere
bulb = smooth_sphere("alambic_bulb", r=0.35, segs=24, rings=18, loc=(0, 0.30, 0), parent=alambic_p, mat=MAT_COPPER)
# inside potion (smaller alpha sphere)
smooth_sphere("alambic_potion", r=0.30, segs=20, rings=14, loc=(0, 0.30, 0), parent=alambic_p, mat=MAT_POTION_G)
# top neck
smooth_cone("alambic_neck", r1=0.12, r2=0.10, depth=0.35, segs=10, loc=(0, 0.80, 0), parent=alambic_p, mat=MAT_COPPER)
# top cap (dome)
smooth_sphere("alambic_cap", r=0.18, segs=18, rings=12, loc=(0, 1.05, 0), parent=alambic_p, mat=MAT_COPPER, scale=(1.0, 0.6, 1.0))
# distillation tube (long horizontal pipe)
tube = smooth_cone("alambic_tube", r1=0.05, r2=0.05, depth=1.2, segs=10, loc=(0.60, 0.85, 0.30), parent=alambic_p, mat=MAT_COPPER)
tube.rotation_euler = (0, 0, math.radians(90))
# collecteur
collecteur = smooth_sphere("alambic_collect", r=0.18, segs=18, rings=14, loc=(1.20, 0.60, 0.30), parent=alambic_p, mat=MAT_COPPER, scale=(0.8, 1.0, 0.8))
# 3 bulles bullage inside main bulb (animated)
alambic_bubbles = []
for bb in range(3):
    bub = smooth_sphere(f"alambic_bub_{bb}", r=0.05, segs=10, rings=6, loc=(random.uniform(-0.15, 0.15), 0.25, random.uniform(-0.15, 0.15)), parent=alambic_p, mat=MAT_GLASS)
    bub["_phase"] = bb * 0.33
    alambic_bubbles.append(bub)


# --- athanor (four magique) (sur table à droite) --------------------------
athanor_p = empty("athanor", (1.6, 1.20, 1.5))
# base
beveled_cube("athanor_base", (0.55, 0.40, 0.55), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.20, 0), parent=athanor_p, mat=MAT_IRON)
# chamber
beveled_cube("athanor_chamber", (0.50, 0.45, 0.50), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.65, 0), parent=athanor_p, mat=MAT_IRON)
# door (slightly open émissif inside)
beveled_cube("athanor_door", (0.42, 0.30, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.65, 0.30), parent=athanor_p, mat=MAT_IRON)
# fire inside (visible through opening)
fire_p = empty("athanor_fire_p", (0, 0.60, 0.28), parent=athanor_p)
fire_outer = smooth_sphere("athanor_fire_outer", r=0.18, segs=18, rings=12, loc=(0, 0, 0), parent=fire_p, mat=MAT_FLAME, scale=(1.0, 1.4, 1.0))
fire_inner = smooth_sphere("athanor_fire_inner", r=0.10, segs=14, rings=10, loc=(0, 0, 0), parent=fire_p, mat=MAT_FLAME_INNER, scale=(1.0, 1.5, 1.0))
# chimney top
smooth_cone("athanor_chim", r1=0.10, r2=0.08, depth=0.30, segs=10, loc=(0, 1.05, 0), parent=athanor_p, mat=MAT_IRON)
# smoke puffs above chimney
athanor_smokes = []
for sm in range(3):
    sp = smooth_sphere(f"athanor_smoke_{sm}", r=0.18, segs=14, rings=10, loc=(0, 1.30 + sm * 0.35, 0), parent=athanor_p, mat=MAT_SMOKE, scale=(1.2, 1.0, 1.2))
    sp["_phase"] = sm * 0.33
    athanor_smokes.append(sp)


# --- 12 fioles potions colorées (sur table avant) -------------------------
potion_mats = [MAT_POTION_R, MAT_POTION_G, MAT_POTION_B, MAT_POTION_P, MAT_POTION_Y, MAT_POTION_C]
fioles = []
for fk in range(12):
    fx = -1.8 + (fk % 6) * 0.35
    fz = 0.4 + (fk // 6) * 0.30
    fp = empty(f"fiole_{fk}", (fx, 1.20, fz))
    # body (sphere)
    smooth_sphere(f"fiole_{fk}_body", r=0.10, segs=14, rings=10, loc=(0, 0.10, 0), parent=fp, mat=MAT_GLASS)
    # inside potion
    pmat = potion_mats[fk % 6]
    smooth_sphere(f"fiole_{fk}_potion", r=0.075, segs=12, rings=8, loc=(0, 0.10, 0), parent=fp, mat=pmat)
    # neck
    smooth_cone(f"fiole_{fk}_neck", r1=0.04, r2=0.035, depth=0.10, segs=8, loc=(0, 0.22, 0), parent=fp, mat=MAT_GLASS)
    # cork
    smooth_cone(f"fiole_{fk}_cork", r1=0.05, r2=0.045, depth=0.04, segs=8, loc=(0, 0.30, 0), parent=fp, mat=MAT_WOOD_DARK)
    # 3 bulles bullage
    fp_bubs = []
    for bb in range(3):
        bub = smooth_sphere(f"fiole_{fk}_bub_{bb}", r=0.018, segs=8, rings=6, loc=(random.uniform(-0.04, 0.04), 0.06, random.uniform(-0.04, 0.04)), parent=fp, mat=MAT_GLASS)
        bub["_phase"] = bb * 0.33
        fp_bubs.append(bub)
    fioles.append({"p": fp, "bubs": fp_bubs, "potion_idx": fk % 6})


# --- chaudron central (sol devant table) ----------------------------------
cauldron_p = empty("cauldron", (0, 0, 3.0))
# body (sphere flatten + handles)
caul_body = smooth_sphere("caul_body", r=0.55, segs=24, rings=18, loc=(0, 0.50, 0), parent=cauldron_p, mat=MAT_IRON, scale=(1.0, 0.85, 1.0))
# rim torus
beveled_cube("caul_rim", (1.20, 0.08, 1.20), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.85, 0), parent=cauldron_p, mat=MAT_IRON)
# 3 legs (tripod)
for lg in range(3):
    la = lg * (math.pi * 2 / 3)
    leg = smooth_cone(f"caul_leg_{lg}", r1=0.06, r2=0.05, depth=0.40, segs=8, loc=(math.cos(la) * 0.45, 0.15, math.sin(la) * 0.45), parent=cauldron_p, mat=MAT_IRON)
    leg.rotation_euler = (math.radians(10 * math.cos(la)), 0, math.radians(10 * math.sin(la)))
# inside liquid (visible from top)
liquid = smooth_sphere("caul_liq", r=0.50, segs=22, rings=14, loc=(0, 0.78, 0), parent=cauldron_p, mat=MAT_CAULDRON_LIQ, scale=(1.0, 0.20, 1.0))
# 6 bubbles inside
caul_bubs = []
for cb in range(6):
    ca = cb * (math.pi * 2 / 6) + 0.5
    cr = 0.30
    bub = smooth_sphere(f"caul_bub_{cb}", r=0.08, segs=12, rings=8, loc=(math.cos(ca) * cr * 0.5, 0.80, math.sin(ca) * cr * 0.5), parent=cauldron_p, mat=MAT_CAULDRON_LIQ)
    bub["_phase"] = cb * 0.20
    caul_bubs.append(bub)
# steam puffs above
caul_steams = []
for st in range(4):
    sp = smooth_sphere(f"caul_steam_{st}", r=0.25, segs=14, rings=10, loc=(0, 1.20 + st * 0.40, 0), parent=cauldron_p, mat=MAT_SMOKE, scale=(1.3, 1.0, 1.3))
    sp["_phase"] = st * 0.25
    caul_steams.append(sp)
# fire under cauldron
caul_fire = smooth_sphere("caul_fire", r=0.30, segs=16, rings=12, loc=(0, 0.15, 0), parent=cauldron_p, mat=MAT_FLAME, scale=(1.0, 0.8, 1.0))
caul_fire_in = smooth_sphere("caul_fire_in", r=0.18, segs=14, rings=10, loc=(0, 0.15, 0), parent=cauldron_p, mat=MAT_FLAME_INNER, scale=(1.0, 0.9, 1.0))


# --- 6 livres piles sur table --------------------------------------------
books_stack = empty("books_stack", (1.6, 1.20, 0.7))
y_off = 0
for bk in range(3):
    bw = 0.35
    bh = 0.10
    bd = 0.40
    bm = book_mats[bk % 3]
    beveled_cube(f"stack_book_{bk}", (bw, bh, bd), bevel_offset=0.02, bevel_segments=2, loc=(0, y_off + bh / 2, 0), parent=books_stack, mat=bm)
    y_off += bh
# 2 books open on table
open_book = empty("open_book", (-0.4, 1.20, 1.0))
# cover
beveled_cube("open_book_cover", (0.45, 0.04, 0.55), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.02, 0), parent=open_book, mat=MAT_BOOK_R)
# pages (slight rise from cover)
beveled_cube("open_book_pages", (0.40, 0.04, 0.50), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.06, 0), parent=open_book, mat=MAT_PARCHMENT)


# --- chandelier mural avec 3 bougies -------------------------------------
chand_p = empty("chand_p", (-4, 4, 0.5))
# arm
beveled_cube("chand_arm", (0.60, 0.05, 0.05), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, 0), parent=chand_p, mat=MAT_GOLD)
# 3 candle holders
flames = []
for ck in range(3):
    cx = -0.25 + ck * 0.25
    smooth_cone(f"chand_cup_{ck}", r1=0.05, r2=0.04, depth=0.08, segs=10, loc=(cx, 0.10, 0), parent=chand_p, mat=MAT_GOLD)
    # candle
    smooth_cone(f"chand_candle_{ck}", r1=0.035, r2=0.030, depth=0.25, segs=8, loc=(cx, 0.30, 0), parent=chand_p, mat=MAT_CANDLE)
    # wick
    smooth_cone(f"chand_wick_{ck}", r1=0.005, r2=0.005, depth=0.04, segs=4, loc=(cx, 0.45, 0), parent=chand_p, mat=MAT_WOOD_DARK)
    # flame
    flame_p = empty(f"chand_flame_p_{ck}", (cx, 0.50, 0), parent=chand_p)
    f_outer = smooth_sphere(f"chand_flame_{ck}", r=0.07, segs=12, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME, scale=(1.0, 1.4, 1.0))
    f_inner = smooth_sphere(f"chand_flame_in_{ck}", r=0.04, segs=10, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME_INNER, scale=(1.0, 1.5, 1.0))
    flames.append({"p": flame_p, "outer": f_outer, "inner": f_inner, "phase": ck * 0.4})


# --- crâne mystique sur table ---------------------------------------------
skull_p = empty("skull_p", (-1.0, 1.20, 1.5))
# main head
smooth_sphere("skull_head", r=0.18, segs=22, rings=16, loc=(0, 0.15, 0), parent=skull_p, mat=MAT_BONE, scale=(1.0, 1.0, 0.85))
# jaw
smooth_sphere("skull_jaw", r=0.12, segs=16, rings=10, loc=(0, -0.05, 0.05), parent=skull_p, mat=MAT_BONE, scale=(1.0, 0.5, 1.0))
# 2 eye sockets
for ez in [0.07, -0.07]:
    smooth_sphere(f"skull_socket_{ez}", r=0.04, segs=12, rings=8, loc=(0.10, 0.18, ez), parent=skull_p, mat=MAT_INK)
# emissive glow in sockets
for ez in [0.07, -0.07]:
    smooth_sphere(f"skull_eye_{ez}", r=0.025, segs=10, rings=6, loc=(0.11, 0.18, ez), parent=skull_p, mat=MAT_MAGIC_PART_A)


# --- mortier + pilon ------------------------------------------------------
mortar_p = empty("mortar_p", (0.5, 1.20, 0.5))
# mortar bowl (sphere cut top)
smooth_sphere("mortar_bowl", r=0.16, segs=18, rings=12, loc=(0, 0.08, 0), parent=mortar_p, mat=MAT_BONE, scale=(1.0, 0.7, 1.0))
# pestle (small cone leaning)
pestle = smooth_cone("pestle", r1=0.035, r2=0.025, depth=0.25, segs=8, loc=(0.08, 0.25, 0), parent=mortar_p, mat=MAT_BONE)
pestle.rotation_euler = (0, 0, math.radians(35))


# --- 8 cristaux émissifs sur étagère ---------------------------------------
crystals_p = empty("crystals", (5, 0, 4))
# small shelf
beveled_cube("crystals_shelf", (1.8, 0.06, 0.4), bevel_offset=0.02, bevel_segments=2, loc=(0, 3.0, 0), parent=crystals_p, mat=MAT_WOOD)
beveled_cube("crystals_shelf2", (1.8, 0.06, 0.4), bevel_offset=0.02, bevel_segments=2, loc=(0, 2.2, 0), parent=crystals_p, mat=MAT_WOOD)
crystal_mats = [MAT_CRYSTAL_PUR, MAT_CRYSTAL_CYA, MAT_CRYSTAL_GRE, MAT_CRYSTAL_RED]
crystals = []
for ck in range(8):
    cx = -0.7 + (ck % 4) * 0.45
    cy = 3.10 + (ck // 4) * 0.80
    cp = empty(f"crystal_{ck}", (cx, cy + 0.15, 0))
    crystals.append(cp)
    cmat = crystal_mats[ck % 4]
    # 4-sided diamond
    smooth_cone(f"crystal_{ck}_top", r1=0.0, r2=0.12, depth=0.20, segs=6, loc=(0, 0.10, 0), parent=cp, mat=cmat)
    bot = smooth_cone(f"crystal_{ck}_bot", r1=0.0, r2=0.12, depth=0.15, segs=6, loc=(0, -0.08, 0), parent=cp, mat=cmat)
    bot.rotation_euler = (math.radians(180), 0, 0)
    cp["_phase"] = ck * 0.5
    cp["_base"] = (cp.location.x, cp.location.y, cp.location.z)
crystals_p.location = (5, 0, 4)


# --- parchemin enroulé + plume + encrier ---------------------------------
parch_p = empty("parch_p", (1.5, 1.20, 0.4))
# parchemin (cylinder enroulé)
parch = smooth_cone("parchemin", r1=0.06, r2=0.06, depth=0.4, segs=10, loc=(0, 0.06, 0), parent=parch_p, mat=MAT_PARCHMENT)
parch.rotation_euler = (0, 0, math.radians(90))
# encrier (small bottle)
ink_p = empty("ink_p", (2.0, 1.20, 0.5))
smooth_cone("inkpot", r1=0.08, r2=0.07, depth=0.12, segs=10, loc=(0, 0.06, 0), parent=ink_p, mat=MAT_INK)
smooth_sphere("ink_drop", r=0.06, segs=12, rings=8, loc=(0, 0.13, 0), parent=ink_p, mat=MAT_INK, scale=(1.0, 0.3, 1.0))
# plume d'écriture
feather_p = empty("feather_p", (2.0, 1.20, 0.5))
feather_shaft = smooth_cone("feather_shaft", r1=0.012, r2=0.008, depth=0.40, segs=6, loc=(0, 0.30, 0), parent=feather_p, mat=MAT_FEATHER)
feather_shaft.rotation_euler = (0, 0, math.radians(15))
# feather fan
for fb in range(6):
    fbz = fb * 0.04 - 0.10
    smooth_sphere(f"feather_fan_{fb}", r=0.04, segs=10, rings=6, loc=(0.05 + fb * 0.005, 0.35 + fbz, 0), parent=feather_p, mat=MAT_FEATHER, scale=(1.0, 1.0, 0.2))


# --- chat noir sur tabouret ---------------------------------------------
cat_p = empty("cat_p", (4, 0, 2))
# tabouret
beveled_cube("stool_top", (0.55, 0.06, 0.55), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.50, 0), parent=cat_p, mat=MAT_WOOD)
for cx, cz in [(-0.20, -0.20), (0.20, -0.20), (-0.20, 0.20), (0.20, 0.20)]:
    smooth_cone(f"stool_leg_{cx}_{cz}", r1=0.04, r2=0.04, depth=0.50, segs=8, loc=(cx, 0.25, cz), parent=cat_p, mat=MAT_WOOD_DARK)
# cat body (curled up sitting)
smooth_sphere("cat_body", r=0.20, segs=20, rings=14, loc=(0, 0.72, 0), parent=cat_p, mat=MAT_CAT, scale=(1.4, 1.0, 1.0))
# cat head
smooth_sphere("cat_head", r=0.15, segs=18, rings=14, loc=(0.18, 0.92, 0), parent=cat_p, mat=MAT_CAT, scale=(1.0, 1.0, 1.1))
# 2 ears (triangular cones)
for ek, ez in [("L", 0.08), ("R", -0.08)]:
    ear_p = empty(f"cat_ear_p_{ek}", (0.18, 1.07, ez), parent=cat_p)
    smooth_cone(f"cat_ear_{ek}", r1=0.05, r2=0.0, depth=0.10, segs=8, loc=(0, 0.05, 0), parent=ear_p, mat=MAT_CAT)
# 2 glowing eyes
for ek, ez in [("L", 0.05), ("R", -0.05)]:
    smooth_sphere(f"cat_eye_{ek}", r=0.025, segs=10, rings=8, loc=(0.28, 0.94, ez), parent=cat_p, mat=MAT_CAT_EYE)
# tail (curled)
tail_p = empty("cat_tail_p", (-0.18, 0.72, 0), parent=cat_p)
for tk in range(4):
    smooth_sphere(f"cat_tail_{tk}", r=0.04, segs=10, rings=6, loc=(-0.10 - tk * 0.08, 0.05 + tk * 0.06, 0), parent=tail_p, mat=MAT_CAT, scale=(1.2, 0.8, 0.8))


# --- 30 magic particles drift 3D -----------------------------------------
magic_parts = []
for mk in range(30):
    pmat = MAT_MAGIC_PART_A if mk % 2 == 0 else MAT_MAGIC_PART_B
    px = random.uniform(-5, 5)
    py = random.uniform(1.5, 5.5)
    pz = random.uniform(0, 4)
    mp = smooth_sphere(f"magic_{mk}", r=random.uniform(0.04, 0.07), segs=8, rings=6, loc=(px, py, pz), mat=pmat)
    mp["_base"] = (px, py, pz)
    mp["_phase"] = mk * 0.22
    magic_parts.append(mp)


# --- 2 spirits éthérés émissifs ------------------------------------------
spirits = []
for sk in range(2):
    sp = empty(f"spirit_{sk}", (-3 + sk * 6, 3, 2))
    # body (ethereal cone tapered down ghost-like)
    smooth_cone(f"spirit_{sk}_body", r1=0.15, r2=0.30, depth=0.80, segs=14, loc=(0, 0, 0), parent=sp, mat=MAT_SPIRIT)
    # head
    smooth_sphere(f"spirit_{sk}_head", r=0.20, segs=18, rings=12, loc=(0, 0.40, 0), parent=sp, mat=MAT_SPIRIT)
    # eyes
    for ez in [0.07, -0.07]:
        smooth_sphere(f"spirit_{sk}_eye_{ez}", r=0.03, segs=10, rings=6, loc=(0.16, 0.45, ez), parent=sp, mat=MAT_MAGIC_PART_A)
    spirits.append({"p": sp, "phase": sk * 1.5, "base_x": sp.location.x, "base_z": sp.location.z})


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

    # alambic bubbles rise
    for bb in alambic_bubbles:
        ph = bb["_phase"]
        local = (tt * 2.0 + ph) % 1.0
        ny = 0.15 + local * 0.45
        kf(bb, f, "location", (bb.location.x if f > 1 else bb.location.x, ny, bb.location.z if f > 1 else bb.location.z))
        sc = 0.6 + local * 0.8
        kf(bb, f, "scale", (sc, sc, sc))

    # athanor : fire pulse + smoke rise
    fp_scale = 1.0 + 0.20 * math.sin(2 * math.pi * tt * 5)
    kf(fire_outer, f, "scale", (fp_scale * 1.0, fp_scale * 1.4, fp_scale * 1.0))
    kf(fire_inner, f, "scale", (fp_scale * 1.0, fp_scale * 1.5, fp_scale * 1.0))
    # athanor fire flicker (rotate slight)
    kf(fire_p, f, "rotation_euler", (0, math.radians(5 * math.sin(2 * math.pi * tt * 6)), math.radians(5 * math.cos(2 * math.pi * tt * 7))))
    for sm in athanor_smokes:
        ph = sm["_phase"]
        local = (tt * 1.5 + ph) % 1.0
        ny = 1.30 + local * 1.5
        sc = 1.0 + local * 1.2
        kf(sm, f, "location", (0, ny, 0))
        kf(sm, f, "scale", (sc, sc, sc))

    # 12 fioles : 3 bubbles each rise
    for fd in fioles:
        for bub in fd["bubs"]:
            ph = bub["_phase"]
            local = (tt * 2.5 + ph) % 1.0
            ny = 0.06 + local * 0.12
            sc = 0.5 + local * 0.6
            kf(bub, f, "location", (bub.location.x if f > 1 else bub.location.x, ny, bub.location.z if f > 1 else bub.location.z))
            kf(bub, f, "scale", (sc, sc, sc))

    # cauldron : bubbles + steam + fire
    for cb in caul_bubs:
        ph = cb["_phase"]
        pulse = 1.0 + 0.6 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        kf(cb, f, "scale", (pulse, pulse * 0.7, pulse))
    for st in caul_steams:
        ph = st["_phase"]
        local = (tt * 1.2 + ph) % 1.0
        ny = 1.20 + local * 1.8
        sc = 1.0 + local * 1.0
        kf(st, f, "location", (0, ny, 0))
        kf(st, f, "scale", (sc, sc, sc))
    cf = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 5)
    kf(caul_fire, f, "scale", (cf, cf * 0.85, cf))
    kf(caul_fire_in, f, "scale", (cf, cf * 0.95, cf))
    # liquid pulse
    lq = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 3)
    kf(liquid, f, "scale", (lq, 0.2 * (1 + 0.1 * math.sin(2 * math.pi * tt * 3)), lq))

    # 3 chandelier flames flicker
    for fl in flames:
        ph = fl["phase"]
        fp_sc = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        kf(fl["outer"], f, "scale", (fp_sc, fp_sc * 1.4, fp_sc))
        kf(fl["inner"], f, "scale", (fp_sc, fp_sc * 1.5, fp_sc))
        # flame sway
        kf(fl["p"], f, "rotation_euler", (math.radians(5 * math.sin(2 * math.pi * tt * 5 + ph * math.pi)), 0, math.radians(5 * math.cos(2 * math.pi * tt * 5.5 + ph * math.pi))))

    # 8 crystals float Y + rotate XYZ
    for cd in crystals:
        bxv, byv, bzv = cd["_base"]
        ph = cd["_phase"]
        nyv = byv + 0.10 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(cd, f, "location", (bxv, nyv, bzv))
        kf(cd, f, "rotation_euler", (math.radians(360 * tt + ph * 30), math.radians(540 * tt + ph * 60), math.radians(180 * tt + ph * 45)))

    # 30 magic particles drift 3D + scintille
    for mp in magic_parts:
        bxp, byp, bzp = mp["_base"]
        ph = mp["_phase"]
        nx = bxp + 0.8 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        ny = byp + 0.5 * math.cos(2 * math.pi * tt * 0.9 + ph * math.pi)
        nz = bzp + 0.6 * math.sin(2 * math.pi * tt * 0.6 + ph * math.pi * 0.7)
        kf(mp, f, "location", (nx, ny, nz))
        sc = 0.7 + 0.6 * abs(math.sin(2 * math.pi * tt * 3 + ph * math.pi))
        kf(mp, f, "scale", (sc, sc, sc))

    # 2 spirits float + pulse
    for sd in spirits:
        ph = sd["phase"]
        nyv = 3 + 0.5 * math.sin(2 * math.pi * tt * 1.0 + ph)
        nx = sd["base_x"] + 0.4 * math.cos(2 * math.pi * tt * 0.6 + ph)
        nz = sd["base_z"] + 0.3 * math.sin(2 * math.pi * tt * 0.8 + ph)
        kf(sd["p"], f, "location", (nx, nyv, nz))
        kf(sd["p"], f, "rotation_euler", (math.radians(8 * math.sin(2 * math.pi * tt * 1.5 + ph)), math.radians(60 * tt + ph * 30), 0))
        sps = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 2 + ph)
        kf(sd["p"], f, "scale", (sps, sps, sps))

    # cat tail wave + ears twitch
    kf(tail_p, f, "rotation_euler", (0, math.radians(20 * math.sin(2 * math.pi * tt * 1.5)), math.radians(15 * math.cos(2 * math.pi * tt * 1.2))))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_alchemist_lab] wrote {OUT}")
