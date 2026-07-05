"""
proc_persian_palace_1001_nights.py — 218e procédural AuroraIA (82e qualité)
1001 nights: ONE mosaic ground + 800 rose petals + Persian dome + 4 minarets + flying carpet + 6 musicians + 8 dancers + camels + peacocks + magic lamp + djinn
FIXES : 1 ground propre + 800 rose petals thématique (signature 1001 nuits)
"""
import bpy, bmesh, math, random, os

random.seed(0x1001218)

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

# Materials Persian night palette
M_SKY = mat("sky", (0.10, 0.08, 0.30, 1.0), 0.0, 0.7, emission=(0.10,0.08,0.30), emission_strength=1.5)
M_MOON = mat("moon", (0.98, 0.95, 0.85, 1.0), 0.0, 0.20, emission=(0.98,0.95,0.85), emission_strength=14.0)
M_STAR = mat("star", (1.0, 1.0, 0.95, 1.0), 0.0, 0.20, emission=(1.0,1.0,0.95), emission_strength=12.0)
M_CLOUD_NIGHT = mat("cloud", (0.25, 0.20, 0.40, 1.0), 0.0, 0.65, emission=(0.20,0.18,0.35), emission_strength=0.6, alpha=0.65)

# Ground mosaic
M_GROUND = mat("ground", (0.55, 0.42, 0.25, 1.0), 0.0, 0.75, emission=(0.50,0.38,0.22), emission_strength=0.4)
M_MOSAIC_TURQ = mat("mosaic_t", (0.20, 0.65, 0.75, 1.0), 0.3, 0.30, emission=(0.20,0.65,0.75), emission_strength=1.3)
M_MOSAIC_BLUE = mat("mosaic_b", (0.20, 0.35, 0.85, 1.0), 0.3, 0.30, emission=(0.20,0.35,0.85), emission_strength=1.3)
M_MOSAIC_GOLD = mat("mosaic_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.90,0.72,0.28), emission_strength=1.0)
M_MOSAIC_RED = mat("mosaic_r", (0.85, 0.18, 0.20, 1.0), 0.3, 0.35, emission=(0.78,0.18,0.18), emission_strength=1.2)
M_MOSAIC_WHITE = mat("mosaic_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.30, emission=(0.88,0.85,0.82), emission_strength=0.8)
M_SAND = mat("sand", (0.78, 0.62, 0.38, 1.0), 0.0, 0.80, emission=(0.72,0.58,0.35), emission_strength=0.4)

# Palace dome turquoise
M_DOME_TURQ = mat("dome_t", (0.18, 0.65, 0.72, 1.0), 0.5, 0.25, emission=(0.18,0.65,0.72), emission_strength=2.0)
M_DOME_GOLD = mat("dome_g", (0.95, 0.82, 0.30, 1.0), 0.95, 0.18, emission=(0.92,0.78,0.28), emission_strength=1.5)
M_WALL_STONE = mat("wall", (0.85, 0.75, 0.55, 1.0), 0.0, 0.70, emission=(0.78,0.68,0.50), emission_strength=0.5)
M_WALL_BLUE = mat("wall_b", (0.30, 0.45, 0.78, 1.0), 0.2, 0.45, emission=(0.30,0.45,0.78), emission_strength=1.0)
M_ARCH = mat("arch", (0.85, 0.65, 0.40, 1.0), 0.3, 0.40, emission=(0.80,0.60,0.38), emission_strength=0.6)

# Water fountain
M_WATER = mat("water", (0.55, 0.85, 0.95, 0.80), 0.4, 0.10, emission=(0.55,0.85,0.95), emission_strength=2.0, alpha=0.80)
M_WATER_FOAM = mat("foam", (1.0, 1.0, 1.0, 1.0), 0.0, 0.10, emission=(0.95,0.95,0.98), emission_strength=2.5)
M_FOUNTAIN_STONE = mat("f_stone", (0.92, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.60), emission_strength=0.5)

# Flying carpet (colorful Persian pattern)
M_CARPET_BG = mat("carpet_b", (0.75, 0.18, 0.20, 1.0), 0.0, 0.65, emission=(0.70,0.18,0.18), emission_strength=0.9)
M_CARPET_GOLD_PAT = mat("carpet_g", (0.95, 0.78, 0.30, 1.0), 0.7, 0.25, emission=(0.90,0.72,0.28), emission_strength=1.2)
M_CARPET_BLUE_PAT = mat("carpet_p", (0.20, 0.55, 0.85, 1.0), 0.0, 0.50, emission=(0.20,0.55,0.85), emission_strength=0.9)
M_CARPET_FRINGE = mat("carpet_f", (0.95, 0.78, 0.30, 1.0), 0.0, 0.55, emission=(0.90,0.72,0.28), emission_strength=0.7)

# Skin tones + clothing
M_SKIN_PERSIAN = mat("skin", (0.85, 0.65, 0.48, 1.0), 0.0, 0.55, emission=(0.78,0.60,0.45), emission_strength=0.4)
M_VEIL_PINK = mat("veil_p", (0.95, 0.55, 0.85, 1.0), 0.0, 0.40, emission=(0.90,0.55,0.85), emission_strength=1.1, alpha=0.85)
M_VEIL_PURPLE = mat("veil_pu", (0.55, 0.30, 0.85, 1.0), 0.0, 0.40, emission=(0.50,0.28,0.78), emission_strength=1.0, alpha=0.85)
M_VEIL_GOLD = mat("veil_g", (1.0, 0.78, 0.30, 1.0), 0.5, 0.30, emission=(0.95,0.72,0.28), emission_strength=1.3, alpha=0.85)
M_VEIL_RED = mat("veil_r", (0.85, 0.18, 0.20, 1.0), 0.0, 0.40, emission=(0.78,0.18,0.18), emission_strength=1.1, alpha=0.85)
M_VEIL_BLUE = mat("veil_b", (0.20, 0.50, 0.85, 1.0), 0.0, 0.40, emission=(0.18,0.45,0.78), emission_strength=1.0, alpha=0.85)
M_HAIR_BLACK = mat("hair", (0.05, 0.04, 0.04, 1.0), 0.0, 0.85)
M_TURBAN_RED = mat("turban_r", (0.78, 0.18, 0.20, 1.0), 0.0, 0.65, emission=(0.72,0.18,0.18), emission_strength=0.7)
M_TURBAN_BLUE = mat("turban_b", (0.20, 0.45, 0.78, 1.0), 0.0, 0.65, emission=(0.18,0.42,0.72), emission_strength=0.7)
M_TURBAN_GOLD = mat("turban_g", (0.95, 0.78, 0.30, 1.0), 0.5, 0.40, emission=(0.90,0.72,0.28), emission_strength=0.8)
M_VEST = mat("vest", (0.45, 0.15, 0.45, 1.0), 0.0, 0.60, emission=(0.40,0.15,0.40), emission_strength=0.5)
M_PANT_WHITE = mat("pant_w", (0.92, 0.88, 0.80, 1.0), 0.0, 0.65, emission=(0.85,0.82,0.75), emission_strength=0.5)

# Camels
M_CAMEL = mat("camel", (0.78, 0.62, 0.38, 1.0), 0.0, 0.75, emission=(0.72,0.58,0.35), emission_strength=0.4)
M_CAMEL_DARK = mat("camel_d", (0.55, 0.42, 0.25, 1.0), 0.0, 0.75)
M_CAMEL_SADDLE = mat("camel_sd", (0.85, 0.30, 0.20, 1.0), 0.0, 0.55, emission=(0.78,0.30,0.20), emission_strength=0.6)

# Peacock
M_PEACOCK_BODY = mat("peacock_b", (0.10, 0.45, 0.55, 1.0), 0.5, 0.35, emission=(0.10,0.45,0.55), emission_strength=1.5)
M_PEACOCK_BLUE = mat("peacock_p_b", (0.10, 0.30, 0.85, 1.0), 0.6, 0.25, emission=(0.10,0.30,0.85), emission_strength=2.5)
M_PEACOCK_GREEN = mat("peacock_p_g", (0.15, 0.65, 0.30, 1.0), 0.5, 0.30, emission=(0.15,0.65,0.30), emission_strength=2.0)
M_PEACOCK_GOLD = mat("peacock_p_y", (0.95, 0.78, 0.30, 1.0), 0.8, 0.20, emission=(0.95,0.78,0.30), emission_strength=2.2)

# Magic lamp + djinn
M_LAMP_BRASS = mat("lamp", (0.85, 0.65, 0.25, 1.0), 0.95, 0.15, emission=(0.85,0.65,0.25), emission_strength=1.0)
M_DJINN_SMOKE = mat("djinn_s", (0.20, 0.55, 0.95, 1.0), 0.0, 0.10, emission=(0.20,0.55,0.95), emission_strength=4.0, alpha=0.65)
M_DJINN_BODY = mat("djinn_b", (0.30, 0.65, 0.95, 1.0), 0.4, 0.25, emission=(0.30,0.65,0.95), emission_strength=3.0, alpha=0.85)
M_DJINN_EYE = mat("djinn_e", (1.0, 0.95, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.30), emission_strength=12.0)

# Roses petals
M_ROSE_PINK = mat("rose_p", (1.0, 0.45, 0.65, 1.0), 0.0, 0.45, emission=(1.0,0.45,0.65), emission_strength=2.2)
M_ROSE_RED = mat("rose_r", (0.95, 0.18, 0.25, 1.0), 0.0, 0.45, emission=(0.90,0.18,0.22), emission_strength=2.0)
M_ROSE_WHITE = mat("rose_w", (1.0, 0.92, 0.92, 1.0), 0.0, 0.45, emission=(1.0,0.88,0.88), emission_strength=1.8)

# Lanterns
M_LANTERN = mat("lantern", (1.0, 0.65, 0.25, 1.0), 0.0, 0.20, emission=(1.0,0.65,0.25), emission_strength=18.0)
M_LANTERN_CAGE = mat("lantern_c", (0.85, 0.65, 0.30, 1.0), 0.85, 0.25, emission=(0.85,0.65,0.30), emission_strength=0.8)

# Instruments
M_OUD = mat("oud", (0.55, 0.30, 0.15, 1.0), 0.0, 0.55, emission=(0.50,0.28,0.13), emission_strength=0.5)
M_DRUM = mat("drum", (0.65, 0.32, 0.18, 1.0), 0.0, 0.55, emission=(0.60,0.30,0.18), emission_strength=0.5)
M_DRUM_SKIN = mat("drum_s", (0.92, 0.85, 0.75, 1.0), 0.0, 0.55, emission=(0.85,0.80,0.72), emission_strength=0.5)

# ============ SKY + MOON + STARS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)

# Crescent moon (signature 1001 nights)
moon_e = empty("moon_e", (-30, 50, 35))
smooth_sphere("moon_full", r=4.0, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)
# Dark cover to make crescent
smooth_sphere("moon_cover", r=4.0, loc=(2.0, -1.5, 0), parent=moon_e, mat_=M_SKY)
for i in range(3):
    smooth_sphere(f"moon_halo{i}", r=4.0 + (i+1)*1.2, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)

# 150 stars
for i in range(150):
    a = random.uniform(0, math.pi*2)
    phi = random.uniform(math.pi/6, math.pi/2.2)
    r_star = 110
    sx = r_star * math.cos(phi) * math.cos(a)
    sy = r_star * math.cos(phi) * math.sin(a)
    sz = r_star * math.sin(phi) * 0.4
    smooth_sphere(f"star{i}", r=random.uniform(0.20, 0.45), segs=10, rings=8,
                  loc=(sx, sy, sz), mat_=M_STAR)

# Clouds drift
clouds = []
for i in range(5):
    a = (i / 5.0) * math.pi * 2
    rad = random.uniform(35, 50)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(28, 38)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD_NIGHT)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ ONE clean mosaic ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)

