"""
proc_scottish_highland_castle.py — 231e procédural AuroraIA (95e qualité)
Scottish Highland: ONE moor ground + castle 4 towers + loch + cottage + 6 highlanders kilt + bagpiper + 4 women + clan chief claymore + 4 Highland cows + 6 sheep + stag + raven + 600 mist + 400 thistle petals
FIXES : 1 ground + 600 mist + 400 thistles signature Highland
"""
import bpy, bmesh, math, random, os

random.seed(0x5C07231)

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

# Scottish stormy dusk palette
M_SKY = mat("sky", (0.45, 0.45, 0.55, 1.0), 0.0, 0.7, emission=(0.42,0.42,0.52), emission_strength=2.0)
M_CLOUD_STORM = mat("cloud_s", (0.45, 0.45, 0.55, 1.0), 0.0, 0.65, emission=(0.42,0.42,0.50), emission_strength=1.2, alpha=0.85)
M_CLOUD_DARK = mat("cloud_d", (0.30, 0.30, 0.40, 1.0), 0.0, 0.75, emission=(0.28,0.28,0.35), emission_strength=0.9, alpha=0.85)
M_SUN_DIM = mat("sun_d", (1.0, 0.78, 0.55, 1.0), 0.0, 0.15, emission=(0.95,0.72,0.50), emission_strength=10.0, alpha=0.75)

# Ground heather + moor
M_HEATHER = mat("heather", (0.50, 0.35, 0.45, 1.0), 0.0, 0.85, emission=(0.45,0.32,0.42), emission_strength=0.4)
M_MOSS_HIGH = mat("moss_h", (0.30, 0.45, 0.30, 1.0), 0.0, 0.80, emission=(0.28,0.42,0.28), emission_strength=0.5)
M_GRASS_H = mat("grass_h", (0.42, 0.55, 0.30, 1.0), 0.0, 0.75, emission=(0.38,0.50,0.28), emission_strength=0.4)
M_ROCK_GRANITE = mat("granite", (0.45, 0.45, 0.50, 1.0), 0.0, 0.85)
M_ROCK_DARK_S = mat("rock_d", (0.30, 0.30, 0.35, 1.0), 0.0, 0.85)
M_PATH_S = mat("path", (0.55, 0.50, 0.45, 1.0), 0.0, 0.80, emission=(0.50,0.45,0.40), emission_strength=0.4)

# Loch (highland lake water)
M_LOCH = mat("loch", (0.18, 0.30, 0.35, 1.0), 0.5, 0.15, emission=(0.18,0.30,0.35), emission_strength=0.8, alpha=0.85)
M_LOCH_DEEP = mat("loch_d", (0.10, 0.20, 0.25, 1.0), 0.4, 0.20, emission=(0.10,0.20,0.25), emission_strength=0.5)
M_LOCH_RIPPLE = mat("ripple", (0.65, 0.78, 0.82, 0.75), 0.0, 0.20, emission=(0.60,0.72,0.78), emission_strength=1.5, alpha=0.75)

# Mountains highland
M_HIGHLAND_MOUNT = mat("highmount", (0.40, 0.42, 0.48, 1.0), 0.0, 0.85)
M_HIGHLAND_MOUNT_DARK = mat("highmount_d", (0.28, 0.30, 0.35, 1.0), 0.0, 0.85)

# Castle granite
M_CASTLE_STONE = mat("castle", (0.55, 0.52, 0.50, 1.0), 0.0, 0.85, emission=(0.50,0.48,0.45), emission_strength=0.4)
M_CASTLE_DARK = mat("castle_d", (0.42, 0.40, 0.38, 1.0), 0.0, 0.85)
M_CASTLE_MOSS = mat("castle_m", (0.35, 0.45, 0.30, 1.0), 0.0, 0.85, emission=(0.32,0.42,0.28), emission_strength=0.4)
M_CASTLE_ROOF = mat("castle_r", (0.40, 0.30, 0.25, 1.0), 0.0, 0.85)
M_WINDOW_GLOW = mat("win_g", (1.0, 0.75, 0.35, 1.0), 0.0, 0.10, emission=(1.0,0.75,0.35), emission_strength=8.0)
M_DOOR_OAK = mat("door_o", (0.30, 0.18, 0.10, 1.0), 0.0, 0.85)

# Royal Stuart tartan flag
M_FLAG_RED = mat("flag_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.72,0.18,0.18), emission_strength=0.7)
M_FLAG_BLUE = mat("flag_b", (0.20, 0.40, 0.65, 1.0), 0.0, 0.55, emission=(0.18,0.38,0.60), emission_strength=0.6)
M_FLAG_GREEN = mat("flag_g", (0.30, 0.50, 0.30, 1.0), 0.0, 0.55, emission=(0.28,0.45,0.28), emission_strength=0.5)
M_FLAG_YELLOW = mat("flag_y", (0.95, 0.78, 0.30, 1.0), 0.0, 0.50, emission=(0.92,0.75,0.28), emission_strength=0.8)
M_GOLD = mat("gold_s", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.92,0.75,0.28), emission_strength=1.0)

# Cottage
M_COTTAGE_STONE = mat("cot_s", (0.65, 0.55, 0.42, 1.0), 0.0, 0.80, emission=(0.60,0.50,0.40), emission_strength=0.4)
M_COTTAGE_ROOF = mat("cot_r", (0.45, 0.32, 0.20, 1.0), 0.0, 0.85, emission=(0.40,0.28,0.18), emission_strength=0.3)
M_THATCH = mat("thatch", (0.75, 0.58, 0.32, 1.0), 0.0, 0.85, emission=(0.70,0.55,0.30), emission_strength=0.4)
M_CHIMNEY = mat("chimney_s", (0.55, 0.50, 0.42, 1.0), 0.0, 0.85)

