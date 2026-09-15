"""
proc_inca_temple_jungle.py — 200e procédural AuroraIA (64e qualité — MILESTONE 200E PROCEDURAL!!!)
Grand temple Inca Machu Picchu pyramide étagée + prêtres + condor + lamas + serpent géant + jungle dense
"""
import bpy, bmesh, math, random, os

random.seed(0x1AC4200)

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

# Wait - I need to fix random.seed: 0x1NCA200 is invalid hex (N is not a hex digit)
# Replaced above to 0x1AC4200

reset()
scene = bpy.context.scene
scene.frame_start = 1; scene.frame_end = 180; scene.render.fps = 30

# Materials
M_SKY = mat("sky", (0.85, 0.55, 0.25, 1.0), 0.0, 0.7, emission=(0.95,0.65,0.30), emission_strength=2.0)
M_SUN = mat("sun", (1.0, 0.85, 0.40, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.40), emission_strength=20.0)
M_CLOUD = mat("cloud", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.85,0.82,0.75), emission_strength=1.5, alpha=0.8)
M_MIST = mat("mist", (0.85, 0.78, 0.65, 1.0), 0.0, 0.65, emission=(0.85,0.78,0.65), emission_strength=1.0, alpha=0.45)
M_GROUND = mat("ground", (0.25, 0.20, 0.12, 1.0), 0.0, 0.85)
M_STONE = mat("stone", (0.55, 0.50, 0.42, 1.0), 0.0, 0.75, emission=(0.45,0.40,0.32), emission_strength=0.4)
M_STONE_DARK = mat("stone_dark", (0.35, 0.30, 0.25, 1.0), 0.0, 0.85)
M_STONE_GOLD = mat("stone_gold", (0.75, 0.55, 0.30, 1.0), 0.5, 0.40, emission=(0.65,0.45,0.25), emission_strength=0.6)
M_GLYPH = mat("glyph", (1.0, 0.65, 0.20, 1.0), 0.3, 0.30, emission=(1.0,0.65,0.20), emission_strength=8.0)
M_GOLD = mat("gold", (1.0, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.22), emission_strength=1.5)
M_GOLD_BRIGHT = mat("gold_b", (1.0, 0.85, 0.35, 1.0), 0.95, 0.15, emission=(1.0,0.85,0.40), emission_strength=3.0)

# Jungle
M_TRUNK = mat("trunk", (0.30, 0.20, 0.12, 1.0), 0.0, 0.85)
M_LEAF = mat("leaf", (0.18, 0.50, 0.22, 1.0), 0.0, 0.65, emission=(0.15,0.45,0.20), emission_strength=0.4)
M_LEAF_LIGHT = mat("leaf_l", (0.30, 0.65, 0.28, 1.0), 0.0, 0.60, emission=(0.25,0.60,0.25), emission_strength=0.6)
M_BROMELIA = mat("brom", (1.0, 0.30, 0.40, 1.0), 0.0, 0.50, emission=(0.95,0.30,0.35), emission_strength=1.5)
M_BROMELIA_YELLOW = mat("brom_y", (1.0, 0.80, 0.25, 1.0), 0.0, 0.50, emission=(1.0,0.80,0.25), emission_strength=1.8)
M_FLOWER = mat("flower", (0.85, 0.30, 0.65, 1.0), 0.0, 0.55, emission=(0.80,0.30,0.60), emission_strength=1.2)
M_WATER = mat("water", (0.30, 0.55, 0.65, 0.7), 0.4, 0.10, emission=(0.40,0.65,0.75), emission_strength=2.0, alpha=0.65)
M_FOAM = mat("foam", (0.95, 0.98, 1.0, 1.0), 0.0, 0.30, emission=(0.90,0.95,1.0), emission_strength=1.5)

