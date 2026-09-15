"""
proc_korean_gyeongbokgung_palace.py — 226e procédural AuroraIA (90e qualité)
Korean palace cherry festival: ONE ground + Geunjeongjeon palace + Gwanghwamun gate + 6 cherry trees + 8 royal guards + king + queen + 6 court ladies + peacocks + cranes + 700 sakura petals + 400 lanterns
FIXES : 1 ground + 700 sakura + 400 hanji lanterns thématiques signature Korean festival
"""
import bpy, bmesh, math, random, os

random.seed(0x70BE226)

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

# Korean dusk palette
M_SKY = mat("sky", (0.95, 0.65, 0.55, 1.0), 0.0, 0.7, emission=(0.92,0.62,0.52), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.85, 0.55, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.55), emission_strength=20.0)
M_CLOUD = mat("cloud", (1.0, 0.78, 0.72, 1.0), 0.0, 0.55, emission=(0.95,0.75,0.70), emission_strength=2.0, alpha=0.85)

# Ground stone courtyard
M_GROUND = mat("ground", (0.65, 0.55, 0.45, 1.0), 0.0, 0.80, emission=(0.60,0.52,0.42), emission_strength=0.4)
M_STONE_TILE = mat("stone_t", (0.78, 0.68, 0.55, 1.0), 0.0, 0.75, emission=(0.72,0.62,0.50), emission_strength=0.5)
M_STONE_DARK = mat("stone_d", (0.50, 0.42, 0.32, 1.0), 0.0, 0.85)
M_GRASS_K = mat("grass_k", (0.30, 0.55, 0.25, 1.0), 0.0, 0.75, emission=(0.28,0.50,0.22), emission_strength=0.4)

# DANCHEONG colors (signature Korean palace paint)
M_DANCH_RED = mat("dr", (0.85, 0.20, 0.18, 1.0), 0.0, 0.55, emission=(0.78,0.20,0.18), emission_strength=0.7)
M_DANCH_GREEN = mat("dg", (0.20, 0.55, 0.30, 1.0), 0.0, 0.55, emission=(0.18,0.50,0.28), emission_strength=0.7)
M_DANCH_BLUE = mat("db", (0.18, 0.40, 0.65, 1.0), 0.0, 0.55, emission=(0.18,0.38,0.60), emission_strength=0.7)
M_DANCH_YELLOW = mat("dy", (1.0, 0.82, 0.20, 1.0), 0.0, 0.50, emission=(1.0,0.82,0.20), emission_strength=0.9)
M_DANCH_WHITE = mat("dw", (0.92, 0.88, 0.82, 1.0), 0.0, 0.55, emission=(0.85,0.82,0.78), emission_strength=0.5)
M_DANCH_BLACK = mat("dbk", (0.12, 0.10, 0.08, 1.0), 0.0, 0.75)

# Palace
M_WOOD_RED = mat("w_r", (0.65, 0.20, 0.18, 1.0), 0.0, 0.65, emission=(0.60,0.20,0.18), emission_strength=0.5)
M_WOOD_DARK = mat("w_d", (0.35, 0.20, 0.10, 1.0), 0.0, 0.75, emission=(0.32,0.18,0.10), emission_strength=0.3)
M_WOOD_LIGHT = mat("w_l", (0.65, 0.42, 0.22, 1.0), 0.0, 0.70, emission=(0.60,0.40,0.20), emission_strength=0.4)
M_TILE_GREY = mat("tile_g", (0.30, 0.32, 0.32, 1.0), 0.2, 0.65, emission=(0.28,0.30,0.30), emission_strength=0.5)
M_GOLD = mat("gold_k", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.92,0.75,0.28), emission_strength=1.2)
M_WINDOW = mat("win", (1.0, 0.78, 0.40, 1.0), 0.0, 0.10, emission=(1.0,0.78,0.40), emission_strength=4.0, alpha=0.85)

# Sakura
M_SAKURA_PINK = mat("sak_p", (1.0, 0.65, 0.85, 1.0), 0.0, 0.45, emission=(1.0,0.65,0.85), emission_strength=1.5)
M_SAKURA_DEEP = mat("sak_d", (1.0, 0.45, 0.75, 1.0), 0.0, 0.45, emission=(1.0,0.45,0.75), emission_strength=1.7)
M_SAKURA_WHITE = mat("sak_w", (1.0, 0.92, 0.92, 1.0), 0.0, 0.45, emission=(1.0,0.88,0.88), emission_strength=1.3)
M_TRUNK_SAK = mat("trunk", (0.35, 0.22, 0.15, 1.0), 0.0, 0.85)
M_TRUNK_GRAY = mat("trunk_g", (0.42, 0.32, 0.28, 1.0), 0.0, 0.85)

# Hanji lanterns
M_LANTERN_RED = mat("lr", (1.0, 0.30, 0.20, 1.0), 0.0, 0.30, emission=(1.0,0.30,0.20), emission_strength=18.0, alpha=0.85)
M_LANTERN_PINK = mat("lp", (1.0, 0.55, 0.75, 1.0), 0.0, 0.30, emission=(1.0,0.55,0.75), emission_strength=16.0, alpha=0.85)
M_LANTERN_YELLOW = mat("ly", (1.0, 0.85, 0.30, 1.0), 0.0, 0.30, emission=(1.0,0.85,0.30), emission_strength=18.0, alpha=0.85)
M_LANTERN_FRAME = mat("lf_k", (0.55, 0.35, 0.18, 1.0), 0.0, 0.75)

