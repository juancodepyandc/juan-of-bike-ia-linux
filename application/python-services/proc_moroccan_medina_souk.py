"""
proc_moroccan_medina_souk.py — 222e procédural AuroraIA (86e qualité)
Moroccan souk night: ONE ground + 600 spice powder + 50 filigree lanterns + 12 spice stalls + 8 merchants + arches + minaret + dome + 4 donkeys + 3 cats + women + tea + chicha
FIXES : 1 ground + 600 spice powder drift thématique signature souk
"""
import bpy, bmesh, math, random, os

random.seed(0x6AAA222)

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

# Moroccan night palette
M_SKY = mat("sky", (0.08, 0.08, 0.20, 1.0), 0.0, 0.7, emission=(0.08,0.08,0.20), emission_strength=1.2)
M_MOON = mat("moon", (0.98, 0.92, 0.80, 1.0), 0.0, 0.20, emission=(0.98,0.92,0.80), emission_strength=12.0)
M_STAR = mat("star", (1.0, 1.0, 0.95, 1.0), 0.0, 0.20, emission=(1.0,1.0,0.95), emission_strength=11.0)

# Cobblestone ground
M_GROUND = mat("ground", (0.45, 0.35, 0.25, 1.0), 0.0, 0.85, emission=(0.40,0.32,0.22), emission_strength=0.4)
M_COBBLE = mat("cobble", (0.55, 0.45, 0.32, 1.0), 0.0, 0.80, emission=(0.50,0.40,0.28), emission_strength=0.5)
M_COBBLE_LIGHT = mat("cobble_l", (0.65, 0.55, 0.42, 1.0), 0.0, 0.75, emission=(0.60,0.50,0.38), emission_strength=0.6)

# Spice colors (signature souk)
M_SPICE_RED = mat("sp_r", (0.95, 0.20, 0.10, 1.0), 0.0, 0.55, emission=(0.90,0.20,0.10), emission_strength=2.0)
M_SPICE_ORANGE = mat("sp_o", (1.0, 0.55, 0.10, 1.0), 0.0, 0.55, emission=(1.0,0.55,0.10), emission_strength=2.2)
M_SPICE_YELLOW = mat("sp_y", (1.0, 0.85, 0.15, 1.0), 0.0, 0.50, emission=(1.0,0.85,0.15), emission_strength=2.4)
M_SPICE_GREEN = mat("sp_g", (0.40, 0.65, 0.20, 1.0), 0.0, 0.55, emission=(0.38,0.60,0.18), emission_strength=1.8)
M_SPICE_BROWN = mat("sp_br", (0.65, 0.35, 0.15, 1.0), 0.0, 0.55, emission=(0.60,0.32,0.15), emission_strength=1.5)
M_SPICE_PURPLE = mat("sp_pu", (0.55, 0.20, 0.65, 1.0), 0.0, 0.55, emission=(0.50,0.18,0.60), emission_strength=2.0)
M_SPICE_WHITE = mat("sp_w", (0.95, 0.92, 0.80, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.75), emission_strength=1.2)

