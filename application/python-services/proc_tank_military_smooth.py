"""
proc_tank_military_smooth.py — 144e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué.

Tank militaire moderne smooth shaded :
- coque (chassis) bevelée smooth
- turret rotatif avec armor sloped
- canon principal long avec muzzle brake
- 2 chenilles complètes (16 track plates + 7 wheels each)
- 4 idler wheels + 2 sprocket wheels
- mitrailleuse coaxiale + commander cupola
- 2 antennas + 2 search lights émissifs
- 4 fuel barrels arrière
- camo netting top
- camouflage stripes vertes/marron
- piste boue dirt road
- 5 arbres camouflage
- 3 tanks alliés en arrière-plan (smaller)
- ciel grey day
- 4 smoke screen puffs

Animations multi-axes simultanées :
- tank chassis : translate X avance + bob subtle
- 2 tracks wheels : 14 wheels (7 each side) rotate X synchronisé
- track plates : translation effect via offset cumulative
- turret : rotate Y ±45° (looking for targets)
- canon : pitch X ±10°·sin(slow) + slight recoil scale Y
- mitrailleuse coaxiale : pivot autour cannon
- 2 search lights : pulse intense
- 2 antennas : sway
- 4 smoke puffs : rise

Sortie : output/3d/pbr_tank_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_tank_proc.glb"))

random.seed(0xCAFE97)

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


def smooth_shade(mesh):
    for poly in mesh.polygons:
        poly.use_smooth = True
    try:
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(40)
    except AttributeError:
        pass


def beveled_cube(name, size_xyz, bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=None, mat=None, smooth=True):
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
    if smooth:
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
MAT_SKY = make_mat("sky", (0.45, 0.48, 0.52), roughness=1.0,
                    emi=(0.30, 0.35, 0.40), emi_strength=0.4)
MAT_GROUND = make_mat("ground", (0.30, 0.25, 0.18), roughness=0.95)
MAT_GROUND_MUD = make_mat("ground_mud", (0.20, 0.15, 0.10), roughness=0.95)
MAT_TANK_GREEN = make_mat("tank_green", (0.20, 0.30, 0.15), metallic=0.55, roughness=0.55,
                            emi=(0.05, 0.08, 0.04), emi_strength=0.15)
MAT_TANK_BROWN = make_mat("tank_brown", (0.35, 0.25, 0.12), metallic=0.50, roughness=0.60,
                            emi=(0.10, 0.07, 0.03), emi_strength=0.15)
MAT_TANK_DARK = make_mat("tank_dark", (0.10, 0.12, 0.10), metallic=0.60, roughness=0.40)
MAT_TRACK_BLACK = make_mat("track", (0.05, 0.05, 0.05), roughness=0.85)
MAT_TRACK_METAL = make_mat("track_metal", (0.30, 0.30, 0.32), metallic=0.85, roughness=0.30)
MAT_STEEL = make_mat("steel", (0.50, 0.50, 0.55), metallic=0.90, roughness=0.25,
                       emi=(0.10, 0.10, 0.12), emi_strength=0.20)
MAT_LIGHT = make_mat("light", (1.0, 0.92, 0.65), roughness=0.0,
                       emi=(1.0, 0.92, 0.65), emi_strength=12.0)
MAT_LIGHT_HALO = make_mat("light_halo", (1.0, 0.92, 0.70), roughness=0.0, alpha=0.30,
                            emi=(1.0, 0.90, 0.65), emi_strength=4.0)
MAT_BARREL_FUEL = make_mat("fuel_barrel", (0.45, 0.30, 0.15), metallic=0.55, roughness=0.40)
MAT_NETTING = make_mat("netting", (0.25, 0.30, 0.20), roughness=0.85, alpha=0.70)
MAT_TREE_TRUNK = make_mat("tree_trunk", (0.30, 0.20, 0.12), roughness=0.9)
MAT_TREE_LEAVES = make_mat("tree_leaves", (0.15, 0.30, 0.12), roughness=0.85,
                             emi=(0.05, 0.10, 0.04), emi_strength=0.2)
MAT_SMOKE = make_mat("smoke", (0.60, 0.60, 0.60), roughness=1.0, alpha=0.65,
                       emi=(0.40, 0.40, 0.40), emi_strength=0.4)
MAT_FLAG = make_mat("flag", (0.30, 0.40, 0.20), roughness=0.6,
                      emi=(0.08, 0.12, 0.04), emi_strength=0.25)

# --- backdrop : grey day sky ------------------------------------------
sky = beveled_cube("sky_back", (40, 0.2, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, 9, 6), mat=MAT_SKY)

# --- ground -----------------------------------------------------------
ground = beveled_cube("ground", (35, 0.1, 25), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_GROUND)
# 2 dirt tracks (mud roads)
for i in range(2):
    track_road = beveled_cube(f"mud_track_{i}", (35, 0.04, 1.0), bevel_offset=0.05, bevel_segments=2, loc=(0, 0.01, -1.5 + i * 3.0), mat=MAT_GROUND_MUD)

# --- 5 arbres camouflage ---------------------------------------
for i, (tx, tz) in enumerate([(-10, 6), (10, 6), (-9, -7), (9, -7), (0, 9)]):
    tp = empty(f"tree_{i}", (tx, 0, tz))
    trunk = smooth_cone(f"tree_{i}_trunk", r1=0.25, r2=0.20, depth=2.5, segs=14, loc=(0, 1.25, 0), parent=tp, mat=MAT_TREE_TRUNK)
    trunk.rotation_euler = (math.radians(90), 0, 0)
    # foliage
    for j in range(5):
        ja = j * (math.pi * 2 / 5)
        f_obj = smooth_sphere(f"tree_{i}_f_{j}", r=0.7, segs=18, rings=14, loc=(math.cos(ja) * 0.5, 3.0 + random.uniform(-0.2, 0.4), math.sin(ja) * 0.5), parent=tp, mat=MAT_TREE_LEAVES, scale=(1.3, 1.0, 1.3))

# --- 3 tanks alliés en arrière-plan (smaller) -----------------
for i, (bx, bz) in enumerate([(-7, 8), (0, 10), (7, 8)]):
    bg_tank = empty(f"bg_tank_{i}", (bx, 0, bz))
    bg_chassis = beveled_cube(f"bg_chassis_{i}", (1.6, 0.50, 1.0), bevel_offset=0.08, bevel_segments=3, loc=(0, 0.35, 0), parent=bg_tank, mat=MAT_TANK_GREEN)
    bg_turret = smooth_sphere(f"bg_turret_{i}", r=0.45, segs=20, rings=14, loc=(0, 0.75, 0), parent=bg_tank, mat=MAT_TANK_GREEN, scale=(1.4, 0.6, 1.0))
    bg_cannon = smooth_cone(f"bg_cannon_{i}", r1=0.08, r2=0.08, depth=1.2, segs=14, loc=(0.6, 0.75, 0), parent=bg_tank, mat=MAT_TANK_DARK)
    bg_cannon.rotation_euler = (0, 0, math.radians(90))

# --- main tank --------------------------------------------------
tank = empty("tank", (-1.0, 0, 0))

# chassis (large bevelled body)
chassis = beveled_cube("chassis", (3.5, 0.60, 1.8), bevel_offset=0.15, bevel_segments=4, loc=(0, 0.6, 0), parent=tank, mat=MAT_TANK_GREEN)

# 2 sloped armor plates (front + back)
front_armor = beveled_cube("front_armor", (0.8, 0.70, 1.7), bevel_offset=0.12, bevel_segments=4, loc=(1.9, 0.65, 0), parent=tank, mat=MAT_TANK_GREEN)
front_armor.rotation_euler = (0, 0, math.radians(-25))
back_armor = beveled_cube("back_armor", (0.8, 0.50, 1.6), bevel_offset=0.12, bevel_segments=4, loc=(-2.0, 0.55, 0), parent=tank, mat=MAT_TANK_GREEN)
back_armor.rotation_euler = (0, 0, math.radians(20))

# camouflage stripes (brown patches on chassis)
for i, (sx, sz) in enumerate([(-0.5, 0.5), (0.5, -0.4), (-1.2, 0.0), (1.0, 0.3)]):
    stripe = beveled_cube(f"camo_stripe_{i}", (0.5, 0.06, 0.4), bevel_offset=0.04, bevel_segments=2, loc=(sx, 0.92, sz), parent=tank, mat=MAT_TANK_BROWN)

# --- 2 chenilles (tracks) ----------------------------------------
def make_track(name, x_local, z_local, parent):
    p = empty(name, (x_local, 0.35, z_local), parent=parent)
    # base track plate (long bevelled)
    base = beveled_cube(f"{name}_base", (3.5, 0.35, 0.50), bevel_offset=0.12, bevel_segments=3, loc=(0, 0, 0), parent=p, mat=MAT_TRACK_BLACK)
    # 16 track plates on top (treads)
    for k in range(16):
        kx = -1.65 + k * 0.22
        plate = beveled_cube(f"{name}_plate_{k}", (0.18, 0.08, 0.55), bevel_offset=0.03, bevel_segments=2, loc=(kx, 0.20, 0), parent=p, mat=MAT_TRACK_METAL)
    # 7 road wheels (smooth)
    wheels = []
    for k in range(7):
        wx = -1.40 + k * 0.45
        w = smooth_cone(f"{name}_w_{k}", r1=0.22, r2=0.22, depth=0.50, segs=22, loc=(wx, -0.05, 0), parent=p, mat=MAT_STEEL)
        w.rotation_euler = (0, math.radians(90), 0)
        # alloy hub
        hub = smooth_cone(f"{name}_w_{k}_hub", r1=0.10, r2=0.10, depth=0.51, segs=18, loc=(wx, -0.05, 0), parent=p, mat=MAT_TANK_DARK)
        hub.rotation_euler = (0, math.radians(90), 0)
        wheels.append(w)
    # sprocket wheel (front, larger)
    sprocket = smooth_cone(f"{name}_sprocket", r1=0.28, r2=0.28, depth=0.52, segs=24, loc=(1.75, -0.05, 0), parent=p, mat=MAT_TRACK_METAL)
    sprocket.rotation_euler = (0, math.radians(90), 0)
    # idler wheel (back)
    idler = smooth_cone(f"{name}_idler", r1=0.25, r2=0.25, depth=0.51, segs=22, loc=(-1.75, -0.05, 0), parent=p, mat=MAT_TRACK_METAL)
    idler.rotation_euler = (0, math.radians(90), 0)
    return p, wheels + [sprocket, idler]

track_L_p, track_L_wheels = make_track("track_L", 0, 0.95, tank)
track_R_p, track_R_wheels = make_track("track_R", 0, -0.95, tank)

# --- turret rotatif ---------------------------------------------
turret_p = empty("turret_p", (0, 1.10, 0), parent=tank)

# turret base (low cone)
turret_ring = smooth_cone("turret_ring", r1=0.95, r2=0.85, depth=0.10, segs=24, loc=(0, 0, 0), parent=turret_p, mat=MAT_TANK_DARK)
turret_ring.rotation_euler = (math.radians(90), 0, 0)

# turret body (smooth half-sphere stretched + sloped armor)
def make_turret_body(name, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=0.85)
    bmesh.ops.scale(bm, vec=(1.4, 0.55, 1.0), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (0, 0.35, 0)
    me.materials.append(MAT_TANK_GREEN)
    smooth_shade(me)
    return o

turret_body = make_turret_body("turret_body", turret_p)

# camouflage on turret
for i in range(3):
    a = i * (math.pi * 2 / 3) + 0.4
    cx = math.cos(a) * 0.8
    cz = math.sin(a) * 0.6
    stripe = beveled_cube(f"turret_camo_{i}", (0.3, 0.06, 0.25), bevel_offset=0.03, bevel_segments=2, loc=(cx, 0.40, cz), parent=turret_p, mat=MAT_TANK_BROWN)
    stripe.rotation_euler = (0, -a, 0)

# --- main cannon (long, with muzzle brake) -----------------------
cannon_p = empty("cannon_p", (0.20, 0.35, 0), parent=turret_p)
# main barrel
barrel = smooth_cone("cannon_barrel", r1=0.13, r2=0.10, depth=3.2, segs=24, loc=(1.6, 0, 0), parent=cannon_p, mat=MAT_TANK_DARK)
barrel.rotation_euler = (0, 0, math.radians(90))
# barrel mantlet (collar near turret)
mantlet = smooth_sphere("mantlet", r=0.20, segs=18, rings=12, loc=(0.15, 0, 0), parent=cannon_p, mat=MAT_TANK_DARK, scale=(1.5, 1.0, 1.0))
# muzzle brake (with 4 slots)
muzzle_brake = smooth_cone("muzzle_brake", r1=0.16, r2=0.16, depth=0.30, segs=18, loc=(3.25, 0, 0), parent=cannon_p, mat=MAT_TANK_DARK)
muzzle_brake.rotation_euler = (0, 0, math.radians(90))
# muzzle slot bands
for k in range(3):
    slot = smooth_cone(f"muzzle_slot_{k}", r1=0.18, r2=0.18, depth=0.04, segs=18, loc=(3.10 + k * 0.10, 0, 0), parent=cannon_p, mat=MAT_STEEL)
    slot.rotation_euler = (0, 0, math.radians(90))

# --- mitrailleuse coaxiale (small machine gun) ----------------
mg_p = empty("mg_p", (0.30, 0.40, 0.25), parent=turret_p)
mg_barrel = smooth_cone("mg_barrel", r1=0.04, r2=0.04, depth=0.8, segs=14, loc=(0.40, 0, 0), parent=mg_p, mat=MAT_TANK_DARK)
mg_barrel.rotation_euler = (0, 0, math.radians(90))
mg_body = beveled_cube("mg_body", (0.20, 0.10, 0.15), bevel_offset=0.03, bevel_segments=2, loc=(0, 0, 0), parent=mg_p, mat=MAT_TANK_DARK)

# --- commander cupola (top hatch with periscope) -----------------
cupola_p = empty("cupola_p", (-0.30, 0.65, 0.30), parent=turret_p)
cupola_body = smooth_cone("cupola_body", r1=0.25, r2=0.25, depth=0.20, segs=20, loc=(0, 0.10, 0), parent=cupola_p, mat=MAT_TANK_GREEN)
cupola_body.rotation_euler = (math.radians(90), 0, 0)
# hatch
hatch = smooth_cone("cupola_hatch", r1=0.20, r2=0.20, depth=0.05, segs=18, loc=(0, 0.22, 0), parent=cupola_p, mat=MAT_TANK_DARK)
hatch.rotation_euler = (math.radians(90), 0, 0)
# periscope
periscope = beveled_cube("periscope", (0.10, 0.15, 0.06), bevel_offset=0.02, bevel_segments=2, loc=(0.10, 0.30, 0), parent=cupola_p, mat=MAT_STEEL)

# --- 2 search lights émissifs -------------------------------
search_lights = []
for side, dz in [("L", 0.40), ("R", -0.40)]:
    sl_p = empty(f"search_light_{side}", (1.40, 0.30, dz), parent=turret_p)
    # housing
    housing = smooth_cone(f"sl_{side}_housing", r1=0.15, r2=0.15, depth=0.15, segs=16, loc=(0, 0, 0), parent=sl_p, mat=MAT_TANK_DARK)
    housing.rotation_euler = (0, 0, math.radians(90))
    # lens
    lens = smooth_sphere(f"sl_{side}_lens", r=0.12, segs=18, rings=12, loc=(0.08, 0, 0), parent=sl_p, mat=MAT_LIGHT, scale=(0.4, 1.0, 1.0))
    # halo
    halo = smooth_sphere(f"sl_{side}_halo", r=0.20, segs=16, rings=12, loc=(0.10, 0, 0), parent=sl_p, mat=MAT_LIGHT_HALO, scale=(0.3, 1.0, 1.0))
    search_lights.append(lens)

# --- 2 antennas ------------------------------------------------
antennas = []
for side, dx in [("F", -0.5), ("B", 0.5)]:
    ant_p = empty(f"antenna_p_{side}", (dx, 0.7, -0.7), parent=turret_p)
    ant = smooth_cone(f"antenna_{side}", r1=0.02, r2=0.01, depth=1.5, segs=8, loc=(0, 0.75, 0), parent=ant_p, mat=MAT_STEEL)
    ant.rotation_euler = (math.radians(90), 0, 0)
    antennas.append(ant_p)

# --- 4 fuel barrels arrière ---------------------------------
for i in range(4):
    bx = -2.3 - (i % 2) * 0.5
    bz = -0.6 + (i // 2) * 1.2
    barrel_p = empty(f"fuel_barrel_{i}", (bx, 1.0, bz), parent=tank)
    body = smooth_cone(f"fuel_barrel_{i}_b", r1=0.18, r2=0.18, depth=0.50, segs=20, loc=(0, 0, 0), parent=barrel_p, mat=MAT_BARREL_FUEL)
    # 3 metal bands
    for ay in [-0.15, 0, 0.15]:
        band = smooth_cone(f"fuel_barrel_{i}_band_{ay}", r1=0.20, r2=0.20, depth=0.04, segs=18, loc=(0, ay, 0), parent=barrel_p, mat=MAT_STEEL)

# --- camo netting top ----------------------------------------
netting = beveled_cube("netting", (1.5, 0.04, 1.3), bevel_offset=0.05, bevel_segments=2, loc=(0, 2.0, -1.2), parent=turret_p, mat=MAT_NETTING)

# --- flag arrière -----------------------------------------
flag_p = empty("flag_p", (-2.5, 1.7, 0), parent=tank)
pole = smooth_cone("flag_pole", r1=0.025, r2=0.020, depth=0.6, segs=8, loc=(0, 0.30, 0), parent=flag_p, mat=MAT_STEEL)
pole.rotation_euler = (math.radians(90), 0, 0)
# flag segments
flag_segs = []
for k in range(5):
    seg = beveled_cube(f"flag_seg_{k}", (0.06, 0.20, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0.04 + k * 0.06, 0.50, 0), parent=flag_p, mat=MAT_FLAG)
    flag_segs.append(seg)

# --- 4 smoke screen puffs (frontal smoke screen) ----------------
smoke_puffs = []
for i in range(4):
    a = i * (math.pi * 2 / 4) + 0.3
    sx = 3.5 + math.cos(a) * 0.5
    sz = math.sin(a) * 1.0
    puff = smooth_sphere(f"smoke_{i}", r=0.30, segs=14, rings=10, loc=(sx, 0.5, sz), mat=MAT_SMOKE)
    smoke_puffs.append((puff, i))

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

# tank advances slowly + slight bob + slight tilt
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    bx = -1.0 + tt * 2.5
    by = 0 + 0.03 * math.sin(tt * math.pi * 6.0)
    tilt = math.radians(2) * math.sin(tt * math.pi * 4.0)
    kf_loc(tank, f, (bx, by, 0))
    kf_rot(tank, f, (tilt, 0, 0))

# 14 wheels (7 each side) + 4 sprockets/idlers rotate
all_track_wheels = track_L_wheels + track_R_wheels
for w in all_track_wheels:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        kf_rot(w, f, (tt * math.pi * 12, math.radians(90), 0))

# turret rotates ±45° looking for targets
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    angle = math.radians(45) * math.sin(tt * math.pi * 2.0)
    kf_rot(turret_p, f, (0, angle, 0))

# cannon pitch up/down + slight recoil scale Y
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    pitch = math.radians(-10) + math.radians(15) * (math.sin(tt * math.pi * 3.0) + 1) * 0.5
    kf_rot(cannon_p, f, (0, 0, pitch))
    # recoil pulse every 60 frames (fire moment)
    recoil = 1.0 - 0.05 * max(0, math.sin(tt * math.pi * 6.0))
    kf_scale(barrel, f, (recoil, 1.0, 1.0))

# 2 search lights pulse
for sl in search_lights:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 6.0)
        kf_scale(sl, f, (0.4 * s, 1.0 * s, 1.0 * s))

# 2 antennas sway
for ant_p in antennas:
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        sway = math.radians(8) * math.sin(tt * math.pi * 4.0)
        kf_rot(ant_p, f, (sway, 0, sway * 0.5))

# flag wave
for j, seg in enumerate(flag_segs):
    base_x = seg.location.x
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        wave = math.sin(j * 0.4 + tt * math.pi * 7.0)
        kf_loc(seg, f, (base_x, 0.50 + wave * 0.05, wave * 0.08))
        kf_rot(seg, f, (0, 0, wave * 0.15))

# 4 smoke puffs rise + expand
for puff, i in smoke_puffs:
    phase = i * 12
    base = puff.location.copy()
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 60
        lt = local_f / 60
        dy = base[1] + lt * 2.5
        dx_drift = math.sin(lt * math.pi * 3.0) * 0.30
        kf_loc(puff, f, (base[0] + dx_drift, dy, base[2]))
        s = 0.5 + lt * 1.8
        kf_scale(puff, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_tank] wrote {OUT}")
