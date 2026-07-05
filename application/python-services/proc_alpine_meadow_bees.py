"""
proc_alpine_meadow_bees.py — 216e procédural AuroraIA (80e qualité)
Alpine summer: ONE ground + 600 bees swarming + 200 butterflies + wildflowers + cows + chalet + waterfall + Matterhorn
FIXES : 1 ground propre + 600 bees swarming + 200 butterflies thématique (signature alpine été)
"""
import bpy, bmesh, math, random, os

random.seed(0x0A19216)

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

# Materials — alpine summer noon
M_SKY = mat("sky", (0.50, 0.75, 0.95, 1.0), 0.0, 0.7, emission=(0.45,0.72,0.92), emission_strength=2.0)
M_SUN = mat("sun", (1.0, 0.95, 0.78, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.78), emission_strength=20.0)
M_CLOUD = mat("cloud", (1.0, 1.0, 0.98, 1.0), 0.0, 0.55, emission=(0.95,0.95,0.95), emission_strength=2.5, alpha=0.85)

# Meadow grass + variations
M_GRASS = mat("grass", (0.35, 0.65, 0.25, 1.0), 0.0, 0.80, emission=(0.30,0.58,0.22), emission_strength=0.5)
M_GRASS_BRIGHT = mat("grass_b", (0.50, 0.78, 0.30, 1.0), 0.0, 0.75, emission=(0.45,0.72,0.28), emission_strength=0.7)
M_GRASS_DARK = mat("grass_d", (0.25, 0.45, 0.18, 1.0), 0.0, 0.85, emission=(0.22,0.40,0.16), emission_strength=0.3)
M_ROCK = mat("rock", (0.55, 0.50, 0.45, 1.0), 0.0, 0.85)
M_ROCK_DARK = mat("rock_d", (0.40, 0.36, 0.32, 1.0), 0.0, 0.85)
M_PATH = mat("path", (0.55, 0.42, 0.28, 1.0), 0.0, 0.80, emission=(0.50,0.38,0.25), emission_strength=0.3)

# Matterhorn-like mountains
M_MOUNTAIN = mat("mountain", (0.65, 0.62, 0.58, 1.0), 0.0, 0.80)
M_SNOW = mat("snow", (0.98, 0.98, 1.0, 1.0), 0.0, 0.40, emission=(0.92,0.94,0.98), emission_strength=1.2)
M_PINE = mat("pine", (0.18, 0.38, 0.20, 1.0), 0.0, 0.65, emission=(0.15,0.32,0.18), emission_strength=0.5)

