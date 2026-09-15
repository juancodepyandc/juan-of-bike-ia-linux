"""
proc_christmas_market_european_lights.py — 250e procédural AuroraIA (115e qualité MILESTONE)
European Christmas Market Strasbourg: giant Xmas tree + 12 wood chalets + Santa+sleigh+8 reindeer + elves + 8 children + carousel + ice rink + nutcracker + cathedral + 1000 snow + 500 lights
FIXES MILESTONE : 1 ground + 1000 snowflakes + 500 lights DOUBLE quantity celebration
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB250)

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

# Night winter sky
M_SKY = mat("sky", (0.06, 0.10, 0.25, 1.0), 0.0, 0.7, emission=(0.08,0.10,0.25), emission_strength=0.8)
M_CLOUD_NIGHT = mat("cloud_n", (0.30, 0.32, 0.42, 1.0), 0.0, 0.7, emission=(0.28,0.30,0.40), emission_strength=0.5)
M_STAR_BR = mat("star_b", (1.0, 0.95, 0.85, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.85), emission_strength=10.0)

# Snow paved ground
M_SNOW_PAVE = mat("snow_p", (0.85, 0.88, 0.92, 1.0), 0.0, 0.45, emission=(0.82,0.85,0.92), emission_strength=0.6)
M_SNOW_BRIGHT = mat("snow_b", (0.95, 0.95, 0.98, 1.0), 0.0, 0.35, emission=(0.92,0.94,0.98), emission_strength=0.8)
M_PAVE_STONE = mat("pave", (0.45, 0.42, 0.42, 1.0), 0.0, 0.85)

# Wood chalets (signature)
M_WOOD_LIGHT = mat("wood_l", (0.65, 0.42, 0.18, 1.0), 0.0, 0.75, emission=(0.60,0.40,0.18), emission_strength=0.4)
M_WOOD_DARK = mat("wood_d", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)
M_WOOD_RED = mat("wood_r", (0.62, 0.18, 0.12, 1.0), 0.0, 0.55, emission=(0.58,0.18,0.12), emission_strength=0.7)
M_WOOD_GREEN = mat("wood_g", (0.18, 0.45, 0.20, 1.0), 0.0, 0.70, emission=(0.18,0.42,0.20), emission_strength=0.5)
M_WOOD_BEAM = mat("wood_be", (0.30, 0.18, 0.08, 1.0), 0.0, 0.85)
WOOD_CHALET_VARIANTS = [M_WOOD_LIGHT, M_WOOD_RED, M_WOOD_GREEN]

# Half-timber (signature Alsace colombages)
M_PLASTER_WHITE = mat("plaster_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.75, emission=(0.92,0.90,0.85), emission_strength=0.5)
M_PLASTER_CREAM = mat("plaster_c", (0.92, 0.85, 0.65, 1.0), 0.0, 0.75, emission=(0.88,0.82,0.62), emission_strength=0.5)

# Roof tiles snowy
M_ROOF_DARK = mat("roof_d", (0.18, 0.15, 0.15, 1.0), 0.0, 0.80, emission=(0.18,0.15,0.15), emission_strength=0.3)
M_ROOF_RED = mat("roof_r", (0.55, 0.20, 0.15, 1.0), 0.0, 0.70, emission=(0.50,0.20,0.15), emission_strength=0.4)

# Christmas tree (signature)
M_FIR_GREEN = mat("fir_g", (0.10, 0.32, 0.15, 1.0), 0.0, 0.65, emission=(0.10,0.30,0.15), emission_strength=0.6)
M_FIR_DARK = mat("fir_d", (0.06, 0.22, 0.10, 1.0), 0.0, 0.70)
M_TRUNK = mat("trunk", (0.30, 0.18, 0.08, 1.0), 0.0, 0.85)

# Decorations
M_ORNAMENT_RED = mat("orn_r", (1.0, 0.15, 0.18, 1.0), 0.85, 0.20, emission=(0.95,0.15,0.18), emission_strength=3.5)
M_ORNAMENT_GOLD = mat("orn_g", (1.0, 0.85, 0.20, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.20), emission_strength=4.0)
M_ORNAMENT_BLUE = mat("orn_b", (0.20, 0.45, 1.0, 1.0), 0.85, 0.20, emission=(0.20,0.45,1.0), emission_strength=3.5)
M_ORNAMENT_GREEN = mat("orn_gr", (0.30, 0.95, 0.40, 1.0), 0.85, 0.20, emission=(0.30,0.92,0.40), emission_strength=3.5)
M_ORNAMENT_PINK = mat("orn_pk", (1.0, 0.55, 0.85, 1.0), 0.85, 0.20, emission=(0.95,0.55,0.82), emission_strength=3.5)
M_ORNAMENT_PURPLE = mat("orn_pu", (0.75, 0.30, 1.0, 1.0), 0.85, 0.20, emission=(0.72,0.30,0.95), emission_strength=3.5)
M_ORNAMENT_SILVER = mat("orn_s", (0.92, 0.92, 0.95, 1.0), 0.95, 0.15, emission=(0.88,0.88,0.92), emission_strength=3.0)
ORNAMENT_COLORS = [M_ORNAMENT_RED, M_ORNAMENT_GOLD, M_ORNAMENT_BLUE,
                   M_ORNAMENT_GREEN, M_ORNAMENT_PINK, M_ORNAMENT_PURPLE, M_ORNAMENT_SILVER]

# Star (signature top tree)
M_STAR_GOLD = mat("star_g", (1.0, 0.92, 0.30, 1.0), 0.95, 0.10, emission=(0.95,0.88,0.30), emission_strength=8.0)

# Lights (signature multicolor)
M_LIGHT_YELLOW = mat("li_y", (1.0, 0.95, 0.40, 1.0), 0.0, 0.20, emission=(1.0,0.95,0.40), emission_strength=8.0)
M_LIGHT_RED = mat("li_r", (1.0, 0.20, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.20,0.20), emission_strength=8.0)
M_LIGHT_GREEN = mat("li_g", (0.20, 1.0, 0.30, 1.0), 0.0, 0.20, emission=(0.20,1.0,0.30), emission_strength=8.0)
M_LIGHT_BLUE = mat("li_b", (0.20, 0.45, 1.0, 1.0), 0.0, 0.20, emission=(0.20,0.45,1.0), emission_strength=8.0)
M_LIGHT_ORANGE = mat("li_o", (1.0, 0.55, 0.18, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.18), emission_strength=8.0)
LIGHT_COLORS = [M_LIGHT_YELLOW, M_LIGHT_RED, M_LIGHT_GREEN, M_LIGHT_BLUE, M_LIGHT_ORANGE]

# Santa
M_SANTA_RED = mat("santa_r", (0.85, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.80,0.15,0.15), emission_strength=0.9)
M_SANTA_WHITE = mat("santa_w", (0.95, 0.95, 0.95, 1.0), 0.0, 0.75)
M_SANTA_BLACK = mat("santa_bk", (0.10, 0.10, 0.10, 1.0), 0.0, 0.80)
M_SANTA_BELT_GOLD = mat("santa_g", (1.0, 0.85, 0.25, 1.0), 0.95, 0.20, emission=(0.95,0.80,0.25), emission_strength=1.5)
M_BEARD_WHITE = mat("beard_w", (0.95, 0.95, 0.92, 1.0), 0.0, 0.55)

# Skin (Santa cheek)
M_SKIN_PINK = mat("skin_p", (0.92, 0.72, 0.62, 1.0), 0.0, 0.55, emission=(0.88,0.70,0.62), emission_strength=0.4)
M_SKIN_CHEEK = mat("skin_c", (0.95, 0.55, 0.50, 1.0), 0.0, 0.55, emission=(0.90,0.55,0.50), emission_strength=0.6)

# Reindeer
M_REINDEER = mat("rein", (0.55, 0.35, 0.18, 1.0), 0.0, 0.75, emission=(0.50,0.32,0.18), emission_strength=0.4)
M_REINDEER_LIGHT = mat("rein_l", (0.75, 0.55, 0.32, 1.0), 0.0, 0.70)
M_ANTLER_R = mat("antler", (0.45, 0.30, 0.18, 1.0), 0.0, 0.55, emission=(0.42,0.28,0.18), emission_strength=0.4)
M_RUDOLPH_NOSE = mat("rudolph", (1.0, 0.20, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.20,0.20), emission_strength=14.0)
M_HARNESS = mat("harness", (0.55, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.50,0.18,0.18), emission_strength=0.5)
M_BELL_GOLD = mat("bell", (1.0, 0.85, 0.25, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.25), emission_strength=2.5)

# Sleigh
M_SLEIGH_RED = mat("sl_r", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.18), emission_strength=0.8)
M_SLEIGH_GOLD = mat("sl_g", (1.0, 0.85, 0.20, 1.0), 0.95, 0.18, emission=(0.95,0.80,0.20), emission_strength=1.8)
M_SLEIGH_RUNNER = mat("sl_run", (0.85, 0.85, 0.85, 1.0), 0.9, 0.20, emission=(0.80,0.80,0.80), emission_strength=1.0)

# Elves
M_ELF_GREEN = mat("elf_g", (0.20, 0.55, 0.25, 1.0), 0.0, 0.60, emission=(0.18,0.52,0.25), emission_strength=0.6)
M_ELF_RED = mat("elf_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.72,0.18,0.18), emission_strength=0.6)
M_ELF_HAT = mat("elf_h", (0.78, 0.20, 0.20, 1.0), 0.0, 0.55, emission=(0.72,0.20,0.20), emission_strength=0.6)
M_SKIN_LIGHT_X = mat("skin_l", (0.92, 0.78, 0.62, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.62), emission_strength=0.4)

# Children clothes
M_COAT_RED = mat("co_r", (0.75, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.70,0.18,0.18), emission_strength=0.5)
M_COAT_BLUE = mat("co_b", (0.18, 0.42, 0.78, 1.0), 0.0, 0.65, emission=(0.18,0.40,0.75), emission_strength=0.5)
M_COAT_GREEN = mat("co_g", (0.18, 0.55, 0.32, 1.0), 0.0, 0.65, emission=(0.18,0.52,0.30), emission_strength=0.5)
M_COAT_PURPLE = mat("co_p", (0.62, 0.30, 0.85, 1.0), 0.0, 0.65, emission=(0.60,0.30,0.82), emission_strength=0.5)
M_COAT_YELLOW = mat("co_y", (0.95, 0.78, 0.20, 1.0), 0.0, 0.55, emission=(0.92,0.75,0.20), emission_strength=0.7)
M_COAT_PINK = mat("co_pk", (0.95, 0.55, 0.85, 1.0), 0.0, 0.55, emission=(0.92,0.55,0.82), emission_strength=0.6)
COAT_COLORS = [M_COAT_RED, M_COAT_BLUE, M_COAT_GREEN, M_COAT_PURPLE, M_COAT_YELLOW, M_COAT_PINK]

M_SCARF_RED = mat("sc_r", (0.95, 0.30, 0.30, 1.0), 0.0, 0.65, emission=(0.90,0.30,0.30), emission_strength=0.6)
M_SCARF_GREEN = mat("sc_g", (0.30, 0.85, 0.40, 1.0), 0.0, 0.65, emission=(0.30,0.80,0.40), emission_strength=0.6)
SCARF_COLORS = [M_SCARF_RED, M_SCARF_GREEN]

# Carousel
M_CAROUSEL_RED = mat("car_r", (0.85, 0.18, 0.20, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.20), emission_strength=1.0)
M_CAROUSEL_GOLD = mat("car_g", (1.0, 0.85, 0.20, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.20), emission_strength=2.0)
M_HORSE_WHITE = mat("h_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.92,0.90,0.85), emission_strength=0.6)
M_HORSE_BROWN = mat("h_b", (0.45, 0.28, 0.15, 1.0), 0.0, 0.75, emission=(0.42,0.28,0.15), emission_strength=0.4)
M_HORSE_BLACK = mat("h_bk", (0.18, 0.12, 0.10, 1.0), 0.0, 0.80)

# Ice rink
M_ICE = mat("ice", (0.75, 0.92, 0.95, 1.0), 0.1, 0.20, emission=(0.72,0.90,0.95), emission_strength=2.5, alpha=0.65)
M_ICE_DEEP = mat("ice_d", (0.55, 0.82, 0.90, 1.0), 0.1, 0.25, alpha=0.78)

# Nutcracker (signature)
M_NUT_RED = mat("nc_r", (0.85, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.80,0.15,0.15), emission_strength=0.8)
M_NUT_BLUE = mat("nc_b", (0.20, 0.42, 0.78, 1.0), 0.0, 0.55, emission=(0.18,0.42,0.75), emission_strength=0.7)
M_NUT_GOLD = mat("nc_g", (1.0, 0.85, 0.25, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.25), emission_strength=1.8)
M_NUT_WHITE = mat("nc_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.70)
M_NUT_BLACK = mat("nc_bk", (0.10, 0.10, 0.10, 1.0), 0.0, 0.65)
M_NUT_BEARD_WHITE = mat("nc_bw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.55)
M_NUT_TEETH = mat("nc_t", (0.92, 0.90, 0.85, 1.0), 0.0, 0.50, emission=(0.88,0.88,0.85), emission_strength=1.0)

# Cathedral
M_CATH_STONE = mat("cath", (0.55, 0.42, 0.32, 1.0), 0.0, 0.85, emission=(0.50,0.40,0.30), emission_strength=0.3)
M_CATH_DARK = mat("cath_d", (0.35, 0.28, 0.22, 1.0), 0.0, 0.85)
M_STAINED_GLASS = mat("sg", (0.78, 0.45, 0.85, 1.0), 0.0, 0.20, emission=(0.85,0.55,0.92), emission_strength=4.0, alpha=0.75)

# Angel
M_ANGEL_GOLD = mat("ang", (1.0, 0.92, 0.55, 1.0), 0.85, 0.20, emission=(0.95,0.88,0.55), emission_strength=2.5)
M_ANGEL_WHITE = mat("ang_w", (0.98, 0.95, 0.92, 1.0), 0.0, 0.40, emission=(0.95,0.92,0.88), emission_strength=1.8)

# Food signature
M_FOOD_SAUSAGE = mat("saus", (0.55, 0.22, 0.15, 1.0), 0.0, 0.65, emission=(0.50,0.20,0.15), emission_strength=0.5)
M_FOOD_BREAD = mat("bread", (0.85, 0.62, 0.32, 1.0), 0.0, 0.65, emission=(0.78,0.58,0.30), emission_strength=0.5)
M_FOOD_CHEESE = mat("cheese", (1.0, 0.85, 0.32, 1.0), 0.0, 0.55, emission=(0.95,0.82,0.32), emission_strength=0.5)
M_FOOD_CHESTNUT = mat("chest", (0.55, 0.30, 0.15, 1.0), 0.0, 0.75)
M_FOOD_GINGERBREAD = mat("ginger", (0.65, 0.42, 0.22, 1.0), 0.0, 0.70, emission=(0.60,0.40,0.22), emission_strength=0.4)
M_MULLED_WINE = mat("wine", (0.55, 0.10, 0.18, 1.0), 0.1, 0.30, emission=(0.50,0.10,0.18), emission_strength=1.2, alpha=0.85)
M_MULLED_CUP = mat("cup", (0.92, 0.88, 0.82, 1.0), 0.0, 0.55)

# Eye
M_EYE_DARK_X = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS_RED = mat("lips", (0.85, 0.20, 0.30, 1.0), 0.0, 0.40, emission=(0.80,0.20,0.30), emission_strength=0.4)

# ============ SKY ============
sky = smooth_sphere("sky", r=250, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Snow clouds
for ci in range(20):
    cax = random.uniform(-80, 80); cay = random.uniform(-80, 80)
    caz = random.uniform(40, 65)
    cloud_e = empty(f"cloud{ci}", (cax, cay, caz))
    for cli in range(random.randint(3, 5)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(2.5, 4.5), segs=16, rings=10,
                      loc=(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD_NIGHT, scale=(1.4, 1.2, 0.7))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)
# Stars
for si in range(60):
    sa = random.uniform(0, math.pi*2); sr = random.uniform(60, 180)
    sh = random.uniform(20, 80)
    smooth_sphere(f"star{si}", r=random.uniform(0.10, 0.25), segs=8, rings=6,
                  loc=(sr*math.cos(sa), sr*math.sin(sa), sh), mat_=M_STAR_BR)
# STAR OF BETHLEHEM (signature large bright star)
beth_e = empty("bethlehem", (0, 60, 70))
smooth_sphere("beth_main", r=2, segs=20, rings=16, loc=(0, 0, 0),
              parent=beth_e, mat_=M_STAR_GOLD)
# Star rays
for ri in range(8):
    ra = (ri / 8.0) * math.pi * 2
    smooth_cone(f"beth_r{ri}", r1=0.4, r2=0.02, depth=4, segs=10,
                loc=(math.cos(ra)*1.5, math.sin(ra)*1.5, 0),
                parent=beth_e, mat_=M_STAR_GOLD).rotation_euler = (0, math.radians(90), ra)

# ============ ONE clean snowy paved ground ============
ground = beveled_cube("ground", (180, 180, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_SNOW_PAVE)
# Snow piles + paved patches
for i in range(180):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 75)
    smooth_sphere(f"snow_pile{i}", r=random.uniform(0.4, 1.2), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_SNOW_BRIGHT if i % 3 == 0 else M_PAVE_STONE if i % 3 == 1 else M_SNOW_PAVE,
                  scale=(1.5, 1.4, 0.22))

# ============ GIANT CHRISTMAS TREE 8m (signature centerpiece) ============
tree_e = empty("tree", loc=(0, 0, 0))
# Trunk
cyl("tr_trunk", r=0.40, depth=2, segs=14, loc=(0, 0, 1), parent=tree_e, mat_=M_TRUNK)
# Layered cone canopy 8m
for li in range(10):
    lz = 1.5 + li * 1.2
    lr = 4.0 - li * 0.40
    smooth_cone(f"tr_l{li}", r1=lr, r2=0.2, depth=2.0, segs=18, loc=(0, 0, lz),
                parent=tree_e, mat_=M_FIR_GREEN if li % 2 == 0 else M_FIR_DARK)
    # Snow caps on each layer
    smooth_cone(f"tr_sn{li}", r1=lr*0.6, r2=0.1, depth=0.5, segs=18, loc=(0, 0, lz + 0.8),
                parent=tree_e, mat_=M_SNOW_BRIGHT)

# Tree ornaments (signature multicolor balls)
for oi in range(80):
    oa = random.uniform(0, math.pi*2)
    oz = random.uniform(2, 11)
    or_radius = (1.0 - (oz - 2) / 9.0) * 3.5 + 0.3
    ox_o = math.cos(oa) * or_radius
    oy_o = math.sin(oa) * or_radius
    smooth_sphere(f"orn{oi}", r=random.uniform(0.18, 0.28),
                  loc=(ox_o, oy_o, oz), parent=tree_e,
                  mat_=random.choice(ORNAMENT_COLORS))

# Garland of lights spiraling
for gi in range(150):
    ga = gi * 0.3
    gz_l = 1.5 + gi * 0.075
    gr_l = (1.0 - (gz_l - 1.5) / 10.0) * 3.8 + 0.3
    if gz_l > 11.5: break
    smooth_sphere(f"gar{gi}", r=0.10,
                  loc=(math.cos(ga)*gr_l, math.sin(ga)*gr_l, gz_l), parent=tree_e,
                  mat_=LIGHT_COLORS[gi % len(LIGHT_COLORS)])

# TOP STAR (signature gold)
star_top_e = empty("star_top", (0, 0, 12), parent=tree_e)
# 5-pointed star (signature)
for pi in range(5):
    pa = (pi / 5.0) * math.pi * 2 + math.pi/2
    smooth_cone(f"st_p{pi}", r1=0.10, r2=0.005, depth=0.8, segs=8,
                loc=(math.cos(pa)*0.40, math.sin(pa)*0.40, 0),
                parent=star_top_e, mat_=M_STAR_GOLD).rotation_euler = (0, math.radians(90), pa)
# Center
smooth_sphere("st_center", r=0.30, segs=18, rings=14, loc=(0, 0, 0),
              parent=star_top_e, mat_=M_STAR_GOLD)

# Gold tinsel ribbons
for ti in range(8):
    ta = (ti / 8.0) * math.pi * 2
    for li in range(20):
        lt = (li / 20.0) * math.pi * 4
        lz_t = 2 + li * 0.45
        if lz_t > 11: break
        lr_t = (1.0 - (lz_t - 2) / 9.0) * 3.5 + 0.3
        beveled_cube(f"tin{ti}_{li}", (0.08, 0.06, 0.06), bevel_offset=0.01,
                     loc=(math.cos(ta + lt*0.3)*lr_t, math.sin(ta + lt*0.3)*lr_t, lz_t),
                     parent=tree_e, mat_=M_ORNAMENT_GOLD)

# ============ ALSACE HALF-TIMBER HOUSE (signature colombages) ============
alsace_e = empty("alsace", loc=(20, 25, 0))
# Stone base
beveled_cube("al_base", (8, 6, 0.6), bevel_offset=0.10, loc=(0, 0, 0.3),
             parent=alsace_e, mat_=M_PAVE_STONE)
# Walls (plaster cream)
beveled_cube("al_wall", (7.8, 5.8, 5), bevel_offset=0.08, loc=(0, 0, 3.0),
             parent=alsace_e, mat_=M_PLASTER_CREAM)
# Half-timber beams (signature crisscross pattern)
# Vertical beams
for vbi in range(7):
    vbx = -3.5 + vbi * 1.2
    beveled_cube(f"al_vb_f{vbi}", (0.18, 0.10, 4.8), bevel_offset=0.03,
                 loc=(vbx, -2.95, 3.0), parent=alsace_e, mat_=M_WOOD_BEAM)
    beveled_cube(f"al_vb_b{vbi}", (0.18, 0.10, 4.8), bevel_offset=0.03,
                 loc=(vbx, 2.95, 3.0), parent=alsace_e, mat_=M_WOOD_BEAM)
# Horizontal beams
for hbi in range(4):
    hbz = 0.8 + hbi * 1.3
    beveled_cube(f"al_hb_f{hbi}", (8, 0.10, 0.18), bevel_offset=0.03,
                 loc=(0, -2.95, hbz), parent=alsace_e, mat_=M_WOOD_BEAM)
    beveled_cube(f"al_hb_b{hbi}", (8, 0.10, 0.18), bevel_offset=0.03,
                 loc=(0, 2.95, hbz), parent=alsace_e, mat_=M_WOOD_BEAM)
# Diagonal cross beams (signature)
for di in range(4):
    diag_e = empty(f"al_d{di}_e", (-2.0 + di*1.5, -2.95, 2.5), parent=alsace_e)
    diag_e.rotation_euler = (0, math.radians(35), 0)
    beveled_cube(f"al_d{di}", (1.2, 0.10, 0.18), bevel_offset=0.03,
                 loc=(0, 0, 0), parent=diag_e, mat_=M_WOOD_BEAM)
# Sloped roof
for ri in range(8):
    rs = 8.5 - ri * 0.10
    rl = 6.5 - ri * 0.10
    beveled_cube(f"al_r{ri}", (rs, rl, 0.30), bevel_offset=0.06,
                 loc=(0, 0, 5.5 + ri*0.30), parent=alsace_e, mat_=M_ROOF_RED)
# Roof snow caps
for sr in range(5):
    smooth_sphere(f"al_rs{sr}", r=0.4,
                  loc=(-3 + sr*1.5, random.uniform(-2.5, 2.5), 7.3),
                  parent=alsace_e, mat_=M_SNOW_BRIGHT, scale=(1.5, 1.5, 0.4))
# Chimney with smoke
beveled_cube("al_chim", (0.6, 0.6, 1.5), bevel_offset=0.06, loc=(2.5, 1.5, 8.5),
             parent=alsace_e, mat_=M_PAVE_STONE)
# Windows (lit signature)
for wi in range(3):
    for wj in range(2):
        wx_w = -2.5 + wi * 2.5
        wz_w = 2 + wj * 1.8
        beveled_cube(f"al_w{wi}_{wj}", (1.0, 0.10, 1.2), bevel_offset=0.06,
                     loc=(wx_w, -2.95, wz_w), parent=alsace_e, mat_=M_LIGHT_YELLOW)
        # Frame
        beveled_cube(f"al_wf{wi}_{wj}", (1.1, 0.12, 1.3), bevel_offset=0.04,
                     loc=(wx_w, -2.94, wz_w), parent=alsace_e, mat_=M_WOOD_DARK)
        # Cross pattern
        beveled_cube(f"al_wcv{wi}_{wj}", (0.08, 0.14, 1.3), bevel_offset=0.01,
                     loc=(wx_w, -2.93, wz_w), parent=alsace_e, mat_=M_WOOD_DARK)
        beveled_cube(f"al_wch{wi}_{wj}", (1.1, 0.14, 0.08), bevel_offset=0.01,
                     loc=(wx_w, -2.93, wz_w), parent=alsace_e, mat_=M_WOOD_DARK)

# ============ 12 WOOD CHALETS (signature small Christmas market huts) ============
def make_chalet(name, loc, scale=1.0, facing=0, food_type="sausage"):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    chalet_col = random.choice(WOOD_CHALET_VARIANTS)
    # Body
    beveled_cube(f"{name}_b", (3, 2.5, 2.5), bevel_offset=0.08, loc=(0, 0, 1.25),
                 parent=base, mat_=chalet_col)
    # Wood plank lines
    for pi in range(5):
        beveled_cube(f"{name}_pl{pi}", (3.05, 2.55, 0.06), bevel_offset=0.02,
                     loc=(0, 0, 0.30 + pi*0.50), parent=base, mat_=M_WOOD_DARK)
    # Sloped roof (signature with overhang)
    for ri in range(6):
        rs = 3.6 - ri * 0.10
        rl = 3 - ri * 0.10
        beveled_cube(f"{name}_r{ri}", (rs, rl, 0.20), bevel_offset=0.06,
                     loc=(0, 0, 2.6 + ri*0.15), parent=base, mat_=M_ROOF_DARK)
    # Snow on roof
    beveled_cube(f"{name}_rs", (3.4, 2.8, 0.20), bevel_offset=0.06, loc=(0, 0, 3.6),
                 parent=base, mat_=M_SNOW_BRIGHT)
    # Snow drape edges
    for di in range(5):
        beveled_cube(f"{name}_rs_d{di}", (0.40, 0.15, 0.30), bevel_offset=0.04,
                     loc=(-1.4 + di*0.7, -1.50, 3.5), parent=base, mat_=M_SNOW_BRIGHT)
    # Counter front (open)
    beveled_cube(f"{name}_count", (3.2, 0.30, 0.5), bevel_offset=0.04, loc=(0, -1.35, 1.0),
                 parent=base, mat_=M_WOOD_DARK)
    # Sign above
    beveled_cube(f"{name}_sign", (2, 0.10, 0.6), bevel_offset=0.06, loc=(0, -1.35, 2.3),
                 parent=base, mat_=M_WOOD_DARK)
    # Sign text (signature lit)
    cyl(f"{name}_st", r=0.08, depth=0.04, segs=14, loc=(0, -1.40, 2.3),
        parent=base, mat_=M_LIGHT_YELLOW).rotation_euler = (math.radians(90), 0, 0)
    # GARLAND LIGHTS draped on chalet (signature)
    for gi in range(15):
        gx_g = -1.5 + gi * 0.20
        gy_g = -1.4 - math.sin(gi * 0.5) * 0.15
        smooth_sphere(f"{name}_g{gi}", r=0.06, loc=(gx_g, gy_g, 2.65),
                      parent=base, mat_=LIGHT_COLORS[gi % len(LIGHT_COLORS)])
    # Wreath signature
    wreath_e = empty(f"{name}_wr_e", (0, -1.40, 1.7), parent=base)
    for wi in range(10):
        wa = (wi / 10.0) * math.pi * 2
        smooth_sphere(f"{name}_wr{wi}", r=0.10, loc=(math.cos(wa)*0.25, 0, math.sin(wa)*0.25),
                      parent=wreath_e, mat_=M_FIR_GREEN)
    # Red bow on wreath
    smooth_sphere(f"{name}_bow", r=0.10, loc=(0, -0.05, -0.25), parent=wreath_e, mat_=M_ORNAMENT_RED,
                  scale=(1.5, 0.6, 1))
    # FOOD on counter (signature variety)
    if food_type == "sausage":
        for fi in range(5):
            cyl(f"{name}_saus{fi}", r=0.08, depth=0.35, segs=10,
                loc=(-0.8 + fi*0.40, -1.20, 1.35), parent=base, mat_=M_FOOD_SAUSAGE).rotation_euler = (math.radians(90), 0, 0)
    elif food_type == "cheese":
        for fi in range(3):
            beveled_cube(f"{name}_ch{fi}", (0.4, 0.4, 0.30), bevel_offset=0.04,
                         loc=(-0.6 + fi*0.6, -1.20, 1.35), parent=base, mat_=M_FOOD_CHEESE)
    elif food_type == "bread":
        for fi in range(4):
            smooth_sphere(f"{name}_br{fi}", r=0.18, segs=14, rings=10,
                          loc=(-0.7 + fi*0.45, -1.20, 1.35), parent=base, mat_=M_FOOD_BREAD,
                          scale=(1, 1.5, 1))
    elif food_type == "chestnut":
        for fi in range(15):
            fa = (fi / 5.0) * math.pi * 2; fr = random.uniform(0, 0.5)
            smooth_sphere(f"{name}_cn{fi}", r=0.06,
                          loc=(math.cos(fa)*fr*0.7, -1.20 + math.sin(fa)*fr*0.1, 1.35),
                          parent=base, mat_=M_FOOD_CHESTNUT)
    elif food_type == "gingerbread":
        for fi in range(6):
            beveled_cube(f"{name}_gb{fi}", (0.18, 0.10, 0.30), bevel_offset=0.02,
                         loc=(-0.5 + fi*0.20, -1.20, 1.35), parent=base, mat_=M_FOOD_GINGERBREAD)
    else:  # mulled wine
        for fi in range(4):
            cyl(f"{name}_wc{fi}", r=0.08, depth=0.20, segs=12,
                loc=(-0.6 + fi*0.4, -1.20, 1.35), parent=base, mat_=M_MULLED_CUP)
            cyl(f"{name}_w{fi}", r=0.06, depth=0.15, segs=12,
                loc=(-0.6 + fi*0.4, -1.20, 1.40), parent=base, mat_=M_MULLED_WINE)
    return base

chalets = []
food_types = ["sausage", "cheese", "bread", "chestnut", "gingerbread", "wine"]
chalet_pos = []
# Circle around tree
for ci in range(12):
    ca = (ci / 12.0) * math.pi * 2
    cx_c = math.cos(ca) * 14
    cy_c = math.sin(ca) * 14
    chalet_pos.append((cx_c, cy_c, ca + math.pi))
for i, (cx, cy, fac) in enumerate(chalet_pos):
    c = make_chalet(f"chalet{i}", (cx, cy, 0), scale=1.0, facing=fac,
                    food_type=food_types[i % len(food_types)])
    chalets.append(c)

# ============ SANTA + SLEIGH + 8 REINDEER (signature) ============
santa_setup_e = empty("santa_setup", (-22, -22, 0))

# SLEIGH signature (curved red)
sleigh_e = empty("sleigh", (0, 0, 1), parent=santa_setup_e)
# Body (signature curved shape)
for si in range(6):
    sz_s = si * 0.20
    sw_s = 2.0 - abs(si - 3) * 0.10
    beveled_cube(f"sl_b{si}", (sw_s, 1.0, 0.30), bevel_offset=0.06,
                 loc=(0, 0, sz_s), parent=sleigh_e, mat_=M_SLEIGH_RED)
# Curved front
smooth_sphere("sl_front", r=0.6, segs=18, rings=14, loc=(1.0, 0, 0.30),
              parent=sleigh_e, mat_=M_SLEIGH_RED, scale=(1.5, 0.8, 1.2))
# Back high
beveled_cube("sl_back", (0.30, 1.2, 1.5), bevel_offset=0.10, loc=(-1.0, 0, 1.0),
             parent=sleigh_e, mat_=M_SLEIGH_RED)
# Gold trim
beveled_cube("sl_trim_t", (2.5, 1.1, 0.06), bevel_offset=0.02, loc=(0, 0, 1.10),
             parent=sleigh_e, mat_=M_SLEIGH_GOLD)
# Curved runners
for side in (-1, 1):
    runner_e = empty(f"sl_run{side}_e", (0, side*0.55, 0), parent=sleigh_e)
    # Front curl
    for ri in range(8):
        ra = (ri / 8.0) * math.pi * 0.7
        rx_r = 1.0 + math.cos(ra) * 0.5
        rz_r = math.sin(ra) * 0.5
        smooth_sphere(f"sl_run{side}_{ri}", r=0.08,
                      loc=(rx_r, 0, rz_r), parent=runner_e, mat_=M_SLEIGH_RUNNER)
    # Straight section
    cyl(f"sl_run{side}_s", r=0.08, depth=2.5, segs=10, loc=(-0.2, 0, 0),
        parent=runner_e, mat_=M_SLEIGH_RUNNER).rotation_euler = (0, math.radians(90), 0)
# Decorative gold spirals
for di in range(6):
    smooth_sphere(f"sl_dec{di}", r=0.08, loc=(0.5 - di*0.3, 0.6, 0.7),
                  parent=sleigh_e, mat_=M_SLEIGH_GOLD)

# SANTA in sleigh signature
santa_e = empty("santa", (-0.4, 0, 1.4), parent=sleigh_e)
# Red coat body
smooth_cone("sa_body", r1=0.50, r2=0.55, depth=1.2, segs=14, loc=(0, 0, 0.6),
            parent=santa_e, mat_=M_SANTA_RED)
# White fur trim bottom
cyl("sa_trim_b", r=0.55, depth=0.12, segs=18, loc=(0, 0, 0.05),
    parent=santa_e, mat_=M_SANTA_WHITE)
# White fur trim front opening
beveled_cube("sa_fr_op", (0.06, 0.10, 1.2), bevel_offset=0.02, loc=(0, -0.50, 0.6),
             parent=santa_e, mat_=M_SANTA_WHITE)
# BLACK BELT signature
cyl("sa_belt", r=0.55, depth=0.12, segs=18, loc=(0, 0, 0.65),
    parent=santa_e, mat_=M_SANTA_BLACK)
# GOLD BUCKLE
beveled_cube("sa_buc", (0.16, 0.12, 0.20), bevel_offset=0.03, loc=(0, -0.55, 0.65),
             parent=santa_e, mat_=M_SANTA_BELT_GOLD)
# Arms
for side in (-1, 1):
    sh = empty(f"sa_sh{side}", (side*0.45, -0.10, 1.4), parent=santa_e)
    sh.rotation_euler = (math.radians(-40), 0, math.radians(side*-20))
    cyl(f"sa_uarm{side}", r=0.10, depth=0.50, segs=10, loc=(0, 0, -0.25),
        parent=sh, mat_=M_SANTA_RED)
    cyl(f"sa_fa{side}", r=0.09, depth=0.40, segs=10, loc=(0, 0, -0.70),
        parent=sh, mat_=M_SANTA_RED)
    # White glove
    smooth_sphere(f"sa_gl{side}", r=0.12, loc=(0, 0, -0.95),
                  parent=sh, mat_=M_SANTA_WHITE)
# Boots black
for side in (-1, 1):
    beveled_cube(f"sa_bt{side}", (0.20, 0.30, 0.20), bevel_offset=0.04,
                 loc=(side*0.20, 0.10, 0), parent=santa_e, mat_=M_SANTA_BLACK)
# Head pink
sa_head_e = empty("sa_he", (0, 0, 1.65), parent=santa_e)
smooth_sphere("sa_head", r=0.25, segs=20, rings=14, loc=(0, 0, 0),
              parent=sa_head_e, mat_=M_SKIN_PINK, scale=(1, 1.0, 1.1))
# Pink cheeks (signature)
for side in (-1, 1):
    smooth_sphere(f"sa_cheek{side}", r=0.08, loc=(side*0.12, -0.20, -0.05),
                  parent=sa_head_e, mat_=M_SKIN_CHEEK)
# Twinkling eyes
for side in (-1, 1):
    smooth_sphere(f"sa_eye{side}", r=0.03, loc=(side*0.08, -0.20, 0.05),
                  parent=sa_head_e, mat_=M_EYE_DARK_X)
# BIG WHITE BEARD signature
for bi in range(20):
    ba = (bi / 20.0) * math.pi - math.pi/2
    smooth_sphere(f"sa_bd{bi}", r=0.07,
                  loc=(math.sin(ba)*0.20, -0.20, -0.10 - (bi%4)*0.10),
                  parent=sa_head_e, mat_=M_BEARD_WHITE)
# Moustache
for side in (-1, 1):
    beveled_cube(f"sa_mou{side}", (0.10, 0.04, 0.06), bevel_offset=0.01,
                 loc=(side*0.05, -0.22, -0.05), parent=sa_head_e, mat_=M_BEARD_WHITE)
# Red cap signature
sa_hat_e = empty("sa_hat", (0, 0, 0.25), parent=sa_head_e)
# Brim white
cyl("sa_hat_brim", r=0.26, depth=0.10, segs=18, loc=(0, 0, 0),
    parent=sa_hat_e, mat_=M_SANTA_WHITE)
# Cone red
smooth_cone("sa_hat_c", r1=0.24, r2=0.04, depth=0.60, segs=14, loc=(0.10, 0, 0.30),
            parent=sa_hat_e, mat_=M_SANTA_RED).rotation_euler = (0, math.radians(20), 0)
# Pom pom
smooth_sphere("sa_hat_pom", r=0.10, loc=(0.30, 0, 0.55),
              parent=sa_hat_e, mat_=M_SANTA_WHITE)

# 8 REINDEER (signature)
def make_reindeer(name, loc, scale=1.0, facing=0, is_rudolph=False):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.6, segs=18, rings=14, loc=(0, 0, 1.3),
                  parent=base, mat_=M_REINDEER, scale=(1.7, 1.0, 1.0))
    # Belly
    smooth_sphere(f"{name}_belly", r=0.5, loc=(0, 0, 1.10),
                  parent=base, mat_=M_REINDEER_LIGHT, scale=(1.5, 0.85, 0.5))
    # 4 long legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}{y}", r=0.08, depth=1.3, segs=10,
                loc=(x*0.55, y*0.35, 0.65), parent=base, mat_=M_REINDEER)
            # Hoof
            cyl(f"{name}_h{x}{y}", r=0.10, depth=0.10, segs=10,
                loc=(x*0.55, y*0.35, 0.05), parent=base, mat_=M_SANTA_BLACK)
    # Neck
    neck_r_e = empty(f"{name}_neck", (0.8, 0, 1.6), parent=base)
    neck_r_e.rotation_euler = (0, math.radians(-30), 0)
    cyl(f"{name}_neck_b", r=0.18, depth=0.8, segs=14, loc=(0, 0, 0.4),
        parent=neck_r_e, mat_=M_REINDEER)
    # Head
    head_r_e = empty(f"{name}_he", (0, 0, 0.85), parent=neck_r_e)
    smooth_sphere(f"{name}_head", r=0.22, segs=18, rings=14, loc=(0.10, 0, 0),
                  parent=head_r_e, mat_=M_REINDEER, scale=(1.5, 0.9, 1.0))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.18, loc=(0.32, 0, -0.05),
                  parent=head_r_e, mat_=M_REINDEER, scale=(1.2, 0.7, 0.7))
    # RUDOLPH RED NOSE (signature)
    if is_rudolph:
        smooth_sphere(f"{name}_nose", r=0.10, loc=(0.50, 0, -0.05),
                      parent=head_r_e, mat_=M_RUDOLPH_NOSE)
    else:
        smooth_sphere(f"{name}_nose", r=0.06, loc=(0.45, 0, -0.02),
                      parent=head_r_e, mat_=M_SANTA_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04, loc=(0.15, side*0.15, 0.05),
                      parent=head_r_e, mat_=M_EYE_DARK_X)
    # ANTLERS signature branched
    for side in (-1, 1):
        ant_e = empty(f"{name}_a{side}_e", (-0.10, side*0.10, 0.30), parent=head_r_e)
        ant_e.rotation_euler = (0, 0, math.radians(side*30))
        # Main beam
        cyl(f"{name}_a{side}_m", r=0.04, depth=0.55, segs=8, loc=(0, side*0.10, 0.30),
            parent=ant_e, mat_=M_ANTLER_R).rotation_euler = (math.radians(side*-20), 0, 0)
        # Branches
        for bri in range(4):
            br_z = 0.20 + bri * 0.15
            bra_e = empty(f"{name}_a{side}_br{bri}_e", (0, side*(0.10 + bri*0.05), br_z), parent=ant_e)
            bra_e.rotation_euler = (math.radians(side*-30), math.radians(side*20 + bri*5), math.radians(side*40))
            cyl(f"{name}_a{side}_br{bri}", r=0.025, depth=0.20, segs=8, loc=(0, 0, 0.10),
                parent=bra_e, mat_=M_ANTLER_R)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.10,
                      loc=(-0.05, side*0.18, 0.10), parent=head_r_e,
                      mat_=M_REINDEER, scale=(0.5, 1.2, 0.9))
    # HARNESS with bells (signature)
    cyl(f"{name}_harn", r=0.22, depth=0.10, segs=14, loc=(0, 0, 0.30),
        parent=neck_r_e, mat_=M_HARNESS)
    # Bells
    for bi in range(3):
        smooth_sphere(f"{name}_bell{bi}", r=0.05,
                      loc=((bi-1)*0.10, 0.15, 0.30),
                      parent=neck_r_e, mat_=M_BELL_GOLD)
    # Tail
    cyl(f"{name}_tail", r=0.04, depth=0.3, segs=8, loc=(-1.0, 0, 1.35),
        parent=base, mat_=M_REINDEER).rotation_euler = (math.radians(45), 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_r_e, "neck": neck_r_e}

reindeer = []
# 8 reindeer in 2 rows of 4
for ri in range(8):
    side_r = 1 if ri % 2 == 0 else -1
    row_r = ri // 2
    rx_r = 4 + row_r * 2.5
    ry_r = side_r * 0.7
    r = make_reindeer(f"reindeer{ri}", (rx_r, ry_r, 0), scale=1.0,
                      facing=math.radians(0), is_rudolph=(ri == 0))
    r["root"].parent = santa_setup_e
    reindeer.append(r)

# Reins from sleigh to reindeer (signature)
for ri in range(8):
    side_r = 1 if ri % 2 == 0 else -1
    row_r = ri // 2
    rx_r = 4 + row_r * 2.5
    ry_r = side_r * 0.7
    # Rope
    cyl(f"rein_rope{ri}", r=0.02, depth=math.sqrt(rx_r**2 + ry_r**2), segs=6,
        loc=(rx_r/2, ry_r/2, 1.5), parent=santa_setup_e,
        mat_=M_HARNESS).rotation_euler = (0, math.radians(90), math.atan2(ry_r, rx_r))

# ============ 4 ELVES (signature green/red small) ============
def make_elf(name, loc, scale=0.7, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    elf_outfit = random.choice([M_ELF_GREEN, M_ELF_RED])
    # Body
    smooth_cone(f"{name}_body", r1=0.25*scale, r2=0.28*scale, depth=0.6*scale, segs=14,
                loc=(0, 0, 0.9*scale), parent=base, mat_=elf_outfit)
    # Belt
    cyl(f"{name}_belt", r=0.28*scale, depth=0.06*scale, segs=14, loc=(0, 0, 0.65*scale),
        parent=base, mat_=M_SANTA_BLACK)
    # Striped tights
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.06*scale, depth=0.7*scale, segs=10,
            loc=(side*0.10*scale, 0, 0.35*scale), parent=base, mat_=M_NUT_WHITE)
        # Stripes
        for sl in range(4):
            cyl(f"{name}_ls{side}_{sl}", r=0.065*scale, depth=0.05*scale, segs=10,
                loc=(side*0.10*scale, 0, 0.10 + sl*0.18*scale), parent=base, mat_=M_ELF_RED)
        # Curled pointy shoes
        beveled_cube(f"{name}_sh{side}", (0.08*scale, 0.25*scale, 0.06*scale), bevel_offset=0.02,
                     loc=(side*0.10*scale, 0.10*scale, 0), parent=base, mat_=M_ELF_RED)
        # Shoe curl tip
        smooth_sphere(f"{name}_sh_t{side}", r=0.04*scale,
                      loc=(side*0.10*scale, 0.20*scale, 0.06*scale), parent=base, mat_=M_BELL_GOLD)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh_arm{side_idx}", (side*0.27*scale, 0, 1.20*scale), parent=base)
        sh.rotation_euler = (math.radians(-50 + side*15), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side_idx}", r=0.04*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.15*scale), parent=sh, mat_=elf_outfit)
        cyl(f"{name}_fa{side_idx}", r=0.035*scale, depth=0.25*scale, segs=10,
            loc=(0, 0, -0.42*scale), parent=sh, mat_=M_SKIN_LIGHT_X)
    # Head
    head_x_e = empty(f"{name}_he", (0, 0, 1.45*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_x_e, mat_=M_SKIN_LIGHT_X, scale=(1, 1.0, 1.1))
    # Pointy ears (signature)
    for side in (-1, 1):
        smooth_cone(f"{name}_ear{side}", r1=0.06*scale, r2=0.01*scale, depth=0.20*scale, segs=8,
                    loc=(side*0.18*scale, 0, 0.05*scale), parent=head_x_e,
                    mat_=M_SKIN_LIGHT_X).rotation_euler = (0, 0, math.radians(side*70))
    # Eyes big
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04*scale,
                      loc=(side*0.07*scale, -0.15*scale, 0.04*scale), parent=head_x_e, mat_=M_EYE_DARK_X)
    # Lips
    beveled_cube(f"{name}_smile", (0.08*scale, 0.04*scale, 0.02*scale), bevel_offset=0.005,
                 loc=(0, -0.18*scale, -0.06*scale), parent=head_x_e, mat_=M_LIPS_RED)
    # POINTY HAT (signature red)
    hat_e = empty(f"{name}_hat", (0, 0, 0.20*scale), parent=head_x_e)
    smooth_cone(f"{name}_hat_c", r1=0.20*scale, r2=0.01*scale, depth=0.50*scale, segs=14,
                loc=(0.10*scale, 0, 0.25*scale), parent=hat_e,
                mat_=M_ELF_HAT).rotation_euler = (0, math.radians(30), 0)
    # Bell on hat tip
    smooth_sphere(f"{name}_hat_bell", r=0.05*scale, loc=(0.35*scale, 0, 0.60*scale),
                  parent=hat_e, mat_=M_BELL_GOLD)
    base["_phase"] = random.uniform(0, math.pi*2)
    base["_speed"] = random.uniform(1.5, 2.5)
    return {"root": base, "he": head_x_e}

elves = []
elf_pos = [(-8, 8, math.radians(0)), (8, 8, math.radians(180)),
            (-10, -10, math.radians(60)), (10, -10, math.radians(-60))]
for i, (ex, ey, fac) in enumerate(elf_pos):
    e = make_elf(f"elf{i}", (ex, ey, 0), scale=0.7, facing=fac)
    elves.append(e)

# ============ 8 CHILDREN amazed (signature) ============
def make_child(name, loc, scale=0.6, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    coat_col = random.choice(COAT_COLORS)
    scarf_col = random.choice(SCARF_COLORS)
    # Coat body
    smooth_cone(f"{name}_coat", r1=0.30*scale, r2=0.32*scale, depth=0.80*scale, segs=14,
                loc=(0, 0, 1.0*scale), parent=base, mat_=coat_col)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.08*scale, depth=0.7*scale, segs=10,
            loc=(side*0.10*scale, 0, 0.35*scale), parent=base, mat_=M_SANTA_BLACK)
        # Snow boots
        beveled_cube(f"{name}_bt{side}", (0.10*scale, 0.20*scale, 0.10*scale), bevel_offset=0.02,
                     loc=(side*0.10*scale, 0, 0), parent=base, mat_=M_SANTA_BLACK)
    # Scarf (signature striped wrapped)
    cyl(f"{name}_scarf", r=0.30*scale, depth=0.15*scale, segs=14, loc=(0, 0, 1.45*scale),
        parent=base, mat_=scarf_col)
    # Scarf tail
    beveled_cube(f"{name}_scarf_t", (0.10*scale, 0.06*scale, 0.40*scale), bevel_offset=0.02,
                 loc=(0.18*scale, -0.15*scale, 1.30*scale), parent=base, mat_=scarf_col)
    # Arms wide pointing (signature amazement)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.50*scale), parent=base)
        sh.rotation_euler = (math.radians(-130), 0, math.radians(side*-40))
        cyl(f"{name}_uarm{side_idx}", r=0.05*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.18*scale), parent=sh, mat_=coat_col)
        cyl(f"{name}_fa{side_idx}", r=0.045*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.50*scale), parent=sh, mat_=M_SKIN_LIGHT_X)
        # Mitten
        smooth_sphere(f"{name}_mit{side_idx}", r=0.07*scale, loc=(0, 0, -0.70*scale),
                      parent=sh, mat_=scarf_col)
    # Head
    head_c_e = empty(f"{name}_he", (0, 0, 1.70*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_c_e, mat_=M_SKIN_LIGHT_X, scale=(1, 1.0, 1.1))
    # Rosy cheeks
    for side in (-1, 1):
        smooth_sphere(f"{name}_cheek{side}", r=0.05*scale, loc=(side*0.12*scale, -0.17*scale, -0.05*scale),
                      parent=head_c_e, mat_=M_SKIN_CHEEK)
    # Big amazed eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04*scale,
                      loc=(side*0.07*scale, -0.16*scale, 0.04*scale),
                      parent=head_c_e, mat_=M_NUT_WHITE)
        smooth_sphere(f"{name}_pup{side}", r=0.025*scale,
                      loc=(side*0.07*scale, -0.18*scale, 0.04*scale),
                      parent=head_c_e, mat_=M_EYE_DARK_X)
    # Open mouth in awe
    smooth_sphere(f"{name}_mouth", r=0.04*scale, loc=(0, -0.17*scale, -0.07*scale),
                  parent=head_c_e, mat_=M_NUT_BLACK)
    # Pom hat (signature)
    hat_c_e = empty(f"{name}_hat", (0, 0, 0.20*scale), parent=head_c_e)
    smooth_cone(f"{name}_hat_c", r1=0.20*scale, r2=0.04*scale, depth=0.35*scale, segs=14,
                loc=(0, 0, 0.17*scale), parent=hat_c_e, mat_=coat_col)
    # White trim
    cyl(f"{name}_hat_tr", r=0.20*scale, depth=0.05*scale, segs=14, loc=(0, 0, 0),
        parent=hat_c_e, mat_=M_NUT_WHITE)
    # Pom pom
    smooth_sphere(f"{name}_hat_p", r=0.08*scale, loc=(0, 0, 0.38*scale),
                  parent=hat_c_e, mat_=M_NUT_WHITE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_c_e}

children = []
child_pos = [(-4, 6, math.radians(-30)), (4, 6, math.radians(30)),
              (-6, 4, math.radians(0)), (6, 4, math.radians(0)),
              (-5, -2, math.radians(180)), (5, -2, math.radians(180)),
              (-3, -8, math.radians(0)), (3, -8, math.radians(0))]
for i, (cx, cy, fac) in enumerate(child_pos):
    c = make_child(f"child{i}", (cx, cy, 0), scale=0.6, facing=fac)
    children.append(c)

# ============ CAROUSEL (signature golden horses) ============
carousel_e = empty("carousel", loc=(20, -10, 0))
# Base
cyl("car_base", r=5, depth=0.4, segs=24, loc=(0, 0, 0.2), parent=carousel_e, mat_=M_CAROUSEL_RED)
# Center pole
cyl("car_pole", r=0.30, depth=6, segs=14, loc=(0, 0, 3.2), parent=carousel_e, mat_=M_CAROUSEL_GOLD)
# Top decorative
smooth_cone("car_top_c", r1=5.5, r2=0.5, depth=2, segs=24, loc=(0, 0, 7.2),
            parent=carousel_e, mat_=M_CAROUSEL_RED)
# Top finial
smooth_sphere("car_finial", r=0.5, loc=(0, 0, 8.5), parent=carousel_e, mat_=M_CAROUSEL_GOLD)
# Gold stripes signature
for si in range(12):
    sa = (si / 12.0) * math.pi * 2
    beveled_cube(f"car_str{si}", (0.10, 0.08, 2), bevel_offset=0.02,
                 loc=(math.cos(sa)*5.4, math.sin(sa)*5.4, 6.2),
                 parent=carousel_e, mat_=M_CAROUSEL_GOLD)
# Lights around top
for li in range(20):
    la = (li / 20.0) * math.pi * 2
    smooth_sphere(f"car_l{li}", r=0.10,
                  loc=(math.cos(la)*5.5, math.sin(la)*5.5, 7.5),
                  parent=carousel_e, mat_=LIGHT_COLORS[li % len(LIGHT_COLORS)])

# Horses signature
horses_carousel = []
horse_colors = [M_HORSE_WHITE, M_HORSE_BROWN, M_HORSE_BLACK, M_HORSE_WHITE,
                M_HORSE_BROWN, M_HORSE_WHITE, M_HORSE_BLACK, M_HORSE_BROWN]
horse_holders = []
for hi in range(8):
    ha = (hi / 8.0) * math.pi * 2
    hx_h = math.cos(ha) * 3.5
    hy_h = math.sin(ha) * 3.5
    horse_e = empty(f"horse{hi}", (hx_h, hy_h, 1.5), parent=carousel_e)
    horse_e.rotation_euler = (0, 0, ha + math.pi/2)
    # Pole (gold)
    cyl(f"hp{hi}", r=0.05, depth=4, segs=10, loc=(0, 0, 1),
        parent=horse_e, mat_=M_CAROUSEL_GOLD)
    # Horse body
    smooth_sphere(f"hb{hi}", r=0.30, segs=18, rings=12, loc=(0, 0, 0.5),
                  parent=horse_e, mat_=horse_colors[hi], scale=(1.6, 0.85, 1))
    # 4 legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"hl{hi}_{x}_{y}", r=0.04, depth=0.5, segs=8,
                loc=(x*0.30, y*0.18, 0.25), parent=horse_e, mat_=horse_colors[hi])
    # Neck
    cyl(f"hn{hi}", r=0.10, depth=0.30, segs=10, loc=(0.40, 0, 0.65),
        parent=horse_e, mat_=horse_colors[hi]).rotation_euler = (0, math.radians(-30), 0)
    # Head
    smooth_sphere(f"hh{hi}", r=0.12, segs=14, rings=10, loc=(0.55, 0, 0.85),
                  parent=horse_e, mat_=horse_colors[hi], scale=(1.5, 0.85, 0.85))
    # Mane signature
    for mi in range(5):
        smooth_sphere(f"hm{hi}_{mi}", r=0.05,
                      loc=(0.35 - mi*0.05, 0, 0.85 + mi*0.04),
                      parent=horse_e, mat_=M_SANTA_BLACK)
    # Tail
    cyl(f"ht{hi}", r=0.05, depth=0.30, segs=8, loc=(-0.40, 0, 0.65),
        parent=horse_e, mat_=M_SANTA_BLACK).rotation_euler = (0, math.radians(60), 0)
    horse_holders.append(horse_e)
    horses_carousel.append({"root": horse_e})

# ============ ICE RINK (signature with skaters) ============
ice_e = empty("ice", loc=(-22, 10, 0))
# Ice surface
beveled_cube("ice_main", (12, 10, 0.15), bevel_offset=0.06, loc=(0, 0, 0.10),
             parent=ice_e, mat_=M_ICE)
beveled_cube("ice_deep", (11, 9, 0.10), bevel_offset=0.04, loc=(0, 0, 0.15),
             parent=ice_e, mat_=M_ICE_DEEP)
# Wood barriers around
for side_x, sx_mul in [("L", -1), ("R", 1)]:
    beveled_cube(f"ice_bar_{side_x}", (0.30, 10.5, 0.8), bevel_offset=0.06,
                 loc=(sx_mul*6, 0, 0.40), parent=ice_e, mat_=M_WOOD_DARK)
for side_y, sy_mul in [("F", -1), ("B", 1)]:
    beveled_cube(f"ice_bar_{side_y}", (12.5, 0.30, 0.8), bevel_offset=0.06,
                 loc=(0, sy_mul*5, 0.40), parent=ice_e, mat_=M_WOOD_DARK)
# Skate marks (signature curved)
for mi in range(15):
    ma = random.uniform(0, math.pi*2); mr = random.uniform(1, 4)
    cyl(f"ice_mk{mi}", r=0.10, depth=0.02, segs=12,
        loc=(mr*math.cos(ma), mr*math.sin(ma), 0.20), parent=ice_e, mat_=M_ICE_DEEP)
# Surface ripples
for ri in range(20):
    rx_r = random.uniform(-5, 5); ry_r = random.uniform(-4, 4)
    cyl(f"ice_rp{ri}", r=random.uniform(0.20, 0.40), depth=0.04, segs=14,
        loc=(rx_r, ry_r, 0.20), parent=ice_e, mat_=M_NUT_WHITE)

# ============ GIANT NUTCRACKER 3m (signature) ============
nut_e = empty("nutcracker", loc=(-15, 22, 0))
# Base (legs)
for side in (-1, 1):
    cyl(f"nc_leg{side}", r=0.22, depth=1.2, segs=12, loc=(side*0.20, 0, 0.6),
        parent=nut_e, mat_=M_NUT_WHITE)
    # Stripes
    for si in range(4):
        cyl(f"nc_ls{side}_{si}", r=0.23, depth=0.06, segs=12,
            loc=(side*0.20, 0, 0.10 + si*0.30), parent=nut_e, mat_=M_NUT_RED)
    # Boot
    beveled_cube(f"nc_bt{side}", (0.30, 0.55, 0.15), bevel_offset=0.04,
                 loc=(side*0.20, 0.10, 0), parent=nut_e, mat_=M_NUT_BLACK)
# Red coat body (signature)
smooth_cone("nc_coat", r1=0.55, r2=0.60, depth=1.4, segs=14, loc=(0, 0, 1.9),
            parent=nut_e, mat_=M_NUT_RED)
# Belt
cyl("nc_belt", r=0.62, depth=0.10, segs=18, loc=(0, 0, 1.50), parent=nut_e, mat_=M_NUT_BLACK)
# Belt buckle gold
beveled_cube("nc_bk", (0.20, 0.10, 0.15), bevel_offset=0.03, loc=(0, -0.60, 1.50),
             parent=nut_e, mat_=M_NUT_GOLD)
# Gold buttons row
for bi in range(5):
    smooth_sphere(f"nc_btn{bi}", r=0.06, loc=(0, -0.62, 1.7 + bi*0.20),
                  parent=nut_e, mat_=M_NUT_GOLD)
# Gold trim
beveled_cube("nc_tr_l", (0.10, 0.10, 1.4), bevel_offset=0.02, loc=(-0.45, -0.60, 1.9),
             parent=nut_e, mat_=M_NUT_GOLD)
beveled_cube("nc_tr_r", (0.10, 0.10, 1.4), bevel_offset=0.02, loc=(0.45, -0.60, 1.9),
             parent=nut_e, mat_=M_NUT_GOLD)
# Blue cuffs at wrists
# Arms
for side in (-1, 1):
    sh = empty(f"nc_sh{side}", (side*0.55, 0, 2.5), parent=nut_e)
    sh.rotation_euler = (math.radians(-20 + side*5), 0, math.radians(side*-5))
    cyl(f"nc_uarm{side}", r=0.15, depth=0.7, segs=12, loc=(0, 0, -0.35),
        parent=sh, mat_=M_NUT_RED)
    # Blue cuff
    cyl(f"nc_cuf{side}", r=0.16, depth=0.10, segs=12, loc=(0, 0, -0.75),
        parent=sh, mat_=M_NUT_BLUE)
    cyl(f"nc_fa{side}", r=0.12, depth=0.5, segs=12, loc=(0, 0, -1.10),
        parent=sh, mat_=M_NUT_WHITE)
# Head
nc_head_e = empty("nc_he", (0, 0, 3.0), parent=nut_e)
smooth_sphere("nc_head", r=0.45, segs=20, rings=14, loc=(0, 0, 0),
              parent=nc_head_e, mat_=M_NUT_WHITE, scale=(1, 1.1, 1.0))
# Big black eyes (signature)
for side in (-1, 1):
    smooth_sphere(f"nc_eye{side}", r=0.10, loc=(side*0.15, -0.40, 0.15),
                  parent=nc_head_e, mat_=M_NUT_WHITE)
    smooth_sphere(f"nc_pup{side}", r=0.07, loc=(side*0.15, -0.46, 0.15),
                  parent=nc_head_e, mat_=M_NUT_BLACK)
# Red round nose
smooth_sphere("nc_nose", r=0.09, loc=(0, -0.45, 0), parent=nc_head_e, mat_=M_NUT_RED)
# White beard signature
for bi in range(15):
    ba = (bi / 15.0) * math.pi - math.pi/2
    smooth_sphere(f"nc_bd{bi}", r=0.06,
                  loc=(math.sin(ba)*0.30, -0.40, -0.20 - (bi%3)*0.08),
                  parent=nc_head_e, mat_=M_NUT_BEARD_WHITE)
# White moustache
for side in (-1, 1):
    beveled_cube(f"nc_mou{side}", (0.18, 0.06, 0.08), bevel_offset=0.02,
                 loc=(side*0.08, -0.45, -0.10), parent=nc_head_e, mat_=M_NUT_BEARD_WHITE)
# Open mouth showing teeth (signature)
beveled_cube("nc_mouth", (0.30, 0.06, 0.20), bevel_offset=0.04, loc=(0, -0.42, -0.30),
             parent=nc_head_e, mat_=M_NUT_BLACK)
# Teeth row
for ti in range(6):
    beveled_cube(f"nc_t{ti}", (0.04, 0.03, 0.10), bevel_offset=0.005,
                 loc=((ti-2.5)*0.05, -0.45, -0.30), parent=nc_head_e, mat_=M_NUT_TEETH)
# TALL HAT (signature)
hat_n_e = empty("nc_hat", (0, 0, 0.55), parent=nc_head_e)
cyl("nc_h_b", r=0.55, depth=0.10, segs=18, loc=(0, 0, 0), parent=hat_n_e, mat_=M_NUT_BLUE)
cyl("nc_h_c", r=0.45, depth=0.8, segs=18, loc=(0, 0, 0.45), parent=hat_n_e, mat_=M_NUT_BLUE)
# Gold trim hat
cyl("nc_h_t", r=0.46, depth=0.05, segs=18, loc=(0, 0, 0.10), parent=hat_n_e, mat_=M_NUT_GOLD)
# Sword in hand (signature)
sword_n_e = empty("nc_sword", (-0.65, -0.10, 1.5), parent=nut_e)
sword_n_e.rotation_euler = (math.radians(0), 0, math.radians(-10))
beveled_cube("nc_sw_b", (0.04, 0.08, 1.5), bevel_offset=0.005, loc=(0, 0, 0.75),
             parent=sword_n_e, mat_=M_SLEIGH_RUNNER)
smooth_cone("nc_sw_p", r1=0.05, r2=0.005, depth=0.20, segs=8, loc=(0, 0, 1.55),
            parent=sword_n_e, mat_=M_SLEIGH_RUNNER)
cyl("nc_sw_cg", r=0.03, depth=0.30, segs=8, loc=(0, 0, 0.10),
    parent=sword_n_e, mat_=M_NUT_GOLD).rotation_euler = (0, math.radians(90), 0)

# ============ STRASBOURG CATHEDRAL background (signature) ============
cath_e = empty("cathedral", loc=(0, 55, 0))
# Foundation
beveled_cube("ca_base", (12, 8, 1.5), bevel_offset=0.10, loc=(0, 0, 0.75),
             parent=cath_e, mat_=M_CATH_DARK)
# Main body
beveled_cube("ca_body", (11, 7, 14), bevel_offset=0.10, loc=(0, 0, 8.5),
             parent=cath_e, mat_=M_CATH_STONE)
# Tall spire signature
for li in range(8):
    lz = 14 + li * 2
    lr = 4 - li * 0.4
    cyl(f"ca_sp{li}", r=lr, depth=2, segs=8, loc=(0, 0, lz),
        parent=cath_e, mat_=M_CATH_STONE)
# Sharp peak
smooth_cone("ca_peak", r1=0.4, r2=0.02, depth=6, segs=14, loc=(0, 0, 32),
            parent=cath_e, mat_=M_CATH_DARK)
# Stained glass rose window (signature)
cyl("ca_rose", r=2.5, depth=0.30, segs=24, loc=(0, -3.5, 8),
    parent=cath_e, mat_=M_STAINED_GLASS).rotation_euler = (math.radians(90), 0, 0)
# Rose window pattern
for ri in range(12):
    ra = (ri / 12.0) * math.pi * 2
    cyl(f"ca_r_p{ri}", r=0.10, depth=2.5, segs=8,
        loc=(math.cos(ra)*1.2, -3.55, 8 + math.sin(ra)*1.2),
        parent=cath_e, mat_=M_CATH_DARK).rotation_euler = (math.radians(90), 0, 0)
# Arched windows
for wi in range(3):
    for ws in (-1, 1):
        beveled_cube(f"ca_w{wi}_{ws}", (1.5, 0.30, 3),
                     bevel_offset=0.10, loc=(ws*3.5, ws*0 + 3.5, 6 + wi*0),
                     parent=cath_e, mat_=M_STAINED_GLASS)

# ============ ANGEL ON TREE (signature gold) ============
angel_e = empty("angel", loc=(8, 0, 14))
# Body robe
smooth_cone("ang_robe", r1=0.30, r2=0.40, depth=1.0, segs=14, loc=(0, 0, 0.5),
            parent=angel_e, mat_=M_ANGEL_WHITE)
# Gold trim
cyl("ang_tr_b", r=0.40, depth=0.06, segs=14, loc=(0, 0, 0), parent=angel_e, mat_=M_ANGEL_GOLD)
# Head
smooth_sphere("ang_head", r=0.20, segs=18, rings=14, loc=(0, 0, 1.20),
              parent=angel_e, mat_=M_SKIN_LIGHT_X)
# Halo (signature gold ring)
cyl("ang_halo", r=0.25, depth=0.04, segs=20, loc=(0, 0, 1.42),
    parent=angel_e, mat_=M_ANGEL_GOLD)
# Hair flowing
for hi in range(8):
    ha = (hi / 8.0) * math.pi * 2
    smooth_sphere(f"ang_hr{hi}", r=0.06, loc=(math.cos(ha)*0.18, math.sin(ha)*0.10, 1.25),
                  parent=angel_e, mat_=M_NUT_GOLD)
# Wings huge (signature)
for side in (-1, 1):
    wing_a_e = empty(f"ang_w{side}_e", (side*0.20, 0.10, 0.90), parent=angel_e)
    wing_a_e.rotation_euler = (0, math.radians(side*30), math.radians(side*-20))
    for wi in range(8):
        wa = (wi / 8.0) * math.pi - math.pi/2
        wl = 0.6 + abs(math.cos(wa)) * 0.5
        feat = beveled_cube(f"ang_f{side}_{wi}", (0.08, 0.04, wl), bevel_offset=0.02,
                            loc=(side*math.cos(wa)*0.6, 0, math.sin(wa)*0.4),
                            parent=wing_a_e, mat_=M_ANGEL_WHITE)
# Trumpet in hand
trumpet_a_e = empty("ang_trum", (0.35, -0.20, 0.95), parent=angel_e)
trumpet_a_e.rotation_euler = (math.radians(-30), 0, math.radians(45))
cyl("ang_t_b", r=0.04, depth=0.40, segs=10, loc=(0, 0, 0.20),
    parent=trumpet_a_e, mat_=M_ANGEL_GOLD)
smooth_cone("ang_t_bell", r1=0.12, r2=0.04, depth=0.20, segs=12, loc=(0, 0, 0.50),
            parent=trumpet_a_e, mat_=M_ANGEL_GOLD)
angel_e["_phase"] = 0

# ============================================================
# ⭐⭐⭐ 1000 SNOWFLAKES + 500 LIGHTS — DOUBLE QUANTITY MILESTONE 250e (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
snowflakes = []
for i in range(1000):
    px = random.uniform(-60, 60)
    py = random.uniform(-60, 60)
    pz = random.uniform(1, 20)
    s = smooth_sphere(f"snow{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6,
                      loc=(px, py, pz), mat_=M_SNOW_BRIGHT)
    s["_phase"] = random.uniform(0, math.pi*2)
    s["_base_x"] = px; s["_base_y"] = py; s["_base_z"] = pz
    s["_amp_x"] = random.uniform(1.0, 2.5)
    s["_amp_y"] = random.uniform(1.0, 2.5)
    s["_speed"] = random.uniform(0.4, 1.0)
    s["_fall"] = random.uniform(1.5, 3.5)
    snowflakes.append(s)

# 500 string lights flashing
twinkle_lights = []
for i in range(500):
    px = random.uniform(-40, 40)
    py = random.uniform(-40, 40)
    pz = random.uniform(3, 18)
    light_col = random.choice(LIGHT_COLORS)
    l = smooth_sphere(f"twl{i}", r=random.uniform(0.07, 0.12), segs=8, rings=6,
                      loc=(px, py, pz), mat_=light_col)
    l["_phase"] = random.uniform(0, math.pi*2)
    l["_base_x"] = px; l["_base_y"] = py; l["_base_z"] = pz
    l["_speed"] = random.uniform(2.0, 5.0)
    twinkle_lights.append(l)

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

# Reindeer step + head turn
for r in reindeer:
    phase = r["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        r["root"].location.z = abs(math.sin(t * 3.0 + phase)) * 0.10
        r["root"].keyframe_insert("location", frame=f)
        r["he"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(15))
        r["he"].keyframe_insert("rotation_euler", frame=f)

# Santa "ho ho" body
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    santa_e.rotation_euler = (math.sin(t * 1.5) * math.radians(4), 0, 0)
    santa_e.keyframe_insert("rotation_euler", frame=f)
    sa_head_e.rotation_euler = (0, 0, math.sin(t * 2.0) * math.radians(15))
    sa_head_e.keyframe_insert("rotation_euler", frame=f)

# Elves run + dance
for e in elves:
    phase = e["root"]["_phase"]; speed = e["root"]["_speed"]
    bx_el = e["root"].location.x; by_el = e["root"].location.y
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        e["root"].location.x = bx_el + math.sin(t * speed + phase) * 1.5
        e["root"].location.y = by_el + math.cos(t * speed + phase) * 1.5
        e["root"].location.z = abs(math.sin(t * speed * 3.0 + phase)) * 0.30
        e["root"].rotation_euler = (math.sin(t * speed * 2.0 + phase) * math.radians(10), 0,
                                     math.atan2(math.cos(t * speed + phase),
                                                math.sin(t * speed + phase)))
        e["root"].keyframe_insert("location", frame=f)
        e["root"].keyframe_insert("rotation_euler", frame=f)

# Children sway + head amazement
for c in children:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        c["root"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(5),
                                     math.cos(t * 2.0 + phase) * math.radians(5),
                                     c["root"].rotation_euler.z)
        c["root"].location.z = abs(math.sin(t * 3.0 + phase)) * 0.10
        c["root"].keyframe_insert("rotation_euler", frame=f)
        c["root"].keyframe_insert("location", frame=f)
        c["he"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(10), 0,
                                   math.cos(t * 1.5 + phase) * math.radians(15))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Carousel rotates
for f in range(1, total_frames + 1, 2):
    t = (f - 1) / fps
    carousel_e.rotation_euler = (0, 0, t * 0.6)
    carousel_e.keyframe_insert("rotation_euler", frame=f)

# Horses bob up/down on carousel
for hi, horse in enumerate(horses_carousel):
    phase = hi * math.pi / 4
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        ha_h = (hi / 8.0) * math.pi * 2
        horse["root"].location.z = 1.5 + math.sin(t * 3.0 + phase) * 0.40
        horse["root"].keyframe_insert("location", frame=f)

# Angel float
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    angel_e.location.z = 14 + math.sin(t * 0.8) * 0.30
    angel_e.rotation_euler = (math.sin(t * 0.5) * math.radians(5),
                               math.cos(t * 0.5) * math.radians(3), 0)
    angel_e.keyframe_insert("location", frame=f)
    angel_e.keyframe_insert("rotation_euler", frame=f)

# Nutcracker stand stiff + small sway
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    nut_e.rotation_euler = (math.sin(t * 0.5) * math.radians(2),
                             math.cos(t * 0.5) * math.radians(2), 0)
    nut_e.keyframe_insert("rotation_euler", frame=f)

# 1000 snowflakes falling tumbling
for s in snowflakes:
    phase = s["_phase"]; speed = s["_speed"]; fall = s["_fall"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay = s["_amp_x"], s["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.5)
        if z < 0.5: z = bz
        s.location = (x, y, max(0.3, z))
        s.rotation_euler = (t * 2.0 + phase, t * 1.5 + phase, t * 2.5 + phase)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("rotation_euler", frame=f)

# 500 lights flashing
for l in twinkle_lights:
    phase = l["_phase"]; speed = l["_speed"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Twinkle
        sc_t = 0.4 + abs(math.sin(t * speed + phase)) * 1.4
        l.scale = (sc_t, sc_t, sc_t)
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
out_glb = os.path.join(out_dir, "pbr_christmas_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_christmas_market_european_lights] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_christmas_market_european_lights] ⭐⭐⭐ MILESTONE 250e 115e qualité ⭐⭐⭐ Christmas tree 8m + Alsace half-timber + 12 chalets + Santa+sleigh+8 reindeer (Rudolph red nose) + 4 elves + 8 children + carousel 8 horses + ice rink + Nutcracker 3m + Strasbourg cathedral + angel + Bethlehem star + 1000 snow + 500 lights DOUBLE")
print("⭐⭐⭐ MILESTONE FIXES: 1 ground + 1000 snowflakes + 500 lights signature CHRISTMAS celebration ⭐⭐⭐")