# Highlanders kilt + clothing
M_SKIN_SCOT = mat("skin_s", (0.95, 0.82, 0.72, 1.0), 0.0, 0.55, emission=(0.88,0.78,0.68), emission_strength=0.4)
# Tartan colors (signature Scottish)
M_TARTAN_RED = mat("tar_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.72,0.18,0.18), emission_strength=0.6)
M_TARTAN_GREEN = mat("tar_g", (0.25, 0.45, 0.25, 1.0), 0.0, 0.70, emission=(0.22,0.42,0.22), emission_strength=0.5)
M_TARTAN_BLUE = mat("tar_b", (0.18, 0.30, 0.55, 1.0), 0.0, 0.65, emission=(0.18,0.30,0.50), emission_strength=0.5)
M_TARTAN_DARK = mat("tar_d", (0.15, 0.20, 0.15, 1.0), 0.0, 0.75)
M_TARTAN_GOLD = mat("tar_y", (0.85, 0.65, 0.20, 1.0), 0.0, 0.65, emission=(0.80,0.60,0.18), emission_strength=0.6)
M_TARTAN_WHITE = mat("tar_w", (0.85, 0.82, 0.75, 1.0), 0.0, 0.65)
M_SPORRAN = mat("sporran", (0.32, 0.20, 0.12, 1.0), 0.0, 0.75)
M_SPORRAN_TASSEL = mat("sp_t", (0.65, 0.55, 0.30, 1.0), 0.0, 0.75)
M_SHIRT_HIGHLAND = mat("shirt_h", (0.92, 0.88, 0.80, 1.0), 0.0, 0.70, emission=(0.85,0.82,0.75), emission_strength=0.5)
M_VEST_HIGHLAND = mat("vest_h", (0.35, 0.22, 0.15, 1.0), 0.0, 0.75)
M_KILT_BELT = mat("k_belt", (0.32, 0.20, 0.12, 1.0), 0.0, 0.80)
M_KILT_BUCKLE = mat("k_buckle", (0.85, 0.78, 0.55, 1.0), 0.85, 0.30)
M_SOCKS_HIGHLAND = mat("socks_h", (0.85, 0.82, 0.75, 1.0), 0.0, 0.75)
M_BOOTS_HIGHLAND = mat("boots_h", (0.18, 0.12, 0.08, 1.0), 0.0, 0.80)
M_HAIR_RED_S = mat("hair_rs", (0.78, 0.42, 0.18, 1.0), 0.0, 0.65)
M_HAIR_DARK_S = mat("hair_ds", (0.18, 0.12, 0.08, 1.0), 0.0, 0.85)
M_BEARD_RED = mat("beard_red", (0.65, 0.32, 0.15, 1.0), 0.0, 0.75)

# Dresses for women
M_DRESS_PURPLE = mat("dress_pu", (0.55, 0.30, 0.55, 1.0), 0.0, 0.65, emission=(0.50,0.28,0.50), emission_strength=0.6)
M_DRESS_GREEN_S = mat("dress_gs", (0.30, 0.50, 0.35, 1.0), 0.0, 0.65, emission=(0.28,0.45,0.32), emission_strength=0.5)
M_DRESS_BLUE_S = mat("dress_bs", (0.30, 0.42, 0.65, 1.0), 0.0, 0.65, emission=(0.28,0.40,0.60), emission_strength=0.5)
M_DRESS_WHITE_S = mat("dress_ws", (0.92, 0.88, 0.82, 1.0), 0.0, 0.70, emission=(0.85,0.82,0.78), emission_strength=0.6)

# Weapons
M_CLAYMORE_BLADE = mat("claymore", (0.85, 0.85, 0.92, 1.0), 0.95, 0.18, emission=(0.78,0.78,0.85), emission_strength=0.6)
M_CLAYMORE_HILT = mat("claymore_h", (0.55, 0.42, 0.25, 1.0), 0.0, 0.65)
M_CLAYMORE_POMMEL = mat("c_pom", (0.85, 0.65, 0.25, 1.0), 0.85, 0.25)
M_SHIELD_TARGE = mat("targe", (0.55, 0.35, 0.18, 1.0), 0.0, 0.65, emission=(0.50,0.32,0.16), emission_strength=0.4)

# Bagpipes (signature)
M_BAGPIPE_BAG = mat("bp_bag", (0.30, 0.42, 0.30, 1.0), 0.0, 0.65, emission=(0.28,0.40,0.28), emission_strength=0.4)
M_BAGPIPE_WOOD = mat("bp_w", (0.45, 0.28, 0.15, 1.0), 0.0, 0.75)
M_BAGPIPE_IVORY = mat("bp_i", (0.95, 0.92, 0.80, 1.0), 0.0, 0.60, emission=(0.88,0.85,0.75), emission_strength=0.5)

# Highland cow (signature)
M_HC_FUR = mat("hc_f", (0.78, 0.42, 0.20, 1.0), 0.0, 0.90, emission=(0.72,0.40,0.18), emission_strength=0.3)
M_HC_FUR_DARK = mat("hc_fd", (0.45, 0.25, 0.12, 1.0), 0.0, 0.90)
M_HC_HORN = mat("hc_h", (0.85, 0.75, 0.55, 1.0), 0.2, 0.55)
M_HC_NOSE = mat("hc_n", (0.18, 0.10, 0.06, 1.0), 0.0, 0.65)

# Sheep
M_SHEEP_WOOL = mat("sheep_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.90, emission=(0.88,0.85,0.82), emission_strength=0.4)
M_SHEEP_FACE = mat("sheep_f", (0.30, 0.25, 0.20, 1.0), 0.0, 0.75)
M_SHEEP_LEG = mat("sheep_l", (0.30, 0.25, 0.20, 1.0), 0.0, 0.80)

# Red Stag
M_STAG = mat("stag", (0.78, 0.42, 0.20, 1.0), 0.0, 0.75, emission=(0.72,0.40,0.18), emission_strength=0.4)
M_STAG_BELLY = mat("stag_b", (0.85, 0.65, 0.45, 1.0), 0.0, 0.70)
M_STAG_ANTLER = mat("antler", (0.85, 0.75, 0.55, 1.0), 0.2, 0.55, emission=(0.80,0.70,0.50), emission_strength=0.4)
M_STAG_EYE = mat("stag_e", (0.20, 0.10, 0.05, 1.0), 0.0, 0.40, emission=(0.18,0.08,0.05), emission_strength=1.5)

# Raven
M_RAVEN_BLACK = mat("raven_bk", (0.05, 0.04, 0.06, 1.0), 0.3, 0.45, emission=(0.05,0.04,0.06), emission_strength=0.3)
M_RAVEN_EYE = mat("raven_e", (1.0, 0.85, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.20), emission_strength=8.0)

# Thistle (signature Scottish flower)
M_THISTLE_PURPLE = mat("th_p", (0.65, 0.30, 0.75, 1.0), 0.0, 0.45, emission=(0.60,0.28,0.70), emission_strength=2.5)
M_THISTLE_PINK = mat("th_pk", (0.95, 0.55, 0.85, 1.0), 0.0, 0.45, emission=(0.90,0.50,0.78), emission_strength=2.2)
M_THISTLE_STEM = mat("th_s", (0.30, 0.45, 0.20, 1.0), 0.0, 0.75)

# MIST (signature Scottish)
M_MIST_SCOT = mat("mist_s", (0.85, 0.88, 0.92, 1.0), 0.0, 0.30, emission=(0.80,0.85,0.88), emission_strength=2.5, alpha=0.55)
M_MIST_BLUE = mat("mist_b", (0.65, 0.75, 0.85, 1.0), 0.0, 0.30, emission=(0.60,0.70,0.82), emission_strength=2.3, alpha=0.55)

# ============ STORMY SKY + CLOUDS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
# Dim sun behind clouds
sun_e = empty("sun_e", (15, 50, 18))
smooth_sphere("sun_dim", r=4, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN_DIM)

# Many storm clouds
clouds = []
for i in range(12):
    a = (i / 12.0) * math.pi * 2
    rad = random.uniform(25, 45)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(18, 28)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    col = M_CLOUD_STORM if i % 2 == 0 else M_CLOUD_DARK
    for j in range(6):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(3.0, 5.0),
                      loc=(random.uniform(-4,4), random.uniform(-3,3), random.uniform(-0.5,1.0)),
                      parent=c_e, mat_=col)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ HIGHLAND MOUNTAINS BACKGROUND ============
mountain_e = empty("mountains", loc=(0, 38, 0))
for i in range(7):
    px = (i - 3) * 9
    py = random.uniform(-3, 3)
    pz = random.uniform(-1, 3)
    h = random.uniform(8, 14)
    smooth_cone(f"mt{i}", r1=8, r2=1.5, depth=h, segs=14,
                loc=(px, py, pz), parent=mountain_e,
                mat_=M_HIGHLAND_MOUNT if i % 2 == 0 else M_HIGHLAND_MOUNT_DARK)

# ============ ONE clean moor ground (heather purple-green) ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_HEATHER)
# Heather patches (organic 3D)
for i in range(60):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 42)
    smooth_sphere(f"heath{i}", r=random.uniform(0.30, 0.55),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_HEATHER if i % 3 == 0 else (M_MOSS_HIGH if i % 3 == 1 else M_GRASS_H),
                  scale=(1.4, 1.3, 0.18))

# Rocks (granite)
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(12, 40)
    smooth_sphere(f"rock{i}", r=random.uniform(0.5, 1.2),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.35),
                  mat_=M_ROCK_GRANITE if i % 2 == 0 else M_ROCK_DARK_S,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.85)))

# ============ LOCH (lake) in front ============
beveled_cube("loch_main", (45, 18, 0.15), bevel_offset=0.05, loc=(0, -18, -0.10), mat_=M_LOCH)
# Loch ripples
for i in range(20):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(3, 20)
    smooth_sphere(f"ripple{i}", r=random.uniform(0.30, 0.55), segs=14, rings=10,
                  loc=(rad*math.cos(a), -18 + rad*math.sin(a)*0.5, 0.0),
                  mat_=M_LOCH_RIPPLE, scale=(1.5, 1.3, 0.10))