# Mosaic plaza centerpiece (geometric pattern)
plaza_e = empty("plaza", (0, 0, 0))
# Central circular mosaic
cyl("mosaic_center", r=10, depth=0.10, segs=32, loc=(0, 0, 0.05),
    parent=plaza_e, mat_=M_MOSAIC_TURQ)
# Concentric rings
ring_mats = [M_MOSAIC_GOLD, M_MOSAIC_BLUE, M_MOSAIC_RED, M_MOSAIC_WHITE]
for ring in range(4):
    cyl(f"mos_ring{ring}", r=8 - ring*1.5, depth=0.12, segs=32,
        loc=(0, 0, 0.06), parent=plaza_e, mat_=ring_mats[ring])
# Star pattern center (8-pointed)
for pt in range(8):
    pa = (pt / 8.0) * math.pi * 2
    star_seg = beveled_cube(f"mos_star_pt{pt}", (0.40, 2.5, 0.08), bevel_offset=0.03,
                            loc=(math.cos(pa)*1.5, math.sin(pa)*1.5, 0.08),
                            parent=plaza_e, mat_=M_MOSAIC_GOLD)
    star_seg.rotation_euler = (0, 0, pa)
# Edge tiles around plaza
for i in range(36):
    a = (i / 36.0) * math.pi * 2
    rad = 10.5
    tile = beveled_cube(f"mos_edge{i}", (0.50, 0.50, 0.10), bevel_offset=0.02,
                        loc=(rad*math.cos(a), rad*math.sin(a), 0.06),
                        parent=plaza_e,
                        mat_=M_MOSAIC_BLUE if i % 3 == 0 else (M_MOSAIC_GOLD if i % 3 == 1 else M_MOSAIC_RED))

