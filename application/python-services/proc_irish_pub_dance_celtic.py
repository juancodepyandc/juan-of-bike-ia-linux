"""
proc_irish_pub_dance_celtic.py — 251e procédural AuroraIA (116e qualité)
Irish Dublin pub: bar + 6 step dancers + 4 musicians (fiddle+tin whistle+bodhran+guitar) + 8 patrons + leprechaun + pot of gold + rainbow + fireplace + Guinness pints + 600 stout bubbles + 400 celtic notes
FIXES : 1 ground + 600 bubbles + 400 musical notes (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB251)

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

# Pub interior ambient
M_CEILING = mat("ceiling", (0.18, 0.12, 0.08, 1.0), 0.0, 0.85, emission=(0.18,0.12,0.08), emission_strength=0.4)
M_WALL_GREEN = mat("wall_g", (0.18, 0.42, 0.22, 1.0), 0.0, 0.75, emission=(0.18,0.40,0.22), emission_strength=0.5)
M_WALL_WOOD = mat("wall_w", (0.42, 0.25, 0.12, 1.0), 0.0, 0.75, emission=(0.40,0.25,0.12), emission_strength=0.4)
M_WALL_PLASTER = mat("wall_p", (0.85, 0.78, 0.62, 1.0), 0.0, 0.75, emission=(0.80,0.75,0.62), emission_strength=0.5)

# Pub floor wood
M_FLOOR_WOOD_DARK = mat("fl_wd", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85, emission=(0.30,0.18,0.08), emission_strength=0.4)
M_FLOOR_WOOD = mat("fl_w", (0.55, 0.32, 0.18, 1.0), 0.0, 0.80, emission=(0.50,0.30,0.18), emission_strength=0.4)
M_FLOOR_PLANK = mat("fl_p", (0.45, 0.26, 0.12, 1.0), 0.0, 0.85)

# Bar materials
M_BAR_WOOD = mat("bar_w", (0.32, 0.18, 0.08, 1.0), 0.0, 0.65, emission=(0.30,0.18,0.08), emission_strength=0.4)
M_BAR_TOP = mat("bar_t", (0.45, 0.28, 0.15, 1.0), 0.1, 0.30, emission=(0.42,0.28,0.15), emission_strength=0.5)
M_BRASS = mat("brass", (0.85, 0.65, 0.30, 1.0), 0.95, 0.20, emission=(0.80,0.62,0.30), emission_strength=1.5)
M_BAR_BRASS_RAIL = mat("rail", (0.92, 0.78, 0.30, 1.0), 0.95, 0.15, emission=(0.88,0.75,0.30), emission_strength=2.0)

# Guinness stout signature
M_STOUT = mat("stout", (0.05, 0.04, 0.03, 1.0), 0.1, 0.40, emission=(0.08,0.06,0.05), emission_strength=0.8)
M_STOUT_FOAM = mat("foam", (0.92, 0.82, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.78,0.62), emission_strength=1.5)
M_PINT_GLASS = mat("pint_g", (0.85, 0.85, 0.85, 1.0), 0.0, 0.10, emission=(0.80,0.80,0.80), emission_strength=0.5, alpha=0.35)

# Whiskey
M_WHISKEY = mat("whisky", (0.85, 0.55, 0.18, 1.0), 0.1, 0.20, emission=(0.80,0.52,0.18), emission_strength=1.2, alpha=0.75)
M_GIN = mat("gin", (0.92, 0.95, 0.98, 1.0), 0.1, 0.20, alpha=0.40)

# Skin
M_SKIN_PALE_I = mat("skin", (0.95, 0.82, 0.75, 1.0), 0.0, 0.55, emission=(0.90,0.80,0.72), emission_strength=0.4)
M_SKIN_FRECKLE = mat("skin_f", (0.95, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.90,0.75,0.62), emission_strength=0.4)
SKIN_VARIANTS_I = [M_SKIN_PALE_I, M_SKIN_FRECKLE]

# Irish red hair (signature)
M_HAIR_RED_IR = mat("h_r", (0.85, 0.32, 0.12, 1.0), 0.0, 0.60, emission=(0.80,0.30,0.12), emission_strength=0.4)
M_HAIR_GINGER_IR = mat("h_g", (0.92, 0.48, 0.18, 1.0), 0.0, 0.60, emission=(0.88,0.45,0.18), emission_strength=0.4)
M_HAIR_BROWN_IR = mat("h_b", (0.32, 0.18, 0.10, 1.0), 0.0, 0.60)
M_HAIR_BLOND_IR = mat("h_bl", (0.85, 0.65, 0.30, 1.0), 0.0, 0.55)
HAIR_VARIANTS_I = [M_HAIR_RED_IR, M_HAIR_GINGER_IR, M_HAIR_BROWN_IR, M_HAIR_BLOND_IR]

# Step dance costumes signature
M_DANCE_GREEN = mat("dr_g", (0.20, 0.62, 0.30, 1.0), 0.0, 0.55, emission=(0.18,0.60,0.30), emission_strength=0.8)
M_DANCE_RED = mat("dr_r", (0.78, 0.20, 0.20, 1.0), 0.0, 0.55, emission=(0.72,0.20,0.20), emission_strength=0.7)
M_DANCE_PURPLE = mat("dr_p", (0.55, 0.20, 0.78, 1.0), 0.0, 0.55, emission=(0.52,0.20,0.75), emission_strength=0.7)
M_DANCE_BLUE = mat("dr_b", (0.20, 0.45, 0.85, 1.0), 0.0, 0.55, emission=(0.18,0.42,0.80), emission_strength=0.7)
M_DANCE_GOLD_TRIM = mat("dr_gt", (0.95, 0.78, 0.25, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.25), emission_strength=1.2)
DANCE_VARIANTS = [M_DANCE_GREEN, M_DANCE_RED, M_DANCE_PURPLE, M_DANCE_BLUE]

# Dance shoes black with buckle
M_DANCE_SHOE = mat("d_sh", (0.10, 0.08, 0.08, 1.0), 0.5, 0.30, emission=(0.10,0.08,0.08), emission_strength=0.5)
M_DANCE_BUCKLE = mat("d_bk", (0.95, 0.78, 0.30, 1.0), 0.95, 0.15, emission=(0.92,0.75,0.30), emission_strength=2.0)

# Casual clothes patrons
M_SHIRT_CHECK_GREEN = mat("sh_g", (0.20, 0.55, 0.25, 1.0), 0.0, 0.75)
M_SHIRT_CHECK_RED = mat("sh_r", (0.65, 0.18, 0.18, 1.0), 0.0, 0.75)
M_SHIRT_CHECK_BLUE = mat("sh_b", (0.20, 0.35, 0.62, 1.0), 0.0, 0.75)
M_SHIRT_BROWN = mat("sh_br", (0.42, 0.25, 0.12, 1.0), 0.0, 0.75)
M_SHIRT_WHITE_I = mat("sh_w", (0.92, 0.88, 0.78, 1.0), 0.0, 0.75)
SHIRT_VARIANTS_I = [M_SHIRT_CHECK_GREEN, M_SHIRT_CHECK_RED, M_SHIRT_CHECK_BLUE,
                    M_SHIRT_BROWN, M_SHIRT_WHITE_I]

M_PANTS_JEANS = mat("jeans", (0.18, 0.30, 0.55, 1.0), 0.0, 0.80)
M_PANTS_BROWN_I = mat("pants_b", (0.30, 0.18, 0.10, 1.0), 0.0, 0.85)

# Apron (barman)
M_APRON = mat("apron", (0.65, 0.42, 0.22, 1.0), 0.0, 0.75, emission=(0.60,0.40,0.22), emission_strength=0.4)
M_APRON_TIE = mat("apron_t", (0.30, 0.18, 0.10, 1.0), 0.0, 0.80)

# Fireplace
M_BRICK_RED = mat("brick", (0.65, 0.28, 0.18, 1.0), 0.0, 0.85, emission=(0.60,0.28,0.18), emission_strength=0.4)
M_BRICK_DARK = mat("brick_d", (0.42, 0.18, 0.10, 1.0), 0.0, 0.85)
M_FIRE_OUTER_I = mat("fire_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=18.0)
M_FIRE_CORE_I = mat("fire_c", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=22.0)
M_LOG = mat("log", (0.30, 0.18, 0.08, 1.0), 0.0, 0.85)
M_EMBER = mat("ember", (1.0, 0.30, 0.10, 1.0), 0.0, 0.20, emission=(1.0,0.30,0.10), emission_strength=10.0)

# Eye
M_EYE_DARK_I = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_GREEN_I = mat("eye_g", (0.20, 0.65, 0.30, 1.0), 0.0, 0.20, emission=(0.20,0.65,0.30), emission_strength=1.5)
M_EYE_BLUE_I = mat("eye_b", (0.20, 0.55, 0.85, 1.0), 0.0, 0.20, emission=(0.20,0.55,0.85), emission_strength=1.2)
EYE_COLORS_I = [M_EYE_GREEN_I, M_EYE_BLUE_I, M_EYE_DARK_I]
M_LIPS_RED_I = mat("lips", (0.85, 0.20, 0.30, 1.0), 0.0, 0.40, emission=(0.80,0.20,0.30), emission_strength=0.5)

# Fiddle (violin)
M_FIDDLE_WOOD = mat("fid_w", (0.55, 0.20, 0.10, 1.0), 0.0, 0.45, emission=(0.50,0.20,0.10), emission_strength=0.5)
M_FIDDLE_DARK = mat("fid_d", (0.18, 0.08, 0.04, 1.0), 0.0, 0.60)
M_STRING = mat("string", (0.85, 0.85, 0.85, 1.0), 0.5, 0.30)
M_BOW_WHITE = mat("bow_w", (0.92, 0.88, 0.78, 1.0), 0.0, 0.65)

# Tin whistle
M_WHISTLE = mat("whistle", (0.85, 0.85, 0.85, 1.0), 0.9, 0.20, emission=(0.80,0.80,0.80), emission_strength=1.0)
M_WHISTLE_DARK = mat("whistle_d", (0.55, 0.55, 0.55, 1.0), 0.8, 0.30)

# Bodhran (Irish drum signature)
M_BODHRAN_RIM = mat("bd_r", (0.32, 0.18, 0.08, 1.0), 0.0, 0.80, emission=(0.30,0.18,0.08), emission_strength=0.4)
M_BODHRAN_SKIN = mat("bd_s", (0.92, 0.78, 0.55, 1.0), 0.0, 0.55, emission=(0.85,0.72,0.52), emission_strength=0.6)
M_BODHRAN_DECOR = mat("bd_d", (0.78, 0.30, 0.18, 1.0), 0.0, 0.55, emission=(0.72,0.30,0.18), emission_strength=0.5)
M_TIPPER = mat("tipper", (0.42, 0.25, 0.12, 1.0), 0.0, 0.75)

# Guitar acoustic
M_GUITAR_WOOD = mat("gt_w", (0.55, 0.32, 0.18, 1.0), 0.0, 0.45, emission=(0.50,0.30,0.18), emission_strength=0.4)
M_GUITAR_HOLE = mat("gt_h", (0.10, 0.08, 0.06, 1.0), 0.0, 0.30)

# Irish flag
M_FLAG_GREEN = mat("fl_g", (0.18, 0.62, 0.32, 1.0), 0.0, 0.55, emission=(0.18,0.60,0.32), emission_strength=1.0)
M_FLAG_WHITE = mat("fl_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.92,0.90,0.88), emission_strength=0.8)
M_FLAG_ORANGE = mat("fl_o", (0.95, 0.55, 0.15, 1.0), 0.0, 0.55, emission=(0.92,0.55,0.15), emission_strength=1.0)

# Shamrock (clover signature)
M_SHAMROCK = mat("sham", (0.20, 0.78, 0.30, 1.0), 0.0, 0.55, emission=(0.18,0.75,0.30), emission_strength=1.5)

# Leprechaun signature
M_LEP_GREEN = mat("lep_g", (0.18, 0.65, 0.25, 1.0), 0.0, 0.55, emission=(0.18,0.62,0.25), emission_strength=0.8)
M_LEP_GREEN_DARK = mat("lep_gd", (0.10, 0.45, 0.18, 1.0), 0.0, 0.75)
M_LEP_HAT = mat("lep_h", (0.10, 0.40, 0.15, 1.0), 0.0, 0.65, emission=(0.10,0.38,0.15), emission_strength=0.6)
M_LEP_BELT_GOLD = mat("lep_b", (1.0, 0.85, 0.20, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.20), emission_strength=2.5)
M_LEP_SHOES = mat("lep_s", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)
M_LEP_BEARD_RED = mat("lep_bd", (0.85, 0.32, 0.12, 1.0), 0.0, 0.65)

# Pot of gold
M_POT_BLACK = mat("pot", (0.18, 0.15, 0.12, 1.0), 0.7, 0.40)
M_GOLD_COIN = mat("gold", (1.0, 0.85, 0.25, 1.0), 0.95, 0.10, emission=(0.95,0.80,0.25), emission_strength=4.0)

# Rainbow (signature)
M_RB_R = mat("rb_r", (1.0, 0.30, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.30,0.20), emission_strength=4.0, alpha=0.75)
M_RB_O = mat("rb_o", (1.0, 0.55, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.20), emission_strength=4.0, alpha=0.75)
M_RB_Y = mat("rb_y", (1.0, 0.95, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.95,0.30), emission_strength=4.0, alpha=0.75)
M_RB_G = mat("rb_g", (0.30, 0.95, 0.30, 1.0), 0.0, 0.20, emission=(0.30,0.95,0.30), emission_strength=4.0, alpha=0.75)
M_RB_B = mat("rb_b", (0.20, 0.45, 1.0, 1.0), 0.0, 0.20, emission=(0.20,0.45,1.0), emission_strength=4.0, alpha=0.75)
M_RB_V = mat("rb_v", (0.65, 0.25, 1.0, 1.0), 0.0, 0.20, emission=(0.65,0.25,1.0), emission_strength=4.0, alpha=0.75)
RB_COLS = [M_RB_R, M_RB_O, M_RB_Y, M_RB_G, M_RB_B, M_RB_V]

# Chalkboard sign
M_CHALK_BLACK = mat("ch_bk", (0.10, 0.10, 0.10, 1.0), 0.0, 0.70)
M_CHALK_WHITE = mat("ch_w", (0.92, 0.88, 0.82, 1.0), 0.0, 0.45, emission=(0.85,0.82,0.78), emission_strength=0.8)

# Wall lamp
M_LAMP_BRASS = mat("lamp", (0.92, 0.65, 0.20, 1.0), 0.9, 0.25, emission=(0.88,0.62,0.20), emission_strength=1.5)
M_LAMP_GLOW = mat("glow", (1.0, 0.85, 0.45, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.45), emission_strength=8.0, alpha=0.85)

# Stout bubbles
M_BUBBLE = mat("bubble", (0.92, 0.85, 0.72, 1.0), 0.0, 0.20, emission=(0.88,0.82,0.70), emission_strength=2.5, alpha=0.55)

# Music notes
M_NOTE_GOLD = mat("note_g", (1.0, 0.85, 0.30, 1.0), 0.0, 0.20, emission=(0.95,0.80,0.30), emission_strength=4.0)
M_NOTE_GREEN = mat("note_gr", (0.30, 0.85, 0.40, 1.0), 0.0, 0.20, emission=(0.30,0.80,0.40), emission_strength=3.5)

# ============ PUB INTERIOR (signature dark cozy) ============
# Ceiling (low ceiling pub feel)
beveled_cube("ceiling", (40, 30, 0.3), bevel_offset=0.06, loc=(0, 0, 9.85), mat_=M_CEILING)
# Wooden beams on ceiling
for bi in range(5):
    beveled_cube(f"beam{bi}", (40, 0.5, 0.4), bevel_offset=0.06,
                 loc=(0, -10 + bi*5, 9.5), mat_=M_FLOOR_WOOD_DARK)

# Walls
# Back wall (signature green)
beveled_cube("wall_b", (40, 0.3, 10), bevel_offset=0.06, loc=(0, 15, 5), mat_=M_WALL_GREEN)
# Lower wood paneling
beveled_cube("wall_b_p", (40, 0.35, 3), bevel_offset=0.06, loc=(0, 14.9, 1.5), mat_=M_WALL_WOOD)
# Side walls
beveled_cube("wall_l", (0.3, 30, 10), bevel_offset=0.06, loc=(-20, 0, 5), mat_=M_WALL_GREEN)
beveled_cube("wall_l_p", (0.35, 30, 3), bevel_offset=0.06, loc=(-19.9, 0, 1.5), mat_=M_WALL_WOOD)
beveled_cube("wall_r", (0.3, 30, 10), bevel_offset=0.06, loc=(20, 0, 5), mat_=M_WALL_GREEN)
beveled_cube("wall_r_p", (0.35, 30, 3), bevel_offset=0.06, loc=(19.9, 0, 1.5), mat_=M_WALL_WOOD)

# ============ ONE clean wood plank floor ground ============
ground = beveled_cube("ground", (60, 60, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_FLOOR_WOOD)
# Pub floor (signature plank pattern)
floor = beveled_cube("floor", (40, 30, 0.35), bevel_offset=0.06, loc=(0, 0, 0.10), mat_=M_FLOOR_WOOD)
# Plank lines
for pi in range(13):
    plank_y = -14 + pi * 2.4
    beveled_cube(f"plk{pi}", (40, 0.10, 0.06), bevel_offset=0.01,
                 loc=(0, plank_y, 0.28), mat_=M_FLOOR_WOOD_DARK)
# Spilled stout circles (signature pub atmosphere)
for si in range(10):
    sx = random.uniform(-15, 15); sy = random.uniform(-10, 10)
    cyl(f"spill{si}", r=random.uniform(0.20, 0.40), depth=0.04, segs=14,
        loc=(sx, sy, 0.30), mat_=M_STOUT)

# ============ LONG BAR (signature centerpiece) ============
bar_e = empty("bar", loc=(0, 10, 0))
# Bar counter base
beveled_cube("bar_b", (20, 2, 1.2), bevel_offset=0.10, loc=(0, 0, 0.6),
             parent=bar_e, mat_=M_BAR_WOOD)
# Plank lines on front
for pi in range(8):
    plank_x = -9 + pi * 2.5
    beveled_cube(f"bp{pi}", (0.10, 2.05, 1.2), bevel_offset=0.01,
                 loc=(plank_x, 0, 0.6), parent=bar_e, mat_=M_FLOOR_WOOD_DARK)
# Polished bar top (signature)
beveled_cube("bar_top", (20.5, 2.2, 0.12), bevel_offset=0.06, loc=(0, 0, 1.25),
             parent=bar_e, mat_=M_BAR_TOP)
# BRASS FOOT RAIL signature
cyl("rail_f", r=0.06, depth=20, segs=12, loc=(0, -1.0, 0.20),
    parent=bar_e, mat_=M_BAR_BRASS_RAIL).rotation_euler = (0, math.radians(90), 0)
# Brass railing along top
for ri in range(8):
    rx = -8.75 + ri * 2.5
    cyl(f"rail_t{ri}", r=0.04, depth=0.40, segs=10, loc=(rx, 1.0, 1.50),
        parent=bar_e, mat_=M_BAR_BRASS_RAIL)
beveled_cube("rail_top_bar", (20, 0.10, 0.05), bevel_offset=0.01, loc=(0, 1.0, 1.7),
             parent=bar_e, mat_=M_BAR_BRASS_RAIL)

# Beer taps (signature 5 pumps)
for ti in range(5):
    tx = -4 + ti * 2.0
    # Base
    cyl(f"tap_b{ti}", r=0.10, depth=0.30, segs=12, loc=(tx, 0.8, 1.45),
        parent=bar_e, mat_=M_BRASS)
    # Pump handle (signature classic)
    cyl(f"tap_h{ti}", r=0.05, depth=0.5, segs=10, loc=(tx, 0.8, 1.85),
        parent=bar_e, mat_=M_BAR_BRASS_RAIL)
    # Handle top
    beveled_cube(f"tap_t{ti}", (0.30, 0.15, 0.30), bevel_offset=0.04,
                 loc=(tx, 0.8, 2.20), parent=bar_e, mat_=M_LEP_GREEN_DARK)

# Bottles on shelves behind bar (signature)
for si in range(2):
    sy_s = 13.5 + si * 0.5
    sz_s = 2.5 + si * 1.0
    beveled_cube(f"shelf{si}", (16, 0.30, 0.10), bevel_offset=0.03,
                 loc=(0, sy_s, sz_s), mat_=M_BAR_WOOD)
    # Bottles on shelf
    for bi in range(20):
        bx_b = -7.5 + bi * 0.8
        # Bottle body
        bottle_col = M_FIDDLE_WOOD if bi % 3 == 0 else M_WHISKEY if bi % 3 == 1 else M_FIDDLE_DARK
        cyl(f"bot{si}_{bi}", r=0.10, depth=0.5, segs=12, loc=(bx_b, sy_s, sz_s + 0.30),
            mat_=bottle_col)
        # Bottle neck
        cyl(f"bot_n{si}_{bi}", r=0.03, depth=0.18, segs=10, loc=(bx_b, sy_s, sz_s + 0.65),
            mat_=bottle_col)
        # Cap
        cyl(f"bot_c{si}_{bi}", r=0.04, depth=0.04, segs=10, loc=(bx_b, sy_s, sz_s + 0.76),
            mat_=M_BRASS)

# Mirror behind bar (signature)
beveled_cube("mirror", (10, 0.06, 2), bevel_offset=0.06, loc=(0, 14.6, 5.0),
             mat_=M_PINT_GLASS)
beveled_cube("mirror_fr", (10.2, 0.10, 2.1), bevel_offset=0.06, loc=(0, 14.7, 5.0),
             mat_=M_BRASS)

# ============ BAR STOOLS ============
for si in range(6):
    sx_st = -8 + si * 3.5
    if sx_st >= -1 and sx_st <= 1: continue
    st_e = empty(f"stool{si}", (sx_st, 7.5, 0))
    # Wood seat
    cyl(f"st_s{si}", r=0.30, depth=0.10, segs=14, loc=(0, 0, 1.0),
        parent=st_e, mat_=M_BAR_WOOD)
    # 3 legs
    for li in range(3):
        la = (li / 3.0) * math.pi * 2
        cyl(f"st_l{si}_{li}", r=0.04, depth=1.0, segs=8,
            loc=(math.cos(la)*0.22, math.sin(la)*0.22, 0.50),
            parent=st_e, mat_=M_BAR_WOOD).rotation_euler = (0, math.radians(la*5), 0)
    # Brass rail between legs
    for ri in range(3):
        ra = (ri / 3.0) * math.pi * 2 + math.pi/3
        cyl(f"st_r{si}_{ri}", r=0.02, depth=0.40, segs=8,
            loc=(math.cos(ra)*0.22, math.sin(ra)*0.22, 0.30),
            parent=st_e, mat_=M_BRASS)

# ============ TABLES with patrons ============
table_positions = [(-12, -5, 0), (-12, -10, 0), (12, -5, 0), (12, -10, 0)]
tables = []
for ti, (tx, ty, tz) in enumerate(table_positions):
    t_e = empty(f"table{ti}", (tx, ty, tz))
    # Round table top
    cyl(f"t_top{ti}", r=1.2, depth=0.10, segs=18, loc=(0, 0, 1.0),
        parent=t_e, mat_=M_BAR_WOOD)
    # Pedestal
    cyl(f"t_ped{ti}", r=0.15, depth=1.0, segs=14, loc=(0, 0, 0.5),
        parent=t_e, mat_=M_BAR_WOOD)
    # Base
    cyl(f"t_base{ti}", r=0.50, depth=0.10, segs=18, loc=(0, 0, 0.05),
        parent=t_e, mat_=M_FLOOR_WOOD_DARK)
    # Pints of Guinness on table (signature)
    for pi in range(2):
        pa = pi * math.pi
        pint_x = math.cos(pa) * 0.5
        pint_y = math.sin(pa) * 0.5
        # Glass
        cyl(f"pint_g{ti}_{pi}", r=0.10, depth=0.45, segs=14,
            loc=(pint_x, pint_y, 1.30), parent=t_e, mat_=M_PINT_GLASS)
        # Stout liquid
        cyl(f"pint_st{ti}_{pi}", r=0.09, depth=0.38, segs=14,
            loc=(pint_x, pint_y, 1.28), parent=t_e, mat_=M_STOUT)
        # Foam head (signature creamy)
        cyl(f"pint_foam{ti}_{pi}", r=0.09, depth=0.08, segs=14,
            loc=(pint_x, pint_y, 1.51), parent=t_e, mat_=M_STOUT_FOAM)
    tables.append(t_e)

# ============ FIREPLACE (signature) ============
fp_e = empty("fireplace", loc=(-18, 0, 0))
# Stone surround
beveled_cube("fp_base", (3, 2, 0.8), bevel_offset=0.10, loc=(0, 0, 0.4),
             parent=fp_e, mat_=M_BRICK_DARK)
# Brick walls
beveled_cube("fp_wall_l", (0.5, 2, 3.5), bevel_offset=0.06, loc=(-1.5, 0, 2.2),
             parent=fp_e, mat_=M_BRICK_RED)
beveled_cube("fp_wall_r", (0.5, 2, 3.5), bevel_offset=0.06, loc=(1.5, 0, 2.2),
             parent=fp_e, mat_=M_BRICK_RED)
beveled_cube("fp_wall_b", (3, 0.4, 3.5), bevel_offset=0.06, loc=(0, 0.9, 2.2),
             parent=fp_e, mat_=M_BRICK_DARK)
# Mantle
beveled_cube("fp_mantle", (3.5, 2.2, 0.30), bevel_offset=0.06, loc=(0, 0, 4.0),
             parent=fp_e, mat_=M_BAR_WOOD)
# Logs burning
for li in range(3):
    la = (li / 3.0) * math.pi
    cyl(f"fp_log{li}", r=0.08, depth=1.5, segs=10, loc=(0, 0, 0.85),
        parent=fp_e, mat_=M_LOG).rotation_euler = (0, math.radians(90), la*math.pi/2)
# Flames
flame_fp = empty("fp_flame", (0, 0, 1.0), parent=fp_e)
smooth_cone("fp_fo", r1=0.40, r2=0.05, depth=1.5, segs=14, loc=(0, 0, 0.75),
            parent=flame_fp, mat_=M_FIRE_OUTER_I)
smooth_cone("fp_fc", r1=0.25, r2=0.02, depth=1.2, segs=14, loc=(0, 0, 0.6),
            parent=flame_fp, mat_=M_FIRE_CORE_I)
# Embers
embers_fp = []
for ei in range(10):
    e = smooth_sphere(f"emb{ei}", r=0.04, segs=8, rings=6,
                      loc=(random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5),
                            random.uniform(0.5, 1.5)),
                      parent=fp_e, mat_=M_EMBER)
    e["_phase"] = random.uniform(0, math.pi*2)
    embers_fp.append(e)
# Items on mantle (signature)
# Photo frames
for pi in range(3):
    px = -1 + pi * 1.0
    beveled_cube(f"frame{pi}", (0.35, 0.10, 0.50), bevel_offset=0.04,
                 loc=(px, -0.7, 4.5), parent=fp_e, mat_=M_BAR_WOOD)
    beveled_cube(f"photo{pi}", (0.25, 0.02, 0.40), bevel_offset=0.02,
                 loc=(px, -0.74, 4.5), parent=fp_e, mat_=M_FLOOR_WOOD)

# ============ 6 IRISH STEP DANCERS (signature) ============
def make_step_dancer(name, loc, scale=1.0, facing=0, is_female=True):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    dance_col = random.choice(DANCE_VARIANTS)
    skin = random.choice(SKIN_VARIANTS_I)
    hair_col = random.choice([M_HAIR_RED_IR, M_HAIR_GINGER_IR])

    if is_female:
        # SHORT EMBROIDERED DRESS (signature step dance)
        smooth_cone(f"{name}_dress", r1=0.45*scale, r2=0.32*scale, depth=0.65*scale, segs=18,
                    loc=(0, 0, 1.05*scale), parent=base, mat_=dance_col)
        # Gold embroidery border
        cyl(f"{name}_emb_b", r=0.46*scale, depth=0.04*scale, segs=18, loc=(0, 0, 0.72*scale),
            parent=base, mat_=M_DANCE_GOLD_TRIM)
        # Vertical embroidery patterns (signature Celtic knots)
        for ei in range(6):
            ea = (ei / 6.0) * math.pi * 2
            beveled_cube(f"{name}_emb{ei}", (0.04*scale, 0.04*scale, 0.50*scale), bevel_offset=0.005,
                         loc=(math.cos(ea)*0.42*scale, math.sin(ea)*0.42*scale, 1.05*scale),
                         parent=base, mat_=M_DANCE_GOLD_TRIM)
            # Celtic knot decoration
            smooth_sphere(f"{name}_knot{ei}", r=0.06*scale,
                          loc=(math.cos(ea)*0.42*scale, math.sin(ea)*0.42*scale, 0.95*scale),
                          parent=base, mat_=M_DANCE_GOLD_TRIM)
        # Bodice tight
        smooth_cone(f"{name}_bodice", r1=0.28*scale, r2=0.30*scale, depth=0.55*scale, segs=14,
                    loc=(0, 0, 1.55*scale), parent=base, mat_=dance_col)
        # Long flowing hair (signature curly red)
        for hi in range(15):
            ha = random.uniform(0, math.pi*2)
            hl_d = random.uniform(0.20, 0.40)
            beveled_cube(f"{name}_hr{hi}", (0.05*scale, 0.07*scale, hl_d*scale), bevel_offset=0.01,
                         loc=(math.cos(ha)*0.16*scale, math.sin(ha)*0.10*scale - 0.08*scale,
                              1.95*scale - hl_d*scale/2),
                         parent=base, mat_=hair_col)
    else:
        # Male: vest + pants
        smooth_cone(f"{name}_vest", r1=0.30*scale, r2=0.32*scale, depth=0.60*scale, segs=14,
                    loc=(0, 0, 1.30*scale), parent=base, mat_=dance_col)
        # White shirt below collar
        smooth_cone(f"{name}_shirt", r1=0.26*scale, r2=0.28*scale, depth=0.30*scale, segs=14,
                    loc=(0, 0, 1.55*scale), parent=base, mat_=M_FLAG_WHITE)
        # Tie
        beveled_cube(f"{name}_tie", (0.06*scale, 0.04*scale, 0.30*scale), bevel_offset=0.01,
                     loc=(0, -0.30*scale, 1.50*scale), parent=base, mat_=M_DANCE_GOLD_TRIM)
        # Hair short
        for hi in range(6):
            ha = (hi / 6.0) * math.pi * 2
            smooth_sphere(f"{name}_hr{hi}", r=0.05*scale,
                          loc=(math.cos(ha)*0.13*scale, math.sin(ha)*0.10*scale, 1.95*scale),
                          parent=base, mat_=hair_col)

    # Pants (visible under skirt for female)
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.08*scale, depth=1.0*scale, segs=10,
            loc=(side*0.12*scale, 0, 0.5*scale), parent=base, mat_=skin)
    # BLACK DANCE SHOES with brass buckle (signature)
    for side in (-1, 1):
        # Shoe
        beveled_cube(f"{name}_sh{side}", (0.10*scale, 0.22*scale, 0.08*scale), bevel_offset=0.02,
                     loc=(side*0.12*scale, 0.04*scale, 0), parent=base, mat_=M_DANCE_SHOE)
        # Brass buckle
        beveled_cube(f"{name}_bk{side}", (0.06*scale, 0.04*scale, 0.05*scale), bevel_offset=0.01,
                     loc=(side*0.12*scale, -0.02*scale, 0.06*scale), parent=base, mat_=M_DANCE_BUCKLE)
    # Arms straight down at sides (signature Irish dance)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh_arm{side_idx}", (side*0.30*scale, 0, 1.80*scale), parent=base)
        sh.rotation_euler = (math.radians(-10), 0, math.radians(side*-5))
        cyl(f"{name}_uarm{side_idx}", r=0.06*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=dance_col if is_female else M_FLAG_WHITE)
        cyl(f"{name}_fa{side_idx}", r=0.05*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=skin)
    # Head
    head_d_e = empty(f"{name}_he", (0, 0, 2.10*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_d_e, mat_=skin, scale=(1, 1.0, 1.1))
    # Big smile
    beveled_cube(f"{name}_smile", (0.08*scale, 0.04*scale, 0.02*scale), bevel_offset=0.005,
                 loc=(0, -0.18*scale, -0.06*scale), parent=head_d_e, mat_=M_LIPS_RED_I)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.04*scale), parent=head_d_e, mat_=random.choice(EYE_COLORS_I))
    # Freckles (signature Irish)
    for fi in range(6):
        fa = (fi / 6.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_fr{fi}", r=0.012*scale,
                      loc=(math.sin(fa)*0.10*scale, -0.16*scale, 0),
                      parent=head_d_e, mat_=M_HAIR_GINGER_IR)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_d_e}

dancers = []
dancer_pos = [(-4, 0, math.radians(0)), (-2, 0, math.radians(0)),
              (0, 0, math.radians(0)), (2, 0, math.radians(0)),
              (4, 0, math.radians(0)), (-4, -3, math.radians(0))]
for i, (dx, dy, fac) in enumerate(dancer_pos):
    d = make_step_dancer(f"dancer{i}", (dx, dy, 0), scale=1.0, facing=fac, is_female=(i % 2 == 0))
    dancers.append(d)

# ============ 4 MUSICIANS sitting playing (signature) ============
# Sitting on stools
def make_musician(name, loc, instrument, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    shirt_col = random.choice(SHIRT_VARIANTS_I)
    pants_col = random.choice([M_PANTS_JEANS, M_PANTS_BROWN_I])
    hair_col = random.choice([M_HAIR_RED_IR, M_HAIR_GINGER_IR, M_HAIR_BROWN_IR])
    # Sitting torso
    smooth_cone(f"{name}_torso", r1=0.30*scale, r2=0.32*scale, depth=0.55*scale, segs=14,
                loc=(0, 0, 1.35*scale), parent=base, mat_=shirt_col)
    # Thighs horizontal (sitting)
    for side in (-1, 1):
        thigh_e = empty(f"{name}_th{side}_e", (side*0.12*scale, 0.20*scale, 0.95*scale), parent=base)
        thigh_e.rotation_euler = (math.radians(-90), 0, 0)
        cyl(f"{name}_th{side}", r=0.10*scale, depth=0.55*scale, segs=10,
            loc=(0, 0, 0.27*scale), parent=thigh_e, mat_=pants_col)
        # Knees + lower legs hanging
        cyl(f"{name}_sh_leg{side}", r=0.08*scale, depth=0.70*scale, segs=10,
            loc=(side*0.12*scale, 0.50*scale, 0.55*scale), parent=base, mat_=pants_col)
        beveled_cube(f"{name}_bt{side}", (0.10*scale, 0.22*scale, 0.10*scale), bevel_offset=0.02,
                     loc=(side*0.12*scale, 0.50*scale, 0.15*scale), parent=base, mat_=M_LEP_SHOES)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 1.85*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN_FRECKLE)
    # Beard for some
    if random.random() > 0.5:
        for bi in range(8):
            ba = (bi / 8.0) * math.pi - math.pi/2
            smooth_sphere(f"{name}_bd{bi}", r=0.04*scale,
                          loc=(math.sin(ba)*0.12*scale, -0.15*scale, -0.10*scale),
                          parent=head_m_e, mat_=hair_col)
    # Hair
    for hi in range(8):
        ha = (hi / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.05*scale,
                      loc=(math.cos(ha)*0.15*scale, math.sin(ha)*0.10*scale, 0.10*scale),
                      parent=head_m_e, mat_=hair_col)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.03*scale), parent=head_m_e, mat_=M_EYE_DARK_I)

    # INSTRUMENTS signature
    inst_e = empty(f"{name}_inst", (0, -0.35*scale, 1.50*scale), parent=base)
    if instrument == "fiddle":
        # Fiddle body
        smooth_sphere(f"{name}_fid_b", r=0.18*scale, segs=18, rings=12, loc=(0, 0, 0),
                      parent=inst_e, mat_=M_FIDDLE_WOOD, scale=(0.8, 0.30, 1.2))
        # F-holes
        for side in (-1, 1):
            cyl(f"{name}_fh{side}", r=0.015*scale, depth=0.02*scale, segs=8,
                loc=(side*0.05*scale, -0.16*scale, 0), parent=inst_e, mat_=M_FIDDLE_DARK)
        # Neck
        cyl(f"{name}_fid_n", r=0.025*scale, depth=0.40*scale, segs=10,
            loc=(0, -0.10*scale, 0.30*scale), parent=inst_e, mat_=M_FIDDLE_DARK)
        # Strings
        for st in range(4):
            cyl(f"{name}_str{st}", r=0.003*scale, depth=0.50*scale, segs=6,
                loc=((st - 1.5)*0.015*scale, -0.12*scale, 0.15*scale),
                parent=inst_e, mat_=M_STRING)
        # Bow
        bow_e = empty(f"{name}_bow_e", (0.30*scale, -0.10*scale, 0), parent=base)
        bow_e.rotation_euler = (0, math.radians(20), math.radians(-90))
        cyl(f"{name}_bow_s", r=0.012*scale, depth=0.60*scale, segs=8,
            loc=(0, 0, 0), parent=bow_e, mat_=M_FIDDLE_DARK)
        # Bow hair
        beveled_cube(f"{name}_bow_h", (0.020*scale, 0.04*scale, 0.55*scale), bevel_offset=0.005,
                     loc=(0, -0.03*scale, 0), parent=bow_e, mat_=M_BOW_WHITE)
    elif instrument == "tin_whistle":
        # Tin whistle vertical (signature small flute)
        cyl(f"{name}_tw_b", r=0.018*scale, depth=0.40*scale, segs=10,
            loc=(0, -0.10*scale, 0.20*scale), parent=inst_e, mat_=M_WHISTLE)
        # Mouthpiece end
        cyl(f"{name}_tw_m", r=0.025*scale, depth=0.05*scale, segs=10,
            loc=(0, -0.10*scale, 0.45*scale), parent=inst_e, mat_=M_WHISTLE_DARK)
        # Finger holes
        for hi in range(6):
            cyl(f"{name}_tw_h{hi}", r=0.008*scale, depth=0.005*scale, segs=6,
                loc=(0.018*scale, -0.10*scale, 0.05*scale + hi*0.05*scale),
                parent=inst_e, mat_=M_WHISTLE_DARK)
    elif instrument == "bodhran":
        # BODHRAN drum signature (Irish frame drum)
        # Frame
        cyl(f"{name}_bod_r", r=0.40*scale, depth=0.20*scale, segs=22, loc=(0, 0, 0),
            parent=inst_e, mat_=M_BODHRAN_RIM).rotation_euler = (math.radians(90), 0, 0)
        # Skin head (signature painted)
        cyl(f"{name}_bod_s", r=0.40*scale, depth=0.04*scale, segs=22, loc=(0, -0.12*scale, 0),
            parent=inst_e, mat_=M_BODHRAN_SKIN).rotation_euler = (math.radians(90), 0, 0)
        # Celtic knot decoration painted (signature)
        for ki in range(4):
            ka = (ki / 4.0) * math.pi * 2
            cyl(f"{name}_bod_k{ki}", r=0.06*scale, depth=0.02*scale, segs=14,
                loc=(math.cos(ka)*0.20*scale, -0.13*scale, math.sin(ka)*0.20*scale),
                parent=inst_e, mat_=M_BODHRAN_DECOR).rotation_euler = (math.radians(90), 0, 0)
        # Crossbar inside (handle)
        cyl(f"{name}_bod_h", r=0.02*scale, depth=0.70*scale, segs=8,
            loc=(0, 0.05*scale, 0), parent=inst_e, mat_=M_FIDDLE_DARK).rotation_euler = (0, math.radians(90), 0)
        # Tipper (signature beater)
        tipper_e = empty(f"{name}_tip", (0.30*scale, 0.10*scale, 0), parent=base)
        tipper_e.rotation_euler = (0, math.radians(-30), 0)
        cyl(f"{name}_tip_s", r=0.012*scale, depth=0.30*scale, segs=8, loc=(0, 0, 0),
            parent=tipper_e, mat_=M_TIPPER)
        # Tipper ends
        smooth_sphere(f"{name}_tip_e1", r=0.025*scale, loc=(0, 0, 0.18*scale),
                      parent=tipper_e, mat_=M_TIPPER)
        smooth_sphere(f"{name}_tip_e2", r=0.025*scale, loc=(0, 0, -0.18*scale),
                      parent=tipper_e, mat_=M_TIPPER)
    elif instrument == "guitar":
        # Guitar body
        smooth_sphere(f"{name}_gt_b", r=0.30*scale, segs=20, rings=14, loc=(0, 0, 0),
                      parent=inst_e, mat_=M_GUITAR_WOOD, scale=(0.9, 0.30, 1.2))
        # Soundhole
        cyl(f"{name}_gt_h", r=0.06*scale, depth=0.02*scale, segs=14,
            loc=(0, -0.16*scale, 0.05*scale), parent=inst_e, mat_=M_GUITAR_HOLE)
        # Neck
        cyl(f"{name}_gt_n", r=0.025*scale, depth=0.50*scale, segs=10,
            loc=(0, -0.10*scale, 0.40*scale), parent=inst_e, mat_=M_FIDDLE_DARK)
        # Headstock
        beveled_cube(f"{name}_gt_hs", (0.10*scale, 0.08*scale, 0.10*scale), bevel_offset=0.01,
                     loc=(0, -0.10*scale, 0.70*scale), parent=inst_e, mat_=M_FIDDLE_DARK)
        # Strings
        for st in range(6):
            cyl(f"{name}_str{st}", r=0.003*scale, depth=0.85*scale, segs=6,
                loc=((st - 2.5)*0.012*scale, -0.13*scale, 0.20*scale),
                parent=inst_e, mat_=M_STRING)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "inst": inst_e, "he": head_m_e}

# Place stools for musicians
musicians = []
musician_data = [("fiddle", (-8, 5)), ("tin_whistle", (-5, 5)),
                  ("bodhran", (5, 5)), ("guitar", (8, 5))]
for i, (inst, (mx, my)) in enumerate(musician_data):
    # Stool for musician
    stool_m_e = empty(f"st_m{i}", (mx, my, 0))
    cyl(f"st_m{i}_s", r=0.25, depth=0.10, segs=14, loc=(0, 0, 0.85),
        parent=stool_m_e, mat_=M_BAR_WOOD)
    for li in range(3):
        la = (li / 3.0) * math.pi * 2
        cyl(f"st_m{i}_l{li}", r=0.03, depth=0.85, segs=8,
            loc=(math.cos(la)*0.20, math.sin(la)*0.20, 0.42),
            parent=stool_m_e, mat_=M_BAR_WOOD)
    # Musician
    m = make_musician(f"musician{i}", (mx, my, 0.95), instrument=inst, scale=1.0,
                      facing=math.radians(180))
    musicians.append(m)

# ============ 8 PATRONS sitting at tables drinking ============
def make_patron(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    shirt_col = random.choice(SHIRT_VARIANTS_I)
    hair_col = random.choice(HAIR_VARIANTS_I)
    skin = random.choice(SKIN_VARIANTS_I)
    # Sitting body
    smooth_cone(f"{name}_torso", r1=0.32*scale, r2=0.34*scale, depth=0.55*scale, segs=14,
                loc=(0, 0, 1.35*scale), parent=base, mat_=shirt_col)
    # Lap thighs
    for side in (-1, 1):
        thigh_e = empty(f"{name}_th{side}_e", (side*0.13*scale, 0.20*scale, 0.95*scale), parent=base)
        thigh_e.rotation_euler = (math.radians(-90), 0, 0)
        cyl(f"{name}_th{side}", r=0.10*scale, depth=0.55*scale, segs=10,
            loc=(0, 0, 0.27*scale), parent=thigh_e, mat_=M_PANTS_JEANS)
    # Arms (one raised cheering with pint, one resting)
    sh_r = empty(f"{name}_sh_r", (0.30*scale, -0.10*scale, 1.60*scale), parent=base)
    sh_r.rotation_euler = (math.radians(-120), 0, math.radians(-30))
    cyl(f"{name}_uarm_R", r=0.06*scale, depth=0.40*scale, segs=10, loc=(0, 0, -0.20*scale),
        parent=sh_r, mat_=shirt_col)
    cyl(f"{name}_fa_R", r=0.05*scale, depth=0.35*scale, segs=10, loc=(0, 0, -0.55*scale),
        parent=sh_r, mat_=skin)
    # PINT raised (signature)
    pint_r_e = empty(f"{name}_pint", (0, 0, -0.85*scale), parent=sh_r)
    cyl(f"{name}_pn_g", r=0.10*scale, depth=0.45*scale, segs=14, loc=(0, 0, 0),
        parent=pint_r_e, mat_=M_PINT_GLASS)
    cyl(f"{name}_pn_s", r=0.09*scale, depth=0.40*scale, segs=14, loc=(0, 0, 0.02*scale),
        parent=pint_r_e, mat_=M_STOUT)
    cyl(f"{name}_pn_f", r=0.09*scale, depth=0.08*scale, segs=14, loc=(0, 0, 0.20*scale),
        parent=pint_r_e, mat_=M_STOUT_FOAM)
    # Left arm resting
    sh_l = empty(f"{name}_sh_l", (-0.30*scale, 0, 1.55*scale), parent=base)
    sh_l.rotation_euler = (math.radians(-45), 0, math.radians(20))
    cyl(f"{name}_uarm_L", r=0.06*scale, depth=0.40*scale, segs=10, loc=(0, 0, -0.20*scale),
        parent=sh_l, mat_=shirt_col)
    cyl(f"{name}_fa_L", r=0.05*scale, depth=0.35*scale, segs=10, loc=(0, 0, -0.55*scale),
        parent=sh_l, mat_=skin)
    # Head
    head_p_e = empty(f"{name}_he", (0, 0, 1.90*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_p_e, mat_=skin)
    # Beard (sometimes)
    if random.random() > 0.4:
        for bi in range(8):
            ba = (bi / 8.0) * math.pi - math.pi/2
            smooth_sphere(f"{name}_bd{bi}", r=0.04*scale,
                          loc=(math.sin(ba)*0.12*scale, -0.15*scale, -0.10*scale),
                          parent=head_p_e, mat_=hair_col)
    # Hair
    for hi in range(8):
        ha = (hi / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.05*scale,
                      loc=(math.cos(ha)*0.15*scale, math.sin(ha)*0.10*scale, 0.10*scale),
                      parent=head_p_e, mat_=hair_col)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.03*scale), parent=head_p_e, mat_=random.choice(EYE_COLORS_I))
    # Rosy cheeks (signature drunk)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ch{side}", r=0.05*scale,
                      loc=(side*0.12*scale, -0.18*scale, -0.05*scale), parent=head_p_e,
                      mat_=M_LIPS_RED_I)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_p_e, "pint_arm": sh_r}

patrons = []
# 2 patrons per table (4 tables = 8 patrons)
for ti, (tx, ty, tz) in enumerate(table_positions):
    for pi in range(2):
        pa_p = pi * math.pi
        px_p = tx + math.cos(pa_p) * 2.2
        py_p = ty + math.sin(pa_p) * 2.2
        fac_p = pa_p + math.pi
        p = make_patron(f"patron{ti}_{pi}", (px_p, py_p, 0.95), scale=1.0, facing=fac_p)
        patrons.append(p)

# ============ BARMAN behind bar ============
barman_e = empty("barman", loc=(0, 11, 1.0))
# Body white shirt
smooth_cone("bm_torso", r1=0.32, r2=0.35, depth=0.65, segs=14, loc=(0, 0, 0.35),
            parent=barman_e, mat_=M_FLAG_WHITE)
# APRON brown signature
beveled_cube("bm_apron", (0.65, 0.10, 0.85), bevel_offset=0.06, loc=(0, -0.30, 0.30),
             parent=barman_e, mat_=M_APRON)
# Apron strap
cyl("bm_strap", r=0.02, depth=1.0, segs=8, loc=(0, -0.30, 0.85),
    parent=barman_e, mat_=M_APRON_TIE).rotation_euler = (0, math.radians(90), 0)
# Apron tie back
beveled_cube("bm_tie", (0.30, 0.10, 0.10), bevel_offset=0.02, loc=(0, 0.30, 0.40),
             parent=barman_e, mat_=M_APRON_TIE)
# Arms holding pint (signature)
for side in (-1, 1):
    sh = empty(f"bm_sh{side}", (side*0.30, -0.10, 0.75), parent=barman_e)
    sh.rotation_euler = (math.radians(-100), 0, math.radians(side*-20))
    cyl(f"bm_uarm{side}", r=0.06, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh, mat_=M_FLAG_WHITE)
    cyl(f"bm_fa{side}", r=0.05, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh, mat_=M_SKIN_PALE_I)
# Pint in hand
cyl("bm_pint_g", r=0.10, depth=0.45, segs=14, loc=(0, -0.50, 0.50),
    parent=barman_e, mat_=M_PINT_GLASS)
cyl("bm_pint_s", r=0.09, depth=0.40, segs=14, loc=(0, -0.50, 0.50),
    parent=barman_e, mat_=M_STOUT)
cyl("bm_pint_f", r=0.09, depth=0.08, segs=14, loc=(0, -0.50, 0.70),
    parent=barman_e, mat_=M_STOUT_FOAM)
# Head
bm_head_e = empty("bm_he", (0, 0, 1.20), parent=barman_e)
smooth_sphere("bm_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
              parent=bm_head_e, mat_=M_SKIN_FRECKLE)
# Big red beard signature
for bi in range(12):
    ba = (bi / 12.0) * math.pi - math.pi/2
    smooth_sphere(f"bm_bd{bi}", r=0.05,
                  loc=(math.sin(ba)*0.13, -0.15, -0.10 - (bi%3)*0.08),
                  parent=bm_head_e, mat_=M_HAIR_RED_IR)
# Hair
for hi in range(8):
    ha = (hi / 8.0) * math.pi * 2
    smooth_sphere(f"bm_hr{hi}", r=0.05,
                  loc=(math.cos(ha)*0.15, math.sin(ha)*0.10, 0.10),
                  parent=bm_head_e, mat_=M_HAIR_RED_IR)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"bm_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                  parent=bm_head_e, mat_=M_EYE_GREEN_I)
# Friendly smile
beveled_cube("bm_smile", (0.10, 0.04, 0.02), bevel_offset=0.005, loc=(0, -0.18, -0.05),
             parent=bm_head_e, mat_=M_LIPS_RED_I)

# ============ LEPRECHAUN + POT OF GOLD + RAINBOW (signature) ============
lep_e = empty("leprechaun", loc=(-12, 5, 0))
# Body green coat
smooth_cone("lep_body", r1=0.25, r2=0.30, depth=0.55, segs=14, loc=(0, 0, 0.85),
            parent=lep_e, mat_=M_LEP_GREEN)
# Belt with gold buckle
cyl("lep_belt", r=0.31, depth=0.08, segs=14, loc=(0, 0, 0.60), parent=lep_e, mat_=M_LEP_GREEN_DARK)
beveled_cube("lep_bk", (0.12, 0.08, 0.10), bevel_offset=0.02, loc=(0, -0.30, 0.60),
             parent=lep_e, mat_=M_LEP_BELT_GOLD)
# Buttons
for bi in range(4):
    smooth_sphere(f"lep_btn{bi}", r=0.03, loc=(0, -0.30, 0.75 + bi*0.10),
                  parent=lep_e, mat_=M_LEP_BELT_GOLD)
# Pants knee-length green
for side in (-1, 1):
    cyl(f"lep_leg{side}", r=0.08, depth=0.45, segs=10,
        loc=(side*0.10, 0, 0.30), parent=lep_e, mat_=M_LEP_GREEN)
    # White socks
    cyl(f"lep_so{side}", r=0.06, depth=0.20, segs=10,
        loc=(side*0.10, 0, 0.10), parent=lep_e, mat_=M_FLAG_WHITE)
    # Pointed shoes (signature with brass buckle)
    beveled_cube(f"lep_sh{side}", (0.10, 0.20, 0.06), bevel_offset=0.02,
                 loc=(side*0.10, 0.06, 0), parent=lep_e, mat_=M_LEP_SHOES)
    # Curl tip
    smooth_sphere(f"lep_sh_t{side}", r=0.04, loc=(side*0.10, 0.16, 0.06),
                  parent=lep_e, mat_=M_LEP_BELT_GOLD)
# Arms
for side in (-1, 1):
    sh = empty(f"lep_sh{side}", (side*0.25, 0, 1.05), parent=lep_e)
    sh.rotation_euler = (math.radians(-50), 0, math.radians(side*-15))
    cyl(f"lep_uarm{side}", r=0.05, depth=0.30, segs=10, loc=(0, 0, -0.15),
        parent=sh, mat_=M_LEP_GREEN)
    cyl(f"lep_fa{side}", r=0.045, depth=0.25, segs=10, loc=(0, 0, -0.42),
        parent=sh, mat_=M_SKIN_PALE_I)
# Head
lep_head_e = empty("lep_he", (0, 0, 1.25), parent=lep_e)
smooth_sphere("lep_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
              parent=lep_head_e, mat_=M_SKIN_PALE_I, scale=(1, 1.0, 1.1))
# RED BEARD signature
for bi in range(15):
    ba = (bi / 15.0) * math.pi - math.pi/2
    smooth_sphere(f"lep_bd{bi}", r=0.05,
                  loc=(math.sin(ba)*0.14, -0.16, -0.12 - (bi%3)*0.08),
                  parent=lep_head_e, mat_=M_LEP_BEARD_RED)
# Eyes (mischievous green)
for side in (-1, 1):
    smooth_sphere(f"lep_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                  parent=lep_head_e, mat_=M_EYE_GREEN_I)
# Pointy ears
for side in (-1, 1):
    smooth_cone(f"lep_ear{side}", r1=0.06, r2=0.01, depth=0.20, segs=8,
                loc=(side*0.18, 0, 0.05), parent=lep_head_e,
                mat_=M_SKIN_PALE_I).rotation_euler = (0, 0, math.radians(side*70))
# TOP HAT signature with gold buckle
hat_lep_e = empty("lep_hat", (0, 0, 0.22), parent=lep_head_e)
cyl("lep_h_brim", r=0.28, depth=0.04, segs=18, loc=(0, 0, 0),
    parent=hat_lep_e, mat_=M_LEP_HAT)
cyl("lep_h_c", r=0.22, depth=0.50, segs=16, loc=(0, 0, 0.27),
    parent=hat_lep_e, mat_=M_LEP_HAT)
# Hat band
cyl("lep_h_band", r=0.23, depth=0.06, segs=18, loc=(0, 0, 0.10),
    parent=hat_lep_e, mat_=M_LEP_GREEN_DARK)
# Gold buckle on hat
beveled_cube("lep_h_bk", (0.10, 0.05, 0.08), bevel_offset=0.02, loc=(0, -0.22, 0.10),
             parent=hat_lep_e, mat_=M_LEP_BELT_GOLD)
# 4-LEAF CLOVER pinned (signature lucky)
clover_e = empty("lep_clover", (0.18, -0.30, 0.85), parent=lep_e)
for ci in range(4):
    ca = (ci / 4.0) * math.pi * 2
    smooth_sphere(f"lep_cl{ci}", r=0.04,
                  loc=(math.cos(ca)*0.06, 0, math.sin(ca)*0.06),
                  parent=clover_e, mat_=M_SHAMROCK, scale=(1.2, 0.3, 1))

# POT OF GOLD (signature)
pot_e = empty("pot", loc=(-15, 8, 0))
# Pot body
smooth_sphere("pot_b", r=0.5, segs=22, rings=16, loc=(0, 0, 0.4),
              parent=pot_e, mat_=M_POT_BLACK, scale=(1.1, 1.1, 1.0))
# Rim
cyl("pot_r", r=0.55, depth=0.10, segs=22, loc=(0, 0, 0.85), parent=pot_e, mat_=M_POT_BLACK)
# Handle
for side in (-1, 1):
    for hi in range(5):
        ha = (hi / 4.0) * math.pi
        smooth_sphere(f"pot_h{side}_{hi}", r=0.04,
                      loc=(side*(0.55 + math.sin(ha)*0.10), 0, 0.85 + math.cos(ha)*0.20),
                      parent=pot_e, mat_=M_POT_BLACK)
# Gold coins overflowing (signature)
for gi in range(30):
    ga = random.uniform(0, math.pi*2)
    gr = random.uniform(0, 0.4)
    gz = random.uniform(0.8, 1.2)
    coin = cyl(f"pot_c{gi}", r=random.uniform(0.06, 0.09), depth=0.04, segs=12,
               loc=(math.cos(ga)*gr, math.sin(ga)*gr, gz), parent=pot_e, mat_=M_GOLD_COIN)
    coin.rotation_euler = (random.uniform(0, math.pi), random.uniform(0, math.pi), 0)
# Spilling coins
for ci in range(10):
    spx = random.uniform(-0.8, 0.8)
    spy = random.uniform(-1.2, -0.6)
    cyl(f"pot_sp{ci}", r=random.uniform(0.06, 0.08), depth=0.04, segs=12,
        loc=(spx, spy, 0.10), parent=pot_e, mat_=M_GOLD_COIN)

# RAINBOW (signature arc above pot)
rainbow_e = empty("rainbow", loc=(-15, 12, 7))
for ri, rcol in enumerate(RB_COLS):
    arc_r = 6 + ri * 0.5
    for ai in range(20):
        aa = math.pi * ai / 20.0
        ax_r = math.cos(aa) * arc_r
        az_r = math.sin(aa) * arc_r * 0.6
        smooth_sphere(f"rb{ri}_{ai}", r=0.3, segs=10, rings=8,
                      loc=(ax_r, 0, az_r - 1), parent=rainbow_e, mat_=rcol)

# ============ IRISH FLAG (signature) ============
flag_irl_e = empty("flag_irl", loc=(15, 13, 4))
# Pole
cyl("fi_pole", r=0.05, depth=4, segs=10, loc=(0, 0, 0), parent=flag_irl_e, mat_=M_FLOOR_WOOD_DARK)
# 3 vertical stripes
for ci, col in enumerate([M_FLAG_GREEN, M_FLAG_WHITE, M_FLAG_ORANGE]):
    beveled_cube(f"fi_s{ci}", (0.10, 0.10, 1.5), bevel_offset=0.04, loc=((ci-1)*0.20, 0.20, 1.5),
                 parent=flag_irl_e, mat_=col)
beveled_cube("fi_bg", (0.6, 0.06, 1.5), bevel_offset=0.06, loc=(0, 0.20, 1.5), parent=flag_irl_e, mat_=M_FLAG_WHITE)

# Shamrocks (signature 4-leaf clovers around pub)
for si in range(15):
    sa = random.uniform(0, math.pi*2); sr = random.uniform(8, 15)
    smooth_sphere(f"shamrock{si}_c", r=0.05, segs=12, rings=10,
                  loc=(sr*math.cos(sa), sr*math.sin(sa), 0.30 + random.uniform(0, 2)),
                  mat_=M_SHAMROCK, scale=(1, 0.3, 1))
    # 4 leaves
    sc_e = empty(f"sham_e{si}", (sr*math.cos(sa), sr*math.sin(sa), 0.30 + random.uniform(0, 2)))
    for li in range(4):
        la = (li / 4.0) * math.pi * 2
        smooth_sphere(f"sham_l{si}_{li}", r=0.06, loc=(math.cos(la)*0.08, 0, math.sin(la)*0.08),
                      parent=sc_e, mat_=M_SHAMROCK)

# ============ CHALKBOARD SIGN (signature) ============
ch_board_e = empty("chalk", loc=(15, -10, 3))
ch_board_e.rotation_euler = (0, 0, math.radians(-90))
beveled_cube("ch_bg", (1.5, 0.10, 2), bevel_offset=0.06, loc=(0, 0, 0), parent=ch_board_e, mat_=M_CHALK_BLACK)
beveled_cube("ch_fr", (1.6, 0.12, 2.1), bevel_offset=0.04, loc=(0, 0.01, 0), parent=ch_board_e, mat_=M_FLOOR_WOOD_DARK)
# Chalk writing (dots representing text)
for li in range(8):
    ly = -0.7 + li * 0.20
    for di in range(8):
        dx = -0.5 + di * 0.15
        smooth_sphere(f"chk_t{li}_{di}", r=0.02, loc=(dx, -0.06, ly),
                      parent=ch_board_e, mat_=M_CHALK_WHITE)

# Wall lamps (signature warm glow)
wall_lamps = []
for li in range(4):
    lx_l = -15 + li * 10
    lamp_e = empty(f"wlamp{li}", (lx_l, 14.7, 5))
    # Bracket
    beveled_cube(f"wl_br{li}", (0.10, 0.30, 0.20), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=lamp_e, mat_=M_LAMP_BRASS)
    # Lamp shade
    smooth_cone(f"wl_s{li}", r1=0.20, r2=0.10, depth=0.30, segs=14, loc=(0, -0.30, -0.15),
                parent=lamp_e, mat_=M_LAMP_BRASS)
    # Bulb glow
    smooth_sphere(f"wl_b{li}", r=0.12, loc=(0, -0.30, -0.10),
                  parent=lamp_e, mat_=M_LAMP_GLOW)
    wall_lamps.append(lamp_e)

# ============================================================
# ⭐ 600 STOUT BUBBLES + 400 CELTIC NOTES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
bubbles = []
for i in range(600):
    # Around the bar / pints area
    px = random.uniform(-15, 15)
    py = random.uniform(-12, 12)
    pz = random.uniform(0.5, 4)
    b = smooth_sphere(f"bub{i}", r=random.uniform(0.04, 0.07), segs=8, rings=6,
                      loc=(px, py, pz), mat_=M_BUBBLE)
    b["_phase"] = random.uniform(0, math.pi*2)
    b["_base_x"] = px; b["_base_y"] = py; b["_base_z"] = pz
    b["_amp_x"] = random.uniform(0.2, 0.6)
    b["_amp_y"] = random.uniform(0.2, 0.6)
    b["_speed"] = random.uniform(1.0, 2.5)
    b["_rise"] = random.uniform(1.0, 2.5)
    bubbles.append(b)

# 400 music notes (signature treble + eighth notes)
notes = []
for i in range(400):
    px = random.uniform(-15, 15)
    py = random.uniform(-10, 10)
    pz = random.uniform(2, 9)
    note_col = M_NOTE_GOLD if i % 2 == 0 else M_NOTE_GREEN
    note_e = empty(f"note{i}", (px, py, pz))
    # Note head (sphere)
    smooth_sphere(f"nh{i}", r=0.06, segs=10, rings=8, loc=(0, 0, 0),
                  parent=note_e, mat_=note_col, scale=(1.2, 0.8, 1))
    # Note stem
    cyl(f"ns{i}", r=0.012, depth=0.30, segs=8, loc=(0.05, 0, 0.15),
        parent=note_e, mat_=note_col)
    # Flag (eighth note)
    if i % 3 == 0:
        beveled_cube(f"nf{i}", (0.08, 0.02, 0.08), bevel_offset=0.005,
                     loc=(0.10, 0, 0.30), parent=note_e, mat_=note_col)
    note_e["_phase"] = random.uniform(0, math.pi*2)
    note_e["_base_x"] = px; note_e["_base_y"] = py; note_e["_base_z"] = pz
    note_e["_amp_x"] = random.uniform(1.0, 2.5)
    note_e["_amp_y"] = random.uniform(1.0, 2.5)
    note_e["_amp_z"] = random.uniform(0.5, 1.2)
    note_e["_speed"] = random.uniform(0.5, 1.2)
    notes.append(note_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Dancers step dance (signature high leg lifts)
for d in dancers:
    phase = d["root"]["_phase"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Bounce up rapidly
        d["root"].location.z = abs(math.sin(t * 6.0 + phase)) * 0.30
        d["root"].rotation_euler = (math.sin(t * 6.0 + phase) * math.radians(3), 0,
                                     d["root"].rotation_euler.z)
        d["root"].keyframe_insert("location", frame=f)
        d["root"].keyframe_insert("rotation_euler", frame=f)
        # Big smile/head straight (signature stoic upper body)
        d["he"].rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(5))
        d["he"].keyframe_insert("rotation_euler", frame=f)

# Musicians play (signature rhythmic motion)
for m in musicians:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 4.0 + phase) * math.radians(4),
                                     math.cos(t * 4.0 + phase) * math.radians(3),
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(8),
                                   0, math.cos(t * 2.0 + phase) * math.radians(5))
        m["he"].keyframe_insert("rotation_euler", frame=f)
        # Instrument vibrate
        sc_i = 1 + math.sin(t * 8.0 + phase) * 0.03
        m["inst"].scale = (sc_i, sc_i, sc_i)
        m["inst"].keyframe_insert("scale", frame=f)

# Patrons cheers (raise pints)
for p in patrons:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Cheer arm motion
        p["pint_arm"].rotation_euler = (math.radians(-120) + math.sin(t * 1.5 + phase) * math.radians(15),
                                          0, math.radians(-30))
        p["pint_arm"].keyframe_insert("rotation_euler", frame=f)
        # Body sway happily
        p["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3),
                                     math.cos(t * 1.5 + phase) * math.radians(5),
                                     p["root"].rotation_euler.z)
        p["root"].keyframe_insert("rotation_euler", frame=f)
        # Head laugh
        p["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0,
                                   math.cos(t * 1.5 + phase) * math.radians(10))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Barman polish + head turn
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    barman_e.rotation_euler = (0, math.sin(t * 1.5) * math.radians(5), 0)
    barman_e.keyframe_insert("rotation_euler", frame=f)
    bm_head_e.rotation_euler = (0, 0, math.sin(t * 1.0) * math.radians(20))
    bm_head_e.keyframe_insert("rotation_euler", frame=f)

# Leprechaun mischievous dance
phase_lep = 0
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    lep_e.rotation_euler = (math.sin(t * 3.0) * math.radians(8),
                             math.cos(t * 3.0) * math.radians(10),
                             math.sin(t * 1.5) * math.radians(15))
    lep_e.location.z = abs(math.sin(t * 4.0)) * 0.20
    lep_e.keyframe_insert("rotation_euler", frame=f)
    lep_e.keyframe_insert("location", frame=f)
    lep_head_e.rotation_euler = (0, 0, math.sin(t * 2.0) * math.radians(25))
    lep_head_e.keyframe_insert("rotation_euler", frame=f)

# Fireplace flicker
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    sc_fl = 1 + math.sin(t * 6.0) * 0.15
    flame_fp.scale = (1 + math.cos(t * 5.0) * 0.10, 1 + math.sin(t * 5.0) * 0.10, sc_fl)
    flame_fp.keyframe_insert("scale", frame=f)

# Embers float up
for em in embers_fp:
    phase = em["_phase"]
    bx_e = em.location.x; by_e = em.location.y; bz_e = em.location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        em.location.x = bx_e + math.sin(t * 2.0 + phase) * 0.20
        em.location.z = bz_e + (t * 1.5) % 3
        em.keyframe_insert("location", frame=f)

# Wall lamps flicker subtle
for wl in wall_lamps:
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        sc_w = 1 + math.sin(t * 3.0) * 0.10
        wl.scale = (sc_w, sc_w, sc_w)
        wl.keyframe_insert("scale", frame=f)

# 600 bubbles rise (signature stout bubbles)
for b in bubbles:
    phase = b["_phase"]; speed = b["_speed"]; rise = b["_rise"]
    bx, by, bz = b["_base_x"], b["_base_y"], b["_base_z"]
    ax, ay = b["_amp_x"], b["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + (t * rise) % 4
        b.location = (x, y, z)
        sc_b = 0.7 + abs(math.sin(t * speed + phase)) * 0.6
        b.scale = (sc_b, sc_b, sc_b)
        b.keyframe_insert("location", frame=f)
        b.keyframe_insert("scale", frame=f)

# 400 notes float
for n in notes:
    phase = n["_phase"]; speed = n["_speed"]
    bx, by, bz = n["_base_x"], n["_base_y"], n["_base_z"]
    ax, ay, az = n["_amp_x"], n["_amp_y"], n["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase) + (t * 0.3) % 2
        n.location = (x, y, max(2, z))
        n.rotation_euler = (math.sin(t * 1.5 + phase) * 0.3,
                             0, math.cos(t * 1.5 + phase) * 0.3)
        n.keyframe_insert("location", frame=f)
        n.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_irish_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_irish_pub_dance_celtic] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_irish_pub_dance_celtic] pub + bar + 5 taps + 6 step dancers + 4 musicians (fiddle+whistle+bodhran+guitar) + 8 patrons + barman + fireplace + leprechaun + pot of gold + rainbow + Irish flag + 15 shamrocks + 600 bubbles + 400 notes")
print("⭐ FIXES: 1 ground + 600 stout bubbles + 400 celtic notes (signature Irish pub thematic mandatory) ⭐")