# ============ MASSIVE CASTLE 4 TOWERS (signature Highland castle) ============
castle_e = empty("castle", loc=(0, 14, 0))
# Central keep
beveled_cube("c_keep", (8, 6, 8), bevel_offset=0.08, loc=(0, 0, 4),
             parent=castle_e, mat_=M_CASTLE_STONE)
# Moss patches on stone
for mi in range(20):
    mx = random.uniform(-3.5, 3.5)
    my = random.uniform(-2.5, 2.5)
    mz = random.uniform(0, 6)
    smooth_sphere(f"c_keep_moss{mi}", r=random.uniform(0.15, 0.30),
                  loc=(mx, my, mz), parent=castle_e, mat_=M_CASTLE_MOSS,
                  scale=(1.2, 0.5, 1.5))
# 4 CORNER TOWERS (signature)
tower_pos = [(-4.5, -3.5), (4.5, -3.5), (-4.5, 3.5), (4.5, 3.5)]
for ti, (tx, ty) in enumerate(tower_pos):
    t_e = empty(f"tower{ti}", (tx, ty, 0), parent=castle_e)
    # Tall round tower
    cyl(f"t_body{ti}", r=1.6, depth=11, segs=20,
        loc=(0, 0, 5.5), parent=t_e, mat_=M_CASTLE_STONE)
    # Battlement at top (signature crenellations)
    for cr in range(12):
        ca = (cr / 12.0) * math.pi * 2
        beveled_cube(f"t_crenel{ti}_{cr}", (0.40, 0.30, 0.50), bevel_offset=0.03,
                     loc=(1.65*math.cos(ca), 1.65*math.sin(ca), 11.0),
                     parent=t_e, mat_=M_CASTLE_DARK)
    # Conical roof (signature Scottish castle)
    smooth_cone(f"t_roof{ti}", r1=1.8, r2=0.05, depth=4, segs=16,
                loc=(0, 0, 13.5), parent=t_e, mat_=M_CASTLE_ROOF)
    # Flag pole top
    cyl(f"t_pole{ti}", r=0.05, depth=2.0, segs=8,
        loc=(0, 0, 16.5), parent=t_e, mat_=M_CASTLE_DARK)
    # Banner (red royal stuart signature)
    banner = beveled_cube(f"t_banner{ti}", (0.05, 0.04, 1.5), bevel_offset=0.01,
                          loc=(0, 0.25, 16.0), parent=t_e, mat_=M_FLAG_RED)
    # 3 narrow windows (arrow slits signature)
    for wi in range(3):
        beveled_cube(f"t_arrow{ti}_{wi}", (0.10, 0.10, 0.50), bevel_offset=0.02,
                     loc=(0, -1.65, 3 + wi*2), parent=t_e, mat_=M_DOOR_OAK)
    # Glowing arched window upper
    beveled_cube(f"t_win{ti}", (0.50, 0.10, 1.0), bevel_offset=0.04,
                 loc=(0, -1.65, 8.5), parent=t_e, mat_=M_WINDOW_GLOW)

# Battlements top of central keep
for cr in range(20):
    cx_b = (cr - 9.5) * 0.85
    beveled_cube(f"c_keep_cr{cr}", (0.7, 0.40, 0.50), bevel_offset=0.03,
                 loc=(cx_b, -3.05, 8.25), parent=castle_e, mat_=M_CASTLE_DARK)
    beveled_cube(f"c_keep_cr_b{cr}", (0.7, 0.40, 0.50), bevel_offset=0.03,
                 loc=(cx_b, 3.05, 8.25), parent=castle_e, mat_=M_CASTLE_DARK)

# Main gate (signature arched)
beveled_cube("c_gate_arch", (2.5, 0.40, 3.0), bevel_offset=0.04,
             loc=(0, -3.05, 1.5), parent=castle_e, mat_=M_DOOR_OAK)
