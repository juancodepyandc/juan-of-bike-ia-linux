"""
proc_mushroom_forest.py — 120e procédural AuroraIA, Phase F++++ MILESTONE.

Forêt fantastique de champignons géants : 10 champignons (3 grands +
4 moyens + 3 petits) chapeaux colorés (rouge/violet/jaune/bleu) avec
spots blancs sur chacun + sol mousseux + 30 lucioles émissives volant
en spirales + 4 souches d'arbre + 6 fougères + 12 puffs de brouillard
mystique + ciel sombre + 3 lapins blancs + 8 petites fleurs émissives
+ chemin de pierres + 3 grands arbres en silhouette.

Animation :
- 30 lucioles : spirales 3D différentielles
- 10 chapeaux champignons : pulse subtle scale
- 6 fougères : sway feuilles
- 12 brouillard puffs : drift + scale
- 3 lapins : hop sin
- 8 fleurs émissives : pulse
- arbres : pas anim

Sortie : output/3d/pbr_mushroomforest_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_mushroomforest_proc.glb"))

random.seed(0xF02E57)

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
MAT_SKY_DARK = make_mat("sky_dark", (0.08, 0.10, 0.14), roughness=1.0,
                          emi=(0.05, 0.08, 0.12), emi_strength=0.5)
MAT_MOSS = make_mat("moss", (0.12, 0.30, 0.10), roughness=0.95,
                      emi=(0.05, 0.15, 0.05), emi_strength=0.2)
MAT_MOSS_LIGHT = make_mat("moss_light", (0.20, 0.45, 0.18), roughness=0.85,
                            emi=(0.10, 0.20, 0.08), emi_strength=0.3)
MAT_STEM = make_mat("stem", (0.95, 0.92, 0.85), roughness=0.7,
                      emi=(0.30, 0.28, 0.22), emi_strength=0.2)
MAT_CAP_RED = make_mat("cap_red", (0.85, 0.10, 0.10), roughness=0.6,
                         emi=(0.5, 0.05, 0.05), emi_strength=0.4)
MAT_CAP_VIOLET = make_mat("cap_violet", (0.70, 0.20, 0.95), roughness=0.6,
                            emi=(0.4, 0.10, 0.65), emi_strength=0.5)
MAT_CAP_YELLOW = make_mat("cap_yellow", (1.0, 0.85, 0.20), roughness=0.6,
                            emi=(0.6, 0.50, 0.10), emi_strength=0.5)
MAT_CAP_BLUE = make_mat("cap_blue", (0.20, 0.45, 0.95), roughness=0.6,
                          emi=(0.10, 0.25, 0.65), emi_strength=0.5)
MAT_SPOT_WHITE = make_mat("spot_white", (0.95, 0.95, 0.92), roughness=0.5,
                            emi=(0.5, 0.5, 0.45), emi_strength=0.4)
MAT_FIREFLY = make_mat("firefly", (1.0, 0.95, 0.40), roughness=0.0,
                         emi=(1.0, 0.95, 0.40), emi_strength=8.0)
MAT_FIREFLY_GREEN = make_mat("firefly_g", (0.50, 1.0, 0.50), roughness=0.0,
                               emi=(0.40, 1.0, 0.40), emi_strength=7.5)
MAT_STUMP = make_mat("stump", (0.30, 0.20, 0.12), roughness=0.9)
MAT_STUMP_TOP = make_mat("stump_top", (0.45, 0.30, 0.20), roughness=0.85,
                           emi=(0.10, 0.05, 0.03), emi_strength=0.15)
MAT_FERN = make_mat("fern", (0.10, 0.40, 0.15), roughness=0.85,
                      emi=(0.05, 0.20, 0.08), emi_strength=0.3)
MAT_MIST = make_mat(
    "mist", (0.55, 0.65, 0.80), roughness=1.0, alpha=0.40,
    emi=(0.45, 0.55, 0.75), emi_strength=1.0,
)
MAT_RABBIT = make_mat("rabbit", (0.90, 0.90, 0.92), roughness=0.7,
                        emi=(0.30, 0.30, 0.30), emi_strength=0.2)
MAT_RABBIT_EYE = make_mat("rabbit_eye", (1.0, 0.20, 0.30), roughness=0.0,
                            emi=(1.0, 0.20, 0.30), emi_strength=4.0)
MAT_FLOWER = make_mat("flower", (1.0, 0.60, 0.85), roughness=0.5,
                        emi=(1.0, 0.50, 0.80), emi_strength=3.5)
MAT_FLOWER_CYAN = make_mat("flower_cyan", (0.30, 0.95, 1.0), roughness=0.5,
                             emi=(0.20, 0.95, 1.0), emi_strength=3.5)
MAT_TREE_BG = make_mat("tree_bg", (0.05, 0.08, 0.05), roughness=0.95)
MAT_STONE_PATH = make_mat("stone_path", (0.35, 0.35, 0.32), roughness=0.85,
                            emi=(0.10, 0.10, 0.10), emi_strength=0.1)

# --- backdrop ---------------------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 16, 5), mat=MAT_SKY_DARK)
sky.scale = (28, 0.1, 14)

# 3 background tree silhouettes
for i, (tx, tz) in enumerate([(-10, 9), (10, 9), (0, 11)]):
    tp = empty(f"tree_bg_{i}", (tx, 0, tz))
    trunk = cone(f"tree_bg_{i}_trunk", r1=0.5, r2=0.3, depth=5.0, segs=8, loc=(0, 2.5, 0), parent=tp, mat=MAT_TREE_BG)
    trunk.rotation_euler = (math.radians(90), 0, 0)
    # 2 foliage blobs
    for j in range(2):
        f = sphere(f"tree_bg_{i}_f_{j}", r=1.5 - j * 0.3, segs=16, rings=10, loc=(0, 5.5 + j * 1.0, 0), parent=tp, mat=MAT_TREE_BG)
        f.scale = (1.1, 1.2, 1.1)

# main ground (mossy)
ground = cube("ground", size=1.0, loc=(0, -0.05, 0), mat=MAT_MOSS)
ground.scale = (30, 0.1, 22)

# light moss patches
for i in range(8):
    mx = random.uniform(-9, 9)
    mz = random.uniform(-6, 6)
    m = cube(f"moss_patch_{i}", size=1.0, loc=(mx, 0.01, mz), mat=MAT_MOSS_LIGHT)
    m.scale = (random.uniform(1.5, 3.0), 0.05, random.uniform(1.0, 2.0))

# --- 10 mushrooms (3 big + 4 medium + 3 small) -----------------------------
def make_mushroom(name, x, z, scale, cap_mat, cap_radius=0.8, stem_height=1.2):
    p = empty(name, (x, 0, z))
    # stem
    stem = cone(f"{name}_stem", r1=0.18 * scale * (cap_radius / 0.8), r2=0.25 * scale * (cap_radius / 0.8), depth=stem_height * scale, segs=14,
                 loc=(0, stem_height * scale / 2, 0), parent=p, mat=MAT_STEM)
    stem.rotation_euler = (math.radians(90), 0, 0)
    # cap (half sphere)
    cap = sphere(f"{name}_cap", r=cap_radius * scale, segs=24, rings=16,
                  loc=(0, stem_height * scale + cap_radius * scale * 0.3, 0), parent=p, mat=cap_mat)
    cap.scale = (1.3, 0.7, 1.3)
    # 5-8 white spots on cap
    n_spots = random.randint(5, 8)
    for i in range(n_spots):
        sa = i * (math.pi * 2 / n_spots) + random.uniform(-0.3, 0.3)
        sr = random.uniform(0.5, 1.0) * cap_radius * scale
        sx = math.cos(sa) * sr
        sz = math.sin(sa) * sr
        sy_top = stem_height * scale + cap_radius * scale * 0.3
        # offset y by spherical position
        sy = sy_top + 0.35 * cap_radius * scale
        spot = sphere(f"{name}_spot_{i}", r=0.08 * scale, segs=8, rings=6, loc=(sx, sy, sz), parent=p, mat=MAT_SPOT_WHITE)
        spot.scale = (1.0, 0.4, 1.0)
    # gills underside (cone)
    gills = cone(f"{name}_gills", r1=cap_radius * scale * 0.7, r2=cap_radius * scale * 0.3, depth=0.05, segs=14,
                  loc=(0, stem_height * scale + 0.05, 0), parent=p, mat=MAT_STEM)
    gills.rotation_euler = (math.radians(90), 0, 0)
    return p, cap

# 3 big mushrooms
mushroom_caps = []
big_data = [
    ((-4.5, 2.0), 1.5, MAT_CAP_RED, 1.2, 1.8),
    ((3.5, -1.5), 1.4, MAT_CAP_VIOLET, 1.1, 1.7),
    ((-1.0, 4.0), 1.6, MAT_CAP_BLUE, 1.3, 1.9),
]
for i, ((x, z), sc, mat, cr, sh) in enumerate(big_data):
    p, cap = make_mushroom(f"mush_big_{i}", x, z, sc, mat, cr, sh)
    mushroom_caps.append(cap)

# 4 medium mushrooms
med_data = [
    ((-7.0, -1.0), 0.8, MAT_CAP_YELLOW),
    ((5.5, 3.0), 0.9, MAT_CAP_RED),
    ((-3.0, -3.5), 0.75, MAT_CAP_VIOLET),
    ((6.5, -2.5), 0.85, MAT_CAP_YELLOW),
]
for i, ((x, z), sc, mat) in enumerate(med_data):
    p, cap = make_mushroom(f"mush_med_{i}", x, z, sc, mat)
    mushroom_caps.append(cap)

# 3 small mushrooms
small_data = [
    ((-2.0, 0.5), 0.45, MAT_CAP_BLUE),
    ((1.5, 2.5), 0.40, MAT_CAP_RED),
    ((4.0, 0.5), 0.50, MAT_CAP_VIOLET),
]
for i, ((x, z), sc, mat) in enumerate(small_data):
    p, cap = make_mushroom(f"mush_small_{i}", x, z, sc, mat)
    mushroom_caps.append(cap)

# --- 4 souches (tree stumps) -----------------------------------------------
for i, (sx, sz) in enumerate([(-9.0, -4.0), (8.5, 1.0), (-6.5, 5.0), (9.0, -4.5)]):
    sp = empty(f"stump_{i}", (sx, 0, sz))
    stump_body = cone(f"stump_{i}_body", r1=0.45, r2=0.55, depth=0.6, segs=12, loc=(0, 0.3, 0), parent=sp, mat=MAT_STUMP)
    stump_body.rotation_euler = (math.radians(90), 0, 0)
    # top disc (lighter, with rings)
    top = cone(f"stump_{i}_top", r1=0.45, r2=0.45, depth=0.08, segs=14, loc=(0, 0.65, 0), parent=sp, mat=MAT_STUMP_TOP)
    top.rotation_euler = (math.radians(90), 0, 0)
    # 2 small mushrooms growing on stump
    for j in range(2):
        ja = j * math.pi
        small = cone(f"stump_{i}_mush_{j}", r1=0.05, r2=0.04, depth=0.15, segs=8, loc=(math.cos(ja) * 0.2, 0.75, math.sin(ja) * 0.2), parent=sp, mat=MAT_STEM)
        small.rotation_euler = (math.radians(90), 0, 0)
        cap = sphere(f"stump_{i}_mushcap_{j}", r=0.10, segs=10, rings=8, loc=(math.cos(ja) * 0.2, 0.85, math.sin(ja) * 0.2), parent=sp, mat=MAT_CAP_RED)
        cap.scale = (1.0, 0.5, 1.0)

# --- 6 fougères (ferns) ---------------------------------------------------
ferns = []
fern_locs = [(-5.5, -3.5), (6.0, 4.5), (-8.0, 2.0), (2.5, 5.5), (8.0, -1.5), (-1.0, -4.5)]
for i, (fx, fz) in enumerate(fern_locs):
    fp = empty(f"fern_{i}", (fx, 0, fz))
    # 6 fronds radiating out, each is a stretched ellipsoid
    for j in range(6):
        a = j * (math.pi * 2 / 6) + random.uniform(-0.3, 0.3)
        h = random.uniform(0.5, 0.8)
        frond = sphere(f"fern_{i}_frond_{j}", r=0.18, segs=10, rings=6, loc=(math.cos(a) * 0.25, 0.4 + h / 2, math.sin(a) * 0.25), parent=fp, mat=MAT_FERN)
        frond.scale = (1.0, 4.0 * h, 0.3)
        frond.rotation_euler = (math.radians(-30), -a, 0)
    ferns.append(fp)

# --- 30 lucioles (fireflies) -----------------------------------------------
fireflies = []
for i in range(30):
    fx = random.uniform(-9, 9)
    fz = random.uniform(-7, 7)
    fy = random.uniform(1.0, 5.5)
    mat = MAT_FIREFLY_GREEN if (i % 4 == 0) else MAT_FIREFLY
    f = sphere(f"firefly_{i}", r=random.uniform(0.06, 0.10), segs=8, rings=6, loc=(fx, fy, fz), mat=mat)
    fireflies.append((f, fx, fy, fz, random.uniform(0, math.pi * 2), random.uniform(0.5, 1.5), random.uniform(0, 1)))

# --- 12 brouillard puffs ---------------------------------------------------
mists = []
for i in range(12):
    mx = random.uniform(-10, 10)
    mz = random.uniform(-7, 7)
    my = random.uniform(1.0, 4.0)
    m = sphere(f"mist_{i}", r=random.uniform(1.0, 1.6), segs=14, rings=10, loc=(mx, my, mz), mat=MAT_MIST)
    m.scale = (1.5, 0.45, 1.3)
    mists.append((m, mx, mz, my, random.uniform(0, math.pi * 2)))

# --- 3 lapins (rabbits) ----------------------------------------------------
def make_rabbit(name, x, z):
    p = empty(name, (x, 0, z))
    body = sphere(f"{name}_body", r=0.25, segs=14, rings=10, loc=(0, 0.25, 0), parent=p, mat=MAT_RABBIT)
    body.scale = (1.2, 0.9, 0.9)
    head = sphere(f"{name}_head", r=0.18, segs=12, rings=10, loc=(0.25, 0.45, 0), parent=p, mat=MAT_RABBIT)
    head.scale = (1.0, 1.1, 0.9)
    # 2 ears
    for side, dz in [("L", 0.10), ("R", -0.10)]:
        ear = cone(f"{name}_ear_{side}", r1=0.05, r2=0.04, depth=0.3, segs=6, loc=(0.20, 0.70, dz), parent=p, mat=MAT_RABBIT)
        ear.rotation_euler = (math.radians(-20), 0, math.radians(10 if side == "L" else -10))
    # 2 eyes
    for side, dz in [("L", 0.10), ("R", -0.10)]:
        eye = sphere(f"{name}_eye_{side}", r=0.025, segs=8, rings=6, loc=(0.36, 0.46, dz), parent=p, mat=MAT_RABBIT_EYE)
    # tail (puff)
    tail = sphere(f"{name}_tail", r=0.08, segs=10, rings=8, loc=(-0.28, 0.28, 0), parent=p, mat=MAT_RABBIT)
    return p

rabbits = []
for i, (rx, rz) in enumerate([(-3.0, -1.5), (4.5, 1.0), (-5.5, 3.5)]):
    r = make_rabbit(f"rabbit_{i}", rx, rz)
    rabbits.append((r, rx, rz, random.uniform(0, 1)))

# --- 8 fleurs émissives ----------------------------------------------------
flowers = []
flower_locs = [(-6, -2), (-4, 3), (2, -3.5), (5, -1), (-7, 0.5), (7, 2.5), (0, -4), (-2, 5)]
for i, (fx, fz) in enumerate(flower_locs):
    fp = empty(f"flower_{i}", (fx, 0, fz))
    # stem
    stem = cone(f"flower_{i}_stem", r1=0.03, r2=0.03, depth=0.35, segs=6, loc=(0, 0.175, 0), parent=fp, mat=MAT_FERN)
    stem.rotation_euler = (math.radians(90), 0, 0)
    # 5 petals
    mat = MAT_FLOWER if i % 2 == 0 else MAT_FLOWER_CYAN
    for k in range(5):
        ka = k * (math.pi * 2 / 5)
        petal = sphere(f"flower_{i}_petal_{k}", r=0.08, segs=8, rings=6, loc=(math.cos(ka) * 0.10, 0.4, math.sin(ka) * 0.10), parent=fp, mat=mat)
        petal.scale = (1.0, 0.4, 1.0)
    # center
    center = sphere(f"flower_{i}_center", r=0.06, segs=8, rings=6, loc=(0, 0.4, 0), parent=fp, mat=MAT_SPOT_WHITE)
    flowers.append(fp)

# --- chemin de pierres -----------------------------------------------------
for i in range(8):
    sx = -8.0 + i * 1.3
    sz = math.sin(i * 0.5) * 0.6 + 1.5
    st = sphere(f"path_stone_{i}", r=0.35, segs=10, rings=8, loc=(sx, 0.10, sz), mat=MAT_STONE_PATH)
    st.scale = (1.0, 0.25, 0.8)

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

# fireflies : 3D spiral paths
for fly, fx0, fy0, fz0, a0, spd, ph in fireflies:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 4.0 * spd
        r = 0.6 + 0.4 * math.sin(tt * math.pi * 3.0 + a0)
        dx = fx0 + math.cos(angle) * r
        dz = fz0 + math.sin(angle) * r
        dy = fy0 + math.sin(tt * math.pi * 3.0 + a0 + ph) * 1.2
        kf_loc(fly, f, (dx, dy, dz))
        s = 0.8 + 0.5 * math.sin(tt * math.pi * 6.0 + a0 + ph)
        kf_scale(fly, f, (s, s, s))

# mushroom caps pulse
for i, cap in enumerate(mushroom_caps):
    phase = i * 0.4
    base_x = cap.scale.x
    base_y = cap.scale.y
    base_z = cap.scale.z
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.05 * math.sin(tt * math.pi * 3.0 + phase)
        kf_scale(cap, f, (base_x * s, base_y, base_z * s))

# ferns sway
for i, fp in enumerate(ferns):
    phase = i * 0.5
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bend = math.radians(8) * math.sin(tt * math.pi * 3.0 + phase)
        kf_rot(fp, f, (bend, 0, bend * 0.6))

# mist puffs drift
for m, mx0, mz0, my0, ph in mists:
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        dx = mx0 + 0.6 * math.sin(tt * math.pi * 1.5 + ph)
        dz = mz0 + 0.4 * math.cos(tt * math.pi * 1.2 + ph)
        dy = my0 + 0.3 * math.sin(tt * math.pi * 2.0 + ph * 0.7)
        kf_loc(m, f, (dx, dy, dz))
        s = 1.0 + 0.18 * math.sin(tt * math.pi * 3.0 + ph)
        kf_scale(m, f, (1.5 * s, 0.45, 1.3 * s))

# rabbits hop
for r, rx, rz, ph in rabbits:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        local = ((tt + ph) * 4.0) % 1.0
        hop_y = 0.5 * math.sin(local * math.pi) if local < 1.0 else 0
        # also forward drift
        dx = rx + 0.4 * math.sin(tt * math.pi * 2.0 + ph)
        dz = rz + 0.4 * math.cos(tt * math.pi * 2.0 + ph * 0.5)
        kf_loc(r, f, (dx, hop_y, dz))
        # rotate to face direction
        kf_rot(r, f, (0, -tt * math.pi * 2.0 + math.pi / 2, 0))

# flowers pulse
for i, fp in enumerate(flowers):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 4.0 + phase)
        kf_scale(fp, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_mushroomforest] wrote {OUT}")
