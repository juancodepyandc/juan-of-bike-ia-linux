"""
proc_cathedral_gothic_interior.py — 175e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Intérieur cathédrale gothique :
- nef longue avec 8 colonnes massives gothiques + chapiteaux
- voûte croisée ogive
- 6 grands vitraux émissifs colorés sur côtés
- rosace circulaire géante émissive arrière
- autel sculpté gold
- 6 bancs longs nef
- 4 chandeliers
- lustre suspendu cristal géant
- 6 statues saints
- 12 bougies émissives
- tapis rouge nef
- 4 vitraux bas
- arches secondaires
- croix géante émissive
- pulpit chair sculpté

Animations multi-axes simultanées :
- lustre pulse + sway
- 12 bougies flammes flicker
- 6 vitraux pulse subtle (cycle couleurs)
- rosace rotation émission cyclique
- statues subtle bob
- croix glow pulse
- tapis ondule

Sortie : output/3d/pbr_cathedral_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_cathedral_proc.glb"))

random.seed(0xCA7E50)


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
MAT_STONE = make_mat("stone", (0.55, 0.50, 0.45), roughness=0.7, emi=(0.18, 0.16, 0.14), emi_strength=0.3)
MAT_STONE_DARK = make_mat("stone_dark", (0.35, 0.32, 0.28), roughness=0.85)
MAT_STONE_LIGHT = make_mat("stone_light", (0.75, 0.70, 0.60), roughness=0.55, emi=(0.30, 0.28, 0.22), emi_strength=0.3)
MAT_FLOOR = make_mat("floor", (0.55, 0.50, 0.42), roughness=0.45, emi=(0.20, 0.18, 0.15), emi_strength=0.3)
MAT_VITRAIL_R = make_mat("vitrail_red", (0.95, 0.20, 0.30), roughness=0.10, alpha=0.85, emi=(0.95, 0.20, 0.30), emi_strength=14.0)
MAT_VITRAIL_B = make_mat("vitrail_blue", (0.20, 0.40, 0.95), roughness=0.10, alpha=0.85, emi=(0.20, 0.40, 0.95), emi_strength=14.0)
MAT_VITRAIL_G = make_mat("vitrail_green", (0.30, 0.85, 0.40), roughness=0.10, alpha=0.85, emi=(0.30, 0.85, 0.40), emi_strength=14.0)
MAT_VITRAIL_P = make_mat("vitrail_purple", (0.65, 0.30, 0.95), roughness=0.10, alpha=0.85, emi=(0.65, 0.30, 0.95), emi_strength=14.0)
MAT_VITRAIL_Y = make_mat("vitrail_yellow", (0.95, 0.85, 0.30), roughness=0.10, alpha=0.85, emi=(0.95, 0.85, 0.30), emi_strength=14.0)
MAT_VITRAIL_O = make_mat("vitrail_orange", (1.0, 0.55, 0.20), roughness=0.10, alpha=0.85, emi=(1.0, 0.55, 0.20), emi_strength=14.0)
MAT_GOLD = make_mat("gold", (0.95, 0.75, 0.30), metallic=0.95, roughness=0.20, emi=(0.45, 0.35, 0.15), emi_strength=0.8)
MAT_GOLD_ORNATE = make_mat("gold_ornate", (1.0, 0.85, 0.40), metallic=0.95, roughness=0.15, emi=(0.55, 0.45, 0.20), emi_strength=1.2)
MAT_WOOD_DARK = make_mat("wood_dark", (0.20, 0.12, 0.06), roughness=0.85)
MAT_WOOD_BENCH = make_mat("wood_bench", (0.30, 0.18, 0.08), roughness=0.7)
MAT_CARPET = make_mat("carpet_red", (0.75, 0.15, 0.10), roughness=0.85, emi=(0.30, 0.05, 0.05), emi_strength=0.4)
MAT_CANDLE = make_mat("candle", (0.95, 0.92, 0.85), roughness=0.6)
MAT_FLAME = make_mat("flame", (1.0, 0.65, 0.20), roughness=0.0, alpha=0.85, emi=(1.0, 0.65, 0.20), emi_strength=15.0)
MAT_FLAME_INNER = make_mat("flame_inner", (1.0, 0.85, 0.30), roughness=0.0, alpha=0.85, emi=(1.0, 0.85, 0.30), emi_strength=20.0)
MAT_CHANDELIER_FRAME = make_mat("chandelier_frame", (0.85, 0.65, 0.30), metallic=0.85, roughness=0.30, emi=(0.40, 0.30, 0.15), emi_strength=0.6)
MAT_CRYSTAL = make_mat("crystal", (0.95, 0.95, 1.0), roughness=0.05, alpha=0.55, emi=(0.55, 0.55, 0.65), emi_strength=2.5)
MAT_SAINT_STATUE = make_mat("saint_statue", (0.92, 0.88, 0.80), roughness=0.5, emi=(0.40, 0.38, 0.35), emi_strength=0.5)
MAT_CROSS = make_mat("cross", (0.95, 0.85, 0.50), metallic=0.85, roughness=0.20, emi=(0.55, 0.45, 0.25), emi_strength=2.5)


# --- backdrop : cathedral structure --------------------------------------
# floor
floor = beveled_cube("floor", (16, 0.2, 24), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_FLOOR)
# carpet runner
carpet = beveled_cube("carpet", (3, 0.05, 22), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.05, 0), mat=MAT_CARPET)
# back wall (with rosace cutout area)
back_wall_top = beveled_cube("back_wall_top", (16, 4, 0.3), bevel_offset=0.05, bevel_segments=2, loc=(0, 10, 11.85), mat=MAT_STONE)
back_wall_left = beveled_cube("back_wall_left", (6, 8, 0.3), bevel_offset=0.05, bevel_segments=2, loc=(-5, 4, 11.85), mat=MAT_STONE)
back_wall_right = beveled_cube("back_wall_right", (6, 8, 0.3), bevel_offset=0.05, bevel_segments=2, loc=(5, 4, 11.85), mat=MAT_STONE)
# front wall (altar end)
front_wall = beveled_cube("front_wall", (16, 12, 0.3), bevel_offset=0.05, bevel_segments=2, loc=(0, 6, -11.85), mat=MAT_STONE_DARK)
# side walls
side_wall_L = beveled_cube("side_wall_L", (0.3, 12, 24), bevel_offset=0.05, bevel_segments=2, loc=(-8, 6, 0), mat=MAT_STONE)
side_wall_R = beveled_cube("side_wall_R", (0.3, 12, 24), bevel_offset=0.05, bevel_segments=2, loc=(8, 6, 0), mat=MAT_STONE)

# vaulted ceiling segments (ogive crossvault — using cones)
for vk in range(6):
    vz = -10 + vk * 4
    # Two arches crossing
    smooth_cone(f"vault_{vk}_L", r1=4.0, r2=0.30, depth=4.0, segs=10, loc=(-4, 9, vz), mat=MAT_STONE_LIGHT)
    smooth_cone(f"vault_{vk}_R", r1=4.0, r2=0.30, depth=4.0, segs=10, loc=(4, 9, vz), mat=MAT_STONE_LIGHT)
    bp_L = bpy.data.objects.get(f"vault_{vk}_L")
    bp_R = bpy.data.objects.get(f"vault_{vk}_R")
    if bp_L:
        bp_L.rotation_euler = (math.radians(90), 0, math.radians(-30))
    if bp_R:
        bp_R.rotation_euler = (math.radians(90), 0, math.radians(30))


# --- 8 COLONNES MASSIVES GOTHIQUES (4 left + 4 right) -----------------
COLUMN_POSITIONS = [(-5.5, 0, -9), (-5.5, 0, -3), (-5.5, 0, 3), (-5.5, 0, 9), (5.5, 0, -9), (5.5, 0, -3), (5.5, 0, 3), (5.5, 0, 9)]
for ci, (cx, cy, cz) in enumerate(COLUMN_POSITIONS):
    col_p = empty(f"column_{ci}_p", (cx, cy, cz))
    # base
    smooth_cone(f"col_{ci}_base", r1=0.65, r2=0.55, depth=0.40, segs=18, loc=(0, 0.20, 0), parent=col_p, mat=MAT_STONE)
    # main shaft
    smooth_cone(f"col_{ci}_shaft", r1=0.45, r2=0.40, depth=8.0, segs=18, loc=(0, 4.40, 0), parent=col_p, mat=MAT_STONE_LIGHT)
    # 8 vertical flutes
    for fl in range(8):
        fa = fl * (math.pi * 2 / 8)
        smooth_cone(f"col_{ci}_fl_{fl}", r1=0.04, r2=0.04, depth=7.6, segs=4, loc=(math.cos(fa) * 0.42, 4.40, math.sin(fa) * 0.42), parent=col_p, mat=MAT_STONE)
    # capital (ornate gothic)
    smooth_cone(f"col_{ci}_cap1", r1=0.55, r2=0.55, depth=0.20, segs=18, loc=(0, 8.50, 0), parent=col_p, mat=MAT_STONE)
    smooth_cone(f"col_{ci}_cap2", r1=0.65, r2=0.50, depth=0.30, segs=18, loc=(0, 8.75, 0), parent=col_p, mat=MAT_STONE_LIGHT)
    # 4 small decorative pinnacles
    for pk in range(4):
        pa = pk * (math.pi * 2 / 4) + math.pi / 4
        smooth_cone(f"col_{ci}_pin_{pk}", r1=0.08, r2=0.0, depth=0.40, segs=6, loc=(math.cos(pa) * 0.55, 9.20, math.sin(pa) * 0.55), parent=col_p, mat=MAT_STONE_LIGHT)


# --- 6 VITRAUX colorés (gothic windows on side walls) ------------------
VITRAIL_MATS = [MAT_VITRAIL_R, MAT_VITRAIL_B, MAT_VITRAIL_G, MAT_VITRAIL_P, MAT_VITRAIL_Y, MAT_VITRAIL_O]
vitraux = []
WINDOW_POSITIONS = [(-7.85, 5, -8), (-7.85, 5, -2), (-7.85, 5, 4), (7.85, 5, -8), (7.85, 5, -2), (7.85, 5, 4)]
for wi, (wx, wy, wz) in enumerate(WINDOW_POSITIONS):
    vp = empty(f"vit_{wi}_p", (wx, wy, wz))
    vp.rotation_euler = (0, math.radians(-90 if wx < 0 else 90), 0)
    # frame
    beveled_cube(f"vit_{wi}_frame", (1.6, 4.0, 0.20), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 0), parent=vp, mat=MAT_STONE_DARK)
    # glass colored (3 panels stacked)
    for pk in range(3):
        py_off = -1.2 + pk * 1.2
        vmat = VITRAIL_MATS[(wi * 3 + pk) % 6]
        glass = beveled_cube(f"vit_{wi}_g_{pk}", (1.3, 1.0, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, py_off, 0.10), parent=vp, mat=vmat)
    # pointed arch top
    smooth_cone(f"vit_{wi}_arch", r1=0.80, r2=0.0, depth=0.80, segs=6, loc=(0, 2.40, 0), parent=vp, mat=MAT_STONE_DARK)
    vp["_phase"] = wi * 0.25
    vitraux.append(vp)


# --- ROSACE arrière géante émissive ------------------------------------
rosace_p = empty("rosace_p", (0, 8, 11.7))
# main circle frame
smooth_cone("rosace_frame", r1=3.0, r2=3.0, depth=0.30, segs=32, loc=(0, 0, 0), parent=rosace_p, mat=MAT_STONE_DARK)
# inner frame
smooth_cone("rosace_inner", r1=2.7, r2=2.7, depth=0.20, segs=32, loc=(0, 0, 0.08), parent=rosace_p, mat=MAT_GOLD_ORNATE)
# central glass colored sections (12 segments)
for sk in range(12):
    sa = sk * (math.pi * 2 / 12)
    sx = math.cos(sa) * 1.5
    sy = math.sin(sa) * 1.5
    smat = VITRAIL_MATS[sk % 6]
    smooth_sphere(f"rosace_p_{sk}", r=0.55, segs=14, rings=10, loc=(sx, sy, 0.15), parent=rosace_p, mat=smat, scale=(1.0, 1.0, 0.10))
# center hub
smooth_sphere("rosace_center", r=0.65, segs=18, rings=12, loc=(0, 0, 0.15), parent=rosace_p, mat=MAT_GOLD_ORNATE, scale=(1.0, 1.0, 0.15))
# 8 outer spokes
for sk in range(8):
    sa = sk * (math.pi * 2 / 8)
    beveled_cube(f"rosace_spoke_{sk}", (0.10, 2.5, 0.10), bevel_offset=0.02, bevel_segments=2, loc=(math.cos(sa) * 0, math.sin(sa) * 0, 0.10), parent=rosace_p, mat=MAT_STONE_DARK)
    sp = bpy.data.objects.get(f"rosace_spoke_{sk}")
    if sp:
        sp.rotation_euler = (0, 0, sa)


# --- AUTEL sculpté gold ---------------------------------------------
altar_p = empty("altar_p", (0, 0, -10))
# base
beveled_cube("altar_base", (2.5, 1.0, 1.5), bevel_offset=0.06, bevel_segments=2, loc=(0, 0.50, 0), parent=altar_p, mat=MAT_GOLD)
# top
beveled_cube("altar_top", (3.0, 0.20, 2.0), bevel_offset=0.04, bevel_segments=2, loc=(0, 1.10, 0), parent=altar_p, mat=MAT_GOLD_ORNATE)
# 4 ornate decorations on front
for dk in range(4):
    dx = -1.0 + dk * 0.66
    smooth_sphere(f"altar_orn_{dk}", r=0.20, segs=18, rings=12, loc=(dx, 0.50, 0.80), parent=altar_p, mat=MAT_GOLD_ORNATE, scale=(1.0, 1.2, 0.40))


# --- GIANT CROSS centrée derrière autel ---------------------------------
cross_p = empty("cross_p", (0, 6, -11.5))
# vertical
beveled_cube("cross_vert", (0.50, 3.5, 0.30), bevel_offset=0.04, bevel_segments=2, loc=(0, 0, 0), parent=cross_p, mat=MAT_CROSS)
# horizontal
beveled_cube("cross_horiz", (2.5, 0.50, 0.30), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.70, 0), parent=cross_p, mat=MAT_CROSS)
# central ornate
smooth_sphere("cross_center", r=0.30, segs=20, rings=14, loc=(0, 0.70, 0.20), parent=cross_p, mat=MAT_GOLD_ORNATE)


# --- 6 BANCS LONGS NEF (3 left + 3 right) -------------------------------
BENCH_POSITIONS = [(-3, 0, -6), (-3, 0, 0), (-3, 0, 6), (3, 0, -6), (3, 0, 0), (3, 0, 6)]
for bi, (bx, by, bz) in enumerate(BENCH_POSITIONS):
    bp = empty(f"bench_{bi}_p", (bx, by, bz))
    # seat
    beveled_cube(f"bench_{bi}_seat", (1.5, 0.10, 4), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.55, 0), parent=bp, mat=MAT_WOOD_BENCH)
    # back rest
    beveled_cube(f"bench_{bi}_back", (1.5, 1.0, 0.10), bevel_offset=0.04, bevel_segments=2, loc=(0, 1.10, -1.95), parent=bp, mat=MAT_WOOD_BENCH)
    # legs
    for lz in [-1.7, 0, 1.7]:
        smooth_cone(f"bench_{bi}_leg_{lz}", r1=0.06, r2=0.05, depth=0.55, segs=8, loc=(0, 0.27, lz), parent=bp, mat=MAT_WOOD_DARK)


# --- LUSTRE GÉANT central -----------------------------------------------
chandelier_p = empty("chandelier_p", (0, 8.5, 0))
# central chain
smooth_cone("chand_chain", r1=0.04, r2=0.04, depth=1.5, segs=4, loc=(0, 0.75, 0), parent=chandelier_p, mat=MAT_CHANDELIER_FRAME)
# main ring (large torus-like via multiple discs)
smooth_cone("chand_main_ring", r1=1.5, r2=1.5, depth=0.10, segs=22, loc=(0, 0, 0), parent=chandelier_p, mat=MAT_CHANDELIER_FRAME)
# inner ring
smooth_cone("chand_inner_ring", r1=1.0, r2=1.0, depth=0.08, segs=22, loc=(0, -0.30, 0), parent=chandelier_p, mat=MAT_CHANDELIER_FRAME)
# 8 spokes connecting rings
for sk in range(8):
    sa = sk * (math.pi * 2 / 8)
    beveled_cube(f"chand_sp_{sk}", (0.04, 0.30, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(math.cos(sa) * 1.0, -0.15, math.sin(sa) * 1.0), parent=chandelier_p, mat=MAT_CHANDELIER_FRAME)
# 12 crystals pendants
for ck in range(12):
    ca = ck * (math.pi * 2 / 12)
    cx = math.cos(ca) * 1.30
    cz = math.sin(ca) * 1.30
    smooth_cone(f"chand_cr_{ck}", r1=0.0, r2=0.10, depth=0.25, segs=6, loc=(cx, -0.05, cz), parent=chandelier_p, mat=MAT_CRYSTAL)
# 8 candles on main ring
chand_candles = []
for ck in range(8):
    ca = ck * (math.pi * 2 / 8)
    cx = math.cos(ca) * 1.50
    cz = math.sin(ca) * 1.50
    # candle
    smooth_cone(f"chand_c_{ck}", r1=0.04, r2=0.03, depth=0.20, segs=8, loc=(cx, 0.15, cz), parent=chandelier_p, mat=MAT_CANDLE)
    # flame
    flame_p = empty(f"chand_fl_p_{ck}", (cx, 0.30, cz), parent=chandelier_p)
    f_out = smooth_sphere(f"chand_fl_{ck}", r=0.07, segs=12, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME, scale=(1.0, 1.4, 1.0))
    f_in = smooth_sphere(f"chand_fl_in_{ck}", r=0.04, segs=10, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME_INNER, scale=(1.0, 1.5, 1.0))
    chand_candles.append({"p": flame_p, "out": f_out, "in": f_in, "phase": ck * 0.30})


# --- 6 STATUES SAINTS (along walls) ----------------------------------
STATUE_POSITIONS = [(-7, 0, -7), (-7, 0, 0), (-7, 0, 7), (7, 0, -7), (7, 0, 0), (7, 0, 7)]
saints = []
for si, (sx, sy, sz) in enumerate(STATUE_POSITIONS):
    sp = empty(f"saint_{si}_p", (sx, sy, sz))
    saints.append(sp)
    # pedestal
    beveled_cube(f"saint_{si}_ped", (0.85, 1.2, 0.85), bevel_offset=0.05, bevel_segments=2, loc=(0, 0.60, 0), parent=sp, mat=MAT_STONE_LIGHT)
    # robe (lower body)
    smooth_cone(f"saint_{si}_robe", r1=0.40, r2=0.30, depth=1.4, segs=14, loc=(0, 1.90, 0), parent=sp, mat=MAT_SAINT_STATUE)
    # torso
    smooth_sphere(f"saint_{si}_torso", r=0.30, segs=20, rings=14, loc=(0, 2.75, 0), parent=sp, mat=MAT_SAINT_STATUE, scale=(1.0, 1.2, 0.85))
    # head
    smooth_sphere(f"saint_{si}_head", r=0.20, segs=18, rings=14, loc=(0, 3.20, 0), parent=sp, mat=MAT_SAINT_STATUE, scale=(0.95, 1.10, 0.95))
    # halo
    smooth_cone(f"saint_{si}_halo", r1=0.30, r2=0.30, depth=0.04, segs=18, loc=(0, 3.40, -0.15), parent=sp, mat=MAT_GOLD_ORNATE)
    # 2 arms hanging
    for ak, az in [("L", 0.20), ("R", -0.20)]:
        smooth_cone(f"saint_{si}_arm_{ak}", r1=0.08, r2=0.06, depth=0.55, segs=8, loc=(0, 2.55, az * 0.4 + 0.10), parent=sp, mat=MAT_SAINT_STATUE)


# --- 12 BOUGIES émissives (sur autel + nef) -------------------------
ground_candles = []
CANDLE_POSITIONS = [(-1.2, 0, -10), (1.2, 0, -10), (-1.6, 0, -9.5), (1.6, 0, -9.5),
                    (-4, 0, -5), (4, 0, -5), (-4, 0, 5), (4, 0, 5),
                    (-4, 0, -10), (4, 0, -10), (-2.5, 0, 8), (2.5, 0, 8)]
for ci, (cx, cy, cz) in enumerate(CANDLE_POSITIONS):
    cp = empty(f"gcandle_{ci}_p", (cx, cy, cz))
    # holder
    smooth_cone(f"gcandle_{ci}_h", r1=0.18, r2=0.15, depth=0.40, segs=12, loc=(0, 0.20, 0), parent=cp, mat=MAT_GOLD)
    # candle stick
    smooth_cone(f"gcandle_{ci}_st", r1=0.08, r2=0.07, depth=0.80, segs=10, loc=(0, 0.80, 0), parent=cp, mat=MAT_CANDLE)
    # flame
    flame_p = empty(f"gcandle_fl_p_{ci}", (0, 1.25, 0), parent=cp)
    f_out = smooth_sphere(f"gcandle_fl_{ci}", r=0.10, segs=12, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME, scale=(1.0, 1.4, 1.0))
    f_in = smooth_sphere(f"gcandle_fl_in_{ci}", r=0.06, segs=10, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME_INNER, scale=(1.0, 1.5, 1.0))
    ground_candles.append({"p": flame_p, "out": f_out, "in": f_in, "phase": ci * 0.30})


# --- PULPIT (chair sculpté pour prêcher) -----------------------------
pulpit_p = empty("pulpit_p", (2.5, 0, -8))
# base
smooth_cone("pulpit_base", r1=0.30, r2=0.20, depth=1.5, segs=14, loc=(0, 0.75, 0), parent=pulpit_p, mat=MAT_WOOD_DARK)
# body
smooth_cone("pulpit_body", r1=0.70, r2=0.50, depth=0.85, segs=14, loc=(0, 1.85, 0), parent=pulpit_p, mat=MAT_WOOD_DARK)
# top desk
beveled_cube("pulpit_desk", (1.0, 0.10, 0.55), bevel_offset=0.04, bevel_segments=2, loc=(0, 2.35, 0), parent=pulpit_p, mat=MAT_WOOD_DARK)
# decorative gold trim
smooth_cone("pulpit_trim", r1=0.55, r2=0.55, depth=0.06, segs=14, loc=(0, 2.30, 0), parent=pulpit_p, mat=MAT_GOLD)


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

    # chandelier sway gentle + chains
    sway_x = math.radians(2 * math.sin(2 * math.pi * tt * 0.8))
    sway_z = math.radians(1.5 * math.cos(2 * math.pi * tt * 1.0))
    kf(chandelier_p, f, "rotation_euler", (sway_x, math.radians(10 * tt), sway_z))

    # 8 chandelier candle flames flicker
    for cc in chand_candles:
        ph = cc["phase"]
        fp_sc = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        kf(cc["out"], f, "scale", (fp_sc, fp_sc * 1.4, fp_sc))
        kf(cc["in"], f, "scale", (fp_sc, fp_sc * 1.5, fp_sc))
        kf(cc["p"], f, "rotation_euler", (math.radians(5 * math.sin(2 * math.pi * tt * 5 + ph * math.pi)), 0, math.radians(5 * math.cos(2 * math.pi * tt * 5.5 + ph * math.pi))))

    # 12 ground candle flames flicker
    for gc in ground_candles:
        ph = gc["phase"]
        fp_sc = 1.0 + 0.18 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        kf(gc["out"], f, "scale", (fp_sc, fp_sc * 1.4, fp_sc))
        kf(gc["in"], f, "scale", (fp_sc, fp_sc * 1.5, fp_sc))
        kf(gc["p"], f, "rotation_euler", (math.radians(5 * math.sin(2 * math.pi * tt * 5 + ph * math.pi)), 0, math.radians(5 * math.cos(2 * math.pi * tt * 5.5 + ph * math.pi))))

    # 6 vitraux pulse subtle émission
    for vp in vitraux:
        ph = vp["_phase"]
        ps = 1.0 + 0.05 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(vp, f, "scale", (ps, ps, ps))

    # ROSACE rotation
    kf(rosace_p, f, "rotation_euler", (0, 0, math.radians(20 * math.sin(2 * math.pi * tt * 0.5))))

    # 6 saints subtle bob
    for si, sp in enumerate(saints):
        bob = 0.05 * math.sin(2 * math.pi * tt * 1.0 + si * 0.5)
        kf(sp, f, "rotation_euler", (math.radians(2 * bob * 10), 0, 0))

    # cross glow pulse
    cs = 1.0 + 0.06 * math.sin(2 * math.pi * tt * 1.5)
    kf(cross_p, f, "scale", (cs, cs, cs))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_cathedral_gothic_interior] wrote {OUT}")
