"""
proc_provence_lavender_fields.py — 221e procédural AuroraIA (85e qualité)
Provence lavender: ONE ground + 600 butterflies + 400 pollen + 500 lavender rows + 5 cypress + mas provençal + 4 sunflowers + cigales + bees + 2 paysans + dog
FIXES : 1 ground + 600 butterflies + 400 pollen thématiques signature Provence
"""
import bpy, bmesh, math, random, os

random.seed(0x2A0EE221)

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

# Provence Mediterranean palette - bright summer noon
M_SKY = mat("sky", (0.45, 0.72, 0.95, 1.0), 0.0, 0.7, emission=(0.40,0.68,0.92), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.95, 0.65, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.65), emission_strength=22.0)
M_CLOUD = mat("cloud", (1.0, 1.0, 0.98, 1.0), 0.0, 0.55, emission=(0.95,0.95,0.95), emission_strength=2.0, alpha=0.85)

# Ground
M_EARTH = mat("earth", (0.45, 0.32, 0.20, 1.0), 0.0, 0.85, emission=(0.40,0.30,0.18), emission_strength=0.3)
M_PATH = mat("path", (0.65, 0.50, 0.32, 1.0), 0.0, 0.75, emission=(0.60,0.45,0.30), emission_strength=0.4)
M_STONE = mat("stone", (0.55, 0.50, 0.42, 1.0), 0.0, 0.85)

# Lavender colors (signature purple field)
M_LAV_PURPLE = mat("lav_p", (0.55, 0.25, 0.78, 1.0), 0.0, 0.50, emission=(0.50,0.22,0.72), emission_strength=1.5)
M_LAV_VIOLET = mat("lav_v", (0.45, 0.20, 0.85, 1.0), 0.0, 0.50, emission=(0.42,0.18,0.78), emission_strength=1.7)
M_LAV_PINK_PURPLE = mat("lav_pp", (0.65, 0.35, 0.85, 1.0), 0.0, 0.50, emission=(0.60,0.32,0.78), emission_strength=1.6)
M_LAV_STEM = mat("lav_s", (0.35, 0.55, 0.30, 1.0), 0.0, 0.70, emission=(0.30,0.50,0.28), emission_strength=0.4)
M_LAV_LEAF = mat("lav_l", (0.55, 0.70, 0.45, 1.0), 0.0, 0.65, emission=(0.50,0.65,0.42), emission_strength=0.5)

# Cypress (tall narrow signature Provence)
M_CYPRESS = mat("cypress", (0.18, 0.32, 0.20, 1.0), 0.0, 0.70, emission=(0.15,0.28,0.18), emission_strength=0.4)
M_CYPRESS_BRIGHT = mat("cypress_br", (0.25, 0.45, 0.25, 1.0), 0.0, 0.65, emission=(0.22,0.40,0.22), emission_strength=0.5)
M_CYPRESS_TRUNK = mat("cypress_t", (0.35, 0.22, 0.12, 1.0), 0.0, 0.80)

# Mas provençal (stone farmhouse)
M_WALL_STONE = mat("wall_s", (0.85, 0.75, 0.55, 1.0), 0.0, 0.70, emission=(0.78,0.70,0.50), emission_strength=0.5)
M_WALL_OCHRE = mat("wall_o", (0.92, 0.72, 0.42, 1.0), 0.0, 0.65, emission=(0.85,0.68,0.40), emission_strength=0.6)
M_ROOF_TILE = mat("roof_t", (0.65, 0.30, 0.18, 1.0), 0.0, 0.70, emission=(0.60,0.28,0.16), emission_strength=0.4)
M_SHUTTER = mat("shutter", (0.20, 0.45, 0.65, 1.0), 0.0, 0.65, emission=(0.18,0.40,0.60), emission_strength=0.5)
M_DOOR = mat("door", (0.40, 0.25, 0.15, 1.0), 0.0, 0.75)
M_WINDOW_GLASS = mat("win", (0.85, 0.92, 0.95, 1.0), 0.0, 0.10, emission=(0.78,0.85,0.92), emission_strength=0.8, alpha=0.85)
M_CHIMNEY = mat("chimney", (0.75, 0.60, 0.40, 1.0), 0.0, 0.80, emission=(0.70,0.55,0.38), emission_strength=0.3)

# Sunflowers signature
M_SUNFLOWER_YELLOW = mat("sf_y", (1.0, 0.82, 0.20, 1.0), 0.0, 0.40, emission=(1.0,0.82,0.20), emission_strength=2.5)
M_SUNFLOWER_BROWN = mat("sf_b", (0.55, 0.30, 0.10, 1.0), 0.0, 0.70, emission=(0.50,0.28,0.10), emission_strength=0.6)
M_SUNFLOWER_STEM = mat("sf_s", (0.30, 0.55, 0.25, 1.0), 0.0, 0.65)
M_SUNFLOWER_LEAF = mat("sf_leaf", (0.25, 0.55, 0.22, 1.0), 0.0, 0.65, emission=(0.22,0.50,0.20), emission_strength=0.4)