# Hanbok (signature Korean costume)
M_SKIN_KOREAN = mat("skin", (0.95, 0.82, 0.72, 1.0), 0.0, 0.55, emission=(0.88,0.78,0.68), emission_strength=0.4)
M_HANBOK_RED = mat("hb_r", (0.85, 0.20, 0.30, 1.0), 0.0, 0.55, emission=(0.78,0.20,0.28), emission_strength=0.7)
M_HANBOK_PINK = mat("hb_p", (1.0, 0.55, 0.70, 1.0), 0.0, 0.55, emission=(0.95,0.50,0.65), emission_strength=0.7)
M_HANBOK_BLUE = mat("hb_b", (0.30, 0.55, 0.85, 1.0), 0.0, 0.55, emission=(0.28,0.50,0.78), emission_strength=0.6)
M_HANBOK_YELLOW = mat("hb_y", (1.0, 0.92, 0.40, 1.0), 0.0, 0.55, emission=(0.95,0.88,0.38), emission_strength=0.8)
M_HANBOK_PURPLE = mat("hb_pu", (0.65, 0.35, 0.78, 1.0), 0.0, 0.55, emission=(0.60,0.32,0.72), emission_strength=0.7)
M_HANBOK_GREEN = mat("hb_g", (0.30, 0.65, 0.40, 1.0), 0.0, 0.55, emission=(0.28,0.60,0.38), emission_strength=0.6)
M_HANBOK_WHITE = mat("hb_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.82), emission_strength=0.6)
M_DRAGON_YELLOW = mat("dy_r", (1.0, 0.82, 0.20, 1.0), 0.4, 0.40, emission=(1.0,0.82,0.20), emission_strength=1.2)
M_HAIR_KOREAN = mat("hair", (0.06, 0.04, 0.03, 1.0), 0.0, 0.85)

# Royal accessories
M_CROWN_GOLD = mat("crown_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.92,0.75,0.28), emission_strength=1.8)
M_SASH_GOLD = mat("sash_g", (1.0, 0.85, 0.30, 1.0), 0.6, 0.30, emission=(0.95,0.80,0.28), emission_strength=0.9)
M_JEWEL_RED = mat("jewel_r", (1.0, 0.18, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.18,0.30), emission_strength=5.0)
M_JEWEL_BLUE = mat("jewel_b", (0.30, 0.55, 1.0, 1.0), 0.0, 0.10, emission=(0.30,0.55,1.0), emission_strength=5.0)
M_JADE_K = mat("jade", (0.18, 0.65, 0.45, 1.0), 0.7, 0.20, emission=(0.18,0.65,0.45), emission_strength=2.0)

# Guard armor
M_ARMOR_BLACK = mat("arm_bk", (0.15, 0.12, 0.10, 1.0), 0.5, 0.45, emission=(0.13,0.10,0.08), emission_strength=0.3)
M_ARMOR_PLATE = mat("arm_p", (0.55, 0.45, 0.30, 1.0), 0.8, 0.30, emission=(0.50,0.42,0.28), emission_strength=0.5)
M_SWORD_STEEL = mat("sword", (0.85, 0.85, 0.92, 1.0), 0.95, 0.18, emission=(0.78,0.78,0.85), emission_strength=0.6)
M_TASSEL_RED = mat("tassel", (0.78, 0.20, 0.20, 1.0), 0.0, 0.65, emission=(0.72,0.20,0.20), emission_strength=0.7)

# Birds
M_PEACOCK = mat("peacock", (0.10, 0.45, 0.55, 1.0), 0.5, 0.35, emission=(0.10,0.45,0.55), emission_strength=1.5)
M_PEACOCK_BLUE = mat("pe_b", (0.10, 0.30, 0.85, 1.0), 0.6, 0.25, emission=(0.10,0.30,0.85), emission_strength=2.5)
M_PEACOCK_GREEN = mat("pe_g", (0.15, 0.65, 0.30, 1.0), 0.5, 0.30, emission=(0.15,0.65,0.30), emission_strength=2.0)
M_PEACOCK_GOLD = mat("pe_y", (0.95, 0.78, 0.30, 1.0), 0.8, 0.20, emission=(0.95,0.78,0.30), emission_strength=2.2)
M_CRANE_K = mat("crane", (0.98, 0.95, 0.92, 1.0), 0.0, 0.55, emission=(0.92,0.90,0.88), emission_strength=0.7)
M_CRANE_RED_K = mat("crane_r", (0.85, 0.18, 0.15, 1.0), 0.0, 0.55, emission=(0.78,0.18,0.15), emission_strength=0.8)
M_CRANE_BLACK = mat("crane_bk", (0.08, 0.06, 0.06, 1.0), 0.0, 0.70)

# Magnolia + willow
M_MAGNOLIA_FLOWER = mat("mag_f", (1.0, 0.92, 0.88, 1.0), 0.0, 0.40, emission=(1.0,0.88,0.85), emission_strength=1.5)
M_MAGNOLIA_LEAF = mat("mag_l", (0.18, 0.45, 0.20, 1.0), 0.0, 0.65, emission=(0.15,0.40,0.18), emission_strength=0.4)
M_WILLOW_K = mat("willow", (0.30, 0.55, 0.25, 1.0), 0.0, 0.55, emission=(0.28,0.50,0.22), emission_strength=0.5)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (25, 45, 30))
smooth_sphere("sun", r=5.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=5.0 + (i+1)*1.5, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

# Clouds
clouds = []
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    rad = random.uniform(32, 45)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(24, 32)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ ONE clean stone courtyard ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)
# Stone path tiles (organic 3D)
for i in range(60):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 35)
    smooth_sphere(f"tile{i}", r=random.uniform(0.30, 0.50), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_STONE_TILE if i % 2 == 0 else M_STONE_DARK,
                  scale=(1.4, 1.2, 0.20))
# Grass patches
for i in range(25):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(18, 38)
    smooth_sphere(f"grass_p{i}", r=random.uniform(0.30, 0.55),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_GRASS_K, scale=(1.4, 1.2, 0.18))

# ============ GEUNJEONGJEON PALACE (main throne hall) ============
palace_e = empty("palace", loc=(0, 18, 0))
# Massive stone base (signature double terrace)
beveled_cube("p_base1", (18, 12, 1.0), bevel_offset=0.06, loc=(0, 0, 0.5),
             parent=palace_e, mat_=M_STONE_TILE)
beveled_cube("p_base2", (16, 10, 1.0), bevel_offset=0.06, loc=(0, 0, 1.5),
             parent=palace_e, mat_=M_STONE_TILE)
# Stairs
for st in range(5):
    beveled_cube(f"p_st{st}", (5, 0.6, 0.20), bevel_offset=0.03,
                 loc=(0, -6.5 - st*0.5, 0.20 + st*0.20), parent=palace_e, mat_=M_STONE_TILE)
# 16 wooden columns (signature traditional Korean)
for x_idx in range(4):
    for y_idx in range(4):
        cx_col = (x_idx - 1.5) * 4.0
        cy_col = (y_idx - 1.5) * 2.4
        # Stone base
        cyl(f"p_col_base_{x_idx}_{y_idx}", r=0.45, depth=0.30, segs=14,
            loc=(cx_col, cy_col, 2.15), parent=palace_e, mat_=M_STONE_TILE)
        # Red wooden column
        cyl(f"p_col_{x_idx}_{y_idx}", r=0.32, depth=4.5, segs=16,
            loc=(cx_col, cy_col, 4.55), parent=palace_e, mat_=M_WOOD_RED)
        # Capital block (dancheong painted)
        beveled_cube(f"p_cap_{x_idx}_{y_idx}", (0.85, 0.85, 0.25), bevel_offset=0.04,
                     loc=(cx_col, cy_col, 6.92), parent=palace_e, mat_=M_DANCH_GREEN)
# Main walls red
beveled_cube("p_walls", (15, 9, 3.5), bevel_offset=0.06, loc=(0, 0, 4.55),
             parent=palace_e, mat_=M_WOOD_RED)
# Dancheong decorative band (signature multicolor)
for d_band in range(15):
    bx = (d_band - 7) * 1.0
    col = [M_DANCH_RED, M_DANCH_GREEN, M_DANCH_BLUE, M_DANCH_YELLOW, M_DANCH_WHITE][d_band % 5]
    beveled_cube(f"p_dch{d_band}", (0.9, 0.05, 0.6), bevel_offset=0.02,
                 loc=(bx, -4.55, 7.20), parent=palace_e, mat_=col)
    beveled_cube(f"p_dch_b{d_band}", (0.9, 0.05, 0.6), bevel_offset=0.02,
                 loc=(bx, 4.55, 7.20), parent=palace_e, mat_=col)
# Windows (glowing paper)
for wi in range(10):
    wx = (wi - 4.5) * 1.5
    beveled_cube(f"p_win{wi}", (1.0, 0.10, 1.5), bevel_offset=0.03,
                 loc=(wx, -4.55, 5.5), parent=palace_e, mat_=M_WINDOW)
