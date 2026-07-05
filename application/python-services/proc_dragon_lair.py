"""
proc_dragon_lair.py — 118e procédural AuroraIA, Phase F++++.

Antre du dragon : grotte sombre + dragon endormi enroulé sur trésor
+ corps long avec écailles + tête + cornes + ailes repliées + queue
+ pile or (30 pièces) + 5 coffres au trésor ouverts + 4 stalactites
+ 3 stalagmites + cristaux émissifs + 3 torches murales + 15 gemmes
brillantes + crâne squelette + épée plantée + sol pierre.

Animation :
- dragon : respire (scale Y subtle) + paupière clignote occasionnel
- 3 torches : flammes pulse
- 15 gemmes : pulse émission différentielle
- pile or : subtle shimmer émission
- cristaux : scintille
- dragon yeux : pulse rouge (presque endormi)

Sortie : output/3d/pbr_dragonlair_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_dragonlair_proc.glb"))

random.seed(0xDEAD12)

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
MAT_CAVE_DARK = make_mat("cave_dark", (0.08, 0.07, 0.06), roughness=0.95)
MAT_CAVE_FLOOR = make_mat("cave_floor", (0.20, 0.17, 0.14), roughness=0.95)
MAT_CAVE_WALL = make_mat("cave_wall", (0.12, 0.10, 0.09), roughness=0.95)
MAT_DRAGON_BODY = make_mat("dragon_body", (0.20, 0.05, 0.05), roughness=0.6,
                             emi=(0.08, 0.02, 0.02), emi_strength=0.15)
MAT_DRAGON_BELLY = make_mat("dragon_belly", (0.45, 0.30, 0.10), roughness=0.5,
                              emi=(0.18, 0.10, 0.04), emi_strength=0.2)
MAT_DRAGON_SCALE = make_mat("dragon_scale", (0.30, 0.08, 0.06), roughness=0.4, metallic=0.3,
                              emi=(0.12, 0.03, 0.02), emi_strength=0.2)
MAT_DRAGON_HORN = make_mat("dragon_horn", (0.15, 0.10, 0.08), roughness=0.6)
MAT_DRAGON_WING = make_mat("dragon_wing", (0.25, 0.06, 0.06), roughness=0.55, alpha=0.95,
                             emi=(0.10, 0.02, 0.02), emi_strength=0.15)
MAT_DRAGON_EYE = make_mat("dragon_eye", (1.0, 0.20, 0.05), roughness=0.0,
                            emi=(1.0, 0.20, 0.05), emi_strength=6.0)
MAT_GOLD = make_mat("gold", (1.0, 0.78, 0.20), metallic=0.95, roughness=0.20,
                     emi=(0.55, 0.40, 0.05), emi_strength=0.5)
MAT_GOLD_BRIGHT = make_mat("gold_bright", (1.0, 0.85, 0.30), metallic=0.95, roughness=0.10,
                             emi=(0.85, 0.65, 0.10), emi_strength=1.2)
MAT_WOOD_CHEST = make_mat("chest_wood", (0.30, 0.18, 0.10), roughness=0.85)
MAT_WOOD_METAL = make_mat("chest_metal", (0.55, 0.50, 0.40), metallic=0.7, roughness=0.4)
MAT_STALAC = make_mat("stalactite", (0.45, 0.40, 0.35), roughness=0.85)
MAT_CRYSTAL_PURPLE = make_mat("crystal_purple", (0.65, 0.25, 1.0), roughness=0.0, alpha=0.85,
                                emi=(0.55, 0.20, 1.0), emi_strength=4.0)
MAT_CRYSTAL_BLUE = make_mat("crystal_blue", (0.20, 0.55, 1.0), roughness=0.0, alpha=0.85,
                              emi=(0.10, 0.45, 1.0), emi_strength=4.5)
MAT_CRYSTAL_GREEN = make_mat("crystal_green", (0.20, 1.0, 0.50), roughness=0.0, alpha=0.85,
                               emi=(0.10, 1.0, 0.40), emi_strength=4.0)
MAT_TORCH_HANDLE = make_mat("torch_handle", (0.30, 0.20, 0.12), roughness=0.85)
MAT_TORCH_FLAME = make_mat("torch_flame", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85,
                             emi=(1.0, 0.55, 0.10), emi_strength=8.0)
MAT_GEM_RUBY = make_mat("gem_ruby", (1.0, 0.10, 0.20), roughness=0.0,
                          emi=(1.0, 0.10, 0.20), emi_strength=5.0)
MAT_GEM_SAPPHIRE = make_mat("gem_sapphire", (0.10, 0.30, 1.0), roughness=0.0,
                              emi=(0.10, 0.30, 1.0), emi_strength=5.0)
MAT_GEM_EMERALD = make_mat("gem_emerald", (0.10, 1.0, 0.30), roughness=0.0,
                             emi=(0.10, 1.0, 0.30), emi_strength=5.0)
MAT_GEM_DIAMOND = make_mat("gem_diamond", (0.95, 0.98, 1.0), roughness=0.0,
                             emi=(0.85, 0.92, 1.0), emi_strength=6.0)
MAT_SKULL = make_mat("skull", (0.90, 0.88, 0.80), roughness=0.6)
MAT_SWORD_BLADE = make_mat("sword_blade", (0.85, 0.85, 0.90), metallic=0.95, roughness=0.15)
MAT_SWORD_HILT = make_mat("sword_hilt", (0.55, 0.40, 0.20), roughness=0.7)

# --- backdrop : cave walls --------------------------------------------------
# cave is enclosed : back wall + 2 side walls + floor + ceiling
# back wall
back = cube("cave_back", size=1.0, loc=(0, 16, 4), mat=MAT_CAVE_WALL)
back.scale = (24, 0.2, 14)

# floor
floor = cube("cave_floor", size=1.0, loc=(0, 0, 0), mat=MAT_CAVE_FLOOR)
floor.scale = (24, 0.1, 18)

# ceiling (low)
ceiling = cube("cave_ceiling", size=1.0, loc=(0, 9.0, 0), mat=MAT_CAVE_DARK)
ceiling.scale = (24, 0.1, 18)

# 2 side walls
for side, x in [("L", -12), ("R", 12)]:
    w = cube(f"cave_wall_{side}", size=1.0, loc=(x, 4.0, 0), mat=MAT_CAVE_WALL)
    w.scale = (0.1, 8, 18)

# --- gold pile (mound of coins) --------------------------------------------
gold_pile = cube("gold_pile_base", size=1.0, loc=(0, 0.4, 0), mat=MAT_GOLD)
gold_pile.scale = (5.5, 0.8, 4.0)

# 30 coins on top
coins = []
for i in range(30):
    cx = random.uniform(-2.5, 2.5)
    cz = random.uniform(-1.8, 1.8)
    cy = 0.85 + random.uniform(0, 0.15)
    coin = cone(f"coin_{i}", r1=0.15, r2=0.15, depth=0.04, segs=12, loc=(cx, cy, cz), mat=MAT_GOLD_BRIGHT)
    coin.rotation_euler = (math.radians(random.uniform(80, 100)), random.uniform(0, math.pi), random.uniform(0, math.pi))
    coins.append(coin)

# --- 5 treasure chests ------------------------------------------------------
def make_chest(name, x, z, rot, mat_w=MAT_WOOD_CHEST, mat_m=MAT_WOOD_METAL):
    p = empty(name, (x, 0, z))
    p.rotation_euler = (0, rot, 0)
    # body (cube with lid open)
    body = cube(f"{name}_body", size=1.0, loc=(0, 0.30, 0), parent=p, mat=mat_w)
    body.scale = (0.6, 0.35, 0.45)
    # lid (rotated open backward)
    lid = cube(f"{name}_lid", size=1.0, loc=(0, 0.65, -0.42), parent=p, mat=mat_w)
    lid.scale = (0.6, 0.05, 0.50)
    lid.rotation_euler = (math.radians(-60), 0, 0)
    # 4 metal bands
    for i, by in enumerate([0.15, 0.40]):
        band = cube(f"{name}_band_{i}", size=1.0, loc=(0, by, 0), parent=p, mat=mat_m)
        band.scale = (0.65, 0.04, 0.50)
    # gold/gem inside
    inside_pile = cube(f"{name}_inside", size=1.0, loc=(0, 0.45, 0), parent=p, mat=MAT_GOLD_BRIGHT)
    inside_pile.scale = (0.5, 0.15, 0.4)
    return p

chest_data = [
    (-3.5, 1.5, math.radians(20)),
    (3.5, 1.0, math.radians(-15)),
    (-2.0, -2.5, math.radians(35)),
    (4.0, -1.5, math.radians(-25)),
    (0.5, -3.0, math.radians(5)),
]
for i, (cx, cz, rot) in enumerate(chest_data):
    make_chest(f"chest_{i}", cx, cz, rot)

# --- 4 stalactites (from ceiling) ------------------------------------------
for i in range(4):
    sx = -5 + i * 3.5
    sz = random.uniform(-3, 3)
    h = random.uniform(1.2, 2.0)
    st = cone(f"stalactite_{i}", r1=0.45, r2=0.0, depth=h, segs=8, loc=(sx, 9.0 - h / 2, sz), mat=MAT_STALAC)
    st.rotation_euler = (math.radians(-90), 0, 0)

# --- 3 stalagmites (from floor) --------------------------------------------
for i, (sx, sz, h) in enumerate([(-7, -3, 1.8), (8, -2, 1.5), (-9, 3, 1.3)]):
    sg = cone(f"stalagmite_{i}", r1=0.45, r2=0.0, depth=h, segs=8, loc=(sx, h / 2 + 0.1, sz), mat=MAT_STALAC)
    sg.rotation_euler = (math.radians(90), 0, 0)

# --- crystals scattered ----------------------------------------------------
crystals = []
crystal_colors = [MAT_CRYSTAL_PURPLE, MAT_CRYSTAL_BLUE, MAT_CRYSTAL_GREEN]
for i in range(7):
    cx = random.uniform(-10, 10)
    cz = random.uniform(-7, 7)
    if abs(cx) < 5 and abs(cz) < 4:
        continue  # avoid the gold pile area
    h = random.uniform(0.8, 1.5)
    mat = crystal_colors[i % 3]
    cr = cone(f"crystal_{i}", r1=0.20, r2=0.0, depth=h, segs=4, loc=(cx, h / 2 + 0.1, cz), mat=mat)
    cr.rotation_euler = (math.radians(90), 0, math.radians(random.uniform(0, 45)))
    crystals.append(cr)

# --- 3 torches murales -----------------------------------------------------
torch_flames = []
for i, (tx, ty, tz) in enumerate([(-11.5, 4.5, -5), (-11.5, 4.5, 5), (11.5, 4.5, 0)]):
    tp = empty(f"torch_{i}", (tx, ty, tz))
    # handle (cone) stuck to wall
    handle = cone(f"torch_{i}_handle", r1=0.06, r2=0.04, depth=0.7, segs=8, loc=(0.4 if tx > 0 else -0.4, 0, 0), parent=tp, mat=MAT_TORCH_HANDLE)
    handle.rotation_euler = (0, 0, math.radians(90 if tx > 0 else -90))
    # bowl
    bowl = cone(f"torch_{i}_bowl", r1=0.20, r2=0.10, depth=0.25, segs=10, loc=(0.7 if tx > 0 else -0.7, 0, 0), parent=tp, mat=MAT_TORCH_HANDLE)
    bowl.rotation_euler = (math.radians(90), 0, 0)
    # flame (large sphere émissif)
    flame = sphere(f"torch_{i}_flame", r=0.30, segs=12, rings=10, loc=(0.7 if tx > 0 else -0.7, 0.3, 0), parent=tp, mat=MAT_TORCH_FLAME)
    flame.scale = (0.8, 1.5, 0.8)
    torch_flames.append(flame)

# --- 15 gemmes brillantes (scattered in gold pile + around) ----------------
gems = []
gem_mats = [MAT_GEM_RUBY, MAT_GEM_SAPPHIRE, MAT_GEM_EMERALD, MAT_GEM_DIAMOND]
for i in range(15):
    gx = random.uniform(-2.5, 2.5)
    gz = random.uniform(-1.8, 1.8)
    gy = 0.90 + random.uniform(0, 0.15)
    mat = random.choice(gem_mats)
    gem = sphere(f"gem_{i}", r=0.10, segs=10, rings=8, loc=(gx, gy, gz), mat=mat)
    gem.scale = (1.0, 1.5, 1.0)
    gem.rotation_euler = (random.uniform(0, math.pi), random.uniform(0, math.pi), random.uniform(0, math.pi))
    gems.append((gem, i))

# --- dragon ---------------------------------------------------------------
dragon_p = empty("dragon", (0, 0.9, 0))
# main body : 6 sphere segments curving along gold pile
N_BODY = 7
body_segs = []
for i in range(N_BODY):
    t = i / (N_BODY - 1)
    # path curls : angle around pile
    a = t * math.pi * 2.2
    r = 2.2 - t * 0.8  # spiraling inward
    bx = math.cos(a) * r
    bz = math.sin(a) * r
    by = 0.0 + 0.2 * math.sin(t * math.pi * 2)
    rr = 0.55 - t * 0.10
    seg = sphere(f"dragon_body_{i}", r=rr, segs=18, rings=12, loc=(bx, by, bz), parent=dragon_p, mat=MAT_DRAGON_BODY)
    seg.scale = (1.1, 0.8, 1.1)
    body_segs.append(seg)
    # 2 scale spikes per body segment on top
    for k in range(2):
        offa = a + (k - 0.5) * 0.3
        sx = math.cos(offa) * (r + 0.05)
        sz = math.sin(offa) * (r + 0.05)
        spike = cone(f"spike_{i}_{k}", r1=0.08, r2=0.0, depth=0.20, segs=4, loc=(sx, by + rr * 0.8, sz), parent=dragon_p, mat=MAT_DRAGON_SCALE)
        spike.rotation_euler = (math.radians(-90), 0, offa)

# head : front of body, slightly bigger
head_p = empty("dragon_head", (body_segs[0].location.x + 0.5, body_segs[0].location.y + 0.3, body_segs[0].location.z + 0.3), parent=dragon_p)
head_p.rotation_euler = (0, math.radians(15), math.radians(-10))
head = sphere("dragon_head_box", r=0.75, segs=20, rings=14, loc=(0, 0, 0), parent=head_p, mat=MAT_DRAGON_BODY)
head.scale = (1.3, 0.9, 1.1)
# snout extension
snout = cone("dragon_snout", r1=0.45, r2=0.20, depth=0.65, segs=10, loc=(0.65, -0.10, 0), parent=head_p, mat=MAT_DRAGON_BODY)
snout.rotation_euler = (0, math.radians(90), 0)
# 2 horns
for side, dz in [("L", 0.30), ("R", -0.30)]:
    horn = cone(f"horn_{side}", r1=0.10, r2=0.0, depth=0.7, segs=6, loc=(-0.20, 0.50, dz), parent=head_p, mat=MAT_DRAGON_HORN)
    horn.rotation_euler = (math.radians(-110), math.radians(30 if side == "L" else -30), 0)
# 2 small eyes (red, glowing)
eyes = []
for side, dz in [("L", 0.22), ("R", -0.22)]:
    eye = sphere(f"eye_{side}", r=0.10, segs=10, rings=8, loc=(0.35, 0.10, dz), parent=head_p, mat=MAT_DRAGON_EYE)
    eyes.append(eye)
# 2 small teeth
for side, dz in [("L", 0.10), ("R", -0.10)]:
    t = cone(f"tooth_{side}", r1=0.04, r2=0.0, depth=0.15, segs=4, loc=(0.85, -0.30, dz), parent=head_p, mat=MAT_SKULL)
    t.rotation_euler = (math.radians(90), 0, 0)

# 2 wings folded over the back
for side, dz, rot in [("L", 1.2, math.radians(50)), ("R", -1.2, math.radians(-50))]:
    wing_p = empty(f"wing_{side}", (body_segs[1].location.x, body_segs[1].location.y + 0.5, body_segs[1].location.z + dz * 0.6), parent=dragon_p)
    wing_p.rotation_euler = (0, 0, rot)
    # 3 wing finger bones (cones) + membrane (flat squashed sphere)
    membrane = sphere(f"wing_{side}_mem", r=0.6, segs=14, rings=10, loc=(0, 0.2, 0), parent=wing_p, mat=MAT_DRAGON_WING)
    membrane.scale = (1.5, 0.05, 1.2)
    for j in range(3):
        ja = math.radians(-30 + j * 30)
        bone = cone(f"wing_{side}_bone_{j}", r1=0.05, r2=0.02, depth=0.7, segs=6, loc=(math.cos(ja) * 0.4, 0.25, math.sin(ja) * 0.4), parent=wing_p, mat=MAT_DRAGON_BODY)
        bone.rotation_euler = (math.radians(90), 0, ja)

# tail : 4 more cone segments extending out from last body segment
tail_p = empty("dragon_tail", (body_segs[-1].location.x, body_segs[-1].location.y, body_segs[-1].location.z), parent=dragon_p)
tail_a = math.pi * 2.2 + 0.5
for i in range(5):
    t = i / 4
    a = tail_a + t * 1.2
    r = 1.4 + t * 1.5
    bx = math.cos(a) * r
    bz = math.sin(a) * r
    rr = 0.35 - t * 0.06
    tseg = sphere(f"dragon_tail_{i}", r=rr, segs=12, rings=8, loc=(bx, 0, bz), parent=tail_p, mat=MAT_DRAGON_BODY)
# tail tip spike
tip = cone("tail_tip", r1=0.10, r2=0.0, depth=0.30, segs=4, loc=(math.cos(tail_a + 1.2) * 2.9, 0, math.sin(tail_a + 1.2) * 2.9), parent=tail_p, mat=MAT_DRAGON_HORN)
tip.rotation_euler = (math.radians(90), tail_a + 1.2, 0)

# --- skull skeleton + sword plantée ---------------------------------------
# skull
skull_p = empty("skull", (-4.5, 0.55, 2.5))
skull_p.rotation_euler = (0, math.radians(30), math.radians(-15))
skull = sphere("skull_main", r=0.30, segs=14, rings=10, loc=(0, 0, 0), parent=skull_p, mat=MAT_SKULL)
skull.scale = (1.0, 1.0, 0.9)
# 2 eye sockets
for side, dx in [("L", 0.15), ("R", -0.15)]:
    socket = sphere(f"skull_socket_{side}", r=0.07, segs=8, rings=6, loc=(0.20, 0.05, dx), parent=skull_p, mat=MAT_CAVE_DARK)
# jaw
jaw = cube("skull_jaw", size=1.0, loc=(0.22, -0.20, 0), parent=skull_p, mat=MAT_SKULL)
jaw.scale = (0.20, 0.10, 0.30)

# sword stuck in ground
sword_p = empty("sword", (-5.5, 0, 3.0))
sword_p.rotation_euler = (math.radians(-20), 0, 0)
blade = cube("sword_blade", size=1.0, loc=(0, 0.8, 0), parent=sword_p, mat=MAT_SWORD_BLADE)
blade.scale = (0.08, 1.0, 0.04)
guard = cube("sword_guard", size=1.0, loc=(0, 1.30, 0), parent=sword_p, mat=MAT_SWORD_HILT)
guard.scale = (0.25, 0.06, 0.08)
hilt = cube("sword_hilt", size=1.0, loc=(0, 1.50, 0), parent=sword_p, mat=MAT_SWORD_HILT)
hilt.scale = (0.06, 0.25, 0.05)
pommel = sphere("sword_pommel", r=0.06, segs=10, rings=8, loc=(0, 1.78, 0), parent=sword_p, mat=MAT_GOLD)

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

# dragon breathing : whole rig scale Y subtle + head sway
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.04 * math.sin(tt * math.pi * 2.5)  # slow breath
    kf_scale(dragon_p, f, (1.0, s, 1.0))
    sway = math.radians(2) * math.sin(tt * math.pi * 1.5)
    kf_rot(head_p, f, (0, math.radians(15) + sway, math.radians(-10)))

# dragon eyes : red pulse (sleepy)
for eye in eyes:
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 3.0)
        kf_scale(eye, f, (s, s, s))

# torch flames pulse
for flame in torch_flames:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 8.0 + flame.location.x)
        kf_scale(flame, f, (0.8 * s, 1.5 * s, 0.8 * s))

# crystals scintillate (random phases)
for i, cr in enumerate(crystals):
    phase = i * 0.6
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 4.0 + phase)
        kf_scale(cr, f, (s, s, s))

# gems pulse (each different phase)
for gem, idx in gems:
    phase = idx * 0.4
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.25 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(gem, f, (s, 1.5 * s, s))

# coins shimmer (subtle rotation)
for i, coin in enumerate(coins):
    phase = i * 0.3
    base_rot = coin.rotation_euler.copy()
    for f in range(1, FRAMES + 1, 5):
        tt = (f - 1) / (FRAMES - 1)
        wobble = math.radians(5) * math.sin(tt * math.pi * 3.0 + phase)
        kf_rot(coin, f, (base_rot[0] + wobble, base_rot[1], base_rot[2]))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_dragonlair] wrote {OUT}")
