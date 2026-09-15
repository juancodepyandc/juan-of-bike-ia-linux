"""
proc_mexican_dia_de_muertos.py — 240e procédural AuroraIA (105e qualité)
Día de los Muertos: cemetery night + 12 graves + 8 catrinas + 5 mariachi skeletons + ofrenda altar + 1000 marigolds + papel picado
FIXES : 1 ground + 600 cempasuchil + 400 monarch butterflies (signature thematic particles)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB240)

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

# Night palette
M_SKY = mat("sky", (0.04, 0.03, 0.10, 1.0), 0.0, 0.7, emission=(0.06,0.05,0.15), emission_strength=0.7)
M_GROUND = mat("ground", (0.32, 0.22, 0.15, 1.0), 0.0, 0.85, emission=(0.30,0.20,0.13), emission_strength=0.3)
M_GROUND_DARK = mat("g_d", (0.20, 0.14, 0.10, 1.0), 0.0, 0.85)

# Cemetery stone
M_STONE_GRAVE = mat("stone", (0.65, 0.60, 0.55, 1.0), 0.0, 0.75, emission=(0.58,0.55,0.50), emission_strength=0.5)
M_STONE_DARK = mat("stone_d", (0.45, 0.42, 0.38, 1.0), 0.0, 0.80)
M_STONE_MOSS = mat("stone_m", (0.42, 0.50, 0.30, 1.0), 0.0, 0.75)

# Marigold colors (cempasuchil signature)
M_MARIGOLD_ORANGE = mat("mar_o", (1.0, 0.55, 0.10, 1.0), 0.0, 0.45, emission=(1.0,0.55,0.10), emission_strength=2.5)
M_MARIGOLD_YELLOW = mat("mar_y", (1.0, 0.78, 0.18, 1.0), 0.0, 0.45, emission=(1.0,0.78,0.18), emission_strength=2.8)
M_MARIGOLD_DEEP = mat("mar_d", (0.95, 0.40, 0.08, 1.0), 0.0, 0.45, emission=(0.95,0.40,0.08), emission_strength=2.2)
M_MARIGOLD_CENTER = mat("mar_c", (0.85, 0.30, 0.05, 1.0), 0.0, 0.45, emission=(0.85,0.30,0.05), emission_strength=2.0)
M_LEAF_GREEN = mat("leaf", (0.20, 0.55, 0.20, 1.0), 0.0, 0.60, emission=(0.18,0.50,0.18), emission_strength=0.7)

# Skeleton signature
M_BONE_WHITE = mat("bone", (0.95, 0.92, 0.82, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.78), emission_strength=1.5)
M_BONE_PAINTED = mat("bone_p", (0.98, 0.95, 0.85, 1.0), 0.0, 0.45, emission=(0.92,0.90,0.82), emission_strength=1.8)

# Catrina dress colors signature
M_CATRINA_PURPLE = mat("cat_p", (0.55, 0.18, 0.65, 1.0), 0.0, 0.45, emission=(0.50,0.16,0.60), emission_strength=1.0)
M_CATRINA_PINK = mat("cat_pk", (0.95, 0.30, 0.55, 1.0), 0.0, 0.45, emission=(0.90,0.28,0.52), emission_strength=1.2)
M_CATRINA_TEAL = mat("cat_t", (0.10, 0.65, 0.55, 1.0), 0.0, 0.45, emission=(0.10,0.60,0.52), emission_strength=1.1)
M_CATRINA_RED = mat("cat_r", (0.85, 0.20, 0.20, 1.0), 0.0, 0.45, emission=(0.80,0.20,0.20), emission_strength=1.2)
M_CATRINA_BLUE = mat("cat_b", (0.20, 0.30, 0.75, 1.0), 0.0, 0.45, emission=(0.18,0.28,0.70), emission_strength=1.0)
M_CATRINA_GOLD = mat("cat_g", (0.95, 0.78, 0.30, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.28), emission_strength=1.3)
M_CATRINA_BLACK = mat("cat_bk", (0.08, 0.06, 0.06, 1.0), 0.3, 0.40)

# Skull paint (signature calavera designs)
M_SKULL_PINK_PAINT = mat("sk_p", (1.0, 0.55, 0.75, 1.0), 0.0, 0.30, emission=(1.0,0.55,0.75), emission_strength=2.5)
M_SKULL_BLUE_PAINT = mat("sk_b", (0.30, 0.75, 1.0, 1.0), 0.0, 0.30, emission=(0.30,0.75,1.0), emission_strength=2.8)
M_SKULL_GREEN_PAINT = mat("sk_g", (0.40, 0.95, 0.40, 1.0), 0.0, 0.30, emission=(0.40,0.95,0.40), emission_strength=2.5)
M_SKULL_PURPLE_PAINT = mat("sk_pu", (0.85, 0.30, 1.0, 1.0), 0.0, 0.30, emission=(0.85,0.30,1.0), emission_strength=2.8)
M_SKULL_RED_PAINT = mat("sk_r", (1.0, 0.20, 0.20, 1.0), 0.0, 0.30, emission=(1.0,0.20,0.20), emission_strength=3.0)
M_SKULL_YELLOW_PAINT = mat("sk_y", (1.0, 0.90, 0.20, 1.0), 0.0, 0.30, emission=(1.0,0.90,0.20), emission_strength=2.8)
M_EYE_BLACK = mat("eye_bk", (0.04, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_GLOW = mat("eye_gl", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.30), emission_strength=12.0)

# Wood
M_WOOD_BROWN = mat("wood", (0.40, 0.22, 0.10, 1.0), 0.0, 0.75, emission=(0.38,0.20,0.10), emission_strength=0.4)
M_WOOD_DARK_BR = mat("wood_d", (0.25, 0.14, 0.06, 1.0), 0.0, 0.80)
M_WOOD_PAINTED_BLUE = mat("wood_b", (0.20, 0.45, 0.85, 1.0), 0.0, 0.50, emission=(0.20,0.45,0.85), emission_strength=0.8)
M_WOOD_PAINTED_RED = mat("wood_r", (0.95, 0.25, 0.20, 1.0), 0.0, 0.50, emission=(0.90,0.25,0.20), emission_strength=0.8)

# Candle
M_CANDLE_WAX = mat("wax", (0.98, 0.92, 0.80, 1.0), 0.0, 0.40, emission=(0.95,0.90,0.78), emission_strength=0.9)
M_FLAME_OUTER = mat("fl_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=15.0)
M_FLAME_CORE = mat("fl_c", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=18.0)

# Photo frame
M_FRAME_GOLD = mat("fr_g", (0.95, 0.78, 0.30, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.28), emission_strength=1.3)
M_PHOTO = mat("photo", (0.55, 0.45, 0.38, 1.0), 0.0, 0.55, emission=(0.50,0.42,0.35), emission_strength=0.6)

# Papel picado (signature paper banners)
M_PAPEL_PINK = mat("pp_p", (1.0, 0.30, 0.55, 1.0), 0.0, 0.50, emission=(1.0,0.30,0.55), emission_strength=2.0, alpha=0.85)
M_PAPEL_PURPLE = mat("pp_pu", (0.65, 0.25, 0.85, 1.0), 0.0, 0.50, emission=(0.65,0.25,0.85), emission_strength=2.0, alpha=0.85)
M_PAPEL_ORANGE = mat("pp_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.50, emission=(1.0,0.55,0.15), emission_strength=2.0, alpha=0.85)
M_PAPEL_YELLOW = mat("pp_y", (1.0, 0.90, 0.20, 1.0), 0.0, 0.50, emission=(1.0,0.90,0.20), emission_strength=2.0, alpha=0.85)
M_PAPEL_GREEN = mat("pp_g", (0.30, 0.85, 0.40, 1.0), 0.0, 0.50, emission=(0.30,0.85,0.40), emission_strength=2.0, alpha=0.85)
M_PAPEL_BLUE = mat("pp_b", (0.30, 0.55, 1.0, 1.0), 0.0, 0.50, emission=(0.30,0.55,1.0), emission_strength=2.0, alpha=0.85)

# Pan de muerto
M_BREAD = mat("bread", (0.85, 0.65, 0.40, 1.0), 0.0, 0.65, emission=(0.78,0.60,0.38), emission_strength=0.5)
M_BREAD_SUGAR = mat("bread_s", (0.98, 0.95, 0.88, 1.0), 0.0, 0.55, emission=(0.92,0.90,0.85), emission_strength=0.8)

# Tequila bottle
M_TEQUILA = mat("teq", (0.85, 0.78, 0.45, 1.0), 0.0, 0.30, emission=(0.80,0.72,0.42), emission_strength=1.0, alpha=0.75)
M_BOTTLE_GLASS = mat("bot", (0.40, 0.55, 0.40, 1.0), 0.0, 0.20, emission=(0.30,0.45,0.30), emission_strength=0.6, alpha=0.55)

# Cross
M_CROSS_WOOD = mat("cross", (0.45, 0.25, 0.15, 1.0), 0.0, 0.75, emission=(0.42,0.23,0.14), emission_strength=0.5)
M_CROSS_FLOWER = mat("cross_f", (0.95, 0.40, 0.10, 1.0), 0.0, 0.45, emission=(0.92,0.40,0.10), emission_strength=2.0)

# Moon
M_MOON = mat("moon", (0.98, 0.95, 0.88, 1.0), 0.0, 0.20, emission=(0.95,0.92,0.85), emission_strength=4.5)
M_STAR = mat("star", (1.0, 0.95, 0.70, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.70), emission_strength=8.0)

# Butterfly signature
M_BUTTERFLY_ORANGE = mat("bf_o", (1.0, 0.45, 0.10, 1.0), 0.0, 0.30, emission=(1.0,0.45,0.10), emission_strength=2.5)
M_BUTTERFLY_BLACK = mat("bf_bk", (0.10, 0.06, 0.04, 1.0), 0.0, 0.40, emission=(0.08,0.05,0.03), emission_strength=0.6)
M_BUTTERFLY_WHITE = mat("bf_w", (0.98, 0.95, 0.90, 1.0), 0.0, 0.30, emission=(0.95,0.92,0.88), emission_strength=1.2)

# Mariachi outfit
M_MARIACHI_BLACK = mat("mar_bk", (0.10, 0.08, 0.08, 1.0), 0.2, 0.45, emission=(0.10,0.08,0.08), emission_strength=0.5)
M_MARIACHI_SILVER = mat("mar_s", (0.85, 0.85, 0.85, 1.0), 0.85, 0.30, emission=(0.80,0.80,0.80), emission_strength=1.2)
M_MARIACHI_RED = mat("mar_r", (0.85, 0.15, 0.15, 1.0), 0.0, 0.45, emission=(0.80,0.15,0.15), emission_strength=0.9)

# Tree/branch dead
M_BRANCH = mat("branch", (0.18, 0.10, 0.06, 1.0), 0.0, 0.85)

# Cempasuchil flower head
M_CEMPASUCHIL_F = mat("cf_o", (1.0, 0.45, 0.05, 1.0), 0.0, 0.40, emission=(1.0,0.45,0.05), emission_strength=2.8)
M_CEMPASUCHIL_Y = mat("cf_y", (1.0, 0.80, 0.18, 1.0), 0.0, 0.40, emission=(1.0,0.80,0.18), emission_strength=3.0)

MARIGOLD_VARIANTS = [M_MARIGOLD_ORANGE, M_MARIGOLD_YELLOW, M_MARIGOLD_DEEP, M_CEMPASUCHIL_F, M_CEMPASUCHIL_Y]
CATRINA_DRESS_VARIANTS = [M_CATRINA_PURPLE, M_CATRINA_PINK, M_CATRINA_TEAL, M_CATRINA_RED, M_CATRINA_BLUE]
SKULL_PAINTS = [M_SKULL_PINK_PAINT, M_SKULL_BLUE_PAINT, M_SKULL_GREEN_PAINT, M_SKULL_PURPLE_PAINT, M_SKULL_RED_PAINT, M_SKULL_YELLOW_PAINT]
PAPEL_COLORS = [M_PAPEL_PINK, M_PAPEL_PURPLE, M_PAPEL_ORANGE, M_PAPEL_YELLOW, M_PAPEL_GREEN, M_PAPEL_BLUE]

# ============ SKY ============
sky = smooth_sphere("sky", r=200, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)

# Moon
moon = smooth_sphere("moon", r=4, segs=24, rings=18, loc=(15, 30, 35), mat_=M_MOON)

# Stars
for si in range(80):
    sa = random.uniform(0, math.pi*2); sr = random.uniform(40, 120)
    sh = random.uniform(10, 50)
    smooth_sphere(f"star{si}", r=random.uniform(0.10, 0.25), segs=8, rings=6,
                  loc=(sr*math.cos(sa), sr*math.sin(sa), sh), mat_=M_STAR)

# ============ ONE clean ground (cemetery earth) ============
ground = beveled_cube("ground", (120, 120, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_GROUND)
# Organic earth variation
for i in range(120):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 50)
    smooth_sphere(f"earth{i}", r=random.uniform(0.4, 0.8), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_GROUND_DARK if i % 2 == 0 else M_GROUND,
                  scale=(1.5, 1.4, 0.20))

# ============ 12 GRAVES with crosses ============
grave_positions = []
for gi in range(12):
    angle = (gi / 12.0) * math.pi * 2
    radius = 14 + random.uniform(-2, 2)
    gx = radius * math.cos(angle)
    gy = radius * math.sin(angle)
    grave_positions.append((gx, gy, math.atan2(-gy, -gx)))

for i, (gx, gy, fac) in enumerate(grave_positions):
    g_e = empty(f"grave{i}", (gx, gy, 0))
    g_e.rotation_euler = (0, 0, fac)
    # Headstone
    beveled_cube(f"hs{i}", (1.4, 0.25, 1.2), bevel_offset=0.06, loc=(0, -0.5, 0.6),
                 parent=g_e, mat_=M_STONE_GRAVE if i % 2 == 0 else M_STONE_DARK)
    # Rounded top
    smooth_sphere(f"hs_top{i}", r=0.70, segs=18, rings=12, loc=(0, -0.5, 1.20),
                  parent=g_e, mat_=M_STONE_GRAVE if i % 2 == 0 else M_STONE_DARK,
                  scale=(1, 0.4, 0.5))
    # Grave mound
    beveled_cube(f"mound{i}", (1.5, 2.5, 0.35), bevel_offset=0.10, loc=(0, 0.8, 0.18),
                 parent=g_e, mat_=M_GROUND_DARK)
    # Cross on grave
    cross_e = empty(f"cross_e{i}", (0, -0.5, 1.30), parent=g_e)
    cyl(f"cross_v{i}", r=0.06, depth=0.8, segs=10, loc=(0, 0, 0),
        parent=cross_e, mat_=M_CROSS_WOOD)
    cyl(f"cross_h{i}", r=0.06, depth=0.5, segs=10, loc=(0, 0, 0.15),
        parent=cross_e, mat_=M_CROSS_WOOD).rotation_euler = (math.radians(90), 0, 0)
    # Marigold wreath on cross
    for fi in range(8):
        fa = (fi / 8.0) * math.pi * 2
        smooth_sphere(f"wr{i}_{fi}", r=0.10,
                      loc=(0.20*math.sin(fa), 0, 0.30 + 0.20*math.cos(fa)),
                      parent=cross_e, mat_=random.choice(MARIGOLD_VARIANTS))
    # Marigold petal trail on grave (signature path of marigolds)
    for pi in range(10):
        py = 0.5 + pi * 0.20
        smooth_sphere(f"pmar{i}_{pi}", r=0.10,
                      loc=(random.uniform(-0.5, 0.5), py, 0.36),
                      parent=g_e, mat_=random.choice(MARIGOLD_VARIANTS),
                      scale=(1, 1, 0.4))
    # Candle on grave
    cyl(f"gc{i}", r=0.08, depth=0.30, segs=12, loc=(0.5, 0.5, 0.45),
        parent=g_e, mat_=M_CANDLE_WAX)
    smooth_cone(f"gc_f{i}", r1=0.08, r2=0.02, depth=0.25, segs=12, loc=(0.5, 0.5, 0.75),
                parent=g_e, mat_=M_FLAME_OUTER)
    g_e["_phase"] = random.uniform(0, math.pi*2)

# ============ 8 CATRINAS (skeleton women elegant) ============
def make_catrina(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    dress_color = random.choice(CATRINA_DRESS_VARIANTS)
    skull_paint = random.choice(SKULL_PAINTS)

    # LONG DRESS (signature catrina elegant)
    # Lower long skirt (cone wide)
    smooth_cone(f"{name}_skirt", r1=0.95*scale, r2=0.40*scale, depth=2.2*scale, segs=18,
                loc=(0, 0, 1.1*scale), parent=base, mat_=dress_color)
    # Ruffles
    for rf in range(4):
        cyl(f"{name}_ruf{rf}", r=0.95*scale - rf*0.10, depth=0.06*scale, segs=20,
            loc=(0, 0, 0.30*scale + rf*0.30*scale), parent=base, mat_=dress_color)
    # Corset top
    smooth_cone(f"{name}_corset", r1=0.40*scale, r2=0.32*scale, depth=0.7*scale, segs=14,
                loc=(0, 0, 2.4*scale), parent=base, mat_=dress_color)
    # Belt with gold buckle
    cyl(f"{name}_belt", r=0.41*scale, depth=0.10*scale, segs=16, loc=(0, 0, 2.20*scale),
        parent=base, mat_=M_CATRINA_GOLD)

    # Bony arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.35*scale, 0, 2.65*scale), parent=base)
        sh.rotation_euler = (math.radians(-25), 0, math.radians(side*-30))
        cyl(f"{name}_uarm{side_idx}", r=0.05*scale, depth=0.50*scale, segs=10,
            loc=(0, 0, -0.25*scale), parent=sh, mat_=M_BONE_WHITE)
        # Elbow
        smooth_sphere(f"{name}_elb{side_idx}", r=0.07*scale, loc=(0, 0, -0.50*scale),
                      parent=sh, mat_=M_BONE_WHITE)
        # Forearm
        fa = empty(f"{name}_fa{side_idx}", (0, 0, -0.50*scale), parent=sh)
        fa.rotation_euler = (math.radians(-35), 0, 0)
        cyl(f"{name}_fa_b{side_idx}", r=0.04*scale, depth=0.42*scale, segs=10,
            loc=(0, 0, -0.21*scale), parent=fa, mat_=M_BONE_WHITE)
        # Hand bony
        smooth_sphere(f"{name}_hand{side_idx}", r=0.06*scale, loc=(0, 0, -0.42*scale),
                      parent=fa, mat_=M_BONE_WHITE)
        # Finger bones
        for fg in range(4):
            cyl(f"{name}_fg{side_idx}_{fg}", r=0.012*scale, depth=0.10*scale, segs=6,
                loc=((fg-1.5)*0.025*scale, 0, -0.50*scale), parent=fa, mat_=M_BONE_WHITE)

    # Neck (bone)
    cyl(f"{name}_neck", r=0.10*scale, depth=0.20*scale, segs=12, loc=(0, 0, 2.85*scale),
        parent=base, mat_=M_BONE_WHITE)

    # SKULL HEAD (signature catrina painted)
    head_e = empty(f"{name}_he", (0, 0, 3.10*scale), parent=base)
    # Skull main
    smooth_sphere(f"{name}_skull", r=0.30*scale, segs=22, rings=16, loc=(0, 0, 0),
                  parent=head_e, mat_=M_BONE_PAINTED, scale=(1, 1.05, 1.1))
    # Skull jaw
    smooth_sphere(f"{name}_jaw", r=0.22*scale, segs=18, rings=12, loc=(0, -0.05*scale, -0.20*scale),
                  parent=head_e, mat_=M_BONE_PAINTED, scale=(1, 0.8, 0.7))
    # Painted eye sockets (signature flowers)
    for side in (-1, 1):
        # Black socket
        smooth_sphere(f"{name}_es{side}", r=0.08*scale,
                      loc=(side*0.12*scale, -0.20*scale, 0.05*scale),
                      parent=head_e, mat_=M_EYE_BLACK)
        # Painted petal flower around eye (signature catrina)
        for pp in range(8):
            pa = (pp / 8.0) * math.pi * 2
            smooth_sphere(f"{name}_pe{side}_{pp}", r=0.04*scale,
                          loc=(side*0.12*scale + math.cos(pa)*0.15*scale,
                               -0.22*scale,
                               0.05*scale + math.sin(pa)*0.15*scale),
                          parent=head_e, mat_=skull_paint)
        # Glow inner
        smooth_sphere(f"{name}_egl{side}", r=0.04*scale,
                      loc=(side*0.12*scale, -0.25*scale, 0.05*scale),
                      parent=head_e, mat_=M_EYE_GLOW)
    # Nose triangle
    smooth_cone(f"{name}_nose", r1=0.05*scale, r2=0.02*scale, depth=0.10*scale, segs=10,
                loc=(0, -0.25*scale, -0.05*scale), parent=head_e,
                mat_=M_EYE_BLACK).rotation_euler = (math.radians(-90), 0, 0)
    # Teeth grin
    for ti in range(6):
        beveled_cube(f"{name}_t{ti}", (0.04*scale, 0.03*scale, 0.08*scale), bevel_offset=0.005,
                     loc=((ti-2.5)*0.05*scale, -0.18*scale, -0.18*scale),
                     parent=head_e, mat_=M_BONE_WHITE)
    # Painted decorative dots on forehead
    for di in range(7):
        da = (di / 7.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_dot{di}", r=0.025*scale,
                      loc=(math.sin(da)*0.20*scale, -0.25*scale, 0.20*scale),
                      parent=head_e, mat_=skull_paint)
    # HAT with flowers (signature catrina)
    hat_e = empty(f"{name}_ha", (0, 0, 0.35*scale), parent=head_e)
    # Hat brim wide
    cyl(f"{name}_brim", r=0.55*scale, depth=0.06*scale, segs=20, loc=(0, 0, 0),
        parent=hat_e, mat_=M_CATRINA_BLACK)
    # Hat crown
    smooth_cone(f"{name}_crown", r1=0.30*scale, r2=0.32*scale, depth=0.35*scale, segs=16,
                loc=(0, 0, 0.20*scale), parent=hat_e, mat_=M_CATRINA_BLACK)
    # Hat flowers (signature)
    for hf in range(12):
        ha = (hf / 12.0) * math.pi * 2
        hr = random.uniform(0.30, 0.50)
        hz = random.uniform(0.05, 0.18)
        smooth_sphere(f"{name}_hf{hf}", r=0.10*scale,
                      loc=(hr*math.cos(ha)*scale, hr*math.sin(ha)*scale, hz*scale),
                      parent=hat_e, mat_=random.choice(MARIGOLD_VARIANTS))
    # Feather plume
    smooth_cone(f"{name}_feather", r1=0.06*scale, r2=0.005*scale, depth=0.50*scale, segs=10,
                loc=(0, 0.20*scale, 0.45*scale), parent=hat_e,
                mat_=random.choice(PAPEL_COLORS)).rotation_euler = (math.radians(20), 0, 0)

    # Hair tendrils peeking
    for hi in range(4):
        ha2 = (hi / 4.0) * math.pi * 2
        smooth_sphere(f"{name}_hair{hi}", r=0.03*scale,
                      loc=(math.cos(ha2)*0.18*scale, math.sin(ha2)*0.10*scale, 0.25*scale),
                      parent=head_e, mat_=M_CATRINA_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "hat": hat_e}

catrinas = []
catrina_positions = [(-7, -3, math.radians(30)), (7, -3, math.radians(-30)),
                     (-9, 4, math.radians(120)), (9, 4, math.radians(-120)),
                     (-4, -8, math.radians(60)), (4, -8, math.radians(-60)),
                     (-5, 9, math.radians(150)), (5, 9, math.radians(-150))]
for i, (cx, cy, fac) in enumerate(catrina_positions):
    c = make_catrina(f"catrina{i}", (cx, cy, 0), scale=1.0, facing=fac)
    catrinas.append(c)

# ============ 5 MARIACHI SKELETONS ============
def make_mariachi(name, loc, instrument="guitar", scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.12*scale, depth=1.0*scale, segs=12,
            loc=(side*0.13*scale, 0, 0.5*scale), parent=base, mat_=M_MARIACHI_BLACK)
        # Silver buttons on side
        for bt in range(5):
            smooth_sphere(f"{name}_btn{side}_{bt}", r=0.03*scale,
                          loc=(side*0.25*scale, 0, 0.20*scale + bt*0.18*scale),
                          parent=base, mat_=M_MARIACHI_SILVER)
    # Belt
    cyl(f"{name}_belt", r=0.30*scale, depth=0.10*scale, segs=16, loc=(0, 0, 1.0*scale),
        parent=base, mat_=M_MARIACHI_SILVER)
    # Chest jacket
    smooth_cone(f"{name}_torso", r1=0.30*scale, r2=0.35*scale, depth=0.7*scale, segs=14,
                loc=(0, 0, 1.4*scale), parent=base, mat_=M_MARIACHI_BLACK)
    # Bow tie
    beveled_cube(f"{name}_bow", (0.15*scale, 0.03*scale, 0.08*scale), bevel_offset=0.01,
                 loc=(0, -0.30*scale, 1.75*scale), parent=base, mat_=M_MARIACHI_RED)
    # Decorative silver buttons + braid
    for bi in range(4):
        smooth_sphere(f"{name}_jbtn{bi}", r=0.035*scale,
                      loc=(0, -0.32*scale, 1.30*scale + bi*0.12*scale),
                      parent=base, mat_=M_MARIACHI_SILVER)
    # Silver embroidery line down sides
    for side in (-1, 1):
        beveled_cube(f"{name}_emb{side}", (0.04*scale, 0.04*scale, 0.6*scale), bevel_offset=0.01,
                     loc=(side*0.32*scale, -0.10*scale, 1.4*scale),
                     parent=base, mat_=M_MARIACHI_SILVER)
    # Bony arms
    arm_left_e = empty(f"{name}_aL", (-0.35*scale, 0, 1.70*scale), parent=base)
    arm_right_e = empty(f"{name}_aR", (0.35*scale, 0, 1.70*scale), parent=base)
    arm_left_e.rotation_euler = (math.radians(-30), 0, math.radians(20))
    arm_right_e.rotation_euler = (math.radians(-30), 0, math.radians(-20))
    for side_idx, (arm_e, side) in enumerate([(arm_left_e, -1), (arm_right_e, 1)]):
        cyl(f"{name}_uarm{side_idx}", r=0.05*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=arm_e, mat_=M_MARIACHI_BLACK)
        smooth_sphere(f"{name}_elb{side_idx}", r=0.06*scale, loc=(0, 0, -0.42*scale),
                      parent=arm_e, mat_=M_BONE_WHITE)
        fa = empty(f"{name}_fa{side_idx}", (0, 0, -0.42*scale), parent=arm_e)
        fa.rotation_euler = (math.radians(-60), 0, 0)
        cyl(f"{name}_fa_b{side_idx}", r=0.04*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.18*scale), parent=fa, mat_=M_BONE_WHITE)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.06*scale, loc=(0, 0, -0.38*scale),
                      parent=fa, mat_=M_BONE_WHITE)

    # Neck + skull
    cyl(f"{name}_neck", r=0.08*scale, depth=0.15*scale, segs=10, loc=(0, 0, 1.85*scale),
        parent=base, mat_=M_BONE_WHITE)
    head_e = empty(f"{name}_he", (0, 0, 2.05*scale), parent=base)
    smooth_sphere(f"{name}_skull", r=0.25*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_BONE_WHITE, scale=(1, 1.05, 1.1))
    smooth_sphere(f"{name}_jaw", r=0.18*scale, segs=18, rings=12, loc=(0, -0.05*scale, -0.18*scale),
                  parent=head_e, mat_=M_BONE_WHITE, scale=(1, 0.8, 0.7))
    # Eye sockets
    for side in (-1, 1):
        smooth_sphere(f"{name}_es{side}", r=0.07*scale,
                      loc=(side*0.10*scale, -0.18*scale, 0.03*scale),
                      parent=head_e, mat_=M_EYE_BLACK)
        smooth_sphere(f"{name}_egl{side}", r=0.03*scale,
                      loc=(side*0.10*scale, -0.22*scale, 0.03*scale),
                      parent=head_e, mat_=M_EYE_GLOW)
    # Teeth grin
    for ti in range(5):
        beveled_cube(f"{name}_t{ti}", (0.03*scale, 0.03*scale, 0.06*scale), bevel_offset=0.005,
                     loc=((ti-2)*0.04*scale, -0.15*scale, -0.18*scale),
                     parent=head_e, mat_=M_BONE_WHITE)
    # Moustache (signature mariachi)
    for side in (-1, 1):
        beveled_cube(f"{name}_mou{side}", (0.10*scale, 0.04*scale, 0.04*scale), bevel_offset=0.01,
                     loc=(side*0.05*scale, -0.20*scale, -0.10*scale),
                     parent=head_e, mat_=M_MARIACHI_BLACK)
    # SOMBRERO (signature wide brim)
    sombrero_e = empty(f"{name}_so", (0, 0, 0.20*scale), parent=head_e)
    cyl(f"{name}_brim", r=0.70*scale, depth=0.05*scale, segs=22, loc=(0, 0, 0),
        parent=sombrero_e, mat_=M_MARIACHI_BLACK)
    cyl(f"{name}_brim2", r=0.65*scale, depth=0.03*scale, segs=22, loc=(0, 0, 0.04*scale),
        parent=sombrero_e, mat_=M_MARIACHI_SILVER)
    smooth_cone(f"{name}_crown", r1=0.25*scale, r2=0.10*scale, depth=0.35*scale, segs=14,
                loc=(0, 0, 0.20*scale), parent=sombrero_e, mat_=M_MARIACHI_BLACK)
    # Silver trim
    cyl(f"{name}_trim", r=0.26*scale, depth=0.03*scale, segs=16, loc=(0, 0, 0.06*scale),
        parent=sombrero_e, mat_=M_MARIACHI_SILVER)

    # INSTRUMENT
    inst_e = empty(f"{name}_inst", (0.05*scale, -0.30*scale, 1.20*scale), parent=base)
    if instrument == "guitar":
        # Guitar body
        smooth_sphere(f"{name}_g_body", r=0.30*scale, segs=20, rings=14,
                      loc=(0, -0.10*scale, 0), parent=inst_e, mat_=M_WOOD_BROWN,
                      scale=(1.1, 0.4, 1.3))
        # Soundhole
        cyl(f"{name}_g_hole", r=0.06*scale, depth=0.02*scale, segs=14,
            loc=(0, -0.15*scale, 0.05*scale), parent=inst_e,
            mat_=M_EYE_BLACK).rotation_euler = (math.radians(90), 0, 0)
        # Neck
        cyl(f"{name}_g_neck", r=0.04*scale, depth=0.55*scale, segs=10,
            loc=(0, -0.05*scale, 0.45*scale), parent=inst_e, mat_=M_WOOD_DARK_BR)
        # Headstock
        beveled_cube(f"{name}_g_head", (0.12*scale, 0.08*scale, 0.10*scale), bevel_offset=0.01,
                     loc=(0, -0.05*scale, 0.78*scale), parent=inst_e, mat_=M_WOOD_DARK_BR)
        # Strings
        for st in range(6):
            cyl(f"{name}_st{st}", r=0.003*scale, depth=0.85*scale, segs=6,
                loc=((st - 2.5)*0.012*scale, -0.10*scale, 0.20*scale),
                parent=inst_e, mat_=M_MARIACHI_SILVER)
    elif instrument == "trumpet":
        # Trumpet body
        cyl(f"{name}_tr_b", r=0.04*scale, depth=0.50*scale, segs=12,
            loc=(0, -0.20*scale, 0.15*scale), parent=inst_e,
            mat_=M_MARIACHI_SILVER).rotation_euler = (math.radians(90), 0, 0)
        # Bell
        smooth_cone(f"{name}_tr_bell", r1=0.15*scale, r2=0.04*scale, depth=0.25*scale, segs=18,
                    loc=(0, -0.40*scale, 0.15*scale), parent=inst_e,
                    mat_=M_MARIACHI_GOLD if False else M_MARIACHI_SILVER).rotation_euler = (math.radians(90), 0, 0)
        # Valves
        for vi in range(3):
            cyl(f"{name}_vlv{vi}", r=0.025*scale, depth=0.12*scale, segs=10,
                loc=((vi-1)*0.06*scale, -0.10*scale, 0.30*scale),
                parent=inst_e, mat_=M_MARIACHI_SILVER)
    elif instrument == "violin":
        # Violin body
        smooth_sphere(f"{name}_v_body", r=0.18*scale, segs=20, rings=14,
                      loc=(0, -0.15*scale, 0.05*scale), parent=inst_e, mat_=M_WOOD_BROWN,
                      scale=(0.8, 0.30, 1.2))
        # Neck
        cyl(f"{name}_v_neck", r=0.025*scale, depth=0.30*scale, segs=10,
            loc=(0, -0.10*scale, 0.32*scale), parent=inst_e, mat_=M_WOOD_DARK_BR)
        # Bow
        cyl(f"{name}_v_bow", r=0.015*scale, depth=0.55*scale, segs=8,
            loc=(0.25*scale, -0.05*scale, 0.10*scale), parent=inst_e,
            mat_=M_WOOD_DARK_BR).rotation_euler = (0, math.radians(20), math.radians(80))
    elif instrument == "guitarron":
        # Big guitarron body
        smooth_sphere(f"{name}_gn_body", r=0.45*scale, segs=20, rings=14,
                      loc=(0, -0.15*scale, -0.10*scale), parent=inst_e, mat_=M_WOOD_BROWN,
                      scale=(1.0, 0.55, 1.0))
        # Neck thicker
        cyl(f"{name}_gn_neck", r=0.06*scale, depth=0.50*scale, segs=10,
            loc=(0, -0.05*scale, 0.40*scale), parent=inst_e, mat_=M_WOOD_DARK_BR)
    elif instrument == "vihuela":
        # Smaller higher pitched
        smooth_sphere(f"{name}_vh_body", r=0.22*scale, segs=20, rings=14,
                      loc=(0, -0.10*scale, 0), parent=inst_e, mat_=M_WOOD_BROWN,
                      scale=(0.9, 0.35, 1.0))
        cyl(f"{name}_vh_neck", r=0.03*scale, depth=0.40*scale, segs=10,
            loc=(0, -0.05*scale, 0.30*scale), parent=inst_e, mat_=M_WOOD_DARK_BR)

    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "inst": inst_e, "he": head_e, "L": arm_left_e, "R": arm_right_e}

mariachi_band = []
mariachi_instruments = ["guitar", "trumpet", "violin", "guitarron", "vihuela"]
mariachi_positions = [(-2.5, 6, math.radians(180)), (-1, 6, math.radians(180)),
                       (0.5, 6, math.radians(180)), (2, 6, math.radians(180)),
                       (3.5, 6, math.radians(180))]
for i, (mx, my, fac) in enumerate(mariachi_positions):
    m = make_mariachi(f"mariachi{i}", (mx, my, 0), instrument=mariachi_instruments[i],
                      scale=1.1, facing=fac)
    mariachi_band.append(m)

# ============ OFRENDA ALTAR (multi-level signature) ============
altar_e = empty("altar", loc=(0, -10, 0))

# 3 tier levels
for level in range(3):
    lz = level * 0.7
    lw = 5 - level * 1.0
    ld = 2 - level * 0.3
    # Tier
    beveled_cube(f"alt_t{level}", (lw, ld, 0.5), bevel_offset=0.06,
                 loc=(0, 0, lz + 0.25), parent=altar_e, mat_=M_WOOD_BROWN)
    # Cloth on top (color)
    cloth_color = [M_PAPEL_PINK, M_PAPEL_PURPLE, M_PAPEL_ORANGE][level]
    beveled_cube(f"alt_cloth{level}", (lw + 0.10, ld + 0.10, 0.06), bevel_offset=0.02,
                 loc=(0, 0, lz + 0.53), parent=altar_e, mat_=cloth_color)

# Photo frames on top tier (3 photos signature)
for ph in range(3):
    phx = (ph - 1) * 1.0
    # Frame
    beveled_cube(f"frame{ph}", (0.55, 0.10, 0.65), bevel_offset=0.03,
                 loc=(phx, -0.3, 2.5), parent=altar_e, mat_=M_FRAME_GOLD)
    # Photo
    beveled_cube(f"photo{ph}", (0.40, 0.02, 0.50), bevel_offset=0.01,
                 loc=(phx, -0.35, 2.5), parent=altar_e, mat_=M_PHOTO)

# 6 candles on tiers
candle_positions = [(-1.8, -0.2, 0.55), (1.8, -0.2, 0.55),
                    (-1.3, -0.1, 1.25), (1.3, -0.1, 1.25),
                    (-0.7, 0, 1.95), (0.7, 0, 1.95)]
candles_animated = []
for ci, (cax, cay, caz) in enumerate(candle_positions):
    c_e = empty(f"cand{ci}_e", (cax, cay, caz), parent=altar_e)
    cyl(f"cand{ci}", r=0.06, depth=0.30, segs=12, loc=(0, 0, 0.15),
        parent=c_e, mat_=M_CANDLE_WAX)
    flame_e = empty(f"cand{ci}_fl_e", (0, 0, 0.42), parent=c_e)
    smooth_cone(f"cand{ci}_fl_o", r1=0.06, r2=0.01, depth=0.20, segs=12, loc=(0, 0, 0.10),
                parent=flame_e, mat_=M_FLAME_OUTER)
    smooth_cone(f"cand{ci}_fl_c", r1=0.04, r2=0.008, depth=0.15, segs=12, loc=(0, 0, 0.08),
                parent=flame_e, mat_=M_FLAME_CORE)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    candles_animated.append(flame_e)
    candles_animated[-1]["_phase"] = random.uniform(0, math.pi*2)

# Pan de muerto on altar (signature bread)
for bi in range(3):
    bx = (bi - 1) * 0.5
    # Bread round
    smooth_sphere(f"pdm{bi}", r=0.18, segs=16, rings=12, loc=(bx, 0.3, 1.30),
                  parent=altar_e, mat_=M_BREAD, scale=(1, 1, 0.65))
    # Bone decorations on top (signature)
    for bn in range(4):
        ba = (bn / 4.0) * math.pi * 2
        cyl(f"pdm_bn{bi}_{bn}", r=0.025, depth=0.18, segs=8,
            loc=(bx + math.cos(ba)*0.10, 0.3 + math.sin(ba)*0.10, 1.40),
            parent=altar_e, mat_=M_BREAD_SUGAR)
    # Center skull/ball
    smooth_sphere(f"pdm_c{bi}", r=0.05, loc=(bx, 0.3, 1.45),
                  parent=altar_e, mat_=M_BREAD_SUGAR)

# Tequila bottles
for ti in range(2):
    tx = (ti - 0.5) * 1.2
    # Bottle body
    smooth_cone(f"teq{ti}_body", r1=0.12, r2=0.08, depth=0.40, segs=14,
                loc=(tx, 0.3, 0.85), parent=altar_e, mat_=M_BOTTLE_GLASS)
    # Neck
    cyl(f"teq{ti}_neck", r=0.04, depth=0.15, segs=10, loc=(tx, 0.3, 1.12),
        parent=altar_e, mat_=M_BOTTLE_GLASS)
    # Cap
    cyl(f"teq{ti}_cap", r=0.04, depth=0.04, segs=10, loc=(tx, 0.3, 1.22),
        parent=altar_e, mat_=M_MARIACHI_GOLD if False else M_CATRINA_GOLD)
    # Liquid inside
    smooth_cone(f"teq{ti}_liq", r1=0.10, r2=0.06, depth=0.30, segs=14,
                loc=(tx, 0.3, 0.83), parent=altar_e, mat_=M_TEQUILA)

# Decorative sugar skulls on altar (signature calaveras de azucar)
for ssi in range(5):
    ssx = (ssi - 2) * 0.65
    skull_color = SKULL_PAINTS[ssi % len(SKULL_PAINTS)]
    s_e = empty(f"sugar_s{ssi}_e", (ssx, -0.4, 1.30), parent=altar_e)
    smooth_sphere(f"sug_s{ssi}", r=0.13, segs=18, rings=12, loc=(0, 0, 0),
                  parent=s_e, mat_=M_BONE_PAINTED, scale=(1, 1, 1.1))
    # Painted eye sockets
    for side in (-1, 1):
        smooth_sphere(f"sug_se{ssi}_{side}", r=0.04,
                      loc=(side*0.05, -0.10, 0.02), parent=s_e, mat_=skull_color)
    # Painted forehead pattern
    smooth_sphere(f"sug_fh{ssi}", r=0.04, loc=(0, -0.12, 0.08),
                  parent=s_e, mat_=skull_color)
    # Painted dots
    for ddi in range(5):
        dda = (ddi / 5.0) * math.pi - math.pi/2
        smooth_sphere(f"sug_dd{ssi}_{ddi}", r=0.015,
                      loc=(math.cos(dda)*0.08, -0.13, -0.05),
                      parent=s_e, mat_=skull_color)
    s_e["_phase"] = random.uniform(0, math.pi*2)

# Cempasuchil flower piles on altar tiers (signature)
for fp in range(20):
    fpx = random.uniform(-2.0, 2.0)
    fpy = random.uniform(-0.8, 0.5)
    fpz = random.choice([0.60, 1.30, 2.00])
    smooth_sphere(f"alt_fl{fp}", r=random.uniform(0.06, 0.10),
                  loc=(fpx, fpy, fpz), parent=altar_e,
                  mat_=random.choice(MARIGOLD_VARIANTS),
                  scale=(1, 1, 0.5))

# ============ PAPEL PICADO (signature paper banners suspended) ============
papel_picado = []
# Strung between columns
for row in range(4):
    rz = 8 - row * 1.5
    for col in range(12):
        cx_p = -22 + col * 4
        col_mat = PAPEL_COLORS[col % len(PAPEL_COLORS)]
        pp_e = empty(f"pp{row}_{col}_e", (cx_p, 0, rz))
        # Banner rectangle
        beveled_cube(f"pp{row}_{col}", (1.5, 0.04, 1.0), bevel_offset=0.04,
                     loc=(0, 0, -0.5), parent=pp_e, mat_=col_mat)
        # Decorative pattern (signature cut-paper)
        for di in range(4):
            for dj in range(3):
                # Holes
                if (di + dj) % 2 == 0:
                    pass
        # Cut tassels at bottom
        for ti2 in range(4):
            tx_p = (ti2 - 1.5) * 0.30
            beveled_cube(f"pp{row}_{col}_t{ti2}", (0.10, 0.04, 0.25), bevel_offset=0.02,
                         loc=(tx_p, 0, -1.10), parent=pp_e, mat_=col_mat)
        pp_e["_phase"] = random.uniform(0, math.pi*2)
        papel_picado.append(pp_e)

# String holding them
for row in range(4):
    rz = 8 - row * 1.5
    cyl(f"string{row}", r=0.02, depth=50, segs=8, loc=(0, 0, rz + 0.05),
        mat_=M_BRANCH).rotation_euler = (0, math.radians(90), 0)

# ============ FLOWER ARCH ENTRY (signature) ============
arch_e = empty("arch", loc=(0, 16, 0))
# 2 vertical posts
for side in (-1, 1):
    cyl(f"arch_p{side}", r=0.20, depth=4.5, segs=14, loc=(side*3, 0, 2.25),
        parent=arch_e, mat_=M_BRANCH)
# Top arc
for ai in range(11):
    aa = math.pi * ai / 10.0
    ax_a = math.cos(aa) * 3
    az_a = math.sin(aa) * 1.5 + 4.5
    smooth_sphere(f"arch_top{ai}", r=0.18, loc=(ax_a, 0, az_a),
                  parent=arch_e, mat_=M_BRANCH)
# Marigold cover on arch (signature)
for fi in range(80):
    fa = random.uniform(0, math.pi)
    fax = math.cos(fa) * 3
    faz = math.sin(fa) * 1.5 + 4.5
    smooth_sphere(f"arch_fl{fi}", r=random.uniform(0.10, 0.16),
                  loc=(fax + random.uniform(-0.3, 0.3),
                       random.uniform(-0.2, 0.2),
                       faz + random.uniform(-0.3, 0.3)),
                  parent=arch_e, mat_=random.choice(MARIGOLD_VARIANTS))
# Posts marigold cover
for side in (-1, 1):
    for fi in range(20):
        fz_a = random.uniform(0.5, 4.0)
        smooth_sphere(f"arch_p_fl{side}_{fi}", r=random.uniform(0.08, 0.13),
                      loc=(side*3 + random.uniform(-0.3, 0.3),
                           random.uniform(-0.2, 0.2),
                           fz_a),
                      parent=arch_e, mat_=random.choice(MARIGOLD_VARIANTS))

# ============ 8 SKELETON CHILDREN running ============
def make_skeleton_child(name, loc, scale=0.7, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_cone(f"{name}_torso", r1=0.18*scale, r2=0.20*scale, depth=0.6*scale, segs=14,
                loc=(0, 0, 0.9*scale), parent=base, mat_=M_BONE_WHITE)
    # Ribs (signature)
    for ri in range(4):
        cyl(f"{name}_rib{ri}", r=0.22*scale, depth=0.04*scale, segs=14,
            loc=(0, 0, 0.65*scale + ri*0.12*scale), parent=base, mat_=M_BONE_WHITE)
    # Pelvis
    smooth_sphere(f"{name}_pel", r=0.20*scale, loc=(0, 0, 0.55*scale),
                  parent=base, mat_=M_BONE_WHITE, scale=(1.2, 0.7, 0.6))
    # Legs (running pose)
    for side_idx, side in enumerate((-1, 1)):
        leg_e = empty(f"{name}_le{side_idx}", (side*0.10*scale, 0, 0.50*scale), parent=base)
        leg_e.rotation_euler = (math.radians(side*-30), 0, 0)
        cyl(f"{name}_upleg{side_idx}", r=0.05*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=leg_e, mat_=M_BONE_WHITE)
        smooth_sphere(f"{name}_kn{side_idx}", r=0.06*scale, loc=(0, 0, -0.42*scale),
                      parent=leg_e, mat_=M_BONE_WHITE)
        cyl(f"{name}_lowleg{side_idx}", r=0.04*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.62*scale), parent=leg_e, mat_=M_BONE_WHITE)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        arm_e = empty(f"{name}_ae{side_idx}", (side*0.22*scale, 0, 1.15*scale), parent=base)
        arm_e.rotation_euler = (math.radians(side*40), 0, 0)
        cyl(f"{name}_uarm{side_idx}", r=0.04*scale, depth=0.32*scale, segs=10,
            loc=(0, 0, -0.16*scale), parent=arm_e, mat_=M_BONE_WHITE)
        cyl(f"{name}_fa{side_idx}", r=0.035*scale, depth=0.28*scale, segs=10,
            loc=(0, 0, -0.45*scale), parent=arm_e, mat_=M_BONE_WHITE)
    # Skull
    head_e = empty(f"{name}_he", (0, 0, 1.40*scale), parent=base)
    smooth_sphere(f"{name}_skull", r=0.18*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_BONE_PAINTED, scale=(1, 1.05, 1.1))
    for side in (-1, 1):
        smooth_sphere(f"{name}_es{side}", r=0.04*scale,
                      loc=(side*0.07*scale, -0.12*scale, 0.02*scale),
                      parent=head_e, mat_=M_EYE_BLACK)
        smooth_sphere(f"{name}_egl{side}", r=0.02*scale,
                      loc=(side*0.07*scale, -0.15*scale, 0.02*scale),
                      parent=head_e, mat_=M_EYE_GLOW)
    base["_phase"] = random.uniform(0, math.pi*2)
    base["_speed"] = random.uniform(1.2, 2.0)
    return {"root": base, "L": None, "R": None, "he": head_e}

skeleton_children = []
sc_positions = [(-12, 6, math.radians(45)), (12, 6, math.radians(-45)),
                (-14, -6, math.radians(135)), (14, -6, math.radians(-135)),
                (-10, 12, math.radians(60)), (10, 12, math.radians(-60)),
                (-8, -12, math.radians(120)), (8, -12, math.radians(-120))]
for i, (scx, scy, fac) in enumerate(sc_positions):
    sc = make_skeleton_child(f"sk_child{i}", (scx, scy, 0), scale=0.7, facing=fac)
    skeleton_children.append(sc)

# ============ DEAD TREES with marigolds + butterflies sitting ============
for ti in range(4):
    ta = (ti / 4.0) * math.pi * 2 + math.pi/4
    tx = math.cos(ta) * 22
    ty = math.sin(ta) * 22
    t_e = empty(f"tree{ti}", (tx, ty, 0))
    # Trunk
    cyl(f"trunk{ti}", r=0.40, depth=5, segs=14, loc=(0, 0, 2.5),
        parent=t_e, mat_=M_BRANCH)
    # Branches dead crooked
    for bi in range(7):
        ba = random.uniform(0, math.pi*2)
        bz = random.uniform(3, 5)
        bl = random.uniform(1.5, 2.5)
        br_e = empty(f"br{ti}_{bi}_e", (0, 0, bz), parent=t_e)
        br_e.rotation_euler = (math.radians(random.uniform(40, 80)), 0, ba)
        cyl(f"br{ti}_{bi}", r=0.10, depth=bl, segs=10, loc=(0, 0, bl/2),
            parent=br_e, mat_=M_BRANCH)
        # Sub branches
        for sb in range(2):
            sba = random.uniform(0, math.pi*2)
            sbr_e = empty(f"sbr{ti}_{bi}_{sb}_e", (0, 0, bl), parent=br_e)
            sbr_e.rotation_euler = (math.radians(random.uniform(20, 50)), 0, sba)
            cyl(f"sbr{ti}_{bi}_{sb}", r=0.05, depth=0.8, segs=8, loc=(0, 0, 0.4),
                parent=sbr_e, mat_=M_BRANCH)
            # Marigold on branch tip
            smooth_sphere(f"br_fl{ti}_{bi}_{sb}", r=0.20,
                          loc=(0, 0, 0.85), parent=sbr_e,
                          mat_=random.choice(MARIGOLD_VARIANTS))

# ============================================================
# ⭐ 600 CEMPASUCHIL PETALS + 400 MONARCH BUTTERFLIES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
cempasuchil_petals = []
for i in range(600):
    px = random.uniform(-30, 30)
    py = random.uniform(-30, 30)
    pz = random.uniform(0.5, 14)
    p_obj = smooth_sphere(f"cemp{i}", r=random.uniform(0.07, 0.12), segs=10, rings=6,
                          loc=(px, py, pz),
                          mat_=random.choice(MARIGOLD_VARIANTS),
                          scale=(1.2, 1.2, 0.40))
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_amp_x"] = random.uniform(0.5, 1.5)
    p_obj["_amp_y"] = random.uniform(0.5, 1.5)
    p_obj["_amp_z"] = random.uniform(0.8, 1.5)
    p_obj["_speed"] = random.uniform(0.4, 0.9)
    p_obj["_fall"] = random.uniform(1.2, 2.5)
    cempasuchil_petals.append(p_obj)

# 400 monarch butterflies
butterflies = []
for i in range(400):
    px = random.uniform(-25, 25)
    py = random.uniform(-25, 25)
    pz = random.uniform(1, 12)
    bf_e = empty(f"bf{i}", (px, py, pz))
    # Body
    smooth_sphere(f"bf_body{i}", r=0.05, segs=10, rings=6, loc=(0, 0, 0),
                  parent=bf_e, mat_=M_BUTTERFLY_BLACK, scale=(1, 2, 0.8))
    # Wings (4 lobed signature)
    for side in (-1, 1):
        # Upper wing
        upper = beveled_cube(f"bf_wu{i}_{side}", (0.20, 0.04, 0.18), bevel_offset=0.02,
                             loc=(side*0.15, 0, 0.02), parent=bf_e, mat_=M_BUTTERFLY_ORANGE)
        # Lower wing
        lower = beveled_cube(f"bf_wl{i}_{side}", (0.16, 0.04, 0.14), bevel_offset=0.02,
                             loc=(side*0.13, -0.10, -0.04), parent=bf_e, mat_=M_BUTTERFLY_ORANGE)
        # Black wing veins
        beveled_cube(f"bf_vein{i}_{side}", (0.20, 0.05, 0.02), bevel_offset=0.005,
                     loc=(side*0.15, 0.05, 0.04), parent=bf_e, mat_=M_BUTTERFLY_BLACK)
        # White spots
        smooth_sphere(f"bf_spot{i}_{side}", r=0.02,
                      loc=(side*0.20, 0.02, 0.05), parent=bf_e, mat_=M_BUTTERFLY_WHITE)
    bf_e["_phase"] = random.uniform(0, math.pi*2)
    bf_e["_base_x"] = px; bf_e["_base_y"] = py; bf_e["_base_z"] = pz
    bf_e["_amp_x"] = random.uniform(1.5, 3.5)
    bf_e["_amp_y"] = random.uniform(1.5, 3.5)
    bf_e["_amp_z"] = random.uniform(0.8, 2.0)
    bf_e["_speed"] = random.uniform(0.7, 1.6)
    butterflies.append(bf_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Catrinas dance multi-axes
for c in catrinas:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Body sway
        c["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                     c["root"].rotation_euler.z + math.sin(t * 1.2 + phase) * math.radians(3))
        c["root"].location.z = abs(math.sin(t * 2.0 + phase)) * 0.15
        c["root"].keyframe_insert("rotation_euler", frame=f)
        c["root"].keyframe_insert("location", frame=f)
        # Head turn
        c["he"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(15))
        c["he"].keyframe_insert("rotation_euler", frame=f)
        # Hat sway
        c["hat"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3),
                                    math.cos(t * 1.5 + phase) * math.radians(3), 0)
        c["hat"].keyframe_insert("rotation_euler", frame=f)

# Mariachi play instruments multi-axes
for m in mariachi_band:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Body rhythm
        m["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(4), 0,
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        # Right arm strumming
        m["R"].rotation_euler = (math.radians(-30) + math.sin(t * 5.0 + phase) * math.radians(15),
                                  0, math.radians(-20))
        m["R"].keyframe_insert("rotation_euler", frame=f)
        # Head bob
        m["he"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(8), 0,
                                   math.cos(t * 2.5 + phase) * math.radians(5))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Skeleton children running
for sc in skeleton_children:
    phase = sc["root"]["_phase"]; speed = sc["root"]["_speed"]
    bx_sc = sc["root"].location.x; by_sc = sc["root"].location.y
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        sc["root"].location.x = bx_sc + math.sin(t * speed + phase) * 1.5
        sc["root"].location.y = by_sc + math.cos(t * speed * 0.8 + phase) * 1.2
        sc["root"].location.z = abs(math.sin(t * speed * 3.0 + phase)) * 0.3
        sc["root"].rotation_euler = (math.sin(t * speed * 4.0 + phase) * math.radians(8), 0,
                                      math.atan2(math.cos(t * speed * 0.8 + phase),
                                                  math.sin(t * speed + phase)))
        sc["root"].keyframe_insert("location", frame=f)
        sc["root"].keyframe_insert("rotation_euler", frame=f)

# Candles flicker on altar + graves
for ci in range(len(candles_animated)):
    fl_e = candles_animated[ci]
    phase = fl_e.get("_phase", 0)
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 5.0 + phase) * 0.15
        fl_e.scale = (1 + math.sin(t * 4.0 + phase) * 0.12,
                      1 + math.cos(t * 4.5 + phase) * 0.12, s)
        fl_e.rotation_euler = (0, 0, math.sin(t * 3.0 + phase) * 0.15)
        fl_e.keyframe_insert("scale", frame=f)
        fl_e.keyframe_insert("rotation_euler", frame=f)

# Papel picado swing in wind
for pp_e in papel_picado:
    phase = pp_e["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        pp_e.rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(15),
                                math.cos(t * 1.5 + phase) * math.radians(8), 0)
        pp_e.keyframe_insert("rotation_euler", frame=f)

# 600 cempasuchil petals falling
for p in cempasuchil_petals:
    phase = p["_phase"]; speed = p["_speed"]; fall = p["_fall"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    ax, ay, az = p["_amp_x"], p["_amp_y"], p["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.3)
        if z < 0.3: z = bz
        p.location = (x, y, max(0.2, z))
        p.rotation_euler = (t * 2.5 + phase, t * 1.8 + phase, t * 3.0 + phase)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# 400 monarch butterflies erratic flight
for bf in butterflies:
    phase = bf["_phase"]; speed = bf["_speed"]
    bx, by, bz = bf["_base_x"], bf["_base_y"], bf["_base_z"]
    ax, ay, az = bf["_amp_x"], bf["_amp_y"], bf["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase) + 0.3*math.sin(t * speed * 3 + phase * 2)
        y = by + ay * math.cos(t * speed * 0.9 + phase) + 0.3*math.cos(t * speed * 3 + phase)
        z = bz + az * math.sin(t * speed * 1.4 + phase) + 0.2*math.sin(t * 5.0 + phase)
        bf.location = (x, y, max(0.4, z))
        bf.rotation_euler = (math.sin(t * 6.0 + phase) * 0.5,
                              math.cos(t * 6.0 + phase) * 0.5,
                              math.atan2(math.cos(t * speed * 0.9 + phase),
                                         math.sin(t * speed + phase)))
        bf.keyframe_insert("location", frame=f)
        bf.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_muertos_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_mexican_dia_de_muertos] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_mexican_dia_de_muertos] cemetery + 12 graves + 8 catrinas + 5 mariachi + ofrenda altar + papel picado + arch + 8 skeleton kids + 4 trees + 600 cempasuchil + 400 monarchs")
print("⭐ FIXES: 1 ground + 600 cempasuchil + 400 monarch butterflies (signature Día de Muertos thematic mandatory) ⭐")
