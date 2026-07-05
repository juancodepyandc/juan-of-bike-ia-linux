"""
proc_haunted_house.py — 121e procédural AuroraIA, Phase F++++.

Maison hantée Halloween : maison 2 étages tordue + 4 fenêtres émissives
vertes + porte ouverte sombre + cheminée tordue avec fumée + brouillard
violet + 5 citrouilles jack-o-lantern + 1 chauve-souris volante
+ 3 corbeaux + arbre mort tordu + 6 tombes + clôture cassée + lune
pleine émissive + 2 buisson morts + chemin tortueux.

Animation :
- 5 citrouilles : pulse émission visage
- chauve-souris : vol erratique
- 3 corbeaux : orbites
- brouillard : drift
- 4 fenêtres : pulse green
- cheminée fumée : monte
- lune : halo breathe

Sortie : output/3d/pbr_hauntedhouse_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_hauntedhouse_proc.glb"))

random.seed(0xBA77ED)

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
MAT_SKY_NIGHT = make_mat("sky_night", (0.05, 0.05, 0.12), roughness=1.0,
                          emi=(0.05, 0.05, 0.15), emi_strength=0.4)
MAT_GROUND = make_mat("ground", (0.10, 0.08, 0.06), roughness=0.95)
MAT_GROUND_PATH = make_mat("ground_path", (0.25, 0.20, 0.15), roughness=0.95)
MAT_HOUSE_WOOD = make_mat("house_wood", (0.18, 0.12, 0.08), roughness=0.85)
MAT_HOUSE_TRIM = make_mat("house_trim", (0.30, 0.20, 0.10), roughness=0.8)
MAT_HOUSE_ROOF = make_mat("house_roof", (0.10, 0.06, 0.05), roughness=0.85)
MAT_DOOR_DARK = make_mat("door_dark", (0.02, 0.02, 0.02), roughness=0.7,
                           emi=(0.30, 0.15, 0.05), emi_strength=0.6)
MAT_WINDOW_GREEN = make_mat(
    "window_green", (0.10, 1.0, 0.30), roughness=0.0, alpha=0.85,
    emi=(0.20, 1.0, 0.40), emi_strength=6.0,
)
MAT_CHIMNEY = make_mat("chimney", (0.20, 0.15, 0.10), roughness=0.85)
MAT_SMOKE = make_mat(
    "smoke", (0.45, 0.35, 0.55), roughness=1.0, alpha=0.55,
    emi=(0.30, 0.20, 0.40), emi_strength=0.5,
)
MAT_FOG_PURPLE = make_mat(
    "fog_purple", (0.55, 0.20, 0.65), roughness=1.0, alpha=0.35,
    emi=(0.50, 0.15, 0.65), emi_strength=1.5,
)
MAT_PUMPKIN_ORANGE = make_mat("pumpkin", (1.0, 0.45, 0.05), roughness=0.7,
                                emi=(0.50, 0.20, 0.05), emi_strength=0.4)
MAT_PUMPKIN_FACE = make_mat(
    "pumpkin_face", (1.0, 0.75, 0.10), roughness=0.0, alpha=0.95,
    emi=(1.0, 0.65, 0.05), emi_strength=8.0,
)
MAT_PUMPKIN_STEM = make_mat("pumpkin_stem", (0.20, 0.30, 0.10), roughness=0.85)
MAT_BAT = make_mat("bat", (0.05, 0.04, 0.04), roughness=0.7)
MAT_BAT_EYE = make_mat("bat_eye", (1.0, 0.10, 0.10), roughness=0.0,
                         emi=(1.0, 0.10, 0.10), emi_strength=5.0)
MAT_CROW = make_mat("crow", (0.08, 0.08, 0.10), roughness=0.7)
MAT_TREE_DEAD = make_mat("tree_dead", (0.20, 0.15, 0.10), roughness=0.95)
MAT_TOMB_STONE = make_mat("tomb_stone", (0.45, 0.42, 0.40), roughness=0.85,
                            emi=(0.15, 0.15, 0.13), emi_strength=0.2)
MAT_TOMB_DARK = make_mat("tomb_dark", (0.30, 0.28, 0.26), roughness=0.85)
MAT_FENCE = make_mat("fence", (0.25, 0.18, 0.12), roughness=0.85)
MAT_MOON = make_mat(
    "moon", (1.0, 0.95, 0.85), roughness=0.0,
    emi=(1.0, 0.95, 0.85), emi_strength=8.0,
)
MAT_MOON_HALO = make_mat(
    "moon_halo", (1.0, 0.95, 0.85), roughness=0.0, alpha=0.20,
    emi=(1.0, 0.90, 0.75), emi_strength=3.0,
)
MAT_STAR = make_mat("star", (1.0, 1.0, 1.0), roughness=0.0,
                      emi=(1.0, 1.0, 1.0), emi_strength=5.0)
MAT_BUSH_DEAD = make_mat("bush_dead", (0.15, 0.10, 0.08), roughness=0.9)
MAT_GHOST = make_mat(
    "ghost", (0.85, 0.92, 0.95), roughness=0.0, alpha=0.50,
    emi=(0.75, 0.85, 0.95), emi_strength=3.5,
)

# --- backdrop ---------------------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 16, 6), mat=MAT_SKY_NIGHT)
sky.scale = (28, 0.1, 14)

# 50 stars
for i in range(50):
    x = random.uniform(-13, 13)
    z = random.uniform(2, 11)
    y = random.uniform(14.0, 14.7)
    r = random.uniform(0.05, 0.10)
    sphere(f"star_{i}", r=r, segs=8, rings=6, loc=(x, y, z), mat=MAT_STAR)

# full moon
moon_p = empty("moon_p", (5.0, 13.0, 9.0))
moon = sphere("moon", r=1.2, segs=24, rings=18, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON)
moon_halo = sphere("moon_halo", r=2.4, segs=22, rings=16, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON_HALO)

# ground (dark dirt)
ground = cube("ground", size=1.0, loc=(0, -0.05, 0), mat=MAT_GROUND)
ground.scale = (28, 0.1, 20)

# winding path
for i in range(10):
    px = -8 + i * 1.5
    pz = 5 + math.sin(i * 0.4) * 0.7
    p = cube(f"path_{i}", size=1.0, loc=(px, 0.02, pz), mat=MAT_GROUND_PATH)
    p.scale = (0.7, 0.05, 0.6)

# --- haunted house (slightly tilted) ---------------------------------------
house = empty("house", (-1.5, 0, -2.0))
house.rotation_euler = (0, math.radians(5), math.radians(-3))

# ground floor (slightly off-square)
floor1 = cube("floor1", size=1.0, loc=(0, 1.0, 0), parent=house, mat=MAT_HOUSE_WOOD)
floor1.scale = (3.0, 1.0, 2.2)

# 2nd floor
floor2 = cube("floor2", size=1.0, loc=(0, 2.8, 0), parent=house, mat=MAT_HOUSE_WOOD)
floor2.scale = (2.7, 0.8, 2.0)

# roof (tilted pyramid)
roof = cone("roof", r1=3.6, r2=0.0, depth=2.0, segs=4, loc=(0, 4.5, 0), parent=house, mat=MAT_HOUSE_ROOF)
roof.rotation_euler = (math.radians(90), 0, math.radians(45))
roof.scale = (1.2, 1.0, 1.0)

# trim band between floors
trim = cube("trim", size=1.0, loc=(0, 2.0, 0), parent=house, mat=MAT_HOUSE_TRIM)
trim.scale = (3.05, 0.15, 2.22)

# 4 windows (glowing green)
windows = []
window_data = [
    (-1.0, 1.0, 1.12, "L1"),
    (1.0, 1.0, 1.12, "R1"),
    (-0.8, 2.8, 1.02, "L2"),
    (0.8, 2.8, 1.02, "R2"),
]
for wx, wy, wz, name in window_data:
    w = cube(f"window_{name}", size=1.0, loc=(wx, wy, wz), parent=house, mat=MAT_WINDOW_GREEN)
    w.scale = (0.5, 0.6, 0.05)
    # window frame (4 thin bars forming +)
    frame_h = cube(f"frame_{name}_h", size=1.0, loc=(wx, wy, wz + 0.02), parent=house, mat=MAT_HOUSE_TRIM)
    frame_h.scale = (0.6, 0.05, 0.02)
    frame_v = cube(f"frame_{name}_v", size=1.0, loc=(wx, wy, wz + 0.02), parent=house, mat=MAT_HOUSE_TRIM)
    frame_v.scale = (0.05, 0.7, 0.02)
    windows.append(w)

# door (dark, open showing glow inside)
door = cube("door", size=1.0, loc=(0, 0.8, 1.12), parent=house, mat=MAT_DOOR_DARK)
door.scale = (0.5, 1.2, 0.05)

# chimney (slightly leaning)
chimney_p = empty("chimney_p", (1.5, 5.5, -0.5), parent=house)
chimney_p.rotation_euler = (math.radians(8), 0, math.radians(-12))
chim = cube("chim", size=1.0, loc=(0, 0, 0), parent=chimney_p, mat=MAT_CHIMNEY)
chim.scale = (0.5, 1.0, 0.5)

# 4 smoke puffs from chimney
chim_smokes = []
for i in range(4):
    py = 1.0 + i * 0.5
    pr = 0.25 + i * 0.05
    puff = sphere(f"chim_smoke_{i}", r=pr, segs=12, rings=8, loc=(0, py, 0), parent=chimney_p, mat=MAT_SMOKE)
    chim_smokes.append((puff, i))

# --- 5 citrouilles jack-o-lantern ------------------------------------------
def make_pumpkin(name, x, z, scale=1.0):
    p = empty(name, (x, 0, z))
    body = sphere(f"{name}_body", r=0.50 * scale, segs=20, rings=14, loc=(0, 0.40 * scale, 0), parent=p, mat=MAT_PUMPKIN_ORANGE)
    body.scale = (1.2, 0.9, 1.2)
    # 4 ridges (squashed spheres around)
    for i in range(4):
        a = i * (math.pi * 2 / 4) + math.pi / 4
        rx = math.cos(a) * 0.40 * scale
        rz = math.sin(a) * 0.40 * scale
        rd = sphere(f"{name}_ridge_{i}", r=0.15 * scale, segs=10, rings=8, loc=(rx, 0.40 * scale, rz), parent=p, mat=MAT_PUMPKIN_ORANGE)
        rd.scale = (0.5, 1.0, 0.5)
    # stem
    stem = cone(f"{name}_stem", r1=0.08 * scale, r2=0.06 * scale, depth=0.20 * scale, segs=8, loc=(0, 0.78 * scale, 0), parent=p, mat=MAT_PUMPKIN_STEM)
    stem.rotation_euler = (math.radians(90), 0, math.radians(15))
    # face : 2 triangle eyes + nose + jagged mouth (all émissif jaune)
    for side, dx in [("L", -0.18), ("R", 0.18)]:
        eye = cube(f"{name}_eye_{side}", size=1.0, loc=(dx * scale, 0.48 * scale, 0.45 * scale), parent=p, mat=MAT_PUMPKIN_FACE)
        eye.scale = (0.10, 0.10, 0.03)
        eye.rotation_euler = (0, 0, math.radians(45))
    nose = cube(f"{name}_nose", size=1.0, loc=(0, 0.40 * scale, 0.47 * scale), parent=p, mat=MAT_PUMPKIN_FACE)
    nose.scale = (0.06, 0.08, 0.03)
    nose.rotation_euler = (0, 0, math.radians(45))
    # 5 mouth teeth
    for k in range(5):
        mx = -0.18 + k * 0.09
        mouth = cube(f"{name}_mouth_{k}", size=1.0, loc=(mx * scale, 0.25 * scale, 0.48 * scale), parent=p, mat=MAT_PUMPKIN_FACE)
        mouth.scale = (0.04, 0.05 + (0.04 if k % 2 == 0 else 0), 0.03)
    return p

pumpkins = []
pumpkin_locs = [(3.5, 4.5, 1.0), (5.5, 6.0, 0.8), (-4.5, 7.0, 1.2), (-3.0, 8.0, 0.7), (4.5, 8.5, 0.9)]
for i, (px, pz, sc) in enumerate(pumpkin_locs):
    p = make_pumpkin(f"pumpkin_{i}", px, pz, sc)
    pumpkins.append(p)

# --- chauve-souris volante -------------------------------------------------
bat_p = empty("bat", (0, 6.5, 5))
bat_body = sphere("bat_body", r=0.15, segs=12, rings=8, loc=(0, 0, 0), parent=bat_p, mat=MAT_BAT)
bat_body.scale = (1.0, 0.8, 1.4)
# 2 wings (large stretched spheres)
for side, dx in [("L", -0.40), ("R", 0.40)]:
    w = sphere(f"bat_wing_{side}", r=0.30, segs=12, rings=8, loc=(dx, 0, 0), parent=bat_p, mat=MAT_BAT)
    w.scale = (1.5, 0.04, 1.0)
# 2 small eyes red
for side, dx in [("L", -0.05), ("R", 0.05)]:
    e = sphere(f"bat_eye_{side}", r=0.03, segs=6, rings=4, loc=(dx, 0.05, 0.13), parent=bat_p, mat=MAT_BAT_EYE)
# 2 small ears
for side, dx in [("L", -0.10), ("R", 0.10)]:
    ear = cone(f"bat_ear_{side}", r1=0.04, r2=0.0, depth=0.12, segs=6, loc=(dx, 0.15, 0), parent=bat_p, mat=MAT_BAT)
    ear.rotation_euler = (math.radians(-30), 0, 0)

# --- 3 corbeaux ------------------------------------------------------------
crows = []
for i in range(3):
    a = i * (math.pi * 2 / 3) + 0.3
    r = 5.5
    bx = math.cos(a) * r + 1
    bz = math.sin(a) * r + 3
    by = 7.0
    cp = empty(f"crow_{i}", (bx, by, bz))
    body = sphere(f"crow_{i}_body", r=0.15, segs=10, rings=8, loc=(0, 0, 0), parent=cp, mat=MAT_CROW)
    body.scale = (1.4, 0.7, 1.0)
    for side, xx in (("L", -0.30), ("R", 0.30)):
        w = cube(f"crow_{i}_w_{side}", size=1.0, loc=(xx, 0, 0), parent=cp, mat=MAT_CROW)
        w.scale = (0.20, 0.02, 0.12)
    # tiny beak
    beak = cone(f"crow_{i}_beak", r1=0.04, r2=0.01, depth=0.08, segs=6, loc=(0, 0, 0.18), parent=cp, mat=MAT_PUMPKIN_FACE)
    beak.rotation_euler = (math.radians(90), 0, 0)
    crows.append((cp, a, r, by))

# --- arbre mort tordu ------------------------------------------------------
tree_p = empty("tree_dead", (5.5, 0, 6.5))
# trunk : 5 segments curving
for i in range(5):
    sx = math.sin(i * 0.6) * 0.3
    h = 0.5 + i * 0.7
    tr = cone(f"tree_trunk_{i}", r1=0.30 - i * 0.04, r2=0.28 - i * 0.04, depth=0.7, segs=8, loc=(sx, h, 0), parent=tree_p, mat=MAT_TREE_DEAD)
    tr.rotation_euler = (math.radians(90), 0, math.radians(20) * math.sin(i * 0.7))
# 6 dead branches
for j in range(6):
    a = j * (math.pi * 2 / 6) + 0.2
    bx = math.cos(a) * 0.5
    bz = math.sin(a) * 0.5
    bra = cone(f"branch_{j}", r1=0.12, r2=0.02, depth=1.5, segs=6, loc=(bx, 3.5, bz), parent=tree_p, mat=MAT_TREE_DEAD)
    bra.rotation_euler = (math.radians(60), 0, a)
    # sub-branches
    sb = cone(f"sub_branch_{j}", r1=0.05, r2=0.01, depth=0.6, segs=6, loc=(bx * 1.5, 4.0, bz * 1.5), parent=tree_p, mat=MAT_TREE_DEAD)
    sb.rotation_euler = (math.radians(40), 0, a + 0.5)

# --- 6 tombes (gravestones) -----------------------------------------------
tomb_locs = [
    (-5.5, -2.0, 0),
    (-3.5, -3.0, math.radians(15)),
    (-2.0, -1.5, math.radians(-10)),
    (3.0, -3.5, math.radians(5)),
    (5.0, -2.5, math.radians(-20)),
    (1.5, -4.0, math.radians(8)),
]
for i, (tx, tz, rot) in enumerate(tomb_locs):
    tp = empty(f"tomb_{i}", (tx, 0, tz))
    tp.rotation_euler = (0, 0, rot)
    # cross or round depending on i
    if i % 2 == 0:
        # round-top tombstone
        body = cube(f"tomb_{i}_body", size=1.0, loc=(0, 0.4, 0), parent=tp, mat=MAT_TOMB_STONE)
        body.scale = (0.5, 0.8, 0.10)
        top = cone(f"tomb_{i}_top", r1=0.25, r2=0.25, depth=0.10, segs=20, loc=(0, 0.85, 0), parent=tp, mat=MAT_TOMB_STONE)
        top.rotation_euler = (math.radians(90), 0, 0)
        top.scale = (1.0, 1.0, 0.3)
    else:
        # cross-shape
        cross_v = cube(f"tomb_{i}_v", size=1.0, loc=(0, 0.5, 0), parent=tp, mat=MAT_TOMB_DARK)
        cross_v.scale = (0.10, 1.0, 0.10)
        cross_h = cube(f"tomb_{i}_h", size=1.0, loc=(0, 0.75, 0), parent=tp, mat=MAT_TOMB_DARK)
        cross_h.scale = (0.50, 0.10, 0.10)

# --- clôture cassée -------------------------------------------------------
for i in range(12):
    fx = -7 + i * 1.2 + random.uniform(-0.1, 0.1)
    fz = -5.5 + math.sin(i * 0.3) * 0.2
    if random.random() < 0.85:  # 85% standing, 15% missing
        fp = empty(f"fence_p_{i}", (fx, 0, fz))
        fp.rotation_euler = (0, 0, math.radians(random.uniform(-15, 15)))
        post = cube(f"fence_{i}", size=1.0, loc=(0, 0.5, 0), parent=fp, mat=MAT_FENCE)
        post.scale = (0.05, 0.9, 0.10)
        # tip pointy
        tip = cone(f"fence_{i}_tip", r1=0.05, r2=0.0, depth=0.15, segs=4, loc=(0, 1.0, 0), parent=fp, mat=MAT_FENCE)
        tip.rotation_euler = (math.radians(90), 0, math.radians(45))

# horizontal rail
rail = cube("fence_rail", size=1.0, loc=(0, 0.5, -5.5), mat=MAT_FENCE)
rail.scale = (12, 0.05, 0.04)

# --- 12 puffs brouillard violet -------------------------------------------
fogs = []
for i in range(12):
    fx = random.uniform(-10, 10)
    fz = random.uniform(-5, 7)
    fy = random.uniform(0.5, 2.5)
    f = sphere(f"fog_{i}", r=random.uniform(0.8, 1.5), segs=14, rings=10, loc=(fx, fy, fz), mat=MAT_FOG_PURPLE)
    f.scale = (1.4, 0.45, 1.2)
    fogs.append((f, fx, fz, fy, random.uniform(0, math.pi * 2)))

# --- 2 bushes morts -------------------------------------------------------
for i, (bx, bz) in enumerate([(-7.0, 3.5), (7.5, 4.0)]):
    bp = empty(f"bush_{i}", (bx, 0, bz))
    # cluster of small dark spheres
    for j in range(5):
        ja = j * (math.pi * 2 / 5)
        jx = math.cos(ja) * 0.30
        jz = math.sin(ja) * 0.30
        b = sphere(f"bush_{i}_{j}", r=0.25, segs=10, rings=8, loc=(jx, 0.25, jz), parent=bp, mat=MAT_BUSH_DEAD)
        b.scale = (1.0, 0.7, 1.0)

# --- 1 ghost flottant -----------------------------------------------------
ghost_p = empty("ghost", (3.5, 3.5, 3.0))
ghost_body = sphere("ghost_body", r=0.40, segs=14, rings=10, loc=(0, 0, 0), parent=ghost_p, mat=MAT_GHOST)
ghost_body.scale = (1.0, 1.4, 1.0)
# wavy bottom (3 small spheres hanging)
for j in range(3):
    ja = -0.5 + j * 0.5
    g = sphere(f"ghost_tail_{j}", r=0.18, segs=10, rings=6, loc=(ja * 0.3, -0.4, 0), parent=ghost_p, mat=MAT_GHOST)
# 2 hollow eyes
for side, dx in [("L", -0.12), ("R", 0.12)]:
    eye = sphere(f"ghost_eye_{side}", r=0.06, segs=8, rings=6, loc=(dx, 0.15, 0.30), parent=ghost_p, mat=MAT_BAT)
    eye.scale = (1.0, 1.3, 0.5)

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

# bat : erratic flight (figure-8)
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    angle = tt * math.pi * 4.0
    bx = 3.5 * math.sin(angle)
    bz = 3.0 * math.sin(angle * 2.0) + 4.0
    by = 6.5 + math.sin(tt * math.pi * 6.0) * 0.5
    kf_loc(bat_p, f, (bx, by, bz))
    kf_rot(bat_p, f, (0, -angle * 2, math.radians(20) * math.sin(tt * math.pi * 10.0)))
    # wing flap (scale Y of wings -- approximate via overall scale)
    s = 1.0 + 0.3 * math.sin(tt * math.pi * 30.0)
    kf_scale(bat_p, f, (s, 1.0, 1.0))

# crows orbit
for cp, a0, r, by in crows:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 2.0
        bx = math.cos(angle) * r + 1
        bz = math.sin(angle) * r + 3
        by_a = by + 0.3 * math.sin(tt * math.pi * 4.0 + a0 * 2)
        kf_loc(cp, f, (bx, by_a, bz))
        kf_rot(cp, f, (0, -angle + math.pi / 2, math.radians(15) * math.sin(tt * math.pi * 10.0)))

# pumpkins pulse face glow (whole scale)
for i, p in enumerate(pumpkins):
    phase = i * 0.7
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.06 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(p, f, (s, s, s))

# fog drift
for fg, fx0, fz0, fy0, ph in fogs:
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        dx = fx0 + 0.6 * math.sin(tt * math.pi * 1.2 + ph)
        dz = fz0 + 0.5 * math.cos(tt * math.pi * 1.5 + ph)
        dy = fy0 + 0.3 * math.sin(tt * math.pi * 2.0 + ph * 0.7)
        kf_loc(fg, f, (dx, dy, dz))
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 3.5 + ph)
        kf_scale(fg, f, (1.4 * s, 0.45, 1.2 * s))

# windows pulse
for i, w in enumerate(windows):
    phase = i * 0.5
    base_x = w.scale.x
    base_y = w.scale.y
    base_z = w.scale.z
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.10 * math.sin(tt * math.pi * 6.0 + phase)
        kf_scale(w, f, (base_x * s, base_y * s, base_z))

# moon halo breathe
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.15 * math.sin(tt * math.pi * 3.0)
    kf_scale(moon_halo, f, (s, s, s))

# chimney smoke rise
for puff, idx in chim_smokes:
    phase = idx * 12
    base_y = puff.location.y
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 70
        lt = local_f / 70
        dy = base_y + lt * 1.8
        dx = math.sin(lt * math.pi * 3.0) * 0.2
        kf_loc(puff, f, (dx, dy, 0))
        s = 0.5 + lt * 1.5
        kf_scale(puff, f, (s, s, s))

# ghost float
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    angle = tt * math.pi * 1.5
    gx = 3.5 + math.cos(angle) * 2.0
    gz = 3.0 + math.sin(angle) * 1.5
    gy = 3.5 + 0.5 * math.sin(tt * math.pi * 4.0)
    kf_loc(ghost_p, f, (gx, gy, gz))
    kf_rot(ghost_p, f, (0, -angle, math.radians(5) * math.sin(tt * math.pi * 6.0)))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_hauntedhouse] wrote {OUT}")
