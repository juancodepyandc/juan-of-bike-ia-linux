"""
proc_machu_picchu_inca_andes.py — 253e procédural AuroraIA (118e qualité)
Machu Picchu Inca Andes: ruins + terraces + temples + Intihuatana + 6 llamas + 4 Quechua women + chasqui + Inca chief + 8 mountain peaks + 600 sacred stones + 400 condors
FIXES : 1 ground + 600 sacred stones + 400 condors (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB253)

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

# Sky high altitude blue
M_SKY = mat("sky", (0.45, 0.65, 0.92, 1.0), 0.0, 0.7, emission=(0.45,0.65,0.92), emission_strength=1.8)
M_SKY_HZ = mat("sky_h", (0.75, 0.85, 0.92, 1.0), 0.0, 0.7, emission=(0.70,0.82,0.92), emission_strength=2.3)
M_SUN = mat("sun", (1.0, 0.95, 0.75, 1.0), 0.0, 0.1, emission=(1.0,0.95,0.75), emission_strength=15.0)

# Clouds
M_CLOUD_ANDES = mat("cloud", (0.95, 0.95, 0.95, 1.0), 0.0, 0.7, emission=(0.92,0.92,0.92), emission_strength=1.2)
M_MIST_ANDES = mat("mist", (0.85, 0.88, 0.92, 1.0), 0.0, 0.50, emission=(0.82,0.85,0.92), emission_strength=2.0, alpha=0.40)

# Mountain rock
M_ROCK_INCA = mat("rock", (0.42, 0.40, 0.38, 1.0), 0.0, 0.85, emission=(0.40,0.38,0.36), emission_strength=0.3)
M_ROCK_DARK_I = mat("rock_d", (0.28, 0.26, 0.24, 1.0), 0.0, 0.85)
M_ROCK_MOSS = mat("rock_m", (0.32, 0.48, 0.25, 1.0), 0.0, 0.80, emission=(0.30,0.45,0.25), emission_strength=0.4)

# Snow cap
M_SNOW_PEAK = mat("snow", (0.95, 0.96, 0.98, 1.0), 0.0, 0.30, emission=(0.92,0.94,0.96), emission_strength=1.0)

# Grass terraces
M_GRASS_TERRACE = mat("grass", (0.30, 0.55, 0.22, 1.0), 0.0, 0.80, emission=(0.28,0.52,0.22), emission_strength=0.4)
M_GRASS_BRIGHT = mat("grass_b", (0.42, 0.65, 0.30, 1.0), 0.0, 0.75, emission=(0.40,0.62,0.30), emission_strength=0.5)
M_DIRT_I = mat("dirt", (0.42, 0.28, 0.15, 1.0), 0.0, 0.85)

# Inca stone (signature precise cut polygonal)
M_STONE_INCA = mat("st_i", (0.55, 0.50, 0.42, 1.0), 0.0, 0.85, emission=(0.52,0.48,0.42), emission_strength=0.4)
M_STONE_DARK_I = mat("st_d", (0.38, 0.35, 0.30, 1.0), 0.0, 0.85)
M_STONE_LIGHT_I = mat("st_l", (0.72, 0.65, 0.55, 1.0), 0.0, 0.80, emission=(0.68,0.62,0.55), emission_strength=0.5)
M_STONE_GOLD_T = mat("st_g", (0.85, 0.65, 0.30, 1.0), 0.0, 0.55, emission=(0.80,0.62,0.30), emission_strength=0.8)

# Skin
M_SKIN_PERU = mat("skin", (0.62, 0.42, 0.25, 1.0), 0.0, 0.55, emission=(0.58,0.40,0.25), emission_strength=0.4)

# Hair black
M_HAIR_BLACK_P = mat("h_bk", (0.10, 0.06, 0.04, 1.0), 0.0, 0.55)

# Quechua textiles signature multicolor
M_TEXTILE_RED = mat("tx_r", (0.85, 0.15, 0.15, 1.0), 0.0, 0.65, emission=(0.80,0.15,0.15), emission_strength=0.7)
M_TEXTILE_PINK = mat("tx_p", (0.95, 0.55, 0.85, 1.0), 0.0, 0.65, emission=(0.92,0.52,0.82), emission_strength=0.6)
M_TEXTILE_GREEN = mat("tx_g", (0.20, 0.62, 0.30, 1.0), 0.0, 0.65, emission=(0.18,0.60,0.30), emission_strength=0.6)
M_TEXTILE_BLUE = mat("tx_b", (0.20, 0.45, 0.85, 1.0), 0.0, 0.65, emission=(0.18,0.42,0.80), emission_strength=0.6)
M_TEXTILE_YELLOW = mat("tx_y", (0.95, 0.85, 0.20, 1.0), 0.0, 0.55, emission=(0.92,0.82,0.20), emission_strength=0.7)
M_TEXTILE_ORANGE = mat("tx_o", (1.0, 0.55, 0.18, 1.0), 0.0, 0.55, emission=(1.0,0.55,0.18), emission_strength=0.7)
M_TEXTILE_PURPLE = mat("tx_pu", (0.62, 0.30, 0.85, 1.0), 0.0, 0.65, emission=(0.60,0.30,0.82), emission_strength=0.6)
TEXTILE_COLORS = [M_TEXTILE_RED, M_TEXTILE_PINK, M_TEXTILE_GREEN, M_TEXTILE_BLUE,
                  M_TEXTILE_YELLOW, M_TEXTILE_ORANGE, M_TEXTILE_PURPLE]

# Hat (signature montera round)
M_HAT_BROWN_P = mat("hat", (0.42, 0.25, 0.10, 1.0), 0.0, 0.75, emission=(0.40,0.25,0.10), emission_strength=0.4)
M_HAT_BRIM = mat("hat_b", (0.30, 0.18, 0.08, 1.0), 0.0, 0.85)

# Llama (signature)
M_LLAMA_WHITE = mat("ll_w", (0.92, 0.88, 0.82, 1.0), 0.0, 0.85, emission=(0.85,0.82,0.78), emission_strength=0.3)
M_LLAMA_BROWN = mat("ll_b", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85)
M_LLAMA_BLACK = mat("ll_bk", (0.18, 0.12, 0.08, 1.0), 0.0, 0.85)
M_LLAMA_PINK_NOSE = mat("ll_n", (0.55, 0.30, 0.30, 1.0), 0.0, 0.55)
LLAMA_VARIANTS = [M_LLAMA_WHITE, M_LLAMA_BROWN, M_LLAMA_BLACK]

# Inca chief
M_GOLD_INCA = mat("gold", (1.0, 0.85, 0.25, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.25), emission_strength=2.5)
M_INCA_TUNIC = mat("inca_t", (0.78, 0.20, 0.20, 1.0), 0.0, 0.65, emission=(0.72,0.20,0.20), emission_strength=0.6)
M_FEATHER_RED = mat("feat_r", (0.95, 0.30, 0.25, 1.0), 0.0, 0.45, emission=(0.92,0.30,0.25), emission_strength=1.5)
M_FEATHER_BLUE = mat("feat_b", (0.30, 0.55, 0.95, 1.0), 0.0, 0.45, emission=(0.30,0.52,0.92), emission_strength=1.5)
M_FEATHER_YELLOW = mat("feat_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.20), emission_strength=1.8)
M_FEATHER_GREEN = mat("feat_g", (0.30, 0.85, 0.40, 1.0), 0.0, 0.45, emission=(0.30,0.80,0.40), emission_strength=1.5)
FEATHER_COLORS_INCA = [M_FEATHER_RED, M_FEATHER_BLUE, M_FEATHER_YELLOW, M_FEATHER_GREEN]

# Condor
M_CONDOR_BLACK = mat("cond_b", (0.15, 0.12, 0.10, 1.0), 0.0, 0.65, emission=(0.15,0.12,0.10), emission_strength=0.3)
M_CONDOR_WHITE_COLLAR = mat("cond_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65)
M_CONDOR_BEAK = mat("cond_bk", (0.85, 0.78, 0.25, 1.0), 0.0, 0.55)
M_CONDOR_EYE = mat("cond_e", (1.0, 0.20, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.20,0.10), emission_strength=4.0)

# Sacred stone
M_STONE_SACRED = mat("st_sac", (0.85, 0.78, 0.55, 1.0), 0.3, 0.30, emission=(0.78,0.72,0.52), emission_strength=2.5)
M_STONE_GLOW = mat("st_glow", (1.0, 0.92, 0.55, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.55), emission_strength=5.0, alpha=0.65)

# Eye
M_EYE_DARK_I = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS = mat("lips", (0.78, 0.32, 0.32, 1.0), 0.0, 0.45)

# Stairs
M_STAIRS = mat("stairs", (0.45, 0.42, 0.38, 1.0), 0.0, 0.85)

# ============ SKY ============
sky = smooth_sphere("sky", r=300, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_h = smooth_sphere("sky_hz", r=250, segs=28, rings=16, loc=(0,0,8), mat_=M_SKY_HZ)
sky_h.scale = (1,1,0.18)
# Sun
sun = smooth_sphere("sun", r=4, segs=24, rings=18, loc=(-40, 80, 80), mat_=M_SUN)
# Clouds wisps signature
for ci in range(25):
    cax = random.uniform(-120, 120); cay = random.uniform(-120, 120)
    caz = random.uniform(35, 70)
    cloud_e = empty(f"cloud{ci}", (cax, cay, caz))
    for cli in range(random.randint(4, 7)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(2.5, 4.5), segs=16, rings=10,
                      loc=(random.uniform(-4, 4), random.uniform(-2, 2), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD_ANDES, scale=(1.8, 1.2, 0.6))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)

# ============ 8 ANDES MOUNTAIN PEAKS (signature Apus sacred) ============
def make_andes_peak(name, loc, height=30, base_w=20, snow_height=0.65):
    p_e = empty(name, loc)
    # Stepped mountain
    for li in range(12):
        lz = li * (height / 12.0)
        lr_p = base_w - li * (base_w * 0.8 / 12.0)
        # Mountain layer
        cyl(f"{name}_{li}", r=lr_p, depth=height/12.0, segs=8,
            loc=(0, 0, lz + height/24.0), parent=p_e,
            mat_=M_ROCK_INCA if li / 12.0 < snow_height else M_SNOW_PEAK)
    # Sharp peak
    smooth_cone(f"{name}_peak", r1=base_w*0.15, r2=0.2, depth=height*0.15, segs=10,
                loc=(0, 0, height), parent=p_e, mat_=M_SNOW_PEAK)
    # Random ridges
    for ri in range(8):
        ra = (ri / 8.0) * math.pi * 2
        rd = random.uniform(0.2, 0.6)
        rh = random.uniform(0.3, 0.8) * height
        beveled_cube(f"{name}_r{ri}", (1, base_w*rd, 2), bevel_offset=0.10,
                     loc=(math.cos(ra)*base_w*rd, math.sin(ra)*base_w*rd, rh),
                     parent=p_e, mat_=M_ROCK_DARK_I).rotation_euler = (0, 0, ra)
    return p_e

# 8 peaks around
peak_positions = [(-60, 50, 0, 30, 18, 0.55),
                  (60, 55, 0, 35, 20, 0.50),
                  (-80, -20, 0, 28, 15, 0.60),
                  (80, -15, 0, 32, 17, 0.55),
                  (-30, 90, 0, 25, 14, 0.65),
                  (40, 95, 0, 28, 16, 0.60),
                  (-100, 30, 0, 22, 12, 0.70),
                  (100, 25, 0, 26, 14, 0.62)]
for i, (px, py, pz, h, bw, sh) in enumerate(peak_positions):
    make_andes_peak(f"peak{i}", (px, py, pz), height=h, base_w=bw, snow_height=sh)

# ============ ONE clean stepped terrace ground ============
ground = beveled_cube("ground", (250, 250, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_GRASS_TERRACE)

# ============ TERRACES (signature Inca agricultural) ============
def make_terrace_set(loc, num_terraces=6, terrace_w=20, terrace_d=4, step_h=1.5):
    t_e = empty("terraces", loc)
    for ti in range(num_terraces):
        tz = ti * step_h
        # Terrace stone wall (signature dry stone)
        beveled_cube(f"tr_w{ti}", (terrace_w, 0.6, step_h), bevel_offset=0.15,
                     loc=(0, ti*terrace_d, tz + step_h/2), parent=t_e, mat_=M_STONE_INCA)
        # Terrace flat top (signature green agricultural)
        beveled_cube(f"tr_t{ti}", (terrace_w, terrace_d, 0.3), bevel_offset=0.10,
                     loc=(0, ti*terrace_d + terrace_d/2, tz + step_h - 0.15),
                     parent=t_e, mat_=M_GRASS_TERRACE if ti % 2 == 0 else M_GRASS_BRIGHT)
        # Detail rocks in wall
        for ri in range(8):
            rx_r = -terrace_w/2 + 0.5 + ri * (terrace_w/8)
            for rj in range(3):
                rz_r = tz + 0.2 + rj * (step_h-0.4)/2
                beveled_cube(f"tr_r{ti}_{ri}_{rj}", (0.5, 0.65, 0.40), bevel_offset=0.05,
                             loc=(rx_r, ti*terrace_d, rz_r), parent=t_e,
                             mat_=M_STONE_DARK_I if (ri+rj) % 2 == 0 else M_STONE_LIGHT_I)
        # Stairs at one end signature
        if ti < num_terraces - 1:
            for si in range(int(step_h*4)):
                beveled_cube(f"tr_st{ti}_{si}", (1.0, 0.3, 0.30), bevel_offset=0.03,
                             loc=(-terrace_w/2 + 0.5, ti*terrace_d + si*0.30, tz + si*step_h/4),
                             parent=t_e, mat_=M_STAIRS)
    return t_e

terraces_main = make_terrace_set((-15, -30, 0), num_terraces=8, terrace_w=30, terrace_d=4, step_h=1.5)
terraces_2 = make_terrace_set((20, -30, 0), num_terraces=6, terrace_w=25, terrace_d=4, step_h=1.5)

# ============ MACHU PICCHU RUINS (signature stone buildings) ============
ruins_e = empty("ruins", loc=(0, 20, 12))
# Central plaza
beveled_cube("plaza", (35, 25, 0.30), bevel_offset=0.10, loc=(0, 0, 0.15), parent=ruins_e, mat_=M_STONE_DARK_I)

# Buildings 1: Temple of the Sun (signature curved semicircular)
temple_sun_e = empty("temple_sun", (-10, 10, 0), parent=ruins_e)
# Curved wall
for ai in range(20):
    aa = math.pi * ai / 20.0
    wx_t = math.cos(aa) * 4
    wy_t = math.sin(aa) * 4
    beveled_cube(f"ts_w{ai}", (1.0, 0.6, 4), bevel_offset=0.10,
                 loc=(wx_t, wy_t, 2), parent=temple_sun_e,
                 mat_=M_STONE_INCA if ai % 2 == 0 else M_STONE_LIGHT_I).rotation_euler = (0, 0, aa)
# Front door
beveled_cube("ts_door", (1.5, 0.3, 3), bevel_offset=0.10, loc=(0, -3.8, 1.5),
             parent=temple_sun_e, mat_=M_STONE_DARK_I)
# Roof opening
cyl("ts_op", r=3.5, depth=0.2, segs=20, loc=(0, 0, 4), parent=temple_sun_e, mat_=M_STONE_LIGHT_I)

# Building 2: Royal Residence (signature rectangular)
royal_e = empty("royal", (10, 5, 0), parent=ruins_e)
beveled_cube("rl_w_l", (0.6, 8, 4), bevel_offset=0.10, loc=(-3, 0, 2), parent=royal_e, mat_=M_STONE_INCA)
beveled_cube("rl_w_r", (0.6, 8, 4), bevel_offset=0.10, loc=(3, 0, 2), parent=royal_e, mat_=M_STONE_INCA)
beveled_cube("rl_w_f", (6, 0.6, 4), bevel_offset=0.10, loc=(0, -4, 2), parent=royal_e, mat_=M_STONE_INCA)
beveled_cube("rl_w_b", (6, 0.6, 4), bevel_offset=0.10, loc=(0, 4, 2), parent=royal_e, mat_=M_STONE_INCA)
# Trapezoidal doorways (signature Inca)
for side, sx in [("F", 0)]:
    beveled_cube(f"rl_door_{side}", (1.5, 0.65, 2.5), bevel_offset=0.10,
                 loc=(sx, -4, 1.25), parent=royal_e, mat_=M_STONE_DARK_I)
# Windows trapezoidal
for wi in range(2):
    beveled_cube(f"rl_w_win{wi}", (1.0, 0.65, 1.2), bevel_offset=0.06,
                 loc=(-1.5 + wi*3, 4, 2.5), parent=royal_e, mat_=M_STONE_DARK_I)
# Stone detail variations
for ri in range(20):
    rx_r = random.uniform(-3, 3); ry_r = random.choice([-4, 4]); rz_r = random.uniform(0.3, 3.7)
    beveled_cube(f"rl_r{ri}", (random.uniform(0.4, 0.8), 0.65, random.uniform(0.4, 0.6)), bevel_offset=0.05,
                 loc=(rx_r, ry_r, rz_r), parent=royal_e, mat_=M_STONE_LIGHT_I)

# Building 3: Granary structures (smaller huts signature)
for hi in range(6):
    hx_g = -15 + hi * 5; hy_g = -8
    hut_e = empty(f"hut{hi}", (hx_g, hy_g, 0), parent=ruins_e)
    # Walls
    beveled_cube(f"hu{hi}_w", (3, 2.5, 3), bevel_offset=0.10, loc=(0, 0, 1.5),
                 parent=hut_e, mat_=M_STONE_INCA)
    # Door
    beveled_cube(f"hu{hi}_d", (1.0, 0.4, 1.8), bevel_offset=0.06, loc=(0, -1.25, 0.9),
                 parent=hut_e, mat_=M_STONE_DARK_I)
    # Thatched roof (signature)
    for ti in range(5):
        sl_w = 3.5 - ti * 0.10
        sl_z = 3 + ti * 0.15
        beveled_cube(f"hu{hi}_r{ti}", (sl_w, 2.6, 0.15), bevel_offset=0.04,
                     loc=(0, 0, sl_z), parent=hut_e, mat_=M_DIRT_I)
    # Roof peak
    smooth_cone(f"hu{hi}_peak", r1=0.3, r2=0.02, depth=0.5, segs=10,
                loc=(0, 0, 4.0), parent=hut_e, mat_=M_DIRT_I)

# ============ INTIHUATANA (signature sacred stone) ============
inti_e = empty("intihuatana", loc=(0, 10, 12))
# Stepped pedestal
for li in range(3):
    lw = 4 - li * 0.5
    lh = 0.5
    beveled_cube(f"int_p{li}", (lw, lw, lh), bevel_offset=0.10,
                 loc=(0, 0, lh*li + lh/2), parent=inti_e, mat_=M_STONE_INCA)
# Central carved stone (signature triangular)
beveled_cube("int_main", (2, 1.5, 1.5), bevel_offset=0.15, loc=(0, 0, 2.0),
             parent=inti_e, mat_=M_STONE_SACRED)
# Vertical pillar (signature sun-tying stone)
beveled_cube("int_pillar", (0.7, 0.7, 1.5), bevel_offset=0.10, loc=(0, 0, 3.4),
             parent=inti_e, mat_=M_STONE_SACRED)
# Top angled cut
beveled_cube("int_top", (0.5, 0.5, 0.3), bevel_offset=0.06, loc=(0, 0, 4.3),
             parent=inti_e, mat_=M_STONE_SACRED)
# Glow on top (signature mystical)
smooth_sphere("int_glow", r=0.5, segs=18, rings=14, loc=(0, 0, 4.6),
              parent=inti_e, mat_=M_STONE_GLOW)

# ============ 6 LLAMAS (signature) ============
def make_llama(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    llama_col = random.choice(LLAMA_VARIANTS)
    # Body
    smooth_sphere(f"{name}_body", r=0.55, segs=18, rings=12, loc=(0, 0, 1.5),
                  parent=base, mat_=llama_col, scale=(1.4, 0.9, 1.0))
    # Long shaggy wool tufts (signature)
    for wi in range(30):
        wa = random.uniform(0, math.pi*2); we = random.uniform(0, math.pi)
        wx = math.sin(we)*math.cos(wa)*0.65; wy = math.sin(we)*math.sin(wa)*0.55
        wz = math.cos(we)*0.55 + 1.5
        smooth_sphere(f"{name}_w{wi}", r=0.10, loc=(wx, wy, wz),
                      parent=base, mat_=llama_col)
    # 4 long legs signature
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}{y}", r=0.08, depth=1.5, segs=10,
                loc=(x*0.45, y*0.30, 0.75), parent=base, mat_=llama_col)
            # Hoof
            cyl(f"{name}_h{x}{y}", r=0.10, depth=0.10, segs=10,
                loc=(x*0.45, y*0.30, 0.05), parent=base, mat_=M_LLAMA_BLACK)
    # LONG NECK (signature)
    neck_e = empty(f"{name}_neck", (0.7, 0, 1.7), parent=base)
    neck_e.rotation_euler = (0, math.radians(-50), 0)
    for ni in range(5):
        cyl(f"{name}_n{ni}", r=0.12 - ni*0.005, depth=0.30, segs=10,
            loc=(0, 0, ni*0.30 + 0.15), parent=neck_e, mat_=llama_col)
    # Head
    head_l_e = empty(f"{name}_he", (0, 0, 1.7), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.20, segs=18, rings=14, loc=(0.10, 0, 0),
                  parent=head_l_e, mat_=llama_col, scale=(1.4, 0.9, 1.0))
    # Long snout
    smooth_sphere(f"{name}_snout", r=0.14, loc=(0.25, 0, -0.10),
                  parent=head_l_e, mat_=llama_col, scale=(1.4, 0.8, 0.7))
    # Pink nose
    smooth_sphere(f"{name}_nose", r=0.04, loc=(0.40, 0, -0.05),
                  parent=head_l_e, mat_=M_LLAMA_PINK_NOSE)
    # Pointed ears (signature)
    for side in (-1, 1):
        smooth_cone(f"{name}_ear{side}", r1=0.06, r2=0.01, depth=0.20, segs=8,
                    loc=(-0.05, side*0.10, 0.20), parent=head_l_e,
                    mat_=llama_col).rotation_euler = (math.radians(-15), 0, math.radians(side*10))
    # Eyes long lashes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04, loc=(0.10, side*0.13, 0.05),
                      parent=head_l_e, mat_=M_EYE_DARK_I)
    # Embroidered halter (signature colorful)
    halter_col = random.choice(TEXTILE_COLORS)
    cyl(f"{name}_halt", r=0.16, depth=0.08, segs=14, loc=(0, 0, 1.3),
        parent=neck_e, mat_=halter_col)
    # Tassels on halter
    for ti in range(5):
        ta = (ti / 5.0) * math.pi * 2
        smooth_sphere(f"{name}_t{ti}", r=0.04,
                      loc=(math.cos(ta)*0.18, math.sin(ta)*0.18, 1.25),
                      parent=neck_e, mat_=random.choice(TEXTILE_COLORS))
    # Saddle textile (signature)
    beveled_cube(f"{name}_sad", (1.2, 1.0, 0.10), bevel_offset=0.04, loc=(0, 0, 2.15),
                 parent=base, mat_=random.choice(TEXTILE_COLORS))
    # Pattern on saddle
    for pi in range(3):
        beveled_cube(f"{name}_sp{pi}", (1.2, 0.1, 0.06), bevel_offset=0.02,
                     loc=(0, -0.4 + pi*0.4, 2.20), parent=base,
                     mat_=random.choice(TEXTILE_COLORS))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_l_e, "neck": neck_e}

llamas = []
llama_pos = [(-25, 5, math.radians(45)), (-22, 8, math.radians(0)),
              (15, -5, math.radians(120)), (18, -2, math.radians(150)),
              (-5, -15, math.radians(-30)), (5, -18, math.radians(-60))]
for i, (lx, ly, fac) in enumerate(llama_pos):
    l = make_llama(f"llama{i}", (lx, ly, 0), scale=1.0, facing=fac)
    llamas.append(l)

# ============ 4 QUECHUA WOMEN signature ============
def make_quechua_woman(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    dress_col = random.choice(TEXTILE_COLORS)
    skirt_col = random.choice(TEXTILE_COLORS)
    # Long pleated skirt (signature)
    smooth_cone(f"{name}_skirt", r1=0.45*scale, r2=0.30*scale, depth=0.9*scale, segs=18,
                loc=(0, 0, 0.65*scale), parent=base, mat_=skirt_col)
    # Pattern stripes on skirt
    for pi in range(5):
        cyl(f"{name}_sp{pi}", r=0.46*scale - pi*0.005, depth=0.06*scale, segs=18,
            loc=(0, 0, 0.20*scale + pi*0.18*scale), parent=base,
            mat_=random.choice(TEXTILE_COLORS))
    # Belt sash
    cyl(f"{name}_belt", r=0.34*scale, depth=0.10*scale, segs=16, loc=(0, 0, 1.15*scale),
        parent=base, mat_=random.choice(TEXTILE_COLORS))
    # Pattern on belt
    for pi in range(6):
        pa = (pi / 6.0) * math.pi * 2
        smooth_sphere(f"{name}_bp{pi}", r=0.03*scale,
                      loc=(math.cos(pa)*0.36*scale, math.sin(pa)*0.36*scale, 1.15*scale),
                      parent=base, mat_=random.choice(TEXTILE_COLORS))
    # Blouse
    smooth_cone(f"{name}_blouse", r1=0.30*scale, r2=0.32*scale, depth=0.60*scale, segs=14,
                loc=(0, 0, 1.50*scale), parent=base, mat_=dress_col)
    # Lliclla (signature traditional shawl folded on shoulders)
    lliclla_e = empty(f"{name}_lli", (0, 0.10*scale, 1.65*scale), parent=base)
    beveled_cube(f"{name}_lli_b", (0.65*scale, 0.20*scale, 0.40*scale), bevel_offset=0.06,
                 loc=(0, 0, 0), parent=lliclla_e, mat_=random.choice(TEXTILE_COLORS))
    # Lliclla patterns
    for ll in range(4):
        beveled_cube(f"{name}_llp{ll}", (0.66*scale, 0.22*scale, 0.06*scale), bevel_offset=0.02,
                     loc=(0, 0, -0.15 + ll*0.10*scale), parent=lliclla_e,
                     mat_=random.choice(TEXTILE_COLORS))
    # Arms (one weaving)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.70*scale), parent=base)
        sh.rotation_euler = (math.radians(-60), 0, math.radians(side*-25))
        cyl(f"{name}_uarm{side_idx}", r=0.06*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.18*scale), parent=sh, mat_=dress_col)
        cyl(f"{name}_fa{side_idx}", r=0.05*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.48*scale), parent=sh, mat_=M_SKIN_PERU)
    # Head
    head_q_e = empty(f"{name}_he", (0, 0, 1.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_q_e, mat_=M_SKIN_PERU)
    # Black braided hair (signature 2 long braids)
    for side in (-1, 1):
        # Long braid
        for bi in range(8):
            smooth_sphere(f"{name}_br{side}_{bi}", r=0.06*scale,
                          loc=(side*0.18*scale, 0, -bi*0.10*scale - 0.05*scale),
                          parent=head_q_e, mat_=M_HAIR_BLACK_P)
        # Tassel end (signature colored)
        smooth_sphere(f"{name}_brt{side}", r=0.07*scale,
                      loc=(side*0.18*scale, 0, -0.90*scale),
                      parent=head_q_e, mat_=random.choice(TEXTILE_COLORS))
    # MONTERA HAT (signature round flat)
    hat_e = empty(f"{name}_hat", (0, 0, 0.20*scale), parent=head_q_e)
    cyl(f"{name}_brim", r=0.28*scale, depth=0.04*scale, segs=18, loc=(0, 0, 0),
        parent=hat_e, mat_=M_HAT_BROWN_P)
    cyl(f"{name}_crown", r=0.20*scale, depth=0.10*scale, segs=18, loc=(0, 0, 0.06*scale),
        parent=hat_e, mat_=M_HAT_BROWN_P)
    # Ribbon band on hat
    cyl(f"{name}_band", r=0.21*scale, depth=0.04*scale, segs=18, loc=(0, 0, 0.04*scale),
        parent=hat_e, mat_=random.choice(TEXTILE_COLORS))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.03*scale), parent=head_q_e, mat_=M_EYE_DARK_I)
    # Lips
    beveled_cube(f"{name}_lips", (0.06*scale, 0.04*scale, 0.02*scale), bevel_offset=0.005,
                 loc=(0, -0.18*scale, -0.06*scale), parent=head_q_e, mat_=M_LIPS)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_q_e}

quechua_women = []
q_pos = [(-10, 25, math.radians(0)), (-5, 25, math.radians(-30)),
          (5, 25, math.radians(30)), (10, 25, math.radians(0))]
for i, (qx, qy, fac) in enumerate(q_pos):
    q = make_quechua_woman(f"quechua{i}", (qx, qy, 12), scale=1.0, facing=fac)
    quechua_women.append(q)

# ============ INCA CHIEF (signature gold crown) ============
chief_e = empty("inca_chief", loc=(0, 22, 12))
# Body red tunic
smooth_cone("ch_robe", r1=0.40, r2=0.45, depth=1.2, segs=14, loc=(0, 0, 1.0),
            parent=chief_e, mat_=M_INCA_TUNIC)
# Gold sash and decorations
cyl("ch_sash", r=0.46, depth=0.12, segs=18, loc=(0, 0, 1.30), parent=chief_e, mat_=M_GOLD_INCA)
# Gold disk pectoral (signature)
smooth_sphere("ch_pect", r=0.30, loc=(0, -0.40, 1.55), parent=chief_e, mat_=M_GOLD_INCA, scale=(1.5, 0.3, 1.5))
# Sun rays around pectoral
for ri in range(12):
    ra = (ri / 12.0) * math.pi * 2
    cyl(f"ch_pr{ri}", r=0.02, depth=0.30, segs=8,
        loc=(math.cos(ra)*0.40, -0.40, 1.55 + math.sin(ra)*0.40),
        parent=chief_e, mat_=M_GOLD_INCA).rotation_euler = (0, math.radians(90), ra)
# Pants
for side in (-1, 1):
    cyl(f"ch_leg{side}", r=0.10, depth=0.8, segs=10,
        loc=(side*0.13, 0, 0.40), parent=chief_e, mat_=M_INCA_TUNIC)
# Sandals
for side in (-1, 1):
    beveled_cube(f"ch_sa{side}", (0.11, 0.22, 0.05), bevel_offset=0.02,
                 loc=(side*0.13, 0, 0), parent=chief_e, mat_=M_HAIR_BLACK_P)
# Arms
for side in (-1, 1):
    sh = empty(f"ch_sh{side}", (side*0.40, 0, 1.65), parent=chief_e)
    sh.rotation_euler = (math.radians(-100), 0, math.radians(side*-25))
    cyl(f"ch_uarm{side}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh, mat_=M_INCA_TUNIC)
    cyl(f"ch_fa{side}", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh, mat_=M_SKIN_PERU)
# Head
ch_head_e = empty("ch_he", (0, 0, 1.95), parent=chief_e)
smooth_sphere("ch_head", r=0.20, segs=18, rings=14, loc=(0, 0, 0),
              parent=ch_head_e, mat_=M_SKIN_PERU)
# Hair long
for hi in range(10):
    ha = (hi / 10.0) * math.pi * 2
    smooth_sphere(f"ch_hr{hi}", r=0.06, loc=(math.cos(ha)*0.18, math.sin(ha)*0.10, -0.05 - (hi%4)*0.05),
                  parent=ch_head_e, mat_=M_HAIR_BLACK_P)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"ch_eye{side}", r=0.03, loc=(side*0.07, -0.16, 0.04),
                  parent=ch_head_e, mat_=M_EYE_DARK_I)
# GOLD CROWN signature (Inca llautu with feathered plume)
crown_e = empty("ch_crown", (0, 0, 0.22), parent=ch_head_e)
# Gold band crown
cyl("ch_cr_b", r=0.22, depth=0.10, segs=18, loc=(0, 0, 0),
    parent=crown_e, mat_=M_GOLD_INCA)
# Decorative pattern
for di in range(8):
    da = (di / 8.0) * math.pi * 2
    smooth_sphere(f"ch_cr_d{di}", r=0.04,
                  loc=(math.cos(da)*0.22, math.sin(da)*0.22, 0),
                  parent=crown_e, mat_=M_FEATHER_RED)
# 8 feather plume (signature)
for fi in range(8):
    fa = (fi / 8.0) * math.pi * 2
    fcol = FEATHER_COLORS_INCA[fi % len(FEATHER_COLORS_INCA)]
    smooth_cone(f"ch_fp{fi}", r1=0.04, r2=0.005, depth=0.70, segs=8,
                loc=(math.cos(fa)*0.20, math.sin(fa)*0.20, 0.50),
                parent=crown_e, mat_=fcol).rotation_euler = (math.radians(-15), 0, fa)
# Mascaipacha (signature royal forehead tassel)
beveled_cube("ch_masc", (0.20, 0.04, 0.08), bevel_offset=0.02, loc=(0, -0.20, -0.02),
             parent=crown_e, mat_=M_FEATHER_RED)
# Earplugs (signature gold)
for side in (-1, 1):
    cyl(f"ch_ep{side}", r=0.06, depth=0.05, segs=14, loc=(side*0.20, 0, -0.05),
        parent=ch_head_e, mat_=M_GOLD_INCA).rotation_euler = (0, math.radians(90), 0)
chief_e["_phase"] = 0

# ============ CHASQUI MESSENGER ============
chasqui_e = empty("chasqui", loc=(20, 18, 12))
chasqui_e.rotation_euler = (0, 0, math.radians(60))
# Running body lean
smooth_cone("ch_q_torso", r1=0.32, r2=0.34, depth=0.6, segs=14, loc=(0, 0, 1.30),
            parent=chasqui_e, mat_=M_TEXTILE_ORANGE)
# Legs (running pose)
for side_idx, side in enumerate((-1, 1)):
    leg_e = empty(f"ch_q_l{side_idx}_e", (side*0.13, 0, 0.95), parent=chasqui_e)
    if side_idx == 0:
        leg_e.rotation_euler = (math.radians(40), 0, 0)
    else:
        leg_e.rotation_euler = (math.radians(-30), 0, 0)
    cyl(f"ch_q_l{side_idx}", r=0.09, depth=0.85, segs=10, loc=(0, 0, -0.42),
        parent=leg_e, mat_=M_SKIN_PERU)
# Arms swinging
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"ch_q_sh{side_idx}", (side*0.30, 0, 1.65), parent=chasqui_e)
    if side_idx == 0:
        sh.rotation_euler = (math.radians(-60), 0, math.radians(15))
    else:
        sh.rotation_euler = (math.radians(60), 0, math.radians(-15))
    cyl(f"ch_q_ua{side_idx}", r=0.06, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh, mat_=M_TEXTILE_ORANGE)
    cyl(f"ch_q_fa{side_idx}", r=0.05, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh, mat_=M_SKIN_PERU)
# Quipu (signature knotted strings he carries)
quipu_e = empty("quipu", (0, 0.30, 1.40), parent=chasqui_e)
# Main cord
cyl("qp_main", r=0.02, depth=0.6, segs=8, loc=(0, 0, 0),
    parent=quipu_e, mat_=M_HAT_BROWN_P).rotation_euler = (0, math.radians(90), 0)
# 8 hanging strings with knots
for qi in range(8):
    qx_p = -0.25 + qi * 0.07
    cyl(f"qp_s{qi}", r=0.008, depth=0.40, segs=6, loc=(qx_p, 0, -0.20),
        parent=quipu_e, mat_=M_HAT_BROWN_P)
    # Knots
    for ki in range(random.randint(2, 5)):
        smooth_sphere(f"qp_k{qi}_{ki}", r=0.02,
                      loc=(qx_p, 0, -0.05 - ki*0.10),
                      parent=quipu_e, mat_=M_TEXTILE_RED if ki % 2 == 0 else M_TEXTILE_BLUE)
# Head
ch_q_head_e = empty("ch_q_he", (0, 0, 1.95), parent=chasqui_e)
smooth_sphere("ch_q_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
              parent=ch_q_head_e, mat_=M_SKIN_PERU)
# Hat band
cyl("ch_q_hb", r=0.20, depth=0.08, segs=18, loc=(0, 0, 0.15),
    parent=ch_q_head_e, mat_=M_TEXTILE_RED)
# Feather signature
smooth_cone("ch_q_fe", r1=0.04, r2=0.005, depth=0.30, segs=8,
            loc=(0.15, -0.05, 0.30), parent=ch_q_head_e, mat_=M_FEATHER_BLUE).rotation_euler = (math.radians(20), 0, math.radians(30))
chasqui_e["_phase"] = 0

# ============================================================
# ⭐ 600 SACRED STONES + 400 CONDORS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
sacred_stones = []
for i in range(600):
    px = random.uniform(-80, 80)
    py = random.uniform(-80, 80)
    pz = random.uniform(2, 30)
    # Carved stone shape
    s = beveled_cube(f"ss{i}", (random.uniform(0.10, 0.20),
                                  random.uniform(0.10, 0.20),
                                  random.uniform(0.10, 0.20)),
                     bevel_offset=0.03, loc=(px, py, pz), mat_=M_STONE_SACRED)
    s["_phase"] = random.uniform(0, math.pi*2)
    s["_base_x"] = px; s["_base_y"] = py; s["_base_z"] = pz
    s["_amp_x"] = random.uniform(0.5, 1.5)
    s["_amp_y"] = random.uniform(0.5, 1.5)
    s["_amp_z"] = random.uniform(0.3, 1.0)
    s["_speed"] = random.uniform(0.3, 0.8)
    sacred_stones.append(s)

# 400 CONDORS (signature flying)
condors = []
for i in range(400):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = random.uniform(10, 45)
    cond_e = empty(f"cond{i}", (px, py, pz))
    # Body
    smooth_sphere(f"cd_b{i}", r=0.15, segs=12, rings=10, loc=(0, 0, 0),
                  parent=cond_e, mat_=M_CONDOR_BLACK, scale=(1.4, 1, 0.85))
    # White collar (signature)
    cyl(f"cd_c{i}", r=0.18, depth=0.05, segs=14, loc=(0, 0, 0.05),
        parent=cond_e, mat_=M_CONDOR_WHITE_COLLAR)
    # Head
    smooth_sphere(f"cd_h{i}", r=0.08, loc=(0.18, 0, 0.05),
                  parent=cond_e, mat_=M_CONDOR_BLACK, scale=(1, 0.9, 0.9))
    # Beak hooked
    smooth_cone(f"cd_bk{i}", r1=0.025, r2=0.005, depth=0.08, segs=8,
                loc=(0.28, 0, 0.02), parent=cond_e,
                mat_=M_CONDOR_BEAK).rotation_euler = (0, math.radians(95), 0)
    # Glowing eye
    smooth_sphere(f"cd_e{i}", r=0.02, loc=(0.22, 0.05, 0.07),
                  parent=cond_e, mat_=M_CONDOR_EYE)
    # WINGS spread huge signature 3m wingspan
    for side in (-1, 1):
        wing = beveled_cube(f"cd_w{i}_{side}", (0.10, 1.2, 0.10), bevel_offset=0.02,
                            loc=(-0.05, side*0.65, 0), parent=cond_e, mat_=M_CONDOR_BLACK)
        # Wing fingers (signature primary feathers)
        for fi in range(5):
            fy_f = side*(0.95 + fi*0.10)
            beveled_cube(f"cd_w{i}_{side}_f{fi}", (0.04, 0.20, 0.03), bevel_offset=0.005,
                         loc=(-0.05, fy_f, 0), parent=cond_e, mat_=M_CONDOR_BLACK)
    # Tail
    beveled_cube(f"cd_t{i}", (0.30, 0.30, 0.05), bevel_offset=0.02, loc=(-0.30, 0, 0),
                 parent=cond_e, mat_=M_CONDOR_BLACK)
    cond_e["_phase"] = random.uniform(0, math.pi*2)
    cond_e["_base_x"] = px; cond_e["_base_y"] = py; cond_e["_base_z"] = pz
    cond_e["_amp_x"] = random.uniform(2.0, 5.0)
    cond_e["_amp_y"] = random.uniform(2.0, 5.0)
    cond_e["_amp_z"] = random.uniform(1.0, 3.0)
    cond_e["_speed"] = random.uniform(0.4, 1.0)
    condors.append(cond_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Clouds drift
for ci in range(25):
    cloud = bpy.data.objects.get(f"cloud{ci}")
    if cloud is None: continue
    phase = cloud["_phase"]
    bx_c = cloud.location.x; by_c = cloud.location.y
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        cloud.location.x = bx_c + math.sin(t * 0.3 + phase) * 3.0
        cloud.location.y = by_c + math.cos(t * 0.3 + phase) * 3.0
        cloud.keyframe_insert("location", frame=f)

# Llamas walk + neck sway
for l in llamas:
    phase = l["root"]["_phase"]
    bx_l = l["root"].location.x; by_l = l["root"].location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        l["root"].location.x = bx_l + math.sin(t * 0.6 + phase) * 0.5
        l["root"].location.y = by_l + math.cos(t * 0.6 + phase) * 0.5
        l["root"].location.z = abs(math.sin(t * 1.5 + phase)) * 0.05
        l["root"].keyframe_insert("location", frame=f)
        # Long neck sway
        l["neck"].rotation_euler = (0, math.radians(-50) + math.sin(t * 0.8 + phase) * math.radians(15), 0)
        l["neck"].keyframe_insert("rotation_euler", frame=f)

# Quechua women weaving
for q in quechua_women:
    phase = q["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        q["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3),
                                     math.cos(t * 1.5 + phase) * math.radians(2),
                                     q["root"].rotation_euler.z)
        q["root"].keyframe_insert("rotation_euler", frame=f)
        q["he"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(5), 0,
                                   math.cos(t * 1.0 + phase) * math.radians(8))
        q["he"].keyframe_insert("rotation_euler", frame=f)

# Chief pose proud + slight movement
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    chief_e.rotation_euler = (0, math.sin(t * 0.6) * math.radians(2),
                                math.sin(t * 0.4) * math.radians(5))
    chief_e.keyframe_insert("rotation_euler", frame=f)
    ch_head_e.rotation_euler = (0, 0, math.sin(t * 0.5) * math.radians(15))
    ch_head_e.keyframe_insert("rotation_euler", frame=f)

# Chasqui running
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    chasqui_e.location.z = 12 + abs(math.sin(t * 4.0)) * 0.2
    chasqui_e.rotation_euler = (math.sin(t * 4.0) * math.radians(4), 0, math.radians(60))
    chasqui_e.keyframe_insert("location", frame=f)
    chasqui_e.keyframe_insert("rotation_euler", frame=f)

# Intihuatana glow pulse
glow_obj = bpy.data.objects.get("int_glow")
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    if glow_obj:
        s_g = 0.7 + abs(math.sin(t * 2.0)) * 0.8
        glow_obj.scale = (s_g, s_g, s_g)
        glow_obj.keyframe_insert("scale", frame=f)

# 600 sacred stones float + glow
for s in sacred_stones:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        s.location = (x, y, z)
        s.rotation_euler = (t * 0.5 + phase, t * 0.3 + phase, t * 0.4 + phase)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("rotation_euler", frame=f)

# 400 condors gliding (signature wings open soaring)
for c in condors:
    phase = c["_phase"]; speed = c["_speed"]
    bx, by, bz = c["_base_x"], c["_base_y"], c["_base_z"]
    ax, ay, az = c["_amp_x"], c["_amp_y"], c["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.4 + phase)
        c.location = (x, y, z)
        # Soaring tilt (signature wings)
        c.rotation_euler = (math.sin(t * speed * 0.8 + phase) * math.radians(15),
                             math.cos(t * speed * 0.8 + phase) * math.radians(10),
                             math.atan2(math.cos(t * speed * 0.9 + phase),
                                        math.sin(t * speed + phase)))
        c.keyframe_insert("location", frame=f)
        c.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_machu_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_machu_picchu_inca_andes] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_machu_picchu_inca_andes] 8 Andes peaks + 8+6 terraces + Temple of the Sun curved + Royal Residence + 6 huts + Intihuatana sacred stone + 6 llamas + 4 Quechua women + Inca chief gold crown + chasqui + quipu + 600 sacred stones + 400 condors")
print("⭐ FIXES: 1 ground + 600 sacred stones + 400 condors (signature Andes thematic mandatory) ⭐")
