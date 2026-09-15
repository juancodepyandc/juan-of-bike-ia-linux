"""
proc_viking_longhouse_feast.py — 201e procédural AuroraIA (65e qualité, post-MILESTONE 200E)
Longhouse viking festin nordique : charpente bois + cheminée + 15 vikings + chef + drakkar + Odin + corbeaux + aurore + neige
"""
import bpy, bmesh, math, random, os

random.seed(0xF1A201)

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
M_SKY_NIGHT = mat("sky", (0.05, 0.08, 0.18, 1.0), 0.0, 0.7, emission=(0.10,0.15,0.30), emission_strength=1.0)
M_AURORA_GREEN = mat("aurora_g", (0.20, 1.0, 0.55, 1.0), 0.0, 0.10, emission=(0.25,1.0,0.60), emission_strength=6.0, alpha=0.5)
M_AURORA_PURPLE = mat("aurora_p", (0.65, 0.30, 1.0, 1.0), 0.0, 0.10, emission=(0.70,0.35,1.0), emission_strength=5.0, alpha=0.5)
M_AURORA_PINK = mat("aurora_pk", (1.0, 0.45, 0.75, 1.0), 0.0, 0.10, emission=(1.0,0.50,0.78), emission_strength=4.5, alpha=0.5)
M_STAR = mat("star", (1.0, 1.0, 0.95, 1.0), 0.0, 0.05, emission=(1.0,0.98,0.90), emission_strength=18.0)
M_SNOW = mat("snow", (0.95, 0.97, 1.0, 1.0), 0.0, 0.45, emission=(0.85,0.90,1.0), emission_strength=0.6)
M_SNOWFLAKE = mat("snowflake", (1.0, 1.0, 1.0, 1.0), 0.0, 0.10, emission=(0.95,0.98,1.0), emission_strength=8.0)

# Wood
M_WOOD = mat("wood", (0.35, 0.20, 0.10, 1.0), 0.0, 0.78)
M_WOOD_DARK = mat("wood_dark", (0.18, 0.10, 0.05, 1.0), 0.0, 0.85)
M_WOOD_RICH = mat("wood_rich", (0.50, 0.30, 0.15, 1.0), 0.0, 0.55, emission=(0.45,0.27,0.13), emission_strength=0.4)
M_FLOOR = mat("floor", (0.25, 0.18, 0.10, 1.0), 0.0, 0.78)
M_THATCH = mat("thatch", (0.55, 0.40, 0.20, 1.0), 0.0, 0.85, emission=(0.45,0.32,0.18), emission_strength=0.3)

# Runes
M_RUNE = mat("rune", (1.0, 0.55, 0.20, 1.0), 0.3, 0.30, emission=(1.0,0.55,0.20), emission_strength=10.0)
M_RUNE_BLUE = mat("rune_b", (0.30, 0.65, 1.0, 1.0), 0.3, 0.30, emission=(0.30,0.70,1.0), emission_strength=8.0)

# Stone
M_STONE = mat("stone", (0.40, 0.38, 0.35, 1.0), 0.0, 0.80, emission=(0.32,0.30,0.28), emission_strength=0.3)
M_STONE_LIT = mat("stone_lit", (0.55, 0.42, 0.30, 1.0), 0.0, 0.65, emission=(0.55,0.40,0.28), emission_strength=0.7)

# Fire
M_FLAME = mat("flame", (1.0, 0.50, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.55,0.15), emission_strength=14.0)
M_FLAME_INNER = mat("flame_in", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.90,0.40), emission_strength=22.0)
M_EMBER = mat("ember", (1.0, 0.30, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.35,0.15), emission_strength=10.0)
M_LOG = mat("log", (0.30, 0.18, 0.10, 1.0), 0.0, 0.80)

# Metals
M_IRON = mat("iron", (0.30, 0.30, 0.32, 1.0), 0.85, 0.45, emission=(0.25,0.25,0.28), emission_strength=0.4)
M_STEEL = mat("steel", (0.65, 0.65, 0.70, 1.0), 0.92, 0.20, emission=(0.55,0.55,0.60), emission_strength=0.4)
M_GOLD = mat("gold", (1.0, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.22), emission_strength=0.9)
M_BRONZE = mat("bronze", (0.85, 0.55, 0.25, 1.0), 0.90, 0.30, emission=(0.78,0.50,0.22), emission_strength=0.6)

# Vikings
M_SKIN_NORDIC = mat("skin_n", (0.92, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.82,0.70,0.58), emission_strength=0.3)
M_HAIR_BLOND = mat("hair_b", (0.85, 0.65, 0.30, 1.0), 0.0, 0.70, emission=(0.80,0.60,0.28), emission_strength=0.4)
M_HAIR_RED = mat("hair_r", (0.80, 0.30, 0.10, 1.0), 0.0, 0.75, emission=(0.75,0.30,0.10), emission_strength=0.5)
M_HAIR_BROWN = mat("hair_br", (0.30, 0.18, 0.10, 1.0), 0.0, 0.80)
M_BEARD_BLOND = mat("beard_b", (0.70, 0.50, 0.25, 1.0), 0.0, 0.85)
M_BEARD_RED = mat("beard_r", (0.65, 0.25, 0.10, 1.0), 0.0, 0.80, emission=(0.55,0.22,0.08), emission_strength=0.3)
M_BEARD_BROWN = mat("beard_br", (0.25, 0.15, 0.08, 1.0), 0.0, 0.80)
M_TUNIC_GREEN = mat("tunic_g", (0.30, 0.40, 0.20, 1.0), 0.0, 0.60, emission=(0.25,0.35,0.18), emission_strength=0.3)
M_TUNIC_BLUE = mat("tunic_b", (0.20, 0.30, 0.50, 1.0), 0.0, 0.55, emission=(0.18,0.28,0.45), emission_strength=0.4)
M_TUNIC_BROWN = mat("tunic_br", (0.45, 0.25, 0.15, 1.0), 0.0, 0.60, emission=(0.40,0.22,0.13), emission_strength=0.3)
M_TUNIC_RED = mat("tunic_r", (0.55, 0.18, 0.15, 1.0), 0.0, 0.55, emission=(0.50,0.18,0.15), emission_strength=0.4)
M_CHIEF_COAT = mat("chief_coat", (0.60, 0.10, 0.10, 1.0), 0.0, 0.50, emission=(0.55,0.10,0.08), emission_strength=0.5)
M_FUR = mat("fur", (0.85, 0.80, 0.65, 1.0), 0.0, 0.80, emission=(0.78,0.72,0.60), emission_strength=0.3)
M_LEATHER = mat("leather", (0.30, 0.18, 0.10, 1.0), 0.0, 0.75)

# Helmet
M_HELMET = mat("helmet", (0.55, 0.55, 0.58, 1.0), 0.90, 0.30, emission=(0.45,0.45,0.50), emission_strength=0.4)

# Axe / weapons
M_AXE_HEAD = mat("axe_head", (0.65, 0.65, 0.70, 1.0), 0.92, 0.20, emission=(0.55,0.55,0.60), emission_strength=0.5)

