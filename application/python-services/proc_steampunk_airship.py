"""
proc_steampunk_airship.py — 119e procédural AuroraIA, Phase F++++.

Aéronef steampunk : ballon ovale en bois + 8 lattes métalliques
horizontales + gondole-cabine en bois ornée + 1 hélice avant tournante
+ 2 propulseurs latéraux à vapeur + 4 cheminées avec fumée + ancre +
3 cordes + drapeau + 2 ailes mécaniques + ciel nuageux + 3 oiseaux
+ 8 hublots cabine émissifs + lanterne avant.

Animation :
- hélice avant : rotation rapide Z
- 2 hélices latérales : rotation Y
- 4 cheminées : fumée monte (10 puffs offset)
- drapeau : flotte sin wave
- ballon : bob Y lente
- ailes : sway up/down
- oiseaux : orbites
- hublots cabine : cycle couleurs subtle

Sortie : output/3d/pbr_airship_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_airship_proc.glb"))

random.seed(0xA1F511)

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
MAT_SKY = make_mat("sky", (0.65, 0.78, 0.92), roughness=1.0,
                    emi=(0.45, 0.62, 0.85), emi_strength=0.5)
MAT_CLOUD = make_mat("cloud", (0.95, 0.97, 1.0), roughness=1.0, alpha=0.9,
                      emi=(0.85, 0.90, 0.95), emi_strength=0.3)
MAT_BALLOON_WOOD = make_mat("balloon_wood", (0.55, 0.30, 0.15), roughness=0.75)
MAT_BALLOON_PLANK = make_mat("balloon_plank", (0.40, 0.22, 0.12), roughness=0.8)
MAT_METAL_BAND = make_mat("metal_band", (0.55, 0.45, 0.30), metallic=0.8, roughness=0.4,
                            emi=(0.15, 0.10, 0.05), emi_strength=0.2)
MAT_BRASS = make_mat("brass", (1.0, 0.75, 0.30), metallic=0.95, roughness=0.20,
                      emi=(0.50, 0.35, 0.10), emi_strength=0.5)
MAT_BRASS_DARK = make_mat("brass_dark", (0.55, 0.40, 0.15), metallic=0.85, roughness=0.4)
MAT_GONDOLA = make_mat("gondola", (0.40, 0.20, 0.12), roughness=0.7)
MAT_GONDOLA_TRIM = make_mat("gondola_trim", (0.65, 0.50, 0.25), metallic=0.7, roughness=0.4,
                              emi=(0.30, 0.20, 0.05), emi_strength=0.3)
MAT_PROPELLER = make_mat("propeller", (0.30, 0.20, 0.12), roughness=0.8)
MAT_PROPELLER_TIP = make_mat("prop_tip", (0.85, 0.55, 0.20), metallic=0.7, roughness=0.3)
MAT_STEAM_PIPE = make_mat("steam_pipe", (0.40, 0.30, 0.18), metallic=0.7, roughness=0.5)
MAT_CHIMNEY = make_mat("chimney", (0.20, 0.18, 0.16), roughness=0.85)
MAT_SMOKE = make_mat(
    "smoke", (0.40, 0.40, 0.42), roughness=1.0, alpha=0.65,
    emi=(0.30, 0.30, 0.32), emi_strength=0.4,
)
MAT_FLAG = make_mat("flag", (0.85, 0.15, 0.10), roughness=0.65,
                     emi=(0.40, 0.05, 0.05), emi_strength=0.3)
MAT_FLAG_POLE = make_mat("flag_pole", (0.30, 0.20, 0.10), roughness=0.6)
MAT_ROPE = make_mat("rope", (0.65, 0.50, 0.30), roughness=0.85)
MAT_ANCHOR = make_mat("anchor", (0.30, 0.25, 0.20), metallic=0.8, roughness=0.55)
MAT_WING = make_mat("wing_metal", (0.55, 0.45, 0.30), metallic=0.7, roughness=0.5)
MAT_WINDOW = make_mat("window", (1.0, 0.85, 0.50), roughness=0.0, alpha=0.85,
                        emi=(1.0, 0.85, 0.45), emi_strength=4.0)
MAT_LANTERN = make_mat("lantern", (1.0, 0.7, 0.30), roughness=0.0, alpha=0.85,
                         emi=(1.0, 0.7, 0.30), emi_strength=6.0)
MAT_BIRD = make_mat("bird_silhouette", (0.15, 0.10, 0.10), roughness=0.7)

# --- backdrop : sky and clouds ----------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 16, 5), mat=MAT_SKY)
sky.scale = (32, 0.1, 14)

# 8 clouds at various positions
for i in range(8):
    cx = -14 + i * 4 + random.uniform(-1, 1)
    cz = random.uniform(2, 10)
    cy = 14 + random.uniform(-0.5, 0.5)
    cl = sphere(f"cloud_{i}", r=random.uniform(1.0, 1.8), segs=14, rings=10, loc=(cx, cy, cz), mat=MAT_CLOUD)
    cl.scale = (1.6, 0.55, 1.1)

# --- main airship -----------------------------------------------------------
ship = empty("ship", (0, 5.5, 0))

# balloon : large oval (wooden, planked)
balloon_p = empty("balloon", (0, 1.0, 0), parent=ship)
balloon = sphere("balloon_main", r=2.6, segs=32, rings=18, loc=(0, 0, 0), parent=balloon_p, mat=MAT_BALLOON_WOOD)
balloon.scale = (1.6, 1.0, 1.0)

# 8 horizontal metal bands (ring around the balloon)
for i in range(8):
    band_x = -3.2 + i * 0.95
    band_r = 2.6 * math.sqrt(max(0, 1.0 - (band_x / 4.16) ** 2))
    if band_r < 0.3:
        continue
    band = cone(f"balloon_band_{i}", r1=band_r * 1.04, r2=band_r * 1.04, depth=0.08, segs=20, loc=(band_x, 0, 0), parent=balloon_p, mat=MAT_METAL_BAND)
    band.rotation_euler = (0, math.radians(90), 0)

# 6 vertical wooden plank ribs
for i in range(6):
    angle = i * (math.pi * 2 / 6)
    plank_p = empty(f"plank_p_{i}", (0, 0, 0), parent=balloon_p)
    plank_p.rotation_euler = (angle, 0, 0)
    plank = cube(f"plank_{i}", size=1.0, loc=(0, 0, 2.55), parent=plank_p, mat=MAT_BALLOON_PLANK)
    plank.scale = (4.0, 0.05, 0.20)

# brass nose cone at front
nose = cone("nose_cone", r1=0.5, r2=0.0, depth=1.2, segs=12, loc=(4.0, 0, 0), parent=balloon_p, mat=MAT_BRASS)
nose.rotation_euler = (0, math.radians(90), 0)

# brass tail cone
tail_cone = cone("tail_cone", r1=0.4, r2=0.0, depth=1.0, segs=12, loc=(-4.0, 0, 0), parent=balloon_p, mat=MAT_BRASS)
tail_cone.rotation_euler = (0, math.radians(-90), 0)

# 2 tail fins (vertical and horizontal stabilizers)
for axis, name_suf, x_off in [("v", "vfin", 0.6), ("h", "hfin", 0.6)]:
    if axis == "v":
        fin = cube(f"tail_{name_suf}", size=1.0, loc=(-3.8 + x_off, 0.6, 0), parent=balloon_p, mat=MAT_BALLOON_PLANK)
        fin.scale = (0.5, 0.8, 0.04)
    else:
        fin = cube(f"tail_{name_suf}", size=1.0, loc=(-3.8 + x_off, 0, 0.6), parent=balloon_p, mat=MAT_BALLOON_PLANK)
        fin.scale = (0.5, 0.04, 0.8)
# rear small propeller for stabilization
rear_prop_p = empty("rear_prop_p", (-4.6, 0, 0), parent=balloon_p)
for blade_i in range(3):
    ba = blade_i * (math.pi * 2 / 3)
    bl = cube(f"rear_blade_{blade_i}", size=1.0, loc=(0, math.cos(ba) * 0.35, math.sin(ba) * 0.35), parent=rear_prop_p, mat=MAT_PROPELLER)
    bl.scale = (0.06, 0.05, 0.3)
    bl.rotation_euler = (ba, 0, 0)

# --- gondola (cabin) below balloon -----------------------------------------
gondola = empty("gondola", (0, -2.2, 0), parent=ship)
body = cube("gondola_body", size=1.0, loc=(0, 0, 0), parent=gondola, mat=MAT_GONDOLA)
body.scale = (3.5, 0.7, 1.2)
# rounded ends (2 half-spheres)
for side, dx in [("F", 1.75), ("B", -1.75)]:
    end = sphere(f"gondola_end_{side}", r=0.6, segs=18, rings=12, loc=(dx, 0, 0), parent=gondola, mat=MAT_GONDOLA)
    end.scale = (0.5, 1.0, 1.0)
# trim band
trim_top = cube("gondola_trim_top", size=1.0, loc=(0, 0.5, 0), parent=gondola, mat=MAT_GONDOLA_TRIM)
trim_top.scale = (3.6, 0.08, 1.25)
trim_bot = cube("gondola_trim_bot", size=1.0, loc=(0, -0.5, 0), parent=gondola, mat=MAT_GONDOLA_TRIM)
trim_bot.scale = (3.6, 0.08, 1.25)

# 8 cabin windows (4 each side)
windows = []
for side, dz in [("L", 0.62), ("R", -0.62)]:
    for i in range(4):
        wx = -1.4 + i * 0.95
        win = cube(f"window_{side}_{i}", size=1.0, loc=(wx, 0.05, dz), parent=gondola, mat=MAT_WINDOW)
        win.scale = (0.30, 0.30, 0.02)
        windows.append((win, i, side))

# front lantern (glowing)
lantern_front = sphere("lantern_front", r=0.18, segs=14, rings=10, loc=(2.3, 0.3, 0), parent=gondola, mat=MAT_LANTERN)

# --- 4 cheminées (chimneys) on top of gondola ------------------------------
chimneys = []
chimney_data = [(-1.2, 0), (-0.4, 0), (0.4, 0), (1.2, 0)]
smoke_puffs = []
for i, (cx, cz) in enumerate(chimney_data):
    c_p = empty(f"chim_p_{i}", (cx, 0.7, cz), parent=gondola)
    chim = cone(f"chim_{i}", r1=0.10, r2=0.12, depth=0.6, segs=10, loc=(0, 0.3, 0), parent=c_p, mat=MAT_CHIMNEY)
    chim.rotation_euler = (math.radians(90), 0, 0)
    # rim (brass)
    rim = cone(f"chim_rim_{i}", r1=0.14, r2=0.14, depth=0.08, segs=10, loc=(0, 0.6, 0), parent=c_p, mat=MAT_BRASS)
    rim.rotation_euler = (math.radians(90), 0, 0)
    chimneys.append(c_p)
    # 4 smoke puffs rising above each chimney
    for k in range(4):
        py = 0.75 + k * 0.4
        pr = 0.18 + k * 0.06
        puff = sphere(f"smoke_{i}_{k}", r=pr, segs=12, rings=8, loc=(0, py, 0), parent=c_p, mat=MAT_SMOKE)
        smoke_puffs.append((puff, i, k))

# --- propellers ------------------------------------------------------------
# front main propeller (rotates on X)
front_prop_p = empty("front_prop_p", (2.5, 0.3, 0), parent=gondola)
front_prop_p.rotation_euler = (0, 0, 0)
# 4 blades
for i in range(4):
    ba = i * (math.pi * 2 / 4)
    bl = cube(f"front_blade_{i}", size=1.0, loc=(0.1, math.cos(ba) * 0.55, math.sin(ba) * 0.55), parent=front_prop_p, mat=MAT_PROPELLER)
    bl.scale = (0.05, 0.08, 0.55)
    bl.rotation_euler = (ba, 0, 0)
    # tip
    tip = cube(f"front_tip_{i}", size=1.0, loc=(0.1, math.cos(ba) * 1.0, math.sin(ba) * 1.0), parent=front_prop_p, mat=MAT_PROPELLER_TIP)
    tip.scale = (0.07, 0.03, 0.12)
    tip.rotation_euler = (ba, 0, 0)
# hub
hub = sphere("front_hub", r=0.20, segs=14, rings=10, loc=(0.1, 0, 0), parent=front_prop_p, mat=MAT_BRASS)

# 2 side propellers (each on its own pylon)
side_props = []
for side, dz in [("L", 1.0), ("R", -1.0)]:
    pyl = cube(f"pylon_{side}", size=1.0, loc=(0, 0.1, dz), parent=gondola, mat=MAT_BRASS_DARK)
    pyl.scale = (0.3, 0.20, 0.10)
    prop_p = empty(f"side_prop_p_{side}", (0, 0.1, dz + (0.18 if side == "L" else -0.18)), parent=gondola)
    for i in range(4):
        ba = i * (math.pi * 2 / 4)
        bl = cube(f"side_blade_{side}_{i}", size=1.0, loc=(0, math.cos(ba) * 0.35, math.sin(ba) * 0.35 if side == "L" else -math.sin(ba) * 0.35), parent=prop_p, mat=MAT_PROPELLER)
        bl.scale = (0.04, 0.05, 0.35)
        bl.rotation_euler = (ba, 0, 0)
    side_props.append(prop_p)

# 2 steam pipes (under chimneys, leading to side props)
for side, dz in [("L", 0.45), ("R", -0.45)]:
    pipe = cone(f"steam_pipe_{side}", r1=0.06, r2=0.06, depth=0.7, segs=8, loc=(-0.3, 0.35, dz), parent=gondola, mat=MAT_STEAM_PIPE)
    pipe.rotation_euler = (math.radians(70), 0, 0)

# --- 2 mechanical wings ---------------------------------------------------
wings = []
for side, dz in [("L", 1.0), ("R", -1.0)]:
    wp = empty(f"wing_p_{side}", (0, 0.3, dz), parent=gondola)
    wing = cube(f"wing_{side}", size=1.0, loc=(0, 0, dz * 0.5), parent=wp, mat=MAT_WING)
    wing.scale = (1.4, 0.04, 0.6)
    # 3 ribs (cubes)
    for i in range(3):
        rib = cube(f"wing_{side}_rib_{i}", size=1.0, loc=(-0.6 + i * 0.6, 0.03, dz * 0.5), parent=wp, mat=MAT_BRASS_DARK)
        rib.scale = (0.04, 0.06, 0.6)
    wings.append(wp)

# --- 3 ropes from balloon to gondola ---------------------------------------
for i, dx in enumerate([-1.5, 0, 1.5]):
    rope = cone(f"rope_{i}", r1=0.035, r2=0.035, depth=2.0, segs=6, loc=(dx, 4.5, 0), parent=ship, mat=MAT_ROPE)
    rope.rotation_euler = (math.radians(90), 0, 0)

# --- anchor hanging below --------------------------------------------------
anchor_p = empty("anchor", (0, -3.3, 0), parent=ship)
# rope from gondola to anchor
arope = cone("arope", r1=0.025, r2=0.025, depth=0.6, segs=6, loc=(0, 0.5, 0), parent=anchor_p, mat=MAT_ROPE)
arope.rotation_euler = (math.radians(90), 0, 0)
# anchor body
ab = cube("anchor_body", size=1.0, loc=(0, 0, 0), parent=anchor_p, mat=MAT_ANCHOR)
ab.scale = (0.08, 0.6, 0.08)
# anchor arms
for side, dx in [("L", -0.30), ("R", 0.30)]:
    arm = cone(f"anchor_arm_{side}", r1=0.06, r2=0.04, depth=0.4, segs=6, loc=(dx, -0.10, 0), parent=anchor_p, mat=MAT_ANCHOR)
    arm.rotation_euler = (0, 0, math.radians(60 if side == "L" else -60))
# ring at top
ring = cone("anchor_ring", r1=0.08, r2=0.08, depth=0.05, segs=10, loc=(0, 0.35, 0), parent=anchor_p, mat=MAT_ANCHOR)
ring.rotation_euler = (math.radians(90), 0, 0)

# --- flag on top of balloon ----------------------------------------------
flag_p = empty("flag", (0, 2.8, 0), parent=ship)
pole = cone("flag_pole", r1=0.05, r2=0.04, depth=1.5, segs=6, loc=(0, 0.75, 0), parent=flag_p, mat=MAT_FLAG_POLE)
pole.rotation_euler = (math.radians(90), 0, 0)
# flag itself (10 segments side-by-side to animate as wave)
flag_segs = []
for i in range(10):
    fs = cube(f"flag_seg_{i}", size=1.0, loc=(i * 0.10 + 0.05, 1.30, 0), parent=flag_p, mat=MAT_FLAG)
    fs.scale = (0.10, 0.35, 0.02)
    flag_segs.append(fs)

# --- 3 oiseaux silhouettes -------------------------------------------------
birds = []
for i in range(3):
    a = i * (math.pi * 2 / 3) + 0.5
    r = 7.0
    bx = math.cos(a) * r + 1
    bz = math.sin(a) * r
    by = 11.0 + random.uniform(-0.5, 0.5)
    bp = empty(f"bird_{i}", (bx, by, bz))
    body = sphere(f"bird_{i}_body", r=0.10, segs=8, rings=6, loc=(0, 0, 0), parent=bp, mat=MAT_BIRD)
    body.scale = (1.5, 0.6, 1.0)
    for side, xx in (("L", -0.25), ("R", 0.25)):
        w = cube(f"bird_{i}_w_{side}", size=1.0, loc=(xx, 0, 0), parent=bp, mat=MAT_BIRD)
        w.scale = (0.20, 0.02, 0.10)
    birds.append((bp, a, r, by))

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

# ship bob
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    dy = 5.5 + 0.3 * math.sin(tt * math.pi * 2.0)
    tilt = math.radians(2) * math.sin(tt * math.pi * 1.5)
    kf_loc(ship, f, (0, dy, 0))
    kf_rot(ship, f, (0, 0, tilt))

# front propeller : rotation X (spinning fast)
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(front_prop_p, f, (tt * math.pi * 30, 0, 0))

# rear propeller : rotation X
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(rear_prop_p, f, (tt * math.pi * 24, 0, 0))

# side propellers : also rotation X
for prop in side_props:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        kf_rot(prop, f, (tt * math.pi * 26, 0, 0))

# smoke puffs : rise + fade
for puff, chim_i, level in smoke_puffs:
    base_y = 0.75 + level * 0.4
    phase = chim_i * 8 + level * 5
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 60
        lt = local_f / 60
        dy = base_y + lt * 1.5
        dx = math.sin(lt * math.pi * 4) * 0.15
        kf_loc(puff, f, (dx, dy, 0))
        s = 0.5 + lt * 1.5
        kf_scale(puff, f, (s, s, s))

# flag wave : each segment offset
for i, seg in enumerate(flag_segs):
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        wave = math.sin(i * 0.4 + tt * math.pi * 6.0)
        dz = wave * 0.20
        ty = math.cos(i * 0.4 + tt * math.pi * 6.0) * 0.10
        kf_loc(seg, f, (i * 0.10 + 0.05, 1.30 + ty, dz))
        kf_rot(seg, f, (0, 0, wave * 0.2))

# wings sway
for i, wp in enumerate(wings):
    phase = i * 0.5
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        wave = math.radians(8) * math.sin(tt * math.pi * 4.0 + phase)
        kf_rot(wp, f, (wave, 0, 0))

# birds orbit
for bp, a0, r, by in birds:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 2.0
        bx = math.cos(angle) * r + 1
        bz = math.sin(angle) * r
        by_a = by + 0.3 * math.sin(tt * math.pi * 4.0 + a0 * 2)
        kf_loc(bp, f, (bx, by_a, bz))
        kf_rot(bp, f, (0, -angle + math.pi / 2, math.radians(15) * math.sin(tt * math.pi * 8.0)))

# windows pulse subtle
for win, idx, side in windows:
    phase = idx * 0.4 + (0.5 if side == "R" else 0)
    for f in range(1, FRAMES + 1, 5):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.06 * math.sin(tt * math.pi * 4.0 + phase)
        kf_scale(win, f, (0.30 * s, 0.30 * s, 0.02))

# lantern pulse
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.15 * math.sin(tt * math.pi * 5.0)
    kf_scale(lantern_front, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_airship] wrote {OUT}")