# Walls
M_WALL_OCHRE = mat("wall_o", (0.85, 0.55, 0.30, 1.0), 0.0, 0.70, emission=(0.78,0.50,0.28), emission_strength=0.6)
M_WALL_ROSE = mat("wall_r", (0.85, 0.45, 0.40, 1.0), 0.0, 0.70, emission=(0.78,0.42,0.38), emission_strength=0.6)
M_WALL_TERRA = mat("wall_t", (0.75, 0.40, 0.25, 1.0), 0.0, 0.75, emission=(0.70,0.38,0.22), emission_strength=0.5)
M_ARCH_STONE = mat("arch", (0.95, 0.78, 0.55, 1.0), 0.0, 0.65, emission=(0.88,0.72,0.52), emission_strength=0.6)
M_DOME_GREEN = mat("dome", (0.18, 0.55, 0.35, 1.0), 0.4, 0.30, emission=(0.18,0.50,0.32), emission_strength=1.8)
M_DOME_GOLD = mat("dome_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.92,0.75,0.28), emission_strength=1.5)
M_MINARET_TILE = mat("min_t", (0.30, 0.55, 0.75, 1.0), 0.4, 0.30, emission=(0.28,0.50,0.70), emission_strength=1.2)

# Stalls
M_STALL_WOOD = mat("stall_w", (0.42, 0.25, 0.15, 1.0), 0.0, 0.70, emission=(0.38,0.22,0.13), emission_strength=0.4)
M_STALL_CLOTH = mat("stall_c", (0.65, 0.20, 0.18, 1.0), 0.0, 0.65, emission=(0.60,0.20,0.18), emission_strength=0.5)
M_BURLAP = mat("burlap", (0.65, 0.55, 0.40, 1.0), 0.0, 0.85, emission=(0.60,0.52,0.38), emission_strength=0.4)
M_BASKET = mat("basket", (0.55, 0.38, 0.20, 1.0), 0.0, 0.85, emission=(0.50,0.35,0.18), emission_strength=0.3)

# Merchants
M_SKIN_BERBER = mat("skin", (0.80, 0.62, 0.45, 1.0), 0.0, 0.55, emission=(0.72,0.58,0.42), emission_strength=0.4)
M_DJELLABA_BROWN = mat("dj_br", (0.55, 0.35, 0.20, 1.0), 0.0, 0.70, emission=(0.50,0.32,0.18), emission_strength=0.5)
M_DJELLABA_BLUE = mat("dj_b", (0.20, 0.40, 0.55, 1.0), 0.0, 0.70, emission=(0.18,0.38,0.52), emission_strength=0.5)
M_DJELLABA_WHITE = mat("dj_w", (0.92, 0.88, 0.78, 1.0), 0.0, 0.70, emission=(0.85,0.82,0.72), emission_strength=0.6)
M_DJELLABA_GREEN = mat("dj_g", (0.30, 0.55, 0.35, 1.0), 0.0, 0.70, emission=(0.28,0.50,0.32), emission_strength=0.5)
M_TURBAN_RED = mat("tur_r", (0.78, 0.20, 0.18, 1.0), 0.0, 0.65, emission=(0.72,0.20,0.18), emission_strength=0.7)
M_TURBAN_BLUE = mat("tur_b", (0.20, 0.45, 0.78, 1.0), 0.0, 0.65, emission=(0.18,0.42,0.72), emission_strength=0.7)
M_TURBAN_GOLD = mat("tur_g", (0.95, 0.78, 0.30, 1.0), 0.5, 0.40, emission=(0.90,0.72,0.28), emission_strength=0.8)
M_HAIK_WHITE = mat("haik", (0.95, 0.92, 0.88, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.82), emission_strength=0.6)
M_BEARD_DARK = mat("beard", (0.18, 0.10, 0.06, 1.0), 0.0, 0.85)

# Donkeys
M_DONKEY = mat("donkey", (0.55, 0.42, 0.30, 1.0), 0.0, 0.75, emission=(0.50,0.40,0.28), emission_strength=0.4)
M_DONKEY_BELLY = mat("donkey_b", (0.85, 0.78, 0.65, 1.0), 0.0, 0.65, emission=(0.78,0.72,0.60), emission_strength=0.4)
M_DONKEY_SADDLE = mat("don_s", (0.78, 0.30, 0.20, 1.0), 0.0, 0.55, emission=(0.72,0.28,0.18), emission_strength=0.5)

# Cats
M_CAT_GREY = mat("cat_g", (0.55, 0.50, 0.48, 1.0), 0.0, 0.65, emission=(0.50,0.45,0.42), emission_strength=0.4)
M_CAT_ORANGE = mat("cat_o", (0.85, 0.50, 0.20, 1.0), 0.0, 0.65, emission=(0.78,0.48,0.18), emission_strength=0.5)
M_CAT_BLACK = mat("cat_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.80)
M_CAT_EYE = mat("cat_eye", (0.85, 1.0, 0.30, 1.0), 0.0, 0.10, emission=(0.85,1.0,0.30), emission_strength=8.0)

# Lanterns (signature filigree)
M_LANTERN_BRASS = mat("lant_br", (0.85, 0.65, 0.25, 1.0), 0.85, 0.25, emission=(0.80,0.60,0.22), emission_strength=0.7)
M_LANTERN_GLOW_RED = mat("lant_r", (1.0, 0.30, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.30,0.20), emission_strength=18.0, alpha=0.85)
M_LANTERN_GLOW_BLUE = mat("lant_bl", (0.30, 0.55, 1.0, 1.0), 0.0, 0.20, emission=(0.30,0.55,1.0), emission_strength=16.0, alpha=0.85)
M_LANTERN_GLOW_GOLD = mat("lant_go", (1.0, 0.82, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.82,0.30), emission_strength=20.0, alpha=0.85)
M_LANTERN_GLOW_GREEN = mat("lant_gr", (0.30, 1.0, 0.55, 1.0), 0.0, 0.20, emission=(0.30,1.0,0.55), emission_strength=16.0, alpha=0.85)

# Carpets
M_CARPET_RED = mat("c_red", (0.78, 0.18, 0.20, 1.0), 0.0, 0.65, emission=(0.72,0.18,0.18), emission_strength=0.7)
M_CARPET_BLUE = mat("c_blue", (0.20, 0.40, 0.65, 1.0), 0.0, 0.65, emission=(0.18,0.38,0.60), emission_strength=0.6)
M_CARPET_GOLD = mat("c_gold", (0.95, 0.78, 0.30, 1.0), 0.4, 0.45, emission=(0.88,0.72,0.28), emission_strength=0.8)
M_CARPET_GREEN = mat("c_green", (0.30, 0.55, 0.35, 1.0), 0.0, 0.65, emission=(0.28,0.50,0.32), emission_strength=0.5)

# Brass teapot, chicha
M_BRASS = mat("brass", (0.85, 0.62, 0.25, 1.0), 0.85, 0.25, emission=(0.80,0.58,0.22), emission_strength=0.7)
M_GLASS_BLUE = mat("glass", (0.30, 0.55, 0.85, 0.65), 0.4, 0.10, emission=(0.30,0.55,0.85), emission_strength=2.0, alpha=0.65)
M_CHICHA_SMOKE = mat("smoke", (0.65, 0.80, 0.95, 1.0), 0.0, 0.30, emission=(0.60,0.75,0.92), emission_strength=2.0, alpha=0.55)

# Spice powder cloud (signature drifting)
M_POWDER_RED = mat("pwd_r", (1.0, 0.30, 0.15, 1.0), 0.0, 0.30, emission=(1.0,0.30,0.15), emission_strength=8.0, alpha=0.75)
M_POWDER_ORANGE = mat("pwd_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.30, emission=(1.0,0.55,0.15), emission_strength=9.0, alpha=0.75)
M_POWDER_YELLOW = mat("pwd_y", (1.0, 0.92, 0.20, 1.0), 0.0, 0.30, emission=(1.0,0.92,0.20), emission_strength=10.0, alpha=0.75)
M_POWDER_GREEN = mat("pwd_g", (0.55, 0.85, 0.20, 1.0), 0.0, 0.30, emission=(0.50,0.80,0.18), emission_strength=8.0, alpha=0.75)
M_POWDER_PURPLE = mat("pwd_pu", (0.75, 0.30, 0.85, 1.0), 0.0, 0.30, emission=(0.70,0.28,0.78), emission_strength=8.5, alpha=0.75)

# ============ SKY + MOON + STARS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
moon_e = empty("moon_e", (-30, 50, 35))
smooth_sphere("moon", r=4.5, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON, scale=(1, 1, 0.95))
for i in range(3):
    smooth_sphere(f"moon_halo{i}", r=4.5 + (i+1)*1.3, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)

# 200 stars
for i in range(200):
    a = random.uniform(0, math.pi*2)
    phi = random.uniform(math.pi/6, math.pi/2.2)
    r_star = 115
    sx = r_star * math.cos(phi) * math.cos(a)
    sy = r_star * math.cos(phi) * math.sin(a)
    sz = r_star * math.sin(phi) * 0.4
    smooth_sphere(f"star{i}", r=random.uniform(0.18, 0.42), segs=10, rings=8,
                  loc=(sx, sy, sz), mat_=M_STAR)

# ============ ONE clean cobblestone ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)
# Cobblestone variation (organic 3D scattered)
for i in range(80):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(3, 40)
    cx = rad * math.cos(a)
    cy = rad * math.sin(a)
    smooth_sphere(f"cobble{i}", r=random.uniform(0.30, 0.50), segs=12, rings=8,
                  loc=(cx, cy, 0.10),
                  mat_=M_COBBLE if i % 2 == 0 else M_COBBLE_LIGHT,
                  scale=(1.2, 1.1, 0.28))

# ============ MEDINA WALLS + ARCHES ============
# Side walls (left and right of souk plaza, with passages)
def make_archway(name, loc, scale=1.0, color=M_WALL_OCHRE):
    base = empty(name, loc)
    # 2 pillars
    for side in (-1, 1):
        beveled_cube(f"{name}_pillar{side}", (0.5*scale, 0.8*scale, 4.0*scale), bevel_offset=0.04,
                     loc=(side*1.5*scale, 0, 2.0*scale), parent=base, mat_=color)
    # Top arch (Moorish horseshoe arch - 7 segments)
    for seg in range(7):
        ang = math.pi - (seg / 6.0) * math.pi
        ax = math.cos(ang) * 1.5 * scale
        az = 4.0*scale + math.sin(ang) * 1.2 * scale
        arch_s = beveled_cube(f"{name}_arch{seg}", (0.5*scale, 0.8*scale, 0.5*scale), bevel_offset=0.04,
                              loc=(ax, 0, az), parent=base, mat_=M_ARCH_STONE)
        arch_s.rotation_euler = (0, ang - math.pi/2, 0)
    # Inner archway (recessed)
    smooth_cone(f"{name}_inside", r1=1.4*scale, r2=1.0*scale, depth=0.30*scale, segs=10,
                loc=(0, 0, 4.0*scale), parent=base, mat_=M_WALL_TERRA).rotation_euler = (math.radians(90), 0, 0)
    # Top decorative band
    beveled_cube(f"{name}_band_top", (3.5*scale, 0.7*scale, 0.40*scale), bevel_offset=0.04,
                 loc=(0, 0, 5.5*scale), parent=base, mat_=M_WALL_OCHRE)
    return base

# 4 arches around plaza
arches_e = []
arch_specs = [
    ("arch_n", (0, 18, 0), math.radians(0)),
    ("arch_s", (0, -18, 0), math.radians(180)),
    ("arch_e", (18, 0, 0), math.radians(90)),
    ("arch_w", (-18, 0, 0), math.radians(-90)),
]
for spec in arch_specs:
    name, loc, fac = spec
    arch_obj = make_archway(name, loc, scale=1.5)
    arch_obj.rotation_euler = (0, 0, fac)
    arches_e.append(arch_obj)

# ============ MOSQUE + MINARET (background landmark) ============
mosque_e = empty("mosque", loc=(22, 22, 0))
# Base building
beveled_cube("m_base", (8, 8, 1.0), bevel_offset=0.06, loc=(0, 0, 0.5),
             parent=mosque_e, mat_=M_WALL_ROSE)
# Walls
beveled_cube("m_walls", (7, 7, 4), bevel_offset=0.06, loc=(0, 0, 3),
             parent=mosque_e, mat_=M_WALL_OCHRE)
# DOME (green/gold signature)
smooth_sphere("m_dome", r=3.5, segs=28, rings=18, loc=(0, 0, 5.5),
              parent=mosque_e, mat_=M_DOME_GREEN, scale=(1, 1, 0.95))
# Dome ribs
for ri in range(8):
    ra = (ri / 8.0) * math.pi * 2
    rib = beveled_cube(f"m_dome_rib{ri}", (0.05, 0.10, 3.5),
                       loc=(3.5*math.cos(ra), 3.5*math.sin(ra), 5.5),
                       parent=mosque_e, mat_=M_DOME_GOLD)
    rib.rotation_euler = (math.radians(-90 + (ri/8)*180), math.radians(ri*22.5), 0)
# Dome top spike + crescent
smooth_cone("m_spike", r1=0.20, r2=0.03, depth=1.5, segs=14,
            loc=(0, 0, 8.5), parent=mosque_e, mat_=M_DOME_GOLD)
smooth_sphere("m_crescent_b", r=0.20, loc=(0, 0, 9.5), parent=mosque_e, mat_=M_DOME_GOLD)
# MINARET (signature tall tower)
minaret_e = empty("minaret", (5, 0, 0), parent=mosque_e)
# Square tower base
beveled_cube("min_base", (1.6, 1.6, 8.0), bevel_offset=0.05, loc=(0, 0, 4.0),
             parent=minaret_e, mat_=M_WALL_OCHRE)
# Decorative tile bands (signature Moroccan zellige)
for band in range(4):
    bz = 1.0 + band * 1.8
    cyl(f"min_band{band}", r=0.85, depth=0.20, segs=4,
        loc=(0, 0, bz), parent=minaret_e, mat_=M_MINARET_TILE)
# Balcony
beveled_cube("min_balc", (1.9, 1.9, 0.30), bevel_offset=0.04,
             loc=(0, 0, 8.2), parent=minaret_e, mat_=M_WALL_OCHRE)
# Smaller upper tower
beveled_cube("min_upper", (1.2, 1.2, 2.5), bevel_offset=0.04,
             loc=(0, 0, 9.7), parent=minaret_e, mat_=M_WALL_OCHRE)
# Top dome
smooth_sphere("min_dome", r=0.9, loc=(0, 0, 11.4),
              parent=minaret_e, mat_=M_DOME_GREEN, scale=(1, 1, 0.95))
# Top finial + crescent
smooth_cone("min_spike", r1=0.15, r2=0.03, depth=1.0, segs=10,
            loc=(0, 0, 12.4), parent=minaret_e, mat_=M_DOME_GOLD)
# Crescent top
crescent_e = empty("min_cre", (0, 0, 13.0), parent=minaret_e)
smooth_sphere("min_cre_f", r=0.20, loc=(0, 0, 0), parent=crescent_e, mat_=M_DOME_GOLD)
smooth_sphere("min_cre_c", r=0.18, loc=(0.10, 0, 0.05), parent=crescent_e, mat_=M_WALL_OCHRE)

# ============ 12 SPICE STALLS (signature conical heaps) ============
def make_stall(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Wood table
    beveled_cube(f"{name}_table", (2.4, 1.2, 0.10), bevel_offset=0.04,
                 loc=(0, 0, 0.80), parent=base, mat_=M_STALL_WOOD)
    # Table legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_leg{x}{y}", r=0.06, depth=0.85, segs=8,
                loc=(x*1.1, y*0.55, 0.42), parent=base, mat_=M_STALL_WOOD)
    # Awning above (cloth)
    awning_e = empty(f"{name}_aw_e", (0, 0, 2.4), parent=base)
    awning_e.rotation_euler = (math.radians(-10), 0, 0)
    beveled_cube(f"{name}_awning", (2.8, 1.6, 0.06), bevel_offset=0.02,
                 loc=(0, -0.2, 0), parent=awning_e, mat_=M_STALL_CLOTH)
    # Awning posts
    for side in (-1, 1):
        cyl(f"{name}_post{side}", r=0.05, depth=1.6, segs=8,
            loc=(side*1.3, -0.7, 1.6), parent=base, mat_=M_STALL_WOOD)
    # 6 spice heaps (signature conical piles)
    spice_colors = [M_SPICE_RED, M_SPICE_ORANGE, M_SPICE_YELLOW,
                    M_SPICE_GREEN, M_SPICE_BROWN, M_SPICE_PURPLE, M_SPICE_WHITE]
    for hi in range(6):
        hx = (hi - 2.5) * 0.35
        hy = 0
        col = spice_colors[(hi + hash(name) % 7) % len(spice_colors)]
        # Burlap base bowl
        cyl(f"{name}_bowl{hi}", r=0.16, depth=0.05, segs=16,
            loc=(hx, hy, 0.88), parent=base, mat_=M_BURLAP)
        # Conical heap (signature)
        smooth_cone(f"{name}_heap{hi}", r1=0.16, r2=0.02, depth=0.30, segs=14,
                    loc=(hx, hy, 1.05), parent=base, mat_=col)
        # Glow inside (powder glow)
        smooth_sphere(f"{name}_heap_g{hi}", r=0.10, loc=(hx, hy, 0.95),
                      parent=base, mat_=col, scale=(1, 1, 0.5))
    # Backwall hanging baskets
    for bi in range(3):
        bx_b = (bi - 1) * 0.7
        # Hanging basket
        cyl(f"{name}_bsk{bi}", r=0.18, depth=0.30, segs=14,
            loc=(bx_b, 0.55, 1.5), parent=base, mat_=M_BASKET)
        # Spices inside
        col = spice_colors[(bi + hash(name)) % 7]
        smooth_sphere(f"{name}_bsk_s{bi}", r=0.15, loc=(bx_b, 0.55, 1.55),
                      parent=base, mat_=col, scale=(1, 1, 0.6))
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

stalls = []
# 12 stalls along 2 rows
stall_specs = []
for row in range(2):
    row_y = (row * 2 - 1) * 6
    for col in range(6):
        col_x = (col - 2.5) * 4
        # Face inward
        facing = math.radians(180 if row == 0 else 0)
        stall_specs.append((f"stall_{row}_{col}", (col_x, row_y, 0), facing))

for spec in stall_specs:
    name, loc, fac = spec
    s = make_stall(name, loc, facing=fac)
    stalls.append(s)

# ============ 8 MERCHANTS + WOMEN ============
def make_merchant(name, loc, robe_mat, turban_mat, has_beard=True, facing=0, action="gesture", scale=1.0, is_woman=False):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long djellaba robe
    smooth_cone(f"{name}_robe", r1=0.55*scale, r2=0.32*scale, depth=1.8*scale, segs=18,
                loc=(0, 0, 0.90*scale), parent=base, mat_=robe_mat)
    # Belt
    cyl(f"{name}_belt", r=0.40*scale, depth=0.08*scale, segs=14,
        loc=(0, 0, 1.50*scale), parent=base, mat_=M_DOME_GOLD)
    # Torso
    beveled_cube(f"{name}_torso", (0.42*scale, 0.25*scale, 0.55*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.95*scale), parent=base, mat_=robe_mat)
    # Neck
    cyl(f"{name}_neck", r=0.09*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 2.30*scale), parent=base, mat_=M_SKIN_BERBER)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.48*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_BERBER)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    if is_woman:
        # Haïk veil (signature white drape covering head)
        smooth_sphere(f"{name}_haik", r=0.22*scale, loc=(0, 0.04*scale, 0.06*scale),
                      parent=head_e, mat_=M_HAIK_WHITE, scale=(1.15, 1.05, 1.05))
        # Veil over face
        beveled_cube(f"{name}_veil", (0.20*scale, 0.06*scale, 0.18*scale), bevel_offset=0.02,
                     loc=(0, -0.16*scale, -0.05*scale), parent=head_e, mat_=M_HAIK_WHITE)
        # Long body veil
        smooth_cone(f"{name}_body_veil", r1=0.52*scale, r2=0.37*scale, depth=2.0*scale, segs=16,
                    loc=(0, 0, 1.05*scale), parent=base, mat_=M_HAIK_WHITE)
    else:
        # Hair
        smooth_sphere(f"{name}_hair", r=0.20*scale, loc=(0, 0.03*scale, 0.05*scale),
                      parent=head_e, mat_=M_BEARD_DARK, scale=(1, 1, 0.85))
        # Turban (signature wrap)
        for tw in range(4):
            cyl(f"{name}_turban_{tw}", r=0.20*scale + tw*0.005*scale, depth=0.08*scale, segs=16,
                loc=(0, 0, 0.13*scale + tw*0.04*scale), parent=head_e, mat_=turban_mat)
        # Turban gem
        smooth_sphere(f"{name}_t_gem", r=0.04*scale, loc=(0, -0.20*scale, 0.18*scale),
                      parent=head_e, mat_=M_SPICE_RED)
        # Beard
        if has_beard:
            smooth_sphere(f"{name}_beard", r=0.14*scale, loc=(0, -0.15*scale, -0.12*scale),
                          parent=head_e, mat_=M_BEARD_DARK, scale=(1.1, 0.8, 1.0))
    # Arms (gesture)
    arms_e = []
    arm_poses = {
        "gesture": [(math.radians(-80), -20), (math.radians(-30), 10)],
        "open": [(math.radians(-100), -30), (math.radians(-100), 30)],
        "hold": [(math.radians(-60), -10), (math.radians(-60), 10)],
    }
    pose = arm_poses.get(action, arm_poses["gesture"])
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 2.20*scale), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15 + rz))
        # Sleeve
        smooth_cone(f"{name}_sleeve{side_idx}", r1=0.15*scale, r2=0.10*scale, depth=0.50*scale, segs=12,
                    loc=(0, 0, -0.25*scale), parent=sh, mat_=robe_mat)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.60*scale), parent=sh, mat_=M_SKIN_BERBER)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07*scale, loc=(0, 0, -0.78*scale),
                      parent=sh, mat_=M_SKIN_BERBER)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

