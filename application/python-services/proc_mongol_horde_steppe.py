"""
proc_mongol_horde_steppe.py — 203e procédural AuroraIA (67e qualité)
Horde mongole steppe : 6 yourtes + 30 cavaliers + chef + 8 chevaux + 30 archers + chamans + troupeau + 200 herbes + aigle
"""
import bpy, bmesh, math, random, os

random.seed(0xD05E203)

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
    if bsdf is None:
        m.node_tree.nodes.clear()
        bsdf = m.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        out = m.node_tree.nodes.new("ShaderNodeOutputMaterial")
        m.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
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

# Materials
M_SKY = mat("sky", (0.70, 0.78, 0.85, 1.0), 0.0, 0.7, emission=(0.65,0.75,0.85), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.92, 0.65, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.65), emission_strength=18.0)
M_CLOUD = mat("cloud", (0.95, 0.93, 0.92, 1.0), 0.0, 0.65, emission=(0.85,0.83,0.82), emission_strength=2.0, alpha=0.75)
M_GRASS = mat("grass", (0.45, 0.55, 0.30, 1.0), 0.0, 0.85, emission=(0.40,0.50,0.28), emission_strength=0.3)
M_GROUND = mat("ground", (0.35, 0.30, 0.22, 1.0), 0.0, 0.85)
M_DIRT = mat("dirt", (0.30, 0.22, 0.15, 1.0), 0.0, 0.85)

# Yurt (felt + wood)
M_FELT_WHITE = mat("felt_w", (0.92, 0.88, 0.78, 1.0), 0.0, 0.75, emission=(0.82,0.78,0.70), emission_strength=0.4)
M_FELT_GREY = mat("felt_g", (0.60, 0.55, 0.48, 1.0), 0.0, 0.80, emission=(0.50,0.47,0.42), emission_strength=0.3)
M_WOOD = mat("wood", (0.45, 0.30, 0.18, 1.0), 0.0, 0.75)
M_WOOD_RED = mat("wood_red", (0.65, 0.20, 0.15, 1.0), 0.0, 0.55, emission=(0.55,0.18,0.13), emission_strength=0.5)
M_ROPE = mat("rope", (0.55, 0.40, 0.25, 1.0), 0.0, 0.80)

# Mongol
M_SKIN_MONGOL = mat("skin_m", (0.85, 0.65, 0.45, 1.0), 0.0, 0.60, emission=(0.75,0.55,0.38), emission_strength=0.3)
M_HAIR_BLACK = mat("hair", (0.05, 0.05, 0.05, 1.0), 0.0, 0.85)
M_BEARD_DARK = mat("beard", (0.10, 0.08, 0.05, 1.0), 0.0, 0.85)

# Armor / clothing
M_DEEL_BLUE = mat("deel_blue", (0.20, 0.30, 0.55, 1.0), 0.0, 0.55, emission=(0.18,0.28,0.50), emission_strength=0.4)
M_DEEL_RED = mat("deel_red", (0.60, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.55,0.18,0.15), emission_strength=0.5)
M_DEEL_GREEN = mat("deel_green", (0.20, 0.45, 0.25, 1.0), 0.0, 0.55, emission=(0.18,0.40,0.22), emission_strength=0.4)
M_DEEL_BROWN = mat("deel_brown", (0.40, 0.25, 0.15, 1.0), 0.0, 0.60, emission=(0.35,0.22,0.13), emission_strength=0.3)
M_ARMOR_LAQ = mat("armor_laq", (0.45, 0.35, 0.18, 1.0), 0.5, 0.40, emission=(0.40,0.30,0.15), emission_strength=0.5)
M_ARMOR_GOLD = mat("armor_g", (0.92, 0.75, 0.30, 1.0), 0.90, 0.20, emission=(0.85,0.68,0.28), emission_strength=0.8)
M_SASH = mat("sash", (0.85, 0.65, 0.25, 1.0), 0.3, 0.45, emission=(0.78,0.58,0.22), emission_strength=0.7)

# Boots
M_BOOT_LEATHER = mat("boot", (0.25, 0.15, 0.08, 1.0), 0.0, 0.75)

# Helmet
M_HELMET_MONGOL = mat("helmet_m", (0.55, 0.55, 0.58, 1.0), 0.90, 0.30, emission=(0.45,0.45,0.50), emission_strength=0.4)
M_HELMET_LAQ = mat("helmet_laq", (0.45, 0.30, 0.18, 1.0), 0.5, 0.40, emission=(0.40,0.28,0.15), emission_strength=0.5)
M_HELMET_GOLD = mat("helmet_g", (0.92, 0.75, 0.30, 1.0), 0.90, 0.20, emission=(0.85,0.70,0.28), emission_strength=0.9)

# Weapons
M_BOW = mat("bow", (0.55, 0.30, 0.15, 1.0), 0.3, 0.55, emission=(0.50,0.28,0.13), emission_strength=0.5)
M_ARROW_SHAFT = mat("arrow_s", (0.50, 0.35, 0.20, 1.0), 0.0, 0.70)
M_ARROW_TIP = mat("arrow_t", (0.55, 0.55, 0.58, 1.0), 0.92, 0.30, emission=(0.50,0.50,0.55), emission_strength=0.5)
M_FEATHER = mat("feather", (0.95, 0.90, 0.80, 1.0), 0.0, 0.55, emission=(0.85,0.82,0.75), emission_strength=0.4)
M_SABER = mat("saber", (0.85, 0.90, 0.95, 1.0), 0.95, 0.10, emission=(0.80,0.85,0.92), emission_strength=0.8)
M_QUIVER = mat("quiver", (0.40, 0.25, 0.15, 1.0), 0.0, 0.65, emission=(0.35,0.22,0.13), emission_strength=0.3)

# Horse
M_HORSE_BROWN = mat("horse_br", (0.45, 0.28, 0.18, 1.0), 0.0, 0.60, emission=(0.40,0.25,0.15), emission_strength=0.4)
M_HORSE_BLACK = mat("horse_bk", (0.10, 0.08, 0.06, 1.0), 0.0, 0.65, emission=(0.10,0.08,0.06), emission_strength=0.3)
M_HORSE_WHITE = mat("horse_w", (0.92, 0.88, 0.80, 1.0), 0.0, 0.55, emission=(0.85,0.80,0.72), emission_strength=0.5)
M_HORSE_GREY = mat("horse_g", (0.60, 0.55, 0.50, 1.0), 0.0, 0.60, emission=(0.55,0.50,0.45), emission_strength=0.4)
M_MANE_BLACK = mat("mane", (0.08, 0.06, 0.04, 1.0), 0.0, 0.80)
M_HOOF = mat("hoof", (0.18, 0.12, 0.08, 1.0), 0.4, 0.55)
M_SADDLE = mat("saddle", (0.55, 0.35, 0.20, 1.0), 0.0, 0.65, emission=(0.50,0.32,0.18), emission_strength=0.4)
M_SADDLE_GOLD = mat("saddle_g", (0.92, 0.75, 0.30, 1.0), 0.90, 0.20, emission=(0.85,0.68,0.25), emission_strength=0.8)

# Yak (chief mount)
M_YAK = mat("yak", (0.18, 0.10, 0.05, 1.0), 0.0, 0.90, emission=(0.18,0.10,0.05), emission_strength=0.2)
M_YAK_HORN = mat("yak_horn", (0.85, 0.78, 0.65, 1.0), 0.4, 0.45, emission=(0.75,0.70,0.58), emission_strength=0.4)

