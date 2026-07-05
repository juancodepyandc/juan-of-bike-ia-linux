"""
proc_cambodian_angkor_wat_temple.py — 273e procédural AuroraIA (138e qualité)
Cambodia Angkor Wat: 5-tower temple + 6 monks + banyan tree roots + Buddha statues + moats + Cambodia flag + 600 banyan leaves + 400 dragonflies
FIXES : 1 ground jungle stone + signature leaves + dragonflies
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB273)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in (bpy.data.meshes, bpy.data.materials, bpy.data.objects,
              bpy.data.cameras, bpy.data.lights, bpy.data.collections):
        for x in list(c):
            try: c.remove(x)
            except: pass

def mat(name, base=(0.8,0.8,0.8,1.0), metallic=0.0, roughness=0.5,
        emission=None, emission_strength=0.0, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = base
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = (*emission, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        m.blend_method = 'BLEND'
    return m

def smooth_shade(mesh):
    for poly in mesh.polygons:
        poly.use_smooth = True
    try:
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(40)
    except AttributeError:
        pass

def make_obj(name, bm, loc=(0,0,0), parent=None, mat_=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); smooth_shade(me)
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    if parent: obj.parent = parent
    if mat_: obj.data.materials.append(mat_)
    return obj

def beveled_cube(name, size_xyz, bevel_offset=0.04, bevel_segments=3, loc=(0,0,0), parent=None, mat_=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size_xyz, verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:],
                    offset=bevel_offset, segments=bevel_segments,
                    profile=0.5, affect='EDGES')
    return make_obj(name, bm, loc, parent, mat_)

def smooth_sphere(name, r=1.0, segs=24, rings=16, loc=(0,0,0), parent=None, mat_=None, scale=(1,1,1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    if scale != (1,1,1):
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    return make_obj(name, bm, loc, parent, mat_)

def smooth_cone(name, r1, r2, depth, segs=18, loc=(0,0,0), parent=None, mat_=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    return make_obj(name, bm, loc, parent, mat_)

def cyl(name, r, depth, segs=16, loc=(0,0,0), parent=None, mat_=None):
    return smooth_cone(name, r, r, depth, segs, loc, parent, mat_)

def empty(name, loc=(0,0,0), parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    if parent: e.parent = parent
    return e

reset()
scene = bpy.context.scene
scene.frame_start = 1; scene.frame_end = 180; scene.render.fps = 30

# Sky tropical sunrise Cambodia
M_SKY = mat("sky", (1.0, 0.65, 0.40, 1.0), 0.0, 0.7, emission=(1.0,0.65,0.40), emission_strength=2.2)
M_SKY_LOW = mat("sky_l", (0.85, 0.55, 0.55, 1.0), 0.0, 0.7, emission=(0.85,0.55,0.55), emission_strength=1.7)
M_SUN = mat("sun", (1.0, 0.80, 0.35, 1.0), 0.0, 0.1, emission=(1.0,0.80,0.35), emission_strength=22.0)

# Stone ground
M_STONE = mat("st", (0.55, 0.50, 0.42, 1.0), 0.0, 0.85, emission=(0.52,0.48,0.42), emission_strength=0.3)
M_STONE_DARK = mat("std", (0.38, 0.35, 0.28, 1.0), 0.0, 0.92)
M_STONE_LICHEN = mat("stl", (0.45, 0.55, 0.32, 1.0), 0.0, 0.85, emission=(0.42,0.52,0.30), emission_strength=0.3)
M_MOSS = mat("mo", (0.30, 0.55, 0.25, 1.0), 0.0, 0.85, emission=(0.28,0.52,0.25), emission_strength=0.3)
M_DIRT = mat("d", (0.42, 0.30, 0.18, 1.0), 0.0, 0.92)

# Temple stone (signature sandstone)
M_TEMPLE_SAND = mat("ts", (0.78, 0.68, 0.50, 1.0), 0.0, 0.75, emission=(0.75,0.65,0.48), emission_strength=0.4)
M_TEMPLE_DARK = mat("td", (0.55, 0.45, 0.32, 1.0), 0.0, 0.85)
M_TEMPLE_GOLD = mat("tg", (0.92, 0.72, 0.32, 1.0), 0.6, 0.30, emission=(0.88,0.70,0.32), emission_strength=1.0)

# Water/moat
M_WATER = mat("wt", (0.32, 0.55, 0.45, 1.0), 0.2, 0.20, emission=(0.30,0.52,0.42), emission_strength=1.2, alpha=0.78)
M_WATER_DEEP = mat("wtd", (0.18, 0.38, 0.32, 1.0), 0.2, 0.25, alpha=0.85)
M_LILY = mat("ly", (0.45, 0.78, 0.45, 1.0), 0.0, 0.55, emission=(0.42,0.75,0.45), emission_strength=0.4)
M_LOTUS_PINK = mat("lp", (0.95, 0.55, 0.75, 1.0), 0.0, 0.40, emission=(0.92,0.55,0.72), emission_strength=1.0)

# Banyan tree
M_BANYAN_TRUNK = mat("bt", (0.42, 0.28, 0.18, 1.0), 0.0, 0.85, emission=(0.40,0.28,0.18), emission_strength=0.2)
M_BANYAN_DARK = mat("btd", (0.25, 0.16, 0.10, 1.0), 0.0, 0.92)
M_BANYAN_LEAF = mat("bl", (0.30, 0.62, 0.28, 1.0), 0.0, 0.55, emission=(0.28,0.60,0.28), emission_strength=0.5)
M_BANYAN_LEAF_DARK = mat("bld", (0.20, 0.45, 0.20, 1.0), 0.0, 0.65)
M_ROOT = mat("rt", (0.32, 0.22, 0.15, 1.0), 0.0, 0.85)

# Monk
M_MONK_SKIN = mat("ms", (0.85, 0.65, 0.45, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.45), emission_strength=0.3)
M_ROBE_SAFFRON = mat("rs", (0.95, 0.55, 0.18, 1.0), 0.0, 0.55, emission=(0.92,0.55,0.18), emission_strength=0.7)
M_ROBE_SAFFRON_DARK = mat("rsd", (0.72, 0.40, 0.12, 1.0), 0.0, 0.65)
M_HEAD_SHAVED = mat("hs", (0.78, 0.55, 0.40, 1.0), 0.0, 0.65, emission=(0.75,0.55,0.40), emission_strength=0.3)

# Buddha statue
M_BUDDHA_STONE = mat("bs", (0.75, 0.65, 0.48, 1.0), 0.0, 0.75, emission=(0.72,0.62,0.48), emission_strength=0.4)
M_BUDDHA_GOLD = mat("bg", (0.95, 0.75, 0.25, 1.0), 0.7, 0.20, emission=(0.92,0.72,0.25), emission_strength=1.2)
M_BUDDHA_DARK = mat("bd", (0.45, 0.38, 0.25, 1.0), 0.0, 0.85)

# Eyes
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Cambodia flag
M_FLAG_BLUE = mat("fb", (0.18, 0.42, 0.78, 1.0), 0.0, 0.45, emission=(0.18,0.42,0.75), emission_strength=1.0)
M_FLAG_RED = mat("fr", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)

# Bell/incense
M_BELL = mat("be", (0.85, 0.65, 0.20, 1.0), 0.7, 0.30, emission=(0.82,0.62,0.20), emission_strength=0.6)
M_INCENSE = mat("ic", (0.18, 0.12, 0.10, 1.0), 0.0, 0.85)
M_INCENSE_TIP = mat("ict", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=5.0)

# Leaf particles
M_LEAF_GREEN = mat("lg", (0.30, 0.65, 0.28, 1.0), 0.0, 0.40, emission=(0.28,0.62,0.28), emission_strength=1.5)
M_LEAF_YELLOW = mat("ly2", (0.92, 0.85, 0.30, 1.0), 0.0, 0.40, emission=(0.88,0.82,0.30), emission_strength=1.8)
M_LEAF_GOLD = mat("lgl", (0.95, 0.75, 0.30, 1.0), 0.3, 0.30, emission=(0.92,0.72,0.30), emission_strength=2.0)
M_LEAF_BROWN = mat("lb", (0.65, 0.45, 0.20, 1.0), 0.0, 0.40, emission=(0.62,0.42,0.20), emission_strength=1.0)
LEAF_COLORS = [M_LEAF_GREEN, M_LEAF_YELLOW, M_LEAF_GOLD, M_LEAF_BROWN]

# Dragonfly
M_DF_BODY = mat("dfb", (0.30, 0.65, 0.65, 1.0), 0.4, 0.30, emission=(0.30,0.62,0.62), emission_strength=2.0)
M_DF_WING = mat("dfw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.10, emission=(0.92,0.92,0.92), emission_strength=2.5, alpha=0.50)
M_DF_BODY_BLUE = mat("dfbb", (0.20, 0.55, 0.85, 1.0), 0.4, 0.30, emission=(0.20,0.55,0.82), emission_strength=2.0)
M_DF_BODY_RED = mat("dfbr", (0.85, 0.30, 0.20, 1.0), 0.4, 0.30, emission=(0.82,0.30,0.20), emission_strength=2.0)
DF_COLORS = [M_DF_BODY, M_DF_BODY_BLUE, M_DF_BODY_RED]

# ============ SKY ============
sky = smooth_sphere("sky", r=300, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=260, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Sun
sun = smooth_sphere("sun", r=10, segs=24, rings=18, loc=(-50, 110, 30), mat_=M_SUN)
for sh in range(4):
    smooth_sphere(f"sun_h{sh}", r=10 + sh*1.2, segs=24, rings=18, loc=(-50, 110, 30), mat_=M_SUN)

# ============ ONE clean jungle stone ground ============
ground = beveled_cube("ground", (240, 240, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_STONE)
# Stone pavers (signature Angkor causeway)
for cbi in range(30):
    for cbj in range(80):
        bx = -20 + cbi * 1.3
        by = -50 + cbj * 1.3
        if random.random() > 0.3:
            beveled_cube(f"pv{cbi}_{cbj}", (1.1, 1.1, 0.10), bevel_offset=0.02,
                         loc=(bx, by, 0.10),
                         mat_=M_STONE if (cbi + cbj) % 2 else M_STONE_LICHEN)
# Moss patches
for mi in range(120):
    a = random.uniform(0, math.pi*2); rad = random.uniform(8, 100)
    smooth_sphere(f"mp{mi}", r=random.uniform(0.4, 0.9), segs=10, rings=6,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_MOSS if mi % 2 else M_STONE_LICHEN, scale=(1.3, 1.2, 0.20))
# Dirt patches
for di in range(40):
    smooth_sphere(f"di{di}", r=random.uniform(0.5, 1.0), segs=10, rings=6,
                  loc=(random.uniform(-100, 100), random.uniform(-100, 100), 0.10),
                  mat_=M_DIRT, scale=(1.4, 1.3, 0.20))

# ============ MOATS surrounding temple (signature water rectangle) ============
moat_e = empty("moat", (0, 0, 0))
# Outer moat (rectangular ring around temple)
for mi in range(4):
    angle = mi * math.pi / 2
    if mi % 2 == 0:
        # Long sides
        beveled_cube(f"mo{mi}", (100, 8, 0.30), bevel_offset=0.06,
                     loc=(0, math.sin(angle) * 45, 0.25), parent=moat_e, mat_=M_WATER)
        beveled_cube(f"mo{mi}_d", (98, 7, 0.20), bevel_offset=0.04,
                     loc=(0, math.sin(angle) * 45, 0.30), parent=moat_e, mat_=M_WATER_DEEP)
    else:
        # Short sides
        beveled_cube(f"mo{mi}", (8, 100, 0.30), bevel_offset=0.06,
                     loc=(math.cos(angle) * 45, 0, 0.25), parent=moat_e, mat_=M_WATER)
        beveled_cube(f"mo{mi}_d", (7, 98, 0.20), bevel_offset=0.04,
                     loc=(math.cos(angle) * 45, 0, 0.30), parent=moat_e, mat_=M_WATER_DEEP)
# Lily pads on moat (signature)
for li in range(30):
    angle_l = random.uniform(0, math.pi*2)
    rad_l = random.uniform(40, 48)
    lx_l = math.cos(angle_l) * rad_l; ly_l = math.sin(angle_l) * rad_l
    if abs(lx_l) > 40 or abs(ly_l) > 40:
        cyl(f"lily{li}", r=0.45, depth=0.04, segs=12,
            loc=(lx_l, ly_l, 0.45), mat_=M_LILY)
        # Lotus flower
        if random.random() > 0.5:
            for pp in range(5):
                ppa = (pp / 5.0) * math.pi * 2
                beveled_cube(f"lo{li}_{pp}", (0.05, 0.10, 0.06), bevel_offset=0.005,
                             loc=(lx_l + math.cos(ppa)*0.10, ly_l + math.sin(ppa)*0.10, 0.50),
                             mat_=M_LOTUS_PINK).rotation_euler = (0, 0, ppa)

# ============ ANGKOR WAT TEMPLE 5 TOWERS (signature) ============
def make_tower(name, loc, height, base_radius, parent=None):
    base = empty(name, loc, parent=parent)
    # Base square (tiered pyramidal)
    n_tiers = max(5, int(height / 2.5))
    for ti in range(n_tiers):
        tz = ti * (height / n_tiers)
        tr = base_radius * (1 - ti / n_tiers * 0.6)
        # Square tier
        beveled_cube(f"{name}_t{ti}", (tr*2, tr*2, height/n_tiers * 0.7), bevel_offset=0.10,
                     loc=(0, 0, tz + height/n_tiers/2), parent=base,
                     mat_=M_TEMPLE_SAND if ti % 2 == 0 else M_TEMPLE_DARK)
        # Decorative bands
        if ti < n_tiers - 1:
            beveled_cube(f"{name}_tb{ti}", (tr*2.1, tr*2.1, 0.15), bevel_offset=0.04,
                         loc=(0, 0, tz + height/n_tiers - 0.10), parent=base, mat_=M_TEMPLE_DARK)
    # Lotus bud top (signature)
    bud_e = empty(f"{name}_b", (0, 0, height), parent=base)
    # Lotus base
    smooth_sphere(f"{name}_b_base", r=base_radius*0.4, segs=18, rings=12, loc=(0, 0, 0),
                  parent=bud_e, mat_=M_TEMPLE_SAND, scale=(1, 1, 0.7))
    # Petals (signature lotus bud)
    for pi in range(8):
        pa = (pi / 8.0) * math.pi * 2
        pet_e = empty(f"{name}_pe{pi}", (0, 0, 0.3), parent=bud_e)
        pet_e.rotation_euler = (math.radians(20), 0, pa)
        beveled_cube(f"{name}_pe{pi}_p", (base_radius*0.25, 0.30, base_radius*1.2), bevel_offset=0.10,
                     loc=(0, 0, base_radius*0.5), parent=pet_e, mat_=M_TEMPLE_SAND)
    # Spire on top
    smooth_cone(f"{name}_sp", r1=base_radius*0.15, r2=0.05, depth=base_radius*0.7, segs=10,
                loc=(0, 0, base_radius*0.7 + base_radius*0.4), parent=bud_e, mat_=M_TEMPLE_GOLD)
    return base

temple_e = empty("temple", (0, 0, 0))
# Temple base platform
beveled_cube("tp_b", (28, 28, 1.5), bevel_offset=0.15, loc=(0, 0, 0.75),
             parent=temple_e, mat_=M_TEMPLE_SAND)
# Stairs front
for si in range(8):
    beveled_cube(f"tp_s{si}", (5, 0.8, 0.20), bevel_offset=0.05,
                 loc=(0, -14.5 - si*0.4, 0.10 + si*0.20), parent=temple_e, mat_=M_TEMPLE_SAND)
# Outer gallery walls
for wi in range(4):
    wa = wi * math.pi / 2
    if wi % 2 == 0:
        beveled_cube(f"gw{wi}", (26, 1, 4), bevel_offset=0.10,
                     loc=(0, math.sin(wa)*13, 2 + 0.75), parent=temple_e, mat_=M_TEMPLE_DARK)
    else:
        beveled_cube(f"gw{wi}", (1, 26, 4), bevel_offset=0.10,
                     loc=(math.cos(wa)*13, 0, 2 + 0.75), parent=temple_e, mat_=M_TEMPLE_DARK)
# Columns around gallery
for ci in range(16):
    ca = (ci / 16.0) * math.pi * 2
    cyl(f"col{ci}", r=0.30, depth=4.5, segs=10,
        loc=(math.cos(ca)*13, math.sin(ca)*13, 0.75 + 2.25), parent=temple_e, mat_=M_TEMPLE_SAND)
# Inner courtyard platform
beveled_cube("ic_p", (16, 16, 1), bevel_offset=0.10, loc=(0, 0, 2),
             parent=temple_e, mat_=M_TEMPLE_SAND)
# Second tier
beveled_cube("st_p", (10, 10, 1.5), bevel_offset=0.10, loc=(0, 0, 3.25),
             parent=temple_e, mat_=M_TEMPLE_DARK)
# 5 TOWERS (signature - 4 corners + 1 center taller)
make_tower("tw_c", (0, 0, 4), 18, 3, parent=temple_e)
make_tower("tw_nw", (-6, 6, 3), 12, 1.5, parent=temple_e)
make_tower("tw_ne", (6, 6, 3), 12, 1.5, parent=temple_e)
make_tower("tw_sw", (-6, -6, 3), 12, 1.5, parent=temple_e)
make_tower("tw_se", (6, -6, 3), 12, 1.5, parent=temple_e)

# ============ 6 MONKS (signature saffron robes) ============
def make_monk(name, loc, scale=1.0, facing=0, pose="standing"):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Saffron robe (signature - draped one shoulder)
    smooth_cone(f"{name}_ro", r1=0.32, r2=0.40, depth=1.2, segs=14, loc=(0, 0, 1.10),
                parent=base, mat_=M_ROBE_SAFFRON)
    # Cross-body draping fold
    beveled_cube(f"{name}_dr", (0.50, 0.10, 0.85), bevel_offset=0.05,
                 loc=(0, -0.30, 1.40), parent=base, mat_=M_ROBE_SAFFRON_DARK)
    # Right shoulder bare (signature)
    smooth_sphere(f"{name}_rs", r=0.18, segs=14, rings=10, loc=(0.32, 0, 1.60),
                  parent=base, mat_=M_MONK_SKIN)
    # Lower robe wrap
    cyl(f"{name}_w", r=0.40, depth=0.30, segs=14, loc=(0, 0, 0.65),
        parent=base, mat_=M_ROBE_SAFFRON_DARK)
    if pose == "standing":
        # Legs
        for side in (-1, 1):
            cyl(f"{name}_l{side}", r=0.10, depth=0.50, segs=10,
                loc=(side*0.13, 0, 0.55), parent=base, mat_=M_ROBE_SAFFRON)
        # Bare feet
        for side in (-1, 1):
            beveled_cube(f"{name}_f{side}", (0.10, 0.22, 0.05), bevel_offset=0.01,
                         loc=(side*0.13, 0.05, 0.03), parent=base, mat_=M_MONK_SKIN)
        # Arms (prayer hands signature)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_a{side_idx}", (side*0.28, 0, 1.55), parent=base)
            sh.rotation_euler = (math.radians(-90), 0, math.radians(side*30))
            cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.30, segs=10, loc=(0, 0, -0.18),
                parent=sh, mat_=M_ROBE_SAFFRON)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.48),
                parent=sh, mat_=M_MONK_SKIN)
        # Hands together
        smooth_sphere(f"{name}_pr", r=0.08, segs=12, rings=8, loc=(0, -0.30, 1.10),
                      parent=base, mat_=M_MONK_SKIN)
    elif pose == "sitting":
        # Crossed legs
        for side in (-1, 1):
            cyl(f"{name}_l{side}", r=0.12, depth=0.55, segs=10,
                loc=(side*0.28, 0.15, 0.30), parent=base, mat_=M_ROBE_SAFFRON).rotation_euler = (math.radians(80), 0, 0)
        # Arms on lap
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.30), parent=base)
            sh.rotation_euler = (math.radians(-100), 0, math.radians(side*40))
            cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.30, segs=10, loc=(0, 0, -0.18),
                parent=sh, mat_=M_ROBE_SAFFRON)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.50),
                parent=sh, mat_=M_MONK_SKIN)
    # Head (shaved signature)
    head_m_e = empty(f"{name}_he", (0, 0, 1.95 if pose == "standing" else 1.50), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_HEAD_SHAVED)
    # Eyes closed (meditation) signature - thin lines
    for side in (-1, 1):
        beveled_cube(f"{name}_ey{side}", (0.04, 0.04, 0.008), bevel_offset=0.005,
                     loc=(side*0.06, -0.15, 0.03), parent=head_m_e, mat_=M_EYE)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.04, loc=(side*0.18, 0, 0.05),
                      parent=head_m_e, mat_=M_MONK_SKIN)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_m_e}

monks = []
monk_pos = [
    (-12, -20, math.radians(0), "standing"),
    (-4, -22, math.radians(0), "standing"),
    (4, -22, math.radians(0), "standing"),
    (12, -20, math.radians(0), "standing"),
    (-8, -30, math.radians(0), "sitting"),
    (8, -30, math.radians(0), "sitting"),
]
for i, (mx, my, fac, pose) in enumerate(monk_pos):
    m = make_monk(f"mk{i}", (mx, my, 0 if pose == "standing" else 0.4), facing=fac, pose=pose)
    monks.append(m)

# ============ BANYAN TREES with ROOTS (signature) ============
def make_banyan(name, loc, scale=1.0):
    base = empty(name, loc)
    # Massive central trunk (irregular)
    for ti in range(6):
        tz = ti * 1.5
        smooth_sphere(f"{name}_t{ti}", r=1.5 - ti*0.10, segs=16, rings=12,
                      loc=(random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2), tz + 0.75),
                      parent=base, mat_=M_BANYAN_TRUNK, scale=(1, 1, 1.2))
    # Hanging roots (signature aerial roots)
    for ri in range(20):
        ra = (ri / 20.0) * math.pi * 2
        rax = math.cos(ra) * 1.0
        ray = math.sin(ra) * 1.0
        # Root strands hanging
        for rsi in range(8):
            rsz = 8 - rsi * 1.0
            cyl(f"{name}_r{ri}_{rsi}", r=0.06 - rsi*0.005, depth=1.0, segs=8,
                loc=(rax + math.sin(rsi*0.3)*0.05, ray + math.cos(rsi*0.3)*0.05, rsz),
                parent=base, mat_=M_ROOT)
    # Massive ground roots spreading
    for gri in range(12):
        gra = (gri / 12.0) * math.pi * 2
        for grsi in range(6):
            grx = math.cos(gra) * (1.5 + grsi*0.4)
            gry = math.sin(gra) * (1.5 + grsi*0.4)
            cyl(f"{name}_gr{gri}_{grsi}", r=0.25 - grsi*0.02, depth=0.5, segs=10,
                loc=(grx, gry, 0.20), parent=base, mat_=M_BANYAN_TRUNK).rotation_euler = (math.radians(90), 0, gra)
    # Canopy (massive)
    canopy_e = empty(f"{name}_ce", (0, 0, 11), parent=base)
    for ci in range(20):
        ca = random.uniform(0, math.pi*2); cr = random.uniform(2, 6)
        smooth_sphere(f"{name}_c{ci}", r=random.uniform(1.5, 3.0), segs=14, rings=10,
                      loc=(math.cos(ca)*cr, math.sin(ca)*cr, random.uniform(-1, 2)),
                      parent=canopy_e, mat_=M_BANYAN_LEAF if ci % 2 else M_BANYAN_LEAF_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "canopy": canopy_e}

banyans = []
banyan_pos = [(-35, -35), (35, -35), (-35, 35), (35, 35)]
for i, (bx, by) in enumerate(banyan_pos):
    b = make_banyan(f"by{i}", (bx, by, 0))
    banyans.append(b)

# Banyan roots OVERGROWING temple walls (signature Ta Prohm)
overgrowth_e = empty("overgrowth", (0, 18, 5))
for oi in range(15):
    oa = (oi / 15.0) * math.pi * 2
    or_x = math.cos(oa) * 13
    or_y = 0
    # Roots cascading down
    for osi in range(8):
        osz = -osi * 0.8
        cyl(f"og{oi}_{osi}", r=0.15, depth=0.8, segs=8,
            loc=(or_x + math.sin(osi*0.3)*0.30, math.sin(oa)*5, osz),
            parent=overgrowth_e, mat_=M_BANYAN_TRUNK)

# ============ BUDDHA STATUES (signature) ============
def make_buddha(name, loc, scale=1.0, size=1.0):
    base = empty(name, loc)
    # Lotus pedestal
    cyl(f"{name}_pd", r=size*0.7, depth=size*0.25, segs=18, loc=(0, 0, size*0.13),
        parent=base, mat_=M_BUDDHA_DARK)
    # Lotus petals
    for pi in range(12):
        pa = (pi / 12.0) * math.pi * 2
        beveled_cube(f"{name}_lp{pi}", (size*0.20, size*0.10, size*0.08), bevel_offset=0.02,
                     loc=(math.cos(pa)*size*0.65, math.sin(pa)*size*0.65, size*0.20),
                     parent=base, mat_=M_BUDDHA_GOLD).rotation_euler = (0, 0, pa)
    # Body (seated cross-legged)
    smooth_sphere(f"{name}_bo", r=size*0.45, segs=16, rings=12, loc=(0, 0, size*0.55),
                  parent=base, mat_=M_BUDDHA_STONE, scale=(1, 1, 0.85))
    # Lap (crossed legs)
    cyl(f"{name}_lap", r=size*0.65, depth=size*0.20, segs=18, loc=(0, 0, size*0.30),
        parent=base, mat_=M_BUDDHA_STONE)
    # Arms folded
    for side in (-1, 1):
        cyl(f"{name}_a{side}", r=size*0.10, depth=size*0.50, segs=10,
            loc=(side*size*0.35, 0, size*0.50), parent=base, mat_=M_BUDDHA_STONE).rotation_euler = (math.radians(90), 0, math.radians(side*40))
    # Hands in dhyana mudra (signature)
    smooth_sphere(f"{name}_hd", r=size*0.12, segs=12, rings=8, loc=(0, 0, size*0.35),
                  parent=base, mat_=M_BUDDHA_STONE)
    # Head
    head_b_e = empty(f"{name}_he", (0, 0, size*1.10), parent=base)
    smooth_sphere(f"{name}_h", r=size*0.22, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_b_e, mat_=M_BUDDHA_STONE)
    # USHNISHA top (signature wisdom bump)
    smooth_sphere(f"{name}_us", r=size*0.10, segs=14, rings=10, loc=(0, 0, size*0.22),
                  parent=head_b_e, mat_=M_BUDDHA_GOLD)
    # Hair curls (signature)
    for hi in range(30):
        ha = random.uniform(0, math.pi*2)
        he = random.uniform(0.3, 0.9)
        smooth_sphere(f"{name}_hr{hi}", r=size*0.025,
                      loc=(math.cos(ha)*math.sin(he)*size*0.22,
                           math.sin(ha)*math.sin(he)*size*0.22,
                           math.cos(he)*size*0.15),
                      parent=head_b_e, mat_=M_BUDDHA_DARK)
    # Closed serene eyes
    for side in (-1, 1):
        beveled_cube(f"{name}_ey{side}", (size*0.04, size*0.04, size*0.008), bevel_offset=0.005,
                     loc=(side*size*0.07, -size*0.18, size*0.03),
                     parent=head_b_e, mat_=M_BUDDHA_DARK)
    # Long ears (signature)
    for side in (-1, 1):
        cyl(f"{name}_er{side}", r=size*0.04, depth=size*0.20, segs=8,
            loc=(side*size*0.22, 0, -size*0.05), parent=head_b_e, mat_=M_BUDDHA_STONE)
    return base

for i, (bx, by, bs) in enumerate([(-15, 8, 1.2), (15, 8, 1.2), (0, -8, 1.5), (-22, -12, 1.0), (22, -12, 1.0)]):
    make_buddha(f"bd{i}", (bx, by, 0), size=bs)

# ============ CAMBODIA FLAG (signature Angkor Wat silhouette) ============
flag_e = empty("flag", (-55, 0, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_TEMPLE_DARK)
# 3 horizontal stripes (blue/red/blue with red wider)
beveled_cube("fl_b_t", (4, 0.05, 0.55), bevel_offset=0.04, loc=(2, 0, 10.5),
             parent=flag_e, mat_=M_FLAG_BLUE)
beveled_cube("fl_r", (4, 0.05, 1.10), bevel_offset=0.04, loc=(2, 0, 9.65),
             parent=flag_e, mat_=M_FLAG_RED)
beveled_cube("fl_b_b", (4, 0.05, 0.55), bevel_offset=0.04, loc=(2, 0, 8.80),
             parent=flag_e, mat_=M_FLAG_BLUE)
# White Angkor Wat silhouette on red stripe (signature)
silh_e = empty("fl_silh", (2, -0.05, 9.65), parent=flag_e)
# 3 tower silhouettes
for ti, (tx_s, th_s) in enumerate([(0, 0.85), (-0.40, 0.55), (0.40, 0.55)]):
    beveled_cube(f"fl_t{ti}", (0.15, 0.05, th_s), bevel_offset=0.02,
                 loc=(tx_s, 0, th_s/2 - 0.40), parent=silh_e, mat_=M_FLAG_WHITE)
    # Tower top spire
    smooth_cone(f"fl_t{ti}_s", r1=0.10, r2=0.02, depth=0.18, segs=8,
                loc=(tx_s, 0, th_s - 0.40 + 0.09), parent=silh_e, mat_=M_FLAG_WHITE)
# Base
beveled_cube("fl_bs", (1.20, 0.05, 0.15), bevel_offset=0.02, loc=(0, 0, -0.40),
             parent=silh_e, mat_=M_FLAG_WHITE)
flag_e["_phase"] = 0

# ============================================================
# 600 BANYAN LEAVES + 400 DRAGONFLIES (PARTICULES SIGNATURES)
# ============================================================
leaves = []
for i in range(600):
    px = random.uniform(-80, 80)
    py = random.uniform(-80, 80)
    pz = random.uniform(2, 20)
    l_col = random.choice(LEAF_COLORS)
    l_e = empty(f"lf{i}", (px, py, pz))
    # Leaf shape (oval)
    smooth_sphere(f"lf{i}_b", r=0.06, segs=10, rings=6, loc=(0, 0, 0),
                  parent=l_e, mat_=l_col, scale=(1, 0.3, 1.4))
    # Stem
    cyl(f"lf{i}_s", r=0.008, depth=0.04, segs=6, loc=(0, 0, -0.08),
        parent=l_e, mat_=l_col)
    l_e["_phase"] = random.uniform(0, math.pi*2)
    l_e["_base_x"] = px; l_e["_base_z"] = pz
    l_e["_drift"] = random.uniform(0.2, 0.6)
    l_e["_fall"] = random.uniform(0.6, 1.3)
    l_e["_swing"] = random.uniform(1.0, 2.5)
    leaves.append(l_e)

# 400 dragonflies
dragonflies = []
for i in range(400):
    px = random.uniform(-80, 80)
    py = random.uniform(-80, 80)
    pz = random.uniform(1, 12)
    df_e = empty(f"df{i}", (px, py, pz))
    df_col = random.choice(DF_COLORS)
    # Body (elongated)
    cyl(f"df{i}_b", r=0.025, depth=0.30, segs=8, loc=(0, 0, 0),
        parent=df_e, mat_=df_col).rotation_euler = (0, math.radians(90), 0)
    # Head
    smooth_sphere(f"df{i}_h", r=0.04, segs=8, rings=6, loc=(0.18, 0, 0),
                  parent=df_e, mat_=df_col)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"df{i}_e{side}", r=0.025, loc=(0.18, side*0.03, 0.02),
                      parent=df_e, mat_=M_EYE)
    # 4 wings (signature dragonfly)
    wing_e_l1 = empty(f"df{i}_wl1_e", (0.05, -0.04, 0.02), parent=df_e)
    wing_e_l2 = empty(f"df{i}_wl2_e", (-0.05, -0.04, 0.02), parent=df_e)
    wing_e_r1 = empty(f"df{i}_wr1_e", (0.05, 0.04, 0.02), parent=df_e)
    wing_e_r2 = empty(f"df{i}_wr2_e", (-0.05, 0.04, 0.02), parent=df_e)
    beveled_cube(f"df{i}_wl1", (0.06, 0.18, 0.005), bevel_offset=0.005, loc=(0, -0.10, 0),
                 parent=wing_e_l1, mat_=M_DF_WING)
    beveled_cube(f"df{i}_wl2", (0.05, 0.16, 0.005), bevel_offset=0.005, loc=(0, -0.09, 0),
                 parent=wing_e_l2, mat_=M_DF_WING)
    beveled_cube(f"df{i}_wr1", (0.06, 0.18, 0.005), bevel_offset=0.005, loc=(0, 0.10, 0),
                 parent=wing_e_r1, mat_=M_DF_WING)
    beveled_cube(f"df{i}_wr2", (0.05, 0.16, 0.005), bevel_offset=0.005, loc=(0, 0.09, 0),
                 parent=wing_e_r2, mat_=M_DF_WING)
    df_e["_phase"] = random.uniform(0, math.pi*2)
    df_e["_base_x"] = px; df_e["_base_y"] = py; df_e["_base_z"] = pz
    df_e["_speed"] = random.uniform(0.8, 2.0)
    df_e["_radius"] = random.uniform(2, 6)
    df_e["_wings"] = [wing_e_l1, wing_e_l2, wing_e_r1, wing_e_r2]
    dragonflies.append(df_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Monks sway (meditating)
for mk in monks:
    phase = mk["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        mk["root"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(2), 0,
                                       mk["root"].rotation_euler.z)
        mk["root"].keyframe_insert("rotation_euler", frame=f)
        mk["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3), 0, 0)
        mk["he"].keyframe_insert("rotation_euler", frame=f)

# Banyan canopies sway
for b in banyans:
    phase = b["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        b["canopy"].rotation_euler = (math.sin(t * 0.7 + phase) * math.radians(4),
                                        math.cos(t * 0.7 + phase) * math.radians(4), 0)
        b["canopy"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 leaves fall + swing
for l in leaves:
    phase = l["_phase"]; drift = l["_drift"]; fall = l["_fall"]; swing = l["_swing"]
    bx, bz = l["_base_x"], l["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.8 + t * drift
        z = bz - (t * fall) % 18
        l.location = (x, l.location.y, z)
        l.rotation_euler = (t * 1.5 + phase, math.sin(t * 2.0 + phase) * math.radians(25), t * 0.7 + phase)
        l.keyframe_insert("location", frame=f)
        l.keyframe_insert("rotation_euler", frame=f)

# 400 dragonflies fly with wing flap
for df in dragonflies:
    phase = df["_phase"]; speed = df["_speed"]; radius = df["_radius"]
    bx, by, bz = df["_base_x"], df["_base_y"], df["_base_z"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * radius
        y = by + math.sin(t * speed + phase) * radius
        z = bz + math.sin(t * speed * 1.5 + phase) * 1.5
        df.location = (x, y, z)
        df.rotation_euler = (0, 0, math.atan2(math.cos(t * speed + phase),
                                                -math.sin(t * speed + phase)))
        df.keyframe_insert("location", frame=f)
        df.keyframe_insert("rotation_euler", frame=f)
        # Wing flap (fast)
        wing_a = math.sin(t * 25.0 + phase) * math.radians(50)
        df["_wings"][0].rotation_euler = (0, wing_a, 0)
        df["_wings"][1].rotation_euler = (0, wing_a * 0.85, 0)
        df["_wings"][2].rotation_euler = (0, -wing_a, 0)
        df["_wings"][3].rotation_euler = (0, -wing_a * 0.85, 0)
        for wg in df["_wings"]:
            wg.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_cambodia_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_cambodian_angkor_wat_temple] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Cambodia Angkor Wat: Temple platform 28x28 + 8 stairs + 4 gallery walls + 16 columns + inner courtyard + 5 towers (center 18m + 4 corners 12m) each with multi-tier pyramidal base + 8 lotus petals + golden spire signature + rectangular moats with lily pads/lotus + 6 saffron monks (4 standing prayer + 2 sitting meditation) + 4 massive banyan trees with 20 hanging roots + 12 ground roots + canopy spheres + roots overgrowing temple walls (Ta Prohm signature) + 5 Buddha statues (lotus pedestal + crossed legs + ushnisha + hair curls + long ears + dhyana mudra hands) + Cambodia flag with Angkor silhouette + 600 banyan leaves + 400 dragonflies (4 wings)")
print("🦋 FIXES: 1 jungle stone ground + 600 banyan leaves + 400 dragonflies signature mandatory 🦋")
