"""
proc_japanese_kyoto_torii_zen.py — 263e procédural AuroraIA (128e qualité)
Kyoto Fushimi Inari + Kinkaku-ji: 20 red torii tunnel + 4 zen monks + stone lanterns + koi pond + 6 maiko geishas + Mt Fuji + Kinkaku-ji + 600 sakura + 400 koi fish
FIXES : 1 ground + 600 sakura petals + 400 koi fish swimming (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB263)

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

# Sky pastel spring
M_SKY = mat("sky", (0.78, 0.85, 0.92, 1.0), 0.0, 0.7, emission=(0.78,0.85,0.92), emission_strength=2.0)
M_CLOUD = mat("cloud", (0.95, 0.92, 0.92, 1.0), 0.0, 0.7, emission=(0.92,0.90,0.92), emission_strength=1.4)
M_SUN = mat("sun", (1.0, 0.92, 0.65, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.65), emission_strength=14.0)

# Mt Fuji
M_FUJI_ROCK = mat("f_r", (0.42, 0.40, 0.42, 1.0), 0.0, 0.85, emission=(0.40,0.38,0.40), emission_strength=0.3)
M_FUJI_SNOW = mat("f_s", (0.95, 0.96, 0.98, 1.0), 0.0, 0.30, emission=(0.92,0.94,0.96), emission_strength=1.0)

# Ground gravel
M_GRAVEL = mat("gv", (0.78, 0.72, 0.65, 1.0), 0.0, 0.80, emission=(0.72,0.68,0.62), emission_strength=0.5)
M_GRAVEL_DARK = mat("gv_d", (0.55, 0.48, 0.40, 1.0), 0.0, 0.85)
M_STONE = mat("st", (0.42, 0.38, 0.35, 1.0), 0.0, 0.85)

# Torii red (signature vermillion)
M_TORII_RED = mat("tr", (0.92, 0.20, 0.12, 1.0), 0.0, 0.55, emission=(0.88,0.20,0.12), emission_strength=0.8)
M_TORII_DARK = mat("tr_d", (0.62, 0.10, 0.10, 1.0), 0.0, 0.65)
M_TORII_BLACK = mat("tr_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.75)

# Wood
M_WOOD = mat("w", (0.45, 0.28, 0.15, 1.0), 0.0, 0.75, emission=(0.42,0.28,0.15), emission_strength=0.4)
M_WOOD_DARK = mat("w_d", (0.25, 0.15, 0.08, 1.0), 0.0, 0.85)

# Stone lantern
M_LAMP_STONE = mat("ls", (0.55, 0.52, 0.48, 1.0), 0.0, 0.85, emission=(0.50,0.48,0.45), emission_strength=0.4)
M_LAMP_MOSS = mat("lm", (0.30, 0.45, 0.25, 1.0), 0.0, 0.75)
M_LAMP_GLOW = mat("lg", (1.0, 0.85, 0.45, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.45), emission_strength=6.0, alpha=0.85)

# Koi pond water
M_WATER = mat("w_p", (0.18, 0.45, 0.42, 1.0), 0.1, 0.20, emission=(0.18,0.42,0.40), emission_strength=1.0, alpha=0.78)
M_WATER_DEEP = mat("w_d_p", (0.10, 0.32, 0.32, 1.0), 0.1, 0.25, alpha=0.85)

# Koi colors signature
M_KOI_RED = mat("k_r", (0.95, 0.25, 0.18, 1.0), 0.0, 0.45, emission=(0.92,0.25,0.18), emission_strength=1.5)
M_KOI_ORANGE = mat("k_o", (1.0, 0.55, 0.18, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.18), emission_strength=1.5)
M_KOI_WHITE = mat("k_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.50, emission=(0.92,0.90,0.88), emission_strength=1.0)
M_KOI_BLACK = mat("k_bk", (0.18, 0.15, 0.15, 1.0), 0.0, 0.65)
M_KOI_GOLD = mat("k_g", (1.0, 0.85, 0.30, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.30), emission_strength=2.0)
KOI_COLORS = [M_KOI_RED, M_KOI_ORANGE, M_KOI_WHITE, M_KOI_GOLD]

# Sakura
M_SAKURA_PINK = mat("sk_p", (1.0, 0.65, 0.85, 1.0), 0.0, 0.45, emission=(0.95,0.65,0.82), emission_strength=2.0)
M_SAKURA_WHITE = mat("sk_w", (0.98, 0.88, 0.92, 1.0), 0.0, 0.45, emission=(0.95,0.88,0.92), emission_strength=1.5)
M_SAKURA_LIGHT = mat("sk_l", (1.0, 0.78, 0.88, 1.0), 0.0, 0.45, emission=(0.95,0.75,0.88), emission_strength=1.6)
SAKURA_COLORS = [M_SAKURA_PINK, M_SAKURA_WHITE, M_SAKURA_LIGHT]
M_SAKURA_TRUNK = mat("sk_t", (0.32, 0.20, 0.12, 1.0), 0.0, 0.85)
M_SAKURA_BRANCH = mat("sk_b", (0.42, 0.28, 0.15, 1.0), 0.0, 0.85)

# Skin
M_SKIN_JP = mat("sj", (0.95, 0.85, 0.75, 1.0), 0.0, 0.55, emission=(0.92,0.82,0.75), emission_strength=0.4)
M_SKIN_GEISHA = mat("sg", (0.98, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.95,0.92,0.90), emission_strength=0.6)

# Hair
M_HAIR_BLACK = mat("hb", (0.08, 0.05, 0.04, 1.0), 0.0, 0.55)

# Kinkaku-ji gold
M_KINKAKU_GOLD = mat("kg", (1.0, 0.85, 0.25, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.25), emission_strength=2.5)
M_KINKAKU_DARK = mat("kg_d", (0.85, 0.62, 0.18, 1.0), 0.95, 0.20)
M_KINKAKU_WHITE = mat("kg_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65)

# Monk robe (signature saffron + grey)
M_MONK_ROBE = mat("mr", (0.55, 0.32, 0.15, 1.0), 0.0, 0.75, emission=(0.50,0.30,0.15), emission_strength=0.4)
M_MONK_GREY = mat("mg", (0.42, 0.40, 0.42, 1.0), 0.0, 0.85)
M_MONK_SASH = mat("ms_b", (0.92, 0.55, 0.18, 1.0), 0.0, 0.65, emission=(0.88,0.55,0.18), emission_strength=0.6)

# Kimono colors signature
M_KIMONO_PINK = mat("kp", (0.95, 0.45, 0.78, 1.0), 0.0, 0.55, emission=(0.92,0.45,0.75), emission_strength=0.7)
M_KIMONO_RED = mat("kr", (0.85, 0.15, 0.25, 1.0), 0.0, 0.55, emission=(0.80,0.15,0.25), emission_strength=0.6)
M_KIMONO_PURPLE = mat("kpu", (0.62, 0.25, 0.78, 1.0), 0.0, 0.55, emission=(0.60,0.25,0.75), emission_strength=0.6)
M_KIMONO_TEAL = mat("kt", (0.18, 0.55, 0.55, 1.0), 0.0, 0.55, emission=(0.18,0.52,0.52), emission_strength=0.6)
M_KIMONO_GOLD = mat("kgo", (0.92, 0.78, 0.32, 1.0), 0.5, 0.30, emission=(0.88,0.75,0.32), emission_strength=1.0)
M_KIMONO_BLUE = mat("kb", (0.20, 0.42, 0.78, 1.0), 0.0, 0.55, emission=(0.18,0.40,0.75), emission_strength=0.6)
KIMONO_COLORS = [M_KIMONO_PINK, M_KIMONO_RED, M_KIMONO_PURPLE, M_KIMONO_TEAL, M_KIMONO_GOLD, M_KIMONO_BLUE]

# Obi sash
M_OBI_GOLD = mat("og", (1.0, 0.85, 0.30, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.30), emission_strength=1.5)
M_OBI_RED = mat("or", (0.78, 0.15, 0.20, 1.0), 0.0, 0.55)

# Eye + lips
M_EYE_DARK = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS = mat("lp", (0.78, 0.15, 0.20, 1.0), 0.0, 0.40, emission=(0.72,0.15,0.20), emission_strength=0.6)

# Lotus
M_LOTUS_PINK = mat("lt_p", (1.0, 0.65, 0.85, 1.0), 0.0, 0.45, emission=(0.95,0.65,0.82), emission_strength=1.5)
M_LOTUS_GREEN = mat("lt_g", (0.30, 0.65, 0.30, 1.0), 0.0, 0.65, emission=(0.28,0.62,0.30), emission_strength=0.5)

# Bamboo
M_BAMBOO = mat("bm", (0.55, 0.62, 0.20, 1.0), 0.0, 0.70, emission=(0.50,0.60,0.20), emission_strength=0.5)
M_BAMBOO_LEAF = mat("bl", (0.30, 0.65, 0.30, 1.0), 0.0, 0.65, emission=(0.30,0.62,0.30), emission_strength=0.5)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sun = smooth_sphere("sun", r=5, segs=24, rings=18, loc=(-30, 80, 60), mat_=M_SUN)
# Pink clouds
for ci in range(15):
    cax = random.uniform(-100, 100); cay = random.uniform(-100, 100)
    caz = random.uniform(30, 60)
    cloud_e = empty(f"cl{ci}", (cax, cay, caz))
    for cli in range(random.randint(3, 5)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(2.5, 4.5), segs=16, rings=10,
                      loc=(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD, scale=(1.4, 1.2, 0.7))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)

# ============ MT FUJI background ============
fuji_e = empty("fuji", loc=(0, 90, 0))
for li in range(10):
    lz = li * 4
    lr = 40 - li * 3.5
    cyl(f"f{li}", r=lr, depth=4, segs=20, loc=(0, 0, lz + 2),
        parent=fuji_e, mat_=M_FUJI_ROCK if li < 6 else M_FUJI_SNOW)
smooth_cone("f_top", r1=8, r2=0.5, depth=10, segs=18, loc=(0, 0, 40), parent=fuji_e, mat_=M_FUJI_SNOW)

# ============ ONE clean raked gravel garden ground ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_GRAVEL)
# Raked patterns (signature zen)
for ri in range(30):
    ry = -45 + ri * 3
    cyl(f"rake{ri}", r=0.20, depth=0.04, segs=10, loc=(0, ry, 0.15), mat_=M_GRAVEL_DARK).rotation_euler = (0, math.radians(90), 0)
# Stones
for si in range(40):
    sx = random.uniform(-70, 70); sy = random.uniform(-70, 70)
    smooth_sphere(f"st{si}", r=random.uniform(0.3, 0.7), segs=12, rings=10,
                  loc=(sx, sy, 0.20), mat_=M_STONE, scale=(1.4, 1.3, 0.5))

# ============ 20 TORII TUNNEL (signature Fushimi Inari) ============
def make_torii(name, loc, scale=1.0, parent=None):
    base = empty(name, loc, parent=parent)
    # 2 vertical pillars (signature slightly angled in)
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.25, depth=5, segs=14, loc=(side*1.4, 0, 2.5),
            parent=base, mat_=M_TORII_RED).rotation_euler = (0, math.radians(side*2), 0)
        # Black base
        cyl(f"{name}_pb{side}", r=0.30, depth=0.30, segs=14, loc=(side*1.4, 0, 0.15),
            parent=base, mat_=M_TORII_BLACK)
    # Top KASAGI horizontal beam (signature with upturned ends)
    beveled_cube(f"{name}_kg", (3.8, 0.30, 0.30), bevel_offset=0.06, loc=(0, 0, 5.2),
                 parent=base, mat_=M_TORII_DARK)
    # NUKI cross beam (signature lower beam below top)
    beveled_cube(f"{name}_nuki", (3.0, 0.25, 0.20), bevel_offset=0.04, loc=(0, 0, 4.4),
                 parent=base, mat_=M_TORII_RED)
    # SHIMAGI second beam under kasagi
    beveled_cube(f"{name}_sm", (3.5, 0.20, 0.18), bevel_offset=0.04, loc=(0, 0, 4.9),
                 parent=base, mat_=M_TORII_DARK)
    # Upturned ends on top beam (signature)
    for side in (-1, 1):
        beveled_cube(f"{name}_up{side}", (0.40, 0.30, 0.25), bevel_offset=0.06,
                     loc=(side*2.0, 0, 5.30), parent=base, mat_=M_TORII_DARK).rotation_euler = (0, math.radians(side*-15), 0)
    # GAKUZUKA central tablet
    beveled_cube(f"{name}_tab", (0.40, 0.30, 0.50), bevel_offset=0.06, loc=(0, 0, 4.7),
                 parent=base, mat_=M_TORII_DARK)
    # White kanji
    cyl(f"{name}_kanji", r=0.06, depth=0.02, segs=10, loc=(0, -0.15, 4.7),
        parent=base, mat_=M_KINKAKU_WHITE).rotation_euler = (math.radians(90), 0, 0)
    return base

# Tunnel of 20 toriis
toriis = []
for ti in range(20):
    ty = -25 + ti * 2.5
    t = make_torii(f"torii{ti}", (0, ty, 0), scale=1.0)
    toriis.append(t)

# ============ STONE LANTERNS along path (signature ishidoro) ============
for li in range(10):
    side = 1 if li % 2 == 0 else -1
    ly = -25 + li * 5
    lan_e = empty(f"lan{li}", (side * 4, ly, 0))
    # Base
    beveled_cube(f"lan_b{li}", (1.0, 1.0, 0.30), bevel_offset=0.06, loc=(0, 0, 0.15),
                 parent=lan_e, mat_=M_LAMP_STONE)
    # Pillar
    cyl(f"lan_p{li}", r=0.20, depth=1.5, segs=12, loc=(0, 0, 1.05),
        parent=lan_e, mat_=M_LAMP_STONE)
    # Mid section
    cyl(f"lan_m{li}", r=0.30, depth=0.20, segs=14, loc=(0, 0, 1.90),
        parent=lan_e, mat_=M_LAMP_STONE)
    # Light chamber signature (6-sided)
    for ci in range(6):
        ca = (ci / 6.0) * math.pi * 2
        beveled_cube(f"lan_c{li}_{ci}", (0.35, 0.10, 0.50), bevel_offset=0.04,
                     loc=(math.cos(ca)*0.30, math.sin(ca)*0.30, 2.30), parent=lan_e,
                     mat_=M_LAMP_STONE).rotation_euler = (0, 0, ca)
    # Glow inside
    smooth_sphere(f"lan_g{li}", r=0.20, segs=14, rings=10, loc=(0, 0, 2.30),
                  parent=lan_e, mat_=M_LAMP_GLOW)
    # Roof signature with corners
    cyl(f"lan_r{li}", r=0.60, depth=0.20, segs=14, loc=(0, 0, 2.70),
        parent=lan_e, mat_=M_LAMP_STONE)
    smooth_cone(f"lan_rp{li}", r1=0.45, r2=0.06, depth=0.30, segs=14, loc=(0, 0, 2.95),
                parent=lan_e, mat_=M_LAMP_STONE)
    smooth_sphere(f"lan_f{li}", r=0.10, loc=(0, 0, 3.20), parent=lan_e, mat_=M_LAMP_STONE)
    # Moss
    smooth_sphere(f"lan_mo{li}", r=0.20, loc=(0.6, 0, 0.30), parent=lan_e, mat_=M_LAMP_MOSS,
                  scale=(1, 1, 0.3))

# ============ KOI POND (signature) ============
pond_e = empty("pond", loc=(0, -38, 0))
# Pond shape kidney
smooth_sphere("p_main", r=8, segs=24, rings=16, loc=(0, 0, 0.10), parent=pond_e,
              mat_=M_WATER, scale=(1.3, 0.85, 0.05))
smooth_sphere("p_deep", r=7.5, segs=22, rings=14, loc=(0, 0, 0.15), parent=pond_e,
              mat_=M_WATER_DEEP, scale=(1.2, 0.8, 0.03))
# Stone border
for bi in range(24):
    ba = (bi / 24.0) * math.pi * 2
    smooth_sphere(f"p_b{bi}", r=0.40, loc=(math.cos(ba)*9*1.3, math.sin(ba)*9*0.85, 0.30),
                  parent=pond_e, mat_=M_STONE, scale=(1.2, 1.1, 0.7))
# Lotus flowers (signature)
for fi in range(15):
    fa = random.uniform(0, math.pi*2); fr = random.uniform(2, 7)
    fx_p = math.cos(fa) * fr * 1.2
    fy_p = math.sin(fa) * fr * 0.8
    # Leaf pad
    cyl(f"lo_l{fi}", r=0.45, depth=0.05, segs=14, loc=(fx_p, fy_p, 0.18),
        parent=pond_e, mat_=M_LOTUS_GREEN)
    # Flower (some)
    if random.random() > 0.5:
        for pi in range(6):
            pa = (pi / 6.0) * math.pi * 2
            smooth_sphere(f"lo_p{fi}_{pi}", r=0.10,
                          loc=(fx_p + math.cos(pa)*0.10, fy_p + math.sin(pa)*0.10, 0.30),
                          parent=pond_e, mat_=M_LOTUS_PINK, scale=(1.3, 0.7, 0.7))

# Bridge over pond signature (red arched)
bridge_e = empty("bridge", (0, -38, 0))
for ai in range(15):
    aa = math.pi * ai / 14.0
    ax = math.cos(aa) * 8
    az = math.sin(aa) * 2
    cyl(f"br_a{ai}", r=0.15, depth=0.60, segs=10, loc=(ax, 0, az + 1),
        parent=bridge_e, mat_=M_TORII_RED)
# Deck
beveled_cube("br_d", (16, 1.5, 0.20), bevel_offset=0.06, loc=(0, 0, 3),
             parent=bridge_e, mat_=M_TORII_RED)
# Railings
for side in (-1, 1):
    beveled_cube(f"br_r{side}", (16, 0.10, 0.40), bevel_offset=0.04, loc=(0, side*0.85, 3.3),
                 parent=bridge_e, mat_=M_TORII_DARK)

# ============ KINKAKU-JI GOLDEN PAVILION (signature) ============
kinkaku_e = empty("kinkaku", loc=(-30, 50, 0))
# Base reflection pool
beveled_cube("kg_pool", (16, 14, 0.20), bevel_offset=0.06, loc=(0, 0, 0.10),
             parent=kinkaku_e, mat_=M_WATER)
# 1st floor (white shinden)
beveled_cube("kg_f1", (10, 8, 3), bevel_offset=0.10, loc=(0, 0, 1.7),
             parent=kinkaku_e, mat_=M_KINKAKU_WHITE)
# 2nd floor GOLD (signature)
beveled_cube("kg_f2", (8, 6, 3), bevel_offset=0.10, loc=(0, 0, 5),
             parent=kinkaku_e, mat_=M_KINKAKU_GOLD)
# 3rd floor GOLD (signature smaller)
beveled_cube("kg_f3", (6, 4.5, 2.5), bevel_offset=0.10, loc=(0, 0, 7.75),
             parent=kinkaku_e, mat_=M_KINKAKU_GOLD)
# Curved roofs each floor signature
for fi in range(3):
    rz = 3.3 + fi * 3.3
    rw_p = (11, 9, 7)[fi]
    rd_p = (9, 7, 5.5)[fi]
    # Layered roof
    for ri in range(4):
        rw_l = rw_p - ri * 0.2
        rd_l = rd_p - ri * 0.2
        beveled_cube(f"kg_r{fi}_{ri}", (rw_l, rd_l, 0.25), bevel_offset=0.10,
                     loc=(0, 0, rz + ri*0.20), parent=kinkaku_e, mat_=M_KINKAKU_DARK)
    # Upturned corners signature
    for cx in (-1, 1):
        for cy in (-1, 1):
            corner_e = empty(f"kg_c{fi}_{cx}_{cy}", (cx*rw_p/2, cy*rd_p/2, rz + 1), parent=kinkaku_e)
            for ci in range(3):
                ca_c = ci * math.pi/8
                cx_c = cx * math.cos(ca_c) * 0.4
                cy_c = cy * math.sin(ca_c) * 0.4
                smooth_sphere(f"kg_cu{fi}_{cx}_{cy}_{ci}", r=0.15,
                              loc=(cx_c, cy_c, ci*0.20), parent=corner_e, mat_=M_KINKAKU_DARK)
# Top phoenix bird gold (signature)
phx_e = empty("kg_phx", (0, 0, 11), parent=kinkaku_e)
smooth_sphere("kg_phx_b", r=0.30, segs=14, rings=10, loc=(0, 0, 0),
              parent=phx_e, mat_=M_KINKAKU_GOLD, scale=(1.5, 0.85, 1))
# Wings
for side in (-1, 1):
    beveled_cube(f"kg_phx_w{side}", (0.10, 0.5, 0.3), bevel_offset=0.04,
                 loc=(side*0.30, 0, 0.10), parent=phx_e, mat_=M_KINKAKU_GOLD)
# Tail
beveled_cube("kg_phx_t", (0.30, 0.10, 0.6), bevel_offset=0.04, loc=(0, -0.30, 0),
             parent=phx_e, mat_=M_KINKAKU_GOLD)

# ============ 4 ZEN MONKS (signature meditation) ============
def make_monk(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sitting lotus pose
    smooth_sphere(f"{name}_lp", r=0.50, segs=18, rings=12, loc=(0, 0, 0.30),
                  parent=base, mat_=M_MONK_ROBE, scale=(1.3, 1.3, 0.5))
    # Torso
    smooth_cone(f"{name}_t", r1=0.30, r2=0.32, depth=0.55, segs=14, loc=(0, 0, 0.85),
                parent=base, mat_=M_MONK_ROBE)
    # Sash (signature kesa)
    sash_e = empty(f"{name}_s", (0, 0, 0.85), parent=base)
    sash_e.rotation_euler = (0, math.radians(20), math.radians(45))
    beveled_cube(f"{name}_sa", (0.55, 0.06, 0.40), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=sash_e, mat_=M_MONK_SASH)
    # Hands in mudra
    for side in (-1, 1):
        sh = empty(f"{name}_sh{side}", (side*0.28, 0, 0.95), parent=base)
        sh.rotation_euler = (math.radians(-90), 0, math.radians(side*-20))
        cyl(f"{name}_uarm{side}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.15),
            parent=sh, mat_=M_MONK_ROBE)
        cyl(f"{name}_fa{side}", r=0.05, depth=0.25, segs=10, loc=(0, 0, -0.42),
            parent=sh, mat_=M_SKIN_JP)
        # Hand on lap
        smooth_sphere(f"{name}_hd{side}", r=0.05, loc=(0, 0, -0.55),
                      parent=sh, mat_=M_SKIN_JP)
    # SHAVED HEAD signature
    head_m_e = empty(f"{name}_he", (0, 0, 1.30), parent=base)
    smooth_sphere(f"{name}_head", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN_JP)
    # Eyes closed
    for side in (-1, 1):
        beveled_cube(f"{name}_eye{side}", (0.04, 0.02, 0.01), bevel_offset=0.003,
                     loc=(side*0.06, -0.14, 0.02), parent=head_m_e, mat_=M_EYE_DARK)
    # Peaceful small smile
    beveled_cube(f"{name}_sm", (0.04, 0.02, 0.01), bevel_offset=0.003,
                 loc=(0, -0.15, -0.06), parent=head_m_e, mat_=M_LIPS)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base}

monks = []
monk_pos = [(-6, -20, math.radians(0)), (6, -20, math.radians(0)),
             (-4, -5, math.radians(0)), (4, -5, math.radians(0))]
for i, (mx, my, fac) in enumerate(monk_pos):
    m = make_monk(f"monk{i}", (mx, my, 0), scale=1.0, facing=fac)
    monks.append(m)

# ============ 6 MAIKO/GEISHAS (signature kimono) ============
def make_geisha(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    kim_col = random.choice(KIMONO_COLORS)
    # Long flowing kimono (signature wrapped)
    smooth_cone(f"{name}_kimono", r1=0.55, r2=0.32, depth=1.8, segs=20, loc=(0, 0, 0.95),
                parent=base, mat_=kim_col)
    # Kimono pattern (signature floral motifs)
    for fi in range(20):
        fa = random.uniform(0, math.pi*2); fe = random.uniform(0.2, 0.8)
        fx_f = math.sin(fe) * math.cos(fa) * 0.50
        fy_f = math.sin(fe) * math.sin(fa) * 0.45
        fz_f = math.cos(fe) * 0.6 + 0.95
        smooth_sphere(f"{name}_fl{fi}", r=0.05,
                      loc=(fx_f, fy_f, fz_f), parent=base, mat_=M_SAKURA_PINK)
    # WIDE OBI signature (gold + red back bow)
    cyl(f"{name}_obi", r=0.42, depth=0.40, segs=18, loc=(0, 0, 1.55),
        parent=base, mat_=M_OBI_GOLD)
    # OBI BOW back (signature)
    bow_e = empty(f"{name}_bow", (0, 0.40, 1.55), parent=base)
    beveled_cube(f"{name}_bow_b", (0.5, 0.20, 0.30), bevel_offset=0.06, loc=(0, 0, 0),
                 parent=bow_e, mat_=M_OBI_RED)
    # Bow loops
    for side in (-1, 1):
        smooth_sphere(f"{name}_bow_l{side}", r=0.18, loc=(side*0.30, 0, 0),
                      parent=bow_e, mat_=M_OBI_RED, scale=(0.7, 0.7, 1.2))
    # Top kimono (signature crossover collar)
    smooth_cone(f"{name}_top", r1=0.32, r2=0.34, depth=0.55, segs=14, loc=(0, 0, 1.85),
                parent=base, mat_=kim_col)
    # White collar visible
    cyl(f"{name}_col", r=0.34, depth=0.10, segs=14, loc=(0, 0, 2.10),
        parent=base, mat_=M_KINKAKU_WHITE)
    # Wide sleeves (signature)
    for side_idx, side in enumerate((-1, 1)):
        sleeve_e = empty(f"{name}_sl{side_idx}_e", (side*0.32, 0, 1.95), parent=base)
        sleeve_e.rotation_euler = (math.radians(-30), 0, math.radians(side*-5))
        smooth_cone(f"{name}_sl{side_idx}", r1=0.12, r2=0.20, depth=0.65, segs=12,
                    loc=(0, 0, -0.32), parent=sleeve_e, mat_=kim_col)
        # Pattern on sleeve
        for fi in range(4):
            fa_p = (fi / 4.0) * math.pi * 2
            smooth_sphere(f"{name}_sf{side_idx}_{fi}", r=0.03,
                          loc=(math.cos(fa_p)*0.14, math.sin(fa_p)*0.14, -0.32),
                          parent=sleeve_e, mat_=M_SAKURA_PINK)
        # Hand
        smooth_sphere(f"{name}_h{side_idx}", r=0.05, loc=(0, 0, -0.70),
                      parent=sleeve_e, mat_=M_SKIN_GEISHA)
    # Head WHITE FACE (signature)
    head_g_e = empty(f"{name}_he", (0, 0, 2.30), parent=base)
    smooth_sphere(f"{name}_head", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_g_e, mat_=M_SKIN_GEISHA, scale=(1, 1.05, 1.1))
    # ELABORATE BLACK HAIR (signature shimada)
    # Bun on top
    smooth_sphere(f"{name}_bun", r=0.22, segs=18, rings=14, loc=(0, 0.10, 0.18),
                  parent=head_g_e, mat_=M_HAIR_BLACK, scale=(1.3, 1.1, 0.85))
    # Hair sides
    for side in (-1, 1):
        smooth_sphere(f"{name}_hs{side}", r=0.13, loc=(side*0.14, 0.05, 0.05),
                      parent=head_g_e, mat_=M_HAIR_BLACK, scale=(0.7, 1.1, 1))
    # KANZASHI hair ornaments (signature gold dangling)
    for side in (-1, 1):
        for di in range(3):
            cyl(f"{name}_kz{side}_{di}", r=0.012, depth=0.10, segs=8,
                loc=(side*0.18, 0.05, 0.20 - di*0.05),
                parent=head_g_e, mat_=M_KINKAKU_GOLD)
            smooth_sphere(f"{name}_kzb{side}_{di}", r=0.025,
                          loc=(side*0.18, 0.05, 0.10 - di*0.06),
                          parent=head_g_e, mat_=random.choice([M_SAKURA_PINK, M_KIMONO_GOLD]))
    # Eyes (signature kohl)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.15, 0.03), parent=head_g_e, mat_=M_EYE_DARK)
        # Kohl
        beveled_cube(f"{name}_kh{side}", (0.08, 0.04, 0.02), bevel_offset=0.005,
                     loc=(side*0.08, -0.16, 0), parent=head_g_e, mat_=M_HAIR_BLACK)
    # RED LIPS small signature
    beveled_cube(f"{name}_lips", (0.04, 0.04, 0.02), bevel_offset=0.005,
                 loc=(0, -0.18, -0.06), parent=head_g_e, mat_=M_LIPS)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_g_e}

geishas = []
g_pos = [(-15, 10, math.radians(45)), (-10, 14, math.radians(-15)),
          (-5, 12, math.radians(20)), (5, 12, math.radians(-20)),
          (10, 14, math.radians(15)), (15, 10, math.radians(-45))]
for i, (gx, gy, fac) in enumerate(g_pos):
    g = make_geisha(f"geisha{i}", (gx, gy, 0), scale=1.0, facing=fac)
    geishas.append(g)

# ============ SAKURA TREES ============
def make_sakura_tree(name, loc, scale=1.0):
    base = empty(name, loc)
    # Gnarled trunk
    for ti in range(5):
        tz = ti * 0.7
        tilt = math.sin(ti * 0.5) * 0.1
        cyl(f"{name}_t{ti}", r=0.35 - ti*0.025, depth=0.70, segs=14,
            loc=(tilt, 0, tz + 0.35), parent=base, mat_=M_SAKURA_TRUNK)
    # Branches
    for bi in range(7):
        ba = (bi / 7.0) * math.pi * 2 + random.uniform(-0.2, 0.2)
        br_e = empty(f"{name}_b{bi}_e", (0, 0, 3.5), parent=base)
        br_e.rotation_euler = (math.radians(random.uniform(35, 60)), 0, ba)
        cyl(f"{name}_b{bi}", r=0.12, depth=2, segs=10, loc=(0, 0, 1),
            parent=br_e, mat_=M_SAKURA_BRANCH)
    # Flower clusters
    for fi in range(150):
        fa = random.uniform(0, math.pi*2); fe = random.uniform(0, math.pi/2)
        fr = random.uniform(2, 5) * scale
        fx = math.cos(fa) * fr; fy = math.sin(fa) * fr
        fz = 4 + math.sin(fe) * 2 + random.uniform(0, 1.5)
        smooth_sphere(f"{name}_fl{fi}", r=random.uniform(0.15, 0.25),
                      loc=(fx, fy, fz), parent=base, mat_=random.choice(SAKURA_COLORS))
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

sakura_trees = []
sp_pos = [(-25, 20, 0), (-25, 5, 0), (20, 20, 0), (20, 5, 0),
          (-15, -20, 0), (15, -20, 0)]
for i, (sx, sy, sz) in enumerate(sp_pos):
    s = make_sakura_tree(f"sakura{i}", (sx, sy, sz), scale=1.0)
    sakura_trees.append(s)

# ============ BAMBOO GROVE (signature side) ============
for bi in range(20):
    bx_p = random.uniform(-50, 50); by_p = random.uniform(30, 60)
    if -40 < bx_p < -20 and 40 < by_p < 60: continue
    b_e = empty(f"bm{bi}", (bx_p, by_p, 0))
    cyl(f"bm_p{bi}", r=0.10, depth=8, segs=8, loc=(0, 0, 4), parent=b_e, mat_=M_BAMBOO)
    # Joints
    for ji in range(8):
        cyl(f"bm_j{bi}_{ji}", r=0.11, depth=0.04, segs=8, loc=(0, 0, 0.5 + ji*1),
            parent=b_e, mat_=M_BAMBOO_LEAF)
    # Leaves at top
    for li in range(8):
        la = (li / 8.0) * math.pi * 2
        beveled_cube(f"bm_l{bi}_{li}", (0.04, 0.10, 0.40), bevel_offset=0.02,
                     loc=(math.cos(la)*0.20, math.sin(la)*0.20, 8),
                     parent=b_e, mat_=M_BAMBOO_LEAF).rotation_euler = (0, math.radians(-30), la)

# ============================================================
# ⭐ 600 SAKURA PETALS + 400 KOI FISH (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
petals = []
for i in range(600):
    px = random.uniform(-70, 70)
    py = random.uniform(-70, 70)
    pz = random.uniform(1, 18)
    p = smooth_sphere(f"p{i}", r=random.uniform(0.06, 0.10), segs=8, rings=6,
                      loc=(px, py, pz), mat_=random.choice(SAKURA_COLORS),
                      scale=(1.4, 0.7, 0.3))
    p["_phase"] = random.uniform(0, math.pi*2)
    p["_base_x"] = px; p["_base_y"] = py; p["_base_z"] = pz
    p["_amp_x"] = random.uniform(1.0, 2.5)
    p["_amp_y"] = random.uniform(1.0, 2.5)
    p["_speed"] = random.uniform(0.4, 0.9)
    p["_fall"] = random.uniform(1.0, 2.5)
    petals.append(p)

# 400 KOI signature fish swimming in pond
kois = []
for i in range(400):
    # Distribute in pond area + some flying
    if i < 250:
        # In pond
        pa = random.uniform(0, math.pi*2); pr = random.uniform(0.5, 8)
        px = math.cos(pa) * pr * 1.2
        py = math.sin(pa) * pr * 0.8 - 38
        pz = 0.20
    else:
        # Other water
        px = random.uniform(-30, 30)
        py = random.uniform(-50, 30)
        pz = random.uniform(0.2, 1)
    k_e = empty(f"koi{i}", (px, py, pz))
    koi_col = random.choice(KOI_COLORS)
    # Fish body elongated
    smooth_sphere(f"k_b{i}", r=0.10, segs=12, rings=8, loc=(0, 0, 0),
                  parent=k_e, mat_=koi_col, scale=(2, 0.85, 0.7))
    # Patches signature (mixed colors)
    if random.random() > 0.5:
        smooth_sphere(f"k_p{i}", r=0.05, loc=(0.05, 0.02, 0.04),
                      parent=k_e, mat_=random.choice([M_KOI_WHITE, M_KOI_BLACK]),
                      scale=(1.2, 0.7, 0.5))
    # Tail
    beveled_cube(f"k_t{i}", (0.06, 0.04, 0.10), bevel_offset=0.02,
                 loc=(-0.18, 0, 0), parent=k_e, mat_=koi_col)
    # Fins
    for side in (-1, 1):
        beveled_cube(f"k_f{i}_{side}", (0.06, 0.04, 0.05), bevel_offset=0.01,
                     loc=(0, side*0.06, -0.02), parent=k_e, mat_=koi_col)
    k_e["_phase"] = random.uniform(0, math.pi*2)
    k_e["_base_x"] = px; k_e["_base_y"] = py; k_e["_base_z"] = pz
    k_e["_amp_x"] = random.uniform(0.8, 2.0)
    k_e["_amp_y"] = random.uniform(0.8, 2.0)
    k_e["_speed"] = random.uniform(0.5, 1.5)
    kois.append(k_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Monks breathe meditative
for mk in monks:
    phase = mk["root"]["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        s_m = 1 + math.sin(t * 0.6 + phase) * 0.02
        mk["root"].scale = (s_m, s_m, s_m)
        mk["root"].keyframe_insert("scale", frame=f)

# Geishas walk gracefully + head turn
for g in geishas:
    phase = g["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        g["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(3),
                                     math.cos(t * 1.2 + phase) * math.radians(4),
                                     g["root"].rotation_euler.z)
        g["root"].location.z = abs(math.sin(t * 1.5 + phase)) * 0.08
        g["root"].keyframe_insert("rotation_euler", frame=f)
        g["root"].keyframe_insert("location", frame=f)
        g["he"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(20))
        g["he"].keyframe_insert("rotation_euler", frame=f)

# Sakura trees sway
for st in sakura_trees:
    phase = st["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        st.rotation_euler = (math.sin(t * 0.6 + phase) * math.radians(3),
                              math.cos(t * 0.6 + phase) * math.radians(3), 0)
        st.keyframe_insert("rotation_euler", frame=f)

# 600 sakura petals fall
for p in petals:
    phase = p["_phase"]; speed = p["_speed"]; fall = p["_fall"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    ax, ay = p["_amp_x"], p["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.3)
        if z < 0.3: z = bz
        p.location = (x, y, max(0.2, z))
        p.rotation_euler = (t * 2.5 + phase, t * 2.0 + phase, t * 3.0 + phase)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# 400 koi swim
for k in kois:
    phase = k["_phase"]; speed = k["_speed"]
    bx, by, bz = k["_base_x"], k["_base_y"], k["_base_z"]
    ax, ay = k["_amp_x"], k["_amp_y"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        k.location = (x, y, bz + math.sin(t * 2.0 + phase) * 0.05)
        # Orient swimming direction
        k.rotation_euler = (0, 0, math.atan2(math.cos(t * speed * 0.9 + phase),
                                                math.sin(t * speed + phase)))
        k.keyframe_insert("location", frame=f)
        k.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_kyoto_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_japanese_kyoto_torii_zen] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_japanese_kyoto_torii_zen] Mt Fuji + raked gravel zen ground + 20 red torii tunnel signature + 10 stone lanterns ishidoro + koi pond with red arched bridge + lotus + Kinkaku-ji 3-tier gold pavilion + phoenix + 4 zen monks lotus pose + 6 maiko geishas signature + 6 sakura + 20 bamboo + 600 sakura + 400 koi")
print("⭐ FIXES: 1 ground + 600 sakura + 400 koi (signature Kyoto mandatory) ⭐")
