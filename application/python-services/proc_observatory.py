"""
proc_observatory.py — 124e procédural AuroraIA, Phase F++++.

Observatoire astronomique nocturne : grande coupole hémisphérique avec
ouverture rotative en fente + télescope géant à l'intérieur + 5
antennes radio paraboliques alignées + 8 panneaux solaires + bâtiment
moderne bas + 3 voitures scientifiques + 60 étoiles + 1 planète Saturne
+ 1 satellite orbital + voie lactée bande + 4 arbres + chemin
+ feux de signalisation.

Animation :
- coupole : rotate Y (1 turn/loop)
- télescope tilt X (sin)
- satellite : orbite Y
- 60 étoiles : scintillent phases offset
- 5 antennes : rotate Y subtle
- 8 panneaux solaires : tilt suivant

Sortie : output/3d/pbr_observatory_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_observatory_proc.glb"))

random.seed(0xB5CAFE)

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
MAT_SKY_NIGHT = make_mat("sky_night", (0.02, 0.03, 0.08), roughness=1.0,
                          emi=(0.03, 0.04, 0.10), emi_strength=0.4)
MAT_MILKY_WAY = make_mat("milky_way", (0.25, 0.20, 0.40), roughness=1.0, alpha=0.7,
                           emi=(0.35, 0.30, 0.55), emi_strength=1.2)
MAT_STAR_W = make_mat("star_w", (1.0, 1.0, 1.0), roughness=0.0,
                       emi=(1.0, 1.0, 1.0), emi_strength=5.5)
MAT_STAR_Y = make_mat("star_y", (1.0, 0.95, 0.65), roughness=0.0,
                       emi=(1.0, 0.95, 0.65), emi_strength=6.0)
MAT_STAR_B = make_mat("star_b", (0.7, 0.85, 1.0), roughness=0.0,
                       emi=(0.7, 0.85, 1.0), emi_strength=6.0)
MAT_PLANET_SATURN = make_mat("planet_saturn", (0.85, 0.70, 0.45), roughness=0.7,
                               emi=(0.30, 0.25, 0.15), emi_strength=0.4)
MAT_PLANET_RING = make_mat("planet_ring", (0.95, 0.85, 0.65), roughness=0.4, alpha=0.55,
                             emi=(0.45, 0.40, 0.30), emi_strength=0.6)
MAT_GROUND = make_mat("ground", (0.08, 0.10, 0.08), roughness=0.95)
MAT_DOME_BASE = make_mat("dome_base", (0.45, 0.45, 0.50), metallic=0.5, roughness=0.5,
                           emi=(0.10, 0.10, 0.12), emi_strength=0.2)
MAT_DOME = make_mat("dome", (0.75, 0.75, 0.80), metallic=0.7, roughness=0.3,
                     emi=(0.20, 0.20, 0.22), emi_strength=0.3)
MAT_DOME_DARK = make_mat("dome_dark", (0.20, 0.20, 0.22), roughness=0.5)
MAT_TELESCOPE = make_mat("telescope", (0.35, 0.35, 0.40), metallic=0.85, roughness=0.3,
                           emi=(0.10, 0.10, 0.12), emi_strength=0.3)
MAT_TELESCOPE_LENS = make_mat("scope_lens", (0.30, 0.85, 1.0), roughness=0.0, alpha=0.85,
                                emi=(0.20, 0.85, 1.0), emi_strength=3.5)
MAT_ANTENNA = make_mat("antenna", (0.85, 0.85, 0.90), metallic=0.7, roughness=0.4)
MAT_ANTENNA_DISH = make_mat("antenna_dish", (0.92, 0.92, 0.95), metallic=0.7, roughness=0.3,
                              emi=(0.20, 0.20, 0.25), emi_strength=0.3)
MAT_PANEL_GLASS = make_mat("panel_glass", (0.10, 0.20, 0.55), metallic=0.7, roughness=0.2,
                             emi=(0.10, 0.30, 0.85), emi_strength=2.0)
MAT_PANEL_FRAME = make_mat("panel_frame", (0.50, 0.50, 0.55), metallic=0.5, roughness=0.6)
MAT_BUILDING = make_mat("building", (0.40, 0.40, 0.45), roughness=0.7,
                          emi=(0.08, 0.08, 0.10), emi_strength=0.2)
MAT_BUILDING_WINDOW = make_mat(
    "bld_window", (1.0, 0.85, 0.55), roughness=0.0, alpha=0.85,
    emi=(1.0, 0.85, 0.55), emi_strength=5.0,
)
MAT_CAR_WHITE = make_mat("car_white", (0.85, 0.85, 0.85), metallic=0.4, roughness=0.4)
MAT_CAR_RED = make_mat("car_red", (0.85, 0.10, 0.10), metallic=0.4, roughness=0.4,
                         emi=(0.30, 0.05, 0.05), emi_strength=0.3)
MAT_CAR_BLUE = make_mat("car_blue", (0.10, 0.30, 0.85), metallic=0.4, roughness=0.4)
MAT_CAR_TIRE = make_mat("car_tire", (0.05, 0.05, 0.05), roughness=0.7)
MAT_CAR_LIGHT = make_mat("car_light", (1.0, 0.95, 0.70), roughness=0.0,
                           emi=(1.0, 0.95, 0.70), emi_strength=4.0)
MAT_SATELLITE = make_mat("satellite", (0.55, 0.55, 0.60), metallic=0.85, roughness=0.3,
                           emi=(0.15, 0.15, 0.20), emi_strength=0.4)
MAT_SAT_PANEL = make_mat("sat_panel", (0.10, 0.20, 0.85), metallic=0.7, roughness=0.2,
                           emi=(0.15, 0.30, 0.85), emi_strength=2.5)
MAT_PATH = make_mat("path", (0.35, 0.35, 0.32), roughness=0.85,
                      emi=(0.08, 0.08, 0.08), emi_strength=0.15)
MAT_TREE_TRUNK = make_mat("tree_trunk", (0.15, 0.10, 0.06), roughness=0.95)
MAT_TREE_LEAVES = make_mat("tree_leaves", (0.05, 0.20, 0.08), roughness=0.85)
MAT_SIGNAL_R = make_mat("signal_red", (1.0, 0.10, 0.10), roughness=0.0,
                          emi=(1.0, 0.10, 0.10), emi_strength=6.0)

# --- backdrop : night sky -------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 18, 6), mat=MAT_SKY_NIGHT)
sky.scale = (32, 0.1, 14)

# milky way band (diagonal)
mw_p = empty("milky_way_p", (0, 17.5, 10.0))
mw_p.rotation_euler = (0, 0, math.radians(20))
mw = cube("milky_way", size=1.0, loc=(0, 0, 0), parent=mw_p, mat=MAT_MILKY_WAY)
mw.scale = (32, 0.1, 2.5)

# 60 stars
for i in range(60):
    x = random.uniform(-15, 15)
    z = random.uniform(2, 12)
    y = random.uniform(16, 17)
    pick = random.random()
    if pick < 0.7:
        m = MAT_STAR_W
    elif pick < 0.88:
        m = MAT_STAR_Y
    else:
        m = MAT_STAR_B
    sr = random.uniform(0.05, 0.13)
    s = sphere(f"star_{i}", r=sr, segs=8, rings=6, loc=(x, y, z), mat=m)
    s["_phase"] = (i * 11) % 47

# Saturn (planet with ring)
saturn_p = empty("saturn", (-9.0, 14.0, 9.5))
saturn = sphere("saturn", r=1.0, segs=20, rings=14, loc=(0, 0, 0), parent=saturn_p, mat=MAT_PLANET_SATURN)
saturn_ring = cone("saturn_ring", r1=2.0, r2=2.0, depth=0.05, segs=30, loc=(0, 0, 0), parent=saturn_p, mat=MAT_PLANET_RING)
saturn_ring.rotation_euler = (math.radians(25), 0, math.radians(10))
saturn_ring.scale = (1.0, 1.0, 0.02)

# ground
ground = cube("ground", size=1.0, loc=(0, -0.05, 0), mat=MAT_GROUND)
ground.scale = (30, 0.1, 24)

# circular path leading to observatory
for i in range(12):
    a = i * (math.pi * 2 / 12)
    px = math.cos(a) * 6.0
    pz = math.sin(a) * 6.0
    if abs(a - math.pi / 2) < 0.4:  # gap for entrance
        continue
    ps = sphere(f"path_{i}", r=0.40, segs=8, rings=6, loc=(px, 0.10, pz), mat=MAT_PATH)
    ps.scale = (1.0, 0.2, 0.8)

# --- main observatory dome -------------------------------------------------
dome_p = empty("dome_p", (0, 0, 0))

# building base (cylindrical)
base = cone("dome_base", r1=2.8, r2=2.8, depth=1.8, segs=20, loc=(0, 0.9, 0), parent=dome_p, mat=MAT_DOME_BASE)
base.rotation_euler = (math.radians(90), 0, 0)

# 4 windows on base
for i in range(4):
    a = i * (math.pi * 2 / 4) + math.pi / 8
    wx = math.cos(a) * 2.85
    wz = math.sin(a) * 2.85
    w = cube(f"dome_window_{i}", size=1.0, loc=(wx, 1.0, wz), parent=dome_p, mat=MAT_BUILDING_WINDOW)
    w.scale = (0.05, 0.5, 0.5)
    w.rotation_euler = (0, -a, 0)

# top ring of base
ring = cone("dome_ring", r1=2.9, r2=2.9, depth=0.15, segs=20, loc=(0, 1.85, 0), parent=dome_p, mat=MAT_DOME_DARK)
ring.rotation_euler = (math.radians(90), 0, 0)

# hemisphere dome (rotating part)
dome_rotate = empty("dome_rotate", (0, 1.9, 0), parent=dome_p)
dome_top = sphere("dome_top", r=2.7, segs=24, rings=12, loc=(0, 0, 0), parent=dome_rotate, mat=MAT_DOME)
dome_top.scale = (1.0, 0.55, 1.0)

# slit (opening for telescope) - dark cube cut out
slit_dark = cube("dome_slit_dark", size=1.0, loc=(0, 1.3, 0), parent=dome_rotate, mat=MAT_DOME_DARK)
slit_dark.scale = (0.8, 0.4, 2.6)
# slit edges (light bands)
for side, dx in [("L", 0.35), ("R", -0.35)]:
    edge = cube(f"slit_edge_{side}", size=1.0, loc=(dx, 1.3, 0), parent=dome_rotate, mat=MAT_DOME_BASE)
    edge.scale = (0.10, 0.45, 2.6)

# --- telescope (visible through slit) -------------------------------------
scope_p = empty("scope", (0, 2.0, 0), parent=dome_rotate)
# main barrel (long cylinder)
barrel = cone("scope_barrel", r1=0.30, r2=0.32, depth=2.5, segs=14, loc=(0, 0, 0), parent=scope_p, mat=MAT_TELESCOPE)
barrel.rotation_euler = (math.radians(30), 0, 0)
# scope rings (3 supports)
for i in range(3):
    ya = i * 0.7 - 0.7
    rng = cone(f"scope_ring_{i}", r1=0.40, r2=0.40, depth=0.05, segs=14, loc=(0, ya * 0.866, ya * 0.5), parent=scope_p, mat=MAT_DOME_BASE)
    rng.rotation_euler = (math.radians(30 + 90), 0, 0)
# lens at front
lens = sphere("scope_lens", r=0.32, segs=14, rings=10, loc=(0, 1.08, 0.625), parent=scope_p, mat=MAT_TELESCOPE_LENS)
lens.scale = (1.0, 0.5, 1.0)
# eyepiece (smaller cone at back)
eyepiece = cone("scope_eye", r1=0.12, r2=0.18, depth=0.5, segs=10, loc=(0, -1.30, -0.75), parent=scope_p, mat=MAT_TELESCOPE)
eyepiece.rotation_euler = (math.radians(30 + 90), 0, 0)

# scope mount (yoke)
yoke = cube("scope_yoke", size=1.0, loc=(0, -1.0, 0), parent=dome_rotate, mat=MAT_DOME_BASE)
yoke.scale = (0.15, 0.5, 1.5)

# --- 5 antennes radio paraboliques alignées ------------------------------
antennas = []
for i in range(5):
    ax = -6.0 + i * 3.0
    ap = empty(f"antenna_{i}", (ax, 0, -8.0))
    # mast (tall vertical pole)
    mast = cone(f"antenna_{i}_mast", r1=0.10, r2=0.08, depth=2.0, segs=8, loc=(0, 1.0, 0), parent=ap, mat=MAT_ANTENNA)
    mast.rotation_euler = (math.radians(90), 0, 0)
    # dish (large parabolic - approximated by stretched sphere)
    dish_p = empty(f"antenna_{i}_dish_p", (0, 2.0, 0), parent=ap)
    dish_p.rotation_euler = (math.radians(20), 0, 0)
    dish = sphere(f"antenna_{i}_dish", r=0.8, segs=18, rings=12, loc=(0, 0, 0), parent=dish_p, mat=MAT_ANTENNA_DISH)
    dish.scale = (1.0, 0.15, 1.0)
    # central receiver (small cone in front of dish)
    rec = cone(f"antenna_{i}_rec", r1=0.05, r2=0.05, depth=0.30, segs=6, loc=(0, 0.20, 0), parent=dish_p, mat=MAT_ANTENNA)
    rec.rotation_euler = (math.radians(90), 0, 0)
    # 3 support struts
    for k in range(3):
        ka = k * (math.pi * 2 / 3)
        strut = cone(f"antenna_{i}_strut_{k}", r1=0.015, r2=0.01, depth=0.25, segs=4, loc=(math.cos(ka) * 0.2, 0.13, math.sin(ka) * 0.2), parent=dish_p, mat=MAT_ANTENNA)
        strut.rotation_euler = (math.radians(70), 0, ka)
    antennas.append(dish_p)

# --- 8 panneaux solaires --------------------------------------------------
panels = []
for i in range(8):
    px = -7.0 + (i % 4) * 4.0
    pz = 8.0 - (i // 4) * 1.8
    pp = empty(f"panel_{i}", (px, 0, pz))
    # stand
    stand = cone(f"panel_{i}_stand", r1=0.08, r2=0.06, depth=0.7, segs=6, loc=(0, 0.35, 0), parent=pp, mat=MAT_PANEL_FRAME)
    stand.rotation_euler = (math.radians(90), 0, 0)
    # panel array (4 cells in 2x2)
    panel_array_p = empty(f"panel_{i}_array_p", (0, 0.8, 0), parent=pp)
    panel_array_p.rotation_euler = (math.radians(-30), 0, 0)
    # frame
    frame = cube(f"panel_{i}_frame", size=1.0, loc=(0, 0, 0), parent=panel_array_p, mat=MAT_PANEL_FRAME)
    frame.scale = (1.4, 0.04, 1.0)
    # 4 cells (slightly smaller, emissive blue)
    for row in range(2):
        for col in range(2):
            cx = -0.35 + col * 0.7
            cz = -0.25 + row * 0.5
            cell = cube(f"panel_{i}_c{row}{col}", size=1.0, loc=(cx, 0.04, cz), parent=panel_array_p, mat=MAT_PANEL_GLASS)
            cell.scale = (0.65, 0.02, 0.45)
    panels.append(panel_array_p)

# --- building (control room, modern low rectangle) -----------------------
bld_p = empty("control_bld", (-5.0, 0, 5.0))
body = cube("bld_body", size=1.0, loc=(0, 0.7, 0), parent=bld_p, mat=MAT_BUILDING)
body.scale = (2.0, 0.7, 1.5)
# 5 windows (glowing)
for i in range(5):
    wx = -0.8 + i * 0.4
    win = cube(f"bld_win_{i}", size=1.0, loc=(wx, 0.85, 0.78), parent=bld_p, mat=MAT_BUILDING_WINDOW)
    win.scale = (0.30, 0.30, 0.05)
# antenna on roof
ant = cone("bld_ant", r1=0.05, r2=0.02, depth=1.0, segs=6, loc=(0, 1.9, 0), parent=bld_p, mat=MAT_ANTENNA)
ant.rotation_euler = (math.radians(90), 0, 0)
# red signal light on top
sig = sphere("bld_signal", r=0.10, segs=10, rings=8, loc=(0, 2.4, 0), parent=bld_p, mat=MAT_SIGNAL_R)

# --- 3 voitures -----------------------------------------------------------
def make_car(name, x, z, color_mat, rot=0):
    p = empty(name, (x, 0, z))
    p.rotation_euler = (0, rot, 0)
    body = cube(f"{name}_body", size=1.0, loc=(0, 0.25, 0), parent=p, mat=color_mat)
    body.scale = (0.85, 0.30, 0.40)
    # roof
    roof = cube(f"{name}_roof", size=1.0, loc=(0, 0.50, 0), parent=p, mat=color_mat)
    roof.scale = (0.55, 0.20, 0.35)
    # 4 wheels
    for i, (wx, wz) in enumerate([(0.50, 0.30), (-0.50, 0.30), (0.50, -0.30), (-0.50, -0.30)]):
        w = cone(f"{name}_w_{i}", r1=0.12, r2=0.12, depth=0.08, segs=10, loc=(wx, 0.12, wz), parent=p, mat=MAT_CAR_TIRE)
        w.rotation_euler = (0, math.radians(90), 0)
    # headlights
    for side, dz in [("L", 0.15), ("R", -0.15)]:
        hl = sphere(f"{name}_hl_{side}", r=0.05, segs=8, rings=6, loc=(0.82, 0.25, dz), parent=p, mat=MAT_CAR_LIGHT)
    return p

cars = [
    make_car("car_0", -4.5, -5.0, MAT_CAR_WHITE),
    make_car("car_1", -3.0, -5.5, MAT_CAR_RED, math.radians(20)),
    make_car("car_2", 4.5, -5.0, MAT_CAR_BLUE, math.radians(-15)),
]

# --- satellite orbital ---------------------------------------------------
sat_p = empty("satellite", (4.0, 9.5, 0))
sat_body = cube("sat_body", size=1.0, loc=(0, 0, 0), parent=sat_p, mat=MAT_SATELLITE)
sat_body.scale = (0.25, 0.25, 0.30)
# 2 solar panels
for side, dx in [("L", -0.50), ("R", 0.50)]:
    panel = cube(f"sat_panel_{side}", size=1.0, loc=(dx, 0, 0), parent=sat_p, mat=MAT_SAT_PANEL)
    panel.scale = (0.40, 0.02, 0.20)
# antenna dish (small)
sat_dish = sphere("sat_dish", r=0.10, segs=10, rings=8, loc=(0, 0.20, 0), parent=sat_p, mat=MAT_ANTENNA_DISH)
sat_dish.scale = (1.0, 0.4, 1.0)

# --- 4 arbres ------------------------------------------------------------
for i, (tx, tz) in enumerate([(-8, 4), (8, 4), (-9, -2), (9, -2)]):
    tp = empty(f"tree_{i}", (tx, 0, tz))
    trunk = cone(f"tree_{i}_trunk", r1=0.18, r2=0.14, depth=1.5, segs=8, loc=(0, 0.75, 0), parent=tp, mat=MAT_TREE_TRUNK)
    trunk.rotation_euler = (math.radians(90), 0, 0)
    for j in range(3):
        h = 1.5 + j * 0.5
        r = 0.7 - j * 0.15
        leaves = cone(f"tree_{i}_l_{j}", r1=r, r2=r * 0.3, depth=0.6, segs=10, loc=(0, h, 0), parent=tp, mat=MAT_TREE_LEAVES)
        leaves.rotation_euler = (math.radians(90), 0, 0)

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

# dome rotates (1 turn / loop)
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(dome_rotate, f, (0, tt * math.pi * 2.0, 0))

# telescope tilt (inside dome)
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    tilt = math.radians(30) + math.radians(20) * math.sin(tt * math.pi * 2.0)
    # we keyframe rotation of scope_p
    scope_p.rotation_euler = (tilt, 0, 0)
    scope_p.keyframe_insert(data_path="rotation_euler", frame=f)
# also tilt scope_p children that have similar base rotation
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    tilt = math.radians(30) + math.radians(20) * math.sin(tt * math.pi * 2.0)
    kf_rot(barrel, f, (tilt, 0, 0))
    # eyepiece below center
    eyepiece.rotation_euler = (tilt + math.radians(90), 0, 0)
    eyepiece.keyframe_insert(data_path="rotation_euler", frame=f)

# stars twinkle
for i in range(60):
    star = bpy.data.objects.get(f"star_{i}")
    if not star:
        continue
    phase = star["_phase"]
    for f in range(1, FRAMES + 1, 6):
        tt = (f - 1) / (FRAMES - 1)
        local = (math.sin(tt * math.pi * 6.0 + phase * 0.13) + 1) * 0.5
        s = 0.6 + 0.6 * local
        kf_scale(star, f, (s, s, s))

# satellite orbits
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    angle = tt * math.pi * 2.0
    sx = math.cos(angle) * 7.0
    sz = math.sin(angle) * 5.0
    sy = 9.5 + 0.3 * math.sin(tt * math.pi * 4.0)
    kf_loc(sat_p, f, (sx, sy, sz))
    kf_rot(sat_p, f, (0, -angle + math.pi / 2, math.radians(10) * math.sin(tt * math.pi * 5.0)))

# 5 antennas subtle rotate
for i, dish_p in enumerate(antennas):
    base_rot = dish_p.rotation_euler.copy()
    for f in range(1, FRAMES + 1, 5):
        tt = (f - 1) / (FRAMES - 1)
        delta = math.radians(15) * math.sin(tt * math.pi * 2.0 + i * 0.5)
        kf_rot(dish_p, f, (base_rot[0], delta, 0))

# 8 panels tilt with subtle sun-tracking
for i, panel in enumerate(panels):
    base_rot = panel.rotation_euler.copy()
    for f in range(1, FRAMES + 1, 5):
        tt = (f - 1) / (FRAMES - 1)
        delta = math.radians(10) * math.sin(tt * math.pi * 1.5 + i * 0.4)
        kf_rot(panel, f, (base_rot[0] + delta, base_rot[1], base_rot[2]))

# saturn rotate
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(saturn_p, f, (0, 0, tt * math.pi * 1.0))

# signal light pulse
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.30 * math.sin(tt * math.pi * 8.0)
    kf_scale(sig, f, (s, s, s))

# scope lens pulse subtle
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.10 * math.sin(tt * math.pi * 5.0)
    kf_scale(lens, f, (s, 0.5 * s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_observatory] wrote {OUT}")
