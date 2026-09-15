"""
proc_japanese_onsen_hot_springs.py — 236e procédural AuroraIA (101e qualité)
Japanese onsen: ONE rocky ground + rotenburo stone bath + waterfall + 6 bathers + 4 maple trees + sika deer + snow monkeys + stone lanterns + bamboo tsukubai + bridge + zen pavilion + Mt Fuji + 600 steam + 400 maple leaves
FIXES : 1 ground + 600 steam + 400 maple leaves signature onsen autumn
"""
import bpy, bmesh, math, random, os

random.seed(0x70757236)

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

# Japanese autumn palette
M_SKY = mat("sky", (0.85, 0.75, 0.62, 1.0), 0.0, 0.7, emission=(0.80,0.70,0.58), emission_strength=2.0)
M_SUN_AUTUMN = mat("sun_a", (1.0, 0.78, 0.40, 1.0), 0.0, 0.10, emission=(1.0,0.78,0.40), emission_strength=18.0)
M_CLOUD_AUTUMN = mat("cloud_a", (1.0, 0.92, 0.78, 1.0), 0.0, 0.55, emission=(0.95,0.88,0.72), emission_strength=2.0, alpha=0.85)

# Ground rocks
M_GROUND = mat("ground", (0.35, 0.32, 0.28, 1.0), 0.0, 0.85, emission=(0.32,0.30,0.26), emission_strength=0.3)
M_ROCK_ONSEN = mat("rock_o", (0.45, 0.42, 0.38, 1.0), 0.0, 0.85)
M_ROCK_DARK_O = mat("rock_d", (0.28, 0.26, 0.22, 1.0), 0.0, 0.85)
M_MOSS_O = mat("moss_o", (0.30, 0.55, 0.30, 1.0), 0.0, 0.75, emission=(0.28,0.50,0.28), emission_strength=0.5)
M_PEBBLE = mat("pebble", (0.55, 0.50, 0.45, 1.0), 0.0, 0.75)
M_GRAVEL = mat("gravel", (0.62, 0.58, 0.52, 1.0), 0.0, 0.80, emission=(0.55,0.52,0.48), emission_strength=0.3)

# Onsen water (signature warm)
M_WATER_HOT = mat("water_hot", (0.45, 0.78, 0.85, 0.85), 0.4, 0.10, emission=(0.45,0.78,0.85), emission_strength=1.8, alpha=0.85)
M_WATER_DEEP_HOT = mat("water_dhot", (0.30, 0.62, 0.72, 1.0), 0.4, 0.15, emission=(0.30,0.62,0.72), emission_strength=1.4)
M_WATER_FOAM_O = mat("foam", (1.0, 0.95, 0.92, 1.0), 0.0, 0.20, emission=(0.92,0.92,0.95), emission_strength=2.5)

# Mt Fuji
M_FUJI = mat("fuji", (0.55, 0.55, 0.65, 1.0), 0.0, 0.80)
M_FUJI_SNOW = mat("fuji_s", (0.98, 0.98, 1.0, 1.0), 0.0, 0.45, emission=(0.92,0.94,0.98), emission_strength=1.0)
M_FUJI_FAR = mat("fuji_far", (0.45, 0.45, 0.55, 1.0), 0.0, 0.85)

