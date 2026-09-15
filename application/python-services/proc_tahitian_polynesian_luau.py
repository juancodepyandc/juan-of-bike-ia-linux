"""
proc_tahitian_polynesian_luau.py — 237e procédural AuroraIA (102e qualité)
Tahitian luau: ONE sandy beach + lagoon + reef + 6 hula dancers + male dancer + 4 musicians + bonfire + pigs + Bora Bora + 5 tikis + turtles + rays + dolphins + 3 fare huts + 600 hibiscus + 400 sea spray
FIXES : 1 ground + 600 hibiscus + 400 sea spray signature Polynesian
"""
import bpy, bmesh, math, random, os

random.seed(0x7AB17237)

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
    if bsdf is None:
        m.node_tree.nodes.clear()
        bsdf = m.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        out = m.node_tree.nodes.new("ShaderNodeOutputMaterial")
        m.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
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

# Tropical sunset palette
M_SKY = mat("sky", (1.0, 0.55, 0.30, 1.0), 0.0, 0.7, emission=(0.95,0.52,0.28), emission_strength=2.8)
M_SUN = mat("sun", (1.0, 0.65, 0.25, 1.0), 0.0, 0.10, emission=(1.0,0.65,0.25), emission_strength=22.0)
M_CLOUD = mat("cloud", (1.0, 0.75, 0.65, 1.0), 0.0, 0.55, emission=(0.95,0.72,0.62), emission_strength=2.0, alpha=0.85)

# Sand
M_GROUND = mat("ground", (0.95, 0.85, 0.65, 1.0), 0.0, 0.80, emission=(0.88,0.78,0.60), emission_strength=0.6)
M_SAND_DARK = mat("sand_d", (0.78, 0.68, 0.45, 1.0), 0.0, 0.85, emission=(0.72,0.62,0.42), emission_strength=0.5)
M_SAND_LIGHT = mat("sand_l", (1.0, 0.92, 0.75, 1.0), 0.0, 0.75, emission=(0.95,0.88,0.72), emission_strength=0.7)
M_SHELL = mat("shell", (0.95, 0.85, 0.78, 1.0), 0.3, 0.40, emission=(0.88,0.78,0.72), emission_strength=0.6)

# Lagoon water (signature turquoise)
M_LAGOON = mat("lagoon", (0.30, 0.85, 0.85, 0.85), 0.4, 0.10, emission=(0.30,0.85,0.85), emission_strength=2.0, alpha=0.85)
M_OCEAN_T = mat("ocean", (0.20, 0.55, 0.78, 1.0), 0.4, 0.15, emission=(0.18,0.50,0.72), emission_strength=1.5)
M_WATER_FOAM = mat("foam", (1.0, 1.0, 1.0, 1.0), 0.0, 0.20, emission=(0.95,0.98,1.0), emission_strength=3.0)
M_REEF = mat("reef", (1.0, 0.55, 0.45, 1.0), 0.0, 0.55, emission=(0.95,0.52,0.42), emission_strength=1.5)
M_REEF_PURPLE = mat("reef_p", (0.85, 0.40, 0.85, 1.0), 0.0, 0.55, emission=(0.78,0.38,0.78), emission_strength=1.5)

# Bora Bora mountain
M_BORA = mat("bora", (0.30, 0.45, 0.30, 1.0), 0.0, 0.80, emission=(0.28,0.42,0.28), emission_strength=0.5)
M_BORA_DARK = mat("bora_d", (0.20, 0.30, 0.20, 1.0), 0.0, 0.85)

# Palm
M_PALM_TRUNK = mat("palm_t", (0.55, 0.35, 0.20, 1.0), 0.0, 0.80, emission=(0.50,0.32,0.18), emission_strength=0.3)
M_PALM_LEAF = mat("palm_l", (0.30, 0.65, 0.30, 1.0), 0.0, 0.70, emission=(0.28,0.60,0.28), emission_strength=0.6)
M_PALM_LEAF_DARK = mat("palm_d", (0.18, 0.45, 0.20, 1.0), 0.0, 0.75)
M_COCONUT = mat("coconut", (0.42, 0.28, 0.15, 1.0), 0.0, 0.85)