# Massive PAGODA ROOF (signature multi-tier)
# Tier 1 lower roof
for side, side_mul in zip(("L", "R"), (-1, 1)):
    roof1 = beveled_cube(f"p_r1_{side}", (16, 7, 0.40), bevel_offset=0.04,
                        loc=(0, side_mul*3, 8.0), parent=palace_e, mat_=M_TILE_GREY)
    roof1.rotation_euler = (math.radians(side_mul*-25), 0, 0)
# Curving up tile ends (signature)
for x_idx in range(8):
    cx_t = (x_idx - 3.5) * 2.0
    for side in (-1, 1):
        # Upturned eaves corner
        eave = beveled_cube(f"p_eave_{x_idx}_{side}", (0.30, 0.25, 0.40), bevel_offset=0.03,
                            loc=(cx_t, side*5.5, 8.5), parent=palace_e, mat_=M_DANCH_GREEN)
        eave.rotation_euler = (math.radians(side*-30), 0, 0)
# 4 corner upturned curls (signature Korean roof corners)
for x in (-1, 1):
    for y in (-1, 1):
        curl_e = empty(f"p_curl_{x}{y}", (x*7.5, y*4.5, 8.5), parent=palace_e)
        curl_e.rotation_euler = (math.radians(y*-30), 0, math.radians(x*-30))
        # Curving up tip
        for s in range(4):
            smooth_sphere(f"p_curl_s{x}{y}_{s}", r=0.15 - s*0.02,
                          loc=(s*0.20, 0, s*0.18), parent=curl_e, mat_=M_DANCH_GREEN)
        # Dragon ornament
        smooth_cone(f"p_curl_dragon{x}{y}", r1=0.12, r2=0.04, depth=0.30, segs=10,
                    loc=(0.30, 0, 0.40), parent=curl_e, mat_=M_GOLD).rotation_euler = (0, math.radians(60), 0)
# Tier 2 upper roof (smaller)
beveled_cube("p_tier2_walls", (12, 7, 2.0), bevel_offset=0.06, loc=(0, 0, 9.5),
             parent=palace_e, mat_=M_WOOD_RED)
# Tier 2 dancheong
for d_band in range(12):
    bx = (d_band - 5.5) * 1.0
    col = [M_DANCH_RED, M_DANCH_GREEN, M_DANCH_BLUE, M_DANCH_YELLOW][d_band % 4]
    beveled_cube(f"p_t2_dch{d_band}", (0.85, 0.05, 0.4), bevel_offset=0.02,
                 loc=(bx, -3.55, 10.20), parent=palace_e, mat_=col)
# Tier 2 roof
for side, side_mul in zip(("L", "R"), (-1, 1)):
    roof2 = beveled_cube(f"p_r2_{side}", (13, 6, 0.35), bevel_offset=0.04,
                        loc=(0, side_mul*2.5, 11.7), parent=palace_e, mat_=M_TILE_GREY)
    roof2.rotation_euler = (math.radians(side_mul*-25), 0, 0)
# Tier 2 corner curls (smaller)
for x in (-1, 1):
    for y in (-1, 1):
        curl_e = empty(f"p_t2_curl_{x}{y}", (x*6.0, y*4.0, 12.2), parent=palace_e)
        curl_e.rotation_euler = (math.radians(y*-30), 0, math.radians(x*-30))
        for s in range(3):
            smooth_sphere(f"p_t2_curl_s{x}{y}_{s}", r=0.12 - s*0.02,
                          loc=(s*0.16, 0, s*0.14), parent=curl_e, mat_=M_DANCH_GREEN)
# Top decorative ridge with dragons
beveled_cube("p_ridge", (13, 0.30, 0.40), bevel_offset=0.03,
             loc=(0, 0, 12.7), parent=palace_e, mat_=M_DANCH_GREEN)
# Dragon ornaments on ridge (signature Korean)
for di in range(3):
    dx_d = (di - 1) * 4
    smooth_sphere(f"p_dragon_b{di}", r=0.35, loc=(dx_d, 0, 13.1),
                  parent=palace_e, mat_=M_GOLD, scale=(1, 1, 1.2))
    smooth_cone(f"p_dragon_t{di}", r1=0.15, r2=0.04, depth=0.50, segs=10,
                loc=(dx_d, 0, 13.5), parent=palace_e, mat_=M_GOLD)

# ============ GWANGHWAMUN GATE (3 arches signature entrance) ============
gate_e = empty("gate", loc=(0, -18, 0))
# Stone base
beveled_cube("g_base", (14, 4, 4), bevel_offset=0.08, loc=(0, 0, 2),
             parent=gate_e, mat_=M_STONE_TILE)
# 3 ARCH ENTRANCES (signature)
for arch_i in range(3):
    arch_x = (arch_i - 1) * 4.0
    # Arched opening (semicircle)
    for arch_pt in range(7):
        ang = math.pi - (arch_pt / 6.0) * math.pi
        ax = math.cos(ang) * 1.5
        az = 2 + math.sin(ang) * 1.5
        beveled_cube(f"g_arch{arch_i}_{arch_pt}", (0.6, 4, 0.4), bevel_offset=0.04,
                     loc=(arch_x + ax, 0, az), parent=gate_e, mat_=M_DANCH_BLACK)
# Upper red wall
beveled_cube("g_upper", (14, 4, 2.5), bevel_offset=0.06, loc=(0, 0, 5.5),
             parent=gate_e, mat_=M_WOOD_RED)
# Dancheong band
for d_band in range(14):
    bx = (d_band - 6.5) * 1.0
    col = [M_DANCH_GREEN, M_DANCH_BLUE, M_DANCH_YELLOW, M_DANCH_RED][d_band % 4]
    beveled_cube(f"g_dch{d_band}", (0.9, 0.05, 0.4), bevel_offset=0.02,
                 loc=(bx, -2.05, 6.0), parent=gate_e, mat_=col)
# Plaque (royal name signature)
beveled_cube("g_plaque", (5, 0.10, 1.2), bevel_offset=0.04,
             loc=(0, -2.10, 6.5), parent=gate_e, mat_=M_DANCH_BLUE)
for hi in range(5):
    smooth_sphere(f"g_p_char{hi}", r=0.18, loc=((hi-2)*0.7, -2.16, 6.5),
                  parent=gate_e, mat_=M_GOLD, scale=(0.8, 0.3, 1))
# Roof
for side, side_mul in zip(("L", "R"), (-1, 1)):
    roof_g = beveled_cube(f"g_roof_{side}", (15, 3, 0.30), bevel_offset=0.04,
                         loc=(0, side_mul*1.5, 7.8), parent=gate_e, mat_=M_TILE_GREY)
    roof_g.rotation_euler = (math.radians(side_mul*-25), 0, 0)
# Corner curls + dragons
for x in (-1, 1):
    for y in (-1, 1):
        curl_e = empty(f"g_curl_{x}{y}", (x*7, y*2.0, 8.2), parent=gate_e)
        curl_e.rotation_euler = (math.radians(y*-30), 0, math.radians(x*-30))
        for s in range(3):
            smooth_sphere(f"g_curl_s{x}{y}_{s}", r=0.12 - s*0.02,
                          loc=(s*0.16, 0, s*0.14), parent=curl_e, mat_=M_DANCH_GREEN)
# Top decorative
beveled_cube("g_ridge", (15, 0.3, 0.35), bevel_offset=0.03,
             loc=(0, 0, 8.7), parent=gate_e, mat_=M_DANCH_GREEN)

