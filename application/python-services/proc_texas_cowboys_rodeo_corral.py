"""
proc_texas_cowboys_rodeo_corral.py — 285e procédural AuroraIA (150e qualité)
Texas cowboys rodeo: 4 cowboys with Stetson hats + leather chaps + lassos + 4 horses + brahman rodeo bull + corral fence + western saloon + Texas Lone Star flag + saguaro cacti + 600 lassos + 400 sheriff stars
FIXES : 1 ground western dust + signature lassos + stars
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB285)

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

# Sky western sunset
M_SKY = mat("sky", (1.0, 0.55, 0.35, 1.0), 0.0, 0.7, emission=(1.0,0.55,0.35), emission_strength=2.3)
M_SKY_LOW = mat("sky_l", (0.95, 0.72, 0.45, 1.0), 0.0, 0.7, emission=(0.92,0.70,0.45), emission_strength=2.0)
M_SUN = mat("sun", (1.0, 0.78, 0.30, 1.0), 0.0, 0.1, emission=(1.0,0.78,0.30), emission_strength=22.0)

# Western dust ground
M_DUST = mat("d", (0.78, 0.55, 0.35, 1.0), 0.0, 0.85, emission=(0.75,0.55,0.35), emission_strength=0.4)
M_DUST_DARK = mat("dd", (0.55, 0.38, 0.22, 1.0), 0.0, 0.92)
M_DUST_LIGHT = mat("dl", (0.92, 0.72, 0.50, 1.0), 0.0, 0.75, emission=(0.88,0.70,0.50), emission_strength=0.5)
M_ROCK = mat("rk", (0.45, 0.32, 0.22, 1.0), 0.0, 0.92)

# Cowboy clothing
M_SKIN_TAN = mat("sk", (0.85, 0.62, 0.42, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.42), emission_strength=0.3)
M_HAIR_BROWN = mat("hb", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)

# Shirt
M_SHIRT_BLUE = mat("sb", (0.32, 0.55, 0.78, 1.0), 0.0, 0.65, emission=(0.30,0.52,0.75), emission_strength=0.3)
M_SHIRT_RED = mat("sr", (0.85, 0.20, 0.22, 1.0), 0.0, 0.55, emission=(0.82,0.20,0.22), emission_strength=0.5)
M_SHIRT_PLAID = mat("sp", (0.78, 0.32, 0.22, 1.0), 0.0, 0.65, emission=(0.75,0.30,0.22), emission_strength=0.4)
M_SHIRT_WHITE = mat("sw", (0.92, 0.88, 0.78, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.78), emission_strength=0.4)
SHIRT_COLORS = [M_SHIRT_BLUE, M_SHIRT_RED, M_SHIRT_PLAID, M_SHIRT_WHITE]

# Leather chaps (signature)
M_LEATHER_BROWN = mat("lb", (0.55, 0.32, 0.18, 1.0), 0.2, 0.55, emission=(0.52,0.30,0.18), emission_strength=0.3)
M_LEATHER_DARK = mat("ld", (0.32, 0.18, 0.10, 1.0), 0.2, 0.65)
M_LEATHER_TAN = mat("lt", (0.72, 0.52, 0.32, 1.0), 0.2, 0.55, emission=(0.70,0.52,0.32), emission_strength=0.4)
M_FRINGE = mat("fr", (0.55, 0.32, 0.18, 1.0), 0.0, 0.85)

# Boots
M_BOOT_BROWN = mat("bb", (0.42, 0.22, 0.12, 1.0), 0.3, 0.40)

# Stetson hat (signature)
M_STETSON = mat("st", (0.55, 0.42, 0.25, 1.0), 0.0, 0.85, emission=(0.52,0.40,0.25), emission_strength=0.3)
M_STETSON_DARK = mat("std", (0.32, 0.22, 0.12, 1.0), 0.0, 0.92)
M_STETSON_BAND = mat("stb", (0.18, 0.12, 0.08, 1.0), 0.2, 0.55)

# Belt buckle (signature)
M_BUCKLE_SILVER = mat("bs", (0.85, 0.85, 0.85, 1.0), 0.9, 0.10, emission=(0.82,0.82,0.82), emission_strength=1.5)
M_BUCKLE_GOLD = mat("bg", (0.95, 0.78, 0.20, 1.0), 0.9, 0.10, emission=(0.92,0.75,0.20), emission_strength=2.0)

# Horse
M_HORSE_BROWN = mat("hbr", (0.45, 0.28, 0.15, 1.0), 0.0, 0.65, emission=(0.42,0.28,0.15), emission_strength=0.3)
M_HORSE_BLACK = mat("hbk", (0.15, 0.12, 0.10, 1.0), 0.0, 0.65)
M_HORSE_WHITE = mat("hw", (0.92, 0.88, 0.82, 1.0), 0.0, 0.65, emission=(0.90,0.88,0.82), emission_strength=0.4)
M_HORSE_PAINT = mat("hp", (0.62, 0.42, 0.22, 1.0), 0.0, 0.65)
HORSE_COLORS = [M_HORSE_BROWN, M_HORSE_BLACK, M_HORSE_WHITE, M_HORSE_PAINT]
M_MANE = mat("mn", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)
M_HOOF = mat("hf", (0.12, 0.10, 0.08, 1.0), 0.2, 0.45)

# Saddle (signature western)
M_SADDLE_LEATHER = mat("sl", (0.55, 0.32, 0.15, 1.0), 0.3, 0.45, emission=(0.52,0.30,0.15), emission_strength=0.3)
M_SADDLE_HORN = mat("sh", (0.45, 0.22, 0.10, 1.0), 0.3, 0.45)
M_STIRRUP = mat("sti", (0.85, 0.85, 0.85, 1.0), 0.8, 0.20)

# Brahman bull (signature hump)
M_BULL_GRAY = mat("bg", (0.62, 0.55, 0.48, 1.0), 0.0, 0.65, emission=(0.60,0.55,0.48), emission_strength=0.3)
M_BULL_HUMP = mat("bh", (0.78, 0.68, 0.55, 1.0), 0.0, 0.65, emission=(0.75,0.65,0.55), emission_strength=0.4)
M_BULL_HORN = mat("bhrn", (0.92, 0.88, 0.78, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.75), emission_strength=0.4)

# Rope
M_ROPE = mat("rp", (0.92, 0.78, 0.45, 1.0), 0.0, 0.75, emission=(0.88,0.75,0.45), emission_strength=0.4)

# Wood
M_WOOD = mat("w", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85, emission=(0.52,0.30,0.15), emission_strength=0.3)
M_WOOD_DARK = mat("wd", (0.32, 0.18, 0.10, 1.0), 0.0, 0.92)
M_WOOD_LIGHT = mat("wl", (0.78, 0.55, 0.30, 1.0), 0.0, 0.75)

# Saguaro cactus
M_CACTUS = mat("c", (0.30, 0.55, 0.30, 1.0), 0.0, 0.75, emission=(0.28,0.52,0.30), emission_strength=0.4)
M_SPINE = mat("sp_c", (0.85, 0.75, 0.45, 1.0), 0.0, 0.55)

# Texas flag (signature lone star)
M_FLAG_BLUE = mat("fb", (0.10, 0.32, 0.65, 1.0), 0.0, 0.45, emission=(0.10,0.30,0.62), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_FLAG_RED = mat("fr_t", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=1.0)
M_FLAG_STAR = mat("fs", (0.95, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.88), emission_strength=3.0)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Lasso particles (signature)
M_LASSO_PT = mat("lpt", (0.92, 0.78, 0.45, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.45), emission_strength=2.0)
M_LASSO_PT_DARK = mat("lptd", (0.65, 0.48, 0.25, 1.0), 0.0, 0.65, emission=(0.62,0.48,0.25), emission_strength=1.5)

# Sheriff star (signature)
M_STAR_SILVER = mat("ss_st", (0.92, 0.92, 0.92, 1.0), 0.95, 0.05, emission=(0.88,0.88,0.88), emission_strength=3.0)
M_STAR_GOLD = mat("sg_st", (1.0, 0.85, 0.20, 1.0), 0.95, 0.05, emission=(0.95,0.82,0.20), emission_strength=3.5)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=12, segs=24, rings=18, loc=(0, 100, 18), mat_=M_SUN)
for sh in range(4):
    smooth_sphere(f"sun_h{sh}", r=12 + sh*1.3, segs=24, rings=18, loc=(0, 100, 18), mat_=M_SUN)

# ============ ONE clean western dust ground ============
ground = beveled_cube("ground", (280, 280, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_DUST)
# Dust bumps
for hi in range(200):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 130)
    smooth_sphere(f"dn{hi}", r=random.uniform(1.0, 2.5), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.12),
                  mat_=M_DUST_DARK if hi % 3 == 0 else M_DUST_LIGHT, scale=(1.4, 1.3, 0.20))
# Rocks scattered
for ri in range(60):
    a = random.uniform(0, math.pi*2); rad = random.uniform(20, 110)
    smooth_sphere(f"rk{ri}", r=random.uniform(0.4, 0.9), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_ROCK, scale=(1.4, 1.3, 0.5))

# ============ CORRAL FENCE (signature wooden) ============
corral_e = empty("corral", (0, 0, 0))
# Circular corral fence
n_posts = 30
corral_radius = 22
for pi in range(n_posts):
    pa = (pi / n_posts) * math.pi * 2
    px = math.cos(pa) * corral_radius
    py = math.sin(pa) * corral_radius
    # Vertical post
    cyl(f"co_p{pi}", r=0.12, depth=2.5, segs=8, loc=(px, py, 1.25),
        parent=corral_e, mat_=M_WOOD_DARK)
    # 2 horizontal rails between posts
    if pi < n_posts - 1:
        pa_next = ((pi + 1) / n_posts) * math.pi * 2
        px_n = math.cos(pa_next) * corral_radius
        py_n = math.sin(pa_next) * corral_radius
        mid_x = (px + px_n) / 2
        mid_y = (py + py_n) / 2
        rail_e = empty(f"co_r{pi}_e", (mid_x, mid_y, 0), parent=corral_e)
        rail_e.rotation_euler = (0, 0, pa + math.pi/2 - math.pi/n_posts)
        # Top rail
        beveled_cube(f"co_r{pi}_t", (2 * math.pi * corral_radius / n_posts, 0.15, 0.10), bevel_offset=0.02,
                     loc=(0, 0, 1.80), parent=rail_e, mat_=M_WOOD)
        # Middle rail
        beveled_cube(f"co_r{pi}_m", (2 * math.pi * corral_radius / n_posts, 0.15, 0.10), bevel_offset=0.02,
                     loc=(0, 0, 1.20), parent=rail_e, mat_=M_WOOD)
        # Bottom rail
        beveled_cube(f"co_r{pi}_b", (2 * math.pi * corral_radius / n_posts, 0.15, 0.10), bevel_offset=0.02,
                     loc=(0, 0, 0.60), parent=rail_e, mat_=M_WOOD)

# ============ WESTERN SALOON (signature) ============
saloon_e = empty("saloon", (-35, 25, 0))
# Main building
beveled_cube("sa_b", (10, 6, 5), bevel_offset=0.10, loc=(0, 0, 2.5),
             parent=saloon_e, mat_=M_WOOD)
# Wood planks (signature horizontal)
for pli in range(10):
    pli_z = 0.3 + pli * 0.50
    beveled_cube(f"sa_pl{pli}", (10.05, 0.06, 0.35), bevel_offset=0.02,
                 loc=(0, -3.05, pli_z), parent=saloon_e, mat_=M_WOOD_DARK)
# Saloon false-front facade (signature high front)
beveled_cube("sa_ff", (10, 0.30, 2.5), bevel_offset=0.10, loc=(0, -3.05, 5.5),
             parent=saloon_e, mat_=M_WOOD)
# Roof flat
beveled_cube("sa_rf", (10.5, 6.5, 0.30), bevel_offset=0.08, loc=(0, 0, 5.15),
             parent=saloon_e, mat_=M_WOOD_DARK)
# Swinging double doors (signature)
for side in (-1, 1):
    beveled_cube(f"sa_d{side}", (1.0, 0.10, 1.8), bevel_offset=0.05,
                 loc=(side*0.55, -3.10, 0.90), parent=saloon_e, mat_=M_WOOD_DARK)
# Door slats
for side in (-1, 1):
    for di_s in range(5):
        beveled_cube(f"sa_ds{side}_{di_s}", (0.90, 0.04, 0.10), bevel_offset=0.01,
                     loc=(side*0.55, -3.14, 0.20 + di_s*0.35), parent=saloon_e, mat_=M_WOOD_LIGHT)
# Big SALOON sign (signature)
beveled_cube("sa_sn", (5, 0.06, 0.8), bevel_offset=0.04, loc=(0, -3.15, 4.5),
             parent=saloon_e, mat_=M_WOOD_DARK)
# Sign text simulation (5 vertical bars to represent SALOON)
for ti in range(5):
    beveled_cube(f"sa_sn_t{ti}", (0.30, 0.08, 0.50), bevel_offset=0.02,
                 loc=(-1.5 + ti*0.75, -3.20, 4.5), parent=saloon_e, mat_=M_WOOD_LIGHT)
# Hitching post (for horses)
hitching_e = empty("sa_hp", (0, -4.5, 0), parent=saloon_e)
cyl("sa_hp_p1", r=0.10, depth=1.5, segs=8, loc=(-1.5, 0, 0.75), parent=hitching_e, mat_=M_WOOD_DARK)
cyl("sa_hp_p2", r=0.10, depth=1.5, segs=8, loc=(1.5, 0, 0.75), parent=hitching_e, mat_=M_WOOD_DARK)
beveled_cube("sa_hp_r", (3.2, 0.10, 0.10), bevel_offset=0.02, loc=(0, 0, 1.30), parent=hitching_e, mat_=M_WOOD)
# Windows
for wi in (-1, 1):
    beveled_cube(f"sa_w{wi}", (1.2, 0.06, 1.2), bevel_offset=0.04,
                 loc=(wi*2.8, -3.05, 2.8), parent=saloon_e, mat_=M_WOOD_LIGHT)
# Window cross
for wi in (-1, 1):
    beveled_cube(f"sa_wxv{wi}", (0.06, 0.08, 1.2), bevel_offset=0.01,
                 loc=(wi*2.8, -3.08, 2.8), parent=saloon_e, mat_=M_WOOD_DARK)
    beveled_cube(f"sa_wxh{wi}", (1.2, 0.08, 0.06), bevel_offset=0.01,
                 loc=(wi*2.8, -3.08, 2.8), parent=saloon_e, mat_=M_WOOD_DARK)

# ============ BRAHMAN BULL (signature rodeo) ============
bull_e = empty("bull", (0, -5, 0))
bull_e.rotation_euler = (0, 0, math.radians(45))
# Body (muscular)
smooth_sphere("bu_bo", r=0.95, segs=14, rings=12, loc=(0, 0, 1.30),
              parent=bull_e, mat_=M_BULL_GRAY, scale=(1.7, 0.85, 0.85))
# Hump (signature brahman)
smooth_sphere("bu_hu", r=0.55, segs=14, rings=12, loc=(0.45, 0, 1.85),
              parent=bull_e, mat_=M_BULL_HUMP, scale=(1.2, 0.95, 1.2))
# Belly
smooth_sphere("bu_be", r=0.85, segs=12, rings=10, loc=(0, 0, 1.05),
              parent=bull_e, mat_=M_BULL_GRAY, scale=(1.6, 0.85, 0.55))
# Head (massive)
head_b_e = empty("bu_he", (1.10, 0, 1.60), parent=bull_e)
head_b_e.rotation_euler = (0, math.radians(-20), 0)
smooth_sphere("bu_h", r=0.45, segs=14, rings=12, loc=(0, 0, 0),
              parent=head_b_e, mat_=M_BULL_GRAY, scale=(1.4, 0.95, 1.0))
# Snout
smooth_sphere("bu_sn", r=0.30, segs=12, rings=10, loc=(0.30, 0, -0.15),
              parent=head_b_e, mat_=M_BULL_HUMP, scale=(1.2, 0.85, 0.75))
# Nostrils
for side in (-1, 1):
    smooth_sphere(f"bu_no{side}", r=0.05, loc=(0.40, side*0.10, -0.18),
                  parent=head_b_e, mat_=M_HORSE_BLACK)
# HUGE HORNS (signature curved upward)
for side in (-1, 1):
    horn_e = empty(f"bu_hn{side}_e", (0, side*0.30, 0.20), parent=head_b_e)
    horn_e.rotation_euler = (0, math.radians(side*40), 0)
    # Curved horn
    for hi in range(8):
        ha = (hi / 8.0) * math.pi * 0.6
        cyl(f"bu_hn{side}_{hi}", r=0.10 - hi*0.008, depth=0.18, segs=10,
            loc=(math.sin(ha)*0.10, 0, math.cos(ha)*0.10 + hi*0.18),
            parent=horn_e, mat_=M_BULL_HORN)
    # Pointed tip
    smooth_cone(f"bu_hn{side}_t", r1=0.04, r2=0.01, depth=0.20, segs=8,
                loc=(0.7, 0, 1.5), parent=horn_e, mat_=M_BULL_HORN)
# Eyes (signature angry)
for side in (-1, 1):
    smooth_sphere(f"bu_ey{side}", r=0.05,
                  loc=(0.10, side*0.20, 0.05),
                  parent=head_b_e, mat_=M_HORSE_BLACK)
# Ears (large droopy signature brahman)
for side in (-1, 1):
    ear_e = empty(f"bu_er{side}", (-0.10, side*0.30, 0.15), parent=head_b_e)
    ear_e.rotation_euler = (0, 0, math.radians(side*60))
    smooth_sphere(f"bu_er{side}_b", r=0.18, segs=12, rings=8,
                  loc=(0.10, 0, -0.10), parent=ear_e, mat_=M_BULL_GRAY, scale=(0.4, 1.0, 1.2))
# 4 legs
for li_b, (lx_b, ly_b) in enumerate([(0.75, 0.40), (0.75, -0.40), (-0.75, 0.40), (-0.75, -0.40)]):
    leg_e = empty(f"bu_le{li_b}", (lx_b, ly_b, 1.00), parent=bull_e)
    cyl(f"bu_ul{li_b}", r=0.18, depth=0.55, segs=10, loc=(0, 0, -0.28),
        parent=leg_e, mat_=M_BULL_GRAY)
    cyl(f"bu_ll{li_b}", r=0.16, depth=0.45, segs=10, loc=(0, 0, -0.80),
        parent=leg_e, mat_=M_BULL_GRAY)
    # Hoof
    cyl(f"bu_hf{li_b}", r=0.18, depth=0.10, segs=10, loc=(0, 0, -1.05),
        parent=leg_e, mat_=M_HOOF)
# Tail
tail_e = empty("bu_te", (-1.50, 0, 1.50), parent=bull_e)
tail_e.rotation_euler = (0, math.radians(80), 0)
for ti in range(8):
    cyl(f"bu_t{ti}", r=0.08 - ti*0.005, depth=0.12, segs=8,
        loc=(0, 0, ti*0.12), parent=tail_e, mat_=M_BULL_GRAY)
smooth_sphere("bu_tu", r=0.12, segs=10, rings=8, loc=(0, 0, 1.0),
              parent=tail_e, mat_=M_BULL_HUMP)
bull_e["_phase"] = 0

# ============ 4 HORSES with SADDLES ============
def make_western_horse(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    horse_col = random.choice(HORSE_COLORS)
    # Body
    smooth_sphere(f"{name}_bo", r=0.65, segs=14, rings=12, loc=(0, 0, 1.30),
                  parent=base, mat_=horse_col, scale=(1.6, 0.85, 0.85))
    # Chest
    smooth_sphere(f"{name}_ch", r=0.55, segs=14, rings=10, loc=(0.75, 0, 1.30),
                  parent=base, mat_=horse_col, scale=(0.85, 0.85, 0.85))
    # Long neck
    neck_e = empty(f"{name}_ne", (0.90, 0, 1.55), parent=base)
    neck_e.rotation_euler = (0, math.radians(-25), 0)
    smooth_sphere(f"{name}_n", r=0.22, segs=14, rings=10, loc=(0, 0, 0.35),
                  parent=neck_e, mat_=horse_col, scale=(1, 1, 2.5))
    # Head
    head_h_e = empty(f"{name}_he", (0, 0, 1.0), parent=neck_e)
    smooth_sphere(f"{name}_h", r=0.22, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_h_e, mat_=horse_col, scale=(1.5, 0.85, 0.85))
    # Snout
    smooth_sphere(f"{name}_sn", r=0.16, segs=12, rings=10, loc=(0.25, 0, -0.05),
                  parent=head_h_e, mat_=horse_col)
    # Ears
    for side in (-1, 1):
        smooth_cone(f"{name}_e{side}", r1=0.06, r2=0.01, depth=0.20, segs=8,
                    loc=(-0.05, side*0.12, 0.25), parent=head_h_e, mat_=horse_col)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.04, loc=(0.08, side*0.15, 0.04),
                      parent=head_h_e, mat_=M_EYE)
    # Mane
    for mi in range(20):
        mx = 0.80 - mi * 0.10
        mz = 1.70 - mi * 0.05
        cyl(f"{name}_m{mi}", r=0.04, depth=0.20, segs=6,
            loc=(mx, 0, mz), parent=base, mat_=M_MANE)
    # SADDLE (signature western with horn)
    saddle_e = empty(f"{name}_sa", (0, 0, 1.85), parent=base)
    # Saddle seat
    beveled_cube(f"{name}_sa_s", (0.85, 0.85, 0.15), bevel_offset=0.06,
                 loc=(0, 0, 0), parent=saddle_e, mat_=M_SADDLE_LEATHER)
    # Saddle pommel (front raised)
    smooth_sphere(f"{name}_sa_p", r=0.18, segs=12, rings=10, loc=(0.35, 0, 0.10),
                  parent=saddle_e, mat_=M_SADDLE_LEATHER)
    # SADDLE HORN (signature)
    cyl(f"{name}_sa_h", r=0.06, depth=0.15, segs=10, loc=(0.45, 0, 0.18),
        parent=saddle_e, mat_=M_SADDLE_HORN)
    smooth_sphere(f"{name}_sa_h_b", r=0.08, segs=12, rings=10, loc=(0.45, 0, 0.28),
                  parent=saddle_e, mat_=M_SADDLE_HORN)
    # Cantle back
    smooth_sphere(f"{name}_sa_c", r=0.20, segs=12, rings=10, loc=(-0.35, 0, 0.10),
                  parent=saddle_e, mat_=M_SADDLE_LEATHER)
    # Stirrups (signature hanging)
    for side in (-1, 1):
        beveled_cube(f"{name}_sa_st{side}", (0.18, 0.06, 0.20), bevel_offset=0.04,
                     loc=(0, side*0.50, -0.50), parent=saddle_e, mat_=M_STIRRUP)
        # Leather strap
        beveled_cube(f"{name}_sa_str{side}", (0.04, 0.04, 0.45), bevel_offset=0.005,
                     loc=(0, side*0.50, -0.25), parent=saddle_e, mat_=M_SADDLE_LEATHER)
    # Tail
    tail_e = empty(f"{name}_te", (-0.80, 0, 1.30), parent=base)
    for ti in range(8):
        cyl(f"{name}_t{ti}", r=0.06 - ti*0.005, depth=0.15, segs=8,
            loc=(-ti*0.08, 0, -ti*0.05), parent=tail_e, mat_=M_MANE)
    # 4 legs
    for li, (lx, ly) in enumerate([(0.55, 0.30), (0.55, -0.30), (-0.55, 0.30), (-0.55, -0.30)]):
        leg_e = empty(f"{name}_le{li}", (lx, ly, 0.95), parent=base)
        cyl(f"{name}_ul{li}", r=0.10, depth=0.50, segs=10, loc=(0, 0, -0.25),
            parent=leg_e, mat_=horse_col)
        cyl(f"{name}_ll{li}", r=0.08, depth=0.45, segs=10, loc=(0, 0, -0.72),
            parent=leg_e, mat_=horse_col)
        cyl(f"{name}_hf{li}", r=0.10, depth=0.10, segs=10, loc=(0, 0, -0.95),
            parent=leg_e, mat_=M_HOOF)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_h_e}

horses = []
horse_pos = [(-30, -10, math.radians(45)), (30, -10, math.radians(-45)),
              (-25, 10, math.radians(20)), (25, 15, math.radians(-30))]
for i, (hx, hy, fac) in enumerate(horse_pos):
    h = make_western_horse(f"hr{i}", (hx, hy, 0), facing=fac)
    horses.append(h)

# ============ 4 COWBOYS (signature) ============
def make_cowboy(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    shirt_col = random.choice(SHIRT_COLORS)
    # Shirt
    smooth_cone(f"{name}_sh", r1=0.32, r2=0.34, depth=0.85, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=shirt_col)
    # Belt
    cyl(f"{name}_be", r=0.36, depth=0.08, segs=14, loc=(0, 0, 0.85),
        parent=base, mat_=M_LEATHER_DARK)
    # BELT BUCKLE (signature large silver/gold)
    buckle_col = M_BUCKLE_GOLD if random.random() > 0.5 else M_BUCKLE_SILVER
    beveled_cube(f"{name}_bb", (0.18, 0.10, 0.15), bevel_offset=0.03,
                 loc=(0, -0.32, 0.85), parent=base, mat_=buckle_col)
    # Star on buckle (signature)
    star_e = empty(f"{name}_bs", (0, -0.38, 0.85), parent=base)
    for sp in range(5):
        spa = (sp / 5.0) * math.pi * 2 + math.pi/2
        beveled_cube(f"{name}_bs_p{sp}", (0.02, 0.04, 0.07), bevel_offset=0.005,
                     loc=(math.cos(spa)*0.05, 0, math.sin(spa)*0.05),
                     parent=star_e, mat_=M_STAR_GOLD).rotation_euler = (spa - math.pi/2, 0, 0)
    # Pants (denim signature blue)
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.11, depth=0.95, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=M_SHIRT_BLUE)
    # LEATHER CHAPS (signature with fringe)
    for side in (-1, 1):
        chaps_e = empty(f"{name}_ch{side}_e", (side*0.13, -0.05, 0.45), parent=base)
        # Main chap leg
        cyl(f"{name}_ch{side}", r=0.13, depth=0.85, segs=10, loc=(0, 0, 0),
            parent=chaps_e, mat_=M_LEATHER_BROWN)
        # Fringe (signature)
        for fi in range(8):
            fa = math.radians(180) + (fi / 8.0 - 0.5) * math.pi * 0.5
            beveled_cube(f"{name}_fr{side}_{fi}", (0.025, 0.025, 0.25), bevel_offset=0.005,
                         loc=(math.cos(fa)*0.13, math.sin(fa)*0.13, -0.35),
                         parent=chaps_e, mat_=M_FRINGE)
    # Boots
    for side in (-1, 1):
        beveled_cube(f"{name}_b{side}", (0.13, 0.30, 0.18), bevel_offset=0.03,
                     loc=(side*0.13, 0.04, 0.09), parent=base, mat_=M_BOOT_BROWN)
        # Boot heel
        beveled_cube(f"{name}_bh{side}", (0.10, 0.10, 0.08), bevel_offset=0.01,
                     loc=(side*0.13, -0.10, 0.04), parent=base, mat_=M_BOOT_BROWN)
        # Spurs (signature)
        cyl(f"{name}_sp{side}", r=0.04, depth=0.04, segs=10,
            loc=(side*0.13, -0.20, 0.10), parent=base, mat_=M_BUCKLE_SILVER).rotation_euler = (math.radians(90), 0, 0)
        # Spur points (rowel)
        for sri in range(8):
            sra = (sri / 8.0) * math.pi * 2
            beveled_cube(f"{name}_sp{side}_r{sri}", (0.04, 0.01, 0.04), bevel_offset=0.005,
                         loc=(side*0.13, -0.20, 0.10),
                         parent=base, mat_=M_BUCKLE_SILVER).rotation_euler = (math.radians(90), sra, 0)
    # Arms (one holding lasso)
    sh_l = empty(f"{name}_a0", (-0.32, 0, 1.60), parent=base)
    sh_l.rotation_euler = (math.radians(-60), 0, math.radians(20))
    cyl(f"{name}_ua0", r=0.08, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=shirt_col)
    cyl(f"{name}_fa0", r=0.07, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_SKIN_TAN)
    sh_r = empty(f"{name}_a1", (0.32, 0, 1.60), parent=base)
    sh_r.rotation_euler = (math.radians(-100), 0, math.radians(-30))
    cyl(f"{name}_ua1", r=0.08, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=shirt_col)
    cyl(f"{name}_fa1", r=0.07, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_SKIN_TAN)
    # LASSO in hand (signature coiled)
    lasso_e = empty(f"{name}_la", (0.20, 0, -0.75), parent=sh_r)
    # Coiled rope
    for li_l in range(5):
        cyl(f"{name}_la_c{li_l}", r=0.18 - li_l*0.02, depth=0.04, segs=14,
            loc=(0, 0, li_l*0.04), parent=lasso_e, mat_=M_ROPE)
    lasso_e["_phase"] = random.uniform(0, math.pi*2)
    # Head
    head_c_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_c_e, mat_=M_SKIN_TAN)
    # Bandana around neck (signature)
    if random.random() > 0.4:
        bandana_col = random.choice([M_SHIRT_RED, M_SHIRT_BLUE])
        beveled_cube(f"{name}_bn", (0.40, 0.06, 0.20), bevel_offset=0.04,
                     loc=(0, -0.20, -0.20), parent=head_c_e, mat_=bandana_col)
    # Hair
    for hi in range(10):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.08, segs=6,
            loc=(math.cos(ha)*0.13, math.sin(ha)*0.10, 0.10),
            parent=head_c_e, mat_=M_HAIR_BROWN)
    # Mustache
    if random.random() > 0.3:
        beveled_cube(f"{name}_mu", (0.12, 0.04, 0.025), bevel_offset=0.005,
                     loc=(0, -0.17, -0.04), parent=head_c_e, mat_=M_HAIR_BROWN)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_c_e, mat_=M_EYE)
    # STETSON HAT (signature)
    hat_e = empty(f"{name}_ha", (0, 0, 0.22), parent=head_c_e)
    # Crown
    cyl(f"{name}_ha_c", r=0.22, depth=0.20, segs=18, loc=(0, 0, 0),
        parent=hat_e, mat_=M_STETSON)
    # Curved crown top (signature)
    smooth_sphere(f"{name}_ha_t", r=0.20, segs=14, rings=10, loc=(0, 0, 0.10),
                  parent=hat_e, mat_=M_STETSON, scale=(1, 1, 0.6))
    # Brim (wide signature curved up at sides)
    cyl(f"{name}_ha_b", r=0.42, depth=0.04, segs=18, loc=(0, 0, -0.10),
        parent=hat_e, mat_=M_STETSON)
    # Curved up brim sides
    for side in (-1, 1):
        beveled_cube(f"{name}_ha_bu{side}", (0.10, 0.42, 0.06), bevel_offset=0.02,
                     loc=(side*0.32, 0, -0.05), parent=hat_e, mat_=M_STETSON).rotation_euler = (math.radians(15), 0, 0)
    # Hat band (signature)
    cyl(f"{name}_ha_bd", r=0.23, depth=0.04, segs=18, loc=(0, 0, -0.05),
        parent=hat_e, mat_=M_STETSON_BAND)
    # Sheriff star on hat (signature)
    if random.random() > 0.6:
        star_h_e = empty(f"{name}_sh_s", (0, -0.22, 0), parent=hat_e)
        for sp in range(5):
            spa = (sp / 5.0) * math.pi * 2 + math.pi/2
            beveled_cube(f"{name}_sh_s_p{sp}", (0.02, 0.04, 0.07), bevel_offset=0.005,
                         loc=(math.cos(spa)*0.05, 0, math.sin(spa)*0.05),
                         parent=star_h_e, mat_=M_STAR_SILVER).rotation_euler = (spa - math.pi/2, 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_c_e, "lasso": lasso_e}

cowboys = []
cowboy_pos = [(-20, -5, math.radians(60)), (20, -5, math.radians(-60)),
               (-18, 18, math.radians(20)), (18, 18, math.radians(-20))]
for i, (cx, cy, fac) in enumerate(cowboy_pos):
    c = make_cowboy(f"cb{i}", (cx, cy, 0), facing=fac)
    cowboys.append(c)

# ============ SAGUARO CACTI (signature southwestern) ============
def make_saguaro(name, loc, scale=1.0):
    base = empty(name, loc)
    # Main trunk
    cyl(f"{name}_t", r=0.55, depth=8, segs=14, loc=(0, 0, 4),
        parent=base, mat_=M_CACTUS)
    # Vertical ribs (signature)
    for ri in range(12):
        ra = (ri / 12.0) * math.pi * 2
        cyl(f"{name}_r{ri}", r=0.04, depth=7.8, segs=6,
            loc=(math.cos(ra)*0.55, math.sin(ra)*0.55, 4),
            parent=base, mat_=M_CACTUS)
    # Top rounded
    smooth_sphere(f"{name}_top", r=0.50, segs=14, rings=10, loc=(0, 0, 8),
                  parent=base, mat_=M_CACTUS, scale=(1, 1, 0.7))
    # Arm branches (signature 2-3 raised arms)
    for ai_a in range(random.randint(2, 3)):
        aa_a = (ai_a / 3.0) * math.pi * 2
        arm_e = empty(f"{name}_a{ai_a}_e", (math.cos(aa_a)*0.55, math.sin(aa_a)*0.55, 4), parent=base)
        # Lower part curving outward
        for sai in range(4):
            cyl(f"{name}_a{ai_a}_l{sai}", r=0.30, depth=0.50, segs=12,
                loc=(math.cos(aa_a)*sai*0.25, math.sin(aa_a)*sai*0.25, sai*0.40),
                parent=arm_e, mat_=M_CACTUS).rotation_euler = (0, 0, aa_a)
        # Upper part vertical
        cyl(f"{name}_a{ai_a}_u", r=0.35, depth=3, segs=12,
            loc=(math.cos(aa_a)*0.9, math.sin(aa_a)*0.9, 3),
            parent=arm_e, mat_=M_CACTUS)
        # Top of arm
        smooth_sphere(f"{name}_a{ai_a}_t", r=0.35, segs=12, rings=10,
                      loc=(math.cos(aa_a)*0.9, math.sin(aa_a)*0.9, 4.5),
                      parent=arm_e, mat_=M_CACTUS)
    # Spines all over (signature)
    for si_s in range(40):
        sa = random.uniform(0, math.pi*2)
        sz = random.uniform(0.5, 7.5)
        cyl(f"{name}_sp{si_s}", r=0.015, depth=0.08, segs=4,
            loc=(math.cos(sa)*0.60, math.sin(sa)*0.60, sz),
            parent=base, mat_=M_SPINE)
    return base

for i, (cx_s, cy_s) in enumerate([(-50, 50), (50, 50), (-70, 30), (70, 30), (-45, -45), (45, -45)]):
    make_saguaro(f"cact{i}", (cx_s, cy_s, 0))

# ============ TEXAS FLAG (signature Lone Star) ============
flag_e = empty("flag", (-55, -30, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_WOOD_DARK)
# Blue vertical stripe (left third)
beveled_cube("fl_bv", (1.4, 0.05, 2.5), bevel_offset=0.06, loc=(0.7, 0, 10.5),
             parent=flag_e, mat_=M_FLAG_BLUE)
# White horizontal stripe (top)
beveled_cube("fl_w", (2.7, 0.05, 1.25), bevel_offset=0.06, loc=(2.75, 0, 11.10),
             parent=flag_e, mat_=M_FLAG_WHITE)
# Red horizontal stripe (bottom)
beveled_cube("fl_r", (2.7, 0.05, 1.25), bevel_offset=0.06, loc=(2.75, 0, 9.85),
             parent=flag_e, mat_=M_FLAG_RED)
# LONE STAR (signature single white star)
star_e = empty("fl_st", (0.7, -0.06, 10.5), parent=flag_e)
for sp in range(5):
    spa = (sp / 5.0) * math.pi * 2 + math.pi/2
    beveled_cube(f"fl_st_p{sp}", (0.05, 0.06, 0.45), bevel_offset=0.01,
                 loc=(math.cos(spa)*0.20, 0, math.sin(spa)*0.20),
                 parent=star_e, mat_=M_FLAG_STAR).rotation_euler = (spa - math.pi/2, 0, 0)
smooth_sphere("fl_stc", r=0.12, loc=(0, 0, 0), parent=star_e, mat_=M_FLAG_STAR)
flag_e["_phase"] = 0

# ============================================================
# 600 SWIRLING LASSOS + 400 SHERIFF STARS (PARTICULES SIGNATURES)
# ============================================================
lassos = []
for i in range(600):
    px = random.uniform(-110, 110)
    py = random.uniform(-110, 110)
    pz = random.uniform(2, 22)
    l_col = M_LASSO_PT if i % 2 == 0 else M_LASSO_PT_DARK
    l_e = empty(f"la{i}", (px, py, pz))
    # Lasso loop (simplified torus-like)
    smooth_sphere(f"la{i}_p", r=0.20, segs=10, rings=8,
                  loc=(0, 0, 0), parent=l_e, mat_=l_col, scale=(1, 1, 0.18))
    smooth_sphere(f"la{i}_p2", r=0.16, segs=10, rings=8,
                  loc=(0, 0, 0), parent=l_e, mat_=l_col, scale=(1, 1, 0.15))
    l_e["_phase"] = random.uniform(0, math.pi*2)
    l_e["_base_x"] = px; l_e["_base_z"] = pz
    l_e["_speed"] = random.uniform(0.5, 1.5)
    l_e["_drift"] = random.uniform(0.2, 0.6)
    lassos.append(l_e)

# 400 sheriff stars
stars = []
for i in range(400):
    px = random.uniform(-110, 110)
    py = random.uniform(-110, 110)
    pz = random.uniform(2, 28)
    s_col = M_STAR_SILVER if i % 2 == 0 else M_STAR_GOLD
    s_e = empty(f"st{i}", (px, py, pz))
    # 5-point star
    for sp in range(5):
        spa = (sp / 5.0) * math.pi * 2 + math.pi/2
        beveled_cube(f"st{i}_p{sp}", (0.03, 0.05, 0.15), bevel_offset=0.005,
                     loc=(math.cos(spa)*0.08, math.sin(spa)*0.08, 0),
                     parent=s_e, mat_=s_col).rotation_euler = (0, 0, spa - math.pi/2)
    # Center
    smooth_sphere(f"st{i}_c", r=0.05, loc=(0, 0, 0), parent=s_e, mat_=s_col)
    # Orbs on points (signature)
    for op in range(5):
        opa = (op / 5.0) * math.pi * 2 + math.pi/2
        smooth_sphere(f"st{i}_o{op}", r=0.025,
                      loc=(math.cos(opa)*0.18, math.sin(opa)*0.18, 0),
                      parent=s_e, mat_=s_col)
    s_e["_phase"] = random.uniform(0, math.pi*2)
    s_e["_base_x"] = px; s_e["_base_y"] = py; s_e["_base_z"] = pz
    s_e["_amp_x"] = random.uniform(0.5, 1.5)
    s_e["_amp_y"] = random.uniform(0.5, 1.5)
    s_e["_amp_z"] = random.uniform(0.4, 1.0)
    s_e["_speed"] = random.uniform(0.5, 1.2)
    stars.append(s_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Cowboys sway with lasso swing
for c in cowboys:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        c["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3), 0,
                                     c["root"].rotation_euler.z + math.sin(t * 1.0 + phase) * math.radians(5))
        c["root"].keyframe_insert("rotation_euler", frame=f)
        c["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(4), 0,
                                   math.cos(t * 1.0 + phase) * math.radians(15))
        c["he"].keyframe_insert("rotation_euler", frame=f)
        # Lasso swing
        c["lasso"].rotation_euler = (0, 0, t * 4.0 + phase)
        c["lasso"].keyframe_insert("rotation_euler", frame=f)

# Horses bob
for h in horses:
    phase = h["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        h["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(2), 0,
                                     h["root"].rotation_euler.z)
        h["root"].keyframe_insert("rotation_euler", frame=f)
        h["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                   math.cos(t * 1.2 + phase) * math.radians(10))
        h["he"].keyframe_insert("rotation_euler", frame=f)

# Bull buck (signature rodeo violent buck)
for f in range(1, total_frames + 1, 2):
    t = (f - 1) / fps
    # Violent buck animation
    buck = math.sin(t * 4.0)
    bull_e.rotation_euler = (buck * math.radians(20), math.cos(t * 4.0) * math.radians(15), math.radians(45) + math.sin(t * 3.0) * math.radians(10))
    bull_e.location.z = abs(math.sin(t * 4.0)) * 0.4
    bull_e.keyframe_insert("rotation_euler", frame=f)
    bull_e.keyframe_insert("location", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 lassos swirl
for l in lassos:
    phase = l["_phase"]; speed = l["_speed"]; drift = l["_drift"]
    bx, bz = l["_base_x"], l["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * 3 + t * drift
        z = bz + math.sin(t * speed * 1.3 + phase) * 1.5
        l.location = (x, l.location.y, z)
        l.rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(20), 0, t * 3.0 + phase)
        l.keyframe_insert("location", frame=f)
        l.keyframe_insert("rotation_euler", frame=f)

# 400 sheriff stars float twinkle
for s in stars:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase) + t * 0.4
        s.location = (x, y, z)
        s.rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(15), 0,
                             t * 1.2 + phase)
        # Twinkle scale
        sc = 0.7 + abs(math.sin(t * 5.0 + phase)) * 0.6
        s.scale = (sc, sc, sc)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("rotation_euler", frame=f)
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
out_glb = os.path.join(out_dir, "pbr_texas_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_texas_cowboys_rodeo_corral] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Texas cowboys rodeo: 4 cowboys (signature Stetson hats with curved brim sides + leather chaps with fringe + big silver/gold star belt buckles + denim pants + leather boots with spurs + rowels + bandanas + mustaches + sheriff stars + coiled lassos in hand) + 4 western horses with full western saddles (horn + pommel + cantle + stirrups) + brahman rodeo bull (signature massive hump + huge curved horns + droopy ears + violent buck animation) + circular corral fence with 30 posts and 3 rails + western saloon (signature false-front + swinging doors + planks + SALOON sign + hitching post + windows) + 6 saguaro cacti with arms and spines signature + Texas Lone Star flag + 600 lassos swirling + 400 sheriff stars twinkling")
print("🤠 FIXES: 1 western dust ground + 600 swirling lassos + 400 sheriff stars signature 🤠")
