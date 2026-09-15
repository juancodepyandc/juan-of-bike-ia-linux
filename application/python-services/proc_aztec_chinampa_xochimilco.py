"""
proc_aztec_chinampa_xochimilco.py — 224e procédural AuroraIA (88e qualité)
Aztec Xochimilco: ONE water + 12 chinampas + 4 trajineras + 6 paddlers + tortillas woman + Aztec dancer feathers + Templo Mayor + 4 mariachi + swans + flamingos + ducks + lilies + willow + 600 hummingbirds + 300 floating petals
FIXES : 1 ground (water surface) + 600 hummingbirds + 300 petals thématiques signature Aztec
"""
import bpy, bmesh, math, random, os

random.seed(0xA27EC224)

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

# Mexico golden afternoon palette
M_SKY = mat("sky", (0.95, 0.78, 0.55, 1.0), 0.0, 0.7, emission=(0.92,0.72,0.50), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.92, 0.55, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.55), emission_strength=22.0)
M_CLOUD = mat("cloud", (1.0, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.95,0.80,0.62), emission_strength=2.0, alpha=0.85)

# Lake water (signature Xochimilco)
M_WATER = mat("water", (0.20, 0.55, 0.62, 0.85), 0.4, 0.10, emission=(0.20,0.55,0.62), emission_strength=1.5, alpha=0.85)
M_WATER_DEEP = mat("water_d", (0.15, 0.42, 0.50, 1.0), 0.4, 0.15, emission=(0.15,0.42,0.50), emission_strength=1.2)
M_RIPPLE = mat("ripple", (0.85, 0.95, 0.95, 0.75), 0.0, 0.20, emission=(0.85,0.95,0.95), emission_strength=2.0, alpha=0.75)

# Chinampa earth + crops
M_EARTH_CHINAMPA = mat("earth_c", (0.42, 0.30, 0.18, 1.0), 0.0, 0.85, emission=(0.38,0.28,0.16), emission_strength=0.3)
M_GROW_GREEN = mat("grow_g", (0.30, 0.65, 0.25, 1.0), 0.0, 0.70, emission=(0.28,0.60,0.22), emission_strength=0.5)
M_CORN_LEAF = mat("corn_l", (0.55, 0.78, 0.30, 1.0), 0.0, 0.65, emission=(0.50,0.72,0.28), emission_strength=0.6)
M_CORN_YELLOW = mat("corn_y", (1.0, 0.82, 0.20, 1.0), 0.0, 0.50, emission=(1.0,0.82,0.20), emission_strength=1.5)
M_TOMATO_RED = mat("tom_r", (0.95, 0.20, 0.18, 1.0), 0.0, 0.40, emission=(0.90,0.20,0.18), emission_strength=1.8)
M_CHILI_RED = mat("chili", (1.0, 0.18, 0.10, 1.0), 0.0, 0.35, emission=(1.0,0.18,0.10), emission_strength=2.2)
M_CHILI_GREEN = mat("chili_g", (0.30, 0.85, 0.20, 1.0), 0.0, 0.40, emission=(0.28,0.80,0.18), emission_strength=2.0)
M_BEAN_GREEN = mat("bean_g", (0.18, 0.55, 0.25, 1.0), 0.0, 0.55, emission=(0.15,0.50,0.22), emission_strength=0.5)