# Hula clothing
M_SKIN_TAHITIAN = mat("skin", (0.85, 0.62, 0.45, 1.0), 0.0, 0.55, emission=(0.78,0.58,0.42), emission_strength=0.4)
M_GRASS_SKIRT = mat("grass_s", (0.85, 0.72, 0.30, 1.0), 0.0, 0.80, emission=(0.78,0.68,0.28), emission_strength=0.5)
M_LEI_RED = mat("lei_r", (0.95, 0.20, 0.25, 1.0), 0.0, 0.45, emission=(0.90,0.20,0.22), emission_strength=1.5)
M_LEI_PINK = mat("lei_pk", (1.0, 0.55, 0.75, 1.0), 0.0, 0.45, emission=(1.0,0.55,0.75), emission_strength=1.7)
M_LEI_YELLOW = mat("lei_y", (1.0, 0.85, 0.30, 1.0), 0.0, 0.45, emission=(1.0,0.85,0.30), emission_strength=1.7)
M_LEI_WHITE = mat("lei_w", (1.0, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(1.0,0.95,0.92), emission_strength=1.5)
M_BIKINI_TROP = mat("bik_t", (0.95, 0.42, 0.45, 1.0), 0.0, 0.40, emission=(0.88,0.40,0.42), emission_strength=0.8)
M_HAIR_BLACK_T = mat("hair_t", (0.06, 0.04, 0.03, 1.0), 0.0, 0.85)
M_TATTOO_DARK = mat("tattoo", (0.10, 0.08, 0.06, 1.0), 0.0, 0.65, emission=(0.10,0.08,0.06), emission_strength=0.4)

# Hibiscus
M_HIBISCUS_RED = mat("hib_r", (0.95, 0.20, 0.20, 1.0), 0.0, 0.45, emission=(0.90,0.20,0.20), emission_strength=2.0)
M_HIBISCUS_PINK = mat("hib_pk", (1.0, 0.55, 0.75, 1.0), 0.0, 0.45, emission=(0.95,0.50,0.70), emission_strength=2.2)
M_HIBISCUS_YELLOW = mat("hib_y", (1.0, 0.85, 0.30, 1.0), 0.0, 0.45, emission=(1.0,0.82,0.30), emission_strength=2.0)
M_HIBISCUS_ORANGE = mat("hib_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.45, emission=(0.95,0.50,0.13), emission_strength=2.2)

# Ukulele + drums
M_UKULELE = mat("uku", (0.78, 0.55, 0.30, 1.0), 0.3, 0.45, emission=(0.72,0.50,0.28), emission_strength=0.5)
M_DRUM_TRIBAL = mat("drum_t", (0.65, 0.42, 0.20, 1.0), 0.0, 0.75, emission=(0.60,0.40,0.18), emission_strength=0.5)
M_DRUM_SKIN_T = mat("drum_sk", (0.92, 0.85, 0.75, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.70), emission_strength=0.4)
M_CONCH = mat("conch", (0.95, 0.85, 0.75, 1.0), 0.3, 0.40, emission=(0.88,0.78,0.70), emission_strength=0.7)

# Bonfire
M_FIRE_O = mat("fire_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=14.0)
M_FIRE_C = mat("fire_c", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=18.0)
M_LOG_FIRE = mat("log_f", (0.30, 0.18, 0.10, 1.0), 0.0, 0.85)

# Pig
M_PIG_PINK_T = mat("pig_t", (0.85, 0.55, 0.55, 1.0), 0.0, 0.65, emission=(0.78,0.52,0.52), emission_strength=0.4)
M_PIG_ROASTED = mat("pig_r", (0.65, 0.32, 0.20, 1.0), 0.0, 0.65, emission=(0.60,0.30,0.18), emission_strength=0.5)

# Pineapple
M_PINEAPPLE = mat("pine", (1.0, 0.78, 0.20, 1.0), 0.0, 0.55, emission=(0.95,0.75,0.20), emission_strength=1.5)
M_PINE_LEAF = mat("pine_l", (0.30, 0.55, 0.25, 1.0), 0.0, 0.65, emission=(0.28,0.50,0.22), emission_strength=0.5)

# Tiki statues (signature wooden)
M_TIKI_WOOD = mat("tiki", (0.45, 0.28, 0.15, 1.0), 0.0, 0.80, emission=(0.42,0.25,0.13), emission_strength=0.5)
M_TIKI_EYE_GLOW = mat("tiki_e", (1.0, 0.85, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.20), emission_strength=10.0)

# Turtle
M_TURTLE_SHELL = mat("turtle_s", (0.35, 0.55, 0.25, 1.0), 0.0, 0.65, emission=(0.32,0.50,0.22), emission_strength=0.5)
M_TURTLE_BODY = mat("turtle_b", (0.55, 0.65, 0.42, 1.0), 0.0, 0.65, emission=(0.50,0.60,0.38), emission_strength=0.4)

# Ray
M_RAY = mat("ray", (0.30, 0.40, 0.45, 1.0), 0.3, 0.55, emission=(0.28,0.38,0.42), emission_strength=0.5, alpha=0.85)
M_RAY_BELLY = mat("ray_b", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.82), emission_strength=0.4)

# Dolphin
M_DOLPHIN = mat("dolphin", (0.55, 0.65, 0.72, 1.0), 0.0, 0.55, emission=(0.50,0.60,0.68), emission_strength=0.5)
M_DOLPHIN_BELLY = mat("dolphin_b", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.82), emission_strength=0.5)

# Faré hut
M_FARE_WOOD = mat("fare_w", (0.55, 0.35, 0.20, 1.0), 0.0, 0.75, emission=(0.50,0.32,0.18), emission_strength=0.4)
M_FARE_THATCH = mat("fare_t", (0.78, 0.62, 0.30, 1.0), 0.0, 0.85, emission=(0.72,0.58,0.28), emission_strength=0.5)

# Torches
M_TORCH_FIRE = mat("torch_f", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=14.0)

# Particles
M_HIB_PETAL_RED = mat("p_red", (0.95, 0.20, 0.25, 1.0), 0.0, 0.45, emission=(0.90,0.20,0.22), emission_strength=2.5)
M_HIB_PETAL_PINK = mat("p_pk", (1.0, 0.55, 0.75, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.70), emission_strength=2.7)
M_HIB_PETAL_YELLOW = mat("p_yel", (1.0, 0.85, 0.30, 1.0), 0.0, 0.45, emission=(1.0,0.82,0.30), emission_strength=2.5)
M_SEA_SPRAY_T = mat("spray_t", (0.85, 0.95, 0.95, 1.0), 0.0, 0.20, emission=(0.78,0.88,0.92), emission_strength=3.0, alpha=0.65)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (25, -45, 12))
smooth_sphere("sun", r=6.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=6.0 + (i+1)*2.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

clouds = []
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    rad = random.uniform(32, 45)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(22, 30)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ BORA BORA mountain ============
bora_e = empty("bora", loc=(0, -38, 0))
smooth_cone("bora_main", r1=18, r2=2, depth=20, segs=20,
            loc=(0, 0, 10), parent=bora_e, mat_=M_BORA)
# Twin peak
smooth_cone("bora_peak", r1=4, r2=1, depth=4, segs=14,
            loc=(8, -2, 16), parent=bora_e, mat_=M_BORA_DARK)
# Side smaller mountains
for side in (-1, 1):
    smooth_cone(f"bora_s{side}", r1=10, r2=2, depth=12, segs=18,
                loc=(side*20, -3, 4), parent=bora_e, mat_=M_BORA_DARK)

# ============ ONE clean sand ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)
# Sand patches
for i in range(80):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 42)
    smooth_sphere(f"sand{i}", r=random.uniform(0.25, 0.45),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_SAND_LIGHT if i % 2 == 0 else M_SAND_DARK,
                  scale=(1.4, 1.3, 0.20))
# Shells scattered
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(10, 30)
    smooth_sphere(f"shell{i}", r=random.uniform(0.15, 0.25),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.18), mat_=M_SHELL,
                  scale=(1, 0.6, 0.6))

# LAGOON (signature turquoise water in front)
beveled_cube("lagoon_main", (50, 18, 0.20), bevel_offset=0.05,
             loc=(0, -22, -0.05), mat_=M_LAGOON)
# Ocean deeper
beveled_cube("ocean_main", (50, 10, 0.15), bevel_offset=0.05,
             loc=(0, -32, -0.08), mat_=M_OCEAN_T)
# Foam waves
for i in range(20):
    rx_w = random.uniform(-23, 23)
    ry_w = random.uniform(-16, -10)
    smooth_sphere(f"wave_f{i}", r=random.uniform(0.30, 0.55),
                  loc=(rx_w, ry_w, 0.05), mat_=M_WATER_FOAM,
                  scale=(2, 1.3, 0.10))
# Coral reef (signature)
for i in range(25):
    a = random.uniform(-math.pi*0.5, math.pi*0.5)
    rad = random.uniform(8, 20)
    rx_r = rad * math.cos(a)
    ry_r = -25 + math.sin(a) * 3
    r_e = empty(f"reef{i}", (rx_r, ry_r, -0.10))
    # Branching coral
    for br in range(3):
        bra = (br / 3.0) * math.pi * 2
        col = M_REEF if i % 2 == 0 else M_REEF_PURPLE
        cyl(f"reef_b{i}_{br}", r=0.10, depth=0.40, segs=8,
            loc=(0.10*math.cos(bra), 0.10*math.sin(bra), 0.20),
            parent=r_e, mat_=col)
        smooth_sphere(f"reef_tip{i}_{br}", r=0.10,
                      loc=(0.15*math.cos(bra), 0.15*math.sin(bra), 0.40),
                      parent=r_e, mat_=col)