# Wildflowers — varied colors
M_FLOWER_RED = mat("fl_r", (0.95, 0.20, 0.25, 1.0), 0.0, 0.45, emission=(0.90,0.20,0.22), emission_strength=1.5)
M_FLOWER_YELLOW = mat("fl_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.40, emission=(1.0,0.85,0.20), emission_strength=2.0)
M_FLOWER_PURPLE = mat("fl_p", (0.55, 0.30, 0.85, 1.0), 0.0, 0.45, emission=(0.50,0.28,0.78), emission_strength=1.6)
M_FLOWER_PINK = mat("fl_pink", (1.0, 0.55, 0.85, 1.0), 0.0, 0.45, emission=(1.0,0.55,0.85), emission_strength=1.7)
M_FLOWER_WHITE = mat("fl_w", (0.98, 0.95, 0.90, 1.0), 0.0, 0.45, emission=(0.95,0.92,0.88), emission_strength=1.3)
M_FLOWER_BLUE = mat("fl_b", (0.20, 0.50, 0.95, 1.0), 0.0, 0.45, emission=(0.18,0.48,0.90), emission_strength=1.8)
M_FLOWER_ORANGE = mat("fl_o", (1.0, 0.55, 0.10, 1.0), 0.0, 0.45, emission=(1.0,0.55,0.10), emission_strength=2.0)
M_STEM_GREEN = mat("stem", (0.30, 0.55, 0.25, 1.0), 0.0, 0.65)
M_LEAF_GREEN = mat("leaf", (0.25, 0.55, 0.22, 1.0), 0.0, 0.65, emission=(0.20,0.48,0.20), emission_strength=0.4)

# Bee colors (signature pollinator)
M_BEE_YELLOW = mat("bee_y", (1.0, 0.85, 0.15, 1.0), 0.0, 0.40, emission=(1.0,0.85,0.15), emission_strength=2.2)
M_BEE_BLACK = mat("bee_b", (0.08, 0.06, 0.04, 1.0), 0.0, 0.75)
M_BEE_WING = mat("bee_w", (0.95, 0.95, 0.98, 0.55), 0.0, 0.10, emission=(0.85,0.85,0.92), emission_strength=1.0, alpha=0.55)

# Butterfly colors
M_BUTTER_MONARCH = mat("bm", (1.0, 0.45, 0.10, 1.0), 0.0, 0.40, emission=(1.0,0.45,0.10), emission_strength=2.5)
M_BUTTER_BLUE = mat("bb", (0.20, 0.55, 0.95, 1.0), 0.0, 0.40, emission=(0.20,0.55,0.95), emission_strength=2.5)
M_BUTTER_WHITE = mat("bw", (0.98, 0.95, 0.88, 1.0), 0.0, 0.40, emission=(0.95,0.92,0.85), emission_strength=2.0)
M_BUTTER_PINK = mat("bpink", (1.0, 0.55, 0.85, 1.0), 0.0, 0.40, emission=(1.0,0.55,0.85), emission_strength=2.2)
M_BUTTER_BODY = mat("bbody", (0.30, 0.18, 0.10, 1.0), 0.0, 0.65)

# Cows (Swiss style brown/white)
M_COW_BROWN = mat("cow_br", (0.55, 0.30, 0.15, 1.0), 0.0, 0.75, emission=(0.50,0.28,0.13), emission_strength=0.3)
M_COW_WHITE = mat("cow_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.82), emission_strength=0.3)
M_COW_BLACK = mat("cow_bk", (0.10, 0.08, 0.06, 1.0), 0.0, 0.80)
M_COW_PINK = mat("cow_pk", (0.95, 0.65, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.60,0.60), emission_strength=0.3)
M_BELL_GOLD = mat("bell", (0.92, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.88,0.72,0.28), emission_strength=0.7)
M_HORN = mat("horn", (0.85, 0.78, 0.65, 1.0), 0.2, 0.55)

# Chalet
M_WOOD_DARK = mat("wood_d", (0.40, 0.25, 0.15, 1.0), 0.0, 0.70, emission=(0.35,0.22,0.13), emission_strength=0.4)
M_WOOD_LIGHT = mat("wood_l", (0.62, 0.40, 0.22, 1.0), 0.0, 0.70, emission=(0.55,0.36,0.20), emission_strength=0.4)
M_ROOF_RED = mat("roof_r", (0.55, 0.18, 0.15, 1.0), 0.0, 0.65, emission=(0.50,0.18,0.15), emission_strength=0.4)
M_WINDOW = mat("win", (0.85, 0.92, 0.95, 1.0), 0.0, 0.10, emission=(0.78,0.85,0.92), emission_strength=1.5, alpha=0.85)
M_WINDOW_GLOW = mat("win_g", (1.0, 0.85, 0.55, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.55), emission_strength=4.0)
M_CURTAIN = mat("curtain", (0.92, 0.62, 0.30, 1.0), 0.0, 0.55, emission=(0.85,0.58,0.28), emission_strength=0.4)

# Waterfall
M_WATER = mat("water", (0.55, 0.78, 0.92, 0.85), 0.4, 0.15, emission=(0.50,0.72,0.88), emission_strength=1.2, alpha=0.85)
M_WATER_FOAM = mat("foam", (1.0, 1.0, 1.0, 1.0), 0.0, 0.20, emission=(0.95,0.95,0.98), emission_strength=2.5)
M_STREAM = mat("stream", (0.65, 0.85, 0.95, 0.80), 0.4, 0.15, emission=(0.55,0.78,0.92), emission_strength=1.0, alpha=0.80)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=130, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (20, 50, 35))
smooth_sphere("sun", r=5.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=5.0 + (i+1)*1.8, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

# 8 fluffy alpine cumulus clouds
clouds = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = random.uniform(28, 40)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(22, 32)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(6):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ MATTERHORN-LIKE BACKGROUND PEAKS ============
mountain_e = empty("mountains", loc=(0, 40, 4))
# Main central Matterhorn peak (signature pyramid shape)
matterhorn = smooth_cone("matterhorn", r1=14, r2=0.5, depth=18, segs=8,
                          loc=(0, 0, 0), parent=mountain_e, mat_=M_MOUNTAIN)
matterhorn.rotation_euler = (math.radians(8), 0, math.radians(15))
# Snow cap on Matterhorn
smooth_cone("matterhorn_snow", r1=3.5, r2=0.4, depth=4, segs=10,
            loc=(0, 0, 7.5), parent=mountain_e, mat_=M_SNOW)
# Side peaks
for side, side_mul in zip(("L", "R"), (-1, 1)):
    smooth_cone(f"peak_{side}", r1=10, r2=1.0, depth=10, segs=20,
                loc=(side_mul*16, -3, -3), parent=mountain_e, mat_=M_MOUNTAIN)
    smooth_cone(f"peak_snow_{side}", r1=3.0, r2=0.8, depth=2.5, segs=20,
                loc=(side_mul*16, -3, 3), parent=mountain_e, mat_=M_SNOW)
    smooth_cone(f"peak_far_{side}", r1=12, r2=2, depth=9, segs=18,
                loc=(side_mul*25, -1, -3), parent=mountain_e, mat_=M_MOUNTAIN)
    smooth_cone(f"peak_far_snow_{side}", r1=4.0, r2=1.5, depth=2.0, segs=16,
                loc=(side_mul*25, -1, 2.5), parent=mountain_e, mat_=M_SNOW)

# Pine trees on lower mountain slopes
for i in range(15):
    a = random.uniform(-math.pi*0.6, math.pi*0.6)
    rad = random.uniform(18, 30)
    px = rad * math.cos(a) * (1 if random.random() > 0.5 else -1)
    py = 25 + random.uniform(-3, 5)
    pz = random.uniform(-1.5, 1.0)
    # Triangle pine (3 cone layers tapered)
    pine_e = empty(f"pine{i}", (px, py, pz))
    cyl(f"pine_trunk{i}", r=0.20, depth=1.0, segs=12,
        loc=(0, 0, 0.5), parent=pine_e, mat_=M_WOOD_DARK)
    for layer in range(3):
        r1 = 1.5 - layer*0.4
        smooth_cone(f"pine_l{i}_{layer}", r1=r1, r2=r1*0.1, depth=1.8, segs=16,
                    loc=(0, 0, 1.5 + layer*1.1), parent=pine_e, mat_=M_PINE)

# ============ ONE clean alpine meadow ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GRASS)

# Bright grass tufts (organic patches)
for i in range(40):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 38)
    smooth_sphere(f"grass_tuft{i}", r=random.uniform(0.30, 0.60),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.18),
                  mat_=M_GRASS_BRIGHT if i % 2 == 0 else M_GRASS_DARK,
                  scale=(1.4, 1.2, 0.25))