# Shields
M_SHIELD_RED = mat("shield_r", (0.65, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.55,0.15,0.13), emission_strength=0.5)
M_SHIELD_BLUE = mat("shield_b", (0.18, 0.30, 0.55, 1.0), 0.0, 0.55, emission=(0.15,0.28,0.50), emission_strength=0.5)
M_SHIELD_YELLOW = mat("shield_y", (0.85, 0.65, 0.20, 1.0), 0.0, 0.50, emission=(0.78,0.58,0.18), emission_strength=0.5)
M_SHIELD_BOSS = mat("shield_boss", (0.55, 0.55, 0.60, 1.0), 0.85, 0.30, emission=(0.45,0.45,0.50), emission_strength=0.4)

# Horn drinks
M_HORN = mat("horn", (0.92, 0.85, 0.60, 1.0), 0.5, 0.35, emission=(0.85,0.78,0.55), emission_strength=0.5)
M_MEAD = mat("mead", (0.95, 0.75, 0.25, 1.0), 0.2, 0.20, emission=(0.95,0.78,0.30), emission_strength=2.0)

# Food
M_MEAT = mat("meat", (0.55, 0.25, 0.15, 1.0), 0.0, 0.55, emission=(0.50,0.22,0.13), emission_strength=0.4)
M_MEAT_COOKED = mat("meat_c", (0.75, 0.45, 0.25, 1.0), 0.0, 0.50, emission=(0.65,0.40,0.22), emission_strength=0.5)
M_BREAD = mat("bread", (0.85, 0.65, 0.35, 1.0), 0.0, 0.55, emission=(0.78,0.60,0.32), emission_strength=0.4)

# Dogs (wolfhounds)
M_DOG_GREY = mat("dog_grey", (0.40, 0.35, 0.30, 1.0), 0.0, 0.65, emission=(0.35,0.30,0.25), emission_strength=0.3)
M_DOG_BROWN = mat("dog_brown", (0.45, 0.28, 0.18, 1.0), 0.0, 0.65, emission=(0.40,0.25,0.15), emission_strength=0.3)
M_DOG_EYE = mat("dog_eye", (1.0, 0.85, 0.30, 1.0), 0.0, 0.15, emission=(1.0,0.85,0.30), emission_strength=3.0)

# Drakkar
M_DRAKKAR = mat("drakkar", (0.30, 0.20, 0.10, 1.0), 0.0, 0.70)
M_DRAKKAR_GOLD = mat("drakkar_gold", (0.85, 0.65, 0.25, 1.0), 0.90, 0.20, emission=(0.78,0.58,0.22), emission_strength=0.7)
M_DRAKKAR_SAIL = mat("drakkar_sail", (0.85, 0.80, 0.70, 1.0), 0.0, 0.65, emission=(0.75,0.72,0.62), emission_strength=0.4)

# Odin statue
M_ODIN_STONE = mat("odin_stone", (0.65, 0.55, 0.40, 1.0), 0.3, 0.45, emission=(0.55,0.45,0.32), emission_strength=0.5)
M_RAVEN = mat("raven", (0.05, 0.05, 0.08, 1.0), 0.0, 0.50, emission=(0.08,0.08,0.10), emission_strength=0.3)
M_RAVEN_EYE = mat("raven_eye", (1.0, 0.30, 0.10, 1.0), 0.0, 0.15, emission=(1.0,0.30,0.10), emission_strength=5.0)

# Particles
M_SPARK = mat("spark", (1.0, 0.85, 0.40, 1.0), 0.0, 0.05, emission=(1.0,0.90,0.45), emission_strength=18.0)

# Lyre / instrument
M_LYRE_WOOD = mat("lyre_w", (0.55, 0.30, 0.15, 1.0), 0.0, 0.55, emission=(0.45,0.25,0.13), emission_strength=0.4)
M_LYRE_STRINGS = mat("lyre_s", (0.85, 0.85, 0.85, 1.0), 0.5, 0.20, emission=(0.75,0.75,0.75), emission_strength=0.5)

# ============ NIGHT SKY ============
sky = smooth_sphere("sky", r=90, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY_NIGHT, scale=(1,1,0.6))
sky.scale = (1,1,0.6)
# 80 STARS twinkle
stars = []
for i in range(80):
    sx = random.uniform(-50, 50)
    sy = random.uniform(15, 45)
    sz = random.uniform(15, 35)
    star = smooth_sphere(f"star{i}", r=random.uniform(0.08, 0.18), segs=10, rings=8,
                        loc=(sx, sy, sz), mat_=M_STAR)
    star["_phase"] = random.uniform(0, math.pi*2)
    stars.append(star)

# AURORE BORÉALE (4 ribbons across sky)
aurora_ribbons = []
aurora_mats = [M_AURORA_GREEN, M_AURORA_PURPLE, M_AURORA_GREEN, M_AURORA_PINK]
for ri in range(4):
    rib_e = empty(f"aurora_e{ri}", (0, 30, 25 + ri * 3))
    # Each ribbon = 8 wave segments
    for j in range(8):
        angle = (j / 7.0) * math.pi - math.pi/2  # -90 to +90
        ry = 30 + math.sin(angle * 3 + ri * 0.5) * 3
        rz_off = math.cos(angle * 2 + ri * 0.3) * 2
        rib = beveled_cube(f"aurora{ri}_{j}", (6, 0.3, 4), bevel_offset=0.1,
                          loc=(angle * 8, ry - 30, rz_off),
                          parent=rib_e, mat_=aurora_mats[ri])
        rib["_phase"] = j * 0.3 + ri * 0.4
    rib_e["_base_phase"] = ri * 0.5
    aurora_ribbons.append(rib_e)

# Moon
moon = smooth_sphere("moon", r=2.0, loc=(-15, 38, 28), mat_=M_STAR)

# ============ GROUND (snowy) ============
ground = beveled_cube("ground", (60, 60, 0.4), bevel_offset=0.05, loc=(0, 0, -0.2), mat_=M_FLOOR)
# Snow patches
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 28)
    smooth_sphere(f"snow_p{i}", r=random.uniform(0.5, 1.5),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.05),
                  mat_=M_SNOW, scale=(1, 1, 0.15))

# ============ LONGHOUSE STRUCTURE ============
longhouse_e = empty("longhouse", loc=(0, 0, 0))

# Floor inside
beveled_cube("lh_floor", (16, 8, 0.20), loc=(0, 0, 0.10), parent=longhouse_e, mat_=M_FLOOR)

# Side walls (2 long)
for side in (-1, 1):
    beveled_cube(f"wall_{side}", (16, 0.40, 4.0), bevel_offset=0.05,
                 loc=(0, side*4, 2.0), parent=longhouse_e, mat_=M_WOOD)
# End walls (2 short)
for end in (-1, 1):
    beveled_cube(f"end_wall_{end}", (0.40, 8, 4.0), bevel_offset=0.05,
                 loc=(end*8, 0, 2.0), parent=longhouse_e, mat_=M_WOOD)

