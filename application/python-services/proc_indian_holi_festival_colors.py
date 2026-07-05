"""
proc_indian_holi_festival_colors.py — 235e procédural AuroraIA (100e qualité MILESTONE)
Indian Holi festival: ONE temple ground + Taj Mahal + Hindu temple + Ganesh + Shiva + 8 Holi dancers + 4 musicians + brahmane + 6 dancing girls + 4 sacred cows + monkeys + peacocks + mandala + 1000 color powder particles
FIXES : 1 ground + 1000 color powder particles signature Holi MILESTONE DOUBLE quantity
"""
import bpy, bmesh, math, random, os

random.seed(0x10210C235)

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

# Indian spring palette - bright Holi
M_SKY = mat("sky", (0.55, 0.72, 0.95, 1.0), 0.0, 0.7, emission=(0.50,0.68,0.92), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.92, 0.55, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.55), emission_strength=22.0)
M_CLOUD = mat("cloud", (1.0, 1.0, 0.92, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.88), emission_strength=2.0, alpha=0.85)

# Ground stone
M_GROUND = mat("ground", (0.78, 0.62, 0.42, 1.0), 0.0, 0.80, emission=(0.72,0.58,0.38), emission_strength=0.5)
M_STONE_TILE = mat("stone_t", (0.85, 0.72, 0.50, 1.0), 0.0, 0.75, emission=(0.78,0.68,0.45), emission_strength=0.5)
M_MARBLE = mat("marble", (0.98, 0.92, 0.85, 1.0), 0.0, 0.35, emission=(0.92,0.88,0.82), emission_strength=0.5)

# Holi colors (signature)
M_HOLI_PINK = mat("h_pink", (1.0, 0.20, 0.60, 1.0), 0.0, 0.45, emission=(0.95,0.20,0.55), emission_strength=2.5)
M_HOLI_MAGENTA = mat("h_mag", (0.95, 0.10, 0.55, 1.0), 0.0, 0.45, emission=(0.90,0.10,0.50), emission_strength=2.8)
M_HOLI_RED = mat("h_red", (1.0, 0.15, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.15,0.20), emission_strength=2.8)
M_HOLI_YELLOW = mat("h_yel", (1.0, 0.92, 0.20, 1.0), 0.0, 0.40, emission=(1.0,0.90,0.20), emission_strength=3.0)
M_HOLI_GREEN = mat("h_grn", (0.20, 0.95, 0.30, 1.0), 0.0, 0.45, emission=(0.20,0.90,0.28), emission_strength=2.8)
M_HOLI_BLUE = mat("h_blu", (0.20, 0.55, 1.0, 1.0), 0.0, 0.45, emission=(0.20,0.50,0.95), emission_strength=2.6)
M_HOLI_PURPLE = mat("h_pur", (0.75, 0.20, 0.95, 1.0), 0.0, 0.45, emission=(0.70,0.20,0.90), emission_strength=2.7)
M_HOLI_ORANGE = mat("h_org", (1.0, 0.50, 0.15, 1.0), 0.0, 0.40, emission=(1.0,0.50,0.15), emission_strength=2.9)
M_HOLI_CYAN = mat("h_cya", (0.30, 0.95, 0.95, 1.0), 0.0, 0.45, emission=(0.28,0.90,0.90), emission_strength=2.7)
M_HOLI_LIME = mat("h_lim", (0.65, 1.0, 0.30, 1.0), 0.0, 0.40, emission=(0.62,0.95,0.28), emission_strength=2.8)

# Skin
M_SKIN_INDIAN = mat("skin", (0.78, 0.55, 0.38, 1.0), 0.0, 0.55, emission=(0.72,0.52,0.36), emission_strength=0.4)
M_HAIR_BLACK_I = mat("hair_b", (0.06, 0.04, 0.03, 1.0), 0.0, 0.85)

