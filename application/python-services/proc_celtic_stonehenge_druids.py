"""
proc_celtic_stonehenge_druids.py — 225e procédural AuroraIA (89e qualité)
Celtic Stonehenge: ONE ground + 30 monoliths + central altar + 7 druids + archdruid + 8 women harp + 5 dolmens + 100 runes + 4 deer + 3 ravens + falcon + aurora + 600 magical sparkles + 300 mist
FIXES : 1 ground + 600 magical sparkles + 300 mist thématiques signature celtic ritual
"""
import bpy, bmesh, math, random, os

random.seed(0xCE17225)

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

# Celtic mystical night palette
M_SKY = mat("sky", (0.10, 0.08, 0.30, 1.0), 0.0, 0.7, emission=(0.10,0.08,0.30), emission_strength=1.5)
M_MOON = mat("moon", (0.98, 0.95, 0.90, 1.0), 0.0, 0.20, emission=(0.98,0.95,0.90), emission_strength=14.0)
M_STAR = mat("star", (1.0, 1.0, 0.95, 1.0), 0.0, 0.20, emission=(1.0,1.0,0.95), emission_strength=10.0)
M_AURORA_GREEN = mat("aurora_g", (0.20, 0.95, 0.55, 1.0), 0.0, 0.20, emission=(0.20,0.95,0.55), emission_strength=8.0, alpha=0.65)
M_AURORA_BLUE = mat("aurora_b", (0.20, 0.55, 0.95, 1.0), 0.0, 0.20, emission=(0.20,0.55,0.95), emission_strength=7.5, alpha=0.65)
M_AURORA_PURPLE = mat("aurora_p", (0.65, 0.30, 0.95, 1.0), 0.0, 0.20, emission=(0.65,0.30,0.95), emission_strength=8.0, alpha=0.65)

# Ground grass + earth
M_GRASS = mat("grass", (0.18, 0.32, 0.18, 1.0), 0.0, 0.85, emission=(0.15,0.28,0.15), emission_strength=0.3)
M_GRASS_BRIGHT = mat("grass_b", (0.25, 0.45, 0.22, 1.0), 0.0, 0.80, emission=(0.22,0.40,0.20), emission_strength=0.5)
M_MOSS = mat("moss", (0.20, 0.50, 0.25, 1.0), 0.0, 0.75, emission=(0.18,0.45,0.22), emission_strength=0.5)
M_ROCK = mat("rock", (0.45, 0.42, 0.40, 1.0), 0.0, 0.85)

# Stonehenge stones
M_STONE_OLD = mat("stone_o", (0.55, 0.52, 0.48, 1.0), 0.0, 0.85, emission=(0.50,0.48,0.45), emission_strength=0.4)
M_STONE_WEATHERED = mat("stone_w", (0.48, 0.45, 0.40, 1.0), 0.0, 0.85, emission=(0.45,0.42,0.38), emission_strength=0.35)
M_STONE_DARK = mat("stone_d", (0.35, 0.32, 0.28, 1.0), 0.0, 0.85)

# Runes (signature glowing celtic spiral)
M_RUNE_BLUE = mat("rune_b", (0.30, 0.65, 1.0, 1.0), 0.0, 0.15, emission=(0.30,0.65,1.0), emission_strength=18.0)
M_RUNE_GREEN = mat("rune_g", (0.30, 1.0, 0.55, 1.0), 0.0, 0.15, emission=(0.30,1.0,0.55), emission_strength=18.0)
M_RUNE_PURPLE = mat("rune_p", (0.85, 0.30, 1.0, 1.0), 0.0, 0.15, emission=(0.85,0.30,1.0), emission_strength=16.0)

# Druids
M_SKIN_DRUID = mat("skin", (0.92, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.85,0.72,0.62), emission_strength=0.4)
M_ROBE_WHITE = mat("robe_w", (0.92, 0.90, 0.85, 1.0), 0.0, 0.70, emission=(0.85,0.82,0.78), emission_strength=0.6)
M_ROBE_GREEN = mat("robe_g", (0.20, 0.45, 0.25, 1.0), 0.0, 0.70, emission=(0.18,0.42,0.22), emission_strength=0.5)
M_ROBE_BLUE = mat("robe_b", (0.25, 0.40, 0.62, 1.0), 0.0, 0.65, emission=(0.22,0.38,0.58), emission_strength=0.5)
M_BEARD_WHITE = mat("beard_w", (0.92, 0.90, 0.88, 1.0), 0.0, 0.65, emission=(0.85,0.82,0.80), emission_strength=0.4)
M_BEARD_GRAY = mat("beard_g", (0.65, 0.62, 0.58, 1.0), 0.0, 0.75, emission=(0.60,0.58,0.55), emission_strength=0.4)
M_HAIR_RED = mat("hair_r", (0.78, 0.42, 0.18, 1.0), 0.0, 0.65, emission=(0.72,0.40,0.18), emission_strength=0.5)
M_HAIR_RED_DEEP = mat("hair_rd", (0.65, 0.30, 0.12, 1.0), 0.0, 0.75)
M_GREEN_DRESS = mat("green_d", (0.30, 0.55, 0.25, 1.0), 0.0, 0.60, emission=(0.28,0.50,0.22), emission_strength=0.6)
M_BLUE_DRESS = mat("blue_d", (0.20, 0.40, 0.65, 1.0), 0.0, 0.60, emission=(0.18,0.38,0.60), emission_strength=0.6)
M_TATTOO_BLUE = mat("tattoo", (0.10, 0.55, 0.85, 1.0), 0.0, 0.30, emission=(0.10,0.55,0.85), emission_strength=2.5)

