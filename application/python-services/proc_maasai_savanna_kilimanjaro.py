"""
proc_maasai_savanna_kilimanjaro.py — 227e procédural AuroraIA (91e qualité)
Maasai savanna: ONE ground + Kilimanjaro + 4 acacia + 8 Maasai warriors + elder + 4 women + Manyatta village + 10 zebu + 6 giraffes + 4 zebras + 2 elephants + 3 lions + 5 gazelles + 600 dust + 400 flies
FIXES : 1 ground + 600 dust + 400 flies signature savane
"""
import bpy, bmesh, math, random, os

random.seed(0x5A4A227)

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

# Savana sunset palette
M_SKY = mat("sky", (1.0, 0.62, 0.30, 1.0), 0.0, 0.7, emission=(0.95,0.58,0.28), emission_strength=3.0)
M_SUN = mat("sun", (1.0, 0.55, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.55,0.20), emission_strength=20.0)
M_CLOUD = mat("cloud", (1.0, 0.62, 0.45, 1.0), 0.0, 0.55, emission=(0.95,0.58,0.42), emission_strength=2.0, alpha=0.85)

# Ground savanna grass
M_GRASS_S = mat("grass_s", (0.75, 0.62, 0.30, 1.0), 0.0, 0.85, emission=(0.70,0.58,0.28), emission_strength=0.5)
M_GRASS_DRY = mat("grass_d", (0.85, 0.72, 0.40, 1.0), 0.0, 0.80, emission=(0.78,0.68,0.38), emission_strength=0.5)
M_EARTH_OCHRE = mat("earth_o", (0.65, 0.42, 0.22, 1.0), 0.0, 0.85, emission=(0.60,0.40,0.20), emission_strength=0.4)
M_ROCK_SAV = mat("rock_s", (0.55, 0.45, 0.32, 1.0), 0.0, 0.85)
M_TUFT = mat("tuft", (0.85, 0.78, 0.50, 1.0), 0.0, 0.80, emission=(0.80,0.72,0.48), emission_strength=0.5)

# Kilimanjaro
M_MOUNTAIN = mat("mountain", (0.45, 0.42, 0.50, 1.0), 0.0, 0.80)
M_MOUNTAIN_SNOW = mat("ms", (0.98, 0.98, 1.0, 1.0), 0.0, 0.45, emission=(0.92,0.94,0.98), emission_strength=1.2)

# Acacia trees (signature flat-top)
M_ACACIA_TRUNK = mat("ac_t", (0.45, 0.32, 0.20, 1.0), 0.0, 0.80, emission=(0.40,0.30,0.18), emission_strength=0.3)
M_ACACIA_LEAF = mat("ac_l", (0.40, 0.55, 0.25, 1.0), 0.0, 0.65, emission=(0.35,0.50,0.22), emission_strength=0.5)
M_ACACIA_LEAF_DARK = mat("ac_ld", (0.28, 0.42, 0.18, 1.0), 0.0, 0.65, emission=(0.25,0.38,0.16), emission_strength=0.4)

# Maasai
M_SKIN_DARK = mat("skin_d", (0.55, 0.35, 0.22, 1.0), 0.0, 0.55, emission=(0.50,0.32,0.20), emission_strength=0.4)
M_SHUKA_RED = mat("shuka_r", (0.85, 0.18, 0.18, 1.0), 0.0, 0.60, emission=(0.78,0.18,0.18), emission_strength=0.8)
M_SHUKA_BLUE = mat("shuka_b", (0.30, 0.55, 0.75, 1.0), 0.0, 0.60, emission=(0.28,0.50,0.70), emission_strength=0.7)
M_SHUKA_PURPLE = mat("shuka_pu", (0.65, 0.30, 0.65, 1.0), 0.0, 0.60, emission=(0.60,0.28,0.60), emission_strength=0.7)
M_BEAD_RED = mat("bead_r", (1.0, 0.15, 0.15, 1.0), 0.0, 0.30, emission=(0.95,0.15,0.15), emission_strength=2.0)
M_BEAD_BLUE = mat("bead_b", (0.20, 0.55, 1.0, 1.0), 0.0, 0.30, emission=(0.20,0.55,1.0), emission_strength=2.0)
M_BEAD_WHITE = mat("bead_w", (1.0, 0.92, 0.85, 1.0), 0.0, 0.30, emission=(0.95,0.88,0.82), emission_strength=1.2)
M_BEAD_GREEN = mat("bead_g", (0.30, 1.0, 0.30, 1.0), 0.0, 0.30, emission=(0.30,1.0,0.30), emission_strength=1.8)
M_BEAD_YELLOW = mat("bead_y", (1.0, 0.92, 0.30, 1.0), 0.0, 0.30, emission=(1.0,0.92,0.30), emission_strength=2.2)
M_HAIR_BRAID = mat("hair_br", (0.55, 0.30, 0.15, 1.0), 0.0, 0.80)
M_SPEAR_WOOD = mat("sp_w", (0.40, 0.25, 0.15, 1.0), 0.0, 0.80)
M_SPEAR_TIP = mat("sp_t", (0.75, 0.70, 0.55, 1.0), 0.85, 0.20, emission=(0.70,0.65,0.50), emission_strength=0.5)
M_SHIELD_HIDE = mat("sh_h", (0.55, 0.32, 0.18, 1.0), 0.0, 0.75)
M_SHIELD_PATTERN = mat("sh_p", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.78), emission_strength=0.5)

# Manyatta (mud huts)
M_MUD = mat("mud", (0.55, 0.35, 0.22, 1.0), 0.0, 0.85, emission=(0.50,0.32,0.20), emission_strength=0.4)
M_STRAW_ROOF = mat("straw", (0.75, 0.55, 0.30, 1.0), 0.0, 0.85, emission=(0.70,0.52,0.28), emission_strength=0.4)
M_DUNG_DARK = mat("dung", (0.35, 0.22, 0.12, 1.0), 0.0, 0.85)

# Zebu cattle
M_ZEBU_BROWN = mat("zebu", (0.62, 0.42, 0.25, 1.0), 0.0, 0.75)
M_ZEBU_WHITE = mat("zebu_w", (0.92, 0.85, 0.75, 1.0), 0.0, 0.70)
M_HORN_ZEBU = mat("horn", (0.85, 0.78, 0.65, 1.0), 0.2, 0.55)

# Giraffes
M_GIRAFFE_TAN = mat("gir", (0.95, 0.78, 0.40, 1.0), 0.0, 0.75, emission=(0.88,0.72,0.38), emission_strength=0.5)
M_GIRAFFE_SPOT = mat("gir_s", (0.55, 0.32, 0.12, 1.0), 0.0, 0.80)

