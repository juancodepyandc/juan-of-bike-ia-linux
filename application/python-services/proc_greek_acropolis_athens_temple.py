"""
proc_greek_acropolis_athens_temple.py — 249e procédural AuroraIA (114e qualité)
Greek Acropolis: Parthenon 8 doric columns + Athena 10m gold statue + 6 philosophers + 4 hoplites + 6 maenads + Erechtheion caryatids + olive tree + 600 olive petals + 400 divine spirits
FIXES : 1 ground + 600 olive petals + 400 spirits (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB249)

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

# Mediterranean sky palette
M_SKY = mat("sky", (0.42, 0.65, 0.92, 1.0), 0.0, 0.7, emission=(0.42,0.65,0.92), emission_strength=2.0)
M_SKY_HORIZON = mat("sky_h", (0.78, 0.85, 0.92, 1.0), 0.0, 0.7, emission=(0.72,0.82,0.92), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.95, 0.78, 1.0), 0.0, 0.1, emission=(1.0,0.95,0.78), emission_strength=16.0)
M_CLOUD_LIGHT = mat("cloud", (0.95, 0.92, 0.88, 1.0), 0.0, 0.7, emission=(0.92,0.90,0.85), emission_strength=1.0)

# Marble (signature white slightly veined)
M_MARBLE = mat("marble", (0.92, 0.90, 0.85, 1.0), 0.0, 0.50, emission=(0.88,0.86,0.82), emission_strength=0.5)
M_MARBLE_AGED = mat("marble_a", (0.82, 0.78, 0.70, 1.0), 0.0, 0.65)
M_MARBLE_VEIN = mat("marble_v", (0.75, 0.72, 0.68, 1.0), 0.0, 0.55)
M_MARBLE_BRIGHT = mat("marble_b", (0.95, 0.94, 0.90, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.88), emission_strength=0.8)

# Stone foundations
M_STONE_FOUND = mat("stone", (0.65, 0.62, 0.55, 1.0), 0.0, 0.85, emission=(0.60,0.58,0.52), emission_strength=0.3)
M_STONE_DARK = mat("stone_d", (0.45, 0.42, 0.38, 1.0), 0.0, 0.85)
M_STONE_RED_TILE = mat("stone_r", (0.78, 0.42, 0.28, 1.0), 0.0, 0.65, emission=(0.72,0.40,0.28), emission_strength=0.4)

# Gold for Athena (signature huge gold statue)
M_GOLD_ATHENA = mat("gold_a", (1.0, 0.85, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.80,0.25), emission_strength=2.8)
M_GOLD_DEEP = mat("gold_d", (0.85, 0.65, 0.18, 1.0), 0.95, 0.20, emission=(0.80,0.60,0.18), emission_strength=2.0)
M_GOLD_BRIGHT = mat("gold_br", (1.0, 0.92, 0.45, 1.0), 0.95, 0.10, emission=(1.0,0.90,0.45), emission_strength=4.0)
M_IVORY = mat("ivory", (0.95, 0.92, 0.85, 1.0), 0.0, 0.30, emission=(0.92,0.90,0.85), emission_strength=1.5)
M_BRONZE = mat("bronze", (0.75, 0.55, 0.30, 1.0), 0.85, 0.30, emission=(0.70,0.52,0.30), emission_strength=1.2)
M_GEM_BLUE_A = mat("gem_b", (0.20, 0.45, 1.0, 1.0), 0.0, 0.10, emission=(0.20,0.45,1.0), emission_strength=8.0)
M_GEM_RED_A = mat("gem_r", (1.0, 0.18, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.18,0.20), emission_strength=8.0)

# Wood
M_WOOD = mat("wood", (0.42, 0.25, 0.12, 1.0), 0.0, 0.75, emission=(0.40,0.25,0.12), emission_strength=0.4)
M_WOOD_DARK = mat("wood_d", (0.25, 0.15, 0.08, 1.0), 0.0, 0.85)

# Skin
M_SKIN_GREEK = mat("skin", (0.92, 0.78, 0.62, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.62), emission_strength=0.4)
M_SKIN_DARKER = mat("skin_d", (0.82, 0.65, 0.48, 1.0), 0.0, 0.55, emission=(0.78,0.62,0.48), emission_strength=0.4)
SKIN_VARIANTS_GR = [M_SKIN_GREEK, M_SKIN_DARKER]

# Hair
M_HAIR_BLACK_GR = mat("h_bk", (0.10, 0.06, 0.04, 1.0), 0.0, 0.55)
M_HAIR_GREY = mat("h_g", (0.65, 0.60, 0.55, 1.0), 0.0, 0.60)
M_HAIR_BROWN_GR = mat("h_br", (0.30, 0.18, 0.10, 1.0), 0.0, 0.60)
M_HAIR_RED_BR = mat("h_rb", (0.55, 0.32, 0.18, 1.0), 0.0, 0.60)

# Toga (signature white draped)
M_TOGA_WHITE = mat("toga", (0.92, 0.90, 0.82, 1.0), 0.0, 0.65, emission=(0.88,0.86,0.80), emission_strength=0.5)
M_TOGA_PURPLE = mat("toga_p", (0.55, 0.20, 0.45, 1.0), 0.0, 0.55, emission=(0.50,0.20,0.42), emission_strength=0.6)
M_TOGA_CRIMSON = mat("toga_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.60, emission=(0.72,0.18,0.18), emission_strength=0.5)
M_TOGA_GOLD_TRIM = mat("toga_gt", (0.95, 0.78, 0.25, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.25), emission_strength=1.2)
TOGA_VARIANTS = [M_TOGA_WHITE, M_TOGA_PURPLE, M_TOGA_CRIMSON]

# Hoplite armor
M_BRONZE_ARMOR = mat("armor", (0.78, 0.55, 0.25, 1.0), 0.85, 0.30, emission=(0.72,0.52,0.25), emission_strength=0.7)
M_BRONZE_DARK = mat("armor_d", (0.55, 0.42, 0.20, 1.0), 0.85, 0.40)
M_HELMET_CREST_RED = mat("crest", (0.85, 0.15, 0.15, 1.0), 0.0, 0.60, emission=(0.80,0.15,0.15), emission_strength=0.7)
M_HELMET_CREST_BLACK = mat("crest_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.70)
M_SHIELD_BRONZE = mat("shield", (0.85, 0.62, 0.28, 1.0), 0.85, 0.30, emission=(0.80,0.58,0.28), emission_strength=0.9)

# Olive tree (signature sacred)
M_OLIVE_TRUNK = mat("ot", (0.55, 0.42, 0.30, 1.0), 0.0, 0.85, emission=(0.50,0.40,0.30), emission_strength=0.3)
M_OLIVE_LEAF = mat("ol", (0.55, 0.62, 0.30, 1.0), 0.0, 0.65, emission=(0.52,0.60,0.30), emission_strength=0.4)
M_OLIVE_LEAF_SILVER = mat("ols", (0.78, 0.82, 0.62, 1.0), 0.0, 0.55, emission=(0.72,0.78,0.62), emission_strength=0.6)
M_OLIVE_FRUIT_GREEN = mat("ofg", (0.30, 0.50, 0.20, 1.0), 0.0, 0.45)
M_OLIVE_FRUIT_BLACK = mat("ofb", (0.15, 0.10, 0.06, 1.0), 0.0, 0.50)

# Spirits (signature divine glow)
M_SPIRIT_GOLD = mat("sp_g", (1.0, 0.92, 0.55, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.55), emission_strength=5.0, alpha=0.55)
M_SPIRIT_WHITE = mat("sp_w", (0.95, 0.95, 1.0, 1.0), 0.0, 0.10, emission=(0.95,0.95,1.0), emission_strength=5.0, alpha=0.55)
SPIRIT_VARIANTS = [M_SPIRIT_GOLD, M_SPIRIT_WHITE]

# Amphora
M_AMPHORA_DARK = mat("amph", (0.32, 0.18, 0.10, 1.0), 0.0, 0.75, emission=(0.30,0.18,0.10), emission_strength=0.4)
M_AMPHORA_RED = mat("amph_r", (0.78, 0.20, 0.15, 1.0), 0.0, 0.70, emission=(0.72,0.20,0.15), emission_strength=0.5)
M_AMPHORA_TERRA = mat("amph_t", (0.85, 0.55, 0.30, 1.0), 0.0, 0.75)

# Owl (signature Athena's owl)
M_OWL_BROWN = mat("owl_b", (0.55, 0.40, 0.25, 1.0), 0.0, 0.65, emission=(0.52,0.40,0.25), emission_strength=0.4)
M_OWL_LIGHT = mat("owl_l", (0.78, 0.65, 0.45, 1.0), 0.0, 0.65)
M_OWL_EYE = mat("owl_e", (1.0, 0.85, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.20), emission_strength=12.0)

# Eye
M_EYE_DARK_GR = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_BLUE_GR = mat("eye_b", (0.20, 0.45, 0.75, 1.0), 0.0, 0.20, emission=(0.20,0.45,0.75), emission_strength=1.0)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Lower horizon
sky_h = smooth_sphere("sky_h", r=230, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_HORIZON)
sky_h.scale = (1,1,0.20)
# Sun
sun = smooth_sphere("sun", r=5, segs=24, rings=18, loc=(40, 80, 75), mat_=M_SUN)
# Clouds
for ci in range(15):
    cax = random.uniform(-100, 100); cay = random.uniform(-100, 100)
    caz = random.uniform(40, 70)
    cloud_e = empty(f"cloud{ci}", (cax, cay, caz))
    for cli in range(random.randint(3, 5)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(2, 4), segs=16, rings=10,
                      loc=(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD_LIGHT, scale=(1.4, 1.2, 0.7))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)

# ============ ONE clean white marble plaza ground ============
ground = beveled_cube("ground", (180, 180, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_STONE_FOUND)
# Marble tile pattern
plaza = beveled_cube("plaza", (60, 60, 0.30), bevel_offset=0.10, loc=(0, 0, 0.10), mat_=M_MARBLE)
# Inlaid stones
for i in range(60):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 28)
    smooth_sphere(f"inlay{i}", r=random.uniform(0.30, 0.50), segs=12, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.27),
                  mat_=M_MARBLE_VEIN, scale=(1.4, 1.2, 0.2))
# Acropolis raised platform (stepped)
for li in range(3):
    lz = 0.30 + li * 0.4
    lw = 50 - li * 1.5
    beveled_cube(f"step{li}", (lw, lw, 0.4), bevel_offset=0.08,
                 loc=(0, 0, lz + 0.2), mat_=M_MARBLE_AGED)

# ============ PARTHENON (signature 8 Doric columns) ============
parthenon_e = empty("parthenon", loc=(0, 15, 1.5))

# Stylobate (3 stepped base signature)
for sb in range(3):
    sb_z = sb * 0.4
    sb_w = 26 - sb * 0.8
    sb_d = 14 - sb * 0.4
    beveled_cube(f"stylo{sb}", (sb_w, sb_d, 0.4), bevel_offset=0.06,
                 loc=(0, 0, sb_z + 0.2), parent=parthenon_e, mat_=M_MARBLE_AGED)

# 8 FRONT COLUMNS (signature Doric)
def make_doric_column(name, loc, height=8, base_r=0.6, top_r=0.55, parent=None):
    col_e = empty(name, loc, parent=parent)
    # Base
    cyl(f"{name}_base", r=base_r*1.15, depth=0.20, segs=18, loc=(0, 0, 0.10),
        parent=col_e, mat_=M_MARBLE)
    # Shaft (signature fluted)
    for fi in range(20):
        fa = (fi / 20.0) * math.pi * 2
        fr = base_r * 0.9
        cyl(f"{name}_fl{fi}", r=0.04, depth=height*0.9, segs=8,
            loc=(math.cos(fa)*fr, math.sin(fa)*fr, height/2 + 0.2),
            parent=col_e, mat_=M_MARBLE_BRIGHT)
    # Main column body
    smooth_cone(f"{name}_shaft", r1=base_r, r2=top_r, depth=height, segs=20,
                loc=(0, 0, height/2 + 0.2), parent=col_e, mat_=M_MARBLE)
    # Capital (signature simple Doric)
    cyl(f"{name}_echinus", r=top_r*1.2, depth=0.20, segs=18, loc=(0, 0, height + 0.30),
        parent=col_e, mat_=M_MARBLE_BRIGHT)
    beveled_cube(f"{name}_abacus", (top_r*2.6, top_r*2.6, 0.20), bevel_offset=0.04,
                 loc=(0, 0, height + 0.50), parent=col_e, mat_=M_MARBLE)
    return col_e

# 8 front columns
col_positions_front = []
for ci in range(8):
    cx = -10.5 + ci * 3
    col_positions_front.append((cx, -6, 1.5))
    make_doric_column(f"col_f{ci}", (cx, -6, 1.5), height=8, parent=parthenon_e)
# 8 back columns
for ci in range(8):
    cx = -10.5 + ci * 3
    make_doric_column(f"col_b{ci}", (cx, 6, 1.5), height=8, parent=parthenon_e)
# 14 side columns each side (visible from front 2-3 each)
for ci in range(4):
    cy = -4.5 + ci * 3
    make_doric_column(f"col_l{ci}", (-12, cy, 1.5), height=8, parent=parthenon_e)
    make_doric_column(f"col_r{ci}", (12, cy, 1.5), height=8, parent=parthenon_e)

# Entablature (signature triglyph + metope)
# Architrave
beveled_cube("archi", (26, 14, 0.5), bevel_offset=0.06, loc=(0, 0, 10.0),
             parent=parthenon_e, mat_=M_MARBLE)
# Frieze with triglyphs and metopes
for fi in range(16):
    fx = -11.5 + fi * 1.5
    # Triglyph (signature 3 vertical grooves)
    beveled_cube(f"trig_f{fi}", (0.6, 14.2, 0.6), bevel_offset=0.04,
                 loc=(fx, 0, 10.5), parent=parthenon_e, mat_=M_MARBLE_AGED)
    for tv in range(3):
        beveled_cube(f"trig_v{fi}_{tv}", (0.05, 14.3, 0.45), bevel_offset=0.01,
                     loc=(fx - 0.2 + tv*0.2, 0, 10.5), parent=parthenon_e, mat_=M_STONE_DARK)
    # Metope (signature relief panel between)
    if fi < 15:
        beveled_cube(f"met_f{fi}", (0.9, 14.2, 0.6), bevel_offset=0.04,
                     loc=(fx + 0.75, 0, 10.5), parent=parthenon_e, mat_=M_MARBLE)
        # Relief detail
        smooth_sphere(f"met_r{fi}", r=0.20, loc=(fx + 0.75, -7.05, 10.5),
                      parent=parthenon_e, mat_=M_MARBLE_AGED, scale=(1.5, 0.1, 1.5))
# Cornice
beveled_cube("cornice", (27, 14.5, 0.4), bevel_offset=0.06, loc=(0, 0, 10.9),
             parent=parthenon_e, mat_=M_MARBLE)

# Pediment (signature triangular)
for pi in range(6):
    p_y = pi * 2.3 - 7
    p_w = 27 - pi * 4
    p_h_z = 11.3 + pi * 0.6
    if p_w > 0:
        beveled_cube(f"pediment{pi}", (p_w, 0.4, 0.55), bevel_offset=0.04,
                     loc=(0, p_y, p_h_z), parent=parthenon_e, mat_=M_MARBLE)
# Pediment relief sculptures
for ri in range(5):
    rx = -8 + ri * 4
    smooth_sphere(f"ped_r{ri}", r=0.6, segs=16, rings=12,
                  loc=(rx, -6.5, 11.8), parent=parthenon_e, mat_=M_MARBLE_AGED,
                  scale=(1, 0.3, 1.5))
# Acroteria (corner ornaments)
for cor in (-1, 1):
    smooth_sphere(f"acro{cor}", r=0.5, loc=(cor*13, -7, 13),
                  parent=parthenon_e, mat_=M_MARBLE_AGED, scale=(1, 1, 1.5))
# Top peak
smooth_sphere("peak", r=0.7, loc=(0, -7, 14),
              parent=parthenon_e, mat_=M_MARBLE_AGED, scale=(1, 1, 1.5))

# Roof tiles signature
for ti in range(13):
    tx_t = -12 + ti * 2
    beveled_cube(f"roof_t{ti}", (2.0, 14, 0.3), bevel_offset=0.06,
                 loc=(tx_t, 0, 12), parent=parthenon_e, mat_=M_STONE_RED_TILE)

# Inner cella walls (visible through columns)
beveled_cube("cella_f", (16, 0.5, 6), bevel_offset=0.06, loc=(0, -4, 5.5),
             parent=parthenon_e, mat_=M_MARBLE_AGED)
beveled_cube("cella_b", (16, 0.5, 6), bevel_offset=0.06, loc=(0, 4, 5.5),
             parent=parthenon_e, mat_=M_MARBLE_AGED)
beveled_cube("cella_l", (0.5, 8, 6), bevel_offset=0.06, loc=(-8, 0, 5.5),
             parent=parthenon_e, mat_=M_MARBLE_AGED)
beveled_cube("cella_r", (0.5, 8, 6), bevel_offset=0.06, loc=(8, 0, 5.5),
             parent=parthenon_e, mat_=M_MARBLE_AGED)
# Cella entrance opening (negative space)
# Open by leaving gap in front

# ============ ATHENA GOLD STATUE (signature 10m inside Parthenon) ============
athena_e = empty("athena", loc=(0, 15, 2.4))
# Body
smooth_cone("ath_body", r1=1.0, r2=0.85, depth=4, segs=16, loc=(0, 0, 2),
            parent=athena_e, mat_=M_GOLD_ATHENA)
# Toga drape (gold over ivory limbs)
smooth_cone("ath_drape", r1=1.05, r2=0.50, depth=3.5, segs=14, loc=(0, 0, 1.75),
            parent=athena_e, mat_=M_GOLD_ATHENA)
# Vertical drape lines
for vi in range(8):
    va = (vi / 8.0) * math.pi * 2
    cyl(f"ath_dr{vi}", r=0.04, depth=3, segs=8,
        loc=(math.cos(va)*0.90, math.sin(va)*0.90, 2),
        parent=athena_e, mat_=M_GOLD_DEEP)
# Belt
cyl("ath_belt", r=0.92, depth=0.20, segs=18, loc=(0, 0, 3.5),
    parent=athena_e, mat_=M_GOLD_DEEP)
# Belt decoration jewels
for bi in range(8):
    ba = (bi / 8.0) * math.pi * 2
    smooth_sphere(f"ath_bj{bi}", r=0.08,
                  loc=(math.cos(ba)*0.95, math.sin(ba)*0.95, 3.5),
                  parent=athena_e, mat_=random.choice([M_GEM_BLUE_A, M_GEM_RED_A]))
# Chest aegis (signature)
beveled_cube("ath_aegis", (1.5, 0.20, 1.2), bevel_offset=0.10, loc=(0, -0.40, 4.5),
             parent=athena_e, mat_=M_GOLD_DEEP)
# Gorgon head on aegis (signature Medusa)
smooth_sphere("ath_gorgon", r=0.30, loc=(0, -0.50, 4.5),
              parent=athena_e, mat_=M_BRONZE, scale=(1.2, 0.7, 1.2))
# Snakes from gorgon
for si in range(8):
    sa = (si / 8.0) * math.pi * 2
    smooth_cone(f"ath_snake{si}", r1=0.06, r2=0.02, depth=0.30, segs=8,
                loc=(math.cos(sa)*0.30, -0.52, 4.5 + math.sin(sa)*0.30),
                parent=athena_e, mat_=M_BRONZE)
# Arms (ivory)
# Left arm holding shield
left_arm_e = empty("ath_la", (-1.0, -0.10, 5), parent=athena_e)
left_arm_e.rotation_euler = (math.radians(-20), 0, math.radians(20))
cyl("ath_uarm_L", r=0.18, depth=1.0, segs=12, loc=(0, 0, -0.50), parent=left_arm_e, mat_=M_IVORY)
cyl("ath_fa_L", r=0.15, depth=0.85, segs=12, loc=(0, 0, -1.4), parent=left_arm_e, mat_=M_IVORY)
# SHIELD (signature huge round)
shield_e = empty("ath_shield", (0, -0.30, -1.9), parent=left_arm_e)
cyl("ath_sh", r=1.2, depth=0.15, segs=24, loc=(0, 0, 0),
    parent=shield_e, mat_=M_GOLD_DEEP).rotation_euler = (math.radians(90), 0, 0)
# Shield boss
smooth_sphere("ath_sh_boss", r=0.30, loc=(0, -0.10, 0),
              parent=shield_e, mat_=M_GOLD_BRIGHT, scale=(1, 0.6, 1))
# Shield rim
cyl("ath_sh_rim", r=1.22, depth=0.10, segs=24, loc=(0, 0, 0),
    parent=shield_e, mat_=M_GOLD_ATHENA).rotation_euler = (math.radians(90), 0, 0)
# Shield decorations 12 stars
for si in range(12):
    sa = (si / 12.0) * math.pi * 2
    smooth_sphere(f"ath_sh_s{si}", r=0.08,
                  loc=(math.cos(sa)*0.85, -0.10, math.sin(sa)*0.85),
                  parent=shield_e, mat_=M_GOLD_BRIGHT)
# Right arm holding LANCE/SPEAR (signature)
right_arm_e = empty("ath_ra", (1.0, -0.10, 5.5), parent=athena_e)
right_arm_e.rotation_euler = (math.radians(0), 0, math.radians(-15))
cyl("ath_uarm_R", r=0.18, depth=1.0, segs=12, loc=(0, 0, -0.50), parent=right_arm_e, mat_=M_IVORY)
cyl("ath_fa_R", r=0.15, depth=0.85, segs=12, loc=(0, 0, -1.4), parent=right_arm_e, mat_=M_IVORY)
# SPEAR (signature)
spear_e = empty("ath_spear", (0.20, 0, 0), parent=athena_e)
cyl("ath_spear_s", r=0.05, depth=8, segs=10, loc=(1.5, 0, 5),
    parent=spear_e, mat_=M_WOOD_DARK)
# Spearhead
smooth_cone("ath_spear_h", r1=0.10, r2=0.005, depth=0.5, segs=10,
            loc=(1.5, 0, 9.2), parent=spear_e, mat_=M_BRONZE)

# HEAD
ath_head_e = empty("ath_he", (0, 0, 6.5), parent=athena_e)
smooth_sphere("ath_head", r=0.50, segs=22, rings=16, loc=(0, 0, 0),
              parent=ath_head_e, mat_=M_IVORY, scale=(1, 1.05, 1.15))
# Face features
for side in (-1, 1):
    smooth_sphere(f"ath_eye{side}", r=0.08, loc=(side*0.16, -0.40, 0.10),
                  parent=ath_head_e, mat_=M_EYE_BLUE_GR)
    smooth_sphere(f"ath_pup{side}", r=0.04, loc=(side*0.16, -0.46, 0.10),
                  parent=ath_head_e, mat_=M_EYE_DARK_GR)
# Nose
smooth_cone("ath_nose", r1=0.07, r2=0.04, depth=0.25, segs=10,
            loc=(0, -0.50, -0.05), parent=ath_head_e,
            mat_=M_IVORY).rotation_euler = (math.radians(-90), 0, 0)
# Lips
beveled_cube("ath_lips", (0.15, 0.05, 0.05), bevel_offset=0.01, loc=(0, -0.50, -0.20),
             parent=ath_head_e, mat_=M_TOGA_CRIMSON)
# HELMET (signature Corinthian style)
helm_e = empty("ath_helm", (0, 0, 0.30), parent=ath_head_e)
# Helmet bowl
smooth_sphere("ath_h_b", r=0.55, segs=22, rings=16, loc=(0, 0, 0),
              parent=helm_e, mat_=M_GOLD_ATHENA, scale=(1, 1.1, 1.0))
# Front piece coming down
beveled_cube("ath_h_f", (0.50, 0.08, 0.50), bevel_offset=0.06, loc=(0, -0.50, -0.10),
             parent=helm_e, mat_=M_GOLD_ATHENA)
# Cheek guards
for side in (-1, 1):
    beveled_cube(f"ath_h_cg{side}", (0.08, 0.30, 0.40), bevel_offset=0.04,
                 loc=(side*0.40, -0.20, -0.20), parent=helm_e, mat_=M_GOLD_ATHENA)
# CREST PLUME (signature horsehair)
crest_e = empty("ath_crest", (0, 0, 0.30), parent=helm_e)
beveled_cube("ath_crest_b", (0.12, 1.4, 0.20), bevel_offset=0.04, loc=(0, 0, 0.10),
             parent=crest_e, mat_=M_GOLD_BRIGHT)
for ci in range(15):
    cy_c = -0.65 + ci * 0.10
    smooth_cone(f"ath_crest_h{ci}", r1=0.04, r2=0.005, depth=0.45, segs=8,
                loc=(0, cy_c, 0.35), parent=crest_e, mat_=M_HELMET_CREST_RED)
# Hair below helmet
for hi in range(8):
    ha = (hi / 8.0) * math.pi * 2
    smooth_sphere(f"ath_hr{hi}", r=0.08, loc=(math.cos(ha)*0.40, math.sin(ha)*0.30, -0.10),
                  parent=ath_head_e, mat_=M_HAIR_BROWN_GR)

# OWL on shield (signature Athena's owl)
owl_e = empty("ath_owl", (-1.2, -1.5, 4.0), parent=athena_e)
# Body
smooth_sphere("owl_body", r=0.25, segs=18, rings=14, loc=(0, 0, 0),
              parent=owl_e, mat_=M_OWL_BROWN, scale=(1, 1.0, 1.3))
# Head
smooth_sphere("owl_h", r=0.20, segs=18, rings=14, loc=(0, -0.10, 0.30),
              parent=owl_e, mat_=M_OWL_LIGHT)
# Eyes (signature huge glowing)
for side in (-1, 1):
    smooth_sphere(f"owl_eye{side}", r=0.07, loc=(side*0.08, -0.20, 0.32),
                  parent=owl_e, mat_=M_OWL_EYE)
    smooth_sphere(f"owl_pup{side}", r=0.03, loc=(side*0.08, -0.24, 0.32),
                  parent=owl_e, mat_=M_EYE_DARK_GR)
# Beak
smooth_cone("owl_beak", r1=0.04, r2=0.005, depth=0.10, segs=8,
            loc=(0, -0.20, 0.20), parent=owl_e,
            mat_=M_BRONZE).rotation_euler = (math.radians(-90), 0, 0)
# Wings
for side in (-1, 1):
    beveled_cube(f"owl_w{side}", (0.10, 0.30, 0.20), bevel_offset=0.03,
                 loc=(side*0.25, 0, 0), parent=owl_e, mat_=M_OWL_BROWN)

# ============ ERECHTHEION WITH CARYATIDS (signature 4 female columns) ============
erech_e = empty("erechtheion", loc=(-25, -10, 1.5))
# Base
beveled_cube("er_base", (10, 5, 0.6), bevel_offset=0.10, loc=(0, 0, 0.3),
             parent=erech_e, mat_=M_MARBLE_AGED)
# Caryatid porch (4 female columns)
def make_caryatid(name, loc, parent=None):
    car_e = empty(name, loc, parent=parent)
    # Base
    cyl(f"{name}_base", r=0.45, depth=0.20, segs=18, loc=(0, 0, 0.10),
        parent=car_e, mat_=M_MARBLE)
    # Body (long pleated robe)
    smooth_cone(f"{name}_dress", r1=0.40, r2=0.32, depth=3.0, segs=14,
                loc=(0, 0, 1.7), parent=car_e, mat_=M_MARBLE)
    # Vertical pleats
    for pi in range(8):
        pa = (pi / 8.0) * math.pi * 2
        cyl(f"{name}_pl{pi}", r=0.03, depth=3.0, segs=6,
            loc=(math.cos(pa)*0.38, math.sin(pa)*0.38, 1.7),
            parent=car_e, mat_=M_MARBLE_VEIN)
    # Torso
    smooth_cone(f"{name}_torso", r1=0.30, r2=0.32, depth=0.7, segs=14,
                loc=(0, 0, 3.4), parent=car_e, mat_=M_MARBLE)
    # Belt
    cyl(f"{name}_belt", r=0.32, depth=0.06, segs=14, loc=(0, 0, 3.2),
        parent=car_e, mat_=M_MARBLE_AGED)
    # Arms at side
    for side in (-1, 1):
        cyl(f"{name}_a{side}", r=0.08, depth=0.7, segs=10, loc=(side*0.30, 0, 3.2),
            parent=car_e, mat_=M_MARBLE)
    # Head
    head_c_e = empty(f"{name}_he", (0, 0, 3.95), parent=car_e)
    smooth_sphere(f"{name}_head", r=0.22, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_c_e, mat_=M_MARBLE)
    # Hair coiled (signature)
    for hi in range(6):
        ha = (hi / 6.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.08,
                      loc=(math.cos(ha)*0.20, math.sin(ha)*0.10, 0.05),
                      parent=head_c_e, mat_=M_MARBLE_AGED)
    # Entablature on top (signature she carries it)
    cyl(f"{name}_basket", r=0.35, depth=0.15, segs=18, loc=(0, 0, 0.30),
        parent=head_c_e, mat_=M_MARBLE_AGED)
    beveled_cube(f"{name}_capital", (0.6, 0.6, 0.25), bevel_offset=0.04,
                 loc=(0, 0, 0.50), parent=head_c_e, mat_=M_MARBLE)
    return car_e

# 4 caryatids in a row
caryatids = []
for ci in range(4):
    cx = -2.5 + ci * 1.7
    c = make_caryatid(f"caryatid{ci}", (cx, 2, 0.6), parent=erech_e)
    caryatids.append(c)
# Architrave over caryatids
beveled_cube("er_arch", (8, 1.0, 0.4), bevel_offset=0.06, loc=(0, 2, 5.2),
             parent=erech_e, mat_=M_MARBLE)
# Roof over Erechtheion
beveled_cube("er_roof", (10, 5.5, 0.5), bevel_offset=0.08, loc=(0, 0.5, 5.6),
             parent=erech_e, mat_=M_STONE_RED_TILE)

# ============ OLIVE TREE (signature sacred Athena gift) ============
olive_e = empty("olive", loc=(-25, 0, 0))
# Thick gnarled trunk
for ti in range(8):
    tilt_x = math.sin(ti * 0.4) * 0.1
    cyl(f"ot_t{ti}", r=0.55 - ti*0.03, depth=0.65, segs=14,
        loc=(tilt_x, 0, ti*0.65 + 0.32),
        parent=olive_e, mat_=M_OLIVE_TRUNK if ti % 2 == 0 else M_AMPHORA_DARK)
# Branches
for bi in range(7):
    ba = (bi / 7.0) * math.pi * 2
    br_e = empty(f"ot_br{bi}_e", (0, 0, 5), parent=olive_e)
    br_e.rotation_euler = (math.radians(random.uniform(40, 60)), 0, ba)
    cyl(f"ot_br{bi}", r=0.18, depth=2.5, segs=10, loc=(0, 0, 1.25),
        parent=br_e, mat_=M_OLIVE_TRUNK)
    # Foliage clusters at branch ends
    for fi in range(8):
        fa = random.uniform(0, math.pi*2); fr = random.uniform(0.5, 1.2); fz = random.uniform(2.0, 2.8)
        smooth_sphere(f"ot_f{bi}_{fi}", r=0.30, segs=14, rings=10,
                      loc=(math.cos(fa)*fr, math.sin(fa)*fr, fz),
                      parent=br_e, mat_=M_OLIVE_LEAF if fi % 2 == 0 else M_OLIVE_LEAF_SILVER,
                      scale=(1.4, 1.2, 0.7))
        # Olives
        if random.random() > 0.6:
            smooth_sphere(f"ot_olv{bi}_{fi}", r=0.05,
                          loc=(math.cos(fa)*fr, math.sin(fa)*fr, fz - 0.10),
                          parent=br_e, mat_=M_OLIVE_FRUIT_BLACK if fi % 2 == 0 else M_OLIVE_FRUIT_GREEN)
olive_e["_phase"] = 0

# ============ 6 PHILOSOPHERS (Socrates + Plato style signature togas) ============
def make_philosopher(name, loc, scale=1.0, facing=0, with_beard=True):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    toga_col = random.choice(TOGA_VARIANTS)
    skin = random.choice(SKIN_VARIANTS_GR)
    hair_col = M_HAIR_GREY if with_beard else random.choice([M_HAIR_BLACK_GR, M_HAIR_BROWN_GR])
    # Long flowing toga (signature)
    smooth_cone(f"{name}_robe", r1=0.55*scale, r2=0.35*scale, depth=2.2*scale, segs=18,
                loc=(0, 0, 1.1*scale), parent=base, mat_=toga_col)
    # Drape folds vertical (signature)
    for di in range(10):
        da = (di / 10.0) * math.pi * 2
        cyl(f"{name}_drf{di}", r=0.02*scale, depth=2.2*scale, segs=6,
            loc=(math.cos(da)*0.50*scale, math.sin(da)*0.50*scale, 1.1*scale),
            parent=base, mat_=M_MARBLE_VEIN if toga_col == M_TOGA_WHITE else M_GOLD_DEEP)
    # Gold trim border
    cyl(f"{name}_trim", r=0.55*scale, depth=0.04*scale, segs=14, loc=(0, 0, 0.10*scale),
        parent=base, mat_=M_TOGA_GOLD_TRIM)
    # Diagonal sash (signature)
    sash_e = empty(f"{name}_sa", (0, -0.10*scale, 1.5*scale), parent=base)
    sash_e.rotation_euler = (0, math.radians(15), math.radians(35))
    beveled_cube(f"{name}_sash", (0.7*scale, 0.06*scale, 0.20*scale), bevel_offset=0.03,
                 loc=(0, 0, 0), parent=sash_e,
                 mat_=M_TOGA_PURPLE if toga_col == M_TOGA_WHITE else M_TOGA_GOLD_TRIM)
    # Arms (one extended gesturing)
    # Right arm extended (philosophical gesture)
    arm_R = empty(f"{name}_aR", (0.40*scale, -0.10*scale, 1.7*scale), parent=base)
    arm_R.rotation_euler = (math.radians(-100), 0, math.radians(-30))
    cyl(f"{name}_uarm_R", r=0.06*scale, depth=0.40*scale, segs=10,
        loc=(0, 0, -0.20*scale), parent=arm_R, mat_=toga_col)
    cyl(f"{name}_fa_R", r=0.05*scale, depth=0.35*scale, segs=10,
        loc=(0, 0, -0.55*scale), parent=arm_R, mat_=skin)
    # Hand pointing
    smooth_sphere(f"{name}_hand_R", r=0.06*scale, loc=(0, 0, -0.78*scale),
                  parent=arm_R, mat_=skin)
    # Left arm bent (holding scroll)
    arm_L = empty(f"{name}_aL", (-0.30*scale, 0, 1.5*scale), parent=base)
    arm_L.rotation_euler = (math.radians(-60), 0, math.radians(30))
    cyl(f"{name}_uarm_L", r=0.06*scale, depth=0.40*scale, segs=10,
        loc=(0, 0, -0.20*scale), parent=arm_L, mat_=toga_col)
    cyl(f"{name}_fa_L", r=0.05*scale, depth=0.35*scale, segs=10,
        loc=(0, 0, -0.55*scale), parent=arm_L, mat_=skin)
    # Scroll
    cyl(f"{name}_scroll", r=0.06*scale, depth=0.30*scale, segs=10, loc=(0, 0, -0.85*scale),
        parent=arm_L, mat_=M_TOGA_WHITE)

    # Bare feet visible at bottom
    for side in (-1, 1):
        beveled_cube(f"{name}_ft{side}", (0.10*scale, 0.20*scale, 0.06*scale), bevel_offset=0.01,
                     loc=(side*0.13*scale, 0, 0), parent=base, mat_=skin)

    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.05*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=skin)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.03*scale), parent=head_e, mat_=M_EYE_DARK_GR)
    # Hair (curly Greek style signature)
    for hi in range(12):
        ha = random.uniform(0, math.pi*2)
        smooth_sphere(f"{name}_hr{hi}", r=0.05*scale,
                      loc=(math.cos(ha)*0.18*scale, math.sin(ha)*0.10*scale + 0.05*scale,
                           random.uniform(0.05, 0.18)*scale),
                      parent=head_e, mat_=hair_col)
    # BEARD (signature for elder philosophers)
    if with_beard:
        for bi in range(15):
            ba = (bi / 15.0) * math.pi - math.pi/2
            smooth_sphere(f"{name}_bd{bi}", r=0.05*scale,
                          loc=(math.sin(ba)*0.14*scale, -0.16*scale, -0.10 - (bi%3)*0.08*scale),
                          parent=head_e, mat_=hair_col)
    # Laurel wreath (signature)
    if random.random() > 0.4:
        for li in range(12):
            la = (li / 12.0) * math.pi * 2
            smooth_sphere(f"{name}_lw{li}", r=0.04*scale,
                          loc=(math.cos(la)*0.22*scale, math.sin(la)*0.15*scale, 0.18*scale),
                          parent=head_e, mat_=M_OLIVE_LEAF)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "aR": arm_R}

philosophers = []
phil_pos = [(-8, 25, math.radians(45)), (-5, 28, math.radians(-15)),
            (-2, 25, math.radians(15)), (1, 28, math.radians(-30)),
            (5, 25, math.radians(60)), (-12, 22, math.radians(0))]
for i, (px, py, fac) in enumerate(phil_pos):
    p = make_philosopher(f"philosopher{i}", (px, py, 1.5), scale=1.0, facing=fac, with_beard=(i % 2 == 0))
    philosophers.append(p)

# ============ 4 HOPLITES (signature soldiers) ============
def make_hoplite(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Tunic (short)
    smooth_cone(f"{name}_tunic", r1=0.32*scale, r2=0.28*scale, depth=0.7*scale, segs=14,
                loc=(0, 0, 0.85*scale), parent=base, mat_=M_TOGA_CRIMSON)
    # Legs (greaves bronze)
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.10*scale, depth=0.80*scale, segs=10,
            loc=(side*0.13*scale, 0, 0.40*scale), parent=base, mat_=M_SKIN_GREEK)
        # Greave (bronze shin guard)
        cyl(f"{name}_grv{side}", r=0.11*scale, depth=0.50*scale, segs=10,
            loc=(side*0.13*scale, 0, 0.30*scale), parent=base, mat_=M_BRONZE_ARMOR)
        # Sandal
        beveled_cube(f"{name}_san{side}", (0.10*scale, 0.20*scale, 0.04*scale), bevel_offset=0.01,
                     loc=(side*0.13*scale, 0, 0), parent=base, mat_=M_WOOD)
    # CUIRASS (signature bronze chest armor)
    smooth_cone(f"{name}_cuirass", r1=0.32*scale, r2=0.34*scale, depth=0.5*scale, segs=14,
                loc=(0, 0, 1.4*scale), parent=base, mat_=M_BRONZE_ARMOR)
    # Pectoral muscle detail
    for side in (-1, 1):
        smooth_sphere(f"{name}_pec{side}", r=0.13*scale,
                      loc=(side*0.10*scale, -0.32*scale, 1.45*scale),
                      parent=base, mat_=M_BRONZE_DARK, scale=(1, 0.4, 0.7))
    # Belt
    cyl(f"{name}_belt", r=0.32*scale, depth=0.10*scale, segs=14, loc=(0, 0, 1.15*scale),
        parent=base, mat_=M_BRONZE_DARK)
    # Arms (bare with arm guard)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.65*scale), parent=base)
        if side == -1:  # left holding shield
            sh.rotation_euler = (math.radians(-60), 0, math.radians(15))
        else:  # right holding spear
            sh.rotation_euler = (math.radians(-30), 0, math.radians(-15))
        cyl(f"{name}_uarm{side_idx}", r=0.07*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=M_SKIN_GREEK)
        cyl(f"{name}_fa{side_idx}", r=0.06*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_GREEK)
        # Arm guard bronze (signature)
        cyl(f"{name}_ag{side_idx}", r=0.08*scale, depth=0.20*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_BRONZE_ARMOR)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.0*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_GREEK)
    # Beard
    for bi in range(8):
        ba = (bi / 8.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_bd{bi}", r=0.04*scale,
                      loc=(math.sin(ba)*0.12*scale, -0.15*scale, -0.10*scale),
                      parent=head_e, mat_=M_HAIR_BLACK_GR)
    # CORINTHIAN HELMET (signature with crest)
    helm_h_e = empty(f"{name}_helm", (0, 0, 0.18*scale), parent=head_e)
    smooth_sphere(f"{name}_h_b", r=0.22*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=helm_h_e, mat_=M_BRONZE_ARMOR, scale=(1, 1.1, 1.0))
    # Nose guard
    beveled_cube(f"{name}_h_n", (0.06*scale, 0.02*scale, 0.15*scale), bevel_offset=0.005,
                 loc=(0, -0.18*scale, -0.08*scale), parent=helm_h_e, mat_=M_BRONZE_ARMOR)
    # Cheek pieces
    for side in (-1, 1):
        beveled_cube(f"{name}_h_c{side}", (0.10*scale, 0.20*scale, 0.18*scale), bevel_offset=0.03,
                     loc=(side*0.18*scale, -0.10*scale, -0.10*scale), parent=helm_h_e, mat_=M_BRONZE_ARMOR)
    # Eye slits
    for side in (-1, 1):
        beveled_cube(f"{name}_h_es{side}", (0.08*scale, 0.04*scale, 0.06*scale), bevel_offset=0.01,
                     loc=(side*0.10*scale, -0.21*scale, 0.02*scale), parent=helm_h_e, mat_=M_STONE_DARK)
    # RED CREST (signature horsehair plume)
    crest_h_e = empty(f"{name}_crh", (0, 0, 0.22*scale), parent=helm_h_e)
    beveled_cube(f"{name}_cr_b", (0.06*scale, 0.50*scale, 0.10*scale), bevel_offset=0.02,
                 loc=(0, 0, 0.05*scale), parent=crest_h_e, mat_=M_BRONZE_DARK)
    for ci in range(12):
        cy_c = -0.22 + ci * 0.04
        smooth_cone(f"{name}_cr_h{ci}", r1=0.03*scale, r2=0.005*scale, depth=0.25*scale, segs=8,
                    loc=(0, cy_c*scale, 0.20*scale), parent=crest_h_e, mat_=M_HELMET_CREST_RED)

    # ROUND SHIELD (signature hoplon)
    shield_h_e = empty(f"{name}_shield", (-0.60*scale, 0, 1.4*scale), parent=base)
    shield_h_e.rotation_euler = (0, math.radians(90), 0)
    cyl(f"{name}_sh_b", r=0.50*scale, depth=0.08*scale, segs=20, loc=(0, 0, 0),
        parent=shield_h_e, mat_=M_SHIELD_BRONZE)
    # Symbol (lambda for Sparta or owl for Athens)
    beveled_cube(f"{name}_sh_sym", (0.30*scale, 0.04*scale, 0.30*scale), bevel_offset=0.04,
                 loc=(0, -0.05*scale, 0), parent=shield_h_e, mat_=M_TOGA_CRIMSON)
    # Rim
    cyl(f"{name}_sh_rim", r=0.52*scale, depth=0.05*scale, segs=22, loc=(0, 0, 0),
        parent=shield_h_e, mat_=M_BRONZE_DARK)
    # Boss
    smooth_sphere(f"{name}_sh_boss", r=0.10*scale, loc=(0, -0.06*scale, 0),
                  parent=shield_h_e, mat_=M_BRONZE_DARK)
    # SPEAR (signature dory)
    spear_h_e = empty(f"{name}_spear", (0.40*scale, 0, 0), parent=base)
    spear_h_e.rotation_euler = (math.radians(-5), 0, math.radians(-5))
    cyl(f"{name}_sp_s", r=0.04*scale, depth=3.0*scale, segs=10,
        loc=(0, 0, 1.5*scale), parent=spear_h_e, mat_=M_WOOD_DARK)
    smooth_cone(f"{name}_sp_h", r1=0.08*scale, r2=0.005*scale, depth=0.30*scale, segs=10,
                loc=(0, 0, 3.15*scale), parent=spear_h_e, mat_=M_BRONZE_ARMOR)
    # Spear butt spike
    smooth_cone(f"{name}_sp_b", r1=0.04*scale, r2=0.005*scale, depth=0.12*scale, segs=8,
                loc=(0, 0, -0.06*scale), parent=spear_h_e, mat_=M_BRONZE_ARMOR)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

hoplites = []
hopl_pos = [(-15, -25, math.radians(45)), (15, -25, math.radians(-45)),
             (-15, 0, math.radians(90)), (15, 0, math.radians(-90))]
for i, (hx, hy, fac) in enumerate(hopl_pos):
    h = make_hoplite(f"hoplite{i}", (hx, hy, 1.5), scale=1.0, facing=fac)
    hoplites.append(h)

# ============ 6 MAENADS (dancers signature) ============
def make_maenad(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    skin = random.choice(SKIN_VARIANTS_GR)
    toga_col = random.choice([M_TOGA_WHITE, M_TOGA_PURPLE, M_TOGA_CRIMSON])
    # Flowing chiton (signature dancing dress)
    smooth_cone(f"{name}_chiton", r1=0.40*scale, r2=0.30*scale, depth=1.8*scale, segs=18,
                loc=(0, 0, 0.9*scale), parent=base, mat_=toga_col)
    # Folds
    for fi in range(8):
        fa = (fi / 8.0) * math.pi * 2
        cyl(f"{name}_fl{fi}", r=0.025*scale, depth=1.8*scale, segs=6,
            loc=(math.cos(fa)*0.38*scale, math.sin(fa)*0.38*scale, 0.9*scale),
            parent=base, mat_=M_MARBLE_VEIN)
    # Belt
    cyl(f"{name}_belt", r=0.30*scale, depth=0.06*scale, segs=14, loc=(0, 0, 1.20*scale),
        parent=base, mat_=M_TOGA_GOLD_TRIM)
    # Torso
    smooth_cone(f"{name}_torso", r1=0.28*scale, r2=0.30*scale, depth=0.45*scale, segs=14,
                loc=(0, 0, 1.45*scale), parent=base, mat_=toga_col)
    # Bare shoulders one side (signature flowing)
    smooth_sphere(f"{name}_sh1", r=0.18*scale, loc=(-0.30*scale, 0, 1.65*scale),
                  parent=base, mat_=skin, scale=(0.7, 1, 1))
    # Arms raised dancing (signature)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.28*scale, 0, 1.75*scale), parent=base)
        sh.rotation_euler = (math.radians(-150), 0, math.radians(side*-30))
        cyl(f"{name}_uarm{side_idx}", r=0.05*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=skin)
        cyl(f"{name}_fa{side_idx}", r=0.045*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=skin)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.17*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=skin)
    # Long flowing hair
    for hi in range(12):
        ha = random.uniform(0, math.pi*2)
        hl_m = random.uniform(0.25, 0.45)
        beveled_cube(f"{name}_hr{hi}", (0.05*scale, 0.07*scale, hl_m*scale), bevel_offset=0.01,
                     loc=(math.cos(ha)*0.16*scale, math.sin(ha)*0.10*scale - 0.05*scale, -hl_m*scale/2),
                     parent=head_e, mat_=M_HAIR_BLACK_GR)
    # Wreath (signature ivy)
    for li in range(10):
        la = (li / 10.0) * math.pi * 2
        smooth_sphere(f"{name}_iv{li}", r=0.04*scale,
                      loc=(math.cos(la)*0.20*scale, math.sin(la)*0.15*scale, 0.15*scale),
                      parent=head_e, mat_=M_OLIVE_LEAF)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.13*scale, 0.04*scale), parent=head_e, mat_=M_EYE_DARK_GR)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

maenads = []
maenad_pos = [(10, 25, math.radians(0)), (12, 28, math.radians(60)),
              (8, 30, math.radians(120)), (15, 25, math.radians(-30)),
              (18, 28, math.radians(-60)), (20, 25, math.radians(0))]
for i, (mx, my, fac) in enumerate(maenad_pos):
    m = make_maenad(f"maenad{i}", (mx, my, 1.5), scale=1.0, facing=fac)
    maenads.append(m)

# ============ AMPHORAS (signature pottery) ============
for ai in range(8):
    amx = -25 + ai * 7
    amy = -15
    if amx < -10 and amx > -20: continue
    a_e = empty(f"amphora{ai}", (amx, amy, 1.5))
    # Body
    smooth_sphere(f"am_b{ai}", r=0.45, segs=20, rings=14, loc=(0, 0, 0.55),
                  parent=a_e, mat_=M_AMPHORA_DARK, scale=(1, 1, 1.3))
    # Neck
    cyl(f"am_n{ai}", r=0.18, depth=0.4, segs=14, loc=(0, 0, 1.15),
        parent=a_e, mat_=M_AMPHORA_DARK)
    # Rim
    cyl(f"am_r{ai}", r=0.22, depth=0.06, segs=16, loc=(0, 0, 1.35),
        parent=a_e, mat_=M_AMPHORA_DARK)
    # 2 handles (signature)
    for side in (-1, 1):
        for hi in range(5):
            ha = (hi / 4.0) * math.pi
            smooth_sphere(f"am_h{ai}_{side}_{hi}", r=0.035,
                          loc=(side*(0.25 + math.sin(ha)*0.15), 0, 0.95 + math.cos(ha)*0.20),
                          parent=a_e, mat_=M_AMPHORA_DARK)
    # Red figure pattern
    cyl(f"am_p{ai}", r=0.46, depth=0.20, segs=20, loc=(0, 0, 0.65),
        parent=a_e, mat_=M_AMPHORA_RED)

# ============ ALTAR SACRIFICIAL (signature) ============
altar_e = empty("altar", loc=(0, -15, 1.5))
beveled_cube("alt_base", (3, 2, 1.5), bevel_offset=0.10, loc=(0, 0, 0.75),
             parent=altar_e, mat_=M_MARBLE)
# Top with offerings
beveled_cube("alt_top", (3.2, 2.2, 0.20), bevel_offset=0.04, loc=(0, 0, 1.55),
             parent=altar_e, mat_=M_MARBLE_AGED)
# Flames offering (signature)
flame_alt = empty("alt_fl", (0, 0, 1.80), parent=altar_e)
smooth_cone("alt_fo", r1=0.30, r2=0.05, depth=0.8, segs=14, loc=(0, 0, 0.4),
            parent=flame_alt, mat_=M_HELMET_CREST_RED)
smooth_cone("alt_fc", r1=0.20, r2=0.02, depth=0.6, segs=14, loc=(0, 0, 0.30),
            parent=flame_alt, mat_=M_GOLD_BRIGHT)
# Decorative carving on altar
for di in range(6):
    da = (di / 6.0) * math.pi * 2
    beveled_cube(f"alt_d{di}", (0.05, 0.05, 1.2), bevel_offset=0.01,
                 loc=(math.cos(da)*1.4, math.sin(da)*0.95, 0.85),
                 parent=altar_e, mat_=M_TOGA_GOLD_TRIM)

# ============================================================
# ⭐ 600 OLIVE PETALS + 400 DIVINE SPIRITS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
olive_petals = []
for i in range(600):
    px = random.uniform(-60, 60)
    py = random.uniform(-60, 60)
    pz = random.uniform(1, 16)
    p = smooth_sphere(f"olp{i}", r=random.uniform(0.06, 0.10), segs=8, rings=6,
                      loc=(px, py, pz),
                      mat_=M_OLIVE_LEAF if i % 2 == 0 else M_OLIVE_LEAF_SILVER,
                      scale=(1.5, 0.6, 0.3))
    p["_phase"] = random.uniform(0, math.pi*2)
    p["_base_x"] = px; p["_base_y"] = py; p["_base_z"] = pz
    p["_amp_x"] = random.uniform(0.8, 2.0)
    p["_amp_y"] = random.uniform(0.8, 2.0)
    p["_amp_z"] = random.uniform(0.5, 1.5)
    p["_speed"] = random.uniform(0.4, 0.9)
    olive_petals.append(p)

# 400 divine spirits (golden/white glowing orbs)
spirits = []
for i in range(400):
    px = random.uniform(-50, 50)
    py = random.uniform(-50, 50)
    pz = random.uniform(2, 18)
    sp_col = random.choice(SPIRIT_VARIANTS)
    sp = smooth_sphere(f"spirit{i}", r=random.uniform(0.10, 0.18), segs=10, rings=8,
                      loc=(px, py, pz), mat_=sp_col)
    sp["_phase"] = random.uniform(0, math.pi*2)
    sp["_base_x"] = px; sp["_base_y"] = py; sp["_base_z"] = pz
    sp["_amp_x"] = random.uniform(1.5, 3.0)
    sp["_amp_y"] = random.uniform(1.5, 3.0)
    sp["_amp_z"] = random.uniform(0.8, 2.0)
    sp["_speed"] = random.uniform(0.4, 1.0)
    spirits.append(sp)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Olive tree sway
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    olive_e.rotation_euler = (math.sin(t * 0.6) * math.radians(2),
                               math.cos(t * 0.6) * math.radians(2), 0)
    olive_e.keyframe_insert("rotation_euler", frame=f)

# Philosophers gesture
for p in philosophers:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        p["aR"].rotation_euler = (math.radians(-100) + math.sin(t * 1.5 + phase) * math.radians(15),
                                   math.cos(t * 1.5 + phase) * math.radians(10),
                                   math.radians(-30))
        p["aR"].keyframe_insert("rotation_euler", frame=f)
        p["he"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(20))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Hoplites watchful turn
for h in hoplites:
    phase = h["root"]["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        h["he"].rotation_euler = (0, 0, math.sin(t * 0.5 + phase) * math.radians(25))
        h["he"].keyframe_insert("rotation_euler", frame=f)

# Maenads dance
for m in maenads:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(8),
                                     math.cos(t * 2.5 + phase) * math.radians(10),
                                     m["root"].rotation_euler.z + math.sin(t * 1.5 + phase) * math.radians(5))
        m["root"].location.z = 1.5 + abs(math.sin(t * 3.0 + phase)) * 0.20
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["root"].keyframe_insert("location", frame=f)
        m["he"].rotation_euler = (0, 0, math.sin(t * 2.0 + phase) * math.radians(20))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Altar flame flicker
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    sc_fl = 1 + math.sin(t * 6.0) * 0.15
    flame_alt.scale = (1 + math.cos(t * 5.0) * 0.10, 1 + math.sin(t * 5.0) * 0.10, sc_fl)
    flame_alt.keyframe_insert("scale", frame=f)

# 600 olive petals drift
for op in olive_petals:
    phase = op["_phase"]; speed = op["_speed"]
    bx, by, bz = op["_base_x"], op["_base_y"], op["_base_z"]
    ax, ay, az = op["_amp_x"], op["_amp_y"], op["_amp_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        op.location = (x, y, max(0.3, z))
        op.rotation_euler = (t * 2.0 + phase, t * 1.5 + phase, t * 2.5 + phase)
        op.keyframe_insert("location", frame=f)
        op.keyframe_insert("rotation_euler", frame=f)

# 400 spirits float (signature ethereal motion)
for sp in spirits:
    phase = sp["_phase"]; speed = sp["_speed"]
    bx, by, bz = sp["_base_x"], sp["_base_y"], sp["_base_z"]
    ax, ay, az = sp["_amp_x"], sp["_amp_y"], sp["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.4 + phase)
        sp.location = (x, y, max(1, z))
        # Pulsing scale (signature ethereal)
        sc_sp = 0.7 + abs(math.sin(t * 2.0 + phase)) * 0.8
        sp.scale = (sc_sp, sc_sp, sc_sp)
        sp.keyframe_insert("location", frame=f)
        sp.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_acropolis_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_greek_acropolis_athens_temple] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_greek_acropolis_athens_temple] Parthenon 8+8+side columns + Athena gold 10m + Erechtheion + 4 caryatids + olive tree + 6 philosophers togas + 4 hoplites + 6 maenads + 8 amphoras + altar + 600 olive petals + 400 spirits")
print("⭐ FIXES: 1 ground + 600 olive petals + 400 divine spirits (signature Greek antiquity thematic mandatory) ⭐")
