"""
proc_cyberpunk_city.py — 130e procédural AuroraIA, Phase F++++ MILESTONE.

Ville cyberpunk futuriste pluvieuse nuit : 8 gratte-ciels rectangulaires
avec néons + 4 enseignes lumineuses + 6 voitures volantes flying file
+ 5 panneaux publicitaires holographiques scintillants + sol mouillé
réfléchissant + 40 gouttes pluie tombant + 10 personnages silhouettes
+ 2 hovercraft + 3 drones planants + 2 ponts élevés inter-gratte-ciels
+ rues émissives + ciel violet sombre.

Animation :
- 6 voitures volantes : file linéaire X
- 5 hologrammes : scale pulse + cycle couleurs
- 3 drones : hover + drift
- 40 gouttes : tombent en loop
- gratte-ciels néons : pulse différentiel
- enseignes : flicker rapide

Sortie : output/3d/pbr_cyberpunk_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_cyberpunk_proc.glb"))

random.seed(0xCAFEED)

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
MAT_SKY = make_mat("sky", (0.08, 0.03, 0.18), roughness=1.0,
                    emi=(0.12, 0.05, 0.25), emi_strength=0.6)
MAT_BUILDING_DARK = make_mat("building_dark", (0.06, 0.05, 0.08), roughness=0.7,
                               emi=(0.04, 0.03, 0.10), emi_strength=0.2)
MAT_BUILDING_DARKER = make_mat("building_darker", (0.03, 0.03, 0.05), roughness=0.6)
MAT_GROUND_WET = make_mat("ground_wet", (0.05, 0.05, 0.08), metallic=0.8, roughness=0.05,
                            emi=(0.10, 0.05, 0.20), emi_strength=0.5)
MAT_STREET = make_mat("street", (0.08, 0.05, 0.12), metallic=0.7, roughness=0.1,
                        emi=(0.15, 0.08, 0.25), emi_strength=0.7)
MAT_NEON_PINK = make_mat("neon_pink", (1.0, 0.20, 0.85), roughness=0.0,
                           emi=(1.0, 0.20, 0.85), emi_strength=10.0)
MAT_NEON_CYAN = make_mat("neon_cyan", (0.20, 0.95, 1.0), roughness=0.0,
                           emi=(0.20, 0.95, 1.0), emi_strength=10.0)
MAT_NEON_PURPLE = make_mat("neon_purple", (0.75, 0.20, 1.0), roughness=0.0,
                             emi=(0.75, 0.20, 1.0), emi_strength=10.0)
MAT_NEON_YELLOW = make_mat("neon_yellow", (1.0, 0.95, 0.20), roughness=0.0,
                             emi=(1.0, 0.95, 0.20), emi_strength=10.0)
MAT_NEON_RED = make_mat("neon_red", (1.0, 0.10, 0.20), roughness=0.0,
                          emi=(1.0, 0.10, 0.20), emi_strength=10.0)
MAT_NEON_GREEN = make_mat("neon_green", (0.20, 1.0, 0.40), roughness=0.0,
                            emi=(0.20, 1.0, 0.40), emi_strength=10.0)
MAT_WINDOW_WARM = make_mat("window_warm", (1.0, 0.65, 0.30), roughness=0.0, alpha=0.85,
                             emi=(1.0, 0.65, 0.30), emi_strength=4.0)
MAT_WINDOW_COLD = make_mat("window_cold", (0.30, 0.85, 1.0), roughness=0.0, alpha=0.85,
                             emi=(0.30, 0.85, 1.0), emi_strength=4.0)
MAT_HOLOGRAM_P = make_mat("hologram_p", (1.0, 0.30, 0.85), roughness=0.0, alpha=0.55,
                            emi=(1.0, 0.30, 0.85), emi_strength=7.0)
MAT_HOLOGRAM_C = make_mat("hologram_c", (0.30, 0.95, 1.0), roughness=0.0, alpha=0.55,
                            emi=(0.30, 0.95, 1.0), emi_strength=7.0)
MAT_HOLOGRAM_Y = make_mat("hologram_y", (1.0, 0.85, 0.20), roughness=0.0, alpha=0.55,
                            emi=(1.0, 0.85, 0.20), emi_strength=7.0)
MAT_CAR_BODY = make_mat("car_body", (0.10, 0.08, 0.10), metallic=0.85, roughness=0.3)
MAT_CAR_HEADLIGHT = make_mat("car_hl", (1.0, 0.95, 0.85), roughness=0.0,
                               emi=(1.0, 0.95, 0.85), emi_strength=8.0)
MAT_CAR_TAILLIGHT = make_mat("car_tl", (1.0, 0.20, 0.20), roughness=0.0,
                               emi=(1.0, 0.20, 0.20), emi_strength=6.0)
MAT_CAR_UNDERGLOW = make_mat("car_under", (0.30, 0.85, 1.0), roughness=0.0,
                               emi=(0.30, 0.85, 1.0), emi_strength=5.0)
MAT_HOVER = make_mat("hover", (0.55, 0.20, 0.55), metallic=0.7, roughness=0.4,
                       emi=(0.20, 0.05, 0.25), emi_strength=0.5)
MAT_DRONE = make_mat("drone", (0.20, 0.20, 0.25), metallic=0.6, roughness=0.4,
                       emi=(0.10, 0.10, 0.15), emi_strength=0.3)
MAT_DRONE_LIGHT = make_mat("drone_light", (0.20, 1.0, 0.40), roughness=0.0,
                             emi=(0.20, 1.0, 0.40), emi_strength=7.0)
MAT_RAIN = make_mat("rain", (0.65, 0.75, 0.85), roughness=0.0, alpha=0.55,
                      emi=(0.55, 0.70, 0.85), emi_strength=1.5)
MAT_PERSON = make_mat("person", (0.08, 0.06, 0.10), roughness=0.7,
                        emi=(0.05, 0.05, 0.10), emi_strength=0.2)
MAT_PERSON_GLOW = make_mat("person_glow", (1.0, 0.10, 0.85), roughness=0.0,
                             emi=(0.4, 0.05, 0.30), emi_strength=2.0)
MAT_BRIDGE = make_mat("bridge", (0.10, 0.08, 0.12), metallic=0.7, roughness=0.4,
                        emi=(0.20, 0.05, 0.30), emi_strength=0.5)

# --- backdrop : night sky --------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 18, 6), mat=MAT_SKY)
sky.scale = (40, 0.1, 18)

# wet ground (highly reflective)
ground = cube("ground_wet", size=1.0, loc=(0, -0.05, 0), mat=MAT_GROUND_WET)
ground.scale = (40, 0.1, 30)

# street strips (4 horizontal emissive lines)
for i in range(4):
    z = -8 + i * 5
    street = cube(f"street_{i}", size=1.0, loc=(0, 0.05, z), mat=MAT_STREET)
    street.scale = (40, 0.05, 1.0)

# --- 8 gratte-ciels (skyscrapers) ----------------------------------------
neon_mats = [MAT_NEON_PINK, MAT_NEON_CYAN, MAT_NEON_PURPLE, MAT_NEON_YELLOW, MAT_NEON_RED, MAT_NEON_GREEN]
window_mats = [MAT_WINDOW_WARM, MAT_WINDOW_COLD]

def make_skyscraper(name, x, z, w, h, d, n_floors, neon_mat):
    p = empty(name, (x, 0, z))
    # main body (dark, with windows arrays)
    body = cube(f"{name}_body", size=1.0, loc=(0, h / 2, 0), parent=p, mat=MAT_BUILDING_DARK)
    body.scale = (w, h, d)
    # window grid (each floor : 4 windows front)
    for floor in range(n_floors):
        fy = 0.8 + floor * (h / n_floors)
        for col in range(4):
            cx = -w * 0.35 + col * (w * 0.7 / 3)
            mat = window_mats[(floor + col) % 2]
            win = cube(f"{name}_w_{floor}_{col}", size=1.0, loc=(cx, fy, d / 2 + 0.01), parent=p, mat=mat)
            win.scale = (0.15, 0.20, 0.02)
    # vertical neon stripe on the side (full height)
    for side, dx in [("L", -w / 2), ("R", w / 2)]:
        ns = cube(f"{name}_neon_{side}", size=1.0, loc=(dx, h / 2, d / 2 + 0.05), parent=p, mat=neon_mat)
        ns.scale = (0.05, h * 0.9, 0.04)
    # top antenna
    ant = cone(f"{name}_ant", r1=0.05, r2=0.02, depth=h * 0.15, segs=4, loc=(0, h + h * 0.07, 0), parent=p, mat=MAT_BUILDING_DARKER)
    ant.rotation_euler = (math.radians(90), 0, 0)
    # blinking light on top
    blink = sphere(f"{name}_blink", r=0.10, segs=10, rings=8, loc=(0, h + h * 0.15, 0), parent=p, mat=MAT_NEON_RED)
    return p, blink

skyscraper_data = [
    (-12, 6, 2.0, 10.0, 2.0, 12, MAT_NEON_PINK),
    (-8, 8, 2.5, 12.0, 2.5, 14, MAT_NEON_CYAN),
    (-4, 6, 1.8, 8.0, 1.8, 10, MAT_NEON_PURPLE),
    (0, 8, 2.2, 11.0, 2.2, 13, MAT_NEON_YELLOW),
    (4, 6, 1.9, 9.5, 1.9, 11, MAT_NEON_GREEN),
    (8, 8, 2.4, 13.0, 2.4, 15, MAT_NEON_RED),
    (12, 6, 2.0, 9.0, 2.0, 10, MAT_NEON_CYAN),
    (16, 7, 2.3, 11.0, 2.3, 13, MAT_NEON_PINK),
]
sky_blinks = []
for i, (sx, sz, w, h, d, nf, nm) in enumerate(skyscraper_data):
    p, blink = make_skyscraper(f"sky_{i}", sx, sz, w, h, d, nf, nm)
    sky_blinks.append((blink, i))

# --- 4 enseignes lumineuses (neon signs on buildings) -------------------
neon_signs = []
sign_data = [
    (-10, 7.5, 6.7, MAT_NEON_PINK),
    (-2, 9.0, 8.7, MAT_NEON_CYAN),
    (6, 8.0, 6.7, MAT_NEON_YELLOW),
    (14, 6.0, 6.7, MAT_NEON_GREEN),
]
for i, (nx, ny, nz, mat) in enumerate(sign_data):
    np = empty(f"sign_{i}", (nx, ny, nz - 0.05))
    # border rectangle
    for side, dx, dy, sx, sy in [
        ("T", 0, 0.5, 1.6, 0.10),
        ("B", 0, -0.5, 1.6, 0.10),
        ("L", -0.8, 0, 0.10, 1.0),
        ("R", 0.8, 0, 0.10, 1.0),
    ]:
        bar = cube(f"sign_{i}_{side}", size=1.0, loc=(dx, dy, 0), parent=np, mat=mat)
        bar.scale = (sx, sy, 0.08)
    # 4 inner letter bars
    for k in range(4):
        kx = -0.55 + k * 0.35
        lt = cube(f"sign_{i}_l_{k}", size=1.0, loc=(kx, 0, 0), parent=np, mat=mat)
        lt.scale = (0.08, 0.45, 0.06)
    neon_signs.append((np, i))

# --- 5 hologrammes publicitaires scintillants ---------------------------
holograms = []
hologram_mats = [MAT_HOLOGRAM_P, MAT_HOLOGRAM_C, MAT_HOLOGRAM_Y]
holo_data = [(-13, 4, 4.5), (-6, 5, 4.5), (2, 4.5, 4.5), (10, 5, 4.5), (15, 4, 4.5)]
for i, (hx, hy, hz) in enumerate(holo_data):
    hp = empty(f"holo_{i}", (hx, hy, hz))
    mat = hologram_mats[i % 3]
    # stylized figure : 3 stacked cubes suggesting a person/object hologram
    for k in range(3):
        ky = -0.5 + k * 0.5
        sx = 0.7 - k * 0.15
        h = cube(f"holo_{i}_{k}", size=1.0, loc=(0, ky, 0), parent=hp, mat=mat)
        h.scale = (sx, 0.40, 0.05)
    # head/top sphere
    head = sphere(f"holo_{i}_head", r=0.30, segs=10, rings=8, loc=(0, 1.20, 0), parent=hp, mat=mat)
    head.scale = (1.0, 1.0, 0.2)
    holograms.append((hp, i))

# --- 6 voitures volantes ---------------------------------------------------
flying_cars = []
for i in range(6):
    cy = 3.0 + (i % 3) * 0.8
    cx = -18 + (i * 3.5) % 36
    cz = (-3 if i % 2 == 0 else 3)
    cp = empty(f"car_{i}", (cx, cy, cz))
    # main body (flat, sleek)
    body = cube(f"car_{i}_body", size=1.0, loc=(0, 0, 0), parent=cp, mat=MAT_CAR_BODY)
    body.scale = (0.8, 0.20, 0.40)
    # cockpit (translucent dome)
    cock = sphere(f"car_{i}_cock", r=0.30, segs=12, rings=8, loc=(0.05, 0.18, 0), parent=cp, mat=MAT_WINDOW_COLD)
    cock.scale = (1.2, 0.6, 0.7)
    # 2 headlights (front)
    for side, dz in [("L", 0.20), ("R", -0.20)]:
        hl = sphere(f"car_{i}_hl_{side}", r=0.05, segs=8, rings=6, loc=(0.78, 0.05, dz), parent=cp, mat=MAT_CAR_HEADLIGHT)
    # 2 taillights (back)
    for side, dz in [("L", 0.20), ("R", -0.20)]:
        tl = sphere(f"car_{i}_tl_{side}", r=0.05, segs=8, rings=6, loc=(-0.78, 0.05, dz), parent=cp, mat=MAT_CAR_TAILLIGHT)
    # underglow strip (cyan)
    underglow = cube(f"car_{i}_under", size=1.0, loc=(0, -0.10, 0), parent=cp, mat=MAT_CAR_UNDERGLOW)
    underglow.scale = (0.7, 0.04, 0.30)
    flying_cars.append((cp, i, cy, cz))

# --- 2 hovercrafts (larger vehicles) ------------------------------------
hovers = []
for i, (hx, hy, hz) in enumerate([(-9, 1.5, 0), (7, 1.5, 0)]):
    hp = empty(f"hover_{i}", (hx, hy, hz))
    # body
    body = cube(f"hover_{i}_body", size=1.0, loc=(0, 0, 0), parent=hp, mat=MAT_HOVER)
    body.scale = (1.4, 0.30, 0.7)
    # 2 fans below
    for side, dx in [("F", 0.6), ("B", -0.6)]:
        fan = cone(f"hover_{i}_fan_{side}", r1=0.35, r2=0.35, depth=0.1, segs=12, loc=(dx, -0.20, 0), parent=hp, mat=MAT_DRONE)
        fan.rotation_euler = (0, 0, 0)
    # cockpit
    cock = sphere(f"hover_{i}_cock", r=0.40, segs=12, rings=8, loc=(0.10, 0.25, 0), parent=hp, mat=MAT_WINDOW_COLD)
    cock.scale = (1.2, 0.6, 0.7)
    # 4 lights on bottom (cyan glow)
    for j, (jx, jz) in enumerate([(0.5, 0.3), (-0.5, 0.3), (0.5, -0.3), (-0.5, -0.3)]):
        l = sphere(f"hover_{i}_l_{j}", r=0.06, segs=8, rings=6, loc=(jx, -0.15, jz), parent=hp, mat=MAT_CAR_UNDERGLOW)
    hovers.append(hp)

# --- 3 drones planants ---------------------------------------------------
drones = []
for i, (dx, dy, dz) in enumerate([(-5, 5.0, -3), (3, 6.0, -2), (10, 5.5, -4)]):
    dp = empty(f"drone_{i}", (dx, dy, dz))
    body = sphere(f"drone_{i}_body", r=0.15, segs=10, rings=8, loc=(0, 0, 0), parent=dp, mat=MAT_DRONE)
    body.scale = (1.2, 0.6, 1.0)
    # 4 propellers
    for j, (jx, jz) in enumerate([(0.25, 0.25), (-0.25, 0.25), (0.25, -0.25), (-0.25, -0.25)]):
        prop = cone(f"drone_{i}_p_{j}", r1=0.10, r2=0.10, depth=0.04, segs=8, loc=(jx, 0.08, jz), parent=dp, mat=MAT_DRONE)
        prop.rotation_euler = (math.radians(90), 0, 0)
    # bottom light
    light = sphere(f"drone_{i}_l", r=0.04, segs=8, rings=6, loc=(0, -0.10, 0), parent=dp, mat=MAT_DRONE_LIGHT)
    drones.append(dp)

# --- 2 ponts élevés (skybridges) ------------------------------------------
bridges = []
for i, (bx, by, bz) in enumerate([(-6, 5.5, 5), (10, 6.0, 5)]):
    bp = empty(f"bridge_{i}", (bx, by, bz))
    deck = cube(f"bridge_{i}_deck", size=1.0, loc=(0, 0, 0), parent=bp, mat=MAT_BRIDGE)
    deck.scale = (3.5, 0.10, 0.6)
    # 2 rails
    for side, dz in [("L", 0.30), ("R", -0.30)]:
        rail = cube(f"bridge_{i}_rail_{side}", size=1.0, loc=(0, 0.20, dz), parent=bp, mat=MAT_NEON_CYAN)
        rail.scale = (3.5, 0.04, 0.04)
    bridges.append(bp)

# --- 10 personnages silhouettes ------------------------------------------
people = []
for i in range(10):
    px = -15 + i * 3.5
    pz = random.uniform(-5, -1)
    pp = empty(f"person_{i}", (px, 0, pz))
    body = cube(f"person_{i}_body", size=1.0, loc=(0, 0.6, 0), parent=pp, mat=MAT_PERSON)
    body.scale = (0.18, 0.50, 0.10)
    head = sphere(f"person_{i}_head", r=0.10, segs=10, rings=6, loc=(0, 1.20, 0), parent=pp, mat=MAT_PERSON)
    # neon hair / jacket detail (small emissive accent)
    glow = cube(f"person_{i}_glow", size=1.0, loc=(0, 0.85, 0.06), parent=pp, mat=MAT_PERSON_GLOW)
    glow.scale = (0.10, 0.10, 0.04)
    people.append(pp)

# --- 40 gouttes de pluie ----------------------------------------------------
rain_drops = []
for i in range(40):
    rx = random.uniform(-18, 18)
    rz = random.uniform(-8, 8)
    ry = random.uniform(2, 14)
    d = cube(f"rain_{i}", size=1.0, loc=(rx, ry, rz), mat=MAT_RAIN)
    d.scale = (0.02, 0.20, 0.02)
    d.rotation_euler = (math.radians(10), 0, math.radians(5))
    rain_drops.append((d, rx, rz, ry, random.uniform(0, 1)))

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

# 6 flying cars move in a horizontal file
for cp, idx, cy, cz in flying_cars:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        offset = idx * 6.0
        x = ((tt * 22.0 + offset) % 36) - 18
        y_bob = cy + 0.15 * math.sin(tt * math.pi * 6.0 + idx)
        kf_loc(cp, f, (x, y_bob, cz))

# 4 neon signs pulse different phases
for ns_p, idx in neon_signs:
    phase = idx * 0.5
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.25 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(ns_p, f, (s, s, 1.0))

# 5 hologrammes scale pulse + Y bob (flickering image)
for hp, idx in holograms:
    phase = idx * 0.4
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        flicker = 1.0 + 0.10 * math.sin(tt * math.pi * 20.0 + phase)
        ys = 1.0 + 0.05 * math.sin(tt * math.pi * 3.0 + phase)
        kf_scale(hp, f, (flicker, ys, flicker))

# 3 drones hover
for i, dp in enumerate(drones):
    base = (dp.location.x, dp.location.y, dp.location.z)
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        dx = base[0] + 0.5 * math.sin(tt * math.pi * 2.0 + i * 0.6)
        dy = base[1] + 0.3 * math.sin(tt * math.pi * 3.0 + i * 0.6)
        dz = base[2] + 0.4 * math.cos(tt * math.pi * 2.5 + i * 0.6)
        kf_loc(dp, f, (dx, dy, dz))

# rain falls
for d, rx, rz, ry_init, ph in rain_drops:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        local = (tt + ph) % 1.0
        ry = ry_init - local * 14.0
        if ry < 0.1:
            ry = 0.1
        kf_loc(d, f, (rx, ry, rz))

# 8 skyscraper blink lights pulse
for blink, idx in sky_blinks:
    phase = idx * 0.3
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.40 * math.sin(tt * math.pi * 8.0 + phase)
        kf_scale(blink, f, (s, s, s))

# people sway subtle
for i, p in enumerate(people):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 5):
        tt = (f - 1) / (FRAMES - 1)
        tilt = math.radians(3) * math.sin(tt * math.pi * 4.0 + phase)
        kf_rot(p, f, (tilt, 0, 0))

# hovers bob
for i, hp in enumerate(hovers):
    base_y = hp.location.y
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        dy = base_y + 0.20 * math.sin(tt * math.pi * 3.0 + i * 0.7)
        kf_loc(hp, f, (hp.location.x, dy, hp.location.z))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_cyberpunk] wrote {OUT}")
