"""
proc_amazon_jungle_tribe_river.py — 255e procédural AuroraIA (120e qualité)
Amazon jungle Yanomami tribe: 8 giant canopy trees + 6 tribe members with body paint + chief shaman + maloca + river + 4 canoes + caiman + jaguar + 6 toucans + 4 monkeys + 600 leaves + 400 fireflies
FIXES : 1 ground + 600 leaves + 400 fireflies (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB255)

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

# Jungle sky filtered
M_SKY = mat("sky", (0.20, 0.45, 0.30, 1.0), 0.0, 0.7, emission=(0.20,0.45,0.30), emission_strength=1.5)
M_SKY_GOLD = mat("sky_g", (0.55, 0.65, 0.30, 1.0), 0.0, 0.7, emission=(0.55,0.65,0.30), emission_strength=2.0)
M_SUN_J = mat("sun", (1.0, 0.92, 0.55, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.55), emission_strength=12.0)

# Ground jungle floor
M_MUD = mat("mud", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85, emission=(0.30,0.20,0.10), emission_strength=0.3)
M_LEAF_LITTER = mat("litter", (0.42, 0.30, 0.15, 1.0), 0.0, 0.85, emission=(0.40,0.28,0.15), emission_strength=0.3)
M_MOSS_J = mat("moss_j", (0.18, 0.42, 0.22, 1.0), 0.0, 0.80, emission=(0.18,0.40,0.22), emission_strength=0.4)
M_ROCK_J = mat("rock_j", (0.30, 0.28, 0.25, 1.0), 0.0, 0.85)

# Tree trunks
M_TRUNK_DARK_J = mat("trunk_d", (0.28, 0.18, 0.08, 1.0), 0.0, 0.85, emission=(0.25,0.18,0.08), emission_strength=0.3)
M_TRUNK_LIGHT = mat("trunk_l", (0.42, 0.28, 0.12, 1.0), 0.0, 0.75, emission=(0.40,0.28,0.12), emission_strength=0.4)
M_TRUNK_BARK = mat("trunk_b", (0.55, 0.35, 0.18, 1.0), 0.0, 0.85)

# Leaves
M_LEAF_DARK = mat("leaf_d", (0.10, 0.35, 0.15, 1.0), 0.0, 0.70, emission=(0.10,0.35,0.15), emission_strength=0.6)
M_LEAF_MID = mat("leaf_m", (0.18, 0.55, 0.22, 1.0), 0.0, 0.70, emission=(0.18,0.55,0.22), emission_strength=0.7)
M_LEAF_BRIGHT = mat("leaf_b", (0.30, 0.78, 0.32, 1.0), 0.0, 0.65, emission=(0.28,0.75,0.32), emission_strength=0.8)
M_LEAF_RED = mat("leaf_r", (0.78, 0.20, 0.18, 1.0), 0.0, 0.65, emission=(0.72,0.18,0.18), emission_strength=0.7)
M_LEAF_YELLOW = mat("leaf_y", (0.95, 0.85, 0.20, 1.0), 0.0, 0.65, emission=(0.92,0.82,0.20), emission_strength=0.8)
LEAF_VARIANTS = [M_LEAF_DARK, M_LEAF_MID, M_LEAF_BRIGHT]

# Vines
M_VINE = mat("vine", (0.32, 0.42, 0.18, 1.0), 0.0, 0.80, emission=(0.30,0.40,0.18), emission_strength=0.4)
M_LIANA = mat("liana", (0.42, 0.28, 0.12, 1.0), 0.0, 0.85)

# Tribe skin
M_SKIN_TRIBAL = mat("skin", (0.65, 0.42, 0.25, 1.0), 0.0, 0.55, emission=(0.62,0.42,0.25), emission_strength=0.4)
M_PAINT_RED = mat("p_r", (0.85, 0.18, 0.15, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.15), emission_strength=0.8)
M_PAINT_BLACK = mat("p_bk", (0.10, 0.08, 0.06, 1.0), 0.0, 0.65)
M_PAINT_WHITE = mat("p_w", (0.92, 0.88, 0.78, 1.0), 0.0, 0.50, emission=(0.85,0.82,0.75), emission_strength=0.8)
M_HAIR_BLACK_T = mat("h_bk", (0.08, 0.06, 0.04, 1.0), 0.0, 0.55)

# Loincloth (signature traditional respectful attire)
M_LOINCLOTH_BROWN = mat("loin_br", (0.40, 0.25, 0.12, 1.0), 0.0, 0.80, emission=(0.38,0.25,0.12), emission_strength=0.3)
M_LOINCLOTH_RED = mat("loin_r", (0.62, 0.18, 0.15, 1.0), 0.0, 0.65, emission=(0.58,0.18,0.15), emission_strength=0.5)
M_FIBER_NATURAL = mat("fiber", (0.78, 0.65, 0.42, 1.0), 0.0, 0.85)

# Bow + arrow
M_BOW = mat("bow", (0.42, 0.28, 0.15, 1.0), 0.0, 0.85)
M_BOW_STRING = mat("bow_s", (0.85, 0.78, 0.55, 1.0), 0.0, 0.55)
M_ARROW_SHAFT = mat("arrow_s", (0.55, 0.42, 0.20, 1.0), 0.0, 0.75)
M_ARROW_HEAD = mat("arrow_h", (0.55, 0.30, 0.15, 1.0), 0.0, 0.70)

# Feathers signature tropical
M_FEATHER_RED_T = mat("feat_r", (0.95, 0.20, 0.20, 1.0), 0.0, 0.45, emission=(0.92,0.20,0.20), emission_strength=2.0)
M_FEATHER_BLUE_T = mat("feat_b", (0.20, 0.55, 0.95, 1.0), 0.0, 0.45, emission=(0.20,0.55,0.92), emission_strength=2.0)
M_FEATHER_YELLOW_T = mat("feat_y", (1.0, 0.92, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.88,0.20), emission_strength=2.2)
M_FEATHER_GREEN_T = mat("feat_g", (0.30, 0.85, 0.40, 1.0), 0.0, 0.45, emission=(0.30,0.80,0.40), emission_strength=2.0)
FEATHER_TROPICAL = [M_FEATHER_RED_T, M_FEATHER_BLUE_T, M_FEATHER_YELLOW_T, M_FEATHER_GREEN_T]

# Maloca house
M_MALOCA_THATCH = mat("mal_t", (0.55, 0.42, 0.20, 1.0), 0.0, 0.85, emission=(0.52,0.40,0.20), emission_strength=0.3)
M_MALOCA_POLE = mat("mal_p", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)

# Water
M_WATER_AMAZON = mat("water", (0.18, 0.32, 0.20, 1.0), 0.1, 0.20, emission=(0.18,0.30,0.20), emission_strength=1.0, alpha=0.78)
M_WATER_DEEP_AM = mat("water_d", (0.10, 0.20, 0.12, 1.0), 0.1, 0.25, alpha=0.85)

# Canoe
M_CANOE_WOOD = mat("can_w", (0.38, 0.22, 0.10, 1.0), 0.0, 0.75)
M_CANOE_DARK = mat("can_d", (0.22, 0.12, 0.06, 1.0), 0.0, 0.85)

# Jaguar (signature spotted)
M_JAGUAR = mat("jag", (0.85, 0.65, 0.32, 1.0), 0.0, 0.70, emission=(0.78,0.62,0.32), emission_strength=0.4)
M_JAGUAR_SPOT = mat("jag_s", (0.18, 0.10, 0.06, 1.0), 0.0, 0.80)
M_JAGUAR_BELLY = mat("jag_b", (0.95, 0.78, 0.45, 1.0), 0.0, 0.70)
M_JAGUAR_EYE = mat("jag_e", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.30), emission_strength=6.0)

# Toucan signature (rainbow beak)
M_TOUCAN_BODY = mat("tou_b", (0.08, 0.06, 0.06, 1.0), 0.0, 0.65, emission=(0.08,0.06,0.06), emission_strength=0.3)
M_TOUCAN_CHEST = mat("tou_c", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65)
M_TOUCAN_BEAK_O = mat("tou_bo", (1.0, 0.55, 0.18, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.18), emission_strength=1.8)
M_TOUCAN_BEAK_Y = mat("tou_by", (1.0, 0.92, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.88,0.20), emission_strength=2.0)
M_TOUCAN_BEAK_BK = mat("tou_bk", (0.10, 0.08, 0.06, 1.0), 0.0, 0.45)
M_TOUCAN_EYE_RING = mat("tou_e", (0.20, 0.55, 0.85, 1.0), 0.0, 0.30, emission=(0.18,0.55,0.85), emission_strength=2.5)

# Monkey
M_MONKEY_BROWN = mat("mk_b", (0.42, 0.25, 0.12, 1.0), 0.0, 0.85, emission=(0.40,0.25,0.12), emission_strength=0.3)
M_MONKEY_FACE = mat("mk_f", (0.85, 0.62, 0.42, 1.0), 0.0, 0.55)
M_MONKEY_DARK = mat("mk_d", (0.18, 0.10, 0.06, 1.0), 0.0, 0.85)

# Caiman
M_CAIMAN_GREEN = mat("ca_g", (0.25, 0.32, 0.15, 1.0), 0.0, 0.80, emission=(0.25,0.32,0.15), emission_strength=0.4)
M_CAIMAN_DARK = mat("ca_d", (0.12, 0.18, 0.10, 1.0), 0.0, 0.85)
M_CAIMAN_EYE = mat("ca_e", (1.0, 0.85, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.20), emission_strength=5.0)
M_TEETH_W = mat("teeth", (0.95, 0.92, 0.85, 1.0), 0.0, 0.40)

# Piranha
M_PIRANHA = mat("pir", (0.45, 0.55, 0.45, 1.0), 0.3, 0.40, emission=(0.42,0.52,0.42), emission_strength=0.6)
M_PIRANHA_RED = mat("pir_r", (0.78, 0.20, 0.15, 1.0), 0.0, 0.55)

# Macaw (parrot)
M_MACAW_BLUE = mat("mc_b", (0.20, 0.45, 0.95, 1.0), 0.0, 0.45, emission=(0.20,0.45,0.92), emission_strength=2.0)
M_MACAW_YELLOW = mat("mc_y", (1.0, 0.85, 0.25, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.25), emission_strength=2.0)
M_MACAW_RED = mat("mc_r", (0.95, 0.18, 0.18, 1.0), 0.0, 0.45, emission=(0.92,0.18,0.18), emission_strength=2.0)
M_MACAW_GREEN = mat("mc_g", (0.30, 0.85, 0.40, 1.0), 0.0, 0.45, emission=(0.30,0.80,0.40), emission_strength=2.0)

# Eye / lips
M_EYE_DARK_J = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Fire (campfire)
M_FIRE_O_J = mat("fire_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=18.0)
M_FIRE_C_J = mat("fire_c", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=22.0)

# Firefly
M_FIREFLY_Y = mat("ff_y", (1.0, 0.95, 0.45, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.45), emission_strength=12.0)
M_FIREFLY_G = mat("ff_g", (0.55, 1.0, 0.45, 1.0), 0.0, 0.10, emission=(0.55,1.0,0.45), emission_strength=12.0)
FIREFLY_COLORS = [M_FIREFLY_Y, M_FIREFLY_G]

# Bones (necklace)
M_BONE = mat("bone", (0.92, 0.85, 0.78, 1.0), 0.0, 0.55)
M_SEED = mat("seed", (0.55, 0.35, 0.18, 1.0), 0.0, 0.70)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Filtered sunlight beams
sun_j = smooth_sphere("sun", r=4, segs=24, rings=18, loc=(20, 60, 80), mat_=M_SUN_J)
# Light shafts (signature dappled jungle)
for li in range(12):
    la = (li / 12.0) * math.pi * 2 + math.pi/8
    lr = random.uniform(20, 50)
    lx_l = math.cos(la) * lr
    ly_l = math.sin(la) * lr
    beam_e = empty(f"beam{li}", (lx_l, ly_l, 30))
    beam_e.rotation_euler = (math.radians(60), 0, la)
    smooth_cone(f"bm{li}", r1=0.5, r2=2, depth=20, segs=10, loc=(0, 0, 0),
                parent=beam_e, mat_=M_SUN_J)

# ============ ONE clean jungle floor ground ============
ground = beveled_cube("ground", (220, 220, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_MUD)
# Organic leaf litter + mud + moss patches
for i in range(200):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 95)
    mat_c = [M_LEAF_LITTER, M_MOSS_J, M_MUD, M_ROCK_J][i % 4]
    smooth_sphere(f"flr{i}", r=random.uniform(0.4, 1.0), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=mat_c, scale=(1.5, 1.4, 0.20))

# ============ 8 GIANT CANOPY TREES (signature massive) ============
def make_jungle_tree(name, loc, scale=1.0, height=15):
    base = empty(name, loc)
    # Buttress roots (signature jungle)
    for ri in range(6):
        ra = (ri / 6.0) * math.pi * 2
        rx_p = math.cos(ra) * 1.2
        ry_p = math.sin(ra) * 1.2
        beveled_cube(f"{name}_butt{ri}", (0.5, 2.5, 1.5), bevel_offset=0.15,
                     loc=(rx_p, ry_p, 0.75), parent=base, mat_=M_TRUNK_DARK_J).rotation_euler = (0, 0, ra)
    # Trunk tall (signature)
    for ti in range(int(height/2)):
        tz = 1.5 + ti * 2
        cyl(f"{name}_t{ti}", r=0.7 - ti*0.025, depth=2, segs=14, loc=(0, 0, tz + 1),
            parent=base, mat_=M_TRUNK_LIGHT if ti % 2 == 0 else M_TRUNK_BARK)
    # Branches at top spreading
    branches = []
    for bi in range(8):
        ba = (bi / 8.0) * math.pi * 2 + random.uniform(-0.2, 0.2)
        br_e = empty(f"{name}_br{bi}_e", (0, 0, height-1), parent=base)
        br_e.rotation_euler = (math.radians(random.uniform(35, 65)), 0, ba)
        cyl(f"{name}_br{bi}", r=0.20, depth=3, segs=10, loc=(0, 0, 1.5),
            parent=br_e, mat_=M_TRUNK_BARK)
        # Sub branches
        for sb in range(3):
            sba = random.uniform(0, math.pi*2)
            sbr_e = empty(f"{name}_sbr{bi}_{sb}_e", (0, 0, 3), parent=br_e)
            sbr_e.rotation_euler = (math.radians(random.uniform(20, 45)), 0, sba)
            cyl(f"{name}_sbr{bi}_{sb}", r=0.08, depth=2, segs=8, loc=(0, 0, 1),
                parent=sbr_e, mat_=M_TRUNK_BARK)
            branches.append(sbr_e)
    # MASSIVE foliage canopy (signature)
    for fi in range(150):
        fa = random.uniform(0, math.pi*2)
        fr = random.uniform(2, 7)*scale
        fz_f = height + random.uniform(-1, 3)
        smooth_sphere(f"{name}_fl{fi}", r=random.uniform(0.5, 1.0),
                      loc=(math.cos(fa)*fr, math.sin(fa)*fr, fz_f),
                      parent=base, mat_=random.choice(LEAF_VARIANTS))
    # Vines hanging
    for vi in range(6):
        va = (vi / 6.0) * math.pi * 2
        vine_e = empty(f"{name}_v{vi}_e", (math.cos(va)*3, math.sin(va)*3, height), parent=base)
        for sg in range(8):
            cyl(f"{name}_v{vi}_{sg}", r=0.04, depth=0.8, segs=6,
                loc=(math.sin(sg*0.5)*0.20, 0, -sg*0.8 + 0.4),
                parent=vine_e, mat_=M_VINE)
        # Leaves on vine
        for lv in range(4):
            smooth_sphere(f"{name}_v{vi}_l{lv}", r=0.20,
                          loc=(math.sin(lv*0.7)*0.30, 0, -lv*1.8 + 0.4),
                          parent=vine_e, mat_=random.choice(LEAF_VARIANTS),
                          scale=(1.5, 0.3, 1))
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

jungle_trees = []
tree_pos = [(-25, -30, 0, 15), (25, -30, 0, 16), (-35, 0, 0, 18),
             (35, 0, 0, 17), (-30, 35, 0, 15), (30, 35, 0, 16),
             (-15, -60, 0, 14), (15, -60, 0, 15)]
for i, (tx, ty, tz, h) in enumerate(tree_pos):
    t = make_jungle_tree(f"jtree{i}", (tx, ty, tz), scale=1.0, height=h)
    jungle_trees.append(t)

# ============ RIVER (serpentine signature) ============
river_pts = []
for ri in range(35):
    rv_y = -50 + ri * 2.5
    rv_x = math.sin(ri * 0.25) * 6 + 15
    river_pts.append((rv_x, rv_y, 0))

for ri in range(len(river_pts) - 1):
    rx1, ry1, _ = river_pts[ri]; rx2, ry2, _ = river_pts[ri+1]
    rmidx = (rx1 + rx2) / 2; rmidy = (ry1 + ry2) / 2
    rlen = math.sqrt((rx2-rx1)**2 + (ry2-ry1)**2) + 0.5
    rang = math.atan2(ry2-ry1, rx2-rx1)
    seg = beveled_cube(f"river{ri}", (rlen, 8, 0.18), bevel_offset=0.04,
                       loc=(rmidx, rmidy, 0.18), mat_=M_WATER_AMAZON)
    seg.rotation_euler = (0, 0, rang)
    seg2 = beveled_cube(f"river_d{ri}", (rlen*0.95, 7, 0.12), bevel_offset=0.03,
                        loc=(rmidx, rmidy, 0.22), mat_=M_WATER_DEEP_AM)
    seg2.rotation_euler = (0, 0, rang)

# ============ MALOCA (signature communal house round) ============
maloca_e = empty("maloca", loc=(-5, 5, 0))
# 12 outer support poles
for pi in range(12):
    pa = (pi / 12.0) * math.pi * 2
    cyl(f"mal_p{pi}", r=0.20, depth=4, segs=12, loc=(math.cos(pa)*4, math.sin(pa)*4, 2),
        parent=maloca_e, mat_=M_MALOCA_POLE)
# Central pole
cyl("mal_cp", r=0.35, depth=8, segs=14, loc=(0, 0, 4), parent=maloca_e, mat_=M_MALOCA_POLE)
# Thatched roof signature (cone)
for ri in range(10):
    rz_m = 4 + ri * 0.45
    rr_m = 5 - ri * 0.45
    cyl(f"mal_r{ri}", r=rr_m, depth=0.50, segs=20, loc=(0, 0, rz_m),
        parent=maloca_e, mat_=M_MALOCA_THATCH if ri % 2 == 0 else M_LEAF_DARK)
# Top peak
smooth_cone("mal_peak", r1=0.30, r2=0.05, depth=0.8, segs=12, loc=(0, 0, 9.0),
            parent=maloca_e, mat_=M_MALOCA_THATCH)
# Doorway
beveled_cube("mal_door", (1.5, 0.4, 2.5), bevel_offset=0.10, loc=(0, -4, 1.25),
             parent=maloca_e, mat_=M_TRUNK_DARK_J)
# Interior fire pit
cyl("mal_fire_b", r=0.6, depth=0.10, segs=14, loc=(0, 0, 0.10), parent=maloca_e, mat_=M_ROCK_J)
# Stones around fire
for si in range(8):
    sa = (si / 8.0) * math.pi * 2
    smooth_sphere(f"mal_fs{si}", r=0.15, loc=(math.cos(sa)*0.5, math.sin(sa)*0.5, 0.15),
                  parent=maloca_e, mat_=M_ROCK_J)
# Fire
fire_mal_e = empty("mal_fire", (0, 0, 0.30), parent=maloca_e)
smooth_cone("mal_fo", r1=0.35, r2=0.05, depth=0.8, segs=14, loc=(0, 0, 0.4), parent=fire_mal_e, mat_=M_FIRE_O_J)
smooth_cone("mal_fc", r1=0.20, r2=0.02, depth=0.6, segs=14, loc=(0, 0, 0.30), parent=fire_mal_e, mat_=M_FIRE_C_J)

# ============ 6 TRIBE MEMBERS with body paint + loincloths ============
def make_tribe_member(name, loc, scale=1.0, facing=0, role="hunter"):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body skin (with red body paint)
    # Torso
    smooth_cone(f"{name}_torso", r1=0.30, r2=0.32, depth=0.55, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=M_SKIN_TRIBAL)
    # Red painted chest/torso (signature)
    smooth_cone(f"{name}_paint_t", r1=0.31, r2=0.33, depth=0.55, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=M_PAINT_RED)
    # White geometric body paint dots
    for di in range(10):
        da = (di / 10.0) * math.pi * 2
        smooth_sphere(f"{name}_dp{di}", r=0.025,
                      loc=(math.cos(da)*0.32, math.sin(da)*0.20, 1.30 + random.uniform(-0.2, 0.2)),
                      parent=base, mat_=M_PAINT_WHITE)
    # Loincloth (signature traditional)
    loin_col = random.choice([M_LOINCLOTH_BROWN, M_LOINCLOTH_RED, M_FIBER_NATURAL])
    beveled_cube(f"{name}_loin", (0.40, 0.10, 0.40), bevel_offset=0.04,
                 loc=(0, -0.05, 0.95), parent=base, mat_=loin_col)
    # Back panel
    beveled_cube(f"{name}_loin_b", (0.40, 0.10, 0.40), bevel_offset=0.04,
                 loc=(0, 0.05, 0.95), parent=base, mat_=loin_col)
    # Side hip cord
    cyl(f"{name}_belt", r=0.30, depth=0.05, segs=14, loc=(0, 0, 1.10),
        parent=base, mat_=M_FIBER_NATURAL)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.09, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.42), parent=base, mat_=M_SKIN_TRIBAL)
        # Red paint stripes on legs
        for sl in range(3):
            cyl(f"{name}_ls{side}_{sl}", r=0.095, depth=0.05, segs=10,
                loc=(side*0.13, 0, 0.15 + sl*0.30), parent=base, mat_=M_PAINT_RED)
    # Feet
    for side in (-1, 1):
        beveled_cube(f"{name}_ft{side}", (0.10, 0.20, 0.05), bevel_offset=0.02,
                     loc=(side*0.13, 0, 0), parent=base, mat_=M_SKIN_TRIBAL)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        if role == "hunter" and side == 1:
            # Right arm holding bow
            sh = empty(f"{name}_sh{side_idx}", (side*0.30, -0.10, 1.60), parent=base)
            sh.rotation_euler = (math.radians(-80), 0, math.radians(-30))
        elif role == "shaman" and side == 1:
            # Right arm raised to sky
            sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.60), parent=base)
            sh.rotation_euler = (math.radians(-160), 0, math.radians(-15))
        else:
            sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.60), parent=base)
            sh.rotation_euler = (math.radians(-30 + side*15), 0, math.radians(side*-10))
        cyl(f"{name}_uarm{side_idx}", r=0.06, depth=0.40, segs=10,
            loc=(0, 0, -0.20), parent=sh, mat_=M_SKIN_TRIBAL)
        # Red paint band arm
        cyl(f"{name}_pb{side_idx}", r=0.065, depth=0.06, segs=10,
            loc=(0, 0, -0.15), parent=sh, mat_=M_PAINT_RED)
        cyl(f"{name}_fa{side_idx}", r=0.05, depth=0.35, segs=10,
            loc=(0, 0, -0.55), parent=sh, mat_=M_SKIN_TRIBAL)
    # Head
    head_t_e = empty(f"{name}_he", (0, 0, 1.85), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_t_e, mat_=M_SKIN_TRIBAL)
    # Black painted face stripe (signature)
    beveled_cube(f"{name}_face_p", (0.36, 0.04, 0.06), bevel_offset=0.01, loc=(0, -0.16, -0.02),
                 parent=head_t_e, mat_=M_PAINT_BLACK)
    # White paint dots
    for di in range(5):
        da = (di / 5.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_fp{di}", r=0.015, loc=(math.sin(da)*0.15, -0.17, 0.10),
                      parent=head_t_e, mat_=M_PAINT_WHITE)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_t_e, mat_=M_EYE_DARK_J)
    # Black bowl-cut hair (signature)
    for hi in range(12):
        ha = (hi / 12.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.06,
                      loc=(math.cos(ha)*0.18, math.sin(ha)*0.13, 0.10),
                      parent=head_t_e, mat_=M_HAIR_BLACK_T)
    # Necklace (signature seeds + bones)
    for ni in range(12):
        na = (ni / 12.0) * math.pi
        if ni % 2 == 0:
            smooth_sphere(f"{name}_neck{ni}", r=0.04,
                          loc=(math.sin(na)*0.20, -0.18, 1.62),
                          parent=base, mat_=M_SEED)
        else:
            cyl(f"{name}_neckb{ni}", r=0.02, depth=0.06, segs=8,
                loc=(math.sin(na)*0.20, -0.18, 1.62),
                parent=base, mat_=M_BONE)
    # Headdress feathers (signature - shaman has bigger)
    if role == "shaman":
        # Feather crown signature
        for fi in range(15):
            fa = (fi / 15.0) * math.pi - math.pi/2
            fl = random.uniform(0.4, 0.7)
            feat_col = random.choice(FEATHER_TROPICAL)
            feat = smooth_cone(f"{name}_fhd{fi}", r1=0.04, r2=0.005, depth=fl, segs=8,
                              loc=(math.sin(fa)*0.20, 0, 0.20 + fl/2),
                              parent=head_t_e, mat_=feat_col)
            feat.rotation_euler = (math.radians(-15), 0, fa)
    else:
        # Simple feather band
        cyl(f"{name}_fb", r=0.20, depth=0.05, segs=14, loc=(0, 0, 0.20),
            parent=head_t_e, mat_=M_PAINT_RED)
        # Some feathers
        for fi in range(5):
            fa = (fi / 5.0) * math.pi - math.pi/2
            feat = smooth_cone(f"{name}_f{fi}", r1=0.03, r2=0.005, depth=0.30, segs=6,
                              loc=(math.sin(fa)*0.20, 0, 0.30),
                              parent=head_t_e, mat_=random.choice(FEATHER_TROPICAL))
            feat.rotation_euler = (math.radians(-15), 0, fa)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_t_e, "role": role}

# 6 tribe members: 1 shaman chief + 5 others
tribe = []
tribe_data = [("shaman", (-2, 0, 0), 0),
               ("hunter", (2, 0, 0), math.radians(-30)),
               ("hunter", (-4, 3, 0), math.radians(45)),
               ("warrior", (4, 3, 0), math.radians(-45)),
               ("warrior", (-3, -3, 0), math.radians(60)),
               ("warrior", (3, -3, 0), math.radians(-60))]
for i, (role, (tx, ty, tz), fac) in enumerate(tribe_data):
    t = make_tribe_member(f"tribe{i}", (tx, ty, tz), scale=1.0, facing=fac, role=role)
    tribe.append(t)

# BOW + ARROWS in hunter's hand
bow_e = empty("bow", (2.5, -0.5, 1.3))
# Bow curve
for bi in range(10):
    ba = (bi / 9.0) * math.pi - math.pi/2
    cyl(f"bw{bi}", r=0.04, depth=0.20, segs=8,
        loc=(0, math.sin(ba)*0.6, math.cos(ba)*0.3),
        parent=bow_e, mat_=M_BOW).rotation_euler = (ba, 0, 0)
# String
cyl("bw_str", r=0.005, depth=1.2, segs=6, loc=(0, 0, 0),
    parent=bow_e, mat_=M_BOW_STRING).rotation_euler = (math.radians(90), 0, 0)
# Arrow
cyl("arr_s", r=0.015, depth=1.0, segs=6, loc=(0, 0, -0.10),
    parent=bow_e, mat_=M_ARROW_SHAFT).rotation_euler = (math.radians(90), 0, 0)
smooth_cone("arr_h", r1=0.04, r2=0.005, depth=0.12, segs=8, loc=(0, 0.55, -0.10),
            parent=bow_e, mat_=M_ARROW_HEAD).rotation_euler = (math.radians(90), 0, 0)
# Feathers
for ff in range(3):
    fa_a = (ff / 3.0) * math.pi * 2
    beveled_cube(f"arr_f{ff}", (0.04, 0.10, 0.04), bevel_offset=0.005,
                 loc=(math.cos(fa_a)*0.03, -0.45, -0.10 + math.sin(fa_a)*0.03),
                 parent=bow_e, mat_=random.choice(FEATHER_TROPICAL))

# ============ 4 CANOES on river (signature) ============
def make_canoe(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long hull (signature carved log)
    smooth_cone(f"{name}_hull", r1=0.30, r2=0.10, depth=3.5, segs=14, loc=(0, 0, 0),
                parent=base, mat_=M_CANOE_WOOD).rotation_euler = (0, math.radians(90), 0)
    # Plank lines on side
    beveled_cube(f"{name}_pl", (3.5, 0.6, 0.06), bevel_offset=0.02, loc=(0, 0, 0.10),
                 parent=base, mat_=M_CANOE_DARK)
    # Paddle (signature)
    paddle_e = empty(f"{name}_pad", (1.0, -0.4, 0.30), parent=base)
    paddle_e.rotation_euler = (math.radians(-30), 0, math.radians(60))
    cyl(f"{name}_p_s", r=0.025, depth=1.5, segs=8, loc=(0, 0, 0),
        parent=paddle_e, mat_=M_BOW)
    # Blade
    beveled_cube(f"{name}_p_b", (0.20, 0.08, 0.40), bevel_offset=0.04, loc=(0, 0, -0.95),
                 parent=paddle_e, mat_=M_BOW)
    return base

canoes = []
canoe_pos = [(13, -30, math.radians(0)), (17, -20, math.radians(10)),
              (12, -10, math.radians(-10)), (16, 5, math.radians(5))]
for i, (cx, cy, fac) in enumerate(canoe_pos):
    c = make_canoe(f"canoe{i}", (cx, cy, 0.3), scale=1.0, facing=fac)
    canoes.append(c)

# ============ 3 PIRANHAS in river ============
for pi in range(3):
    px_p = 16 + random.uniform(-3, 3); py_p = -30 + pi*15; pz_p = 0.30
    p_e = empty(f"piranha{pi}", (px_p, py_p, pz_p))
    # Body flat oval (signature)
    smooth_sphere(f"pir_b{pi}", r=0.30, segs=14, rings=10, loc=(0, 0, 0),
                  parent=p_e, mat_=M_PIRANHA, scale=(1.3, 0.85, 0.55))
    # Red belly
    smooth_sphere(f"pir_belly{pi}", r=0.20, loc=(0, 0, -0.10),
                  parent=p_e, mat_=M_PIRANHA_RED, scale=(1.2, 0.85, 0.4))
    # Tail fin
    beveled_cube(f"pir_tail{pi}", (0.10, 0.04, 0.20), bevel_offset=0.02,
                 loc=(-0.35, 0, 0), parent=p_e, mat_=M_PIRANHA)
    # Sharp teeth
    for ti in range(4):
        cyl(f"pir_t{pi}_{ti}", r=0.02, depth=0.06, segs=6,
            loc=(0.25, (ti-1.5)*0.02, 0), parent=p_e, mat_=M_TEETH_W)
    p_e["_phase"] = random.uniform(0, math.pi*2)

# ============ CAIMAN crocodile (signature) ============
caiman_e = empty("caiman", loc=(18, 10, 0))
caiman_e.rotation_euler = (0, 0, math.radians(-30))
# Long body
smooth_cone("ca_body", r1=0.45, r2=0.15, depth=4, segs=18, loc=(0, 0, 0.30),
            parent=caiman_e, mat_=M_CAIMAN_GREEN).rotation_euler = (0, math.radians(90), 0)
# Scales (signature spine ridges)
for sci in range(12):
    scx = -1.6 + sci * 0.30
    beveled_cube(f"ca_sc{sci}", (0.08, 0.20, 0.15), bevel_offset=0.02,
                 loc=(scx, 0, 0.45), parent=caiman_e, mat_=M_CAIMAN_DARK)
# Head with jaws
head_ca_e = empty("ca_he", (1.8, 0, 0.30), parent=caiman_e)
smooth_sphere("ca_head", r=0.40, segs=18, rings=14, loc=(0.2, 0, 0), parent=head_ca_e,
              mat_=M_CAIMAN_GREEN, scale=(1.6, 0.9, 0.55))
# Eyes raised (signature)
for side in (-1, 1):
    smooth_sphere(f"ca_eye_b{side}", r=0.10, loc=(0.05, side*0.20, 0.25),
                  parent=head_ca_e, mat_=M_CAIMAN_GREEN)
    smooth_sphere(f"ca_eye{side}", r=0.05, loc=(0.05, side*0.20, 0.30),
                  parent=head_ca_e, mat_=M_CAIMAN_EYE)
# Teeth row
for ti in range(10):
    cyl(f"ca_t{ti}", r=0.025, depth=0.10, segs=6,
        loc=(0.10 + (ti-4.5)*0.10, 0.22, 0), parent=head_ca_e, mat_=M_TEETH_W)
    cyl(f"ca_t_b{ti}", r=0.025, depth=0.10, segs=6,
        loc=(0.10 + (ti-4.5)*0.10, -0.22, 0), parent=head_ca_e, mat_=M_TEETH_W)
# Tail
tail_ca_e = empty("ca_tail", (-2.0, 0, 0.30), parent=caiman_e)
for ti2 in range(5):
    cyl(f"ca_t{ti2}", r=0.30 - ti2*0.04, depth=0.40, segs=14, loc=(-ti2*0.40, 0, 0),
        parent=tail_ca_e, mat_=M_CAIMAN_GREEN).rotation_euler = (0, math.radians(90), 0)

# ============ JAGUAR (signature spotted) ============
jaguar_e = empty("jaguar", loc=(-15, -20, 0))
jaguar_e.rotation_euler = (0, 0, math.radians(30))
# Body
smooth_sphere("jag_body", r=0.55, segs=20, rings=14, loc=(0, 0, 1.0),
              parent=jaguar_e, mat_=M_JAGUAR, scale=(1.8, 0.95, 1.0))
# Belly
smooth_sphere("jag_belly", r=0.45, loc=(0, 0, 0.85), parent=jaguar_e,
              mat_=M_JAGUAR_BELLY, scale=(1.5, 0.85, 0.5))
# SPOTS (signature)
for sp in range(40):
    spa = random.uniform(0, math.pi*2); spe = random.uniform(0, math.pi)
    spx = math.sin(spe)*math.cos(spa)*0.95
    spy = math.sin(spe)*math.sin(spa)*0.55
    spz = math.cos(spe)*0.6 + 1.0
    # Black rosette spot
    smooth_sphere(f"jag_sp{sp}", r=random.uniform(0.06, 0.10),
                  loc=(spx, spy, spz), parent=jaguar_e, mat_=M_JAGUAR_SPOT,
                  scale=(1, 1, 0.3))
# 4 legs
for x in (-1, 1):
    for y in (-1, 1):
        cyl(f"jag_l{x}{y}", r=0.10, depth=0.95, segs=10,
            loc=(x*0.50, y*0.30, 0.48), parent=jaguar_e, mat_=M_JAGUAR)
        # Spots on legs
        for sl in range(3):
            smooth_sphere(f"jag_lsp{x}{y}_{sl}", r=0.05,
                          loc=(x*0.50, y*0.30, 0.30 + sl*0.30),
                          parent=jaguar_e, mat_=M_JAGUAR_SPOT, scale=(1, 0.3, 1))
        # Paw
        smooth_sphere(f"jag_p{x}{y}", r=0.13, loc=(x*0.50, y*0.30, 0),
                      parent=jaguar_e, mat_=M_JAGUAR, scale=(1, 1.1, 0.6))
# Head
jag_head_e = empty("jag_he", (1.0, 0, 1.1), parent=jaguar_e)
smooth_sphere("jag_head", r=0.30, segs=20, rings=14, loc=(0, 0, 0),
              parent=jag_head_e, mat_=M_JAGUAR, scale=(1.2, 1.0, 1.0))
# Spots on head
for sp in range(10):
    spa = random.uniform(0, math.pi*2); spe = random.uniform(0, math.pi/2)
    smooth_sphere(f"jag_hsp{sp}", r=0.04,
                  loc=(math.sin(spe)*math.cos(spa)*0.30,
                       math.sin(spe)*math.sin(spa)*0.30,
                       math.cos(spe)*0.30),
                  parent=jag_head_e, mat_=M_JAGUAR_SPOT, scale=(1, 1, 0.3))
# Snout
smooth_sphere("jag_snout", r=0.18, loc=(0.25, 0, -0.10),
              parent=jag_head_e, mat_=M_JAGUAR_BELLY, scale=(1, 0.85, 0.7))
# Nose
smooth_sphere("jag_nose", r=0.05, loc=(0.40, 0, -0.05), parent=jag_head_e, mat_=M_JAGUAR_SPOT)
# Eyes amber glow
for side in (-1, 1):
    smooth_sphere(f"jag_eye{side}", r=0.05, loc=(0.15, side*0.15, 0.05),
                  parent=jag_head_e, mat_=M_JAGUAR_EYE)
# Ears
for side in (-1, 1):
    smooth_sphere(f"jag_ear{side}", r=0.08, loc=(-0.05, side*0.20, 0.20),
                  parent=jag_head_e, mat_=M_JAGUAR, scale=(0.7, 1, 1.2))
# Tail
tail_jag_e = empty("jag_tail", (-1.0, 0, 1.0), parent=jaguar_e)
cyl("jag_tail_b", r=0.06, depth=1.5, segs=10, loc=(0, 0, 0.40),
    parent=tail_jag_e, mat_=M_JAGUAR).rotation_euler = (math.radians(40), 0, 0)
# Tail spots
for ti in range(5):
    smooth_sphere(f"jag_tail_sp{ti}", r=0.04,
                  loc=(0, math.cos(ti*0.5)*0.10, 0.10 + ti*0.30),
                  parent=tail_jag_e, mat_=M_JAGUAR_SPOT)

# ============ 6 TOUCANS (signature rainbow beaks) ============
def make_toucan(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body black
    smooth_sphere(f"{name}_body", r=0.22, segs=18, rings=12, loc=(0, 0, 0),
                  parent=base, mat_=M_TOUCAN_BODY, scale=(1.2, 1.5, 1.0))
    # White chest signature
    smooth_sphere(f"{name}_chest", r=0.17, loc=(0, -0.08, 0),
                  parent=base, mat_=M_TOUCAN_CHEST, scale=(0.95, 0.6, 0.9))
    # Head
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=12, loc=(0, 0.25, 0.10),
                  parent=base, mat_=M_TOUCAN_BODY)
    # HUGE COLORFUL BEAK (signature)
    beak_e = empty(f"{name}_be", (0, 0.40, 0.05), parent=base)
    # Orange upper beak
    smooth_cone(f"{name}_b_up", r1=0.15, r2=0.02, depth=0.50, segs=12,
                loc=(0, 0.20, 0.04), parent=beak_e,
                mat_=M_TOUCAN_BEAK_O).rotation_euler = (math.radians(-90), 0, 0)
    # Yellow lower beak
    smooth_cone(f"{name}_b_low", r1=0.13, r2=0.02, depth=0.45, segs=12,
                loc=(0, 0.18, -0.04), parent=beak_e,
                mat_=M_TOUCAN_BEAK_Y).rotation_euler = (math.radians(-90), 0, 0)
    # Black tip
    smooth_cone(f"{name}_b_tip", r1=0.04, r2=0.005, depth=0.10, segs=8,
                loc=(0, 0.50, 0), parent=beak_e,
                mat_=M_TOUCAN_BEAK_BK).rotation_euler = (math.radians(-90), 0, 0)
    # Eye ring blue
    cyl(f"{name}_er", r=0.05, depth=0.02, segs=14, loc=(0.10, 0.10, 0.10),
        parent=base, mat_=M_TOUCAN_EYE_RING).rotation_euler = (0, math.radians(90), 0)
    smooth_sphere(f"{name}_eye", r=0.03, loc=(0.13, 0.10, 0.10),
                  parent=base, mat_=M_EYE_DARK_J)
    # Wings
    for side in (-1, 1):
        wing = beveled_cube(f"{name}_w{side}", (0.08, 0.18, 0.15), bevel_offset=0.02,
                            loc=(side*0.20, 0, 0), parent=base, mat_=M_TOUCAN_BODY)
    # Tail
    beveled_cube(f"{name}_tl", (0.20, 0.30, 0.06), bevel_offset=0.02,
                 loc=(0, -0.35, 0), parent=base, mat_=M_TOUCAN_BODY)
    # Feet
    for side in (-1, 1):
        cyl(f"{name}_ft{side}", r=0.02, depth=0.08, segs=6,
            loc=(side*0.05, 0, -0.20), parent=base, mat_=M_MACAW_YELLOW)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base}

toucans = []
toucan_pos = [(-25, -28, 12), (25, -28, 13), (-32, 5, 14), (32, 5, 13),
               (-28, 33, 12), (28, 33, 14)]
for i, (tx, ty, tz) in enumerate(toucan_pos):
    t = make_toucan(f"toucan{i}", (tx, ty, tz), scale=1.0, facing=random.uniform(0, math.pi*2))
    toucans.append(t)

# ============ 4 MONKEYS swinging ============
def make_monkey(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.25, segs=16, rings=10, loc=(0, 0, 0),
                  parent=base, mat_=M_MONKEY_BROWN, scale=(1, 1, 1.2))
    # 4 long limbs (signature hanging)
    for side_idx, side in enumerate((-1, 1)):
        # Arm
        arm_e = empty(f"{name}_a{side_idx}_e", (side*0.18, 0, 0.10), parent=base)
        arm_e.rotation_euler = (math.radians(-160), 0, math.radians(side*-20))
        cyl(f"{name}_uarm{side_idx}", r=0.04, depth=0.40, segs=8, loc=(0, 0, -0.20),
            parent=arm_e, mat_=M_MONKEY_BROWN)
        cyl(f"{name}_fa{side_idx}", r=0.035, depth=0.35, segs=8, loc=(0, 0, -0.55),
            parent=arm_e, mat_=M_MONKEY_BROWN)
        # Leg
        leg_e = empty(f"{name}_l{side_idx}_e", (side*0.12, 0, -0.20), parent=base)
        leg_e.rotation_euler = (math.radians(60), 0, 0)
        cyl(f"{name}_lp{side_idx}", r=0.04, depth=0.35, segs=8, loc=(0, 0, -0.17),
            parent=leg_e, mat_=M_MONKEY_BROWN)
    # LONG PREHENSILE TAIL (signature curling)
    tail_e = empty(f"{name}_tl_e", (0, 0, 0.25), parent=base)
    for ti in range(8):
        ta_t = ti * 0.3
        cyl(f"{name}_tl{ti}", r=0.025, depth=0.15, segs=6,
            loc=(math.sin(ta_t)*0.15, math.cos(ta_t)*0.15, ti*0.10 + 0.10),
            parent=tail_e, mat_=M_MONKEY_BROWN)
    # Head
    head_m_e = empty(f"{name}_he", (0, -0.30, 0.10), parent=base)
    smooth_sphere(f"{name}_head", r=0.16, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_MONKEY_BROWN)
    # Face lighter
    smooth_sphere(f"{name}_face", r=0.13, loc=(0, -0.05, 0),
                  parent=head_m_e, mat_=M_MONKEY_FACE, scale=(0.9, 0.5, 1))
    # Eyes (big)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04, loc=(side*0.06, -0.10, 0.04),
                      parent=head_m_e, mat_=M_EYE_DARK_J)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.06,
                      loc=(side*0.16, -0.02, 0.02), parent=head_m_e,
                      mat_=M_MONKEY_BROWN, scale=(0.5, 1, 1))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base}

monkeys = []
monkey_pos = [(-28, -30, 11), (28, -32, 12), (-32, 0, 13), (32, 38, 11)]
for i, (mx, my, mz) in enumerate(monkey_pos):
    m = make_monkey(f"monkey{i}", (mx, my, mz), scale=1.0,
                    facing=random.uniform(0, math.pi*2))
    monkeys.append(m)

# ============ 4 MACAWS perched/flying (signature rainbow parrots) ============
for mc in range(4):
    mca = (mc / 4.0) * math.pi * 2 + math.pi/8
    mcx = math.cos(mca) * 25
    mcy = math.sin(mca) * 25
    mcz = random.uniform(11, 14)
    mc_e = empty(f"macaw{mc}", (mcx, mcy, mcz))
    mc_e.rotation_euler = (0, 0, mca + math.pi)
    # Body
    smooth_sphere(f"mc_b{mc}", r=0.18, segs=16, rings=12, loc=(0, 0, 0),
                  parent=mc_e, mat_=M_MACAW_BLUE, scale=(1.2, 1.3, 1))
    # Yellow chest
    smooth_sphere(f"mc_c{mc}", r=0.13, loc=(0, -0.06, 0),
                  parent=mc_e, mat_=M_MACAW_YELLOW, scale=(0.9, 0.7, 0.9))
    # Head
    smooth_sphere(f"mc_h{mc}", r=0.13, loc=(0, 0.20, 0.08),
                  parent=mc_e, mat_=M_MACAW_BLUE)
    # Curved beak
    smooth_cone(f"mc_bk{mc}", r1=0.05, r2=0.005, depth=0.15, segs=10,
                loc=(0, 0.32, 0), parent=mc_e,
                mat_=M_TOUCAN_BEAK_BK).rotation_euler = (math.radians(-110), 0, 0)
    # Wings spread
    for side in (-1, 1):
        wing = beveled_cube(f"mc_w{mc}_{side}", (0.06, 0.40, 0.10), bevel_offset=0.02,
                            loc=(side*0.20, 0, 0), parent=mc_e, mat_=M_MACAW_BLUE)
        # Yellow wing edges
        beveled_cube(f"mc_wy{mc}_{side}", (0.06, 0.40, 0.04), bevel_offset=0.01,
                     loc=(side*0.25, 0, -0.05), parent=mc_e, mat_=M_MACAW_YELLOW)
        # Red tips
        beveled_cube(f"mc_wr{mc}_{side}", (0.04, 0.20, 0.04), bevel_offset=0.01,
                     loc=(side*0.40, -0.05, 0), parent=mc_e, mat_=M_MACAW_RED)
    # Long tail multicolor
    for tf in range(5):
        ta = (tf - 2) * 0.10
        beveled_cube(f"mc_tf{mc}_{tf}", (0.04, 0.50, 0.04), bevel_offset=0.005,
                     loc=(ta*0.05, -0.40, 0), parent=mc_e,
                     mat_=[M_MACAW_RED, M_MACAW_YELLOW, M_MACAW_BLUE, M_MACAW_RED, M_MACAW_GREEN][tf])
    mc_e["_phase"] = random.uniform(0, math.pi*2)

# ============================================================
# ⭐ 600 LEAVES + 400 FIREFLIES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
leaves_falling = []
for i in range(600):
    px = random.uniform(-70, 70)
    py = random.uniform(-70, 70)
    pz = random.uniform(1, 18)
    p = beveled_cube(f"leaf{i}", (random.uniform(0.08, 0.14),
                                    random.uniform(0.04, 0.06),
                                    random.uniform(0.12, 0.20)),
                     bevel_offset=0.02, loc=(px, py, pz),
                     mat_=random.choice(LEAF_VARIANTS))
    p["_phase"] = random.uniform(0, math.pi*2)
    p["_base_x"] = px; p["_base_y"] = py; p["_base_z"] = pz
    p["_amp_x"] = random.uniform(1.0, 2.5)
    p["_amp_y"] = random.uniform(1.0, 2.5)
    p["_speed"] = random.uniform(0.4, 1.0)
    p["_fall"] = random.uniform(1.0, 2.5)
    leaves_falling.append(p)

# 400 fireflies (signature)
fireflies = []
for i in range(400):
    px = random.uniform(-50, 50)
    py = random.uniform(-50, 50)
    pz = random.uniform(1, 10)
    fcol = random.choice(FIREFLY_COLORS)
    f_obj = smooth_sphere(f"ff{i}", r=random.uniform(0.05, 0.08), segs=8, rings=6,
                          loc=(px, py, pz), mat_=fcol)
    f_obj["_phase"] = random.uniform(0, math.pi*2)
    f_obj["_base_x"] = px; f_obj["_base_y"] = py; f_obj["_base_z"] = pz
    f_obj["_amp_x"] = random.uniform(1.0, 2.5)
    f_obj["_amp_y"] = random.uniform(1.0, 2.5)
    f_obj["_amp_z"] = random.uniform(0.5, 1.5)
    f_obj["_speed"] = random.uniform(0.6, 1.5)
    fireflies.append(f_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Jungle trees sway
for jt in jungle_trees:
    phase = jt["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        jt.rotation_euler = (math.sin(t * 0.5 + phase) * math.radians(2),
                              math.cos(t * 0.5 + phase) * math.radians(2), 0)
        jt.keyframe_insert("rotation_euler", frame=f)

# Tribe dance ritual
for tr in tribe:
    phase = tr["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        tr["root"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(5),
                                       math.cos(t * 2.5 + phase) * math.radians(5),
                                       tr["root"].rotation_euler.z)
        tr["root"].location.z = abs(math.sin(t * 3.0 + phase)) * 0.15
        tr["root"].keyframe_insert("rotation_euler", frame=f)
        tr["root"].keyframe_insert("location", frame=f)
        tr["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0,
                                     math.cos(t * 1.5 + phase) * math.radians(15))
        tr["he"].keyframe_insert("rotation_euler", frame=f)

# Maloca fire flicker
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    sc_fl = 1 + math.sin(t * 6.0) * 0.15
    fire_mal_e.scale = (1 + math.cos(t * 5.0) * 0.10, 1 + math.sin(t * 5.0) * 0.10, sc_fl)
    fire_mal_e.keyframe_insert("scale", frame=f)

# Jaguar walks slowly
phase_jag = 0
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    jaguar_e.location.x = -15 + math.sin(t * 0.5) * 1.0
    jaguar_e.location.z = abs(math.sin(t * 1.0)) * 0.05
    jaguar_e.keyframe_insert("location", frame=f)
    jag_head_e.rotation_euler = (0, 0, math.sin(t * 0.8) * math.radians(15))
    jag_head_e.keyframe_insert("rotation_euler", frame=f)

# Caiman lurks (slight body motion)
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    caiman_e.location.z = math.sin(t * 0.8) * 0.05
    caiman_e.rotation_euler = (0, 0, math.radians(-30) + math.sin(t * 0.5) * math.radians(5))
    caiman_e.keyframe_insert("location", frame=f)
    caiman_e.keyframe_insert("rotation_euler", frame=f)

# Toucans head turn + slight wing
for tc in toucans:
    phase = tc["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        tc["root"].rotation_euler = (0, math.sin(t * 1.5 + phase) * math.radians(3),
                                       tc["root"].rotation_euler.z + math.sin(t * 1.0 + phase) * math.radians(10))
        tc["root"].keyframe_insert("rotation_euler", frame=f)

# Monkeys swing
for m in monkeys:
    phase = m["root"]["_phase"]
    bz_m = m["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(15),
                                     math.cos(t * 2.0 + phase) * math.radians(10),
                                     m["root"].rotation_euler.z)
        m["root"].location.z = bz_m + math.sin(t * 1.5 + phase) * 0.50
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["root"].keyframe_insert("location", frame=f)

# Macaws fly
for mci in range(4):
    macaw = bpy.data.objects.get(f"macaw{mci}")
    if macaw is None: continue
    phase = macaw["_phase"]
    bx_mc = macaw.location.x; by_mc = macaw.location.y; bz_mc = macaw.location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        macaw.location.x = bx_mc + math.sin(t * 1.0 + phase) * 2
        macaw.location.y = by_mc + math.cos(t * 1.0 + phase) * 2
        macaw.location.z = bz_mc + math.sin(t * 1.5 + phase) * 0.5
        macaw.keyframe_insert("location", frame=f)

# 600 leaves falling
for l in leaves_falling:
    phase = l["_phase"]; speed = l["_speed"]; fall = l["_fall"]
    bx, by, bz = l["_base_x"], l["_base_y"], l["_base_z"]
    ax, ay = l["_amp_x"], l["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.3)
        if z < 0.3: z = bz
        l.location = (x, y, max(0.2, z))
        l.rotation_euler = (t * 3.0 + phase, t * 2.0 + phase, t * 4.0 + phase)
        l.keyframe_insert("location", frame=f)
        l.keyframe_insert("rotation_euler", frame=f)

# 400 fireflies twinkle + move
for f_obj in fireflies:
    phase = f_obj["_phase"]; speed = f_obj["_speed"]
    bx, by, bz = f_obj["_base_x"], f_obj["_base_y"], f_obj["_base_z"]
    ax, ay, az = f_obj["_amp_x"], f_obj["_amp_y"], f_obj["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.4 + phase)
        f_obj.location = (x, y, max(0.5, z))
        # Twinkle (signature)
        s_t = 0.5 + abs(math.sin(t * 4.0 + phase)) * 1.0
        f_obj.scale = (s_t, s_t, s_t)
        f_obj.keyframe_insert("location", frame=f)
        f_obj.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_amazon_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_amazon_jungle_tribe_river] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_amazon_jungle_tribe_river] 8 jungle giants + maloca + 6 tribe body-painted loincloths + chief shaman + bow+arrow + river + 4 canoes + 3 piranhas + caiman + jaguar spotted + 6 toucans rainbow beak + 4 monkeys + 4 macaws + 600 leaves + 400 fireflies")
print("⭐ FIXES: 1 ground + 600 leaves + 400 fireflies (signature Amazon thematic mandatory) ⭐")
