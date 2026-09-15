"""
proc_petra_jordan_treasury_canyon.py — 281e procédural AuroraIA (146e qualité)
Petra Jordan Treasury canyon: Al-Khazneh Nabataean facade + Siq canyon walls + 4 Bedouins + 6 camels + Ad-Deir monastery + Jordan flag + 600 red sand swirls + 400 walking camels
FIXES : 1 ground red sand desert + signature sand + camels
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB281)

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

# Desert sky
M_SKY = mat("sky", (0.85, 0.65, 0.45, 1.0), 0.0, 0.7, emission=(0.82,0.62,0.42), emission_strength=2.0)
M_SKY_LOW = mat("sky_l", (0.95, 0.78, 0.55, 1.0), 0.0, 0.7, emission=(0.92,0.75,0.55), emission_strength=1.7)
M_SUN = mat("sun", (1.0, 0.85, 0.45, 1.0), 0.0, 0.1, emission=(1.0,0.85,0.45), emission_strength=20.0)

# Red sand (signature Petra)
M_SAND_RED = mat("sr", (0.85, 0.45, 0.32, 1.0), 0.0, 0.85, emission=(0.82,0.42,0.30), emission_strength=0.4)
M_SAND_DARK = mat("sd", (0.62, 0.32, 0.22, 1.0), 0.0, 0.92)
M_SAND_LIGHT = mat("sl", (0.95, 0.62, 0.45, 1.0), 0.0, 0.75, emission=(0.92,0.60,0.45), emission_strength=0.5)
M_SAND_PINK = mat("sp", (0.92, 0.55, 0.42, 1.0), 0.0, 0.85, emission=(0.88,0.55,0.40), emission_strength=0.5)
M_DUST = mat("d", (0.78, 0.55, 0.40, 1.0), 0.0, 0.92, alpha=0.65)

# Rock walls (signature Nabataean carved sandstone)
M_ROCK_RED = mat("rkr", (0.78, 0.40, 0.28, 1.0), 0.0, 0.85, emission=(0.75,0.40,0.28), emission_strength=0.4)
M_ROCK_PINK = mat("rkp", (0.85, 0.55, 0.45, 1.0), 0.0, 0.80, emission=(0.82,0.55,0.45), emission_strength=0.5)
M_ROCK_DARK = mat("rkd", (0.52, 0.28, 0.20, 1.0), 0.0, 0.92)
M_ROCK_ORANGE = mat("rko", (0.92, 0.55, 0.30, 1.0), 0.0, 0.85, emission=(0.88,0.55,0.30), emission_strength=0.5)
M_ROCK_STRIATION = mat("rks", (0.65, 0.32, 0.22, 1.0), 0.0, 0.90)

# Treasury detail
M_FACADE_GLOW = mat("fg", (0.95, 0.65, 0.42, 1.0), 0.0, 0.80, emission=(0.92,0.62,0.40), emission_strength=0.7)

# Bedouin
M_SKIN_TAN = mat("sk", (0.78, 0.55, 0.38, 1.0), 0.0, 0.55, emission=(0.75,0.55,0.38), emission_strength=0.3)
M_HAIR_BLACK = mat("hb", (0.10, 0.08, 0.06, 1.0), 0.0, 0.85)

# Thawb (signature white robe)
M_THAWB_WHITE = mat("tw", (0.92, 0.90, 0.82, 1.0), 0.0, 0.55, emission=(0.90,0.88,0.82), emission_strength=0.4)
M_THAWB_BROWN = mat("tbr", (0.55, 0.38, 0.22, 1.0), 0.0, 0.65, emission=(0.52,0.38,0.22), emission_strength=0.3)

# Keffiyeh (signature red checkered)
M_KEFFIYEH_RED = mat("kr", (0.85, 0.25, 0.22, 1.0), 0.0, 0.55, emission=(0.82,0.25,0.22), emission_strength=0.5)
M_KEFFIYEH_WHITE = mat("kw", (0.92, 0.90, 0.85, 1.0), 0.0, 0.55)
M_KEFFIYEH_BLACK = mat("kb", (0.18, 0.15, 0.13, 1.0), 0.0, 0.65)
M_AGAL = mat("ag", (0.10, 0.08, 0.06, 1.0), 0.2, 0.45)

# Camel (signature)
M_CAMEL_TAN = mat("ct", (0.82, 0.62, 0.42, 1.0), 0.0, 0.75, emission=(0.80,0.62,0.42), emission_strength=0.3)
M_CAMEL_DARK = mat("cdk", (0.55, 0.38, 0.22, 1.0), 0.0, 0.85)
M_CAMEL_BELLY = mat("cbe", (0.95, 0.82, 0.62, 1.0), 0.0, 0.65)
M_SADDLE = mat("sa", (0.85, 0.30, 0.22, 1.0), 0.0, 0.55, emission=(0.82,0.30,0.22), emission_strength=0.5)
M_SADDLE_GOLD = mat("sag", (0.95, 0.78, 0.20, 1.0), 0.6, 0.30, emission=(0.92,0.75,0.20), emission_strength=0.8)
M_TASSEL = mat("ts", (0.55, 0.18, 0.20, 1.0), 0.0, 0.65, emission=(0.52,0.18,0.20), emission_strength=0.5)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Jordan flag
M_FLAG_BLACK = mat("fb", (0.10, 0.08, 0.06, 1.0), 0.0, 0.45)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_FLAG_GREEN = mat("fgr", (0.18, 0.55, 0.28, 1.0), 0.0, 0.45, emission=(0.18,0.52,0.28), emission_strength=1.0)
M_FLAG_RED = mat("fr", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=1.0)
M_FLAG_STAR = mat("fs", (0.95, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.88), emission_strength=2.5)

# Sand swirl particles
M_SAND_PT = mat("spt", (0.92, 0.55, 0.32, 1.0), 0.0, 0.40, emission=(0.90,0.55,0.30), emission_strength=1.5)
M_SAND_PT_DARK = mat("sptd", (0.72, 0.42, 0.22, 1.0), 0.0, 0.55, emission=(0.70,0.42,0.22), emission_strength=1.2)
M_SAND_PT_LIGHT = mat("sptl", (1.0, 0.72, 0.42, 1.0), 0.0, 0.35, emission=(0.95,0.70,0.42), emission_strength=1.8)
SAND_COLORS = [M_SAND_PT, M_SAND_PT_DARK, M_SAND_PT_LIGHT]

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=10, segs=24, rings=18, loc=(40, 90, 40), mat_=M_SUN)
for sh in range(4):
    smooth_sphere(f"sun_h{sh}", r=10 + sh*1.2, segs=24, rings=18, loc=(40, 90, 40), mat_=M_SUN)

# ============ ONE clean red sand ground ============
ground = beveled_cube("ground", (300, 300, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_SAND_RED)
# Sand dunes (organic 3D)
for hi in range(250):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 140)
    smooth_sphere(f"dn{hi}", r=random.uniform(1.5, 3.5), segs=12, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_SAND_DARK if hi % 3 == 0 else (M_SAND_LIGHT if hi % 3 == 1 else M_SAND_PINK),
                  scale=(1.5, 1.4, 0.20))

# ============ SIQ CANYON (signature narrow walls leading to Treasury) ============
canyon_e = empty("canyon", (0, 0, 0))
# Left canyon wall
for wi in range(20):
    wy = -60 + wi * 6
    wall_height = random.uniform(25, 35)
    # Wall column
    wall_col_e = empty(f"wl{wi}_e", (-20, wy, 0), parent=canyon_e)
    for li in range(int(wall_height / 2.5)):
        smooth_sphere(f"wl{wi}_s{li}", r=random.uniform(3, 4.5), segs=14, rings=12,
                      loc=(random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3),
                           li*2.5 + 1.5),
                      parent=wall_col_e,
                      mat_=M_ROCK_RED if li % 2 == 0 else M_ROCK_ORANGE,
                      scale=(1.4, 1.4, 1.0))
    # Rock striations (signature horizontal layers)
    for sti in range(int(wall_height / 4)):
        cyl(f"wl{wi}_st{sti}", r=4.5, depth=0.30, segs=14, loc=(0, 0, sti*4 + 2),
            parent=wall_col_e, mat_=M_ROCK_STRIATION)
# Right canyon wall
for wi in range(20):
    wy = -60 + wi * 6
    wall_height = random.uniform(25, 35)
    wall_col_e = empty(f"wr{wi}_e", (20, wy, 0), parent=canyon_e)
    for li in range(int(wall_height / 2.5)):
        smooth_sphere(f"wr{wi}_s{li}", r=random.uniform(3, 4.5), segs=14, rings=12,
                      loc=(random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3),
                           li*2.5 + 1.5),
                      parent=wall_col_e,
                      mat_=M_ROCK_PINK if li % 2 == 0 else M_ROCK_RED,
                      scale=(1.4, 1.4, 1.0))
    for sti in range(int(wall_height / 4)):
        cyl(f"wr{wi}_st{sti}", r=4.5, depth=0.30, segs=14, loc=(0, 0, sti*4 + 2),
            parent=wall_col_e, mat_=M_ROCK_STRIATION)

# ============ AL-KHAZNEH TREASURY (signature Nabataean carved facade) ============
treasury_e = empty("treasury", (0, 50, 0))
# Cliff backdrop (signature carved INTO cliff)
beveled_cube("tr_cf", (35, 5, 35), bevel_offset=0.10, loc=(0, 3, 17.5),
             parent=treasury_e, mat_=M_ROCK_PINK)

# LOWER LEVEL (signature 6 columns + portico)
# Lower platform
beveled_cube("tr_pl", (22, 2, 1), bevel_offset=0.10, loc=(0, -0.5, 0.5),
             parent=treasury_e, mat_=M_FACADE_GLOW)
# Stairs
for si_s in range(4):
    beveled_cube(f"tr_st{si_s}", (10, 1, 0.20), bevel_offset=0.04,
                 loc=(0, -1.5 - si_s*0.5, 0.10 + si_s*0.20), parent=treasury_e, mat_=M_FACADE_GLOW)
# 6 columns (signature Hellenistic)
for ci in range(6):
    cx = -10 + ci * 4
    # Column shaft (fluted)
    cyl(f"tr_c{ci}", r=0.8, depth=12, segs=18, loc=(cx, 0.5, 7),
        parent=treasury_e, mat_=M_FACADE_GLOW)
    # Column flutes
    for fi in range(12):
        fa = (fi / 12.0) * math.pi * 2
        cyl(f"tr_c{ci}_f{fi}", r=0.08, depth=11.5, segs=6,
            loc=(cx + math.cos(fa)*0.75, 0.5 + math.sin(fa)*0.75, 7),
            parent=treasury_e, mat_=M_ROCK_DARK)
    # Capital (top decoration)
    cyl(f"tr_c{ci}_cap", r=1.0, depth=0.30, segs=14, loc=(cx, 0.5, 12.7),
        parent=treasury_e, mat_=M_FACADE_GLOW)
    # Base
    cyl(f"tr_c{ci}_bs", r=0.9, depth=0.40, segs=14, loc=(cx, 0.5, 1.2),
        parent=treasury_e, mat_=M_FACADE_GLOW)
# Entablature (horizontal beam over columns)
beveled_cube("tr_en", (24, 3, 1.5), bevel_offset=0.10, loc=(0, 1, 13.5),
             parent=treasury_e, mat_=M_FACADE_GLOW)
# Triangular pediment over portico
for pri in range(8):
    pri_t = pri / 8.0
    pediment_w = 11 * (1 - pri_t)
    beveled_cube(f"tr_pd{pri}", (pediment_w, 1.5, 0.40), bevel_offset=0.04,
                 loc=(0, 1, 14.5 + pri*0.30), parent=treasury_e, mat_=M_FACADE_GLOW)
# Entrance door (signature dark cave entrance)
beveled_cube("tr_dr", (3, 0.20, 7), bevel_offset=0.10, loc=(0, -0.4, 5),
             parent=treasury_e, mat_=M_ROCK_DARK)
# Door frame ornate
beveled_cube("tr_df_t", (4, 0.30, 0.40), bevel_offset=0.06, loc=(0, -0.4, 8.7),
             parent=treasury_e, mat_=M_ROCK_DARK)
for side in (-1, 1):
    beveled_cube(f"tr_df_{side}", (0.40, 0.30, 7), bevel_offset=0.06,
                 loc=(side*1.7, -0.4, 5), parent=treasury_e, mat_=M_ROCK_DARK)

# UPPER LEVEL (signature 2 wing pediments + central tholos)
upper_e = empty("tr_up", (0, 0, 17), parent=treasury_e)
# Left wing
beveled_cube("tr_lw", (7, 2, 4), bevel_offset=0.10, loc=(-7, 1, 2),
             parent=upper_e, mat_=M_FACADE_GLOW)
# Half pediment left
for pi in range(5):
    pi_t = pi / 5.0
    beveled_cube(f"tr_hpl{pi}", (5 * (1 - pi_t), 1.5, 0.40), bevel_offset=0.04,
                 loc=(-7, 1, 4 + pi*0.30), parent=upper_e, mat_=M_FACADE_GLOW)
# Right wing
beveled_cube("tr_rw", (7, 2, 4), bevel_offset=0.10, loc=(7, 1, 2),
             parent=upper_e, mat_=M_FACADE_GLOW)
for pi in range(5):
    pi_t = pi / 5.0
    beveled_cube(f"tr_hpr{pi}", (5 * (1 - pi_t), 1.5, 0.40), bevel_offset=0.04,
                 loc=(7, 1, 4 + pi*0.30), parent=upper_e, mat_=M_FACADE_GLOW)
# CENTRAL THOLOS (signature circular pavilion top)
tholos_e = empty("tr_th", (0, 1, 4), parent=upper_e)
# Circular base
cyl("tr_th_b", r=3, depth=0.8, segs=18, loc=(0, 0, 0), parent=tholos_e, mat_=M_FACADE_GLOW)
# 8 columns around tholos
for tci in range(8):
    tca = (tci / 8.0) * math.pi * 2
    cyl(f"tr_th_c{tci}", r=0.30, depth=4, segs=10,
        loc=(math.cos(tca)*2.7, math.sin(tca)*2.7, 2.4),
        parent=tholos_e, mat_=M_FACADE_GLOW)
# Tholos roof (cone)
smooth_cone("tr_th_r", r1=3.5, r2=1.0, depth=2, segs=18, loc=(0, 0, 5.5),
            parent=tholos_e, mat_=M_FACADE_GLOW)
# URN ON TOP (signature - legend says treasure hidden inside)
urn_e = empty("tr_ur", (0, 0, 7.5), parent=tholos_e)
smooth_sphere("tr_ur_b", r=0.50, segs=14, rings=12, loc=(0, 0, 0),
              parent=urn_e, mat_=M_FACADE_GLOW, scale=(1, 1, 1.3))
cyl("tr_ur_n", r=0.20, depth=0.30, segs=10, loc=(0, 0, 0.50),
    parent=urn_e, mat_=M_FACADE_GLOW)
# Niche carvings between tholos columns (signature statues)
for ni in range(4):
    nia = (ni / 4.0) * math.pi * 2 + math.pi/8
    # Niche figure (Castor/Pollux/Isis style)
    fig_e = empty(f"tr_ni{ni}", (math.cos(nia)*4, math.sin(nia)*4 + 1, 0 + 17 + 1), parent=treasury_e)
    smooth_cone(f"tr_ni{ni}_b", r1=0.3, r2=0.35, depth=2.5, segs=10, loc=(0, 0, 1.25),
                parent=fig_e, mat_=M_ROCK_DARK)
    smooth_sphere(f"tr_ni{ni}_h", r=0.25, segs=12, rings=10, loc=(0, 0, 2.7),
                  parent=fig_e, mat_=M_ROCK_DARK)
# Frieze (decorative band)
beveled_cube("tr_fr", (24, 3.1, 0.40), bevel_offset=0.06, loc=(0, 1, 14.8),
             parent=treasury_e, mat_=M_ROCK_DARK)
# Crowning element on pediment apex
smooth_sphere("tr_apx", r=0.8, segs=14, rings=10, loc=(0, 1, 17.5),
              parent=treasury_e, mat_=M_FACADE_GLOW)

# ============ AD-DEIR MONASTERY (signature distant peak) ============
deir_e = empty("deir", (-60, 90, 0))
# Cliff backdrop
beveled_cube("dr_cf", (28, 4, 28), bevel_offset=0.08, loc=(0, 2, 14),
             parent=deir_e, mat_=M_ROCK_RED)
# Lower facade - 4 columns
for ci in range(4):
    cx_d = -7 + ci * 4
    cyl(f"dr_c{ci}", r=0.7, depth=10, segs=14, loc=(cx_d, 0, 6),
        parent=deir_e, mat_=M_FACADE_GLOW)
    cyl(f"dr_c{ci}_cap", r=0.85, depth=0.30, segs=12, loc=(cx_d, 0, 11.3),
        parent=deir_e, mat_=M_FACADE_GLOW)
# Entablature
beveled_cube("dr_en", (18, 2, 1.2), bevel_offset=0.08, loc=(0, 0, 12),
             parent=deir_e, mat_=M_FACADE_GLOW)
# Door
beveled_cube("dr_dr", (2.5, 0.2, 6), bevel_offset=0.08, loc=(0, -0.4, 4.5),
             parent=deir_e, mat_=M_ROCK_DARK)
# Upper level with central tholos
upper_d_e = empty("dr_up", (0, 0, 13), parent=deir_e)
# Side wings smaller
for wing_s in (-1, 1):
    beveled_cube(f"dr_wg{wing_s}", (6, 1.5, 4), bevel_offset=0.08, loc=(wing_s*6, 0, 2),
                 parent=upper_d_e, mat_=M_FACADE_GLOW)
# Tholos
cyl("dr_th_b", r=2.5, depth=0.6, segs=18, loc=(0, 0, 1.5), parent=upper_d_e, mat_=M_FACADE_GLOW)
for tci in range(8):
    tca = (tci / 8.0) * math.pi * 2
    cyl(f"dr_th_c{tci}", r=0.25, depth=3.5, segs=10,
        loc=(math.cos(tca)*2.2, math.sin(tca)*2.2, 3.5), parent=upper_d_e, mat_=M_FACADE_GLOW)
smooth_cone("dr_th_r", r1=3, r2=0.8, depth=1.8, segs=18, loc=(0, 0, 6),
            parent=upper_d_e, mat_=M_FACADE_GLOW)
# Big urn (signature - "Ad-Deir" means monastery, the dome's urn is larger)
smooth_sphere("dr_ur_b", r=0.7, segs=14, rings=12, loc=(0, 0, 7.7),
              parent=upper_d_e, mat_=M_FACADE_GLOW, scale=(1, 1, 1.3))
cyl("dr_ur_n", r=0.25, depth=0.40, segs=10, loc=(0, 0, 8.5),
    parent=upper_d_e, mat_=M_FACADE_GLOW)

# ============ 6 CAMELS (signature) ============
def make_camel(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_bo", r=0.7, segs=14, rings=12, loc=(0, 0, 1.50),
                  parent=base, mat_=M_CAMEL_TAN, scale=(1.6, 0.85, 0.85))
    # Hump (signature single hump dromedary)
    smooth_sphere(f"{name}_hp", r=0.50, segs=14, rings=12, loc=(0, 0, 2.0),
                  parent=base, mat_=M_CAMEL_DARK, scale=(0.9, 0.85, 1.2))
    # Belly cream
    smooth_sphere(f"{name}_be", r=0.55, segs=12, rings=10, loc=(0, 0, 1.25),
                  parent=base, mat_=M_CAMEL_BELLY, scale=(1.5, 0.85, 0.55))
    # SADDLE on hump (signature red with tassels)
    saddle_e = empty(f"{name}_sd_e", (0, 0, 2.35), parent=base)
    beveled_cube(f"{name}_sd_b", (1.0, 0.85, 0.30), bevel_offset=0.06, loc=(0, 0, 0),
                 parent=saddle_e, mat_=M_SADDLE)
    # Saddle gold trim
    beveled_cube(f"{name}_sd_g", (1.05, 0.90, 0.06), bevel_offset=0.02, loc=(0, 0, 0.18),
                 parent=saddle_e, mat_=M_SADDLE_GOLD)
    # Tassels hanging
    for ti in range(6):
        ta = (ti / 6.0) * math.pi * 2
        for tji in range(3):
            cyl(f"{name}_ts{ti}_{tji}", r=0.02, depth=0.15, segs=4,
                loc=(math.cos(ta)*0.55, math.sin(ta)*0.45, -tji*0.15 - 0.05),
                parent=saddle_e, mat_=M_TASSEL)
    # Long neck (signature S-curve)
    neck_e = empty(f"{name}_ne", (0.80, 0, 1.85), parent=base)
    neck_e.rotation_euler = (0, math.radians(-35), 0)
    for ni in range(6):
        cyl(f"{name}_n{ni}", r=0.18 - ni*0.005, depth=0.22, segs=10,
            loc=(0, 0, 0.15 + ni*0.22), parent=neck_e, mat_=M_CAMEL_TAN)
    # Head
    head_c_e = empty(f"{name}_he", (0, 0, 1.50), parent=neck_e)
    smooth_sphere(f"{name}_h", r=0.22, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_c_e, mat_=M_CAMEL_TAN, scale=(1.4, 0.85, 0.85))
    # Long snout
    smooth_sphere(f"{name}_sn", r=0.15, segs=10, rings=8, loc=(0.20, 0, -0.10),
                  parent=head_c_e, mat_=M_CAMEL_DARK, scale=(1.3, 0.85, 0.85))
    # Long ears
    for side in (-1, 1):
        smooth_cone(f"{name}_er{side}", r1=0.05, r2=0.01, depth=0.18, segs=8,
                    loc=(-0.10, side*0.12, 0.18), parent=head_c_e, mat_=M_CAMEL_TAN)
    # Eyes (long lashes)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.04, loc=(0.08, side*0.13, 0.04),
                      parent=head_c_e, mat_=M_EYE)
    # Eyelashes (signature)
    for side in (-1, 1):
        for li in range(4):
            cyl(f"{name}_el{side}_{li}", r=0.005, depth=0.04, segs=4,
                loc=(0.10, side*0.13, 0.10 + li*0.01),
                parent=head_c_e, mat_=M_CAMEL_DARK).rotation_euler = (0, math.radians(30), 0)
    # 4 long legs (signature)
    for li, (lx_c, ly_c) in enumerate([(0.55, 0.30), (0.55, -0.30), (-0.55, 0.30), (-0.55, -0.30)]):
        leg_e = empty(f"{name}_le{li}", (lx_c, ly_c, 1.10), parent=base)
        # Upper leg
        cyl(f"{name}_ul{li}", r=0.12, depth=0.55, segs=10, loc=(0, 0, -0.28),
            parent=leg_e, mat_=M_CAMEL_TAN)
        # Knee
        smooth_sphere(f"{name}_kn{li}", r=0.12, segs=12, rings=8, loc=(0, 0, -0.55),
                      parent=leg_e, mat_=M_CAMEL_TAN)
        # Lower leg
        cyl(f"{name}_ll{li}", r=0.10, depth=0.55, segs=10, loc=(0, 0, -0.82),
            parent=leg_e, mat_=M_CAMEL_TAN)
        # Foot (signature wide pad)
        beveled_cube(f"{name}_ft{li}", (0.18, 0.20, 0.10), bevel_offset=0.03,
                     loc=(0, 0, -1.10), parent=leg_e, mat_=M_CAMEL_DARK)
    # Short tail with tuft
    tail_e = empty(f"{name}_te", (-0.65, 0, 1.65), parent=base)
    tail_e.rotation_euler = (0, math.radians(120), 0)
    for ti in range(4):
        cyl(f"{name}_t{ti}", r=0.06 - ti*0.008, depth=0.10, segs=8,
            loc=(0, 0, ti*0.10), parent=tail_e, mat_=M_CAMEL_TAN)
    smooth_sphere(f"{name}_tu", r=0.10, segs=10, rings=8, loc=(0, 0, 0.45),
                  parent=tail_e, mat_=M_CAMEL_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "neck": neck_e, "he": head_c_e}

camels = []
camel_pos = [(-15, 30, math.radians(0)), (-7, 33, math.radians(-15)),
              (0, 28, math.radians(20)), (8, 32, math.radians(-30)),
              (15, 30, math.radians(0)), (22, 35, math.radians(-45))]
for i, (cx_c, cy_c, fac) in enumerate(camel_pos):
    c = make_camel(f"cm{i}", (cx_c, cy_c, 0), facing=fac)
    camels.append(c)

# ============ 4 BEDOUINS (signature) ============
def make_bedouin(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long thawb (white robe signature)
    thawb_col = random.choice([M_THAWB_WHITE, M_THAWB_BROWN])
    smooth_cone(f"{name}_tw", r1=0.32, r2=0.50, depth=1.65, segs=14, loc=(0, 0, 0.85),
                parent=base, mat_=thawb_col)
    # Belt
    cyl(f"{name}_be", r=0.36, depth=0.10, segs=14, loc=(0, 0, 0.95),
        parent=base, mat_=M_KEFFIYEH_BLACK)
    # Sandals
    for side in (-1, 1):
        beveled_cube(f"{name}_sa{side}", (0.10, 0.22, 0.04), bevel_offset=0.01,
                     loc=(side*0.13, 0.04, 0.03), parent=base, mat_=M_KEFFIYEH_BLACK)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.32, 0, 1.65), parent=base)
        sh.rotation_euler = (math.radians(-70), 0, math.radians(side*30))
        cyl(f"{name}_ua{side_idx}", r=0.08, depth=0.45, segs=10, loc=(0, 0, -0.22),
            parent=sh, mat_=thawb_col)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=M_SKIN_TAN)
    # Head
    head_b_e = empty(f"{name}_he", (0, 0, 2.0), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_b_e, mat_=M_SKIN_TAN)
    # Beard (signature)
    for bi in range(15):
        ba = random.uniform(-math.pi*0.45, math.pi*0.45)
        beard_len = random.uniform(0.10, 0.25)
        for bsi in range(int(beard_len * 6)):
            cyl(f"{name}_bd{bi}_{bsi}", r=0.020, depth=0.06, segs=6,
                loc=(math.sin(ba)*0.10, -0.10, -0.08 - bsi*0.06),
                parent=head_b_e, mat_=M_HAIR_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_b_e, mat_=M_EYE)
    # KEFFIYEH (signature red checkered pattern)
    keff_e = empty(f"{name}_kf", (0, 0, 0.12), parent=head_b_e)
    keff_col = M_KEFFIYEH_RED if random.random() > 0.3 else M_KEFFIYEH_WHITE
    # Main scarf wrap
    cyl(f"{name}_kf_c", r=0.22, depth=0.20, segs=14, loc=(0, 0, 0),
        parent=keff_e, mat_=keff_col)
    # Drape over shoulders (signature side flaps)
    for side_k in (-1, 1):
        beveled_cube(f"{name}_kf_d{side_k}", (0.06, 0.30, 0.55), bevel_offset=0.04,
                     loc=(side_k*0.18, 0, -0.30), parent=keff_e, mat_=keff_col)
    # Back drape
    beveled_cube(f"{name}_kf_b", (0.40, 0.06, 0.55), bevel_offset=0.04,
                 loc=(0, 0.20, -0.30), parent=keff_e, mat_=keff_col)
    # Checkered pattern
    for chk in range(8):
        cha = (chk / 8.0) * math.pi * 2
        beveled_cube(f"{name}_kf_chk{chk}", (0.05, 0.04, 0.04), bevel_offset=0.005,
                     loc=(math.cos(cha)*0.22, math.sin(cha)*0.20, 0),
                     parent=keff_e, mat_=M_KEFFIYEH_BLACK if chk % 2 else M_KEFFIYEH_WHITE)
    # AGAL (black rope band signature)
    cyl(f"{name}_ag1", r=0.23, depth=0.04, segs=14, loc=(0, 0, 0.08),
        parent=keff_e, mat_=M_AGAL)
    cyl(f"{name}_ag2", r=0.23, depth=0.04, segs=14, loc=(0, 0, 0.03),
        parent=keff_e, mat_=M_AGAL)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_b_e}

bedouins = []
bedouin_pos = [(-12, 18, math.radians(20)), (-2, 22, math.radians(0)),
                (8, 18, math.radians(-15)), (18, 22, math.radians(-30))]
for i, (bx, by, fac) in enumerate(bedouin_pos):
    b = make_bedouin(f"bd{i}", (bx, by, 0), facing=fac)
    bedouins.append(b)

# ============ JORDAN FLAG (signature horizontal stripes + triangle + star) ============
flag_e = empty("flag", (-50, -40, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_KEFFIYEH_BLACK)
# 3 horizontal stripes
beveled_cube("fl_bk", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 11.5),
             parent=flag_e, mat_=M_FLAG_BLACK)
beveled_cube("fl_w", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 10.65),
             parent=flag_e, mat_=M_FLAG_WHITE)
beveled_cube("fl_g", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 9.80),
             parent=flag_e, mat_=M_FLAG_GREEN)
# Red triangle (signature)
for ti in range(8):
    tw = 2 - ti * 0.25
    beveled_cube(f"fl_t{ti}", (tw, 0.06, 0.30), bevel_offset=0.02,
                 loc=(tw/2 + 0.05, 0, 9.80 + ti*0.30), parent=flag_e, mat_=M_FLAG_RED)
# 7-point white star (signature)
star_e = empty("fl_st", (0.5, -0.06, 10.65), parent=flag_e)
for sp in range(7):
    spa = (sp / 7.0) * math.pi * 2 + math.pi/2
    beveled_cube(f"fl_st_p{sp}", (0.03, 0.06, 0.20), bevel_offset=0.005,
                 loc=(math.cos(spa)*0.10, 0, math.sin(spa)*0.10),
                 parent=star_e, mat_=M_FLAG_STAR).rotation_euler = (spa - math.pi/2, 0, 0)
smooth_sphere("fl_stc", r=0.06, loc=(0, 0, 0), parent=star_e, mat_=M_FLAG_STAR)
flag_e["_phase"] = 0

# ============================================================
# 600 RED SAND SWIRLS + 400 WALKING CAMELS (PARTICULES SIGNATURES)
# ============================================================
sand_grains = []
for i in range(600):
    px = random.uniform(-120, 120)
    py = random.uniform(-120, 120)
    pz = random.uniform(1, 18)
    s_col = random.choice(SAND_COLORS)
    sg = smooth_sphere(f"sg{i}", r=random.uniform(0.10, 0.22), segs=8, rings=6,
                       loc=(px, py, pz), mat_=s_col, scale=(1.2, 1.0, 0.5))
    sg["_phase"] = random.uniform(0, math.pi*2)
    sg["_base_x"] = px; sg["_base_y"] = py; sg["_base_z"] = pz
    sg["_radius"] = random.uniform(2, 5)
    sg["_speed"] = random.uniform(1.0, 2.5)
    sg["_lift"] = random.uniform(0.5, 1.5)
    sand_grains.append(sg)

# 400 walking camel particles (caravan signature)
mini_camels = []
for i in range(400):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = 0.6
    mc_e = empty(f"mc{i}", (px, py, pz))
    # Body
    smooth_sphere(f"mc{i}_bo", r=0.25, segs=10, rings=8, loc=(0, 0, 0),
                  parent=mc_e, mat_=M_CAMEL_TAN, scale=(1.5, 0.85, 0.85))
    # Hump
    smooth_sphere(f"mc{i}_hp", r=0.18, segs=10, rings=8, loc=(0, 0, 0.15),
                  parent=mc_e, mat_=M_CAMEL_DARK, scale=(0.85, 0.85, 1.0))
    # Neck
    cyl(f"mc{i}_n", r=0.06, depth=0.30, segs=8, loc=(0.25, 0, 0.20),
        parent=mc_e, mat_=M_CAMEL_TAN).rotation_euler = (0, math.radians(50), 0)
    # Head
    smooth_sphere(f"mc{i}_h", r=0.10, segs=10, rings=8, loc=(0.40, 0, 0.30),
                  parent=mc_e, mat_=M_CAMEL_TAN, scale=(1.3, 0.85, 0.85))
    # Legs
    for side in (-1, 1):
        for fr in (-1, 1):
            cyl(f"mc{i}_l{side}_{fr}", r=0.04, depth=0.40, segs=6,
                loc=(fr*0.20, side*0.15, -0.20), parent=mc_e, mat_=M_CAMEL_TAN)
    mc_e["_phase"] = random.uniform(0, math.pi*2)
    mc_e["_base_x"] = px; mc_e["_base_y"] = py
    mc_e["_speed"] = random.uniform(0.3, 0.7)
    mc_e["_direction"] = random.uniform(0, math.pi*2)
    mini_camels.append(mc_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Camels sway/walk
for c in camels:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        c["root"].location.z = abs(math.sin(t * 1.5 + phase)) * 0.10
        c["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3), 0,
                                     c["root"].rotation_euler.z)
        c["root"].keyframe_insert("location", frame=f)
        c["root"].keyframe_insert("rotation_euler", frame=f)
        c["neck"].rotation_euler = (0, math.radians(-35) + math.sin(t * 1.5 + phase) * math.radians(10), 0)
        c["neck"].keyframe_insert("rotation_euler", frame=f)
        c["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(8), 0,
                                   math.cos(t * 0.8 + phase) * math.radians(15))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Bedouins sway
for b in bedouins:
    phase = b["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        b["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     b["root"].rotation_euler.z)
        b["root"].keyframe_insert("rotation_euler", frame=f)
        b["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(3), 0,
                                   math.cos(t * 0.8 + phase) * math.radians(15))
        b["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 sand grains swirl
for sg in sand_grains:
    phase = sg["_phase"]; speed = sg["_speed"]; radius = sg["_radius"]; lift = sg["_lift"]
    bx, by, bz = sg["_base_x"], sg["_base_y"], sg["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * radius
        y = by + math.sin(t * speed + phase) * radius
        z = bz + math.sin(t * speed * 1.5 + phase) * lift + (t * 0.4) % 8
        sg.location = (x, y, z)
        sg.rotation_euler = (t * 2.0 + phase, math.sin(t * 1.5 + phase) * math.radians(30), t * 1.5 + phase)
        sg.keyframe_insert("location", frame=f)
        sg.keyframe_insert("rotation_euler", frame=f)

# 400 mini camels walk in caravan patterns
for mc in mini_camels:
    phase = mc["_phase"]; speed = mc["_speed"]
    bx, by = mc["_base_x"], mc["_base_y"]
    direction = mc["_direction"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Linear walk in their direction
        x = bx + math.cos(direction) * t * speed * 3
        y = by + math.sin(direction) * t * speed * 3
        z = 0.6 + abs(math.sin(t * 4.0 + phase)) * 0.08
        mc.location = (x, y, z)
        mc.rotation_euler = (math.sin(t * 4.0 + phase) * math.radians(3), 0, direction)
        mc.keyframe_insert("location", frame=f)
        mc.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_petra_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_petra_jordan_treasury_canyon] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Petra Jordan: Al-Khazneh Treasury (signature 2-tier Nabataean facade with 6 columns lower level + entablature + triangular pediment + central tholos with 8 circular columns + cone roof + urn on top + 2 wing half-pediments + 4 niche figures) + Ad-Deir Monastery distant peak + Siq canyon with 40 rock walls (red/pink/orange + horizontal striations) + 6 dromedary camels (signature single hump + saddle red + gold trim + tassels + long neck S-curve + long eyelashes + 4 legs with wide pad feet + tail with tuft) + 4 Bedouins (thawb robes + checkered keffiyeh red/white + agal black rope + beards) + Jordan flag (black/white/green stripes + red triangle + 7-point star signature) + 600 red sand swirls + 400 walking caravan camel particles")
print("🐪 FIXES: 1 red sand desert ground + 600 sand swirls (3 colors) + 400 camel caravan signature 🐪")