# Priests
M_PRIEST_ROBE = mat("priest_robe", (0.60, 0.20, 0.15, 1.0), 0.0, 0.55, emission=(0.55,0.18,0.13), emission_strength=0.4)
M_PRIEST_ROBE_GOLD = mat("priest_robe_g", (0.85, 0.55, 0.20, 1.0), 0.2, 0.45, emission=(0.78,0.50,0.18), emission_strength=0.5)
M_FEATHER_RED = mat("feather_r", (0.85, 0.15, 0.20, 1.0), 0.0, 0.50, emission=(0.80,0.15,0.18), emission_strength=0.6)
M_FEATHER_YELLOW = mat("feather_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.50, emission=(0.95,0.80,0.20), emission_strength=0.7)
M_FEATHER_BLUE = mat("feather_b", (0.20, 0.55, 0.85, 1.0), 0.0, 0.50, emission=(0.18,0.50,0.80), emission_strength=0.6)
M_FEATHER_GREEN = mat("feather_g", (0.20, 0.75, 0.40, 1.0), 0.0, 0.50, emission=(0.18,0.70,0.35), emission_strength=0.7)
M_SKIN_INCA = mat("skin_inca", (0.75, 0.55, 0.38, 1.0), 0.0, 0.60, emission=(0.65,0.45,0.30), emission_strength=0.3)
M_HAIR_INCA = mat("hair_inca", (0.10, 0.06, 0.04, 1.0), 0.0, 0.85)

# Statues
M_JAGUAR = mat("jaguar", (0.85, 0.65, 0.25, 1.0), 0.4, 0.30, emission=(0.75,0.55,0.22), emission_strength=0.7)
M_JAGUAR_SPOT = mat("jaguar_spot", (0.20, 0.10, 0.05, 1.0), 0.0, 0.75)
M_CONDOR_STAT = mat("condor_stat", (0.30, 0.20, 0.10, 1.0), 0.4, 0.45, emission=(0.30,0.20,0.10), emission_strength=0.5)
M_SERPENT_STAT = mat("serpent_stat", (0.55, 0.30, 0.18, 1.0), 0.4, 0.35, emission=(0.50,0.28,0.18), emission_strength=0.6)

# Condor flying
M_CONDOR = mat("condor", (0.08, 0.06, 0.06, 1.0), 0.0, 0.55, emission=(0.10,0.08,0.08), emission_strength=0.3)
M_CONDOR_NECK = mat("condor_neck", (0.92, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.85,0.82,0.78), emission_strength=0.5)
M_CONDOR_HEAD = mat("condor_head", (0.85, 0.55, 0.30, 1.0), 0.0, 0.55, emission=(0.80,0.50,0.28), emission_strength=0.6)
M_CONDOR_EYE = mat("condor_eye", (1.0, 0.50, 0.10, 1.0), 0.0, 0.20, emission=(1.0,0.50,0.10), emission_strength=8.0)

# Lamas
M_LAMA = mat("lama", (0.95, 0.92, 0.82, 1.0), 0.0, 0.65, emission=(0.85,0.82,0.72), emission_strength=0.4)
M_LAMA_DARK = mat("lama_dark", (0.45, 0.30, 0.20, 1.0), 0.0, 0.65)
M_LAMA_EYE = mat("lama_eye", (0.10, 0.06, 0.04, 1.0), 0.2, 0.20)

# Dog xolo
M_XOLO = mat("xolo", (0.18, 0.10, 0.08, 1.0), 0.0, 0.60, emission=(0.18,0.10,0.08), emission_strength=0.3)

# Serpent géant
M_SERPENT_BODY = mat("serp_body", (0.55, 0.85, 0.30, 1.0), 0.3, 0.30, emission=(0.50,0.80,0.30), emission_strength=2.5)
M_SERPENT_BELLY = mat("serp_belly", (0.95, 0.85, 0.40, 1.0), 0.0, 0.50, emission=(0.85,0.78,0.38), emission_strength=1.0)
M_SERPENT_EYE = mat("serp_eye", (1.0, 0.30, 0.10, 1.0), 0.0, 0.15, emission=(1.0,0.30,0.10), emission_strength=10.0)
M_SCALE_GOLD = mat("scale_gold", (1.0, 0.78, 0.30, 1.0), 0.95, 0.20, emission=(0.95,0.72,0.28), emission_strength=1.2)

# Offerings / Altar
M_ALTAR_STONE = mat("altar_stone", (0.45, 0.40, 0.32, 1.0), 0.0, 0.70, emission=(0.40,0.35,0.28), emission_strength=0.6)
M_BLOOD = mat("blood", (0.55, 0.10, 0.10, 1.0), 0.0, 0.45, emission=(0.50,0.10,0.08), emission_strength=0.8)
M_CHALICE = mat("chalice", (0.95, 0.78, 0.30, 1.0), 0.95, 0.15, emission=(0.90,0.72,0.28), emission_strength=1.5)

# Pollen / mist particles
M_POLLEN = mat("pollen", (1.0, 0.95, 0.55, 1.0), 0.0, 0.30, emission=(1.0,0.95,0.55), emission_strength=8.0)

# 200 marker indicator
M_MARKER_200 = mat("marker_200", (1.0, 0.85, 0.30, 1.0), 0.95, 0.05, emission=(1.0,0.85,0.30), emission_strength=15.0)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=95, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.65))
sky.scale = (1,1,0.65)
# Sun (large golden)
sun = smooth_sphere("sun", r=5.5, loc=(0, 38, 26), mat_=M_SUN)
# Sun rays (8 cones)
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    ray = smooth_cone(f"sunray{i}", r1=2.5, r2=0.5, depth=15, segs=10,
                     loc=(0 + 4*math.cos(a), 38, 26 + 4*math.sin(a)),
                     mat_=mat(f"ray{i}", (1.0,0.85,0.40,1), 0, 0.05,
                              emission=(1.0,0.85,0.40), emission_strength=8.0, alpha=0.4))
    ray.rotation_euler = (math.radians(90 + a*5), 0, a)