# Maple (momiji) signature red autumn
M_MAPLE_RED = mat("maple_r", (0.92, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.85,0.18,0.18), emission_strength=1.5)
M_MAPLE_ORANGE = mat("maple_o", (1.0, 0.45, 0.15, 1.0), 0.0, 0.50, emission=(0.95,0.42,0.13), emission_strength=1.7)
M_MAPLE_DEEP_RED = mat("maple_dr", (0.78, 0.10, 0.10, 1.0), 0.0, 0.55, emission=(0.72,0.10,0.10), emission_strength=1.6)
M_MAPLE_YELLOW = mat("maple_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.50, emission=(0.95,0.80,0.20), emission_strength=1.8)
M_MAPLE_TRUNK = mat("maple_t", (0.42, 0.30, 0.18, 1.0), 0.0, 0.85)

# Stone lantern
M_STONE_LANT = mat("stone_l", (0.55, 0.52, 0.48, 1.0), 0.0, 0.80, emission=(0.50,0.48,0.45), emission_strength=0.4)
M_LANTERN_GLOW = mat("lant_g", (1.0, 0.78, 0.40, 1.0), 0.0, 0.10, emission=(1.0,0.78,0.40), emission_strength=8.0)

# Bamboo tsukubai
M_BAMBOO = mat("bamboo", (0.65, 0.78, 0.30, 1.0), 0.0, 0.55, emission=(0.60,0.72,0.28), emission_strength=0.5)
M_BAMBOO_INSIDE = mat("bamboo_i", (0.85, 0.75, 0.45, 1.0), 0.0, 0.60)

# Bridge taiko (signature curved red)
M_BRIDGE_RED = mat("bridge_r", (0.75, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.70,0.18,0.18), emission_strength=0.7)
M_BRIDGE_GOLD = mat("bridge_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.20, emission=(0.92,0.75,0.28), emission_strength=1.0)

# Zen pavilion
M_PAVILION_WOOD = mat("pav_w", (0.45, 0.28, 0.15, 1.0), 0.0, 0.70, emission=(0.42,0.25,0.13), emission_strength=0.4)
M_PAVILION_ROOF = mat("pav_r", (0.30, 0.18, 0.10, 1.0), 0.0, 0.85, emission=(0.28,0.16,0.08), emission_strength=0.3)
M_PAVILION_WHITE = mat("pav_white", (0.95, 0.92, 0.85, 1.0), 0.0, 0.60, emission=(0.88,0.85,0.78), emission_strength=0.5)

# People
M_SKIN_JAPAN = mat("skin_j", (0.95, 0.85, 0.78, 1.0), 0.0, 0.55, emission=(0.88,0.78,0.72), emission_strength=0.35)
M_TOWEL_WHITE = mat("towel", (0.95, 0.92, 0.88, 1.0), 0.0, 0.70, emission=(0.88,0.85,0.82), emission_strength=0.6)
M_HAIR_DARK_J = mat("hair_j", (0.06, 0.04, 0.03, 1.0), 0.0, 0.85)

# Sika deer
M_DEER_TAN = mat("deer_t", (0.78, 0.55, 0.30, 1.0), 0.0, 0.75, emission=(0.72,0.50,0.28), emission_strength=0.4)
M_DEER_BELLY_O = mat("deer_b", (0.92, 0.78, 0.55, 1.0), 0.0, 0.70)
M_DEER_SPOT_WHITE = mat("deer_sp", (0.98, 0.95, 0.88, 1.0), 0.0, 0.55, emission=(0.92,0.88,0.82), emission_strength=0.5)
M_DEER_EYE_O = mat("deer_e", (0.20, 0.10, 0.05, 1.0), 0.0, 0.40, emission=(0.18,0.08,0.05), emission_strength=1.5)
M_ANTLER_O = mat("antler", (0.65, 0.55, 0.40, 1.0), 0.2, 0.55)

# Snow monkey (Macaque signature)
M_MONKEY_FUR = mat("monkey_f", (0.65, 0.55, 0.50, 1.0), 0.0, 0.90, emission=(0.60,0.52,0.48), emission_strength=0.4)
M_MONKEY_FACE_PINK = mat("monkey_p", (0.95, 0.55, 0.55, 1.0), 0.0, 0.55, emission=(0.88,0.52,0.52), emission_strength=0.5)
M_MONKEY_HANDS = mat("monkey_h", (0.95, 0.55, 0.55, 1.0), 0.0, 0.55)

# Steam (signature)
M_STEAM = mat("steam", (0.95, 0.92, 0.95, 1.0), 0.0, 0.30, emission=(0.92,0.90,0.92), emission_strength=2.5, alpha=0.55)
M_STEAM_LIGHT = mat("steam_l", (1.0, 0.98, 1.0, 1.0), 0.0, 0.30, emission=(0.95,0.95,0.98), emission_strength=2.8, alpha=0.55)

# Maple leaf particle
M_LEAF_FALL_R = mat("leaf_r", (0.92, 0.18, 0.18, 1.0), 0.0, 0.45, emission=(0.85,0.18,0.18), emission_strength=2.5)
M_LEAF_FALL_O = mat("leaf_o", (1.0, 0.55, 0.18, 1.0), 0.0, 0.45, emission=(0.95,0.50,0.18), emission_strength=2.7)
M_LEAF_FALL_Y = mat("leaf_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.80,0.20), emission_strength=2.8)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (-25, 40, 18))
smooth_sphere("sun_a", r=5.5, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN_AUTUMN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=5.5 + (i+1)*1.8, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN_AUTUMN)

clouds = []
for i in range(7):
    a = (i / 7.0) * math.pi * 2
    rad = random.uniform(32, 45)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(22, 30)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD_AUTUMN)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ MT FUJI background (signature) ============
fuji_e = empty("fuji", loc=(0, 38, 4))
fuji_main = smooth_cone("fuji_main", r1=20, r2=2.5, depth=18, segs=24,
                         loc=(0, 0, 0), parent=fuji_e, mat_=M_FUJI)
# Snow cap (signature)
smooth_cone("fuji_snow", r1=5.0, r2=2.0, depth=4.0, segs=24,
            loc=(0, 0, 9.5), parent=fuji_e, mat_=M_FUJI_SNOW)
# Side smaller peak
for side in (-1, 1):
    smooth_cone(f"fuji_side{side}", r1=12, r2=2, depth=10, segs=20,
                loc=(side*22, -3, -3), parent=fuji_e, mat_=M_FUJI_FAR)
    smooth_cone(f"fuji_cap_s{side}", r1=3.0, r2=1.2, depth=2.0, segs=18,
                loc=(side*22, -3, 3.5), parent=fuji_e, mat_=M_FUJI_SNOW)

# ============ ONE clean rocky ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)
# Pebble/gravel patches (organic 3D)
for i in range(80):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 42)
    smooth_sphere(f"pebble{i}", r=random.uniform(0.20, 0.40),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_PEBBLE if i % 3 == 0 else (M_GRAVEL if i % 3 == 1 else M_ROCK_ONSEN),
                  scale=(1.3, 1.2, 0.30))
# Rocks scattered
for i in range(35):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(15, 40)
    smooth_sphere(f"rock{i}", r=random.uniform(0.5, 1.0),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_ROCK_ONSEN if i % 2 == 0 else M_ROCK_DARK_O,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.85)))