# Sand dunes (organic 3D variations around plaza)
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(20, 38)
    smooth_sphere(f"dune{i}", r=random.uniform(1.0, 2.2),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.40),
                  mat_=M_SAND, scale=(2.0, 1.6, 0.30))

# ============ MAIN PALACE WITH DOME ============
palace_e = empty("palace", loc=(0, 18, 0))
# Base platform
beveled_cube("p_base", (12, 8, 1.0), bevel_offset=0.08, loc=(0, 0, 0.5),
             parent=palace_e, mat_=M_WALL_STONE)
# Main walls
beveled_cube("p_walls", (11, 7, 6), bevel_offset=0.06, loc=(0, 0, 4),
             parent=palace_e, mat_=M_WALL_STONE)
# Decorative blue band
beveled_cube("p_band", (11.2, 7.2, 0.4), bevel_offset=0.04,
             loc=(0, 0, 6.4), parent=palace_e, mat_=M_WALL_BLUE)
# Main entrance arch (signature ogive)
for arch_side in (-1, 1):
    arch_e = empty(f"arch_e{arch_side}", (arch_side*3, -3.55, 0), parent=palace_e)
    # Vertical sides
    beveled_cube(f"arch_vert{arch_side}", (0.4, 0.2, 4.0), bevel_offset=0.04,
                 loc=(0, 0, 3.0), parent=arch_e, mat_=M_ARCH)
# Curved top (ogive shape — 5 segments)
for arch_pt in range(7):
    ap = (arch_pt - 3) * 0.40
    ah = math.sqrt(max(0.1, 4.0 - ap*ap)) * 0.8
    beveled_cube(f"arch_top{arch_pt}", (0.40, 0.20, 0.30), bevel_offset=0.02,
                 loc=(ap, -3.55, 5.0 + ah*0.5), parent=palace_e, mat_=M_ARCH)

# DOME (central turquoise onion dome signature)
dome_e = empty("dome", (0, 0, 7.5), parent=palace_e)
# Dome lower bulb
smooth_sphere("dome_lower", r=4.0, segs=32, rings=20, loc=(0, 0, 0),
              parent=dome_e, mat_=M_DOME_TURQ, scale=(1, 1, 0.9))
# Dome neck
cyl("dome_neck", r=1.5, depth=1.0, segs=20, loc=(0, 0, 3.5),
    parent=dome_e, mat_=M_DOME_TURQ)
# Onion spike top (signature)
for sp in range(3):
    sp_r = 0.40 - sp*0.10
    sp_h = sp*0.6 + 4.5
    smooth_sphere(f"dome_spike{sp}", r=sp_r, loc=(0, 0, sp_h),
                  parent=dome_e, mat_=M_DOME_GOLD, scale=(1, 1, 1.2))
# Top crescent
smooth_cone("dome_crescent", r1=0.05, r2=0.20, depth=0.8, segs=14,
            loc=(0, 0, 6.5), parent=dome_e, mat_=M_DOME_GOLD)
# Gold band at dome base
cyl("dome_band", r=4.2, depth=0.30, segs=32, loc=(0, 0, -0.5),
    parent=dome_e, mat_=M_DOME_GOLD)

# 4 MINARETS at corners (signature)
minaret_corners = [(-5.5, -3.5), (5.5, -3.5), (-5.5, 3.5), (5.5, 3.5)]
for mi, (mx, my) in enumerate(minaret_corners):
    m_e = empty(f"min{mi}", (mx, my, 0), parent=palace_e)
    # Tall slender tower
    for s in range(6):
        cyl(f"min_seg{mi}_{s}", r=0.55 - s*0.04, depth=1.5, segs=14,
            loc=(0, 0, s*1.5 + 0.75), parent=m_e, mat_=M_WALL_STONE)
    # Decorative blue ring
    cyl(f"min_ring{mi}", r=0.65, depth=0.25, segs=16,
        loc=(0, 0, 7.5), parent=m_e, mat_=M_MOSAIC_TURQ)
    # Balcony
    cyl(f"min_balc{mi}", r=0.80, depth=0.20, segs=20,
        loc=(0, 0, 8.0), parent=m_e, mat_=M_WALL_STONE)
    # Upper section
    cyl(f"min_upper{mi}", r=0.40, depth=2.0, segs=14,
        loc=(0, 0, 9.0), parent=m_e, mat_=M_WALL_STONE)
    # Onion top
    smooth_sphere(f"min_dome{mi}", r=0.55, loc=(0, 0, 10.5),
                  parent=m_e, mat_=M_DOME_TURQ, scale=(1, 1, 0.9))
    smooth_cone(f"min_spike{mi}", r1=0.10, r2=0.02, depth=0.60, segs=10,
                loc=(0, 0, 11.3), parent=m_e, mat_=M_DOME_GOLD)
    # Crescent top
    smooth_cone(f"min_cres{mi}", r1=0.02, r2=0.12, depth=0.40, segs=10,
                loc=(0, 0, 11.85), parent=m_e, mat_=M_DOME_GOLD)

# ============ 2 FOUNTAINS ============
fountains = []
for fi, (fx, fy) in enumerate([(-7, 2), (7, 2)]):
    f_e = empty(f"fountain{fi}", (fx, fy, 0))
    # Stone basin (octagonal-ish)
    cyl(f"f_basin{fi}", r=2.0, depth=0.50, segs=8,
        loc=(0, 0, 0.25), parent=f_e, mat_=M_FOUNTAIN_STONE)
    cyl(f"f_basin_in{fi}", r=1.7, depth=0.40, segs=8,
        loc=(0, 0, 0.40), parent=f_e, mat_=M_WATER)
    # Center pillar
    cyl(f"f_pillar{fi}", r=0.30, depth=1.5, segs=16,
        loc=(0, 0, 1.15), parent=f_e, mat_=M_FOUNTAIN_STONE)
    cyl(f"f_pillar_top{fi}", r=0.55, depth=0.30, segs=16,
        loc=(0, 0, 1.95), parent=f_e, mat_=M_FOUNTAIN_STONE)
    # Decorative top sphere
    smooth_sphere(f"f_top{fi}", r=0.35, loc=(0, 0, 2.25),
                  parent=f_e, mat_=M_MOSAIC_GOLD)
    # Water jets
    jets = []
    for ji in range(6):
        ja = (ji / 6.0) * math.pi * 2
        jx = math.cos(ja) * 0.30
        jy = math.sin(ja) * 0.30
        # Arc of water (3 droplet spheres)
        for d_idx in range(4):
            jet_t = d_idx / 4.0
            arc_x = jx + math.cos(ja) * jet_t * 1.2
            arc_y = jy + math.sin(ja) * jet_t * 1.2
            arc_z = 2.5 + math.sin(jet_t * math.pi) * 1.0 - jet_t * 0.5
            smooth_sphere(f"f_jet{fi}_{ji}_{d_idx}", r=0.10,
                          loc=(arc_x, arc_y, arc_z), parent=f_e, mat_=M_WATER_FOAM)
    f_e["_phase"] = fi * 0.5
    fountains.append(f_e)