# Druid accessories
M_MISTLETOE = mat("misletoe", (0.30, 0.65, 0.30, 1.0), 0.0, 0.55, emission=(0.28,0.60,0.28), emission_strength=1.5)
M_MISTLETOE_BERRY = mat("misletoe_b", (0.95, 0.95, 0.90, 1.0), 0.0, 0.45, emission=(0.88,0.88,0.85), emission_strength=1.0)
M_GOLD_CROWN = mat("gold_c", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.92,0.78,0.28), emission_strength=1.5)
M_OAK_STAFF = mat("oak", (0.45, 0.28, 0.15, 1.0), 0.0, 0.80)
M_CRYSTAL = mat("crystal", (0.85, 0.92, 1.0, 0.75), 0.4, 0.10, emission=(0.85,0.92,1.0), emission_strength=4.0, alpha=0.75)

# Harp + Lyre
M_HARP_WOOD = mat("harp_w", (0.55, 0.30, 0.15, 1.0), 0.0, 0.60, emission=(0.50,0.28,0.13), emission_strength=0.5)
M_HARP_GOLD = mat("harp_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.20, emission=(0.92,0.75,0.28), emission_strength=1.2)
M_STRING = mat("string", (0.85, 0.85, 0.92, 1.0), 0.8, 0.20, emission=(0.78,0.78,0.85), emission_strength=0.4)

# Deer (signature majestic stag)
M_DEER_BROWN = mat("deer_b", (0.45, 0.30, 0.18, 1.0), 0.0, 0.75, emission=(0.42,0.28,0.16), emission_strength=0.3)
M_DEER_BELLY = mat("deer_bl", (0.78, 0.62, 0.45, 1.0), 0.0, 0.65, emission=(0.72,0.58,0.42), emission_strength=0.3)
M_ANTLER = mat("antler", (0.85, 0.75, 0.55, 1.0), 0.2, 0.55, emission=(0.78,0.70,0.50), emission_strength=0.4)
M_DEER_EYE = mat("deer_e", (0.20, 0.10, 0.05, 1.0), 0.0, 0.40, emission=(0.18,0.08,0.05), emission_strength=2.0)

# Ravens + falcon
M_RAVEN = mat("raven", (0.05, 0.04, 0.06, 1.0), 0.3, 0.45, emission=(0.05,0.04,0.06), emission_strength=0.3)
M_RAVEN_EYE = mat("raven_e", (1.0, 0.85, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.20), emission_strength=8.0)
M_FALCON_BODY = mat("falcon", (0.55, 0.42, 0.25, 1.0), 0.0, 0.65, emission=(0.50,0.40,0.22), emission_strength=0.4)
M_FALCON_HEAD = mat("falcon_h", (0.92, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.60), emission_strength=0.5)
M_FALCON_BEAK = mat("falcon_b", (1.0, 0.65, 0.20, 1.0), 0.5, 0.40, emission=(0.95,0.62,0.18), emission_strength=0.7)

# Magical sparkles + mist
M_SPARK_GREEN = mat("sp_g", (0.30, 1.0, 0.55, 1.0), 0.0, 0.10, emission=(0.30,1.0,0.55), emission_strength=20.0)
M_SPARK_BLUE = mat("sp_b", (0.30, 0.65, 1.0, 1.0), 0.0, 0.10, emission=(0.30,0.65,1.0), emission_strength=20.0)
M_SPARK_PURPLE = mat("sp_p", (0.85, 0.30, 1.0, 1.0), 0.0, 0.10, emission=(0.85,0.30,1.0), emission_strength=20.0)
M_SPARK_GOLD = mat("sp_go", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.30), emission_strength=22.0)

M_MIST = mat("mist", (0.55, 0.78, 0.85, 1.0), 0.0, 0.30, emission=(0.55,0.78,0.85), emission_strength=2.5, alpha=0.55)
M_MIST_GREEN = mat("mist_g", (0.40, 0.85, 0.55, 1.0), 0.0, 0.30, emission=(0.40,0.85,0.55), emission_strength=2.8, alpha=0.55)

# ============ SKY + MOON + STARS + AURORA ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
moon_e = empty("moon_e", (-25, 50, 38))
smooth_sphere("moon", r=5.0, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)
for i in range(3):
    smooth_sphere(f"moon_halo{i}", r=5.0 + (i+1)*1.5, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)

# Aurora ribbons
auroras = []
for i, col in enumerate((M_AURORA_GREEN, M_AURORA_BLUE, M_AURORA_PURPLE)):
    a_e = empty(f"aurora_e{i}", (0, 35, 30 + i*3))
    for s in range(8):
        seg_x = (s - 3.5) * 7
        seg_z = math.sin(s * 0.8) * 2
        beveled_cube(f"aurora_{i}_{s}", (7, 0.3, 5 + i), bevel_offset=0.1,
                     loc=(seg_x, 0, seg_z), parent=a_e, mat_=col)
    a_e["_phase"] = i * 0.5
    a_e.rotation_euler = (math.radians(10*i), 0, 0)
    auroras.append(a_e)

# 200 stars
for i in range(200):
    a = random.uniform(0, math.pi*2)
    phi = random.uniform(math.pi/6, math.pi/2.2)
    r_star = 115
    sx = r_star * math.cos(phi) * math.cos(a)
    sy = r_star * math.cos(phi) * math.sin(a)
    sz = r_star * math.sin(phi) * 0.4
    smooth_sphere(f"star{i}", r=random.uniform(0.20, 0.45), segs=10, rings=8,
                  loc=(sx, sy, sz), mat_=M_STAR)

# ============ ONE clean grass ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GRASS)
# Bright grass tufts
for i in range(50):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 42)
    smooth_sphere(f"tuft{i}", r=random.uniform(0.30, 0.60),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_GRASS_BRIGHT if i % 2 == 0 else M_MOSS,
                  scale=(1.4, 1.2, 0.20))
# Rocks scattered
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(15, 38)
    smooth_sphere(f"rock{i}", r=random.uniform(0.4, 1.0),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_ROCK,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.85)))

