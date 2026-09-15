"""
proc_mongolian_steppe_nomads_eagles.py — 270e MILESTONE procédural AuroraIA (135e qualité)
Mongolian steppe nomads eagles: gers + 4 horse riders + 4 wrestlers + Mongolia flag + eagles + 1000 grass blades + 500 golden eagles (DOUBLE MILESTONE PARTICLES)
FIXES : 1 ground steppe + DOUBLE signature herbe + aigles
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB270)

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

# Sky big steppe
M_SKY = mat("sky", (0.45, 0.72, 0.92, 1.0), 0.0, 0.7, emission=(0.45,0.70,0.90), emission_strength=2.0)
M_SKY_LOW = mat("sky_l", (0.85, 0.92, 0.95, 1.0), 0.0, 0.7, emission=(0.85,0.90,0.95), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.95, 0.78, 1.0), 0.0, 0.1, emission=(1.0,0.95,0.78), emission_strength=18.0)
M_CLOUD = mat("cl", (0.95, 0.95, 0.92, 1.0), 0.0, 0.85, emission=(0.95,0.95,0.92), emission_strength=1.0, alpha=0.85)

# Steppe ground
M_STEPPE = mat("st", (0.55, 0.62, 0.30, 1.0), 0.0, 0.85, emission=(0.52,0.60,0.30), emission_strength=0.3)
M_STEPPE_DARK = mat("std", (0.42, 0.50, 0.22, 1.0), 0.0, 0.92)
M_DIRT = mat("d", (0.45, 0.32, 0.20, 1.0), 0.0, 0.92)

# Grass blade colors
M_GRASS_G1 = mat("g1", (0.55, 0.72, 0.30, 1.0), 0.0, 0.55, emission=(0.52,0.70,0.30), emission_strength=0.5)
M_GRASS_G2 = mat("g2", (0.45, 0.65, 0.25, 1.0), 0.0, 0.55, emission=(0.42,0.62,0.25), emission_strength=0.5)
M_GRASS_Y = mat("gy", (0.85, 0.78, 0.30, 1.0), 0.0, 0.55, emission=(0.82,0.75,0.30), emission_strength=0.6)
M_GRASS_DRY = mat("gd", (0.72, 0.62, 0.30, 1.0), 0.0, 0.65, emission=(0.70,0.60,0.30), emission_strength=0.5)
GRASS_COLORS = [M_GRASS_G1, M_GRASS_G2, M_GRASS_Y, M_GRASS_DRY]

# Ger (yurt) white felt + wood + colorful door
M_FELT = mat("fl", (0.95, 0.92, 0.88, 1.0), 0.0, 0.85, emission=(0.92,0.90,0.85), emission_strength=0.3)
M_FELT_DARK = mat("fld", (0.65, 0.62, 0.55, 1.0), 0.0, 0.90)
M_WOOD = mat("w", (0.65, 0.42, 0.20, 1.0), 0.0, 0.65, emission=(0.62,0.40,0.20), emission_strength=0.3)
M_WOOD_DARK = mat("wd", (0.35, 0.22, 0.10, 1.0), 0.0, 0.75)
M_DOOR_RED = mat("dr", (0.85, 0.20, 0.20, 1.0), 0.0, 0.55, emission=(0.82,0.20,0.20), emission_strength=0.7)
M_DOOR_BLUE = mat("db", (0.20, 0.45, 0.85, 1.0), 0.0, 0.55, emission=(0.20,0.42,0.82), emission_strength=0.7)
M_ROOF_RING = mat("rr", (0.65, 0.32, 0.10, 1.0), 0.0, 0.75)

# Skin/horse
M_SKIN_TAN = mat("st2", (0.85, 0.65, 0.45, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.45), emission_strength=0.3)
M_HORSE_BROWN = mat("hb", (0.45, 0.28, 0.15, 1.0), 0.0, 0.65, emission=(0.42,0.28,0.15), emission_strength=0.3)
M_HORSE_BLACK = mat("hbk", (0.15, 0.12, 0.10, 1.0), 0.0, 0.65)
M_HORSE_WHITE = mat("hw", (0.92, 0.88, 0.82, 1.0), 0.0, 0.65, emission=(0.90,0.88,0.82), emission_strength=0.4)
M_HORSE_BAY = mat("hby", (0.62, 0.32, 0.18, 1.0), 0.0, 0.65, emission=(0.60,0.30,0.18), emission_strength=0.3)
HORSE_COLORS = [M_HORSE_BROWN, M_HORSE_BLACK, M_HORSE_WHITE, M_HORSE_BAY]
M_MANE = mat("mn", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)
M_HOOF = mat("hf", (0.12, 0.10, 0.08, 1.0), 0.2, 0.45)

# Deel (Mongol robe) colors signature
M_DEEL_BLUE = mat("dlb", (0.20, 0.45, 0.78, 1.0), 0.0, 0.55, emission=(0.20,0.42,0.75), emission_strength=0.6)
M_DEEL_RED = mat("dlr", (0.85, 0.18, 0.25, 1.0), 0.0, 0.55, emission=(0.82,0.18,0.25), emission_strength=0.7)
M_DEEL_GREEN = mat("dlg", (0.32, 0.65, 0.40, 1.0), 0.0, 0.55, emission=(0.30,0.62,0.40), emission_strength=0.6)
M_DEEL_ORANGE = mat("dlo", (1.0, 0.55, 0.20, 1.0), 0.0, 0.55, emission=(0.95,0.55,0.20), emission_strength=0.7)
M_DEEL_YELLOW = mat("dly", (0.95, 0.78, 0.25, 1.0), 0.0, 0.55, emission=(0.92,0.75,0.25), emission_strength=0.7)
DEEL_COLORS = [M_DEEL_BLUE, M_DEEL_RED, M_DEEL_GREEN, M_DEEL_ORANGE, M_DEEL_YELLOW]
M_SASH = mat("sa", (0.95, 0.78, 0.20, 1.0), 0.3, 0.30, emission=(0.92,0.75,0.20), emission_strength=0.8)

# Hat
M_HAT_FUR = mat("hfu", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)
M_HAT_POINT = mat("hp", (0.32, 0.20, 0.10, 1.0), 0.0, 0.75)

# Boot
M_BOOT = mat("bo", (0.32, 0.18, 0.10, 1.0), 0.2, 0.45)
M_BOOT_TIP = mat("bt", (0.55, 0.32, 0.15, 1.0), 0.3, 0.40)

# Hair/face
M_HAIR_BLACK = mat("hbl", (0.10, 0.08, 0.06, 1.0), 0.0, 0.85)
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Wrestler outfit (signature naked torso + small briefs)
M_BRIEFS_BLUE = mat("brb", (0.18, 0.45, 0.78, 1.0), 0.0, 0.55, emission=(0.18,0.42,0.75), emission_strength=0.5)
M_BRIEFS_RED = mat("brr", (0.85, 0.18, 0.25, 1.0), 0.0, 0.55, emission=(0.82,0.18,0.25), emission_strength=0.6)
M_VEST_BLUE = mat("vb", (0.20, 0.42, 0.78, 1.0), 0.0, 0.55, emission=(0.20,0.40,0.75), emission_strength=0.5)
M_VEST_RED = mat("vr", (0.85, 0.18, 0.25, 1.0), 0.0, 0.55, emission=(0.82,0.18,0.25), emission_strength=0.6)
WRESTLER_COLORS = [(M_BRIEFS_BLUE, M_VEST_BLUE), (M_BRIEFS_RED, M_VEST_RED)]

# Eagle (signature)
M_EAGLE_BROWN = mat("eb", (0.42, 0.25, 0.10, 1.0), 0.0, 0.55, emission=(0.40,0.25,0.10), emission_strength=0.4)
M_EAGLE_GOLD = mat("eg", (0.92, 0.72, 0.30, 1.0), 0.3, 0.40, emission=(0.88,0.70,0.30), emission_strength=1.2)
M_EAGLE_HEAD = mat("ehd", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.92,0.88,0.82), emission_strength=0.7)
M_BEAK_YELLOW = mat("by", (0.95, 0.78, 0.20, 1.0), 0.3, 0.20, emission=(0.92,0.75,0.20), emission_strength=1.0)
M_TALON = mat("tl", (0.55, 0.42, 0.20, 1.0), 0.4, 0.30)

# Mongolia flag (signature soyombo)
M_FLAG_RED = mat("fr", (0.85, 0.15, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.15,0.18), emission_strength=1.0)
M_FLAG_BLUE = mat("fb", (0.18, 0.32, 0.65, 1.0), 0.0, 0.45, emission=(0.18,0.30,0.62), emission_strength=0.9)
M_FLAG_GOLD = mat("fg", (0.95, 0.78, 0.20, 1.0), 0.3, 0.30, emission=(0.92,0.75,0.20), emission_strength=1.5)

# Lasso/uurga
M_LASSO_POLE = mat("lp", (0.55, 0.32, 0.15, 1.0), 0.0, 0.75)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Sun
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-40, 90, 30), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-40, 90, 30), mat_=M_SUN)
# Clouds
for ci in range(25):
    cx = random.uniform(-150, 150)
    cy = random.uniform(-150, 150)
    cz = random.uniform(45, 70)
    cloud_e = empty(f"cl{ci}_e", (cx, cy, cz))
    for cp in range(6):
        cpa = random.uniform(0, math.pi*2); cpr = random.uniform(0, 4)
        smooth_sphere(f"cl{ci}_p{cp}", r=random.uniform(2, 4), segs=14, rings=10,
                      loc=(math.cos(cpa)*cpr, math.sin(cpa)*cpr, random.uniform(-1, 1)),
                      parent=cloud_e, mat_=M_CLOUD, scale=(1.5, 1.5, 0.5))

# ============ ONE clean steppe ground ============
ground = beveled_cube("ground", (300, 300, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_STEPPE)
# Rolling hill bumps (organic 3D scattered, not stacked)
for hi in range(200):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 130)
    smooth_sphere(f"hl{hi}", r=random.uniform(1.5, 3.5), segs=12, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_STEPPE_DARK if hi % 3 == 0 else M_STEPPE, scale=(1.5, 1.4, 0.20))
# Dirt patches (path)
for di in range(40):
    smooth_sphere(f"di{di}", r=random.uniform(0.6, 1.0), segs=10, rings=6,
                  loc=(random.uniform(-50, 50), random.uniform(-50, 50), 0.10),
                  mat_=M_DIRT, scale=(1.3, 1.2, 0.20))

# ============ 4 GERS (yurts signature white felt) ============
def make_ger(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Cylindrical walls
    cyl(f"{name}_w", r=3, depth=2.2, segs=22, loc=(0, 0, 1.1), parent=base, mat_=M_FELT)
    # Felt panels (decorative bands)
    cyl(f"{name}_wp", r=3.02, depth=0.20, segs=22, loc=(0, 0, 2.0), parent=base, mat_=M_FELT_DARK)
    cyl(f"{name}_wp2", r=3.02, depth=0.15, segs=22, loc=(0, 0, 0.20), parent=base, mat_=M_FELT_DARK)
    # Conical roof
    smooth_cone(f"{name}_r", r1=3.2, r2=0.5, depth=1.5, segs=22, loc=(0, 0, 2.95),
                parent=base, mat_=M_FELT)
    # Crown ring (toono signature)
    cyl(f"{name}_cr", r=0.55, depth=0.20, segs=14, loc=(0, 0, 3.6),
        parent=base, mat_=M_ROOF_RING)
    # Roof poles (radiating from crown)
    for pi in range(16):
        pa = (pi / 16.0) * math.pi * 2
        pole_e = empty(f"{name}_p{pi}_e", (0, 0, 3.5), parent=base)
        pole_e.rotation_euler = (math.radians(60), 0, pa)
        cyl(f"{name}_p{pi}", r=0.04, depth=2.8, segs=6, loc=(0, 0, -1.4),
            parent=pole_e, mat_=M_WOOD)
    # Door (red/blue signature decoration)
    door_col = random.choice([M_DOOR_RED, M_DOOR_BLUE])
    door_e = empty(f"{name}_de", (0, -3.05, 0), parent=base)
    beveled_cube(f"{name}_d", (1.0, 0.08, 1.5), bevel_offset=0.04, loc=(0, 0, 0.75),
                 parent=door_e, mat_=door_col)
    # Door frame
    beveled_cube(f"{name}_df_l", (0.12, 0.10, 1.5), bevel_offset=0.02,
                 loc=(-0.55, 0, 0.75), parent=door_e, mat_=M_WOOD_DARK)
    beveled_cube(f"{name}_df_r", (0.12, 0.10, 1.5), bevel_offset=0.02,
                 loc=(0.55, 0, 0.75), parent=door_e, mat_=M_WOOD_DARK)
    beveled_cube(f"{name}_df_t", (1.2, 0.10, 0.15), bevel_offset=0.02,
                 loc=(0, 0, 1.50), parent=door_e, mat_=M_WOOD_DARK)
    # Decorative pattern on door (golden)
    for di in range(3):
        smooth_sphere(f"{name}_dd{di}", r=0.08, loc=(0, -0.05, 0.5 + di*0.30),
                      parent=door_e, mat_=M_SASH)
    # Smoke chimney
    cyl(f"{name}_ch", r=0.10, depth=0.6, segs=10, loc=(0, 0, 4.0),
        parent=base, mat_=M_WOOD_DARK)
    return base

ger_pos = [(-22, 10, math.radians(0)), (-8, -18, math.radians(45)),
            (15, -10, math.radians(-30)), (28, 12, math.radians(15))]
for i, (gx, gy, fac) in enumerate(ger_pos):
    make_ger(f"ger{i}", (gx, gy, 0), facing=fac)

# ============ 4 HORSE RIDERS (signature) ============
def make_horse(name, loc, scale=1.0, facing=0, parent_base=None):
    base = empty(name, loc, parent=parent_base) if parent_base else empty(name, loc)
    if not parent_base:
        base.rotation_euler = (0, 0, facing)
    horse_col = random.choice(HORSE_COLORS)
    # Body
    smooth_sphere(f"{name}_bo", r=0.6, segs=16, rings=12, loc=(0, 0, 1.2),
                  parent=base, mat_=horse_col, scale=(1.5, 0.85, 0.85))
    # Chest
    smooth_sphere(f"{name}_ch", r=0.55, segs=14, rings=10, loc=(0.7, 0, 1.30),
                  parent=base, mat_=horse_col, scale=(0.85, 0.85, 0.85))
    # Hindquarters
    smooth_sphere(f"{name}_hq", r=0.55, segs=14, rings=10, loc=(-0.7, 0, 1.25),
                  parent=base, mat_=horse_col, scale=(0.85, 0.85, 0.95))
    # Long neck
    neck_e = empty(f"{name}_ne", (0.85, 0, 1.45), parent=base)
    neck_e.rotation_euler = (0, math.radians(-30), 0)
    smooth_sphere(f"{name}_n", r=0.20, segs=14, rings=10, loc=(0, 0, 0.30),
                  parent=neck_e, mat_=horse_col, scale=(1, 1, 2.5))
    # Head
    head_h_e = empty(f"{name}_he", (0, 0, 0.85), parent=neck_e)
    smooth_sphere(f"{name}_h", r=0.22, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_h_e, mat_=horse_col, scale=(1.4, 0.85, 0.85))
    # Snout
    smooth_cone(f"{name}_sn", r1=0.18, r2=0.15, depth=0.25, segs=12, loc=(0.18, 0, -0.05),
                parent=head_h_e, mat_=horse_col).rotation_euler = (0, math.radians(90), 0)
    # Ears (signature pointy)
    for side in (-1, 1):
        smooth_cone(f"{name}_e{side}", r1=0.05, r2=0.01, depth=0.18, segs=8,
                    loc=(-0.10, side*0.10, 0.22), parent=head_h_e, mat_=horse_col)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.04, loc=(0.05, side*0.13, 0.05),
                      parent=head_h_e, mat_=M_EYE)
    # Mane (signature stripe)
    for mi in range(20):
        mi_t = mi / 20.0
        mx = 0.75 - mi_t * 1.5
        mz = 1.65 - mi_t * 0.55
        cyl(f"{name}_m{mi}", r=0.04, depth=0.18, segs=6,
            loc=(mx, 0, mz), parent=base, mat_=M_MANE)
    # Tail
    tail_e = empty(f"{name}_te", (-1.10, 0, 1.20), parent=base)
    for ti in range(8):
        cyl(f"{name}_t{ti}", r=0.06 - ti*0.005, depth=0.15, segs=8,
            loc=(-ti*0.08, 0, -ti*0.05), parent=tail_e, mat_=M_MANE)
    # 4 legs (galloping pose)
    leg_pos = [(0.55, 0.30), (0.55, -0.30), (-0.55, 0.30), (-0.55, -0.30)]
    legs_e = []
    for li, (lx, ly) in enumerate(leg_pos):
        leg_e = empty(f"{name}_le{li}", (lx, ly, 0.95), parent=base)
        # Upper leg
        cyl(f"{name}_ul{li}", r=0.10, depth=0.50, segs=10, loc=(0, 0, -0.25),
            parent=leg_e, mat_=horse_col)
        # Knee
        smooth_sphere(f"{name}_kn{li}", r=0.10, segs=12, rings=8, loc=(0, 0, -0.50),
                      parent=leg_e, mat_=horse_col)
        # Lower leg
        cyl(f"{name}_ll{li}", r=0.08, depth=0.45, segs=10, loc=(0, 0, -0.72),
            parent=leg_e, mat_=horse_col)
        # Hoof
        cyl(f"{name}_hf{li}", r=0.10, depth=0.10, segs=10, loc=(0, 0, -0.95),
            parent=leg_e, mat_=M_HOOF)
        legs_e.append(leg_e)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_h_e, "legs": legs_e}

def make_rider_on_horse(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    horse = make_horse(f"{name}_hr", (0, 0, 0), parent_base=base)
    # Rider sitting on horse
    rider_e = empty(f"{name}_re", (0, 0, 1.95), parent=base)
    deel_col = random.choice(DEEL_COLORS)
    # Body (deel robe)
    smooth_cone(f"{name}_rt", r1=0.30, r2=0.32, depth=0.85, segs=14, loc=(0, 0, 0.3),
                parent=rider_e, mat_=deel_col)
    # Yellow sash signature
    cyl(f"{name}_sa", r=0.33, depth=0.15, segs=14, loc=(0, 0, 0.10),
        parent=rider_e, mat_=M_SASH)
    # Legs (sit astride)
    for side in (-1, 1):
        leg_e = empty(f"{name}_lg{side}", (side*0.30, 0, -0.20), parent=rider_e)
        leg_e.rotation_euler = (math.radians(-90), 0, 0)
        cyl(f"{name}_l{side}", r=0.09, depth=0.50, segs=10, loc=(0, 0, -0.25),
            parent=leg_e, mat_=deel_col)
        # Boot
        beveled_cube(f"{name}_b{side}", (0.12, 0.30, 0.22), bevel_offset=0.03,
                     loc=(0, 0.15, -0.55), parent=leg_e, mat_=M_BOOT)
        # Boot tip up (signature)
        beveled_cube(f"{name}_bt{side}", (0.10, 0.10, 0.10), bevel_offset=0.02,
                     loc=(0, 0.32, -0.50), parent=leg_e, mat_=M_BOOT_TIP)
    # Arms holding reins
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.32, 0, 0.70), parent=rider_e)
        sh.rotation_euler = (math.radians(-60), 0, math.radians(side*20))
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=deel_col)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=deel_col)
    # Head
    head_r_e = empty(f"{name}_he", (0, 0, 1.0), parent=rider_e)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_r_e, mat_=M_SKIN_TAN)
    # Hair black
    for hi in range(12):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.10, segs=6,
            loc=(math.cos(ha)*0.10, math.sin(ha)*0.10, 0.10),
            parent=head_r_e, mat_=M_HAIR_BLACK)
    # POINTED HAT signature (with fur trim)
    hat_e = empty(f"{name}_ha", (0, 0, 0.20), parent=head_r_e)
    smooth_cone(f"{name}_ha_c", r1=0.22, r2=0.04, depth=0.40, segs=14, loc=(0, 0, 0.18),
                parent=hat_e, mat_=M_HAT_POINT)
    # Fur trim
    cyl(f"{name}_ha_f", r=0.24, depth=0.10, segs=14, loc=(0, 0, 0),
        parent=hat_e, mat_=M_HAT_FUR)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_r_e, mat_=M_EYE)
    # URUGA (lasso pole, signature)
    lasso_e = empty(f"{name}_uu", (0.30, -0.20, 0.50), parent=rider_e)
    lasso_e.rotation_euler = (math.radians(-50), 0, math.radians(-15))
    cyl(f"{name}_uu_p", r=0.025, depth=3, segs=8, loc=(0, 0, 0),
        parent=lasso_e, mat_=M_LASSO_POLE)
    # Loop at end
    for li in range(8):
        la = (li / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_uu_l{li}", r=0.025,
                      loc=(math.cos(la)*0.20, math.sin(la)*0.20, -1.45),
                      parent=lasso_e, mat_=M_LASSO_POLE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "horse": horse, "rider": rider_e, "he": head_r_e}

riders = []
rider_pos = [(-30, 0, math.radians(45)), (5, 25, math.radians(-30)),
              (-15, -25, math.radians(120)), (25, -20, math.radians(150))]
for i, (rx, ry, fac) in enumerate(rider_pos):
    r = make_rider_on_horse(f"rider{i}", (rx, ry, 0), facing=fac)
    riders.append(r)

# ============ 4 WRESTLERS (signature bökh) ============
def make_wrestler(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    briefs_col, vest_col = random.choice(WRESTLER_COLORS)
    # Bare torso (no shirt signature)
    smooth_cone(f"{name}_to", r1=0.32, r2=0.36, depth=0.75, segs=14, loc=(0, 0, 1.20),
                parent=base, mat_=M_SKIN_TAN)
    # Open VEST (signature shoulders/back only)
    for side in (-1, 1):
        beveled_cube(f"{name}_v{side}", (0.04, 0.10, 0.50), bevel_offset=0.005,
                     loc=(side*0.28, 0, 1.30), parent=base, mat_=vest_col)
    # Back panel
    beveled_cube(f"{name}_vb", (0.55, 0.04, 0.45), bevel_offset=0.02,
                 loc=(0, 0.35, 1.35), parent=base, mat_=vest_col)
    # Front collar wings
    for side in (-1, 1):
        beveled_cube(f"{name}_vc{side}", (0.20, 0.04, 0.30), bevel_offset=0.02,
                     loc=(side*0.18, -0.30, 1.45), parent=base, mat_=vest_col)
    # SMALL BRIEFS signature
    beveled_cube(f"{name}_br", (0.55, 0.30, 0.20), bevel_offset=0.05,
                 loc=(0, 0, 0.78), parent=base, mat_=briefs_col)
    # Muscled legs
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.13, depth=0.75, segs=10,
            loc=(side*0.15, 0, 0.38), parent=base, mat_=M_SKIN_TAN)
        # Boot
        beveled_cube(f"{name}_b{side}", (0.13, 0.30, 0.22), bevel_offset=0.03,
                     loc=(side*0.15, 0.05, 0.10), parent=base, mat_=M_BOOT)
        # Tip up
        beveled_cube(f"{name}_bt{side}", (0.11, 0.10, 0.10), bevel_offset=0.02,
                     loc=(side*0.15, 0.20, 0.15), parent=base, mat_=M_BOOT_TIP)
    # Arms muscled (wrestling grip pose)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.34, 0, 1.55), parent=base)
        sh.rotation_euler = (math.radians(-70), 0, math.radians(side*30))
        cyl(f"{name}_ua{side_idx}", r=0.10, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=M_SKIN_TAN)
        cyl(f"{name}_fa{side_idx}", r=0.09, depth=0.40, segs=10, loc=(0, 0, -0.60),
            parent=sh, mat_=M_SKIN_TAN)
    # Head
    head_wr_e = empty(f"{name}_he", (0, 0, 1.85), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_wr_e, mat_=M_SKIN_TAN)
    # Hair
    for hi in range(10):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.08, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.12),
            parent=head_wr_e, mat_=M_HAIR_BLACK)
    # POINTED HAT signature
    hat_e = empty(f"{name}_ha", (0, 0, 0.20), parent=head_wr_e)
    smooth_cone(f"{name}_ha_c", r1=0.18, r2=0.04, depth=0.30, segs=12, loc=(0, 0, 0.13),
                parent=hat_e, mat_=M_HAT_POINT)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_wr_e, mat_=M_EYE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_wr_e}

wrestlers = []
wr_pos = [(-5, 8, math.radians(90)), (-3, 8, math.radians(-90)),
           (3, 8, math.radians(90)), (5, 8, math.radians(-90))]
for i, (wx, wy, fac) in enumerate(wr_pos):
    w = make_wrestler(f"wr{i}", (wx, wy, 0), facing=fac)
    wrestlers.append(w)

# ============ MONGOLIA FLAG (signature soyombo) ============
flag_e = empty("flag", (-45, 0, 0))
cyl("fl_p", r=0.12, depth=14, segs=10, loc=(0, 0, 7), parent=flag_e, mat_=M_WOOD_DARK)
# 3 vertical stripes (red, blue, red)
for si, (sx_f, col) in enumerate([(0.6, M_FLAG_RED), (2.0, M_FLAG_BLUE), (3.4, M_FLAG_RED)]):
    beveled_cube(f"fl_s{si}", (1.4, 0.05, 2.5), bevel_offset=0.06, loc=(sx_f, 0, 12.5),
                 parent=flag_e, mat_=col)
# SOYOMBO symbol (signature)
sb_e = empty("fl_sb", (0.6, -0.06, 12.5), parent=flag_e)
# Flame top
smooth_cone("fl_sb_f", r1=0.12, r2=0.02, depth=0.30, segs=8, loc=(0, 0, 0.85),
            parent=sb_e, mat_=M_FLAG_GOLD)
# Sun
smooth_sphere("fl_sb_su", r=0.10, loc=(0, 0, 0.55), parent=sb_e, mat_=M_FLAG_GOLD)
# Moon (crescent)
smooth_sphere("fl_sb_mo", r=0.08, loc=(0, 0, 0.30), parent=sb_e, mat_=M_FLAG_GOLD, scale=(1, 0.3, 1))
# Triangles (down arrows)
for ti in range(2):
    tz_f = -0.10 - ti * 0.25
    beveled_cube(f"fl_sb_t{ti}", (0.16, 0.04, 0.05), bevel_offset=0.005,
                 loc=(0, 0, tz_f), parent=sb_e, mat_=M_FLAG_GOLD)
# Yin yang
smooth_sphere("fl_sb_y", r=0.10, loc=(0, 0, -0.45), parent=sb_e, mat_=M_FLAG_GOLD)
# Rectangles vertical bars
for si_b in (-1, 1):
    beveled_cube(f"fl_sb_b{si_b}", (0.03, 0.04, 0.80), bevel_offset=0.005,
                 loc=(si_b*0.18, 0, 0.20), parent=sb_e, mat_=M_FLAG_GOLD)
flag_e["_phase"] = 0

# ============================================================
# ⭐ 1000 GRASS BLADES + 500 GOLDEN EAGLES (DOUBLE MILESTONE PARTICLES)
# ============================================================
grass_blades = []
for i in range(1000):
    px = random.uniform(-120, 120)
    py = random.uniform(-120, 120)
    pz = 0.10
    # Grass blade is a tall thin cube/triangle
    g_col = random.choice(GRASS_COLORS)
    blade = beveled_cube(f"gr{i}", (0.04, 0.04, random.uniform(0.4, 0.9)), bevel_offset=0.005,
                          loc=(px, py, pz + 0.3), mat_=g_col)
    blade["_phase"] = random.uniform(0, math.pi*2)
    blade["_base_x"] = px; blade["_base_y"] = py
    blade["_speed"] = random.uniform(0.8, 2.0)
    grass_blades.append(blade)

# 500 golden eagles flying
eagles = []
for i in range(500):
    px = random.uniform(-130, 130)
    py = random.uniform(-130, 130)
    pz = random.uniform(12, 55)
    e_e = empty(f"ea{i}", (px, py, pz))
    # Body
    smooth_sphere(f"ea{i}_bo", r=0.22, segs=12, rings=10, loc=(0, 0, 0),
                  parent=e_e, mat_=M_EAGLE_BROWN, scale=(1.4, 0.85, 0.85))
    # Golden head (signature)
    smooth_sphere(f"ea{i}_h", r=0.10, segs=10, rings=8, loc=(0.25, 0, 0.05),
                  parent=e_e, mat_=M_EAGLE_GOLD)
    # Beak hooked
    cyl(f"ea{i}_be", r=0.018, depth=0.12, segs=6, loc=(0.36, 0, 0),
        parent=e_e, mat_=M_BEAK_YELLOW).rotation_euler = (0, math.radians(110), 0)
    # WINGS (signature spread)
    wing_e_l = empty(f"ea{i}_wl_e", (0, -0.10, 0), parent=e_e)
    wing_e_r = empty(f"ea{i}_wr_e", (0, 0.10, 0), parent=e_e)
    # Wing planes
    beveled_cube(f"ea{i}_wl", (0.40, 0.85, 0.04), bevel_offset=0.01, loc=(0, -0.45, 0),
                 parent=wing_e_l, mat_=M_EAGLE_BROWN)
    beveled_cube(f"ea{i}_wr", (0.40, 0.85, 0.04), bevel_offset=0.01, loc=(0, 0.45, 0),
                 parent=wing_e_r, mat_=M_EAGLE_BROWN)
    # Wing tip primary feathers (signature spread)
    for fi in range(5):
        fa = (fi / 5.0 - 0.5) * math.radians(50)
        beveled_cube(f"ea{i}_wtl{fi}", (0.08, 0.30, 0.02), bevel_offset=0.005,
                     loc=(math.sin(fa)*0.15, -0.90 + math.cos(fa)*0.20, 0),
                     parent=wing_e_l, mat_=M_EAGLE_BROWN).rotation_euler = (0, 0, fa)
        beveled_cube(f"ea{i}_wtr{fi}", (0.08, 0.30, 0.02), bevel_offset=0.005,
                     loc=(math.sin(fa)*0.15, 0.90 - math.cos(fa)*0.20, 0),
                     parent=wing_e_r, mat_=M_EAGLE_BROWN).rotation_euler = (0, 0, fa)
    # Tail fan
    for ti in range(5):
        ta = (ti - 2) * math.radians(15)
        beveled_cube(f"ea{i}_t{ti}", (0.04, 0.25, 0.02), bevel_offset=0.005,
                     loc=(-0.35, math.sin(ta)*0.10, 0), parent=e_e,
                     mat_=M_EAGLE_BROWN).rotation_euler = (0, 0, ta)
    # Talons
    cyl(f"ea{i}_ta", r=0.02, depth=0.08, segs=6, loc=(0, 0, -0.10),
        parent=e_e, mat_=M_TALON)
    e_e["_phase"] = random.uniform(0, math.pi*2)
    e_e["_base_x"] = px; e_e["_base_y"] = py; e_e["_base_z"] = pz
    e_e["_speed"] = random.uniform(0.4, 1.2)
    e_e["_radius"] = random.uniform(6, 18)
    e_e["_wl"] = wing_e_l; e_e["_wr"] = wing_e_r
    eagles.append(e_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Horse riders gallop (legs cycle + body bob + horse forward motion)
for r in riders:
    phase = r["root"]["_phase"]
    fac = r["root"].rotation_euler.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Gallop bounce
        r["root"].location.z = abs(math.sin(t * 6.0 + phase)) * 0.20
        r["root"].rotation_euler = (math.sin(t * 6.0 + phase) * math.radians(4), 0,
                                     fac + math.sin(t * 0.5 + phase) * math.radians(2))
        r["root"].keyframe_insert("location", frame=f)
        r["root"].keyframe_insert("rotation_euler", frame=f)
        # Horse legs gallop (4 legs phase)
        for li, leg in enumerate(r["horse"]["legs"]):
            leg_phase = li * math.pi / 2
            leg.rotation_euler = (math.sin(t * 6.0 + phase + leg_phase) * math.radians(35), 0, 0)
            leg.keyframe_insert("rotation_euler", frame=f)
        # Horse head bob
        r["horse"]["he"].rotation_euler = (math.sin(t * 6.0 + phase) * math.radians(8), 0, 0)
        r["horse"]["he"].keyframe_insert("rotation_euler", frame=f)
        # Rider head bob
        r["he"].rotation_euler = (math.sin(t * 6.0 + phase) * math.radians(5), 0, 0)
        r["he"].keyframe_insert("rotation_euler", frame=f)

# Wrestlers grapple
for w in wrestlers:
    phase = w["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        w["root"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(8), 0,
                                     w["root"].rotation_euler.z + math.sin(t * 1.5 + phase) * math.radians(10))
        w["root"].location.z = math.sin(t * 3.0 + phase) * 0.08
        w["root"].keyframe_insert("rotation_euler", frame=f)
        w["root"].keyframe_insert("location", frame=f)
        w["he"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(10), 0,
                                   math.cos(t * 2.0 + phase) * math.radians(15))
        w["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(10))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 1000 grass blades sway
for g in grass_blades:
    phase = g["_phase"]; speed = g["_speed"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        g.rotation_euler = (math.sin(t * speed + phase) * math.radians(20),
                             math.cos(t * speed * 0.8 + phase) * math.radians(15), 0)
        g.keyframe_insert("rotation_euler", frame=f)

# 500 eagles fly in circles with wing flap
for e in eagles:
    phase = e["_phase"]; speed = e["_speed"]; radius = e["_radius"]
    bx, by, bz = e["_base_x"], e["_base_y"], e["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * radius
        y = by + math.sin(t * speed + phase) * radius
        z = bz + math.sin(t * speed * 1.2 + phase) * 3
        e.location = (x, y, z)
        e.rotation_euler = (0, 0, math.atan2(math.cos(t * speed + phase),
                                              -math.sin(t * speed + phase)))
        e.keyframe_insert("location", frame=f)
        e.keyframe_insert("rotation_euler", frame=f)
        # Wing flap slow (soaring)
        wing_a = math.sin(t * 3.0 + phase) * math.radians(20)
        e["_wl"].rotation_euler = (0, wing_a, 0)
        e["_wr"].rotation_euler = (0, -wing_a, 0)
        e["_wl"].keyframe_insert("rotation_euler", frame=f)
        e["_wr"].keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_mongolia_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_mongolian_steppe_nomads_eagles] DONE → {out_glb} ({size_mb:.2f} MB)")
print("⭐ 270e MILESTONE 135e qualité ⭐")
print("Mongolia steppe: 4 gers (white felt + 16 radial roof poles + crown ring + decorative doors red/blue + smoke chimneys) + 4 horse riders galloping (4-leg cycle animation + deel robes + sash + pointed fur hats + uurga lasso pole) + 4 traditional bökh wrestlers (vest + briefs + pointed hats + boots) + Mongolia flag with soyombo symbol + 25 clouds + 1000 GRASS BLADES + 500 GOLDEN EAGLES (DOUBLE MILESTONE)")
print("⭐ DOUBLE PARTICLES MILESTONE: 1 steppe ground + 1000 grass blades + 500 golden eagles signature Mongolia ⭐")
