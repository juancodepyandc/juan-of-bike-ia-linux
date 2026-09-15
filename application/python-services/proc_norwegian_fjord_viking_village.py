"""
proc_norwegian_fjord_viking_village.py — 230e procédural AuroraIA (94e qualité)
Norwegian Viking village: ONE rocky ground + 3 fjord mountains + 4 drakkar boats + 6 turf-roof longhouses + stavkirke + 8 vikings + chief Mjolnir + 4 women + goats + pigs + Yggdrasil + aurora + 600 sea spray + 400 aurora particles
FIXES : 1 ground + 600 sea spray + 400 aurora particles signature Nordic fjord night
"""
import bpy, bmesh, math, random, os

random.seed(0x07F230)

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

# Norwegian night palette
M_SKY = mat("sky", (0.05, 0.08, 0.20, 1.0), 0.0, 0.7, emission=(0.05,0.08,0.20), emission_strength=1.0)
M_MOON = mat("moon", (0.92, 0.95, 1.0, 1.0), 0.0, 0.20, emission=(0.92,0.95,1.0), emission_strength=12.0)
M_STAR = mat("star", (1.0, 1.0, 0.95, 1.0), 0.0, 0.20, emission=(1.0,1.0,0.95), emission_strength=12.0)

# AURORA signature massive
M_AURORA_GREEN = mat("aur_g", (0.20, 0.95, 0.55, 1.0), 0.0, 0.20, emission=(0.20,0.95,0.55), emission_strength=10.0, alpha=0.65)
M_AURORA_PURPLE = mat("aur_p", (0.65, 0.30, 0.95, 1.0), 0.0, 0.20, emission=(0.65,0.30,0.95), emission_strength=10.0, alpha=0.65)
M_AURORA_PINK = mat("aur_pk", (0.95, 0.55, 0.85, 1.0), 0.0, 0.20, emission=(0.95,0.55,0.85), emission_strength=9.5, alpha=0.60)
M_AURORA_TEAL = mat("aur_t", (0.20, 0.85, 0.85, 1.0), 0.0, 0.20, emission=(0.20,0.85,0.85), emission_strength=9.0, alpha=0.65)

# Ground rocky coast
M_GROUND = mat("ground", (0.30, 0.32, 0.30, 1.0), 0.0, 0.85, emission=(0.28,0.30,0.28), emission_strength=0.3)
M_ROCK_NORD = mat("rock_n", (0.35, 0.35, 0.35, 1.0), 0.0, 0.85)
M_ROCK_DARK = mat("rock_d", (0.22, 0.22, 0.25, 1.0), 0.0, 0.85)
M_MOSS = mat("moss_n", (0.30, 0.55, 0.30, 1.0), 0.0, 0.70, emission=(0.28,0.50,0.28), emission_strength=0.5)
M_GRASS_NORD = mat("grass_n", (0.35, 0.55, 0.30, 1.0), 0.0, 0.75, emission=(0.32,0.50,0.28), emission_strength=0.5)
M_SNOW = mat("snow", (0.95, 0.95, 1.0, 1.0), 0.0, 0.45, emission=(0.90,0.92,0.98), emission_strength=1.0)

# Fjord water
M_WATER = mat("water", (0.10, 0.25, 0.40, 1.0), 0.5, 0.10, emission=(0.10,0.25,0.40), emission_strength=1.5)
M_WATER_FOAM = mat("foam", (0.95, 0.98, 1.0, 1.0), 0.0, 0.20, emission=(0.90,0.95,1.0), emission_strength=3.0)

# Mountains fjord (signature steep)
M_MOUNTAIN = mat("mountain", (0.32, 0.32, 0.40, 1.0), 0.0, 0.80, emission=(0.30,0.30,0.38), emission_strength=0.3)
M_MOUNTAIN_DARK = mat("mountain_d", (0.20, 0.22, 0.28, 1.0), 0.0, 0.85)

# Wood (drakkar + longhouse)
M_WOOD_DARK = mat("wood_d", (0.35, 0.22, 0.12, 1.0), 0.0, 0.80, emission=(0.32,0.20,0.10), emission_strength=0.3)
M_WOOD_MED = mat("wood_m", (0.50, 0.32, 0.18, 1.0), 0.0, 0.75, emission=(0.45,0.30,0.16), emission_strength=0.4)
M_WOOD_LIGHT = mat("wood_l", (0.65, 0.42, 0.22, 1.0), 0.0, 0.70, emission=(0.60,0.40,0.20), emission_strength=0.5)
M_WOOD_BLACK = mat("wood_bk", (0.18, 0.10, 0.06, 1.0), 0.0, 0.85)

# Drakkar (signature dragon head)
M_DRAGON_HEAD = mat("d_head", (0.65, 0.42, 0.20, 1.0), 0.0, 0.65, emission=(0.60,0.40,0.18), emission_strength=0.5)
M_DRAGON_GOLD = mat("d_gold", (0.95, 0.72, 0.25, 1.0), 0.95, 0.18, emission=(0.92,0.72,0.25), emission_strength=1.2)
M_DRAGON_EYE_RED = mat("d_eye", (1.0, 0.20, 0.15, 1.0), 0.0, 0.10, emission=(1.0,0.20,0.15), emission_strength=10.0)

# Shield colors (signature painted Viking shields)
M_SHIELD_RED = mat("sh_r", (0.78, 0.20, 0.18, 1.0), 0.0, 0.55, emission=(0.72,0.20,0.18), emission_strength=0.6)
M_SHIELD_BLUE = mat("sh_b", (0.20, 0.40, 0.65, 1.0), 0.0, 0.55, emission=(0.18,0.38,0.60), emission_strength=0.6)
M_SHIELD_YELLOW = mat("sh_y", (0.95, 0.78, 0.25, 1.0), 0.0, 0.55, emission=(0.90,0.72,0.22), emission_strength=0.7)
M_SHIELD_BLACK = mat("sh_bk", (0.15, 0.12, 0.10, 1.0), 0.0, 0.65)
M_SHIELD_PATTERN = mat("sh_p", (0.85, 0.85, 0.85, 1.0), 0.0, 0.55)

# Turf roof (signature Nordic)
M_TURF = mat("turf", (0.25, 0.42, 0.20, 1.0), 0.0, 0.80, emission=(0.22,0.38,0.18), emission_strength=0.4)
M_TURF_DARK = mat("turf_d", (0.18, 0.32, 0.15, 1.0), 0.0, 0.80)
M_WALL_LOG = mat("wall_l", (0.42, 0.25, 0.15, 1.0), 0.0, 0.80, emission=(0.38,0.22,0.13), emission_strength=0.3)

# Stavkirke (signature stave church)
M_STAVE_DARK = mat("stave_d", (0.18, 0.10, 0.06, 1.0), 0.0, 0.85)
M_STAVE_TAR = mat("stave_t", (0.10, 0.08, 0.06, 1.0), 0.3, 0.65, emission=(0.08,0.06,0.05), emission_strength=0.3)