# Trajineras (signature colorful boats)
M_BOAT_RED = mat("boat_r", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.78,0.18,0.18), emission_strength=0.7)
M_BOAT_YELLOW = mat("boat_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.50, emission=(1.0,0.85,0.20), emission_strength=0.9)
M_BOAT_BLUE = mat("boat_b", (0.20, 0.55, 0.85, 1.0), 0.0, 0.55, emission=(0.20,0.50,0.78), emission_strength=0.7)
M_BOAT_GREEN = mat("boat_g", (0.30, 0.65, 0.30, 1.0), 0.0, 0.55, emission=(0.28,0.60,0.28), emission_strength=0.6)
M_BOAT_WHITE = mat("boat_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.78), emission_strength=0.5)
M_BOAT_FLOWER_PINK = mat("bf_p", (1.0, 0.45, 0.75, 1.0), 0.0, 0.40, emission=(1.0,0.45,0.75), emission_strength=2.2)
M_BOAT_FLOWER_PURPLE = mat("bf_pu", (0.65, 0.30, 0.85, 1.0), 0.0, 0.45, emission=(0.60,0.28,0.78), emission_strength=2.0)
M_BOAT_FLOWER_ORANGE = mat("bf_o", (1.0, 0.55, 0.10, 1.0), 0.0, 0.40, emission=(1.0,0.55,0.10), emission_strength=2.4)

# People
M_SKIN_AZTEC = mat("skin", (0.82, 0.58, 0.40, 1.0), 0.0, 0.55, emission=(0.75,0.55,0.38), emission_strength=0.4)
M_HAIR_AZTEC = mat("hair", (0.08, 0.05, 0.04, 1.0), 0.0, 0.85)
M_CLOTH_WHITE = mat("cl_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.78), emission_strength=0.5)
M_HUIPIL_PINK = mat("huipil_p", (0.95, 0.45, 0.65, 1.0), 0.0, 0.55, emission=(0.90,0.42,0.60), emission_strength=0.7)
M_HUIPIL_RED = mat("huipil_r", (0.85, 0.20, 0.25, 1.0), 0.0, 0.55, emission=(0.78,0.20,0.22), emission_strength=0.7)
M_PANTS_BROWN = mat("pant_b", (0.45, 0.30, 0.18, 1.0), 0.0, 0.75, emission=(0.42,0.28,0.16), emission_strength=0.3)
M_SOMBRERO = mat("somb", (0.75, 0.55, 0.30, 1.0), 0.0, 0.75, emission=(0.70,0.52,0.28), emission_strength=0.5)
M_PADDLE = mat("paddle", (0.55, 0.35, 0.20, 1.0), 0.0, 0.75, emission=(0.50,0.32,0.18), emission_strength=0.4)

# Aztec dancer feathers (signature massive plume fan)
M_FEATHER_QUETZAL_GREEN = mat("f_qg", (0.15, 0.80, 0.40, 1.0), 0.0, 0.40, emission=(0.15,0.80,0.40), emission_strength=2.8)
M_FEATHER_QUETZAL_BLUE = mat("f_qb", (0.15, 0.55, 0.95, 1.0), 0.0, 0.40, emission=(0.15,0.55,0.95), emission_strength=2.8)
M_FEATHER_QUETZAL_RED = mat("f_qr", (0.95, 0.18, 0.20, 1.0), 0.0, 0.40, emission=(0.90,0.18,0.20), emission_strength=2.8)
M_FEATHER_GOLD = mat("f_g", (1.0, 0.78, 0.20, 1.0), 0.85, 0.20, emission=(0.95,0.72,0.20), emission_strength=2.5)
M_JADE_AZTEC = mat("jade", (0.18, 0.65, 0.45, 1.0), 0.7, 0.20, emission=(0.18,0.65,0.45), emission_strength=2.5)
M_BREASTPLATE = mat("bp", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.90,0.72,0.28), emission_strength=1.5)
M_FACE_PAINT_RED = mat("fpr", (0.85, 0.18, 0.18, 1.0), 0.0, 0.40, emission=(0.78,0.18,0.18), emission_strength=1.0)
M_FACE_PAINT_WHITE = mat("fpw", (0.95, 0.92, 0.85, 1.0), 0.0, 0.40, emission=(0.88,0.85,0.78), emission_strength=0.9)

# Templo Mayor signature
M_TEMPLO_BASE = mat("templo_b", (0.65, 0.42, 0.25, 1.0), 0.0, 0.80, emission=(0.60,0.40,0.22), emission_strength=0.5)
M_TEMPLO_RED = mat("templo_r", (0.85, 0.20, 0.15, 1.0), 0.0, 0.65, emission=(0.78,0.20,0.15), emission_strength=0.8)
M_TEMPLO_BLUE = mat("templo_bl", (0.20, 0.40, 0.75, 1.0), 0.0, 0.55, emission=(0.18,0.38,0.70), emission_strength=0.9)
M_SNAKE_SCALES = mat("ss", (0.30, 0.65, 0.40, 1.0), 0.5, 0.30, emission=(0.28,0.60,0.38), emission_strength=1.0)
M_JAGUAR_STONE = mat("jag_s", (0.50, 0.40, 0.28, 1.0), 0.0, 0.75)

# Mariachi colors
M_MARIACHI_BLACK = mat("m_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.65, emission=(0.10,0.08,0.08), emission_strength=0.3)
M_MARIACHI_SILVER = mat("m_s", (0.85, 0.85, 0.92, 1.0), 0.85, 0.20, emission=(0.78,0.78,0.85), emission_strength=0.8)
M_BOWTIE_RED = mat("bow", (0.85, 0.18, 0.18, 1.0), 0.0, 0.45, emission=(0.78,0.18,0.18), emission_strength=0.7)
M_GUITAR_WOOD = mat("g_w", (0.45, 0.25, 0.12, 1.0), 0.0, 0.55, emission=(0.40,0.22,0.10), emission_strength=0.5)
M_TRUMPET_BRASS = mat("tp_br", (0.95, 0.72, 0.25, 1.0), 0.95, 0.18, emission=(0.90,0.68,0.22), emission_strength=1.0)

# Birds
M_SWAN = mat("swan", (0.95, 0.92, 0.88, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.82), emission_strength=0.5)
M_SWAN_BEAK = mat("swan_b", (1.0, 0.65, 0.30, 1.0), 0.0, 0.45, emission=(0.95,0.62,0.28), emission_strength=0.7)
M_FLAMINGO_PINK = mat("flam_p", (1.0, 0.55, 0.75, 1.0), 0.0, 0.50, emission=(1.0,0.55,0.75), emission_strength=1.5)
M_FLAMINGO_PINK_DEEP = mat("flam_d", (0.95, 0.35, 0.55, 1.0), 0.0, 0.50, emission=(0.90,0.32,0.50), emission_strength=1.7)
M_DUCK_BROWN = mat("duck_b", (0.55, 0.42, 0.25, 1.0), 0.0, 0.65)
M_DUCK_GREEN = mat("duck_g", (0.18, 0.55, 0.35, 1.0), 0.4, 0.40, emission=(0.18,0.55,0.35), emission_strength=1.0)

# Hummingbirds (signature)
M_HUMMING_GREEN = mat("hg", (0.20, 0.95, 0.45, 1.0), 0.6, 0.20, emission=(0.20,0.95,0.45), emission_strength=4.0)
M_HUMMING_BLUE = mat("hb", (0.20, 0.55, 0.95, 1.0), 0.6, 0.20, emission=(0.20,0.55,0.95), emission_strength=4.0)
M_HUMMING_PURPLE = mat("hp", (0.65, 0.30, 0.95, 1.0), 0.6, 0.20, emission=(0.65,0.30,0.95), emission_strength=4.0)
M_HUMMING_RUBY = mat("hru", (0.95, 0.15, 0.45, 1.0), 0.6, 0.20, emission=(0.95,0.15,0.45), emission_strength=4.0)
M_HUMMING_WING = mat("hw", (0.85, 0.85, 0.92, 0.40), 0.0, 0.20, emission=(0.85,0.85,0.92), emission_strength=2.0, alpha=0.40)

# Lily pads
M_LILY_LEAF = mat("ll", (0.20, 0.55, 0.25, 1.0), 0.0, 0.65, emission=(0.18,0.50,0.22), emission_strength=0.4)
M_LILY_FLOWER = mat("lf", (1.0, 0.85, 0.92, 1.0), 0.0, 0.45, emission=(1.0,0.85,0.92), emission_strength=1.5)
M_LILY_FLOWER_PINK = mat("lfp", (1.0, 0.55, 0.85, 1.0), 0.0, 0.45, emission=(1.0,0.55,0.85), emission_strength=1.7)

# Willow weeping
M_WILLOW_TRUNK = mat("wt", (0.42, 0.30, 0.18, 1.0), 0.0, 0.80)
M_WILLOW_LEAF = mat("wl", (0.32, 0.55, 0.28, 1.0), 0.0, 0.55, emission=(0.30,0.50,0.25), emission_strength=0.5)

# Floating petals (signature)
M_PETAL_PINK = mat("pp", (1.0, 0.55, 0.75, 1.0), 0.0, 0.45, emission=(1.0,0.55,0.75), emission_strength=2.0)
M_PETAL_RED = mat("pr", (0.95, 0.20, 0.30, 1.0), 0.0, 0.45, emission=(0.90,0.20,0.28), emission_strength=2.0)
M_PETAL_YELLOW = mat("py", (1.0, 0.92, 0.30, 1.0), 0.0, 0.45, emission=(1.0,0.92,0.30), emission_strength=2.5)
M_PETAL_ORANGE = mat("po", (1.0, 0.55, 0.20, 1.0), 0.0, 0.45, emission=(1.0,0.55,0.20), emission_strength=2.3)
M_PETAL_WHITE = mat("pw", (1.0, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(1.0,0.95,0.92), emission_strength=1.8)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (30, 0, 30))
smooth_sphere("sun", r=5.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=5.0 + (i+1)*1.8, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

# Clouds drift
clouds = []
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    rad = random.uniform(35, 48)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(24, 32)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ ONE clean water surface ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_WATER)
# Deeper water variation (organic 3D)
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(20, 40)
    smooth_sphere(f"water_d{i}", r=random.uniform(0.8, 1.6),
                  loc=(rad*math.cos(a), rad*math.sin(a), -0.40),
                  mat_=M_WATER_DEEP, scale=(2.0, 1.6, 0.15))
# Surface ripples (organic 3D)
for i in range(40):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 35)
    smooth_sphere(f"ripple{i}", r=random.uniform(0.25, 0.50), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_RIPPLE, scale=(1.5, 1.3, 0.12))

# ============ TEMPLO MAYOR BACKGROUND (signature double pyramid) ============
templo_e = empty("templo", loc=(0, 32, 0))
# Double pyramid base (signature Templo Mayor 4 levels each)
levels = 5
for lv in range(levels):
    width = 12 - lv * 1.8
    depth = 7 - lv * 0.9
    height = 1.5
    lz = lv * height + height/2
    # Wide platform
    beveled_cube(f"tm_lv{lv}", (width, depth, height), bevel_offset=0.04,
                 loc=(0, 0, lz), parent=templo_e, mat_=M_TEMPLO_BASE)
# Top split into 2 temples (signature Templo Mayor)
templo_top_z = levels * 1.5
# LEFT temple (Tlaloc - rain - blue)
beveled_cube("tm_left_base", (4.5, 4.5, 0.8), bevel_offset=0.04,
             loc=(-2.5, 0, templo_top_z + 0.4), parent=templo_e, mat_=M_TEMPLO_BLUE)
beveled_cube("tm_left_walls", (3.8, 3.8, 2.5), bevel_offset=0.05,
             loc=(-2.5, 0, templo_top_z + 2.05), parent=templo_e, mat_=M_TEMPLO_BLUE)
# Left temple roof
beveled_cube("tm_left_roof", (4.2, 4.2, 0.4), bevel_offset=0.04,
             loc=(-2.5, 0, templo_top_z + 3.50), parent=templo_e, mat_=M_TEMPLO_BLUE)
# Glyph
smooth_sphere("tm_left_glyph", r=0.25, loc=(-2.5, -1.95, templo_top_z + 2.0),
              parent=templo_e, mat_=M_FEATHER_GOLD)

# RIGHT temple (Huitzilopochtli - war - red)
beveled_cube("tm_right_base", (4.5, 4.5, 0.8), bevel_offset=0.04,
             loc=(2.5, 0, templo_top_z + 0.4), parent=templo_e, mat_=M_TEMPLO_RED)
beveled_cube("tm_right_walls", (3.8, 3.8, 2.5), bevel_offset=0.05,
             loc=(2.5, 0, templo_top_z + 2.05), parent=templo_e, mat_=M_TEMPLO_RED)
beveled_cube("tm_right_roof", (4.2, 4.2, 0.4), bevel_offset=0.04,
             loc=(2.5, 0, templo_top_z + 3.50), parent=templo_e, mat_=M_TEMPLO_RED)
smooth_sphere("tm_right_glyph", r=0.25, loc=(2.5, -1.95, templo_top_z + 2.0),
              parent=templo_e, mat_=M_FEATHER_GOLD)

# Central staircase (signature dual stair)
for step in range(18):
    step_y = -3.6 - step * 0.20
    step_z = 0.30 + step * (templo_top_z) / 18
    # Left stair
    beveled_cube(f"tm_stair_l{step}", (4.0, 0.40, 0.25), bevel_offset=0.03,
                 loc=(-2.5, step_y, step_z), parent=templo_e, mat_=M_TEMPLO_BASE)
    beveled_cube(f"tm_stair_r{step}", (4.0, 0.40, 0.25), bevel_offset=0.03,
                 loc=(2.5, step_y, step_z), parent=templo_e, mat_=M_TEMPLO_BASE)
# Central divider
beveled_cube("tm_divider", (0.5, 4.0, templo_top_z + 0.5), bevel_offset=0.04,
             loc=(0, -1.5, templo_top_z/2), parent=templo_e, mat_=M_TEMPLO_BASE)

# Serpent heads at base of stairs (signature feathered serpent)
for side in (-1, 1):
    s_head_e = empty(f"tm_serp_e{side}", (side*4, -3.6, 0.50), parent=templo_e)
    smooth_sphere(f"tm_serp_head{side}", r=0.50, segs=20, rings=14,
                  loc=(0, 0, 0), parent=s_head_e, mat_=M_SNAKE_SCALES,
                  scale=(1.5, 1.2, 1))
    # Open mouth fangs
    for fang in (-1, 1):
        smooth_cone(f"tm_fang{side}_{fang}", r1=0.06, r2=0.005, depth=0.20, segs=8,
                    loc=(0.30, fang*0.10, -0.10), parent=s_head_e,
                    mat_=M_FACE_PAINT_WHITE).rotation_euler = (0, math.radians(45), 0)
    # Glowing eyes
    for side_eye in (-1, 1):
        smooth_sphere(f"tm_serp_eye{side}_{side_eye}", r=0.06,
                      loc=(0.15, side_eye*0.20, 0.20), parent=s_head_e,
                      mat_=M_FEATHER_QUETZAL_RED)
    # Feathered crown
    for fi in range(5):
        fa = (fi - 2) * 0.30
        plume = beveled_cube(f"tm_plume{side}_{fi}", (0.10, 0.40, 0.04), bevel_offset=0.02,
                             loc=(-0.20, math.sin(fa)*0.30, 0.40),
                             parent=s_head_e,
                             mat_=M_FEATHER_QUETZAL_GREEN if fi % 2 == 0 else M_FEATHER_QUETZAL_BLUE)
        plume.rotation_euler = (math.radians(20), 0, fa)

# Jaguar stone heads on either side
for side in (-1, 1):
    j_e = empty(f"jaguar_e{side}", (side*8, -3, 0.5), parent=templo_e)
    smooth_sphere(f"jaguar_head{side}", r=0.40, segs=20, rings=14, loc=(0, 0, 0),
                  parent=j_e, mat_=M_JAGUAR_STONE)
    # Eyes
    for eye in (-1, 1):
        smooth_sphere(f"jaguar_e{side}_{eye}", r=0.05,
                      loc=(0.20, eye*0.15, 0.10), parent=j_e, mat_=M_FEATHER_QUETZAL_RED)
    # Fangs
    for f_side in (-1, 1):
        smooth_cone(f"jaguar_fang{side}_{f_side}", r1=0.04, r2=0.005, depth=0.12, segs=8,
                    loc=(0.30, f_side*0.06, -0.10), parent=j_e,
                    mat_=M_FACE_PAINT_WHITE).rotation_euler = (0, math.radians(180), 0)

# ============ 12 CHINAMPAS (floating islands with crops) ============
chinampas = []
chinampa_specs = [
    (-12, 12, 1, "corn"), (-7, 11, 1, "tomato"), (-2, 12, 1, "chili"),
    (3, 11, 1, "bean"), (8, 12, 1, "corn"), (13, 11, 1, "tomato"),
    (-13, -5, 1, "chili"), (-8, -6, 1, "corn"), (-3, -5, 1, "bean"),
    (4, -6, 1, "tomato"), (9, -5, 1, "chili"), (14, -6, 1, "corn"),
]
for ci, (cx, cy, _, crop) in enumerate(chinampa_specs):
    c_e = empty(f"chin{ci}", (cx, cy, 0))
    # Earth island (raised)
    beveled_cube(f"ch_earth{ci}", (3.5, 2.5, 0.4), bevel_offset=0.06,
                 loc=(0, 0, 0.20), parent=c_e, mat_=M_EARTH_CHINAMPA)
    # Crops on chinampa
    if crop == "corn":
        # Tall corn stalks 12 plants
        for r in range(3):
            for c in range(4):
                px = (c - 1.5) * 0.7
                py = (r - 1) * 0.7
                # Stalk
                cyl(f"corn{ci}_{r}_{c}_st", r=0.035, depth=1.4, segs=8,
                    loc=(px, py, 0.90), parent=c_e, mat_=M_CORN_LEAF)
                # Leaves
                for l in range(4):
                    la = (l / 4.0) * math.pi * 2
                    leaf = beveled_cube(f"corn{ci}_{r}_{c}_l{l}", (0.05, 0.25, 0.02), bevel_offset=0.01,
                                        loc=(px + 0.08*math.cos(la), py + 0.08*math.sin(la), 1.0 + l*0.15),
                                        parent=c_e, mat_=M_CORN_LEAF)
                    leaf.rotation_euler = (math.radians(20), 0, la)
                # Corn cob (yellow signature)
                smooth_cone(f"corn{ci}_{r}_{c}_cob", r1=0.06, r2=0.04, depth=0.20, segs=10,
                            loc=(px, py, 1.35), parent=c_e, mat_=M_CORN_YELLOW)
                # Tassel top
                cyl(f"corn{ci}_{r}_{c}_top", r=0.02, depth=0.20, segs=6,
                    loc=(px, py, 1.55), parent=c_e, mat_=M_GROW_GREEN)
    elif crop == "tomato":
        # 8 tomato plants
        for r in range(2):
            for c in range(4):
                px = (c - 1.5) * 0.7
                py = (r * 2 - 1) * 0.5
                # Stem
                cyl(f"tom{ci}_{r}_{c}_st", r=0.025, depth=0.50, segs=6,
                    loc=(px, py, 0.65), parent=c_e, mat_=M_GROW_GREEN)
                # Leaves bush
                smooth_sphere(f"tom{ci}_{r}_{c}_bush", r=0.20, loc=(px, py, 0.80),
                              parent=c_e, mat_=M_GROW_GREEN, scale=(1.5, 1.2, 0.8))
                # 4 tomatoes hanging
                for to in range(4):
                    toa = (to / 4.0) * math.pi * 2
                    smooth_sphere(f"tom{ci}_{r}_{c}_t{to}", r=0.07,
                                  loc=(px + math.cos(toa)*0.12, py + math.sin(toa)*0.12, 0.78),
                                  parent=c_e, mat_=M_TOMATO_RED)
    elif crop == "chili":
        # Chili plants
        for r in range(3):
            for c in range(4):
                px = (c - 1.5) * 0.7
                py = (r - 1) * 0.6
                # Stem
                cyl(f"ch{ci}_{r}_{c}_st", r=0.022, depth=0.45, segs=6,
                    loc=(px, py, 0.60), parent=c_e, mat_=M_GROW_GREEN)
                # Leaves bush
                smooth_sphere(f"ch{ci}_{r}_{c}_bush", r=0.18, loc=(px, py, 0.75),
                              parent=c_e, mat_=M_GROW_GREEN, scale=(1.2, 1, 0.7))
                # Chilis (signature elongated)
                for chi in range(4):
                    chia = (chi / 4.0) * math.pi * 2
                    chili_col = M_CHILI_RED if (chi + ci) % 2 == 0 else M_CHILI_GREEN
                    cyl(f"ch{ci}_{r}_{c}_chi{chi}", r=0.02, depth=0.18, segs=8,
                        loc=(px + math.cos(chia)*0.12, py + math.sin(chia)*0.12, 0.62),
                        parent=c_e, mat_=chili_col).rotation_euler = (math.radians(60), 0, chia)
    elif crop == "bean":
        # Bean stalks tall (climbing)
        for r in range(2):
            for c in range(4):
                px = (c - 1.5) * 0.7
                py = (r * 2 - 1) * 0.5
                # Stick support
                cyl(f"bn{ci}_{r}_{c}_pole", r=0.02, depth=1.2, segs=6,
                    loc=(px, py, 0.80), parent=c_e, mat_=M_PADDLE)
                # Bean leaves climbing
                for bl in range(4):
                    bla = (bl / 4.0) * math.pi * 2
                    smooth_sphere(f"bn{ci}_{r}_{c}_l{bl}", r=0.08,
                                  loc=(px + 0.07*math.cos(bla), py + 0.07*math.sin(bla), 0.4 + bl*0.30),
                                  parent=c_e, mat_=M_BEAN_GREEN, scale=(1.5, 0.7, 0.5))
                # Bean pods
                for bp in range(3):
                    cyl(f"bn{ci}_{r}_{c}_p{bp}", r=0.02, depth=0.15, segs=6,
                        loc=(px + 0.10, py, 0.5 + bp*0.30), parent=c_e, mat_=M_BEAN_GREEN)
    # Reed border (signature chinampa edge)
    for ri in range(20):
        ra = (ri / 20.0) * math.pi * 2
        rx = 1.6 * math.cos(ra)
        ry = 1.1 * math.sin(ra)
        cyl(f"chin{ci}_reed{ri}", r=0.02, depth=0.40, segs=6,
            loc=(rx, ry, 0.40), parent=c_e, mat_=M_PADDLE)
    chinampas.append(c_e)

# ============ 4 TRAJINERAS (colorful gondolas signature) ============
def make_trajinera(name, loc, body_color, arch_color, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long hull (signature flat bottom boat)
    beveled_cube(f"{name}_hull", (4.0, 1.2, 0.30), bevel_offset=0.05,
                 loc=(0, 0, 0.15), parent=base, mat_=body_color)
    # Hull side bands
    for side in (-1, 1):
        beveled_cube(f"{name}_band{side}", (4.1, 0.10, 0.10),
                     loc=(0, side*0.60, 0.30), parent=base, mat_=M_BOAT_WHITE)
    # Pointed bow
    bow = smooth_cone(f"{name}_bow", r1=0.3, r2=0.1, depth=0.8, segs=10,
                      loc=(2.4, 0, 0.20), parent=base, mat_=body_color)
    bow.rotation_euler = (0, math.radians(90), 0)
    # Stern
    stern = smooth_cone(f"{name}_stern", r1=0.3, r2=0.1, depth=0.4, segs=10,
                        loc=(-2.2, 0, 0.20), parent=base, mat_=body_color)
    stern.rotation_euler = (0, math.radians(-90), 0)
    # Arched canopy (signature trajinera)
    canopy_e = empty(f"{name}_canopy_e", (0, 0, 1.2), parent=base)
    # 2 arch poles
    for ax_off, ax in enumerate((-1.5, 0, 1.5)):
        # Curved arch (5 segments)
        for arch_seg in range(5):
            ang = math.pi - (arch_seg / 4.0) * math.pi
            arch_x = math.cos(ang) * 0.75
            arch_z = math.sin(ang) * 0.6
            seg = beveled_cube(f"{name}_arch{ax_off}_{arch_seg}", (0.10, 0.10, 0.30), bevel_offset=0.02,
                              loc=(ax, arch_x, arch_z), parent=canopy_e, mat_=arch_color)
            seg.rotation_euler = (ang - math.pi/2, 0, 0)
    # Side arch beams
    for side in (-1, 1):
        beveled_cube(f"{name}_arch_side{side}", (3.5, 0.10, 0.10),
                     loc=(0, side*0.75, 0), parent=canopy_e, mat_=arch_color)
    # Top decorative beam
    beveled_cube(f"{name}_top_beam", (3.5, 0.10, 0.10),
                 loc=(0, 0, 0.65), parent=canopy_e, mat_=arch_color)
    # FLOWER decorations on canopy (signature)
    flower_mats = [M_BOAT_FLOWER_PINK, M_BOAT_FLOWER_PURPLE, M_BOAT_FLOWER_ORANGE,
                   M_BOAT_YELLOW, M_BOAT_FLOWER_PINK]
    for fp in range(7):
        fpx = (fp - 3) * 0.5
        fp_e = empty(f"{name}_fp_e{fp}", (fpx, 0, 0.70), parent=canopy_e)
        flower_col = flower_mats[fp % 5]
        for petal in range(6):
            pa = (petal / 6.0) * math.pi * 2
            smooth_sphere(f"{name}_fp{fp}_p{petal}", r=0.06,
                          loc=(0.10*math.cos(pa), 0.10*math.sin(pa), 0),
                          parent=fp_e, mat_=flower_col, scale=(1, 1, 0.5))
        # Center
        smooth_sphere(f"{name}_fp{fp}_c", r=0.04, loc=(0, 0, 0.02),
                      parent=fp_e, mat_=M_BOAT_YELLOW)
    # Side decoration (signature painted designs)
    for di in range(5):
        dx_d = (di - 2) * 0.7
        # Diamond shape on hull
        diamond = beveled_cube(f"{name}_decor{di}", (0.20, 0.05, 0.20), bevel_offset=0.02,
                               loc=(dx_d, -0.65, 0.20), parent=base, mat_=arch_color)
        diamond.rotation_euler = (math.radians(45), 0, 0)
        # Other side
        diamond2 = beveled_cube(f"{name}_decor_b{di}", (0.20, 0.05, 0.20), bevel_offset=0.02,
                                loc=(dx_d, 0.65, 0.20), parent=base, mat_=arch_color)
        diamond2.rotation_euler = (math.radians(45), 0, 0)
    # Name plaque on bow (signature painted name)
    beveled_cube(f"{name}_plaque", (0.8, 0.05, 0.30), bevel_offset=0.02,
                 loc=(2.0, 0, 0.50), parent=base, mat_=M_BOAT_WHITE)
    # Seats
    for sti in range(2):
        beveled_cube(f"{name}_seat{sti}", (0.80, 1.0, 0.15), bevel_offset=0.03,
                     loc=(-0.5 + sti*1.5, 0, 0.42), parent=base, mat_=arch_color)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

trajineras = []
traj_specs = [
    ("traj1", (-9, 3, 0), M_BOAT_RED, M_BOAT_YELLOW, math.radians(15)),
    ("traj2", (5, 4, 0), M_BOAT_YELLOW, M_BOAT_BLUE, math.radians(-15)),
    ("traj3", (-5, -2, 0), M_BOAT_BLUE, M_BOAT_RED, math.radians(70)),
    ("traj4", (8, -1, 0), M_BOAT_GREEN, M_BOAT_YELLOW, math.radians(-80)),
]
for spec in traj_specs:
    name, loc, body, arch, fac = spec
    t = make_trajinera(name, loc, body, arch, facing=fac)
    trajineras.append(t)

# ============ PEOPLE (paddlers + woman + dancer + mariachi) ============
def make_person(name, loc, top_mat, pant_mat, sombrero=False, facing=0, action="paddle", scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sitting body for paddler
    smooth_cone(f"{name}_legs", r1=0.30*scale, r2=0.22*scale, depth=0.55*scale, segs=14,
                loc=(0, 0, 0.30*scale), parent=base, mat_=pant_mat)
    # Torso
    beveled_cube(f"{name}_torso", (0.34*scale, 0.20*scale, 0.55*scale), bevel_offset=0.05,
                 loc=(0, 0, 0.85*scale), parent=base, mat_=top_mat)
    # Neck
    cyl(f"{name}_neck", r=0.08*scale, depth=0.15*scale, segs=10,
        loc=(0, 0, 1.18*scale), parent=base, mat_=M_SKIN_AZTEC)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.35*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.17*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_AZTEC)
    # Hair
    smooth_sphere(f"{name}_hair", r=0.18*scale, loc=(0, 0.03*scale, 0.04*scale),
                  parent=head_e, mat_=M_HAIR_AZTEC, scale=(1, 1, 0.85))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Sombrero (signature Mexican hat for paddlers)
    if sombrero:
        cyl(f"{name}_somb_brim", r=0.32*scale, depth=0.04*scale, segs=18,
            loc=(0, 0, 0.20*scale), parent=head_e, mat_=M_SOMBRERO)
        cyl(f"{name}_somb_crown", r=0.18*scale, depth=0.20*scale, segs=16,
            loc=(0, 0, 0.32*scale), parent=head_e, mat_=M_SOMBRERO)
        # Hat decoration
        cyl(f"{name}_somb_band", r=0.19*scale, depth=0.04*scale, segs=16,
            loc=(0, 0, 0.24*scale), parent=head_e, mat_=M_HUIPIL_RED)
    # Arms
    arms_e = []
    arm_poses = {
        "paddle": [(math.radians(-90), -20), (math.radians(-60), 30)],
        "sit": [(math.radians(-30), -10), (math.radians(-30), 10)],
        "play_g": [(math.radians(-70), -25), (math.radians(-50), 25)],
        "play_t": [(math.radians(-110), 0), (math.radians(-70), 20)],
    }
    pose = arm_poses.get(action, arm_poses["paddle"])
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.27*scale, 0, 1.10*scale), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15 + rz))
        cyl(f"{name}_uarm{side_idx}", r=0.07*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.15*scale), parent=sh, mat_=top_mat)
        cyl(f"{name}_fa{side_idx}", r=0.06*scale, depth=0.28*scale, segs=10,
            loc=(0, 0, -0.40*scale), parent=sh, mat_=M_SKIN_AZTEC)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07*scale, loc=(0, 0, -0.55*scale),
                      parent=sh, mat_=M_SKIN_AZTEC)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