people = []
# 8 merchants behind stalls
people_specs = [
    ("merc1", (-9, 4.5, 0), M_DJELLABA_BROWN, M_TURBAN_RED, "gesture", math.radians(180), False),
    ("merc2", (-5, 4.5, 0), M_DJELLABA_BLUE, M_TURBAN_BLUE, "open", math.radians(180), False),
    ("merc3", (0, 4.5, 0), M_DJELLABA_WHITE, M_TURBAN_GOLD, "hold", math.radians(180), False),
    ("merc4", (5, 4.5, 0), M_DJELLABA_GREEN, M_TURBAN_RED, "gesture", math.radians(180), False),
    ("merc5", (-9, -4.5, 0), M_DJELLABA_BLUE, M_TURBAN_GOLD, "gesture", math.radians(0), False),
    ("merc6", (-5, -4.5, 0), M_DJELLABA_BROWN, M_TURBAN_BLUE, "open", math.radians(0), False),
    ("merc7", (0, -4.5, 0), M_DJELLABA_WHITE, M_TURBAN_RED, "hold", math.radians(0), False),
    ("merc8", (5, -4.5, 0), M_DJELLABA_GREEN, M_TURBAN_GOLD, "gesture", math.radians(0), False),
    # 3 women in haïk
    ("woman1", (-12, 0, 0), M_HAIK_WHITE, None, "open", math.radians(90), True),
    ("woman2", (10, 1, 0), M_HAIK_WHITE, None, "hold", math.radians(-90), True),
    ("woman3", (2, 12, 0), M_HAIK_WHITE, None, "gesture", math.radians(180), True),
]
for spec in people_specs:
    name, loc, robe, turban, act, fac, is_w = spec
    p = make_merchant(name, loc, robe, turban, has_beard=not is_w, facing=fac, action=act, is_woman=is_w)
    people.append(p)