# ============ 6 SAKURA TREES ============
sakura_trees = []
sakura_pos = [(-22, 8, 0, 1.0), (22, 8, 0, 1.0),
              (-20, -2, 0, 0.95), (20, -2, 0, 0.95),
              (-22, -14, 0, 1.05), (22, -14, 0, 1.05)]
for i, (tx, ty, tz, sc) in enumerate(sakura_pos):
    base = empty(f"sak{i}", (tx, ty, tz))
    # Twisted trunk
    for s in range(5):
        seg = smooth_cone(f"sak{i}_t{s}", r1=(0.40 - s*0.04)*sc, r2=(0.36 - s*0.04)*sc,
                          depth=0.9*sc, segs=14,
                          loc=(random.uniform(-0.05,0.05)*sc, random.uniform(-0.05,0.05)*sc,
                               (s+0.5)*0.9*sc),
                          parent=base, mat_=M_TRUNK_GRAY)
        seg.rotation_euler = (math.radians(random.uniform(-5,5)),
                              math.radians(random.uniform(-5,5)), 0)
    # 5 branches
    for j in range(5):
        a = (j / 5.0) * math.pi * 2
        b_e = empty(f"sak{i}_be{j}", (0, 0, 4.5*sc), parent=base)
        b_e.rotation_euler = (math.radians(55), 0, a)
        for k in range(3):
            cyl(f"sak{i}_b{j}_{k}", r=(0.14 - k*0.025)*sc, depth=0.7*sc, segs=10,
                loc=(0, (k+0.5)*0.7*sc, 0), parent=b_e,
                mat_=M_TRUNK_SAK).rotation_euler = (math.radians(90), 0, 0)
    # Massive canopy
    for j in range(10):
        a = (j / 10.0) * math.pi * 2
        rad = random.uniform(1.5, 2.8) * sc
        col = [M_SAKURA_PINK, M_SAKURA_DEEP, M_SAKURA_WHITE][j % 3]
        smooth_sphere(f"sak{i}_can{j}", r=random.uniform(1.2, 1.8) * sc,
                      loc=(rad*math.cos(a), rad*math.sin(a), 4.8*sc + random.uniform(0, 1.2)),
                      parent=base, mat_=col, scale=(1, 1, 0.85))
    for j in range(12):
        a = random.uniform(0, math.pi*2)
        rad = random.uniform(1.0, 3.0) * sc
        col = random.choice([M_SAKURA_PINK, M_SAKURA_DEEP, M_SAKURA_WHITE])
        smooth_sphere(f"sak{i}_sc{j}", r=random.uniform(0.5, 0.9) * sc,
                      loc=(rad*math.cos(a), rad*math.sin(a), 4.8*sc + random.uniform(-0.3, 1.0)),
                      parent=base, mat_=col, scale=(1, 1, 0.7))
    base["_phase"] = random.uniform(0, math.pi*2)
    sakura_trees.append(base)

# ============ KING + QUEEN ============
def make_royal(name, loc, robe_mat, crown_mat=None, is_king=True, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long royal robe (signature wide)
    smooth_cone(f"{name}_robe", r1=0.65, r2=0.45, depth=2.0, segs=20,
                loc=(0, 0, 1.0), parent=base, mat_=robe_mat)
    # Decorative band at hem
    cyl(f"{name}_hem", r=0.66, depth=0.15, segs=20, loc=(0, 0, 0.10),
        parent=base, mat_=M_SASH_GOLD)
    # Dragon embroidery on chest (king only)
    if is_king:
        # Round dragon roundel (signature king)
        smooth_sphere(f"{name}_dragon", r=0.20, loc=(0, -0.35, 1.55),
                      parent=base, mat_=M_DRAGON_YELLOW, scale=(1, 0.3, 1))
        for di in range(8):
            da = (di / 8.0) * math.pi * 2
            smooth_sphere(f"{name}_drag_d{di}", r=0.05,
                          loc=(0.18*math.cos(da), -0.35, 1.55 + 0.18*math.sin(da)),
                          parent=base, mat_=M_DRAGON_YELLOW)
    else:
        # Peony flower (queen signature)
        for pe in range(6):
            pa = (pe / 6.0) * math.pi * 2
            smooth_sphere(f"{name}_peony{pe}", r=0.06,
                          loc=(0.10*math.cos(pa), -0.35, 1.55 + 0.10*math.sin(pa)),
                          parent=base, mat_=M_HANBOK_RED)
        smooth_sphere(f"{name}_peony_c", r=0.05, loc=(0, -0.35, 1.55),
                      parent=base, mat_=M_HANBOK_YELLOW)
    # Sash signature gold belt
    cyl(f"{name}_sash", r=0.55, depth=0.12, segs=16,
        loc=(0, 0, 1.30), parent=base, mat_=M_SASH_GOLD)
    # Sash buckle
    beveled_cube(f"{name}_buckle", (0.25, 0.10, 0.20), bevel_offset=0.03,
                 loc=(0, -0.50, 1.30), parent=base, mat_=M_GOLD)
    smooth_sphere(f"{name}_buckle_jewel", r=0.06, loc=(0, -0.58, 1.30),
                  parent=base, mat_=M_JEWEL_RED if is_king else M_JEWEL_BLUE)
    # Torso
    beveled_cube(f"{name}_torso", (0.45, 0.28, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 1.78), parent=base, mat_=robe_mat)
    # Neck
    cyl(f"{name}_neck", r=0.09, depth=0.18, segs=10,
        loc=(0, 0, 2.15), parent=base, mat_=M_SKIN_KOREAN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.35), parent=base)
    smooth_sphere(f"{name}_head", r=0.20, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_KOREAN)
    # Hair (dark, bun)
    smooth_sphere(f"{name}_hair", r=0.22, loc=(0, 0.05, 0.05),
                  parent=head_e, mat_=M_HAIR_KOREAN, scale=(1, 1, 0.9))
    if not is_king:
        # Queen's hair bun (signature)
        smooth_sphere(f"{name}_bun", r=0.18, loc=(0, 0.20, 0.10),
                      parent=head_e, mat_=M_HAIR_KOREAN, scale=(1.1, 0.7, 1.0))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.07, -0.16, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Crown
    if is_king:
        # King's GWANBO (signature winged crown)
        cyl(f"{name}_crown_base", r=0.22, depth=0.18, segs=18,
            loc=(0, 0, 0.20), parent=head_e, mat_=M_DANCH_BLACK)
        # Top dome
        smooth_sphere(f"{name}_crown_dome", r=0.22, loc=(0, 0, 0.35),
                      parent=head_e, mat_=M_DANCH_BLACK, scale=(1, 1, 0.7))
        # Wings on sides (signature gwanbo)
        for side in (-1, 1):
            wing = beveled_cube(f"{name}_crown_w{side}", (0.05, 0.30, 0.25), bevel_offset=0.02,
                               loc=(side*0.25, 0.05, 0.30), parent=head_e, mat_=M_DANCH_BLACK)
            wing.rotation_euler = (0, 0, math.radians(side*-20))
        # Gold ornaments on crown
        smooth_sphere(f"{name}_c_gem", r=0.04, loc=(0, -0.20, 0.25),
                      parent=head_e, mat_=M_GOLD)
    else:
        # Queen's HAIRPIN crown signature
        for ci in range(6):
            ca = (ci / 6.0) * math.pi - math.pi/2
            pin = cyl(f"{name}_pin{ci}", r=0.020, depth=0.25, segs=8,
                      loc=(math.sin(ca)*0.18, -0.05, 0.20), parent=head_e, mat_=M_GOLD)
            # Jewel top
            smooth_sphere(f"{name}_pin_g{ci}", r=0.05,
                          loc=(math.sin(ca)*0.18, -0.05, 0.35),
                          parent=head_e,
                          mat_=M_JEWEL_RED if ci % 2 == 0 else M_JADE_K)
        # Forehead ornament
        smooth_sphere(f"{name}_fb", r=0.06, loc=(0, -0.18, 0.18),
                      parent=head_e, mat_=M_JADE_K)
    # Wide signature flowing sleeves
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.35, 0, 2.05), parent=base)
        sh.rotation_euler = (math.radians(-15), 0, math.radians(side*-15))
        # Wide sleeve (signature hanbok)
        smooth_cone(f"{name}_sleeve{side_idx}", r1=0.25, r2=0.18, depth=0.70, segs=14,
                    loc=(0, 0, -0.35), parent=sh, mat_=robe_mat)
        cyl(f"{name}_fa{side_idx}", r=0.07, depth=0.25, segs=10,
            loc=(0, 0, -0.80), parent=sh, mat_=M_SKIN_KOREAN)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08, loc=(0, 0, -0.95),
                      parent=sh, mat_=M_SKIN_KOREAN)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