# Stone path winding
for i in range(25):
    px = (i - 12) * 1.5
    py = math.sin(i * 0.4) * 2.5 - 4
    smooth_sphere(f"path_stone{i}", r=random.uniform(0.40, 0.65), segs=14, rings=10,
                  loc=(px, py, 0.10), mat_=M_PATH,
                  scale=(1.3, 1.0, 0.28))

# 25 alpine rocks (organic 3D)
for i in range(25):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(12, 35)
    smooth_sphere(f"rock{i}", r=random.uniform(0.4, 1.1),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_ROCK if i % 2 == 0 else M_ROCK_DARK,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.8)))

# ============ 150 WILDFLOWERS scattered ============
flower_colors = [M_FLOWER_RED, M_FLOWER_YELLOW, M_FLOWER_PURPLE, M_FLOWER_PINK,
                 M_FLOWER_WHITE, M_FLOWER_BLUE, M_FLOWER_ORANGE]
flowers = []
for i in range(150):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 35)
    fx = rad * math.cos(a)
    fy = rad * math.sin(a)
    f_e = empty(f"flower{i}", (fx, fy, 0))
    # Stem
    cyl(f"flower_stem{i}", r=0.025, depth=0.5, segs=8,
        loc=(0, 0, 0.25), parent=f_e, mat_=M_STEM_GREEN)
    # 2 leaves
    for side in (-1, 1):
        beveled_cube(f"flower_leaf{i}_{side}", (0.04, 0.10, 0.02), bevel_offset=0.01,
                     loc=(side*0.05, 0, 0.15), parent=f_e, mat_=M_LEAF_GREEN)
    # Flower head (multiple petals)
    color = flower_colors[i % len(flower_colors)]
    if i % 7 == 0:  # Sunflower-style yellow large
        # Center
        smooth_sphere(f"flower_c{i}", r=0.10, loc=(0, 0, 0.55),
                      parent=f_e, mat_=mat(f"flc_m{i}", (0.55, 0.30, 0.10, 1), 0, 0.7),
                      scale=(1, 1, 0.5))
        # 8 petals around
        for p in range(8):
            pa = (p / 8.0) * math.pi * 2
            petal = beveled_cube(f"flower_p{i}_{p}", (0.06, 0.12, 0.025), bevel_offset=0.01,
                                 loc=(0.15*math.cos(pa), 0.15*math.sin(pa), 0.55),
                                 parent=f_e, mat_=color)
            petal.rotation_euler = (0, 0, pa)
    else:
        # Standard flower 5 petal cluster
        for p in range(5):
            pa = (p / 5.0) * math.pi * 2
            smooth_sphere(f"flower_p{i}_{p}", r=0.05,
                          loc=(0.06*math.cos(pa), 0.06*math.sin(pa), 0.55),
                          parent=f_e, mat_=color, scale=(1, 1, 0.6))
        # Center
        smooth_sphere(f"flower_c{i}", r=0.03, loc=(0, 0, 0.58),
                      parent=f_e, mat_=M_FLOWER_YELLOW)
    f_e["_phase"] = random.uniform(0, math.pi*2)
    flowers.append(f_e)