# ============ 4 DONKEYS + 3 CATS ============
def make_donkey(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.50, segs=20, rings=14, loc=(0, 0, 0.90),
                  parent=base, mat_=M_DONKEY, scale=(1.7, 1, 1.0))
    smooth_sphere(f"{name}_belly", r=0.40, loc=(0, 0, 0.75),
                  parent=base, mat_=M_DONKEY_BELLY, scale=(1.5, 0.95, 0.7))
    # Saddle with cargo (signature)
    beveled_cube(f"{name}_saddle", (0.85, 0.55, 0.20), bevel_offset=0.04,
                 loc=(0, 0, 1.30), parent=base, mat_=M_DONKEY_SADDLE)
    # Cargo bags
    for side in (-1, 1):
        smooth_sphere(f"{name}_bag{side}", r=0.20, loc=(0, side*0.40, 1.20),
                      parent=base, mat_=M_BASKET, scale=(1.2, 1, 1))
    # Neck
    neck = beveled_cube(f"{name}_neck", (0.35, 0.30, 0.55), bevel_offset=0.04,
                       loc=(0.65, 0, 1.05), parent=base, mat_=M_DONKEY)
    neck.rotation_euler = (0, math.radians(-20), 0)
    # Head
    head_e = empty(f"{name}_he", (0.95, 0, 1.25), parent=base)
    beveled_cube(f"{name}_head", (0.40, 0.20, 0.25), bevel_offset=0.04,
                 loc=(0, 0, 0), parent=head_e, mat_=M_DONKEY)
    smooth_cone(f"{name}_muzzle", r1=0.10, r2=0.08, depth=0.20, segs=12,
                loc=(0.22, 0, -0.05), parent=head_e,
                mat_=M_DONKEY_BELLY).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.035,
                      loc=(0.05, side*0.10, 0.05), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # LONG EARS (signature donkey)
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.07, r2=0.02, depth=0.35, segs=10,
                          loc=(-0.05, side*0.08, 0.20), parent=head_e, mat_=M_DONKEY)
        ear.rotation_euler = (math.radians(-10), 0, math.radians(side*12))
    # 4 legs
    for x_idx, x in enumerate((0.40, -0.40)):
        for y_idx, y in enumerate((-0.30, 0.30)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.09, depth=0.70, segs=10,
                loc=(x, y, 0.35), parent=base, mat_=M_DONKEY)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.10, depth=0.10, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_CAT_BLACK)
    # Tail
    cyl(f"{name}_tail", r=0.04, depth=0.40, segs=8,
        loc=(-0.65, 0, 0.95), parent=base, mat_=M_DONKEY)
    smooth_sphere(f"{name}_tail_tuft", r=0.10, loc=(-0.78, 0, 0.65),
                  parent=base, mat_=M_DONKEY)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