# Throne platform
throne_e = empty("throne", loc=(0, 18, 0))
beveled_cube("th_plat", (4, 3, 1.0), bevel_offset=0.06, loc=(0, 0, 3.0),
             parent=throne_e, mat_=M_STONE_TILE)
# King's throne (taller)
beveled_cube("th_k_seat", (1.4, 0.9, 0.4), bevel_offset=0.03,
             loc=(-1.0, 0, 3.70), parent=throne_e, mat_=M_DRAGON_YELLOW)
beveled_cube("th_k_back", (1.4, 0.20, 2.5), bevel_offset=0.04,
             loc=(-1.0, 0.4, 4.95), parent=throne_e, mat_=M_DRAGON_YELLOW)
# Queen's throne
beveled_cube("th_q_seat", (1.4, 0.9, 0.4), bevel_offset=0.03,
             loc=(1.0, 0, 3.70), parent=throne_e, mat_=M_HANBOK_BLUE)
beveled_cube("th_q_back", (1.4, 0.20, 2.5), bevel_offset=0.04,
             loc=(1.0, 0.4, 4.95), parent=throne_e, mat_=M_HANBOK_BLUE)
# Sun + moon mural behind (signature Irworobongdo)
mural = beveled_cube("mural", (3.5, 0.10, 2.0), bevel_offset=0.04,
                     loc=(0, 0.55, 5.5), parent=throne_e, mat_=M_DANCH_BLUE)
smooth_sphere("mural_sun", r=0.30, loc=(-0.8, 0.50, 6.0), parent=throne_e, mat_=M_DANCH_RED)
smooth_sphere("mural_moon", r=0.25, loc=(0.8, 0.50, 6.0), parent=throne_e, mat_=M_DANCH_WHITE)
# 5 mountain peaks (Irworobongdo signature)
for mi in range(5):
    smooth_cone(f"mural_peak{mi}", r1=0.30, r2=0.05, depth=0.50, segs=10,
                loc=((mi-2)*0.7, 0.55, 5.7), parent=throne_e, mat_=M_DANCH_GREEN)
# King + Queen seated
king = make_royal("king", (-1.0, 18, 3.95), M_DRAGON_YELLOW, is_king=True, facing=math.radians(180))
queen = make_royal("queen", (1.0, 18, 3.95), M_HANBOK_BLUE, is_king=False, facing=math.radians(180))

