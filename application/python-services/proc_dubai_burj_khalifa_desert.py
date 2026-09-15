"""
proc_dubai_burj_khalifa_desert.py — 252e procédural AuroraIA (117e qualité)
Dubai Burj Khalifa desert night: 800m skyscraper + Palm Jumeirah + 6 luxury cars + 4 camels + Bedouin tent + 8 tourists + dancing fountains + helicopter + Gold Souk + 600 gold sand + 400 lasers
FIXES : 1 ground + 600 sand grains + 400 lasers rotating (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB252)

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

# Night sky Dubai
M_SKY = mat("sky", (0.04, 0.04, 0.15, 1.0), 0.0, 0.7, emission=(0.05,0.05,0.18), emission_strength=0.7)
M_STAR_D = mat("star", (1.0, 0.95, 0.85, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.85), emission_strength=8.0)
M_MOON_D = mat("moon", (0.95, 0.92, 0.85, 1.0), 0.0, 0.20, emission=(0.92,0.88,0.82), emission_strength=4.0)

# Ground
M_SAND_GOLDEN_D = mat("sand", (0.85, 0.72, 0.40, 1.0), 0.0, 0.55, emission=(0.80,0.68,0.40), emission_strength=0.5)
M_SAND_DARK_D = mat("sand_d", (0.62, 0.50, 0.28, 1.0), 0.0, 0.75)
M_CONCRETE = mat("concrete", (0.55, 0.55, 0.55, 1.0), 0.0, 0.75, emission=(0.50,0.50,0.50), emission_strength=0.4)
M_ASPHALT = mat("asphalt", (0.18, 0.18, 0.20, 1.0), 0.0, 0.85, emission=(0.18,0.18,0.20), emission_strength=0.3)

# Burj Khalifa (signature glass + steel)
M_GLASS_BLUE = mat("glass_b", (0.18, 0.42, 0.78, 1.0), 0.4, 0.20, emission=(0.30,0.55,0.92), emission_strength=3.5, alpha=0.85)
M_GLASS_LIGHT = mat("glass_l", (0.55, 0.78, 0.95, 1.0), 0.4, 0.20, emission=(0.55,0.82,1.0), emission_strength=4.0, alpha=0.85)
M_STEEL_DARK = mat("steel_d", (0.30, 0.30, 0.35, 1.0), 0.85, 0.30, emission=(0.28,0.28,0.32), emission_strength=0.3)
M_STEEL_LIGHT = mat("steel_l", (0.55, 0.55, 0.62, 1.0), 0.85, 0.30, emission=(0.50,0.52,0.58), emission_strength=0.4)
M_TOWER_LIT = mat("tower_lit", (1.0, 0.92, 0.55, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.55), emission_strength=6.0)

# Spire
M_SPIRE = mat("spire", (0.85, 0.88, 0.92, 1.0), 0.85, 0.20, emission=(0.85,0.88,0.92), emission_strength=2.0)
M_BEACON = mat("beacon", (1.0, 0.20, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.20,0.20), emission_strength=20.0)

# Water Palm Jumeirah
M_WATER_DUBAI = mat("water", (0.18, 0.55, 0.78, 1.0), 0.1, 0.20, emission=(0.20,0.55,0.78), emission_strength=1.5, alpha=0.78)
M_WATER_DEEP = mat("water_d", (0.10, 0.42, 0.62, 1.0), 0.1, 0.25, alpha=0.85)
M_FOUNTAIN_WATER = mat("fount", (0.85, 0.92, 0.98, 1.0), 0.0, 0.10, emission=(0.85,0.92,0.98), emission_strength=4.0, alpha=0.55)

# Palm tree
M_PALM_TRUNK_D = mat("palm_t", (0.55, 0.32, 0.15, 1.0), 0.0, 0.80, emission=(0.50,0.30,0.15), emission_strength=0.3)
M_PALM_LEAF_D = mat("palm_l", (0.30, 0.62, 0.25, 1.0), 0.0, 0.55, emission=(0.28,0.58,0.25), emission_strength=0.4)

# Luxury cars
M_CAR_RED = mat("car_r", (0.92, 0.18, 0.15, 1.0), 0.9, 0.15, emission=(0.88,0.18,0.15), emission_strength=1.5)
M_CAR_YELLOW = mat("car_y", (0.95, 0.85, 0.20, 1.0), 0.9, 0.15, emission=(0.92,0.82,0.20), emission_strength=1.5)
M_CAR_BLACK = mat("car_bk", (0.05, 0.05, 0.06, 1.0), 0.95, 0.15, emission=(0.10,0.10,0.10), emission_strength=0.5)
M_CAR_WHITE = mat("car_w", (0.92, 0.92, 0.95, 1.0), 0.9, 0.15, emission=(0.88,0.88,0.92), emission_strength=1.2)
M_CAR_BLUE = mat("car_b", (0.18, 0.45, 0.85, 1.0), 0.9, 0.15, emission=(0.18,0.42,0.85), emission_strength=1.5)
M_CAR_GOLD = mat("car_g", (1.0, 0.85, 0.30, 1.0), 0.95, 0.10, emission=(0.95,0.80,0.30), emission_strength=2.5)
CAR_COLORS = [M_CAR_RED, M_CAR_YELLOW, M_CAR_BLACK, M_CAR_WHITE, M_CAR_BLUE, M_CAR_GOLD]

M_TIRE = mat("tire", (0.10, 0.10, 0.10, 1.0), 0.0, 0.80)
M_RIM_GOLD = mat("rim_g", (1.0, 0.85, 0.30, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.30), emission_strength=2.0)
M_RIM_SILVER = mat("rim_s", (0.85, 0.85, 0.88, 1.0), 0.95, 0.20, emission=(0.80,0.80,0.85), emission_strength=1.5)
M_WINDSHIELD = mat("ws", (0.10, 0.18, 0.32, 1.0), 0.5, 0.10, emission=(0.18,0.30,0.45), emission_strength=1.5, alpha=0.65)
M_HEADLIGHT = mat("hl", (1.0, 0.95, 0.80, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.80), emission_strength=10.0)

# Camel
M_CAMEL_TAN = mat("camel", (0.85, 0.62, 0.32, 1.0), 0.0, 0.75, emission=(0.78,0.58,0.32), emission_strength=0.4)
M_CAMEL_DARK = mat("camel_d", (0.55, 0.40, 0.20, 1.0), 0.0, 0.85)
M_HARNESS_DUBAI = mat("harn", (0.78, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.72,0.18,0.18), emission_strength=0.6)
M_TASSEL_GOLD = mat("tas_g", (1.0, 0.85, 0.30, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.30), emission_strength=2.0)

# Bedouin tent
M_TENT_RED = mat("tent_r", (0.65, 0.20, 0.18, 1.0), 0.0, 0.75, emission=(0.60,0.20,0.18), emission_strength=0.6)
M_TENT_PATTERN = mat("tent_p", (0.92, 0.78, 0.32, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.32), emission_strength=1.0)
M_TENT_POLE = mat("t_pole", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)
M_CARPET_RED = mat("carpet", (0.78, 0.20, 0.20, 1.0), 0.0, 0.75, emission=(0.72,0.20,0.20), emission_strength=0.5)
M_CARPET_PATTERN = mat("carpet_p", (0.85, 0.45, 0.18, 1.0), 0.0, 0.70, emission=(0.80,0.45,0.18), emission_strength=0.6)

# Skin
M_SKIN_BROWN = mat("skin_br", (0.65, 0.42, 0.25, 1.0), 0.0, 0.55, emission=(0.60,0.40,0.25), emission_strength=0.4)
M_SKIN_LIGHT = mat("skin_l", (0.92, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.62), emission_strength=0.4)
SKIN_DUBAI = [M_SKIN_BROWN, M_SKIN_LIGHT]

# Bedouin clothes
M_DISHDASHA_WHITE = mat("dish", (0.92, 0.90, 0.85, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.80), emission_strength=0.5)
M_KEFFIYEH_RED = mat("kef_r", (0.85, 0.20, 0.18, 1.0), 0.0, 0.65, emission=(0.80,0.20,0.18), emission_strength=0.5)
M_KEFFIYEH_WHITE = mat("kef_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65)
M_AGAL = mat("agal", (0.10, 0.08, 0.08, 1.0), 0.0, 0.75)
M_ABAYA_BLACK = mat("abaya", (0.10, 0.10, 0.12, 1.0), 0.0, 0.65, emission=(0.12,0.12,0.14), emission_strength=0.3)
M_HIJAB_BLACK = mat("hijab", (0.08, 0.08, 0.10, 1.0), 0.0, 0.70)

# Tourist clothes
M_TSHIRT_BLUE = mat("ts_b", (0.18, 0.45, 0.85, 1.0), 0.0, 0.65)
M_TSHIRT_PINK = mat("ts_p", (0.95, 0.55, 0.85, 1.0), 0.0, 0.65, emission=(0.92,0.55,0.82), emission_strength=0.5)
M_TSHIRT_WHITE = mat("ts_w", (0.92, 0.90, 0.85, 1.0), 0.0, 0.65)
M_TSHIRT_YELLOW = mat("ts_y", (0.95, 0.85, 0.20, 1.0), 0.0, 0.55, emission=(0.92,0.82,0.20), emission_strength=0.6)
TSHIRT_VARIANTS = [M_TSHIRT_BLUE, M_TSHIRT_PINK, M_TSHIRT_WHITE, M_TSHIRT_YELLOW]
M_SHORTS_KHAKI = mat("shorts", (0.65, 0.55, 0.35, 1.0), 0.0, 0.75)
M_CAMERA = mat("cam", (0.12, 0.12, 0.12, 1.0), 0.4, 0.30)

# Hair
M_HAIR_BLACK_D = mat("h_bk", (0.08, 0.06, 0.05, 1.0), 0.0, 0.55)
M_HAIR_BROWN_D = mat("h_br", (0.32, 0.18, 0.10, 1.0), 0.0, 0.60)
M_HAIR_BLOND_D = mat("h_bl", (0.85, 0.65, 0.30, 1.0), 0.0, 0.55)
HAIR_DUBAI = [M_HAIR_BLACK_D, M_HAIR_BROWN_D, M_HAIR_BLOND_D]

# Helicopter
M_HELI_BODY = mat("heli_b", (0.85, 0.85, 0.92, 1.0), 0.5, 0.30, emission=(0.80,0.80,0.88), emission_strength=0.5)
M_HELI_DARK = mat("heli_d", (0.18, 0.18, 0.22, 1.0), 0.5, 0.40)
M_HELI_ROTOR = mat("heli_r", (0.32, 0.32, 0.35, 1.0), 0.7, 0.35)

# Gold Souk
M_SOUK_GOLD = mat("souk_g", (1.0, 0.85, 0.25, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.25), emission_strength=2.5)
M_SOUK_GOLD_DEEP = mat("souk_gd", (0.85, 0.62, 0.18, 1.0), 0.95, 0.20, emission=(0.80,0.58,0.18), emission_strength=1.8)
M_NECKLACE = mat("nk", (1.0, 0.92, 0.45, 1.0), 0.95, 0.10, emission=(0.95,0.88,0.45), emission_strength=3.0)
M_SOUK_AWNING = mat("awn", (0.78, 0.42, 0.18, 1.0), 0.0, 0.75, emission=(0.72,0.40,0.18), emission_strength=0.6)
M_SOUK_GLASS = mat("souk_gl", (0.85, 0.92, 0.95, 1.0), 0.0, 0.20, emission=(0.85,0.92,0.95), emission_strength=2.0, alpha=0.55)

# Eye
M_EYE_DARK_D = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Lasers
M_LASER_RED = mat("las_r", (1.0, 0.20, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.20,0.20), emission_strength=12.0, alpha=0.55)
M_LASER_GREEN = mat("las_g", (0.20, 1.0, 0.30, 1.0), 0.0, 0.10, emission=(0.20,1.0,0.30), emission_strength=12.0, alpha=0.55)
M_LASER_BLUE = mat("las_b", (0.20, 0.45, 1.0, 1.0), 0.0, 0.10, emission=(0.20,0.45,1.0), emission_strength=12.0, alpha=0.55)
M_LASER_PURPLE = mat("las_p", (0.75, 0.25, 1.0, 1.0), 0.0, 0.10, emission=(0.75,0.25,1.0), emission_strength=12.0, alpha=0.55)
M_LASER_YELLOW = mat("las_y", (1.0, 0.92, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.20), emission_strength=12.0, alpha=0.55)
LASER_COLORS = [M_LASER_RED, M_LASER_GREEN, M_LASER_BLUE, M_LASER_PURPLE, M_LASER_YELLOW]

# Gold sand particles
M_GOLD_SAND = mat("gs", (1.0, 0.85, 0.45, 1.0), 0.5, 0.30, emission=(0.95,0.80,0.45), emission_strength=3.0)

# ============ SKY ============
sky = smooth_sphere("sky", r=350, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Moon
moon = smooth_sphere("moon", r=4, segs=24, rings=18, loc=(60, 100, 100), mat_=M_MOON_D)
# Stars
for si in range(150):
    sa = random.uniform(0, math.pi*2); sr = random.uniform(80, 220)
    sh = random.uniform(30, 120)
    smooth_sphere(f"star{si}", r=random.uniform(0.10, 0.30), segs=8, rings=6,
                  loc=(sr*math.cos(sa), sr*math.sin(sa), sh), mat_=M_STAR_D)

# ============ ONE clean sand+concrete ground ============
ground = beveled_cube("ground", (250, 250, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_SAND_GOLDEN_D)
# Concrete plaza near tower
plaza = beveled_cube("plaza", (100, 100, 0.30), bevel_offset=0.10, loc=(0, -20, 0.10), mat_=M_CONCRETE)
# Roads
beveled_cube("road1", (200, 8, 0.20), bevel_offset=0.06, loc=(0, -40, 0.18), mat_=M_ASPHALT)
beveled_cube("road2", (8, 100, 0.20), bevel_offset=0.06, loc=(-50, 10, 0.18), mat_=M_ASPHALT)
# Road lines
for li in range(20):
    beveled_cube(f"rl{li}", (3, 0.30, 0.04), bevel_offset=0.01, loc=(-90 + li*10, -40, 0.30),
                 mat_=M_TENT_PATTERN)
# Sand dunes
for i in range(150):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(60, 120)
    smooth_sphere(f"dune{i}", r=random.uniform(0.5, 1.2), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_SAND_DARK_D if i % 2 == 0 else M_SAND_GOLDEN_D,
                  scale=(1.5, 1.4, 0.22))

# ============ BURJ KHALIFA 8m signature massive tower ============
burj_e = empty("burj", loc=(0, 0, 0))
# 8 tiered setbacks signature (decreasing as goes up)
# Base wide
beveled_cube("burj_base", (10, 10, 1), bevel_offset=0.20, loc=(0, 0, 0.5), parent=burj_e, mat_=M_STEEL_DARK)
# Stepped levels
levels_data = [
    (8, 8, 1, 12, 0),    # (w, d, height_per_step, num_steps, y_offset)
    (7, 7, 1, 8, 0),
    (6, 6, 1, 8, 0),
    (5, 5, 1, 8, 0),
    (4, 4, 1, 8, 0),
    (3, 3, 1, 8, 0),
    (2.5, 2.5, 1, 6, 0),
    (2, 2, 1, 6, 0),
]
current_z = 1
for li, (lw, ld, lh, ln, ly) in enumerate(levels_data):
    for sl in range(ln):
        beveled_cube(f"bk_l{li}_{sl}", (lw, ld, lh), bevel_offset=0.15,
                     loc=(0, 0, current_z + lh/2), parent=burj_e,
                     mat_=M_GLASS_BLUE if sl % 2 == 0 else M_GLASS_LIGHT)
        current_z += lh
    # Steel band between levels
    beveled_cube(f"bk_band{li}", (lw + 0.3, ld + 0.3, 0.30), bevel_offset=0.06,
                 loc=(0, 0, current_z + 0.15), parent=burj_e, mat_=M_STEEL_LIGHT)
    current_z += 0.30
# Tall triangular spire (signature)
spire_top = current_z
for si in range(8):
    sr_s = 1.5 - si * 0.18
    sz_s = spire_top + si * 1.5
    cyl(f"bk_sp{si}", r=sr_s, depth=1.5, segs=12, loc=(0, 0, sz_s),
        parent=burj_e, mat_=M_SPIRE)
# Final needle point
cyl("bk_needle", r=0.10, depth=4, segs=10, loc=(0, 0, spire_top + 12),
    parent=burj_e, mat_=M_SPIRE)
# Red aviation beacon at top (signature)
smooth_sphere("bk_beacon", r=0.25, loc=(0, 0, spire_top + 14.5),
              parent=burj_e, mat_=M_BEACON)
# Lit windows scattered
for wi in range(300):
    wa = random.uniform(0, math.pi*2)
    wz = random.uniform(2, spire_top - 2)
    wr = 4.5 - wz * 0.05
    if wr < 1: wr = 1
    smooth_sphere(f"bk_w{wi}", r=0.10,
                  loc=(math.cos(wa)*wr, math.sin(wa)*wr, wz),
                  parent=burj_e, mat_=M_TOWER_LIT)

# ============ PALM JUMEIRAH (signature artificial island) ============
palm_e = empty("palm_j", loc=(-60, 50, 0))
# Trunk of palm island
beveled_cube("pj_trunk", (12, 24, 0.30), bevel_offset=0.10, loc=(0, 0, 0.15),
             parent=palm_e, mat_=M_SAND_GOLDEN_D)
# Crown frond fronds (16)
for fi in range(16):
    fa = (fi / 16.0) * math.pi * 2
    side_f = 1 if fi % 2 == 0 else -1
    fx_p = math.cos(fa) * 8
    fy_p = -8 + math.sin(fa) * 10
    beveled_cube(f"pj_f{fi}", (3, 8, 0.25), bevel_offset=0.06,
                 loc=(fx_p, fy_p - 4, 0.20), parent=palm_e, mat_=M_SAND_GOLDEN_D)
# Water around
beveled_cube("pj_water", (30, 35, 0.10), bevel_offset=0.10, loc=(0, -2, 0.05),
             parent=palm_e, mat_=M_WATER_DUBAI)
# Buildings on palm
for bi in range(30):
    ba = random.uniform(0, math.pi*2); br = random.uniform(2, 9)
    # Modern building tower
    cyl(f"pj_b{bi}", r=0.4, depth=random.uniform(1, 2), segs=10,
        loc=(math.cos(ba)*br, math.sin(ba)*br - 5, 0.5 + random.uniform(0, 1)),
        parent=palm_e, mat_=M_GLASS_BLUE if bi % 2 == 0 else M_STEEL_LIGHT)

# ============ DANCING FOUNTAINS (signature Burj Lake) ============
fountain_e = empty("fountain", loc=(0, -25, 0))
# Lake basin
cyl("fount_lake", r=15, depth=0.30, segs=32, loc=(0, 0, 0.15),
    parent=fountain_e, mat_=M_WATER_DUBAI)
cyl("fount_deep", r=14, depth=0.20, segs=32, loc=(0, 0, 0.20),
    parent=fountain_e, mat_=M_WATER_DEEP)
# Stone edge
cyl("fount_rim", r=15.5, depth=0.40, segs=32, loc=(0, 0, 0.20),
    parent=fountain_e, mat_=M_CONCRETE)
# Water JETS (signature varying heights)
fountains_jets = []
for ji in range(30):
    ja = (ji / 30.0) * math.pi * 2
    jr = random.uniform(2, 12)
    jx_j = math.cos(ja) * jr
    jy_j = math.sin(ja) * jr
    # Jet base
    cyl(f"jet_b{ji}", r=0.15, depth=0.10, segs=10, loc=(jx_j, jy_j, 0.30),
        parent=fountain_e, mat_=M_STEEL_DARK)
    # Water spray (varying heights signature)
    h_j = random.uniform(1.5, 5.0)
    jet_e = empty(f"jet_e{ji}", (jx_j, jy_j, 0.35), parent=fountain_e)
    smooth_cone(f"jet{ji}", r1=0.20, r2=0.04, depth=h_j, segs=10,
                loc=(0, 0, h_j/2), parent=jet_e, mat_=M_FOUNTAIN_WATER)
    # Top spray droplets
    smooth_sphere(f"jet_t{ji}", r=0.20, loc=(0, 0, h_j + 0.1),
                  parent=jet_e, mat_=M_FOUNTAIN_WATER, scale=(1.5, 1.5, 0.5))
    jet_e["_phase"] = random.uniform(0, math.pi*2)
    jet_e["_base_h"] = h_j
    fountains_jets.append(jet_e)

# ============ 6 LUXURY CARS (signature) ============
def make_luxury_car(name, loc, scale=1.0, facing=0, car_type="sports"):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    car_col = random.choice(CAR_COLORS)
    # Body main (low sports car shape)
    beveled_cube(f"{name}_body", (4.5*scale, 2*scale, 0.6*scale), bevel_offset=0.15,
                 loc=(0, 0, 0.6*scale), parent=base, mat_=car_col)
    # Hood (longer aerodynamic)
    beveled_cube(f"{name}_hood", (2*scale, 1.9*scale, 0.4*scale), bevel_offset=0.10,
                 loc=(1.5*scale, 0, 0.85*scale), parent=base, mat_=car_col)
    # Trunk
    beveled_cube(f"{name}_trunk", (1.5*scale, 1.9*scale, 0.4*scale), bevel_offset=0.10,
                 loc=(-1.5*scale, 0, 0.85*scale), parent=base, mat_=car_col)
    # Cabin
    beveled_cube(f"{name}_cabin", (1.5*scale, 1.7*scale, 0.8*scale), bevel_offset=0.20,
                 loc=(-0.2*scale, 0, 1.20*scale), parent=base, mat_=car_col)
    # Windshield + side windows
    beveled_cube(f"{name}_ws", (1.4*scale, 1.7*scale, 0.6*scale), bevel_offset=0.15,
                 loc=(-0.2*scale, 0, 1.30*scale), parent=base, mat_=M_WINDSHIELD)
    # 4 wheels with gold rims signature
    for x in (-1, 1):
        for y in (-1, 1):
            wheel_e = empty(f"{name}_w{x}{y}_e", (x*1.5*scale, y*1.0*scale, 0.40*scale), parent=base)
            wheel_e.rotation_euler = (math.radians(90), 0, 0)
            # Tire
            cyl(f"{name}_tire{x}{y}", r=0.40*scale, depth=0.25*scale, segs=18,
                loc=(0, 0, 0), parent=wheel_e, mat_=M_TIRE)
            # Rim (gold or silver)
            cyl(f"{name}_rim{x}{y}", r=0.28*scale, depth=0.10*scale, segs=18,
                loc=(0, 0, 0.13*scale), parent=wheel_e, mat_=M_RIM_GOLD if car_col == M_CAR_BLACK else M_RIM_SILVER)
            # Spokes
            for sp in range(5):
                spa = (sp / 5.0) * math.pi * 2
                beveled_cube(f"{name}_sp{x}{y}_{sp}", (0.04*scale, 0.04*scale, 0.25*scale), bevel_offset=0.005,
                             loc=(0, 0, 0.13*scale), parent=wheel_e,
                             mat_=M_RIM_GOLD if car_col == M_CAR_BLACK else M_RIM_SILVER).rotation_euler = (0, 0, spa)
    # Headlights (signature bright)
    for side in (-1, 1):
        smooth_sphere(f"{name}_hl{side}", r=0.15*scale,
                      loc=(2.40*scale, side*0.7*scale, 0.7*scale),
                      parent=base, mat_=M_HEADLIGHT, scale=(0.4, 1.5, 1))
    # Tail lights red
    for side in (-1, 1):
        smooth_sphere(f"{name}_tl{side}", r=0.10*scale,
                      loc=(-2.40*scale, side*0.7*scale, 0.7*scale),
                      parent=base, mat_=M_LASER_RED, scale=(0.4, 1.5, 1))
    # Spoiler (signature sports)
    beveled_cube(f"{name}_spoil", (0.10*scale, 1.5*scale, 0.30*scale), bevel_offset=0.04,
                 loc=(-2.3*scale, 0, 1.10*scale), parent=base, mat_=car_col)
    # Exhaust
    cyl(f"{name}_exh_l", r=0.06*scale, depth=0.15*scale, segs=10,
        loc=(-2.4*scale, -0.40*scale, 0.40*scale), parent=base, mat_=M_RIM_SILVER).rotation_euler = (0, math.radians(90), 0)
    cyl(f"{name}_exh_r", r=0.06*scale, depth=0.15*scale, segs=10,
        loc=(-2.4*scale, 0.40*scale, 0.40*scale), parent=base, mat_=M_RIM_SILVER).rotation_euler = (0, math.radians(90), 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base}

cars = []
car_pos = [(-25, -40, math.radians(0)), (-10, -40, math.radians(0)),
            (5, -40, math.radians(0)), (-50, -10, math.radians(90)),
            (-50, 10, math.radians(90)), (-50, 30, math.radians(90))]
for i, (cx, cy, fac) in enumerate(car_pos):
    c = make_luxury_car(f"car{i}", (cx, cy, 0), scale=1.0, facing=fac)
    cars.append(c)

# ============ 4 CAMELS (signature with harnesses) ============
def make_camel(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.8, segs=20, rings=14, loc=(0, 0, 2),
                  parent=base, mat_=M_CAMEL_TAN, scale=(1.5, 1.0, 1.0))
    # HUMP (signature)
    smooth_sphere(f"{name}_hump", r=0.5, segs=18, rings=12, loc=(0, 0, 2.6),
                  parent=base, mat_=M_CAMEL_TAN, scale=(1.2, 0.9, 0.85))
    # 4 long legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}{y}", r=0.10, depth=2.0, segs=10,
                loc=(x*0.55, y*0.40, 1), parent=base, mat_=M_CAMEL_TAN)
            # Hoof
            cyl(f"{name}_h{x}{y}", r=0.12, depth=0.10, segs=10,
                loc=(x*0.55, y*0.40, 0.05), parent=base, mat_=M_CAMEL_DARK)
    # LONG CURVED NECK signature
    neck_e = empty(f"{name}_neck", (1.0, 0, 2.3), parent=base)
    neck_e.rotation_euler = (0, math.radians(-30), 0)
    for ni in range(5):
        cyl(f"{name}_n{ni}", r=0.18 - ni*0.01, depth=0.30, segs=12,
            loc=(0, 0, ni*0.30 + 0.15), parent=neck_e, mat_=M_CAMEL_TAN)
    # Head
    head_c_e = empty(f"{name}_he", (0, 0, 1.7), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.25, segs=18, rings=14, loc=(0.10, 0, 0),
                  parent=head_c_e, mat_=M_CAMEL_TAN, scale=(1.5, 0.9, 1))
    # Long snout
    smooth_sphere(f"{name}_snout", r=0.18, loc=(0.32, 0, -0.10),
                  parent=head_c_e, mat_=M_CAMEL_DARK, scale=(1.3, 0.7, 0.7))
    # Eyes (with lashes signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04,
                      loc=(0.10, side*0.15, 0.05), parent=head_c_e, mat_=M_EYE_DARK_D)
    # Long eyelashes (signature)
    for side in (-1, 1):
        for li in range(4):
            cyl(f"{name}_lash{side}_{li}", r=0.005, depth=0.06, segs=4,
                loc=(0.10 + li*0.01, side*0.15, 0.10), parent=head_c_e, mat_=M_HAIR_BLACK_D)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.08,
                      loc=(-0.05, side*0.15, 0.15), parent=head_c_e,
                      mat_=M_CAMEL_TAN, scale=(0.5, 1, 1.2))
    # HARNESS signature red with tassels
    cyl(f"{name}_harn", r=0.20, depth=0.10, segs=14, loc=(0, 0, 1.5),
        parent=neck_e, mat_=M_HARNESS_DUBAI)
    # Tassels (signature)
    for ti in range(8):
        ta = (ti / 8.0) * math.pi * 2
        for hi in range(4):
            smooth_sphere(f"{name}_t{ti}_{hi}", r=0.04,
                          loc=(math.cos(ta)*0.22, math.sin(ta)*0.22, 1.5 - hi*0.10),
                          parent=neck_e, mat_=M_TASSEL_GOLD)
    # Saddle blanket
    beveled_cube(f"{name}_saddle", (1.5, 1.7, 0.10), bevel_offset=0.04, loc=(0, 0, 3.15),
                 parent=base, mat_=M_CARPET_RED)
    # Pattern on saddle
    for pi in range(4):
        beveled_cube(f"{name}_sp{pi}", (0.30, 1.7, 0.05), bevel_offset=0.02,
                     loc=(-0.45 + pi*0.30, 0, 3.20), parent=base, mat_=M_CARPET_PATTERN)
    # Tail
    cyl(f"{name}_tail", r=0.05, depth=0.6, segs=8, loc=(-1.2, 0, 2.1),
        parent=base, mat_=M_CAMEL_TAN).rotation_euler = (math.radians(60), 0, 0)
    smooth_sphere(f"{name}_tt", r=0.10, loc=(-1.2, 0, 1.5),
                  parent=base, mat_=M_CAMEL_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_c_e, "neck": neck_e}

camels = []
camel_pos = [(40, 30, math.radians(-30)), (45, 25, math.radians(-45)),
              (48, 35, math.radians(-15)), (52, 28, math.radians(-30))]
for i, (cx, cy, fac) in enumerate(camel_pos):
    c = make_camel(f"camel{i}", (cx, cy, 0), scale=1.0, facing=fac)
    camels.append(c)

# ============ BEDOUIN TENT (signature) ============
tent_e = empty("tent", loc=(50, 45, 0))
# Main center pole
cyl("t_p", r=0.15, depth=5, segs=10, loc=(0, 0, 2.5), parent=tent_e, mat_=M_TENT_POLE)
# Tent fabric (multiple panels signature)
for ti in range(12):
    ta = (ti / 12.0) * math.pi * 2
    panel_e = empty(f"t_p{ti}_e", (0, 0, 2.5), parent=tent_e)
    panel_e.rotation_euler = (0, 0, ta)
    # Slope panel
    beveled_cube(f"t_p{ti}", (4, 0.10, 4), bevel_offset=0.08, loc=(2, 0, 0),
                 parent=panel_e, mat_=M_TENT_RED).rotation_euler = (0, math.radians(20), 0)
    # Pattern
    for pi in range(4):
        beveled_cube(f"t_p{ti}_pat{pi}", (3.8, 0.12, 0.30), bevel_offset=0.02,
                     loc=(2, 0, -1.5 + pi*1.0), parent=panel_e,
                     mat_=M_TENT_PATTERN).rotation_euler = (0, math.radians(20), 0)
# Carpet inside
cyl("t_carpet", r=3, depth=0.10, segs=18, loc=(0, 0, 0.10),
    parent=tent_e, mat_=M_CARPET_RED)
# Pattern on carpet
for ci in range(8):
    ca = (ci / 8.0) * math.pi * 2
    cyl(f"t_cp{ci}", r=0.30, depth=0.05, segs=14,
        loc=(math.cos(ca)*1.5, math.sin(ca)*1.5, 0.16),
        parent=tent_e, mat_=M_CARPET_PATTERN)

# ============ 8 TOURISTS taking photos ============
def make_tourist(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    tshirt = random.choice(TSHIRT_VARIANTS)
    hair = random.choice(HAIR_DUBAI)
    skin = random.choice(SKIN_DUBAI)
    # Body
    smooth_cone(f"{name}_torso", r1=0.28*scale, r2=0.30*scale, depth=0.6*scale, segs=14,
                loc=(0, 0, 1.3*scale), parent=base, mat_=tshirt)
    # Shorts
    smooth_cone(f"{name}_sh", r1=0.30*scale, r2=0.28*scale, depth=0.40*scale, segs=14,
                loc=(0, 0, 0.85*scale), parent=base, mat_=M_SHORTS_KHAKI)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.08*scale, depth=0.7*scale, segs=10,
            loc=(side*0.10*scale, 0, 0.35*scale), parent=base, mat_=skin)
        beveled_cube(f"{name}_sk{side}", (0.10*scale, 0.18*scale, 0.06*scale), bevel_offset=0.02,
                     loc=(side*0.10*scale, 0, 0), parent=base, mat_=M_HAIR_BROWN_D)
    # Arms (one raised holding camera/phone)
    sh_r = empty(f"{name}_sh_r", (0.30*scale, -0.15*scale, 1.55*scale), parent=base)
    sh_r.rotation_euler = (math.radians(-90), 0, math.radians(-15))
    cyl(f"{name}_uarm_R", r=0.05*scale, depth=0.30*scale, segs=10,
        loc=(0, 0, -0.15*scale), parent=sh_r, mat_=tshirt)
    cyl(f"{name}_fa_R", r=0.045*scale, depth=0.30*scale, segs=10,
        loc=(0, 0, -0.45*scale), parent=sh_r, mat_=skin)
    # CAMERA / PHONE in hand
    beveled_cube(f"{name}_cam", (0.15*scale, 0.05*scale, 0.10*scale), bevel_offset=0.02,
                 loc=(0, 0, -0.62*scale), parent=sh_r, mat_=M_CAMERA)
    # Lens
    cyl(f"{name}_lens", r=0.04*scale, depth=0.05*scale, segs=10,
        loc=(0.08*scale, 0, -0.62*scale), parent=sh_r, mat_=M_HEADLIGHT).rotation_euler = (0, math.radians(90), 0)
    sh_l = empty(f"{name}_sh_l", (-0.30*scale, 0, 1.55*scale), parent=base)
    sh_l.rotation_euler = (math.radians(-45), 0, math.radians(20))
    cyl(f"{name}_uarm_L", r=0.05*scale, depth=0.30*scale, segs=10,
        loc=(0, 0, -0.15*scale), parent=sh_l, mat_=tshirt)
    cyl(f"{name}_fa_L", r=0.045*scale, depth=0.30*scale, segs=10,
        loc=(0, 0, -0.45*scale), parent=sh_l, mat_=skin)
    # Head
    head_t_e = empty(f"{name}_he", (0, 0, 1.85*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.17*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_t_e, mat_=skin)
    # Hair
    for hi in range(8):
        ha = (hi / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.05*scale,
                      loc=(math.cos(ha)*0.14*scale, math.sin(ha)*0.10*scale, 0.10*scale),
                      parent=head_t_e, mat_=hair)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.03*scale), parent=head_t_e, mat_=M_EYE_DARK_D)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_t_e}

tourists = []
tourist_pos = [(-15, -22, math.radians(60)), (-12, -25, math.radians(70)),
                (-8, -22, math.radians(45)), (-5, -25, math.radians(50)),
                (5, -25, math.radians(120)), (8, -22, math.radians(135)),
                (12, -25, math.radians(110)), (15, -22, math.radians(120))]
for i, (tx, ty, fac) in enumerate(tourist_pos):
    t = make_tourist(f"tourist{i}", (tx, ty, 0), scale=1.0, facing=fac)
    tourists.append(t)

# ============ HELICOPTER flying (signature) ============
heli_e = empty("helicopter", loc=(80, 60, 50))
# Body (signature streamlined)
smooth_sphere("h_body", r=1.2, segs=20, rings=14, loc=(0, 0, 0),
              parent=heli_e, mat_=M_HELI_BODY, scale=(2.5, 1.0, 1.0))
# Tail boom
cyl("h_tail", r=0.20, depth=4, segs=14, loc=(-3, 0, 0),
    parent=heli_e, mat_=M_HELI_BODY).rotation_euler = (0, math.radians(90), 0)
# Tail fin
beveled_cube("h_fin", (0.30, 0.10, 0.80), bevel_offset=0.06, loc=(-5, 0, 0.3),
             parent=heli_e, mat_=M_HELI_BODY)
# Cockpit windshield
smooth_sphere("h_ws", r=1.0, segs=18, rings=12, loc=(0.8, 0, 0.2),
              parent=heli_e, mat_=M_WINDSHIELD, scale=(0.8, 0.7, 0.7))
# Landing skids
for side in (-1, 1):
    cyl(f"h_skid{side}", r=0.06, depth=3, segs=10, loc=(0, side*0.6, -0.8),
        parent=heli_e, mat_=M_HELI_DARK).rotation_euler = (0, math.radians(90), 0)
    # Support
    cyl(f"h_sup{side}", r=0.04, depth=0.5, segs=8, loc=(0.5, side*0.6, -0.5),
        parent=heli_e, mat_=M_HELI_DARK)
# MAIN ROTOR (signature)
rotor_main_e = empty("h_rotor", (0, 0, 1.3), parent=heli_e)
# Hub
cyl("h_hub", r=0.15, depth=0.20, segs=14, loc=(0, 0, 0), parent=rotor_main_e, mat_=M_HELI_DARK)
# 4 blades
for bi in range(4):
    ba = (bi / 4.0) * math.pi * 2
    beveled_cube(f"h_b{bi}", (4, 0.30, 0.04), bevel_offset=0.03,
                 loc=(math.cos(ba)*2, math.sin(ba)*2, 0),
                 parent=rotor_main_e, mat_=M_HELI_ROTOR).rotation_euler = (0, 0, ba)
# Tail rotor
tail_rotor_e = empty("h_tr", (-5.2, 0.30, 0.30), parent=heli_e)
cyl("h_tr_h", r=0.05, depth=0.15, segs=10, loc=(0, 0, 0),
    parent=tail_rotor_e, mat_=M_HELI_DARK).rotation_euler = (0, math.radians(90), 0)
for bi in range(3):
    ba = (bi / 3.0) * math.pi * 2
    beveled_cube(f"h_tr_b{bi}", (0.04, 0.04, 0.50), bevel_offset=0.01,
                 loc=(0, math.sin(ba)*0.30, math.cos(ba)*0.30),
                 parent=tail_rotor_e, mat_=M_HELI_ROTOR)

# ============ GOLD SOUK (signature jewelry market) ============
souk_e = empty("souk", loc=(40, -50, 0))
# Awning structure
for ai in range(5):
    ax_s = ai * 3 - 6
    beveled_cube(f"souk_a{ai}", (3, 4, 0.20), bevel_offset=0.06,
                 loc=(ax_s, 0, 3), parent=souk_e, mat_=M_SOUK_AWNING)
    # Posts
    for side in (-1, 1):
        cyl(f"souk_p{ai}_{side}", r=0.10, depth=3, segs=10,
            loc=(ax_s, side*2, 1.5), parent=souk_e, mat_=M_STEEL_LIGHT)
# Shop displays with GOLD JEWELRY signature
for di in range(5):
    dx_s = di * 3 - 6
    # Counter
    beveled_cube(f"souk_c{di}", (2.5, 1.5, 0.6), bevel_offset=0.06,
                 loc=(dx_s, 0, 0.8), parent=souk_e, mat_=M_STEEL_DARK)
    # Glass display top
    beveled_cube(f"souk_g{di}", (2.4, 1.4, 0.8), bevel_offset=0.10,
                 loc=(dx_s, 0, 1.7), parent=souk_e, mat_=M_SOUK_GLASS)
    # GOLD NECKLACES on display (signature)
    for ni in range(8):
        nx_n = -1 + ni * 0.30
        ny_n = -0.4 + (ni % 2) * 0.4
        # Necklace beads
        for bi in range(10):
            ba_n = (bi / 10.0) * math.pi
            smooth_sphere(f"sk_n{di}_{ni}_{bi}", r=0.025,
                          loc=(dx_s + nx_n + math.sin(ba_n)*0.10, ny_n, 1.42 + math.cos(ba_n)*0.05),
                          parent=souk_e, mat_=M_NECKLACE)
    # Gold rings
    for ri in range(6):
        cyl(f"sk_r{di}_{ri}", r=0.04, depth=0.04, segs=14,
            loc=(dx_s - 1.0 + ri*0.4, 0.5, 1.42),
            parent=souk_e, mat_=M_SOUK_GOLD).rotation_euler = (math.radians(90), 0, 0)
    # Sign
    beveled_cube(f"sk_sg{di}", (2.0, 0.10, 0.50), bevel_offset=0.04,
                 loc=(dx_s, -1.95, 2.5), parent=souk_e, mat_=M_SOUK_GOLD_DEEP)

# Some palm trees scattered (signature Dubai oasis)
for ti in range(5):
    ta = random.uniform(0, math.pi*2); tr = random.uniform(35, 70)
    tx_p = math.cos(ta) * tr
    ty_p = math.sin(ta) * tr
    t_p_e = empty(f"palm{ti}", (tx_p, ty_p, 0))
    # Trunk
    cyl(f"p{ti}_t", r=0.30, depth=6, segs=14, loc=(0, 0, 3), parent=t_p_e, mat_=M_PALM_TRUNK_D)
    # Crown
    crown_e = empty(f"p{ti}_cr", (0, 0, 6.5), parent=t_p_e)
    for li in range(8):
        la = (li / 8.0) * math.pi * 2
        leaf_e = empty(f"p{ti}_l{li}_e", (0, 0, 0), parent=crown_e)
        leaf_e.rotation_euler = (math.radians(60), 0, la)
        cyl(f"p{ti}_lr{li}", r=0.03, depth=2.5, segs=8, loc=(0, 0, 1.25),
            parent=leaf_e, mat_=M_PALM_TRUNK_D)
        for sl in range(6):
            sl_z = sl * 0.35 + 0.40
            for ps in (-1, 1):
                beveled_cube(f"p{ti}_pn{li}_{sl}_{ps}", (0.03, 0.5, 0.04), bevel_offset=0.01,
                             loc=(ps*0.25, 0, sl_z), parent=leaf_e, mat_=M_PALM_LEAF_D)

# ============================================================
# ⭐ 600 GOLD SAND GRAINS + 400 LASERS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
gold_sands = []
for i in range(600):
    px = random.uniform(-80, 80)
    py = random.uniform(-80, 80)
    pz = random.uniform(0.5, 15)
    s = smooth_sphere(f"gs{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6,
                      loc=(px, py, pz), mat_=M_GOLD_SAND)
    s["_phase"] = random.uniform(0, math.pi*2)
    s["_base_x"] = px; s["_base_y"] = py; s["_base_z"] = pz
    s["_amp_x"] = random.uniform(1.0, 2.5)
    s["_amp_y"] = random.uniform(1.0, 2.5)
    s["_amp_z"] = random.uniform(0.3, 1.0)
    s["_speed"] = random.uniform(0.3, 0.8)
    gold_sands.append(s)

# 400 LASERS (signature beam cones rotating)
lasers = []
laser_emitters = []
# 8 emitters around plaza
emitter_pos = []
for ei in range(8):
    ea = (ei / 8.0) * math.pi * 2
    er = 35
    emitter_pos.append((math.cos(ea)*er, math.sin(ea)*er - 10, 5))

for ei, (ex_p, ey_p, ez_p) in enumerate(emitter_pos):
    em_e = empty(f"emit{ei}", (ex_p, ey_p, ez_p))
    # Emitter base
    beveled_cube(f"em_b{ei}", (0.50, 0.50, 0.30), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=em_e, mat_=M_STEEL_DARK)
    # Lasers from each emitter (50 per emitter = 400 total)
    for li in range(50):
        las_col = random.choice(LASER_COLORS)
        # Random direction
        la_a = random.uniform(0, math.pi*2)
        la_e = random.uniform(math.radians(20), math.radians(80))
        la_len = random.uniform(15, 40)
        # Direction vector
        dx = math.sin(la_e) * math.cos(la_a) * la_len
        dy = math.sin(la_e) * math.sin(la_a) * la_len
        dz = math.cos(la_e) * la_len
        # Beam (thin elongated cylinder)
        beam = smooth_cone(f"las{ei}_{li}", r1=0.08, r2=0.02, depth=la_len, segs=8,
                           loc=(dx/2, dy/2, dz/2), parent=em_e, mat_=las_col)
        # Orient beam
        beam.rotation_euler = (math.atan2(math.sqrt(dx*dx + dy*dy), dz),
                                0, math.atan2(dy, dx))
        beam["_phase"] = random.uniform(0, math.pi*2)
        beam["_dir_a"] = la_a
        beam["_dir_e"] = la_e
        beam["_len"] = la_len
        lasers.append(beam)
    em_e["_phase"] = random.uniform(0, math.pi*2)
    laser_emitters.append(em_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Tower beacon pulse
beacon = bpy.data.objects.get("bk_beacon")
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    if beacon:
        s_b = 0.5 + abs(math.sin(t * 3.0)) * 1.5
        beacon.scale = (s_b, s_b, s_b)
        beacon.keyframe_insert("scale", frame=f)

# Fountain jets dancing
for jet in fountains_jets:
    phase = jet["_phase"]
    base_h = jet["_base_h"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        new_h = base_h + math.sin(t * 2.0 + phase) * base_h * 0.5
        jet.scale = (1, 1, new_h / base_h)
        jet.keyframe_insert("scale", frame=f)

# Cars vibrating idle
for c in cars:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        c["root"].location.z = math.sin(t * 8.0 + phase) * 0.02
        c["root"].keyframe_insert("location", frame=f)

# Camels walking
for ca in camels:
    phase = ca["root"]["_phase"]
    bx_c = ca["root"].location.x; by_c = ca["root"].location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        ca["root"].location.x = bx_c + math.sin(t * 0.6 + phase) * 0.5
        ca["root"].location.y = by_c + math.cos(t * 0.6 + phase) * 0.5
        ca["root"].location.z = abs(math.sin(t * 1.5 + phase)) * 0.05
        ca["root"].keyframe_insert("location", frame=f)
        # Neck sway
        ca["neck"].rotation_euler = (0, math.radians(-30) + math.sin(t * 0.8 + phase) * math.radians(10), 0)
        ca["neck"].keyframe_insert("rotation_euler", frame=f)

# Tourists photographing (head turn)
for t_obj in tourists:
    phase = t_obj["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        t_obj["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(10), 0,
                                       math.cos(t * 1.2 + phase) * math.radians(20))
        t_obj["he"].keyframe_insert("rotation_euler", frame=f)

# Helicopter circling
phase_heli = 0
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    heli_e.location.x = 80 + math.cos(t * 0.3) * 20
    heli_e.location.y = 60 + math.sin(t * 0.3) * 20
    heli_e.location.z = 50 + math.sin(t * 0.5) * 3
    heli_e.rotation_euler = (0, math.sin(t * 0.3) * math.radians(5),
                              t * 0.3 + math.pi)
    heli_e.keyframe_insert("location", frame=f)
    heli_e.keyframe_insert("rotation_euler", frame=f)

# Rotors spinning fast
for f in range(1, total_frames + 1, 1):
    t = (f - 1) / fps
    rotor_main_e.rotation_euler = (0, 0, t * 25)
    rotor_main_e.keyframe_insert("rotation_euler", frame=f)
    tail_rotor_e.rotation_euler = (t * 30, math.radians(90), 0)
    tail_rotor_e.keyframe_insert("rotation_euler", frame=f)

# Laser emitters rotate
for em in laser_emitters:
    phase = em["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        em.rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(15),
                              math.cos(t * 0.8 + phase) * math.radians(15),
                              t * 0.8 + phase)
        em.keyframe_insert("rotation_euler", frame=f)

# 600 gold sand particles drift
for s in gold_sands:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        s.location = (x, y, max(0.3, z))
        sc_s = 0.7 + abs(math.sin(t * speed + phase)) * 0.6
        s.scale = (sc_s, sc_s, sc_s)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
# ARCHITECTURE DE SORTIE. Ce script ecrivait son GLB dans
# `application/public/_pbr_test/`, un dossier servi par Vite — et que le build
# EFFACAIT au build (vite.config.ts, closeBundle). Le
# livrable ne rejoignait donc jamais `application/output/3d/`, ou la
# bibliotheque 3D, l interface et le tunnel vont le chercher : le fichier
# existait sur le disque et restait invisible. 111 scripts partageaient ce
# defaut, alors que `aurora_output_paths` enonce le contraire en toutes
# lettres : « Every module MUST place its outputs under
# application/output/<module_name>/<project_name>/ ».
import sys as _sys_out
_sys_out.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aurora_output_paths import get_3d_project_dir as _aurora_dir_3d
out_dir = str(_aurora_dir_3d(
    os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]))
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_dubai_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_dubai_burj_khalifa_desert] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_dubai_burj_khalifa_desert] Burj Khalifa 8 tiers + spire + beacon + 300 lit windows + Palm Jumeirah + 6 luxury cars + 4 camels harnessed + Bedouin tent + 8 tourists + dancing fountains + helicopter + Gold Souk + 5 palms + 600 gold sand + 400 lasers")
print("⭐ FIXES: 1 ground + 600 gold sand + 400 lasers (signature Dubai thematic mandatory) ⭐")