# Paysans
M_SKIN_PROV = mat("skin", (0.95, 0.78, 0.60, 1.0), 0.0, 0.55, emission=(0.88,0.72,0.55), emission_strength=0.4)
M_LINEN_WHITE = mat("linen_w", (0.92, 0.88, 0.78, 1.0), 0.0, 0.70, emission=(0.85,0.82,0.72), emission_strength=0.5)
M_LINEN_BLUE = mat("linen_b", (0.30, 0.45, 0.65, 1.0), 0.0, 0.65, emission=(0.28,0.42,0.60), emission_strength=0.5)
M_STRAW_HAT = mat("straw", (0.92, 0.78, 0.42, 1.0), 0.0, 0.75, emission=(0.85,0.72,0.40), emission_strength=0.6)
M_PANT_BROWN = mat("pant", (0.45, 0.30, 0.18, 1.0), 0.0, 0.75, emission=(0.42,0.28,0.16), emission_strength=0.3)
M_HAIR_PAYSAN = mat("hair_p", (0.45, 0.28, 0.18, 1.0), 0.0, 0.85)

# Sheep dog (Berger)
M_DOG_WHITE = mat("dog_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.82), emission_strength=0.4)
M_DOG_BLACK = mat("dog_b", (0.10, 0.08, 0.08, 1.0), 0.0, 0.80)
M_DOG_PINK = mat("dog_p", (1.0, 0.55, 0.55, 1.0), 0.0, 0.50, emission=(0.90,0.50,0.50), emission_strength=0.3)

# Bee
M_BEE_YELLOW = mat("bee_y", (1.0, 0.85, 0.15, 1.0), 0.0, 0.40, emission=(1.0,0.85,0.15), emission_strength=2.5)
M_BEE_BLACK = mat("bee_b", (0.08, 0.06, 0.04, 1.0), 0.0, 0.75)
M_BEE_WING = mat("bee_w", (0.95, 0.95, 0.98, 0.55), 0.0, 0.10, emission=(0.85,0.85,0.92), emission_strength=1.0, alpha=0.55)

# Cicadas
M_CICADA = mat("cicada", (0.55, 0.45, 0.20, 1.0), 0.0, 0.55, emission=(0.50,0.42,0.18), emission_strength=0.5)
M_CICADA_WING = mat("c_wing", (0.85, 0.78, 0.65, 0.65), 0.0, 0.20, emission=(0.78,0.72,0.60), emission_strength=0.5, alpha=0.65)

# Hive
M_HIVE = mat("hive", (0.85, 0.55, 0.20, 1.0), 0.0, 0.65, emission=(0.78,0.50,0.18), emission_strength=0.5)

# Butterflies (signature Provence)
M_BUTTER_MONARCH = mat("bm", (1.0, 0.45, 0.10, 1.0), 0.0, 0.40, emission=(1.0,0.45,0.10), emission_strength=3.0)
M_BUTTER_BLUE = mat("bb", (0.20, 0.55, 0.95, 1.0), 0.0, 0.40, emission=(0.20,0.55,0.95), emission_strength=3.0)
M_BUTTER_WHITE = mat("bw", (0.98, 0.95, 0.88, 1.0), 0.0, 0.40, emission=(0.95,0.92,0.85), emission_strength=2.5)
M_BUTTER_YELLOW = mat("by", (1.0, 0.92, 0.30, 1.0), 0.0, 0.40, emission=(1.0,0.92,0.30), emission_strength=3.0)
M_BUTTER_PINK = mat("bpink", (1.0, 0.55, 0.85, 1.0), 0.0, 0.40, emission=(1.0,0.55,0.85), emission_strength=2.8)
M_BUTTER_BODY = mat("bbody", (0.30, 0.18, 0.10, 1.0), 0.0, 0.65)

# Pollen (signature golden floating)
M_POLLEN = mat("pollen", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=15.0)
M_POLLEN_DEEP = mat("pollen_d", (1.0, 0.78, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.78,0.20), emission_strength=14.0)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (15, 45, 35))
smooth_sphere("sun", r=5.5, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=5.5 + (i+1)*1.8, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

# 8 fluffy cumulus clouds
clouds = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = random.uniform(30, 42)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(24, 32)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(6):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ ONE clean earth ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_EARTH)

# Earth path winding (organic 3D scattered stones)
for i in range(30):
    px = (i - 15) * 1.6
    py = math.sin(i * 0.25) * 3
    smooth_sphere(f"path_stone{i}", r=random.uniform(0.30, 0.55), segs=14, rings=10,
                  loc=(px, py, 0.10), mat_=M_PATH,
                  scale=(1.4, 1.0, 0.30))

# 25 scattered field stones
for i in range(25):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(15, 40)
    smooth_sphere(f"rock{i}", r=random.uniform(0.40, 0.75),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_STONE,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.8)))