# ============ FLYING CARPET (signature) ============
carpet_e = empty("carpet", loc=(0, -5, 6))
carpet_e.rotation_euler = (math.radians(8), 0, math.radians(15))
# Main carpet (red with patterns)
beveled_cube("c_main", (2.5, 1.6, 0.08), bevel_offset=0.05,
             loc=(0, 0, 0), parent=carpet_e, mat_=M_CARPET_BG)
# Gold border
for side, axis in zip((-1, 1), ('x', 'y')):
    beveled_cube(f"c_border_x{side}", (2.5, 0.15, 0.10), bevel_offset=0.02,
                 loc=(0, side*0.80, 0.01), parent=carpet_e, mat_=M_CARPET_GOLD_PAT)
    beveled_cube(f"c_border_y{side}", (0.15, 1.6, 0.10), bevel_offset=0.02,
                 loc=(side*1.25, 0, 0.01), parent=carpet_e, mat_=M_CARPET_GOLD_PAT)
# Pattern medallions (3 diamonds)
for di in range(3):
    dx = (di - 1) * 0.65
    diamond = beveled_cube(f"c_diamond{di}", (0.30, 0.30, 0.06), bevel_offset=0.04,
                          loc=(dx, 0, 0.05), parent=carpet_e, mat_=M_CARPET_GOLD_PAT)
    diamond.rotation_euler = (0, 0, math.radians(45))
    # Inner diamond
    inner = beveled_cube(f"c_inner_d{di}", (0.18, 0.18, 0.05), bevel_offset=0.02,
                        loc=(dx, 0, 0.08), parent=carpet_e, mat_=M_CARPET_BLUE_PAT)
    inner.rotation_euler = (0, 0, math.radians(45))
# Tassels at corners (signature)
for sx in (-1, 1):
    for sy in (-1, 1):
        for ti in range(3):
            cyl(f"c_tas_{sx}_{sy}_{ti}", r=0.025, depth=0.20, segs=8,
                loc=(sx*1.28 + ti*0.05, sy*0.85, -0.10), parent=carpet_e,
                mat_=M_CARPET_FRINGE)
# Princess on carpet
princess_e = empty("princess", (0, 0, 0.10), parent=carpet_e)
# Sitting torso
smooth_cone("pr_robe", r1=0.30, r2=0.20, depth=0.50, segs=16,
            loc=(0, 0, 0.30), parent=princess_e, mat_=M_VEIL_PURPLE)
# Hips (sitting cross-legged)
smooth_sphere("pr_hips", r=0.30, loc=(0, 0, 0.10),
              parent=princess_e, mat_=M_VEIL_PURPLE, scale=(1.4, 1.4, 0.5))
# Torso
beveled_cube("pr_torso", (0.32, 0.20, 0.40), bevel_offset=0.04,
             loc=(0, 0, 0.65), parent=princess_e, mat_=M_VEIL_PINK)
# Neck
cyl("pr_neck", r=0.08, depth=0.15, segs=10, loc=(0, 0, 0.93),
    parent=princess_e, mat_=M_SKIN_PERSIAN)
# Head
pr_head_e = empty("pr_he", (0, 0, 1.10), parent=princess_e)
smooth_sphere("pr_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
              parent=pr_head_e, mat_=M_SKIN_PERSIAN)
# Hair
smooth_sphere("pr_hair", r=0.20, loc=(0, 0.05, 0.05),
              parent=pr_head_e, mat_=M_HAIR_BLACK, scale=(1, 1, 0.9))
# Veil draped
smooth_sphere("pr_veil", r=0.22, loc=(0, 0.10, 0.0),
              parent=pr_head_e, mat_=M_VEIL_GOLD, scale=(1.15, 1.05, 0.9))
