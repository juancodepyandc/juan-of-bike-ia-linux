"""
proc_argentinian_tango_milonga.py — 238e procédural AuroraIA (103e qualité)
Argentinian tango: ONE wood floor + cabaret + curved stage + 4 tango couples + 5 musicians + cantor + 8 spectators + candelabras + mirrors + columns + 600 rose petals + 400 candle sparkles
FIXES : 1 ground + 600 rose petals + 400 candle sparkles signature tango
"""
import bpy, bmesh, math, random, os

random.seed(0x747C0238)

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

# Tango cabaret palette - moody warm
M_SKY = mat("sky", (0.08, 0.06, 0.12, 1.0), 0.0, 0.7, emission=(0.08,0.06,0.12), emission_strength=0.5)
M_AMBIENT = mat("amb", (0.45, 0.30, 0.18, 1.0), 0.0, 0.30, emission=(0.42,0.28,0.16), emission_strength=2.0)

# Wood floor (signature dance floor)
M_FLOOR = mat("floor", (0.42, 0.25, 0.12, 1.0), 0.3, 0.40, emission=(0.38,0.22,0.10), emission_strength=0.6)
M_FLOOR_GLOSS = mat("floor_g", (0.55, 0.32, 0.15, 1.0), 0.6, 0.20, emission=(0.50,0.30,0.13), emission_strength=0.8)
M_FLOOR_LINE = mat("floor_l", (0.78, 0.55, 0.30, 1.0), 0.5, 0.30, emission=(0.72,0.50,0.28), emission_strength=0.7)

# Walls art deco
M_WALL_BURGUNDY = mat("wall_b", (0.45, 0.15, 0.18, 1.0), 0.0, 0.50, emission=(0.42,0.15,0.18), emission_strength=0.7)
M_WALL_GOLD = mat("wall_g", (0.85, 0.65, 0.25, 1.0), 0.85, 0.25, emission=(0.78,0.60,0.22), emission_strength=0.8)
M_WALL_DARK_WOOD = mat("wall_d", (0.25, 0.15, 0.08, 1.0), 0.2, 0.40, emission=(0.22,0.13,0.06), emission_strength=0.4)
M_MIRROR = mat("mirror", (0.85, 0.85, 0.90, 1.0), 0.95, 0.10, emission=(0.78,0.78,0.85), emission_strength=1.5)
M_COLUMN = mat("column", (0.55, 0.42, 0.25, 1.0), 0.0, 0.45, emission=(0.50,0.38,0.22), emission_strength=0.6)

# Stage
M_STAGE = mat("stage", (0.30, 0.18, 0.10, 1.0), 0.3, 0.35, emission=(0.28,0.16,0.08), emission_strength=0.5)
M_CURTAIN = mat("curtain", (0.62, 0.10, 0.15, 1.0), 0.0, 0.65, emission=(0.58,0.10,0.15), emission_strength=0.8)

# Dancers
M_SKIN_ARG = mat("skin", (0.92, 0.78, 0.62, 1.0), 0.0, 0.55, emission=(0.85,0.72,0.58), emission_strength=0.4)
M_DRESS_RED = mat("dress_r", (0.95, 0.12, 0.20, 1.0), 0.0, 0.45, emission=(0.92,0.12,0.18), emission_strength=1.2)
M_DRESS_BLACK_T = mat("dress_b", (0.10, 0.08, 0.08, 1.0), 0.3, 0.45, emission=(0.10,0.08,0.08), emission_strength=0.5)
M_TUXEDO = mat("tuxedo", (0.08, 0.06, 0.06, 1.0), 0.4, 0.30, emission=(0.10,0.08,0.06), emission_strength=0.4)
M_SHIRT_TUXEDO = mat("tux_shirt", (0.95, 0.92, 0.88, 1.0), 0.0, 0.60, emission=(0.92,0.90,0.88), emission_strength=0.7)
M_BOWTIE = mat("bowtie", (0.10, 0.08, 0.08, 1.0), 0.5, 0.25)
M_HAIR_BLACK_T = mat("hair", (0.05, 0.04, 0.03, 1.0), 0.0, 0.85)
M_HAIR_GOMINA = mat("hair_g", (0.10, 0.06, 0.04, 1.0), 0.7, 0.15, emission=(0.10,0.06,0.04), emission_strength=0.4)
M_LIPS_RED = mat("lips", (0.95, 0.18, 0.25, 1.0), 0.0, 0.30, emission=(0.90,0.18,0.22), emission_strength=1.5)
M_SHOES_BLACK = mat("shoes_b", (0.08, 0.06, 0.06, 1.0), 0.7, 0.20, emission=(0.10,0.08,0.06), emission_strength=0.4)
M_STOCKINGS = mat("stockings", (0.30, 0.20, 0.20, 1.0), 0.0, 0.45, emission=(0.30,0.20,0.20), emission_strength=0.4, alpha=0.85)

# Rose in mouth (signature)
M_ROSE_MOUTH = mat("rose_m", (0.95, 0.18, 0.20, 1.0), 0.0, 0.40, emission=(0.92,0.18,0.18), emission_strength=2.5)

# Instruments
M_BANDONEON = mat("band", (0.20, 0.15, 0.10, 1.0), 0.3, 0.45, emission=(0.18,0.13,0.08), emission_strength=0.6)
M_BANDONEON_KEYS = mat("band_k", (0.95, 0.92, 0.88, 1.0), 0.0, 0.40, emission=(0.85,0.82,0.78), emission_strength=0.7)
M_VIOLIN_WOOD = mat("vio", (0.55, 0.30, 0.15, 1.0), 0.3, 0.35, emission=(0.50,0.28,0.13), emission_strength=0.6)
M_VIOLIN_STRING = mat("vio_s", (0.85, 0.85, 0.92, 1.0), 0.7, 0.20, emission=(0.78,0.78,0.85), emission_strength=0.5)
M_PIANO_BLACK = mat("piano_b", (0.10, 0.08, 0.08, 1.0), 0.7, 0.20, emission=(0.10,0.08,0.08), emission_strength=0.5)
M_PIANO_WHITE_KEY = mat("piano_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.40)
M_PIANO_BLACK_KEY = mat("piano_bk", (0.08, 0.06, 0.06, 1.0), 0.5, 0.30)
M_BASS_WOOD = mat("bass", (0.55, 0.30, 0.15, 1.0), 0.3, 0.40, emission=(0.50,0.28,0.13), emission_strength=0.6)

# Candles + fire
M_CANDELABRA = mat("cand", (0.95, 0.72, 0.25, 1.0), 0.95, 0.18, emission=(0.92,0.70,0.22), emission_strength=1.5)
M_CANDLE_WAX = mat("wax", (1.0, 0.92, 0.78, 1.0), 0.0, 0.40, emission=(0.92,0.85,0.75), emission_strength=0.8)
M_FLAME = mat("flame", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.30), emission_strength=18.0)
M_FLAME_OUTER = mat("flame_o", (1.0, 0.45, 0.15, 1.0), 0.0, 0.10, emission=(1.0,0.45,0.15), emission_strength=15.0)