donkeys = [
    make_donkey("don1", (-15, -8, 0), math.radians(120)),
    make_donkey("don2", (14, -10, 0), math.radians(-60)),
    make_donkey("don3", (-13, 8, 0), math.radians(60)),
    make_donkey("don4", (15, 7, 0), math.radians(-120)),
]

# Cats
def make_cat(name, loc, color, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.18, segs=18, rings=12, loc=(0, 0, 0.30),
                  parent=base, mat_=color, scale=(1.7, 0.9, 0.9))
    # Head
    head_e = empty(f"{name}_he", (0.27, 0, 0.40), parent=base)
    smooth_sphere(f"{name}_head", r=0.13, segs=16, rings=10, loc=(0, 0, 0),
                  parent=head_e, mat_=color)
    # Pointed ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.04, r2=0.005, depth=0.10, segs=8,
                          loc=(-0.02, side*0.07, 0.13), parent=head_e, mat_=color)
        ear.rotation_euler = (math.radians(-15), 0, math.radians(side*15))
    # Eyes (glowing)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025,
                      loc=(0.08, side*0.06, 0.03), parent=head_e, mat_=M_CAT_EYE)
    # Snout + nose
    smooth_cone(f"{name}_snout", r1=0.06, r2=0.04, depth=0.10, segs=10,
                loc=(0.12, 0, -0.03), parent=head_e,
                mat_=color).rotation_euler = (0, math.radians(90), 0)
    smooth_sphere(f"{name}_nose", r=0.02, loc=(0.17, 0, -0.04), parent=head_e, mat_=M_DOME_GREEN if False else M_BEARD_DARK)
    # 4 legs
    for x_idx, x in enumerate((0.15, -0.15)):
        for y_idx, y in enumerate((-0.08, 0.08)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.03, depth=0.20, segs=8,
                loc=(x, y, 0.10), parent=base, mat_=color)
    # Tail (curled up)
    tail_e = empty(f"{name}_te", (-0.28, 0, 0.40), parent=base)
    for ti in range(5):
        cyl(f"{name}_tail{ti}", r=0.035 - ti*0.003, depth=0.08, segs=6,
            loc=(0, 0, ti*0.06), parent=tail_e, mat_=color)
    tail_e.rotation_euler = (math.radians(-50), 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

cats = [
    make_cat("cat1", (-3, -2, 0), M_CAT_GREY, math.radians(45)),
    make_cat("cat2", (4, -3, 0), M_CAT_ORANGE, math.radians(-30)),
    make_cat("cat3", (1, 8, 0), M_CAT_BLACK, math.radians(120)),
]

# ============ 50 HANGING LANTERNS (filigree signature) ============
lantern_colors = [M_LANTERN_GLOW_RED, M_LANTERN_GLOW_BLUE, M_LANTERN_GLOW_GOLD, M_LANTERN_GLOW_GREEN]
lanterns = []
for i in range(50):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 16)
    lx = rad * math.cos(a)
    ly = rad * math.sin(a)
    lz = random.uniform(4, 9)
    l_e = empty(f"lant{i}", (lx, ly, lz))
    # Chain
    for ci in range(4):
        smooth_sphere(f"lant_ch{i}_{ci}", r=0.03,
                      loc=(0, 0, ci*0.3 + 0.5), parent=l_e, mat_=M_LANTERN_BRASS)
    # Top brass cap
    cyl(f"lant_top{i}", r=0.20, depth=0.05, segs=14,
        loc=(0, 0, 0.4), parent=l_e, mat_=M_LANTERN_BRASS)
    # Main body (decorative cone shape - signature filigree)
    col = lantern_colors[i % 4]
    smooth_sphere(f"lant_b{i}", r=0.22, segs=16, rings=12,
                  loc=(0, 0, 0.05), parent=l_e, mat_=col, scale=(1, 1, 1.3))
    # Brass cage frame (8 vertical ribs - signature filigree)
    for fri in range(8):
        fra = (fri / 8.0) * math.pi * 2
        rib = beveled_cube(f"lant_rib{i}_{fri}", (0.015, 0.015, 0.50), bevel_offset=0.005,
                          loc=(0.22*math.cos(fra), 0.22*math.sin(fra), 0.10),
                          parent=l_e, mat_=M_LANTERN_BRASS)
    # Horizontal bands
    for hbi in range(3):
        cyl(f"lant_hb{i}_{hbi}", r=0.23, depth=0.012, segs=16,
            loc=(0, 0, -0.10 + hbi*0.20), parent=l_e, mat_=M_LANTERN_BRASS)
    # Bottom tassel
    cyl(f"lant_tas{i}", r=0.02, depth=0.20, segs=6,
        loc=(0, 0, -0.30), parent=l_e, mat_=M_LANTERN_BRASS)
    smooth_sphere(f"lant_tas_b{i}", r=0.04, loc=(0, 0, -0.45),
                  parent=l_e, mat_=M_LANTERN_BRASS)
    l_e["_phase"] = random.uniform(0, math.pi*2)
    lanterns.append(l_e)