# Eyes
for side in (-1, 1):
    smooth_sphere(f"pr_eye{side}", r=0.022,
                  loc=(side*0.06, -0.14, 0.02), parent=pr_head_e,
                  mat_=mat(f"pr_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
# Tiara
for ti in range(5):
    ta = (ti - 2) * 0.35
    smooth_sphere(f"pr_tiara{ti}", r=0.04, loc=(math.sin(ta)*0.20, -0.05, 0.20),
                  parent=pr_head_e, mat_=M_DOME_GOLD)
# Arms (raised in dance)
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"pr_sh{side_idx}", (side*0.25, 0, 0.85), parent=princess_e)
    sh.rotation_euler = (math.radians(-100), 0, math.radians(side*-30))
    cyl(f"pr_uarm{side_idx}", r=0.06, depth=0.30, segs=10,
        loc=(0, 0, -0.15), parent=sh, mat_=M_SKIN_PERSIAN)
    cyl(f"pr_fa{side_idx}", r=0.05, depth=0.28, segs=10,
        loc=(0, 0, -0.40), parent=sh, mat_=M_SKIN_PERSIAN)
    smooth_sphere(f"pr_hand{side_idx}", r=0.06, loc=(0, 0, -0.55),
                  parent=sh, mat_=M_SKIN_PERSIAN)

# ============ 6 MUSICIANS sitting in semi-circle ============
def make_musician(name, loc, instrument, robe_mat, turban_mat, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sitting body (low)
    smooth_cone(f"{name}_body", r1=0.40, r2=0.30, depth=0.70, segs=16,
                loc=(0, 0, 0.35), parent=base, mat_=robe_mat)
    # Torso
    beveled_cube(f"{name}_torso", (0.32, 0.20, 0.50), bevel_offset=0.04,
                 loc=(0, 0, 0.95), parent=base, mat_=robe_mat)
    # Vest open
    beveled_cube(f"{name}_vest", (0.34, 0.10, 0.45), bevel_offset=0.03,
                 loc=(0, -0.10, 0.95), parent=base, mat_=M_VEST)
    # Neck
    cyl(f"{name}_neck", r=0.08, depth=0.15, segs=10,
        loc=(0, 0, 1.23), parent=base, mat_=M_SKIN_PERSIAN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.40), parent=base)
    smooth_sphere(f"{name}_head", r=0.17, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_PERSIAN)
    # Beard
    smooth_sphere(f"{name}_beard", r=0.10, loc=(0, -0.15, -0.10),
                  parent=head_e, mat_=M_HAIR_BLACK, scale=(1.0, 0.8, 1.1))
    # Turban (signature)
    cyl(f"{name}_t_base", r=0.20, depth=0.10, segs=16,
        loc=(0, 0, 0.15), parent=head_e, mat_=turban_mat)
    cyl(f"{name}_t_mid", r=0.22, depth=0.12, segs=18,
        loc=(0, 0, 0.25), parent=head_e, mat_=turban_mat)
    cyl(f"{name}_t_top", r=0.20, depth=0.10, segs=14,
        loc=(0, 0, 0.35), parent=head_e, mat_=turban_mat)
    # Turban gem
    smooth_sphere(f"{name}_t_gem", r=0.04, loc=(0, -0.20, 0.30),
                  parent=head_e, mat_=M_MOSAIC_RED)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.13, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Arms holding instrument
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.15), parent=base)
        sh.rotation_euler = (math.radians(-70), 0, math.radians(side*-20))
        cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
            loc=(0, 0, -0.15), parent=sh, mat_=M_SKIN_PERSIAN)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
            loc=(0, 0, -0.40), parent=sh, mat_=M_SKIN_PERSIAN)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07, loc=(0, 0, -0.55),
                      parent=sh, mat_=M_SKIN_PERSIAN)
        arms_e.append(sh)
    # Instrument in lap
    inst_e = empty(f"{name}_inst_e", (0, -0.40, 0.85), parent=base)
    if instrument == "oud":
        # Pear-shaped body
        smooth_sphere(f"{name}_oud_body", r=0.25, segs=20, rings=14,
                      loc=(0, 0, 0), parent=inst_e, mat_=M_OUD, scale=(1, 0.7, 1.2))
        # Neck
        beveled_cube(f"{name}_oud_neck", (0.06, 0.06, 0.55), bevel_offset=0.02,
                     loc=(0, -0.50, 0.10), parent=inst_e, mat_=M_OUD)
        # Strings
        for st_i in range(4):
            cyl(f"{name}_oud_str{st_i}", r=0.005, depth=0.6, segs=6,
                loc=((st_i-1.5)*0.03, -0.50, 0.10), parent=inst_e,
                mat_=mat(f"{name}_str_m{st_i}", (0.95,0.92,0.85,1), 0.7, 0.2))
    elif instrument == "tablas":
        # 2 drums
        for tb_idx, tb_x in enumerate((-0.20, 0.20)):
            cyl(f"{name}_tb{tb_idx}", r=0.15, depth=0.25, segs=16,
                loc=(tb_x, 0, 0), parent=inst_e, mat_=M_DRUM)
            cyl(f"{name}_tb_skin{tb_idx}", r=0.15, depth=0.02, segs=16,
                loc=(tb_x, 0, 0.13), parent=inst_e, mat_=M_DRUM_SKIN)
    elif instrument == "sitar":
        # Long neck stringed
        smooth_sphere(f"{name}_sit_body", r=0.22, loc=(0, 0, 0),
                      parent=inst_e, mat_=M_OUD)
        beveled_cube(f"{name}_sit_neck", (0.05, 0.05, 1.0), bevel_offset=0.02,
                     loc=(0, -0.40, 0.25), parent=inst_e, mat_=M_OUD)
    else:  # tambourin
        cyl(f"{name}_tam", r=0.18, depth=0.06, segs=20,
            loc=(0, 0, 0), parent=inst_e, mat_=M_DRUM)
        cyl(f"{name}_tam_skin", r=0.16, depth=0.02, segs=20,
            loc=(0, 0, 0.04), parent=inst_e, mat_=M_DRUM_SKIN)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

musicians = []
mus_specs = [
    ("mus1", (-7, 8, 0), "oud", M_VEIL_BLUE, M_TURBAN_BLUE, math.radians(20)),
    ("mus2", (-9, 5, 0), "tablas", M_VEIL_RED, M_TURBAN_RED, math.radians(40)),
    ("mus3", (-8, -2, 0), "sitar", M_VEIL_PURPLE, M_TURBAN_GOLD, math.radians(80)),
    ("mus4", (7, 8, 0), "tambourin", M_VEIL_BLUE, M_TURBAN_RED, math.radians(-20)),
    ("mus5", (9, 5, 0), "oud", M_VEIL_GOLD, M_TURBAN_BLUE, math.radians(-40)),
    ("mus6", (8, -2, 0), "tablas", M_VEIL_RED, M_TURBAN_GOLD, math.radians(-80)),
]
for spec in mus_specs:
    name, loc, inst, robe, tur, fac = spec
    m = make_musician(name, loc, inst, robe, tur, facing=fac)
    musicians.append(m)

# ============ 8 DANCERS with colorful veils ============
def make_dancer(name, loc, veil_mat, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long skirt (signature flowing)
    smooth_cone(f"{name}_skirt", r1=0.55, r2=0.35, depth=1.5, segs=20,
                loc=(0, 0, 0.75), parent=base, mat_=veil_mat)
    # Belt with coins
    cyl(f"{name}_belt", r=0.40, depth=0.10, segs=18,
        loc=(0, 0, 1.45), parent=base, mat_=M_DOME_GOLD)
    # Coin tassels
    for ti in range(8):
        ta = (ti / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_coin{ti}", r=0.04,
                      loc=(0.40*math.cos(ta), 0.40*math.sin(ta), 1.35),
                      parent=base, mat_=M_DOME_GOLD)
    # Bare torso (bralette)
    beveled_cube(f"{name}_top", (0.40, 0.20, 0.30), bevel_offset=0.04,
                 loc=(0, 0, 1.70), parent=base, mat_=veil_mat)
    # Neck
    cyl(f"{name}_neck", r=0.08, depth=0.15, segs=10,
        loc=(0, 0, 1.95), parent=base, mat_=M_SKIN_PERSIAN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.12), parent=base)
    smooth_sphere(f"{name}_head", r=0.17, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_PERSIAN)
    # Hair (long, flowing)
    smooth_sphere(f"{name}_hair", r=0.19, loc=(0, 0.05, 0.05),
                  parent=head_e, mat_=M_HAIR_BLACK, scale=(1, 1, 0.95))
    # Headband with gem
    cyl(f"{name}_hb", r=0.20, depth=0.05, segs=16,
        loc=(0, 0, 0.15), parent=head_e, mat_=M_DOME_GOLD)
    smooth_sphere(f"{name}_hb_gem", r=0.05, loc=(0, -0.18, 0.16),
                  parent=head_e, mat_=M_MOSAIC_RED)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.13, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Arms (graceful dance pose)
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.90), parent=base)
        sh.rotation_euler = (math.radians(-150), 0, math.radians(side*-40))
        cyl(f"{name}_uarm{side_idx}", r=0.06, depth=0.30, segs=10,
            loc=(0, 0, -0.15), parent=sh, mat_=M_SKIN_PERSIAN)
        cyl(f"{name}_fa{side_idx}", r=0.05, depth=0.28, segs=10,
            loc=(0, 0, -0.40), parent=sh, mat_=M_SKIN_PERSIAN)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.06, loc=(0, 0, -0.55),
                      parent=sh, mat_=M_SKIN_PERSIAN)
        # Veil hanging from hand (signature)
        veil = beveled_cube(f"{name}_veil{side_idx}", (0.30, 0.05, 0.50), bevel_offset=0.02,
                            loc=(0, 0, -0.80), parent=sh, mat_=veil_mat)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