# ============ PALM TREES (8 signature) ============
def make_palm(name, loc, lean=15, scale=1.0):
    base = empty(name, loc)
    # Curved trunk
    trunk_segs = 8
    for s in range(trunk_segs):
        seg_x = math.sin(s * 0.3) * 0.10 * scale
        seg_y = math.cos(s * 0.3) * 0.05 * scale
        seg = smooth_cone(f"{name}_t{s}", r1=(0.30 - s*0.022)*scale, r2=(0.27 - s*0.022)*scale,
                          depth=0.9*scale, segs=12,
                          loc=(seg_x + s*math.sin(math.radians(lean))*0.2,
                               seg_y, (s+0.5)*0.9*scale),
                          parent=base, mat_=M_PALM_TRUNK)
        # Texture rings on trunk (signature)
        if s % 2 == 0:
            cyl(f"{name}_ring{s}", r=(0.32 - s*0.022)*scale, depth=0.06*scale, segs=14,
                loc=(seg_x + s*math.sin(math.radians(lean))*0.2,
                     seg_y, (s+0.3)*0.9*scale), parent=base, mat_=M_PALM_TRUNK)
    # Top fronds (signature 9 large leaves radiating)
    top_z = 7 * scale
    top_x = (trunk_segs-1) * math.sin(math.radians(lean)) * 0.2
    for j in range(9):
        a = (j / 9.0) * math.pi * 2
        f_e = empty(f"{name}_f_e{j}", (top_x, 0, top_z), parent=base)
        f_e.rotation_euler = (math.radians(30), 0, a)
        # Frond stem
        beveled_cube(f"{name}_fr{j}", (0.06*scale, 0.06*scale, 2.2*scale), bevel_offset=0.01,
                     loc=(0, 0, 1.1*scale), parent=f_e, mat_=M_PALM_LEAF)
        # Multiple leaflets along frond
        for li in range(8):
            li_z = (li + 1) * 0.27 * scale
            for side in (-1, 1):
                leaf = beveled_cube(f"{name}_leaf{j}_{li}_{side}", (0.05*scale, 0.30*scale, 0.05*scale), bevel_offset=0.01,
                                     loc=(0, side*0.20*scale, li_z), parent=f_e,
                                     mat_=M_PALM_LEAF if li % 2 == 0 else M_PALM_LEAF_DARK)
                leaf.rotation_euler = (0, 0, math.radians(side*45))
    # Coconuts (signature 5)
    for ci in range(5):
        ca = (ci / 5.0) * math.pi * 2
        smooth_sphere(f"{name}_coco{ci}", r=0.18 * scale,
                      loc=(top_x + 0.30*scale*math.cos(ca), 0.30*scale*math.sin(ca),
                           top_z - 0.30*scale), parent=base, mat_=M_COCONUT)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

palms = []
palm_pos = [(-25, 8, 0, -15, 1.0), (-20, 12, 0, 10, 0.95),
            (-12, 18, 0, -20, 1.05), (12, 18, 0, 20, 1.0),
            (20, 12, 0, -10, 0.95), (25, 8, 0, 15, 1.0),
            (-15, -8, 0, 30, 0.9), (15, -8, 0, -30, 0.9)]
for i, (px, py, pz, lean, sc) in enumerate(palm_pos):
    p = make_palm(f"palm{i}", (px, py, pz), lean=lean, scale=sc)
    palms.append(p)

# ============ BONFIRE LUAU (signature) ============
fire_e = empty("fire", loc=(0, 5, 0))
# Stone ring
for ri in range(10):
    ra = (ri / 10.0) * math.pi * 2
    smooth_sphere(f"f_stone{ri}", r=0.30,
                  loc=(1.5*math.cos(ra), 1.5*math.sin(ra), 0.20),
                  parent=fire_e, mat_=M_PALM_TRUNK)
# Logs cross
for li in range(6):
    la = (li / 6.0) * math.pi
    log = cyl(f"f_log{li}", r=0.12, depth=2.2, segs=12,
              loc=(math.cos(la)*0.15, math.sin(la)*0.15, 0.50),
              parent=fire_e, mat_=M_LOG_FIRE)
    log.rotation_euler = (0, math.radians(90), la)
# Flames
flame_e = empty("flame", (0, 0, 0.8), parent=fire_e)
smooth_cone("flame_o", r1=0.70, r2=0.05, depth=2.2, segs=14,
            loc=(0, 0, 1.1), parent=flame_e, mat_=M_FIRE_O)
smooth_cone("flame_c", r1=0.40, r2=0.02, depth=1.6, segs=14,
            loc=(0, 0, 0.8), parent=flame_e, mat_=M_FIRE_C)

# 8 ROASTED PIGS on spits around fire (signature luau)
for pi in range(8):
    pa = (pi / 8.0) * math.pi * 2
    pig_x = 4 * math.cos(pa)
    pig_y = 5 + 4 * math.sin(pa)
    pig_e = empty(f"pig{pi}", (pig_x, pig_y, 0.8))
    # Body
    smooth_sphere(f"pig_b{pi}", r=0.30, segs=18, rings=12, loc=(0, 0, 0),
                  parent=pig_e, mat_=M_PIG_ROASTED, scale=(2, 1, 1))
    # Spit through
    cyl(f"pig_spit{pi}", r=0.03, depth=2.5, segs=8, loc=(0, 0, 0),
        parent=pig_e, mat_=M_PALM_TRUNK).rotation_euler = (0, math.radians(90), 0)
    # Head
    smooth_sphere(f"pig_h{pi}", r=0.18, loc=(0.50, 0, 0.05), parent=pig_e, mat_=M_PIG_ROASTED)
    # 2 supports
    for side in (-1, 1):
        cyl(f"pig_sup{pi}_{side}", r=0.04, depth=0.6, segs=8,
            loc=(side*0.7, 0, -0.3), parent=pig_e, mat_=M_PALM_TRUNK)
    # Pineapples + coconuts beside
    if pi % 2 == 0:
        smooth_sphere(f"pine{pi}", r=0.22, loc=(0.5, 0.5, -0.6), parent=pig_e,
                      mat_=M_PINEAPPLE, scale=(1, 1, 1.4))
        for li_p in range(5):
            la_p = (li_p / 5.0) * math.pi * 2
            beveled_cube(f"pine_l{pi}_{li_p}", (0.03, 0.04, 0.18), bevel_offset=0.005,
                         loc=(0.5 + 0.05*math.cos(la_p), 0.5 + 0.05*math.sin(la_p), -0.30),
                         parent=pig_e, mat_=M_PINE_LEAF).rotation_euler = (math.radians(10*math.cos(la_p)), 0, 0)

