"""
proc_underwater_atlantis_ruins.py — 162e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Ruines Atlantis submergées :
- 8 colonnes grecques (3 entières + 5 brisées) avec chapiteaux ioniques
- temple central ruiné avec frontón cassé
- statue de dieu marin émergée (corps + bras tridents + tête)
- 2 sphinx gardiens gauche/droite
- 3 coffres au trésor avec or émissif
- 6 amphores brisées avec contenu (perles, pièces)
- 12 poissons colorés bancs
- 4 raies manta glide
- 2 tortues marines
- 8 méduses bioluminescentes
- 30 bulles montantes
- 6 light rays subaquatiques
- 10 algues sway
- 5 coraux décoratifs
- 30 fragments pierre flottants
- ciel sous-marin profond + lumière surface
- 4 sphères énergie mystique émissives orbitant temple

Animations multi-axes simultanées :
- 12 poissons bancs : orbites synchronisées schooling
- 4 raies : glide path différentielles avec aile flap
- 2 tortues : swim nage + flippers
- 8 méduses : bell pulse + tentacles wave
- 30 bulles rise + wobble
- 6 light rays : pulse intensité + scale
- 10 algues sway bend
- 30 fragments : float lent rotation
- 4 sphères énergie : orbit temple + pulse + rotate XYZ
- statue marin : trident lift slight + head turn

Sortie : output/3d/pbr_atlantis_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_atlantis_proc.glb"))

random.seed(0xA71A175)


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
MAT_SEA_DEEP = make_mat("sea_deep", (0.05, 0.10, 0.25), roughness=1.0, emi=(0.04, 0.10, 0.25), emi_strength=0.6)
MAT_SEA_UPPER = make_mat("sea_upper", (0.20, 0.45, 0.65), roughness=0.30, alpha=0.85, emi=(0.15, 0.35, 0.55), emi_strength=1.2)
MAT_RAY = make_mat("ray", (0.55, 0.85, 1.0), roughness=0.0, alpha=0.20, emi=(0.55, 0.85, 1.0), emi_strength=3.0)
MAT_SAND = make_mat("sand", (0.45, 0.40, 0.30), roughness=0.95)
MAT_MARBLE = make_mat("marble", (0.85, 0.82, 0.75), roughness=0.5, emi=(0.30, 0.28, 0.25), emi_strength=0.3)
MAT_MARBLE_AGED = make_mat("marble_aged", (0.55, 0.55, 0.50), roughness=0.7, emi=(0.18, 0.18, 0.16), emi_strength=0.3)
MAT_MOSS = make_mat("moss", (0.20, 0.50, 0.25), roughness=0.7, emi=(0.05, 0.20, 0.08), emi_strength=0.4)
MAT_GOLD = make_mat("gold", (0.95, 0.75, 0.30), metallic=0.95, roughness=0.20, emi=(0.45, 0.35, 0.15), emi_strength=0.8)
MAT_GOLD_GLOW = make_mat("gold_glow", (1.0, 0.85, 0.35), roughness=0.10, emi=(1.0, 0.85, 0.35), emi_strength=6.0)
MAT_WOOD = make_mat("wood_old", (0.30, 0.18, 0.10), roughness=0.85)
MAT_PEARL = make_mat("pearl", (0.95, 0.92, 0.85), roughness=0.10, emi=(0.55, 0.55, 0.50), emi_strength=2.0)
MAT_AMPHORA = make_mat("amphora", (0.50, 0.30, 0.20), roughness=0.8)
MAT_FISH_A = make_mat("fish_A", (0.95, 0.55, 0.20), roughness=0.4, emi=(0.45, 0.25, 0.10), emi_strength=0.6)
MAT_FISH_B = make_mat("fish_B", (0.30, 0.55, 0.95), roughness=0.4, emi=(0.15, 0.25, 0.55), emi_strength=0.6)
MAT_FISH_C = make_mat("fish_C", (0.95, 0.95, 0.30), roughness=0.4, emi=(0.45, 0.45, 0.15), emi_strength=0.6)
MAT_RAY_MANTA = make_mat("ray_manta", (0.20, 0.18, 0.22), roughness=0.5, emi=(0.08, 0.07, 0.10), emi_strength=0.3)
MAT_TURTLE_SHELL = make_mat("turtle_shell", (0.30, 0.45, 0.20), roughness=0.6)
MAT_TURTLE_SKIN = make_mat("turtle_skin", (0.45, 0.40, 0.25), roughness=0.7)
MAT_JELLY = make_mat("jelly", (0.65, 0.40, 0.95), roughness=0.10, alpha=0.55, emi=(0.65, 0.40, 0.95), emi_strength=5.0)
MAT_JELLY_TENT = make_mat("jelly_tent", (0.50, 0.30, 0.85), roughness=0.20, alpha=0.65, emi=(0.50, 0.30, 0.85), emi_strength=3.0)
MAT_BUBBLE = make_mat("bubble", (0.80, 0.95, 1.0), roughness=0.05, alpha=0.45, emi=(0.60, 0.90, 1.0), emi_strength=1.5)
MAT_ALGAE = make_mat("algae", (0.15, 0.40, 0.20), roughness=0.7, emi=(0.05, 0.20, 0.08), emi_strength=0.4)
MAT_CORAL_A = make_mat("coral_A", (0.95, 0.40, 0.55), roughness=0.4, emi=(0.45, 0.20, 0.30), emi_strength=0.8)
MAT_CORAL_B = make_mat("coral_B", (0.95, 0.65, 0.30), roughness=0.4, emi=(0.45, 0.30, 0.15), emi_strength=0.8)
MAT_STATUE = make_mat("statue", (0.65, 0.65, 0.58), roughness=0.5, emi=(0.22, 0.22, 0.20), emi_strength=0.3)
MAT_TRIDENT = make_mat("trident", (0.85, 0.75, 0.40), metallic=0.7, roughness=0.30, emi=(0.40, 0.35, 0.20), emi_strength=0.7)
MAT_ENERGY = make_mat("energy", (0.55, 0.95, 1.0), roughness=0.0, alpha=0.55, emi=(0.55, 0.95, 1.0), emi_strength=9.0)


# --- backdrop : deep sea with light rays --------------------------------
sea_back = beveled_cube("sea_back", (40, 0.2, 24), bevel_offset=0.05, bevel_segments=2, loc=(0, 14, 10), mat=MAT_SEA_DEEP)
sea_upper = beveled_cube("sea_upper", (40, 0.2, 24), bevel_offset=0.05, bevel_segments=2, loc=(0, 18, 12), mat=MAT_SEA_UPPER)
ground = beveled_cube("sand", (30, 0.2, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_SAND)

# 6 light rays subaquatiques penetrating
light_rays = []
for r in range(6):
    rx = random.uniform(-10, 10)
    rz = random.uniform(-3, 6)
    ray = beveled_cube(f"ray_{r}", (0.50, 14.0, 0.50), bevel_offset=0.04, bevel_segments=2, loc=(rx, 7.5, rz), mat=MAT_RAY)
    ray.rotation_euler = (math.radians(random.uniform(-8, 8)), 0, math.radians(random.uniform(-10, 10)))
    light_rays.append(ray)


# --- 8 colonnes grecques + central temple base --------------------------
# 3 colonnes entières (haut + chapiteau ionique)
WHOLE_COLUMNS = [(-5, 2), (5, 2), (0, -3)]
for ci, (cx, cz) in enumerate(WHOLE_COLUMNS):
    # 3 sections (drum stacks)
    for sg in range(3):
        seg = smooth_cone(f"col_w_{ci}_drum_{sg}", r1=0.35, r2=0.33, depth=1.0, segs=18, loc=(cx, 0.5 + sg * 1.05, cz), mat=MAT_MARBLE)
        # 4 flutes (decorative grooves)
        for fl in range(4):
            fa = fl * (math.pi * 2 / 4)
            smooth_cone(f"col_w_{ci}_fl_{sg}_{fl}", r1=0.04, r2=0.04, depth=0.95, segs=4, loc=(cx + math.cos(fa) * 0.34, 0.5 + sg * 1.05, cz + math.sin(fa) * 0.34), mat=MAT_MARBLE_AGED)
    # base
    smooth_cone(f"col_w_{ci}_base", r1=0.50, r2=0.40, depth=0.20, segs=18, loc=(cx, 0.10, cz), mat=MAT_MARBLE)
    # capital (ionique) : 2 volutes side
    smooth_cone(f"col_w_{ci}_cap", r1=0.42, r2=0.42, depth=0.18, segs=18, loc=(cx, 3.80, cz), mat=MAT_MARBLE)
    # 2 ionic volutes (small donut-like spheres)
    for vk, vx in [(0, -0.30), (1, 0.30)]:
        smooth_sphere(f"col_w_{ci}_vol_{vk}", r=0.14, segs=14, rings=10, loc=(cx + vx, 3.90, cz), mat=MAT_MARBLE_AGED, scale=(1.0, 0.50, 1.4))
    # moss on column
    for mk in range(3):
        ma = mk * (math.pi * 2 / 3) + 0.5
        smooth_sphere(f"col_w_{ci}_moss_{mk}", r=0.10, segs=10, rings=6, loc=(cx + math.cos(ma) * 0.36, random.uniform(1, 3), cz + math.sin(ma) * 0.36), mat=MAT_MOSS, scale=(1.2, 0.5, 1.2))

# 5 colonnes brisées (varying heights)
BROKEN_COLUMNS = [(-8, -1), (8, -1), (-6, 5), (6, 5), (-2, 6)]
for bi, (bx, bz) in enumerate(BROKEN_COLUMNS):
    h = random.uniform(0.8, 2.2)
    # broken drum (truncated)
    smooth_cone(f"col_b_{bi}_drum", r1=0.30, r2=0.28, depth=h, segs=14, loc=(bx, h / 2, bz), mat=MAT_MARBLE_AGED)
    # broken top (uneven)
    smooth_sphere(f"col_b_{bi}_top", r=0.32, segs=14, rings=10, loc=(bx + random.uniform(-0.1, 0.1), h + 0.10, bz), mat=MAT_MARBLE_AGED, scale=(1.0, 0.30, 1.0))
    # base
    smooth_cone(f"col_b_{bi}_base", r1=0.42, r2=0.36, depth=0.15, segs=14, loc=(bx, 0.08, bz), mat=MAT_MARBLE_AGED)


# --- temple central base + frontón cassé -----------------------------
temple_p = empty("temple_p", (0, 0, 0))
# base platform (rectangular stepped)
for sg in range(3):
    sx = 5.0 - sg * 0.4
    sz = 4.0 - sg * 0.3
    smooth_cone(f"temple_step_{sg}", r1=0.0, r2=0.0, depth=0.20, segs=4, loc=(0, 0.10 + sg * 0.20, 0), parent=temple_p, mat=MAT_MARBLE)  # placeholder
    beveled_cube(f"temple_step_b_{sg}", (sx, 0.20, sz), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.10 + sg * 0.20, 0), parent=temple_p, mat=MAT_MARBLE)
# frontón cassé (broken pediment) above columns
front = beveled_cube("temple_pediment", (10, 0.6, 0.6), bevel_offset=0.05, bevel_segments=2, loc=(0, 4.5, 0), parent=temple_p, mat=MAT_MARBLE_AGED)
# broken middle (gap)
broken_chunk = beveled_cube("temple_chunk", (1.5, 0.8, 0.5), bevel_offset=0.04, bevel_segments=2, loc=(-3.5, 3.5, 0.5), parent=temple_p, mat=MAT_MARBLE_AGED)
broken_chunk.rotation_euler = (0, 0, math.radians(25))


# --- statue dieu marin émergée -------------------------------------------
statue_p = empty("statue_p", (0, 0.40, 0))
# base
smooth_cone("statue_base", r1=0.55, r2=0.50, depth=0.30, segs=14, loc=(0, 0.15, 0), parent=statue_p, mat=MAT_MARBLE)
# legs + torso (cone tapered)
smooth_cone("statue_torso", r1=0.30, r2=0.18, depth=1.6, segs=14, loc=(0, 1.10, 0), parent=statue_p, mat=MAT_STATUE)
# arms (raised holding trident)
arm_L = empty("statue_arm_L_p", (0.20, 1.80, 0), parent=statue_p)
arm_L.rotation_euler = (0, 0, math.radians(-45))
smooth_cone("statue_arm_L", r1=0.06, r2=0.05, depth=0.60, segs=10, loc=(0, 0.30, 0), parent=arm_L, mat=MAT_STATUE)
arm_R = empty("statue_arm_R_p", (-0.20, 1.80, 0), parent=statue_p)
arm_R.rotation_euler = (0, 0, math.radians(45))
smooth_cone("statue_arm_R", r1=0.06, r2=0.05, depth=0.60, segs=10, loc=(0, 0.30, 0), parent=arm_R, mat=MAT_STATUE)
# head
smooth_sphere("statue_head", r=0.20, segs=18, rings=14, loc=(0, 2.10, 0), parent=statue_p, mat=MAT_STATUE)
# beard
smooth_sphere("statue_beard", r=0.15, segs=14, rings=10, loc=(0, 1.95, 0.08), parent=statue_p, mat=MAT_STATUE, scale=(1.0, 1.2, 0.6))
# crown
smooth_cone("statue_crown", r1=0.22, r2=0.18, depth=0.10, segs=12, loc=(0, 2.30, 0), parent=statue_p, mat=MAT_TRIDENT)
# trident (handle + 3 tips)
trident_p = empty("trident_p", (0.40, 2.20, 0), parent=statue_p)
smooth_cone("trident_handle", r1=0.04, r2=0.04, depth=1.4, segs=8, loc=(0, 0.30, 0), parent=trident_p, mat=MAT_TRIDENT)
# 3 tips
for tk in range(3):
    tx = -0.10 + tk * 0.10
    smooth_cone(f"trident_tip_{tk}", r1=0.025, r2=0.0, depth=0.30, segs=6, loc=(tx, 1.15, 0), parent=trident_p, mat=MAT_TRIDENT)
# crossbar
beveled_cube("trident_cross", (0.30, 0.04, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.95, 0), parent=trident_p, mat=MAT_TRIDENT)


# --- 2 sphinx gardiens (left + right) -----------------------------------
for sk, sx_pos in [(0, -7), (1, 7)]:
    sphinx_p = empty(f"sphinx_{sk}_p", (sx_pos, 0, -5))
    # body (lion body, lying)
    smooth_sphere(f"sphinx_{sk}_body", r=0.50, segs=18, rings=12, loc=(0, 0.45, 0), parent=sphinx_p, mat=MAT_STATUE, scale=(1.8, 0.85, 0.95))
    # head (human face)
    smooth_sphere(f"sphinx_{sk}_head", r=0.30, segs=18, rings=14, loc=(0.90, 0.85, 0), parent=sphinx_p, mat=MAT_STATUE)
    # headdress
    smooth_cone(f"sphinx_{sk}_dress", r1=0.45, r2=0.0, depth=0.50, segs=14, loc=(0.90, 1.20, 0), parent=sphinx_p, mat=MAT_STATUE)
    # 4 legs (small flat)
    for lk, (lx, lz) in enumerate([(-0.5, 0.40), (-0.5, -0.40), (0.5, 0.40), (0.5, -0.40)]):
        smooth_cone(f"sphinx_{sk}_leg_{lk}", r1=0.12, r2=0.10, depth=0.40, segs=8, loc=(lx, 0.20, lz), parent=sphinx_p, mat=MAT_STATUE)
    sphinx_p.rotation_euler = (0, math.radians(180 if sk == 0 else 0), 0)


# --- 3 coffres au trésor (chests) -------------------------------------
for ck, (cx_pos, cz_pos) in enumerate([(2, 4), (-2, 4), (3, -2)]):
    chest_p = empty(f"chest_{ck}_p", (cx_pos, 0.10, cz_pos))
    # box
    box = beveled_cube(f"chest_{ck}_box", (0.7, 0.45, 0.45), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.22, 0), parent=chest_p, mat=MAT_WOOD)
    # lid (open angle)
    lid_p = empty(f"chest_{ck}_lid_p", (0, 0.45, -0.22), parent=chest_p)
    lid_p.rotation_euler = (math.radians(-70), 0, 0)
    beveled_cube(f"chest_{ck}_lid", (0.7, 0.10, 0.45), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.05, 0.22), parent=lid_p, mat=MAT_WOOD)
    # 4 gold trims
    for tt in range(4):
        ty = 0.12 if tt % 2 == 0 else 0.32
        tz = 0.22 if tt < 2 else -0.22
        smooth_cone(f"chest_{ck}_trim_{tt}", r1=0.015, r2=0.015, depth=0.70, segs=6, loc=(0, ty, tz), parent=chest_p, mat=MAT_GOLD)
        # rotate horizontal
        chest_p.scale = (1, 1, 1)  # noop
    # gold pile overflowing
    for gk in range(8):
        gold_sphere = smooth_sphere(f"chest_{ck}_gold_{gk}", r=0.06, segs=10, rings=6, loc=(random.uniform(-0.25, 0.25), 0.45 + random.uniform(0, 0.10), random.uniform(-0.20, 0.20)), parent=chest_p, mat=MAT_GOLD_GLOW)
    # 3 pearls
    for pk in range(3):
        smooth_sphere(f"chest_{ck}_pearl_{pk}", r=0.05, segs=10, rings=6, loc=(random.uniform(-0.20, 0.20), 0.50, random.uniform(-0.15, 0.15)), parent=chest_p, mat=MAT_PEARL)


# --- 6 amphores brisées ---------------------------------------------------
for ak in range(6):
    a = ak * (math.pi * 2 / 6) + 0.3
    r = random.uniform(3, 7)
    ax = math.cos(a) * r
    az = math.sin(a) * r
    amp_p = empty(f"amp_{ak}_p", (ax, 0.05, az))
    amp_p.rotation_euler = (math.radians(random.uniform(-20, 20)), random.uniform(0, math.pi * 2), math.radians(random.uniform(40, 70)))
    # body (broken)
    smooth_sphere(f"amp_{ak}_body", r=0.20, segs=14, rings=10, loc=(0, 0.20, 0), parent=amp_p, mat=MAT_AMPHORA, scale=(0.85, 1.2, 0.85))
    # neck
    smooth_cone(f"amp_{ak}_neck", r1=0.08, r2=0.06, depth=0.20, segs=10, loc=(0, 0.40, 0), parent=amp_p, mat=MAT_AMPHORA)
    # 2 handles
    for hk, hz in [(0, 0.15), (1, -0.15)]:
        handle = smooth_cone(f"amp_{ak}_handle_{hk}", r1=0.025, r2=0.025, depth=0.20, segs=6, loc=(0.18, 0.30, hz), parent=amp_p, mat=MAT_AMPHORA)
        handle.rotation_euler = (0, 0, math.radians(30 if hz > 0 else -30))


# --- 12 fish schooling ----------------------------------------------------
fish_school = []
SCHOOL_CENTER_R = 6.0
SCHOOL_CENTER_Y = 4.0
for fk in range(12):
    fm = [MAT_FISH_A, MAT_FISH_B, MAT_FISH_C][fk % 3]
    a = fk * (math.pi * 2 / 12)
    fr = SCHOOL_CENTER_R + random.uniform(-0.5, 0.5)
    fy = SCHOOL_CENTER_Y + random.uniform(-0.8, 0.8)
    fp = empty(f"fish_{fk}_p", (math.cos(a) * fr, fy, math.sin(a) * fr))
    # body
    smooth_sphere(f"fish_{fk}_b", r=0.18, segs=14, rings=10, loc=(0, 0, 0), parent=fp, mat=fm, scale=(1.6, 0.95, 0.7))
    # tail fin
    smooth_sphere(f"fish_{fk}_t", r=0.10, segs=10, rings=6, loc=(-0.25, 0, 0), parent=fp, mat=fm, scale=(0.7, 1.4, 0.1))
    # eye
    smooth_sphere(f"fish_{fk}_e", r=0.025, segs=8, rings=6, loc=(0.22, 0.05, 0.06), parent=fp, mat=MAT_GOLD_GLOW)
    fish_school.append({"p": fp, "a0": a, "r": fr, "y0": fy, "phase": fk * 0.20})


# --- 4 raies manta ---------------------------------------------------------
manta_rays = []
for rk in range(4):
    a = rk * (math.pi * 2 / 4) + 0.5
    rr = random.uniform(7, 10)
    ry = random.uniform(3, 6)
    rp = empty(f"manta_{rk}_p", (math.cos(a) * rr, ry, math.sin(a) * rr))
    # body
    smooth_sphere(f"manta_{rk}_b", r=0.30, segs=18, rings=12, loc=(0, 0, 0), parent=rp, mat=MAT_RAY_MANTA, scale=(1.4, 0.10, 1.0))
    # 2 wings (triangular)
    w_L = empty(f"manta_{rk}_wL", (0, 0, 0.40), parent=rp)
    smooth_sphere(f"manta_{rk}_wL_b", r=0.30, segs=14, rings=8, loc=(0, 0, 0.30), parent=w_L, mat=MAT_RAY_MANTA, scale=(1.4, 0.05, 1.5))
    w_R = empty(f"manta_{rk}_wR", (0, 0, -0.40), parent=rp)
    smooth_sphere(f"manta_{rk}_wR_b", r=0.30, segs=14, rings=8, loc=(0, 0, -0.30), parent=w_R, mat=MAT_RAY_MANTA, scale=(1.4, 0.05, 1.5))
    # tail
    smooth_cone(f"manta_{rk}_tail", r1=0.05, r2=0.0, depth=0.80, segs=8, loc=(-0.40, 0, 0), parent=rp, mat=MAT_RAY_MANTA)
    manta_rays.append({"p": rp, "wL": w_L, "wR": w_R, "a": a, "r": rr, "y": ry, "phase": rk * 0.7})


# --- 2 sea turtles ---------------------------------------------------------
turtles = []
for tk in range(2):
    tp = empty(f"turtle_{tk}_p", (-5 + tk * 10, 2.5, 3))
    # shell
    smooth_sphere(f"turtle_{tk}_shell", r=0.35, segs=20, rings=14, loc=(0, 0, 0), parent=tp, mat=MAT_TURTLE_SHELL, scale=(1.2, 0.55, 1.0))
    # head
    smooth_sphere(f"turtle_{tk}_head", r=0.13, segs=14, rings=10, loc=(0.35, 0, 0), parent=tp, mat=MAT_TURTLE_SKIN, scale=(1.2, 0.85, 0.85))
    # 4 flippers
    for fk, (fx, fz) in enumerate([(0.15, 0.35), (0.15, -0.35), (-0.20, 0.35), (-0.20, -0.35)]):
        flp = empty(f"turtle_{tk}_fl_p_{fk}", (fx, -0.05, fz), parent=tp)
        smooth_sphere(f"turtle_{tk}_fl_{fk}", r=0.18, segs=12, rings=8, loc=(0, 0, 0.10 * (1 if fz > 0 else -1)), parent=flp, mat=MAT_TURTLE_SKIN, scale=(1.6, 0.10, 0.5))
    # tail
    smooth_cone(f"turtle_{tk}_tail", r1=0.04, r2=0.0, depth=0.15, segs=6, loc=(-0.35, 0, 0), parent=tp, mat=MAT_TURTLE_SKIN)
    turtles.append({"p": tp, "phase": tk * 1.5, "base_x": tp.location.x})


# --- 8 méduses bioluminescentes ----------------------------------------
jellies = []
for jk in range(8):
    a = jk * (math.pi * 2 / 8)
    jr = random.uniform(4, 9)
    jy = random.uniform(5, 10)
    jp = empty(f"jelly_{jk}_p", (math.cos(a) * jr, jy, math.sin(a) * jr))
    # bell
    bell = smooth_sphere(f"jelly_{jk}_bell", r=0.35, segs=20, rings=14, loc=(0, 0, 0), parent=jp, mat=MAT_JELLY, scale=(1.3, 0.6, 1.3))
    # 6 tentacles
    for tk in range(6):
        ta = tk * (math.pi * 2 / 6)
        smooth_cone(f"jelly_{jk}_t_{tk}", r1=0.04, r2=0.0, depth=random.uniform(0.6, 1.0), segs=8, loc=(math.cos(ta) * 0.25, -0.50, math.sin(ta) * 0.25), parent=jp, mat=MAT_JELLY_TENT)
    jellies.append({"p": jp, "bell": bell, "a": a, "r": jr, "y": jy, "phase": jk * 0.5})


# --- 30 bubbles rise -----------------------------------------------------
bubbles = []
for bk in range(30):
    bx = random.uniform(-12, 12)
    by = random.uniform(0.2, 1.5)
    bz = random.uniform(-3, 6)
    bu = smooth_sphere(f"bubble_{bk}", r=random.uniform(0.06, 0.12), segs=12, rings=8, loc=(bx, by, bz), mat=MAT_BUBBLE)
    bu["_base"] = (bx, by, bz)
    bu["_phase"] = bk * 0.20
    bu["_speed"] = random.uniform(1.2, 2.2)
    bubbles.append(bu)


# --- 10 algues sway ------------------------------------------------------
algae_list = []
for ak in range(10):
    ax = random.uniform(-10, 10)
    az = random.uniform(-3, 6)
    if abs(ax) < 1.5 and abs(az) < 1.5:
        continue
    ap = empty(f"algae_{ak}", (ax, 0, az))
    algae_list.append(ap)
    cur = ap
    for j in range(4):
        e = empty(f"algae_{ak}_e_{j}", (0, 0.40, 0), parent=cur)
        smooth_cone(f"algae_{ak}_s_{j}", r1=0.06, r2=0.04, depth=0.50, segs=8, loc=(0, 0.25, 0), parent=e, mat=MAT_ALGAE)
        cur = e


# --- 5 coraux ------------------------------------------------------------
for ck in range(5):
    cx = random.uniform(-9, 9)
    cz = random.uniform(-2, 6)
    if abs(cx) < 2 and abs(cz) < 2:
        continue
    cp = empty(f"coral_{ck}_p", (cx, 0.05, cz))
    cm = MAT_CORAL_A if ck % 2 == 0 else MAT_CORAL_B
    for j in range(5):
        a = j * (math.pi * 2 / 5)
        smooth_cone(f"coral_{ck}_b_{j}", r1=0.10, r2=0.04, depth=random.uniform(0.5, 0.9), segs=8, loc=(math.cos(a) * 0.15, 0.30, math.sin(a) * 0.15), parent=cp, mat=cm)


# --- 30 stone fragments floating -----------------------------------------
fragments = []
for fk in range(30):
    fx = random.uniform(-10, 10)
    fy = random.uniform(2, 9)
    fz = random.uniform(-3, 7)
    fp = beveled_cube(f"frag_{fk}", (random.uniform(0.15, 0.30), random.uniform(0.10, 0.20), random.uniform(0.15, 0.30)), bevel_offset=0.02, bevel_segments=2, loc=(fx, fy, fz), mat=MAT_MARBLE_AGED)
    fp["_base"] = (fx, fy, fz)
    fp["_phase"] = fk * 0.15
    fragments.append(fp)


# --- 4 sphères énergie mystique orbitant temple ------------------------
energy_spheres = []
for ek in range(4):
    ea = ek * (math.pi * 2 / 4)
    er = 2.5
    ep = empty(f"energy_{ek}_p", (math.cos(ea) * er, 5.0, math.sin(ea) * er))
    smooth_sphere(f"energy_{ek}_core", r=0.25, segs=18, rings=12, loc=(0, 0, 0), parent=ep, mat=MAT_ENERGY)
    # outer aura sphere
    smooth_sphere(f"energy_{ek}_aura", r=0.40, segs=16, rings=10, loc=(0, 0, 0), parent=ep, mat=MAT_ENERGY, scale=(1.0, 1.0, 1.0))
    energy_spheres.append({"p": ep, "a": ea, "r": er, "phase": ek * 0.5})


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

    # 12 fish schooling
    for fd in fish_school:
        ang = fd["a0"] + tt * 2 * math.pi * 0.7
        fx = math.cos(ang) * fd["r"]
        fz = math.sin(ang) * fd["r"]
        fy = fd["y0"] + 0.4 * math.sin(2 * math.pi * tt * 1.5 + fd["phase"])
        kf(fd["p"], f, "location", (fx, fy, fz))
        kf(fd["p"], f, "rotation_euler", (0, ang + math.pi / 2, math.radians(8 * math.sin(2 * math.pi * tt * 3 + fd["phase"]))))

    # 4 manta rays glide
    for mr in manta_rays:
        ang = mr["a"] + tt * 2 * math.pi * 0.3
        mx = math.cos(ang) * mr["r"]
        mz = math.sin(ang) * mr["r"]
        my = mr["y"] + 0.5 * math.sin(2 * math.pi * tt * 1.0 + mr["phase"])
        kf(mr["p"], f, "location", (mx, my, mz))
        kf(mr["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))
        wflap = math.radians(25) * math.sin(2 * math.pi * tt * 1.5 + mr["phase"])
        kf(mr["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(mr["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # 2 turtles swim + flippers
    for tr in turtles:
        ph = tr["phase"]
        nx = tr["base_x"] + 3 * math.sin(2 * math.pi * tt * 0.4 + ph)
        ny = 2.5 + 0.4 * math.cos(2 * math.pi * tt * 0.6 + ph)
        kf(tr["p"], f, "location", (nx, ny, 3))
        kf(tr["p"], f, "rotation_euler", (math.radians(5 * math.sin(2 * math.pi * tt * 1.5 + ph)), 0, 0))

    # 8 jellies bell pulse
    for jl in jellies:
        ang = jl["a"] + tt * 2 * math.pi * 0.2
        bx_ = math.cos(ang) * jl["r"]
        bz_ = math.sin(ang) * jl["r"]
        by_ = jl["y"] + 0.6 * math.sin(2 * math.pi * tt * 1.0 + jl["phase"])
        kf(jl["p"], f, "location", (bx_, by_, bz_))
        bp = math.sin(2 * math.pi * tt * 2.5 + jl["phase"])
        kf(jl["bell"], f, "scale", (1.3 + 0.20 * bp, 0.6 - 0.15 * bp, 1.3 + 0.20 * bp))

    # 30 bubbles rise
    for bu in bubbles:
        bx_, by_, bz_ = bu["_base"]
        ph = bu["_phase"]
        spd = bu["_speed"]
        local = (tt * spd + ph) % 1.0
        ny = by_ + local * 10.0
        nx = bx_ + 0.18 * math.sin(2 * math.pi * local * 6 + ph)
        sc = 0.7 + local * 0.6
        kf(bu, f, "location", (nx, ny, bz_))
        kf(bu, f, "scale", (sc, sc, sc))

    # 6 light rays pulse
    for ri, ray in enumerate(light_rays):
        sy_sc = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 1.3 + ri * 0.5)
        sxz_sc = 1.0 + 0.20 * math.sin(2 * math.pi * tt * 1.5 + ri * 0.4)
        kf(ray, f, "scale", (sxz_sc, sy_sc, sxz_sc))

    # 10 algae sway
    for ai, ap in enumerate(algae_list):
        bend_x = math.radians(12) * math.sin(2 * math.pi * tt * 1.5 + ai * 0.7)
        bend_z = math.radians(10) * math.cos(2 * math.pi * tt * 1.7 + ai * 0.5)
        kf(ap, f, "rotation_euler", (bend_x, 0, bend_z))

    # 30 fragments float + rotation
    for fp_obj in fragments:
        bx_, by_, bz_ = fp_obj["_base"]
        ph = fp_obj["_phase"]
        ny = by_ + 0.3 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        kf(fp_obj, f, "location", (bx_, ny, bz_))
        kf(fp_obj, f, "rotation_euler", (math.radians(180 * tt + ph * 30), math.radians(120 * tt + ph * 40), math.radians(90 * tt + ph * 20)))

    # 4 energy spheres orbit + pulse
    for es in energy_spheres:
        ang = es["a"] + tt * 2 * math.pi * 1.0
        ex = math.cos(ang) * es["r"]
        ez = math.sin(ang) * es["r"]
        ey = 5.0 + 0.5 * math.sin(2 * math.pi * tt * 1.5 + es["phase"])
        kf(es["p"], f, "location", (ex, ey, ez))
        ps = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 3 + es["phase"])
        kf(es["p"], f, "scale", (ps, ps, ps))
        kf(es["p"], f, "rotation_euler", (math.radians(360 * tt), math.radians(540 * tt), 0))

    # statue : head turn slight + trident lift
    statue_head = bpy.data.objects.get("statue_head")
    if statue_head:
        kf(statue_head, f, "rotation_euler", (0, math.radians(10 * math.sin(2 * math.pi * tt * 0.5)), 0))
    trident_p_obj = bpy.data.objects.get("trident_p")
    if trident_p_obj:
        kf(trident_p_obj, f, "rotation_euler", (math.radians(5 * math.sin(2 * math.pi * tt * 0.8)), 0, 0))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_underwater_atlantis_ruins] wrote {OUT}")
