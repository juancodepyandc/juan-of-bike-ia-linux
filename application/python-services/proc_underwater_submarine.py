"""
proc_underwater_submarine.py — 127e procédural AuroraIA, Phase F++++.

Sous-marin d'exploration sous-marine abysses : sous-marin jaune
(coque + tour observation hublots + hélice arrière + 2 ailerons +
périscope + 2 lights frontaux) + grotte sous-marine arche + 6 méduses
bioluminescentes + 5 poissons abyssaux émissifs + 2 anémones + algues
filaments + 25 bulles montantes + lit océan sablonneux + 4 rochers
+ crâne baleine.

Animation :
- sous-marin avance lentement (translate X)
- hélice arrière tourne (rotate X rapide)
- 2 lights front pulse
- 6 méduses pulse + drift
- 5 poissons abyssaux : glow cycle phases offset
- 4 algues filaments : sway
- 25 bulles montent depuis sub + reset

Sortie : output/3d/pbr_submarine_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_submarine_proc.glb"))

random.seed(0xABBEE5)

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
MAT_WATER_DEEP = make_mat("water_deep", (0.02, 0.05, 0.15), roughness=1.0,
                            emi=(0.03, 0.08, 0.18), emi_strength=0.4)
MAT_WATER_LIGHT = make_mat("water_light", (0.05, 0.20, 0.35), roughness=0.5, alpha=0.8,
                             emi=(0.10, 0.25, 0.40), emi_strength=0.6)
MAT_SAND = make_mat("sand", (0.45, 0.40, 0.30), roughness=0.95)
MAT_ROCK = make_mat("rock", (0.20, 0.18, 0.15), roughness=0.95)
MAT_CAVE = make_mat("cave", (0.08, 0.10, 0.12), roughness=0.95)
MAT_SUB_YELLOW = make_mat("sub_yellow", (1.0, 0.85, 0.20), metallic=0.7, roughness=0.3,
                            emi=(0.4, 0.32, 0.05), emi_strength=0.4)
MAT_SUB_DARK = make_mat("sub_dark", (0.20, 0.18, 0.12), metallic=0.5, roughness=0.5)
MAT_SUB_WINDOW = make_mat("sub_window", (1.0, 0.95, 0.55), roughness=0.0, alpha=0.85,
                            emi=(1.0, 0.95, 0.55), emi_strength=6.0)
MAT_SUB_LIGHT = make_mat("sub_light", (1.0, 1.0, 0.85), roughness=0.0,
                           emi=(1.0, 1.0, 0.85), emi_strength=10.0)
MAT_SUB_BEAM = make_mat("sub_beam", (1.0, 1.0, 0.85), roughness=0.0, alpha=0.18,
                          emi=(1.0, 1.0, 0.85), emi_strength=3.5)
MAT_PROPELLER = make_mat("propeller", (0.45, 0.45, 0.50), metallic=0.85, roughness=0.3)
MAT_JELLY_PURPLE = make_mat(
    "jelly_purple", (0.80, 0.30, 1.0), roughness=0.0, alpha=0.55,
    emi=(0.75, 0.20, 1.0), emi_strength=4.0,
)
MAT_JELLY_PINK = make_mat(
    "jelly_pink", (1.0, 0.45, 0.80), roughness=0.0, alpha=0.55,
    emi=(1.0, 0.35, 0.75), emi_strength=4.0,
)
MAT_JELLY_CYAN = make_mat(
    "jelly_cyan", (0.30, 0.95, 1.0), roughness=0.0, alpha=0.55,
    emi=(0.25, 0.95, 1.0), emi_strength=4.0,
)
MAT_JELLY_TENT = make_mat(
    "jelly_tent", (1.0, 0.75, 1.0), roughness=0.0, alpha=0.45,
    emi=(0.85, 0.55, 1.0), emi_strength=3.0,
)
MAT_FISH_DEEP_R = make_mat("fish_deep_r", (0.85, 0.10, 0.15), roughness=0.4,
                             emi=(0.85, 0.10, 0.15), emi_strength=3.5)
MAT_FISH_DEEP_B = make_mat("fish_deep_b", (0.20, 0.50, 1.0), roughness=0.4,
                             emi=(0.20, 0.50, 1.0), emi_strength=3.5)
MAT_FISH_DEEP_G = make_mat("fish_deep_g", (0.40, 1.0, 0.30), roughness=0.4,
                             emi=(0.30, 1.0, 0.25), emi_strength=3.5)
MAT_FISH_EYE = make_mat("fish_eye", (1.0, 1.0, 0.85), roughness=0.0,
                          emi=(1.0, 1.0, 0.85), emi_strength=5.0)
MAT_ANEMONE = make_mat("anemone", (1.0, 0.50, 0.70), roughness=0.6,
                         emi=(0.5, 0.20, 0.35), emi_strength=0.5)
MAT_ALGAE = make_mat("algae", (0.10, 0.55, 0.20), roughness=0.85,
                       emi=(0.05, 0.25, 0.10), emi_strength=0.3)
MAT_BUBBLE = make_mat(
    "bubble", (0.85, 0.95, 1.0), roughness=0.0, alpha=0.5,
    emi=(0.80, 0.92, 1.0), emi_strength=1.8,
)
MAT_SKULL = make_mat("skull", (0.85, 0.82, 0.75), roughness=0.7,
                       emi=(0.30, 0.28, 0.25), emi_strength=0.2)

# --- backdrop : deep water -------------------------------------------------
deep = cube("deep_back", size=1.0, loc=(0, 16, 4), mat=MAT_WATER_DEEP)
deep.scale = (32, 0.1, 14)

# upper water (slightly lighter)
upper = cube("water_upper", size=1.0, loc=(0, 14, 9), mat=MAT_WATER_LIGHT)
upper.scale = (32, 0.1, 6)

# sandy ocean floor
sand = cube("sand_floor", size=1.0, loc=(0, -0.05, 0), mat=MAT_SAND)
sand.scale = (30, 0.1, 22)

# 4 rochers
for i, (rx, rz, h) in enumerate([(-7, 4, 1.0), (8, -3, 1.5), (-9, -5, 0.8), (6, 5, 1.2)]):
    r = sphere(f"rock_{i}", r=h, segs=14, rings=10, loc=(rx, h * 0.6, rz), mat=MAT_ROCK)
    r.scale = (1.4, 0.8, 1.1)

# --- cave arch (large rocky arch over the scene) --------------------------
cave_p = empty("cave_p", (8, 0, -3))
# 2 vertical pillars
for side, dz in [("L", -1.5), ("R", 1.5)]:
    pillar = cone(f"cave_pillar_{side}", r1=1.0, r2=0.7, depth=5.0, segs=10, loc=(0, 2.5, dz), parent=cave_p, mat=MAT_CAVE)
    pillar.rotation_euler = (math.radians(90), 0, 0)
# arch (top connecting piece)
arch = sphere("cave_arch", r=2.0, segs=20, rings=14, loc=(0, 5.5, 0), parent=cave_p, mat=MAT_CAVE)
arch.scale = (1.4, 0.5, 1.8)

# --- submarine -------------------------------------------------------------
sub_p = empty("submarine", (-5.0, 4.5, 0))
# main hull (long ellipsoid)
hull = sphere("sub_hull", r=1.2, segs=24, rings=14, loc=(0, 0, 0), parent=sub_p, mat=MAT_SUB_YELLOW)
hull.scale = (3.5, 0.8, 0.8)
# nose cap (darker)
nose = sphere("sub_nose", r=0.95, segs=20, rings=12, loc=(2.8, 0, 0), parent=sub_p, mat=MAT_SUB_DARK)
nose.scale = (0.6, 0.8, 0.8)
# tail cone
tail = cone("sub_tail", r1=0.5, r2=0.0, depth=0.8, segs=12, loc=(-3.5, 0, 0), parent=sub_p, mat=MAT_SUB_DARK)
tail.rotation_euler = (0, math.radians(-90), 0)

# conning tower (observation tower)
tower = cube("sub_tower", size=1.0, loc=(0, 0.95, 0), parent=sub_p, mat=MAT_SUB_YELLOW)
tower.scale = (1.5, 0.7, 0.7)
# top of tower (dome)
tower_top = sphere("sub_tower_top", r=0.50, segs=16, rings=10, loc=(0, 1.35, 0), parent=sub_p, mat=MAT_SUB_YELLOW)
tower_top.scale = (1.4, 0.6, 1.0)
# 4 hublots on tower (round windows)
for i, dz in enumerate([-0.40, -0.13, 0.13, 0.40]):
    w = sphere(f"sub_hublot_{i}", r=0.10, segs=12, rings=8, loc=(0.30, 0.95, dz), parent=sub_p, mat=MAT_SUB_WINDOW)
    w.scale = (1.0, 1.0, 0.3)
# 4 hublots on the hull
for i, dz in enumerate([-1.0, -0.4, 0.4, 1.0]):
    w = sphere(f"sub_hublot_h_{i}", r=0.12, segs=12, rings=8, loc=(dz, 0.30, 0.78), parent=sub_p, mat=MAT_SUB_WINDOW)
    w.scale = (1.0, 1.0, 0.3)

# periscope (cylinder)
peri = cone("sub_peri", r1=0.06, r2=0.05, depth=0.7, segs=8, loc=(0, 1.75, 0), parent=sub_p, mat=MAT_SUB_DARK)
peri.rotation_euler = (math.radians(90), 0, 0)
# periscope head
peri_head = cube("sub_peri_head", size=1.0, loc=(0.10, 2.05, 0), parent=sub_p, mat=MAT_SUB_DARK)
peri_head.scale = (0.18, 0.10, 0.10)

# 2 ailerons (horizontal stabilizers)
for side, dz in [("L", 1.05), ("R", -1.05)]:
    ail = cube(f"sub_ail_{side}", size=1.0, loc=(-2.5, 0, dz), parent=sub_p, mat=MAT_SUB_YELLOW)
    ail.scale = (0.5, 0.04, 0.4)

# 1 vertical fin
fin = cube("sub_fin", size=1.0, loc=(-2.5, 0.5, 0), parent=sub_p, mat=MAT_SUB_YELLOW)
fin.scale = (0.4, 0.5, 0.04)

# 2 front lights
front_lights = []
front_beams = []
for side, dz in [("L", 0.35), ("R", -0.35)]:
    fl = sphere(f"sub_fl_{side}", r=0.15, segs=12, rings=8, loc=(3.20, 0.15, dz), parent=sub_p, mat=MAT_SUB_LIGHT)
    front_lights.append(fl)
    # beam emerging
    beam = cone(f"sub_beam_{side}", r1=0.08, r2=0.8, depth=4.0, segs=12, loc=(5.0, 0.15, dz), parent=sub_p, mat=MAT_SUB_BEAM)
    beam.rotation_euler = (0, math.radians(90), 0)
    front_beams.append(beam)

# propeller (rotating at back)
prop_p = empty("sub_prop_p", (-3.8, 0, 0), parent=sub_p)
for blade_i in range(4):
    ba = blade_i * (math.pi * 2 / 4)
    bl = cube(f"sub_blade_{blade_i}", size=1.0, loc=(0, math.cos(ba) * 0.45, math.sin(ba) * 0.45), parent=prop_p, mat=MAT_PROPELLER)
    bl.scale = (0.05, 0.06, 0.45)
    bl.rotation_euler = (ba, 0, 0)
# prop hub
prop_hub = sphere("sub_prop_hub", r=0.18, segs=12, rings=8, loc=(0, 0, 0), parent=prop_p, mat=MAT_PROPELLER)

# 25 bubbles from sub
sub_bubbles = []
for i in range(25):
    bx = -3.5 + random.uniform(-0.3, 0.3)
    by = 0.3 + random.uniform(0, 0.3)
    bz = 0 + random.uniform(-0.3, 0.3)
    b = sphere(f"sub_bub_{i}", r=random.uniform(0.04, 0.08), segs=8, rings=6, loc=(bx, by, bz), parent=sub_p, mat=MAT_BUBBLE)
    sub_bubbles.append((b, bx, bz, random.uniform(0, 1)))

# --- 6 méduses bioluminescentes -------------------------------------------
jellies = []
jelly_colors = [MAT_JELLY_PURPLE, MAT_JELLY_PINK, MAT_JELLY_CYAN]
for i in range(6):
    jx = random.uniform(-10, 10)
    jy = random.uniform(2, 8)
    jz = random.uniform(-5, 5)
    jp = empty(f"jelly_{i}", (jx, jy, jz))
    bell = sphere(f"jelly_{i}_bell", r=0.45, segs=18, rings=12, loc=(0, 0, 0), parent=jp, mat=jelly_colors[i % 3])
    bell.scale = (1.0, 0.55, 1.0)
    # 6 tentacles
    for j in range(6):
        a = j * (math.pi * 2 / 6)
        tx = math.cos(a) * 0.30
        tz = math.sin(a) * 0.30
        for k in range(4):
            ty = -0.2 - k * 0.25
            rr = 0.04 - k * 0.005
            sphere(f"jelly_{i}_t{j}_{k}", r=rr, segs=8, rings=6, loc=(tx, ty, tz), parent=jp, mat=MAT_JELLY_TENT)
    jellies.append((jp, jx, jz, jy, random.uniform(0, math.pi * 2)))

# --- 5 poissons abyssaux ---------------------------------------------------
fishes = []
fish_mats = [MAT_FISH_DEEP_R, MAT_FISH_DEEP_B, MAT_FISH_DEEP_G]
for i in range(5):
    fx = random.uniform(-9, 9)
    fy = random.uniform(1, 8)
    fz = random.uniform(-6, 6)
    fp = empty(f"fish_{i}", (fx, fy, fz))
    mat = fish_mats[i % 3]
    body = sphere(f"fish_{i}_body", r=0.25, segs=14, rings=10, loc=(0, 0, 0), parent=fp, mat=mat)
    body.scale = (1.8, 0.6, 0.8)
    tail = cone(f"fish_{i}_tail", r1=0.15, r2=0.02, depth=0.20, segs=4, loc=(-0.30, 0, 0), parent=fp, mat=mat)
    tail.rotation_euler = (0, math.radians(-90), 0)
    tail.scale = (1.0, 1.5, 0.3)
    # bioluminescent lure (antenna)
    lure_p = cone(f"fish_{i}_lure_p", r1=0.02, r2=0.02, depth=0.3, segs=6, loc=(0.30, 0.20, 0), parent=fp, mat=mat)
    lure_p.rotation_euler = (math.radians(20), 0, 0)
    # lure light at end
    lure_light = sphere(f"fish_{i}_lure", r=0.08, segs=10, rings=8, loc=(0.35, 0.45, 0), parent=fp, mat=MAT_FISH_EYE)
    # 2 eyes (big, bioluminescent)
    for side, dz in [("L", 0.08), ("R", -0.08)]:
        eye = sphere(f"fish_{i}_eye_{side}", r=0.05, segs=8, rings=6, loc=(0.20, 0.05, dz), parent=fp, mat=MAT_FISH_EYE)
    fishes.append((fp, fx, fz, fy, random.uniform(0, math.pi * 2), random.uniform(0.5, 1.0)))

# --- 2 anémones ------------------------------------------------------------
for i, (ax, az) in enumerate([(-4, -2), (3, -3)]):
    ap = empty(f"anemone_{i}", (ax, 0.1, az))
    # base
    base = sphere(f"anemone_{i}_base", r=0.4, segs=14, rings=10, loc=(0, 0, 0), parent=ap, mat=MAT_ANEMONE)
    base.scale = (1.0, 0.5, 1.0)
    # 8 tentacles radiating
    for j in range(8):
        a = j * (math.pi * 2 / 8) + random.uniform(-0.2, 0.2)
        h = random.uniform(0.6, 1.0)
        t = cone(f"anemone_{i}_t_{j}", r1=0.05, r2=0.02, depth=h, segs=4, loc=(math.cos(a) * 0.25, h / 2, math.sin(a) * 0.25), parent=ap, mat=MAT_ANEMONE)
        t.rotation_euler = (math.radians(-20), 0, a)

# --- 6 algues filaments --------------------------------------------------
algae = []
for i in range(6):
    ax = random.uniform(-10, 10)
    az = random.uniform(-7, 7)
    ap = empty(f"algae_{i}", (ax, 0.05, az))
    # 5 segments stacked
    for j in range(5):
        h = 0.3 + j * 0.5
        seg = cone(f"algae_{i}_{j}", r1=0.08 - j * 0.012, r2=0.07 - j * 0.012, depth=0.5, segs=6, loc=(0, h, 0), parent=ap, mat=MAT_ALGAE)
        seg.rotation_euler = (math.radians(90), 0, 0)
    algae.append(ap)

# --- whale skull -----------------------------------------------------------
skull_p = empty("whale_skull", (-3, 0.2, 5))
skull_p.rotation_euler = (0, math.radians(35), math.radians(15))
sk_body = sphere("skull_main", r=0.7, segs=18, rings=12, loc=(0, 0, 0), parent=skull_p, mat=MAT_SKULL)
sk_body.scale = (1.6, 0.7, 1.0)
# 2 eye sockets
for side, dz in [("L", 0.30), ("R", -0.30)]:
    socket = sphere(f"skull_socket_{side}", r=0.12, segs=8, rings=6, loc=(0.40, 0.10, dz), parent=skull_p, mat=MAT_CAVE)
# jaw (lower)
jaw = cube("skull_jaw", size=1.0, loc=(0.30, -0.20, 0), parent=skull_p, mat=MAT_SKULL)
jaw.scale = (0.50, 0.15, 0.50)

# --- 20 distant bubbles (background ambiance) -----------------------------
ambient_bubbles = []
for i in range(20):
    bx = random.uniform(-12, 12)
    bz = random.uniform(-8, 8)
    by = random.uniform(0.5, 9.0)
    b = sphere(f"amb_bub_{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6, loc=(bx, by, bz), mat=MAT_BUBBLE)
    ambient_bubbles.append((b, bx, bz, random.uniform(0, 1)))

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

# submarine moves forward + slight bob
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    sx = -5.0 + tt * 4.0
    sy = 4.5 + 0.3 * math.sin(tt * math.pi * 2.0)
    kf_loc(sub_p, f, (sx, sy, 0))
    pitch = math.radians(3) * math.sin(tt * math.pi * 2.0)
    kf_rot(sub_p, f, (pitch, 0, 0))

# propeller rotates fast
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(prop_p, f, (tt * math.pi * 30, 0, 0))

# front lights pulse
for fl in front_lights:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 6.0)
        kf_scale(fl, f, (s, s, s))

# 6 jellies pulse + drift
for jp, jx, jz, jy, ph in jellies:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        dx = jx + 0.5 * math.sin(tt * math.pi * 1.2 + ph)
        dy = jy + 0.6 * math.sin(tt * math.pi * 2.0 + ph)
        dz = jz + 0.3 * math.cos(tt * math.pi * 1.5 + ph)
        kf_loc(jp, f, (dx, dy, dz))
        s = 1.0 + 0.25 * math.sin(tt * math.pi * 6.0 + ph)
        kf_scale(jp, f, (s, 1.0 / s if s > 0 else 1.0, s))

# 5 fishes swim circles
for fp, fx, fz, fy, a0, spd in fishes:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 2.0 * spd
        x = fx + math.cos(angle) * 1.5
        z = fz + math.sin(angle) * 1.5
        y = fy + 0.4 * math.sin(tt * math.pi * 4.0 + a0)
        kf_loc(fp, f, (x, y, z))
        kf_rot(fp, f, (0, -angle + math.pi / 2, 0))
        # pulse glow
        s_lure = 1.0 + 0.30 * math.sin(tt * math.pi * 5.0 + a0)
        # find lure light
        lure_light = bpy.data.objects.get(f"fish_{fishes.index((fp, fx, fz, fy, a0, spd))}_lure")
        if lure_light:
            kf_scale(lure_light, f, (s_lure, s_lure, s_lure))

# 6 algae sway
for i, ap in enumerate(algae):
    phase = i * 0.5
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bend = math.radians(15) * math.sin(tt * math.pi * 3.0 + phase)
        kf_rot(ap, f, (bend, 0, bend * 0.5))

# sub bubbles rise from sub
for b, bx, bz, ph in sub_bubbles:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        local = (tt + ph) % 1.0
        # follow sub's X position
        sub_x = -5.0 + tt * 4.0
        by = 0.3 + local * 8.0
        kf_loc(b, f, (bx + sub_x + 5.0 - sub_x, by, bz))  # simplify: keep relative
        # actually keep relative bx (already relative to sub_p), simpler
        kf_loc(b, f, (bx, by, bz))

# ambient bubbles rise (background)
for b, bx, bz, ph in ambient_bubbles:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        local = (tt + ph) % 1.0
        by = 0.5 + local * 9.0
        kf_loc(b, f, (bx + 0.15 * math.sin(local * math.pi * 6.0), by, bz))
        s = 0.6 + 0.5 * local
        kf_scale(b, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_submarine] wrote {OUT}")