# ============ 8 ROYAL GUARDS in hanbok armor ============
def make_guard(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_hip{side_idx}", (side*0.15, 0, 0.85), parent=base)
        cyl(f"{name}_thigh{side_idx}", r=0.11, depth=0.45, segs=12,
            loc=(0, 0, -0.22), parent=hip, mat_=M_HANBOK_RED)
        cyl(f"{name}_calf{side_idx}", r=0.09, depth=0.40, segs=12,
            loc=(0, 0, -0.65), parent=hip, mat_=M_HANBOK_RED)
        beveled_cube(f"{name}_boot{side_idx}", (0.16, 0.30, 0.10),
                     loc=(0, 0.05, -0.85), parent=hip, mat_=M_DANCH_BLACK)
    # Long red robe over
    smooth_cone(f"{name}_robe", r1=0.45, r2=0.32, depth=1.2, segs=14,
                loc=(0, 0, 1.0), parent=base, mat_=M_HANBOK_RED)
    # Belt
    cyl(f"{name}_belt", r=0.36, depth=0.10, segs=14,
        loc=(0, 0, 1.40), parent=base, mat_=M_DANCH_BLACK)
    # Armor plate chest (signature)
    beveled_cube(f"{name}_armor", (0.42, 0.25, 0.55), bevel_offset=0.04,
                 loc=(0, 0, 1.75), parent=base, mat_=M_ARMOR_BLACK)
    # Gold plate trim
    beveled_cube(f"{name}_plate_g", (0.44, 0.05, 0.55), bevel_offset=0.02,
                 loc=(0, -0.13, 1.75), parent=base, mat_=M_ARMOR_PLATE)
    # Neck
    cyl(f"{name}_neck", r=0.08, depth=0.16, segs=10,
        loc=(0, 0, 2.10), parent=base, mat_=M_SKIN_KOREAN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.27), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_KOREAN)
    # Hair
    smooth_sphere(f"{name}_hair", r=0.20, loc=(0, 0.04, 0.05),
                  parent=head_e, mat_=M_HAIR_KOREAN, scale=(1, 1, 0.85))
    # GAT (signature Korean black hat)
    cyl(f"{name}_gat_brim", r=0.32, depth=0.04, segs=20,
        loc=(0, 0, 0.20), parent=head_e, mat_=M_DANCH_BLACK)
    cyl(f"{name}_gat_crown", r=0.16, depth=0.20, segs=16,
        loc=(0, 0, 0.32), parent=head_e, mat_=M_DANCH_BLACK)
    # Tassel red signature
    cyl(f"{name}_tassel", r=0.03, depth=0.30, segs=8,
        loc=(-0.30, 0, 0.10), parent=head_e, mat_=M_TASSEL_RED)
    smooth_sphere(f"{name}_tassel_b", r=0.06, loc=(-0.30, 0, -0.10),
                  parent=head_e, mat_=M_TASSEL_RED)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.14, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Mustache
    smooth_sphere(f"{name}_must", r=0.08, loc=(0, -0.14, -0.05),
                  parent=head_e, mat_=M_HAIR_KOREAN, scale=(1.5, 0.6, 0.3))
    # Arms (one holds sword)
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 2.00), parent=base)
        if side_idx == 0:
            # Salute position
            sh.rotation_euler = (math.radians(-80), 0, math.radians(-30))
        else:
            sh.rotation_euler = (math.radians(-10), 0, math.radians(10))
        cyl(f"{name}_uarm{side_idx}", r=0.08, depth=0.35, segs=12,
            loc=(0, 0, -0.18), parent=sh, mat_=M_HANBOK_RED)
        cyl(f"{name}_fa{side_idx}", r=0.07, depth=0.30, segs=10,
            loc=(0, 0, -0.50), parent=sh, mat_=M_SKIN_KOREAN)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07, loc=(0, 0, -0.68),
                      parent=sh, mat_=M_SKIN_KOREAN)
        arms_e.append(sh)
    # SWORD (signature)
    sword_e = empty(f"{name}_sword_e", (0.20, -0.4, 1.20), parent=base)
    sword_e.rotation_euler = (math.radians(80), 0, 0)
    # Scabbard
    cyl(f"{name}_scab", r=0.04, depth=0.85, segs=10, loc=(0, 0, 0),
        parent=sword_e, mat_=M_DANCH_BLACK)
    # Hilt
    cyl(f"{name}_hilt", r=0.04, depth=0.15, segs=10, loc=(0, 0, 0.50),
        parent=sword_e, mat_=M_GOLD)
    # Crossguard
    beveled_cube(f"{name}_cross", (0.10, 0.04, 0.04), bevel_offset=0.01,
                 loc=(0, 0, 0.60), parent=sword_e, mat_=M_GOLD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

guards = []
# Lined up in front of palace
guard_specs = [
    ("g1", (-8, 14, 0), math.radians(180)),
    ("g2", (-5, 14, 0), math.radians(180)),
    ("g3", (-2, 14, 0), math.radians(180)),
    ("g4", (2, 14, 0), math.radians(180)),
    ("g5", (5, 14, 0), math.radians(180)),
    ("g6", (8, 14, 0), math.radians(180)),
    ("g7", (-8, 10, 0), math.radians(180)),
    ("g8", (8, 10, 0), math.radians(180)),
]
for spec in guard_specs:
    name, loc, fac = spec
    g = make_guard(name, loc, facing=fac)
    guards.append(g)

# ============ 6 COURT LADIES in hanbok ============
def make_court_lady(name, loc, top_mat, skirt_mat, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long flowing skirt (signature chima)
    smooth_cone(f"{name}_skirt", r1=0.55, r2=0.40, depth=1.6, segs=18,
                loc=(0, 0, 0.80), parent=base, mat_=skirt_mat)
    # Inner pleats
    for pl in range(8):
        pa = (pl / 8.0) * math.pi * 2
        beveled_cube(f"{name}_pleat{pl}", (0.06, 0.10, 1.4), bevel_offset=0.01,
                     loc=(0.50*math.cos(pa), 0.50*math.sin(pa), 0.80),
                     parent=base, mat_=skirt_mat)
    # Wide ribbon belt (signature)
    cyl(f"{name}_belt", r=0.45, depth=0.08, segs=14,
        loc=(0, 0, 1.50), parent=base, mat_=M_SASH_GOLD)
    # Bow (signature otgoreum)
    beveled_cube(f"{name}_bow", (0.18, 0.10, 0.20), bevel_offset=0.03,
                 loc=(0, -0.35, 1.55), parent=base, mat_=top_mat)
    # Long ribbons hanging
    for ri in range(2):
        beveled_cube(f"{name}_ribbon{ri}", (0.06, 0.04, 0.5),
                     loc=((ri*2-1)*0.05, -0.40, 1.30), parent=base, mat_=top_mat)
    # Short top (jeogori signature) - wraps around chest
    smooth_sphere(f"{name}_top", r=0.30, loc=(0, 0, 1.80),
                  parent=base, mat_=top_mat, scale=(1.2, 0.7, 0.7))
    # Neck
    cyl(f"{name}_neck", r=0.08, depth=0.16, segs=10,
        loc=(0, 0, 2.05), parent=base, mat_=M_SKIN_KOREAN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.22), parent=base)
    smooth_sphere(f"{name}_head", r=0.17, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_KOREAN)
    # Hair with traditional bun (signature)
    smooth_sphere(f"{name}_hair", r=0.18, loc=(0, 0.05, 0.05),
                  parent=head_e, mat_=M_HAIR_KOREAN, scale=(1, 1, 0.85))
    smooth_sphere(f"{name}_bun", r=0.16, loc=(0, 0.22, 0.05),
                  parent=head_e, mat_=M_HAIR_KOREAN, scale=(1.1, 0.7, 1))
    # Hair pin (signature binyeo)
    cyl(f"{name}_binyeo", r=0.020, depth=0.30, segs=8,
        loc=(0, 0.22, 0.10), parent=head_e, mat_=M_GOLD).rotation_euler = (0, math.radians(90), 0)
    smooth_sphere(f"{name}_binyeo_top", r=0.05, loc=(0.18, 0.22, 0.10),
                  parent=head_e, mat_=M_JADE_K)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.13, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Wide sleeves (signature flowing)
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.95), parent=base)
        sh.rotation_euler = (math.radians(-25), 0, math.radians(side*-15))
        # Wide jeogori sleeve
        smooth_cone(f"{name}_sleeve{side_idx}", r1=0.22, r2=0.16, depth=0.60, segs=14,
                    loc=(0, 0, -0.30), parent=sh, mat_=top_mat)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.25, segs=10,
            loc=(0, 0, -0.72), parent=sh, mat_=M_SKIN_KOREAN)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07, loc=(0, 0, -0.88),
                      parent=sh, mat_=M_SKIN_KOREAN)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

court_ladies = []
lady_specs = [
    ("lady1", (-6, 5, 0), M_HANBOK_PINK, M_HANBOK_RED, math.radians(45)),
    ("lady2", (-3, 6, 0), M_HANBOK_BLUE, M_HANBOK_PINK, math.radians(20)),
    ("lady3", (0, 7, 0), M_HANBOK_YELLOW, M_HANBOK_GREEN, math.radians(0)),
    ("lady4", (3, 6, 0), M_HANBOK_PURPLE, M_HANBOK_BLUE, math.radians(-20)),
    ("lady5", (6, 5, 0), M_HANBOK_GREEN, M_HANBOK_YELLOW, math.radians(-45)),
    ("lady6", (0, 3, 0), M_HANBOK_WHITE, M_HANBOK_RED, math.radians(180)),
]
for spec in lady_specs:
    name, loc, top, skirt, fac = spec
    l = make_court_lady(name, loc, top, skirt, facing=fac)
    court_ladies.append(l)