# Spectator tables
M_TABLE_WOOD = mat("table_w", (0.30, 0.18, 0.10, 1.0), 0.0, 0.55)
M_TABLECLOTH = mat("table_c", (0.55, 0.18, 0.20, 1.0), 0.0, 0.65, emission=(0.50,0.18,0.20), emission_strength=0.7)
M_WINE_GLASS = mat("wine_g", (0.85, 0.92, 0.95, 0.65), 0.4, 0.10, emission=(0.78,0.85,0.92), emission_strength=1.0, alpha=0.65)
M_WINE_RED = mat("wine_r", (0.55, 0.10, 0.15, 1.0), 0.0, 0.30, emission=(0.50,0.10,0.13), emission_strength=2.0)

# Argentine flag (signature)
M_FLAG_BLUE = mat("flag_b", (0.50, 0.78, 0.92, 1.0), 0.0, 0.45, emission=(0.45,0.72,0.88), emission_strength=1.0)
M_FLAG_WHITE = mat("flag_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.82), emission_strength=0.7)
M_FLAG_SUN = mat("flag_sun", (1.0, 0.85, 0.30, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.28), emission_strength=1.5)

# Particles
M_ROSE_PETAL_R = mat("rose_pr", (0.95, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.90,0.18,0.18), emission_strength=2.5)
M_ROSE_PETAL_D = mat("rose_pd", (0.78, 0.10, 0.15, 1.0), 0.0, 0.45, emission=(0.72,0.10,0.13), emission_strength=2.7)
M_CANDLE_SPARK = mat("c_spark", (1.0, 0.78, 0.35, 1.0), 0.0, 0.10, emission=(1.0,0.78,0.35), emission_strength=22.0)
M_CANDLE_SPARK_GOLD = mat("c_spark_g", (1.0, 0.92, 0.45, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.45), emission_strength=20.0)

# ============ SKY night ambient ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)

# ============ WALLS (cabaret enclosed) ============
# Back wall
beveled_cube("wall_back", (40, 1, 12), bevel_offset=0.10, loc=(0, 22, 6), mat_=M_WALL_BURGUNDY)
# Side walls
for side in (-1, 1):
    beveled_cube(f"wall_side_{side}", (1, 30, 12), bevel_offset=0.10,
                 loc=(side*20, 7, 6), mat_=M_WALL_BURGUNDY)
# Floor extension behind/around
beveled_cube("wall_front", (40, 1, 12), bevel_offset=0.10, loc=(0, -8, 6), mat_=M_WALL_BURGUNDY)

# Gold trim around walls (signature art deco)
for ti in range(40):
    tx = (ti - 19.5) * 1.0
    cyl(f"trim_b_{ti}", r=0.10, depth=0.40, segs=12, loc=(tx, 21.4, 3.0), mat_=M_WALL_GOLD)
    cyl(f"trim_b_t_{ti}", r=0.10, depth=0.40, segs=12, loc=(tx, 21.4, 8.0), mat_=M_WALL_GOLD)

# 6 LARGE MIRRORS on walls (signature)
mirrors = []
for mi in range(6):
    side_x = (mi % 2) * 2 - 1  # alternate sides
    my = -5 + (mi // 2) * 9
    # Mirror frame
    beveled_cube(f"mirror_frame{mi}", (0.3, 2.5, 4.0), bevel_offset=0.08,
                 loc=(side_x*19.6, my, 5.5), mat_=M_WALL_GOLD)
    # Mirror surface
    m = beveled_cube(f"mirror{mi}", (0.1, 2.2, 3.6), bevel_offset=0.05,
                     loc=(side_x*19.5, my, 5.5), mat_=M_MIRROR)
    mirrors.append(m)

# 8 COLUMNS art deco (signature)
for ci in range(8):
    cx_c = (ci % 4 - 1.5) * 11
    cy_c = (ci // 4) * 26 - 6
    # Column shaft
    cyl(f"col{ci}", r=0.45, depth=11, segs=18, loc=(cx_c, cy_c, 5.5), mat_=M_COLUMN)
    # Column base
    cyl(f"col_base{ci}", r=0.65, depth=0.40, segs=18, loc=(cx_c, cy_c, 0.20), mat_=M_WALL_GOLD)
    # Column capital
    cyl(f"col_cap{ci}", r=0.65, depth=0.40, segs=18, loc=(cx_c, cy_c, 11.0), mat_=M_WALL_GOLD)
    # Geometric art deco pattern
    for pi in range(3):
        beveled_cube(f"col_pat{ci}_{pi}", (0.50, 0.05, 0.50), bevel_offset=0.04,
                     loc=(cx_c, cy_c - 0.50, 10.5 - pi*0.65), mat_=M_WALL_GOLD)

# ============ ONE clean wood floor ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_AMBIENT)
# Polished wood dance floor (signature)
floor_main = beveled_cube("floor_main", (35, 28, 0.30), bevel_offset=0.06,
                          loc=(0, 7, 0.10), mat_=M_FLOOR)
# Floor planks
for pi in range(35):
    px = (pi - 17) * 1.0
    beveled_cube(f"plank{pi}", (0.95, 28, 0.04), bevel_offset=0.01,
                 loc=(px, 7, 0.27), mat_=M_FLOOR_GLOSS if pi % 2 == 0 else M_FLOOR)
# Decorative pattern center (signature)
for ri in range(3):
    cyl(f"floor_ring{ri}", r=8 - ri*2, depth=0.02, segs=32,
        loc=(0, 7, 0.28), mat_=M_FLOOR_LINE)

# ============ STAGE curved bois (signature) ============
stage_e = empty("stage", loc=(0, 18, 0))
# Curved stage platform
for sa_seg in range(15):
    sa = math.pi * 0.4 - (sa_seg / 14.0) * math.pi * 0.8
    sx = math.cos(sa) * 8
    sy = math.sin(sa) * 4
    beveled_cube(f"stage_seg{sa_seg}", (1.2, 2.0, 0.8), bevel_offset=0.06,
                 loc=(sx, sy, 0.40), parent=stage_e, mat_=M_STAGE)
# Curtain backdrop massive
for cu in range(12):
    cua = math.pi * 0.5 - (cu / 11.0) * math.pi
    cx_cu = math.cos(cua) * 9
    cy_cu = math.sin(cua) * 4.5
    beveled_cube(f"curt{cu}", (0.6, 0.20, 8), bevel_offset=0.04,
                 loc=(cx_cu, cy_cu + 1.0, 5), parent=stage_e, mat_=M_CURTAIN)
# Stage spotlight (gold)
for sl in range(3):
    cyl(f"spot{sl}", r=0.40, depth=0.30, segs=14, loc=((sl-1)*3, 0, 10),
        parent=stage_e, mat_=M_CANDELABRA)
    # Light cone
    smooth_cone(f"spot_light{sl}", r1=0.10, r2=3.0, depth=5, segs=14,
                loc=((sl-1)*3, 0, 7.5), parent=stage_e,
                mat_=mat(f"light_c{sl}", (1.0, 0.85, 0.45, 1.0), 0, 0.30,
                          emission=(1.0,0.85,0.45), emission_strength=2.5, alpha=0.35))

# ============ ARGENTINE FLAG behind stage (signature) ============
flag_e = empty("flag", (0, 22, 9))
# 3 horizontal bands
beveled_cube("flag_top", (5, 0.10, 0.6), bevel_offset=0.04, loc=(0, 0, 0.6),
             parent=flag_e, mat_=M_FLAG_BLUE)
beveled_cube("flag_mid", (5, 0.10, 0.6), bevel_offset=0.04, loc=(0, 0, 0),
             parent=flag_e, mat_=M_FLAG_WHITE)
beveled_cube("flag_bot", (5, 0.10, 0.6), bevel_offset=0.04, loc=(0, 0, -0.6),
             parent=flag_e, mat_=M_FLAG_BLUE)
# Sun of May center (signature)
smooth_sphere("flag_sun", r=0.30, loc=(0, -0.05, 0), parent=flag_e, mat_=M_FLAG_SUN)
# Sun rays
for ri in range(16):
    ra = (ri / 16.0) * math.pi * 2
    beveled_cube(f"flag_ray{ri}", (0.10, 0.03, 0.20), bevel_offset=0.02,
                 loc=(0.40*math.cos(ra), -0.06, 0.40*math.sin(ra)),
                 parent=flag_e, mat_=M_FLAG_SUN).rotation_euler = (ra, 0, 0)

# ============ 4 TANGO COUPLES (signature close embrace) ============
def make_tango_couple(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # ============ MAN (TUXEDO) ============
    man_e = empty(f"{name}_man", (0.15, 0, 0), parent=base)
    # Legs in stride
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_m_hip{side_idx}", (side*0.13, 0, 0.85), parent=man_e)
        # Stride pose
        leg_rx = math.radians(15 if side_idx == 0 else -10)
        hip.rotation_euler = (leg_rx, 0, 0)
        cyl(f"{name}_m_thigh{side_idx}", r=0.11, depth=0.50, segs=12,
            loc=(0, 0, -0.25), parent=hip, mat_=M_TUXEDO)
        cyl(f"{name}_m_calf{side_idx}", r=0.09, depth=0.50, segs=12,
            loc=(0, 0, -0.75), parent=hip, mat_=M_TUXEDO)
        # Polished shoes
        beveled_cube(f"{name}_m_shoe{side_idx}", (0.14, 0.30, 0.08), bevel_offset=0.02,
                     loc=(0, 0.06, -1.0), parent=hip, mat_=M_SHOES_BLACK)
    # Tuxedo pants + jacket
    smooth_cone(f"{name}_m_pants", r1=0.30, r2=0.22, depth=0.45, segs=14,
                loc=(0, 0, 1.0), parent=man_e, mat_=M_TUXEDO)
    # Belt
    cyl(f"{name}_m_belt", r=0.30, depth=0.05, segs=14,
        loc=(0, 0, 1.20), parent=man_e, mat_=M_TUXEDO)
    # White shirt visible
    beveled_cube(f"{name}_m_shirt", (0.40, 0.22, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 1.50), parent=man_e, mat_=M_SHIRT_TUXEDO)
    # Tuxedo jacket V open
    for side in (-1, 1):
        beveled_cube(f"{name}_m_jacket{side}", (0.10, 0.10, 0.55), bevel_offset=0.03,
                     loc=(side*0.16, -0.10, 1.50), parent=man_e, mat_=M_TUXEDO)
    # Bow tie (signature)
    beveled_cube(f"{name}_m_bow", (0.14, 0.04, 0.06), bevel_offset=0.01,
                 loc=(0, -0.13, 1.80), parent=man_e, mat_=M_BOWTIE)
    # Neck
    cyl(f"{name}_m_neck", r=0.09, depth=0.15, segs=10, loc=(0, 0, 1.88),
        parent=man_e, mat_=M_SKIN_ARG)
    # Head
    m_head_e = empty(f"{name}_m_he", (0, 0, 2.05), parent=man_e)
    smooth_sphere(f"{name}_m_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=m_head_e, mat_=M_SKIN_ARG)
    # GOMINA slicked back hair (signature tango)
    smooth_sphere(f"{name}_m_hair", r=0.19, loc=(0, 0.04, 0.06),
                  parent=m_head_e, mat_=M_HAIR_GOMINA, scale=(1, 1, 0.7))
    # Mustache thin
    smooth_sphere(f"{name}_m_must", r=0.07, loc=(0, -0.16, -0.04),
                  parent=m_head_e, mat_=M_HAIR_BLACK_T, scale=(1.8, 0.4, 0.3))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_m_eye{side}", r=0.022,
                      loc=(side*0.07, -0.14, 0.02), parent=m_head_e,
                      mat_=mat(f"{name}_m_ew{side}", (0.10, 0.05, 0.04, 1), 0, 0.4,
                                emission=(0.30, 0.15, 0.08), emission_strength=1.5))
    # ROSE IN MOUTH (signature tango)
    rose_e = empty(f"{name}_m_rose_e", (0, -0.20, -0.06), parent=m_head_e)
    smooth_sphere(f"{name}_m_rose", r=0.08, loc=(0, 0, 0),
                  parent=rose_e, mat_=M_ROSE_MOUTH, scale=(1, 1, 0.8))
    # Rose stem
    cyl(f"{name}_m_stem", r=0.012, depth=0.25, segs=8, loc=(0, -0.10, 0),
        parent=rose_e, mat_=mat(f"{name}_stem_m", (0.30, 0.55, 0.30, 1), 0, 0.5)).rotation_euler = (math.radians(90), 0, 0)
    # ============ WOMAN (RED DRESS) ============
    woman_e = empty(f"{name}_woman", (-0.15, 0, 0), parent=base)
    # Legs (signature one extended)
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_w_hip{side_idx}", (side*0.12, 0, 0.85), parent=woman_e)
        # POINTED leg signature
        if side_idx == 0:
            hip.rotation_euler = (math.radians(-15), 0, math.radians(-30))
        else:
            hip.rotation_euler = (math.radians(15), 0, 0)
        cyl(f"{name}_w_thigh{side_idx}", r=0.09, depth=0.55, segs=12,
            loc=(0, 0, -0.28), parent=hip, mat_=M_STOCKINGS)
        cyl(f"{name}_w_calf{side_idx}", r=0.07, depth=0.55, segs=12,
            loc=(0, 0, -0.85), parent=hip, mat_=M_STOCKINGS)
        # High heels red (signature)
        beveled_cube(f"{name}_w_heel{side_idx}", (0.10, 0.25, 0.06), bevel_offset=0.02,
                     loc=(0, 0.04, -1.13), parent=hip, mat_=M_DRESS_RED)
        cyl(f"{name}_w_pin{side_idx}", r=0.020, depth=0.10, segs=8,
            loc=(0, -0.10, -1.18), parent=hip, mat_=M_DRESS_RED)
    # Red dress (signature slit fendue)
    smooth_cone(f"{name}_w_dress", r1=0.45, r2=0.30, depth=1.6, segs=18,
                loc=(0, 0, 0.85), parent=woman_e, mat_=M_DRESS_RED)
    # Slit (open from leg)
    beveled_cube(f"{name}_w_slit", (0.20, 0.08, 1.2), bevel_offset=0.05,
                 loc=(-0.15, -0.20, 0.65), parent=woman_e, mat_=M_SKIN_ARG)
    # Belt
    cyl(f"{name}_w_belt", r=0.34, depth=0.06, segs=18,
        loc=(0, 0, 1.40), parent=woman_e, mat_=M_DRESS_BLACK_T)
    # Bare back top (open dress)
    beveled_cube(f"{name}_w_top", (0.36, 0.20, 0.55), bevel_offset=0.04,
                 loc=(0, 0, 1.75), parent=woman_e, mat_=M_DRESS_RED)
    # Spaghetti straps
    for side in (-1, 1):
        beveled_cube(f"{name}_w_strap{side}", (0.04, 0.04, 0.30), bevel_offset=0.01,
                     loc=(side*0.14, -0.10, 1.95), parent=woman_e, mat_=M_DRESS_RED)
    # Neck
    cyl(f"{name}_w_neck", r=0.08, depth=0.15, segs=10, loc=(0, 0, 2.05),
        parent=woman_e, mat_=M_SKIN_ARG)
    # Head
    w_head_e = empty(f"{name}_w_he", (0, 0, 2.22), parent=woman_e)
    smooth_sphere(f"{name}_w_head", r=0.17, segs=20, rings=14, loc=(0, 0, 0),
                  parent=w_head_e, mat_=M_SKIN_ARG)
    # Hair slicked bun (signature)
    smooth_sphere(f"{name}_w_hair", r=0.20, loc=(0, 0.05, 0.05),
                  parent=w_head_e, mat_=M_HAIR_BLACK_T, scale=(1, 1, 0.85))
    smooth_sphere(f"{name}_w_bun", r=0.15, loc=(0, 0.22, 0.05),
                  parent=w_head_e, mat_=M_HAIR_BLACK_T, scale=(1.2, 0.8, 1.2))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_w_eye{side}", r=0.025,
                      loc=(side*0.06, -0.13, 0.02), parent=w_head_e,
                      mat_=mat(f"{name}_w_ew{side}", (0.10, 0.05, 0.04, 1), 0, 0.4,
                                emission=(0.30, 0.15, 0.08), emission_strength=1.5))
    # RED LIPS signature
    beveled_cube(f"{name}_w_lips", (0.10, 0.04, 0.03), loc=(0, -0.17, -0.08),
                 parent=w_head_e, mat_=M_LIPS_RED)
    # Earrings dangling
    for side in (-1, 1):
        cyl(f"{name}_w_earring{side}", r=0.015, depth=0.18, segs=8,
            loc=(side*0.18, 0, -0.08), parent=w_head_e, mat_=M_FLAG_SUN)
        smooth_sphere(f"{name}_w_earring_b{side}", r=0.04, loc=(side*0.18, 0, -0.20),
                      parent=w_head_e, mat_=M_FLAG_SUN)
    # ============ EMBRACE (close embrace signature tango) ============
    # Man's right hand on woman's back, woman's left arm around man's shoulders
    # Man's right arm
    m_sh_r = empty(f"{name}_m_sh_r", (-0.28, 0, 1.78), parent=man_e)
    m_sh_r.rotation_euler = (math.radians(-100), 0, math.radians(60))
    cyl(f"{name}_m_uarm_r", r=0.07, depth=0.32, segs=12,
        loc=(0, 0, -0.17), parent=m_sh_r, mat_=M_TUXEDO)
    cyl(f"{name}_m_fa_r", r=0.06, depth=0.30, segs=10,
        loc=(0, 0, -0.45), parent=m_sh_r, mat_=M_SKIN_ARG)
    smooth_sphere(f"{name}_m_hand_r", r=0.07, loc=(0, 0, -0.62),
                  parent=m_sh_r, mat_=M_SKIN_ARG)
    # Man's left arm (holding woman's hand extended out)
    m_sh_l = empty(f"{name}_m_sh_l", (0.28, 0, 1.78), parent=man_e)
    m_sh_l.rotation_euler = (math.radians(-80), 0, math.radians(45))
    cyl(f"{name}_m_uarm_l", r=0.07, depth=0.32, segs=12,
        loc=(0, 0, -0.17), parent=m_sh_l, mat_=M_TUXEDO)
    cyl(f"{name}_m_fa_l", r=0.06, depth=0.30, segs=10,
        loc=(0, 0, -0.45), parent=m_sh_l, mat_=M_SKIN_ARG)
    smooth_sphere(f"{name}_m_hand_l", r=0.07, loc=(0, 0, -0.62),
                  parent=m_sh_l, mat_=M_SKIN_ARG)
    # Woman's left arm (around man's shoulders signature)
    w_sh_l = empty(f"{name}_w_sh_l", (0.30, 0, 1.95), parent=woman_e)
    w_sh_l.rotation_euler = (math.radians(-130), 0, math.radians(-50))
    cyl(f"{name}_w_uarm_l", r=0.06, depth=0.30, segs=12,
        loc=(0, 0, -0.15), parent=w_sh_l, mat_=M_SKIN_ARG)
    cyl(f"{name}_w_fa_l", r=0.05, depth=0.28, segs=10,
        loc=(0, 0, -0.42), parent=w_sh_l, mat_=M_SKIN_ARG)
    smooth_sphere(f"{name}_w_hand_l", r=0.06, loc=(0, 0, -0.58),
                  parent=w_sh_l, mat_=M_SKIN_ARG)
    # Woman's right hand (held by man's left, extended)
    w_sh_r = empty(f"{name}_w_sh_r", (-0.30, 0, 1.95), parent=woman_e)
    w_sh_r.rotation_euler = (math.radians(-90), 0, math.radians(45))
    cyl(f"{name}_w_uarm_r", r=0.06, depth=0.30, segs=12,
        loc=(0, 0, -0.15), parent=w_sh_r, mat_=M_SKIN_ARG)
    cyl(f"{name}_w_fa_r", r=0.05, depth=0.28, segs=10,
        loc=(0, 0, -0.42), parent=w_sh_r, mat_=M_SKIN_ARG)
    smooth_sphere(f"{name}_w_hand_r", r=0.06, loc=(0, 0, -0.58),
                  parent=w_sh_r, mat_=M_SKIN_ARG)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "m_head": m_head_e, "w_head": w_head_e}

couples = []
couple_specs = [
    ("couple1", (-8, 5, 0), math.radians(20)),
    ("couple2", (-3, 6, 0), math.radians(-15)),
    ("couple3", (3, 6, 0), math.radians(15)),
    ("couple4", (8, 5, 0), math.radians(-20)),
]
for spec in couple_specs:
    name, loc, fac = spec
    c = make_tango_couple(name, loc, facing=fac)
    couples.append(c)

# ============ 5 MUSICIANS on stage ============
def make_tango_musician(name, loc, instrument, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sitting body (for most) or standing (cantor)
    if instrument == "cantor":
        # Standing cantor
        smooth_cone(f"{name}_pants", r1=0.30, r2=0.22, depth=1.0, segs=14,
                    loc=(0, 0, 0.50), parent=base, mat_=M_TUXEDO)
    else:
        smooth_cone(f"{name}_pants", r1=0.30, r2=0.22, depth=0.50, segs=14,
                    loc=(0, 0, 0.25), parent=base, mat_=M_TUXEDO)
    # Shirt + jacket
    beveled_cube(f"{name}_shirt", (0.40, 0.22, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 0.95 if instrument != "cantor" else 1.55), parent=base, mat_=M_SHIRT_TUXEDO)
    # Jacket
    for side in (-1, 1):
        beveled_cube(f"{name}_jacket{side}", (0.08, 0.08, 0.50), bevel_offset=0.02,
                     loc=(side*0.16, -0.10, 0.95 if instrument != "cantor" else 1.55), parent=base, mat_=M_TUXEDO)
    # Bow tie
    beveled_cube(f"{name}_bow", (0.12, 0.04, 0.05), bevel_offset=0.01,
                 loc=(0, -0.12, 1.18 if instrument != "cantor" else 1.78), parent=base, mat_=M_BOWTIE)
    # Neck
    cyl(f"{name}_neck", r=0.09, depth=0.15, segs=10,
        loc=(0, 0, 1.32 if instrument != "cantor" else 1.92), parent=base, mat_=M_SKIN_ARG)
    head_e = empty(f"{name}_he", (0, 0, 1.50 if instrument != "cantor" else 2.10), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_ARG)
    smooth_sphere(f"{name}_hair", r=0.19, loc=(0, 0.04, 0.06),
                  parent=head_e, mat_=M_HAIR_GOMINA, scale=(1, 1, 0.7))
    # Mustache
    smooth_sphere(f"{name}_must", r=0.07, loc=(0, -0.16, -0.04),
                  parent=head_e, mat_=M_HAIR_BLACK_T, scale=(1.7, 0.4, 0.3))
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.14, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.10, 0.05, 0.04, 1), 0, 0.4,
                                emission=(0.30, 0.15, 0.08), emission_strength=1.5))
    # Instrument
    inst_e = empty(f"{name}_inst_e", (0, -0.40, 0.80 if instrument != "cantor" else 0), parent=base)
    arms_e = []
    if instrument == "bandoneon":
        # Bandoneon (signature accordion-like)
        for bi in range(8):
            beveled_cube(f"{name}_band_b{bi}", (0.35, 0.04, 0.30), bevel_offset=0.02,
                         loc=(0, (bi - 3.5)*0.05, 0), parent=inst_e, mat_=M_BANDONEON)
        # End blocks
        beveled_cube(f"{name}_band_l", (0.35, 0.06, 0.40), bevel_offset=0.02,
                     loc=(0, -0.25, 0), parent=inst_e, mat_=M_BANDONEON)
        beveled_cube(f"{name}_band_r", (0.35, 0.06, 0.40), bevel_offset=0.02,
                     loc=(0, 0.25, 0), parent=inst_e, mat_=M_BANDONEON)
        # Buttons (signature mother of pearl)
        for ki in range(12):
            beveled_cube(f"{name}_band_k{ki}", (0.025, 0.04, 0.025), bevel_offset=0.005,
                         loc=(0.06 + (ki%6)*0.03 - 0.10, 0.27, -0.10 + (ki//6)*0.06),
                         parent=inst_e, mat_=M_BANDONEON_KEYS)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.18), parent=base)
            sh.rotation_euler = (math.radians(-95), 0, math.radians(side*-20))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_TUXEDO)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_ARG)
            arms_e.append(sh)
    elif instrument == "violin":
        # Violin tucked under chin
        smooth_sphere(f"{name}_vio_body", r=0.20, segs=18, rings=12,
                      loc=(0, 0, 0.40), parent=inst_e, mat_=M_VIOLIN_WOOD,
                      scale=(1, 0.4, 1.5))
        beveled_cube(f"{name}_vio_neck", (0.04, 0.04, 0.50), bevel_offset=0.01,
                     loc=(0, -0.05, 0.70), parent=inst_e, mat_=M_VIOLIN_WOOD)
        # Strings
        for st in range(4):
            cyl(f"{name}_vio_str{st}", r=0.003, depth=0.85, segs=4,
                loc=((st-1.5)*0.012, -0.10, 0.50), parent=inst_e, mat_=M_VIOLIN_STRING)
        # Bow
        beveled_cube(f"{name}_vio_bow", (0.015, 0.015, 0.55), bevel_offset=0.005,
                     loc=(0.30, -0.10, 0.40), parent=inst_e, mat_=M_VIOLIN_WOOD)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.18), parent=base)
            sh.rotation_euler = (math.radians(-110 if side_idx == 0 else -90), 0, math.radians(side*-15))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_TUXEDO)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_ARG)
            arms_e.append(sh)
    elif instrument == "piano":
        # Piano signature large
        beveled_cube(f"{name}_piano_body", (1.5, 0.8, 0.40), bevel_offset=0.04,
                     loc=(0, 0.20, 0), parent=inst_e, mat_=M_PIANO_BLACK)
        # Keys
        for ki in range(16):
            beveled_cube(f"{name}_piano_k{ki}", (0.08, 0.06, 0.04), bevel_offset=0.005,
                         loc=((ki - 7.5)*0.085, -0.05, 0.22),
                         parent=inst_e, mat_=M_PIANO_WHITE_KEY)
        # Black keys
        for ki in range(10):
            beveled_cube(f"{name}_piano_bk{ki}", (0.04, 0.06, 0.05), bevel_offset=0.005,
                         loc=((ki - 4.5)*0.13, -0.05, 0.245),
                         parent=inst_e, mat_=M_PIANO_BLACK_KEY)
        # Music stand
        beveled_cube(f"{name}_piano_stand", (1.0, 0.05, 0.50), bevel_offset=0.02,
                     loc=(0, 0.40, 0.50), parent=inst_e, mat_=M_PIANO_BLACK)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.18), parent=base)
            sh.rotation_euler = (math.radians(-95), 0, math.radians(side*-25))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_TUXEDO)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_ARG)
            arms_e.append(sh)
    elif instrument == "bass":
        # Double bass (signature standing)
        smooth_sphere(f"{name}_bass_body", r=0.45, segs=20, rings=14,
                      loc=(0.50, 0, 1.0), parent=base, mat_=M_BASS_WOOD,
                      scale=(0.85, 0.4, 1.5))
        # Long neck
        beveled_cube(f"{name}_bass_neck", (0.08, 0.06, 1.2), bevel_offset=0.02,
                     loc=(0.50, -0.10, 2.3), parent=base, mat_=M_BASS_WOOD)
        # 4 strings
        for st in range(4):
            cyl(f"{name}_bass_str{st}", r=0.005, depth=2.5, segs=4,
                loc=(0.50 + (st-1.5)*0.012, -0.20, 1.7), parent=base, mat_=M_VIOLIN_STRING)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.18), parent=base)
            sh.rotation_euler = (math.radians(-110), 0, math.radians(side*-30))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_TUXEDO)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_ARG)
            arms_e.append(sh)
    else:  # cantor
        # Hands clasped
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.78), parent=base)
            sh.rotation_euler = (math.radians(-90), 0, math.radians(side*-20))
            cyl(f"{name}_uarm{side_idx}", r=0.08, depth=0.35, segs=10,
                loc=(0, 0, -0.18), parent=sh, mat_=M_TUXEDO)
            cyl(f"{name}_fa{side_idx}", r=0.07, depth=0.32, segs=10,
                loc=(0, 0, -0.50), parent=sh, mat_=M_SKIN_ARG)
            smooth_sphere(f"{name}_hand{side_idx}", r=0.08, loc=(0, 0, -0.68),
                          parent=sh, mat_=M_SKIN_ARG)
            arms_e.append(sh)
        # Singing mouth open
        beveled_cube(f"{name}_mouth", (0.08, 0.04, 0.10), loc=(0, -0.17, -0.08),
                     parent=head_e, mat_=mat(f"{name}_mouth_m", (0.20, 0.05, 0.05, 1), 0, 0.5))
        # Microphone
        cyl(f"{name}_mic_stand", r=0.04, depth=1.8, segs=10, loc=(0, -0.35, 0.9),
            parent=base, mat_=M_PIANO_BLACK)
        smooth_sphere(f"{name}_mic", r=0.06, loc=(0, -0.35, 1.85),
                      parent=base, mat_=M_PIANO_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

musicians = []
mus_specs = [
    ("cantor", (0, 16, 0.8), "cantor", math.radians(0)),
    ("bandoneon", (-5, 17, 0.8), "bandoneon", math.radians(0)),
    ("violin", (-3, 18, 0.8), "violin", math.radians(0)),
    ("piano", (3, 18, 0.8), "piano", math.radians(0)),
    ("bass", (5, 17, 0.8), "bass", math.radians(0)),
]
for spec in mus_specs:
    name, loc, inst, fac = spec
    m = make_tango_musician(name, loc, inst, facing=fac)
    musicians.append(m)

# ============ 8 SPECTATORS at tables ============
def make_spectator(name, loc, is_woman=True, dress_mat=M_DRESS_RED, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_cone(f"{name}_legs", r1=0.30, r2=0.24, depth=0.55, segs=14,
                loc=(0, 0, 0.30), parent=base, mat_=dress_mat if is_woman else M_TUXEDO)
    # Torso
    beveled_cube(f"{name}_torso", (0.40, 0.22, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 0.95), parent=base, mat_=dress_mat if is_woman else M_SHIRT_TUXEDO)
    if not is_woman:
        # Jacket
        for side in (-1, 1):
            beveled_cube(f"{name}_jacket{side}", (0.08, 0.08, 0.50),
                         loc=(side*0.16, -0.10, 0.95), parent=base, mat_=M_TUXEDO)
    # Neck
    cyl(f"{name}_neck", r=0.08, depth=0.15, segs=10, loc=(0, 0, 1.30),
        parent=base, mat_=M_SKIN_ARG)
    head_e = empty(f"{name}_he", (0, 0, 1.48), parent=base)
    smooth_sphere(f"{name}_head", r=0.17, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_ARG)
    smooth_sphere(f"{name}_hair", r=0.19, loc=(0, 0.05, 0.05),
                  parent=head_e, mat_=M_HAIR_BLACK_T, scale=(1, 1, 0.85))
    if is_woman:
        # Bun
        smooth_sphere(f"{name}_bun", r=0.13, loc=(0, 0.22, 0.05),
                      parent=head_e, mat_=M_HAIR_BLACK_T)
        # Red lips
        beveled_cube(f"{name}_lips", (0.08, 0.04, 0.025), loc=(0, -0.16, -0.08),
                     parent=head_e, mat_=M_LIPS_RED)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.13, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.10, 0.05, 0.04, 1), 0, 0.4,
                                emission=(0.30, 0.15, 0.08), emission_strength=1.5))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