# Moss patches
for i in range(25):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(10, 35)
    smooth_sphere(f"moss{i}", r=random.uniform(0.25, 0.50),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_MOSS_O, scale=(1.4, 1.2, 0.20))

# ============ ROTENBURO STONE BATH (signature outdoor onsen) ============
bath_e = empty("bath", loc=(0, 0, 0))
# Rock ring around bath (signature)
for i in range(24):
    a = (i / 24.0) * math.pi * 2
    rx = 5.5 * math.cos(a)
    ry = 5.0 * math.sin(a)
    smooth_sphere(f"bath_rock{i}", r=random.uniform(0.55, 0.80),
                  loc=(rx, ry, 0.40), parent=bath_e,
                  mat_=M_ROCK_ONSEN if i % 2 == 0 else M_ROCK_DARK_O,
                  scale=(random.uniform(0.9, 1.3), random.uniform(0.9, 1.3),
                         random.uniform(0.7, 1.0)))
# Water surface (signature warm spring)
bath_water = cyl("bath_water", r=4.5, depth=0.30, segs=32, loc=(0, 0, 0.40),
    parent=bath_e, mat_=M_WATER_HOT)
bath_water.scale = (1, 0.85, 1)
# Deeper center
bath_water_deep = cyl("bath_water_deep", r=2.5, depth=0.40, segs=32, loc=(0, 0, 0.35),
    parent=bath_e, mat_=M_WATER_DEEP_HOT)
bath_water_deep.scale = (1, 0.85, 1)
# Water ripples
for i in range(15):
    a = random.uniform(0, math.pi*2)
    rad_r = random.uniform(1, 4)
    smooth_sphere(f"bath_ripple{i}", r=random.uniform(0.25, 0.40), segs=14, rings=10,
                  loc=(rad_r*math.cos(a), rad_r*math.sin(a)*0.85, 0.50),
                  parent=bath_e, mat_=M_WATER_FOAM_O, scale=(1.5, 1.3, 0.10))
# Moss on bath rocks
for i in range(15):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 6)
    smooth_sphere(f"bath_moss{i}", r=random.uniform(0.15, 0.30),
                  loc=(rad*math.cos(a), rad*math.sin(a)*0.85, 0.55), parent=bath_e,
                  mat_=M_MOSS_O, scale=(1.2, 0.6, 0.4))

# ============ WATERFALL (signature) ============
wf_e = empty("waterfall", loc=(-12, 10, 0))
# Rock cliff
for ri in range(7):
    smooth_sphere(f"wf_cliff{ri}", r=random.uniform(1.2, 2.0),
                  loc=(random.uniform(-2, 2), random.uniform(-2, 2),
                       2 + ri*1.3), parent=wf_e, mat_=M_ROCK_ONSEN, scale=(1.2, 1.0, 1.2))
# Falling water column signature
beveled_cube("wf_main", (1.4, 0.5, 7), bevel_offset=0.04, loc=(0, 0, 5),
             parent=wf_e, mat_=M_WATER_HOT)
# Foam top
smooth_sphere("wf_top", r=1.0, loc=(0, 0, 8.5), parent=wf_e, mat_=M_WATER_FOAM_O,
              scale=(1.3, 1, 0.6))
# Splash base
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    smooth_sphere(f"wf_sp{i}", r=random.uniform(0.30, 0.45),
                  loc=(math.cos(a)*1.0, math.sin(a)*1.0, 0.5),
                  parent=wf_e, mat_=M_WATER_FOAM_O)
# Stream to bath
for si in range(8):
    sx = -10 + si * 1.3
    smooth_sphere(f"stream{si}", r=0.25, segs=14, rings=10,
                  loc=(sx, 6 - si*0.8, 0.15), mat_=M_WATER_HOT, scale=(1.3, 1, 0.20))