# ============ 500 LAVENDER PLANTS IN ROWS (signature geometric purple field) ============
lavender_objs = []
# 20 rows of 25 plants
for row in range(20):
    row_y = (row - 10) * 1.8
    for col in range(25):
        col_x = (col - 12) * 1.5
        # Slight randomness
        lx = col_x + random.uniform(-0.1, 0.1)
        ly = row_y + random.uniform(-0.1, 0.1)
        # Skip plants too close to path or near mas
        if abs(ly) < 1.5 and abs(lx) < 18:
            continue
        if 12 < lx < 22 and 6 < ly < 16:  # Mas area
            continue
        if -22 < lx < -10 and -15 < ly < -8:  # cypress row
            continue
        lav_e = empty(f"lav_{row}_{col}", (lx, ly, 0))
        # Stem
        cyl(f"lav_s_{row}_{col}", r=0.025, depth=0.6, segs=6,
            loc=(0, 0, 0.30), parent=lav_e, mat_=M_LAV_STEM)
        # Leaves (silvery green at base)
        for li in range(4):
            la = (li / 4.0) * math.pi * 2
            leaf = beveled_cube(f"lav_l_{row}_{col}_{li}", (0.04, 0.18, 0.02), bevel_offset=0.01,
                                loc=(0.05*math.cos(la), 0.05*math.sin(la), 0.20),
                                parent=lav_e, mat_=M_LAV_LEAF)
            leaf.rotation_euler = (0, 0, la)
        # Flower spike (signature lavender wand)
        col_idx = random.randint(0, 2)
        flower_col = [M_LAV_PURPLE, M_LAV_VIOLET, M_LAV_PINK_PURPLE][col_idx]
        for fi in range(6):
            f_z = 0.65 + fi * 0.07
            f_r = 0.045 - fi * 0.004
            smooth_sphere(f"lav_f_{row}_{col}_{fi}", r=f_r,
                          loc=(0, 0, f_z), parent=lav_e, mat_=flower_col,
                          scale=(1.3, 1.3, 0.7))
        # Top spike
        smooth_cone(f"lav_tip_{row}_{col}", r1=0.035, r2=0.005, depth=0.10, segs=8,
                    loc=(0, 0, 1.10), parent=lav_e, mat_=flower_col)
        lav_e["_phase"] = random.uniform(0, math.pi*2)
        lavender_objs.append(lav_e)

# ============ 5 CYPRESS (tall narrow signature Provence) ============
cypress_pos = [(-15, -12, 0), (-15, -8, 0), (-15, -4, 0), (-15, 0, 0), (-15, 4, 0)]
cypress_objs = []
for i, (cx, cy, cz) in enumerate(cypress_pos):
    base = empty(f"cypress{i}", (cx, cy, cz))
    # Tall narrow trunk
    cyl(f"cyp_trunk{i}", r=0.18, depth=1.0, segs=12,
        loc=(0, 0, 0.5), parent=base, mat_=M_CYPRESS_TRUNK)
    # Foliage - very tall narrow cone (signature)
    cone_h = 7
    for layer in range(7):
        l_z = 1.5 + layer * 0.9
        r1 = 0.7 - layer * 0.08
        r2 = 0.6 - layer * 0.08
        col = M_CYPRESS if layer % 2 == 0 else M_CYPRESS_BRIGHT
        smooth_cone(f"cyp_l{i}_{layer}", r1=r1, r2=r2, depth=1.0, segs=14,
                    loc=(0, 0, l_z), parent=base, mat_=col)
    # Top tapered
    smooth_cone(f"cyp_top{i}", r1=0.3, r2=0.05, depth=1.2, segs=12,
                loc=(0, 0, 8.5), parent=base, mat_=M_CYPRESS)
    base["_phase"] = random.uniform(0, math.pi*2)
    cypress_objs.append(base)

# ============ MAS PROVENÇAL (stone farmhouse) ============
mas_e = empty("mas", loc=(17, 12, 0))
mas_e.rotation_euler = (0, 0, math.radians(-25))
# Stone base
beveled_cube("mas_base", (8, 6, 0.6), bevel_offset=0.06, loc=(0, 0, 0.30),
             parent=mas_e, mat_=M_WALL_STONE)
# Main walls (ochre + stone signature)
beveled_cube("mas_walls", (7.5, 5.5, 3.5), bevel_offset=0.06, loc=(0, 0, 2.35),
             parent=mas_e, mat_=M_WALL_OCHRE)
# Stone corners (signature exposed)
for x_idx, x in enumerate((-3.5, 3.5)):
    for y_idx, y in enumerate((-2.5, 2.5)):
        beveled_cube(f"mas_corner_{x_idx}{y_idx}", (0.4, 0.4, 3.5), bevel_offset=0.04,
                     loc=(x, y, 2.35), parent=mas_e, mat_=M_WALL_STONE)
# Roof (terracotta tiles - signature)
for side, side_mul in zip(("L", "R"), (-1, 1)):
    roof = beveled_cube(f"mas_roof_{side}", (8.5, 3.5, 0.25), bevel_offset=0.04,
                       loc=(0, side_mul*1.5, 4.5), parent=mas_e, mat_=M_ROOF_TILE)
    roof.rotation_euler = (math.radians(side_mul*-25), 0, 0)
# Roof ridge
beveled_cube("mas_ridge", (8.5, 0.3, 0.20), bevel_offset=0.03,
             loc=(0, 0, 5.5), parent=mas_e, mat_=M_ROOF_TILE)
# Roof tile detail rows (signature ridges)
for tile_row in range(8):
    cyl(f"mas_tile_{tile_row}", r=0.06, depth=8.0, segs=8,
        loc=(0, -2.4 + tile_row * 0.6, 4.3 - tile_row * 0.05), parent=mas_e,
        mat_=M_ROOF_TILE).rotation_euler = (0, math.radians(90), 0)