# Banner
M_BANNER_YELLOW = mat("banner_y", (0.92, 0.82, 0.20, 1.0), 0.3, 0.40, emission=(0.85,0.75,0.20), emission_strength=1.2)
M_BANNER_RED = mat("banner_r", (0.65, 0.15, 0.15, 1.0), 0.0, 0.50, emission=(0.58,0.15,0.13), emission_strength=0.6)
M_BANNER_BLACK_INSIGNIA = mat("banner_ins", (0.05, 0.05, 0.05, 1.0), 0.0, 0.5, emission=(0.10,0.10,0.10), emission_strength=0.4)

# Fire
M_FLAME = mat("flame", (1.0, 0.50, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.55,0.15), emission_strength=14.0)
M_FLAME_INNER = mat("flame_in", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.90,0.40), emission_strength=20.0)
M_EMBER = mat("ember", (1.0, 0.30, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.35,0.15), emission_strength=10.0)
M_LOG = mat("log", (0.30, 0.18, 0.10, 1.0), 0.0, 0.80)

# Shaman
M_SHAMAN_ROBE = mat("sham_robe", (0.40, 0.20, 0.30, 1.0), 0.0, 0.60, emission=(0.35,0.18,0.28), emission_strength=0.5)
M_SHAMAN_FEATHER = mat("sham_f_red", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.78,0.18,0.15), emission_strength=0.7)
M_SHAMAN_FEATHER2 = mat("sham_f_yellow", (0.92, 0.78, 0.20, 1.0), 0.0, 0.55, emission=(0.85,0.72,0.20), emission_strength=0.8)
M_SHAMAN_BONE = mat("sham_bone", (0.92, 0.88, 0.78, 1.0), 0.0, 0.55, emission=(0.85,0.82,0.72), emission_strength=0.4)
M_DRUM = mat("drum", (0.55, 0.35, 0.20, 1.0), 0.0, 0.65, emission=(0.45,0.28,0.15), emission_strength=0.4)
M_DRUM_SKIN = mat("drum_skin", (0.95, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.60), emission_strength=0.4)

# Sheep
M_SHEEP_WOOL = mat("sheep", (0.95, 0.92, 0.85, 1.0), 0.0, 0.85, emission=(0.85,0.82,0.78), emission_strength=0.4)
M_SHEEP_HEAD = mat("sheep_head", (0.55, 0.45, 0.35, 1.0), 0.0, 0.75, emission=(0.45,0.38,0.28), emission_strength=0.3)
M_SHEEP_BLACK = mat("sheep_bk", (0.10, 0.08, 0.06, 1.0), 0.0, 0.85)

# Dog
M_DOG_NOMAD = mat("dog_n", (0.45, 0.30, 0.18, 1.0), 0.0, 0.65, emission=(0.40,0.25,0.15), emission_strength=0.3)
M_DOG_EYE = mat("dog_eye", (1.0, 0.85, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.30), emission_strength=3.0)

# Eagle
M_EAGLE = mat("eagle", (0.30, 0.20, 0.15, 1.0), 0.0, 0.55, emission=(0.25,0.18,0.13), emission_strength=0.4)
M_EAGLE_HEAD = mat("eagle_h", (0.85, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.75,0.70,0.58), emission_strength=0.5)
M_EAGLE_BEAK = mat("eagle_b", (0.85, 0.55, 0.20, 1.0), 0.0, 0.50, emission=(0.78,0.50,0.18), emission_strength=0.6)
M_EAGLE_EYE = mat("eagle_eye", (1.0, 0.60, 0.10, 1.0), 0.0, 0.15, emission=(1.0,0.60,0.10), emission_strength=8.0)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=95, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.60))
sky.scale = (1,1,0.60)
sun = smooth_sphere("sun", r=4.0, loc=(15, 35, 22), mat_=M_SUN)
# 10 clouds drift (signature steppe open sky)
clouds = []
for i in range(10):
    a = (i / 10.0) * math.pi * 2 + random.uniform(-0.1, 0.1)
    rad = random.uniform(20, 32)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(14, 22)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.0, 3.5),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ GROUND ============
ground = beveled_cube("ground", (70, 70, 0.4), bevel_offset=0.05, loc=(0, 0, -0.2), mat_=M_GROUND)
# Dirt path circle around camp center
for i in range(36):
    a = (i / 36.0) * math.pi * 2
    smooth_sphere(f"dirt{i}", r=0.35, loc=(8*math.cos(a), 8*math.sin(a), 0.05),
                  mat_=M_DIRT, scale=(1, 1, 0.15))
# Grass patches (40)
for i in range(40):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(10, 30)
    smooth_sphere(f"grass_p{i}", r=random.uniform(0.4, 0.9),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_GRASS, scale=(1, 1, 0.18))

# ============ 6 YOURTES (yurts traditionnelles mongoles) ============
def make_yurt(name, loc, scale=1.0):
    base = empty(name, loc)
    # Bottom cylindrical wall (felt over wood lattice)
    cyl(f"{name}_body", r=1.8*scale, depth=1.6*scale, segs=24,
        loc=(0, 0, 0.8*scale), parent=base, mat_=M_FELT_WHITE)
    # Wood lattice rings visible (3)
    for i in range(3):
        cyl(f"{name}_lat{i}", r=1.82*scale, depth=0.06*scale, segs=24,
            loc=(0, 0, 0.3 + i*0.55), parent=base, mat_=M_WOOD)
    # Conical roof (signature yourt)
    smooth_cone(f"{name}_roof", r1=1.85*scale, r2=0.20*scale, depth=1.4*scale, segs=24,
                loc=(0, 0, 2.3*scale), parent=base, mat_=M_FELT_GREY)
    # Smoke hole (small disk on top with hole - representational)
    cyl(f"{name}_smokehole", r=0.30*scale, depth=0.10, segs=18,
        loc=(0, 0, 3.0*scale), parent=base, mat_=M_WOOD_RED)
    # Smoke (subtle)
    smooth_sphere(f"{name}_smoke", r=0.30, loc=(0, 0, 3.5*scale),
                  parent=base, mat_=M_CLOUD)
    # Door (orange/red painted door front, signature)
    beveled_cube(f"{name}_door", (0.50*scale, 0.05*scale, 1.0*scale),
                 loc=(0, -1.85*scale, 0.5*scale), parent=base, mat_=M_WOOD_RED)
    # Door frame
    for side in (-1, 1):
        beveled_cube(f"{name}_doorframe_{side}", (0.08*scale, 0.08*scale, 1.1*scale),
                     loc=(side*0.30*scale, -1.85*scale, 0.55*scale), parent=base, mat_=M_WOOD_RED)
    beveled_cube(f"{name}_doortop", (0.66*scale, 0.08*scale, 0.08*scale),
                 loc=(0, -1.85*scale, 1.05*scale), parent=base, mat_=M_WOOD_RED)
    # Roof ropes (3 visible)
    for i in range(3):
        a = (i / 3.0) * math.pi * 2 + 0.4
        cyl(f"{name}_rope{i}", r=0.025*scale, depth=1.5*scale, segs=6,
            loc=(0.9*math.cos(a)*scale, 0.9*math.sin(a)*scale, 2.0*scale),
            parent=base, mat_=M_ROPE).rotation_euler = (math.radians(45), 0, a)
    return base

yurts = []
yurt_positions = [(8, 8), (-8, 8), (8, -8), (-8, -8), (0, 12), (0, -12)]
for i, (yx, yy) in enumerate(yurt_positions):
    yu = make_yurt(f"yurt{i}", (yx, yy, 0), scale=random.uniform(0.95, 1.15))
    yu.rotation_euler = (0, 0, math.atan2(-yy, -yx) + math.pi/2)
    yurts.append(yu)