# ============ 4 MAPLE TREES (momiji signature red autumn) ============
def make_maple(name, loc, scale=1.0):
    base = empty(name, loc)
    # Trunk
    for s in range(5):
        seg_x = math.sin(s * 0.3) * 0.08 * scale
        seg = smooth_cone(f"{name}_t{s}", r1=(0.30 - s*0.025)*scale, r2=(0.27 - s*0.025)*scale,
                          depth=0.8*scale, segs=12,
                          loc=(seg_x, 0, (s+0.5)*0.8*scale),
                          parent=base, mat_=M_MAPLE_TRUNK)
        seg.rotation_euler = (math.radians(random.uniform(-5, 5)),
                              math.radians(random.uniform(-5, 5)), 0)
    # 6 branches spreading wide (signature maple shape)
    for j in range(6):
        a = (j / 6.0) * math.pi * 2
        b_e = empty(f"{name}_be{j}", (0, 0, 3.8*scale), parent=base)
        b_e.rotation_euler = (math.radians(45), 0, a)
        for k in range(3):
            cyl(f"{name}_b{j}_{k}", r=(0.12 - k*0.025)*scale, depth=0.6*scale, segs=10,
                loc=(0, (k+0.5)*0.6*scale, 0), parent=b_e,
                mat_=M_MAPLE_TRUNK).rotation_euler = (math.radians(90), 0, 0)
    # MASSIVE RED CANOPY (signature autumn momiji)
    for j in range(12):
        a = (j / 12.0) * math.pi * 2
        rad = random.uniform(1.5, 3.0) * scale
        # Mix of red shades signature
        col = [M_MAPLE_RED, M_MAPLE_ORANGE, M_MAPLE_DEEP_RED, M_MAPLE_YELLOW][j % 4]
        smooth_sphere(f"{name}_can{j}", r=random.uniform(1.0, 1.5) * scale,
                      loc=(rad*math.cos(a), rad*math.sin(a), 5.0*scale + random.uniform(-0.3, 0.8)),
                      parent=base, mat_=col, scale=(1, 1, 0.7))
    # Smaller puffs
    for j in range(15):
        a = random.uniform(0, math.pi*2)
        rad = random.uniform(1.0, 3.0) * scale
        col = random.choice([M_MAPLE_RED, M_MAPLE_ORANGE, M_MAPLE_DEEP_RED, M_MAPLE_YELLOW])
        smooth_sphere(f"{name}_sub{j}", r=random.uniform(0.4, 0.7) * scale,
                      loc=(rad*math.cos(a), rad*math.sin(a), 5.0*scale + random.uniform(-0.5, 0.6)),
                      parent=base, mat_=col, scale=(1, 1, 0.6))
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

maples = []
maple_pos = [(-10, -8, 0, 1.0), (10, -8, 0, 1.05),
             (-12, 18, 0, 0.95), (12, 18, 0, 1.0)]
for i, (mx, my, mz, sc) in enumerate(maple_pos):
    m = make_maple(f"maple{i}", (mx, my, mz), scale=sc)
    maples.append(m)

# ============ 4 STONE LANTERNS (ishidoro signature) ============
def make_ishidoro(name, loc):
    base = empty(name, loc)
    # Base wide
    cyl(f"{name}_base", r=0.40, depth=0.20, segs=14, loc=(0, 0, 0.10),
        parent=base, mat_=M_STONE_LANT)
    # Pole
    cyl(f"{name}_pole", r=0.18, depth=1.2, segs=14, loc=(0, 0, 0.80),
        parent=base, mat_=M_STONE_LANT)
    # Middle platform
    cyl(f"{name}_mid", r=0.42, depth=0.10, segs=14, loc=(0, 0, 1.45),
        parent=base, mat_=M_STONE_LANT)
    # Light chamber (signature opening)
    beveled_cube(f"{name}_chamber", (0.45, 0.45, 0.50), bevel_offset=0.04,
                 loc=(0, 0, 1.80), parent=base, mat_=M_STONE_LANT)
    # Glowing window (signature)
    smooth_sphere(f"{name}_glow", r=0.15, loc=(0, -0.18, 1.80),
                  parent=base, mat_=M_LANTERN_GLOW, scale=(1, 0.3, 1))
    # Top roof
    cyl(f"{name}_roof", r=0.55, depth=0.10, segs=14, loc=(0, 0, 2.15),
        parent=base, mat_=M_STONE_LANT)
    # Roof slanted top
    smooth_cone(f"{name}_pyr", r1=0.55, r2=0.10, depth=0.40, segs=14,
                loc=(0, 0, 2.45), parent=base, mat_=M_STONE_LANT)
    # Finial top
    smooth_sphere(f"{name}_top", r=0.10, loc=(0, 0, 2.80),
                  parent=base, mat_=M_STONE_LANT)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

lanterns = []
lant_pos = [(-7, 4, 0), (7, 4, 0), (-7, -4, 0), (7, -4, 0)]
for i, (lx, ly, lz) in enumerate(lant_pos):
    l = make_ishidoro(f"lant{i}", (lx, ly, lz))
    lanterns.append(l)

# ============ BAMBOO TSUKUBAI (signature) ============
tsuk_e = empty("tsukubai", loc=(8, 2, 0))
# Stone basin
cyl("tsuk_basin", r=0.45, depth=0.30, segs=18, loc=(0, 0, 0.15),
    parent=tsuk_e, mat_=M_ROCK_ONSEN)
# Inner water
cyl("tsuk_water", r=0.38, depth=0.20, segs=18, loc=(0, 0, 0.20),
    parent=tsuk_e, mat_=M_WATER_HOT)
# Bamboo spout (signature pole + horizontal pipe)
cyl("tsuk_pole", r=0.05, depth=1.2, segs=12, loc=(0.7, 0, 0.60),
    parent=tsuk_e, mat_=M_BAMBOO)