# Chimney
beveled_cube("mas_chimney", (0.50, 0.50, 1.8), bevel_offset=0.04,
             loc=(-2.5, 0, 5.8), parent=mas_e, mat_=M_CHIMNEY)
beveled_cube("mas_chimney_top", (0.65, 0.65, 0.20), bevel_offset=0.03,
             loc=(-2.5, 0, 6.80), parent=mas_e, mat_=M_CHIMNEY)
# Door (wooden)
beveled_cube("mas_door", (1.2, 0.20, 2.4), bevel_offset=0.04,
             loc=(0, -2.85, 1.5), parent=mas_e, mat_=M_DOOR)
# Door details
for fi in range(4):
    beveled_cube(f"mas_door_p{fi}", (1.0, 0.04, 0.30),
                 loc=(0, -2.95, 0.5 + fi*0.55), parent=mas_e, mat_=M_DOOR)
# 4 windows (with blue shutters signature)
for win_i in range(4):
    wx = -3.0 + (win_i % 2) * 6.0
    wy_idx = win_i // 2
    wy = -2.85 if wy_idx == 0 else 2.85
    wz = 2.5
    # Window glass
    beveled_cube(f"mas_win_{win_i}", (0.90, 0.10, 0.90), bevel_offset=0.03,
                 loc=(wx, wy, wz), parent=mas_e, mat_=M_WINDOW_GLASS)
    # Frame
    for fi in range(2):
        beveled_cube(f"mas_win_fr_h{win_i}_{fi}", (1.0, 0.06, 0.05),
                     loc=(wx, wy - 0.02 * (1 if wy < 0 else -1), 2.05 + fi*0.90),
                     parent=mas_e, mat_=M_DOOR)
        beveled_cube(f"mas_win_fr_v{win_i}_{fi}", (0.05, 0.06, 1.0),
                     loc=(wx + (fi-0.5)*0.95, wy - 0.02 * (1 if wy < 0 else -1), wz),
                     parent=mas_e, mat_=M_DOOR)
    # Blue shutters (signature provençal)
    for side in (-1, 1):
        beveled_cube(f"mas_shut_{win_i}_{side}", (0.50, 0.05, 1.0), bevel_offset=0.02,
                     loc=(wx + side*0.65, wy - 0.05 * (1 if wy < 0 else -1), wz),
                     parent=mas_e, mat_=M_SHUTTER)
# Steps
for i in range(2):
    beveled_cube(f"mas_step{i}", (1.5, 0.4, 0.20), bevel_offset=0.03,
                 loc=(0, -3.4 - i*0.4, 0.10 + i*0.20), parent=mas_e, mat_=M_WALL_STONE)
# Geranium pots on windowsills
for win_i in range(4):
    wx = -3.0 + (win_i % 2) * 6.0
    wy_idx = win_i // 2
    wy = -3.0 if wy_idx == 0 else 3.0
    # Pot
    cyl(f"mas_pot_{win_i}", r=0.18, depth=0.20, segs=14,
        loc=(wx, wy, 1.85), parent=mas_e, mat_=M_ROOF_TILE)
    # Geraniums (red)
    for ge in range(3):
        ga = ge * 2.1
        smooth_sphere(f"mas_ger_{win_i}_{ge}", r=0.08,
                      loc=(wx + math.cos(ga)*0.08, wy + math.sin(ga)*0.08, 2.05),
                      parent=mas_e, mat_=mat(f"ger_m{win_i}_{ge}", (1.0, 0.30, 0.30, 1), 0, 0.45,
                                                emission=(0.95,0.30,0.30), emission_strength=1.5))

# ============ 4 SUNFLOWERS (giant signature) ============
def make_sunflower(name, loc, scale=1.0):
    base = empty(name, loc)
    # Tall stem
    cyl(f"{name}_stem", r=0.10*scale, depth=2.8*scale, segs=14,
        loc=(0, 0, 1.4*scale), parent=base, mat_=M_SUNFLOWER_STEM)
    # 5 leaves
    for li in range(5):
        l_z = 0.5 + li * 0.50
        l_a = (li / 5.0) * math.pi * 2
        leaf = beveled_cube(f"{name}_leaf{li}", (0.35*scale, 0.18*scale, 0.04*scale), bevel_offset=0.02,
                            loc=(math.cos(l_a)*0.25*scale, math.sin(l_a)*0.25*scale, l_z*scale),
                            parent=base, mat_=M_SUNFLOWER_LEAF)
        leaf.rotation_euler = (math.radians(15), 0, l_a)
    # Head (signature large)
    head_e = empty(f"{name}_he", (0, 0, 3.0*scale), parent=base)
    head_e.rotation_euler = (math.radians(40), 0, 0)
    # Center disc (brown seeds)
    cyl(f"{name}_disc", r=0.50*scale, depth=0.15*scale, segs=24,
        loc=(0, 0, 0), parent=head_e, mat_=M_SUNFLOWER_BROWN)
    # Petals (signature 20 yellow petals around)
    for pi in range(20):
        pa = (pi / 20.0) * math.pi * 2
        petal = beveled_cube(f"{name}_petal{pi}", (0.10*scale, 0.50*scale, 0.04*scale), bevel_offset=0.02,
                             loc=(0.75*math.cos(pa)*scale, 0.75*math.sin(pa)*scale, 0),
                             parent=head_e, mat_=M_SUNFLOWER_YELLOW)
        petal.rotation_euler = (0, 0, pa + math.pi/2)
    # Petal tips
    for pi in range(20):
        pa = (pi / 20.0) * math.pi * 2
        smooth_sphere(f"{name}_pt{pi}", r=0.05*scale,
                      loc=(1.0*math.cos(pa)*scale, 1.0*math.sin(pa)*scale, 0),
                      parent=head_e, mat_=M_SUNFLOWER_YELLOW)
    # Back of head
    smooth_sphere(f"{name}_back", r=0.40*scale, loc=(0, 0, -0.10*scale),
                  parent=head_e, mat_=M_SUNFLOWER_LEAF, scale=(1, 1, 0.6))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