people = []
# 4 paddlers on stern of each trajinera + 2 more
paddler_specs = [
    ("padd1", (-11, 3, 0.4), M_CLOTH_WHITE, M_PANTS_BROWN, True, math.radians(15)),
    ("padd2", (3, 4, 0.4), M_CLOTH_WHITE, M_PANTS_BROWN, True, math.radians(-15)),
    ("padd3", (-7, -2, 0.4), M_CLOTH_WHITE, M_PANTS_BROWN, True, math.radians(70)),
    ("padd4", (6, -1, 0.4), M_CLOTH_WHITE, M_PANTS_BROWN, True, math.radians(-80)),
    ("padd5", (-15, 0, 0.4), M_CLOTH_WHITE, M_PANTS_BROWN, True, math.radians(90)),
    ("padd6", (15, 2, 0.4), M_CLOTH_WHITE, M_PANTS_BROWN, True, math.radians(-90)),
]
for spec in paddler_specs:
    name, loc, top, pant, somb, fac = spec
    p = make_person(name, loc, top, pant, sombrero=somb, facing=fac, action="paddle")
    people.append(p)
    # Add paddle
    paddle_e = empty(f"{name}_paddle", (loc[0] + 0.5, loc[1] - 0.6, 0.8))
    cyl(f"{name}_pad_shaft", r=0.03, depth=1.4, segs=8, loc=(0, 0, 0),
        parent=paddle_e, mat_=M_PADDLE)
    beveled_cube(f"{name}_pad_blade", (0.25, 0.05, 0.30), bevel_offset=0.02,
                 loc=(0, 0, 0.85), parent=paddle_e, mat_=M_PADDLE)
    paddle_e.rotation_euler = (math.radians(45), 0, 0)
    paddle_e.parent = bpy.data.objects[name]