# ============ 5 TIKIS (signature wooden statues) ============
def make_tiki(name, loc, scale=1.0):
    base = empty(name, loc)
    # Wide base
    beveled_cube(f"{name}_base", (0.5*scale, 0.5*scale, 0.3*scale), bevel_offset=0.04,
                 loc=(0, 0, 0.15*scale), parent=base, mat_=M_TIKI_WOOD)
    # Body (vertical block)
    beveled_cube(f"{name}_body", (0.55*scale, 0.45*scale, 2.5*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.55*scale), parent=base, mat_=M_TIKI_WOOD)
    # Arms folded across
    beveled_cube(f"{name}_arm", (0.60*scale, 0.10*scale, 0.20*scale), bevel_offset=0.02,
                 loc=(0, -0.20*scale, 1.50*scale), parent=base, mat_=M_TIKI_WOOD)
    # Big head signature
    head_e = empty(f"{name}_he", (0, 0, 3.10*scale), parent=base)
    beveled_cube(f"{name}_head", (0.60*scale, 0.50*scale, 0.80*scale), bevel_offset=0.06,
                 loc=(0, 0, 0), parent=head_e, mat_=M_TIKI_WOOD)
    # MASSIVE FROWN MOUTH (signature)
    beveled_cube(f"{name}_mouth", (0.40*scale, 0.05*scale, 0.15*scale), bevel_offset=0.02,
                 loc=(0, -0.26*scale, -0.20*scale), parent=head_e, mat_=M_TIKI_WOOD)
    # Teeth
    for ti in range(5):
        beveled_cube(f"{name}_tooth{ti}", (0.05*scale, 0.03*scale, 0.08*scale), bevel_offset=0.005,
                     loc=((ti-2)*0.07*scale, -0.27*scale, -0.20*scale), parent=head_e,
                     mat_=mat(f"tooth_m{name}{ti}", (0.95, 0.90, 0.85, 1.0), 0, 0.4))
    # Nose triangular
    beveled_cube(f"{name}_nose", (0.10*scale, 0.10*scale, 0.20*scale), bevel_offset=0.02,
                 loc=(0, -0.25*scale, 0), parent=head_e, mat_=M_TIKI_WOOD)
    # GLOWING eyes (signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.08*scale, loc=(side*0.15*scale, -0.26*scale, 0.15*scale),
                      parent=head_e, mat_=M_TIKI_EYE_GLOW)
    # Eye brow ridges
    for side in (-1, 1):
        beveled_cube(f"{name}_brow{side}", (0.18*scale, 0.04*scale, 0.06*scale), bevel_offset=0.01,
                     loc=(side*0.15*scale, -0.27*scale, 0.27*scale), parent=head_e, mat_=M_TIKI_WOOD)
    # Crown (carved top)
    for ci in range(5):
        ca = (ci - 2) * 0.10
        beveled_cube(f"{name}_crown{ci}", (0.08*scale, 0.40*scale, 0.15*scale), bevel_offset=0.02,
                     loc=(math.sin(ca)*0.10*scale, 0, 0.45*scale),
                     parent=head_e, mat_=M_TIKI_WOOD)
    return base

tikis = []
tiki_pos = [(-12, 0, 0, 1.0), (12, 0, 0, 1.0), (-8, 10, 0, 0.95),
            (8, 10, 0, 0.95), (0, 14, 0, 1.1)]
for i, (tx, ty, tz, sc) in enumerate(tiki_pos):
    t = make_tiki(f"tiki{i}", (tx, ty, tz), scale=sc)
    tikis.append(t)

# ============ 3 FARE HUTS (signature Polynesian thatched hut) ============
def make_fare(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Stilts (4)
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_stilt_{x}{y}", r=0.10*scale, depth=1.0*scale,
                segs=10, loc=(x*1.5*scale, y*1.0*scale, 0.5*scale),
                parent=base, mat_=M_FARE_WOOD)
    # Platform
    beveled_cube(f"{name}_platform", (3.4*scale, 2.4*scale, 0.20*scale), bevel_offset=0.04,
                 loc=(0, 0, 1.1*scale), parent=base, mat_=M_FARE_WOOD)
    # Walls (open sides signature)
    for side in (-1, 1):
        beveled_cube(f"{name}_wall_b_{side}", (3.0*scale, 0.10*scale, 1.3*scale), bevel_offset=0.04,
                     loc=(0, side*1.15*scale, 1.85*scale), parent=base, mat_=M_FARE_WOOD)
    # MASSIVE THATCHED roof (signature)
    for side, side_mul in zip(("L", "R"), (-1, 1)):
        roof = beveled_cube(f"{name}_roof_{side}", (3.5*scale, 1.8*scale, 0.30*scale), bevel_offset=0.04,
                           loc=(0, side_mul*0.9*scale, 3.0*scale), parent=base, mat_=M_FARE_THATCH)
        roof.rotation_euler = (math.radians(side_mul*-40), 0, 0)
    # Thatch detail
    for ti in range(12):
        tx_t = (ti - 5.5) * 0.30 * scale
        cyl(f"{name}_thatch{ti}", r=0.04*scale, depth=3.5*scale, segs=8,
            loc=(tx_t, 0, 3.0*scale - abs(tx_t)*0.08), parent=base, mat_=M_FARE_THATCH).rotation_euler = (0, math.radians(90), 0)
    # Roof ridge
    beveled_cube(f"{name}_ridge", (3.5*scale, 0.20*scale, 0.20*scale), bevel_offset=0.03,
                 loc=(0, 0, 3.80*scale), parent=base, mat_=M_FARE_WOOD)
    return base

fares = []
fare_pos = [(-18, 14, 0, 0.9, math.radians(20)),
            (18, 14, 0, 0.9, math.radians(-20)),
            (0, 22, 0, 1.0, math.radians(0))]
for i, (fx, fy, fz, sc, fac) in enumerate(fare_pos):
    f = make_fare(f"fare{i}", (fx, fy, fz), scale=sc, facing=fac)
    fares.append(f)

# ============ TORCHES (signature) ============
torches = []
torch_pos = [(-15, 8, 0), (15, 8, 0), (-10, 14, 0), (10, 14, 0),
             (-15, -2, 0), (15, -2, 0)]
for ti, (tx, ty, tz) in enumerate(torch_pos):
    t_e = empty(f"torch{ti}", (tx, ty, tz))
    # Pole
    cyl(f"torch_pole{ti}", r=0.08, depth=3.0, segs=10, loc=(0, 0, 1.5),
        parent=t_e, mat_=M_FARE_WOOD)
    # Top fuel
    cyl(f"torch_fuel{ti}", r=0.15, depth=0.30, segs=14, loc=(0, 0, 3.0),
        parent=t_e, mat_=M_TIKI_WOOD)
    # Flame
    flame_t_e = empty(f"torch_fl{ti}", (0, 0, 3.30), parent=t_e)
    smooth_cone(f"torch_fl_o{ti}", r1=0.30, r2=0.05, depth=1.2, segs=14,
                loc=(0, 0, 0.6), parent=flame_t_e, mat_=M_TORCH_FIRE)
    smooth_cone(f"torch_fl_c{ti}", r1=0.18, r2=0.02, depth=0.8, segs=14,
                loc=(0, 0, 0.4), parent=flame_t_e, mat_=M_FIRE_C)
    t_e["_phase"] = random.uniform(0, math.pi*2)
    torches.append({"e": t_e, "flame": flame_t_e})

