"""
proc_jamaican_blue_mountains_coffee_plantation.py — 294e procédural AuroraIA (159e qualité)
Jamaica Blue Mountains coffee plantation: 8 coffee plants + 4 pickers with baskets + red plantation farm + Mt Blue Mountain + Jamaica flag + 600 coffee beans + 400 sapphire hummingbirds
FIXES : 1 ground mountain terraces + signature beans + hummingbirds
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB294)

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

# Sky tropical Jamaican
M_SKY = mat("sky", (0.42, 0.62, 0.85, 1.0), 0.0, 0.7, emission=(0.42,0.62,0.82), emission_strength=1.7)
M_SKY_LOW = mat("sky_l", (0.95, 0.78, 0.55, 1.0), 0.0, 0.7, emission=(0.92,0.78,0.55), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.85, 0.55, 1.0), 0.0, 0.1, emission=(1.0,0.85,0.55), emission_strength=15.0)
M_CLOUD = mat("cl", (0.95, 0.95, 0.92, 1.0), 0.0, 0.85, emission=(0.95,0.95,0.92), emission_strength=0.8, alpha=0.85)
M_MIST = mat("mi", (0.85, 0.92, 0.95, 1.0), 0.0, 0.95, emission=(0.85,0.92,0.95), emission_strength=1.0, alpha=0.45)

# Mountain terraces (signature Blue Mountains green)
M_TERRACE = mat("te", (0.32, 0.55, 0.30, 1.0), 0.0, 0.75, emission=(0.30,0.52,0.30), emission_strength=0.4)
M_TERRACE_DARK = mat("ted", (0.20, 0.38, 0.20, 1.0), 0.0, 0.85)
M_TERRACE_LIGHT = mat("tel", (0.45, 0.65, 0.35, 1.0), 0.0, 0.75, emission=(0.42,0.62,0.35), emission_strength=0.4)
M_DIRT = mat("d", (0.42, 0.28, 0.18, 1.0), 0.0, 0.92)
M_WALL_STONE = mat("ws", (0.55, 0.50, 0.42, 1.0), 0.0, 0.92)

# Mt Blue Mountain (signature deep blue mountain)
M_MOUNTAIN_BLUE = mat("mb", (0.20, 0.32, 0.55, 1.0), 0.0, 0.85, emission=(0.20,0.32,0.55), emission_strength=0.3)
M_MOUNTAIN_PURPLE = mat("mp", (0.32, 0.30, 0.55, 1.0), 0.0, 0.85, emission=(0.30,0.28,0.55), emission_strength=0.3)
M_MOUNTAIN_DARK = mat("md", (0.18, 0.22, 0.32, 1.0), 0.0, 0.92)
M_SNOW = mat("sn", (0.95, 0.95, 0.95, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.92), emission_strength=0.5)

# Coffee plant
M_COFFEE_LEAF = mat("cl", (0.20, 0.55, 0.22, 1.0), 0.0, 0.55, emission=(0.18,0.52,0.22), emission_strength=0.5)
M_COFFEE_LEAF_DARK = mat("cld", (0.12, 0.38, 0.15, 1.0), 0.0, 0.65)
M_COFFEE_STEM = mat("cs", (0.42, 0.28, 0.15, 1.0), 0.0, 0.85)
M_COFFEE_TRUNK = mat("ct", (0.55, 0.32, 0.18, 1.0), 0.0, 0.85, emission=(0.52,0.30,0.18), emission_strength=0.3)
# Coffee cherries (signature red ripe)
M_CHERRY_RED = mat("crr", (0.92, 0.18, 0.20, 1.0), 0.2, 0.30, emission=(0.88,0.18,0.20), emission_strength=1.0)
M_CHERRY_GREEN = mat("crg", (0.45, 0.65, 0.25, 1.0), 0.0, 0.55, emission=(0.42,0.62,0.25), emission_strength=0.5)
M_CHERRY_YELLOW = mat("cry", (0.95, 0.85, 0.30, 1.0), 0.0, 0.45, emission=(0.92,0.82,0.30), emission_strength=0.7)
CHERRY_COLORS = [M_CHERRY_RED, M_CHERRY_RED, M_CHERRY_GREEN, M_CHERRY_YELLOW]  # More red

# Coffee bean
M_BEAN_BROWN = mat("bb", (0.42, 0.22, 0.10, 1.0), 0.0, 0.65, emission=(0.40,0.22,0.10), emission_strength=0.5)
M_BEAN_LIGHT = mat("bbl", (0.62, 0.42, 0.20, 1.0), 0.0, 0.60, emission=(0.60,0.42,0.20), emission_strength=0.6)
M_BEAN_DARK = mat("bbd", (0.25, 0.12, 0.05, 1.0), 0.0, 0.75, emission=(0.25,0.12,0.05), emission_strength=0.4)
BEAN_COLORS = [M_BEAN_BROWN, M_BEAN_LIGHT, M_BEAN_DARK]

# Farm building (signature red Jamaican plantation house)
M_FARM_RED = mat("fr", (0.78, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.75,0.18,0.18), emission_strength=0.5)
M_FARM_WHITE = mat("fw", (0.92, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.88,0.88,0.85), emission_strength=0.4)
M_FARM_GREEN = mat("fg", (0.18, 0.45, 0.22, 1.0), 0.0, 0.65, emission=(0.18,0.42,0.22), emission_strength=0.4)
M_FARM_ROOF = mat("fr_r", (0.32, 0.18, 0.15, 1.0), 0.0, 0.85)
M_WOOD = mat("w", (0.55, 0.32, 0.15, 1.0), 0.0, 0.75)

# Picker clothing
M_SKIN_DARK = mat("sk", (0.42, 0.28, 0.18, 1.0), 0.0, 0.55, emission=(0.40,0.28,0.18), emission_strength=0.3)
M_HAIR_BLACK = mat("hb", (0.10, 0.08, 0.06, 1.0), 0.0, 0.85)
M_SHIRT_WHITE = mat("sw", (0.92, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.88,0.88,0.85), emission_strength=0.4)
M_SHIRT_YELLOW = mat("sy", (1.0, 0.85, 0.30, 1.0), 0.0, 0.55, emission=(0.95,0.82,0.30), emission_strength=0.5)
M_SHIRT_GREEN = mat("sg", (0.30, 0.55, 0.32, 1.0), 0.0, 0.55, emission=(0.30,0.52,0.30), emission_strength=0.5)
M_PANTS_BROWN = mat("pb", (0.42, 0.28, 0.18, 1.0), 0.0, 0.75)
M_PANTS_BLUE = mat("pbl", (0.20, 0.30, 0.55, 1.0), 0.0, 0.65)

# Straw hat
M_STRAW = mat("st_h", (0.85, 0.72, 0.42, 1.0), 0.0, 0.75, emission=(0.82,0.72,0.42), emission_strength=0.4)

# Basket (signature woven for coffee cherries)
M_BASKET_WOVEN = mat("bw_w", (0.65, 0.45, 0.20, 1.0), 0.0, 0.85, emission=(0.62,0.42,0.20), emission_strength=0.3)
M_BASKET_DARK = mat("bwd", (0.32, 0.20, 0.10, 1.0), 0.0, 0.92)

# Jamaica flag (signature)
M_FLAG_BLACK = mat("fb", (0.10, 0.10, 0.12, 1.0), 0.0, 0.45)
M_FLAG_GREEN = mat("fg_j", (0.18, 0.62, 0.30, 1.0), 0.0, 0.45, emission=(0.18,0.60,0.30), emission_strength=1.0)
M_FLAG_YELLOW = mat("fy_j", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.20), emission_strength=1.2)

# Sapphire hummingbird (signature Jamaican doctor bird streamertail)
M_HUMMING_GREEN = mat("hg", (0.30, 0.85, 0.45, 1.0), 0.4, 0.20, emission=(0.30,0.82,0.45), emission_strength=2.5)
M_HUMMING_BLUE = mat("hbl_b", (0.18, 0.45, 0.92, 1.0), 0.5, 0.10, emission=(0.18,0.45,0.90), emission_strength=3.0)
M_HUMMING_PURPLE = mat("hpu", (0.55, 0.30, 0.85, 1.0), 0.4, 0.20, emission=(0.52,0.30,0.82), emission_strength=2.8)
M_HUMMING_RED = mat("hr_b", (0.85, 0.20, 0.22, 1.0), 0.3, 0.30, emission=(0.82,0.20,0.22), emission_strength=2.0)
M_HUMMING_BEAK = mat("hbe", (0.18, 0.15, 0.13, 1.0), 0.2, 0.45)
HUMMING_COLORS = [M_HUMMING_GREEN, M_HUMMING_BLUE, M_HUMMING_PURPLE, M_HUMMING_RED]

# Coffee bean particles
M_BEAN_PT = mat("bnpt", (0.42, 0.22, 0.10, 1.0), 0.2, 0.35, emission=(0.40,0.22,0.10), emission_strength=1.8)
M_BEAN_PT_LIGHT = mat("bnptl", (0.62, 0.42, 0.20, 1.0), 0.2, 0.35, emission=(0.60,0.42,0.20), emission_strength=2.0)
M_BEAN_PT_DARK = mat("bnptd", (0.25, 0.12, 0.05, 1.0), 0.2, 0.45, emission=(0.25,0.12,0.05), emission_strength=1.5)
BEAN_PT_COLORS = [M_BEAN_PT, M_BEAN_PT_LIGHT, M_BEAN_PT_DARK]

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-50, 110, 35), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-50, 110, 35), mat_=M_SUN)
# Clouds
for ci in range(20):
    cx_c = random.uniform(-150, 150); cy_c = random.uniform(-100, 100); cz_c = random.uniform(45, 70)
    cloud_e = empty(f"cl{ci}_e", (cx_c, cy_c, cz_c))
    for cp in range(5):
        cpa = random.uniform(0, math.pi*2); cpr = random.uniform(0, 3)
        smooth_sphere(f"cl{ci}_p{cp}", r=random.uniform(2, 3.5), segs=14, rings=10,
                      loc=(math.cos(cpa)*cpr, math.sin(cpa)*cpr, random.uniform(-1, 1)),
                      parent=cloud_e, mat_=M_CLOUD, scale=(1.5, 1.5, 0.5))
# Morning mist over mountains
for mi in range(20):
    mx = random.uniform(-100, 100); my = random.uniform(20, 100); mz = random.uniform(20, 40)
    smooth_sphere(f"mst{mi}", r=random.uniform(2, 5), segs=12, rings=8,
                  loc=(mx, my, mz), mat_=M_MIST, scale=(2, 2, 0.5))

# ============ ONE clean mountain coffee terraces ground ============
ground = beveled_cube("ground", (260, 260, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_TERRACE)
# COFFEE TERRACES (signature stepped going up mountain)
terrace_e = empty("terraces", (0, 35, 0))
n_terraces = 10
for ti in range(n_terraces):
    tz = ti * 1.0
    tw = 90 - ti * 4
    td = 60 - ti * 3
    tr_col = M_TERRACE_LIGHT if ti % 2 else M_TERRACE
    # Terrace level
    beveled_cube(f"tr{ti}", (tw, td, 0.30), bevel_offset=0.06,
                 loc=(0, 0, tz + 0.15), parent=terrace_e, mat_=tr_col)
    # Stone retaining wall front
    beveled_cube(f"tr{ti}_w", (tw, 0.30, 1.0), bevel_offset=0.06,
                 loc=(0, td/2 - 0.15, tz + 0.50), parent=terrace_e, mat_=M_WALL_STONE)
    # Dirt patches
    for di in range(5):
        smooth_sphere(f"tr{ti}_d{di}", r=random.uniform(0.4, 0.7), segs=10, rings=6,
                      loc=(random.uniform(-tw/2 + 2, tw/2 - 2), random.uniform(-td/2 + 2, td/2 - 2), tz + 0.25),
                      parent=terrace_e, mat_=M_DIRT, scale=(1.4, 1.3, 0.15))

# General grass ground bumps
for hi in range(120):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 130)
    smooth_sphere(f"hl{hi}", r=random.uniform(0.8, 1.8), segs=10, rings=6,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_TERRACE_DARK if hi % 3 == 0 else M_TERRACE, scale=(1.4, 1.3, 0.18))

# ============ MT BLUE MOUNTAIN (signature blue distant peak) ============
def make_blue_mountain(name, loc, height, base_radius):
    base = empty(name, loc)
    n_layers = int(height / 4)
    for li in range(n_layers):
        lz = li * 4
        lr1 = base_radius * (1 - li / n_layers * 0.85)
        lr2 = base_radius * (1 - (li+1) / n_layers * 0.85)
        # Higher layers more purple/dark blue
        if li < n_layers * 0.3:
            mc = M_MOUNTAIN_DARK
        elif li < n_layers * 0.7:
            mc = M_MOUNTAIN_BLUE
        else:
            mc = M_MOUNTAIN_PURPLE
        smooth_cone(f"{name}_l{li}", r1=lr1, r2=lr2, depth=4.5, segs=18,
                    loc=(0, 0, lz + 2.25), parent=base, mat_=mc)
    # Peak
    smooth_cone(f"{name}_pk", r1=0.5, r2=0.05, depth=2, segs=12,
                loc=(0, 0, height - 0.5), parent=base, mat_=M_MOUNTAIN_PURPLE)
    return base

make_blue_mountain("mt_blue", (0, 110, 0), 50, 16)
make_blue_mountain("mt2", (-60, 100, 0), 38, 12)
make_blue_mountain("mt3", (55, 105, 0), 42, 13)

# ============ 8 COFFEE PLANT BUSHES (signature with red cherries) ============
def make_coffee_plant(name, loc, scale=1.0):
    base = empty(name, loc)
    # Trunk
    cyl(f"{name}_tr", r=0.10, depth=1.8, segs=10, loc=(0, 0, 0.9), parent=base, mat_=M_COFFEE_TRUNK)
    # 6 branches radiating
    for bi in range(6):
        ba = (bi / 6.0) * math.pi * 2
        branch_e = empty(f"{name}_b{bi}_e", (0, 0, 0.6 + bi*0.15), parent=base)
        branch_e.rotation_euler = (math.radians(20), 0, ba)
        cyl(f"{name}_b{bi}", r=0.04, depth=1.5, segs=8, loc=(0, 0, 0.75),
            parent=branch_e, mat_=M_COFFEE_STEM)
        # Leaves along branch (signature glossy)
        for li in range(8):
            li_t = li / 8.0
            for ls in (-1, 1):
                lz = li * 0.18
                beveled_cube(f"{name}_lf{bi}_{li}_{ls}", (0.05, 0.20, 0.03), bevel_offset=0.005,
                             loc=(ls*0.10, 0, 0.15 + lz), parent=branch_e,
                             mat_=M_COFFEE_LEAF if li % 2 == 0 else M_COFFEE_LEAF_DARK).rotation_euler = (0, 0, math.radians(ls*20))
        # COFFEE CHERRIES clusters (signature red berries)
        for ci_b in range(6):
            ci_t = ci_b / 6.0
            cz_b = ci_t * 1.4
            cherry_col = random.choice(CHERRY_COLORS)
            # Cluster of 2-3 cherries
            for cn in range(random.randint(2, 4)):
                cna = (cn / 3.0) * math.pi * 2
                smooth_sphere(f"{name}_ch{bi}_{ci_b}_{cn}", r=0.04, segs=10, rings=8,
                              loc=(math.cos(cna)*0.06 - 0.10, 0, cz_b),
                              parent=branch_e, mat_=cherry_col)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base}

coffee_plants = []
coffee_pos = [(-20, 20, 4), (-10, 22, 5), (0, 20, 4), (10, 22, 5),
               (20, 20, 4), (-15, 30, 6), (15, 30, 6), (0, 35, 7)]
for i, (cpx, cpy, cpz) in enumerate(coffee_pos):
    cp = make_coffee_plant(f"cf{i}", (cpx, cpy, cpz))
    coffee_plants.append(cp)

# ============ PLANTATION FARM HOUSE (signature red Jamaican) ============
farm_e = empty("farm", (-30, -5, 0))
# Main building
beveled_cube("fa_b", (8, 6, 4), bevel_offset=0.12, loc=(0, 0, 2),
             parent=farm_e, mat_=M_FARM_RED)
# White trim/details (signature gingerbread style)
for ti_t in range(4):
    beveled_cube(f"fa_tr{ti_t}", (8.05, 0.05, 0.20), bevel_offset=0.02,
                 loc=(0, -3.05, 0.5 + ti_t*1.0), parent=farm_e, mat_=M_FARM_WHITE)
# Veranda/porch (signature)
beveled_cube("fa_v", (10, 2, 0.30), bevel_offset=0.06, loc=(0, -3.5, 0.30),
             parent=farm_e, mat_=M_WOOD)
# Veranda posts
for pi in range(6):
    cyl(f"fa_vp{pi}", r=0.10, depth=2, segs=10, loc=(-4.5 + pi*1.8, -4.5, 1.3),
        parent=farm_e, mat_=M_FARM_WHITE)
# Veranda railing
beveled_cube("fa_vr", (10, 0.06, 0.4), bevel_offset=0.04, loc=(0, -4.5, 0.80),
             parent=farm_e, mat_=M_FARM_WHITE)
# Pitched roof (signature)
roof_e = empty("fa_re", (0, 0, 4.2), parent=farm_e)
for ri in range(8):
    ri_t = ri / 8.0
    rw = 8.5 * (1 - ri_t * 0.8)
    rd = 6.5 - ri * 0.4
    beveled_cube(f"fa_r{ri}", (rw, rd, 0.30), bevel_offset=0.04,
                 loc=(0, 0, ri*0.40), parent=roof_e, mat_=M_FARM_ROOF)
# Chimney
beveled_cube("fa_ch", (0.8, 0.8, 2), bevel_offset=0.08, loc=(2.5, 1, 5.5),
             parent=farm_e, mat_=M_FARM_RED)
# Windows
for wi in (-1, 1):
    beveled_cube(f"fa_w{wi}", (1.5, 0.06, 1.5), bevel_offset=0.04,
                 loc=(wi*2.5, -3.10, 2.5), parent=farm_e, mat_=M_FARM_WHITE)
    # Window frame
    for wxi in (-1, 1):
        beveled_cube(f"fa_wx{wi}_{wxi}", (0.04, 0.08, 1.5), bevel_offset=0.01,
                     loc=(wi*2.5 + wxi*0.7, -3.12, 2.5), parent=farm_e, mat_=M_WOOD)
    beveled_cube(f"fa_wxc{wi}", (1.5, 0.08, 0.04), bevel_offset=0.01,
                 loc=(wi*2.5, -3.12, 2.5), parent=farm_e, mat_=M_WOOD)
# Door (signature green)
beveled_cube("fa_d", (1.0, 0.08, 2.2), bevel_offset=0.05, loc=(0, -3.05, 1.4),
             parent=farm_e, mat_=M_FARM_GREEN)
# Sign "Blue Mountain Coffee"
beveled_cube("fa_sg", (3.5, 0.06, 0.5), bevel_offset=0.04, loc=(0, -3.10, 3.5),
             parent=farm_e, mat_=M_WOOD)

# Drying racks for coffee beans (signature)
def make_drying_rack(name, loc):
    base = empty(name, loc)
    # Wooden frame
    for ci in range(4):
        ca = (ci / 4.0) * math.pi * 2 + math.pi/4
        cyl(f"{name}_p{ci}", r=0.08, depth=1.2, segs=8,
            loc=(math.cos(ca)*1, math.sin(ca)*0.75, 0.6), parent=base, mat_=M_WOOD)
    # Top surface with beans
    beveled_cube(f"{name}_t", (2, 1.5, 0.10), bevel_offset=0.04, loc=(0, 0, 1.2),
                 parent=base, mat_=M_WOOD)
    # Drying beans
    for bi_d in range(40):
        bx = random.uniform(-0.85, 0.85); by = random.uniform(-0.65, 0.65)
        smooth_sphere(f"{name}_b{bi_d}", r=0.04, segs=8, rings=6,
                      loc=(bx, by, 1.28), parent=base, mat_=random.choice(BEAN_COLORS),
                      scale=(1, 0.7, 0.5))
    return base

for i, (rx, ry) in enumerate([(-20, -8), (-10, -8)]):
    make_drying_rack(f"dr{i}", (rx, ry, 0))

# ============ 4 COFFEE PICKERS with BASKETS (signature) ============
def make_picker(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    shirt_col = random.choice([M_SHIRT_WHITE, M_SHIRT_YELLOW, M_SHIRT_GREEN])
    # Shirt
    smooth_cone(f"{name}_sh", r1=0.30, r2=0.33, depth=0.75, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=shirt_col)
    # Pants
    pants_col = random.choice([M_PANTS_BROWN, M_PANTS_BLUE])
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.11, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=pants_col)
    # Sandals
    for side in (-1, 1):
        beveled_cube(f"{name}_sd{side}", (0.10, 0.22, 0.05), bevel_offset=0.01,
                     loc=(side*0.13, 0.04, 0.03), parent=base, mat_=M_BASKET_DARK)
    # Arms (one reaching toward plants, one holding basket)
    sh_l = empty(f"{name}_a0", (-0.30, 0, 1.55), parent=base)
    sh_l.rotation_euler = (math.radians(-100), 0, math.radians(30))
    cyl(f"{name}_ua0", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=shirt_col)
    cyl(f"{name}_fa0", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_SKIN_DARK)
    sh_r = empty(f"{name}_a1", (0.30, 0, 1.55), parent=base)
    sh_r.rotation_euler = (math.radians(-50), 0, math.radians(-15))
    cyl(f"{name}_ua1", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=shirt_col)
    cyl(f"{name}_fa1", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_SKIN_DARK)
    # BASKET on hip/back (signature woven for coffee cherries)
    basket_e = empty(f"{name}_bk", (0, 0.35, 1.0), parent=base)
    # Basket body
    cyl(f"{name}_bk_b", r=0.30, depth=0.50, segs=14, loc=(0, 0, 0),
        parent=basket_e, mat_=M_BASKET_WOVEN)
    # Woven pattern lines
    for bli in range(5):
        cyl(f"{name}_bk_bl{bli}", r=0.31, depth=0.04, segs=14, loc=(0, 0, -0.20 + bli*0.10),
            parent=basket_e, mat_=M_BASKET_DARK)
    # Cherries inside basket (signature red)
    for cb in range(15):
        cba = random.uniform(0, math.pi*2); cbr = random.uniform(0, 0.20)
        smooth_sphere(f"{name}_bk_c{cb}", r=0.04, segs=8, rings=6,
                      loc=(math.cos(cba)*cbr, math.sin(cba)*cbr, 0.20),
                      parent=basket_e, mat_=M_CHERRY_RED)
    # Basket strap
    cyl(f"{name}_bk_st", r=0.04, depth=0.50, segs=8, loc=(0, -0.30, 0.30),
        parent=basket_e, mat_=M_BASKET_DARK).rotation_euler = (math.radians(70), 0, 0)
    # Head
    head_p_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_p_e, mat_=M_SKIN_DARK)
    # Hair short black
    for hi in range(10):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.06, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.10),
            parent=head_p_e, mat_=M_HAIR_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_p_e, mat_=M_EYE)
    # STRAW HAT (signature)
    hat_e = empty(f"{name}_ha", (0, 0, 0.20), parent=head_p_e)
    cyl(f"{name}_ha_c", r=0.18, depth=0.15, segs=14, loc=(0, 0, 0),
        parent=hat_e, mat_=M_STRAW)
    cyl(f"{name}_ha_b", r=0.32, depth=0.04, segs=18, loc=(0, 0, -0.08),
        parent=hat_e, mat_=M_STRAW)
    # Hat band (red/yellow Jamaica)
    cyl(f"{name}_ha_bd", r=0.19, depth=0.04, segs=14, loc=(0, 0, -0.04),
        parent=hat_e, mat_=M_FARM_RED)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_p_e}

pickers = []
picker_pos = [(-15, 18, 4, math.radians(0)), (-3, 20, 4, math.radians(45)),
               (8, 20, 4, math.radians(-30)), (18, 18, 4, math.radians(90))]
for i, (px, py, pz, fac) in enumerate(picker_pos):
    p = make_picker(f"pk{i}", (px, py, pz), facing=fac)
    pickers.append(p)

# ============ JAMAICA FLAG main (signature) ============
flag_e = empty("flag", (-50, -25, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_WOOD)
# Yellow X diagonal cross (signature)
for diag in (0, 1):
    diag_e = empty(f"fl_d{diag}_e", (2, -0.05, 10.5), parent=flag_e)
    diag_e.rotation_euler = (0, math.radians(30 if diag == 0 else -30), 0)
    beveled_cube(f"fl_d{diag}", (5, 0.05, 0.45), bevel_offset=0.04,
                 loc=(0, 0, 0), parent=diag_e, mat_=M_FLAG_YELLOW)
# Top and bottom triangles green (signature)
beveled_cube("fl_g_t", (4, 0.05, 0.85), bevel_offset=0.04, loc=(2, 0, 11.45),
             parent=flag_e, mat_=M_FLAG_GREEN)
beveled_cube("fl_g_b", (4, 0.05, 0.85), bevel_offset=0.04, loc=(2, 0, 9.65),
             parent=flag_e, mat_=M_FLAG_GREEN)
# Left and right triangles black (signature)
left_e = empty("fl_bk_l", (0.7, -0.06, 10.5), parent=flag_e)
for ti in range(8):
    tw = 1.4 - ti * 0.18
    beveled_cube(f"fl_bk_l_t{ti}", (tw, 0.05, 0.20), bevel_offset=0.02,
                 loc=(0, 0, (ti - 4) * 0.20), parent=left_e, mat_=M_FLAG_BLACK)
right_e = empty("fl_bk_r", (3.3, -0.06, 10.5), parent=flag_e)
for ti in range(8):
    tw = 1.4 - ti * 0.18
    beveled_cube(f"fl_bk_r_t{ti}", (tw, 0.05, 0.20), bevel_offset=0.02,
                 loc=(0, 0, (ti - 4) * 0.20), parent=right_e, mat_=M_FLAG_BLACK)
flag_e["_phase"] = 0

# ============================================================
# 600 COFFEE BEANS + 400 SAPPHIRE HUMMINGBIRDS (PARTICULES SIGNATURES)
# ============================================================
beans = []
for i in range(600):
    px = random.uniform(-110, 110)
    py = random.uniform(-100, 100)
    pz = random.uniform(2, 22)
    b_col = random.choice(BEAN_PT_COLORS)
    # Coffee bean shape (oval with center groove)
    b_e = empty(f"bn{i}", (px, py, pz))
    smooth_sphere(f"bn{i}_b", r=0.08, segs=10, rings=8, loc=(0, 0, 0),
                  parent=b_e, mat_=b_col, scale=(1, 0.5, 0.55))
    # Groove (signature)
    beveled_cube(f"bn{i}_g", (0.01, 0.08, 0.005), bevel_offset=0.002,
                 loc=(0, 0, 0.04), parent=b_e, mat_=M_BEAN_PT_DARK)
    b_e["_phase"] = random.uniform(0, math.pi*2)
    b_e["_base_x"] = px; b_e["_base_y"] = py; b_e["_base_z"] = pz
    b_e["_amp_x"] = random.uniform(0.5, 1.5)
    b_e["_amp_y"] = random.uniform(0.5, 1.5)
    b_e["_amp_z"] = random.uniform(0.4, 1.0)
    b_e["_speed"] = random.uniform(0.4, 1.0)
    beans.append(b_e)

# 400 sapphire hummingbirds (signature Jamaican doctor bird streamertail)
hummingbirds = []
for i in range(400):
    px = random.uniform(-110, 110)
    py = random.uniform(-100, 100)
    pz = random.uniform(3, 28)
    hb_col = random.choice(HUMMING_COLORS)
    hb_e = empty(f"hb{i}", (px, py, pz))
    # Body (small iridescent)
    smooth_sphere(f"hb{i}_b", r=0.07, segs=10, rings=8, loc=(0, 0, 0),
                  parent=hb_e, mat_=hb_col, scale=(1.3, 0.85, 0.85))
    # Head
    smooth_sphere(f"hb{i}_h", r=0.05, segs=8, rings=6, loc=(0.08, 0, 0.02),
                  parent=hb_e, mat_=hb_col)
    # LONG SLENDER BEAK (signature)
    cyl(f"hb{i}_bk", r=0.008, depth=0.12, segs=6, loc=(0.18, 0, 0),
        parent=hb_e, mat_=M_HUMMING_BEAK).rotation_euler = (0, math.radians(95), 0)
    # Wings (signature blur for fast flap)
    wing_e_l = empty(f"hb{i}_wl_e", (0, -0.04, 0), parent=hb_e)
    wing_e_r = empty(f"hb{i}_wr_e", (0, 0.04, 0), parent=hb_e)
    beveled_cube(f"hb{i}_wl", (0.06, 0.18, 0.01), bevel_offset=0.005, loc=(0, -0.10, 0),
                 parent=wing_e_l, mat_=hb_col)
    beveled_cube(f"hb{i}_wr", (0.06, 0.18, 0.01), bevel_offset=0.005, loc=(0, 0.10, 0),
                 parent=wing_e_r, mat_=hb_col)
    # LONG STREAMER TAIL FEATHERS (signature Jamaican streamertail)
    for ti in range(3):
        beveled_cube(f"hb{i}_t{ti}", (0.02 - ti*0.005, 0.35 - ti*0.05, 0.008), bevel_offset=0.003,
                     loc=(-0.20 - ti*0.05, (ti-1)*0.02, 0), parent=hb_e, mat_=hb_col)
    hb_e["_phase"] = random.uniform(0, math.pi*2)
    hb_e["_base_x"] = px; hb_e["_base_y"] = py; hb_e["_base_z"] = pz
    hb_e["_speed"] = random.uniform(0.8, 2.0)
    hb_e["_radius"] = random.uniform(3, 10)
    hb_e["_wl"] = wing_e_l; hb_e["_wr"] = wing_e_r
    hummingbirds.append(hb_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Coffee plants sway
for cp in coffee_plants:
    phase = cp["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        cp["root"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3),
                                      math.cos(t * 0.8 + phase) * math.radians(3), 0)
        cp["root"].keyframe_insert("rotation_euler", frame=f)

# Pickers work
for p in pickers:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        p["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(8), 0,
                                     p["root"].rotation_euler.z + math.sin(t * 1.0 + phase) * math.radians(5))
        p["root"].keyframe_insert("rotation_euler", frame=f)
        p["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(10), 0,
                                   math.cos(t * 1.2 + phase) * math.radians(15))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 beans float multi-axis
for b in beans:
    phase = b["_phase"]; speed = b["_speed"]
    bx, by, bz = b["_base_x"], b["_base_y"], b["_base_z"]
    ax, ay, az = b["_amp_x"], b["_amp_y"], b["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase) + t * 0.3
        b.location = (x, y, z)
        b.rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(20), 0,
                             t * 1.0 + phase)
        b.keyframe_insert("location", frame=f)
        b.keyframe_insert("rotation_euler", frame=f)

# 400 hummingbirds dart with rapid wing flap
for hb in hummingbirds:
    phase = hb["_phase"]; speed = hb["_speed"]; radius = hb["_radius"]
    bx, by, bz = hb["_base_x"], hb["_base_y"], hb["_base_z"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * radius
        y = by + math.sin(t * speed + phase) * radius
        z = bz + math.sin(t * speed * 1.5 + phase) * 1.5
        hb.location = (x, y, z)
        hb.rotation_euler = (0, 0, math.atan2(math.cos(t * speed + phase),
                                                -math.sin(t * speed + phase)))
        hb.keyframe_insert("location", frame=f)
        hb.keyframe_insert("rotation_euler", frame=f)
        # FAST wing flap (signature hummingbird)
        wing_a = math.sin(t * 30.0 + phase) * math.radians(60)
        hb["_wl"].rotation_euler = (0, wing_a, 0)
        hb["_wr"].rotation_euler = (0, -wing_a, 0)
        hb["_wl"].keyframe_insert("rotation_euler", frame=f)
        hb["_wr"].keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_jamaica_coffee_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_jamaican_blue_mountains_coffee_plantation] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Jamaica Blue Mountains coffee: signature 10-level coffee terraces with stone retaining walls + 8 coffee plant bushes (signature 6 radiating branches + glossy leaves + RED CHERRY clusters) + signature red plantation farm house with white gingerbread trim + green door + veranda with 6 posts + pitched roof + chimney + 'Blue Mountain Coffee' sign + 2 drying racks with 40 beans each + 4 coffee pickers (signature straw hats + colorful shirts + woven baskets with red cherries on hips) + Mt Blue Mountain 50m signature deep blue/purple mountain + 2 secondary peaks + morning mist + Jamaica flag with X-cross signature + 600 coffee beans floating + 400 sapphire hummingbirds (signature Jamaican doctor bird with iridescent green/blue/purple/red bodies + LONG streamer tail feathers + slender beaks + rapid wing flap)")
print("☕ FIXES: 1 mountain terraces ground + 600 coffee beans + 400 sapphire hummingbirds signature ☕")