# Viking skin + hair
M_SKIN_VIKING = mat("skin_v", (0.92, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.85,0.72,0.62), emission_strength=0.4)
M_HAIR_BLOND_V = mat("hair_v", (0.85, 0.62, 0.30, 1.0), 0.0, 0.65)
M_HAIR_DARK_V = mat("hair_dv", (0.42, 0.22, 0.10, 1.0), 0.0, 0.85)
M_HAIR_RED_V = mat("hair_rv", (0.78, 0.32, 0.15, 1.0), 0.0, 0.65)
M_BEARD_BLOND_V = mat("beard_bv", (0.78, 0.55, 0.25, 1.0), 0.0, 0.75)

# Viking clothing
M_TUNIC_VIKING_BROWN = mat("t_brown", (0.45, 0.30, 0.18, 1.0), 0.0, 0.70, emission=(0.42,0.28,0.16), emission_strength=0.4)
M_TUNIC_VIKING_GREEN = mat("t_green", (0.30, 0.45, 0.25, 1.0), 0.0, 0.70, emission=(0.28,0.42,0.22), emission_strength=0.5)
M_TUNIC_VIKING_RED = mat("t_red", (0.65, 0.20, 0.18, 1.0), 0.0, 0.65, emission=(0.60,0.20,0.18), emission_strength=0.6)
M_TUNIC_VIKING_BLUE = mat("t_blue", (0.20, 0.32, 0.55, 1.0), 0.0, 0.65, emission=(0.18,0.30,0.50), emission_strength=0.5)
M_DRESS_LIGHT = mat("dress_l", (0.65, 0.55, 0.45, 1.0), 0.0, 0.70, emission=(0.60,0.50,0.42), emission_strength=0.5)
M_FUR = mat("fur", (0.55, 0.42, 0.30, 1.0), 0.0, 0.90)
M_FUR_WHITE = mat("fur_w", (0.85, 0.82, 0.75, 1.0), 0.0, 0.90)
M_LEATHER_V = mat("leather_v", (0.32, 0.20, 0.12, 1.0), 0.0, 0.75)

# Helmet (signature horned)
M_HELMET = mat("helmet", (0.55, 0.55, 0.60, 1.0), 0.85, 0.30, emission=(0.50,0.50,0.55), emission_strength=0.5)
M_HORN = mat("horn_v", (0.85, 0.75, 0.55, 1.0), 0.2, 0.55)

# Weapons + axes
M_AXE_WOOD = mat("axe_w", (0.55, 0.32, 0.18, 1.0), 0.0, 0.75)
M_AXE_STEEL = mat("axe_s", (0.55, 0.55, 0.60, 1.0), 0.95, 0.20, emission=(0.50,0.50,0.55), emission_strength=0.5)
M_MJOLNIR = mat("mjolnir", (0.55, 0.55, 0.60, 1.0), 0.95, 0.18, emission=(0.55,0.55,0.60), emission_strength=1.0)
M_RUNE_GLOW = mat("rune_g_v", (0.30, 0.85, 1.0, 1.0), 0.0, 0.10, emission=(0.30,0.85,1.0), emission_strength=15.0)

# Animals
M_GOAT = mat("goat", (0.65, 0.55, 0.42, 1.0), 0.0, 0.75)
M_GOAT_DARK = mat("goat_d", (0.30, 0.22, 0.15, 1.0), 0.0, 0.85)
M_PIG = mat("pig", (0.92, 0.65, 0.62, 1.0), 0.0, 0.65, emission=(0.85,0.60,0.58), emission_strength=0.4)

# Fire campfire
M_FIRE_OUTER_N = mat("fire_o_n", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=14.0)
M_FIRE_CORE_N = mat("fire_c_n", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=18.0)
M_EMBER_N = mat("ember_n", (1.0, 0.30, 0.10, 1.0), 0.0, 0.20, emission=(1.0,0.30,0.10), emission_strength=12.0)

# Yggdrasil leaves
M_LEAF_GOLD = mat("leaf_g", (1.0, 0.85, 0.30, 1.0), 0.5, 0.30, emission=(0.95,0.78,0.28), emission_strength=2.0)
M_LEAF_GREEN = mat("leaf_gr", (0.25, 0.55, 0.30, 1.0), 0.0, 0.55, emission=(0.22,0.50,0.28), emission_strength=0.8)

# Harp
M_HARP_V = mat("harp_v", (0.55, 0.32, 0.18, 1.0), 0.0, 0.60, emission=(0.50,0.30,0.16), emission_strength=0.4)
M_STRING_V = mat("str_v", (0.85, 0.85, 0.92, 1.0), 0.8, 0.20, emission=(0.78,0.78,0.85), emission_strength=0.5)

# Particles
M_SEA_SPRAY = mat("spray", (0.85, 0.92, 0.98, 1.0), 0.0, 0.20, emission=(0.78,0.88,0.95), emission_strength=3.5, alpha=0.65)
M_AUR_PARTICLE_G = mat("aurp_g", (0.30, 1.0, 0.55, 1.0), 0.0, 0.10, emission=(0.30,1.0,0.55), emission_strength=15.0)
M_AUR_PARTICLE_P = mat("aurp_p", (0.85, 0.30, 1.0, 1.0), 0.0, 0.10, emission=(0.85,0.30,1.0), emission_strength=14.0)
M_AUR_PARTICLE_T = mat("aurp_t", (0.30, 0.92, 1.0, 1.0), 0.0, 0.10, emission=(0.30,0.92,1.0), emission_strength=15.0)

# ============ SKY + MOON + STARS + AURORA MASSIVE ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
moon_e = empty("moon_e", (-25, 40, 38))
smooth_sphere("moon", r=4.5, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)
for i in range(3):
    smooth_sphere(f"moon_halo{i}", r=4.5 + (i+1)*1.5, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)

# 300 stars
for i in range(300):
    a = random.uniform(0, math.pi*2)
    phi = random.uniform(math.pi/6, math.pi/2.2)
    r_star = 115
    sx = r_star * math.cos(phi) * math.cos(a)
    sy = r_star * math.cos(phi) * math.sin(a)
    sz = r_star * math.sin(phi) * 0.4
    smooth_sphere(f"star{i}", r=random.uniform(0.20, 0.50), segs=10, rings=8,
                  loc=(sx, sy, sz), mat_=M_STAR)

# MASSIVE AURORA (5 layered ribbons signature Norway)
auroras = []
aurora_mats = [M_AURORA_GREEN, M_AURORA_PURPLE, M_AURORA_PINK, M_AURORA_TEAL, M_AURORA_GREEN]
for i, col in enumerate(aurora_mats):
    a_e = empty(f"aurora_e{i}", (0, 30, 28 + i*4))
    for s in range(10):
        seg_x = (s - 4.5) * 6
        seg_z = math.sin(s * 0.6) * 3
        beveled_cube(f"aurora_{i}_{s}", (6, 0.3, 6 + i*0.5), bevel_offset=0.10,
                     loc=(seg_x, 0, seg_z), parent=a_e, mat_=col)
    a_e["_phase"] = i * 0.4
    a_e.rotation_euler = (math.radians(10*i), 0, 0)
    auroras.append(a_e)

# ============ FJORD MOUNTAINS (3 massive steep cliffs signature) ============
fjord_e = empty("fjord", loc=(0, 30, 0))
# Central massive cliff
beveled_cube("fj_main", (12, 8, 16), bevel_offset=0.10, loc=(0, 0, 8),
             parent=fjord_e, mat_=M_MOUNTAIN)
