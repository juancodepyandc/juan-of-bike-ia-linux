"""
proc_knight_tournament.py — 183e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes + anatomie).

Tournoi médiéval avec 2 chevaliers joutant :
- 2 chevaliers armures complètes (casque + heaume + visière + cuirasse + 2 bras + 2 jambes + 2 boucliers + 2 lances longues)
- 2 chevaux caparaçonnés galopant
- lice (clôture jouting)
- tribune avec public
- roi sur trône
- 4 tentes médiévales
- bannières + drapeaux + flags
- chevaliers spectateurs fond
- ciel matin doré

Animations multi-axes simultanées :
- 2 chevaliers chargent vers center (drift X opposé)
- chevaux galop animation alterné (4 legs)
- bannières flutter
- public wave
- drapeaux wave

Sortie : output/3d/pbr_tournament_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_tournament_proc.glb"))

random.seed(0x4CC177)


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
MAT_SKY = make_mat("sky_morning", (0.95, 0.75, 0.45), roughness=1.0, emi=(0.55, 0.40, 0.25), emi_strength=1.0)
MAT_SUN = make_mat("sun", (1.0, 0.85, 0.40), roughness=0.0, emi=(1.0, 0.85, 0.40), emi_strength=12.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.85, 0.40), roughness=0.0, alpha=0.30, emi=(1.0, 0.85, 0.40), emi_strength=3.0)
MAT_GRASS = make_mat("grass", (0.25, 0.55, 0.20), roughness=0.7, emi=(0.10, 0.25, 0.08), emi_strength=0.3)
MAT_DIRT = make_mat("dirt", (0.40, 0.25, 0.15), roughness=0.85)
MAT_KNIGHT_A_PRIM = make_mat("knight_A_prim", (0.65, 0.65, 0.70), metallic=0.95, roughness=0.20, emi=(0.30, 0.30, 0.32), emi_strength=0.5)
MAT_KNIGHT_A_TRIM = make_mat("knight_A_trim", (0.85, 0.15, 0.15), roughness=0.6, emi=(0.40, 0.05, 0.05), emi_strength=0.6)
MAT_KNIGHT_A_GOLD = make_mat("knight_A_gold", (0.95, 0.75, 0.30), metallic=0.85, roughness=0.30, emi=(0.45, 0.35, 0.10), emi_strength=0.6)
MAT_KNIGHT_B_PRIM = make_mat("knight_B_prim", (0.85, 0.85, 0.90), metallic=0.95, roughness=0.20, emi=(0.45, 0.45, 0.48), emi_strength=0.7)
MAT_KNIGHT_B_TRIM = make_mat("knight_B_trim", (0.20, 0.40, 0.85), roughness=0.6, emi=(0.05, 0.15, 0.40), emi_strength=0.6)
MAT_KNIGHT_B_SILVER = make_mat("knight_B_silver", (0.85, 0.85, 0.95), metallic=0.95, roughness=0.20, emi=(0.40, 0.40, 0.45), emi_strength=0.6)
MAT_HORSE_BROWN = make_mat("horse_brown", (0.45, 0.25, 0.12), roughness=0.65)
MAT_HORSE_WHITE = make_mat("horse_white", (0.92, 0.90, 0.85), roughness=0.6, emi=(0.40, 0.38, 0.35), emi_strength=0.4)
MAT_CAPARISON_RED = make_mat("caparison_red", (0.75, 0.15, 0.12), roughness=0.6, emi=(0.30, 0.05, 0.05), emi_strength=0.4)
MAT_CAPARISON_BLUE = make_mat("caparison_blue", (0.15, 0.30, 0.75), roughness=0.6, emi=(0.05, 0.10, 0.30), emi_strength=0.4)
MAT_LANCE = make_mat("lance", (0.45, 0.30, 0.15), roughness=0.7)
MAT_LANCE_TIP = make_mat("lance_tip", (0.85, 0.85, 0.90), metallic=0.85, roughness=0.30)
MAT_WOOD = make_mat("wood", (0.40, 0.25, 0.12), roughness=0.7)
MAT_WOOD_DARK = make_mat("wood_dark", (0.20, 0.12, 0.06), roughness=0.85)
MAT_TENT_A = make_mat("tent_A", (0.85, 0.30, 0.20), roughness=0.7, emi=(0.30, 0.08, 0.05), emi_strength=0.4)
MAT_TENT_B = make_mat("tent_B", (0.20, 0.45, 0.75), roughness=0.7, emi=(0.05, 0.15, 0.30), emi_strength=0.4)
MAT_TENT_C = make_mat("tent_C", (0.85, 0.75, 0.20), roughness=0.7, emi=(0.30, 0.25, 0.05), emi_strength=0.4)
MAT_TENT_D = make_mat("tent_D", (0.35, 0.65, 0.25), roughness=0.7, emi=(0.10, 0.25, 0.08), emi_strength=0.4)
MAT_FLAG_RED = make_mat("flag_red", (0.85, 0.20, 0.15), roughness=0.7, emi=(0.30, 0.05, 0.05), emi_strength=0.4)
MAT_FLAG_BLUE = make_mat("flag_blue", (0.20, 0.40, 0.85), roughness=0.7, emi=(0.05, 0.15, 0.30), emi_strength=0.4)
MAT_FLAG_GOLD = make_mat("flag_gold", (0.95, 0.75, 0.25), metallic=0.4, roughness=0.4, emi=(0.30, 0.22, 0.05), emi_strength=0.4)
MAT_TRIBUNE = make_mat("tribune", (0.50, 0.32, 0.18), roughness=0.7)
MAT_SPECTATOR = make_mat("spectator", (0.30, 0.25, 0.30), roughness=0.7)
MAT_KING_ROBE = make_mat("king_robe", (0.65, 0.15, 0.45), roughness=0.5, emi=(0.30, 0.05, 0.18), emi_strength=0.5)
MAT_KING_CROWN = make_mat("king_crown", (1.0, 0.85, 0.30), metallic=0.95, roughness=0.15, emi=(0.55, 0.45, 0.15), emi_strength=1.0)
MAT_THRONE = make_mat("throne", (0.45, 0.30, 0.15), roughness=0.6)


# --- backdrop : sky + ground --------------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 12), mat=MAT_SKY)
sun_p = empty("sun_p", (-9, 13, 10))
sun = smooth_sphere("sun", r=1.4, segs=24, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo_1 = smooth_sphere("sun_halo_1", r=2.2, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=3.0, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# grass field
ground = beveled_cube("ground", (40, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_GRASS)
# dirt jouting lane center
lane = beveled_cube("lane", (12, 0.05, 2.5), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.03, 0), mat=MAT_DIRT)


# --- LICE (clôture jouting) --------------------------------------------
# 2 long barriers (left + right of lane)
for li, lz in [(0, 1.3), (1, -1.3)]:
    barrier_p = empty(f"barrier_p_{li}", (0, 0, lz))
    # 6 vertical posts
    for pk in range(7):
        px = -5 + pk * 1.7
        smooth_cone(f"barrier_{li}_post_{pk}", r1=0.06, r2=0.05, depth=1.0, segs=8, loc=(px, 0.5, 0), parent=barrier_p, mat=MAT_WOOD_DARK)
    # 2 horizontal rails
    for rk in [0, 1]:
        beveled_cube(f"barrier_{li}_rail_{rk}", (12, 0.08, 0.08), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.4 + rk * 0.4, 0), parent=barrier_p, mat=MAT_WOOD)


# --- KNIGHT FUNCTION ---------------------------------------------------
def build_knight(name, base_pos, prim_mat, trim_mat, gold_mat, facing_dir=1, caparison_mat=MAT_CAPARISON_RED, horse_mat=MAT_HORSE_BROWN):
    """Build a complete knight on horseback."""
    kp = empty(f"{name}_p", base_pos)

    # HORSE (full anatomy)
    horse_p = empty(f"{name}_horse_p", (0, 0, 0), parent=kp)
    # body
    smooth_sphere(f"{name}_horse_body", r=0.55, segs=20, rings=14, loc=(0, 1.2, 0), parent=horse_p, mat=horse_mat, scale=(1.6, 0.9, 0.85))
    # caparison (cloth covering)
    smooth_sphere(f"{name}_horse_capar", r=0.65, segs=18, rings=12, loc=(0, 1.05, 0), parent=horse_p, mat=caparison_mat, scale=(1.65, 0.55, 1.0))
    # neck (curved up)
    neck = smooth_cone(f"{name}_horse_neck", r1=0.20, r2=0.15, depth=0.85, segs=10, loc=(0.85, 1.45, 0), parent=horse_p, mat=horse_mat)
    neck.rotation_euler = (0, 0, math.radians(-55))
    # head
    smooth_sphere(f"{name}_horse_head", r=0.20, segs=16, rings=12, loc=(1.30, 1.85, 0), parent=horse_p, mat=horse_mat, scale=(1.4, 1.0, 0.85))
    # snout
    smooth_cone(f"{name}_horse_snout", r1=0.15, r2=0.10, depth=0.20, segs=10, loc=(1.50, 1.75, 0), parent=horse_p, mat=horse_mat)
    # 2 ears
    for ek, ez in [("L", 0.12), ("R", -0.12)]:
        smooth_cone(f"{name}_horse_ear_{ek}", r1=0.04, r2=0.0, depth=0.10, segs=6, loc=(1.20, 2.05, ez), parent=horse_p, mat=horse_mat)
    # 4 LEGS articulated (legs_root for galop animation)
    horse_legs = {}
    LEG_POSITIONS = [(-0.40, 0.85, 0.30), (-0.40, 0.85, -0.30), (0.40, 0.85, 0.30), (0.40, 0.85, -0.30)]
    for li, (lx, ly, lz) in enumerate(LEG_POSITIONS):
        leg_root = empty(f"{name}_horse_leg_root_{li}", (lx, ly, lz), parent=horse_p)
        # thigh
        smooth_cone(f"{name}_horse_thigh_{li}", r1=0.10, r2=0.08, depth=0.50, segs=8, loc=(0, -0.25, 0), parent=leg_root, mat=horse_mat)
        # knee + lower leg
        smooth_cone(f"{name}_horse_calf_{li}", r1=0.08, r2=0.06, depth=0.45, segs=8, loc=(0, -0.60, 0), parent=leg_root, mat=horse_mat)
        # hoof
        smooth_sphere(f"{name}_horse_hoof_{li}", r=0.08, segs=10, rings=8, loc=(0, -0.85, 0), parent=leg_root, mat=MAT_WOOD_DARK)
        horse_legs[li] = leg_root
    # tail
    smooth_cone(f"{name}_horse_tail", r1=0.05, r2=0.0, depth=0.40, segs=6, loc=(-0.75, 1.30, 0), parent=horse_p, mat=horse_mat)

    # KNIGHT body on horse
    knight_body_p = empty(f"{name}_knight_p", (0, 0, 0), parent=horse_p)
    # cuirasse (chest armor)
    smooth_sphere(f"{name}_cuirasse", r=0.30, segs=18, rings=14, loc=(0, 1.95, 0), parent=knight_body_p, mat=prim_mat, scale=(1.0, 1.4, 0.85))
    # trim accent
    smooth_sphere(f"{name}_trim", r=0.22, segs=14, rings=10, loc=(0, 1.95, 0.18), parent=knight_body_p, mat=trim_mat, scale=(1.0, 1.2, 0.30))
    # neck (gorget)
    smooth_cone(f"{name}_gorget", r1=0.15, r2=0.13, depth=0.18, segs=12, loc=(0, 2.40, 0), parent=knight_body_p, mat=prim_mat)
    # HELMET (casque)
    helmet_p = empty(f"{name}_helmet_p", (0, 2.60, 0), parent=knight_body_p)
    # heaume base
    smooth_sphere(f"{name}_helmet", r=0.25, segs=20, rings=14, loc=(0, 0, 0), parent=helmet_p, mat=prim_mat, scale=(1.0, 1.1, 1.0))
    # visière (visor)
    smooth_sphere(f"{name}_visor", r=0.20, segs=14, rings=10, loc=(0, -0.05, 0.20), parent=helmet_p, mat=gold_mat, scale=(1.0, 0.30, 0.40))
    # crête plume (crest plume)
    smooth_cone(f"{name}_crest", r1=0.04, r2=0.0, depth=0.45, segs=4, loc=(0, 0.25, 0), parent=helmet_p, mat=trim_mat)
    crest = bpy.data.objects.get(f"{name}_crest")
    if crest:
        crest.rotation_euler = (0, 0, math.radians(20))

    # 2 ARMS articulated
    # right arm (carrying lance)
    arm_R_p = empty(f"{name}_arm_R_p", (0.35, 2.20, 0.10), parent=knight_body_p)
    arm_R_p.rotation_euler = (math.radians(-30), 0, math.radians(-15))
    smooth_cone(f"{name}_arm_R_upper", r1=0.10, r2=0.08, depth=0.30, segs=8, loc=(0, -0.15, 0), parent=arm_R_p, mat=prim_mat)
    elbow_R = empty(f"{name}_elbow_R", (0, -0.30, 0), parent=arm_R_p)
    smooth_cone(f"{name}_arm_R_lower", r1=0.08, r2=0.06, depth=0.30, segs=8, loc=(0, -0.15, 0), parent=elbow_R, mat=prim_mat)
    # hand (gauntlet)
    smooth_sphere(f"{name}_hand_R", r=0.08, segs=12, rings=8, loc=(0, -0.30, 0), parent=elbow_R, mat=gold_mat)

    # LANCE attached to right hand (long pointed cone)
    lance_p = empty(f"{name}_lance_p", (0, -0.30, 0), parent=elbow_R)
    lance_p.rotation_euler = (0, 0, math.radians(facing_dir * 80))
    # lance shaft
    smooth_cone(f"{name}_lance_shaft", r1=0.06, r2=0.04, depth=3.5, segs=8, loc=(0, 1.75 * facing_dir, 0), parent=lance_p, mat=MAT_LANCE)
    # lance tip steel
    smooth_cone(f"{name}_lance_tip", r1=0.10, r2=0.0, depth=0.30, segs=8, loc=(0, 3.65 * facing_dir, 0), parent=lance_p, mat=MAT_LANCE_TIP)
    # lance hand grip
    smooth_sphere(f"{name}_lance_grip", r=0.10, segs=12, rings=8, loc=(0, 0.10 * facing_dir, 0), parent=lance_p, mat=MAT_WOOD_DARK)

    # left arm (carrying shield)
    arm_L_p = empty(f"{name}_arm_L_p", (-0.35, 2.20, 0.10), parent=knight_body_p)
    arm_L_p.rotation_euler = (math.radians(-20), 0, math.radians(20))
    smooth_cone(f"{name}_arm_L_upper", r1=0.10, r2=0.08, depth=0.30, segs=8, loc=(0, -0.15, 0), parent=arm_L_p, mat=prim_mat)
    elbow_L = empty(f"{name}_elbow_L", (0, -0.30, 0), parent=arm_L_p)
    smooth_cone(f"{name}_arm_L_lower", r1=0.08, r2=0.06, depth=0.25, segs=8, loc=(0, -0.12, 0), parent=elbow_L, mat=prim_mat)
    # SHIELD (kite shield)
    shield_p = empty(f"{name}_shield_p", (0, -0.20, 0), parent=elbow_L)
    # main shield body (oval kite)
    smooth_sphere(f"{name}_shield_body", r=0.40, segs=18, rings=14, loc=(0, -0.10, 0.15), parent=shield_p, mat=trim_mat, scale=(0.8, 1.3, 0.10))
    # shield trim
    smooth_sphere(f"{name}_shield_trim", r=0.42, segs=18, rings=14, loc=(0, -0.10, 0.18), parent=shield_p, mat=gold_mat, scale=(0.85, 1.35, 0.05))
    # central emblem (small sphere)
    smooth_sphere(f"{name}_shield_emblem", r=0.10, segs=14, rings=10, loc=(0, -0.10, 0.20), parent=shield_p, mat=gold_mat, scale=(0.85, 1.0, 0.50))

    # 2 LEGS (knight on horse — legs hanging down sides)
    for lk, lz in [("L", 0.20), ("R", -0.20)]:
        smooth_cone(f"{name}_kleg_{lk}_thigh", r1=0.10, r2=0.08, depth=0.45, segs=8, loc=(0.05, 1.50, lz), parent=knight_body_p, mat=prim_mat)
        smooth_cone(f"{name}_kleg_{lk}_calf", r1=0.07, r2=0.06, depth=0.35, segs=8, loc=(0.05, 1.10, lz), parent=knight_body_p, mat=prim_mat)
        # boot
        smooth_sphere(f"{name}_kleg_{lk}_boot", r=0.10, segs=12, rings=8, loc=(0.05, 0.90, lz), parent=knight_body_p, mat=gold_mat, scale=(1.4, 0.5, 1.0))

    return {"p": kp, "horse_legs": horse_legs, "knight_body": knight_body_p, "lance_p": lance_p}


# 2 KNIGHTS
knight_A = build_knight("knight_A", (-5, 0, 0), MAT_KNIGHT_A_PRIM, MAT_KNIGHT_A_TRIM, MAT_KNIGHT_A_GOLD, facing_dir=1, caparison_mat=MAT_CAPARISON_RED, horse_mat=MAT_HORSE_BROWN)
knight_B = build_knight("knight_B", (5, 0, 0), MAT_KNIGHT_B_PRIM, MAT_KNIGHT_B_TRIM, MAT_KNIGHT_B_SILVER, facing_dir=-1, caparison_mat=MAT_CAPARISON_BLUE, horse_mat=MAT_HORSE_WHITE)
knight_B["p"].rotation_euler = (0, math.radians(180), 0)


# --- TRIBUNE avec public ---------------------------------------------
tribune_p = empty("tribune_p", (0, 0, 6))
# main structure
beveled_cube("tribune_base", (10, 2.5, 2), bevel_offset=0.05, bevel_segments=2, loc=(0, 1.25, 0), parent=tribune_p, mat=MAT_TRIBUNE)
# canopy roof
beveled_cube("tribune_roof", (11, 0.20, 2.5), bevel_offset=0.04, bevel_segments=2, loc=(0, 3.5, 0), parent=tribune_p, mat=MAT_WOOD_DARK)
# 4 supporting columns
for ck, cx in [(0, -4), (1, -1.3), (2, 1.3), (3, 4)]:
    smooth_cone(f"tribune_col_{ck}", r1=0.10, r2=0.10, depth=2.5, segs=8, loc=(cx, 2.4, 0.85), parent=tribune_p, mat=MAT_WOOD_DARK)

# ROI sur trône (center of tribune)
king_p = empty("king_p", (0, 1.8, 0.3), parent=tribune_p)
# throne
beveled_cube("throne", (1.0, 1.2, 0.8), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.60, -0.3), parent=king_p, mat=MAT_THRONE)
# throne back high
beveled_cube("throne_back", (1.0, 2.0, 0.10), bevel_offset=0.04, bevel_segments=2, loc=(0, 1.20, -0.65), parent=king_p, mat=MAT_THRONE)
# king body (robe)
smooth_cone("king_body", r1=0.25, r2=0.35, depth=0.85, segs=14, loc=(0, 1.05, 0), parent=king_p, mat=MAT_KING_ROBE)
# king head
smooth_sphere("king_head", r=0.18, segs=18, rings=14, loc=(0, 1.65, 0), parent=king_p, mat=MAT_SPECTATOR)
# CROWN
smooth_cone("king_crown_base", r1=0.20, r2=0.18, depth=0.08, segs=12, loc=(0, 1.85, 0), parent=king_p, mat=MAT_KING_CROWN)
# 5 crown points
for pk in range(5):
    pa = pk * (math.pi * 2 / 5)
    smooth_cone(f"king_crown_p_{pk}", r1=0.04, r2=0.0, depth=0.20, segs=6, loc=(math.cos(pa) * 0.18, 1.95, math.sin(pa) * 0.18), parent=king_p, mat=MAT_KING_CROWN)

# 20 spectateurs sur tribune (silhouettes)
spectators = []
for sk in range(20):
    sx = -4.5 + (sk % 10) * 1.0
    sy = 1.8 + (sk // 10) * 0.40
    sp = empty(f"spec_{sk}_p", (sx, sy, 0.3 + (sk // 10) * 0.30), parent=tribune_p)
    spectators.append(sp)
    smooth_cone(f"spec_{sk}_b", r1=0.12, r2=0.18, depth=0.60, segs=6, loc=(0, 0.30, 0), parent=sp, mat=MAT_SPECTATOR)
    smooth_sphere(f"spec_{sk}_h", r=0.10, segs=10, rings=8, loc=(0, 0.65, 0), parent=sp, mat=MAT_SPECTATOR)
    sp["_phase"] = sk * 0.15

# 4 BANNIÈRES sur tribune corners
banners = []
for bi, bx in [(0, -4.5), (1, -1.5), (2, 1.5), (3, 4.5)]:
    bp = empty(f"banner_{bi}_p", (bx, 3.7, 0.5), parent=tribune_p)
    banners.append(bp)
    # pole
    smooth_cone(f"banner_{bi}_pole", r1=0.04, r2=0.04, depth=1.5, segs=6, loc=(0, 0.75, 0), parent=bp, mat=MAT_WOOD_DARK)
    # flag cloth
    flag_inner = empty(f"banner_{bi}_inner", (0, 0.40, 0), parent=bp)
    banners[bi] = {"p": bp, "inner": flag_inner, "phase": bi * 0.30}
    bmat = [MAT_FLAG_RED, MAT_FLAG_BLUE, MAT_FLAG_GOLD, MAT_FLAG_RED][bi]
    beveled_cube(f"banner_{bi}_cloth", (0.04, 0.50, 0.40), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.20), parent=flag_inner, mat=bmat)


# --- 4 TENTES médiévales ---------------------------------------------
TENT_MATS = [MAT_TENT_A, MAT_TENT_B, MAT_TENT_C, MAT_TENT_D]
for ti, (tx, ty, tz) in enumerate([(-9, 0, 4), (9, 0, 4), (-9, 0, -4), (9, 0, -4)]):
    tp = empty(f"tent_{ti}_p", (tx, ty, tz))
    tmat = TENT_MATS[ti]
    # main tent (cone)
    smooth_cone(f"tent_{ti}_main", r1=1.2, r2=0.0, depth=2.2, segs=14, loc=(0, 1.1, 0), parent=tp, mat=tmat)
    # 4 corner ties
    for ck in range(4):
        ca = ck * (math.pi * 2 / 4) + math.pi / 4
        smooth_cone(f"tent_{ti}_tie_{ck}", r1=0.02, r2=0.02, depth=1.3, segs=4, loc=(math.cos(ca) * 1.0, 0.6, math.sin(ca) * 1.0), parent=tp, mat=MAT_WOOD_DARK)
        bt = bpy.data.objects.get(f"tent_{ti}_tie_{ck}")
        if bt:
            bt.rotation_euler = (math.radians(60 * math.sin(ca)), 0, math.radians(-60 * math.cos(ca)))
    # door entrance
    beveled_cube(f"tent_{ti}_door", (0.30, 1.0, 0.05), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.5, 1.0), parent=tp, mat=MAT_WOOD_DARK)
    # small flag top
    smooth_cone(f"tent_{ti}_flag_pole", r1=0.03, r2=0.03, depth=0.50, segs=4, loc=(0, 2.40, 0), parent=tp, mat=MAT_WOOD_DARK)
    beveled_cube(f"tent_{ti}_flag", (0.04, 0.15, 0.20), bevel_offset=0.01, bevel_segments=2, loc=(0.10, 2.55, 0), parent=tp, mat=[MAT_FLAG_RED, MAT_FLAG_BLUE, MAT_FLAG_GOLD, MAT_FLAG_RED][ti])


# --- 6 BANNIÈRES poles autour de la lice ----------------------------
side_banners = []
for bk in range(6):
    a = bk * (math.pi * 2 / 6) + 0.3
    bx = math.cos(a) * 10
    bz = math.sin(a) * 5 - 2
    bp = empty(f"side_banner_{bk}_p", (bx, 0, bz))
    side_banners.append({"p": bp, "phase": bk * 0.30})
    # pole tall
    smooth_cone(f"side_banner_{bk}_pole", r1=0.05, r2=0.04, depth=4.0, segs=6, loc=(0, 2.0, 0), parent=bp, mat=MAT_WOOD_DARK)
    # banner cloth
    flag_inner = empty(f"side_banner_{bk}_inner", (0, 3.5, 0), parent=bp)
    side_banners[bk]["inner"] = flag_inner
    bmat = [MAT_FLAG_RED, MAT_FLAG_BLUE, MAT_FLAG_GOLD][bk % 3]
    beveled_cube(f"side_banner_{bk}_cloth", (0.04, 1.0, 0.45), bevel_offset=0.02, bevel_segments=2, loc=(0, -0.5, 0.25), parent=flag_inner, mat=bmat)


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

    # 2 KNIGHTS CHARGE vers center
    # knight A charges right
    a_x = -5 + tt * 4
    a_y = 0 + 0.10 * math.sin(2 * math.pi * tt * 4)  # gallop bounce
    kf(knight_A["p"], f, "location", (a_x, a_y, 0))
    # knight B charges left (rotated 180°)
    b_x = 5 - tt * 4
    b_y = 0 + 0.10 * math.sin(2 * math.pi * tt * 4 + math.pi)
    kf(knight_B["p"], f, "location", (b_x, b_y, 0))

    # 4 LEGS galop animation alternated for each horse
    for kn in [knight_A, knight_B]:
        for li, leg_root in kn["horse_legs"].items():
            # alternating phase : legs 0,3 vs 1,2
            phase = 0 if li in [0, 3] else math.pi
            leg_swing = math.radians(25 * math.sin(2 * math.pi * tt * 6 + phase))
            kf(leg_root, f, "rotation_euler", (leg_swing, 0, 0))

    # bannières (4 tribune) flutter
    for bd in banners:
        if isinstance(bd, dict):
            ph = bd["phase"]
            kf(bd["inner"], f, "rotation_euler", (math.radians(20 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)), 0, math.radians(8 * math.cos(2 * math.pi * tt * 3.5 + ph * math.pi))))

    # 6 side banners wave
    for sb in side_banners:
        ph = sb["phase"]
        kf(sb["inner"], f, "rotation_euler", (math.radians(15 * math.sin(2 * math.pi * tt * 2.5 + ph * math.pi)), 0, math.radians(5 * math.cos(2 * math.pi * tt * 3 + ph * math.pi))))

    # public wave (spectators bob up + down)
    for si, sp in enumerate(spectators):
        ph = sp["_phase"]
        bob = 0.10 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(sp, f, "rotation_euler", (math.radians(5 * bob), 0, 0))

    # sun pulse + halos breathe
    sp_sc = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 2)
    kf(sun, f, "scale", (sp_sc, sp_sc, sp_sc))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2]):
        br = 1.0 + 0.10 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.0)
        kf(halo, f, "scale", (br, br, br))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_knight_tournament] wrote {OUT}")