# Saree white (gets stained with colors)
M_SAREE_WHITE = mat("saree_w", (0.92, 0.88, 0.82, 1.0), 0.0, 0.65, emission=(0.85,0.82,0.78), emission_strength=0.6)
M_SAREE_GOLD_TRIM = mat("saree_g", (1.0, 0.78, 0.30, 1.0), 0.7, 0.25, emission=(0.95,0.75,0.28), emission_strength=1.0)
M_KURTA_WHITE = mat("kurta_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.70, emission=(0.88,0.85,0.82), emission_strength=0.5)
M_DHOTI_WHITE = mat("dhoti_w", (0.92, 0.88, 0.85, 1.0), 0.0, 0.75, emission=(0.85,0.82,0.78), emission_strength=0.5)

# Brahmane (priest)
M_ROBE_ORANGE = mat("robe_or", (0.95, 0.55, 0.15, 1.0), 0.0, 0.60, emission=(0.90,0.50,0.13), emission_strength=0.9)
M_ROBE_SAFFRON = mat("robe_s", (1.0, 0.65, 0.20, 1.0), 0.0, 0.55, emission=(0.95,0.60,0.18), emission_strength=1.0)

# Temple
M_TEMPLE_STONE = mat("temple_s", (0.82, 0.65, 0.42, 1.0), 0.0, 0.75, emission=(0.75,0.60,0.38), emission_strength=0.5)
M_TEMPLE_RED = mat("temple_r", (0.75, 0.18, 0.15, 1.0), 0.0, 0.65, emission=(0.70,0.18,0.15), emission_strength=0.7)
M_TEMPLE_GOLD = mat("temple_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.92,0.75,0.28), emission_strength=1.2)
M_DOME_INDIAN = mat("dome_i", (1.0, 0.92, 0.78, 1.0), 0.5, 0.30, emission=(0.95,0.88,0.72), emission_strength=0.8)

# Ganesh + Shiva
M_GANESH_GOLD = mat("ganesh_g", (1.0, 0.82, 0.30, 1.0), 0.95, 0.18, emission=(0.95,0.78,0.28), emission_strength=1.5)
M_GANESH_RED = mat("ganesh_r", (0.85, 0.20, 0.20, 1.0), 0.0, 0.55, emission=(0.78,0.20,0.20), emission_strength=0.8)
M_SHIVA_BLUE = mat("shiva_b", (0.20, 0.50, 0.85, 1.0), 0.0, 0.55, emission=(0.18,0.45,0.80), emission_strength=1.0)
M_SHIVA_WHITE = mat("shiva_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.82), emission_strength=0.6)

# Cows + monkeys + peacocks
M_COW_HOLI = mat("cow_h", (0.85, 0.72, 0.55, 1.0), 0.0, 0.75, emission=(0.78,0.68,0.50), emission_strength=0.4)
M_COW_HORN = mat("cow_horn", (0.85, 0.78, 0.55, 1.0), 0.2, 0.55)
M_MONKEY = mat("monkey", (0.65, 0.42, 0.25, 1.0), 0.0, 0.75)
M_MONKEY_FACE = mat("monkey_f", (0.92, 0.62, 0.62, 1.0), 0.0, 0.65)
M_PEACOCK = mat("peacock", (0.10, 0.45, 0.55, 1.0), 0.5, 0.35, emission=(0.10,0.45,0.55), emission_strength=1.5)
M_PEACOCK_BLUE = mat("pe_b", (0.10, 0.30, 0.85, 1.0), 0.6, 0.25, emission=(0.10,0.30,0.85), emission_strength=2.5)
M_PEACOCK_GREEN = mat("pe_g", (0.15, 0.65, 0.30, 1.0), 0.5, 0.30, emission=(0.15,0.65,0.30), emission_strength=2.0)
M_PEACOCK_GOLD = mat("pe_y", (0.95, 0.78, 0.30, 1.0), 0.8, 0.20, emission=(0.95,0.78,0.30), emission_strength=2.2)

# Marigolds (signature garlands)
M_MARIGOLD_ORANGE = mat("mar_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.45, emission=(0.95,0.50,0.13), emission_strength=2.0)
M_MARIGOLD_YELLOW = mat("mar_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.80,0.20), emission_strength=2.2)

# Tabla / Sitar / Harmonium / Dholak
M_TABLA_WOOD = mat("tabla_w", (0.45, 0.25, 0.12, 1.0), 0.0, 0.55, emission=(0.42,0.22,0.10), emission_strength=0.5)
M_TABLA_SKIN = mat("tabla_sk", (0.92, 0.85, 0.75, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.70), emission_strength=0.4)
M_SITAR_BODY = mat("sitar", (0.65, 0.45, 0.25, 1.0), 0.3, 0.45, emission=(0.60,0.42,0.22), emission_strength=0.5)
M_HARMONIUM = mat("harm", (0.45, 0.22, 0.12, 1.0), 0.0, 0.60)
M_KEYS = mat("keys", (0.95, 0.92, 0.85, 1.0), 0.0, 0.40)

# Taj Mahal
M_TAJ_MARBLE = mat("taj", (1.0, 0.95, 0.90, 1.0), 0.0, 0.30, emission=(0.95,0.92,0.88), emission_strength=1.2)
M_TAJ_DOME = mat("taj_d", (0.98, 0.95, 0.90, 1.0), 0.0, 0.30, emission=(0.92,0.90,0.85), emission_strength=1.0)
M_TAJ_GOLD = mat("taj_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.92,0.75,0.28), emission_strength=1.2)

# Mandala glow
M_MANDALA = mat("mand", (1.0, 0.55, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.20), emission_strength=2.5)
M_MANDALA_INNER = mat("mand_i", (0.95, 0.30, 0.50, 1.0), 0.0, 0.20, emission=(0.95,0.30,0.50), emission_strength=3.0)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (20, 50, 30))
smooth_sphere("sun", r=5.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=5.0 + (i+1)*1.7, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

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

# ============ TAJ MAHAL background (signature) ============
taj_e = empty("taj", loc=(0, 38, 0))
# Massive marble base platform
beveled_cube("taj_base", (24, 10, 1.5), bevel_offset=0.10, loc=(0, 0, 0.75),
             parent=taj_e, mat_=M_TAJ_MARBLE)
# Main building base
beveled_cube("taj_main_b", (14, 7, 6), bevel_offset=0.08, loc=(0, 0, 4.5),
             parent=taj_e, mat_=M_TAJ_MARBLE)
# 4 small domes corners (signature chattris)
for x in (-1, 1):
    for y in (-1, 1):
        smooth_sphere(f"taj_dome_s{x}{y}", r=1.0, loc=(x*5, y*2.5, 8.5),
                      parent=taj_e, mat_=M_TAJ_DOME, scale=(1, 1, 1.3))
        # Top spike
        smooth_cone(f"taj_dome_sp{x}{y}", r1=0.15, r2=0.02, depth=1.0, segs=12,
                    loc=(x*5, y*2.5, 9.5), parent=taj_e, mat_=M_TAJ_GOLD)
# MAIN ONION DOME (signature massive)
smooth_sphere("taj_main_dome", r=4.5, segs=28, rings=18, loc=(0, 0, 9.5),
              parent=taj_e, mat_=M_TAJ_DOME, scale=(1, 1, 1.15))
# Dome top spire
smooth_cone("taj_main_sp", r1=0.50, r2=0.05, depth=3.0, segs=14,
            loc=(0, 0, 14), parent=taj_e, mat_=M_TAJ_GOLD)
smooth_sphere("taj_main_orb", r=0.30, loc=(0, 0, 16), parent=taj_e, mat_=M_TAJ_GOLD)
# 4 MINARETS corners (signature)
for x in (-1, 1):
    for y in (-1, 1):
        m_e = empty(f"taj_min_{x}{y}", (x*12, y*5, 0), parent=taj_e)
        # Tall tower
        for s in range(6):
            cyl(f"taj_min_s{x}{y}_{s}", r=0.45 - s*0.04, depth=1.5, segs=14,
                loc=(0, 0, s*1.5 + 0.75), parent=m_e, mat_=M_TAJ_MARBLE)
        # Balcony
        cyl(f"taj_min_b{x}{y}", r=0.55, depth=0.20, segs=18,
            loc=(0, 0, 9.5), parent=m_e, mat_=M_TAJ_MARBLE)
        # Top dome
        smooth_sphere(f"taj_min_d{x}{y}", r=0.50, loc=(0, 0, 10.0),
                      parent=m_e, mat_=M_TAJ_DOME, scale=(1, 1, 1.1))
        # Spike
        smooth_cone(f"taj_min_sp{x}{y}", r1=0.10, r2=0.02, depth=0.6, segs=10,
                    loc=(0, 0, 10.8), parent=m_e, mat_=M_TAJ_GOLD)
# Main arch entrance
beveled_cube("taj_arch", (3, 0.5, 4), bevel_offset=0.10, loc=(0, -3.55, 3.5),
             parent=taj_e, mat_=M_TEMPLE_RED)

# ============ ONE clean temple ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)
# Stone tiles
for i in range(80):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 40)
    smooth_sphere(f"tile{i}", r=random.uniform(0.30, 0.50), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_STONE_TILE if i % 2 == 0 else M_GROUND,
                  scale=(1.4, 1.2, 0.15))

# Central mandala (signature)
mandala_e = empty("mandala", (0, 0, 0))
# 8 concentric rings
for ring in range(5):
    rad = 1.5 + ring * 1.0
    for pt in range(int(8 + ring*4)):
        pa = (pt / int(8 + ring*4)) * math.pi * 2
        col = [M_MANDALA, M_MANDALA_INNER, M_HOLI_YELLOW, M_HOLI_PINK, M_HOLI_GREEN][ring]
        smooth_sphere(f"mand_r{ring}_{pt}", r=0.10,
                      loc=(rad*math.cos(pa), rad*math.sin(pa), 0.08),
                      parent=mandala_e, mat_=col, scale=(1, 1, 0.4))
# Center lotus
for pet in range(8):
    pa = (pet / 8.0) * math.pi * 2
    smooth_sphere(f"mand_lot{pet}", r=0.20, loc=(0.30*math.cos(pa), 0.30*math.sin(pa), 0.10),
                  parent=mandala_e, mat_=M_MANDALA_INNER, scale=(1, 1, 0.5))
smooth_sphere("mand_center", r=0.15, loc=(0, 0, 0.15), parent=mandala_e, mat_=M_HOLI_YELLOW)

# ============ HINDU TEMPLE (signature) ============
temple_e = empty("temple", loc=(15, 8, 0))
# Base platform
beveled_cube("t_base", (5, 5, 1.0), bevel_offset=0.06, loc=(0, 0, 0.5),
             parent=temple_e, mat_=M_TEMPLE_STONE)
# Main shrine
beveled_cube("t_main", (4, 4, 3), bevel_offset=0.06, loc=(0, 0, 2.5),
             parent=temple_e, mat_=M_TEMPLE_RED)
# Stepped pyramid roof (signature shikhara)
for tier in range(8):
    tier_w = 3.5 - tier * 0.35
    tier_h = 0.40
    tier_z = 4 + tier * tier_h
    beveled_cube(f"t_tier{tier}", (tier_w, tier_w, tier_h), bevel_offset=0.05,
                 loc=(0, 0, tier_z), parent=temple_e, mat_=M_TEMPLE_RED if tier % 2 == 0 else M_TEMPLE_STONE)
# Crown finial
smooth_sphere("t_crown", r=0.30, loc=(0, 0, 7.4), parent=temple_e, mat_=M_TEMPLE_GOLD)
smooth_cone("t_spire", r1=0.20, r2=0.02, depth=1.0, segs=14,
            loc=(0, 0, 8.0), parent=temple_e, mat_=M_TEMPLE_GOLD)
# Entrance with arch
beveled_cube("t_door", (1.0, 0.30, 2.2), bevel_offset=0.05, loc=(0, -2.05, 1.1),
             parent=temple_e, mat_=M_TEMPLE_GOLD)
# Decorative carvings on walls
for ci in range(8):
    ca = (ci / 8.0) * math.pi * 2
    smooth_sphere(f"t_carv{ci}", r=0.18, loc=(2.05*math.cos(ca), 2.05*math.sin(ca), 2.0),
                  parent=temple_e, mat_=M_TEMPLE_GOLD, scale=(0.3, 1, 1))

# ============ GANESH STATUE (signature elephant god) ============
ganesh_e = empty("ganesh", loc=(-15, 8, 0))
# Pedestal
beveled_cube("g_ped", (3, 3, 1.5), bevel_offset=0.08, loc=(0, 0, 0.75),
             parent=ganesh_e, mat_=M_TEMPLE_GOLD)
# Sitting body
smooth_sphere("g_body", r=1.0, segs=22, rings=14, loc=(0, 0, 2.5),
              parent=ganesh_e, mat_=M_GANESH_GOLD, scale=(1, 0.9, 1.1))
# Elephant head (signature)
head_e = empty("g_he", (0, -0.10, 3.6), parent=ganesh_e)
smooth_sphere("g_head", r=0.80, segs=22, rings=14, loc=(0, 0, 0),
              parent=head_e, mat_=M_GANESH_GOLD, scale=(1.1, 1, 1.1))
# Trunk (signature)
trunk_e = empty("g_trunk_e", (0, -0.50, -0.15), parent=head_e)
for ti in range(6):
    sk_x = math.sin(ti * 0.4) * 0.10
    cyl(f"g_trunk{ti}", r=0.20 - ti*0.02, depth=0.20, segs=12,
        loc=(sk_x, 0, -ti*0.18), parent=trunk_e, mat_=M_GANESH_GOLD)
# Trunk tip
smooth_sphere("g_trunk_tip", r=0.10, loc=(math.sin(6*0.4)*0.10, 0, -1.10),
              parent=trunk_e, mat_=M_GANESH_GOLD)
# Large ears (signature)
for side in (-1, 1):
    ear = smooth_sphere(f"g_ear{side}", r=0.55,
                        loc=(side*0.85, 0.10, 0.1), parent=head_e, mat_=M_GANESH_GOLD,
                        scale=(0.3, 1.2, 1.4))
# Eyes
for side in (-1, 1):
    smooth_sphere(f"g_eye{side}", r=0.06,
                  loc=(side*0.20, -0.65, 0.15), parent=head_e, mat_=M_GANESH_RED)
# Crown (signature)
cyl("g_crown_b", r=0.45, depth=0.20, segs=18, loc=(0, 0, 0.65),
    parent=head_e, mat_=M_GANESH_GOLD)
for ci in range(8):
    ca = (ci / 8.0) * math.pi * 2
    smooth_cone(f"g_crown_p{ci}", r1=0.10, r2=0.02, depth=0.40, segs=10,
                loc=(0.40*math.cos(ca), 0.40*math.sin(ca), 0.85), parent=head_e,
                mat_=M_GANESH_RED if ci % 2 == 0 else M_GANESH_GOLD)
# Tilak on forehead (signature red mark)
smooth_sphere("g_tilak", r=0.08, loc=(0, -0.75, 0.40),
              parent=head_e, mat_=M_GANESH_RED)
# 4 arms (signature)
for arm_idx in range(4):
    side = -1 if arm_idx < 2 else 1
    arm_pos = (arm_idx % 2) * 0.5
    sh = empty(f"g_sh{arm_idx}", (side*0.85, 0, 3.0), parent=ganesh_e)
    sh.rotation_euler = (math.radians(-50 + arm_pos*40), 0, math.radians(side*-50))
    cyl(f"g_arm{arm_idx}", r=0.13, depth=0.50, segs=12,
        loc=(0, 0, -0.25), parent=sh, mat_=M_GANESH_GOLD)
    cyl(f"g_fa{arm_idx}", r=0.11, depth=0.45, segs=10,
        loc=(0, 0, -0.70), parent=sh, mat_=M_GANESH_GOLD)
    smooth_sphere(f"g_hand{arm_idx}", r=0.12, loc=(0, 0, -0.95),
                  parent=sh, mat_=M_GANESH_GOLD)

# ============ SHIVA STATUE ============
shiva_e = empty("shiva", loc=(15, -8, 0))
# Pedestal
beveled_cube("s_ped", (2.5, 2.5, 1), bevel_offset=0.06, loc=(0, 0, 0.5),
             parent=shiva_e, mat_=M_TEMPLE_STONE)
# Sitting body (blue signature)
smooth_cone("s_legs", r1=0.70, r2=0.55, depth=0.60, segs=14,
            loc=(0, 0, 1.30), parent=shiva_e, mat_=M_SHIVA_BLUE)
# Torso bare
beveled_cube("s_torso", (0.55, 0.30, 0.85), bevel_offset=0.06, loc=(0, 0, 2.1),
             parent=shiva_e, mat_=M_SHIVA_BLUE)
# Necklaces
for ni in range(3):
    cyl(f"s_neck_l{ni}", r=0.20 + ni*0.05, depth=0.05, segs=18,
        loc=(0, 0, 2.55 - ni*0.10), parent=shiva_e, mat_=M_SAREE_GOLD_TRIM)
# Head
head_s_e = empty("s_he", (0, 0, 2.85), parent=shiva_e)
smooth_sphere("s_head", r=0.25, segs=20, rings=14, loc=(0, 0, 0),
              parent=head_s_e, mat_=M_SHIVA_BLUE)
# Long hair tied (jata signature)
smooth_sphere("s_hair", r=0.35, loc=(0, 0.05, 0.20),
              parent=head_s_e, mat_=M_HAIR_BLACK_I, scale=(1.1, 1, 1.5))
# Third eye (signature)
smooth_sphere("s_third_eye", r=0.05, loc=(0, -0.22, 0.10),
              parent=head_s_e, mat_=M_HOLI_RED)
# Crescent moon in hair
beveled_cube("s_moon", (0.10, 0.04, 0.04), loc=(0, -0.20, 0.40),
             parent=head_s_e, mat_=M_SHIVA_WHITE)
# Snake around neck (signature)
for sni in range(8):
    sa = (sni / 8.0) * math.pi * 2
    smooth_sphere(f"s_snake{sni}", r=0.06,
                  loc=(0.25*math.cos(sa), 0.25*math.sin(sa), 2.45),
                  parent=shiva_e, mat_=M_HOLI_GREEN)
# 4 arms (Shiva has 4)
shiva_arms = []
for arm_idx in range(4):
    side = -1 if arm_idx < 2 else 1
    arm_z_off = (arm_idx % 2) * 0.3
    sh = empty(f"s_sh{arm_idx}", (side*0.30, 0, 2.40 + arm_z_off), parent=shiva_e)
    sh.rotation_euler = (math.radians(-130 if arm_z_off == 0 else -90), 0, math.radians(side*-50))
    cyl(f"s_arm{arm_idx}", r=0.07, depth=0.35, segs=10,
        loc=(0, 0, -0.18), parent=sh, mat_=M_SHIVA_BLUE)
    cyl(f"s_fa{arm_idx}", r=0.06, depth=0.32, segs=10,
        loc=(0, 0, -0.50), parent=sh, mat_=M_SHIVA_BLUE)
    smooth_sphere(f"s_hand{arm_idx}", r=0.07, loc=(0, 0, -0.68),
                  parent=sh, mat_=M_SHIVA_BLUE)
    shiva_arms.append(sh)
# Trident (signature trishula)
trident_e = empty("s_tri", (-0.7, -0.3, 3.5), parent=shiva_e)
trident_e.rotation_euler = (math.radians(-20), 0, 0)
cyl("s_tri_shaft", r=0.03, depth=2.0, segs=8, loc=(0, 0, 0),
    parent=trident_e, mat_=M_TEMPLE_GOLD)
# 3 prongs
for pr in range(3):
    pa = (pr - 1) * 0.20
    smooth_cone(f"s_tri_pr{pr}", r1=0.04, r2=0.005, depth=0.30, segs=8,
                loc=(math.sin(pa)*0.08, 0, 1.15), parent=trident_e, mat_=M_TEMPLE_GOLD).rotation_euler = (pa, 0, 0)

# ============ 8 HOLI DANCERS in white sari/kurta + colors ============
def make_holi_dancer(name, loc, is_woman=True, color_stains=None, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    if color_stains is None:
        color_stains = random.sample([M_HOLI_PINK, M_HOLI_MAGENTA, M_HOLI_YELLOW, M_HOLI_BLUE,
                                       M_HOLI_GREEN, M_HOLI_ORANGE, M_HOLI_PURPLE, M_HOLI_CYAN], 4)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_hip{side_idx}", (side*0.13*scale, 0, 0.85*scale), parent=base)
        if is_woman:
            # Hidden under sari
            cyl(f"{name}_legs", r=0.30*scale, depth=1.0*scale, segs=14,
                loc=(0, 0, 0.45*scale), parent=base, mat_=M_SAREE_WHITE)
            break
        else:
            # Dhoti pants
            cyl(f"{name}_thigh{side_idx}", r=0.11*scale, depth=0.50*scale, segs=12,
                loc=(0, 0, -0.25*scale), parent=hip, mat_=M_DHOTI_WHITE)
            cyl(f"{name}_calf{side_idx}", r=0.09*scale, depth=0.45*scale, segs=12,
                loc=(0, 0, -0.72*scale), parent=hip, mat_=M_SKIN_INDIAN)
            # Bare feet
            beveled_cube(f"{name}_foot{side_idx}", (0.14*scale, 0.25*scale, 0.06*scale), bevel_offset=0.02,
                         loc=(0, 0.04*scale, -0.95*scale), parent=hip, mat_=M_SKIN_INDIAN)
    # Sari/Kurta torso
    if is_woman:
        # SARI (signature)
        smooth_cone(f"{name}_sari", r1=0.45*scale, r2=0.32*scale, depth=1.4*scale, segs=18,
                    loc=(0, 0, 0.85*scale), parent=base, mat_=M_SAREE_WHITE)
        # Gold border on sari
        cyl(f"{name}_sari_t", r=0.46*scale, depth=0.10*scale, segs=18,
            loc=(0, 0, 0.20*scale), parent=base, mat_=M_SAREE_GOLD_TRIM)
        # Choli top
        beveled_cube(f"{name}_choli", (0.40*scale, 0.22*scale, 0.30*scale), bevel_offset=0.04,
                     loc=(0, 0, 1.75*scale), parent=base, mat_=M_SAREE_WHITE)
        # Pallu (drape over shoulder signature)
        drape = beveled_cube(f"{name}_pallu", (0.30*scale, 0.05*scale, 1.0*scale), bevel_offset=0.03,
                            loc=(-0.10*scale, -0.10*scale, 1.50*scale), parent=base, mat_=M_SAREE_WHITE)
        drape.rotation_euler = (0, math.radians(-15), 0)
        # Gold border on pallu
        beveled_cube(f"{name}_pallu_t", (0.32*scale, 0.06*scale, 0.05*scale), bevel_offset=0.01,
                     loc=(-0.10*scale, -0.10*scale, 1.0*scale), parent=base, mat_=M_SAREE_GOLD_TRIM)
    else:
        # KURTA (signature long shirt)
        smooth_cone(f"{name}_kurta", r1=0.40*scale, r2=0.32*scale, depth=0.95*scale, segs=14,
                    loc=(0, 0, 1.05*scale), parent=base, mat_=M_KURTA_WHITE)
        # Standing collar
        cyl(f"{name}_collar", r=0.22*scale, depth=0.10*scale, segs=14,
            loc=(0, 0, 1.65*scale), parent=base, mat_=M_KURTA_WHITE)
    # Color stains on body (signature Holi)
    for st in range(15):
        stx = random.uniform(-0.20, 0.20) * scale
        sty = random.uniform(-0.20, 0.20) * scale
        stz = random.uniform(0.5, 1.8) * scale
        col = color_stains[st % 4]
        smooth_sphere(f"{name}_stain{st}", r=random.uniform(0.06, 0.12) * scale,
                      loc=(stx, sty, stz), parent=base, mat_=col,
                      scale=(1, 0.3, 1))
    # Neck
    cyl(f"{name}_neck", r=0.09*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 1.95*scale), parent=base, mat_=M_SKIN_INDIAN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.13*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_INDIAN)
    # Color stains on face/hair
    for fs in range(6):
        fs_a = (fs / 6.0) * math.pi * 2
        col = color_stains[fs % 4]
        smooth_sphere(f"{name}_face_stain{fs}", r=0.07*scale,
                      loc=(0.13*scale*math.cos(fs_a), -0.08*scale, 0.13*scale*math.sin(fs_a)),
                      parent=head_e, mat_=col, scale=(1, 0.3, 1))
    # Hair black
    smooth_sphere(f"{name}_hair", r=0.20*scale, loc=(0, 0.05*scale, 0.05*scale),
                  parent=head_e, mat_=M_HAIR_BLACK_I, scale=(1, 1, 0.85))
    if is_woman:
        # Hair bun signature
        smooth_sphere(f"{name}_bun", r=0.16*scale, loc=(0, 0.25*scale, 0.0),
                      parent=head_e, mat_=M_HAIR_BLACK_I)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.20, 0.10, 0.06, 1), 0, 0.4,
                                emission=(0.30,0.15,0.10), emission_strength=1.5))
    # BINDI (signature red dot forehead)
    smooth_sphere(f"{name}_bindi", r=0.025*scale, loc=(0, -0.16*scale, 0.10*scale),
                  parent=head_e, mat_=M_HOLI_RED)
    # Necklace (women)
    if is_woman:
        for ni in range(8):
            na = (ni - 3.5) * 0.25
            smooth_sphere(f"{name}_neck_b{ni}", r=0.03*scale,
                          loc=(math.sin(na)*0.10*scale, -0.10*scale, 1.95*scale),
                          parent=base, mat_=M_SAREE_GOLD_TRIM)
    # Arms raised celebrating
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.32*scale, 0, 1.85*scale), parent=base)
        sh.rotation_euler = (math.radians(-140), 0, math.radians(side*-40))
        cyl(f"{name}_uarm{side_idx}", r=0.07*scale, depth=0.32*scale, segs=12,
            loc=(0, 0, -0.17*scale), parent=sh, mat_=M_SKIN_INDIAN)
        cyl(f"{name}_fa{side_idx}", r=0.06*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.45*scale), parent=sh, mat_=M_SKIN_INDIAN)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07*scale, loc=(0, 0, -0.62*scale),
                      parent=sh, mat_=M_SKIN_INDIAN)
        # Bangles signature
        for bi in range(3):
            cyl(f"{name}_bangle{side_idx}_{bi}", r=0.065*scale, depth=0.03*scale, segs=12,
                loc=(0, 0, -0.42*scale - bi*0.05*scale), parent=sh,
                mat_=M_SAREE_GOLD_TRIM if bi % 2 == 0 else color_stains[bi % 4])
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

