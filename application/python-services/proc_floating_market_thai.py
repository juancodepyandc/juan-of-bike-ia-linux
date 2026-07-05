"""
proc_floating_market_thai.py — 172e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Marché flottant thaïlandais Damnoen Saduak :
- 12 barques colorées sur rivière
- 50 fruits/légumes empilés sur barques (mangues/bananes/ananas/durians/épices)
- 6 marchandes silhouettes avec chapeau conique
- pagaies dans barques
- 4 maisons palafittes sur pilotis arrière
- temple wat bouddhiste arrière doré
- 30 nymphéas + nénuphars
- 8 lanternes thai émissives suspendues
- ciel matin doré + brouillard rivière
- 20 poissons swim
- 1 tortue
- arbres tropicaux + palmiers
- 6 oiseaux

Animations multi-axes simultanées :
- 12 barques ondulent eau (Y bob différentielle)
- 6 marchandes pagayent (paddle stroke)
- lanternes pulse + sway
- brouillard drift
- 20 poissons swim cercles
- tortue swim slow
- soleil pulse
- nymphéas float gentle

Sortie : output/3d/pbr_market_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_market_proc.glb"))

random.seed(0x7AAA17)


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
MAT_SKY = make_mat("sky_morning", (1.0, 0.75, 0.45), roughness=1.0, emi=(0.65, 0.45, 0.30), emi_strength=1.2)
MAT_SUN = make_mat("sun", (1.0, 0.85, 0.40), roughness=0.0, emi=(1.0, 0.85, 0.40), emi_strength=12.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.85, 0.40), roughness=0.0, alpha=0.30, emi=(1.0, 0.85, 0.40), emi_strength=3.0)
MAT_WATER = make_mat("water", (0.30, 0.50, 0.55), roughness=0.20, alpha=0.85, emi=(0.18, 0.30, 0.35), emi_strength=0.8)
MAT_WATER_BRIGHT = make_mat("water_bright", (0.55, 0.75, 0.85), roughness=0.10, alpha=0.65, emi=(0.30, 0.50, 0.60), emi_strength=1.2)
MAT_FOG = make_mat("fog", (0.85, 0.80, 0.70), roughness=1.0, alpha=0.35, emi=(0.60, 0.55, 0.45), emi_strength=0.6)
MAT_BANK = make_mat("bank", (0.30, 0.25, 0.15), roughness=0.85)
MAT_GRASS = make_mat("grass", (0.20, 0.45, 0.20), roughness=0.7, emi=(0.08, 0.18, 0.08), emi_strength=0.3)
MAT_BOAT_RED = make_mat("boat_red", (0.75, 0.20, 0.20), roughness=0.6, emi=(0.30, 0.05, 0.05), emi_strength=0.4)
MAT_BOAT_BLUE = make_mat("boat_blue", (0.20, 0.40, 0.75), roughness=0.6, emi=(0.05, 0.15, 0.30), emi_strength=0.4)
MAT_BOAT_YELLOW = make_mat("boat_yellow", (0.95, 0.75, 0.20), roughness=0.6, emi=(0.40, 0.30, 0.08), emi_strength=0.4)
MAT_BOAT_GREEN = make_mat("boat_green", (0.20, 0.55, 0.30), roughness=0.6, emi=(0.08, 0.20, 0.10), emi_strength=0.4)
MAT_WOOD = make_mat("wood", (0.45, 0.25, 0.15), roughness=0.7)
MAT_WOOD_DARK = make_mat("wood_dark", (0.25, 0.15, 0.08), roughness=0.85)
MAT_MANGO = make_mat("mango", (0.95, 0.75, 0.25), roughness=0.5, emi=(0.45, 0.30, 0.10), emi_strength=0.4)
MAT_BANANA = make_mat("banana", (0.95, 0.85, 0.30), roughness=0.5, emi=(0.45, 0.40, 0.10), emi_strength=0.4)
MAT_PINEAPPLE = make_mat("pineapple", (0.85, 0.75, 0.20), roughness=0.5, emi=(0.40, 0.35, 0.08), emi_strength=0.4)
MAT_DURIAN = make_mat("durian", (0.55, 0.50, 0.20), roughness=0.7, emi=(0.20, 0.18, 0.05), emi_strength=0.3)
MAT_ORANGE = make_mat("orange", (1.0, 0.55, 0.10), roughness=0.5, emi=(0.50, 0.25, 0.05), emi_strength=0.5)
MAT_RED_PEPPER = make_mat("red_pepper", (0.95, 0.15, 0.10), roughness=0.5, emi=(0.45, 0.05, 0.05), emi_strength=0.5)
MAT_GREEN_PEPPER = make_mat("green_pepper", (0.25, 0.65, 0.20), roughness=0.5, emi=(0.10, 0.30, 0.08), emi_strength=0.4)
MAT_PURPLE = make_mat("purple_fruit", (0.55, 0.30, 0.65), roughness=0.5, emi=(0.25, 0.10, 0.30), emi_strength=0.4)
MAT_LEAF = make_mat("leaf", (0.20, 0.55, 0.18), roughness=0.6, emi=(0.08, 0.25, 0.05), emi_strength=0.3)
MAT_HAT = make_mat("hat_straw", (0.85, 0.70, 0.40), roughness=0.7)
MAT_CLOTHES = make_mat("clothes", (0.65, 0.15, 0.15), roughness=0.6, emi=(0.25, 0.05, 0.05), emi_strength=0.3)
MAT_SKIN = make_mat("skin", (0.85, 0.65, 0.50), roughness=0.6)
MAT_PADDLE = make_mat("paddle", (0.30, 0.18, 0.10), roughness=0.7)
MAT_HOUSE_WALL = make_mat("house_wall", (0.55, 0.35, 0.20), roughness=0.7, emi=(0.20, 0.12, 0.06), emi_strength=0.3)
MAT_HOUSE_ROOF = make_mat("house_roof", (0.30, 0.18, 0.10), roughness=0.7)
MAT_PILOT = make_mat("pilot", (0.20, 0.12, 0.06), roughness=0.85)
MAT_TEMPLE_GOLD = make_mat("temple_gold", (1.0, 0.85, 0.30), metallic=0.85, roughness=0.20, emi=(0.55, 0.45, 0.15), emi_strength=1.5)
MAT_TEMPLE_WHITE = make_mat("temple_white", (0.95, 0.90, 0.80), roughness=0.4, emi=(0.40, 0.38, 0.32), emi_strength=0.5)
MAT_LANTERN_RED = make_mat("lantern_red", (1.0, 0.30, 0.20), roughness=0.0, emi=(1.0, 0.30, 0.20), emi_strength=12.0)
MAT_LANTERN_GOLD = make_mat("lantern_gold", (1.0, 0.85, 0.30), roughness=0.0, emi=(1.0, 0.85, 0.30), emi_strength=12.0)
MAT_LILY_PAD = make_mat("lily_pad", (0.25, 0.55, 0.30), roughness=0.7, emi=(0.10, 0.25, 0.12), emi_strength=0.4)
MAT_LOTUS = make_mat("lotus", (0.95, 0.65, 0.85), roughness=0.4, emi=(0.45, 0.25, 0.40), emi_strength=0.5)
MAT_FISH_A = make_mat("fish_A", (0.85, 0.45, 0.15), roughness=0.4, emi=(0.40, 0.20, 0.05), emi_strength=0.5)
MAT_FISH_B = make_mat("fish_B", (0.55, 0.85, 0.95), roughness=0.4, emi=(0.20, 0.40, 0.45), emi_strength=0.5)
MAT_TURTLE_SHELL = make_mat("turtle_shell", (0.35, 0.45, 0.20), roughness=0.6)
MAT_PALM_TRUNK = make_mat("palm_trunk", (0.30, 0.20, 0.10), roughness=0.85)
MAT_PALM_LEAF = make_mat("palm_leaf", (0.20, 0.50, 0.20), roughness=0.6, emi=(0.08, 0.20, 0.08), emi_strength=0.3)
MAT_BIRD = make_mat("bird", (0.95, 0.55, 0.20), roughness=0.5, emi=(0.40, 0.20, 0.08), emi_strength=0.4)


# --- backdrop : sky + river ----------------------------------------------
sky = beveled_cube("sky_back", (45, 0.2, 25), bevel_offset=0.05, bevel_segments=2, loc=(0, 13, 11), mat=MAT_SKY)

# sun + halos
sun_p = empty("sun_p", (8, 11, 8))
sun = smooth_sphere("sun", r=1.2, segs=24, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo_1 = smooth_sphere("sun_halo_1", r=1.9, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=2.7, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# river (main water surface)
river_p = empty("river_p", (0, 0, 0))
river = beveled_cube("river", (30, 0.20, 14), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 1), parent=river_p, mat=MAT_WATER)
# bright reflection patches
for rk in range(6):
    rx = random.uniform(-12, 12)
    rz = random.uniform(-4, 6)
    smooth_sphere(f"river_refl_{rk}", r=random.uniform(0.5, 1.0), segs=14, rings=8, loc=(rx, 0.12, rz), parent=river_p, mat=MAT_WATER_BRIGHT, scale=(1.0, 0.10, 1.0))

# river banks (left and right)
for bk, bz in [(0, -6), (1, 8)]:
    bank = beveled_cube(f"bank_{bk}", (30, 0.5, 3), bevel_offset=0.05, bevel_segments=2, loc=(0, 0.15, bz), mat=MAT_BANK)
    # grass top
    smooth_sphere(f"bank_grass_{bk}", r=1.5, segs=14, rings=8, loc=(-5, 0.35, bz), mat=MAT_GRASS, scale=(6, 0.10, 1.5))
    smooth_sphere(f"bank_grass2_{bk}", r=1.5, segs=14, rings=8, loc=(5, 0.35, bz), mat=MAT_GRASS, scale=(6, 0.10, 1.5))


# --- 4 maisons palafittes arrière ----------------------------------------
houses = []
HOUSE_POSITIONS = [(-9, 0, 8), (-3, 0, 8), (3, 0, 8), (9, 0, 8)]
for hi, (hx, hy, hz) in enumerate(HOUSE_POSITIONS):
    hp = empty(f"house_{hi}_p", (hx, hy, hz))
    houses.append(hp)
    # 4 stilts (pilotis)
    for sk, (sx_off, sz_off) in enumerate([(-0.65, -0.65), (0.65, -0.65), (-0.65, 0.65), (0.65, 0.65)]):
        smooth_cone(f"house_{hi}_stilt_{sk}", r1=0.10, r2=0.08, depth=2.0, segs=8, loc=(sx_off, 1.0, sz_off), parent=hp, mat=MAT_PILOT)
    # main body
    beveled_cube(f"house_{hi}_body", (1.6, 1.3, 1.4), bevel_offset=0.05, bevel_segments=2, loc=(0, 2.65, 0), parent=hp, mat=MAT_HOUSE_WALL)
    # roof (gabled)
    smooth_cone(f"house_{hi}_roof", r1=1.0, r2=0.0, depth=0.85, segs=4, loc=(0, 3.70, 0), parent=hp, mat=MAT_HOUSE_ROOF)
    # door
    beveled_cube(f"house_{hi}_door", (0.40, 0.85, 0.05), bevel_offset=0.02, bevel_segments=2, loc=(0, 2.4, 0.72), parent=hp, mat=MAT_WOOD_DARK)
    # 2 small windows
    for wk, wx_off in [(0, -0.45), (1, 0.45)]:
        smooth_sphere(f"house_{hi}_win_{wk}", r=0.18, segs=12, rings=8, loc=(wx_off, 2.85, 0.72), parent=hp, mat=MAT_LANTERN_GOLD, scale=(1.0, 1.0, 0.10))


# --- temple wat bouddhiste arrière (centre) ------------------------------
temple_p = empty("temple_p", (-15, 0, 10))
# base
beveled_cube("temple_base", (3.5, 0.5, 3.0), bevel_offset=0.05, bevel_segments=2, loc=(0, 0.25, 0), parent=temple_p, mat=MAT_TEMPLE_WHITE)
# walls
beveled_cube("temple_walls", (3, 2.5, 2.5), bevel_offset=0.05, bevel_segments=2, loc=(0, 1.75, 0), parent=temple_p, mat=MAT_TEMPLE_WHITE)
# roof tiered (3 levels)
for tk in range(3):
    smooth_cone(f"temple_roof_{tk}", r1=2.0 - tk * 0.40, r2=0.10, depth=0.85, segs=8, loc=(0, 3.5 + tk * 0.70, 0), parent=temple_p, mat=MAT_TEMPLE_GOLD)
# 4 finials at corners
for ck, (cx, cz) in enumerate([(-1.4, -1.2), (1.4, -1.2), (-1.4, 1.2), (1.4, 1.2)]):
    smooth_cone(f"temple_finial_{ck}", r1=0.0, r2=0.10, depth=0.60, segs=6, loc=(cx, 3.5, cz), parent=temple_p, mat=MAT_TEMPLE_GOLD)
# main spire
smooth_cone("temple_spire", r1=0.0, r2=0.20, depth=1.5, segs=8, loc=(0, 6.0, 0), parent=temple_p, mat=MAT_TEMPLE_GOLD)


# --- 12 BARQUES COLORÉES sur rivière ----------------------------------
BOAT_MATS = [MAT_BOAT_RED, MAT_BOAT_BLUE, MAT_BOAT_YELLOW, MAT_BOAT_GREEN]
boats = []
for bi in range(12):
    a = bi * (math.pi * 2 / 12) + random.uniform(-0.2, 0.2)
    r = random.uniform(3, 10)
    bx = math.cos(a) * r * 1.5
    bz = math.sin(a) * r * 0.4 + 1
    # keep boats on water
    if abs(bx) > 14:
        bx = math.copysign(13, bx)
    bp = empty(f"boat_{bi}_p", (bx, 0.25, bz))
    boats.append(bp)
    bmat = BOAT_MATS[bi % 4]
    # hull (elongated oval)
    smooth_sphere(f"boat_{bi}_hull", r=0.65, segs=18, rings=12, loc=(0, 0, 0), parent=bp, mat=bmat, scale=(2.5, 0.30, 0.85))
    # inner darker
    smooth_sphere(f"boat_{bi}_inner", r=0.55, segs=16, rings=12, loc=(0, 0.08, 0), parent=bp, mat=MAT_WOOD_DARK, scale=(2.3, 0.15, 0.75))
    # rim plank
    smooth_sphere(f"boat_{bi}_rim", r=0.65, segs=16, rings=8, loc=(0, 0.13, 0), parent=bp, mat=MAT_WOOD, scale=(2.5, 0.05, 0.85))
    bp["_phase"] = bi * 0.30
    bp["_base"] = (bx, 0.25, bz)


# --- 50 fruits/légumes sur barques ------------------------------------
FRUIT_MATS = [MAT_MANGO, MAT_BANANA, MAT_PINEAPPLE, MAT_DURIAN, MAT_ORANGE, MAT_RED_PEPPER, MAT_GREEN_PEPPER, MAT_PURPLE]
for fk in range(50):
    boat_idx = fk % 12
    boat = boats[boat_idx]
    base_x = boat["_base"][0]
    base_z = boat["_base"][2]
    fr_idx = fk % len(FRUIT_MATS)
    fmat = FRUIT_MATS[fr_idx]
    # position on boat (random within hull)
    fx_off = random.uniform(-0.8, 0.8)
    fz_off = random.uniform(-0.25, 0.25)
    fy = 0.35 + random.uniform(0, 0.20)
    smooth_sphere(f"fruit_{fk}", r=random.uniform(0.08, 0.14), segs=12, rings=8, loc=(base_x + fx_off, fy, base_z + fz_off), mat=fmat, scale=(1.0, random.uniform(0.7, 1.2), random.uniform(0.8, 1.0)))


# --- 6 MARCHANDES sur barques ----------------------------------------
sellers = []
SELLER_BOATS = [0, 2, 4, 6, 8, 10]
for si, bi in enumerate(SELLER_BOATS):
    boat = boats[bi]
    base_x = boat["_base"][0]
    base_z = boat["_base"][2]
    sp = empty(f"seller_{si}_p", (base_x - 0.6, 0.40, base_z))
    sellers.append(sp)
    # body (cloth dress)
    smooth_cone(f"seller_{si}_body", r1=0.22, r2=0.30, depth=0.85, segs=14, loc=(0, 0.42, 0), parent=sp, mat=MAT_CLOTHES)
    # head
    smooth_sphere(f"seller_{si}_head", r=0.15, segs=18, rings=12, loc=(0, 1.0, 0), parent=sp, mat=MAT_SKIN)
    # conical hat (signature)
    smooth_cone(f"seller_{si}_hat", r1=0.35, r2=0.0, depth=0.30, segs=14, loc=(0, 1.25, 0), parent=sp, mat=MAT_HAT)
    # 2 arms holding paddle
    arm_L = empty(f"seller_{si}_armL_p", (0.15, 0.85, 0), parent=sp)
    smooth_cone(f"seller_{si}_armL", r1=0.05, r2=0.05, depth=0.40, segs=8, loc=(0, -0.20, 0), parent=arm_L, mat=MAT_SKIN)
    arm_R = empty(f"seller_{si}_armR_p", (-0.15, 0.85, 0), parent=sp)
    smooth_cone(f"seller_{si}_armR", r1=0.05, r2=0.05, depth=0.40, segs=8, loc=(0, -0.20, 0), parent=arm_R, mat=MAT_SKIN)
    # paddle held by arms
    paddle_p = empty(f"seller_{si}_paddle_p", (0, 0.60, 0), parent=sp)
    paddle_p.rotation_euler = (0, 0, math.radians(45))
    smooth_cone(f"seller_{si}_paddle_shaft", r1=0.03, r2=0.03, depth=1.5, segs=6, loc=(0, -0.30, 0), parent=paddle_p, mat=MAT_PADDLE)
    # paddle blade
    smooth_sphere(f"seller_{si}_paddle_blade", r=0.20, segs=12, rings=8, loc=(0, -1.10, 0), parent=paddle_p, mat=MAT_PADDLE, scale=(0.5, 0.10, 1.4))
    sp["_arm_L"] = arm_L
    sp["_arm_R"] = arm_R
    sp["_paddle"] = paddle_p
    sp["_phase"] = si * 0.40


# --- 30 nymphéas + lotus -------------------------------------------------
lilies = []
for lk in range(30):
    a = lk * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(2, 12)
    lx = math.cos(a) * r * 1.3
    lz = math.sin(a) * r * 0.4 + 1
    if abs(lx) > 14:
        continue
    lp = empty(f"lily_{lk}_p", (lx, 0.18, lz))
    lilies.append(lp)
    # pad
    smooth_sphere(f"lily_{lk}_pad", r=0.30, segs=14, rings=8, loc=(0, 0, 0), parent=lp, mat=MAT_LILY_PAD, scale=(1.0, 0.10, 1.0))
    # flower
    if lk % 3 == 0:
        for pk in range(5):
            pa = pk * (math.pi * 2 / 5)
            smooth_cone(f"lily_{lk}_pet_{pk}", r1=0.05, r2=0.0, depth=0.15, segs=6, loc=(math.cos(pa) * 0.08, 0.06, math.sin(pa) * 0.08), parent=lp, mat=MAT_LOTUS)
    lp["_phase"] = lk * 0.20


# --- 8 LANTERNES THAI émissives ---------------------------------------
lanterns = []
LANTERN_POSITIONS = [(-12, 6, 4), (-6, 6, 4), (0, 6.5, 4), (6, 6, 4), (12, 6, 4), (-9, 5.5, -3), (0, 5.5, -3), (9, 5.5, -3)]
LANTERN_MATS = [MAT_LANTERN_RED, MAT_LANTERN_GOLD]
for li, (lx, ly, lz) in enumerate(LANTERN_POSITIONS):
    lp = empty(f"lantern_{li}_p", (lx, ly, lz))
    lanterns.append(lp)
    # chain
    smooth_cone(f"lantern_{li}_chain", r1=0.015, r2=0.015, depth=2.0, segs=4, loc=(0, 1.1, 0), parent=lp, mat=MAT_WOOD_DARK)
    # body sphere
    lmat = LANTERN_MATS[li % 2]
    smooth_sphere(f"lantern_{li}_body", r=0.30, segs=18, rings=14, loc=(0, 0, 0), parent=lp, mat=lmat, scale=(1.0, 1.3, 1.0))
    # 3 decorative rings
    for rk in range(3):
        smooth_cone(f"lantern_{li}_r_{rk}", r1=0.32, r2=0.32, depth=0.03, segs=14, loc=(0, -0.20 + rk * 0.20, 0), parent=lp, mat=MAT_WOOD_DARK)
    lp["_phase"] = li * 0.30
    lp["_base"] = (lx, ly, lz)


# --- 4 palmiers ----------------------------------------------------
palms = []
PALM_POSITIONS = [(-12, 0, -6), (12, 0, -6), (-12, 0, 9), (12, 0, 9)]
for pi, (px, py, pz) in enumerate(PALM_POSITIONS):
    pp = empty(f"palm_{pi}_p", (px, py, pz))
    palms.append(pp)
    # trunk (5 segments slightly curved)
    cur_y = 0
    for sg in range(5):
        seg_y = cur_y + 0.85
        # slight bend
        smooth_cone(f"palm_{pi}_t_{sg}", r1=0.18 - sg * 0.015, r2=0.16 - sg * 0.015, depth=0.90, segs=10, loc=(math.cos(sg * 0.5) * 0.05, seg_y, math.sin(sg * 0.5) * 0.05), parent=pp, mat=MAT_PALM_TRUNK)
        cur_y += 0.90
    # 8 fronds (palm leaves)
    for lk in range(8):
        la = lk * (math.pi * 2 / 8)
        leaf_p = empty(f"palm_{pi}_lp_{lk}", (math.cos(la) * 0.2, cur_y, math.sin(la) * 0.2), parent=pp)
        leaf_p.rotation_euler = (math.radians(-15 - random.uniform(0, 15)), -la, 0)
        smooth_sphere(f"palm_{pi}_l_{lk}", r=0.50, segs=14, rings=10, loc=(0, -0.30, 1.0), parent=leaf_p, mat=MAT_PALM_LEAF, scale=(0.30, 0.05, 2.5))
    pp["_phase"] = pi * 0.5


# --- 20 poissons ------------------------------------------------------
fish_school = []
for fk in range(20):
    a = fk * (math.pi * 2 / 20)
    fr = random.uniform(2, 10)
    fy = random.uniform(-0.10, 0.10)
    fp = empty(f"fish_{fk}_p", (math.cos(a) * fr, 0.15, math.sin(a) * fr * 0.4 + 1))
    fmat = MAT_FISH_A if fk % 2 == 0 else MAT_FISH_B
    smooth_sphere(f"fish_{fk}_b", r=0.10, segs=12, rings=8, loc=(0, 0, 0), parent=fp, mat=fmat, scale=(1.6, 0.85, 0.7))
    smooth_sphere(f"fish_{fk}_t", r=0.07, segs=10, rings=6, loc=(-0.15, 0, 0), parent=fp, mat=fmat, scale=(0.5, 1.2, 0.1))
    fish_school.append({"p": fp, "a0": a, "r": fr, "y0": 0.15, "phase": fk * 0.15})


# --- 1 tortue --------------------------------------------------------
turtle_p = empty("turtle", (-3, 0.20, 3))
smooth_sphere("turtle_shell", r=0.35, segs=18, rings=14, loc=(0, 0, 0), parent=turtle_p, mat=MAT_TURTLE_SHELL, scale=(1.2, 0.5, 1.0))
smooth_sphere("turtle_head", r=0.12, segs=12, rings=8, loc=(0.35, 0.05, 0), parent=turtle_p, mat=MAT_SKIN)
for fk, (fx, fz) in enumerate([(0.15, 0.30), (0.15, -0.30), (-0.20, 0.30), (-0.20, -0.30)]):
    smooth_sphere(f"turtle_fl_{fk}", r=0.15, segs=10, rings=8, loc=(fx, -0.05, fz), parent=turtle_p, mat=MAT_SKIN, scale=(1.4, 0.1, 0.5))


# --- 6 oiseaux ------------------------------------------------------
birds = []
for bk in range(6):
    a = bk * (math.pi * 2 / 6) + 0.3
    br = random.uniform(7, 12)
    by = random.uniform(8, 11)
    bp = empty(f"bird_{bk}_p", (math.cos(a) * br, by, math.sin(a) * br * 0.7))
    smooth_sphere(f"bird_{bk}_b", r=0.10, segs=12, rings=8, loc=(0, 0, 0), parent=bp, mat=MAT_BIRD, scale=(1.4, 0.7, 0.7))
    wL = empty(f"bird_{bk}_wL", (0, 0.02, 0.05), parent=bp)
    wR = empty(f"bird_{bk}_wR", (0, 0.02, -0.05), parent=bp)
    smooth_sphere(f"bird_{bk}_wL_b", r=0.10, segs=10, rings=6, loc=(0, 0, 0.15), parent=wL, mat=MAT_BIRD, scale=(0.5, 0.05, 1.5))
    smooth_sphere(f"bird_{bk}_wR_b", r=0.10, segs=10, rings=6, loc=(0, 0, -0.15), parent=wR, mat=MAT_BIRD, scale=(0.5, 0.05, 1.5))
    birds.append({"p": bp, "wL": wL, "wR": wR, "a": a, "r": br, "by": by, "phase": bk * 0.4})


# --- 10 fog puffs ---------------------------------------------------
fog_puffs = []
for gk in range(10):
    gx = random.uniform(-13, 13)
    gz = random.uniform(-4, 7)
    gy = random.uniform(0.5, 2)
    gp = smooth_sphere(f"fog_{gk}", r=random.uniform(0.8, 1.4), segs=14, rings=8, loc=(gx, gy, gz), mat=MAT_FOG, scale=(1.0, 0.25, 1.0))
    gp["_base"] = (gx, gy, gz)
    gp["_phase"] = gk * 0.30
    fog_puffs.append(gp)


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

    # 12 boats : bob Y + sway X/Z
    for bp in boats:
        bx_, by_, bz_ = bp["_base"]
        ph = bp["_phase"]
        ny = by_ + 0.10 * math.sin(2 * math.pi * tt * 1.2 + ph * math.pi)
        nx = bx_ + 0.15 * math.sin(2 * math.pi * tt * 0.6 + ph * math.pi)
        nz = bz_ + 0.10 * math.cos(2 * math.pi * tt * 0.8 + ph * math.pi)
        kf(bp, f, "location", (nx, ny, nz))
        kf(bp, f, "rotation_euler", (math.radians(5 * math.sin(2 * math.pi * tt * 1.5 + ph)), math.radians(20 * math.sin(2 * math.pi * tt * 0.3 + ph * math.pi)), math.radians(4 * math.cos(2 * math.pi * tt * 1.0 + ph))))

    # 6 sellers paddle (paddle rotates back and forth)
    for sl in sellers:
        ph = sl["_phase"]
        paddle = sl["_paddle"]
        stroke = math.radians(30) * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)
        kf(paddle, f, "rotation_euler", (0, 0, math.radians(45) + stroke))

    # 8 lanterns pulse + sway
    for lp in lanterns:
        ph = lp["_phase"]
        bx_, by_, bz_ = lp["_base"]
        sway_x = bx_ + 0.15 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi)
        sway_z = bz_ + 0.10 * math.cos(2 * math.pi * tt * 1.0 + ph * math.pi)
        kf(lp, f, "location", (sway_x, by_, sway_z))
        ps = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 2.5 + ph * math.pi)
        kf(lp, f, "scale", (ps, ps, ps))

    # 30 lilies float gentle
    for li in lilies:
        ph = li["_phase"]
        ms = 1.0 + 0.05 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)
        kf(li, f, "scale", (ms, ms, ms))
        kf(li, f, "rotation_euler", (0, math.radians(10 * math.sin(2 * math.pi * tt * 0.5 + ph * math.pi)), 0))

    # 20 fish swim in cercles
    for fd in fish_school:
        ang = fd["a0"] + tt * 2 * math.pi * 0.5
        fx = math.cos(ang) * fd["r"]
        fz = math.sin(ang) * fd["r"] * 0.4 + 1
        kf(fd["p"], f, "location", (fx, fd["y0"], fz))
        kf(fd["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))

    # turtle swim slow
    tx_turt = -3 + 2 * math.sin(2 * math.pi * tt * 0.3)
    ty_turt = 0.20 + 0.10 * math.sin(2 * math.pi * tt * 0.5)
    kf(turtle_p, f, "location", (tx_turt, ty_turt, 3))

    # 6 birds flap + orbit
    for bd in birds:
        ang = bd["a"] + tt * 2 * math.pi * 0.4
        bx_ = math.cos(ang) * bd["r"]
        bz_ = math.sin(ang) * bd["r"] * 0.7
        by_ = bd["by"] + 0.3 * math.sin(2 * math.pi * tt * 1.5 + bd["phase"])
        kf(bd["p"], f, "location", (bx_, by_, bz_))
        kf(bd["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))
        wflap = math.radians(50) * math.sin(2 * math.pi * tt * 8 + bd["phase"])
        kf(bd["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(bd["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # 10 fog drift
    for fp in fog_puffs:
        bx_, by_, bz_ = fp["_base"]
        ph = fp["_phase"]
        nx = bx_ + 1.0 * math.sin(2 * math.pi * tt * 0.3 + ph * math.pi)
        nz = bz_ + 0.5 * math.cos(2 * math.pi * tt * 0.4 + ph * math.pi)
        kf(fp, f, "location", (nx, by_, nz))

    # 4 palms sway
    for ppm in palms:
        ph = ppm["_phase"]
        sw = math.radians(3 * math.sin(2 * math.pi * tt * 0.6 + ph * math.pi))
        kf(ppm, f, "rotation_euler", (sw, 0, math.radians(2 * math.cos(2 * math.pi * tt * 0.7 + ph * math.pi))))

    # sun pulse + halos breathe
    sp = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 2)
    kf(sun, f, "scale", (sp, sp, sp))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2]):
        br = 1.0 + 0.10 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.0)
        kf(halo, f, "scale", (br, br, br))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_floating_market_thai] wrote {OUT}")