# ============ 6 HULA DANCERS (signature) ============
def make_hula_dancer(name, loc, lei_color, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_hip{side_idx}", (side*0.12*scale, 0, 0.85*scale), parent=base)
        cyl(f"{name}_thigh{side_idx}", r=0.10*scale, depth=0.55*scale, segs=12,
            loc=(0, 0, -0.28*scale), parent=hip, mat_=M_SKIN_TAHITIAN)
        cyl(f"{name}_calf{side_idx}", r=0.08*scale, depth=0.55*scale, segs=12,
            loc=(0, 0, -0.85*scale), parent=hip, mat_=M_SKIN_TAHITIAN)
        # Bare feet (signature)
        beveled_cube(f"{name}_foot{side_idx}", (0.12*scale, 0.22*scale, 0.05*scale), bevel_offset=0.02,
                     loc=(0, 0.04*scale, -1.10*scale), parent=hip, mat_=M_SKIN_TAHITIAN)
    # GRASS SKIRT (signature massive long fringes)
    for fr in range(36):
        fra = (fr / 36.0) * math.pi * 2
        for sk in range(4):
            fr_z = 0.4 - sk*0.10
            beveled_cube(f"{name}_grass_fr{fr}_{sk}", (0.03*scale, 0.04*scale, 0.55*scale), bevel_offset=0.005,
                         loc=(0.32*scale*math.cos(fra), 0.32*scale*math.sin(fra),
                              fr_z*scale + 0.6*scale), parent=base, mat_=M_GRASS_SKIRT)
    # Belt with shells
    cyl(f"{name}_belt", r=0.32*scale, depth=0.08*scale, segs=18,
        loc=(0, 0, 1.05*scale), parent=base, mat_=M_PALM_TRUNK)
    for si in range(8):
        sa = (si / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_belt_sh{si}", r=0.03*scale,
                      loc=(0.34*scale*math.cos(sa), 0.34*scale*math.sin(sa), 1.05*scale),
                      parent=base, mat_=M_SHELL)
    # Bare midriff
    smooth_sphere(f"{name}_midriff", r=0.20*scale, loc=(0, 0, 1.30*scale),
                  parent=base, mat_=M_SKIN_TAHITIAN, scale=(1.3, 1, 1))
    # Bikini coconut top (signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_coco_t{side}", r=0.10*scale,
                      loc=(side*0.10*scale, -0.15*scale, 1.65*scale),
                      parent=base, mat_=M_COCONUT)
    # Strap
    beveled_cube(f"{name}_strap", (0.30*scale, 0.04*scale, 0.04*scale),
                 loc=(0, -0.18*scale, 1.78*scale), parent=base, mat_=M_PALM_TRUNK)
    # Neck
    cyl(f"{name}_neck", r=0.08*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 1.95*scale), parent=base, mat_=M_SKIN_TAHITIAN)
    # LEI necklace (signature flower garland)
    for li in range(12):
        la = (li / 12.0) * math.pi * 2
        smooth_sphere(f"{name}_lei{li}", r=0.05*scale,
                      loc=(0.18*scale*math.cos(la), -0.12*scale + 0.10*scale*math.sin(la), 1.93*scale),
                      parent=base, mat_=lei_color)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.12*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.17*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_TAHITIAN)
    # LONG black hair signature
    smooth_sphere(f"{name}_hair", r=0.22*scale, loc=(0, 0.08*scale, -0.10*scale),
                  parent=head_e, mat_=M_HAIR_BLACK_T, scale=(1.05, 1.05, 1.5))
    smooth_sphere(f"{name}_hair_t", r=0.19*scale, loc=(0, 0.02*scale, 0.06*scale),
                  parent=head_e, mat_=M_HAIR_BLACK_T, scale=(1, 1, 0.85))
    # Hair strands
    for hs in range(5):
        cyl(f"{name}_hs{hs}", r=0.025*scale, depth=0.45*scale, segs=8,
            loc=((hs-2)*0.05*scale, 0.20*scale, -0.30*scale),
            parent=head_e, mat_=M_HAIR_BLACK_T)
    # FLOWER IN HAIR (signature single hibiscus behind ear)
    smooth_sphere(f"{name}_flower", r=0.08*scale,
                  loc=(0.18*scale, 0.05*scale, 0.10*scale),
                  parent=head_e, mat_=lei_color, scale=(1, 1, 0.7))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.20, 0.10, 0.05, 1), 0, 0.4,
                                emission=(0.30,0.15,0.10), emission_strength=1.5))
    # Smile
    beveled_cube(f"{name}_smile", (0.07*scale, 0.04*scale, 0.025*scale), loc=(0, -0.17*scale, -0.08*scale),
                 parent=head_e, mat_=M_LEI_RED)
    # Arms HULA signature pose (raised + curl)
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.90*scale), parent=base)
        # Hula pose - one arm extends out, other curls
        if side_idx == 0:
            sh.rotation_euler = (math.radians(-90), 0, math.radians(-80))  # extended
        else:
            sh.rotation_euler = (math.radians(-130), 0, math.radians(50))  # curl
        cyl(f"{name}_uarm{side_idx}", r=0.07*scale, depth=0.32*scale, segs=12,
            loc=(0, 0, -0.17*scale), parent=sh, mat_=M_SKIN_TAHITIAN)
        cyl(f"{name}_fa{side_idx}", r=0.06*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.45*scale), parent=sh, mat_=M_SKIN_TAHITIAN)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07*scale, loc=(0, 0, -0.62*scale),
                      parent=sh, mat_=M_SKIN_TAHITIAN)
        # Wrist lei (signature haku)
        for wi in range(6):
            wa = (wi / 6.0) * math.pi * 2
            smooth_sphere(f"{name}_wrist{side_idx}_{wi}", r=0.03*scale,
                          loc=(0.07*scale*math.cos(wa), 0.07*scale*math.sin(wa), -0.42*scale),
                          parent=sh, mat_=lei_color)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

dancers = []
lei_colors = [M_LEI_RED, M_LEI_PINK, M_LEI_YELLOW, M_LEI_WHITE]
dancer_specs = [
    ("d1", (-5, -2, 0), M_LEI_RED, math.radians(45)),
    ("d2", (-2, -1, 0), M_LEI_PINK, math.radians(20)),
    ("d3", (0, 0, 0), M_LEI_YELLOW, math.radians(0)),
    ("d4", (2, -1, 0), M_LEI_PINK, math.radians(-20)),
    ("d5", (5, -2, 0), M_LEI_RED, math.radians(-45)),
    ("d6", (0, 2, 0), M_LEI_WHITE, math.radians(180)),
]
for spec in dancer_specs:
    name, loc, lei, fac = spec
    d = make_hula_dancer(name, loc, lei, facing=fac)
    dancers.append(d)

# ============ MALE TAHITIAN DANCER with tattoos (signature) ============
male_e = empty("male", loc=(0, -5, 0))
male_e.rotation_euler = (0, 0, math.radians(0))
# Legs bare with tattoos
for side_idx, side in enumerate((-1, 1)):
    hip = empty(f"ml_hip{side_idx}", (side*0.15, 0, 0.85), parent=male_e)
    leg_rx = math.radians(25 if side_idx == 0 else -15)
    hip.rotation_euler = (leg_rx, 0, 0)
    cyl(f"ml_thigh{side_idx}", r=0.12, depth=0.55, segs=12,
        loc=(0, 0, -0.28), parent=hip, mat_=M_SKIN_TAHITIAN)
    cyl(f"ml_calf{side_idx}", r=0.10, depth=0.55, segs=12,
        loc=(0, 0, -0.85), parent=hip, mat_=M_SKIN_TAHITIAN)
    # Tattoo bands (signature Polynesian)
    for ti in range(3):
        cyl(f"ml_tat{side_idx}_{ti}", r=0.105 + ti*0.005, depth=0.04, segs=12,
            loc=(0, 0, -0.55 + ti*0.20), parent=hip, mat_=M_TATTOO_DARK)
# Loincloth (signature pareo)
beveled_cube("ml_pareo", (0.36, 0.22, 0.35), bevel_offset=0.04, loc=(0, 0, 1.0),
             parent=male_e, mat_=M_LEI_RED)
# Belt
cyl("ml_belt", r=0.32, depth=0.06, segs=18, loc=(0, 0, 1.18),
    parent=male_e, mat_=M_PALM_TRUNK)