# ============ WATERFALL + STREAM ============
waterfall_e = empty("waterfall", loc=(-22, 30, 0))
# Rock cliff base
for i in range(5):
    smooth_sphere(f"wf_cliff{i}", r=random.uniform(1.5, 2.5),
                  loc=(random.uniform(-2, 2), random.uniform(-2, 2),
                       2 + i*1.5),
                  parent=waterfall_e, mat_=M_ROCK, scale=(1.2, 1.0, 1.2))
# Falling water column (signature)
water_e = empty("water_fall", (0, -1, 0), parent=waterfall_e)
beveled_cube("wf_main", (1.8, 0.6, 8), bevel_offset=0.05,
             loc=(0, 0, 5), parent=water_e, mat_=M_WATER)
# Foam at top
smooth_sphere("wf_top", r=1.2, loc=(0, 0, 9.5),
              parent=water_e, mat_=M_WATER_FOAM, scale=(1.4, 1, 0.6))
# Splash at base
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    smooth_sphere(f"wf_splash{i}", r=random.uniform(0.35, 0.55),
                  loc=(math.cos(a)*1.2, math.sin(a)*1.2, 0.5),
                  parent=water_e, mat_=M_WATER_FOAM)
# Stream flowing down meadow
stream_e = empty("stream", loc=(-15, 25, 0))
for i in range(30):
    sx = -i * 1.2
    sy = math.sin(i * 0.3) * 1.5
    sz = 0.05
    beveled_cube(f"stream_seg{i}", (1.4, 0.6, 0.10), bevel_offset=0.03,
                 loc=(sx, sy, sz), parent=stream_e, mat_=M_STREAM)
    # Foam patches
    if i % 5 == 0:
        smooth_sphere(f"stream_foam{i}", r=0.18,
                      loc=(sx, sy, 0.10), parent=stream_e, mat_=M_WATER_FOAM,
                      scale=(1, 1, 0.4))

# ============ SWISS CHALET ============
chalet_e = empty("chalet", loc=(18, 18, 0))
chalet_e.rotation_euler = (0, 0, math.radians(-35))
# Stone foundation
beveled_cube("ch_found", (5, 4, 0.6), bevel_offset=0.06,
             loc=(0, 0, 0.30), parent=chalet_e, mat_=M_ROCK)
# Main body wood logs
beveled_cube("ch_body", (4.8, 3.8, 3.0), bevel_offset=0.06,
             loc=(0, 0, 2.1), parent=chalet_e, mat_=M_WOOD_LIGHT)
# Horizontal log details (signature chalet)
for i in range(5):
    cyl(f"ch_log{i}", r=0.10, depth=4.8, segs=12,
        loc=(0, -1.95, 0.8 + i*0.55), parent=chalet_e, mat_=M_WOOD_DARK).rotation_euler = (0, math.radians(90), 0)
    cyl(f"ch_log_b{i}", r=0.10, depth=4.8, segs=12,
        loc=(0, 1.95, 0.8 + i*0.55), parent=chalet_e, mat_=M_WOOD_DARK).rotation_euler = (0, math.radians(90), 0)