# ============ TEA SERVICE + CHICHA CORNER ============
tea_e = empty("tea", loc=(0, -15, 0))
# Carpet area
for c_idx, c_pos in enumerate([(0, 0), (-1.2, 0.5), (1.2, 0.5)]):
    carpet_col = [M_CARPET_RED, M_CARPET_BLUE, M_CARPET_GOLD][c_idx]
    cx_c, cy_c = c_pos
    beveled_cube(f"carpet{c_idx}", (2.0, 1.4, 0.05), bevel_offset=0.03,
                 loc=(cx_c, cy_c, 0.05), parent=tea_e, mat_=carpet_col)
# Brass teapot center
teapot_e = empty("teapot", (0, 0, 0.20), parent=tea_e)
smooth_sphere("tp_body", r=0.18, segs=18, rings=12, loc=(0, 0, 0),
              parent=teapot_e, mat_=M_BRASS, scale=(1, 1, 1.2))
smooth_cone("tp_spout", r1=0.06, r2=0.025, depth=0.30, segs=10,
            loc=(0.20, 0, 0.05), parent=teapot_e,
            mat_=M_BRASS).rotation_euler = (0, math.radians(-70), 0)
beveled_cube("tp_handle", (0.04, 0.04, 0.30), bevel_offset=0.01,
             loc=(-0.18, 0, 0.05), parent=teapot_e, mat_=M_BRASS)
