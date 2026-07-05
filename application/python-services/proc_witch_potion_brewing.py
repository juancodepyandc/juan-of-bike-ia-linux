"""
proc_witch_potion_brewing.py — 191e procédural AuroraIA (55e qualité)
Sorcière brassant potion dans forêt sombre avec chaudron + 30 bulles + chat noir + lucioles + corbeaux + hibou
Construction smooth (bevels + smooth shading + multi-axis animations + anatomie articulée hiérarchique)
"""
import bpy, bmesh, math, random, os

random.seed(0xBEEFCA47)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in (bpy.data.meshes, bpy.data.materials, bpy.data.objects,
              bpy.data.cameras, bpy.data.lights, bpy.data.collections):
        for x in list(c):
            try: c.remove(x)
            except: pass

def mat(name, base=(0.8,0.8,0.8,1.0), metallic=0.0, roughness=0.5,
        emission=None, emission_strength=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
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
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    smooth_shade(me)
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

def smooth_sphere(name, r=1.0, segs=28, rings=18, loc=(0,0,0), parent=None, mat_=None, scale=(1,1,1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    if scale != (1,1,1):
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    return make_obj(name, bm, loc, parent, mat_)

def smooth_cone(name, r1, r2, depth, segs=20, loc=(0,0,0), parent=None, mat_=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    return make_obj(name, bm, loc, parent, mat_)

def cyl(name, r, depth, segs=18, loc=(0,0,0), parent=None, mat_=None):
    return smooth_cone(name, r, r, depth, segs, loc, parent, mat_)

def empty(name, loc=(0,0,0), parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    if parent: e.parent = parent
    return e

# ============ SCENE ============
reset()
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 180
scene.render.fps = 30

# ============ MATERIALS ============
M_SKY_NIGHT = mat("sky_night", (0.06, 0.04, 0.12, 1.0), 0.0, 0.7, emission=(0.10,0.06,0.18), emission_strength=0.6)
M_MOON = mat("moon", (0.95, 0.92, 0.80, 1.0), 0.0, 0.3, emission=(0.95,0.90,0.78), emission_strength=8.0)
M_STAR = mat("star", (1.0, 1.0, 0.95, 1.0), 0.0, 0.2, emission=(1.0,0.95,0.85), emission_strength=15.0)
M_FOG = mat("fog", (0.30, 0.32, 0.38, 1.0), 0.0, 0.85, emission=(0.20,0.22,0.30), emission_strength=0.3, alpha=0.35)
M_GROUND = mat("ground", (0.10, 0.08, 0.06, 1.0), 0.0, 0.90)
M_GRASS_DARK = mat("grass_dark", (0.12, 0.18, 0.08, 1.0), 0.0, 0.85)

# Tree (twisted dark)
M_TRUNK_DARK = mat("trunk_dark", (0.10, 0.07, 0.05, 1.0), 0.0, 0.88)
M_LEAF_DARK = mat("leaf_dark", (0.08, 0.12, 0.06, 1.0), 0.0, 0.75, emission=(0.06,0.10,0.05), emission_strength=0.15)
M_LEAF_GLOW = mat("leaf_glow", (0.20, 0.45, 0.20, 1.0), 0.0, 0.55, emission=(0.18,0.55,0.20), emission_strength=1.2)

# Cauldron
M_CAULDRON = mat("cauldron", (0.08, 0.08, 0.10, 1.0), 0.85, 0.40, emission=(0.06,0.06,0.08), emission_strength=0.2)
M_CAULDRON_RIM = mat("cauldron_rim", (0.20, 0.20, 0.22, 1.0), 0.85, 0.35, emission=(0.15,0.15,0.18), emission_strength=0.3)
M_POTION_GREEN = mat("potion_green", (0.15, 0.95, 0.30, 1.0), 0.0, 0.10, emission=(0.20,1.0,0.30), emission_strength=8.0)
M_POTION_PURPLE = mat("potion_purple", (0.65, 0.18, 0.85, 1.0), 0.0, 0.15, emission=(0.70,0.20,0.90), emission_strength=5.0)
M_BUBBLE = mat("bubble", (0.85, 1.0, 0.80, 0.6), 0.0, 0.10, emission=(0.85,1.0,0.85), emission_strength=4.0, alpha=0.5)

# Fire under cauldron
M_FIRE_OUTER = mat("fire_outer", (1.0, 0.50, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.55,0.15), emission_strength=12.0)
M_FIRE_INNER = mat("fire_inner", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.90,0.45), emission_strength=18.0)
M_LOG = mat("log", (0.25, 0.15, 0.08, 1.0), 0.0, 0.80)
M_EMBER = mat("ember", (1.0, 0.30, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.40,0.15), emission_strength=10.0)

# Witch
M_ROBE = mat("robe", (0.04, 0.04, 0.06, 1.0), 0.0, 0.80)
M_HAT = mat("hat", (0.05, 0.05, 0.07, 1.0), 0.0, 0.75)
M_HAT_BAND = mat("hat_band", (0.45, 0.10, 0.45, 1.0), 0.3, 0.55, emission=(0.40,0.10,0.40), emission_strength=0.6)
M_BUCKLE = mat("buckle", (0.85, 0.78, 0.30, 1.0), 0.9, 0.25, emission=(0.78,0.70,0.28), emission_strength=0.5)
M_SKIN_GREEN = mat("skin_green", (0.50, 0.65, 0.42, 1.0), 0.0, 0.65, emission=(0.40,0.55,0.32), emission_strength=0.3)
M_HAIR_BLACK = mat("hair_black", (0.03, 0.03, 0.04, 1.0), 0.0, 0.85)
M_EYES_YELLOW = mat("eyes_yellow", (1.0, 0.85, 0.25, 1.0), 0.0, 0.2, emission=(1.0,0.85,0.20), emission_strength=4.0)
M_MOUTH = mat("mouth", (0.30, 0.05, 0.15, 1.0), 0.0, 0.6, emission=(0.25,0.04,0.12), emission_strength=0.3)

# Magic staff
M_STAFF = mat("staff", (0.20, 0.12, 0.08, 1.0), 0.0, 0.80)
M_STAFF_ORB = mat("staff_orb", (0.85, 0.40, 1.0, 1.0), 0.0, 0.15, emission=(0.90,0.50,1.0), emission_strength=10.0)
M_STAFF_RUNES = mat("staff_runes", (0.95, 0.65, 1.0, 1.0), 0.0, 0.30, emission=(1.0,0.65,1.0), emission_strength=6.0)

# Cat
M_CAT_BLACK = mat("cat_black", (0.03, 0.03, 0.04, 1.0), 0.0, 0.55, emission=(0.05,0.05,0.07), emission_strength=0.2)
M_CAT_EYES = mat("cat_eyes", (1.0, 0.95, 0.20, 1.0), 0.0, 0.15, emission=(1.0,0.90,0.18), emission_strength=8.0)
M_CAT_PINK = mat("cat_pink", (0.85, 0.35, 0.55, 1.0), 0.0, 0.55)

# Broom
M_BROOM_HANDLE = mat("broom_handle", (0.25, 0.15, 0.08, 1.0), 0.0, 0.75)
M_BROOM_BRISTLE = mat("broom_bristle", (0.55, 0.40, 0.20, 1.0), 0.0, 0.85)
M_BROOM_BIND = mat("broom_bind", (0.35, 0.15, 0.10, 1.0), 0.0, 0.70)

# Table + grimoire
M_TABLE = mat("table", (0.20, 0.12, 0.08, 1.0), 0.0, 0.78)
M_BOOK_COVER = mat("book_cover", (0.40, 0.05, 0.10, 1.0), 0.3, 0.45, emission=(0.30,0.05,0.08), emission_strength=0.4)
M_BOOK_PAGES = mat("book_pages", (0.88, 0.80, 0.65, 1.0), 0.0, 0.65, emission=(0.80,0.72,0.55), emission_strength=0.5)
M_INK = mat("ink", (0.15, 0.05, 0.05, 1.0), 0.0, 0.8)

# Vials
VIAL_COLORS = [
    mat("vial_red", (1.0, 0.15, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.20,0.25), emission_strength=4.0),
    mat("vial_blue", (0.15, 0.40, 1.0, 1.0), 0.0, 0.10, emission=(0.20,0.50,1.0), emission_strength=4.0),
    mat("vial_yellow", (1.0, 0.95, 0.15, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.25), emission_strength=4.5),
    mat("vial_green", (0.20, 1.0, 0.30, 1.0), 0.0, 0.10, emission=(0.25,1.0,0.35), emission_strength=5.0),
    mat("vial_purple", (0.70, 0.20, 0.95, 1.0), 0.0, 0.10, emission=(0.75,0.25,1.0), emission_strength=4.5),
    mat("vial_orange", (1.0, 0.50, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.55,0.15), emission_strength=4.0),
]
M_VIAL_GLASS = mat("vial_glass", (0.85, 0.95, 1.0, 0.5), 0.0, 0.05, alpha=0.5)
M_VIAL_CORK = mat("vial_cork", (0.55, 0.35, 0.15, 1.0), 0.0, 0.85)

# Mushrooms (fly agaric red+white)
M_MUSH_RED = mat("mush_red", (0.95, 0.18, 0.15, 1.0), 0.0, 0.50, emission=(0.85,0.18,0.15), emission_strength=0.8)
M_MUSH_DOT = mat("mush_dot", (1.0, 0.98, 0.92, 1.0), 0.0, 0.45, emission=(0.98,0.95,0.90), emission_strength=0.5)
M_MUSH_STEM = mat("mush_stem", (0.92, 0.88, 0.78, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.75), emission_strength=0.3)

# Lucioles
M_FIREFLY = mat("firefly", (1.0, 0.95, 0.40, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.50), emission_strength=18.0)

# Birds
M_OWL = mat("owl", (0.55, 0.45, 0.30, 1.0), 0.0, 0.65)
M_OWL_BELLY = mat("owl_belly", (0.85, 0.75, 0.55, 1.0), 0.0, 0.60, emission=(0.75,0.65,0.50), emission_strength=0.3)
M_OWL_EYES = mat("owl_eyes", (1.0, 0.70, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.65,0.15), emission_strength=6.0)
M_BEAK = mat("beak", (0.30, 0.20, 0.10, 1.0), 0.0, 0.6)
M_RAVEN = mat("raven", (0.04, 0.04, 0.06, 1.0), 0.0, 0.45, emission=(0.05,0.05,0.07), emission_strength=0.2)
M_RAVEN_BEAK = mat("raven_beak", (0.20, 0.18, 0.18, 1.0), 0.0, 0.55)
M_RAVEN_EYE = mat("raven_eye", (1.0, 0.30, 0.10, 1.0), 0.0, 0.20, emission=(1.0,0.35,0.15), emission_strength=3.0)

# Skull (decoration)
M_SKULL = mat("skull", (0.85, 0.82, 0.72, 1.0), 0.0, 0.65, emission=(0.75,0.72,0.65), emission_strength=0.3)

# ============ SKY DOME + MOON + STARS ============
sky = smooth_sphere("sky_dome", r=85.0, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY_NIGHT, scale=(1,1,0.6))
sky.scale = (1,1,0.6)
moon = smooth_sphere("moon", r=3.5, loc=(-15, 35, 28), mat_=M_MOON)
# Crescent shadow (smaller dark sphere offset)
smooth_sphere("moon_shadow", r=3.4, loc=(-12, 35, 28), mat_=M_SKY_NIGHT)
# Stars (60)
stars = []
for i in range(60):
    sx = random.uniform(-50, 50)
    sy = random.uniform(15, 45)
    sz = random.uniform(15, 35)
    star = smooth_sphere(f"star{i}", r=random.uniform(0.08, 0.18),
                         loc=(sx, sy, sz), mat_=M_STAR)
    star["_phase"] = random.uniform(0, math.pi*2)
    stars.append(star)

# ============ GROUND + FOG ============
ground = beveled_cube("ground", (50, 50, 0.4), bevel_offset=0.08, loc=(0, 0, -0.2), mat_=M_GROUND)
# Grass tufts
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(3, 18)
    smooth_sphere(f"grass{i}", r=random.uniform(0.20, 0.40),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.1),
                  mat_=M_GRASS_DARK, scale=(1, 1, 0.4))
# Fog layer (large flat semi-transparent)
fog_layers = []
for i in range(3):
    a = (i / 3.0) * math.pi * 2
    fog = smooth_sphere(f"fog{i}", r=12.0, segs=20, rings=12,
                       loc=(6*math.cos(a), 6*math.sin(a), 0.4),
                       mat_=M_FOG, scale=(1.2, 1.0, 0.08))
    fog["_phase"] = random.uniform(0, math.pi*2)
    fog_layers.append(fog)

# ============ TWISTED TREES (8 trees with gnarled trunks) ============
trees = []
def make_twisted_tree(name, loc, scale=1.0):
    base = empty(name, loc)
    # Trunk: 6 twisted segments
    for i in range(6):
        r1 = (0.38 - i*0.045) * scale
        r2 = (0.34 - i*0.045) * scale
        h = 0.9 * scale
        seg = smooth_cone(f"{name}_t{i}", r1=r1, r2=r2, depth=h, segs=14,
                          loc=(random.uniform(-0.1,0.1)*scale,
                               random.uniform(-0.1,0.1)*scale,
                               (i+0.5)*h),
                          parent=base, mat_=M_TRUNK_DARK)
        seg.rotation_euler = (math.radians(random.uniform(-8,8)),
                              math.radians(random.uniform(-8,8)), 0)
    # 4 twisted branches
    top_z = 6 * 0.9 * scale
    branches_e = []
    for j in range(4):
        a = (j / 4.0) * math.pi * 2 + random.uniform(-0.2, 0.2)
        b_e = empty(f"{name}_b_e{j}", (0, 0, top_z - 0.5*scale), parent=base)
        b_e.rotation_euler = (math.radians(50), 0, a)
        # Branch segments
        for k in range(3):
            bseg = smooth_cone(f"{name}_b{j}_{k}", r1=0.14*scale - k*0.025*scale,
                              r2=0.10*scale - k*0.025*scale, depth=0.6*scale,
                              segs=12,
                              loc=(0, (k+0.5)*0.6*scale, 0), parent=b_e, mat_=M_TRUNK_DARK)
            bseg.rotation_euler = (math.radians(20 + k*15), 0, 0)
        branches_e.append(b_e)
    # Sparse spooky leaves at branch tips
    for b_e in branches_e:
        for k in range(3):
            if random.random() > 0.4:
                m_ = M_LEAF_GLOW if random.random() < 0.25 else M_LEAF_DARK
                smooth_sphere(f"{name}_leaf_{id(b_e)}_{k}", r=0.30*scale,
                              loc=(random.uniform(-0.2,0.2)*scale,
                                   1.8*scale + random.uniform(-0.3,0.3)*scale,
                                   random.uniform(-0.1,0.4)*scale),
                              parent=b_e, mat_=m_,
                              scale=(1, 1, 0.6))
    return base

tree_positions = [
    (-13, 3, 0, 1.2), (12, 5, 0, 1.1),
    (-10, -8, 0, 1.0), (11, -7, 0, 1.05),
    (-16, 11, 0, 0.95), (15, 12, 0, 1.0),
    (-8, 14, 0, 0.9), (8, -14, 0, 0.95),
]
for i, (x, y, z, s) in enumerate(tree_positions):
    trees.append(make_twisted_tree(f"tree{i}", (x, y, z), scale=s))

# ============ CAULDRON ============
cauldron_base = empty("cauldron", loc=(0, 0, 0.95))
# Body (rounded pot)
smooth_sphere("cauldron_body", r=1.2, segs=28, rings=18,
              loc=(0, 0, 0), parent=cauldron_base, mat_=M_CAULDRON,
              scale=(1.0, 1.0, 0.9))
# Rim
cyl("cauldron_rim", r=1.18, depth=0.15, segs=28,
    loc=(0, 0, 0.85), parent=cauldron_base, mat_=M_CAULDRON_RIM)
# 3 legs underneath
for i in range(3):
    a = (i / 3.0) * math.pi * 2
    leg = cyl(f"cauldron_leg{i}", r=0.12, depth=0.85, segs=12,
             loc=(0.85*math.cos(a), 0.85*math.sin(a), -1.15),
             parent=cauldron_base, mat_=M_CAULDRON)
    leg.rotation_euler = (math.radians(15*math.sin(a)),
                          math.radians(-15*math.cos(a)), 0)
# Handles (2 side rings)
for side in (-1, 1):
    handle = cyl(f"handle_{side}", r=0.18, depth=0.05, segs=20,
                 loc=(side*1.20, 0, 0.50), parent=cauldron_base, mat_=M_CAULDRON_RIM)
    handle.rotation_euler = (math.radians(90), math.radians(side*15), 0)

# POTION inside (green liquid surface)
potion_surf = smooth_sphere("potion_surf", r=1.10, loc=(0, 0, 0.80),
                            parent=cauldron_base, mat_=M_POTION_GREEN,
                            scale=(1.05, 1.05, 0.06))

# 30 BUBBLES rising from potion (different sizes)
bubbles = []
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(0.05, 0.9)
    bx = rad * math.cos(a)
    by = rad * math.sin(a)
    bz = 0.85 + random.uniform(0, 1.8)
    br = random.uniform(0.06, 0.18)
    bub = smooth_sphere(f"bubble{i}", r=br, segs=14, rings=10,
                       loc=(bx, by, bz), parent=cauldron_base, mat_=M_BUBBLE)
    bub["_phase"] = random.uniform(0, math.pi*2)
    bub["_base_x"] = bx
    bub["_base_y"] = by
    bub["_base_z"] = bz
    bub["_speed"] = random.uniform(1.0, 2.5)
    bub["_base_r"] = br
    bubbles.append(bub)

# Steam puffs above (10)
steams = []
for i in range(10):
    a = random.uniform(0, math.pi*2)
    sx = random.uniform(-0.6, 0.6)
    sy = random.uniform(-0.6, 0.6)
    sz = 1.5 + i * 0.4
    steam = smooth_sphere(f"steam{i}", r=0.35, loc=(sx, sy, sz),
                         parent=cauldron_base, mat_=M_FOG)
    steam["_phase"] = random.uniform(0, math.pi*2)
    steams.append(steam)

# ============ FIRE under cauldron ============
fire_base = empty("fire", loc=(0, 0, 0))
# 4 logs crossed
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    log = cyl(f"log{i}", r=0.12, depth=1.2, segs=12,
             loc=(0.1*math.cos(a), 0.1*math.sin(a), 0.1),
             parent=fire_base, mat_=M_LOG)
    log.rotation_euler = (math.radians(90), 0, a)
# 6 flames (outer + inner)
flames = []
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    fx, fy = 0.18*math.cos(a), 0.18*math.sin(a)
    outer = smooth_cone(f"flame_o{i}", r1=0.22, r2=0.02, depth=0.7, segs=10,
                       loc=(fx, fy, 0.45), parent=fire_base, mat_=M_FIRE_OUTER)
    inner = smooth_cone(f"flame_i{i}", r1=0.13, r2=0.01, depth=0.5, segs=10,
                       loc=(fx, fy, 0.50), parent=fire_base, mat_=M_FIRE_INNER)
    outer["_phase"] = i * 0.7
    inner["_phase"] = i * 0.7 + 0.4
    flames.append((outer, inner))
# Embers (8 small glowing dots scattered)
embers = []
for i in range(8):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(0.05, 0.35)
    e = smooth_sphere(f"ember{i}", r=0.04,
                     loc=(rad*math.cos(a), rad*math.sin(a), random.uniform(0.05, 0.30)),
                     parent=fire_base, mat_=M_EMBER)
    e["_phase"] = random.uniform(0, math.pi*2)
    embers.append(e)

# ============ WITCH ANATOMIE ============
witch_base = empty("witch", loc=(-1.7, -1.4, 0))
witch_base.rotation_euler = (0, 0, math.radians(45))  # facing cauldron

# Robe long (cone-shaped down, body up)
beveled_cube("robe_lower", (0.85, 0.85, 1.5), bevel_offset=0.10,
             loc=(0, 0, 0.75), parent=witch_base, mat_=M_ROBE)
# Skirt flare bottom
smooth_cone("robe_skirt", r1=0.85, r2=0.45, depth=0.30, segs=24,
            loc=(0, 0, 0.15), parent=witch_base, mat_=M_ROBE)
# Torso
beveled_cube("witch_torso", (0.65, 0.55, 0.95), bevel_offset=0.08,
             loc=(0, 0, 1.95), parent=witch_base, mat_=M_ROBE)
# Belt
beveled_cube("witch_belt", (0.72, 0.62, 0.10), loc=(0, 0, 1.50),
             parent=witch_base, mat_=M_HAT_BAND)
# Belt buckle
beveled_cube("witch_buckle", (0.18, 0.10, 0.18), loc=(0, -0.32, 1.50),
             parent=witch_base, mat_=M_BUCKLE)
# Neck
cyl("witch_neck", r=0.12, depth=0.25, segs=14, loc=(0, 0, 2.55),
    parent=witch_base, mat_=M_SKIN_GREEN)
# Head
head_e = empty("witch_head_e", (0, 0, 2.80), parent=witch_base)
smooth_sphere("witch_head", r=0.30, segs=24, rings=16,
              loc=(0, 0, 0), parent=head_e, mat_=M_SKIN_GREEN)
# Hooked nose (long pointed forward)
nose = smooth_cone("witch_nose", r1=0.08, r2=0.025, depth=0.40, segs=12,
                  loc=(0, -0.42, -0.05), parent=head_e, mat_=M_SKIN_GREEN)
nose.rotation_euler = (math.radians(70), 0, 0)
# Wart on nose
smooth_sphere("witch_wart", r=0.04, loc=(0.04, -0.45, -0.10),
              parent=head_e, mat_=M_SKIN_GREEN, scale=(1.2, 1, 1))
# Chin pointed
smooth_cone("witch_chin", r1=0.18, r2=0.05, depth=0.20, segs=12,
            loc=(0, -0.22, -0.30), parent=head_e, mat_=M_SKIN_GREEN)
# Eyes (yellow glowing)
for side_idx, side in enumerate((-1, 1)):
    smooth_sphere(f"witch_eye_{side_idx}", r=0.07,
                  loc=(side*0.11, -0.25, 0.08), parent=head_e, mat_=M_EYES_YELLOW)
    smooth_sphere(f"witch_pup_{side_idx}", r=0.03,
                  loc=(side*0.11, -0.30, 0.08), parent=head_e, mat_=M_HAIR_BLACK)
# Eyebrows (angled menacing)
for side_idx, side in enumerate((-1, 1)):
    brow = beveled_cube(f"witch_brow_{side_idx}", (0.13, 0.04, 0.04),
                       loc=(side*0.13, -0.28, 0.20), parent=head_e, mat_=M_HAIR_BLACK)
    brow.rotation_euler = (0, 0, math.radians(side*-20))
# Mouth (open chanting)
beveled_cube("witch_mouth", (0.10, 0.03, 0.10), loc=(0, -0.30, -0.10),
             parent=head_e, mat_=M_MOUTH)
# 2 tooth (single front fangs)
for i in (-1, 1):
    cyl(f"witch_tooth_{i}", r=0.02, depth=0.06, segs=8,
        loc=(i*0.03, -0.31, -0.05), parent=head_e, mat_=M_MUSH_DOT)
# Long stringy black hair (spheres + cones flowing back)
for i in range(6):
    a = (i / 6.0) * math.pi - math.pi/2
    smooth_sphere(f"hair_l{i}", r=0.10, segs=12, rings=8,
                  loc=(0.30*math.cos(a), 0.18, 0.15 + 0.08*i),
                  parent=head_e, mat_=M_HAIR_BLACK, scale=(0.8, 1.5, 1.0))
# Long flowing hair down back (3 segs)
for i in range(3):
    hair_seg = beveled_cube(f"hair_back{i}", (0.40, 0.10, 0.45),
                           bevel_offset=0.05,
                           loc=(0, 0.20, -0.30 - i*0.40),
                           parent=head_e, mat_=M_HAIR_BLACK)
    hair_seg.rotation_euler = (math.radians(i*8), 0, 0)

# WITCH HAT (pointed, large brim)
hat_e = empty("hat_e", (0, 0, 0.35), parent=head_e)
# Brim (flat disc)
cyl("hat_brim", r=0.65, depth=0.06, segs=28,
    loc=(0, 0, 0), parent=hat_e, mat_=M_HAT)
# Cone (curved tip)
hat_cone = smooth_cone("hat_cone", r1=0.40, r2=0.04, depth=1.4, segs=18,
                       loc=(0.06, 0, 0.65), parent=hat_e, mat_=M_HAT)
# Tilt the cone slightly (curl-tip effect via rotation)
hat_cone.rotation_euler = (math.radians(8), 0, math.radians(5))
# Hat band
cyl("hat_band", r=0.42, depth=0.10, segs=28,
    loc=(0, 0, 0.10), parent=hat_e, mat_=M_HAT_BAND)
# Hat buckle
beveled_cube("hat_buckle", (0.12, 0.06, 0.12), loc=(0, -0.40, 0.10),
             parent=hat_e, mat_=M_BUCKLE)

# WITCH ARMS (one extended over cauldron with staff, other gesturing)
# Right arm extended toward cauldron with staff
r_sh = empty("witch_r_sh", (0.45, -0.20, 2.40), parent=witch_base)
r_sh.rotation_euler = (math.radians(-50), math.radians(20), math.radians(-30))
beveled_cube("witch_r_upper", (0.18, 0.18, 0.55), loc=(0, 0, -0.28),
             parent=r_sh, mat_=M_ROBE)
r_el = empty("witch_r_el", (0, 0, -0.58), parent=r_sh)
r_el.rotation_euler = (math.radians(30), 0, 0)
beveled_cube("witch_r_fa", (0.16, 0.16, 0.50), loc=(0, 0, -0.25),
             parent=r_el, mat_=M_ROBE)
# Right hand
r_hand = empty("witch_r_hand", (0, 0, -0.55), parent=r_el)
smooth_sphere("witch_r_hand_g", r=0.10, loc=(0, 0, 0),
              parent=r_hand, mat_=M_SKIN_GREEN)
# Fingers (3 visible)
for i in range(3):
    f = cyl(f"witch_r_finger{i}", r=0.025, depth=0.16, segs=8,
           loc=((i-1)*0.06, -0.08, -0.08), parent=r_hand, mat_=M_SKIN_GREEN)
    f.rotation_euler = (math.radians(40), 0, 0)

# STAFF held by right hand
staff_e = empty("staff_e", (0, 0, -0.10), parent=r_hand)
# Staff pole (long)
cyl("staff_pole", r=0.05, depth=2.4, segs=12,
    loc=(0, 0, -1.0), parent=staff_e, mat_=M_STAFF)
# Wrapping bands (3 runes)
for i in range(3):
    runes = cyl(f"staff_rune{i}", r=0.07, depth=0.08, segs=14,
               loc=(0, 0, -0.4 - i*0.55), parent=staff_e, mat_=M_STAFF_RUNES)
# Orb at top (magic glow)
staff_orb = smooth_sphere("staff_orb", r=0.18, segs=20, rings=14,
                          loc=(0, 0, 0.15), parent=staff_e, mat_=M_STAFF_ORB)
# Claw holding orb (3 prongs)
for i in range(3):
    a = (i / 3.0) * math.pi * 2
    claw = smooth_cone(f"staff_claw{i}", r1=0.04, r2=0.01, depth=0.20, segs=8,
                      loc=(0.15*math.cos(a), 0.15*math.sin(a), 0.08),
                      parent=staff_e, mat_=M_STAFF)
    claw.rotation_euler = (math.radians(-30*math.cos(a)),
                           math.radians(-30*math.sin(a)), 0)

# Left arm gesturing (raised toward cauldron)
l_sh = empty("witch_l_sh", (-0.45, -0.20, 2.40), parent=witch_base)
l_sh.rotation_euler = (math.radians(-90), math.radians(-25), math.radians(30))
beveled_cube("witch_l_upper", (0.18, 0.18, 0.55), loc=(0, 0, -0.28),
             parent=l_sh, mat_=M_ROBE)
l_el = empty("witch_l_el", (0, 0, -0.58), parent=l_sh)
l_el.rotation_euler = (math.radians(45), 0, 0)
beveled_cube("witch_l_fa", (0.16, 0.16, 0.50), loc=(0, 0, -0.25),
             parent=l_el, mat_=M_ROBE)
# Left hand (open, fingers spread)
l_hand = empty("witch_l_hand", (0, 0, -0.55), parent=l_el)
smooth_sphere("witch_l_hand_g", r=0.10, loc=(0, 0, 0),
              parent=l_hand, mat_=M_SKIN_GREEN)
for i in range(4):
    f = cyl(f"witch_l_finger{i}", r=0.025, depth=0.18, segs=8,
           loc=((i-1.5)*0.05, -0.10, -0.09), parent=l_hand, mat_=M_SKIN_GREEN)
    f.rotation_euler = (math.radians(30 + i*5), 0, math.radians((i-1.5)*5))

# ============ TABLE (alchemy table) ============
table_base = empty("table", loc=(3.5, -1.5, 0))
table_base.rotation_euler = (0, 0, math.radians(-20))
# Top
beveled_cube("table_top", (1.8, 1.0, 0.08), bevel_offset=0.04,
             loc=(0, 0, 1.0), parent=table_base, mat_=M_TABLE)
# 4 legs
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"table_leg_{x_idx}_{y_idx}", r=0.07, depth=1.0, segs=10,
            loc=(x*0.78, y*0.40, 0.5), parent=table_base, mat_=M_TABLE)

# 12 FIOLES on table (4×3 grid)
vials = []
for i in range(12):
    col = i % 4
    row = i // 4
    vx = (col - 1.5) * 0.35
    vy = (row - 1) * 0.30
    vial_e = empty(f"vial_e{i}", (vx, vy, 1.30), parent=table_base)
    # Glass bottle
    smooth_sphere(f"vial_body{i}", r=0.10, loc=(0, 0, 0.05),
                  parent=vial_e, mat_=M_VIAL_GLASS, scale=(1, 1, 1.5))
    # Liquid inside (colored)
    color = VIAL_COLORS[i % 6]
    smooth_sphere(f"vial_liquid{i}", r=0.08, loc=(0, 0, 0.02),
                  parent=vial_e, mat_=color, scale=(1, 1, 1.2))
    # Neck
    cyl(f"vial_neck{i}", r=0.035, depth=0.10, segs=10,
        loc=(0, 0, 0.20), parent=vial_e, mat_=M_VIAL_GLASS)
    # Cork
    cyl(f"vial_cork{i}", r=0.045, depth=0.06, segs=10,
        loc=(0, 0, 0.28), parent=vial_e, mat_=M_VIAL_CORK)
    vial_e["_phase"] = random.uniform(0, math.pi*2)
    vials.append(vial_e)

# GRIMOIRE ouvert on table
grim_base = empty("grimoire", loc=(0.5, 0.40, 1.05), parent=table_base)
grim_base.rotation_euler = (0, 0, math.radians(15))
# Open book: 2 pages tilted
for side_idx, side in enumerate((-1, 1)):
    page = beveled_cube(f"book_page_{side_idx}", (0.30, 0.40, 0.025), bevel_offset=0.02,
                       loc=(side*0.16, 0, 0.02), parent=grim_base, mat_=M_BOOK_PAGES)
    page.rotation_euler = (0, math.radians(side*6), 0)
    # Ink scribbles on page
    for j in range(3):
        beveled_cube(f"ink_{side_idx}_{j}", (0.20, 0.025, 0.005),
                     loc=(side*0.16, -0.15 + j*0.15, 0.04), parent=grim_base, mat_=M_INK)
# Spine
beveled_cube("book_spine", (0.04, 0.40, 0.06), loc=(0, 0, 0.03),
             parent=grim_base, mat_=M_BOOK_COVER)

# SKULL decoration
skull_e = empty("skull", (0.65, -0.30, 1.10), parent=table_base)
skull_e.rotation_euler = (math.radians(15), 0, math.radians(25))
smooth_sphere("skull_cranium", r=0.16, segs=20, rings=14,
              loc=(0, 0, 0.10), parent=skull_e, mat_=M_SKULL,
              scale=(1, 1.2, 1))
# Eye sockets
for side in (-1, 1):
    smooth_sphere(f"skull_eye_{side}", r=0.04,
                  loc=(side*0.06, -0.13, 0.10), parent=skull_e, mat_=M_HAIR_BLACK)
# Jaw
beveled_cube("skull_jaw", (0.16, 0.10, 0.06), loc=(0, -0.05, -0.05),
             parent=skull_e, mat_=M_SKULL)
# Teeth
for i in range(5):
    cyl(f"skull_tooth{i}", r=0.012, depth=0.05, segs=6,
        loc=((i-2)*0.025, -0.06, -0.05), parent=skull_e, mat_=M_MUSH_DOT)

# ============ BLACK CAT ============
cat_base = empty("cat", loc=(2.2, 0.8, 0))
cat_base.rotation_euler = (0, 0, math.radians(-60))
# Body (curled sitting)
cat_body = smooth_sphere("cat_body", r=0.30, segs=24, rings=16,
                          loc=(0, 0, 0.30), parent=cat_base, mat_=M_CAT_BLACK,
                          scale=(1.0, 1.5, 0.9))
# Front legs (sitting)
for side in (-1, 1):
    cyl(f"cat_fleg_{side}", r=0.06, depth=0.30, segs=10,
        loc=(side*0.10, -0.35, 0.15), parent=cat_base, mat_=M_CAT_BLACK)
# Back haunches
for side in (-1, 1):
    smooth_sphere(f"cat_haunch_{side}", r=0.16,
                  loc=(side*0.18, 0.20, 0.18),
                  parent=cat_base, mat_=M_CAT_BLACK, scale=(1, 1.3, 1))
# Head
cat_head = empty("cat_head", (0, -0.40, 0.55), parent=cat_base)
smooth_sphere("cat_h", r=0.20, segs=20, rings=14, loc=(0, 0, 0),
              parent=cat_head, mat_=M_CAT_BLACK, scale=(1, 0.9, 0.9))
# Triangular ears
for side in (-1, 1):
    ear = smooth_cone(f"cat_ear_{side}", r1=0.07, r2=0.005, depth=0.18, segs=8,
                     loc=(side*0.13, 0.05, 0.18), parent=cat_head, mat_=M_CAT_BLACK)
    ear.rotation_euler = (math.radians(-10), math.radians(side*15), 0)
    # Inner ear pink
    smooth_cone(f"cat_ear_in_{side}", r1=0.04, r2=0.005, depth=0.10, segs=6,
                loc=(side*0.13, 0.06, 0.16), parent=cat_head, mat_=M_CAT_PINK)
# Eyes (yellow glowing)
for side in (-1, 1):
    smooth_sphere(f"cat_eye_{side}", r=0.06,
                  loc=(side*0.07, -0.16, 0.04), parent=cat_head, mat_=M_CAT_EYES)
    # Pupil vertical slit
    beveled_cube(f"cat_pup_{side}", (0.018, 0.005, 0.06),
                 loc=(side*0.07, -0.20, 0.04), parent=cat_head, mat_=M_HAIR_BLACK)
# Nose
smooth_sphere("cat_nose", r=0.025, loc=(0, -0.20, -0.05),
              parent=cat_head, mat_=M_CAT_PINK)
# Whiskers (3 each side)
for side in (-1, 1):
    for i in range(3):
        beveled_cube(f"cat_whisk_{side}_{i}", (0.18, 0.008, 0.005),
                     loc=(side*0.20, -0.18, -0.04 + (i-1)*0.04),
                     parent=cat_head, mat_=M_MUSH_DOT)
# TAIL (curled - 5 segments)
tail_e = empty("cat_tail_e", (0, 0.35, 0.30), parent=cat_base)
for i in range(5):
    tseg = cyl(f"cat_tail{i}", r=0.045 - i*0.005, depth=0.20, segs=10,
              loc=(0, 0.20*i, 0.10 + i*0.06), parent=tail_e, mat_=M_CAT_BLACK)
    tseg.rotation_euler = (math.radians(i*10), 0, math.radians(i*8))

# ============ BROOM hovering ============
broom_base = empty("broom", loc=(4.8, 2.5, 1.2))
broom_base.rotation_euler = (math.radians(-15), 0, math.radians(30))
# Handle long
cyl("broom_handle", r=0.05, depth=2.5, segs=12,
    loc=(0, 0, 0), parent=broom_base, mat_=M_BROOM_HANDLE)
# Bristles (12 cones flaring from one end)
bristle_e = empty("bristle_e", (0, 0, -1.4), parent=broom_base)
for i in range(12):
    a = (i / 12.0) * math.pi * 2
    bris = smooth_cone(f"bristle{i}", r1=0.06, r2=0.01, depth=0.55, segs=8,
                      loc=(0.10*math.cos(a), 0.10*math.sin(a), -0.30),
                      parent=bristle_e, mat_=M_BROOM_BRISTLE)
    bris.rotation_euler = (math.radians(-10*math.cos(a)),
                           math.radians(-10*math.sin(a)), 0)
# Bindings
cyl("broom_bind1", r=0.10, depth=0.08, segs=14,
    loc=(0, 0, -1.10), parent=broom_base, mat_=M_BROOM_BIND)
cyl("broom_bind2", r=0.09, depth=0.06, segs=14,
    loc=(0, 0, -1.25), parent=broom_base, mat_=M_BROOM_BIND)

# ============ MUSHROOMS (12 fly agaric) ============
mushrooms = []
for i in range(12):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 8)
    mx = rad * math.cos(a)
    my = rad * math.sin(a)
    m_e = empty(f"mush_e{i}", (mx, my, 0))
    # Stem
    h = random.uniform(0.30, 0.55)
    cyl(f"mush_stem{i}", r=random.uniform(0.06, 0.10), depth=h, segs=10,
        loc=(0, 0, h/2), parent=m_e, mat_=M_MUSH_STEM)
    # Cap (red with white dots)
    cap_r = random.uniform(0.20, 0.35)
    smooth_sphere(f"mush_cap{i}", r=cap_r, segs=18, rings=10,
                  loc=(0, 0, h+0.05), parent=m_e, mat_=M_MUSH_RED,
                  scale=(1, 1, 0.55))
    # 5 white dots on cap
    for j in range(5):
        da = (j / 5.0) * math.pi * 2
        smooth_sphere(f"mush_dot{i}_{j}", r=cap_r*0.18,
                      loc=(cap_r*0.6*math.cos(da), cap_r*0.6*math.sin(da), h+0.10),
                      parent=m_e, mat_=M_MUSH_DOT, scale=(1, 1, 0.3))
    mushrooms.append(m_e)

# ============ 50 LUCIOLES (fireflies) drift ============
fireflies = []
for i in range(50):
    fx = random.uniform(-12, 12)
    fy = random.uniform(-12, 12)
    fz = random.uniform(1.0, 6.0)
    ff = smooth_sphere(f"firefly{i}", r=0.06, segs=10, rings=8,
                      loc=(fx, fy, fz), mat_=M_FIREFLY)
    ff["_phase"] = random.uniform(0, math.pi*2)
    ff["_base_x"] = fx
    ff["_base_y"] = fy
    ff["_base_z"] = fz
    ff["_speed_x"] = random.uniform(0.5, 1.5)
    ff["_speed_y"] = random.uniform(0.5, 1.5)
    ff["_speed_z"] = random.uniform(0.3, 0.8)
    fireflies.append(ff)

# ============ OWL on tree branch ============
owl_e = empty("owl", loc=(-13, 3, 5.5))
owl_e.rotation_euler = (0, 0, math.radians(-30))
# Body (round)
smooth_sphere("owl_body", r=0.40, segs=24, rings=16, loc=(0, 0, 0),
              parent=owl_e, mat_=M_OWL, scale=(1, 0.85, 1.3))
# Belly lighter
smooth_sphere("owl_belly", r=0.30, loc=(0, -0.15, -0.05),
              parent=owl_e, mat_=M_OWL_BELLY, scale=(1, 0.4, 1))
# Head
owl_head = empty("owl_head_e", (0, 0, 0.50), parent=owl_e)
smooth_sphere("owl_h", r=0.30, segs=22, rings=14, loc=(0, 0, 0),
              parent=owl_head, mat_=M_OWL)
# Ear tufts
for side in (-1, 1):
    tuft = smooth_cone(f"owl_tuft_{side}", r1=0.06, r2=0.01, depth=0.15, segs=8,
                      loc=(side*0.20, 0.05, 0.22), parent=owl_head, mat_=M_OWL)
    tuft.rotation_euler = (math.radians(-15), 0, math.radians(side*15))
# Big eyes (huge yellow)
for side in (-1, 1):
    smooth_sphere(f"owl_eye_disc_{side}", r=0.14,
                  loc=(side*0.13, -0.18, 0.03), parent=owl_head, mat_=M_OWL_BELLY)
    smooth_sphere(f"owl_eye_{side}", r=0.12,
                  loc=(side*0.13, -0.23, 0.03), parent=owl_head, mat_=M_OWL_EYES)
    smooth_sphere(f"owl_pup_{side}", r=0.05,
                  loc=(side*0.13, -0.30, 0.03), parent=owl_head, mat_=M_HAIR_BLACK)
# Beak
smooth_cone("owl_beak", r1=0.06, r2=0.015, depth=0.10, segs=10,
            loc=(0, -0.28, -0.08), parent=owl_head, mat_=M_BEAK)
# Wings folded
for side in (-1, 1):
    wing = beveled_cube(f"owl_wing_{side}", (0.18, 0.10, 0.45), bevel_offset=0.04,
                        loc=(side*0.35, 0, -0.05), parent=owl_e, mat_=M_OWL)
    wing.rotation_euler = (0, math.radians(side*8), 0)
# Feet
for side in (-1, 1):
    cyl(f"owl_foot_{side}", r=0.04, depth=0.15, segs=8,
        loc=(side*0.10, 0.05, -0.55), parent=owl_e, mat_=M_BEAK)
# Branch (owl perched on)
branch = cyl("owl_branch", r=0.12, depth=1.2, segs=12,
              loc=(0, 0.3, -0.7), parent=owl_e, mat_=M_TRUNK_DARK)
branch.rotation_euler = (math.radians(90), 0, 0)

# ============ 5 RAVENS flying ============
ravens = []
for i in range(5):
    a = (i / 5.0) * math.pi * 2 + random.uniform(-0.1, 0.1)
    rad = random.uniform(10, 14)
    rx = rad * math.cos(a)
    ry = rad * math.sin(a)
    rz = random.uniform(6, 10)
    rav_e = empty(f"raven_e{i}", (rx, ry, rz))
    rav_e.rotation_euler = (0, 0, a + math.pi/2)
    # Body
    smooth_sphere(f"raven_body{i}", r=0.16, segs=18, rings=12,
                  loc=(0, 0, 0), parent=rav_e, mat_=M_RAVEN, scale=(2.0, 0.8, 0.8))
    # Head
    smooth_sphere(f"raven_h{i}", r=0.10, loc=(0.25, 0, 0.05),
                  parent=rav_e, mat_=M_RAVEN)
    # Beak
    smooth_cone(f"raven_bk{i}", r1=0.035, r2=0.005, depth=0.12, segs=8,
                loc=(0.36, 0, 0.02), parent=rav_e, mat_=M_RAVEN_BEAK)
    # Eye
    smooth_sphere(f"raven_eye{i}", r=0.025, loc=(0.30, -0.07, 0.07),
                  parent=rav_e, mat_=M_RAVEN_EYE)
    # Wings (outstretched 2-seg per side)
    raven_wings = []
    for side in (-1, 1):
        w_e = empty(f"raven_w_e{i}_{side}", (0, side*0.12, 0), parent=rav_e)
        beveled_cube(f"raven_w{i}_{side}", (0.18, 0.55, 0.04), bevel_offset=0.02,
                     loc=(0, side*0.28, 0), parent=w_e, mat_=M_RAVEN)
        # tip
        beveled_cube(f"raven_wt{i}_{side}", (0.12, 0.20, 0.03),
                     loc=(0, side*0.58, 0), parent=w_e, mat_=M_RAVEN)
        raven_wings.append((w_e, side))
    # Tail
    beveled_cube(f"raven_t{i}", (0.10, 0.18, 0.03),
                 loc=(-0.28, 0, 0), parent=rav_e, mat_=M_RAVEN)
    ravens.append({"e": rav_e, "wings": raven_wings, "phase": random.uniform(0, math.pi*2),
                   "orbit_radius": rad, "orbit_speed": random.uniform(0.4, 0.7),
                   "orbit_phase": a, "base_z": rz})

# ============ ANIMATION ============
fps = 30
duration_s = 6
total_frames = fps * duration_s

# Stars twinkle
for i, star in enumerate(stars):
    phase = star["_phase"]
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.5 + phase) * 0.40
        star.scale = (s, s, s)
        star.keyframe_insert("scale", frame=f)