# ============ FEU CAMP CENTRAL ============
campfire_e = empty("campfire", loc=(0, 0, 0))
# Stone ring (6 stones)
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    smooth_sphere(f"camp_stone{i}", r=0.30,
                  loc=(1.0*math.cos(a), 1.0*math.sin(a), 0.20),
                  parent=campfire_e, mat_=M_GROUND)
# 4 logs crossed
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    log = cyl(f"camp_log{i}", r=0.15, depth=1.8, segs=12,
             loc=(0.08*math.cos(a), 0.08*math.sin(a), 0.30),
             parent=campfire_e, mat_=M_LOG)
    log.rotation_euler = (math.radians(90), 0, a)
# 6 flames
flames = []
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    rad = random.uniform(0.20, 0.45)
    fx = rad * math.cos(a)
    fy = rad * math.sin(a)
    outer = smooth_cone(f"camp_fl_o{i}", r1=0.25, r2=0.02, depth=0.95, segs=10,
                       loc=(fx, fy, 0.75), parent=campfire_e, mat_=M_FLAME)
    inner = smooth_cone(f"camp_fl_i{i}", r1=0.15, r2=0.01, depth=0.7, segs=10,
                       loc=(fx, fy, 0.80), parent=campfire_e, mat_=M_FLAME_INNER)
    outer["_phase"] = i * 0.5
    inner["_phase"] = i * 0.5 + 0.3
    flames.append((outer, inner))
# Embers (5)
embers = []
for i in range(5):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(0.10, 0.40)
    e = smooth_sphere(f"camp_ember{i}", r=0.04,
                     loc=(rad*math.cos(a), rad*math.sin(a),
                          random.uniform(0.10, 0.50)),
                     parent=campfire_e, mat_=M_EMBER)
    e["_phase"] = random.uniform(0, math.pi*2)
    embers.append(e)

# ============ HORSE constructor ============
def make_horse(name, loc, color_mat, mane_mat=M_MANE_BLACK, has_saddle=False, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.55*scale, segs=22, rings=14, loc=(0, 0, 1.4*scale),
                  parent=base, mat_=color_mat, scale=(2.2, 1.0, 1.0))
    # Neck (curved)
    neck_e = empty(f"{name}_neck_e", (1.0*scale, 0, 1.5*scale), parent=base)
    for i in range(3):
        cyl(f"{name}_neck{i}", r=(0.20 - i*0.02)*scale, depth=0.35*scale, segs=12,
            loc=(i*0.18*scale, 0, 0.20*scale + i*0.08*scale), parent=neck_e, mat_=color_mat)
    # Head
    head_e = empty(f"{name}_head_e", (1.6*scale, 0, 1.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.22*scale, segs=20, rings=14, loc=(0,0,0),
                  parent=head_e, mat_=color_mat, scale=(1.5, 0.85, 0.8))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.13*scale, loc=(0.18*scale, 0, -0.06*scale),
                  parent=head_e, mat_=color_mat)
    # Ears
    for side in (-1, 1):
        smooth_cone(f"{name}_ear_{side}", r1=0.05*scale, r2=0.005, depth=0.15*scale, segs=8,
                    loc=(0, side*0.10*scale, 0.15*scale), parent=head_e, mat_=color_mat).rotation_euler = (math.radians(-10), math.radians(side*15), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.035*scale,
                      loc=(0.12*scale, side*0.12*scale, 0.05*scale), parent=head_e,
                      mat_=mat(f"{name}_e_b", (0.05,0.05,0.05,1), 0, 0.3))
    # Mane (5 chunks)
    for i in range(5):
        smooth_sphere(f"{name}_mane{i}", r=(0.10 - i*0.01)*scale,
                      loc=((0.80 - i*0.15)*scale, 0, (1.70 - i*0.05)*scale), parent=base,
                      mat_=mane_mat, scale=(1, 1.5, 1.2))
    # 4 LEGS (galloping pose - alternate forward/back)
    leg_data = [
        ((-0.5, -0.4), 0.15),    # front left
        ((-0.5, 0.4), -0.15),    # front right
        ((0.5, -0.4), -0.15),    # back left
        ((0.5, 0.4), 0.15),      # back right
    ]
    legs_e = []
    for li, ((x, y), rx) in enumerate(leg_data):
        leg_e = empty(f"{name}_leg_e{li}", (x*scale, y*scale, 0.7*scale), parent=base)
        leg_e.rotation_euler = (math.radians(rx*100), 0, 0)
        legs_e.append(leg_e)
        cyl(f"{name}_leg{li}", r=0.08*scale, depth=0.75*scale, segs=10,
            loc=(0, 0, -0.40*scale), parent=leg_e, mat_=color_mat)
        # Hoof
        cyl(f"{name}_hoof{li}", r=0.09*scale, depth=0.08*scale, segs=10,
            loc=(0, 0, -0.80*scale), parent=leg_e, mat_=M_HOOF)
    # Tail (long)
    for i in range(5):
        cyl(f"{name}_tail{i}", r=(0.08-i*0.01)*scale, depth=0.20*scale, segs=10,
            loc=(-1.2*scale - i*0.10*scale, 0, 1.30*scale - i*0.06*scale), parent=base, mat_=mane_mat)

    # SADDLE if rider
    if has_saddle:
        beveled_cube(f"{name}_saddle", (0.65*scale, 0.45*scale, 0.20*scale), bevel_offset=0.04,
                     loc=(-0.2*scale, 0, 2.0*scale), parent=base, mat_=M_SADDLE)
        # Pommel
        smooth_sphere(f"{name}_pommel", r=0.10*scale, loc=(0.20*scale, 0, 2.18*scale),
                      parent=base, mat_=M_SADDLE_GOLD)
        # Cantle
        smooth_sphere(f"{name}_cantle", r=0.10*scale, loc=(-0.55*scale, 0, 2.18*scale),
                      parent=base, mat_=M_SADDLE_GOLD)
        # Bridle
        cyl(f"{name}_bridle", r=0.02*scale, depth=0.30*scale, segs=8,
            loc=(1.55*scale, 0, 1.95*scale), parent=base, mat_=M_BOOT_LEATHER)
    return {"root": base, "head_e": head_e, "legs_e": legs_e}

