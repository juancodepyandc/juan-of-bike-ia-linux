"""
proc_train_station.py — 125e procédural AuroraIA, Phase F++++.

Gare rétro avec locomotive vapeur : grande gare avec horloge centrale
+ toit en arc + 2 plateformes + locomotive vapeur (chassis + cheminée
+ 4 grandes roues + chaudière) + 3 wagons (passagers/marchandises/
citerne) + rails (sleepers + rails) + 4 lampadaires émissifs + tableau
d'affichage + 8 passagers silhouettes + 6 valises + ciel matin
+ signalisation rouge/vert + arbres latéraux.

Animation :
- locomotive avance lentement le long des rails
- 4 roues locomotive tournent (rapides)
- 6 roues wagons tournent
- cheminée fumée monte (10 puffs)
- 4 lampadaires : pulse
- horloge pendule oscille
- signalisation : alternance rouge/vert

Sortie : output/3d/pbr_trainstation_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_trainstation_proc.glb"))

random.seed(0xFAB12E)

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
MAT_SKY = make_mat("sky_morning", (0.75, 0.85, 0.95), roughness=1.0,
                    emi=(0.55, 0.70, 0.85), emi_strength=0.5)
MAT_CLOUD = make_mat("cloud", (0.95, 0.96, 1.0), roughness=1.0, alpha=0.85,
                      emi=(0.85, 0.88, 0.95), emi_strength=0.3)
MAT_GROUND = make_mat("ground", (0.30, 0.30, 0.30), roughness=0.9)
MAT_PLATFORM = make_mat("platform", (0.55, 0.45, 0.35), roughness=0.85)
MAT_RAIL = make_mat("rail", (0.30, 0.30, 0.32), metallic=0.85, roughness=0.3)
MAT_SLEEPER = make_mat("sleeper", (0.25, 0.15, 0.08), roughness=0.9)
MAT_STATION_WALL = make_mat("station_wall", (0.65, 0.50, 0.35), roughness=0.7,
                              emi=(0.20, 0.15, 0.08), emi_strength=0.15)
MAT_STATION_ROOF = make_mat("station_roof", (0.40, 0.25, 0.15), roughness=0.7)
MAT_STATION_TRIM = make_mat("station_trim", (0.85, 0.70, 0.40), metallic=0.5, roughness=0.4,
                              emi=(0.30, 0.25, 0.10), emi_strength=0.3)
MAT_CLOCK_FACE = make_mat("clock_face", (0.95, 0.92, 0.85), roughness=0.5,
                            emi=(0.85, 0.80, 0.70), emi_strength=1.5)
MAT_CLOCK_HAND = make_mat("clock_hand", (0.10, 0.08, 0.05), roughness=0.4)
MAT_LOCO_BLACK = make_mat("loco_black", (0.05, 0.05, 0.05), roughness=0.5)
MAT_LOCO_RED = make_mat("loco_red", (0.65, 0.10, 0.08), roughness=0.5,
                          emi=(0.30, 0.05, 0.05), emi_strength=0.3)
MAT_LOCO_GOLD = make_mat("loco_gold", (1.0, 0.78, 0.20), metallic=0.95, roughness=0.20,
                           emi=(0.50, 0.40, 0.10), emi_strength=0.5)
MAT_LOCO_CHIMNEY = make_mat("loco_chimney", (0.15, 0.12, 0.10), roughness=0.85)
MAT_SMOKE = make_mat(
    "smoke", (0.55, 0.55, 0.58), roughness=1.0, alpha=0.65,
    emi=(0.35, 0.35, 0.38), emi_strength=0.5,
)
MAT_STEAM = make_mat(
    "steam", (0.92, 0.94, 0.97), roughness=1.0, alpha=0.55,
    emi=(0.85, 0.88, 0.95), emi_strength=0.8,
)
MAT_HEADLIGHT = make_mat(
    "headlight", (1.0, 0.95, 0.70), roughness=0.0,
    emi=(1.0, 0.95, 0.70), emi_strength=8.0,
)
MAT_WHEEL = make_mat("wheel", (0.20, 0.15, 0.12), metallic=0.5, roughness=0.5)
MAT_WHEEL_RIM = make_mat("wheel_rim", (0.55, 0.45, 0.35), metallic=0.7, roughness=0.4)
MAT_WAGON_GREEN = make_mat("wagon_green", (0.15, 0.45, 0.20), roughness=0.6,
                             emi=(0.05, 0.20, 0.08), emi_strength=0.3)
MAT_WAGON_BROWN = make_mat("wagon_brown", (0.45, 0.30, 0.15), roughness=0.7)
MAT_WAGON_TANK = make_mat("wagon_tank", (0.45, 0.45, 0.50), metallic=0.7, roughness=0.4)
MAT_WAGON_WINDOW = make_mat(
    "wagon_window", (1.0, 0.85, 0.55), roughness=0.0, alpha=0.85,
    emi=(1.0, 0.85, 0.55), emi_strength=4.5,
)
MAT_LAMP_POST = make_mat("lamp_post", (0.10, 0.10, 0.10), roughness=0.7)
MAT_LAMP_LIGHT = make_mat("lamp_light", (1.0, 0.85, 0.50), roughness=0.0, alpha=0.85,
                            emi=(1.0, 0.85, 0.50), emi_strength=7.5)
MAT_SIGNAL_RED = make_mat("signal_red", (1.0, 0.10, 0.10), roughness=0.0,
                            emi=(1.0, 0.10, 0.10), emi_strength=6.0)
MAT_SIGNAL_GREEN = make_mat("signal_green", (0.10, 1.0, 0.30), roughness=0.0,
                              emi=(0.10, 1.0, 0.30), emi_strength=6.0)
MAT_BOARD = make_mat("board", (0.10, 0.10, 0.12), roughness=0.6,
                       emi=(0.05, 0.05, 0.08), emi_strength=0.4)
MAT_BOARD_TEXT = make_mat("board_text", (0.30, 1.0, 0.60), roughness=0.0,
                            emi=(0.30, 1.0, 0.50), emi_strength=4.5)
MAT_PERSON = make_mat("person", (0.15, 0.12, 0.10), roughness=0.7)
MAT_PERSON_COAT_R = make_mat("coat_r", (0.55, 0.10, 0.10), roughness=0.7)
MAT_PERSON_COAT_B = make_mat("coat_b", (0.10, 0.20, 0.55), roughness=0.7)
MAT_LUGGAGE = make_mat("luggage", (0.45, 0.30, 0.15), roughness=0.7)
MAT_LUGGAGE_HANDLE = make_mat("luggage_h", (0.70, 0.55, 0.20), metallic=0.5, roughness=0.4)
MAT_TREE_TRUNK = make_mat("tree_trunk", (0.30, 0.20, 0.12), roughness=0.9)
MAT_TREE_LEAVES = make_mat("tree_leaves", (0.15, 0.45, 0.18), roughness=0.85)

# --- backdrop ---------------------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 18, 6), mat=MAT_SKY)
sky.scale = (36, 0.1, 14)

# 6 clouds
for i in range(6):
    cx = -15 + i * 5 + random.uniform(-1, 1)
    cz = 10 + random.uniform(-1, 1)
    cy = 13 + random.uniform(-0.5, 0.5)
    cl = sphere(f"cloud_{i}", r=random.uniform(0.9, 1.5), segs=14, rings=10, loc=(cx, cy, cz), mat=MAT_CLOUD)
    cl.scale = (1.6, 0.5, 1.1)

# ground
ground = cube("ground", size=1.0, loc=(0, -0.05, 0), mat=MAT_GROUND)
ground.scale = (40, 0.1, 24)

# --- 2 plateformes parallèles ----------------------------------------------
for side, dz, mat in [("F", 2.5, MAT_PLATFORM), ("B", -2.5, MAT_PLATFORM)]:
    plat = cube(f"platform_{side}", size=1.0, loc=(0, 0.20, dz), mat=mat)
    plat.scale = (32, 0.35, 1.5)
# platform edge stripe (lighter for visibility)
for side, dz in [("F", 1.95), ("B", -1.95)]:
    edge = cube(f"plat_edge_{side}", size=1.0, loc=(0, 0.40, dz), mat=MAT_STATION_TRIM)
    edge.scale = (32, 0.05, 0.10)

# --- rails (2 sets) --------------------------------------------------------
# left rail set
for rail_offset in [-0.7, 0.7]:
    rail = cube(f"rail_{rail_offset}", size=1.0, loc=(0, 0.10, rail_offset), mat=MAT_RAIL)
    rail.scale = (35, 0.05, 0.08)
# 30 sleepers (railroad ties)
for i in range(30):
    sx = -15 + i * 1.0
    sl = cube(f"sleeper_{i}", size=1.0, loc=(sx, 0.05, 0), mat=MAT_SLEEPER)
    sl.scale = (0.7, 0.05, 1.7)

# --- station building (centered behind platform F) -------------------------
station = empty("station", (-2.0, 0, 5.5))
# main wall
wall = cube("station_wall", size=1.0, loc=(0, 1.5, 0), parent=station, mat=MAT_STATION_WALL)
wall.scale = (6.0, 1.5, 0.4)
# 5 arched windows on the wall (cubes)
for i in range(5):
    wx = -2.0 + i * 1.0
    win = cube(f"station_win_{i}", size=1.0, loc=(wx, 1.8, 0.21), parent=station, mat=MAT_WAGON_WINDOW)
    win.scale = (0.30, 0.55, 0.05)
# main entrance (large door)
door = cube("station_door", size=1.0, loc=(2.5, 0.85, 0.21), parent=station, mat=MAT_STATION_ROOF)
door.scale = (0.30, 0.85, 0.06)
# arched roof
roof = cone("station_roof", r1=3.5, r2=0.5, depth=0.8, segs=4, loc=(0, 3.2, 0), parent=station, mat=MAT_STATION_ROOF)
roof.rotation_euler = (math.radians(90), 0, math.radians(45))
roof.scale = (2.5, 1.0, 0.5)

# clock tower (above center)
tower = cube("clock_tower", size=1.0, loc=(0, 4.0, 0), parent=station, mat=MAT_STATION_WALL)
tower.scale = (0.6, 1.4, 0.4)
# clock face (round disc)
clock_face = cone("clock_face", r1=0.50, r2=0.50, depth=0.05, segs=20, loc=(0, 4.3, 0.20), parent=station, mat=MAT_CLOCK_FACE)
clock_face.rotation_euler = (math.radians(90), 0, 0)
# 12 hour marks (small dark dots)
for i in range(12):
    a = i * (math.pi * 2 / 12) - math.pi / 2
    mx = math.cos(a) * 0.42
    my = math.sin(a) * 0.42 + 4.3
    mark = cube(f"clock_mark_{i}", size=1.0, loc=(mx, my, 0.22), parent=station, mat=MAT_CLOCK_HAND)
    mark.scale = (0.04, 0.04, 0.02)
# 2 hands (pendule = clock hands actually)
hand_hour = cube("clock_hand_hour", size=1.0, loc=(0, 4.3, 0.23), parent=station, mat=MAT_CLOCK_HAND)
hand_hour.scale = (0.04, 0.25, 0.02)
hand_min_p = empty("clock_hand_min_p", (0, 4.3, 0.24), parent=station)
hand_min = cube("clock_hand_min", size=1.0, loc=(0, 0.18, 0), parent=hand_min_p, mat=MAT_CLOCK_HAND)
hand_min.scale = (0.025, 0.35, 0.02)
# pendulum (long swinging bar below clock)
pendulum_p = empty("pendulum_p", (0, 3.0, 0.20), parent=station)
pendulum = cube("pendulum", size=1.0, loc=(0, -0.4, 0), parent=pendulum_p, mat=MAT_CLOCK_HAND)
pendulum.scale = (0.04, 0.7, 0.04)
# pendulum bob
bob = sphere("pendulum_bob", r=0.12, segs=12, rings=8, loc=(0, -0.85, 0), parent=pendulum_p, mat=MAT_LOCO_GOLD)

# --- locomotive (positioned on the tracks) --------------------------------
loco_p = empty("loco", (-5.0, 0, 0))
# main boiler (long cylinder)
boiler = cone("boiler", r1=0.55, r2=0.55, depth=2.5, segs=14, loc=(0, 0.95, 0), parent=loco_p, mat=MAT_LOCO_BLACK)
boiler.rotation_euler = (0, math.radians(90), 0)
# front cap (boiler door)
cap_front = cone("cap_front", r1=0.6, r2=0.6, depth=0.15, segs=14, loc=(1.30, 0.95, 0), parent=loco_p, mat=MAT_LOCO_RED)
cap_front.rotation_euler = (0, math.radians(90), 0)
# headlight
headlight = sphere("headlight", r=0.18, segs=14, rings=10, loc=(1.45, 0.95, 0), parent=loco_p, mat=MAT_HEADLIGHT)
# cheminée (chimney/funnel)
chim = cone("chim", r1=0.20, r2=0.28, depth=0.45, segs=12, loc=(0.85, 1.55, 0), parent=loco_p, mat=MAT_LOCO_CHIMNEY)
chim.rotation_euler = (math.radians(90), 0, 0)
# steam dome (small dome on top of boiler)
dome = sphere("steam_dome", r=0.18, segs=12, rings=10, loc=(0.20, 1.45, 0), parent=loco_p, mat=MAT_LOCO_GOLD)
dome.scale = (1.0, 0.7, 1.0)
# sand dome
sand_dome = sphere("sand_dome", r=0.15, segs=10, rings=8, loc=(-0.30, 1.45, 0), parent=loco_p, mat=MAT_LOCO_GOLD)
sand_dome.scale = (1.0, 0.7, 1.0)
# cabin (driver's compartment)
cabin = cube("cabin", size=1.0, loc=(-1.30, 1.30, 0), parent=loco_p, mat=MAT_LOCO_RED)
cabin.scale = (1.0, 1.0, 0.95)
# cabin roof
cab_roof = cube("cab_roof", size=1.0, loc=(-1.30, 1.85, 0), parent=loco_p, mat=MAT_LOCO_BLACK)
cab_roof.scale = (1.1, 0.08, 1.0)
# cabin windows
for side, dz in [("L", 0.50), ("R", -0.50)]:
    cw = cube(f"cab_win_{side}", size=1.0, loc=(-1.30, 1.50, dz), parent=loco_p, mat=MAT_WAGON_WINDOW)
    cw.scale = (0.30, 0.30, 0.04)
# chassis platform
chassis = cube("chassis", size=1.0, loc=(0, 0.35, 0), parent=loco_p, mat=MAT_LOCO_BLACK)
chassis.scale = (2.6, 0.10, 0.95)
# wheels (4 large driving wheels + 2 leading wheels)
loco_wheels_p = empty("loco_wheels", (0, 0, 0), parent=loco_p)
for i, (wx, wr) in enumerate([(1.0, 0.30), (0.4, 0.40), (-0.4, 0.40), (-1.0, 0.40)]):
    for side, dz in [("L", 0.55), ("R", -0.55)]:
        w = cone(f"wheel_{i}_{side}", r1=wr, r2=wr, depth=0.10, segs=14, loc=(wx, wr, dz), parent=loco_wheels_p, mat=MAT_WHEEL)
        w.rotation_euler = (0, math.radians(90), 0)
        # rim ring
        rim = cone(f"wheel_rim_{i}_{side}", r1=wr * 0.5, r2=wr * 0.5, depth=0.11, segs=12, loc=(wx, wr, dz), parent=loco_wheels_p, mat=MAT_WHEEL_RIM)
        rim.rotation_euler = (0, math.radians(90), 0)
        # 4 spokes
        for k in range(4):
            ka = k * (math.pi / 4)
            spoke = cube(f"spoke_{i}_{side}_{k}", size=1.0, loc=(wx, wr, dz), parent=loco_wheels_p, mat=MAT_WHEEL_RIM)
            spoke.scale = (wr * 0.7, 0.04, 0.04)
            spoke.rotation_euler = (0, 0, ka)
            spoke.rotation_mode = 'XYZ'

# 10 smoke puffs from chimney
chim_smokes = []
for k in range(10):
    py = 1.85 + k * 0.4
    pr = 0.18 + k * 0.06
    puff = sphere(f"smoke_{k}", r=pr, segs=12, rings=8, loc=(0.85, py, 0), parent=loco_p, mat=MAT_SMOKE)
    chim_smokes.append((puff, k))

# 4 steam jets from sides
steam_jets = []
for i, (sx, sz) in enumerate([(1.0, 0.6), (1.0, -0.6), (-0.4, 0.6), (-0.4, -0.6)]):
    sj = sphere(f"steam_jet_{i}", r=0.20, segs=10, rings=8, loc=(sx, 0.65, sz), parent=loco_p, mat=MAT_STEAM)
    sj.scale = (1.0, 0.5, 1.0)
    steam_jets.append((sj, i))

# --- 3 wagons (passenger / freight / tank) --------------------------------
wagon_offset = -3.5  # starts behind loco
wagons = []

# wagon 1 : passenger (green)
w1_p = empty("wagon_pass", (wagon_offset, 0, 0), parent=loco_p)
w1_body = cube("w1_body", size=1.0, loc=(0, 1.0, 0), parent=w1_p, mat=MAT_WAGON_GREEN)
w1_body.scale = (2.0, 0.85, 0.95)
# 4 windows
for i in range(4):
    wx = -0.65 + i * 0.45
    w = cube(f"w1_win_{i}", size=1.0, loc=(wx, 1.20, 0.49), parent=w1_p, mat=MAT_WAGON_WINDOW)
    w.scale = (0.30, 0.40, 0.03)
# roof
w1_roof = cube("w1_roof", size=1.0, loc=(0, 1.50, 0), parent=w1_p, mat=MAT_LOCO_BLACK)
w1_roof.scale = (2.1, 0.06, 1.0)
# 4 wheels
w1_wheels = empty("w1_wheels", (0, 0, 0), parent=w1_p)
for i, wx in enumerate([0.7, -0.7]):
    for side, dz in [("L", 0.55), ("R", -0.55)]:
        w = cone(f"w1_w_{i}_{side}", r1=0.28, r2=0.28, depth=0.08, segs=12, loc=(wx, 0.28, dz), parent=w1_wheels, mat=MAT_WHEEL)
        w.rotation_euler = (0, math.radians(90), 0)
wagons.append((w1_p, w1_wheels))

# wagon 2 : freight (brown)
w2_p = empty("wagon_freight", (wagon_offset - 2.6, 0, 0), parent=loco_p)
w2_body = cube("w2_body", size=1.0, loc=(0, 0.85, 0), parent=w2_p, mat=MAT_WAGON_BROWN)
w2_body.scale = (2.0, 0.6, 0.95)
# door (sliding)
door_freight = cube("w2_door", size=1.0, loc=(0, 0.75, 0.50), parent=w2_p, mat=MAT_STATION_ROOF)
door_freight.scale = (0.5, 0.45, 0.03)
# 4 wheels
w2_wheels = empty("w2_wheels", (0, 0, 0), parent=w2_p)
for i, wx in enumerate([0.7, -0.7]):
    for side, dz in [("L", 0.55), ("R", -0.55)]:
        w = cone(f"w2_w_{i}_{side}", r1=0.28, r2=0.28, depth=0.08, segs=12, loc=(wx, 0.28, dz), parent=w2_wheels, mat=MAT_WHEEL)
        w.rotation_euler = (0, math.radians(90), 0)
wagons.append((w2_p, w2_wheels))

# wagon 3 : tank (silver cylinder)
w3_p = empty("wagon_tank", (wagon_offset - 5.2, 0, 0), parent=loco_p)
tank = cone("w3_tank", r1=0.55, r2=0.55, depth=2.0, segs=14, loc=(0, 0.95, 0), parent=w3_p, mat=MAT_WAGON_TANK)
tank.rotation_euler = (0, math.radians(90), 0)
# dome on top
top_hatch = sphere("w3_hatch", r=0.18, segs=12, rings=8, loc=(0, 1.55, 0), parent=w3_p, mat=MAT_LOCO_GOLD)
# 4 wheels
w3_wheels = empty("w3_wheels", (0, 0, 0), parent=w3_p)
for i, wx in enumerate([0.7, -0.7]):
    for side, dz in [("L", 0.55), ("R", -0.55)]:
        w = cone(f"w3_w_{i}_{side}", r1=0.28, r2=0.28, depth=0.08, segs=12, loc=(wx, 0.28, dz), parent=w3_wheels, mat=MAT_WHEEL)
        w.rotation_euler = (0, math.radians(90), 0)
wagons.append((w3_p, w3_wheels))

# --- 4 lampadaires émissifs ----------------------------------------------
lamps = []
for i, (lx, lz) in enumerate([(-10, 2.5), (10, 2.5), (-10, -2.5), (10, -2.5)]):
    lp = empty(f"lamp_{i}", (lx, 0, lz))
    # post
    post = cone(f"lamp_{i}_post", r1=0.08, r2=0.06, depth=2.5, segs=8, loc=(0, 1.25, 0), parent=lp, mat=MAT_LAMP_POST)
    post.rotation_euler = (math.radians(90), 0, 0)
    # crossbar
    crossbar = cube(f"lamp_{i}_cb", size=1.0, loc=(0, 2.5, 0), parent=lp, mat=MAT_LAMP_POST)
    crossbar.scale = (0.4, 0.05, 0.05)
    # 2 lights (one each end of crossbar)
    for side, dx in [("L", -0.25), ("R", 0.25)]:
        light = sphere(f"lamp_{i}_l_{side}", r=0.15, segs=12, rings=8, loc=(dx, 2.4, 0), parent=lp, mat=MAT_LAMP_LIGHT)
    lamps.append(lp)

# --- tableau d'affichage ---------------------------------------------------
board_p = empty("board", (-1.0, 0, 2.0))
# stand
stand = cube("board_stand", size=1.0, loc=(0, 0.7, 0), parent=board_p, mat=MAT_LAMP_POST)
stand.scale = (0.06, 0.7, 0.06)
# board face
board = cube("board_face", size=1.0, loc=(0, 1.6, 0), parent=board_p, mat=MAT_BOARD)
board.scale = (1.0, 0.6, 0.05)
# 4 lines of text (emissive bars)
for i in range(4):
    by = 1.40 + i * 0.10
    txt = cube(f"board_t_{i}", size=1.0, loc=(0, by, 0.03), parent=board_p, mat=MAT_BOARD_TEXT)
    txt.scale = (0.7, 0.04, 0.03)

# --- signalisation rouge/vert (2 signal lights at end of tracks) ---------
signal_p = empty("signal", (12.0, 0, 0))
# pole
pole = cone("signal_pole", r1=0.05, r2=0.05, depth=2.5, segs=6, loc=(0, 1.25, 0), parent=signal_p, mat=MAT_LAMP_POST)
pole.rotation_euler = (math.radians(90), 0, 0)
# red light on top
sig_r = sphere("signal_r", r=0.12, segs=10, rings=8, loc=(0, 2.7, 0), parent=signal_p, mat=MAT_SIGNAL_RED)
# green light below
sig_g = sphere("signal_g", r=0.12, segs=10, rings=8, loc=(0, 2.40, 0), parent=signal_p, mat=MAT_SIGNAL_GREEN)
# box around them
sig_box = cube("signal_box", size=1.0, loc=(0, 2.55, 0), parent=signal_p, mat=MAT_LAMP_POST)
sig_box.scale = (0.10, 0.45, 0.18)

# --- 8 passagers silhouettes ----------------------------------------------
people = []
for i in range(8):
    plat_side = 1 if i % 2 == 0 else -1
    px = -8 + (i // 2) * 3.5
    pz = plat_side * 2.2
    pp = empty(f"person_{i}", (px, 0, pz))
    # body
    body = cube(f"person_{i}_body", size=1.0, loc=(0, 0.85, 0), parent=pp, mat=MAT_PERSON_COAT_R if i % 2 == 0 else MAT_PERSON_COAT_B)
    body.scale = (0.20, 0.65, 0.12)
    # head
    head = sphere(f"person_{i}_head", r=0.12, segs=10, rings=8, loc=(0, 1.35, 0), parent=pp, mat=MAT_PERSON)
    # legs
    for side, dx in [("L", -0.07), ("R", 0.07)]:
        leg = cube(f"person_{i}_leg_{side}", size=1.0, loc=(dx, 0.30, 0), parent=pp, mat=MAT_PERSON)
        leg.scale = (0.07, 0.35, 0.10)
    people.append(pp)

# --- 6 valises ------------------------------------------------------------
for i in range(6):
    plat_side = 1 if i % 2 == 0 else -1
    lx = -7 + (i // 2) * 4.0
    lz = plat_side * 2.2 + 0.3
    lp = empty(f"luggage_{i}", (lx, 0, lz))
    body = cube(f"luggage_{i}_body", size=1.0, loc=(0, 0.20, 0), parent=lp, mat=MAT_LUGGAGE)
    body.scale = (0.30, 0.20, 0.18)
    handle = cube(f"luggage_{i}_h", size=1.0, loc=(0, 0.36, 0), parent=lp, mat=MAT_LUGGAGE_HANDLE)
    handle.scale = (0.12, 0.04, 0.02)

# --- 4 arbres latéraux ----------------------------------------------------
for i, (tx, tz) in enumerate([(-15, 6), (15, 6), (-15, -6), (15, -6)]):
    tp = empty(f"tree_{i}", (tx, 0, tz))
    trunk = cone(f"tree_{i}_trunk", r1=0.25, r2=0.18, depth=2.0, segs=8, loc=(0, 1.0, 0), parent=tp, mat=MAT_TREE_TRUNK)
    trunk.rotation_euler = (math.radians(90), 0, 0)
    leaves = sphere(f"tree_{i}_leaves", r=1.2, segs=18, rings=12, loc=(0, 2.5, 0), parent=tp, mat=MAT_TREE_LEAVES)
    leaves.scale = (1.0, 0.9, 1.0)

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

# locomotive moves forward slowly (along X)
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    lx = -5.0 + tt * 12.0  # cross the platform
    kf_loc(loco_p, f, (lx, 0, 0))

# loco wheels rotate
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(loco_wheels_p, f, (math.pi * 16 * tt, math.radians(90), 0))

# wagon wheels rotate
for w_p, w_wheels in wagons:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        kf_rot(w_wheels, f, (math.pi * 16 * tt, math.radians(90), 0))

# chimney smoke rise
for puff, k in chim_smokes:
    phase = k * 6
    base_y = puff.location.y
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 80
        lt = local_f / 80
        dy = base_y + lt * 2.5
        dx = math.sin(lt * math.pi * 3.0) * 0.20
        kf_loc(puff, f, (0.85 + dx, dy, 0))
        s = 0.5 + lt * 1.8
        kf_scale(puff, f, (s, s, s))

# 4 steam jets pulse
for sj, idx in steam_jets:
    phase = idx * 12
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 40
        lt = local_f / 40
        s = 0.4 + 1.5 * math.exp(-((lt - 0.3) * 5.0) ** 2)
        kf_scale(sj, f, (s, 0.5 * s, s))

# 4 lamps pulse
for i, lp in enumerate(lamps):
    phase = i * 0.5
    # find lamp light children to scale (they're children of lp, but easier to scale lp slightly)
    # actually scale ONLY the light sphere : let's identify them
    for child in lp.children:
        if "_l_" in child.name:
            for f in range(1, FRAMES + 1, 4):
                tt = (f - 1) / (FRAMES - 1)
                s = 1.0 + 0.20 * math.sin(tt * math.pi * 5.0 + phase)
                kf_scale(child, f, (s, s, s))

# clock minute hand rotates (1 turn per loop)
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(hand_min_p, f, (0, 0, -tt * math.pi * 2.0))

# pendulum oscillates
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    swing = math.radians(20) * math.sin(tt * math.pi * 6.0)
    kf_rot(pendulum_p, f, (0, 0, swing))

# signal red/green alternation (scale tricks since material switching is complex)
for f in range(1, FRAMES + 1, 5):
    tt = (f - 1) / (FRAMES - 1)
    on = math.sin(tt * math.pi * 4.0) > 0
    if on:
        kf_scale(sig_r, f, (1.0, 1.0, 1.0))
        kf_scale(sig_g, f, (0.4, 0.4, 0.4))
    else:
        kf_scale(sig_r, f, (0.4, 0.4, 0.4))
        kf_scale(sig_g, f, (1.0, 1.0, 1.0))

# people sway (tiny tilt)
for i, p in enumerate(people):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 5):
        tt = (f - 1) / (FRAMES - 1)
        tilt = math.radians(3) * math.sin(tt * math.pi * 4.0 + phase)
        kf_rot(p, f, (tilt, 0, 0))

# headlight pulse
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.15 * math.sin(tt * math.pi * 6.0)
    kf_scale(headlight, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_trainstation] wrote {OUT}")