# Horizontal pipe spout
cyl("tsuk_spout", r=0.05, depth=0.50, segs=12, loc=(0.4, 0, 0.95),
    parent=tsuk_e, mat_=M_BAMBOO).rotation_euler = (0, math.radians(90), 0)
# Bamboo end open (inside lighter)
cyl("tsuk_end", r=0.04, depth=0.04, segs=12, loc=(0.10, 0, 0.95),
    parent=tsuk_e, mat_=M_BAMBOO_INSIDE).rotation_euler = (0, math.radians(90), 0)
# Water stream from spout
for ws in range(4):
    smooth_sphere(f"tsuk_ws{ws}", r=0.03,
                  loc=(0.10, 0, 0.95 - ws*0.15), parent=tsuk_e, mat_=M_WATER_HOT,
                  scale=(1, 1, 1.5))

# ============ TAIKO BRIDGE (signature curved red bridge) ============
bridge_e = empty("bridge", loc=(-3, 14, 0))
bridge_e.rotation_euler = (0, 0, math.radians(15))
# Stream water below
beveled_cube("br_water", (5, 1.5, 0.10), bevel_offset=0.05, loc=(0, 0, 0.05),
             parent=bridge_e, mat_=M_WATER_HOT)
# CURVED bridge (signature taiko)
for arch_seg in range(11):
    ang = math.pi - (arch_seg / 10.0) * math.pi
    ax_b = math.cos(ang) * 2.5
    az_b = math.sin(ang) * 1.5
    beveled_cube(f"br_arch{arch_seg}", (0.4, 1.5, 0.15), bevel_offset=0.03,
                 loc=(ax_b, 0, az_b + 0.5), parent=bridge_e, mat_=M_BRIDGE_RED)
# Railings
for side in (-1, 1):
    for arch_seg in range(11):
        ang = math.pi - (arch_seg / 10.0) * math.pi
        ax_b = math.cos(ang) * 2.5
        az_b = math.sin(ang) * 1.5
        smooth_sphere(f"br_rail_{side}_{arch_seg}", r=0.06,
                      loc=(ax_b, side*0.65, az_b + 1.0), parent=bridge_e, mat_=M_BRIDGE_RED)
    # Top rail
    for arch_seg in range(11):
        ang = math.pi - (arch_seg / 10.0) * math.pi
        ax_b = math.cos(ang) * 2.5
        az_b = math.sin(ang) * 1.5
        smooth_sphere(f"br_rail_t_{side}_{arch_seg}", r=0.06,
                      loc=(ax_b, side*0.65, az_b + 1.30), parent=bridge_e, mat_=M_BRIDGE_GOLD)

# ============ ZEN PAVILION (signature) ============
pav_e = empty("pavilion", loc=(15, 12, 0))
# Wooden platform
beveled_cube("pav_floor", (3.0, 2.5, 0.20), bevel_offset=0.04, loc=(0, 0, 0.10),
             parent=pav_e, mat_=M_PAVILION_WOOD)
# 4 columns
for x in (-1, 1):
    for y in (-1, 1):
        cyl(f"pav_col_{x}{y}", r=0.10, depth=2.5, segs=12,
            loc=(x*1.3, y*1.1, 1.45), parent=pav_e, mat_=M_PAVILION_WOOD)
# Roof slanted curved
for side, side_mul in zip(("L", "R"), (-1, 1)):
    roof = beveled_cube(f"pav_roof_{side}", (3.5, 1.8, 0.25), bevel_offset=0.04,
                       loc=(0, side_mul*1.0, 3.0), parent=pav_e, mat_=M_PAVILION_ROOF)
    roof.rotation_euler = (math.radians(side_mul*-30), 0, 0)
# Curved corners (signature pagoda)
for x in (-1, 1):
    for y in (-1, 1):
        curl = beveled_cube(f"pav_curl_{x}{y}", (0.20, 0.20, 0.30), bevel_offset=0.04,
                           loc=(x*1.6, y*0.8, 3.2), parent=pav_e, mat_=M_PAVILION_ROOF)
        curl.rotation_euler = (math.radians(y*-30), 0, math.radians(x*-30))
# Top spire
smooth_cone("pav_spire", r1=0.10, r2=0.02, depth=0.40, segs=10,
            loc=(0, 0, 3.6), parent=pav_e, mat_=M_BRIDGE_GOLD)
# Inside lantern
cyl("pav_lant", r=0.20, depth=0.30, segs=14, loc=(0, 0, 2.2),
    parent=pav_e, mat_=M_LANTERN_GLOW)