# ============ MONGOL WARRIOR constructor ============
def make_mongol(name, loc, deel_mat, has_helmet=True, helmet_mat=M_HELMET_LAQ,
                action="ride", on_horse=False, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    z_off = 0 if not on_horse else 1.8*scale
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg{side_idx}", r=0.11*scale, depth=0.85*scale, segs=10,
            loc=(side*0.14*scale, 0, (0.42 + z_off)*scale), parent=base, mat_=M_DEEL_BROWN)
        # Boot
        beveled_cube(f"{name}_boot{side_idx}", (0.18*scale, 0.28*scale, 0.18*scale),
                     loc=(side*0.14*scale, 0.05*scale, (0.10 + z_off)*scale),
                     parent=base, mat_=M_BOOT_LEATHER)
    # Torso (deel - traditional robe)
    beveled_cube(f"{name}_torso", (0.55*scale, 0.32*scale, 0.85*scale), bevel_offset=0.05,
                 loc=(0, 0, (1.30 + z_off)*scale), parent=base, mat_=deel_mat)
    # Belt sash gold
    beveled_cube(f"{name}_sash", (0.62*scale, 0.36*scale, 0.12*scale),
                 loc=(0, 0, (0.92 + z_off)*scale), parent=base, mat_=M_SASH)
    # Armor laquered (some warriors)
    if action in ("ride", "fight"):
        # Chest armor plate
        beveled_cube(f"{name}_armor", (0.45*scale, 0.18*scale, 0.65*scale), bevel_offset=0.03,
                     loc=(0, -0.20*scale, (1.40 + z_off)*scale), parent=base, mat_=M_ARMOR_LAQ)
        # 4 plate rows visible
        for i in range(4):
            beveled_cube(f"{name}_pl{i}", (0.50*scale, 0.04*scale, 0.10*scale),
                         loc=(0, -0.22*scale, (1.00 + z_off + i*0.20)*scale),
                         parent=base, mat_=M_ARMOR_GOLD)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, (1.90 + z_off)*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.20*scale, segs=20, rings=14, loc=(0,0,0),
                  parent=head_e, mat_=M_SKIN_MONGOL)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.025*scale,
                      loc=(side*0.07*scale, -0.16*scale, 0.03*scale), parent=head_e,
                      mat_=mat(f"{name}_ew", (0.05,0.05,0.05,1), 0, 0.3))
    # Nose
    smooth_sphere(f"{name}_nose", r=0.04*scale, loc=(0, -0.18*scale, -0.04*scale),
                  parent=head_e, mat_=M_SKIN_MONGOL)
    # Mouth
    beveled_cube(f"{name}_mouth", (0.08*scale, 0.02*scale, 0.02*scale),
                 loc=(0, -0.18*scale, -0.13*scale), parent=head_e, mat_=M_BEARD_DARK)
    # Hair black + braided behind
    smooth_sphere(f"{name}_hair", r=0.22*scale, loc=(0, 0.05*scale, 0.05*scale),
                  parent=head_e, mat_=M_HAIR_BLACK, scale=(1.05, 0.95, 0.7))
    # Long braid behind
    cyl(f"{name}_braid", r=0.04*scale, depth=0.40*scale, segs=8,
        loc=(0, 0.25*scale, -0.10*scale), parent=head_e, mat_=M_HAIR_BLACK)
    # Beard (sparse mongol style)
    smooth_sphere(f"{name}_beard", r=0.08*scale, loc=(0, -0.10*scale, -0.22*scale),
                  parent=head_e, mat_=M_BEARD_DARK, scale=(1.2, 0.5, 0.8))
    # HELMET (conical Mongol helmet signature)
    if has_helmet:
        helm_e = empty(f"{name}_helm_e", (0, 0, 0.20*scale), parent=head_e)
        smooth_cone(f"{name}_helm_body", r1=0.22*scale, r2=0.04*scale, depth=0.30*scale, segs=14,
                    loc=(0, 0, 0.15*scale), parent=helm_e, mat_=helmet_mat)
        # Brim
        cyl(f"{name}_helm_brim", r=0.24*scale, depth=0.04*scale, segs=16,
            loc=(0, 0, 0), parent=helm_e, mat_=helmet_mat)
        # Spike top (signature)
        smooth_cone(f"{name}_helm_spike", r1=0.04*scale, r2=0.005, depth=0.15*scale, segs=8,
                    loc=(0, 0, 0.38*scale), parent=helm_e, mat_=helmet_mat)
        # Top decorative ball
        smooth_sphere(f"{name}_helm_ball", r=0.03*scale, loc=(0, 0, 0.50*scale),
                      parent=helm_e, mat_=M_ARMOR_GOLD)
        # Side flaps (cheek guards)
        for side in (-1, 1):
            flap = beveled_cube(f"{name}_helm_flap{side}", (0.04*scale, 0.18*scale, 0.20*scale),
                               loc=(side*0.20*scale, 0, -0.15*scale), parent=helm_e, mat_=helmet_mat)
            flap.rotation_euler = (0, math.radians(side*5), 0)

    # ARMS (action-dependent)
    arms_pose = {
        "ride": [(math.radians(-50), -10), (math.radians(-50), 10)],
        "fight": [(math.radians(-140), -15), (math.radians(-80), 30)],
        "draw_bow": [(math.radians(-90), -40), (math.radians(-90), -20)],
        "rest": [(math.radians(-15), 0), (math.radians(-15), 0)],
        "drum": [(math.radians(-90), -25), (math.radians(-90), 25)],
        "throne": [(math.radians(-30), -10), (math.radians(-30), 10)],
    }
    pose = arms_pose.get(action, arms_pose["ride"])
    arms_e = {}
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, (1.75 + z_off)*scale), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15 + rz))
        cyl(f"{name}_up{side_idx}", r=0.08*scale, depth=0.38*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=deel_mat)
        el = empty(f"{name}_el{side_idx}", (0, 0, -0.40*scale), parent=sh)
        el.rotation_euler = (math.radians(30 if side == -1 else 40), 0, 0)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.36*scale, segs=10,
            loc=(0, 0, -0.18*scale), parent=el, mat_=M_SKIN_MONGOL)
        hand = empty(f"{name}_hand{side_idx}", (0, 0, -0.40*scale), parent=el)
        smooth_sphere(f"{name}_hand_g{side_idx}", r=0.07*scale, loc=(0,0,0),
                      parent=hand, mat_=M_SKIN_MONGOL)
        arms_e[f"sh{side_idx}"] = sh
        arms_e[f"hand{side_idx}"] = hand

    # Weapon based on action
    if action == "fight":
        # SABER right hand
        saber_e = empty(f"{name}_saber_e", (0, 0, -0.05*scale), parent=arms_e["hand1"])
        cyl(f"{name}_saber_h", r=0.025*scale, depth=0.15*scale, segs=10,
            loc=(0, 0, -0.08*scale), parent=saber_e, mat_=M_BOOT_LEATHER)
        # Curved blade (saber/scimitar)
        cyl(f"{name}_saber_b", r=0.025*scale, depth=0.7*scale, segs=10,
            loc=(0, 0, 0.30*scale), parent=saber_e, mat_=M_SABER)
        smooth_cone(f"{name}_saber_t", r1=0.025*scale, r2=0.005, depth=0.15*scale, segs=8,
                    loc=(0, 0, 0.72*scale), parent=saber_e, mat_=M_SABER)
    elif action == "draw_bow":
        # BOW + ARROW
        # Left hand holds bow
        bow_e = empty(f"{name}_bow_e", (0, 0, -0.10*scale), parent=arms_e["hand0"])
        for side in (-1, 1):
            seg = smooth_cone(f"{name}_bow_s_{side}", r1=0.03*scale, r2=0.015*scale,
                             depth=0.5*scale, segs=10,
                             loc=(0, side*0.20*scale, 0), parent=bow_e, mat_=M_BOW)
            seg.rotation_euler = (math.radians(side*30), 0, 0)
        # String
        cyl(f"{name}_bow_str", r=0.005*scale, depth=0.85*scale, segs=4,
            loc=(0.05*scale, 0, 0), parent=bow_e, mat_=M_ROPE)
        # Arrow drawn
        cyl(f"{name}_arrow_shaft", r=0.015*scale, depth=0.55*scale, segs=8,
            loc=(0.20*scale, 0, 0), parent=bow_e, mat_=M_ARROW_SHAFT).rotation_euler = (0, math.radians(90), 0)
        smooth_cone(f"{name}_arrow_tip", r1=0.025*scale, r2=0.005, depth=0.08*scale, segs=8,
                    loc=(0.50*scale, 0, 0), parent=bow_e, mat_=M_ARROW_TIP).rotation_euler = (0, math.radians(90), 0)
        # Feather fletching
        for fi in range(3):
            a_f = (fi / 3.0) * math.pi * 2
            beveled_cube(f"{name}_arrow_feather{fi}", (0.05*scale, 0.02*scale, 0.10*scale),
                         loc=(-0.10*scale, 0.04*math.cos(a_f)*scale, 0.04*math.sin(a_f)*scale),
                         parent=bow_e, mat_=M_FEATHER)

    # QUIVER on back if archer
    if action in ("draw_bow", "ride"):
        quiv_e = empty(f"{name}_quiv_e", (0, 0.25*scale, (1.55 + z_off)*scale), parent=base)
        cyl(f"{name}_quiv", r=0.10*scale, depth=0.55*scale, segs=12,
            loc=(0, 0, 0), parent=quiv_e, mat_=M_QUIVER)
        # 5 arrow shafts sticking out
        for ai in range(5):
            a2 = (ai / 5.0) * math.pi * 2
            cyl(f"{name}_quiv_arr{ai}", r=0.012*scale, depth=0.30*scale, segs=6,
                loc=(0.04*math.cos(a2)*scale, 0.04*math.sin(a2)*scale, 0.35*scale),
                parent=quiv_e, mat_=M_ARROW_SHAFT)
            # Tiny feathers
            beveled_cube(f"{name}_quiv_f{ai}", (0.04*scale, 0.04*scale, 0.06*scale),
                         loc=(0.04*math.cos(a2)*scale, 0.04*math.sin(a2)*scale, 0.50*scale),
                         parent=quiv_e, mat_=M_FEATHER)

    return {"root": base, "head_e": head_e, "sh0": arms_e["sh0"], "sh1": arms_e["sh1"]}