# 4 COLUMNS RUNES (massive vertical posts)
for x_idx, x in enumerate((-5, -1.5, 1.5, 5)):
    col_e = empty(f"col_e{x_idx}", (x, 0, 0), parent=longhouse_e)
    # Column wood
    cyl(f"col{x_idx}", r=0.30, depth=6.5, segs=16,
        loc=(0, 0, 3.25), parent=col_e, mat_=M_WOOD_DARK)
    # Runes etched (3 stacked)
    for r in range(3):
        rune = beveled_cube(f"rune{x_idx}_{r}", (0.35, 0.10, 0.25), bevel_offset=0.02,
                            loc=(0, 0, 2.0 + r * 0.7), parent=col_e,
                            mat_=M_RUNE if x_idx % 2 == 0 else M_RUNE_BLUE)
    # Capital top
    smooth_sphere(f"col_top{x_idx}", r=0.40, loc=(0, 0, 6.4),
                  parent=col_e, mat_=M_WOOD_RICH, scale=(1, 1, 0.5))

# ROOF (peaked thatched)
# 4 horizontal roof beams + slanted thatching
# Ridge beam
beveled_cube("ridge_beam", (17, 0.40, 0.40), loc=(0, 0, 6.8), parent=longhouse_e, mat_=M_WOOD_DARK)
# Roof thatching (2 angled planes)
for side in (-1, 1):
    roof = beveled_cube(f"roof_{side}", (17, 5.5, 0.30), bevel_offset=0.05,
                       loc=(0, side*2.5, 5.5), parent=longhouse_e, mat_=M_THATCH)
    roof.rotation_euler = (math.radians(side*-25), 0, 0)
# Roof rafters (8 visible inside)
for i in range(8):
    rx = (i - 3.5) * 2.0
    rafter_e = empty(f"rafter_e{i}", (rx, 0, 5.5), parent=longhouse_e)
    for side in (-1, 1):
        raft = beveled_cube(f"rafter_{i}_{side}", (0.20, 4.5, 0.20),
                           loc=(0, side*2.0, 0), parent=rafter_e, mat_=M_WOOD_DARK)
        raft.rotation_euler = (math.radians(side*-25), 0, 0)
    # Cross tie
    beveled_cube(f"crosstie_{i}", (0.20, 7.5, 0.20),
                 loc=(0, 0, -0.3), parent=rafter_e, mat_=M_WOOD_DARK)

# Smoke hole (opening above fire)
# (just visual gap - skip drawing nothing)

# ============ CHEMINÉE CENTRALE (fire pit) ============
fire_pit_e = empty("fire_pit", loc=(0, 0, 0))
# Stone ring (8 stones)
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    smooth_sphere(f"fire_stone{i}", r=0.35,
                  loc=(1.5*math.cos(a), 1.5*math.sin(a), 0.30),
                  parent=fire_pit_e,
                  mat_=M_STONE_LIT if i % 2 == 0 else M_STONE)
# Floor under fire (darker)
cyl("fire_floor", r=1.3, depth=0.05, segs=20, loc=(0,0,0.18),
    parent=fire_pit_e, mat_=M_WOOD_DARK)

# Logs (4 crossed)
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    log = cyl(f"log{i}", r=0.18, depth=2.0, segs=12,
             loc=(0.10*math.cos(a), 0.10*math.sin(a), 0.30),
             parent=fire_pit_e, mat_=M_LOG)
    log.rotation_euler = (math.radians(90), 0, a)

# Flames (8 flames cluster)
flames = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = random.uniform(0.20, 0.55)
    fx = rad * math.cos(a)
    fy = rad * math.sin(a)
    outer = smooth_cone(f"flame_o{i}", r1=0.30, r2=0.02, depth=1.0, segs=10,
                       loc=(fx, fy, 0.80), parent=fire_pit_e, mat_=M_FLAME)
    inner = smooth_cone(f"flame_i{i}", r1=0.18, r2=0.01, depth=0.75, segs=10,
                       loc=(fx, fy, 0.85), parent=fire_pit_e, mat_=M_FLAME_INNER)
    outer["_phase"] = i * 0.5
    inner["_phase"] = i * 0.5 + 0.3
    flames.append((outer, inner))

# 6 embers scattered
embers = []
for i in range(6):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(0.10, 0.40)
    e = smooth_sphere(f"ember{i}", r=0.05,
                     loc=(rad*math.cos(a), rad*math.sin(a),
                          random.uniform(0.10, 0.45)),
                     parent=fire_pit_e, mat_=M_EMBER)
    e["_phase"] = random.uniform(0, math.pi*2)
    embers.append(e)

# Chain hanging cauldron above fire
cyl("chain", r=0.015, depth=2.5, segs=8,
    loc=(0, 0, 4.0), parent=fire_pit_e, mat_=M_IRON)
# Cauldron
cauldron_e = empty("cauldron", (0, 0, 2.0), parent=fire_pit_e)
smooth_sphere("cauldron_body", r=0.55, segs=22, rings=14, loc=(0, 0, 0),
              parent=cauldron_e, mat_=M_IRON, scale=(1, 1, 0.85))
cyl("cauldron_rim", r=0.52, depth=0.10, segs=22,
    loc=(0, 0, 0.35), parent=cauldron_e, mat_=M_BRONZE)
# Soup inside (glowing)
smooth_sphere("cauldron_soup", r=0.48, loc=(0, 0, 0.30),
              parent=cauldron_e, mat_=M_MEAD, scale=(1, 1, 0.1))

# ============ LARGE FEAST TABLE ============
table_e = empty("table", loc=(0, 0, 0))
# Top
beveled_cube("table_top", (12, 2.0, 0.10), bevel_offset=0.04,
             loc=(0, 0, 1.0), parent=table_e, mat_=M_WOOD)
# Legs (4 pairs)
for x_idx in range(4):
    x = (x_idx - 1.5) * 3.5
    for side in (-1, 1):
        beveled_cube(f"table_leg{x_idx}_{side}", (0.25, 0.25, 1.0),
                     loc=(x, side*0.85, 0.50), parent=table_e, mat_=M_WOOD_DARK)
# Stretchers (2 long)
for side in (-1, 1):
    beveled_cube(f"table_str_{side}", (11, 0.10, 0.10), loc=(0, side*0.85, 0.30),
                 parent=table_e, mat_=M_WOOD_DARK)

# BOEUF RÔTI (giant roast at center of table)
roast_e = empty("roast", loc=(0, 0, 1.15))
# Body (large oval)
smooth_sphere("roast_body", r=0.55, segs=24, rings=16, loc=(0, 0, 0.30),
              parent=roast_e, mat_=M_MEAT_COOKED, scale=(2.5, 0.9, 0.8))
# Charred patches
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    rad = random.uniform(0.3, 0.8)
    smooth_sphere(f"roast_char{i}", r=0.15,
                  loc=(rad*math.cos(a) * 2, rad*math.sin(a) * 0.6, 0.45),
                  parent=roast_e, mat_=M_MEAT, scale=(1, 1, 0.4))