# Snow cap
beveled_cube("fj_main_snow", (10, 6, 1.5), bevel_offset=0.10, loc=(0, 0, 16.75),
             parent=fjord_e, mat_=M_SNOW)
# Side cliffs (very steep)
for side, side_mul in zip(("L", "R"), (-1, 1)):
    cliff = beveled_cube(f"fj_{side}", (8, 7, 14), bevel_offset=0.10,
                        loc=(side_mul*15, -1, 7), parent=fjord_e, mat_=M_MOUNTAIN_DARK)
    cliff.rotation_euler = (0, math.radians(side_mul*-5), 0)
    # Snow cap
    beveled_cube(f"fj_snow_{side}", (6, 5, 1.2), bevel_offset=0.08,
                 loc=(side_mul*15, -1, 14.6), parent=fjord_e, mat_=M_SNOW)
    # Far cliff
    far = beveled_cube(f"fj_far_{side}", (10, 5, 12), bevel_offset=0.10,
                      loc=(side_mul*28, -2, 6), parent=fjord_e, mat_=M_MOUNTAIN)
    beveled_cube(f"fj_far_snow_{side}", (7, 4, 1), bevel_offset=0.08,
                 loc=(side_mul*28, -2, 12.5), parent=fjord_e, mat_=M_SNOW)
# Pine trees on slopes
for i in range(20):
    a = random.uniform(-math.pi*0.7, math.pi*0.7)
    rad = random.uniform(8, 25)
    px = rad * math.cos(a)
    py = 25 + random.uniform(-5, 5)
    pz = random.uniform(-2, 6)
    pine_e = empty(f"pine{i}", (px, py, pz))
    cyl(f"p_t{i}", r=0.15, depth=0.8, segs=10, loc=(0, 0, 0.4),
        parent=pine_e, mat_=M_WOOD_DARK)
    for layer in range(3):
        smooth_cone(f"p_l{i}_{layer}", r1=1.0 - layer*0.25, r2=0.1, depth=1.2, segs=14,
                    loc=(0, 0, 1.2 + layer*0.7), parent=pine_e,
                    mat_=M_AURORA_GREEN if i % 5 == 0 else M_LEAF_GREEN)

# ============ ONE clean rocky coast ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)
# Water in front (fjord)
beveled_cube("water_main", (60, 25, 0.15), bevel_offset=0.05, loc=(0, -20, -0.10), mat_=M_WATER)
# Rocky variations (organic 3D)
for i in range(50):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(10, 40)
    smooth_sphere(f"rock{i}", r=random.uniform(0.5, 1.2),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.35),
                  mat_=M_ROCK_NORD if i % 2 == 0 else M_ROCK_DARK,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.85)))
# Moss + grass
for i in range(40):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 35)
    smooth_sphere(f"moss{i}", r=random.uniform(0.30, 0.55),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_MOSS if i % 2 == 0 else M_GRASS_NORD,
                  scale=(1.5, 1.3, 0.20))
# Coastal foam
for i in range(15):
    a = random.uniform(-math.pi*0.8, -math.pi*0.2)
    rad = random.uniform(10, 28)
    smooth_sphere(f"foam{i}", r=random.uniform(0.30, 0.55), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*math.sin(a) - 8, 0.05),
                  mat_=M_WATER_FOAM, scale=(1.6, 1.4, 0.15))

# ============ 4 DRAKKARS (Viking longships moored) ============
def make_drakkar(name, loc, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long curved hull (signature drakkar)
    hull = beveled_cube(f"{name}_hull", (6.0*scale, 1.5*scale, 0.6*scale), bevel_offset=0.10,
                       loc=(0, 0, 0.3*scale), parent=base, mat_=M_WOOD_DARK)
    # Hull side planks (signature lapstrake)
    for pl in range(5):
        for side in (-1, 1):
            plank = beveled_cube(f"{name}_pl{pl}_{side}", (5.8*scale, 0.04*scale, 0.18*scale), bevel_offset=0.02,
                                loc=(0, side*0.78*scale, 0.20 + pl*0.13), parent=base, mat_=M_WOOD_MED)
    # Curved bow rising up (signature)
    bow_e = empty(f"{name}_bow_e", (3.2*scale, 0, 0.5*scale), parent=base)
    bow_e.rotation_euler = (0, math.radians(20), 0)
    for bi in range(4):
        cyl(f"{name}_bow_seg{bi}", r=(0.30 - bi*0.04)*scale, depth=0.40*scale, segs=14,
            loc=(0, 0, bi*0.35*scale), parent=bow_e, mat_=M_WOOD_DARK)
    # DRAGON HEAD (signature)
    drag_e = empty(f"{name}_dragon_e", (0, 0, 1.4*scale), parent=bow_e)
    drag_e.rotation_euler = (math.radians(-30), 0, 0)
    smooth_sphere(f"{name}_drag_head", r=0.30*scale, segs=18, rings=12,
                  loc=(0, 0, 0.3*scale), parent=drag_e, mat_=M_DRAGON_HEAD, scale=(1.5, 1, 1.2))
    # Snout
    smooth_cone(f"{name}_drag_snout", r1=0.18*scale, r2=0.08*scale, depth=0.35*scale, segs=14,
                loc=(0, 0, 0.5*scale), parent=drag_e, mat_=M_DRAGON_HEAD).rotation_euler = (math.radians(-90), 0, 0)
    # Fangs
    for side in (-1, 1):
        smooth_cone(f"{name}_drag_fang{side}", r1=0.04*scale, r2=0.005*scale, depth=0.12*scale, segs=8,
                    loc=(0, side*0.08*scale, 0.45*scale), parent=drag_e,
                    mat_=M_WATER_FOAM).rotation_euler = (math.radians(80), 0, 0)
    # Glowing red eyes (signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_drag_eye{side}", r=0.07*scale,
                      loc=(side*0.18*scale, -0.15*scale, 0.40*scale),
                      parent=drag_e, mat_=M_DRAGON_EYE_RED)
    # Horns (signature)
    for side in (-1, 1):
        horn = smooth_cone(f"{name}_drag_horn{side}", r1=0.05*scale, r2=0.01*scale, depth=0.25*scale, segs=10,
                           loc=(side*0.12*scale, 0.18*scale, 0.50*scale),
                           parent=drag_e, mat_=M_DRAGON_GOLD)
        horn.rotation_euler = (math.radians(-30), 0, math.radians(side*15))
    # Mane spirals
    for sp in range(5):
        smooth_sphere(f"{name}_drag_mane{sp}", r=0.10*scale,
                      loc=(0, 0.15*scale + sp*0.10*scale, 0.30*scale - sp*0.15*scale),
                      parent=drag_e, mat_=M_DRAGON_GOLD)
    # Stern (curved up signature)
    stern_e = empty(f"{name}_stern_e", (-3.0*scale, 0, 0.5*scale), parent=base)
    stern_e.rotation_euler = (0, math.radians(-25), 0)
    for si in range(4):
        cyl(f"{name}_stern_seg{si}", r=(0.28 - si*0.04)*scale, depth=0.40*scale, segs=14,
            loc=(0, 0, si*0.35*scale), parent=stern_e, mat_=M_WOOD_DARK)
    # Curl top (spiraled tail signature)
    for sp in range(5):
        sp_angle = sp * 0.6
        smooth_sphere(f"{name}_stern_curl{sp}", r=0.10*scale,
                      loc=(math.cos(sp_angle)*0.15*scale, 0, 1.5*scale + sp*0.10*scale),
                      parent=stern_e, mat_=M_DRAGON_GOLD)
    # MAST + SAIL
    cyl(f"{name}_mast", r=0.10*scale, depth=4.0*scale, segs=12,
        loc=(0, 0, 2.0*scale), parent=base, mat_=M_WOOD_DARK)
    # Yardarm
    beveled_cube(f"{name}_yard", (3.0*scale, 0.10*scale, 0.10*scale), bevel_offset=0.02,
                 loc=(0, 0, 3.5*scale), parent=base, mat_=M_WOOD_DARK)
    # SAIL (signature striped red/white)
    for stripe in range(6):
        sx = (stripe - 2.5) * 0.5 * scale
        col = M_SHIELD_RED if stripe % 2 == 0 else M_DRESS_LIGHT
        beveled_cube(f"{name}_sail{stripe}", (0.5*scale, 0.05*scale, 2.5*scale), bevel_offset=0.02,
                     loc=(sx, 0, 2.25*scale), parent=base, mat_=col)
    # SHIELDS along sides (signature)
    shield_colors = [M_SHIELD_RED, M_SHIELD_BLUE, M_SHIELD_YELLOW, M_SHIELD_BLACK]
    for side in (-1, 1):
        for shi in range(6):
            sx_sh = (shi - 2.5) * 0.8
            col = shield_colors[(shi + (1 if side > 0 else 0)) % 4]
            sh_e = empty(f"{name}_sh_e_{side}_{shi}", (sx_sh*scale, side*0.85*scale, 0.65*scale), parent=base)
            sh_e.rotation_euler = (math.radians(side*-80), 0, 0)
            cyl(f"{name}_shield{side}_{shi}", r=0.30*scale, depth=0.06*scale, segs=18,
                loc=(0, 0, 0), parent=sh_e, mat_=col)
            # Center boss
            smooth_sphere(f"{name}_sh_boss{side}_{shi}", r=0.08*scale, loc=(0, 0, 0.04*scale),
                          parent=sh_e, mat_=M_AXE_STEEL)
            # 4 metal bands (signature)
            for bd in range(4):
                bd_a = (bd / 4.0) * math.pi
                beveled_cube(f"{name}_sh_band{side}_{shi}_{bd}", (0.04*scale, 0.04*scale, 0.55*scale), bevel_offset=0.01,
                             loc=(0, 0, 0.02*scale), parent=sh_e, mat_=M_AXE_STEEL).rotation_euler = (0, 0, bd_a)
    # Oars (signature)
    for side in (-1, 1):
        for oi in range(5):
            ox_o = (oi - 2) * 0.8
            cyl(f"{name}_oar{side}_{oi}", r=0.04*scale, depth=2.0*scale, segs=10,
                loc=(ox_o*scale, side*1.5*scale, 0.5*scale), parent=base, mat_=M_WOOD_MED).rotation_euler = (math.radians(70), 0, 0)
            # Paddle blade
            beveled_cube(f"{name}_oar_b{side}_{oi}", (0.20*scale, 0.04*scale, 0.40*scale), bevel_offset=0.02,
                         loc=(ox_o*scale, side*2.0*scale, -0.3*scale), parent=base, mat_=M_WOOD_MED)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