# ============ STONEHENGE CIRCLE (30 monoliths + trilithons) ============
stonehenge_radius = 12
# Outer ring - 30 standing stones
outer_stones = []
for i in range(30):
    a = (i / 30.0) * math.pi * 2
    sx = stonehenge_radius * math.cos(a)
    sy = stonehenge_radius * math.sin(a)
    stone_e = empty(f"stone{i}", (sx, sy, 0))
    stone_e.rotation_euler = (math.radians(random.uniform(-3, 3)),
                              math.radians(random.uniform(-3, 3)),
                              a)
    # Tall monolith (signature)
    beveled_cube(f"stone_b{i}", (1.5, 0.8, 5.5), bevel_offset=0.08,
                 loc=(0, 0, 2.75), parent=stone_e,
                 mat_=M_STONE_OLD if i % 2 == 0 else M_STONE_WEATHERED)
    # Slight irregular shape
    smooth_sphere(f"stone_irreg{i}", r=0.4, loc=(0, 0, 5.0),
                  parent=stone_e,
                  mat_=M_STONE_OLD if i % 2 == 0 else M_STONE_WEATHERED,
                  scale=(1.4, 0.7, 0.5))
    # Lintel (only every 2nd pair for trilithons - signature)
    if i % 2 == 0 and i < 30:
        next_a = ((i + 2) / 30.0) * math.pi * 2
        mid_a = (a + next_a) / 2
        mid_x = stonehenge_radius * math.cos(mid_a)
        mid_y = stonehenge_radius * math.sin(mid_a)
        lintel_dist = stonehenge_radius * 2 * math.sin(math.pi / 30)
        lintel = beveled_cube(f"lintel{i}", (lintel_dist * 1.05, 0.7, 0.8), bevel_offset=0.06,
                              loc=(mid_x, mid_y, 6.0),
                              mat_=M_STONE_WEATHERED)
        lintel.rotation_euler = (0, 0, mid_a + math.pi/2)
    outer_stones.append(stone_e)

# Inner ring (5 trilithons - tall horseshoe signature)
trilithon_radius = 6
for i in range(5):
    a = (i / 5.0) * math.pi - math.pi/2  # opening toward south
    if abs(a + math.pi/2) > math.pi * 0.8:  # skip back for U-shape opening
        continue
    tri_e = empty(f"tri{i}", (trilithon_radius * math.cos(a),
                               trilithon_radius * math.sin(a), 0))
    tri_e.rotation_euler = (0, 0, a + math.pi/2)
    # 2 tall stones
    for side in (-1, 1):
        beveled_cube(f"tri_st{i}_{side}", (1.0, 1.6, 7.5), bevel_offset=0.07,
                     loc=(side*1.0, 0, 3.75), parent=tri_e, mat_=M_STONE_OLD)
    # Lintel above
    beveled_cube(f"tri_lin{i}", (3.5, 1.6, 1.0), bevel_offset=0.06,
                 loc=(0, 0, 8.0), parent=tri_e, mat_=M_STONE_WEATHERED)

# ============ CENTRAL ALTAR STONE ============
altar_e = empty("altar", loc=(0, 0, 0))
# Massive altar stone (signature flat slab)
beveled_cube("alt_main", (3.0, 1.5, 1.0), bevel_offset=0.08, loc=(0, 0, 0.5),
             parent=altar_e, mat_=M_STONE_OLD)
# Glowing runes carved (signature)
for ri in range(8):
    rune_x = (ri - 3.5) * 0.35
    smooth_sphere(f"alt_rune{ri}", r=0.10,
                  loc=(rune_x, 0, 1.04), parent=altar_e,
                  mat_=M_RUNE_BLUE if ri % 3 == 0 else (M_RUNE_GREEN if ri % 3 == 1 else M_RUNE_PURPLE),
                  scale=(0.6, 0.6, 0.3))
# Mistletoe + crystal ball on altar
smooth_sphere("alt_crystal", r=0.25, loc=(0, 0, 1.30), parent=altar_e, mat_=M_CRYSTAL)
# Mistletoe wreath
for mi in range(8):
    ma = (mi / 8.0) * math.pi * 2
    smooth_sphere(f"misl{mi}", r=0.08, loc=(0.30*math.cos(ma), 0.30*math.sin(ma), 1.20),
                  parent=altar_e, mat_=M_MISTLETOE)
    smooth_sphere(f"misl_b{mi}", r=0.04, loc=(0.35*math.cos(ma), 0.35*math.sin(ma), 1.22),
                  parent=altar_e, mat_=M_MISTLETOE_BERRY)
# Floor circle (ground level glowing)
for ci in range(20):
    ca = (ci / 20.0) * math.pi * 2
    cyl(f"alt_floor_r{ci}", r=0.10, depth=0.04, segs=8,
        loc=(3.5*math.cos(ca), 3.5*math.sin(ca), 0.05),
        mat_=M_RUNE_BLUE if ci % 3 != 0 else M_RUNE_GREEN)