# Zebras
M_ZEBRA_WHITE = mat("zeb_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.70, emission=(0.88,0.85,0.78), emission_strength=0.4)
M_ZEBRA_BLACK = mat("zeb_b", (0.10, 0.08, 0.08, 1.0), 0.0, 0.80)

# Elephants
M_ELEPHANT = mat("ele", (0.55, 0.55, 0.55, 1.0), 0.0, 0.80, emission=(0.50,0.50,0.50), emission_strength=0.3)
M_TUSK = mat("tusk", (0.95, 0.92, 0.85, 1.0), 0.3, 0.40, emission=(0.88,0.85,0.78), emission_strength=0.5)
M_EYE_BEAST = mat("eye_b", (0.18, 0.10, 0.05, 1.0), 0.0, 0.40, emission=(0.15,0.08,0.05), emission_strength=0.5)

# Lions
M_LION_BODY = mat("lion_b", (0.85, 0.65, 0.30, 1.0), 0.0, 0.65, emission=(0.78,0.60,0.28), emission_strength=0.4)
M_LION_MANE = mat("lion_m", (0.55, 0.32, 0.12, 1.0), 0.0, 0.85)

# Gazelles
M_GAZELLE = mat("gaz", (0.85, 0.62, 0.30, 1.0), 0.0, 0.70, emission=(0.78,0.58,0.28), emission_strength=0.4)
M_GAZELLE_BELLY = mat("gaz_b", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65)
M_HORN_GAZ = mat("horn_g", (0.20, 0.12, 0.08, 1.0), 0.0, 0.65)

# Particles (signature dust + flies)
M_DUST_OCHRE = mat("dust", (0.85, 0.62, 0.30, 1.0), 0.0, 0.55, emission=(0.78,0.58,0.28), emission_strength=2.5, alpha=0.65)
M_DUST_DARK = mat("dust_d", (0.65, 0.45, 0.22, 1.0), 0.0, 0.65, emission=(0.60,0.42,0.20), emission_strength=2.2, alpha=0.65)
M_FLY = mat("fly", (0.15, 0.12, 0.10, 1.0), 0.0, 0.55, emission=(0.30,0.25,0.20), emission_strength=2.0)
M_FLY_WING = mat("fly_w", (0.55, 0.55, 0.65, 0.55), 0.0, 0.20, emission=(0.50,0.50,0.60), emission_strength=1.0, alpha=0.55)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (35, 0, 12))
smooth_sphere("sun", r=6.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=6.0 + (i+1)*2.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

# Clouds
clouds = []
for i in range(7):
    a = (i / 7.0) * math.pi * 2
    rad = random.uniform(30, 45)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(20, 28)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ MT KILIMANJARO (signature flat-top with snow cap) ============
kili_e = empty("kili", loc=(0, 40, 5))
# Main flat-top mountain (signature Kilimanjaro shape)
kili_main = smooth_cone("kili_main", r1=20, r2=8, depth=14, segs=24,
                         loc=(0, 0, 0), parent=kili_e, mat_=M_MOUNTAIN)
# Snow cap (flat top)
cyl("kili_cap", r=8.5, depth=2.0, segs=24, loc=(0, 0, 7.5),
    parent=kili_e, mat_=M_MOUNTAIN_SNOW)
# Side smaller peak (Mawenzi - signature)
mawenzi = smooth_cone("mawenzi", r1=8, r2=2, depth=8, segs=16,
                       loc=(15, -3, -3), parent=kili_e, mat_=M_MOUNTAIN)
mawenzi.rotation_euler = (math.radians(5), 0, math.radians(15))
# Small Mawenzi snow
smooth_cone("mawenzi_snow", r1=2.5, r2=0.8, depth=2.0, segs=14,
            loc=(15, -3, 1.8), parent=kili_e, mat_=M_MOUNTAIN_SNOW)

# ============ ONE clean savanna ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GRASS_S)

# Grass tufts (organic 3D)
for i in range(80):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 42)
    smooth_sphere(f"tuft{i}", r=random.uniform(0.25, 0.50),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_TUFT if i % 2 == 0 else M_GRASS_DRY,
                  scale=(1.5, 1.3, 0.20))

# Earth patches
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 35)
    smooth_sphere(f"earth_p{i}", r=random.uniform(0.50, 1.0),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_EARTH_OCHRE, scale=(1.8, 1.4, 0.18))

# Rocks scattered
for i in range(25):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(12, 40)
    smooth_sphere(f"rock{i}", r=random.uniform(0.4, 1.0),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.35),
                  mat_=M_ROCK_SAV,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.85)))

# ============ 4 ACACIAS (signature flat-top) ============
def make_acacia(name, loc, scale=1.0):
    base = empty(name, loc)
    # Trunk (twisted)
    for s in range(5):
        seg = smooth_cone(f"{name}_t{s}", r1=(0.40 - s*0.04)*scale, r2=(0.36 - s*0.04)*scale,
                          depth=1.1*scale, segs=12,
                          loc=(random.uniform(-0.10,0.10)*scale, random.uniform(-0.10,0.10)*scale,
                               (s+0.5)*1.1*scale),
                          parent=base, mat_=M_ACACIA_TRUNK)
        seg.rotation_euler = (math.radians(random.uniform(-5,5)),
                              math.radians(random.uniform(-5,5)), 0)
    # 6 branches radiating from top (signature flat-top)
    for j in range(6):
        a = (j / 6.0) * math.pi * 2
        b_e = empty(f"{name}_be{j}", (0, 0, 5.5*scale), parent=base)
        b_e.rotation_euler = (math.radians(70), 0, a)
        for k in range(3):
            cyl(f"{name}_b{j}_{k}", r=(0.18 - k*0.03)*scale, depth=1.5*scale, segs=10,
                loc=(0, (k+0.5)*1.5*scale, 0), parent=b_e,
                mat_=M_ACACIA_TRUNK).rotation_euler = (math.radians(90), 0, 0)
    # FLAT-TOP CANOPY (signature savanna acacia umbrella)
    # Main flat disc
    cyl(f"{name}_canopy_main", r=4.5*scale, depth=0.6*scale, segs=24,
        loc=(0, 0, 7.5*scale), parent=base, mat_=M_ACACIA_LEAF)
    # Layered foliage
    for j in range(12):
        a = (j / 12.0) * math.pi * 2
        rad = random.uniform(2.5, 4.5) * scale
        col = M_ACACIA_LEAF if j % 2 == 0 else M_ACACIA_LEAF_DARK
        smooth_sphere(f"{name}_can{j}", r=random.uniform(1.0, 1.5) * scale,
                      loc=(rad*math.cos(a), rad*math.sin(a), 7.5*scale + random.uniform(-0.2, 0.4)),
                      parent=base, mat_=col, scale=(1, 1, 0.6))
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

acacias = []
ac_pos = [(-20, 12, 0, 1.0), (22, 8, 0, 1.0),
          (-18, -10, 0, 0.95), (20, -16, 0, 1.0)]
for i, (tx, ty, tz, sc) in enumerate(ac_pos):
    a = make_acacia(f"acacia{i}", (tx, ty, tz), scale=sc)
    acacias.append(a)