sunflowers = []
sf_pos = [(-3, -16, 0), (3, -16, 0), (-3, -19, 0), (3, -19, 0)]
for i, (sx, sy, sz) in enumerate(sf_pos):
    s = make_sunflower(f"sunflower{i}", (sx, sy, sz), scale=1.0)
    sunflowers.append(s)

# ============ 2 PAYSANS (peasants) walking ============
def make_paysan(name, loc, shirt_mat, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs (separate)
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_hip{side_idx}", (side*0.12*scale, 0, 0.80*scale), parent=base)
        cyl(f"{name}_thigh{side_idx}", r=0.10*scale, depth=0.40*scale, segs=12,
            loc=(0, 0, -0.20*scale), parent=hip, mat_=M_PANT_BROWN)
        cyl(f"{name}_calf{side_idx}", r=0.085*scale, depth=0.40*scale, segs=12,
            loc=(0, 0, -0.62*scale), parent=hip, mat_=M_PANT_BROWN)
        # Boots
        beveled_cube(f"{name}_boot{side_idx}", (0.16*scale, 0.30*scale, 0.10*scale), bevel_offset=0.02,
                     loc=(0, 0.04*scale, -0.85*scale), parent=hip,
                     mat_=mat(f"boot_m{side_idx}", (0.25, 0.15, 0.10, 1), 0, 0.7))
    # Pants belt
    cyl(f"{name}_belt", r=0.30*scale, depth=0.10*scale, segs=14,
        loc=(0, 0, 0.95*scale), parent=base, mat_=M_DOOR)
    # Shirt torso (white/blue linen)
    beveled_cube(f"{name}_torso", (0.40*scale, 0.22*scale, 0.65*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.32*scale), parent=base, mat_=shirt_mat)
    # Open collar V (signature linen)
    beveled_cube(f"{name}_v", (0.10*scale, 0.05*scale, 0.20*scale), bevel_offset=0.02,
                 loc=(0, -0.12*scale, 1.55*scale), parent=base, mat_=M_SKIN_PROV)
    # Neck
    cyl(f"{name}_neck", r=0.09*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 1.72*scale), parent=base, mat_=M_SKIN_PROV)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.90*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.19*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_PROV)
    # Hair
    smooth_sphere(f"{name}_hair", r=0.20*scale, loc=(0, 0.03*scale, 0.06*scale),
                  parent=head_e, mat_=M_HAIR_PAYSAN, scale=(1, 1, 0.85))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Mustache (signature peasant)
    smooth_sphere(f"{name}_mustache", r=0.10*scale, loc=(0, -0.17*scale, -0.05*scale),
                  parent=head_e, mat_=M_HAIR_PAYSAN, scale=(1.5, 0.7, 0.4))
    # STRAW HAT signature (wide brim)
    cyl(f"{name}_hat_brim", r=0.30*scale, depth=0.05*scale, segs=18,
        loc=(0, 0, 0.18*scale), parent=head_e, mat_=M_STRAW_HAT)
    cyl(f"{name}_hat_crown", r=0.18*scale, depth=0.18*scale, segs=16,
        loc=(0, 0, 0.30*scale), parent=head_e, mat_=M_STRAW_HAT)
    # Hat band
    cyl(f"{name}_hat_band", r=0.19*scale, depth=0.04*scale, segs=16,
        loc=(0, 0, 0.20*scale), parent=head_e, mat_=M_LINEN_BLUE)
    # Arms (walking - opposite swing)
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.65*scale), parent=base)
        sh.rotation_euler = (math.radians(-25 + (side_idx*2-1)*15), 0, math.radians(side*-15))
        # Upper arm
        cyl(f"{name}_uarm{side_idx}", r=0.08*scale, depth=0.35*scale, segs=12,
            loc=(0, 0, -0.18*scale), parent=sh, mat_=shirt_mat)
        # Forearm (rolled-up signature)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.35*scale, segs=12,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_PROV)
        # Hand
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08*scale, loc=(0, 0, -0.78*scale),
                      parent=sh, mat_=M_SKIN_PROV)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

