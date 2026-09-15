"""
proc_russian_kremlin_red_square.py — 259e procédural AuroraIA (124e qualité)
Russian Kremlin Red Square: St Basil's 9 onion domes + Kremlin red towers + 6 soldiers ushanka + 4 women fur + giant matryoshka + 4 Cossack dancers + troika horses + 600 snow + 400 red stars
FIXES : 1 ground + 600 snowflakes + 400 red stars (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB259)

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

# Winter overcast sky
M_SKY = mat("sky", (0.55, 0.58, 0.65, 1.0), 0.0, 0.7, emission=(0.55,0.58,0.65), emission_strength=1.5)
M_CLOUD_GRY = mat("cloud_g", (0.72, 0.72, 0.75, 1.0), 0.0, 0.7, emission=(0.70,0.70,0.72), emission_strength=1.2)

# Snow ground
M_SNOW = mat("snow", (0.92, 0.94, 0.96, 1.0), 0.0, 0.40, emission=(0.88,0.92,0.96), emission_strength=0.6)
M_SNOW_BRIGHT = mat("snow_b", (0.98, 0.98, 1.0, 1.0), 0.0, 0.35, emission=(0.95,0.95,0.98), emission_strength=0.8)
M_GRANITE = mat("granite", (0.42, 0.40, 0.42, 1.0), 0.0, 0.85, emission=(0.40,0.38,0.40), emission_strength=0.3)
M_PAVE_RED = mat("pave_r", (0.55, 0.25, 0.20, 1.0), 0.0, 0.85)

# Kremlin red brick
M_KREMLIN_RED = mat("k_r", (0.72, 0.18, 0.15, 1.0), 0.0, 0.75, emission=(0.68,0.18,0.15), emission_strength=0.6)
M_KREMLIN_RED_D = mat("k_rd", (0.52, 0.15, 0.12, 1.0), 0.0, 0.85)
M_KREMLIN_WHITE = mat("k_w", (0.92, 0.92, 0.88, 1.0), 0.0, 0.65)

# Tower spires green/gold
M_SPIRE_GREEN = mat("sp_g", (0.18, 0.42, 0.28, 1.0), 0.5, 0.35, emission=(0.18,0.42,0.28), emission_strength=0.6)
M_SPIRE_GOLD = mat("sp_gd", (1.0, 0.85, 0.30, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.30), emission_strength=2.5)
M_RED_STAR = mat("rs", (1.0, 0.18, 0.18, 1.0), 0.0, 0.10, emission=(1.0,0.18,0.18), emission_strength=8.0)

# St Basil's domes (signature 9 colorful onion)
M_DOME_RED_BLUE = mat("d_rb", (0.78, 0.18, 0.45, 1.0), 0.4, 0.30, emission=(0.72,0.18,0.42), emission_strength=1.0)
M_DOME_GREEN_GOLD = mat("d_gg", (0.30, 0.65, 0.30, 1.0), 0.4, 0.30, emission=(0.28,0.62,0.30), emission_strength=1.0)
M_DOME_BLUE = mat("d_b", (0.20, 0.45, 0.85, 1.0), 0.4, 0.30, emission=(0.18,0.42,0.80), emission_strength=1.0)
M_DOME_GOLD = mat("d_g", (1.0, 0.85, 0.30, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.30), emission_strength=2.0)
M_DOME_WHITE = mat("d_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55)
M_DOME_PURPLE = mat("d_p", (0.55, 0.25, 0.78, 1.0), 0.4, 0.30, emission=(0.52,0.25,0.75), emission_strength=1.0)
M_DOME_ORANGE = mat("d_o", (1.0, 0.55, 0.20, 1.0), 0.0, 0.50, emission=(0.95,0.55,0.20), emission_strength=0.8)
M_DOME_GREEN_DARK = mat("d_gd", (0.10, 0.42, 0.20, 1.0), 0.5, 0.35, emission=(0.10,0.40,0.20), emission_strength=0.8)
M_DOME_STRIPED = mat("d_st", (0.42, 0.20, 0.18, 1.0), 0.0, 0.55)
DOME_COLORS = [M_DOME_RED_BLUE, M_DOME_GREEN_GOLD, M_DOME_BLUE, M_DOME_GOLD,
                M_DOME_WHITE, M_DOME_PURPLE, M_DOME_ORANGE, M_DOME_GREEN_DARK, M_DOME_STRIPED]

# Skin
M_SKIN_PALE_R = mat("skin", (0.95, 0.82, 0.72, 1.0), 0.0, 0.55, emission=(0.90,0.80,0.72), emission_strength=0.4)
M_CHEEK_PINK = mat("cheek", (0.95, 0.55, 0.55, 1.0), 0.0, 0.55, emission=(0.92,0.55,0.55), emission_strength=0.6)

# Hair
M_HAIR_BLOND_R = mat("h_bl", (0.78, 0.62, 0.32, 1.0), 0.0, 0.55)
M_HAIR_BROWN_R = mat("h_br", (0.32, 0.18, 0.10, 1.0), 0.0, 0.60)
M_HAIR_BLACK_R = mat("h_bk", (0.10, 0.06, 0.04, 1.0), 0.0, 0.55)

# Soldier uniform (signature green coat)
M_UNIFORM_GREEN = mat("uni_g", (0.18, 0.32, 0.22, 1.0), 0.0, 0.75, emission=(0.18,0.30,0.22), emission_strength=0.4)
M_UNIFORM_RED = mat("uni_r", (0.65, 0.18, 0.18, 1.0), 0.0, 0.65)
M_UNIFORM_GOLD = mat("uni_g_b", (0.92, 0.78, 0.20, 1.0), 0.85, 0.25, emission=(0.88,0.75,0.20), emission_strength=1.2)
M_UNIFORM_BLACK = mat("uni_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.75)

# Ushanka fur (signature Russian hat)
M_FUR_BROWN_R = mat("fur_b", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85, emission=(0.30,0.20,0.10), emission_strength=0.3)
M_FUR_GREY = mat("fur_g", (0.55, 0.50, 0.45, 1.0), 0.0, 0.85)
M_FUR_BLACK = mat("fur_bk", (0.15, 0.12, 0.10, 1.0), 0.0, 0.85)
M_FUR_WHITE = mat("fur_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.85, emission=(0.90,0.88,0.85), emission_strength=0.5)

# Long fur coat
M_COAT_BROWN_R = mat("co_b", (0.42, 0.28, 0.15, 1.0), 0.0, 0.80, emission=(0.40,0.28,0.15), emission_strength=0.4)
M_COAT_BLACK = mat("co_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.80)
M_COAT_RED = mat("co_r", (0.65, 0.18, 0.18, 1.0), 0.0, 0.70, emission=(0.60,0.18,0.18), emission_strength=0.5)

# Matryoshka (signature)
M_MAT_RED = mat("mt_r", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.18), emission_strength=0.8)
M_MAT_YELLOW = mat("mt_y", (0.95, 0.85, 0.32, 1.0), 0.0, 0.55, emission=(0.90,0.82,0.32), emission_strength=0.7)
M_MAT_WHITE = mat("mt_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55)
M_MAT_BLUE = mat("mt_b", (0.20, 0.42, 0.78, 1.0), 0.0, 0.55, emission=(0.20,0.42,0.78), emission_strength=0.6)
M_MAT_GREEN = mat("mt_g", (0.18, 0.55, 0.32, 1.0), 0.0, 0.55, emission=(0.18,0.52,0.30), emission_strength=0.6)
M_MAT_PINK = mat("mt_p", (0.95, 0.55, 0.78, 1.0), 0.0, 0.55, emission=(0.92,0.55,0.75), emission_strength=0.6)

# Cossack costume (signature)
M_COSSACK_RED = mat("cos_r", (0.85, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.80,0.15,0.15), emission_strength=0.6)
M_COSSACK_BLACK = mat("cos_bk", (0.12, 0.10, 0.10, 1.0), 0.0, 0.80)
M_COSSACK_BLUE = mat("cos_b", (0.20, 0.42, 0.78, 1.0), 0.0, 0.65, emission=(0.20,0.42,0.78), emission_strength=0.5)
M_COSSACK_BELT = mat("cos_belt", (0.18, 0.10, 0.06, 1.0), 0.0, 0.75)

# Horse colors
M_HORSE_BAY = mat("h_bay", (0.45, 0.25, 0.12, 1.0), 0.0, 0.75, emission=(0.42,0.25,0.12), emission_strength=0.4)
M_HORSE_WHITE = mat("h_wh", (0.92, 0.88, 0.82, 1.0), 0.0, 0.70)
M_HORSE_BLACK = mat("h_blk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.80)
M_HORSE_MANE = mat("h_mn", (0.20, 0.12, 0.08, 1.0), 0.0, 0.65)
HORSE_COLORS_R = [M_HORSE_BAY, M_HORSE_WHITE, M_HORSE_BLACK]

# Troika sleigh
M_SLEIGH_RED_R = mat("sl_r", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.18), emission_strength=0.7)
M_SLEIGH_GOLD_R = mat("sl_g", (1.0, 0.85, 0.30, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.30), emission_strength=1.5)
M_SLEIGH_WOOD = mat("sl_w", (0.55, 0.30, 0.15, 1.0), 0.0, 0.75)

# Balalaika
M_BALALAIKA = mat("bal", (0.42, 0.25, 0.12, 1.0), 0.0, 0.55, emission=(0.40,0.25,0.12), emission_strength=0.4)
M_BAL_DARK = mat("bal_d", (0.18, 0.10, 0.06, 1.0), 0.0, 0.85)
M_BAL_STRING = mat("bal_s", (0.85, 0.85, 0.85, 1.0), 0.5, 0.30)

# Accordion
M_ACC_RED = mat("acc_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.72,0.18,0.18), emission_strength=0.6)
M_ACC_WHITE = mat("acc_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55)
M_ACC_BLACK = mat("acc_bk", (0.10, 0.08, 0.08, 1.0), 0.3, 0.40)

# Eye / lips
M_EYE_DARK_R = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_BLUE_R = mat("eye_b", (0.30, 0.55, 0.85, 1.0), 0.0, 0.20, emission=(0.28,0.52,0.82), emission_strength=1.2)
M_LIPS_RED_R = mat("lips", (0.78, 0.18, 0.30, 1.0), 0.0, 0.40)

# Snowflake
M_SNOWFLAKE = mat("sf", (0.95, 0.95, 0.98, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.95), emission_strength=2.5, alpha=0.85)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Snow clouds heavy
for ci in range(25):
    cax = random.uniform(-100, 100); cay = random.uniform(-100, 100)
    caz = random.uniform(30, 65)
    cloud_e = empty(f"cloud{ci}", (cax, cay, caz))
    for cli in range(random.randint(3, 5)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(3, 5), segs=16, rings=10,
                      loc=(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD_GRY, scale=(1.4, 1.2, 0.7))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)

# ============ ONE clean snowy granite ground (Red Square pavement) ============
ground = beveled_cube("ground", (180, 180, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_SNOW)
# Granite paving plaza signature
plaza = beveled_cube("plaza", (60, 80, 0.30), bevel_offset=0.10, loc=(0, 0, 0.10), mat_=M_GRANITE)
# Tile pattern Red Square
for ti in range(40):
    for tj in range(50):
        tx_g = -57 + ti * 3
        ty_g = -75 + tj * 3
        if abs(tx_g) > 30 or abs(ty_g) > 40: continue
        if (ti + tj) % 8 == 0:
            beveled_cube(f"tile_pave{ti}_{tj}", (2.8, 2.8, 0.05), bevel_offset=0.02,
                         loc=(tx_g, ty_g, 0.27), mat_=M_PAVE_RED)
# Snow patches on ground
for si in range(150):
    sx_s = random.uniform(-70, 70); sy_s = random.uniform(-70, 70)
    if -28 < sx_s < 28 and -38 < sy_s < 38 and random.random() > 0.3: continue
    smooth_sphere(f"snow_p{si}", r=random.uniform(0.3, 0.8), segs=10, rings=8,
                  loc=(sx_s, sy_s, 0.15), mat_=M_SNOW_BRIGHT, scale=(1.5, 1.4, 0.20))

# ============ ST BASIL'S CATHEDRAL (signature 9 colorful onion domes) ============
basil_e = empty("basil", loc=(0, 30, 0))
# Main central body
beveled_cube("bs_base", (12, 12, 2), bevel_offset=0.10, loc=(0, 0, 1),
             parent=basil_e, mat_=M_KREMLIN_RED)
# Central tower (tallest)
cyl("bs_central_t", r=2, depth=10, segs=20, loc=(0, 0, 7), parent=basil_e, mat_=M_KREMLIN_RED)
# Central tier white
beveled_cube("bs_c_tier", (5, 5, 2), bevel_offset=0.15, loc=(0, 0, 12),
             parent=basil_e, mat_=M_KREMLIN_WHITE)
# Central tower spire base
cyl("bs_c_tower", r=1.5, depth=4, segs=18, loc=(0, 0, 15), parent=basil_e, mat_=M_KREMLIN_RED)
# Central DOME (largest signature onion shape)
def make_onion_dome(name, loc, scale=1.0, parent=None, dome_mat=None, twist_stripes=False):
    base_e = empty(name, loc, parent=parent)
    # Onion shape (signature bulging bottom)
    smooth_sphere(f"{name}_lower", r=1.0*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=base_e, mat_=dome_mat, scale=(1, 1, 1.2))
    # Bulge bottom (signature)
    smooth_sphere(f"{name}_bulge", r=1.1*scale, segs=20, rings=14, loc=(0, 0, -0.20*scale),
                  parent=base_e, mat_=dome_mat, scale=(1, 1, 0.5))
    # Top pinch
    smooth_sphere(f"{name}_pinch", r=0.40*scale, segs=14, rings=10, loc=(0, 0, 1.05*scale),
                  parent=base_e, mat_=dome_mat)
    # Spiral stripes (signature twisted dome)
    if twist_stripes:
        for si in range(8):
            sa = (si / 8.0) * math.pi * 2
            for sti in range(10):
                sti_a = sa + sti * 0.3
                stx = math.cos(sti_a) * (1.0 - sti*0.05) * scale
                sty = math.sin(sti_a) * (1.0 - sti*0.05) * scale
                stz = sti * 0.15 * scale - 0.2
                if stz > 1.2 * scale: break
                smooth_sphere(f"{name}_str{si}_{sti}", r=0.05*scale,
                              loc=(stx, sty, stz), parent=base_e, mat_=M_DOME_GOLD)
    # Cross on top (signature Russian Orthodox)
    cyl(f"{name}_cross_p", r=0.04*scale, depth=0.5*scale, segs=8, loc=(0, 0, 1.5*scale),
        parent=base_e, mat_=M_SPIRE_GOLD)
    beveled_cube(f"{name}_cross_h1", (0.05*scale, 0.3*scale, 0.05*scale), bevel_offset=0.01,
                 loc=(0, 0, 1.6*scale), parent=base_e, mat_=M_SPIRE_GOLD)
    beveled_cube(f"{name}_cross_h2", (0.05*scale, 0.2*scale, 0.05*scale), bevel_offset=0.01,
                 loc=(0, 0, 1.4*scale), parent=base_e, mat_=M_SPIRE_GOLD)
    # Diagonal bar (signature 3-bar Orthodox)
    beveled_cube(f"{name}_cross_d", (0.05*scale, 0.18*scale, 0.05*scale), bevel_offset=0.01,
                 loc=(0, 0, 1.30*scale), parent=base_e, mat_=M_SPIRE_GOLD).rotation_euler = (math.radians(20), 0, 0)
    return base_e

# Central largest dome
central_dome = make_onion_dome("c_dome", (0, 0, 18), scale=2.0, parent=basil_e,
                                 dome_mat=M_DOME_GOLD)

# 8 surrounding smaller domes (signature)
dome_positions_b = [
    (-4, -4, 8, M_DOME_RED_BLUE, True),
    (4, -4, 8, M_DOME_GREEN_GOLD, False),
    (-4, 4, 8, M_DOME_BLUE, False),
    (4, 4, 8, M_DOME_PURPLE, True),
    (-7, 0, 9, M_DOME_ORANGE, False),
    (7, 0, 9, M_DOME_WHITE, True),
    (0, -7, 9, M_DOME_GREEN_DARK, False),
    (0, 7, 9, M_DOME_STRIPED, True)
]
for di, (dx, dy, dz, dmat, twist) in enumerate(dome_positions_b):
    # Tower below dome
    cyl(f"bs_dt{di}", r=1.2, depth=6, segs=18, loc=(dx, dy, dz/2 + 2),
        parent=basil_e, mat_=M_KREMLIN_RED)
    # Decorative arch
    smooth_sphere(f"bs_da{di}", r=1.3, segs=18, rings=10, loc=(dx, dy, dz),
                  parent=basil_e, mat_=M_KREMLIN_WHITE, scale=(1, 1, 0.4))
    # Dome with cross
    dome = make_onion_dome(f"d{di}", (dx, dy, dz + 1), scale=1.1, parent=basil_e,
                            dome_mat=dmat, twist_stripes=twist)

# Decorative arches/windows on main body
for ai in range(8):
    aa = (ai / 8.0) * math.pi * 2
    smooth_sphere(f"bs_ar{ai}", r=0.6, segs=14, rings=10,
                  loc=(math.cos(aa)*5.8, math.sin(aa)*5.8, 3),
                  parent=basil_e, mat_=M_KREMLIN_WHITE, scale=(1, 0.2, 1.5))

# ============ KREMLIN WALL (signature red brick) ============
kremlin_wall_e = empty("k_wall", loc=(0, -25, 0))
# Long wall sections
wall_segs_k = [
    ((-30, 0), (30, 0), 6),    # front
    ((-30, 0), (-30, -20), 6),  # left
    ((30, 0), (30, -20), 6),    # right
]
for wi, (start, end, h) in enumerate(wall_segs_k):
    sx, sy = start; ex, ey = end
    mx = (sx + ex) / 2; my = (sy + ey) / 2
    wlen = math.sqrt((ex-sx)**2 + (ey-sy)**2)
    wang = math.atan2(ey-sy, ex-sx)
    # Wall
    seg = beveled_cube(f"kw{wi}", (wlen, 1.5, h), bevel_offset=0.10,
                       loc=(mx, my, h/2), parent=kremlin_wall_e, mat_=M_KREMLIN_RED)
    seg.rotation_euler = (0, 0, wang)
    # Brick line details
    for bi in range(int(h)):
        beveled_cube(f"kw{wi}_b{bi}", (wlen+0.1, 1.55, 0.10), bevel_offset=0.04,
                     loc=(mx, my, 0.5 + bi*1.0), parent=kremlin_wall_e, mat_=M_KREMLIN_RED_D).rotation_euler = (0, 0, wang)
    # SWALLOW-TAIL CRENELLATIONS signature
    n_cren = int(wlen / 2.5)
    for ci in range(n_cren):
        cy_pos = (ci - n_cren/2 + 0.5) * 2.5
        cx_pos = mx + cy_pos * math.cos(wang)
        cy_p = my + cy_pos * math.sin(wang)
        # M-shape signature (2 peaks)
        for ms in (-1, 1):
            beveled_cube(f"kw{wi}_cr{ci}_{ms}", (0.6, 1.6, 1.0), bevel_offset=0.06,
                         loc=(cx_pos + ms*math.cos(wang)*0.3 - math.sin(wang)*ms*0.3,
                              cy_p + ms*math.sin(wang)*0.3 + math.cos(wang)*ms*0.3,
                              h + 0.5), parent=kremlin_wall_e, mat_=M_KREMLIN_RED).rotation_euler = (0, 0, wang)

# ============ KREMLIN TOWERS (signature 5 prominent) ============
tower_positions_k = [(0, 0, 0), (-30, 0, 0), (30, 0, 0), (-30, -20, 0), (30, -20, 0)]
for ti, (tx, ty, tz) in enumerate(tower_positions_k):
    t_e = empty(f"kt{ti}", (tx, ty, tz + 0), parent=kremlin_wall_e)
    # Square base
    beveled_cube(f"kt_b{ti}", (4, 4, 4), bevel_offset=0.10, loc=(0, 0, 2),
                 parent=t_e, mat_=M_KREMLIN_RED)
    # Body taller
    beveled_cube(f"kt_body{ti}", (3.5, 3.5, 6), bevel_offset=0.10, loc=(0, 0, 7),
                 parent=t_e, mat_=M_KREMLIN_RED)
    # Decorative top crenellations
    for ci in range(4):
        ca = (ci / 4.0) * math.pi * 2
        beveled_cube(f"kt_cr{ti}_{ci}", (1.0, 1.0, 1.0), bevel_offset=0.06,
                     loc=(math.cos(ca)*1.5, math.sin(ca)*1.5, 10.5),
                     parent=t_e, mat_=M_KREMLIN_RED)
    # Decorative roof
    beveled_cube(f"kt_roof{ti}", (4, 4, 1), bevel_offset=0.10, loc=(0, 0, 11.5),
                 parent=t_e, mat_=M_KREMLIN_WHITE)
    # Pyramidal green spire (signature)
    smooth_cone(f"kt_s{ti}", r1=1.5, r2=0.10, depth=5, segs=14, loc=(0, 0, 14.5),
                parent=t_e, mat_=M_SPIRE_GREEN)
    # RED STAR on top (signature Soviet)
    star_e = empty(f"kt_st{ti}", (0, 0, 17.5), parent=t_e)
    # 5-point star body
    for pi in range(5):
        pa = (pi / 5.0) * math.pi * 2 + math.pi/2
        smooth_cone(f"kt_st_p{ti}_{pi}", r1=0.10, r2=0.005, depth=0.50, segs=8,
                    loc=(math.cos(pa)*0.30, math.sin(pa)*0.30, 0),
                    parent=star_e, mat_=M_RED_STAR).rotation_euler = (0, math.radians(90), pa)
    smooth_sphere(f"kt_st_c{ti}", r=0.20, loc=(0, 0, 0), parent=star_e, mat_=M_RED_STAR)
    # Windows
    for wi in range(3):
        wz = 4 + wi * 2
        beveled_cube(f"kt_w{ti}_{wi}", (0.5, 0.6, 0.8), bevel_offset=0.06,
                     loc=(0, -1.8, wz), parent=t_e, mat_=M_SPIRE_GOLD)

# ============ 6 RUSSIAN SOLDIERS (signature ushanka) ============
def make_soldier(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Green wool coat (signature long)
    smooth_cone(f"{name}_coat", r1=0.35, r2=0.32, depth=1.5, segs=14, loc=(0, 0, 0.85),
                parent=base, mat_=M_UNIFORM_GREEN)
    # Belt
    cyl(f"{name}_belt", r=0.36, depth=0.10, segs=14, loc=(0, 0, 1.05),
        parent=base, mat_=M_UNIFORM_BLACK)
    # Buckle red star signature
    beveled_cube(f"{name}_buc", (0.10, 0.10, 0.15), bevel_offset=0.02, loc=(0, -0.35, 1.05),
                 parent=base, mat_=M_RED_STAR)
    # Buttons row
    for bi in range(5):
        smooth_sphere(f"{name}_btn{bi}", r=0.03, loc=(0, -0.32, 1.30 + bi*0.15),
                      parent=base, mat_=M_UNIFORM_GOLD)
    # Shoulder boards (signature)
    for side in (-1, 1):
        beveled_cube(f"{name}_sb{side}", (0.20, 0.10, 0.06), bevel_offset=0.02,
                     loc=(side*0.30, 0, 2.0), parent=base, mat_=M_UNIFORM_RED)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.11, depth=1.0, segs=10,
            loc=(side*0.13, 0, 0.5), parent=base, mat_=M_UNIFORM_GREEN)
    # BOOTS tall black (signature)
    for side in (-1, 1):
        cyl(f"{name}_bt{side}", r=0.13, depth=0.55, segs=12,
            loc=(side*0.13, 0, 0.28), parent=base, mat_=M_UNIFORM_BLACK)
        beveled_cube(f"{name}_btf{side}", (0.14, 0.25, 0.10), bevel_offset=0.02,
                     loc=(side*0.13, 0.05, 0), parent=base, mat_=M_UNIFORM_BLACK)
    # Arms straight down (parade pose)
    for side in (-1, 1):
        sh = empty(f"{name}_sh{side}", (side*0.32, 0, 1.85), parent=base)
        sh.rotation_euler = (math.radians(-10), 0, math.radians(side*-3))
        cyl(f"{name}_uarm{side}", r=0.07, depth=0.40, segs=10,
            loc=(0, 0, -0.20), parent=sh, mat_=M_UNIFORM_GREEN)
        cyl(f"{name}_fa{side}", r=0.06, depth=0.35, segs=10,
            loc=(0, 0, -0.55), parent=sh, mat_=M_UNIFORM_GREEN)
        # Gloves
        smooth_sphere(f"{name}_gl{side}", r=0.07, loc=(0, 0, -0.78),
                      parent=sh, mat_=M_UNIFORM_BLACK)
    # Head
    head_s_e = empty(f"{name}_he", (0, 0, 2.15), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_s_e, mat_=M_SKIN_PALE_R)
    # Cheeks pink (cold)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ch{side}", r=0.06, loc=(side*0.13, -0.16, -0.05),
                      parent=head_s_e, mat_=M_CHEEK_PINK)
    # Eyes blue
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_s_e, mat_=M_EYE_BLUE_R)
    # USHANKA fur hat (signature)
    fur_col = random.choice([M_FUR_BROWN_R, M_FUR_GREY, M_FUR_BLACK])
    hat_u_e = empty(f"{name}_hat", (0, 0, 0.20), parent=head_s_e)
    # Body
    smooth_sphere(f"{name}_hat_b", r=0.21, segs=18, rings=14, loc=(0, 0, 0.05),
                  parent=hat_u_e, mat_=fur_col, scale=(1, 1, 0.9))
    # Front earflap (signature down or up)
    beveled_cube(f"{name}_hat_f", (0.36, 0.10, 0.18), bevel_offset=0.04,
                 loc=(0, -0.20, -0.06), parent=hat_u_e, mat_=fur_col)
    # Side earflaps signature
    for side in (-1, 1):
        beveled_cube(f"{name}_hat_e{side}", (0.10, 0.18, 0.25), bevel_offset=0.04,
                     loc=(side*0.20, 0, -0.05), parent=hat_u_e, mat_=fur_col)
    # Red star on front (signature Soviet)
    smooth_sphere(f"{name}_hat_st", r=0.07, loc=(0, -0.22, 0.05),
                  parent=hat_u_e, mat_=M_RED_STAR, scale=(1, 0.2, 1))
    # RIFLE held vertically (signature parade)
    rifle_e = empty(f"{name}_rifle", (0.32, 0, 0.5), parent=base)
    rifle_e.rotation_euler = (0, 0, 0)
    # Stock wood
    beveled_cube(f"{name}_rf_s", (0.06, 0.10, 0.6), bevel_offset=0.03,
                 loc=(0, 0, 0.30), parent=rifle_e, mat_=M_SLEIGH_WOOD)
    # Barrel steel
    cyl(f"{name}_rf_b", r=0.025, depth=1.0, segs=8, loc=(0, 0, 1.20),
        parent=rifle_e, mat_=M_UNIFORM_BLACK)
    # Bayonet
    smooth_cone(f"{name}_rf_ba", r1=0.025, r2=0.005, depth=0.30, segs=6,
                loc=(0, 0, 1.85), parent=rifle_e, mat_=M_BAL_STRING)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_s_e}

soldiers = []
soldier_pos = [(-10, 5, math.radians(0)), (-5, 5, math.radians(0)),
                (0, 5, math.radians(0)), (5, 5, math.radians(0)),
                (10, 5, math.radians(0)), (-3, 12, math.radians(0))]
for i, (sx, sy, fac) in enumerate(soldier_pos):
    s = make_soldier(f"soldier{i}", (sx, sy, 0), scale=1.0, facing=fac)
    soldiers.append(s)

# ============ 4 WOMEN with fur coats (signature) ============
def make_russian_woman(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    coat_col = random.choice([M_COAT_BROWN_R, M_COAT_BLACK, M_COAT_RED])
    # LONG FUR COAT (signature)
    smooth_cone(f"{name}_coat", r1=0.55, r2=0.40, depth=1.7, segs=18, loc=(0, 0, 0.95),
                parent=base, mat_=coat_col)
    # Fur trim bottom
    cyl(f"{name}_trim_b", r=0.56, depth=0.15, segs=18, loc=(0, 0, 0.20),
        parent=base, mat_=M_FUR_WHITE)
    # Fur collar signature (huge)
    smooth_sphere(f"{name}_collar", r=0.30, segs=18, rings=14, loc=(0, -0.05, 1.95),
                  parent=base, mat_=M_FUR_WHITE, scale=(1.5, 0.6, 1))
    # Belt
    cyl(f"{name}_belt", r=0.45, depth=0.10, segs=18, loc=(0, 0, 1.30),
        parent=base, mat_=M_UNIFORM_BLACK)
    # Arms in pockets pose
    for side in (-1, 1):
        sh = empty(f"{name}_sh{side}", (side*0.40, 0, 1.85), parent=base)
        sh.rotation_euler = (math.radians(-40), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side}", r=0.08, depth=0.40, segs=10,
            loc=(0, 0, -0.20), parent=sh, mat_=coat_col)
        cyl(f"{name}_fa{side}", r=0.07, depth=0.35, segs=10,
            loc=(0, 0, -0.55), parent=sh, mat_=M_FUR_WHITE)
    # Head
    head_w_e = empty(f"{name}_he", (0, 0, 2.15), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_w_e, mat_=M_SKIN_PALE_R)
    # Pink cheeks
    for side in (-1, 1):
        smooth_sphere(f"{name}_ch{side}", r=0.06, loc=(side*0.13, -0.16, -0.05),
                      parent=head_w_e, mat_=M_CHEEK_PINK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_w_e, mat_=M_EYE_BLUE_R)
    # Red lips
    beveled_cube(f"{name}_lips", (0.06, 0.04, 0.02), bevel_offset=0.005,
                 loc=(0, -0.18, -0.06), parent=head_w_e, mat_=M_LIPS_RED_R)
    # FUR HAT (signature huge)
    fur_col_h = random.choice([M_FUR_BROWN_R, M_FUR_WHITE, M_FUR_BLACK])
    smooth_sphere(f"{name}_hat", r=0.28, segs=20, rings=14, loc=(0, 0, 0.20),
                  parent=head_w_e, mat_=fur_col_h, scale=(1.2, 1.2, 0.85))
    # Hair flowing
    for hi in range(12):
        ha = random.uniform(0, math.pi*2)
        hl_w = random.uniform(0.20, 0.40)
        beveled_cube(f"{name}_hr{hi}", (0.05, 0.07, hl_w), bevel_offset=0.01,
                     loc=(math.cos(ha)*0.16, math.sin(ha)*0.10 + 0.08, -hl_w/2),
                     parent=head_w_e, mat_=random.choice([M_HAIR_BLOND_R, M_HAIR_BROWN_R, M_HAIR_BLACK_R]))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_w_e}

women_r = []
women_pos = [(-15, 0, math.radians(30)), (-12, -5, math.radians(-30)),
              (12, -5, math.radians(30)), (15, 0, math.radians(-30))]
for i, (wx, wy, fac) in enumerate(women_pos):
    w = make_russian_woman(f"woman_r{i}", (wx, wy, 0), scale=1.0, facing=fac)
    women_r.append(w)

# ============ GIANT MATRYOSHKA (signature) ============
matryoshka_e = empty("matryoshka", loc=(0, -8, 0))
# Body (egg-shape signature)
smooth_sphere("mt_body", r=2, segs=24, rings=18, loc=(0, 0, 2),
              parent=matryoshka_e, mat_=M_MAT_RED, scale=(1, 1, 1.4))
# White face area (signature)
smooth_sphere("mt_face_bg", r=0.9, segs=20, rings=14, loc=(0, -1.0, 3),
              parent=matryoshka_e, mat_=M_MAT_WHITE, scale=(1, 0.3, 1.1))
# Scarf yellow (signature triangular)
beveled_cube("mt_scarf_b", (2.0, 0.10, 0.8), bevel_offset=0.06, loc=(0, -1.05, 3.7),
             parent=matryoshka_e, mat_=M_MAT_YELLOW)
# Floral pattern apron front (signature)
for fi in range(20):
    fa = random.uniform(0, math.pi*2); fe = random.uniform(0.2, 0.8)
    fx_f = math.sin(fe) * math.cos(fa) * 1.6
    fz_f = math.cos(fe) * 0.5 + 2.0
    if fx_f < 0: continue
    smooth_sphere(f"mt_fl{fi}", r=0.15, loc=(0, -1.5, fz_f),
                  parent=matryoshka_e,
                  mat_=random.choice([M_MAT_PINK, M_MAT_BLUE, M_MAT_GREEN, M_MAT_YELLOW]))
# Eyes (signature big)
for side in (-1, 1):
    smooth_sphere(f"mt_eye{side}", r=0.10, loc=(side*0.25, -1.6, 3.2),
                  parent=matryoshka_e, mat_=M_MAT_WHITE)
    smooth_sphere(f"mt_pup{side}", r=0.05, loc=(side*0.25, -1.7, 3.2),
                  parent=matryoshka_e, mat_=M_EYE_DARK_R)
# Red cheeks
for side in (-1, 1):
    smooth_sphere(f"mt_ch{side}", r=0.10, loc=(side*0.35, -1.65, 2.95),
                  parent=matryoshka_e, mat_=M_CHEEK_PINK)
# Small red lips
beveled_cube("mt_lips", (0.20, 0.06, 0.08), bevel_offset=0.02, loc=(0, -1.7, 2.85),
             parent=matryoshka_e, mat_=M_LIPS_RED_R)
# Wood pedestal
cyl("mt_ped", r=1.5, depth=0.30, segs=18, loc=(0, 0, 0.15), parent=matryoshka_e, mat_=M_SLEIGH_WOOD)

# ============ 4 COSSACK DANCERS (signature kazatchok) ============
def make_cossack(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Red tunic with embroidery
    smooth_cone(f"{name}_tunic", r1=0.30, r2=0.32, depth=0.75, segs=14, loc=(0, 0, 1.20),
                parent=base, mat_=M_COSSACK_RED)
    # Black belt
    cyl(f"{name}_belt", r=0.33, depth=0.10, segs=14, loc=(0, 0, 0.95),
        parent=base, mat_=M_COSSACK_BELT)
    # Black pants (baggy signature)
    for side in (-1, 1):
        cyl(f"{name}_pants{side}", r=0.15, depth=0.95, segs=12,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=M_COSSACK_BLACK)
        # Tall boots
        cyl(f"{name}_bt{side}", r=0.12, depth=0.50, segs=12,
            loc=(side*0.13, 0, 0.25), parent=base, mat_=M_COSSACK_BLACK)
    # Arms crossed/akimbo (signature dance pose)
    for side in (-1, 1):
        sh = empty(f"{name}_sh{side}", (side*0.32, 0, 1.55), parent=base)
        sh.rotation_euler = (math.radians(-80), 0, math.radians(side*40))
        cyl(f"{name}_uarm{side}", r=0.06, depth=0.40, segs=10,
            loc=(0, 0, -0.20), parent=sh, mat_=M_COSSACK_RED)
        cyl(f"{name}_fa{side}", r=0.05, depth=0.30, segs=10,
            loc=(0, 0, -0.55), parent=sh, mat_=M_SKIN_PALE_R)
    # Embroidery patterns on tunic
    for ei in range(8):
        ea = (ei / 8.0) * math.pi * 2
        beveled_cube(f"{name}_em{ei}", (0.04, 0.04, 0.55), bevel_offset=0.005,
                     loc=(math.cos(ea)*0.31, math.sin(ea)*0.31, 1.20),
                     parent=base, mat_=M_MAT_YELLOW)
    # Head
    head_c_e = empty(f"{name}_he", (0, 0, 1.85), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_c_e, mat_=M_SKIN_PALE_R)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_c_e, mat_=M_EYE_BLUE_R)
    # Big moustache signature
    for side in (-1, 1):
        for mi in range(3):
            smooth_sphere(f"{name}_mou{side}_{mi}", r=0.03,
                          loc=(side*(0.05 + mi*0.04), -0.17, -0.06),
                          parent=head_c_e, mat_=M_HAIR_BLOND_R)
    # Hair
    for hi in range(6):
        ha = (hi / 6.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.05,
                      loc=(math.cos(ha)*0.13, math.sin(ha)*0.10, 0.10),
                      parent=head_c_e, mat_=M_HAIR_BLOND_R)
    # PAPAKHA fur hat (signature tall Cossack)
    hat_p_e = empty(f"{name}_hat", (0, 0, 0.20), parent=head_c_e)
    cyl(f"{name}_hat_c", r=0.20, depth=0.30, segs=14, loc=(0, 0, 0.20),
        parent=hat_p_e, mat_=M_FUR_BLACK)
    smooth_sphere(f"{name}_hat_t", r=0.18, loc=(0, 0, 0.35),
                  parent=hat_p_e, mat_=M_FUR_BLACK, scale=(1, 1, 0.5))
    # Red top piece signature
    smooth_sphere(f"{name}_hat_r", r=0.10, loc=(0, 0, 0.40),
                  parent=hat_p_e, mat_=M_COSSACK_RED)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_c_e}

cossacks = []
cossack_pos = [(-8, -15, math.radians(0)), (8, -15, math.radians(0)),
                (-5, -20, math.radians(0)), (5, -20, math.radians(0))]
for i, (cx, cy, fac) in enumerate(cossack_pos):
    c = make_cossack(f"cossack{i}", (cx, cy, 0), scale=1.0, facing=fac)
    cossacks.append(c)

# ============ MUSICIANS with accordion + balalaika ============
def make_musician_r(name, loc, instrument, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body red tunic
    smooth_cone(f"{name}_t", r1=0.32, r2=0.34, depth=0.7, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=M_COSSACK_RED)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.11, depth=1.0, segs=10,
            loc=(side*0.13, 0, 0.5), parent=base, mat_=M_COSSACK_BLACK)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN_PALE_R)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_m_e, mat_=M_EYE_BLUE_R)
    # Ushanka
    smooth_sphere(f"{name}_hat", r=0.22, segs=18, rings=14, loc=(0, 0, 0.20),
                  parent=head_m_e, mat_=M_FUR_BROWN_R, scale=(1, 1, 0.9))
    # Instrument
    inst_e = empty(f"{name}_inst", (0, -0.30, 1.30), parent=base)
    if instrument == "accordion":
        # Body (signature bellows)
        beveled_cube(f"{name}_acc", (0.55, 0.30, 0.45), bevel_offset=0.06, loc=(0, 0, 0),
                     parent=inst_e, mat_=M_ACC_RED)
        # Bellows folds
        for fi in range(8):
            beveled_cube(f"{name}_af{fi}", (0.50, 0.30, 0.04), bevel_offset=0.01,
                         loc=(-0.20 + fi*0.06, 0, 0), parent=inst_e, mat_=M_ACC_BLACK)
        # Keyboards
        for side in (-1, 1):
            beveled_cube(f"{name}_ak{side}", (0.06, 0.25, 0.35), bevel_offset=0.02,
                         loc=(side*0.30, 0, 0), parent=inst_e, mat_=M_ACC_WHITE)
    elif instrument == "balalaika":
        # Triangular body (signature)
        for ti in range(3):
            ta = (ti / 3.0) * math.pi * 2 + math.pi/2
            beveled_cube(f"{name}_bb{ti}", (0.35, 0.06, 0.30), bevel_offset=0.04,
                         loc=(math.cos(ta)*0.10, 0, math.sin(ta)*0.10 + 0.20),
                         parent=inst_e, mat_=M_BALALAIKA).rotation_euler = (0, 0, ta - math.pi/2)
        # Body main
        beveled_cube(f"{name}_bb_b", (0.40, 0.10, 0.40), bevel_offset=0.08, loc=(0, 0, 0.10),
                     parent=inst_e, mat_=M_BALALAIKA)
        # Neck
        cyl(f"{name}_bb_n", r=0.025, depth=0.70, segs=10, loc=(0, 0, 0.55),
            parent=inst_e, mat_=M_BAL_DARK)
        # 3 strings
        for st in range(3):
            cyl(f"{name}_bb_s{st}", r=0.005, depth=0.80, segs=6,
                loc=((st-1)*0.012, -0.05, 0.30), parent=inst_e,
                mat_=M_BAL_STRING)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "inst": inst_e, "he": head_m_e}

musicians_r = []
mus_r_pos = [("accordion", -15, -22), ("balalaika", 15, -22)]
for i, (inst, mx, my) in enumerate(mus_r_pos):
    m = make_musician_r(f"mus_r{i}", (mx, my, 0), instrument=inst, scale=1.0,
                        facing=math.radians(0))
    musicians_r.append(m)

# ============ TROIKA (signature 3 horses + sleigh) ============
troika_e = empty("troika", loc=(-25, -25, 0))
troika_e.rotation_euler = (0, 0, math.radians(30))

# SLEIGH signature red curved
sleigh_e = empty("tr_sleigh", (0, 0, 0.5), parent=troika_e)
# Body curved
for si in range(6):
    sw_s = 1.5 - abs(si - 3) * 0.10
    sz_s = si * 0.20
    beveled_cube(f"tr_sl{si}", (sw_s, 0.8, 0.30), bevel_offset=0.06, loc=(0, 0, sz_s),
                 parent=sleigh_e, mat_=M_SLEIGH_RED_R)
# Front curl
smooth_sphere("tr_front", r=0.4, segs=14, rings=10, loc=(0.8, 0, 0.40),
              parent=sleigh_e, mat_=M_SLEIGH_RED_R, scale=(1.5, 0.85, 1))
# High back
beveled_cube("tr_back", (0.30, 1.0, 1.5), bevel_offset=0.10, loc=(-0.8, 0, 1.0),
             parent=sleigh_e, mat_=M_SLEIGH_RED_R)
# Gold trim
beveled_cube("tr_trim", (2.0, 0.85, 0.05), bevel_offset=0.02, loc=(0, 0, 1.10),
             parent=sleigh_e, mat_=M_SLEIGH_GOLD_R)
# Runners
for side in (-1, 1):
    runner_e = empty(f"tr_run{side}_e", (0, side*0.45, 0), parent=sleigh_e)
    for ri in range(5):
        ra = (ri / 4.0) * math.pi * 0.5
        rx_r = 0.8 + math.cos(ra) * 0.4
        rz_r = math.sin(ra) * 0.4
        smooth_sphere(f"tr_r{side}_{ri}", r=0.08, loc=(rx_r, 0, rz_r),
                      parent=runner_e, mat_=M_BAL_STRING)
    cyl(f"tr_r{side}_s", r=0.08, depth=2.5, segs=10, loc=(-0.2, 0, 0),
        parent=runner_e, mat_=M_BAL_STRING).rotation_euler = (0, math.radians(90), 0)

# 3 HORSES (signature troika spread)
troika_horses = []
horse_pos_t = [(3, 0, 0), (3, -1.5, 0), (3, 1.5, 0)]
for hi, (hx, hy, hz) in enumerate(horse_pos_t):
    h_e = empty(f"tr_h{hi}", (hx, hy, hz), parent=troika_e)
    horse_col = HORSE_COLORS_R[hi % len(HORSE_COLORS_R)]
    # Body
    smooth_sphere(f"trh{hi}_b", r=0.55, segs=20, rings=14, loc=(0, 0, 1.2),
                  parent=h_e, mat_=horse_col, scale=(1.7, 1, 1))
    # 4 legs (running pose)
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"trh{hi}_l{x}_{y}", r=0.08, depth=1.2, segs=10,
                loc=(x*0.5, y*0.30, 0.6), parent=h_e, mat_=horse_col)
    # Neck
    neck_th = empty(f"trh{hi}_n", (0.95, 0, 1.5), parent=h_e)
    neck_th.rotation_euler = (0, math.radians(-30), 0)
    cyl(f"trh{hi}_nb", r=0.18, depth=0.7, segs=14, loc=(0, 0, 0.35),
        parent=neck_th, mat_=horse_col)
    # Head
    head_th = empty(f"trh{hi}_he", (0, 0, 0.75), parent=neck_th)
    smooth_sphere(f"trh{hi}_h", r=0.20, segs=16, rings=12, loc=(0.1, 0, 0),
                  parent=head_th, mat_=horse_col, scale=(1.5, 0.9, 1))
    # Mane signature
    for mi in range(5):
        smooth_sphere(f"trh{hi}_m{mi}", r=0.06,
                      loc=(0.1 - mi*0.05, 0, 0.20 + mi*0.04),
                      parent=neck_th, mat_=M_HORSE_MANE)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"trh{hi}_eye{side}", r=0.04, loc=(0.20, side*0.10, 0.05),
                      parent=head_th, mat_=M_EYE_DARK_R)
    # Bell harness (signature)
    cyl(f"trh{hi}_harn", r=0.20, depth=0.08, segs=14, loc=(0, 0, 0.30),
        parent=neck_th, mat_=M_HORSE_MANE)
    # 3 bells
    for bi in range(3):
        ba = (bi - 1) * 0.30
        smooth_sphere(f"trh{hi}_bell{bi}", r=0.05, loc=(ba, -0.15, 0.30),
                      parent=neck_th, mat_=M_SLEIGH_GOLD_R)
    # Tail
    cyl(f"trh{hi}_tail", r=0.05, depth=0.7, segs=10, loc=(-1.0, 0, 1.2),
        parent=h_e, mat_=M_HORSE_MANE).rotation_euler = (math.radians(60), 0, 0)
    # YOKE arch over middle horse signature (signature DUGA wooden bow)
    if hi == 0:
        for di in range(7):
            da = math.pi * di / 6.0
            dx_d = math.cos(da) * 1.2
            dz_d = math.sin(da) * 0.8 + 2.0
            smooth_sphere(f"tr_duga{di}", r=0.08, loc=(dx_d - 0.5, 0, dz_d),
                          parent=h_e, mat_=M_SLEIGH_WOOD)
        # Bell hanging from yoke (signature)
        smooth_sphere("tr_yoke_bell", r=0.15, loc=(-0.4, 0, 2.5),
                      parent=h_e, mat_=M_SLEIGH_GOLD_R)
    troika_horses.append({"root": h_e})

# Harness reins
for hi in range(3):
    cyl(f"tr_rein{hi}", r=0.015, depth=2.5, segs=6,
        loc=(1.5, horse_pos_t[hi][1], 1.4),
        parent=troika_e, mat_=M_BAL_DARK).rotation_euler = (0, math.radians(90), 0)

# ============================================================
# ⭐ 600 SNOWFLAKES + 400 RED STARS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
snowflakes = []
for i in range(600):
    px = random.uniform(-70, 70)
    py = random.uniform(-70, 70)
    pz = random.uniform(1, 25)
    s = smooth_sphere(f"sf{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6,
                      loc=(px, py, pz), mat_=M_SNOWFLAKE)
    s["_phase"] = random.uniform(0, math.pi*2)
    s["_base_x"] = px; s["_base_y"] = py; s["_base_z"] = pz
    s["_amp_x"] = random.uniform(1.0, 2.5)
    s["_amp_y"] = random.uniform(1.0, 2.5)
    s["_speed"] = random.uniform(0.4, 1.0)
    s["_fall"] = random.uniform(1.5, 3.5)
    snowflakes.append(s)

# 400 red stars (signature)
red_stars = []
for i in range(400):
    px = random.uniform(-60, 60)
    py = random.uniform(-60, 60)
    pz = random.uniform(3, 25)
    s_e = empty(f"rs{i}", (px, py, pz))
    # 5-point star simplified
    smooth_sphere(f"rs_c{i}", r=0.08, segs=10, rings=8, loc=(0, 0, 0),
                  parent=s_e, mat_=M_RED_STAR)
    # 5 points
    for pi in range(5):
        pa = (pi / 5.0) * math.pi * 2 + math.pi/2
        smooth_cone(f"rs_p{i}_{pi}", r1=0.03, r2=0.005, depth=0.18, segs=6,
                    loc=(math.cos(pa)*0.10, math.sin(pa)*0.10, 0),
                    parent=s_e, mat_=M_RED_STAR).rotation_euler = (0, math.radians(90), pa)
    s_e["_phase"] = random.uniform(0, math.pi*2)
    s_e["_base_x"] = px; s_e["_base_y"] = py; s_e["_base_z"] = pz
    s_e["_amp_x"] = random.uniform(0.5, 1.5)
    s_e["_amp_y"] = random.uniform(0.5, 1.5)
    s_e["_speed"] = random.uniform(1.0, 3.0)
    red_stars.append(s_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Clouds drift slowly
for ci in range(25):
    cloud = bpy.data.objects.get(f"cloud{ci}")
    if cloud is None: continue
    phase = cloud["_phase"]
    bx_c = cloud.location.x; by_c = cloud.location.y
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        cloud.location.x = bx_c + math.sin(t * 0.3 + phase) * 2.0
        cloud.location.y = by_c + math.cos(t * 0.3 + phase) * 2.0
        cloud.keyframe_insert("location", frame=f)

# Soldiers parade march (goose step signature)
for s in soldiers:
    phase = s["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s["root"].location.z = abs(math.sin(t * 2.5 + phase)) * 0.05
        s["root"].keyframe_insert("location", frame=f)
        s["he"].rotation_euler = (0, 0, math.sin(t * 0.6 + phase) * math.radians(5))
        s["he"].keyframe_insert("rotation_euler", frame=f)

# Women browse + sway
for w in women_r:
    phase = w["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        w["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(3),
                                     math.cos(t * 1.0 + phase) * math.radians(3),
                                     w["root"].rotation_euler.z)
        w["root"].keyframe_insert("rotation_euler", frame=f)
        w["he"].rotation_euler = (0, 0, math.sin(t * 1.2 + phase) * math.radians(20))
        w["he"].keyframe_insert("rotation_euler", frame=f)

# Matryoshka rotates
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    matryoshka_e.rotation_euler = (0, 0, t * 0.5)
    matryoshka_e.keyframe_insert("rotation_euler", frame=f)

# Cossacks dance kazatchok (signature legs bent + bounce)
for c in cossacks:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        c["root"].location.z = abs(math.sin(t * 4.0 + phase)) * 0.30
        c["root"].rotation_euler = (math.sin(t * 4.0 + phase) * math.radians(8), 0,
                                     c["root"].rotation_euler.z)
        c["root"].keyframe_insert("location", frame=f)
        c["root"].keyframe_insert("rotation_euler", frame=f)
        c["he"].rotation_euler = (0, 0, math.sin(t * 3.0 + phase) * math.radians(15))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Musicians play
for mu in musicians_r:
    phase = mu["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        mu["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(4), 0,
                                       mu["root"].rotation_euler.z)
        mu["root"].keyframe_insert("rotation_euler", frame=f)
        sc_i = 1 + math.sin(t * 4.0 + phase) * 0.10
        mu["inst"].scale = (sc_i, 1, 1)
        mu["inst"].keyframe_insert("scale", frame=f)

# Troika gallop
phase_t = 0
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    troika_e.location.x = -25 + math.sin(t * 0.3) * 2
    troika_e.location.z = abs(math.sin(t * 5.0)) * 0.10
    troika_e.keyframe_insert("location", frame=f)
# Each horse leg bounce
for hi in range(3):
    horse_obj = troika_horses[hi]["root"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Bounce
        ph_h = hi * 0.5
        horse_obj.location.z = horse_pos_t[hi][2] + abs(math.sin(t * 6.0 + ph_h)) * 0.15
        horse_obj.keyframe_insert("location", frame=f)

# 600 snowflakes fall
for s in snowflakes:
    phase = s["_phase"]; speed = s["_speed"]; fall = s["_fall"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay = s["_amp_x"], s["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.5)
        if z < 0.5: z = bz
        s.location = (x, y, max(0.3, z))
        s.rotation_euler = (t * 2.0 + phase, t * 1.5 + phase, t * 2.5 + phase)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("rotation_euler", frame=f)

# 400 red stars twinkle + drift
for s in red_stars:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay = s["_amp_x"], s["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase) * 0.3
        y = by + ay * math.cos(t * speed * 0.9 + phase) * 0.3
        s.location = (x, y, bz)
        # Twinkle
        sc_s = 0.5 + abs(math.sin(t * speed + phase)) * 1.0
        s.scale = (sc_s, sc_s, sc_s)
        s.rotation_euler = (0, 0, t * 0.5 + phase)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)
        s.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_russia_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_russian_kremlin_red_square] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_russian_kremlin_red_square] St Basil's 9 colorful onion domes + 3-bar Orthodox crosses + Kremlin wall + 5 towers with RED STARS + 6 soldiers ushanka + 4 women fur coats + giant matryoshka + 4 Cossack dancers + 2 musicians + troika 3 horses + 600 snow + 400 red stars")
print("⭐ FIXES: 1 ground + 600 snowflakes + 400 red stars (signature Russia mandatory) ⭐")
