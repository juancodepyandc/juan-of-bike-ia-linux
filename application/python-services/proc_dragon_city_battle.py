"""
proc_dragon_city_battle.py — 180e procédural AuroraIA, MILESTONE 180e + 44E QUALITÉ.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes + anatomie complète).

Combat épique dragon attaquant ville médiévale :
- dragon géant : body 6 segs + 2 wings + tête + jaw + flame + tail 8 segs + 4 legs + 12 spikes
- ville médiévale : 8 tours + 30 maisons + château central + remparts
- 4 catapultes
- 50 soldats silhouettes
- 30 explosions sol
- 80 sparks
- 20 plumes flammes
- ciel sombre orageux
- soleil rougeoyant
- 12 nuages noirs

Animations multi-axes simultanées :
- dragon vol cercle + bank + wings flap puissants + tail wave 8 segs + jaw open pulse + flame breath cyclique
- ville tours flammes pulse
- 30 explosions sol pulse
- 80 sparks parabolic
- 4 catapultes tirent cyclic
- 50 soldats panique
- 12 nuages drift

Sortie : output/3d/pbr_dragonbattle_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_dragonbattle_proc.glb"))

random.seed(0xD24C17)


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
MAT_SKY = make_mat("sky_dark_storm", (0.30, 0.15, 0.12), roughness=1.0, emi=(0.30, 0.12, 0.08), emi_strength=1.2)
MAT_CLOUD_DARK = make_mat("cloud_dark", (0.12, 0.08, 0.08), roughness=1.0, alpha=0.75, emi=(0.10, 0.05, 0.05), emi_strength=0.3)
MAT_SUN_RED = make_mat("sun_red", (1.0, 0.30, 0.10), roughness=0.0, emi=(1.0, 0.30, 0.10), emi_strength=13.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.30, 0.10), roughness=0.0, alpha=0.30, emi=(1.0, 0.30, 0.10), emi_strength=4.0)
MAT_GROUND = make_mat("ground", (0.20, 0.12, 0.08), roughness=0.95, emi=(0.10, 0.05, 0.03), emi_strength=0.3)
MAT_DRAGON_BODY = make_mat("dragon_body", (0.30, 0.08, 0.06), metallic=0.20, roughness=0.55, emi=(0.20, 0.05, 0.03), emi_strength=0.4)
MAT_DRAGON_BELLY = make_mat("dragon_belly", (0.85, 0.45, 0.15), roughness=0.40, emi=(0.45, 0.25, 0.08), emi_strength=0.7)
MAT_DRAGON_DARK = make_mat("dragon_dark", (0.12, 0.04, 0.03), roughness=0.65)
MAT_DRAGON_HORN = make_mat("dragon_horn", (0.85, 0.70, 0.35), metallic=0.5, roughness=0.30, emi=(0.30, 0.25, 0.10), emi_strength=0.5)
MAT_DRAGON_EYE = make_mat("dragon_eye", (1.0, 0.85, 0.20), roughness=0.0, emi=(1.0, 0.85, 0.20), emi_strength=18.0)
MAT_DRAGON_WING = make_mat("dragon_wing", (0.30, 0.10, 0.08), roughness=0.65, alpha=0.92, emi=(0.18, 0.05, 0.04), emi_strength=0.5)
MAT_FLAME = make_mat("flame", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85, emi=(1.0, 0.55, 0.10), emi_strength=18.0)
MAT_FLAME_INNER = make_mat("flame_inner", (1.0, 0.85, 0.30), roughness=0.0, alpha=0.85, emi=(1.0, 0.85, 0.30), emi_strength=22.0)
MAT_STONE_TOWER = make_mat("stone_tower", (0.45, 0.40, 0.35), roughness=0.85)
MAT_STONE_DARK = make_mat("stone_dark", (0.25, 0.22, 0.20), roughness=0.95)
MAT_ROOF_RED = make_mat("roof_red", (0.55, 0.20, 0.15), roughness=0.7)
MAT_WOOD = make_mat("wood", (0.30, 0.18, 0.10), roughness=0.7)
MAT_EXPLOSION = make_mat("explosion", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85, emi=(1.0, 0.55, 0.10), emi_strength=14.0)
MAT_SPARK = make_mat("spark", (1.0, 0.85, 0.30), roughness=0.0, emi=(1.0, 0.85, 0.30), emi_strength=12.0)
MAT_FEATHER_FLAME = make_mat("feather_flame", (1.0, 0.55, 0.15), roughness=0.10, alpha=0.85, emi=(1.0, 0.55, 0.15), emi_strength=12.0)
MAT_SOLDIER = make_mat("soldier", (0.25, 0.20, 0.18), roughness=0.6)
MAT_FLAG_MED = make_mat("flag_med", (0.55, 0.20, 0.15), roughness=0.6, emi=(0.20, 0.05, 0.05), emi_strength=0.3)
MAT_CASTLE_GOLD = make_mat("castle_gold", (0.85, 0.65, 0.30), metallic=0.6, roughness=0.30, emi=(0.30, 0.25, 0.10), emi_strength=0.5)


# --- backdrop : dark stormy sky -----------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 12), mat=MAT_SKY)
# dying red sun
sun_p = empty("sun_p", (-9, 13, 10))
sun = smooth_sphere("sun_red", r=1.5, segs=24, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_RED)
sun_halo_1 = smooth_sphere("sun_halo_1", r=2.3, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=3.2, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
# 12 dark clouds
clouds = []
for ck in range(12):
    cx = random.uniform(-18, 18)
    cy = random.uniform(11, 15)
    cz = random.uniform(4, 14)
    cp = empty(f"cloud_{ck}", (cx, cy, cz))
    clouds.append(cp)
    for j in range(3):
        smooth_sphere(f"cloud_{ck}_p_{j}", r=random.uniform(0.8, 1.3), segs=14, rings=10, loc=(random.uniform(-1, 1), random.uniform(-0.2, 0.2), random.uniform(-0.6, 0.6)), parent=cp, mat=MAT_CLOUD_DARK, scale=(1.0, 0.55, 1.0))
    cp["_base_x"] = cx
    cp["_speed"] = random.uniform(0.4, 0.8)

# ground
ground = beveled_cube("ground", (40, 0.2, 30), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_GROUND)


# --- VILLE MÉDIÉVALE centrale -----------------------------------------
# CHATEAU central
castle_p = empty("castle", (0, 0, -1))
# main keep
beveled_cube("castle_keep", (3, 4, 2.5), bevel_offset=0.05, bevel_segments=2, loc=(0, 2, 0), parent=castle_p, mat=MAT_STONE_TOWER)
# 4 corner towers
for ck in range(4):
    ca = ck * (math.pi * 2 / 4) + math.pi / 4
    cx = math.cos(ca) * 2.0
    cz = math.sin(ca) * 2.0
    smooth_cone(f"castle_tower_{ck}", r1=0.55, r2=0.50, depth=5.5, segs=14, loc=(cx, 2.75, cz), parent=castle_p, mat=MAT_STONE_TOWER)
    # tower roof
    smooth_cone(f"castle_roof_{ck}", r1=0.65, r2=0.0, depth=1.0, segs=10, loc=(cx, 6.0, cz), parent=castle_p, mat=MAT_ROOF_RED)
    # flag on tower
    flag_p = empty(f"castle_flag_p_{ck}", (cx, 6.8, cz), parent=castle_p)
    smooth_cone(f"castle_flagpole_{ck}", r1=0.03, r2=0.03, depth=0.50, segs=4, loc=(0, 0.25, 0), parent=flag_p, mat=MAT_WOOD)
    flag_inner = empty(f"castle_flag_inner_{ck}", (0, 0.40, 0), parent=flag_p)
    beveled_cube(f"castle_flag_{ck}", (0.04, 0.20, 0.25), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.15), parent=flag_inner, mat=MAT_FLAG_MED)
# main entrance (gate)
beveled_cube("castle_gate", (1.2, 1.8, 0.20), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.9, 1.30), parent=castle_p, mat=MAT_WOOD)
# golden dome top
smooth_sphere("castle_dome", r=0.75, segs=20, rings=14, loc=(0, 4.5, 0), parent=castle_p, mat=MAT_CASTLE_GOLD, scale=(1.0, 0.7, 1.0))

# 8 TOURS médiévales périphériques en flammes
city_towers = []
TOWER_POSITIONS = [(-6, 0, 3), (-3, 0, 5), (3, 0, 5), (6, 0, 3), (-6, 0, -4), (-3, 0, -6), (3, 0, -6), (6, 0, -4)]
for ti, (tx, ty, tz) in enumerate(TOWER_POSITIONS):
    tp = empty(f"tower_{ti}_p", (tx, ty, tz))
    city_towers.append(tp)
    # tower body
    th = random.uniform(2.5, 3.5)
    smooth_cone(f"tower_{ti}_body", r1=0.40, r2=0.35, depth=th, segs=12, loc=(0, th / 2, 0), parent=tp, mat=MAT_STONE_TOWER if ti % 2 == 0 else MAT_STONE_DARK)
    # roof
    smooth_cone(f"tower_{ti}_roof", r1=0.50, r2=0.0, depth=0.80, segs=10, loc=(0, th + 0.40, 0), parent=tp, mat=MAT_ROOF_RED)
    # flame on top (ville en flammes!)
    flame_p = empty(f"tower_{ti}_fl_p", (0, th + 1.20, 0), parent=tp)
    f_out = smooth_sphere(f"tower_{ti}_fl", r=0.35, segs=14, rings=10, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME, scale=(0.8, 1.8, 0.8))
    f_in = smooth_sphere(f"tower_{ti}_fl_in", r=0.22, segs=12, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME_INNER, scale=(0.6, 2.0, 0.6))
    tp["_flame_p"] = flame_p
    tp["_fl_out"] = f_out
    tp["_fl_in"] = f_in
    tp["_phase"] = ti * 0.25

# 30 MAISONS médiévales (small)
houses = []
for hi in range(30):
    a = hi * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(8, 13)
    hx = math.cos(a) * r
    hz = math.sin(a) * r * 0.7
    hp = empty(f"house_{hi}_p", (hx, 0, hz))
    houses.append(hp)
    # body cube
    beveled_cube(f"house_{hi}_body", (random.uniform(0.5, 0.8), random.uniform(0.6, 1.0), random.uniform(0.5, 0.8)), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.40, 0), parent=hp, mat=MAT_STONE_TOWER if hi % 2 == 0 else MAT_WOOD)
    # roof
    smooth_cone(f"house_{hi}_roof", r1=0.55, r2=0.0, depth=0.50, segs=6, loc=(0, 1.0, 0), parent=hp, mat=MAT_ROOF_RED)
    # some houses on fire
    if hi % 3 == 0:
        hf = smooth_sphere(f"house_{hi}_fl", r=0.20, segs=10, rings=8, loc=(0, 1.3, 0), parent=hp, mat=MAT_FLAME, scale=(0.7, 1.6, 0.7))
        hp["_flame"] = hf

# REMPARTS (walls around city) — 8 segments
for wk in range(8):
    wa = wk * (math.pi * 2 / 8) + math.pi / 8
    next_wa = ((wk + 1) % 8) * (math.pi * 2 / 8) + math.pi / 8
    x1 = math.cos(wa) * 7.5
    z1 = math.sin(wa) * 7.5
    x2 = math.cos(next_wa) * 7.5
    z2 = math.sin(next_wa) * 7.5
    midx = (x1 + x2) / 2
    midz = (z1 + z2) / 2
    angle = math.atan2(z2 - z1, x2 - x1)
    length = math.sqrt((x2 - x1) ** 2 + (z2 - z1) ** 2)
    wall = beveled_cube(f"rempart_{wk}", (length, 1.5, 0.4), bevel_offset=0.04, bevel_segments=2, loc=(midx, 0.75, midz), mat=MAT_STONE_TOWER)
    wall.rotation_euler = (0, -angle, 0)


# --- DRAGON GÉANT (vol au-dessus de la ville) -----------------------
dragon_p = empty("dragon", (0, 9, -2))

# BODY 6 segments tapered
body_segs = []
for bs in range(6):
    rb = 0.55 - bs * 0.06
    bx_off = -1.5 + bs * 0.65
    seg = smooth_sphere(f"dragon_body_{bs}", r=rb, segs=22, rings=16, loc=(bx_off, 0, 0), parent=dragon_p, mat=MAT_DRAGON_BODY, scale=(1.2, 0.95, 0.95))
    body_segs.append(seg)
    # belly highlight
    smooth_sphere(f"dragon_belly_{bs}", r=rb * 0.65, segs=18, rings=12, loc=(bx_off, -0.30, 0), parent=dragon_p, mat=MAT_DRAGON_BELLY, scale=(1.2, 0.50, 0.85))

# 12 SPIKES back
for sk in range(12):
    sx_off = -1.5 + sk * 0.40
    spike = smooth_cone(f"dragon_spike_{sk}", r1=0.10, r2=0.0, depth=0.50, segs=8, loc=(sx_off, 0.50, 0), parent=dragon_p, mat=MAT_DRAGON_HORN)

# HEAD articulé
head_p = empty("dragon_head_p", (1.80, 0.10, 0), parent=dragon_p)
# main head
head = smooth_sphere("dragon_head", r=0.60, segs=24, rings=18, loc=(0.25, 0, 0), parent=head_p, mat=MAT_DRAGON_BODY, scale=(1.4, 1.0, 1.0))
# JAW (open)
jaw_p = empty("dragon_jaw_p", (0.40, -0.20, 0), parent=head_p)
jaw_p.rotation_euler = (0, 0, math.radians(-20))  # jaw open
smooth_sphere("dragon_jaw", r=0.40, segs=20, rings=14, loc=(0, -0.15, 0), parent=jaw_p, mat=MAT_DRAGON_DARK, scale=(1.4, 0.45, 0.9))
# 2 horns
for hk, hz in [("L", 0.20), ("R", -0.20)]:
    horn = smooth_cone(f"dragon_horn_{hk}", r1=0.08, r2=0.0, depth=0.65, segs=8, loc=(-0.10, 0.40, hz), parent=head_p, mat=MAT_DRAGON_HORN)
    horn.rotation_euler = (math.radians(-25), 0, math.radians(-15 if hz > 0 else 15))
# 2 eyes intense
for ek, ez in [("L", 0.20), ("R", -0.20)]:
    smooth_sphere(f"dragon_eye_{ek}", r=0.12, segs=14, rings=10, loc=(0.35, 0.20, ez), parent=head_p, mat=MAT_DRAGON_EYE)
# nostrils
for nk, nz in [("L", 0.10), ("R", -0.10)]:
    smooth_sphere(f"dragon_nostril_{nk}", r=0.04, segs=10, rings=6, loc=(0.55, 0.05, nz), parent=head_p, mat=MAT_DRAGON_DARK)
# 6 spike teeth visible in open jaw
for tk in range(6):
    tx = -0.20 + tk * 0.10
    smooth_cone(f"dragon_tooth_{tk}", r1=0.025, r2=0.0, depth=0.10, segs=4, loc=(0.30 + tx, -0.10, 0), parent=head_p, mat=MAT_DRAGON_HORN)

# FLAME BREATH (issuing from mouth — cyclic)
flame_breath_p = empty("flame_breath_p", (2.50, -0.10, 0), parent=dragon_p)
flame_breath_out = smooth_cone("flame_breath_out", r1=0.0, r2=0.50, depth=2.5, segs=14, loc=(0.85, 0, 0), parent=flame_breath_p, mat=MAT_FLAME)
flame_breath_out.rotation_euler = (0, 0, math.radians(-90))
flame_breath_in = smooth_cone("flame_breath_in", r1=0.0, r2=0.30, depth=2.2, segs=12, loc=(0.85, 0, 0), parent=flame_breath_p, mat=MAT_FLAME_INNER)
flame_breath_in.rotation_euler = (0, 0, math.radians(-90))

# 2 WINGS spread
wing_L_p = empty("wing_L_p", (-0.20, 0.40, 0), parent=dragon_p)
wing_R_p = empty("wing_R_p", (-0.20, 0.40, 0), parent=dragon_p)
wing_L_p.rotation_euler = (0, 0, math.radians(20))
wing_R_p.rotation_euler = (0, 0, math.radians(-20))

# each wing structure (4 phalanges + 3 membranes)
for side, wing_p, sign in [("L", wing_L_p, 1), ("R", wing_R_p, -1)]:
    # main bone
    smooth_cone(f"wing_{side}_main", r1=0.10, r2=0.05, depth=2.5, segs=10, loc=(0, 0, sign * 1.25), parent=wing_p, mat=MAT_DRAGON_BODY)
    bp = bpy.data.objects.get(f"wing_{side}_main")
    if bp:
        bp.rotation_euler = (math.radians(90 * sign), 0, 0)
    # 4 phalanges
    for ph in range(4):
        pa = -0.5 + ph * 0.30
        phal = smooth_cone(f"wing_{side}_ph_{ph}", r1=0.06, r2=0.02, depth=1.6, segs=6, loc=(pa * 0.5, 0, sign * 2.0), parent=wing_p, mat=MAT_DRAGON_BODY)
        phal.rotation_euler = (math.radians(90 * sign + (ph - 1.5) * 15), 0, 0)
    # 3 membrane panels
    for mb in range(3):
        mba = -0.20 + mb * 0.20
        smooth_sphere(f"wing_{side}_mb_{mb}", r=0.55, segs=14, rings=10, loc=(mba * 0.6, 0, sign * 2.0), parent=wing_p, mat=MAT_DRAGON_WING, scale=(2.0, 0.05, 2.0))

# TAIL 8 segments wave parented sequentially
tail_p = empty("dragon_tail_p", (-2.0, 0, 0), parent=dragon_p)
tail_segs = []
cur_parent = tail_p
for t in range(8):
    tseg_p = empty(f"tail_seg_p_{t}", (-0.45, 0, 0), parent=cur_parent)
    rt = 0.30 - t * 0.025
    smooth_sphere(f"tail_seg_{t}", r=rt, segs=14, rings=10, loc=(-0.22, 0, 0), parent=tseg_p, mat=MAT_DRAGON_BODY, scale=(1.4, 0.95, 0.95))
    tail_segs.append(tseg_p)
    cur_parent = tseg_p
# tail tip spike
smooth_cone("tail_tip", r1=0.10, r2=0.0, depth=0.40, segs=8, loc=(-0.20, 0, 0), parent=cur_parent, mat=MAT_DRAGON_HORN)

# 4 LEGS articulated
dragon_legs = []
LEG_POSITIONS = [(-0.50, -0.35, 0.40), (-0.50, -0.35, -0.40), (0.80, -0.35, 0.40), (0.80, -0.35, -0.40)]
for lk, base_pos in enumerate(LEG_POSITIONS):
    leg_root = empty(f"leg_{lk}_root", base_pos, parent=dragon_p)
    leg_root.rotation_euler = (0, 0, math.radians(20))
    # thigh
    smooth_cone(f"leg_{lk}_thigh", r1=0.12, r2=0.10, depth=0.50, segs=8, loc=(0, -0.25, 0), parent=leg_root, mat=MAT_DRAGON_BODY)
    # knee joint
    knee_p = empty(f"leg_{lk}_knee_p", (0, -0.50, 0), parent=leg_root)
    knee_p.rotation_euler = (0, 0, math.radians(-30))
    # calf
    smooth_cone(f"leg_{lk}_calf", r1=0.10, r2=0.08, depth=0.45, segs=8, loc=(0, -0.22, 0), parent=knee_p, mat=MAT_DRAGON_BODY)
    # foot + 3 claws
    smooth_sphere(f"leg_{lk}_foot", r=0.10, segs=12, rings=8, loc=(0, -0.45, 0), parent=knee_p, mat=MAT_DRAGON_DARK)
    for ck in range(3):
        ca = ck * (math.pi * 2 / 3)
        claw = smooth_cone(f"leg_{lk}_claw_{ck}", r1=0.025, r2=0.0, depth=0.10, segs=6, loc=(math.cos(ca) * 0.10, -0.55, math.sin(ca) * 0.10), parent=knee_p, mat=MAT_DRAGON_HORN)
    dragon_legs.append(leg_root)


# --- 4 CATAPULTES défendant ville -----------------------------------
catapults = []
CATA_POSITIONS = [(-6, 0, 6), (6, 0, 6), (-6, 0, -7), (6, 0, -7)]
for ci, (cx, cy, cz) in enumerate(CATA_POSITIONS):
    cp = empty(f"cata_{ci}_p", (cx, cy, cz))
    catapults.append({"p": cp, "phase": ci * 0.40})
    # base
    beveled_cube(f"cata_{ci}_base", (0.85, 0.30, 0.55), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.15, 0), parent=cp, mat=MAT_WOOD)
    # 4 wheels
    for wk, (wx, wz) in enumerate([(-0.4, -0.25), (0.4, -0.25), (-0.4, 0.25), (0.4, 0.25)]):
        wheel = smooth_cone(f"cata_{ci}_w_{wk}", r1=0.18, r2=0.18, depth=0.08, segs=14, loc=(wx, 0.18, wz), parent=cp, mat=MAT_STONE_DARK)
        wheel.rotation_euler = (math.radians(90), 0, 0)
    # arm (pivoting) — pointing up
    arm_p = empty(f"cata_{ci}_arm_p", (0, 0.35, 0), parent=cp)
    arm_p.rotation_euler = (0, 0, math.radians(-30))  # initial position
    smooth_cone(f"cata_{ci}_arm", r1=0.08, r2=0.06, depth=1.2, segs=8, loc=(0, 0.55, 0), parent=arm_p, mat=MAT_WOOD)
    # bucket (ball at end)
    smooth_sphere(f"cata_{ci}_bucket", r=0.18, segs=14, rings=10, loc=(0, 1.10, 0), parent=arm_p, mat=MAT_STONE_DARK)
    catapults[ci]["arm_p"] = arm_p


# --- 50 SOLDATS silhouettes panique ---------------------------------
soldiers = []
for sk in range(50):
    a = sk * (math.pi * 2 / 50) + random.uniform(-0.3, 0.3)
    r = random.uniform(5, 11)
    sx = math.cos(a) * r
    sz = math.sin(a) * r
    sp = empty(f"soldier_{sk}_p", (sx, 0, sz))
    # body cone
    smooth_cone(f"soldier_{sk}_b", r1=0.10, r2=0.14, depth=0.50, segs=6, loc=(0, 0.30, 0), parent=sp, mat=MAT_SOLDIER)
    # head
    smooth_sphere(f"soldier_{sk}_h", r=0.08, segs=10, rings=8, loc=(0, 0.60, 0), parent=sp, mat=MAT_SOLDIER)
    sp["_base"] = (sx, sz)
    sp["_phase"] = sk * 0.10
    soldiers.append(sp)


# --- 30 EXPLOSIONS sol -----------------------------------------------
explosions = []
for ek in range(30):
    a = ek * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(3, 9)
    ex = math.cos(a) * r
    ez = math.sin(a) * r
    epx = smooth_sphere(f"explo_{ek}", r=random.uniform(0.25, 0.50), segs=14, rings=10, loc=(ex, 0.15, ez), mat=MAT_EXPLOSION, scale=(1.0, 0.5, 1.0))
    epx["_base"] = (ex, 0.15, ez)
    epx["_phase"] = ek * 0.15
    explosions.append(epx)


# --- 80 SPARKS parabolic --------------------------------------------
sparks = []
for sk in range(80):
    a = sk * (math.pi * 2 / 80) + random.uniform(-0.5, 0.5)
    r = random.uniform(2, 10)
    sx = math.cos(a) * r
    sz = math.sin(a) * r
    sp_obj = smooth_sphere(f"spark_{sk}", r=random.uniform(0.025, 0.05), segs=8, rings=6, loc=(sx, 0.5, sz), mat=MAT_SPARK)
    sp_obj["_base_x"] = sx
    sp_obj["_base_z"] = sz
    sp_obj["_phase"] = sk * 0.08
    sp_obj["_speed"] = random.uniform(0.8, 1.6)
    sparks.append(sp_obj)


# --- 20 PLUMES FLAMMES drift -----------------------------------------
flame_feathers = []
for fk in range(20):
    a = fk * (math.pi * 2 / 20) + random.uniform(-0.2, 0.2)
    r = random.uniform(4, 9)
    fy = random.uniform(3, 8)
    fx = math.cos(a) * r
    fz = math.sin(a) * r
    fp = empty(f"flame_f_{fk}_p", (fx, fy, fz))
    smooth_cone(f"flame_f_{fk}_b", r1=0.06, r2=0.04, depth=0.18, segs=6, loc=(0, 0.05, 0), parent=fp, mat=MAT_DRAGON_BODY)
    smooth_cone(f"flame_f_{fk}_m", r1=0.04, r2=0.03, depth=0.18, segs=6, loc=(0, 0.18, 0), parent=fp, mat=MAT_FLAME)
    smooth_cone(f"flame_f_{fk}_t", r1=0.03, r2=0.0, depth=0.20, segs=6, loc=(0, 0.35, 0), parent=fp, mat=MAT_FEATHER_FLAME)
    fp["_base"] = (fx, fy, fz)
    fp["_phase"] = fk * 0.15
    flame_feathers.append(fp)


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

    # DRAGON : vol en cercle autour ville + bank
    orbit_ang = tt * 2 * math.pi * 0.5
    dx = math.cos(orbit_ang) * 9
    dy = 9 + 1.5 * math.sin(2 * math.pi * tt * 1.0)
    dz = math.sin(orbit_ang) * 8
    kf(dragon_p, f, "location", (dx, dy, dz))
    face_yaw = orbit_ang + math.pi / 2
    bank = math.radians(25 * math.sin(2 * math.pi * tt * 1.5))
    pitch = math.radians(10 * math.sin(2 * math.pi * tt * 2))
    kf(dragon_p, f, "rotation_euler", (pitch, face_yaw, bank))

    # WINGS flap powerful
    flap = math.radians(50) * math.sin(2 * math.pi * tt * 3.5)
    kf(wing_L_p, f, "rotation_euler", (flap, 0, math.radians(20)))
    kf(wing_R_p, f, "rotation_euler", (-flap, 0, math.radians(-20)))

    # TAIL wave 8 segments propagated
    for ti, ts in enumerate(tail_segs):
        wave_x = math.radians(20) * math.sin(2 * math.pi * tt * 2.5 - ti * 0.5)
        wave_y = math.radians(15) * math.cos(2 * math.pi * tt * 2.2 - ti * 0.4)
        kf(ts, f, "rotation_euler", (wave_x, wave_y, 0))

    # JAW open pulse
    jaw_rot = math.radians(-20 + 15 * math.sin(2 * math.pi * tt * 2))
    kf(jaw_p, f, "rotation_euler", (0, 0, jaw_rot))

    # HEAD turn slight
    kf(head_p, f, "rotation_euler", (0, math.radians(15 * math.sin(2 * math.pi * tt * 1.2)), 0))

    # FLAME BREATH cyclic (intense bursts)
    flame_intensity = 0.3 + 0.7 * abs(math.sin(2 * math.pi * tt * 1.5))
    kf(flame_breath_out, f, "scale", (flame_intensity, flame_intensity, flame_intensity))
    kf(flame_breath_in, f, "scale", (flame_intensity * 0.85, flame_intensity * 0.85, flame_intensity * 0.85))

    # 4 LEGS subtle articulate
    for lk, leg_root in enumerate(dragon_legs):
        leg_swing = math.radians(15 * math.sin(2 * math.pi * tt * 1.5 + lk * 0.5))
        kf(leg_root, f, "rotation_euler", (0, 0, math.radians(20) + leg_swing))

    # 8 city towers flames pulse
    for tp in city_towers:
        ph = tp["_phase"]
        ps = 1.0 + 0.20 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(tp["_fl_out"], f, "scale", (ps * 0.8, ps * 1.8, ps * 0.8))
        kf(tp["_fl_in"], f, "scale", (ps * 0.6, ps * 2.0, ps * 0.6))

    # 4 catapults : arm rotation (cyclic firing)
    for cd in catapults:
        ph = cd["phase"]
        # arm rotate -30° → +30° (fire cycle)
        arm_ang = math.radians(-30) + math.radians(60) * (1 - math.cos(2 * math.pi * tt * 0.7 + ph * math.pi)) / 2
        kf(cd["arm_p"], f, "rotation_euler", (0, 0, arm_ang))

    # 50 soldiers panique : run xy
    for sl in soldiers:
        bx_, bz_ = sl["_base"]
        ph = sl["_phase"]
        nx = bx_ + 0.5 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        nz = bz_ + 0.4 * math.cos(2 * math.pi * tt * 1.8 + ph * math.pi)
        kf(sl, f, "location", (nx, 0, nz))
        kf(sl, f, "rotation_euler", (0, math.radians(180 * tt + ph * 60), 0))

    # 30 explosions sol pulse
    for ex in explosions:
        ph = ex["_phase"]
        bx_, by_, bz_ = ex["_base"]
        intensity = 0.5 + 0.5 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        sc = 0.5 + intensity * 1.8
        kf(ex, f, "scale", (sc, sc * 0.6, sc))

    # 80 sparks parabolic
    for sp_obj in sparks:
        bx_ = sp_obj["_base_x"]
        bz_ = sp_obj["_base_z"]
        ph = sp_obj["_phase"]
        spd = sp_obj["_speed"]
        local = (tt * spd + ph) % 1.0
        py = 0.3 + 5.0 * local * (1 - local)
        nx = bx_ * (1 + local * 0.5)
        nz = bz_ * (1 + local * 0.5)
        kf(sp_obj, f, "location", (nx, py, nz))
        sc = 0.7 + 0.5 * abs(math.sin(2 * math.pi * tt * 5 + ph * math.pi))
        kf(sp_obj, f, "scale", (sc, sc, sc))

    # 20 flame feathers drift
    for ff in flame_feathers:
        bx_, by_, bz_ = ff["_base"]
        ph = ff["_phase"]
        nx = bx_ + 0.8 * math.sin(2 * math.pi * tt * 0.6 + ph * math.pi)
        ny = by_ + 0.6 * math.cos(2 * math.pi * tt * 0.8 + ph * math.pi)
        nz = bz_ + 0.6 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        kf(ff, f, "location", (nx, ny, nz))
        kf(ff, f, "rotation_euler", (math.radians(180 * tt + ph * 30), math.radians(120 * tt + ph * 40), math.radians(90 * tt + ph * 20)))

    # 12 clouds drift
    for cp in clouds:
        bx_ = cp["_base_x"]
        spd = cp["_speed"]
        new_x = bx_ + tt * spd * 5 - 2.5
        if new_x > 18:
            new_x -= 36
        kf(cp, f, "location", (new_x, cp.location.y if f > 1 else cp.location.y, cp.location.z))

    # sun pulse
    sp_sc = 1.0 + 0.05 * math.sin(2 * math.pi * tt * 1.5)
    kf(sun, f, "scale", (sp_sc, sp_sc, sp_sc))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2]):
        br = 1.0 + 0.10 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.0)
        kf(halo, f, "scale", (br, br, br))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_dragon_city_battle] wrote {OUT}")
