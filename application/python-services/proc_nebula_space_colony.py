"""
proc_nebula_space_colony.py — 181e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Colonie spatiale dans nébuleuse multicolore :
- station spatiale modulaire 12 modules + 4 solar arrays + antennes + docking bay
- 3 vaisseaux orbitant
- 6 cargo ships
- 30 asteroids
- nébuleuse 4 zones colorées (rose/bleu/violet/vert)
- 200 étoiles
- 1 planète géante avec anneaux
- 3 lunes
- sun étoile distante
- 4 comètes traçantes
- 4 satellites

Animations multi-axes simultanées :
- station rotation lente Y continue
- 4 solar arrays tracking
- 3 vaisseaux orbits différentiels
- 6 cargo ships drift
- 30 asteroids rotate XYZ continue + drift
- planète rotate Y + 3 lunes orbit
- 4 comètes traverse linear + tail trails
- 4 satellites blink

Sortie : output/3d/pbr_nebula_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_nebula_proc.glb"))

random.seed(0xBE5C01)


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
MAT_SPACE = make_mat("space", (0.01, 0.01, 0.03), roughness=1.0, emi=(0.02, 0.02, 0.05), emi_strength=0.4)
MAT_STAR = make_mat("star", (1.0, 1.0, 0.95), roughness=0.0, emi=(1.0, 1.0, 0.95), emi_strength=5.0)
MAT_NEBULA_PINK = make_mat("nebula_pink", (0.95, 0.30, 0.55), roughness=0.0, alpha=0.40, emi=(0.95, 0.30, 0.55), emi_strength=6.0)
MAT_NEBULA_BLUE = make_mat("nebula_blue", (0.30, 0.45, 0.95), roughness=0.0, alpha=0.40, emi=(0.30, 0.45, 0.95), emi_strength=6.0)
MAT_NEBULA_PURPLE = make_mat("nebula_purple", (0.65, 0.25, 0.95), roughness=0.0, alpha=0.40, emi=(0.65, 0.25, 0.95), emi_strength=6.0)
MAT_NEBULA_GREEN = make_mat("nebula_green", (0.30, 0.95, 0.55), roughness=0.0, alpha=0.40, emi=(0.30, 0.95, 0.55), emi_strength=6.0)
MAT_SUN_DISTANT = make_mat("sun_distant", (1.0, 0.85, 0.40), roughness=0.0, emi=(1.0, 0.85, 0.40), emi_strength=15.0)
MAT_STATION_HULL = make_mat("station_hull", (0.65, 0.65, 0.70), metallic=0.85, roughness=0.30, emi=(0.25, 0.25, 0.28), emi_strength=0.4)
MAT_STATION_DARK = make_mat("station_dark", (0.30, 0.30, 0.35), metallic=0.7, roughness=0.45)
MAT_STATION_BRIGHT = make_mat("station_bright", (0.95, 0.95, 0.95), metallic=0.95, roughness=0.15, emi=(0.45, 0.45, 0.48), emi_strength=0.8)
MAT_SOLAR_PANEL = make_mat("solar_panel", (0.15, 0.20, 0.45), roughness=0.10, emi=(0.20, 0.35, 0.65), emi_strength=2.5)
MAT_WINDOW_GLOW = make_mat("window_glow", (0.95, 0.85, 0.50), roughness=0.0, emi=(0.95, 0.85, 0.50), emi_strength=10.0)
MAT_ENGINE_GLOW = make_mat("engine_glow", (0.30, 0.85, 1.0), roughness=0.0, emi=(0.30, 0.85, 1.0), emi_strength=13.0)
MAT_ANTENNA = make_mat("antenna", (0.55, 0.50, 0.50), metallic=0.7, roughness=0.40, emi=(0.20, 0.18, 0.18), emi_strength=0.3)
MAT_SHIP_BODY = make_mat("ship_body", (0.55, 0.60, 0.65), metallic=0.80, roughness=0.35)
MAT_SHIP_RED = make_mat("ship_red", (0.85, 0.30, 0.20), roughness=0.5, emi=(0.40, 0.10, 0.05), emi_strength=0.5)
MAT_SHIP_BLUE = make_mat("ship_blue", (0.20, 0.40, 0.85), roughness=0.5, emi=(0.05, 0.15, 0.40), emi_strength=0.5)
MAT_CARGO = make_mat("cargo", (0.45, 0.35, 0.25), roughness=0.6, emi=(0.18, 0.12, 0.08), emi_strength=0.3)
MAT_ASTEROID = make_mat("asteroid", (0.30, 0.25, 0.22), roughness=0.95)
MAT_PLANET_OCEAN = make_mat("planet_ocean", (0.15, 0.35, 0.55), roughness=0.5, emi=(0.05, 0.15, 0.25), emi_strength=0.6)
MAT_PLANET_LAND = make_mat("planet_land", (0.40, 0.55, 0.30), roughness=0.7, emi=(0.15, 0.20, 0.10), emi_strength=0.4)
MAT_PLANET_CLOUDS = make_mat("planet_clouds", (0.95, 0.92, 0.88), roughness=0.7, alpha=0.55, emi=(0.45, 0.45, 0.42), emi_strength=0.4)
MAT_PLANET_RING = make_mat("planet_ring", (0.65, 0.55, 0.45), roughness=0.5, alpha=0.75, emi=(0.30, 0.25, 0.20), emi_strength=0.5)
MAT_MOON_A = make_mat("moon_A", (0.85, 0.80, 0.75), roughness=0.6, emi=(0.30, 0.28, 0.25), emi_strength=0.4)
MAT_MOON_B = make_mat("moon_B", (0.55, 0.45, 0.55), roughness=0.7, emi=(0.20, 0.15, 0.20), emi_strength=0.4)
MAT_MOON_C = make_mat("moon_C", (0.65, 0.55, 0.30), roughness=0.6, emi=(0.25, 0.20, 0.10), emi_strength=0.4)
MAT_COMET = make_mat("comet", (0.85, 0.95, 1.0), roughness=0.0, emi=(0.85, 0.95, 1.0), emi_strength=12.0)
MAT_COMET_TAIL = make_mat("comet_tail", (0.55, 0.75, 1.0), roughness=0.0, alpha=0.40, emi=(0.55, 0.75, 1.0), emi_strength=8.0)
MAT_SATELLITE = make_mat("satellite", (0.80, 0.80, 0.85), metallic=0.7, roughness=0.40)
MAT_SAT_LIGHT = make_mat("sat_light", (1.0, 0.30, 0.30), roughness=0.0, emi=(1.0, 0.30, 0.30), emi_strength=10.0)


# --- backdrop : space + nebula -------------------------------------------
sky = beveled_cube("space_back", (55, 0.2, 32), bevel_offset=0.05, bevel_segments=2, loc=(0, 18, 14), mat=MAT_SPACE)

# 4 NEBULA zones (multi-layered glow clouds)
NEBULA_MATS = [MAT_NEBULA_PINK, MAT_NEBULA_BLUE, MAT_NEBULA_PURPLE, MAT_NEBULA_GREEN]
nebula_clouds = []
for ni in range(4):
    nmat = NEBULA_MATS[ni]
    # central position per zone
    nz_x = -12 + (ni % 2) * 24
    nz_y = 8 + (ni // 2) * 8
    np_obj = empty(f"nebula_{ni}_p", (nz_x, nz_y, 12))
    nebula_clouds.append(np_obj)
    # cluster of glow blobs forming nebula zone
    for j in range(8):
        bx = random.uniform(-4, 4)
        by = random.uniform(-3, 3)
        bz = random.uniform(-1, 1)
        smooth_sphere(f"nebula_{ni}_b_{j}", r=random.uniform(1.5, 2.5), segs=18, rings=14, loc=(bx, by, bz), parent=np_obj, mat=nmat, scale=(1.0, 1.0, 0.30))
    np_obj["_phase"] = ni * 0.30

# 200 ÉTOILES distantes
for i in range(200):
    smooth_sphere(f"star_{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6, loc=(random.uniform(-25, 25), random.uniform(2, 17), random.uniform(8, 17)), mat=MAT_STAR)

# DISTANT SUN
sun_p = empty("sun_distant_p", (15, 14, 14))
smooth_sphere("sun_distant", r=1.2, segs=22, rings=16, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_DISTANT)


# --- STATION SPATIALE modulaire géante --------------------------------
station_p = empty("station", (0, 6, 2))

# 12 MODULES cylindrical
# central core (large cylinder horizontal)
core = smooth_cone("station_core", r1=0.85, r2=0.85, depth=4.0, segs=20, loc=(0, 0, 0), parent=station_p, mat=MAT_STATION_HULL)
core.rotation_euler = (0, 0, math.radians(90))

# 4 modules autour
for mk in range(4):
    ma = mk * (math.pi * 2 / 4)
    mx_off = math.cos(ma) * 1.5
    mz_off = math.sin(ma) * 1.5
    mod = smooth_cone(f"station_mod_{mk}", r1=0.50, r2=0.50, depth=2.5, segs=14, loc=(mx_off, 0, mz_off), parent=station_p, mat=MAT_STATION_DARK)
    mod.rotation_euler = (0, 0, math.radians(90))
    # connector to core
    conn = smooth_cone(f"station_conn_{mk}", r1=0.15, r2=0.15, depth=0.7, segs=10, loc=(mx_off * 0.55, 0, mz_off * 0.55), parent=station_p, mat=MAT_STATION_DARK)
    conn.rotation_euler = (0, 0, math.atan2(-mz_off, mx_off))

# 4 modules secondaires
for mk in range(4):
    ma = mk * (math.pi * 2 / 4) + math.pi / 4
    mx_off = math.cos(ma) * 2.5
    mz_off = math.sin(ma) * 2.5
    smooth_cone(f"station_mod2_{mk}", r1=0.30, r2=0.30, depth=1.8, segs=12, loc=(mx_off, 0, mz_off), parent=station_p, mat=MAT_STATION_BRIGHT)

# 8 windows émissifs sur core
for wk in range(8):
    wa = wk * (math.pi * 2 / 8)
    smooth_sphere(f"station_win_{wk}", r=0.10, segs=10, rings=6, loc=(math.cos(wa) * 0.86, 0, math.sin(wa) * 0.86), parent=station_p, mat=MAT_WINDOW_GLOW)

# DOCKING BAY (front opening)
docking_p = empty("docking_p", (0, 0, 2.5), parent=station_p)
beveled_cube("docking_frame", (1.0, 0.80, 0.30), bevel_offset=0.04, bevel_segments=2, loc=(0, 0, 0), parent=docking_p, mat=MAT_STATION_DARK)
# inside glow
smooth_sphere("docking_glow", r=0.40, segs=14, rings=10, loc=(0, 0, -0.15), parent=docking_p, mat=MAT_ENGINE_GLOW, scale=(1.0, 0.7, 0.30))

# 4 SOLAR ARRAYS (large panels, parented for tracking)
solar_arrays = []
for sk in range(4):
    sa = sk * (math.pi * 2 / 4) + math.pi / 8
    sx = math.cos(sa) * 1.0
    sz = math.sin(sa) * 1.0
    # arm
    arm = smooth_cone(f"solar_arm_{sk}", r1=0.06, r2=0.06, depth=2.0, segs=8, loc=(sx * 1.5, 0.85, sz * 1.5), parent=station_p, mat=MAT_STATION_DARK)
    arm.rotation_euler = (math.radians(90), 0, 0)
    # solar panel (rotating tracker)
    panel_p = empty(f"solar_panel_p_{sk}", (sx * 1.5, 2.0, sz * 1.5), parent=station_p)
    solar_arrays.append({"p": panel_p, "phase": sk * 0.30})
    panel = beveled_cube(f"solar_panel_{sk}", (2.0, 0.05, 1.5), bevel_offset=0.03, bevel_segments=2, loc=(0, 0, 0), parent=panel_p, mat=MAT_SOLAR_PANEL)
    # 4 cell divisions
    for cd in range(3):
        beveled_cube(f"solar_div_{sk}_{cd}", (2.0, 0.01, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.05, -0.5 + cd * 0.5), parent=panel_p, mat=MAT_STATION_DARK)
    # support frame
    beveled_cube(f"solar_frame_{sk}", (2.1, 0.08, 1.6), bevel_offset=0.02, bevel_segments=2, loc=(0, -0.04, 0), parent=panel_p, mat=MAT_STATION_BRIGHT)

# ANTENNES communication
for ak in range(3):
    aa = ak * (math.pi * 2 / 3) + 0.3
    ax = math.cos(aa) * 0.5
    az = math.sin(aa) * 0.5
    smooth_cone(f"antenna_{ak}", r1=0.03, r2=0.0, depth=1.5, segs=6, loc=(ax, 1.5, az), parent=station_p, mat=MAT_ANTENNA)
    # dish at top
    smooth_cone(f"antenna_{ak}_dish", r1=0.20, r2=0.10, depth=0.10, segs=10, loc=(ax, 2.25, az), parent=station_p, mat=MAT_STATION_BRIGHT)


# --- 3 VAISSEAUX orbitant ---------------------------------------------
ships = []
SHIP_MATS = [MAT_SHIP_RED, MAT_SHIP_BLUE, MAT_SHIP_RED]
for si in range(3):
    a = si * (math.pi * 2 / 3) + 0.5
    r = random.uniform(5, 8)
    by = random.uniform(4, 9)
    sp = empty(f"ship_{si}_p", (math.cos(a) * r, by, math.sin(a) * r))
    ships.append({"p": sp, "a": a, "r": r, "by": by, "phase": si * 0.50})
    # main body (oval)
    smooth_sphere(f"ship_{si}_body", r=0.40, segs=20, rings=14, loc=(0, 0, 0), parent=sp, mat=MAT_SHIP_BODY, scale=(2.5, 0.6, 0.85))
    # accent stripe (red/blue)
    smooth_sphere(f"ship_{si}_accent", r=0.30, segs=16, rings=10, loc=(0, 0.10, 0), parent=sp, mat=SHIP_MATS[si], scale=(2.4, 0.10, 0.85))
    # cockpit dome
    smooth_sphere(f"ship_{si}_cockpit", r=0.20, segs=14, rings=10, loc=(0.45, 0.15, 0), parent=sp, mat=MAT_WINDOW_GLOW, scale=(1.0, 0.85, 0.85))
    # engine glow back
    smooth_sphere(f"ship_{si}_engine", r=0.15, segs=12, rings=8, loc=(-1.0, 0, 0), parent=sp, mat=MAT_ENGINE_GLOW)
    # 2 wings small
    for wk, wz in [(0, 0.35), (1, -0.35)]:
        beveled_cube(f"ship_{si}_wing_{wk}", (0.50, 0.04, 0.30), bevel_offset=0.02, bevel_segments=2, loc=(-0.20, -0.05, wz), parent=sp, mat=SHIP_MATS[si])


# --- 6 CARGO SHIPS ----------------------------------------------------
cargos = []
for ci in range(6):
    a = ci * (math.pi * 2 / 6) + 0.7
    r = random.uniform(10, 14)
    by = random.uniform(2, 10)
    cp = empty(f"cargo_{ci}_p", (math.cos(a) * r, by, math.sin(a) * r))
    cargos.append({"p": cp, "a": a, "r": r, "by": by, "phase": ci * 0.30})
    # body box
    beveled_cube(f"cargo_{ci}_body", (1.5, 0.40, 0.55), bevel_offset=0.04, bevel_segments=2, loc=(0, 0, 0), parent=cp, mat=MAT_CARGO)
    # 4 container blocks
    for bk in range(4):
        beveled_cube(f"cargo_{ci}_box_{bk}", (0.30, 0.30, 0.30), bevel_offset=0.02, bevel_segments=2, loc=(-0.50 + bk * 0.33, 0.25, 0), parent=cp, mat=MAT_STATION_DARK)
    # engine glow
    smooth_sphere(f"cargo_{ci}_engine", r=0.12, segs=10, rings=8, loc=(-0.85, 0, 0), parent=cp, mat=MAT_ENGINE_GLOW)


# --- 30 ASTEROIDS -----------------------------------------------------
asteroids = []
for ak in range(30):
    a = ak * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(8, 17)
    by = random.uniform(1, 13)
    asp = empty(f"ast_{ak}_p", (math.cos(a) * r, by, math.sin(a) * r))
    asteroids.append({"p": asp, "phase": ak * 0.12, "base": (math.cos(a) * r, by, math.sin(a) * r)})
    # irregular shape (cluster of small spheres)
    main_r = random.uniform(0.25, 0.55)
    smooth_sphere(f"ast_{ak}_main", r=main_r, segs=14, rings=10, loc=(0, 0, 0), parent=asp, mat=MAT_ASTEROID, scale=(1.0, 0.85, 1.1))
    # 3 bumps
    for bk in range(3):
        ba = bk * (math.pi * 2 / 3)
        smooth_sphere(f"ast_{ak}_b_{bk}", r=random.uniform(0.10, 0.20), segs=10, rings=6, loc=(math.cos(ba) * main_r * 0.7, math.sin(ba) * main_r * 0.5, 0), parent=asp, mat=MAT_ASTEROID, scale=(1.0, 0.85, 1.0))


# --- PLANÈTE GÉANTE avec anneaux -------------------------------------
planet_p = empty("planet", (-12, 4, 5))
# main planet
smooth_sphere("planet_ocean", r=2.0, segs=28, rings=20, loc=(0, 0, 0), parent=planet_p, mat=MAT_PLANET_OCEAN)
# 5 land continents (random patches)
for ck in range(5):
    ca = ck * (math.pi * 2 / 5) + random.uniform(-0.3, 0.3)
    cp_lat = random.uniform(-0.6, 0.6)
    cx = 2.0 * math.cos(ca) * math.sqrt(1 - cp_lat ** 2)
    cz = 2.0 * math.sin(ca) * math.sqrt(1 - cp_lat ** 2)
    cy = 2.0 * cp_lat
    smooth_sphere(f"planet_cont_{ck}", r=random.uniform(0.6, 1.0), segs=14, rings=10, loc=(cx, cy, cz), parent=planet_p, mat=MAT_PLANET_LAND, scale=(1.0, 0.15, 1.0))
# cloud band atmosphere
smooth_sphere("planet_cloud", r=2.10, segs=24, rings=16, loc=(0, 0, 0), parent=planet_p, mat=MAT_PLANET_CLOUDS)
# rings (3 layers)
ring_p = empty("ring_p", (0, 0, 0), parent=planet_p)
ring_p.rotation_euler = (math.radians(20), 0, math.radians(15))
for rk in range(3):
    rr = 3.5 + rk * 0.5
    smooth_cone(f"planet_ring_{rk}", r1=rr, r2=rr * 1.02, depth=0.05, segs=32, loc=(0, 0, 0), parent=ring_p, mat=MAT_PLANET_RING)


# --- 3 LUNES orbitant planète ---------------------------------------
moons = []
MOON_MATS = [MAT_MOON_A, MAT_MOON_B, MAT_MOON_C]
for mk in range(3):
    ma = mk * (math.pi * 2 / 3)
    mr = 4.5 + mk * 0.8
    mp = empty(f"moon_{mk}_p", (math.cos(ma) * mr, 0, math.sin(ma) * mr), parent=planet_p)
    moons.append({"p": mp, "a": ma, "r": mr, "phase": mk * 0.40})
    smooth_sphere(f"moon_{mk}", r=random.uniform(0.30, 0.55), segs=18, rings=14, loc=(0, 0, 0), parent=mp, mat=MOON_MATS[mk])


# --- 4 COMÈTES traçantes ------------------------------------------
comets = []
for ck in range(4):
    cx = random.uniform(-15, 15)
    cy = random.uniform(8, 14)
    cz = random.uniform(8, 14)
    cp = empty(f"comet_{ck}_p", (cx, cy, cz))
    comets.append({"p": cp, "base": (cx, cy, cz), "phase": ck * 0.40, "dx": random.uniform(0.5, 1.0)})
    # head
    smooth_sphere(f"comet_{ck}_head", r=0.20, segs=14, rings=10, loc=(0, 0, 0), parent=cp, mat=MAT_COMET)
    # tail (elongated cone)
    tail = smooth_cone(f"comet_{ck}_tail", r1=0.0, r2=0.18, depth=2.5, segs=10, loc=(-1.25, 0, 0), parent=cp, mat=MAT_COMET_TAIL)
    tail.rotation_euler = (0, 0, math.radians(-90))


# --- 4 SATELLITES ---------------------------------------------------
satellites = []
for st in range(4):
    a = st * (math.pi * 2 / 4) + 0.5
    r = 6
    by = random.uniform(4, 10)
    sp = empty(f"sat_{st}_p", (math.cos(a) * r, by, math.sin(a) * r))
    satellites.append({"p": sp, "a": a, "r": r, "by": by, "phase": st * 0.30})
    # body
    beveled_cube(f"sat_{st}_body", (0.30, 0.20, 0.20), bevel_offset=0.03, bevel_segments=2, loc=(0, 0, 0), parent=sp, mat=MAT_SATELLITE)
    # 2 solar panels small
    for sk, sz_off in [(0, 0.30), (1, -0.30)]:
        beveled_cube(f"sat_{st}_p_{sk}", (0.40, 0.02, 0.18), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, sz_off), parent=sp, mat=MAT_SOLAR_PANEL)
    # blinking light
    bl = smooth_sphere(f"sat_{st}_light", r=0.04, segs=8, rings=6, loc=(0.18, 0.12, 0), parent=sp, mat=MAT_SAT_LIGHT)
    satellites[st]["light"] = bl


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

    # STATION rotation lente continue
    kf(station_p, f, "rotation_euler", (0, math.radians(60 * tt * 360 / 360), math.radians(3 * math.sin(2 * math.pi * tt * 0.5))))

    # 4 SOLAR ARRAYS tracking
    for sa in solar_arrays:
        ph = sa["phase"]
        # track sun (slight rotation)
        tracking = math.radians(30 * math.sin(2 * math.pi * tt * 0.3 + ph * math.pi))
        kf(sa["p"], f, "rotation_euler", (tracking, 0, 0))

    # 3 vaisseaux orbits
    for sh in ships:
        ang = sh["a"] + tt * 2 * math.pi * 0.4
        bx = math.cos(ang) * sh["r"]
        bz = math.sin(ang) * sh["r"]
        by = sh["by"] + 0.4 * math.sin(2 * math.pi * tt * 1.2 + sh["phase"])
        kf(sh["p"], f, "location", (bx, by, bz))
        kf(sh["p"], f, "rotation_euler", (0, ang + math.pi / 2, math.radians(8 * math.sin(2 * math.pi * tt * 1.5 + sh["phase"]))))

    # 6 cargo ships drift
    for cg in cargos:
        ang = cg["a"] + tt * 2 * math.pi * 0.2
        bx = math.cos(ang) * cg["r"]
        bz = math.sin(ang) * cg["r"]
        by = cg["by"] + 0.30 * math.sin(2 * math.pi * tt * 1.0 + cg["phase"])
        kf(cg["p"], f, "location", (bx, by, bz))
        kf(cg["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))

    # 30 asteroids rotate XYZ + drift
    for ast in asteroids:
        bx_, by_, bz_ = ast["base"]
        ph = ast["phase"]
        ny = by_ + 0.4 * math.sin(2 * math.pi * tt * 0.5 + ph * math.pi)
        nx = bx_ + 0.3 * math.cos(2 * math.pi * tt * 0.4 + ph * math.pi)
        kf(ast["p"], f, "location", (nx, ny, bz_))
        kf(ast["p"], f, "rotation_euler", (math.radians(180 * tt + ph * 30), math.radians(120 * tt + ph * 40), math.radians(90 * tt + ph * 20)))

    # PLANÈTE rotate Y + 3 LUNES orbit
    kf(planet_p, f, "rotation_euler", (0, math.radians(40 * tt * 360 / 360), 0))
    for mn in moons:
        ang = mn["a"] + tt * 2 * math.pi * 0.7
        mx = math.cos(ang) * mn["r"]
        mz = math.sin(ang) * mn["r"]
        kf(mn["p"], f, "location", (mx, 0, mz))

    # 4 COMÈTES traverse linear
    for cm in comets:
        bx_, by_, bz_ = cm["base"]
        ph = cm["phase"]
        dx = cm["dx"]
        local = (tt * 0.5 + ph) % 1.0
        nx = bx_ - local * 30  # comet traverses screen
        if nx < -25:
            nx += 50
        kf(cm["p"], f, "location", (nx, by_, bz_))

    # 4 satellites orbit + blink
    for sat in satellites:
        ang = sat["a"] + tt * 2 * math.pi * 0.6
        bx = math.cos(ang) * sat["r"]
        bz = math.sin(ang) * sat["r"]
        by = sat["by"]
        kf(sat["p"], f, "location", (bx, by, bz))
        kf(sat["p"], f, "rotation_euler", (0, math.radians(360 * tt * 3), 0))
        # blink light
        blink = 1.0 + 0.5 * abs(math.sin(2 * math.pi * tt * 4 + sat["phase"]))
        kf(sat["light"], f, "scale", (blink, blink, blink))

    # 4 nebula zones gentle drift
    for ni, np_obj in enumerate(nebula_clouds):
        ph = np_obj["_phase"]
        ns = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 0.4 + ph * math.pi)
        kf(np_obj, f, "scale", (ns, ns, ns))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_nebula_space_colony] wrote {OUT}")