# Bare chest with TATTOOS (signature)
beveled_cube("ml_torso", (0.42, 0.22, 0.55), bevel_offset=0.05, loc=(0, 0, 1.45),
             parent=male_e, mat_=M_SKIN_TAHITIAN)
# Massive chest tattoo (signature)
for ti in range(8):
    ta_x = math.sin(ti * 0.4) * 0.15
    ta_z = 1.35 + ti * 0.08
    beveled_cube(f"ml_chest_tat{ti}", (0.30, 0.04, 0.05), bevel_offset=0.01,
                 loc=(ta_x, -0.12, ta_z), parent=male_e, mat_=M_TATTOO_DARK)
# Arm tattoos signature
for side in (-1, 1):
    for ai in range(4):
        cyl(f"ml_arm_tat{side}_{ai}", r=0.085, depth=0.05, segs=12,
            loc=(side*0.30, 0, 1.65 - ai*0.20), parent=male_e, mat_=M_TATTOO_DARK)
# Neck
cyl("ml_neck", r=0.09, depth=0.16, segs=10, loc=(0, 0, 1.82),
    parent=male_e, mat_=M_SKIN_TAHITIAN)
# Head
ml_head_e = empty("ml_he", (0, 0, 2.0), parent=male_e)
smooth_sphere("ml_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
              parent=ml_head_e, mat_=M_SKIN_TAHITIAN)
# Hair pulled back
smooth_sphere("ml_hair", r=0.20, loc=(0, 0.05, 0.05),
              parent=ml_head_e, mat_=M_HAIR_BLACK_T, scale=(1, 1, 0.85))
# Face tattoos (signature moko)
beveled_cube("ml_face_tat", (0.15, 0.04, 0.03), loc=(0, -0.16, 0.05),
             parent=ml_head_e, mat_=M_TATTOO_DARK)
beveled_cube("ml_face_tat_v", (0.04, 0.04, 0.15), loc=(0, -0.16, 0.02),
             parent=ml_head_e, mat_=M_TATTOO_DARK)
# Headband with feathers
cyl("ml_band", r=0.20, depth=0.04, segs=16, loc=(0, 0, 0.18),
    parent=ml_head_e, mat_=M_LEI_RED)
for fi in range(3):
    feather = beveled_cube(f"ml_fea{fi}", (0.04, 0.05, 0.30), bevel_offset=0.01,
                          loc=((fi-1)*0.06, 0.05, 0.40), parent=ml_head_e,
                          mat_=[M_LEI_RED, M_LEI_WHITE, M_LEI_YELLOW][fi])
    feather.rotation_euler = (math.radians(-20), 0, 0)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"ml_eye{side}", r=0.025, loc=(side*0.06, -0.14, 0.02),
                  parent=ml_head_e, mat_=mat(f"ml_ew{side}", (0.20, 0.10, 0.05, 1), 0, 0.4,
                                                emission=(0.30,0.15,0.10), emission_strength=1.5))
# Arms hula pose
ml_arms = []
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"ml_sh{side_idx}", (side*0.32, 0, 1.77), parent=male_e)
    sh.rotation_euler = (math.radians(-100), 0, math.radians(side*-45))
    cyl(f"ml_uarm{side_idx}", r=0.08, depth=0.35, segs=12, loc=(0, 0, -0.18), parent=sh, mat_=M_SKIN_TAHITIAN)
    cyl(f"ml_fa{side_idx}", r=0.07, depth=0.32, segs=10, loc=(0, 0, -0.50), parent=sh, mat_=M_SKIN_TAHITIAN)
    smooth_sphere(f"ml_hand{side_idx}", r=0.08, loc=(0, 0, -0.68), parent=sh, mat_=M_SKIN_TAHITIAN)
    ml_arms.append(sh)

# ============ 4 MUSICIANS ============
def make_polynesian_musician(name, loc, instrument, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_cone(f"{name}_legs", r1=0.30, r2=0.22, depth=0.55, segs=14,
                loc=(0, 0, 0.30), parent=base, mat_=M_PALM_TRUNK)
    # Bare chest
    beveled_cube(f"{name}_torso", (0.42, 0.22, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 0.95), parent=base, mat_=M_SKIN_TAHITIAN)
    # Tattoos
    for ti in range(3):
        cyl(f"{name}_arm_tat{ti}", r=0.105, depth=0.04, segs=12,
            loc=(0.30, -0.10, 1.0 + ti*0.15), parent=base, mat_=M_TATTOO_DARK)
    # Neck
    cyl(f"{name}_neck", r=0.09, depth=0.16, segs=10, loc=(0, 0, 1.30),
        parent=base, mat_=M_SKIN_TAHITIAN)
    head_e = empty(f"{name}_he", (0, 0, 1.48), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_TAHITIAN)
    smooth_sphere(f"{name}_hair", r=0.20, loc=(0, 0.04, 0.05),
                  parent=head_e, mat_=M_HAIR_BLACK_T, scale=(1, 1, 0.85))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022, loc=(side*0.06, -0.14, 0.02),
                      parent=head_e, mat_=mat(f"{name}_ew{side}", (0.20, 0.10, 0.05, 1), 0, 0.4,
                                                emission=(0.30,0.15,0.10), emission_strength=1.5))
    # Lei
    for li in range(10):
        la = (li / 10.0) * math.pi * 2
        smooth_sphere(f"{name}_lei{li}", r=0.04,
                      loc=(0.20*math.cos(la), -0.10 + 0.08*math.sin(la), 1.30),
                      parent=base, mat_=M_LEI_RED if li % 2 == 0 else M_LEI_YELLOW)
    inst_e = empty(f"{name}_inst_e", (0, -0.45, 0.85), parent=base)
    arms_e = []
    if instrument == "ukulele":
        # Ukulele signature
        smooth_sphere(f"{name}_uku_body", r=0.18, segs=18, rings=12,
                      loc=(0, 0, 0), parent=inst_e, mat_=M_UKULELE, scale=(1, 0.5, 1.3))
        beveled_cube(f"{name}_uku_neck", (0.05, 0.04, 0.45), bevel_offset=0.02,
                     loc=(0, -0.05, 0.35), parent=inst_e, mat_=M_UKULELE)
        for st in range(4):
            cyl(f"{name}_uku_str{st}", r=0.003, depth=0.65, segs=4,
                loc=((st-1.5)*0.012, -0.12, 0.20), parent=inst_e, mat_=M_DRUM_SKIN_T)
    elif instrument == "drum_tribal":
        # Tribal drum
        cyl(f"{name}_dr_body", r=0.25, depth=0.50, segs=18,
            loc=(0, 0, 0), parent=inst_e, mat_=M_DRUM_TRIBAL)
        cyl(f"{name}_dr_skin", r=0.25, depth=0.03, segs=18,
            loc=(0, 0, 0.27), parent=inst_e, mat_=M_DRUM_SKIN_T)
        # Tribal carvings
        for ci in range(8):
            ca = (ci / 8.0) * math.pi * 2
            beveled_cube(f"{name}_dr_c{ci}", (0.04, 0.04, 0.40),
                         loc=(0.25*math.cos(ca), 0.25*math.sin(ca), 0),
                         parent=inst_e, mat_=M_TATTOO_DARK)
    elif instrument == "conch":
        # Conch shell horn
        smooth_sphere(f"{name}_conch_b", r=0.22, segs=18, rings=12,
                      loc=(0, 0, 0), parent=inst_e, mat_=M_CONCH, scale=(1.3, 1, 1))
        smooth_cone(f"{name}_conch_p", r1=0.10, r2=0.04, depth=0.30, segs=12,
                    loc=(0.25, 0, 0), parent=inst_e,
                    mat_=M_CONCH).rotation_euler = (0, math.radians(90), 0)
    else:  # pahu drum (large standing)
        cyl(f"{name}_pahu", r=0.30, depth=0.80, segs=20,
            loc=(0, 0, 0.10), parent=inst_e, mat_=M_DRUM_TRIBAL)
        cyl(f"{name}_pahu_t", r=0.30, depth=0.03, segs=20,
            loc=(0, 0, 0.52), parent=inst_e, mat_=M_DRUM_SKIN_T)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.18), parent=base)
        sh.rotation_euler = (math.radians(-100), 0, math.radians(side*-25))
        cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
            loc=(0, 0, -0.15), parent=sh, mat_=M_SKIN_TAHITIAN)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
            loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_TAHITIAN)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07, loc=(0, 0, -0.58),
                      parent=sh, mat_=M_SKIN_TAHITIAN)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