dancers = []
dancer_specs = [
    ("d1", (-6, 3, 0), True, math.radians(45)),
    ("d2", (-3, 5, 0), True, math.radians(20)),
    ("d3", (0, 6, 0), False, math.radians(0)),
    ("d4", (3, 5, 0), True, math.radians(-20)),
    ("d5", (6, 3, 0), True, math.radians(-45)),
    ("d6", (-5, -2, 0), False, math.radians(70)),
    ("d7", (5, -2, 0), True, math.radians(-70)),
    ("d8", (0, -4, 0), False, math.radians(180)),
]
for spec in dancer_specs:
    name, loc, is_w, fac = spec
    d = make_holi_dancer(name, loc, is_woman=is_w, facing=fac)
    dancers.append(d)

# 6 dancing girls (smaller, scattered)
girl_specs = [
    ("g1", (-10, 2, 0), True, math.radians(45), 0.9),
    ("g2", (10, 2, 0), True, math.radians(-45), 0.9),
    ("g3", (-8, -4, 0), True, math.radians(60), 0.95),
    ("g4", (8, -4, 0), True, math.radians(-60), 0.95),
    ("g5", (-2, 8, 0), True, math.radians(180), 0.9),
    ("g6", (2, 8, 0), True, math.radians(180), 0.9),
]
for spec in girl_specs:
    name, loc, is_w, fac, sc = spec
    g = make_holi_dancer(name, loc, is_woman=is_w, facing=fac, scale=sc)
    dancers.append(g)

