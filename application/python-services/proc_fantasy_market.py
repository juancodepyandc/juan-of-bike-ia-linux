"""
proc_fantasy_market.py — 132e procédural AuroraIA, Phase F++++.

Marché médiéval fantasy place centrale : 6 stands marchands en bois
(forge / herboriste / poissonnier / boulanger / armurier / mage)
+ produits exposés + cheminée forge fumante + 4 bannières flottantes
+ 6 lanternes + 12 personnages clients silhouettes + cathédrale arrière-
plan + pierres pavées + 3 chiens errants + 2 chevaux attachés
+ 3 tonneaux + 4 cageots + 5 oiseaux + arbre central avec feuilles.

Animation :
- 4 bannières flottent
- forge fumée monte
- 12 personnages bougent (drift)
- 5 oiseaux orbites
- 3 chiens trottinent
- 6 lanternes pulse
- forge flame émissive pulse
- arbre feuilles sway

Sortie : output/3d/pbr_fantasymarket_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_fantasymarket_proc.glb"))

random.seed(0xFA17A5)

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


def cube(name, size=1.0, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


def sphere(name, r=1.0, segs=24, rings=12, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


def cone(name, r1=1.0, r2=0.0, depth=1.0, segs=24, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


# --- materials --------------------------------------------------------------
MAT_SKY = make_mat("sky", (0.65, 0.78, 0.88), roughness=1.0,
                    emi=(0.55, 0.70, 0.82), emi_strength=0.5)
MAT_CATHEDRAL = make_mat("cathedral", (0.40, 0.35, 0.30), roughness=0.85)
MAT_CATHEDRAL_ROOF = make_mat("cathedral_roof", (0.25, 0.20, 0.18), roughness=0.7)
MAT_CATHEDRAL_WIN = make_mat("cathedral_win", (1.0, 0.85, 0.55), roughness=0.0, alpha=0.85,
                                emi=(1.0, 0.85, 0.55), emi_strength=4.0)
MAT_GROUND_STONE = make_mat("ground_stone", (0.45, 0.40, 0.35), roughness=0.9)
MAT_STONE_DARK = make_mat("stone_dark", (0.30, 0.27, 0.25), roughness=0.9)
MAT_WOOD = make_mat("wood", (0.45, 0.28, 0.15), roughness=0.7)
MAT_WOOD_DARK = make_mat("wood_dark", (0.25, 0.15, 0.08), roughness=0.8)
MAT_STAND_RED = make_mat("stand_red", (0.65, 0.15, 0.10), roughness=0.6)
MAT_STAND_BLUE = make_mat("stand_blue", (0.10, 0.30, 0.55), roughness=0.6)
MAT_STAND_GREEN = make_mat("stand_green", (0.15, 0.45, 0.20), roughness=0.6)
MAT_STAND_YELLOW = make_mat("stand_yellow", (0.80, 0.65, 0.20), roughness=0.6)
MAT_STAND_PURPLE = make_mat("stand_purple", (0.45, 0.20, 0.55), roughness=0.6)
MAT_STAND_ORANGE = make_mat("stand_orange", (0.85, 0.45, 0.15), roughness=0.6)
MAT_FORGE_BRICK = make_mat("forge_brick", (0.40, 0.22, 0.18), roughness=0.85)
MAT_FORGE_FIRE = make_mat("forge_fire", (1.0, 0.45, 0.10), roughness=0.0, alpha=0.85,
                            emi=(1.0, 0.45, 0.10), emi_strength=8.0)
MAT_FORGE_ANVIL = make_mat("forge_anvil", (0.20, 0.18, 0.16), metallic=0.8, roughness=0.4)
MAT_BREAD = make_mat("bread", (0.75, 0.55, 0.30), roughness=0.8,
                      emi=(0.25, 0.15, 0.05), emi_strength=0.2)
MAT_HERB = make_mat("herb", (0.20, 0.55, 0.25), roughness=0.85,
                     emi=(0.05, 0.20, 0.08), emi_strength=0.3)
MAT_FISH = make_mat("fish", (0.65, 0.65, 0.75), metallic=0.4, roughness=0.4,
                      emi=(0.30, 0.30, 0.35), emi_strength=0.3)
MAT_ARMOR = make_mat("armor", (0.55, 0.55, 0.60), metallic=0.85, roughness=0.3,
                       emi=(0.15, 0.15, 0.18), emi_strength=0.3)
MAT_MAGE_BOOK = make_mat("mage_book", (0.55, 0.10, 0.40), roughness=0.5,
                           emi=(0.45, 0.05, 0.30), emi_strength=0.6)
MAT_MAGE_CRYSTAL = make_mat("mage_crystal", (0.55, 0.30, 1.0), roughness=0.0,
                              emi=(0.55, 0.30, 1.0), emi_strength=5.0)
MAT_SMOKE = make_mat(
    "smoke", (0.45, 0.42, 0.38), roughness=1.0, alpha=0.65,
    emi=(0.30, 0.28, 0.25), emi_strength=0.4,
)
MAT_BANNER_R = make_mat("banner_r", (0.85, 0.10, 0.20), roughness=0.6,
                          emi=(0.30, 0.05, 0.08), emi_strength=0.4)
MAT_BANNER_B = make_mat("banner_b", (0.20, 0.30, 0.85), roughness=0.6,
                          emi=(0.05, 0.10, 0.40), emi_strength=0.4)
MAT_BANNER_G = make_mat("banner_g", (0.15, 0.65, 0.30), roughness=0.6,
                          emi=(0.05, 0.30, 0.10), emi_strength=0.4)
MAT_BANNER_Y = make_mat("banner_y", (0.90, 0.75, 0.20), roughness=0.6,
                          emi=(0.40, 0.30, 0.05), emi_strength=0.4)
MAT_LANTERN_LIGHT = make_mat("lantern_light", (1.0, 0.75, 0.30), roughness=0.0, alpha=0.85,
                               emi=(1.0, 0.75, 0.30), emi_strength=6.5)
MAT_LANTERN_CASE = make_mat("lantern_case", (0.25, 0.18, 0.10), roughness=0.7)
MAT_TREE_TRUNK = make_mat("tree_trunk", (0.30, 0.20, 0.12), roughness=0.9)
MAT_TREE_LEAVES = make_mat("tree_leaves", (0.20, 0.55, 0.25), roughness=0.85,
                             emi=(0.08, 0.25, 0.10), emi_strength=0.3)
MAT_DOG = make_mat("dog", (0.45, 0.30, 0.20), roughness=0.7)
MAT_HORSE_BROWN = make_mat("horse_brown", (0.55, 0.30, 0.15), roughness=0.7)
MAT_HORSE_MANE = make_mat("horse_mane", (0.20, 0.15, 0.10), roughness=0.85)
MAT_BIRD = make_mat("bird", (0.25, 0.20, 0.18), roughness=0.7)
MAT_BARREL = make_mat("barrel", (0.45, 0.28, 0.15), roughness=0.7)
MAT_CRATE = make_mat("crate", (0.55, 0.40, 0.20), roughness=0.7)
MAT_BARREL_METAL = make_mat("barrel_metal", (0.40, 0.40, 0.45), metallic=0.7, roughness=0.4)
MAT_PERSON_BODY = make_mat("person_body", (0.30, 0.20, 0.15), roughness=0.7)
person_coat_colors = [
    make_mat("coat_r1", (0.55, 0.15, 0.10), roughness=0.7),
    make_mat("coat_g1", (0.15, 0.45, 0.20), roughness=0.7),
    make_mat("coat_b1", (0.15, 0.25, 0.55), roughness=0.7),
    make_mat("coat_y1", (0.65, 0.55, 0.20), roughness=0.7),
    make_mat("coat_p1", (0.40, 0.15, 0.45), roughness=0.7),
    make_mat("coat_o1", (0.65, 0.40, 0.15), roughness=0.7),
]
MAT_PERSON_HEAD = make_mat("person_head", (0.95, 0.75, 0.55), roughness=0.7)

# --- backdrop : sky --------------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 18, 6), mat=MAT_SKY)
sky.scale = (40, 0.1, 14)

# --- cathedral in background ----------------------------------------------
cath_p = empty("cathedral", (0, 0, 11))
# main body
body = cube("cath_body", size=1.0, loc=(0, 3.0, 0), parent=cath_p, mat=MAT_CATHEDRAL)
body.scale = (5.0, 3.0, 2.0)
# roof
roof = cone("cath_roof", r1=3.0, r2=0.3, depth=2.5, segs=4, loc=(0, 7.0, 0), parent=cath_p, mat=MAT_CATHEDRAL_ROOF)
roof.rotation_euler = (math.radians(90), 0, math.radians(45))
# 3 stained glass windows
for i in range(3):
    wx = -1.5 + i * 1.5
    w = cube(f"cath_win_{i}", size=1.0, loc=(wx, 3.5, 1.05), parent=cath_p, mat=MAT_CATHEDRAL_WIN)
    w.scale = (0.5, 1.5, 0.05)
# 2 spire towers (left + right)
for side, dx in [("L", -2.8), ("R", 2.8)]:
    tower = cube(f"cath_tower_{side}", size=1.0, loc=(dx, 4.5, 0), parent=cath_p, mat=MAT_CATHEDRAL)
    tower.scale = (1.0, 4.0, 1.0)
    # spire
    spire = cone(f"cath_spire_{side}", r1=0.8, r2=0.0, depth=2.5, segs=4, loc=(dx, 7.5, 0), parent=cath_p, mat=MAT_CATHEDRAL_ROOF)
    spire.rotation_euler = (math.radians(90), 0, math.radians(45))
# main door
door = cube("cath_door", size=1.0, loc=(0, 1.0, 1.05), parent=cath_p, mat=MAT_WOOD_DARK)
door.scale = (0.7, 1.8, 0.05)
# rose window above door
rose = cone("cath_rose", r1=0.45, r2=0.45, depth=0.08, segs=20, loc=(0, 5.5, 1.05), parent=cath_p, mat=MAT_CATHEDRAL_WIN)
rose.rotation_euler = (math.radians(90), 0, 0)

# --- ground stone pavement -----------------------------------------------
ground = cube("ground_stone", size=1.0, loc=(0, -0.05, 0), mat=MAT_GROUND_STONE)
ground.scale = (30, 0.1, 22)

# pavement pattern : 20 darker stones randomly placed
for i in range(20):
    sx = random.uniform(-13, 13)
    sz = random.uniform(-8, 8)
    s = cube(f"stone_{i}", size=1.0, loc=(sx, 0.005, sz), mat=MAT_STONE_DARK)
    s.scale = (random.uniform(0.6, 1.2), 0.02, random.uniform(0.6, 1.2))

# --- 6 stands marchands -----------------------------------------------
def make_stand(name, x, z, color_mat, rot=0):
    p = empty(name, (x, 0, z))
    p.rotation_euler = (0, rot, 0)
    # base table
    table = cube(f"{name}_table", size=1.0, loc=(0, 0.6, 0), parent=p, mat=MAT_WOOD)
    table.scale = (1.6, 0.10, 0.9)
    # 4 legs
    for j, (lx, lz) in enumerate([(0.7, 0.4), (-0.7, 0.4), (0.7, -0.4), (-0.7, -0.4)]):
        leg = cube(f"{name}_leg_{j}", size=1.0, loc=(lx, 0.30, lz), parent=p, mat=MAT_WOOD_DARK)
        leg.scale = (0.06, 0.6, 0.06)
    # awning (sloped roof)
    awning = cube(f"{name}_awning", size=1.0, loc=(0, 1.5, -0.3), parent=p, mat=color_mat)
    awning.scale = (1.8, 0.06, 1.0)
    awning.rotation_euler = (math.radians(-20), 0, 0)
    # 2 awning support poles
    for side, lx in [("L", -0.85), ("R", 0.85)]:
        pole = cone(f"{name}_pole_{side}", r1=0.05, r2=0.05, depth=1.0, segs=6, loc=(lx, 1.1, -0.3), parent=p, mat=MAT_WOOD_DARK)
        pole.rotation_euler = (math.radians(90), 0, 0)
    return p

stands_data = [
    # (name, x, z, color, rot, type)
    ("stand_forge", -7.0, -2.0, MAT_FORGE_BRICK, 0, "forge"),
    ("stand_herb", -3.5, -2.0, MAT_STAND_GREEN, 0, "herb"),
    ("stand_fish", 0, -2.0, MAT_STAND_BLUE, 0, "fish"),
    ("stand_bread", 3.5, -2.0, MAT_STAND_YELLOW, 0, "bread"),
    ("stand_armor", 7.0, -2.0, MAT_STAND_RED, 0, "armor"),
    ("stand_mage", -5.0, 4.0, MAT_STAND_PURPLE, math.pi, "mage"),
]
stand_objects = {}
forge_flame = None
forge_smoke_puffs = []
mage_crystal_obj = None
for sd in stands_data:
    sname, sx, sz, color, rot, kind = sd
    p = make_stand(sname, sx, sz, color, rot)
    stand_objects[kind] = p
    # add products on table based on kind
    if kind == "forge":
        # anvil
        anvil = cube(f"{sname}_anvil", size=1.0, loc=(0, 0.85, 0), parent=p, mat=MAT_FORGE_ANVIL)
        anvil.scale = (0.40, 0.20, 0.20)
        # forge fire (sphere émissive)
        forge_flame = sphere(f"{sname}_flame", r=0.20, segs=12, rings=8, loc=(0.50, 0.85, 0), parent=p, mat=MAT_FORGE_FIRE)
        forge_flame.scale = (1.0, 1.5, 1.0)
        # 6 chimney smoke puffs
        for k in range(6):
            py = 1.5 + k * 0.5
            pr = 0.18 + k * 0.06
            puff = sphere(f"{sname}_smoke_{k}", r=pr, segs=12, rings=8, loc=(0.50, py, 0), parent=p, mat=MAT_SMOKE)
            forge_smoke_puffs.append((puff, k))
        # 3 swords on display
        for j in range(3):
            jz = -0.30 + j * 0.30
            sw = cube(f"{sname}_sword_{j}", size=1.0, loc=(-0.50, 0.75, jz), parent=p, mat=MAT_ARMOR)
            sw.scale = (0.04, 0.04, 0.25)
            sw.rotation_euler = (math.radians(20), 0, 0)
    elif kind == "herb":
        # 6 small herb bundles
        for j in range(6):
            jx = -0.5 + (j % 3) * 0.5
            jz = -0.30 + (j // 3) * 0.30
            herb = sphere(f"{sname}_herb_{j}", r=0.10, segs=8, rings=6, loc=(jx, 0.75, jz), parent=p, mat=MAT_HERB)
            herb.scale = (1.0, 0.7, 1.0)
        # 2 hanging dried herbs from awning
        for j in range(2):
            hx = -0.5 + j * 1.0
            h = cube(f"{sname}_hang_{j}", size=1.0, loc=(hx, 1.2, -0.05), parent=p, mat=MAT_HERB)
            h.scale = (0.04, 0.30, 0.04)
    elif kind == "fish":
        # 5 fish on display
        for j in range(5):
            jx = -0.6 + j * 0.30
            f = cone(f"{sname}_f_{j}", r1=0.12, r2=0.02, depth=0.25, segs=8, loc=(jx, 0.73, 0), parent=p, mat=MAT_FISH)
            f.rotation_euler = (math.radians(90), 0, math.radians(90))
            f.scale = (1.0, 0.4, 1.0)
    elif kind == "bread":
        # 6 round breads
        for j in range(6):
            jx = -0.5 + (j % 3) * 0.5
            jz = -0.25 + (j // 3) * 0.30
            b = sphere(f"{sname}_b_{j}", r=0.10, segs=10, rings=8, loc=(jx, 0.78, jz), parent=p, mat=MAT_BREAD)
            b.scale = (1.0, 0.6, 1.0)
        # baguettes
        for j in range(3):
            jx = -0.4 + j * 0.4
            bag = cone(f"{sname}_bag_{j}", r1=0.06, r2=0.05, depth=0.5, segs=8, loc=(jx, 0.70, 0.3), parent=p, mat=MAT_BREAD)
            bag.rotation_euler = (0, math.radians(90), 0)
    elif kind == "armor":
        # 2 helmets + 2 swords + 1 shield
        for j in range(2):
            jx = -0.4 + j * 0.8
            helm = sphere(f"{sname}_helm_{j}", r=0.14, segs=12, rings=8, loc=(jx, 0.82, 0), parent=p, mat=MAT_ARMOR)
            helm.scale = (1.0, 1.0, 0.9)
        # 2 swords vertical
        for j in range(2):
            jz = -0.20 + j * 0.40
            sw = cube(f"{sname}_sw_{j}", size=1.0, loc=(0, 1.0, jz), parent=p, mat=MAT_ARMOR)
            sw.scale = (0.03, 0.45, 0.03)
        # 1 shield
        shield = cone(f"{sname}_shield", r1=0.25, r2=0.25, depth=0.06, segs=12, loc=(0.5, 0.85, 0.2), parent=p, mat=MAT_ARMOR)
        shield.rotation_euler = (math.radians(90), 0, 0)
    elif kind == "mage":
        # purple book on table
        book = cube(f"{sname}_book", size=1.0, loc=(-0.4, 0.73, 0), parent=p, mat=MAT_MAGE_BOOK)
        book.scale = (0.25, 0.05, 0.20)
        # crystal ball (glowing purple)
        mage_crystal_obj = sphere(f"{sname}_crystal", r=0.18, segs=14, rings=10, loc=(0.3, 0.82, 0), parent=p, mat=MAT_MAGE_CRYSTAL)
        # 3 small potion bottles
        for j in range(3):
            jx = -0.4 + j * 0.30
            jz = 0.25
            pot = cone(f"{sname}_pot_{j}", r1=0.06, r2=0.04, depth=0.20, segs=8, loc=(jx, 0.77, jz), parent=p, mat=MAT_MAGE_CRYSTAL)
            pot.rotation_euler = (math.radians(90), 0, 0)

# --- 4 bannières flottantes au dessus des stands -------------------------
banner_data = [
    (-9.0, 3.0, -3.0, MAT_BANNER_R),
    (-2.0, 3.0, -3.0, MAT_BANNER_G),
    (5.0, 3.0, -3.0, MAT_BANNER_Y),
    (-5.0, 3.0, 6.0, MAT_BANNER_B),
]
banner_objs = []
for i, (bx, by, bz, bmat) in enumerate(banner_data):
    bp = empty(f"banner_{i}", (bx, by, bz))
    # pole
    pole = cone(f"banner_{i}_pole", r1=0.06, r2=0.05, depth=1.5, segs=6, loc=(0, -0.75, 0), parent=bp, mat=MAT_WOOD_DARK)
    pole.rotation_euler = (math.radians(90), 0, 0)
    # 6 banner segments waving
    segs_list = []
    for j in range(6):
        seg = cube(f"banner_{i}_{j}", size=1.0, loc=(0.04 + j * 0.10, 0, 0), parent=bp, mat=bmat)
        seg.scale = (0.10, 0.5, 0.02)
        segs_list.append(seg)
    banner_objs.append((segs_list, i))

# --- 6 lanternes éparpillées ----------------------------------------------
lantern_lights = []
for i, (lx, lz) in enumerate([(-9, 0), (-3, 0), (3, 0), (9, 0), (-6, 5), (5, 5)]):
    lp = empty(f"lantern_{i}", (lx, 2.5, lz))
    # pole
    pole = cone(f"lantern_{i}_pole", r1=0.06, r2=0.04, depth=2.5, segs=6, loc=(0, -1.25, 0), parent=lp, mat=MAT_WOOD_DARK)
    pole.rotation_euler = (math.radians(90), 0, 0)
    # case
    case = cube(f"lantern_{i}_case", size=1.0, loc=(0, 0, 0), parent=lp, mat=MAT_LANTERN_CASE)
    case.scale = (0.18, 0.20, 0.18)
    # light
    light = sphere(f"lantern_{i}_light", r=0.12, segs=12, rings=8, loc=(0, 0, 0), parent=lp, mat=MAT_LANTERN_LIGHT)
    # cap
    cap = cone(f"lantern_{i}_cap", r1=0.20, r2=0.0, depth=0.10, segs=6, loc=(0, 0.18, 0), parent=lp, mat=MAT_LANTERN_CASE)
    cap.rotation_euler = (math.radians(90), 0, 0)
    lantern_lights.append(light)

# --- 12 personnages silhouettes -------------------------------------------
people = []
person_positions = [
    (-8, -0.5), (-6, 0.5), (-4, 1.0), (-2, -0.5), (0, 0.5), (2, 1.0),
    (4, -0.5), (6, 0.5), (8, -0.5), (-3, 6.0), (3, 6.0), (-9, 5.0),
]
for i, (px, pz) in enumerate(person_positions):
    pp = empty(f"person_{i}", (px, 0, pz))
    # body
    body = cube(f"person_{i}_body", size=1.0, loc=(0, 0.55, 0), parent=pp, mat=person_coat_colors[i % 6])
    body.scale = (0.20, 0.55, 0.12)
    # head
    head = sphere(f"person_{i}_head", r=0.12, segs=10, rings=8, loc=(0, 1.10, 0), parent=pp, mat=MAT_PERSON_HEAD)
    # 2 legs
    for side, dx in [("L", -0.08), ("R", 0.08)]:
        leg = cube(f"person_{i}_leg_{side}", size=1.0, loc=(dx, 0.15, 0), parent=pp, mat=MAT_PERSON_BODY)
        leg.scale = (0.07, 0.30, 0.10)
    # 2 arms
    for side, dx in [("L", -0.22), ("R", 0.22)]:
        arm = cube(f"person_{i}_arm_{side}", size=1.0, loc=(dx, 0.55, 0), parent=pp, mat=person_coat_colors[i % 6])
        arm.scale = (0.07, 0.35, 0.10)
    people.append((pp, i))

# --- 3 chiens errants -------------------------------------------------------
dogs = []
for i, (dx, dz) in enumerate([(2, 3), (-3, 4), (5, 2)]):
    dp = empty(f"dog_{i}", (dx, 0, dz))
    # body
    body = cube(f"dog_{i}_body", size=1.0, loc=(0, 0.30, 0), parent=dp, mat=MAT_DOG)
    body.scale = (0.50, 0.20, 0.20)
    # head
    head = sphere(f"dog_{i}_head", r=0.15, segs=10, rings=8, loc=(0.35, 0.35, 0), parent=dp, mat=MAT_DOG)
    # 4 legs
    for k, (lx, lz) in enumerate([(0.25, 0.15), (0.25, -0.15), (-0.25, 0.15), (-0.25, -0.15)]):
        leg = cube(f"dog_{i}_l_{k}", size=1.0, loc=(lx, 0.10, lz), parent=dp, mat=MAT_DOG)
        leg.scale = (0.06, 0.20, 0.06)
    # tail
    tail = cone(f"dog_{i}_tail", r1=0.05, r2=0.02, depth=0.20, segs=6, loc=(-0.30, 0.40, 0), parent=dp, mat=MAT_DOG)
    tail.rotation_euler = (0, 0, math.radians(110))
    dogs.append(dp)

# --- 2 chevaux attachés --------------------------------------------------
def make_horse(name, x, z):
    p = empty(name, (x, 0, z))
    body = sphere(f"{name}_body", r=0.30, segs=14, rings=10, loc=(0, 0.7, 0), parent=p, mat=MAT_HORSE_BROWN)
    body.scale = (1.7, 0.8, 0.7)
    neck = cone(f"{name}_neck", r1=0.15, r2=0.12, depth=0.5, segs=8, loc=(0.45, 1.05, 0), parent=p, mat=MAT_HORSE_BROWN)
    neck.rotation_euler = (0, 0, math.radians(-50))
    head = sphere(f"{name}_head", r=0.18, segs=12, rings=10, loc=(0.75, 1.35, 0), parent=p, mat=MAT_HORSE_BROWN)
    head.scale = (1.4, 0.9, 0.8)
    for side, dz in [("L", 0.10), ("R", -0.10)]:
        ear = cone(f"{name}_ear_{side}", r1=0.04, r2=0.0, depth=0.10, segs=6, loc=(0.72, 1.50, dz), parent=p, mat=MAT_HORSE_BROWN)
        ear.rotation_euler = (math.radians(-15), 0, 0)
    # mane
    for k in range(4):
        mp = sphere(f"{name}_mane_{k}", r=0.05, segs=8, rings=6, loc=(0.45 + k * 0.06, 1.20 + k * 0.05, 0), parent=p, mat=MAT_HORSE_MANE)
    # 4 legs
    for i, (lx, lz) in enumerate([(0.45, 0.20), (0.45, -0.20), (-0.45, 0.20), (-0.45, -0.20)]):
        leg = cube(f"{name}_leg_{i}", size=1.0, loc=(lx, 0.35, lz), parent=p, mat=MAT_HORSE_BROWN)
        leg.scale = (0.10, 0.7, 0.10)
    return p

for i, (hx, hz) in enumerate([(9, 4), (-10, 4)]):
    h = make_horse(f"horse_{i}", hx, hz)

# --- 3 tonneaux + 4 cageots ---------------------------------------------
for i, (bx, bz) in enumerate([(-8, 2), (8, 2), (2, 4)]):
    bp = empty(f"barrel_{i}", (bx, 0, bz))
    body = cone(f"barrel_{i}_b", r1=0.30, r2=0.30, depth=0.6, segs=12, loc=(0, 0.30, 0), parent=bp, mat=MAT_BARREL)
    body.rotation_euler = (math.radians(90), 0, 0)
    for ay in [0.10, 0.30, 0.50]:
        band = cone(f"barrel_{i}_band_{ay}", r1=0.32, r2=0.32, depth=0.03, segs=12, loc=(0, ay, 0), parent=bp, mat=MAT_BARREL_METAL)
        band.rotation_euler = (math.radians(90), 0, 0)

for i, (cx, cz) in enumerate([(-7, 3.5), (7, 3.5), (-4, 5), (4, 5)]):
    cp = empty(f"crate_{i}", (cx, 0, cz))
    body = cube(f"crate_{i}_b", size=1.0, loc=(0, 0.25, 0), parent=cp, mat=MAT_CRATE)
    body.scale = (0.40, 0.50, 0.40)
    # planks
    for j, ay in enumerate([0.10, 0.40]):
        plank = cube(f"crate_{i}_p_{j}", size=1.0, loc=(0, ay, 0), parent=cp, mat=MAT_WOOD_DARK)
        plank.scale = (0.42, 0.03, 0.42)

# --- arbre central ---------------------------------------------------------
tree_p = empty("tree_center", (0, 0, 7.5))
trunk = cone("tree_trunk", r1=0.30, r2=0.22, depth=2.5, segs=8, loc=(0, 1.25, 0), parent=tree_p, mat=MAT_TREE_TRUNK)
trunk.rotation_euler = (math.radians(90), 0, 0)
# foliage : 5 leaf blobs
foliage_p = empty("tree_foliage_p", (0, 3.0, 0), parent=tree_p)
for j in range(5):
    ja = j * (math.pi * 2 / 5)
    f = sphere(f"tree_leaves_{j}", r=1.0, segs=18, rings=12, loc=(math.cos(ja) * 0.5, random.uniform(-0.2, 0.4), math.sin(ja) * 0.5), parent=foliage_p, mat=MAT_TREE_LEAVES)
    f.scale = (1.2, 1.0, 1.2)
# central main blob
main_blob = sphere("tree_main_blob", r=1.3, segs=20, rings=14, loc=(0, 0.4, 0), parent=foliage_p, mat=MAT_TREE_LEAVES)

# --- 5 oiseaux flying ------------------------------------------------------
birds = []
for i in range(5):
    a = i * (math.pi * 2 / 5) + 0.3
    r = 6.0
    bx = math.cos(a) * r
    bz = math.sin(a) * r
    by = 9.0
    bp = empty(f"bird_{i}", (bx, by, bz))
    body = sphere(f"bird_{i}_body", r=0.10, segs=8, rings=6, loc=(0, 0, 0), parent=bp, mat=MAT_BIRD)
    body.scale = (1.4, 0.6, 1.0)
    for side, xx in (("L", -0.25), ("R", 0.25)):
        w = cube(f"bird_{i}_w_{side}", size=1.0, loc=(xx, 0, 0), parent=bp, mat=MAT_BIRD)
        w.scale = (0.22, 0.02, 0.10)
    birds.append((bp, a, r, by))

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

# 24 banner segs wave
for segs_list, i in banner_objs:
    for k, seg in enumerate(segs_list):
        for f in range(1, FRAMES + 1, 2):
            tt = (f - 1) / (FRAMES - 1)
            wave = math.sin(k * 0.4 + tt * math.pi * 6.0 + i * 0.7)
            kx = 0.04 + k * 0.10
            kz = wave * 0.10
            kf_loc(seg, f, (kx, 0, kz))
            kf_rot(seg, f, (0, 0, wave * 0.20))

# forge flame pulse
if forge_flame:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 10.0)
        kf_scale(forge_flame, f, (s, 1.5 * s, s))

# forge smoke puffs rise
for puff, k in forge_smoke_puffs:
    phase = k * 8
    base_y = 1.5 + k * 0.5
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 60
        lt = local_f / 60
        dy = base_y + lt * 1.8
        dx = 0.50 + math.sin(lt * math.pi * 3.0) * 0.20
        kf_loc(puff, f, (dx, dy, 0))
        s = 0.5 + lt * 1.5
        kf_scale(puff, f, (s, s, s))

# 6 lanterns pulse
for i, light in enumerate(lantern_lights):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(light, f, (s, s, s))

# 12 personnages drift
for pp, idx in people:
    base_x = pp.location.x
    base_z = pp.location.z
    phase = idx * 0.4
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        dx = base_x + 0.3 * math.sin(tt * math.pi * 2.0 + phase)
        dz = base_z + 0.2 * math.cos(tt * math.pi * 1.7 + phase)
        kf_loc(pp, f, (dx, 0, dz))
        tilt = math.radians(3) * math.sin(tt * math.pi * 4.0 + phase)
        kf_rot(pp, f, (tilt, 0, 0))

# 3 dogs trot
for i, dp in enumerate(dogs):
    base_x = dp.location.x
    base_z = dp.location.z
    phase = i * 0.6
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = tt * math.pi * 2.0 + phase
        dx = base_x + math.cos(angle) * 1.0
        dz = base_z + math.sin(angle) * 1.0
        kf_loc(dp, f, (dx, 0.1 * abs(math.sin(tt * math.pi * 8.0)), dz))
        kf_rot(dp, f, (0, -angle + math.pi / 2, 0))

# 5 birds orbit
for bp, a0, r, by in birds:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 2.0
        bx = math.cos(angle) * r
        bz = math.sin(angle) * r
        by_a = by + 0.3 * math.sin(tt * math.pi * 4.0 + a0)
        kf_loc(bp, f, (bx, by_a, bz))
        kf_rot(bp, f, (0, -angle + math.pi / 2, math.radians(15) * math.sin(tt * math.pi * 8.0)))

# mage crystal pulse
if mage_crystal_obj:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 4.0)
        kf_scale(mage_crystal_obj, f, (s, s, s))

# tree foliage sway
for f in range(1, FRAMES + 1, 5):
    tt = (f - 1) / (FRAMES - 1)
    bend = math.radians(3) * math.sin(tt * math.pi * 2.0)
    kf_rot(foliage_p, f, (bend, 0, bend * 0.5))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_fantasymarket] wrote {OUT}")