# ============ 4 PEACOCKS + 2 CRANES ============
def make_peacock_k(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.28, segs=18, rings=12, loc=(0, 0, 0.55),
                  parent=base, mat_=M_PEACOCK, scale=(1.4, 1, 1.1))
    # Neck
    neck_e = empty(f"{name}_ne", (0.30, 0, 0.7), parent=base)
    for ni in range(4):
        cyl(f"{name}_neck{ni}", r=0.06, depth=0.15, segs=10,
            loc=(0, 0, ni*0.13), parent=neck_e, mat_=M_PEACOCK)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 0.55), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_PEACOCK)
    # Crown feathers
    for cf in range(5):
        cfa = (cf - 2) * 0.2
        cf_obj = smooth_cone(f"{name}_cr{cf}", r1=0.015, r2=0.03, depth=0.15, segs=8,
                             loc=(0.02*math.sin(cfa), 0, 0.18), parent=head_e,
                             mat_=M_PEACOCK_BLUE)
        smooth_sphere(f"{name}_cr_tip{cf}", r=0.025,
                      loc=(0.02*math.sin(cfa), 0, 0.32), parent=head_e, mat_=M_PEACOCK_GOLD)
    smooth_cone(f"{name}_beak", r1=0.03, r2=0.005, depth=0.10, segs=8,
                loc=(0.08, 0, -0.02), parent=head_e,
                mat_=M_GOLD).rotation_euler = (0, math.radians(90), 0)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.02,
                      loc=(0.03, side*0.05, 0.04), parent=head_e, mat_=M_DANCH_BLACK)
    # Tail fan
    tail_e = empty(f"{name}_te", (-0.30, 0, 0.65), parent=base)
    tail_e.rotation_euler = (math.radians(-30), 0, 0)
    for fi in range(25):
        fa = (fi - 12) * 0.10
        f_len = 2.2 - abs(fa) * 0.5
        f_e = empty(f"{name}_fe{fi}", (0, 0, 0), parent=tail_e)
        f_e.rotation_euler = (0, 0, fa)
        beveled_cube(f"{name}_fs{fi}", (0.04, f_len, 0.02), bevel_offset=0.01,
                     loc=(0, f_len*0.5, 0), parent=f_e, mat_=M_PEACOCK_GREEN)
        # Eye marking
        smooth_sphere(f"{name}_fe_o{fi}", r=0.15, loc=(0, f_len, 0),
                      parent=f_e, mat_=M_PEACOCK_BLUE, scale=(0.7, 1, 0.2))
        smooth_sphere(f"{name}_fe_m{fi}", r=0.10, loc=(0, f_len, 0.03),
                      parent=f_e, mat_=M_PEACOCK_GOLD, scale=(0.7, 1, 0.2))
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.04, depth=0.5, segs=10,
            loc=(0.05, side*0.08, 0.25), parent=base, mat_=M_DANCH_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "tail": tail_e, "he": head_e}

peacocks = [
    make_peacock_k("peacock1", (-12, 4, 0), math.radians(30)),
    make_peacock_k("peacock2", (12, 4, 0), math.radians(-30)),
    make_peacock_k("peacock3", (-12, -8, 0), math.radians(60)),
    make_peacock_k("peacock4", (12, -8, 0), math.radians(-60)),
]

def make_crane_k(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.35, segs=20, rings=14, loc=(0, 0, 1.0),
                  parent=base, mat_=M_CRANE_K, scale=(2, 0.9, 1))
    # Long S-neck
    neck_e = empty(f"{name}_ne", (0.50, 0, 1.30), parent=base)
    for ni in range(5):
        a = ni * 0.5
        nx = 0.15 * math.sin(a)
        nz = 0.15 * math.cos(a) + ni * 0.18
        cyl(f"{name}_neck{ni}", r=0.06, depth=0.20, segs=10,
            loc=(nx, 0, nz), parent=neck_e, mat_=M_CRANE_K)
    head_e = empty(f"{name}_he", (0.15, 0, 1.10), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_CRANE_K)
    # Red crown
    smooth_sphere(f"{name}_crown", r=0.06, loc=(0, 0.04, 0.06),
                  parent=head_e, mat_=M_CRANE_RED_K, scale=(1, 1, 0.6))
    smooth_cone(f"{name}_beak", r1=0.04, r2=0.005, depth=0.25, segs=10,
                loc=(0.15, 0, -0.05), parent=head_e,
                mat_=M_CRANE_BLACK).rotation_euler = (math.radians(75), 0, 0)
    smooth_sphere(f"{name}_eye", r=0.02, loc=(0.05, 0, 0.05),
                  parent=head_e, mat_=M_CRANE_BLACK)
    # Folded wings
    for side in (-1, 1):
        beveled_cube(f"{name}_w{side}", (0.10, 0.40, 0.30), bevel_offset=0.03,
                     loc=(0, side*0.25, 1.0), parent=base, mat_=M_CRANE_K)
    beveled_cube(f"{name}_tail", (0.30, 0.20, 0.10), loc=(-0.55, 0, 1.0),
                 parent=base, mat_=M_CRANE_BLACK)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.03, depth=0.90, segs=10,
            loc=(side*0.05, 0, 0.45), parent=base, mat_=M_CRANE_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

cranes = [
    make_crane_k("crane1", (-15, 0, 0), math.radians(30)),
    make_crane_k("crane2", (15, 0, 0), math.radians(-30)),
]

# Magnolia + willow trees
# Magnolia
mag_e = empty("magnolia", loc=(-25, -20, 0))
for s in range(4):
    cyl(f"mag_t{s}", r=0.25 - s*0.03, depth=1.0, segs=12,
        loc=(0, 0, (s+0.5)*1.0), parent=mag_e, mat_=M_TRUNK_GRAY)
# Branches + flowers
for b in range(5):
    ba = (b / 5.0) * math.pi * 2
    b_e = empty(f"mag_b{b}", (math.cos(ba)*0.3, math.sin(ba)*0.3, 3.5), parent=mag_e)
    b_e.rotation_euler = (math.radians(50), 0, ba)
    for k in range(2):
        cyl(f"mag_br{b}_{k}", r=0.07, depth=0.7, segs=10,
            loc=(0, k*0.7, 0), parent=b_e, mat_=M_TRUNK_GRAY).rotation_euler = (math.radians(90), 0, 0)
    # White flowers
    for fl in range(5):
        smooth_sphere(f"mag_fl{b}_{fl}", r=0.20,
                      loc=(random.uniform(-0.3,0.3), 0.8 + random.uniform(0,0.5),
                           random.uniform(-0.2,0.2)), parent=b_e, mat_=M_MAGNOLIA_FLOWER)
    # Leaves
    for lv in range(6):
        smooth_sphere(f"mag_lv{b}_{lv}", r=0.18,
                      loc=(random.uniform(-0.4,0.4), random.uniform(0.5,1.5),
                           random.uniform(-0.4,0.4)), parent=b_e, mat_=M_MAGNOLIA_LEAF,
                      scale=(1, 1.3, 0.5))

# Willow
willow_e = empty("willow_k", loc=(25, -20, 0))
cyl("w_trunk", r=0.45, depth=5.5, segs=14, loc=(0, 0, 2.75),
    parent=willow_e, mat_=M_TRUNK_GRAY).rotation_euler = (math.radians(10), 0, 0)
for bi in range(8):
    ba = (bi / 8.0) * math.pi * 2
    b_e = empty(f"w_b_e{bi}", (math.cos(ba)*0.3, math.sin(ba)*0.3, 5.0), parent=willow_e)
    b_e.rotation_euler = (math.radians(25), 0, ba)
    for sk in range(4):
        cyl(f"w_b{bi}_{sk}", r=0.08 - sk*0.014, depth=0.5, segs=8,
            loc=(0, sk*0.50, sk*-0.18), parent=b_e, mat_=M_TRUNK_GRAY)
    # Cascading leaves
    for hi in range(4):
        for sk in range(6):
            smooth_sphere(f"w_l{bi}_{hi}_{sk}", r=random.uniform(0.08, 0.14),
                          loc=(hi*0.1 + sk*0.05, 2 + sk*0.20, -sk*0.25 - 0.20),
                          parent=b_e, mat_=M_WILLOW_K, scale=(0.8, 1.4, 0.5))

