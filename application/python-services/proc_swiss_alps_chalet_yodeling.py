"""
proc_swiss_alps_chalet_yodeling.py — 244e procédural AuroraIA (109e qualité)
Swiss Alps yodeling: chalet + Matterhorn + lake + 6 cows + 2 goats + 4 yodelers + alphorn + 4 hikers + 8 firs + chairlift + 600 edelweiss + 400 cowbells
FIXES : 1 ground + 600 edelweiss drift + 400 cowbells ring (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB244)

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

# Sky palette (sunny alpine)
M_SKY = mat("sky", (0.45, 0.65, 0.92, 1.0), 0.0, 0.7, emission=(0.45,0.65,0.92), emission_strength=1.8)
M_SUN = mat("sun", (1.0, 0.95, 0.65, 1.0), 0.0, 0.1, emission=(1.0,0.95,0.65), emission_strength=14.0)
M_CLOUD = mat("cloud", (0.95, 0.95, 0.95, 1.0), 0.0, 0.7, emission=(0.92,0.92,0.92), emission_strength=1.5)

# Snow mountain
M_SNOW = mat("snow", (0.95, 0.96, 0.98, 1.0), 0.0, 0.30, emission=(0.92,0.94,0.96), emission_strength=1.2)
M_SNOW_BLUE = mat("snow_b", (0.85, 0.90, 0.95, 1.0), 0.0, 0.35, emission=(0.80,0.85,0.92), emission_strength=1.0)
M_ROCK_MT = mat("rock_mt", (0.50, 0.48, 0.45, 1.0), 0.0, 0.85, emission=(0.45,0.42,0.40), emission_strength=0.3)
M_ROCK_DARK = mat("rock_d", (0.35, 0.32, 0.30, 1.0), 0.0, 0.85)

# Grass alpine
M_GRASS = mat("grass", (0.30, 0.62, 0.25, 1.0), 0.0, 0.80, emission=(0.28,0.58,0.25), emission_strength=0.4)
M_GRASS_DEEP = mat("grass_d", (0.22, 0.50, 0.20, 1.0), 0.0, 0.80)
M_GRASS_GOLD = mat("grass_g", (0.65, 0.72, 0.25, 1.0), 0.0, 0.75)
M_DIRT = mat("dirt", (0.45, 0.30, 0.18, 1.0), 0.0, 0.85)

# Lake
M_LAKE = mat("lake", (0.20, 0.65, 0.78, 1.0), 0.1, 0.20, emission=(0.18,0.62,0.75), emission_strength=1.6, alpha=0.78)
M_LAKE_DEEP = mat("lake_d", (0.12, 0.50, 0.65, 1.0), 0.1, 0.25, alpha=0.85)

# Chalet wood
M_CHALET_WOOD = mat("ch_w", (0.55, 0.32, 0.15, 1.0), 0.0, 0.75, emission=(0.50,0.30,0.14), emission_strength=0.4)
M_CHALET_DARK = mat("ch_d", (0.32, 0.18, 0.08, 1.0), 0.0, 0.80)
M_CHALET_BEAM = mat("ch_b", (0.22, 0.12, 0.06, 1.0), 0.0, 0.85)
M_ROOF_DARK = mat("roof", (0.18, 0.12, 0.10, 1.0), 0.0, 0.80, emission=(0.18,0.12,0.10), emission_strength=0.3)
M_SHUTTER_RED = mat("shut", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.18), emission_strength=0.8)
M_WHITE_PLASTER = mat("plast", (0.92, 0.88, 0.78, 1.0), 0.0, 0.65, emission=(0.85,0.82,0.75), emission_strength=0.5)
M_WINDOW_GLASS = mat("win", (0.55, 0.75, 0.85, 1.0), 0.1, 0.20, emission=(0.50,0.70,0.85), emission_strength=1.5, alpha=0.65)
M_GERANIUM = mat("ger", (0.95, 0.20, 0.30, 1.0), 0.0, 0.45, emission=(0.92,0.20,0.30), emission_strength=2.0)

# Cow brown
M_COW_BR = mat("cow_br", (0.62, 0.40, 0.20, 1.0), 0.0, 0.75, emission=(0.58,0.38,0.20), emission_strength=0.4)
M_COW_WHITE_PATCH = mat("cow_wp", (0.92, 0.88, 0.82, 1.0), 0.0, 0.75)
M_COW_HORN_S = mat("cow_h_s", (0.92, 0.85, 0.75, 1.0), 0.0, 0.40)
M_COW_NOSE_S = mat("cow_n_s", (0.30, 0.18, 0.12, 1.0), 0.0, 0.55)
# Cowbell signature
M_BELL_GOLD = mat("bell", (0.95, 0.78, 0.25, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.25), emission_strength=2.5)
M_BELL_DARK = mat("bell_d", (0.65, 0.50, 0.18, 1.0), 0.85, 0.30)

# Goat
M_GOAT_WHITE = mat("goat_w", (0.92, 0.88, 0.82, 1.0), 0.0, 0.85)
M_GOAT_GREY = mat("goat_g", (0.55, 0.52, 0.50, 1.0), 0.0, 0.80)
M_GOAT_HORN = mat("goat_h", (0.40, 0.30, 0.20, 1.0), 0.0, 0.55)

# Skin
M_SKIN_PALE_S = mat("skin", (0.92, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.62), emission_strength=0.4)
M_HAIR_BL = mat("h_bl", (0.85, 0.65, 0.30, 1.0), 0.0, 0.55)
M_HAIR_BR_S = mat("h_br_s", (0.30, 0.18, 0.10, 1.0), 0.0, 0.60)

# Lederhosen
M_LEDER_BROWN = mat("led_br", (0.42, 0.22, 0.10, 1.0), 0.0, 0.75, emission=(0.38,0.20,0.10), emission_strength=0.3)
M_LEDER_DARK = mat("led_d", (0.25, 0.14, 0.06, 1.0), 0.0, 0.85)
M_LEDER_TRIM = mat("led_t", (0.95, 0.78, 0.20, 1.0), 0.85, 0.30, emission=(0.92,0.75,0.20), emission_strength=1.2)
M_SHIRT_WHITE = mat("sh_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65)
M_TIE_RED = mat("tie", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.18), emission_strength=0.6)
M_HAT_GREEN = mat("hat_g", (0.18, 0.42, 0.20, 1.0), 0.0, 0.65, emission=(0.18,0.40,0.20), emission_strength=0.4)

# Dirndl (signature Bavarian women dress)
M_DIRNDL_RED = mat("d_r", (0.85, 0.18, 0.25, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.25), emission_strength=0.6)
M_DIRNDL_BLUE = mat("d_b", (0.18, 0.30, 0.65, 1.0), 0.0, 0.55, emission=(0.18,0.30,0.62), emission_strength=0.6)
M_DIRNDL_APRON = mat("d_a", (0.85, 0.78, 0.30, 1.0), 0.0, 0.55, emission=(0.80,0.75,0.30), emission_strength=0.7)
M_BLOUSE_WHITE = mat("bl_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.92,0.90,0.85), emission_strength=0.5)

# Alphorn wood
M_ALPHORN_WOOD = mat("ah_w", (0.55, 0.32, 0.15, 1.0), 0.0, 0.65, emission=(0.50,0.30,0.14), emission_strength=0.4)
M_ALPHORN_DARK = mat("ah_d", (0.30, 0.18, 0.08, 1.0), 0.0, 0.75)

# Backpack
M_PACK_RED = mat("pack_r", (0.85, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.80,0.18,0.18), emission_strength=0.6)
M_PACK_BLUE = mat("pack_b", (0.18, 0.45, 0.85, 1.0), 0.0, 0.65, emission=(0.18,0.42,0.80), emission_strength=0.6)
M_PACK_GREEN = mat("pack_g", (0.18, 0.62, 0.32, 1.0), 0.0, 0.65, emission=(0.18,0.60,0.30), emission_strength=0.6)
M_PACK_YELLOW = mat("pack_y", (0.95, 0.78, 0.20, 1.0), 0.0, 0.55, emission=(0.92,0.75,0.20), emission_strength=0.8)
PACK_COLORS = [M_PACK_RED, M_PACK_BLUE, M_PACK_GREEN, M_PACK_YELLOW]
M_BOOTS = mat("boots", (0.25, 0.18, 0.10, 1.0), 0.0, 0.75)
M_POLE = mat("pole", (0.85, 0.85, 0.85, 1.0), 0.9, 0.20)

# Trees fir signature
M_FIR_DARK = mat("fir_d", (0.10, 0.30, 0.15, 1.0), 0.0, 0.75, emission=(0.10,0.30,0.15), emission_strength=0.4)
M_FIR_BRIGHT = mat("fir_b", (0.18, 0.45, 0.20, 1.0), 0.0, 0.70, emission=(0.18,0.42,0.20), emission_strength=0.5)
M_TRUNK_PINE = mat("trk_p", (0.30, 0.18, 0.08, 1.0), 0.0, 0.85)

# Chairlift
M_LIFT_RED = mat("lift", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.18), emission_strength=0.8)
M_LIFT_CABLE = mat("cable", (0.30, 0.30, 0.30, 1.0), 0.5, 0.40)
M_LIFT_PYLON = mat("pylon", (0.55, 0.55, 0.55, 1.0), 0.7, 0.40)

# Edelweiss signature
M_EDELWEISS_W = mat("ed_w", (0.98, 0.95, 0.88, 1.0), 0.0, 0.50, emission=(0.95,0.92,0.85), emission_strength=2.5)
M_EDELWEISS_YEL = mat("ed_y", (0.95, 0.85, 0.25, 1.0), 0.0, 0.40, emission=(0.92,0.82,0.25), emission_strength=2.5)
M_EDELWEISS_FUR = mat("ed_f", (0.92, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.62), emission_strength=1.5)

# Alpine flowers other
M_GENTIAN_BLUE = mat("gent", (0.18, 0.30, 0.85, 1.0), 0.0, 0.45, emission=(0.18,0.30,0.85), emission_strength=2.0)
M_POPPY_RED = mat("poppy", (0.95, 0.20, 0.20, 1.0), 0.0, 0.45, emission=(0.92,0.20,0.20), emission_strength=2.0)
M_BUTTERCUP = mat("butter", (1.0, 0.92, 0.20, 1.0), 0.0, 0.40, emission=(1.0,0.92,0.20), emission_strength=2.2)

# Eye/teeth
M_EYE_DARK_A = mat("eye_d_a", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)

# Sun
sun = smooth_sphere("sun", r=5, segs=24, rings=18, loc=(-20, 80, 80), mat_=M_SUN)
# Sun halo
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=5 + sh*0.6, segs=20, rings=14, loc=(-20, 80, 80), mat_=M_SUN)

# Fluffy white clouds
for ci in range(20):
    cax = random.uniform(-80, 80); cay = random.uniform(-80, 80)
    caz = random.uniform(30, 60)
    cloud_e = empty(f"cloud{ci}", (cax, cay, caz))
    for cli in range(random.randint(3, 5)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(2, 4), segs=16, rings=10,
                      loc=(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD, scale=(1.4, 1.2, 0.7))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)

# ============ MATTERHORN + 2 SNOW MOUNTAINS (signature) ============
# Matterhorn (signature triangular peak)
mh_e = empty("matterhorn", (0, 60, 0))
# Lower rocky base
for li in range(8):
    lz = li * 3
    lr = 30 - li * 2.5
    cyl(f"mh{li}", r=lr, depth=3, segs=22, loc=(0, 0, lz + 1.5),
        parent=mh_e, mat_=M_ROCK_MT if li < 5 else M_ROCK_DARK)
# Upper snow cap
for li in range(5):
    lz = 24 + li * 2.5
    lr = 12 - li * 2.2
    cyl(f"mh_sn{li}", r=lr, depth=2.5, segs=22, loc=(0, 0, lz + 1.25),
        parent=mh_e, mat_=M_SNOW)
# Sharp signature peak
smooth_cone("mh_peak", r1=2.5, r2=0.1, depth=8, segs=18, loc=(0, 0, 38),
            parent=mh_e, mat_=M_SNOW)
# Iconic asymmetric tilt (signature)
mh_e.rotation_euler = (math.radians(5), 0, math.radians(8))

# 2 secondary mountains
for mi, (mx, my) in enumerate([(40, 50), (-40, 55)]):
    m2_e = empty(f"mt2_{mi}", (mx, my, 0))
    for li in range(7):
        lz = li * 2.5
        lr = 25 - li * 2.8
        cyl(f"mt2_{mi}_{li}", r=lr, depth=2.5, segs=20, loc=(0, 0, lz + 1.25),
            parent=m2_e, mat_=M_ROCK_MT if li < 4 else M_SNOW_BLUE if li < 5 else M_SNOW)
    smooth_cone(f"mt2_{mi}_p", r1=3, r2=0.2, depth=6, segs=18, loc=(0, 0, 18),
                parent=m2_e, mat_=M_SNOW)

# ============ ONE clean alpine flower meadow ground ============
ground = beveled_cube("ground", (160, 160, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_GRASS)
# Organic grass variations
for i in range(180):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 65)
    smooth_sphere(f"grs{i}", r=random.uniform(0.4, 0.8), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_GRASS_DEEP if i % 3 == 0 else M_GRASS_GOLD if i % 3 == 1 else M_DIRT,
                  scale=(1.5, 1.4, 0.20))
# Scattered alpine flowers (gentian + poppies + buttercups)
for ai in range(120):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 50)
    ax_f = rad * math.cos(a); ay_f = rad * math.sin(a)
    fl_col = random.choice([M_GENTIAN_BLUE, M_POPPY_RED, M_BUTTERCUP])
    # Stem
    cyl(f"fl_st{ai}", r=0.015, depth=0.20, segs=6, loc=(ax_f, ay_f, 0.20),
        mat_=M_GRASS_DEEP)
    # Flower head
    for pp in range(5):
        pa = (pp / 5.0) * math.pi * 2
        smooth_sphere(f"fl_p{ai}_{pp}", r=0.04,
                      loc=(ax_f + math.cos(pa)*0.05, ay_f + math.sin(pa)*0.05, 0.32),
                      mat_=fl_col, scale=(1, 1, 0.5))

# ============ LAKE alpine (signature turquoise) ============
lake_e = empty("lake", loc=(20, -20, 0))
# Lake shape (kidney bean)
lake_main = smooth_sphere("lake_main", r=12, segs=24, rings=16, loc=(0, 0, 0.10),
                          parent=lake_e, mat_=M_LAKE, scale=(1.3, 0.85, 0.05))
lake_deep = smooth_sphere("lake_d", r=10, segs=22, rings=14, loc=(0, 0, 0.15),
                          parent=lake_e, mat_=M_LAKE_DEEP, scale=(1.2, 0.8, 0.03))
# Lake reflection ripples
for ri in range(15):
    ra_l = random.uniform(0, math.pi*2)
    rr_l = random.uniform(2, 11)
    cyl(f"ripple{ri}", r=random.uniform(0.20, 0.40), depth=0.04, segs=14,
        loc=(rr_l*math.cos(ra_l), rr_l*math.sin(ra_l), 0.18),
        parent=lake_e, mat_=M_SNOW_BLUE)

# ============ CHALET SUISSE (signature wood balcony shutters) ============
chalet_e = empty("chalet", loc=(-12, -10, 0))
# Stone base
beveled_cube("c_base", (7, 5, 0.8), bevel_offset=0.10, loc=(0, 0, 0.4),
             parent=chalet_e, mat_=M_ROCK_MT)
# Lower floor white plaster
beveled_cube("c_lower", (7, 5, 2.2), bevel_offset=0.08, loc=(0, 0, 1.9),
             parent=chalet_e, mat_=M_WHITE_PLASTER)
# Upper floor wood (signature)
beveled_cube("c_upper", (7.2, 5.2, 1.8), bevel_offset=0.08, loc=(0, 0, 3.9),
             parent=chalet_e, mat_=M_CHALET_WOOD)
# Wood plank lines on upper floor
for pi in range(7):
    py_p = -2.4 + pi * 0.8
    beveled_cube(f"c_pl{pi}", (7.3, 5.3, 0.04), bevel_offset=0.01,
                 loc=(0, 0, 3.1 + pi*0.25), parent=chalet_e, mat_=M_CHALET_DARK)
# Wide overhanging roof (signature alpine)
for ri in range(5):
    rw = 9 - ri * 0.3
    rl = 7 - ri * 0.3
    beveled_cube(f"c_r{ri}", (rw, rl, 0.20), bevel_offset=0.04,
                 loc=(0, 0, 5.0 + ri*0.40), parent=chalet_e, mat_=M_ROOF_DARK)
# Sloped sides
for side in (-1, 1):
    # Left/right slope
    sl_e = empty(f"c_sl{side}_e", (0, side*2.5, 5.0), parent=chalet_e)
    for ri in range(6):
        sw_y = 7 - ri * 0.5
        beveled_cube(f"c_sl{side}_{ri}", (8, sw_y * 0.10, 0.20), bevel_offset=0.03,
                     loc=(0, side*ri*0.20, ri*0.30), parent=sl_e, mat_=M_ROOF_DARK)
# Triangular gable
for gi in range(6):
    gy_p = (6 - gi) * 0.30
    gw_p = 7 - gi
    beveled_cube(f"c_gable{gi}", (gw_p, 0.20, 0.40), bevel_offset=0.04,
                 loc=(0, 2.55, 5.5 + gi*0.40), parent=chalet_e, mat_=M_CHALET_WOOD)

# 4 Windows + RED SHUTTERS (signature)
for wp_x, wp_y in [(-2, -2.55), (2, -2.55), (-2, 2.55), (2, 2.55)]:
    # Window
    beveled_cube(f"win_{wp_x}_{wp_y}", (0.9, 0.10, 1.0), bevel_offset=0.04,
                 loc=(wp_x, wp_y, 3.9), parent=chalet_e, mat_=M_WINDOW_GLASS)
    # Window frame
    beveled_cube(f"winf_{wp_x}_{wp_y}", (1.0, 0.12, 1.1), bevel_offset=0.03,
                 loc=(wp_x, wp_y + 0.01 * (1 if wp_y > 0 else -1), 3.9),
                 parent=chalet_e, mat_=M_CHALET_DARK)
    # Red shutters (signature)
    for s_side in (-1, 1):
        beveled_cube(f"sh_{wp_x}_{wp_y}_{s_side}", (0.50, 0.08, 1.1), bevel_offset=0.04,
                     loc=(wp_x + s_side*0.7, wp_y, 3.9),
                     parent=chalet_e, mat_=M_SHUTTER_RED)
        # Shutter heart cutout
        smooth_sphere(f"sh_heart_{wp_x}_{wp_y}_{s_side}", r=0.10,
                      loc=(wp_x + s_side*0.7, wp_y - 0.05 * (1 if wp_y > 0 else -1), 3.9),
                      parent=chalet_e, mat_=M_CHALET_BEAM)

# Wood balcony (signature carved railing)
beveled_cube("balcony", (8, 1.5, 0.20), bevel_offset=0.04, loc=(0, 2.7, 3.0),
             parent=chalet_e, mat_=M_CHALET_WOOD)
# Carved railing posts
for bi in range(15):
    bx_p = -3.8 + bi * 0.55
    cyl(f"bal_p{bi}", r=0.05, depth=0.8, segs=8, loc=(bx_p, 3.4, 3.5),
        parent=chalet_e, mat_=M_CHALET_BEAM)
# Top railing
beveled_cube("bal_top", (8, 0.10, 0.10), bevel_offset=0.02, loc=(0, 3.4, 4.0),
             parent=chalet_e, mat_=M_CHALET_WOOD)
# Geranium flowers on balcony (signature alpine chalet)
for gi in range(12):
    gx_p = -3.5 + gi * 0.65
    # Pot
    cyl(f"pot{gi}", r=0.10, depth=0.18, segs=10, loc=(gx_p, 3.40, 3.15),
        parent=chalet_e, mat_=M_CHALET_DARK)
    # Geranium cluster
    for fi in range(5):
        fa = (fi / 5.0) * math.pi * 2
        smooth_sphere(f"ger{gi}_{fi}", r=0.06,
                      loc=(gx_p + math.cos(fa)*0.06, 3.40 + math.sin(fa)*0.06, 3.30),
                      parent=chalet_e, mat_=M_GERANIUM)
# Door front
beveled_cube("door", (1.0, 0.10, 2.0), bevel_offset=0.04, loc=(0, -2.55, 2.0),
             parent=chalet_e, mat_=M_CHALET_DARK)
# Door handle
smooth_sphere("d_handle", r=0.06, loc=(0.40, -2.62, 2.0), parent=chalet_e, mat_=M_BELL_GOLD)
# Wood beams diagonals signature (cross pattern on upper)
for side in (-1, 1):
    for sx in [-2.0, 2.0]:
        beam_e = empty(f"beam_{side}_{sx}_e", (sx, side*2.6, 4.5), parent=chalet_e)
        beam_e.rotation_euler = (0, math.radians(35), 0)
        beveled_cube(f"beam_{side}_{sx}", (2.0, 0.10, 0.10), bevel_offset=0.02,
                     loc=(0, 0, 0), parent=beam_e, mat_=M_CHALET_BEAM)

# ============ 6 BROWN COWS with cowbells signature ============
def make_cow_swiss(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body brown
    smooth_sphere(f"{name}_body", r=0.7*scale, segs=20, rings=14, loc=(0, 0, 1.2*scale),
                  parent=base, mat_=M_COW_BR, scale=(1.7, 1.0, 1.0))
    # White patches (signature swiss cow)
    for pp in range(6):
        pa = random.uniform(0, math.pi*2)
        pe = random.uniform(0.3, math.pi - 0.3)
        pxc = math.sin(pe) * math.cos(pa) * 0.85*scale
        pyc = math.sin(pe) * math.sin(pa) * 0.55*scale
        pzc = math.cos(pe) * 0.55*scale + 1.2*scale
        smooth_sphere(f"{name}_pa{pp}", r=random.uniform(0.18, 0.25)*scale,
                      loc=(pxc, pyc, pzc), parent=base, mat_=M_COW_WHITE_PATCH,
                      scale=(1.2, 1, 0.3))
    # 4 legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}{y}", r=0.10*scale, depth=1.2*scale, segs=10,
                loc=(x*0.55*scale, y*0.35*scale, 0.6*scale), parent=base, mat_=M_COW_BR)
            # Hoof black
            cyl(f"{name}_h{x}{y}", r=0.12*scale, depth=0.10*scale, segs=10,
                loc=(x*0.55*scale, y*0.35*scale, 0.05*scale), parent=base, mat_=M_LEDER_DARK)
    # Head
    head_e = empty(f"{name}_he", (1.1*scale, 0, 1.35*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.30*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_COW_BR, scale=(1.4, 0.9, 1.0))
    # White face patch
    smooth_sphere(f"{name}_fp", r=0.20*scale, loc=(0.10*scale, 0, 0),
                  parent=head_e, mat_=M_COW_WHITE_PATCH, scale=(1.4, 0.7, 0.9))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.22*scale, loc=(0.32*scale, 0, -0.10*scale),
                  parent=head_e, mat_=M_COW_BR, scale=(1.1, 0.8, 0.7))
    # Nose
    smooth_sphere(f"{name}_nose", r=0.06*scale, loc=(0.50*scale, 0, -0.05*scale),
                  parent=head_e, mat_=M_COW_NOSE_S)
    # Horns
    for side in (-1, 1):
        h_e = empty(f"{name}_h{side}_e", (-0.05*scale, side*0.15*scale, 0.20*scale), parent=head_e)
        h_e.rotation_euler = (math.radians(side*-10), 0, math.radians(side*20))
        cyl(f"{name}_horn{side}", r=0.035*scale, depth=0.30*scale, segs=8,
            loc=(0, 0, 0.15*scale), parent=h_e, mat_=M_COW_HORN_S)
        smooth_cone(f"{name}_horn_tip{side}", r1=0.025*scale, r2=0.005*scale, depth=0.10*scale, segs=8,
                    loc=(0, 0, 0.35*scale), parent=h_e, mat_=M_COW_HORN_S)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.10*scale,
                      loc=(-0.05*scale, side*0.30*scale, 0.10*scale),
                      parent=head_e, mat_=M_COW_BR, scale=(0.5, 1.2, 0.9))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04*scale,
                      loc=(0.18*scale, side*0.15*scale, 0.05*scale), parent=head_e, mat_=M_EYE_DARK_A)

    # COWBELL signature (around neck)
    bell_e = empty(f"{name}_bell_e", (0.55*scale, 0, 1.20*scale), parent=base)
    # Bell shape (truncated cone)
    smooth_cone(f"{name}_bell", r1=0.15*scale, r2=0.20*scale, depth=0.22*scale, segs=14,
                loc=(0, 0, -0.10*scale), parent=bell_e, mat_=M_BELL_GOLD)
    # Bell strap
    cyl(f"{name}_strap", r=0.025*scale, depth=0.30*scale, segs=8, loc=(0, 0, 0.05*scale),
        parent=bell_e, mat_=M_LEDER_BROWN)
    # Bell handle/ring
    cyl(f"{name}_ring", r=0.05*scale, depth=0.02*scale, segs=10, loc=(0, 0, 0.18*scale),
        parent=bell_e, mat_=M_BELL_DARK).rotation_euler = (math.radians(90), 0, 0)
    # Clapper
    cyl(f"{name}_clapper", r=0.02*scale, depth=0.15*scale, segs=8, loc=(0, 0, -0.05*scale),
        parent=bell_e, mat_=M_BELL_DARK)
    # Tail
    cyl(f"{name}_tail", r=0.04*scale, depth=0.7*scale, segs=8, loc=(-1.05*scale, 0, 1.20*scale),
        parent=base, mat_=M_COW_BR)
    smooth_sphere(f"{name}_tt", r=0.08*scale, loc=(-1.05*scale, 0, 0.75*scale),
                  parent=base, mat_=M_COW_NOSE_S)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "bell": bell_e}

cows_swiss = []
cow_pos_sw = [(-5, -22, math.radians(45)), (5, -22, math.radians(-45)),
              (-8, -28, math.radians(60)), (8, -28, math.radians(-60)),
              (-12, -18, math.radians(30)), (12, -18, math.radians(-30))]
for i, (cx, cy, fac) in enumerate(cow_pos_sw):
    c = make_cow_swiss(f"swcow{i}", (cx, cy, 0), scale=1.0, facing=fac)
    cows_swiss.append(c)

# ============ 2 GOATS ============
def make_goat(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.4*scale, segs=18, rings=12, loc=(0, 0, 0.8*scale),
                  parent=base, mat_=M_GOAT_WHITE, scale=(1.6, 0.85, 1.0))
    # Grey patches
    smooth_sphere(f"{name}_pa1", r=0.25*scale, loc=(0.2*scale, 0, 1.0*scale),
                  parent=base, mat_=M_GOAT_GREY, scale=(1, 0.6, 0.6))
    # 4 legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}{y}", r=0.05*scale, depth=0.8*scale, segs=8,
                loc=(x*0.30*scale, y*0.20*scale, 0.4*scale), parent=base, mat_=M_GOAT_WHITE)
    # Head
    head_e = empty(f"{name}_he", (0.55*scale, 0, 0.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.20*scale, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_GOAT_WHITE, scale=(1.5, 0.85, 0.95))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.13*scale, loc=(0.22*scale, 0, -0.06*scale),
                  parent=head_e, mat_=M_GOAT_WHITE, scale=(1.2, 0.7, 0.7))
    # Beard
    cyl(f"{name}_beard", r=0.04*scale, depth=0.15*scale, segs=8, loc=(0.25*scale, 0, -0.18*scale),
        parent=head_e, mat_=M_GOAT_WHITE)
    # Curved horns (signature)
    for side in (-1, 1):
        h_e = empty(f"{name}_h{side}_e", (-0.05*scale, side*0.08*scale, 0.15*scale), parent=head_e)
        h_e.rotation_euler = (math.radians(side*-30), 0, math.radians(side*30))
        for hi in range(4):
            cyl(f"{name}_h{side}_{hi}", r=0.025*scale - hi*0.003, depth=0.10*scale, segs=8,
                loc=(math.sin(hi*0.5)*0.04*scale, 0, hi*0.10*scale), parent=h_e, mat_=M_GOAT_HORN)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(0.12*scale, side*0.10*scale, 0.04*scale), parent=head_e, mat_=M_EYE_DARK_A)
    # Tail
    cyl(f"{name}_tail", r=0.025*scale, depth=0.15*scale, segs=6, loc=(-0.55*scale, 0, 0.85*scale),
        parent=base, mat_=M_GOAT_WHITE).rotation_euler = (math.radians(60), 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

goats = []
goat_pos = [(-25, 15, math.radians(45)), (-30, 18, math.radians(-30))]
for i, (gx, gy, fac) in enumerate(goat_pos):
    g = make_goat(f"goat{i}", (gx, gy, 0), scale=1.0, facing=fac)
    goats.append(g)

# ============ 4 YODELERS (2 men lederhosen + 2 women dirndl) ============
def make_yodeler_man(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Lederhosen shorts brown
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.13*scale, depth=0.6*scale, segs=10,
            loc=(side*0.13*scale, 0, 0.3*scale), parent=base, mat_=M_LEDER_BROWN)
        # Knee socks white
        cyl(f"{name}_sock{side}", r=0.10*scale, depth=0.6*scale, segs=10,
            loc=(side*0.13*scale, 0, 0.7*scale), parent=base, mat_=M_SHIRT_WHITE)
        # Boots
        beveled_cube(f"{name}_boot{side}", (0.10*scale, 0.18*scale, 0.06*scale), bevel_offset=0.01,
                     loc=(side*0.13*scale, 0, 0), parent=base, mat_=M_BOOTS)
    # Lederhosen suspenders (signature)
    for side in (-1, 1):
        susp_e = empty(f"{name}_susp{side}_e", (side*0.20*scale, 0, 1.40*scale), parent=base)
        susp_e.rotation_euler = (math.radians(side*5), math.radians(side*5), math.radians(side*15))
        beveled_cube(f"{name}_susp{side}", (0.05*scale, 0.05*scale, 0.5*scale), bevel_offset=0.01,
                     loc=(0, 0, 0), parent=susp_e, mat_=M_LEDER_BROWN)
        # Trim
        beveled_cube(f"{name}_susp_t{side}", (0.06*scale, 0.06*scale, 0.10*scale), bevel_offset=0.01,
                     loc=(0, 0, 0.25*scale), parent=susp_e, mat_=M_LEDER_TRIM)
    # Front leather panel (signature)
    beveled_cube(f"{name}_pan", (0.30*scale, 0.10*scale, 0.40*scale), bevel_offset=0.04,
                 loc=(0, -0.18*scale, 0.85*scale), parent=base, mat_=M_LEDER_BROWN)
    # Embroidery trim
    beveled_cube(f"{name}_emb", (0.32*scale, 0.06*scale, 0.04*scale), bevel_offset=0.01,
                 loc=(0, -0.20*scale, 1.00*scale), parent=base, mat_=M_LEDER_TRIM)
    # Shirt white
    smooth_cone(f"{name}_shirt", r1=0.28*scale, r2=0.30*scale, depth=0.55*scale, segs=14,
                loc=(0, 0, 1.45*scale), parent=base, mat_=M_SHIRT_WHITE)
    # Arms raised (singing yodel pose)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.70*scale), parent=base)
        sh.rotation_euler = (math.radians(-130 - side*10), 0, math.radians(side*-40))
        cyl(f"{name}_uarm{side_idx}", r=0.06*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=M_SHIRT_WHITE)
        cyl(f"{name}_fa{side_idx}", r=0.05*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_PALE_S)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.0*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_PALE_S)
    # Mouth open singing (signature)
    smooth_sphere(f"{name}_mouth", r=0.05*scale, loc=(0, -0.18*scale, -0.08*scale),
                  parent=head_e, mat_=M_LEDER_DARK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.04*scale), parent=head_e, mat_=M_EYE_DARK_A)
    # Hair
    for hi in range(8):
        ha = (hi / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.06*scale,
                      loc=(math.cos(ha)*0.13*scale, math.sin(ha)*0.10*scale, 0.10*scale),
                      parent=head_e, mat_=M_HAIR_BL)
    # Tyrolean HAT GREEN with feather (signature)
    hat_e = empty(f"{name}_hat", (0, 0, 0.20*scale), parent=head_e)
    cyl(f"{name}_brim", r=0.22*scale, depth=0.04*scale, segs=16, loc=(0, 0, 0),
        parent=hat_e, mat_=M_HAT_GREEN)
    smooth_cone(f"{name}_crown", r1=0.17*scale, r2=0.15*scale, depth=0.25*scale, segs=14,
                loc=(0, 0, 0.13*scale), parent=hat_e, mat_=M_HAT_GREEN)
    # Tyrolean feather
    smooth_cone(f"{name}_feather", r1=0.05*scale, r2=0.005*scale, depth=0.30*scale, segs=10,
                loc=(0.18*scale, 0.05*scale, 0.15*scale), parent=hat_e,
                mat_=M_BELL_GOLD).rotation_euler = (math.radians(15), 0, math.radians(20))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

def make_yodeler_woman(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    dirndl_main = random.choice([M_DIRNDL_RED, M_DIRNDL_BLUE])
    # Long flared skirt (signature dirndl)
    smooth_cone(f"{name}_skirt", r1=0.55*scale, r2=0.30*scale, depth=1.0*scale, segs=18,
                loc=(0, 0, 0.6*scale), parent=base, mat_=dirndl_main)
    # White apron over (signature)
    apron = smooth_cone(f"{name}_apron", r1=0.45*scale, r2=0.28*scale, depth=0.9*scale, segs=18,
                        loc=(0, -0.15*scale, 0.6*scale), parent=base, mat_=M_DIRNDL_APRON)
    apron.scale = (1, 0.4, 1)
    # Belt
    cyl(f"{name}_belt", r=0.30*scale, depth=0.10*scale, segs=16, loc=(0, 0, 1.15*scale),
        parent=base, mat_=M_LEDER_DARK)
    # White blouse
    smooth_cone(f"{name}_blouse", r1=0.28*scale, r2=0.30*scale, depth=0.45*scale, segs=14,
                loc=(0, 0, 1.45*scale), parent=base, mat_=M_BLOUSE_WHITE)
    # Bodice dirndl over blouse
    smooth_cone(f"{name}_bodice", r1=0.30*scale, r2=0.32*scale, depth=0.40*scale, segs=14,
                loc=(0, 0, 1.50*scale), parent=base, mat_=dirndl_main)
    # Front lacing
    for li in range(4):
        cyl(f"{name}_lc{li}", r=0.01*scale, depth=0.05*scale, segs=6,
            loc=(0, -0.30*scale, 1.40*scale + li*0.10*scale), parent=base, mat_=M_LEDER_TRIM).rotation_euler = (math.radians(90), 0, 0)
    # Long sleeves
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.28*scale, 0, 1.70*scale), parent=base)
        sh.rotation_euler = (math.radians(-120 - side*10), 0, math.radians(side*-30))
        cyl(f"{name}_uarm{side_idx}", r=0.06*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=M_BLOUSE_WHITE)
        cyl(f"{name}_fa{side_idx}", r=0.05*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_PALE_S)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.0*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_PALE_S)
    # Mouth open singing
    smooth_sphere(f"{name}_mouth", r=0.04*scale, loc=(0, -0.18*scale, -0.08*scale),
                  parent=head_e, mat_=M_TIE_RED)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.04*scale), parent=head_e, mat_=M_EYE_DARK_A)
    # Braided pigtails signature
    for side in (-1, 1):
        for bi in range(4):
            smooth_sphere(f"{name}_pt{side}_{bi}", r=0.05*scale,
                          loc=(side*0.20*scale, 0.05*scale, -0.05*scale - bi*0.10*scale),
                          parent=head_e, mat_=M_HAIR_BL)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

yodelers = []
yodeler_pos = [(-8, 5, math.radians(0)), (8, 5, math.radians(0))]
for i, (yx, yy, fac) in enumerate(yodeler_pos):
    y = make_yodeler_man(f"yman{i}", (yx, yy, 0), scale=1.0, facing=fac)
    yodelers.append(y)
yodeler_w_pos = [(-3, 7, math.radians(0)), (3, 7, math.radians(0))]
for i, (yx, yy, fac) in enumerate(yodeler_w_pos):
    y = make_yodeler_woman(f"ywoman{i}", (yx, yy, 0), scale=1.0, facing=fac)
    yodelers.append(y)

# ============ ALPHORN (signature massive 3m) ============
alphorn_e = empty("alphorn", loc=(0, 12, 0))
# Bend angle (signature angled up at end)
# Body segments
for ai in range(10):
    ai_z = ai * 0.30
    ai_y = 0
    ai_r_start = 0.05 + ai * 0.012
    cyl(f"ah_b{ai}", r=ai_r_start, depth=0.32, segs=14, loc=(0, ai_y, ai_z),
        parent=alphorn_e, mat_=M_ALPHORN_WOOD)
# Long horizontal section
horn_h_e = empty("ah_horiz_e", (0, 0, 3.0), parent=alphorn_e)
horn_h_e.rotation_euler = (math.radians(-90), 0, 0)
for ai in range(8):
    ai_d = ai * 0.40
    ai_r_h = 0.10 + ai * 0.02
    cyl(f"ah_h{ai}", r=ai_r_h, depth=0.42, segs=14, loc=(0, ai_d, 0),
        parent=horn_h_e, mat_=M_ALPHORN_WOOD)
# Bell flared at end (signature)
smooth_cone("ah_bell", r1=0.30, r2=0.10, depth=0.5, segs=18, loc=(0, 3.2, 0),
            parent=horn_h_e, mat_=M_ALPHORN_WOOD)
# Decorative bands (signature)
for bi in range(6):
    by_b = 0.5 + bi * 0.45
    cyl(f"ah_band{bi}", r=0.12 + bi * 0.025, depth=0.06, segs=14, loc=(0, by_b, 0),
        parent=horn_h_e, mat_=M_ALPHORN_DARK)
# Mouthpiece
cyl("ah_mp", r=0.04, depth=0.10, segs=10, loc=(0, 0, 0),
    parent=alphorn_e, mat_=M_ALPHORN_DARK)
# Support stand
beveled_cube("ah_stand", (0.4, 0.4, 0.05), bevel_offset=0.02, loc=(0, 0, -0.02),
             parent=alphorn_e, mat_=M_LEDER_BROWN)

# ============ 4 HIKERS (signature backpacks + poles) ============
def make_hiker(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    pack_color = random.choice(PACK_COLORS)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.10*scale, depth=1.0*scale, segs=10,
            loc=(side*0.12*scale, 0, 0.5*scale), parent=base, mat_=M_LEDER_BROWN)
        # Boots
        beveled_cube(f"{name}_boot{side}", (0.10*scale, 0.18*scale, 0.06*scale), bevel_offset=0.01,
                     loc=(side*0.12*scale, 0, 0), parent=base, mat_=M_BOOTS)
    # Jacket
    smooth_cone(f"{name}_jacket", r1=0.28*scale, r2=0.30*scale, depth=0.60*scale, segs=14,
                loc=(0, 0, 1.30*scale), parent=base, mat_=pack_color)
    # Backpack (signature)
    smooth_sphere(f"{name}_pack", r=0.28*scale, segs=18, rings=12, loc=(0, 0.30*scale, 1.45*scale),
                  parent=base, mat_=pack_color, scale=(0.9, 0.7, 1.3))
    # Pack straps
    for side in (-1, 1):
        beveled_cube(f"{name}_st{side}", (0.04*scale, 0.20*scale, 0.5*scale), bevel_offset=0.01,
                     loc=(side*0.15*scale, 0.10*scale, 1.30*scale), parent=base, mat_=M_LEDER_DARK)
    # Arm with hiking pole
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.60*scale), parent=base)
        sh.rotation_euler = (math.radians(-30 + side*20), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side_idx}", r=0.06*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=pack_color)
        cyl(f"{name}_fa{side_idx}", r=0.05*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_PALE_S)
        # Pole
        if side_idx == 0:
            cyl(f"{name}_pole{side_idx}", r=0.012*scale, depth=1.4*scale, segs=6,
                loc=(0, 0, -1.25*scale), parent=sh, mat_=M_POLE)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.90*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_PALE_S)
    # Cap
    cyl(f"{name}_cap", r=0.20*scale, depth=0.04*scale, segs=14, loc=(0, 0, 0.20*scale),
        parent=head_e, mat_=pack_color)
    smooth_sphere(f"{name}_cap_t", r=0.18*scale, loc=(0, 0, 0.22*scale),
                  parent=head_e, mat_=pack_color, scale=(1, 1, 0.7))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.03*scale), parent=head_e, mat_=M_EYE_DARK_A)
    base["_phase"] = random.uniform(0, math.pi*2)
    base["_speed"] = random.uniform(0.6, 1.2)
    return {"root": base, "he": head_e}

hikers = []
hiker_pos = [(-30, -5, math.radians(45)), (35, 0, math.radians(-30)),
              (-35, 8, math.radians(60)), (32, 12, math.radians(-60))]
for i, (hx, hy, fac) in enumerate(hiker_pos):
    h = make_hiker(f"hiker{i}", (hx, hy, 0), scale=1.0, facing=fac)
    hikers.append(h)

# ============ 8 FIR TREES (signature pointed pine) ============
for ti in range(8):
    ta = (ti / 8.0) * math.pi * 2 + math.pi/8
    tx = math.cos(ta) * 40 + random.uniform(-3, 3)
    ty = math.sin(ta) * 40 + random.uniform(-3, 3)
    # Avoid road/lake
    if -25 < tx < 35 and -35 < ty < -10: continue
    t_e = empty(f"fir{ti}", (tx, ty, 0))
    # Trunk
    cyl(f"fir{ti}_t", r=0.30, depth=2.5, segs=12, loc=(0, 0, 1.25), parent=t_e, mat_=M_TRUNK_PINE)
    # Layered cone canopy
    for li in range(6):
        lz = 2 + li * 1.5
        lr = 2.5 - li * 0.35
        smooth_cone(f"fir{ti}_l{li}", r1=lr, r2=0.10, depth=2.0, segs=14, loc=(0, 0, lz),
                    parent=t_e, mat_=M_FIR_DARK if li % 2 == 0 else M_FIR_BRIGHT)

# ============ CHAIRLIFT (signature) ============
# 4 pylons
pylons = []
for pi, (px_p, py_p) in enumerate([(30, 35), (15, 25), (0, 15), (-15, 5)]):
    py_e = empty(f"pylon{pi}", (px_p, py_p, 0))
    # Tower
    cyl(f"py{pi}_t", r=0.25, depth=15, segs=12, loc=(0, 0, 7.5), parent=py_e, mat_=M_LIFT_PYLON)
    # Top wheel housing
    beveled_cube(f"py{pi}_top", (0.8, 0.8, 0.4), bevel_offset=0.04, loc=(0, 0, 15.2), parent=py_e, mat_=M_LIFT_PYLON)
    # Wheel
    cyl(f"py{pi}_w", r=0.5, depth=0.20, segs=14, loc=(0, 0, 15.2), parent=py_e, mat_=M_LIFT_RED).rotation_euler = (math.radians(90), 0, 0)
    pylons.append(py_e)

# Cable segments between pylons
pylon_data = [(30, 35), (15, 25), (0, 15), (-15, 5)]
for ci in range(len(pylon_data) - 1):
    px1, py1 = pylon_data[ci]; px2, py2 = pylon_data[ci+1]
    midx = (px1+px2)/2; midy = (py1+py2)/2
    cl = math.sqrt((px2-px1)**2 + (py2-py1)**2)
    cang = math.atan2(py2-py1, px2-px1)
    cable = cyl(f"cable{ci}", r=0.04, depth=cl, segs=8, loc=(midx, midy, 15.2),
                mat_=M_LIFT_CABLE)
    cable.rotation_euler = (math.radians(90), 0, cang + math.radians(90))

# Chairs hanging
for chi in range(5):
    chf = chi / 4.0
    ch_x = 30 - chf * 45
    ch_y = 35 - chf * 30
    chair_e = empty(f"chair{chi}", (ch_x, ch_y, 14))
    # Hanger
    cyl(f"ch{chi}_h", r=0.05, depth=1.2, segs=8, loc=(0, 0, 0.6),
        parent=chair_e, mat_=M_LIFT_PYLON)
    # Bar
    cyl(f"ch{chi}_b", r=0.08, depth=2, segs=10, loc=(0, 0, 0),
        parent=chair_e, mat_=M_LIFT_RED).rotation_euler = (0, math.radians(90), 0)
    # Seat
    beveled_cube(f"ch{chi}_s", (2, 1, 0.10), bevel_offset=0.03, loc=(0, 0, -0.4),
                 parent=chair_e, mat_=M_LIFT_RED)
    # Back
    beveled_cube(f"ch{chi}_back", (2, 0.10, 0.8), bevel_offset=0.03, loc=(0, -0.4, 0),
                 parent=chair_e, mat_=M_LIFT_RED)
    chair_e["_phase"] = random.uniform(0, math.pi*2)

# ============================================================
# ⭐ 600 EDELWEISS + 400 COWBELLS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
edelweiss_particles = []
for i in range(600):
    px = random.uniform(-60, 60)
    py = random.uniform(-60, 60)
    pz = random.uniform(0.5, 14)
    ed_e = empty(f"ed{i}", (px, py, pz))
    # Center yellow
    smooth_sphere(f"ed_c{i}", r=0.05, segs=10, rings=6, loc=(0, 0, 0),
                  parent=ed_e, mat_=M_EDELWEISS_YEL)
    # 8 petals signature star shape
    for pp in range(8):
        pa = (pp / 8.0) * math.pi * 2
        smooth_sphere(f"ed_p{i}_{pp}", r=0.06,
                      loc=(math.cos(pa)*0.10, math.sin(pa)*0.10, 0),
                      parent=ed_e, mat_=M_EDELWEISS_W, scale=(1.4, 0.7, 0.3))
    ed_e["_phase"] = random.uniform(0, math.pi*2)
    ed_e["_base_x"] = px; ed_e["_base_y"] = py; ed_e["_base_z"] = pz
    ed_e["_amp_x"] = random.uniform(1.0, 2.5)
    ed_e["_amp_y"] = random.uniform(1.0, 2.5)
    ed_e["_amp_z"] = random.uniform(0.4, 1.0)
    ed_e["_speed"] = random.uniform(0.3, 0.7)
    edelweiss_particles.append(ed_e)

# 400 cowbells suspended ringing
cowbells_part = []
for i in range(400):
    px = random.uniform(-50, 50)
    py = random.uniform(-50, 50)
    pz = random.uniform(2, 16)
    bell_e = empty(f"cb{i}", (px, py, pz))
    # Bell shape
    smooth_cone(f"cb_b{i}", r1=0.10, r2=0.15, depth=0.20, segs=12,
                loc=(0, 0, 0), parent=bell_e, mat_=M_BELL_GOLD)
    # Top loop
    cyl(f"cb_l{i}", r=0.04, depth=0.02, segs=10, loc=(0, 0, 0.12),
        parent=bell_e, mat_=M_BELL_DARK).rotation_euler = (math.radians(90), 0, 0)
    # Clapper inside
    cyl(f"cb_c{i}", r=0.02, depth=0.10, segs=6, loc=(0, 0, -0.05),
        parent=bell_e, mat_=M_BELL_DARK)
    bell_e["_phase"] = random.uniform(0, math.pi*2)
    bell_e["_base_x"] = px; bell_e["_base_y"] = py; bell_e["_base_z"] = pz
    bell_e["_amp_x"] = random.uniform(0.5, 1.5)
    bell_e["_amp_y"] = random.uniform(0.5, 1.5)
    bell_e["_amp_z"] = random.uniform(0.3, 0.8)
    bell_e["_speed"] = random.uniform(0.4, 0.9)
    cowbells_part.append(bell_e)

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

# Cows chew + tail + bell sway
for c in cows_swiss:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Body slight
        c["root"].location.z = math.sin(t * 0.6 + phase) * 0.03
        c["root"].keyframe_insert("location", frame=f)
        # Head chew motion
        c["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(5),
                                   0, math.cos(t * 1.0 + phase) * math.radians(8))
        c["he"].keyframe_insert("rotation_euler", frame=f)
        # Bell sway (signature ring)
        c["bell"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(15),
                                     math.cos(t * 2.5 + phase) * math.radians(12), 0)
        c["bell"].keyframe_insert("rotation_euler", frame=f)

# Goats nibble
for g in goats:
    phase = g["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        g["he"].rotation_euler = (math.radians(-30) + math.sin(t * 1.5 + phase) * math.radians(15), 0, 0)
        g["he"].keyframe_insert("rotation_euler", frame=f)

# Yodelers body sway + mouth pulse
for y in yodelers:
    phase = y["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        y["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(5), 0,
                                     y["root"].rotation_euler.z)
        y["root"].location.z = abs(math.sin(t * 2.0 + phase)) * 0.10
        y["root"].keyframe_insert("rotation_euler", frame=f)
        y["root"].keyframe_insert("location", frame=f)
        # Head pulse with yodel
        y["he"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(8),
                                   math.cos(t * 3.0 + phase) * math.radians(5), 0)
        y["he"].keyframe_insert("rotation_euler", frame=f)

# Alphorn vibrate
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    alphorn_e.rotation_euler = (math.sin(t * 4.0) * math.radians(2),
                                 math.cos(t * 4.0) * math.radians(2), 0)
    alphorn_e.keyframe_insert("rotation_euler", frame=f)

# Hikers walking
for h in hikers:
    phase = h["root"]["_phase"]; speed = h["root"]["_speed"]
    bx_h = h["root"].location.x; by_h = h["root"].location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        h["root"].location.x = bx_h + math.sin(t * speed + phase) * 0.8
        h["root"].location.y = by_h + math.cos(t * speed + phase) * 0.8
        h["root"].location.z = abs(math.sin(t * speed * 2.5 + phase)) * 0.1
        h["root"].keyframe_insert("location", frame=f)

# Chairlift chairs swing
for chi in range(5):
    chair = bpy.data.objects.get(f"chair{chi}")
    if chair is None: continue
    phase = chair["_phase"]
    bx_ch = chair.location.x; by_ch = chair.location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        chair.location.x = bx_ch - t * 1.5
        chair.location.y = by_ch - t * 1.0
        chair.rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(5), 0, 0)
        chair.keyframe_insert("location", frame=f)
        chair.keyframe_insert("rotation_euler", frame=f)

# 600 edelweiss drift slow
for ed in edelweiss_particles:
    phase = ed["_phase"]; speed = ed["_speed"]
    bx, by, bz = ed["_base_x"], ed["_base_y"], ed["_base_z"]
    ax, ay, az = ed["_amp_x"], ed["_amp_y"], ed["_amp_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        ed.location = (x, y, max(0.3, z))
        ed.rotation_euler = (t * 1.0 + phase, 0, t * 1.5 + phase)
        ed.keyframe_insert("location", frame=f)
        ed.keyframe_insert("rotation_euler", frame=f)

# 400 cowbells suspended ring (signature pendulum)
for cb in cowbells_part:
    phase = cb["_phase"]; speed = cb["_speed"]
    bx, by, bz = cb["_base_x"], cb["_base_y"], cb["_base_z"]
    ax, ay, az = cb["_amp_x"], cb["_amp_y"], cb["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase) * 0.3
        y = by + ay * math.cos(t * speed * 0.9 + phase) * 0.3
        z = bz + az * math.sin(t * speed * 1.4 + phase) * 0.3
        cb.location = (x, y, max(1, z))
        # Pendulum swing signature
        cb.rotation_euler = (math.sin(t * 4.0 + phase) * math.radians(25),
                              math.cos(t * 4.0 + phase) * math.radians(20),
                              0)
        cb.keyframe_insert("location", frame=f)
        cb.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_alps_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_swiss_alps_chalet_yodeling] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_swiss_alps_chalet_yodeling] Matterhorn + 2 mts + chalet wood balcony shutters + 6 brown cows + 2 goats + 2 men lederhosen + 2 women dirndl + alphorn 3m + 4 hikers + 8 firs + chairlift 5 chairs + 600 edelweiss + 400 cowbells")
print("⭐ FIXES: 1 ground + 600 edelweiss + 400 cowbells (signature Alps thematic mandatory) ⭐")