# ============ MAASAI WARRIORS (tall slim signature) ============
def make_maasai(name, loc, shuka_mat, is_chief=False, is_woman=False, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Tall slim body (signature Maasai height)
    # Legs (very long)
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_hip{side_idx}", (side*0.10*scale, 0, 0.90*scale), parent=base)
        # Thigh
        cyl(f"{name}_thigh{side_idx}", r=0.08*scale, depth=0.55*scale, segs=12,
            loc=(0, 0, -0.27*scale), parent=hip, mat_=M_SKIN_DARK)
        smooth_sphere(f"{name}_knee{side_idx}", r=0.07*scale, loc=(0, 0, -0.55*scale),
                      parent=hip, mat_=M_SKIN_DARK)
        # Calf
        cyl(f"{name}_calf{side_idx}", r=0.07*scale, depth=0.55*scale, segs=12,
            loc=(0, 0, -0.85*scale), parent=hip, mat_=M_SKIN_DARK)
        # Sandal
        beveled_cube(f"{name}_sandal{side_idx}", (0.14*scale, 0.25*scale, 0.04*scale),
                     loc=(0, 0.04*scale, -1.10*scale), parent=hip, mat_=M_SPEAR_WOOD)
        # Ankle beads
        cyl(f"{name}_ankle{side_idx}", r=0.075*scale, depth=0.03*scale, segs=12,
            loc=(0, 0, -1.05*scale), parent=hip, mat_=M_BEAD_RED)
    # Shuka (red cloth wrap signature)
    smooth_cone(f"{name}_shuka", r1=0.32*scale, r2=0.22*scale, depth=1.0*scale, segs=14,
                loc=(0, 0, 1.0*scale), parent=base, mat_=shuka_mat)
    # Cloth over shoulder (drape)
    drape = beveled_cube(f"{name}_drape", (0.30*scale, 0.04*scale, 0.85*scale), bevel_offset=0.02,
                        loc=(-0.12*scale, -0.05*scale, 1.4*scale), parent=base, mat_=shuka_mat)
    drape.rotation_euler = (0, math.radians(-15), 0)
    # Torso bare slim
    beveled_cube(f"{name}_torso", (0.30*scale, 0.18*scale, 0.45*scale), bevel_offset=0.04,
                 loc=(0, 0, 1.70*scale), parent=base, mat_=M_SKIN_DARK)
    # Neck
    cyl(f"{name}_neck", r=0.075*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 2.00*scale), parent=base, mat_=M_SKIN_DARK)
    # MASSIVE BEADED NECKLACE (signature Maasai)
    bead_colors = [M_BEAD_RED, M_BEAD_BLUE, M_BEAD_WHITE, M_BEAD_GREEN, M_BEAD_YELLOW]
    for ring in range(4 if is_woman else 2):
        ring_r = 0.16 * scale + ring * 0.04 * scale
        ring_z = 1.95 * scale - ring * 0.03 * scale
        for bd in range(16):
            ba = (bd / 16.0) * math.pi * 2
            bead_col = bead_colors[(bd + ring) % 5]
            smooth_sphere(f"{name}_bd{ring}_{bd}", r=0.025*scale,
                          loc=(ring_r*math.cos(ba), ring_r*math.sin(ba), ring_z),
                          parent=base, mat_=bead_col)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.18*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.16*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_DARK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_w{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.13*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.95, 0.92, 0.85, 1), 0, 0.4,
                                emission=(0.85,0.82,0.78), emission_strength=0.3))
        smooth_sphere(f"{name}_eye_p{side}", r=0.012*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ep{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Hair (short or braided)
    if is_woman:
        # Bald or short hair (Maasai women often shaved)
        smooth_sphere(f"{name}_hair", r=0.165*scale, loc=(0, 0, 0),
                      parent=head_e, mat_=M_SKIN_DARK)
        # Beaded ear rings (signature large)
        for side in (-1, 1):
            cyl(f"{name}_ear{side}", r=0.08*scale, depth=0.03*scale, segs=12,
                loc=(side*0.18*scale, 0, -0.05*scale), parent=head_e, mat_=M_BEAD_RED).rotation_euler = (0, math.radians(90), 0)
            # Hanging earrings
            for ei in range(3):
                smooth_sphere(f"{name}_ear_b{side}_{ei}", r=0.02*scale,
                              loc=(side*0.18*scale, 0, -0.10*scale - ei*0.04*scale),
                              parent=head_e, mat_=M_BEAD_BLUE if ei % 2 == 0 else M_BEAD_WHITE)
    else:
        # Braided red ochre hair (signature warrior)
        smooth_sphere(f"{name}_hair", r=0.17*scale, loc=(0, 0.02*scale, 0.04*scale),
                      parent=head_e, mat_=M_HAIR_BRAID, scale=(1.05, 1.0, 0.95))
        # Braids hanging
        for bri in range(6):
            ba = (bri - 2.5) * 0.25
            br = beveled_cube(f"{name}_braid{bri}", (0.025*scale, 0.025*scale, 0.40*scale),
                             loc=(math.sin(ba)*0.10*scale, 0.10*scale, -0.20*scale),
                             parent=head_e, mat_=M_HAIR_BRAID)
    # Chief decoration (taller + headdress)
    if is_chief:
        # Lion mane headdress (signature elder/chief)
        for mi in range(12):
            ma = (mi / 12.0) * math.pi * 2
            mane_obj = smooth_sphere(f"{name}_mane{mi}", r=0.06*scale,
                                      loc=(0.18*scale*math.cos(ma), 0.18*scale*math.sin(ma), 0.15*scale),
                                      parent=head_e, mat_=M_LION_MANE)
    # Arms (slim long)
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.22*scale, 0, 1.95*scale), parent=base)
        # Holding spear pose or arm down
        if side_idx == 0:
            sh.rotation_euler = (math.radians(-25), 0, math.radians(-10))
        else:
            sh.rotation_euler = (math.radians(-15), 0, math.radians(10))
        cyl(f"{name}_uarm{side_idx}", r=0.05*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=M_SKIN_DARK)
        cyl(f"{name}_fa{side_idx}", r=0.045*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.60*scale), parent=sh, mat_=M_SKIN_DARK)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.06*scale, loc=(0, 0, -0.80*scale),
                      parent=sh, mat_=M_SKIN_DARK)
        # Arm beaded bands
        for bd_idx in range(2):
            cyl(f"{name}_arm_bd{side_idx}_{bd_idx}", r=0.052*scale, depth=0.03*scale, segs=10,
                loc=(0, 0, -0.30*scale - bd_idx*0.20*scale), parent=sh,
                mat_=M_BEAD_RED if bd_idx == 0 else M_BEAD_BLUE)
        arms_e.append(sh)
    # Spear (signature)
    if not is_woman:
        spear_e = empty(f"{name}_spear_e", (-0.30*scale, 0, 1.5*scale), parent=base)
        spear_e.rotation_euler = (math.radians(-10), 0, 0)
        cyl(f"{name}_spear_sh", r=0.025*scale, depth=2.5*scale, segs=10,
            loc=(0, 0, 0), parent=spear_e, mat_=M_SPEAR_WOOD)
        # Spear blade
        smooth_cone(f"{name}_spear_blade", r1=0.06*scale, r2=0.005*scale, depth=0.30*scale, segs=10,
                    loc=(0, 0, 1.40*scale), parent=spear_e, mat_=M_SPEAR_TIP)
        # Counterweight base
        smooth_cone(f"{name}_spear_cw", r1=0.04*scale, r2=0.02*scale, depth=0.15*scale, segs=8,
                    loc=(0, 0, -1.30*scale), parent=spear_e, mat_=M_SPEAR_TIP)
        # Shield (signature oval painted)
        shield_e = empty(f"{name}_shield_e", (0.35*scale, 0, 1.3*scale), parent=base)
        shield_e.rotation_euler = (0, math.radians(-30), 0)
        beveled_cube(f"{name}_shield", (0.65*scale, 0.05*scale, 1.0*scale), bevel_offset=0.05,
                     loc=(0, 0, 0), parent=shield_e, mat_=M_SHIELD_HIDE)
        # Center vertical pattern (signature white stripes)
        beveled_cube(f"{name}_shield_p1", (0.10*scale, 0.06*scale, 1.0*scale), bevel_offset=0.02,
                     loc=(0, -0.04*scale, 0), parent=shield_e, mat_=M_SHIELD_PATTERN)
        beveled_cube(f"{name}_shield_p2", (0.55*scale, 0.06*scale, 0.10*scale), bevel_offset=0.02,
                     loc=(0, -0.04*scale, 0.25*scale), parent=shield_e, mat_=M_SHIELD_PATTERN)
        beveled_cube(f"{name}_shield_p3", (0.55*scale, 0.06*scale, 0.10*scale), bevel_offset=0.02,
                     loc=(0, -0.04*scale, -0.25*scale), parent=shield_e, mat_=M_SHIELD_PATTERN)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