# ============ DRUIDS (6 + archdruid) ============
def make_druid(name, loc, robe_mat, hood=True, archdruid=False, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long robe cone
    smooth_cone(f"{name}_robe", r1=0.55*scale, r2=0.35*scale, depth=2.0*scale, segs=18,
                loc=(0, 0, 1.0*scale), parent=base, mat_=robe_mat)
    # Belt
    cyl(f"{name}_belt", r=0.42*scale, depth=0.08*scale, segs=14,
        loc=(0, 0, 1.55*scale), parent=base, mat_=M_OAK_STAFF)
    # Torso
    beveled_cube(f"{name}_torso", (0.42*scale, 0.25*scale, 0.55*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.95*scale), parent=base, mat_=robe_mat)
    # Neck
    cyl(f"{name}_neck", r=0.09*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 2.30*scale), parent=base, mat_=M_SKIN_DRUID)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.48*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_DRUID)
    # Long white/gray beard (signature druid)
    smooth_sphere(f"{name}_beard", r=0.20*scale, loc=(0, -0.15*scale, -0.20*scale),
                  parent=head_e,
                  mat_=M_BEARD_WHITE if archdruid else M_BEARD_GRAY,
                  scale=(1.1, 1.0, 1.4))
    # Beard strands
    for i in range(4):
        beveled_cube(f"{name}_b_str{i}", (0.08*scale, 0.06*scale, 0.40*scale),
                     loc=((i-1.5)*0.05*scale, -0.15*scale, -0.55*scale),
                     parent=head_e,
                     mat_=M_BEARD_WHITE if archdruid else M_BEARD_GRAY)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=M_RUNE_BLUE if archdruid else mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    if hood:
        # Hood
        smooth_sphere(f"{name}_hood", r=0.30*scale, loc=(0, 0.10*scale, 0.05*scale),
                      parent=head_e, mat_=robe_mat, scale=(1.15, 1.10, 1.05))
    else:
        # Hair (gray/white)
        smooth_sphere(f"{name}_hair", r=0.22*scale, loc=(0, 0.05*scale, 0.05*scale),
                      parent=head_e, mat_=M_BEARD_WHITE, scale=(1, 1, 0.9))
    # Crown for archdruid (signature mistletoe + gold)
    if archdruid:
        for ci in range(12):
            ca = (ci / 12.0) * math.pi * 2
            # Gold band
            leaf = beveled_cube(f"{name}_crown{ci}", (0.06*scale, 0.10*scale, 0.04*scale), bevel_offset=0.01,
                                loc=(0.22*scale*math.cos(ca), 0.22*scale*math.sin(ca), 0.18*scale),
                                parent=head_e, mat_=M_GOLD_CROWN)
            leaf.rotation_euler = (0, 0, ca)
        # Mistletoe sprigs in crown
        for mi in range(6):
            ma = (mi / 6.0) * math.pi * 2
            smooth_sphere(f"{name}_m{mi}", r=0.05*scale,
                          loc=(0.22*scale*math.cos(ma), 0.22*scale*math.sin(ma), 0.25*scale),
                          parent=head_e, mat_=M_MISTLETOE)
            smooth_sphere(f"{name}_mb{mi}", r=0.025*scale,
                          loc=(0.22*scale*math.cos(ma), 0.22*scale*math.sin(ma), 0.28*scale),
                          parent=head_e, mat_=M_MISTLETOE_BERRY)
    # Arms raised (chant pose)
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 2.20*scale), parent=base)
        sh.rotation_euler = (math.radians(-150), 0, math.radians(side*-30))
        # Long sleeve
        smooth_cone(f"{name}_sleeve{side_idx}", r1=0.16*scale, r2=0.10*scale, depth=0.55*scale, segs=12,
                    loc=(0, 0, -0.28*scale), parent=sh, mat_=robe_mat)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.65*scale), parent=sh, mat_=M_SKIN_DRUID)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08*scale, loc=(0, 0, -0.82*scale),
                      parent=sh, mat_=M_SKIN_DRUID)
        arms_e.append(sh)
    # Staff (oak with crystal top for archdruid)
    if archdruid:
        staff_e = empty(f"{name}_staff_e", (0.40*scale, 0, 1.5*scale), parent=base)
        staff_e.rotation_euler = (math.radians(-10), 0, 0)
        cyl(f"{name}_staff_shaft", r=0.04*scale, depth=3.0*scale, segs=10, loc=(0, 0, 0),
            parent=staff_e, mat_=M_OAK_STAFF)
        # Crystal top (signature)
        smooth_sphere(f"{name}_staff_crystal", r=0.15*scale, loc=(0, 0, 1.6*scale),
                      parent=staff_e, mat_=M_CRYSTAL)
        # Halo around crystal
        for hi in range(3):
            smooth_sphere(f"{name}_staff_h{hi}", r=0.15*scale + (hi+1)*0.05*scale,
                          loc=(0, 0, 1.6*scale), parent=staff_e, mat_=M_CRYSTAL)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

druids = []
# 6 druids around altar
druid_pos = [(-4, -2, 0), (4, -2, 0), (-3, 3, 0), (3, 3, 0), (0, -5, 0), (0, 5, 0)]
for i, (dx, dy, dz) in enumerate(druid_pos):
    fac = math.atan2(-dy, -dx) + math.pi
    d = make_druid(f"druid{i}", (dx, dy, dz), M_ROBE_WHITE, hood=True, archdruid=False, facing=fac)
    druids.append(d)
# Archdruid (center, taller)
archdruid = make_druid("archdruid", (4, 0, 0), M_ROBE_GREEN, hood=False, archdruid=True,
                        facing=math.radians(180), scale=1.15)
druids.append(archdruid)