# Brahmane priest (signature saffron robe)
brahmane = make_holi_dancer("brahmane", (0, 0, 0), is_woman=False,
                              color_stains=[M_HOLI_RED, M_HOLI_YELLOW, M_HOLI_ORANGE, M_HOLI_GREEN],
                              facing=math.radians(0), scale=1.15)
# Override robe color to saffron
robe_obj = bpy.data.objects.get("brahmane_kurta")
if robe_obj:
    robe_obj.data.materials.clear()
    robe_obj.data.materials.append(M_ROBE_SAFFRON)
dancers.append(brahmane)

# ============ 4 MUSICIANS (tabla, sitar, harmonium, dholak) ============
def make_indian_musician(name, loc, instrument, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sitting body
    smooth_cone(f"{name}_legs", r1=0.40, r2=0.30, depth=0.50, segs=14,
                loc=(0, 0, 0.25), parent=base, mat_=M_KURTA_WHITE)
    # Torso
    beveled_cube(f"{name}_torso", (0.42, 0.22, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 0.80), parent=base, mat_=M_KURTA_WHITE)
    # Neck
    cyl(f"{name}_neck", r=0.09, depth=0.16, segs=10, loc=(0, 0, 1.15),
        parent=base, mat_=M_SKIN_INDIAN)
    head_e = empty(f"{name}_he", (0, 0, 1.33), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_INDIAN)
    smooth_sphere(f"{name}_hair", r=0.20, loc=(0, 0.04, 0.05),
                  parent=head_e, mat_=M_HAIR_BLACK_I, scale=(1, 1, 0.85))
    # Bindi
    smooth_sphere(f"{name}_bindi", r=0.025, loc=(0, -0.16, 0.10),
                  parent=head_e, mat_=M_HOLI_RED)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.14, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.20, 0.10, 0.06, 1), 0, 0.4,
                                emission=(0.30,0.15,0.10), emission_strength=1.5))
    # Color stains
    for st in range(8):
        col = random.choice([M_HOLI_PINK, M_HOLI_YELLOW, M_HOLI_GREEN, M_HOLI_BLUE])
        smooth_sphere(f"{name}_stain{st}", r=0.06,
                      loc=(random.uniform(-0.18, 0.18), random.uniform(-0.18, 0.18),
                           random.uniform(0.5, 1.4)), parent=base, mat_=col,
                      scale=(1, 0.3, 1))
    # Instrument
    inst_e = empty(f"{name}_inst_e", (0, -0.45, 0.50), parent=base)
    arms_e = []
    if instrument == "tabla":
        # 2 drums signature
        for tb_idx, tb_x in enumerate((-0.18, 0.18)):
            cyl(f"{name}_tb{tb_idx}", r=0.18, depth=0.25, segs=18,
                loc=(tb_x, 0, 0), parent=inst_e, mat_=M_TABLA_WOOD)
            cyl(f"{name}_tb_skin{tb_idx}", r=0.18, depth=0.02, segs=18,
                loc=(tb_x, 0, 0.13), parent=inst_e, mat_=M_TABLA_SKIN)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.27, 0, 1.03), parent=base)
            sh.rotation_euler = (math.radians(-90), 0, math.radians(side*-25))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_KURTA_WHITE)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_INDIAN)
            arms_e.append(sh)
    elif instrument == "sitar":
        # Long neck stringed (signature)
        smooth_sphere(f"{name}_sit_body", r=0.30, segs=20, rings=14,
                      loc=(0, 0, 0), parent=inst_e, mat_=M_SITAR_BODY, scale=(1, 0.5, 1.3))
        beveled_cube(f"{name}_sit_neck", (0.06, 0.06, 1.5), bevel_offset=0.02,
                     loc=(0, -0.10, 0.95), parent=inst_e, mat_=M_SITAR_BODY)
        # Strings + frets
        for st in range(7):
            cyl(f"{name}_sit_str{st}", r=0.005, depth=2.0, segs=4,
                loc=((st-3)*0.012, -0.16, 0.4), parent=inst_e, mat_=M_TEMPLE_GOLD)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.27, 0, 1.03), parent=base)
            sh.rotation_euler = (math.radians(-70 if side_idx == 0 else -100), 0, math.radians(side*-30))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_KURTA_WHITE)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_INDIAN)
            arms_e.append(sh)
    elif instrument == "harmonium":
        # Wooden box with bellows
        beveled_cube(f"{name}_harm_b", (0.50, 0.30, 0.30), bevel_offset=0.04,
                     loc=(0, 0, 0), parent=inst_e, mat_=M_HARMONIUM)
        # Keys
        for ki in range(8):
            beveled_cube(f"{name}_key{ki}", (0.05, 0.06, 0.04), bevel_offset=0.01,
                         loc=((ki - 3.5)*0.06, -0.18, 0.18), parent=inst_e, mat_=M_KEYS)
        # Bellows (back)
        for bi in range(4):
            beveled_cube(f"{name}_bel{bi}", (0.45, 0.04, 0.18),
                         loc=(0, 0.15 + bi*0.04, 0), parent=inst_e, mat_=M_HARMONIUM)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.27, 0, 1.03), parent=base)
            sh.rotation_euler = (math.radians(-100), 0, math.radians(side*-20))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_KURTA_WHITE)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_INDIAN)
            arms_e.append(sh)
    else:  # dholak (drum cylinder)
        cyl(f"{name}_dh_body", r=0.20, depth=0.60, segs=16,
            loc=(0, 0, 0), parent=inst_e, mat_=M_TABLA_WOOD).rotation_euler = (math.radians(90), 0, 0)
        for end in (-1, 1):
            cyl(f"{name}_dh_end{end}", r=0.20, depth=0.03, segs=16,
                loc=(0, end*0.32, 0), parent=inst_e, mat_=M_TABLA_SKIN).rotation_euler = (math.radians(90), 0, 0)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.27, 0, 1.03), parent=base)
            sh.rotation_euler = (math.radians(-100), 0, math.radians(side*-30))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_KURTA_WHITE)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_INDIAN)
            arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