paysans = []
paysan_specs = [
    ("paysan1", (-2, 5, 0), M_LINEN_WHITE, math.radians(180), 1.0),
    ("paysan2", (2, 5, 0), M_LINEN_BLUE, math.radians(180), 1.0),
]
for spec in paysan_specs:
    name, loc, shirt, fac, sc = spec
    p = make_paysan(name, loc, shirt, facing=fac, scale=sc)
    paysans.append(p)

# ============ SHEEP DOG (Border collie / Berger) ============
dog_e = empty("dog", loc=(3, 7, 0))
dog_e.rotation_euler = (0, 0, math.radians(120))
# Body
smooth_sphere("dog_body", r=0.30, segs=20, rings=14, loc=(0, 0, 0.55),
              parent=dog_e, mat_=M_DOG_WHITE, scale=(1.7, 1, 1))
# Black patches (signature border collie)
for sp in range(4):
    smooth_sphere(f"dog_patch{sp}", r=0.15,
                  loc=(random.uniform(-0.4, 0.4), random.uniform(-0.2, 0.2),
                       0.65 + random.uniform(-0.1, 0.2)),
                  parent=dog_e, mat_=M_DOG_BLACK, scale=(1, 1, 0.35))
# Head
head_e = empty("dog_he", (0.45, 0, 0.75), parent=dog_e)
smooth_sphere("dog_head", r=0.22, segs=18, rings=12, loc=(0, 0, 0),
              parent=head_e, mat_=M_DOG_WHITE)
# Black ears (alert pointed)
for side in (-1, 1):
    ear = smooth_cone(f"dog_ear{side}", r1=0.08, r2=0.02, depth=0.18, segs=10,
                      loc=(-0.05, side*0.12, 0.22), parent=head_e, mat_=M_DOG_BLACK)
    ear.rotation_euler = (math.radians(-20), 0, math.radians(side*15))
# Snout
smooth_cone("dog_snout", r1=0.13, r2=0.10, depth=0.20, segs=12,
            loc=(0.20, 0, -0.05), parent=head_e,
            mat_=M_DOG_WHITE).rotation_euler = (0, math.radians(90), 0)
# Nose (pink)
smooth_sphere("dog_nose", r=0.05, loc=(0.32, 0, -0.05), parent=head_e, mat_=M_DOG_BLACK)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"dog_eye{side}", r=0.04,
                  loc=(0.08, side*0.10, 0.06), parent=head_e,
                  mat_=mat(f"dog_ew{side}", (0.05,0.05,0.05,1), 0, 0.4))
# Tongue (signature dog panting)
beveled_cube("dog_tongue", (0.05, 0.06, 0.12), loc=(0.30, 0, -0.10),
             parent=head_e, mat_=M_DOG_PINK)
# 4 legs
for x_idx, x in enumerate((0.30, -0.30)):
    for y_idx, y in enumerate((-0.18, 0.18)):
        cyl(f"dog_leg{x_idx}{y_idx}", r=0.07, depth=0.50, segs=10,
            loc=(x, y, 0.25), parent=dog_e, mat_=M_DOG_WHITE)
# Tail (curled up signature)
tail_e = empty("dog_te", (-0.45, 0, 0.70), parent=dog_e)
for ti in range(4):
    cyl(f"dog_tail{ti}", r=0.06 - ti*0.01, depth=0.18, segs=8,
        loc=(0, 0, ti*0.13), parent=tail_e, mat_=M_DOG_WHITE)
tail_e.rotation_euler = (math.radians(-30), 0, 0)

# ============ 3 BEEHIVES (signature traditional) ============
for i, (hx, hy) in enumerate([(-22, 6), (-22, 9), (-22, 12)]):
    h_e = empty(f"hive{i}", (hx, hy, 0))
    # Stack of round hives
    for sk in range(3):
        cyl(f"hive_l{i}_{sk}", r=0.35 - sk*0.04, depth=0.30, segs=18,
            loc=(0, 0, 0.20 + sk*0.30), parent=h_e, mat_=M_HIVE)
    # Top cap
    smooth_cone(f"hive_top{i}", r1=0.30, r2=0.05, depth=0.30, segs=12,
                loc=(0, 0, 1.20), parent=h_e, mat_=M_HIVE)
    # Entrance hole
    smooth_sphere(f"hive_hole{i}", r=0.05, loc=(0, -0.35, 0.30), parent=h_e,
                  mat_=mat(f"hole{i}", (0.1, 0.05, 0.02, 1), 0, 0.5))

# ============ 8 CIGALES on cypress (signature Provence) ============
cigales = []
for i in range(8):
    cyp_idx = i % 5
    cx_p, cy_p, _ = cypress_pos[cyp_idx]
    cig_h = random.uniform(3, 6)
    cig_e = empty(f"cig{i}", (cx_p + random.uniform(-0.3, 0.3),
                                cy_p + random.uniform(-0.3, 0.3), cig_h))
    # Body
    smooth_sphere(f"cig_b{i}", r=0.10, segs=12, rings=8, loc=(0, 0, 0),
                  parent=cig_e, mat_=M_CICADA, scale=(1.6, 1, 1))
    # Head
    smooth_sphere(f"cig_h{i}", r=0.07, loc=(0.13, 0, 0), parent=cig_e, mat_=M_CICADA)
    # Wings (translucent)
    for side in (-1, 1):
        beveled_cube(f"cig_w{i}_{side}", (0.06, 0.18, 0.01), bevel_offset=0.005,
                     loc=(-0.02, side*0.10, 0.05), parent=cig_e, mat_=M_CICADA_WING)
    # Legs
    for li in range(6):
        la = (li / 6.0) * math.pi * 2
        cyl(f"cig_l{i}_{li}", r=0.012, depth=0.10, segs=6,
            loc=(0.06*math.cos(la), 0.06*math.sin(la), -0.05),
            parent=cig_e, mat_=M_CICADA)
    cig_e["_phase"] = random.uniform(0, math.pi*2)
    cigales.append(cig_e)