# Spit (skewer through)
cyl("spit", r=0.04, depth=4.0, segs=10,
    loc=(0, 0, 0.30), parent=roast_e, mat_=M_IRON).rotation_euler = (0, math.radians(90), 0)
# 4 dipper bowls beside
for i in range(4):
    x = -3.5 + i * 2.5
    cyl(f"bowl{i}", r=0.20, depth=0.08, segs=18,
        loc=(x, -0.4, 1.10), parent=table_e, mat_=M_WOOD)
    # Stew inside
    smooth_sphere(f"stew{i}", r=0.18, loc=(x, -0.4, 1.15),
                  parent=table_e, mat_=M_MEAT_COOKED, scale=(1, 1, 0.3))
# 6 breads (round loaves)
for i in range(6):
    x = -5 + i * 2
    smooth_sphere(f"bread{i}", r=0.18, loc=(x, 0.4, 1.10),
                  parent=table_e, mat_=M_BREAD, scale=(1, 1, 0.7))

# 16 HORNS À HYDROMEL (drinking horns)
horns = []
for hi in range(16):
    side = -1 if hi < 8 else 1
    x_pos = -5.5 + (hi % 8) * 1.6
    h_e = empty(f"horn_e{hi}", (x_pos, side*0.7, 1.15), parent=table_e)
    h_e.rotation_euler = (math.radians(side*30), 0, math.radians(side*-15))
    # Horn body (curved cone)
    cyl(f"horn_body{hi}", r=0.10, depth=0.45, segs=14,
        loc=(0, 0, 0), parent=h_e, mat_=M_HORN)
    # Tip pointed
    smooth_cone(f"horn_tip{hi}", r1=0.10, r2=0.02, depth=0.20, segs=10,
                loc=(0, 0, -0.30), parent=h_e, mat_=M_HORN)
    # Rim band
    cyl(f"horn_rim{hi}", r=0.12, depth=0.04, segs=14,
        loc=(0, 0, 0.22), parent=h_e, mat_=M_GOLD)
    # Mead inside
    smooth_sphere(f"horn_mead{hi}", r=0.08, loc=(0, 0, 0.10),
                  parent=h_e, mat_=M_MEAD)
    horns.append(h_e)

# ============ 15 VIKINGS + CHEF (16 total) at long table ============
def make_viking(name, loc, tunic_mat, hair_mat, beard_mat, has_helmet=False, has_horn=True, action="toast"):
    base = empty(name, loc)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg{side_idx}", r=0.12, depth=0.85, segs=10,
            loc=(side*0.14, 0, 0.42), parent=base, mat_=M_LEATHER)
        # Boot
        beveled_cube(f"{name}_boot{side_idx}", (0.20, 0.30, 0.20),
                     loc=(side*0.14, 0.05, 0.10), parent=base, mat_=M_LEATHER)
    # Torso (tunic)
    beveled_cube(f"{name}_torso", (0.55, 0.35, 0.85), bevel_offset=0.05,
                 loc=(0, 0, 1.30), parent=base, mat_=tunic_mat)
    # Belt
    beveled_cube(f"{name}_belt", (0.60, 0.40, 0.10), loc=(0, 0, 0.92),
                 parent=base, mat_=M_LEATHER)
    # Belt buckle
    beveled_cube(f"{name}_buckle", (0.12, 0.05, 0.12), loc=(0, -0.22, 0.92),
                 parent=base, mat_=M_BRONZE)
    # Fur shoulder cape
    smooth_sphere(f"{name}_fur", r=0.25, loc=(0, 0.10, 1.65),
                  parent=base, mat_=M_FUR, scale=(1.6, 0.8, 0.8))
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 1.90), parent=base)
    smooth_sphere(f"{name}_head", r=0.20, segs=20, rings=14, loc=(0,0,0),
                  parent=head_e, mat_=M_SKIN_NORDIC)
    # Eyes (blue or green)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.025,
                      loc=(side*0.07, -0.17, 0.03), parent=head_e,
                      mat_=mat(f"{name}_eyew", (1,1,1,1), 0, 0.3))
    # Nose
    smooth_sphere(f"{name}_nose", r=0.04, loc=(0, -0.18, -0.03),
                  parent=head_e, mat_=M_SKIN_NORDIC)
    # BEARD (long braided)
    smooth_sphere(f"{name}_beard1", r=0.13, loc=(0, -0.10, -0.15),
                  parent=head_e, mat_=beard_mat, scale=(1.4, 0.7, 1.4))
    # Braid below
    for j in range(3):
        smooth_sphere(f"{name}_beard_b{j}", r=0.06 - j*0.01,
                      loc=(0, -0.13, -0.30 - j*0.13),
                      parent=head_e, mat_=beard_mat, scale=(1, 1.2, 1.2))
    # Hair (long, sometimes braided)
    smooth_sphere(f"{name}_hair_top", r=0.22, loc=(0, 0.03, 0.10),
                  parent=head_e, mat_=hair_mat, scale=(1.05, 0.95, 0.7))
    # Hair back (long)
    smooth_sphere(f"{name}_hair_back", r=0.22, loc=(0, 0.20, -0.05),
                  parent=head_e, mat_=hair_mat, scale=(1.05, 0.7, 1.2))
    # HELMET (some warriors)
    if has_helmet:
        helm_e = empty(f"{name}_helm_e", (0, 0, 0.18), parent=head_e)
        # Dome (rounded)
        smooth_sphere(f"{name}_helm_dome", r=0.24, segs=20, rings=14,
                      loc=(0, 0, 0), parent=helm_e, mat_=M_HELMET, scale=(1, 1, 0.75))
        # Nose guard
        beveled_cube(f"{name}_nose_guard", (0.06, 0.03, 0.20),
                     loc=(0, -0.18, -0.10), parent=helm_e, mat_=M_HELMET)
        # 2 simple horns (NO not historical but iconic) - skip for authentic
        # Riveting band
        cyl(f"{name}_helm_band", r=0.25, depth=0.05, segs=20,
            loc=(0, 0, -0.05), parent=helm_e, mat_=M_BRONZE)

    # ARMS (action-dependent)
    arms_pose = {
        "toast": [(math.radians(-140), -15), (math.radians(-30), 5)],  # right arm raised with horn
        "axe": [(math.radians(-130), -10), (math.radians(-50), 10)],
        "drum": [(math.radians(-80), 0), (math.radians(-80), 0)],
        "rest": [(math.radians(-30), 0), (math.radians(-30), 0)],
    }
    pose_data = arms_pose.get(action, arms_pose["toast"])
    arms_e = {}
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.75), parent=base)
        rx, rz = pose_data[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15) + math.radians(rz))
        cyl(f"{name}_up{side_idx}", r=0.08, depth=0.40, segs=10,
            loc=(0, 0, -0.20), parent=sh, mat_=tunic_mat)
        el = empty(f"{name}_el{side_idx}", (0, 0, -0.42), parent=sh)
        el.rotation_euler = (math.radians(40 if side == -1 else 50), 0, 0)
        cyl(f"{name}_fa{side_idx}", r=0.07, depth=0.38, segs=10,
            loc=(0, 0, -0.20), parent=el, mat_=M_SKIN_NORDIC)
        # Hand
        hand = empty(f"{name}_hand{side_idx}", (0, 0, -0.42), parent=el)
        smooth_sphere(f"{name}_hand_g{side_idx}", r=0.07, loc=(0, 0, 0),
                      parent=hand, mat_=M_SKIN_NORDIC)
        arms_e[f"sh{side_idx}"] = sh
        arms_e[f"hand{side_idx}"] = hand

    # HORN à hydromel dans main droite (right hand)
    if has_horn:
        horn_e = empty(f"{name}_horn_e", (0, 0, -0.05), parent=arms_e["hand1"])
        horn_e.rotation_euler = (math.radians(45), 0, 0)
        cyl(f"{name}_horn_body", r=0.07, depth=0.30, segs=12,
            loc=(0, 0, 0), parent=horn_e, mat_=M_HORN)
        smooth_cone(f"{name}_horn_tip", r1=0.07, r2=0.02, depth=0.15, segs=10,
                    loc=(0, 0, -0.20), parent=horn_e, mat_=M_HORN)
        cyl(f"{name}_horn_rim", r=0.09, depth=0.03, segs=12,
            loc=(0, 0, 0.15), parent=horn_e, mat_=M_GOLD)
        # Mead inside
        smooth_sphere(f"{name}_horn_mead", r=0.06, loc=(0, 0, 0.05),
                      parent=horn_e, mat_=M_MEAD)
    return {"root": base, "head_e": head_e, "sh0": arms_e["sh0"], "sh1": arms_e["sh1"]}

