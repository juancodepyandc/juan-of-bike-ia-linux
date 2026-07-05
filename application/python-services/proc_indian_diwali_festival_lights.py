"""
proc_indian_diwali_festival_lights.py — 260e procédural AuroraIA (125e qualité)
Diwali festival: Taj Mahal + 8 houses with arches + Ganesh gold statue + rangoli + 6 women in saris + 4 musicians + 4 men dhoti + masala + diyas + fireworks + 600 diyas + 400 jasmine
FIXES : 1 ground + 600 diya flames + 400 jasmine petals (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB260)

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

# Sky night purple with fireworks
M_SKY = mat("sky", (0.18, 0.10, 0.28, 1.0), 0.0, 0.7, emission=(0.18,0.10,0.28), emission_strength=1.0)
M_SKY_GOLD = mat("sky_g", (0.55, 0.32, 0.42, 1.0), 0.0, 0.7, emission=(0.55,0.32,0.42), emission_strength=1.3)
M_STAR = mat("star", (1.0, 0.95, 0.80, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.80), emission_strength=8.0)
M_MOON = mat("moon", (0.95, 0.92, 0.85, 1.0), 0.0, 0.20, emission=(0.92,0.88,0.82), emission_strength=4.0)

# Rangoli colors signature (multi-vivid)
M_RANGOLI_RED = mat("rg_r", (1.0, 0.18, 0.20, 1.0), 0.0, 0.55, emission=(0.95,0.18,0.20), emission_strength=2.5)
M_RANGOLI_ORANGE = mat("rg_o", (1.0, 0.55, 0.18, 1.0), 0.0, 0.55, emission=(0.95,0.55,0.18), emission_strength=2.5)
M_RANGOLI_YELLOW = mat("rg_y", (1.0, 0.92, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.88,0.20), emission_strength=2.5)
M_RANGOLI_GREEN = mat("rg_g", (0.20, 0.95, 0.30, 1.0), 0.0, 0.45, emission=(0.20,0.90,0.30), emission_strength=2.0)
M_RANGOLI_BLUE = mat("rg_b", (0.20, 0.55, 1.0, 1.0), 0.0, 0.45, emission=(0.20,0.55,0.95), emission_strength=2.2)
M_RANGOLI_PINK = mat("rg_pk", (1.0, 0.30, 0.78, 1.0), 0.0, 0.45, emission=(0.95,0.30,0.75), emission_strength=2.2)
M_RANGOLI_PURPLE = mat("rg_p", (0.62, 0.30, 0.95, 1.0), 0.0, 0.45, emission=(0.60,0.30,0.92), emission_strength=2.0)
M_RANGOLI_WHITE = mat("rg_w", (1.0, 0.95, 0.85, 1.0), 0.0, 0.40, emission=(0.95,0.92,0.85), emission_strength=2.0)
RANGOLI_COLORS = [M_RANGOLI_RED, M_RANGOLI_ORANGE, M_RANGOLI_YELLOW, M_RANGOLI_GREEN,
                  M_RANGOLI_BLUE, M_RANGOLI_PINK, M_RANGOLI_PURPLE, M_RANGOLI_WHITE]

# Ground
M_STONE_INDIA = mat("stone", (0.78, 0.62, 0.45, 1.0), 0.0, 0.75, emission=(0.72,0.60,0.45), emission_strength=0.5)
M_STONE_PAVE_I = mat("stone_p", (0.55, 0.45, 0.32, 1.0), 0.0, 0.85)

# Taj Mahal white marble
M_TAJ_WHITE = mat("taj_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.45, emission=(0.92,0.90,0.88), emission_strength=1.2)
M_TAJ_GOLD = mat("taj_g", (1.0, 0.85, 0.30, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.30), emission_strength=2.5)
M_TAJ_RED = mat("taj_r", (0.78, 0.42, 0.32, 1.0), 0.0, 0.75, emission=(0.72,0.40,0.32), emission_strength=0.5)

# House colors (Indian vibrant)
M_HOUSE_PINK = mat("h_pk", (0.92, 0.45, 0.65, 1.0), 0.0, 0.75, emission=(0.88,0.45,0.62), emission_strength=0.6)
M_HOUSE_YELLOW = mat("h_y", (0.95, 0.78, 0.32, 1.0), 0.0, 0.75, emission=(0.90,0.75,0.32), emission_strength=0.7)
M_HOUSE_ORANGE = mat("h_o", (0.95, 0.55, 0.18, 1.0), 0.0, 0.75, emission=(0.90,0.55,0.18), emission_strength=0.6)
M_HOUSE_BLUE = mat("h_b", (0.30, 0.55, 0.85, 1.0), 0.0, 0.75, emission=(0.28,0.52,0.82), emission_strength=0.6)
M_HOUSE_RED = mat("h_r", (0.78, 0.25, 0.20, 1.0), 0.0, 0.75, emission=(0.72,0.25,0.20), emission_strength=0.6)
M_HOUSE_GREEN = mat("h_g", (0.30, 0.65, 0.42, 1.0), 0.0, 0.75, emission=(0.30,0.62,0.40), emission_strength=0.5)
HOUSE_COLORS = [M_HOUSE_PINK, M_HOUSE_YELLOW, M_HOUSE_ORANGE, M_HOUSE_BLUE, M_HOUSE_RED, M_HOUSE_GREEN]

# Ganesh
M_GANESH_GOLD = mat("g_g", (1.0, 0.85, 0.25, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.25), emission_strength=2.8)
M_GANESH_DEEP = mat("g_gd", (0.85, 0.62, 0.18, 1.0), 0.95, 0.20, emission=(0.80,0.58,0.18), emission_strength=2.0)
M_GANESH_RED = mat("g_r", (0.85, 0.20, 0.20, 1.0), 0.0, 0.55, emission=(0.80,0.20,0.20), emission_strength=1.0)

# Skin
M_SKIN_INDIA = mat("skin", (0.78, 0.55, 0.38, 1.0), 0.0, 0.55, emission=(0.72,0.52,0.38), emission_strength=0.4)
M_SKIN_BRIGHT = mat("skin_b", (0.88, 0.65, 0.48, 1.0), 0.0, 0.55)

# Hair black
M_HAIR_BLACK_I = mat("h_bk", (0.08, 0.05, 0.04, 1.0), 0.0, 0.55)

# Sari colors signature (vibrant embroidered)
M_SARI_RED = mat("sari_r", (0.95, 0.18, 0.25, 1.0), 0.0, 0.55, emission=(0.92,0.18,0.25), emission_strength=0.8)
M_SARI_PINK = mat("sari_pk", (0.95, 0.45, 0.78, 1.0), 0.0, 0.55, emission=(0.92,0.45,0.75), emission_strength=0.8)
M_SARI_ORANGE = mat("sari_o", (1.0, 0.55, 0.18, 1.0), 0.0, 0.55, emission=(0.95,0.55,0.18), emission_strength=0.9)
M_SARI_GREEN = mat("sari_g", (0.20, 0.62, 0.32, 1.0), 0.0, 0.55, emission=(0.18,0.60,0.30), emission_strength=0.8)
M_SARI_BLUE = mat("sari_b", (0.18, 0.32, 0.85, 1.0), 0.0, 0.55, emission=(0.18,0.30,0.82), emission_strength=0.8)
M_SARI_PURPLE = mat("sari_pu", (0.62, 0.25, 0.85, 1.0), 0.0, 0.55, emission=(0.60,0.25,0.82), emission_strength=0.8)
M_SARI_GOLD = mat("sari_gd", (0.95, 0.78, 0.30, 1.0), 0.6, 0.30, emission=(0.92,0.75,0.30), emission_strength=1.2)
SARI_COLORS = [M_SARI_RED, M_SARI_PINK, M_SARI_ORANGE, M_SARI_GREEN, M_SARI_BLUE, M_SARI_PURPLE, M_SARI_GOLD]

# Dhoti (signature white men's)
M_DHOTI_WHITE = mat("dhoti", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.90,0.88,0.82), emission_strength=0.5)
M_KURTA_GOLD = mat("kurta_g", (0.92, 0.78, 0.32, 1.0), 0.4, 0.30, emission=(0.88,0.75,0.32), emission_strength=0.8)
M_KURTA_RED = mat("kurta_r", (0.78, 0.20, 0.20, 1.0), 0.0, 0.55, emission=(0.72,0.20,0.20), emission_strength=0.6)
M_KURTA_BLUE = mat("kurta_b", (0.20, 0.42, 0.78, 1.0), 0.0, 0.55, emission=(0.18,0.40,0.75), emission_strength=0.6)
KURTA_COLORS = [M_KURTA_GOLD, M_KURTA_RED, M_KURTA_BLUE]

# Bindi
M_BINDI = mat("bindi", (1.0, 0.15, 0.15, 1.0), 0.0, 0.10, emission=(1.0,0.15,0.15), emission_strength=5.0)
M_GOLD_JEWEL = mat("gold_j", (1.0, 0.85, 0.30, 1.0), 0.95, 0.10, emission=(0.95,0.80,0.30), emission_strength=3.0)

# Diya signature (terra cotta oil lamp)
M_DIYA_CLAY = mat("diya", (0.62, 0.30, 0.18, 1.0), 0.0, 0.75, emission=(0.58,0.30,0.18), emission_strength=0.5)
M_DIYA_OIL = mat("diya_o", (0.92, 0.78, 0.55, 1.0), 0.3, 0.20, emission=(0.88,0.75,0.55), emission_strength=1.5, alpha=0.85)
M_FLAME_BRIGHT = mat("fl_b", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=25.0)
M_FLAME_OUTER = mat("fl_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=20.0)

# Spices for masala
M_MASALA_RED = mat("ms_r", (0.85, 0.15, 0.10, 1.0), 0.0, 0.65, emission=(0.80,0.15,0.10), emission_strength=0.5)
M_MASALA_YELLOW = mat("ms_y", (0.95, 0.78, 0.18, 1.0), 0.0, 0.65, emission=(0.90,0.75,0.18), emission_strength=0.5)
M_MASALA_BROWN = mat("ms_b", (0.55, 0.32, 0.15, 1.0), 0.0, 0.75)
M_MASALA_GREEN = mat("ms_g", (0.30, 0.55, 0.20, 1.0), 0.0, 0.65)
M_BOWL_BRASS = mat("bowl", (0.92, 0.65, 0.20, 1.0), 0.9, 0.20, emission=(0.88,0.62,0.20), emission_strength=1.0)

# Sitar / instruments
M_SITAR_WOOD = mat("sit_w", (0.55, 0.30, 0.15, 1.0), 0.0, 0.55, emission=(0.50,0.30,0.15), emission_strength=0.5)
M_SITAR_GOLD = mat("sit_g", (1.0, 0.85, 0.30, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.30), emission_strength=1.5)
M_TABLA_RED = mat("tab_r", (0.65, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.60,0.18,0.18), emission_strength=0.5)
M_TABLA_SKIN = mat("tab_s", (0.92, 0.78, 0.55, 1.0), 0.0, 0.55, emission=(0.85,0.72,0.52), emission_strength=0.5)
M_STRING_I = mat("string", (0.85, 0.85, 0.85, 1.0), 0.5, 0.30)

# Eye
M_EYE_DARK_I = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS_I = mat("lips", (0.65, 0.18, 0.25, 1.0), 0.0, 0.40, emission=(0.60,0.18,0.25), emission_strength=0.5)

# Firework colors
M_FW_RED = mat("fw_r", (1.0, 0.20, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.20,0.20), emission_strength=15.0)
M_FW_GOLD = mat("fw_g", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(0.95,0.80,0.30), emission_strength=18.0)
M_FW_GREEN = mat("fw_gr", (0.30, 1.0, 0.45, 1.0), 0.0, 0.10, emission=(0.30,0.95,0.45), emission_strength=15.0)
M_FW_BLUE = mat("fw_b", (0.30, 0.55, 1.0, 1.0), 0.0, 0.10, emission=(0.28,0.55,1.0), emission_strength=15.0)
M_FW_PURPLE = mat("fw_p", (0.85, 0.30, 1.0, 1.0), 0.0, 0.10, emission=(0.82,0.30,1.0), emission_strength=15.0)
FW_COLORS = [M_FW_RED, M_FW_GOLD, M_FW_GREEN, M_FW_BLUE, M_FW_PURPLE]

# Jasmine
M_JASMINE = mat("jas", (0.98, 0.95, 0.92, 1.0), 0.0, 0.40, emission=(0.95,0.92,0.90), emission_strength=2.0)
M_JASMINE_CENTER = mat("jas_c", (0.95, 0.88, 0.45, 1.0), 0.0, 0.40, emission=(0.92,0.85,0.45), emission_strength=2.0)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Sky horizon gold
sky_g = smooth_sphere("sky_h", r=230, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_GOLD)
sky_g.scale = (1,1,0.20)
# Moon
moon = smooth_sphere("moon", r=3.5, segs=24, rings=18, loc=(40, 80, 50), mat_=M_MOON)
# Stars
for si in range(80):
    sa = random.uniform(0, math.pi*2); sr = random.uniform(60, 180)
    sh = random.uniform(30, 90)
    smooth_sphere(f"star{si}", r=random.uniform(0.10, 0.25), segs=8, rings=6,
                  loc=(sr*math.cos(sa), sr*math.sin(sa), sh), mat_=M_STAR)

# ============ ONE clean stone ground ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_STONE_INDIA)
# Pavement detail
for ti in range(30):
    for tj in range(30):
        tx_g = -45 + ti * 3; ty_g = -45 + tj * 3
        if (ti + tj) % 4 == 0:
            beveled_cube(f"pave{ti}_{tj}", (2.8, 2.8, 0.05), bevel_offset=0.02,
                         loc=(tx_g, ty_g, 0.12), mat_=M_STONE_PAVE_I)

# ============ RANGOLI signature (colorful floor patterns) ============
# Central rangoli pattern (signature concentric circles + petals)
rangoli_center = empty("rangoli", loc=(0, 0, 0))
# Center
cyl("rg_c", r=0.5, depth=0.04, segs=24, loc=(0, 0, 0.15), parent=rangoli_center, mat_=M_RANGOLI_RED)
# Ring 1
for ri in range(16):
    ra = (ri / 16.0) * math.pi * 2
    smooth_sphere(f"rg1_{ri}", r=0.12, loc=(math.cos(ra)*0.8, math.sin(ra)*0.8, 0.15),
                  parent=rangoli_center, mat_=RANGOLI_COLORS[ri % len(RANGOLI_COLORS)],
                  scale=(1, 1, 0.3))
# Ring 2 petals signature
for ri in range(12):
    ra = (ri / 12.0) * math.pi * 2
    # Elongated petal
    petal_e = empty(f"rg_pe{ri}_e", (math.cos(ra)*1.6, math.sin(ra)*1.6, 0.15), parent=rangoli_center)
    petal_e.rotation_euler = (0, 0, ra)
    beveled_cube(f"rg_pe{ri}", (0.5, 0.20, 0.04), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=petal_e, mat_=RANGOLI_COLORS[ri % len(RANGOLI_COLORS)])
# Ring 3 outer
for ri in range(20):
    ra = (ri / 20.0) * math.pi * 2
    smooth_sphere(f"rg3_{ri}", r=0.10, loc=(math.cos(ra)*2.5, math.sin(ra)*2.5, 0.15),
                  parent=rangoli_center, mat_=RANGOLI_COLORS[ri % len(RANGOLI_COLORS)],
                  scale=(1, 1, 0.3))
# Outer petals
for ri in range(8):
    ra = (ri / 8.0) * math.pi * 2 + math.pi/8
    petal_o_e = empty(f"rg_po{ri}_e", (math.cos(ra)*3.5, math.sin(ra)*3.5, 0.15), parent=rangoli_center)
    petal_o_e.rotation_euler = (0, 0, ra)
    beveled_cube(f"rg_po{ri}", (0.8, 0.30, 0.04), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=petal_o_e, mat_=RANGOLI_COLORS[ri % len(RANGOLI_COLORS)])

# Side rangolis smaller (4 corners)
for ci in range(4):
    ca = (ci / 4.0) * math.pi * 2 + math.pi/4
    cx_r = math.cos(ca) * 25
    cy_r = math.sin(ca) * 25
    rc_e = empty(f"rg_corner{ci}", (cx_r, cy_r, 0))
    cyl(f"rg_c_c{ci}", r=0.3, depth=0.04, segs=18, loc=(0, 0, 0.15),
        parent=rc_e, mat_=M_RANGOLI_YELLOW)
    for pi in range(8):
        pa = (pi / 8.0) * math.pi * 2
        smooth_sphere(f"rg_c_p{ci}_{pi}", r=0.10,
                      loc=(math.cos(pa)*0.5, math.sin(pa)*0.5, 0.15),
                      parent=rc_e, mat_=RANGOLI_COLORS[pi % len(RANGOLI_COLORS)],
                      scale=(1, 1, 0.3))

# ============ TAJ MAHAL background (signature) ============
taj_e = empty("taj", loc=(0, 50, 0))
# Base platform red stone
beveled_cube("tj_base", (24, 14, 1.5), bevel_offset=0.10, loc=(0, 0, 0.75),
             parent=taj_e, mat_=M_TAJ_RED)
# White marble main building
beveled_cube("tj_main", (16, 12, 8), bevel_offset=0.20, loc=(0, 0, 5.5),
             parent=taj_e, mat_=M_TAJ_WHITE)
# IWAN (signature pointed arch front)
beveled_cube("tj_iwan", (5, 1, 6), bevel_offset=0.30, loc=(0, -6, 5.5),
             parent=taj_e, mat_=M_TAJ_RED)
# 4 corner CHATTRIS (signature small domes)
for x in (-1, 1):
    for y in (-1, 1):
        # Tower
        cyl(f"tj_cs_t{x}_{y}", r=0.8, depth=8, segs=18, loc=(x*8, y*5.5, 4),
            parent=taj_e, mat_=M_TAJ_WHITE)
        # Chattri base
        cyl(f"tj_cs_b{x}_{y}", r=1.0, depth=0.50, segs=18, loc=(x*8, y*5.5, 8.5),
            parent=taj_e, mat_=M_TAJ_WHITE)
        # Small dome
        smooth_sphere(f"tj_cs_d{x}_{y}", r=0.85, segs=18, rings=14, loc=(x*8, y*5.5, 9.2),
                      parent=taj_e, mat_=M_TAJ_WHITE, scale=(1, 1, 1.2))
        # Spire
        cyl(f"tj_cs_s{x}_{y}", r=0.06, depth=1.5, segs=10, loc=(x*8, y*5.5, 10.5),
            parent=taj_e, mat_=M_TAJ_GOLD)
# CENTRAL DOME (signature huge)
# Drum (cylindrical base)
cyl("tj_drum", r=4, depth=2, segs=22, loc=(0, 0, 10), parent=taj_e, mat_=M_TAJ_WHITE)
# Onion dome (signature bulbous)
smooth_sphere("tj_dome", r=4.5, segs=24, rings=18, loc=(0, 0, 13),
              parent=taj_e, mat_=M_TAJ_WHITE, scale=(1, 1, 1.15))
# Top pinch
smooth_sphere("tj_dome_t", r=1.0, loc=(0, 0, 18), parent=taj_e, mat_=M_TAJ_WHITE)
# Tall spire
cyl("tj_sp", r=0.10, depth=4, segs=12, loc=(0, 0, 20), parent=taj_e, mat_=M_TAJ_GOLD)
# Crescent moon top
smooth_sphere("tj_cre", r=0.30, loc=(0, 0, 22.5), parent=taj_e, mat_=M_TAJ_GOLD,
              scale=(0.3, 1, 1))
# 4 MINARETS (signature corners)
for x in (-1, 1):
    for y in (-1, 1):
        mx_t = x * 14; my_t = y * 9
        # Minaret tower 3 tiers
        for ti in range(3):
            tz = 1.5 + ti * 5
            tr = 0.6 - ti * 0.05
            cyl(f"tj_mi{x}_{y}_{ti}", r=tr, depth=5, segs=18, loc=(mx_t, my_t, tz + 2.5),
                parent=taj_e, mat_=M_TAJ_WHITE)
            # Balcony
            cyl(f"tj_mb{x}_{y}_{ti}", r=tr+0.10, depth=0.25, segs=18, loc=(mx_t, my_t, tz + 5),
                parent=taj_e, mat_=M_TAJ_WHITE)
        # Top dome
        smooth_sphere(f"tj_md{x}_{y}", r=0.40, loc=(mx_t, my_t, 18),
                      parent=taj_e, mat_=M_TAJ_WHITE)
        # Spire
        cyl(f"tj_ms{x}_{y}", r=0.05, depth=1, segs=8, loc=(mx_t, my_t, 19),
            parent=taj_e, mat_=M_TAJ_GOLD)

# Reflecting pool (signature)
beveled_cube("tj_pool", (12, 35, 0.10), bevel_offset=0.04, loc=(0, -25, 0.20),
             mat_=M_STONE_INDIA)

# ============ 8 INDIAN HOUSES with arches (signature) ============
def make_indian_house(name, loc, scale=1.0, facing=0, h_color=None):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    if h_color is None:
        h_color = random.choice(HOUSE_COLORS)
    # Body
    beveled_cube(f"{name}_b", (5, 5, 4), bevel_offset=0.10, loc=(0, 0, 2),
                 parent=base, mat_=h_color)
    # Stripe decorative band
    cyl(f"{name}_band", r=2.55, depth=0.20, segs=18, loc=(0, 0, 3),
        parent=base, mat_=M_TAJ_WHITE)
    # POINTED ARCH DOOR (signature)
    beveled_cube(f"{name}_door_b", (1.4, 0.5, 2), bevel_offset=0.30, loc=(0, -2.5, 1),
                 parent=base, mat_=M_KURTA_BLUE)
    # Decorative arch trim
    smooth_sphere(f"{name}_arch_t", r=0.7, segs=14, rings=10, loc=(0, -2.5, 2),
                  parent=base, mat_=M_TAJ_WHITE, scale=(1, 0.3, 0.7))
    # Arched WINDOWS
    for wi in range(2):
        for side in (-1, 1):
            wx_p = side * (1.5 + wi*0.8)
            beveled_cube(f"{name}_w{wi}_{side}", (0.6, 0.4, 1.0), bevel_offset=0.15,
                         loc=(wx_p, -2.5, 2.5), parent=base, mat_=M_FLAME_BRIGHT)
            # Window arch
            smooth_sphere(f"{name}_wa{wi}_{side}", r=0.35, loc=(wx_p, -2.5, 3.0),
                          parent=base, mat_=M_TAJ_WHITE, scale=(1, 0.3, 0.5))
    # Flat roof + parapet
    beveled_cube(f"{name}_roof", (5.2, 5.2, 0.30), bevel_offset=0.06, loc=(0, 0, 4.15),
                 parent=base, mat_=M_TAJ_RED)
    # Parapet crenellations decorative
    for ci in range(8):
        cy_pos = -2.4 + ci * 0.7
        beveled_cube(f"{name}_pa{ci}", (0.5, 0.5, 0.30), bevel_offset=0.04,
                     loc=(2.5, cy_pos, 4.6), parent=base, mat_=M_TAJ_WHITE)
        beveled_cube(f"{name}_pa_b{ci}", (0.5, 0.5, 0.30), bevel_offset=0.04,
                     loc=(-2.5, cy_pos, 4.6), parent=base, mat_=M_TAJ_WHITE)
    # Small dome on top center
    smooth_sphere(f"{name}_dome", r=0.7, segs=18, rings=14, loc=(0, 0, 4.85),
                  parent=base, mat_=M_TAJ_WHITE, scale=(1, 1, 0.9))
    # Spire
    cyl(f"{name}_sp", r=0.05, depth=0.5, segs=10, loc=(0, 0, 5.5),
        parent=base, mat_=M_TAJ_GOLD)
    # DIYAS on parapet edge (signature)
    for di in range(8):
        dx_p = -2.4 + di * 0.7
        # Diya bowl
        smooth_sphere(f"{name}_d{di}_b", r=0.10, segs=12, rings=8,
                      loc=(dx_p, -2.5, 4.5), parent=base, mat_=M_DIYA_CLAY, scale=(1, 1, 0.5))
        # Flame
        smooth_cone(f"{name}_d{di}_f", r1=0.05, r2=0.005, depth=0.15, segs=8,
                    loc=(dx_p, -2.5, 4.62), parent=base, mat_=M_FLAME_OUTER)
    # GARLAND across door signature (marigold orange)
    for gi in range(8):
        gx_p = -1.5 + gi * 0.4
        smooth_sphere(f"{name}_g{gi}", r=0.08, loc=(gx_p, -2.55, 3.5),
                      parent=base, mat_=M_RANGOLI_ORANGE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

houses = []
house_pos = [(-25, -10, math.radians(0)), (-15, -15, math.radians(0)),
              (15, -15, math.radians(0)), (25, -10, math.radians(0)),
              (-35, 5, math.radians(0)), (-25, 15, math.radians(0)),
              (25, 15, math.radians(0)), (35, 5, math.radians(0))]
for i, (hx, hy, fac) in enumerate(house_pos):
    h = make_indian_house(f"house{i}", (hx, hy, 0), scale=1.0, facing=fac,
                          h_color=HOUSE_COLORS[i % len(HOUSE_COLORS)])
    houses.append(h)

# ============ GANESH GOLD STATUE (signature elephant god) ============
ganesh_e = empty("ganesh", loc=(0, 15, 0))
# Pedestal
for li in range(3):
    lw = 5 - li * 0.5
    beveled_cube(f"gn_p{li}", (lw, lw, 0.6), bevel_offset=0.08, loc=(0, 0, 0.3 + li*0.6),
                 parent=ganesh_e, mat_=M_TAJ_RED)
# Sitting position lotus base
cyl("gn_lotus", r=2.5, depth=0.4, segs=22, loc=(0, 0, 2.2), parent=ganesh_e, mat_=M_RANGOLI_PINK)
# Body sitting (signature seated)
smooth_sphere("gn_body", r=1.4, segs=22, rings=16, loc=(0, 0, 3.5),
              parent=ganesh_e, mat_=M_GANESH_GOLD, scale=(1.3, 1.0, 1.2))
# Belly (signature large)
smooth_sphere("gn_belly", r=1.5, segs=22, rings=16, loc=(0, -0.3, 3.0),
              parent=ganesh_e, mat_=M_GANESH_GOLD, scale=(1.4, 0.85, 1))
# 4 arms (signature)
for side_idx, side in enumerate((-1, 1)):
    # Upper arms
    sh_u = empty(f"gn_sh_u{side_idx}", (side*1.0, 0, 4.5), parent=ganesh_e)
    sh_u.rotation_euler = (math.radians(-60), 0, math.radians(side*-30))
    cyl(f"gn_uarm_u{side_idx}", r=0.18, depth=0.8, segs=14, loc=(0, 0, -0.40),
        parent=sh_u, mat_=M_GANESH_GOLD)
    cyl(f"gn_fa_u{side_idx}", r=0.15, depth=0.6, segs=14, loc=(0, 0, -1.10),
        parent=sh_u, mat_=M_GANESH_GOLD)
    # Hand holding item
    smooth_sphere(f"gn_h_u{side_idx}", r=0.18, loc=(0, 0, -1.50),
                  parent=sh_u, mat_=M_GANESH_GOLD)
    # Lower arms
    sh_l = empty(f"gn_sh_l{side_idx}", (side*0.9, -0.10, 3.8), parent=ganesh_e)
    sh_l.rotation_euler = (math.radians(-40 - side*30), 0, math.radians(side*-15))
    cyl(f"gn_uarm_l{side_idx}", r=0.18, depth=0.8, segs=14, loc=(0, 0, -0.40),
        parent=sh_l, mat_=M_GANESH_GOLD)
    cyl(f"gn_fa_l{side_idx}", r=0.15, depth=0.6, segs=14, loc=(0, 0, -1.10),
        parent=sh_l, mat_=M_GANESH_GOLD)
    smooth_sphere(f"gn_h_l{side_idx}", r=0.18, loc=(0, 0, -1.50),
                  parent=sh_l, mat_=M_GANESH_GOLD)
# Hand items: axe, modak (sweet), trident, lotus
# Modak in lower right hand (signature sweet)
smooth_sphere("gn_modak", r=0.18, loc=(0.85, -1.5, 2.4),
              parent=ganesh_e, mat_=M_GANESH_DEEP, scale=(1, 1, 1.3))
# ELEPHANT HEAD (signature)
head_g_e = empty("gn_he", (0, 0, 5.5), parent=ganesh_e)
smooth_sphere("gn_head", r=1.0, segs=22, rings=16, loc=(0, 0, 0),
              parent=head_g_e, mat_=M_GANESH_GOLD, scale=(1.2, 1.0, 1.1))
# TRUNK (signature curled)
trunk_e = empty("gn_trunk", (0, -0.6, -0.2), parent=head_g_e)
trunk_e.rotation_euler = (math.radians(40), 0, 0)
for ti in range(6):
    cyl(f"gn_t{ti}", r=0.30 - ti*0.03, depth=0.25, segs=14,
        loc=(math.sin(ti*0.5)*0.10, ti*0.25, 0), parent=trunk_e, mat_=M_GANESH_GOLD)
# BIG EARS (signature)
for side in (-1, 1):
    smooth_sphere(f"gn_ear{side}", r=0.55, loc=(side*0.85, -0.10, 0.05),
                  parent=head_g_e, mat_=M_GANESH_GOLD, scale=(0.5, 1.3, 1.2))
    # Inner ear pink
    smooth_sphere(f"gn_ear_i{side}", r=0.40, loc=(side*0.90, -0.15, 0.05),
                  parent=head_g_e, mat_=M_RANGOLI_PINK, scale=(0.3, 1.0, 1.0))
# TUSKS (signature)
for side in (-1, 1):
    smooth_cone(f"gn_tu{side}", r1=0.12, r2=0.02, depth=0.40, segs=10,
                loc=(side*0.25, -0.65, -0.30), parent=head_g_e,
                mat_=M_TAJ_WHITE).rotation_euler = (math.radians(-110), 0, 0)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"gn_eye{side}", r=0.10, loc=(side*0.30, -0.65, 0.30),
                  parent=head_g_e, mat_=M_TAJ_WHITE)
    smooth_sphere(f"gn_pup{side}", r=0.05, loc=(side*0.30, -0.72, 0.30),
                  parent=head_g_e, mat_=M_EYE_DARK_I)
# CROWN signature
crown_e = empty("gn_cr", (0, 0, 0.55), parent=head_g_e)
cyl("gn_cr_b", r=0.50, depth=0.25, segs=18, loc=(0, 0, 0),
    parent=crown_e, mat_=M_GANESH_DEEP)
# 5 crown points
for ci in range(5):
    ca = (ci / 5.0) * math.pi - math.pi/2
    smooth_cone(f"gn_cr_p{ci}", r1=0.08, r2=0.005, depth=0.35, segs=8,
                loc=(math.sin(ca)*0.35, -0.10, 0.15), parent=crown_e, mat_=M_GANESH_DEEP)
    # Jewel on tip
    smooth_sphere(f"gn_cr_j{ci}", r=0.05,
                  loc=(math.sin(ca)*0.35, -0.10, 0.35), parent=crown_e, mat_=M_RANGOLI_RED)
# Tilak red on forehead (signature)
smooth_sphere("gn_tilak", r=0.06, loc=(0, -0.95, 0.15),
              parent=head_g_e, mat_=M_GANESH_RED)
# Necklaces gold
for ni in range(3):
    cyl(f"gn_nk{ni}", r=0.55 + ni*0.05, depth=0.05, segs=18, loc=(0, -0.10, 4.4 + ni*0.10),
        parent=ganesh_e, mat_=M_GANESH_DEEP)
# Mouse vahana at base (signature small)
mouse_e = empty("gn_mouse", (0, -2.3, 2.4), parent=ganesh_e)
smooth_sphere("ms_b", r=0.20, segs=14, rings=10, loc=(0, 0, 0),
              parent=mouse_e, mat_=M_HAIR_BLACK_I, scale=(1.5, 1.0, 0.9))
smooth_sphere("ms_h", r=0.12, loc=(0, -0.20, 0.05), parent=mouse_e, mat_=M_HAIR_BLACK_I)
# Tail
cyl("ms_tail", r=0.015, depth=0.30, segs=6, loc=(0, 0.25, 0), parent=mouse_e,
    mat_=M_HAIR_BLACK_I).rotation_euler = (math.radians(80), 0, 0)

# ============ 6 WOMEN in saris (signature) ============
def make_woman_sari(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    sari_col = random.choice(SARI_COLORS)
    sari_border = random.choice([M_SARI_GOLD, M_RANGOLI_RED, M_RANGOLI_YELLOW])
    # Long flowing sari skirt
    smooth_cone(f"{name}_skirt", r1=0.50, r2=0.32, depth=1.5, segs=20, loc=(0, 0, 0.85),
                parent=base, mat_=sari_col)
    # Gold border bottom
    cyl(f"{name}_border", r=0.51, depth=0.10, segs=20, loc=(0, 0, 0.20),
        parent=base, mat_=sari_border)
    # Decorative gold border with pattern
    for bi in range(12):
        ba = (bi / 12.0) * math.pi * 2
        smooth_sphere(f"{name}_bd{bi}", r=0.03,
                      loc=(math.cos(ba)*0.51, math.sin(ba)*0.51, 0.30),
                      parent=base, mat_=M_GOLD_JEWEL)
    # Pleats vertical
    for pi in range(10):
        pa = (pi / 10.0) * math.pi * 2
        cyl(f"{name}_pl{pi}", r=0.02, depth=1.5, segs=6,
            loc=(math.cos(pa)*0.48, math.sin(pa)*0.48, 0.85),
            parent=base, mat_=sari_border)
    # Blouse choli short
    smooth_cone(f"{name}_blouse", r1=0.30, r2=0.32, depth=0.40, segs=14, loc=(0, 0, 1.75),
                parent=base, mat_=sari_border)
    # PALLU draped over shoulder (signature)
    pallu_e = empty(f"{name}_pallu", (0, 0.10, 2.0), parent=base)
    pallu_e.rotation_euler = (0, math.radians(15), math.radians(45))
    beveled_cube(f"{name}_pa", (0.55, 0.06, 0.7), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=pallu_e, mat_=sari_col)
    # Gold border on pallu
    cyl(f"{name}_pa_b", r=0.30, depth=0.04, segs=14, loc=(0, 0, -0.30),
        parent=pallu_e, mat_=sari_border)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.95), parent=base)
        sh.rotation_euler = (math.radians(-50 + side*15), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.15),
            parent=sh, mat_=sari_border)
        cyl(f"{name}_fa{side_idx}", r=0.05, depth=0.30, segs=10, loc=(0, 0, -0.45),
            parent=sh, mat_=M_SKIN_INDIA)
        # GOLD BANGLES (signature)
        for bi in range(5):
            cyl(f"{name}_bg{side_idx}_{bi}", r=0.06, depth=0.02, segs=14,
                loc=(0, 0, -0.30 - bi*0.04), parent=sh, mat_=M_GOLD_JEWEL)
    # Head
    head_w_e = empty(f"{name}_he", (0, 0, 2.20), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_w_e, mat_=M_SKIN_INDIA)
    # Black hair tied back signature
    smooth_sphere(f"{name}_hair", r=0.20, loc=(0, 0.08, 0.05),
                  parent=head_w_e, mat_=M_HAIR_BLACK_I, scale=(1, 1.1, 1.1))
    # Long braid back
    for bi in range(6):
        smooth_sphere(f"{name}_br{bi}", r=0.06,
                      loc=(0, 0.20, -0.05 - bi*0.10), parent=head_w_e, mat_=M_HAIR_BLACK_I)
    # BINDI (signature red dot on forehead)
    smooth_sphere(f"{name}_bindi", r=0.025, loc=(0, -0.18, 0.10),
                  parent=head_w_e, mat_=M_BINDI)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.16, 0.03),
                      parent=head_w_e, mat_=M_EYE_DARK_I)
    # Lips red
    beveled_cube(f"{name}_lips", (0.06, 0.04, 0.02), bevel_offset=0.005,
                 loc=(0, -0.18, -0.06), parent=head_w_e, mat_=M_LIPS_I)
    # Nose ring (signature gold)
    smooth_sphere(f"{name}_nr", r=0.02, loc=(0.04, -0.20, -0.02),
                  parent=head_w_e, mat_=M_GOLD_JEWEL)
    # Gold earrings
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.05, loc=(side*0.18, 0, -0.05),
                      parent=head_w_e, mat_=M_GOLD_JEWEL)
    # Necklace gold
    for ni in range(8):
        na = (ni / 8.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_nk{ni}", r=0.04,
                      loc=(math.sin(na)*0.22, -0.18, 1.92),
                      parent=base, mat_=M_GOLD_JEWEL)
    # Big pendant
    smooth_sphere(f"{name}_pend", r=0.07, loc=(0, -0.25, 1.75),
                  parent=base, mat_=M_GOLD_JEWEL)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_w_e}

women_sari = []
ws_pos = [(-12, 2, math.radians(30)), (-8, 0, math.radians(-15)),
          (-4, 4, math.radians(45)), (4, 4, math.radians(-45)),
          (8, 0, math.radians(15)), (12, 2, math.radians(-30))]
for i, (wx, wy, fac) in enumerate(ws_pos):
    w = make_woman_sari(f"sari{i}", (wx, wy, 0), scale=1.0, facing=fac)
    women_sari.append(w)

# ============ 4 MEN dhoti (signature traditional) ============
def make_man_dhoti(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    kurta_col = random.choice(KURTA_COLORS)
    # Dhoti wrapped (signature white)
    smooth_cone(f"{name}_dhoti", r1=0.42, r2=0.30, depth=1.0, segs=14, loc=(0, 0, 0.55),
                parent=base, mat_=M_DHOTI_WHITE)
    # Pleats
    for pi in range(8):
        pa = (pi / 8.0) * math.pi * 2
        cyl(f"{name}_dpl{pi}", r=0.02, depth=1.0, segs=6,
            loc=(math.cos(pa)*0.40, math.sin(pa)*0.40, 0.55),
            parent=base, mat_=M_DHOTI_WHITE)
    # KURTA top (signature long shirt)
    smooth_cone(f"{name}_kurta", r1=0.32, r2=0.34, depth=0.9, segs=14, loc=(0, 0, 1.45),
                parent=base, mat_=kurta_col)
    # Gold border on kurta
    cyl(f"{name}_k_b", r=0.35, depth=0.06, segs=14, loc=(0, 0, 1.0),
        parent=base, mat_=M_GOLD_JEWEL)
    # Embroidery patterns
    for ei in range(6):
        ea = (ei / 6.0) * math.pi * 2
        beveled_cube(f"{name}_em{ei}", (0.04, 0.04, 0.5), bevel_offset=0.005,
                     loc=(math.cos(ea)*0.32, math.sin(ea)*0.32, 1.45),
                     parent=base, mat_=M_GOLD_JEWEL)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.32, 0, 1.80), parent=base)
        sh.rotation_euler = (math.radians(-40 + side*10), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.35, segs=10, loc=(0, 0, -0.18),
            parent=sh, mat_=kurta_col)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.48),
            parent=sh, mat_=M_SKIN_INDIA)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 2.10), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN_INDIA)
    # Black moustache + beard
    for bi in range(8):
        ba = (bi / 8.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_bd{bi}", r=0.03,
                      loc=(math.sin(ba)*0.12, -0.16, -0.10),
                      parent=head_m_e, mat_=M_HAIR_BLACK_I)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_m_e, mat_=M_EYE_DARK_I)
    # Hair
    for hi in range(6):
        ha = (hi / 6.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.05,
                      loc=(math.cos(ha)*0.14, math.sin(ha)*0.10, 0.10),
                      parent=head_m_e, mat_=M_HAIR_BLACK_I)
    # Tilak (signature red mark on forehead)
    smooth_sphere(f"{name}_tilak", r=0.03, loc=(0, -0.17, 0.12),
                  parent=head_m_e, mat_=M_GANESH_RED)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_m_e}

men_dhoti = []
md_pos = [(-15, 8, math.radians(45)), (-10, 12, math.radians(-30)),
           (10, 12, math.radians(30)), (15, 8, math.radians(-45))]
for i, (mx, my, fac) in enumerate(md_pos):
    m = make_man_dhoti(f"man{i}", (mx, my, 0), scale=1.0, facing=fac)
    men_dhoti.append(m)

# ============ 4 MUSICIANS sitar/tabla/harmonium ============
def make_musician_i(name, loc, instrument, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sitting body
    smooth_cone(f"{name}_body", r1=0.45, r2=0.35, depth=1.0, segs=14, loc=(0, 0, 0.55),
                parent=base, mat_=random.choice([M_SARI_RED, M_KURTA_GOLD, M_KURTA_BLUE]))
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 1.40), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN_INDIA)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_m_e, mat_=M_EYE_DARK_I)
    # Hair / turban
    if random.random() > 0.5:
        # Turban
        cyl(f"{name}_turban", r=0.22, depth=0.18, segs=14, loc=(0, 0, 0.20),
            parent=head_m_e, mat_=random.choice([M_KURTA_GOLD, M_KURTA_RED]))
    # Tilak
    smooth_sphere(f"{name}_tilak", r=0.03, loc=(0, -0.17, 0.12),
                  parent=head_m_e, mat_=M_GANESH_RED)
    # INSTRUMENT
    inst_e = empty(f"{name}_inst", (0, -0.30, 0.85), parent=base)
    if instrument == "sitar":
        # GOURD body (signature large)
        smooth_sphere(f"{name}_st_g", r=0.40, segs=20, rings=14, loc=(0, 0, 0),
                      parent=inst_e, mat_=M_SITAR_WOOD, scale=(1, 0.85, 1))
        # Long neck (signature)
        cyl(f"{name}_st_n", r=0.05, depth=1.5, segs=10, loc=(0, 0, 0.85),
            parent=inst_e, mat_=M_SITAR_WOOD)
        # Frets
        for fri in range(10):
            cyl(f"{name}_st_f{fri}", r=0.055, depth=0.02, segs=10,
                loc=(0, 0, 0.20 + fri*0.13), parent=inst_e, mat_=M_SITAR_GOLD)
        # Strings
        for st in range(7):
            cyl(f"{name}_st_s{st}", r=0.003, depth=1.6, segs=6,
                loc=((st-3)*0.012, -0.05, 0.80), parent=inst_e, mat_=M_STRING_I)
        # Small gourd on neck top
        smooth_sphere(f"{name}_st_g2", r=0.20, loc=(0, 0, 1.70),
                      parent=inst_e, mat_=M_SITAR_WOOD)
    elif instrument == "tabla":
        # 2 drums signature (high+low pitch)
        for di_t in range(2):
            dx_t = (di_t - 0.5) * 0.50
            cyl(f"{name}_tb{di_t}", r=0.15 + di_t*0.05, depth=0.30, segs=14,
                loc=(dx_t, 0, 0.10), parent=inst_e, mat_=M_TABLA_RED)
            # Skin top (signature dark center)
            cyl(f"{name}_tb_s{di_t}", r=0.15 + di_t*0.05, depth=0.03, segs=14,
                loc=(dx_t, 0, 0.27), parent=inst_e, mat_=M_TABLA_SKIN)
            # Dark center patch (signature syahi)
            cyl(f"{name}_tb_sy{di_t}", r=0.04, depth=0.02, segs=10,
                loc=(dx_t, 0, 0.29), parent=inst_e, mat_=M_HAIR_BLACK_I)
            # Strings around
            for stri in range(6):
                stra = (stri / 6.0) * math.pi * 2
                cyl(f"{name}_tb_st{di_t}_{stri}", r=0.005, depth=0.30, segs=6,
                    loc=(dx_t + math.cos(stra)*(0.16 + di_t*0.05),
                         math.sin(stra)*(0.16 + di_t*0.05), 0.10),
                    parent=inst_e, mat_=M_STRING_I)
    elif instrument == "harmonium":
        # Wooden box
        beveled_cube(f"{name}_h_b", (0.60, 0.40, 0.30), bevel_offset=0.06,
                     loc=(0, 0, 0.15), parent=inst_e, mat_=M_SITAR_WOOD)
        # Keys white
        for ki in range(12):
            kx_h = -0.27 + ki * 0.04
            beveled_cube(f"{name}_h_k{ki}", (0.03, 0.04, 0.18), bevel_offset=0.005,
                         loc=(kx_h, -0.18, 0.35), parent=inst_e, mat_=M_DHOTI_WHITE)
        # Black keys some
        for ki in range(8):
            kx_h = -0.22 + ki * 0.06
            beveled_cube(f"{name}_h_bk{ki}", (0.02, 0.03, 0.12), bevel_offset=0.005,
                         loc=(kx_h, -0.20, 0.42), parent=inst_e, mat_=M_HAIR_BLACK_I)
        # Bellows at back
        for fi in range(5):
            beveled_cube(f"{name}_h_f{fi}", (0.50, 0.08, 0.05), bevel_offset=0.01,
                         loc=(0, 0.18, 0.20 + fi*0.06), parent=inst_e, mat_=M_TABLA_RED)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "inst": inst_e, "he": head_m_e}

musicians_i = []
mus_data_i = [("sitar", -22, -2), ("tabla", -18, -3),
               ("harmonium", 18, -3), ("sitar", 22, -2)]
for i, (inst, mx, my) in enumerate(mus_data_i):
    m = make_musician_i(f"mus_i{i}", (mx, my, 0), instrument=inst, scale=1.0,
                        facing=math.radians(-90))
    musicians_i.append(m)

# ============ MASALA SPICE BOWLS (signature) ============
masala_e = empty("masala", loc=(15, -5, 0))
# Brass tray
cyl("ms_tray", r=1.5, depth=0.10, segs=22, loc=(0, 0, 0.30),
    parent=masala_e, mat_=M_BOWL_BRASS)
# 6 spice bowls
for bi in range(6):
    ba = (bi / 6.0) * math.pi * 2
    bx_m = math.cos(ba) * 0.9
    by_m = math.sin(ba) * 0.9
    spice_col = [M_MASALA_RED, M_MASALA_YELLOW, M_MASALA_BROWN, M_MASALA_GREEN,
                  M_RANGOLI_ORANGE, M_RANGOLI_YELLOW][bi]
    # Bowl
    cyl(f"ms_b{bi}", r=0.20, depth=0.10, segs=14, loc=(bx_m, by_m, 0.40),
        parent=masala_e, mat_=M_BOWL_BRASS)
    # Spice mound
    smooth_cone(f"ms_s{bi}", r1=0.18, r2=0.03, depth=0.15, segs=14,
                loc=(bx_m, by_m, 0.52), parent=masala_e, mat_=spice_col)

# ============ FIREWORKS in sky (signature) ============
fireworks = []
for fwi in range(8):
    fwa = (fwi / 8.0) * math.pi * 2
    fwr = random.uniform(20, 40)
    fwx = math.cos(fwa) * fwr
    fwy = math.sin(fwa) * fwr
    fwz = random.uniform(20, 40)
    fw_e = empty(f"fw{fwi}", (fwx, fwy, fwz))
    fw_col = random.choice(FW_COLORS)
    # Center burst
    smooth_sphere(f"fw_c{fwi}", r=0.30, segs=14, rings=10, loc=(0, 0, 0),
                  parent=fw_e, mat_=fw_col)
    # Sparks radiating (signature)
    for si in range(25):
        sa = random.uniform(0, math.pi*2); se = random.uniform(0, math.pi)
        sl = random.uniform(2, 4)
        sx = math.sin(se)*math.cos(sa) * sl
        sy = math.sin(se)*math.sin(sa) * sl
        sz = math.cos(se) * sl
        spark_e = empty(f"fw_se{fwi}_{si}", (0, 0, 0), parent=fw_e)
        cyl(f"fw_sp{fwi}_{si}", r=0.04, depth=sl, segs=6,
            loc=(sx/2, sy/2, sz/2), parent=spark_e, mat_=fw_col)
    # Trail particles
    for ti in range(15):
        ta = random.uniform(0, math.pi*2); te = random.uniform(0, math.pi)
        tl = random.uniform(0.5, 2)
        tx = math.sin(te)*math.cos(ta) * tl
        ty = math.sin(te)*math.sin(ta) * tl
        tz = math.cos(te) * tl
        smooth_sphere(f"fw_tr{fwi}_{ti}", r=random.uniform(0.10, 0.20),
                      loc=(tx, ty, tz), parent=fw_e, mat_=fw_col)
    fw_e["_phase"] = random.uniform(0, math.pi*2)
    fireworks.append(fw_e)

# ============ LIT DIYAS rows on ground signature ============
ground_diyas = []
for di in range(40):
    da = (di / 40.0) * math.pi * 2
    drad = random.uniform(6, 30)
    dx_p = math.cos(da) * drad
    dy_p = math.sin(da) * drad
    diya_e = empty(f"gd{di}", (dx_p, dy_p, 0))
    # Bowl
    smooth_sphere(f"gd_b{di}", r=0.12, segs=14, rings=10, loc=(0, 0, 0.20),
                  parent=diya_e, mat_=M_DIYA_CLAY, scale=(1, 1, 0.5))
    # Oil
    cyl(f"gd_o{di}", r=0.10, depth=0.03, segs=12, loc=(0, 0, 0.30),
        parent=diya_e, mat_=M_DIYA_OIL)
    # Flame
    flame_d_e = empty(f"gd_f{di}_e", (0, 0, 0.36), parent=diya_e)
    smooth_cone(f"gd_fo{di}", r1=0.06, r2=0.01, depth=0.18, segs=10,
                loc=(0, 0, 0.09), parent=flame_d_e, mat_=M_FLAME_OUTER)
    smooth_cone(f"gd_fc{di}", r1=0.03, r2=0.005, depth=0.10, segs=8,
                loc=(0, 0, 0.06), parent=flame_d_e, mat_=M_FLAME_BRIGHT)
    diya_e["_phase"] = random.uniform(0, math.pi*2)
    ground_diyas.append({"e": diya_e, "flame": flame_d_e})

# ============================================================
# ⭐ 600 DIYAS + 400 JASMINE (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
floating_diyas = []
for i in range(600):
    px = random.uniform(-60, 60)
    py = random.uniform(-60, 60)
    pz = random.uniform(2, 18)
    d_e = empty(f"fd{i}", (px, py, pz))
    # Small diya body
    smooth_sphere(f"fd_b{i}", r=0.08, segs=10, rings=8, loc=(0, 0, 0),
                  parent=d_e, mat_=M_DIYA_CLAY, scale=(1, 1, 0.4))
    # Flame (signature glowing yellow)
    smooth_cone(f"fd_f{i}", r1=0.05, r2=0.005, depth=0.12, segs=8,
                loc=(0, 0, 0.06), parent=d_e, mat_=M_FLAME_BRIGHT)
    d_e["_phase"] = random.uniform(0, math.pi*2)
    d_e["_base_x"] = px; d_e["_base_y"] = py; d_e["_base_z"] = pz
    d_e["_amp_x"] = random.uniform(1.0, 2.5)
    d_e["_amp_y"] = random.uniform(1.0, 2.5)
    d_e["_speed"] = random.uniform(0.4, 1.0)
    floating_diyas.append(d_e)

# 400 jasmine flowers
jasmines = []
for i in range(400):
    px = random.uniform(-50, 50)
    py = random.uniform(-50, 50)
    pz = random.uniform(2, 16)
    j_e = empty(f"jm{i}", (px, py, pz))
    # Center yellow
    smooth_sphere(f"jm_c{i}", r=0.04, loc=(0, 0, 0),
                  parent=j_e, mat_=M_JASMINE_CENTER)
    # 5 white petals
    for pi in range(5):
        pa = (pi / 5.0) * math.pi * 2
        smooth_sphere(f"jm_p{i}_{pi}", r=0.05,
                      loc=(math.cos(pa)*0.06, math.sin(pa)*0.06, 0),
                      parent=j_e, mat_=M_JASMINE, scale=(1.4, 0.7, 0.3))
    j_e["_phase"] = random.uniform(0, math.pi*2)
    j_e["_base_x"] = px; j_e["_base_y"] = py; j_e["_base_z"] = pz
    j_e["_amp_x"] = random.uniform(1.0, 2.5)
    j_e["_amp_y"] = random.uniform(1.0, 2.5)
    j_e["_speed"] = random.uniform(0.5, 1.0)
    j_e["_fall"] = random.uniform(1.0, 2.5)
    jasmines.append(j_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Women sari dance + head turn
for w in women_sari:
    phase = w["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        w["root"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(5),
                                     math.cos(t * 2.0 + phase) * math.radians(8),
                                     w["root"].rotation_euler.z + math.sin(t * 1.5 + phase) * math.radians(5))
        w["root"].location.z = abs(math.sin(t * 2.5 + phase)) * 0.15
        w["root"].keyframe_insert("rotation_euler", frame=f)
        w["root"].keyframe_insert("location", frame=f)
        w["he"].rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(20))
        w["he"].keyframe_insert("rotation_euler", frame=f)

# Men dhoti pray pose
for m in men_dhoti:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3),
                                     math.cos(t * 1.5 + phase) * math.radians(3),
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(5), 0,
                                   math.cos(t * 1.2 + phase) * math.radians(12))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Musicians play
for mu in musicians_i:
    phase = mu["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        mu["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(4), 0,
                                       mu["root"].rotation_euler.z)
        mu["root"].keyframe_insert("rotation_euler", frame=f)
        sc_i = 1 + math.sin(t * 5.0 + phase) * 0.04
        mu["inst"].scale = (sc_i, sc_i, sc_i)
        mu["inst"].keyframe_insert("scale", frame=f)

# Ganesh slight breath
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    sc_g = 1 + math.sin(t * 1.0) * 0.02
    ganesh_e.scale = (sc_g, sc_g, sc_g)
    ganesh_e.keyframe_insert("scale", frame=f)
    head_g_e.rotation_euler = (0, 0, math.sin(t * 0.6) * math.radians(10))
    head_g_e.keyframe_insert("rotation_euler", frame=f)

# Trunk wave
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    trunk_e.rotation_euler = (math.radians(40) + math.sin(t * 1.5) * math.radians(10),
                                math.cos(t * 1.5) * math.radians(8), 0)
    trunk_e.keyframe_insert("rotation_euler", frame=f)

# Ground diyas flicker
for gd in ground_diyas:
    phase = gd["e"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        sc_fl = 1 + math.sin(t * 6.0 + phase) * 0.15
        gd["flame"].scale = (1 + math.cos(t * 5.0 + phase) * 0.10,
                              1 + math.sin(t * 5.0 + phase) * 0.10, sc_fl)
        gd["flame"].rotation_euler = (0, 0, math.sin(t * 4.0 + phase) * 0.2)
        gd["flame"].keyframe_insert("scale", frame=f)
        gd["flame"].keyframe_insert("rotation_euler", frame=f)

# Fireworks pulse
for fw in fireworks:
    phase = fw["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s_fw = 0.5 + abs(math.sin(t * 1.5 + phase)) * 1.5
        fw.scale = (s_fw, s_fw, s_fw)
        fw.keyframe_insert("scale", frame=f)

# 600 floating diyas drift
for fd in floating_diyas:
    phase = fd["_phase"]; speed = fd["_speed"]
    bx, by, bz = fd["_base_x"], fd["_base_y"], fd["_base_z"]
    ax, ay = fd["_amp_x"], fd["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + (t * 0.3) % 3
        fd.location = (x, y, z)
        sc_fd = 1 + math.sin(t * 4.0 + phase) * 0.15
        fd.scale = (sc_fd, sc_fd, sc_fd)
        fd.keyframe_insert("location", frame=f)
        fd.keyframe_insert("scale", frame=f)

# 400 jasmine fall
for j in jasmines:
    phase = j["_phase"]; speed = j["_speed"]; fall = j["_fall"]
    bx, by, bz = j["_base_x"], j["_base_y"], j["_base_z"]
    ax, ay = j["_amp_x"], j["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.3)
        if z < 0.3: z = bz
        j.location = (x, y, max(0.2, z))
        j.rotation_euler = (t * 2.0 + phase, t * 1.5 + phase, t * 2.5 + phase)
        j.keyframe_insert("location", frame=f)
        j.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_diwali_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_indian_diwali_festival_lights] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_indian_diwali_festival_lights] Taj Mahal + 8 colorful houses + Ganesh gold 4 arms signature + RANGOLI multicolor floor patterns + 6 sari women + 4 dhoti men + 4 musicians sitar/tabla/harmonium + masala bowls + 40 ground diyas + 8 fireworks + 600 floating diyas + 400 jasmine")
print("⭐ FIXES: 1 ground + 600 diyas + 400 jasmine (signature Diwali mandatory) ⭐")