# ============ 8 CELTIC WOMEN (red hair + harps/lyres) ============
def make_celt_woman(name, loc, dress_mat, instrument, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long dress
    smooth_cone(f"{name}_dress", r1=0.50, r2=0.35, depth=1.8, segs=18,
                loc=(0, 0, 0.90), parent=base, mat_=dress_mat)
    # Belt
    cyl(f"{name}_belt", r=0.38, depth=0.10, segs=14,
        loc=(0, 0, 1.40), parent=base, mat_=M_OAK_STAFF)
    # Torso
    beveled_cube(f"{name}_torso", (0.38, 0.22, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 1.80), parent=base, mat_=dress_mat)
    # Neck
    cyl(f"{name}_neck", r=0.09, depth=0.16, segs=10,
        loc=(0, 0, 2.15), parent=base, mat_=M_SKIN_DRUID)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.32), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_DRUID)
    # RED HAIR (signature celt - long flowing)
    smooth_sphere(f"{name}_hair_back", r=0.25, loc=(0, 0.08, -0.10),
                  parent=head_e, mat_=M_HAIR_RED, scale=(1.05, 1.0, 1.4))
    smooth_sphere(f"{name}_hair_top", r=0.20, loc=(0, 0.02, 0.06),
                  parent=head_e, mat_=M_HAIR_RED, scale=(1, 1, 0.85))
    # Hair strands flowing
    for hs in range(5):
        strand = beveled_cube(f"{name}_hs{hs}", (0.10, 0.06, 0.50),
                             loc=((hs-2)*0.07, 0.20, -0.40),
                             parent=head_e, mat_=M_HAIR_RED_DEEP)
        strand.rotation_euler = (math.radians(15), 0, 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.14, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.20, 0.55, 0.30, 1), 0, 0.5,
                                emission=(0.18,0.50,0.28), emission_strength=0.5))
    # Blue tattoo (signature woad - face)
    beveled_cube(f"{name}_tat_h", (0.20, 0.05, 0.02), loc=(0, -0.16, 0.10),
                 parent=head_e, mat_=M_TATTOO_BLUE)
    beveled_cube(f"{name}_tat_c", (0.04, 0.05, 0.18), loc=(0, -0.16, 0.04),
                 parent=head_e, mat_=M_TATTOO_BLUE)
    # Blue tattoo on arms (signature)
    for side in (-1, 1):
        for ti in range(2):
            cyl(f"{name}_arm_tat_{side}_{ti}", r=0.075, depth=0.04, segs=12,
                loc=(side*0.30, 0, 1.95 - ti*0.20), parent=base, mat_=M_TATTOO_BLUE)
    # Arms playing instrument
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 2.05), parent=base)
        if instrument == "harp":
            # Arms reaching forward
            sh.rotation_euler = (math.radians(-70 if side_idx == 0 else -90), 0,
                                  math.radians(side*-30))
        else:  # lyre
            sh.rotation_euler = (math.radians(-80), 0, math.radians(side*-25))
        cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.32, segs=10,
            loc=(0, 0, -0.16), parent=sh, mat_=M_SKIN_DRUID)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10,
            loc=(0, 0, -0.45), parent=sh, mat_=M_SKIN_DRUID)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07, loc=(0, 0, -0.62),
                      parent=sh, mat_=M_SKIN_DRUID)
        arms_e.append(sh)
    # Harp / Lyre
    inst_e = empty(f"{name}_inst_e", (0, -0.45, 1.10), parent=base)
    if instrument == "harp":
        # Triangle frame celtic harp (signature)
        # Soundboard
        beveled_cube(f"{name}_h_sb", (0.06, 0.30, 1.0), bevel_offset=0.02,
                     loc=(0, -0.05, 0.20), parent=inst_e, mat_=M_HARP_WOOD)
        # Top arm (curved)
        beveled_cube(f"{name}_h_top", (0.08, 0.06, 0.50), bevel_offset=0.02,
                     loc=(0, 0.30, 0.55), parent=inst_e, mat_=M_HARP_WOOD)
        # Neck
        beveled_cube(f"{name}_h_neck", (0.06, 0.55, 0.10), bevel_offset=0.02,
                     loc=(0, 0.13, 0.70), parent=inst_e, mat_=M_HARP_GOLD)
        # Strings
        for sti in range(8):
            sti_y = -0.05 + sti * 0.04
            cyl(f"{name}_h_str{sti}", r=0.003, depth=0.55, segs=4,
                loc=(0, sti_y, 0.45), parent=inst_e, mat_=M_STRING)
        # Gold ornament
        smooth_sphere(f"{name}_h_orn", r=0.07, loc=(0, 0.35, 0.75),
                      parent=inst_e, mat_=M_HARP_GOLD)
    else:  # lyre
        # U-shape frame
        beveled_cube(f"{name}_l_base", (0.30, 0.10, 0.08), bevel_offset=0.02,
                     loc=(0, 0, 0), parent=inst_e, mat_=M_HARP_WOOD)
        for side in (-1, 1):
            beveled_cube(f"{name}_l_arm{side}", (0.04, 0.04, 0.40),
                         loc=(side*0.13, 0, 0.20), parent=inst_e, mat_=M_HARP_WOOD)
        beveled_cube(f"{name}_l_top", (0.30, 0.04, 0.06),
                     loc=(0, 0, 0.40), parent=inst_e, mat_=M_HARP_GOLD)
        for sti in range(6):
            cyl(f"{name}_l_str{sti}", r=0.003, depth=0.40, segs=4,
                loc=((sti-2.5)*0.04, 0, 0.20), parent=inst_e, mat_=M_STRING)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

celt_women = []
celt_specs = [
    ("celtw1", (-8, 7, 0), M_GREEN_DRESS, "harp", math.radians(-30)),
    ("celtw2", (-9, 4, 0), M_BLUE_DRESS, "lyre", math.radians(-20)),
    ("celtw3", (-9, 0, 0), M_GREEN_DRESS, "harp", math.radians(0)),
    ("celtw4", (-8, -4, 0), M_BLUE_DRESS, "lyre", math.radians(30)),
    ("celtw5", (8, 7, 0), M_GREEN_DRESS, "harp", math.radians(-150)),
    ("celtw6", (9, 4, 0), M_BLUE_DRESS, "lyre", math.radians(-160)),
    ("celtw7", (9, 0, 0), M_GREEN_DRESS, "harp", math.radians(180)),
    ("celtw8", (8, -4, 0), M_BLUE_DRESS, "lyre", math.radians(150)),
]
for spec in celt_specs:
    name, loc, dress, inst, fac = spec
    w = make_celt_woman(name, loc, dress, inst, facing=fac)
    celt_women.append(w)

# ============ 5 OUTER DOLMENS ============
for i in range(5):
    a = (i / 5.0) * math.pi * 2 + math.pi / 5
    rad = 22
    dx = rad * math.cos(a)
    dy = rad * math.sin(a)
    d_e = empty(f"dolmen{i}", (dx, dy, 0))
    d_e.rotation_euler = (0, 0, a)
    # 3 standing stones + capstone (signature dolmen)
    for j in range(3):
        ja = (j / 3.0) * math.pi * 2
        beveled_cube(f"dol_st{i}_{j}", (0.6, 0.6, 2.0), bevel_offset=0.06,
                     loc=(0.8*math.cos(ja), 0.8*math.sin(ja), 1.0),
                     parent=d_e,
                     mat_=M_STONE_OLD if (i+j) % 2 == 0 else M_STONE_WEATHERED)
    # Capstone (large flat slab signature)
    beveled_cube(f"dol_cap{i}", (2.5, 2.5, 0.5), bevel_offset=0.08,
                 loc=(0, 0, 2.30), parent=d_e, mat_=M_STONE_DARK)
    # Glowing rune on capstone
    smooth_sphere(f"dol_rune{i}", r=0.18, loc=(0, 0, 2.60),
                  parent=d_e, mat_=M_RUNE_BLUE if i % 2 == 0 else M_RUNE_GREEN)