# 14 vikings at table sides (7 each side)
vikings = []
hair_choices = [M_HAIR_BLOND, M_HAIR_RED, M_HAIR_BROWN]
beard_choices = [M_BEARD_BLOND, M_BEARD_RED, M_BEARD_BROWN]
tunic_choices = [M_TUNIC_GREEN, M_TUNIC_BLUE, M_TUNIC_BROWN, M_TUNIC_RED]
for i in range(14):
    side = -1 if i < 7 else 1
    seat_x = -5 + (i % 7) * 1.7
    seat_y = side * 1.6
    facing = math.radians(side * -90)
    has_helm = random.random() < 0.4
    hair_idx = random.randint(0, 2)
    v = make_viking(f"viking{i}", (seat_x, seat_y, 0.5),
                    random.choice(tunic_choices),
                    hair_choices[hair_idx], beard_choices[hair_idx],
                    has_helmet=has_helm, action="toast")
    v["root"].rotation_euler = (0, 0, facing)
    vikings.append(v)

# CHEF (head of table, larger, axe + chief coat + helmet)
chef = make_viking("chef", (-7, 0, 0.5), M_CHIEF_COAT, M_HAIR_BLOND, M_BEARD_BLOND,
                   has_helmet=True, has_horn=False, action="axe")
chef["root"].rotation_euler = (0, 0, math.radians(90))
# Add scale slightly
chef["root"].scale = (1.15, 1.15, 1.15)
# AXE in chef's right hand
axe_e = empty("axe_e", (0.30, 0, 1.05), parent=chef["sh1"])
axe_e.rotation_euler = (math.radians(-30), 0, 0)
# Handle
cyl("axe_handle", r=0.04, depth=0.95, segs=10,
    loc=(0, 0, 0.30), parent=axe_e, mat_=M_LEATHER)
# Head
beveled_cube("axe_head_main", (0.04, 0.30, 0.30), bevel_offset=0.03,
             loc=(0, 0.10, 0.80), parent=axe_e, mat_=M_AXE_HEAD)
# Pointed tip
smooth_cone("axe_tip", r1=0.04, r2=0.005, depth=0.20, segs=8,
            loc=(0, 0.30, 0.80), parent=axe_e, mat_=M_AXE_HEAD)

# SCALDE (Skald - poet) at end of table playing lyre
scald_base = empty("scald", loc=(7, 0, 0.5))
scald_base.rotation_euler = (0, 0, math.radians(-90))
# Quick simple body
for side_idx, side in enumerate((-1, 1)):
    cyl(f"scald_leg{side_idx}", r=0.12, depth=0.85, segs=10,
        loc=(side*0.14, 0, 0.42), parent=scald_base, mat_=M_LEATHER)
beveled_cube("scald_torso", (0.55, 0.35, 0.85), bevel_offset=0.05,
             loc=(0, 0, 1.30), parent=scald_base, mat_=M_TUNIC_GREEN)
beveled_cube("scald_belt", (0.60, 0.40, 0.10), loc=(0, 0, 0.92),
             parent=scald_base, mat_=M_LEATHER)
scald_head_e = empty("scald_head_e", (0, 0, 1.90), parent=scald_base)
smooth_sphere("scald_head", r=0.20, loc=(0,0,0), parent=scald_head_e, mat_=M_SKIN_NORDIC)
smooth_sphere("scald_beard", r=0.13, loc=(0, -0.10, -0.15), parent=scald_head_e,
              mat_=M_BEARD_BROWN, scale=(1.4, 0.7, 1.4))
smooth_sphere("scald_hair", r=0.22, loc=(0, 0.05, 0.05), parent=scald_head_e,
              mat_=M_HAIR_BROWN, scale=(1.05, 0.95, 0.7))
# Arms playing lyre
sc_l_sh = empty("scald_l_sh", (-0.25, 0, 1.75), parent=scald_base)
sc_l_sh.rotation_euler = (math.radians(-80), 0, math.radians(20))
cyl("scald_l_up", r=0.08, depth=0.40, segs=10,
    loc=(0, 0, -0.20), parent=sc_l_sh, mat_=M_TUNIC_GREEN)
sc_r_sh = empty("scald_r_sh", (0.25, 0, 1.75), parent=scald_base)
sc_r_sh.rotation_euler = (math.radians(-100), 0, math.radians(-30))
cyl("scald_r_up", r=0.08, depth=0.40, segs=10,
    loc=(0, 0, -0.20), parent=sc_r_sh, mat_=M_TUNIC_GREEN)
# LYRE in left arm (between knees)
lyre_e = empty("lyre_e", (0, -0.35, 1.20), parent=scald_base)
lyre_e.rotation_euler = (math.radians(-15), 0, 0)
# Body (wood frame)
beveled_cube("lyre_body", (0.35, 0.10, 0.45), bevel_offset=0.04,
             loc=(0, 0, 0), parent=lyre_e, mat_=M_LYRE_WOOD)
# 2 horns at top
for side in (-1, 1):
    horn = beveled_cube(f"lyre_horn_{side}", (0.04, 0.08, 0.30),
                       loc=(side*0.18, 0, 0.30), parent=lyre_e, mat_=M_LYRE_WOOD)
    horn.rotation_euler = (0, 0, math.radians(side*15))
