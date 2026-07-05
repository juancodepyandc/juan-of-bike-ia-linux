"""
proc_swiss_chalet_alps.py — 133e procédural AuroraIA, Phase F++++.

Chalet suisse dans Alpes : chalet en bois 2 étages avec balcon fleuri
+ 2 cheminées avec fumée + 5 fenêtres émissives + volets + toit large
pente forte + 4 sapins enneigés + 3 montagnes neigeuses background
avec snow caps + lac glacé bleu + 4 vaches broutant avec cloches
émissives + 60 flocons neige tombant + ciel matin clair + soleil
+ 4 rondins bois + cheminée principale.

Animation :
- 60 flocons tombent lentement
- 2 cheminées fumée monte
- 4 vaches head bob (chewing)
- cloches pulse émission
- 4 sapins sway feuilles
- soleil halo pulse

Sortie : output/3d/pbr_swisschalet_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_swisschalet_proc.glb"))

random.seed(0xCAFE55)

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
MAT_SKY = make_mat("sky", (0.70, 0.85, 0.95), roughness=1.0,
                    emi=(0.55, 0.75, 0.92), emi_strength=0.5)
MAT_SUN = make_mat("sun", (1.0, 0.95, 0.75), roughness=0.0,
                     emi=(1.0, 0.95, 0.75), emi_strength=6.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.95, 0.80), roughness=0.0, alpha=0.25,
                          emi=(1.0, 0.90, 0.75), emi_strength=2.5)
MAT_SNOW = make_mat("snow", (0.95, 0.96, 1.0), roughness=0.7,
                      emi=(0.55, 0.60, 0.70), emi_strength=0.3)
MAT_MOUNTAIN = make_mat("mountain", (0.30, 0.32, 0.38), roughness=0.9)
MAT_MOUNTAIN_DARK = make_mat("mountain_dark", (0.20, 0.22, 0.28), roughness=0.95)
MAT_ICE_LAKE = make_mat("ice_lake", (0.55, 0.75, 0.90), metallic=0.6, roughness=0.1, alpha=0.9,
                          emi=(0.45, 0.65, 0.85), emi_strength=0.7)
MAT_GROUND = make_mat("ground", (0.20, 0.35, 0.18), roughness=0.85)
MAT_WOOD_CHALET = make_mat("wood_chalet", (0.55, 0.30, 0.15), roughness=0.7)
MAT_WOOD_DARK = make_mat("wood_dark", (0.30, 0.18, 0.08), roughness=0.8)
MAT_ROOF = make_mat("roof", (0.45, 0.25, 0.15), roughness=0.7)
MAT_ROOF_SNOW = make_mat("roof_snow", (0.85, 0.88, 0.92), roughness=0.7,
                           emi=(0.40, 0.45, 0.55), emi_strength=0.2)
MAT_WINDOW = make_mat("window", (1.0, 0.85, 0.55), roughness=0.0, alpha=0.85,
                        emi=(1.0, 0.85, 0.55), emi_strength=5.0)
MAT_SHUTTER = make_mat("shutter", (0.55, 0.10, 0.10), roughness=0.6,
                         emi=(0.25, 0.03, 0.03), emi_strength=0.3)
MAT_FLOWER_R = make_mat("flower_r", (0.95, 0.20, 0.30), roughness=0.5,
                          emi=(0.45, 0.05, 0.10), emi_strength=0.5)
MAT_FLOWER_P = make_mat("flower_p", (1.0, 0.55, 0.85), roughness=0.5,
                          emi=(0.45, 0.20, 0.40), emi_strength=0.5)
MAT_FLOWER_Y = make_mat("flower_y", (1.0, 0.85, 0.20), roughness=0.5,
                          emi=(0.45, 0.40, 0.05), emi_strength=0.5)
MAT_CHIMNEY = make_mat("chimney", (0.30, 0.25, 0.22), roughness=0.85)
MAT_SMOKE = make_mat(
    "smoke", (0.65, 0.65, 0.68), roughness=1.0, alpha=0.65,
    emi=(0.45, 0.45, 0.48), emi_strength=0.5,
)
MAT_FIR_TRUNK = make_mat("fir_trunk", (0.25, 0.15, 0.08), roughness=0.95)
MAT_FIR_LEAVES = make_mat("fir_leaves", (0.10, 0.30, 0.15), roughness=0.85)
MAT_FIR_SNOW = make_mat("fir_snow", (0.90, 0.93, 0.98), roughness=0.7,
                          emi=(0.45, 0.50, 0.55), emi_strength=0.3)
MAT_COW_BODY = make_mat("cow_body", (0.95, 0.95, 0.95), roughness=0.7)
MAT_COW_SPOT = make_mat("cow_spot", (0.15, 0.10, 0.06), roughness=0.7)
MAT_COW_HORN = make_mat("cow_horn", (0.85, 0.80, 0.70), roughness=0.5)
MAT_COW_BELL = make_mat("cow_bell", (1.0, 0.80, 0.20), metallic=0.85, roughness=0.25,
                          emi=(0.55, 0.40, 0.10), emi_strength=0.8)
MAT_FLAKE = make_mat("flake", (0.95, 0.95, 1.0), roughness=0.0, alpha=0.85,
                       emi=(0.95, 0.95, 1.0), emi_strength=2.5)
MAT_LOG = make_mat("log", (0.45, 0.28, 0.15), roughness=0.85)

# --- backdrop : alpine sky ------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 18, 7), mat=MAT_SKY)
sky.scale = (40, 0.1, 14)

# sun + halo
sun_p = empty("sun_p", (8.0, 14.0, 9.0))
sun = sphere("sun", r=0.9, segs=20, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo = sphere("sun_halo", r=1.6, segs=18, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# --- 3 mountains background -----------------------------------------------
mountain_data = [
    (-8, 5.0, 8.0, 7.0),
    (0, 8.5, 9.0, 6.5),
    (8, 4.5, 8.0, 7.0),
]
for i, (mx, mh, mw, mz) in enumerate(mountain_data):
    mp = empty(f"mount_{i}", (mx, 0, mz))
    # main rock body
    body = cone(f"mount_{i}_body", r1=mw, r2=0.5, depth=mh, segs=8, loc=(0, mh / 2, 0), parent=mp, mat=MAT_MOUNTAIN)
    body.rotation_euler = (math.radians(90), 0, random.uniform(0, math.pi / 2))
    # snow cap
    cap = cone(f"mount_{i}_cap", r1=2.5, r2=0.1, depth=2.0, segs=8, loc=(0, mh - 1.0, 0), parent=mp, mat=MAT_SNOW)
    cap.rotation_euler = (math.radians(90), 0, 0)
    # dark side details
    dark = cone(f"mount_{i}_dark", r1=mw * 0.7, r2=0.3, depth=mh * 0.7, segs=8, loc=(mw * 0.2, mh * 0.35, 0), parent=mp, mat=MAT_MOUNTAIN_DARK)
    dark.rotation_euler = (math.radians(90), 0, random.uniform(0, math.pi / 2))

# --- snowy ground ----------------------------------------------------------
ground = cube("ground", size=1.0, loc=(0, -0.05, 0), mat=MAT_SNOW)
ground.scale = (35, 0.1, 25)

# some patches of green grass peeking through
for i in range(6):
    gx = random.uniform(-10, 10)
    gz = random.uniform(-8, 6)
    g = cube(f"grass_{i}", size=1.0, loc=(gx, 0.01, gz), mat=MAT_GROUND)
    g.scale = (random.uniform(1.5, 3.0), 0.05, random.uniform(1.0, 2.0))

# --- frozen lake ----------------------------------------------------------
lake = cube("ice_lake", size=1.0, loc=(0, 0.02, 6.5), mat=MAT_ICE_LAKE)
lake.scale = (8, 0.05, 3.5)

# --- main chalet -----------------------------------------------------------
chalet = empty("chalet", (-2.0, 0, -2.0))

# ground floor (stone base)
stone_base = cube("chalet_stone", size=1.0, loc=(0, 0.4, 0), parent=chalet, mat=MAT_MOUNTAIN)
stone_base.scale = (3.5, 0.4, 2.5)

# 1st floor (wooden)
floor1 = cube("chalet_f1", size=1.0, loc=(0, 1.4, 0), parent=chalet, mat=MAT_WOOD_CHALET)
floor1.scale = (3.5, 1.2, 2.5)

# 2nd floor (slightly smaller, with balcony)
floor2 = cube("chalet_f2", size=1.0, loc=(0, 2.8, 0), parent=chalet, mat=MAT_WOOD_DARK)
floor2.scale = (3.2, 1.2, 2.3)

# roof (steeply sloped, large overhang)
roof_p = empty("roof_p", (0, 4.0, 0), parent=chalet)
# 2 sloped panels (front/back)
for side, dz, rot in [("F", 0, math.radians(-30)), ("B", 0, math.radians(30))]:
    panel = cube(f"roof_{side}", size=1.0, loc=(0, 0.5, 1.6 if side == "F" else -1.6), parent=roof_p, mat=MAT_ROOF)
    panel.scale = (4.5, 0.10, 3.0)
    panel.rotation_euler = (rot, 0, 0)

# snow on top of roof
for side, dz in [("F", 1.5), ("B", -1.5)]:
    snow_layer = cube(f"roof_snow_{side}", size=1.0, loc=(0, 1.0, dz), parent=roof_p, mat=MAT_ROOF_SNOW)
    snow_layer.scale = (4.0, 0.15, 2.5)
    snow_layer.rotation_euler = (math.radians(-30) if side == "F" else math.radians(30), 0, 0)

# 5 fenêtres avec volets
windows = []
window_data = [
    (-0.9, 1.4, 1.27),
    (0.9, 1.4, 1.27),
    (0, 2.8, 1.17),
    (-1.0, 2.8, 1.17),
    (1.0, 2.8, 1.17),
]
for i, (wx, wy, wz) in enumerate(window_data):
    w = cube(f"chalet_w_{i}", size=1.0, loc=(wx, wy, wz), parent=chalet, mat=MAT_WINDOW)
    w.scale = (0.4, 0.4, 0.05)
    windows.append(w)
    # 2 shutters (open)
    for side, dx in [("L", -0.27), ("R", 0.27)]:
        sh = cube(f"chalet_sh_{i}_{side}", size=1.0, loc=(wx + dx, wy, wz + 0.04), parent=chalet, mat=MAT_SHUTTER)
        sh.scale = (0.10, 0.45, 0.03)

# door (centered ground floor)
door = cube("chalet_door", size=1.0, loc=(0, 1.2, 1.27), parent=chalet, mat=MAT_WOOD_DARK)
door.scale = (0.35, 0.9, 0.06)

# balcony (extends from 2nd floor front)
balc_p = empty("balc_p", (0, 2.20, 1.40), parent=chalet)
balc_floor = cube("balc_floor", size=1.0, loc=(0, 0, 0), parent=balc_p, mat=MAT_WOOD_CHALET)
balc_floor.scale = (3.0, 0.06, 0.6)
# 2 sides walls
for side, dx in [("L", -1.5), ("R", 1.5)]:
    bw = cube(f"balc_w_{side}", size=1.0, loc=(dx, 0.05, 0), parent=balc_p, mat=MAT_WOOD_CHALET)
    bw.scale = (0.05, 0.10, 0.6)
# 8 railing posts
for i in range(8):
    rx = -1.4 + i * 0.4
    rp = cube(f"balc_rail_{i}", size=1.0, loc=(rx, 0.25, 0.28), parent=balc_p, mat=MAT_WOOD_DARK)
    rp.scale = (0.05, 0.4, 0.05)
# top rail
top_rail = cube("balc_top_rail", size=1.0, loc=(0, 0.45, 0.28), parent=balc_p, mat=MAT_WOOD_DARK)
top_rail.scale = (3.0, 0.05, 0.05)

# flower boxes on balcony (alternating colors)
flower_mats = [MAT_FLOWER_R, MAT_FLOWER_P, MAT_FLOWER_Y]
for i in range(7):
    fx = -1.2 + i * 0.4
    # box
    box = cube(f"balc_box_{i}", size=1.0, loc=(fx, 0.10, 0.28), parent=balc_p, mat=MAT_WOOD_DARK)
    box.scale = (0.18, 0.08, 0.06)
    # 3 flowers per box
    for k in range(3):
        kx = -0.10 + k * 0.10
        flower = sphere(f"balc_flower_{i}_{k}", r=0.06, segs=8, rings=6, loc=(fx + kx, 0.18, 0.28), parent=balc_p, mat=flower_mats[(i + k) % 3])

# --- 2 cheminées ---------------------------------------------------------
chimneys = []
smoke_puffs_list = []
for i, (cx, cz) in enumerate([(-1.0, -0.5), (1.2, 0.5)]):
    chim_p = empty(f"chim_p_{i}", (cx, 5.0, cz), parent=chalet)
    chim = cube(f"chim_{i}", size=1.0, loc=(0, 0, 0), parent=chim_p, mat=MAT_CHIMNEY)
    chim.scale = (0.3, 1.0, 0.3)
    # top opening
    top = cone(f"chim_{i}_top", r1=0.18, r2=0.15, depth=0.08, segs=8, loc=(0, 0.55, 0), parent=chim_p, mat=MAT_WOOD_DARK)
    top.rotation_euler = (math.radians(90), 0, 0)
    chimneys.append(chim_p)
    # 5 smoke puffs
    for k in range(5):
        py = 0.7 + k * 0.5
        pr = 0.18 + k * 0.08
        puff = sphere(f"chim_{i}_smoke_{k}", r=pr, segs=12, rings=8, loc=(0, py, 0), parent=chim_p, mat=MAT_SMOKE)
        smoke_puffs_list.append((puff, i, k))

# --- 4 sapins enneigés ---------------------------------------------------
firs = []
for i, (fx, fz) in enumerate([(-8, -3), (8, -3), (-7, 2), (8, 2.5)]):
    fp = empty(f"fir_{i}", (fx, 0, fz))
    # trunk
    trunk = cone(f"fir_{i}_trunk", r1=0.18, r2=0.14, depth=1.2, segs=8, loc=(0, 0.6, 0), parent=fp, mat=MAT_FIR_TRUNK)
    trunk.rotation_euler = (math.radians(90), 0, 0)
    # 4 layers of leaves (alternating fir + snow)
    for j in range(4):
        y = 1.0 + j * 0.55
        r = 0.85 - j * 0.18
        mat = MAT_FIR_LEAVES if j % 2 == 0 else MAT_FIR_LEAVES
        layer = cone(f"fir_{i}_l_{j}", r1=r, r2=r * 0.3, depth=0.55, segs=10, loc=(0, y, 0), parent=fp, mat=mat)
        layer.rotation_euler = (math.radians(90), 0, 0)
        # snow on top of each layer
        snow = cone(f"fir_{i}_s_{j}", r1=r * 0.9, r2=r * 0.25, depth=0.10, segs=10, loc=(0, y + 0.20, 0), parent=fp, mat=MAT_FIR_SNOW)
        snow.rotation_euler = (math.radians(90), 0, 0)
    firs.append(fp)

# --- 4 vaches broutant ---------------------------------------------------
cow_heads = []  # for animation
cow_bells = []
def make_cow(name, x, z, rot=0):
    p = empty(name, (x, 0, z))
    p.rotation_euler = (0, rot, 0)
    # body
    body = sphere(f"{name}_body", r=0.40, segs=16, rings=10, loc=(0, 0.8, 0), parent=p, mat=MAT_COW_BODY)
    body.scale = (1.7, 0.9, 0.8)
    # spots (3 black patches)
    for k in range(3):
        ka = k * (math.pi * 2 / 3)
        spot = sphere(f"{name}_spot_{k}", r=0.20, segs=10, rings=8, loc=(math.cos(ka) * 0.4, 0.80, math.sin(ka) * 0.4), parent=p, mat=MAT_COW_SPOT)
        spot.scale = (1.0, 0.4, 1.0)
    # head (forward bottom for grazing)
    head_p = empty(f"{name}_head_p", (0.65, 0.55, 0), parent=p)
    head = sphere(f"{name}_head", r=0.22, segs=12, rings=8, loc=(0, 0, 0), parent=head_p, mat=MAT_COW_BODY)
    head.scale = (1.3, 0.9, 0.8)
    # 2 horns
    for side, dz in [("L", 0.12), ("R", -0.12)]:
        horn = cone(f"{name}_horn_{side}", r1=0.04, r2=0.0, depth=0.20, segs=6, loc=(0.10, 0.22, dz), parent=head_p, mat=MAT_COW_HORN)
        horn.rotation_euler = (math.radians(-30), 0, math.radians(20 if side == "L" else -20))
    # 2 ears
    for side, dz in [("L", 0.18), ("R", -0.18)]:
        ear = sphere(f"{name}_ear_{side}", r=0.07, segs=8, rings=6, loc=(0.10, 0.15, dz), parent=head_p, mat=MAT_COW_BODY)
        ear.scale = (0.6, 0.7, 1.2)
    # snout
    snout = sphere(f"{name}_snout", r=0.10, segs=10, rings=6, loc=(0.22, 0.05, 0), parent=head_p, mat=MAT_COW_SPOT)
    snout.scale = (1.3, 0.7, 0.9)
    # bell hanging from neck
    bell = sphere(f"{name}_bell", r=0.10, segs=10, rings=8, loc=(0.45, 0.40, 0), parent=p, mat=MAT_COW_BELL)
    bell.scale = (1.0, 1.2, 1.0)
    cow_bells.append(bell)
    # 4 legs
    for k, (lx, lz) in enumerate([(0.35, 0.20), (0.35, -0.20), (-0.35, 0.20), (-0.35, -0.20)]):
        leg = cube(f"{name}_leg_{k}", size=1.0, loc=(lx, 0.30, lz), parent=p, mat=MAT_COW_BODY)
        leg.scale = (0.10, 0.6, 0.10)
    # tail
    tail = cone(f"{name}_tail", r1=0.05, r2=0.02, depth=0.30, segs=6, loc=(-0.55, 0.75, 0), parent=p, mat=MAT_COW_BODY)
    tail.rotation_euler = (0, 0, math.radians(110))
    return p, head_p

cows = []
for i, (cx, cz, crot) in enumerate([
    (4.5, 4.0, math.radians(45)),
    (5.5, 5.0, math.radians(-30)),
    (-5.0, 4.5, math.radians(70)),
    (-4.0, 3.0, math.radians(-60)),
]):
    cp, head_p = make_cow(f"cow_{i}", cx, cz, crot)
    cows.append((cp, head_p, i))

# --- 4 rondins de bois empilés ------------------------------------------
log_p = empty("log_pile", (-3.5, 0, -4.0))
for i in range(6):
    # bottom layer 3 logs, middle 2, top 1
    if i < 3:
        ix = -0.6 + i * 0.6
        iy = 0.15
    elif i < 5:
        ix = -0.3 + (i - 3) * 0.6
        iy = 0.40
    else:
        ix = 0
        iy = 0.65
    log = cone(f"log_{i}", r1=0.18, r2=0.18, depth=0.8, segs=10, loc=(ix, iy, 0), parent=log_p, mat=MAT_LOG)
    log.rotation_euler = (0, math.radians(90), 0)

# --- 60 flocons de neige ------------------------------------------------
flakes = []
for i in range(60):
    fx = random.uniform(-15, 15)
    fz = random.uniform(-10, 10)
    fy = random.uniform(3, 12)
    f = sphere(f"flake_{i}", r=random.uniform(0.05, 0.10), segs=6, rings=4, loc=(fx, fy, fz), mat=MAT_FLAKE)
    flakes.append((f, fx, fz, fy, random.uniform(0, 1)))

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

# 60 flakes fall slowly with horizontal drift
for fk, fx, fz, fy_init, ph in flakes:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        local = (tt + ph) % 1.0
        fy = fy_init - local * 10.0
        if fy < 0.1:
            fy = 0.1
        drift_x = math.sin(local * math.pi * 3.0 + ph * 5.0) * 0.3
        drift_z = math.cos(local * math.pi * 2.5 + ph * 5.0) * 0.2
        kf_loc(fk, f, (fx + drift_x, fy, fz + drift_z))

# 2 chimney smoke rise
for puff, chim_i, k in smoke_puffs_list:
    phase = chim_i * 10 + k * 8
    base_y = 0.7 + k * 0.5
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 70
        lt = local_f / 70
        dy = base_y + lt * 2.0
        dx = math.sin(lt * math.pi * 3.0) * 0.20
        kf_loc(puff, f, (dx, dy, 0))
        s = 0.5 + lt * 1.5
        kf_scale(puff, f, (s, s, s))

# cows head bob (chewing)
for cp, head_p, idx in cows:
    phase = idx * 0.5
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bob = math.radians(8) * math.sin(tt * math.pi * 6.0 + phase)
        kf_rot(head_p, f, (bob, 0, 0))

# cow bells pulse
for i, bell in enumerate(cow_bells):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(bell, f, (s, 1.2 * s, s))

# 4 firs sway
for i, fp in enumerate(firs):
    phase = i * 0.5
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bend = math.radians(2) * math.sin(tt * math.pi * 2.0 + phase)
        kf_rot(fp, f, (bend, 0, bend * 0.5))

# sun halo breathe
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.10 * math.sin(tt * math.pi * 3.0)
    kf_scale(sun_halo, f, (s, s, s))

# windows pulse subtle
for i, w in enumerate(windows):
    phase = i * 0.4
    base = w.scale.copy()
    for f in range(1, FRAMES + 1, 5):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.06 * math.sin(tt * math.pi * 4.0 + phase)
        kf_scale(w, f, (base[0] * s, base[1] * s, base[2]))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_swisschalet] wrote {OUT}")