# ============ 8 HORSES GALLOPING + 8 CAVALIERS RIDERS ============
horses = []
riders = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = 16 + random.uniform(-1, 1)
    hx = rad * math.cos(a)
    hy = rad * math.sin(a)
    facing = a + math.pi/2  # tangent to circle
    color_choice = random.choice([M_HORSE_BROWN, M_HORSE_BLACK, M_HORSE_WHITE, M_HORSE_GREY])
    h = make_horse(f"horse{i}", (hx, hy, 0), color_choice, has_saddle=True, facing=facing)
    horses.append(h)
    # Rider on horse
    rider_actions = ["draw_bow", "fight", "ride"]
    act = rider_actions[i % 3]
    deel_choice = random.choice([M_DEEL_BLUE, M_DEEL_RED, M_DEEL_GREEN, M_DEEL_BROWN])
    r = make_mongol(f"rider{i}", (hx, hy, 0), deel_choice,
                    has_helmet=True, helmet_mat=M_HELMET_LAQ,
                    action=act, on_horse=True, facing=facing)
    riders.append(r)

# ============ 22 ADDITIONAL FOOT WARRIORS/ARCHERS (around camp) ============
foot_warriors = []
for i in range(22):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(4, 20)
    fx = rad * math.cos(a)
    fy = rad * math.sin(a)
    # Avoid yurts (rad 8 mostly)
    if abs(rad - 8) < 2.5:
        rad = 12 + random.uniform(0, 4)
        fx = rad * math.cos(a)
        fy = rad * math.sin(a)
    facing = random.uniform(0, math.pi*2)
    actions = ["draw_bow", "fight", "rest", "ride"]
    act = random.choice(actions)
    deel_choice = random.choice([M_DEEL_BLUE, M_DEEL_RED, M_DEEL_GREEN, M_DEEL_BROWN])
    helm_choice = random.choice([M_HELMET_LAQ, M_HELMET_MONGOL])
    w = make_mongol(f"foot{i}", (fx, fy, 0), deel_choice,
                    has_helmet=(random.random() < 0.7),
                    helmet_mat=helm_choice,
                    action=act, on_horse=False, facing=facing)
    foot_warriors.append(w)

# ============ YAK (chief's mount) ============
yak_base = empty("yak", loc=(0, 4, 0))
yak_base.rotation_euler = (0, 0, math.radians(0))
# Body massive (yak is huge)
smooth_sphere("yak_body", r=0.85, segs=24, rings=16, loc=(0, 0, 1.6),
              parent=yak_base, mat_=M_YAK, scale=(2.3, 1.2, 1.0))
# Lower body fur (long hanging hair)
smooth_sphere("yak_belly_fur", r=0.95, loc=(0, 0, 1.0),
              parent=yak_base, mat_=M_YAK, scale=(2.2, 1.4, 0.5))
# Head
yak_head_e = empty("yak_head_e", (1.6, 0, 1.8), parent=yak_base)
smooth_sphere("yak_head", r=0.40, segs=22, rings=14, loc=(0,0,0),
              parent=yak_head_e, mat_=M_YAK, scale=(1.4, 0.95, 0.85))
# Snout
smooth_sphere("yak_snout", r=0.22, loc=(0.30, 0, -0.10),
              parent=yak_head_e, mat_=M_SKIN_MONGOL)
# 2 HORNS curved (signature yak)
for side in (-1, 1):
    horn_e = empty(f"yak_horn_e{side}", (0, side*0.20, 0.30), parent=yak_head_e)
    horn_e.rotation_euler = (math.radians(-20), math.radians(side*25), 0)
    for s in range(3):
        seg = smooth_cone(f"yak_horn{side}_{s}", r1=0.07 - s*0.015, r2=0.05 - s*0.015,
                          depth=0.18, segs=10,
                          loc=(0, side*0.10*s, s*0.15),
                          parent=horn_e, mat_=M_YAK_HORN)
        seg.rotation_euler = (math.radians(-20*s), 0, 0)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"yak_eye_{side}", r=0.05, loc=(0.20, side*0.18, 0.10),
                  parent=yak_head_e, mat_=mat(f"yak_ew_{side}", (0.05,0.05,0.05,1), 0, 0.3))
# 4 LEGS short
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"yak_leg{x_idx}{y_idx}", r=0.15, depth=1.0, segs=12,
            loc=(x*0.55, y*0.45, 0.55), parent=yak_base, mat_=M_YAK)
        cyl(f"yak_hoof{x_idx}{y_idx}", r=0.17, depth=0.08, segs=12,
            loc=(x*0.55, y*0.45, 0.04), parent=yak_base, mat_=M_HOOF)
# Tail
for i in range(3):
    smooth_sphere(f"yak_tail{i}", r=0.12 - i*0.02,
                  loc=(-1.6 - i*0.15, 0, 1.50 - i*0.10), parent=yak_base, mat_=M_YAK,
                  scale=(1, 1.4, 1))
# Saddle ornate on yak (chief mount)
beveled_cube("yak_saddle", (0.85, 0.65, 0.25), bevel_offset=0.04,
             loc=(-0.20, 0, 2.30), parent=yak_base, mat_=M_SADDLE_GOLD)
beveled_cube("yak_saddle_red", (0.95, 0.75, 0.05), loc=(-0.20, 0, 2.45),
             parent=yak_base, mat_=M_BANNER_RED)

# ============ CHEF (GENGIS KHAN sur yak) ============
chef = make_mongol("chef_khan", (0, 4, 0), M_DEEL_RED,
                   has_helmet=True, helmet_mat=M_HELMET_GOLD,
                   action="throne", on_horse=True, scale=1.25)
# Larger fur cape (signature chief)
smooth_sphere("chef_fur", r=0.35, loc=(0, 0.10, 1.75),
              parent=chef["root"], mat_=M_YAK, scale=(1.8, 0.9, 1.0))