musicians = []
mus_specs = [
    ("mus1", (-5, 11, 0), "tabla", math.radians(0)),
    ("mus2", (-2, 12, 0), "sitar", math.radians(0)),
    ("mus3", (2, 12, 0), "harmonium", math.radians(0)),
    ("mus4", (5, 11, 0), "dholak", math.radians(0)),
]
for spec in mus_specs:
    name, loc, inst, fac = spec
    m = make_indian_musician(name, loc, inst, facing=fac)
    musicians.append(m)

# ============ 4 SACRED COWS ============
def make_sacred_cow(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.55, segs=20, rings=14, loc=(0, 0, 1.10),
                  parent=base, mat_=M_COW_HOLI, scale=(1.7, 1, 1))
    # Hump
    smooth_sphere(f"{name}_hump", r=0.30, loc=(0.35, 0, 1.45),
                  parent=base, mat_=M_COW_HOLI, scale=(1.1, 1, 1.3))
    # Head
    head_e = empty(f"{name}_he", (1.10, 0, 1.30), parent=base)
    beveled_cube(f"{name}_head", (0.40, 0.22, 0.28), bevel_offset=0.04,
                 loc=(0, 0, 0), parent=head_e, mat_=M_COW_HOLI)
    smooth_cone(f"{name}_muzzle", r1=0.10, r2=0.08, depth=0.18, segs=12,
                loc=(0.18, 0, -0.04), parent=head_e,
                mat_=M_COW_HOLI).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04, loc=(0.05, side*0.13, 0.08),
                      parent=head_e, mat_=M_HAIR_BLACK_I)
    # Curved horns
    for side in (-1, 1):
        horn = smooth_cone(f"{name}_horn{side}", r1=0.04, r2=0.01, depth=0.25, segs=10,
                           loc=(-0.05, side*0.15, 0.20), parent=head_e, mat_=M_COW_HORN)
        horn.rotation_euler = (math.radians(-30), 0, math.radians(side*40))
    # Painted color stains signature
    for st in range(8):
        col = random.choice([M_HOLI_PINK, M_HOLI_YELLOW, M_HOLI_RED])
        smooth_sphere(f"{name}_stain{st}", r=0.10,
                      loc=(random.uniform(-0.6, 0.6), random.uniform(-0.4, 0.4),
                           1.10 + random.uniform(-0.2, 0.4)), parent=base, mat_=col,
                      scale=(1, 1, 0.3))
    # 4 legs
    for x_idx, x in enumerate((0.50, -0.50)):
        for y_idx, y in enumerate((-0.35, 0.35)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.08, depth=0.85, segs=10,
                loc=(x, y, 0.40), parent=base, mat_=M_COW_HOLI)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.09, depth=0.10, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_COW_HORN)
    return {"root": base, "he": head_e}

