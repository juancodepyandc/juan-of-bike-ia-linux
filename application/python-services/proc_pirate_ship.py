"""
proc_pirate_ship.py — 131e procédural AuroraIA, Phase F++++.

Galion pirate sur mer agitée : grand galion en bois multi-pont +
3 mâts (foremast + mainmast + mizzenmast) avec voiles bombées + drapeau
pirate Jolly Roger + 6 canons sur 2 côtés + roue de gouvernail + figurehead
proue + 8 vagues + île au loin avec 4 palmiers + trésor coffre flottant
+ 3 mouettes + ciel orage + tonneau flottant + crow's nest.

Animation :
- galion pitch/roll
- voiles bombement scale
- drapeau pirate flotte
- 8 vagues ondulent
- 3 mouettes orbites
- gouvernail rotate
- 6 canons pas anim mais détaillés

Sortie : output/3d/pbr_pirateship_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_pirateship_proc.glb"))

random.seed(0xCAFE17)

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
MAT_SKY_STORM = make_mat("sky_storm", (0.20, 0.18, 0.25), roughness=1.0,
                          emi=(0.15, 0.15, 0.22), emi_strength=0.4)
MAT_CLOUD_DARK = make_mat("cloud_dark", (0.30, 0.28, 0.32), roughness=1.0, alpha=0.85,
                            emi=(0.20, 0.20, 0.25), emi_strength=0.3)
MAT_OCEAN = make_mat(
    "ocean", (0.05, 0.20, 0.35), metallic=0.8, roughness=0.1, alpha=0.95,
    emi=(0.05, 0.20, 0.35), emi_strength=0.4,
)
MAT_WAVE = make_mat(
    "wave", (0.20, 0.45, 0.55), metallic=0.7, roughness=0.15, alpha=0.85,
    emi=(0.15, 0.40, 0.55), emi_strength=0.5,
)
MAT_FOAM = make_mat(
    "foam", (0.95, 0.95, 1.0), roughness=0.4, alpha=0.85,
    emi=(0.85, 0.90, 1.0), emi_strength=1.2,
)
MAT_HULL_DARK = make_mat("hull_dark", (0.25, 0.15, 0.08), roughness=0.7)
MAT_HULL_LIGHT = make_mat("hull_light", (0.45, 0.28, 0.15), roughness=0.7)
MAT_HULL_TRIM = make_mat("hull_trim", (0.85, 0.70, 0.30), metallic=0.5, roughness=0.4,
                          emi=(0.30, 0.20, 0.05), emi_strength=0.3)
MAT_DECK = make_mat("deck", (0.55, 0.40, 0.20), roughness=0.7)
MAT_MAST = make_mat("mast", (0.30, 0.20, 0.10), roughness=0.8)
MAT_SAIL = make_mat("sail", (0.85, 0.82, 0.75), roughness=0.85, alpha=0.95,
                     emi=(0.30, 0.28, 0.25), emi_strength=0.3)
MAT_SAIL_TORN = make_mat("sail_torn", (0.70, 0.65, 0.55), roughness=0.9, alpha=0.95)
MAT_ROPE = make_mat("rope", (0.55, 0.40, 0.20), roughness=0.85)
MAT_FLAG_BLACK = make_mat("flag_black", (0.05, 0.05, 0.05), roughness=0.7)
MAT_SKULL = make_mat("skull", (0.95, 0.92, 0.85), roughness=0.5,
                       emi=(0.40, 0.40, 0.35), emi_strength=0.3)
MAT_CANNON = make_mat("cannon", (0.15, 0.13, 0.10), metallic=0.8, roughness=0.4)
MAT_WHEEL = make_mat("wheel", (0.45, 0.30, 0.15), roughness=0.6)
MAT_FIGUREHEAD = make_mat("figurehead", (0.65, 0.50, 0.30), metallic=0.4, roughness=0.5,
                            emi=(0.20, 0.15, 0.08), emi_strength=0.3)
MAT_LANTERN = make_mat("lantern", (1.0, 0.65, 0.20), roughness=0.0, alpha=0.85,
                         emi=(1.0, 0.65, 0.20), emi_strength=7.0)
MAT_ISLAND_SAND = make_mat("island_sand", (0.85, 0.78, 0.55), roughness=0.95)
MAT_PALM_TRUNK = make_mat("palm_trunk", (0.35, 0.25, 0.15), roughness=0.85)
MAT_PALM_LEAF = make_mat("palm_leaf", (0.20, 0.45, 0.15), roughness=0.85)
MAT_CHEST = make_mat("chest", (0.30, 0.18, 0.10), roughness=0.7)
MAT_CHEST_METAL = make_mat("chest_metal", (0.55, 0.50, 0.40), metallic=0.7, roughness=0.4)
MAT_GOLD = make_mat("gold", (1.0, 0.78, 0.20), metallic=0.95, roughness=0.20,
                     emi=(0.55, 0.40, 0.05), emi_strength=0.6)
MAT_GULL = make_mat("gull", (0.85, 0.85, 0.88), roughness=0.7)
MAT_BARREL = make_mat("barrel", (0.45, 0.28, 0.15), roughness=0.7)

# --- backdrop ---------------------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 18, 6), mat=MAT_SKY_STORM)
sky.scale = (40, 0.1, 16)

# 6 storm clouds
for i in range(6):
    cx = -15 + i * 5 + random.uniform(-1, 1)
    cz = 11 + random.uniform(-0.5, 1.0)
    cy = 14.5 + random.uniform(-0.5, 0.5)
    cl = sphere(f"cloud_{i}", r=random.uniform(1.2, 1.8), segs=14, rings=10, loc=(cx, cy, cz), mat=MAT_CLOUD_DARK)
    cl.scale = (1.7, 0.55, 1.1)

# --- ocean surface ----------------------------------------------------------
ocean = cube("ocean", size=1.0, loc=(0, 0, 0), mat=MAT_OCEAN)
ocean.scale = (40, 0.1, 28)

# 8 waves
waves = []
for i in range(8):
    wx = random.uniform(-15, 15)
    wz = random.uniform(-10, 10)
    if abs(wx) < 5 and abs(wz) < 5:
        continue  # leave ship area clear
    w = sphere(f"wave_{i}", r=random.uniform(0.7, 1.1), segs=16, rings=10, loc=(wx, 0.3, wz), mat=MAT_WAVE)
    w.scale = (2.2, 0.4, 1.4)
    waves.append((w, wx, wz, random.uniform(0, math.pi * 2)))

# 4 foam crests
foams = []
for i in range(4):
    wx = random.uniform(-10, 10)
    wz = random.uniform(-8, 8)
    fo = sphere(f"foam_{i}", r=0.5, segs=12, rings=8, loc=(wx, 0.55, wz), mat=MAT_FOAM)
    fo.scale = (1.4, 0.15, 0.8)
    foams.append((fo, wx, wz, random.uniform(0, 1)))

# --- main pirate ship -----------------------------------------------------
ship = empty("ship", (-1.0, 0.8, 0))

# hull bottom (curved, dark wood)
hull = sphere("hull", r=1.5, segs=24, rings=14, loc=(0, 0, 0), parent=ship, mat=MAT_HULL_DARK)
hull.scale = (3.0, 0.8, 1.2)

# upper hull / quarterdeck
upper = cube("upper_hull", size=1.0, loc=(0, 0.7, 0), parent=ship, mat=MAT_HULL_LIGHT)
upper.scale = (4.5, 0.7, 2.0)

# stern (raised at back)
stern = cube("stern", size=1.0, loc=(-2.5, 1.5, 0), parent=ship, mat=MAT_HULL_LIGHT)
stern.scale = (1.5, 1.2, 2.0)

# bow (raised at front)
bow = cube("bow", size=1.0, loc=(2.5, 1.2, 0), parent=ship, mat=MAT_HULL_LIGHT)
bow.scale = (1.3, 0.9, 1.8)

# main deck
deck = cube("deck", size=1.0, loc=(0, 1.10, 0), parent=ship, mat=MAT_DECK)
deck.scale = (4.5, 0.05, 2.0)

# stern deck (raised)
stern_deck = cube("stern_deck", size=1.0, loc=(-2.5, 2.15, 0), parent=ship, mat=MAT_DECK)
stern_deck.scale = (1.5, 0.05, 2.0)

# gold trim around hull
for side, dy in [("T", 1.05), ("B", 0.55)]:
    for k_side, dz in [("F", 1.05), ("B", -1.05)]:
        trim = cube(f"hull_trim_{side}_{k_side}", size=1.0, loc=(0, dy, dz), parent=ship, mat=MAT_HULL_TRIM)
        trim.scale = (4.5, 0.05, 0.05)

# --- 6 canons (3 each side) -----------------------------------------------
for side, dz in [("F", 1.05), ("B", -1.05)]:
    for i in range(3):
        cx = -1.5 + i * 1.5
        cp = empty(f"cannon_p_{side}_{i}", (cx, 0.85, dz), parent=ship)
        # barrel
        barrel = cone(f"cannon_b_{side}_{i}", r1=0.12, r2=0.14, depth=0.55, segs=10, loc=(0, 0, 0.20 if dz > 0 else -0.20), parent=cp, mat=MAT_CANNON)
        barrel.rotation_euler = (math.radians(90 if dz > 0 else -90), 0, 0)
        # carriage (wooden support)
        carr = cube(f"cannon_c_{side}_{i}", size=1.0, loc=(0, -0.10, 0), parent=cp, mat=MAT_HULL_DARK)
        carr.scale = (0.30, 0.20, 0.40)
        # 2 small wheels
        for w_side, w_dx in [("L", 0.18), ("R", -0.18)]:
            w = cone(f"cannon_w_{side}_{i}_{w_side}", r1=0.06, r2=0.06, depth=0.06, segs=8, loc=(w_dx, -0.18, 0), parent=cp, mat=MAT_HULL_DARK)
            w.rotation_euler = (math.radians(90), 0, 0)

# --- 3 mâts avec voiles --------------------------------------------------
masts_data = [
    ("foremast", 1.8, 2.5, 0.8, [(2.0, 1.2)]),       # foremast : 1 voile
    ("mainmast", 0.0, 3.0, 0.9, [(2.4, 1.5), (1.8, 1.0)]),  # mainmast : 2 voiles
    ("mizzenmast", -1.8, 2.5, 0.8, [(2.0, 1.2)]),    # mizzenmast : 1 voile
]
sails = []
for mast_name, mx, mh, mr, sail_data in masts_data:
    # mast pole
    mast = cone(f"{mast_name}", r1=0.10, r2=0.08, depth=mh + 0.3, segs=8, loc=(mx, 1.1 + (mh + 0.3) / 2, 0), parent=ship, mat=MAT_MAST)
    mast.rotation_euler = (math.radians(90), 0, 0)
    # crow's nest at mainmast top
    if mast_name == "mainmast":
        nest = cone("crows_nest", r1=0.40, r2=0.40, depth=0.30, segs=12, loc=(mx, 1.1 + mh, 0), parent=ship, mat=MAT_HULL_DARK)
        nest.rotation_euler = (math.radians(90), 0, 0)
        # 4 railing posts
        for j in range(4):
            a = j * (math.pi * 2 / 4)
            rp = cube(f"nest_rail_{j}", size=1.0, loc=(mx + math.cos(a) * 0.35, 1.1 + mh + 0.15, math.sin(a) * 0.35), parent=ship, mat=MAT_MAST)
            rp.scale = (0.03, 0.15, 0.03)
    # yards (horizontal cross beams) + sails attached
    for k, (yard_y_off, sail_h) in enumerate(sail_data):
        yard_y = 1.1 + yard_y_off
        # yard
        yard = cube(f"{mast_name}_yard_{k}", size=1.0, loc=(mx, yard_y, 0), parent=ship, mat=MAT_MAST)
        yard.scale = (0.05, 0.05, 2.4)
        # sail (curved approximation via 5 cubes stacked horizontally)
        sail_p = empty(f"{mast_name}_sail_p_{k}", (mx, yard_y - sail_h / 2, 0), parent=ship)
        for j in range(5):
            jx = -0.96 + j * 0.48
            # belly amount : middle bigger
            belly = 0.20 if j == 2 else (0.10 if 1 <= j <= 3 else 0.05)
            seg = cube(f"{mast_name}_sail_{k}_s_{j}", size=1.0, loc=(jx * 0.0, -0.05, jx), parent=sail_p, mat=MAT_SAIL)
            seg.scale = (0.40, sail_h, 0.45)
        sails.append(sail_p)

# --- drapeau pirate Jolly Roger -------------------------------------------
# mainmast = mast_x = 0, top at y = 1.1 + 3.3 = 4.4
flag_p = empty("pirate_flag", (0, 4.5, 0), parent=ship)
# pole already there, add flag itself
# flag : 4 segments waving
flag_segs = []
for j in range(5):
    seg = cube(f"pirate_flag_{j}", size=1.0, loc=(0, 0.0, 0.08 + j * 0.18), parent=flag_p, mat=MAT_FLAG_BLACK)
    seg.scale = (0.04, 0.5, 0.18)
    flag_segs.append(seg)
# skull on flag (sphere blanc + 2 black eye sockets + crossed bones)
skull = sphere("pirate_skull", r=0.10, segs=12, rings=8, loc=(0, 0.15, 0.5), parent=flag_p, mat=MAT_SKULL)
skull.scale = (1.0, 0.9, 0.4)
# 2 eye sockets
for side, dz in [("L", -0.04), ("R", 0.04)]:
    eye = sphere(f"pirate_skull_eye_{side}", r=0.025, segs=8, rings=6, loc=(0.01, 0.20, 0.50 + dz), parent=flag_p, mat=MAT_FLAG_BLACK)
# 2 crossed bones
for k in range(2):
    bone = cube(f"pirate_bone_{k}", size=1.0, loc=(0.01, 0.00, 0.5), parent=flag_p, mat=MAT_SKULL)
    bone.scale = (0.025, 0.20, 0.04)
    bone.rotation_euler = (0, 0, math.radians(45 if k == 0 else -45))

# --- roue de gouvernail ------------------------------------------------
wheel_p = empty("wheel_p", (-2.5, 2.6, 0), parent=ship)
# hub
hub = sphere("wheel_hub", r=0.12, segs=12, rings=8, loc=(0, 0, 0), parent=wheel_p, mat=MAT_WHEEL)
# 8 spokes
for k in range(8):
    a = k * (math.pi / 4)
    spoke = cube(f"wheel_spoke_{k}", size=1.0, loc=(0, math.sin(a) * 0.25, math.cos(a) * 0.25), parent=wheel_p, mat=MAT_WHEEL)
    spoke.scale = (0.04, 0.35, 0.04)
    spoke.rotation_euler = (a, 0, 0)
# outer ring (8 small spheres at perimeter)
for k in range(8):
    a = k * (math.pi / 4)
    pt = sphere(f"wheel_pt_{k}", r=0.05, segs=8, rings=6, loc=(0, math.sin(a) * 0.45, math.cos(a) * 0.45), parent=wheel_p, mat=MAT_WHEEL)

# --- figurehead at the bow ---------------------------------------------
fig_p = empty("figurehead", (3.4, 1.0, 0), parent=ship)
# mermaid-like figure : torso + head
torso = sphere("fig_torso", r=0.30, segs=14, rings=10, loc=(0, 0, 0), parent=fig_p, mat=MAT_FIGUREHEAD)
torso.scale = (0.7, 1.4, 0.6)
head = sphere("fig_head", r=0.18, segs=12, rings=8, loc=(0, 0.55, 0), parent=fig_p, mat=MAT_FIGUREHEAD)
# hair (back)
hair = sphere("fig_hair", r=0.20, segs=10, rings=8, loc=(0, 0.55, -0.15), parent=fig_p, mat=MAT_HULL_DARK)
hair.scale = (1.0, 0.9, 0.6)
# 2 arms extended forward
for side, dz in [("L", 0.18), ("R", -0.18)]:
    arm = cube(f"fig_arm_{side}", size=1.0, loc=(0.30, -0.10, dz), parent=fig_p, mat=MAT_FIGUREHEAD)
    arm.scale = (0.30, 0.10, 0.10)
    arm.rotation_euler = (0, 0, math.radians(-30))

# --- 2 lanternes sur le bord ----------------------------------------------
for i, (lx, lz) in enumerate([(-2.7, 1.0), (-2.7, -1.0)]):
    lp = empty(f"lantern_{i}", (lx, 2.5, lz), parent=ship)
    case = cube(f"lantern_{i}_case", size=1.0, loc=(0, 0, 0), parent=lp, mat=MAT_HULL_DARK)
    case.scale = (0.10, 0.18, 0.10)
    # light orb
    light = sphere(f"lantern_{i}_light", r=0.08, segs=10, rings=8, loc=(0, 0, 0), parent=lp, mat=MAT_LANTERN)
    # top cap
    cap = cone(f"lantern_{i}_cap", r1=0.12, r2=0.0, depth=0.10, segs=4, loc=(0, 0.14, 0), parent=lp, mat=MAT_HULL_DARK)
    cap.rotation_euler = (math.radians(90), 0, math.radians(45))

# --- ropes (rigging) ---------------------------------------------------
# 4 ropes from mast tops to deck corners
for k in range(4):
    src_x = [1.8, 0, 0, -1.8][k]
    dst_x = [4.0, 4.0, -4.0, -4.0][k]
    src_y = 3.5
    dst_y = 1.1
    dx = dst_x - src_x
    dy = dst_y - src_y
    length = math.sqrt(dx * dx + dy * dy)
    mx = (src_x + dst_x) / 2
    my = (src_y + dst_y) / 2
    rope = cube(f"rope_{k}", size=1.0, loc=(mx, my, 0), parent=ship, mat=MAT_ROPE)
    rope.scale = (length, 0.02, 0.02)
    rope.rotation_euler = (0, 0, math.atan2(dy, dx))

# --- island in distance --------------------------------------------------
island_p = empty("island", (9.0, 0, 7.0))
# sand mound
sand = sphere("island_sand", r=2.0, segs=18, rings=12, loc=(0, 0.2, 0), parent=island_p, mat=MAT_ISLAND_SAND)
sand.scale = (1.4, 0.3, 1.0)
# 4 palm trees
for i in range(4):
    a = i * (math.pi * 2 / 4) + 0.3
    px = math.cos(a) * 1.0
    pz = math.sin(a) * 0.7
    pp = empty(f"palm_{i}", (px, 0.3, pz), parent=island_p)
    # trunk (curving)
    for j in range(4):
        h = 0.3 + j * 0.5
        sx = math.sin(j * 0.5) * 0.1
        tr = cone(f"palm_{i}_trunk_{j}", r1=0.10 - j * 0.015, r2=0.10 - j * 0.015, depth=0.5, segs=6, loc=(sx, h, 0), parent=pp, mat=MAT_PALM_TRUNK)
        tr.rotation_euler = (math.radians(90), 0, 0)
    # 5 fronds
    for k in range(5):
        ka = k * (math.pi * 2 / 5)
        frond = sphere(f"palm_{i}_f_{k}", r=0.2, segs=10, rings=6, loc=(math.cos(ka) * 0.4, 2.5, math.sin(ka) * 0.4), parent=pp, mat=MAT_PALM_LEAF)
        frond.scale = (3.0, 0.2, 0.4)
        frond.rotation_euler = (math.radians(-20), -ka, 0)

# --- floating treasure chest ---------------------------------------------
chest_p = empty("chest", (5.5, 0.4, -4.0))
body = cube("chest_body", size=1.0, loc=(0, 0, 0), parent=chest_p, mat=MAT_CHEST)
body.scale = (0.7, 0.4, 0.5)
lid = cube("chest_lid", size=1.0, loc=(0, 0.35, -0.45), parent=chest_p, mat=MAT_CHEST)
lid.scale = (0.7, 0.05, 0.55)
lid.rotation_euler = (math.radians(-50), 0, 0)
# metal bands
for ay in [0.05, 0.30]:
    band = cube(f"chest_band_{ay}", size=1.0, loc=(0, ay, 0), parent=chest_p, mat=MAT_CHEST_METAL)
    band.scale = (0.72, 0.04, 0.52)
# gold inside
gold = cube("chest_gold", size=1.0, loc=(0, 0.20, 0), parent=chest_p, mat=MAT_GOLD)
gold.scale = (0.55, 0.10, 0.4)

# --- floating barrel ------------------------------------------------------
barrel_p = empty("barrel", (-6.0, 0.35, 4.0))
barrel = cone("barrel_body", r1=0.30, r2=0.30, depth=0.6, segs=14, loc=(0, 0, 0), parent=barrel_p, mat=MAT_BARREL)
# 3 metal bands
for ay in [-0.20, 0, 0.20]:
    band = cone(f"barrel_band_{ay}", r1=0.32, r2=0.32, depth=0.04, segs=14, loc=(0, ay, 0), parent=barrel_p, mat=MAT_CHEST_METAL)

# --- 3 mouettes flying ----------------------------------------------------
gulls = []
for i in range(3):
    a = i * (math.pi * 2 / 3) + 0.5
    r = 6.0
    bx = math.cos(a) * r
    bz = math.sin(a) * r
    by = 7.5 + random.uniform(-0.5, 0.5)
    bp = empty(f"gull_{i}", (bx, by, bz))
    body = sphere(f"gull_{i}_body", r=0.13, segs=10, rings=8, loc=(0, 0, 0), parent=bp, mat=MAT_GULL)
    body.scale = (1.4, 0.7, 1.0)
    for side, xx in (("L", -0.30), ("R", 0.30)):
        w = cube(f"gull_{i}_w_{side}", size=1.0, loc=(xx, 0, 0), parent=bp, mat=MAT_GULL)
        w.scale = (0.30, 0.02, 0.10)
    gulls.append((bp, a, r, by))

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

# ship pitch + roll + bob
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    pitch = math.radians(6) * math.sin(tt * math.pi * 2.5)
    roll = math.radians(4) * math.cos(tt * math.pi * 2.0)
    by = 0.8 + 0.25 * math.sin(tt * math.pi * 2.5)
    kf_loc(ship, f, (-1.0, by, 0))
    kf_rot(ship, f, (pitch, 0, roll))

# 8 waves ondulate
for w, wx, wz, ph in waves:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        dy = 0.3 + 0.35 * math.sin(tt * math.pi * 4.0 + ph)
        kf_loc(w, f, (wx, dy, wz))
        s = 1.0 + 0.15 * math.cos(tt * math.pi * 3.0 + ph)
        kf_scale(w, f, (2.2 * s, 0.4, 1.4 * s))

# foam dance
for fo, fx, fz, ph in foams:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        dy = 0.55 + 0.20 * math.sin(tt * math.pi * 5.0 + ph)
        s = 1.0 + 0.25 * math.sin(tt * math.pi * 6.0 + ph)
        kf_loc(fo, f, (fx, dy, fz))
        kf_scale(fo, f, (1.4 * s, 0.15, 0.8 * s))

# sails belly (scale Z pulse like wind filling)
for sail_p in sails:
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.10 * math.sin(tt * math.pi * 2.0)
        kf_scale(sail_p, f, (s, 1.0, 1.0))

# pirate flag wave
for j, seg in enumerate(flag_segs):
    base_x = seg.location.x
    base_y = seg.location.y
    base_z = seg.location.z
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        wave = math.sin(j * 0.4 + tt * math.pi * 6.0)
        dy = base_y + wave * 0.08
        dx = base_x + math.cos(j * 0.4 + tt * math.pi * 6.0) * 0.05
        kf_loc(seg, f, (dx, dy, base_z))
        kf_rot(seg, f, (0, wave * 0.20, 0))

# wheel rotate slowly
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    angle = math.radians(20) * math.sin(tt * math.pi * 2.0)
    kf_rot(wheel_p, f, (angle, 0, 0))

# 3 gulls fly
for bp, a0, r, by in gulls:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 2.0
        bx = math.cos(angle) * r
        bz = math.sin(angle) * r
        by_a = by + 0.4 * math.sin(tt * math.pi * 4.0 + a0)
        kf_loc(bp, f, (bx, by_a, bz))
        kf_rot(bp, f, (0, -angle + math.pi / 2, math.radians(18) * math.sin(tt * math.pi * 8.0)))

# chest bobs in water
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    by = 0.4 + 0.15 * math.sin(tt * math.pi * 3.0)
    tilt = math.radians(5) * math.sin(tt * math.pi * 4.0)
    kf_loc(chest_p, f, (5.5, by, -4.0))
    kf_rot(chest_p, f, (tilt, 0, tilt * 0.7))

# barrel bobs and rolls
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    by = 0.35 + 0.15 * math.sin(tt * math.pi * 3.5)
    roll = tt * math.pi * 1.5
    kf_loc(barrel_p, f, (-6.0, by, 4.0))
    kf_rot(barrel_p, f, (0, 0, roll))

# lanterns pulse
for i in range(2):
    light = bpy.data.objects.get(f"lantern_{i}_light")
    if light:
        for f in range(1, FRAMES + 1, 3):
            tt = (f - 1) / (FRAMES - 1)
            s = 1.0 + 0.20 * math.sin(tt * math.pi * 5.0 + i * 0.5)
            kf_scale(light, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_pirateship] wrote {OUT}")
