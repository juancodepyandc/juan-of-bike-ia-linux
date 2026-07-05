"""
proc_caribbean_pirate_island_treasure.py — 247e procédural AuroraIA (112e qualité)
Caribbean pirate island: galleon 3 masts + jolly roger + cannons + 6 pirates + captain + parrot + 8 palms + treasure chest + 2 mermaids + 6 crabs + 600 gold coins + 400 sea spray
FIXES : 1 ground + 600 coins falling + 400 sea spray (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB247)

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

# Tropical sky
M_SKY = mat("sky", (0.55, 0.78, 0.95, 1.0), 0.0, 0.7, emission=(0.55,0.78,0.95), emission_strength=1.8)
M_SUN = mat("sun", (1.0, 0.95, 0.65, 1.0), 0.0, 0.1, emission=(1.0,0.95,0.65), emission_strength=14.0)
M_CLOUD_FLUFF = mat("cloud", (0.95, 0.95, 0.95, 1.0), 0.0, 0.7, emission=(0.92,0.92,0.92), emission_strength=1.3)

# Sand
M_SAND_GOLDEN = mat("sand", (0.95, 0.82, 0.50, 1.0), 0.0, 0.65, emission=(0.88,0.78,0.50), emission_strength=0.5)
M_SAND_WET = mat("sand_w", (0.65, 0.55, 0.32, 1.0), 0.0, 0.55)
M_SAND_DARK = mat("sand_d", (0.65, 0.55, 0.30, 1.0), 0.0, 0.75)

# Ocean
M_OCEAN_TURQ = mat("ocean", (0.18, 0.72, 0.78, 1.0), 0.1, 0.20, emission=(0.18,0.70,0.75), emission_strength=1.8, alpha=0.78)
M_OCEAN_DEEP = mat("ocean_d", (0.10, 0.45, 0.62, 1.0), 0.1, 0.25, alpha=0.85)
M_FOAM = mat("foam", (0.95, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.90), emission_strength=1.8, alpha=0.65)

# Galleon wood
M_GALLEON_WOOD = mat("g_w", (0.42, 0.25, 0.12, 1.0), 0.0, 0.75, emission=(0.40,0.25,0.12), emission_strength=0.4)
M_GALLEON_DARK = mat("g_d", (0.28, 0.16, 0.08, 1.0), 0.0, 0.85)
M_GALLEON_TRIM = mat("g_t", (0.85, 0.65, 0.20, 1.0), 0.85, 0.25, emission=(0.80,0.62,0.20), emission_strength=1.2)
M_GALLEON_RED = mat("g_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.72,0.18,0.18), emission_strength=0.7)

# Sails BLACK signature
M_SAIL_BLACK = mat("sail_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.70, emission=(0.08,0.06,0.06), emission_strength=0.4)
M_SAIL_TORN = mat("sail_t", (0.18, 0.15, 0.12, 1.0), 0.0, 0.75)
M_ROPE_P = mat("rope_p", (0.55, 0.42, 0.20, 1.0), 0.0, 0.85)

# Jolly Roger (skull bones) signature
M_FLAG_BLACK = mat("fl_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.55)
M_BONE_WHITE_P = mat("bn_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.92,0.90,0.85), emission_strength=1.2)

# Cannon
M_CANNON = mat("cn", (0.32, 0.32, 0.32, 1.0), 0.8, 0.40, emission=(0.30,0.30,0.30), emission_strength=0.5)
M_CANNON_DARK = mat("cn_d", (0.18, 0.18, 0.18, 1.0), 0.85, 0.45)

# Pirate skin / clothes
M_SKIN_TAN_P = mat("skin", (0.85, 0.62, 0.42, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.42), emission_strength=0.4)
M_SKIN_DARK_P = mat("skin_d", (0.55, 0.32, 0.20, 1.0), 0.0, 0.55, emission=(0.52,0.32,0.20), emission_strength=0.4)
SKIN_VARIANTS_P = [M_SKIN_TAN_P, M_SKIN_DARK_P]

# Bandana colors signature
M_BANDANA_RED = mat("bd_r", (0.85, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.78,0.15,0.15), emission_strength=0.7)
M_BANDANA_BLUE = mat("bd_b", (0.20, 0.40, 0.78, 1.0), 0.0, 0.55, emission=(0.18,0.38,0.72), emission_strength=0.7)
M_BANDANA_GREEN = mat("bd_g", (0.20, 0.55, 0.30, 1.0), 0.0, 0.55, emission=(0.18,0.52,0.28), emission_strength=0.7)
M_BANDANA_BLACK = mat("bd_bk", (0.10, 0.10, 0.10, 1.0), 0.0, 0.65)
BANDANA_COLORS = [M_BANDANA_RED, M_BANDANA_BLUE, M_BANDANA_GREEN, M_BANDANA_BLACK]

# Shirt
M_SHIRT_WHITE_P = mat("sh_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.70, emission=(0.85,0.85,0.80), emission_strength=0.4)
M_SHIRT_STRIPED = mat("sh_s", (0.85, 0.85, 0.85, 1.0), 0.0, 0.65)
M_PANTS_BROWN = mat("pants_br", (0.32, 0.20, 0.10, 1.0), 0.0, 0.80)
M_PANTS_RED = mat("pants_r", (0.65, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.62,0.18,0.18), emission_strength=0.4)
M_BELT_LEATHER = mat("blt", (0.20, 0.12, 0.06, 1.0), 0.0, 0.85)
M_VEST_BROWN = mat("vest", (0.42, 0.25, 0.10, 1.0), 0.0, 0.75)

# Boots
M_BOOTS_PIRATE = mat("boots", (0.25, 0.15, 0.08, 1.0), 0.0, 0.75)

# Hair / beard
M_HAIR_BLACK_P = mat("h_bk", (0.10, 0.08, 0.06, 1.0), 0.0, 0.55)
M_HAIR_RED_P = mat("h_r", (0.65, 0.30, 0.10, 1.0), 0.0, 0.60)
M_HAIR_GREY_P = mat("h_g", (0.55, 0.50, 0.42, 1.0), 0.0, 0.65)
HAIR_VARIANTS_P = [M_HAIR_BLACK_P, M_HAIR_RED_P, M_HAIR_GREY_P]

# Tricorn hat captain
M_TRICORN = mat("tri", (0.15, 0.10, 0.08, 1.0), 0.0, 0.65, emission=(0.12,0.08,0.06), emission_strength=0.3)
M_TRICORN_TRIM = mat("tri_t", (0.95, 0.78, 0.25, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.25), emission_strength=1.0)

# Sword/cutlass
M_BLADE_STEEL_P = mat("blade", (0.85, 0.85, 0.88, 1.0), 0.92, 0.18, emission=(0.80,0.80,0.85), emission_strength=1.2)
M_HILT_GOLD = mat("hilt", (0.95, 0.78, 0.25, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.25), emission_strength=1.0)
M_HILT_WOOD = mat("h_w", (0.40, 0.25, 0.12, 1.0), 0.0, 0.75)

# Parrot signature
M_PARROT_RED = mat("p_r", (0.95, 0.18, 0.18, 1.0), 0.0, 0.45, emission=(0.92,0.18,0.18), emission_strength=1.5)
M_PARROT_YELLOW = mat("p_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.80,0.20), emission_strength=1.5)
M_PARROT_BLUE = mat("p_b", (0.18, 0.42, 0.85, 1.0), 0.0, 0.45, emission=(0.18,0.42,0.80), emission_strength=1.5)
M_PARROT_GREEN = mat("p_g", (0.20, 0.62, 0.30, 1.0), 0.0, 0.45, emission=(0.18,0.55,0.28), emission_strength=1.2)
M_PARROT_BEAK = mat("p_bk", (0.20, 0.18, 0.10, 1.0), 0.0, 0.55)
M_PARROT_EYE = mat("p_e", (1.0, 0.85, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.20), emission_strength=4.0)

# Palm tree
M_PALM_TRUNK = mat("palm_t", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85, emission=(0.50,0.30,0.15), emission_strength=0.3)
M_PALM_TRUNK_DARK = mat("palm_td", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)
M_PALM_LEAF = mat("palm_l", (0.30, 0.62, 0.25, 1.0), 0.0, 0.55, emission=(0.28,0.58,0.25), emission_strength=0.5)
M_PALM_LEAF_BR = mat("palm_lb", (0.35, 0.72, 0.30, 1.0), 0.0, 0.55, emission=(0.30,0.68,0.30), emission_strength=0.6)
M_COCONUT_P = mat("coco_p", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)

# Treasure chest
M_CHEST_WOOD = mat("ch_w", (0.42, 0.22, 0.10, 1.0), 0.0, 0.65, emission=(0.40,0.22,0.10), emission_strength=0.4)
M_CHEST_GOLD = mat("ch_g", (0.95, 0.78, 0.25, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.25), emission_strength=1.2)
M_CHEST_IRON = mat("ch_i", (0.32, 0.30, 0.28, 1.0), 0.85, 0.35)

# Gold (signature)
M_GOLD_SHINY = mat("gold", (1.0, 0.85, 0.25, 1.0), 0.95, 0.10, emission=(0.95,0.80,0.25), emission_strength=4.0)
M_GOLD_DEEP_P = mat("gold_d", (0.85, 0.65, 0.18, 1.0), 0.95, 0.15, emission=(0.80,0.60,0.18), emission_strength=3.0)
M_GEM_RED = mat("gem_r", (1.0, 0.18, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.18,0.20), emission_strength=6.0)
M_GEM_GREEN = mat("gem_g", (0.20, 1.0, 0.30, 1.0), 0.0, 0.10, emission=(0.20,1.0,0.30), emission_strength=6.0)
M_GEM_BLUE = mat("gem_b", (0.20, 0.45, 1.0, 1.0), 0.0, 0.10, emission=(0.20,0.45,1.0), emission_strength=6.0)
M_PEARL = mat("pearl", (0.92, 0.92, 0.95, 1.0), 0.3, 0.20, emission=(0.85,0.85,0.92), emission_strength=2.0)
GEM_VARIANTS = [M_GEM_RED, M_GEM_GREEN, M_GEM_BLUE, M_PEARL]

# Mermaid
M_MERMAID_SKIN = mat("mer_sk", (0.92, 0.75, 0.62, 1.0), 0.0, 0.45, emission=(0.88,0.72,0.62), emission_strength=0.5)
M_MERMAID_TAIL_GREEN = mat("mer_t_g", (0.20, 0.78, 0.55, 1.0), 0.4, 0.30, emission=(0.20,0.75,0.52), emission_strength=1.5)
M_MERMAID_TAIL_PURPLE = mat("mer_t_p", (0.65, 0.30, 0.85, 1.0), 0.4, 0.30, emission=(0.62,0.30,0.82), emission_strength=1.5)
M_MERMAID_HAIR_RED = mat("mer_h_r", (0.78, 0.30, 0.12, 1.0), 0.0, 0.55)
M_MERMAID_HAIR_BLOND = mat("mer_h_b", (0.92, 0.75, 0.32, 1.0), 0.0, 0.55, emission=(0.85,0.70,0.30), emission_strength=0.6)
M_MERMAID_BIKINI = mat("mer_bk", (0.95, 0.78, 0.30, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.30), emission_strength=2.0)

# Crab
M_CRAB_RED = mat("cr_r", (0.85, 0.20, 0.18, 1.0), 0.0, 0.55, emission=(0.80,0.20,0.18), emission_strength=0.6)
M_CRAB_LIGHT = mat("cr_l", (0.95, 0.62, 0.45, 1.0), 0.0, 0.55, emission=(0.90,0.58,0.42), emission_strength=0.6)

# Rocks
M_ROCK_GREY_P = mat("rock", (0.45, 0.45, 0.42, 1.0), 0.0, 0.85)

# Sea spray
M_SPRAY = mat("spray", (0.92, 0.95, 0.98, 1.0), 0.0, 0.30, emission=(0.88,0.92,0.95), emission_strength=2.5, alpha=0.45)

# Eye
M_EYE_BLACK_P = mat("eye_bk", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_PATCH = mat("eye_p", (0.10, 0.08, 0.08, 1.0), 0.0, 0.65)

# ============ SKY ============
sky = smooth_sphere("sky", r=260, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Sun
sun_t = smooth_sphere("sun", r=5, segs=24, rings=18, loc=(30, 80, 75), mat_=M_SUN)
# Clouds
for ci in range(15):
    cax = random.uniform(-80, 80); cay = random.uniform(-80, 80)
    caz = random.uniform(30, 55)
    cloud_e = empty(f"cloud{ci}", (cax, cay, caz))
    for cli in range(random.randint(3, 5)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(2, 4), segs=16, rings=10,
                      loc=(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD_FLUFF, scale=(1.4, 1.2, 0.7))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)

# ============ ONE clean golden sand ground ============
ground = beveled_cube("ground", (180, 180, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_SAND_GOLDEN)
# Sand dunes
for i in range(150):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 65)
    smooth_sphere(f"dune{i}", r=random.uniform(0.4, 0.9), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_SAND_DARK if i % 3 == 0 else M_SAND_GOLDEN,
                  scale=(1.5, 1.4, 0.22))

# ============ OCEAN BAY (signature turquoise) ============
# Large ocean area to one side
ocean_e = empty("ocean", loc=(30, 0, 0))
ocean_main = beveled_cube("ocean_main", (50, 100, 0.20), bevel_offset=0.06, loc=(0, 0, 0.20),
                          parent=ocean_e, mat_=M_OCEAN_TURQ)
ocean_deep = beveled_cube("ocean_d", (45, 95, 0.15), bevel_offset=0.04, loc=(0, 0, 0.25),
                          parent=ocean_e, mat_=M_OCEAN_DEEP)
# Foam waves at shore
for fi in range(30):
    fy_f = -45 + fi * 3
    cyl(f"foam{fi}", r=random.uniform(0.5, 1.2), depth=0.10, segs=14,
        loc=(random.uniform(2, 10), fy_f, 0.30),
        parent=ocean_e, mat_=M_FOAM)
# Surface ripples
for ri in range(40):
    rx_r = random.uniform(-20, 22); ry_r = random.uniform(-45, 45)
    cyl(f"ripple{ri}", r=random.uniform(0.30, 0.60), depth=0.04, segs=14,
        loc=(rx_r, ry_r, 0.30), parent=ocean_e, mat_=M_FOAM)

# ============ PIRATE GALLEON (signature 3-mast warship) ============
galleon_e = empty("galleon", loc=(28, 0, 2.0))
# HULL (signature large)
# Main hull body
hull = smooth_cone("g_hull", r1=4, r2=1, depth=18, segs=22, loc=(0, 0, 0),
                   parent=galleon_e, mat_=M_GALLEON_WOOD)
hull.rotation_euler = (math.radians(90), 0, 0)
# Hull belt
beveled_cube("g_hull_b", (4.5, 18, 0.6), bevel_offset=0.10, loc=(0, 0, 0.5),
             parent=galleon_e, mat_=M_GALLEON_DARK)
# Plank lines
for pi in range(10):
    pz = -2 + pi * 0.4
    pl_w = 4.5 - abs(pi - 5) * 0.15
    beveled_cube(f"g_pl{pi}", (pl_w, 18.5, 0.10), bevel_offset=0.02,
                 loc=(0, 0, pz), parent=galleon_e,
                 mat_=M_GALLEON_WOOD if pi % 2 == 0 else M_GALLEON_DARK)
# Top deck
beveled_cube("g_deck", (4, 16, 0.30), bevel_offset=0.06, loc=(0, 0, 2.0),
             parent=galleon_e, mat_=M_GALLEON_WOOD)
# Side railings
for side in (-1, 1):
    beveled_cube(f"g_rail_top{side}", (0.30, 16, 0.50), bevel_offset=0.04,
                 loc=(side*2.0, 0, 2.4), parent=galleon_e, mat_=M_GALLEON_DARK)
    # Posts
    for pi in range(15):
        py = -7 + pi * 1.0
        cyl(f"g_post{side}_{pi}", r=0.06, depth=0.45, segs=8,
            loc=(side*2.05, py, 2.4), parent=galleon_e, mat_=M_GALLEON_WOOD)
# Gold trim
for side in (-1, 1):
    beveled_cube(f"g_trim{side}", (0.10, 16, 0.20), bevel_offset=0.03,
                 loc=(side*2.10, 0, 1.8), parent=galleon_e, mat_=M_GALLEON_TRIM)
# Stern (signature high captain quarter)
beveled_cube("g_stern", (4.5, 4, 3), bevel_offset=0.10, loc=(0, -7, 3.5),
             parent=galleon_e, mat_=M_GALLEON_WOOD)
# Stern windows (signature ornate)
for wi in range(3):
    wx_w = -1.5 + wi * 1.5
    beveled_cube(f"g_sw{wi}", (1.0, 0.10, 1.0), bevel_offset=0.06,
                 loc=(wx_w, -9, 3.5), parent=galleon_e, mat_=M_GALLEON_TRIM)
    # Window cross detail
    beveled_cube(f"g_swc{wi}_v", (0.06, 0.12, 1.05), bevel_offset=0.01,
                 loc=(wx_w, -9.05, 3.5), parent=galleon_e, mat_=M_GALLEON_DARK)
    beveled_cube(f"g_swc{wi}_h", (1.05, 0.12, 0.06), bevel_offset=0.01,
                 loc=(wx_w, -9.05, 3.5), parent=galleon_e, mat_=M_GALLEON_DARK)
# Stern decorations
for di in range(4):
    dz = 5 + di * 0.5
    cyl(f"g_sd{di}", r=2.2 - di*0.15, depth=0.10, segs=20,
        loc=(0, -8.5, dz), parent=galleon_e, mat_=M_GALLEON_TRIM)
# Bow figurehead (signature)
beveled_cube("g_bow", (3, 4, 1.5), bevel_offset=0.10, loc=(0, 8, 2.5),
             parent=galleon_e, mat_=M_GALLEON_WOOD)
# Bowsprit
cyl("g_bowsprit", r=0.15, depth=4, segs=10, loc=(0, 10.5, 3.0),
    parent=galleon_e, mat_=M_GALLEON_DARK).rotation_euler = (math.radians(15), 0, 0)
# Mermaid figurehead on bow (signature)
fig_e = empty("fig", (0, 10.5, 1.5), parent=galleon_e)
# Body curve
smooth_sphere("fig_body", r=0.40, segs=18, rings=12, loc=(0, 0.2, 0.4),
              parent=fig_e, mat_=M_GALLEON_TRIM, scale=(1, 1.5, 0.8))
# Head
smooth_sphere("fig_head", r=0.20, segs=18, rings=14, loc=(0, 0.4, 0.85),
              parent=fig_e, mat_=M_GALLEON_TRIM)
# Tail behind
smooth_cone("fig_tail", r1=0.30, r2=0.05, depth=1.5, segs=14, loc=(0, -0.5, 0.4),
            parent=fig_e, mat_=M_GALLEON_TRIM).rotation_euler = (math.radians(90), 0, 0)

# 3 MASTS (signature)
mast_positions = [(0, 5.5, 2.0, 14, "fore"), (0, 0, 2.0, 18, "main"), (0, -4, 2.0, 13, "mizzen")]
sails_all = []
for mi, (mx, my, mz, mh, mname) in enumerate(mast_positions):
    mast_e = empty(f"mast_{mname}", (mx, my, mz), parent=galleon_e)
    # Mast pole
    cyl(f"mp_{mname}", r=0.18, depth=mh, segs=12, loc=(0, 0, mh/2),
        parent=mast_e, mat_=M_GALLEON_DARK)
    # Yard arms 2 levels
    for ya in range(2):
        ya_z = mh * 0.35 + ya * mh * 0.4
        ya_w = mh * 0.5 - ya * 0.8
        cyl(f"yard_{mname}_{ya}", r=0.10, depth=ya_w, segs=10, loc=(0, 0, ya_z),
            parent=mast_e, mat_=M_GALLEON_DARK).rotation_euler = (0, math.radians(90), 0)
        # BLACK SAIL (signature)
        sail = beveled_cube(f"sail_{mname}_{ya}", (ya_w*0.95, 0.10, mh*0.32), bevel_offset=0.05,
                            loc=(0, 0, ya_z - mh*0.16), parent=mast_e, mat_=M_SAIL_BLACK)
        sail["_phase"] = random.uniform(0, math.pi*2)
        sails_all.append(sail)
        # Ropes from yard
        for side in (-1, 1):
            cyl(f"sr_{mname}_{ya}_{side}", r=0.015, depth=mh*0.36, segs=6,
                loc=(side*ya_w*0.48, 0, ya_z - mh*0.18),
                parent=mast_e, mat_=M_ROPE_P)
    # Top crow's nest
    cyl(f"nest_{mname}", r=0.35, depth=0.4, segs=14, loc=(0, 0, mh - 0.3),
        parent=mast_e, mat_=M_GALLEON_WOOD)
    cyl(f"nest_rim_{mname}", r=0.40, depth=0.10, segs=14, loc=(0, 0, mh - 0.1),
        parent=mast_e, mat_=M_GALLEON_DARK)
# JOLLY ROGER flag on main mast (signature skull + crossbones)
flag_e = empty("flag", (0, 0, 17), parent=galleon_e)
beveled_cube("fl_bg", (1.8, 0.05, 1.2), bevel_offset=0.04, loc=(0.9, 0, 0), parent=flag_e, mat_=M_FLAG_BLACK)
# Skull
smooth_sphere("fl_skull", r=0.18, segs=18, rings=14, loc=(0.7, -0.06, 0.15),
              parent=flag_e, mat_=M_BONE_WHITE_P)
# Skull jaw
smooth_sphere("fl_jaw", r=0.15, loc=(0.7, -0.06, -0.05),
              parent=flag_e, mat_=M_BONE_WHITE_P, scale=(1.1, 0.7, 0.5))
# Eye sockets (signature dark)
for side in (-1, 1):
    smooth_sphere(f"fl_es{side}", r=0.05,
                  loc=(0.7 + side*0.06, -0.10, 0.18), parent=flag_e, mat_=M_FLAG_BLACK)
# Teeth
for ti in range(5):
    beveled_cube(f"fl_t{ti}", (0.025, 0.02, 0.05), bevel_offset=0.005,
                 loc=(0.7 + (ti-2)*0.03, -0.10, 0.02), parent=flag_e, mat_=M_BONE_WHITE_P)
# Crossbones (signature X)
for diag in (0, 1):
    diag_e = empty(f"fl_d{diag}_e", (1.1, -0.06, -0.20), parent=flag_e)
    diag_e.rotation_euler = (0, math.radians(35 if diag == 0 else -35), 0)
    beveled_cube(f"fl_d{diag}", (0.7, 0.04, 0.06), bevel_offset=0.02,
                 loc=(0, 0, 0), parent=diag_e, mat_=M_BONE_WHITE_P)
    # Bone ends
    smooth_sphere(f"fl_d{diag}_e1", r=0.06, loc=(0.35, 0, 0), parent=diag_e, mat_=M_BONE_WHITE_P)
    smooth_sphere(f"fl_d{diag}_e2", r=0.06, loc=(-0.35, 0, 0), parent=diag_e, mat_=M_BONE_WHITE_P)

# 8 CANNONS on side (signature)
cannons = []
for ci in range(8):
    side_c = 1 if ci % 2 == 0 else -1
    cy_pos = -5 + (ci // 2) * 3
    c_e = empty(f"cannon{ci}", (side_c*2.0, cy_pos, 1.3), parent=galleon_e)
    c_e.rotation_euler = (0, 0, math.radians(side_c * 90))
    # Carriage
    beveled_cube(f"c_carr{ci}", (1.0, 0.4, 0.30), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=c_e, mat_=M_GALLEON_WOOD)
    # Wheels
    for side_w in (-1, 1):
        for fb in (-1, 1):
            cyl(f"c_w{ci}_{side_w}_{fb}", r=0.10, depth=0.06, segs=12,
                loc=(fb*0.35, side_w*0.20, -0.15),
                parent=c_e, mat_=M_GALLEON_DARK).rotation_euler = (math.radians(90), 0, 0)
    # Barrel
    smooth_cone(f"c_bar{ci}", r1=0.15, r2=0.10, depth=1.0, segs=14,
                loc=(0.5, 0, 0.18), parent=c_e, mat_=M_CANNON).rotation_euler = (0, math.radians(90), 0)
    # Rings on barrel
    for ri in range(3):
        cyl(f"c_ring{ci}_{ri}", r=0.12, depth=0.04, segs=14,
            loc=(0.2 + ri*0.25, 0, 0.18), parent=c_e, mat_=M_CANNON_DARK).rotation_euler = (0, math.radians(90), 0)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    cannons.append(c_e)

# ============ 6 PIRATES on deck ============
def make_pirate(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    skin = random.choice(SKIN_VARIANTS_P)
    bandana_col = random.choice(BANDANA_COLORS)
    hair = random.choice(HAIR_VARIANTS_P)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.11*scale, depth=0.85*scale, segs=10,
            loc=(side*0.13*scale, 0, 0.42*scale), parent=base, mat_=random.choice([M_PANTS_BROWN, M_PANTS_RED]))
        # Boot
        beveled_cube(f"{name}_boot{side}", (0.11*scale, 0.22*scale, 0.10*scale), bevel_offset=0.02,
                     loc=(side*0.13*scale, 0, 0), parent=base, mat_=M_BOOTS_PIRATE)
    # Belt
    cyl(f"{name}_belt", r=0.27*scale, depth=0.10*scale, segs=14, loc=(0, 0, 0.95*scale),
        parent=base, mat_=M_BELT_LEATHER)
    # Belt buckle
    beveled_cube(f"{name}_buckle", (0.10*scale, 0.04*scale, 0.10*scale), bevel_offset=0.02,
                 loc=(0, -0.28*scale, 0.95*scale), parent=base, mat_=M_GALLEON_TRIM)
    # Shirt (white or striped)
    shirt_mat = random.choice([M_SHIRT_WHITE_P, M_SHIRT_STRIPED])
    smooth_cone(f"{name}_shirt", r1=0.28*scale, r2=0.30*scale, depth=0.55*scale, segs=14,
                loc=(0, 0, 1.30*scale), parent=base, mat_=shirt_mat)
    # Stripes on shirt
    if shirt_mat == M_SHIRT_STRIPED:
        for si in range(4):
            cyl(f"{name}_str{si}", r=0.30*scale, depth=0.06*scale, segs=14,
                loc=(0, 0, 1.10*scale + si*0.20*scale), parent=base, mat_=bandana_col)
    # Vest open
    if random.random() > 0.4:
        for side in (-1, 1):
            beveled_cube(f"{name}_v{side}", (0.15*scale, 0.10*scale, 0.55*scale), bevel_offset=0.03,
                         loc=(side*0.20*scale, -0.10*scale, 1.30*scale),
                         parent=base, mat_=M_VEST_BROWN)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.65*scale), parent=base)
        sh.rotation_euler = (math.radians(-50 + side*10), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side_idx}", r=0.06*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=shirt_mat)
        # Forearm exposed skin
        cyl(f"{name}_fa{side_idx}", r=0.05*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=skin)
        # Hand
        smooth_sphere(f"{name}_hand{side_idx}", r=0.06*scale, loc=(0, 0, -0.75*scale),
                      parent=sh, mat_=skin)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=skin)
    # Beard (most pirates have one)
    if random.random() > 0.3:
        for bi in range(8):
            ba = (bi / 8.0) * math.pi - math.pi/2
            smooth_sphere(f"{name}_bd{bi}", r=0.04*scale,
                          loc=(math.sin(ba)*0.12*scale, -0.15*scale, -0.12*scale),
                          parent=head_e, mat_=hair)
    # Eye + eye patch (signature)
    has_patch = random.random() > 0.6
    if has_patch:
        # Eye patch
        beveled_cube(f"{name}_patch", (0.10*scale, 0.04*scale, 0.08*scale), bevel_offset=0.02,
                     loc=(-0.07*scale, -0.16*scale, 0.04*scale), parent=head_e, mat_=M_EYE_PATCH)
        # Strap diagonal
        beveled_cube(f"{name}_patch_str", (0.40*scale, 0.04*scale, 0.02*scale), bevel_offset=0.005,
                     loc=(0, -0.10*scale, 0.06*scale), parent=head_e, mat_=M_EYE_PATCH).rotation_euler = (0, 0, math.radians(20))
        # Right eye only
        smooth_sphere(f"{name}_eyeR", r=0.025*scale,
                      loc=(0.07*scale, -0.15*scale, 0.03*scale), parent=head_e, mat_=M_EYE_BLACK_P)
    else:
        for side in (-1, 1):
            smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                          loc=(side*0.06*scale, -0.15*scale, 0.03*scale), parent=head_e, mat_=M_EYE_BLACK_P)
    # Hair
    for hi in range(6):
        ha = (hi / 6.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.05*scale,
                      loc=(math.cos(ha)*0.15*scale, math.sin(ha)*0.08*scale, 0.08*scale),
                      parent=head_e, mat_=hair)
    # BANDANA (signature)
    bandana_e = empty(f"{name}_band", (0, 0, 0.15*scale), parent=head_e)
    cyl(f"{name}_band_b", r=0.20*scale, depth=0.08*scale, segs=14, loc=(0, 0, 0),
        parent=bandana_e, mat_=bandana_col)
    # Knot at back
    smooth_sphere(f"{name}_knot", r=0.05*scale, loc=(0, 0.20*scale, 0),
                  parent=bandana_e, mat_=bandana_col)
    # Knot tail
    beveled_cube(f"{name}_kt", (0.04*scale, 0.06*scale, 0.15*scale), bevel_offset=0.01,
                 loc=(0, 0.25*scale, -0.08*scale), parent=bandana_e, mat_=bandana_col)
    # CUTLASS at side
    sword_e = empty(f"{name}_sw_e", (0.30*scale, 0, 0.85*scale), parent=base)
    sword_e.rotation_euler = (math.radians(-15), 0, math.radians(70))
    beveled_cube(f"{name}_sw_b", (0.03*scale, 0.06*scale, 0.55*scale), bevel_offset=0.005,
                 loc=(0, 0, 0.30*scale), parent=sword_e, mat_=M_BLADE_STEEL_P)
    smooth_cone(f"{name}_sw_p", r1=0.025*scale, r2=0.003*scale, depth=0.10*scale, segs=8,
                loc=(0, 0, 0.62*scale), parent=sword_e, mat_=M_BLADE_STEEL_P)
    cyl(f"{name}_sw_cg", r=0.02*scale, depth=0.15*scale, segs=8, loc=(0, 0, 0.04*scale),
        parent=sword_e, mat_=M_HILT_GOLD).rotation_euler = (0, math.radians(90), 0)
    cyl(f"{name}_sw_gr", r=0.018*scale, depth=0.12*scale, segs=8, loc=(0, 0, -0.05*scale),
        parent=sword_e, mat_=M_HILT_WOOD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

pirates = []
pirate_pos = [(-1.5, 4, math.radians(0)), (1.5, 4, math.radians(0)),
              (-1.5, 1, math.radians(180)), (1.5, 1, math.radians(180)),
              (-1.5, -2, math.radians(0)), (1.5, -2, math.radians(180))]
for i, (pxx, pyy, pfac) in enumerate(pirate_pos):
    p = make_pirate(f"pirate{i}", (28 + pxx, pyy, 2.3), scale=1.0, facing=pfac)
    pirates.append(p)

# ============ CAPTAIN (tricorn hat + parrot + sword raised) ============
captain_p_e = empty("captain_p", loc=(28, -5, 2.3))
captain_p_e.rotation_euler = (0, 0, math.radians(0))
# Pants
for side in (-1, 1):
    cyl(f"capP_leg{side}", r=0.11, depth=0.85, segs=10,
        loc=(side*0.13, 0, 0.42), parent=captain_p_e, mat_=M_PANTS_BROWN)
    beveled_cube(f"capP_boot{side}", (0.12, 0.25, 0.12), bevel_offset=0.02,
                 loc=(side*0.13, 0, 0), parent=captain_p_e, mat_=M_BOOTS_PIRATE)
# Belt
cyl("capP_belt", r=0.28, depth=0.10, segs=14, loc=(0, 0, 0.95), parent=captain_p_e, mat_=M_BELT_LEATHER)
# Long coat (signature)
smooth_cone("capP_coat", r1=0.32, r2=0.34, depth=0.80, segs=14, loc=(0, 0, 1.25),
            parent=captain_p_e, mat_=M_GALLEON_RED)
# Gold buttons row
for bi in range(5):
    smooth_sphere(f"capP_bt{bi}", r=0.025, loc=(0, -0.34, 1.05 + bi*0.15),
                  parent=captain_p_e, mat_=M_GALLEON_TRIM)
# Coat trim
beveled_cube("capP_trim", (0.10, 0.10, 0.85), bevel_offset=0.01, loc=(-0.25, -0.32, 1.25),
             parent=captain_p_e, mat_=M_GALLEON_TRIM)
# Shirt frill at collar
for fi in range(3):
    smooth_sphere(f"capP_frill{fi}", r=0.07,
                  loc=((fi-1)*0.06, -0.30, 1.65), parent=captain_p_e, mat_=M_SHIRT_WHITE_P)
# Arms
# Right arm raised with sword
sword_arm_e = empty("capP_swa", (0.30, -0.10, 1.65), parent=captain_p_e)
sword_arm_e.rotation_euler = (math.radians(-130), 0, math.radians(-30))
cyl("capP_uarm_R", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20), parent=sword_arm_e, mat_=M_GALLEON_RED)
cyl("capP_fa_R", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55), parent=sword_arm_e, mat_=M_SKIN_TAN_P)
# CUTLASS HUGE (signature captain)
sword_main_e = empty("capP_sword_e", (0, 0, -0.85), parent=sword_arm_e)
beveled_cube("capP_sw_b", (0.05, 0.10, 1.2), bevel_offset=0.005, loc=(0, 0, -0.60),
             parent=sword_main_e, mat_=M_BLADE_STEEL_P)
smooth_cone("capP_sw_p", r1=0.05, r2=0.005, depth=0.20, segs=8, loc=(0, 0, -1.25),
            parent=sword_main_e, mat_=M_BLADE_STEEL_P)
cyl("capP_sw_cg", r=0.03, depth=0.30, segs=10, loc=(0, 0, 0.05),
    parent=sword_main_e, mat_=M_HILT_GOLD).rotation_euler = (0, math.radians(90), 0)
# Hand guard ornate
smooth_sphere("capP_sw_guard", r=0.10, loc=(0, 0, 0.05),
              parent=sword_main_e, mat_=M_HILT_GOLD, scale=(0.7, 1.5, 1.0))
cyl("capP_sw_gr", r=0.025, depth=0.18, segs=8, loc=(0, 0, 0.15), parent=sword_main_e, mat_=M_HILT_WOOD)
smooth_sphere("capP_sw_pommel", r=0.04, loc=(0, 0, 0.25), parent=sword_main_e, mat_=M_HILT_GOLD)

# Left arm gesturing
left_arm_e = empty("capP_la", (-0.30, 0, 1.65), parent=captain_p_e)
left_arm_e.rotation_euler = (math.radians(-60), 0, math.radians(25))
cyl("capP_uarm_L", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20), parent=left_arm_e, mat_=M_GALLEON_RED)
cyl("capP_fa_L", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55), parent=left_arm_e, mat_=M_SKIN_TAN_P)

# Head
capP_head_e = empty("capP_he", (0, 0, 2.0), parent=captain_p_e)
smooth_sphere("capP_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
              parent=capP_head_e, mat_=M_SKIN_TAN_P)
# Long black beard (signature)
for bi in range(12):
    ba = (bi / 12.0) * math.pi - math.pi/2
    smooth_sphere(f"capP_bd{bi}", r=0.05,
                  loc=(math.sin(ba)*0.14, -0.16, -0.12 - (bi%3)*0.05),
                  parent=capP_head_e, mat_=M_HAIR_BLACK_P)
# Moustache
for side in (-1, 1):
    beveled_cube(f"capP_mou{side}", (0.10, 0.05, 0.04), bevel_offset=0.01,
                 loc=(side*0.05, -0.18, -0.06), parent=capP_head_e, mat_=M_HAIR_BLACK_P)
# Eyes piercing
for side in (-1, 1):
    smooth_sphere(f"capP_eye{side}", r=0.025,
                  loc=(side*0.06, -0.15, 0.03), parent=capP_head_e, mat_=M_EYE_BLACK_P)
# Hair flowing
for hi in range(10):
    ha = random.uniform(0, math.pi*2)
    hl_h = random.uniform(0.10, 0.20)
    smooth_sphere(f"capP_hr{hi}", r=0.04,
                  loc=(math.cos(ha)*0.15, 0.10 + math.sin(ha)*0.05, 0.08 - hi*0.02),
                  parent=capP_head_e, mat_=M_HAIR_BLACK_P)
# TRICORN HAT (signature)
tricorn_e = empty("capP_tri", (0, 0, 0.20), parent=capP_head_e)
# Hat brim 3-pointed (signature)
for corner in range(3):
    ca = (corner / 3.0) * math.pi * 2
    beveled_cube(f"capP_tri_brim{corner}", (0.40, 0.40, 0.06), bevel_offset=0.04,
                 loc=(math.cos(ca)*0.20, math.sin(ca)*0.20, 0), parent=tricorn_e, mat_=M_TRICORN)
# Center crown
smooth_sphere("capP_tri_crown", r=0.25, loc=(0, 0, 0.05),
              parent=tricorn_e, mat_=M_TRICORN, scale=(1, 1, 0.4))
# Gold trim
cyl("capP_tri_trim", r=0.30, depth=0.04, segs=18, loc=(0, 0, 0.02),
    parent=tricorn_e, mat_=M_TRICORN_TRIM)
# Plume feather
smooth_cone("capP_plume", r1=0.06, r2=0.005, depth=0.40, segs=10,
            loc=(0.20, -0.10, 0.20), parent=tricorn_e,
            mat_=M_PARROT_RED).rotation_euler = (math.radians(20), 0, math.radians(30))

# PARROT on shoulder (signature)
parrot_e = empty("parrot", (-0.30, 0, 1.80), parent=captain_p_e)
# Body
smooth_sphere("p_body", r=0.18, segs=16, rings=12, loc=(0, 0, 0),
              parent=parrot_e, mat_=M_PARROT_RED, scale=(1, 1.5, 1.1))
# Yellow chest
smooth_sphere("p_chest", r=0.14, loc=(0, -0.08, -0.02),
              parent=parrot_e, mat_=M_PARROT_YELLOW, scale=(1, 0.5, 0.9))
# Head
parrot_head_e = empty("p_he", (0, 0.15, 0.18), parent=parrot_e)
smooth_sphere("p_head", r=0.13, segs=16, rings=12, loc=(0, 0, 0),
              parent=parrot_head_e, mat_=M_PARROT_RED)
# Blue cheek
smooth_sphere("p_cheek", r=0.08, loc=(0, -0.10, 0),
              parent=parrot_head_e, mat_=M_PARROT_BLUE, scale=(1, 0.7, 1))
# BEAK (signature curved)
smooth_cone("p_beak", r1=0.06, r2=0.01, depth=0.15, segs=10,
            loc=(0, -0.15, -0.05), parent=parrot_head_e,
            mat_=M_PARROT_BEAK).rotation_euler = (math.radians(-110), 0, 0)
# Beak curl
smooth_cone("p_beak_hook", r1=0.025, r2=0.005, depth=0.07, segs=8,
            loc=(0, -0.20, -0.10), parent=parrot_head_e,
            mat_=M_PARROT_BEAK).rotation_euler = (math.radians(-160), 0, 0)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"p_eye{side}", r=0.025, loc=(side*0.08, -0.05, 0.04),
                  parent=parrot_head_e, mat_=M_PARROT_EYE)
# Wings
for side in (-1, 1):
    wing = beveled_cube(f"p_w{side}", (0.05, 0.20, 0.12), bevel_offset=0.02,
                        loc=(side*0.15, 0, 0), parent=parrot_e, mat_=M_PARROT_BLUE)
# Tail feathers
for tf in range(5):
    ta = (tf - 2) * 0.10
    beveled_cube(f"p_tf{tf}", (0.04, 0.04, 0.30), bevel_offset=0.01,
                 loc=(ta*0.5, -0.25, -0.05), parent=parrot_e,
                 mat_=[M_PARROT_RED, M_PARROT_YELLOW, M_PARROT_BLUE, M_PARROT_GREEN, M_PARROT_RED][tf])
# Feet
for side in (-1, 1):
    cyl(f"p_ft{side}", r=0.015, depth=0.08, segs=6, loc=(side*0.05, 0, -0.20),
        parent=parrot_e, mat_=M_PARROT_BEAK)

# ============ 8 PALM TREES on island ============
def make_palm(name, loc, scale=1.0, lean=0):
    base = empty(name, loc)
    base.rotation_euler = (0, math.radians(lean), 0)
    # Curved trunk segments
    for ti in range(12):
        tz = ti * 0.5
        tilt = math.sin(ti * 0.3) * 0.10
        cyl(f"{name}_t{ti}", r=0.18 - ti*0.005, depth=0.50, segs=10,
            loc=(tilt, 0, tz + 0.25), parent=base,
            mat_=M_PALM_TRUNK if ti % 2 == 0 else M_PALM_TRUNK_DARK)
    # Trunk rings
    for ri in range(8):
        rz = 0.5 + ri * 0.75
        cyl(f"{name}_r{ri}", r=0.20, depth=0.04, segs=10, loc=(0, 0, rz),
            parent=base, mat_=M_PALM_TRUNK_DARK)
    # CROWN of leaves (signature)
    crown_e = empty(f"{name}_cr", (0, 0, 6.5*scale), parent=base)
    for li in range(8):
        la = (li / 8.0) * math.pi * 2
        leaf_e = empty(f"{name}_l{li}_e", (0, 0, 0), parent=crown_e)
        leaf_e.rotation_euler = (math.radians(60), 0, la)
        # Leaf rachis
        cyl(f"{name}_lr{li}", r=0.03, depth=2.5, segs=8, loc=(0, 0, 1.25),
            parent=leaf_e, mat_=M_PALM_TRUNK_DARK)
        # Pinnae (segments)
        for sl in range(8):
            sl_z = sl * 0.30 + 0.40
            for ps in (-1, 1):
                beveled_cube(f"{name}_pn{li}_{sl}_{ps}", (0.03, 0.5, 0.04), bevel_offset=0.01,
                             loc=(ps*0.25, 0, sl_z), parent=leaf_e, mat_=M_PALM_LEAF if sl % 2 == 0 else M_PALM_LEAF_BR)
    # Coconuts (signature)
    for ci in range(5):
        ca = (ci / 5.0) * math.pi * 2
        smooth_sphere(f"{name}_coco{ci}", r=0.18,
                      loc=(math.cos(ca)*0.25, math.sin(ca)*0.25, 6.3),
                      parent=base, mat_=M_COCONUT_P)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "crown": crown_e}

palms = []
palm_pos = [(-20, -25, math.radians(5)), (-15, -32, math.radians(-8)),
             (-25, -15, math.radians(10)), (-10, -28, math.radians(-5)),
             (-30, -22, math.radians(3)), (-20, -38, math.radians(7)),
             (-12, -18, math.radians(-10)), (-18, -10, math.radians(5))]
for i, (px, py, lean) in enumerate(palm_pos):
    p = make_palm(f"palm{i}", (px, py, 0), scale=1.0, lean=lean*5)
    palms.append(p)

# ============ TREASURE CHEST (signature open with gold) ============
chest_e = empty("chest", loc=(-18, -22, 0))
# Chest base
beveled_cube("ch_base", (1.5, 1.0, 0.7), bevel_offset=0.06, loc=(0, 0, 0.35),
             parent=chest_e, mat_=M_CHEST_WOOD)
# Curved lid (signature open back)
lid_e = empty("ch_lid", (0, 0.5, 0.7), parent=chest_e)
lid_e.rotation_euler = (math.radians(-70), 0, 0)
beveled_cube("ch_lid_b", (1.5, 1.0, 0.4), bevel_offset=0.06, loc=(0, 0, 0.2),
             parent=lid_e, mat_=M_CHEST_WOOD)
# Iron bands
for ix in (-1, 0, 1):
    beveled_cube(f"ch_band{ix}", (0.10, 1.05, 0.75), bevel_offset=0.02,
                 loc=(ix*0.6, 0, 0.35), parent=chest_e, mat_=M_CHEST_IRON)
# Lock
beveled_cube("ch_lock", (0.20, 0.10, 0.25), bevel_offset=0.04, loc=(0, -0.50, 0.45),
             parent=chest_e, mat_=M_CHEST_GOLD)
# Keyhole
smooth_sphere("ch_kh", r=0.04, loc=(0, -0.56, 0.45), parent=chest_e, mat_=M_FLAG_BLACK)

# GOLD PILE inside (signature)
for gi in range(40):
    gx = random.uniform(-0.55, 0.55)
    gy = random.uniform(-0.35, 0.35)
    gz = random.uniform(0.65, 1.0)
    coin = cyl(f"chc{gi}", r=random.uniform(0.06, 0.10), depth=0.04, segs=12,
               loc=(gx, gy, gz), parent=chest_e, mat_=M_GOLD_SHINY)
    coin.rotation_euler = (random.uniform(0, math.pi), random.uniform(0, math.pi), 0)
# Necklaces overflowing
for ni in range(3):
    nx = -0.4 + ni * 0.4
    for bi in range(10):
        ba = (bi / 10.0) * math.pi
        smooth_sphere(f"neck{ni}_{bi}", r=0.04,
                      loc=(nx + math.cos(ba)*0.15, 0.4 + math.sin(ba)*0.10, 0.7),
                      parent=chest_e, mat_=M_PEARL if ni % 2 == 0 else M_GEM_RED)
# Gems
for gei in range(10):
    gx_g = random.uniform(-0.5, 0.5); gy_g = random.uniform(-0.3, 0.3)
    smooth_sphere(f"gem{gei}", r=0.06,
                  loc=(gx_g, gy_g, 1.05), parent=chest_e,
                  mat_=random.choice(GEM_VARIANTS))
# Pile spilling out
for si in range(8):
    spx = random.uniform(-1.0, 1.0)
    spy = random.uniform(-1.5, -0.7)
    cyl(f"spill{si}", r=random.uniform(0.06, 0.10), depth=0.04, segs=12,
        loc=(spx, spy, 0.04), parent=chest_e, mat_=M_GOLD_SHINY)

# ============ 2 MERMAIDS on rocks (signature) ============
def make_mermaid(name, loc, scale=1.0, facing=0, tail_color=None, hair_color=None):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    if tail_color is None:
        tail_color = M_MERMAID_TAIL_GREEN
    if hair_color is None:
        hair_color = M_MERMAID_HAIR_RED
    # Upper body
    smooth_sphere(f"{name}_torso", r=0.32*scale, segs=18, rings=12, loc=(0, 0, 0.6*scale),
                  parent=base, mat_=M_MERMAID_SKIN, scale=(1, 0.85, 1.1))
    # Bikini shells (signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_shell{side}", r=0.10*scale,
                      loc=(side*0.18*scale, -0.20*scale, 0.65*scale), parent=base, mat_=M_MERMAID_BIKINI,
                      scale=(1, 0.5, 0.7))
    # Waist
    smooth_cone(f"{name}_waist", r1=0.25*scale, r2=0.20*scale, depth=0.35*scale, segs=14,
                loc=(0, 0, 0.30*scale), parent=base, mat_=M_MERMAID_SKIN)
    # FISH TAIL signature
    tail_e = empty(f"{name}_te", (0, 0, 0.10*scale), parent=base)
    tail_e.rotation_euler = (math.radians(-30), 0, 0)
    # Tail segments (scales)
    for ti in range(8):
        ti_z = -ti * 0.18*scale
        r_t = 0.22*scale - ti * 0.015
        cyl(f"{name}_t{ti}", r=r_t, depth=0.18*scale, segs=14,
            loc=(0, 0, ti_z), parent=tail_e, mat_=tail_color)
        # Scales overlap rings
        cyl(f"{name}_ts{ti}", r=r_t + 0.02*scale, depth=0.03*scale, segs=14,
            loc=(0, 0, ti_z + 0.05*scale), parent=tail_e, mat_=tail_color)
    # Tail fin signature
    fin_e = empty(f"{name}_fin", (0, 0, -1.5*scale), parent=tail_e)
    fin_e.rotation_euler = (math.radians(80), 0, 0)
    # 2 fan-shape fins
    for side in (-1, 1):
        beveled_cube(f"{name}_f{side}", (0.50*scale, 0.04*scale, 0.30*scale), bevel_offset=0.05,
                     loc=(side*0.20*scale, 0, 0.10*scale), parent=fin_e, mat_=tail_color)
        # Spiked tips
        for tip in range(3):
            smooth_cone(f"{name}_ftt{side}_{tip}", r1=0.04*scale, r2=0.005*scale, depth=0.20*scale, segs=8,
                        loc=(side*(0.20 + tip*0.10)*scale, 0, 0.30*scale),
                        parent=fin_e, mat_=tail_color)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.28*scale, 0, 0.85*scale), parent=base)
        if side == -1:
            sh.rotation_euler = (math.radians(-40), 0, math.radians(20))
        else:
            sh.rotation_euler = (math.radians(-90), 0, math.radians(-20))
        cyl(f"{name}_uarm{side_idx}", r=0.05*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.18*scale), parent=sh, mat_=M_MERMAID_SKIN)
        cyl(f"{name}_fa{side_idx}", r=0.045*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.50*scale), parent=sh, mat_=M_MERMAID_SKIN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.2*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.16*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_MERMAID_SKIN, scale=(1, 1.05, 1.1))
    # Long flowing hair signature
    for hi in range(15):
        ha = random.uniform(0, math.pi*2)
        hl_m = random.uniform(0.30, 0.55)
        hcs = beveled_cube(f"{name}_hr{hi}", (0.05*scale, 0.08*scale, hl_m*scale), bevel_offset=0.01,
                          loc=(math.cos(ha)*0.15*scale, math.sin(ha)*0.10*scale - 0.08*scale, -hl_m*scale/2),
                          parent=head_e, mat_=hair_color)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.13*scale, 0.04*scale), parent=head_e, mat_=M_EYE_BLACK_P)
    # Lips
    beveled_cube(f"{name}_lips", (0.08*scale, 0.04*scale, 0.03*scale), bevel_offset=0.005,
                 loc=(0, -0.14*scale, -0.08*scale), parent=head_e, mat_=M_GALLEON_RED)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "tail": tail_e, "fin": fin_e}

# Rocks for mermaids
rock_e_1 = empty("mer_rock1", (8, -25, 0))
smooth_sphere("rock1_b", r=2, segs=18, rings=14, loc=(0, 0, 0.5),
              parent=rock_e_1, mat_=M_ROCK_GREY_P, scale=(1.5, 1.2, 0.6))
rock_e_2 = empty("mer_rock2", (12, 25, 0))
smooth_sphere("rock2_b", r=2, segs=18, rings=14, loc=(0, 0, 0.5),
              parent=rock_e_2, mat_=M_ROCK_GREY_P, scale=(1.5, 1.2, 0.6))

mermaids = []
mer1 = make_mermaid("mer1", (8, -25, 1.0), scale=1.0, facing=math.radians(-45),
                     tail_color=M_MERMAID_TAIL_GREEN, hair_color=M_MERMAID_HAIR_RED)
mer2 = make_mermaid("mer2", (12, 25, 1.0), scale=1.0, facing=math.radians(135),
                     tail_color=M_MERMAID_TAIL_PURPLE, hair_color=M_MERMAID_HAIR_BLOND)
mermaids = [mer1, mer2]

# ============ 6 CRABS on beach ============
def make_crab(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body shell
    smooth_sphere(f"{name}_body", r=0.25*scale, segs=18, rings=12, loc=(0, 0, 0.15*scale),
                  parent=base, mat_=M_CRAB_RED, scale=(1.3, 0.9, 0.55))
    # Lighter belly
    smooth_sphere(f"{name}_b", r=0.20*scale, loc=(0, 0, 0.10*scale),
                  parent=base, mat_=M_CRAB_LIGHT, scale=(1.1, 0.8, 0.3))
    # 8 legs (signature)
    for side in (-1, 1):
        for li in range(4):
            la = -0.5 + li * 0.35
            l_e = empty(f"{name}_l{side}_{li}_e", (side*0.20*scale, la*0.18*scale, 0.10*scale), parent=base)
            l_e.rotation_euler = (0, 0, math.radians(side*-30 + la*-20))
            cyl(f"{name}_l{side}_{li}", r=0.025*scale, depth=0.20*scale, segs=8,
                loc=(side*0.10*scale, 0, -0.05*scale), parent=l_e, mat_=M_CRAB_RED)
            # Foot tip
            smooth_cone(f"{name}_lf{side}_{li}", r1=0.025*scale, r2=0.005*scale, depth=0.06*scale, segs=6,
                        loc=(side*0.18*scale, 0, -0.10*scale), parent=l_e, mat_=M_CRAB_RED)
    # CLAWS (signature huge)
    for side in (-1, 1):
        claw_e = empty(f"{name}_cl{side}_e", (side*0.20*scale, -0.10*scale, 0.15*scale), parent=base)
        claw_e.rotation_euler = (0, 0, math.radians(side*-30))
        # Arm
        cyl(f"{name}_cl_a{side}", r=0.035*scale, depth=0.20*scale, segs=8,
            loc=(side*0.15*scale, 0, 0), parent=claw_e, mat_=M_CRAB_RED)
        # Claw upper
        smooth_sphere(f"{name}_cl_u{side}", r=0.10*scale,
                      loc=(side*0.30*scale, -0.05*scale, 0.02*scale), parent=claw_e, mat_=M_CRAB_RED,
                      scale=(1.3, 0.8, 0.6))
        # Claw lower (pinching)
        smooth_sphere(f"{name}_cl_lw{side}", r=0.08*scale,
                      loc=(side*0.30*scale, -0.05*scale, -0.04*scale), parent=claw_e, mat_=M_CRAB_RED,
                      scale=(1.5, 0.8, 0.4))
    # Eyes on stalks (signature)
    for side in (-1, 1):
        cyl(f"{name}_es{side}", r=0.015*scale, depth=0.08*scale, segs=6,
            loc=(side*0.08*scale, -0.12*scale, 0.20*scale), parent=base, mat_=M_CRAB_RED)
        smooth_sphere(f"{name}_e{side}", r=0.03*scale,
                      loc=(side*0.08*scale, -0.12*scale, 0.27*scale), parent=base, mat_=M_EYE_BLACK_P)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base}

crabs = []
crab_pos = [(-15, -10, math.radians(45)), (-25, -5, math.radians(-30)),
             (-8, 5, math.radians(120)), (-22, 8, math.radians(60)),
             (-12, -15, math.radians(150)), (-18, 12, math.radians(-60))]
for i, (cx, cy, fac) in enumerate(crab_pos):
    c = make_crab(f"crab{i}", (cx, cy, 0), scale=1.0, facing=fac)
    crabs.append(c)

# ============================================================
# ⭐ 600 GOLD COINS + 400 SEA SPRAY (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
coins = []
for i in range(600):
    px = random.uniform(-25, 25)
    py = random.uniform(-25, 25)
    pz = random.uniform(0.5, 14)
    coin = cyl(f"coin{i}", r=random.uniform(0.07, 0.10), depth=0.025, segs=14,
               loc=(px, py, pz), mat_=M_GOLD_SHINY)
    coin["_phase"] = random.uniform(0, math.pi*2)
    coin["_base_x"] = px; coin["_base_y"] = py; coin["_base_z"] = pz
    coin["_amp_x"] = random.uniform(0.5, 1.2)
    coin["_amp_y"] = random.uniform(0.5, 1.2)
    coin["_speed"] = random.uniform(0.5, 1.2)
    coin["_fall"] = random.uniform(1.5, 3.0)
    coins.append(coin)

# 400 sea spray droplets
sprays = []
for i in range(400):
    px = random.uniform(10, 55)
    py = random.uniform(-40, 40)
    pz = random.uniform(1, 10)
    s_obj = smooth_sphere(f"spray{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6,
                          loc=(px, py, pz), mat_=M_SPRAY)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(1.5, 3.0)
    s_obj["_amp_y"] = random.uniform(1.5, 3.0)
    s_obj["_amp_z"] = random.uniform(0.5, 1.5)
    s_obj["_speed"] = random.uniform(0.5, 1.2)
    sprays.append(s_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Galleon waves bob
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    galleon_e.location.z = 2.0 + math.sin(t * 1.2) * 0.20
    galleon_e.rotation_euler = (math.sin(t * 1.2) * math.radians(3),
                                 math.cos(t * 1.2) * math.radians(3), 0)
    galleon_e.keyframe_insert("location", frame=f)
    galleon_e.keyframe_insert("rotation_euler", frame=f)

# Sails ripple wind
for sail in sails_all:
    phase = sail["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        sail.rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5),
                                math.cos(t * 1.5 + phase) * math.radians(3), 0)
        sail.keyframe_insert("rotation_euler", frame=f)

# Pirates sway drunk
for p in pirates:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        p["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(5),
                                     math.cos(t * 1.2 + phase) * math.radians(6),
                                     p["root"].rotation_euler.z)
        p["root"].location.z = 2.3 + math.sin(t * 1.5 + phase) * 0.08
        p["root"].keyframe_insert("rotation_euler", frame=f)
        p["root"].keyframe_insert("location", frame=f)
        p["he"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(15))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Captain proud body + head + sword brandish
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    captain_p_e.rotation_euler = (0, math.sin(t * 1.0) * math.radians(3), 0)
    captain_p_e.keyframe_insert("rotation_euler", frame=f)
    capP_head_e.rotation_euler = (0, 0, math.sin(t * 0.8) * math.radians(20))
    capP_head_e.keyframe_insert("rotation_euler", frame=f)
    sword_arm_e.rotation_euler = (math.radians(-130) + math.sin(t * 2.0) * math.radians(8),
                                   0, math.radians(-30))
    sword_arm_e.keyframe_insert("rotation_euler", frame=f)

# Parrot wing flap + head turn
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    p_wing_L = bpy.data.objects.get("p_w-1")
    p_wing_R = bpy.data.objects.get("p_w1")
    if p_wing_L:
        p_wing_L.rotation_euler = (math.sin(t * 8.0) * math.radians(20), 0, 0)
        p_wing_L.keyframe_insert("rotation_euler", frame=f)
    if p_wing_R:
        p_wing_R.rotation_euler = (-math.sin(t * 8.0) * math.radians(20), 0, 0)
        p_wing_R.keyframe_insert("rotation_euler", frame=f)
    parrot_head_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(30))
    parrot_head_e.keyframe_insert("rotation_euler", frame=f)

# Palms sway in breeze
for p in palms:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        p["crown"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(5),
                                      math.cos(t * 1.0 + phase) * math.radians(5), 0)
        p["crown"].keyframe_insert("rotation_euler", frame=f)

# Cannons recoil intermittent
for ci, c_e in enumerate(cannons):
    phase = c_e["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        # Sporadic fire
        if math.sin(t * 1.0 + phase) > 0.95:
            c_e.location.z = 1.3 - 0.05
        else:
            c_e.location.z = 1.3
        c_e.keyframe_insert("location", frame=f)

# Mermaids tail flick
for mr in mermaids:
    phase = mr["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        mr["tail"].rotation_euler = (math.radians(-30) + math.sin(t * 2.0 + phase) * math.radians(10),
                                       0, math.cos(t * 2.0 + phase) * math.radians(15))
        mr["tail"].keyframe_insert("rotation_euler", frame=f)
        mr["he"].rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(20))
        mr["he"].keyframe_insert("rotation_euler", frame=f)
        mr["root"].location.z = 1.0 + math.sin(t * 1.5 + phase) * 0.05
        mr["root"].keyframe_insert("location", frame=f)

# Crabs scuttle
for c in crabs:
    phase = c["root"]["_phase"]
    bx_c = c["root"].location.x; by_c = c["root"].location.y
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        c["root"].location.x = bx_c + math.sin(t * 2.0 + phase) * 0.8
        c["root"].location.y = by_c + math.cos(t * 1.8 + phase) * 0.5
        c["root"].keyframe_insert("location", frame=f)

# 600 coins falling + spin
for c in coins:
    phase = c["_phase"]; speed = c["_speed"]; fall = c["_fall"]
    bx, by, bz = c["_base_x"], c["_base_y"], c["_base_z"]
    ax_c, ay_c = c["_amp_x"], c["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax_c * math.sin(t * speed + phase)
        y = by + ay_c * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.5)
        if z < 0.5: z = bz
        c.location = (x, y, max(0.3, z))
        c.rotation_euler = (t * 6.0 + phase, t * 4.0 + phase, t * 5.0 + phase)
        c.keyframe_insert("location", frame=f)
        c.keyframe_insert("rotation_euler", frame=f)

# 400 sea spray drift
for s in sprays:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        s.location = (x, y, max(0.5, z))
        s.keyframe_insert("location", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_pirate_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_caribbean_pirate_island_treasure] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_caribbean_pirate_island_treasure] galleon 3 masts + jolly roger + 8 cannons + 6 pirates + captain + parrot + 8 palms + open treasure chest + 2 mermaids + 6 crabs + 600 gold coins + 400 sea spray")
print("⭐ FIXES: 1 ground + 600 gold coins + 400 sea spray (signature Caribbean pirate thematic mandatory) ⭐")