cows = []
cow_pos = [(-12, 12, 0, math.radians(45)), (12, 12, 0, math.radians(-45)),
           (-12, -10, 0, math.radians(90)), (12, -10, 0, math.radians(-90))]
for i, (cx, cy, cz, fac) in enumerate(cow_pos):
    c = make_sacred_cow(f"cow{i}", (cx, cy, cz), facing=fac)
    cows.append(c)

# ============ MONKEYS ============
def make_monkey(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.30, segs=18, rings=12, loc=(0, 0, 0.60),
                  parent=base, mat_=M_MONKEY, scale=(1.4, 1, 1))
    # Head
    head_e = empty(f"{name}_he", (0.40, 0, 0.85), parent=base)
    smooth_sphere(f"{name}_head", r=0.22, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_MONKEY)
    # Face pink (signature)
    smooth_sphere(f"{name}_face", r=0.20, loc=(0, -0.05, 0),
                  parent=head_e, mat_=M_MONKEY_FACE, scale=(1, 0.4, 1.1))
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.08, loc=(side*0.18, 0.05, 0.05),
                      parent=head_e, mat_=M_MONKEY)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.03, loc=(side*0.06, -0.14, 0.06),
                      parent=head_e, mat_=M_HAIR_BLACK_I)
    # 4 legs
    for x_idx, x in enumerate((0.20, -0.20)):
        for y_idx, y in enumerate((-0.15, 0.15)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.05, depth=0.40, segs=10,
                loc=(x, y, 0.30), parent=base, mat_=M_MONKEY)
    # Long curled tail
    tail_e = empty(f"{name}_te", (-0.35, 0, 0.60), parent=base)
    for ti in range(6):
        ta = ti * 0.5
        cyl(f"{name}_tail{ti}", r=0.04 - ti*0.003, depth=0.15, segs=8,
            loc=(math.sin(ta)*0.05, 0, ti*0.12), parent=tail_e, mat_=M_MONKEY)
    return {"root": base, "he": head_e}