musicians = []
mus_specs = [
    ("mus1", (-6, 8, 0), "ukulele", math.radians(0)),
    ("mus2", (-2, 9, 0), "drum_tribal", math.radians(0)),
    ("mus3", (2, 9, 0), "conch", math.radians(0)),
    ("mus4", (6, 8, 0), "pahu", math.radians(0)),
]
for spec in mus_specs:
    name, loc, inst, fac = spec
    m = make_polynesian_musician(name, loc, inst, facing=fac)
    musicians.append(m)

# ============ TURTLES + RAYS + DOLPHINS in lagoon ============
def make_turtle(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Shell (signature)
    smooth_sphere(f"{name}_shell", r=0.45, segs=20, rings=14, loc=(0, 0, 0.20),
                  parent=base, mat_=M_TURTLE_SHELL, scale=(1.4, 1, 0.5))
    # Shell pattern
    for sp in range(8):
        sa = (sp / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_sp{sp}", r=0.10, loc=(0.30*math.cos(sa), 0.20*math.sin(sa), 0.35),
                      parent=base, mat_=M_TURTLE_BODY, scale=(1, 1, 0.4))
    # Head
    head_e = empty(f"{name}_he", (0.55, 0, 0.15), parent=base)
    smooth_sphere(f"{name}_head", r=0.15, segs=16, rings=10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_TURTLE_BODY)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(0.05, side*0.08, 0.06),
                      parent=head_e, mat_=M_HAIR_BLACK_T)
    # 4 flippers
    for x_idx, x in enumerate((0.40, -0.40)):
        for y_idx, y in enumerate((-0.30, 0.30)):
            beveled_cube(f"{name}_flip{x_idx}{y_idx}", (0.28, 0.16, 0.06), bevel_offset=0.03,
                         loc=(x, y, 0.05), parent=base, mat_=M_TURTLE_BODY)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

turtles = [
    make_turtle("turtle1", (-10, -22, 0.3), math.radians(45)),
    make_turtle("turtle2", (10, -22, 0.3), math.radians(-45)),
]

# Manta rays
def make_ray(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Disc body
    smooth_sphere(f"{name}_body", r=0.40, segs=18, rings=12, loc=(0, 0, 0),
                  parent=base, mat_=M_RAY, scale=(1.8, 1.5, 0.20))
    # Belly white
    smooth_sphere(f"{name}_belly", r=0.35, loc=(0, 0, -0.05),
                  parent=base, mat_=M_RAY_BELLY, scale=(1.6, 1.3, 0.15))
    # Long tail
    cyl(f"{name}_tail", r=0.05, depth=0.80, segs=10, loc=(-0.60, 0, 0),
        parent=base, mat_=M_RAY)
    # Head fins (cephalic horns)
    for side in (-1, 1):
        beveled_cube(f"{name}_fin{side}", (0.20, 0.08, 0.06),
                     loc=(0.50, side*0.10, 0), parent=base, mat_=M_RAY)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.03, loc=(0.20, side*0.30, 0.05),
                      parent=base, mat_=M_HAIR_BLACK_T)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

rays = [
    make_ray("ray1", (-15, -25, 0.2), math.radians(60)),
    make_ray("ray2", (15, -25, 0.2), math.radians(-60)),
]

# Dolphins jumping
def make_dolphin(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sleek body
    smooth_sphere(f"{name}_body", r=0.30, segs=20, rings=14, loc=(0, 0, 0),
                  parent=base, mat_=M_DOLPHIN, scale=(2.5, 1, 1))
    # Belly white
    smooth_sphere(f"{name}_belly", r=0.25, loc=(0, 0, -0.08),
                  parent=base, mat_=M_DOLPHIN_BELLY, scale=(2.2, 0.95, 0.7))
    # Beak/snout (signature)
    smooth_cone(f"{name}_snout", r1=0.12, r2=0.05, depth=0.30, segs=12,
                loc=(0.75, 0, 0), parent=base, mat_=M_DOLPHIN).rotation_euler = (0, math.radians(90), 0)
    # Dorsal fin
    fin = beveled_cube(f"{name}_dorsal", (0.10, 0.10, 0.25), bevel_offset=0.03,
                      loc=(0, 0, 0.30), parent=base, mat_=M_DOLPHIN)
    fin.rotation_euler = (0, math.radians(-20), 0)
    # Tail fluke
    beveled_cube(f"{name}_fluke", (0.20, 0.50, 0.06), loc=(-0.80, 0, 0),
                 parent=base, mat_=M_DOLPHIN)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.02, loc=(0.45, side*0.18, 0.05),
                      parent=base, mat_=M_HAIR_BLACK_T)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

dolphins = [
    make_dolphin("dolphin1", (-8, -28, 1.5), math.radians(45)),
    make_dolphin("dolphin2", (8, -28, 1.5), math.radians(-45)),
]

# ============================================================
# ⭐ 600 HIBISCUS PETALS + 400 SEA SPRAY (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
hib_colors = [M_HIB_PETAL_RED, M_HIB_PETAL_PINK, M_HIB_PETAL_YELLOW]
hibiscus_petals = []
for i in range(600):
    px = random.uniform(-30, 30)
    py = random.uniform(-30, 30)
    pz = random.uniform(0.5, 12)
    col = hib_colors[i % 3]
    p_obj = smooth_sphere(f"hp{i}", r=random.uniform(0.10, 0.16), segs=10, rings=6,
                          loc=(px, py, pz), mat_=col,
                          scale=(1.5, 0.6, 0.15))
    p_obj.rotation_euler = (random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2))
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_speed"] = random.uniform(0.4, 1.2)
    p_obj["_drift_x"] = random.uniform(-1.6, 1.6)
    p_obj["_drift_y"] = random.uniform(-1.6, 1.6)
    hibiscus_petals.append(p_obj)