# Roof (steep alpine pitch)
roof_e = empty("ch_roof_e", (0, 0, 3.8), parent=chalet_e)
for side, side_mul in zip(("L", "R"), (-1, 1)):
    roof = beveled_cube(f"ch_roof_{side}", (5.5, 4.5, 0.30), bevel_offset=0.04,
                       loc=(0, side_mul*1.2, 0.8), parent=roof_e, mat_=M_ROOF_RED)
    roof.rotation_euler = (math.radians(side_mul*-45), 0, 0)
# Roof ridge
beveled_cube("ch_ridge", (5.5, 0.3, 0.20), bevel_offset=0.03,
             loc=(0, 0, 2.0), parent=roof_e, mat_=M_WOOD_DARK)
# Chimney
beveled_cube("ch_chimney", (0.50, 0.50, 1.5), bevel_offset=0.04,
             loc=(1.5, 0.4, 5.0), parent=chalet_e, mat_=M_ROCK_DARK)
# Smoke from chimney
for i in range(4):
    smooth_sphere(f"ch_smoke{i}", r=0.30 + i*0.10,
                  loc=(1.5 + math.sin(i)*0.3, 0.4, 6.2 + i*0.6),
                  parent=chalet_e,
                  mat_=mat(f"smoke_m{i}", (0.85, 0.82, 0.78, 1.0), 0, 0.65,
                            emission=(0.80,0.78,0.75), emission_strength=0.8, alpha=0.65))
# 2 windows with glow + curtains
for side in (-1, 1):
    beveled_cube(f"ch_win_{side}", (0.80, 0.10, 0.80), bevel_offset=0.03,
                 loc=(side*1.5, -1.92, 2.4), parent=chalet_e, mat_=M_WINDOW_GLOW)
    # Window frame
    for fi in range(2):
        beveled_cube(f"ch_win_fr_h_{side}_{fi}", (0.85, 0.05, 0.05),
                     loc=(side*1.5, -1.95, 2.0 + fi*0.80), parent=chalet_e, mat_=M_WOOD_DARK)
        beveled_cube(f"ch_win_fr_v_{side}_{fi}", (0.05, 0.05, 0.85),
                     loc=(side*1.5 + (fi-0.5)*0.80, -1.95, 2.4), parent=chalet_e, mat_=M_WOOD_DARK)
    # Curtains
    beveled_cube(f"ch_curtain_{side}", (0.30, 0.06, 0.70),
                 loc=(side*(1.5 - 0.35), -1.93, 2.4), parent=chalet_e, mat_=M_CURTAIN)
# Door
beveled_cube("ch_door", (0.80, 0.10, 1.6), bevel_offset=0.03,
             loc=(0, -1.92, 1.55), parent=chalet_e, mat_=M_WOOD_DARK)
# Door knob
smooth_sphere("ch_knob", r=0.06, loc=(0.30, -1.96, 1.55), parent=chalet_e, mat_=M_BELL_GOLD)
# Geranium flower boxes under windows (signature alpine)
for side in (-1, 1):
    beveled_cube(f"ch_box_{side}", (0.95, 0.25, 0.20), bevel_offset=0.03,
                 loc=(side*1.5, -2.10, 1.95), parent=chalet_e, mat_=M_WOOD_DARK)
    # Geraniums (red)
    for ge in range(5):
        smooth_sphere(f"ch_ger_{side}_{ge}", r=0.10,
                      loc=(side*1.5 + (ge-2)*0.18, -2.15, 2.10),
                      parent=chalet_e, mat_=M_FLOWER_RED)