monkeys = [
    make_monkey("monk1", (-9, 6, 0), math.radians(120)),
    make_monkey("monk2", (9, 6, 0), math.radians(-120)),
    make_monkey("monk3", (-7, -3, 0), math.radians(60)),
]

# ============ 2 PEACOCKS ============
def make_peacock_holi(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.28, segs=18, rings=12, loc=(0, 0, 0.55),
                  parent=base, mat_=M_PEACOCK, scale=(1.4, 1, 1.1))
    # Neck
    neck_e = empty(f"{name}_ne", (0.30, 0, 0.7), parent=base)
    for ni in range(4):
        cyl(f"{name}_neck{ni}", r=0.06, depth=0.15, segs=10,
            loc=(0, 0, ni*0.13), parent=neck_e, mat_=M_PEACOCK)
    head_e = empty(f"{name}_he", (0, 0, 0.55), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_PEACOCK)
    # Crown
    for cf in range(5):
        cfa = (cf - 2) * 0.2
        smooth_cone(f"{name}_cr{cf}", r1=0.015, r2=0.03, depth=0.15, segs=8,
                    loc=(0.02*math.sin(cfa), 0, 0.18), parent=head_e, mat_=M_PEACOCK_BLUE)
        smooth_sphere(f"{name}_cr_tip{cf}", r=0.025,
                      loc=(0.02*math.sin(cfa), 0, 0.32), parent=head_e, mat_=M_PEACOCK_GOLD)
    # Beak
    smooth_cone(f"{name}_beak", r1=0.03, r2=0.005, depth=0.10, segs=8,
                loc=(0.08, 0, -0.02), parent=head_e,
                mat_=M_TEMPLE_GOLD).rotation_euler = (0, math.radians(90), 0)
    # Tail fan
    tail_e = empty(f"{name}_te", (-0.30, 0, 0.65), parent=base)
    tail_e.rotation_euler = (math.radians(-30), 0, 0)
    for fi in range(20):
        fa = (fi - 9.5) * 0.10
        f_len = 1.8 - abs(fa) * 0.4
        f_e = empty(f"{name}_fe{fi}", (0, 0, 0), parent=tail_e)
        f_e.rotation_euler = (0, 0, fa)
        beveled_cube(f"{name}_fs{fi}", (0.04, f_len, 0.02), bevel_offset=0.01,
                     loc=(0, f_len*0.5, 0), parent=f_e, mat_=M_PEACOCK_GREEN)
        smooth_sphere(f"{name}_fe_o{fi}", r=0.12, loc=(0, f_len, 0),
                      parent=f_e, mat_=M_PEACOCK_BLUE, scale=(0.7, 1, 0.2))
        smooth_sphere(f"{name}_fe_m{fi}", r=0.08, loc=(0, f_len, 0.03),
                      parent=f_e, mat_=M_PEACOCK_GOLD, scale=(0.7, 1, 0.2))
    return {"root": base, "tail": tail_e, "he": head_e}