# Woman with tortillas + mortar (on chinampa)
woman = make_person("woman", (-12, 11, 0.5), M_HUIPIL_PINK, M_PANTS_BROWN,
                     sombrero=False, facing=math.radians(0), action="sit")
people.append(woman)
# Tortillas plate
cyl("tortilla_plate", r=0.20, depth=0.03, segs=14,
    loc=(-11.8, 10.5, 0.85), mat_=M_CORN_YELLOW)
for ti in range(3):
    cyl(f"tortilla{ti}", r=0.16, depth=0.02, segs=14,
        loc=(-11.8, 10.5, 0.88 + ti*0.025), mat_=M_CORN_YELLOW)
# Stone mortar (signature molcajete)
cyl("mortar_b", r=0.20, depth=0.18, segs=16, loc=(-12.4, 10.5, 0.85),
    mat_=M_JAGUAR_STONE)
cyl("mortar_in", r=0.16, depth=0.10, segs=16, loc=(-12.4, 10.5, 0.95),
    mat_=M_HUIPIL_RED)

# AZTEC DANCER (massive feather headdress signature)
dancer_e = empty("dancer", loc=(0, -15, 0))
dancer_e.rotation_euler = (0, 0, math.radians(180))
# Body (standing)
smooth_cone("d_legs", r1=0.32, r2=0.22, depth=0.95, segs=14,
            loc=(0, 0, 0.50), parent=dancer_e, mat_=M_PANTS_BROWN)