# Cross bar
beveled_cube("lyre_cross", (0.45, 0.04, 0.04), loc=(0, 0, 0.45),
             parent=lyre_e, mat_=M_LYRE_WOOD)
# 4 strings
for i in range(4):
    cyl(f"lyre_str{i}", r=0.005, depth=0.4, segs=4,
        loc=((i-1.5)*0.07, 0, 0.20), parent=lyre_e, mat_=M_LYRE_STRINGS)

# ============ 12 BOUCLIERS RONDS sur mur (3 each side wall, 6 chacun) ============
shields_obj = []
shield_colors = [M_SHIELD_RED, M_SHIELD_BLUE, M_SHIELD_YELLOW]
for side_idx, side_y in enumerate((-3.95, 3.95)):
    for i in range(6):
        sx = -6 + i * 2.4
        s_e = empty(f"shield_e{side_idx}_{i}", (sx, side_y, 2.8))
        s_e.rotation_euler = (math.radians(90), 0, 0)
        color = shield_colors[(i + side_idx) % 3]
        # Shield disc
        cyl(f"shield_disc{side_idx}_{i}", r=0.40, depth=0.08, segs=24,
            loc=(0, 0, 0), parent=s_e, mat_=color)
        # Boss (center metal)
        cyl(f"shield_boss{side_idx}_{i}", r=0.10, depth=0.10, segs=16,
            loc=(0, 0, 0.06), parent=s_e, mat_=M_SHIELD_BOSS)
        # Rim metal
        cyl(f"shield_rim{side_idx}_{i}", r=0.42, depth=0.05, segs=24,
            loc=(0, 0, 0), parent=s_e, mat_=M_IRON)
        # 4 radial planks visible
        for r in range(4):
            ang = (r / 4.0) * math.pi/2
            beveled_cube(f"shield_plank{side_idx}_{i}_{r}", (0.78, 0.04, 0.04),
                         loc=(0, 0, 0.045), parent=s_e, mat_=M_WOOD_DARK).rotation_euler = (0, 0, ang)
        shields_obj.append(s_e)

# ============ DRAKKAR MINIATURE (on wall display or table side) ============
drakkar_e = empty("drakkar", loc=(7, 0, 3.5))
drakkar_e.rotation_euler = (0, 0, math.radians(-90))
# Hull (long, curved)
beveled_cube("drk_hull", (3.5, 0.7, 0.40), bevel_offset=0.05,
             loc=(0, 0, 0), parent=drakkar_e, mat_=M_DRAKKAR)
# Curved bow (dragon head end)
bow_e = empty("drk_bow_e", (2.0, 0, 0.20), parent=drakkar_e)
bow_e.rotation_euler = (0, math.radians(-30), 0)
beveled_cube("drk_bow", (1.0, 0.5, 0.45), loc=(0.30, 0, 0), parent=bow_e, mat_=M_DRAKKAR)
# Dragon head (signature drakkar)
smooth_sphere("drk_dragon_head", r=0.25, loc=(0.95, 0, 0.20),
              parent=bow_e, mat_=M_DRAKKAR_GOLD)
smooth_cone("drk_dragon_snout", r1=0.20, r2=0.05, depth=0.35, segs=12,
            loc=(1.20, 0, 0.20), parent=bow_e, mat_=M_DRAKKAR_GOLD).rotation_euler = (0, math.radians(80), 0)
# Eyes red
for side in (-1, 1):
    smooth_sphere(f"drk_eye_{side}", r=0.04, loc=(0.95, side*0.15, 0.25),
                  parent=bow_e, mat_=M_RAVEN_EYE)
# Curved stern
stern_e = empty("drk_stern_e", (-2.0, 0, 0.20), parent=drakkar_e)
stern_e.rotation_euler = (0, math.radians(30), 0)
beveled_cube("drk_stern", (1.0, 0.5, 0.45), loc=(-0.30, 0, 0), parent=stern_e, mat_=M_DRAKKAR)
# Mast + sail
cyl("drk_mast", r=0.04, depth=1.2, segs=10,
    loc=(0, 0, 0.85), parent=drakkar_e, mat_=M_WOOD_DARK)
# Square sail with red stripes
beveled_cube("drk_sail", (0.04, 1.2, 0.85), bevel_offset=0.03,
             loc=(0, 0, 0.85), parent=drakkar_e, mat_=M_DRAKKAR_SAIL)
# 4 sail stripes
for i in range(4):
    if i % 2 == 0:
        beveled_cube(f"drk_stripe{i}", (0.045, 1.18, 0.10),
                     loc=(0.005, 0, 0.50 + i*0.20), parent=drakkar_e, mat_=M_SHIELD_RED)
# Mini shields on hull (6)
for i in range(6):
    sx = -1.0 + i*0.35
    for side in (-1, 1):
        cyl(f"drk_shield{i}_{side}", r=0.10, depth=0.04, segs=14,
            loc=(sx, side*0.40, 0.20), parent=drakkar_e,
            mat_=shield_colors[i % 3])

# ============ COR DE GUERRE (signature instrument warriors) ============
warhorn_e = empty("warhorn", loc=(-7, -3.5, 3.0))
warhorn_e.rotation_euler = (0, math.radians(20), math.radians(30))
# Body curved (5 cone segments forming spiral)
prev = None
for i in range(5):
    r1 = 0.05 + i * 0.04
    r2 = 0.06 + i * 0.04
    seg = smooth_cone(f"horn_seg{i}", r1=r1, r2=r2, depth=0.30, segs=12,
                      loc=(0, 0, i*0.30 - 0.6), parent=warhorn_e, mat_=M_BRONZE)
# Bell at end (flare)
smooth_cone("horn_bell", r1=0.30, r2=0.15, depth=0.30, segs=14,
            loc=(0, 0, 0.95), parent=warhorn_e, mat_=M_BRONZE)
# Decorative band
cyl("horn_band", r=0.13, depth=0.04, segs=14,
    loc=(0, 0, 0.20), parent=warhorn_e, mat_=M_GOLD)

# ============ ODIN STATUE + 2 RAVENS (Huginn & Muninn) ============
odin_base = empty("odin", loc=(0, 3.5, 0))
# Pedestal
beveled_cube("odin_ped", (1.0, 1.0, 0.4), bevel_offset=0.05,
             loc=(0, 0, 0.2), parent=odin_base, mat_=M_STONE_LIT)
# 2 legs
for side_idx, side in enumerate((-1, 1)):
    cyl(f"odin_leg{side_idx}", r=0.13, depth=0.85, segs=10,
        loc=(side*0.15, 0, 0.85), parent=odin_base, mat_=M_ODIN_STONE)
# Torso (massive)
beveled_cube("odin_torso", (0.60, 0.40, 0.95), bevel_offset=0.06,
             loc=(0, 0, 1.75), parent=odin_base, mat_=M_ODIN_STONE)
# Cape
smooth_cone("odin_cape", r1=0.55, r2=0.30, depth=1.0, segs=14,
            loc=(0, 0.10, 1.20), parent=odin_base, mat_=M_ODIN_STONE)
