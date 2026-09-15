"""
proc_spanish_andalusian_flamenco_patio.py — 232e procédural AuroraIA (96e qualité)
Andalusian flamenco patio: ONE mosaic ground + arches + columns + fountain + balconies + bougainvilliers + 2 flamenco dancers + cantaor + 4 guitarists + 4 spectators + Giralda + 600 rose petals + 400 castanet sparkles
FIXES : 1 ground + 600 rose petals + 400 castanet sparkles signature flamenco
"""
import bpy, bmesh, math, random, os

random.seed(0x5DA232)

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

# Andalusian sunset palette
M_SKY = mat("sky", (0.95, 0.62, 0.40, 1.0), 0.0, 0.7, emission=(0.92,0.58,0.38), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.78, 0.35, 1.0), 0.0, 0.10, emission=(1.0,0.78,0.35), emission_strength=20.0)
M_CLOUD = mat("cloud", (1.0, 0.78, 0.55, 1.0), 0.0, 0.55, emission=(0.95,0.75,0.52), emission_strength=2.0, alpha=0.85)

# Mosaic floor (azulejos signature)
M_GROUND = mat("ground", (0.55, 0.42, 0.30, 1.0), 0.0, 0.80, emission=(0.50,0.40,0.28), emission_strength=0.4)
M_AZULEJO_BLUE = mat("az_b", (0.20, 0.50, 0.78, 1.0), 0.3, 0.30, emission=(0.18,0.45,0.72), emission_strength=1.0)
M_AZULEJO_WHITE = mat("az_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.40, emission=(0.88,0.85,0.82), emission_strength=0.6)
M_AZULEJO_GOLD = mat("az_g", (0.95, 0.78, 0.30, 1.0), 0.7, 0.30, emission=(0.92,0.75,0.28), emission_strength=1.0)
M_AZULEJO_GREEN = mat("az_gr", (0.30, 0.65, 0.40, 1.0), 0.3, 0.35, emission=(0.28,0.60,0.38), emission_strength=0.9)
M_AZULEJO_RED = mat("az_r", (0.78, 0.20, 0.20, 1.0), 0.3, 0.35, emission=(0.72,0.20,0.20), emission_strength=1.0)

# Walls
M_WALL_WHITE = mat("wall_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.70, emission=(0.88,0.85,0.78), emission_strength=0.6)
M_WALL_OCHRE = mat("wall_o", (0.92, 0.72, 0.42, 1.0), 0.0, 0.65, emission=(0.85,0.68,0.40), emission_strength=0.5)
M_COLUMN_MARBLE = mat("col_m", (0.98, 0.95, 0.88, 1.0), 0.0, 0.30, emission=(0.92,0.88,0.82), emission_strength=0.5)
M_ARCH_MOORISH = mat("arch_m", (0.92, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.60), emission_strength=0.6)

# Bougainvilliers (signature cascading)
M_BOUG_PURPLE = mat("boug_p", (0.75, 0.20, 0.85, 1.0), 0.0, 0.45, emission=(0.72,0.20,0.78), emission_strength=2.2)
M_BOUG_PINK = mat("boug_pk", (1.0, 0.45, 0.75, 1.0), 0.0, 0.45, emission=(0.95,0.42,0.70), emission_strength=2.5)
M_BOUG_MAGENTA = mat("boug_m", (0.95, 0.20, 0.55, 1.0), 0.0, 0.45, emission=(0.90,0.20,0.52), emission_strength=2.3)
M_BOUG_RED = mat("boug_r", (0.95, 0.20, 0.20, 1.0), 0.0, 0.45, emission=(0.90,0.20,0.20), emission_strength=2.2)
M_BOUG_LEAF = mat("boug_l", (0.30, 0.55, 0.30, 1.0), 0.0, 0.65, emission=(0.28,0.50,0.28), emission_strength=0.5)
M_BOUG_STEM = mat("boug_s", (0.35, 0.22, 0.12, 1.0), 0.0, 0.80)

# Fountain
M_WATER = mat("water", (0.55, 0.78, 0.92, 0.85), 0.4, 0.10, emission=(0.50,0.72,0.88), emission_strength=1.5, alpha=0.85)
M_WATER_FOAM = mat("foam", (1.0, 1.0, 1.0, 1.0), 0.0, 0.20, emission=(0.95,0.95,0.98), emission_strength=2.5)

# Iron forged balconies (signature)
M_IRON_FORGED = mat("iron", (0.15, 0.12, 0.10, 1.0), 0.5, 0.50, emission=(0.13,0.10,0.08), emission_strength=0.4)

# Skin
M_SKIN_SPANISH = mat("skin", (0.90, 0.72, 0.55, 1.0), 0.0, 0.55, emission=(0.85,0.68,0.52), emission_strength=0.4)
M_HAIR_DARK_S = mat("hair_s", (0.10, 0.06, 0.04, 1.0), 0.0, 0.85)
M_HAIR_BLACK_S = mat("hair_bs", (0.05, 0.04, 0.03, 1.0), 0.0, 0.85)

# Flamenco dancer F (signature dress)
M_DRESS_RED = mat("dress_r", (0.85, 0.18, 0.20, 1.0), 0.0, 0.55, emission=(0.78,0.18,0.18), emission_strength=0.7)
M_DRESS_BLACK = mat("dress_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.65, emission=(0.08,0.06,0.06), emission_strength=0.3)
M_DRESS_POLKA = mat("dress_pol", (0.85, 0.85, 0.85, 1.0), 0.0, 0.65)
M_FRILL = mat("frill", (0.92, 0.18, 0.20, 1.0), 0.0, 0.55, emission=(0.85,0.18,0.18), emission_strength=0.8)
M_FRILL_BLACK = mat("frill_bk", (0.18, 0.10, 0.10, 1.0), 0.0, 0.65)
M_SHAWL = mat("shawl", (0.55, 0.20, 0.25, 1.0), 0.3, 0.45, emission=(0.50,0.18,0.22), emission_strength=0.7)
M_FAN_RED = mat("fan_r", (0.95, 0.20, 0.20, 1.0), 0.0, 0.55, emission=(0.90,0.20,0.20), emission_strength=0.8)

# Flamenco dancer M
M_SUIT_BLACK = mat("suit", (0.12, 0.10, 0.08, 1.0), 0.0, 0.70, emission=(0.10,0.08,0.06), emission_strength=0.3)
M_VEST_RED = mat("vest_r", (0.85, 0.20, 0.20, 1.0), 0.0, 0.65, emission=(0.78,0.20,0.20), emission_strength=0.7)
M_SHIRT_WHITE = mat("shirt_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.78), emission_strength=0.6)
M_BELT_RED = mat("belt_r", (0.65, 0.15, 0.15, 1.0), 0.0, 0.65, emission=(0.60,0.15,0.15), emission_strength=0.7)
M_CASTANET = mat("castanet", (0.30, 0.18, 0.12, 1.0), 0.0, 0.75, emission=(0.65,0.45,0.20), emission_strength=2.5)

# Guitars
M_GUITAR_WOOD = mat("g_wood", (0.55, 0.30, 0.15, 1.0), 0.0, 0.55, emission=(0.50,0.28,0.13), emission_strength=0.5)
M_GUITAR_WOOD_LIGHT = mat("g_wl", (0.78, 0.55, 0.30, 1.0), 0.0, 0.50, emission=(0.72,0.50,0.28), emission_strength=0.6)
M_GUITAR_STRING = mat("g_str", (0.85, 0.85, 0.92, 1.0), 0.7, 0.20, emission=(0.78,0.78,0.85), emission_strength=0.5)
M_GUITAR_BLACK = mat("g_bk", (0.08, 0.06, 0.04, 1.0), 0.0, 0.85)

# Spectators
M_DRESS_PURPLE_S = mat("d_pu_s", (0.55, 0.20, 0.55, 1.0), 0.0, 0.65, emission=(0.50,0.18,0.50), emission_strength=0.6)
M_DRESS_PINK_S = mat("d_pk_s", (0.95, 0.55, 0.75, 1.0), 0.0, 0.55, emission=(0.90,0.50,0.70), emission_strength=0.7)
M_SUIT_BROWN = mat("suit_br", (0.45, 0.30, 0.18, 1.0), 0.0, 0.70, emission=(0.42,0.28,0.16), emission_strength=0.4)

# Tables + wine
M_TABLE_WROUGHT = mat("table_iron", (0.18, 0.12, 0.10, 1.0), 0.5, 0.50)
M_WINE_RED = mat("wine_r", (0.55, 0.10, 0.15, 1.0), 0.0, 0.30, emission=(0.50,0.10,0.13), emission_strength=2.0)
M_SANGRIA = mat("sangria", (0.78, 0.18, 0.25, 1.0), 0.0, 0.25, emission=(0.72,0.18,0.22), emission_strength=2.2, alpha=0.85)
M_GLASS = mat("glass", (0.85, 0.92, 0.95, 0.65), 0.4, 0.10, emission=(0.78,0.85,0.92), emission_strength=1.0, alpha=0.65)
M_BOTTLE = mat("bottle", (0.20, 0.55, 0.30, 1.0), 0.3, 0.20, emission=(0.18,0.50,0.28), emission_strength=0.8, alpha=0.85)

# Giralda tower
M_GIRALDA_STONE = mat("gir_s", (0.85, 0.72, 0.45, 1.0), 0.0, 0.70, emission=(0.78,0.68,0.42), emission_strength=0.5)
M_GIRALDA_TILE = mat("gir_t", (0.92, 0.78, 0.30, 1.0), 0.3, 0.50, emission=(0.85,0.72,0.28), emission_strength=0.7)

# Roses + sparkles (signature flamenco particles)
M_ROSE_RED = mat("rose_r", (0.95, 0.20, 0.25, 1.0), 0.0, 0.45, emission=(0.90,0.20,0.22), emission_strength=2.5)
M_ROSE_PINK = mat("rose_pk", (1.0, 0.55, 0.65, 1.0), 0.0, 0.45, emission=(1.0,0.55,0.65), emission_strength=2.2)
M_ROSE_DEEP = mat("rose_d", (0.78, 0.10, 0.18, 1.0), 0.0, 0.45, emission=(0.72,0.10,0.18), emission_strength=2.7)
M_SPARK_GOLD = mat("sp_g", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.30), emission_strength=22.0)
M_SPARK_AMBER = mat("sp_a", (1.0, 0.65, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.65,0.20), emission_strength=20.0)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (25, 40, 25))
smooth_sphere("sun", r=5.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=5.0 + (i+1)*1.7, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

clouds = []
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    rad = random.uniform(32, 45)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(22, 30)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ GIRALDA TOWER (signature Sevilla landmark) ============
gir_e = empty("giralda", loc=(0, 35, 0))
# Base square (massive)
beveled_cube("gir_base", (4, 4, 18), bevel_offset=0.08, loc=(0, 0, 9),
             parent=gir_e, mat_=M_GIRALDA_STONE)
# Decorative arch panels (signature mudejar)
for ai in range(6):
    az = 2 + ai * 2.5
    for side in (-1, 1):
        for y_side in (-1, 1):
            beveled_cube(f"gir_arch{ai}_{side}_{y_side}", (0.3, 0.10, 1.5), bevel_offset=0.03,
                         loc=(side*2.05, y_side*2.05, az), parent=gir_e, mat_=M_GIRALDA_TILE)
# Bell tower upper
beveled_cube("gir_bell", (3, 3, 4), bevel_offset=0.06, loc=(0, 0, 20),
             parent=gir_e, mat_=M_GIRALDA_STONE)
# Bell arches
for side_b in (-1, 1):
    for y_b in (-1, 1):
        beveled_cube(f"gir_bell_arch_{side_b}_{y_b}", (1.5, 0.10, 2.0), bevel_offset=0.04,
                     loc=(side_b*1.05, y_b*1.55, 20), parent=gir_e, mat_=M_GIRALDA_TILE)
# Pyramid top
smooth_cone("gir_pyr", r1=2.0, r2=0.2, depth=3, segs=14, loc=(0, 0, 23.5),
            parent=gir_e, mat_=M_GIRALDA_STONE)
# Giraldillo (statue top signature)
smooth_sphere("gir_statue", r=0.50, loc=(0, 0, 25.5), parent=gir_e, mat_=M_AZULEJO_GOLD)
beveled_cube("gir_statue_b", (0.20, 0.20, 1.0), loc=(0, 0, 26.5),
             parent=gir_e, mat_=M_AZULEJO_GOLD)
# Flag
beveled_cube("gir_flag", (0.05, 0.04, 0.8), loc=(0, 0.30, 27),
             parent=gir_e, mat_=M_FRILL)

# ============ ONE clean tile ground (mosaic central) ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)
# Central mosaic plaza (signature azulejo geometric pattern)
plaza_e = empty("plaza", (0, 0, 0))
# Central circle
cyl("mosaic_c", r=10, depth=0.12, segs=32, loc=(0, 0, 0.06),
    parent=plaza_e, mat_=M_AZULEJO_BLUE)
# Star pattern (signature 8-pointed)
for pt in range(8):
    pa = (pt / 8.0) * math.pi * 2
    star = beveled_cube(f"star{pt}", (0.5, 2.5, 0.08), bevel_offset=0.03,
                        loc=(math.cos(pa)*1.5, math.sin(pa)*1.5, 0.10),
                        parent=plaza_e, mat_=M_AZULEJO_GOLD)
    star.rotation_euler = (0, 0, pa)
# Concentric ring
cyl("mosaic_ring", r=6, depth=0.10, segs=32, loc=(0, 0, 0.07),
    parent=plaza_e, mat_=M_AZULEJO_WHITE)
cyl("mosaic_inner", r=2, depth=0.10, segs=32, loc=(0, 0, 0.08),
    parent=plaza_e, mat_=M_AZULEJO_RED)
# Tile edge pattern (organic 3D)
for i in range(48):
    a = (i / 48.0) * math.pi * 2
    rad = 11
    col = [M_AZULEJO_BLUE, M_AZULEJO_GOLD, M_AZULEJO_GREEN, M_AZULEJO_RED, M_AZULEJO_WHITE][i % 5]
    tile = beveled_cube(f"tile_edge{i}", (0.55, 0.55, 0.10), bevel_offset=0.02,
                        loc=(rad*math.cos(a), rad*math.sin(a), 0.06),
                        parent=plaza_e, mat_=col)
    tile.rotation_euler = (0, 0, a)

# Outside floor tiles (organic 3D)
for i in range(60):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(13, 38)
    smooth_sphere(f"floor_tile{i}", r=random.uniform(0.30, 0.50), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_AZULEJO_WHITE if i % 2 == 0 else M_GROUND,
                  scale=(1.4, 1.2, 0.15))

# ============ COURTYARD WALLS + ARCHES (4 sides Moorish) ============
def make_moorish_arch(name, loc, scale=1.0, color=M_ARCH_MOORISH):
    base = empty(name, loc)
    # 2 columns
    for side in (-1, 1):
        # Column base
        cyl(f"{name}_col_base{side}", r=0.55*scale, depth=0.40*scale, segs=18,
            loc=(side*2.0*scale, 0, 0.20*scale), parent=base, mat_=M_COLUMN_MARBLE)
        # Column shaft (signature fluted)
        cyl(f"{name}_col{side}", r=0.40*scale, depth=4.0*scale, segs=20,
            loc=(side*2.0*scale, 0, 2.4*scale), parent=base, mat_=M_COLUMN_MARBLE)
        # Capital (signature decorative)
        cyl(f"{name}_cap{side}", r=0.55*scale, depth=0.25*scale, segs=18,
            loc=(side*2.0*scale, 0, 4.55*scale), parent=base, mat_=M_COLUMN_MARBLE)
    # Moorish horseshoe arch (7 segments - signature)
    for seg in range(7):
        ang = math.pi - (seg / 6.0) * math.pi
        ax = math.cos(ang) * 2.0 * scale
        az = 4.7*scale + math.sin(ang) * 1.5 * scale
        arch_s = beveled_cube(f"{name}_arch{seg}", (0.5*scale, 0.8*scale, 0.45*scale), bevel_offset=0.04,
                              loc=(ax, 0, az), parent=base, mat_=color)
        arch_s.rotation_euler = (0, ang - math.pi/2, 0)
    # Top decorative band (signature stucco)
    beveled_cube(f"{name}_band", (4.5*scale, 0.4*scale, 0.40*scale), bevel_offset=0.04,
                 loc=(0, 0, 6.5*scale), parent=base, mat_=M_WALL_OCHRE)
    # Geometric pattern on band
    for pt in range(8):
        sx_p = (pt - 3.5) * 0.5 * scale
        beveled_cube(f"{name}_pat{pt}", (0.20*scale, 0.05*scale, 0.20*scale), bevel_offset=0.02,
                     loc=(sx_p, -0.22*scale, 6.5*scale), parent=base, mat_=M_AZULEJO_GOLD)
    return base

# 4 arches around courtyard
arches_pos = [(0, 18, 0, math.radians(0)),
              (0, -18, 0, math.radians(180)),
              (18, 0, 0, math.radians(90)),
              (-18, 0, 0, math.radians(-90))]
for ai, (ax_a, ay_a, az_a, fac) in enumerate(arches_pos):
    arch = make_moorish_arch(f"arch{ai}", (ax_a, ay_a, az_a), scale=1.5)
    arch.rotation_euler = (0, 0, fac)

# Additional intermediate arches
for ai_idx in range(4):
    side_x = 1 if ai_idx % 2 == 0 else -1
    side_y = 1 if ai_idx < 2 else -1
    pos = (side_x * 14, side_y * 14, 0)
    fac = math.atan2(-pos[1], -pos[0])
    arch = make_moorish_arch(f"arch_c{ai_idx}", pos, scale=1.3)
    arch.rotation_euler = (0, 0, fac)

# Upper level walls with balconies
for side, side_mul in zip(("L", "R"), (-1, 1)):
    beveled_cube(f"wall_{side}_upper", (16, 1, 4), bevel_offset=0.06,
                 loc=(side_mul*16, 0, 9), mat_=M_WALL_WHITE)
for side, side_mul in zip(("F", "B"), (-1, 1)):
    beveled_cube(f"wall_{side}_upper", (1, 16, 4), bevel_offset=0.06,
                 loc=(0, side_mul*16, 9), mat_=M_WALL_WHITE)

# WROUGHT IRON BALCONIES (signature Andalusian)
for ai_idx in range(8):
    a = (ai_idx / 8.0) * math.pi * 2
    bx = 15 * math.cos(a)
    by = 15 * math.sin(a)
    bz = 9
    b_e = empty(f"balcony{ai_idx}", (bx, by, bz))
    b_e.rotation_euler = (0, 0, a + math.pi/2)
    # Balcony platform
    beveled_cube(f"b_plat{ai_idx}", (1.5, 0.6, 0.15), bevel_offset=0.03,
                 loc=(0, -0.3, 0), parent=b_e, mat_=M_COLUMN_MARBLE)
    # Iron railing posts
    for pp in range(6):
        px_p = (pp - 2.5) * 0.30
        cyl(f"b_post{ai_idx}_{pp}", r=0.04, depth=0.80, segs=8,
            loc=(px_p, -0.55, 0.40), parent=b_e, mat_=M_IRON_FORGED)
    # Top rail
    beveled_cube(f"b_rail{ai_idx}", (1.6, 0.05, 0.08), bevel_offset=0.01,
                 loc=(0, -0.55, 0.80), parent=b_e, mat_=M_IRON_FORGED)
    # Decorative curls (signature wrought iron)
    for sp in range(3):
        spx = (sp - 1) * 0.40
        for cl in range(5):
            ca = cl * 1.2
            smooth_sphere(f"b_curl{ai_idx}_{sp}_{cl}", r=0.04,
                          loc=(spx + math.cos(ca)*0.10, -0.55, 0.30 + math.sin(ca)*0.15 + cl*0.04),
                          parent=b_e, mat_=M_IRON_FORGED)
    # BOUGAINVILLIER cascading from balcony (signature)
    for boug in range(20):
        b_x = random.uniform(-0.7, 0.7)
        b_y = -0.7 + random.uniform(-0.05, 0.05)
        b_z = -random.uniform(0.5, 3.5)
        boug_col = random.choice([M_BOUG_PURPLE, M_BOUG_PINK, M_BOUG_MAGENTA, M_BOUG_RED])
        smooth_sphere(f"b_boug{ai_idx}_{boug}", r=random.uniform(0.08, 0.15),
                      loc=(b_x, b_y, b_z), parent=b_e, mat_=boug_col)
    # Leaves
    for lf in range(15):
        smooth_sphere(f"b_leaf{ai_idx}_{lf}", r=random.uniform(0.06, 0.12),
                      loc=(random.uniform(-0.6, 0.6), -0.7, -random.uniform(0.3, 3.0)),
                      parent=b_e, mat_=M_BOUG_LEAF, scale=(1, 0.4, 1.5))

# ============ CENTRAL FOUNTAIN (signature azulejo) ============
fountain_e = empty("fountain", loc=(0, 0, 0))
# Octagonal basin (signature)
for oi in range(8):
    oa = (oi / 8.0) * math.pi * 2 + math.pi/8
    cyl(f"f_basin{oi}", r=0.5, depth=0.5, segs=4,
        loc=(2.5*math.cos(oa), 2.5*math.sin(oa), 0.25), parent=fountain_e, mat_=M_COLUMN_MARBLE)
# Basin wall (azulejo tiles)
for ti in range(24):
    ta = (ti / 24.0) * math.pi * 2
    col = M_AZULEJO_BLUE if ti % 2 == 0 else M_AZULEJO_WHITE
    beveled_cube(f"f_tile{ti}", (0.40, 0.20, 0.50), bevel_offset=0.02,
                 loc=(2.7*math.cos(ta), 2.7*math.sin(ta), 0.25),
                 parent=fountain_e, mat_=col).rotation_euler = (0, 0, ta + math.pi/2)
# Water surface
cyl("f_water", r=2.4, depth=0.30, segs=32, loc=(0, 0, 0.40),
    parent=fountain_e, mat_=M_WATER)
# Central pillar
cyl("f_pillar", r=0.30, depth=1.5, segs=16, loc=(0, 0, 1.25),
    parent=fountain_e, mat_=M_COLUMN_MARBLE)
# Upper basin (smaller)
cyl("f_upper_basin", r=0.80, depth=0.20, segs=20, loc=(0, 0, 2.10),
    parent=fountain_e, mat_=M_COLUMN_MARBLE)
cyl("f_upper_water", r=0.70, depth=0.10, segs=20, loc=(0, 0, 2.25),
    parent=fountain_e, mat_=M_WATER)
# Top sphere
smooth_sphere("f_top", r=0.30, loc=(0, 0, 2.55), parent=fountain_e, mat_=M_AZULEJO_GOLD)
# Water jets cascading
for ji in range(8):
    ja = (ji / 8.0) * math.pi * 2
    for ji_d in range(4):
        jd_t = ji_d / 4.0
        jx = math.cos(ja) * jd_t * 1.0
        jy = math.sin(ja) * jd_t * 1.0
        jz = 2.25 + math.sin(jd_t * math.pi) * 0.5 - jd_t * 0.3
        smooth_sphere(f"f_jet{ji}_{ji_d}", r=0.08,
                      loc=(jx, jy, jz), parent=fountain_e, mat_=M_WATER_FOAM)

# ============ FLAMENCO DANCER FEMALE (signature dress) ============
dancer_f_e = empty("dancer_f", loc=(-3, -5, 0))
dancer_f_e.rotation_euler = (0, 0, math.radians(30))
# Legs
for side_idx, side in enumerate((-1, 1)):
    hip = empty(f"df_hip{side_idx}", (side*0.12, 0, 0.80), parent=dancer_f_e)
    leg_rx = math.radians(-15 if side_idx == 0 else 25)
    hip.rotation_euler = (leg_rx, 0, 0)
    cyl(f"df_thigh{side_idx}", r=0.10, depth=0.50, segs=12,
        loc=(0, 0, -0.25), parent=hip, mat_=M_SKIN_SPANISH)
    cyl(f"df_calf{side_idx}", r=0.08, depth=0.50, segs=12,
        loc=(0, 0, -0.75), parent=hip, mat_=M_SKIN_SPANISH)
    # High heel flamenco shoes
    beveled_cube(f"df_shoe{side_idx}", (0.14, 0.28, 0.06), bevel_offset=0.02,
                 loc=(0, 0.05, -1.00), parent=hip, mat_=M_DRESS_BLACK)
    # Heel
    cyl(f"df_heel{side_idx}", r=0.025, depth=0.10, segs=8,
        loc=(0, -0.10, -1.05), parent=hip, mat_=M_DRESS_BLACK)
# DRESS (signature flamenco bata de cola long skirt)
smooth_cone("df_skirt", r1=0.55, r2=0.65, depth=1.4, segs=20,
            loc=(0, 0, 0.85), parent=dancer_f_e, mat_=M_DRESS_RED)
# Polka dots on dress
for pd in range(15):
    pda = random.uniform(0, math.pi*2)
    pdr = random.uniform(0.35, 0.55)
    pdz = random.uniform(0.40, 1.40)
    smooth_sphere(f"df_polka{pd}", r=0.05,
                  loc=(pdr*math.cos(pda), pdr*math.sin(pda), pdz),
                  parent=dancer_f_e, mat_=M_DRESS_POLKA, scale=(1, 0.3, 1))
# FRILLS at bottom (signature volants 3 layers)
for layer in range(3):
    cyl(f"df_frill{layer}", r=0.70 + layer*0.08, depth=0.20, segs=24,
        loc=(0, 0, 0.40 - layer*0.18), parent=dancer_f_e,
        mat_=M_FRILL if layer % 2 == 0 else M_FRILL_BLACK)
# Belt
cyl("df_belt", r=0.30, depth=0.10, segs=18,
    loc=(0, 0, 1.45), parent=dancer_f_e, mat_=M_BELT_RED)
# Tight bodice
beveled_cube("df_bodice", (0.40, 0.22, 0.55), bevel_offset=0.05,
             loc=(0, 0, 1.80), parent=dancer_f_e, mat_=M_DRESS_RED)
# More frills on top
for layer in range(2):
    cyl(f"df_top_frill{layer}", r=0.42 + layer*0.04, depth=0.10, segs=18,
        loc=(0, 0, 2.10 - layer*0.08), parent=dancer_f_e, mat_=M_FRILL)
# Neck
cyl("df_neck", r=0.08, depth=0.16, segs=10, loc=(0, 0, 2.20),
    parent=dancer_f_e, mat_=M_SKIN_SPANISH)
# Head
df_head_e = empty("df_he", (0, 0, 2.38), parent=dancer_f_e)
smooth_sphere("df_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
              parent=df_head_e, mat_=M_SKIN_SPANISH)
# Hair (slicked back bun signature)
smooth_sphere("df_hair", r=0.20, loc=(0, 0.05, 0.05),
              parent=df_head_e, mat_=M_HAIR_BLACK_S, scale=(1, 1, 0.85))
smooth_sphere("df_bun", r=0.15, loc=(0, 0.22, 0.05),
              parent=df_head_e, mat_=M_HAIR_BLACK_S, scale=(1.2, 0.8, 1.2))
# Red rose in hair (signature)
smooth_sphere("df_rose_hair", r=0.10, loc=(0.18, 0.15, 0.10),
              parent=df_head_e, mat_=M_ROSE_RED, scale=(1, 1, 0.8))
# Eyes
for side in (-1, 1):
    smooth_sphere(f"df_eye{side}", r=0.025,
                  loc=(side*0.06, -0.14, 0.02), parent=df_head_e,
                  mat_=mat(f"df_ew{side}", (0.10, 0.05, 0.04, 1), 0, 0.40,
                            emission=(0.40, 0.15, 0.08), emission_strength=1.5))
# Lips red (signature)
beveled_cube("df_lips", (0.10, 0.04, 0.03), loc=(0, -0.18, -0.08),
             parent=df_head_e, mat_=M_ROSE_RED)
# Earrings hanging gold (signature)
for side in (-1, 1):
    cyl(f"df_earring{side}", r=0.015, depth=0.20, segs=8,
        loc=(side*0.18, 0.02, -0.08), parent=df_head_e, mat_=M_AZULEJO_GOLD)
    smooth_sphere(f"df_earring_b{side}", r=0.04, loc=(side*0.18, 0.02, -0.20),
                  parent=df_head_e, mat_=M_AZULEJO_GOLD)
# Arms (dance pose flamenco signature)
df_arms = []
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"df_sh{side_idx}", (side*0.32, 0, 2.08), parent=dancer_f_e)
    # Flamenco arm raised + curl signature
    if side_idx == 0:
        sh.rotation_euler = (math.radians(-140), 0, math.radians(-45))
    else:
        sh.rotation_euler = (math.radians(-130), 0, math.radians(60))
    cyl(f"df_uarm{side_idx}", r=0.07, depth=0.32, segs=12,
        loc=(0, 0, -0.17), parent=sh, mat_=M_SKIN_SPANISH)
    cyl(f"df_fa{side_idx}", r=0.06, depth=0.30, segs=10,
        loc=(0, 0, -0.47), parent=sh, mat_=M_SKIN_SPANISH)
    smooth_sphere(f"df_hand{side_idx}", r=0.07, loc=(0, 0, -0.64),
                  parent=sh, mat_=M_SKIN_SPANISH)
    # Bracelets
    for bi in range(2):
        cyl(f"df_brac{side_idx}_{bi}", r=0.07, depth=0.03, segs=12,
            loc=(0, 0, -0.40 + bi*0.04), parent=sh, mat_=M_AZULEJO_GOLD)
    df_arms.append(sh)
# Fan in left hand (signature flamenco prop)
fan_e = empty("df_fan_e", (-0.5, -0.5, 1.5), parent=dancer_f_e)
fan_e.rotation_euler = (math.radians(-30), 0, math.radians(60))
# Fan blades
for fb in range(12):
    fba = (fb / 12.0) * math.pi
    blade = beveled_cube(f"df_fan_b{fb}", (0.04, 0.30, 0.02), bevel_offset=0.005,
                         loc=(0, math.sin(fba)*0.10, 0.15 - math.cos(fba)*0.15),
                         parent=fan_e, mat_=M_FAN_RED)
    blade.rotation_euler = (0, 0, fba - math.pi/2)

# Castanets in right hand (signature)
for cs in range(2):
    cyl(f"df_castanet_top{cs}", r=0.04, depth=0.04, segs=12,
        loc=(0.5 + cs*0.04, -0.5, 1.5), mat_=M_CASTANET)
    cyl(f"df_castanet_bot{cs}", r=0.04, depth=0.04, segs=12,
        loc=(0.5 + cs*0.04, -0.5, 1.42), mat_=M_CASTANET)

# ============ FLAMENCO DANCER MALE (signature) ============
dancer_m_e = empty("dancer_m", loc=(3, -5, 0))
dancer_m_e.rotation_euler = (0, 0, math.radians(-30))
# Legs (signature stance)
for side_idx, side in enumerate((-1, 1)):
    hip = empty(f"dm_hip{side_idx}", (side*0.15, 0, 0.85), parent=dancer_m_e)
    # Stomping pose
    leg_rx = math.radians(25 if side_idx == 0 else -10)
    hip.rotation_euler = (leg_rx, 0, 0)
    cyl(f"dm_thigh{side_idx}", r=0.11, depth=0.55, segs=12,
        loc=(0, 0, -0.27), parent=hip, mat_=M_SUIT_BLACK)
    cyl(f"dm_calf{side_idx}", r=0.10, depth=0.55, segs=12,
        loc=(0, 0, -0.82), parent=hip, mat_=M_SUIT_BLACK)
    # Black shoes
    beveled_cube(f"dm_shoe{side_idx}", (0.14, 0.30, 0.10), bevel_offset=0.02,
                 loc=(0, 0.04, -1.10), parent=hip, mat_=M_DRESS_BLACK)
# Pants high-waisted
smooth_cone("dm_pants", r1=0.32, r2=0.28, depth=0.30, segs=14,
            loc=(0, 0, 1.05), parent=dancer_m_e, mat_=M_SUIT_BLACK)
# Belt
cyl("dm_belt", r=0.30, depth=0.08, segs=18,
    loc=(0, 0, 1.22), parent=dancer_m_e, mat_=M_BELT_RED)
# White shirt
beveled_cube("dm_shirt", (0.42, 0.24, 0.50), bevel_offset=0.05,
             loc=(0, 0, 1.55), parent=dancer_m_e, mat_=M_SHIRT_WHITE)
# RED VEST/CHALECO (signature)
beveled_cube("dm_vest", (0.44, 0.10, 0.45), bevel_offset=0.04,
             loc=(0, -0.13, 1.55), parent=dancer_m_e, mat_=M_VEST_RED)
# Vest buttons
for bi in range(4):
    smooth_sphere(f"dm_btn{bi}", r=0.020,
                  loc=(0, -0.18, 1.70 - bi*0.13), parent=dancer_m_e, mat_=M_AZULEJO_GOLD)
# Neck
cyl("dm_neck", r=0.09, depth=0.16, segs=10, loc=(0, 0, 1.88),
    parent=dancer_m_e, mat_=M_SKIN_SPANISH)
# Head
dm_head_e = empty("dm_he", (0, 0, 2.05), parent=dancer_m_e)
smooth_sphere("dm_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
              parent=dm_head_e, mat_=M_SKIN_SPANISH)
# Hair slicked dark
smooth_sphere("dm_hair", r=0.20, loc=(0, 0.04, 0.05),
              parent=dm_head_e, mat_=M_HAIR_BLACK_S, scale=(1, 1, 0.75))
# Sideburns (signature)
for side in (-1, 1):
    beveled_cube(f"dm_sideburn{side}", (0.04, 0.05, 0.20),
                 loc=(side*0.17, 0, -0.08), parent=dm_head_e, mat_=M_HAIR_BLACK_S)
# Mustache thin (signature)
smooth_sphere("dm_must", r=0.06, loc=(0, -0.16, -0.05),
              parent=dm_head_e, mat_=M_HAIR_BLACK_S, scale=(1.7, 0.4, 0.3))
# Eyes
for side in (-1, 1):
    smooth_sphere(f"dm_eye{side}", r=0.025,
                  loc=(side*0.07, -0.14, 0.02), parent=dm_head_e,
                  mat_=mat(f"dm_ew{side}", (0.10, 0.05, 0.04, 1), 0, 0.40,
                            emission=(0.40, 0.15, 0.08), emission_strength=1.5))
# Arms (dance pose - one raised one to side)
dm_arms = []
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"dm_sh{side_idx}", (side*0.32, 0, 1.85), parent=dancer_m_e)
    if side_idx == 0:
        sh.rotation_euler = (math.radians(-160), 0, math.radians(-30))
    else:
        sh.rotation_euler = (math.radians(-30), 0, math.radians(40))
    cyl(f"dm_uarm{side_idx}", r=0.08, depth=0.35, segs=12,
        loc=(0, 0, -0.18), parent=sh, mat_=M_SHIRT_WHITE)
    cyl(f"dm_fa{side_idx}", r=0.07, depth=0.32, segs=10,
        loc=(0, 0, -0.50), parent=sh, mat_=M_SKIN_SPANISH)
    smooth_sphere(f"dm_hand{side_idx}", r=0.08, loc=(0, 0, -0.68),
                  parent=sh, mat_=M_SKIN_SPANISH)
    dm_arms.append(sh)

# ============ 4 GUITARISTS + 1 CANTAOR singer ============
def make_seated_musician(name, loc, instrument, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sitting body
    smooth_cone(f"{name}_legs", r1=0.30, r2=0.22, depth=0.55, segs=14,
                loc=(0, 0, 0.32), parent=base, mat_=M_SUIT_BLACK)
    # Torso
    beveled_cube(f"{name}_torso", (0.40, 0.22, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 0.95), parent=base, mat_=M_SHIRT_WHITE)
    # Black vest
    beveled_cube(f"{name}_vest", (0.42, 0.10, 0.50), bevel_offset=0.04,
                 loc=(0, -0.13, 0.95), parent=base, mat_=M_SUIT_BLACK)
    # Neck
    cyl(f"{name}_neck", r=0.08, depth=0.15, segs=10, loc=(0, 0, 1.30),
        parent=base, mat_=M_SKIN_SPANISH)
    head_e = empty(f"{name}_he", (0, 0, 1.48), parent=base)
    smooth_sphere(f"{name}_head", r=0.17, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_SPANISH)
    smooth_sphere(f"{name}_hair", r=0.19, loc=(0, 0.04, 0.05),
                  parent=head_e, mat_=M_HAIR_DARK_S, scale=(1, 1, 0.85))
    # Beard
    smooth_sphere(f"{name}_beard", r=0.13, loc=(0, -0.15, -0.12),
                  parent=head_e, mat_=M_HAIR_DARK_S, scale=(1.0, 0.8, 1.2))
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.13, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.10, 0.05, 0.04, 1), 0, 0.4,
                                emission=(0.40, 0.15, 0.08), emission_strength=1.3))
    # Arms
    arms_e = []
    if instrument == "guitar":
        # Guitar in lap
        guitar_e = empty(f"{name}_g_e", (0, -0.45, 0.85), parent=base)
        # Body (signature flamenco guitar shape)
        smooth_sphere(f"{name}_g_body", r=0.30, segs=20, rings=14,
                      loc=(0, 0, 0), parent=guitar_e, mat_=M_GUITAR_WOOD_LIGHT,
                      scale=(0.85, 0.4, 1.3))
        # Sound hole
        smooth_sphere(f"{name}_g_hole", r=0.10, loc=(0, -0.13, 0),
                      parent=guitar_e, mat_=M_GUITAR_BLACK, scale=(1, 0.1, 1))
        # Rosette around hole
        for ro in range(12):
            roa = (ro / 12.0) * math.pi * 2
            smooth_sphere(f"{name}_g_rose{ro}", r=0.015,
                          loc=(0.12*math.cos(roa), -0.13, 0.12*math.sin(roa)),
                          parent=guitar_e, mat_=M_AZULEJO_GOLD)
        # Neck
        beveled_cube(f"{name}_g_neck", (0.06, 0.04, 0.80), bevel_offset=0.01,
                     loc=(0, -0.08, 0.65), parent=guitar_e, mat_=M_GUITAR_WOOD)
        # Headstock
        beveled_cube(f"{name}_g_head", (0.10, 0.04, 0.20), bevel_offset=0.02,
                     loc=(0, -0.08, 1.10), parent=guitar_e, mat_=M_GUITAR_WOOD)
        # 6 strings (signature)
        for st in range(6):
            cyl(f"{name}_g_str{st}", r=0.004, depth=1.5, segs=4,
                loc=((st-2.5)*0.012, -0.16, 0.40), parent=guitar_e, mat_=M_GUITAR_STRING)
        # Bridge
        beveled_cube(f"{name}_g_bridge", (0.18, 0.04, 0.04), bevel_offset=0.01,
                     loc=(0, -0.16, 0.18), parent=guitar_e, mat_=M_GUITAR_BLACK)
        # Arms strum/fret
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.27, 0, 1.18), parent=base)
            if side_idx == 0:
                sh.rotation_euler = (math.radians(-100), 0, math.radians(-50))
            else:
                sh.rotation_euler = (math.radians(-70), 0, math.radians(30))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_SHIRT_WHITE)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_SPANISH)
            smooth_sphere(f"{name}_hand{side_idx}", r=0.07, loc=(0, 0, -0.58),
                          parent=sh, mat_=M_SKIN_SPANISH)
            arms_e.append(sh)
    else:  # singer
        # Hands clasped raised
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.27, 0, 1.18), parent=base)
            sh.rotation_euler = (math.radians(-130), 0, math.radians(side*-20))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_SHIRT_WHITE)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_SPANISH)
            smooth_sphere(f"{name}_hand{side_idx}", r=0.07, loc=(0, 0, -0.58),
                          parent=sh, mat_=M_SKIN_SPANISH)
            arms_e.append(sh)
        # Open mouth singing
        beveled_cube(f"{name}_mouth", (0.08, 0.04, 0.06), loc=(0, -0.16, -0.07),
                     parent=head_e, mat_=M_GUITAR_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

musicians = []
# Cantaor (singer) center
cantaor = make_seated_musician("cantaor", (0, -10, 0.6), "singer", math.radians(0))
musicians.append(cantaor)
# 4 guitarists
guitar_specs = [
    ("guit1", (-3, -11, 0.6), math.radians(20)),
    ("guit2", (3, -11, 0.6), math.radians(-20)),
    ("guit3", (-1.5, -12.5, 0.6), math.radians(15)),
    ("guit4", (1.5, -12.5, 0.6), math.radians(-15)),
]
for spec in guitar_specs:
    name, loc, fac = spec
    g = make_seated_musician(name, loc, "guitar", facing=fac)
    musicians.append(g)

# ============ 4 SPECTATORS clapping (signature palmas) ============
def make_spectator(name, loc, dress_mat, hair_mat=M_HAIR_DARK_S, is_woman=True, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_cone(f"{name}_legs", r1=0.32, r2=0.24, depth=0.60, segs=14,
                loc=(0, 0, 0.35), parent=base, mat_=dress_mat)
    beveled_cube(f"{name}_torso", (0.40, 0.22, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 0.95), parent=base, mat_=dress_mat)
    cyl(f"{name}_neck", r=0.08, depth=0.15, segs=10, loc=(0, 0, 1.30),
        parent=base, mat_=M_SKIN_SPANISH)
    head_e = empty(f"{name}_he", (0, 0, 1.48), parent=base)
    smooth_sphere(f"{name}_head", r=0.17, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_SPANISH)
    smooth_sphere(f"{name}_hair", r=0.19, loc=(0, 0.05, 0.05),
                  parent=head_e, mat_=hair_mat, scale=(1, 1, 0.9))
    if is_woman:
        # Hair bun + rose
        smooth_sphere(f"{name}_bun", r=0.15, loc=(0, 0.22, 0.05),
                      parent=head_e, mat_=hair_mat, scale=(1.2, 0.8, 1.2))
        smooth_sphere(f"{name}_rose", r=0.06, loc=(0.16, 0.10, 0.10),
                      parent=head_e, mat_=M_ROSE_RED)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.13, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.10, 0.05, 0.04, 1), 0, 0.4,
                                emission=(0.40, 0.15, 0.08), emission_strength=1.0))
    # Arms clapping (signature palmas)
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.20), parent=base)
        sh.rotation_euler = (math.radians(-90), 0, math.radians(side*-25))
        cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
            loc=(0, 0, -0.15), parent=sh, mat_=dress_mat)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
            loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_SPANISH)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07, loc=(0, 0, -0.58),
                      parent=sh, mat_=M_SKIN_SPANISH)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