# Loincloth
beveled_cube("d_loin", (0.32, 0.20, 0.30), bevel_offset=0.03,
             loc=(0, 0, 1.00), parent=dancer_e, mat_=M_FEATHER_QUETZAL_RED)
# Torso (bare with breastplate)
beveled_cube("d_torso", (0.38, 0.22, 0.55), bevel_offset=0.05,
             loc=(0, 0, 1.45), parent=dancer_e, mat_=M_SKIN_AZTEC)
# GOLD BREASTPLATE (signature aztec ornament)
cyl("d_bp", r=0.18, depth=0.04, segs=18,
    loc=(0, -0.13, 1.55), parent=dancer_e, mat_=M_BREASTPLATE)
# Jade necklace
for nk in range(8):
    nka = math.pi + (nk - 4) * 0.20
    smooth_sphere(f"d_neck{nk}", r=0.04,
                  loc=(math.sin(nka)*0.18, -0.10, 1.80), parent=dancer_e, mat_=M_JADE_AZTEC)
# Neck
cyl("d_neck_c", r=0.09, depth=0.16, segs=10,
    loc=(0, 0, 1.85), parent=dancer_e, mat_=M_SKIN_AZTEC)
# Head
d_head_e = empty("d_he", (0, 0, 2.05), parent=dancer_e)
smooth_sphere("d_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
              parent=d_head_e, mat_=M_SKIN_AZTEC)
# Face paint (signature lines)
beveled_cube("d_paint_h", (0.30, 0.05, 0.02), loc=(0, -0.16, 0.05),
             parent=d_head_e, mat_=M_FACE_PAINT_RED)
beveled_cube("d_paint_v", (0.04, 0.05, 0.30), loc=(0, -0.16, 0),
             parent=d_head_e, mat_=M_FACE_PAINT_WHITE)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"d_eye{side}", r=0.022,
                  loc=(side*0.06, -0.14, 0.02), parent=d_head_e,
                  mat_=mat(f"d_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
# Hair
smooth_sphere("d_hair", r=0.19, loc=(0, 0.04, 0.04),
              parent=d_head_e, mat_=M_HAIR_AZTEC, scale=(1, 1, 0.85))
# MASSIVE FEATHER HEADDRESS FAN (signature Quetzal plume)
headdress_e = empty("headdress", (0, 0, 0.20), parent=d_head_e)
# 24 feathers radiating outward
feather_colors = [M_FEATHER_QUETZAL_GREEN, M_FEATHER_QUETZAL_BLUE,
                  M_FEATHER_QUETZAL_RED, M_FEATHER_GOLD]
for fi in range(24):
    fa = (fi / 24.0) * math.pi - math.pi/2  # 180° spread
    f_len = 1.6 - abs(fa - math.pi/2 + math.pi/2) * 0.15
    fea_e = empty(f"feather_e{fi}", (0, 0, 0), parent=headdress_e)
    fea_e.rotation_euler = (math.radians(-30), 0, fa)
    # Feather quill
    cyl(f"feather_quill{fi}", r=0.015, depth=f_len, segs=6,
        loc=(0, 0, f_len/2), parent=fea_e, mat_=feather_colors[fi % 4])
    # Feather vane
    beveled_cube(f"feather_vane{fi}", (0.10, 0.04, f_len), bevel_offset=0.01,
                 loc=(0, 0, f_len/2), parent=fea_e, mat_=feather_colors[fi % 4])
    # Eye marking near tip
    smooth_sphere(f"feather_eye{fi}", r=0.07,
                  loc=(0, 0, f_len - 0.1), parent=fea_e, mat_=feather_colors[(fi+2) % 4],
                  scale=(0.8, 0.3, 1))
# Inner ring of feathers (gold)
for ifi in range(12):
    ifa = (ifi / 12.0) * math.pi - math.pi/2
    f_e = empty(f"inner_f_e{ifi}", (0, 0, 0), parent=headdress_e)
    f_e.rotation_euler = (math.radians(-20), 0, ifa)
    beveled_cube(f"inner_f{ifi}", (0.06, 0.04, 0.50), bevel_offset=0.01,
                 loc=(0, 0, 0.30), parent=f_e, mat_=M_FEATHER_GOLD)
# Arms (raised in dance pose)
dancer_arms_e = []
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"d_sh{side_idx}", (side*0.30, 0, 1.78), parent=dancer_e)
    sh.rotation_euler = (math.radians(-130), 0, math.radians(side*-50))
    cyl(f"d_uarm{side_idx}", r=0.08, depth=0.35, segs=10,
        loc=(0, 0, -0.18), parent=sh, mat_=M_SKIN_AZTEC)
    cyl(f"d_fa{side_idx}", r=0.07, depth=0.30, segs=10,
        loc=(0, 0, -0.50), parent=sh, mat_=M_SKIN_AZTEC)
    smooth_sphere(f"d_hand{side_idx}", r=0.08, loc=(0, 0, -0.68),
                  parent=sh, mat_=M_SKIN_AZTEC)
    # Arm bracelets
    cyl(f"d_brac{side_idx}", r=0.10, depth=0.05, segs=12,
        loc=(0, 0, -0.30), parent=sh, mat_=M_FEATHER_GOLD)
    dancer_arms_e.append(sh)