drakkars = []
drakkar_pos = [(-15, -12, 0, math.radians(-15)),
               (-5, -14, 0, math.radians(0)),
               (5, -14, 0, math.radians(0)),
               (15, -12, 0, math.radians(15))]
for i, (dx, dy, dz, fac) in enumerate(drakkar_pos):
    d = make_drakkar(f"drakkar{i}", (dx, dy, dz), facing=fac, scale=0.9)
    drakkars.append(d)

# ============ 6 LONGHOUSES (turf-roof signature Nordic) ============
def make_longhouse(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Wood log walls (signature)
    beveled_cube(f"{name}_walls", (6*scale, 3*scale, 2.5*scale), bevel_offset=0.06,
                 loc=(0, 0, 1.25*scale), parent=base, mat_=M_WALL_LOG)
    # Log details horizontal
    for log_i in range(8):
        log_z = 0.5*scale + log_i * 0.30*scale
        cyl(f"{name}_log_f{log_i}", r=0.10*scale, depth=6.2*scale, segs=10,
            loc=(0, -1.55*scale, log_z), parent=base, mat_=M_WOOD_DARK).rotation_euler = (0, math.radians(90), 0)
        cyl(f"{name}_log_b{log_i}", r=0.10*scale, depth=6.2*scale, segs=10,
            loc=(0, 1.55*scale, log_z), parent=base, mat_=M_WOOD_DARK).rotation_euler = (0, math.radians(90), 0)
    # Steep triangular gables (signature)
    for side, side_mul in zip(("F", "B"), (-1, 1)):
        # Triangle gable
        for tri_i in range(6):
            tri_w = 6*scale - tri_i * 0.5
            tri_h_pos = 2.5*scale + tri_i * 0.25
            beveled_cube(f"{name}_gable_{side}_{tri_i}", (tri_w, 0.20*scale, 0.20*scale), bevel_offset=0.02,
                         loc=(0, side_mul*1.5*scale, tri_h_pos), parent=base, mat_=M_WOOD_DARK)
    # TURF ROOF (signature green/grass on roof)
    for side, side_mul in zip(("L", "R"), (-1, 1)):
        roof = beveled_cube(f"{name}_roof_{side}", (6.5*scale, 3.5*scale, 0.40*scale), bevel_offset=0.04,
                           loc=(0, side_mul*0.85*scale, 4.0*scale), parent=base, mat_=M_TURF)
        roof.rotation_euler = (math.radians(side_mul*-45), 0, 0)
        # Grass detail
        for gi in range(15):
            gx_g = (gi - 7) * 0.4 * scale
            gy_g = random.uniform(-1.5, 1.5) * scale
            smooth_sphere(f"{name}_grass_{side}_{gi}", r=random.uniform(0.08, 0.14)*scale,
                          loc=(gx_g, gy_g, 0.20*scale), parent=roof, mat_=M_GRASS_NORD if gi % 2 == 0 else M_TURF_DARK,
                          scale=(1, 1.5, 0.3))
    # Door (signature wide)
    beveled_cube(f"{name}_door", (1.0*scale, 0.20*scale, 1.8*scale), bevel_offset=0.04,
                 loc=(0, -1.65*scale, 1.0*scale), parent=base, mat_=M_WOOD_DARK)
    # Rune carvings on door (signature)
    for ri in range(3):
        smooth_sphere(f"{name}_rune{ri}", r=0.08*scale,
                      loc=(0, -1.78*scale, 0.6*scale + ri*0.30*scale),
                      parent=base, mat_=M_RUNE_GLOW, scale=(0.6, 0.3, 1))
    # Smoke hole
    cyl(f"{name}_smokehole", r=0.30*scale, depth=0.15*scale, segs=14,
        loc=(0, 0, 5.5*scale), parent=base, mat_=M_WOOD_BLACK)
    # Smoke wisps
    for si in range(3):
        smooth_sphere(f"{name}_smoke{si}", r=0.25*scale + si*0.08*scale,
                      loc=(math.sin(si)*0.20, 0, 5.8*scale + si*0.30),
                      parent=base,
                      mat_=mat(f"{name}_smoke_m{si}", (0.65, 0.65, 0.70, 1.0), 0, 0.65,
                               emission=(0.60,0.60,0.65), emission_strength=0.5, alpha=0.55))
    return base

houses = []
house_pos = [(-22, 4, 0, math.radians(0)),
             (-15, 8, 0, math.radians(20)),
             (-6, 6, 0, math.radians(-15)),
             (6, 6, 0, math.radians(15)),
             (15, 8, 0, math.radians(-20)),
             (22, 4, 0, math.radians(0))]
for i, (hx, hy, hz, fac) in enumerate(house_pos):
    h = make_longhouse(f"house{i}", (hx, hy, hz), scale=1.0, facing=fac)
    houses.append(h)

# ============ STAVKIRKE (signature stave church) ============
stav_e = empty("stavkirke", loc=(0, 14, 0))
# Base square
beveled_cube("st_base", (4, 4, 4), bevel_offset=0.06, loc=(0, 0, 2),
             parent=stav_e, mat_=M_STAVE_TAR)
# Tiered tower (signature multiple roofs)
for tier in range(3):
    tier_w = 3.5 - tier * 0.6
    tier_h = 2.5 - tier * 0.4
    tier_z = 4 + tier * 2.5
    beveled_cube(f"st_tier{tier}", (tier_w, tier_w, tier_h), bevel_offset=0.05,
                 loc=(0, 0, tier_z), parent=stav_e, mat_=M_STAVE_DARK)
    # Steep slanted roof above
    for side, side_mul in zip(("L", "R"), (-1, 1)):
        roof = beveled_cube(f"st_tier_roof{tier}_{side}", (tier_w + 0.3, tier_w * 0.6, 0.20), bevel_offset=0.03,
                           loc=(0, side_mul*tier_w*0.3, tier_z + tier_h/2 + 0.1),
                           parent=stav_e, mat_=M_STAVE_TAR)
        roof.rotation_euler = (math.radians(side_mul*-40), 0, 0)
    # Dragon head finials at corners (signature)
    if tier == 0:
        for x in (-1, 1):
            for y in (-1, 1):
                drag_e = empty(f"st_drag_{tier}_{x}{y}", (x*1.8, y*1.8, tier_z + tier_h/2), parent=stav_e)
                drag_e.rotation_euler = (math.radians(40), 0, math.radians(x*45))
                smooth_cone(f"st_dr_{tier}_{x}{y}", r1=0.20, r2=0.02, depth=0.80, segs=12,
                            loc=(0, 0, 0.4), parent=drag_e, mat_=M_STAVE_DARK)
                smooth_sphere(f"st_dr_h{tier}_{x}{y}", r=0.15, loc=(0, 0, 0.85),
                              parent=drag_e, mat_=M_STAVE_DARK, scale=(1.3, 1, 1))
# Top spire
smooth_cone("st_spire", r1=0.30, r2=0.02, depth=2.5, segs=14, loc=(0, 0, 12),
            parent=stav_e, mat_=M_STAVE_TAR)
# Cross top
beveled_cube("st_cross_v", (0.08, 0.08, 0.7), loc=(0, 0, 13.5),
             parent=stav_e, mat_=M_DRAGON_GOLD)
beveled_cube("st_cross_h", (0.45, 0.08, 0.08), loc=(0, 0, 13.65),
             parent=stav_e, mat_=M_DRAGON_GOLD)
# Wall decorations - rune carvings
for ri in range(6):
    smooth_sphere(f"st_rune{ri}", r=0.10, loc=(0, -2.05, 1.5 + ri*0.4),
                  parent=stav_e, mat_=M_RUNE_GLOW, scale=(0.6, 0.3, 1))

# ============ CENTRAL CAMPFIRE ============
fire_e = empty("fire", loc=(0, -2, 0))
# Stone ring
for ri in range(10):
    ra = (ri / 10.0) * math.pi * 2
    smooth_sphere(f"f_stone{ri}", r=0.35,
                  loc=(1.5*math.cos(ra), 1.5*math.sin(ra), 0.25),
                  parent=fire_e, mat_=M_ROCK_NORD)
# Logs cross
for li in range(4):
    la = (li / 4.0) * math.pi
    log = cyl(f"f_log{li}", r=0.12, depth=2.0, segs=12,
              loc=(math.cos(la)*0.2, math.sin(la)*0.2, 0.45),
              parent=fire_e, mat_=M_WOOD_DARK)
    log.rotation_euler = (0, math.radians(90), la)
# Embers
for ei in range(10):
    ea = (ei / 10.0) * math.pi * 2
    smooth_sphere(f"f_ember{ei}", r=0.12,
                  loc=(0.4*math.cos(ea), 0.4*math.sin(ea), 0.50),
                  parent=fire_e, mat_=M_EMBER_N)
# Flames
flame_e = empty("flame", (0, 0, 0.7), parent=fire_e)
smooth_cone("flame_o", r1=0.70, r2=0.05, depth=2.2, segs=16,
            loc=(0, 0, 1.1), parent=flame_e, mat_=M_FIRE_OUTER_N)
smooth_cone("flame_c", r1=0.40, r2=0.02, depth=1.6, segs=14,
            loc=(0, 0, 0.8), parent=flame_e, mat_=M_FIRE_CORE_N)

# ============ 8 VIKINGS + chief + 4 women ============
def make_viking(name, loc, tunic_mat, beard_mat=M_BEARD_BLOND_V, hair_mat=M_HAIR_BLOND_V,
                is_chief=False, is_woman=False, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_hip{side_idx}", (side*0.15*scale, 0, 0.85*scale), parent=base)
        cyl(f"{name}_thigh{side_idx}", r=0.12*scale, depth=0.50*scale, segs=12,
            loc=(0, 0, -0.25*scale), parent=hip, mat_=M_LEATHER_V)
        cyl(f"{name}_calf{side_idx}", r=0.10*scale, depth=0.50*scale, segs=12,
            loc=(0, 0, -0.75*scale), parent=hip, mat_=M_LEATHER_V)
        # Fur boots
        beveled_cube(f"{name}_boot{side_idx}", (0.16*scale, 0.30*scale, 0.10*scale), bevel_offset=0.02,
                     loc=(0, 0.05*scale, -1.00*scale), parent=hip, mat_=M_FUR)
    # Tunic (longer for woman)
    tunic_depth = 1.6*scale if is_woman else 0.90*scale
    smooth_cone(f"{name}_tunic", r1=0.45*scale, r2=0.32*scale, depth=tunic_depth, segs=16,
                loc=(0, 0, 0.90*scale + tunic_depth/2 - 0.45*scale), parent=base, mat_=tunic_mat)
    # Belt
    cyl(f"{name}_belt", r=0.36*scale, depth=0.10*scale, segs=14,
        loc=(0, 0, 1.40*scale), parent=base, mat_=M_LEATHER_V)
    # Buckle
    beveled_cube(f"{name}_buckle", (0.12*scale, 0.05*scale, 0.10*scale), bevel_offset=0.02,
                 loc=(0, -0.36*scale, 1.40*scale), parent=base, mat_=M_DRAGON_GOLD)
    # Fur cloak over shoulders (signature)
    if is_chief or random.random() > 0.4:
        cloak_mat = M_FUR_WHITE if is_chief else M_FUR
        for ci in range(5):
            ca = (ci / 5.0) * math.pi * 2
            smooth_sphere(f"{name}_cloak{ci}", r=0.20*scale,
                          loc=(0.30*scale*math.cos(ca), 0.20*scale*math.sin(ca), 1.80*scale),
                          parent=base, mat_=cloak_mat, scale=(1, 1, 1.5))
    # Torso
    beveled_cube(f"{name}_torso", (0.40*scale, 0.22*scale, 0.55*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.75*scale), parent=base, mat_=tunic_mat)
    # Neck
    cyl(f"{name}_neck", r=0.09*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 2.10*scale), parent=base, mat_=M_SKIN_VIKING)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.28*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.20*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_VIKING)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.07*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.20, 0.50, 0.85, 1), 0, 0.4,
                                emission=(0.18,0.45,0.78), emission_strength=0.5))
    if is_woman:
        # Long blonde hair (signature viking woman)
        smooth_sphere(f"{name}_hair", r=0.25*scale, loc=(0, 0.05*scale, -0.10*scale),
                      parent=head_e, mat_=hair_mat, scale=(1.1, 1.05, 1.5))
        # 2 braids signature
        for side in (-1, 1):
            for bi in range(5):
                cyl(f"{name}_braid{side}_{bi}", r=0.03*scale, depth=0.14*scale, segs=8,
                    loc=(side*0.20*scale, 0.10*scale, -0.12*scale - bi*0.13*scale),
                    parent=head_e, mat_=hair_mat)
            # Braid ties
            cyl(f"{name}_tie{side}", r=0.04*scale, depth=0.03*scale, segs=10,
                loc=(side*0.20*scale, 0.10*scale, -0.78*scale), parent=head_e, mat_=M_DRAGON_GOLD)
        # Head circlet
        cyl(f"{name}_circlet", r=0.22*scale, depth=0.04*scale, segs=18,
            loc=(0, 0, 0.18*scale), parent=head_e, mat_=M_DRAGON_GOLD)
    else:
        # Wild blonde hair
        smooth_sphere(f"{name}_hair", r=0.23*scale, loc=(0, 0.04*scale, 0.04*scale),
                      parent=head_e, mat_=hair_mat, scale=(1.05, 1.0, 0.85))
        # MASSIVE BEARD (signature viking)
        smooth_sphere(f"{name}_beard", r=0.20*scale, loc=(0, -0.15*scale, -0.20*scale),
                      parent=head_e, mat_=beard_mat, scale=(1.1, 1.0, 1.4))
        # Beard braids
        for bi in range(3):
            cyl(f"{name}_b_braid{bi}", r=0.04*scale, depth=0.20*scale, segs=8,
                loc=((bi-1)*0.08*scale, -0.18*scale, -0.55*scale),
                parent=head_e, mat_=beard_mat)
        # Mustache
        smooth_sphere(f"{name}_must", r=0.12*scale, loc=(0, -0.18*scale, -0.05*scale),
                      parent=head_e, mat_=beard_mat, scale=(1.5, 0.7, 0.5))
        # HELMET (signature horned)
        helm_e = empty(f"{name}_helm_e", (0, 0, 0.12*scale), parent=head_e)
        # Bowl
        smooth_sphere(f"{name}_helm_b", r=0.22*scale, loc=(0, 0, 0),
                      parent=helm_e, mat_=M_HELMET, scale=(1, 1, 0.7))
        # Nose guard
        beveled_cube(f"{name}_helm_n", (0.05*scale, 0.04*scale, 0.15*scale), bevel_offset=0.01,
                     loc=(0, -0.20*scale, -0.05*scale), parent=helm_e, mat_=M_HELMET)
        # 2 HORNS (signature)
        for side in (-1, 1):
            horn_e = empty(f"{name}_horn_e{side}", (side*0.18*scale, 0, 0.10*scale), parent=helm_e)
            horn_e.rotation_euler = (math.radians(-20), 0, math.radians(side*45))
            for ho in range(4):
                ho_x = math.sin(ho * 0.3) * 0.04 * scale
                cyl(f"{name}_horn{side}_{ho}", r=(0.06 - ho*0.008)*scale, depth=0.20*scale, segs=10,
                    loc=(ho_x, 0, ho*0.16*scale), parent=horn_e, mat_=M_HORN)
        # Chief crown decoration on helmet
        if is_chief:
            # Gold band
            cyl(f"{name}_crown_b", r=0.22*scale, depth=0.05*scale, segs=18,
                loc=(0, 0, -0.05*scale), parent=helm_e, mat_=M_DRAGON_GOLD)
            # Jewel center
            smooth_sphere(f"{name}_crown_j", r=0.04*scale, loc=(0, -0.22*scale, 0),
                          parent=helm_e, mat_=M_DRAGON_EYE_RED)
    # Arms holding weapon or raised mug
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.32*scale, 0, 2.00*scale), parent=base)
        if is_chief:
            # Holding Mjolnir
            if side_idx == 0:
                sh.rotation_euler = (math.radians(-120), 0, math.radians(-30))
            else:
                sh.rotation_euler = (math.radians(-20), 0, math.radians(15))
        elif is_woman:
            # Holding harp or hands clasped
            sh.rotation_euler = (math.radians(-50), 0, math.radians(side*-30))
        else:
            # Holding mug raised cheer
            if side_idx == 0:
                sh.rotation_euler = (math.radians(-100), 0, math.radians(-30))
            else:
                sh.rotation_euler = (math.radians(-20), 0, math.radians(15))
        cyl(f"{name}_uarm{side_idx}", r=0.09*scale, depth=0.40*scale, segs=12,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=tunic_mat)
        cyl(f"{name}_fa{side_idx}", r=0.08*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_VIKING)
        # Forearm leather wrap
        cyl(f"{name}_wrap{side_idx}", r=0.085*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_LEATHER_V)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08*scale, loc=(0, 0, -0.78*scale),
                      parent=sh, mat_=M_SKIN_VIKING)
        arms_e.append(sh)
    # Mjolnir hammer for chief
    if is_chief:
        mjol_e = empty(f"{name}_mjol_e", (-0.5*scale, -0.3*scale, 2.7*scale), parent=base)
        # Hammer head (signature blocky square)
        beveled_cube(f"{name}_mjol_h", (0.30*scale, 0.45*scale, 0.30*scale), bevel_offset=0.04,
                     loc=(0, 0, 0), parent=mjol_e, mat_=M_MJOLNIR)
        # Glowing rune on head (signature)
        smooth_sphere(f"{name}_mjol_r", r=0.10*scale, loc=(0, -0.24*scale, 0),
                      parent=mjol_e, mat_=M_RUNE_GLOW, scale=(0.7, 0.3, 0.7))
        # Handle (short)
        cyl(f"{name}_mjol_handle", r=0.04*scale, depth=0.50*scale, segs=10,
            loc=(0, 0, -0.40*scale), parent=mjol_e, mat_=M_WOOD_DARK)
        # Handle wrap
        cyl(f"{name}_mjol_wrap", r=0.05*scale, depth=0.20*scale, segs=10,
            loc=(0, 0, -0.40*scale), parent=mjol_e, mat_=M_LEATHER_V)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