# ============ 4 SWISS COWS in pasture ============
def make_cow(name, loc, color_body=M_COW_BROWN, facing=0, action="graze"):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.65, segs=22, rings=14, loc=(0, 0, 1.20),
                  parent=base, mat_=color_body, scale=(1.8, 1.0, 1.0))
    # White spots on brown body (Swiss style)
    for sp in range(4):
        smooth_sphere(f"{name}_spot{sp}", r=0.25,
                      loc=(random.uniform(-0.6, 0.6), random.uniform(-0.4, 0.4),
                           1.20 + random.uniform(-0.2, 0.3)),
                      parent=base, mat_=M_COW_WHITE,
                      scale=(1, 1, 0.35))
    # Neck
    neck = beveled_cube(f"{name}_neck", (0.40, 0.35, 0.55), bevel_offset=0.05,
                       loc=(0.85, 0, 1.35), parent=base, mat_=color_body)
    neck.rotation_euler = (0, math.radians(-15), 0)
    # Head
    head_e = empty(f"{name}_he", (1.25, 0, 1.55), parent=base)
    if action == "graze":
        head_e.rotation_euler = (0, math.radians(60), 0)
    beveled_cube(f"{name}_head", (0.55, 0.30, 0.35), bevel_offset=0.05,
                 loc=(0, 0, 0), parent=head_e, mat_=color_body)
    # Muzzle (pink nose)
    smooth_sphere(f"{name}_muzzle", r=0.14,
                  loc=(0.30, 0, -0.08), parent=head_e, mat_=M_COW_PINK,
                  scale=(1, 1, 0.7))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.05,
                      loc=(0.10, side*0.16, 0.10), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Horns
    for side in (-1, 1):
        horn = smooth_cone(f"{name}_horn{side}", r1=0.05, r2=0.015, depth=0.25, segs=10,
                           loc=(-0.10, side*0.18, 0.22), parent=head_e, mat_=M_HORN)
        horn.rotation_euler = (math.radians(-30), 0, math.radians(side*30))
    # Ears
    for side in (-1, 1):
        ear = beveled_cube(f"{name}_ear{side}", (0.08, 0.18, 0.04),
                          loc=(-0.05, side*0.25, 0.20), parent=head_e, mat_=color_body)
        ear.rotation_euler = (0, 0, math.radians(side*30))
    # Cowbell (signature swiss)
    bell_e = empty(f"{name}_bell_e", (0.85, 0, 0.95), parent=base)
    cyl(f"{name}_collar", r=0.42, depth=0.12, segs=18,
        loc=(0, 0, 0), parent=bell_e, mat_=M_WOOD_DARK)
    smooth_sphere(f"{name}_bell", r=0.18,
                  loc=(0, -0.35, -0.20), parent=bell_e, mat_=M_BELL_GOLD,
                  scale=(1, 0.7, 1.2))
    # 4 legs
    for x_idx, x in enumerate((0.50, -0.50)):
        for y_idx, y in enumerate((-0.35, 0.35)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.12, depth=0.85, segs=10,
                loc=(x, y, 0.42), parent=base, mat_=color_body)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.13, depth=0.10, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_COW_BLACK)
    # Udder (back)
    smooth_sphere(f"{name}_udder", r=0.20, loc=(-0.40, 0, 0.75),
                  parent=base, mat_=M_COW_PINK, scale=(1, 0.9, 0.8))
    # Tail
    tail = beveled_cube(f"{name}_tail", (0.08, 0.08, 0.70),
                       loc=(-0.85, 0, 1.30), parent=base, mat_=color_body)
    tail.rotation_euler = (math.radians(-15), math.radians(30), 0)
    # Tail tuft (white)
    smooth_sphere(f"{name}_tail_tuft", r=0.10, loc=(-1.20, 0, 0.95),
                  parent=base, mat_=M_COW_WHITE)
    base["_phase"] = random.uniform(0, math.pi*2)
    base["_action"] = action
    return {"root": base, "head_e": head_e, "bell": bell_e}

cows = []
cow_specs = [
    ("cow1", (-3, 0, 0), M_COW_BROWN, math.radians(45), "graze"),
    ("cow2", (4, 2, 0), M_COW_BROWN, math.radians(-30), "stand"),
    ("cow3", (8, -5, 0), M_COW_BROWN, math.radians(120), "graze"),
    ("cow4", (-8, 5, 0), M_COW_BROWN, math.radians(-60), "graze"),
]
for spec in cow_specs:
    name, loc, col, fac, act = spec
    c = make_cow(name, loc, color_body=col, facing=fac, action=act)
    cows.append(c)