peacocks = [
    make_peacock_holi("peacock1", (-11, -7, 0), math.radians(45)),
    make_peacock_holi("peacock2", (11, -7, 0), math.radians(-45)),
]

# ============ MARIGOLD GARLANDS (signature Indian festival) ============
for gi in range(12):
    a = (gi / 12.0) * math.pi * 2
    rad = 18
    gx = rad * math.cos(a)
    gy = rad * math.sin(a)
    g_e = empty(f"garland{gi}", (gx, gy, 6))
    # Hanging chain of marigolds
    for fi in range(10):
        smooth_sphere(f"gar_f{gi}_{fi}", r=0.10,
                      loc=(0, 0, -fi*0.30), parent=g_e,
                      mat_=M_MARIGOLD_ORANGE if fi % 2 == 0 else M_MARIGOLD_YELLOW)

# ============================================================
# ⭐ 1000 COLOR POWDER PARTICLES (MILESTONE DOUBLE QUANTITY)
# ============================================================
holi_colors = [M_HOLI_PINK, M_HOLI_MAGENTA, M_HOLI_RED, M_HOLI_YELLOW, M_HOLI_GREEN,
               M_HOLI_BLUE, M_HOLI_PURPLE, M_HOLI_ORANGE, M_HOLI_CYAN, M_HOLI_LIME]
color_powder = []
for i in range(1000):
    px = random.uniform(-25, 25)
    py = random.uniform(-25, 25)
    pz = random.uniform(0.5, 15)
    col = holi_colors[i % 10]
    p_obj = smooth_sphere(f"hp{i}", r=random.uniform(0.06, 0.12), segs=8, rings=6,
                          loc=(px, py, pz), mat_=col)
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_amp_x"] = random.uniform(1.5, 3.5)
    p_obj["_amp_y"] = random.uniform(1.5, 3.5)
    p_obj["_amp_z"] = random.uniform(0.6, 1.8)
    p_obj["_speed"] = random.uniform(0.6, 1.5)
    color_powder.append(p_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Dancers celebrate
for d in dancers:
    phase = d["root"]["_phase"]
    base_z = d["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        d["root"].location.z = base_z + abs(math.sin(t * 3.0 + phase)) * 0.10
        d["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5),
                                     math.cos(t * 1.2 + phase) * math.radians(4),
                                     d["root"].rotation_euler.z + math.sin(t * 1.0 + phase) * math.radians(10))
        d["root"].keyframe_insert("location", frame=f)
        d["root"].keyframe_insert("rotation_euler", frame=f)
        for ai, arm in enumerate(d["arms"]):
            wave = math.sin(t * 2.5 + phase + ai * math.pi) * math.radians(20)
            arm.rotation_euler = (math.radians(-140) + wave, 0, math.radians((-1 if ai==0 else 1)*-40))
            arm.keyframe_insert("rotation_euler", frame=f)
        d["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                    math.sin(t * 1.2 + phase) * math.radians(15))
        d["he"].keyframe_insert("rotation_euler", frame=f)

# Musicians play fast tempo
for m in musicians:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        for ai, arm in enumerate(m["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 6.0 + phase + ai * math.pi) * math.radians(18)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0,
                                    math.sin(t * 1.5 + phase) * math.radians(15))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Cows graze
for c in cows:
    phase = hash(c["root"].name) % 100 * 0.05
    base_z = c["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        c["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.04
        c["root"].keyframe_insert("location", frame=f)
        c["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(12), 0,
                                    math.sin(t * 0.5 + phase) * math.radians(15))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Monkeys jump
for mk in monkeys:
    phase = hash(mk["root"].name) % 100 * 0.05
    base_z = mk["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        mk["root"].location.z = base_z + abs(math.sin(t * 3.0 + phase)) * 0.20
        mk["root"].keyframe_insert("location", frame=f)
        mk["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(15), 0,
                                     math.sin(t * 1.5 + phase) * math.radians(25))
        mk["he"].keyframe_insert("rotation_euler", frame=f)

# Peacocks tail fan
for p in peacocks:
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        p["tail"].rotation_euler = (math.radians(-30) + math.sin(t * 1.0) * math.radians(10), 0,
                                      math.sin(t * 1.5) * math.radians(25))
        p["tail"].keyframe_insert("rotation_euler", frame=f)
        p["he"].rotation_euler = (0, 0, math.sin(t * 1.0) * math.radians(35))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Mandala pulse
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 1.5) * 0.10
    mandala_e.scale = (s, s, s)
    mandala_e.keyframe_insert("scale", frame=f)

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
# ⭐⭐⭐ 1000 COLOR POWDER EXPLODE/VORTEX (MILESTONE DOUBLE - signature Holi)
# ============================================================
for p in color_powder:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    ax, ay, az = p["_amp_x"], p["_amp_y"], p["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # EXPLODE pattern - radiate out from center + drift up
        x = bx + ax * math.sin(t * speed + phase) + math.sin(t * speed * 2) * 0.5
        y = by + ay * math.cos(t * speed * 0.9 + phase) + math.cos(t * speed * 2) * 0.5
        z = bz + az * math.sin(t * speed * 1.3 + phase) + math.sin(t * 0.6) * 1.0
        p.location = (x, y, max(0.2, z))
        sc = 1 + math.sin(t * 4.0 + phase) * 0.4
        p.scale = (sc, sc, sc)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_holi_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_indian_holi_festival_colors] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_indian_holi_festival_colors] 🎉 MILESTONE 100e: ONE temple ground + Taj Mahal + Hindu temple + Ganesh + Shiva + 14 Holi dancers + brahmane + 4 musicians + 4 sacred cows + 3 monkeys + 2 peacocks + 12 marigold garlands + mandala + 1000 COLOR POWDER (DOUBLE)")
print("⭐ FIXES: 1 ground + 1000 color powder explode vortex (signature Holi MILESTONE 100e mandatory) ⭐")
