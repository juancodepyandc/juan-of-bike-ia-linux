"""
proc_whale_breaching_ocean.py — 159e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Baleine à bosse breachant l'océan :
- corps baleine massive bevelé (4 segments tapered)
- tête + bouche fendue
- 2 yeux + 2 nageoires pectorales
- queue avec 2 lobes
- gorge plissée (ventral grooves) 12 lignes
- évent + jet d'eau émissif
- 6 baleineaux en arrière-plan
- 30 splashs water émissifs autour baleine
- 20 gouttes d'eau projetées
- 40 mouettes volant au ciel
- 3 bateaux d'observation
- soleil + halos émissifs
- ciel couchant orange-rose
- vagues animées (50 segments wave)
- récifs rocheux côté
- 25 nuages

Animations multi-axes simultanées :
- baleine breach : Y monte puis redescend + rotation X (head up arc) + bank Z
- queue swish synchronized
- 2 nageoires pectorales : balayage différentiel
- 30 splashs : éclatent au moment du retour eau (alpha + scale)
- 20 gouttes : trajectoires paraboliques
- 50 vagues segments : wave propagated
- 6 baleineaux : ondulations différentielles
- 40 mouettes : flap + orbit
- 3 bateaux : bob waves
- soleil pulse + halos breathe
- jet évent rise cyclique

Sortie : output/3d/pbr_whale_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_whale_proc.glb"))

random.seed(0xBA1EE5)


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
MAT_SKY = make_mat("sky_sunset", (1.0, 0.55, 0.30), roughness=1.0, emi=(0.65, 0.30, 0.20), emi_strength=1.0)
MAT_SUN = make_mat("sun", (1.0, 0.75, 0.30), roughness=0.0, emi=(1.0, 0.75, 0.30), emi_strength=12.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.75, 0.30), roughness=0.0, alpha=0.30, emi=(1.0, 0.75, 0.30), emi_strength=3.0)
MAT_CLOUD = make_mat("cloud", (0.95, 0.75, 0.65), roughness=1.0, alpha=0.65, emi=(0.45, 0.35, 0.30), emi_strength=0.4)
MAT_OCEAN = make_mat("ocean", (0.10, 0.30, 0.55), roughness=0.30, emi=(0.05, 0.15, 0.35), emi_strength=0.8)
MAT_OCEAN_LIGHT = make_mat("ocean_light", (0.30, 0.55, 0.75), roughness=0.20, alpha=0.85, emi=(0.20, 0.40, 0.60), emi_strength=1.0)
MAT_WAVE_TOP = make_mat("wave_top", (0.85, 0.95, 1.0), roughness=0.10, alpha=0.85, emi=(0.55, 0.75, 0.95), emi_strength=2.0)
MAT_WHALE_BODY = make_mat("whale_body", (0.18, 0.22, 0.28), roughness=0.4, emi=(0.06, 0.08, 0.10), emi_strength=0.3)
MAT_WHALE_BELLY = make_mat("whale_belly", (0.85, 0.85, 0.80), roughness=0.4, emi=(0.30, 0.30, 0.28), emi_strength=0.3)
MAT_WHALE_BARNACLE = make_mat("whale_barnacle", (0.55, 0.50, 0.45), roughness=0.85)
MAT_WHALE_EYE = make_mat("whale_eye", (0.05, 0.05, 0.05), roughness=0.0, emi=(0.20, 0.15, 0.10), emi_strength=4.0)
MAT_BABY_WHALE = make_mat("baby_whale", (0.25, 0.30, 0.35), roughness=0.4, emi=(0.10, 0.12, 0.14), emi_strength=0.4)
MAT_SPLASH = make_mat("splash", (0.95, 0.98, 1.0), roughness=0.10, alpha=0.75, emi=(0.70, 0.85, 1.0), emi_strength=2.5)
MAT_DROP = make_mat("drop", (0.75, 0.90, 1.0), roughness=0.05, alpha=0.65, emi=(0.55, 0.75, 1.0), emi_strength=2.0)
MAT_SEAGULL = make_mat("seagull", (0.95, 0.95, 0.90), roughness=0.5, emi=(0.40, 0.40, 0.35), emi_strength=0.3)
MAT_SEAGULL_DARK = make_mat("seagull_dark", (0.30, 0.25, 0.20), roughness=0.7)
MAT_BOAT_HULL = make_mat("boat_hull", (0.55, 0.30, 0.15), roughness=0.6)
MAT_BOAT_TRIM = make_mat("boat_trim", (0.85, 0.65, 0.30), metallic=0.4, roughness=0.40, emi=(0.30, 0.20, 0.08), emi_strength=0.4)
MAT_SAIL = make_mat("sail", (0.95, 0.92, 0.85), roughness=0.7, emi=(0.30, 0.28, 0.25), emi_strength=0.3)
MAT_ROCK = make_mat("rock", (0.30, 0.27, 0.25), roughness=0.95)
MAT_MOSS = make_mat("moss", (0.20, 0.40, 0.18), roughness=0.7, emi=(0.05, 0.15, 0.05), emi_strength=0.3)


# --- backdrop : sunset sky -------------------------------------------------
sky = beveled_cube("sky_back", (60, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 12), mat=MAT_SKY)

# sun + halos
sun_p = empty("sun_p", (8, 14, 8))
sun = smooth_sphere("sun", r=1.4, segs=28, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo_1 = smooth_sphere("sun_halo_1", r=2.1, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=3.0, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_3 = smooth_sphere("sun_halo_3", r=4.0, segs=18, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# 25 clouds drifting
clouds = []
for ck in range(25):
    a = ck * (math.pi * 2 / 25) + random.uniform(-0.2, 0.2)
    r = random.uniform(12, 20)
    cy = random.uniform(10, 15)
    cx = math.cos(a) * r * 0.7
    cz = math.sin(a) * r * 0.7 + random.uniform(-2, 0)
    cp = empty(f"cloud_{ck}", (cx, cy, cz))
    clouds.append(cp)
    for j in range(random.randint(3, 4)):
        smooth_sphere(f"cloud_{ck}_p_{j}", r=random.uniform(0.6, 1.0), segs=18, rings=12, loc=(random.uniform(-0.8, 0.8), random.uniform(-0.15, 0.2), random.uniform(-0.6, 0.6)), parent=cp, mat=MAT_CLOUD, scale=(1.0, 0.55, 1.0))
    cp["_base_x"] = cx
    cp["_speed"] = random.uniform(0.3, 0.7)


# --- ocean surface (50 wave segments grid) -------------------------------
ocean_p = empty("ocean_p", (0, 0, 0))
# main ocean plane
ocean = beveled_cube("ocean", (40, 0.2, 25), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 4), parent=ocean_p, mat=MAT_OCEAN)
# 50 wave crests (rows of cone segments)
wave_segs = []
for wk in range(50):
    wa = wk * (math.pi * 2 / 50)
    wr = random.uniform(5, 14)
    wx = math.cos(wa) * wr
    wz = math.sin(wa) * wr * 0.6 + random.uniform(-1, 1)
    if abs(wx) < 3.5 and abs(wz - 1) < 3.5:
        continue  # skip near whale impact zone
    wseg = smooth_cone(f"wave_{wk}", r1=0.45, r2=0.30, depth=0.20, segs=14, loc=(wx, 0.08, wz), parent=ocean_p, mat=MAT_WAVE_TOP)
    wseg.rotation_euler = (math.radians(90), 0, 0)
    wseg["_base_y"] = 0.08
    wseg["_phase"] = wk * 0.2
    wave_segs.append(wseg)


# --- rocky reef on side ---------------------------------------------------
reef_p = empty("reef_p", (-12, 0, 3))
for rk in range(5):
    a = rk * (math.pi * 2 / 5) + 0.5
    r = random.uniform(0.4, 1.0)
    rx = math.cos(a) * 0.8
    rz = math.sin(a) * 0.8
    rh = random.uniform(0.8, 1.6)
    rock = smooth_sphere(f"reef_{rk}", r=r, segs=14, rings=10, loc=(rx, rh / 2, rz), parent=reef_p, mat=MAT_ROCK, scale=(1.0, rh, 1.0))
    # moss
    smooth_sphere(f"reef_{rk}_moss", r=r * 0.95, segs=12, rings=8, loc=(rx, rh, rz), parent=reef_p, mat=MAT_MOSS, scale=(1.0, 0.15, 1.0))


# --- MAIN WHALE ----------------------------------------------------------
whale_p = empty("whale", (0, 1.0, 2.0))
# body : 4 tapered segments (head→tail)
body_segs = []
for bs in range(4):
    sx = 1.2 - bs * 0.18
    sy = 0.85 - bs * 0.05
    sz = 0.95 - bs * 0.08
    seg = smooth_sphere(f"whale_body_{bs}", r=0.75, segs=24, rings=18, loc=(-1.5 + bs * 0.9, 0, 0), parent=whale_p, mat=MAT_WHALE_BODY, scale=(sx, sy, sz))
    body_segs.append(seg)
    # belly highlight (smaller lighter sphere below)
    smooth_sphere(f"whale_belly_{bs}", r=0.50, segs=18, rings=14, loc=(-1.5 + bs * 0.9, -0.30, 0), parent=whale_p, mat=MAT_WHALE_BELLY, scale=(sx, 0.40, sz * 0.85))

# head (front bulge, scarred)
head = smooth_sphere("whale_head", r=0.85, segs=26, rings=20, loc=(-2.50, 0.10, 0), parent=whale_p, mat=MAT_WHALE_BODY, scale=(1.3, 0.95, 1.0))
# mouth split (jaw line)
jaw = smooth_sphere("whale_jaw", r=0.70, segs=22, rings=16, loc=(-2.60, -0.25, 0), parent=whale_p, mat=MAT_WHALE_BODY, scale=(1.4, 0.55, 0.95))

# 12 ventral grooves (under jaw — humpback signature)
for vk in range(12):
    vz = -0.50 + vk * (1.0 / 11)
    smooth_cone(f"groove_{vk}", r1=0.025, r2=0.020, depth=1.2, segs=6, loc=(-1.8, -0.40, vz), parent=whale_p, mat=MAT_WHALE_BELLY)

# 2 eyes
for ek, ez in [("L", 0.45), ("R", -0.45)]:
    smooth_sphere(f"whale_eye_{ek}", r=0.10, segs=14, rings=10, loc=(-2.30, 0.20, ez * 0.65), parent=whale_p, mat=MAT_WHALE_EYE)

# 2 pectoral fins (huge, signature humpback)
for fk, fz in [("L", 0.8), ("R", -0.8)]:
    fin_p = empty(f"fin_p_{fk}", (-1.5, -0.20, fz), parent=whale_p)
    fin_body = smooth_sphere(f"fin_{fk}", r=0.20, segs=18, rings=12, loc=(0, 0, fz * 0.5), parent=fin_p, mat=MAT_WHALE_BODY, scale=(2.0, 0.20, 1.0))
    # white edge (front)
    smooth_sphere(f"fin_{fk}_edge", r=0.15, segs=14, rings=10, loc=(0.15, 0.02, fz * 0.5), parent=fin_p, mat=MAT_WHALE_BELLY, scale=(1.8, 0.20, 0.4))

# tail (peduncle + 2 flukes)
tail_p = empty("tail_p", (2.0, 0, 0), parent=whale_p)
tail_peduncle = smooth_sphere("tail_pedunc", r=0.30, segs=18, rings=14, loc=(0, 0, 0), parent=tail_p, mat=MAT_WHALE_BODY, scale=(1.5, 0.35, 0.5))
# 2 fluke lobes (left + right)
for fk, fz in [("L", 0.6), ("R", -0.6)]:
    smooth_sphere(f"fluke_{fk}", r=0.25, segs=16, rings=12, loc=(0.20, 0, fz), parent=tail_p, mat=MAT_WHALE_BODY, scale=(1.4, 0.15, 1.5))
    # white edge underside
    smooth_sphere(f"fluke_{fk}_edge", r=0.20, segs=14, rings=10, loc=(0.20, -0.05, fz), parent=tail_p, mat=MAT_WHALE_BELLY, scale=(1.4, 0.10, 1.4))

# 6 barnacles on head
for bk in range(6):
    ba = bk * (math.pi * 2 / 6)
    bx = -2.55 + math.cos(ba) * 0.2
    by = 0.30 + math.sin(ba) * 0.15
    bz = math.cos(ba) * 0.6
    smooth_sphere(f"barnacle_{bk}", r=0.06, segs=10, rings=8, loc=(bx, by, bz), parent=whale_p, mat=MAT_WHALE_BARNACLE)

# blowhole + jet
blowhole = smooth_sphere("blowhole", r=0.10, segs=12, rings=8, loc=(-1.80, 0.65, 0), parent=whale_p, mat=MAT_WHALE_EYE, scale=(1.5, 0.30, 1.0))
# water jet (4 spray puffs)
jet_puffs = []
for jk in range(4):
    jp = smooth_sphere(f"jet_{jk}", r=0.15, segs=14, rings=10, loc=(-1.80, 0.80 + jk * 0.40, 0), parent=whale_p, mat=MAT_SPLASH, scale=(1.0, 1.0, 1.0))
    jp["_phase"] = jk * 0.25
    jet_puffs.append(jp)


# --- 30 splashs around whale ---------------------------------------------
splashes = []
for sk in range(30):
    a = sk * (math.pi * 2 / 30) + random.uniform(-0.1, 0.1)
    r = random.uniform(2.0, 3.5)
    sx = math.cos(a) * r
    sz = math.sin(a) * r + 2
    sp_obj = smooth_sphere(f"splash_{sk}", r=random.uniform(0.10, 0.20), segs=12, rings=8, loc=(sx, 0.10, sz), mat=MAT_SPLASH, scale=(1.0, 0.30, 1.0))
    sp_obj["_phase"] = sk * 0.12
    sp_obj["_a"] = a
    sp_obj["_r"] = r
    splashes.append(sp_obj)


# --- 20 droplets parabolic trajectories ----------------------------------
droplets = []
for dk in range(20):
    a = dk * (math.pi * 2 / 20)
    dp = smooth_sphere(f"drop_{dk}", r=0.06, segs=10, rings=6, loc=(math.cos(a) * 2.5, 0.5, math.sin(a) * 2.5 + 2), mat=MAT_DROP)
    dp["_phase"] = dk * 0.15
    dp["_a"] = a
    dp["_speed"] = random.uniform(0.8, 1.5)
    droplets.append(dp)


# --- 6 baby whales arrière-plan -----------------------------------------
babies = []
for bk in range(6):
    a = bk * (math.pi * 2 / 6) + random.uniform(-0.3, 0.3)
    r = random.uniform(8, 13)
    bx = math.cos(a) * r
    bz = math.sin(a) * r * 0.6
    bp = empty(f"baby_whale_{bk}", (bx, 0.20, bz))
    babies.append(bp)
    # 3 body segments
    for bs in range(3):
        sx = 0.6 - bs * 0.10
        smooth_sphere(f"baby_{bk}_b_{bs}", r=0.35, segs=18, rings=12, loc=(-0.5 + bs * 0.35, 0, 0), parent=bp, mat=MAT_BABY_WHALE, scale=(sx, 0.5, 0.6))
    # tail
    smooth_sphere(f"baby_{bk}_tail", r=0.15, segs=14, rings=10, loc=(0.50, 0, 0), parent=bp, mat=MAT_BABY_WHALE, scale=(1.0, 0.10, 1.5))
    bp["_phase"] = bk * 0.6
    bp["_base_x"] = bx
    bp["_base_z"] = bz


# --- 40 seagulls volant ---------------------------------------------------
seagulls = []
for sk in range(40):
    a = sk * (math.pi * 2 / 40) + random.uniform(-0.2, 0.2)
    r = random.uniform(7, 15)
    sy = random.uniform(3, 9)
    sx = math.cos(a) * r
    sz = math.sin(a) * r * 0.7
    sp = empty(f"seagull_{sk}", (sx, sy, sz))
    # body
    smooth_sphere(f"sg_{sk}_body", r=0.10, segs=12, rings=8, loc=(0, 0, 0), parent=sp, mat=MAT_SEAGULL, scale=(1.4, 0.7, 0.7))
    # 2 wings
    wL = empty(f"sg_{sk}_wL", (0, 0.02, 0.05), parent=sp)
    wR = empty(f"sg_{sk}_wR", (0, 0.02, -0.05), parent=sp)
    smooth_sphere(f"sg_{sk}_wL_b", r=0.10, segs=10, rings=6, loc=(0, 0, 0.15), parent=wL, mat=MAT_SEAGULL, scale=(0.5, 0.05, 1.5))
    smooth_sphere(f"sg_{sk}_wR_b", r=0.10, segs=10, rings=6, loc=(0, 0, -0.15), parent=wR, mat=MAT_SEAGULL, scale=(0.5, 0.05, 1.5))
    # head + dark cap
    smooth_sphere(f"sg_{sk}_head", r=0.06, segs=10, rings=6, loc=(0.10, 0.02, 0), parent=sp, mat=MAT_SEAGULL)
    seagulls.append({"p": sp, "wL": wL, "wR": wR, "a": a, "r": r, "by": sy, "phase": sk * 0.3})


# --- 3 observation boats -------------------------------------------------
boats = []
BOAT_POSITIONS = [(8, 0.30, 4), (-7, 0.30, 5), (10, 0.30, -1)]
for bi, (bx, by, bz) in enumerate(BOAT_POSITIONS):
    bp = empty(f"boat_{bi}", (bx, by, bz))
    boats.append(bp)
    # hull (tapered)
    hull = smooth_sphere(f"boat_{bi}_hull", r=0.55, segs=18, rings=12, loc=(0, 0.10, 0), parent=bp, mat=MAT_BOAT_HULL, scale=(1.6, 0.40, 0.85))
    # deck
    deck = beveled_cube(f"boat_{bi}_deck", (1.4, 0.06, 0.7), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.30, 0), parent=bp, mat=MAT_BOAT_TRIM)
    # cabin
    cabin = beveled_cube(f"boat_{bi}_cabin", (0.55, 0.30, 0.45), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.50, 0), parent=bp, mat=MAT_BOAT_HULL)
    # mast
    smooth_cone(f"boat_{bi}_mast", r1=0.04, r2=0.03, depth=1.4, segs=8, loc=(0, 1.10, 0), parent=bp, mat=MAT_BOAT_TRIM)
    # sail (small triangle)
    smooth_cone(f"boat_{bi}_sail", r1=0.0, r2=0.40, depth=0.8, segs=8, loc=(-0.20, 1.20, 0), parent=bp, mat=MAT_SAIL)
    bp["_base_x"] = bx
    bp["_phase"] = bi * 0.7


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

    # whale breaching arc :  tt 0..0.5 = ascend, 0.5..1.0 = descend
    # using sin curve
    breach_y = 1.0 + 5.5 * math.sin(math.pi * tt) - 1.0  # peak at tt=0.5
    breach_y = max(-0.5, breach_y)
    # rotation : head up during ascent, head down during descent
    breach_rot_x = math.radians(-30) * math.sin(math.pi * tt + math.pi / 2)
    # bank
    bank_z = math.radians(15) * math.sin(2 * math.pi * tt * 1.5)
    # forward drift slight
    breach_x = -1.0 * math.sin(math.pi * tt) * 0.5
    kf(whale_p, f, "location", (breach_x, breach_y, 2.0))
    kf(whale_p, f, "rotation_euler", (breach_rot_x, math.radians(45 * math.sin(2 * math.pi * tt * 0.4)), bank_z))

    # tail swish
    tail_swish = math.radians(25) * math.sin(2 * math.pi * tt * 2)
    kf(tail_p, f, "rotation_euler", (0, tail_swish, math.radians(15 * math.cos(2 * math.pi * tt * 2.5))))

    # 2 pectoral fins flap differential
    # (re-find by name — simpler is recompute angle)
    # Since fins are children of whale_p via fin_p_L/R, we need to update their euler.
    # Use bpy.data.objects
    fin_L_p = bpy.data.objects.get("fin_p_L")
    fin_R_p = bpy.data.objects.get("fin_p_R")
    if fin_L_p:
        kf(fin_L_p, f, "rotation_euler", (math.radians(40 * math.sin(2 * math.pi * tt * 1.5)), 0, 0))
    if fin_R_p:
        kf(fin_R_p, f, "rotation_euler", (math.radians(40 * math.sin(2 * math.pi * tt * 1.5 + math.pi)), 0, 0))

    # blowhole jet : puffs rise + scale
    for jp in jet_puffs:
        ph = jp["_phase"]
        local = (tt * 2 + ph) % 1.0
        ny = 0.80 + local * 1.5
        sc = 1.0 + local * 1.0
        kf(jp, f, "location", (-1.80, ny, 0))
        kf(jp, f, "scale", (sc, sc, sc))

    # 30 splashs : pulse at certain tt (around whale impact)
    for sp in splashes:
        ph = sp["_phase"]
        # active when whale near water level (tt near 0, 0.5 or 1)
        impact = math.sin(math.pi * tt) ** 2  # peaks at 0.5
        local = (tt * 3 + ph) % 1.0
        sc = 0.5 + impact * 1.5 + 0.3 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        ny = 0.10 + impact * 0.5 + local * 0.4
        kf(sp, f, "location", (sp.location.x if f > 1 else sp.location.x, ny, sp.location.z if f > 1 else sp.location.z))
        kf(sp, f, "scale", (sc, sc * 0.6, sc))

    # 20 droplets parabolic
    for dp in droplets:
        ph = dp["_phase"]
        a = dp["_a"]
        spd = dp["_speed"]
        local = (tt * spd + ph) % 1.0
        # parabolic : y = 4 * local * (1 - local)
        py = 0.5 + 4.0 * local * (1 - local)
        rad = 2.5 + local * 1.5
        px = math.cos(a) * rad
        pz = math.sin(a) * rad + 2
        kf(dp, f, "location", (px, py, pz))

    # 50 wave segments wave
    for ws in wave_segs:
        ph = ws["_phase"]
        ny = ws["_base_y"] + 0.25 * math.sin(2 * math.pi * tt * 1.8 + ph * math.pi)
        kf(ws, f, "location", (ws.location.x if f > 1 else ws.location.x, ny, ws.location.z if f > 1 else ws.location.z))
        sc = 1.0 + 0.12 * math.sin(2 * math.pi * tt * 2.5 + ph * math.pi)
        kf(ws, f, "scale", (sc, sc, sc))

    # 6 baby whales : ondulate Y + sway
    for bd in babies:
        ph = bd["_phase"]
        nyv = 0.20 + 0.35 * math.sin(2 * math.pi * tt * 1.3 + ph)
        nx = bd["_base_x"] + 0.4 * math.cos(2 * math.pi * tt * 0.4 + ph)
        nz = bd["_base_z"] + 0.3 * math.sin(2 * math.pi * tt * 0.5 + ph)
        kf(bd, f, "location", (nx, nyv, nz))
        kf(bd, f, "rotation_euler", (math.radians(8 * math.sin(2 * math.pi * tt * 1.5 + ph)), math.radians(180 * tt + ph * 60), 0))

    # 40 seagulls : flap + orbit slow
    for sg in seagulls:
        ang = sg["a"] + tt * 2 * math.pi * 0.3
        bx_ = math.cos(ang) * sg["r"]
        bz_ = math.sin(ang) * sg["r"] * 0.7
        by_ = sg["by"] + 0.3 * math.sin(2 * math.pi * tt * 1.5 + sg["phase"])
        kf(sg["p"], f, "location", (bx_, by_, bz_))
        kf(sg["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))
        wflap = math.radians(50) * math.sin(2 * math.pi * tt * 7 + sg["phase"])
        kf(sg["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(sg["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # 3 boats : bob with waves
    for boat in boats:
        ph = boat["_phase"]
        by_ = 0.30 + 0.20 * math.sin(2 * math.pi * tt * 1.0 + ph)
        roll = math.radians(8 * math.sin(2 * math.pi * tt * 0.8 + ph))
        pitch = math.radians(5 * math.cos(2 * math.pi * tt * 1.2 + ph))
        kf(boat, f, "location", (boat["_base_x"], by_, boat.location.z if f > 1 else boat.location.z))
        kf(boat, f, "rotation_euler", (pitch, math.radians(20 * math.sin(2 * math.pi * tt * 0.3 + ph)), roll))

    # clouds drift
    for cp in clouds:
        bx_ = cp["_base_x"]
        spd = cp["_speed"]
        new_x = bx_ + tt * spd * 6 - 3
        if new_x > 18:
            new_x -= 36
        kf(cp, f, "location", (new_x, cp.location.y if f > 1 else cp.location.y, cp.location.z))

    # sun pulse + halos breathe
    sp_sc = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 2)
    kf(sun, f, "scale", (sp_sc, sp_sc, sp_sc))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2, sun_halo_3]):
        br = 1.0 + 0.10 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.0)
        kf(halo, f, "scale", (br, br, br))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_whale_breaching_ocean] wrote {OUT}")