# 8 low clouds (signature Machu Picchu) drift
clouds = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = random.uniform(15, 25)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(6, 12)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(4):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.0, 3.5),
                      loc=(random.uniform(-2,2), random.uniform(-1.5,1.5), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ GROUND ============
ground = beveled_cube("ground", (70, 70, 0.4), bevel_offset=0.05, loc=(0, 0, -0.2), mat_=M_GROUND)
# Stone path leading to pyramid
beveled_cube("path", (4, 25, 0.10), loc=(0, -12, 0.05), mat_=M_STONE)

# ============ PYRAMIDE INCA ÉTAGÉE 7 niveaux (Machu Picchu style) ============
pyramid_e = empty("pyramid", loc=(0, 0, 0))

# 7 levels stacked
level_sizes = [
    (16, 16, 1.2),  # base
    (14, 14, 1.0),
    (12, 12, 1.0),
    (10, 10, 1.0),
    (8, 8, 1.0),
    (6, 6, 0.9),
    (4, 4, 0.8),
]
cum_z = 0
for i, (sx, sy, sz) in enumerate(level_sizes):
    level = beveled_cube(f"pyramid_lvl{i}", (sx, sy, sz), bevel_offset=0.05,
                        loc=(0, 0, cum_z + sz/2), parent=pyramid_e,
                        mat_=M_STONE if i % 2 == 0 else M_STONE_DARK)
    cum_z += sz

total_h = cum_z

# 200 MARCHES (signature pyramide escalier)
# Front staircase from base to top
for s in range(200):
    # Distribute steps across 7 levels - 28 steps per level approximately
    level_idx = min(6, s // 28)
    step_in_level = s % 28
    # Step within level
    base_z_level = sum(level_sizes[j][2] for j in range(level_idx))
    step_z = base_z_level + (step_in_level / 28.0) * level_sizes[level_idx][2]
    # Step Y depends on level (narrower at top)
    level_sx = level_sizes[level_idx][0]
    step_y = -level_sx / 2 + (level_sx * 0.30)  # front of level
    step_w = level_sizes[level_idx][0] * 0.35
    # Emissive every 10th step (signature 200 marches éclairées)
    is_emissive = (s % 10 == 0)
    step = beveled_cube(f"step{s}", (step_w, 0.30, 0.10), bevel_offset=0.015,
                       loc=(0, step_y, step_z), parent=pyramid_e,
                       mat_=M_GLYPH if is_emissive else M_STONE_DARK)

# GRANDE PORTE TRAPÈZE (signature Inca authentique)
door_e = empty("door", (0, -7.5, 0.5), parent=pyramid_e)
# Trapezoidal door (wider at bottom)
# 2 vertical posts angled
for side in (-1, 1):
    post = beveled_cube(f"door_post_{side}", (0.3, 0.40, 2.5), bevel_offset=0.03,
                       loc=(side*0.85, 0, 1.25), parent=door_e, mat_=M_STONE_GOLD)
    post.rotation_euler = (0, math.radians(side*-5), 0)  # angled inward (trapezoid)
# Top lintel
beveled_cube("door_lintel", (1.5, 0.40, 0.40), loc=(0, 0, 2.65), parent=door_e, mat_=M_STONE_GOLD)
# Inside dark
beveled_cube("door_inside", (1.0, 0.10, 2.3), loc=(0, 0, 1.20), parent=door_e, mat_=M_STONE_DARK)

# Top platform (sacred area)
top_platform = beveled_cube("top_platform", (5, 5, 0.30), bevel_offset=0.05,
                            loc=(0, 0, total_h + 0.15), parent=pyramid_e, mat_=M_STONE_GOLD)

# ============ TRINITÉ INCA STATUES (Jaguar + Condor + Serpent) ============
# JAGUAR statue (left)
jaguar_e = empty("jaguar_stat", loc=(-1.8, -0.5, total_h + 0.4))
# Body
beveled_cube("jag_body", (0.7, 1.5, 0.45), bevel_offset=0.06,
             loc=(0, 0, 0.30), parent=jaguar_e, mat_=M_JAGUAR)
# Head
smooth_sphere("jag_head", r=0.30, loc=(0, 0.85, 0.50),
              parent=jaguar_e, mat_=M_JAGUAR, scale=(1, 1.2, 0.9))
# 4 legs
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"jag_leg{x_idx}{y_idx}", r=0.12, depth=0.55, segs=10,
            loc=(x*0.30, y*0.55, 0.10), parent=jaguar_e, mat_=M_JAGUAR)
# Tail
cyl("jag_tail", r=0.08, depth=0.70, segs=10,
    loc=(0, -0.85, 0.45), parent=jaguar_e, mat_=M_JAGUAR).rotation_euler = (math.radians(80), 0, 0)
# Spots (8)
for i in range(8):
    smooth_sphere(f"jag_spot{i}", r=0.08, loc=(random.uniform(-0.3, 0.3),
                                                random.uniform(-0.6, 0.6),
                                                0.50), parent=jaguar_e,
                  mat_=M_JAGUAR_SPOT, scale=(1, 1, 0.4))
# Eyes (yellow émissif)
for side in (-1, 1):
    smooth_sphere(f"jag_eye_{side}", r=0.05, loc=(side*0.10, 1.05, 0.55),
                  parent=jaguar_e, mat_=M_CONDOR_EYE)
# Ears
for side in (-1, 1):
    smooth_cone(f"jag_ear_{side}", r1=0.06, r2=0.005, depth=0.12, segs=8,
                loc=(side*0.15, 0.75, 0.80), parent=jaguar_e, mat_=M_JAGUAR).rotation_euler = (math.radians(-10), 0, math.radians(side*15))

# CONDOR statue (right)
condor_stat_e = empty("condor_stat", loc=(1.8, -0.5, total_h + 0.4))
# Body
beveled_cube("cs_body", (0.5, 0.85, 0.85), bevel_offset=0.05,
             loc=(0, 0, 0.45), parent=condor_stat_e, mat_=M_CONDOR_STAT)
# Wings outspread
for side in (-1, 1):
    w = beveled_cube(f"cs_wing_{side}", (1.2, 0.05, 0.55), bevel_offset=0.04,
                    loc=(side*0.85, 0, 0.50), parent=condor_stat_e, mat_=M_CONDOR_STAT)
    w.rotation_euler = (0, math.radians(side*10), 0)
# Head with hooked beak
smooth_sphere("cs_head", r=0.20, loc=(0, 0.50, 1.10),
              parent=condor_stat_e, mat_=M_CONDOR_HEAD)
smooth_cone("cs_beak", r1=0.10, r2=0.02, depth=0.20, segs=10,
            loc=(0, 0.70, 1.05), parent=condor_stat_e, mat_=M_CONDOR_HEAD).rotation_euler = (math.radians(70), 0, 0)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"cs_eye_{side}", r=0.04, loc=(side*0.08, 0.60, 1.15),
                  parent=condor_stat_e, mat_=M_CONDOR_EYE)

# SERPENT statue (center, in front of door)
serpent_stat_e = empty("serpent_stat", loc=(0, -0.3, total_h + 0.35))
# Coiled body (5 ring segments)
for i in range(5):
    r = 0.40 - i*0.05
    h = 0.18
    seg = smooth_sphere(f"ss_coil{i}", r=r, segs=24, rings=14,
                       loc=(0, 0, i*h), parent=serpent_stat_e, mat_=M_SERPENT_STAT,
                       scale=(1, 1, 0.5))
# Head raised on top
ss_head_e = empty("ss_head_e", (0, 0.30, 0.95), parent=serpent_stat_e)
smooth_sphere("ss_head", r=0.18, segs=18, rings=12, loc=(0, 0, 0),
              parent=ss_head_e, mat_=M_SERPENT_STAT, scale=(1, 1.5, 0.8))
# Eyes
for side in (-1, 1):
    smooth_sphere(f"ss_eye_{side}", r=0.04, loc=(side*0.08, 0.18, 0.05),
                  parent=ss_head_e, mat_=M_CONDOR_EYE)

# ============ ALTAR DE SACRIFICE (centre top platform) ============
altar_e = empty("altar", loc=(0, 0.5, total_h + 0.30))
# Main altar stone
beveled_cube("altar_main", (2.2, 1.5, 0.85), bevel_offset=0.06,
             loc=(0, 0, 0.45), parent=altar_e, mat_=M_ALTAR_STONE)
