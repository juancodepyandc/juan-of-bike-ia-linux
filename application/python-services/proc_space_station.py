"""
proc_space_station.py — 129e procédural AuroraIA, Phase F++++.

Station spatiale orbitale type ISS : module central + 4 modules radiaux
+ 6 panneaux solaires déployés + 2 antennes communications + 1 docking
port + 2 satellites visite + cargo bay + 4 fenêtres émissives + 60
étoiles fond + planète Terre + 1 navette spatiale en approche
+ 1 astronaut EVA flottant à côté.

Animation :
- station rotate Y lente
- 6 panneaux orientent (tilt)
- navette s'approche (translation)
- 2 antennes pivotent
- planète Terre tourne
- 60 étoiles scintillent
- astronaut EVA flotte

Sortie : output/3d/pbr_spacestation_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_spacestation_proc.glb"))

random.seed(0xFA15ED)

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
MAT_SPACE = make_mat("space", (0.01, 0.01, 0.03), roughness=1.0,
                      emi=(0.02, 0.02, 0.05), emi_strength=0.3)
MAT_STAR_W = make_mat("star_w", (1.0, 1.0, 1.0), roughness=0.0,
                        emi=(1.0, 1.0, 1.0), emi_strength=5.5)
MAT_STAR_Y = make_mat("star_y", (1.0, 0.95, 0.65), roughness=0.0,
                        emi=(1.0, 0.95, 0.65), emi_strength=6.0)
MAT_STAR_B = make_mat("star_b", (0.7, 0.85, 1.0), roughness=0.0,
                        emi=(0.7, 0.85, 1.0), emi_strength=6.0)
MAT_EARTH = make_mat("earth", (0.20, 0.50, 0.85), roughness=0.6,
                       emi=(0.15, 0.35, 0.65), emi_strength=0.5)
MAT_EARTH_GREEN = make_mat("earth_green", (0.20, 0.55, 0.25), roughness=0.6,
                             emi=(0.10, 0.30, 0.12), emi_strength=0.4)
MAT_EARTH_CLOUD = make_mat("earth_cloud", (0.95, 0.95, 1.0), roughness=0.8, alpha=0.7,
                             emi=(0.7, 0.75, 0.85), emi_strength=0.6)
MAT_EARTH_ATM = make_mat("earth_atm", (0.30, 0.65, 1.0), roughness=0.0, alpha=0.20,
                           emi=(0.30, 0.65, 1.0), emi_strength=1.5)
MAT_STATION_MAIN = make_mat("station_main", (0.85, 0.85, 0.90), metallic=0.7, roughness=0.3,
                              emi=(0.20, 0.20, 0.25), emi_strength=0.3)
MAT_STATION_DARK = make_mat("station_dark", (0.30, 0.30, 0.32), metallic=0.6, roughness=0.5)
MAT_STATION_GOLD = make_mat("station_gold", (0.95, 0.75, 0.30), metallic=0.85, roughness=0.4,
                              emi=(0.50, 0.40, 0.10), emi_strength=0.4)
MAT_WINDOW = make_mat("window", (1.0, 0.95, 0.60), roughness=0.0, alpha=0.85,
                        emi=(1.0, 0.95, 0.60), emi_strength=6.0)
MAT_SOLAR_PANEL = make_mat("solar", (0.10, 0.20, 0.85), metallic=0.7, roughness=0.2,
                             emi=(0.10, 0.30, 1.0), emi_strength=2.5)
MAT_SOLAR_FRAME = make_mat("solar_frame", (0.50, 0.50, 0.55), metallic=0.5, roughness=0.5)
MAT_ANTENNA = make_mat("antenna", (0.85, 0.85, 0.90), metallic=0.7, roughness=0.4)
MAT_ANTENNA_DISH = make_mat("antenna_dish", (0.95, 0.95, 0.98), metallic=0.7, roughness=0.3,
                              emi=(0.20, 0.20, 0.25), emi_strength=0.3)
MAT_SHUTTLE = make_mat("shuttle", (0.95, 0.95, 0.95), metallic=0.5, roughness=0.4,
                         emi=(0.20, 0.20, 0.20), emi_strength=0.2)
MAT_SHUTTLE_BLACK = make_mat("shuttle_black", (0.10, 0.10, 0.10), roughness=0.5)
MAT_SHUTTLE_ENGINE = make_mat("shuttle_engine", (1.0, 0.30, 0.10), roughness=0.0,
                                emi=(1.0, 0.30, 0.10), emi_strength=7.0)
MAT_ASTRONAUT_SUIT = make_mat("astronaut", (0.95, 0.95, 0.95), roughness=0.6,
                                emi=(0.20, 0.20, 0.20), emi_strength=0.2)
MAT_ASTRONAUT_VISOR = make_mat("visor", (1.0, 0.85, 0.30), metallic=0.9, roughness=0.2,
                                 emi=(0.4, 0.30, 0.05), emi_strength=0.5)
MAT_DOCKING_LIGHT_R = make_mat("dock_r", (1.0, 0.10, 0.10), roughness=0.0,
                                 emi=(1.0, 0.10, 0.10), emi_strength=6.0)
MAT_DOCKING_LIGHT_G = make_mat("dock_g", (0.10, 1.0, 0.30), roughness=0.0,
                                 emi=(0.10, 1.0, 0.30), emi_strength=6.0)

# --- backdrop : deep space ------------------------------------------------
space = cube("space_back", size=1.0, loc=(0, 16, 4), mat=MAT_SPACE)
space.scale = (40, 0.1, 20)

# 60 stars in 3D space
for i in range(60):
    x = random.uniform(-18, 18)
    z = random.uniform(-3, 12)
    y = random.uniform(14.5, 15.5)
    pick = random.random()
    if pick < 0.7:
        m = MAT_STAR_W
    elif pick < 0.88:
        m = MAT_STAR_Y
    else:
        m = MAT_STAR_B
    sr = random.uniform(0.05, 0.12)
    s = sphere(f"star_{i}", r=sr, segs=8, rings=6, loc=(x, y, z), mat=m)
    s["_phase"] = (i * 13) % 47

# --- planet Earth in background -------------------------------------------
earth_p = empty("earth_p", (-10.0, 4.0, 8.0))
earth = sphere("earth", r=3.0, segs=32, rings=24, loc=(0, 0, 0), parent=earth_p, mat=MAT_EARTH)
# atmosphere halo
atm = sphere("earth_atm", r=3.25, segs=30, rings=22, loc=(0, 0, 0), parent=earth_p, mat=MAT_EARTH_ATM)
# 4 green continents (large patches)
for i in range(4):
    a = i * (math.pi * 2 / 4) + 0.5
    cx = math.cos(a) * 2.0
    cz = math.sin(a) * 2.0
    cy = random.uniform(-0.5, 0.5)
    cont = sphere(f"continent_{i}", r=0.9, segs=14, rings=10, loc=(cx, cy, cz), parent=earth_p, mat=MAT_EARTH_GREEN)
    cont.scale = (1.0, 0.4, 1.0)
# 3 cloud swirls
for i in range(3):
    a = i * (math.pi * 2 / 3) + 1.2
    cx = math.cos(a) * 2.5
    cy = random.uniform(-1.0, 1.0)
    cz = math.sin(a) * 2.5
    cl = sphere(f"earth_cloud_{i}", r=1.0, segs=14, rings=10, loc=(cx, cy, cz), parent=earth_p, mat=MAT_EARTH_CLOUD)
    cl.scale = (1.2, 0.3, 1.2)

# --- main space station ---------------------------------------------------
station = empty("station", (3.0, 6.0, 0))

# central node (cylindrical)
central = cone("station_central", r1=0.7, r2=0.7, depth=2.0, segs=14, loc=(0, 0, 0), parent=station, mat=MAT_STATION_MAIN)
central.rotation_euler = (0, math.radians(90), 0)

# 4 windows on central
for i, ay in enumerate([-0.5, -0.15, 0.15, 0.5]):
    win = cube(f"station_win_{i}", size=1.0, loc=(ay, 0, 0.72), parent=station, mat=MAT_WINDOW)
    win.scale = (0.20, 0.20, 0.04)

# 4 radial modules (Y, -Y, Z, -Z)
modules = []
for i, (dx, dy, dz) in enumerate([(0, 1.5, 0), (0, -1.5, 0), (0, 0, 1.5), (0, 0, -1.5)]):
    mod = cone(f"module_{i}", r1=0.45, r2=0.45, depth=1.5, segs=12, loc=(dx, dy, dz), parent=station, mat=MAT_STATION_MAIN)
    # orient towards center
    if dy != 0:
        mod.rotation_euler = (math.radians(90 if dy > 0 else -90), 0, 0)
    else:
        mod.rotation_euler = (0, math.radians(90 if dz > 0 else -90), 0)
    # cap end
    cap = sphere(f"module_{i}_cap", r=0.48, segs=14, rings=10, loc=(dx * 1.4, dy * 1.4, dz * 1.4), parent=station, mat=MAT_STATION_GOLD)
    cap.scale = (0.6, 0.6, 0.6)
    modules.append(mod)
    # 2 small windows on each module
    if dy != 0:
        for w_i, dz_off in enumerate([-0.3, 0.3]):
            w = cube(f"module_{i}_w_{w_i}", size=1.0, loc=(0.40, dy, dz_off), parent=station, mat=MAT_WINDOW)
            w.scale = (0.04, 0.10, 0.10)
    else:
        for w_i, dx_off in enumerate([-0.3, 0.3]):
            w = cube(f"module_{i}_w_{w_i}", size=1.0, loc=(dx_off, 0.40, dz), parent=station, mat=MAT_WINDOW)
            w.scale = (0.10, 0.10, 0.04)

# Long backbone (truss) extending Z axis
truss_p = empty("truss", (0, 0, 0), parent=station)
truss_main = cube("truss_main", size=1.0, loc=(2.0, 0, 0), parent=truss_p, mat=MAT_STATION_DARK)
truss_main.scale = (5.0, 0.10, 0.10)
truss_main2 = cube("truss_main2", size=1.0, loc=(-2.0, 0, 0), parent=truss_p, mat=MAT_STATION_DARK)
truss_main2.scale = (5.0, 0.10, 0.10)
# perpendicular truss
for k in range(5):
    kx = -3.5 + k * 1.75
    pt = cube(f"truss_perp_{k}", size=1.0, loc=(kx, 0, 0), parent=truss_p, mat=MAT_STATION_DARK)
    pt.scale = (0.05, 0.05, 1.2)

# --- 6 solar panels (3 left + 3 right) ------------------------------------
solar_panels = []
for i, (px, pz, py) in enumerate([
    (-5.0, 1.0, 0), (-5.0, -1.0, 0), (-5.0, 0, 1.0),
    (5.0, 1.0, 0), (5.0, -1.0, 0), (5.0, 0, 1.0),
]):
    sp_p = empty(f"solar_p_{i}", (px, py, pz), parent=station)
    # axis support (small arm extending from truss)
    sp_p.rotation_euler = (0, math.radians(15 * (i % 3 - 1)), 0)
    # frame
    frame = cube(f"solar_{i}_frame", size=1.0, loc=(0, 0, 0), parent=sp_p, mat=MAT_SOLAR_FRAME)
    frame.scale = (0.05, 1.6, 0.04)
    # 6 cells in 2x3 array
    for r in range(3):
        for c in range(2):
            cx = -0.4 + c * 0.8
            cz = -1.2 + r * 1.0
            cell = cube(f"solar_{i}_c_{r}_{c}", size=1.0, loc=(0, cz, cx), parent=sp_p, mat=MAT_SOLAR_PANEL)
            cell.scale = (0.04, 0.45, 0.35)
    solar_panels.append(sp_p)

# --- 2 antennes communications --------------------------------------------
antennas = []
for i, (ax, az) in enumerate([(0, 1.5), (0, -1.5)]):
    ap = empty(f"antenna_{i}", (ax, 1.0, az), parent=station)
    # mast
    mast = cone(f"antenna_{i}_mast", r1=0.05, r2=0.04, depth=0.7, segs=6, loc=(0, 0.35, 0), parent=ap, mat=MAT_ANTENNA)
    mast.rotation_euler = (math.radians(90), 0, 0)
    # dish (squashed sphere)
    dish_p = empty(f"antenna_{i}_dish_p", (0, 0.8, 0), parent=ap)
    dish_p.rotation_euler = (math.radians(20), 0, 0)
    dish = sphere(f"antenna_{i}_dish", r=0.40, segs=18, rings=12, loc=(0, 0, 0), parent=dish_p, mat=MAT_ANTENNA_DISH)
    dish.scale = (1.0, 0.15, 1.0)
    # receiver
    rec = cone(f"antenna_{i}_rec", r1=0.04, r2=0.04, depth=0.2, segs=4, loc=(0, 0.12, 0), parent=dish_p, mat=MAT_ANTENNA)
    rec.rotation_euler = (math.radians(90), 0, 0)
    antennas.append(dish_p)

# --- docking port (one end of station with red/green lights) -------------
dock_p = empty("dock", (3.5, 0, 0), parent=station)
dock_ring = cone("dock_ring", r1=0.55, r2=0.55, depth=0.20, segs=14, loc=(0, 0, 0), parent=dock_p, mat=MAT_STATION_DARK)
dock_ring.rotation_euler = (0, math.radians(90), 0)
# red and green guidance lights (4 of each)
for i in range(4):
    a = i * (math.pi * 2 / 4)
    rx = math.cos(a) * 0.50
    rz = math.sin(a) * 0.50
    mat = MAT_DOCKING_LIGHT_R if i % 2 == 0 else MAT_DOCKING_LIGHT_G
    light = sphere(f"dock_l_{i}", r=0.06, segs=8, rings=6, loc=(0, rx, rz), parent=dock_p, mat=mat)

# --- cargo bay (large box hanging below) ---------------------------------
cargo_p = empty("cargo", (-2.0, -2.5, 0), parent=station)
cargo_body = cube("cargo_body", size=1.0, loc=(0, 0, 0), parent=cargo_p, mat=MAT_STATION_GOLD)
cargo_body.scale = (0.7, 0.7, 1.2)
# attachment arm
arm = cube("cargo_arm", size=1.0, loc=(0, 0.85, 0), parent=cargo_p, mat=MAT_STATION_DARK)
arm.scale = (0.06, 0.7, 0.06)
# 2 windows on cargo
for w_i, dz in enumerate([-0.4, 0.4]):
    w = cube(f"cargo_w_{w_i}", size=1.0, loc=(0.36, 0, dz), parent=cargo_p, mat=MAT_WINDOW)
    w.scale = (0.04, 0.20, 0.20)

# --- 2 visiting satellites (small) ----------------------------------------
satellites = []
sat_data = [
    (12.0, 9.0, 3.0, math.radians(15)),
    (-7.0, 11.0, -2.0, math.radians(-25)),
]
for i, (sx, sy, sz, rot) in enumerate(sat_data):
    sp = empty(f"sat_{i}", (sx, sy, sz))
    sp.rotation_euler = (0, rot, 0)
    body = cube(f"sat_{i}_body", size=1.0, loc=(0, 0, 0), parent=sp, mat=MAT_STATION_GOLD)
    body.scale = (0.25, 0.25, 0.35)
    # 2 solar panels
    for side, dx in [("L", -0.55), ("R", 0.55)]:
        panel = cube(f"sat_{i}_p_{side}", size=1.0, loc=(dx, 0, 0), parent=sp, mat=MAT_SOLAR_PANEL)
        panel.scale = (0.40, 0.04, 0.25)
    # dish on top
    dish = sphere(f"sat_{i}_dish", r=0.10, segs=8, rings=6, loc=(0, 0.25, 0), parent=sp, mat=MAT_ANTENNA_DISH)
    dish.scale = (1.0, 0.4, 1.0)
    satellites.append(sp)

# --- navette spatiale (shuttle approaching) -------------------------------
shuttle = empty("shuttle", (8.0, 5.0, -2.0))
shuttle.rotation_euler = (0, math.radians(180), 0)
# main body (long, white)
body = sphere("shuttle_body", r=0.5, segs=18, rings=12, loc=(0, 0, 0), parent=shuttle, mat=MAT_SHUTTLE)
body.scale = (2.2, 0.7, 0.8)
# nose (darker, more pointed)
nose = sphere("shuttle_nose", r=0.40, segs=14, rings=10, loc=(1.1, 0, 0), parent=shuttle, mat=MAT_SHUTTLE_BLACK)
nose.scale = (1.2, 0.7, 0.8)
# wings (delta-like)
for side, dz in [("L", 0.55), ("R", -0.55)]:
    wing = cube(f"shuttle_w_{side}", size=1.0, loc=(-0.4, 0, dz), parent=shuttle, mat=MAT_SHUTTLE)
    wing.scale = (0.6, 0.06, 0.4)
# vertical fin
fin = cube("shuttle_fin", size=1.0, loc=(-0.8, 0.35, 0), parent=shuttle, mat=MAT_SHUTTLE)
fin.scale = (0.30, 0.35, 0.06)
# 3 engines (back, glowing)
for i, dz in enumerate([-0.25, 0, 0.25]):
    eng = cone(f"shuttle_engine_{i}", r1=0.12, r2=0.18, depth=0.30, segs=10, loc=(-1.20, 0, dz), parent=shuttle, mat=MAT_SHUTTLE_ENGINE)
    eng.rotation_euler = (0, math.radians(-90), 0)
# cockpit windows
cock = cube("shuttle_cock", size=1.0, loc=(0.55, 0.20, 0), parent=shuttle, mat=MAT_WINDOW)
cock.scale = (0.30, 0.15, 0.40)

# --- astronaut EVA --------------------------------------------------------
eva_p = empty("astronaut", (5.0, 5.5, 1.5))
suit_body = sphere("eva_body", r=0.20, segs=14, rings=10, loc=(0, 0, 0), parent=eva_p, mat=MAT_ASTRONAUT_SUIT)
suit_body.scale = (1.0, 1.4, 0.8)
# helmet
helmet = sphere("eva_helmet", r=0.15, segs=14, rings=10, loc=(0, 0.30, 0), parent=eva_p, mat=MAT_ASTRONAUT_SUIT)
# gold visor
visor = sphere("eva_visor", r=0.12, segs=12, rings=8, loc=(0.05, 0.30, 0), parent=eva_p, mat=MAT_ASTRONAUT_VISOR)
visor.scale = (0.8, 0.7, 1.0)
# 4 limbs
for limb_name, (lx, ly, lz, sx, sy, sz) in [
    ("arm_L", (0.20, 0.10, 0, 0.15, 0.30, 0.10)),
    ("arm_R", (-0.20, 0.10, 0, 0.15, 0.30, 0.10)),
    ("leg_L", (0.08, -0.20, 0, 0.12, 0.30, 0.10)),
    ("leg_R", (-0.08, -0.20, 0, 0.12, 0.30, 0.10)),
]:
    limb = cube(f"eva_{limb_name}", size=1.0, loc=(lx, ly, lz), parent=eva_p, mat=MAT_ASTRONAUT_SUIT)
    limb.scale = (sx, sy, sz)
# PLSS backpack
plss = cube("eva_plss", size=1.0, loc=(0, 0.05, -0.18), parent=eva_p, mat=MAT_STATION_DARK)
plss.scale = (0.18, 0.30, 0.10)
# tether (rope to station)
tether = cube("eva_tether", size=1.0, loc=(-1.0, 0, 0), parent=eva_p, mat=MAT_STATION_DARK)
tether.scale = (2.0, 0.02, 0.02)

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

# station slow rotate
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(station, f, (0, tt * math.pi * 0.5, 0))  # 1/4 turn / loop

# Earth slowly rotates
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(earth_p, f, (0, tt * math.pi * 0.8, math.radians(20)))

# 6 solar panels tilt (track sun = +x direction)
for i, sp in enumerate(solar_panels):
    base_rot = sp.rotation_euler.copy()
    phase = i * 0.3
    for f in range(1, FRAMES + 1, 5):
        tt = (f - 1) / (FRAMES - 1)
        delta = math.radians(10) * math.sin(tt * math.pi * 1.5 + phase)
        kf_rot(sp, f, (base_rot[0] + delta, base_rot[1] + delta, base_rot[2]))

# 2 antennas pivot
for i, ap in enumerate(antennas):
    base_rot = ap.rotation_euler.copy()
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        delta = math.radians(20) * math.sin(tt * math.pi * 2.0 + i * 0.6)
        kf_rot(ap, f, (base_rot[0], delta, 0))

# stars twinkle
for i in range(60):
    star = bpy.data.objects.get(f"star_{i}")
    if not star:
        continue
    phase = star["_phase"]
    for f in range(1, FRAMES + 1, 6):
        tt = (f - 1) / (FRAMES - 1)
        local = (math.sin(tt * math.pi * 6.0 + phase * 0.13) + 1) * 0.5
        s = 0.7 + 0.5 * local
        kf_scale(star, f, (s, s, s))

# shuttle approaches the station
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    sx = 8.0 - tt * 3.0
    sy = 5.0 - tt * 0.3
    sz = -2.0 + tt * 1.5
    kf_loc(shuttle, f, (sx, sy, sz))
    # slight banking
    tilt = math.radians(5) * math.sin(tt * math.pi * 4.0)
    kf_rot(shuttle, f, (tilt, math.radians(180), 0))

# 2 satellites slow drift
for sp in satellites:
    base = (sp.location.x, sp.location.y, sp.location.z)
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        dx = base[0] + 0.3 * math.sin(tt * math.pi * 2.0)
        dz = base[2] + 0.3 * math.cos(tt * math.pi * 2.0)
        kf_loc(sp, f, (dx, base[1], dz))
        kf_rot(sp, f, (0, tt * math.pi * 1.0, 0))

# astronaut EVA floats subtle
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    dx = 5.0 + 0.3 * math.sin(tt * math.pi * 2.0)
    dy = 5.5 + 0.2 * math.sin(tt * math.pi * 3.0)
    dz = 1.5 + 0.2 * math.cos(tt * math.pi * 2.5)
    kf_loc(eva_p, f, (dx, dy, dz))
    # slight tumble
    kf_rot(eva_p, f, (math.radians(5) * math.sin(tt * math.pi * 4.0), tt * math.pi * 0.4, 0))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_spacestation] wrote {OUT}")
