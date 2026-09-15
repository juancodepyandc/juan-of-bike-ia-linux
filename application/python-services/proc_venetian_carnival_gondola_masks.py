"""
proc_venetian_carnival_gondola_masks.py — 256e procédural AuroraIA (121e qualité)
Venice Carnival: 4 black gondolas + 6 masked carnival figures + Doge's Palace + St Mark's Cathedral + Bridge of Sighs + 4 musicians + pigeons + 600 mask feathers + 400 gold confetti
FIXES : 1 ground + 600 feathers + 400 confetti (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB256)

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

# Sunset pastel pink sky signature
M_SKY = mat("sky", (0.92, 0.65, 0.78, 1.0), 0.0, 0.7, emission=(0.92,0.65,0.78), emission_strength=2.0)
M_SKY_HORIZON = mat("sky_h", (1.0, 0.78, 0.55, 1.0), 0.0, 0.7, emission=(1.0,0.78,0.55), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.85, 0.55, 1.0), 0.0, 0.1, emission=(1.0,0.85,0.55), emission_strength=12.0)
M_CLOUD_PINK = mat("cloud_p", (0.98, 0.88, 0.92, 1.0), 0.0, 0.7, emission=(0.95,0.85,0.90), emission_strength=1.5)

# Stone pavement
M_STONE_VEN = mat("stone", (0.78, 0.72, 0.62, 1.0), 0.0, 0.85, emission=(0.72,0.68,0.60), emission_strength=0.4)
M_STONE_PAVE_DARK = mat("stone_d", (0.55, 0.52, 0.45, 1.0), 0.0, 0.85)
M_STONE_TILE_VEN = mat("stone_t", (0.85, 0.78, 0.65, 1.0), 0.0, 0.80, emission=(0.78,0.72,0.62), emission_strength=0.4)

# Canal water (signature turquoise green Venice)
M_CANAL = mat("canal", (0.20, 0.55, 0.62, 1.0), 0.1, 0.20, emission=(0.20,0.55,0.62), emission_strength=1.5, alpha=0.78)
M_CANAL_DEEP = mat("canal_d", (0.12, 0.42, 0.55, 1.0), 0.1, 0.25, alpha=0.85)
M_REFLECT = mat("refl", (0.95, 0.78, 0.55, 1.0), 0.0, 0.10, emission=(0.92,0.75,0.55), emission_strength=2.0, alpha=0.55)

# Palace stone signature pink-ish marble
M_PALACE_PINK = mat("palace_p", (0.92, 0.78, 0.62, 1.0), 0.0, 0.65, emission=(0.88,0.75,0.62), emission_strength=0.5)
M_PALACE_WHITE = mat("palace_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.90,0.88,0.82), emission_strength=0.6)
M_PALACE_GOLD = mat("palace_g", (0.95, 0.78, 0.25, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.25), emission_strength=2.0)
M_PALACE_DARK = mat("palace_d", (0.55, 0.42, 0.30, 1.0), 0.0, 0.85)

# Cathedral colors
M_DOME_GOLD = mat("dome", (1.0, 0.85, 0.30, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.30), emission_strength=3.0)
M_DOME_BLUE = mat("dome_b", (0.30, 0.45, 0.78, 1.0), 0.4, 0.30, emission=(0.28,0.42,0.75), emission_strength=1.5)
M_DOME_GREEN = mat("dome_g", (0.30, 0.55, 0.42, 1.0), 0.4, 0.30, emission=(0.28,0.52,0.40), emission_strength=1.2)

# Gondola signature shiny black
M_GONDOLA_BLACK = mat("gond_b", (0.05, 0.04, 0.04, 1.0), 0.7, 0.20, emission=(0.10,0.08,0.08), emission_strength=0.5)
M_GONDOLA_DEEP = mat("gond_d", (0.02, 0.02, 0.02, 1.0), 0.8, 0.25)
M_GONDOLA_GOLD = mat("gond_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.15, emission=(0.92,0.75,0.30), emission_strength=2.0)
M_GONDOLA_VELVET = mat("vel", (0.62, 0.18, 0.20, 1.0), 0.0, 0.65, emission=(0.58,0.18,0.20), emission_strength=0.5)
M_GONDOLA_VELVET_BLUE = mat("vel_b", (0.18, 0.30, 0.62, 1.0), 0.0, 0.65, emission=(0.18,0.30,0.60), emission_strength=0.5)

# Gondolier outfit (signature striped shirt)
M_STRIPE_WHITE = mat("st_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.90,0.88,0.82), emission_strength=0.4)
M_STRIPE_BLACK = mat("st_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.75)
M_STRIPE_RED = mat("st_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.72,0.18,0.18), emission_strength=0.5)
M_HAT_STRAW = mat("hat_s", (0.85, 0.72, 0.42, 1.0), 0.0, 0.75, emission=(0.78,0.68,0.42), emission_strength=0.4)
M_HAT_BAND = mat("hat_b", (0.62, 0.18, 0.18, 1.0), 0.0, 0.65)

# Skin
M_SKIN_PALE_V = mat("skin", (0.92, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.62), emission_strength=0.4)

# Hair
M_HAIR_BLACK_V = mat("h_bk", (0.10, 0.06, 0.04, 1.0), 0.0, 0.55)
M_HAIR_BROWN_V = mat("h_br", (0.32, 0.18, 0.10, 1.0), 0.0, 0.60)
M_HAIR_BLOND_V = mat("h_bl", (0.85, 0.65, 0.30, 1.0), 0.0, 0.55)

# MASK COLORS (signature carnival)
M_MASK_WHITE = mat("mk_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.30, emission=(0.92,0.90,0.82), emission_strength=1.0)
M_MASK_GOLD = mat("mk_g", (1.0, 0.85, 0.30, 1.0), 0.95, 0.10, emission=(0.95,0.80,0.30), emission_strength=2.5)
M_MASK_SILVER = mat("mk_s", (0.92, 0.92, 0.95, 1.0), 0.95, 0.10, emission=(0.88,0.88,0.92), emission_strength=2.0)
M_MASK_BLACK = mat("mk_bk", (0.08, 0.06, 0.06, 1.0), 0.3, 0.40)
M_MASK_RED = mat("mk_r", (0.78, 0.15, 0.18, 1.0), 0.3, 0.30, emission=(0.72,0.15,0.18), emission_strength=1.2)
M_MASK_PURPLE = mat("mk_p", (0.62, 0.20, 0.78, 1.0), 0.3, 0.30, emission=(0.60,0.20,0.75), emission_strength=1.2)
M_MASK_BLUE = mat("mk_b", (0.20, 0.45, 0.85, 1.0), 0.3, 0.30, emission=(0.18,0.42,0.80), emission_strength=1.2)
MASK_COLORS = [M_MASK_WHITE, M_MASK_GOLD, M_MASK_SILVER, M_MASK_RED, M_MASK_PURPLE, M_MASK_BLUE]

# Baroque dress colors (signature carnival opulent)
M_DRESS_GOLD = mat("dr_gd", (0.92, 0.78, 0.32, 1.0), 0.5, 0.30, emission=(0.88,0.75,0.32), emission_strength=1.2)
M_DRESS_VENETIAN_RED = mat("dr_vr", (0.62, 0.15, 0.20, 1.0), 0.0, 0.55, emission=(0.58,0.15,0.20), emission_strength=0.6)
M_DRESS_PURPLE = mat("dr_pu", (0.55, 0.25, 0.78, 1.0), 0.0, 0.55, emission=(0.52,0.25,0.75), emission_strength=0.6)
M_DRESS_TEAL = mat("dr_t", (0.18, 0.55, 0.55, 1.0), 0.0, 0.55, emission=(0.18,0.55,0.55), emission_strength=0.7)
M_DRESS_PINK_V = mat("dr_pk", (0.85, 0.45, 0.65, 1.0), 0.0, 0.55, emission=(0.80,0.42,0.62), emission_strength=0.7)
M_DRESS_EMERALD = mat("dr_em", (0.18, 0.55, 0.32, 1.0), 0.0, 0.55, emission=(0.18,0.52,0.30), emission_strength=0.6)
DRESS_COLORS = [M_DRESS_GOLD, M_DRESS_VENETIAN_RED, M_DRESS_PURPLE, M_DRESS_TEAL, M_DRESS_PINK_V, M_DRESS_EMERALD]

# Feather plume colors
M_FEATHER_W = mat("fe_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.45, emission=(0.90,0.88,0.85), emission_strength=1.5)
M_FEATHER_GO = mat("fe_g", (1.0, 0.85, 0.30, 1.0), 0.0, 0.45, emission=(0.95,0.80,0.30), emission_strength=2.5)
M_FEATHER_R = mat("fe_r", (0.92, 0.20, 0.25, 1.0), 0.0, 0.45, emission=(0.88,0.20,0.25), emission_strength=1.8)
M_FEATHER_P = mat("fe_p", (0.65, 0.25, 0.85, 1.0), 0.0, 0.45, emission=(0.62,0.25,0.82), emission_strength=1.8)
M_FEATHER_B = mat("fe_b", (0.25, 0.55, 0.92, 1.0), 0.0, 0.45, emission=(0.25,0.55,0.90), emission_strength=1.8)
FEATHER_VENICE = [M_FEATHER_W, M_FEATHER_GO, M_FEATHER_R, M_FEATHER_P, M_FEATHER_B]

# Lips dark red
M_LIPS_DARK = mat("lips_d", (0.55, 0.10, 0.18, 1.0), 0.0, 0.40, emission=(0.52,0.10,0.18), emission_strength=0.6)

# Eye
M_EYE_DARK_V = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_LIGHT = mat("eye_l", (0.30, 0.55, 0.85, 1.0), 0.0, 0.20, emission=(0.28,0.52,0.82), emission_strength=1.0)

# Music instruments
M_ACCORDION_RED = mat("acc_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.72,0.18,0.18), emission_strength=0.6)
M_ACCORDION_BLACK = mat("acc_bk", (0.10, 0.08, 0.08, 1.0), 0.3, 0.40)
M_VIOLIN_WOOD = mat("vio_w", (0.55, 0.20, 0.10, 1.0), 0.0, 0.45, emission=(0.50,0.20,0.10), emission_strength=0.5)
M_VIOLIN_DARK = mat("vio_d", (0.18, 0.08, 0.04, 1.0), 0.0, 0.60)
M_STRING = mat("string", (0.85, 0.85, 0.85, 1.0), 0.5, 0.30)

# Pigeons
M_PIGEON_GREY = mat("pg_g", (0.65, 0.65, 0.70, 1.0), 0.0, 0.70, emission=(0.60,0.60,0.65), emission_strength=0.4)
M_PIGEON_DARK = mat("pg_d", (0.42, 0.42, 0.48, 1.0), 0.0, 0.75)
M_PIGEON_NECK = mat("pg_n", (0.55, 0.45, 0.65, 1.0), 0.3, 0.30, emission=(0.55,0.45,0.65), emission_strength=0.8)

# Confetti / particles
M_CONFETTI_GOLD = mat("conf_g", (1.0, 0.85, 0.30, 1.0), 0.95, 0.10, emission=(0.95,0.80,0.30), emission_strength=4.0)
M_CONFETTI_SILVER = mat("conf_s", (0.92, 0.92, 0.95, 1.0), 0.95, 0.10, emission=(0.88,0.88,0.92), emission_strength=3.5)
CONFETTI_COLS = [M_CONFETTI_GOLD, M_CONFETTI_SILVER]

# Buildings (Venice waterfront)
M_BUILDING_ORANGE = mat("bd_o", (0.95, 0.62, 0.32, 1.0), 0.0, 0.85, emission=(0.88,0.60,0.32), emission_strength=0.5)
M_BUILDING_YELLOW = mat("bd_y", (0.95, 0.85, 0.55, 1.0), 0.0, 0.75, emission=(0.88,0.80,0.55), emission_strength=0.5)
M_BUILDING_RED = mat("bd_r", (0.78, 0.42, 0.32, 1.0), 0.0, 0.85, emission=(0.72,0.40,0.30), emission_strength=0.4)
M_BUILDING_PINK = mat("bd_p", (0.92, 0.75, 0.68, 1.0), 0.0, 0.80, emission=(0.85,0.72,0.65), emission_strength=0.5)
BUILDING_COLORS = [M_BUILDING_ORANGE, M_BUILDING_YELLOW, M_BUILDING_RED, M_BUILDING_PINK]
M_WINDOW_GLOW = mat("win_g", (1.0, 0.88, 0.45, 1.0), 0.0, 0.20, emission=(1.0,0.88,0.45), emission_strength=4.0)

# ============ SKY (sunset pastel pink) ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Lower horizon orange
sky_h = smooth_sphere("sky_h", r=230, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_HORIZON)
sky_h.scale = (1,1,0.25)
# Sun
sun = smooth_sphere("sun", r=5, segs=24, rings=18, loc=(-20, 70, 35), mat_=M_SUN)
# Pink clouds
for ci in range(20):
    cax = random.uniform(-100, 100); cay = random.uniform(-100, 100)
    caz = random.uniform(25, 60)
    cloud_e = empty(f"cloud{ci}", (cax, cay, caz))
    for cli in range(random.randint(3, 5)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(3, 5), segs=16, rings=10,
                      loc=(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD_PINK, scale=(1.4, 1.2, 0.7))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)

# ============ ONE clean stone pavement ground ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_STONE_VEN)
# Plaza tiles signature
for ti in range(40):
    for tj in range(40):
        tx_g = -58 + ti * 3; ty_g = -58 + tj * 3
        # Avoid canal area
        if abs(tx_g) > 50 or abs(ty_g) > 50: continue
        if 8 < ty_g < 25 and -25 < tx_g < 25: continue  # canal cutout
        tcol = M_STONE_TILE_VEN if (ti + tj) % 2 == 0 else M_STONE_VEN
        beveled_cube(f"tile{ti}_{tj}", (2.8, 2.8, 0.06), bevel_offset=0.02,
                     loc=(tx_g, ty_g, 0.12), mat_=tcol)

# ============ CANAL (signature serpentine) ============
canal_e = empty("canal", (0, 15, 0))
# Main canal stretch
beveled_cube("canal_main", (50, 12, 0.20), bevel_offset=0.06, loc=(0, 0, 0.10),
             parent=canal_e, mat_=M_CANAL)
beveled_cube("canal_deep", (48, 11, 0.15), bevel_offset=0.04, loc=(0, 0, 0.15),
             parent=canal_e, mat_=M_CANAL_DEEP)
# Sunset reflections on water
for ri in range(20):
    rx_r = random.uniform(-22, 22); ry_r = random.uniform(-5, 5)
    cyl(f"refl{ri}", r=random.uniform(0.40, 0.80), depth=0.04, segs=14,
        loc=(rx_r, ry_r, 0.18), parent=canal_e, mat_=M_REFLECT)
# Stone canal walls
for side in (-1, 1):
    beveled_cube(f"canal_wall_{side}", (50, 0.5, 1.2), bevel_offset=0.06,
                 loc=(0, side*6.3, 0.4), parent=canal_e, mat_=M_PALACE_DARK)
# Mooring posts (signature striped Venice)
for pi in range(8):
    px_p = -22 + pi * 6
    cyl(f"post{pi}", r=0.18, depth=2.5, segs=12, loc=(px_p, -6.5, 1),
        parent=canal_e, mat_=M_STRIPE_WHITE)
    # Red stripes signature
    for sl in range(3):
        cyl(f"post_s{pi}_{sl}", r=0.19, depth=0.20, segs=12,
            loc=(px_p, -6.5, 0.4 + sl*0.6), parent=canal_e, mat_=M_STRIPE_RED)

# ============ DOGE'S PALACE (signature gothic) ============
doge_e = empty("doge", loc=(-30, -10, 0))
# Base
beveled_cube("dg_base", (25, 12, 0.6), bevel_offset=0.10, loc=(0, 0, 0.3),
             parent=doge_e, mat_=M_PALACE_PINK)
# Main body with gothic windows (signature)
beveled_cube("dg_body", (24, 11, 8), bevel_offset=0.10, loc=(0, 0, 4.6),
             parent=doge_e, mat_=M_PALACE_PINK)
# Lower arcade (signature columned)
for ai in range(12):
    ax_a = -11 + ai * 2
    # Column
    cyl(f"dg_col{ai}", r=0.30, depth=3, segs=18, loc=(ax_a, -5.5, 2.0),
        parent=doge_e, mat_=M_PALACE_WHITE)
    # Capital
    cyl(f"dg_cap{ai}", r=0.40, depth=0.20, segs=18, loc=(ax_a, -5.5, 3.6),
        parent=doge_e, mat_=M_PALACE_WHITE)
    # Arches between
    if ai < 11:
        smooth_sphere(f"dg_ar{ai}", r=1.0, segs=18, rings=14,
                      loc=(ax_a + 1, -5.5, 3.7), parent=doge_e, mat_=M_PALACE_WHITE,
                      scale=(1, 0.2, 0.8))
# Second floor windows (signature)
for wi in range(12):
    wx_w = -11 + wi * 2
    # Frame
    beveled_cube(f"dg_w{wi}", (1.5, 0.3, 2.5), bevel_offset=0.10,
                 loc=(wx_w, -5.5, 6.5), parent=doge_e, mat_=M_PALACE_WHITE)
    # Glass
    beveled_cube(f"dg_wg{wi}", (1.2, 0.10, 2.2), bevel_offset=0.06,
                 loc=(wx_w, -5.55, 6.5), parent=doge_e, mat_=M_WINDOW_GLOW)
# Crenellated top (signature)
for ci in range(14):
    cx_p = -11.5 + ci * 1.8
    beveled_cube(f"dg_cr{ci}", (0.9, 1.0, 0.7), bevel_offset=0.05,
                 loc=(cx_p, -5.5, 9), parent=doge_e, mat_=M_PALACE_PINK)
# Top facade
beveled_cube("dg_top", (24, 11, 0.6), bevel_offset=0.06, loc=(0, 0, 8.4),
             parent=doge_e, mat_=M_PALACE_PINK)

# ============ ST MARK'S CATHEDRAL (signature 5 domes) ============
basilica_e = empty("basilica", loc=(0, -25, 0))
# Base
beveled_cube("ba_base", (24, 18, 4), bevel_offset=0.10, loc=(0, 0, 2),
             parent=basilica_e, mat_=M_PALACE_WHITE)
# Façade
beveled_cube("ba_facade", (24, 0.6, 10), bevel_offset=0.10, loc=(0, -9.2, 5),
             parent=basilica_e, mat_=M_PALACE_WHITE)
# Gothic arches front
for ai in range(5):
    ax_a = -10 + ai * 5
    # Arch
    cyl(f"ba_ar{ai}", r=1.8, depth=0.30, segs=20, loc=(ax_a, -9.55, 6),
        parent=basilica_e, mat_=M_PALACE_GOLD).rotation_euler = (math.radians(90), 0, 0)
    # Window in arch
    smooth_sphere(f"ba_arw{ai}", r=1.5, loc=(ax_a, -9.5, 6),
                  parent=basilica_e, mat_=M_WINDOW_GLOW, scale=(1, 0.05, 1))
# 5 DOMES (signature) - center largest
for di in range(5):
    if di == 2:
        # Central dome (largest)
        smooth_sphere(f"ba_d{di}", r=4, segs=24, rings=16, loc=(0, 0, 12),
                      parent=basilica_e, mat_=M_DOME_GOLD, scale=(1, 1, 1.2))
        # Lantern on top
        cyl(f"ba_lt{di}", r=0.6, depth=1.5, segs=18, loc=(0, 0, 16),
            parent=basilica_e, mat_=M_PALACE_WHITE)
        smooth_sphere(f"ba_lt_d{di}", r=0.6, loc=(0, 0, 17),
                      parent=basilica_e, mat_=M_DOME_GOLD)
        # Cross
        beveled_cube(f"ba_cr_v{di}", (0.10, 0.10, 1.0), bevel_offset=0.02,
                     loc=(0, 0, 18), parent=basilica_e, mat_=M_DOME_GOLD)
        beveled_cube(f"ba_cr_h{di}", (0.10, 0.50, 0.10), bevel_offset=0.02,
                     loc=(0, 0, 18.2), parent=basilica_e, mat_=M_DOME_GOLD)
    else:
        # 4 corner domes
        dx_d = (-8, -8, 8, 8)[di if di < 2 else di-1]
        dy_d = (-5, 5, -5, 5)[di if di < 2 else di-1]
        smooth_sphere(f"ba_d{di}", r=2.5, segs=22, rings=14, loc=(dx_d, dy_d, 9),
                      parent=basilica_e,
                      mat_=M_DOME_BLUE if di < 2 else M_DOME_GREEN, scale=(1, 1, 1.15))
        # Small lantern
        smooth_sphere(f"ba_lt{di}", r=0.4, loc=(dx_d, dy_d, 11.5),
                      parent=basilica_e, mat_=M_PALACE_WHITE)
# Decorative mosaics (signature gold)
for mi in range(5):
    mx_m = -10 + mi * 5
    beveled_cube(f"ba_mos{mi}", (3, 0.10, 3), bevel_offset=0.06,
                 loc=(mx_m, -9.6, 9.5), parent=basilica_e, mat_=M_PALACE_GOLD)
    # Cross details
    beveled_cube(f"ba_mc{mi}_v", (0.5, 0.12, 2.5), bevel_offset=0.04,
                 loc=(mx_m, -9.7, 9.5), parent=basilica_e, mat_=M_DOME_BLUE)
# Pinnacles on top
for pi in range(7):
    px_p = -12 + pi * 4
    smooth_cone(f"ba_pin{pi}", r1=0.30, r2=0.05, depth=2, segs=8,
                loc=(px_p, -9.5, 12), parent=basilica_e, mat_=M_PALACE_WHITE)
# 4 BRONZE HORSES (signature Cavalli di San Marco)
for hi in range(4):
    hx_h = -3 + hi * 2
    h_e = empty(f"ba_h{hi}", (hx_h, -9.5, 11), parent=basilica_e)
    # Body
    smooth_sphere(f"horse_b{hi}", r=0.30, segs=16, rings=10, loc=(0, 0, 0.20),
                  parent=h_e, mat_=M_PALACE_GOLD, scale=(1.5, 0.85, 1))
    # 4 legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"horse_l{hi}_{x}_{y}", r=0.05, depth=0.40, segs=8,
                loc=(x*0.20, y*0.15, 0), parent=h_e, mat_=M_PALACE_GOLD)
    # Head
    smooth_sphere(f"horse_h{hi}", r=0.10, loc=(0.30, 0, 0.30),
                  parent=h_e, mat_=M_PALACE_GOLD, scale=(1.5, 0.85, 0.85))

# CAMPANILE TOWER (signature)
camp_e = empty("campanile", (15, -25, 0))
# Tower body
beveled_cube("cmp_b", (4, 4, 20), bevel_offset=0.10, loc=(0, 0, 10),
             parent=camp_e, mat_=M_BUILDING_ORANGE)
# Brick pattern lines
for bi in range(20):
    beveled_cube(f"cmp_bk{bi}", (4.05, 4.05, 0.04), bevel_offset=0.01,
                 loc=(0, 0, bi * 1), parent=camp_e, mat_=M_BUILDING_RED)
# Belfry (signature columns)
beveled_cube("cmp_belf", (5, 5, 3), bevel_offset=0.10, loc=(0, 0, 21.5),
             parent=camp_e, mat_=M_PALACE_WHITE)
for ai in range(4):
    aa = (ai / 4.0) * math.pi * 2
    for ci in range(3):
        cx_c = math.cos(aa)*2.1 + math.sin(aa)*(ci-1)*0.7
        cy_c = math.sin(aa)*2.1 + math.cos(aa)*(ci-1)*0.7
        cyl(f"cmp_col{ai}_{ci}", r=0.10, depth=2.5, segs=10,
            loc=(cx_c, cy_c, 21.5), parent=camp_e, mat_=M_PALACE_WHITE)
# Pyramid roof
smooth_cone("cmp_r", r1=2.5, r2=0.05, depth=4, segs=4, loc=(0, 0, 25),
            parent=camp_e, mat_=M_PALACE_GOLD).rotation_euler = (0, 0, math.radians(45))
# Angel statue on top (signature)
angel_e = empty("cmp_angel", (0, 0, 28), parent=camp_e)
smooth_sphere("cmp_a_b", r=0.4, segs=18, rings=14, loc=(0, 0, 0),
              parent=angel_e, mat_=M_PALACE_GOLD)
# Wings
for side in (-1, 1):
    beveled_cube(f"cmp_a_w{side}", (0.10, 0.5, 0.4), bevel_offset=0.04,
                 loc=(side*0.30, 0, 0.20), parent=angel_e, mat_=M_PALACE_GOLD)

# ============ BRIDGE OF SIGHS (signature) ============
bridge_e = empty("bridge", loc=(-12, 15, 0))
# Bridge arch
for ai in range(15):
    aa = math.pi * ai / 15.0
    ax_b = math.cos(aa) * 4
    az_b = math.sin(aa) * 3
    smooth_sphere(f"br{ai}", r=0.5, segs=14, rings=10,
                  loc=(ax_b, 0, az_b + 3), parent=bridge_e, mat_=M_PALACE_WHITE,
                  scale=(1, 0.6, 1))
# Bridge top covered passage
beveled_cube("br_top", (5, 3, 1.5), bevel_offset=0.10, loc=(0, 0, 6),
             parent=bridge_e, mat_=M_PALACE_WHITE)
# Carved windows (signature pierced)
for wi in range(3):
    wx_b = -1.2 + wi * 1.2
    beveled_cube(f"br_w{wi}", (0.6, 3.2, 0.6), bevel_offset=0.06,
                 loc=(wx_b, 0, 6.5), parent=bridge_e, mat_=M_PALACE_DARK)
# Decorative roof
beveled_cube("br_roof", (5.2, 3.2, 0.30), bevel_offset=0.06, loc=(0, 0, 6.9),
             parent=bridge_e, mat_=M_PALACE_DARK)

# ============ BUILDINGS along canal ============
for bi in range(8):
    bx_p = -25 + bi * 7
    by_p = 22
    bh = random.uniform(8, 14)
    bld_e = empty(f"bld{bi}", (bx_p, by_p, 0))
    bld_col = random.choice(BUILDING_COLORS)
    # Body
    beveled_cube(f"b{bi}_b", (5, 5, bh), bevel_offset=0.10, loc=(0, 0, bh/2),
                 parent=bld_e, mat_=bld_col)
    # Windows
    for wfloor in range(int(bh/3)):
        for wcol in range(3):
            wx_w = -1.5 + wcol * 1.5
            wz_w = 1.5 + wfloor * 3
            beveled_cube(f"b{bi}_w{wfloor}_{wcol}", (0.7, 0.10, 1.2), bevel_offset=0.04,
                         loc=(wx_w, -2.5, wz_w), parent=bld_e, mat_=M_WINDOW_GLOW)
            # Shutters
            for side_s in (-1, 1):
                beveled_cube(f"b{bi}_s{wfloor}_{wcol}_{side_s}", (0.40, 0.06, 1.3), bevel_offset=0.03,
                             loc=(wx_w + side_s*0.6, -2.55, wz_w), parent=bld_e, mat_=M_PALACE_DARK)
    # Roof tiles red
    beveled_cube(f"b{bi}_r", (5.2, 5.2, 0.5), bevel_offset=0.10, loc=(0, 0, bh + 0.25),
                 parent=bld_e, mat_=M_GONDOLA_VELVET)

# ============ 4 GONDOLAS (signature black curved elegant) ============
def make_gondola(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # LONG HULL (signature curved, asymmetric)
    hull = smooth_cone(f"{name}_hull", r1=0.55, r2=0.15, depth=10, segs=18, loc=(0, 0, 0),
                       parent=base, mat_=M_GONDOLA_BLACK)
    hull.rotation_euler = (0, math.radians(90), 0)
    # Plank lines along
    beveled_cube(f"{name}_pl", (10, 1.0, 0.15), bevel_offset=0.04, loc=(0, 0, 0.15),
                 parent=base, mat_=M_GONDOLA_DEEP)
    # Top deck
    beveled_cube(f"{name}_deck", (9, 0.9, 0.10), bevel_offset=0.03, loc=(0, 0, 0.35),
                 parent=base, mat_=M_GONDOLA_BLACK)
    # GOLD TRIM along edges (signature)
    beveled_cube(f"{name}_trim_l", (9.5, 0.06, 0.06), bevel_offset=0.02, loc=(0, -0.45, 0.40),
                 parent=base, mat_=M_GONDOLA_GOLD)
    beveled_cube(f"{name}_trim_r", (9.5, 0.06, 0.06), bevel_offset=0.02, loc=(0, 0.45, 0.40),
                 parent=base, mat_=M_GONDOLA_GOLD)

    # PROW IRON DECORATION (signature ferro)
    ferro_e = empty(f"{name}_ferro", (5.0, 0, 0.40), parent=base)
    # Vertical curved
    for fi in range(6):
        fz = fi * 0.40
        fx_f = math.sin(fi * 0.5) * 0.10
        cyl(f"{name}_f{fi}", r=0.05, depth=0.40, segs=8,
            loc=(fx_f, 0, fz), parent=ferro_e, mat_=M_PALACE_DARK)
    # Top S-curve (signature halberd shape)
    smooth_sphere(f"{name}_f_top", r=0.20, loc=(0.20, 0, 2.4),
                  parent=ferro_e, mat_=M_PALACE_DARK, scale=(1.5, 0.4, 0.6))
    # 6 horizontal teeth (signature Venice quarters)
    for ti in range(6):
        beveled_cube(f"{name}_ft{ti}", (0.30, 0.04, 0.12), bevel_offset=0.02,
                     loc=(0.20, 0, 0.4 + ti*0.30), parent=ferro_e, mat_=M_PALACE_DARK)

    # STERN (signature curved)
    stern_e = empty(f"{name}_stern", (-5.0, 0, 0.40), parent=base)
    # Curl up
    for si in range(4):
        sz_s = si * 0.25
        cyl(f"{name}_st{si}", r=0.08 - si*0.01, depth=0.30, segs=10,
            loc=(-si*0.15, 0, sz_s), parent=stern_e, mat_=M_GONDOLA_BLACK)
    # Curl tip
    smooth_sphere(f"{name}_st_tip", r=0.12, loc=(-0.60, 0, 1.10),
                  parent=stern_e, mat_=M_GONDOLA_BLACK)

    # PASSENGER SEATING (signature velvet)
    velvet_col = random.choice([M_GONDOLA_VELVET, M_GONDOLA_VELVET_BLUE])
    # Seat platform
    beveled_cube(f"{name}_seat", (1.8, 1.0, 0.40), bevel_offset=0.06, loc=(0.5, 0, 0.60),
                 parent=base, mat_=velvet_col)
    # Backrest
    beveled_cube(f"{name}_back", (0.30, 1.0, 0.90), bevel_offset=0.06, loc=(-0.5, 0, 0.95),
                 parent=base, mat_=velvet_col)
    # Decorative armrests
    for side in (-1, 1):
        beveled_cube(f"{name}_ar{side}", (1.8, 0.10, 0.30), bevel_offset=0.04,
                     loc=(0.5, side*0.55, 0.85), parent=base, mat_=M_GONDOLA_GOLD)
    # Gold tassels on backrest
    for tii in range(3):
        smooth_sphere(f"{name}_ts{tii}", r=0.06, loc=(-0.4, -0.3 + tii*0.3, 1.5),
                      parent=base, mat_=M_GONDOLA_GOLD)

    # FORCOLA oarlock (signature carved wooden)
    forcola_e = empty(f"{name}_for", (-3.5, 0.4, 0.6), parent=base)
    cyl(f"{name}_for_b", r=0.06, depth=0.6, segs=8, loc=(0, 0, 0.3),
        parent=forcola_e, mat_=M_VIOLIN_WOOD)
    # Curved top
    smooth_sphere(f"{name}_for_t", r=0.10, loc=(0.08, 0, 0.7),
                  parent=forcola_e, mat_=M_VIOLIN_WOOD, scale=(1.5, 0.6, 0.7))
    # OAR signature
    oar_e = empty(f"{name}_oar", (0, 0, 0.7), parent=forcola_e)
    oar_e.rotation_euler = (math.radians(-30), 0, math.radians(20))
    cyl(f"{name}_oar_s", r=0.025, depth=3.5, segs=10, loc=(0, 0, -1.75),
        parent=oar_e, mat_=M_VIOLIN_WOOD)
    # Blade
    beveled_cube(f"{name}_oar_b", (0.18, 0.04, 0.50), bevel_offset=0.04,
                 loc=(0, 0, -3.6), parent=oar_e, mat_=M_VIOLIN_WOOD)

    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "oar": oar_e}

gondolas = []
gondola_pos = [(15, 15, math.radians(0)), (-5, 18, math.radians(15)),
                (-20, 14, math.radians(-10)), (8, 12, math.radians(180))]
for i, (gx, gy, fac) in enumerate(gondola_pos):
    g = make_gondola(f"gondola{i}", (gx, gy, 0.5), scale=1.0, facing=fac)
    gondolas.append(g)

# GONDOLIERS standing on gondolas (signature)
def make_gondolier(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Striped shirt (signature)
    smooth_cone(f"{name}_shirt", r1=0.28*scale, r2=0.30*scale, depth=0.7*scale, segs=14,
                loc=(0, 0, 1.30*scale), parent=base, mat_=M_STRIPE_WHITE)
    # Horizontal stripes (signature)
    for si in range(7):
        cyl(f"{name}_str{si}", r=0.31*scale, depth=0.05*scale, segs=14,
            loc=(0, 0, 1.00*scale + si*0.10*scale), parent=base, mat_=M_STRIPE_BLACK)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.10*scale, depth=0.95*scale, segs=10,
            loc=(side*0.13*scale, 0, 0.47*scale), parent=base, mat_=M_STRIPE_BLACK)
        # Shoes
        beveled_cube(f"{name}_sh{side}", (0.10*scale, 0.20*scale, 0.05*scale), bevel_offset=0.02,
                     loc=(side*0.13*scale, 0, 0), parent=base, mat_=M_STRIPE_BLACK)
    # Red sash (signature)
    cyl(f"{name}_sash", r=0.32*scale, depth=0.10*scale, segs=14, loc=(0, 0, 1.05*scale),
        parent=base, mat_=M_STRIPE_RED)
    # Arms (one holding oar)
    sh_r = empty(f"{name}_sh_r", (0.30*scale, 0.20*scale, 1.70*scale), parent=base)
    sh_r.rotation_euler = (math.radians(-70), 0, math.radians(-30))
    cyl(f"{name}_uarm_R", r=0.06*scale, depth=0.40*scale, segs=10, loc=(0, 0, -0.20*scale),
        parent=sh_r, mat_=M_STRIPE_WHITE)
    cyl(f"{name}_fa_R", r=0.05*scale, depth=0.35*scale, segs=10, loc=(0, 0, -0.55*scale),
        parent=sh_r, mat_=M_SKIN_PALE_V)
    sh_l = empty(f"{name}_sh_l", (-0.30*scale, 0, 1.70*scale), parent=base)
    sh_l.rotation_euler = (math.radians(-40), 0, math.radians(20))
    cyl(f"{name}_uarm_L", r=0.06*scale, depth=0.40*scale, segs=10, loc=(0, 0, -0.20*scale),
        parent=sh_l, mat_=M_STRIPE_WHITE)
    cyl(f"{name}_fa_L", r=0.05*scale, depth=0.35*scale, segs=10, loc=(0, 0, -0.55*scale),
        parent=sh_l, mat_=M_SKIN_PALE_V)
    # Head
    head_g_e = empty(f"{name}_he", (0, 0, 2.0*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_g_e, mat_=M_SKIN_PALE_V)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale, loc=(side*0.06*scale, -0.15*scale, 0.03*scale),
                      parent=head_g_e, mat_=M_EYE_DARK_V)
    # Hair
    for hi in range(8):
        ha = (hi / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.05*scale,
                      loc=(math.cos(ha)*0.14*scale, math.sin(ha)*0.10*scale, 0.10*scale),
                      parent=head_g_e, mat_=M_HAIR_BLACK_V)
    # STRAW HAT signature (boater)
    hat_g_e = empty(f"{name}_hat", (0, 0, 0.20*scale), parent=head_g_e)
    cyl(f"{name}_hat_brim", r=0.30*scale, depth=0.04*scale, segs=18, loc=(0, 0, 0),
        parent=hat_g_e, mat_=M_HAT_STRAW)
    cyl(f"{name}_hat_c", r=0.22*scale, depth=0.10*scale, segs=18, loc=(0, 0, 0.06*scale),
        parent=hat_g_e, mat_=M_HAT_STRAW)
    # Red band
    cyl(f"{name}_hat_band", r=0.23*scale, depth=0.04*scale, segs=18, loc=(0, 0, 0.04*scale),
        parent=hat_g_e, mat_=M_HAT_BAND)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_g_e}

gondoliers = []
# Place a gondolier on each gondola
for gi, g in enumerate(gondolas):
    g_loc = g["root"].location
    g_fac = g["root"].rotation_euler.z
    # Gondolier at stern
    stern_offset_x = math.cos(g_fac) * -4
    stern_offset_y = math.sin(g_fac) * -4
    go = make_gondolier(f"gondolier{gi}", (g_loc.x + stern_offset_x, g_loc.y + stern_offset_y, 0.8),
                        scale=1.0, facing=g_fac)
    gondoliers.append(go)

# ============ 6 MASKED CARNIVAL FIGURES (signature baroque) ============
def make_masked_figure(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    dress_col = random.choice(DRESS_COLORS)
    mask_col = random.choice(MASK_COLORS)
    # LONG BAROQUE DRESS (signature voluminous)
    smooth_cone(f"{name}_skirt", r1=0.75*scale, r2=0.35*scale, depth=1.7*scale, segs=20,
                loc=(0, 0, 0.85*scale), parent=base, mat_=dress_col)
    # Multiple layered ruffles (signature)
    for li in range(5):
        ly = 0.20 + li * 0.30
        rad = 0.78 - li * 0.05
        cyl(f"{name}_ruf{li}", r=rad*scale, depth=0.08*scale, segs=20, loc=(0, 0, ly*scale),
            parent=base, mat_=dress_col)
        # Gold trim alternating
        if li % 2 == 0:
            cyl(f"{name}_trim{li}", r=(rad + 0.03)*scale, depth=0.05*scale, segs=20,
                loc=(0, 0, ly*scale + 0.04*scale), parent=base, mat_=M_PALACE_GOLD)
    # Corset top (signature tight)
    smooth_cone(f"{name}_corset", r1=0.30*scale, r2=0.32*scale, depth=0.6*scale, segs=14,
                loc=(0, 0, 1.85*scale), parent=base, mat_=dress_col)
    # Decorative lace front
    for li in range(5):
        cyl(f"{name}_lc{li}", r=0.01*scale, depth=0.06*scale, segs=6,
            loc=(0, -0.30*scale, 1.65*scale + li*0.10*scale),
            parent=base, mat_=M_FEATHER_GO).rotation_euler = (math.radians(90), 0, 0)
    # PUFFY SLEEVES (signature baroque)
    for side in (-1, 1):
        # Shoulder puff
        smooth_sphere(f"{name}_puff{side}", r=0.18*scale, loc=(side*0.35*scale, 0, 2.10*scale),
                      parent=base, mat_=dress_col, scale=(1, 0.85, 1))
        # Sleeve
        sleeve_e = empty(f"{name}_sl{side}_e", (side*0.32*scale, 0, 2.0*scale), parent=base)
        sleeve_e.rotation_euler = (math.radians(-60), 0, math.radians(side*-20))
        smooth_cone(f"{name}_sl{side}", r1=0.10*scale, r2=0.15*scale, depth=0.50*scale, segs=12,
                    loc=(0, 0, -0.25*scale), parent=sleeve_e, mat_=M_STRIPE_WHITE)
        # Lace cuff
        cyl(f"{name}_cuf{side}", r=0.16*scale, depth=0.08*scale, segs=14, loc=(0, 0, -0.55*scale),
            parent=sleeve_e, mat_=M_PALACE_GOLD)
        # Hand
        smooth_sphere(f"{name}_h{side}", r=0.06*scale, loc=(0, 0, -0.65*scale),
                      parent=sleeve_e, mat_=M_SKIN_PALE_V)
    # Collar lace
    cyl(f"{name}_collar", r=0.33*scale, depth=0.10*scale, segs=14, loc=(0, 0, 2.20*scale),
        parent=base, mat_=M_STRIPE_WHITE)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 2.45*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN_PALE_V)
    # CARNIVAL MASK signature (covering face)
    mask_e = empty(f"{name}_mask", (0, -0.06*scale, 0.05*scale), parent=head_m_e)
    # Main mask shape
    beveled_cube(f"{name}_mk_b", (0.30*scale, 0.08*scale, 0.30*scale), bevel_offset=0.10,
                 loc=(0, -0.10*scale, 0), parent=mask_e, mat_=mask_col)
    # Forehead extension
    smooth_sphere(f"{name}_mk_fh", r=0.18*scale, loc=(0, -0.12*scale, 0.10*scale),
                  parent=mask_e, mat_=mask_col, scale=(1, 0.4, 0.7))
    # Cheek extensions
    for side in (-1, 1):
        smooth_sphere(f"{name}_mk_ck{side}", r=0.10*scale,
                      loc=(side*0.15*scale, -0.12*scale, -0.05*scale),
                      parent=mask_e, mat_=mask_col, scale=(1, 0.3, 1))
    # Eye holes (signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_mk_eh{side}", r=0.04*scale,
                      loc=(side*0.08*scale, -0.18*scale, 0.03*scale),
                      parent=mask_e, mat_=M_EYE_DARK_V)
    # Gold decorations on mask
    for di in range(6):
        da = (di / 6.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_mk_d{di}", r=0.02*scale,
                      loc=(math.sin(da)*0.20*scale, -0.18*scale, 0.10*scale + math.cos(da)*0.10*scale),
                      parent=mask_e, mat_=M_PALACE_GOLD)
    # Long beak (Colombina with beak or Bauta)
    if random.random() > 0.5:
        # Long pointed beak signature
        smooth_cone(f"{name}_beak", r1=0.08*scale, r2=0.005*scale, depth=0.50*scale, segs=10,
                    loc=(0, -0.30*scale, -0.10*scale), parent=mask_e,
                    mat_=mask_col).rotation_euler = (math.radians(-110), 0, 0)
    # FEATHER PLUMES (signature elaborate)
    plume_e = empty(f"{name}_plume", (0, 0, 0.25*scale), parent=head_m_e)
    for fi in range(12):
        fa = (fi / 12.0) * math.pi - math.pi/2
        fl = random.uniform(0.4, 0.8)
        feat_col = random.choice(FEATHER_VENICE)
        feat = smooth_cone(f"{name}_pf{fi}", r1=0.04*scale, r2=0.005*scale, depth=fl*scale, segs=8,
                          loc=(math.sin(fa)*0.18*scale, 0, fl*scale/2),
                          parent=plume_e, mat_=feat_col)
        feat.rotation_euler = (math.radians(-15), 0, fa)
    # Lips red
    beveled_cube(f"{name}_lips", (0.08*scale, 0.04*scale, 0.025*scale), bevel_offset=0.005,
                 loc=(0, -0.18*scale, -0.18*scale), parent=head_m_e, mat_=M_LIPS_DARK)
    # Long flowing hair behind
    hair_col = random.choice([M_HAIR_BLACK_V, M_HAIR_BROWN_V, M_HAIR_BLOND_V])
    for hi in range(12):
        ha = random.uniform(0, math.pi*2)
        hl_h = random.uniform(0.30, 0.60)
        beveled_cube(f"{name}_hr{hi}", (0.05*scale, 0.07*scale, hl_h*scale), bevel_offset=0.01,
                     loc=(math.cos(ha)*0.16*scale, math.sin(ha)*0.10*scale + 0.08*scale, -hl_h*scale/2),
                     parent=head_m_e, mat_=hair_col)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_m_e}

masked_figures = []
mf_pos = [(15, -3, math.radians(45)), (10, -8, math.radians(0)),
           (5, -3, math.radians(-30)), (-15, -3, math.radians(60)),
           (-10, -8, math.radians(120)), (-5, -3, math.radians(-60))]
for i, (mx, my, fac) in enumerate(mf_pos):
    m = make_masked_figure(f"masked{i}", (mx, my, 0), scale=1.0, facing=fac)
    masked_figures.append(m)

# ============ 4 MUSICIANS (signature accordion + violin) ============
def make_musician_v(name, loc, instrument, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body baroque outfit
    smooth_cone(f"{name}_torso", r1=0.32*scale, r2=0.34*scale, depth=0.6*scale, segs=14,
                loc=(0, 0, 1.30*scale), parent=base, mat_=M_DRESS_VENETIAN_RED)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.11*scale, depth=0.95*scale, segs=10,
            loc=(side*0.13*scale, 0, 0.47*scale), parent=base, mat_=M_STRIPE_BLACK)
    # Mask half (signature smaller for musician)
    head_v_e = empty(f"{name}_he", (0, 0, 1.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_v_e, mat_=M_SKIN_PALE_V)
    # Smaller mask (signature Colombina half-mask)
    beveled_cube(f"{name}_mk", (0.30*scale, 0.08*scale, 0.20*scale), bevel_offset=0.06,
                 loc=(0, -0.16*scale, 0.05*scale), parent=head_v_e, mat_=M_MASK_GOLD)
    # Tricorn hat
    cyl(f"{name}_tri", r=0.30*scale, depth=0.04*scale, segs=18, loc=(0, 0, 0.20*scale),
        parent=head_v_e, mat_=M_STRIPE_BLACK)
    cyl(f"{name}_tri_c", r=0.20*scale, depth=0.15*scale, segs=14, loc=(0, 0, 0.26*scale),
        parent=head_v_e, mat_=M_STRIPE_BLACK)
    # Feather on hat
    smooth_cone(f"{name}_tf", r1=0.04*scale, r2=0.005*scale, depth=0.30*scale, segs=8,
                loc=(0.18*scale, -0.05*scale, 0.30*scale), parent=head_v_e,
                mat_=random.choice(FEATHER_VENICE)).rotation_euler = (math.radians(20), 0, math.radians(30))
    # Arms holding instrument
    inst_e = empty(f"{name}_inst", (0, -0.30*scale, 1.40*scale), parent=base)
    if instrument == "accordion":
        # Accordion body (signature bellows)
        beveled_cube(f"{name}_acc_b", (0.60, 0.40, 0.50), bevel_offset=0.06,
                     loc=(0, 0, 0), parent=inst_e, mat_=M_ACCORDION_RED)
        # Bellows folds
        for fi in range(8):
            beveled_cube(f"{name}_acc_f{fi}", (0.55, 0.40, 0.05), bevel_offset=0.01,
                         loc=(-0.25 + fi*0.07, 0, 0), parent=inst_e, mat_=M_ACCORDION_BLACK)
        # Keyboards on side
        for side in (-1, 1):
            beveled_cube(f"{name}_acc_k{side}", (0.06, 0.30, 0.40), bevel_offset=0.03,
                         loc=(side*0.32, 0, 0), parent=inst_e, mat_=M_STRIPE_WHITE)
    elif instrument == "violin":
        # Violin body
        smooth_sphere(f"{name}_vio_b", r=0.18, segs=18, rings=12, loc=(0, 0, 0),
                      parent=inst_e, mat_=M_VIOLIN_WOOD, scale=(0.8, 0.30, 1.2))
        # Neck
        cyl(f"{name}_vio_n", r=0.025, depth=0.40, segs=10, loc=(0, -0.10, 0.30),
            parent=inst_e, mat_=M_VIOLIN_DARK)
        # Bow
        bow_e = empty(f"{name}_bow", (0.30, -0.10, 0), parent=base)
        bow_e.rotation_euler = (0, math.radians(20), math.radians(-90))
        cyl(f"{name}_bow_s", r=0.012, depth=0.60, segs=8, loc=(0, 0, 0),
            parent=bow_e, mat_=M_VIOLIN_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "inst": inst_e, "he": head_v_e}

musicians = []
mus_pos = [("accordion", -20, 5), ("violin", -18, 8),
            ("accordion", 18, 5), ("violin", 20, 8)]
for i, (inst, mx, my) in enumerate(mus_pos):
    m = make_musician_v(f"mus_v{i}", (mx, my, 0), instrument=inst, scale=1.0,
                        facing=math.radians(0))
    musicians.append(m)

# ============ PIGEONS (signature St Mark's pigeons) ============
pigeons = []
for pi in range(20):
    pa = random.uniform(0, math.pi*2)
    pr = random.uniform(5, 30)
    px_p = math.cos(pa) * pr
    py_p = math.sin(pa) * pr - 5
    pz_p = random.uniform(0.5, 12)
    p_e = empty(f"pigeon{pi}", (px_p, py_p, pz_p))
    # Body
    smooth_sphere(f"pg_b{pi}", r=0.12, segs=14, rings=10, loc=(0, 0, 0),
                  parent=p_e, mat_=M_PIGEON_GREY, scale=(1.5, 1, 1))
    # Head
    smooth_sphere(f"pg_h{pi}", r=0.08, loc=(0.15, 0, 0.06), parent=p_e, mat_=M_PIGEON_GREY)
    # Neck purple iridescent
    smooth_sphere(f"pg_n{pi}", r=0.08, loc=(0.10, 0, -0.05), parent=p_e, mat_=M_PIGEON_NECK)
    # Beak
    smooth_cone(f"pg_bk{pi}", r1=0.025, r2=0.005, depth=0.06, segs=6,
                loc=(0.22, 0, 0.05), parent=p_e, mat_=M_MASK_BLACK)
    # Wings
    for side in (-1, 1):
        beveled_cube(f"pg_w{pi}_{side}", (0.06, 0.18, 0.05), bevel_offset=0.01,
                     loc=(0, side*0.08, 0), parent=p_e, mat_=M_PIGEON_DARK)
    # Feet
    for side in (-1, 1):
        cyl(f"pg_f{pi}_{side}", r=0.012, depth=0.04, segs=6, loc=(0, side*0.04, -0.12),
            parent=p_e, mat_=M_MASK_RED)
    p_e["_phase"] = random.uniform(0, math.pi*2)
    p_e["_speed"] = random.uniform(0.5, 1.5)
    pigeons.append(p_e)

# ============================================================
# ⭐ 600 MASK FEATHERS + 400 GOLD CONFETTI (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
feathers_part = []
for i in range(600):
    px = random.uniform(-70, 70)
    py = random.uniform(-70, 70)
    pz = random.uniform(1, 18)
    feat_col = random.choice(FEATHER_VENICE)
    # Feather shape (elongated)
    f_obj = beveled_cube(f"feat{i}", (0.04, 0.06, 0.20),
                         bevel_offset=0.02, loc=(px, py, pz), mat_=feat_col)
    f_obj["_phase"] = random.uniform(0, math.pi*2)
    f_obj["_base_x"] = px; f_obj["_base_y"] = py; f_obj["_base_z"] = pz
    f_obj["_amp_x"] = random.uniform(0.8, 2.0)
    f_obj["_amp_y"] = random.uniform(0.8, 2.0)
    f_obj["_amp_z"] = random.uniform(0.5, 1.5)
    f_obj["_speed"] = random.uniform(0.4, 1.0)
    feathers_part.append(f_obj)

# 400 gold confetti
confetti = []
for i in range(400):
    px = random.uniform(-50, 50)
    py = random.uniform(-50, 50)
    pz = random.uniform(2, 18)
    c_obj = beveled_cube(f"conf{i}", (random.uniform(0.06, 0.10),
                                        random.uniform(0.02, 0.04),
                                        random.uniform(0.10, 0.16)),
                         bevel_offset=0.02, loc=(px, py, pz),
                         mat_=random.choice(CONFETTI_COLS))
    c_obj["_phase"] = random.uniform(0, math.pi*2)
    c_obj["_base_x"] = px; c_obj["_base_y"] = py; c_obj["_base_z"] = pz
    c_obj["_amp_x"] = random.uniform(1.0, 2.5)
    c_obj["_amp_y"] = random.uniform(1.0, 2.5)
    c_obj["_speed"] = random.uniform(0.5, 1.2)
    c_obj["_fall"] = random.uniform(1.5, 3.0)
    confetti.append(c_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Clouds drift
for ci in range(20):
    cloud = bpy.data.objects.get(f"cloud{ci}")
    if cloud is None: continue
    phase = cloud["_phase"]
    bx_c = cloud.location.x; by_c = cloud.location.y
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        cloud.location.x = bx_c + math.sin(t * 0.3 + phase) * 2.0
        cloud.location.y = by_c + math.cos(t * 0.3 + phase) * 2.0
        cloud.keyframe_insert("location", frame=f)

# Gondolas glide slowly
for g in gondolas:
    phase = g["root"]["_phase"]
    bx_g = g["root"].location.x; by_g = g["root"].location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        g["root"].location.x = bx_g + math.sin(t * 0.4 + phase) * 0.8
        g["root"].location.y = by_g + math.cos(t * 0.4 + phase) * 0.3
        g["root"].location.z = 0.5 + math.sin(t * 1.0 + phase) * 0.08
        g["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     g["root"].rotation_euler.z)
        g["root"].keyframe_insert("location", frame=f)
        g["root"].keyframe_insert("rotation_euler", frame=f)
        # Oar rowing motion
        g["oar"].rotation_euler = (math.radians(-30) + math.sin(t * 1.5 + phase) * math.radians(20),
                                    0, math.radians(20))
        g["oar"].keyframe_insert("rotation_euler", frame=f)

# Gondoliers row pose with body sway
for go in gondoliers:
    phase = go["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        go["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                       go["root"].rotation_euler.z)
        go["root"].keyframe_insert("rotation_euler", frame=f)
        go["he"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(10))
        go["he"].keyframe_insert("rotation_euler", frame=f)

# Masked figures elegant walk + head turn
for m in masked_figures:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(3),
                                     math.cos(t * 1.0 + phase) * math.radians(3),
                                     m["root"].rotation_euler.z)
        m["root"].location.z = abs(math.sin(t * 1.5 + phase)) * 0.15
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["root"].keyframe_insert("location", frame=f)
        m["he"].rotation_euler = (0, 0, math.sin(t * 1.2 + phase) * math.radians(25))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Musicians play
for mu in musicians:
    phase = mu["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        mu["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(4), 0,
                                       mu["root"].rotation_euler.z)
        mu["root"].keyframe_insert("rotation_euler", frame=f)
        # Accordion bellows expand/contract
        sc_i = 1 + math.sin(t * 4.0 + phase) * 0.15
        mu["inst"].scale = (sc_i, 1, 1)
        mu["inst"].keyframe_insert("scale", frame=f)
        mu["he"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(6), 0,
                                     math.cos(t * 2.0 + phase) * math.radians(8))
        mu["he"].keyframe_insert("rotation_euler", frame=f)

# Pigeons fly + walk
for p in pigeons:
    phase = p["_phase"]; speed = p["_speed"]
    bx_p = p.location.x; by_p = p.location.y; bz_p = p.location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        p.location.x = bx_p + math.sin(t * speed + phase) * 1.5
        p.location.y = by_p + math.cos(t * speed + phase) * 1.5
        p.location.z = bz_p + math.sin(t * speed * 1.5 + phase) * 0.3
        p.keyframe_insert("location", frame=f)

# 600 feathers float drift
for ft in feathers_part:
    phase = ft["_phase"]; speed = ft["_speed"]
    bx, by, bz = ft["_base_x"], ft["_base_y"], ft["_base_z"]
    ax, ay, az = ft["_amp_x"], ft["_amp_y"], ft["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase) - (t * 0.5) % 5
        ft.location = (x, y, max(0.5, z))
        ft.rotation_euler = (t * 2.5 + phase, t * 2.0 + phase, t * 3.0 + phase)
        ft.keyframe_insert("location", frame=f)
        ft.keyframe_insert("rotation_euler", frame=f)

# 400 confetti tumbling fall
for c in confetti:
    phase = c["_phase"]; speed = c["_speed"]; fall = c["_fall"]
    bx, by, bz = c["_base_x"], c["_base_y"], c["_base_z"]
    ax, ay = c["_amp_x"], c["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.3)
        if z < 0.3: z = bz
        c.location = (x, y, max(0.2, z))
        c.rotation_euler = (t * 4.0 + phase, t * 3.0 + phase, t * 5.0 + phase)
        c.keyframe_insert("location", frame=f)
        c.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_venice_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_venetian_carnival_gondola_masks] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_venetian_carnival_gondola_masks] Doge's Palace gothic + St Mark's 5 domes + 4 bronze horses + Campanile + Bridge of Sighs + 8 buildings + 4 black gondolas signature + 4 gondoliers striped + 6 masked figures baroque + 4 musicians + 20 pigeons + 600 feathers + 400 confetti")
print("⭐ FIXES: 1 ground + 600 mask feathers + 400 gold confetti (signature Venice thematic mandatory) ⭐")