# ============ 6 BATHERS in onsen (signature) ============
def make_bather(name, loc, has_towel_head=True, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Submerged body (only torso/head above water)
    # Torso (signature shoulders above water)
    smooth_sphere(f"{name}_torso", r=0.32, segs=20, rings=14, loc=(0, 0, 0.55),
                  parent=base, mat_=M_SKIN_JAPAN, scale=(1.4, 1, 0.7))
    # Shoulders rounded
    for side in (-1, 1):
        smooth_sphere(f"{name}_shoulder{side}", r=0.16, loc=(side*0.30, 0, 0.55),
                      parent=base, mat_=M_SKIN_JAPAN)
    # Neck
    cyl(f"{name}_neck", r=0.09, depth=0.15, segs=10, loc=(0, 0, 0.78),
        parent=base, mat_=M_SKIN_JAPAN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 0.95), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_JAPAN)
    # Hair
    smooth_sphere(f"{name}_hair", r=0.20, loc=(0, 0.05, 0.05),
                  parent=head_e, mat_=M_HAIR_DARK_J, scale=(1, 1, 0.85))
    # TOWEL FOLDED on head (signature onsen)
    if has_towel_head:
        beveled_cube(f"{name}_towel_h", (0.30, 0.20, 0.06), bevel_offset=0.02,
                     loc=(0, 0.02, 0.18), parent=head_e, mat_=M_TOWEL_WHITE)
        # Fold
        beveled_cube(f"{name}_towel_f", (0.30, 0.10, 0.10), bevel_offset=0.02,
                     loc=(0, -0.08, 0.20), parent=head_e, mat_=M_TOWEL_WHITE)
    # Eyes (closed peaceful signature)
    for side in (-1, 1):
        beveled_cube(f"{name}_eye{side}", (0.05, 0.04, 0.005),
                     loc=(side*0.06, -0.14, 0.02), parent=head_e, mat_=M_HAIR_DARK_J)
    # Smile relaxed
    beveled_cube(f"{name}_smile", (0.07, 0.04, 0.02), loc=(0, -0.18, -0.06),
                 parent=head_e, mat_=mat(f"smile{name}", (0.65, 0.30, 0.30, 1), 0, 0.5))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

bathers = []
bather_specs = [
    ("b1", (-2.5, 1, 0), True, math.radians(45)),
    ("b2", (2.5, 1, 0), True, math.radians(-45)),
    ("b3", (-2, -1.5, 0), True, math.radians(120)),
    ("b4", (2, -1.5, 0), True, math.radians(-120)),
    ("b5", (0, 2.5, 0), True, math.radians(180)),
    ("b6", (0, -3.0, 0), True, math.radians(0)),
]
for spec in bather_specs:
    name, loc, towel, fac = spec
    b = make_bather(name, loc, has_towel_head=towel, facing=fac)
    bathers.append(b)

# ============ 2 SIKA DEER (signature spotted) ============
def make_sika_deer(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.45, segs=20, rings=14, loc=(0, 0, 1.0),
                  parent=base, mat_=M_DEER_TAN, scale=(1.7, 1, 1))
    # Belly white
    smooth_sphere(f"{name}_belly", r=0.35, loc=(0, 0, 0.85),
                  parent=base, mat_=M_DEER_BELLY_O, scale=(1.5, 0.95, 0.6))
    # WHITE SPOTS on back (signature sika)
    for sp in range(12):
        smooth_sphere(f"{name}_spot{sp}", r=0.06,
                      loc=(random.uniform(-0.6, 0.6), random.uniform(-0.4, 0.4),
                           1.10 + random.uniform(-0.1, 0.3)),
                      parent=base, mat_=M_DEER_SPOT_WHITE, scale=(1, 1, 0.4))
    # Neck (long graceful)
    neck = beveled_cube(f"{name}_neck", (0.25, 0.20, 0.70), bevel_offset=0.04,
                       loc=(0.75, 0, 1.30), parent=base, mat_=M_DEER_TAN)
    neck.rotation_euler = (0, math.radians(-30), 0)
    # Head
    head_e = empty(f"{name}_he", (1.10, 0, 1.65), parent=base)
    beveled_cube(f"{name}_head", (0.35, 0.18, 0.25), bevel_offset=0.04,
                 loc=(0, 0, 0), parent=head_e, mat_=M_DEER_TAN)
    smooth_cone(f"{name}_muzzle", r1=0.08, r2=0.05, depth=0.18, segs=12,
                loc=(0.20, 0, -0.04), parent=head_e,
                mat_=M_DEER_TAN).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04,
                      loc=(0.05, side*0.10, 0.08), parent=head_e, mat_=M_DEER_EYE_O)
    # Ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.05, r2=0.01, depth=0.18, segs=10,
                          loc=(-0.05, side*0.12, 0.15), parent=head_e, mat_=M_DEER_TAN)
        ear.rotation_euler = (math.radians(-15), 0, math.radians(side*30))
    # Antlers (smaller for sika)
    for side in (-1, 1):
        ant_e = empty(f"{name}_ant{side}", (-0.05, side*0.10, 0.22), parent=head_e)
        ant_e.rotation_euler = (math.radians(-20), 0, math.radians(side*15))
        cyl(f"{name}_ant_m{side}", r=0.04, depth=0.35, segs=8,
            loc=(0, 0, 0.17), parent=ant_e, mat_=M_ANTLER_O)
        # 3 tines
        for ti in range(3):
            tine_h = 0.10 + ti * 0.08
            cyl(f"{name}_tine{side}_{ti}", r=0.025, depth=0.18, segs=6,
                loc=(math.sin(ti*0.3)*0.06, 0, tine_h*1.5), parent=ant_e, mat_=M_ANTLER_O).rotation_euler = (0, math.radians(side*30), 0)
    # 4 long legs
    for x_idx, x in enumerate((0.45, -0.45)):
        for y_idx, y in enumerate((-0.30, 0.30)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.06, depth=0.90, segs=10,
                loc=(x, y, 0.45), parent=base, mat_=M_DEER_TAN)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.07, depth=0.08, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_HAIR_DARK_J)
    # Short tail
    smooth_sphere(f"{name}_tail", r=0.08, loc=(-0.70, 0, 1.0),
                  parent=base, mat_=M_DEER_BELLY_O)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