# Head
odin_head_e = empty("odin_head", (0, 0, 2.40), parent=odin_base)
smooth_sphere("odin_head_main", r=0.22, loc=(0,0,0), parent=odin_head_e, mat_=M_ODIN_STONE)
# 1 EYE (one-eyed signature) on right side
smooth_sphere("odin_eye", r=0.05, loc=(0.10, -0.18, 0.05), parent=odin_head_e, mat_=M_DOG_EYE)
# Eye patch (left)
beveled_cube("odin_patch", (0.10, 0.05, 0.08), loc=(-0.10, -0.18, 0.05),
             parent=odin_head_e, mat_=M_LEATHER)
# Long beard
smooth_sphere("odin_beard", r=0.18, loc=(0, -0.12, -0.20),
              parent=odin_head_e, mat_=M_BEARD_BROWN, scale=(1.3, 0.6, 1.5))
# Hat (wide-brimmed traveler hat)
cyl("odin_hat_brim", r=0.40, depth=0.04, segs=18,
    loc=(0, 0, 0.18), parent=odin_head_e, mat_=M_LEATHER)
smooth_cone("odin_hat_top", r1=0.20, r2=0.05, depth=0.35, segs=14,
            loc=(0, 0, 0.35), parent=odin_head_e, mat_=M_LEATHER)
# 2 arms (one holding spear)
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"odin_sh{side_idx}", (side*0.30, 0, 2.20), parent=odin_base)
    sh.rotation_euler = (math.radians(-10), 0, math.radians(side*-20))
    cyl(f"odin_up{side_idx}", r=0.10, depth=0.50, segs=10,
        loc=(0, 0, -0.25), parent=sh, mat_=M_ODIN_STONE)
    cyl(f"odin_fa{side_idx}", r=0.09, depth=0.50, segs=10,
        loc=(0, 0, -0.75), parent=sh, mat_=M_ODIN_STONE)
# SPEAR Gungnir (right side)
spear_e = empty("spear_e", (0.35, -0.30, 1.20), parent=odin_base)
cyl("spear_shaft", r=0.04, depth=2.5, segs=10,
    loc=(0, 0, 0), parent=spear_e, mat_=M_LEATHER)
smooth_cone("spear_tip", r1=0.07, r2=0.005, depth=0.40, segs=10,
            loc=(0, 0, 1.45), parent=spear_e, mat_=M_AXE_HEAD)

# 2 RAVENS (Huginn & Muninn) on Odin's shoulders
ravens = []
for ri, side in enumerate((-1, 1)):
    rav_e = empty(f"raven{ri}", (side*0.25, 0, 2.10), parent=odin_base)
    smooth_sphere(f"rav_body{ri}", r=0.15, loc=(0,0,0),
                  parent=rav_e, mat_=M_RAVEN, scale=(1.6, 0.8, 0.9))
    smooth_sphere(f"rav_head{ri}", r=0.10, loc=(0.18, 0, 0.05),
                  parent=rav_e, mat_=M_RAVEN)
    # Beak
    smooth_cone(f"rav_beak{ri}", r1=0.04, r2=0.005, depth=0.12, segs=8,
                loc=(0.30, 0, 0.02), parent=rav_e, mat_=M_BRONZE)
    # Eye red
    smooth_sphere(f"rav_eye{ri}", r=0.025, loc=(0.22, side*0.08, 0.10),
                  parent=rav_e, mat_=M_RAVEN_EYE)
    # 2 wings folded
    for s in (-1, 1):
        beveled_cube(f"rav_w{ri}_{s}", (0.16, 0.05, 0.18),
                     loc=(0, s*0.10, 0), parent=rav_e, mat_=M_RAVEN)
    # Tail
    beveled_cube(f"rav_tail{ri}", (0.10, 0.04, 0.04),
                 loc=(-0.18, 0, 0), parent=rav_e, mat_=M_RAVEN)
    ravens.append(rav_e)

# ============ 8 WOLFHOUNDS (dogs) under table ============
dogs = []
for di in range(8):
    if di < 4:
        x_pos = -5 + di * 3
        y_pos = -0.3
    else:
        x_pos = -5 + (di-4) * 3
        y_pos = 0.3
    d_e = empty(f"dog{di}", (x_pos, y_pos, 0))
    d_e.rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    mat_choice = M_DOG_GREY if random.random() < 0.5 else M_DOG_BROWN
    # Body lying down
    smooth_sphere(f"dog_body{di}", r=0.25, loc=(0, 0, 0.25),
                  parent=d_e, mat_=mat_choice, scale=(1.8, 0.8, 0.7))
    # Head
    head_e = empty(f"dog_head{di}", (0.40, 0, 0.30), parent=d_e)
    smooth_sphere(f"dog_h{di}", r=0.13, loc=(0,0,0), parent=head_e,
                  mat_=mat_choice, scale=(1.5, 0.9, 0.9))
    # Long ears
    for side in (-1, 1):
        ear = beveled_cube(f"dog_ear{di}_{side}", (0.05, 0.06, 0.15),
                          loc=(side*0.05, -0.05, 0.10), parent=head_e, mat_=mat_choice)
        ear.rotation_euler = (math.radians(20), 0, math.radians(side*15))
    # Snout
    smooth_sphere(f"dog_snout{di}", r=0.08, loc=(0.13, 0, -0.05),
                  parent=head_e, mat_=mat_choice)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"dog_eye{di}_{side}", r=0.03,
                      loc=(0.10, side*0.07, 0.05), parent=head_e, mat_=M_DOG_EYE)
    # 4 short legs (folded under)
    for x_idx, xx in enumerate((-1, 1)):
        for y_idx, yy in enumerate((-1, 1)):
            cyl(f"dog_leg{di}_{x_idx}_{y_idx}", r=0.05, depth=0.18, segs=8,
                loc=(xx*0.15, yy*0.15, 0.10), parent=d_e, mat_=mat_choice)
    # Tail
    tail_e = empty(f"dog_tail{di}_e", (-0.40, 0, 0.25), parent=d_e)
    cyl(f"dog_tail{di}", r=0.04, depth=0.30, segs=10,
        loc=(0, 0, 0), parent=tail_e, mat_=mat_choice).rotation_euler = (math.radians(-30), 0, 0)
    dogs.append({"e": d_e, "tail": tail_e, "head": head_e,
                 "phase": random.uniform(0, math.pi*2)})

# ============ 40 SPARKS (sparks rising from fire) ============
sparks = []
for i in range(40):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(0.1, 0.8)
    sx, sy = rad*math.cos(a), rad*math.sin(a)
    sz = random.uniform(1.0, 4.0)
    sp = smooth_sphere(f"spark{i}", r=random.uniform(0.04, 0.08), segs=8, rings=6,
                      loc=(sx, sy, sz), mat_=M_SPARK)
    sp["_phase"] = random.uniform(0, math.pi*2)
    sp["_speed"] = random.uniform(1.0, 2.5)
    sp["_base_x"] = sx; sp["_base_y"] = sy; sp["_base_z"] = sz
    sparks.append(sp)