# ============ 100 RUNES on ground around stones (signature glowing circle) ============
runes_objs = []
for i in range(100):
    # Concentric rings of runes
    ring = i // 20  # 0-4
    pos_in_ring = i % 20
    ring_rad = 4 + ring * 1.8
    ra = (pos_in_ring / 20.0) * math.pi * 2
    rx = ring_rad * math.cos(ra)
    ry = ring_rad * math.sin(ra)
    rune_col = [M_RUNE_BLUE, M_RUNE_GREEN, M_RUNE_PURPLE][ring % 3]
    rune_obj = smooth_sphere(f"rune{i}", r=0.08, loc=(rx, ry, 0.05),
                              mat_=rune_col, scale=(0.6, 0.6, 0.20))
    rune_obj["_phase"] = random.uniform(0, math.pi*2)
    runes_objs.append(rune_obj)

# ============ 4 MAJESTIC STAGS ============
def make_stag(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.55, segs=20, rings=14, loc=(0, 0, 1.20),
                  parent=base, mat_=M_DEER_BROWN, scale=(1.7, 1, 1))
    # Belly
    smooth_sphere(f"{name}_belly", r=0.45, loc=(0, 0, 1.05),
                  parent=base, mat_=M_DEER_BELLY, scale=(1.5, 0.95, 0.7))
    # Neck (long graceful)
    neck = beveled_cube(f"{name}_neck", (0.30, 0.25, 0.85), bevel_offset=0.04,
                       loc=(0.85, 0, 1.50), parent=base, mat_=M_DEER_BROWN)
    neck.rotation_euler = (0, math.radians(-25), 0)
    # Head
    head_e = empty(f"{name}_he", (1.30, 0, 1.95), parent=base)
    beveled_cube(f"{name}_head", (0.40, 0.20, 0.30), bevel_offset=0.04,
                 loc=(0, 0, 0), parent=head_e, mat_=M_DEER_BROWN)
    # Muzzle
    smooth_cone(f"{name}_muzzle", r1=0.10, r2=0.07, depth=0.20, segs=12,
                loc=(0.22, 0, -0.05), parent=head_e,
                mat_=M_DEER_BROWN).rotation_euler = (0, math.radians(90), 0)
    # Eyes (glowing)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.05,
                      loc=(0.05, side*0.12, 0.08), parent=head_e, mat_=M_DEER_EYE)
    # Ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.06, r2=0.01, depth=0.20, segs=10,
                          loc=(-0.05, side*0.15, 0.18), parent=head_e, mat_=M_DEER_BROWN)
        ear.rotation_euler = (math.radians(-15), 0, math.radians(side*30))
    # MASSIVE BRANCHING ANTLERS (signature majestic stag)
    for side in (-1, 1):
        ant_e = empty(f"{name}_ant_e{side}", (-0.10, side*0.12, 0.25), parent=head_e)
        ant_e.rotation_euler = (math.radians(-15), 0, math.radians(side*20))
        # Main beam
        cyl(f"{name}_ant_main{side}", r=0.04, depth=0.50, segs=8,
            loc=(0, 0, 0.25), parent=ant_e, mat_=M_ANTLER)
        # 5 tines branching (signature antler)
        for ti in range(5):
            tine_h = 0.20 + ti * 0.08
            tine_x = math.sin(ti * 0.4) * 0.15
            tine_e = empty(f"{name}_ant_t_e{side}_{ti}", (tine_x, 0, tine_h), parent=ant_e)
            tine_e.rotation_euler = (0, math.radians(side*45 + ti*5), 0)
            cyl(f"{name}_tine{side}_{ti}", r=0.025 - ti*0.003, depth=0.25, segs=6,
                loc=(0, 0, 0.12), parent=tine_e, mat_=M_ANTLER)
            # Tine fork tip
            for tt in range(2):
                cyl(f"{name}_tt{side}_{ti}_{tt}", r=0.015, depth=0.15, segs=6,
                    loc=((tt*2-1)*0.05, 0, 0.30),
                    parent=tine_e, mat_=M_ANTLER).rotation_euler = (0, math.radians((tt*2-1)*30), 0)
    # 4 legs
    for x_idx, x in enumerate((0.50, -0.50)):
        for y_idx, y in enumerate((-0.35, 0.35)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.08, depth=1.0, segs=10,
                loc=(x, y, 0.55), parent=base, mat_=M_DEER_BROWN)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.09, depth=0.10, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_DEER_BROWN)
    # White tail
    smooth_sphere(f"{name}_tail", r=0.12, loc=(-0.75, 0, 1.15),
                  parent=base, mat_=M_DEER_BELLY, scale=(0.6, 0.8, 1.0))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

stags = []
stag_pos = [(-22, 12, 0), (22, 12, 0), (-22, -10, 0), (22, -10, 0)]
for i, (sx, sy, sz) in enumerate(stag_pos):
    fac = math.atan2(-sy, -sx)
    s = make_stag(f"stag{i}", (sx, sy, sz), facing=fac)
    stags.append(s)

