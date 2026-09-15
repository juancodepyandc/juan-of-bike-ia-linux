"""
proc_capetown_table_mountain_penguins.py — 291e procédural AuroraIA (156e qualité)
Cape Town Table Mountain penguins: signature flat-top mountain + Lion's Head + 6 African penguins + 4 surfers + cable car + Boulders Beach + South Africa rainbow flag + 600 starfish + 400 whale spouts
FIXES : 1 ground cliff ocean + signature starfish + whale spouts
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB291)

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

# Sky African coast
M_SKY = mat("sky", (0.45, 0.72, 0.92, 1.0), 0.0, 0.7, emission=(0.45,0.70,0.90), emission_strength=1.7)
M_SKY_LOW = mat("sky_l", (0.85, 0.92, 0.95, 1.0), 0.0, 0.7, emission=(0.85,0.90,0.92), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.92, 0.65, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.65), emission_strength=16.0)
M_CLOUD = mat("cl", (0.95, 0.95, 0.92, 1.0), 0.0, 0.85, emission=(0.95,0.95,0.92), emission_strength=1.0, alpha=0.85)
# Tablecloth clouds (signature Table Mountain phenomenon)
M_TABLECLOTH = mat("tc", (0.92, 0.95, 0.98, 1.0), 0.0, 0.92, emission=(0.92,0.95,0.98), emission_strength=1.5, alpha=0.75)

# Ground (signature granite cliff)
M_GRANITE = mat("gr", (0.55, 0.50, 0.45, 1.0), 0.0, 0.85, emission=(0.52,0.50,0.45), emission_strength=0.3)
M_GRANITE_DARK = mat("grd", (0.35, 0.32, 0.30, 1.0), 0.0, 0.92)
M_FYNBOS = mat("fy", (0.45, 0.55, 0.32, 1.0), 0.0, 0.65, emission=(0.42,0.52,0.30), emission_strength=0.4)
M_SAND_BEACH = mat("sb", (0.95, 0.85, 0.55, 1.0), 0.0, 0.65, emission=(0.92,0.82,0.55), emission_strength=0.5)

# Ocean Atlantic
M_OCEAN = mat("oc", (0.18, 0.45, 0.75, 1.0), 0.2, 0.20, emission=(0.18,0.45,0.72), emission_strength=1.5, alpha=0.78)
M_OCEAN_DEEP = mat("ocd", (0.10, 0.28, 0.55, 1.0), 0.2, 0.25, alpha=0.85)
M_FOAM = mat("fm", (0.95, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.90), emission_strength=1.5, alpha=0.65)
M_WAVE = mat("wv", (0.55, 0.85, 0.95, 1.0), 0.1, 0.15, emission=(0.55,0.82,0.92), emission_strength=1.2, alpha=0.70)

# Table Mountain (signature flat-top)
M_MOUNTAIN_TAN = mat("mt", (0.65, 0.55, 0.40, 1.0), 0.0, 0.85, emission=(0.62,0.55,0.40), emission_strength=0.3)
M_MOUNTAIN_GRAY = mat("mg", (0.42, 0.42, 0.42, 1.0), 0.0, 0.88)
M_MOUNTAIN_RED = mat("mtr", (0.62, 0.42, 0.32, 1.0), 0.0, 0.85)

# African penguin
M_PENGUIN_BLACK = mat("pb", (0.10, 0.10, 0.12, 1.0), 0.0, 0.45, emission=(0.10,0.10,0.12), emission_strength=0.3)
M_PENGUIN_WHITE = mat("pw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.5)
M_PENGUIN_BEAK = mat("pbk", (0.32, 0.20, 0.10, 1.0), 0.2, 0.45)
M_PENGUIN_PINK = mat("ppk", (0.95, 0.65, 0.55, 1.0), 0.0, 0.55, emission=(0.92,0.62,0.55), emission_strength=0.5)

# Surfer (signature wetsuit)
M_SKIN_TAN = mat("sk", (0.85, 0.65, 0.45, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.45), emission_strength=0.3)
M_HAIR_BLOND = mat("hb", (0.85, 0.72, 0.42, 1.0), 0.0, 0.85)
M_HAIR_BROWN = mat("hbr", (0.42, 0.28, 0.18, 1.0), 0.0, 0.85)
M_WETSUIT_BLACK = mat("wsb", (0.10, 0.10, 0.12, 1.0), 0.3, 0.40)
M_WETSUIT_BLUE = mat("wsbl", (0.18, 0.42, 0.78, 1.0), 0.3, 0.45, emission=(0.18,0.42,0.75), emission_strength=0.4)
WETSUIT_COLORS = [M_WETSUIT_BLACK, M_WETSUIT_BLUE]

# Surfboard
M_BOARD_WHITE = mat("bw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.35, emission=(0.92,0.92,0.90), emission_strength=0.5)
M_BOARD_RED = mat("br", (0.92, 0.20, 0.22, 1.0), 0.0, 0.45, emission=(0.88,0.20,0.22), emission_strength=0.5)
M_BOARD_BLUE = mat("bbl", (0.20, 0.55, 0.85, 1.0), 0.0, 0.45, emission=(0.20,0.55,0.82), emission_strength=0.5)
BOARD_COLORS = [M_BOARD_WHITE, M_BOARD_RED, M_BOARD_BLUE]

# Cable car
M_CABLE_METAL = mat("cm", (0.55, 0.55, 0.58, 1.0), 0.7, 0.30)
M_CABLE_GLASS = mat("cg", (0.35, 0.55, 0.75, 1.0), 0.4, 0.15, emission=(0.32,0.55,0.75), emission_strength=2.0, alpha=0.55)
M_CABLE_RED = mat("cr", (0.85, 0.20, 0.22, 1.0), 0.0, 0.55, emission=(0.82,0.20,0.22), emission_strength=0.5)

# South Africa rainbow flag colors (signature 6 colors)
M_FLAG_BLACK = mat("fb", (0.10, 0.10, 0.12, 1.0), 0.0, 0.45)
M_FLAG_GREEN = mat("fg", (0.18, 0.62, 0.30, 1.0), 0.0, 0.45, emission=(0.18,0.60,0.30), emission_strength=1.0)
M_FLAG_YELLOW = mat("fy_sa", (0.98, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.20), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_FLAG_RED = mat("fr", (0.85, 0.18, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.18), emission_strength=1.0)
M_FLAG_BLUE = mat("fb_sa", (0.18, 0.32, 0.62, 1.0), 0.0, 0.45, emission=(0.18,0.32,0.60), emission_strength=1.0)

# Boulders (Boulders Beach signature)
M_BOULDER = mat("bd", (0.55, 0.50, 0.45, 1.0), 0.0, 0.88)
M_BOULDER_DARK = mat("bdd", (0.32, 0.30, 0.28, 1.0), 0.0, 0.92)

# Starfish (signature 5-arm colorful)
M_STARFISH_RED = mat("sfr", (0.92, 0.30, 0.30, 1.0), 0.0, 0.40, emission=(0.88,0.30,0.30), emission_strength=2.0)
M_STARFISH_ORANGE = mat("sfo", (1.0, 0.55, 0.18, 1.0), 0.0, 0.40, emission=(0.95,0.55,0.18), emission_strength=2.0)
M_STARFISH_PURPLE = mat("sfp", (0.75, 0.30, 0.85, 1.0), 0.0, 0.40, emission=(0.72,0.30,0.82), emission_strength=2.0)
M_STARFISH_PINK = mat("sfpk", (1.0, 0.55, 0.78, 1.0), 0.0, 0.40, emission=(0.95,0.55,0.75), emission_strength=2.0)
M_STARFISH_BLUE = mat("sfbl", (0.30, 0.65, 0.95, 1.0), 0.0, 0.40, emission=(0.30,0.62,0.92), emission_strength=2.0)
STARFISH_COLORS = [M_STARFISH_RED, M_STARFISH_ORANGE, M_STARFISH_PURPLE, M_STARFISH_PINK, M_STARFISH_BLUE]

# Whale spout
M_SPOUT = mat("sp", (0.95, 0.95, 0.98, 1.0), 0.0, 0.10, emission=(0.92,0.92,0.95), emission_strength=2.5, alpha=0.60)
M_SPOUT_BLUE = mat("spb", (0.78, 0.92, 0.98, 1.0), 0.0, 0.10, emission=(0.75,0.90,0.95), emission_strength=2.2, alpha=0.55)
M_WHALE_DARK = mat("wd", (0.18, 0.22, 0.28, 1.0), 0.1, 0.55)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-50, 110, 40), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-50, 110, 40), mat_=M_SUN)
# Clouds
for ci in range(15):
    cx_c = random.uniform(-150, 150); cy_c = random.uniform(-100, 100); cz_c = random.uniform(55, 75)
    cloud_e = empty(f"cl{ci}_e", (cx_c, cy_c, cz_c))
    for cp in range(5):
        cpa = random.uniform(0, math.pi*2); cpr = random.uniform(0, 4)
        smooth_sphere(f"cl{ci}_p{cp}", r=random.uniform(2.5, 4), segs=14, rings=10,
                      loc=(math.cos(cpa)*cpr, math.sin(cpa)*cpr, random.uniform(-1, 1)),
                      parent=cloud_e, mat_=M_CLOUD, scale=(1.5, 1.5, 0.5))

# ============ ONE clean cliff + ocean ground ============
ground = beveled_cube("ground", (300, 300, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_GRANITE)
# Granite outcrops (organic 3D)
for hi in range(150):
    a = random.uniform(0, math.pi*2); rad = random.uniform(5, 130)
    smooth_sphere(f"gr{hi}", r=random.uniform(1.0, 2.5), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_GRANITE_DARK if hi % 3 == 0 else M_GRANITE, scale=(1.4, 1.3, 0.25))
# Fynbos (signature coastal vegetation)
for fi in range(120):
    a = random.uniform(0, math.pi*2); rad = random.uniform(20, 110)
    smooth_sphere(f"fy{fi}", r=random.uniform(0.4, 0.8), segs=10, rings=6,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.20),
                  mat_=M_FYNBOS, scale=(1.3, 1.2, 0.85))
# Sand beach patch (signature Boulders Beach)
beach_e = empty("beach", (0, -55, 0))
for bi in range(40):
    a = random.uniform(0, math.pi); rad = random.uniform(5, 35)
    smooth_sphere(f"bsd{bi}", r=random.uniform(0.5, 1.2), segs=10, rings=6,
                  loc=(rad*math.cos(a) - 30, rad*math.sin(a) * -1, 0.20),
                  parent=beach_e, mat_=M_SAND_BEACH, scale=(1.4, 1.3, 0.20))

# ============ OCEAN ============
ocean_e = empty("ocean", (0, -85, 0))
beveled_cube("oc", (300, 80, 0.20), bevel_offset=0.08, loc=(0, 0, 0.20),
             parent=ocean_e, mat_=M_OCEAN)
beveled_cube("oc_d", (290, 75, 0.15), bevel_offset=0.06, loc=(0, 0, 0.25),
             parent=ocean_e, mat_=M_OCEAN_DEEP)
# Wave foam at shore
for fi in range(50):
    fx = random.uniform(-140, 140); fy = random.uniform(35, 40)
    cyl(f"oc_f{fi}", r=random.uniform(0.5, 1.0), depth=0.05, segs=14,
        loc=(fx, fy, 0.30), parent=ocean_e, mat_=M_FOAM)
# Big waves (signature surfable)
for wi in range(8):
    wx_w = -80 + wi * 20
    beveled_cube(f"oc_w{wi}", (8, 2, 1.2), bevel_offset=0.30, loc=(wx_w, 20, 0.80),
                 parent=ocean_e, mat_=M_WAVE)

# ============ TABLE MOUNTAIN (signature flat-top plateau) ============
table_e = empty("table", (0, 70, 0))
# Slopes leading up
for li in range(8):
    lz = li * 4
    lr = 22 - li * 1.5  # Tapered to top
    smooth_cone(f"tb_l{li}", r1=lr, r2=lr - 1.5, depth=4.5, segs=18,
                loc=(0, 0, lz + 2.25), parent=table_e, mat_=M_MOUNTAIN_TAN)
# FLAT TOP (signature plateau)
beveled_cube("tb_top", (15, 8, 1.5), bevel_offset=0.15, loc=(0, 0, 33),
             parent=table_e, mat_=M_MOUNTAIN_GRAY)
# Sandstone striations (signature)
for si in range(15):
    sz = 5 + si * 2
    beveled_cube(f"tb_s{si}", (40 - si*0.8, 22 - si*0.5, 0.30), bevel_offset=0.04,
                 loc=(0, 0, sz), parent=table_e, mat_=M_MOUNTAIN_RED)
# TABLECLOTH cloud (signature lying over plateau)
tablecloth_e = empty("tb_tc", (0, 0, 35), parent=table_e)
for ti in range(20):
    smooth_sphere(f"tb_tc{ti}", r=random.uniform(3, 5), segs=14, rings=10,
                  loc=(random.uniform(-10, 10), random.uniform(-6, 6), random.uniform(-1, 2)),
                  parent=tablecloth_e, mat_=M_TABLECLOTH, scale=(1.4, 1.4, 0.4))
# Cliff faces (signature vertical)
for ci in range(12):
    ca = (ci / 12.0) * math.pi * 2
    cyl(f"tb_cl{ci}", r=0.50, depth=28, segs=8,
        loc=(math.cos(ca)*16, math.sin(ca)*10, 16), parent=table_e, mat_=M_MOUNTAIN_GRAY)

# ============ LION'S HEAD (signature pointed peak) ============
lions_head_e = empty("lions_head", (-45, 75, 0))
for li in range(7):
    lz = li * 4
    lr_b = 8 - li * 0.9
    lr_t = 7 - (li+1) * 0.9
    smooth_cone(f"lh_{li}", r1=lr_b, r2=lr_t, depth=4.5, segs=14,
                loc=(0, 0, lz + 2.25), parent=lions_head_e, mat_=M_MOUNTAIN_TAN)
# Pointed peak
smooth_cone("lh_pk", r1=0.6, r2=0.05, depth=2.5, segs=10, loc=(0, 0, 30),
            parent=lions_head_e, mat_=M_MOUNTAIN_GRAY)

# ============ CABLE CAR (signature) ============
cable_e = empty("cable", (-20, 20, 0))
# Lower station
beveled_cube("cb_ls", (4, 4, 5), bevel_offset=0.10, loc=(0, 0, 2.5),
             parent=cable_e, mat_=M_CABLE_METAL)
beveled_cube("cb_ls_r", (5, 5, 0.30), bevel_offset=0.06, loc=(0, 0, 5.15),
             parent=cable_e, mat_=M_CABLE_RED)
# Cable
cable_top_pos = (20, 50, 35)
cable_bot_pos = (0, 0, 5)
# Drape line
cable_dist = math.sqrt(sum((cable_top_pos[i] - cable_bot_pos[i])**2 for i in range(3)))
for ci in range(30):
    t = ci / 30.0
    cx = cable_bot_pos[0] + (cable_top_pos[0] - cable_bot_pos[0]) * t
    cy = cable_bot_pos[1] + (cable_top_pos[1] - cable_bot_pos[1]) * t
    cz = cable_bot_pos[2] + (cable_top_pos[2] - cable_bot_pos[2]) * t - math.sin(t * math.pi) * 2
    smooth_sphere(f"cb_c{ci}", r=0.05, loc=(cx, cy, cz),
                  parent=cable_e, mat_=M_CABLE_METAL)
# Cable car (in middle)
car_t = 0.55
car_x = cable_bot_pos[0] + (cable_top_pos[0] - cable_bot_pos[0]) * car_t
car_y = cable_bot_pos[1] + (cable_top_pos[1] - cable_bot_pos[1]) * car_t
car_z = cable_bot_pos[2] + (cable_top_pos[2] - cable_bot_pos[2]) * car_t - math.sin(car_t * math.pi) * 2 - 2
car_e = empty("cb_car", (car_x, car_y, car_z), parent=cable_e)
# Car body
cyl("cb_car_b", r=2, depth=2.5, segs=18, loc=(0, 0, 0), parent=car_e, mat_=M_CABLE_METAL).rotation_euler = (0, 0, 0)
# Windows
for wi in range(8):
    wa = (wi / 8.0) * math.pi * 2
    beveled_cube(f"cb_car_w{wi}", (0.05, 1.0, 1.2), bevel_offset=0.04,
                 loc=(math.cos(wa)*2.05, math.sin(wa)*2.05, 0),
                 parent=car_e, mat_=M_CABLE_GLASS).rotation_euler = (0, 0, wa)
# Top connection
cyl("cb_car_c", r=0.20, depth=1.5, segs=10, loc=(0, 0, 2),
    parent=car_e, mat_=M_CABLE_METAL)
# Red trim
cyl("cb_car_tr", r=2.05, depth=0.10, segs=18, loc=(0, 0, 1.0),
    parent=car_e, mat_=M_CABLE_RED)
cable_e["_car"] = car_e

# Upper station (on Table Mountain)
beveled_cube("cb_us", (5, 5, 3), bevel_offset=0.10, loc=(20, 50, 36.5),
             parent=cable_e, mat_=M_CABLE_METAL)

# ============ BOULDERS BEACH (signature giant granite boulders) ============
for bi in range(8):
    a = random.uniform(0, math.pi); rad = random.uniform(5, 30)
    bx = math.cos(a) * rad - 10
    by = math.sin(a) * rad - 60
    smooth_sphere(f"bd{bi}", r=random.uniform(2.0, 3.5), segs=18, rings=14,
                  loc=(bx, by, 1.5), mat_=M_BOULDER if bi % 2 else M_BOULDER_DARK,
                  scale=(1.2, 1.2, 0.85))

# ============ 6 AFRICAN PENGUINS on beach (signature) ============
def make_african_penguin(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body (smaller than emperor)
    smooth_sphere(f"{name}_bo", r=0.32, segs=14, rings=12, loc=(0, 0, 0.55),
                  parent=base, mat_=M_PENGUIN_BLACK, scale=(0.85, 0.85, 1.4))
    # White belly with signature black band/stripe
    smooth_sphere(f"{name}_be", r=0.28, segs=14, rings=12, loc=(0, -0.08, 0.55),
                  parent=base, mat_=M_PENGUIN_WHITE, scale=(0.85, 0.55, 1.3))
    # Black chest band (signature African penguin)
    smooth_sphere(f"{name}_cb", r=0.30, segs=12, rings=10, loc=(0, -0.05, 0.75),
                  parent=base, mat_=M_PENGUIN_BLACK, scale=(0.85, 0.40, 0.10))
    # Head
    head_p_e = empty(f"{name}_he", (0, 0, 1.15), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_p_e, mat_=M_PENGUIN_BLACK, scale=(0.95, 0.85, 1.0))
    # White face stripe (signature)
    smooth_sphere(f"{name}_fa", r=0.15, segs=12, rings=10, loc=(0, -0.10, 0),
                  parent=head_p_e, mat_=M_PENGUIN_WHITE, scale=(1.2, 0.55, 0.85))
    # Pink eye patches (signature African penguin)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ep{side}", r=0.04,
                      loc=(side*0.08, -0.13, 0.08),
                      parent=head_p_e, mat_=M_PENGUIN_PINK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.08, -0.16, 0.05),
                      parent=head_p_e, mat_=M_EYE)
    # Beak (signature)
    cyl(f"{name}_bk", r=0.04, depth=0.15, segs=10, loc=(0.12, -0.10, -0.05),
        parent=head_p_e, mat_=M_PENGUIN_BEAK).rotation_euler = (0, math.radians(110), 0)
    # Wing flippers
    for side in (-1, 1):
        wing_e = empty(f"{name}_w{side}_e", (side*0.30, 0, 0.75), parent=base)
        wing_e.rotation_euler = (0, math.radians(side*5), math.radians(side*10))
        beveled_cube(f"{name}_w{side}", (0.06, 0.12, 0.50), bevel_offset=0.04,
                     loc=(0, 0, 0), parent=wing_e, mat_=M_PENGUIN_BLACK)
    # Feet pink
    for side in (-1, 1):
        beveled_cube(f"{name}_f{side}", (0.08, 0.18, 0.05), bevel_offset=0.02,
                     loc=(side*0.08, 0.08, 0.03), parent=base, mat_=M_PENGUIN_PINK)
    # Tail short
    beveled_cube(f"{name}_t", (0.15, 0.08, 0.06), bevel_offset=0.02,
                 loc=(0, 0.22, 0.25), parent=base, mat_=M_PENGUIN_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_p_e}

penguins = []
penguin_pos = [(-15, -50, math.radians(20)), (-8, -52, math.radians(0)),
                (0, -50, math.radians(-15)), (8, -52, math.radians(15)),
                (15, -50, math.radians(-30)), (-12, -55, math.radians(45))]
for i, (px, py, fac) in enumerate(penguin_pos):
    p = make_african_penguin(f"pn{i}", (px, py, 0), facing=fac)
    penguins.append(p)

# ============ 4 SURFERS (signature) ============
def make_surfer(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    wetsuit_col = random.choice(WETSUIT_COLORS)
    board_col = random.choice(BOARD_COLORS)
    # Surfboard underneath (signature)
    board_e = empty(f"{name}_bd", (0, 0, -0.10), parent=base)
    smooth_cone(f"{name}_bd_n", r1=0.05, r2=0.30, depth=2.5, segs=10, loc=(0, 0, 0),
                parent=board_e, mat_=board_col).rotation_euler = (0, math.radians(90), math.radians(180))
    beveled_cube(f"{name}_bd_b", (2.4, 0.5, 0.06), bevel_offset=0.05, loc=(0, 0, 0),
                 parent=board_e, mat_=board_col)
    # Body in wetsuit
    smooth_cone(f"{name}_bo", r1=0.28, r2=0.32, depth=0.85, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=wetsuit_col)
    # Legs in wetsuit
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.10, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=wetsuit_col)
    # Bare feet
    for side in (-1, 1):
        beveled_cube(f"{name}_f{side}", (0.09, 0.20, 0.05), bevel_offset=0.01,
                     loc=(side*0.13, 0.04, 0.03), parent=base, mat_=M_SKIN_TAN)
    # Arms (one balancing, one outstretched)
    sh_l = empty(f"{name}_a0", (-0.30, 0, 1.60), parent=base)
    sh_l.rotation_euler = (math.radians(-90), 0, math.radians(60))
    cyl(f"{name}_ua0", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=M_SKIN_TAN)
    cyl(f"{name}_fa0", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_SKIN_TAN)
    sh_r = empty(f"{name}_a1", (0.30, 0, 1.60), parent=base)
    sh_r.rotation_euler = (math.radians(-90), 0, math.radians(-60))
    cyl(f"{name}_ua1", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=M_SKIN_TAN)
    cyl(f"{name}_fa1", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_SKIN_TAN)
    # Head
    head_s_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_s_e, mat_=M_SKIN_TAN)
    # Long wet hair (signature)
    hair_col = random.choice([M_HAIR_BLOND, M_HAIR_BROWN])
    for hi in range(20):
        ha = random.uniform(math.pi*0.5, math.pi*1.5)
        hair_len = random.uniform(0.25, 0.45)
        for hsi in range(int(hair_len * 6)):
            cyl(f"{name}_hr{hi}_{hsi}", r=0.020, depth=0.08, segs=4,
                loc=(math.cos(ha)*0.13, math.sin(ha)*0.10, -hsi*0.08 - 0.08),
                parent=head_s_e, mat_=hair_col)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_s_e, mat_=M_EYE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_s_e}

surfers = []
surfer_pos = [(-30, -70, math.radians(20)), (-10, -75, math.radians(0)),
               (10, -75, math.radians(-10)), (30, -70, math.radians(-30))]
for i, (sx, sy, fac) in enumerate(surfer_pos):
    s = make_surfer(f"sr{i}", (sx, sy, 1.0), facing=fac)
    surfers.append(s)

# ============ SOUTH AFRICA FLAG (signature 6 colors rainbow) ============
flag_e = empty("flag", (-60, -40, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_CABLE_METAL)
# Y-shape signature: green stripe (Y on side, becoming horizontal)
# Left triangle (black with yellow border to red/blue)
# Simplified: vertical bands transition to horizontal
# Y horizontal arms (red top, blue bottom)
beveled_cube("fl_r", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 11.45),
             parent=flag_e, mat_=M_FLAG_RED)
beveled_cube("fl_b", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 9.65),
             parent=flag_e, mat_=M_FLAG_BLUE)
# Green Y center
beveled_cube("fl_g", (3, 0.06, 0.60), bevel_offset=0.04, loc=(2.5, -0.01, 10.5),
             parent=flag_e, mat_=M_FLAG_GREEN)
# White borders on green
beveled_cube("fl_w_t", (3, 0.07, 0.10), bevel_offset=0.02, loc=(2.5, -0.005, 10.85),
             parent=flag_e, mat_=M_FLAG_WHITE)
beveled_cube("fl_w_b", (3, 0.07, 0.10), bevel_offset=0.02, loc=(2.5, -0.005, 10.15),
             parent=flag_e, mat_=M_FLAG_WHITE)
# Yellow chevron (signature)
beveled_cube("fl_y", (1.5, 0.07, 0.45), bevel_offset=0.04, loc=(0.75, -0.01, 10.5),
             parent=flag_e, mat_=M_FLAG_YELLOW)
# Black left triangle
black_e = empty("fl_bk", (0.7, -0.06, 10.5), parent=flag_e)
for bi in range(8):
    bi_t = bi / 8.0
    bw = 1.4 * (1 - bi_t)
    beveled_cube(f"fl_bk_t{bi}", (bw, 0.04, 0.20), bevel_offset=0.02,
                 loc=(bw/2 - 0.7, 0, (bi - 4) * 0.15), parent=black_e, mat_=M_FLAG_BLACK)
flag_e["_phase"] = 0

# ============================================================
# 600 STARFISH MULTICOLORS + 400 WHALE SPOUTS (PARTICULES SIGNATURES)
# ============================================================
starfish = []
for i in range(600):
    px = random.uniform(-130, 130)
    py = random.uniform(-100, 0)
    pz = random.uniform(0.5, 8)
    sf_col = random.choice(STARFISH_COLORS)
    sf_e = empty(f"sf{i}", (px, py, pz))
    # 5-arm star
    for arm in range(5):
        aa = (arm / 5.0) * math.pi * 2 + math.pi/2
        beveled_cube(f"sf{i}_a{arm}", (0.05, 0.12, 0.04), bevel_offset=0.01,
                     loc=(math.cos(aa)*0.08, math.sin(aa)*0.08, 0),
                     parent=sf_e, mat_=sf_col).rotation_euler = (0, 0, aa - math.pi/2)
    # Center bump
    smooth_sphere(f"sf{i}_c", r=0.05, loc=(0, 0, 0.02), parent=sf_e, mat_=sf_col)
    sf_e["_phase"] = random.uniform(0, math.pi*2)
    sf_e["_base_x"] = px; sf_e["_base_y"] = py; sf_e["_base_z"] = pz
    sf_e["_amp_x"] = random.uniform(1, 3)
    sf_e["_amp_y"] = random.uniform(1, 3)
    sf_e["_amp_z"] = random.uniform(0.3, 1.0)
    sf_e["_speed"] = random.uniform(0.3, 0.8)
    starfish.append(sf_e)

# 400 whale spouts (with whale body silhouettes underneath)
spouts = []
for i in range(400):
    px = random.uniform(-130, 130)
    py = random.uniform(-100, -50)
    pz = 0.4
    sp_e = empty(f"sp{i}", (px, py, pz))
    # Whale back (signature dark)
    smooth_sphere(f"sp{i}_w", r=0.30, segs=12, rings=8, loc=(0, 0, 0.10),
                  parent=sp_e, mat_=M_WHALE_DARK, scale=(2.0, 0.85, 0.45))
    # SPOUT (signature V-shape water plume)
    sp_col = M_SPOUT if i % 2 == 0 else M_SPOUT_BLUE
    for sji in range(8):
        sji_t = sji / 8.0
        # V-spread spout
        for ss in (-1, 1):
            cyl(f"sp{i}_w{sji}_{ss}", r=0.06 - sji*0.005, depth=0.20, segs=8,
                loc=(ss * sji * 0.10, 0, 0.30 + sji*0.25),
                parent=sp_e, mat_=sp_col).rotation_euler = (0, math.radians(ss*5), 0)
    sp_e["_phase"] = random.uniform(0, math.pi*2)
    sp_e["_base_x"] = px; sp_e["_base_y"] = py
    sp_e["_speed"] = random.uniform(0.3, 0.8)
    sp_e["_pulse"] = random.uniform(2, 5)
    spouts.append(sp_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Penguins waddle
for p in penguins:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        p["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3), 0,
                                     p["root"].rotation_euler.z)
        p["root"].location.z = abs(math.sin(t * 2.0 + phase)) * 0.05
        p["root"].keyframe_insert("rotation_euler", frame=f)
        p["root"].keyframe_insert("location", frame=f)
        p["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                   math.cos(t * 1.0 + phase) * math.radians(15))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Surfers balance (sway on board)
for s in surfers:
    phase = s["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s["root"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(5), 0,
                                     s["root"].rotation_euler.z + math.sin(t * 1.5 + phase) * math.radians(8))
        s["root"].location.z = 1.0 + math.sin(t * 1.5 + phase) * 0.15
        s["root"].keyframe_insert("rotation_euler", frame=f)
        s["root"].keyframe_insert("location", frame=f)
        s["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0, 0)
        s["he"].keyframe_insert("rotation_euler", frame=f)

# Cable car sway
phase_c = 0
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    cable_e["_car"].location.z = car_z + math.sin(t * 1.0) * 0.15
    cable_e["_car"].rotation_euler = (0, math.sin(t * 0.8) * math.radians(3), math.sin(t * 0.5) * math.radians(2))
    cable_e["_car"].keyframe_insert("location", frame=f)
    cable_e["_car"].keyframe_insert("rotation_euler", frame=f)

# Tablecloth clouds drift
phase_tc = 0
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    tablecloth_e.location = (math.sin(t * 0.5) * 2, math.cos(t * 0.4) * 1.5, 35 + math.sin(t * 0.3) * 0.5)
    tablecloth_e.keyframe_insert("location", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 starfish sway
for sf in starfish:
    phase = sf["_phase"]; speed = sf["_speed"]
    bx, by, bz = sf["_base_x"], sf["_base_y"], sf["_base_z"]
    ax, ay, az = sf["_amp_x"], sf["_amp_y"], sf["_amp_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        sf.location = (x, y, z)
        sf.rotation_euler = (0, 0, t * 0.5 + phase)
        sf.keyframe_insert("location", frame=f)
        sf.keyframe_insert("rotation_euler", frame=f)

# 400 whale spouts pulse
for sp in spouts:
    phase = sp["_phase"]; speed = sp["_speed"]; pulse = sp["_pulse"]
    bx, by = sp["_base_x"], sp["_base_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Whale drift
        x = bx + math.sin(t * speed * 0.3 + phase) * 3
        y = by + math.cos(t * speed * 0.2 + phase) * 2
        sp.location = (x, y, sp.location.z)
        sp.rotation_euler = (0, 0, math.atan2(math.cos(t * speed * 0.2 + phase),
                                                -math.sin(t * speed * 0.2 + phase)))
        # Spout pulse
        sc = 0.5 + abs(math.sin(t * pulse + phase)) * 1.2
        sp.scale = (1, 1, sc)
        sp.keyframe_insert("location", frame=f)
        sp.keyframe_insert("rotation_euler", frame=f)
        sp.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_capetown_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_capetown_table_mountain_penguins] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Cape Town: signature flat-top Table Mountain 33m plateau with TABLECLOTH cloud drifting + 12 vertical cliff faces + Lion's Head pointed peak + Atlantic Ocean with waves + Boulders Beach with 8 giant granite boulders + 6 African penguins (signature pink eye patches + black chest band + white face stripe + pink feet) + 4 surfers on boards (wetsuits + long wet hair + balance pose + 3 board colors) + cable car system with lower/upper stations + 30 cable segments + 8-window car + South Africa rainbow flag (signature 6 colors with Y-shape) + 600 starfish multicolor swaying + 400 whale spouts pulsing")
print("🐳 FIXES: 1 cliff ground + ocean + 600 starfish (red/orange/purple/pink/blue) + 400 whale spouts signature 🐳")
