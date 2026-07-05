"""
proc_welsh_snowdonia_castle_dragons.py — 288e procédural AuroraIA (153e qualité)
Welsh Snowdonia castle dragons: Caernarfon castle 4 round towers + 4 red dragons + 4 Welsh knights + harp + Mt Snowdon + Wales flag with red dragon + 600 dragon scales + 400 celtic fairies
FIXES : 1 ground green prairie + signature scales + fairies
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB288)

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

# Sky misty Wales
M_SKY = mat("sky", (0.55, 0.68, 0.78, 1.0), 0.0, 0.7, emission=(0.55,0.68,0.78), emission_strength=1.5)
M_SKY_LOW = mat("sky_l", (0.78, 0.82, 0.85, 1.0), 0.0, 0.7, emission=(0.78,0.82,0.85), emission_strength=1.3)
M_SUN = mat("sun", (0.95, 0.85, 0.65, 1.0), 0.0, 0.1, emission=(0.92,0.82,0.65), emission_strength=12.0)
M_MIST = mat("mi", (0.85, 0.88, 0.92, 1.0), 0.0, 0.95, emission=(0.85,0.88,0.92), emission_strength=1.0, alpha=0.45)

# Green prairie
M_GRASS = mat("g", (0.30, 0.62, 0.28, 1.0), 0.0, 0.65, emission=(0.28,0.60,0.28), emission_strength=0.4)
M_GRASS_DARK = mat("gd", (0.18, 0.45, 0.18, 1.0), 0.0, 0.75)
M_GRASS_DRY = mat("gdy", (0.62, 0.65, 0.32, 1.0), 0.0, 0.65)
M_DIRT = mat("d", (0.42, 0.30, 0.18, 1.0), 0.0, 0.92)
M_STONE = mat("st", (0.55, 0.50, 0.45, 1.0), 0.0, 0.92)

# Castle stone (signature gray)
M_CASTLE_GRAY = mat("cg", (0.55, 0.55, 0.52, 1.0), 0.0, 0.85, emission=(0.52,0.52,0.50), emission_strength=0.3)
M_CASTLE_DARK = mat("cgd", (0.32, 0.32, 0.30, 1.0), 0.0, 0.92)
M_CASTLE_LIGHT = mat("cgl", (0.78, 0.75, 0.70, 1.0), 0.0, 0.75)

# Wood door
M_WOOD_DARK = mat("wd", (0.32, 0.18, 0.10, 1.0), 0.0, 0.75)
M_WOOD_BROWN = mat("wb", (0.55, 0.32, 0.15, 1.0), 0.0, 0.65)
M_IRON = mat("ir", (0.18, 0.15, 0.13, 1.0), 0.5, 0.45)

# Mountain
M_MOUNTAIN = mat("mt", (0.42, 0.42, 0.45, 1.0), 0.0, 0.85)
M_MOUNTAIN_DARK = mat("mtd", (0.28, 0.28, 0.30, 1.0), 0.0, 0.92)
M_SNOW = mat("sn", (0.95, 0.95, 0.95, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.92), emission_strength=0.5)

# Dragon red (signature Y Ddraig Goch)
M_DRAGON_RED = mat("dr", (0.85, 0.18, 0.18, 1.0), 0.1, 0.45, emission=(0.82,0.18,0.18), emission_strength=0.8)
M_DRAGON_DARK = mat("drd", (0.55, 0.10, 0.10, 1.0), 0.1, 0.55)
M_DRAGON_BELLY = mat("db", (1.0, 0.55, 0.45, 1.0), 0.0, 0.55, emission=(0.95,0.55,0.45), emission_strength=0.6)
M_DRAGON_SPIKE = mat("ds", (0.55, 0.08, 0.08, 1.0), 0.0, 0.65)
M_DRAGON_WING = mat("dw", (0.78, 0.15, 0.15, 1.0), 0.0, 0.45, emission=(0.75,0.15,0.15), emission_strength=0.7, alpha=0.85)
M_FIRE = mat("f", (1.0, 0.55, 0.15, 1.0), 0.2, 0.10, emission=(1.0,0.55,0.15), emission_strength=10.0, alpha=0.85)
M_FIRE_CORE = mat("fc", (1.0, 0.92, 0.30, 1.0), 0.2, 0.10, emission=(1.0,0.92,0.30), emission_strength=15.0, alpha=0.90)

# Knight armor
M_ARMOR = mat("ar", (0.65, 0.65, 0.68, 1.0), 0.8, 0.20, emission=(0.62,0.62,0.65), emission_strength=0.4)
M_ARMOR_DARK = mat("ard", (0.42, 0.42, 0.45, 1.0), 0.7, 0.30)
M_TABARD_RED = mat("trd", (0.78, 0.15, 0.18, 1.0), 0.0, 0.55, emission=(0.75,0.15,0.18), emission_strength=0.5)
M_TABARD_WHITE = mat("twh", (0.92, 0.90, 0.85, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.82), emission_strength=0.4)
M_SHIELD = mat("sh", (0.55, 0.55, 0.65, 1.0), 0.6, 0.35)

# Skin
M_SKIN = mat("sk", (0.85, 0.65, 0.45, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.45), emission_strength=0.3)
M_HAIR_BROWN = mat("hbr", (0.42, 0.28, 0.15, 1.0), 0.0, 0.85)

# Harp
M_HARP_WOOD = mat("hw", (0.62, 0.42, 0.20, 1.0), 0.0, 0.55, emission=(0.60,0.42,0.20), emission_strength=0.4)
M_HARP_GOLD = mat("hg", (0.95, 0.78, 0.20, 1.0), 0.8, 0.20, emission=(0.92,0.75,0.20), emission_strength=1.0)
M_STRING = mat("str", (0.85, 0.85, 0.85, 1.0), 0.5, 0.30)

# Wales flag
M_FLAG_GREEN = mat("fg", (0.18, 0.55, 0.22, 1.0), 0.0, 0.45, emission=(0.18,0.52,0.22), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_FLAG_RED = mat("fr", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=1.0)

# Tree (oak)
M_TRUNK = mat("tk", (0.42, 0.28, 0.18, 1.0), 0.0, 0.85)
M_CANOPY_DARK = mat("cad", (0.20, 0.42, 0.20, 1.0), 0.0, 0.65)
M_CANOPY = mat("ca", (0.32, 0.55, 0.25, 1.0), 0.0, 0.65, emission=(0.30,0.52,0.25), emission_strength=0.4)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_DRAGON = mat("egd", (0.95, 0.85, 0.20, 1.0), 0.0, 0.20, emission=(0.92,0.82,0.20), emission_strength=3.0)

# Dragon scale particles
M_SCALE_RED = mat("scr", (0.92, 0.20, 0.22, 1.0), 0.2, 0.30, emission=(0.88,0.20,0.22), emission_strength=2.5)
M_SCALE_DARK = mat("scd", (0.65, 0.10, 0.15, 1.0), 0.2, 0.35, emission=(0.62,0.10,0.15), emission_strength=2.0)
M_SCALE_BRIGHT = mat("scb", (1.0, 0.35, 0.25, 1.0), 0.2, 0.30, emission=(0.95,0.32,0.25), emission_strength=3.0)
SCALE_COLORS = [M_SCALE_RED, M_SCALE_DARK, M_SCALE_BRIGHT]

# Celtic fairy
M_FAIRY_GLOW = mat("fgl", (0.78, 1.0, 0.92, 1.0), 0.0, 0.05, emission=(0.75,0.95,0.92), emission_strength=4.0)
M_FAIRY_BLUE = mat("fbg", (0.55, 0.78, 1.0, 1.0), 0.0, 0.05, emission=(0.52,0.75,0.95), emission_strength=3.5)
M_FAIRY_PURPLE = mat("fpg", (0.85, 0.55, 1.0, 1.0), 0.0, 0.05, emission=(0.82,0.55,0.95), emission_strength=3.5)
FAIRY_COLORS = [M_FAIRY_GLOW, M_FAIRY_BLUE, M_FAIRY_PURPLE]

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-40, 110, 35), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-40, 110, 35), mat_=M_SUN)
# Misty atmosphere
for mi in range(20):
    mx = random.uniform(-120, 120); my = random.uniform(-100, 100); mz = random.uniform(15, 35)
    smooth_sphere(f"mst{mi}", r=random.uniform(2, 4), segs=12, rings=8,
                  loc=(mx, my, mz), mat_=M_MIST, scale=(2, 2, 0.5))

# ============ ONE clean green prairie ground ============
ground = beveled_cube("ground", (280, 280, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_GRASS)
# Grass bumps
for hi in range(180):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 130)
    smooth_sphere(f"hl{hi}", r=random.uniform(1.2, 2.5), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_GRASS_DARK if hi % 3 == 0 else (M_GRASS if hi % 3 == 1 else M_GRASS_DRY),
                  scale=(1.5, 1.4, 0.18))
# Stone outcrops
for ri in range(60):
    a = random.uniform(0, math.pi*2); rad = random.uniform(20, 110)
    smooth_sphere(f"rk{ri}", r=random.uniform(0.5, 1.0), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.12),
                  mat_=M_STONE, scale=(1.4, 1.3, 0.25))

# ============ MT SNOWDON (signature misty peak) ============
def make_mountain(name, loc, height, base_radius):
    base = empty(name, loc)
    n_layers = int(height / 4)
    for li in range(n_layers):
        lz = li * 4
        lr1 = base_radius * (1 - li / n_layers * 0.85)
        lr2 = base_radius * (1 - (li+1) / n_layers * 0.85)
        smooth_cone(f"{name}_l{li}", r1=lr1, r2=lr2, depth=4.5, segs=18,
                    loc=(0, 0, lz + 2.25), parent=base,
                    mat_=M_MOUNTAIN_DARK if li < n_layers//2 else M_MOUNTAIN)
    # Snow cap
    snow_e = empty(f"{name}_se", (0, 0, height * 0.60), parent=base)
    for si in range(4):
        sz = si * 3
        sr = base_radius * (0.4 - si / 4 * 0.35)
        smooth_cone(f"{name}_s{si}", r1=sr + 0.3, r2=sr - 0.1, depth=3, segs=16,
                    loc=(0, 0, sz), parent=snow_e, mat_=M_SNOW)
    smooth_cone(f"{name}_pk", r1=0.4, r2=0.04, depth=2, segs=12,
                loc=(0, 0, height - 0.5), parent=base, mat_=M_SNOW)
    return base

make_mountain("snowdon", (0, 90, 0), 50, 14)
make_mountain("mt2", (-55, 80, 0), 38, 12)
make_mountain("mt3", (50, 85, 0), 42, 13)

# ============ CAERNARFON CASTLE (signature 4 round towers + crenellations) ============
castle_e = empty("castle", (0, 10, 0))
# Main rectangular keep
beveled_cube("ct_k", (20, 16, 8), bevel_offset=0.15, loc=(0, 0, 4),
             parent=castle_e, mat_=M_CASTLE_GRAY)
# Stone block lines (decorative)
for blk_y in range(6):
    by_b = -8 + blk_y * 2.5
    beveled_cube(f"ct_blk{blk_y}", (20.05, 0.05, 0.30), bevel_offset=0.02,
                 loc=(0, -8.05, 0.5 + blk_y*1.2), parent=castle_e, mat_=M_CASTLE_DARK)
# Crenellations on top (signature)
for ci in range(20):
    cx_c = -9 + ci * 1.0
    beveled_cube(f"ct_cr{ci}", (0.6, 16.2, 1.5), bevel_offset=0.06, loc=(cx_c, 0, 8.75),
                 parent=castle_e, mat_=M_CASTLE_LIGHT)
for ci in range(14):
    cy_c = -7 + ci * 1.0
    beveled_cube(f"ct_cs{ci}", (20.2, 0.6, 1.5), bevel_offset=0.06, loc=(0, cy_c, 8.75),
                 parent=castle_e, mat_=M_CASTLE_LIGHT)
# Main entrance gate
gate_e = empty("ct_ge", (0, -8.05, 2.0), parent=castle_e)
# Arched gate
cyl("ct_g", r=1.5, depth=0.30, segs=18, loc=(0, 0, 0), parent=gate_e, mat_=M_WOOD_DARK).rotation_euler = (math.radians(90), 0, 0)
beveled_cube("ct_gb", (3, 0.30, 1.8), bevel_offset=0.06, loc=(0, 0, -1), parent=gate_e, mat_=M_WOOD_DARK)
# Wooden door planks
for di in range(5):
    beveled_cube(f"ct_dp{di}", (0.55, 0.32, 2.2), bevel_offset=0.02,
                 loc=(-1.1 + di*0.55, 0, -0.20), parent=gate_e, mat_=M_WOOD_BROWN)
# Iron rivets
for ri in range(8):
    ra = (ri / 8.0) * math.pi * 2
    smooth_sphere(f"ct_dr{ri}", r=0.08,
                  loc=(math.cos(ra)*1.0, -0.10, math.sin(ra)*0.5),
                  parent=gate_e, mat_=M_IRON)
# Portcullis bars (signature)
for pi in range(6):
    cyl(f"ct_pc{pi}", r=0.05, depth=2.2, segs=8, loc=(-1.25 + pi*0.5, -0.05, 0),
        parent=gate_e, mat_=M_IRON)
# 4 ROUND TOWERS at corners (signature Caernarfon polygonal)
tower_corners = [(-10, -8), (10, -8), (-10, 8), (10, 8)]
for ti, (tx, ty) in enumerate(tower_corners):
    tower_e = empty(f"ct_tw{ti}", (tx, ty, 0), parent=castle_e)
    # Round tower body
    cyl(f"ct_tw{ti}_b", r=2.5, depth=12, segs=20, loc=(0, 0, 6),
        parent=tower_e, mat_=M_CASTLE_GRAY)
    # Stone bands
    for bi in range(4):
        cyl(f"ct_tw{ti}_b{bi}", r=2.55, depth=0.20, segs=20, loc=(0, 0, 2 + bi*2.5),
            parent=tower_e, mat_=M_CASTLE_DARK)
    # Crenellations
    for cri in range(12):
        cra = (cri / 12.0) * math.pi * 2
        beveled_cube(f"ct_tw{ti}_cr{cri}", (0.5, 0.5, 1.2), bevel_offset=0.04,
                     loc=(math.cos(cra)*2.6, math.sin(cra)*2.6, 12.6),
                     parent=tower_e, mat_=M_CASTLE_LIGHT)
    # Conical roof (signature)
    smooth_cone(f"ct_tw{ti}_r", r1=2.8, r2=0.1, depth=3.5, segs=20, loc=(0, 0, 14.7),
                parent=tower_e, mat_=M_CASTLE_DARK)
    # Flag pole + flag on top tower
    cyl(f"ct_tw{ti}_fp", r=0.06, depth=2, segs=8, loc=(0, 0, 17.5),
        parent=tower_e, mat_=M_IRON)
    beveled_cube(f"ct_tw{ti}_fl", (0.04, 1.5, 0.8), bevel_offset=0.04, loc=(0, 0.75, 17.5),
                 parent=tower_e, mat_=M_FLAG_RED)
    # Arrow slits (signature narrow windows)
    for asi in range(3):
        asa = (asi / 3.0) * math.pi * 2 + math.pi/4
        beveled_cube(f"ct_tw{ti}_as{asi}", (0.06, 0.30, 0.85), bevel_offset=0.005,
                     loc=(math.cos(asa)*2.55, math.sin(asa)*2.55, 5 + asi*2.5),
                     parent=tower_e, mat_=M_CASTLE_DARK).rotation_euler = (0, 0, asa)
# Battlement walkway top
beveled_cube("ct_wk", (20.4, 16.4, 0.3), bevel_offset=0.04, loc=(0, 0, 8.3), parent=castle_e, mat_=M_CASTLE_DARK)
# Inner courtyard floor
beveled_cube("ct_cy", (18, 14, 0.20), bevel_offset=0.04, loc=(0, 0, 0.10), parent=castle_e, mat_=M_STONE)
# Main keep tower (taller central)
keep_e = empty("ct_keep", (0, 0, 0), parent=castle_e)
beveled_cube("ct_keep_b", (5, 5, 16), bevel_offset=0.12, loc=(0, 0, 8), parent=keep_e, mat_=M_CASTLE_GRAY)
# Keep crenellations
for cri in range(8):
    cra = (cri / 8.0) * math.pi * 2 + math.pi/8
    beveled_cube(f"ct_keep_cr{cri}", (0.6, 0.6, 1.2), bevel_offset=0.06,
                 loc=(math.cos(cra)*2.5, math.sin(cra)*2.5, 16.6),
                 parent=keep_e, mat_=M_CASTLE_LIGHT)

# ============ 4 RED DRAGONS Y DDRAIG GOCH (signature) ============
def make_dragon(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_bo", r=0.85, segs=14, rings=12, loc=(0, 0, 3),
                  parent=base, mat_=M_DRAGON_RED, scale=(2.0, 0.85, 0.85))
    # Belly lighter
    smooth_sphere(f"{name}_be", r=0.80, segs=12, rings=10, loc=(0, 0, 2.7),
                  parent=base, mat_=M_DRAGON_BELLY, scale=(1.9, 0.85, 0.55))
    # SCALE PLATES (signature dorsal spikes)
    for si_d in range(12):
        sx_d = -1.4 + si_d * 0.25
        sh_d = 0.30 - abs(si_d - 5.5) * 0.02
        beveled_cube(f"{name}_sp{si_d}", (0.06, 0.10, sh_d), bevel_offset=0.01,
                     loc=(sx_d, 0, 3.55), parent=base, mat_=M_DRAGON_SPIKE)
    # Long neck (signature serpentine)
    neck_e = empty(f"{name}_ne", (1.20, 0, 3.30), parent=base)
    neck_e.rotation_euler = (0, math.radians(-30), 0)
    for ni in range(8):
        cyl(f"{name}_n{ni}", r=0.25 - ni*0.015, depth=0.30, segs=10,
            loc=(0, 0, ni*0.30 + 0.15), parent=neck_e, mat_=M_DRAGON_RED)
        # Belly stripe
        cyl(f"{name}_nb{ni}", r=0.22 - ni*0.012, depth=0.30, segs=10,
            loc=(0, -0.04, ni*0.30 + 0.15), parent=neck_e, mat_=M_DRAGON_BELLY)
    # Head
    head_d_e = empty(f"{name}_he", (0, 0, 2.8), parent=neck_e)
    smooth_sphere(f"{name}_h", r=0.30, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_d_e, mat_=M_DRAGON_RED, scale=(1.6, 0.85, 0.85))
    # Snout
    smooth_sphere(f"{name}_sn", r=0.20, segs=12, rings=10, loc=(0.25, 0, -0.05),
                  parent=head_d_e, mat_=M_DRAGON_RED, scale=(1.4, 0.85, 0.85))
    # HORNS (signature curved back)
    for side in (-1, 1):
        horn_e = empty(f"{name}_hn{side}_e", (-0.15, side*0.18, 0.15), parent=head_d_e)
        horn_e.rotation_euler = (0, math.radians(-30), math.radians(side*15))
        for hni in range(5):
            cyl(f"{name}_hn{side}_{hni}", r=0.06 - hni*0.008, depth=0.15, segs=8,
                loc=(0, 0, hni*0.15), parent=horn_e, mat_=M_DRAGON_SPIKE)
    # Eyes (signature glowing yellow)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.05, loc=(0.08, side*0.15, 0.10),
                      parent=head_d_e, mat_=M_EYE_DRAGON)
        smooth_sphere(f"{name}_ep{side}", r=0.025, loc=(0.12, side*0.15, 0.10),
                      parent=head_d_e, mat_=M_EYE)
    # Teeth/fangs (signature)
    for side in (-1, 1):
        cyl(f"{name}_fa{side}", r=0.015, depth=0.08, segs=6,
            loc=(0.35, side*0.05, -0.15), parent=head_d_e, mat_=M_TABARD_WHITE).rotation_euler = (math.radians(180), 0, 0)
    # FIRE BREATH (signature)
    fire_e = empty(f"{name}_fi", (0.50, 0, -0.10), parent=head_d_e)
    smooth_cone(f"{name}_fi_b", r1=0.10, r2=0.50, depth=1.0, segs=12, loc=(0.50, 0, 0),
                parent=fire_e, mat_=M_FIRE).rotation_euler = (0, math.radians(90), 0)
    smooth_cone(f"{name}_fi_c", r1=0.05, r2=0.30, depth=0.7, segs=12, loc=(0.45, 0, 0),
                parent=fire_e, mat_=M_FIRE_CORE).rotation_euler = (0, math.radians(90), 0)
    fire_e["_phase"] = random.uniform(0, math.pi*2)
    # WINGS (signature bat-like with membranes)
    for side in (-1, 1):
        wing_e = empty(f"{name}_w{side}_e", (0, side*0.50, 3.40), parent=base)
        wing_e.rotation_euler = (math.radians(side*30), 0, math.radians(side*15))
        # Wing arm bones
        for wi_b in range(3):
            cyl(f"{name}_w{side}_b{wi_b}", r=0.06 - wi_b*0.01, depth=0.50, segs=8,
                loc=(0, side*(wi_b*0.50 + 0.50), -wi_b*0.20),
                parent=wing_e, mat_=M_DRAGON_DARK)
        # Wing membrane (signature thin)
        beveled_cube(f"{name}_w{side}_m", (0.05, 1.8, 1.2), bevel_offset=0.04, loc=(0, side*1.20, -0.3),
                     parent=wing_e, mat_=M_DRAGON_WING)
        # Wing fingers (3 segments)
        for fi_w in range(3):
            fia = (fi_w - 1) * math.radians(20)
            beveled_cube(f"{name}_w{side}_f{fi_w}", (0.04, 0.6, 0.06), bevel_offset=0.01,
                         loc=(0, side*2.0 + math.cos(fia)*0.2, math.sin(fia)*0.3),
                         parent=wing_e, mat_=M_DRAGON_DARK)
        wing_e["_phase"] = random.uniform(0, math.pi*2)
    # 4 legs with claws
    for li, (lx_d, ly_d) in enumerate([(0.85, 0.40), (0.85, -0.40), (-0.85, 0.40), (-0.85, -0.40)]):
        leg_e = empty(f"{name}_le{li}", (lx_d, ly_d, 2.50), parent=base)
        cyl(f"{name}_ul{li}", r=0.18, depth=0.45, segs=10, loc=(0, 0, -0.22),
            parent=leg_e, mat_=M_DRAGON_RED)
        cyl(f"{name}_ll{li}", r=0.15, depth=0.55, segs=10, loc=(0, 0, -0.72),
            parent=leg_e, mat_=M_DRAGON_RED)
        # Claws
        for cl in range(3):
            beveled_cube(f"{name}_cl{li}_{cl}", (0.05, 0.10, 0.10), bevel_offset=0.01,
                         loc=((cl-1)*0.08, 0.10, -1.05), parent=leg_e, mat_=M_DRAGON_SPIKE)
    # LONG TAIL (signature)
    tail_e = empty(f"{name}_te", (-1.50, 0, 3), parent=base)
    tail_e.rotation_euler = (0, math.radians(85), 0)
    for ti in range(10):
        cyl(f"{name}_t{ti}", r=0.18 - ti*0.012, depth=0.20, segs=10,
            loc=(0, 0, ti*0.20), parent=tail_e, mat_=M_DRAGON_RED)
        # Tail spikes
        beveled_cube(f"{name}_ts{ti}", (0.05, 0.08, 0.15 - ti*0.005), bevel_offset=0.005,
                     loc=(0, 0, ti*0.20 + 0.10), parent=tail_e, mat_=M_DRAGON_SPIKE)
    # Tail tip arrow (signature)
    smooth_cone(f"{name}_tt", r1=0.10, r2=0.02, depth=0.30, segs=8, loc=(0, 0, 2.1),
                parent=tail_e, mat_=M_DRAGON_SPIKE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "fire": fire_e, "head": head_d_e}

dragons = []
dragon_pos = [(-30, -20, 4, math.radians(20)), (30, -20, 4, math.radians(-20)),
               (-25, 35, 4, math.radians(60)), (25, 35, 4, math.radians(-60))]
for i, (dx, dy, dz, fac) in enumerate(dragon_pos):
    d = make_dragon(f"dg{i}", (dx, dy, dz), facing=fac)
    dragons.append(d)

# ============ 4 WELSH KNIGHTS in armor (signature) ============
def make_knight(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Plate armor body
    smooth_cone(f"{name}_a", r1=0.32, r2=0.36, depth=0.85, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=M_ARMOR)
    # TABARD (signature red with white)
    beveled_cube(f"{name}_tb_f", (0.50, 0.10, 0.85), bevel_offset=0.04, loc=(0, -0.34, 1.30),
                 parent=base, mat_=M_TABARD_RED)
    # Welsh dragon on tabard (simplified)
    smooth_sphere(f"{name}_tb_dr", r=0.10, loc=(0, -0.38, 1.40),
                  parent=base, mat_=M_TABARD_WHITE)
    # Belt
    cyl(f"{name}_be", r=0.37, depth=0.10, segs=14, loc=(0, 0, 0.85),
        parent=base, mat_=M_ARMOR_DARK)
    # Pants/greaves
    for side in (-1, 1):
        cyl(f"{name}_g{side}", r=0.12, depth=0.95, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=M_ARMOR)
    # Boots
    for side in (-1, 1):
        beveled_cube(f"{name}_bt{side}", (0.13, 0.28, 0.10), bevel_offset=0.02,
                     loc=(side*0.13, 0.04, 0.05), parent=base, mat_=M_ARMOR_DARK)
    # Arms (one with sword, one with shield)
    sh_l = empty(f"{name}_a0", (-0.32, 0, 1.60), parent=base)
    sh_l.rotation_euler = (math.radians(-90), 0, math.radians(20))
    cyl(f"{name}_ua0", r=0.08, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=M_ARMOR)
    cyl(f"{name}_fa0", r=0.07, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_ARMOR)
    # SHIELD (signature with cross or dragon)
    shield_e = empty(f"{name}_sh", (0, 0.30, -0.70), parent=sh_l)
    # Shield shape (kite/heater)
    beveled_cube(f"{name}_sh_b", (0.70, 0.06, 0.95), bevel_offset=0.10,
                 loc=(0, 0, 0), parent=shield_e, mat_=M_SHIELD)
    # Red cross on shield
    beveled_cube(f"{name}_sh_cv", (0.10, 0.10, 0.70), bevel_offset=0.02,
                 loc=(0, -0.04, 0), parent=shield_e, mat_=M_TABARD_RED)
    beveled_cube(f"{name}_sh_ch", (0.55, 0.10, 0.10), bevel_offset=0.02,
                 loc=(0, -0.04, 0.10), parent=shield_e, mat_=M_TABARD_RED)
    # Right arm with sword
    sh_r = empty(f"{name}_a1", (0.32, 0, 1.60), parent=base)
    sh_r.rotation_euler = (math.radians(-60), 0, math.radians(-15))
    cyl(f"{name}_ua1", r=0.08, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=M_ARMOR)
    cyl(f"{name}_fa1", r=0.07, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_ARMOR)
    # SWORD (signature long)
    sword_e = empty(f"{name}_sw_e", (0, 0, -0.85), parent=sh_r)
    # Blade
    beveled_cube(f"{name}_sw_bl", (0.05, 0.10, 1.50), bevel_offset=0.02, loc=(0, 0, -0.75),
                 parent=sword_e, mat_=M_ARMOR)
    # Hilt
    beveled_cube(f"{name}_sw_h", (0.06, 0.15, 0.10), bevel_offset=0.02, loc=(0, 0, 0.05),
                 parent=sword_e, mat_=M_HARP_GOLD)
    # Pommel
    smooth_sphere(f"{name}_sw_p", r=0.06, loc=(0, 0, 0.18),
                  parent=sword_e, mat_=M_HARP_GOLD)
    # Guard cross
    beveled_cube(f"{name}_sw_g", (0.04, 0.45, 0.05), bevel_offset=0.01, loc=(0, 0, 0),
                 parent=sword_e, mat_=M_ARMOR)
    # Head with HELMET (signature visor)
    head_k_e = empty(f"{name}_he", (0, 0, 2.0), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_k_e, mat_=M_SKIN)
    # Helmet
    helmet_e = empty(f"{name}_hl", (0, 0, 0.05), parent=head_k_e)
    smooth_sphere(f"{name}_hl_t", r=0.20, segs=14, rings=12, loc=(0, 0, 0.05),
                  parent=helmet_e, mat_=M_ARMOR, scale=(1, 1, 1.1))
    # Visor (signature dark slit)
    beveled_cube(f"{name}_hl_v", (0.20, 0.04, 0.05), bevel_offset=0.005, loc=(0, -0.18, 0.02),
                 parent=helmet_e, mat_=M_EYE)
    # Crest plume (signature)
    cyl(f"{name}_hl_c", r=0.04, depth=0.30, segs=8, loc=(0, 0, 0.30),
        parent=helmet_e, mat_=M_TABARD_RED)
    for cri in range(5):
        smooth_sphere(f"{name}_hl_cp{cri}", r=0.08, segs=10, rings=6,
                      loc=(0, -cri*0.06, 0.40 + cri*0.04),
                      parent=helmet_e, mat_=M_TABARD_RED, scale=(0.6, 1.5, 1.0))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_k_e}

knights = []
knight_pos = [(-12, -8, math.radians(45)), (12, -8, math.radians(-45)),
               (-12, 8, math.radians(135)), (12, 8, math.radians(-135))]
for i, (kx, ky, fac) in enumerate(knight_pos):
    k = make_knight(f"kn{i}", (kx, ky, 0), facing=fac)
    knights.append(k)

# ============ CELTIC HARP (signature) ============
harp_e = empty("harp", (-25, 0, 0))
harp_e.rotation_euler = (0, 0, math.radians(20))
# Forepillar (curved front)
for ci in range(8):
    ca = (ci / 8.0) * math.pi * 0.6
    cx = -math.sin(ca) * 0.4
    cz = math.cos(ca) * 1.8 + 0.2
    cyl(f"hp_fp{ci}", r=0.10 - ci*0.005, depth=0.25, segs=10,
        loc=(cx, 0, cz), parent=harp_e, mat_=M_HARP_WOOD)
# Sound box (curved base)
beveled_cube("hp_sb", (0.80, 0.30, 1.5), bevel_offset=0.15, loc=(0.40, 0, 1),
             parent=harp_e, mat_=M_HARP_WOOD)
# Top harmonic curve
for ci in range(8):
    ca = (ci / 8.0) * math.pi * 0.3
    cyl(f"hp_t{ci}", r=0.06, depth=0.15, segs=8,
        loc=(0.40 - math.sin(ca)*0.3, 0, 1.85 + math.cos(ca)*0.2),
        parent=harp_e, mat_=M_HARP_GOLD)
# Strings (signature)
for st in range(15):
    sty = -0.4 + st * 0.05
    cyl(f"hp_s{st}", r=0.005, depth=1.4 - st*0.05, segs=4,
        loc=(0.20 - st*0.02, 0, 1 + st*0.025), parent=harp_e, mat_=M_STRING)
# Gold decoration
smooth_sphere("hp_d1", r=0.08, loc=(0, 0, 2.0), parent=harp_e, mat_=M_HARP_GOLD)
smooth_sphere("hp_d2", r=0.10, loc=(0.40, 0, 0.20), parent=harp_e, mat_=M_HARP_GOLD)

# ============ WALES FLAG (signature red dragon on green/white) ============
flag_e = empty("flag", (-55, -40, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_IRON)
# White top half
beveled_cube("fl_w", (4, 0.05, 1.25), bevel_offset=0.06, loc=(2, 0, 11.10),
             parent=flag_e, mat_=M_FLAG_WHITE)
# Green bottom half
beveled_cube("fl_g", (4, 0.05, 1.25), bevel_offset=0.06, loc=(2, 0, 9.85),
             parent=flag_e, mat_=M_FLAG_GREEN)
# Red dragon (signature simplified)
dragon_e = empty("fl_dr", (2, -0.05, 10.5), parent=flag_e)
# Dragon body
smooth_sphere("fl_dr_bo", r=0.35, segs=14, rings=10, loc=(0, 0, 0),
              parent=dragon_e, mat_=M_FLAG_RED, scale=(1.7, 0.10, 0.85))
# Dragon head
smooth_sphere("fl_dr_h", r=0.18, segs=12, rings=10, loc=(0.45, 0, 0.10),
              parent=dragon_e, mat_=M_FLAG_RED, scale=(1.3, 0.10, 0.85))
# Tail curl
for ti in range(5):
    ta = (ti / 5.0) * math.pi * 0.6
    smooth_sphere(f"fl_dr_t{ti}", r=0.06 - ti*0.005, segs=8, rings=6,
                  loc=(-0.40 - ti*0.10, 0, math.sin(ta)*0.10),
                  parent=dragon_e, mat_=M_FLAG_RED, scale=(1, 0.1, 1))
# Wings
for side in (-1, 1):
    beveled_cube(f"fl_dr_w{side}", (0.20, 0.05, 0.20), bevel_offset=0.04,
                 loc=(0, 0, side*0.20), parent=dragon_e, mat_=M_FLAG_RED)
flag_e["_phase"] = 0

# ============ OAK TREES (signature druidic) ============
def make_oak(name, loc):
    base = empty(name, loc)
    # Trunk thick
    cyl(f"{name}_t", r=0.50, depth=6, segs=10, loc=(0, 0, 3), parent=base, mat_=M_TRUNK)
    # Canopy (wide rounded)
    canopy_e = empty(f"{name}_ce", (0, 0, 6.5), parent=base)
    for ci in range(15):
        ca = random.uniform(0, math.pi*2); cr = random.uniform(0, 3)
        smooth_sphere(f"{name}_c{ci}", r=random.uniform(1.5, 2.5), segs=14, rings=10,
                      loc=(math.cos(ca)*cr, math.sin(ca)*cr, random.uniform(-0.5, 1.5)),
                      parent=canopy_e, mat_=M_CANOPY if ci % 2 else M_CANOPY_DARK)
    return base

for i, (tx, ty) in enumerate([(-50, -20), (50, -20), (-40, -40), (40, -40), (-60, 30), (60, 30)]):
    make_oak(f"ok{i}", (tx, ty, 0))

# ============================================================
# 600 DRAGON SCALES + 400 CELTIC FAIRIES (PARTICULES SIGNATURES)
# ============================================================
scales = []
for i in range(600):
    px = random.uniform(-110, 110)
    py = random.uniform(-110, 110)
    pz = random.uniform(2, 25)
    sc_col = random.choice(SCALE_COLORS)
    sc_e = empty(f"sc{i}", (px, py, pz))
    # Scale shape (curved teardrop)
    beveled_cube(f"sc{i}_b", (0.10, 0.05, 0.15), bevel_offset=0.02,
                 loc=(0, 0, 0), parent=sc_e, mat_=sc_col)
    # Ridge
    beveled_cube(f"sc{i}_r", (0.04, 0.05, 0.15), bevel_offset=0.005,
                 loc=(0, 0, 0.01), parent=sc_e, mat_=sc_col)
    sc_e["_phase"] = random.uniform(0, math.pi*2)
    sc_e["_base_x"] = px; sc_e["_base_z"] = pz
    sc_e["_drift"] = random.uniform(0.2, 0.5)
    sc_e["_fall"] = random.uniform(0.4, 1.0)
    sc_e["_swing"] = random.uniform(1.0, 2.0)
    scales.append(sc_e)

# 400 Celtic fairies
fairies = []
for i in range(400):
    px = random.uniform(-110, 110)
    py = random.uniform(-110, 110)
    pz = random.uniform(2, 25)
    f_col = random.choice(FAIRY_COLORS)
    f_e = empty(f"fa{i}", (px, py, pz))
    # Glow body
    smooth_sphere(f"fa{i}_g", r=0.15, segs=12, rings=8, loc=(0, 0, 0),
                  parent=f_e, mat_=f_col)
    # Tiny fairy form
    smooth_sphere(f"fa{i}_bo", r=0.05, segs=8, rings=6, loc=(0, 0, 0),
                  parent=f_e, mat_=M_TABARD_WHITE)
    # Wings
    for side in (-1, 1):
        beveled_cube(f"fa{i}_w{side}", (0.04, 0.10, 0.04), bevel_offset=0.005,
                     loc=(0, side*0.06, 0.02), parent=f_e, mat_=f_col)
    # Trail sparkles
    for ti in range(3):
        smooth_sphere(f"fa{i}_t{ti}", r=0.03 - ti*0.008,
                      loc=(-0.10 - ti*0.05, 0, 0), parent=f_e, mat_=f_col)
    f_e["_phase"] = random.uniform(0, math.pi*2)
    f_e["_base_x"] = px; f_e["_base_y"] = py; f_e["_base_z"] = pz
    f_e["_amp"] = random.uniform(1, 3)
    f_e["_speed"] = random.uniform(0.6, 1.6)
    f_e["_blink"] = random.uniform(3, 7)
    fairies.append(f_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Dragons sway + fire breath + wing flap
for d in dragons:
    phase = d["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        d["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3), 0,
                                     d["root"].rotation_euler.z + math.sin(t * 0.8 + phase) * math.radians(5))
        d["root"].location.z = d["root"].location.z + math.sin(t * 1.2 + phase) * 0.10
        d["root"].keyframe_insert("rotation_euler", frame=f)
        d["root"].keyframe_insert("location", frame=f)
        # Fire breath pulse
        sc_f = 1 + abs(math.sin(t * 4.0 + phase)) * 1.0
        d["fire"].scale = (sc_f, sc_f, sc_f)
        d["fire"].keyframe_insert("scale", frame=f)
        # Head shake
        d["head"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0,
                                     math.cos(t * 1.5 + phase) * math.radians(15))
        d["head"].keyframe_insert("rotation_euler", frame=f)

# Knights sway
for k in knights:
    phase = k["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        k["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     k["root"].rotation_euler.z)
        k["root"].keyframe_insert("rotation_euler", frame=f)
        k["he"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(4), 0,
                                   math.cos(t * 1.0 + phase) * math.radians(15))
        k["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 scales fall + sway
for sc in scales:
    phase = sc["_phase"]; drift = sc["_drift"]; fall = sc["_fall"]; swing = sc["_swing"]
    bx, bz = sc["_base_x"], sc["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.7 + t * drift
        z = bz - (t * fall) % 20
        sc.location = (x, sc.location.y, z)
        sc.rotation_euler = (t * 2.0 + phase, math.sin(t * 2.5 + phase) * math.radians(30), t * 1.5 + phase)
        sc.keyframe_insert("location", frame=f)
        sc.keyframe_insert("rotation_euler", frame=f)

# 400 fairies float and blink
for fa in fairies:
    phase = fa["_phase"]; speed = fa["_speed"]; amp = fa["_amp"]; blink = fa["_blink"]
    bx, by, bz = fa["_base_x"], fa["_base_y"], fa["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * amp
        y = by + math.cos(t * speed * 0.9 + phase) * amp
        z = bz + math.sin(t * speed * 1.3 + phase) * 1.5
        fa.location = (x, y, z)
        # Blink scale
        sc_f = 0.4 + abs(math.sin(t * blink + phase)) * 1.2
        fa.scale = (sc_f, sc_f, sc_f)
        fa.keyframe_insert("location", frame=f)
        fa.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_wales_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_welsh_snowdonia_castle_dragons] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Wales Snowdonia: Caernarfon castle (signature rectangular keep + 4 round corner towers + crenellations + arrow slits + wooden door with iron rivets + portcullis + central keep tower) + Mt Snowdon 50m + 2 secondary peaks misty + 4 RED DRAGONS Y Ddraig Goch (signature long serpentine neck + horns + glowing yellow eyes + fire breath + bat-like wings with membranes + dorsal spikes + clawed legs + spiked tail with arrow tip) + 4 Welsh knights (full plate armor + helmets with visor and red plume + tabards red with white dragon + shields with red cross + long swords with gold hilts) + Celtic harp + 6 oak trees + Wales flag with signature red dragon on green/white + 600 dragon scales + 400 Celtic fairies blinking")
print("🐉 FIXES: 1 green prairie ground + 600 dragon scales + 400 Celtic fairies signature 🐉")
