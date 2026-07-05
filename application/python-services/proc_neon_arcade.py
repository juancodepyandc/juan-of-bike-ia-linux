"""
proc_neon_arcade.py — 128e procédural AuroraIA, Phase F++++.

Salle d'arcade rétro années 80 : 6 bornes d'arcade vintage colorées
en ligne + 1 baby-foot + 1 air hockey + 1 flipper rétro + 4 néons
muraux émissifs (logos retro) + sol damier émissif + 5 lampes
suspendues + 2 chaises hautes + table + 3 personnages 8-bit + 4 boules
de billard + ciel/mur sombre.

Animation :
- 4 néons muraux : cycle couleurs (alternance scale on/off)
- 6 écrans bornes : flicker pulse
- 5 lampes plafond : pulse
- baby-foot ball : bounce + roulis
- flipper plateau : bouncing ball
- 3 perso 8-bit : bob

Sortie : output/3d/pbr_arcadeneon_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_arcadeneon_proc.glb"))

random.seed(0xAC0DEF)

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
MAT_WALL = make_mat("wall", (0.10, 0.06, 0.15), roughness=0.7,
                     emi=(0.10, 0.06, 0.18), emi_strength=0.3)
MAT_FLOOR_DARK = make_mat("floor_dark", (0.05, 0.05, 0.08), roughness=0.6)
MAT_FLOOR_TILE_PINK = make_mat("floor_pink", (0.95, 0.30, 0.65), roughness=0.4,
                                 emi=(0.85, 0.20, 0.55), emi_strength=2.0)
MAT_FLOOR_TILE_CYAN = make_mat("floor_cyan", (0.20, 0.85, 1.0), roughness=0.4,
                                 emi=(0.15, 0.75, 1.0), emi_strength=2.0)
MAT_ARCADE_RED = make_mat("arcade_red", (0.85, 0.10, 0.15), roughness=0.55,
                            emi=(0.35, 0.05, 0.08), emi_strength=0.3)
MAT_ARCADE_BLUE = make_mat("arcade_blue", (0.15, 0.30, 0.85), roughness=0.55,
                             emi=(0.05, 0.15, 0.45), emi_strength=0.3)
MAT_ARCADE_GREEN = make_mat("arcade_green", (0.15, 0.75, 0.30), roughness=0.55,
                              emi=(0.05, 0.40, 0.15), emi_strength=0.3)
MAT_ARCADE_YELLOW = make_mat("arcade_yellow", (1.0, 0.85, 0.10), roughness=0.55,
                               emi=(0.50, 0.40, 0.05), emi_strength=0.3)
MAT_ARCADE_PURPLE = make_mat("arcade_purple", (0.75, 0.20, 0.95), roughness=0.55,
                               emi=(0.40, 0.10, 0.50), emi_strength=0.3)
MAT_ARCADE_ORANGE = make_mat("arcade_orange", (1.0, 0.50, 0.10), roughness=0.55,
                               emi=(0.50, 0.25, 0.05), emi_strength=0.3)
MAT_SCREEN = make_mat("screen", (0.40, 0.20, 0.95), roughness=0.0, alpha=0.9,
                        emi=(0.40, 0.20, 1.0), emi_strength=5.5)
MAT_SCREEN_R = make_mat("screen_r", (1.0, 0.20, 0.20), roughness=0.0,
                          emi=(1.0, 0.20, 0.20), emi_strength=5.5)
MAT_SCREEN_G = make_mat("screen_g", (0.20, 1.0, 0.40), roughness=0.0,
                          emi=(0.20, 1.0, 0.40), emi_strength=5.5)
MAT_JOYSTICK = make_mat("joystick", (0.10, 0.10, 0.10), roughness=0.5)
MAT_JOYSTICK_KNOB = make_mat("joy_knob", (0.85, 0.10, 0.10), roughness=0.3,
                               emi=(0.30, 0.05, 0.05), emi_strength=0.3)
MAT_BUTTON_R = make_mat("button_r", (1.0, 0.20, 0.20), roughness=0.3,
                          emi=(0.5, 0.10, 0.10), emi_strength=0.4)
MAT_BUTTON_B = make_mat("button_b", (0.20, 0.40, 1.0), roughness=0.3,
                          emi=(0.10, 0.20, 0.5), emi_strength=0.4)
MAT_BUTTON_Y = make_mat("button_y", (1.0, 0.95, 0.10), roughness=0.3,
                          emi=(0.50, 0.50, 0.05), emi_strength=0.4)
MAT_NEON_PINK = make_mat("neon_pink", (1.0, 0.30, 0.85), roughness=0.0,
                           emi=(1.0, 0.30, 0.85), emi_strength=8.0)
MAT_NEON_CYAN = make_mat("neon_cyan", (0.20, 0.95, 1.0), roughness=0.0,
                           emi=(0.20, 0.95, 1.0), emi_strength=8.0)
MAT_NEON_YELLOW = make_mat("neon_yellow", (1.0, 0.95, 0.20), roughness=0.0,
                             emi=(1.0, 0.95, 0.20), emi_strength=8.0)
MAT_NEON_GREEN = make_mat("neon_green", (0.30, 1.0, 0.20), roughness=0.0,
                            emi=(0.30, 1.0, 0.20), emi_strength=8.0)
MAT_BABYFOOT = make_mat("babyfoot", (0.30, 0.55, 0.20), roughness=0.7)
MAT_BABYFOOT_FRAME = make_mat("babyfoot_frame", (0.40, 0.20, 0.10), roughness=0.7)
MAT_BABYFOOT_PLAYER = make_mat("babyfoot_player_r", (0.95, 0.10, 0.10), roughness=0.6)
MAT_BABYFOOT_PLAYER_B = make_mat("babyfoot_player_b", (0.10, 0.30, 0.95), roughness=0.6)
MAT_BABYFOOT_BALL = make_mat("babyfoot_ball", (0.95, 0.95, 0.95), roughness=0.4,
                               emi=(0.5, 0.5, 0.5), emi_strength=0.5)
MAT_AIRHOCKEY = make_mat("airhockey", (0.20, 0.25, 0.95), roughness=0.4,
                           emi=(0.10, 0.15, 0.55), emi_strength=0.3)
MAT_AIRHOCKEY_PUCK = make_mat("airhockey_puck", (0.10, 0.10, 0.10), roughness=0.5)
MAT_PINBALL = make_mat("pinball", (0.95, 0.10, 0.30), roughness=0.5,
                         emi=(0.50, 0.05, 0.15), emi_strength=0.3)
MAT_PINBALL_TOP = make_mat("pinball_top", (0.20, 0.20, 0.30), roughness=0.5,
                             emi=(0.20, 0.30, 0.95), emi_strength=1.5)
MAT_LAMP_BASE = make_mat("lamp_base", (0.10, 0.10, 0.10), roughness=0.6)
MAT_LAMP_LIGHT = make_mat("lamp_light", (1.0, 0.85, 0.50), roughness=0.0, alpha=0.85,
                            emi=(1.0, 0.85, 0.50), emi_strength=8.0)
MAT_CHAIR = make_mat("chair", (0.55, 0.10, 0.10), roughness=0.6)
MAT_CHAIR_LEG = make_mat("chair_leg", (0.15, 0.15, 0.15), roughness=0.6)
MAT_TABLE = make_mat("table", (0.30, 0.20, 0.10), roughness=0.7)
MAT_PERSON_HEAD = make_mat("person_head", (0.95, 0.75, 0.55), roughness=0.7)
MAT_PERSON_R = make_mat("person_r", (0.85, 0.10, 0.20), roughness=0.7,
                          emi=(0.30, 0.05, 0.08), emi_strength=0.3)
MAT_PERSON_B = make_mat("person_b", (0.20, 0.45, 0.95), roughness=0.7,
                          emi=(0.10, 0.20, 0.5), emi_strength=0.3)
MAT_PERSON_G = make_mat("person_g", (0.30, 0.85, 0.30), roughness=0.7,
                          emi=(0.10, 0.4, 0.15), emi_strength=0.3)
MAT_BILLIARD_BALL = make_mat("billiard", (0.95, 0.10, 0.10), roughness=0.3,
                               emi=(0.30, 0.05, 0.05), emi_strength=0.3)

# --- backdrop : 3 walls + floor + ceiling -------------------------------
# back wall
back = cube("back_wall", size=1.0, loc=(0, 5, -6), mat=MAT_WALL)
back.scale = (24, 8, 0.2)

# left and right walls
for side, dx in [("L", -12), ("R", 12)]:
    wall = cube(f"wall_{side}", size=1.0, loc=(dx, 5, 0), mat=MAT_WALL)
    wall.scale = (0.2, 8, 14)

# ceiling
ceiling = cube("ceiling", size=1.0, loc=(0, 9, 0), mat=MAT_WALL)
ceiling.scale = (24, 0.2, 14)

# checkerboard floor (8x8 cells)
N_CELLS = 10
CELL_SIZE = 2.4
for i in range(N_CELLS):
    for j in range(N_CELLS):
        x = -N_CELLS * CELL_SIZE / 2 + i * CELL_SIZE + CELL_SIZE / 2
        z = -N_CELLS * CELL_SIZE / 2 + j * CELL_SIZE + CELL_SIZE / 2
        mat = MAT_FLOOR_TILE_PINK if (i + j) % 2 == 0 else MAT_FLOOR_TILE_CYAN
        tile = cube(f"floor_{i}_{j}", size=1.0, loc=(x, 0, z), mat=mat)
        tile.scale = (CELL_SIZE * 0.45, 0.05, CELL_SIZE * 0.45)
# floor base (dark underneath)
floor_base = cube("floor_base", size=1.0, loc=(0, -0.05, 0), mat=MAT_FLOOR_DARK)
floor_base.scale = (28, 0.05, 16)

# --- 6 bornes d'arcade en ligne ----------------------------------------
def make_arcade(name, x, z, cabinet_mat, screen_mat):
    p = empty(name, (x, 0, z))
    # base
    base = cube(f"{name}_base", size=1.0, loc=(0, 0.4, 0), parent=p, mat=cabinet_mat)
    base.scale = (0.8, 0.8, 0.6)
    # cabinet body (upper part)
    cab = cube(f"{name}_cab", size=1.0, loc=(0, 1.4, 0), parent=p, mat=cabinet_mat)
    cab.scale = (0.8, 1.2, 0.55)
    # marquee header
    marquee = cube(f"{name}_marquee", size=1.0, loc=(0, 2.20, 0), parent=p, mat=cabinet_mat)
    marquee.scale = (0.8, 0.30, 0.40)
    # screen (front-facing, tilted slightly)
    screen = cube(f"{name}_screen", size=1.0, loc=(0, 1.55, 0.30), parent=p, mat=screen_mat)
    screen.scale = (0.55, 0.40, 0.04)
    # control panel below screen
    panel = cube(f"{name}_panel", size=1.0, loc=(0, 1.0, 0.30), parent=p, mat=MAT_JOYSTICK)
    panel.scale = (0.55, 0.10, 0.40)
    panel.rotation_euler = (math.radians(-15), 0, 0)
    # joystick
    joy = cone(f"{name}_joy", r1=0.05, r2=0.04, depth=0.20, segs=8, loc=(-0.15, 1.07, 0.42), parent=p, mat=MAT_JOYSTICK)
    joy.rotation_euler = (math.radians(75), 0, 0)
    joy_knob = sphere(f"{name}_joy_knob", r=0.05, segs=10, rings=8, loc=(-0.15, 1.20, 0.50), parent=p, mat=MAT_JOYSTICK_KNOB)
    # 2 buttons
    for k, (bx, mat) in enumerate([(0.10, MAT_BUTTON_R), (0.20, MAT_BUTTON_Y)]):
        bt = sphere(f"{name}_btn_{k}", r=0.04, segs=8, rings=6, loc=(bx, 1.05, 0.44), parent=p, mat=mat)
    # coin slot
    coin = cube(f"{name}_coin", size=1.0, loc=(0, 0.7, 0.32), parent=p, mat=MAT_JOYSTICK)
    coin.scale = (0.08, 0.02, 0.03)
    return p, screen

arcade_data = [
    (-7.0, -3.0, MAT_ARCADE_RED, MAT_SCREEN),
    (-5.5, -3.0, MAT_ARCADE_BLUE, MAT_SCREEN_G),
    (-4.0, -3.0, MAT_ARCADE_GREEN, MAT_SCREEN_R),
    (-2.5, -3.0, MAT_ARCADE_YELLOW, MAT_SCREEN),
    (-1.0, -3.0, MAT_ARCADE_PURPLE, MAT_SCREEN_G),
    (0.5, -3.0, MAT_ARCADE_ORANGE, MAT_SCREEN_R),
]
arcade_screens = []
for i, (ax, az, cm, sm) in enumerate(arcade_data):
    p, scr = make_arcade(f"arcade_{i}", ax, az, cm, sm)
    arcade_screens.append(scr)

# --- baby-foot ------------------------------------------------------------
baby_p = empty("babyfoot", (3.0, 0, -3.0))
# main table top (green field)
field = cube("baby_field", size=1.0, loc=(0, 0.7, 0), parent=baby_p, mat=MAT_BABYFOOT)
field.scale = (1.5, 0.05, 0.9)
# 4 sides (walls)
for side, dx, dz, sx, sz in [("F", 0, 0.95, 1.55, 0.05), ("B", 0, -0.95, 1.55, 0.05), ("L", 1.55, 0, 0.05, 0.95), ("R", -1.55, 0, 0.05, 0.95)]:
    w = cube(f"baby_w_{side}", size=1.0, loc=(dx, 0.78, dz), parent=baby_p, mat=MAT_BABYFOOT_FRAME)
    w.scale = (sx, 0.20, sz)
# 4 legs
for i, (lx, lz) in enumerate([(1.4, 0.85), (-1.4, 0.85), (1.4, -0.85), (-1.4, -0.85)]):
    leg = cube(f"baby_leg_{i}", size=1.0, loc=(lx, 0.35, lz), parent=baby_p, mat=MAT_BABYFOOT_FRAME)
    leg.scale = (0.06, 0.7, 0.06)
# 4 rods with players (alternating red/blue)
for i, (rx, color) in enumerate([(-1.0, MAT_BABYFOOT_PLAYER_B), (-0.3, MAT_BABYFOOT_PLAYER), (0.3, MAT_BABYFOOT_PLAYER_B), (1.0, MAT_BABYFOOT_PLAYER)]):
    # rod
    rod = cone(f"baby_rod_{i}", r1=0.03, r2=0.03, depth=2.0, segs=6, loc=(rx, 0.85, 0), parent=baby_p, mat=MAT_BABYFOOT_FRAME)
    rod.rotation_euler = (math.radians(90), 0, 0)
    # 3 players on rod
    for k in range(3):
        kz = -0.7 + k * 0.7
        player = cube(f"baby_p_{i}_{k}", size=1.0, loc=(rx, 0.85, kz), parent=baby_p, mat=color)
        player.scale = (0.07, 0.20, 0.07)
# ball on field
baby_ball = sphere("baby_ball", r=0.07, segs=10, rings=8, loc=(0, 0.78, 0), parent=baby_p, mat=MAT_BABYFOOT_BALL)

# --- air hockey ----------------------------------------------------------
ah_p = empty("airhockey", (6.0, 0, -3.0))
table_ah = cube("ah_table", size=1.0, loc=(0, 0.7, 0), parent=ah_p, mat=MAT_AIRHOCKEY)
table_ah.scale = (1.3, 0.06, 0.8)
# 2 short side walls
for side, dz in [("F", 0.85), ("B", -0.85)]:
    w = cube(f"ah_w_{side}", size=1.0, loc=(0, 0.78, dz), parent=ah_p, mat=MAT_BABYFOOT_FRAME)
    w.scale = (1.4, 0.12, 0.04)
# 2 goals (open ends with frame)
for side, dx in [("L", 1.40), ("R", -1.40)]:
    fr = cube(f"ah_goal_{side}", size=1.0, loc=(dx, 0.78, 0), parent=ah_p, mat=MAT_BABYFOOT_FRAME)
    fr.scale = (0.04, 0.12, 0.30)
# 4 legs
for i, (lx, lz) in enumerate([(1.2, 0.75), (-1.2, 0.75), (1.2, -0.75), (-1.2, -0.75)]):
    leg = cube(f"ah_leg_{i}", size=1.0, loc=(lx, 0.35, lz), parent=ah_p, mat=MAT_BABYFOOT_FRAME)
    leg.scale = (0.06, 0.7, 0.06)
# puck
puck = cone("ah_puck", r1=0.07, r2=0.07, depth=0.03, segs=12, loc=(0, 0.75, 0), parent=ah_p, mat=MAT_AIRHOCKEY_PUCK)
# 2 paddles
for side, dx, color in [("L", 1.0, MAT_BUTTON_R), ("R", -1.0, MAT_BUTTON_B)]:
    pad = cone(f"ah_pad_{side}", r1=0.10, r2=0.10, depth=0.05, segs=12, loc=(dx, 0.77, 0), parent=ah_p, mat=color)

# --- pinball machine ----------------------------------------------------
pin_p = empty("pinball", (-7.0, 0, 1.0))
# legs
for i, (lx, lz) in enumerate([(0.5, 0.4), (-0.5, 0.4), (0.5, -0.4), (-0.5, -0.4)]):
    leg = cube(f"pin_leg_{i}", size=1.0, loc=(lx, 0.35, lz), parent=pin_p, mat=MAT_BABYFOOT_FRAME)
    leg.scale = (0.06, 0.7, 0.06)
# main playing field (tilted)
field_p = empty("pin_field_p", (0, 0.8, 0), parent=pin_p)
field_p.rotation_euler = (math.radians(-15), 0, 0)
field = cube("pin_field", size=1.0, loc=(0, 0, 0), parent=field_p, mat=MAT_PINBALL)
field.scale = (1.0, 0.05, 1.5)
# 4 bumpers on field
bumpers = []
for k, (bx, bz) in enumerate([(-0.3, 0.5), (0.3, 0.5), (-0.3, -0.2), (0.3, -0.2)]):
    bumper = cone(f"pin_bump_{k}", r1=0.10, r2=0.10, depth=0.10, segs=10, loc=(bx, 0.08, bz), parent=field_p, mat=MAT_BUTTON_Y)
    bumper.rotation_euler = (math.radians(90), 0, 0)
    bumpers.append(bumper)
# 2 flippers at bottom
for side, dx, rot in [("L", -0.25, math.radians(30)), ("R", 0.25, math.radians(-30))]:
    fl = cube(f"pin_flip_{side}", size=1.0, loc=(dx, 0.05, 0.8), parent=field_p, mat=MAT_BUTTON_R)
    fl.scale = (0.15, 0.04, 0.05)
    fl.rotation_euler = (0, 0, rot)
# ball
pin_ball = sphere("pin_ball", r=0.06, segs=10, rings=8, loc=(0, 0.07, -0.4), parent=field_p, mat=MAT_LAMP_LIGHT)
# backbox (vertical display panel)
backbox = cube("pin_back", size=1.0, loc=(0, 1.5, -0.7), parent=pin_p, mat=MAT_PINBALL_TOP)
backbox.scale = (1.0, 0.8, 0.10)

# --- 4 néons muraux émissifs ----------------------------------------------
neon_signs = []
# place along back wall
neon_data = [
    (-7.5, 6.0, MAT_NEON_PINK),
    (-2.5, 6.0, MAT_NEON_CYAN),
    (2.5, 6.0, MAT_NEON_YELLOW),
    (7.5, 6.0, MAT_NEON_GREEN),
]
for i, (nx, ny, mat) in enumerate(neon_data):
    np = empty(f"neon_{i}", (nx, ny, -5.85))
    # outer rectangle (border of sign)
    for side, dx, dy, sx, sy in [
        ("T", 0, 0.5, 1.6, 0.08),
        ("B", 0, -0.5, 1.6, 0.08),
        ("L", -0.8, 0, 0.08, 1.0),
        ("R", 0.8, 0, 0.08, 1.0),
    ]:
        bar = cube(f"neon_{i}_{side}", size=1.0, loc=(dx, dy, 0), parent=np, mat=mat)
        bar.scale = (sx, sy, 0.08)
    # 3 inner letters (vertical bars suggesting text)
    for k in range(3):
        kx = -0.4 + k * 0.4
        lt = cube(f"neon_{i}_l_{k}", size=1.0, loc=(kx, 0, 0), parent=np, mat=mat)
        lt.scale = (0.06, 0.25, 0.06)
    neon_signs.append((np, i))

# --- 5 lampes plafond ----------------------------------------------------
ceiling_lamps = []
lamp_xs = [-7, -3.5, 0, 3.5, 7]
for i, lx in enumerate(lamp_xs):
    lp = empty(f"clamp_{i}", (lx, 8.5, 0))
    # rod
    rod = cone(f"clamp_{i}_rod", r1=0.04, r2=0.04, depth=0.5, segs=4, loc=(0, -0.25, 0), parent=lp, mat=MAT_LAMP_BASE)
    rod.rotation_euler = (math.radians(90), 0, 0)
    # shade
    shade = cone(f"clamp_{i}_shade", r1=0.30, r2=0.20, depth=0.25, segs=14, loc=(0, -0.50, 0), parent=lp, mat=MAT_LAMP_BASE)
    shade.rotation_euler = (math.radians(180), 0, 0)
    # light bulb
    bulb = sphere(f"clamp_{i}_bulb", r=0.15, segs=12, rings=8, loc=(0, -0.55, 0), parent=lp, mat=MAT_LAMP_LIGHT)
    ceiling_lamps.append(bulb)

# --- 2 chaises hautes + table -------------------------------------------
chairs = []
for i, (cx, cz) in enumerate([(5.5, 3.0), (7.5, 3.0)]):
    cp = empty(f"chair_{i}", (cx, 0, cz))
    # seat
    seat = cube(f"chair_{i}_seat", size=1.0, loc=(0, 0.7, 0), parent=cp, mat=MAT_CHAIR)
    seat.scale = (0.3, 0.05, 0.3)
    # backrest
    back = cube(f"chair_{i}_back", size=1.0, loc=(0, 1.1, 0.13), parent=cp, mat=MAT_CHAIR)
    back.scale = (0.3, 0.4, 0.04)
    # 4 legs
    for j, (jx, jz) in enumerate([(0.12, 0.12), (-0.12, 0.12), (0.12, -0.12), (-0.12, -0.12)]):
        leg = cube(f"chair_{i}_l_{j}", size=1.0, loc=(jx, 0.35, jz), parent=cp, mat=MAT_CHAIR_LEG)
        leg.scale = (0.04, 0.7, 0.04)
    chairs.append(cp)

# round table between chairs
table_p = empty("table", (6.5, 0, 3.0))
table_top = cone("table_top", r1=0.4, r2=0.4, depth=0.05, segs=20, loc=(0, 0.75, 0), parent=table_p, mat=MAT_TABLE)
table_top.rotation_euler = (math.radians(90), 0, 0)
table_leg = cone("table_leg", r1=0.05, r2=0.08, depth=0.75, segs=8, loc=(0, 0.375, 0), parent=table_p, mat=MAT_CHAIR_LEG)
table_leg.rotation_euler = (math.radians(90), 0, 0)
# 4 billiard balls on table
for i in range(4):
    a = i * (math.pi * 2 / 4)
    bx = math.cos(a) * 0.15
    bz = math.sin(a) * 0.15
    bb = sphere(f"billiard_{i}", r=0.06, segs=10, rings=8, loc=(bx, 0.85, bz), parent=table_p, mat=MAT_BILLIARD_BALL)

# --- 3 personnages 8-bit -------------------------------------------------
def make_person(name, x, z, color):
    p = empty(name, (x, 0, z))
    body = cube(f"{name}_body", size=1.0, loc=(0, 0.5, 0), parent=p, mat=color)
    body.scale = (0.18, 0.40, 0.12)
    head = sphere(f"{name}_head", r=0.13, segs=12, rings=8, loc=(0, 1.05, 0), parent=p, mat=MAT_PERSON_HEAD)
    # legs
    for side, dx in [("L", -0.08), ("R", 0.08)]:
        leg = cube(f"{name}_leg_{side}", size=1.0, loc=(dx, 0.15, 0), parent=p, mat=color)
        leg.scale = (0.07, 0.30, 0.10)
    # 2 arms
    for side, dx in [("L", -0.22), ("R", 0.22)]:
        arm = cube(f"{name}_arm_{side}", size=1.0, loc=(dx, 0.45, 0), parent=p, mat=color)
        arm.scale = (0.07, 0.30, 0.10)
    return p

people = []
for i, (px, pz, mat) in enumerate([
    (-6.0, -1.5, MAT_PERSON_R),
    (-3.5, -1.5, MAT_PERSON_B),
    (4.0, -1.5, MAT_PERSON_G),
]):
    p = make_person(f"person_{i}", px, pz, mat)
    people.append(p)

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

# 4 neon signs : pulse (each different phase)
for ns_p, idx in neon_signs:
    phase = idx * 0.7
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(ns_p, f, (s, s, 1.0))

# 6 arcade screens flicker
for i, scr in enumerate(arcade_screens):
    phase = i * 0.4
    base_x = scr.scale.x
    base_y = scr.scale.y
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        # rapid flicker
        s = 1.0 + 0.08 * math.sin(tt * math.pi * 18.0 + phase)
        kf_scale(scr, f, (base_x * s, base_y * s, scr.scale.z))

# 5 ceiling lamps pulse
for i, bulb in enumerate(ceiling_lamps):
    phase = i * 0.5
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 4.0 + phase)
        kf_scale(bulb, f, (s, s, s))

# baby-foot ball bounces
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    bx = 0.8 * math.sin(tt * math.pi * 6.0)
    bz = 0.5 * math.cos(tt * math.pi * 4.0)
    by = 0.78 + 0.05 * abs(math.sin(tt * math.pi * 8.0))
    kf_loc(baby_ball, f, (bx, by, bz))

# pinball ball bounces around
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    bx = 0.6 * math.sin(tt * math.pi * 5.0)
    bz = -0.5 + math.cos(tt * math.pi * 4.0) * 0.5
    kf_loc(pin_ball, f, (bx, 0.07, bz))

# 4 pinball bumpers pulse
for i, bumper in enumerate(bumpers):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 6.0 + phase)
        kf_scale(bumper, f, (s, s, s))

# pinball flippers : alternating activate
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    # cycle every 90 frames
    local = (tt * 4.0) % 1.0
    flip_l_active = local < 0.1
    flip_r_active = 0.5 < local < 0.6
    fl_l = bpy.data.objects.get("pin_flip_L")
    fl_r = bpy.data.objects.get("pin_flip_R")
    if fl_l:
        rot_l = math.radians(50 if flip_l_active else 30)
        fl_l.rotation_euler = (0, 0, rot_l)
        fl_l.keyframe_insert(data_path="rotation_euler", frame=f)
    if fl_r:
        rot_r = math.radians(-50 if flip_r_active else -30)
        fl_r.rotation_euler = (0, 0, rot_r)
        fl_r.keyframe_insert(data_path="rotation_euler", frame=f)

# 3 people bob
for i, p in enumerate(people):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        bob = 0.05 * math.sin(tt * math.pi * 4.0 + phase)
        kf_loc(p, f, (p.location.x, bob, p.location.z))
        tilt = math.radians(3) * math.sin(tt * math.pi * 4.0 + phase)
        kf_rot(p, f, (0, 0, tilt))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_arcadeneon] wrote {OUT}")
