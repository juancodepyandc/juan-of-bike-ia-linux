"""
proc_botswana_okavango_delta_safari.py — 286e procédural AuroraIA (151e qualité)
Botswana Okavango Delta safari: 4 African elephants + 4 giraffes + 3 lions pride + 2 hippos + 3 mokoro canoes + Bantu villagers + thatched huts + Botswana flag + 600 papyrus reeds + 400 flamingos
FIXES : 1 ground wetland + signature reeds + flamingos
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB286)

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

# Sky African dawn
M_SKY = mat("sky", (0.85, 0.65, 0.45, 1.0), 0.0, 0.7, emission=(0.82,0.62,0.45), emission_strength=2.0)
M_SKY_LOW = mat("sky_l", (1.0, 0.78, 0.55, 1.0), 0.0, 0.7, emission=(0.95,0.78,0.55), emission_strength=1.7)
M_SUN = mat("sun", (1.0, 0.85, 0.45, 1.0), 0.0, 0.1, emission=(1.0,0.85,0.45), emission_strength=18.0)

# Wetland ground (signature delta)
M_WETLAND = mat("wt", (0.55, 0.62, 0.32, 1.0), 0.0, 0.75, emission=(0.52,0.60,0.32), emission_strength=0.4)
M_WETLAND_DARK = mat("wtd", (0.32, 0.42, 0.22, 1.0), 0.0, 0.85)
M_DELTA_WATER = mat("dw", (0.42, 0.62, 0.55, 1.0), 0.2, 0.20, emission=(0.42,0.62,0.55), emission_strength=1.5, alpha=0.78)
M_DELTA_DEEP = mat("dwd", (0.22, 0.42, 0.45, 1.0), 0.2, 0.25, alpha=0.85)
M_REED = mat("re", (0.78, 0.78, 0.32, 1.0), 0.0, 0.65, emission=(0.75,0.75,0.32), emission_strength=0.4)
M_PAPYRUS = mat("pp", (0.42, 0.55, 0.20, 1.0), 0.0, 0.65, emission=(0.40,0.52,0.20), emission_strength=0.5)
M_PAPYRUS_HEAD = mat("pph", (0.85, 0.78, 0.30, 1.0), 0.0, 0.55, emission=(0.82,0.75,0.30), emission_strength=0.7)
M_LILY_PAD = mat("lp", (0.30, 0.65, 0.30, 1.0), 0.0, 0.55, emission=(0.28,0.62,0.30), emission_strength=0.4)

# Acacia tree
M_TRUNK = mat("tk", (0.45, 0.32, 0.18, 1.0), 0.0, 0.85, emission=(0.42,0.30,0.18), emission_strength=0.2)
M_CANOPY = mat("ca", (0.32, 0.55, 0.25, 1.0), 0.0, 0.65, emission=(0.30,0.52,0.25), emission_strength=0.4)
M_CANOPY_DARK = mat("cad", (0.20, 0.38, 0.18, 1.0), 0.0, 0.75)

# Elephant
M_ELEPHANT_GRAY = mat("eg", (0.52, 0.52, 0.55, 1.0), 0.0, 0.85, emission=(0.50,0.50,0.55), emission_strength=0.3)
M_ELEPHANT_DARK = mat("egd", (0.32, 0.32, 0.35, 1.0), 0.0, 0.92)
M_ELEPHANT_PINK = mat("egp", (0.65, 0.55, 0.55, 1.0), 0.0, 0.75)
M_TUSK = mat("tu", (0.92, 0.88, 0.78, 1.0), 0.2, 0.40, emission=(0.88,0.85,0.78), emission_strength=0.5)

# Giraffe (signature spotted)
M_GIRAFFE_TAN = mat("gt", (0.95, 0.78, 0.45, 1.0), 0.0, 0.75, emission=(0.92,0.75,0.45), emission_strength=0.4)
M_GIRAFFE_SPOT = mat("gs", (0.55, 0.32, 0.15, 1.0), 0.0, 0.75)
M_GIRAFFE_HORN = mat("gh", (0.42, 0.28, 0.18, 1.0), 0.0, 0.65)

# Lion
M_LION_TAN = mat("lt", (0.92, 0.72, 0.42, 1.0), 0.0, 0.75, emission=(0.88,0.70,0.42), emission_strength=0.3)
M_LION_MANE = mat("lm", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85, emission=(0.52,0.30,0.15), emission_strength=0.4)
M_LION_BELLY = mat("lb", (0.95, 0.85, 0.62, 1.0), 0.0, 0.65)

# Hippo
M_HIPPO_GRAY = mat("hg", (0.55, 0.45, 0.42, 1.0), 0.0, 0.65, emission=(0.52,0.45,0.42), emission_strength=0.3)
M_HIPPO_DARK = mat("hgd", (0.32, 0.28, 0.25, 1.0), 0.0, 0.75)
M_HIPPO_PINK = mat("hp_pk", (0.85, 0.55, 0.45, 1.0), 0.0, 0.55, emission=(0.82,0.55,0.45), emission_strength=0.4)

# Mokoro canoe (signature dugout)
M_MOKORO_WOOD = mat("mw", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85, emission=(0.52,0.30,0.15), emission_strength=0.3)
M_MOKORO_DARK = mat("mwd", (0.32, 0.18, 0.10, 1.0), 0.0, 0.92)

# Bantu villager skin
M_SKIN_DARK = mat("sk", (0.42, 0.28, 0.18, 1.0), 0.0, 0.55, emission=(0.40,0.28,0.18), emission_strength=0.3)
M_HAIR_BLACK = mat("hb", (0.08, 0.06, 0.05, 1.0), 0.0, 0.85)

# Bantu clothing colorful
M_CLOTH_RED = mat("cr", (0.85, 0.20, 0.22, 1.0), 0.0, 0.55, emission=(0.82,0.20,0.22), emission_strength=0.5)
M_CLOTH_YELLOW = mat("cy", (1.0, 0.78, 0.20, 1.0), 0.0, 0.55, emission=(0.95,0.75,0.20), emission_strength=0.7)
M_CLOTH_GREEN = mat("cg", (0.20, 0.55, 0.32, 1.0), 0.0, 0.55, emission=(0.20,0.52,0.32), emission_strength=0.5)
M_CLOTH_BLUE = mat("cb", (0.20, 0.42, 0.78, 1.0), 0.0, 0.55, emission=(0.20,0.42,0.75), emission_strength=0.5)
CLOTH_COLORS = [M_CLOTH_RED, M_CLOTH_YELLOW, M_CLOTH_GREEN, M_CLOTH_BLUE]

# Thatched hut
M_HUT_WALL = mat("hw", (0.78, 0.55, 0.32, 1.0), 0.0, 0.85, emission=(0.75,0.55,0.32), emission_strength=0.3)
M_THATCH = mat("th", (0.65, 0.45, 0.20, 1.0), 0.0, 0.85, emission=(0.62,0.42,0.20), emission_strength=0.3)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Botswana flag
M_FLAG_BLUE = mat("fb", (0.42, 0.65, 0.85, 1.0), 0.0, 0.45, emission=(0.42,0.62,0.82), emission_strength=1.0)
M_FLAG_BLACK = mat("fbk", (0.10, 0.08, 0.06, 1.0), 0.0, 0.45)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)

# Flamingo (signature pink)
M_FLAMINGO_PINK = mat("fp", (1.0, 0.55, 0.75, 1.0), 0.0, 0.55, emission=(0.95,0.55,0.72), emission_strength=1.5)
M_FLAMINGO_BLACK = mat("fpb", (0.10, 0.10, 0.10, 1.0), 0.0, 0.55)
M_FLAMINGO_BEAK = mat("fpk", (0.55, 0.35, 0.20, 1.0), 0.2, 0.45)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=10, segs=24, rings=18, loc=(-40, 110, 30), mat_=M_SUN)
for sh in range(4):
    smooth_sphere(f"sun_h{sh}", r=10 + sh*1.2, segs=24, rings=18, loc=(-40, 110, 30), mat_=M_SUN)

# ============ ONE clean wetland ground ============
ground = beveled_cube("ground", (260, 260, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_WETLAND)
# Wetland bumps (organic 3D)
for hi in range(200):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 120)
    smooth_sphere(f"hl{hi}", r=random.uniform(1.0, 2.5), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_WETLAND_DARK if hi % 3 == 0 else M_WETLAND, scale=(1.4, 1.3, 0.18))

# ============ DELTA WATER CHANNELS (signature) ============
delta_e = empty("delta", (0, 0, 0))
# Main waterway
beveled_cube("dw_m", (180, 25, 0.20), bevel_offset=0.08, loc=(0, -30, 0.20),
             parent=delta_e, mat_=M_DELTA_WATER)
beveled_cube("dw_md", (175, 22, 0.15), bevel_offset=0.06, loc=(0, -30, 0.25),
             parent=delta_e, mat_=M_DELTA_DEEP)
# Side channels
for ci in range(4):
    cy = -15 + ci * 20
    beveled_cube(f"dw_s{ci}", (40, 8, 0.20), bevel_offset=0.06,
                 loc=(random.uniform(-50, 50), cy, 0.20),
                 parent=delta_e, mat_=M_DELTA_WATER).rotation_euler = (0, 0, random.uniform(-0.3, 0.3))
# Lily pads
for li in range(30):
    lx = random.uniform(-80, 80); ly = random.uniform(-50, 0)
    cyl(f"lily{li}", r=random.uniform(0.4, 0.8), depth=0.04, segs=12,
        loc=(lx, ly, 0.32), parent=delta_e, mat_=M_LILY_PAD)

# ============ 6 ACACIA TREES (signature flat-top) ============
def make_acacia(name, loc, scale=1.0):
    base = empty(name, loc)
    # Trunk
    h = random.uniform(7, 10)
    for ti in range(int(h)):
        cyl(f"{name}_t{ti}", r=0.30 - ti*0.015, depth=1.0, segs=10,
            loc=(0, 0, ti + 0.5), parent=base, mat_=M_TRUNK)
    # FLAT-TOP CANOPY (signature acacia)
    canopy_e = empty(f"{name}_ce", (0, 0, h), parent=base)
    # Wide flat canopy disc
    for ci in range(15):
        ca = random.uniform(0, math.pi*2); cr = random.uniform(0, 4)
        smooth_sphere(f"{name}_c{ci}", r=random.uniform(1.5, 2.5), segs=12, rings=8,
                      loc=(math.cos(ca)*cr, math.sin(ca)*cr, random.uniform(-0.3, 0.5)),
                      parent=canopy_e, mat_=M_CANOPY if ci % 2 else M_CANOPY_DARK,
                      scale=(1.4, 1.4, 0.55))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "canopy": canopy_e}

acacias = []
for i in range(6):
    angle = random.uniform(0, math.pi*2)
    rad = random.uniform(40, 90)
    ax = math.cos(angle) * rad; ay = math.sin(angle) * rad
    if ay > 0:
        acacias.append(make_acacia(f"ac{i}", (ax, ay, 0)))

# ============ 4 AFRICAN ELEPHANTS (signature) ============
def make_elephant(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body (signature massive)
    smooth_sphere(f"{name}_bo", r=1.1, segs=14, rings=12, loc=(0, 0, 2.2),
                  parent=base, mat_=M_ELEPHANT_GRAY, scale=(1.6, 0.85, 0.85))
    # Belly
    smooth_sphere(f"{name}_be", r=1.0, segs=12, rings=10, loc=(0, 0, 1.8),
                  parent=base, mat_=M_ELEPHANT_GRAY, scale=(1.5, 0.85, 0.55))
    # Head
    head_e_e = empty(f"{name}_he", (1.50, 0, 2.5), parent=base)
    smooth_sphere(f"{name}_h", r=0.65, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_e_e, mat_=M_ELEPHANT_GRAY, scale=(1.3, 1.0, 1.0))
    # HUGE EARS (signature African elephant)
    for side in (-1, 1):
        ear_e = empty(f"{name}_er{side}_e", (0, side*0.50, 0.10), parent=head_e_e)
        ear_e.rotation_euler = (0, 0, math.radians(side*30))
        # Big fan-shape ear
        smooth_sphere(f"{name}_er{side}", r=0.70, segs=14, rings=10, loc=(0, 0.30, 0),
                      parent=ear_e, mat_=M_ELEPHANT_GRAY, scale=(0.15, 1.4, 1.4))
    # TRUNK (signature long curved)
    trunk_e = empty(f"{name}_tr_e", (0.55, 0, -0.20), parent=head_e_e)
    trunk_e.rotation_euler = (0, math.radians(-20), 0)
    for ti in range(8):
        ta = (ti / 8.0) * math.pi * 0.5
        cyl(f"{name}_tr{ti}", r=0.18 - ti*0.01, depth=0.20, segs=10,
            loc=(math.sin(ta)*0.10, 0, -ti*0.18),
            parent=trunk_e, mat_=M_ELEPHANT_GRAY)
    # TUSKS (signature)
    for side in (-1, 1):
        tusk_e = empty(f"{name}_tu{side}_e", (0.55, side*0.18, -0.20), parent=head_e_e)
        tusk_e.rotation_euler = (0, math.radians(20), math.radians(side*10))
        for tui in range(4):
            cyl(f"{name}_tu{side}_{tui}", r=0.07 - tui*0.008, depth=0.18, segs=10,
                loc=(0, 0, -tui*0.18), parent=tusk_e, mat_=M_TUSK)
    # Eyes (small)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.05, loc=(0.30, side*0.30, 0.10),
                      parent=head_e_e, mat_=M_EYE)
    # 4 massive pillar legs
    for li, (lx_e, ly_e) in enumerate([(0.85, 0.50), (0.85, -0.50), (-0.85, 0.50), (-0.85, -0.50)]):
        leg_e = empty(f"{name}_le{li}", (lx_e, ly_e, 1.20), parent=base)
        cyl(f"{name}_ul{li}", r=0.30, depth=0.70, segs=12, loc=(0, 0, -0.35),
            parent=leg_e, mat_=M_ELEPHANT_GRAY)
        cyl(f"{name}_ll{li}", r=0.28, depth=0.60, segs=12, loc=(0, 0, -1.0),
            parent=leg_e, mat_=M_ELEPHANT_GRAY)
        # Foot
        cyl(f"{name}_ft{li}", r=0.35, depth=0.20, segs=12, loc=(0, 0, -1.40),
            parent=leg_e, mat_=M_ELEPHANT_DARK)
    # Tail with tuft
    tail_e = empty(f"{name}_te", (-1.60, 0, 2.30), parent=base)
    for ti in range(4):
        cyl(f"{name}_t{ti}", r=0.06 - ti*0.005, depth=0.20, segs=8,
            loc=(0, 0, -ti*0.20), parent=tail_e, mat_=M_ELEPHANT_GRAY)
    smooth_sphere(f"{name}_tu_t", r=0.10, segs=10, rings=8, loc=(0, 0, -0.95),
                  parent=tail_e, mat_=M_HAIR_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "trunk": trunk_e, "he": head_e_e}

elephants = []
elephant_pos = [(-15, 15, math.radians(20)), (-3, 18, math.radians(0)),
                 (10, 15, math.radians(-20)), (22, 18, math.radians(-45))]
for i, (ex, ey, fac) in enumerate(elephant_pos):
    el = make_elephant(f"el{i}", (ex, ey, 0), facing=fac)
    elephants.append(el)

# ============ 4 GIRAFFES (signature spotted long neck) ============
def make_giraffe(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_bo", r=0.7, segs=14, rings=12, loc=(0, 0, 2.5),
                  parent=base, mat_=M_GIRAFFE_TAN, scale=(1.5, 0.85, 0.85))
    # SPOTS (signature)
    for spi in range(30):
        sa = random.uniform(0, math.pi*2)
        sx_g = random.uniform(-0.8, 0.8)
        sy_g = math.cos(sa) * 0.50
        sz_g = math.sin(sa) * 0.50 + 2.5
        smooth_sphere(f"{name}_sp{spi}", r=0.08, segs=8, rings=6,
                      loc=(sx_g, sy_g, sz_g), parent=base, mat_=M_GIRAFFE_SPOT)
    # LONG NECK (signature 4m+)
    neck_e = empty(f"{name}_ne", (0.50, 0, 3.0), parent=base)
    neck_e.rotation_euler = (0, math.radians(-30), 0)
    for ni in range(12):
        cyl(f"{name}_n{ni}", r=0.22 - ni*0.005, depth=0.35, segs=10,
            loc=(0, 0, ni*0.35 + 0.2), parent=neck_e, mat_=M_GIRAFFE_TAN)
        # Spots on neck
        if ni % 2 == 0:
            sma = random.uniform(0, math.pi*2)
            smooth_sphere(f"{name}_nsp{ni}", r=0.06,
                          loc=(math.cos(sma)*0.18, math.sin(sma)*0.18, ni*0.35 + 0.2),
                          parent=neck_e, mat_=M_GIRAFFE_SPOT)
    # Head
    head_g_e = empty(f"{name}_he", (0, 0, 4.5), parent=neck_e)
    smooth_sphere(f"{name}_h", r=0.20, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_g_e, mat_=M_GIRAFFE_TAN, scale=(1.5, 0.85, 0.85))
    # Snout
    smooth_sphere(f"{name}_sn", r=0.13, segs=10, rings=8, loc=(0.20, 0, -0.05),
                  parent=head_g_e, mat_=M_GIRAFFE_TAN)
    # OSSICONES (signature horn knobs)
    for side in (-1, 1):
        cyl(f"{name}_oc{side}", r=0.04, depth=0.18, segs=8,
            loc=(-0.05, side*0.10, 0.20), parent=head_g_e, mat_=M_GIRAFFE_HORN)
        smooth_sphere(f"{name}_oct{side}", r=0.06,
                      loc=(-0.05, side*0.10, 0.32), parent=head_g_e, mat_=M_HAIR_BLACK)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.10, segs=10, rings=8,
                      loc=(-0.10, side*0.18, 0.15), parent=head_g_e, mat_=M_GIRAFFE_TAN)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.04, loc=(0.10, side*0.13, 0.04),
                      parent=head_g_e, mat_=M_EYE)
    # Mane (signature short tufts down neck)
    for mi in range(8):
        for ms in (-1, 0, 1):
            beveled_cube(f"{name}_mn{mi}_{ms}", (0.05, 0.04, 0.10), bevel_offset=0.005,
                         loc=(0, ms*0.06, mi*0.55 + 0.4),
                         parent=neck_e, mat_=M_GIRAFFE_SPOT)
    # 4 long legs (signature)
    for li, (lx_g, ly_g) in enumerate([(0.55, 0.30), (0.55, -0.30), (-0.55, 0.30), (-0.55, -0.30)]):
        leg_e = empty(f"{name}_le{li}", (lx_g, ly_g, 2.10), parent=base)
        cyl(f"{name}_ul{li}", r=0.12, depth=1.0, segs=10, loc=(0, 0, -0.50),
            parent=leg_e, mat_=M_GIRAFFE_TAN)
        cyl(f"{name}_ll{li}", r=0.10, depth=0.95, segs=10, loc=(0, 0, -1.55),
            parent=leg_e, mat_=M_GIRAFFE_TAN)
        # Hoof
        cyl(f"{name}_hf{li}", r=0.13, depth=0.10, segs=10, loc=(0, 0, -2.05),
            parent=leg_e, mat_=M_GIRAFFE_SPOT)
        # Spots on legs
        for sl in range(2):
            smooth_sphere(f"{name}_lsp{li}_{sl}", r=0.05,
                          loc=(0, ly_g*0.4, -0.30 - sl*0.50),
                          parent=leg_e, mat_=M_GIRAFFE_SPOT)
    # Tail
    cyl(f"{name}_t", r=0.05, depth=0.50, segs=8, loc=(-0.80, 0, 2.40),
        parent=base, mat_=M_GIRAFFE_TAN).rotation_euler = (0, math.radians(95), 0)
    smooth_sphere(f"{name}_tu_t", r=0.08, loc=(-1.10, 0, 2.40),
                  parent=base, mat_=M_HAIR_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "neck": neck_e, "he": head_g_e}

giraffes = []
giraffe_pos = [(-35, 45, math.radians(45)), (35, 45, math.radians(-45)),
                (-20, 60, math.radians(15)), (20, 60, math.radians(-15))]
for i, (gx, gy, fac) in enumerate(giraffe_pos):
    g = make_giraffe(f"gi{i}", (gx, gy, 0), facing=fac)
    giraffes.append(g)

# ============ 3 LIONS (pride) ============
def make_lion(name, loc, has_mane=False, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_bo", r=0.55, segs=14, rings=12, loc=(0, 0, 0.90),
                  parent=base, mat_=M_LION_TAN, scale=(1.8, 0.85, 0.85))
    # Belly cream
    smooth_sphere(f"{name}_be", r=0.50, segs=12, rings=10, loc=(0, 0, 0.75),
                  parent=base, mat_=M_LION_BELLY, scale=(1.7, 0.85, 0.55))
    # Head
    head_l_e = empty(f"{name}_he", (1.20, 0, 0.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.35, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_l_e, mat_=M_LION_TAN, scale=(1.3, 0.95, 0.95))
    # MANE (signature male lion)
    if has_mane:
        for mi in range(20):
            ma = random.uniform(0, math.pi*2)
            smooth_sphere(f"{name}_mn{mi}", r=0.20, segs=10, rings=8,
                          loc=(math.cos(ma)*0.35, math.sin(ma)*0.40, random.uniform(-0.10, 0.10)),
                          parent=head_l_e, mat_=M_LION_MANE)
    # Snout
    smooth_sphere(f"{name}_sn", r=0.18, segs=12, rings=10, loc=(0.25, 0, -0.08),
                  parent=head_l_e, mat_=M_LION_TAN)
    # Nose pink
    smooth_sphere(f"{name}_no", r=0.06, loc=(0.40, 0, -0.05),
                  parent=head_l_e, mat_=M_HIPPO_PINK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.04, loc=(0.08, side*0.15, 0.05),
                      parent=head_l_e, mat_=M_GIRAFFE_HORN)
        smooth_sphere(f"{name}_ep{side}", r=0.02, loc=(0.11, side*0.15, 0.05),
                      parent=head_l_e, mat_=M_EYE)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.07, segs=10, rings=8,
                      loc=(-0.05, side*0.22, 0.20), parent=head_l_e, mat_=M_LION_TAN)
    # 4 legs
    for li, (lx_l, ly_l) in enumerate([(0.55, 0.25), (0.55, -0.25), (-0.55, 0.25), (-0.55, -0.25)]):
        leg_e = empty(f"{name}_le{li}", (lx_l, ly_l, 0.70), parent=base)
        cyl(f"{name}_ul{li}", r=0.12, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=leg_e, mat_=M_LION_TAN)
        cyl(f"{name}_ll{li}", r=0.10, depth=0.30, segs=10, loc=(0, 0, -0.50),
            parent=leg_e, mat_=M_LION_TAN)
        cyl(f"{name}_pw{li}", r=0.13, depth=0.10, segs=10, loc=(0, 0, -0.70),
            parent=leg_e, mat_=M_LION_TAN)
    # Tail with tuft
    tail_e = empty(f"{name}_te", (-1.10, 0, 0.95), parent=base)
    for ti in range(6):
        cyl(f"{name}_t{ti}", r=0.06 - ti*0.005, depth=0.18, segs=8,
            loc=(-ti*0.18, 0, ti*0.05 - 0.05), parent=tail_e, mat_=M_LION_TAN).rotation_euler = (0, math.radians(85), 0)
    smooth_sphere(f"{name}_tu_t", r=0.10, segs=10, rings=8, loc=(-1.1, 0, 0.15),
                  parent=tail_e, mat_=M_LION_MANE if has_mane else M_LION_TAN)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_l_e}

lions = []
lion_pos = [(-50, 30, math.radians(45), True), (40, 35, math.radians(-30), False), (-45, 50, math.radians(60), False)]
for i, (lx, ly, fac, mane) in enumerate(lion_pos):
    ln = make_lion(f"ln{i}", (lx, ly, 0), has_mane=mane, facing=fac)
    lions.append(ln)

# ============ 2 HIPPOS in water (signature) ============
def make_hippo(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Massive body
    smooth_sphere(f"{name}_bo", r=0.95, segs=14, rings=12, loc=(0, 0, 0.85),
                  parent=base, mat_=M_HIPPO_GRAY, scale=(1.6, 1.0, 0.95))
    # Underwater portion
    smooth_sphere(f"{name}_bu", r=0.85, segs=12, rings=10, loc=(0, 0, 0.40),
                  parent=base, mat_=M_HIPPO_DARK, scale=(1.5, 1.0, 0.7))
    # Head huge (signature wide)
    head_h_e = empty(f"{name}_he", (1.30, 0, 1.0), parent=base)
    smooth_sphere(f"{name}_h", r=0.55, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_h_e, mat_=M_HIPPO_GRAY, scale=(1.5, 1.2, 0.85))
    # Snout/mouth
    smooth_sphere(f"{name}_sn", r=0.35, segs=12, rings=10, loc=(0.25, 0, -0.15),
                  parent=head_h_e, mat_=M_HIPPO_PINK)
    # Big tusks (signature)
    for side in (-1, 1):
        cyl(f"{name}_tu{side}", r=0.04, depth=0.20, segs=8,
            loc=(0.45, side*0.12, -0.20), parent=head_h_e, mat_=M_TUSK).rotation_euler = (math.radians(180), 0, 0)
    # Tiny eyes on top
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.05, loc=(0.0, side*0.22, 0.35),
                      parent=head_h_e, mat_=M_EYE)
    # Tiny ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.08, segs=10, rings=8,
                      loc=(-0.20, side*0.30, 0.40), parent=head_h_e, mat_=M_HIPPO_GRAY)
    # 4 stubby legs
    for li, (lx_h, ly_h) in enumerate([(0.70, 0.45), (0.70, -0.45), (-0.70, 0.45), (-0.70, -0.45)]):
        cyl(f"{name}_l{li}", r=0.25, depth=0.30, segs=10,
            loc=(lx_h, ly_h, 0.30), parent=base, mat_=M_HIPPO_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_h_e}

hippos = []
hippo_pos = [(-12, -25, math.radians(20)), (12, -28, math.radians(-30))]
for i, (hx, hy, fac) in enumerate(hippo_pos):
    h = make_hippo(f"hp{i}", (hx, hy, 0.30), facing=fac)
    hippos.append(h)

# ============ 3 MOKORO DUGOUT CANOES (signature) ============
def make_mokoro(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long narrow hull (signature dugout)
    smooth_cone(f"{name}_h", r1=0.30, r2=0.10, depth=4.5, segs=12, loc=(0, 0, 0),
                parent=base, mat_=M_MOKORO_WOOD).rotation_euler = (0, math.radians(90), 0)
    # Hollow inside dark
    beveled_cube(f"{name}_in", (4.0, 0.40, 0.20), bevel_offset=0.04, loc=(0, 0, 0.15),
                 parent=base, mat_=M_MOKORO_DARK)
    # Upturned ends (signature)
    bow_e = empty(f"{name}_bw", (2.3, 0, 0.30), parent=base)
    bow_e.rotation_euler = (0, math.radians(-25), 0)
    cyl(f"{name}_bw_p", r=0.10, depth=0.45, segs=10, loc=(0, 0, 0),
        parent=bow_e, mat_=M_MOKORO_WOOD)
    # Pole (signature poled by standing villager)
    pole_e = empty(f"{name}_pl", (-1.5, 0, 0.4), parent=base)
    pole_e.rotation_euler = (0, math.radians(-30), 0)
    cyl(f"{name}_pl_p", r=0.04, depth=4, segs=8, loc=(0, 0, 1.5),
        parent=pole_e, mat_=M_MOKORO_WOOD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

mokoros = []
for i, (mx, my, fac) in enumerate([(-30, -32, math.radians(10)), (10, -35, math.radians(-15)), (40, -30, math.radians(20))]):
    m = make_mokoro(f"mo{i}", (mx, my, 0.40), facing=fac)
    mokoros.append(m)

# ============ THATCHED HUTS (signature Bantu) ============
def make_hut(name, loc, scale=1.0):
    base = empty(name, loc)
    # Circular wall
    cyl(f"{name}_w", r=2, depth=2.2, segs=22, loc=(0, 0, 1.1), parent=base, mat_=M_HUT_WALL)
    # CONICAL THATCHED ROOF (signature)
    smooth_cone(f"{name}_r", r1=2.5, r2=0.05, depth=2.5, segs=22, loc=(0, 0, 3.45),
                parent=base, mat_=M_THATCH)
    # Thatch tufts
    for ti_t in range(40):
        ta = random.uniform(0, math.pi*2); tr = random.uniform(0.3, 2.3)
        smooth_sphere(f"{name}_t{ti_t}", r=random.uniform(0.10, 0.18), segs=10, rings=6,
                      loc=(math.cos(ta)*tr, math.sin(ta)*tr, random.uniform(2.5, 5.5)),
                      parent=base, mat_=M_THATCH, scale=(1.2, 1.2, 0.7))
    # Door
    beveled_cube(f"{name}_d", (0.7, 0.05, 1.4), bevel_offset=0.04, loc=(0, -2.05, 0.90),
                 parent=base, mat_=M_TRUNK)
    return base

for i, (hx, hy) in enumerate([(-65, 40), (65, 50), (0, 80)]):
    make_hut(f"hu{i}", (hx, hy, 0))

# ============ BANTU VILLAGERS (signature poling mokoro) ============
def make_villager(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    cloth_col = random.choice(CLOTH_COLORS)
    # Body wrap
    smooth_cone(f"{name}_to", r1=0.30, r2=0.34, depth=0.85, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=cloth_col)
    # Pants/skirt
    cyl(f"{name}_p", r=0.32, depth=0.50, segs=14, loc=(0, 0, 0.55),
        parent=base, mat_=cloth_col)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.10, depth=0.45, segs=10,
            loc=(side*0.13, 0, 0.25), parent=base, mat_=M_SKIN_DARK)
    # Arms raised holding pole
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.60), parent=base)
        sh.rotation_euler = (math.radians(-150), 0, math.radians(side*15))
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=M_SKIN_DARK)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=M_SKIN_DARK)
    # Head
    head_v_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_v_e, mat_=M_SKIN_DARK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_v_e, mat_=M_EYE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_v_e}

villagers = []
# Place villagers on/near mokoros
for i, (vx, vy, fac) in enumerate([(-30, -32, math.radians(0)), (10, -35, math.radians(0)),
                                     (40, -30, math.radians(0)), (-60, 38, math.radians(45))]):
    v = make_villager(f"vl{i}", (vx, vy, 1.0 if i < 3 else 0), facing=fac)
    villagers.append(v)

# ============ BOTSWANA FLAG (signature blue black white) ============
flag_e = empty("flag", (-60, -50, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_TRUNK)
# Light blue top
beveled_cube("fl_bt", (4, 0.05, 0.95), bevel_offset=0.06, loc=(2, 0, 11.45),
             parent=flag_e, mat_=M_FLAG_BLUE)
# White stripe
beveled_cube("fl_w1", (4, 0.05, 0.20), bevel_offset=0.04, loc=(2, 0, 10.85),
             parent=flag_e, mat_=M_FLAG_WHITE)
# Black stripe
beveled_cube("fl_bk", (4, 0.05, 0.45), bevel_offset=0.06, loc=(2, 0, 10.42),
             parent=flag_e, mat_=M_FLAG_BLACK)
# White stripe
beveled_cube("fl_w2", (4, 0.05, 0.20), bevel_offset=0.04, loc=(2, 0, 10.0),
             parent=flag_e, mat_=M_FLAG_WHITE)
# Light blue bottom
beveled_cube("fl_bb", (4, 0.05, 0.95), bevel_offset=0.06, loc=(2, 0, 9.45),
             parent=flag_e, mat_=M_FLAG_BLUE)
flag_e["_phase"] = 0

# ============================================================
# 600 PAPYRUS REEDS + 400 FLAMINGOS (PARTICULES SIGNATURES)
# ============================================================
reeds = []
for i in range(600):
    px = random.uniform(-110, 110)
    py = random.uniform(-100, 100)
    pz = 0.30
    r_e = empty(f"re{i}", (px, py, pz))
    # Tall papyrus stem
    cyl(f"re{i}_s", r=0.025, depth=random.uniform(1.5, 3.0), segs=6,
        loc=(0, 0, 1.0), parent=r_e, mat_=M_PAPYRUS)
    # Papyrus head (signature fluffy umbrella)
    head_top_z = 2.2
    for hi_p in range(12):
        hpa = (hi_p / 12.0) * math.pi * 2
        beveled_cube(f"re{i}_h{hi_p}", (0.02, 0.04, 0.20), bevel_offset=0.005,
                     loc=(math.cos(hpa)*0.10, math.sin(hpa)*0.10, head_top_z),
                     parent=r_e, mat_=M_PAPYRUS_HEAD).rotation_euler = (0, math.radians(15), hpa)
    smooth_sphere(f"re{i}_c", r=0.06, loc=(0, 0, head_top_z),
                  parent=r_e, mat_=M_PAPYRUS_HEAD)
    r_e["_phase"] = random.uniform(0, math.pi*2)
    r_e["_speed"] = random.uniform(0.5, 1.5)
    reeds.append(r_e)

# 400 flamingos
flamingos = []
for i in range(400):
    px = random.uniform(-110, 110)
    py = random.uniform(-110, 110)
    pz = random.uniform(0.3, 18)
    fl_e = empty(f"fl{i}", (px, py, pz))
    # Body (signature pink)
    smooth_sphere(f"fl{i}_bo", r=0.18, segs=10, rings=8, loc=(0, 0, 0),
                  parent=fl_e, mat_=M_FLAMINGO_PINK, scale=(1.3, 0.85, 0.85))
    # LONG CURVED NECK (signature)
    neck_top_e = empty(f"fl{i}_ne", (0.10, 0, 0.05), parent=fl_e)
    neck_top_e.rotation_euler = (0, math.radians(-50), 0)
    for ni in range(5):
        ni_t = ni / 5.0
        cyl(f"fl{i}_n{ni}", r=0.025, depth=0.10, segs=8,
            loc=(math.sin(ni_t*math.pi*0.4)*0.05, 0, ni_t*0.45 + 0.05),
            parent=neck_top_e, mat_=M_FLAMINGO_PINK)
    # Small head
    smooth_sphere(f"fl{i}_h", r=0.06, segs=8, rings=6, loc=(0.05, 0, 0.55),
                  parent=neck_top_e, mat_=M_FLAMINGO_PINK)
    # CURVED BEAK (signature)
    cyl(f"fl{i}_bk", r=0.015, depth=0.12, segs=6, loc=(0.10, 0, 0.50),
        parent=neck_top_e, mat_=M_FLAMINGO_BEAK).rotation_euler = (0, math.radians(125), 0)
    # Beak tip black
    smooth_sphere(f"fl{i}_bkt", r=0.015, loc=(0.13, 0, 0.43),
                  parent=neck_top_e, mat_=M_FLAMINGO_BLACK)
    # 1 long leg (signature standing)
    cyl(f"fl{i}_l", r=0.02, depth=0.80, segs=6, loc=(0, 0, -0.40),
        parent=fl_e, mat_=M_FLAMINGO_PINK)
    # Other leg tucked up
    cyl(f"fl{i}_l2", r=0.02, depth=0.30, segs=6, loc=(0.05, 0.08, -0.10),
        parent=fl_e, mat_=M_FLAMINGO_PINK).rotation_euler = (math.radians(45), 0, 0)
    # Wings (signature pink with black tips)
    for side in (-1, 1):
        beveled_cube(f"fl{i}_w{side}", (0.10, 0.20, 0.04), bevel_offset=0.008,
                     loc=(0, side*0.10, 0.05), parent=fl_e, mat_=M_FLAMINGO_PINK)
        # Black wing tip
        beveled_cube(f"fl{i}_wt{side}", (0.08, 0.10, 0.025), bevel_offset=0.005,
                     loc=(0, side*0.20, 0.06), parent=fl_e, mat_=M_FLAMINGO_BLACK)
    fl_e["_phase"] = random.uniform(0, math.pi*2)
    fl_e["_base_x"] = px; fl_e["_base_y"] = py; fl_e["_base_z"] = pz
    fl_e["_speed"] = random.uniform(0.4, 1.1)
    fl_e["_radius"] = random.uniform(3, 12)
    flamingos.append(fl_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Elephants sway/trunk swing
for el in elephants:
    phase = el["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        el["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(2), 0,
                                       el["root"].rotation_euler.z)
        el["root"].keyframe_insert("rotation_euler", frame=f)
        el["trunk"].rotation_euler = (0, math.radians(-20) + math.sin(t * 1.5 + phase) * math.radians(20),
                                        math.cos(t * 1.0 + phase) * math.radians(15))
        el["trunk"].keyframe_insert("rotation_euler", frame=f)

# Giraffes sway necks (signature gracefulness)
for g in giraffes:
    phase = g["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        g["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     g["root"].rotation_euler.z)
        g["root"].keyframe_insert("rotation_euler", frame=f)
        g["neck"].rotation_euler = (0, math.radians(-30) + math.sin(t * 0.8 + phase) * math.radians(8),
                                     math.cos(t * 0.6 + phase) * math.radians(12))
        g["neck"].keyframe_insert("rotation_euler", frame=f)

# Lions chill
for ln in lions:
    phase = ln["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        ln["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(5), 0,
                                    math.cos(t * 0.7 + phase) * math.radians(15))
        ln["he"].keyframe_insert("rotation_euler", frame=f)

# Hippos
for h in hippos:
    phase = h["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        h["he"].rotation_euler = (0, math.sin(t * 1.0 + phase) * math.radians(8), 0)
        h["he"].keyframe_insert("rotation_euler", frame=f)

# Mokoros bob
for m in mokoros:
    phase = m["_phase"]
    bz_m = m.location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        m.location.z = bz_m + math.sin(t * 1.5 + phase) * 0.08
        m.rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2),
                             math.cos(t * 1.5 + phase) * math.radians(2),
                             m.rotation_euler.z)
        m.keyframe_insert("location", frame=f)
        m.keyframe_insert("rotation_euler", frame=f)

# Acacias sway
for ac in acacias:
    phase = ac["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        ac["canopy"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3),
                                        math.cos(t * 0.8 + phase) * math.radians(3), 0)
        ac["canopy"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 papyrus reeds sway
for r in reeds:
    phase = r["_phase"]; speed = r["_speed"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        r.rotation_euler = (math.sin(t * speed + phase) * math.radians(8),
                             math.cos(t * speed * 0.8 + phase) * math.radians(6), 0)
        r.keyframe_insert("rotation_euler", frame=f)

# 400 flamingos fly in circles
for fl in flamingos:
    phase = fl["_phase"]; speed = fl["_speed"]; radius = fl["_radius"]
    bx, by, bz_f = fl["_base_x"], fl["_base_y"], fl["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * radius
        y = by + math.sin(t * speed + phase) * radius
        z = bz_f + math.sin(t * speed * 1.3 + phase) * 1.5
        fl.location = (x, y, z)
        fl.rotation_euler = (0, 0, math.atan2(math.cos(t * speed + phase),
                                                -math.sin(t * speed + phase)))
        fl.keyframe_insert("location", frame=f)
        fl.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_botswana_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_botswana_okavango_delta_safari] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Botswana Okavango Delta: wetland with main waterway + 4 side channels + 30 lily pads + 4 African elephants (signature massive body + HUGE fan ears + long curved trunk + 2 tusks + 4 pillar legs + tail tuft) + 4 giraffes (signature long neck 4m+ + 30 spots + ossicones horn knobs + mane tufts + 4 long legs) + 3 lions (1 with mane signature + 2 lionesses + amber eyes + pink nose + tail tufts) + 2 hippos in water (signature wide head + tusks + tiny eyes on top) + 3 mokoro dugout canoes with poles + 4 Bantu villagers + 3 thatched conical huts + 6 acacia trees with signature flat-top canopy + Botswana flag (signature blue/white/black/white/blue) + 600 papyrus reeds with fluffy umbrella heads + 400 flamingos with signature curved necks + curved beaks + standing on 1 leg + pink with black wing tips")
print("🦩 FIXES: 1 wetland ground + 600 papyrus reeds + 400 flamingos signature 🦩")
