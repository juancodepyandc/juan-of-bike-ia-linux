"""
proc_moroccan_marrakech_souk_medina.py — 257e procédural AuroraIA (122e qualité)
Marrakech medina night: 12 souk stalls + Koutoubia minaret + horseshoe arch + 6 merchants djellaba + 4 women caftans + 4 musicians + camel + cats + tagines + 600 lanterns + 400 spices
FIXES : 1 ground + 600 blue lanterns + 400 spices (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB257)

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

# Night sky
M_SKY = mat("sky", (0.05, 0.06, 0.15, 1.0), 0.0, 0.7, emission=(0.06,0.08,0.18), emission_strength=0.7)
M_STAR_M = mat("star", (1.0, 0.95, 0.85, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.85), emission_strength=10.0)
M_MOON_M = mat("moon", (0.95, 0.92, 0.85, 1.0), 0.0, 0.20, emission=(0.92,0.88,0.82), emission_strength=4.5)

# Ground
M_STONE_PAVE = mat("stone", (0.62, 0.42, 0.25, 1.0), 0.0, 0.85, emission=(0.58,0.42,0.25), emission_strength=0.5)
M_STONE_DARK_M = mat("stone_d", (0.42, 0.28, 0.15, 1.0), 0.0, 0.85)
M_STONE_TILE_M = mat("stone_t", (0.78, 0.55, 0.30, 1.0), 0.0, 0.80, emission=(0.72,0.52,0.30), emission_strength=0.5)

# Walls medina
M_WALL_OCHRE = mat("wall_o", (0.85, 0.55, 0.32, 1.0), 0.0, 0.75, emission=(0.78,0.52,0.32), emission_strength=0.5)
M_WALL_RED = mat("wall_r", (0.78, 0.32, 0.20, 1.0), 0.0, 0.80, emission=(0.72,0.32,0.20), emission_strength=0.5)
M_WALL_DARK = mat("wall_d", (0.42, 0.20, 0.10, 1.0), 0.0, 0.85)

# Wood
M_WOOD_M = mat("wood", (0.42, 0.25, 0.12, 1.0), 0.0, 0.75, emission=(0.40,0.25,0.12), emission_strength=0.4)
M_WOOD_DARK_M = mat("wood_d", (0.25, 0.15, 0.08, 1.0), 0.0, 0.85)

# KOUTOUBIA MINARET (signature ochre)
M_MINARET = mat("minaret", (0.85, 0.50, 0.28, 1.0), 0.0, 0.75, emission=(0.78,0.48,0.28), emission_strength=0.7)
M_MINARET_ZELLIGE = mat("zel", (0.20, 0.55, 0.65, 1.0), 0.4, 0.30, emission=(0.20,0.55,0.65), emission_strength=1.5)
M_MINARET_GOLD = mat("min_g", (1.0, 0.85, 0.30, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.30), emission_strength=2.5)

# Lanterns BLUE (signature Moroccan)
M_LANTERN_BLUE = mat("lan_b", (0.20, 0.55, 0.95, 1.0), 0.0, 0.20, emission=(0.20,0.55,0.95), emission_strength=8.0, alpha=0.85)
M_LANTERN_GOLD = mat("lan_g", (1.0, 0.85, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.30), emission_strength=9.0, alpha=0.85)
M_LANTERN_RED = mat("lan_r", (1.0, 0.30, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.30,0.30), emission_strength=8.0, alpha=0.85)
M_LANTERN_TURQUOISE = mat("lan_t", (0.30, 0.85, 0.85, 1.0), 0.0, 0.20, emission=(0.30,0.85,0.85), emission_strength=8.0, alpha=0.85)
LANTERN_COLORS = [M_LANTERN_BLUE, M_LANTERN_GOLD, M_LANTERN_RED, M_LANTERN_TURQUOISE]
M_LANTERN_FRAME = mat("lan_f", (0.18, 0.12, 0.06, 1.0), 0.7, 0.40, emission=(0.16,0.12,0.06), emission_strength=0.6)

# Spices (vivid pyramids)
M_SPICE_RED = mat("sp_r", (0.95, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.92,0.15,0.15), emission_strength=1.5)
M_SPICE_ORANGE = mat("sp_o", (1.0, 0.55, 0.18, 1.0), 0.0, 0.55, emission=(0.95,0.55,0.18), emission_strength=1.5)
M_SPICE_YELLOW = mat("sp_y", (1.0, 0.92, 0.20, 1.0), 0.0, 0.55, emission=(0.95,0.88,0.20), emission_strength=1.5)
M_SPICE_GREEN = mat("sp_g", (0.30, 0.75, 0.30, 1.0), 0.0, 0.55, emission=(0.30,0.72,0.30), emission_strength=1.2)
M_SPICE_BROWN = mat("sp_br", (0.42, 0.25, 0.12, 1.0), 0.0, 0.70)
M_SPICE_PURPLE = mat("sp_p", (0.55, 0.20, 0.62, 1.0), 0.0, 0.55, emission=(0.52,0.20,0.60), emission_strength=1.3)
M_SPICE_PINK = mat("sp_pk", (0.92, 0.55, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.52,0.62), emission_strength=1.4)
M_SPICE_WHITE = mat("sp_w", (0.92, 0.88, 0.78, 1.0), 0.0, 0.65)
SPICE_COLORS = [M_SPICE_RED, M_SPICE_ORANGE, M_SPICE_YELLOW, M_SPICE_GREEN,
                M_SPICE_BROWN, M_SPICE_PURPLE, M_SPICE_PINK, M_SPICE_WHITE]

# Carpets/rugs (signature colorful Berber)
M_RUG_RED = mat("rg_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.75, emission=(0.72,0.18,0.18), emission_strength=0.5)
M_RUG_BLUE = mat("rg_b", (0.20, 0.42, 0.78, 1.0), 0.0, 0.75, emission=(0.18,0.42,0.75), emission_strength=0.5)
M_RUG_ORANGE = mat("rg_o", (0.95, 0.55, 0.18, 1.0), 0.0, 0.75, emission=(0.92,0.55,0.18), emission_strength=0.5)
M_RUG_TURQUOISE = mat("rg_t", (0.30, 0.78, 0.78, 1.0), 0.0, 0.75, emission=(0.30,0.75,0.75), emission_strength=0.5)
M_RUG_PURPLE = mat("rg_p", (0.55, 0.25, 0.78, 1.0), 0.0, 0.75, emission=(0.52,0.25,0.75), emission_strength=0.5)
RUG_COLORS = [M_RUG_RED, M_RUG_BLUE, M_RUG_ORANGE, M_RUG_TURQUOISE, M_RUG_PURPLE]

# Skin
M_SKIN_ARAB = mat("skin", (0.78, 0.55, 0.38, 1.0), 0.0, 0.55, emission=(0.72,0.52,0.38), emission_strength=0.4)

# Djellaba/Caftan colors
M_DJELLABA_BROWN = mat("dj_b", (0.42, 0.28, 0.15, 1.0), 0.0, 0.80, emission=(0.40,0.28,0.15), emission_strength=0.4)
M_DJELLABA_CREAM = mat("dj_c", (0.78, 0.65, 0.45, 1.0), 0.0, 0.75, emission=(0.72,0.62,0.42), emission_strength=0.5)
M_DJELLABA_GREEN = mat("dj_g", (0.18, 0.42, 0.25, 1.0), 0.0, 0.75, emission=(0.18,0.40,0.25), emission_strength=0.5)
M_DJELLABA_BLUE = mat("dj_blue", (0.18, 0.32, 0.62, 1.0), 0.0, 0.75, emission=(0.18,0.30,0.60), emission_strength=0.5)
DJELLABA_COLORS = [M_DJELLABA_BROWN, M_DJELLABA_CREAM, M_DJELLABA_GREEN, M_DJELLABA_BLUE]

# Caftan vibrant
M_CAFTAN_PINK = mat("cf_p", (0.95, 0.45, 0.65, 1.0), 0.0, 0.55, emission=(0.92,0.45,0.62), emission_strength=0.7)
M_CAFTAN_GOLD = mat("cf_g", (0.92, 0.78, 0.32, 1.0), 0.5, 0.30, emission=(0.88,0.75,0.32), emission_strength=1.2)
M_CAFTAN_PURPLE = mat("cf_pu", (0.62, 0.30, 0.78, 1.0), 0.0, 0.55, emission=(0.60,0.30,0.75), emission_strength=0.7)
M_CAFTAN_TEAL = mat("cf_t", (0.18, 0.55, 0.55, 1.0), 0.0, 0.55, emission=(0.18,0.52,0.52), emission_strength=0.7)
CAFTAN_COLORS = [M_CAFTAN_PINK, M_CAFTAN_GOLD, M_CAFTAN_PURPLE, M_CAFTAN_TEAL]

# Hair / beard
M_HAIR_BLACK_M = mat("h_bk", (0.10, 0.06, 0.04, 1.0), 0.0, 0.55)
M_BEARD_DARK = mat("bd", (0.30, 0.20, 0.12, 1.0), 0.0, 0.65)
M_HIJAB_BLACK = mat("hj_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.70)
M_HIJAB_BLUE = mat("hj_b", (0.20, 0.32, 0.62, 1.0), 0.0, 0.70)

# Tagine (signature conical)
M_TAGINE_CLAY = mat("tag", (0.78, 0.35, 0.18, 1.0), 0.0, 0.75, emission=(0.72,0.35,0.18), emission_strength=0.5)
M_TAGINE_DARK_M = mat("tag_d", (0.42, 0.22, 0.10, 1.0), 0.0, 0.85)
M_TAGINE_STEAM = mat("steam", (0.92, 0.92, 0.95, 1.0), 0.0, 0.40, emission=(0.88,0.88,0.92), emission_strength=2.0, alpha=0.45)

# Brass lamps Berber
M_BRASS = mat("brass", (0.92, 0.65, 0.20, 1.0), 0.9, 0.20, emission=(0.88,0.62,0.20), emission_strength=1.8)
M_BRASS_DARK = mat("brass_d", (0.55, 0.40, 0.15, 1.0), 0.85, 0.35)
M_LAMP_GLOW_M = mat("glow", (1.0, 0.85, 0.45, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.45), emission_strength=6.0, alpha=0.85)

# Camel
M_CAMEL_T = mat("camel", (0.85, 0.62, 0.32, 1.0), 0.0, 0.75, emission=(0.78,0.58,0.32), emission_strength=0.4)
M_CAMEL_D = mat("camel_d", (0.55, 0.40, 0.20, 1.0), 0.0, 0.85)
M_HARNESS_M = mat("harn", (0.78, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.72,0.18,0.18), emission_strength=0.5)

# Cats
M_CAT_GREY = mat("cat_g", (0.55, 0.50, 0.45, 1.0), 0.0, 0.75, emission=(0.50,0.48,0.42), emission_strength=0.4)
M_CAT_ORANGE = mat("cat_o", (0.92, 0.55, 0.25, 1.0), 0.0, 0.75, emission=(0.88,0.52,0.25), emission_strength=0.5)
M_CAT_WHITE = mat("cat_w", (0.92, 0.88, 0.82, 1.0), 0.0, 0.75)

# Guembri (Moroccan bass lute)
M_GUEMBRI = mat("gb", (0.45, 0.28, 0.15, 1.0), 0.0, 0.55, emission=(0.42,0.28,0.15), emission_strength=0.5)
M_GUEMBRI_STRING = mat("gb_s", (0.85, 0.78, 0.55, 1.0), 0.0, 0.55)
M_DARBOUKA = mat("darb", (0.85, 0.45, 0.18, 1.0), 0.0, 0.65, emission=(0.80,0.42,0.18), emission_strength=0.5)
M_DARBOUKA_SKIN = mat("darb_s", (0.92, 0.78, 0.55, 1.0), 0.0, 0.55, emission=(0.85,0.72,0.52), emission_strength=0.5)

# Eye
M_EYE_DARK_M = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS_M = mat("lips", (0.55, 0.18, 0.20, 1.0), 0.0, 0.40)

# Babouche slippers
M_BABOUCHE = mat("bab", (0.95, 0.78, 0.30, 1.0), 0.5, 0.30, emission=(0.92,0.75,0.30), emission_strength=0.8)

# Spice particles
M_SPICE_DUST = mat("sd", (1.0, 0.65, 0.18, 1.0), 0.0, 0.30, emission=(0.95,0.65,0.18), emission_strength=3.0, alpha=0.55)

# Tagine food
M_FOOD_VEG = mat("veg", (0.85, 0.42, 0.18, 1.0), 0.0, 0.55, emission=(0.80,0.42,0.18), emission_strength=0.5)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Moon
moon = smooth_sphere("moon", r=3.5, segs=24, rings=18, loc=(60, 80, 60), mat_=M_MOON_M)
# Stars
for si in range(120):
    sa = random.uniform(0, math.pi*2); sr = random.uniform(60, 200)
    sh = random.uniform(25, 90)
    smooth_sphere(f"star{si}", r=random.uniform(0.10, 0.25), segs=8, rings=6,
                  loc=(sr*math.cos(sa), sr*math.sin(sa), sh), mat_=M_STAR_M)

# ============ ONE clean stone pavement ground ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_STONE_PAVE)
# Tile pattern
for ti in range(30):
    for tj in range(30):
        tx_g = -45 + ti * 3; ty_g = -45 + tj * 3
        tcol = M_STONE_TILE_M if (ti + tj) % 2 == 0 else M_STONE_PAVE
        beveled_cube(f"tile{ti}_{tj}", (2.8, 2.8, 0.06), bevel_offset=0.02,
                     loc=(tx_g, ty_g, 0.12), mat_=tcol)
# Edge cobblestones
for bi in range(40):
    smooth_sphere(f"cob{bi}", r=0.30, segs=12, rings=10,
                  loc=(random.uniform(-60, 60), random.uniform(-60, 60), 0.30),
                  mat_=M_STONE_DARK_M, scale=(1.5, 1.4, 0.4))

# ============ KOUTOUBIA MINARET (signature tower) ============
minaret_e = empty("minaret", loc=(0, 35, 0))
# Square base
beveled_cube("min_base", (8, 8, 3), bevel_offset=0.10, loc=(0, 0, 1.5),
             parent=minaret_e, mat_=M_MINARET)
# Main tower 4 levels
for li in range(5):
    lz = 3 + li * 4
    lw = 6 - li * 0.3
    beveled_cube(f"min_l{li}", (lw, lw, 4), bevel_offset=0.15, loc=(0, 0, lz + 2),
                 parent=minaret_e, mat_=M_MINARET)
    # Decorative band signature
    cyl(f"min_bd{li}", r=0.10, depth=lw+0.5, segs=8, loc=(0, lw/2 + 0.10, lz + 4),
        parent=minaret_e, mat_=M_MINARET_ZELLIGE).rotation_euler = (0, math.radians(90), 0)
    # Multifoil arches (signature horseshoe)
    for side in (-1, 1):
        beveled_cube(f"min_a{li}_{side}", (1.0, 0.6, 1.5), bevel_offset=0.20,
                     loc=(side*lw/2*0.6, lw/2 + 0.10, lz + 1.5), parent=minaret_e,
                     mat_=M_MINARET_ZELLIGE)
        # Smaller horseshoe shape
        smooth_sphere(f"min_ah{li}_{side}", r=0.5, loc=(side*lw/2*0.6, lw/2 + 0.05, lz + 2),
                      parent=minaret_e, mat_=M_MINARET_ZELLIGE, scale=(1, 0.3, 1))
# Top crown structure (signature smaller)
beveled_cube("min_top", (3, 3, 1.5), bevel_offset=0.10, loc=(0, 0, 24),
             parent=minaret_e, mat_=M_MINARET)
# Pyramidal cap
smooth_cone("min_cap", r1=2, r2=0.10, depth=2, segs=4, loc=(0, 0, 25.75),
            parent=minaret_e, mat_=M_MINARET).rotation_euler = (0, 0, math.radians(45))
# Decorative ball spheres signature
for si in range(3):
    smooth_sphere(f"min_ball{si}", r=0.40 - si*0.10, loc=(0, 0, 27 + si*0.50),
                  parent=minaret_e, mat_=M_MINARET_GOLD)
# Crescent moon top (signature)
crescent_e = empty("min_cre", (0, 0, 29), parent=minaret_e)
smooth_sphere("min_cre_b", r=0.40, segs=18, rings=14, loc=(0, 0, 0),
              parent=crescent_e, mat_=M_MINARET_GOLD)
smooth_sphere("min_cre_c", r=0.32, loc=(0.10, 0, 0),
              parent=crescent_e, mat_=M_MINARET)

# ============ HORSESHOE ARCH ENTRANCE (signature) ============
arch_e = empty("arch", loc=(0, -35, 0))
# 2 side pillars
for side in (-1, 1):
    beveled_cube(f"ar_p{side}", (1.5, 1.5, 6), bevel_offset=0.10, loc=(side*4, 0, 3),
                 parent=arch_e, mat_=M_WALL_OCHRE)
    # Zellige tile decoration
    for li in range(5):
        beveled_cube(f"ar_z{side}_{li}", (1.55, 1.55, 0.30), bevel_offset=0.04,
                     loc=(side*4, 0, 0.5 + li*1.2), parent=arch_e, mat_=M_MINARET_ZELLIGE)
# Horseshoe arch shape (signature curve)
for ai in range(20):
    aa = math.pi * ai / 18.0 - math.pi/12
    ax_a = math.cos(aa) * 4
    az_a = math.sin(aa) * 5 + 4 if aa > 0 else 4
    if aa > 0:
        smooth_sphere(f"ar_h{ai}", r=0.5, segs=14, rings=10,
                      loc=(ax_a, 0, az_a + 2), parent=arch_e, mat_=M_WALL_OCHRE)
# Top decorative band
beveled_cube("ar_top", (12, 1.5, 1.0), bevel_offset=0.10, loc=(0, 0, 10),
             parent=arch_e, mat_=M_WALL_RED)
# Crenellated top signature
for ci in range(10):
    cx_c = -5 + ci * 1.1
    beveled_cube(f"ar_cr{ci}", (0.6, 1.5, 0.6), bevel_offset=0.04,
                 loc=(cx_c, 0, 10.7), parent=arch_e, mat_=M_WALL_OCHRE)

# ============ 12 SOUK STALLS (signature spice + goods) ============
def make_souk_stall(name, loc, scale=1.0, facing=0, stall_type="spices"):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # 4 posts
    for x_p in (-1, 1):
        for y_p in (-1, 1):
            cyl(f"{name}_p_{x_p}_{y_p}", r=0.10, depth=3.5, segs=10,
                loc=(x_p*1.5, y_p*1.0, 1.75), parent=base, mat_=M_WOOD_DARK_M)
    # Wood awning frame
    beveled_cube(f"{name}_aw_top", (3.5, 2.5, 0.15), bevel_offset=0.06,
                 loc=(0, 0, 3.4), parent=base, mat_=M_WOOD_M)
    # Striped colored awning (signature)
    awning_col = random.choice([M_RUG_RED, M_RUG_BLUE, M_RUG_ORANGE, M_RUG_TURQUOISE])
    for ai in range(6):
        ax_a = -1.5 + ai * 0.55
        beveled_cube(f"{name}_aw{ai}", (0.50, 2.6, 0.05), bevel_offset=0.02,
                     loc=(ax_a, 0, 3.55), parent=base,
                     mat_=awning_col if ai % 2 == 0 else M_RUG_ORANGE)
    # Counter/table
    beveled_cube(f"{name}_c", (3.2, 2.2, 0.20), bevel_offset=0.06, loc=(0, 0, 1.0),
                 parent=base, mat_=M_WOOD_M)
    # Front cloth
    beveled_cube(f"{name}_cl", (3.4, 0.10, 0.8), bevel_offset=0.04, loc=(0, -1.10, 0.5),
                 parent=base, mat_=random.choice(RUG_COLORS))

    if stall_type == "spices":
        # SPICE PYRAMIDS (signature multicolor)
        spice_colors_used = []
        for si in range(8):
            sx_s = -1.2 + si * 0.35
            sy_s = -0.5 + (si % 2) * 1.0
            scol = SPICE_COLORS[si % len(SPICE_COLORS)]
            spice_colors_used.append(scol)
            # Cone pyramid signature
            smooth_cone(f"{name}_sp{si}", r1=0.18, r2=0.02, depth=0.30, segs=14,
                        loc=(sx_s, sy_s, 1.25), parent=base, mat_=scol)
            # Base ring
            cyl(f"{name}_sp_b{si}", r=0.20, depth=0.06, segs=14,
                loc=(sx_s, sy_s, 1.13), parent=base, mat_=scol)
    elif stall_type == "rugs":
        # Hanging carpets (signature)
        for ri in range(3):
            rcol = random.choice(RUG_COLORS)
            beveled_cube(f"{name}_rg{ri}", (1.0, 0.10, 2.0), bevel_offset=0.06,
                         loc=(-1.0 + ri*1.0, 1.0, 2.5), parent=base, mat_=rcol)
            # Pattern bands
            for pi in range(5):
                beveled_cube(f"{name}_rgp{ri}_{pi}", (1.05, 0.12, 0.20), bevel_offset=0.02,
                             loc=(-1.0 + ri*1.0, 1.05, 1.8 + pi*0.30), parent=base,
                             mat_=random.choice(RUG_COLORS))
    elif stall_type == "lamps":
        # Hanging lamps
        for li in range(6):
            la = (li / 6.0) * math.pi * 2
            lx_l = math.cos(la) * 1.0
            ly_l = math.sin(la) * 0.7
            # Lamp body
            smooth_sphere(f"{name}_lp{li}", r=0.15, segs=14, rings=10,
                          loc=(lx_l, ly_l, 2.5), parent=base, mat_=random.choice(LANTERN_COLORS))
            # Brass top
            cyl(f"{name}_lp_t{li}", r=0.05, depth=0.20, segs=10,
                loc=(lx_l, ly_l, 2.85), parent=base, mat_=M_BRASS)
        # Tagines on counter (signature)
        for ti in range(3):
            tx_t = -0.8 + ti * 0.8
            # Tagine base
            cyl(f"{name}_tg_b{ti}", r=0.20, depth=0.08, segs=14, loc=(tx_t, 0, 1.18),
                parent=base, mat_=M_TAGINE_CLAY)
            # Conical lid (signature)
            smooth_cone(f"{name}_tg_l{ti}", r1=0.18, r2=0.04, depth=0.35, segs=14,
                        loc=(tx_t, 0, 1.40), parent=base, mat_=M_TAGINE_CLAY)
            # Knob top
            smooth_sphere(f"{name}_tg_k{ti}", r=0.04, loc=(tx_t, 0, 1.60),
                          parent=base, mat_=M_TAGINE_DARK_M)
    else:  # leather / general
        # Hanging items
        for pi in range(6):
            px_p = -1.2 + pi * 0.5
            beveled_cube(f"{name}_pr{pi}", (0.35, 0.10, 0.50), bevel_offset=0.04,
                         loc=(px_p, 0.8, 2.0), parent=base,
                         mat_=random.choice([M_DJELLABA_BROWN, M_DJELLABA_CREAM, M_RUG_RED]))

    # Hanging lantern (signature each stall has one)
    cyl(f"{name}_ll_c", r=0.012, depth=0.40, segs=6, loc=(0, 0, 3.0),
        parent=base, mat_=M_LANTERN_FRAME)
    # Star-shaped lantern body
    lan_col = random.choice(LANTERN_COLORS)
    smooth_sphere(f"{name}_ll", r=0.20, segs=14, rings=10, loc=(0, 0, 2.6),
                  parent=base, mat_=lan_col, scale=(1, 1, 1.2))
    # 8 brass star points
    for sti in range(8):
        sta = (sti / 8.0) * math.pi * 2
        smooth_cone(f"{name}_lp_st{sti}", r1=0.04, r2=0.005, depth=0.12, segs=6,
                    loc=(math.cos(sta)*0.20, math.sin(sta)*0.20, 2.6),
                    parent=base, mat_=M_BRASS).rotation_euler = (0, math.radians(90), sta)
    return base

stalls = []
stall_types = ["spices", "rugs", "lamps", "leather", "spices", "rugs",
                "lamps", "leather", "spices", "rugs", "lamps", "leather"]
for si in range(12):
    sa = (si / 12.0) * math.pi * 2
    sx_s = math.cos(sa) * 15
    sy_s = math.sin(sa) * 10
    s = make_souk_stall(f"stall{si}", (sx_s, sy_s, 0), scale=1.0,
                        facing=sa + math.pi, stall_type=stall_types[si])
    stalls.append(s)

# ============ TAGINE display (extra steaming central) ============
tagine_center_e = empty("tag_center", loc=(0, 0, 0))
# Stone hearth
cyl("tc_h", r=1.5, depth=0.30, segs=18, loc=(0, 0, 0.30), parent=tagine_center_e, mat_=M_STONE_DARK_M)
# 4 tagines arranged
tagine_positions_c = [(-0.7, 0, 0), (0.7, 0, 0), (0, -0.7, 0), (0, 0.7, 0)]
for ti, (tx, ty, tz) in enumerate(tagine_positions_c):
    t_e = empty(f"tag_c{ti}", (tx, ty, 0.45), parent=tagine_center_e)
    # Base
    cyl(f"tc_b{ti}", r=0.35, depth=0.12, segs=14, loc=(0, 0, 0), parent=t_e, mat_=M_TAGINE_CLAY)
    # Conical lid (signature)
    smooth_cone(f"tc_l{ti}", r1=0.32, r2=0.06, depth=0.50, segs=14, loc=(0, 0, 0.32),
                parent=t_e, mat_=M_TAGINE_CLAY)
    # Pattern bands
    for pb in range(3):
        cyl(f"tc_pb{ti}_{pb}", r=0.30 - pb*0.05, depth=0.02, segs=14,
            loc=(0, 0, 0.20 + pb*0.10), parent=t_e, mat_=M_TAGINE_DARK_M)
    # Knob
    smooth_sphere(f"tc_k{ti}", r=0.07, loc=(0, 0, 0.62), parent=t_e, mat_=M_TAGINE_DARK_M)
    # Steam rising signature
    for si_st in range(4):
        smooth_sphere(f"tc_st{ti}_{si_st}", r=0.10 - si_st*0.01,
                      loc=(math.sin(si_st*0.4)*0.05, 0, 0.75 + si_st*0.25),
                      parent=t_e, mat_=M_TAGINE_STEAM, scale=(1, 1, 0.7))
    t_e["_phase"] = random.uniform(0, math.pi*2)

# ============ 6 MERCHANTS (djellaba) ============
def make_merchant(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    djel_col = random.choice(DJELLABA_COLORS)
    # Long djellaba robe
    smooth_cone(f"{name}_robe", r1=0.50*scale, r2=0.35*scale, depth=1.8*scale, segs=18,
                loc=(0, 0, 0.95*scale), parent=base, mat_=djel_col)
    # Pointed hood (signature djellaba) - peaked back
    hood_e = empty(f"{name}_hood", (0, 0.15*scale, 2.0*scale), parent=base)
    smooth_cone(f"{name}_hd_c", r1=0.20*scale, r2=0.03*scale, depth=0.40*scale, segs=12,
                loc=(0, 0, 0.20*scale), parent=hood_e, mat_=djel_col)
    # Sleeves
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.40*scale, 0, 1.75*scale), parent=base)
        sh.rotation_euler = (math.radians(-50 + side*15), 0, math.radians(side*-15))
        smooth_cone(f"{name}_sl{side_idx}", r1=0.12*scale, r2=0.16*scale, depth=0.50*scale, segs=12,
                    loc=(0, 0, -0.25*scale), parent=sh, mat_=djel_col)
        # Hand
        smooth_sphere(f"{name}_h{side_idx}", r=0.06*scale, loc=(0, 0, -0.55*scale),
                      parent=sh, mat_=M_SKIN_ARAB)
    # Babouches yellow signature
    for side in (-1, 1):
        beveled_cube(f"{name}_bab{side}", (0.10*scale, 0.18*scale, 0.05*scale), bevel_offset=0.02,
                     loc=(side*0.12*scale, 0.05*scale, 0), parent=base, mat_=M_BABOUCHE)
        # Pointed toe (signature)
        smooth_sphere(f"{name}_bab_t{side}", r=0.04*scale,
                      loc=(side*0.12*scale, 0.15*scale, 0.05*scale), parent=base, mat_=M_BABOUCHE)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 2.05*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN_ARAB)
    # Beard (signature)
    for bi in range(10):
        ba = (bi / 10.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_bd{bi}", r=0.04*scale,
                      loc=(math.sin(ba)*0.13*scale, -0.16*scale, -0.10*scale - (bi%3)*0.05*scale),
                      parent=head_m_e, mat_=M_BEARD_DARK)
    # Moustache
    for side in (-1, 1):
        beveled_cube(f"{name}_mou{side}", (0.08*scale, 0.04*scale, 0.04*scale), bevel_offset=0.01,
                     loc=(side*0.05*scale, -0.17*scale, -0.06*scale), parent=head_m_e, mat_=M_BEARD_DARK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale, loc=(side*0.06*scale, -0.15*scale, 0.03*scale),
                      parent=head_m_e, mat_=M_EYE_DARK_M)
    # FEZ/TARBOUCHE or turban
    if random.random() > 0.5:
        # Fez (signature red cylindrical)
        cyl(f"{name}_fez", r=0.20*scale, depth=0.25*scale, segs=14, loc=(0, 0, 0.25*scale),
            parent=head_m_e, mat_=M_LANTERN_RED)
        # Tassel
        smooth_sphere(f"{name}_tas", r=0.04*scale, loc=(0.10*scale, 0, 0.42*scale),
                      parent=head_m_e, mat_=M_HAIR_BLACK_M)
    else:
        # Turban wrapped (signature)
        for ti2 in range(5):
            ta_t = (ti2 / 5.0) * math.pi - math.pi/2
            cyl(f"{name}_tb{ti2}", r=0.21*scale, depth=0.06*scale, segs=14,
                loc=(0, 0, 0.18*scale + ti2*0.07*scale),
                parent=head_m_e, mat_=M_DJELLABA_CREAM).rotation_euler = (math.radians(ta_t*5), 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_m_e}

merchants = []
merchant_pos = [(-15, 8, math.radians(60)), (15, 8, math.radians(-60)),
                 (-15, -8, math.radians(45)), (15, -8, math.radians(-45)),
                 (-5, 15, math.radians(0)), (5, 15, math.radians(0))]
for i, (mx, my, fac) in enumerate(merchant_pos):
    m = make_merchant(f"merchant{i}", (mx, my, 0), scale=1.0, facing=fac)
    merchants.append(m)

# ============ 4 WOMEN (hijab + caftan) ============
def make_woman_morocco(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    caft_col = random.choice(CAFTAN_COLORS)
    # Long caftan dress
    smooth_cone(f"{name}_caftan", r1=0.55*scale, r2=0.35*scale, depth=1.9*scale, segs=20,
                loc=(0, 0, 1.0*scale), parent=base, mat_=caft_col)
    # Gold belt
    cyl(f"{name}_belt", r=0.40*scale, depth=0.10*scale, segs=18, loc=(0, 0, 1.45*scale),
        parent=base, mat_=M_CAFTAN_GOLD)
    # Belt jewels
    for bj in range(8):
        bja = (bj / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_bj{bj}", r=0.03*scale,
                      loc=(math.cos(bja)*0.42*scale, math.sin(bja)*0.42*scale, 1.45*scale),
                      parent=base, mat_=random.choice([M_LANTERN_BLUE, M_LANTERN_RED]))
    # Embroidered patterns on caftan
    for ei in range(8):
        ea = (ei / 8.0) * math.pi * 2
        beveled_cube(f"{name}_em{ei}", (0.04*scale, 0.04*scale, 1.6*scale), bevel_offset=0.005,
                     loc=(math.cos(ea)*0.50*scale, math.sin(ea)*0.50*scale, 1.0*scale),
                     parent=base, mat_=M_CAFTAN_GOLD)
    # Arms with caftan sleeves
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.35*scale, 0, 1.80*scale), parent=base)
        sh.rotation_euler = (math.radians(-50 + side*15), 0, math.radians(side*-20))
        smooth_cone(f"{name}_sl{side_idx}", r1=0.10*scale, r2=0.14*scale, depth=0.55*scale, segs=12,
                    loc=(0, 0, -0.27*scale), parent=sh, mat_=caft_col)
        # Hand
        smooth_sphere(f"{name}_h{side_idx}", r=0.05*scale, loc=(0, 0, -0.60*scale),
                      parent=sh, mat_=M_SKIN_ARAB)
        # Henna patterns on hand (signature dots)
        for hi in range(3):
            smooth_sphere(f"{name}_hen{side_idx}_{hi}", r=0.012*scale,
                          loc=(0, 0, -0.60*scale + hi*0.02*scale),
                          parent=sh, mat_=M_DJELLABA_BROWN)
    # Head
    head_w_e = empty(f"{name}_he", (0, 0, 2.05*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.17*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_w_e, mat_=M_SKIN_ARAB)
    # HIJAB signature (covering head)
    hijab_col = random.choice([M_HIJAB_BLACK, M_HIJAB_BLUE, M_CAFTAN_PURPLE])
    smooth_sphere(f"{name}_hj", r=0.22*scale, segs=20, rings=14, loc=(0, 0.04*scale, 0.05*scale),
                  parent=head_w_e, mat_=hijab_col, scale=(1, 1, 1.1))
    # Hijab drape down sides
    for side in (-1, 1):
        beveled_cube(f"{name}_hj_d{side}", (0.06*scale, 0.20*scale, 0.40*scale), bevel_offset=0.04,
                     loc=(side*0.16*scale, 0.05*scale, -0.18*scale), parent=head_w_e, mat_=hijab_col)
    # Eyes lined kohl signature
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale, loc=(side*0.06*scale, -0.15*scale, 0.03*scale),
                      parent=head_w_e, mat_=M_EYE_DARK_M)
        # Kohl line
        beveled_cube(f"{name}_kh{side}", (0.10*scale, 0.04*scale, 0.02*scale), bevel_offset=0.005,
                     loc=(side*0.08*scale, -0.16*scale, 0.0), parent=head_w_e, mat_=M_HAIR_BLACK_M)
    # Lips
    beveled_cube(f"{name}_lips", (0.06*scale, 0.04*scale, 0.02*scale), bevel_offset=0.005,
                 loc=(0, -0.16*scale, -0.07*scale), parent=head_w_e, mat_=M_LIPS_M)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_w_e}

women = []
women_pos = [(-10, 3, math.radians(45)), (10, 3, math.radians(-45)),
              (-7, -3, math.radians(-30)), (7, -3, math.radians(30))]
for i, (wx, wy, fac) in enumerate(women_pos):
    w = make_woman_morocco(f"woman{i}", (wx, wy, 0), scale=1.0, facing=fac)
    women.append(w)

# ============ 4 MUSICIANS (Gnawa guembri + darbouka) ============
def make_musician_m(name, loc, instrument, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body djellaba
    smooth_cone(f"{name}_robe", r1=0.45*scale, r2=0.32*scale, depth=1.0*scale, segs=14,
                loc=(0, 0, 0.55*scale), parent=base, mat_=M_DJELLABA_BROWN)
    # Sash
    cyl(f"{name}_sa", r=0.34*scale, depth=0.08*scale, segs=14, loc=(0, 0, 0.95*scale),
        parent=base, mat_=M_LANTERN_RED)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 1.40*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN_ARAB)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.03*scale), parent=head_m_e, mat_=M_EYE_DARK_M)
    # Fez red
    cyl(f"{name}_fez", r=0.20*scale, depth=0.25*scale, segs=14, loc=(0, 0, 0.25*scale),
        parent=head_m_e, mat_=M_LANTERN_RED)
    # Tassel
    smooth_sphere(f"{name}_tas", r=0.04*scale, loc=(0.10*scale, 0, 0.42*scale),
                  parent=head_m_e, mat_=M_HAIR_BLACK_M)
    # Beard
    for bi in range(8):
        ba = (bi / 8.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_bd{bi}", r=0.04*scale,
                      loc=(math.sin(ba)*0.12*scale, -0.15*scale, -0.10*scale),
                      parent=head_m_e, mat_=M_BEARD_DARK)
    # INSTRUMENT
    inst_e = empty(f"{name}_inst", (0, -0.30*scale, 0.85*scale), parent=base)
    if instrument == "guembri":
        # Bass lute body (signature wood rectangular)
        beveled_cube(f"{name}_gb_b", (0.45, 0.20, 0.30), bevel_offset=0.06,
                     loc=(0, 0, 0), parent=inst_e, mat_=M_GUEMBRI)
        # Long neck
        cyl(f"{name}_gb_n", r=0.025, depth=0.80, segs=10, loc=(0, -0.05, 0.55),
            parent=inst_e, mat_=M_GUEMBRI)
        # 3 strings
        for st in range(3):
            cyl(f"{name}_gb_st{st}", r=0.005, depth=1.0, segs=6,
                loc=((st-1)*0.015, -0.07, 0.30), parent=inst_e,
                mat_=M_GUEMBRI_STRING).rotation_euler = (0, math.radians(90), 0)
    elif instrument == "darbouka":
        # Hourglass goblet drum (signature)
        smooth_cone(f"{name}_drb_t", r1=0.20, r2=0.15, depth=0.30, segs=14,
                    loc=(0, 0, 0.20), parent=inst_e, mat_=M_DARBOUKA)
        smooth_cone(f"{name}_drb_m", r1=0.15, r2=0.10, depth=0.15, segs=14,
                    loc=(0, 0, 0.025), parent=inst_e, mat_=M_DARBOUKA)
        smooth_cone(f"{name}_drb_b", r1=0.10, r2=0.18, depth=0.25, segs=14,
                    loc=(0, 0, -0.20), parent=inst_e, mat_=M_DARBOUKA)
        # Skin top
        cyl(f"{name}_drb_s", r=0.21, depth=0.03, segs=14, loc=(0, 0, 0.35),
            parent=inst_e, mat_=M_DARBOUKA_SKIN)
        # Decorations
        for di in range(8):
            da = (di / 8.0) * math.pi * 2
            smooth_sphere(f"{name}_drb_d{di}", r=0.02,
                          loc=(math.cos(da)*0.21, math.sin(da)*0.21, 0.20),
                          parent=inst_e, mat_=M_BRASS)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "inst": inst_e, "he": head_m_e}

musicians_m = []
mus_data_m = [("guembri", -18, -12), ("darbouka", -22, -10),
               ("guembri", 18, -12), ("darbouka", 22, -10)]
for i, (inst, mx, my) in enumerate(mus_data_m):
    m = make_musician_m(f"mus_m{i}", (mx, my, 0), instrument=inst, scale=1.0,
                        facing=math.radians(90))
    musicians_m.append(m)

# ============ DROMEDARY CAMEL (signature) ============
camel_e = empty("dromedary", loc=(-25, -15, 0))
camel_e.rotation_euler = (0, 0, math.radians(60))
# Body
smooth_sphere("dr_body", r=0.85, segs=20, rings=14, loc=(0, 0, 2.2),
              parent=camel_e, mat_=M_CAMEL_T, scale=(1.7, 1.0, 1.0))
# Single hump (signature dromedary)
smooth_sphere("dr_hump", r=0.55, segs=18, rings=14, loc=(0.10, 0, 2.85),
              parent=camel_e, mat_=M_CAMEL_T, scale=(1.2, 0.9, 1.0))
# 4 long legs
for x in (-1, 1):
    for y in (-1, 1):
        cyl(f"dr_l{x}{y}", r=0.11, depth=2.2, segs=10,
            loc=(x*0.55, y*0.40, 1.1), parent=camel_e, mat_=M_CAMEL_T)
        cyl(f"dr_h{x}{y}", r=0.12, depth=0.10, segs=10, loc=(x*0.55, y*0.40, 0.05),
            parent=camel_e, mat_=M_CAMEL_D)
# Long curved neck
neck_dr_e = empty("dr_neck", (1.1, 0, 2.6), parent=camel_e)
neck_dr_e.rotation_euler = (0, math.radians(-25), 0)
for ni in range(6):
    cyl(f"dr_n{ni}", r=0.18 - ni*0.012, depth=0.30, segs=12,
        loc=(0, 0, ni*0.30 + 0.15), parent=neck_dr_e, mat_=M_CAMEL_T)
# Head
head_dr_e = empty("dr_he", (0, 0, 2.05), parent=neck_dr_e)
smooth_sphere("dr_head", r=0.22, segs=18, rings=14, loc=(0.10, 0, 0),
              parent=head_dr_e, mat_=M_CAMEL_T, scale=(1.4, 0.9, 1.0))
smooth_sphere("dr_snout", r=0.18, loc=(0.30, 0, -0.10),
              parent=head_dr_e, mat_=M_CAMEL_D, scale=(1.3, 0.7, 0.7))
for side in (-1, 1):
    smooth_sphere(f"dr_eye{side}", r=0.04, loc=(0.10, side*0.15, 0.05),
                  parent=head_dr_e, mat_=M_EYE_DARK_M)
    # Long eyelashes signature
    for li in range(4):
        cyl(f"dr_lash{side}_{li}", r=0.005, depth=0.07, segs=4,
            loc=(0.10 + li*0.01, side*0.15, 0.10), parent=head_dr_e, mat_=M_HAIR_BLACK_M)
# Red harness with tassels
cyl("dr_harn", r=0.20, depth=0.10, segs=14, loc=(0, 0, 1.6),
    parent=neck_dr_e, mat_=M_HARNESS_M)
for ti in range(6):
    ta = (ti / 6.0) * math.pi * 2
    smooth_sphere(f"dr_t{ti}", r=0.04,
                  loc=(math.cos(ta)*0.22, math.sin(ta)*0.22, 1.6),
                  parent=neck_dr_e, mat_=M_MINARET_GOLD)
# Saddle blanket
beveled_cube("dr_sad", (1.5, 1.7, 0.10), bevel_offset=0.04, loc=(0, 0, 3.35),
             parent=camel_e, mat_=M_RUG_RED)
for pi in range(4):
    beveled_cube(f"dr_sp{pi}", (0.30, 1.7, 0.05), bevel_offset=0.02,
                 loc=(-0.45 + pi*0.30, 0, 3.40), parent=camel_e, mat_=random.choice(RUG_COLORS))

# ============ CATS (signature street cats) ============
def make_cat(name, loc, scale=0.6, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    cat_col = random.choice([M_CAT_GREY, M_CAT_ORANGE, M_CAT_WHITE])
    # Body
    smooth_sphere(f"{name}_body", r=0.30*scale, segs=16, rings=10, loc=(0, 0, 0.30*scale),
                  parent=base, mat_=cat_col, scale=(1.6, 0.85, 1))
    # 4 legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}{y}", r=0.04*scale, depth=0.30*scale, segs=8,
                loc=(x*0.20*scale, y*0.12*scale, 0.15*scale), parent=base, mat_=cat_col)
    # Head
    head_c_e = empty(f"{name}_he", (0.35*scale, 0, 0.40*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.16*scale, segs=14, rings=10, loc=(0, 0, 0),
                  parent=head_c_e, mat_=cat_col)
    # Pointed ears
    for side in (-1, 1):
        smooth_cone(f"{name}_ear{side}", r1=0.06*scale, r2=0.005*scale, depth=0.10*scale, segs=8,
                    loc=(0, side*0.08*scale, 0.10*scale), parent=head_c_e, mat_=cat_col)
    # Glowing eyes (signature night)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale, loc=(0.10*scale, side*0.07*scale, 0.04*scale),
                      parent=head_c_e, mat_=M_LANTERN_GOLD)
    # Tail
    cyl(f"{name}_tail", r=0.025*scale, depth=0.40*scale, segs=8,
        loc=(-0.35*scale, 0, 0.35*scale), parent=base, mat_=cat_col).rotation_euler = (math.radians(60), 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

cats = []
cat_pos = [(-7, -22, math.radians(45)), (8, -22, math.radians(-45)),
            (-25, 12, math.radians(0)), (25, 12, math.radians(180))]
for i, (cx, cy, fac) in enumerate(cat_pos):
    c = make_cat(f"cat{i}", (cx, cy, 0), scale=0.6, facing=fac)
    cats.append(c)

# ============ HANGING BERBER LAMPS along streets (signature) ============
hanging_lamps = []
for ri in range(3):
    rz_l = 5 + ri * 1.5
    for ci in range(8):
        cx_l = -28 + ci * 8
        lan_e = empty(f"hl{ri}_{ci}", (cx_l, ri*5 - 5, rz_l))
        # Cord
        cyl(f"hl{ri}_{ci}_c", r=0.01, depth=0.8, segs=6, loc=(0, 0, 0.4),
            parent=lan_e, mat_=M_LANTERN_FRAME)
        # Star-shaped Berber lamp
        lam_col = random.choice(LANTERN_COLORS)
        # Body
        smooth_sphere(f"hl{ri}_{ci}_b", r=0.18, segs=14, rings=10, loc=(0, 0, 0),
                      parent=lan_e, mat_=lam_col, scale=(1, 1, 1.2))
        # Brass frame
        cyl(f"hl{ri}_{ci}_t", r=0.10, depth=0.04, segs=10, loc=(0, 0, 0.20),
            parent=lan_e, mat_=M_BRASS)
        # 8 star spikes (signature Berber)
        for st in range(8):
            sa = (st / 8.0) * math.pi * 2
            smooth_cone(f"hl{ri}_{ci}_st{st}", r1=0.04, r2=0.005, depth=0.12, segs=6,
                        loc=(math.cos(sa)*0.18, math.sin(sa)*0.18, 0),
                        parent=lan_e, mat_=M_BRASS).rotation_euler = (0, math.radians(90), sa)
        lan_e["_phase"] = random.uniform(0, math.pi*2)
        hanging_lamps.append(lan_e)

# ============================================================
# ⭐ 600 LANTERNS + 400 SPICES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
floating_lanterns = []
for i in range(600):
    px = random.uniform(-60, 60)
    py = random.uniform(-60, 60)
    pz = random.uniform(3, 20)
    lan_col = M_LANTERN_BLUE if i % 2 == 0 else random.choice(LANTERN_COLORS)
    lan_e = empty(f"fl{i}", (px, py, pz))
    smooth_sphere(f"fl_b{i}", r=random.uniform(0.10, 0.18), segs=12, rings=10,
                  loc=(0, 0, 0), parent=lan_e, mat_=lan_col, scale=(1, 1, 1.2))
    # Frame top
    cyl(f"fl_t{i}", r=0.06, depth=0.03, segs=10, loc=(0, 0, 0.13),
        parent=lan_e, mat_=M_BRASS)
    lan_e["_phase"] = random.uniform(0, math.pi*2)
    lan_e["_base_x"] = px; lan_e["_base_y"] = py; lan_e["_base_z"] = pz
    lan_e["_amp_x"] = random.uniform(1.0, 2.5)
    lan_e["_amp_y"] = random.uniform(1.0, 2.5)
    lan_e["_amp_z"] = random.uniform(0.5, 1.5)
    lan_e["_speed"] = random.uniform(0.3, 0.8)
    floating_lanterns.append(lan_e)

# 400 spice particles floating
spice_particles = []
for i in range(400):
    px = random.uniform(-50, 50)
    py = random.uniform(-50, 50)
    pz = random.uniform(1, 12)
    s_col = random.choice([M_SPICE_DUST, M_SPICE_ORANGE, M_SPICE_YELLOW, M_SPICE_RED])
    s_obj = smooth_sphere(f"sp{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6,
                          loc=(px, py, pz), mat_=s_col)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(1.5, 3.0)
    s_obj["_amp_y"] = random.uniform(1.5, 3.0)
    s_obj["_amp_z"] = random.uniform(0.5, 1.5)
    s_obj["_speed"] = random.uniform(0.4, 1.0)
    spice_particles.append(s_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Merchants gesticulate
for m in merchants:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3),
                                     math.cos(t * 1.5 + phase) * math.radians(3),
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (0, 0, math.sin(t * 1.2 + phase) * math.radians(20))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Women browse + sway
for w in women:
    phase = w["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        w["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(3),
                                     math.cos(t * 1.2 + phase) * math.radians(3),
                                     w["root"].rotation_euler.z)
        w["root"].keyframe_insert("rotation_euler", frame=f)
        w["he"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(15))
        w["he"].keyframe_insert("rotation_euler", frame=f)

# Musicians play
for mu in musicians_m:
    phase = mu["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        mu["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(4), 0,
                                       mu["root"].rotation_euler.z)
        mu["root"].keyframe_insert("rotation_euler", frame=f)
        sc_i = 1 + math.sin(t * 5.0 + phase) * 0.05
        mu["inst"].scale = (sc_i, sc_i, sc_i)
        mu["inst"].keyframe_insert("scale", frame=f)
        mu["he"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(6), 0,
                                     math.cos(t * 2.0 + phase) * math.radians(8))
        mu["he"].keyframe_insert("rotation_euler", frame=f)

# Camel sway
phase_dr = 0
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    camel_e.location.z = math.sin(t * 0.6) * 0.05
    neck_dr_e.rotation_euler = (0, math.radians(-25) + math.sin(t * 0.8) * math.radians(8), 0)
    camel_e.keyframe_insert("location", frame=f)
    neck_dr_e.keyframe_insert("rotation_euler", frame=f)

# Cats walking
for c in cats:
    phase = c["_phase"]
    bx_c = c.location.x; by_c = c.location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        c.location.x = bx_c + math.sin(t * 1.0 + phase) * 0.8
        c.location.y = by_c + math.cos(t * 1.0 + phase) * 0.8
        c.location.z = abs(math.sin(t * 2.0 + phase)) * 0.05
        c.keyframe_insert("location", frame=f)

# Tagine steam
for ti in range(4):
    tc = bpy.data.objects.get(f"tag_c{ti}")
    if tc is None: continue
    phase = tc["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        sc_t = 1 + math.sin(t * 1.5 + phase) * 0.08
        tc.scale = (sc_t, sc_t, sc_t)
        tc.keyframe_insert("scale", frame=f)

# Hanging lamps sway gently
for hl in hanging_lamps:
    phase = hl["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        hl.rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(8),
                              math.cos(t * 1.5 + phase) * math.radians(6), 0)
        hl.keyframe_insert("rotation_euler", frame=f)

# 600 floating lanterns drift
for l in floating_lanterns:
    phase = l["_phase"]; speed = l["_speed"]
    bx, by, bz = l["_base_x"], l["_base_y"], l["_base_z"]
    ax, ay, az = l["_amp_x"], l["_amp_y"], l["_amp_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        l.location = (x, y, z)
        l.rotation_euler = (math.sin(t * speed + phase) * math.radians(8),
                             math.cos(t * speed + phase) * math.radians(8), 0)
        l.keyframe_insert("location", frame=f)
        l.keyframe_insert("rotation_euler", frame=f)

# 400 spice particles drift
for sp in spice_particles:
    phase = sp["_phase"]; speed = sp["_speed"]
    bx, by, bz = sp["_base_x"], sp["_base_y"], sp["_base_z"]
    ax, ay, az = sp["_amp_x"], sp["_amp_y"], sp["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        sp.location = (x, y, max(0.5, z))
        sc_sp = 0.7 + abs(math.sin(t * speed + phase)) * 0.6
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
out_glb = os.path.join(out_dir, "pbr_marrakech_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_moroccan_marrakech_souk_medina] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_moroccan_marrakech_souk_medina] Koutoubia minaret + horseshoe arch + 12 souk stalls (spices+rugs+lamps+leather) + 4 tagines steam + 6 merchants djellaba + 4 women caftans+hijab + 4 musicians guembri+darbouka + dromedary + 4 cats + 24 hanging lamps + 600 lanterns + 400 spices")
print("⭐ FIXES: 1 ground + 600 blue lanterns + 400 spices (signature Marrakech thematic mandatory) ⭐")