deer = [
    make_sika_deer("deer1", (-18, 5, 0), math.radians(45)),
    make_sika_deer("deer2", (18, 5, 0), math.radians(-45)),
]

# ============ SNOW MONKEYS in bath (signature Japanese macaque) ============
def make_snow_monkey(name, loc, in_water=False, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    z_off = 0.4 if in_water else 0
    # Furry body (signature thick fur)
    smooth_sphere(f"{name}_body", r=0.28, segs=18, rings=12, loc=(0, 0, 0.55 + z_off),
                  parent=base, mat_=M_MONKEY_FUR, scale=(1.4, 1, 1.1))
    # Head
    head_e = empty(f"{name}_he", (0.30, 0, 0.85 + z_off), parent=base)
    smooth_sphere(f"{name}_head", r=0.22, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_MONKEY_FUR)
    # PINK FACE signature
    smooth_sphere(f"{name}_face", r=0.18, loc=(0, -0.08, 0),
                  parent=head_e, mat_=M_MONKEY_FACE_PINK, scale=(1, 0.4, 1.1))
    # Ears (small round)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.07, loc=(side*0.18, 0.05, 0.05),
                      parent=head_e, mat_=M_MONKEY_FUR)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.16, 0.05),
                      parent=head_e, mat_=M_HAIR_DARK_J)
    # Nose (small)
    smooth_sphere(f"{name}_nose", r=0.02, loc=(0, -0.20, -0.05),
                  parent=head_e, mat_=M_HAIR_DARK_J)
    # If not in water, show legs
    if not in_water:
        for x_idx, x in enumerate((0.20, -0.20)):
            for y_idx, y in enumerate((-0.15, 0.15)):
                cyl(f"{name}_leg{x_idx}{y_idx}", r=0.05, depth=0.30, segs=10,
                    loc=(x, y, 0.25), parent=base, mat_=M_MONKEY_FUR)
        # Tail
        cyl(f"{name}_tail", r=0.04, depth=0.35, segs=8,
            loc=(-0.30, 0, 0.55), parent=base, mat_=M_MONKEY_FUR).rotation_euler = (0, math.radians(-45), 0)
    # Arms
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 0.75 + z_off), parent=base)
        sh.rotation_euler = (math.radians(-30), 0, math.radians(side*-15))
        cyl(f"{name}_arm{side_idx}", r=0.06, depth=0.30, segs=10,
            loc=(0, 0, -0.15), parent=sh, mat_=M_MONKEY_FUR)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.06, loc=(0, 0, -0.32),
                      parent=sh, mat_=M_MONKEY_HANDS)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

monkeys = []
monkey_specs = [
    # In bath
    ("monk1", (-1, 3, 0.4), True, math.radians(90)),
    ("monk2", (1, 3, 0.4), True, math.radians(-90)),
    # On rocks
    ("monk3", (-8, -2, 1.0), False, math.radians(45)),
    ("monk4", (8, -2, 1.0), False, math.radians(-45)),
    ("monk5", (-6, 7, 1.0), False, math.radians(120)),
]
for spec in monkey_specs:
    name, loc, in_w, fac = spec
    m = make_snow_monkey(name, loc, in_water=in_w, facing=fac)
    monkeys.append(m)

# ============================================================
# ⭐ 600 STEAM + 400 MAPLE LEAVES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 steam particles (signature onsen vapor rising)
steam_particles = []
for i in range(600):
    # Concentrate around bath
    if i < 400:
        a = random.uniform(0, math.pi*2)
        rad = random.uniform(0, 5)
        px = rad * math.cos(a)
        py = rad * math.sin(a) * 0.85
    else:
        px = random.uniform(-15, 15)
        py = random.uniform(-15, 15)
    pz = random.uniform(0.8, 8)
    s_obj = smooth_sphere(f"steam{i}", r=random.uniform(0.25, 0.55), segs=12, rings=8,
                          loc=(px, py, pz), mat_=M_STEAM if i % 2 == 0 else M_STEAM_LIGHT,
                          scale=(1.3, 1.3, 0.5))
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(0.4, 1.2)
    s_obj["_amp_y"] = random.uniform(0.4, 1.2)
    s_obj["_speed"] = random.uniform(0.3, 0.8)
    steam_particles.append(s_obj)