dancers = []
dancer_specs = [
    ("d1", (-3, 1, 0), M_VEIL_PINK, math.radians(20)),
    ("d2", (3, 1, 0), M_VEIL_PURPLE, math.radians(-20)),
    ("d3", (-2, -3, 0), M_VEIL_GOLD, math.radians(60)),
    ("d4", (2, -3, 0), M_VEIL_RED, math.radians(-60)),
    ("d5", (-4, -1, 0), M_VEIL_BLUE, math.radians(45)),
    ("d6", (4, -1, 0), M_VEIL_PINK, math.radians(-45)),
    ("d7", (0, 3, 0), M_VEIL_PURPLE, math.radians(0)),
    ("d8", (0, -4, 0), M_VEIL_GOLD, math.radians(180)),
]
for spec in dancer_specs:
    name, loc, veil, fac = spec
    d = make_dancer(name, loc, veil, facing=fac)
    dancers.append(d)

# ============ 3 CAMELS ============
def make_camel(name, loc, facing=0, two_hump=False):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.60, segs=20, rings=14, loc=(0, 0, 1.30),
                  parent=base, mat_=M_CAMEL, scale=(1.7, 0.95, 0.95))
    # Hump(s)
    smooth_sphere(f"{name}_hump1", r=0.40, loc=(0.15, 0, 1.70),
                  parent=base, mat_=M_CAMEL, scale=(0.9, 1, 1.2))
    if two_hump:
        smooth_sphere(f"{name}_hump2", r=0.35, loc=(-0.30, 0, 1.70),
                      parent=base, mat_=M_CAMEL, scale=(0.9, 1, 1.2))
    # Saddle on hump
    beveled_cube(f"{name}_saddle", (0.50, 0.45, 0.15), bevel_offset=0.04,
                 loc=(0.15, 0, 2.00), parent=base, mat_=M_CAMEL_SADDLE)
    # Long neck (curved up)
    neck_e = empty(f"{name}_neck_e", (1.0, 0, 1.40), parent=base)
    for ni in range(4):
        cyl(f"{name}_neck{ni}", r=0.20 - ni*0.02, depth=0.35, segs=12,
            loc=(0, 0, ni*0.30), parent=neck_e, mat_=M_CAMEL)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.40), parent=neck_e)
    beveled_cube(f"{name}_head", (0.40, 0.22, 0.30), bevel_offset=0.04,
                 loc=(0.10, 0, 0), parent=head_e, mat_=M_CAMEL)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04,
                      loc=(0.10, side*0.12, 0.08), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.06, r2=0.01, depth=0.18, segs=10,
                          loc=(-0.10, side*0.10, 0.18), parent=head_e, mat_=M_CAMEL_DARK)
        ear.rotation_euler = (math.radians(-20), 0, math.radians(side*15))
    # 4 legs (long)
    for x_idx, x in enumerate((0.55, -0.55)):
        for y_idx, y in enumerate((-0.35, 0.35)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.12, depth=1.10, segs=10,
                loc=(x, y, 0.55), parent=base, mat_=M_CAMEL)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.13, depth=0.10, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_CAMEL_DARK)
    # Tail
    beveled_cube(f"{name}_tail", (0.08, 0.08, 0.50),
                 loc=(-0.90, 0, 1.30), parent=base, mat_=M_CAMEL)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

camels = [
    make_camel("camel1", (-14, -5, 0), math.radians(-30), True),
    make_camel("camel2", (-15, -2, 0), math.radians(-30), False),
    make_camel("camel3", (14, -5, 0), math.radians(150), True),
]

# ============ 2 PEACOCKS with tail fan ============
def make_peacock(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.30, segs=20, rings=14, loc=(0, 0, 0.6),
                  parent=base, mat_=M_PEACOCK_BODY, scale=(1.4, 1, 1.1))
    # Long neck (curved up)
    neck_e = empty(f"{name}_neck_e", (0.30, 0, 0.7), parent=base)
    for ni in range(4):
        cyl(f"{name}_neck{ni}", r=0.07, depth=0.18, segs=10,
            loc=(0, 0, ni*0.15), parent=neck_e, mat_=M_PEACOCK_BODY)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 0.6), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_PEACOCK_BODY)
    # Crown feathers (signature peacock)
    for cf in range(5):
        cfa = (cf - 2) * 0.20
        cf_obj = smooth_cone(f"{name}_crown{cf}", r1=0.015, r2=0.030, depth=0.15, segs=8,
                             loc=(0.02*math.sin(cfa), 0, 0.18), parent=head_e,
                             mat_=M_PEACOCK_BLUE)
        cf_obj.rotation_euler = (cfa, 0, 0)
        # Eye-feather tip
        smooth_sphere(f"{name}_crown_tip{cf}", r=0.025,
                      loc=(0.02*math.sin(cfa), 0, 0.32),
                      parent=head_e, mat_=M_PEACOCK_GOLD)
    # Beak
    smooth_cone(f"{name}_beak", r1=0.04, r2=0.01, depth=0.12, segs=10,
                loc=(0.10, 0, -0.02), parent=head_e,
                mat_=mat(f"{name}_beak_m", (0.85, 0.65, 0.30, 1), 0.7, 0.3)).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025,
                      loc=(0.04, side*0.06, 0.05), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # MASSIVE TAIL FAN (signature) - 30 feathers radiating
    tail_e = empty(f"{name}_te", (-0.30, 0, 0.7), parent=base)
    tail_e.rotation_euler = (math.radians(-30), 0, 0)
    for fi in range(30):
        fa = (fi - 14.5) * 0.10
        f_len = 2.5 - abs(fa) * 0.5
        feather_e = empty(f"{name}_fe{fi}", (0, 0, 0), parent=tail_e)
        feather_e.rotation_euler = (0, 0, fa)
        # Feather shaft
        beveled_cube(f"{name}_f_shaft{fi}", (0.04, f_len, 0.02), bevel_offset=0.01,
                     loc=(0, f_len*0.5, 0), parent=feather_e, mat_=M_PEACOCK_GREEN)
        # Feather end (eye marking - signature peacock eye)
        smooth_sphere(f"{name}_f_eye_o{fi}", r=0.18,
                      loc=(0, f_len, 0), parent=feather_e, mat_=M_PEACOCK_BLUE,
                      scale=(0.7, 1, 0.2))
        smooth_sphere(f"{name}_f_eye_m{fi}", r=0.12,
                      loc=(0, f_len, 0.03), parent=feather_e, mat_=M_PEACOCK_GOLD,
                      scale=(0.7, 1, 0.2))
        smooth_sphere(f"{name}_f_eye_i{fi}", r=0.06,
                      loc=(0, f_len, 0.06), parent=feather_e, mat_=M_PEACOCK_GREEN,
                      scale=(0.7, 1, 0.2))
    # 2 legs
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.04, depth=0.5, segs=10,
            loc=(0.05, side*0.08, 0.25), parent=base, mat_=M_CAMEL_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "tail": tail_e}