# ============ 4 MARIACHI (charro suits + instruments) ============
def make_mariachi(name, loc, instrument, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Black charro pants
    smooth_cone(f"{name}_pants", r1=0.30, r2=0.22, depth=1.0, segs=14,
                loc=(0, 0, 0.50), parent=base, mat_=M_MARIACHI_BLACK)
    # Silver buttons down side (signature)
    for b in range(5):
        smooth_sphere(f"{name}_button{b}", r=0.025,
                      loc=(-0.32, 0, 0.20 + b*0.20), parent=base, mat_=M_MARIACHI_SILVER)
    # Jacket black
    beveled_cube(f"{name}_jacket", (0.40, 0.24, 0.60), bevel_offset=0.04,
                 loc=(0, 0, 1.30), parent=base, mat_=M_MARIACHI_BLACK)
    # White shirt collar
    cyl(f"{name}_collar", r=0.20, depth=0.05, segs=14,
        loc=(0, 0, 1.55), parent=base, mat_=M_CLOTH_WHITE)
    # Red bow tie (signature)
    beveled_cube(f"{name}_bow", (0.18, 0.05, 0.06), bevel_offset=0.01,
                 loc=(0, -0.13, 1.55), parent=base, mat_=M_BOWTIE_RED)
    # Neck
    cyl(f"{name}_neck", r=0.09, depth=0.15, segs=10,
        loc=(0, 0, 1.68), parent=base, mat_=M_SKIN_AZTEC)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.85), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_AZTEC)
    # Mustache (signature)
    smooth_sphere(f"{name}_must", r=0.10, loc=(0, -0.15, -0.06),
                  parent=head_e, mat_=M_HAIR_AZTEC, scale=(1.5, 0.6, 0.4))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.14, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # CHARRO SOMBRERO (signature wide-brim)
    cyl(f"{name}_somb_brim", r=0.45, depth=0.05, segs=20,
        loc=(0, 0, 0.20), parent=head_e, mat_=M_MARIACHI_BLACK)
    cyl(f"{name}_somb_crown", r=0.20, depth=0.25, segs=16,
        loc=(0, 0, 0.35), parent=head_e, mat_=M_MARIACHI_BLACK)
    # Silver band
    cyl(f"{name}_somb_band", r=0.21, depth=0.04, segs=16,
        loc=(0, 0, 0.25), parent=head_e, mat_=M_MARIACHI_SILVER)
    # Instrument
    inst_e = empty(f"{name}_inst_e", (0, -0.35, 1.15), parent=base)
    arms_e = []
    if instrument == "guitarron":
        # Large bass guitar
        smooth_sphere(f"{name}_g_body", r=0.30, segs=20, rings=14,
                      loc=(0, 0, 0), parent=inst_e, mat_=M_GUITAR_WOOD,
                      scale=(1, 0.7, 1.4))
        beveled_cube(f"{name}_g_neck", (0.08, 0.06, 0.80), bevel_offset=0.02,
                     loc=(0, -0.10, 0.60), parent=inst_e, mat_=M_GUITAR_WOOD)
        # Strings
        for st in range(6):
            cyl(f"{name}_g_str{st}", r=0.005, depth=1.0, segs=4,
                loc=((st-2.5)*0.02, -0.16, 0.30), parent=inst_e, mat_=M_MARIACHI_SILVER)
        # Arms play guitar
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.55), parent=base)
            sh.rotation_euler = (math.radians(-70 if side_idx == 0 else -90), 0,
                                  math.radians(side*-25 + (20 if side_idx == 1 else 0)))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_MARIACHI_BLACK)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_AZTEC)
            smooth_sphere(f"{name}_hand{side_idx}", r=0.07, loc=(0, 0, -0.58),
                          parent=sh, mat_=M_SKIN_AZTEC)
            arms_e.append(sh)
    elif instrument == "vihuela":
        # Smaller guitar
        smooth_sphere(f"{name}_v_body", r=0.22, segs=18, rings=12,
                      loc=(0, 0, 0), parent=inst_e, mat_=M_GUITAR_WOOD,
                      scale=(1, 0.6, 1.3))
        beveled_cube(f"{name}_v_neck", (0.06, 0.06, 0.60), bevel_offset=0.02,
                     loc=(0, -0.08, 0.45), parent=inst_e, mat_=M_GUITAR_WOOD)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.55), parent=base)
            sh.rotation_euler = (math.radians(-70 if side_idx == 0 else -90), 0,
                                  math.radians(side*-25 + (20 if side_idx == 1 else 0)))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_MARIACHI_BLACK)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_AZTEC)
            arms_e.append(sh)
    elif instrument == "trumpet":
        # Trumpet brass (signature)
        trumpet_e = empty(f"{name}_t_e", (0, -0.40, 0), parent=inst_e)
        cyl(f"{name}_t_main", r=0.04, depth=0.60, segs=10,
            loc=(0, 0, 0), parent=trumpet_e, mat_=M_TRUMPET_BRASS)
        # Bell flare
        smooth_cone(f"{name}_t_bell", r1=0.12, r2=0.05, depth=0.25, segs=14,
                    loc=(0, 0, 0.40), parent=trumpet_e, mat_=M_TRUMPET_BRASS)
        # Valves
        for v in range(3):
            cyl(f"{name}_t_v{v}", r=0.03, depth=0.10, segs=8,
                loc=(0, (v-1)*0.08, 0.05), parent=trumpet_e, mat_=M_TRUMPET_BRASS)
        # Arms (raised playing trumpet)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.55), parent=base)
            sh.rotation_euler = (math.radians(-110), 0, math.radians(side*-15))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_MARIACHI_BLACK)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_AZTEC)
            arms_e.append(sh)
    else:  # violin
        # Violin body
        smooth_sphere(f"{name}_vio_body", r=0.18, segs=16, rings=12,
                      loc=(0, 0, 0), parent=inst_e, mat_=M_GUITAR_WOOD,
                      scale=(1, 0.4, 1.5))
        beveled_cube(f"{name}_vio_neck", (0.04, 0.04, 0.40), bevel_offset=0.01,
                     loc=(0, -0.05, 0.30), parent=inst_e, mat_=M_GUITAR_WOOD)
        # Bow
        beveled_cube(f"{name}_bow_s", (0.012, 0.012, 0.60), bevel_offset=0.005,
                     loc=(0.30, -0.10, 0.10), parent=inst_e, mat_=M_PADDLE)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.55), parent=base)
            sh.rotation_euler = (math.radians(-110 if side_idx == 0 else -90), 0,
                                  math.radians(side*-15))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_MARIACHI_BLACK)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_AZTEC)
            arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