# ============================================================
# ⭐ 700 SAKURA PETALS + 400 HANJI LANTERNS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 700 sakura petals
sakura_petals = []
for i in range(700):
    px = random.uniform(-42, 42)
    py = random.uniform(-42, 42)
    pz = random.uniform(1, 25)
    col = [M_SAKURA_PINK, M_SAKURA_DEEP, M_SAKURA_WHITE][i % 3]
    p_obj = smooth_sphere(f"sp{i}", r=random.uniform(0.08, 0.14), segs=10, rings=6,
                          loc=(px, py, pz), mat_=col,
                          scale=(1.5, 0.6, 0.12))
    p_obj.rotation_euler = (random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2))
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_speed"] = random.uniform(0.4, 1.3)
    p_obj["_drift_x"] = random.uniform(-1.6, 1.6)
    p_obj["_drift_y"] = random.uniform(-1.6, 1.6)
    sakura_petals.append(p_obj)

# 400 hanji paper lanterns rising
hanji_lanterns = []
for i in range(400):
    px = random.uniform(-42, 42)
    py = random.uniform(-42, 42)
    pz = random.uniform(0.5, 25)
    l_e = empty(f"hl{i}", (px, py, pz))
    col = [M_LANTERN_RED, M_LANTERN_PINK, M_LANTERN_YELLOW][i % 3]
    smooth_sphere(f"hl_b{i}", r=random.uniform(0.18, 0.30), segs=14, rings=10,
                  loc=(0, 0, 0), parent=l_e, mat_=col, scale=(1, 1, 1.3))
    # Top frame
    cyl(f"hl_t{i}", r=0.05, depth=0.04, segs=8, loc=(0, 0, 0.15),
        parent=l_e, mat_=M_LANTERN_FRAME)
    # Bottom tassel
    cyl(f"hl_ta{i}", r=0.018, depth=0.20, segs=6, loc=(0, 0, -0.30),
        parent=l_e, mat_=M_LANTERN_FRAME)
    smooth_sphere(f"hl_ta_b{i}", r=0.03, loc=(0, 0, -0.45),
                  parent=l_e, mat_=M_TASSEL_RED)
    l_e["_phase"] = random.uniform(0, math.pi*2)
    l_e["_base_x"] = px; l_e["_base_y"] = py; l_e["_base_z"] = pz
    l_e["_speed"] = random.uniform(0.3, 0.9)
    l_e["_drift_x"] = random.uniform(-0.5, 0.5)
    l_e["_drift_y"] = random.uniform(-0.5, 0.5)
    hanji_lanterns.append(l_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Sakura trees sway
for t in sakura_trees:
    phase = t["_phase"]
    for f in range(1, total_frames + 1, 5):
        t_v = (f - 1) / fps
        t.rotation_euler = (math.sin(t_v * 0.8 + phase) * math.radians(2),
                             math.cos(t_v * 0.7 + phase) * math.radians(1.5),
                             0)
        t.keyframe_insert("rotation_euler", frame=f)

# King + Queen majestic movement
for r in (king, queen):
    phase = r["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        r["he"].rotation_euler = (math.sin(t * 0.5 + phase) * math.radians(3), 0,
                                   math.sin(t * 0.4 + phase) * math.radians(10))
        r["he"].keyframe_insert("rotation_euler", frame=f)
        for ai, arm in enumerate(r["arms"]):
            wave = math.sin(t * 1.0 + phase + ai * math.pi) * math.radians(5)
            arm.rotation_euler = (math.radians(-15) + wave, 0, math.radians(side*-15 if False else 0))
            arm.keyframe_insert("rotation_euler", frame=f)

# Guards salute (rigid sway)
for g in guards:
    phase = g["root"]["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        g["he"].rotation_euler = (math.sin(t * 0.6 + phase) * math.radians(2), 0,
                                   math.sin(t * 0.4 + phase) * math.radians(5))
        g["he"].keyframe_insert("rotation_euler", frame=f)

# Court ladies grace
for l in court_ladies:
    phase = l["root"]["_phase"]
    base_z = l["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        l["root"].location.z = base_z + math.sin(t * 1.2 + phase) * 0.03
        l["root"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3),
                                      math.cos(t * 0.6 + phase) * math.radians(2),
                                      l["root"].rotation_euler.z)
        l["root"].keyframe_insert("location", frame=f)
        l["root"].keyframe_insert("rotation_euler", frame=f)
        for ai, arm in enumerate(l["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 1.5 + phase + ai * math.pi) * math.radians(10)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        l["he"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(5), 0,
                                    math.sin(t * 1.0 + phase) * math.radians(15))
        l["he"].keyframe_insert("rotation_euler", frame=f)

# Peacocks tail fan
for p in peacocks:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        p["tail"].rotation_euler = (math.radians(-30) + math.sin(t * 1.0 + phase) * math.radians(10),
                                      0,
                                      math.sin(t * 1.5 + phase) * math.radians(20))
        p["tail"].keyframe_insert("rotation_euler", frame=f)
        p["he"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(40))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Cranes head/neck
for c in cranes:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        c["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(8), 0,
                                    math.sin(t * 0.6 + phase) * math.radians(20))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Clouds drift
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 0.7,
                        by + math.cos(t * 0.25 + phase) * 0.7,
                        c_e.location.z)
        c_e.keyframe_insert("location", frame=f)

# Sun halos
for obj in bpy.data.objects:
    if obj.name.startswith("sun_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.7) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 700 SAKURA PETALS falling + 400 HANJI LANTERNS rising
# ============================================================
for p in sakura_petals:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    drift_x = p["_drift_x"]; drift_y = p["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        z = bz - (speed * t) % 25
        x = bx + drift_x * math.sin(t * 1.3 + phase) * 0.6
        y = by + drift_y * math.cos(t * 1.1 + phase) * 0.6
        rx = phase + t * 1.7
        ry = phase + t * 1.5
        rz = phase + t * 2.0
        p.location = (x, y, max(0.05, z))
        p.rotation_euler = (rx, ry, rz)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

for l in hanji_lanterns:
    phase = l["_phase"]; speed = l["_speed"]
    bx, by, bz = l["_base_x"], l["_base_y"], l["_base_z"]
    drift_x = l["_drift_x"]; drift_y = l["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        # Rise gently
        z = bz + (speed * t) % 26
        x = bx + drift_x * math.sin(t * 0.5 + phase)
        y = by + drift_y * math.cos(t * 0.4 + phase)
        l.location = (x, y, min(28, z))
        sc = 1 + math.sin(t * 1.5 + phase) * 0.10
        l.scale = (sc, sc, sc)
        l.keyframe_insert("location", frame=f)
        l.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_korea_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_korean_gyeongbokgung_palace] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_korean_gyeongbokgung_palace] ONE ground + Geunjeongjeon palace 2-tier dancheong + Gwanghwamun gate 3 arches + 6 sakura + 8 royal guards + king dragon + queen peony + 6 court ladies hanbok + 4 peacocks + 2 cranes + magnolia + willow + 700 SAKURA + 400 LANTERNS")
print("⭐ FIXES: 1 ground + 700 sakura petals + 400 hanji lanterns (signature Korean festival mandatory) ⭐")