# Hold spear/staff in right hand
staff_e = empty("chef_staff_e", (0.30, 0, 1.0), parent=chef["sh1"])
cyl("chef_staff", r=0.05, depth=2.5, segs=12,
    loc=(0, 0, 0.5), parent=staff_e, mat_=M_WOOD)
# Banner attached to staff (yellow with insignia)
beveled_cube("chef_banner", (0.05, 0.55, 0.85), bevel_offset=0.04,
             loc=(0.03, 0, 1.50), parent=staff_e, mat_=M_BANNER_YELLOW)
# Black insignia on banner
beveled_cube("chef_banner_ins", (0.06, 0.20, 0.30), loc=(0.04, 0, 1.50),
             parent=staff_e, mat_=M_BANNER_BLACK_INSIGNIA)

# ============ BANNER POLE central (large camp banner) ============
banner_pole_e = empty("banner_pole", loc=(3, 0, 0))
cyl("banner_pole", r=0.08, depth=5.5, segs=12,
    loc=(0, 0, 2.75), parent=banner_pole_e, mat_=M_WOOD)
# Cross bar
beveled_cube("banner_cross", (0.08, 1.5, 0.08), loc=(0, 0, 5.0),
             parent=banner_pole_e, mat_=M_WOOD)
# Banner large yellow
banner_main = beveled_cube("banner_main", (0.10, 1.4, 1.6), bevel_offset=0.04,
                            loc=(0.03, 0, 4.2), parent=banner_pole_e, mat_=M_BANNER_YELLOW)
# Insignia (Tchakra-like 9-pointed)
for i in range(9):
    a = (i / 9.0) * math.pi * 2
    smooth_sphere(f"banner_ins{i}", r=0.10,
                  loc=(0.05, 0.40*math.cos(a), 4.2 + 0.40*math.sin(a)),
                  parent=banner_pole_e, mat_=M_BANNER_BLACK_INSIGNIA)
# 4 horsetails hanging (signature mongol banner)
for i in range(4):
    hori_e = empty(f"horsetail_e{i}", (0.03, (i-1.5)*0.35, 5.0), parent=banner_pole_e)
    for s in range(4):
        smooth_sphere(f"horsetail{i}_{s}", r=0.06 - s*0.005,
                      loc=(0, 0, -0.15 - s*0.20), parent=hori_e, mat_=M_MANE_BLACK,
                      scale=(1, 1.5, 1))
banner_pole_e["_banner"] = banner_main

# ============ 5 SHAMANS (autour feu central) ============
shamans = []
for si in range(5):
    a = (si / 5.0) * math.pi * 2 + math.pi/2
    rad = 2.0
    sx, sy = rad*math.cos(a), rad*math.sin(a)
    facing = a + math.pi
    s_base = empty(f"shaman{si}", (sx, sy, 0))
    s_base.rotation_euler = (0, 0, facing)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"sham{si}_leg{side_idx}", r=0.10, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.42), parent=s_base, mat_=M_DEEL_BROWN)
        beveled_cube(f"sham{si}_boot{side_idx}", (0.16, 0.25, 0.15),
                     loc=(side*0.13, 0.05, 0.10), parent=s_base, mat_=M_BOOT_LEATHER)
    # Robe long
    smooth_cone(f"sham{si}_robe", r1=0.45, r2=0.22, depth=1.0, segs=14,
                loc=(0, 0, 1.0), parent=s_base, mat_=M_SHAMAN_ROBE)
    # Torso
    beveled_cube(f"sham{si}_torso", (0.45, 0.30, 0.65), bevel_offset=0.05,
                 loc=(0, 0, 1.65), parent=s_base, mat_=M_SHAMAN_ROBE)
    # Bone necklace
    for j in range(6):
        a_n = (j / 6.0) * math.pi
        smooth_cone(f"sham{si}_bone{j}", r1=0.025, r2=0.005, depth=0.12, segs=8,
                    loc=(0.18*math.cos(a_n - math.pi/2), -0.18, 1.85 + 0.05*math.sin(a_n)),
                    parent=s_base, mat_=M_SHAMAN_BONE)
    # Head
    sham_head_e = empty(f"sham{si}_head_e", (0, 0, 2.05), parent=s_base)
    smooth_sphere(f"sham{si}_h", r=0.18, loc=(0,0,0), parent=sham_head_e, mat_=M_SKIN_MONGOL)
    for side in (-1, 1):
        smooth_sphere(f"sham{si}_eye_{side}", r=0.022,
                      loc=(side*0.06, -0.14, 0.03), parent=sham_head_e,
                      mat_=mat(f"sham_ew{si}_{side}", (0.05,0.05,0.05,1), 0, 0.3))
    # Feather headdress (5 tall feathers)
    for fi in range(5):
        col = M_SHAMAN_FEATHER if fi % 2 == 0 else M_SHAMAN_FEATHER2
        feather = beveled_cube(f"sham{si}_f{fi}", (0.04, 0.06, 0.55), bevel_offset=0.02,
                               loc=((fi-2)*0.05, 0.02, 0.30), parent=sham_head_e, mat_=col)
        feather.rotation_euler = (math.radians(-10 + fi*3), 0, math.radians((fi-2)*5))
    # Mask / face paint hint
    smooth_sphere(f"sham{si}_paint", r=0.05, loc=(0, -0.16, 0.05),
                  parent=sham_head_e, mat_=M_SHAMAN_FEATHER, scale=(1.3, 0.4, 0.5))
    # 2 arms holding drum
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"sham{si}_sh{side_idx}", (side*0.25, 0, 1.95), parent=s_base)
        sh.rotation_euler = (math.radians(-90), 0, math.radians(side*-25))
        cyl(f"sham{si}_up{side_idx}", r=0.07, depth=0.36, segs=10,
            loc=(0, 0, -0.18), parent=sh, mat_=M_SHAMAN_ROBE)
        cyl(f"sham{si}_fa{side_idx}", r=0.06, depth=0.33, segs=10,
            loc=(0, 0, -0.50), parent=sh, mat_=M_SKIN_MONGOL)
    # DRUM held in front
    drum_e = empty(f"sham{si}_drum_e", (0, -0.50, 1.55), parent=s_base)
    drum_e.rotation_euler = (math.radians(-10), 0, 0)
    # Drum frame circular
    cyl(f"sham{si}_drum_body", r=0.25, depth=0.10, segs=20,
        loc=(0, 0, 0), parent=drum_e, mat_=M_DRUM)
    # Skin top (signature)
    cyl(f"sham{si}_drum_skin", r=0.24, depth=0.04, segs=20,
        loc=(0, 0, 0.05), parent=drum_e, mat_=M_DRUM_SKIN)
    # Stick
    cyl(f"sham{si}_stick", r=0.02, depth=0.30, segs=8,
        loc=(0.30, -0.10, 0.05), parent=drum_e, mat_=M_WOOD)
    shamans.append({"root": s_base, "head_e": sham_head_e, "drum_e": drum_e,
                    "phase": si * 0.4})