# 400 maple leaves falling
maple_leaves = []
for i in range(400):
    px = random.uniform(-30, 30)
    py = random.uniform(-30, 30)
    pz = random.uniform(1, 15)
    col = [M_LEAF_FALL_R, M_LEAF_FALL_O, M_LEAF_FALL_Y][i % 3]
    p_obj = smooth_sphere(f"leaf{i}", r=random.uniform(0.10, 0.16), segs=10, rings=6,
                          loc=(px, py, pz), mat_=col,
                          scale=(1.7, 0.5, 0.15))
    p_obj.rotation_euler = (random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2))
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_speed"] = random.uniform(0.3, 1.2)
    p_obj["_drift_x"] = random.uniform(-1.8, 1.8)
    p_obj["_drift_y"] = random.uniform(-1.8, 1.8)
    maple_leaves.append(p_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Maples sway
for m in maples:
    phase = m["_phase"]
    for f in range(1, total_frames + 1, 5):
        t_v = (f - 1) / fps
        m.rotation_euler = (math.sin(t_v * 0.8 + phase) * math.radians(2),
                             math.cos(t_v * 0.7 + phase) * math.radians(1.5), 0)
        m.keyframe_insert("rotation_euler", frame=f)

# Bathers relax (subtle head bob)
for b in bathers:
    phase = b["root"]["_phase"]
    base_z = b["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        b["root"].location.z = base_z + math.sin(t * 0.8 + phase) * 0.03
        b["root"].keyframe_insert("location", frame=f)
        b["he"].rotation_euler = (math.sin(t * 0.6 + phase) * math.radians(4), 0,
                                    math.sin(t * 0.5 + phase) * math.radians(8))
        b["he"].keyframe_insert("rotation_euler", frame=f)

# Deer head turn
for d in deer:
    phase = d["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        d["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(8), 0,
                                    math.sin(t * 0.6 + phase) * math.radians(15))
        d["he"].keyframe_insert("rotation_euler", frame=f)

# Monkeys bob heads + arms
for mk in monkeys:
    phase = mk["root"]["_phase"]
    base_z = mk["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        mk["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        mk["root"].keyframe_insert("location", frame=f)
        mk["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(8), 0,
                                     math.sin(t * 0.8 + phase) * math.radians(20))
        mk["he"].keyframe_insert("rotation_euler", frame=f)

# Waterfall water animation
wf_main_obj = bpy.data.objects.get("wf_main")
if wf_main_obj:
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s_z = 1 + math.sin(t * 3.0) * 0.05
        wf_main_obj.scale = (1 + math.sin(t * 4.0) * 0.05, 1, s_z)
        wf_main_obj.keyframe_insert("scale", frame=f)

# Tsukubai water stream
for ws in range(4):
    ws_name = f"tsuk_ws{ws}"
    if ws_name in bpy.data.objects:
        ws_obj = bpy.data.objects[ws_name]
        base_z = ws_obj.location.z
        for f in range(1, total_frames + 1, 4):
            t = (f - 1) / fps
            ws_obj.location.z = (base_z + ws*0.05) - (t * 0.8 + ws*0.2) % 0.95
            ws_obj.keyframe_insert("location", frame=f)

# Lanterns pulse
for l in lanterns:
    phase = l["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 1.5 + phase) * 0.05
        l.scale = (s, s, s)
        l.keyframe_insert("scale", frame=f)

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
# ⭐⭐⭐ 600 STEAM rising spiral + 400 MAPLE LEAVES tombent
# ============================================================
for s in steam_particles:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay = s["_amp_x"], s["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Rising spiral
        z = bz + (speed * t) % 10
        # Spiral drift
        x = bx + ax * math.sin(t * 0.5 + phase + z * 0.3)
        y = by + ay * math.cos(t * 0.4 + phase + z * 0.3)
        s.location = (x, y, min(15, z))
        sc = 1 + math.sin(t * 1.5 + phase) * 0.15
        s.scale = (sc * 1.3, sc * 1.3, sc * 0.5)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

# 400 MAPLE LEAVES falling
for p in maple_leaves:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    drift_x = p["_drift_x"]; drift_y = p["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        z = bz - (speed * t * 0.6) % 15
        x = bx + drift_x * math.sin(t * 1.3 + phase) * 0.7
        y = by + drift_y * math.cos(t * 1.1 + phase) * 0.7
        p.location = (x, y, max(0.2, z))
        p.rotation_euler = (phase + t * 1.7, phase + t * 1.5, phase + t * 2.0)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_onsen_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_japanese_onsen_hot_springs] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_japanese_onsen_hot_springs] ONE rocky ground + Mt Fuji + rotenburo stone bath + waterfall + 6 bathers towels + 4 maple trees momiji + 4 stone lanterns + bamboo tsukubai + taiko bridge red + zen pavilion + 2 sika deer + 5 snow monkeys + 600 STEAM + 400 MAPLE LEAVES")
print("⭐ FIXES: 1 ground + 600 steam rising spiral + 400 maple leaves falling (signature onsen autumn mandatory) ⭐")