# Gate iron studs
for stu in range(8):
    smooth_sphere(f"c_gate_stud{stu}", r=0.08,
                  loc=((stu % 4 - 1.5)*0.5, -3.25, 0.5 + (stu // 4)*1.5),
                  parent=castle_e, mat_=M_KILT_BUCKLE)
# Portcullis (signature iron grate)
for pi in range(5):
    cyl(f"c_port_v{pi}", r=0.04, depth=2.8, segs=8,
        loc=((pi-2)*0.50, -3.15, 1.5), parent=castle_e, mat_=M_CASTLE_DARK)
for pi in range(4):
    cyl(f"c_port_h{pi}", r=0.04, depth=2.5, segs=8,
        loc=(0, -3.15, 0.5 + pi*0.6), parent=castle_e, mat_=M_CASTLE_DARK).rotation_euler = (0, math.radians(90), 0)
# Castle windows glowing (signature warm light)
for wi in range(6):
    wx = (wi % 3 - 1) * 1.5
    wy_idx = wi // 3
    wy = -3.05 if wy_idx == 0 else 3.05
    beveled_cube(f"c_win_{wi}", (0.6, 0.10, 1.0), bevel_offset=0.03,
                 loc=(wx, wy, 5.5), parent=castle_e, mat_=M_WINDOW_GLOW)
# Top massive central flag pole (signature)
cyl("c_main_pole", r=0.10, depth=4.0, segs=10,
    loc=(0, 0, 10.5), parent=castle_e, mat_=M_CASTLE_DARK)
# Royal Stuart flag (signature red+yellow lion rampant)
flag_main = beveled_cube("c_main_flag", (0.10, 0.04, 2.5), bevel_offset=0.02,
                          loc=(0, 0.30, 10), parent=castle_e, mat_=M_FLAG_RED)
# Lion rampant detail
smooth_sphere("c_lion", r=0.20, loc=(0, 0.40, 10.5), parent=castle_e, mat_=M_FLAG_YELLOW, scale=(1, 0.1, 1.2))

# ============ STONE COTTAGE ============
cottage_e = empty("cottage", loc=(-22, -5, 0))
cottage_e.rotation_euler = (0, 0, math.radians(15))
# Stone walls
beveled_cube("cot_walls", (4.5, 3.0, 2.5), bevel_offset=0.06, loc=(0, 0, 1.25),
             parent=cottage_e, mat_=M_COTTAGE_STONE)
# Stone details (rough texture)
for si in range(15):
    smooth_sphere(f"cot_stone{si}", r=random.uniform(0.10, 0.20),
                  loc=(random.uniform(-2.0, 2.0), random.uniform(-1.3, 1.3),
                       random.uniform(0.3, 2.2)), parent=cottage_e, mat_=M_CASTLE_STONE)
# Steeply pitched thatched roof (signature)
for side, side_mul in zip(("L", "R"), (-1, 1)):
    roof = beveled_cube(f"cot_roof_{side}", (5.0, 2.2, 0.30), bevel_offset=0.04,
                       loc=(0, side_mul*1.0, 3.4), parent=cottage_e, mat_=M_THATCH)
    roof.rotation_euler = (math.radians(side_mul*-45), 0, 0)
# Thatch detail strips
for ti in range(15):
    tx_t = (ti - 7) * 0.30
    cyl(f"cot_th{ti}", r=0.04, depth=5.0, segs=8,
        loc=(tx_t, 0, 3.2 - abs(tx_t)*0.05), parent=cottage_e, mat_=M_THATCH).rotation_euler = (0, math.radians(90), 0)
# Chimney
beveled_cube("cot_ch", (0.45, 0.45, 1.8), bevel_offset=0.04, loc=(1.5, 0, 4.4),
             parent=cottage_e, mat_=M_CHIMNEY)
# Smoke from chimney
for si in range(4):
    smooth_sphere(f"cot_smoke{si}", r=0.30 + si*0.08,
                  loc=(1.5 + math.sin(si)*0.20, 0, 5.5 + si*0.7),
                  parent=cottage_e, mat_=M_MIST_SCOT)
# Door (oak)
beveled_cube("cot_door", (0.80, 0.10, 1.6), bevel_offset=0.03,
             loc=(0, -1.55, 0.80), parent=cottage_e, mat_=M_DOOR_OAK)
# Glowing windows
for wi in range(2):
    wx_c = (wi*2 - 1) * 1.3
    beveled_cube(f"cot_win{wi}", (0.7, 0.10, 0.8), bevel_offset=0.03,
                 loc=(wx_c, -1.55, 1.5), parent=cottage_e, mat_=M_WINDOW_GLOW)

# ============ HIGHLANDERS (6 men in kilt) ============
def make_highlander(name, loc, tartan_mat, hair_mat=M_HAIR_RED_S, is_chief=False, is_piper=False, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs bare (kilt shows knees signature)
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_hip{side_idx}", (side*0.13*scale, 0, 0.65*scale), parent=base)
        # Thigh (bare)
        cyl(f"{name}_thigh{side_idx}", r=0.10*scale, depth=0.30*scale, segs=12,
            loc=(0, 0, -0.15*scale), parent=hip, mat_=M_SKIN_SCOT)
        # Knee
        smooth_sphere(f"{name}_knee{side_idx}", r=0.085*scale, loc=(0, 0, -0.32*scale),
                      parent=hip, mat_=M_SKIN_SCOT)
        # Sock (long signature wool)
        cyl(f"{name}_sock{side_idx}", r=0.09*scale, depth=0.40*scale, segs=12,
            loc=(0, 0, -0.55*scale), parent=hip, mat_=M_SOCKS_HIGHLAND)
        # Sock bands at top (signature flashes)
        cyl(f"{name}_flash{side_idx}", r=0.095*scale, depth=0.06*scale, segs=12,
            loc=(0, 0, -0.36*scale), parent=hip, mat_=M_TARTAN_RED)
        # Boots (signature ghillie brogues)
        beveled_cube(f"{name}_boot{side_idx}", (0.14*scale, 0.30*scale, 0.10*scale), bevel_offset=0.02,
                     loc=(0, 0.05*scale, -0.80*scale), parent=hip, mat_=M_BOOTS_HIGHLAND)
    # KILT (signature pleated tartan)
    kilt_e = empty(f"{name}_kilt_e", (0, 0, 0.90*scale), parent=base)
    smooth_cone(f"{name}_kilt", r1=0.40*scale, r2=0.32*scale, depth=0.45*scale, segs=14,
                loc=(0, 0, 0), parent=kilt_e, mat_=tartan_mat)
    # Pleats (signature 8 pleats)
    for pl in range(8):
        pa = (pl / 8.0) * math.pi * 2
        beveled_cube(f"{name}_pleat{pl}", (0.05*scale, 0.04*scale, 0.50*scale), bevel_offset=0.01,
                     loc=(0.42*scale*math.cos(pa), 0.42*scale*math.sin(pa), 0),
                     parent=kilt_e, mat_=tartan_mat)
    # SPORRAN (signature leather pouch)
    sp_e = empty(f"{name}_sp_e", (0, -0.40*scale, 0.85*scale), parent=base)
    smooth_sphere(f"{name}_sporran", r=0.15*scale, loc=(0, 0, 0),
                  parent=sp_e, mat_=M_SPORRAN, scale=(1, 0.6, 1.3))
    # Tassels (signature 3)
    for ts in range(3):
        ts_x = (ts - 1) * 0.06*scale
        cyl(f"{name}_tassel{ts}", r=0.02*scale, depth=0.15*scale, segs=8,
            loc=(ts_x, -0.08*scale, -0.13*scale), parent=sp_e, mat_=M_SPORRAN_TASSEL)
        smooth_sphere(f"{name}_tassel_b{ts}", r=0.04*scale, loc=(ts_x, -0.08*scale, -0.22*scale),
                      parent=sp_e, mat_=M_SPORRAN_TASSEL)
    # Belt
    cyl(f"{name}_belt", r=0.38*scale, depth=0.10*scale, segs=18,
        loc=(0, 0, 1.18*scale), parent=base, mat_=M_KILT_BELT)
    # Buckle (signature decorative)
    beveled_cube(f"{name}_buckle", (0.18*scale, 0.05*scale, 0.14*scale), bevel_offset=0.02,
                 loc=(0, -0.38*scale, 1.18*scale), parent=base, mat_=M_KILT_BUCKLE)
    # Shirt white
    beveled_cube(f"{name}_shirt", (0.42*scale, 0.24*scale, 0.55*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.50*scale), parent=base, mat_=M_SHIRT_HIGHLAND)
    # VEST (signature jacobite)
    beveled_cube(f"{name}_vest", (0.45*scale, 0.10*scale, 0.50*scale), bevel_offset=0.04,
                 loc=(0, -0.13*scale, 1.50*scale), parent=base, mat_=M_VEST_HIGHLAND)
    # Buttons
    for bi in range(4):
        smooth_sphere(f"{name}_btn{bi}", r=0.025*scale,
                      loc=(0, -0.18*scale, 1.65*scale - bi*0.15*scale),
                      parent=base, mat_=M_KILT_BUCKLE)
    # SASH OVER SHOULDER (signature tartan)
    sash = beveled_cube(f"{name}_sash", (0.20*scale, 0.04*scale, 0.85*scale), bevel_offset=0.02,
                       loc=(-0.10*scale, -0.13*scale, 1.50*scale), parent=base, mat_=tartan_mat)
    sash.rotation_euler = (0, math.radians(-20), 0)
    # Neck
    cyl(f"{name}_neck", r=0.09*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 1.85*scale), parent=base, mat_=M_SKIN_SCOT)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.03*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.19*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_SCOT)
    # Hair (red signature Scottish)
    smooth_sphere(f"{name}_hair", r=0.21*scale, loc=(0, 0.04*scale, 0.05*scale),
                  parent=head_e, mat_=hair_mat, scale=(1, 1, 0.85))
    # MASSIVE RED BEARD (signature)
    smooth_sphere(f"{name}_beard", r=0.18*scale, loc=(0, -0.15*scale, -0.15*scale),
                  parent=head_e, mat_=M_BEARD_RED, scale=(1.1, 1.0, 1.3))
    # Beard strands
    for bsi in range(4):
        beveled_cube(f"{name}_b_str{bsi}", (0.07*scale, 0.06*scale, 0.30*scale),
                     loc=((bsi-1.5)*0.06*scale, -0.18*scale, -0.45*scale),
                     parent=head_e, mat_=M_BEARD_RED)
    # Mustache
    smooth_sphere(f"{name}_must", r=0.10*scale, loc=(0, -0.17*scale, -0.04*scale),
                  parent=head_e, mat_=M_BEARD_RED, scale=(1.5, 0.7, 0.4))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.20, 0.50, 0.30, 1), 0, 0.4,
                                emission=(0.18,0.45,0.28), emission_strength=0.5))
    # GLENGARRY (signature Scottish bonnet)
    bonnet_e = empty(f"{name}_bonnet_e", (0, 0, 0.18*scale), parent=head_e)
    # Round flat
    cyl(f"{name}_bonnet", r=0.22*scale, depth=0.12*scale, segs=18,
        loc=(0, 0, 0), parent=bonnet_e, mat_=M_TARTAN_DARK)
    # Check pattern strip
    for ci in range(12):
        ca = (ci / 12.0) * math.pi * 2
        col_check = M_TARTAN_WHITE if ci % 2 == 0 else M_TARTAN_DARK
        beveled_cube(f"{name}_check{ci}", (0.04*scale, 0.04*scale, 0.06*scale), bevel_offset=0.01,
                     loc=(0.22*scale*math.cos(ca), 0.22*scale*math.sin(ca), 0),
                     parent=bonnet_e, mat_=col_check)
    # Red pom-pom on top (signature toorie)
    smooth_sphere(f"{name}_toorie", r=0.06*scale, loc=(0, 0, 0.08*scale),
                  parent=bonnet_e, mat_=M_TARTAN_RED)
    # Cap badge gold (signature)
    smooth_sphere(f"{name}_badge", r=0.04*scale, loc=(0, -0.18*scale, 0.02*scale),
                  parent=bonnet_e, mat_=M_GOLD)
    # Arms (holding weapon or instrument)
    arms_e = []
    arm_poses = {
        "stand": [(math.radians(-15), 0), (math.radians(-15), 0)],
        "play": [(math.radians(-90), -30), (math.radians(-90), 30)],
        "chief": [(math.radians(-120), -30), (math.radians(-20), 15)],
        "dance": [(math.radians(-130), -20), (math.radians(-130), 20)],
    }
    if is_piper:
        action = "play"
    elif is_chief:
        action = "chief"
    else:
        action = random.choice(["stand", "dance"])
    pose = arm_poses[action]
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.78*scale), parent=base)
        rx, rz = pose[side_idx]
        sh.rotation_euler = (rx, 0, math.radians(side*-15 + rz))
        cyl(f"{name}_uarm{side_idx}", r=0.08*scale, depth=0.35*scale, segs=12,
            loc=(0, 0, -0.18*scale), parent=sh, mat_=M_SHIRT_HIGHLAND)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.50*scale), parent=sh, mat_=M_SKIN_SCOT)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08*scale, loc=(0, 0, -0.68*scale),
                      parent=sh, mat_=M_SKIN_SCOT)
        arms_e.append(sh)
    # CLAYMORE for chief (signature massive 2-handed sword)
    if is_chief:
        claymore_e = empty(f"{name}_claymore_e", (-0.5*scale, -0.3*scale, 2.0*scale), parent=base)
        claymore_e.rotation_euler = (math.radians(-30), 0, math.radians(20))
        # Long blade
        beveled_cube(f"{name}_claymore_b", (0.10*scale, 0.04*scale, 1.5*scale), bevel_offset=0.02,
                     loc=(0, 0, 0.6*scale), parent=claymore_e, mat_=M_CLAYMORE_BLADE)
        # Hilt long (2-handed signature)
        cyl(f"{name}_claymore_h", r=0.04*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.30*scale), parent=claymore_e, mat_=M_CLAYMORE_HILT)
        # Crossguard (signature curved)
        for cg in range(2):
            beveled_cube(f"{name}_cg{cg}", (0.20*scale, 0.06*scale, 0.06*scale), bevel_offset=0.01,
                         loc=((cg*2-1)*0.10*scale, 0, -0.12*scale), parent=claymore_e, mat_=M_CLAYMORE_POMMEL)
        # Pommel
        smooth_sphere(f"{name}_pommel", r=0.06*scale, loc=(0, 0, -0.55*scale),
                      parent=claymore_e, mat_=M_CLAYMORE_POMMEL)
        # Targe shield on back (signature)
        targe_e = empty(f"{name}_targe_e", (0, 0.20*scale, 1.60*scale), parent=base)
        cyl(f"{name}_targe", r=0.30*scale, depth=0.05*scale, segs=20,
            loc=(0, 0, 0), parent=targe_e, mat_=M_SHIELD_TARGE).rotation_euler = (math.radians(90), 0, 0)
        # Boss center
        smooth_sphere(f"{name}_targe_boss", r=0.08*scale, loc=(0, 0.04*scale, 0),
                      parent=targe_e, mat_=M_KILT_BUCKLE)
        # Studs
        for st in range(8):
            sta = (st / 8.0) * math.pi * 2
            smooth_sphere(f"{name}_targe_st{st}", r=0.025*scale,
                          loc=(0.22*scale*math.cos(sta), 0.04*scale, 0.22*scale*math.sin(sta)),
                          parent=targe_e, mat_=M_KILT_BUCKLE)
    # BAGPIPES for piper
    if is_piper:
        bp_e = empty(f"{name}_bp_e", (0.4*scale, -0.40*scale, 1.6*scale), parent=base)
        # Bag (green tartan signature)
        smooth_sphere(f"{name}_bp_bag", r=0.30*scale, loc=(0, 0, 0),
                      parent=bp_e, mat_=M_BAGPIPE_BAG, scale=(1.4, 1, 1.2))
        # 3 drones (signature) on top
        for di in range(3):
            d_x = (di - 1) * 0.08*scale
            d_len = (1.0 + di*0.15)*scale  # variable lengths
            cyl(f"{name}_drone{di}", r=0.025*scale, depth=d_len, segs=10,
                loc=(d_x, 0, 0.20*scale + d_len/2), parent=bp_e, mat_=M_BAGPIPE_WOOD)
            # Ivory band
            cyl(f"{name}_drone_b{di}", r=0.035*scale, depth=0.03*scale, segs=10,
                loc=(d_x, 0, 0.20*scale + d_len), parent=bp_e, mat_=M_BAGPIPE_IVORY)
            # Top cap
            smooth_sphere(f"{name}_drone_top{di}", r=0.04*scale,
                          loc=(d_x, 0, 0.20*scale + d_len + 0.05*scale), parent=bp_e, mat_=M_BAGPIPE_IVORY)
        # Chanter (front - signature)
        cyl(f"{name}_chanter", r=0.022*scale, depth=0.50*scale, segs=10,
            loc=(0, -0.20*scale, -0.20*scale), parent=bp_e, mat_=M_BAGPIPE_WOOD)
        # Blowpipe
        cyl(f"{name}_blowpipe", r=0.022*scale, depth=0.30*scale, segs=10,
            loc=(-0.10*scale, -0.30*scale, 0.20*scale), parent=bp_e, mat_=M_BAGPIPE_WOOD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

highlanders = []
hl_specs = [
    ("hl1", (-7, -2, 0), M_TARTAN_RED, M_HAIR_RED_S, False, False, math.radians(45)),
    ("hl2", (-3, -3, 0), M_TARTAN_GREEN, M_HAIR_RED_S, False, False, math.radians(20)),
    ("hl3", (3, -3, 0), M_TARTAN_BLUE, M_HAIR_DARK_S, False, False, math.radians(-20)),
    ("hl4", (7, -2, 0), M_TARTAN_GOLD, M_HAIR_RED_S, False, False, math.radians(-45)),
    ("hl5", (-5, 1, 0), M_TARTAN_GREEN, M_HAIR_DARK_S, False, False, math.radians(90)),
    ("hl6", (5, 1, 0), M_TARTAN_RED, M_HAIR_RED_S, False, False, math.radians(-90)),
]
for spec in hl_specs:
    name, loc, tartan, hair, chief, piper, fac = spec
    h = make_highlander(name, loc, tartan, hair, is_chief=chief, is_piper=piper, facing=fac)
    highlanders.append(h)

# Bagpiper (signature)
piper = make_highlander("piper", (0, -1, 0), M_TARTAN_RED, M_HAIR_RED_S, is_piper=True,
                         facing=math.radians(180), scale=1.05)
highlanders.append(piper)

# Clan chief with claymore
chief_h = make_highlander("chief_h", (0, 4, 0), M_TARTAN_GOLD, M_HAIR_RED_S, is_chief=True,
                           facing=math.radians(180), scale=1.15)
highlanders.append(chief_h)

# 4 Scottish women in dresses
def make_scot_woman(name, loc, dress_mat, hair_mat=M_HAIR_RED_S, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long flowing dress
    smooth_cone(f"{name}_dress", r1=0.55*scale, r2=0.35*scale, depth=1.7*scale, segs=18,
                loc=(0, 0, 0.85*scale), parent=base, mat_=dress_mat)
    # Bodice tight
    beveled_cube(f"{name}_bodice", (0.42*scale, 0.25*scale, 0.55*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.85*scale), parent=base, mat_=dress_mat)
    # Tartan sash (signature)
    sash = beveled_cube(f"{name}_sash", (0.20*scale, 0.04*scale, 1.0*scale), bevel_offset=0.02,
                       loc=(-0.10*scale, -0.13*scale, 1.50*scale), parent=base, mat_=M_TARTAN_GREEN)
    sash.rotation_euler = (0, math.radians(-20), 0)
    # White collar
    cyl(f"{name}_collar", r=0.22*scale, depth=0.04*scale, segs=16,
        loc=(0, 0, 2.10*scale), parent=base, mat_=M_DRESS_WHITE_S)
    # Neck
    cyl(f"{name}_neck", r=0.08*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 2.18*scale), parent=base, mat_=M_SKIN_SCOT)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.36*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.17*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_SCOT)
    # Long flowing red hair (signature)
    smooth_sphere(f"{name}_hair_b", r=0.25*scale, loc=(0, 0.08*scale, -0.05*scale),
                  parent=head_e, mat_=hair_mat, scale=(1.05, 1.05, 1.5))
    smooth_sphere(f"{name}_hair_t", r=0.20*scale, loc=(0, 0.02*scale, 0.06*scale),
                  parent=head_e, mat_=hair_mat, scale=(1, 1, 0.85))
    # Hair strands
    for hs in range(6):
        hs_x = (hs - 2.5) * 0.06*scale
        cyl(f"{name}_hs{hs}", r=0.02*scale, depth=0.50*scale, segs=8,
            loc=(hs_x, 0.20*scale, -0.30*scale), parent=head_e, mat_=hair_mat)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.13*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.30, 0.55, 0.30, 1), 0, 0.4,
                                emission=(0.28,0.50,0.28), emission_strength=0.5))
    # Arms
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.32*scale, 0, 2.06*scale), parent=base)
        sh.rotation_euler = (math.radians(-30), 0, math.radians(side*-25))
        cyl(f"{name}_uarm{side_idx}", r=0.07*scale, depth=0.32*scale, segs=10,
            loc=(0, 0, -0.17*scale), parent=sh, mat_=dress_mat)
        cyl(f"{name}_fa{side_idx}", r=0.06*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.47*scale), parent=sh, mat_=M_SKIN_SCOT)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07*scale, loc=(0, 0, -0.64*scale),
                      parent=sh, mat_=M_SKIN_SCOT)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