# 8 warriors + chief + 4 women
maasai_people = []
warrior_specs = [
    ("w1", (-4, 3, 0), M_SHUKA_RED, math.radians(-30)),
    ("w2", (-2, 5, 0), M_SHUKA_RED, math.radians(0)),
    ("w3", (0, 6, 0), M_SHUKA_RED, math.radians(10)),
    ("w4", (2, 5, 0), M_SHUKA_BLUE, math.radians(-10)),
    ("w5", (4, 3, 0), M_SHUKA_RED, math.radians(30)),
    ("w6", (-5, 0, 0), M_SHUKA_BLUE, math.radians(60)),
    ("w7", (5, 0, 0), M_SHUKA_RED, math.radians(-60)),
    ("w8", (0, 8, 0), M_SHUKA_PURPLE, math.radians(180)),
]
for spec in warrior_specs:
    name, loc, shuka, fac = spec
    w = make_maasai(name, loc, shuka, facing=fac, scale=1.1)  # taller
    maasai_people.append(w)
# Chief
chief = make_maasai("chief", (0, 2, 0), M_SHUKA_PURPLE, is_chief=True, facing=math.radians(180), scale=1.2)
maasai_people.append(chief)
# 4 women
women_specs = [
    ("mwoman1", (-3, -2, 0), M_SHUKA_BLUE, math.radians(45)),
    ("mwoman2", (3, -2, 0), M_SHUKA_BLUE, math.radians(-45)),
    ("mwoman3", (-2, -5, 0), M_SHUKA_RED, math.radians(60)),
    ("mwoman4", (2, -5, 0), M_SHUKA_RED, math.radians(-60)),
]
for spec in women_specs:
    name, loc, shuka, fac = spec
    w = make_maasai(name, loc, shuka, is_woman=True, facing=fac, scale=1.0)
    maasai_people.append(w)

# ============ MANYATTA VILLAGE (mud huts) ============
def make_hut(name, loc, scale=1.0):
    base = empty(name, loc)
    # Mud walls (oval-ish)
    smooth_sphere(f"{name}_walls", r=1.2*scale, segs=18, rings=12, loc=(0, 0, 0.6*scale),
                  parent=base, mat_=M_MUD, scale=(1.3, 1.1, 0.7))
    # Doorway (dark hole)
    beveled_cube(f"{name}_door", (0.4*scale, 0.10*scale, 0.7*scale), bevel_offset=0.03,
                 loc=(0, -1.20*scale, 0.50*scale), parent=base, mat_=M_DUNG_DARK)
    # Straw roof (cone signature)
    smooth_cone(f"{name}_roof", r1=1.4*scale, r2=0.20*scale, depth=0.80*scale, segs=14,
                loc=(0, 0, 1.30*scale), parent=base, mat_=M_STRAW_ROOF)
    # Straw details
    for sti in range(8):
        sa = (sti / 8.0) * math.pi * 2
        beveled_cube(f"{name}_str{sti}", (0.05*scale, 0.05*scale, 0.50*scale),
                     loc=(1.0*scale*math.cos(sa), 1.0*scale*math.sin(sa), 1.30*scale),
                     parent=base, mat_=M_STRAW_ROOF)
    return base

# 5 huts in circle (manyatta signature)
huts = []
for i in range(5):
    a = (i / 5.0) * math.pi * 2
    rad = 12
    hx = rad * math.cos(a) - 18
    hy = rad * math.sin(a) - 18
    h = make_hut(f"hut{i}", (hx, hy, 0), scale=1.0)
    huts.append(h)
# Cattle enclosure (thorn fence circle around huts)
for i in range(24):
    a = (i / 24.0) * math.pi * 2
    fx = 14 * math.cos(a) - 18
    fy = 14 * math.sin(a) - 18
    cyl(f"fence{i}", r=0.05, depth=1.5, segs=8,
        loc=(fx, fy, 0.75), mat_=M_SPEAR_WOOD)

