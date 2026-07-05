"""
proc_desert_oasis.py — 134e procédural AuroraIA, Phase F++++.

Oasis désert au crépuscule : dunes sable rouge avec 3 ondulations
+ bassin oasis bleu eau métallique + 6 palmiers dattiers avec dattes
+ 2 chameaux + 1 tente bédouine avec coussins + feu de camp pulsant
+ 3 scorpions au sol + 8 étoiles ciel + lune montante + halo + 5 cactus
mini + 4 fleurs désert émissives + ruines anciennes 2 piliers + 3
oiseaux du désert + ciel coucher pourpre/orange.

Animation :
- feu camp : flames pulse intense
- 8 étoiles scintillent
- 6 palmiers sway feuilles
- 2 chameaux head bob
- eau ondule
- 3 scorpions trottinent
- 4 fleurs émissives pulse
- 3 oiseaux orbites

Sortie : output/3d/pbr_desertoasis_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_desertoasis_proc.glb"))

random.seed(0xDE5E27)

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
MAT_SKY_TWILIGHT = make_mat("sky_tw", (0.45, 0.20, 0.55), roughness=1.0,
                              emi=(0.45, 0.20, 0.55), emi_strength=0.6)
MAT_SKY_LOW = make_mat("sky_low", (0.95, 0.55, 0.30), roughness=1.0,
                         emi=(0.85, 0.45, 0.25), emi_strength=0.5)
MAT_STAR = make_mat("star", (1.0, 1.0, 0.95), roughness=0.0,
                      emi=(1.0, 1.0, 0.95), emi_strength=5.5)
MAT_MOON = make_mat("moon", (0.95, 0.92, 0.85), roughness=0.0,
                      emi=(0.95, 0.92, 0.85), emi_strength=7.0)
MAT_MOON_HALO = make_mat("moon_halo", (0.85, 0.85, 0.80), roughness=0.0, alpha=0.30,
                           emi=(0.85, 0.80, 0.75), emi_strength=2.8)
MAT_SAND_RED = make_mat("sand_red", (0.85, 0.55, 0.35), roughness=0.95)
MAT_SAND_DARK = make_mat("sand_dark", (0.65, 0.38, 0.22), roughness=0.95)
MAT_OASIS = make_mat(
    "oasis_water", (0.15, 0.50, 0.65), metallic=0.8, roughness=0.08, alpha=0.90,
    emi=(0.25, 0.60, 0.75), emi_strength=0.8,
)
MAT_PALM_TRUNK = make_mat("palm_trunk", (0.40, 0.25, 0.15), roughness=0.9)
MAT_PALM_LEAF = make_mat("palm_leaf", (0.20, 0.50, 0.18), roughness=0.85)
MAT_DATE = make_mat("date", (0.50, 0.25, 0.10), roughness=0.6,
                     emi=(0.20, 0.10, 0.05), emi_strength=0.3)
MAT_CAMEL_BODY = make_mat("camel", (0.75, 0.55, 0.30), roughness=0.85)
MAT_CAMEL_HUMP = make_mat("camel_hump", (0.65, 0.45, 0.22), roughness=0.85)
MAT_TENT_FABRIC = make_mat("tent_fabric", (0.65, 0.45, 0.25), roughness=0.7)
MAT_TENT_RED = make_mat("tent_red", (0.65, 0.15, 0.10), roughness=0.6,
                          emi=(0.25, 0.05, 0.03), emi_strength=0.3)
MAT_CUSHION_P = make_mat("cushion_p", (0.70, 0.20, 0.50), roughness=0.6,
                           emi=(0.35, 0.10, 0.25), emi_strength=0.3)
MAT_CUSHION_B = make_mat("cushion_b", (0.20, 0.30, 0.65), roughness=0.6,
                           emi=(0.10, 0.15, 0.30), emi_strength=0.3)
MAT_FIRE = make_mat("fire", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85,
                     emi=(1.0, 0.55, 0.10), emi_strength=8.0)
MAT_EMBER = make_mat("ember", (1.0, 0.25, 0.05), roughness=0.0,
                      emi=(1.0, 0.25, 0.05), emi_strength=5.0)
MAT_WOOD_DARK = make_mat("wood_dark", (0.20, 0.12, 0.08), roughness=0.85)
MAT_SCORPION = make_mat("scorpion", (0.35, 0.20, 0.10), roughness=0.6)
MAT_CACTUS = make_mat("cactus", (0.20, 0.45, 0.20), roughness=0.85)
MAT_FLOWER_Y = make_mat("flower_y", (1.0, 0.85, 0.20), roughness=0.4,
                          emi=(0.5, 0.45, 0.05), emi_strength=2.5)
MAT_FLOWER_O = make_mat("flower_o", (1.0, 0.45, 0.10), roughness=0.4,
                          emi=(0.55, 0.25, 0.05), emi_strength=2.5)
MAT_RUINS = make_mat("ruins", (0.65, 0.50, 0.30), roughness=0.85,
                       emi=(0.20, 0.15, 0.08), emi_strength=0.2)
MAT_BIRD = make_mat("bird", (0.25, 0.20, 0.15), roughness=0.7)

# --- backdrop : twilight sky --------------------------------------------
sky_top = cube("sky_top", size=1.0, loc=(0, 18, 11), mat=MAT_SKY_TWILIGHT)
sky_top.scale = (40, 0.1, 8)
sky_bot = cube("sky_low", size=1.0, loc=(0, 18, 4), mat=MAT_SKY_LOW)
sky_bot.scale = (40, 0.1, 8)

# 50 stars (sparse for twilight)
for i in range(50):
    x = random.uniform(-15, 15)
    z = random.uniform(8, 13)
    y = random.uniform(15, 16)
    r = random.uniform(0.06, 0.11)
    s = sphere(f"star_{i}", r=r, segs=8, rings=6, loc=(x, y, z), mat=MAT_STAR)
    s["_phase"] = (i * 11) % 47

# moon + halo
moon_p = empty("moon_p", (-7.0, 13.5, 9.0))
moon = sphere("moon", r=1.0, segs=24, rings=18, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON)
moon_halo = sphere("moon_halo", r=2.0, segs=20, rings=14, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON_HALO)

# --- desert ground with red sand ------------------------------------------
ground = cube("ground", size=1.0, loc=(0, -0.05, 0), mat=MAT_SAND_RED)
ground.scale = (40, 0.1, 28)

# 3 dunes (large undulations)
for i, (dx, dz, dsx, dsy, dsz) in enumerate([(-12, 5, 7, 0.9, 3), (12, -4, 6, 0.8, 3), (-15, -6, 5, 0.7, 3)]):
    d = sphere(f"dune_{i}", r=2.0, segs=18, rings=12, loc=(dx, 0.5, dz), mat=MAT_SAND_DARK)
    d.scale = (dsx, dsy, dsz)

# --- oasis pond ----------------------------------------------------------
oasis = cube("oasis", size=1.0, loc=(0, 0.02, 0), mat=MAT_OASIS)
oasis.scale = (4.0, 0.05, 3.0)

# sand ring around oasis (slightly raised)
for i in range(16):
    a = i * (math.pi * 2 / 16)
    sx = math.cos(a) * 2.8
    sz = math.sin(a) * 2.2
    sr = sphere(f"oasis_ring_{i}", r=0.25, segs=10, rings=6, loc=(sx, 0.1, sz), mat=MAT_SAND_DARK)
    sr.scale = (1.0, 0.3, 1.0)

# --- 6 palmiers dattiers --------------------------------------------------
palms = []
palm_positions = []
for i in range(6):
    a = i * (math.pi * 2 / 6) + 0.4
    r = 4.5
    pp_x = math.cos(a) * r
    pp_z = math.sin(a) * r
    palm_positions.append((pp_x, pp_z))

for i, (px, pz) in enumerate(palm_positions):
    pp = empty(f"palm_{i}", (px, 0, pz))
    # trunk (5 segments curving)
    for j in range(5):
        h = 0.5 + j * 0.8
        sx = math.sin(j * 0.3) * 0.10
        cone_seg = cone(f"palm_{i}_t_{j}", r1=0.18 - j * 0.015, r2=0.16 - j * 0.015, depth=0.8, segs=8, loc=(sx, h, 0), parent=pp, mat=MAT_PALM_TRUNK)
        cone_seg.rotation_euler = (math.radians(90), 0, 0)
    # leaves head : 8 fronds radiating
    head_p = empty(f"palm_{i}_head", (0, 4.2, 0), parent=pp)
    for k in range(8):
        ka = k * (math.pi * 2 / 8)
        frond = sphere(f"palm_{i}_f_{k}", r=0.3, segs=10, rings=6, loc=(math.cos(ka) * 0.8, -0.1, math.sin(ka) * 0.8), parent=head_p, mat=MAT_PALM_LEAF)
        frond.scale = (3.5, 0.3, 0.6)
        frond.rotation_euler = (math.radians(-20), -ka, 0)
    # 3 date clusters
    for k in range(3):
        ka = k * (math.pi * 2 / 3)
        date = sphere(f"palm_{i}_date_{k}", r=0.15, segs=10, rings=8, loc=(math.cos(ka) * 0.25, 4.0, math.sin(ka) * 0.25), parent=pp, mat=MAT_DATE)
        date.scale = (1.0, 0.6, 1.0)
    palms.append(head_p)

# --- 2 chameaux ----------------------------------------------------------
def make_camel(name, x, z, rot=0):
    p = empty(name, (x, 0.45, z))
    p.rotation_euler = (0, rot, 0)
    body = cube(f"{name}_body", size=1.0, loc=(0, 0.5, 0), parent=p, mat=MAT_CAMEL_BODY)
    body.scale = (1.4, 0.4, 0.5)
    # 2 humps
    hump1 = sphere(f"{name}_hump1", r=0.30, segs=14, rings=10, loc=(0.25, 0.95, 0), parent=p, mat=MAT_CAMEL_HUMP)
    hump2 = sphere(f"{name}_hump2", r=0.25, segs=12, rings=10, loc=(-0.30, 0.90, 0), parent=p, mat=MAT_CAMEL_HUMP)
    # neck
    neck = cone(f"{name}_neck", r1=0.18, r2=0.15, depth=0.7, segs=8, loc=(0.7, 0.95, 0), parent=p, mat=MAT_CAMEL_BODY)
    neck.rotation_euler = (0, 0, math.radians(-30))
    # head
    head_p = empty(f"{name}_head_p", (0.95, 1.25, 0), parent=p)
    head = sphere(f"{name}_head", r=0.20, segs=12, rings=10, loc=(0, 0, 0), parent=head_p, mat=MAT_CAMEL_BODY)
    head.scale = (1.4, 0.9, 0.8)
    # 4 legs
    for i, (lx, lz) in enumerate([(0.5, 0.20), (0.5, -0.20), (-0.5, 0.20), (-0.5, -0.20)]):
        leg = cube(f"{name}_leg_{i}", size=1.0, loc=(lx, 0.15, lz), parent=p, mat=MAT_CAMEL_BODY)
        leg.scale = (0.13, 0.40, 0.13)
    # tail
    tail = cone(f"{name}_tail", r1=0.04, r2=0.02, depth=0.25, segs=6, loc=(-0.75, 0.85, 0), parent=p, mat=MAT_CAMEL_BODY)
    tail.rotation_euler = (0, 0, math.radians(110))
    return p, head_p

camel_heads = []
for i, (cx, cz, crot) in enumerate([
    (-3.5, 4.0, math.radians(-30)),
    (3.5, -4.0, math.radians(140)),
]):
    cp, head_p = make_camel(f"camel_{i}", cx, cz, crot)
    camel_heads.append((cp, head_p, i))

# --- bedouin tent --------------------------------------------------------
tent_p = empty("tent", (-4.5, 0, -3.0))
tent_p.rotation_euler = (0, math.radians(25), 0)
# main tent (large cone, brown fabric)
tent_main = cone("tent_main", r1=1.5, r2=0.05, depth=2.0, segs=6, loc=(0, 1.0, 0), parent=tent_p, mat=MAT_TENT_FABRIC)
tent_main.rotation_euler = (math.radians(90), 0, math.radians(30))
# entrance opening (smaller darker triangle)
entrance = cube("tent_entrance", size=1.0, loc=(0.95, 0.6, 0.4), parent=tent_p, mat=MAT_WOOD_DARK)
entrance.scale = (0.05, 0.7, 0.4)
entrance.rotation_euler = (0, math.radians(35), 0)
# red banner on top
banner_top = cube("tent_banner", size=1.0, loc=(0, 2.10, 0), parent=tent_p, mat=MAT_TENT_RED)
banner_top.scale = (0.2, 0.10, 0.2)
# 4 cushions inside (visible through opening)
for i, (cx, cz) in enumerate([(1.2, 0.3), (1.0, -0.2), (0.8, 0.0), (1.4, 0)]):
    mat = MAT_CUSHION_P if i % 2 == 0 else MAT_CUSHION_B
    cush = cube(f"tent_cush_{i}", size=1.0, loc=(cx, 0.20, cz), parent=tent_p, mat=mat)
    cush.scale = (0.20, 0.10, 0.15)
# 2 ropes/stakes
for side, dx in [("L", -1.6), ("R", 1.6)]:
    rope = cone(f"tent_rope_{side}", r1=0.02, r2=0.02, depth=1.0, segs=4, loc=(dx, 0.5, 0), parent=tent_p, mat=MAT_WOOD_DARK)
    rope.rotation_euler = (math.radians(45), 0, 0)

# --- feu de camp ----------------------------------------------------------
fire_p = empty("fire_camp", (-2.5, 0, -2.0))
# 4 logs en croix
for k in range(4):
    ka = k * (math.pi / 4)
    log = cone(f"fire_log_{k}", r1=0.06, r2=0.06, depth=0.6, segs=6, loc=(0, 0.06, 0), parent=fire_p, mat=MAT_WOOD_DARK)
    log.rotation_euler = (0, ka, math.radians(90))
# main flame (large sphere émissive)
flame_main = sphere("fire_flame", r=0.25, segs=14, rings=10, loc=(0, 0.30, 0), parent=fire_p, mat=MAT_FIRE)
flame_main.scale = (1.0, 1.8, 1.0)
# 5 ember sphères en arrière-plan
embers = []
for k in range(5):
    a = k * (math.pi * 2 / 5)
    ex = math.cos(a) * 0.15
    ez = math.sin(a) * 0.15
    em = sphere(f"fire_ember_{k}", r=0.08, segs=8, rings=6, loc=(ex, 0.25, ez), parent=fire_p, mat=MAT_EMBER)
    em.scale = (1.0, 1.2, 1.0)
    embers.append(em)

# --- 3 scorpions ---------------------------------------------------------
scorpions = []
for i, (sx, sz) in enumerate([(2.5, 3.0), (-3.0, -4.0), (4.0, 1.0)]):
    sp = empty(f"scorpion_{i}", (sx, 0, sz))
    # body
    body = sphere(f"scorp_{i}_body", r=0.12, segs=10, rings=6, loc=(0, 0.10, 0), parent=sp, mat=MAT_SCORPION)
    body.scale = (1.6, 0.5, 0.7)
    # tail (3 segments)
    for k in range(3):
        kx = -0.15 - k * 0.10
        ky = 0.10 + k * 0.06
        tail_seg = sphere(f"scorp_{i}_t_{k}", r=0.05 - k * 0.005, segs=8, rings=6, loc=(kx, ky, 0), parent=sp, mat=MAT_SCORPION)
    # stinger
    stinger = cone(f"scorp_{i}_sting", r1=0.04, r2=0.0, depth=0.10, segs=4, loc=(-0.40, 0.30, 0), parent=sp, mat=MAT_EMBER)
    stinger.rotation_euler = (math.radians(120), 0, 0)
    # 2 pincers
    for side, dz in [("L", 0.10), ("R", -0.10)]:
        pinc = sphere(f"scorp_{i}_pinc_{side}", r=0.06, segs=8, rings=6, loc=(0.18, 0.10, dz), parent=sp, mat=MAT_SCORPION)
        pinc.scale = (1.4, 0.6, 0.8)
    scorpions.append((sp, i))

# --- 5 mini cactus -------------------------------------------------------
for i, (cx, cz) in enumerate([(-6, -2), (6, -1), (-8, 4), (7, 4), (-1, -5)]):
    cp = empty(f"cactus_{i}", (cx, 0, cz))
    main = cone(f"cactus_{i}_main", r1=0.12, r2=0.10, depth=0.6, segs=10, loc=(0, 0.30, 0), parent=cp, mat=MAT_CACTUS)
    main.rotation_euler = (math.radians(90), 0, 0)
    # 1-2 arms
    arms = random.randint(1, 2)
    for j in range(arms):
        ja = j * math.pi
        a = cone(f"cactus_{i}_arm_{j}", r1=0.08, r2=0.06, depth=0.3, segs=6, loc=(math.cos(ja) * 0.15, 0.4, math.sin(ja) * 0.15), parent=cp, mat=MAT_CACTUS)
        a.rotation_euler = (math.radians(90), 0, math.radians(-50 if j == 0 else 50))

# --- 4 fleurs désert émissives -------------------------------------------
flowers_obj = []
for i, (fx, fz) in enumerate([(2.0, 2.5), (-2.0, 2.5), (1.5, -2.5), (-1.5, -2.5)]):
    fp = empty(f"flower_{i}", (fx, 0, fz))
    # stem
    stem = cone(f"flower_{i}_stem", r1=0.03, r2=0.03, depth=0.3, segs=6, loc=(0, 0.15, 0), parent=fp, mat=MAT_CACTUS)
    stem.rotation_euler = (math.radians(90), 0, 0)
    # 5 petals
    mat = MAT_FLOWER_Y if i % 2 == 0 else MAT_FLOWER_O
    for k in range(5):
        ka = k * (math.pi * 2 / 5)
        petal = sphere(f"flower_{i}_p_{k}", r=0.08, segs=8, rings=6, loc=(math.cos(ka) * 0.10, 0.35, math.sin(ka) * 0.10), parent=fp, mat=mat)
        petal.scale = (1.0, 0.4, 1.0)
    # center
    center = sphere(f"flower_{i}_c", r=0.05, segs=8, rings=6, loc=(0, 0.35, 0), parent=fp, mat=MAT_EMBER)
    flowers_obj.append((fp, i))

# --- ruines anciennes : 2 piliers ----------------------------------------
ruins_p = empty("ruins", (6.5, 0, 5.5))
ruins_p.rotation_euler = (0, math.radians(-15), 0)
# 2 pillars (broken at top)
for side, dx in [("L", -1.0), ("R", 1.0)]:
    # main pillar (cylindrical)
    pillar = cone(f"pillar_{side}", r1=0.30, r2=0.30, depth=2.0, segs=16, loc=(dx, 1.0, 0), parent=ruins_p, mat=MAT_RUINS)
    pillar.rotation_euler = (math.radians(90), 0, 0)
    # broken top (smaller off-center piece)
    top = cone(f"pillar_top_{side}", r1=0.30, r2=0.25, depth=0.3, segs=10, loc=(dx, 2.15, 0), parent=ruins_p, mat=MAT_RUINS)
    top.rotation_euler = (math.radians(90), 0, 0)
    # capital block
    cap = cube(f"pillar_cap_{side}", size=1.0, loc=(dx, 2.45, 0), parent=ruins_p, mat=MAT_RUINS)
    cap.scale = (0.6, 0.18, 0.6)
# rubble at base
for i in range(5):
    rx = random.uniform(-1.8, 1.8)
    rz = random.uniform(-0.6, 0.6)
    rb = sphere(f"rubble_{i}", r=random.uniform(0.15, 0.25), segs=10, rings=8, loc=(rx, 0.15, rz), parent=ruins_p, mat=MAT_RUINS)
    rb.scale = (1.2, 0.5, 1.0)
# fallen broken pillar piece
fallen = cone("pillar_fallen", r1=0.28, r2=0.28, depth=1.3, segs=14, loc=(0, 0.25, 1.5), parent=ruins_p, mat=MAT_RUINS)
fallen.rotation_euler = (0, math.radians(30), math.radians(90))

# --- 3 oiseaux ---------------------------------------------------------
birds = []
for i in range(3):
    a = i * (math.pi * 2 / 3) + 0.5
    r = 6.5
    bx = math.cos(a) * r
    bz = math.sin(a) * r
    by = 9.0 + random.uniform(-0.5, 0.5)
    bp = empty(f"bird_{i}", (bx, by, bz))
    body = sphere(f"bird_{i}_body", r=0.13, segs=10, rings=8, loc=(0, 0, 0), parent=bp, mat=MAT_BIRD)
    body.scale = (1.5, 0.7, 1.0)
    for side, xx in (("L", -0.30), ("R", 0.30)):
        w = cube(f"bird_{i}_w_{side}", size=1.0, loc=(xx, 0, 0), parent=bp, mat=MAT_BIRD)
        w.scale = (0.30, 0.02, 0.10)
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

# main fire flame intense pulse
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.40 * math.sin(tt * math.pi * 10.0)
    kf_scale(flame_main, f, (s, 1.8 * s, s))

# 5 embers pulse
for i, em in enumerate(embers):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.25 * math.sin(tt * math.pi * 8.0 + phase)
        kf_scale(em, f, (s, 1.2 * s, s))

# 6 palms sway
for i, palm_head in enumerate(palms):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bend = math.radians(5) * math.sin(tt * math.pi * 3.0 + phase)
        kf_rot(palm_head, f, (bend, 0, bend * 0.5))

# 2 camels head bob
for cp, head_p, idx in camel_heads:
    phase = idx * 0.5
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bob = math.radians(8) * math.sin(tt * math.pi * 4.0 + phase)
        kf_rot(head_p, f, (bob, 0, 0))

# stars twinkle
for i in range(50):
    star = bpy.data.objects.get(f"star_{i}")
    if not star:
        continue
    phase = star["_phase"]
    for f in range(1, FRAMES + 1, 6):
        tt = (f - 1) / (FRAMES - 1)
        local = (math.sin(tt * math.pi * 6.0 + phase * 0.13) + 1) * 0.5
        s = 0.7 + 0.5 * local
        kf_scale(star, f, (s, s, s))

# moon halo breathe
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.12 * math.sin(tt * math.pi * 3.0)
    kf_scale(moon_halo, f, (s, s, s))

# 3 scorpions move (circular)
for sp, idx in scorpions:
    base_x = sp.location.x
    base_z = sp.location.z
    phase = idx * 0.6
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = tt * math.pi * 2.0 + phase
        dx = base_x + math.cos(angle) * 0.8
        dz = base_z + math.sin(angle) * 0.8
        kf_loc(sp, f, (dx, 0, dz))
        kf_rot(sp, f, (0, -angle + math.pi / 2, 0))

# 4 flowers pulse
for fp, idx in flowers_obj:
    phase = idx * 0.4
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 4.0 + phase)
        kf_scale(fp, f, (s, s, s))

# 3 birds orbit
for bp, a0, r, by in birds:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 2.0
        bx = math.cos(angle) * r
        bz = math.sin(angle) * r
        by_a = by + 0.3 * math.sin(tt * math.pi * 4.0 + a0)
        kf_loc(bp, f, (bx, by_a, bz))
        kf_rot(bp, f, (0, -angle + math.pi / 2, math.radians(15) * math.sin(tt * math.pi * 8.0)))

# oasis water subtle wobble (scale)
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.03 * math.sin(tt * math.pi * 4.0)
    kf_scale(oasis, f, (4.0 * s, 0.05, 3.0 * s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_desertoasis] wrote {OUT}")
