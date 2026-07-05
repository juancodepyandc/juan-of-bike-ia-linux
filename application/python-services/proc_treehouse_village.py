"""
proc_treehouse_village.py — 122e procédural AuroraIA, Phase F++++.

Village d'arbres habitat : 4 grands arbres avec maisons treehouses
en bois + 6 ponts suspendus reliant les maisons + 3 escaliers spirale
+ 8 lanternes émissives + 3 échelles + 4 drapeaux + 4 balcons + 4
cheminées avec fumée + 6 oiseaux + ciel coucher de soleil
+ sol forêt + 4 petits arbustes.

Animation :
- 4 drapeaux : flottent
- 8 lanternes : pulse
- 4 cheminées : fumée monte
- 6 ponts : sway léger
- 6 oiseaux : volent en arcs

Sortie : output/3d/pbr_treehouse_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_treehouse_proc.glb"))

random.seed(0xFADE12)

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
MAT_SKY_SUNSET = make_mat("sky_sunset", (0.95, 0.65, 0.30), roughness=1.0,
                            emi=(0.85, 0.55, 0.25), emi_strength=0.7)
MAT_SKY_TOP = make_mat("sky_top", (0.50, 0.30, 0.55), roughness=1.0,
                         emi=(0.40, 0.25, 0.50), emi_strength=0.5)
MAT_GROUND_FOREST = make_mat("ground", (0.15, 0.30, 0.10), roughness=0.95)
MAT_TRUNK = make_mat("trunk", (0.30, 0.20, 0.12), roughness=0.9)
MAT_BARK_DARK = make_mat("bark_dark", (0.18, 0.12, 0.08), roughness=0.95)
MAT_LEAVES = make_mat("leaves", (0.15, 0.55, 0.20), roughness=0.85)
MAT_HOUSE_WALL = make_mat("house_wall", (0.60, 0.35, 0.18), roughness=0.7)
MAT_HOUSE_DARK = make_mat("house_dark", (0.40, 0.22, 0.10), roughness=0.8)
MAT_HOUSE_ROOF = make_mat("house_roof", (0.45, 0.20, 0.10), roughness=0.7)
MAT_ROOF_TILE = make_mat("roof_tile", (0.55, 0.25, 0.15), roughness=0.7)
MAT_WINDOW = make_mat("window", (1.0, 0.85, 0.50), roughness=0.0, alpha=0.85,
                        emi=(1.0, 0.85, 0.45), emi_strength=5.0)
MAT_DOOR = make_mat("door", (0.45, 0.25, 0.12), roughness=0.7)
MAT_LANTERN = make_mat("lantern", (1.0, 0.70, 0.30), roughness=0.0, alpha=0.85,
                         emi=(1.0, 0.70, 0.30), emi_strength=7.0)
MAT_LANTERN_CASE = make_mat("lantern_case", (0.20, 0.15, 0.10), roughness=0.7)
MAT_BRIDGE_PLANK = make_mat("bridge_plank", (0.50, 0.30, 0.15), roughness=0.85)
MAT_ROPE = make_mat("rope", (0.65, 0.50, 0.30), roughness=0.85)
MAT_FLAG = make_mat("flag", (0.85, 0.20, 0.20), roughness=0.65,
                      emi=(0.40, 0.05, 0.05), emi_strength=0.3)
MAT_FLAG_BLUE = make_mat("flag_blue", (0.15, 0.30, 0.85), roughness=0.65,
                           emi=(0.05, 0.10, 0.40), emi_strength=0.3)
MAT_FLAG_GREEN = make_mat("flag_green", (0.15, 0.85, 0.30), roughness=0.65,
                            emi=(0.05, 0.40, 0.10), emi_strength=0.3)
MAT_CHIMNEY = make_mat("chimney", (0.35, 0.25, 0.18), roughness=0.85)
MAT_SMOKE = make_mat(
    "smoke", (0.55, 0.50, 0.45), roughness=1.0, alpha=0.6,
    emi=(0.30, 0.20, 0.15), emi_strength=0.4,
)
MAT_BIRD = make_mat("bird", (0.20, 0.15, 0.10), roughness=0.7)
MAT_SUN = make_mat("sun", (1.0, 0.55, 0.20), roughness=0.0,
                     emi=(1.0, 0.55, 0.20), emi_strength=7.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.65, 0.30), roughness=0.0, alpha=0.25,
                          emi=(1.0, 0.65, 0.30), emi_strength=2.5)
MAT_BUSH = make_mat("bush", (0.10, 0.40, 0.15), roughness=0.85)

# --- backdrop ---------------------------------------------------------------
sky_bot = cube("sky_bot", size=1.0, loc=(0, 16, 4), mat=MAT_SKY_SUNSET)
sky_bot.scale = (32, 0.1, 8)

sky_top = cube("sky_top", size=1.0, loc=(0, 16, 10), mat=MAT_SKY_TOP)
sky_top.scale = (32, 0.1, 8)

# setting sun
sun_p = empty("sun_p", (6.5, 14.0, 5.0))
sun = sphere("sun", r=1.2, segs=24, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo = sphere("sun_halo", r=2.4, segs=22, rings=16, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# ground (forest floor)
ground = cube("ground", size=1.0, loc=(0, -0.05, 0), mat=MAT_GROUND_FOREST)
ground.scale = (30, 0.1, 22)

# 8 small bushes
for i in range(8):
    bx = random.uniform(-12, 12)
    bz = random.uniform(-8, 8)
    bp = empty(f"bush_{i}", (bx, 0, bz))
    for j in range(4):
        ja = j * (math.pi * 2 / 4)
        b = sphere(f"bush_{i}_{j}", r=0.25, segs=10, rings=8, loc=(math.cos(ja) * 0.20, 0.25, math.sin(ja) * 0.20), parent=bp, mat=MAT_BUSH)
        b.scale = (1.0, 0.8, 1.0)

# --- 4 grands arbres avec maisons treehouses ------------------------------
trees = []
tree_data = [
    (-6.0, -2.0, 6.0),   # tree 0
    (5.5, 2.5, 7.0),    # tree 1
    (-5.0, 5.5, 5.5),   # tree 2
    (6.0, -3.0, 5.8),   # tree 3
]

def make_tree(name, x, z, trunk_h):
    p = empty(name, (x, 0, z))
    # trunk (5 cone segments curving slightly)
    for i in range(6):
        sx = math.sin(i * 0.25) * 0.1
        h = 0.5 + i * (trunk_h / 6)
        tr = cone(f"{name}_trunk_{i}", r1=0.50 - i * 0.05, r2=0.48 - i * 0.05, depth=trunk_h / 6, segs=10, loc=(sx, h, 0), parent=p, mat=MAT_TRUNK)
        tr.rotation_euler = (math.radians(90), 0, 0)
    # foliage : large cluster of leaves at top
    foliage_p = empty(f"{name}_foliage", (0, trunk_h + 0.5, 0), parent=p)
    for j in range(6):
        ja = j * (math.pi * 2 / 6) + random.uniform(-0.3, 0.3)
        fx = math.cos(ja) * 0.8 + random.uniform(-0.2, 0.2)
        fz = math.sin(ja) * 0.8 + random.uniform(-0.2, 0.2)
        fy = random.uniform(-0.3, 0.5)
        f = sphere(f"{name}_leaves_{j}", r=1.0, segs=18, rings=12, loc=(fx, fy, fz), parent=foliage_p, mat=MAT_LEAVES)
        f.scale = (1.3, 1.0, 1.3)
    return p

def make_treehouse(name, parent, y_offset, scale=1.0, roof_color=MAT_HOUSE_ROOF):
    p = empty(name, (0, y_offset, 0), parent=parent)
    # base platform extending around trunk
    base = cube(f"{name}_base", size=1.0, loc=(0, 0, 0), parent=p, mat=MAT_HOUSE_DARK)
    base.scale = (2.0 * scale, 0.1, 2.0 * scale)
    # walls (4 walls of a small house)
    wall_h = 1.0 * scale
    for side, x_off, z_off, sx, sz in [("F", 0, 0.85 * scale, 1.7 * scale, 0.08), ("B", 0, -0.85 * scale, 1.7 * scale, 0.08), ("L", -0.85 * scale, 0, 0.08, 1.7 * scale), ("R", 0.85 * scale, 0, 0.08, 1.7 * scale)]:
        w = cube(f"{name}_wall_{side}", size=1.0, loc=(x_off, wall_h / 2, z_off), parent=p, mat=MAT_HOUSE_WALL)
        w.scale = (sx, wall_h, sz)
    # roof (pyramid)
    roof = cone(f"{name}_roof", r1=1.4 * scale, r2=0.05, depth=1.2 * scale, segs=4, loc=(0, wall_h + 0.6 * scale, 0), parent=p, mat=roof_color)
    roof.rotation_euler = (math.radians(90), 0, math.radians(45))
    # window (glowing front)
    win = cube(f"{name}_window", size=1.0, loc=(0, wall_h / 2 + 0.1 * scale, 0.88 * scale), parent=p, mat=MAT_WINDOW)
    win.scale = (0.5 * scale, 0.45 * scale, 0.05)
    # door
    door = cube(f"{name}_door", size=1.0, loc=(0.85 * scale, wall_h / 2, 0), parent=p, mat=MAT_DOOR)
    door.scale = (0.04, 0.7 * scale, 0.35 * scale)
    # chimney
    chim_p = empty(f"{name}_chim_p", (0.5 * scale, wall_h + 0.7 * scale, -0.3 * scale), parent=p)
    chim = cube(f"{name}_chim", size=1.0, loc=(0, 0.3 * scale, 0), parent=chim_p, mat=MAT_CHIMNEY)
    chim.scale = (0.18 * scale, 0.7 * scale, 0.18 * scale)
    # balcony (small platform extending out front)
    balc = cube(f"{name}_balc", size=1.0, loc=(0, 0.05, 1.0 * scale), parent=p, mat=MAT_BRIDGE_PLANK)
    balc.scale = (1.5 * scale, 0.05, 0.4 * scale)
    # 2 balcony rails
    for side, dx in [("L", -0.7 * scale), ("R", 0.7 * scale)]:
        r1 = cube(f"{name}_rail_post_{side}", size=1.0, loc=(dx, 0.3, 1.18 * scale), parent=p, mat=MAT_TRUNK)
        r1.scale = (0.05, 0.5, 0.05)
    rail_top = cube(f"{name}_rail_top", size=1.0, loc=(0, 0.55, 1.18 * scale), parent=p, mat=MAT_TRUNK)
    rail_top.scale = (1.4 * scale, 0.04, 0.04)
    return p, chim_p

# build trees and houses
tree_objs = []
treehouse_chimneys = []
flag_objs = []
roof_colors = [MAT_HOUSE_ROOF, MAT_ROOF_TILE, MAT_HOUSE_ROOF, MAT_ROOF_TILE]
for i, (tx, tz, th) in enumerate(tree_data):
    tp = make_tree(f"tree_{i}", tx, tz, th)
    tree_objs.append((tp, tx, tz, th))
    # house mid-way up the trunk
    house_y = th - 1.5
    hp, chim_p = make_treehouse(f"house_{i}", tp, house_y, scale=1.0, roof_color=roof_colors[i])
    treehouse_chimneys.append(chim_p)
    # flag on top of house (offset slightly)
    flag_p = empty(f"flag_p_{i}", (0, house_y + 2.4, 0), parent=tp)
    pole = cone(f"flag_pole_{i}", r1=0.04, r2=0.03, depth=0.8, segs=6, loc=(0, 0.4, 0), parent=flag_p, mat=MAT_TRUNK)
    pole.rotation_euler = (math.radians(90), 0, 0)
    flag_mat = [MAT_FLAG, MAT_FLAG_BLUE, MAT_FLAG_GREEN, MAT_FLAG][i]
    # flag : 6 segments waving
    flag_segs = []
    for j in range(6):
        seg = cube(f"flag_{i}_{j}", size=1.0, loc=(j * 0.09 + 0.05, 0.75, 0), parent=flag_p, mat=flag_mat)
        seg.scale = (0.09, 0.25, 0.02)
        flag_segs.append(seg)
    flag_objs.append((flag_segs, i))

# --- 6 ponts suspendus reliant les maisons --------------------------------
# pairs : (tree_a, tree_b)
bridge_pairs = [(0, 1), (1, 3), (3, 0), (0, 2), (1, 2), (2, 3)]
bridges = []
for bi, (a, b) in enumerate(bridge_pairs):
    pa = tree_data[a]
    pb = tree_data[b]
    house_y_a = pa[2] - 1.5
    house_y_b = pb[2] - 1.5
    # midpoint + slight sag
    mx = (pa[0] + pb[0]) / 2
    mz = (pa[1] + pb[1]) / 2
    my = (house_y_a + house_y_b) / 2 - 0.5  # sag
    bp = empty(f"bridge_{bi}", (mx, my, mz))
    # compute direction
    dx = pb[0] - pa[0]
    dz = pb[1] - pa[1]
    length = math.sqrt(dx * dx + dz * dz) - 2.0  # subtract platform widths
    angle = math.atan2(dz, dx)
    bp.rotation_euler = (0, -angle, 0)
    # 10 planks across the bridge
    for k in range(10):
        kt = (k + 0.5) / 10
        kx = -length / 2 + kt * length
        # sag along Y (parabolic)
        ky = -0.3 * 4 * kt * (1 - kt)
        plank = cube(f"bridge_{bi}_plank_{k}", size=1.0, loc=(kx, ky, 0), parent=bp, mat=MAT_BRIDGE_PLANK)
        plank.scale = (0.10, 0.05, 0.7)
    # 2 ropes (one each side)
    for side, dz_off in [("L", 0.4), ("R", -0.4)]:
        # rope segments
        for k in range(10):
            kt = (k + 0.5) / 10
            kx = -length / 2 + kt * length
            ky = -0.3 * 4 * kt * (1 - kt) + 0.5
            r = cube(f"bridge_{bi}_rope_{side}_{k}", size=1.0, loc=(kx, ky, dz_off), parent=bp, mat=MAT_ROPE)
            r.scale = (length / 10 * 0.9, 0.03, 0.03)
        # vertical rope drops every 2 planks
        for k in range(5):
            kt = (k * 2 + 1) / 10
            kx = -length / 2 + kt * length
            ky_low = -0.3 * 4 * kt * (1 - kt)
            ky_high = ky_low + 0.5
            r = cube(f"bridge_{bi}_drop_{side}_{k}", size=1.0, loc=(kx, (ky_low + ky_high) / 2, dz_off), parent=bp, mat=MAT_ROPE)
            r.scale = (0.025, 0.5, 0.025)
    bridges.append(bp)

# --- 8 lanternes émissives -------------------------------------------------
lanterns = []
# place lanterns along trees and bridges
lantern_positions = [
    (-6.0, 5.5, -2.0),    # tree 0 area
    (-5.0, 4.0, -2.0),
    (5.5, 6.5, 2.5),     # tree 1
    (5.5, 4.5, 2.5),
    (-5.0, 5.0, 5.5),    # tree 2
    (-5.0, 3.5, 5.5),
    (6.0, 5.0, -3.0),    # tree 3
    (6.0, 3.5, -3.0),
]
for i, (lx, ly, lz) in enumerate(lantern_positions):
    lp = empty(f"lantern_{i}", (lx, ly, lz))
    # case (small box)
    case = cube(f"lantern_{i}_case", size=1.0, loc=(0, 0, 0), parent=lp, mat=MAT_LANTERN_CASE)
    case.scale = (0.15, 0.20, 0.15)
    # light orb inside
    light = sphere(f"lantern_{i}_light", r=0.12, segs=12, rings=8, loc=(0, 0, 0), parent=lp, mat=MAT_LANTERN)
    # top
    top = cone(f"lantern_{i}_top", r1=0.18, r2=0.0, depth=0.10, segs=4, loc=(0, 0.14, 0), parent=lp, mat=MAT_LANTERN_CASE)
    top.rotation_euler = (math.radians(90), 0, 0)
    # rope hanging
    rope = cone(f"lantern_{i}_rope", r1=0.015, r2=0.015, depth=0.4, segs=6, loc=(0, 0.34, 0), parent=lp, mat=MAT_ROPE)
    rope.rotation_euler = (math.radians(90), 0, 0)
    lanterns.append(light)

# --- 4 chimney smokes ------------------------------------------------------
chim_smokes = []
for ti, chim_p in enumerate(treehouse_chimneys):
    for k in range(3):
        py = 0.8 + k * 0.4
        pr = 0.18 + k * 0.06
        puff = sphere(f"chim_{ti}_smoke_{k}", r=pr, segs=12, rings=8, loc=(0, py, 0), parent=chim_p, mat=MAT_SMOKE)
        chim_smokes.append((puff, ti, k))

# --- 3 escaliers spirale autour d'arbre 0 ---------------------------------
spiral_p = empty("spiral_stair_p", (tree_data[0][0], 0, tree_data[0][1]))
for i in range(12):
    t = i / 11
    h = 0.3 + t * 4.0
    a = t * math.pi * 3
    sx = math.cos(a) * 0.75
    sz = math.sin(a) * 0.75
    step = cube(f"spiral_step_{i}", size=1.0, loc=(sx, h, sz), parent=spiral_p, mat=MAT_BRIDGE_PLANK)
    step.scale = (0.55, 0.04, 0.25)
    step.rotation_euler = (0, -a, 0)

# --- 3 échelles (one to tree 1, one tree 2, one tree 3) -------------------
for ti, (tx, tz, th) in enumerate(tree_data[1:], start=1):
    # ladder placed at the side of the trunk
    lad_p = empty(f"ladder_{ti}", (tx + 0.6, 0, tz))
    # 6 rungs
    for r in range(7):
        rung = cube(f"ladder_{ti}_r_{r}", size=1.0, loc=(0, 0.3 + r * 0.55, 0), parent=lad_p, mat=MAT_BRIDGE_PLANK)
        rung.scale = (0.40, 0.04, 0.05)
    # 2 side rails
    for side, dx in [("L", -0.18), ("R", 0.18)]:
        rail = cube(f"ladder_{ti}_rail_{side}", size=1.0, loc=(dx, 2.0, 0), parent=lad_p, mat=MAT_TRUNK)
        rail.scale = (0.05, 4.0, 0.05)

# --- 6 oiseaux flying ------------------------------------------------------
birds = []
for i in range(6):
    a = i * (math.pi * 2 / 6) + 0.3
    r = 8.0
    bx = math.cos(a) * r
    bz = math.sin(a) * r
    by = 10.0
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

# flags wave
for flag_segs, i in flag_objs:
    for k, seg in enumerate(flag_segs):
        for f in range(1, FRAMES + 1, 2):
            tt = (f - 1) / (FRAMES - 1)
            wave = math.sin(k * 0.5 + tt * math.pi * 7.0 + i * 0.6)
            kx = k * 0.09 + 0.05
            kz = wave * 0.14
            ky = 0.75 + math.cos(k * 0.5 + tt * math.pi * 7.0) * 0.05
            kf_loc(seg, f, (kx, ky, kz))
            kf_rot(seg, f, (0, 0, wave * 0.15))

# lanterns pulse
for i, light in enumerate(lanterns):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(light, f, (s, s, s))

# chimney smokes rise + reset
for puff, ti, level in chim_smokes:
    base_y = 0.8 + level * 0.4
    phase = ti * 10 + level * 5
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 60
        lt = local_f / 60
        dy = base_y + lt * 1.5
        dx = math.sin(lt * math.pi * 3.0) * 0.15
        kf_loc(puff, f, (dx, dy, 0))
        s = 0.5 + lt * 1.5
        kf_scale(puff, f, (s, s, s))

# bridges sway
for i, bp in enumerate(bridges):
    base_rot = bp.rotation_euler.copy()
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        sway = math.radians(2) * math.sin(tt * math.pi * 2.5 + i * 0.7)
        kf_rot(bp, f, (sway, base_rot[1], 0))

# birds orbit
for bp, a0, r, by in birds:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 2.0
        bx = math.cos(angle) * r
        bz = math.sin(angle) * r
        by_a = by + 0.4 * math.sin(tt * math.pi * 4.0 + a0)
        kf_loc(bp, f, (bx, by_a, bz))
        kf_rot(bp, f, (0, -angle + math.pi / 2, math.radians(15) * math.sin(tt * math.pi * 8.0)))

# sun halo breathe + sun pulse
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.12 * math.sin(tt * math.pi * 3.0)
    kf_scale(sun_halo, f, (s, s, s))
    sp = 1.0 + 0.04 * math.sin(tt * math.pi * 5.0)
    kf_scale(sun, f, (sp, sp, sp))

# trees foliage sway (subtle)
for tp, tx, tz, th in tree_objs:
    foliage_p = tp.children[6] if len(tp.children) > 6 else None
    # foliage_p is by name :
    foliage_obj = next((c for c in tp.children if "foliage" in c.name), None)
    if foliage_obj:
        for f in range(1, FRAMES + 1, 5):
            tt = (f - 1) / (FRAMES - 1)
            bend = math.radians(2) * math.sin(tt * math.pi * 2.0 + tx)
            kf_rot(foliage_obj, f, (bend, 0, bend * 0.5))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_treehouse] wrote {OUT}")