# ============================================================
# ⭐ 600 BUTTERFLIES + 400 POLLEN + 100 BEES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 butterflies
butterflies = []
butter_mats = [M_BUTTER_MONARCH, M_BUTTER_BLUE, M_BUTTER_WHITE, M_BUTTER_YELLOW, M_BUTTER_PINK]
for i in range(600):
    px = random.uniform(-38, 38)
    py = random.uniform(-38, 38)
    pz = random.uniform(0.8, 6)
    bf_e = empty(f"bf{i}", (px, py, pz))
    # Body
    cyl(f"bf_body{i}", r=0.025, depth=0.16, segs=6,
        loc=(0, 0, 0), parent=bf_e, mat_=M_BUTTER_BODY)
    color = butter_mats[i % 5]
    # 4 wings
    wings = []
    for side in (-1, 1):
        w_u_e = empty(f"bf_wue{i}_{side}", (0, 0, 0), parent=bf_e)
        beveled_cube(f"bf_w_u{i}_{side}", (0.05, 0.16, 0.008), bevel_offset=0.004,
                     loc=(0, side*0.10, 0.04), parent=w_u_e, mat_=color)
        beveled_cube(f"bf_w_l{i}_{side}", (0.04, 0.12, 0.008), bevel_offset=0.004,
                     loc=(0, side*0.08, -0.04), parent=w_u_e, mat_=color)
        wings.append((w_u_e, side))
    bf_e["_phase"] = random.uniform(0, math.pi*2)
    bf_e["_base_x"] = px; bf_e["_base_y"] = py; bf_e["_base_z"] = pz
    bf_e["_amp_x"] = random.uniform(2.0, 4.5)
    bf_e["_amp_y"] = random.uniform(2.0, 4.5)
    bf_e["_amp_z"] = random.uniform(0.6, 1.8)
    bf_e["_speed"] = random.uniform(0.6, 1.4)
    butterflies.append({"e": bf_e, "wings": wings})

# 400 pollen (signature golden floating)
pollens = []
for i in range(400):
    px = random.uniform(-38, 38)
    py = random.uniform(-38, 38)
    pz = random.uniform(0.5, 5)
    p_obj = smooth_sphere(f"poll{i}", r=random.uniform(0.04, 0.08), segs=8, rings=6,
                          loc=(px, py, pz),
                          mat_=M_POLLEN if i % 2 == 0 else M_POLLEN_DEEP)
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_amp_x"] = random.uniform(0.8, 2.0)
    p_obj["_amp_y"] = random.uniform(0.8, 2.0)
    p_obj["_amp_z"] = random.uniform(0.4, 1.0)
    p_obj["_speed"] = random.uniform(0.3, 0.8)
    pollens.append(p_obj)