vikings = []
viking_specs = [
    ("v1", (-9, -2, 0), M_TUNIC_VIKING_BROWN, M_BEARD_BLOND_V, M_HAIR_BLOND_V, math.radians(45)),
    ("v2", (-7, -4, 0), M_TUNIC_VIKING_GREEN, M_BEARD_BLOND_V, M_HAIR_RED_V, math.radians(60)),
    ("v3", (-5, -2, 0), M_TUNIC_VIKING_RED, M_HAIR_DARK_V, M_HAIR_DARK_V, math.radians(30)),
    ("v4", (5, -2, 0), M_TUNIC_VIKING_BLUE, M_BEARD_BLOND_V, M_HAIR_BLOND_V, math.radians(-30)),
    ("v5", (7, -4, 0), M_TUNIC_VIKING_BROWN, M_HAIR_DARK_V, M_HAIR_DARK_V, math.radians(-60)),
    ("v6", (9, -2, 0), M_TUNIC_VIKING_GREEN, M_BEARD_BLOND_V, M_HAIR_RED_V, math.radians(-45)),
    ("v7", (-2, -6, 0), M_TUNIC_VIKING_RED, M_BEARD_BLOND_V, M_HAIR_BLOND_V, math.radians(0)),
    ("v8", (2, -6, 0), M_TUNIC_VIKING_BLUE, M_HAIR_DARK_V, M_HAIR_DARK_V, math.radians(0)),
]
for spec in viking_specs:
    name, loc, tunic, beard, hair, fac = spec
    v = make_viking(name, loc, tunic, beard, hair, facing=fac)
    vikings.append(v)

