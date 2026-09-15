"""
proc_iceland_geysir_aurora_volcanoes.py — 272e procédural AuroraIA (137e qualité)
Iceland geysir aurora volcanoes: 4 active geysers + 6 snowy volcanoes + glaciers + Blue Lagoon + 4 vikings + grass-roof houses + Iceland flag + 600 geyser steam + 400 aurora ribbons
FIXES : 1 ground lava + signature steam + aurora
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB272)

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

# Night sky Iceland
M_SKY = mat("sky", (0.05, 0.07, 0.18, 1.0), 0.0, 0.7, emission=(0.05,0.07,0.18), emission_strength=1.2)
M_SKY_LOW = mat("sky_l", (0.15, 0.20, 0.42, 1.0), 0.0, 0.7, emission=(0.15,0.20,0.42), emission_strength=1.0)
M_MOON = mat("mn", (0.92, 0.90, 0.85, 1.0), 0.0, 0.1, emission=(0.90,0.88,0.82), emission_strength=14.0)
M_STAR = mat("st", (1.0, 0.95, 0.85, 1.0), 0.0, 0.1, emission=(1.0,0.95,0.85), emission_strength=6.0)

# Lava ground
M_LAVA_DARK = mat("ld", (0.10, 0.08, 0.08, 1.0), 0.0, 0.92, emission=(0.10,0.08,0.08), emission_strength=0.2)
M_LAVA_ROCK = mat("lr", (0.18, 0.15, 0.13, 1.0), 0.0, 0.85)
M_LAVA_GLOW = mat("lg", (0.85, 0.18, 0.05, 1.0), 0.2, 0.30, emission=(0.85,0.18,0.05), emission_strength=4.0)
M_MOSS = mat("mo", (0.32, 0.55, 0.30, 1.0), 0.0, 0.85, emission=(0.30,0.52,0.30), emission_strength=0.3)

# Snow/ice
M_SNOW = mat("sn", (0.95, 0.95, 0.95, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.92), emission_strength=0.5)
M_ICE = mat("ic", (0.75, 0.85, 0.92, 1.0), 0.0, 0.10, emission=(0.72,0.82,0.90), emission_strength=1.0, alpha=0.85)
M_GLACIER = mat("gl", (0.78, 0.88, 0.95, 1.0), 0.0, 0.20, emission=(0.75,0.85,0.92), emission_strength=0.8)
M_GLACIER_BLUE = mat("glb", (0.55, 0.78, 0.92, 1.0), 0.0, 0.15, emission=(0.55,0.75,0.90), emission_strength=1.0)

# Volcano
M_VOLCANO_DARK = mat("vd", (0.15, 0.12, 0.10, 1.0), 0.0, 0.92)
M_VOLCANO_GRAY = mat("vg", (0.32, 0.30, 0.28, 1.0), 0.0, 0.85)

# Geyser water
M_GEYSER_WATER = mat("gw", (0.85, 0.95, 1.0, 1.0), 0.0, 0.10, emission=(0.85,0.92,1.0), emission_strength=2.5, alpha=0.75)
M_GEYSER_HOT = mat("gh", (0.95, 0.98, 1.0, 1.0), 0.0, 0.10, emission=(0.92,0.95,1.0), emission_strength=4.0, alpha=0.65)

# Blue Lagoon
M_LAGOON = mat("lg2", (0.45, 0.85, 0.92, 1.0), 0.2, 0.10, emission=(0.45,0.82,0.90), emission_strength=2.0, alpha=0.78)
M_LAGOON_DEEP = mat("lgd", (0.20, 0.65, 0.78, 1.0), 0.2, 0.15, alpha=0.85)

# Steam
M_STEAM_WHITE = mat("sw2", (0.95, 0.95, 0.95, 1.0), 0.0, 0.95, emission=(0.95,0.95,0.95), emission_strength=1.8, alpha=0.40)
M_STEAM_BLUE = mat("sb", (0.85, 0.92, 0.98, 1.0), 0.0, 0.95, emission=(0.85,0.92,0.98), emission_strength=1.5, alpha=0.35)

# Viking
M_VIKING_SKIN = mat("vs", (0.85, 0.65, 0.48, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.48), emission_strength=0.3)
M_VIKING_BEARD = mat("vbr", (0.62, 0.42, 0.22, 1.0), 0.0, 0.85)
M_VIKING_BEARD_BLOND = mat("vbb", (0.85, 0.70, 0.32, 1.0), 0.0, 0.85)
M_VIKING_HAIR_BROWN = mat("vhb", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85)

# Armor/clothing
M_FUR = mat("fu", (0.35, 0.25, 0.15, 1.0), 0.0, 0.90)
M_LEATHER = mat("le", (0.32, 0.20, 0.12, 1.0), 0.2, 0.45)
M_TUNIC_RED = mat("tr", (0.65, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.62,0.18,0.18), emission_strength=0.5)
M_TUNIC_GREEN = mat("tg", (0.28, 0.55, 0.32, 1.0), 0.0, 0.65, emission=(0.28,0.52,0.32), emission_strength=0.4)
M_TUNIC_BROWN = mat("tbr", (0.42, 0.28, 0.15, 1.0), 0.0, 0.75)
TUNIC_COLORS = [M_TUNIC_RED, M_TUNIC_GREEN, M_TUNIC_BROWN]
M_CHAINMAIL = mat("cm", (0.55, 0.55, 0.55, 1.0), 0.7, 0.40)
M_METAL = mat("me", (0.55, 0.55, 0.55, 1.0), 0.9, 0.20)
M_METAL_SHINE = mat("mes", (0.85, 0.82, 0.78, 1.0), 1.0, 0.10)
M_HORN = mat("hn", (0.92, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.82,0.62), emission_strength=0.4)

# Eyes
M_EYE_BLUE = mat("eb", (0.20, 0.55, 0.85, 1.0), 0.0, 0.20, emission=(0.20,0.55,0.82), emission_strength=0.5)
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Grass-roof house
M_HOUSE_WOOD = mat("hw", (0.55, 0.32, 0.15, 1.0), 0.0, 0.75, emission=(0.52,0.30,0.15), emission_strength=0.3)
M_HOUSE_DARK = mat("hd", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)
M_GRASS_ROOF = mat("gr", (0.42, 0.58, 0.28, 1.0), 0.0, 0.85, emission=(0.40,0.55,0.28), emission_strength=0.3)
M_GRASS_ROOF_DARK = mat("grd", (0.28, 0.42, 0.22, 1.0), 0.0, 0.92)
M_DOOR_RED = mat("dr", (0.65, 0.20, 0.20, 1.0), 0.0, 0.55, emission=(0.62,0.20,0.20), emission_strength=0.5)
M_WINDOW_GLOW = mat("wg", (1.0, 0.78, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.78,0.30), emission_strength=6.0)

# Iceland flag (signature)
M_FLAG_BLUE = mat("fb", (0.10, 0.30, 0.62, 1.0), 0.0, 0.45, emission=(0.10,0.30,0.60), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_FLAG_RED = mat("fr", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=1.0)

# Aurora colors
M_AURORA_GREEN = mat("ag", (0.18, 0.95, 0.45, 1.0), 0.0, 0.05, emission=(0.18,0.92,0.45), emission_strength=8.0, alpha=0.65)
M_AURORA_PURPLE = mat("ap", (0.55, 0.25, 0.85, 1.0), 0.0, 0.05, emission=(0.55,0.25,0.82), emission_strength=7.0, alpha=0.65)
M_AURORA_PINK = mat("apk", (0.85, 0.30, 0.65, 1.0), 0.0, 0.05, emission=(0.82,0.30,0.62), emission_strength=7.0, alpha=0.60)
M_AURORA_BLUE = mat("ab", (0.30, 0.55, 0.95, 1.0), 0.0, 0.05, emission=(0.30,0.52,0.92), emission_strength=7.0, alpha=0.65)
AURORA_COLORS = [M_AURORA_GREEN, M_AURORA_PURPLE, M_AURORA_PINK, M_AURORA_BLUE]

# Geyser droplet
M_DROP = mat("dp", (0.92, 0.95, 1.0, 1.0), 0.0, 0.10, emission=(0.92,0.95,1.0), emission_strength=2.5, alpha=0.65)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Moon
smooth_sphere("moon", r=7, segs=24, rings=18, loc=(60, 100, 50), mat_=M_MOON)
for sh in range(3):
    smooth_sphere(f"moon_h{sh}", r=7 + sh*0.8, segs=24, rings=18, loc=(60, 100, 50), mat_=M_MOON)
# Stars
for si in range(100):
    sa = random.uniform(0, math.pi*2); se = random.uniform(0.3, 0.9)
    sx_st = math.cos(sa) * 230 * math.cos(se)
    sy_st = math.sin(sa) * 230 * math.cos(se)
    sz_st = math.sin(se) * 180 + 50
    smooth_sphere(f"star{si}", r=random.uniform(0.4, 0.8), segs=8, rings=6,
                  loc=(sx_st, sy_st, sz_st), mat_=M_STAR)

# ============ ONE clean black lava ground ============
ground = beveled_cube("ground", (250, 250, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_LAVA_DARK)
# Lava rock patches scattered
for ri in range(250):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 110)
    smooth_sphere(f"lr{ri}", r=random.uniform(0.5, 1.2), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.12),
                  mat_=M_LAVA_ROCK if ri % 3 == 0 else M_LAVA_DARK, scale=(1.4, 1.3, 0.22))
# Moss patches
for mi in range(80):
    a = random.uniform(0, math.pi*2); rad = random.uniform(5, 90)
    smooth_sphere(f"mp{mi}", r=random.uniform(0.4, 0.9), segs=10, rings=6,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_MOSS, scale=(1.3, 1.2, 0.18))
# Lava crack glow lines
for ci in range(15):
    cx_c = random.uniform(-70, 70); cy_c = random.uniform(-70, 70)
    beveled_cube(f"lc{ci}", (random.uniform(2, 5), 0.3, 0.05), bevel_offset=0.02,
                 loc=(cx_c, cy_c, 0.05), mat_=M_LAVA_GLOW).rotation_euler = (0, 0, random.uniform(0, math.pi))

# ============ 6 SNOWY VOLCANOES (signature Eyjafjallajökull) ============
def make_snow_volcano(name, loc, height, base_radius):
    base = empty(name, loc)
    # Stratovolcano shape with layers
    n_layers = int(height / 4)
    for li in range(n_layers):
        lz = li * 4
        lr1 = base_radius * (1 - li / n_layers * 0.8)
        lr2 = base_radius * (1 - (li+1) / n_layers * 0.8)
        smooth_cone(f"{name}_l{li}", r1=lr1, r2=lr2, depth=4.5, segs=22,
                    loc=(0, 0, lz + 2.25), parent=base,
                    mat_=M_VOLCANO_DARK if li < n_layers//2 else M_VOLCANO_GRAY)
    # Snow cap on top half
    snow_cap_e = empty(f"{name}_se", (0, 0, height * 0.6), parent=base)
    n_snow = max(3, int(height / 8))
    for si in range(n_snow):
        sz_s = si * 3
        sr = base_radius * (0.5 - si / n_snow * 0.3)
        smooth_cone(f"{name}_s{si}", r1=sr + 0.5, r2=sr - 0.2, depth=3, segs=18,
                    loc=(0, 0, sz_s), parent=snow_cap_e, mat_=M_SNOW)
    # Peak
    smooth_cone(f"{name}_pk", r1=0.5, r2=0.05, depth=2, segs=14,
                loc=(0, 0, height - 0.5), parent=base, mat_=M_SNOW)
    # Glacier flows down
    for gi in range(3):
        ga = (gi / 3.0) * math.pi * 2
        for sgi in range(5):
            sgz = height * 0.6 - sgi * 2
            beveled_cube(f"{name}_g{gi}_{sgi}", (1.5, 0.4, 0.3), bevel_offset=0.05,
                         loc=(math.cos(ga)*(base_radius * 0.6), math.sin(ga)*(base_radius * 0.6), sgz),
                         parent=base, mat_=M_GLACIER).rotation_euler = (0, 0, ga)
    return base

volcano_pos = [(-50, 60, 25, 8), (-20, 75, 30, 10), (15, 65, 22, 7),
                (45, 55, 28, 9), (-65, 30, 26, 8), (60, 20, 24, 7)]
for i, (vx, vy, vh, vr) in enumerate(volcano_pos):
    make_snow_volcano(f"vol{i}", (vx, vy, 0), vh, vr)

# ============ 4 ACTIVE GEYSERS (signature) ============
def make_geyser(name, loc):
    base = empty(name, loc)
    # Crater bowl
    cyl(f"{name}_c", r=2.5, depth=0.30, segs=22, loc=(0, 0, 0.15), parent=base, mat_=M_VOLCANO_GRAY)
    # Inner pool
    cyl(f"{name}_p", r=2.0, depth=0.20, segs=22, loc=(0, 0, 0.25), parent=base, mat_=M_GEYSER_WATER)
    # Surrounding mineral rim (signature white)
    cyl(f"{name}_rim", r=2.7, depth=0.10, segs=22, loc=(0, 0, 0.05), parent=base, mat_=M_SNOW)
    # JET column water shooting up (signature)
    jet_e = empty(f"{name}_j", (0, 0, 0.30), parent=base)
    # Stacked water layers narrowing
    for ji in range(20):
        jz = ji * 0.6
        jr = 0.40 - ji * 0.015
        smooth_sphere(f"{name}_j{ji}", r=max(0.05, jr), segs=12, rings=8,
                      loc=(random.uniform(-0.1, 0.1), random.uniform(-0.1, 0.1), jz),
                      parent=jet_e, mat_=M_GEYSER_HOT if ji < 5 else M_GEYSER_WATER,
                      scale=(1, 1, 1.5))
    # Steam cloud at top
    for sti in range(8):
        sta = random.uniform(0, math.pi*2); str_r = random.uniform(0, 1.5)
        smooth_sphere(f"{name}_st{sti}", r=random.uniform(0.6, 1.2), segs=12, rings=8,
                      loc=(math.cos(sta)*str_r, math.sin(sta)*str_r, 12 + random.uniform(0, 2)),
                      parent=base, mat_=M_STEAM_WHITE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "jet": jet_e}

geysers = []
geyser_pos = [(-15, -25), (15, -28), (-25, 0), (25, -5)]
for i, (gx, gy) in enumerate(geyser_pos):
    g = make_geyser(f"gy{i}", (gx, gy, 0))
    geysers.append(g)

# ============ BLUE LAGOON (signature) ============
lagoon_e = empty("lagoon", (0, -45, 0))
# Outer pool shape
for li in range(8):
    la = (li / 8.0) * math.pi * 2
    lr = 8 + random.uniform(-1, 1)
    smooth_sphere(f"lg_o{li}", r=4, segs=14, rings=10,
                  loc=(math.cos(la)*lr, math.sin(la)*lr, 0.20),
                  parent=lagoon_e, mat_=M_LAGOON_DEEP, scale=(1.2, 1.2, 0.15))
# Inner pool (lighter blue)
cyl("lg_i", r=10, depth=0.30, segs=22, loc=(0, 0, 0.30), parent=lagoon_e, mat_=M_LAGOON)
# Steam rising from lagoon
for sti in range(15):
    sta = random.uniform(0, math.pi*2); str_r = random.uniform(0, 8)
    smooth_sphere(f"lg_st{sti}", r=random.uniform(0.5, 1.2), segs=10, rings=8,
                  loc=(math.cos(sta)*str_r, math.sin(sta)*str_r, 2 + random.uniform(0, 3)),
                  parent=lagoon_e, mat_=M_STEAM_BLUE)
# Lava rock around lagoon
for ri in range(20):
    ra = (ri / 20.0) * math.pi * 2
    rr = 12 + random.uniform(-0.5, 0.5)
    smooth_sphere(f"lg_r{ri}", r=random.uniform(0.6, 1.0), segs=10, rings=8,
                  loc=(math.cos(ra)*rr, math.sin(ra)*rr, 0.30),
                  parent=lagoon_e, mat_=M_LAVA_ROCK, scale=(1.4, 1.3, 0.6))

# ============ 4 VIKINGS (signature) ============
def make_viking(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    tunic_col = random.choice(TUNIC_COLORS)
    # Fur cloak
    smooth_cone(f"{name}_cl", r1=0.45, r2=0.48, depth=1.2, segs=14, loc=(0, 0.15, 1.10),
                parent=base, mat_=M_FUR)
    # Tunic body
    smooth_cone(f"{name}_to", r1=0.32, r2=0.34, depth=0.85, segs=14, loc=(0, 0, 1.20),
                parent=base, mat_=tunic_col)
    # Belt
    cyl(f"{name}_be", r=0.35, depth=0.10, segs=14, loc=(0, 0, 0.85),
        parent=base, mat_=M_LEATHER)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.12, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=M_TUNIC_BROWN)
    # Leather boots
    for side in (-1, 1):
        beveled_cube(f"{name}_b{side}", (0.14, 0.32, 0.20), bevel_offset=0.03,
                     loc=(side*0.13, 0.04, 0.08), parent=base, mat_=M_LEATHER)
    # Arms muscular (one holding axe)
    sh_l = empty(f"{name}_a0", (-0.34, 0, 1.65), parent=base)
    sh_l.rotation_euler = (math.radians(-30), 0, math.radians(30))
    cyl(f"{name}_ua0", r=0.10, depth=0.45, segs=10, loc=(0, 0, -0.22),
        parent=sh_l, mat_=tunic_col)
    cyl(f"{name}_fa0", r=0.09, depth=0.40, segs=10, loc=(0, 0, -0.65),
        parent=sh_l, mat_=M_VIKING_SKIN)
    sh_r = empty(f"{name}_a1", (0.34, 0, 1.65), parent=base)
    sh_r.rotation_euler = (math.radians(-90), 0, math.radians(-40))
    cyl(f"{name}_ua1", r=0.10, depth=0.45, segs=10, loc=(0, 0, -0.22),
        parent=sh_r, mat_=tunic_col)
    cyl(f"{name}_fa1", r=0.09, depth=0.40, segs=10, loc=(0, 0, -0.65),
        parent=sh_r, mat_=M_VIKING_SKIN)
    # AXE in right hand (signature)
    axe_e = empty(f"{name}_axe", (0.15, 0, -0.95), parent=sh_r)
    axe_e.rotation_euler = (0, math.radians(-20), 0)
    cyl(f"{name}_axe_h", r=0.04, depth=1.2, segs=8, loc=(0, 0, 0),
        parent=axe_e, mat_=M_HOUSE_WOOD)
    # Axe head
    beveled_cube(f"{name}_axe_b", (0.25, 0.06, 0.30), bevel_offset=0.04,
                 loc=(0.15, 0, 0.55), parent=axe_e, mat_=M_METAL)
    # Axe edge
    beveled_cube(f"{name}_axe_e", (0.30, 0.04, 0.18), bevel_offset=0.04,
                 loc=(0.25, 0, 0.55), parent=axe_e, mat_=M_METAL_SHINE)
    # Head
    head_v_e = empty(f"{name}_he", (0, 0, 2.0), parent=base)
    smooth_sphere(f"{name}_h", r=0.20, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_v_e, mat_=M_VIKING_SKIN)
    # Eyes blue (signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.030, loc=(side*0.07, -0.16, 0.04),
                      parent=head_v_e, mat_=M_EYE_BLUE)
    # BEARD (signature long)
    beard_col = random.choice([M_VIKING_BEARD, M_VIKING_BEARD_BLOND])
    for bi in range(30):
        ba = random.uniform(-math.pi*0.45, math.pi*0.45)
        beard_len = random.uniform(0.20, 0.45)
        for bsi in range(int(beard_len * 6)):
            cyl(f"{name}_bd{bi}_{bsi}", r=0.025, depth=0.08, segs=6,
                loc=(math.sin(ba)*0.15, -0.10, -0.10 - bsi*0.08),
                parent=head_v_e, mat_=beard_col)
    # Hair flowing back
    for hi in range(15):
        ha = random.uniform(math.pi*0.3, math.pi*0.7)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.30, segs=6,
            loc=(math.cos(ha)*0.18, math.sin(ha)*0.15, 0.10),
            parent=head_v_e, mat_=beard_col)
    # HELMET with horns (signature mythical)
    hat_e = empty(f"{name}_ha", (0, 0, 0.18), parent=head_v_e)
    # Dome
    smooth_sphere(f"{name}_ha_d", r=0.24, segs=18, rings=12, loc=(0, 0, 0),
                  parent=hat_e, mat_=M_METAL, scale=(1, 1, 0.7))
    # Nose guard
    beveled_cube(f"{name}_ha_n", (0.06, 0.04, 0.25), bevel_offset=0.01,
                 loc=(0, -0.22, -0.15), parent=hat_e, mat_=M_METAL)
    # Rim
    cyl(f"{name}_ha_r", r=0.25, depth=0.04, segs=18, loc=(0, 0, -0.10),
        parent=hat_e, mat_=M_METAL_SHINE)
    # HORNS (signature)
    for side_h in (-1, 1):
        horn_e = empty(f"{name}_hn{side_h}", (side_h*0.20, 0, 0.10), parent=hat_e)
        horn_e.rotation_euler = (0, side_h*math.radians(70), 0)
        for hi in range(8):
            hia = (hi / 8.0) * math.pi * 0.6
            cyl(f"{name}_hn{side_h}_{hi}", r=0.06 - hi*0.005, depth=0.10, segs=8,
                loc=(0, math.sin(hia)*0.05, math.cos(hia)*0.10 + hi*0.10),
                parent=horn_e, mat_=M_HORN)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_v_e}

vikings = []
viking_pos = [(-15, 15, math.radians(20)), (-5, 12, math.radians(0)),
               (8, 15, math.radians(-10)), (20, 18, math.radians(-30))]
for i, (vx, vy, fac) in enumerate(viking_pos):
    v = make_viking(f"vk{i}", (vx, vy, 0), facing=fac)
    vikings.append(v)

# ============ 3 GRASS-ROOF HOUSES (signature Icelandic turf) ============
def make_turf_house(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Stone wall base
    beveled_cube(f"{name}_w", (4, 3, 1.8), bevel_offset=0.10, loc=(0, 0, 1.10),
                 parent=base, mat_=M_LAVA_ROCK)
    # Wood facade front
    beveled_cube(f"{name}_wf", (4, 0.20, 1.5), bevel_offset=0.06, loc=(0, -1.55, 0.95),
                 parent=base, mat_=M_HOUSE_WOOD)
    # Vertical planks
    for pi in range(8):
        beveled_cube(f"{name}_p{pi}", (0.40, 0.05, 1.5), bevel_offset=0.02,
                     loc=(-1.8 + pi*0.5, -1.62, 0.95), parent=base, mat_=M_HOUSE_DARK)
    # Door (red signature)
    beveled_cube(f"{name}_d", (0.8, 0.06, 1.4), bevel_offset=0.04,
                 loc=(0, -1.66, 0.90), parent=base, mat_=M_DOOR_RED)
    # Window (glow)
    for side in (-1, 1):
        beveled_cube(f"{name}_wi{side}", (0.7, 0.04, 0.5), bevel_offset=0.02,
                     loc=(side*1.20, -1.66, 1.35), parent=base, mat_=M_WINDOW_GLOW)
        # Window cross
        beveled_cube(f"{name}_wxc{side}_v", (0.04, 0.06, 0.5), bevel_offset=0.01,
                     loc=(side*1.20, -1.68, 1.35), parent=base, mat_=M_HOUSE_DARK)
        beveled_cube(f"{name}_wxc{side}_h", (0.7, 0.06, 0.04), bevel_offset=0.01,
                     loc=(side*1.20, -1.68, 1.35), parent=base, mat_=M_HOUSE_DARK)
    # GRASS ROOF (signature steep pitched turf)
    roof_e = empty(f"{name}_re", (0, 0, 2.0), parent=base)
    # Roof main (triangular)
    smooth_cone(f"{name}_r", r1=2.5, r2=0.05, depth=2.0, segs=4, loc=(0, 0, 1.0),
                parent=roof_e, mat_=M_GRASS_ROOF).rotation_euler = (0, 0, math.radians(45))
    # Grass tufts on roof
    for ti in range(40):
        ta = random.uniform(0, math.pi*2); tr = random.uniform(0.5, 2.3)
        smooth_sphere(f"{name}_gt{ti}", r=random.uniform(0.10, 0.20), segs=10, rings=6,
                      loc=(math.cos(ta)*tr, math.sin(ta)*tr, random.uniform(0.5, 1.5)),
                      parent=roof_e, mat_=M_GRASS_ROOF if ti % 2 else M_GRASS_ROOF_DARK,
                      scale=(1.2, 1.2, 0.7))
    # Smoke chimney
    cyl(f"{name}_ch", r=0.15, depth=0.6, segs=10, loc=(1.2, 0.5, 2.2),
        parent=base, mat_=M_HOUSE_DARK)
    return base

for i, (hx, hy, hf) in enumerate([(-40, -10, math.radians(20)), (38, -8, math.radians(-30)), (0, 35, math.radians(180))]):
    make_turf_house(f"th{i}", (hx, hy, 0), facing=hf)

# ============ ICELAND FLAG (signature blue/white/red cross) ============
flag_e = empty("flag", (-55, -30, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_METAL)
# Blue field
beveled_cube("fl_b", (4, 0.05, 2.5), bevel_offset=0.06, loc=(2, 0, 10.5),
             parent=flag_e, mat_=M_FLAG_BLUE)
# White cross (horizontal + vertical)
beveled_cube("fl_wh", (4.02, 0.06, 0.50), bevel_offset=0.04, loc=(2, -0.005, 10.5),
             parent=flag_e, mat_=M_FLAG_WHITE)
beveled_cube("fl_wv", (0.50, 0.06, 2.52), bevel_offset=0.04, loc=(1.20, -0.005, 10.5),
             parent=flag_e, mat_=M_FLAG_WHITE)
# Red cross (offset within white)
beveled_cube("fl_rh", (4.04, 0.07, 0.25), bevel_offset=0.02, loc=(2, -0.010, 10.5),
             parent=flag_e, mat_=M_FLAG_RED)
beveled_cube("fl_rv", (0.25, 0.07, 2.54), bevel_offset=0.02, loc=(1.20, -0.010, 10.5),
             parent=flag_e, mat_=M_FLAG_RED)
flag_e["_phase"] = 0

# ============================================================
# 600 GEYSER STEAM DROPS + 400 AURORA RIBBONS (PARTICULES SIGNATURES)
# ============================================================
steam_drops = []
for i in range(600):
    # Concentrate around geysers + lagoon
    region = i % 5
    if region == 0:
        # Geyser 1
        px = -15 + random.uniform(-3, 3); py = -25 + random.uniform(-3, 3)
        pz = random.uniform(5, 25)
    elif region == 1:
        # Geyser 2
        px = 15 + random.uniform(-3, 3); py = -28 + random.uniform(-3, 3)
        pz = random.uniform(5, 25)
    elif region == 2:
        # Geyser 3
        px = -25 + random.uniform(-3, 3); py = 0 + random.uniform(-3, 3)
        pz = random.uniform(5, 25)
    elif region == 3:
        # Geyser 4
        px = 25 + random.uniform(-3, 3); py = -5 + random.uniform(-3, 3)
        pz = random.uniform(5, 25)
    else:
        # Blue lagoon area
        px = random.uniform(-12, 12); py = -45 + random.uniform(-10, 10)
        pz = random.uniform(2, 15)
    s_col = M_STEAM_WHITE if i % 2 == 0 else M_STEAM_BLUE
    s = smooth_sphere(f"sd{i}", r=random.uniform(0.20, 0.40), segs=10, rings=8,
                      loc=(px, py, pz), mat_=s_col, scale=(1.5, 1.5, 0.6))
    s["_phase"] = random.uniform(0, math.pi*2)
    s["_base_x"] = px; s["_base_y"] = py; s["_base_z"] = pz
    s["_rise"] = random.uniform(2.0, 4.5)
    s["_speed"] = random.uniform(0.6, 1.4)
    steam_drops.append(s)

# 400 aurora ribbons
auroras = []
for i in range(400):
    # Spread across high sky in horizontal bands
    px = random.uniform(-150, 150)
    py = random.uniform(-100, 100)
    pz = random.uniform(35, 65)
    aur_col = random.choice(AURORA_COLORS)
    # Curved ribbon
    a_e = empty(f"au{i}", (px, py, pz))
    for ai in range(8):
        aiz = -0.5 + ai * 0.5
        ax = math.sin(ai * 0.5) * 1.2
        ay = math.cos(ai * 0.4) * 0.8
        beveled_cube(f"au{i}_s{ai}", (1.5, 0.10, 0.30), bevel_offset=0.04,
                     loc=(ax, ay, aiz), parent=a_e, mat_=aur_col)
    a_e["_phase"] = random.uniform(0, math.pi*2)
    a_e["_base_x"] = px; a_e["_base_y"] = py; a_e["_base_z"] = pz
    a_e["_speed"] = random.uniform(0.3, 0.8)
    a_e["_amp"] = random.uniform(2, 5)
    auroras.append(a_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Geyser jet pulses
for g in geysers:
    phase = g["root"]["_phase"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Pulse height
        scale_jet = 0.4 + abs(math.sin(t * 1.5 + phase)) * 1.6
        g["jet"].scale = (1, 1, scale_jet)
        g["jet"].keyframe_insert("scale", frame=f)

# Vikings sway with axe swing
for v in vikings:
    phase = v["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        v["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3), 0,
                                     v["root"].rotation_euler.z + math.sin(t * 2.0 + phase) * math.radians(8))
        v["root"].keyframe_insert("rotation_euler", frame=f)
        v["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                   math.cos(t * 1.5 + phase) * math.radians(10))
        v["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 steam drops rise
for s in steam_drops:
    phase = s["_phase"]; speed = s["_speed"]; rise = s["_rise"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * 0.4
        y = by + math.cos(t * speed * 0.9 + phase) * 0.4
        z = bz + (t * rise) % 20
        s.location = (x, y, z)
        sc_s = 1 + math.sin(t * 1.5 + phase) * 0.30 + t * 0.06
        s.scale = (sc_s * 1.5, sc_s * 1.5, sc_s * 0.6)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

# 400 aurora ribbons wave + drift
for a in auroras:
    phase = a["_phase"]; speed = a["_speed"]; amp = a["_amp"]
    bx, by, bz = a["_base_x"], a["_base_y"], a["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * amp
        y = by + math.cos(t * speed * 0.8 + phase) * amp
        z = bz + math.sin(t * speed * 1.2 + phase) * 1.5
        a.location = (x, y, z)
        a.rotation_euler = (math.sin(t * speed + phase) * math.radians(15),
                             math.cos(t * speed * 0.7 + phase) * math.radians(10),
                             math.sin(t * speed * 0.5 + phase) * math.radians(20))
        a.keyframe_insert("location", frame=f)
        a.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_iceland_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_iceland_geysir_aurora_volcanoes] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Iceland geysir aurora: 6 snowy stratovolcanoes with snow caps + glacier flows + Eyjafjallajokull peaks + 4 active geysers (crater bowl + mineral rim + 20-layer pulsing jet + steam clouds) + Blue Lagoon turquoise + 4 vikings (fur cloaks + tunics + axes + horned helmets signature + beards + blue eyes) + 3 turf houses with grass roofs + Iceland flag with offset blue/white/red cross + 100 stars + moon + lava cracks glow")
print("✨ FIXES: 1 black lava ground + 600 geyser steam + 400 aurora ribbons green/purple/pink/blue waving (signature Iceland mandatory) ✨")