# ============ 10 ZEBU CATTLE (signature long-horned) ============
def make_zebu(name, loc, body_color, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.50, segs=20, rings=14, loc=(0, 0, 1.0),
                  parent=base, mat_=body_color, scale=(1.8, 1, 1))
    # Hump (signature zebu shoulder hump)
    smooth_sphere(f"{name}_hump", r=0.30, loc=(0.40, 0, 1.40),
                  parent=base, mat_=body_color, scale=(1.2, 1, 1.4))
    # Belly
    smooth_sphere(f"{name}_belly", r=0.40, loc=(0, 0, 0.85),
                  parent=base, mat_=M_ZEBU_WHITE, scale=(1.5, 0.95, 0.6))
    # Neck
    neck = beveled_cube(f"{name}_neck", (0.30, 0.30, 0.50), bevel_offset=0.04,
                       loc=(0.80, 0, 1.20), parent=base, mat_=body_color)
    neck.rotation_euler = (0, math.radians(-25), 0)
    # Head
    head_e = empty(f"{name}_he", (1.20, 0, 1.40), parent=base)
    beveled_cube(f"{name}_head", (0.40, 0.25, 0.30), bevel_offset=0.04,
                 loc=(0, 0, 0), parent=head_e, mat_=body_color)
    smooth_cone(f"{name}_muzzle", r1=0.12, r2=0.10, depth=0.20, segs=12,
                loc=(0.22, 0, -0.05), parent=head_e,
                mat_=M_ZEBU_WHITE).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04,
                      loc=(0.06, side*0.13, 0.08), parent=head_e, mat_=M_EYE_BEAST)
    # LONG CURVED HORNS (signature zebu)
    for side in (-1, 1):
        horn_e = empty(f"{name}_horn_e{side}", (-0.08, side*0.12, 0.20), parent=head_e)
        horn_e.rotation_euler = (math.radians(-10), 0, math.radians(side*30))
        for sk in range(4):
            sk_a = sk * 0.4
            cyl(f"{name}_horn{side}_{sk}", r=0.05 - sk*0.008, depth=0.40, segs=10,
                loc=(math.sin(sk_a)*0.05, 0, sk*0.32), parent=horn_e, mat_=M_HORN_ZEBU)
    # Ears
    for side in (-1, 1):
        ear = beveled_cube(f"{name}_ear{side}", (0.06, 0.18, 0.04),
                          loc=(-0.05, side*0.20, 0.18), parent=head_e, mat_=body_color)
        ear.rotation_euler = (0, 0, math.radians(side*30))
    # 4 legs
    for x_idx, x in enumerate((0.50, -0.50)):
        for y_idx, y in enumerate((-0.35, 0.35)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.09, depth=0.85, segs=10,
                loc=(x, y, 0.45), parent=base, mat_=body_color)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.10, depth=0.10, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_HORN_ZEBU)
    # Tail with tuft
    cyl(f"{name}_tail", r=0.04, depth=0.70, segs=10,
        loc=(-0.85, 0, 0.95), parent=base, mat_=body_color)
    smooth_sphere(f"{name}_tail_tuft", r=0.10, loc=(-1.05, 0, 0.50),
                  parent=base, mat_=body_color)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

zebus = []
# 10 zebus near village
zebu_pos = [(-14, -22, 0), (-12, -20, 0), (-10, -18, 0), (-16, -18, 0), (-14, -16, 0),
            (-18, -22, 0), (-12, -24, 0), (-20, -20, 0), (-15, -25, 0), (-13, -26, 0)]
for i, (zx, zy, zz) in enumerate(zebu_pos):
    col = M_ZEBU_BROWN if i % 2 == 0 else M_ZEBU_WHITE
    fac = math.radians(random.uniform(-180, 180))
    z = make_zebu(f"zebu{i}", (zx, zy, zz), body_color=col, facing=fac)
    zebus.append(z)

# ============ 6 GIRAFFES (signature long neck) ============
def make_giraffe(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.55, segs=20, rings=14, loc=(0, 0, 2.5),
                  parent=base, mat_=M_GIRAFFE_TAN, scale=(1.7, 1, 1))
    # Spots (signature)
    for sp in range(15):
        spx = random.uniform(-0.8, 0.8)
        spy = random.uniform(-0.4, 0.4)
        spz = 2.5 + random.uniform(-0.3, 0.5)
        smooth_sphere(f"{name}_spot{sp}", r=random.uniform(0.10, 0.20),
                      loc=(spx, spy, spz), parent=base, mat_=M_GIRAFFE_SPOT,
                      scale=(1, 1, 0.3))
    # LONG NECK (signature giraffe - 5m tall)
    neck_e = empty(f"{name}_neck_e", (0.5, 0, 2.7), parent=base)
    neck_e.rotation_euler = (0, math.radians(-20), 0)
    for ni in range(8):
        seg = cyl(f"{name}_neck{ni}", r=0.18 - ni*0.012, depth=0.30, segs=12,
                  loc=(0, 0, ni*0.32), parent=neck_e, mat_=M_GIRAFFE_TAN)
        # Spots on neck
        if ni % 2 == 0:
            smooth_sphere(f"{name}_neck_sp{ni}", r=0.10,
                          loc=(0.18, 0, ni*0.32), parent=neck_e, mat_=M_GIRAFFE_SPOT,
                          scale=(0.6, 1, 0.7))
    # Mane (signature short mane down neck)
    for mi in range(6):
        beveled_cube(f"{name}_mane{mi}", (0.04, 0.06, 0.15),
                     loc=(0, 0, 0.30 + mi*0.30), parent=neck_e, mat_=M_GIRAFFE_SPOT)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.6), parent=neck_e)
    beveled_cube(f"{name}_head", (0.35, 0.20, 0.25), bevel_offset=0.03,
                 loc=(0, 0, 0), parent=head_e, mat_=M_GIRAFFE_TAN)
    # Long muzzle
    smooth_cone(f"{name}_muzzle", r1=0.10, r2=0.08, depth=0.30, segs=12,
                loc=(0.25, 0, -0.04), parent=head_e,
                mat_=M_GIRAFFE_TAN).rotation_euler = (0, math.radians(90), 0)
    # Eyes (large gentle)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.05,
                      loc=(0.10, side*0.12, 0.08), parent=head_e, mat_=M_EYE_BEAST)
    # OSSICONES (signature giraffe horns - 2 covered with fur)
    for side in (-1, 1):
        oss = cyl(f"{name}_ossi{side}", r=0.04, depth=0.20, segs=10,
                  loc=(-0.10, side*0.10, 0.18), parent=head_e, mat_=M_GIRAFFE_TAN)
        # Tuft top
        smooth_sphere(f"{name}_oss_top{side}", r=0.06, loc=(-0.10, side*0.10, 0.32),
                      parent=head_e, mat_=M_GIRAFFE_SPOT)
    # Ears (big rounded)
    for side in (-1, 1):
        ear = beveled_cube(f"{name}_ear{side}", (0.05, 0.12, 0.05),
                          loc=(-0.05, side*0.18, 0.12), parent=head_e, mat_=M_GIRAFFE_TAN)
        ear.rotation_euler = (0, 0, math.radians(side*40))
    # 4 long legs (signature)
    for x_idx, x in enumerate((0.50, -0.50)):
        for y_idx, y in enumerate((-0.35, 0.35)):
            cyl(f"{name}_thigh{x_idx}{y_idx}", r=0.10, depth=0.90, segs=10,
                loc=(x, y, 1.95), parent=base, mat_=M_GIRAFFE_TAN)
            cyl(f"{name}_calf{x_idx}{y_idx}", r=0.08, depth=0.90, segs=10,
                loc=(x, y, 1.05), parent=base, mat_=M_GIRAFFE_TAN)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.10, depth=0.10, segs=10,
                loc=(x, y, 0.10), parent=base, mat_=M_GIRAFFE_SPOT)
    # Tail
    cyl(f"{name}_tail", r=0.04, depth=0.80, segs=10,
        loc=(-0.85, 0, 2.3), parent=base, mat_=M_GIRAFFE_TAN)
    smooth_sphere(f"{name}_tail_tuft", r=0.08, loc=(-1.10, 0, 1.8),
                  parent=base, mat_=M_GIRAFFE_SPOT)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "neck": neck_e}

giraffes = []
giraffe_pos = [(-22, 14, 0), (22, 10, 0), (24, 12, 0),
               (-20, -14, 0), (18, -18, 0), (-24, -8, 0)]