spectators = []
spec_specs = [
    ("sp1", (-13, -1, 0.5), True, M_DRESS_RED, math.radians(40)),
    ("sp2", (-13, -4, 0.5), False, M_TUXEDO, math.radians(40)),
    ("sp3", (13, -1, 0.5), True, M_DRESS_BLACK_T, math.radians(-40)),
    ("sp4", (13, -4, 0.5), False, M_TUXEDO, math.radians(-40)),
    ("sp5", (-13, 8, 0.5), True, M_DRESS_BLACK_T, math.radians(70)),
    ("sp6", (-13, 11, 0.5), False, M_TUXEDO, math.radians(70)),
    ("sp7", (13, 8, 0.5), True, M_DRESS_RED, math.radians(-70)),
    ("sp8", (13, 11, 0.5), False, M_TUXEDO, math.radians(-70)),
]
for spec in spec_specs:
    name, loc, is_w, dress, fac = spec
    s = make_spectator(name, loc, is_woman=is_w, dress_mat=dress, facing=fac)
    spectators.append(s)

# ============ TABLES + WINE for spectators ============
table_pos = [(-12, -2.5, 0), (12, -2.5, 0), (-12, 9.5, 0), (12, 9.5, 0)]
for ti, (tx, ty, tz) in enumerate(table_pos):
    t_e = empty(f"table{ti}", (tx, ty, tz))
    # Table top
    cyl(f"t_top{ti}", r=0.70, depth=0.05, segs=20, loc=(0, 0, 1.0),
        parent=t_e, mat_=M_TABLECLOTH)
    # Single leg
    cyl(f"t_leg{ti}", r=0.06, depth=1.0, segs=12, loc=(0, 0, 0.50),
        parent=t_e, mat_=M_PIANO_BLACK)
    # Base
    cyl(f"t_base{ti}", r=0.30, depth=0.05, segs=14, loc=(0, 0, 0.05),
        parent=t_e, mat_=M_PIANO_BLACK)
    # 2 wine glasses
    for gi in range(2):
        ga = gi * math.pi
        glass_e = empty(f"t_g_e{ti}_{gi}", (math.cos(ga)*0.30, math.sin(ga)*0.30, 1.05), parent=t_e)
        cyl(f"t_g_stem{ti}_{gi}", r=0.015, depth=0.15, segs=10, loc=(0, 0, 0),
            parent=glass_e, mat_=M_WINE_GLASS)
        cyl(f"t_g_bowl{ti}_{gi}", r=0.06, depth=0.10, segs=14, loc=(0, 0, 0.10),
            parent=glass_e, mat_=M_WINE_GLASS)
        # Wine
        cyl(f"t_g_wine{ti}_{gi}", r=0.055, depth=0.08, segs=12, loc=(0, 0, 0.10),
            parent=glass_e, mat_=M_WINE_RED)
    # CANDLE on table (signature)
    cand_e = empty(f"t_cand{ti}", (0, 0, 1.05), parent=t_e)
    cyl(f"t_cand_b{ti}", r=0.06, depth=0.30, segs=12, loc=(0, 0, 0.15),
        parent=cand_e, mat_=M_CANDLE_WAX)
    # Flame
    flame_t = empty(f"t_cand_fl{ti}", (0, 0, 0.32), parent=cand_e)
    smooth_cone(f"t_cand_fl_o{ti}", r1=0.05, r2=0.005, depth=0.15, segs=10,
                loc=(0, 0, 0.075), parent=flame_t, mat_=M_FLAME_OUTER)
    smooth_cone(f"t_cand_fl_c{ti}", r1=0.025, r2=0.001, depth=0.10, segs=10,
                loc=(0, 0, 0.05), parent=flame_t, mat_=M_FLAME)

