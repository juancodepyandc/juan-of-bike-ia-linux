"""
proc_canadian_wilderness_aurora_lake.py — 264e procédural AuroraIA (129e qualité)
Canadian wilderness: 8 snow mountains + glacier + frozen lake + grizzly + moose with antlers + 6 lumberjacks + 4 beavers + log cabin + 8 snowy firs + aurora borealis + 600 aurora + 400 snow
FIXES : 1 ground + 600 aurora waves + 400 snowflakes (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB264)

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

# Night sky
M_SKY = mat("sky", (0.05, 0.06, 0.18, 1.0), 0.0, 0.7, emission=(0.06,0.08,0.20), emission_strength=0.7)
M_STAR = mat("star", (1.0, 0.95, 0.78, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.78), emission_strength=10.0)
M_MOON = mat("moon", (0.92, 0.92, 0.85, 1.0), 0.0, 0.20, emission=(0.88,0.88,0.82), emission_strength=4.0)

# Aurora signature
M_AURORA_GREEN = mat("au_g", (0.18, 0.95, 0.45, 1.0), 0.0, 0.10, emission=(0.18,0.95,0.45), emission_strength=6.0, alpha=0.55)
M_AURORA_PURPLE = mat("au_p", (0.55, 0.20, 0.85, 1.0), 0.0, 0.10, emission=(0.55,0.20,0.85), emission_strength=5.5, alpha=0.55)
M_AURORA_PINK = mat("au_pk", (0.95, 0.40, 0.85, 1.0), 0.0, 0.10, emission=(0.92,0.40,0.85), emission_strength=5.0, alpha=0.55)
AURORA_COLORS = [M_AURORA_GREEN, M_AURORA_PURPLE, M_AURORA_PINK]

# Snow ground
M_SNOW = mat("snow", (0.95, 0.96, 0.98, 1.0), 0.0, 0.30, emission=(0.92,0.94,0.96), emission_strength=1.0)
M_SNOW_BRIGHT = mat("snow_b", (0.98, 0.98, 1.0, 1.0), 0.0, 0.25, emission=(0.95,0.95,0.98), emission_strength=1.2)

# Frozen lake
M_ICE = mat("ice", (0.65, 0.85, 0.92, 1.0), 0.4, 0.20, emission=(0.65,0.82,0.92), emission_strength=1.5, alpha=0.70)
M_ICE_DEEP = mat("ice_d", (0.45, 0.65, 0.78, 1.0), 0.4, 0.25, alpha=0.85)
M_ICE_CRACK = mat("ice_c", (0.30, 0.45, 0.55, 1.0), 0.3, 0.40)

# Mountain
M_MT_ROCK = mat("mt_r", (0.42, 0.38, 0.40, 1.0), 0.0, 0.85, emission=(0.40,0.36,0.38), emission_strength=0.3)
M_MT_DARK = mat("mt_d", (0.22, 0.22, 0.25, 1.0), 0.0, 0.85)

# Glacier
M_GLACIER = mat("gl", (0.78, 0.92, 0.95, 1.0), 0.3, 0.30, emission=(0.75,0.90,0.95), emission_strength=1.5, alpha=0.85)

# Cabin
M_LOG = mat("log", (0.55, 0.32, 0.15, 1.0), 0.0, 0.75, emission=(0.50,0.30,0.15), emission_strength=0.4)
M_LOG_DARK = mat("log_d", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)
M_ROOF_RED_C = mat("rf_r", (0.55, 0.20, 0.18, 1.0), 0.0, 0.70, emission=(0.52,0.20,0.18), emission_strength=0.4)
M_WINDOW_GLOW = mat("win", (1.0, 0.85, 0.45, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.45), emission_strength=5.0)
M_CHIMNEY = mat("ch", (0.42, 0.40, 0.38, 1.0), 0.0, 0.85)
M_SMOKE = mat("smk", (0.78, 0.78, 0.82, 1.0), 0.0, 0.40, emission=(0.75,0.75,0.82), emission_strength=1.0, alpha=0.50)

# Fire campfire
M_FIRE_OUTER = mat("fo", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=18.0)
M_FIRE_CORE = mat("fc", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=22.0)
M_ROCK_FIRE = mat("rf", (0.40, 0.38, 0.35, 1.0), 0.0, 0.85)

# Trees
M_FIR_DARK = mat("fd", (0.10, 0.30, 0.15, 1.0), 0.0, 0.75, emission=(0.10,0.30,0.15), emission_strength=0.4)
M_FIR_BRIGHT = mat("fb", (0.18, 0.45, 0.20, 1.0), 0.0, 0.70)
M_TRUNK_PINE = mat("tp", (0.30, 0.18, 0.08, 1.0), 0.0, 0.85)

# Bear grizzly
M_BEAR_BROWN = mat("bb", (0.42, 0.25, 0.12, 1.0), 0.0, 0.85, emission=(0.40,0.25,0.12), emission_strength=0.3)
M_BEAR_DARK = mat("bb_d", (0.22, 0.12, 0.06, 1.0), 0.0, 0.85)
M_BEAR_NOSE = mat("bn", (0.18, 0.10, 0.06, 1.0), 0.0, 0.65)

# Moose
M_MOOSE_BROWN = mat("mb", (0.32, 0.18, 0.10, 1.0), 0.0, 0.85, emission=(0.30,0.18,0.10), emission_strength=0.3)
M_MOOSE_DARK = mat("mb_d", (0.18, 0.10, 0.05, 1.0), 0.0, 0.85)
M_ANTLER = mat("ant", (0.62, 0.45, 0.20, 1.0), 0.0, 0.55, emission=(0.58,0.42,0.20), emission_strength=0.4)

# Beaver
M_BEAVER = mat("bv", (0.55, 0.32, 0.18, 1.0), 0.0, 0.80, emission=(0.50,0.30,0.18), emission_strength=0.3)
M_BEAVER_TAIL = mat("bv_t", (0.32, 0.18, 0.10, 1.0), 0.0, 0.85)

# Skin
M_SKIN = mat("sk", (0.92, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.62), emission_strength=0.4)
M_CHEEK = mat("ck", (0.95, 0.55, 0.55, 1.0), 0.0, 0.55, emission=(0.92,0.55,0.55), emission_strength=0.6)

# Lumberjack
M_FLANNEL_RED = mat("fr", (0.78, 0.20, 0.20, 1.0), 0.0, 0.75, emission=(0.72,0.20,0.20), emission_strength=0.5)
M_FLANNEL_DARK = mat("fr_d", (0.42, 0.10, 0.10, 1.0), 0.0, 0.85)
M_JEANS = mat("jn", (0.18, 0.32, 0.55, 1.0), 0.0, 0.80)
M_BOOTS = mat("bt", (0.32, 0.18, 0.08, 1.0), 0.0, 0.80)
M_HAT_TUQUE = mat("tq", (0.85, 0.20, 0.20, 1.0), 0.0, 0.75, emission=(0.80,0.20,0.20), emission_strength=0.5)
M_HAIR_BROWN = mat("hb", (0.32, 0.18, 0.10, 1.0), 0.0, 0.60)
M_BEARD_BROWN = mat("bd", (0.42, 0.28, 0.15, 1.0), 0.0, 0.65)
M_BEARD_RED = mat("bd_r", (0.78, 0.32, 0.10, 1.0), 0.0, 0.60)

# Axe
M_AXE_HEAD = mat("ah", (0.85, 0.85, 0.85, 1.0), 0.9, 0.20, emission=(0.80,0.80,0.80), emission_strength=0.5)
M_AXE_HANDLE = mat("ah_h", (0.42, 0.25, 0.12, 1.0), 0.0, 0.70)

# Eye
M_EYE_DARK = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Maple leaf
M_MAPLE_RED = mat("mr_r", (0.95, 0.18, 0.15, 1.0), 0.0, 0.45, emission=(0.92,0.18,0.15), emission_strength=2.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.55)

# ============ SKY ============
sky = smooth_sphere("sky", r=300, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Moon
moon = smooth_sphere("moon", r=4, segs=24, rings=18, loc=(-50, 80, 70), mat_=M_MOON)
# Stars
for si in range(200):
    sa = random.uniform(0, math.pi*2); sr = random.uniform(80, 220)
    sh = random.uniform(30, 110)
    smooth_sphere(f"star{si}", r=random.uniform(0.10, 0.30), segs=8, rings=6,
                  loc=(sr*math.cos(sa), sr*math.sin(sa), sh), mat_=M_STAR)

# ============ AURORA BANDS signature ============
for au in range(6):
    au_y_pos = -40 + au * 18
    au_h = 35 + random.uniform(-5, 5)
    band_e = empty(f"aurora{au}", (0, au_y_pos, au_h))
    aurora_col = AURORA_COLORS[au % len(AURORA_COLORS)]
    aurora_col_2 = AURORA_COLORS[(au+1) % len(AURORA_COLORS)]
    for si in range(60):
        sx_off = -60 + si * 2
        sz_off = math.sin(si * 0.25 + au) * 4
        col_use = aurora_col if si % 3 != 0 else aurora_col_2
        for hi in range(7):
            hz = hi * 1.0
            beveled_cube(f"au{au}_{si}_{hi}", (1.8, 0.4, 0.8), bevel_offset=0.05,
                         loc=(sx_off, sz_off, hz - 3),
                         parent=band_e, mat_=col_use)
    band_e["_phase"] = random.uniform(0, math.pi*2)

# ============ ONE clean snow ground ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_SNOW)
# Snow drifts
for i in range(120):
    a = random.uniform(0, math.pi*2); rad = random.uniform(2, 80)
    smooth_sphere(f"sd{i}", r=random.uniform(0.4, 1.0), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_SNOW_BRIGHT, scale=(1.5, 1.4, 0.22))

# ============ 8 SNOW MOUNTAINS ============
for mi in range(8):
    ma = (mi / 8.0) * math.pi * 2 + math.pi/8
    mxr = 70 + random.uniform(-10, 10)
    mx_p = math.cos(ma) * mxr
    my_p = math.sin(ma) * mxr
    if my_p < -40: continue
    height = random.uniform(25, 40)
    m_e = empty(f"mt{mi}", (mx_p, my_p, 0))
    for li in range(10):
        lz = li * (height / 10.0)
        lr = (1.0 - li/10.0) * random.uniform(15, 22)
        cyl(f"mt{mi}_{li}", r=lr, depth=height/10.0, segs=8,
            loc=(0, 0, lz + height/20.0), parent=m_e,
            mat_=M_MT_ROCK if li < 4 else M_SNOW)
    smooth_cone(f"mt{mi}_p", r1=2, r2=0.2, depth=4, segs=8, loc=(0, 0, height),
                parent=m_e, mat_=M_SNOW)

# ============ GLACIER (signature blue ice) ============
glacier_e = empty("glacier", loc=(50, 50, 0))
for li in range(8):
    lz = li * 1.5
    lr = 8 - li * 0.5
    smooth_sphere(f"gl{li}", r=lr, segs=14, rings=10, loc=(0, 0, lz),
                  parent=glacier_e, mat_=M_GLACIER, scale=(1.5, 1.3, 0.8))
# Glacier cracks
for ci in range(10):
    ca = (ci / 10.0) * math.pi * 2
    beveled_cube(f"gl_c{ci}", (0.3, 4, 0.10), bevel_offset=0.04,
                 loc=(math.cos(ca)*5, math.sin(ca)*5, 1), parent=glacier_e,
                 mat_=M_ICE_CRACK)

# ============ FROZEN LAKE (signature) ============
lake_e = empty("lake", loc=(0, -30, 0))
beveled_cube("l_main", (30, 25, 0.15), bevel_offset=0.10, loc=(0, 0, 0.10),
             parent=lake_e, mat_=M_ICE)
beveled_cube("l_d", (28, 23, 0.10), bevel_offset=0.06, loc=(0, 0, 0.15),
             parent=lake_e, mat_=M_ICE_DEEP)
# Ice cracks signature
for ci in range(15):
    cx_c = random.uniform(-13, 13); cy_c = random.uniform(-10, 10)
    cl = random.uniform(2, 6)
    ca = random.uniform(0, math.pi*2)
    beveled_cube(f"l_cr{ci}", (cl, 0.10, 0.04), bevel_offset=0.02,
                 loc=(cx_c, cy_c, 0.20),
                 parent=lake_e, mat_=M_ICE_CRACK).rotation_euler = (0, 0, ca)

# ============ LOG CABIN (signature) ============
cabin_e = empty("cabin", loc=(-15, -10, 0))
# Foundation
beveled_cube("c_f", (8, 6, 0.5), bevel_offset=0.10, loc=(0, 0, 0.25),
             parent=cabin_e, mat_=M_MT_DARK)
# Log walls (signature stacked logs)
for li in range(8):
    lz = 0.5 + li * 0.4
    # Front+back walls
    for y_p in (-1, 1):
        cyl(f"c_lw_y{li}_{y_p}", r=0.20, depth=8, segs=12,
            loc=(0, y_p*3, lz), parent=cabin_e,
            mat_=M_LOG if li % 2 == 0 else M_LOG_DARK).rotation_euler = (0, math.radians(90), 0)
    # Side walls
    for x_p in (-1, 1):
        cyl(f"c_lw_x{li}_{x_p}", r=0.20, depth=6, segs=12,
            loc=(x_p*4, 0, lz), parent=cabin_e,
            mat_=M_LOG if li % 2 == 0 else M_LOG_DARK).rotation_euler = (math.radians(90), 0, 0)
# Door
beveled_cube("c_door", (1.0, 0.20, 2.0), bevel_offset=0.06, loc=(0, -3, 1.5),
             parent=cabin_e, mat_=M_LOG_DARK)
# Window LIT signature
beveled_cube("c_w", (1.0, 0.10, 1.0), bevel_offset=0.06, loc=(-2, -3, 2.5),
             parent=cabin_e, mat_=M_WINDOW_GLOW)
beveled_cube("c_w2", (1.0, 0.10, 1.0), bevel_offset=0.06, loc=(2, -3, 2.5),
             parent=cabin_e, mat_=M_WINDOW_GLOW)
# Window frames
beveled_cube("c_wf", (1.1, 0.12, 1.1), bevel_offset=0.04, loc=(-2, -2.95, 2.5),
             parent=cabin_e, mat_=M_LOG_DARK)
beveled_cube("c_wf2", (1.1, 0.12, 1.1), bevel_offset=0.04, loc=(2, -2.95, 2.5),
             parent=cabin_e, mat_=M_LOG_DARK)
# Sloped red roof
for ri in range(6):
    rw = 8.5 - ri * 0.10
    rl = 6 - ri * 0.10
    beveled_cube(f"c_r{ri}", (rw, rl, 0.30), bevel_offset=0.06,
                 loc=(0, 0, 4 + ri*0.25), parent=cabin_e, mat_=M_ROOF_RED_C)
# Snow on roof
for sri in range(5):
    smooth_sphere(f"c_rs{sri}", r=0.3, loc=(-3 + sri*1.5, 0, 5.5),
                  parent=cabin_e, mat_=M_SNOW_BRIGHT, scale=(1.5, 1.3, 0.4))
# Chimney
beveled_cube("c_chim", (0.5, 0.5, 1.5), bevel_offset=0.06, loc=(2.5, 1.5, 5.5),
             parent=cabin_e, mat_=M_CHIMNEY)
# Smoke
for si in range(5):
    smooth_sphere(f"c_sm{si}", r=0.30 - si*0.02, loc=(2.5, 1.5, 6.5 + si*0.6),
                  parent=cabin_e, mat_=M_SMOKE)

# ============ CAMPFIRE outside cabin ============
fire_e = empty("fire", loc=(-15, -5, 0))
# Stone ring
for si in range(8):
    sa = (si / 8.0) * math.pi * 2
    smooth_sphere(f"fs{si}", r=0.20, loc=(math.cos(sa)*0.6, math.sin(sa)*0.6, 0.15),
                  parent=fire_e, mat_=M_ROCK_FIRE)
# Logs
for li in range(4):
    la = (li / 4.0) * math.pi
    cyl(f"fl{li}", r=0.08, depth=0.7, segs=10, loc=(0, 0, 0.20),
        parent=fire_e, mat_=M_LOG).rotation_euler = (0, math.radians(90), la*math.pi/2)
# Flames
flame_e = empty("flame", (0, 0, 0.35), parent=fire_e)
smooth_cone("fo_o", r1=0.30, r2=0.05, depth=1.0, segs=14, loc=(0, 0, 0.5),
            parent=flame_e, mat_=M_FIRE_OUTER)
smooth_cone("fo_c", r1=0.20, r2=0.02, depth=0.8, segs=14, loc=(0, 0, 0.4),
            parent=flame_e, mat_=M_FIRE_CORE)

# ============ 8 SNOWY FIR TREES ============
def make_snowy_fir(name, loc, scale=1.0):
    base = empty(name, loc)
    cyl(f"{name}_t", r=0.30, depth=2, segs=12, loc=(0, 0, 1), parent=base, mat_=M_TRUNK_PINE)
    for li in range(6):
        lz = 1.5 + li * 1.5
        lr = 2.5 - li * 0.35
        smooth_cone(f"{name}_l{li}", r1=lr, r2=0.10, depth=2, segs=14, loc=(0, 0, lz),
                    parent=base, mat_=M_FIR_DARK if li % 2 == 0 else M_FIR_BRIGHT)
        # Snow caps
        smooth_cone(f"{name}_sn{li}", r1=lr*0.7, r2=0.10, depth=0.5, segs=14, loc=(0, 0, lz + 0.7),
                    parent=base, mat_=M_SNOW_BRIGHT)
    return base

firs = []
for ti in range(8):
    ta = (ti / 8.0) * math.pi * 2 + math.pi/8
    tx = math.cos(ta) * 35
    ty = math.sin(ta) * 35
    if -15 < ty < -45: continue
    f_obj = make_snowy_fir(f"fir{ti}", (tx, ty, 0), scale=1.0)
    firs.append(f_obj)

# ============ GRIZZLY BEAR (signature) ============
bear_e = empty("bear", loc=(20, 0, 0))
bear_e.rotation_euler = (0, 0, math.radians(120))
# Body
smooth_sphere("br_b", r=0.9, segs=20, rings=14, loc=(0, 0, 1.2),
              parent=bear_e, mat_=M_BEAR_BROWN, scale=(1.7, 1.0, 1.0))
# Fur tufts signature
for fi in range(50):
    fa = random.uniform(0, math.pi*2); fe = random.uniform(0, math.pi)
    fx = math.sin(fe) * math.cos(fa) * 1.0
    fy = math.sin(fe) * math.sin(fa) * 0.6
    fz = math.cos(fe) * 0.7 + 1.2
    smooth_sphere(f"br_f{fi}", r=0.12, loc=(fx, fy, fz),
                  parent=bear_e, mat_=M_BEAR_BROWN if fi % 2 == 0 else M_BEAR_DARK)
# 4 legs
for x in (-1, 1):
    for y in (-1, 1):
        cyl(f"br_l{x}{y}", r=0.18, depth=1.2, segs=12,
            loc=(x*0.55, y*0.35, 0.6), parent=bear_e, mat_=M_BEAR_BROWN)
# Head
head_b_e = empty("br_he", (1.4, 0, 1.3), parent=bear_e)
smooth_sphere("br_h", r=0.50, segs=20, rings=14, loc=(0, 0, 0),
              parent=head_b_e, mat_=M_BEAR_BROWN, scale=(1.3, 0.9, 1))
# Snout
smooth_sphere("br_sn", r=0.30, loc=(0.30, 0, -0.10),
              parent=head_b_e, mat_=M_BEAR_BROWN, scale=(1.2, 0.85, 0.7))
# Nose
smooth_sphere("br_n", r=0.10, loc=(0.50, 0, -0.05), parent=head_b_e, mat_=M_BEAR_NOSE)
# Ears
for side in (-1, 1):
    smooth_sphere(f"br_e{side}", r=0.15, loc=(-0.10, side*0.30, 0.30),
                  parent=head_b_e, mat_=M_BEAR_BROWN, scale=(0.6, 1, 1))
# Eyes
for side in (-1, 1):
    smooth_sphere(f"br_ey{side}", r=0.05, loc=(0.20, side*0.20, 0.10),
                  parent=head_b_e, mat_=M_EYE_DARK)

# ============ MOOSE with antlers (signature) ============
moose_e = empty("moose", loc=(-25, 25, 0))
moose_e.rotation_euler = (0, 0, math.radians(-45))
# Body
smooth_sphere("mo_b", r=0.85, segs=20, rings=14, loc=(0, 0, 2),
              parent=moose_e, mat_=M_MOOSE_BROWN, scale=(1.8, 1.0, 1.1))
# 4 long legs
for x in (-1, 1):
    for y in (-1, 1):
        cyl(f"mo_l{x}{y}", r=0.10, depth=2, segs=12,
            loc=(x*0.55, y*0.35, 1), parent=moose_e, mat_=M_MOOSE_DARK)
# Long neck
neck_m_e = empty("mo_n", (1.0, 0, 2.5), parent=moose_e)
neck_m_e.rotation_euler = (0, math.radians(-15), 0)
cyl("mo_nb", r=0.25, depth=1.0, segs=14, loc=(0, 0, 0.5), parent=neck_m_e, mat_=M_MOOSE_BROWN)
# Head (signature long)
head_m_e = empty("mo_he", (0, 0, 1.1), parent=neck_m_e)
smooth_sphere("mo_h", r=0.35, segs=18, rings=14, loc=(0.20, 0, 0),
              parent=head_m_e, mat_=M_MOOSE_BROWN, scale=(2, 0.85, 0.9))
# Bulbous nose (signature)
smooth_sphere("mo_no", r=0.18, loc=(0.65, 0, -0.10),
              parent=head_m_e, mat_=M_MOOSE_DARK)
# Dewlap (signature throat skin)
smooth_sphere("mo_dl", r=0.15, loc=(0, 0, -0.30),
              parent=head_m_e, mat_=M_MOOSE_DARK, scale=(0.5, 1, 1.5))
# Eyes
for side in (-1, 1):
    smooth_sphere(f"mo_ey{side}", r=0.04, loc=(0.20, side*0.18, 0.10),
                  parent=head_m_e, mat_=M_EYE_DARK)
# Ears
for side in (-1, 1):
    smooth_sphere(f"mo_er{side}", r=0.10, loc=(-0.10, side*0.20, 0.20),
                  parent=head_m_e, mat_=M_MOOSE_BROWN, scale=(0.5, 1.5, 1.3))
# MASSIVE PALMATE ANTLERS signature
for side in (-1, 1):
    ant_e = empty(f"mo_a{side}_e", (-0.10, side*0.15, 0.40), parent=head_m_e)
    ant_e.rotation_euler = (0, 0, math.radians(side*30))
    # Beam
    cyl(f"mo_a{side}_m", r=0.06, depth=0.50, segs=10, loc=(0, side*0.20, 0.20),
        parent=ant_e, mat_=M_ANTLER)
    # Palm signature flat broad
    beveled_cube(f"mo_a{side}_palm", (0.60, 0.05, 0.50), bevel_offset=0.10,
                 loc=(0, side*0.50, 0.60), parent=ant_e, mat_=M_ANTLER)
    # Tines on palm
    for ti in range(5):
        smooth_cone(f"mo_a{side}_t{ti}", r1=0.04, r2=0.005, depth=0.20, segs=6,
                    loc=((ti-2)*0.12, side*0.65, 0.55),
                    parent=ant_e, mat_=M_ANTLER).rotation_euler = (math.radians(side*-30), 0, 0)

# ============ 4 BEAVERS (signature flat tails) ============
def make_beaver(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_b", r=0.30, segs=18, rings=12, loc=(0, 0, 0.30),
                  parent=base, mat_=M_BEAVER, scale=(1.5, 1, 0.9))
    # Head
    head_bv_e = empty(f"{name}_he", (0.4, 0, 0.5), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=14, rings=10, loc=(0, 0, 0),
                  parent=head_bv_e, mat_=M_BEAVER, scale=(1.3, 0.9, 1))
    # Snout
    smooth_sphere(f"{name}_sn", r=0.12, loc=(0.13, 0, -0.05), parent=head_bv_e, mat_=M_BEAVER,
                  scale=(1.2, 0.7, 0.7))
    # 2 BIG INCISORS (signature orange)
    for side in (-1, 1):
        beveled_cube(f"{name}_t{side}", (0.04, 0.03, 0.08), bevel_offset=0.005,
                     loc=(side*0.025, 0.20, -0.10), parent=head_bv_e, mat_=M_MAPLE_RED)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(0.10, side*0.10, 0.05),
                      parent=head_bv_e, mat_=M_EYE_DARK)
    # Round ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.06, loc=(-0.05, side*0.13, 0.10),
                      parent=head_bv_e, mat_=M_BEAVER)
    # FLAT PADDLE TAIL signature
    beveled_cube(f"{name}_tl", (0.35, 0.5, 0.05), bevel_offset=0.06, loc=(-0.45, 0, 0.30),
                 parent=base, mat_=M_BEAVER_TAIL)
    # Cross-hatch pattern on tail
    for ci in range(5):
        beveled_cube(f"{name}_tlc{ci}", (0.40, 0.06, 0.01), bevel_offset=0.005,
                     loc=(-0.45, -0.20 + ci*0.10, 0.33), parent=base, mat_=M_BEARD_BROWN)
    # 4 small legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}{y}", r=0.04, depth=0.15, segs=8,
                loc=(x*0.20, y*0.15, 0.10), parent=base, mat_=M_BEAVER)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base}

beavers = []
beaver_pos = [(-5, -25, math.radians(0)), (5, -25, math.radians(180)),
               (0, -30, math.radians(60)), (-3, -35, math.radians(-60))]
for i, (bx, by, fac) in enumerate(beaver_pos):
    b = make_beaver(f"beaver{i}", (bx, by, 0.4), scale=1.0, facing=fac)
    beavers.append(b)

# Beaver dam logs
for di in range(6):
    cyl(f"dam{di}", r=0.12, depth=2, segs=10, loc=(random.uniform(-3, 3), -28 + di*0.3, 0.3),
        mat_=M_LOG).rotation_euler = (0, math.radians(90), random.uniform(0, math.pi))

# ============ 6 LUMBERJACKS (signature) ============
def make_lumberjack(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body - red flannel shirt (signature)
    smooth_cone(f"{name}_sh", r1=0.32, r2=0.34, depth=0.7, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=M_FLANNEL_RED)
    # Plaid pattern lines (signature)
    for pi in range(6):
        cyl(f"{name}_pl{pi}", r=0.34, depth=0.06, segs=14,
            loc=(0, 0, 1.05 + pi*0.10), parent=base, mat_=M_FLANNEL_DARK)
    # Vertical plaid
    for pi in range(4):
        pa = (pi / 4.0) * math.pi * 2 + math.pi/4
        beveled_cube(f"{name}_pv{pi}", (0.04, 0.04, 0.6), bevel_offset=0.005,
                     loc=(math.cos(pa)*0.33, math.sin(pa)*0.33, 1.30),
                     parent=base, mat_=M_FLANNEL_DARK)
    # Suspenders
    for side in (-1, 1):
        beveled_cube(f"{name}_su{side}", (0.06, 0.04, 0.50), bevel_offset=0.01,
                     loc=(side*0.20, -0.30, 1.35), parent=base, mat_=M_LOG_DARK)
    # Jeans
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.11, depth=1.0, segs=10,
            loc=(side*0.13, 0, 0.5), parent=base, mat_=M_JEANS)
    # Boots
    for side in (-1, 1):
        beveled_cube(f"{name}_bt{side}", (0.13, 0.25, 0.15), bevel_offset=0.04,
                     loc=(side*0.13, 0.05, 0), parent=base, mat_=M_BOOTS)
    # Arms holding axe
    sh_r = empty(f"{name}_shr", (0.30, -0.05, 1.65), parent=base)
    sh_r.rotation_euler = (math.radians(-50), 0, math.radians(-15))
    cyl(f"{name}_ua_r", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=M_FLANNEL_RED)
    cyl(f"{name}_fa_r", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_SKIN)
    sh_l = empty(f"{name}_shl", (-0.30, -0.05, 1.65), parent=base)
    sh_l.rotation_euler = (math.radians(-70), 0, math.radians(15))
    cyl(f"{name}_ua_l", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=M_FLANNEL_RED)
    cyl(f"{name}_fa_l", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_SKIN)
    # AXE signature
    axe_e = empty(f"{name}_axe", (0, 0, -0.85), parent=sh_l)
    # Handle
    cyl(f"{name}_ax_h", r=0.04, depth=1.2, segs=10, loc=(0, 0, -0.50),
        parent=axe_e, mat_=M_AXE_HANDLE)
    # Head signature (large blade)
    beveled_cube(f"{name}_ax_b", (0.05, 0.25, 0.30), bevel_offset=0.04,
                 loc=(0, 0, 0.15), parent=axe_e, mat_=M_AXE_HEAD)
    # Head
    head_lj_e = empty(f"{name}_he", (0, 0, 2.0), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_lj_e, mat_=M_SKIN)
    # Big beard (signature)
    for bi in range(12):
        ba = (bi / 12.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_bd{bi}", r=0.05,
                      loc=(math.sin(ba)*0.13, -0.16, -0.10 - (bi%3)*0.08),
                      parent=head_lj_e, mat_=random.choice([M_BEARD_BROWN, M_BEARD_RED]))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_lj_e, mat_=M_EYE_DARK)
    # Pink cheeks (cold)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ch{side}", r=0.06, loc=(side*0.13, -0.16, -0.05),
                      parent=head_lj_e, mat_=M_CHEEK)
    # TUQUE (signature Canadian knit hat with pom)
    tq_e = empty(f"{name}_tq", (0, 0, 0.20), parent=head_lj_e)
    cyl(f"{name}_tq_b", r=0.20, depth=0.10, segs=14, loc=(0, 0, 0),
        parent=tq_e, mat_=M_HAT_TUQUE)
    smooth_cone(f"{name}_tq_c", r1=0.18, r2=0.06, depth=0.25, segs=14, loc=(0, 0, 0.18),
                parent=tq_e, mat_=M_HAT_TUQUE)
    # Pom signature
    smooth_sphere(f"{name}_tq_pm", r=0.08, loc=(0, 0, 0.35),
                  parent=tq_e, mat_=M_SNOW_BRIGHT)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_lj_e}

lumberjacks = []
lj_pos = [(-3, 5, math.radians(45)), (3, 5, math.radians(-45)),
           (-12, 0, math.radians(30)), (12, 0, math.radians(-30)),
           (-8, 15, math.radians(60)), (8, 15, math.radians(-60))]
for i, (lx, ly, fac) in enumerate(lj_pos):
    l = make_lumberjack(f"lj{i}", (lx, ly, 0), scale=1.0, facing=fac)
    lumberjacks.append(l)

# Logs cut
for li in range(6):
    cyl(f"log{li}", r=0.15, depth=1.5, segs=12, loc=(random.uniform(-15, 15),
                                                         random.uniform(0, 20),
                                                         0.20),
        mat_=M_LOG).rotation_euler = (0, math.radians(90), random.uniform(0, math.pi))

# Canada flag
flag_e = empty("flag", loc=(15, 5, 0))
cyl("fl_p", r=0.05, depth=6, segs=10, loc=(0, 0, 3), parent=flag_e, mat_=M_LOG_DARK)
beveled_cube("fl_w", (2.4, 0.05, 1.5), bevel_offset=0.04, loc=(1.2, 0, 5.5), parent=flag_e, mat_=M_FLAG_WHITE)
# Red sides
beveled_cube("fl_r1", (0.8, 0.06, 1.55), bevel_offset=0.04, loc=(0.4, -0.01, 5.5), parent=flag_e, mat_=M_MAPLE_RED)
beveled_cube("fl_r2", (0.8, 0.06, 1.55), bevel_offset=0.04, loc=(2.0, -0.01, 5.5), parent=flag_e, mat_=M_MAPLE_RED)
# Maple leaf signature
smooth_sphere("fl_ml", r=0.30, loc=(1.2, -0.06, 5.5), parent=flag_e, mat_=M_MAPLE_RED, scale=(1, 0.2, 1))

# ============================================================
# ⭐ 600 AURORA + 400 SNOWFLAKES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
aurora_particles = []
for i in range(600):
    px = random.uniform(-80, 80)
    py = random.uniform(-60, 60)
    pz = random.uniform(30, 65)
    aur_col = random.choice(AURORA_COLORS)
    a = smooth_sphere(f"ap{i}", r=random.uniform(0.20, 0.40), segs=10, rings=6,
                      loc=(px, py, pz), mat_=aur_col, scale=(2, 0.8, 0.5))
    a["_phase"] = random.uniform(0, math.pi*2)
    a["_base_x"] = px; a["_base_y"] = py; a["_base_z"] = pz
    a["_amp_x"] = random.uniform(2, 5)
    a["_amp_y"] = random.uniform(1, 2)
    a["_amp_z"] = random.uniform(0.5, 1.5)
    a["_speed"] = random.uniform(0.3, 0.8)
    aurora_particles.append(a)

# 400 snowflakes
snowflakes = []
for i in range(400):
    px = random.uniform(-70, 70); py = random.uniform(-70, 70)
    pz = random.uniform(1, 25)
    s = smooth_sphere(f"sf{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6,
                      loc=(px, py, pz), mat_=M_SNOW_BRIGHT)
    s["_phase"] = random.uniform(0, math.pi*2)
    s["_base_x"] = px; s["_base_y"] = py; s["_base_z"] = pz
    s["_amp_x"] = random.uniform(1, 2.5)
    s["_amp_y"] = random.uniform(1, 2.5)
    s["_speed"] = random.uniform(0.4, 0.9)
    s["_fall"] = random.uniform(1.5, 3)
    snowflakes.append(s)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Aurora bands undulate
for au in range(6):
    band = bpy.data.objects.get(f"aurora{au}")
    if band is None: continue
    phase = band["_phase"]
    by_a = band.location.y
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        band.location.y = by_a + math.sin(t * 0.8 + phase) * 4
        band.location.z = band.location.z + math.sin(t * 0.5 + phase) * 0.2
        band.keyframe_insert("location", frame=f)

# Fire flicker
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    sc_fl = 1 + math.sin(t * 6.0) * 0.15
    flame_e.scale = (1 + math.cos(t * 5.0) * 0.10, 1 + math.sin(t * 5.0) * 0.10, sc_fl)
    flame_e.keyframe_insert("scale", frame=f)

# Lumberjacks chop axe motion
for l in lumberjacks:
    phase = l["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        l["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(8), 0,
                                     l["root"].rotation_euler.z)
        l["root"].keyframe_insert("rotation_euler", frame=f)
        l["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(5), 0, 0)
        l["he"].keyframe_insert("rotation_euler", frame=f)

# Beavers waddle
for bv in beavers:
    phase = bv["root"]["_phase"]
    bx_b = bv["root"].location.x; by_b = bv["root"].location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        bv["root"].location.x = bx_b + math.sin(t * 1.5 + phase) * 0.5
        bv["root"].location.y = by_b + math.cos(t * 1.5 + phase) * 0.3
        bv["root"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0,
                                       bv["root"].rotation_euler.z)
        bv["root"].keyframe_insert("location", frame=f)
        bv["root"].keyframe_insert("rotation_euler", frame=f)

# Bear walk slowly
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    bear_e.location.z = abs(math.sin(t * 1.0)) * 0.05
    head_b_e.rotation_euler = (0, 0, math.sin(t * 0.8) * math.radians(15))
    bear_e.keyframe_insert("location", frame=f)
    head_b_e.keyframe_insert("rotation_euler", frame=f)

# Moose neck sway
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    neck_m_e.rotation_euler = (0, math.radians(-15) + math.sin(t * 0.6) * math.radians(8),
                                math.cos(t * 0.6) * math.radians(10))
    neck_m_e.keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(8))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 aurora particles flow
for a in aurora_particles:
    phase = a["_phase"]; speed = a["_speed"]
    bx, by, bz = a["_base_x"], a["_base_y"], a["_base_z"]
    ax, ay, az = a["_amp_x"], a["_amp_y"], a["_amp_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        a.location = (x, y, z)
        a.keyframe_insert("location", frame=f)

# 400 snowflakes fall
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

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_canada_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_canadian_wilderness_aurora_lake] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_canadian_wilderness_aurora_lake] 8 snow mountains + glacier + frozen lake with cracks + log cabin red roof + campfire + 8 snowy firs + grizzly bear + moose with palmate antlers signature + 4 beavers with paddle tails + 6 lumberjacks plaid+tuque+axe + Canada flag + 600 aurora + 400 snow")
print("⭐ FIXES: 1 ground + 600 aurora + 400 snowflakes (signature Canada mandatory) ⭐")