# Chief with Mjolnir
chief = make_viking("chief_v", (0, -3, 0), M_TUNIC_VIKING_RED, M_BEARD_BLOND_V, M_HAIR_BLOND_V,
                     is_chief=True, facing=math.radians(0), scale=1.15)
vikings.append(chief)

# 4 viking women
women_v_specs = [
    ("wv1", (-3, 1, 0), M_DRESS_LIGHT, M_HAIR_BLOND_V, math.radians(0)),
    ("wv2", (3, 1, 0), M_TUNIC_VIKING_BLUE, M_HAIR_RED_V, math.radians(0)),
    ("wv3", (-12, 0, 0), M_DRESS_LIGHT, M_HAIR_BLOND_V, math.radians(90)),
    ("wv4", (12, 0, 0), M_TUNIC_VIKING_GREEN, M_HAIR_BLOND_V, math.radians(-90)),
]
for spec in women_v_specs:
    name, loc, dress, hair, fac = spec
    w = make_viking(name, loc, dress, M_HAIR_BLOND_V, hair, is_woman=True, facing=fac)
    vikings.append(w)

# ============ GOATS + PIGS ============
def make_goat(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.30, segs=18, rings=12, loc=(0, 0, 0.55),
                  parent=base, mat_=M_GOAT, scale=(1.6, 1, 1))
    # Head
    head_e = empty(f"{name}_he", (0.45, 0, 0.75), parent=base)
    smooth_sphere(f"{name}_head", r=0.16, segs=16, rings=10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_GOAT)
    smooth_cone(f"{name}_snout", r1=0.09, r2=0.06, depth=0.15, segs=10,
                loc=(0.16, 0, -0.04), parent=head_e,
                mat_=M_GOAT).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025,
                      loc=(0.06, side*0.08, 0.04), parent=head_e, mat_=M_WOOD_BLACK)
    # Horns curved back signature
    for side in (-1, 1):
        for ho in range(3):
            cyl(f"{name}_horn{side}_{ho}", r=0.025 - ho*0.005, depth=0.10, segs=8,
                loc=(-0.05 - ho*0.04, side*0.05, 0.18 - ho*0.04),
                parent=head_e, mat_=M_HORN)
    # Beard
    smooth_sphere(f"{name}_beard", r=0.06, loc=(0, -0.10, -0.18),
                  parent=head_e, mat_=M_GOAT_DARK, scale=(1, 0.7, 1.5))
    # 4 legs
    for x_idx, x in enumerate((0.30, -0.30)):
        for y_idx, y in enumerate((-0.18, 0.18)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.04, depth=0.50, segs=10,
                loc=(x, y, 0.27), parent=base, mat_=M_GOAT)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.05, depth=0.06, segs=8,
                loc=(x, y, 0.05), parent=base, mat_=M_GOAT_DARK)
    # Tail
    smooth_sphere(f"{name}_tail", r=0.06, loc=(-0.55, 0, 0.62),
                  parent=base, mat_=M_GOAT)
    return {"root": base, "he": head_e}