cyl("tp_lid", r=0.08, depth=0.05, segs=14, loc=(0, 0, 0.22),
    parent=teapot_e, mat_=M_BRASS)
smooth_sphere("tp_lid_knob", r=0.04, loc=(0, 0, 0.28), parent=teapot_e, mat_=M_BRASS)
# 4 tea glasses around
for tg in range(4):
    tga = (tg / 4.0) * math.pi * 2
    glass_e = empty(f"glass{tg}", (0.35*math.cos(tga), 0.35*math.sin(tga), 0.15), parent=tea_e)
    cyl(f"glass_b{tg}", r=0.05, depth=0.10, segs=14, loc=(0, 0, 0.05),
        parent=glass_e, mat_=M_GLASS_BLUE)
    # Tea inside
    cyl(f"glass_tea{tg}", r=0.045, depth=0.06, segs=12, loc=(0, 0, 0.05),
        parent=glass_e, mat_=mat(f"tea_m{tg}", (0.55, 0.30, 0.10, 1), 0, 0.3,
                                    emission=(0.50,0.30,0.10), emission_strength=0.5))
# CHICHA (hookah) - signature
chicha_e = empty("chicha", (-1.5, -0.5, 0.10), parent=tea_e)
# Glass base
smooth_sphere("ch_base", r=0.25, segs=20, rings=14, loc=(0, 0, 0.25),
              parent=chicha_e, mat_=M_GLASS_BLUE, scale=(1, 1, 1.2))
# Liquid inside
smooth_sphere("ch_liq", r=0.20, loc=(0, 0, 0.18),
              parent=chicha_e, mat_=mat("ch_liq_m", (0.30, 0.55, 0.85, 0.85), 0.3, 0.15,
                                          emission=(0.30,0.55,0.85), emission_strength=1.5, alpha=0.85))
# Stem
cyl("ch_stem", r=0.04, depth=0.80, segs=12, loc=(0, 0, 0.85),
    parent=chicha_e, mat_=M_BRASS)