# 4 corner posts
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        beveled_cube(f"altar_post{x_idx}{y_idx}", (0.20, 0.20, 1.20),
                     loc=(x*1.0, y*0.65, 0.60), parent=altar_e, mat_=M_STONE_GOLD)
# Chalice on altar
chalice_e = empty("chalice_e", (0, 0, 0.95), parent=altar_e)
cyl("chalice_stem", r=0.06, depth=0.30, segs=12,
    loc=(0, 0, 0), parent=chalice_e, mat_=M_CHALICE)
smooth_sphere("chalice_cup", r=0.20, loc=(0, 0, 0.25),
              parent=chalice_e, mat_=M_CHALICE, scale=(1, 1, 0.7))
# Blood pulsing
smooth_sphere("chalice_blood", r=0.16, loc=(0, 0, 0.30),
              parent=chalice_e, mat_=M_BLOOD, scale=(1, 1, 0.4))
# Chalice base disc
cyl("chalice_base", r=0.15, depth=0.04, segs=14,
    loc=(0, 0, -0.16), parent=chalice_e, mat_=M_CHALICE)

# OFFERINGS gold (8 piles around altar)
offerings = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    ox = 0.7 * math.cos(a)
    oy = 0.7 * math.sin(a)
    o_e = empty(f"offering_e{i}", (ox, oy, 0.92), parent=altar_e)
    # 3-4 gold spheres mound
    for j in range(4):
        smooth_sphere(f"offering{i}_{j}", r=random.uniform(0.05, 0.08),
                      loc=(random.uniform(-0.10, 0.10), random.uniform(-0.10, 0.10), 0.05*j),
                      parent=o_e, mat_=M_GOLD_BRIGHT)
    offerings.append(o_e)

# 6 PRÊTRES en cape plumes (procession autour autel)
def make_priest(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg{side_idx}", r=0.11, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.42), parent=base, mat_=M_PRIEST_ROBE)
        beveled_cube(f"{name}_foot{side_idx}", (0.18, 0.28, 0.08),
                     loc=(side*0.13, 0.05, 0.04), parent=base, mat_=M_STONE_DARK)
    # Robe (long flowing cone)
    smooth_cone(f"{name}_robe", r1=0.55, r2=0.25, depth=1.3, segs=18,
                loc=(0, 0, 0.65), parent=base, mat_=M_PRIEST_ROBE)
    # Belt/Sash gold
    cyl(f"{name}_sash", r=0.45, depth=0.10, segs=18,
        loc=(0, 0, 1.15), parent=base, mat_=M_PRIEST_ROBE_GOLD)
    # Torso (smaller, upper body)
    smooth_sphere(f"{name}_torso", r=0.32, loc=(0, 0, 1.55),
                  parent=base, mat_=M_PRIEST_ROBE, scale=(1, 0.7, 1.3))
    # Neck
    cyl(f"{name}_neck", r=0.08, depth=0.15, segs=10,
        loc=(0, 0, 1.95), parent=base, mat_=M_SKIN_INCA)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 2.15), parent=base)
    smooth_sphere(f"{name}_head", r=0.20, segs=20, rings=14, loc=(0,0,0),
                  parent=head_e, mat_=M_SKIN_INCA)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.025,
                      loc=(side*0.07, -0.16, 0.03), parent=head_e,
                      mat_=mat(f"{name}_ew", (1,1,1,1), 0, 0.3))
    # Hair (cut straight)
    smooth_sphere(f"{name}_hair", r=0.22, loc=(0, 0.03, 0.05),
                  parent=head_e, mat_=M_HAIR_INCA, scale=(1, 1, 0.6))

    # CAPE FEATHER (large, signature Inca!)
    cape_e = empty(f"{name}_cape_e", (0, 0.20, 1.85), parent=base)
    # 16 feathers in fan pattern
    feather_colors = [M_FEATHER_RED, M_FEATHER_YELLOW, M_FEATHER_BLUE, M_FEATHER_GREEN]
    for fi in range(16):
        angle = (fi / 15.0) * math.pi - math.pi/2  # -90 to +90 deg
        feather_x = 0.55 * math.sin(angle) * 0.8
        feather_y = 0.55 * math.sin(angle) * 0.3
        feather_z = 0.55 * math.cos(angle) * 0.4
        col = feather_colors[fi % 4]
        f_obj = beveled_cube(f"{name}_feather{fi}", (0.04, 0.04, 0.55), bevel_offset=0.02,
                            loc=(feather_x, feather_y, -0.05 - feather_z),
                            parent=cape_e, mat_=col)
        f_obj.rotation_euler = (math.radians(angle*math.degrees(0.3)),
                                math.radians(angle*math.degrees(0.2)),
                                angle)
    # Headdress feathers (3 tall feathers on head)
    for fi in range(3):
        col = [M_FEATHER_YELLOW, M_FEATHER_RED, M_FEATHER_BLUE][fi]
        f_obj = beveled_cube(f"{name}_hf{fi}", (0.05, 0.06, 0.60), bevel_offset=0.02,
                            loc=((fi-1)*0.10, 0.03, 0.35), parent=head_e, mat_=col)
        f_obj.rotation_euler = (math.radians(-10 + fi*5), 0, math.radians((fi-1)*8))
    # Gold disc pendant
    cyl(f"{name}_pendant", r=0.10, depth=0.03, segs=14,
        loc=(0, -0.20, 1.70), parent=base, mat_=M_GOLD_BRIGHT)
    # 2 ARMS holding offering bowl (in front)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.80), parent=base)
        sh.rotation_euler = (math.radians(-70), 0, math.radians(side*-15))
        cyl(f"{name}_up{side_idx}", r=0.08, depth=0.40, segs=10,
            loc=(0, 0, -0.20), parent=sh, mat_=M_PRIEST_ROBE)
        el = empty(f"{name}_el{side_idx}", (0, 0, -0.42), parent=sh)
        el.rotation_euler = (math.radians(50), 0, 0)
        cyl(f"{name}_fa{side_idx}", r=0.07, depth=0.38, segs=10,
            loc=(0, 0, -0.20), parent=el, mat_=M_SKIN_INCA)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07,
                      loc=(0, 0, -0.42), parent=el, mat_=M_SKIN_INCA)
    return {"root": base, "head_e": head_e, "cape_e": cape_e}