women_h = []
women_specs = [
    ("scw1", (-9, 3, 0), M_DRESS_PURPLE, M_HAIR_RED_S, math.radians(45)),
    ("scw2", (9, 3, 0), M_DRESS_GREEN_S, M_HAIR_RED_S, math.radians(-45)),
    ("scw3", (-2, 6, 0), M_DRESS_BLUE_S, M_HAIR_RED_S, math.radians(180)),
    ("scw4", (2, 6, 0), M_DRESS_WHITE_S, M_HAIR_DARK_S, math.radians(180)),
]
for spec in women_specs:
    name, loc, dress, hair, fac = spec
    w = make_scot_woman(name, loc, dress, hair, facing=fac)
    women_h.append(w)

# ============ 4 HIGHLAND COWS (signature long hair + horns) ============
def make_highland_cow(name, loc, body_color=M_HC_FUR, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Massive body covered in shaggy hair
    smooth_sphere(f"{name}_body", r=0.65, segs=20, rings=14, loc=(0, 0, 1.10),
                  parent=base, mat_=body_color, scale=(1.8, 1, 1))
    # Shaggy fur (signature)
    for fi in range(12):
        fa = (fi / 12.0) * math.pi * 2
        for sk in range(3):
            beveled_cube(f"{name}_fur{fi}_{sk}", (0.12, 0.08, 0.50), bevel_offset=0.02,
                         loc=(0.65*math.cos(fa), 0.55*math.sin(fa) - sk*0.06,
                              0.65 - sk*0.10), parent=base, mat_=body_color)
    # Head with massive forelock (signature signature signature)
    head_e = empty(f"{name}_he", (1.20, 0, 1.30), parent=base)
    smooth_sphere(f"{name}_head", r=0.32, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=body_color, scale=(1, 1.1, 1))
    # MASSIVE FORELOCK over eyes (signature)
    for fl in range(15):
        fl_x = random.uniform(-0.25, 0.25)
        fl_y = -0.18 + random.uniform(-0.04, 0.04)
        fl_z = 0.10 + random.uniform(-0.10, 0.05)
        cyl(f"{name}_forelock{fl}", r=0.025, depth=random.uniform(0.30, 0.55), segs=6,
            loc=(fl_x, fl_y, fl_z), parent=head_e, mat_=body_color)
    # Muzzle
    smooth_sphere(f"{name}_muzzle", r=0.18, loc=(0, -0.30, -0.10),
                  parent=head_e, mat_=M_HC_NOSE, scale=(1.2, 0.6, 0.8))
    # MASSIVE CURVED HORNS (signature - wide)
    for side in (-1, 1):
        horn_e = empty(f"{name}_horn_e{side}", (-0.05, side*0.22, 0.20), parent=head_e)
        horn_e.rotation_euler = (math.radians(-10), 0, math.radians(side*60))
        # Long curved horn
        for sk in range(5):
            sk_x = math.sin(sk * 0.4) * 0.08
            cyl(f"{name}_horn{side}_{sk}", r=0.07 - sk*0.008, depth=0.25, segs=10,
                loc=(sk_x, 0, sk*0.21), parent=horn_e, mat_=M_HC_HORN)
        # Tip
        smooth_cone(f"{name}_horn_tip{side}", r1=0.05, r2=0.005, depth=0.15, segs=8,
                    loc=(math.sin(5*0.4)*0.08, 0, 5*0.21), parent=horn_e, mat_=M_HC_HORN)
    # 4 legs (covered in hair)
    for x_idx, x in enumerate((0.50, -0.50)):
        for y_idx, y in enumerate((-0.35, 0.35)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.10, depth=0.65, segs=10,
                loc=(x, y, 0.35), parent=base, mat_=body_color)
            # Hooves
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.11, depth=0.10, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_HC_NOSE)
    # Tail
    cyl(f"{name}_tail", r=0.04, depth=0.60, segs=10,
        loc=(-0.85, 0, 0.95), parent=base, mat_=body_color)
    smooth_sphere(f"{name}_tail_t", r=0.12, loc=(-1.0, 0, 0.55),
                  parent=base, mat_=body_color)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