# ============ CANDELABRAS (signature gold candle holders) ============
candelabras = []
candelabra_pos = [(-15, 6, 0), (15, 6, 0), (-15, 14, 0), (15, 14, 0),
                  (-7, 18, 0), (7, 18, 0)]
for ci, (cx, cy, cz) in enumerate(candelabra_pos):
    c_e = empty(f"cand{ci}", (cx, cy, cz))
    # Base
    cyl(f"cand_b{ci}", r=0.30, depth=0.20, segs=18, loc=(0, 0, 0.10),
        parent=c_e, mat_=M_CANDELABRA)
    # Tall pole
    cyl(f"cand_p{ci}", r=0.08, depth=2.5, segs=12, loc=(0, 0, 1.45),
        parent=c_e, mat_=M_CANDELABRA)
    # 5 arms (signature candelabra)
    for ai in range(5):
        aa = (ai - 2) * 0.30
        arm_e = empty(f"cand_a{ci}_{ai}", (0, 0, 2.65), parent=c_e)
        arm_e.rotation_euler = (0, 0, aa)
        # Curved arm
        for sk in range(3):
            sk_t = sk / 3.0
            cyl(f"cand_arm{ci}_{ai}_{sk}", r=0.04, depth=0.18, segs=8,
                loc=(0.15*sk_t, 0, 0.15*(1 - sk_t)), parent=arm_e, mat_=M_CANDELABRA).rotation_euler = (0, math.radians(45*(1-sk_t)), 0)
        # Candle
        cyl(f"cand_w{ci}_{ai}", r=0.04, depth=0.20, segs=10,
            loc=(0.45, 0, 0.10), parent=arm_e, mat_=M_CANDLE_WAX)
        # Flame
        flame_c = empty(f"cand_fl_e{ci}_{ai}", (0.45, 0, 0.25), parent=arm_e)
        smooth_cone(f"cand_fl_o{ci}_{ai}", r1=0.06, r2=0.005, depth=0.15, segs=10,
                    loc=(0, 0, 0.075), parent=flame_c, mat_=M_FLAME_OUTER)
        smooth_cone(f"cand_fl_c{ci}_{ai}", r1=0.03, r2=0.001, depth=0.10, segs=10,
                    loc=(0, 0, 0.05), parent=flame_c, mat_=M_FLAME)
    # Center candle on top
    cyl(f"cand_top_w{ci}", r=0.05, depth=0.30, segs=12, loc=(0, 0, 2.85),
        parent=c_e, mat_=M_CANDLE_WAX)
    flame_top = empty(f"cand_top_fl{ci}", (0, 0, 3.10), parent=c_e)
    smooth_cone(f"cand_top_fl_o{ci}", r1=0.07, r2=0.005, depth=0.18, segs=10,
                loc=(0, 0, 0.09), parent=flame_top, mat_=M_FLAME_OUTER)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    candelabras.append(c_e)