# 100 bees buzzing around hives
bees = []
for i in range(100):
    # Bees concentrated near hives (left side)
    if i % 3 == 0:
        px = random.uniform(-25, -18)
        py = random.uniform(5, 14)
    else:
        px = random.uniform(-38, 38)
        py = random.uniform(-38, 38)
    pz = random.uniform(0.5, 4)
    b_e = empty(f"bee{i}", (px, py, pz))
    smooth_sphere(f"bee_b{i}", r=0.08, segs=10, rings=6, loc=(0, 0, 0),
                  parent=b_e, mat_=M_BEE_YELLOW, scale=(1.4, 1, 1))
    cyl(f"bee_str{i}", r=0.08, depth=0.04, segs=10,
        loc=(0, 0, 0), parent=b_e, mat_=M_BEE_BLACK).rotation_euler = (0, math.radians(90), 0)
    smooth_sphere(f"bee_h{i}", r=0.05, loc=(0.10, 0, 0),
                  parent=b_e, mat_=M_BEE_BLACK)
    for side in (-1, 1):
        beveled_cube(f"bee_w{i}_{side}", (0.03, 0.10, 0.008), bevel_offset=0.004,
                     loc=(-0.02, side*0.06, 0.03), parent=b_e, mat_=M_BEE_WING)
    b_e["_phase"] = random.uniform(0, math.pi*2)
    b_e["_base_x"] = px; b_e["_base_y"] = py; b_e["_base_z"] = pz
    b_e["_amp_x"] = random.uniform(1.2, 2.5)
    b_e["_amp_y"] = random.uniform(1.2, 2.5)
    b_e["_amp_z"] = random.uniform(0.4, 1.0)
    b_e["_speed"] = random.uniform(1.2, 2.2)
    bees.append(b_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Lavender sway (gentle)
for lav in lavender_objs[::3]:  # animate 1/3 to keep file size reasonable
    phase = lav["_phase"]
    for f in range(1, total_frames + 1, 6):
        t_v = (f - 1) / fps
        lav.rotation_euler = (math.sin(t_v * 1.2 + phase) * math.radians(4),
                                math.cos(t_v * 1.0 + phase) * math.radians(3),
                                0)
        lav.keyframe_insert("rotation_euler", frame=f)

# Cypress sway gently
for cyp in cypress_objs:
    phase = cyp["_phase"]
    for f in range(1, total_frames + 1, 5):
        t_v = (f - 1) / fps
        cyp.rotation_euler = (math.sin(t_v * 0.7 + phase) * math.radians(1.5),
                                math.cos(t_v * 0.6 + phase) * math.radians(1.2), 0)
        cyp.keyframe_insert("rotation_euler", frame=f)

# Paysans walk in place (leg + body bob)
for p in paysans:
    phase = p["root"]["_phase"]
    base_z = p["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        p["root"].location.z = base_z + abs(math.sin(t * 2.5 + phase)) * 0.05
        p["root"].keyframe_insert("location", frame=f)
        # Arm swing
        for ai, arm in enumerate(p["arms"]):
            swing = math.sin(t * 2.5 + phase + ai * math.pi) * math.radians(25)
            arm.rotation_euler = (math.radians(-25 + (ai*2-1)*15) + swing, 0, math.radians((-1 if ai==0 else 1)*-15))
            arm.keyframe_insert("rotation_euler", frame=f)
        p["he"].rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(8))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Sunflowers slowly turn head toward sun + sway
for s in sunflowers:
    phase = s["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s["he"].rotation_euler = (math.radians(40) + math.sin(t * 0.4 + phase) * math.radians(8),
                                    0,
                                    math.sin(t * 0.3 + phase) * math.radians(12))
        s["he"].keyframe_insert("rotation_euler", frame=f)
        s["root"].rotation_euler = (math.sin(t * 0.5 + phase) * math.radians(2),
                                      math.cos(t * 0.4 + phase) * math.radians(2), 0)
        s["root"].keyframe_insert("rotation_euler", frame=f)

# Cigales pulse on cypress (vibrate signature)
for cig in cigales:
    phase = cig["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        cig.scale = (1 + math.sin(t * 8.0 + phase) * 0.05,
                      1, 1)
        cig.keyframe_insert("scale", frame=f)

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
# ⭐⭐⭐ 600 BUTTERFLIES flap wings + drift (signature Provence summer)
# ============================================================
for bf in butterflies:
    e = bf["e"]
    phase = e["_phase"]; speed = e["_speed"]
    bx, by, bz = e["_base_x"], e["_base_y"], e["_base_z"]
    ax, ay, az = e["_amp_x"], e["_amp_y"], e["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed * 0.5 + phase)
        y = by + ay * math.cos(t * speed * 0.4 + phase)
        z = bz + az * math.sin(t * speed * 0.8 + phase * 1.3)
        e.location = (x, y, max(0.3, z))
        e.rotation_euler = (math.sin(t * speed * 0.4 + phase) * 0.3, 0,
                            math.atan2(math.cos(t * speed * 0.4 + phase),
                                       math.sin(t * speed * 0.5 + phase)))
        e.keyframe_insert("location", frame=f)
        e.keyframe_insert("rotation_euler", frame=f)
        flap = math.sin(t * 12.0 + phase) * math.radians(50)
        for w_e, side in bf["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)

# 400 POLLEN floating
for p in pollens:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    ax, ay, az = p["_amp_x"], p["_amp_y"], p["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase * 1.5)
        p.location = (x, y, max(0.3, z))
        sc = 1 + math.sin(t * 2.5 + phase) * 0.3
        p.scale = (sc, sc, sc)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("scale", frame=f)

# 100 BEES buzzing erratic
for bee in bees:
    phase = bee["_phase"]; speed = bee["_speed"]
    bx, by, bz = bee["_base_x"], bee["_base_y"], bee["_base_z"]
    ax, ay, az = bee["_amp_x"], bee["_amp_y"], bee["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase) + 0.3*math.sin(t * speed * 3.5 + phase * 2)
        y = by + ay * math.cos(t * speed * 0.9 + phase) + 0.3*math.cos(t * speed * 3.2 + phase)
        z = bz + az * math.sin(t * speed * 1.4 + phase * 1.7) + 0.2*math.sin(t * 6.0 + phase)
        bee.location = (x, y, max(0.3, z))
        bee.rotation_euler = (0, 0, math.atan2(math.cos(t * speed * 0.9 + phase),
                                                math.sin(t * speed + phase)))
        bee.keyframe_insert("location", frame=f)
        bee.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_provence_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_provence_lavender_fields] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_provence_lavender_fields] ONE earth ground + 500 lavenders rows + 5 cypress + mas provençal + 4 sunflowers + 2 paysans + dog + 3 hives + 8 cigales + 600 BUTTERFLIES + 400 POLLEN + 100 BEES")
print("⭐ FIXES: 1 ground + 600 butterflies + 400 pollen + 100 bees (signature Provence summer mandatory) ⭐")