# Bubbles rise (Z up + wobble + scale)
for bub in bubbles:
    if "_phase" not in bub.keys():
        continue
    phase = bub["_phase"]
    base_x = bub["_base_x"]
    base_y = bub["_base_y"]
    base_z = bub["_base_z"]
    speed = bub["_speed"]
    base_r = bub["_base_r"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Loop rise
        z = base_z + ((speed * t) % 2.0)
        x = base_x + math.sin(t * 3.0 + phase) * 0.08
        y = base_y + math.cos(t * 2.5 + phase) * 0.08
        bub.location = (x, y, z)
        s = 1 + math.sin(t * 4.0 + phase) * 0.15
        bub.scale = (s, s, s)
        bub.keyframe_insert("location", frame=f)
        bub.keyframe_insert("scale", frame=f)

# Steam drift up
for steam in steams:
    if "_phase" not in steam.keys():
        continue
    phase = steam["_phase"]
    base_x = steam.location.x
    base_y = steam.location.y
    base_z = steam.location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        z = base_z + ((0.8 * t) % 3.0)
        x = base_x + math.sin(t * 0.8 + phase) * 0.3
        y = base_y + math.cos(t * 0.7 + phase) * 0.3
        s = 1 + math.sin(t * 1.0 + phase) * 0.15
        steam.location = (x, y, z)
        steam.scale = (s, s, s)
        steam.keyframe_insert("location", frame=f)
        steam.keyframe_insert("scale", frame=f)

# Potion surface pulse
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    s = 1.05 + math.sin(t * 2.5) * 0.03
    potion_surf.scale = (s, s, 0.06 + math.sin(t * 2.5) * 0.02)
    potion_surf.keyframe_insert("scale", frame=f)

# Flames pulse (outer + inner différentielles)
for outer, inner in flames:
    p_o = outer["_phase"]
    p_i = inner["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s_o = 1 + math.sin(t * 6.0 + p_o) * 0.25
        outer.scale = (s_o, s_o, s_o)
        outer.keyframe_insert("scale", frame=f)
        s_i = 1 + math.sin(t * 8.0 + p_i) * 0.30
        inner.scale = (s_i, s_i, s_i)
        inner.keyframe_insert("scale", frame=f)

# Embers flicker
for ember in embers:
    phase = ember["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 5.0 + phase) * 0.40
        ember.scale = (s, s, s)
        ember.keyframe_insert("scale", frame=f)

# Witch incantation (head sway + arm gesture)
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    head_e.rotation_euler = (
        math.sin(t * 1.5) * math.radians(8),
        math.sin(t * 1.2 + 0.5) * math.radians(5),
        0,
    )
    head_e.keyframe_insert("rotation_euler", frame=f)
    # Left arm gesture
    l_sh.rotation_euler = (
        math.radians(-90) + math.sin(t * 2.0) * math.radians(15),
        math.radians(-25) + math.sin(t * 1.5 + 0.3) * math.radians(8),
        math.radians(30) + math.sin(t * 1.0) * math.radians(10),
    )
    l_sh.keyframe_insert("rotation_euler", frame=f)
    # Right arm with staff (smaller motion)
    r_sh.rotation_euler = (
        math.radians(-50) + math.sin(t * 1.5 + 1.0) * math.radians(8),
        math.radians(20),
        math.radians(-30) + math.sin(t * 1.2) * math.radians(5),
    )
    r_sh.keyframe_insert("rotation_euler", frame=f)

# Staff orb pulse (scale + rotation around)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 3.5) * 0.15
    staff_orb.scale = (s, s, s)
    staff_orb.keyframe_insert("scale", frame=f)
    staff_e.rotation_euler = (0, 0, t * 0.5)
    staff_e.keyframe_insert("rotation_euler", frame=f)

# Cat tail wave + head tilt
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    tail_e.rotation_euler = (
        0,
        math.sin(t * 1.5) * math.radians(15),
        math.sin(t * 1.2) * math.radians(20),
    )
    tail_e.keyframe_insert("rotation_euler", frame=f)
    cat_head.rotation_euler = (
        math.sin(t * 0.8) * math.radians(8),
        0,
        math.sin(t * 1.0) * math.radians(15),
    )
    cat_head.keyframe_insert("rotation_euler", frame=f)

# Broom hover bob + rotate
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    broom_base.location.z = 1.2 + math.sin(t * 1.8) * 0.10
    broom_base.rotation_euler = (
        math.radians(-15) + math.sin(t * 1.5) * math.radians(5),
        math.sin(t * 1.2) * math.radians(3),
        math.radians(30) + math.sin(t * 0.8) * math.radians(8),
    )
    broom_base.keyframe_insert("location", frame=f)
    broom_base.keyframe_insert("rotation_euler", frame=f)

# Vials glow différentielles (scale pulse)
for vial in vials:
    if "_phase" not in vial.keys():
        continue
    phase = vial["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.0 + phase) * 0.05
        vial.scale = (s, s, s)
        vial.keyframe_insert("scale", frame=f)

# Fireflies drift 3D
for ff in fireflies:
    phase = ff["_phase"]
    base_x = ff["_base_x"]
    base_y = ff["_base_y"]
    base_z = ff["_base_z"]
    sx = ff["_speed_x"]
    sy = ff["_speed_y"]
    sz = ff["_speed_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = base_x + math.sin(t * sx + phase) * 2.5
        y = base_y + math.cos(t * sy + phase) * 2.5
        z = base_z + math.sin(t * sz + phase) * 1.5
        ff.location = (x, y, z)
        s = 1 + math.sin(t * 5.0 + phase) * 0.3  # twinkle
        ff.scale = (s, s, s)
        ff.keyframe_insert("location", frame=f)
        ff.keyframe_insert("scale", frame=f)

# Owl head rotate slowly
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    owl_head.rotation_euler = (0, 0, math.sin(t * 0.8) * math.radians(60))
    owl_head.keyframe_insert("rotation_euler", frame=f)

# Ravens flap + orbit
for rav in ravens:
    phase = rav["phase"]
    rad = rav["orbit_radius"]
    speed = rav["orbit_speed"]
    base_phase = rav["orbit_phase"]
    base_z = rav["base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Flap
        flap = math.sin(t * 6.0 + phase) * math.radians(45)
        for w_e, side in rav["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)
        # Orbit
        a = base_phase + speed * t
        x = rad * math.cos(a)
        y = rad * math.sin(a)
        z = base_z + math.sin(t * 1.5 + phase) * 0.6
        rav["e"].location = (x, y, z)
        rav["e"].rotation_euler = (0, 0, a + math.pi/2)
        rav["e"].keyframe_insert("location", frame=f)
        rav["e"].keyframe_insert("rotation_euler", frame=f)

# Fog layers drift
for fog in fog_layers:
    phase = fog["_phase"]
    base_x = fog.location.x
    base_y = fog.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        fog.location.x = base_x + math.sin(t * 0.4 + phase) * 0.6
        fog.location.y = base_y + math.cos(t * 0.3 + phase) * 0.5
        s = 1 + math.sin(t * 0.5 + phase) * 0.1
        fog.scale = (1.2*s, 1.0*s, 0.08)
        fog.keyframe_insert("location", frame=f)
        fog.keyframe_insert("scale", frame=f)

# Moon breathe
for f in range(1, total_frames + 1, 8):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 0.6) * 0.03
    moon.scale = (s, s, s)
    moon.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_witch_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
    export_yup=True,
    use_selection=False,
)

size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_witch_potion_brewing] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_witch_potion_brewing] Witch full anatomy + cauldron + 30 bubbles + 10 steam + fire 6 flames + cat + broom hover + table + grimoire + 12 vials + skull + 8 twisted trees + 12 mushrooms + 50 fireflies + owl head rotate + 5 ravens orbit + moon + 60 stars + fog")
