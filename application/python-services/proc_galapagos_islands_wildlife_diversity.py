"""
proc_galapagos_islands_wildlife_diversity.py — 276e procédural AuroraIA (141e qualité)
Galapagos Islands wildlife: 4 giant tortoises + 6 marine iguanas + 4 sea lions + frigates + 3 volcanic islands + Darwin ship + opuntia cacti + Ecuador flag + 600 iguana scales + 400 blue-footed boobies
FIXES : 1 ground volcanic + signature scales + boobies
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB276)

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

# Sky tropical
M_SKY = mat("sky", (0.55, 0.78, 0.92, 1.0), 0.0, 0.7, emission=(0.55,0.75,0.90), emission_strength=1.8)
M_SKY_LOW = mat("sky_l", (0.85, 0.92, 0.95, 1.0), 0.0, 0.7, emission=(0.85,0.90,0.95), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.92, 0.55, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.55), emission_strength=18.0)
M_CLOUD = mat("cl", (0.95, 0.95, 0.92, 1.0), 0.0, 0.85, emission=(0.95,0.95,0.92), emission_strength=0.8, alpha=0.85)

# Volcanic ground
M_VOLCANIC = mat("vc", (0.18, 0.16, 0.15, 1.0), 0.0, 0.92, emission=(0.18,0.16,0.15), emission_strength=0.2)
M_LAVA_ROCK = mat("lr", (0.32, 0.25, 0.22, 1.0), 0.0, 0.88)
M_SAND_BEACH = mat("sb", (0.95, 0.85, 0.55, 1.0), 0.0, 0.65, emission=(0.92,0.82,0.55), emission_strength=0.4)

# Ocean Pacific
M_OCEAN = mat("oc", (0.18, 0.55, 0.85, 1.0), 0.2, 0.20, emission=(0.18,0.55,0.82), emission_strength=1.5, alpha=0.75)
M_OCEAN_DEEP = mat("ocd", (0.10, 0.32, 0.62, 1.0), 0.2, 0.25, alpha=0.85)
M_FOAM = mat("fm", (0.95, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.90), emission_strength=1.5, alpha=0.65)

# Tortoise
M_TORT_SHELL = mat("ts", (0.32, 0.28, 0.22, 1.0), 0.0, 0.75, emission=(0.30,0.28,0.22), emission_strength=0.2)
M_TORT_SHELL_DARK = mat("tsd", (0.18, 0.15, 0.12, 1.0), 0.0, 0.85)
M_TORT_SKIN = mat("tsk", (0.42, 0.38, 0.30, 1.0), 0.0, 0.65)

# Marine iguana (signature)
M_IGUANA_BLACK = mat("ib", (0.10, 0.10, 0.12, 1.0), 0.0, 0.65, emission=(0.10,0.10,0.12), emission_strength=0.2)
M_IGUANA_GRAY = mat("ig", (0.32, 0.32, 0.35, 1.0), 0.0, 0.75)
M_IGUANA_RED = mat("ir", (0.55, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.52,0.18,0.18), emission_strength=0.4)

# Sea lion
M_SEALION_BROWN = mat("slb", (0.55, 0.38, 0.22, 1.0), 0.1, 0.55, emission=(0.52,0.38,0.22), emission_strength=0.3)
M_SEALION_DARK = mat("sld", (0.35, 0.22, 0.12, 1.0), 0.1, 0.65)
M_WHISKER = mat("wh", (0.92, 0.88, 0.80, 1.0), 0.0, 0.55)

# Frigate bird (signature red throat)
M_FRIGATE_BLACK = mat("fb", (0.10, 0.10, 0.12, 1.0), 0.0, 0.55, emission=(0.10,0.10,0.12), emission_strength=0.3)
M_FRIGATE_RED = mat("frr", (0.95, 0.18, 0.18, 1.0), 0.0, 0.30, emission=(0.92,0.18,0.18), emission_strength=2.5)

# Blue-footed booby (signature)
M_BOOBY_WHITE = mat("bw", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.92,0.90,0.85), emission_strength=0.4)
M_BOOBY_BROWN = mat("bbr", (0.55, 0.42, 0.28, 1.0), 0.0, 0.65)
M_BOOBY_BLUE_FEET = mat("bbf", (0.30, 0.65, 1.0, 1.0), 0.2, 0.20, emission=(0.30,0.65,0.95), emission_strength=3.5)
M_BOOBY_BEAK = mat("bbk", (0.45, 0.55, 0.65, 1.0), 0.2, 0.45)

# Cactus opuntia (signature)
M_CACTUS_GREEN = mat("cg", (0.30, 0.55, 0.30, 1.0), 0.0, 0.65, emission=(0.28,0.52,0.30), emission_strength=0.4)
M_CACTUS_DARK = mat("cgd", (0.22, 0.42, 0.22, 1.0), 0.0, 0.75)
M_SPINE = mat("sp", (0.85, 0.85, 0.55, 1.0), 0.0, 0.45)
M_CACTUS_FLOWER = mat("cf", (1.0, 0.85, 0.30, 1.0), 0.0, 0.40, emission=(0.95,0.82,0.30), emission_strength=1.5)

# Ship Darwin
M_SHIP_HULL = mat("sh", (0.55, 0.32, 0.15, 1.0), 0.0, 0.55, emission=(0.52,0.30,0.15), emission_strength=0.4)
M_SHIP_DECK = mat("sd", (0.65, 0.42, 0.20, 1.0), 0.0, 0.55, emission=(0.62,0.40,0.20), emission_strength=0.4)
M_SAIL_WHITE = mat("sw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.5)
M_ROPE = mat("rp", (0.65, 0.55, 0.30, 1.0), 0.0, 0.85)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_WHITE = mat("ew", (0.95, 0.92, 0.85, 1.0), 0.0, 0.30)

# Ecuador flag
M_FLAG_YELLOW = mat("fy", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.20), emission_strength=1.2)
M_FLAG_BLUE = mat("fb2", (0.18, 0.32, 0.65, 1.0), 0.0, 0.45, emission=(0.18,0.30,0.62), emission_strength=1.0)
M_FLAG_RED = mat("fr2", (0.85, 0.18, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.18), emission_strength=1.0)

# Iguana scales particles
M_SCALE_BLACK = mat("scb", (0.18, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.18,0.18,0.20), emission_strength=1.0)
M_SCALE_RED = mat("scr", (0.65, 0.22, 0.20, 1.0), 0.0, 0.45, emission=(0.62,0.22,0.20), emission_strength=1.5)
M_SCALE_GREEN = mat("scg", (0.32, 0.55, 0.32, 1.0), 0.0, 0.45, emission=(0.30,0.52,0.30), emission_strength=1.2)
SCALE_COLORS = [M_SCALE_BLACK, M_SCALE_RED, M_SCALE_GREEN]

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Sun
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(40, 100, 35), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(40, 100, 35), mat_=M_SUN)
# Clouds
for ci in range(15):
    cx_c = random.uniform(-150, 150); cy_c = random.uniform(-150, 150); cz_c = random.uniform(45, 65)
    cloud_e = empty(f"cl{ci}_e", (cx_c, cy_c, cz_c))
    for cp in range(5):
        cpa = random.uniform(0, math.pi*2); cpr = random.uniform(0, 3)
        smooth_sphere(f"cl{ci}_p{cp}", r=random.uniform(1.8, 3.5), segs=14, rings=10,
                      loc=(math.cos(cpa)*cpr, math.sin(cpa)*cpr, random.uniform(-1, 1)),
                      parent=cloud_e, mat_=M_CLOUD, scale=(1.5, 1.5, 0.5))

# ============ ONE clean volcanic ground (island archipelago) ============
ground = beveled_cube("ground", (280, 280, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_VOLCANIC)
# Lava rock scattered
for ri in range(250):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 120)
    smooth_sphere(f"lr{ri}", r=random.uniform(0.5, 1.2), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.12),
                  mat_=M_LAVA_ROCK if ri % 3 == 0 else M_VOLCANIC, scale=(1.4, 1.3, 0.22))

# Beach sand patches (signature white-sand beaches)
beach_e = empty("beach", (0, 50, 0))
for bi in range(60):
    a = random.uniform(0, math.pi*0.8) + math.pi*0.6
    rad = random.uniform(25, 60)
    smooth_sphere(f"bsd{bi}", r=random.uniform(0.5, 1.0), segs=10, rings=6,
                  loc=(rad*math.cos(a), rad*math.sin(a) - 20, 0.20),
                  parent=beach_e, mat_=M_SAND_BEACH, scale=(1.4, 1.3, 0.22))

# ============ OCEAN around archipelago ============
ocean_e = empty("ocean", (0, 60, 0))
beveled_cube("oc", (260, 100, 0.20), bevel_offset=0.08, loc=(0, 0, 0.20),
             parent=ocean_e, mat_=M_OCEAN)
beveled_cube("oc_d", (255, 95, 0.15), bevel_offset=0.06, loc=(0, 0, 0.25),
             parent=ocean_e, mat_=M_OCEAN_DEEP)
# Wave foam
for fi in range(40):
    fx = random.uniform(-100, 100); fy = random.uniform(-45, -35)
    cyl(f"fm{fi}", r=random.uniform(0.5, 1.0), depth=0.05, segs=14,
        loc=(fx, fy, 0.30), parent=ocean_e, mat_=M_FOAM)

# ============ 3 VOLCANIC ISLANDS (signature) ============
def make_volcanic_island(name, loc, height, base_radius):
    base = empty(name, loc)
    n_layers = int(height / 3)
    for li in range(n_layers):
        lz = li * 3
        lr1 = base_radius * (1 - li / n_layers * 0.85)
        lr2 = base_radius * (1 - (li+1) / n_layers * 0.85)
        smooth_cone(f"{name}_l{li}", r1=lr1, r2=lr2, depth=3.5, segs=20,
                    loc=(0, 0, lz + 1.75), parent=base, mat_=M_VOLCANIC)
    # Crater rim at top
    cyl(f"{name}_cr", r=base_radius*0.3, depth=0.40, segs=18, loc=(0, 0, height),
        parent=base, mat_=M_LAVA_ROCK)
    # Vegetation on slopes
    for vi in range(15):
        va = random.uniform(0, math.pi*2); vr = random.uniform(0.5, base_radius*0.7)
        smooth_sphere(f"{name}_v{vi}", r=random.uniform(0.4, 0.8), segs=10, rings=6,
                      loc=(math.cos(va)*vr, math.sin(va)*vr, random.uniform(2, height-2)),
                      parent=base, mat_=M_CACTUS_DARK, scale=(1.2, 1.1, 0.85))
    return base

for i, (ix, iy, ih, ir) in enumerate([(-50, 70, 18, 6), (40, 75, 22, 7), (-15, 90, 15, 5)]):
    make_volcanic_island(f"isl{i}", (ix, iy, 0), ih, ir)

# ============ 4 GIANT TORTOISES (signature) ============
def make_tortoise(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Massive dome SHELL (signature)
    shell_e = empty(f"{name}_se", (0, 0, 0.75), parent=base)
    smooth_sphere(f"{name}_sh", r=1.4, segs=22, rings=18, loc=(0, 0, 0),
                  parent=shell_e, mat_=M_TORT_SHELL, scale=(1.2, 1.1, 0.85))
    # Shell hexagonal scutes (signature)
    for sci in range(20):
        sca = random.uniform(0, math.pi*2)
        scz = random.uniform(0.2, 0.95)
        sch = math.sin(math.acos(min(1, scz / 0.95)))
        scx = math.cos(sca) * 1.45 * sch
        scy = math.sin(sca) * 1.45 * sch
        beveled_cube(f"{name}_sc{sci}", (0.30, 0.30, 0.04), bevel_offset=0.02,
                     loc=(scx, scy, scz), parent=shell_e, mat_=M_TORT_SHELL_DARK)
    # Belly plate
    smooth_sphere(f"{name}_be", r=1.2, segs=18, rings=12, loc=(0, 0, -0.3),
                  parent=shell_e, mat_=M_TORT_SKIN, scale=(1.2, 1.1, 0.3))
    # 4 thick legs
    for li, (lx_t, ly_t) in enumerate([(0.85, 0.55), (0.85, -0.55), (-0.85, 0.55), (-0.85, -0.55)]):
        leg_e = empty(f"{name}_le{li}", (lx_t, ly_t, 0.40), parent=base)
        # Upper leg
        cyl(f"{name}_ul{li}", r=0.20, depth=0.35, segs=12, loc=(0, 0, -0.18),
            parent=leg_e, mat_=M_TORT_SKIN)
        # Foot
        beveled_cube(f"{name}_ft{li}", (0.25, 0.30, 0.10), bevel_offset=0.03,
                     loc=(0, 0, -0.40), parent=leg_e, mat_=M_TORT_SKIN)
        # Claws
        for cl in range(3):
            cy_cl = -0.10 + cl * 0.10
            beveled_cube(f"{name}_cl{li}_{cl}", (0.04, 0.06, 0.04), bevel_offset=0.005,
                         loc=(0.10, cy_cl, -0.45), parent=leg_e, mat_=M_TORT_SHELL_DARK)
    # Long neck extended (signature)
    neck_e = empty(f"{name}_ne", (1.15, 0, 1.0), parent=base)
    neck_e.rotation_euler = (0, math.radians(-25), 0)
    for ni in range(5):
        cyl(f"{name}_n{ni}", r=0.15 - ni*0.005, depth=0.20, segs=10,
            loc=(0, 0, 0.10 + ni*0.18), parent=neck_e, mat_=M_TORT_SKIN)
    # Head
    head_t_e = empty(f"{name}_he", (0, 0, 1.05), parent=neck_e)
    smooth_sphere(f"{name}_h", r=0.20, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_t_e, mat_=M_TORT_SKIN, scale=(1.3, 0.85, 0.85))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.04, loc=(0.13, side*0.10, 0.05),
                      parent=head_t_e, mat_=M_EYE)
    # Mouth
    beveled_cube(f"{name}_mo", (0.10, 0.04, 0.02), bevel_offset=0.005,
                 loc=(0.20, 0, -0.05), parent=head_t_e, mat_=M_TORT_SHELL_DARK)
    # Tail
    cyl(f"{name}_t", r=0.10, depth=0.30, segs=8, loc=(-1.30, 0, 0.65),
        parent=base, mat_=M_TORT_SKIN).rotation_euler = (0, math.radians(90), 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "neck": neck_e, "he": head_t_e}

tortoises = []
tort_pos = [(-20, -15, math.radians(20)), (-5, -10, math.radians(-30)),
             (10, -18, math.radians(60)), (25, -10, math.radians(-90))]
for i, (tx_t, ty_t, fac) in enumerate(tort_pos):
    t = make_tortoise(f"to{i}", (tx_t, ty_t, 0), facing=fac)
    tortoises.append(t)

# ============ 6 MARINE IGUANAS (signature black) ============
def make_iguana(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body elongated
    smooth_sphere(f"{name}_bo", r=0.30, segs=14, rings=10, loc=(0, 0, 0.20),
                  parent=base, mat_=M_IGUANA_BLACK, scale=(2.2, 0.85, 0.55))
    # Spines along back (signature)
    for si_p in range(12):
        sx_s = -0.55 + si_p * 0.10
        sh_s = 0.18 - abs(si_p - 5.5) * 0.02
        beveled_cube(f"{name}_sp{si_p}", (0.04, 0.04, sh_s), bevel_offset=0.005,
                     loc=(sx_s, 0, 0.30 + sh_s/2), parent=base, mat_=M_IGUANA_GRAY)
    # Head
    head_i_e = empty(f"{name}_he", (0.55, 0, 0.25), parent=base)
    smooth_sphere(f"{name}_h", r=0.16, segs=12, rings=10, loc=(0, 0, 0),
                  parent=head_i_e, mat_=M_IGUANA_BLACK, scale=(1.4, 0.85, 0.85))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.03, loc=(0.06, side*0.08, 0.05),
                      parent=head_i_e, mat_=M_EYE)
    # Mouth/nose
    beveled_cube(f"{name}_no", (0.08, 0.04, 0.04), bevel_offset=0.01,
                 loc=(0.18, 0, -0.02), parent=head_i_e, mat_=M_IGUANA_GRAY)
    # Red mossy spots (signature breeding)
    for ri in range(5):
        ra = random.uniform(0, math.pi*2)
        smooth_sphere(f"{name}_r{ri}", r=0.04,
                      loc=(random.uniform(-0.5, 0.3), math.cos(ra)*0.18, 0.20),
                      parent=base, mat_=M_IGUANA_RED)
    # Long tail
    tail_e = empty(f"{name}_t", (-0.55, 0, 0.20), parent=base)
    for ti in range(6):
        tx_t = -ti * 0.20
        cyl(f"{name}_tl{ti}", r=0.10 - ti*0.012, depth=0.22, segs=10,
            loc=(tx_t, 0, 0), parent=tail_e, mat_=M_IGUANA_BLACK).rotation_euler = (0, math.radians(90), 0)
    # 4 legs (sprawled)
    for li, (lx_i, ly_i) in enumerate([(0.30, 0.30), (0.30, -0.30), (-0.20, 0.30), (-0.20, -0.30)]):
        leg_e = empty(f"{name}_le{li}", (lx_i, ly_i, 0.10), parent=base)
        cyl(f"{name}_ll{li}", r=0.06, depth=0.20, segs=8, loc=(0, ly_i*0.4, -0.05),
            parent=leg_e, mat_=M_IGUANA_BLACK).rotation_euler = (math.radians(80), 0, 0)
        # Foot/claws
        for cl in range(4):
            beveled_cube(f"{name}_cl{li}_{cl}", (0.02, 0.05, 0.02), bevel_offset=0.005,
                         loc=(cl*0.03 - 0.04, ly_i*0.5, -0.10), parent=leg_e, mat_=M_IGUANA_GRAY)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_i_e, "tail": tail_e}

iguanas = []
ig_pos = [(-30, -25, math.radians(0)), (-22, -28, math.radians(20)),
           (-12, -30, math.radians(-15)), (8, -30, math.radians(30)),
           (18, -28, math.radians(-25)), (28, -25, math.radians(10))]
for i, (igx, igy, fac) in enumerate(ig_pos):
    ig = make_iguana(f"ig{i}", (igx, igy, 0), facing=fac)
    iguanas.append(ig)

# ============ 4 SEA LIONS (signature lounging) ============
def make_sea_lion(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body cylinder/sphere (signature blob)
    smooth_sphere(f"{name}_bo", r=0.50, segs=16, rings=12, loc=(0, 0, 0.40),
                  parent=base, mat_=M_SEALION_BROWN, scale=(1.8, 0.85, 0.85))
    # Belly lighter
    smooth_sphere(f"{name}_be", r=0.48, segs=14, rings=10, loc=(0, 0, 0.25),
                  parent=base, mat_=M_SEALION_BROWN, scale=(1.6, 0.85, 0.55))
    # Head
    head_sl_e = empty(f"{name}_he", (0.75, 0, 0.55), parent=base)
    head_sl_e.rotation_euler = (0, math.radians(-30), 0)
    smooth_sphere(f"{name}_h", r=0.22, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_sl_e, mat_=M_SEALION_BROWN, scale=(1.3, 0.85, 0.85))
    # Snout
    smooth_sphere(f"{name}_sn", r=0.10, segs=10, rings=8, loc=(0.20, 0, -0.04),
                  parent=head_sl_e, mat_=M_SEALION_DARK)
    # Whiskers (signature)
    for side in (-1, 1):
        for wi in range(4):
            cyl(f"{name}_w{side}_{wi}", r=0.005, depth=0.15, segs=4,
                loc=(0.22, side*(0.06 + wi*0.02), -0.04 + wi*0.02),
                parent=head_sl_e, mat_=M_WHISKER).rotation_euler = (0, math.radians(80), 0)
    # Big eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.05, loc=(0.08, side*0.10, 0.05),
                      parent=head_sl_e, mat_=M_EYE_WHITE)
        smooth_sphere(f"{name}_ep{side}", r=0.025, loc=(0.10, side*0.10, 0.05),
                      parent=head_sl_e, mat_=M_EYE)
    # Ear flaps
    for side in (-1, 1):
        beveled_cube(f"{name}_er{side}", (0.04, 0.04, 0.10), bevel_offset=0.01,
                     loc=(-0.05, side*0.18, 0.10), parent=head_sl_e, mat_=M_SEALION_BROWN)
    # Front flippers
    for side in (-1, 1):
        flipper_e = empty(f"{name}_fl{side}", (0.30, side*0.40, 0.20), parent=base)
        flipper_e.rotation_euler = (0, math.radians(20), 0)
        beveled_cube(f"{name}_flp{side}", (0.50, 0.18, 0.06), bevel_offset=0.04,
                     loc=(0.20, 0, 0), parent=flipper_e, mat_=M_SEALION_DARK)
    # Back flippers
    for side in (-1, 1):
        beveled_cube(f"{name}_bfl{side}", (0.50, 0.20, 0.06), bevel_offset=0.04,
                     loc=(-0.70, side*0.20, 0.15), parent=base, mat_=M_SEALION_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_sl_e}

sea_lions = []
sl_pos = [(-25, 25, math.radians(20)), (-10, 30, math.radians(-10)),
           (10, 28, math.radians(30)), (25, 25, math.radians(-20))]
for i, (slx, sly, fac) in enumerate(sl_pos):
    sl = make_sea_lion(f"sl{i}", (slx, sly, 0), facing=fac)
    sea_lions.append(sl)

# ============ 4 OPUNTIA CACTI (signature) ============
def make_opuntia(name, loc):
    base = empty(name, loc)
    # Trunk
    cyl(f"{name}_tr", r=0.40, depth=2.5, segs=12, loc=(0, 0, 1.25), parent=base, mat_=M_TORT_SHELL)
    # Bark texture
    for bi in range(8):
        ba = (bi / 8.0) * math.pi * 2
        cyl(f"{name}_br{bi}", r=0.04, depth=2.4, segs=6,
            loc=(math.cos(ba)*0.40, math.sin(ba)*0.40, 1.25), parent=base, mat_=M_TORT_SHELL_DARK)
    # FLAT PAD segments (signature opuntia paddles)
    pad_positions = [(0, 0, 3, 0), (-0.7, 0, 4, math.radians(-30)),
                      (0.7, 0, 4, math.radians(30)), (0, 0.7, 5, math.radians(90)),
                      (-1.4, 0, 5.5, math.radians(-60)), (1.4, 0, 5.5, math.radians(60))]
    for pi_p, (px_p, py_p, pz_p, prot) in enumerate(pad_positions):
        pad_e = empty(f"{name}_p{pi_p}", (px_p, py_p, pz_p), parent=base)
        pad_e.rotation_euler = (0, 0, prot)
        # Flat oval pad
        smooth_sphere(f"{name}_pd{pi_p}", r=0.65, segs=14, rings=10, loc=(0, 0, 0),
                      parent=pad_e, mat_=M_CACTUS_GREEN, scale=(1.2, 0.18, 1.4))
        # Spines
        for si_sp in range(12):
            sa_s = (si_sp / 12.0) * math.pi * 2
            sr_s = random.uniform(0.4, 0.7)
            cyl(f"{name}_sp{pi_p}_{si_sp}", r=0.012, depth=0.10, segs=4,
                loc=(math.cos(sa_s)*sr_s, 0.15, math.sin(sa_s)*sr_s),
                parent=pad_e, mat_=M_SPINE)
        # Yellow flowers (signature)
        if random.random() > 0.5:
            smooth_sphere(f"{name}_fl{pi_p}", r=0.10, segs=10, rings=8,
                          loc=(0, 0.20, 0.60), parent=pad_e, mat_=M_CACTUS_FLOWER)
    return base

for i, (cx, cy) in enumerate([(-35, -8), (-20, 0), (15, 0), (35, -8)]):
    make_opuntia(f"cact{i}", (cx, cy, 0))

# ============ DARWIN SHIP (signature) ============
def make_darwin_ship(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Hull
    smooth_cone(f"{name}_h", r1=0.85, r2=0.35, depth=8, segs=14, loc=(0, 0, 0),
                parent=base, mat_=M_SHIP_HULL).rotation_euler = (0, math.radians(90), 0)
    # Deck planks
    beveled_cube(f"{name}_d", (8, 1.7, 0.15), bevel_offset=0.04, loc=(0, 0, 0.55),
                 parent=base, mat_=M_SHIP_DECK)
    # Plank lines
    for pi in range(12):
        beveled_cube(f"{name}_pl{pi}", (8.1, 0.10, 0.03), bevel_offset=0.01,
                     loc=(0, -0.75 + pi*0.15, 0.65), parent=base, mat_=M_SHIP_HULL)
    # Cabin
    beveled_cube(f"{name}_ca", (2, 1.4, 0.85), bevel_offset=0.06, loc=(-2, 0, 1.0),
                 parent=base, mat_=M_SHIP_DECK)
    # 3 masts with sails
    for mi, mx_s in enumerate([2, 0, -1]):
        mast_e = empty(f"{name}_m{mi}", (mx_s, 0, 0.6), parent=base)
        cyl(f"{name}_mp{mi}", r=0.10, depth=6, segs=10, loc=(0, 0, 3),
            parent=mast_e, mat_=M_SHIP_DECK)
        # Sail
        sail_e = empty(f"{name}_s{mi}", (0, 0, 3.5), parent=mast_e)
        beveled_cube(f"{name}_sp{mi}", (0.05, 2, 2.5), bevel_offset=0.06, loc=(0, 0, 0),
                     parent=sail_e, mat_=M_SAIL_WHITE)
        # Yardarm horizontal
        cyl(f"{name}_y{mi}", r=0.06, depth=2.2, segs=8, loc=(0, 0, 4.5),
            parent=mast_e, mat_=M_SHIP_DECK).rotation_euler = (math.radians(90), 0, 0)
        # Rigging ropes
        for ri in (-1, 1):
            cyl(f"{name}_r{mi}_{ri}", r=0.01, depth=5, segs=4,
                loc=(0, ri*0.8, 2.5), parent=mast_e, mat_=M_ROPE).rotation_euler = (math.radians(15*ri), 0, 0)
    # Bow figurehead (Darwin signature)
    smooth_sphere(f"{name}_fg", r=0.18, segs=12, rings=10, loc=(4.2, 0, 0.85),
                  parent=base, mat_=M_SAIL_WHITE)
    base["_phase"] = 0
    return base

ship = make_darwin_ship("ship", (0, 35, 0.5), facing=math.radians(0))

# ============ FRIGATE BIRDS perched on rocks ============
def make_frigate(name, loc, facing=0, inflated=False):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_bo", r=0.25, segs=12, rings=10, loc=(0, 0, 0.3),
                  parent=base, mat_=M_FRIGATE_BLACK, scale=(1.5, 0.85, 0.95))
    # RED THROAT POUCH inflated (signature)
    if inflated:
        smooth_sphere(f"{name}_th", r=0.30, segs=14, rings=12, loc=(0.30, 0, 0.10),
                      parent=base, mat_=M_FRIGATE_RED, scale=(1.0, 0.85, 1.2))
    # Head
    smooth_sphere(f"{name}_h", r=0.12, segs=10, rings=8, loc=(0.25, 0, 0.40),
                  parent=base, mat_=M_FRIGATE_BLACK)
    # Hooked beak (signature)
    cyl(f"{name}_bk", r=0.020, depth=0.20, segs=6, loc=(0.40, 0, 0.38),
        parent=base, mat_=M_BOOBY_BEAK).rotation_euler = (0, math.radians(80), 0)
    # Wings folded
    for side in (-1, 1):
        beveled_cube(f"{name}_w{side}", (0.30, 0.15, 0.05), bevel_offset=0.02,
                     loc=(-0.10, side*0.18, 0.30), parent=base, mat_=M_FRIGATE_BLACK)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.025, depth=0.20, segs=6,
            loc=(0, side*0.06, 0.10), parent=base, mat_=M_BOOBY_BEAK)
    return base

# Place some frigates on island peaks
make_frigate("fg1", (-50, 70, 18), facing=math.radians(45), inflated=True)
make_frigate("fg2", (40, 75, 22), facing=math.radians(-30), inflated=True)
make_frigate("fg3", (-15, 90, 15), facing=math.radians(120), inflated=False)

# ============ ECUADOR FLAG (signature horizontal stripes) ============
flag_e = empty("flag", (-55, -40, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_SHIP_DECK)
# 3 stripes
beveled_cube("fl_y", (4, 0.05, 1.20), bevel_offset=0.06, loc=(2, 0, 11.5),
             parent=flag_e, mat_=M_FLAG_YELLOW)
beveled_cube("fl_b", (4, 0.05, 0.60), bevel_offset=0.04, loc=(2, 0, 10.6),
             parent=flag_e, mat_=M_FLAG_BLUE)
beveled_cube("fl_r", (4, 0.05, 0.60), bevel_offset=0.04, loc=(2, 0, 10),
             parent=flag_e, mat_=M_FLAG_RED)
# Coat of arms (sun + condor simplified)
coa_e = empty("fl_co", (2, -0.05, 11.5), parent=flag_e)
smooth_sphere("fl_co_s", r=0.20, loc=(0, 0, 0), parent=coa_e, mat_=M_FLAG_BLUE)
smooth_sphere("fl_co_su", r=0.10, loc=(0, 0, 0.05), parent=coa_e, mat_=M_FLAG_YELLOW)
# Sun rays
for ri in range(8):
    rang = (ri / 8.0) * math.pi * 2
    beveled_cube(f"fl_co_r{ri}", (0.03, 0.04, 0.10), bevel_offset=0.005,
                 loc=(math.cos(rang)*0.15, 0, math.sin(rang)*0.15),
                 parent=coa_e, mat_=M_FLAG_YELLOW).rotation_euler = (0, rang, 0)
flag_e["_phase"] = 0

# ============================================================
# 600 IGUANA SCALES + 400 BLUE-FOOTED BOOBIES (PARTICULES SIGNATURES)
# ============================================================
scales = []
for i in range(600):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = random.uniform(2, 22)
    sc_col = random.choice(SCALE_COLORS)
    # Scale (small flat hexagonal piece)
    s_e = empty(f"sc{i}", (px, py, pz))
    beveled_cube(f"sc{i}_b", (0.08, 0.10, 0.02), bevel_offset=0.01,
                 loc=(0, 0, 0), parent=s_e, mat_=sc_col)
    # Ridge
    beveled_cube(f"sc{i}_r", (0.02, 0.10, 0.025), bevel_offset=0.005,
                 loc=(0, 0, 0.01), parent=s_e, mat_=sc_col)
    s_e["_phase"] = random.uniform(0, math.pi*2)
    s_e["_base_x"] = px; s_e["_base_z"] = pz
    s_e["_drift"] = random.uniform(0.15, 0.45)
    s_e["_fall"] = random.uniform(0.4, 1.0)
    s_e["_swing"] = random.uniform(0.8, 1.8)
    scales.append(s_e)

# 400 blue-footed boobies
boobies = []
for i in range(400):
    px = random.uniform(-110, 110)
    py = random.uniform(-110, 110)
    pz = random.uniform(8, 40)
    b_e = empty(f"bb{i}", (px, py, pz))
    # White body
    smooth_sphere(f"bb{i}_bo", r=0.18, segs=10, rings=8, loc=(0, 0, 0),
                  parent=b_e, mat_=M_BOOBY_WHITE, scale=(1.5, 0.85, 0.85))
    # Brown back
    smooth_sphere(f"bb{i}_bk", r=0.15, segs=10, rings=8, loc=(0, 0, 0.05),
                  parent=b_e, mat_=M_BOOBY_BROWN, scale=(1.4, 0.85, 0.65))
    # Head
    smooth_sphere(f"bb{i}_h", r=0.08, segs=10, rings=8, loc=(0.20, 0, 0.05),
                  parent=b_e, mat_=M_BOOBY_WHITE)
    # Beak (signature)
    cyl(f"bb{i}_be", r=0.015, depth=0.10, segs=6, loc=(0.30, 0, 0),
        parent=b_e, mat_=M_BOOBY_BEAK).rotation_euler = (0, math.radians(95), 0)
    # BLUE FEET (signature)
    for side in (-1, 1):
        beveled_cube(f"bb{i}_ft{side}", (0.08, 0.06, 0.025), bevel_offset=0.005,
                     loc=(0, side*0.06, -0.08), parent=b_e, mat_=M_BOOBY_BLUE_FEET)
        # Webbed toes
        for ti in range(3):
            beveled_cube(f"bb{i}_to{side}_{ti}", (0.04, 0.02, 0.015), bevel_offset=0.003,
                         loc=(0.05, side*0.06 + (ti-1)*0.025, -0.08),
                         parent=b_e, mat_=M_BOOBY_BLUE_FEET)
    # Wings (signature pointed)
    wing_e_l = empty(f"bb{i}_wl_e", (0, -0.10, 0.05), parent=b_e)
    wing_e_r = empty(f"bb{i}_wr_e", (0, 0.10, 0.05), parent=b_e)
    beveled_cube(f"bb{i}_wl", (0.16, 0.40, 0.025), bevel_offset=0.008, loc=(0, -0.20, 0),
                 parent=wing_e_l, mat_=M_BOOBY_BROWN)
    beveled_cube(f"bb{i}_wr", (0.16, 0.40, 0.025), bevel_offset=0.008, loc=(0, 0.20, 0),
                 parent=wing_e_r, mat_=M_BOOBY_BROWN)
    # Tail
    beveled_cube(f"bb{i}_t", (0.20, 0.10, 0.02), bevel_offset=0.005,
                 loc=(-0.20, 0, 0.02), parent=b_e, mat_=M_BOOBY_BROWN)
    b_e["_phase"] = random.uniform(0, math.pi*2)
    b_e["_base_x"] = px; b_e["_base_y"] = py; b_e["_base_z"] = pz
    b_e["_speed"] = random.uniform(0.6, 1.4)
    b_e["_radius"] = random.uniform(5, 14)
    b_e["_wl"] = wing_e_l; b_e["_wr"] = wing_e_r
    boobies.append(b_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Tortoises slowly walk
for t in tortoises:
    phase = t["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        ft = (f - 1) / fps
        t["root"].rotation_euler = (math.sin(ft * 0.5 + phase) * math.radians(2), 0,
                                     t["root"].rotation_euler.z)
        t["root"].keyframe_insert("rotation_euler", frame=f)
        t["neck"].rotation_euler = (0, math.radians(-25) + math.sin(ft * 0.8 + phase) * math.radians(15), 0)
        t["neck"].keyframe_insert("rotation_euler", frame=f)
        t["he"].rotation_euler = (0, 0, math.sin(ft * 0.6 + phase) * math.radians(20))
        t["he"].keyframe_insert("rotation_euler", frame=f)

# Iguanas head bob (signature salt sneeze)
for ig in iguanas:
    phase = ig["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        ft = (f - 1) / fps
        ig["he"].rotation_euler = (0, math.sin(ft * 1.5 + phase) * math.radians(10), 0)
        ig["he"].keyframe_insert("rotation_euler", frame=f)
        ig["tail"].rotation_euler = (0, 0, math.sin(ft * 0.8 + phase) * math.radians(15))
        ig["tail"].keyframe_insert("rotation_euler", frame=f)

# Sea lions sway/bark
for sl in sea_lions:
    phase = sl["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        ft = (f - 1) / fps
        sl["root"].rotation_euler = (math.sin(ft * 1.2 + phase) * math.radians(3), 0,
                                       sl["root"].rotation_euler.z)
        sl["root"].keyframe_insert("rotation_euler", frame=f)
        sl["he"].rotation_euler = (0, math.radians(-30) + math.sin(ft * 1.5 + phase) * math.radians(10), 0)
        sl["he"].keyframe_insert("rotation_euler", frame=f)

# Ship bob
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    ship.location.z = 0.5 + math.sin(t * 0.8) * 0.15
    ship.rotation_euler = (math.sin(t * 0.8) * math.radians(3),
                            math.cos(t * 0.8) * math.radians(2),
                            ship.rotation_euler.z)
    ship.keyframe_insert("location", frame=f)
    ship.keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(10))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 scales float
for sc in scales:
    phase = sc["_phase"]; drift = sc["_drift"]; fall = sc["_fall"]; swing = sc["_swing"]
    bx, bz = sc["_base_x"], sc["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.7 + t * drift
        z = bz - (t * fall) % 18
        sc.location = (x, sc.location.y, z)
        sc.rotation_euler = (t * 2.0 + phase, math.sin(t * 2.5 + phase) * math.radians(35), t * 1.5 + phase)
        sc.keyframe_insert("location", frame=f)
        sc.keyframe_insert("rotation_euler", frame=f)

# 400 boobies fly with wing flap
for bb in boobies:
    phase = bb["_phase"]; speed = bb["_speed"]; radius = bb["_radius"]
    bx, by, bz_b = bb["_base_x"], bb["_base_y"], bb["_base_z"]
    for f in range(1, total_frames + 1, 2):
        ft = (f - 1) / fps
        x = bx + math.cos(ft * speed + phase) * radius
        y = by + math.sin(ft * speed + phase) * radius
        z = bz_b + math.sin(ft * speed * 1.3 + phase) * 2
        bb.location = (x, y, z)
        bb.rotation_euler = (0, 0, math.atan2(math.cos(ft * speed + phase),
                                                -math.sin(ft * speed + phase)))
        bb.keyframe_insert("location", frame=f)
        bb.keyframe_insert("rotation_euler", frame=f)
        # Wing flap
        wing_a = math.sin(ft * 14.0 + phase) * math.radians(40)
        bb["_wl"].rotation_euler = (0, wing_a, 0)
        bb["_wr"].rotation_euler = (0, -wing_a, 0)
        bb["_wl"].keyframe_insert("rotation_euler", frame=f)
        bb["_wr"].keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_galapagos_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_galapagos_islands_wildlife_diversity] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Galapagos: 4 giant tortoises (dome shells with 20 hexagonal scutes + long extending necks + claws) + 6 marine iguanas (elongated bodies + dorsal spines + red breeding spots + long tails) + 4 sea lions (signature blob bodies + whiskers + flippers + big eyes) + 4 opuntia cacti with 6 flat pad segments + spines + yellow flowers + 3 volcanic islands with craters + 3 frigates with red inflated throat pouches signature + Darwin ship with 3 masts and sails + Ecuador flag with coat of arms sun + 600 iguana scales (3 colors) + 400 blue-footed boobies (signature blue feet + brown back + white belly + pointed wings)")
print("🐦 FIXES: 1 volcanic ground + 600 iguana scales + 400 blue-footed boobies flying signature 🐦")
