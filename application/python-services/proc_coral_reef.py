"""
proc_coral_reef.py — 115e procédural AuroraIA, Phase F++++.

Récif corallien sous-marin : sol sablonneux + 8 coraux variés (branchu,
cerveau, table, doigts, fans) + 15 poissons tropicaux (jaune/bleu/orange/
rose) + 1 tortue marine + 2 méduses translucides + algues ondulantes
+ 20 bulles montantes + 6 rayons soleil pénétrant + eau bleu turquoise
en haut + 4 étoiles de mer.

Animation :
- 15 fish swim circles différenciés
- 2 méduses pulse (scale Y) + tentacules sway
- tortue glide horizontal + tilt
- 20 bulles montent puis fade
- 8 algues sway
- rayons soleil pulse douce
- coraux fan sway

Sortie : output/3d/pbr_coralreef_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_coralreef_proc.glb"))

random.seed(0xC04A1F)

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
MAT_WATER = make_mat(
    "water_top", (0.20, 0.60, 0.75), roughness=0.05, metallic=0.5, alpha=0.55,
    emi=(0.30, 0.70, 0.85), emi_strength=0.8,
)
MAT_WATER_DEEP = make_mat("water_deep", (0.05, 0.20, 0.30), roughness=0.6,
                            emi=(0.05, 0.20, 0.30), emi_strength=0.3)
MAT_SAND = make_mat("sand", (0.85, 0.78, 0.55), roughness=0.95)
MAT_ROCK = make_mat("rock", (0.30, 0.28, 0.22), roughness=0.95)
MAT_CORAL_PINK = make_mat("coral_pink", (0.95, 0.40, 0.55), roughness=0.7,
                            emi=(0.6, 0.2, 0.3), emi_strength=0.3)
MAT_CORAL_ORANGE = make_mat("coral_orange", (1.0, 0.55, 0.20), roughness=0.7,
                              emi=(0.7, 0.3, 0.1), emi_strength=0.3)
MAT_CORAL_PURPLE = make_mat("coral_purple", (0.75, 0.30, 0.95), roughness=0.7,
                              emi=(0.45, 0.15, 0.7), emi_strength=0.3)
MAT_CORAL_BLUE = make_mat("coral_blue", (0.30, 0.65, 0.95), roughness=0.7,
                            emi=(0.15, 0.4, 0.7), emi_strength=0.3)
MAT_CORAL_BRAIN = make_mat("coral_brain", (0.90, 0.75, 0.60), roughness=0.85)
MAT_CORAL_FAN = make_mat("coral_fan", (1.0, 0.30, 0.30), roughness=0.75,
                            emi=(0.5, 0.1, 0.1), emi_strength=0.4)
MAT_FISH_YELLOW = make_mat("fish_yellow", (1.0, 0.85, 0.10), roughness=0.5,
                             emi=(0.4, 0.35, 0.05), emi_strength=0.3)
MAT_FISH_BLUE = make_mat("fish_blue", (0.20, 0.45, 1.0), roughness=0.5,
                            emi=(0.1, 0.2, 0.5), emi_strength=0.4)
MAT_FISH_ORANGE = make_mat("fish_orange", (1.0, 0.45, 0.10), roughness=0.5,
                              emi=(0.5, 0.2, 0.05), emi_strength=0.4)
MAT_FISH_PINK = make_mat("fish_pink", (1.0, 0.55, 0.75), roughness=0.5,
                            emi=(0.5, 0.25, 0.35), emi_strength=0.3)
MAT_FISH_STRIPE = make_mat("fish_stripe", (0.10, 0.10, 0.10), roughness=0.5)
MAT_TURTLE_BODY = make_mat("turtle_body", (0.25, 0.40, 0.20), roughness=0.7)
MAT_TURTLE_SHELL = make_mat("turtle_shell", (0.40, 0.30, 0.15), roughness=0.6,
                              emi=(0.15, 0.1, 0.05), emi_strength=0.2)
MAT_JELLY = make_mat(
    "jelly", (0.85, 0.55, 0.95), roughness=0.0, alpha=0.55,
    emi=(0.8, 0.4, 1.0), emi_strength=3.0,
)
MAT_JELLY_TENT = make_mat(
    "jelly_tent", (0.95, 0.7, 1.0), roughness=0.0, alpha=0.45,
    emi=(0.85, 0.55, 1.0), emi_strength=2.5,
)
MAT_ALGAE = make_mat("algae", (0.10, 0.50, 0.20), roughness=0.85,
                       emi=(0.05, 0.25, 0.1), emi_strength=0.2)
MAT_BUBBLE = make_mat(
    "bubble", (0.85, 0.95, 1.0), roughness=0.0, alpha=0.5,
    emi=(0.8, 0.9, 1.0), emi_strength=1.5,
)
MAT_SUN_RAY = make_mat(
    "sun_ray", (1.0, 0.95, 0.70), roughness=0.0, alpha=0.20,
    emi=(1.0, 0.95, 0.65), emi_strength=2.5,
)
MAT_STARFISH = make_mat("starfish", (1.0, 0.55, 0.25), roughness=0.7,
                          emi=(0.5, 0.25, 0.10), emi_strength=0.4)

# --- backdrop ---------------------------------------------------------------
back = cube("water_deep_back", size=1.0, loc=(0, 12, 0), mat=MAT_WATER_DEEP)
back.scale = (28, 0.1, 16)

# water top surface (translucent ceiling effect)
water_top = cube("water_top_surface", size=1.0, loc=(0, 11.0, 4.0), mat=MAT_WATER)
water_top.scale = (28, 0.1, 16)

# --- sandy ground -----------------------------------------------------------
sand = cube("sand_ground", size=1.0, loc=(0, -0.05, 0), mat=MAT_SAND)
sand.scale = (30, 0.1, 22)

# small rocks scattered
for i in range(10):
    rx = random.uniform(-10, 10)
    rz = random.uniform(-8, 8)
    rsize = random.uniform(0.2, 0.5)
    rk = sphere(f"rock_{i}", r=rsize, segs=10, rings=8, loc=(rx, 0.15, rz), mat=MAT_ROCK)
    rk.scale = (1.0, 0.4, 1.0)

# --- 8 coraux variés --------------------------------------------------------
# 1. Branching coral (3 sphere chains)
def make_branching_coral(name, x, z, mat):
    p = empty(name, (x, 0.3, z))
    base_r = 0.30
    sphere(f"{name}_base", r=base_r, segs=12, rings=8, loc=(0, 0, 0), parent=p, mat=mat)
    for i in range(5):
        a = i * (math.pi * 2 / 5)
        bx = math.cos(a) * 0.15
        bz = math.sin(a) * 0.15
        # 3 spheres stacked
        for j in range(3):
            ys = 0.3 + j * 0.22
            rr = 0.18 - j * 0.03
            sphere(f"{name}_b{i}_{j}", r=rr, segs=10, rings=8, loc=(bx * (1 + j * 0.3), ys, bz * (1 + j * 0.3)), parent=p, mat=mat)
    return p

# 2. Brain coral (compact ridged sphere)
def make_brain_coral(name, x, z, mat):
    p = empty(name, (x, 0.4, z))
    main = sphere(f"{name}_main", r=0.50, segs=18, rings=12, loc=(0, 0, 0), parent=p, mat=mat)
    main.scale = (1.2, 0.7, 1.0)
    # 6 small bumps for ridges
    for i in range(6):
        a = i * (math.pi * 2 / 6)
        bx = math.cos(a) * 0.35
        bz = math.sin(a) * 0.30
        b = sphere(f"{name}_bump_{i}", r=0.12, segs=8, rings=6, loc=(bx, 0.15, bz), parent=p, mat=mat)
    return p

# 3. Table coral (flat top + stem)
def make_table_coral(name, x, z, mat):
    p = empty(name, (x, 0.3, z))
    stem = cone(f"{name}_stem", r1=0.15, r2=0.20, depth=0.6, segs=10, loc=(0, 0.1, 0), parent=p, mat=mat)
    stem.rotation_euler = (math.radians(90), 0, 0)
    table = cone(f"{name}_table", r1=0.75, r2=0.85, depth=0.18, segs=14, loc=(0, 0.5, 0), parent=p, mat=mat)
    table.rotation_euler = (math.radians(90), 0, 0)
    return p

# 4. Finger coral (many vertical fingers)
def make_finger_coral(name, x, z, mat):
    p = empty(name, (x, 0.2, z))
    sphere(f"{name}_base", r=0.30, segs=12, rings=8, loc=(0, 0, 0), parent=p, mat=mat)
    for i in range(12):
        a = i * (math.pi * 2 / 12)
        r = 0.18 + random.uniform(-0.05, 0.05)
        bx = math.cos(a) * r
        bz = math.sin(a) * r
        h = random.uniform(0.5, 0.9)
        f = cone(f"{name}_finger_{i}", r1=0.06, r2=0.04, depth=h, segs=6, loc=(bx, 0.1 + h / 2, bz), parent=p, mat=mat)
        f.rotation_euler = (math.radians(90), 0, 0)
    return p

# 5. Sea fan (flat vertical fan)
def make_fan_coral(name, x, z, mat):
    p = empty(name, (x, 0.3, z))
    base = cone(f"{name}_base", r1=0.20, r2=0.15, depth=0.3, segs=8, loc=(0, 0, 0), parent=p, mat=mat)
    base.rotation_euler = (math.radians(90), 0, 0)
    # fan shape : multiple flat cubes radiating from base
    fan_p = empty(f"{name}_fan_p", (0, 0.4, 0), parent=p)
    for i in range(9):
        a = -math.pi / 3 + i * (2 * math.pi / 3 / 8)
        h = 0.7 + random.uniform(-0.1, 0.2)
        seg = cube(f"{name}_seg_{i}", size=1.0, loc=(0, h / 2, 0), parent=fan_p, mat=mat)
        seg.scale = (0.06, h, 0.06)
        seg.rotation_euler = (0, 0, a)
    return p, fan_p

coral_objs = []
coral_fans = []
coral_data = [
    ("branching", (-3.5, -1.0), MAT_CORAL_PINK),
    ("brain", (-1.5, -0.5), MAT_CORAL_BRAIN),
    ("table", (1.0, 0.5), MAT_CORAL_PURPLE),
    ("finger", (3.0, -1.5), MAT_CORAL_ORANGE),
    ("fan", (5.0, 0.0), MAT_CORAL_FAN),
    ("branching", (-5.5, 1.5), MAT_CORAL_BLUE),
    ("brain", (4.0, 2.5), MAT_CORAL_BRAIN),
    ("fan", (-2.0, 2.0), MAT_CORAL_FAN),
]
for i, (kind, (x, z), mat) in enumerate(coral_data):
    name = f"coral_{i}_{kind}"
    if kind == "branching":
        p = make_branching_coral(name, x, z, mat)
        coral_objs.append(p)
    elif kind == "brain":
        p = make_brain_coral(name, x, z, mat)
        coral_objs.append(p)
    elif kind == "table":
        p = make_table_coral(name, x, z, mat)
        coral_objs.append(p)
    elif kind == "finger":
        p = make_finger_coral(name, x, z, mat)
        coral_objs.append(p)
    elif kind == "fan":
        p, fan_p = make_fan_coral(name, x, z, mat)
        coral_objs.append(p)
        coral_fans.append(fan_p)

# --- 15 fishes scattered ----------------------------------------------------
def make_fish(name, scale=1.0, body_mat=MAT_FISH_YELLOW, parent=None):
    p = empty(name, (0, 0, 0), parent=parent)
    body = sphere(f"{name}_body", r=0.15 * scale, segs=14, rings=10, loc=(0, 0, 0), parent=p, mat=body_mat)
    body.scale = (1.5, 0.9, 0.7)
    # tail
    tail = cone(f"{name}_tail", r1=0.12 * scale, r2=0.02 * scale, depth=0.15 * scale, segs=4, loc=(-0.20 * scale, 0, 0), parent=p, mat=body_mat)
    tail.rotation_euler = (0, math.radians(-90), 0)
    tail.scale = (1.0, 1.4, 0.3)
    # eye
    eye = sphere(f"{name}_eye", r=0.025 * scale, segs=6, rings=4, loc=(0.13 * scale, 0.03 * scale, 0.06 * scale), parent=p, mat=MAT_FISH_STRIPE)
    return p

fish_colors = [MAT_FISH_YELLOW, MAT_FISH_BLUE, MAT_FISH_ORANGE, MAT_FISH_PINK]
fishes = []
for i in range(15):
    cx = random.uniform(-9, 9)
    cy = random.uniform(1.5, 8.5)
    cz = random.uniform(-7, 7)
    f = make_fish(f"fish_{i}", scale=random.uniform(0.8, 1.4), body_mat=random.choice(fish_colors))
    f.location = (cx, cy, cz)
    f["_a0"] = random.uniform(0, math.pi * 2)
    f["_r"] = random.uniform(1.0, 2.5)
    f["_y0"] = cy
    f["_x0"] = cx
    f["_z0"] = cz
    f["_spd"] = random.uniform(0.7, 1.6)
    f["_dir"] = random.choice([1, -1])
    fishes.append(f)

# --- 1 sea turtle -----------------------------------------------------------
turtle_p = empty("turtle", (-4.0, 5.0, 1.0))
shell = sphere("turtle_shell", r=0.45, segs=18, rings=12, loc=(0, 0, 0), parent=turtle_p, mat=MAT_TURTLE_SHELL)
shell.scale = (1.3, 0.5, 1.0)
# head poking out front
head = sphere("turtle_head", r=0.15, segs=12, rings=8, loc=(0.55, 0, 0), parent=turtle_p, mat=MAT_TURTLE_BODY)
head.scale = (1.0, 0.9, 0.9)
# 4 fins
for i, (fx, fz, rot) in enumerate([(0.25, 0.45, math.radians(15)), (0.25, -0.45, math.radians(-15)), (-0.25, 0.45, math.radians(30)), (-0.25, -0.45, math.radians(-30))]):
    fin = sphere(f"turtle_fin_{i}", r=0.12, segs=10, rings=6, loc=(fx, 0, fz), parent=turtle_p, mat=MAT_TURTLE_BODY)
    fin.scale = (1.6, 0.3, 0.8)
    fin.rotation_euler = (0, 0, rot)
# tail
tail = cone("turtle_tail", r1=0.05, r2=0.01, depth=0.18, segs=6, loc=(-0.55, 0, 0), parent=turtle_p, mat=MAT_TURTLE_BODY)
tail.rotation_euler = (0, math.radians(90), 0)

# --- 2 jellyfish ------------------------------------------------------------
jellies = []
for i, (jx, jy, jz) in enumerate([(2.5, 7.5, 2.0), (-2.0, 6.0, -1.5)]):
    jp = empty(f"jelly_{i}", (jx, jy, jz))
    bell = sphere(f"jelly_{i}_bell", r=0.5, segs=18, rings=12, loc=(0, 0, 0), parent=jp, mat=MAT_JELLY)
    bell.scale = (1.0, 0.55, 1.0)
    # 6 tentacles
    for j in range(6):
        a = j * (math.pi * 2 / 6)
        tx = math.cos(a) * 0.35
        tz = math.sin(a) * 0.35
        # 4 segments per tentacle, drooping down
        for k in range(4):
            ty = -0.2 - k * 0.25
            rr = 0.04 - k * 0.005
            t = sphere(f"jelly_{i}_t{j}_{k}", r=rr, segs=8, rings=6, loc=(tx, ty, tz), parent=jp, mat=MAT_JELLY_TENT)
    jellies.append(jp)

# --- 8 algues ondulantes ----------------------------------------------------
algae = []
algae_locs = [(-7, -2.5), (-6, 3), (-3, 4), (0, -3), (2, 3.5), (4, -2), (6, -3.5), (7, 2)]
for i, (x, z) in enumerate(algae_locs):
    ap = empty(f"algae_{i}", (x, 0.05, z))
    # 5 segments stacked
    for j in range(5):
        ys = 0.3 + j * 0.6
        rr = 0.08 - j * 0.01
        seg = cone(f"algae_{i}_{j}", r1=rr, r2=rr * 0.7, depth=0.6, segs=6, loc=(0, ys, 0), parent=ap, mat=MAT_ALGAE)
        seg.rotation_euler = (math.radians(90), 0, 0)
    algae.append(ap)

# --- 20 bulles montantes ----------------------------------------------------
bubbles = []
for i in range(20):
    bx = random.uniform(-8, 8)
    bz = random.uniform(-7, 7)
    by = random.uniform(0.5, 9.0)
    br = random.uniform(0.05, 0.12)
    b = sphere(f"bubble_{i}", r=br, segs=10, rings=8, loc=(bx, by, bz), mat=MAT_BUBBLE)
    b["_x"] = bx
    b["_z"] = bz
    b["_ph"] = random.uniform(0, 1)
    b["_spd"] = random.uniform(0.7, 1.3)
    bubbles.append(b)

# --- 6 rayons soleil pénétrant du dessus -----------------------------------
sun_rays = []
for i in range(6):
    rx = -8 + i * 3.2
    rz = random.uniform(-5, 5)
    rp = empty(f"sun_ray_p_{i}", (rx, 6.0, rz))
    rp.rotation_euler = (0, 0, math.radians(random.uniform(-5, 5)))
    ray = cube(f"sun_ray_{i}", size=1.0, loc=(0, 0, 0), parent=rp, mat=MAT_SUN_RAY)
    ray.scale = (0.6, 10.0, 0.6)
    sun_rays.append(ray)

# --- 4 starfish on the sand ------------------------------------------------
for i in range(4):
    sx = random.uniform(-7, 7)
    sz = random.uniform(-5, 5)
    sp = empty(f"starfish_{i}", (sx, 0.10, sz))
    # 5 arms radiating
    for j in range(5):
        a = j * (math.pi * 2 / 5)
        arm = cone(f"starfish_{i}_arm_{j}", r1=0.08, r2=0.02, depth=0.3, segs=6, loc=(math.cos(a) * 0.18, 0, math.sin(a) * 0.18), parent=sp, mat=MAT_STARFISH)
        arm.rotation_euler = (math.radians(90), a, 0)
        arm.scale = (1.0, 0.3, 1.0)

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

# fishes swim circles
for fish in fishes:
    a0 = fish["_a0"]
    r = fish["_r"]
    y0 = fish["_y0"]
    x0 = fish["_x0"]
    z0 = fish["_z0"]
    spd = fish["_spd"]
    direction = fish["_dir"]
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + direction * tt * math.pi * 2.0 * spd
        x = x0 + math.cos(angle) * r
        z = z0 + math.sin(angle) * r
        y = y0 + 0.3 * math.sin(tt * math.pi * 4.0 + a0)
        kf_loc(fish, f, (x, y, z))
        kf_rot(fish, f, (0, -angle * direction, math.radians(8) * math.sin(tt * math.pi * 8.0)))

# turtle glide horizontal
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    angle = tt * math.pi * 1.5
    tx = math.sin(angle) * 5.0 - 4.0
    ty = 5.0 + 0.4 * math.sin(tt * math.pi * 3.0)
    tz = math.cos(angle) * 2.0 + 1.0
    kf_loc(turtle_p, f, (tx, ty, tz))
    kf_rot(turtle_p, f, (0, -angle, math.radians(10) * math.sin(tt * math.pi * 4.0)))

# jellies pulse + drift
for i, jp in enumerate(jellies):
    bx0 = jp.location.x
    bz0 = jp.location.z
    by0 = jp.location.y
    phase = i * 0.7
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        dx = bx0 + 0.4 * math.sin(tt * math.pi * 1.2 + phase)
        dy = by0 + 0.6 * math.sin(tt * math.pi * 2.0 + phase) - tt * 0.5
        dz = bz0 + 0.3 * math.cos(tt * math.pi * 1.5 + phase)
        kf_loc(jp, f, (dx, dy, dz))
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 6.0 + phase)
        kf_scale(jp, f, (s, 1.0 / s if s > 0 else 1.0, s))  # bell contracts and expands

# algae sway
for i, ap in enumerate(algae):
    phase = i * 0.6
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bend = math.radians(15) * math.sin(tt * math.pi * 3.0 + phase)
        kf_rot(ap, f, (0, 0, bend))

# bubbles rise + reset
for b in bubbles:
    bx = b["_x"]
    bz = b["_z"]
    ph = b["_ph"]
    spd = b["_spd"]
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        local = (tt + ph) % 1.0
        by = 0.5 + local * 9.5
        wob = 0.15 * math.sin(local * math.pi * 6.0)
        kf_loc(b, f, (bx + wob, by, bz + wob * 0.5))
        # scale slight grow as it rises
        s = 0.6 + 0.5 * local
        kf_scale(b, f, (s, s, s))

# sun rays pulse
for i, ray in enumerate(sun_rays):
    base_x = ray.scale.x
    base_z = ray.scale.z
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 4.0 + i * 0.5)
        kf_scale(ray, f, (base_x * s, ray.scale.y, base_z * s))

# coral fans sway
for fan_p in coral_fans:
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bend = math.radians(8) * math.sin(tt * math.pi * 3.5)
        kf_rot(fan_p, f, (0, bend, 0))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_coralreef] wrote {OUT}")
