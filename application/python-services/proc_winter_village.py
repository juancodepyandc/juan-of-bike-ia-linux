"""
proc_winter_village.py — 136e procédural AuroraIA, Phase F++++.

Village hiver Noël nuit : 6 maisons toits enneigés avec fenêtres
chaudes émissives + église centrale avec clocher et cloche + grand
sapin Noël décoré avec 30 boules colorées + étoile sommet + 10
lampadaires + 20 personnages drift + bonhomme de neige (3 boules
+ chapeau + carotte + 2 bras + 2 yeux) + 4 traineaux + cheval
+ 3 sapins normaux + chemin + 8 cadeaux + ciel nuit étoilé + lune
+ 80 flocons.

Animation :
- 80 flocons tombent avec drift
- 10 lampadaires pulse
- étoile sapin pulse intense
- 30 boules sapin pulse différentiel
- 20 personnages drift + sway
- 1 traineau bouge le long du chemin
- cloche église pulse émission
- lune halo breathe

Sortie : output/3d/pbr_wintervillage_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_wintervillage_proc.glb"))

random.seed(0xCAFE99)

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
MAT_SKY = make_mat("sky_night", (0.05, 0.05, 0.15), roughness=1.0,
                    emi=(0.06, 0.08, 0.18), emi_strength=0.4)
MAT_STAR = make_mat("star", (1.0, 1.0, 0.95), roughness=0.0,
                      emi=(1.0, 1.0, 0.95), emi_strength=5.5)
MAT_MOON = make_mat("moon", (0.92, 0.92, 0.85), roughness=0.0,
                      emi=(0.92, 0.92, 0.85), emi_strength=7.0)
MAT_MOON_HALO = make_mat("moon_halo", (0.85, 0.85, 0.80), roughness=0.0, alpha=0.25,
                          emi=(0.85, 0.85, 0.78), emi_strength=2.5)
MAT_SNOW = make_mat("snow", (0.95, 0.96, 1.0), roughness=0.7,
                      emi=(0.55, 0.60, 0.70), emi_strength=0.3)
MAT_PATH_SNOW = make_mat("path_snow", (0.75, 0.78, 0.85), roughness=0.7,
                           emi=(0.40, 0.45, 0.55), emi_strength=0.25)
MAT_HOUSE_WALL = make_mat("house_wall", (0.55, 0.30, 0.15), roughness=0.7)
MAT_HOUSE_WALL_2 = make_mat("house_wall_2", (0.40, 0.25, 0.12), roughness=0.7)
MAT_HOUSE_WALL_3 = make_mat("house_wall_3", (0.65, 0.42, 0.22), roughness=0.7)
MAT_ROOF_SNOW = make_mat("roof_snow", (0.85, 0.88, 0.92), roughness=0.7,
                           emi=(0.40, 0.45, 0.55), emi_strength=0.2)
MAT_CHIMNEY = make_mat("chimney", (0.30, 0.25, 0.22), roughness=0.85)
MAT_WINDOW = make_mat("window", (1.0, 0.85, 0.50), roughness=0.0, alpha=0.85,
                        emi=(1.0, 0.85, 0.50), emi_strength=5.5)
MAT_DOOR = make_mat("door", (0.30, 0.18, 0.10), roughness=0.7)
MAT_CHURCH_WALL = make_mat("church_wall", (0.65, 0.55, 0.40), roughness=0.7)
MAT_CHURCH_ROOF = make_mat("church_roof", (0.25, 0.15, 0.10), roughness=0.7)
MAT_BELL = make_mat("bell", (1.0, 0.78, 0.20), metallic=0.95, roughness=0.20,
                     emi=(0.55, 0.40, 0.05), emi_strength=0.8)
MAT_CROSS = make_mat("cross", (0.95, 0.90, 0.80), roughness=0.5,
                       emi=(0.40, 0.35, 0.30), emi_strength=0.4)
MAT_FIR_TRUNK = make_mat("fir_trunk", (0.25, 0.15, 0.08), roughness=0.9)
MAT_FIR_LEAVES = make_mat("fir_leaves", (0.10, 0.30, 0.15), roughness=0.85)
MAT_TREE_BALL_R = make_mat("ball_r", (1.0, 0.10, 0.20), roughness=0.0,
                             emi=(1.0, 0.10, 0.20), emi_strength=4.0)
MAT_TREE_BALL_B = make_mat("ball_b", (0.20, 0.40, 1.0), roughness=0.0,
                             emi=(0.20, 0.40, 1.0), emi_strength=4.0)
MAT_TREE_BALL_G = make_mat("ball_g", (0.20, 1.0, 0.30), roughness=0.0,
                             emi=(0.20, 1.0, 0.30), emi_strength=4.0)
MAT_TREE_BALL_Y = make_mat("ball_y", (1.0, 0.95, 0.20), roughness=0.0,
                             emi=(1.0, 0.95, 0.20), emi_strength=4.0)
MAT_TREE_STAR = make_mat("tree_star", (1.0, 0.85, 0.30), roughness=0.0,
                           emi=(1.0, 0.85, 0.30), emi_strength=12.0)
MAT_LAMP_POST = make_mat("lamp_post", (0.10, 0.10, 0.10), roughness=0.6)
MAT_LAMP_LIGHT = make_mat("lamp_light", (1.0, 0.85, 0.50), roughness=0.0, alpha=0.85,
                            emi=(1.0, 0.85, 0.50), emi_strength=8.0)
MAT_SNOWMAN = make_mat("snowman", (0.98, 0.98, 1.0), roughness=0.6)
MAT_SNOWMAN_HAT = make_mat("snowman_hat", (0.10, 0.10, 0.10), roughness=0.5)
MAT_CARROT = make_mat("carrot", (1.0, 0.45, 0.10), roughness=0.5,
                        emi=(0.40, 0.15, 0.05), emi_strength=0.4)
MAT_COAL = make_mat("coal", (0.05, 0.05, 0.05), roughness=0.4)
MAT_SLED = make_mat("sled", (0.55, 0.25, 0.15), roughness=0.6)
MAT_SLED_METAL = make_mat("sled_metal", (0.55, 0.55, 0.60), metallic=0.85, roughness=0.3)
MAT_HORSE_BROWN = make_mat("horse_brown", (0.55, 0.30, 0.15), roughness=0.7)
MAT_HORSE_MANE = make_mat("horse_mane", (0.20, 0.15, 0.10), roughness=0.85)
MAT_PERSON_BODY = make_mat("person_body", (0.30, 0.20, 0.15), roughness=0.7)
MAT_PERSON_HAT = make_mat("person_hat", (0.85, 0.20, 0.20), roughness=0.6,
                            emi=(0.30, 0.05, 0.08), emi_strength=0.3)
person_coats = [
    make_mat("coat_r", (0.65, 0.15, 0.10), roughness=0.7),
    make_mat("coat_g", (0.15, 0.45, 0.20), roughness=0.7),
    make_mat("coat_b", (0.15, 0.25, 0.55), roughness=0.7),
    make_mat("coat_y", (0.75, 0.55, 0.20), roughness=0.7),
]
MAT_PERSON_HEAD = make_mat("person_head", (0.95, 0.75, 0.55), roughness=0.7)
MAT_GIFT_R = make_mat("gift_r", (0.95, 0.15, 0.15), roughness=0.6,
                        emi=(0.40, 0.05, 0.05), emi_strength=0.3)
MAT_GIFT_G = make_mat("gift_g", (0.15, 0.65, 0.20), roughness=0.6,
                        emi=(0.05, 0.30, 0.10), emi_strength=0.3)
MAT_GIFT_B = make_mat("gift_b", (0.20, 0.30, 0.85), roughness=0.6,
                        emi=(0.10, 0.15, 0.40), emi_strength=0.3)
MAT_GIFT_GOLD = make_mat("gift_gold", (1.0, 0.85, 0.20), metallic=0.7, roughness=0.4,
                           emi=(0.45, 0.40, 0.05), emi_strength=0.5)
MAT_FLAKE = make_mat("flake", (0.95, 0.95, 1.0), roughness=0.0, alpha=0.85,
                       emi=(0.95, 0.95, 1.0), emi_strength=2.5)

# --- backdrop : night sky --------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 18, 6), mat=MAT_SKY)
sky.scale = (40, 0.1, 14)

# 70 stars
for i in range(70):
    x = random.uniform(-15, 15)
    z = random.uniform(2, 12)
    y = random.uniform(15, 16)
    r = random.uniform(0.05, 0.10)
    s = sphere(f"star_{i}", r=r, segs=8, rings=6, loc=(x, y, z), mat=MAT_STAR)
    s["_phase"] = (i * 13) % 47

# moon + halo
moon_p = empty("moon_p", (8.0, 13.5, 9.0))
moon = sphere("moon", r=1.0, segs=22, rings=16, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON)
moon_halo = sphere("moon_halo", r=2.0, segs=20, rings=14, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON_HALO)

# --- snowy ground ----------------------------------------------------------
ground = cube("ground", size=1.0, loc=(0, -0.05, 0), mat=MAT_SNOW)
ground.scale = (40, 0.1, 28)

# winding path through village
path_stones = []
for i in range(20):
    px = -10 + i * 1.0
    pz = math.sin(i * 0.5) * 0.8
    p = cube(f"path_{i}", size=1.0, loc=(px, 0.02, pz), mat=MAT_PATH_SNOW)
    p.scale = (0.8, 0.05, 0.6)
    path_stones.append(p)

# --- église centrale -----------------------------------------------------
church_p = empty("church", (0, 0, 5.5))
# main body
body = cube("church_body", size=1.0, loc=(0, 1.5, 0), parent=church_p, mat=MAT_CHURCH_WALL)
body.scale = (3.5, 1.5, 2.0)
# 4 arched windows (warm)
for i in range(4):
    wx = -1.2 + i * 0.8
    w = cube(f"church_w_{i}", size=1.0, loc=(wx, 1.5, 1.05), parent=church_p, mat=MAT_WINDOW)
    w.scale = (0.20, 0.5, 0.05)
# double door
for side, dx in [("L", -0.20), ("R", 0.20)]:
    door = cube(f"church_door_{side}", size=1.0, loc=(dx, 0.75, 1.05), parent=church_p, mat=MAT_DOOR)
    door.scale = (0.15, 0.7, 0.05)
# roof (steep pitched)
roof = cone("church_roof", r1=2.8, r2=0.3, depth=2.0, segs=4, loc=(0, 4.0, 0), parent=church_p, mat=MAT_CHURCH_ROOF)
roof.rotation_euler = (math.radians(90), 0, math.radians(45))
# snow on roof
roof_snow = cone("church_roof_snow", r1=2.5, r2=0.2, depth=0.15, segs=4, loc=(0, 4.2, 0), parent=church_p, mat=MAT_ROOF_SNOW)
roof_snow.rotation_euler = (math.radians(90), 0, math.radians(45))
# bell tower (above roof)
tower = cube("church_tower", size=1.0, loc=(0, 5.5, 0), parent=church_p, mat=MAT_CHURCH_WALL)
tower.scale = (0.7, 1.5, 0.7)
# bell tower openings (4 arches showing the bell)
for side, dx, dz in [("F", 0, 0.38), ("B", 0, -0.38), ("L", -0.38, 0), ("R", 0.38, 0)]:
    opening = cube(f"church_to_{side}", size=1.0, loc=(dx, 5.5, dz), parent=church_p, mat=MAT_WINDOW)
    opening.scale = (0.10 if abs(dx) > 0 else 0.5, 0.6, 0.10 if abs(dz) > 0 else 0.5)
# bell inside (visible)
bell = cone("church_bell", r1=0.20, r2=0.18, depth=0.30, segs=14, loc=(0, 5.5, 0), parent=church_p, mat=MAT_BELL)
bell.rotation_euler = (math.radians(90), 0, 0)
# spire
spire = cone("church_spire", r1=0.5, r2=0.05, depth=1.5, segs=4, loc=(0, 7.0, 0), parent=church_p, mat=MAT_CHURCH_ROOF)
spire.rotation_euler = (math.radians(90), 0, math.radians(45))
# cross on top
cross_v = cube("cross_v", size=1.0, loc=(0, 8.2, 0), parent=church_p, mat=MAT_CROSS)
cross_v.scale = (0.06, 0.5, 0.06)
cross_h = cube("cross_h", size=1.0, loc=(0, 8.3, 0), parent=church_p, mat=MAT_CROSS)
cross_h.scale = (0.25, 0.06, 0.06)

# --- 6 maisons --------------------------------------------------------
def make_house(name, x, z, wall_mat, rot=0):
    p = empty(name, (x, 0, z))
    p.rotation_euler = (0, rot, 0)
    # body
    body = cube(f"{name}_body", size=1.0, loc=(0, 0.9, 0), parent=p, mat=wall_mat)
    body.scale = (1.4, 0.9, 1.2)
    # roof
    roof = cone(f"{name}_roof", r1=1.5, r2=0.05, depth=0.9, segs=4, loc=(0, 1.8 + 0.45, 0), parent=p, mat=MAT_CHURCH_ROOF)
    roof.rotation_euler = (math.radians(90), 0, math.radians(45))
    # snow on roof
    snow = cone(f"{name}_snow", r1=1.3, r2=0.05, depth=0.10, segs=4, loc=(0, 1.8 + 0.55, 0), parent=p, mat=MAT_ROOF_SNOW)
    snow.rotation_euler = (math.radians(90), 0, math.radians(45))
    # chimney
    chim = cube(f"{name}_chim", size=1.0, loc=(0.5, 2.3, -0.4), parent=p, mat=MAT_CHIMNEY)
    chim.scale = (0.18, 0.5, 0.18)
    # 2 windows (front)
    for k, dx in enumerate([-0.40, 0.40]):
        w = cube(f"{name}_w_{k}", size=1.0, loc=(dx, 1.0, 0.62), parent=p, mat=MAT_WINDOW)
        w.scale = (0.30, 0.30, 0.04)
    # door (centered)
    door = cube(f"{name}_door", size=1.0, loc=(0, 0.7, 0.62), parent=p, mat=MAT_DOOR)
    door.scale = (0.25, 0.55, 0.04)
    return p

house_data = [
    (-7, -2, MAT_HOUSE_WALL, math.radians(15)),
    (-4, -3, MAT_HOUSE_WALL_2, math.radians(-10)),
    (-2, 0, MAT_HOUSE_WALL_3, math.radians(5)),
    (4, -2, MAT_HOUSE_WALL_2, math.radians(20)),
    (7, -3, MAT_HOUSE_WALL, math.radians(-15)),
    (3, 1, MAT_HOUSE_WALL_3, math.radians(-25)),
]
for i, (hx, hz, mat, rot) in enumerate(house_data):
    make_house(f"house_{i}", hx, hz, mat, rot)

# --- grand sapin de Noël décoré ----------------------------------------
xmas_tree_p = empty("xmas_tree", (-5.5, 0, 1.0))
# trunk
trunk = cone("xmas_trunk", r1=0.20, r2=0.18, depth=0.8, segs=8, loc=(0, 0.4, 0), parent=xmas_tree_p, mat=MAT_FIR_TRUNK)
trunk.rotation_euler = (math.radians(90), 0, 0)
# 5 layers
for j in range(5):
    h = 0.8 + j * 0.7
    r = 1.4 - j * 0.20
    layer = cone(f"xmas_l_{j}", r1=r, r2=r * 0.2, depth=0.8, segs=12, loc=(0, h, 0), parent=xmas_tree_p, mat=MAT_FIR_LEAVES)
    layer.rotation_euler = (math.radians(90), 0, 0)

# 30 boules décoratives (alternating colors)
tree_balls = []
ball_colors = [MAT_TREE_BALL_R, MAT_TREE_BALL_B, MAT_TREE_BALL_G, MAT_TREE_BALL_Y]
for i in range(30):
    a = random.uniform(0, math.pi * 2)
    h = random.uniform(1.0, 4.0)
    r = 1.4 - (h - 0.8) * 0.20 + 0.10
    bx = math.cos(a) * r
    bz = math.sin(a) * r
    mat = ball_colors[i % 4]
    b = sphere(f"xmas_ball_{i}", r=0.08, segs=10, rings=8, loc=(bx, h, bz), parent=xmas_tree_p, mat=mat)
    tree_balls.append((b, i))

# star on top
tree_star = sphere("xmas_star", r=0.22, segs=14, rings=10, loc=(0, 4.5, 0), parent=xmas_tree_p, mat=MAT_TREE_STAR)
tree_star.scale = (1.0, 1.2, 0.5)

# --- 3 sapins normaux ------------------------------------------------
for i, (fx, fz) in enumerate([(-9, 4), (9, 4), (-9, -6)]):
    fp = empty(f"fir_{i}", (fx, 0, fz))
    trunk = cone(f"fir_{i}_trunk", r1=0.16, r2=0.12, depth=1.0, segs=8, loc=(0, 0.5, 0), parent=fp, mat=MAT_FIR_TRUNK)
    trunk.rotation_euler = (math.radians(90), 0, 0)
    for j in range(4):
        h = 1.0 + j * 0.55
        r = 0.8 - j * 0.18
        layer = cone(f"fir_{i}_l_{j}", r1=r, r2=r * 0.3, depth=0.55, segs=10, loc=(0, h, 0), parent=fp, mat=MAT_FIR_LEAVES)
        layer.rotation_euler = (math.radians(90), 0, 0)
        # snow on layer
        snow = cone(f"fir_{i}_s_{j}", r1=r * 0.85, r2=r * 0.25, depth=0.08, segs=10, loc=(0, h + 0.20, 0), parent=fp, mat=MAT_ROOF_SNOW)
        snow.rotation_euler = (math.radians(90), 0, 0)

# --- 10 lampadaires émissifs ----------------------------------------
lantern_lights = []
lamp_positions = [(-9, -1), (-5, -1), (-1, -1), (3, -1), (7, -1), (-7, 3), (-3, 4), (1, 5), (5, 4), (8, 2)]
for i, (lx, lz) in enumerate(lamp_positions):
    lp = empty(f"lamp_{i}", (lx, 0, lz))
    # post
    post = cone(f"lamp_{i}_post", r1=0.06, r2=0.05, depth=2.5, segs=6, loc=(0, 1.25, 0), parent=lp, mat=MAT_LAMP_POST)
    post.rotation_euler = (math.radians(90), 0, 0)
    # crossbar (small)
    crossbar = cube(f"lamp_{i}_cb", size=1.0, loc=(0, 2.5, 0), parent=lp, mat=MAT_LAMP_POST)
    crossbar.scale = (0.25, 0.04, 0.04)
    # light orb
    light = sphere(f"lamp_{i}_light", r=0.12, segs=10, rings=8, loc=(0, 2.5, 0), parent=lp, mat=MAT_LAMP_LIGHT)
    # cap
    cap = cone(f"lamp_{i}_cap", r1=0.16, r2=0.0, depth=0.10, segs=6, loc=(0, 2.65, 0), parent=lp, mat=MAT_LAMP_POST)
    cap.rotation_euler = (math.radians(90), 0, 0)
    lantern_lights.append(light)

# --- bonhomme de neige ------------------------------------------------
snowman_p = empty("snowman", (1.0, 0, 3.0))
# 3 boules
for j, (sy, sr) in enumerate([(0.45, 0.45), (1.15, 0.35), (1.70, 0.25)]):
    b = sphere(f"snow_b_{j}", r=sr, segs=14, rings=10, loc=(0, sy, 0), parent=snowman_p, mat=MAT_SNOWMAN)
# 2 eyes coal
for side, dz in [("L", -0.10), ("R", 0.10)]:
    eye = sphere(f"snow_eye_{side}", r=0.04, segs=8, rings=6, loc=(0.18, 1.78, dz), parent=snowman_p, mat=MAT_COAL)
# carrot nose
nose = cone("snow_nose", r1=0.05, r2=0.0, depth=0.20, segs=6, loc=(0.30, 1.68, 0), parent=snowman_p, mat=MAT_CARROT)
nose.rotation_euler = (0, math.radians(90), 0)
# mouth (5 coal dots curve)
for k in range(5):
    a = math.radians(-30 + k * 15)
    mx = math.cos(a) * 0.12 + 0.20
    my = math.sin(a) * 0.05 + 1.58
    m = sphere(f"snow_mouth_{k}", r=0.020, segs=6, rings=4, loc=(mx, my, 0), parent=snowman_p, mat=MAT_COAL)
# hat (cone + brim)
hat_brim = cone("snow_brim", r1=0.32, r2=0.32, depth=0.05, segs=14, loc=(0, 2.0, 0), parent=snowman_p, mat=MAT_SNOWMAN_HAT)
hat_brim.rotation_euler = (math.radians(90), 0, 0)
hat = cone("snow_hat", r1=0.22, r2=0.22, depth=0.45, segs=14, loc=(0, 2.25, 0), parent=snowman_p, mat=MAT_SNOWMAN_HAT)
hat.rotation_euler = (math.radians(90), 0, 0)
# 2 arms (sticks)
for side, dz in [("L", 0.40), ("R", -0.40)]:
    arm = cone(f"snow_arm_{side}", r1=0.04, r2=0.02, depth=0.5, segs=6, loc=(0, 1.20, dz), parent=snowman_p, mat=MAT_FIR_TRUNK)
    arm.rotation_euler = (0, 0, math.radians(80 if side == "L" else -80))
# 3 coal buttons on middle body
for j in range(3):
    bt = sphere(f"snow_btn_{j}", r=0.03, segs=8, rings=6, loc=(0.34, 1.20 + j * 0.08 - 0.10, 0), parent=snowman_p, mat=MAT_COAL)

# --- 4 traineaux -------------------------------------------------------
def make_sled(name, x, z, rot=0):
    p = empty(name, (x, 0, z))
    p.rotation_euler = (0, rot, 0)
    # body
    body = cube(f"{name}_body", size=1.0, loc=(0, 0.20, 0), parent=p, mat=MAT_SLED)
    body.scale = (0.6, 0.06, 0.25)
    # 2 runners
    for side, dz in [("L", 0.18), ("R", -0.18)]:
        rn = cube(f"{name}_rn_{side}", size=1.0, loc=(0, 0.08, dz), parent=p, mat=MAT_SLED_METAL)
        rn.scale = (0.8, 0.04, 0.04)
    # pull rope
    rope = cube(f"{name}_rope", size=1.0, loc=(0.45, 0.22, 0), parent=p, mat=MAT_FIR_TRUNK)
    rope.scale = (0.20, 0.02, 0.02)
    return p

sleds = []
sled_data = [
    (-3.5, 2.0, math.radians(45)),
    (5.5, 3.5, math.radians(-30)),
    (-8.0, 2.5, math.radians(10)),
    (6.0, 0.5, math.radians(-50)),
]
for i, (sx, sz, srot) in enumerate(sled_data):
    s = make_sled(f"sled_{i}", sx, sz, srot)
    sleds.append(s)

# 1 sled is moving along the path
moving_sled = sleds[0]

# --- 1 cheval ----------------------------------------------------------
horse_p = empty("horse", (-2.5, 0, 1.8))
horse_p.rotation_euler = (0, math.radians(40), 0)
body = sphere("horse_body", r=0.30, segs=14, rings=10, loc=(0, 0.7, 0), parent=horse_p, mat=MAT_HORSE_BROWN)
body.scale = (1.7, 0.8, 0.7)
neck = cone("horse_neck", r1=0.15, r2=0.12, depth=0.5, segs=8, loc=(0.45, 1.05, 0), parent=horse_p, mat=MAT_HORSE_BROWN)
neck.rotation_euler = (0, 0, math.radians(-50))
head = sphere("horse_head", r=0.18, segs=12, rings=10, loc=(0.75, 1.35, 0), parent=horse_p, mat=MAT_HORSE_BROWN)
head.scale = (1.4, 0.9, 0.8)
# 2 ears
for side, dz in [("L", 0.10), ("R", -0.10)]:
    ear = cone(f"horse_ear_{side}", r1=0.04, r2=0.0, depth=0.10, segs=6, loc=(0.72, 1.50, dz), parent=horse_p, mat=MAT_HORSE_BROWN)
    ear.rotation_euler = (math.radians(-15), 0, 0)
# mane
for k in range(4):
    mp = sphere(f"horse_mane_{k}", r=0.05, segs=8, rings=6, loc=(0.45 + k * 0.06, 1.20 + k * 0.05, 0), parent=horse_p, mat=MAT_HORSE_MANE)
# 4 legs
for i, (lx, lz) in enumerate([(0.45, 0.20), (0.45, -0.20), (-0.45, 0.20), (-0.45, -0.20)]):
    leg = cube(f"horse_leg_{i}", size=1.0, loc=(lx, 0.35, lz), parent=horse_p, mat=MAT_HORSE_BROWN)
    leg.scale = (0.10, 0.7, 0.10)
# tail
tail = cone("horse_tail", r1=0.06, r2=0.02, depth=0.30, segs=6, loc=(-0.55, 0.75, 0), parent=horse_p, mat=MAT_HORSE_MANE)
tail.rotation_euler = (0, 0, math.radians(110))

# --- 20 personnages avec chapeaux ----------------------------------
people = []
for i in range(20):
    a = i * (math.pi * 2 / 20) + 0.2
    r = 6.5 + (i % 3) * 0.6
    px = math.cos(a) * r + (i % 3 - 1) * 1.5
    pz = math.sin(a) * r * 0.6 + (i % 4 - 1) * 0.5
    pp = empty(f"person_{i}", (px, 0, pz))
    # body
    body = cube(f"person_{i}_body", size=1.0, loc=(0, 0.55, 0), parent=pp, mat=person_coats[i % 4])
    body.scale = (0.18, 0.55, 0.10)
    # head
    head = sphere(f"person_{i}_head", r=0.12, segs=10, rings=8, loc=(0, 1.10, 0), parent=pp, mat=MAT_PERSON_HEAD)
    # hat (red Santa-style cone)
    hat = cone(f"person_{i}_hat", r1=0.12, r2=0.0, depth=0.20, segs=8, loc=(0, 1.30, 0), parent=pp, mat=MAT_PERSON_HAT)
    hat.rotation_euler = (math.radians(90), 0, 0)
    # 2 legs
    for side, dx in [("L", -0.07), ("R", 0.07)]:
        leg = cube(f"person_{i}_l_{side}", size=1.0, loc=(dx, 0.15, 0), parent=pp, mat=MAT_PERSON_BODY)
        leg.scale = (0.07, 0.30, 0.10)
    # 2 arms
    for side, dx in [("L", -0.20), ("R", 0.20)]:
        arm = cube(f"person_{i}_a_{side}", size=1.0, loc=(dx, 0.55, 0), parent=pp, mat=person_coats[i % 4])
        arm.scale = (0.07, 0.30, 0.10)
    people.append((pp, i))

# --- 8 cadeaux empilés sous le sapin -------------------------------
gift_mats = [MAT_GIFT_R, MAT_GIFT_G, MAT_GIFT_B, MAT_GIFT_GOLD]
for i in range(8):
    # arrangement around xmas tree
    a = i * (math.pi * 2 / 8) + 0.5
    gx = -5.5 + math.cos(a) * 2.0
    gz = 1.0 + math.sin(a) * 2.0
    gp = empty(f"gift_{i}", (gx, 0, gz))
    mat = gift_mats[i % 4]
    body = cube(f"gift_{i}_body", size=1.0, loc=(0, 0.2, 0), parent=gp, mat=mat)
    body.scale = (0.30 + random.uniform(0, 0.10), 0.20 + random.uniform(0, 0.10), 0.25 + random.uniform(0, 0.10))
    # ribbon (cross of cubes on top)
    rb1 = cube(f"gift_{i}_rib1", size=1.0, loc=(0, 0.32, 0), parent=gp, mat=MAT_GIFT_GOLD)
    rb1.scale = (0.06, 0.06, 0.30)
    rb2 = cube(f"gift_{i}_rib2", size=1.0, loc=(0, 0.32, 0), parent=gp, mat=MAT_GIFT_GOLD)
    rb2.scale = (0.30, 0.06, 0.06)
    # bow on top
    bow = sphere(f"gift_{i}_bow", r=0.06, segs=8, rings=6, loc=(0, 0.40, 0), parent=gp, mat=MAT_GIFT_GOLD)

# --- 80 flocons de neige -------------------------------------------
flakes = []
for i in range(80):
    fx = random.uniform(-15, 15)
    fz = random.uniform(-10, 10)
    fy = random.uniform(3, 13)
    fk = sphere(f"flake_{i}", r=random.uniform(0.05, 0.10), segs=6, rings=4, loc=(fx, fy, fz), mat=MAT_FLAKE)
    flakes.append((fk, fx, fz, fy, random.uniform(0, 1)))

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

# 80 flakes fall with drift
for fk, fx, fz, fy_init, ph in flakes:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        local = (tt + ph) % 1.0
        fy = fy_init - local * 12.0
        if fy < 0.1:
            fy = 0.1
        drift_x = math.sin(local * math.pi * 3.0 + ph * 5.0) * 0.3
        kf_loc(fk, f, (fx + drift_x, fy, fz))

# 10 lampadaires pulse
for i, light in enumerate(lantern_lights):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(light, f, (s, s, s))

# tree star pulse intense
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.30 * math.sin(tt * math.pi * 6.0)
    kf_scale(tree_star, f, (s, 1.2 * s, 0.5 * s))

# 30 tree balls pulse différentiel
for ball, idx in tree_balls:
    phase = idx * 0.3
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.18 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(ball, f, (s, s, s))

# 20 personnages drift + sway
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

# moving sled along path
sled_base_x = moving_sled.location.x
sled_base_z = moving_sled.location.z
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    dx = sled_base_x + math.sin(tt * math.pi * 2.0) * 1.5
    dz = sled_base_z + math.cos(tt * math.pi * 2.0) * 0.8
    kf_loc(moving_sled, f, (dx, 0, dz))

# church bell pulse
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.15 * math.sin(tt * math.pi * 4.0)
    kf_scale(bell, f, (s, s, s))

# moon halo breathe
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.12 * math.sin(tt * math.pi * 3.0)
    kf_scale(moon_halo, f, (s, s, s))

# stars twinkle
for i in range(70):
    star = bpy.data.objects.get(f"star_{i}")
    if not star:
        continue
    phase = star["_phase"]
    for f in range(1, FRAMES + 1, 6):
        tt = (f - 1) / (FRAMES - 1)
        local = (math.sin(tt * math.pi * 6.0 + phase * 0.13) + 1) * 0.5
        s = 0.7 + 0.5 * local
        kf_scale(star, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_wintervillage] wrote {OUT}")