mariachi = []
mar_specs = [
    ("mar1", (-3, -18, 0.5), "guitarron", math.radians(0)),
    ("mar2", (-1, -18, 0.5), "vihuela", math.radians(0)),
    ("mar3", (1, -18, 0.5), "trumpet", math.radians(0)),
    ("mar4", (3, -18, 0.5), "violin", math.radians(0)),
]
for spec in mar_specs:
    name, loc, inst, fac = spec
    m = make_mariachi(name, loc, inst, facing=fac)
    mariachi.append(m)

# ============ SWANS + FLAMINGOS + DUCKS ============
def make_swan(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.40, segs=20, rings=14, loc=(0, 0, 0.20),
                  parent=base, mat_=M_SWAN, scale=(1.5, 1, 1))
    # Long S-curved neck (signature swan)
    neck_e = empty(f"{name}_neck_e", (0.40, 0, 0.40), parent=base)
    for ni in range(6):
        sk_x = math.sin(ni * 0.5) * 0.12
        cyl(f"{name}_neck{ni}", r=0.08, depth=0.20, segs=10,
            loc=(sk_x, 0, ni*0.18), parent=neck_e, mat_=M_SWAN)
    # Head
    smooth_sphere(f"{name}_head", r=0.12, loc=(0, 0, 1.20),
                  parent=neck_e, mat_=M_SWAN)
    # Beak (orange)
    smooth_cone(f"{name}_beak", r1=0.05, r2=0.01, depth=0.15, segs=10,
                loc=(0.12, 0, 1.15), parent=neck_e,
                mat_=M_SWAN_BEAK).rotation_euler = (0, math.radians(90), 0)
    # Black knob at beak base (signature)
    smooth_sphere(f"{name}_knob", r=0.04, loc=(0.04, 0, 1.20),
                  parent=neck_e, mat_=M_MARIACHI_BLACK)
    # Eyes
    smooth_sphere(f"{name}_eye", r=0.02, loc=(0.06, 0.08, 1.22),
                  parent=neck_e, mat_=M_MARIACHI_BLACK)
    # Wings folded
    for side in (-1, 1):
        beveled_cube(f"{name}_wing{side}", (0.30, 0.30, 0.50), bevel_offset=0.04,
                     loc=(0, side*0.20, 0.35), parent=base, mat_=M_SWAN)
    return {"root": base}

def make_flamingo(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body pink
    smooth_sphere(f"{name}_body", r=0.25, segs=18, rings=12, loc=(0, 0, 1.10),
                  parent=base, mat_=M_FLAMINGO_PINK, scale=(1.6, 1, 1))
    # Wing accent darker pink
    smooth_sphere(f"{name}_wing_acc", r=0.18, loc=(-0.10, 0, 1.20),
                  parent=base, mat_=M_FLAMINGO_PINK_DEEP, scale=(1.5, 0.7, 0.6))
    # S-neck
    neck_e = empty(f"{name}_neck_e", (0.30, 0, 1.20), parent=base)
    for ni in range(8):
        sk_x = math.sin(ni * 0.5) * 0.12
        cyl(f"{name}_neck{ni}", r=0.05, depth=0.14, segs=10,
            loc=(sk_x, 0, ni*0.13), parent=neck_e, mat_=M_FLAMINGO_PINK)
    # Head
    smooth_sphere(f"{name}_head", r=0.08, loc=(0, 0, 1.05),
                  parent=neck_e, mat_=M_FLAMINGO_PINK)
    # Curved beak (signature pink with black tip)
    beak = smooth_cone(f"{name}_beak", r1=0.04, r2=0.01, depth=0.18, segs=10,
                       loc=(0.08, 0, 0.95), parent=neck_e, mat_=M_FLAMINGO_PINK)
    beak.rotation_euler = (0, math.radians(50), 0)
    smooth_cone(f"{name}_beak_tip", r1=0.02, r2=0.005, depth=0.06, segs=8,
                loc=(0.18, 0, 0.85), parent=neck_e,
                mat_=M_MARIACHI_BLACK).rotation_euler = (0, math.radians(70), 0)
    # 1 long leg (signature - other tucked)
    cyl(f"{name}_leg", r=0.03, depth=1.0, segs=8,
        loc=(0, 0, 0.50), parent=base, mat_=M_FLAMINGO_PINK)
    # Foot
    beveled_cube(f"{name}_foot", (0.12, 0.10, 0.03), loc=(0, 0, 0.0),
                 parent=base, mat_=M_FLAMINGO_PINK)
    return {"root": base}

# Birds
swans = []
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    rad = random.uniform(8, 15)
    sx = rad * math.cos(a)
    sy = rad * math.sin(a) - 5
    swan = make_swan(f"swan{i}", (sx, sy, 0.1), math.radians(random.uniform(-180, 180)))
    swans.append(swan)
flamingos = []
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    rad = random.uniform(12, 18)
    fx = rad * math.cos(a)
    fy = rad * math.sin(a) + 3
    flam = make_flamingo(f"flam{i}", (fx, fy, 0), math.radians(random.uniform(-180, 180)))
    flamingos.append(flam)

# 6 ducks
for i in range(6):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 18)
    dx = rad * math.cos(a)
    dy = rad * math.sin(a)
    d_e = empty(f"duck{i}", (dx, dy, 0.1))
    d_e.rotation_euler = (0, 0, math.radians(random.uniform(-180, 180)))
    col = M_DUCK_BROWN if i % 2 == 0 else M_DUCK_GREEN
    smooth_sphere(f"duck_body{i}", r=0.15, segs=16, rings=10, loc=(0, 0, 0.15),
                  parent=d_e, mat_=col, scale=(1.6, 1, 1))
    smooth_sphere(f"duck_head{i}", r=0.10, loc=(0.20, 0, 0.30),
                  parent=d_e, mat_=col)
    smooth_cone(f"duck_beak{i}", r1=0.04, r2=0.02, depth=0.10, segs=8,
                loc=(0.30, 0, 0.28), parent=d_e,
                mat_=M_SWAN_BEAK).rotation_euler = (0, math.radians(90), 0)

# 8 LILY PADS + FLOWERS
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = random.uniform(6, 16)
    lx = rad * math.cos(a) + random.uniform(-1, 1)
    ly = rad * math.sin(a) + random.uniform(-1, 1)
    l_e = empty(f"lily{i}", (lx, ly, 0.1))
    # Pad (flat)
    smooth_sphere(f"lily_pad{i}", r=0.45, loc=(0, 0, 0),
                  parent=l_e, mat_=M_LILY_LEAF, scale=(1, 1, 0.12))
    # Flower (signature pink)
    flower_col = M_LILY_FLOWER if i % 2 == 0 else M_LILY_FLOWER_PINK
    for petal in range(8):
        pa = (petal / 8.0) * math.pi * 2
        beveled_cube(f"lily_p{i}_{petal}", (0.08, 0.05, 0.15), bevel_offset=0.02,
                     loc=(0.10*math.cos(pa), 0.10*math.sin(pa), 0.08),
                     parent=l_e, mat_=flower_col).rotation_euler = (math.radians(20), 0, pa)
    smooth_sphere(f"lily_c{i}", r=0.05, loc=(0, 0, 0.12),
                  parent=l_e, mat_=M_PETAL_YELLOW)

# ============ WEEPING WILLOW (signature) ============
willow_e = empty("willow", loc=(-20, -3, 0))
# Trunk leaning
cyl("w_trunk", r=0.50, depth=5.0, segs=14, loc=(0, 0, 2.5),
    parent=willow_e, mat_=M_WILLOW_TRUNK).rotation_euler = (math.radians(15), 0, 0)
# 6 cascading branches
for bi in range(6):
    ba = (bi / 6.0) * math.pi * 2
    b_e = empty(f"w_b_e{bi}", (math.cos(ba)*0.5, math.sin(ba)*0.5, 5.0), parent=willow_e)
    b_e.rotation_euler = (math.radians(30), 0, ba)
    # Branch arc
    for sk in range(4):
        cyl(f"w_b{bi}_{sk}", r=0.10 - sk*0.018, depth=0.50, segs=8,
            loc=(0, sk*0.50, sk*-0.20), parent=b_e, mat_=M_WILLOW_TRUNK)
    # Weeping leaves cascade (signature)
    for hi in range(5):
        ha = (hi - 2) * 0.3
        for sk in range(8):
            smooth_sphere(f"w_l{bi}_{hi}_{sk}", r=random.uniform(0.08, 0.15),
                          loc=(ha + sk*0.05, 2 + sk*0.20, -sk*0.30 - 0.20),
                          parent=b_e, mat_=M_WILLOW_LEAF, scale=(0.8, 1.4, 0.5))