for i, (gx, gy, gz) in enumerate(giraffe_pos):
    fac = math.radians(random.uniform(-180, 180))
    g = make_giraffe(f"giraffe{i}", (gx, gy, gz), facing=fac)
    giraffes.append(g)

# ============ 4 ZEBRAS ============
def make_zebra(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.45, segs=20, rings=14, loc=(0, 0, 1.0),
                  parent=base, mat_=M_ZEBRA_WHITE, scale=(1.8, 1, 1))
    # Black stripes (signature)
    for st in range(12):
        sta = (st / 12.0) * math.pi
        stripe = beveled_cube(f"{name}_stripe{st}", (0.05, 0.40, 0.30),
                              loc=(0.7*math.cos(sta - math.pi/2), 0, 1.0),
                              parent=base, mat_=M_ZEBRA_BLACK)
        stripe.rotation_euler = (0, 0, sta)
    # Neck + head
    neck = beveled_cube(f"{name}_neck", (0.30, 0.25, 0.55), bevel_offset=0.04,
                       loc=(0.80, 0, 1.30), parent=base, mat_=M_ZEBRA_WHITE)
    neck.rotation_euler = (0, math.radians(-25), 0)
    # Neck stripes
    for ns in range(4):
        beveled_cube(f"{name}_nstripe{ns}", (0.05, 0.30, 0.10),
                     loc=(0.85 - ns*0.10, 0, 1.25 + ns*0.05), parent=base, mat_=M_ZEBRA_BLACK)
    head_e = empty(f"{name}_he", (1.20, 0, 1.45), parent=base)
    beveled_cube(f"{name}_head", (0.40, 0.22, 0.30), bevel_offset=0.04,
                 loc=(0, 0, 0), parent=head_e, mat_=M_ZEBRA_WHITE)
    # Head stripes
    for hs in range(3):
        beveled_cube(f"{name}_hstripe{hs}", (0.05, 0.25, 0.30),
                     loc=(-0.10 + hs*0.10, 0, 0), parent=head_e, mat_=M_ZEBRA_BLACK)
    smooth_cone(f"{name}_muzzle", r1=0.10, r2=0.08, depth=0.20, segs=12,
                loc=(0.22, 0, -0.05), parent=head_e,
                mat_=M_ZEBRA_BLACK).rotation_euler = (0, math.radians(90), 0)
    # Mane (signature standing)
    for mi in range(6):
        beveled_cube(f"{name}_mane{mi}", (0.04, 0.10, 0.18),
                     loc=(0.70 - mi*0.18, 0, 1.55), parent=base, mat_=M_ZEBRA_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04,
                      loc=(0.05, side*0.13, 0.08), parent=head_e, mat_=M_ZEBRA_BLACK)
    # Ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.06, r2=0.01, depth=0.15, segs=10,
                          loc=(-0.10, side*0.15, 0.20), parent=head_e, mat_=M_ZEBRA_WHITE)
        ear.rotation_euler = (math.radians(-20), 0, math.radians(side*15))
    # 4 legs (striped)
    for x_idx, x in enumerate((0.45, -0.45)):
        for y_idx, y in enumerate((-0.30, 0.30)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.07, depth=0.95, segs=10,
                loc=(x, y, 0.50), parent=base, mat_=M_ZEBRA_WHITE)
            for ls in range(4):
                cyl(f"{name}_leg_str{x_idx}{y_idx}_{ls}", r=0.072, depth=0.08, segs=10,
                    loc=(x, y, 0.20 + ls*0.20), parent=base, mat_=M_ZEBRA_BLACK)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.08, depth=0.10, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_ZEBRA_BLACK)
    # Tail
    cyl(f"{name}_tail", r=0.04, depth=0.70, segs=10,
        loc=(-0.80, 0, 0.95), parent=base, mat_=M_ZEBRA_WHITE)
    smooth_sphere(f"{name}_tail_t", r=0.08, loc=(-1.05, 0, 0.55),
                  parent=base, mat_=M_ZEBRA_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

zebras = []
zebra_pos = [(-12, 18, 0), (10, 16, 0), (-8, -28, 0), (14, -26, 0)]
for i, (zx, zy, zz) in enumerate(zebra_pos):
    fac = math.radians(random.uniform(-180, 180))
    z = make_zebra(f"zebra{i}", (zx, zy, zz), facing=fac)
    zebras.append(z)

# ============ 2 ELEPHANTS ============
def make_elephant(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Massive body
    smooth_sphere(f"{name}_body", r=1.0, segs=22, rings=16, loc=(0, 0, 1.8),
                  parent=base, mat_=M_ELEPHANT, scale=(1.7, 1.2, 1))
    # Head
    head_e = empty(f"{name}_he", (1.30, 0, 2.0), parent=base)
    smooth_sphere(f"{name}_head", r=0.70, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_ELEPHANT, scale=(1.2, 1, 1.1))
    # MASSIVE EARS (signature African elephant)
    for side in (-1, 1):
        ear_e = empty(f"{name}_ear_e{side}", (-0.10, side*0.55, 0.15), parent=head_e)
        beveled_cube(f"{name}_ear{side}", (0.10, 0.80, 1.0), bevel_offset=0.06,
                     loc=(0, side*0.50, 0), parent=ear_e, mat_=M_ELEPHANT)
    # TRUNK (signature long curl)
    trunk_e = empty(f"{name}_trunk_e", (0.50, 0, -0.25), parent=head_e)
    for ti in range(8):
        seg_r = 0.20 - ti*0.018
        seg_x = math.sin(ti * 0.3) * 0.15
        seg_z = -ti * 0.20
        cyl(f"{name}_trunk{ti}", r=seg_r, depth=0.22, segs=12,
            loc=(seg_x, 0, seg_z), parent=trunk_e, mat_=M_ELEPHANT)
    # Trunk tip
    smooth_sphere(f"{name}_trunk_tip", r=0.06,
                  loc=(math.sin(8 * 0.3) * 0.15, 0, -1.65), parent=trunk_e, mat_=M_ELEPHANT)
    # Tusks (signature ivory)
    for side in (-1, 1):
        tusk_e = empty(f"{name}_tusk_e{side}", (0.40, side*0.20, -0.10), parent=head_e)
        tusk_e.rotation_euler = (math.radians(-30), 0, math.radians(side*-15))
        for ts in range(3):
            cyl(f"{name}_tusk{side}_{ts}", r=0.06 - ts*0.012, depth=0.25, segs=10,
                loc=(0, 0, -ts*0.20), parent=tusk_e, mat_=M_TUSK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.06,
                      loc=(0.30, side*0.32, 0.25), parent=head_e, mat_=M_EYE_BEAST)
    # 4 thick legs
    for x_idx, x in enumerate((0.80, -0.70)):
        for y_idx, y in enumerate((-0.65, 0.65)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.20, depth=1.5, segs=12,
                loc=(x, y, 0.75), parent=base, mat_=M_ELEPHANT)
            cyl(f"{name}_foot{x_idx}{y_idx}", r=0.25, depth=0.20, segs=12,
                loc=(x, y, 0.10), parent=base, mat_=M_ELEPHANT)
    # Tail
    cyl(f"{name}_tail", r=0.05, depth=0.70, segs=10,
        loc=(-1.50, 0, 1.5), parent=base, mat_=M_ELEPHANT)
    smooth_sphere(f"{name}_tail_t", r=0.08, loc=(-1.65, 0, 1.0),
                  parent=base, mat_=M_LION_MANE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "trunk": trunk_e}

elephants = [
    make_elephant("ele1", (-15, 22, 0), math.radians(45)),
    make_elephant("ele2", (15, 22, 0), math.radians(-45)),
]

# ============ 3 LIONS ============
def make_lion(name, loc, is_male=False, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.50, segs=20, rings=14, loc=(0, 0, 0.75),
                  parent=base, mat_=M_LION_BODY, scale=(1.9, 1.1, 1))
    head_e = empty(f"{name}_he", (0.95, 0, 0.85), parent=base)
    smooth_sphere(f"{name}_head", r=0.32, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_LION_BODY)
    # MANE (signature male lion)
    if is_male:
        for mi in range(18):
            ma = (mi / 18.0) * math.pi * 2
            smooth_sphere(f"{name}_mane{mi}", r=0.18,
                          loc=(-0.05 + math.cos(ma)*0.30, math.sin(ma)*0.30, 0.05),
                          parent=head_e, mat_=M_LION_MANE)
    # Muzzle
    smooth_cone(f"{name}_muzzle", r1=0.18, r2=0.14, depth=0.20, segs=12,
                loc=(0.28, 0, -0.05), parent=head_e,
                mat_=M_LION_BODY).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.05,
                      loc=(0.18, side*0.12, 0.08), parent=head_e, mat_=M_EYE_BEAST)
    # Nose
    smooth_sphere(f"{name}_nose", r=0.04, loc=(0.40, 0, -0.05), parent=head_e, mat_=M_ZEBRA_BLACK)
    # Ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.08, r2=0.02, depth=0.10, segs=10,
                          loc=(0, side*0.20, 0.22), parent=head_e, mat_=M_LION_BODY)
    # 4 legs
    for x_idx, x in enumerate((0.45, -0.45)):
        for y_idx, y in enumerate((-0.30, 0.30)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.10, depth=0.65, segs=10,
                loc=(x, y, 0.35), parent=base, mat_=M_LION_BODY)
            cyl(f"{name}_paw{x_idx}{y_idx}", r=0.12, depth=0.10, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_LION_BODY)
    # Tail
    cyl(f"{name}_tail", r=0.04, depth=0.80, segs=10,
        loc=(-0.85, 0, 0.7), parent=base, mat_=M_LION_BODY)
    smooth_sphere(f"{name}_tail_t", r=0.10, loc=(-1.15, 0, 0.40),
                  parent=base, mat_=M_LION_MANE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

lions = [
    make_lion("lion_m", (8, -10, 0), is_male=True, facing=math.radians(-30)),
    make_lion("lion_f1", (10, -8, 0), is_male=False, facing=math.radians(-60)),
    make_lion("lion_f2", (6, -12, 0), is_male=False, facing=math.radians(0)),
]

# ============ 5 GAZELLES ============
def make_gazelle(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.30, segs=18, rings=12, loc=(0, 0, 0.85),
                  parent=base, mat_=M_GAZELLE, scale=(1.6, 1, 1))
    # Belly white
    smooth_sphere(f"{name}_belly", r=0.25, loc=(0, 0, 0.75),
                  parent=base, mat_=M_GAZELLE_BELLY, scale=(1.5, 0.95, 0.6))
    # Neck
    neck = beveled_cube(f"{name}_neck", (0.18, 0.16, 0.40), bevel_offset=0.03,
                       loc=(0.50, 0, 1.05), parent=base, mat_=M_GAZELLE)
    neck.rotation_euler = (0, math.radians(-25), 0)
    head_e = empty(f"{name}_he", (0.75, 0, 1.25), parent=base)
    beveled_cube(f"{name}_head", (0.20, 0.14, 0.20), bevel_offset=0.03,
                 loc=(0, 0, 0), parent=head_e, mat_=M_GAZELLE)
    smooth_cone(f"{name}_muzzle", r1=0.07, r2=0.05, depth=0.15, segs=10,
                loc=(0.13, 0, -0.04), parent=head_e,
                mat_=M_ZEBRA_BLACK).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.03,
                      loc=(0.04, side*0.09, 0.05), parent=head_e, mat_=M_EYE_BEAST)
    # Curved horns (signature gazelle)
    for side in (-1, 1):
        for sk in range(3):
            sk_z = sk * 0.10
            sk_x = math.sin(sk * 0.4) * 0.05
            cyl(f"{name}_horn{side}_{sk}", r=0.025 - sk*0.005, depth=0.12, segs=8,
                loc=(-0.05 + sk_x, side*0.08, 0.14 + sk_z), parent=head_e, mat_=M_HORN_GAZ)
    # Ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.05, r2=0.01, depth=0.15, segs=10,
                          loc=(-0.05, side*0.12, 0.18), parent=head_e, mat_=M_GAZELLE)
        ear.rotation_euler = (math.radians(-25), 0, math.radians(side*30))
    # 4 thin legs
    for x_idx, x in enumerate((0.35, -0.35)):
        for y_idx, y in enumerate((-0.20, 0.20)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.04, depth=0.75, segs=10,
                loc=(x, y, 0.40), parent=base, mat_=M_GAZELLE)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.05, depth=0.06, segs=8,
                loc=(x, y, 0.05), parent=base, mat_=M_HORN_GAZ)
    # White tail
    smooth_sphere(f"{name}_tail", r=0.08, loc=(-0.60, 0, 0.85),
                  parent=base, mat_=M_GAZELLE_BELLY, scale=(0.6, 0.8, 1.0))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

