"""
proc_korean_palace_gyeongbokgung_hanbok.py — 254e procédural AuroraIA (119e qualité)
Korean Gyeongbokgung Palace: dancheong rooftop + 8 sakura trees + 4 hanbok women + 6 royal guards + king+queen throne + 6 musicians + haetae lions + 600 sakura petals + 400 red lanterns
FIXES : 1 ground + 600 sakura + 400 lanterns (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB254)

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

# Spring sky
M_SKY = mat("sky", (0.55, 0.78, 0.92, 1.0), 0.0, 0.7, emission=(0.55,0.78,0.92), emission_strength=2.0)
M_SUN_K = mat("sun", (1.0, 0.92, 0.65, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.65), emission_strength=15.0)
M_CLOUD_PINK = mat("cloud_p", (0.98, 0.92, 0.88, 1.0), 0.0, 0.7, emission=(0.95,0.90,0.88), emission_strength=1.5)

# Palace stone ground
M_STONE_PALACE = mat("stone_p", (0.78, 0.72, 0.62, 1.0), 0.0, 0.85, emission=(0.72,0.68,0.60), emission_strength=0.4)
M_STONE_DARK = mat("stone_d", (0.45, 0.42, 0.38, 1.0), 0.0, 0.85)
M_STONE_TILE = mat("stone_t", (0.85, 0.80, 0.70, 1.0), 0.0, 0.80, emission=(0.80,0.75,0.68), emission_strength=0.5)

# Dancheong colors (signature Korean traditional)
M_DANCHEONG_RED = mat("dc_r", (0.78, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.72,0.15,0.15), emission_strength=0.6)
M_DANCHEONG_GREEN = mat("dc_g", (0.18, 0.55, 0.30, 1.0), 0.0, 0.55, emission=(0.18,0.52,0.30), emission_strength=0.6)
M_DANCHEONG_BLUE = mat("dc_b", (0.20, 0.45, 0.78, 1.0), 0.0, 0.55, emission=(0.18,0.42,0.75), emission_strength=0.6)
M_DANCHEONG_YELLOW = mat("dc_y", (0.95, 0.78, 0.20, 1.0), 0.0, 0.55, emission=(0.90,0.75,0.20), emission_strength=0.7)
M_DANCHEONG_WHITE = mat("dc_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.90,0.88,0.82), emission_strength=0.6)
DC_COLORS = [M_DANCHEONG_RED, M_DANCHEONG_GREEN, M_DANCHEONG_BLUE, M_DANCHEONG_YELLOW, M_DANCHEONG_WHITE]

# Palace wood
M_WOOD_PALACE = mat("wood_p", (0.42, 0.22, 0.10, 1.0), 0.0, 0.75, emission=(0.40,0.22,0.10), emission_strength=0.4)
M_WOOD_DARK_K = mat("wood_d", (0.25, 0.12, 0.06, 1.0), 0.0, 0.85)
M_WOOD_RED = mat("wood_r", (0.62, 0.20, 0.15, 1.0), 0.0, 0.65, emission=(0.58,0.20,0.15), emission_strength=0.5)

# Roof tiles (signature blue/black curved)
M_ROOF_DARK = mat("roof_d", (0.18, 0.18, 0.22, 1.0), 0.5, 0.40, emission=(0.18,0.18,0.22), emission_strength=0.3)
M_ROOF_BLUE = mat("roof_b", (0.25, 0.35, 0.50, 1.0), 0.4, 0.40, emission=(0.25,0.35,0.50), emission_strength=0.4)

# Sakura cherry blossom (signature)
M_SAKURA_PINK = mat("sak_p", (1.0, 0.65, 0.85, 1.0), 0.0, 0.45, emission=(0.95,0.65,0.82), emission_strength=1.8)
M_SAKURA_WHITE = mat("sak_w", (0.98, 0.88, 0.92, 1.0), 0.0, 0.45, emission=(0.95,0.88,0.92), emission_strength=1.5)
M_SAKURA_LIGHT = mat("sak_l", (1.0, 0.78, 0.88, 1.0), 0.0, 0.45, emission=(0.95,0.75,0.88), emission_strength=1.6)
SAKURA_COLORS = [M_SAKURA_PINK, M_SAKURA_WHITE, M_SAKURA_LIGHT]
M_SAKURA_TRUNK = mat("sak_t", (0.32, 0.20, 0.12, 1.0), 0.0, 0.85)
M_SAKURA_BRANCH = mat("sak_br", (0.42, 0.28, 0.15, 1.0), 0.0, 0.85)

# Skin
M_SKIN_ASIA = mat("skin", (0.92, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.62), emission_strength=0.4)
M_HAIR_BLACK_K = mat("h_bk", (0.08, 0.06, 0.05, 1.0), 0.0, 0.55)

# Hanbok colors signature (vibrant traditional)
M_HANBOK_RED = mat("hb_r", (0.92, 0.20, 0.30, 1.0), 0.0, 0.55, emission=(0.88,0.20,0.30), emission_strength=0.8)
M_HANBOK_GREEN = mat("hb_g", (0.30, 0.65, 0.40, 1.0), 0.0, 0.55, emission=(0.28,0.62,0.38), emission_strength=0.6)
M_HANBOK_BLUE = mat("hb_b", (0.30, 0.55, 0.85, 1.0), 0.0, 0.55, emission=(0.28,0.52,0.80), emission_strength=0.7)
M_HANBOK_PINK = mat("hb_p", (0.95, 0.55, 0.85, 1.0), 0.0, 0.55, emission=(0.92,0.55,0.82), emission_strength=0.8)
M_HANBOK_PURPLE = mat("hb_pu", (0.62, 0.30, 0.85, 1.0), 0.0, 0.55, emission=(0.60,0.30,0.82), emission_strength=0.7)
M_HANBOK_GOLD = mat("hb_gd", (1.0, 0.85, 0.30, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.30), emission_strength=1.5)
M_HANBOK_WHITE = mat("hb_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.65, emission=(0.90,0.88,0.82), emission_strength=0.5)
M_HANBOK_YELLOW = mat("hb_y", (1.0, 0.92, 0.50, 1.0), 0.0, 0.55, emission=(0.95,0.88,0.50), emission_strength=0.7)
HANBOK_BLOUSE = [M_HANBOK_RED, M_HANBOK_PINK, M_HANBOK_BLUE, M_HANBOK_YELLOW]
HANBOK_SKIRT = [M_HANBOK_GREEN, M_HANBOK_PURPLE, M_HANBOK_RED, M_HANBOK_BLUE]

# Guard uniform
M_GUARD_BLUE = mat("guard_b", (0.18, 0.32, 0.55, 1.0), 0.0, 0.65, emission=(0.18,0.30,0.52), emission_strength=0.5)
M_GUARD_RED = mat("guard_r", (0.62, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.58,0.18,0.18), emission_strength=0.5)

# King royal robe (signature gold dragon)
M_KING_ROBE = mat("kr", (0.95, 0.78, 0.20, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.20), emission_strength=1.0)
M_KING_DEEP = mat("kd", (0.78, 0.62, 0.18, 1.0), 0.85, 0.25, emission=(0.72,0.58,0.18), emission_strength=0.8)
M_QUEEN_ROBE = mat("qr", (0.85, 0.18, 0.30, 1.0), 0.3, 0.40, emission=(0.80,0.18,0.30), emission_strength=0.6)

# Haetae lion (signature mythological)
M_HAETAE = mat("haet", (0.55, 0.50, 0.45, 1.0), 0.0, 0.85, emission=(0.52,0.48,0.42), emission_strength=0.4)
M_HAETAE_MOSS = mat("haet_m", (0.40, 0.55, 0.30, 1.0), 0.0, 0.75)

# Music instruments
M_INSTR_WOOD = mat("instr_w", (0.55, 0.32, 0.15, 1.0), 0.0, 0.55, emission=(0.50,0.30,0.15), emission_strength=0.4)
M_INSTR_DARK = mat("instr_d", (0.28, 0.15, 0.08, 1.0), 0.0, 0.85)

# Eye / lips
M_EYE_DARK_K = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS_K = mat("lips_k", (0.78, 0.30, 0.30, 1.0), 0.0, 0.40, emission=(0.72,0.30,0.30), emission_strength=0.4)

# Lantern red signature
M_LANTERN_R = mat("lan_r", (0.92, 0.20, 0.18, 1.0), 0.0, 0.30, emission=(0.92,0.20,0.18), emission_strength=8.0, alpha=0.85)
M_LANTERN_FRAME = mat("lan_f", (0.32, 0.20, 0.10, 1.0), 0.0, 0.65)

# Throne
M_THRONE_GOLD = mat("th_g", (1.0, 0.85, 0.30, 1.0), 0.95, 0.10, emission=(0.95,0.80,0.30), emission_strength=2.5)
M_THRONE_RED = mat("th_r", (0.72, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.68,0.15,0.15), emission_strength=0.6)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Sun
sun_k = smooth_sphere("sun", r=4, segs=24, rings=18, loc=(40, 70, 75), mat_=M_SUN_K)
# Pink-tinted clouds (signature spring)
for ci in range(20):
    cax = random.uniform(-100, 100); cay = random.uniform(-100, 100)
    caz = random.uniform(35, 70)
    cloud_e = empty(f"cloud{ci}", (cax, cay, caz))
    for cli in range(random.randint(3, 5)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(2.5, 4.5), segs=16, rings=10,
                      loc=(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD_PINK, scale=(1.4, 1.2, 0.7))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)

# ============ ONE clean stone-tiled palace courtyard ground ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_STONE_PALACE)
# Tile pattern
for ti in range(30):
    for tj in range(30):
        tx_g = -45 + ti * 3; ty_g = -45 + tj * 3
        tcol = M_STONE_TILE if (ti + tj) % 2 == 0 else M_STONE_PALACE
        beveled_cube(f"tile{ti}_{tj}", (2.8, 2.8, 0.05), bevel_offset=0.02,
                     loc=(tx_g, ty_g, 0.12), mat_=tcol)
# Edge stone tiles darker
for bi in range(40):
    cyl(f"edge{bi}", r=0.20, depth=0.10, segs=12,
        loc=(-50 + bi*2.5, -50, 0.12), mat_=M_STONE_DARK)
    cyl(f"edge_b{bi}", r=0.20, depth=0.10, segs=12,
        loc=(-50 + bi*2.5, 50, 0.12), mat_=M_STONE_DARK)

# ============ KOREAN PALACE GYEONGBOKGUNG (signature dancheong) ============
palace_e = empty("palace", loc=(0, 25, 0))

# Stone platform (signature elevated base)
beveled_cube("p_plat", (30, 16, 1.5), bevel_offset=0.10, loc=(0, 0, 0.75),
             parent=palace_e, mat_=M_STONE_PALACE)
# Stairs front
for si in range(6):
    beveled_cube(f"p_st{si}", (8, 0.50, 0.25), bevel_offset=0.03,
                 loc=(0, -8 - si*0.50, 0.25 + si*0.25), parent=palace_e, mat_=M_STONE_DARK)

# Main palace walls (red)
beveled_cube("p_w_b", (28, 0.6, 6), bevel_offset=0.10, loc=(0, 7, 4.5), parent=palace_e, mat_=M_WOOD_RED)
beveled_cube("p_w_l", (0.6, 14, 6), bevel_offset=0.10, loc=(-14, 0, 4.5), parent=palace_e, mat_=M_WOOD_RED)
beveled_cube("p_w_r", (0.6, 14, 6), bevel_offset=0.10, loc=(14, 0, 4.5), parent=palace_e, mat_=M_WOOD_RED)

# 12 RED COLUMNS (signature)
column_positions = [(-12, -7, 0), (-8, -7, 0), (-4, -7, 0), (0, -7, 0),
                     (4, -7, 0), (8, -7, 0), (12, -7, 0),
                     (-12, 7, 0), (-8, 7, 0), (-4, 7, 0),
                     (8, 7, 0), (12, 7, 0)]
for ci, (cx, cy, cz) in enumerate(column_positions):
    col_e = empty(f"col{ci}", (cx, cy, cz + 1.5), parent=palace_e)
    # Base stone
    cyl(f"col_b{ci}", r=0.55, depth=0.30, segs=18, loc=(0, 0, 0), parent=col_e, mat_=M_STONE_DARK)
    # Red shaft (signature)
    cyl(f"col_s{ci}", r=0.40, depth=5.5, segs=18, loc=(0, 0, 2.9), parent=col_e, mat_=M_WOOD_RED)
    # Capital with dancheong painted top
    cyl(f"col_c{ci}", r=0.50, depth=0.20, segs=18, loc=(0, 0, 5.7), parent=col_e, mat_=M_DANCHEONG_BLUE)

# Entablature with DANCHEONG (signature multicolor)
beveled_cube("p_ent", (29, 16.5, 0.40), bevel_offset=0.06, loc=(0, 0, 8),
             parent=palace_e, mat_=M_DANCHEONG_GREEN)
# Painted dancheong panels
for di in range(15):
    dx = -13.5 + di * 2
    col_d = DC_COLORS[di % len(DC_COLORS)]
    beveled_cube(f"p_dc{di}", (1.8, 16.7, 0.40), bevel_offset=0.04,
                 loc=(dx, 0, 8), parent=palace_e, mat_=col_d)
    # Detail patterns (signature taegeuk/floral)
    for pi in range(3):
        smooth_sphere(f"p_dcd{di}_{pi}", r=0.08, loc=(dx, -8.3 + pi*8, 8.05),
                      parent=palace_e, mat_=DC_COLORS[(di+pi) % len(DC_COLORS)])

# CURVED ROOF signature pagoda-style
# Lower roof (signature curved up at ends)
roof_e = empty("p_roof", (0, 0, 8.4), parent=palace_e)
# Main roof tile body
for ri in range(8):
    rw = 30 - ri * 0.4
    rd = 17 - ri * 0.2
    rh = 0.30
    beveled_cube(f"p_r{ri}", (rw, rd, rh), bevel_offset=0.06,
                 loc=(0, 0, ri * 0.30), parent=roof_e, mat_=M_ROOF_DARK)
# Curved corners (signature upturned eaves)
for corner_x in (-1, 1):
    for corner_y in (-1, 1):
        corner_e = empty(f"p_corn_{corner_x}_{corner_y}", (corner_x*14.5, corner_y*8.2, 0.3), parent=roof_e)
        # Curved upturn
        for ci in range(5):
            ca = ci * math.pi/8
            cx_c = corner_x * math.cos(ca) * 1.5
            cy_c = corner_y * math.sin(ca) * 1.5
            cz_c = ci * 0.40
            smooth_sphere(f"p_uc{corner_x}_{corner_y}_{ci}", r=0.40,
                          loc=(cx_c, cy_c, cz_c), parent=corner_e, mat_=M_ROOF_DARK)
        # Decorative dragon-like sculpture at corner tip (signature japsang)
        smooth_sphere(f"p_jap{corner_x}_{corner_y}", r=0.30,
                      loc=(corner_x*1.8, corner_y*0.5, 2.5), parent=corner_e, mat_=M_DANCHEONG_RED, scale=(1.5, 0.7, 1.5))
# Decorative roof ridges
for ri2 in range(7):
    cyl(f"p_rdg{ri2}", r=0.10, depth=30, segs=12, loc=(0, -7 + ri2*2.3, 2.7),
        parent=roof_e, mat_=M_ROOF_BLUE).rotation_euler = (0, math.radians(90), 0)
# Top ridge with dragon-like beasts (signature)
beveled_cube("p_top_ridge", (30, 0.40, 0.60), bevel_offset=0.10, loc=(0, 0, 3.0),
             parent=roof_e, mat_=M_DANCHEONG_RED)
# 6 japsang figures on top ridge (signature mythical beasts)
for ji in range(6):
    jx = -12 + ji * 5
    smooth_sphere(f"p_jp{ji}", r=0.30, loc=(jx, 0, 3.4),
                  parent=roof_e, mat_=M_DANCHEONG_BLUE, scale=(1, 1, 1.5))
# Lit lanterns under eaves (signature)
for li in range(8):
    lx = -12 + li * 3.4
    # Lantern hanging
    smooth_sphere(f"p_lan{li}", r=0.30, segs=16, rings=12, loc=(lx, -8.3, 7.5),
                  parent=palace_e, mat_=M_LANTERN_R, scale=(1, 1, 1.4))
    # Cord
    cyl(f"p_lc{li}", r=0.015, depth=0.40, segs=6, loc=(lx, -8.3, 7.8),
        parent=palace_e, mat_=M_LANTERN_FRAME)

# Door openings
beveled_cube("p_door_l", (4, 0.7, 5), bevel_offset=0.10, loc=(-5, -7, 4),
             parent=palace_e, mat_=M_WOOD_RED)
beveled_cube("p_door_r", (4, 0.7, 5), bevel_offset=0.10, loc=(5, -7, 4),
             parent=palace_e, mat_=M_WOOD_RED)

# ============ THRONE inside palace (signature) ============
throne_e = empty("throne", (0, 5, 1.5), parent=palace_e)
# Stepped base
for li in range(3):
    lw = 6 - li * 0.8
    beveled_cube(f"th_b{li}", (lw, 4 - li*0.6, 0.4), bevel_offset=0.06,
                 loc=(0, 0, li*0.4 + 0.2), parent=throne_e, mat_=M_THRONE_RED)
# Throne chair gold (signature)
beveled_cube("th_seat", (3, 2, 0.6), bevel_offset=0.06, loc=(0, 0, 1.5),
             parent=throne_e, mat_=M_THRONE_GOLD)
# High back
beveled_cube("th_back", (3, 0.30, 3), bevel_offset=0.06, loc=(0, 1, 3),
             parent=throne_e, mat_=M_THRONE_GOLD)
# Decorative arches at top (signature)
for ai in range(5):
    ax_t = -1.2 + ai * 0.6
    smooth_sphere(f"th_a{ai}", r=0.25, loc=(ax_t, 1, 4.5),
                  parent=throne_e, mat_=M_THRONE_GOLD)
# Armrests
for side in (-1, 1):
    beveled_cube(f"th_ar{side}", (0.30, 2, 0.50), bevel_offset=0.06, loc=(side*1.5, 0, 2.0),
                 parent=throne_e, mat_=M_THRONE_GOLD)
    # Dragon head armrest tips
    smooth_sphere(f"th_dh{side}", r=0.18, loc=(side*1.5, -1.1, 2.30),
                  parent=throne_e, mat_=M_THRONE_GOLD, scale=(1, 1.3, 1))

# ============ KING and QUEEN on throne (signature) ============
king_e = empty("king", (-0.7, 0, 3.4), parent=throne_e)
# Royal robe gold
smooth_cone("k_robe", r1=0.40, r2=0.50, depth=1.0, segs=14, loc=(0, 0, 0.5),
            parent=king_e, mat_=M_KING_ROBE)
# Dragon pattern stripes
for ri in range(4):
    cyl(f"k_stripe{ri}", r=0.50, depth=0.05, segs=18, loc=(0, 0, 0.20 + ri*0.20),
        parent=king_e, mat_=M_KING_DEEP)
# Belt
cyl("k_belt", r=0.51, depth=0.08, segs=18, loc=(0, 0, 0.80),
    parent=king_e, mat_=M_DANCHEONG_RED)
# Head
k_head_e = empty("k_he", (0, 0, 1.30), parent=king_e)
smooth_sphere("k_head", r=0.20, segs=18, rings=14, loc=(0, 0, 0),
              parent=k_head_e, mat_=M_SKIN_ASIA)
# Beard
for bi in range(8):
    ba = (bi / 8.0) * math.pi - math.pi/2
    smooth_sphere(f"k_bd{bi}", r=0.04,
                  loc=(math.sin(ba)*0.13, -0.16, -0.10 - (bi%2)*0.08),
                  parent=k_head_e, mat_=M_HAIR_BLACK_K)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"k_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                  parent=k_head_e, mat_=M_EYE_DARK_K)
# GAT HAT (signature traditional black wide brim)
k_hat_e = empty("k_hat", (0, 0, 0.25), parent=k_head_e)
cyl("k_hat_brim", r=0.40, depth=0.04, segs=20, loc=(0, 0, 0),
    parent=k_hat_e, mat_=M_HAIR_BLACK_K)
cyl("k_hat_crown", r=0.18, depth=0.30, segs=14, loc=(0, 0, 0.20),
    parent=k_hat_e, mat_=M_HAIR_BLACK_K)
# Gold crown decoration
cyl("k_hat_gold", r=0.19, depth=0.04, segs=14, loc=(0, 0, 0.10),
    parent=k_hat_e, mat_=M_THRONE_GOLD)

# Queen
queen_e = empty("queen", (0.7, 0, 3.4), parent=throne_e)
# Robe pink/red
smooth_cone("q_robe", r1=0.40, r2=0.50, depth=1.0, segs=14, loc=(0, 0, 0.5),
            parent=queen_e, mat_=M_QUEEN_ROBE)
# Belt
cyl("q_belt", r=0.51, depth=0.08, segs=18, loc=(0, 0, 0.80),
    parent=queen_e, mat_=M_HANBOK_GOLD)
# Head
q_head_e = empty("q_he", (0, 0, 1.30), parent=queen_e)
smooth_sphere("q_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
              parent=q_head_e, mat_=M_SKIN_ASIA)
# Long black hair (signature elaborate updo)
for hi in range(10):
    ha = (hi / 10.0) * math.pi * 2
    smooth_sphere(f"q_hr{hi}", r=0.06,
                  loc=(math.cos(ha)*0.18, math.sin(ha)*0.10 + 0.10, 0.10),
                  parent=q_head_e, mat_=M_HAIR_BLACK_K)
# Hair ornament gold
smooth_sphere("q_orn", r=0.10, loc=(0, 0.18, 0.20),
              parent=q_head_e, mat_=M_THRONE_GOLD)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"q_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                  parent=q_head_e, mat_=M_EYE_DARK_K)
# Lips
beveled_cube("q_lips", (0.08, 0.04, 0.02), bevel_offset=0.005, loc=(0, -0.18, -0.07),
             parent=q_head_e, mat_=M_LIPS_K)

# ============ 6 ROYAL GUARDS (signature uniforms) ============
def make_guard(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Uniform body
    smooth_cone(f"{name}_uni", r1=0.32, r2=0.35, depth=1.0, segs=14, loc=(0, 0, 1.05),
                parent=base, mat_=M_GUARD_BLUE)
    # Red sash
    beveled_cube(f"{name}_sash", (0.10, 0.70, 0.40), bevel_offset=0.04,
                 loc=(0, -0.10, 1.30), parent=base, mat_=M_GUARD_RED)
    # Belt
    cyl(f"{name}_belt", r=0.36, depth=0.08, segs=14, loc=(0, 0, 1.05),
        parent=base, mat_=M_WOOD_DARK_K)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.10, depth=1.0, segs=10,
            loc=(side*0.13, 0, 0.5), parent=base, mat_=M_GUARD_BLUE)
        # Boots
        beveled_cube(f"{name}_bt{side}", (0.10, 0.20, 0.10), bevel_offset=0.02,
                     loc=(side*0.13, 0, 0), parent=base, mat_=M_HAIR_BLACK_K)
    # Arms (one holding spear)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.32, 0, 1.65), parent=base)
        sh.rotation_euler = (math.radians(-15), 0, math.radians(side*-5))
        cyl(f"{name}_uarm{side_idx}", r=0.06, depth=0.40, segs=10,
            loc=(0, 0, -0.20), parent=sh, mat_=M_GUARD_BLUE)
        cyl(f"{name}_fa{side_idx}", r=0.05, depth=0.35, segs=10,
            loc=(0, 0, -0.55), parent=sh, mat_=M_SKIN_ASIA)
    # SPEAR (signature)
    spear_e = empty(f"{name}_sp", (0.40, 0, 0), parent=base)
    cyl(f"{name}_sp_s", r=0.05, depth=3.5, segs=10, loc=(0, 0, 1.7),
        parent=spear_e, mat_=M_INSTR_DARK)
    smooth_cone(f"{name}_sp_h", r1=0.08, r2=0.005, depth=0.35, segs=10,
                loc=(0, 0, 3.65), parent=spear_e, mat_=M_HANBOK_GOLD)
    # Head
    head_g_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_g_e, mat_=M_SKIN_ASIA)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_g_e, mat_=M_EYE_DARK_K)
    # Hair / topknot
    for hi in range(6):
        ha = (hi / 6.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.04,
                      loc=(math.cos(ha)*0.13, math.sin(ha)*0.08, 0.10),
                      parent=head_g_e, mat_=M_HAIR_BLACK_K)
    # CONICAL HELMET signature (red iron)
    helm_g_e = empty(f"{name}_helm", (0, 0, 0.20), parent=head_g_e)
    smooth_cone(f"{name}_h_b", r1=0.22, r2=0.05, depth=0.40, segs=14, loc=(0, 0, 0.20),
                parent=helm_g_e, mat_=M_GUARD_RED)
    # Brim
    cyl(f"{name}_h_brim", r=0.25, depth=0.04, segs=16, loc=(0, 0, 0),
        parent=helm_g_e, mat_=M_HAIR_BLACK_K)
    # Top finial
    smooth_sphere(f"{name}_h_fin", r=0.06, loc=(0, 0, 0.45),
                  parent=helm_g_e, mat_=M_HANBOK_GOLD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_g_e}

guards = []
guard_pos = [(-12, 0, math.radians(90)), (12, 0, math.radians(-90)),
              (-12, -10, math.radians(90)), (12, -10, math.radians(-90)),
              (-15, -20, math.radians(0)), (15, -20, math.radians(0))]
for i, (gx, gy, fac) in enumerate(guard_pos):
    g = make_guard(f"guard{i}", (gx, gy, 0), scale=1.0, facing=fac)
    guards.append(g)

# ============ 4 HANBOK WOMEN (signature flowing traditional) ============
def make_hanbok_woman(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    blouse_col = random.choice(HANBOK_BLOUSE)
    skirt_col = random.choice(HANBOK_SKIRT)
    # Long FLOWING SKIRT (signature voluminous)
    smooth_cone(f"{name}_skirt", r1=0.65, r2=0.40, depth=1.6, segs=20, loc=(0, 0, 0.80),
                parent=base, mat_=skirt_col)
    # Skirt pleats
    for pi in range(12):
        pa = (pi / 12.0) * math.pi * 2
        cyl(f"{name}_pl{pi}", r=0.03, depth=1.6, segs=6,
            loc=(math.cos(pa)*0.55, math.sin(pa)*0.55, 0.80),
            parent=base, mat_=M_HANBOK_GOLD if pi % 3 == 0 else skirt_col)
    # Belt (signature gold sash)
    cyl(f"{name}_belt", r=0.45, depth=0.08, segs=16, loc=(0, 0, 1.55),
        parent=base, mat_=M_HANBOK_GOLD)
    # Belt bow at front (signature)
    smooth_sphere(f"{name}_bow", r=0.10, loc=(0, -0.45, 1.55), parent=base, mat_=skirt_col, scale=(1.8, 0.6, 1.2))
    # JEOGORI BLOUSE (signature short flowing top)
    smooth_cone(f"{name}_blouse", r1=0.32, r2=0.35, depth=0.45, segs=14, loc=(0, 0, 1.80),
                parent=base, mat_=blouse_col)
    # Wide flowing sleeves (signature)
    for side in (-1, 1):
        sleeve_e = empty(f"{name}_sl{side}_e", (side*0.32, 0, 1.95), parent=base)
        sleeve_e.rotation_euler = (math.radians(-60), 0, math.radians(side*-30))
        smooth_cone(f"{name}_sl{side}", r1=0.15, r2=0.18, depth=0.50, segs=12,
                    loc=(0, 0, -0.25), parent=sleeve_e, mat_=blouse_col)
        # Wide cuff
        cyl(f"{name}_cuff{side}", r=0.20, depth=0.10, segs=14, loc=(0, 0, -0.55),
            parent=sleeve_e, mat_=M_HANBOK_GOLD)
        # Forearm
        cyl(f"{name}_fa{side}", r=0.05, depth=0.30, segs=10, loc=(0, 0, -0.75),
            parent=sleeve_e, mat_=M_SKIN_ASIA)
    # Collar trim white
    cyl(f"{name}_col", r=0.33, depth=0.05, segs=14, loc=(0, 0, 2.10),
        parent=base, mat_=M_HANBOK_WHITE)
    # Norigae ornament (signature pendant)
    nori_e = empty(f"{name}_n_e", (0, -0.30, 1.40), parent=base)
    smooth_sphere(f"{name}_n_b", r=0.05, loc=(0, 0, 0), parent=nori_e, mat_=M_HANBOK_GOLD)
    # Tassel below
    for ti in range(3):
        cyl(f"{name}_n_t{ti}", r=0.015, depth=0.20, segs=6, loc=((ti-1)*0.04, 0, -0.15),
            parent=nori_e, mat_=random.choice(HANBOK_BLOUSE))
    # Head
    head_hb_e = empty(f"{name}_he", (0, 0, 2.30), parent=base)
    smooth_sphere(f"{name}_head", r=0.16, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_hb_e, mat_=M_SKIN_ASIA)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022, loc=(side*0.05, -0.13, 0.03),
                      parent=head_hb_e, mat_=M_EYE_DARK_K)
    # Lips red
    beveled_cube(f"{name}_lips", (0.06, 0.04, 0.02), bevel_offset=0.005, loc=(0, -0.16, -0.06),
                 parent=head_hb_e, mat_=M_LIPS_K)
    # Black hair pulled back (signature)
    for hi in range(10):
        ha = (hi / 10.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.06,
                      loc=(math.cos(ha)*0.14, math.sin(ha)*0.10 + 0.10, 0.05 - (hi%3)*0.05),
                      parent=head_hb_e, mat_=M_HAIR_BLACK_K)
    # Hair ornament (binyeo pin gold)
    smooth_sphere(f"{name}_pin", r=0.06, loc=(0, 0.12, 0.18),
                  parent=head_hb_e, mat_=M_HANBOK_GOLD, scale=(1, 0.5, 0.5))
    cyl(f"{name}_pin_p", r=0.012, depth=0.25, segs=8, loc=(0.10, 0.10, 0.18),
        parent=head_hb_e, mat_=M_HANBOK_GOLD).rotation_euler = (0, math.radians(90), 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_hb_e}

hanbok_women = []
hb_pos = [(-10, -3, math.radians(20)), (-5, -5, math.radians(-15)),
          (5, -5, math.radians(15)), (10, -3, math.radians(-20))]
for i, (hx, hy, fac) in enumerate(hb_pos):
    h = make_hanbok_woman(f"hanbok{i}", (hx, hy, 0), scale=1.0, facing=fac)
    hanbok_women.append(h)

# ============ 6 MUSICIANS (signature traditional Korean) ============
def make_musician_k(name, loc, instrument, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    robe_col = random.choice([M_HANBOK_GREEN, M_HANBOK_BLUE, M_HANBOK_PURPLE])
    # Long sitting robe
    smooth_cone(f"{name}_robe", r1=0.50, r2=0.40, depth=1.2, segs=14, loc=(0, 0, 0.6),
                parent=base, mat_=robe_col)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 1.40), parent=base)
    smooth_sphere(f"{name}_head", r=0.16, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN_ASIA)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022, loc=(side*0.05, -0.13, 0.03),
                      parent=head_m_e, mat_=M_EYE_DARK_K)
    # Hair topknot
    smooth_sphere(f"{name}_topknot", r=0.07, loc=(0, 0.05, 0.20),
                  parent=head_m_e, mat_=M_HAIR_BLACK_K)
    # Black gat hat for males
    if random.random() > 0.5:
        cyl(f"{name}_hat_b", r=0.30, depth=0.03, segs=18, loc=(0, 0, 0.18),
            parent=head_m_e, mat_=M_HAIR_BLACK_K)
    # INSTRUMENT
    inst_e = empty(f"{name}_inst", (0, -0.30, 0.85), parent=base)
    if instrument == "gayageum":
        # Long zither (signature 12 strings)
        beveled_cube(f"{name}_ga_b", (1.5, 0.20, 0.15), bevel_offset=0.04,
                     loc=(0, 0, 0), parent=inst_e, mat_=M_INSTR_WOOD)
        # Strings
        for st in range(12):
            cyl(f"{name}_ga_st{st}", r=0.005, depth=1.5, segs=6,
                loc=(0, -0.10 + st*0.018, 0.05), parent=inst_e,
                mat_=M_DANCHEONG_WHITE).rotation_euler = (0, math.radians(90), 0)
        # Bridges
        for bri in range(3):
            beveled_cube(f"{name}_ga_br{bri}", (0.04, 0.25, 0.10), bevel_offset=0.01,
                         loc=(-0.5 + bri*0.5, 0, 0.10), parent=inst_e, mat_=M_INSTR_DARK)
    elif instrument == "daegeum":
        # Bamboo flute (signature long horizontal)
        cyl(f"{name}_dg_b", r=0.04, depth=1.0, segs=12, loc=(0, 0, 0.10),
            parent=inst_e, mat_=M_INSTR_WOOD).rotation_euler = (0, math.radians(90), 0)
        # Finger holes
        for fi in range(6):
            cyl(f"{name}_dg_h{fi}", r=0.012, depth=0.005, segs=8,
                loc=(-0.30 + fi*0.10, 0.04, 0.10), parent=inst_e, mat_=M_INSTR_DARK)
    elif instrument == "janggu":
        # Hourglass drum (signature)
        smooth_cone(f"{name}_jg_l", r1=0.25, r2=0.15, depth=0.30, segs=14,
                    loc=(0, 0, 0.15), parent=inst_e, mat_=M_DANCHEONG_RED)
        smooth_cone(f"{name}_jg_r", r1=0.15, r2=0.25, depth=0.30, segs=14,
                    loc=(0, 0, -0.15), parent=inst_e, mat_=M_DANCHEONG_RED)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_m_e, "inst": inst_e}

musicians_k = []
mus_data = [("gayageum", (-8, 10)), ("daegeum", (-4, 10)),
             ("janggu", (0, 10)), ("gayageum", (4, 10)),
             ("daegeum", (8, 10)), ("janggu", (-12, 10))]
for i, (inst, (mx, my)) in enumerate(mus_data):
    m = make_musician_k(f"mus_k{i}", (mx, my, 0), instrument=inst, scale=1.0,
                        facing=math.radians(180))
    musicians_k.append(m)

# ============ 8 SAKURA CHERRY TREES (signature flowering) ============
def make_sakura_tree(name, loc, scale=1.0):
    base = empty(name, loc)
    # Trunk dark
    for ti in range(5):
        tz = ti * 0.6
        tilt = math.sin(ti * 0.5) * 0.05
        cyl(f"{name}_t{ti}", r=0.30 - ti*0.025, depth=0.60, segs=14,
            loc=(tilt, 0, tz + 0.30), parent=base, mat_=M_SAKURA_TRUNK)
    # Branches spreading
    branches = []
    for bi in range(7):
        ba = (bi / 7.0) * math.pi * 2 + random.uniform(-0.2, 0.2)
        br_e = empty(f"{name}_br{bi}_e", (0, 0, 3.0), parent=base)
        br_e.rotation_euler = (math.radians(random.uniform(40, 65)), 0, ba)
        cyl(f"{name}_br{bi}", r=0.12, depth=1.8, segs=10, loc=(0, 0, 0.9),
            parent=br_e, mat_=M_SAKURA_BRANCH)
        # Sub-branches
        for sb in range(3):
            sba = random.uniform(0, math.pi*2)
            sbr_e = empty(f"{name}_sbr{bi}_{sb}_e", (0, 0, 1.6), parent=br_e)
            sbr_e.rotation_euler = (math.radians(random.uniform(20, 40)), 0, sba)
            cyl(f"{name}_sbr{bi}_{sb}", r=0.05, depth=1.2, segs=8, loc=(0, 0, 0.6),
                parent=sbr_e, mat_=M_SAKURA_BRANCH)
            branches.append(sbr_e)
    # FLOWER CLUSTERS (signature pink puffs all over)
    for fi in range(180):
        fa = random.uniform(0, math.pi*2)
        fe = random.uniform(0, math.pi/2)
        fr = random.uniform(2, 5)*scale
        fx_f = math.cos(fa) * fr
        fy_f = math.sin(fa) * fr
        fz_f = 3 + math.sin(fe) * 3 + random.uniform(0, 2)
        smooth_sphere(f"{name}_fl{fi}", r=random.uniform(0.20, 0.30),
                      loc=(fx_f, fy_f, fz_f), parent=base,
                      mat_=random.choice(SAKURA_COLORS))
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

sakura_trees = []
sakura_pos = [(-30, -20, 0), (-25, 5, 0), (-30, 30, 0), (-15, 40, 0),
               (15, 40, 0), (30, 30, 0), (25, 5, 0), (30, -20, 0)]
for i, (sx, sy, sz) in enumerate(sakura_pos):
    s = make_sakura_tree(f"sakura{i}", (sx, sy, sz), scale=1.0)
    sakura_trees.append(s)

# ============ 2 HAETAE LIONS (signature mythological guardians) ============
def make_haetae(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Pedestal
    beveled_cube(f"{name}_ped", (2, 1.5, 1.5), bevel_offset=0.10, loc=(0, 0, 0.75),
                 parent=base, mat_=M_STONE_PALACE)
    # Body sitting (signature lion + dog hybrid)
    smooth_sphere(f"{name}_body", r=0.6, segs=18, rings=12, loc=(0, 0, 2.0),
                  parent=base, mat_=M_HAETAE, scale=(1.0, 1.3, 1.2))
    # Curly mane (signature)
    for mi in range(20):
        ma = (mi / 20.0) * math.pi * 2
        mp = math.cos((mi/20.0) * math.pi)
        smooth_sphere(f"{name}_m{mi}", r=0.18,
                      loc=(math.cos(ma)*0.45, math.sin(ma)*0.30 - 0.2, 2.55 + mp*0.2),
                      parent=base, mat_=M_HAETAE)
    # Head
    head_h_e = empty(f"{name}_he", (0, -0.7, 2.5), parent=base)
    smooth_sphere(f"{name}_head", r=0.40, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_h_e, mat_=M_HAETAE, scale=(1.3, 1.2, 1.0))
    # Open mouth (signature roaring)
    smooth_sphere(f"{name}_mouth", r=0.25, loc=(0, -0.30, -0.15),
                  parent=head_h_e, mat_=M_DANCHEONG_RED, scale=(1.2, 0.8, 0.6))
    # Teeth
    for ti in range(4):
        beveled_cube(f"{name}_t{ti}", (0.04, 0.05, 0.10), bevel_offset=0.005,
                     loc=((ti-1.5)*0.06, -0.30, -0.05), parent=head_h_e, mat_=M_HANBOK_WHITE)
    # Eyes glowing
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.08, loc=(side*0.20, -0.25, 0.10),
                      parent=head_h_e, mat_=M_DANCHEONG_RED)
    # Horn (signature single)
    smooth_cone(f"{name}_horn", r1=0.10, r2=0.02, depth=0.40, segs=10,
                loc=(0, 0, 0.40), parent=head_h_e, mat_=M_HAETAE)
    # Moss on stone
    smooth_sphere(f"{name}_moss1", r=0.20, loc=(0.8, 0, 1.4),
                  parent=base, mat_=M_HAETAE_MOSS, scale=(1, 0.4, 1))
    # 4 legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}{y}", r=0.15, depth=0.4, segs=10,
                loc=(x*0.3, y*0.4, 1.7), parent=base, mat_=M_HAETAE)
    # Tail curled
    for ti2 in range(4):
        ta_t = (ti2 / 4.0) * math.pi
        smooth_sphere(f"{name}_tl{ti2}", r=0.12,
                      loc=(0, 0.5 + math.cos(ta_t)*0.3, 2.2 + math.sin(ta_t)*0.4),
                      parent=base, mat_=M_HAETAE)
    return base

haetae_1 = make_haetae("haetae_L", (-7, -22, 0), scale=1.0, facing=math.radians(0))
haetae_2 = make_haetae("haetae_R", (7, -22, 0), scale=1.0, facing=math.radians(0))

# ============ STONE LANTERNS (signature garden) ============
for li in range(6):
    la = (li / 6.0) * math.pi * 2 + math.pi/12
    lx_p = math.cos(la) * 35
    ly_p = math.sin(la) * 35
    lan_e = empty(f"st_lan{li}", (lx_p, ly_p, 0))
    # Base
    cyl(f"sl{li}_b", r=0.40, depth=0.30, segs=14, loc=(0, 0, 0.15), parent=lan_e, mat_=M_STONE_PALACE)
    # Pillar
    cyl(f"sl{li}_p", r=0.18, depth=1.2, segs=12, loc=(0, 0, 0.90), parent=lan_e, mat_=M_STONE_PALACE)
    # Lantern body
    beveled_cube(f"sl{li}_lan", (0.55, 0.55, 0.55), bevel_offset=0.06,
                 loc=(0, 0, 1.80), parent=lan_e, mat_=M_STONE_PALACE)
    # Window opening lit
    for side_x in (-1, 1):
        beveled_cube(f"sl{li}_w_x{side_x}", (0.05, 0.30, 0.30), bevel_offset=0.02,
                     loc=(side_x*0.27, 0, 1.80), parent=lan_e, mat_=M_LANTERN_R)
    # Pyramidal roof
    smooth_cone(f"sl{li}_r", r1=0.50, r2=0.05, depth=0.40, segs=4, loc=(0, 0, 2.30),
                parent=lan_e, mat_=M_STONE_PALACE)

# ============ ENTRANCE GATE (signature) ============
gate_e = empty("gate", loc=(0, -45, 0))
# Posts
for side in (-1, 1):
    cyl(f"g_p{side}", r=0.5, depth=6, segs=18, loc=(side*5, 0, 3),
        parent=gate_e, mat_=M_WOOD_RED)
# Top horizontal beam
beveled_cube("g_top", (12, 0.8, 0.8), bevel_offset=0.10, loc=(0, 0, 6.5),
             parent=gate_e, mat_=M_WOOD_RED)
# Curved roof
for ri in range(6):
    rw = 13 - ri * 0.2
    beveled_cube(f"g_r{ri}", (rw, 2, 0.20), bevel_offset=0.06,
                 loc=(0, 0, 7.0 + ri*0.20), parent=gate_e, mat_=M_ROOF_DARK)
# Dancheong panels on top
for di in range(6):
    dx = -5 + di * 2
    beveled_cube(f"g_dc{di}", (1.8, 0.6, 0.30), bevel_offset=0.04,
                 loc=(dx, 0, 6.5), parent=gate_e, mat_=DC_COLORS[di % len(DC_COLORS)])

# ============================================================
# ⭐ 600 SAKURA PETALS + 400 RED LANTERNS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
sakura_petals = []
for i in range(600):
    px = random.uniform(-70, 70)
    py = random.uniform(-70, 70)
    pz = random.uniform(0.5, 18)
    p = smooth_sphere(f"sp{i}", r=random.uniform(0.06, 0.10), segs=8, rings=6,
                      loc=(px, py, pz), mat_=random.choice(SAKURA_COLORS),
                      scale=(1.4, 1, 0.3))
    p["_phase"] = random.uniform(0, math.pi*2)
    p["_base_x"] = px; p["_base_y"] = py; p["_base_z"] = pz
    p["_amp_x"] = random.uniform(1.0, 2.5)
    p["_amp_y"] = random.uniform(1.0, 2.5)
    p["_speed"] = random.uniform(0.5, 1.0)
    p["_fall"] = random.uniform(1.5, 3.0)
    sakura_petals.append(p)

# 400 floating red lanterns
floating_lanterns = []
for i in range(400):
    px = random.uniform(-60, 60)
    py = random.uniform(-60, 60)
    pz = random.uniform(3, 20)
    lan_e = empty(f"fl{i}", (px, py, pz))
    # Lantern body
    smooth_sphere(f"fl_b{i}", r=random.uniform(0.20, 0.30), segs=14, rings=10,
                  loc=(0, 0, 0), parent=lan_e, mat_=M_LANTERN_R, scale=(1, 1, 1.3))
    # Top/bottom caps
    cyl(f"fl_t{i}", r=0.10, depth=0.04, segs=10, loc=(0, 0, 0.30),
        parent=lan_e, mat_=M_LANTERN_FRAME)
    cyl(f"fl_b2{i}", r=0.10, depth=0.04, segs=10, loc=(0, 0, -0.30),
        parent=lan_e, mat_=M_LANTERN_FRAME)
    # Tassel
    cyl(f"fl_ts{i}", r=0.015, depth=0.10, segs=6, loc=(0, 0, -0.40),
        parent=lan_e, mat_=M_HANBOK_GOLD)
    lan_e["_phase"] = random.uniform(0, math.pi*2)
    lan_e["_base_x"] = px; lan_e["_base_y"] = py; lan_e["_base_z"] = pz
    lan_e["_amp_x"] = random.uniform(0.5, 1.5)
    lan_e["_amp_y"] = random.uniform(0.5, 1.5)
    lan_e["_amp_z"] = random.uniform(0.5, 1.5)
    lan_e["_speed"] = random.uniform(0.3, 0.8)
    floating_lanterns.append(lan_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Clouds drift
for ci in range(20):
    cloud = bpy.data.objects.get(f"cloud{ci}")
    if cloud is None: continue
    phase = cloud["_phase"]
    bx_c = cloud.location.x; by_c = cloud.location.y
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        cloud.location.x = bx_c + math.sin(t * 0.3 + phase) * 2.0
        cloud.location.y = by_c + math.cos(t * 0.3 + phase) * 2.0
        cloud.keyframe_insert("location", frame=f)

# Guards still + head turn
for g in guards:
    phase = g["root"]["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        g["he"].rotation_euler = (0, 0, math.sin(t * 0.5 + phase) * math.radians(20))
        g["he"].keyframe_insert("rotation_euler", frame=f)

# Hanbok women walk gracefully (sway)
for h in hanbok_women:
    phase = h["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        h["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(3),
                                     math.cos(t * 1.2 + phase) * math.radians(4),
                                     h["root"].rotation_euler.z)
        h["root"].location.z = abs(math.sin(t * 2.0 + phase)) * 0.10
        h["root"].keyframe_insert("rotation_euler", frame=f)
        h["root"].keyframe_insert("location", frame=f)
        h["he"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(15))
        h["he"].keyframe_insert("rotation_euler", frame=f)

# Musicians play (rhythmic)
for m in musicians_k:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(4),
                                     0, m["root"].rotation_euler.z)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0,
                                   math.cos(t * 2.0 + phase) * math.radians(5))
        m["he"].keyframe_insert("rotation_euler", frame=f)
        sc_i = 1 + math.sin(t * 6.0 + phase) * 0.04
        m["inst"].scale = (sc_i, sc_i, sc_i)
        m["inst"].keyframe_insert("scale", frame=f)

# King + Queen ceremonial slow
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    k_head_e.rotation_euler = (0, 0, math.sin(t * 0.4) * math.radians(10))
    k_head_e.keyframe_insert("rotation_euler", frame=f)
    q_head_e.rotation_euler = (0, 0, math.sin(t * 0.4 + math.pi) * math.radians(10))
    q_head_e.keyframe_insert("rotation_euler", frame=f)

# Sakura trees gentle sway
for s in sakura_trees:
    phase = s["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s.rotation_euler = (math.sin(t * 0.6 + phase) * math.radians(3),
                             math.cos(t * 0.6 + phase) * math.radians(3), 0)
        s.keyframe_insert("rotation_euler", frame=f)

# 600 sakura petals falling
for p in sakura_petals:
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

# 400 lanterns float bobbing
for l in floating_lanterns:
    phase = l["_phase"]; speed = l["_speed"]
    bx, by, bz = l["_base_x"], l["_base_y"], l["_base_z"]
    ax, ay, az = l["_amp_x"], l["_amp_y"], l["_amp_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        l.location = (x, y, z)
        l.rotation_euler = (math.sin(t * speed + phase) * math.radians(5),
                             math.cos(t * speed + phase) * math.radians(5), 0)
        l.keyframe_insert("location", frame=f)
        l.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_korea_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_korean_palace_gyeongbokgung_hanbok] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_korean_palace_gyeongbokgung_hanbok] palace + 12 red columns + dancheong + curved pagoda roof + throne + king+queen + 6 guards spears + 4 hanbok women + 6 musicians (gayageum+daegeum+janggu) + 2 haetae + 8 sakura trees + 6 stone lanterns + gate + 600 petals + 400 lanterns")
print("⭐ FIXES: 1 ground + 600 sakura + 400 red lanterns (signature Korea thematic mandatory) ⭐")