# ============================================================
# ⭐ 600 HUMMINGBIRDS + 300 FLOATING PETALS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 hummingbirds (signature Mexico high-speed wing flap)
def make_hummingbird(name, loc, body_col):
    base = empty(name, loc)
    smooth_sphere(f"{name}_body", r=0.10, segs=10, rings=6, loc=(0, 0, 0),
                  parent=base, mat_=body_col, scale=(1.5, 1, 1))
    smooth_sphere(f"{name}_head", r=0.06, loc=(0.10, 0, 0.02),
                  parent=base, mat_=body_col)
    # Long beak (signature)
    smooth_cone(f"{name}_beak", r1=0.015, r2=0.003, depth=0.12, segs=6,
                loc=(0.22, 0, 0.0), parent=base,
                mat_=M_MARIACHI_BLACK).rotation_euler = (0, math.radians(90), 0)
    # Wings (translucent - signature ultra-fast flap)
    wings = []
    for side in (-1, 1):
        w_e = empty(f"{name}_we{side}", (0, side*0.05, 0.02), parent=base)
        beveled_cube(f"{name}_w{side}", (0.06, 0.18, 0.008), bevel_offset=0.003,
                     loc=(-0.02, side*0.13, 0.02), parent=w_e, mat_=M_HUMMING_WING)
        wings.append((w_e, side))
    return {"root": base, "wings": wings}

humming_colors = [M_HUMMING_GREEN, M_HUMMING_BLUE, M_HUMMING_PURPLE, M_HUMMING_RUBY]
hummingbirds = []
for i in range(600):
    px = random.uniform(-40, 40)
    py = random.uniform(-40, 40)
    pz = random.uniform(0.5, 10)
    col = humming_colors[i % 4]
    h = make_hummingbird(f"h{i}", (px, py, pz), col)
    h["root"]["_phase"] = random.uniform(0, math.pi*2)
    h["root"]["_base_x"] = px; h["root"]["_base_y"] = py; h["root"]["_base_z"] = pz
    h["root"]["_amp_x"] = random.uniform(1.0, 2.5)
    h["root"]["_amp_y"] = random.uniform(1.0, 2.5)
    h["root"]["_amp_z"] = random.uniform(0.5, 1.5)
    h["root"]["_speed"] = random.uniform(0.8, 1.6)
    hummingbirds.append(h)

# 300 floating petals on water (signature)
petal_colors = [M_PETAL_PINK, M_PETAL_RED, M_PETAL_YELLOW, M_PETAL_ORANGE, M_PETAL_WHITE]
floating_petals = []
for i in range(300):
    px = random.uniform(-40, 40)
    py = random.uniform(-40, 40)
    pz = 0.20  # On water surface
    col = petal_colors[i % 5]
    p_obj = smooth_sphere(f"fp{i}", r=random.uniform(0.10, 0.18), segs=10, rings=6,
                          loc=(px, py, pz), mat_=col,
                          scale=(1.6, 0.7, 0.10))
    p_obj.rotation_euler = (0, 0, random.uniform(0, math.pi*2))
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py
    p_obj["_amp"] = random.uniform(0.6, 1.6)
    p_obj["_speed"] = random.uniform(0.3, 0.7)
    floating_petals.append(p_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Trajineras drift on water
for t in trajineras:
    phase = t["_phase"]
    base_x = t.location.x
    base_y = t.location.y
    for f in range(1, total_frames + 1, 4):
        t_v = (f - 1) / fps
        t.location = (base_x + math.sin(t_v * 0.4 + phase) * 1.5,
                       base_y + math.cos(t_v * 0.3 + phase) * 1.0,
                       math.sin(t_v * 1.5 + phase) * 0.05)
        t.rotation_euler = (math.sin(t_v * 1.0 + phase) * math.radians(3),
                             math.cos(t_v * 0.8 + phase) * math.radians(2.5),
                             t.rotation_euler.z + math.sin(t_v * 0.5) * math.radians(2))
        t.keyframe_insert("location", frame=f)
        t.keyframe_insert("rotation_euler", frame=f)

# Paddlers paddle motion
for p in people[:6]:  # first 6 are paddlers
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Paddle stroke
        for ai, arm in enumerate(p["arms"]):
            base_rx = arm.rotation_euler.x
            stroke = math.sin(t * 3.0 + phase + ai * math.pi) * math.radians(35)
            arm.rotation_euler = (base_rx + stroke, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        # Body lean
        p["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(8),
                                     math.cos(t * 2.5 + phase) * math.radians(4),
                                     p["root"].rotation_euler.z)
        p["root"].keyframe_insert("rotation_euler", frame=f)

# Dancer twirls
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    dancer_e.rotation_euler = (math.sin(t * 1.0) * math.radians(8), 0,
                                 math.radians(180) + t * 1.0)
    dancer_e.keyframe_insert("rotation_euler", frame=f)
    # Headdress feathers undulate
    headdress_e.rotation_euler = (math.sin(t * 2.0) * math.radians(5), 0,
                                    math.cos(t * 1.5) * math.radians(3))
    headdress_e.keyframe_insert("rotation_euler", frame=f)
    # Arms wave
    for ai, arm in enumerate(dancer_arms_e):
        wave = math.sin(t * 3.0 + ai * math.pi) * math.radians(20)
        arm.rotation_euler = (math.radians(-130) + wave, 0, math.radians((-1 if ai == 0 else 1)*-50))
        arm.keyframe_insert("rotation_euler", frame=f)

# Mariachi play instruments
for m in mariachi:
    phase = m["root"]["_phase"]
    base_z = m["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        m["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        m["root"].keyframe_insert("location", frame=f)
        for ai, arm in enumerate(m["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 4.0 + phase + ai * math.pi) * math.radians(15)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(8), 0,
                                    math.sin(t * 1.2 + phase) * math.radians(15))
        m["he"].keyframe_insert("rotation_euler", frame=f)

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

# Sun halos
for obj in bpy.data.objects:
    if obj.name.startswith("sun_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.7) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 600 HUMMINGBIRDS hover ultra-fast wings (signature)
# ============================================================
for h in hummingbirds:
    e = h["root"]
    phase = e["_phase"]; speed = e["_speed"]
    bx, by, bz = e["_base_x"], e["_base_y"], e["_base_z"]
    ax, ay, az = e["_amp_x"], e["_amp_y"], e["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Hover + dart
        x = bx + ax * math.sin(t * speed + phase) + 0.2*math.sin(t * speed * 4 + phase * 2)
        y = by + ay * math.cos(t * speed * 0.9 + phase) + 0.2*math.cos(t * speed * 4 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase * 1.5)
        e.location = (x, y, max(0.3, z))
        e.rotation_euler = (0, 0, math.atan2(math.cos(t * speed * 0.9 + phase),
                                              math.sin(t * speed + phase)))
        e.keyframe_insert("location", frame=f)
        e.keyframe_insert("rotation_euler", frame=f)
        # ULTRA-FAST wing flap (signature hummingbird)
        flap = math.sin(t * 30.0 + phase) * math.radians(45)
        for w_e, side in h["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)

# 300 floating petals on water
for p in floating_petals:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by = p["_base_x"], p["_base_y"]
    amp = p["_amp"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        # Drift on surface (slow)
        x = bx + amp * math.sin(t * speed + phase)
        y = by + amp * math.cos(t * speed * 0.9 + phase)
        z = 0.20 + math.sin(t * 1.5 + phase) * 0.05  # subtle bob
        p.location = (x, y, z)
        # Slow rotation
        p.rotation_euler = (0, 0, p.rotation_euler.z + t * 0.3)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_aztec_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_aztec_chinampa_xochimilco] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_aztec_chinampa_xochimilco] ONE water + Templo Mayor + 12 chinampas + 4 trajineras flowers + 6 paddlers + woman tortillas + Aztec dancer headdress 24 feathers + 4 mariachi + swans + flamingos + ducks + lilies + willow + 600 HUMMINGBIRDS + 300 PETALS")
print("⭐ FIXES: 1 ground + 600 hummingbirds ultra-fast wings + 300 floating petals (signature Mexico Aztec mandatory) ⭐")