# ============ 100 SHEEP (troupeau) ============
sheep = []
# Cluster sheep in herd far from yurts
for i in range(100):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(22, 30)
    sx = rad * math.cos(a) + random.uniform(-2, 2)
    sy = rad * math.sin(a) + random.uniform(-2, 2)
    s_e = empty(f"sheep{i}", (sx, sy, 0))
    s_e.rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    is_black = random.random() < 0.15
    wool = M_SHEEP_BLACK if is_black else M_SHEEP_WOOL
    # Body (fluffy)
    smooth_sphere(f"sheep_body{i}", r=0.30, segs=18, rings=12, loc=(0, 0, 0.45),
                  parent=s_e, mat_=wool, scale=(1.6, 0.95, 1.0))
    # Head
    smooth_sphere(f"sheep_h{i}", r=0.14, loc=(0.40, 0, 0.55),
                  parent=s_e, mat_=M_SHEEP_HEAD, scale=(1, 0.9, 1.0))
    # Ears
    for side in (-1, 1):
        beveled_cube(f"sheep_ear{i}_{side}", (0.06, 0.04, 0.08),
                     loc=(0.38, side*0.10, 0.65), parent=s_e, mat_=M_SHEEP_HEAD)
    # 4 legs
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"sheep_leg{i}_{x_idx}_{y_idx}", r=0.04, depth=0.35, segs=8,
                loc=(x*0.18, y*0.18, 0.18), parent=s_e, mat_=M_SHEEP_HEAD)
    sheep.append({"e": s_e, "phase": random.uniform(0, math.pi*2)})

# ============ 4 NOMAD DOGS ============
dogs = []
for i in range(4):
    a = (i / 4.0) * math.pi * 2 + 0.5
    rad = random.uniform(5, 10)
    dx, dy = rad*math.cos(a), rad*math.sin(a)
    d_e = empty(f"dog{i}", (dx, dy, 0))
    d_e.rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    # Body
    smooth_sphere(f"dog_body{i}", r=0.25, segs=18, rings=12, loc=(0,0,0.40),
                  parent=d_e, mat_=M_DOG_NOMAD, scale=(1.8, 0.85, 0.85))
    # Head
    head_e = empty(f"dog_h{i}_e", (0.40, 0, 0.50), parent=d_e)
    smooth_sphere(f"dog_h{i}", r=0.13, loc=(0,0,0), parent=head_e,
                  mat_=M_DOG_NOMAD, scale=(1.5, 0.9, 0.9))
    # 2 pointed ears
    for side in (-1, 1):
        smooth_cone(f"dog_ear{i}_{side}", r1=0.05, r2=0.005, depth=0.10, segs=8,
                    loc=(side*0.06, 0.05, 0.10), parent=head_e, mat_=M_DOG_NOMAD).rotation_euler = (math.radians(-15), math.radians(side*15), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"dog_eye{i}_{side}", r=0.03,
                      loc=(0.10, side*0.07, 0.05), parent=head_e, mat_=M_DOG_EYE)
    # Snout
    smooth_sphere(f"dog_snout{i}", r=0.07, loc=(0.13, 0, -0.05),
                  parent=head_e, mat_=M_HAIR_BLACK)
    # 4 legs
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"dog_leg{i}_{x_idx}_{y_idx}", r=0.04, depth=0.30, segs=8,
                loc=(x*0.15, y*0.15, 0.15), parent=d_e, mat_=M_DOG_NOMAD)
    # Tail (curled)
    tail_e = empty(f"dog_tail{i}_e", (-0.30, 0, 0.45), parent=d_e)
    cyl(f"dog_tail{i}", r=0.04, depth=0.25, segs=10,
        loc=(0, 0, 0), parent=tail_e, mat_=M_DOG_NOMAD).rotation_euler = (math.radians(-45), 0, 0)
    dogs.append({"e": d_e, "tail": tail_e, "head": head_e, "phase": random.uniform(0, math.pi*2)})

# ============ EAGLE (steppe eagle flying high) ============
eagle_e = empty("eagle", loc=(8, 18, 20))
eagle_e.rotation_euler = (0, 0, math.radians(-30))
# Body
smooth_sphere("eagle_body", r=0.40, segs=20, rings=14, loc=(0,0,0),
              parent=eagle_e, mat_=M_EAGLE, scale=(2.0, 0.9, 0.95))
# Head white head (signature steppe eagle)
smooth_sphere("eagle_head", r=0.18, loc=(0.65, 0, 0.05),
              parent=eagle_e, mat_=M_EAGLE_HEAD)
# Beak hooked
smooth_cone("eagle_beak", r1=0.06, r2=0.005, depth=0.18, segs=10,
            loc=(0.80, 0, 0), parent=eagle_e, mat_=M_EAGLE_BEAK).rotation_euler = (math.radians(80), 0, 0)
# Eye
smooth_sphere("eagle_eye", r=0.05, loc=(0.62, -0.12, 0.10),
              parent=eagle_e, mat_=M_EAGLE_EYE)
# 2 WINGS huge
eagle_wings = []
for side_idx, side in enumerate((-1, 1)):
    w_sh = empty(f"eagle_w_sh{side_idx}", (0, side*0.35, 0), parent=eagle_e)
    # Inner wing
    beveled_cube(f"eagle_w_in{side_idx}", (0.9, 1.4, 0.06), bevel_offset=0.04,
                 loc=(0, side*0.7, 0), parent=w_sh, mat_=M_EAGLE)
    # Outer wing + primary feathers
    w_outer = empty(f"eagle_w_out{side_idx}", (0, side*1.4, 0), parent=w_sh)
    beveled_cube(f"eagle_w_o{side_idx}", (0.8, 1.2, 0.05),
                 loc=(0, side*0.6, 0), parent=w_outer, mat_=M_EAGLE)
    # 4 long tip feathers
    for fi in range(4):
        beveled_cube(f"eagle_prim{side_idx}_{fi}", (0.18, 0.55, 0.04),
                     loc=(0.30 - fi*0.20, side*1.2, 0), parent=w_outer, mat_=M_EAGLE)
    eagle_wings.append((w_sh, w_outer, side))
# Tail (5 fanned)
for ti in range(5):
    angle = (ti - 2) * 0.10
    beveled_cube(f"eagle_tail{ti}", (0.05, 0.40, 0.04), bevel_offset=0.02,
                 loc=(-0.8, math.sin(angle)*0.10, math.cos(angle)*0.10 - 0.05),
                 parent=eagle_e, mat_=M_EAGLE).rotation_euler = (angle, 0, 0)
# Feet (talons hanging)
for side in (-1, 1):
    cyl(f"eagle_foot_{side}", r=0.04, depth=0.20, segs=8,
        loc=(-0.30, side*0.18, -0.30), parent=eagle_e, mat_=M_EAGLE_BEAK)