# ============================================================
# ⭐ 600 BEES SWARMING + 200 BUTTERFLIES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# Bees — small striped yellow-black bodies + wings
bees = []
for i in range(600):
    px = random.uniform(-35, 35)
    py = random.uniform(-35, 35)
    pz = random.uniform(0.5, 6)
    bee_e = empty(f"bee{i}", (px, py, pz))
    # Body (yellow with black stripes)
    smooth_sphere(f"bee_body{i}", r=0.10, segs=10, rings=6, loc=(0, 0, 0),
                  parent=bee_e, mat_=M_BEE_YELLOW, scale=(1.4, 1, 1))
    # 2 black stripes
    for s in range(2):
        cyl(f"bee_str{i}_{s}", r=0.10, depth=0.04, segs=10,
            loc=((s-0.5)*0.10, 0, 0), parent=bee_e, mat_=M_BEE_BLACK)
        # rotate stripe to be perpendicular to body axis
        bpy.data.objects[f"bee_str{i}_{s}"].rotation_euler = (0, math.radians(90), 0)
    # Head
    smooth_sphere(f"bee_head{i}", r=0.07, loc=(0.15, 0, 0),
                  parent=bee_e, mat_=M_BEE_BLACK)
    # 2 wings (translucent)
    for side in (-1, 1):
        beveled_cube(f"bee_w{i}_{side}", (0.04, 0.12, 0.01), bevel_offset=0.005,
                     loc=(-0.02, side*0.08, 0.04), parent=bee_e, mat_=M_BEE_WING)
    bee_e["_phase"] = random.uniform(0, math.pi*2)
    bee_e["_base_x"] = px; bee_e["_base_y"] = py; bee_e["_base_z"] = pz
    bee_e["_amp_x"] = random.uniform(1.5, 3.0)
    bee_e["_amp_y"] = random.uniform(1.5, 3.0)
    bee_e["_amp_z"] = random.uniform(0.4, 1.2)
    bee_e["_speed"] = random.uniform(1.0, 2.0)
    bees.append(bee_e)

# Butterflies — bigger wings, varied colors
butterflies = []
butter_mats = [M_BUTTER_MONARCH, M_BUTTER_BLUE, M_BUTTER_WHITE, M_BUTTER_PINK]
for i in range(200):
    px = random.uniform(-30, 30)
    py = random.uniform(-30, 30)
    pz = random.uniform(0.5, 5)
    bf_e = empty(f"bf{i}", (px, py, pz))
    # Body
    cyl(f"bf_body{i}", r=0.04, depth=0.20, segs=8,
        loc=(0, 0, 0), parent=bf_e, mat_=M_BUTTER_BODY)
    color = butter_mats[i % 4]
    # 4 wings (2 left + 2 right, upper + lower)
    wings = []
    for side in (-1, 1):
        # Upper wing
        w_u_e = empty(f"bf_wue{i}_{side}", (0, 0, 0), parent=bf_e)
        beveled_cube(f"bf_w_u{i}_{side}", (0.05, 0.18, 0.01), bevel_offset=0.005,
                     loc=(0, side*0.13, 0.05), parent=w_u_e, mat_=color)
        # Lower wing
        beveled_cube(f"bf_w_l{i}_{side}", (0.04, 0.14, 0.01), bevel_offset=0.005,
                     loc=(0, side*0.10, -0.05), parent=w_u_e, mat_=color)
        wings.append((w_u_e, side))
    bf_e["_phase"] = random.uniform(0, math.pi*2)
    bf_e["_base_x"] = px; bf_e["_base_y"] = py; bf_e["_base_z"] = pz
    bf_e["_amp_x"] = random.uniform(2.0, 4.0)
    bf_e["_amp_y"] = random.uniform(2.0, 4.0)
    bf_e["_amp_z"] = random.uniform(0.8, 2.0)
    bf_e["_speed"] = random.uniform(0.7, 1.5)
    butterflies.append({"e": bf_e, "wings": wings})

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Flowers sway gentle
for fl in flowers:
    phase = fl["_phase"]
    for f in range(1, total_frames + 1, 6):
        t_v = (f - 1) / fps
        fl.rotation_euler = (math.sin(t_v * 1.2 + phase) * math.radians(5),
                              math.cos(t_v * 1.0 + phase) * math.radians(4),
                              0)
        fl.keyframe_insert("rotation_euler", frame=f)

