"""
proc_yellowstone_geysers_bison_wolves.py — 287e procédural AuroraIA (152e qualité)
Yellowstone geysers bisons wolves: Old Faithful + Grand Prismatic colored springs + 6 bisons + 4 wolves + ranger cabin + Mt Sheridan + USA flag + 600 mineral droplets + 400 thermal sparkles
FIXES : 1 ground volcanic prairie + signature mineral + sparkles
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB287)

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

# Sky
M_SKY = mat("sky", (0.55, 0.72, 0.92, 1.0), 0.0, 0.7, emission=(0.55,0.70,0.90), emission_strength=1.7)
M_SKY_LOW = mat("sky_l", (0.85, 0.92, 0.95, 1.0), 0.0, 0.7, emission=(0.85,0.90,0.92), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.92, 0.55, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.55), emission_strength=15.0)
M_CLOUD = mat("cl", (0.95, 0.95, 0.92, 1.0), 0.0, 0.85, emission=(0.95,0.95,0.92), emission_strength=1.0, alpha=0.85)

# Volcanic prairie
M_PRAIRIE = mat("pr", (0.55, 0.62, 0.32, 1.0), 0.0, 0.75, emission=(0.52,0.60,0.32), emission_strength=0.4)
M_PRAIRIE_DARK = mat("prd", (0.32, 0.42, 0.22, 1.0), 0.0, 0.85)
M_VOLCANIC_ROCK = mat("vr", (0.42, 0.32, 0.28, 1.0), 0.0, 0.92)
M_MINERAL_WHITE = mat("mw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.90), emission_strength=0.6)
M_MINERAL_YELLOW = mat("my", (0.92, 0.78, 0.30, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.30), emission_strength=0.8)

# Geothermal pool colors (signature Grand Prismatic)
M_POOL_CENTER = mat("pc", (0.18, 0.78, 0.92, 1.0), 0.1, 0.10, emission=(0.18,0.75,0.90), emission_strength=2.5, alpha=0.85)
M_POOL_BLUE = mat("pb", (0.30, 0.65, 0.92, 1.0), 0.1, 0.15, emission=(0.30,0.65,0.92), emission_strength=2.0, alpha=0.85)
M_POOL_GREEN = mat("pg", (0.65, 0.92, 0.55, 1.0), 0.1, 0.15, emission=(0.62,0.92,0.55), emission_strength=2.0, alpha=0.80)
M_POOL_YELLOW = mat("pyl", (0.95, 0.85, 0.30, 1.0), 0.1, 0.15, emission=(0.92,0.82,0.30), emission_strength=2.2, alpha=0.80)
M_POOL_ORANGE = mat("po", (1.0, 0.65, 0.18, 1.0), 0.1, 0.15, emission=(0.95,0.65,0.18), emission_strength=2.5, alpha=0.85)
M_POOL_RED = mat("prd2", (0.92, 0.30, 0.20, 1.0), 0.1, 0.15, emission=(0.88,0.30,0.20), emission_strength=2.0, alpha=0.85)
M_POOL_RIM = mat("prim", (0.85, 0.72, 0.55, 1.0), 0.0, 0.75)

# Old Faithful water
M_WATER_STEAM = mat("wst", (0.92, 0.95, 0.98, 1.0), 0.0, 0.10, emission=(0.90,0.95,0.98), emission_strength=2.8, alpha=0.78)
M_WATER_HOT = mat("wht", (0.85, 0.95, 1.0, 1.0), 0.0, 0.10, emission=(0.82,0.92,0.98), emission_strength=3.2, alpha=0.70)
M_STEAM = mat("stm", (0.95, 0.95, 0.95, 1.0), 0.0, 0.95, emission=(0.95,0.95,0.95), emission_strength=1.5, alpha=0.45)

# Mountains
M_MOUNTAIN_GRAY = mat("mg", (0.55, 0.55, 0.55, 1.0), 0.0, 0.85)
M_MOUNTAIN_DARK = mat("md", (0.32, 0.32, 0.35, 1.0), 0.0, 0.92)
M_SNOW = mat("sn", (0.95, 0.95, 0.95, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.92), emission_strength=0.5)

# Bison (signature American)
M_BISON_BROWN = mat("bb", (0.42, 0.28, 0.18, 1.0), 0.0, 0.85, emission=(0.40,0.28,0.18), emission_strength=0.3)
M_BISON_DARK = mat("bbd", (0.22, 0.15, 0.10, 1.0), 0.0, 0.92)
M_BISON_HUMP = mat("bbh", (0.55, 0.38, 0.22, 1.0), 0.0, 0.85, emission=(0.52,0.38,0.22), emission_strength=0.3)
M_BISON_HORN = mat("bbhrn", (0.32, 0.28, 0.22, 1.0), 0.2, 0.55)

# Wolf
M_WOLF_GRAY = mat("wg", (0.55, 0.55, 0.55, 1.0), 0.0, 0.85, emission=(0.52,0.52,0.52), emission_strength=0.3)
M_WOLF_DARK = mat("wgd", (0.28, 0.28, 0.30, 1.0), 0.0, 0.92)
M_WOLF_WHITE = mat("ww", (0.92, 0.90, 0.85, 1.0), 0.0, 0.75, emission=(0.88,0.88,0.85), emission_strength=0.4)

# Ranger cabin (signature log)
M_LOG_BROWN = mat("lb", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85, emission=(0.52,0.30,0.15), emission_strength=0.3)
M_LOG_DARK = mat("ld", (0.32, 0.18, 0.10, 1.0), 0.0, 0.92)
M_ROOF_DARK = mat("rd", (0.18, 0.12, 0.08, 1.0), 0.0, 0.85)
M_WINDOW_GLOW = mat("wgw", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(0.95,0.82,0.30), emission_strength=5.0)
M_DOOR = mat("dr", (0.42, 0.22, 0.12, 1.0), 0.0, 0.75)

# USA flag
M_FLAG_RED = mat("fr", (0.78, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.75,0.18,0.20), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_FLAG_BLUE = mat("fb", (0.18, 0.22, 0.55, 1.0), 0.0, 0.45, emission=(0.18,0.22,0.52), emission_strength=1.0)
M_FLAG_STAR = mat("fs", (0.95, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.88), emission_strength=2.0)

# Trees (lodgepole pine)
M_PINE_DARK = mat("pd", (0.18, 0.35, 0.18, 1.0), 0.0, 0.75)
M_TRUNK = mat("tk", (0.42, 0.28, 0.18, 1.0), 0.0, 0.85)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_GOLD = mat("egl", (0.95, 0.85, 0.20, 1.0), 0.0, 0.20, emission=(0.92,0.82,0.20), emission_strength=2.5)

# Mineral droplet
M_DROP = mat("dp", (0.92, 0.95, 1.0, 1.0), 0.0, 0.10, emission=(0.90,0.92,0.98), emission_strength=2.5, alpha=0.65)
M_DROP_BLUE = mat("dpb", (0.55, 0.85, 0.95, 1.0), 0.0, 0.10, emission=(0.52,0.82,0.92), emission_strength=2.2, alpha=0.55)

# Thermal sparkle
M_SPARKLE_YELLOW = mat("sky2", (1.0, 0.92, 0.30, 1.0), 0.5, 0.05, emission=(0.95,0.88,0.30), emission_strength=4.0)
M_SPARKLE_ORANGE = mat("sko", (1.0, 0.65, 0.18, 1.0), 0.5, 0.05, emission=(0.95,0.62,0.18), emission_strength=3.5)
M_SPARKLE_WHITE = mat("skw", (0.98, 0.98, 0.92, 1.0), 0.5, 0.05, emission=(0.95,0.95,0.90), emission_strength=4.5)
SPARKLE_COLORS = [M_SPARKLE_YELLOW, M_SPARKLE_ORANGE, M_SPARKLE_WHITE]

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(40, 110, 40), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(40, 110, 40), mat_=M_SUN)
# Clouds
for ci in range(15):
    cx_c = random.uniform(-150, 150); cy_c = random.uniform(-150, 150); cz_c = random.uniform(50, 70)
    cloud_e = empty(f"cl{ci}_e", (cx_c, cy_c, cz_c))
    for cp in range(5):
        cpa = random.uniform(0, math.pi*2); cpr = random.uniform(0, 3)
        smooth_sphere(f"cl{ci}_p{cp}", r=random.uniform(2, 3.5), segs=14, rings=10,
                      loc=(math.cos(cpa)*cpr, math.sin(cpa)*cpr, random.uniform(-1, 1)),
                      parent=cloud_e, mat_=M_CLOUD, scale=(1.5, 1.5, 0.5))

# ============ ONE clean volcanic prairie ground ============
ground = beveled_cube("ground", (280, 280, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_PRAIRIE)
# Prairie bumps
for hi in range(180):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 130)
    smooth_sphere(f"hl{hi}", r=random.uniform(1.5, 3), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_PRAIRIE_DARK if hi % 3 == 0 else M_PRAIRIE, scale=(1.5, 1.4, 0.20))
# Volcanic rocks
for ri in range(50):
    a = random.uniform(0, math.pi*2); rad = random.uniform(20, 110)
    smooth_sphere(f"rk{ri}", r=random.uniform(0.4, 0.9), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.12),
                  mat_=M_VOLCANIC_ROCK, scale=(1.4, 1.3, 0.3))
# Mineral deposits (white/yellow)
for mi in range(70):
    a = random.uniform(0, math.pi*2); rad = random.uniform(30, 100)
    smooth_sphere(f"md{mi}", r=random.uniform(0.6, 1.2), segs=10, rings=6,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_MINERAL_YELLOW if mi % 2 else M_MINERAL_WHITE, scale=(1.4, 1.3, 0.15))

# ============ MT SHERIDAN backdrop (signature) ============
def make_mountain(name, loc, height, base_radius):
    base = empty(name, loc)
    n_layers = int(height / 4)
    for li in range(n_layers):
        lz = li * 4
        lr1 = base_radius * (1 - li / n_layers * 0.85)
        lr2 = base_radius * (1 - (li+1) / n_layers * 0.85)
        smooth_cone(f"{name}_l{li}", r1=lr1, r2=lr2, depth=4.5, segs=18,
                    loc=(0, 0, lz + 2.25), parent=base,
                    mat_=M_MOUNTAIN_DARK if li < n_layers//2 else M_MOUNTAIN_GRAY)
    # Snow cap
    snow_e = empty(f"{name}_se", (0, 0, height * 0.55), parent=base)
    for si in range(5):
        sz = si * 3
        sr = base_radius * (0.5 - si / 5 * 0.4)
        smooth_cone(f"{name}_s{si}", r1=sr + 0.3, r2=sr - 0.1, depth=3, segs=16,
                    loc=(0, 0, sz), parent=snow_e, mat_=M_SNOW)
    smooth_cone(f"{name}_pk", r1=0.4, r2=0.04, depth=2, segs=12,
                loc=(0, 0, height - 0.5), parent=base, mat_=M_SNOW)
    return base

make_mountain("mt_sheridan", (0, 90, 0), 50, 14)
make_mountain("mt2", (-50, 80, 0), 35, 11)
make_mountain("mt3", (55, 85, 0), 38, 12)

# ============ OLD FAITHFUL GEYSER (signature) ============
faithful_e = empty("faithful", (0, 0, 0))
# Mineral mound base
cyl("of_b", r=4, depth=0.40, segs=22, loc=(0, 0, 0.20), parent=faithful_e, mat_=M_MINERAL_WHITE)
# Inner crater
cyl("of_c", r=2.5, depth=0.30, segs=22, loc=(0, 0, 0.30), parent=faithful_e, mat_=M_MINERAL_YELLOW)
# Hole
cyl("of_h", r=1.0, depth=0.10, segs=18, loc=(0, 0, 0.40), parent=faithful_e, mat_=M_VOLCANIC_ROCK)
# WATER JET (signature shooting up high)
jet_e = empty("of_j", (0, 0, 0.45), parent=faithful_e)
# Stacked water columns (animatable)
for ji in range(25):
    jz = ji * 0.8
    jr = 0.50 - ji * 0.015
    jw_col = M_WATER_HOT if ji < 8 else M_WATER_STEAM
    smooth_sphere(f"of_j{ji}", r=max(0.08, jr), segs=12, rings=8,
                  loc=(random.uniform(-0.15, 0.15), random.uniform(-0.15, 0.15), jz),
                  parent=jet_e, mat_=jw_col, scale=(1, 1, 1.6))
# Steam cloud at top
for sti in range(12):
    sta = random.uniform(0, math.pi*2); str_r = random.uniform(0, 2.5)
    smooth_sphere(f"of_st{sti}", r=random.uniform(0.8, 1.5), segs=12, rings=8,
                  loc=(math.cos(sta)*str_r, math.sin(sta)*str_r, 18 + random.uniform(0, 3)),
                  parent=faithful_e, mat_=M_STEAM)
faithful_e["_phase"] = 0
faithful_e["_jet"] = jet_e

# ============ 4 GRAND PRISMATIC SPRING POOLS (signature concentric colors) ============
def make_prismatic_pool(name, loc, scale=1.0):
    base = empty(name, loc)
    # Outer rim
    cyl(f"{name}_rim", r=5.0, depth=0.20, segs=22, loc=(0, 0, 0.10),
        parent=base, mat_=M_POOL_RIM)
    # Concentric color rings (signature)
    rings_data = [(4.5, M_POOL_RED), (4.0, M_POOL_ORANGE), (3.5, M_POOL_YELLOW),
                   (2.8, M_POOL_GREEN), (2.0, M_POOL_BLUE), (1.0, M_POOL_CENTER)]
    for ri, (rr, rcol) in enumerate(rings_data):
        cyl(f"{name}_r{ri}", r=rr, depth=0.30 - ri*0.015, segs=22,
            loc=(0, 0, 0.20 + ri*0.02), parent=base, mat_=rcol)
    # Steam rising (signature)
    for sti in range(8):
        sta = random.uniform(0, math.pi*2); str_r = random.uniform(0, 3)
        smooth_sphere(f"{name}_st{sti}", r=random.uniform(0.6, 1.0), segs=10, rings=8,
                      loc=(math.cos(sta)*str_r, math.sin(sta)*str_r, random.uniform(2, 4)),
                      parent=base, mat_=M_STEAM)
    return base

pool_pos = [(-25, -15), (25, -15), (-30, 25), (30, 25)]
for i, (px, py) in enumerate(pool_pos):
    make_prismatic_pool(f"pool{i}", (px, py, 0))

# ============ 6 AMERICAN BISONS (signature massive) ============
def make_bison(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_bo", r=0.9, segs=14, rings=12, loc=(0, 0, 1.30),
                  parent=base, mat_=M_BISON_BROWN, scale=(1.6, 0.85, 0.85))
    # MASSIVE HUMP (signature shoulder hump)
    smooth_sphere(f"{name}_hu", r=0.55, segs=14, rings=12, loc=(0.55, 0, 1.85),
                  parent=base, mat_=M_BISON_HUMP, scale=(1.0, 0.85, 1.0))
    # Belly darker
    smooth_sphere(f"{name}_be", r=0.85, segs=12, rings=10, loc=(0, 0, 0.95),
                  parent=base, mat_=M_BISON_DARK, scale=(1.5, 0.85, 0.5))
    # Head (signature huge with thick fur)
    head_b_e = empty(f"{name}_he", (1.30, 0, 1.45), parent=base)
    smooth_sphere(f"{name}_h", r=0.45, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_b_e, mat_=M_BISON_DARK, scale=(1.3, 0.95, 1.0))
    # SHAGGY BEARD signature
    for bi in range(15):
        ba = random.uniform(-math.pi*0.4, math.pi*0.4)
        smooth_sphere(f"{name}_bd{bi}", r=0.10,
                      loc=(math.sin(ba)*0.20, -0.20, -0.15 - random.uniform(0, 0.20)),
                      parent=head_b_e, mat_=M_BISON_DARK)
    # Snout
    smooth_sphere(f"{name}_sn", r=0.20, segs=12, rings=10, loc=(0.25, 0, -0.10),
                  parent=head_b_e, mat_=M_BISON_BROWN)
    # HORNS (signature curved short)
    for side in (-1, 1):
        horn_e = empty(f"{name}_hn{side}_e", (-0.10, side*0.30, 0.20), parent=head_b_e)
        horn_e.rotation_euler = (0, math.radians(side*30), 0)
        cyl(f"{name}_hn{side}", r=0.06, depth=0.30, segs=10, loc=(0, 0, 0.10),
            parent=horn_e, mat_=M_BISON_HORN)
        smooth_cone(f"{name}_hnt{side}", r1=0.04, r2=0.01, depth=0.10, segs=8,
                    loc=(0, 0, 0.30), parent=horn_e, mat_=M_BISON_HORN)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.08, segs=10, rings=8,
                      loc=(-0.10, side*0.35, 0.10), parent=head_b_e, mat_=M_BISON_BROWN)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.04, loc=(0.08, side*0.22, 0.05),
                      parent=head_b_e, mat_=M_EYE)
    # 4 short legs
    for li, (lx_b, ly_b) in enumerate([(0.70, 0.30), (0.70, -0.30), (-0.70, 0.30), (-0.70, -0.30)]):
        leg_e = empty(f"{name}_le{li}", (lx_b, ly_b, 1.0), parent=base)
        cyl(f"{name}_ul{li}", r=0.18, depth=0.45, segs=10, loc=(0, 0, -0.22),
            parent=leg_e, mat_=M_BISON_DARK)
        cyl(f"{name}_ll{li}", r=0.16, depth=0.40, segs=10, loc=(0, 0, -0.65),
            parent=leg_e, mat_=M_BISON_DARK)
        # Hoof
        cyl(f"{name}_hf{li}", r=0.18, depth=0.10, segs=10, loc=(0, 0, -0.90),
            parent=leg_e, mat_=M_BISON_HORN)
    # Tail with tuft
    tail_e = empty(f"{name}_te", (-1.0, 0, 1.40), parent=base)
    for ti in range(4):
        cyl(f"{name}_t{ti}", r=0.06 - ti*0.005, depth=0.15, segs=8,
            loc=(0, 0, -ti*0.15), parent=tail_e, mat_=M_BISON_DARK)
    smooth_sphere(f"{name}_tu_t", r=0.10, segs=10, rings=8, loc=(0, 0, -0.70),
                  parent=tail_e, mat_=M_BISON_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_b_e}

bisons = []
bison_pos = [(-50, 30, math.radians(45)), (40, 30, math.radians(-30)),
              (-45, 50, math.radians(60)), (35, 50, math.radians(-60)),
              (-40, 0, math.radians(0)), (45, 5, math.radians(180))]
for i, (bx, by, fac) in enumerate(bison_pos):
    b = make_bison(f"bi{i}", (bx, by, 0), facing=fac)
    bisons.append(b)

# ============ 4 GRAY WOLVES (signature pack) ============
def make_wolf(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    wolf_col = random.choice([M_WOLF_GRAY, M_WOLF_DARK, M_WOLF_WHITE])
    # Body (signature lean)
    smooth_sphere(f"{name}_bo", r=0.40, segs=14, rings=12, loc=(0, 0, 0.75),
                  parent=base, mat_=wolf_col, scale=(1.7, 0.85, 0.85))
    # Belly lighter
    smooth_sphere(f"{name}_be", r=0.35, segs=12, rings=10, loc=(0, 0, 0.60),
                  parent=base, mat_=M_WOLF_WHITE, scale=(1.5, 0.85, 0.45))
    # Head
    head_w_e = empty(f"{name}_he", (0.85, 0, 0.85), parent=base)
    smooth_sphere(f"{name}_h", r=0.22, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_w_e, mat_=wolf_col, scale=(1.3, 0.85, 0.95))
    # POINTED SNOUT (signature)
    smooth_cone(f"{name}_sn", r1=0.10, r2=0.06, depth=0.20, segs=10, loc=(0.20, 0, -0.05),
                parent=head_w_e, mat_=wolf_col).rotation_euler = (0, math.radians(90), 0)
    # Nose black
    smooth_sphere(f"{name}_no", r=0.04, loc=(0.32, 0, -0.05),
                  parent=head_w_e, mat_=M_EYE)
    # POINTED EARS (signature)
    for side in (-1, 1):
        smooth_cone(f"{name}_er{side}", r1=0.06, r2=0.02, depth=0.18, segs=8,
                    loc=(-0.05, side*0.13, 0.18), parent=head_w_e, mat_=wolf_col)
    # Eyes (signature golden glowing)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.04, loc=(0.06, side*0.10, 0.05),
                      parent=head_w_e, mat_=M_EYE_GOLD)
        smooth_sphere(f"{name}_ep{side}", r=0.018, loc=(0.10, side*0.10, 0.05),
                      parent=head_w_e, mat_=M_EYE)
    # 4 legs (signature lean)
    for li, (lx_w, ly_w) in enumerate([(0.40, 0.18), (0.40, -0.18), (-0.40, 0.18), (-0.40, -0.18)]):
        leg_e = empty(f"{name}_le{li}", (lx_w, ly_w, 0.55), parent=base)
        cyl(f"{name}_ul{li}", r=0.07, depth=0.35, segs=10, loc=(0, 0, -0.17),
            parent=leg_e, mat_=wolf_col)
        cyl(f"{name}_ll{li}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.50),
            parent=leg_e, mat_=wolf_col)
        # Paw
        cyl(f"{name}_pw{li}", r=0.08, depth=0.08, segs=10, loc=(0, 0, -0.70),
            parent=leg_e, mat_=M_WOLF_DARK)
    # BUSHY TAIL (signature)
    tail_e = empty(f"{name}_te", (-0.80, 0, 0.85), parent=base)
    tail_e.rotation_euler = (0, math.radians(60), 0)
    for ti in range(6):
        cyl(f"{name}_t{ti}", r=0.10 - ti*0.005, depth=0.12, segs=10,
            loc=(0, 0, ti*0.12), parent=tail_e, mat_=wolf_col)
    smooth_sphere(f"{name}_tu_t", r=0.13, segs=12, rings=8, loc=(0, 0, 0.80),
                  parent=tail_e, mat_=wolf_col)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_w_e}

wolves = []
wolf_pos = [(-15, -45, math.radians(0)), (-8, -42, math.radians(-15)),
             (5, -45, math.radians(20)), (12, -42, math.radians(-30))]
for i, (wx, wy, fac) in enumerate(wolf_pos):
    w = make_wolf(f"wo{i}", (wx, wy, 0), facing=fac)
    wolves.append(w)

# ============ RANGER LOG CABIN (signature) ============
cabin_e = empty("cabin", (-60, -10, 0))
# Log walls (stacked logs signature)
for li_c in range(8):
    lz_c = li_c * 0.45 + 0.225
    beveled_cube(f"ca_l{li_c}", (8, 6, 0.35), bevel_offset=0.06, loc=(0, 0, lz_c),
                 parent=cabin_e, mat_=M_LOG_BROWN if li_c % 2 == 0 else M_LOG_DARK)
# Roof (steep pitched)
for ri_c in range(8):
    ri_t = ri_c / 8.0
    rw = 8 + 1 * (1 - ri_t)
    rl = 6 + 1 * (1 - ri_t)
    beveled_cube(f"ca_r{ri_c}", (rw, rl, 0.20), bevel_offset=0.05,
                 loc=(0, 0, 3.8 + ri_c * 0.30), parent=cabin_e, mat_=M_ROOF_DARK)
# Chimney
beveled_cube("ca_ch", (1, 1, 3), bevel_offset=0.10, loc=(2.5, 2, 5.5),
             parent=cabin_e, mat_=M_VOLCANIC_ROCK)
# Door
beveled_cube("ca_d", (1.5, 0.10, 2.5), bevel_offset=0.05, loc=(0, -3.05, 1.25),
             parent=cabin_e, mat_=M_DOOR)
# Windows (glowing warm)
for side in (-1, 1):
    beveled_cube(f"ca_w{side}", (1.5, 0.06, 1.2), bevel_offset=0.04,
                 loc=(side*2.5, -3.05, 2.0), parent=cabin_e, mat_=M_WINDOW_GLOW)
    # Window cross
    beveled_cube(f"ca_wxv{side}", (0.08, 0.08, 1.2), bevel_offset=0.01,
                 loc=(side*2.5, -3.08, 2.0), parent=cabin_e, mat_=M_LOG_DARK)
    beveled_cube(f"ca_wxh{side}", (1.5, 0.08, 0.08), bevel_offset=0.01,
                 loc=(side*2.5, -3.08, 2.0), parent=cabin_e, mat_=M_LOG_DARK)

# ============ LODGEPOLE PINES (signature) ============
def make_pine(name, loc):
    base = empty(name, loc)
    # Tall thin trunk
    cyl(f"{name}_t", r=0.25, depth=10, segs=10, loc=(0, 0, 5), parent=base, mat_=M_TRUNK)
    # Conical canopy
    for li in range(5):
        lz = 5 + li * 1.2
        lr = 2 - li * 0.30
        smooth_cone(f"{name}_c{li}", r1=lr, r2=lr*0.5, depth=1.5, segs=14,
                    loc=(0, 0, lz), parent=base, mat_=M_PINE_DARK)
    return base

for i in range(10):
    angle = random.uniform(0, math.pi*2)
    rad = random.uniform(70, 120)
    px = math.cos(angle) * rad; py = math.sin(angle) * rad
    if py > -50:
        make_pine(f"pn{i}", (px, py, 0))

# ============ USA FLAG (signature stars and stripes) ============
flag_e = empty("flag", (-65, -45, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_LOG_DARK)
# 13 red and white stripes (signature)
for si in range(13):
    sz = 9.5 + si * 0.13
    color = M_FLAG_RED if si % 2 == 0 else M_FLAG_WHITE
    beveled_cube(f"fl_s{si}", (4, 0.05, 0.12), bevel_offset=0.02, loc=(2, 0, sz),
                 parent=flag_e, mat_=color)
# Blue canton with stars (top-left)
beveled_cube("fl_c", (1.6, 0.06, 0.85), bevel_offset=0.04, loc=(0.8, -0.005, 10.65),
             parent=flag_e, mat_=M_FLAG_BLUE)
# 50 stars (signature simplified 5x4)
for si in range(20):
    sx_st = 0.20 + (si % 5) * 0.30
    sy_st = -0.06
    sz_st = 10.35 + (si // 5) * 0.20
    smooth_sphere(f"fl_st{si}", r=0.04, loc=(sx_st, sy_st, sz_st),
                  parent=flag_e, mat_=M_FLAG_STAR)
flag_e["_phase"] = 0

# ============================================================
# 600 MINERAL DROPLETS + 400 THERMAL SPARKLES (PARTICULES SIGNATURES)
# ============================================================
droplets = []
for i in range(600):
    # Concentrate near geysers and pools
    region = i % 5
    if region == 0:
        # Old Faithful
        px = random.uniform(-5, 5); py = random.uniform(-5, 5)
        pz = random.uniform(5, 35)
    elif region < 4:
        # Prismatic pools
        pool_x, pool_y = random.choice(pool_pos)
        px = pool_x + random.uniform(-7, 7); py = pool_y + random.uniform(-7, 7)
        pz = random.uniform(2, 18)
    else:
        # Scattered
        px = random.uniform(-100, 100); py = random.uniform(-100, 100)
        pz = random.uniform(2, 22)
    d_col = M_DROP if i % 2 == 0 else M_DROP_BLUE
    d = smooth_sphere(f"dr{i}", r=random.uniform(0.15, 0.32), segs=10, rings=8,
                     loc=(px, py, pz), mat_=d_col, scale=(1.3, 1.3, 0.6))
    d["_phase"] = random.uniform(0, math.pi*2)
    d["_base_x"] = px; d["_base_y"] = py; d["_base_z"] = pz
    d["_rise"] = random.uniform(1.5, 4.0)
    d["_speed"] = random.uniform(0.5, 1.3)
    droplets.append(d)

# 400 thermal sparkles
sparkles = []
for i in range(400):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = random.uniform(1, 28)
    s_col = random.choice(SPARKLE_COLORS)
    s_e = empty(f"sp{i}", (px, py, pz))
    # Sparkle 4-point star
    for sp in range(4):
        spa = (sp / 4.0) * math.pi * 2
        beveled_cube(f"sp{i}_p{sp}", (0.03, 0.04, 0.12), bevel_offset=0.005,
                     loc=(math.cos(spa)*0.06, math.sin(spa)*0.06, 0),
                     parent=s_e, mat_=s_col).rotation_euler = (0, 0, spa)
    smooth_sphere(f"sp{i}_c", r=0.04, loc=(0, 0, 0), parent=s_e, mat_=s_col)
    s_e["_phase"] = random.uniform(0, math.pi*2)
    s_e["_base_x"] = px; s_e["_base_y"] = py; s_e["_base_z"] = pz
    s_e["_amp"] = random.uniform(0.5, 1.5)
    s_e["_speed"] = random.uniform(0.5, 1.3)
    s_e["_blink"] = random.uniform(3, 7)
    sparkles.append(s_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Old Faithful jet pulse
phase_f = faithful_e["_phase"]
for f in range(1, total_frames + 1, 2):
    t = (f - 1) / fps
    # Major eruption pulse
    scale_jet = 0.3 + abs(math.sin(t * 1.0 + phase_f)) * 1.7
    faithful_e["_jet"].scale = (1, 1, scale_jet)
    faithful_e["_jet"].keyframe_insert("scale", frame=f)

# Bisons sway (chewing cud)
for b in bisons:
    phase = b["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        b["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     b["root"].rotation_euler.z)
        b["root"].keyframe_insert("rotation_euler", frame=f)
        b["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3), 0,
                                   math.cos(t * 1.0 + phase) * math.radians(8))
        b["he"].keyframe_insert("rotation_euler", frame=f)

# Wolves prowl
for w in wolves:
    phase = w["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        w["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(2), 0,
                                     w["root"].rotation_euler.z + math.sin(t * 0.8 + phase) * math.radians(5))
        w["root"].location.z = abs(math.sin(t * 2.0 + phase)) * 0.05
        w["root"].keyframe_insert("rotation_euler", frame=f)
        w["root"].keyframe_insert("location", frame=f)
        w["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3), 0,
                                   math.cos(t * 1.2 + phase) * math.radians(20))
        w["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 mineral droplets rise
for d in droplets:
    phase = d["_phase"]; speed = d["_speed"]; rise = d["_rise"]
    bx, by, bz_d = d["_base_x"], d["_base_y"], d["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * 0.4
        y = by + math.cos(t * speed * 0.9 + phase) * 0.4
        z = bz_d + (t * rise) % 22
        d.location = (x, y, z)
        sc_d = 1 + math.sin(t * 1.5 + phase) * 0.25 + t * 0.05
        d.scale = (sc_d * 1.3, sc_d * 1.3, sc_d * 0.6)
        d.keyframe_insert("location", frame=f)
        d.keyframe_insert("scale", frame=f)

# 400 thermal sparkles twinkle
for s in sparkles:
    phase = s["_phase"]; speed = s["_speed"]; amp = s["_amp"]; blink = s["_blink"]
    bx, by, bz_s = s["_base_x"], s["_base_y"], s["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * amp
        y = by + math.cos(t * speed * 0.9 + phase) * amp
        z = bz_s + math.sin(t * speed * 1.3 + phase) * 0.8
        s.location = (x, y, z)
        # Twinkle scale
        sc_s = 0.5 + abs(math.sin(t * blink + phase)) * 1.0
        s.scale = (sc_s, sc_s, sc_s)
        s.rotation_euler = (0, 0, t * 2.0 + phase)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)
        s.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_yellowstone_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_yellowstone_geysers_bison_wolves] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Yellowstone: Old Faithful geyser (signature mineral mound + crater + 25-segment pulsing water jet + steam cloud) + 4 Grand Prismatic Spring pools (signature concentric color rings red/orange/yellow/green/blue/center turquoise) + 6 American bisons (signature massive shoulder hump + shaggy beards + curved horns + 4 legs with hooves + tail tuft) + 4 gray wolves (signature lean body + pointed snout + pointed ears + golden glowing eyes + bushy tail) + Mt Sheridan 50m + 2 secondary peaks + ranger log cabin with 8 stacked logs + chimney + glowing windows + 10 lodgepole pine trees + USA flag (13 stripes + blue canton + 20 stars) + 600 mineral droplets rising + 400 thermal sparkles twinkling")
print("🌋 FIXES: 1 volcanic prairie ground + 600 mineral droplets + 400 thermal sparkles signature 🌋")
