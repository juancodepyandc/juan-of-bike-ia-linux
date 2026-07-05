"""
proc_norwegian_fjord_viking_ship.py — 246e procédural AuroraIA (111e qualité)
Norwegian fjord viking longship + aurora borealis: drakkar + 18 rowers + king + 4 turf houses + stave church + 600 aurora + 400 snow
FIXES : 1 ground + 600 aurora waves + 400 snowflakes (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB246)

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

# Night Nordic sky palette
M_SKY = mat("sky", (0.04, 0.06, 0.18, 1.0), 0.0, 0.7, emission=(0.05,0.08,0.20), emission_strength=0.7)
M_STAR = mat("star", (1.0, 0.95, 0.78, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.78), emission_strength=10.0)
M_MOON = mat("moon", (0.92, 0.92, 0.85, 1.0), 0.0, 0.20, emission=(0.88,0.88,0.82), emission_strength=4.0)

# Aurora colors signature
M_AURORA_GREEN = mat("au_g", (0.18, 0.95, 0.45, 1.0), 0.0, 0.10, emission=(0.18,0.95,0.45), emission_strength=6.0, alpha=0.55)
M_AURORA_GREEN_BR = mat("au_gb", (0.30, 1.0, 0.55, 1.0), 0.0, 0.10, emission=(0.30,1.0,0.55), emission_strength=7.0, alpha=0.50)
M_AURORA_PURPLE = mat("au_p", (0.55, 0.20, 0.85, 1.0), 0.0, 0.10, emission=(0.55,0.20,0.85), emission_strength=5.5, alpha=0.55)
M_AURORA_BLUE = mat("au_b", (0.25, 0.55, 1.0, 1.0), 0.0, 0.10, emission=(0.25,0.55,1.0), emission_strength=5.0, alpha=0.55)
M_AURORA_PINK = mat("au_pk", (0.95, 0.40, 0.85, 1.0), 0.0, 0.10, emission=(0.92,0.40,0.85), emission_strength=5.5, alpha=0.55)
AURORA_COLORS = [M_AURORA_GREEN, M_AURORA_GREEN_BR, M_AURORA_PURPLE, M_AURORA_BLUE, M_AURORA_PINK]

# Water fjord
M_WATER_FJORD = mat("water", (0.10, 0.32, 0.55, 1.0), 0.1, 0.20, emission=(0.10,0.35,0.55), emission_strength=1.3, alpha=0.78)
M_WATER_FJORD_DEEP = mat("water_d", (0.05, 0.22, 0.45, 1.0), 0.1, 0.25, alpha=0.85)
M_WATER_REFLECT_V = mat("wr", (0.20, 0.85, 0.50, 1.0), 0.0, 0.10, emission=(0.20,0.85,0.50), emission_strength=2.0, alpha=0.55)

# Ground rocky earth
M_GROUND_ROCK = mat("ground", (0.30, 0.32, 0.28, 1.0), 0.0, 0.85, emission=(0.28,0.30,0.26), emission_strength=0.2)
M_GROUND_SNOW = mat("g_snow", (0.85, 0.88, 0.92, 1.0), 0.0, 0.40, emission=(0.78,0.82,0.88), emission_strength=0.8)
M_GROUND_GRASS = mat("g_grass", (0.30, 0.45, 0.22, 1.0), 0.0, 0.80, emission=(0.28,0.42,0.22), emission_strength=0.3)
M_ROCK_DARK_V = mat("rock_d", (0.20, 0.22, 0.20, 1.0), 0.0, 0.85)

# Cliffs
M_CLIFF_DARK = mat("cliff", (0.32, 0.30, 0.28, 1.0), 0.0, 0.85, emission=(0.30,0.28,0.26), emission_strength=0.2)
M_CLIFF_SNOW = mat("cliff_s", (0.85, 0.88, 0.92, 1.0), 0.0, 0.40, emission=(0.82,0.85,0.90), emission_strength=0.7)
M_CLIFF_MOSS = mat("cliff_m", (0.30, 0.45, 0.22, 1.0), 0.0, 0.75)

# Snow firs
M_FIR_DARK_V = mat("fir_d", (0.10, 0.30, 0.15, 1.0), 0.0, 0.75, emission=(0.10,0.30,0.15), emission_strength=0.4)
M_FIR_SNOW = mat("fir_s", (0.85, 0.88, 0.92, 1.0), 0.0, 0.40, emission=(0.82,0.85,0.90), emission_strength=0.6)
M_TRUNK_PINE_V = mat("trk_p", (0.30, 0.18, 0.08, 1.0), 0.0, 0.85)

# Drakkar wood (signature dark wood + red accents)
M_DRAKKAR_WOOD = mat("dr_w", (0.45, 0.25, 0.10, 1.0), 0.0, 0.65, emission=(0.42,0.25,0.10), emission_strength=0.4)
M_DRAKKAR_DARK = mat("dr_d", (0.25, 0.15, 0.06, 1.0), 0.0, 0.80)
M_DRAKKAR_GOLD = mat("dr_gd", (0.95, 0.78, 0.25, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.25), emission_strength=1.5)
M_DRAKKAR_RED = mat("dr_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.72,0.18,0.18), emission_strength=0.8)

# Sail (signature red striped)
M_SAIL_WHITE = mat("sail_w", (0.85, 0.82, 0.75, 1.0), 0.0, 0.70, emission=(0.78,0.78,0.72), emission_strength=0.5)
M_SAIL_RED = mat("sail_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.60, emission=(0.72,0.18,0.18), emission_strength=0.6)
M_ROPE = mat("rope", (0.55, 0.42, 0.20, 1.0), 0.0, 0.85)

# Shield signature painted
M_SHIELD_RED = mat("sh_r", (0.78, 0.20, 0.20, 1.0), 0.0, 0.55, emission=(0.72,0.20,0.20), emission_strength=0.7)
M_SHIELD_YELLOW = mat("sh_y", (0.92, 0.78, 0.20, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.20), emission_strength=0.8)
M_SHIELD_BLUE = mat("sh_b", (0.20, 0.42, 0.78, 1.0), 0.0, 0.55, emission=(0.20,0.42,0.75), emission_strength=0.7)
M_SHIELD_GREEN = mat("sh_g", (0.20, 0.55, 0.30, 1.0), 0.0, 0.55, emission=(0.20,0.55,0.30), emission_strength=0.7)
M_SHIELD_BLACK = mat("sh_bk", (0.12, 0.10, 0.10, 1.0), 0.0, 0.75)
M_SHIELD_BOSS = mat("sh_bs", (0.85, 0.85, 0.85, 1.0), 0.9, 0.25, emission=(0.80,0.80,0.80), emission_strength=1.0)
SHIELD_COLORS = [M_SHIELD_RED, M_SHIELD_YELLOW, M_SHIELD_BLUE, M_SHIELD_GREEN, M_SHIELD_BLACK]

# Viking skin
M_SKIN_VIKING = mat("skin_v", (0.92, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.62), emission_strength=0.3)
M_HAIR_BLOND_V = mat("h_bl", (0.85, 0.65, 0.30, 1.0), 0.0, 0.55)
M_HAIR_RED_V = mat("h_r", (0.72, 0.30, 0.10, 1.0), 0.0, 0.60)
M_HAIR_BROWN_V = mat("h_br", (0.32, 0.18, 0.08, 1.0), 0.0, 0.60)
M_BEARD = mat("beard", (0.50, 0.32, 0.18, 1.0), 0.0, 0.65)
HAIR_VARIANTS_V = [M_HAIR_BLOND_V, M_HAIR_RED_V, M_HAIR_BROWN_V]

# Viking clothes signature
M_VIKING_TUNIC_GREEN = mat("vt_g", (0.30, 0.50, 0.25, 1.0), 0.0, 0.70, emission=(0.28,0.48,0.25), emission_strength=0.3)
M_VIKING_TUNIC_BROWN = mat("vt_b", (0.42, 0.28, 0.15, 1.0), 0.0, 0.75, emission=(0.40,0.28,0.15), emission_strength=0.3)
M_VIKING_TUNIC_GREY = mat("vt_gr", (0.45, 0.45, 0.45, 1.0), 0.0, 0.75)
M_VIKING_PANTS_DARK = mat("vp_d", (0.25, 0.18, 0.10, 1.0), 0.0, 0.80)
M_LEATHER_BELT = mat("lbelt", (0.30, 0.18, 0.10, 1.0), 0.0, 0.75)
M_FUR_BROWN = mat("fur", (0.42, 0.28, 0.15, 1.0), 0.0, 0.85, emission=(0.40,0.28,0.15), emission_strength=0.3)
M_FUR_GREY = mat("fur_g", (0.55, 0.50, 0.45, 1.0), 0.0, 0.85)
TUNIC_VARIANTS = [M_VIKING_TUNIC_GREEN, M_VIKING_TUNIC_BROWN, M_VIKING_TUNIC_GREY]

# Helmet (signature horned/rounded)
M_HELMET_STEEL = mat("hl", (0.62, 0.62, 0.65, 1.0), 0.9, 0.30, emission=(0.58,0.58,0.62), emission_strength=0.5)
M_HELMET_DARK = mat("hl_d", (0.42, 0.42, 0.45, 1.0), 0.8, 0.40)
M_HELMET_GOLD = mat("hl_gd", (0.95, 0.78, 0.25, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.25), emission_strength=1.0)

# Axe + sword
M_AXE_HEAD = mat("axe", (0.55, 0.55, 0.55, 1.0), 0.9, 0.30, emission=(0.52,0.52,0.52), emission_strength=0.8)
M_AXE_HANDLE = mat("axe_h", (0.40, 0.25, 0.12, 1.0), 0.0, 0.75)
M_SWORD = mat("sword", (0.85, 0.85, 0.88, 1.0), 0.92, 0.18, emission=(0.80,0.80,0.85), emission_strength=1.2)

# Turf house (signature sod roof + wood walls)
M_TURF_ROOF = mat("turf", (0.30, 0.55, 0.25, 1.0), 0.0, 0.80, emission=(0.28,0.52,0.22), emission_strength=0.4)
M_TURF_DIRT = mat("turf_d", (0.32, 0.22, 0.10, 1.0), 0.0, 0.85)
M_TURF_GRASS_TOP = mat("turf_g", (0.20, 0.50, 0.20, 1.0), 0.0, 0.75, emission=(0.20,0.50,0.20), emission_strength=0.5)
M_LOG_WALL = mat("log", (0.55, 0.32, 0.15, 1.0), 0.0, 0.75, emission=(0.50,0.30,0.15), emission_strength=0.4)
M_LOG_DARK = mat("log_d", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)
M_DOOR_VIKING = mat("door", (0.30, 0.20, 0.10, 1.0), 0.0, 0.85)
M_WINDOW_LIT = mat("win", (1.0, 0.78, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.78,0.30), emission_strength=4.0)

# Stave church (signature)
M_STAVE_DARK = mat("stave", (0.18, 0.12, 0.06, 1.0), 0.0, 0.80, emission=(0.16,0.10,0.06), emission_strength=0.3)
M_STAVE_LIGHT = mat("stave_l", (0.42, 0.25, 0.10, 1.0), 0.0, 0.75)
M_DRAGON_HEAD = mat("dragon", (0.65, 0.45, 0.18, 1.0), 0.0, 0.55, emission=(0.60,0.42,0.18), emission_strength=0.5)
M_RUNE_GOLD = mat("rune", (1.0, 0.85, 0.20, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.20), emission_strength=1.5)

# Snow
M_SNOW_FLAKE = mat("snow_f", (0.95, 0.95, 0.98, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.95), emission_strength=2.5, alpha=0.85)

# Eye
M_EYE_BLUE_V = mat("eye_b_v", (0.20, 0.55, 0.85, 1.0), 0.0, 0.10, emission=(0.20,0.55,0.85), emission_strength=1.5)
M_EYE_BLACK_V = mat("eye_bk_v", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Campfire
M_FIRE_OUTER_V = mat("fire_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=15.0)
M_FIRE_CORE_V = mat("fire_c", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=18.0)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Moon
moon = smooth_sphere("moon", r=4, segs=24, rings=18, loc=(50, 80, 70), mat_=M_MOON)
# Stars
for si in range(150):
    sa = random.uniform(0, math.pi*2); sr = random.uniform(80, 200)
    sh = random.uniform(30, 100)
    smooth_sphere(f"star{si}", r=random.uniform(0.10, 0.30), segs=8, rings=6,
                  loc=(sr*math.cos(sa), sr*math.sin(sa), sh), mat_=M_STAR)

# ============ AURORA BOREALIS BANDS (signature multiple curtains) ============
# Each aurora band is a wavy ribbon high in sky
for au in range(6):
    au_y_pos = -40 + au * 18
    au_h = 35 + random.uniform(-5, 5)
    band_e = empty(f"aurora{au}_e", (0, au_y_pos, au_h))
    aurora_col = AURORA_COLORS[au % len(AURORA_COLORS)]
    aurora_col_2 = AURORA_COLORS[(au+1) % len(AURORA_COLORS)]
    # Many wavy segments
    for si in range(80):
        sx_off = -80 + si * 2
        sz_off = math.sin(si * 0.25 + au) * 4
        # Vertical ribbon
        col_use = aurora_col if si % 3 != 0 else aurora_col_2
        for hi in range(8):
            hz = hi * 1.0
            beveled_cube(f"au{au}_{si}_{hi}", (1.8, 0.4, 0.8), bevel_offset=0.05,
                         loc=(sx_off, sz_off, hz - 4),
                         parent=band_e, mat_=col_use)
    band_e["_phase"] = random.uniform(0, math.pi*2)

# ============ ONE clean rocky+grass ground ============
ground = beveled_cube("ground", (180, 180, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_GROUND_ROCK)
# Organic variations + snow patches
for i in range(180):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 75)
    mat_choice = [M_GROUND_GRASS, M_GROUND_SNOW, M_ROCK_DARK_V][i % 3]
    smooth_sphere(f"earth{i}", r=random.uniform(0.4, 1.0), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=mat_choice, scale=(1.5, 1.4, 0.22))

# ============ FJORD WATER (serpentine signature) ============
fjord_pts = []
for ri in range(35):
    fj_y = -50 + ri * 2.8
    fj_x = math.sin(ri * 0.20) * 6
    fjord_pts.append((fj_x, fj_y, 0))

for ri in range(len(fjord_pts) - 1):
    fx1, fy1, _ = fjord_pts[ri]; fx2, fy2, _ = fjord_pts[ri+1]
    fmidx = (fx1 + fx2) / 2; fmidy = (fy1 + fy2) / 2
    flen = math.sqrt((fx2-fx1)**2 + (fy2-fy1)**2) + 0.5
    fang = math.atan2(fy2-fy1, fx2-fx1)
    seg = beveled_cube(f"fjord{ri}", (flen, 18, 0.18), bevel_offset=0.04,
                       loc=(fmidx, fmidy, 0.18), mat_=M_WATER_FJORD)
    seg.rotation_euler = (0, 0, fang)
    seg2 = beveled_cube(f"fjord_d{ri}", (flen*0.95, 16, 0.12), bevel_offset=0.03,
                        loc=(fmidx, fmidy, 0.22), mat_=M_WATER_FJORD_DEEP)
    seg2.rotation_euler = (0, 0, fang)
# Aurora reflections on water (signature green stripes)
for ri in range(25):
    rx_r = random.uniform(-6, 6); ry_r = random.uniform(-40, 40)
    cyl(f"refl_v{ri}", r=random.uniform(0.30, 0.60), depth=0.04, segs=14,
        loc=(rx_r, ry_r, 0.25), mat_=M_WATER_REFLECT_V)

# ============ 2 CLIFFS (signature towering on sides) ============
def make_cliff(name, x_side):
    c_e = empty(name, (x_side * 20, 0, 0))
    # Layered cliff face
    for li in range(10):
        lz = li * 2.5
        cl_l = 35 - li * 1.0
        cl_w = 4 + li * 0.5
        beveled_cube(f"{name}_{li}", (cl_w, cl_l, 2.5), bevel_offset=0.15,
                     loc=(x_side*cl_w/2, 0, lz + 1.25), parent=c_e,
                     mat_=M_CLIFF_DARK if li < 6 else M_CLIFF_SNOW)
    # Moss / grass tufts on cliff
    for mi in range(20):
        mz = random.uniform(2, 12)
        my_c = random.uniform(-15, 15)
        smooth_sphere(f"{name}_moss{mi}", r=random.uniform(0.30, 0.60),
                      loc=(x_side*2, my_c, mz), parent=c_e, mat_=M_CLIFF_MOSS,
                      scale=(0.5, 1.5, 0.8))
    return c_e

cliff_left = make_cliff("cliff_L", -1)
cliff_right = make_cliff("cliff_R", 1)

# ============ DRAKKAR LONGSHIP (signature centerpiece) ============
drakkar_e = empty("drakkar", loc=(0, 0, 1.0))
# Long curved hull (signature)
hull_main = smooth_cone("dr_hull", r1=2.5, r2=0.5, depth=14, segs=20, loc=(0, 0, 0),
                        parent=drakkar_e, mat_=M_DRAKKAR_WOOD)
hull_main.rotation_euler = (math.radians(90), 0, 0)
# Hull planking strakes (signature overlapping planks)
for pi in range(8):
    pz = -1.0 + pi * 0.3
    pl_w = 14 - pi * 0.2
    beveled_cube(f"plank{pi}", (1.8 - pi * 0.05, pl_w, 0.15), bevel_offset=0.04,
                 loc=(0, 0, pz), parent=drakkar_e, mat_=M_DRAKKAR_WOOD if pi % 2 == 0 else M_DRAKKAR_DARK)
# Top deck
beveled_cube("dr_deck", (3.5, 13, 0.20), bevel_offset=0.06, loc=(0, 0, 1.0),
             parent=drakkar_e, mat_=M_DRAKKAR_WOOD)
# Side rails with shields (signature)
for side in (-1, 1):
    beveled_cube(f"dr_rail{side}", (0.30, 12, 0.40), bevel_offset=0.04,
                 loc=(side*1.7, 0, 1.3), parent=drakkar_e, mat_=M_DRAKKAR_DARK)
    # 15 shields per side (30 total signature)
    for shi in range(15):
        sh_y = -5.5 + shi * 0.8
        shield_e = empty(f"sh_{side}_{shi}_e", (side*1.85, sh_y, 1.3), parent=drakkar_e)
        # Round shield
        shield_col = SHIELD_COLORS[shi % len(SHIELD_COLORS)]
        cyl(f"sh_{side}_{shi}", r=0.30, depth=0.06, segs=18, loc=(0, 0, 0),
            parent=shield_e, mat_=shield_col).rotation_euler = (0, math.radians(90), 0)
        # Boss center
        smooth_sphere(f"sh_{side}_{shi}_b", r=0.08, loc=(side*0.04, 0, 0),
                      parent=shield_e, mat_=M_SHIELD_BOSS, scale=(0.7, 1, 1))
        # Rim
        cyl(f"sh_{side}_{shi}_rm", r=0.31, depth=0.02, segs=20, loc=(0, 0, 0),
            parent=shield_e, mat_=M_DRAKKAR_DARK).rotation_euler = (0, math.radians(90), 0)
# DRAGON PROW (signature carved)
prow_e = empty("dr_prow", (0, 6.5, 1.0), parent=drakkar_e)
# Neck curving up
for ni in range(6):
    nz = ni * 0.5
    ny = math.sin(ni * 0.4) * 0.3
    cyl(f"prow_n{ni}", r=0.30 - ni*0.025, depth=0.55, segs=12,
        loc=(0, ny, nz), parent=prow_e, mat_=M_DRAKKAR_WOOD)
# Dragon head
head_p_e = empty("prow_he", (0, 0.5, 3.2), parent=prow_e)
head_p_e.rotation_euler = (math.radians(-30), 0, 0)
smooth_sphere("prow_head", r=0.45, segs=20, rings=14, loc=(0, 0, 0),
              parent=head_p_e, mat_=M_DRAKKAR_WOOD, scale=(1.3, 1.5, 1.0))
# Open mouth roar
smooth_sphere("prow_mouth", r=0.30, loc=(0, 0.40, -0.10),
              parent=head_p_e, mat_=M_DRAKKAR_RED, scale=(1.2, 0.8, 0.6))
# Teeth
for ti in range(8):
    cyl(f"prow_t{ti}", r=0.03, depth=0.10, segs=6,
        loc=((ti-3.5)*0.06, 0.40, -0.05), parent=head_p_e, mat_=M_SHIELD_BOSS)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"prow_eye{side}", r=0.06,
                  loc=(side*0.15, 0.25, 0.20), parent=head_p_e, mat_=M_EYE_BLUE_V)
# Horns
for side in (-1, 1):
    smooth_cone(f"prow_h{side}", r1=0.06, r2=0.01, depth=0.40, segs=8,
                loc=(side*0.15, -0.20, 0.30), parent=head_p_e,
                mat_=M_DRAKKAR_GOLD).rotation_euler = (math.radians(-30), 0, math.radians(side*30))
# STERN (other end - matching curve)
stern_e = empty("dr_stern", (0, -6.5, 1.0), parent=drakkar_e)
for ni in range(5):
    nz = ni * 0.5
    cyl(f"stern_n{ni}", r=0.25 - ni*0.02, depth=0.55, segs=12,
        loc=(0, 0, nz), parent=stern_e, mat_=M_DRAKKAR_WOOD)
# Stern curl
smooth_sphere("stern_curl", r=0.15, loc=(0, 0, 2.5), parent=stern_e, mat_=M_DRAKKAR_WOOD)

# MAST + SAIL (signature red striped)
mast_e = empty("mast", (0, 0, 1.0), parent=drakkar_e)
cyl("mast_pole", r=0.15, depth=8, segs=12, loc=(0, 0, 4), parent=mast_e, mat_=M_DRAKKAR_DARK)
# Horizontal yard
cyl("mast_yard", r=0.10, depth=6, segs=10, loc=(0, 0, 6),
    parent=mast_e, mat_=M_DRAKKAR_DARK).rotation_euler = (0, math.radians(90), 0)
# Sail base white
sail = beveled_cube("sail", (5.5, 0.10, 4), bevel_offset=0.05, loc=(0, 0, 4),
                    parent=mast_e, mat_=M_SAIL_WHITE)
sail["_phase"] = 0
# Red stripes (signature)
for ri in range(4):
    beveled_cube(f"sail_str{ri}", (5.5, 0.12, 0.4), bevel_offset=0.04,
                 loc=(0, 0.005, 2.5 + ri*0.8), parent=mast_e, mat_=M_SAIL_RED)
# Sail ropes
for side in (-1, 1):
    cyl(f"sail_rope{side}", r=0.025, depth=4.5, segs=6,
        loc=(side*2.5, 0, 4), parent=mast_e, mat_=M_ROPE).rotation_euler = (0, math.radians(side*15), 0)

# 18 ROWERS along benches (signature)
rowers = []
def make_rower(name, loc, scale=0.7, facing=0, side_idx=-1):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    tunic = random.choice(TUNIC_VARIANTS)
    hair = random.choice(HAIR_VARIANTS_V)
    # Tunic body
    smooth_cone(f"{name}_torso", r1=0.28*scale, r2=0.30*scale, depth=0.55*scale, segs=12,
                loc=(0, 0, 0.55*scale), parent=base, mat_=tunic)
    # Belt
    cyl(f"{name}_belt", r=0.28*scale, depth=0.08*scale, segs=14, loc=(0, 0, 0.55*scale),
        parent=base, mat_=M_LEATHER_BELT)
    # Pants
    for side_l in (-1, 1):
        cyl(f"{name}_leg{side_l}", r=0.08*scale, depth=0.50*scale, segs=8,
            loc=(side_l*0.10*scale, 0, 0.25*scale), parent=base, mat_=M_VIKING_PANTS_DARK)
    # Arms rowing position
    for side_arm in (-1, 1):
        sh = empty(f"{name}_sh{side_arm}", (side_arm*0.25*scale, 0, 0.85*scale), parent=base)
        sh.rotation_euler = (math.radians(-60), 0, math.radians(side_arm*-10))
        cyl(f"{name}_uarm{side_arm}", r=0.05*scale, depth=0.30*scale, segs=8,
            loc=(0, 0, -0.15*scale), parent=sh, mat_=tunic)
        # Hands forward (gripping oar)
        fa = empty(f"{name}_fa{side_arm}", (0, 0, -0.30*scale), parent=sh)
        fa.rotation_euler = (math.radians(-30), 0, 0)
        cyl(f"{name}_fa_b{side_arm}", r=0.04*scale, depth=0.30*scale, segs=8,
            loc=(0, 0, -0.15*scale), parent=fa, mat_=M_SKIN_VIKING)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.05*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.13*scale, segs=16, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_VIKING)
    # Beard
    for bi in range(6):
        ba = (bi / 6.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_bd{bi}", r=0.04*scale,
                      loc=(math.sin(ba)*0.10*scale, -0.12*scale, -0.10*scale),
                      parent=head_e, mat_=M_BEARD)
    # Hair tufts under helmet
    for hi in range(4):
        ha = (hi / 4.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.04*scale,
                      loc=(math.cos(ha)*0.12*scale, math.sin(ha)*0.05*scale, 0.05*scale),
                      parent=head_e, mat_=hair)
    # HELMET (signature rounded with nose guard)
    helmet_e = empty(f"{name}_helm", (0, 0, 0.15*scale), parent=head_e)
    smooth_sphere(f"{name}_helm_b", r=0.16*scale, segs=18, rings=12, loc=(0, 0, 0),
                  parent=helmet_e, mat_=M_HELMET_STEEL, scale=(1, 1, 0.8))
    # Nose guard
    beveled_cube(f"{name}_helm_n", (0.04*scale, 0.02*scale, 0.12*scale), bevel_offset=0.005,
                 loc=(0, -0.14*scale, -0.05*scale), parent=helmet_e, mat_=M_HELMET_STEEL)
    # Helmet rim
    cyl(f"{name}_helm_rim", r=0.16*scale, depth=0.03*scale, segs=18, loc=(0, 0, -0.08*scale),
        parent=helmet_e, mat_=M_HELMET_DARK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.05*scale, -0.11*scale, 0.02*scale),
                      parent=head_e, mat_=M_EYE_BLUE_V)
    # OAR (signature long extending out side)
    oar_side = -1 if side_idx == 0 else 1
    oar_e = empty(f"{name}_oar_e", (oar_side*0.30*scale, 0, 0.70*scale), parent=base)
    oar_e.rotation_euler = (0, 0, math.radians(oar_side*-75))
    cyl(f"{name}_oar_shaft", r=0.04*scale, depth=2.5*scale, segs=8,
        loc=(0, 1.25*scale, 0), parent=oar_e, mat_=M_AXE_HANDLE)
    # Paddle blade
    beveled_cube(f"{name}_oar_blade", (0.30*scale, 0.04*scale, 0.10*scale), bevel_offset=0.03,
                 loc=(0, 2.6*scale, 0), parent=oar_e, mat_=M_DRAKKAR_WOOD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "oar": oar_e, "he": head_e}

# 9 rowers per side
for ri in range(9):
    ry_pos = -4.5 + ri * 1.0
    # Left side
    r_l = make_rower(f"rower_L{ri}", (-0.5, ry_pos, 1.5), scale=0.7,
                     facing=math.radians(0), side_idx=0)
    rowers.append(r_l)
    # Right side
    r_r = make_rower(f"rower_R{ri}", (0.5, ry_pos, 1.5), scale=0.7,
                     facing=math.radians(0), side_idx=1)
    rowers.append(r_r)
# Parent rowers to drakkar
for r in rowers:
    r["root"].parent = drakkar_e

# CAPTAIN/KING at prow
captain_e = empty("captain", (0, 4.5, 2.0), parent=drakkar_e)
# King body taller
smooth_cone("cap_body", r1=0.32, r2=0.35, depth=0.7, segs=12, loc=(0, 0, 0.7),
            parent=captain_e, mat_=M_VIKING_TUNIC_GREEN)
# Fur cape (signature)
smooth_sphere("cap_cape", r=0.45, segs=18, rings=14, loc=(0, 0.10, 0.95),
              parent=captain_e, mat_=M_FUR_BROWN, scale=(1, 0.5, 1.2))
# Belt with gold buckle
cyl("cap_belt", r=0.35, depth=0.10, segs=14, loc=(0, 0, 0.70),
    parent=captain_e, mat_=M_LEATHER_BELT)
beveled_cube("cap_buckle", (0.10, 0.08, 0.12), bevel_offset=0.02, loc=(0, -0.32, 0.70),
             parent=captain_e, mat_=M_DRAKKAR_GOLD)
# Pants
for side_l in (-1, 1):
    cyl(f"cap_leg{side_l}", r=0.10, depth=0.7, segs=10,
        loc=(side_l*0.12, 0, 0.35), parent=captain_e, mat_=M_VIKING_PANTS_DARK)
# Head
cap_head_e = empty("cap_he", (0, 0, 1.55), parent=captain_e)
smooth_sphere("cap_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
              parent=cap_head_e, mat_=M_SKIN_VIKING)
# Big beard signature
for bi in range(12):
    ba = (bi / 12.0) * math.pi - math.pi/2
    smooth_sphere(f"cap_bd{bi}", r=0.05,
                  loc=(math.sin(ba)*0.13, -0.15, -0.10 - (bi%3)*0.05),
                  parent=cap_head_e, mat_=M_HAIR_BLOND_V)
# Eyes piercing blue
for side in (-1, 1):
    smooth_sphere(f"cap_eye{side}", r=0.04, loc=(side*0.06, -0.15, 0.03),
                  parent=cap_head_e, mat_=M_EYE_BLUE_V)
# CROWN HELMET (signature gold)
crown_e = empty("cap_cr_e", (0, 0, 0.18), parent=cap_head_e)
smooth_sphere("cap_cr_b", r=0.20, segs=20, rings=14, loc=(0, 0, 0),
              parent=crown_e, mat_=M_HELMET_GOLD, scale=(1, 1, 0.7))
# Crown spikes
for ci in range(8):
    ca = (ci / 8.0) * math.pi * 2
    smooth_cone(f"cap_cr_sp{ci}", r1=0.04, r2=0.005, depth=0.20, segs=8,
                loc=(math.cos(ca)*0.18, math.sin(ca)*0.18, 0.08),
                parent=crown_e, mat_=M_HELMET_GOLD)
# Sword in hand
sword_e = empty("cap_sword", (0.30, 0.10, 1.30), parent=captain_e)
sword_e.rotation_euler = (math.radians(-30), 0, math.radians(15))
beveled_cube("cap_sw_b", (0.04, 0.08, 1.5), bevel_offset=0.005, loc=(0, 0, 0.75),
             parent=sword_e, mat_=M_SWORD)
smooth_cone("cap_sw_p", r1=0.05, r2=0.005, depth=0.25, segs=8, loc=(0, 0, 1.55),
            parent=sword_e, mat_=M_SWORD)
cyl("cap_sw_cg", r=0.02, depth=0.30, segs=8, loc=(0, 0, 0.08), parent=sword_e,
    mat_=M_DRAKKAR_GOLD).rotation_euler = (0, math.radians(90), 0)
cyl("cap_sw_gr", r=0.025, depth=0.20, segs=8, loc=(0, 0, -0.10), parent=sword_e, mat_=M_AXE_HANDLE)

# ============ 4 TURF HOUSES (signature sod roof) ============
def make_turf_house(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Stone foundation
    beveled_cube(f"{name}_found", (3.5, 5, 0.4), bevel_offset=0.06, loc=(0, 0, 0.2),
                 parent=base, mat_=M_ROCK_DARK_V)
    # Log walls
    for li in range(7):
        lz = 0.4 + li * 0.35
        # Front + back walls
        for y_p in (-1, 1):
            cyl(f"{name}_log_y{li}_{y_p}", r=0.18, depth=3.5, segs=12,
                loc=(0, y_p*2.5, lz), parent=base,
                mat_=M_LOG_WALL if li % 2 == 0 else M_LOG_DARK).rotation_euler = (0, math.radians(90), 0)
        # Side walls
        for x_p in (-1, 1):
            cyl(f"{name}_log_x{li}_{x_p}", r=0.18, depth=5, segs=12,
                loc=(x_p*1.75, 0, lz), parent=base,
                mat_=M_LOG_WALL if li % 2 == 0 else M_LOG_DARK).rotation_euler = (math.radians(90), 0, 0)
    # Door
    beveled_cube(f"{name}_door", (0.8, 0.2, 1.5), bevel_offset=0.04, loc=(0, -2.5, 1.05),
                 parent=base, mat_=M_DOOR_VIKING)
    # Lit window
    beveled_cube(f"{name}_win", (0.5, 0.10, 0.4), bevel_offset=0.03, loc=(-1.2, -2.5, 1.5),
                 parent=base, mat_=M_WINDOW_LIT)
    # Roof beams sloped
    for side in (-1, 1):
        beam_e = empty(f"{name}_b{side}_e", (0, 0, 2.85), parent=base)
        beam_e.rotation_euler = (0, math.radians(side*30), 0)
        for bi in range(10):
            cyl(f"{name}_b{side}_{bi}", r=0.08, depth=5.5, segs=10,
                loc=(side*1.0, -2.5 + bi*0.55, 0.5),
                parent=beam_e, mat_=M_LOG_DARK).rotation_euler = (math.radians(90), 0, 0)
    # TURF ROOF (signature sod grass)
    for ri in range(8):
        rz = 2.85 + ri * 0.20
        rw = 3.5 - ri * 0.30
        beveled_cube(f"{name}_r{ri}", (rw, 5, 0.30), bevel_offset=0.06,
                     loc=(0, 0, rz + 0.15), parent=base,
                     mat_=M_TURF_DIRT if ri < 3 else M_TURF_ROOF)
    # Grass tufts on roof
    for gi in range(15):
        gx_g = random.uniform(-1.5, 1.5); gy_g = random.uniform(-2.4, 2.4)
        smooth_sphere(f"{name}_gt{gi}", r=0.12,
                      loc=(gx_g, gy_g, 4.5), parent=base, mat_=M_TURF_GRASS_TOP,
                      scale=(1, 1, 0.7))
    # Chimney smoke
    cyl(f"{name}_chim", r=0.15, depth=0.5, segs=10, loc=(0.8, 0, 4.7),
        parent=base, mat_=M_ROCK_DARK_V)
    return base

houses = []
house_pos = [(-25, -30, math.radians(15)), (-22, -22, math.radians(-15)),
              (25, -30, math.radians(165)), (22, -22, math.radians(195))]
for i, (hx, hy, fac) in enumerate(house_pos):
    h = make_turf_house(f"house{i}", (hx, hy, 0), scale=1.0, facing=fac)
    houses.append(h)

# ============ STAVE CHURCH (signature stacked roofs + dragon heads) ============
church_e = empty("church", loc=(0, -35, 0))
# Base
beveled_cube("ch_base", (6, 6, 1), bevel_offset=0.10, loc=(0, 0, 0.5),
             parent=church_e, mat_=M_STAVE_DARK)
# Walls
beveled_cube("ch_walls", (5, 5, 4), bevel_offset=0.10, loc=(0, 0, 3),
             parent=church_e, mat_=M_STAVE_DARK)
# Decorative vertical staves
for x_p in (-1, 1):
    for y_p in (-1, 1):
        cyl(f"ch_stave_{x_p}_{y_p}", r=0.30, depth=5, segs=12,
            loc=(x_p*2.4, y_p*2.4, 2.5), parent=church_e, mat_=M_STAVE_LIGHT)
# 4 STACKED ROOFS (signature)
for ri in range(4):
    rz = 5 + ri * 1.8
    rw = 5.2 - ri * 0.8
    # Pyramidal roof
    smooth_cone(f"ch_r{ri}", r1=rw, r2=rw*0.4, depth=1.5, segs=4, loc=(0, 0, rz + 0.75),
                parent=church_e, mat_=M_STAVE_DARK)
    # Decorative trim
    cyl(f"ch_rt{ri}", r=rw, depth=0.15, segs=12, loc=(0, 0, rz),
        parent=church_e, mat_=M_STAVE_LIGHT)
    # Dragon heads at corners (signature)
    if ri < 3:
        for corner_x in (-1, 1):
            for corner_y in (-1, 1):
                cx_c = corner_x * (rw - 0.5); cy_c = corner_y * (rw - 0.5)
                dragon_h_e = empty(f"ch_dr_{ri}_{corner_x}_{corner_y}_e",
                                    (cx_c, cy_c, rz + 0.8), parent=church_e)
                # Dragon head/neck
                cyl(f"ch_dr_n{ri}_{corner_x}_{corner_y}", r=0.10, depth=0.50, segs=10,
                    loc=(0, 0, 0.25), parent=dragon_h_e, mat_=M_DRAGON_HEAD)
                # Head
                smooth_sphere(f"ch_dr_h{ri}_{corner_x}_{corner_y}", r=0.18, segs=14, rings=10,
                              loc=(0, 0, 0.55), parent=dragon_h_e, mat_=M_DRAGON_HEAD,
                              scale=(1.4, 0.9, 1.0))
# Top crucifix/spire
cyl("ch_sp", r=0.10, depth=2, segs=10, loc=(0, 0, 13.5), parent=church_e, mat_=M_STAVE_LIGHT)
# Cross
beveled_cube("ch_cross_v", (0.10, 0.10, 0.8), bevel_offset=0.02, loc=(0, 0, 14.5),
             parent=church_e, mat_=M_RUNE_GOLD)
beveled_cube("ch_cross_h", (0.10, 0.50, 0.10), bevel_offset=0.02, loc=(0, 0, 14.7),
             parent=church_e, mat_=M_RUNE_GOLD)
# Door + rune carvings
beveled_cube("ch_door", (1.2, 0.20, 2.5), bevel_offset=0.06, loc=(0, -2.5, 1.5),
             parent=church_e, mat_=M_DOOR_VIKING)
# Runes
for ri in range(4):
    smooth_sphere(f"ch_rune{ri}", r=0.06, loc=(0.5 - ri*0.30, -2.6, 2.2),
                  parent=church_e, mat_=M_RUNE_GOLD)

# ============ SNOW FIR TREES ============
for ti in range(8):
    ta = (ti / 8.0) * math.pi * 2 + math.pi/8
    tx = math.cos(ta) * 40 + random.uniform(-3, 3)
    ty = math.sin(ta) * 40 + random.uniform(-3, 3)
    if -10 < tx < 10 and -50 < ty < 50: continue  # avoid fjord
    t_e = empty(f"fir{ti}", (tx, ty, 0))
    # Trunk
    cyl(f"fir{ti}_t", r=0.30, depth=2, segs=12, loc=(0, 0, 1), parent=t_e, mat_=M_TRUNK_PINE_V)
    # Layered cone with snow caps
    for li in range(6):
        lz = 1.5 + li * 1.5
        lr = 2.5 - li * 0.35
        cone = smooth_cone(f"fir{ti}_l{li}", r1=lr, r2=0.10, depth=2.0, segs=14, loc=(0, 0, lz),
                           parent=t_e, mat_=M_FIR_DARK_V)
        # Snow on top of cone
        smooth_cone(f"fir{ti}_sn{li}", r1=lr*0.7, r2=0.10, depth=0.5, segs=14, loc=(0, 0, lz + 0.7),
                    parent=t_e, mat_=M_FIR_SNOW)

# ============ CAMPFIRE on shore ============
campfire_e = empty("campfire", (-15, -5, 0))
# Stone ring
for si in range(8):
    sa = (si / 8.0) * math.pi * 2
    smooth_sphere(f"cf_st{si}", r=0.20, loc=(math.cos(sa)*0.6, math.sin(sa)*0.6, 0.15),
                  parent=campfire_e, mat_=M_ROCK_DARK_V)
# Logs
for li in range(4):
    la = (li / 4.0) * math.pi
    cyl(f"cf_log{li}", r=0.06, depth=0.7, segs=8, loc=(0, 0, 0.20),
        parent=campfire_e, mat_=M_LOG_WALL).rotation_euler = (0, math.radians(90), la*0.5)
# Flames (signature)
flame_e = empty("cf_flame", (0, 0, 0.35), parent=campfire_e)
smooth_cone("cf_fo", r1=0.30, r2=0.05, depth=1.2, segs=14, loc=(0, 0, 0.6), parent=flame_e, mat_=M_FIRE_OUTER_V)
smooth_cone("cf_fc", r1=0.20, r2=0.02, depth=0.9, segs=14, loc=(0, 0, 0.45), parent=flame_e, mat_=M_FIRE_CORE_V)

# ============================================================
# ⭐ 600 AURORA + 400 SNOW (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 aurora particles (wavy)
aurora_particles = []
for i in range(600):
    px = random.uniform(-80, 80)
    py = random.uniform(-60, 60)
    pz = random.uniform(30, 65)
    aur_col = random.choice(AURORA_COLORS)
    a_obj = smooth_sphere(f"aur_p{i}", r=random.uniform(0.20, 0.45), segs=10, rings=6,
                          loc=(px, py, pz), mat_=aur_col, scale=(2.0, 0.8, 0.5))
    a_obj["_phase"] = random.uniform(0, math.pi*2)
    a_obj["_base_x"] = px; a_obj["_base_y"] = py; a_obj["_base_z"] = pz
    a_obj["_amp_x"] = random.uniform(2.0, 5.0)
    a_obj["_amp_y"] = random.uniform(0.8, 2.0)
    a_obj["_amp_z"] = random.uniform(0.5, 1.5)
    a_obj["_speed"] = random.uniform(0.3, 0.8)
    aurora_particles.append(a_obj)

# 400 snowflakes
snowflakes = []
for i in range(400):
    px = random.uniform(-60, 60)
    py = random.uniform(-60, 60)
    pz = random.uniform(1, 20)
    s_obj = smooth_sphere(f"snow{i}", r=random.uniform(0.06, 0.10), segs=8, rings=6,
                          loc=(px, py, pz), mat_=M_SNOW_FLAKE)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(1.0, 2.5)
    s_obj["_amp_y"] = random.uniform(1.0, 2.5)
    s_obj["_speed"] = random.uniform(0.4, 0.9)
    s_obj["_fall"] = random.uniform(1.5, 3.0)
    snowflakes.append(s_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Drakkar slow wave bob
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    drakkar_e.location.z = 1.0 + math.sin(t * 1.0) * 0.15
    drakkar_e.rotation_euler = (math.sin(t * 1.0) * math.radians(3),
                                 math.cos(t * 1.0) * math.radians(2), 0)
    drakkar_e.keyframe_insert("location", frame=f)
    drakkar_e.keyframe_insert("rotation_euler", frame=f)

# Rowers synchronized
for ri, r in enumerate(rowers):
    phase = r["root"]["_phase"]
    # All rowers same wave phase
    sync_phase = phase * 0.3
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Synchronized rowing motion
        r["oar"].rotation_euler = (r["oar"].rotation_euler.x,
                                    math.sin(t * 2.0 + sync_phase) * math.radians(20),
                                    r["oar"].rotation_euler.z)
        r["oar"].keyframe_insert("rotation_euler", frame=f)
        # Body lean
        r["root"].rotation_euler = (math.sin(t * 2.0 + sync_phase) * math.radians(5),
                                     0, r["root"].rotation_euler.z)
        r["root"].keyframe_insert("rotation_euler", frame=f)

# Captain head turn proud
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    cap_head_e.rotation_euler = (0, 0, math.sin(t * 0.6) * math.radians(20))
    cap_head_e.keyframe_insert("rotation_euler", frame=f)

# Aurora bands wave
for au in range(6):
    band = bpy.data.objects.get(f"aurora{au}_e")
    if band is None: continue
    phase = band["_phase"]
    by_a = band.location.y
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        band.location.y = by_a + math.sin(t * 0.8 + phase) * 4
        band.location.z = band.location.z + math.sin(t * 0.5 + phase) * 0.2
        band.keyframe_insert("location", frame=f)

# Campfire flicker
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    sc_fl = 1 + math.sin(t * 6.0) * 0.15
    flame_e.scale = (1 + math.cos(t * 5.0) * 0.10, 1 + math.sin(t * 5.0) * 0.10, sc_fl)
    flame_e.rotation_euler = (0, 0, math.sin(t * 4.0) * 0.2)
    flame_e.keyframe_insert("scale", frame=f)
    flame_e.keyframe_insert("rotation_euler", frame=f)

# Sail wave with wind
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    sail.rotation_euler = (math.sin(t * 1.2) * math.radians(5),
                            math.cos(t * 1.2) * math.radians(3), 0)
    sail.keyframe_insert("rotation_euler", frame=f)

# 600 aurora particles wave
for a in aurora_particles:
    phase = a["_phase"]; speed = a["_speed"]
    bx, by, bz = a["_base_x"], a["_base_y"], a["_base_z"]
    ax_a, ay_a, az_a = a["_amp_x"], a["_amp_y"], a["_amp_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + ax_a * math.sin(t * speed + phase)
        y = by + ay_a * math.cos(t * speed * 0.9 + phase)
        z = bz + az_a * math.sin(t * speed * 1.3 + phase)
        a.location = (x, y, z)
        a.keyframe_insert("location", frame=f)

# 400 snow falls
for s in snowflakes:
    phase = s["_phase"]; speed = s["_speed"]; fall = s["_fall"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax_s, ay_s = s["_amp_x"], s["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax_s * math.sin(t * speed + phase)
        y = by + ay_s * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.5)
        if z < 0.5: z = bz
        s.location = (x, y, max(0.3, z))
        s.rotation_euler = (t * 2.0 + phase, t * 1.5 + phase, t * 2.5 + phase)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_viking_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_norwegian_fjord_viking_ship] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_norwegian_fjord_viking_ship] drakkar + 18 rowers + king captain + 30 shields + dragon prow + 4 turf houses + stave church + 8 firs + campfire + 600 aurora + 400 snow")
print("⭐ FIXES: 1 ground + 600 aurora + 400 snow (signature Norwegian fjord mandatory) ⭐")