goats = [
    make_goat("goat1", (-18, 0, 0), math.radians(45)),
    make_goat("goat2", (18, 0, 0), math.radians(-45)),
    make_goat("goat3", (-3, 10, 0), math.radians(180)),
]

# Pigs
def make_pig(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.30, segs=18, rings=12, loc=(0, 0, 0.35),
                  parent=base, mat_=M_PIG, scale=(1.8, 1.2, 1))
    # Head
    head_e = empty(f"{name}_he", (0.50, 0, 0.40), parent=base)
    smooth_sphere(f"{name}_head", r=0.20, segs=16, rings=10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_PIG, scale=(1, 1, 0.9))
    # Snout
    smooth_cone(f"{name}_snout", r1=0.12, r2=0.10, depth=0.15, segs=10,
                loc=(0.18, 0, -0.05), parent=head_e,
                mat_=M_PIG).rotation_euler = (0, math.radians(90), 0)
    # Snout disc
    cyl(f"{name}_snout_disc", r=0.10, depth=0.03, segs=12,
        loc=(0.28, 0, -0.05), parent=head_e, mat_=M_DRAGON_HEAD).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025,
                      loc=(0.05, side*0.10, 0.05), parent=head_e, mat_=M_WOOD_BLACK)
    # Ears
    for side in (-1, 1):
        smooth_cone(f"{name}_ear{side}", r1=0.06, r2=0.01, depth=0.12, segs=8,
                    loc=(-0.05, side*0.12, 0.15), parent=head_e, mat_=M_PIG).rotation_euler = (math.radians(-20), 0, math.radians(side*15))
    # 4 short legs
    for x_idx, x in enumerate((0.30, -0.30)):
        for y_idx, y in enumerate((-0.18, 0.18)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.05, depth=0.20, segs=10,
                loc=(x, y, 0.12), parent=base, mat_=M_PIG)
    # Curly tail
    for ti in range(4):
        ta = ti * 1.2
        smooth_sphere(f"{name}_tail{ti}", r=0.025,
                      loc=(-0.55 + math.cos(ta)*0.05, math.sin(ta)*0.05, 0.40 + ti*0.04),
                      parent=base, mat_=M_PIG)
    return {"root": base}

