"""
proc_circus_tent.py — 123e procédural AuroraIA, Phase F++++.

Chapiteau de cirque : grand chapiteau pointu rayé rouge/blanc + 4
drapeaux flottants au sommet + entrée arquée + caravane + 2 roulottes
+ 8 lanternes émissives + 3 chevaux acrobates courant en cercle +
clown bondissant + roue ferris en arrière-plan + barrière + ciel
coucher étoilé + 20 confettis + projecteurs.

Animation :
- 3 chevaux : courent en cercle (orbites)
- drapeaux : flottent (sin waves)
- clown : bondit (sin Y)
- 8 lanternes : pulse couleurs cyclées
- 20 confettis : tombent en spirale
- 2 projecteurs spotlights : tournent

Sortie : output/3d/pbr_circus_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_circus_proc.glb"))

random.seed(0xC11C05)

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
MAT_SKY = make_mat("sky_dusk", (0.35, 0.18, 0.45), roughness=1.0,
                    emi=(0.30, 0.15, 0.40), emi_strength=0.6)
MAT_SKY_LOW = make_mat("sky_low", (0.85, 0.45, 0.30), roughness=1.0,
                         emi=(0.75, 0.35, 0.25), emi_strength=0.5)
MAT_STAR = make_mat("star", (1.0, 1.0, 0.95), roughness=0.0,
                      emi=(1.0, 1.0, 0.95), emi_strength=5.5)
MAT_GROUND = make_mat("ground", (0.18, 0.15, 0.10), roughness=0.95)
MAT_TENT_RED = make_mat("tent_red", (0.95, 0.10, 0.10), roughness=0.65,
                          emi=(0.40, 0.05, 0.05), emi_strength=0.3)
MAT_TENT_WHITE = make_mat("tent_white", (0.95, 0.95, 0.90), roughness=0.65,
                            emi=(0.40, 0.40, 0.38), emi_strength=0.3)
MAT_TENT_TOP = make_mat("tent_top", (1.0, 0.85, 0.20), metallic=0.7, roughness=0.3,
                          emi=(0.55, 0.45, 0.10), emi_strength=0.6)
MAT_TENT_POLE = make_mat("tent_pole", (0.40, 0.25, 0.10), roughness=0.7)
MAT_ENTRY = make_mat("entry", (0.40, 0.18, 0.05), roughness=0.75,
                       emi=(0.30, 0.10, 0.03), emi_strength=0.3)
MAT_FLAG_R = make_mat("flag_r", (1.0, 0.10, 0.20), roughness=0.5,
                        emi=(0.5, 0.05, 0.10), emi_strength=0.4)
MAT_FLAG_B = make_mat("flag_b", (0.20, 0.40, 1.0), roughness=0.5,
                        emi=(0.10, 0.20, 0.50), emi_strength=0.4)
MAT_FLAG_Y = make_mat("flag_y", (1.0, 0.95, 0.10), roughness=0.5,
                        emi=(0.50, 0.50, 0.05), emi_strength=0.4)
MAT_FLAG_G = make_mat("flag_g", (0.20, 1.0, 0.30), roughness=0.5,
                        emi=(0.10, 0.50, 0.15), emi_strength=0.4)
MAT_FENCE = make_mat("fence", (0.30, 0.20, 0.10), roughness=0.85)
MAT_CARAVAN = make_mat("caravan", (0.85, 0.35, 0.10), roughness=0.6,
                         emi=(0.35, 0.15, 0.05), emi_strength=0.3)
MAT_WAGON_GREEN = make_mat("wagon_green", (0.10, 0.55, 0.20), roughness=0.6,
                             emi=(0.05, 0.25, 0.08), emi_strength=0.3)
MAT_WAGON_BLUE = make_mat("wagon_blue", (0.10, 0.35, 0.85), roughness=0.6,
                            emi=(0.05, 0.15, 0.40), emi_strength=0.3)
MAT_WHEEL = make_mat("wheel", (0.10, 0.08, 0.06), roughness=0.7)
MAT_HORSE_WHITE = make_mat("horse_white", (0.95, 0.92, 0.88), roughness=0.7)
MAT_HORSE_BROWN = make_mat("horse_brown", (0.55, 0.30, 0.15), roughness=0.75)
MAT_HORSE_BLACK = make_mat("horse_black", (0.10, 0.08, 0.06), roughness=0.7)
MAT_HORSE_MANE = make_mat("horse_mane", (0.20, 0.15, 0.10), roughness=0.85)
MAT_CLOWN_RED = make_mat("clown_red", (1.0, 0.30, 0.30), roughness=0.5,
                           emi=(0.30, 0.05, 0.05), emi_strength=0.3)
MAT_CLOWN_BLUE = make_mat("clown_blue", (0.20, 0.40, 1.0), roughness=0.5,
                            emi=(0.10, 0.20, 0.40), emi_strength=0.3)
MAT_CLOWN_FACE = make_mat("clown_face", (0.95, 0.95, 0.90), roughness=0.6)
MAT_CLOWN_HAIR = make_mat("clown_hair", (1.0, 0.50, 0.10), roughness=0.7,
                            emi=(0.50, 0.20, 0.05), emi_strength=0.5)
MAT_CLOWN_EYE = make_mat("clown_eye", (0.05, 0.05, 0.05), roughness=0.3)
MAT_LANTERN_R = make_mat("lantern_r", (1.0, 0.30, 0.20), roughness=0.0, alpha=0.85,
                            emi=(1.0, 0.30, 0.20), emi_strength=7.0)
MAT_LANTERN_B = make_mat("lantern_b", (0.20, 0.50, 1.0), roughness=0.0, alpha=0.85,
                            emi=(0.20, 0.50, 1.0), emi_strength=7.0)
MAT_LANTERN_Y = make_mat("lantern_y", (1.0, 0.85, 0.30), roughness=0.0, alpha=0.85,
                            emi=(1.0, 0.85, 0.30), emi_strength=7.0)
MAT_LANTERN_G = make_mat("lantern_g", (0.20, 1.0, 0.40), roughness=0.0, alpha=0.85,
                            emi=(0.20, 1.0, 0.40), emi_strength=7.0)
MAT_LANTERN_ROPE = make_mat("lantern_rope", (0.30, 0.20, 0.10), roughness=0.9)
MAT_CONFETTI_R = make_mat("confetti_r", (1.0, 0.30, 0.30), roughness=0.5,
                            emi=(0.5, 0.05, 0.10), emi_strength=2.0)
MAT_CONFETTI_B = make_mat("confetti_b", (0.30, 0.40, 1.0), roughness=0.5,
                            emi=(0.10, 0.20, 0.5), emi_strength=2.0)
MAT_CONFETTI_Y = make_mat("confetti_y", (1.0, 0.85, 0.30), roughness=0.5,
                            emi=(0.50, 0.40, 0.10), emi_strength=2.0)
MAT_SPOT = make_mat("spotlight", (1.0, 0.95, 0.70), roughness=0.0, alpha=0.25,
                      emi=(1.0, 0.95, 0.70), emi_strength=5.0)
MAT_FERRIS = make_mat("ferris", (0.40, 0.35, 0.30), metallic=0.7, roughness=0.5)
MAT_FERRIS_CAR = make_mat("ferris_car", (0.85, 0.55, 0.15), roughness=0.6,
                            emi=(0.30, 0.20, 0.05), emi_strength=0.4)

# --- backdrop ---------------------------------------------------------------
sky_top = cube("sky_top", size=1.0, loc=(0, 16, 10), mat=MAT_SKY)
sky_top.scale = (32, 0.1, 8)

sky_bot = cube("sky_low", size=1.0, loc=(0, 16, 4), mat=MAT_SKY_LOW)
sky_bot.scale = (32, 0.1, 8)

# 50 stars in upper sky
for i in range(50):
    x = random.uniform(-14, 14)
    z = random.uniform(7, 12)
    y = random.uniform(14.0, 14.7)
    r = random.uniform(0.05, 0.10)
    sphere(f"star_{i}", r=r, segs=8, rings=6, loc=(x, y, z), mat=MAT_STAR)

# ground (sawdust)
ground = cube("ground", size=1.0, loc=(0, -0.05, 0), mat=MAT_GROUND)
ground.scale = (30, 0.1, 22)

# --- main circus tent : large striped cone --------------------------------
tent_p = empty("tent", (-1.0, 0, 0))

# build tent as 12 vertical strips alternating red/white
N_STRIPS = 16
TENT_R = 4.0
TENT_H = 5.0
for i in range(N_STRIPS):
    a0 = i * (math.pi * 2 / N_STRIPS)
    a1 = (i + 1) * (math.pi * 2 / N_STRIPS)
    mat = MAT_TENT_RED if i % 2 == 0 else MAT_TENT_WHITE
    # one segment as a stretched cube approximating the strip
    ax = math.cos((a0 + a1) / 2) * TENT_R * 0.7
    az = math.sin((a0 + a1) / 2) * TENT_R * 0.7
    strip = cone(f"tent_strip_{i}", r1=0.45, r2=0.04, depth=TENT_H, segs=4, loc=(ax, TENT_H / 2, az), parent=tent_p, mat=mat)
    strip.rotation_euler = (math.radians(90) - math.atan2(TENT_H, TENT_R), -((a0 + a1) / 2), math.radians(45))

# central pole at top
top_pole = cone("tent_top_pole", r1=0.10, r2=0.10, depth=1.5, segs=8, loc=(0, TENT_H + 0.5, 0), parent=tent_p, mat=MAT_TENT_POLE)
top_pole.rotation_euler = (math.radians(90), 0, 0)
# golden ball on top
top_ball = sphere("tent_top_ball", r=0.30, segs=14, rings=10, loc=(0, TENT_H + 1.5, 0), parent=tent_p, mat=MAT_TENT_TOP)

# 4 flags around the top ball
flags_top = []
flag_mats = [MAT_FLAG_R, MAT_FLAG_B, MAT_FLAG_Y, MAT_FLAG_G]
for i in range(4):
    a = i * (math.pi * 2 / 4)
    fp = empty(f"flag_top_{i}", (math.cos(a) * 0.3, TENT_H + 1.5, math.sin(a) * 0.3), parent=tent_p)
    pole = cone(f"flag_top_{i}_pole", r1=0.025, r2=0.02, depth=0.6, segs=4, loc=(0, 0.3, 0), parent=fp, mat=MAT_TENT_POLE)
    pole.rotation_euler = (math.radians(90), 0, 0)
    # 5 segments waving
    flag_segs = []
    for j in range(5):
        seg = cube(f"flag_top_{i}_{j}", size=1.0, loc=(0.04 + j * 0.07, 0.55, 0), parent=fp, mat=flag_mats[i])
        seg.scale = (0.07, 0.20, 0.02)
        flag_segs.append(seg)
    flags_top.append((flag_segs, i))

# tent base ring (slight foundation)
base_ring = cone("tent_base", r1=TENT_R * 1.1, r2=TENT_R * 1.1, depth=0.3, segs=16, loc=(0, 0.15, 0), parent=tent_p, mat=MAT_TENT_RED)
base_ring.rotation_euler = (math.radians(90), 0, 0)

# entrance arch (in front of tent)
entry = empty("entrance", (3.0, 0, 0), parent=tent_p)
# 2 vertical posts
for side, dz in [("L", 0.8), ("R", -0.8)]:
    post = cone(f"entry_post_{side}", r1=0.15, r2=0.13, depth=2.0, segs=8, loc=(0, 1.0, dz), parent=entry, mat=MAT_ENTRY)
    post.rotation_euler = (math.radians(90), 0, 0)
# arch (top horizontal beam)
arch = cube("entry_arch", size=1.0, loc=(0, 2.1, 0), parent=entry, mat=MAT_ENTRY)
arch.scale = (0.2, 0.3, 1.8)
# top decorative ball
deco = sphere("entry_deco", r=0.25, segs=14, rings=10, loc=(0, 2.5, 0), parent=entry, mat=MAT_TENT_TOP)

# --- caravan (large yellow/red wagon) --------------------------------------
caravan_p = empty("caravan", (-7.0, 0, 3.0))
caravan_p.rotation_euler = (0, math.radians(20), 0)
# body
body = cube("caravan_body", size=1.0, loc=(0, 1.0, 0), parent=caravan_p, mat=MAT_CARAVAN)
body.scale = (1.8, 0.9, 1.0)
# roof (curved hint via cone)
roof = cone("caravan_roof", r1=1.3, r2=0.7, depth=0.5, segs=4, loc=(0, 2.0, 0), parent=caravan_p, mat=MAT_TENT_RED)
roof.rotation_euler = (math.radians(90), 0, math.radians(45))
roof.scale = (1.3, 1.0, 1.0)
# 4 wheels
for i, (wx, wz) in enumerate([(0.7, 0.5), (-0.7, 0.5), (0.7, -0.5), (-0.7, -0.5)]):
    w = cone(f"caravan_wheel_{i}", r1=0.35, r2=0.35, depth=0.10, segs=14, loc=(wx, 0.35, wz), parent=caravan_p, mat=MAT_WHEEL)
    w.rotation_euler = (0, math.radians(90), 0)
    # spokes
    for k in range(6):
        ka = k * (math.pi / 6)
        spoke = cube(f"caravan_spoke_{i}_{k}", size=1.0, loc=(wx, 0.35, wz), parent=caravan_p, mat=MAT_CARAVAN)
        spoke.scale = (0.05, 0.30, 0.05)
        spoke.rotation_euler = (0, math.radians(90), ka)
# small door
door = cube("caravan_door", size=1.0, loc=(0.95, 0.8, 0), parent=caravan_p, mat=MAT_ENTRY)
door.scale = (0.04, 0.7, 0.4)
# window
win = cube("caravan_win", size=1.0, loc=(-0.85, 1.1, 0.5), parent=caravan_p, mat=MAT_LANTERN_Y)
win.scale = (0.04, 0.30, 0.30)
# chimney with smoke
chim_caravan_p = empty("caravan_chim_p", (0.5, 2.4, 0), parent=caravan_p)
chim = cube("caravan_chim", size=1.0, loc=(0, 0.2, 0), parent=chim_caravan_p, mat=MAT_WHEEL)
chim.scale = (0.10, 0.4, 0.10)

# --- 2 roulottes (smaller wagons) ------------------------------------------
roul_data = [
    (-7.5, -3.0, math.radians(-15), MAT_WAGON_GREEN),
    (5.5, -4.0, math.radians(35), MAT_WAGON_BLUE),
]
for i, (rx, rz, rot, mat) in enumerate(roul_data):
    rp = empty(f"roul_{i}", (rx, 0, rz))
    rp.rotation_euler = (0, rot, 0)
    body = cube(f"roul_{i}_body", size=1.0, loc=(0, 0.7, 0), parent=rp, mat=mat)
    body.scale = (1.2, 0.6, 0.7)
    # roof (curved)
    roof = cone(f"roul_{i}_roof", r1=0.9, r2=0.4, depth=0.3, segs=4, loc=(0, 1.30, 0), parent=rp, mat=MAT_TENT_RED)
    roof.rotation_euler = (math.radians(90), 0, math.radians(45))
    # wheels
    for j, (wx, wz) in enumerate([(0.5, 0.35), (-0.5, 0.35), (0.5, -0.35), (-0.5, -0.35)]):
        w = cone(f"roul_{i}_w_{j}", r1=0.25, r2=0.25, depth=0.08, segs=12, loc=(wx, 0.25, wz), parent=rp, mat=MAT_WHEEL)
        w.rotation_euler = (0, math.radians(90), 0)
    # door
    door = cube(f"roul_{i}_door", size=1.0, loc=(0.65, 0.6, 0), parent=rp, mat=MAT_ENTRY)
    door.scale = (0.03, 0.5, 0.25)
    # window glowing
    win = cube(f"roul_{i}_win", size=1.0, loc=(-0.62, 0.85, 0.30), parent=rp, mat=MAT_LANTERN_Y)
    win.scale = (0.03, 0.20, 0.20)

# --- 8 lanternes émissives (strung around) --------------------------------
lantern_lights = []
lantern_mats = [MAT_LANTERN_R, MAT_LANTERN_B, MAT_LANTERN_Y, MAT_LANTERN_G,
                MAT_LANTERN_R, MAT_LANTERN_B, MAT_LANTERN_Y, MAT_LANTERN_G]
# place along the perimeter and entrance
for i in range(8):
    a = i * (math.pi * 2 / 8)
    lx = math.cos(a) * 6.5
    lz = math.sin(a) * 6.5
    ly = 3.0
    lp = empty(f"lantern_{i}", (lx, ly, lz))
    light = sphere(f"lantern_{i}_light", r=0.20, segs=12, rings=8, loc=(0, 0, 0), parent=lp, mat=lantern_mats[i])
    # cap above
    cap = cone(f"lantern_{i}_cap", r1=0.25, r2=0.0, depth=0.15, segs=6, loc=(0, 0.20, 0), parent=lp, mat=MAT_LANTERN_ROPE)
    cap.rotation_euler = (math.radians(90), 0, 0)
    # rope
    rope = cone(f"lantern_{i}_rope", r1=0.02, r2=0.02, depth=0.7, segs=4, loc=(0, 0.55, 0), parent=lp, mat=MAT_LANTERN_ROPE)
    rope.rotation_euler = (math.radians(90), 0, 0)
    lantern_lights.append((light, i))

# --- 3 chevaux courant autour de la tente ----------------------------------
def make_horse(name, mat_body=MAT_HORSE_BROWN, mat_mane=MAT_HORSE_MANE):
    p = empty(name, (0, 0, 0))
    # body (sphere stretched)
    body = sphere(f"{name}_body", r=0.30, segs=14, rings=10, loc=(0, 0.7, 0), parent=p, mat=mat_body)
    body.scale = (1.7, 0.8, 0.7)
    # head + neck
    neck = cone(f"{name}_neck", r1=0.15, r2=0.12, depth=0.5, segs=8, loc=(0.45, 1.05, 0), parent=p, mat=mat_body)
    neck.rotation_euler = (0, 0, math.radians(-50))
    head = sphere(f"{name}_head", r=0.18, segs=12, rings=10, loc=(0.75, 1.35, 0), parent=p, mat=mat_body)
    head.scale = (1.4, 0.9, 0.8)
    # 2 ears
    for side, dz in [("L", 0.10), ("R", -0.10)]:
        ear = cone(f"{name}_ear_{side}", r1=0.04, r2=0.0, depth=0.10, segs=6, loc=(0.72, 1.50, dz), parent=p, mat=mat_body)
        ear.rotation_euler = (math.radians(-15), 0, 0)
    # mane (along neck)
    for k in range(4):
        mp = sphere(f"{name}_mane_{k}", r=0.05, segs=8, rings=6, loc=(0.45 + k * 0.06, 1.20 + k * 0.05, 0), parent=p, mat=mat_mane)
    # 4 legs
    for i, (lx, lz) in enumerate([(0.45, 0.30), (0.45, -0.30), (-0.45, 0.30), (-0.45, -0.30)]):
        leg = cube(f"{name}_leg_{i}", size=1.0, loc=(lx, 0.35, lz), parent=p, mat=mat_body)
        leg.scale = (0.12, 0.7, 0.12)
    # tail (curled)
    tail = cone(f"{name}_tail", r1=0.08, r2=0.02, depth=0.4, segs=6, loc=(-0.55, 0.75, 0), parent=p, mat=mat_mane)
    tail.rotation_euler = (0, 0, math.radians(110))
    return p

horse_data = [
    (0, MAT_HORSE_WHITE, MAT_HORSE_MANE),
    (math.pi * 2 / 3, MAT_HORSE_BROWN, MAT_HORSE_MANE),
    (math.pi * 4 / 3, MAT_HORSE_BLACK, MAT_HORSE_MANE),
]
horses = []
for i, (a0, body_mat, mane_mat) in enumerate(horse_data):
    h = make_horse(f"horse_{i}", body_mat, mane_mat)
    horses.append((h, a0))

# --- clown bondissant -------------------------------------------------------
clown_p = empty("clown", (2.5, 0.5, 4.0))
# body bottom (red pants)
pants = cube("clown_pants", size=1.0, loc=(0, 0, 0), parent=clown_p, mat=MAT_CLOWN_RED)
pants.scale = (0.32, 0.45, 0.32)
# shirt (blue)
shirt = cube("clown_shirt", size=1.0, loc=(0, 0.50, 0), parent=clown_p, mat=MAT_CLOWN_BLUE)
shirt.scale = (0.40, 0.40, 0.35)
# head
head = sphere("clown_head", r=0.22, segs=14, rings=10, loc=(0, 0.95, 0), parent=clown_p, mat=MAT_CLOWN_FACE)
# nose red
nose = sphere("clown_nose", r=0.06, segs=10, rings=8, loc=(0, 0.92, 0.20), parent=clown_p, mat=MAT_CLOWN_RED)
# 2 eyes
for side, dx in [("L", -0.08), ("R", 0.08)]:
    eye = sphere(f"clown_eye_{side}", r=0.03, segs=8, rings=6, loc=(dx, 1.0, 0.18), parent=clown_p, mat=MAT_CLOWN_EYE)
# 2 mouth (smiling, just orange spheres for cheeks + red line approximation)
for side, dx in [("L", -0.10), ("R", 0.10)]:
    cheek = sphere(f"clown_cheek_{side}", r=0.04, segs=6, rings=4, loc=(dx, 0.88, 0.18), parent=clown_p, mat=MAT_CLOWN_RED)
# 2 hair tufts (orange)
for side, dx in [("L", -0.18), ("R", 0.18)]:
    hair = sphere(f"clown_hair_{side}", r=0.10, segs=10, rings=8, loc=(dx, 1.05, 0), parent=clown_p, mat=MAT_CLOWN_HAIR)
# tiny hat (cone)
hat = cone("clown_hat", r1=0.10, r2=0.02, depth=0.20, segs=8, loc=(0, 1.25, 0), parent=clown_p, mat=MAT_CLOWN_BLUE)
hat.rotation_euler = (math.radians(90), 0, 0)
# 2 arms
for side, dx in [("L", -0.30), ("R", 0.30)]:
    arm = cube(f"clown_arm_{side}", size=1.0, loc=(dx, 0.45, 0), parent=clown_p, mat=MAT_CLOWN_BLUE)
    arm.scale = (0.10, 0.30, 0.10)
# 2 shoes (big)
for side, dx in [("L", -0.15), ("R", 0.15)]:
    shoe = cube(f"clown_shoe_{side}", size=1.0, loc=(dx, -0.30, 0.10), parent=clown_p, mat=MAT_CLOWN_RED)
    shoe.scale = (0.18, 0.10, 0.30)

# --- ferris wheel en arrière-plan -----------------------------------------
ferris_p = empty("ferris", (10.0, 0, 5.5))
# main support pole
pole = cone("ferris_pole", r1=0.20, r2=0.20, depth=5.0, segs=12, loc=(0, 2.5, 0), parent=ferris_p, mat=MAT_FERRIS)
pole.rotation_euler = (math.radians(90), 0, 0)
# wheel (large ring) - approximated with 16 spokes + cars
wheel_p = empty("ferris_wheel", (0, 5.0, 0), parent=ferris_p)
N_SPOKES = 12
for i in range(N_SPOKES):
    a = i * (math.pi * 2 / N_SPOKES)
    spoke = cube(f"ferris_spoke_{i}", size=1.0, loc=(math.cos(a) * 1.5, math.sin(a) * 1.5, 0), parent=wheel_p, mat=MAT_FERRIS)
    spoke.scale = (0.04, 3.0, 0.04)
    spoke.rotation_euler = (0, 0, a)
# 6 cars on outer rim
for k in range(6):
    a = k * (math.pi * 2 / 6)
    car_x = math.cos(a) * 3.0
    car_y = math.sin(a) * 3.0
    car = cube(f"ferris_car_{k}", size=1.0, loc=(car_x, car_y, 0), parent=wheel_p, mat=MAT_FERRIS_CAR)
    car.scale = (0.35, 0.35, 0.40)

# --- barrière (fence around perimeter) -------------------------------------
N_FENCE = 24
for i in range(N_FENCE):
    a = i * (math.pi * 2 / N_FENCE)
    fx = math.cos(a) * 9.0
    fz = math.sin(a) * 9.0
    # skip in front of entrance
    if abs(a - 0) < 0.4 or abs(a - math.pi * 2) < 0.4:
        continue
    fp = cone(f"fence_post_{i}", r1=0.06, r2=0.04, depth=0.7, segs=4, loc=(fx, 0.35, fz), parent=None, mat=MAT_FENCE)
    fp.rotation_euler = (math.radians(90), 0, math.radians(45))

# --- 20 confettis tombant --------------------------------------------------
confetti_mats = [MAT_CONFETTI_R, MAT_CONFETTI_B, MAT_CONFETTI_Y]
confettis = []
for i in range(20):
    cx = random.uniform(-6, 6)
    cz = random.uniform(-6, 6)
    cy = random.uniform(2.5, 7.5)
    mat = random.choice(confetti_mats)
    c = cube(f"confetti_{i}", size=1.0, loc=(cx, cy, cz), mat=mat)
    c.scale = (0.10, 0.02, 0.07)
    c.rotation_euler = (random.uniform(0, math.pi), random.uniform(0, math.pi), random.uniform(0, math.pi))
    confettis.append((c, cx, cz, cy, random.uniform(0, 1), random.uniform(0.5, 1.0)))

# --- 2 projecteurs spotlights ---------------------------------------------
spotlights = []
for i, (sx, sz) in enumerate([(-9, -4), (9, -4)]):
    sp_p = empty(f"spot_p_{i}", (sx, 0.5, sz))
    base = cone(f"spot_{i}_base", r1=0.20, r2=0.15, depth=0.3, segs=8, loc=(0, 0, 0), parent=sp_p, mat=MAT_FERRIS)
    base.rotation_euler = (math.radians(90), 0, 0)
    # beam (large stretched cone)
    beam_p = empty(f"spot_{i}_beam_p", (0, 0.3, 0), parent=sp_p)
    beam = cone(f"spot_{i}_beam", r1=0.05, r2=2.0, depth=10.0, segs=12, loc=(0, 5.0, 0), parent=beam_p, mat=MAT_SPOT)
    beam.rotation_euler = (math.radians(90), 0, 0)
    spotlights.append(beam_p)

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

# horses run around the tent
for h, a0 in horses:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 4.0
        hx = math.cos(angle) * 5.5
        hz = math.sin(angle) * 5.5
        # gallop bob
        hy = 0.1 * math.sin(tt * math.pi * 30.0 + a0)
        kf_loc(h, f, (hx, hy, hz))
        kf_rot(h, f, (0, -angle + math.pi / 2, math.radians(5) * math.sin(tt * math.pi * 30.0)))

# clown bounces
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    angle = tt * math.pi * 2
    cy = 0.5 + 1.0 * abs(math.sin(tt * math.pi * 6.0))
    cx = 2.5 + math.cos(angle) * 1.5
    cz = 4.0 + math.sin(angle) * 1.0
    kf_loc(clown_p, f, (cx, cy, cz))
    kf_rot(clown_p, f, (0, -angle, math.radians(8) * math.sin(tt * math.pi * 8.0)))

# flags wave (top)
for flag_segs, i in flags_top:
    for k, seg in enumerate(flag_segs):
        for f in range(1, FRAMES + 1, 2):
            tt = (f - 1) / (FRAMES - 1)
            wave = math.sin(k * 0.5 + tt * math.pi * 8.0 + i * 0.6)
            kx = 0.04 + k * 0.07
            kz = wave * 0.10
            kf_loc(seg, f, (kx, 0.55, kz))
            kf_rot(seg, f, (0, 0, wave * 0.15))

# lanterns pulse
for light, idx in lantern_lights:
    phase = idx * 0.4
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.25 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(light, f, (s, s, s))

# confettis fall in spiral
for c, cx, cz, cy_init, ph, spd in confettis:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        local = (tt + ph) % 1.0
        angle = local * math.pi * 4.0 * spd
        r = 0.4
        x = cx + math.cos(angle) * r
        z = cz + math.sin(angle) * r
        y = cy_init - local * 6.0
        if y < 0.1:
            y = 0.1
        kf_loc(c, f, (x, y, z))
        kf_rot(c, f, (local * math.pi * 8 * spd, local * math.pi * 6 * spd, local * math.pi * 5 * spd))

# ferris wheel rotate
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(wheel_p, f, (0, 0, tt * math.pi * 2.0))

# spotlights rotate
for i, beam_p in enumerate(spotlights):
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        angle = math.radians(30) * math.sin(tt * math.pi * 2.5 + i * math.pi)
        kf_rot(beam_p, f, (math.radians(20), angle, 0))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_circus] wrote {OUT}")