# 400 sea spray
sea_spray = []
for i in range(400):
    # Near lagoon
    px = random.uniform(-25, 25)
    py = random.uniform(-30, -10)
    pz = random.uniform(0.3, 5)
    s_obj = smooth_sphere(f"spray{i}", r=random.uniform(0.08, 0.14), segs=8, rings=6,
                          loc=(px, py, pz), mat_=M_SEA_SPRAY_T)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(0.6, 1.4)
    s_obj["_amp_y"] = random.uniform(0.4, 1.0)
    s_obj["_amp_z"] = random.uniform(0.4, 1.2)
    s_obj["_speed"] = random.uniform(0.6, 1.4)
    sea_spray.append(s_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Palms sway
for p in palms:
    phase = p["_phase"]
    for f in range(1, total_frames + 1, 5):
        t_v = (f - 1) / fps
        p.rotation_euler = (math.sin(t_v * 0.8 + phase) * math.radians(3),
                             math.cos(t_v * 0.7 + phase) * math.radians(2.5), 0)
        p.keyframe_insert("rotation_euler", frame=f)

# Hula dancers hip wiggle
for d in dancers:
    phase = d["root"]["_phase"]
    base_z = d["root"].location.z
    base_rz = d["root"].rotation_euler.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        d["root"].location.z = base_z + abs(math.sin(t * 3.5 + phase)) * 0.06
        d["root"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(5),
                                     math.cos(t * 2.0 + phase) * math.radians(4),
                                     base_rz + math.sin(t * 2.0 + phase) * math.radians(20))
        d["root"].keyframe_insert("location", frame=f)
        d["root"].keyframe_insert("rotation_euler", frame=f)
        for ai, arm in enumerate(d["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 2.5 + phase + ai * math.pi) * math.radians(15)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        d["he"].rotation_euler = (math.sin(t * 1.8 + phase) * math.radians(5), 0,
                                    math.sin(t * 1.5 + phase) * math.radians(15))
        d["he"].keyframe_insert("rotation_euler", frame=f)

# Male dancer fire dance
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    male_e.location.z = abs(math.sin(t * 3.0)) * 0.10
    male_e.rotation_euler = (math.sin(t * 2.0) * math.radians(6),
                              math.cos(t * 1.8) * math.radians(4),
                              math.sin(t * 1.5) * math.radians(20))
    male_e.keyframe_insert("location", frame=f)
    male_e.keyframe_insert("rotation_euler", frame=f)
    for ai, arm in enumerate(ml_arms):
        wave = math.sin(t * 3.0 + ai * math.pi) * math.radians(20)
        arm.rotation_euler = (math.radians(-100) + wave, 0, math.radians(side*-45))
        arm.keyframe_insert("rotation_euler", frame=f)

# Musicians play
for m in musicians:
    phase = m["root"]["_phase"]
    base_z = m["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["root"].location.z = base_z + math.sin(t * 2.0 + phase) * 0.04
        m["root"].keyframe_insert("location", frame=f)
        for ai, arm in enumerate(m["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 5.0 + phase + ai * math.pi) * math.radians(15)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(6), 0,
                                    math.sin(t * 1.2 + phase) * math.radians(12))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Bonfire flicker
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 5.0) * 0.15
    flame_e.scale = (1 + math.sin(t * 4.0) * 0.12,
                      1 + math.cos(t * 4.5) * 0.12, s)
    flame_e.rotation_euler = (0, 0, math.sin(t * 3.0) * 0.20)
    flame_e.keyframe_insert("scale", frame=f)
    flame_e.keyframe_insert("rotation_euler", frame=f)

# Torch flames
for tr in torches:
    phase = tr["e"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 5.0 + phase) * 0.15
        tr["flame"].scale = (1 + math.sin(t * 4.0 + phase) * 0.12,
                              1 + math.cos(t * 4.5 + phase) * 0.12, s)
        tr["flame"].rotation_euler = (0, 0, math.sin(t * 3.0 + phase) * 0.18)
        tr["flame"].keyframe_insert("scale", frame=f)
        tr["flame"].keyframe_insert("rotation_euler", frame=f)

# Turtles swim
for t_obj in turtles:
    phase = t_obj["_phase"]
    base_x = t_obj.location.x
    base_y = t_obj.location.y
    base_z = t_obj.location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        t_obj.location = (base_x + math.sin(t * 0.5 + phase) * 1.5,
                          base_y + math.cos(t * 0.4 + phase) * 1.0,
                          base_z + math.sin(t * 0.8 + phase) * 0.15)
        t_obj.keyframe_insert("location", frame=f)

# Rays glide
for r in rays:
    phase = r["_phase"]
    base_x = r.location.x
    base_y = r.location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        r.location = (base_x + math.sin(t * 0.4 + phase) * 2.0,
                      base_y + math.cos(t * 0.3 + phase) * 1.5,
                      0.2 + math.sin(t * 0.8 + phase) * 0.1)
        r.keyframe_insert("location", frame=f)

# Dolphins jump
for d_obj in dolphins:
    phase = d_obj["_phase"]
    base_x = d_obj.location.x
    base_z = d_obj.location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        d_obj.location.z = base_z + abs(math.sin(t * 1.5 + phase)) * 2.0
        d_obj.rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(30), 0,
                                 d_obj.rotation_euler.z)
        d_obj.keyframe_insert("location", frame=f)
        d_obj.keyframe_insert("rotation_euler", frame=f)

# Tiki eyes pulse
for tk in tikis:
    for obj in bpy.data.objects:
        if obj.name.startswith(f"{tk.name}_eye"):
            phase = hash(obj.name) % 100 * 0.05
            for f in range(1, total_frames + 1, 4):
                t = (f - 1) / fps
                s = 1 + math.sin(t * 3.0 + phase) * 0.30
                obj.scale = (s, s, s)
                obj.keyframe_insert("scale", frame=f)

# Clouds drift
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 0.7,
                        by + math.cos(t * 0.25 + phase) * 0.7,
                        c_e.location.z)
        c_e.keyframe_insert("location", frame=f)

# Sun halos
for obj in bpy.data.objects:
    if obj.name.startswith("sun_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.7) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 600 HIBISCUS PETALS + 400 SEA SPRAY (signature Polynesian)
# ============================================================
for p in hibiscus_petals:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    drift_x = p["_drift_x"]; drift_y = p["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        z = bz - (speed * t * 0.4) % 12
        x = bx + drift_x * math.sin(t * 1.3 + phase) * 0.6
        y = by + drift_y * math.cos(t * 1.1 + phase) * 0.6
        p.location = (x, y, max(0.1, z))
        p.rotation_euler = (phase + t * 1.7, phase + t * 1.5, phase + t * 2.0)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# 400 SEA SPRAY rise/fall
for s in sea_spray:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase) * 0.3
        z = bz + abs(math.sin(t * speed * 1.5 + phase)) * az * 2
        s.location = (x, y, max(0.1, z))
        sc = 1 + math.sin(t * 3.0 + phase) * 0.25
        s.scale = (sc, sc, sc)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_tahiti_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_tahitian_polynesian_luau] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_tahitian_polynesian_luau] ONE sand beach + lagoon turquoise + Bora Bora + 8 palms coconuts + bonfire + 8 roasted pigs + 5 tikis + 3 fare huts + 6 torches + 6 hula dancers + male dancer tattooed + 4 musicians + 2 turtles + 2 rays + 2 dolphins + 600 HIBISCUS + 400 SEA SPRAY")
print("⭐ FIXES: 1 ground + 600 hibiscus + 400 sea spray (signature Polynesian luau mandatory) ⭐")