cows = []
cow_pos = [(-15, 10, 0, math.radians(45)),
           (15, 10, 0, math.radians(-45)),
           (-20, -5, 0, math.radians(90)),
           (20, -5, 0, math.radians(-90))]
for i, (cx, cy, cz, fac) in enumerate(cow_pos):
    cow_col = M_HC_FUR if i % 2 == 0 else M_HC_FUR_DARK
    c = make_highland_cow(f"hcow{i}", (cx, cy, cz), body_color=cow_col, facing=fac)
    cows.append(c)

# ============ 6 SHEEP ============
def make_sheep(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Wool body (signature)
    smooth_sphere(f"{name}_body", r=0.30, segs=18, rings=12, loc=(0, 0, 0.55),
                  parent=base, mat_=M_SHEEP_WOOL, scale=(1.6, 1.1, 1))
    # Wool puffs
    for wi in range(8):
        wa = (wi / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_wool{wi}", r=0.16,
                      loc=(0.30*math.cos(wa), 0.25*math.sin(wa), 0.65),
                      parent=base, mat_=M_SHEEP_WOOL)
    # Head (dark face signature)
    head_e = empty(f"{name}_he", (0.50, 0, 0.65), parent=base)
    smooth_sphere(f"{name}_head", r=0.13, segs=16, rings=10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SHEEP_FACE)
    smooth_cone(f"{name}_snout", r1=0.08, r2=0.05, depth=0.12, segs=10,
                loc=(0.10, 0, -0.04), parent=head_e,
                mat_=M_SHEEP_FACE).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.02,
                      loc=(0.04, side*0.07, 0.04), parent=head_e, mat_=M_HC_NOSE)
    # Ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.05, r2=0.01, depth=0.12, segs=10,
                          loc=(-0.02, side*0.10, 0.08), parent=head_e, mat_=M_SHEEP_FACE)
        ear.rotation_euler = (math.radians(-20), 0, math.radians(side*40))
    # 4 legs
    for x_idx, x in enumerate((0.25, -0.25)):
        for y_idx, y in enumerate((-0.15, 0.15)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.04, depth=0.45, segs=10,
                loc=(x, y, 0.23), parent=base, mat_=M_SHEEP_LEG)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.05, depth=0.06, segs=8,
                loc=(x, y, 0.05), parent=base, mat_=M_HC_NOSE)
    return {"root": base, "he": head_e}