priests = []
priest_positions = []
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    px = 1.8 * math.cos(a)
    py = 1.8 * math.sin(a)
    priest_positions.append((px, py))
    p = make_priest(f"priest{i}", (px, py, total_h + 0.30), facing=a + math.pi)
    priests.append(p)

# 100 GLYPHS on pyramid walls (emissive)
glyph_count = 0
for level_idx in range(6):
    base_z_level = sum(level_sizes[j][2] for j in range(level_idx))
    next_z_level = base_z_level + level_sizes[level_idx][2]
    level_sx = level_sizes[level_idx][0]
    # 4 walls per level, ~4 glyphs per wall
    for wall in range(4):
        for g in range(4):
            if glyph_count >= 100:
                break
            wall_a = (wall / 4.0) * math.pi * 2
            wx = (level_sx/2 + 0.02) * math.cos(wall_a)
            wy = (level_sx/2 + 0.02) * math.sin(wall_a)
            wz = base_z_level + 0.2 + g * (level_sizes[level_idx][2] / 5)
            # Glyph as small beveled cube on wall
            glyph = beveled_cube(f"glyph{glyph_count}", (0.20, 0.10, 0.20),
                                bevel_offset=0.02,
                                loc=(wx, wy, wz), parent=pyramid_e, mat_=M_GLYPH)
            glyph.rotation_euler = (0, 0, wall_a)
            glyph["_phase"] = random.uniform(0, math.pi*2)
            glyph_count += 1

# ============ JUNGLE DENSE (25 trees) ============
trees = []
def make_jungle_tree(name, loc, height=8, scale=1.0):
    base = empty(name, loc)
    # Trunk 5-seg
    for i in range(5):
        r1 = (0.40 - i*0.04) * scale
        r2 = (0.36 - i*0.04) * scale
        h = height / 5 * scale
        seg = smooth_cone(f"{name}_t{i}", r1=r1, r2=r2, depth=h, segs=14,
                          loc=(0, 0, (i+0.5)*h), parent=base, mat_=M_TRUNK)
        seg.rotation_euler = (math.radians(random.uniform(-3,3)),
                              math.radians(random.uniform(-3,3)), 0)
    # Canopy spread (8 leaf clusters)
    top_z = height * scale
    for j in range(8):
        a = (j / 8.0) * math.pi * 2
        rad = random.uniform(1.2, 2.0) * scale
        smooth_sphere(f"{name}_canopy{j}", r=random.uniform(1.0, 1.6) * scale,
                      loc=(rad*math.cos(a), rad*math.sin(a), top_z + random.uniform(-0.5, 0.5)),
                      parent=base,
                      mat_=M_LEAF_LIGHT if random.random() < 0.3 else M_LEAF)
    return base

for i in range(25):
    a = random.uniform(0, math.pi*2)
    # Avoid pyramid area (rad > 12)
    rad = random.uniform(14, 28)
    tx, ty = rad*math.cos(a), rad*math.sin(a)
    trees.append(make_jungle_tree(f"tree{i}", (tx, ty, 0),
                                   height=random.uniform(6, 10),
                                   scale=random.uniform(0.9, 1.2)))

# Bromélias émissives (20) sur sol et arbres
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(10, 25)
    bx = rad * math.cos(a)
    by = rad * math.sin(a)
    bz = random.uniform(0.2, 4)
    color = M_BROMELIA if random.random() < 0.5 else M_BROMELIA_YELLOW
    # Star-shaped bromélia (8 petals radiating)
    for j in range(8):
        a2 = (j / 8.0) * math.pi * 2
        petal = smooth_cone(f"brom{i}_{j}", r1=0.06, r2=0.01, depth=0.25, segs=8,
                            loc=(bx + 0.15*math.cos(a2), by + 0.15*math.sin(a2), bz),
                            mat_=color)
        petal.rotation_euler = (math.radians(60*math.cos(a2)),
                                math.radians(60*math.sin(a2)), 0)

# Tropical flowers (15)
for i in range(15):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 26)
    fx = rad*math.cos(a)
    fy = rad*math.sin(a)
    smooth_sphere(f"flower{i}", r=0.20, loc=(fx, fy, 0.15), mat_=M_FLOWER,
                  scale=(1, 1, 0.4))

# 2 CASCADES (waterfalls from elevated rocks)
cascades = []
for ci in range(2):
    cx = -15 if ci == 0 else 15
    cy = 15 if ci == 0 else -10
    cascade_e = empty(f"cascade{ci}", (cx, cy, 0))
    # Rock support
    smooth_sphere(f"cascade_rock{ci}", r=2.5, loc=(0, 0, 1.5),
                  parent=cascade_e, mat_=M_STONE_DARK, scale=(1, 1, 0.8))
    # Water column (6 segs falling)
    for i in range(6):
        seg = beveled_cube(f"cascade_seg{ci}_{i}", (1.2, 0.30, 1.0),
                          bevel_offset=0.08,
                          loc=(0, 1.5, 3 - i*0.95), parent=cascade_e, mat_=M_WATER)
        seg["_base_z"] = seg.location.z
    # Spray pool at base
    smooth_sphere(f"cascade_pool{ci}", r=2.0, loc=(0, 2.0, 0.05),
                  parent=cascade_e, mat_=M_WATER, scale=(1.2, 1.0, 0.1))
    # 4 foam blobs at base
    for j in range(4):
        a = (j / 4.0) * math.pi * 2
        smooth_sphere(f"cascade_foam{ci}_{j}", r=0.35,
                      loc=(0.8*math.cos(a), 2.0+0.6*math.sin(a), 0.15),
                      parent=cascade_e, mat_=M_FOAM)
    cascades.append(cascade_e)