spectators = []
spec_specs = [
    ("sp1", (-9, -2, 0.5), M_DRESS_PURPLE_S, M_HAIR_DARK_S, True, math.radians(60)),
    ("sp2", (-9, 2, 0.5), M_DRESS_PINK_S, M_HAIR_DARK_S, True, math.radians(30)),
    ("sp3", (9, -2, 0.5), M_SUIT_BROWN, M_HAIR_DARK_S, False, math.radians(-60)),
    ("sp4", (9, 2, 0.5), M_DRESS_PINK_S, M_HAIR_DARK_S, True, math.radians(-30)),
]
for spec in spec_specs:
    name, loc, dress, hair, is_w, fac = spec
    s = make_spectator(name, loc, dress, hair_mat=hair, is_woman=is_w, facing=fac)
    spectators.append(s)

# ============ TABLES + WINE GLASSES + SANGRIA ============
table_pos = [(-9, -5, 0), (9, -5, 0)]
for ti, (tx, ty, tz) in enumerate(table_pos):
    t_e = empty(f"table{ti}", (tx, ty, tz))
    # Iron wrought leg
    cyl(f"t_leg{ti}", r=0.06, depth=0.80, segs=10,
        loc=(0, 0, 0.40), parent=t_e, mat_=M_TABLE_WROUGHT)
    # Top
    cyl(f"t_top{ti}", r=0.60, depth=0.06, segs=20,
        loc=(0, 0, 0.83), parent=t_e, mat_=M_COLUMN_MARBLE)
    # 2 wine glasses
    for gi in range(2):
        ga = gi * math.pi
        glass_e = empty(f"t_glass_e{ti}_{gi}", (math.cos(ga)*0.25, math.sin(ga)*0.25, 0.92), parent=t_e)
        cyl(f"t_g_stem{ti}_{gi}", r=0.015, depth=0.15, segs=10,
            loc=(0, 0, 0), parent=glass_e, mat_=M_GLASS)
        cyl(f"t_g_bowl{ti}_{gi}", r=0.06, depth=0.10, segs=14,
            loc=(0, 0, 0.10), parent=glass_e, mat_=M_GLASS)
        # Wine
        cyl(f"t_g_wine{ti}_{gi}", r=0.055, depth=0.08, segs=12,
            loc=(0, 0, 0.10), parent=glass_e, mat_=M_WINE_RED)
    # Sangria pitcher
    smooth_sphere(f"t_pit{ti}", r=0.10, segs=18, rings=12,
                  loc=(0, 0, 0.95), parent=t_e, mat_=M_GLASS, scale=(1, 1, 1.3))
    cyl(f"t_pit_n{ti}", r=0.05, depth=0.10, segs=12, loc=(0, 0, 1.10),
        parent=t_e, mat_=M_GLASS)
    smooth_sphere(f"t_sangria{ti}", r=0.08, loc=(0, 0, 0.95),
                  parent=t_e, mat_=M_SANGRIA, scale=(1, 1, 1.2))