pigs = [
    make_pig("pig1", (-15, 12, 0), math.radians(60)),
    make_pig("pig2", (15, 12, 0), math.radians(-60)),
]

# ============ YGGDRASIL TREE small (signature mythic) ============
ygg_e = empty("yggdrasil", loc=(0, 18, 0))
# Twisted trunk
for s in range(6):
    seg = smooth_cone(f"ygg_t{s}", r1=0.45 - s*0.04, r2=0.40 - s*0.04, depth=1.0, segs=14,
                      loc=(math.sin(s*0.3)*0.08, math.cos(s*0.3)*0.08, (s+0.5)*1.0),
                      parent=ygg_e, mat_=M_WOOD_DARK)
# Massive golden canopy
for j in range(15):
    a = (j / 15.0) * math.pi * 2
    rad = random.uniform(2.0, 3.5)
    col = M_LEAF_GOLD if j % 2 == 0 else M_LEAF_GREEN
    smooth_sphere(f"ygg_can{j}", r=random.uniform(1.0, 1.4),
                  loc=(rad*math.cos(a), rad*math.sin(a), 7 + random.uniform(-0.5, 1.0)),
                  parent=ygg_e, mat_=col, scale=(1, 1, 0.85))

# ============================================================
# ⭐ 600 SEA SPRAY + 400 AURORA PARTICLES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 sea spray (signature)
sea_spray = []
for i in range(600):
    # Near coast water
    px = random.uniform(-30, 30)
    py = random.uniform(-30, -5)
    pz = random.uniform(0.2, 4)
    s_obj = smooth_sphere(f"spray{i}", r=random.uniform(0.06, 0.14), segs=8, rings=6,
                          loc=(px, py, pz), mat_=M_SEA_SPRAY)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(0.6, 1.4)
    s_obj["_amp_y"] = random.uniform(0.4, 1.0)
    s_obj["_amp_z"] = random.uniform(0.4, 1.0)
    s_obj["_speed"] = random.uniform(0.5, 1.2)
    sea_spray.append(s_obj)

# 400 aurora particles cascade (signature high above)
aurora_particles = []
aur_part_colors = [M_AUR_PARTICLE_G, M_AUR_PARTICLE_P, M_AUR_PARTICLE_T]
for i in range(400):
    px = random.uniform(-35, 35)
    py = random.uniform(15, 35)
    pz = random.uniform(15, 35)
    col = aur_part_colors[i % 3]
    p_obj = smooth_sphere(f"aurp{i}", r=random.uniform(0.08, 0.14), segs=8, rings=6,
                          loc=(px, py, pz), mat_=col)
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_amp_x"] = random.uniform(1.5, 3.5)
    p_obj["_amp_y"] = random.uniform(1.0, 2.5)
    p_obj["_amp_z"] = random.uniform(0.8, 2.0)
    p_obj["_speed"] = random.uniform(0.4, 1.0)
    aurora_particles.append(p_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Aurora ribbons wave
for a_obj in auroras:
    phase = a_obj["_phase"]
    base_x = a_obj.location.x
    base_z = a_obj.location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        a_obj.location.x = base_x + math.sin(t * 0.5 + phase) * 6
        a_obj.location.z = base_z + math.cos(t * 0.4 + phase) * 2
        a_obj.keyframe_insert("location", frame=f)

# Vikings cheer + sway
for v in vikings:
    phase = v["root"]["_phase"]
    base_z = v["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        v["root"].location.z = base_z + abs(math.sin(t * 2.0 + phase)) * 0.10
        v["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5),
                                     math.cos(t * 1.2 + phase) * math.radians(3),
                                     v["root"].rotation_euler.z)
        v["root"].keyframe_insert("location", frame=f)
        v["root"].keyframe_insert("rotation_euler", frame=f)
        for ai, arm in enumerate(v["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 2.5 + phase + ai * math.pi) * math.radians(15)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        v["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                    math.sin(t * 1.2 + phase) * math.radians(15))
        v["he"].keyframe_insert("rotation_euler", frame=f)

# Drakkars rocking on water
for d in drakkars:
    phase = d["_phase"]
    base_z = d.location.z
    base_rx = d.rotation_euler.x
    base_ry = d.rotation_euler.y
    base_rz = d.rotation_euler.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        d.location.z = base_z + math.sin(t * 1.5 + phase) * 0.10
        d.rotation_euler = (base_rx + math.sin(t * 1.2 + phase) * math.radians(3),
                             base_ry + math.cos(t * 1.0 + phase) * math.radians(2.5),
                             base_rz)
        d.keyframe_insert("location", frame=f)
        d.keyframe_insert("rotation_euler", frame=f)

# Campfire flames flicker
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 5.0) * 0.15
    flame_e.scale = (1 + math.sin(t * 4.0) * 0.12,
                      1 + math.cos(t * 4.5) * 0.12, s)
    flame_e.rotation_euler = (0, 0, math.sin(t * 3.0) * 0.20)
    flame_e.keyframe_insert("scale", frame=f)
    flame_e.keyframe_insert("rotation_euler", frame=f)

# Moon halos
for obj in bpy.data.objects:
    if obj.name.startswith("moon_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.7) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# Goats + pigs subtle bob
for g in goats:
    phase = hash(g["root"].name) % 100 * 0.05
    base_z = g["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        g["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.04
        g["root"].keyframe_insert("location", frame=f)
        g["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(8), 0,
                                    math.sin(t * 0.5 + phase) * math.radians(15))
        g["he"].keyframe_insert("rotation_euler", frame=f)

# ============================================================
# ⭐⭐⭐ 600 SEA SPRAY + 400 AURORA PARTICLES (signature Nordic night)
# ============================================================
for s in sea_spray:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase) * 0.3
        # Rise upward then fall (signature spray)
        z = bz + abs(math.sin(t * speed * 1.5 + phase)) * az * 2
        s.location = (x, y, max(0.1, z))
        sc = 1 + math.sin(t * 3.0 + phase) * 0.25
        s.scale = (sc, sc, sc)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

# 400 AURORA PARTICLES cascade
for ap in aurora_particles:
    phase = ap["_phase"]; speed = ap["_speed"]
    bx, by, bz = ap["_base_x"], ap["_base_y"], ap["_base_z"]
    ax, ay, az = ap["_amp_x"], ap["_amp_y"], ap["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.85 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase * 1.5)
        ap.location = (x, y, z)
        sc = 1 + math.sin(t * 3.5 + phase) * 0.4
        ap.scale = (sc, sc, sc)
        ap.keyframe_insert("location", frame=f)
        ap.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_norway_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_norwegian_fjord_viking_village] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_norwegian_fjord_viking_village] ONE rocky coast + 3 fjord cliffs + 4 drakkars dragon heads + 6 longhouses turf roofs + stavkirke + 13 vikings + chief Mjolnir + 3 goats + 2 pigs + Yggdrasil + aurora 5 ribbons + 600 SEA SPRAY + 400 AURORA PARTICLES")
print("⭐ FIXES: 1 ground + 600 sea spray + 400 aurora particles (signature Nordic fjord night mandatory) ⭐")