# ============ CONDOR FLYING (massive) ============
condor_e = empty("condor_flying", loc=(10, 15, 18))
condor_e.rotation_euler = (0, 0, math.radians(-45))
# Body
smooth_sphere("condor_body", r=0.85, segs=22, rings=14, loc=(0,0,0),
              parent=condor_e, mat_=M_CONDOR, scale=(2.0, 1.0, 0.9))
# Neck (white ruff)
smooth_sphere("condor_neck", r=0.40, loc=(1.0, 0, 0.10),
              parent=condor_e, mat_=M_CONDOR_NECK, scale=(1, 1.3, 0.8))
# Head with hooked beak
smooth_sphere("condor_head", r=0.25, loc=(1.55, 0, 0.20),
              parent=condor_e, mat_=M_CONDOR_HEAD)
# Comb on head (signature)
beveled_cube("condor_comb", (0.04, 0.10, 0.20), loc=(1.55, 0, 0.45),
             parent=condor_e, mat_=M_CONDOR_HEAD)
# Beak hooked
smooth_cone("condor_beak", r1=0.10, r2=0.02, depth=0.30, segs=10,
            loc=(1.78, 0, 0.10), parent=condor_e, mat_=M_CONDOR_HEAD).rotation_euler = (math.radians(80), 0, 0)
# Eye
smooth_sphere("condor_eye", r=0.06, loc=(1.65, -0.18, 0.25),
              parent=condor_e, mat_=M_CONDOR_EYE)
# WINGS HUGE outspread (signature condor)
condor_wings = []
for side_idx, side in enumerate((-1, 1)):
    w_sh = empty(f"condor_wsh{side_idx}", (0, side*0.55, 0), parent=condor_e)
    # Inner wing (broad)
    beveled_cube(f"condor_win{side_idx}", (1.5, 1.8, 0.10), bevel_offset=0.04,
                 loc=(0, side*0.9, 0), parent=w_sh, mat_=M_CONDOR)
    # Outer wing
    w_outer = empty(f"condor_wout{side_idx}", (0, side*1.8, 0), parent=w_sh)
    beveled_cube(f"condor_wout_b{side_idx}", (1.2, 1.6, 0.08),
                 loc=(0, side*0.8, 0), parent=w_outer, mat_=M_CONDOR)
    # Primary feathers (4 long tips)
    for ti in range(4):
        beveled_cube(f"condor_prim{side_idx}_{ti}", (0.20, 0.80, 0.04),
                     loc=(0.4 - ti*0.30, side*1.5, 0), parent=w_outer, mat_=M_CONDOR)
    condor_wings.append((w_sh, w_outer, side))
# Tail feathers (5 fanned)
for ti in range(5):
    angle = (ti - 2) * 0.15
    beveled_cube(f"condor_tail{ti}", (0.06, 0.50, 0.05), bevel_offset=0.02,
                 loc=(-1.2, math.sin(angle)*0.20, math.cos(angle)*0.2 - 0.05),
                 parent=condor_e, mat_=M_CONDOR).rotation_euler = (angle, 0, 0)
# Feet (tucked)
for side in (-1, 1):
    cyl(f"condor_foot_{side}", r=0.04, depth=0.30, segs=8,
        loc=(-0.5, side*0.20, -0.30), parent=condor_e, mat_=M_CONDOR_HEAD)

# ============ 4 LAMAS ============
def make_lama(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body wool
    smooth_sphere(f"{name}_body", r=0.45, segs=20, rings=14, loc=(0,0,1.0),
                  parent=base, mat_=M_LAMA, scale=(1.5, 0.85, 1.0))
    # Long neck (curved up)
    neck_e = empty(f"{name}_neck_e", (0.5, 0, 1.1), parent=base)
    for i in range(3):
        cyl(f"{name}_neck{i}", r=0.13, depth=0.30, segs=12,
            loc=(0.10*i, 0, 0.20*i + 0.15), parent=neck_e, mat_=M_LAMA)
    # Head
    head_e = empty(f"{name}_head_e", (0.50, 0, 0.75), parent=neck_e)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=12, loc=(0,0,0),
                  parent=head_e, mat_=M_LAMA, scale=(1, 1.4, 0.8))
    # Ears (pointed)
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear_{side}", r1=0.05, r2=0.005, depth=0.20, segs=8,
                         loc=(side*0.08, 0.05, 0.18), parent=head_e, mat_=M_LAMA)
        ear.rotation_euler = (math.radians(-10), math.radians(side*15), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.04,
                      loc=(side*0.07, -0.15, 0.05), parent=head_e, mat_=M_LAMA_EYE)
    # Snout
    smooth_sphere(f"{name}_snout", r=0.08, loc=(0, -0.20, -0.06),
                  parent=head_e, mat_=M_LAMA_DARK)
    # 4 legs
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.06, depth=0.80, segs=10,
                loc=(x*0.20, y*0.30, 0.40), parent=base, mat_=M_LAMA)
            # Hooves
            beveled_cube(f"{name}_hoof{x_idx}{y_idx}", (0.10, 0.12, 0.08),
                         loc=(x*0.20, y*0.30, 0.04), parent=base, mat_=M_LAMA_DARK)
    # Tail
    cyl(f"{name}_tail", r=0.05, depth=0.20, segs=10,
        loc=(-0.55, 0, 1.10), parent=base, mat_=M_LAMA).rotation_euler = (math.radians(-30), 0, 0)
    return {"root": base, "head_e": head_e}

lamas = []
for i in range(4):
    a = (i / 4.0) * math.pi * 2 + 0.5
    rad = 9
    lx, ly = rad*math.cos(a), rad*math.sin(a)
    l = make_lama(f"lama{i}", (lx, ly, 0), facing=a + math.pi/2)
    lamas.append(l)