peacocks = [
    make_peacock("peacock1", (-10, 14, 0), math.radians(30)),
    make_peacock("peacock2", (10, 14, 0), math.radians(-30)),
]

# ============ MAGIC LAMP + DJINN ============
lamp_e = empty("lamp", loc=(5, -6, 0.5))
# Brass body (signature aladin oil lamp)
smooth_sphere("lamp_body", r=0.45, segs=22, rings=14, loc=(0, 0, 0),
              parent=lamp_e, mat_=M_LAMP_BRASS, scale=(1.5, 1, 0.8))
# Spout (curved)
smooth_cone("lamp_spout", r1=0.10, r2=0.05, depth=0.5, segs=12,
            loc=(0.55, 0, 0.10), parent=lamp_e,
            mat_=M_LAMP_BRASS).rotation_euler = (0, math.radians(-90), 0)
# Handle
beveled_cube("lamp_handle_v", (0.05, 0.05, 0.30), bevel_offset=0.02,
             loc=(-0.55, 0, 0.10), parent=lamp_e, mat_=M_LAMP_BRASS)
beveled_cube("lamp_handle_h", (0.20, 0.05, 0.05), bevel_offset=0.02,
             loc=(-0.65, 0, 0.25), parent=lamp_e, mat_=M_LAMP_BRASS)
# Top spike
smooth_cone("lamp_top", r1=0.08, r2=0.01, depth=0.25, segs=10,
            loc=(0, 0, 0.30), parent=lamp_e, mat_=M_LAMP_BRASS)

# DJINN emerging from spout (smoke + figure)
djinn_e = empty("djinn", loc=(6.5, -6, 2.5))
# Smoke trail bottom (cone)
for i in range(5):
    t_p = i / 5.0
    smooth_sphere(f"djinn_smoke{i}", r=0.30 + t_p*0.40,
                  loc=(-1.0 + t_p*1.0, 0, -1.5 + t_p*1.5),
                  parent=djinn_e, mat_=M_DJINN_SMOKE, scale=(1, 1, 0.8))
# Djinn body upper (translucent blue)
smooth_cone("djinn_body", r1=0.55, r2=0.30, depth=1.2, segs=18,
            loc=(0, 0, 0.6), parent=djinn_e, mat_=M_DJINN_BODY)
# Arms crossed
for side in (-1, 1):
    arm_e = empty(f"djinn_arm{side}", (side*0.45, 0, 1.20), parent=djinn_e)
    arm_e.rotation_euler = (math.radians(-50), 0, math.radians(side*45))
    cyl(f"djinn_uarm{side}", r=0.10, depth=0.40, segs=12,
        loc=(0, 0, -0.20), parent=arm_e, mat_=M_DJINN_BODY)
    cyl(f"djinn_fa{side}", r=0.08, depth=0.35, segs=10,
        loc=(0, 0, -0.55), parent=arm_e, mat_=M_DJINN_BODY)
# Torso
beveled_cube("djinn_torso", (0.50, 0.30, 0.50), bevel_offset=0.05,
             loc=(0, 0, 1.50), parent=djinn_e, mat_=M_DJINN_BODY)
# Head
djinn_head_e = empty("djinn_he", (0, 0, 1.95), parent=djinn_e)
smooth_sphere("djinn_head", r=0.35, segs=22, rings=14, loc=(0, 0, 0),
              parent=djinn_head_e, mat_=M_DJINN_BODY)
# Glowing yellow eyes (signature)
for side in (-1, 1):
    smooth_sphere(f"djinn_eye{side}", r=0.06,
                  loc=(0.08, side*0.18, 0.05), parent=djinn_head_e, mat_=M_DJINN_EYE)
# Beard (curling smoke)
smooth_sphere("djinn_beard", r=0.25, loc=(0, -0.25, -0.20),
              parent=djinn_head_e, mat_=M_DJINN_BODY, scale=(1.1, 1.0, 1.3))
# Turban on djinn
cyl("djinn_t", r=0.42, depth=0.18, segs=18,
    loc=(0, 0, 0.30), parent=djinn_head_e, mat_=M_TURBAN_GOLD)
# Turban gem
smooth_sphere("djinn_gem", r=0.07, loc=(0, -0.40, 0.35),
              parent=djinn_head_e, mat_=M_MOSAIC_RED)

# ============ 30 HANGING LANTERNS (across plaza) ============
lanterns = []
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(4, 18)
    lx = rad * math.cos(a)
    ly = rad * math.sin(a)
    lz = random.uniform(4, 10)
    l_e = empty(f"lant{i}", (lx, ly, lz))
    # Chain (hanging from sky)
    for ci in range(5):
        smooth_sphere(f"lant_ch{i}_{ci}", r=0.04,
                      loc=(0, 0, ci*0.3 + 0.7), parent=l_e, mat_=M_LANTERN_CAGE)
    # Cage frame (octagonal)
    cyl(f"lant_top{i}", r=0.25, depth=0.06, segs=14,
        loc=(0, 0, 0.5), parent=l_e, mat_=M_LANTERN_CAGE)
    # Body (glowing)
    smooth_sphere(f"lant_body{i}", r=0.20, loc=(0, 0, 0.2),
                  parent=l_e, mat_=M_LANTERN, scale=(1, 1, 1.3))
    # Frame ribs
    for fri in range(6):
        fra = (fri / 6.0) * math.pi * 2
        rib = beveled_cube(f"lant_rib{i}_{fri}", (0.02, 0.02, 0.40), bevel_offset=0.005,
                          loc=(0.18*math.cos(fra), 0.18*math.sin(fra), 0.20),
                          parent=l_e, mat_=M_LANTERN_CAGE)
    # Bottom
    cyl(f"lant_btm{i}", r=0.18, depth=0.05, segs=14,
        loc=(0, 0, 0.0), parent=l_e, mat_=M_LANTERN_CAGE)
    # Hanging tassel
    cyl(f"lant_tas{i}", r=0.02, depth=0.20, segs=8,
        loc=(0, 0, -0.15), parent=l_e, mat_=M_LANTERN_CAGE)
    l_e["_phase"] = random.uniform(0, math.pi*2)
    lanterns.append(l_e)