# ============ 3 RAVENS + 1 FALCON ============
def make_raven(name, loc):
    base = empty(name, loc)
    smooth_sphere(f"{name}_body", r=0.25, segs=18, rings=12, loc=(0, 0, 0),
                  parent=base, mat_=M_RAVEN, scale=(1.7, 1, 1))
    head_e = empty(f"{name}_he", (0.40, 0, 0.10), parent=base)
    smooth_sphere(f"{name}_head", r=0.15, segs=16, rings=10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_RAVEN)
    smooth_cone(f"{name}_beak", r1=0.06, r2=0.005, depth=0.22, segs=10,
                loc=(0.20, 0, -0.02), parent=head_e,
                mat_=M_RAVEN).rotation_euler = (0, math.radians(90), 0)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04,
                      loc=(0.08, side*0.08, 0.05), parent=head_e, mat_=M_RAVEN_EYE)
    wings = []
    for side in (-1, 1):
        w_e = empty(f"{name}_we{side}", (0, side*0.18, 0.05), parent=base)
        beveled_cube(f"{name}_w_m{side}", (0.45, 0.85, 0.05), bevel_offset=0.02,
                     loc=(0, side*0.45, 0), parent=w_e, mat_=M_RAVEN)
        wings.append((w_e, side))
    beveled_cube(f"{name}_tail", (0.30, 0.20, 0.05), loc=(-0.40, 0, 0),
                 parent=base, mat_=M_RAVEN)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "wings": wings}

ravens = [
    make_raven("raven1", (-5, 16, 8)),
    make_raven("raven2", (5, 16, 10)),
    make_raven("raven3", (0, -16, 9)),
]

# Falcon (signature majestic raptor)
falcon_e = empty("falcon", loc=(0, 0, 18))
# Body
smooth_sphere("fal_body", r=0.30, segs=20, rings=14, loc=(0, 0, 0),
              parent=falcon_e, mat_=M_FALCON_BODY, scale=(1.7, 1, 1))
# Head
fal_he = empty("fal_he", (0.45, 0, 0.10), parent=falcon_e)
smooth_sphere("fal_head", r=0.18, segs=18, rings=12, loc=(0, 0, 0),
              parent=fal_he, mat_=M_FALCON_HEAD)
# Beak (hooked)
beak_e = empty("fal_be", (0.18, 0, -0.05), parent=fal_he)
smooth_cone("fal_beak_m", r1=0.07, r2=0.02, depth=0.18, segs=10,
            loc=(0, 0, 0), parent=beak_e,
            mat_=M_FALCON_BEAK).rotation_euler = (0, math.radians(90), 0)
smooth_cone("fal_beak_h", r1=0.04, r2=0.005, depth=0.08, segs=8,
            loc=(0.16, 0, -0.04), parent=beak_e,
            mat_=M_FALCON_BEAK).rotation_euler = (math.radians(-25), math.radians(90), 0)
# Glowing eyes
for side in (-1, 1):
    smooth_sphere(f"fal_eye{side}", r=0.04,
                  loc=(0.08, side*0.10, 0.06), parent=fal_he, mat_=M_RAVEN_EYE)
# Wings (spread wide for soar)
fal_wings = []
for side in (-1, 1):
    w_e = empty(f"fal_we{side}", (0, side*0.25, 0.05), parent=falcon_e)
    beveled_cube(f"fal_w_m{side}", (0.55, 1.20, 0.05), bevel_offset=0.03,
                 loc=(0, side*0.65, 0), parent=w_e, mat_=M_FALCON_BODY)
    # Wing tip primary feathers
    for fi in range(5):
        beveled_cube(f"fal_wf{side}_{fi}", (0.35, 0.10, 0.04),
                     loc=(0.10 + (fi-2)*0.08, side*1.30, 0),
                     parent=w_e, mat_=M_FALCON_BODY)
    fal_wings.append((w_e, side))
# Tail
for ti in range(5):
    ta = (ti - 2) * 0.20
    tail_f = beveled_cube(f"fal_tail{ti}", (0.30, 0.10, 0.04),
                          loc=(-0.45 - ti*0.05, math.sin(ta)*0.20, 0),
                          parent=falcon_e, mat_=M_FALCON_BODY)
    tail_f.rotation_euler = (0, 0, ta)

# ============================================================
# ⭐ 600 MAGICAL SPARKLES + 300 MIST (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 magical sparkles (signature - vortex around altar)
sparkles = []
spark_colors = [M_SPARK_GREEN, M_SPARK_BLUE, M_SPARK_PURPLE, M_SPARK_GOLD]
for i in range(600):
    # Spiral around altar (vortex)
    angle = random.uniform(0, math.pi*2)
    rad = random.uniform(1, 18)
    height = random.uniform(0.5, 14)
    px = rad * math.cos(angle)
    py = rad * math.sin(angle)
    pz = height
    col = spark_colors[i % 4]
    s_obj = smooth_sphere(f"spk{i}", r=random.uniform(0.06, 0.12), segs=8, rings=6,
                          loc=(px, py, pz), mat_=col)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_radius"] = rad
    s_obj["_angle"] = angle
    s_obj["_base_z"] = pz
    s_obj["_speed"] = random.uniform(0.5, 1.5)
    s_obj["_amp_z"] = random.uniform(0.4, 1.5)
    sparkles.append(s_obj)

