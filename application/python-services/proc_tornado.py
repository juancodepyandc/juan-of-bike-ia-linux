"""
proc_tornado.py — 112e procédural AuroraIA, Phase F++++.

Tornade en mouvement : entonnoir cônique vertical (8 anneaux empilés
décroissants du sol vers les nuages) + spirale de 50 débris orbitant
en vortex + 8 nuages sombres tourbillonnants au sommet + sol prairie
endommagée + maison délabrée + grange + tracteur retourné + 4 arbres
déracinés + 8 éclairs de poussière au sol.

Animation :
- tornade rotate Z (rapide, 4 turns/loop)
- 50 débris : orbites circulaires à différents rayons et hauteurs,
  montant en spirale dans le funnel
- 8 nuages : rotation différentielle + scale pulse
- éclairs au sol : pulse émission

Sortie : output/3d/pbr_tornado_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_tornado_proc.glb"))

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
MAT_SKY_STORM = make_mat("sky_storm", (0.18, 0.16, 0.18), roughness=1.0,
                          emi=(0.10, 0.08, 0.12), emi_strength=0.3)
MAT_GROUND = make_mat("ground_field", (0.18, 0.20, 0.10), roughness=0.95)
MAT_GROUND_TORN = make_mat("ground_torn", (0.22, 0.15, 0.10), roughness=0.95)
MAT_FUNNEL = make_mat(
    "funnel", (0.35, 0.30, 0.30), roughness=0.5, alpha=0.55,
    emi=(0.25, 0.20, 0.20), emi_strength=0.6,
)
MAT_FUNNEL_DENSE = make_mat(
    "funnel_dense", (0.25, 0.22, 0.22), roughness=0.5, alpha=0.75,
    emi=(0.15, 0.12, 0.12), emi_strength=0.4,
)
MAT_CLOUD = make_mat(
    "cloud_dark", (0.20, 0.20, 0.22), roughness=0.95, alpha=0.85,
    emi=(0.12, 0.10, 0.15), emi_strength=0.3,
)
MAT_DEBRIS_WOOD = make_mat("debris_wood", (0.45, 0.30, 0.18), roughness=0.85)
MAT_DEBRIS_METAL = make_mat("debris_metal", (0.55, 0.55, 0.55), metallic=0.7, roughness=0.4)
MAT_DEBRIS_DARK = make_mat("debris_dark", (0.20, 0.18, 0.16), roughness=0.9)
MAT_HOUSE_WALL = make_mat("house_wall", (0.55, 0.50, 0.42), roughness=0.85)
MAT_HOUSE_ROOF = make_mat("house_roof", (0.30, 0.15, 0.10), roughness=0.85)
MAT_BARN_RED = make_mat("barn_red", (0.45, 0.10, 0.08), roughness=0.85)
MAT_TRACTOR = make_mat("tractor", (0.75, 0.55, 0.10), roughness=0.6, metallic=0.4)
MAT_TRACTOR_DARK = make_mat("tractor_dark", (0.15, 0.13, 0.10), roughness=0.7)
MAT_TREE_TRUNK = make_mat("trunk", (0.30, 0.22, 0.15), roughness=0.9)
MAT_TREE_LEAVES = make_mat("leaves", (0.15, 0.32, 0.10), roughness=0.85)
MAT_DUST = make_mat(
    "dust", (0.55, 0.45, 0.35), roughness=0.5, alpha=0.4,
    emi=(0.4, 0.3, 0.25), emi_strength=1.5,
)
MAT_LIGHTNING = make_mat(
    "lightning", (1.0, 0.95, 0.8), roughness=0.0, alpha=0.85,
    emi=(1.0, 0.95, 0.8), emi_strength=8.0,
)

# --- backdrop ---------------------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 16, 5), mat=MAT_SKY_STORM)
sky.scale = (28, 0.1, 14)

ground = cube("ground", size=1.0, loc=(0, 0, -0.05), mat=MAT_GROUND)
ground.scale = (30, 0.1, 24)

# torn-up ground patch under tornado base
torn = cube("ground_torn", size=1.0, loc=(0, 0.01, 0), mat=MAT_GROUND_TORN)
torn.scale = (5, 0.05, 5)

# --- tornado funnel : 10 stacked rings (cylinders), wide bottom narrow top --
funnel_pivot = empty("funnel", (0, 0, 0))
N_RINGS = 10
ring_objs = []
for i in range(N_RINGS):
    h = i * 1.1
    # radius decreases nonlinearly
    t = i / (N_RINGS - 1)
    r = 1.4 + (0.4 - 1.4) * (t ** 0.7) + 0.3 * (1 - t)
    r = max(0.3, r)
    if i >= N_RINGS - 2:
        r = 0.4 - (i - (N_RINGS - 2)) * 0.05
        r = max(0.25, r)
    bottom_widen = 1.6 if i == 0 else (1.25 if i == 1 else 1.0)
    r_use = r * bottom_widen
    m = MAT_FUNNEL_DENSE if i < 2 or i > 7 else MAT_FUNNEL
    seg = cone(f"funnel_{i}", r1=r_use * 1.05, r2=r_use, depth=1.0, segs=20,
                loc=(0, 0.5 + h, 0), parent=funnel_pivot, mat=m)
    seg.rotation_euler = (math.radians(90), 0, 0)
    ring_objs.append(seg)

# --- 50 debris swirling around the funnel -----------------------------------
debris = []
DEBRIS_COUNT = 50
for i in range(DEBRIS_COUNT):
    h = random.uniform(0.3, 9.0)
    t = h / 9.0
    # radius at this height (with random jitter inside)
    base_r = 1.4 + (0.4 - 1.4) * (t ** 0.7) + 0.3 * (1 - t)
    base_r = max(0.4, base_r)
    r_d = base_r + random.uniform(0.5, 1.6)
    a0 = random.uniform(0, math.pi * 2)
    x = math.cos(a0) * r_d
    z = math.sin(a0) * r_d
    pick = random.random()
    if pick < 0.4:
        m = MAT_DEBRIS_WOOD
        size = random.uniform(0.10, 0.22)
        ob = cube(f"debris_{i}", size=size, loc=(x, h, z), parent=funnel_pivot, mat=m)
        ob.scale = (1.0, 0.3 + random.random() * 0.3, 2.0 + random.random())
    elif pick < 0.7:
        m = MAT_DEBRIS_DARK
        size = random.uniform(0.08, 0.18)
        ob = sphere(f"debris_{i}", r=size, segs=8, rings=6, loc=(x, h, z), parent=funnel_pivot, mat=m)
    else:
        m = MAT_DEBRIS_METAL
        size = random.uniform(0.08, 0.20)
        ob = cube(f"debris_{i}", size=size, loc=(x, h, z), parent=funnel_pivot, mat=m)
        ob.scale = (1.5, 1.0, 0.5)
    ob.rotation_euler = (random.uniform(0, math.pi), random.uniform(0, math.pi), random.uniform(0, math.pi))
    debris.append((ob, a0, r_d, h, random.uniform(0.6, 1.4)))

# --- 8 dark clouds at the top (around y=10) ---------------------------------
clouds = []
for i in range(8):
    a = i * (math.pi * 2 / 8)
    r = 2.5
    cx = math.cos(a) * r
    cz = math.sin(a) * r
    cy = 10.0 + random.uniform(-0.4, 0.4)
    c = sphere(f"cloud_{i}", r=random.uniform(1.1, 1.5), segs=16, rings=12,
                loc=(cx, cy, cz), mat=MAT_CLOUD)
    c.scale = (1.4, 0.55, 1.1)
    clouds.append((c, a, r))
# central cloud blob right above the funnel
central_cloud = sphere("cloud_central", r=2.2, segs=20, rings=14, loc=(0, 9.5, 0), mat=MAT_CLOUD)
central_cloud.scale = (1.6, 0.6, 1.4)

# --- damaged house ---------------------------------------------------------
house_p = empty("house", (-7.0, 0, 4.5))
house_body = cube("house_body", size=1.0, loc=(0, 0.7, 0), parent=house_p, mat=MAT_HOUSE_WALL)
house_body.scale = (1.6, 0.7, 1.4)
house_roof = cone("house_roof", r1=1.5, r2=0.05, depth=0.8, segs=4, loc=(0, 1.55, 0), parent=house_p, mat=MAT_HOUSE_ROOF)
house_roof.rotation_euler = (math.radians(90), 0, math.radians(45))
# tilted (storm damage)
house_p.rotation_euler = (0, 0, math.radians(-4))
# broken door
door = cube("door", size=1.0, loc=(0.6, 0.35, 1.45), parent=house_p, mat=MAT_DEBRIS_DARK)
door.scale = (0.25, 0.45, 0.04)
door.rotation_euler = (0, math.radians(-30), 0)

# --- barn (red, partially collapsed) ----------------------------------------
barn_p = empty("barn", (7.5, 0, 4.0))
barn_body = cube("barn_body", size=1.0, loc=(0, 0.9, 0), parent=barn_p, mat=MAT_BARN_RED)
barn_body.scale = (2.5, 0.9, 1.8)
barn_roof = cone("barn_roof", r1=2.0, r2=0.1, depth=0.9, segs=4, loc=(0, 1.9, 0), parent=barn_p, mat=MAT_HOUSE_ROOF)
barn_roof.rotation_euler = (math.radians(90), 0, math.radians(45))
barn_roof.scale = (1.4, 1.0, 1.0)
# barn door
bd = cube("barn_door", size=1.0, loc=(0, 0.6, 1.85), parent=barn_p, mat=MAT_DEBRIS_DARK)
bd.scale = (0.8, 0.6, 0.05)
# partial roof collapse (missing chunk shown as smaller piece)
chunk = cube("barn_chunk", size=1.0, loc=(0.8, 0.4, -1.6), parent=barn_p, mat=MAT_BARN_RED)
chunk.scale = (0.5, 0.3, 0.4)
chunk.rotation_euler = (math.radians(40), 0, math.radians(20))

# --- tractor renversé ------------------------------------------------------
tractor_p = empty("tractor", (3.5, 0.4, 5.0))
tractor_p.rotation_euler = (math.radians(180), 0, math.radians(-15))  # flipped
body = cube("tractor_body", size=1.0, loc=(0, 0, 0), parent=tractor_p, mat=MAT_TRACTOR)
body.scale = (0.9, 0.45, 1.2)
cabin = cube("tractor_cabin", size=1.0, loc=(0, 0.4, -0.2), parent=tractor_p, mat=MAT_TRACTOR_DARK)
cabin.scale = (0.7, 0.35, 0.65)
# 4 wheels sticking up
for i, (wx, wz) in enumerate([(0.7, 0.6), (-0.7, 0.6), (0.7, -0.6), (-0.7, -0.6)]):
    rw = 0.30 if abs(wz) > 0.5 else 0.35
    w = cone(f"wheel_{i}", r1=rw, r2=rw, depth=0.18, segs=14, loc=(wx, -0.35, wz), parent=tractor_p, mat=MAT_DEBRIS_DARK)
    w.rotation_euler = (0, math.radians(90), 0)
exh = cone("exhaust", r1=0.05, r2=0.05, depth=0.4, segs=8, loc=(0.35, 0.5, 0.4), parent=tractor_p, mat=MAT_DEBRIS_DARK)
exh.rotation_euler = (math.radians(90), 0, 0)

# --- 4 trees uprooted -------------------------------------------------------
tree_data = [
    (-5.0, 7.0, math.radians(35)),
    ( 5.5, 6.5, math.radians(-45)),
    (-9.0, 6.0, math.radians(50)),
    ( 9.5, 7.5, math.radians(-25)),
]
for i, (tx, tz, tilt) in enumerate(tree_data):
    p = empty(f"tree_{i}", (tx, 0.6, tz))
    p.rotation_euler = (0, 0, tilt)
    trunk = cone(f"tree_{i}_trunk", r1=0.18, r2=0.12, depth=1.5, segs=8, loc=(0, 0.4, 0), parent=p, mat=MAT_TREE_TRUNK)
    trunk.rotation_euler = (math.radians(90), 0, 0)
    # foliage (3 sphere puffs)
    for j, (px, py, pz) in enumerate([(0, 1.3, 0), (0.3, 1.1, 0.2), (-0.3, 1.4, -0.2)]):
        f = sphere(f"tree_{i}_leaves_{j}", r=0.5, segs=12, rings=8, loc=(px, py, pz), parent=p, mat=MAT_TREE_LEAVES)
    # roots exposed
    for k in range(3):
        ra = k * (math.pi * 2 / 3)
        root = cone(f"tree_{i}_root_{k}", r1=0.08, r2=0.02, depth=0.4, segs=6,
                     loc=(math.cos(ra) * 0.18, -0.35, math.sin(ra) * 0.18), parent=p, mat=MAT_TREE_TRUNK)
        root.rotation_euler = (math.radians(140), 0, ra)

# --- 8 dust bursts at ground around tornado --------------------------------
dust_objs = []
for i in range(8):
    a = i * (math.pi * 2 / 8)
    r = 2.2
    dx = math.cos(a) * r
    dz = math.sin(a) * r
    d = sphere(f"dust_{i}", r=0.4, segs=14, rings=10, loc=(dx, 0.3, dz), mat=MAT_DUST)
    d.scale = (1.0, 0.4, 1.0)
    dust_objs.append((d, i))

# --- 4 lightning flashes at the cloud level --------------------------------
lightning_objs = []
for i in range(4):
    a = i * (math.pi * 2 / 4) + 0.4
    r = 1.8
    lx = math.cos(a) * r
    lz = math.sin(a) * r
    ly = 9.8
    l = cone(f"lightning_{i}", r1=0.05, r2=0.01, depth=0.8, segs=4, loc=(lx, ly, lz), mat=MAT_LIGHTNING)
    l.rotation_euler = (math.radians(180 + random.uniform(-10, 10)), 0, math.radians(random.uniform(-15, 15)))
    lightning_objs.append((l, i))

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

# tornado funnel rotate (whole pivot spins)
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(funnel_pivot, f, (0, tt * math.pi * 8.0, 0))  # 4 turns/loop
    # subtle position wiggle (the tornado wanders)
    wx = math.sin(tt * math.pi * 2.0) * 0.3
    wz = math.cos(tt * math.pi * 1.5) * 0.2
    kf_loc(funnel_pivot, f, (wx, 0, wz))

# individual rings counter-rotate slightly (visual chaos)
for idx, ring in enumerate(ring_objs):
    speed = 1.5 + idx * 0.25
    direction = -1 if idx % 2 else 1
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        kf_rot(ring, f, (math.radians(90), 0, direction * tt * math.pi * speed))

# debris orbit at their radius+height, with vertical drift upward
for ob, a0, r_d, h0, spd in debris:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 4.0 * spd
        # drift up, wrap around
        h = (h0 + tt * 4.0 * spd) % 9.0
        # radius narrows at top
        rh_t = h / 9.0
        r_now = 1.4 + (0.4 - 1.4) * (rh_t ** 0.7) + 0.3 * (1 - rh_t)
        r_now = max(0.4, r_now) + (r_d - 1.4)  # preserve offset
        if r_now < 0.5:
            r_now = 0.5
        x = math.cos(angle) * r_now
        z = math.sin(angle) * r_now
        kf_loc(ob, f, (x, h, z))
        kf_rot(ob, f, (tt * math.pi * 3.0, tt * math.pi * 4.0 * spd, tt * math.pi * 2.5))

# clouds rotate around central axis
for c, a0, r in clouds:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 1.5
        kf_loc(c, f, (math.cos(angle) * r, c.location.y, math.sin(angle) * r))
        s = 1.0 + 0.1 * math.sin(tt * math.pi * 4.0 + a0)
        kf_scale(c, f, (1.4 * s, 0.55, 1.1 * s))

# central cloud scale pulse
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.08 * math.sin(tt * math.pi * 5.0)
    kf_scale(central_cloud, f, (1.6 * s, 0.6, 1.4 * s))

# dust pulses at ground
for d, idx in dust_objs:
    phase_off = idx * 8
    for f in range(1, FRAMES + 1, 3):
        local = ((f + phase_off) % 36) / 36
        s = 0.5 + 1.0 * math.exp(-((local - 0.3) * 5.0) ** 2)
        kf_scale(d, f, (s, 0.4 * s, s))

# lightning flashes (short bursts)
for l, idx in lightning_objs:
    phase = idx * 35
    for f in range(1, FRAMES + 1, 3):
        local = ((f + phase) % 50) / 50
        # sharp pulse near start
        s = 0.3 + 1.5 * math.exp(-((local - 0.1) * 10.0) ** 2)
        kf_scale(l, f, (s, s * 4.0, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_tornado] wrote {OUT}")