sheep = []
sheep_pos = [(-10, 14, 0), (-7, 16, 0), (-3, 17, 0),
             (3, 17, 0), (7, 16, 0), (10, 14, 0)]
for i, (sx, sy, sz) in enumerate(sheep_pos):
    fac = math.radians(random.uniform(-180, 180))
    s = make_sheep(f"sheep{i}", (sx, sy, sz), facing=fac)
    sheep.append(s)

# ============ MAJESTIC RED STAG ============
def make_red_stag(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.55, segs=20, rings=14, loc=(0, 0, 1.30),
                  parent=base, mat_=M_STAG, scale=(1.7, 1, 1))
    # Belly
    smooth_sphere(f"{name}_belly", r=0.45, loc=(0, 0, 1.10),
                  parent=base, mat_=M_STAG_BELLY, scale=(1.5, 0.95, 0.7))
    # Neck
    neck = beveled_cube(f"{name}_neck", (0.30, 0.25, 0.85), bevel_offset=0.04,
                       loc=(0.85, 0, 1.60), parent=base, mat_=M_STAG)
    neck.rotation_euler = (0, math.radians(-25), 0)
    # Head
    head_e = empty(f"{name}_he", (1.30, 0, 2.10), parent=base)
    beveled_cube(f"{name}_head", (0.40, 0.20, 0.30), bevel_offset=0.04,
                 loc=(0, 0, 0), parent=head_e, mat_=M_STAG)
    smooth_cone(f"{name}_muzzle", r1=0.10, r2=0.07, depth=0.20, segs=12,
                loc=(0.22, 0, -0.05), parent=head_e,
                mat_=M_STAG).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.05,
                      loc=(0.05, side*0.12, 0.08), parent=head_e, mat_=M_STAG_EYE)
    # Ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.06, r2=0.01, depth=0.20, segs=10,
                          loc=(-0.05, side*0.15, 0.18), parent=head_e, mat_=M_STAG)
        ear.rotation_euler = (math.radians(-15), 0, math.radians(side*30))
    # MASSIVE BRANCHING ANTLERS (signature majestic stag)
    for side in (-1, 1):
        ant_e = empty(f"{name}_ant_e{side}", (-0.10, side*0.12, 0.25), parent=head_e)
        ant_e.rotation_euler = (math.radians(-15), 0, math.radians(side*20))
        # Main beam
        cyl(f"{name}_ant_m{side}", r=0.05, depth=0.55, segs=8,
            loc=(0, 0, 0.27), parent=ant_e, mat_=M_STAG_ANTLER)
        # 6 tines branching (signature)
        for ti in range(6):
            tine_h = 0.10 + ti * 0.10
            tine_e = empty(f"{name}_ant_t_e{side}_{ti}", (math.sin(ti*0.4)*0.10, 0, tine_h), parent=ant_e)
            tine_e.rotation_euler = (0, math.radians(side*40 + ti*8), 0)
            cyl(f"{name}_tine{side}_{ti}", r=0.030 - ti*0.003, depth=0.30, segs=6,
                loc=(0, 0, 0.15), parent=tine_e, mat_=M_STAG_ANTLER)
            # Tip fork
            for tt in range(2):
                cyl(f"{name}_tt{side}_{ti}_{tt}", r=0.015, depth=0.20, segs=6,
                    loc=((tt*2-1)*0.06, 0, 0.32),
                    parent=tine_e, mat_=M_STAG_ANTLER).rotation_euler = (0, math.radians((tt*2-1)*30), 0)
    # 4 long legs
    for x_idx, x in enumerate((0.50, -0.50)):
        for y_idx, y in enumerate((-0.35, 0.35)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.08, depth=1.10, segs=10,
                loc=(x, y, 0.60), parent=base, mat_=M_STAG)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.09, depth=0.10, segs=10,
                loc=(x, y, 0.10), parent=base, mat_=M_STAG_ANTLER)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

stag = make_red_stag("stag", (-25, 8, 0), facing=math.radians(60))

# Raven (signature)
raven_e = empty("raven", loc=(0, 0, 20))
smooth_sphere("rv_body", r=0.30, segs=18, rings=12, loc=(0, 0, 0),
              parent=raven_e, mat_=M_RAVEN_BLACK, scale=(1.7, 1, 1))
rv_head_e = empty("rv_he", (0.45, 0, 0.10), parent=raven_e)
smooth_sphere("rv_head", r=0.18, loc=(0, 0, 0), parent=rv_head_e, mat_=M_RAVEN_BLACK)
smooth_cone("rv_beak", r1=0.07, r2=0.01, depth=0.25, segs=10,
            loc=(0.22, 0, -0.02), parent=rv_head_e,
            mat_=M_RAVEN_BLACK).rotation_euler = (0, math.radians(90), 0)
for side in (-1, 1):
    smooth_sphere(f"rv_eye{side}", r=0.04, loc=(0.08, side*0.10, 0.06),
                  parent=rv_head_e, mat_=M_RAVEN_EYE)
rv_wings = []
for side in (-1, 1):
    w_e = empty(f"rv_we{side}", (0, side*0.22, 0.05), parent=raven_e)
    beveled_cube(f"rv_w{side}", (0.50, 0.95, 0.05), bevel_offset=0.02,
                 loc=(0, side*0.50, 0), parent=w_e, mat_=M_RAVEN_BLACK)
    rv_wings.append((w_e, side))
beveled_cube("rv_tail", (0.35, 0.25, 0.05), loc=(-0.45, 0, 0),
             parent=raven_e, mat_=M_RAVEN_BLACK)

# ============ THISTLES on ground (signature Scottish flower) ============
for i in range(25):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 30)
    tx_th = rad * math.cos(a)
    ty_th = rad * math.sin(a)
    th_e = empty(f"thistle{i}", (tx_th, ty_th, 0))
    # Stem
    cyl(f"th_stem{i}", r=0.025, depth=0.50, segs=6,
        loc=(0, 0, 0.25), parent=th_e, mat_=M_THISTLE_STEM)
    # Spiky leaves
    for li in range(4):
        la = (li / 4.0) * math.pi * 2
        beveled_cube(f"th_l{i}_{li}", (0.04, 0.18, 0.015), bevel_offset=0.005,
                     loc=(0.05*math.cos(la), 0.05*math.sin(la), 0.25),
                     parent=th_e, mat_=M_THISTLE_STEM)
    # Purple flower head (signature)
    smooth_sphere(f"th_head{i}", r=0.10, loc=(0, 0, 0.55),
                  parent=th_e, mat_=M_THISTLE_PURPLE if i % 2 == 0 else M_THISTLE_PINK,
                  scale=(1, 1, 0.85))
    # Spikes (signature)
    for sp in range(10):
        sa = (sp / 10.0) * math.pi * 2
        spv = (sp / 10.0) * math.pi
        sx_sp = 0.10 * math.cos(sa) * math.sin(spv)
        sy_sp = 0.10 * math.sin(sa) * math.sin(spv)
        sz_sp = 0.10 * math.cos(spv)
        smooth_cone(f"th_sp{i}_{sp}", r1=0.015, r2=0.005, depth=0.06, segs=6,
                    loc=(sx_sp, sy_sp, 0.55 + sz_sp), parent=th_e,
                    mat_=M_THISTLE_PURPLE).rotation_euler = (sa, 0, 0)