# ============================================================
# ⭐ 600 ROSE PETALS + 400 CANDLE SPARKLES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
rose_petals = []
rose_colors = [M_ROSE_PETAL_R, M_ROSE_PETAL_D]
for i in range(600):
    px = random.uniform(-18, 18)
    py = random.uniform(-7, 20)
    pz = random.uniform(0.5, 11)
    col = rose_colors[i % 2]
    p_obj = smooth_sphere(f"rose{i}", r=random.uniform(0.10, 0.16), segs=10, rings=6,
                          loc=(px, py, pz), mat_=col, scale=(1.5, 0.6, 0.15))
    p_obj.rotation_euler = (random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2))
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_speed"] = random.uniform(0.3, 1.0)
    p_obj["_drift_x"] = random.uniform(-1.6, 1.6)
    p_obj["_drift_y"] = random.uniform(-1.6, 1.6)
    rose_petals.append(p_obj)

# 400 candle sparkles
spark_colors = [M_CANDLE_SPARK, M_CANDLE_SPARK_GOLD]
candle_sparkles = []
for i in range(400):
    # Concentrate near candelabras
    if i < 200:
        ci_idx = i % len(candelabra_pos)
        cx, cy, _ = candelabra_pos[ci_idx]
        px = cx + random.uniform(-1.0, 1.0)
        py = cy + random.uniform(-1.0, 1.0)
        pz = random.uniform(2.5, 5)
    else:
        px = random.uniform(-15, 15)
        py = random.uniform(-5, 18)
        pz = random.uniform(1, 8)
    col = spark_colors[i % 2]
    s_obj = smooth_sphere(f"cs{i}", r=random.uniform(0.04, 0.08), segs=8, rings=6,
                          loc=(px, py, pz), mat_=col)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(0.3, 0.8)
    s_obj["_amp_y"] = random.uniform(0.3, 0.8)
    s_obj["_amp_z"] = random.uniform(0.5, 1.5)
    s_obj["_speed"] = random.uniform(0.6, 1.2)
    candle_sparkles.append(s_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Tango couples slow embrace + leg flicks
for c in couples:
    phase = c["root"]["_phase"]
    base_z = c["root"].location.z
    base_rz = c["root"].rotation_euler.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Slow majestic body sway
        c["root"].location.z = base_z + abs(math.sin(t * 1.2 + phase)) * 0.08
        c["root"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(4),
                                     math.cos(t * 0.7 + phase) * math.radians(3),
                                     base_rz + math.sin(t * 0.5 + phase) * math.radians(25))
        c["root"].keyframe_insert("location", frame=f)
        c["root"].keyframe_insert("rotation_euler", frame=f)
        # Heads close together
        c["m_head"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(3), 0,
                                        math.sin(t * 0.8 + phase) * math.radians(10))
        c["m_head"].keyframe_insert("rotation_euler", frame=f)
        c["w_head"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(3), 0,
                                        -math.sin(t * 0.8 + phase) * math.radians(10))
        c["w_head"].keyframe_insert("rotation_euler", frame=f)

# Musicians play
for m in musicians:
    phase = m["root"]["_phase"]
    base_z = m["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        m["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        m["root"].keyframe_insert("location", frame=f)
        for ai, arm in enumerate(m["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 3.5 + phase + ai * math.pi) * math.radians(12)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(6), 0,
                                    math.sin(t * 1.2 + phase) * math.radians(15))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Spectators applaud
for s in spectators:
    phase = s["root"]["_phase"]
    base_z = s["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.03
        s["root"].keyframe_insert("location", frame=f)
        s["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(4), 0,
                                    math.sin(t * 0.7 + phase) * math.radians(15))
        s["he"].keyframe_insert("rotation_euler", frame=f)

# Candelabra flames flicker
for c in candelabras:
    phase = c["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        for obj in bpy.data.objects:
            if obj.name.startswith("cand_fl_e") and c.name in obj.name:
                s = 1 + math.sin(t * 6.0 + phase) * 0.20
                obj.scale = (s, s, s)
                obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 600 ROSE PETALS + 400 CANDLE SPARKLES (signature tango)
# ============================================================
for p in rose_petals:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    drift_x = p["_drift_x"]; drift_y = p["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        z = bz - (speed * t * 0.4) % 11
        x = bx + drift_x * math.sin(t * 1.3 + phase) * 0.6
        y = by + drift_y * math.cos(t * 1.1 + phase) * 0.6
        p.location = (x, y, max(0.05, z))
        p.rotation_euler = (phase + t * 1.7, phase + t * 1.5, phase + t * 2.0)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# 400 CANDLE SPARKLES vortex
for s in candle_sparkles:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        # Rise upward (sparkles ascending from flames)
        z = bz + (speed * t * 0.3) % 5
        s.location = (x, y, max(0.5, z))
        sc = 1 + math.sin(t * 5.0 + phase) * 0.4
        s.scale = (sc, sc, sc)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_argentina_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_argentinian_tango_milonga] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_argentinian_tango_milonga] ONE wood floor + cabaret walls + 6 mirrors + 8 columns + curved stage + Argentine flag + 4 tango couples close embrace + 5 musicians (cantor+bandoneon+violin+piano+bass) + 8 spectators + 4 tables wine + 6 candelabras + 600 ROSE + 400 CANDLE SPARKLES")
print("⭐ FIXES: 1 ground + 600 rose petals + 400 candle sparkles (signature tango mandatory) ⭐")