# Cows animate
for c in cows:
    phase = c["root"]["_phase"]
    action = c["root"]["_action"]
    base_z = c["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Body subtle bob
        c["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.03
        c["root"].keyframe_insert("location", frame=f)
        # Head movement (graze cycle)
        if action == "graze":
            head_rx = math.radians(60) + math.sin(t * 0.8 + phase) * math.radians(20)
            head_rz = math.sin(t * 0.5 + phase) * math.radians(20)
            c["head_e"].rotation_euler = (0, head_rx, head_rz)
        else:
            c["head_e"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(8), 0,
                                           math.sin(t * 0.7 + phase) * math.radians(20))
        c["head_e"].keyframe_insert("rotation_euler", frame=f)
        # Bell swing
        c["bell"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(15),
                                     math.cos(t * 2.0 + phase) * math.radians(10), 0)
        c["bell"].keyframe_insert("rotation_euler", frame=f)

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

# Sun halos pulse
for obj in bpy.data.objects:
    if obj.name.startswith("sun_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.8) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# Waterfall falling water animation (translate down + foam pulse)
water_main = bpy.data.objects["wf_main"]
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    # Water column scale-Y to simulate flow
    s_z = 1 + math.sin(t * 2.5) * 0.04
    water_main.scale = (1 + math.sin(t * 3.0) * 0.05, 1, s_z)
    water_main.keyframe_insert("scale", frame=f)
# Foam splash pulse
for obj in bpy.data.objects:
    if obj.name.startswith("wf_splash"):
        for f in range(1, total_frames + 1, 4):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 4.0 + hash(obj.name) % 100 * 0.05) * 0.20
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# Stream flow scale shimmer
for obj in bpy.data.objects:
    if obj.name.startswith("stream_seg"):
        phase = hash(obj.name) % 100 * 0.05
        for f in range(1, total_frames + 1, 5):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 3.0 + phase) * 0.05
            obj.scale = (s, 1, 1)
            obj.keyframe_insert("scale", frame=f)

# Smoke from chimney rise
for sm_idx in range(4):
    smoke_name = f"ch_smoke{sm_idx}"
    if smoke_name in bpy.data.objects:
        smoke = bpy.data.objects[smoke_name]
        base_z_smoke = smoke.location.z
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            smoke.location.z = base_z_smoke + math.sin(t * 0.8 + sm_idx) * 0.4
            smoke.scale = (1 + math.sin(t * 1.5) * 0.1, 1 + math.cos(t * 1.5) * 0.1, 1)
            smoke.keyframe_insert("location", frame=f)
            smoke.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 600 BEES SWARMING (signature pollinators alpine)
# ============================================================
for bee in bees:
    phase = bee["_phase"]; speed = bee["_speed"]
    bx, by, bz = bee["_base_x"], bee["_base_y"], bee["_base_z"]
    ax, ay, az = bee["_amp_x"], bee["_amp_y"], bee["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Erratic swarm pattern (fast multi-freq)
        x = bx + ax * math.sin(t * speed + phase) + 0.3*math.sin(t * speed * 3.5 + phase * 2)
        y = by + ay * math.cos(t * speed * 0.9 + phase) + 0.3*math.cos(t * speed * 3.2 + phase)
        z = bz + az * math.sin(t * speed * 1.4 + phase * 1.7) + 0.2*math.sin(t * 6.0 + phase)
        bee.location = (x, y, max(0.2, z))
        bee.rotation_euler = (0, 0, math.atan2(math.cos(t * speed * 0.9 + phase),
                                                math.sin(t * speed + phase)))
        bee.keyframe_insert("location", frame=f)
        bee.keyframe_insert("rotation_euler", frame=f)

# ============================================================
# ⭐⭐⭐ 200 BUTTERFLIES floating + wing flap (signature alpine summer)
# ============================================================
for bf in butterflies:
    e = bf["e"]
    phase = e["_phase"]; speed = e["_speed"]
    bx, by, bz = e["_base_x"], e["_base_y"], e["_base_z"]
    ax, ay, az = e["_amp_x"], e["_amp_y"], e["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Floating drift (slower than bees, graceful)
        x = bx + ax * math.sin(t * speed * 0.5 + phase)
        y = by + ay * math.cos(t * speed * 0.4 + phase)
        z = bz + az * math.sin(t * speed * 0.8 + phase * 1.3)
        e.location = (x, y, max(0.3, z))
        e.rotation_euler = (math.sin(t * speed * 0.4 + phase) * 0.3,
                            0,
                            math.atan2(math.cos(t * speed * 0.4 + phase),
                                       math.sin(t * speed * 0.5 + phase)))
        e.keyframe_insert("location", frame=f)
        e.keyframe_insert("rotation_euler", frame=f)
        # Wing flap (fast)
        flap = math.sin(t * 12.0 + phase) * math.radians(50)
        for w_e, side in bf["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_alpine_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_alpine_meadow_bees] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_alpine_meadow_bees] ONE ground + Matterhorn + 15 pines + chalet + waterfall + stream + 4 cows + 150 flowers + 600 BEES + 200 BUTTERFLIES")
print("⭐ FIXES: 1 ground + 600 bees swarming + 200 butterflies flap (signature alpine summer mandatory) ⭐")