gazelles = []
gaz_pos = [(-8, 20, 0), (-5, 22, 0), (0, 24, 0), (5, 22, 0), (8, 20, 0)]
for i, (gx, gy, gz) in enumerate(gaz_pos):
    fac = math.radians(random.uniform(-180, 180))
    g = make_gazelle(f"gazelle{i}", (gx, gy, gz), facing=fac)
    gazelles.append(g)

# ============================================================
# ⭐ 600 DUST + 400 FLIES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 ochre dust
dust_savanna = []
for i in range(600):
    px = random.uniform(-40, 40)
    py = random.uniform(-40, 40)
    pz = random.uniform(0.3, 5)
    col = M_DUST_OCHRE if i % 2 == 0 else M_DUST_DARK
    d_obj = smooth_sphere(f"dust{i}", r=random.uniform(0.06, 0.14), segs=8, rings=6,
                          loc=(px, py, pz), mat_=col)
    d_obj["_phase"] = random.uniform(0, math.pi*2)
    d_obj["_base_x"] = px; d_obj["_base_y"] = py; d_obj["_base_z"] = pz
    d_obj["_amp_x"] = random.uniform(0.8, 2.2)
    d_obj["_amp_y"] = random.uniform(0.8, 2.2)
    d_obj["_amp_z"] = random.uniform(0.3, 1.0)
    d_obj["_speed"] = random.uniform(0.3, 0.7)
    dust_savanna.append(d_obj)