# 300 mist particles (signature low ground)
mist_particles = []
for i in range(300):
    px = random.uniform(-30, 30)
    py = random.uniform(-30, 30)
    pz = random.uniform(0.2, 2.5)
    m_obj = smooth_sphere(f"mist{i}", r=random.uniform(0.25, 0.60), segs=12, rings=8,
                          loc=(px, py, pz),
                          mat_=M_MIST if i % 3 != 0 else M_MIST_GREEN,
                          scale=(1.5, 1.5, 0.4))
    m_obj["_phase"] = random.uniform(0, math.pi*2)
    m_obj["_base_x"] = px; m_obj["_base_y"] = py; m_obj["_base_z"] = pz
    m_obj["_amp_x"] = random.uniform(0.8, 2.0)
    m_obj["_amp_y"] = random.uniform(0.8, 2.0)
    m_obj["_speed"] = random.uniform(0.2, 0.6)
    mist_particles.append(m_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Aurora ribbons wave
for i, a_obj in enumerate(auroras):
    phase = a_obj["_phase"]
    base_x = a_obj.location.x
    base_z = a_obj.location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        a_obj.location.x = base_x + math.sin(t * 0.6 + phase) * 5
        a_obj.location.z = base_z + math.cos(t * 0.5 + phase) * 1.5
        a_obj.keyframe_insert("location", frame=f)

# Druids chant (body sway + arms wave)
for d in druids:
    phase = d["root"]["_phase"]
    base_z = d["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        d["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.04
        d["root"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(4),
                                     math.cos(t * 0.6 + phase) * math.radians(3),
                                     d["root"].rotation_euler.z)
        d["root"].keyframe_insert("location", frame=f)
        d["root"].keyframe_insert("rotation_euler", frame=f)
        for ai, arm in enumerate(d["arms"]):
            wave = math.sin(t * 2.0 + phase + ai * math.pi) * math.radians(15)
            arm.rotation_euler = (math.radians(-150) + wave, 0, math.radians((-1 if ai==0 else 1)*-30))
            arm.keyframe_insert("rotation_euler", frame=f)
        d["he"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(6), 0,
                                    math.sin(t * 0.8 + phase) * math.radians(10))
        d["he"].keyframe_insert("rotation_euler", frame=f)

# Celtic women harp/lyre play
for w in celt_women:
    phase = w["root"]["_phase"]
    base_z = w["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        w["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.03
        w["root"].keyframe_insert("location", frame=f)
        for ai, arm in enumerate(w["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 5.0 + phase + ai * math.pi) * math.radians(15)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        w["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                    math.sin(t * 1.0 + phase) * math.radians(8))
        w["he"].keyframe_insert("rotation_euler", frame=f)

# Runes pulse
for r in runes_objs:
    phase = r["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        sc = 1 + math.sin(t * 2.5 + phase) * 0.30
        r.scale = (sc * 0.6, sc * 0.6, sc * 0.20)
        r.keyframe_insert("scale", frame=f)

# Stags slight movement (sway + head)
for s in stags:
    phase = s["root"]["_phase"]
    base_z = s["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s["root"].location.z = base_z + math.sin(t * 0.8 + phase) * 0.04
        s["root"].keyframe_insert("location", frame=f)
        s["he"].rotation_euler = (math.sin(t * 0.7 + phase) * math.radians(6), 0,
                                    math.sin(t * 0.5 + phase) * math.radians(15))
        s["he"].keyframe_insert("rotation_euler", frame=f)

# Ravens orbit + flap
for r in ravens:
    phase = r["root"]["_phase"]
    base_x = r["root"].location.x
    base_y = r["root"].location.y
    base_z = r["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        a = t * 0.6 + phase
        rad = 14 + math.sin(t * 0.4) * 2
        r["root"].location = (rad * math.cos(a), rad * math.sin(a),
                                base_z + math.sin(t * 1.2 + phase) * 1.0)
        r["root"].rotation_euler = (0, 0, a + math.pi/2)
        r["root"].keyframe_insert("location", frame=f)
        r["root"].keyframe_insert("rotation_euler", frame=f)
        flap = math.sin(t * 5.0 + phase) * math.radians(35)
        for w_e, side in r["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)

# Falcon majestic soar above
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    a = t * 0.4
    rad = 22
    falcon_e.location = (rad * math.cos(a), rad * math.sin(a) - 3,
                          18 + math.sin(t * 0.6) * 2.0)
    falcon_e.rotation_euler = (0, 0, a + math.pi/2)
    falcon_e.keyframe_insert("location", frame=f)
    falcon_e.keyframe_insert("rotation_euler", frame=f)
    # Slow flap
    flap = math.sin(t * 1.5) * math.radians(20)
    for w_e, side in fal_wings:
        w_e.rotation_euler = (side * flap, 0, 0)
        w_e.keyframe_insert("rotation_euler", frame=f)

# Moon halos
for obj in bpy.data.objects:
    if obj.name.startswith("moon_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.7) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 600 MAGICAL SPARKLES vortex (signature celtic ritual)
# ============================================================
for s in sparkles:
    phase = s["_phase"]; speed = s["_speed"]
    rad = s["_radius"]; base_angle = s["_angle"]
    base_z = s["_base_z"]; amp_z = s["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Vortex spiral around altar
        angle = base_angle + t * speed
        # Slight radial drift
        cur_rad = rad + math.sin(t * 0.8 + phase) * 0.5
        x = cur_rad * math.cos(angle)
        y = cur_rad * math.sin(angle)
        # Vertical oscillation
        z = base_z + amp_z * math.sin(t * 1.5 + phase)
        s.location = (x, y, max(0.3, z))
        # Pulse scale
        sc = 1 + math.sin(t * 4.0 + phase) * 0.4
        s.scale = (sc, sc, sc)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

# 300 MIST drift low (signature)
for m in mist_particles:
    phase = m["_phase"]; speed = m["_speed"]
    bx, by, bz = m["_base_x"], m["_base_y"], m["_base_z"]
    ax, ay = m["_amp_x"], m["_amp_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.85 + phase)
        z = bz + math.sin(t * 0.6 + phase) * 0.3
        m.location = (x, y, max(0.2, z))
        sc = 1 + math.sin(t * 1.5 + phase) * 0.15
        m.scale = (sc * 1.5, sc * 1.5, sc * 0.4)
        m.keyframe_insert("location", frame=f)
        m.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_celtic_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_celtic_stonehenge_druids] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_celtic_stonehenge_druids] ONE grass + Stonehenge 30 stones + trilithons + altar + 6 druids + archdruid mistletoe crown + 8 celt women red hair harp/lyre + 5 dolmens + 100 runes + 4 stags + 3 ravens + falcon + aurora + 600 SPARKLES + 300 MIST")
print("⭐ FIXES: 1 ground + 600 magical sparkles vortex + 300 mist drift (signature Celtic ritual mandatory) ⭐")