# ============ 200 HERBES HAUTES (tall steppe grasses) ============
grasses = []
for i in range(200):
    gx = random.uniform(-30, 30)
    gy = random.uniform(-30, 30)
    # Skip area near yurts/camp
    near_camp = False
    for (yx, yy) in yurt_positions:
        if (gx - yx)**2 + (gy - yy)**2 < 9:
            near_camp = True
            break
    if abs(gx) < 4 and abs(gy) < 4:
        near_camp = True
    if near_camp:
        # push outward
        ang = math.atan2(gy, gx)
        rad = 14 + random.uniform(0, 10)
        gx, gy = rad*math.cos(ang), rad*math.sin(ang)
    g_e = empty(f"grass{i}", (gx, gy, 0))
    # Several grass blades (3-4 per tuft)
    for j in range(random.randint(2, 4)):
        a2 = random.uniform(0, math.pi*2)
        blade = beveled_cube(f"grass{i}_{j}", (0.04, 0.04, 0.7),
                             loc=(0.05*math.cos(a2), 0.05*math.sin(a2), 0.35),
                             parent=g_e, mat_=M_GRASS)
        blade.rotation_euler = (math.radians(random.uniform(-5, 5)),
                                math.radians(random.uniform(-5, 5)), 0)
    g_e["_phase"] = random.uniform(0, math.pi*2)
    grasses.append(g_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Horses gallop (legs alternate cycle + Z bob) + orbit en cercle
for hi, horse in enumerate(horses):
    phase = hi * 0.4
    a_base = (hi / 8.0) * math.pi * 2
    rad = 16
    legs = horse["legs_e"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Orbit galloping in circle
        a = a_base + t * 0.4
        x = rad * math.cos(a)
        y = rad * math.sin(a)
        z = 0 + abs(math.sin(t * 6.0 + phase)) * 0.2
        horse["root"].location = (x, y, z)
        horse["root"].rotation_euler = (0, 0, a + math.pi/2)
        horse["root"].keyframe_insert("location", frame=f)
        horse["root"].keyframe_insert("rotation_euler", frame=f)
        # Legs gallop alternate
        for li, leg in enumerate(legs):
            phase_offset = li * math.pi/2
            leg.rotation_euler = (math.sin(t * 6.0 + phase + phase_offset) * math.radians(35), 0, 0)
            leg.keyframe_insert("rotation_euler", frame=f)

# Riders follow horses (their root is at (hx, hy, 0) but we need them to move with horse)
# Easier: re-position riders each frame to match horse position
for ri, rider in enumerate(riders):
    horse = horses[ri]
    phase = ri * 0.4
    a_base = (ri / 8.0) * math.pi * 2
    rad = 16
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        a = a_base + t * 0.4
        x = rad * math.cos(a)
        y = rad * math.sin(a)
        z = 0 + abs(math.sin(t * 6.0 + phase)) * 0.2
        rider["root"].location = (x, y, z)
        rider["root"].rotation_euler = (0, 0, a + math.pi/2)
        rider["root"].keyframe_insert("location", frame=f)
        rider["root"].keyframe_insert("rotation_euler", frame=f)

# Foot warriors subtle bob + head turn
for fw in foot_warriors:
    base_z = fw["root"].location.z
    phase = hash(fw["root"].name) % 100 * 0.05
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        fw["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.03
        fw["root"].keyframe_insert("location", frame=f)
        fw["head_e"].rotation_euler = (0, 0, math.sin(t * 0.7 + phase) * math.radians(15))
        fw["head_e"].keyframe_insert("rotation_euler", frame=f)

# Chef (Khan) on yak - majestic subtle motion
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    chef["root"].location.z = math.sin(t * 1.0) * 0.04
    chef["root"].keyframe_insert("location", frame=f)
    chef["head_e"].rotation_euler = (0, 0, math.sin(t * 0.6) * math.radians(10))
    chef["head_e"].keyframe_insert("rotation_euler", frame=f)

# Yak subtle bob
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    yak_base.location.z = math.sin(t * 1.2) * 0.04
    yak_base.keyframe_insert("location", frame=f)
    yak_head_e.rotation_euler = (0, math.sin(t * 0.8) * math.radians(5),
                                  math.sin(t * 0.6) * math.radians(10))
    yak_head_e.keyframe_insert("rotation_euler", frame=f)

# Banner pole wave (large flag)
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    banner_pole_e["_banner"].rotation_euler = (math.sin(t * 2.0) * math.radians(8),
                                                math.sin(t * 1.8 + 0.5) * math.radians(5),
                                                0)
    banner_pole_e["_banner"].keyframe_insert("rotation_euler", frame=f)

# Shamans dance + drum strike
for s in shamans:
    phase = s["phase"]
    base_z = s["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s["root"].location.z = base_z + abs(math.sin(t * 2.5 + phase)) * 0.12
        s["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(6), 0,
                                     s["root"].rotation_euler.z + math.sin(t * 1.0 + phase) * math.radians(8))
        s["root"].keyframe_insert("location", frame=f)
        s["root"].keyframe_insert("rotation_euler", frame=f)
        s["head_e"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(10), 0,
                                       math.sin(t * 1.2 + phase) * math.radians(15))
        s["head_e"].keyframe_insert("rotation_euler", frame=f)
        # Drum strike (Z shake)
        s["drum_e"].rotation_euler = (math.radians(-10),
                                       math.sin(t * 8.0 + phase) * math.radians(15),
                                       0)
        s["drum_e"].keyframe_insert("rotation_euler", frame=f)

# Campfire flames
for outer, inner in flames:
    p_o = outer["_phase"]; p_i = inner["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s_o = 1 + math.sin(t * 6.0 + p_o) * 0.30
        outer.scale = (s_o, s_o, s_o)
        outer.keyframe_insert("scale", frame=f)
        s_i = 1 + math.sin(t * 8.0 + p_i) * 0.35
        inner.scale = (s_i, s_i, s_i)
        inner.keyframe_insert("scale", frame=f)
for e in embers:
    phase = e["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 5.0 + phase) * 0.40
        e.scale = (s, s, s)
        e.keyframe_insert("scale", frame=f)

# 100 sheep gentle bob + head turn (grazing)
for sh in sheep:
    phase = sh["phase"]
    base_z = sh["e"].location.z
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        sh["e"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.03
        sh["e"].rotation_euler = (math.sin(t * 0.3 + phase) * math.radians(3),
                                   0,
                                   sh["e"].rotation_euler.z + math.sin(t * 0.5 + phase) * math.radians(8))
        sh["e"].keyframe_insert("location", frame=f)
        sh["e"].keyframe_insert("rotation_euler", frame=f)

# Dogs subtle bob + tail wag
for d in dogs:
    phase = d["phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        d["tail"].rotation_euler = (math.radians(-45),
                                     0,
                                     math.sin(t * 4.0 + phase) * math.radians(30))
        d["tail"].keyframe_insert("rotation_euler", frame=f)
        d["head"].rotation_euler = (0, 0, math.sin(t * 1.2 + phase) * math.radians(20))
        d["head"].keyframe_insert("rotation_euler", frame=f)

# Eagle flap + orbit massive
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    flap = math.sin(t * 1.8) * math.radians(30)
    for w_sh, w_out, side in eagle_wings:
        w_sh.rotation_euler = (side * flap, 0, 0)
        w_sh.keyframe_insert("rotation_euler", frame=f)
        w_out.rotation_euler = (side * flap * 0.6, 0, 0)
        w_out.keyframe_insert("rotation_euler", frame=f)
    a = t * 0.3
    r = 16
    eagle_e.location = (r * math.cos(a), r * math.sin(a) + 5,
                         20 + math.sin(t * 0.8) * 1.5)
    eagle_e.rotation_euler = (0, 0, a + math.pi/2)
    eagle_e.keyframe_insert("location", frame=f)
    eagle_e.keyframe_insert("rotation_euler", frame=f)

# 200 grasses wave
for g in grasses:
    phase = g["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        g.rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(15),
                             math.cos(t * 1.3 + phase) * math.radians(12),
                             0)
        g.keyframe_insert("rotation_euler", frame=f)

# Clouds drift
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 0.7,
                        by + math.cos(t * 0.25 + phase) * 0.7,
                        c_e.location.z)
        c_e.keyframe_insert("location", frame=f)

# Sun pulse
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 0.8) * 0.05
    sun.scale = (s, s, s)
    sun.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_mongol_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_mongol_horde_steppe] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_mongol_horde_steppe] 6 yurts + Khan on yak + 8 horses+riders galloping + 22 foot warriors + 5 shamans dance/drum + 100 sheep + 4 nomad dogs + eagle flying + banner pole + 200 grasses + 10 clouds + campfire 6 flames")