# 400 flies (signature savanna - small dark dots zigzag)
flies = []
for i in range(400):
    # Concentrated near animals
    if i < 200:
        # Near cattle/animals
        cx = random.choice([-15, 15, 0, -22, 22])
        cy = random.choice([-22, 18, 22, -10])
        px = cx + random.uniform(-3, 3)
        py = cy + random.uniform(-3, 3)
    else:
        px = random.uniform(-35, 35)
        py = random.uniform(-35, 35)
    pz = random.uniform(0.5, 4)
    f_e = empty(f"fly{i}", (px, py, pz))
    # Small dark body
    smooth_sphere(f"fly_b{i}", r=0.04, segs=8, rings=6, loc=(0, 0, 0),
                  parent=f_e, mat_=M_FLY)
    # Wings (tiny transparent)
    for side in (-1, 1):
        beveled_cube(f"fly_w{i}_{side}", (0.02, 0.06, 0.004), bevel_offset=0.001,
                     loc=(0, side*0.04, 0.02), parent=f_e, mat_=M_FLY_WING)
    f_e["_phase"] = random.uniform(0, math.pi*2)
    f_e["_base_x"] = px; f_e["_base_y"] = py; f_e["_base_z"] = pz
    f_e["_amp_x"] = random.uniform(0.5, 1.2)
    f_e["_amp_y"] = random.uniform(0.5, 1.2)
    f_e["_amp_z"] = random.uniform(0.2, 0.6)
    f_e["_speed"] = random.uniform(2.0, 4.0)
    flies.append(f_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Acacia sway
for ac in acacias:
    phase = ac["_phase"]
    for f in range(1, total_frames + 1, 5):
        t_v = (f - 1) / fps
        ac.rotation_euler = (math.sin(t_v * 0.7 + phase) * math.radians(2),
                              math.cos(t_v * 0.6 + phase) * math.radians(1.5), 0)
        ac.keyframe_insert("rotation_euler", frame=f)

# Maasai sway + body
for p in maasai_people:
    phase = p["root"]["_phase"]
    base_z = p["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        p["root"].location.z = base_z + math.sin(t * 1.2 + phase) * 0.04
        p["root"].keyframe_insert("location", frame=f)
        p["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(4), 0,
                                    math.sin(t * 0.6 + phase) * math.radians(15))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Zebus bob heads + graze
for z in zebus:
    phase = z["root"]["_phase"]
    base_z = z["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        z["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.03
        z["root"].keyframe_insert("location", frame=f)
        z["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(15), 0,
                                    math.sin(t * 0.6 + phase) * math.radians(12))
        z["he"].keyframe_insert("rotation_euler", frame=f)

# Giraffes neck sway + head browsing
for g in giraffes:
    phase = g["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        g["neck"].rotation_euler = (0,
                                      math.radians(-20) + math.sin(t * 0.5 + phase) * math.radians(8),
                                      math.sin(t * 0.4 + phase) * math.radians(10))
        g["neck"].keyframe_insert("rotation_euler", frame=f)
        g["he"].rotation_euler = (math.sin(t * 0.7 + phase) * math.radians(8), 0,
                                    math.sin(t * 0.5 + phase) * math.radians(15))
        g["he"].keyframe_insert("rotation_euler", frame=f)

# Zebras bob
for z in zebras:
    phase = z["root"]["_phase"]
    base_z = z["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        z["root"].location.z = base_z + abs(math.sin(t * 1.5 + phase)) * 0.06
        z["root"].keyframe_insert("location", frame=f)
        z["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(8), 0,
                                    math.sin(t * 1.0 + phase) * math.radians(12))
        z["he"].keyframe_insert("rotation_euler", frame=f)

# Elephants trunk sway
for e in elephants:
    phase = e["root"]["_phase"]
    base_z = e["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        e["root"].location.z = base_z + math.sin(t * 0.8 + phase) * 0.05
        e["root"].keyframe_insert("location", frame=f)
        # Trunk swings
        e["trunk"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(15),
                                       math.cos(t * 1.0 + phase) * math.radians(10), 0)
        e["trunk"].keyframe_insert("rotation_euler", frame=f)
        e["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(6), 0,
                                    math.sin(t * 0.5 + phase) * math.radians(10))
        e["he"].keyframe_insert("rotation_euler", frame=f)

# Lions slow head turn (roaring)
for l in lions:
    phase = l["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        l["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(8), 0,
                                    math.sin(t * 1.0 + phase) * math.radians(20))
        l["he"].keyframe_insert("rotation_euler", frame=f)

# Gazelles bound (high vertical bobbing)
for g in gazelles:
    phase = g["root"]["_phase"]
    base_z = g["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        g["root"].location.z = base_z + abs(math.sin(t * 3.0 + phase)) * 0.30
        g["root"].keyframe_insert("location", frame=f)
        g["he"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(8), 0,
                                    math.sin(t * 1.5 + phase) * math.radians(15))
        g["he"].keyframe_insert("rotation_euler", frame=f)

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
# ⭐⭐⭐ 600 DUST drift + 400 FLIES zigzag (signature savanna)
# ============================================================
for d in dust_savanna:
    phase = d["_phase"]; speed = d["_speed"]
    bx, by, bz = d["_base_x"], d["_base_y"], d["_base_z"]
    ax, ay, az = d["_amp_x"], d["_amp_y"], d["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        d.location = (x, y, max(0.1, z))
        sc = 1 + math.sin(t * 2.0 + phase) * 0.20
        d.scale = (sc, sc, sc)
        d.keyframe_insert("location", frame=f)
        d.keyframe_insert("scale", frame=f)

# 400 FLIES zigzag (signature erratic)
for fl in flies:
    phase = fl["_phase"]; speed = fl["_speed"]
    bx, by, bz = fl["_base_x"], fl["_base_y"], fl["_base_z"]
    ax, ay, az = fl["_amp_x"], fl["_amp_y"], fl["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Zigzag chaotic
        x = bx + ax * math.sin(t * speed + phase) + 0.3*math.sin(t * speed * 4 + phase * 2)
        y = by + ay * math.cos(t * speed * 0.9 + phase) + 0.3*math.cos(t * speed * 4 + phase)
        z = bz + az * math.sin(t * speed * 1.4 + phase * 1.7)
        fl.location = (x, y, max(0.2, z))
        fl.keyframe_insert("location", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_maasai_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_maasai_savanna_kilimanjaro] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_maasai_savanna_kilimanjaro] ONE savanna + Kilimanjaro flat-top + 4 acacias + 13 Maasai people + manyatta village + 10 zebu + 6 giraffes + 4 zebras + 2 elephants + 3 lions + 5 gazelles + 600 DUST + 400 FLIES")
print("⭐ FIXES: 1 ground + 600 dust + 400 flies (signature savanna Africa mandatory) ⭐")