# Olive jar
for ji in range(2):
    jx_o = -8 + ji*16
    jy_o = -8
    j_e = empty(f"jar{ji}", (jx_o, jy_o, 0))
    smooth_sphere(f"jar_body{ji}", r=0.50, segs=20, rings=14, loc=(0, 0, 0.50),
                  parent=j_e, mat_=M_AZULEJO_BLUE, scale=(1, 1, 1.3))
    # Decorative band
    cyl(f"jar_band{ji}", r=0.45, depth=0.05, segs=18, loc=(0, 0, 0.55),
        parent=j_e, mat_=M_AZULEJO_WHITE)
    # Mouth
    cyl(f"jar_m{ji}", r=0.25, depth=0.10, segs=14, loc=(0, 0, 1.0),
        parent=j_e, mat_=M_AZULEJO_BLUE)

# ============================================================
# ⭐ 600 ROSE PETALS + 400 CASTANET SPARKLES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 rose petals (signature)
rose_colors = [M_ROSE_RED, M_ROSE_PINK, M_ROSE_DEEP]
rose_petals = []
for i in range(600):
    px = random.uniform(-20, 20)
    py = random.uniform(-20, 20)
    pz = random.uniform(0.5, 12)
    col = rose_colors[i % 3]
    p_obj = smooth_sphere(f"rose_p{i}", r=random.uniform(0.10, 0.16), segs=10, rings=6,
                          loc=(px, py, pz), mat_=col,
                          scale=(1.5, 0.6, 0.15))
    p_obj.rotation_euler = (random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2))
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_speed"] = random.uniform(0.4, 1.3)
    p_obj["_drift_x"] = random.uniform(-1.6, 1.6)
    p_obj["_drift_y"] = random.uniform(-1.6, 1.6)
    rose_petals.append(p_obj)