# ============ 50 SNOWFLAKES (falling outside) ============
snowflakes = []
for i in range(50):
    sx = random.uniform(-25, 25)
    sy = random.uniform(-15, 15)
    sz = random.uniform(2, 15)
    # Only outside longhouse (skip inside box)
    if abs(sx) < 8.5 and abs(sy) < 4.5:
        # Push to outside
        sy = 4.5 + abs(sy - 4.5) if sy > 0 else -4.5 - abs(sy + 4.5)
    sf = smooth_sphere(f"snowflake{i}", r=random.uniform(0.06, 0.12), segs=8, rings=6,
                      loc=(sx, sy, sz), mat_=M_SNOWFLAKE)
    sf["_phase"] = random.uniform(0, math.pi*2)
    sf["_speed"] = random.uniform(0.8, 1.8)
    sf["_base_x"] = sx; sf["_base_y"] = sy; sf["_base_z"] = sz
    snowflakes.append(sf)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# 14 vikings + chef + scald subtle motions + toast (right arm raised oscillation)
for vi, v in enumerate(vikings):
    phase = vi * 0.4
    base_z = v["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Body subtle bob
        v["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.03
        v["root"].keyframe_insert("location", frame=f)
        # Head turn (laughing/conversation)
        v["head_e"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(8),
                                       0,
                                       math.sin(t * 0.7 + phase) * math.radians(20))
        v["head_e"].keyframe_insert("rotation_euler", frame=f)
        # Right shoulder (toast arm) oscillation
        v["sh1"].rotation_euler = (math.radians(-140) + math.sin(t * 2.5 + phase) * math.radians(15),
                                    0,
                                    math.radians(15) + math.sin(t * 2.5 + phase + 0.3) * math.radians(10))
        v["sh1"].keyframe_insert("rotation_euler", frame=f)

# Chef axe lift (lift axe periodically + Z bob)
base_z_chef = chef["root"].location.z
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    chef["root"].location.z = base_z_chef + math.sin(t * 1.5) * 0.05
    chef["root"].keyframe_insert("location", frame=f)
    # Chef right shoulder lifts axe high
    chef["sh1"].rotation_euler = (math.radians(-130) + math.sin(t * 1.8) * math.radians(30),
                                   0,
                                   math.radians(-15) + math.sin(t * 1.8 + 0.5) * math.radians(15))
    chef["sh1"].keyframe_insert("rotation_euler", frame=f)
    chef["head_e"].rotation_euler = (0, 0, math.sin(t * 0.8) * math.radians(15))
    chef["head_e"].keyframe_insert("rotation_euler", frame=f)

# Scald playing lyre (right arm strumming fast)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    sc_r_sh.rotation_euler = (math.radians(-100) + math.sin(t * 8.0) * math.radians(20),
                               0,
                               math.radians(-30) + math.sin(t * 8.0 + 0.3) * math.radians(10))
    sc_r_sh.keyframe_insert("rotation_euler", frame=f)
    # Body sway with music
    scald_base.rotation_euler = (math.sin(t * 1.5) * math.radians(3),
                                  0,
                                  math.radians(-90) + math.sin(t * 1.2) * math.radians(5))
    scald_base.keyframe_insert("rotation_euler", frame=f)
    scald_head_e.rotation_euler = (math.sin(t * 1.5) * math.radians(5), 0,
                                    math.sin(t * 1.0) * math.radians(10))
    scald_head_e.keyframe_insert("rotation_euler", frame=f)

# Fire animation - flames pulse + embers flicker
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

# Sparks rising from fire
for sp in sparks:
    phase = sp["_phase"]; speed = sp["_speed"]
    bx, by, bz = sp["_base_x"], sp["_base_y"], sp["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        z = bz + (speed * t) % 5.0
        x = bx + math.sin(t * 2.0 + phase) * 0.3
        y = by + math.cos(t * 2.0 + phase) * 0.3
        s = 1 + math.sin(t * 4.0 + phase) * 0.4
        sp.location = (x, y, z)
        sp.scale = (s, s, s)
        sp.keyframe_insert("location", frame=f)
        sp.keyframe_insert("scale", frame=f)

# Cauldron rotate slowly
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    cauldron_e.rotation_euler = (0, 0, t * 0.2)
    cauldron_e.keyframe_insert("rotation_euler", frame=f)

# Dogs tail wave + head turn
for d in dogs:
    phase = d["phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        d["tail"].rotation_euler = (math.radians(-30),
                                     0,
                                     math.sin(t * 3.5 + phase) * math.radians(25))
        d["tail"].keyframe_insert("rotation_euler", frame=f)
        d["head"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(15))
        d["head"].keyframe_insert("rotation_euler", frame=f)

# Ravens occasional small wing flap
for ri, rav_e in enumerate(ravens):
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        # Subtle wing twitch
        s = 1 + math.sin(t * 2.0 + ri) * 0.03
        rav_e.scale = (s, s, s)
        rav_e.keyframe_insert("scale", frame=f)

# Stars twinkle
for star in stars:
    phase = star["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 3.0 + phase) * 0.35
        star.scale = (s, s, s)
        star.keyframe_insert("scale", frame=f)

# Aurora breathe + drift
for ar in aurora_ribbons:
    base_phase = ar["_base_phase"]
    base_y = ar.location.y
    base_z = ar.location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        ar.location.z = base_z + math.sin(t * 0.6 + base_phase) * 0.8
        ar.rotation_euler = (math.sin(t * 0.4 + base_phase) * math.radians(3),
                              math.cos(t * 0.5 + base_phase) * math.radians(3),
                              0)
        s = 1 + math.sin(t * 0.8 + base_phase) * 0.1
        ar.scale = (s, s, s)
        ar.keyframe_insert("location", frame=f)
        ar.keyframe_insert("rotation_euler", frame=f)
        ar.keyframe_insert("scale", frame=f)

# Snowflakes fall + twirl
for sf in snowflakes:
    phase = sf["_phase"]; speed = sf["_speed"]
    bx, by, bz = sf["_base_x"], sf["_base_y"], sf["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        z = bz - (speed * t) % 15
        x = bx + math.sin(t * 0.8 + phase) * 0.5
        y = by + math.cos(t * 0.7 + phase) * 0.5
        sf.location = (x, y, max(-0.2, z))
        sf.rotation_euler = (phase + t * 0.8, phase + t * 0.6, phase + t * 1.0)
        sf.keyframe_insert("location", frame=f)
        sf.keyframe_insert("rotation_euler", frame=f)

# Moon breathe
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 0.5) * 0.04
    moon.scale = (s, s, s)
    moon.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_viking_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_viking_longhouse_feast] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_viking_longhouse_feast] Longhouse + 4 cols runes + cheminée 8 flammes + cauldron + 14 vikings + chef axe + scald lyre + 12 shields + drakkar miniature + war horn + Odin statue spear + 2 ravens + 8 wolfhounds + 16 horns + roast + 40 sparks + 50 snowflakes + 4 aurora + 80 stars")
