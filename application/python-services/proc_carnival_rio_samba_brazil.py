"""
proc_carnival_rio_samba_brazil.py — 242e procédural AuroraIA (107e qualité)
Carnaval Rio de Janeiro samba: 3 floats + 8 sambistas + 6 batería + 4 capoeira + queen + tribunes + Christ Redentor + 600 paillettes + 400 confetti
FIXES : 1 ground + 600 sequins + 400 confetti (signature thematic particles)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB242)

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
M_SKY = mat("sky", (0.04, 0.03, 0.10, 1.0), 0.0, 0.7, emission=(0.05,0.04,0.13), emission_strength=0.6)
M_STAR = mat("star", (1.0, 0.95, 0.70, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.70), emission_strength=10.0)
M_MOON = mat("moon", (0.95, 0.92, 0.85, 1.0), 0.0, 0.20, emission=(0.92,0.90,0.82), emission_strength=4.0)

# Asphalt
M_ASPHALT = mat("asph", (0.18, 0.16, 0.16, 1.0), 0.0, 0.85, emission=(0.16,0.14,0.14), emission_strength=0.3)
M_ASPHALT_LINE = mat("line", (0.95, 0.92, 0.30, 1.0), 0.0, 0.55, emission=(0.92,0.88,0.30), emission_strength=2.5)

# Float colors signature
M_FLOAT_QUEEN_PINK = mat("fq_p", (1.0, 0.35, 0.65, 1.0), 0.0, 0.45, emission=(1.0,0.35,0.65), emission_strength=2.5)
M_FLOAT_PURPLE = mat("fp", (0.65, 0.25, 0.85, 1.0), 0.0, 0.40, emission=(0.65,0.25,0.85), emission_strength=2.3)
M_FLOAT_GOLD = mat("fg", (1.0, 0.85, 0.30, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.28), emission_strength=2.5)
M_FLOAT_RED = mat("fr", (0.95, 0.18, 0.18, 1.0), 0.0, 0.40, emission=(0.92,0.18,0.18), emission_strength=2.3)
M_FLOAT_GREEN = mat("fgr", (0.20, 0.85, 0.30, 1.0), 0.0, 0.40, emission=(0.20,0.80,0.30), emission_strength=2.3)
M_FLOAT_BLUE = mat("fb", (0.20, 0.45, 1.0, 1.0), 0.0, 0.40, emission=(0.20,0.45,1.0), emission_strength=2.5)
M_FLOAT_TURQUOISE = mat("ft", (0.15, 0.85, 0.78, 1.0), 0.0, 0.40, emission=(0.15,0.80,0.75), emission_strength=2.3)
M_FLOAT_ORANGE = mat("fo", (1.0, 0.55, 0.10, 1.0), 0.0, 0.40, emission=(1.0,0.55,0.10), emission_strength=2.4)
M_FLOAT_DARK = mat("fd", (0.25, 0.18, 0.18, 1.0), 0.0, 0.70)

FLOAT_COLORS = [M_FLOAT_QUEEN_PINK, M_FLOAT_PURPLE, M_FLOAT_GOLD, M_FLOAT_RED,
                M_FLOAT_GREEN, M_FLOAT_BLUE, M_FLOAT_TURQUOISE, M_FLOAT_ORANGE]

# Dragon (signature float 2)
M_DRAGON_GOLD = mat("dr_g", (1.0, 0.80, 0.25, 1.0), 0.90, 0.18, emission=(0.95,0.78,0.25), emission_strength=2.8)
M_DRAGON_RED = mat("dr_r", (0.95, 0.20, 0.15, 1.0), 0.0, 0.40, emission=(0.92,0.20,0.15), emission_strength=2.0)
M_DRAGON_EYE = mat("dr_e", (1.0, 0.30, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.30,0.20), emission_strength=20.0)

# Jungle animal (signature float 3)
M_JUNGLE_GREEN = mat("jg", (0.18, 0.55, 0.20, 1.0), 0.0, 0.55, emission=(0.18,0.50,0.20), emission_strength=1.5)
M_JUNGLE_DARK = mat("jd", (0.10, 0.30, 0.12, 1.0), 0.0, 0.70)
M_LEAF_BIG = mat("lb", (0.30, 0.85, 0.30, 1.0), 0.0, 0.55, emission=(0.28,0.80,0.30), emission_strength=1.5)

# Skin
M_SKIN_LIGHT = mat("sk_l", (0.92, 0.72, 0.55, 1.0), 0.0, 0.55, emission=(0.88,0.70,0.55), emission_strength=0.5)
M_SKIN_TAN = mat("sk_t", (0.78, 0.55, 0.38, 1.0), 0.0, 0.55, emission=(0.75,0.55,0.38), emission_strength=0.4)
M_SKIN_DARK = mat("sk_d", (0.45, 0.28, 0.18, 1.0), 0.0, 0.55, emission=(0.45,0.28,0.18), emission_strength=0.3)
SKIN_VARIANTS = [M_SKIN_LIGHT, M_SKIN_TAN, M_SKIN_DARK]

# Hair
M_HAIR_BLACK = mat("h_bk", (0.10, 0.06, 0.06, 1.0), 0.0, 0.55)
M_HAIR_BROWN = mat("h_br", (0.35, 0.18, 0.08, 1.0), 0.0, 0.55)
M_HAIR_BLOND = mat("h_bl", (0.85, 0.65, 0.30, 1.0), 0.0, 0.50)
HAIR_VARIANTS = [M_HAIR_BLACK, M_HAIR_BROWN, M_HAIR_BLOND]

# Bikini sequins (signature sambista)
M_BIKINI_GOLD = mat("bk_g", (1.0, 0.85, 0.20, 1.0), 0.95, 0.10, emission=(0.95,0.80,0.20), emission_strength=3.5)
M_BIKINI_SILVER = mat("bk_s", (0.92, 0.92, 0.95, 1.0), 0.95, 0.10, emission=(0.85,0.85,0.92), emission_strength=2.8)
M_BIKINI_PINK = mat("bk_p", (1.0, 0.30, 0.60, 1.0), 0.85, 0.15, emission=(0.95,0.30,0.58), emission_strength=3.0)
M_BIKINI_BLUE = mat("bk_b", (0.20, 0.55, 1.0, 1.0), 0.85, 0.15, emission=(0.20,0.55,1.0), emission_strength=2.8)
M_BIKINI_GREEN = mat("bk_gr", (0.20, 0.85, 0.40, 1.0), 0.85, 0.15, emission=(0.20,0.85,0.40), emission_strength=2.8)
M_BIKINI_PURPLE = mat("bk_pu", (0.75, 0.25, 0.95, 1.0), 0.85, 0.15, emission=(0.75,0.25,0.95), emission_strength=3.0)
M_BIKINI_RED = mat("bk_r", (1.0, 0.18, 0.15, 1.0), 0.85, 0.15, emission=(0.95,0.18,0.15), emission_strength=3.0)
M_BIKINI_TURQUOISE = mat("bk_t", (0.20, 0.95, 0.85, 1.0), 0.85, 0.15, emission=(0.20,0.92,0.82), emission_strength=2.8)
BIKINI_COLORS = [M_BIKINI_GOLD, M_BIKINI_SILVER, M_BIKINI_PINK, M_BIKINI_BLUE,
                 M_BIKINI_GREEN, M_BIKINI_PURPLE, M_BIKINI_RED, M_BIKINI_TURQUOISE]

# Feathers signature samba colors
M_FEATHER_PINK = mat("fe_p", (1.0, 0.45, 0.75, 1.0), 0.0, 0.45, emission=(1.0,0.45,0.75), emission_strength=2.2)
M_FEATHER_BLUE = mat("fe_b", (0.30, 0.65, 1.0, 1.0), 0.0, 0.45, emission=(0.30,0.65,1.0), emission_strength=2.2)
M_FEATHER_GREEN = mat("fe_g", (0.30, 0.95, 0.45, 1.0), 0.0, 0.45, emission=(0.30,0.95,0.45), emission_strength=2.2)
M_FEATHER_YELLOW = mat("fe_y", (1.0, 0.92, 0.20, 1.0), 0.0, 0.45, emission=(1.0,0.92,0.20), emission_strength=2.5)
M_FEATHER_RED = mat("fe_r", (1.0, 0.25, 0.30, 1.0), 0.0, 0.45, emission=(1.0,0.25,0.30), emission_strength=2.2)
M_FEATHER_PURPLE = mat("fe_pu", (0.85, 0.30, 1.0, 1.0), 0.0, 0.45, emission=(0.85,0.30,1.0), emission_strength=2.2)
M_FEATHER_ORANGE = mat("fe_o", (1.0, 0.55, 0.18, 1.0), 0.0, 0.45, emission=(1.0,0.55,0.18), emission_strength=2.2)
FEATHER_COLORS = [M_FEATHER_PINK, M_FEATHER_BLUE, M_FEATHER_GREEN, M_FEATHER_YELLOW,
                  M_FEATHER_RED, M_FEATHER_PURPLE, M_FEATHER_ORANGE]

# Drum
M_DRUM_RED = mat("dr_red", (0.85, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.80,0.15,0.15), emission_strength=1.0)
M_DRUM_SKIN = mat("dr_sk", (0.92, 0.78, 0.55, 1.0), 0.0, 0.65, emission=(0.85,0.72,0.52), emission_strength=0.8)
M_DRUM_METAL = mat("dr_m", (0.85, 0.85, 0.85, 1.0), 0.9, 0.20, emission=(0.80,0.80,0.80), emission_strength=1.5)

# Berimbau
M_WOOD = mat("wood", (0.50, 0.30, 0.15, 1.0), 0.0, 0.70, emission=(0.45,0.28,0.15), emission_strength=0.4)
M_WOOD_DARK = mat("wood_d", (0.30, 0.18, 0.08, 1.0), 0.0, 0.80)
M_GOURD = mat("gourd", (0.65, 0.45, 0.20, 1.0), 0.0, 0.65, emission=(0.60,0.42,0.20), emission_strength=0.5)
M_STRING = mat("string", (0.85, 0.85, 0.85, 1.0), 0.2, 0.30)

# Eyes/teeth
M_EYE_WHITE = mat("eye_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.30, emission=(0.92,0.88,0.82), emission_strength=0.6)
M_EYE_BLACK = mat("eye_bk", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS = mat("lips", (0.90, 0.20, 0.30, 1.0), 0.0, 0.35, emission=(0.85,0.20,0.30), emission_strength=0.6)

# Brazil flag
M_FLAG_GREEN = mat("fl_g", (0.05, 0.55, 0.20, 1.0), 0.0, 0.40, emission=(0.05,0.55,0.20), emission_strength=2.0)
M_FLAG_YELLOW = mat("fl_y", (1.0, 0.85, 0.15, 1.0), 0.0, 0.40, emission=(1.0,0.85,0.15), emission_strength=2.0)
M_FLAG_BLUE = mat("fl_b", (0.05, 0.18, 0.55, 1.0), 0.0, 0.40, emission=(0.05,0.18,0.55), emission_strength=2.0)
M_FLAG_WHITE = mat("fl_w", (0.95, 0.95, 0.95, 1.0), 0.0, 0.40, emission=(0.92,0.92,0.92), emission_strength=1.8)

# Stadium tribune
M_TRIBUNE = mat("trib", (0.55, 0.45, 0.35, 1.0), 0.0, 0.85)
M_TRIBUNE_RAIL = mat("trib_r", (0.85, 0.85, 0.85, 1.0), 0.7, 0.30)

# Projectors signature
M_PROJ_BEAM_PINK = mat("pb_p", (1.0, 0.45, 0.75, 1.0), 0.0, 0.10, emission=(1.0,0.45,0.75), emission_strength=12.0, alpha=0.45)
M_PROJ_BEAM_BLUE = mat("pb_b", (0.30, 0.55, 1.0, 1.0), 0.0, 0.10, emission=(0.30,0.55,1.0), emission_strength=12.0, alpha=0.45)
M_PROJ_BEAM_GREEN = mat("pb_g", (0.30, 1.0, 0.45, 1.0), 0.0, 0.10, emission=(0.30,1.0,0.45), emission_strength=12.0, alpha=0.45)
M_PROJ_BEAM_YELLOW = mat("pb_y", (1.0, 0.92, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.20), emission_strength=12.0, alpha=0.45)
PROJ_BEAMS = [M_PROJ_BEAM_PINK, M_PROJ_BEAM_BLUE, M_PROJ_BEAM_GREEN, M_PROJ_BEAM_YELLOW]

# Christ Redentor
M_CHRIST = mat("christ", (0.78, 0.75, 0.72, 1.0), 0.0, 0.65, emission=(0.72,0.68,0.65), emission_strength=1.5)

# Sequins / Confetti
M_SEQ_GOLD = mat("seq_g", (1.0, 0.92, 0.30, 1.0), 0.95, 0.10, emission=(0.95,0.88,0.30), emission_strength=4.0)
M_SEQ_PINK = mat("seq_p", (1.0, 0.30, 0.60, 1.0), 0.85, 0.15, emission=(0.95,0.30,0.60), emission_strength=3.5)
M_SEQ_SILVER = mat("seq_s", (0.95, 0.95, 0.95, 1.0), 0.95, 0.10, emission=(0.90,0.90,0.90), emission_strength=3.5)
M_SEQ_BLUE = mat("seq_b", (0.30, 0.55, 1.0, 1.0), 0.85, 0.15, emission=(0.30,0.55,1.0), emission_strength=3.5)
M_SEQ_GREEN = mat("seq_gr", (0.30, 1.0, 0.45, 1.0), 0.85, 0.15, emission=(0.30,0.95,0.45), emission_strength=3.5)
SEQ_COLORS = [M_SEQ_GOLD, M_SEQ_PINK, M_SEQ_SILVER, M_SEQ_BLUE, M_SEQ_GREEN]

# Confetti
M_CONF_PINK = mat("cf_p", (1.0, 0.30, 0.55, 1.0), 0.0, 0.40, emission=(1.0,0.30,0.55), emission_strength=2.5, alpha=0.9)
M_CONF_YELLOW = mat("cf_y", (1.0, 0.92, 0.20, 1.0), 0.0, 0.40, emission=(1.0,0.92,0.20), emission_strength=2.5, alpha=0.9)
M_CONF_BLUE = mat("cf_b", (0.20, 0.65, 1.0, 1.0), 0.0, 0.40, emission=(0.20,0.65,1.0), emission_strength=2.5, alpha=0.9)
M_CONF_GREEN = mat("cf_g", (0.30, 1.0, 0.45, 1.0), 0.0, 0.40, emission=(0.30,0.95,0.45), emission_strength=2.5, alpha=0.9)
M_CONF_PURPLE = mat("cf_pu", (0.85, 0.30, 1.0, 1.0), 0.0, 0.40, emission=(0.85,0.30,1.0), emission_strength=2.5, alpha=0.9)
M_CONF_ORANGE = mat("cf_o", (1.0, 0.55, 0.20, 1.0), 0.0, 0.40, emission=(1.0,0.55,0.20), emission_strength=2.5, alpha=0.9)
CONFETTI_COLORS = [M_CONF_PINK, M_CONF_YELLOW, M_CONF_BLUE, M_CONF_GREEN, M_CONF_PURPLE, M_CONF_ORANGE]

# Balloons
BALLOON_COLORS = CONFETTI_COLORS  # reuse

# ============ SKY ============
sky = smooth_sphere("sky", r=250, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Moon
moon = smooth_sphere("moon", r=3.5, segs=24, rings=18, loc=(-40, 80, 60), mat_=M_MOON)
# Stars
for si in range(120):
    sa = random.uniform(0, math.pi*2); sr = random.uniform(60, 180)
    sh = random.uniform(20, 80)
    smooth_sphere(f"star{si}", r=random.uniform(0.10, 0.30), segs=8, rings=6,
                  loc=(sr*math.cos(sa), sr*math.sin(sa), sh), mat_=M_STAR)

# ============ ONE clean asphalt sambódromo ground ============
ground = beveled_cube("ground", (180, 180, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_ASPHALT)
# Sambódromo central runway
runway = beveled_cube("runway", (16, 100, 0.30), bevel_offset=0.06, loc=(0, 0, 0.10), mat_=M_ASPHALT_LINE)
runway_inner = beveled_cube("runway_i", (14, 100, 0.35), bevel_offset=0.04, loc=(0, 0, 0.15), mat_=M_ASPHALT)
# Yellow center stripes (signature sambódromo)
for ci in range(20):
    cy_pos = -45 + ci * 5
    beveled_cube(f"stripe{ci}", (0.5, 2.0, 0.04), bevel_offset=0.02,
                 loc=(0, cy_pos, 0.18), mat_=M_ASPHALT_LINE)

# ============ CHRIST REDENTOR (background signature) ============
christ_e = empty("christ", loc=(60, 80, 0))
# Mountain
for mi in range(6):
    mz = mi * 4
    mr = 8 - mi * 0.9
    smooth_sphere(f"mt{mi}", r=mr, segs=20, rings=14, loc=(0, 0, mz),
                  parent=christ_e, mat_=M_JUNGLE_DARK, scale=(1, 1, 0.7))
# Christ statue base
cyl("christ_base", r=2, depth=2, segs=18, loc=(0, 0, 24), parent=christ_e, mat_=M_CHRIST)
# Body
cyl("christ_body", r=0.7, depth=4, segs=18, loc=(0, 0, 28), parent=christ_e, mat_=M_CHRIST)
# Head
smooth_sphere("christ_head", r=0.5, segs=20, rings=14, loc=(0, 0, 30.5),
              parent=christ_e, mat_=M_CHRIST)
# Arms outstretched (signature crucifix pose)
for side in (-1, 1):
    arm = cyl(f"christ_arm{side}", r=0.3, depth=3.5, segs=14, loc=(side*1.75, 0, 29),
              parent=christ_e, mat_=M_CHRIST)
    arm.rotation_euler = (0, math.radians(90), 0)
# Robe details
for ri in range(3):
    cyl(f"christ_robe{ri}", r=0.75 - ri*0.05, depth=0.10, segs=18,
        loc=(0, 0, 26 + ri*0.8), parent=christ_e, mat_=M_CHRIST)

# ============ 3 FLOATS (signature elaborate) ============
def make_float(name, loc, float_type="queen", scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)

    # Truck base (large platform)
    beveled_cube(f"{name}_truck", (4, 8, 0.8), bevel_offset=0.10, loc=(0, 0, 0.8),
                 parent=base, mat_=M_FLOAT_DARK)
    # Wheels
    for x in (-1, 1):
        for y in (-2, 2):
            w = cyl(f"{name}_w{x}{y}", r=0.5, depth=0.30, segs=18, loc=(x*1.8, y*0.6, 0.4),
                    parent=base, mat_=M_FLOAT_DARK)
            w.rotation_euler = (math.radians(90), 0, 0)
    # Decorative side panels
    for side in (-1, 1):
        col = random.choice(FLOAT_COLORS)
        beveled_cube(f"{name}_side{side}", (0.20, 7.8, 1.5), bevel_offset=0.06,
                     loc=(side*2.0, 0, 1.8), parent=base, mat_=col)
        # Sequin dots on side
        for sq in range(20):
            sq_y = -3.5 + sq * 0.40
            sq_z = 1.4 + (sq % 4) * 0.25
            smooth_sphere(f"{name}_sq{side}_{sq}", r=0.10,
                          loc=(side*2.10, sq_y, sq_z),
                          parent=base, mat_=random.choice(SEQ_COLORS))

    # Float-specific top decoration
    if float_type == "queen":
        # Queen pedestal (signature multi-tier elaborate)
        for tier in range(3):
            tier_z = 2.0 + tier * 1.5
            tier_w = 3.5 - tier * 0.8
            cyl(f"{name}_t{tier}", r=tier_w, depth=0.3, segs=22,
                loc=(0, 0, tier_z), parent=base, mat_=M_FLOAT_QUEEN_PINK)
            # Decorative gold rim
            cyl(f"{name}_tr{tier}", r=tier_w + 0.1, depth=0.10, segs=22,
                loc=(0, 0, tier_z + 0.10), parent=base, mat_=M_FLOAT_GOLD)
            # Sequin ring
            for si in range(16):
                sa = (si / 16.0) * math.pi * 2
                smooth_sphere(f"{name}_t{tier}_s{si}", r=0.12,
                              loc=(math.cos(sa)*tier_w, math.sin(sa)*tier_w, tier_z + 0.20),
                              parent=base, mat_=random.choice(SEQ_COLORS))
        # Queen herself on top
        q_e = empty(f"{name}_queen", (0, 0, 6.5), parent=base)
        # Body
        smooth_cone(f"{name}_q_body", r1=0.45, r2=0.30, depth=1.5, segs=14,
                    loc=(0, 0, 0.75), parent=q_e, mat_=M_BIKINI_GOLD)
        # Skin parts
        smooth_sphere(f"{name}_q_torso", r=0.40, segs=18, rings=12, loc=(0, 0, 0.85),
                      parent=q_e, mat_=M_SKIN_TAN, scale=(1, 0.9, 1.2))
        # Bikini top
        smooth_sphere(f"{name}_q_btop", r=0.42, segs=18, rings=12, loc=(0, 0, 1.20),
                      parent=q_e, mat_=M_BIKINI_GOLD, scale=(1.0, 0.5, 0.3))
        # Head
        smooth_sphere(f"{name}_q_head", r=0.20, segs=18, rings=14, loc=(0, 0, 1.65),
                      parent=q_e, mat_=M_SKIN_TAN)
        # Crown signature
        cyl(f"{name}_q_crown_b", r=0.22, depth=0.10, segs=16, loc=(0, 0, 1.85),
            parent=q_e, mat_=M_FLOAT_GOLD)
        for ci in range(8):
            ca = (ci / 8.0) * math.pi * 2
            smooth_cone(f"{name}_q_cr_sp{ci}", r1=0.04, r2=0.005, depth=0.25, segs=8,
                        loc=(math.cos(ca)*0.20, math.sin(ca)*0.20, 2.0),
                        parent=q_e, mat_=M_FLOAT_GOLD)
            # Jewel on tip
            smooth_sphere(f"{name}_q_cr_j{ci}", r=0.04,
                          loc=(math.cos(ca)*0.20, math.sin(ca)*0.20, 2.15),
                          parent=q_e, mat_=random.choice(SEQ_COLORS))
        # GIANT FEATHER PLUME (signature 1m+ tall)
        for fi in range(40):
            fa = random.uniform(0, math.pi*2)
            fr = random.uniform(0.10, 0.80)
            fz = random.uniform(1.5, 4.0)
            feat = smooth_cone(f"{name}_q_pl{fi}", r1=0.10, r2=0.005, depth=fz, segs=8,
                              loc=(math.cos(fa)*fr, math.sin(fa)*fr, 2.0 + fz/2),
                              parent=q_e, mat_=random.choice(FEATHER_COLORS))
            feat.rotation_euler = (math.radians(random.uniform(-15, 15)), 0, fa)
        # Wings of feathers behind
        for side in (-1, 1):
            for wi in range(15):
                wa = (wi / 15.0) * math.pi - math.pi/2
                wl = 1.0 + random.uniform(-0.2, 0.2)
                feat = smooth_cone(f"{name}_q_w{side}_{wi}", r1=0.06, r2=0.005, depth=wl, segs=8,
                                  loc=(side*(0.5 + math.cos(wa)*0.6), -0.3, 1.0 + math.sin(wa)*1.0),
                                  parent=q_e, mat_=random.choice(FEATHER_COLORS))
                feat.rotation_euler = (math.radians(-90 + side*30), 0, math.radians(side*60 + wi*5))

    elif float_type == "dragon":
        # Dragon body (long serpentine signature)
        dragon_e = empty(f"{name}_dragon", (0, 0, 2.5), parent=base)
        # Body segments
        for di in range(8):
            d_y = -3 + di * 0.8
            d_z = math.sin(di * 0.6) * 0.5
            smooth_sphere(f"{name}_d_b{di}", r=0.5 - di*0.03, segs=18, rings=14,
                          loc=(0, d_y, d_z), parent=dragon_e, mat_=M_DRAGON_GOLD,
                          scale=(1.2, 1.0, 1.0))
        # Dragon head signature (front)
        head_e = empty(f"{name}_d_he", (0, 4, 1.5), parent=dragon_e)
        head_e.rotation_euler = (math.radians(-20), 0, 0)
        smooth_sphere(f"{name}_d_head", r=0.8, segs=20, rings=14, loc=(0, 0, 0),
                      parent=head_e, mat_=M_DRAGON_GOLD, scale=(1.3, 1.5, 1.0))
        # Mouth open
        smooth_sphere(f"{name}_d_mouth", r=0.5, segs=16, rings=12, loc=(0, 0.6, -0.15),
                      parent=head_e, mat_=M_DRAGON_RED, scale=(1.2, 0.8, 0.6))
        # Glowing red eyes (signature)
        for side in (-1, 1):
            smooth_sphere(f"{name}_d_eye{side}", r=0.10,
                          loc=(side*0.30, 0.40, 0.30), parent=head_e, mat_=M_DRAGON_EYE)
        # Horns
        for side in (-1, 1):
            smooth_cone(f"{name}_d_h{side}", r1=0.10, r2=0.02, depth=0.55, segs=10,
                        loc=(side*0.35, -0.30, 0.35), parent=head_e,
                        mat_=M_DRAGON_GOLD).rotation_euler = (math.radians(-30), 0, math.radians(side*15))
        # Whiskers
        for side in (-1, 1):
            cyl(f"{name}_d_wh{side}", r=0.02, depth=0.8, segs=8,
                loc=(side*0.20, 0.65, -0.05), parent=head_e, mat_=M_DRAGON_RED).rotation_euler = (0, math.radians(side*60), math.radians(90))
        # Teeth row
        for ti in range(8):
            cyl(f"{name}_d_t{ti}", r=0.025, depth=0.10, segs=6,
                loc=((ti-3.5)*0.10, 0.55, -0.05), parent=head_e, mat_=M_EYE_WHITE)
        # Scales (signature spine)
        for sc in range(10):
            sc_y = -2 + sc * 0.7
            smooth_cone(f"{name}_d_sc{sc}", r1=0.15, r2=0.02, depth=0.35, segs=10,
                        loc=(0, sc_y, 0.6 + math.sin(sc*0.6)*0.3), parent=dragon_e, mat_=M_DRAGON_RED)
        # Tail tip
        smooth_cone(f"{name}_d_tail", r1=0.3, r2=0.05, depth=1.5, segs=12,
                    loc=(0, -4, -0.5), parent=dragon_e, mat_=M_DRAGON_GOLD).rotation_euler = (math.radians(90), 0, 0)
        # Wings
        for side in (-1, 1):
            wing = beveled_cube(f"{name}_d_wing{side}", (0.15, 2.5, 1.8), bevel_offset=0.06,
                                loc=(side*0.8, 0, 1.3), parent=dragon_e, mat_=M_DRAGON_RED)
            wing.rotation_euler = (math.radians(side*25), 0, 0)

    else:  # jungle
        # Big tree/jungle scene
        # Central giant flower/tree
        cyl(f"{name}_j_trunk", r=0.50, depth=5, segs=16, loc=(0, 0, 4.5),
            parent=base, mat_=M_WOOD_DARK)
        # Big leaves (signature tropical)
        for li in range(8):
            la = (li / 8.0) * math.pi * 2
            leaf_e = empty(f"{name}_j_l{li}_e", (math.cos(la)*0.3, math.sin(la)*0.3, 6.5), parent=base)
            leaf_e.rotation_euler = (math.radians(60), 0, la)
            for sl in range(5):
                smooth_sphere(f"{name}_j_l{li}_{sl}", r=0.20 + sl*0.10,
                              loc=(0, 0, sl*0.40), parent=leaf_e, mat_=M_LEAF_BIG,
                              scale=(2.5, 0.3, 1))
        # Animal on top (jaguar/macaw)
        # Macaw
        macaw_e = empty(f"{name}_macaw", (0, 0, 8), parent=base)
        # Body
        smooth_sphere(f"{name}_m_body", r=0.4, segs=18, rings=12, loc=(0, 0, 0),
                      parent=macaw_e, mat_=M_BIKINI_BLUE, scale=(1.2, 1.5, 1.0))
        # Head
        smooth_sphere(f"{name}_m_head", r=0.30, segs=16, rings=12, loc=(0, 0.6, 0.25),
                      parent=macaw_e, mat_=M_BIKINI_BLUE)
        # Beak (signature large)
        smooth_cone(f"{name}_m_beak", r1=0.15, r2=0.04, depth=0.30, segs=12,
                    loc=(0, 0.85, 0.15), parent=macaw_e, mat_=M_FLOAT_GOLD).rotation_euler = (math.radians(-110), 0, 0)
        # Wings spread
        for side in (-1, 1):
            wing = beveled_cube(f"{name}_m_w{side}", (0.10, 1.5, 0.6), bevel_offset=0.05,
                                loc=(side*0.40, 0, 0.10), parent=macaw_e, mat_=M_BIKINI_RED)
            wing.rotation_euler = (0, math.radians(side*30), 0)
            # Yellow wing tips
            beveled_cube(f"{name}_m_wt{side}", (0.10, 1.0, 0.4), bevel_offset=0.03,
                         loc=(side*0.50, -0.7, 0.05), parent=macaw_e, mat_=M_FLAG_YELLOW if False else M_BIKINI_GOLD).rotation_euler = (0, math.radians(side*30), 0)
        # Tail feathers
        for tf in range(5):
            ta = (tf - 2) * 0.10
            beveled_cube(f"{name}_m_tf{tf}", (0.08, 0.04, 1.0), bevel_offset=0.02,
                         loc=(ta*0.5, -0.5, -0.30), parent=macaw_e, mat_=random.choice(FEATHER_COLORS))

    base["_phase"] = random.uniform(0, math.pi*2)
    return base

floats = []
# 3 floats spaced along the runway
floats_data = [(-25, "queen"), (-5, "dragon"), (15, "jungle")]
for i, (fy, ft) in enumerate(floats_data):
    f = make_float(f"float{i}", (0, fy, 0), float_type=ft, scale=1.0, facing=0)
    floats.append(f)

# ============ 8 SAMBISTAS (signature samba dancers feathers + sequins) ============
def make_sambista(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    skin = random.choice(SKIN_VARIANTS)
    hair = random.choice(HAIR_VARIANTS)
    bikini_color = random.choice(BIKINI_COLORS)
    feather_color1 = random.choice(FEATHER_COLORS)
    feather_color2 = random.choice(FEATHER_COLORS)

    # Body (hourglass figure signature)
    # Hips
    smooth_sphere(f"{name}_hips", r=0.30*scale, segs=18, rings=12, loc=(0, 0, 1.0*scale),
                  parent=base, mat_=skin, scale=(1.3, 0.9, 0.9))
    # Bikini bottom
    smooth_sphere(f"{name}_bb", r=0.32*scale, segs=18, rings=12, loc=(0, 0, 1.0*scale),
                  parent=base, mat_=bikini_color, scale=(1.3, 0.95, 0.5))
    # Sequin dots on bottom
    for sq in range(8):
        sa = (sq / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_bbs{sq}", r=0.04*scale,
                      loc=(math.cos(sa)*0.32*scale, math.sin(sa)*0.20*scale, 0.95*scale),
                      parent=base, mat_=M_BIKINI_GOLD)
    # Waist
    smooth_cone(f"{name}_waist", r1=0.28*scale, r2=0.22*scale, depth=0.4*scale, segs=14,
                loc=(0, 0, 1.30*scale), parent=base, mat_=skin)
    # Torso
    smooth_sphere(f"{name}_torso", r=0.30*scale, segs=18, rings=12, loc=(0, 0, 1.70*scale),
                  parent=base, mat_=skin, scale=(1.1, 0.85, 1.0))
    # Bikini top (signature triangle)
    for side in (-1, 1):
        bt = beveled_cube(f"{name}_bt{side}", (0.18*scale, 0.04*scale, 0.18*scale), bevel_offset=0.02,
                         loc=(side*0.18*scale, -0.18*scale, 1.78*scale), parent=base, mat_=bikini_color)
        # Sequins
        for sq in range(3):
            smooth_sphere(f"{name}_bts{side}_{sq}", r=0.025*scale,
                          loc=(side*0.18*scale, -0.20*scale, 1.78*scale + (sq-1)*0.05*scale),
                          parent=base, mat_=M_BIKINI_GOLD)
    # Strings
    for side in (-1, 1):
        cyl(f"{name}_str{side}", r=0.01*scale, depth=0.10*scale, segs=6,
            loc=(side*0.27*scale, 0, 1.85*scale), parent=base, mat_=bikini_color)
    # Long legs
    for side in (-1, 1):
        leg_e = empty(f"{name}_le{side}", (side*0.12*scale, 0, 0.95*scale), parent=base)
        leg_e.rotation_euler = (math.radians(side*5), 0, 0)
        cyl(f"{name}_thigh{side}", r=0.10*scale, depth=0.55*scale, segs=10,
            loc=(0, 0, -0.27*scale), parent=leg_e, mat_=skin)
        smooth_sphere(f"{name}_knee{side}", r=0.08*scale, loc=(0, 0, -0.55*scale),
                      parent=leg_e, mat_=skin)
        cyl(f"{name}_calf{side}", r=0.08*scale, depth=0.50*scale, segs=10,
            loc=(0, 0, -0.80*scale), parent=leg_e, mat_=skin)
        # Foot
        beveled_cube(f"{name}_foot{side}", (0.08*scale, 0.20*scale, 0.05*scale), bevel_offset=0.01,
                     loc=(0, -0.05*scale, -1.05*scale), parent=leg_e, mat_=skin)
        # High heel
        cyl(f"{name}_heel{side}", r=0.025*scale, depth=0.12*scale, segs=8,
            loc=(0, 0.08*scale, -1.12*scale), parent=leg_e, mat_=M_FLOAT_GOLD)
    # Long arms with raised pose
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.85*scale), parent=base)
        sh.rotation_euler = (math.radians(-90 - side*30), 0, math.radians(side*-30))
        cyl(f"{name}_uarm{side_idx}", r=0.06*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=skin)
        # Forearm
        fa = empty(f"{name}_fa{side_idx}", (0, 0, -0.40*scale), parent=sh)
        fa.rotation_euler = (math.radians(-30), 0, 0)
        cyl(f"{name}_fa_b{side_idx}", r=0.05*scale, depth=0.38*scale, segs=10,
            loc=(0, 0, -0.19*scale), parent=fa, mat_=skin)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.06*scale, loc=(0, 0, -0.40*scale),
                      parent=fa, mat_=skin, scale=(0.7, 1.2, 0.5))
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.10*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.20*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=skin, scale=(1, 1.05, 1.1))
    # Hair (long flowing)
    for hi in range(12):
        ha = (hi / 12.0) * math.pi * 2
        hl = random.uniform(0.30, 0.50)
        hcs = beveled_cube(f"{name}_hr{hi}", (0.06*scale, 0.10*scale, hl*scale), bevel_offset=0.02,
                          loc=(math.cos(ha)*0.18*scale, math.sin(ha)*0.10*scale - 0.10*scale, -hl*scale/2),
                          parent=head_e, mat_=hair)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04*scale,
                      loc=(side*0.07*scale, -0.18*scale, 0.05*scale), parent=head_e, mat_=M_EYE_WHITE)
        smooth_sphere(f"{name}_pup{side}", r=0.02*scale,
                      loc=(side*0.07*scale, -0.20*scale, 0.05*scale), parent=head_e, mat_=M_EYE_BLACK)
    # Lips
    beveled_cube(f"{name}_lips", (0.10*scale, 0.04*scale, 0.04*scale), bevel_offset=0.01,
                 loc=(0, -0.20*scale, -0.10*scale), parent=head_e, mat_=M_LIPS)
    # GIANT FEATHER HEADDRESS (signature)
    hd_e = empty(f"{name}_hd", (0, 0, 0.20*scale), parent=head_e)
    # Crown base
    cyl(f"{name}_hd_base", r=0.22*scale, depth=0.08*scale, segs=16, loc=(0, 0, 0),
        parent=hd_e, mat_=bikini_color)
    # Feathers in fan pattern
    for fi in range(25):
        fa = (fi / 25.0) * math.pi - math.pi/2
        fl_len = random.uniform(0.8, 1.5)
        ft_c = feather_color1 if fi % 2 == 0 else feather_color2
        feat = smooth_cone(f"{name}_hd_f{fi}", r1=0.05*scale, r2=0.003*scale, depth=fl_len*scale, segs=8,
                          loc=(math.sin(fa)*0.20*scale, 0.04*scale, fl_len*scale/2),
                          parent=hd_e, mat_=ft_c)
        feat.rotation_euler = (math.radians(-15), 0, fa)
    # Back wings of feathers (signature large costume)
    wings_e = empty(f"{name}_wings", (0, 0.20*scale, 1.50*scale), parent=base)
    for side in (-1, 1):
        for wi in range(15):
            wa = (wi / 15.0) * math.pi - math.pi/2
            wl = random.uniform(0.8, 1.3)
            ft_c = feather_color1 if wi % 2 == 0 else feather_color2
            feat = smooth_cone(f"{name}_w{side}_{wi}", r1=0.04*scale, r2=0.003*scale, depth=wl*scale, segs=8,
                              loc=(side*0.30*scale + math.cos(wa)*0.40*scale, 0,
                                   math.sin(wa)*0.70*scale + 0.20*scale),
                              parent=wings_e, mat_=ft_c)
            feat.rotation_euler = (math.radians(-90 + wi*3), 0, math.radians(side*60 + wi*4))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "wings": wings_e, "hd": hd_e}

sambistas = []
# 8 sambistas dancing on/near floats
sambista_pos = [(-3, -28, math.radians(0)), (3, -28, math.radians(0)),
                (-4, -22, math.radians(0)), (4, -22, math.radians(0)),
                (-4, -8, math.radians(0)), (4, -8, math.radians(0)),
                (-3, 10, math.radians(0)), (3, 10, math.radians(0))]
for i, (sx, sy, fac) in enumerate(sambista_pos):
    s = make_sambista(f"sambista{i}", (sx, sy, 0), scale=1.0, facing=fac)
    sambistas.append(s)

# ============ 6 BATERÍA percussionists ============
def make_batería(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    skin = random.choice(SKIN_VARIANTS)
    # Body
    smooth_cone(f"{name}_torso", r1=0.30*scale, r2=0.35*scale, depth=0.8*scale, segs=14,
                loc=(0, 0, 1.4*scale), parent=base, mat_=M_FLOAT_GREEN)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.13*scale, depth=1.0*scale, segs=10,
            loc=(side*0.13*scale, 0, 0.5*scale), parent=base, mat_=M_FLAG_YELLOW)
    # Arms holding drum
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.75*scale), parent=base)
        sh.rotation_euler = (math.radians(-50), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side_idx}", r=0.07*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=skin)
        # Forearm
        fa = empty(f"{name}_fa{side_idx}", (0, 0, -0.40*scale), parent=sh)
        fa.rotation_euler = (math.radians(-50), 0, 0)
        cyl(f"{name}_fa_b{side_idx}", r=0.06*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.18*scale), parent=fa, mat_=skin)
        # Drumstick
        cyl(f"{name}_stick{side_idx}", r=0.018*scale, depth=0.25*scale, segs=6,
            loc=(0, 0, -0.50*scale), parent=fa, mat_=M_WOOD)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.0*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=skin)
    # Cap signature
    cyl(f"{name}_cap", r=0.20*scale, depth=0.05*scale, segs=14, loc=(0, 0, 0.20*scale),
        parent=head_e, mat_=M_FLOAT_RED)
    smooth_sphere(f"{name}_cap_t", r=0.18*scale, loc=(0, 0, 0.20*scale),
                  parent=head_e, mat_=M_FLOAT_RED, scale=(1, 1, 0.5))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.03*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.03*scale), parent=head_e, mat_=M_EYE_BLACK)
    # Surdo drum (signature large)
    drum_e = empty(f"{name}_drum", (0.30*scale, -0.10*scale, 1.0*scale), parent=base)
    drum_e.rotation_euler = (math.radians(-30), 0, 0)
    # Drum body
    cyl(f"{name}_d_b", r=0.30*scale, depth=0.45*scale, segs=20, loc=(0, 0, 0),
        parent=drum_e, mat_=M_DRUM_RED)
    # Top skin
    cyl(f"{name}_d_t", r=0.30*scale, depth=0.03*scale, segs=20, loc=(0, 0, 0.23*scale),
        parent=drum_e, mat_=M_DRUM_SKIN)
    # Metal rim
    cyl(f"{name}_d_rim", r=0.32*scale, depth=0.03*scale, segs=22, loc=(0, 0, 0.25*scale),
        parent=drum_e, mat_=M_DRUM_METAL)
    # Tension rods
    for ti in range(8):
        ta = (ti / 8.0) * math.pi * 2
        cyl(f"{name}_d_rod{ti}", r=0.015*scale, depth=0.45*scale, segs=6,
            loc=(math.cos(ta)*0.30*scale, math.sin(ta)*0.30*scale, 0),
            parent=drum_e, mat_=M_DRUM_METAL)
    # Strap over shoulder
    cyl(f"{name}_strap", r=0.02*scale, depth=0.8*scale, segs=8,
        loc=(0.15*scale, -0.05*scale, 1.5*scale), parent=base,
        mat_=M_FLOAT_RED).rotation_euler = (math.radians(60), 0, math.radians(30))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "L": None, "R": None, "drum": drum_e, "he": head_e}

batería = []
# 6 percussionists around floats
batería_pos = [(-7, -25, math.radians(180)), (7, -25, math.radians(180)),
                (-7, -10, math.radians(180)), (7, -10, math.radians(180)),
                (-7, 5, math.radians(180)), (7, 5, math.radians(180))]
for i, (bx, by, fac) in enumerate(batería_pos):
    b = make_batería(f"bateria{i}", (bx, by, 0), scale=1.0, facing=fac)
    batería.append(b)

# ============ 4 CAPOEIRA musicians berimbau ============
def make_capoeira(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    skin = random.choice(SKIN_VARIANTS)
    # White outfit
    smooth_cone(f"{name}_torso", r1=0.28*scale, r2=0.32*scale, depth=0.7*scale, segs=14,
                loc=(0, 0, 1.4*scale), parent=base, mat_=M_FLAG_WHITE)
    # Pants white
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.12*scale, depth=1.0*scale, segs=10,
            loc=(side*0.12*scale, 0, 0.5*scale), parent=base, mat_=M_FLAG_WHITE)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=skin)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.03*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.02*scale), parent=head_e, mat_=M_EYE_BLACK)
    # Arms holding berimbau
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.70*scale), parent=base)
        if side == -1:
            sh.rotation_euler = (math.radians(-100), 0, math.radians(15))
        else:
            sh.rotation_euler = (math.radians(-50), 0, math.radians(-15))
        cyl(f"{name}_uarm{side_idx}", r=0.06*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=skin)
        cyl(f"{name}_fa{side_idx}", r=0.05*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=skin)
    # Berimbau (signature bow + gourd + string)
    ber_e = empty(f"{name}_ber", (-0.40*scale, 0, 1.0*scale), parent=base)
    # Bow stick
    cyl(f"{name}_ber_b", r=0.025*scale, depth=1.5*scale, segs=10, loc=(0, 0, 0.30*scale),
        parent=ber_e, mat_=M_WOOD).rotation_euler = (math.radians(15), 0, 0)
    # Gourd cabaça (signature large)
    smooth_sphere(f"{name}_ber_g", r=0.18*scale, segs=18, rings=12, loc=(0.15*scale, 0, 0.50*scale),
                  parent=ber_e, mat_=M_GOURD)
    # String taut
    cyl(f"{name}_ber_s", r=0.005*scale, depth=1.5*scale, segs=6, loc=(-0.05*scale, 0, 0.30*scale),
        parent=ber_e, mat_=M_STRING).rotation_euler = (math.radians(15), 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "ber": ber_e, "he": head_e}

capoeiras = []
capoeira_pos = [(-10, -15, math.radians(90)), (10, -15, math.radians(-90)),
                 (-10, 0, math.radians(90)), (10, 0, math.radians(-90))]
for i, (cx, cy, fac) in enumerate(capoeira_pos):
    c = make_capoeira(f"capoeira{i}", (cx, cy, 0), scale=1.0, facing=fac)
    capoeiras.append(c)

# ============ TRIBUNES (signature 2 sides with spectators) ============
def make_tribune(side_mul):
    t_e = empty(f"tribune_{side_mul}", (side_mul * 14, 0, 0))
    # Tier seats
    for row in range(5):
        rz = row * 1.2
        rw = 50
        rd = 2 + row * 0.3
        # Seat
        beveled_cube(f"trib{side_mul}_s{row}", (rd, rw, 0.4), bevel_offset=0.06,
                     loc=(0, 0, rz + 0.2), parent=t_e, mat_=M_TRIBUNE)
        # Rail
        cyl(f"trib{side_mul}_r{row}", r=0.04, depth=rw, segs=8,
            loc=(rd/2, 0, rz + 1.0), parent=t_e, mat_=M_TRIBUNE_RAIL).rotation_euler = (math.radians(90), 0, 0)
    # Spectators (15 per side, 30 total)
    for spi in range(15):
        sp_y = -40 + spi * 5.5
        sp_row = spi % 5
        sp_z = sp_row * 1.2 + 0.8
        # Spectator
        spec_color = random.choice(FLOAT_COLORS)
        cyl(f"sp{side_mul}_{spi}", r=0.15, depth=0.6, segs=10,
            loc=(0.3, sp_y, sp_z), parent=t_e, mat_=spec_color)
        skin = random.choice(SKIN_VARIANTS)
        smooth_sphere(f"sp{side_mul}_h{spi}", r=0.13, segs=14, rings=10,
                      loc=(0.3, sp_y, sp_z + 0.45), parent=t_e, mat_=skin)
        # Arms raised cheering
        for side in (-1, 1):
            cyl(f"sp{side_mul}_a{spi}_{side}", r=0.04, depth=0.30, segs=6,
                loc=(0.3, sp_y + side*0.18, sp_z + 0.55), parent=t_e, mat_=skin).rotation_euler = (0, math.radians(side*-30), 0)
    return t_e

tribune_left = make_tribune(-1)
tribune_right = make_tribune(1)

# ============ 6 BRAZIL FLAGS + projectors ============
# 6 projectors signature
projectors = []
proj_pos = [(-13, -40, 8), (13, -40, 8), (-13, 0, 8), (13, 0, 8), (-13, 40, 8), (13, 40, 8)]
for pi, (px, py, pz) in enumerate(proj_pos):
    p_e = empty(f"proj{pi}", (px, py, pz))
    # Body
    beveled_cube(f"proj_b{pi}", (0.5, 0.5, 0.4), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=p_e, mat_=M_FLOAT_DARK)
    # Lens
    cyl(f"proj_l{pi}", r=0.18, depth=0.10, segs=14, loc=(0, 0, -0.25),
        parent=p_e, mat_=M_DRUM_METAL)
    # BEAM (signature)
    beam_e = empty(f"proj_beam{pi}_e", (0, 0, -0.30), parent=p_e)
    beam_color = PROJ_BEAMS[pi % len(PROJ_BEAMS)]
    beam = smooth_cone(f"proj_bm{pi}", r1=0.18, r2=4.5, depth=10, segs=18,
                      loc=(0, 0, -5), parent=beam_e, mat_=beam_color)
    p_e["_phase"] = random.uniform(0, math.pi*2)
    projectors.append({"e": p_e, "beam": beam_e})

# Brazil flag on pole
flag_e = empty("brflag", loc=(0, -45, 0))
cyl("flag_pole", r=0.10, depth=10, segs=10, loc=(0, 0, 5), parent=flag_e, mat_=M_TRIBUNE_RAIL)
# Flag green field
beveled_cube("fl_green", (3, 0.05, 2), bevel_offset=0.04, loc=(1.5, 0, 9), parent=flag_e, mat_=M_FLAG_GREEN)
# Yellow diamond
diamond_e = empty("fl_dia_e", (1.5, -0.05, 9), parent=flag_e)
diamond_e.rotation_euler = (0, 0, math.radians(45))
beveled_cube("fl_dia", (1.4, 0.04, 1.4), bevel_offset=0.04, loc=(0, 0, 0), parent=diamond_e, mat_=M_FLAG_YELLOW)
# Blue circle
smooth_sphere("fl_circ", r=0.5, segs=18, rings=14, loc=(1.5, -0.08, 9),
              parent=flag_e, mat_=M_FLAG_BLUE, scale=(1, 0.1, 1))
flag_e["_phase"] = 0

# ============ BALLOONS in sky ============
for bi in range(15):
    bax = random.uniform(-25, 25)
    bay = random.uniform(-40, 30)
    baz = random.uniform(10, 25)
    bal_e = empty(f"balloon{bi}", (bax, bay, baz))
    smooth_sphere(f"bal_b{bi}", r=0.6, segs=16, rings=12, loc=(0, 0, 0),
                  parent=bal_e, mat_=random.choice(BALLOON_COLORS),
                  scale=(1, 1, 1.2))
    # Knot
    smooth_sphere(f"bal_k{bi}", r=0.08, loc=(0, 0, -0.7),
                  parent=bal_e, mat_=random.choice(BALLOON_COLORS))
    # String down
    cyl(f"bal_s{bi}", r=0.01, depth=4, segs=6, loc=(0, 0, -2.5),
        parent=bal_e, mat_=M_FLAG_WHITE)
    bal_e["_phase"] = random.uniform(0, math.pi*2)

# ============================================================
# ⭐ 600 SEQUINS + 400 CONFETTI (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
sequins = []
for i in range(600):
    px = random.uniform(-30, 30)
    py = random.uniform(-50, 50)
    pz = random.uniform(0.5, 14)
    s_obj = beveled_cube(f"seq{i}", (0.10, 0.02, 0.10), bevel_offset=0.01,
                         loc=(px, py, pz), mat_=random.choice(SEQ_COLORS))
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(0.5, 1.5)
    s_obj["_amp_y"] = random.uniform(0.5, 1.5)
    s_obj["_amp_z"] = random.uniform(0.5, 1.0)
    s_obj["_speed"] = random.uniform(0.6, 1.5)
    s_obj["_fall"] = random.uniform(1.5, 3.0)
    sequins.append(s_obj)

# 400 confetti
confetti = []
for i in range(400):
    px = random.uniform(-25, 25)
    py = random.uniform(-45, 45)
    pz = random.uniform(1, 16)
    c_obj = beveled_cube(f"conf{i}", (0.12, 0.04, 0.18), bevel_offset=0.02,
                         loc=(px, py, pz), mat_=random.choice(CONFETTI_COLORS))
    c_obj["_phase"] = random.uniform(0, math.pi*2)
    c_obj["_base_x"] = px; c_obj["_base_y"] = py; c_obj["_base_z"] = pz
    c_obj["_amp_x"] = random.uniform(1.5, 3.5)
    c_obj["_amp_y"] = random.uniform(1.5, 3.5)
    c_obj["_amp_z"] = random.uniform(0.5, 1.5)
    c_obj["_speed"] = random.uniform(0.8, 2.0)
    confetti.append(c_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Sambistas dance hips swing + arm movement + wings
for s in sambistas:
    phase = s["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Hips swing signature
        s["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(6),
                                     math.cos(t * 3.0 + phase) * math.radians(8),
                                     math.sin(t * 1.5 + phase) * math.radians(5))
        s["root"].location.z = abs(math.sin(t * 4.0 + phase)) * 0.15
        s["root"].keyframe_insert("rotation_euler", frame=f)
        s["root"].keyframe_insert("location", frame=f)
        # Wings undulate
        s["wings"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(5),
                                      math.cos(t * 2.5 + phase) * math.radians(10), 0)
        s["wings"].keyframe_insert("rotation_euler", frame=f)
        # Headdress sway
        s["hd"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(4),
                                   math.cos(t * 2.0 + phase) * math.radians(4), 0)
        s["hd"].keyframe_insert("rotation_euler", frame=f)
        # Head
        s["he"].rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(15))
        s["he"].keyframe_insert("rotation_euler", frame=f)

# Bateria drumming
for b in batería:
    phase = b["root"]["_phase"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Body rhythm
        b["root"].rotation_euler = (math.sin(t * 5.0 + phase) * math.radians(4),
                                     0, b["root"].rotation_euler.z)
        b["root"].keyframe_insert("rotation_euler", frame=f)
        # Head bob
        b["he"].rotation_euler = (math.sin(t * 5.0 + phase) * math.radians(8), 0,
                                   math.cos(t * 4.0 + phase) * math.radians(5))
        b["he"].keyframe_insert("rotation_euler", frame=f)
        # Drum slight vibration
        s_d = 1 + math.sin(t * 8.0 + phase) * 0.04
        b["drum"].scale = (s_d, s_d, 1)
        b["drum"].keyframe_insert("scale", frame=f)

# Capoeira berimbau swings
for c in capoeiras:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        c["ber"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(8), 0,
                                    math.cos(t * 1.5 + phase) * math.radians(5))
        c["ber"].keyframe_insert("rotation_euler", frame=f)
        c["root"].rotation_euler = (0, math.sin(t * 1.2 + phase) * math.radians(3),
                                     c["root"].rotation_euler.z)
        c["root"].keyframe_insert("rotation_euler", frame=f)

# Floats roll slowly forward
for fi, fl in enumerate(floats):
    phase = fl["_phase"]
    base_y = fl.location.y
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        fl.location.y = base_y + t * 0.5
        fl.location.z = math.sin(t * 1.0 + phase) * 0.05
        fl.keyframe_insert("location", frame=f)

# Projectors sweep color beams
for pr in projectors:
    phase = pr["e"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        pr["beam"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(20),
                                      math.cos(t * 1.5 + phase) * math.radians(15),
                                      math.sin(t * 0.8 + phase) * math.radians(10))
        pr["beam"].keyframe_insert("rotation_euler", frame=f)

# Brazil flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(8))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 sequins twinkling falling
for s in sequins:
    phase = s["_phase"]; speed = s["_speed"]; fall = s["_fall"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.3)
        if z < 0.3: z = bz
        s.location = (x, y, max(0.2, z))
        s.rotation_euler = (t * 4.0 + phase, t * 3.0 + phase, t * 5.0 + phase)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("rotation_euler", frame=f)

# 400 confetti erratic flight
for c in confetti:
    phase = c["_phase"]; speed = c["_speed"]
    bx, by, bz = c["_base_x"], c["_base_y"], c["_base_z"]
    ax, ay, az = c["_amp_x"], c["_amp_y"], c["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase) + 0.5*math.sin(t * speed * 4 + phase * 2)
        y = by + ay * math.cos(t * speed * 0.9 + phase) + 0.5*math.cos(t * speed * 4 + phase)
        z = bz + az * math.sin(t * speed * 1.5 + phase)
        c.location = (x, y, max(0.5, z))
        c.rotation_euler = (t * 5.0 + phase, t * 4.0 + phase, t * 6.0 + phase)
        c.keyframe_insert("location", frame=f)
        c.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_carnival_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_carnival_rio_samba_brazil] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_carnival_rio_samba_brazil] sambódromo + Christ Redentor + 3 floats (queen+dragon+macaw) + 8 sambistas feathered + 6 batería drums + 4 capoeira berimbau + 2 tribunes 30 spectators + 6 projectors + Brazil flag + 15 balloons + 600 sequins + 400 confetti")
print("⭐ FIXES: 1 ground + 600 sequins + 400 confetti (signature carnival thematic mandatory) ⭐")