# ============================================================
# ⭐ 600 MIST + 400 THISTLE PETALS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 mist particles (signature Scottish lowground)
mist_particles = []
for i in range(600):
    px = random.uniform(-40, 40)
    py = random.uniform(-40, 30)
    pz = random.uniform(0.3, 4)
    m_obj = smooth_sphere(f"mist{i}", r=random.uniform(0.30, 0.65), segs=12, rings=8,
                          loc=(px, py, pz),
                          mat_=M_MIST_SCOT if i % 2 == 0 else M_MIST_BLUE,
                          scale=(1.5, 1.5, 0.4))
    m_obj["_phase"] = random.uniform(0, math.pi*2)
    m_obj["_base_x"] = px; m_obj["_base_y"] = py; m_obj["_base_z"] = pz
    m_obj["_amp_x"] = random.uniform(0.8, 2.0)
    m_obj["_amp_y"] = random.uniform(0.8, 2.0)
    m_obj["_speed"] = random.uniform(0.2, 0.6)
    mist_particles.append(m_obj)

# 400 thistle petals floating
thistle_petals = []
for i in range(400):
    px = random.uniform(-38, 38)
    py = random.uniform(-38, 38)
    pz = random.uniform(0.8, 12)
    col = M_THISTLE_PURPLE if i % 2 == 0 else M_THISTLE_PINK
    p_obj = smooth_sphere(f"th_p{i}", r=random.uniform(0.06, 0.12), segs=8, rings=6,
                          loc=(px, py, pz), mat_=col,
                          scale=(1, 1, 0.7))
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_speed"] = random.uniform(0.4, 1.0)
    p_obj["_drift_x"] = random.uniform(-1.2, 1.2)
    p_obj["_drift_y"] = random.uniform(-1.2, 1.2)
    thistle_petals.append(p_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Highlanders bob + dance
for h in highlanders:
    phase = h["root"]["_phase"]
    base_z = h["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        h["root"].location.z = base_z + abs(math.sin(t * 2.0 + phase)) * 0.08
        h["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(4),
                                     math.cos(t * 1.2 + phase) * math.radians(3),
                                     h["root"].rotation_euler.z)
        h["root"].keyframe_insert("location", frame=f)
        h["root"].keyframe_insert("rotation_euler", frame=f)
        h["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                    math.sin(t * 1.2 + phase) * math.radians(15))
        h["he"].keyframe_insert("rotation_euler", frame=f)

# Women sway
for w in women_h:
    phase = w["root"]["_phase"]
    base_z = w["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        w["root"].location.z = base_z + math.sin(t * 1.2 + phase) * 0.03
        w["root"].keyframe_insert("location", frame=f)
        w["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(5), 0,
                                    math.sin(t * 0.8 + phase) * math.radians(15))
        w["he"].keyframe_insert("rotation_euler", frame=f)

# Cows bob (Highland cow shaggy sway)
for c in cows:
    phase = c["root"]["_phase"]
    base_z = c["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        c["root"].location.z = base_z + math.sin(t * 0.8 + phase) * 0.04
        c["root"].keyframe_insert("location", frame=f)
        c["he"].rotation_euler = (math.sin(t * 0.6 + phase) * math.radians(8), 0,
                                    math.sin(t * 0.5 + phase) * math.radians(12))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Sheep bob
for s in sheep:
    phase = hash(s["root"].name) % 100 * 0.05
    base_z = s["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.03
        s["root"].keyframe_insert("location", frame=f)
        s["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(6), 0,
                                    math.sin(t * 0.7 + phase) * math.radians(15))
        s["he"].keyframe_insert("rotation_euler", frame=f)

# Stag majestic head turn
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    stag["he"].rotation_euler = (math.sin(t * 0.6) * math.radians(6), 0,
                                   math.sin(t * 0.5) * math.radians(20))
    stag["he"].keyframe_insert("rotation_euler", frame=f)

# Raven orbit + flap
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    a = t * 0.6
    rad = 16 + math.sin(t * 0.4) * 2
    raven_e.location = (rad * math.cos(a), rad * math.sin(a) - 5,
                         20 + math.sin(t * 1.2) * 2.0)
    raven_e.rotation_euler = (0, 0, a + math.pi/2)
    raven_e.keyframe_insert("location", frame=f)
    raven_e.keyframe_insert("rotation_euler", frame=f)
    flap = math.sin(t * 5.0) * math.radians(35)
    for w_e, side in rv_wings:
        w_e.rotation_euler = (side * flap, 0, 0)
        w_e.keyframe_insert("rotation_euler", frame=f)

# Castle flag flap
flag_main_obj = bpy.data.objects.get("c_main_flag")
if flag_main_obj:
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        flag_main_obj.rotation_euler = (math.sin(t * 4.0) * math.radians(15),
                                          math.cos(t * 3.5) * math.radians(10), 0)
        flag_main_obj.keyframe_insert("rotation_euler", frame=f)

# Clouds drift slow stormy
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 1.0,
                        by + math.cos(t * 0.25 + phase) * 0.8,
                        c_e.location.z)
        c_e.keyframe_insert("location", frame=f)

# Cottage smoke rise
for si in range(4):
    smoke_name = f"cot_smoke{si}"
    if smoke_name in bpy.data.objects:
        smoke = bpy.data.objects[smoke_name]
        base_z_sm = smoke.location.z
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            smoke.location.z = base_z_sm + math.sin(t * 0.8 + si) * 0.4
            smoke.scale = (1 + math.sin(t * 1.5) * 0.1, 1 + math.cos(t * 1.5) * 0.1, 1)
            smoke.keyframe_insert("location", frame=f)
            smoke.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 600 MIST drift low + 400 THISTLE petals float
# ============================================================
for m in mist_particles:
    phase = m["_phase"]; speed = m["_speed"]
    bx, by, bz = m["_base_x"], m["_base_y"], m["_base_z"]
    ax, ay = m["_amp_x"], m["_amp_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.85 + phase)
        z = bz + math.sin(t * 0.6 + phase) * 0.4
        m.location = (x, y, max(0.2, z))
        sc = 1 + math.sin(t * 1.0 + phase) * 0.15
        m.scale = (sc * 1.5, sc * 1.5, sc * 0.4)
        m.keyframe_insert("location", frame=f)
        m.keyframe_insert("scale", frame=f)

# 400 THISTLE PETALS float drift
for p in thistle_petals:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    drift_x = p["_drift_x"]; drift_y = p["_drift_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        z = bz - (speed * t * 0.3) % 12
        x = bx + drift_x * math.sin(t * 1.3 + phase) * 0.6
        y = by + drift_y * math.cos(t * 1.1 + phase) * 0.6
        p.location = (x, y, max(0.3, z))
        p.rotation_euler = (phase + t * 1.5, phase + t * 1.3, phase + t * 1.7)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_scotland_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_scottish_highland_castle] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_scottish_highland_castle] ONE moor + Highland mountains + castle 4 towers + loch + cottage + 8 highlanders kilt + bagpiper + chief claymore + 4 women + 4 Highland cows + 6 sheep + stag + raven + 25 thistles + 600 MIST + 400 THISTLE PETALS")
print("⭐ FIXES: 1 ground + 600 mist + 400 thistle petals (signature Highland mandatory) ⭐")