# Bowl top
cyl("ch_bowl", r=0.12, depth=0.12, segs=14, loc=(0, 0, 1.30),
    parent=chicha_e, mat_=M_BRASS)
# Tobacco/coal glowing
smooth_sphere("ch_coal", r=0.08, loc=(0, 0, 1.40), parent=chicha_e,
              mat_=mat("coal", (1.0, 0.30, 0.10, 1), 0, 0.2,
                       emission=(1.0,0.30,0.10), emission_strength=5.0))
# Hose
for hi in range(8):
    smooth_sphere(f"ch_hose{hi}", r=0.04, loc=(0.3 + hi*0.20, math.sin(hi*0.5)*0.2, 0.5 - hi*0.05),
                  parent=chicha_e, mat_=M_CARPET_RED)
# Smoke column rising
smoke_e = empty("ch_smoke_e", (0, 0, 1.5), parent=chicha_e)
for si in range(6):
    smooth_sphere(f"ch_smoke{si}", r=0.20 + si*0.05,
                  loc=(math.sin(si*0.8)*0.20, math.cos(si*0.8)*0.20, si*0.55),
                  parent=smoke_e, mat_=M_CHICHA_SMOKE)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Merchants gesture + body sway
for p in people:
    phase = p["root"]["_phase"]
    base_z = p["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        p["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        p["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(4),
                                     math.cos(t * 1.0 + phase) * math.radians(3),
                                     p["root"].rotation_euler.z)
        p["root"].keyframe_insert("location", frame=f)
        p["root"].keyframe_insert("rotation_euler", frame=f)
        # Head turn
        p["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(6), 0,
                                    math.sin(t * 1.2 + phase) * math.radians(20))
        p["he"].keyframe_insert("rotation_euler", frame=f)
        # Arms gesture
        for ai, arm in enumerate(p["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 2.5 + phase + ai * math.pi) * math.radians(15)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)

# Donkeys bob
for d in donkeys:
    phase = d["root"]["_phase"]
    base_z = d["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        d["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.04
        d["root"].keyframe_insert("location", frame=f)
        d["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(8), 0,
                                    math.sin(t * 0.5 + phase) * math.radians(15))
        d["he"].keyframe_insert("rotation_euler", frame=f)

# Cats walking + head turn
for c in cats:
    phase = c["root"]["_phase"]
    base_x = c["root"].location.x
    base_y = c["root"].location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        c["root"].location = (base_x + math.sin(t * 0.5 + phase) * 1.5,
                               base_y + math.cos(t * 0.4 + phase) * 1.2,
                               0)
        c["root"].keyframe_insert("location", frame=f)
        c["he"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(30))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Lanterns pulse + sway
for l in lanterns:
    phase = l["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.0 + phase) * 0.10
        l.scale = (s, s, s)
        l.rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3),
                             math.cos(t * 0.7 + phase) * math.radians(2.5), 0)
        l.keyframe_insert("scale", frame=f)
        l.keyframe_insert("rotation_euler", frame=f)

# Stalls awning subtle
for s in stalls:
    phase = s["_phase"]
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        s.rotation_euler = (math.sin(t * 0.5 + phase) * math.radians(0.5),
                             math.cos(t * 0.4 + phase) * math.radians(0.5),
                             s.rotation_euler.z)
        s.keyframe_insert("rotation_euler", frame=f)

# Chicha smoke rises + spirals
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    smoke_e.rotation_euler = (0, 0, t * 1.2)
    smoke_e.scale = (1 + math.sin(t * 1.5) * 0.08,
                      1 + math.cos(t * 1.5) * 0.08,
                      1 + math.sin(t * 1.0) * 0.10)
    smoke_e.keyframe_insert("rotation_euler", frame=f)
    smoke_e.keyframe_insert("scale", frame=f)

# Moon halos
for obj in bpy.data.objects:
    if obj.name.startswith("moon_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.7) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 600 SPICE POWDER drift (signature souk)
# ============================================================
spice_powder = []
powder_colors = [M_POWDER_RED, M_POWDER_ORANGE, M_POWDER_YELLOW, M_POWDER_GREEN, M_POWDER_PURPLE]
for i in range(600):
    px = random.uniform(-25, 25)
    py = random.uniform(-25, 25)
    pz = random.uniform(0.8, 8)
    col = powder_colors[i % 5]
    p_obj = smooth_sphere(f"powder{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6,
                          loc=(px, py, pz), mat_=col)
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_amp_x"] = random.uniform(0.6, 1.6)
    p_obj["_amp_y"] = random.uniform(0.6, 1.6)
    p_obj["_amp_z"] = random.uniform(0.3, 0.8)
    p_obj["_speed"] = random.uniform(0.4, 1.0)
    spice_powder.append(p_obj)

for p in spice_powder:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    ax, ay, az = p["_amp_x"], p["_amp_y"], p["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Spiral drift around stalls
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase * 1.5)
        p.location = (x, y, max(0.3, z))
        sc = 1 + math.sin(t * 3.0 + phase) * 0.25
        p.scale = (sc, sc, sc)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_morocco_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_moroccan_medina_souk] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_moroccan_medina_souk] ONE cobble ground + 4 horseshoe arches + mosque dome+minaret + 12 spice stalls + 8 merchants + 3 women haïk + 4 donkeys + 3 cats + 50 lanterns + tea+chicha + 600 SPICE POWDER")
print("⭐ FIXES: 1 ground + 600 spice powder spiral drift + pulse (signature Morocco souk mandatory) ⭐")