# 2 XOLO DOGS (Mexican hairless dog - actually Peruvian Inca dog)
xolos = []
for i in range(2):
    x = -3 + i * 6
    y = -5
    x_e = empty(f"xolo{i}", (x, y, 0))
    # Body slim hairless
    smooth_sphere(f"xolo_body{i}", r=0.20, segs=18, rings=12, loc=(0,0,0.45),
                  parent=x_e, mat_=M_XOLO, scale=(1.5, 0.8, 0.8))
    # Head
    smooth_sphere(f"xolo_h{i}", r=0.13, loc=(0.30, 0, 0.55),
                  parent=x_e, mat_=M_XOLO)
    # Pointed ears
    for side in (-1, 1):
        smooth_cone(f"xolo_ear_{i}_{side}", r1=0.04, r2=0.005, depth=0.10, segs=8,
                    loc=(side*0.06, 0.32, 0.65), parent=x_e, mat_=M_XOLO).rotation_euler = (math.radians(-15), math.radians(side*10), 0)
    # 4 legs
    for x_idx, xx in enumerate((-1, 1)):
        for y_idx, yy in enumerate((-1, 1)):
            cyl(f"xolo_leg{i}_{x_idx}{y_idx}", r=0.03, depth=0.40, segs=8,
                loc=(xx*0.10, yy*0.13, 0.20), parent=x_e, mat_=M_XOLO)
    # Tail (curled up)
    cyl(f"xolo_tail{i}", r=0.03, depth=0.20, segs=8,
        loc=(-0.28, 0, 0.55), parent=x_e, mat_=M_XOLO).rotation_euler = (math.radians(-45), 0, 0)
    xolos.append(x_e)

# ============ SERPENT GÉANT émissif (rampant à travers la scène) ============
serpent_e = empty("serpent_giant", loc=(0, 0, 0))
# 12 segments sinusoïdal
serpent_segs = []
for i in range(12):
    t = i / 11.0
    sx = -18 + t * 36  # span -18 to +18
    sy = math.sin(t * math.pi * 2.5) * 4 + 5  # serpentine
    sz = 0.5
    r = 0.5 - abs(t - 0.4) * 0.4  # thicker in middle
    seg = smooth_sphere(f"serp_seg{i}", r=max(0.15, r), segs=18, rings=12,
                       loc=(sx, sy, sz), parent=serpent_e, mat_=M_SERPENT_BODY,
                       scale=(1, 1.3, 0.7))
    # Belly underside
    smooth_sphere(f"serp_belly{i}", r=max(0.12, r*0.8), loc=(sx, sy, sz-0.1),
                  parent=serpent_e, mat_=M_SERPENT_BELLY, scale=(0.8, 1.0, 0.4))
    # Gold scale bands every 3 segs
    if i % 3 == 0 and r > 0.2:
        cyl(f"serp_scale{i}", r=r*0.85, depth=0.05, segs=18,
            loc=(sx, sy, sz), parent=serpent_e, mat_=M_SCALE_GOLD).rotation_euler = (math.radians(90), 0, 0)
    serpent_segs.append((seg, sx, sy))

# Serpent head (at end)
head_seg_x = -18 + 11/11 * 36
head_seg_y = math.sin(math.pi * 2.5) * 4 + 5
serp_head_e = empty("serp_head_e", (head_seg_x + 0.6, head_seg_y, 0.6))
smooth_sphere("serp_head_main", r=0.55, segs=22, rings=14, loc=(0,0,0),
              parent=serp_head_e, mat_=M_SERPENT_BODY, scale=(1.3, 1.5, 0.85))
# Eyes (red émissifs intense)
for side in (-1, 1):
    smooth_sphere(f"serp_eye_{side}", r=0.08, loc=(side*0.20, 0.40, 0.15),
                  parent=serp_head_e, mat_=M_SERPENT_EYE)
# Tongue forked
tongue_e = empty("serp_tongue_e", (0, 0.80, -0.05), parent=serp_head_e)
for side in (-1, 1):
    fork = beveled_cube(f"serp_tong_{side}", (0.03, 0.30, 0.04), bevel_offset=0.01,
                       loc=(side*0.05, 0.15, 0), parent=tongue_e,
                       mat_=mat(f"tongue_{side}", (0.85, 0.20, 0.30, 1), 0, 0.5,
                                emission=(0.80,0.18,0.28), emission_strength=2.0))
# Fangs (2 white pointed)
for side in (-1, 1):
    smooth_cone(f"serp_fang_{side}", r1=0.06, r2=0.005, depth=0.18, segs=8,
                loc=(side*0.10, 0.50, -0.20), parent=serp_head_e,
                mat_=mat(f"fang_{side}", (1,0.95,0.85,1), 0, 0.4)).rotation_euler = (math.radians(150), 0, 0)

# ============ 200 PARTICULES POLLEN + MIST ============
pollens = []
for i in range(200):
    px = random.uniform(-30, 30)
    py = random.uniform(-30, 30)
    pz = random.uniform(0.5, 12)
    m_ = M_POLLEN if i < 130 else M_MIST
    p = smooth_sphere(f"pollen{i}", r=random.uniform(0.04, 0.10), segs=8, rings=6,
                     loc=(px, py, pz), mat_=m_)
    p["_phase"] = random.uniform(0, math.pi*2)
    p["_base_x"] = px; p["_base_y"] = py; p["_base_z"] = pz
    p["_speed"] = random.uniform(0.3, 1.0)
    pollens.append(p)

# 200 MILESTONE marker (giant golden 200 sphere above pyramid)
marker_e = empty("marker_200", (0, 0, total_h + 4))
# 200 number as 3 spheres in row + glow
for di, dx in enumerate([-0.8, 0, 0.8]):
    smooth_sphere(f"marker_d{di}", r=0.40, loc=(dx, 0, 0), parent=marker_e,
                  mat_=M_MARKER_200)
# Halo
smooth_sphere("marker_halo", r=1.5, loc=(0, 0, 0), parent=marker_e,
              mat_=M_GOLD, scale=(1.5, 1, 0.6))

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Sun pulse + halos
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 1.0) * 0.06
    sun.scale = (s, s, s)
    sun.keyframe_insert("scale", frame=f)

# Clouds drift
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 0.8,
                        by + math.cos(t * 0.25 + phase) * 0.8,
                        c_e.location.z + math.sin(t * 0.5 + phase) * 0.2)
        c_e.keyframe_insert("location", frame=f)