# 400 castanet sparkles (signature)
castanet_sparkles = []
spark_colors = [M_SPARK_GOLD, M_SPARK_AMBER]
for i in range(400):
    # Concentrated near dancers + scatter
    if i < 200:
        # Near dancers
        cx = random.choice([-3, 3])
        cy = -5 + random.uniform(-1, 1)
        px = cx + random.uniform(-1.5, 1.5)
        py = cy + random.uniform(-1.5, 1.5)
        pz = random.uniform(1, 4)
    else:
        px = random.uniform(-15, 15)
        py = random.uniform(-15, 15)
        pz = random.uniform(1, 8)
    col = spark_colors[i % 2]
    s_obj = smooth_sphere(f"cs{i}", r=random.uniform(0.06, 0.10), segs=8, rings=6,
                          loc=(px, py, pz), mat_=col)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(0.5, 1.4)
    s_obj["_amp_y"] = random.uniform(0.5, 1.4)
    s_obj["_amp_z"] = random.uniform(0.4, 1.0)
    s_obj["_speed"] = random.uniform(0.8, 1.8)
    castanet_sparkles.append(s_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Female dancer twirl + arms
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Body twirl (signature flamenco zapateado)
    dancer_f_e.rotation_euler = (math.sin(t * 1.5) * math.radians(6),
                                  math.cos(t * 1.3) * math.radians(4),
                                  math.radians(30) + t * 1.5)
    dancer_f_e.location.z = abs(math.sin(t * 4.0)) * 0.10
    dancer_f_e.keyframe_insert("rotation_euler", frame=f)
    dancer_f_e.keyframe_insert("location", frame=f)
    # Arms wave
    for ai, arm in enumerate(df_arms):
        base_rx = arm.rotation_euler.x
        wave = math.sin(t * 2.5 + ai * math.pi) * math.radians(15)
        arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
        arm.keyframe_insert("rotation_euler", frame=f)
    # Head turn
    df_head_e.rotation_euler = (math.sin(t * 1.2) * math.radians(5), 0,
                                  math.sin(t * 1.0) * math.radians(15))
    df_head_e.keyframe_insert("rotation_euler", frame=f)

# Male dancer stomp
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Strong stomping
    dancer_m_e.location.z = abs(math.sin(t * 4.5)) * 0.12
    dancer_m_e.rotation_euler = (math.sin(t * 2.0) * math.radians(5),
                                   math.cos(t * 1.5) * math.radians(4),
                                   math.radians(-30) + math.sin(t * 1.0) * math.radians(15))
    dancer_m_e.keyframe_insert("location", frame=f)
    dancer_m_e.keyframe_insert("rotation_euler", frame=f)
    for ai, arm in enumerate(dm_arms):
        base_rx = arm.rotation_euler.x
        wave = math.sin(t * 3.0 + ai * math.pi) * math.radians(20)
        arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
        arm.keyframe_insert("rotation_euler", frame=f)
    dm_head_e.rotation_euler = (math.sin(t * 1.5) * math.radians(6), 0,
                                  math.sin(t * 1.2) * math.radians(15))
    dm_head_e.keyframe_insert("rotation_euler", frame=f)

# Musicians play guitar/sing
for m in musicians:
    phase = m["root"]["_phase"]
    base_z = m["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        m["root"].keyframe_insert("location", frame=f)
        for ai, arm in enumerate(m["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 4.5 + phase + ai * math.pi) * math.radians(18)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(8), 0,
                                    math.sin(t * 1.2 + phase) * math.radians(15))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Spectators clap palmas
for s in spectators:
    phase = s["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        for ai, arm in enumerate(s["arms"]):
            clap = math.sin(t * 6.0 + phase + ai * math.pi) * math.radians(15)
            arm.rotation_euler = (math.radians(-90) + clap, 0, math.radians((-1 if ai==0 else 1)*-25))
            arm.keyframe_insert("rotation_euler", frame=f)
        s["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                    math.sin(t * 1.2 + phase) * math.radians(15))
        s["he"].keyframe_insert("rotation_euler", frame=f)

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
# ⭐⭐⭐ 600 ROSE PETALS + 400 CASTANET SPARKLES (signature flamenco)
# ============================================================
for p in rose_petals:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    drift_x = p["_drift_x"]; drift_y = p["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        z = bz - (speed * t * 0.7) % 12
        x = bx + drift_x * math.sin(t * 1.3 + phase) * 0.6
        y = by + drift_y * math.cos(t * 1.1 + phase) * 0.6
        p.location = (x, y, max(0.05, z))
        p.rotation_euler = (phase + t * 1.7, phase + t * 1.5, phase + t * 2.0)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# 400 CASTANET SPARKLES vortex
for s in castanet_sparkles:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        s.location = (x, y, max(0.3, z))
        sc = 1 + math.sin(t * 5.0 + phase) * 0.4
        s.scale = (sc, sc, sc)
        s.keyframe_insert("location", frame=f)
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
out_glb = os.path.join(out_dir, "pbr_spain_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_spanish_andalusian_flamenco_patio] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_spanish_andalusian_flamenco_patio] ONE mosaic ground + Giralda tower + 8 Moorish arches + central fountain + 8 wrought iron balconies + bougainvilliers cascading + female + male dancers + cantaor + 4 guitarists + 4 spectators + tables + 600 ROSE PETALS + 400 CASTANET SPARKLES")
print("⭐ FIXES: 1 ground + 600 rose petals + 400 castanet sparkles (signature flamenco mandatory) ⭐")