# ============================================================
# ⭐ 800 ROSE PETALS tombant (PARTICULE THÉMATIQUE OBLIGATOIRE)
# ============================================================
rose_petals = []
for i in range(800):
    px = random.uniform(-42, 42)
    py = random.uniform(-42, 42)
    pz = random.uniform(2, 30)
    color = M_ROSE_PINK if i % 3 == 0 else (M_ROSE_RED if i % 3 == 1 else M_ROSE_WHITE)
    petal = smooth_sphere(f"rose{i}", r=random.uniform(0.10, 0.15), segs=10, rings=6,
                          loc=(px, py, pz), mat_=color,
                          scale=(1.5, 0.7, 0.18))
    petal.rotation_euler = (random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2))
    petal["_phase"] = random.uniform(0, math.pi*2)
    petal["_base_x"] = px; petal["_base_y"] = py; petal["_base_z"] = pz
    petal["_speed"] = random.uniform(0.4, 1.4)
    petal["_drift_x"] = random.uniform(-1.8, 1.8)
    petal["_drift_y"] = random.uniform(-1.8, 1.8)
    rose_petals.append(petal)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Princess carpet flies (sway + drift)
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    carpet_e.location = (math.sin(t * 0.5) * 3, -5 + math.cos(t * 0.4) * 2,
                          6 + math.sin(t * 0.8) * 0.8)
    carpet_e.rotation_euler = (math.radians(8) + math.sin(t * 1.0) * math.radians(5),
                                 math.cos(t * 0.7) * math.radians(4),
                                 math.radians(15) + t * 0.2)
    carpet_e.keyframe_insert("location", frame=f)
    carpet_e.keyframe_insert("rotation_euler", frame=f)

# Musicians sway + arms strum
for m in musicians:
    phase = m["root"]["_phase"]
    base_z = m["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        m["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        m["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(3),
                                     math.cos(t * 1.0 + phase) * math.radians(3),
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("location", frame=f)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        # Arms strum/play
        for ai, arm in enumerate(m["arms"]):
            strum = math.sin(t * 5.0 + phase + ai * math.pi) * math.radians(15)
            base_rx = math.radians(-70)
            arm.rotation_euler = (base_rx + strum, 0, math.radians((-1 if ai==0 else 1)*-20))
            arm.keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(6), 0,
                                    math.sin(t * 1.2 + phase) * math.radians(10))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Dancers spin + arms sway
for d in dancers:
    phase = d["root"]["_phase"]
    base_z = d["root"].location.z
    base_rz = d["root"].rotation_euler.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Body sway + rotation
        d["root"].location.z = base_z + abs(math.sin(t * 2.0 + phase)) * 0.10
        d["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(6),
                                     math.cos(t * 1.2 + phase) * math.radians(5),
                                     base_rz + t * 0.8)
        d["root"].keyframe_insert("location", frame=f)
        d["root"].keyframe_insert("rotation_euler", frame=f)
        # Arms float
        for ai, arm in enumerate(d["arms"]):
            wave = math.sin(t * 2.5 + phase + ai * math.pi) * math.radians(20)
            arm.rotation_euler = (math.radians(-150) + wave, 0, math.radians((-1 if ai==0 else 1)*-40))
            arm.keyframe_insert("rotation_euler", frame=f)
        d["he"].rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(20))
        d["he"].keyframe_insert("rotation_euler", frame=f)

# Camels walk in place (subtle body bob)
for c in camels:
    phase = c["root"]["_phase"]
    base_z = c["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        c["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.05
        c["root"].keyframe_insert("location", frame=f)
        c["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(5), 0,
                                    math.sin(t * 0.6 + phase) * math.radians(15))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Peacocks - tail fan opens + sway
for p in peacocks:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Tail rotation around X-axis (fan up and down)
        p["tail"].rotation_euler = (math.radians(-30) + math.sin(t * 1.0 + phase) * math.radians(10),
                                     0,
                                     math.sin(t * 1.5 + phase) * math.radians(20))
        p["tail"].keyframe_insert("rotation_euler", frame=f)
        # Head turn
        p["he"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(40))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Djinn rises + rotates + smoke pulse
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    djinn_e.location.z = 2.5 + math.sin(t * 1.0) * 0.5
    djinn_e.rotation_euler = (0, 0, t * 0.8)
    djinn_e.keyframe_insert("location", frame=f)
    djinn_e.keyframe_insert("rotation_euler", frame=f)
# Djinn eyes pulse
for side in (-1, 1):
    eye_obj = bpy.data.objects.get(f"djinn_eye{side}")
    if eye_obj:
        for f in range(1, total_frames + 1, 4):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 3.0) * 0.3
            eye_obj.scale = (s, s, s)
            eye_obj.keyframe_insert("scale", frame=f)

# Fountain jets shimmer
for f_e in fountains:
    phase = f_e["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        f_e.rotation_euler = (0, 0, math.sin(t * 0.5 + phase) * math.radians(3))
        f_e.keyframe_insert("rotation_euler", frame=f)

# Lanterns pulse
for l in lanterns:
    phase = l["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.0 + phase) * 0.08
        l.scale = (s, s, s)
        # Sway
        l.rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(4),
                             math.cos(t * 0.8 + phase) * math.radians(3), 0)
        l.keyframe_insert("scale", frame=f)
        l.keyframe_insert("rotation_euler", frame=f)

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

# Moon halos
for obj in bpy.data.objects:
    if obj.name.startswith("moon_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.7) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 800 ROSE PETALS tombant (signature 1001 nights)
# ============================================================
for pt in rose_petals:
    phase = pt["_phase"]; speed = pt["_speed"]
    bx, by, bz = pt["_base_x"], pt["_base_y"], pt["_base_z"]
    drift_x = pt["_drift_x"]; drift_y = pt["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        z = bz - (speed * t) % 30
        x = bx + drift_x * math.sin(t * 1.3 + phase) * 0.7
        y = by + drift_y * math.cos(t * 1.1 + phase) * 0.7
        rx = phase + t * 1.7
        ry = phase + t * 1.5
        rz = phase + t * 2.0
        pt.location = (x, y, max(0.05, z))
        pt.rotation_euler = (rx, ry, rz)
        pt.keyframe_insert("location", frame=f)
        pt.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_persian_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_persian_palace_1001_nights] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_persian_palace_1001_nights] ONE mosaic ground + Palace+dome+4 minarets + 2 fountains + flying carpet princess + 6 musicians + 8 dancers + 3 camels + 2 peacocks fan + lamp+djinn + 30 lanterns + 800 ROSE PETALS")
print("⭐ FIXES: 1 ground + 800 rose petals tombent + spiral drift (signature 1001 nuits mandatory) ⭐")
