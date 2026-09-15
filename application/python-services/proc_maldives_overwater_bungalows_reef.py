"""
proc_maldives_overwater_bungalows_reef.py — 297e procédural AuroraIA (162e qualité EXPERT REALISM)
Maldives: turquoise lagoon + 6 overwater bungalows + coral reef + 4 tourists + 600 tropical fish + 400 manta rays
REALISM RULES: smooth_sphere stretched anatomy, bevel_offset>=0.15 bevel_segments>=5, joint spheres, no naked cubes
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB297)

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

def beveled_cube(name, size_xyz, bevel_offset=0.15, bevel_segments=5, loc=(0,0,0), parent=None, mat_=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size_xyz, verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:],
                    offset=bevel_offset, segments=bevel_segments,
                    profile=0.7, affect='EDGES')
    return make_obj(name, bm, loc, parent, mat_)

def smooth_sphere(name, r=1.0, segs=28, rings=20, loc=(0,0,0), parent=None, mat_=None, scale=(1,1,1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    if scale != (1,1,1):
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    return make_obj(name, bm, loc, parent, mat_)

def smooth_cone(name, r1, r2, depth, segs=22, loc=(0,0,0), parent=None, mat_=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    return make_obj(name, bm, loc, parent, mat_)

def cyl(name, r, depth, segs=20, loc=(0,0,0), parent=None, mat_=None):
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

# Sky tropical paradise
M_SKY = mat("sky", (0.55, 0.85, 0.95, 1.0), 0.0, 0.7, emission=(0.55,0.82,0.92), emission_strength=2.0)
M_SKY_LOW = mat("sky_l", (0.92, 0.92, 0.95, 1.0), 0.0, 0.7, emission=(0.90,0.92,0.95), emission_strength=1.7)
M_SUN = mat("sun", (1.0, 0.92, 0.65, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.65), emission_strength=18.0)
M_CLOUD = mat("cl", (0.98, 0.98, 0.95, 1.0), 0.0, 0.85, emission=(0.98,0.98,0.95), emission_strength=1.0, alpha=0.85)

# ONE clean turquoise lagoon ground (signature Maldives)
M_LAGOON_TURQ = mat("lt", (0.20, 0.85, 0.92, 1.0), 0.3, 0.10, emission=(0.20,0.85,0.92), emission_strength=2.5, alpha=0.75)
M_LAGOON_DEEP = mat("ld", (0.10, 0.55, 0.75, 1.0), 0.3, 0.15, emission=(0.10,0.55,0.72), emission_strength=1.5, alpha=0.85)
M_LAGOON_BRIGHT = mat("lb", (0.45, 0.95, 0.95, 1.0), 0.3, 0.08, emission=(0.45,0.92,0.95), emission_strength=3.0, alpha=0.70)
M_SAND_WHITE = mat("sw", (0.98, 0.95, 0.85, 1.0), 0.0, 0.65, emission=(0.95,0.92,0.85), emission_strength=0.6)
M_FOAM = mat("fm", (0.98, 0.98, 0.95, 1.0), 0.0, 0.30, emission=(0.98,0.98,0.95), emission_strength=2.0, alpha=0.55)

# Bungalow
M_THATCH = mat("th", (0.65, 0.45, 0.20, 1.0), 0.0, 0.85, emission=(0.62,0.42,0.20), emission_strength=0.3)
M_THATCH_DARK = mat("thd", (0.42, 0.30, 0.15, 1.0), 0.0, 0.92)
M_WOOD_TROPICAL = mat("wt", (0.85, 0.65, 0.42, 1.0), 0.0, 0.65, emission=(0.82,0.62,0.42), emission_strength=0.3)
M_WOOD_DARK = mat("wd", (0.42, 0.28, 0.15, 1.0), 0.0, 0.85)
M_WALL_WHITE = mat("ww", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.92,0.88,0.82), emission_strength=0.4)
M_WALL_CREAM = mat("wc", (0.92, 0.88, 0.78, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.78), emission_strength=0.4)

# Tourist
M_SKIN = mat("sk", (0.95, 0.78, 0.55, 1.0), 0.0, 0.55, emission=(0.92,0.78,0.55), emission_strength=0.3)
M_HAIR_BLOND = mat("hb", (0.85, 0.72, 0.42, 1.0), 0.0, 0.85)
M_HAIR_BROWN = mat("hbr", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)
M_SWIM_BLUE = mat("sbl", (0.18, 0.55, 0.85, 1.0), 0.0, 0.55, emission=(0.18,0.55,0.82), emission_strength=0.5)
M_SWIM_PINK = mat("spk", (1.0, 0.55, 0.78, 1.0), 0.0, 0.55, emission=(0.95,0.55,0.75), emission_strength=0.6)
M_SWIM_RED = mat("sr", (0.85, 0.20, 0.22, 1.0), 0.0, 0.55, emission=(0.82,0.20,0.22), emission_strength=0.6)
M_SWIM_GREEN = mat("sg", (0.20, 0.65, 0.32, 1.0), 0.0, 0.55, emission=(0.20,0.62,0.32), emission_strength=0.5)
SWIM_COLORS = [M_SWIM_BLUE, M_SWIM_PINK, M_SWIM_RED, M_SWIM_GREEN]

# Palm tree
M_PALM_TRUNK = mat("pt", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85, emission=(0.52,0.30,0.15), emission_strength=0.3)
M_PALM_LEAF = mat("pl", (0.30, 0.62, 0.25, 1.0), 0.0, 0.55, emission=(0.28,0.58,0.25), emission_strength=0.5)
M_COCONUT = mat("co", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)

# Coral reef
M_CORAL_PINK = mat("crp", (1.0, 0.55, 0.78, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.75), emission_strength=1.5)
M_CORAL_ORANGE = mat("cro", (1.0, 0.55, 0.18, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.18), emission_strength=1.5)
M_CORAL_PURPLE = mat("crpu", (0.65, 0.30, 0.85, 1.0), 0.0, 0.45, emission=(0.62,0.30,0.82), emission_strength=1.5)
M_CORAL_YELLOW = mat("cry", (1.0, 0.92, 0.30, 1.0), 0.0, 0.45, emission=(0.95,0.88,0.30), emission_strength=1.8)
M_CORAL_BLUE = mat("crb", (0.30, 0.65, 0.95, 1.0), 0.0, 0.45, emission=(0.30,0.62,0.92), emission_strength=1.5)
CORAL_COLORS = [M_CORAL_PINK, M_CORAL_ORANGE, M_CORAL_PURPLE, M_CORAL_YELLOW, M_CORAL_BLUE]

# Tropical fish (signature multi-color)
M_FISH_BLUE = mat("fbl", (0.18, 0.55, 0.95, 1.0), 0.4, 0.20, emission=(0.18,0.55,0.92), emission_strength=2.5)
M_FISH_YELLOW = mat("fy", (1.0, 0.92, 0.20, 1.0), 0.3, 0.20, emission=(0.95,0.88,0.20), emission_strength=2.8)
M_FISH_ORANGE = mat("fo", (1.0, 0.55, 0.18, 1.0), 0.3, 0.25, emission=(0.95,0.55,0.18), emission_strength=2.5)
M_FISH_PINK = mat("fp", (1.0, 0.45, 0.65, 1.0), 0.3, 0.25, emission=(0.95,0.45,0.62), emission_strength=2.5)
M_FISH_RED = mat("fr", (0.92, 0.20, 0.22, 1.0), 0.3, 0.25, emission=(0.88,0.20,0.22), emission_strength=2.5)
M_FISH_PURPLE = mat("fpu", (0.65, 0.30, 0.92, 1.0), 0.3, 0.25, emission=(0.62,0.30,0.90), emission_strength=2.5)
FISH_COLORS = [M_FISH_BLUE, M_FISH_YELLOW, M_FISH_ORANGE, M_FISH_PINK, M_FISH_RED, M_FISH_PURPLE]
M_FISH_STRIPE = mat("fst", (0.10, 0.10, 0.12, 1.0), 0.2, 0.40)

# Manta ray (signature dark)
M_MANTA_DARK = mat("mr", (0.18, 0.22, 0.28, 1.0), 0.2, 0.45, emission=(0.18,0.22,0.28), emission_strength=0.3)
M_MANTA_BELLY = mat("mrb", (0.78, 0.82, 0.85, 1.0), 0.1, 0.55)

# Maldives flag (signature green/red/crescent)
M_FLAG_RED = mat("frd", (0.85, 0.15, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.15,0.18), emission_strength=1.0)
M_FLAG_GREEN = mat("fgr", (0.18, 0.62, 0.32, 1.0), 0.0, 0.45, emission=(0.18,0.60,0.32), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS_RED = mat("lr", (0.78, 0.18, 0.20, 1.0), 0.0, 0.30, emission=(0.75,0.18,0.20), emission_strength=0.5)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-40, 90, 35), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-40, 90, 35), mat_=M_SUN)
# Tropical fluffy clouds
for ci in range(20):
    cx_c = random.uniform(-150, 150); cy_c = random.uniform(-100, 100); cz_c = random.uniform(50, 70)
    cloud_e = empty(f"cl{ci}_e", (cx_c, cy_c, cz_c))
    for cp in range(7):
        cpa = random.uniform(0, math.pi*2); cpr = random.uniform(0, 4)
        smooth_sphere(f"cl{ci}_p{cp}", r=random.uniform(2.5, 4.5), segs=16, rings=12,
                      loc=(math.cos(cpa)*cpr, math.sin(cpa)*cpr, random.uniform(-1, 1)),
                      parent=cloud_e, mat_=M_CLOUD, scale=(1.5, 1.5, 0.6))

# ============ ONE clean turquoise lagoon ground (NO SANDWICH) ============
ground = beveled_cube("ground", (300, 300, 0.4), bevel_offset=0.15, bevel_segments=5, loc=(0, 0, -0.20), mat_=M_LAGOON_TURQ)
# Sand patches (organic, scattered, no flat overlay)
beach_e = empty("beach", (0, 60, 0))
for bi in range(60):
    a = random.uniform(-math.pi*0.5, math.pi*0.5); rad = random.uniform(5, 35)
    smooth_sphere(f"bsd{bi}", r=random.uniform(1.5, 3.0), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  parent=beach_e, mat_=M_SAND_WHITE, scale=(1.5, 1.4, 0.18))
# Bright shallow turquoise spots (organic spheres only - no planes)
for li in range(80):
    a = random.uniform(0, math.pi*2); rad = random.uniform(15, 110)
    smooth_sphere(f"lb_{li}", r=random.uniform(2.0, 4.0), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*math.sin(a), -0.10),
                  mat_=M_LAGOON_BRIGHT, scale=(1.5, 1.5, 0.15))
# Deep blue patches
for di in range(40):
    a = random.uniform(0, math.pi*2); rad = random.uniform(60, 130)
    smooth_sphere(f"ld_{di}", r=random.uniform(3.0, 5.0), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*math.sin(a), -0.18),
                  mat_=M_LAGOON_DEEP, scale=(1.5, 1.5, 0.15))

# ============ 6 OVERWATER BUNGALOWS on stilts (signature) ============
def make_bungalow(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # 4 wooden stilts (cylinder with sphere base joint - no naked cylinder)
    for si in range(4):
        sa = (si / 4.0) * math.pi * 2 + math.pi/4
        sx = math.cos(sa) * 2.0; sy = math.sin(sa) * 1.5
        cyl(f"{name}_st{si}", r=0.20, depth=3.5, segs=14, loc=(sx, sy, 1.5),
            parent=base, mat_=M_WOOD_DARK)
        # Water ring (foam at base)
        smooth_sphere(f"{name}_sw{si}", r=0.30, segs=12, rings=10,
                      loc=(sx, sy, -0.10), parent=base, mat_=M_FOAM, scale=(1.3, 1.3, 0.4))
    # Platform deck
    beveled_cube(f"{name}_pl", (5, 4, 0.30), bevel_offset=0.15, bevel_segments=5,
                 loc=(0, 0, 3.30), parent=base, mat_=M_WOOD_TROPICAL)
    # Deck planks (subtle wood grain via lines)
    for pi in range(10):
        beveled_cube(f"{name}_pl_p{pi}", (5.02, 0.04, 0.02), bevel_offset=0.005, bevel_segments=2,
                     loc=(0, -1.9 + pi*0.42, 3.46), parent=base, mat_=M_WOOD_DARK)
    # Main building walls
    beveled_cube(f"{name}_w", (4, 3.5, 2.5), bevel_offset=0.15, bevel_segments=5,
                 loc=(0, 0, 4.70), parent=base, mat_=M_WALL_WHITE)
    # CONICAL THATCHED ROOF (signature)
    roof_e = empty(f"{name}_re", (0, 0, 6.0), parent=base)
    smooth_cone(f"{name}_r", r1=2.8, r2=0.05, depth=2.0, segs=18, loc=(0, 0, 1.0),
                parent=roof_e, mat_=M_THATCH)
    # Thatch tufts (organic spheres)
    for ti in range(45):
        ta = random.uniform(0, math.pi*2); tr = random.uniform(0.3, 2.5)
        smooth_sphere(f"{name}_t{ti}", r=random.uniform(0.12, 0.22), segs=12, rings=8,
                      loc=(math.cos(ta)*tr, math.sin(ta)*tr, random.uniform(0.5, 2.0)),
                      parent=roof_e, mat_=M_THATCH if ti % 2 == 0 else M_THATCH_DARK,
                      scale=(1.3, 1.3, 0.7))
    # Roof apex finial
    smooth_sphere(f"{name}_fi", r=0.20, segs=14, rings=10, loc=(0, 0, 8.4),
                  parent=base, mat_=M_WOOD_DARK)
    # Door
    beveled_cube(f"{name}_d", (0.8, 0.05, 1.6), bevel_offset=0.05, bevel_segments=4,
                 loc=(0, -1.78, 4.5), parent=base, mat_=M_WOOD_DARK)
    # Windows (panoramic)
    for wi in (-1, 1):
        beveled_cube(f"{name}_wi{wi}", (1.0, 0.05, 1.2), bevel_offset=0.05, bevel_segments=4,
                     loc=(wi*1.4, -1.78, 4.8), parent=base, mat_=M_LAGOON_TURQ)
        # Window frame
        for wxi in (-1, 1):
            cyl(f"{name}_wxv{wi}_{wxi}", r=0.03, depth=1.2, segs=10,
                loc=(wi*1.4 + wxi*0.45, -1.80, 4.8), parent=base, mat_=M_WOOD_DARK)
    # Stairs down to water (signature ladder access)
    stairs_e = empty(f"{name}_sa", (2.8, 0, 1.8), parent=base)
    for si_s in range(5):
        beveled_cube(f"{name}_sa_p{si_s}", (0.6, 0.4, 0.08), bevel_offset=0.04, bevel_segments=3,
                     loc=(0, 0, si_s*0.32), parent=stairs_e, mat_=M_WOOD_DARK)
    # Railing
    for si_r in range(6):
        cyl(f"{name}_ra{si_r}", r=0.05, depth=1.2, segs=8,
            loc=(2.5, -1.8 + si_r*0.75, 3.95), parent=base, mat_=M_WOOD_DARK)
    return base

# Bungalows arranged in arc
bungalow_pos = [
    (-30, -25, math.radians(0)), (-15, -32, math.radians(10)),
    (0, -36, math.radians(0)), (15, -32, math.radians(-10)),
    (30, -25, math.radians(0)), (-22, -18, math.radians(20))
]
for i, (bx, by, fac) in enumerate(bungalow_pos):
    make_bungalow(f"bg{i}", (bx, by, 0), facing=fac)

# Wooden walkway connecting (signature)
walkway_e = empty("walkway", (0, -10, 0))
for wi in range(20):
    wy_p = -5 - wi * 2
    beveled_cube(f"wk{wi}", (1.2, 1.8, 0.20), bevel_offset=0.10, bevel_segments=4,
                 loc=(0, wy_p, 3.30), parent=walkway_e, mat_=M_WOOD_TROPICAL)
    # Walkway stilts
    for st_s in (-1, 1):
        cyl(f"wk{wi}_st{st_s}", r=0.10, depth=3.5, segs=10,
            loc=(st_s*0.5, wy_p, 1.5), parent=walkway_e, mat_=M_WOOD_DARK)

# ============ PALM TREES on small sand island (signature) ============
def make_palm(name, loc, lean=0):
    base = empty(name, loc)
    base.rotation_euler = (0, math.radians(lean), 0)
    # Curved trunk (cyl stack)
    for ti in range(14):
        tz = ti * 0.5
        tilt = math.sin(ti * 0.3) * 0.12
        cyl(f"{name}_t{ti}", r=0.20 - ti*0.005, depth=0.50, segs=12,
            loc=(tilt, 0, tz + 0.25), parent=base, mat_=M_PALM_TRUNK)
    # Crown leaves (signature palm fronds)
    crown_e = empty(f"{name}_cr", (0, 0, 7.5), parent=base)
    for li in range(12):
        la = (li / 12.0) * math.pi * 2
        leaf_e = empty(f"{name}_le{li}", (0, 0, 0), parent=crown_e)
        leaf_e.rotation_euler = (math.radians(70), 0, la)
        # Rachis
        cyl(f"{name}_lr{li}", r=0.025, depth=3, segs=10, loc=(0, 0, 1.5),
            parent=leaf_e, mat_=M_PALM_TRUNK)
        # Pinnae using spheres (organic leaflets)
        for sl in range(10):
            sl_z = sl * 0.30 + 0.30
            for ps in (-1, 1):
                smooth_sphere(f"{name}_pn{li}_{sl}_{ps}", r=0.06, segs=10, rings=8,
                              loc=(ps*0.30, 0, sl_z), parent=leaf_e, mat_=M_PALM_LEAF,
                              scale=(0.3, 1.0, 0.6))
    # Coconuts
    for ci in range(8):
        ca = (ci / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_co{ci}", r=0.22, segs=14, rings=10,
                      loc=(math.cos(ca)*0.40, math.sin(ca)*0.40, 7.3),
                      parent=base, mat_=M_COCONUT)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "crown": crown_e}

palms = []
# Palms on small sand island in middle
palm_pos = [(0, 50, 5), (-8, 55, -3), (8, 55, 3), (-15, 48, 8), (15, 48, -8)]
for i, (px, py, lean) in enumerate(palm_pos):
    p = make_palm(f"pm{i}", (px, py, 0.3), lean=lean)
    palms.append(p)

# ============ CORAL REEF underwater (signature multi-color organic) ============
reef_e = empty("reef", (0, 0, -0.50))
for ci in range(80):
    a = random.uniform(0, math.pi*2); rad = random.uniform(15, 100)
    rx = math.cos(a) * rad; ry = math.sin(a) * rad
    c_col = random.choice(CORAL_COLORS)
    # Coral cluster - multiple organic spheres
    coral_e = empty(f"cr{ci}_e", (rx, ry, 0), parent=reef_e)
    coral_type = ci % 4
    if coral_type == 0:
        # Brain coral (ridged sphere)
        smooth_sphere(f"cr{ci}_b", r=random.uniform(0.6, 1.2), segs=18, rings=14,
                      loc=(0, 0, 0), parent=coral_e, mat_=c_col, scale=(1.2, 1.2, 0.85))
    elif coral_type == 1:
        # Branching coral (multiple cones)
        for bri in range(5):
            ba = (bri / 5.0) * math.pi * 2
            smooth_cone(f"cr{ci}_b{bri}", r1=0.20, r2=0.05, depth=random.uniform(0.6, 1.0),
                        segs=12, loc=(math.cos(ba)*0.20, math.sin(ba)*0.15, 0.3),
                        parent=coral_e, mat_=c_col)
    elif coral_type == 2:
        # Plate coral (flat disc)
        cyl(f"cr{ci}_p", r=random.uniform(0.8, 1.4), depth=0.20, segs=18,
            loc=(0, 0, 0), parent=coral_e, mat_=c_col)
    else:
        # Tubular coral
        for tu in range(6):
            cyl(f"cr{ci}_tu{tu}", r=random.uniform(0.08, 0.14), depth=random.uniform(0.4, 0.8), segs=10,
                loc=(random.uniform(-0.4, 0.4), random.uniform(-0.4, 0.4), 0.2),
                parent=coral_e, mat_=c_col)

# ============ 4 TOURISTS (signature swimsuits + relaxed pose) ============
def make_tourist(name, loc, scale=1.0, facing=0, pose="standing"):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    swim_col = random.choice(SWIM_COLORS)
    # Body (stretched sphere not cube)
    smooth_sphere(f"{name}_bo", r=0.30, segs=18, rings=14, loc=(0, 0, 1.25),
                  parent=base, mat_=M_SKIN, scale=(1, 0.85, 1.5))
    # Swimsuit area
    cyl(f"{name}_sw", r=0.31, depth=0.30, segs=18, loc=(0, 0, 1.00),
        parent=base, mat_=swim_col)
    # Legs with knee joints
    for side in (-1, 1):
        leg_e = empty(f"{name}_le{side}", (side*0.12, 0, 0.85), parent=base)
        # Upper leg
        cyl(f"{name}_ul{side}", r=0.10, depth=0.40, segs=14, loc=(0, 0, -0.20),
            parent=leg_e, mat_=M_SKIN)
        # KNEE JOINT sphere
        smooth_sphere(f"{name}_kn{side}", r=0.10, segs=12, rings=10, loc=(0, 0, -0.40),
                      parent=leg_e, mat_=M_SKIN)
        # Lower leg
        cyl(f"{name}_ll{side}", r=0.08, depth=0.40, segs=14, loc=(0, 0, -0.60),
            parent=leg_e, mat_=M_SKIN)
        # Foot
        smooth_sphere(f"{name}_ft{side}", r=0.10, segs=12, rings=8, loc=(0, 0.05, -0.85),
                      parent=leg_e, mat_=M_SKIN, scale=(1.0, 1.4, 0.5))
    # Arms with joints
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.32, 0, 1.65), parent=base)
        sh.rotation_euler = (math.radians(-70), 0, math.radians(side*30))
        # Shoulder joint
        smooth_sphere(f"{name}_sh{side_idx}", r=0.09, segs=12, rings=10, loc=(0, 0, 0),
                      parent=sh, mat_=M_SKIN)
        # Upper arm
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.35, segs=14, loc=(0, 0, -0.18),
            parent=sh, mat_=M_SKIN)
        # Elbow joint
        smooth_sphere(f"{name}_el{side_idx}", r=0.07, segs=12, rings=10, loc=(0, 0, -0.36),
                      parent=sh, mat_=M_SKIN)
        # Forearm
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=14, loc=(0, 0, -0.52),
            parent=sh, mat_=M_SKIN)
        # Hand
        smooth_sphere(f"{name}_hd{side_idx}", r=0.07, segs=12, rings=10, loc=(0, 0, -0.70),
                      parent=sh, mat_=M_SKIN)
    # Head
    head_t_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=20, rings=16, loc=(0, 0, 0),
                  parent=head_t_e, mat_=M_SKIN)
    # Hair
    hair_col = random.choice([M_HAIR_BLOND, M_HAIR_BROWN])
    for hi in range(20):
        ha = random.uniform(0, math.pi*2)
        smooth_sphere(f"{name}_hr{hi}", r=0.05, segs=10, rings=8,
                      loc=(math.cos(ha)*0.15, math.sin(ha)*0.12, 0.10 + random.uniform(-0.02, 0.05)),
                      parent=head_t_e, mat_=hair_col, scale=(1, 1, 0.7))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_t_e, mat_=M_EYE)
    # Lips
    smooth_sphere(f"{name}_lp", r=0.04, loc=(0, -0.17, -0.07),
                  parent=head_t_e, mat_=M_LIPS_RED, scale=(1.5, 0.5, 0.4))
    # Sunglasses (signature)
    if random.random() > 0.4:
        for side in (-1, 1):
            cyl(f"{name}_sg{side}", r=0.06, depth=0.04, segs=12,
                loc=(side*0.08, -0.16, 0.03), parent=head_t_e, mat_=M_FISH_STRIPE).rotation_euler = (math.radians(90), 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_t_e}

tourists = []
for i, (tx, ty, fac) in enumerate([(-25, -25, math.radians(120)), (-12, -32, math.radians(90)),
                                     (8, -32, math.radians(-90)), (25, -25, math.radians(-120))]):
    t = make_tourist(f"to{i}", (tx, ty, 3.65), facing=fac)
    tourists.append(t)

# ============ MALDIVES FLAG (signature green/red/crescent) ============
flag_e = empty("flag", (-55, -55, 0))
cyl("fl_p", r=0.10, depth=12, segs=12, loc=(0, 0, 6), parent=flag_e, mat_=M_WOOD_DARK)
# Red field
beveled_cube("fl_r", (4, 0.05, 2.5), bevel_offset=0.10, bevel_segments=4,
             loc=(2, 0, 10.5), parent=flag_e, mat_=M_FLAG_RED)
# Green rectangle center
beveled_cube("fl_g", (2.4, 0.06, 1.6), bevel_offset=0.08, bevel_segments=4,
             loc=(2, -0.005, 10.5), parent=flag_e, mat_=M_FLAG_GREEN)
# White crescent (signature - sphere offset cutout)
crescent_e = empty("fl_cr", (2.4, -0.06, 10.5), parent=flag_e)
smooth_sphere("fl_cr_o", r=0.50, segs=18, rings=14, loc=(0, 0, 0),
              parent=crescent_e, mat_=M_FLAG_WHITE)
smooth_sphere("fl_cr_i", r=0.45, segs=18, rings=14, loc=(0.20, -0.04, 0),
              parent=crescent_e, mat_=M_FLAG_GREEN)
flag_e["_phase"] = 0

# ============================================================
# 600 TROPICAL FISH SCHOOLS + 400 MANTA RAYS (signature)
# ============================================================
fish = []
for i in range(600):
    px = random.uniform(-130, 130)
    py = random.uniform(-130, 130)
    pz = random.uniform(-0.30, 5)  # Mostly underwater + above surface
    f_col = random.choice(FISH_COLORS)
    f_e = empty(f"fi{i}", (px, py, pz))
    # Fish body (organic streamlined)
    smooth_sphere(f"fi{i}_b", r=0.18, segs=14, rings=10, loc=(0, 0, 0),
                  parent=f_e, mat_=f_col, scale=(2.0, 0.85, 1.1))
    # Tail fin (signature triangular)
    smooth_cone(f"fi{i}_t", r1=0.04, r2=0.15, depth=0.20, segs=10, loc=(-0.25, 0, 0),
                parent=f_e, mat_=f_col).rotation_euler = (0, math.radians(90), 0)
    # Dorsal fin
    beveled_cube(f"fi{i}_df", (0.10, 0.04, 0.12), bevel_offset=0.02, bevel_segments=3,
                 loc=(0.03, 0, 0.18), parent=f_e, mat_=f_col)
    # Side fins
    for side in (-1, 1):
        beveled_cube(f"fi{i}_sf{side}", (0.08, 0.04, 0.06), bevel_offset=0.02, bevel_segments=3,
                     loc=(0.05, side*0.12, -0.05), parent=f_e, mat_=f_col)
    # Eye
    smooth_sphere(f"fi{i}_ey", r=0.025, loc=(0.18, 0.08, 0.05),
                  parent=f_e, mat_=M_EYE)
    # Stripe (some)
    if i % 3 == 0:
        beveled_cube(f"fi{i}_str", (0.30, 0.04, 0.04), bevel_offset=0.01, bevel_segments=2,
                     loc=(0, 0, 0.05), parent=f_e, mat_=M_FISH_STRIPE)
    f_e["_phase"] = random.uniform(0, math.pi*2)
    f_e["_base_x"] = px; f_e["_base_y"] = py; f_e["_base_z"] = pz
    f_e["_speed"] = random.uniform(0.5, 1.5)
    f_e["_radius"] = random.uniform(3, 10)
    fish.append(f_e)

# 400 manta rays
mantas = []
for i in range(400):
    px = random.uniform(-130, 130)
    py = random.uniform(-130, 130)
    pz = random.uniform(-0.50, 3)
    m_e = empty(f"mt{i}", (px, py, pz))
    # Body diamond shape (signature wide flat)
    smooth_sphere(f"mt{i}_b", r=0.35, segs=16, rings=12, loc=(0, 0, 0),
                  parent=m_e, mat_=M_MANTA_DARK, scale=(2.2, 1.5, 0.20))
    # Belly lighter
    smooth_sphere(f"mt{i}_be", r=0.32, segs=14, rings=10, loc=(0, 0, -0.05),
                  parent=m_e, mat_=M_MANTA_BELLY, scale=(2.0, 1.4, 0.18))
    # Wing tips (signature pointed)
    wing_e_l = empty(f"mt{i}_wl", (0, -0.30, 0), parent=m_e)
    wing_e_r = empty(f"mt{i}_wr", (0, 0.30, 0), parent=m_e)
    smooth_cone(f"mt{i}_wl_t", r1=0.30, r2=0.05, depth=0.40, segs=10,
                loc=(0, -0.40, 0), parent=wing_e_l, mat_=M_MANTA_DARK).rotation_euler = (math.radians(90), 0, 0)
    smooth_cone(f"mt{i}_wr_t", r1=0.30, r2=0.05, depth=0.40, segs=10,
                loc=(0, 0.40, 0), parent=wing_e_r, mat_=M_MANTA_DARK).rotation_euler = (math.radians(-90), 0, 0)
    # Head cephalic fins (signature manta horns)
    for side in (-1, 1):
        cyl(f"mt{i}_cf{side}", r=0.04, depth=0.20, segs=8,
            loc=(0.50, side*0.10, 0.02), parent=m_e, mat_=M_MANTA_DARK).rotation_euler = (0, math.radians(80), math.radians(side*15))
    # Tail (signature long whip)
    cyl(f"mt{i}_t", r=0.03, depth=0.80, segs=10, loc=(-0.55, 0, 0),
        parent=m_e, mat_=M_MANTA_DARK).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"mt{i}_ey{side}", r=0.025, loc=(0.42, side*0.15, 0.03),
                      parent=m_e, mat_=M_EYE)
    m_e["_phase"] = random.uniform(0, math.pi*2)
    m_e["_base_x"] = px; m_e["_base_y"] = py; m_e["_base_z"] = pz
    m_e["_speed"] = random.uniform(0.3, 0.8)
    m_e["_radius"] = random.uniform(6, 15)
    m_e["_wl"] = wing_e_l; m_e["_wr"] = wing_e_r
    mantas.append(m_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Tourists relaxed sway
for t in tourists:
    phase = t["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        ft = (f - 1) / fps
        t["root"].rotation_euler = (math.sin(ft * 1.0 + phase) * math.radians(3), 0,
                                     t["root"].rotation_euler.z)
        t["root"].keyframe_insert("rotation_euler", frame=f)
        t["he"].rotation_euler = (math.sin(ft * 1.0 + phase) * math.radians(4), 0,
                                   math.cos(ft * 0.8 + phase) * math.radians(15))
        t["he"].keyframe_insert("rotation_euler", frame=f)

# Palm sway
for p in palms:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        ft = (f - 1) / fps
        p["crown"].rotation_euler = (math.sin(ft * 0.8 + phase) * math.radians(5),
                                      math.cos(ft * 0.8 + phase) * math.radians(5), 0)
        p["crown"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 fish swim in schools
for fi in fish:
    phase = fi["_phase"]; speed = fi["_speed"]; radius = fi["_radius"]
    bx, by, bz_f = fi["_base_x"], fi["_base_y"], fi["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * radius
        y = by + math.sin(t * speed + phase) * radius
        z = bz_f + math.sin(t * speed * 1.3 + phase) * 0.5
        fi.location = (x, y, z)
        fi.rotation_euler = (math.sin(t * speed * 1.5 + phase) * math.radians(10), 0,
                              math.atan2(math.cos(t * speed + phase),
                                          -math.sin(t * speed + phase)))
        fi.keyframe_insert("location", frame=f)
        fi.keyframe_insert("rotation_euler", frame=f)

# 400 manta rays glide gracefully
for mt in mantas:
    phase = mt["_phase"]; speed = mt["_speed"]; radius = mt["_radius"]
    bx, by, bz_m = mt["_base_x"], mt["_base_y"], mt["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * radius
        y = by + math.sin(t * speed + phase) * radius
        z = bz_m + math.sin(t * speed * 0.8 + phase) * 0.6
        mt.location = (x, y, z)
        mt.rotation_euler = (math.sin(t * speed * 1.2 + phase) * math.radians(15), 0,
                              math.atan2(math.cos(t * speed + phase),
                                          -math.sin(t * speed + phase)))
        mt.keyframe_insert("location", frame=f)
        mt.keyframe_insert("rotation_euler", frame=f)
        # Wing flap (slow graceful)
        wing_a = math.sin(t * 2.0 + phase) * math.radians(20)
        mt["_wl"].rotation_euler = (wing_a, 0, 0)
        mt["_wr"].rotation_euler = (-wing_a, 0, 0)
        mt["_wl"].keyframe_insert("rotation_euler", frame=f)
        mt["_wr"].keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_maldives_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_maldives_overwater_bungalows_reef] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Maldives REALISM EXPERT: 1 SEUL turquoise lagoon ground (organic sphere variations only) + 6 overwater bungalows with conical thatch roofs + stilts + decks + stairs + sand island with 5 palms + coral reef 80 colorful organic corals (brain/branching/plate/tubular) + 4 tourists with joint-sphere anatomy + swimsuits + sunglasses + Maldives crescent flag + 600 tropical fish (signature multi-color streamlined organic) + 400 manta rays (signature diamond + cephalic fins + whip tail + wing flap)")
print("🐟 REALISM: bevel>=0.15 segs>=5 + smooth_sphere stretched + joint spheres + organic corals + no naked cubes 🐟")