# Priests : subtle bob + cape sway
for pi, p in enumerate(priests):
    phase = pi * 0.7
    base_z = p["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        p["root"].location.z = base_z + math.sin(t * 0.8 + phase) * 0.04
        p["root"].keyframe_insert("location", frame=f)
        # Head ritualistic turn
        p["head_e"].rotation_euler = (math.sin(t * 0.6 + phase) * math.radians(5),
                                       0,
                                       math.sin(t * 0.4 + phase) * math.radians(10))
        p["head_e"].keyframe_insert("rotation_euler", frame=f)
        # Cape sway (feathers ripple)
        p["cape_e"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(5),
                                       math.cos(t * 0.8 + phase) * math.radians(3),
                                       0)
        p["cape_e"].keyframe_insert("rotation_euler", frame=f)

# Offerings gold pulse
for o_e in offerings:
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.5 + hash(o_e.name) % 100) * 0.10
        o_e.scale = (s, s, s)
        o_e.keyframe_insert("scale", frame=f)

# Chalice blood pulsing
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    chalice_e.rotation_euler = (0, 0, t * 0.3)
    chalice_e.keyframe_insert("rotation_euler", frame=f)

# Statues subtle pulse
for stat_e in [jaguar_e, condor_stat_e, serpent_stat_e]:
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 0.8 + hash(stat_e.name) % 100) * 0.02
        stat_e.scale = (s, s, s)
        stat_e.keyframe_insert("scale", frame=f)

# Condor flap + orbit massive
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    flap = math.sin(t * 1.5) * math.radians(35)
    for w_sh, w_outer, side in condor_wings:
        w_sh.rotation_euler = (side * flap, 0, 0)
        w_sh.keyframe_insert("rotation_euler", frame=f)
        w_outer.rotation_euler = (side * flap * 0.5, 0, 0)
        w_outer.keyframe_insert("rotation_euler", frame=f)
    # Orbit massive
    angle = t * 0.4
    r = 16
    condor_e.location = (r * math.cos(angle), r * math.sin(angle) + 5,
                          18 + math.sin(t * 0.8) * 1.0)
    condor_e.rotation_euler = (0, 0, angle + math.pi/2)
    condor_e.keyframe_insert("location", frame=f)
    condor_e.keyframe_insert("rotation_euler", frame=f)

# Lamas walk slowly
for li, lama in enumerate(lamas):
    phase = li * 0.5
    base_z = lama["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        lama["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.03
        lama["root"].keyframe_insert("location", frame=f)
        lama["head_e"].rotation_euler = (0, math.sin(t * 0.8 + phase) * math.radians(8),
                                          math.sin(t * 0.6 + phase) * math.radians(15))
        lama["head_e"].keyframe_insert("rotation_euler", frame=f)

# Serpent giant ondule (segments wave + head moves)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    for i, (seg, sx, sy) in enumerate(serpent_segs):
        # Y oscillates with phase offset (propagating wave)
        new_y = sy + math.sin(t * 1.8 + i * 0.4) * 0.5
        seg.location.y = new_y
        seg.keyframe_insert("location", frame=f)
    # Head follows
    head_t = 11 / 11.0
    new_head_y = math.sin(head_t * math.pi * 2.5 + t * 1.8 + 11 * 0.4) * 4 + 5
    serp_head_e.location.y = new_head_y
    serp_head_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(20))
    serp_head_e.keyframe_insert("location", frame=f)
    serp_head_e.keyframe_insert("rotation_euler", frame=f)
    # Tongue flick
    tongue_e.rotation_euler = (math.sin(t * 8.0) * math.radians(20), 0, 0)
    tongue_e.keyframe_insert("rotation_euler", frame=f)

# Cascades flow
for ci, cascade in enumerate(cascades):
    for obj in cascade.children:
        if "_base_z" in obj.keys():
            base_z = obj["_base_z"]
            phase = hash(obj.name) % 100 * 0.1
            for f in range(1, total_frames + 1, 4):
                t = (f - 1) / fps
                obj.location.z = base_z + math.sin(t * 3.0 + phase) * 0.10
                s = 1 + math.sin(t * 4.0 + phase) * 0.08
                obj.scale = (s, 1, s)
                obj.keyframe_insert("location", frame=f)
                obj.keyframe_insert("scale", frame=f)

# Glyphs pulse différentielles
for obj in bpy.data.objects:
    if obj.name.startswith("glyph") and obj.name != "glyph":
        if "_phase" in obj.keys():
            phase = obj["_phase"]
            for f in range(1, total_frames + 1, 5):
                t = (f - 1) / fps
                s = 1 + math.sin(t * 2.0 + phase) * 0.15
                obj.scale = (s, s, s)
                obj.keyframe_insert("scale", frame=f)

# 200 marker rotates + pulses (celebration!)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    marker_e.rotation_euler = (0, 0, t * 0.8)
    s = 1 + math.sin(t * 2.5) * 0.10
    marker_e.scale = (s, s, s)
    marker_e.keyframe_insert("rotation_euler", frame=f)
    marker_e.keyframe_insert("scale", frame=f)

# Pollen drift
for p in pollens:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * 1.8
        y = by + math.cos(t * speed * 0.8 + phase) * 1.8
        z = bz + math.sin(t * speed * 0.5 + phase) * 1.2 + (t * 0.3) % 4.0
        s = 1 + math.sin(t * 3.5 + phase) * 0.4
        p.location = (x, y, z)
        p.scale = (s, s, s)
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
out_glb = os.path.join(out_dir, "pbr_inca_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_inca_temple_jungle] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_inca_temple_jungle] MILESTONE 200E! Pyramide étagée 7 niveaux + 200 marches + door trapeze + Jaguar+Condor+Serpent statues + altar chalice blood + 8 offerings + 6 priests caped feathers + 100 glyphs + 25 trees + 20 bromélias + 15 flowers + 2 cascades + condor flying + 4 lamas + 2 xolos + serpent géant 12-seg + 200 pollen")
