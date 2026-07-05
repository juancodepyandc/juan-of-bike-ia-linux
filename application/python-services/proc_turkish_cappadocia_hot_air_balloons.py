"""
proc_turkish_cappadocia_hot_air_balloons.py — 275e procédural AuroraIA (140e qualité)
Turkey Cappadocia hot air balloons sunrise: 12 fairy chimneys + 8 colorful hot air balloons + 4 tourists + mosque silhouette minaret + Turkey flag + 600 tulip petals + 400 swallows
FIXES : 1 ground tuf rock + signature tulips + swallows
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB275)

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

# Sunrise sky Cappadocia (signature)
M_SKY = mat("sky", (1.0, 0.62, 0.45, 1.0), 0.0, 0.7, emission=(1.0,0.62,0.45), emission_strength=2.5)
M_SKY_LOW = mat("sky_l", (1.0, 0.85, 0.55, 1.0), 0.0, 0.7, emission=(1.0,0.85,0.55), emission_strength=2.0)
M_SKY_HIGH = mat("sky_h", (0.55, 0.30, 0.45, 1.0), 0.0, 0.7, emission=(0.55,0.30,0.45), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.85, 0.40, 1.0), 0.0, 0.1, emission=(1.0,0.85,0.40), emission_strength=25.0)

# Tuf rock (signature Cappadocia volcanic)
M_TUF = mat("tf", (0.85, 0.72, 0.50, 1.0), 0.0, 0.85, emission=(0.82,0.70,0.50), emission_strength=0.4)
M_TUF_DARK = mat("tfd", (0.55, 0.42, 0.28, 1.0), 0.0, 0.92)
M_TUF_LIGHT = mat("tfl", (0.95, 0.85, 0.65, 1.0), 0.0, 0.75, emission=(0.92,0.82,0.62), emission_strength=0.5)
M_TUF_RED = mat("tfr", (0.85, 0.55, 0.40, 1.0), 0.0, 0.85, emission=(0.82,0.55,0.40), emission_strength=0.3)
M_DIRT = mat("d", (0.62, 0.42, 0.25, 1.0), 0.0, 0.92)

# Balloon colors (signature vibrant Cappadocia)
M_BAL_RED = mat("br", (0.92, 0.20, 0.20, 1.0), 0.0, 0.45, emission=(0.90,0.20,0.20), emission_strength=1.0)
M_BAL_YELLOW = mat("by", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.20), emission_strength=1.2)
M_BAL_BLUE = mat("bbl", (0.20, 0.55, 0.95, 1.0), 0.0, 0.45, emission=(0.20,0.55,0.92), emission_strength=1.0)
M_BAL_ORANGE = mat("bor", (1.0, 0.55, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.20), emission_strength=1.2)
M_BAL_PURPLE = mat("bp", (0.55, 0.25, 0.85, 1.0), 0.0, 0.45, emission=(0.52,0.25,0.82), emission_strength=1.0)
M_BAL_GREEN = mat("bg", (0.30, 0.85, 0.40, 1.0), 0.0, 0.45, emission=(0.30,0.82,0.40), emission_strength=1.0)
M_BAL_PINK = mat("bpk", (1.0, 0.55, 0.78, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.75), emission_strength=1.0)
M_BAL_TURQ = mat("btq", (0.30, 0.85, 0.85, 1.0), 0.0, 0.45, emission=(0.30,0.82,0.82), emission_strength=1.0)
BALLOON_COLORS = [M_BAL_RED, M_BAL_YELLOW, M_BAL_BLUE, M_BAL_ORANGE, M_BAL_PURPLE, M_BAL_GREEN, M_BAL_PINK, M_BAL_TURQ]
M_BAL_WHITE = mat("bw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.90), emission_strength=0.7)
M_BAL_STRIPE_DARK = mat("bsd", (0.32, 0.18, 0.10, 1.0), 0.0, 0.65)

# Basket
M_BASKET = mat("bk", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85, emission=(0.52,0.30,0.15), emission_strength=0.3)
M_BASKET_DARK = mat("bkd", (0.32, 0.18, 0.08, 1.0), 0.0, 0.92)
M_ROPE = mat("rp", (0.65, 0.55, 0.30, 1.0), 0.0, 0.85)

# Flame
M_FLAME = mat("fl", (1.0, 0.55, 0.15, 1.0), 0.2, 0.10, emission=(1.0,0.55,0.15), emission_strength=18.0, alpha=0.85)
M_FLAME_BLUE = mat("flbl", (0.30, 0.55, 1.0, 1.0), 0.2, 0.10, emission=(0.30,0.55,0.95), emission_strength=15.0, alpha=0.80)

# Skin/hair
M_SKIN = mat("sk", (0.85, 0.65, 0.45, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.45), emission_strength=0.3)
M_HAIR_BROWN = mat("hb", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)
M_HAIR_BLACK = mat("hbk", (0.08, 0.06, 0.05, 1.0), 0.0, 0.85)

# Tourist clothing
M_JACKET_RED = mat("jr", (0.85, 0.25, 0.20, 1.0), 0.0, 0.55, emission=(0.82,0.25,0.20), emission_strength=0.5)
M_JACKET_BLUE = mat("jb", (0.20, 0.42, 0.75, 1.0), 0.0, 0.55, emission=(0.20,0.42,0.72), emission_strength=0.5)
M_JACKET_GREEN = mat("jg", (0.30, 0.65, 0.40, 1.0), 0.0, 0.55, emission=(0.30,0.62,0.40), emission_strength=0.5)
M_JACKET_PURPLE = mat("jp", (0.55, 0.30, 0.85, 1.0), 0.0, 0.55, emission=(0.52,0.30,0.82), emission_strength=0.5)
JACKET_COLORS = [M_JACKET_RED, M_JACKET_BLUE, M_JACKET_GREEN, M_JACKET_PURPLE]
M_PANTS_BLUE = mat("pb", (0.20, 0.30, 0.55, 1.0), 0.0, 0.65)
M_SHOE = mat("sho", (0.18, 0.10, 0.08, 1.0), 0.2, 0.45)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Mosque
M_MOSQUE_WHITE = mat("mw", (0.85, 0.82, 0.75, 1.0), 0.0, 0.65, emission=(0.82,0.80,0.75), emission_strength=0.5)
M_MOSQUE_DOME = mat("mdo", (0.30, 0.50, 0.70, 1.0), 0.4, 0.20, emission=(0.30,0.48,0.68), emission_strength=0.7)
M_MOSQUE_GOLD = mat("mg", (0.95, 0.78, 0.25, 1.0), 0.7, 0.20, emission=(0.92,0.75,0.25), emission_strength=1.2)

# Turkey flag
M_FLAG_RED = mat("fr", (0.85, 0.10, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.10,0.18), emission_strength=1.2)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)

# Tulip petals
M_TULIP_RED = mat("tlr", (0.92, 0.18, 0.25, 1.0), 0.0, 0.40, emission=(0.90,0.18,0.25), emission_strength=2.0)
M_TULIP_PINK = mat("tlp", (1.0, 0.55, 0.78, 1.0), 0.0, 0.40, emission=(0.95,0.55,0.75), emission_strength=2.0)
M_TULIP_YELLOW = mat("tly", (1.0, 0.85, 0.30, 1.0), 0.0, 0.40, emission=(0.95,0.82,0.30), emission_strength=2.0)
M_TULIP_PURPLE = mat("tlpu", (0.65, 0.30, 0.85, 1.0), 0.0, 0.40, emission=(0.62,0.30,0.82), emission_strength=2.0)
M_TULIP_ORANGE = mat("tlo", (1.0, 0.55, 0.15, 1.0), 0.0, 0.40, emission=(0.95,0.55,0.15), emission_strength=2.0)
TULIP_COLORS = [M_TULIP_RED, M_TULIP_PINK, M_TULIP_YELLOW, M_TULIP_PURPLE, M_TULIP_ORANGE]
M_LEAF_GREEN = mat("lg", (0.30, 0.62, 0.25, 1.0), 0.0, 0.50, emission=(0.28,0.60,0.25), emission_strength=0.5)

# Swallow bird
M_SWALLOW_BLACK = mat("sb", (0.10, 0.10, 0.12, 1.0), 0.0, 0.55, emission=(0.10,0.10,0.12), emission_strength=0.3)
M_SWALLOW_BELLY = mat("sbe", (0.85, 0.75, 0.55, 1.0), 0.0, 0.55, emission=(0.82,0.72,0.55), emission_strength=0.4)
M_SWALLOW_RED = mat("sbr", (0.85, 0.32, 0.22, 1.0), 0.0, 0.45, emission=(0.82,0.32,0.22), emission_strength=0.6)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sky_h = smooth_sphere("sky_h", r=260, segs=28, rings=16, loc=(0,0,15), mat_=M_SKY_HIGH)
sky_h.scale = (1,1,0.2)
# Big sunrise sun (signature)
sun = smooth_sphere("sun", r=15, segs=28, rings=20, loc=(0, 110, 25), mat_=M_SUN)
for sh in range(5):
    smooth_sphere(f"sun_h{sh}", r=15 + sh*1.5, segs=24, rings=18, loc=(0, 110, 25), mat_=M_SUN)

# ============ ONE clean tuf rock ground ============
ground = beveled_cube("ground", (280, 280, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_TUF)
# Tuf rock outcrops scattered
for ri in range(250):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 130)
    smooth_sphere(f"rk{ri}", r=random.uniform(0.5, 1.3), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.12),
                  mat_=M_TUF_DARK if ri % 3 == 0 else (M_TUF if ri % 3 == 1 else M_TUF_RED),
                  scale=(1.4, 1.3, 0.22))
# Dirt patches (paths)
for di in range(50):
    smooth_sphere(f"di{di}", r=random.uniform(0.6, 1.0), segs=10, rings=6,
                  loc=(random.uniform(-100, 100), random.uniform(-100, 100), 0.10),
                  mat_=M_DIRT, scale=(1.4, 1.3, 0.20))

# ============ 12 FAIRY CHIMNEYS (signature Cappadocia rock formations) ============
def make_fairy_chimney(name, loc, height, base_radius, has_cap=True):
    base = empty(name, loc)
    # Main pillar (tapered)
    n_sections = max(5, int(height / 2))
    for si in range(n_sections):
        sz = si * (height / n_sections)
        sr = base_radius * (1 - si / n_sections * 0.5) + random.uniform(-0.1, 0.1)
        # Carved cave windows (some sections have holes)
        smooth_sphere(f"{name}_s{si}", r=sr, segs=16, rings=12,
                      loc=(random.uniform(-0.15, 0.15), random.uniform(-0.15, 0.15), sz + height/n_sections/2),
                      parent=base, mat_=M_TUF if si % 2 == 0 else M_TUF_LIGHT,
                      scale=(1.1, 1.0, 1.0))
    # MUSHROOM CAP at top (signature darker basalt cap)
    if has_cap:
        cap_e = empty(f"{name}_ce", (0, 0, height), parent=base)
        smooth_sphere(f"{name}_cap", r=base_radius * 1.4, segs=18, rings=14,
                      loc=(0, 0, 0), parent=cap_e, mat_=M_TUF_DARK,
                      scale=(1.2, 1.2, 0.55))
        # Cap rim shadow
        cyl(f"{name}_cr", r=base_radius * 1.45, depth=0.20, segs=18,
            loc=(0, 0, -0.15), parent=cap_e, mat_=M_TUF_DARK)
    # Cave openings (signature - dark holes for living)
    for cv in range(3):
        cva = (cv / 3.0) * math.pi * 2
        cvy = height * 0.4 + cv * height * 0.18
        # Hole opening
        cyl(f"{name}_cv{cv}", r=0.30, depth=0.20, segs=10,
            loc=(math.cos(cva)*base_radius*0.9, math.sin(cva)*base_radius*0.9, cvy),
            parent=base, mat_=M_TUF_DARK).rotation_euler = (math.radians(90), 0, cva)
    return base

chimneys = []
chimney_data = [
    (-25, -20, 8, 2.2, True), (-15, -25, 12, 3.0, True), (-5, -20, 10, 2.5, True),
    (5, -22, 14, 3.5, True), (15, -25, 9, 2.3, True), (25, -20, 11, 2.8, True),
    (-30, 5, 15, 4.0, True), (-15, 10, 13, 3.2, True), (10, 8, 16, 4.5, True),
    (25, 5, 12, 3.0, True), (-20, 25, 18, 5.0, True), (20, 25, 14, 3.5, True)
]
for i, (cx, cy, ch, cr, cap) in enumerate(chimney_data):
    c = make_fairy_chimney(f"fc{i}", (cx, cy, 0), ch, cr, has_cap=cap)
    chimneys.append(c)

# ============ 8 HOT AIR BALLOONS (signature) ============
def make_balloon(name, loc, scale=1.0):
    base = empty(name, loc)
    bal_col = random.choice(BALLOON_COLORS)
    bal_col_alt = random.choice([c for c in BALLOON_COLORS if c != bal_col])
    # Main balloon envelope (sphere stretched up)
    envelope_e = empty(f"{name}_ee", (0, 0, 6), parent=base)
    # Stitched panels (signature)
    n_panels = 12
    for pi in range(n_panels):
        pa = (pi / n_panels) * math.pi * 2
        # Panel as curved segment
        panel_e = empty(f"{name}_p{pi}_e", (0, 0, 0), parent=envelope_e)
        panel_e.rotation_euler = (0, 0, pa)
        # Panel shape (stretched sphere segment)
        panel_col = bal_col if pi % 2 == 0 else bal_col_alt
        for ri in range(8):
            rh = (ri / 8.0) * math.pi
            rr = 4 * math.sin(rh) + 0.2
            rh_z = -4 * math.cos(rh) + 4
            smooth_sphere(f"{name}_p{pi}_s{ri}", r=0.5,
                          loc=(rr, 0, rh_z), parent=panel_e, mat_=panel_col,
                          scale=(0.6, 0.5, 0.6))
    # Top apex
    smooth_sphere(f"{name}_ap", r=0.40, segs=12, rings=10, loc=(0, 0, 4.2),
                  parent=envelope_e, mat_=bal_col)
    # Bottom opening (signature)
    cyl(f"{name}_op", r=0.8, depth=0.5, segs=16, loc=(0, 0, -4.0),
        parent=envelope_e, mat_=M_BAL_STRIPE_DARK)
    # Flame (visible)
    flame_e = empty(f"{name}_fle", (0, 0, -3.7), parent=envelope_e)
    smooth_cone(f"{name}_fl_b", r1=0.30, r2=0.05, depth=0.50, segs=12, loc=(0, 0, -0.25),
                parent=flame_e, mat_=M_FLAME).rotation_euler = (math.radians(180), 0, 0)
    smooth_cone(f"{name}_fl_c", r1=0.15, r2=0.02, depth=0.30, segs=12, loc=(0, 0, -0.10),
                parent=flame_e, mat_=M_FLAME_BLUE).rotation_euler = (math.radians(180), 0, 0)
    flame_e["_phase"] = random.uniform(0, math.pi*2)
    # Ropes connecting to basket
    for ri in range(4):
        ra = (ri / 4.0) * math.pi * 2 + math.pi/4
        cyl(f"{name}_r{ri}", r=0.02, depth=2.5, segs=6,
            loc=(math.cos(ra)*0.7, math.sin(ra)*0.7, 0.8),
            parent=base, mat_=M_ROPE)
    # BASKET (signature wicker)
    basket_e = empty(f"{name}_bke", (0, 0, -0.5), parent=base)
    # Basket main body
    beveled_cube(f"{name}_bk", (1.5, 1.5, 1.0), bevel_offset=0.08, loc=(0, 0, 0),
                 parent=basket_e, mat_=M_BASKET)
    # Wicker pattern (horizontal bands)
    for bi in range(5):
        bz_b = -0.40 + bi * 0.20
        cyl(f"{name}_bkb{bi}", r=0.78, depth=0.06, segs=18, loc=(0, 0, bz_b),
            parent=basket_e, mat_=M_BASKET_DARK)
    # Rim
    cyl(f"{name}_bkr", r=0.78, depth=0.10, segs=18, loc=(0, 0, 0.55),
        parent=basket_e, mat_=M_BASKET_DARK)
    # Gas tank
    for tk in (-1, 1):
        cyl(f"{name}_tk{tk}", r=0.18, depth=0.45, segs=12, loc=(tk*0.55, 0, 0.10),
            parent=basket_e, mat_=M_MOSQUE_WHITE)
    # Pilot inside basket
    smooth_sphere(f"{name}_pl_h", r=0.15, segs=14, rings=10, loc=(0, 0, 1.0),
                  parent=basket_e, mat_=M_SKIN)
    smooth_cone(f"{name}_pl_b", r1=0.20, r2=0.22, depth=0.40, segs=14, loc=(0, 0, 0.65),
                parent=basket_e, mat_=random.choice(JACKET_COLORS))
    base["_phase"] = random.uniform(0, math.pi*2)
    base["_base_x"] = loc[0]; base["_base_y"] = loc[1]; base["_base_z"] = loc[2]
    base["_drift"] = random.uniform(0.05, 0.15)
    return {"root": base, "envelope": envelope_e, "flame": flame_e}

balloons = []
balloon_pos = [
    (-30, -10, 18), (-15, -5, 25), (0, 0, 30), (15, -5, 22),
    (30, -10, 28), (-25, 15, 32), (10, 20, 26), (28, 12, 35)
]
for i, (bx, by, bz) in enumerate(balloon_pos):
    b = make_balloon(f"bal{i}", (bx, by, bz))
    balloons.append(b)

# ============ 4 TOURISTS on ground (signature) ============
def make_tourist(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    jacket_col = random.choice(JACKET_COLORS)
    # Jacket
    smooth_cone(f"{name}_j", r1=0.30, r2=0.32, depth=0.85, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=jacket_col)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.11, depth=0.95, segs=10,
            loc=(side*0.13, 0, 0.50), parent=base, mat_=M_PANTS_BLUE)
    # Shoes
    for side in (-1, 1):
        beveled_cube(f"{name}_sh{side}", (0.13, 0.26, 0.06), bevel_offset=0.02,
                     loc=(side*0.13, 0, 0.03), parent=base, mat_=M_SHOE)
    # Arms (pointing up at balloons)
    sh_l = empty(f"{name}_a0", (-0.28, 0, 1.60), parent=base)
    sh_l.rotation_euler = (math.radians(-150), 0, 0)
    cyl(f"{name}_ua0", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=jacket_col)
    cyl(f"{name}_fa0", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_SKIN)
    sh_r = empty(f"{name}_a1", (0.28, 0, 1.60), parent=base)
    sh_r.rotation_euler = (math.radians(-100), 0, math.radians(-15))
    cyl(f"{name}_ua1", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=jacket_col)
    cyl(f"{name}_fa1", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_SKIN)
    # Camera in right hand
    beveled_cube(f"{name}_cam", (0.10, 0.15, 0.10), bevel_offset=0.02,
                 loc=(0, 0, -0.75), parent=sh_r, mat_=M_BAL_STRIPE_DARK)
    cyl(f"{name}_cam_l", r=0.04, depth=0.05, segs=10,
        loc=(0, -0.08, -0.75), parent=sh_r, mat_=M_MOSQUE_WHITE).rotation_euler = (math.radians(90), 0, 0)
    # Head
    head_t_e = empty(f"{name}_he", (0, 0, 1.90), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_t_e, mat_=M_SKIN)
    # Hair
    for hi in range(12):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.10, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.15),
            parent=head_t_e, mat_=random.choice([M_HAIR_BROWN, M_HAIR_BLACK]))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_t_e, mat_=M_EYE)
    # Beanie hat
    if random.random() > 0.5:
        cyl(f"{name}_hat", r=0.20, depth=0.16, segs=14, loc=(0, 0, 0.16),
            parent=head_t_e, mat_=random.choice(JACKET_COLORS))
        smooth_sphere(f"{name}_hatp", r=0.06, loc=(0, 0, 0.28),
                      parent=head_t_e, mat_=M_BAL_WHITE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_t_e}

tourists = []
for i, (tx, ty, fac) in enumerate([(-8, 30, math.radians(180)), (-2, 32, math.radians(170)),
                                     (4, 30, math.radians(190)), (10, 32, math.radians(180))]):
    t = make_tourist(f"to{i}", (tx, ty, 0), facing=fac)
    tourists.append(t)

# ============ MOSQUE silhouette (signature) ============
mosque_e = empty("mosque", (-45, 45, 0))
# Main building
beveled_cube("mo_b", (8, 8, 5), bevel_offset=0.15, loc=(0, 0, 2.5),
             parent=mosque_e, mat_=M_MOSQUE_WHITE)
# Dome (signature blue)
smooth_sphere("mo_d", r=4, segs=22, rings=18, loc=(0, 0, 6),
              parent=mosque_e, mat_=M_MOSQUE_DOME, scale=(1, 1, 0.7))
# Small domes around
for di in range(4):
    da = (di / 4.0) * math.pi * 2 + math.pi/4
    smooth_sphere(f"mo_sd{di}", r=1.2, segs=14, rings=10,
                  loc=(math.cos(da)*5, math.sin(da)*5, 5.5),
                  parent=mosque_e, mat_=M_MOSQUE_DOME, scale=(1, 1, 0.7))
# Minarets (signature 4 corners)
for mi in range(4):
    ma = (mi / 4.0) * math.pi * 2 + math.pi/4
    minaret_e = empty(f"mo_mn{mi}_e", (math.cos(ma)*5.5, math.sin(ma)*5.5, 0), parent=mosque_e)
    # Tall tower
    cyl(f"mo_mn{mi}_t", r=0.50, depth=12, segs=14, loc=(0, 0, 6),
        parent=minaret_e, mat_=M_MOSQUE_WHITE)
    # Balcony
    cyl(f"mo_mn{mi}_ba", r=0.65, depth=0.30, segs=14, loc=(0, 0, 11),
        parent=minaret_e, mat_=M_MOSQUE_WHITE)
    # Cone roof
    smooth_cone(f"mo_mn{mi}_cn", r1=0.55, r2=0.05, depth=2, segs=12, loc=(0, 0, 13),
                parent=minaret_e, mat_=M_MOSQUE_DOME)
    # Crescent on top
    smooth_sphere(f"mo_mn{mi}_cr", r=0.20, loc=(0, 0, 14.5),
                  parent=minaret_e, mat_=M_MOSQUE_GOLD, scale=(1, 0.3, 1))
# Crescent on main dome
smooth_sphere("mo_d_cr", r=0.40, loc=(0, 0, 9), parent=mosque_e, mat_=M_MOSQUE_GOLD, scale=(1, 0.3, 1))

# ============ TURKEY FLAG (signature crescent + star) ============
flag_e = empty("flag", (45, 40, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_BAL_STRIPE_DARK)
# Red flag field
beveled_cube("fl_f", (4, 0.05, 2.5), bevel_offset=0.06, loc=(2, 0, 10.5),
             parent=flag_e, mat_=M_FLAG_RED)
# CRESCENT (signature)
cres_e = empty("fl_cr", (1.5, -0.05, 10.5), parent=flag_e)
# Outer crescent shape (sphere)
smooth_sphere("fl_cr_o", r=0.40, segs=18, rings=14, loc=(0, 0, 0),
              parent=cres_e, mat_=M_FLAG_WHITE)
# Inner cut (background red sphere offset)
smooth_sphere("fl_cr_i", r=0.36, segs=18, rings=14, loc=(0.15, -0.04, 0),
              parent=cres_e, mat_=M_FLAG_RED)
# STAR (signature 5-point white)
star_e = empty("fl_st", (2.5, -0.06, 10.5), parent=flag_e)
for sp in range(5):
    spa = (sp / 5.0) * math.pi * 2 + math.pi/2
    beveled_cube(f"fl_st_p{sp}", (0.05, 0.06, 0.30), bevel_offset=0.01,
                 loc=(math.cos(spa)*0.15, 0, math.sin(spa)*0.15),
                 parent=star_e, mat_=M_FLAG_WHITE).rotation_euler = (spa - math.pi/2, 0, 0)
smooth_sphere("fl_stc", r=0.10, loc=(0, 0, 0), parent=star_e, mat_=M_FLAG_WHITE)
flag_e["_phase"] = 0

# ============================================================
# 600 TULIP PETALS + 400 SWALLOWS (PARTICULES SIGNATURES)
# ============================================================
tulips = []
for i in range(600):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = random.uniform(2, 25)
    t_col = random.choice(TULIP_COLORS)
    t_e = empty(f"tl{i}", (px, py, pz))
    # Tulip petals (cup shape)
    for pp in range(6):
        ppa = (pp / 6.0) * math.pi * 2
        pet_e = empty(f"tl{i}_pe{pp}_e", (0, 0, 0), parent=t_e)
        pet_e.rotation_euler = (math.radians(-20), 0, ppa)
        beveled_cube(f"tl{i}_pe{pp}", (0.04, 0.10, 0.06), bevel_offset=0.005,
                     loc=(0.04, 0, 0), parent=pet_e, mat_=t_col)
    # Center
    smooth_sphere(f"tl{i}_c", r=0.03, loc=(0, 0, -0.02), parent=t_e, mat_=M_TULIP_YELLOW)
    # Small leaf
    beveled_cube(f"tl{i}_lf", (0.04, 0.08, 0.02), bevel_offset=0.005,
                 loc=(0.05, 0, -0.10), parent=t_e, mat_=M_LEAF_GREEN)
    t_e["_phase"] = random.uniform(0, math.pi*2)
    t_e["_base_x"] = px; t_e["_base_z"] = pz
    t_e["_drift"] = random.uniform(0.2, 0.6)
    t_e["_fall"] = random.uniform(0.5, 1.3)
    t_e["_swing"] = random.uniform(1.0, 2.2)
    tulips.append(t_e)

# 400 swallows
swallows = []
for i in range(400):
    px = random.uniform(-110, 110)
    py = random.uniform(-110, 110)
    pz = random.uniform(8, 45)
    s_e = empty(f"sw{i}", (px, py, pz))
    # Body
    smooth_sphere(f"sw{i}_bo", r=0.10, segs=10, rings=8, loc=(0, 0, 0),
                  parent=s_e, mat_=M_SWALLOW_BLACK, scale=(1.5, 0.85, 0.85))
    # Belly cream
    smooth_sphere(f"sw{i}_be", r=0.09, segs=10, rings=8, loc=(0, 0, -0.04),
                  parent=s_e, mat_=M_SWALLOW_BELLY, scale=(1.3, 0.7, 0.6))
    # Red throat patch (signature)
    smooth_sphere(f"sw{i}_th", r=0.05, segs=8, rings=6, loc=(0.10, 0, 0.02),
                  parent=s_e, mat_=M_SWALLOW_RED)
    # FORKED TAIL (signature swallow)
    for tail_s in (-1, 1):
        beveled_cube(f"sw{i}_t{tail_s}", (0.08, 0.04, 0.02), bevel_offset=0.005,
                     loc=(-0.18, tail_s*0.04, -0.03), parent=s_e, mat_=M_SWALLOW_BLACK).rotation_euler = (0, 0, tail_s*math.radians(20))
    # Wings (signature pointed)
    wing_e_l = empty(f"sw{i}_wl_e", (0, -0.06, 0), parent=s_e)
    wing_e_r = empty(f"sw{i}_wr_e", (0, 0.06, 0), parent=s_e)
    beveled_cube(f"sw{i}_wl", (0.12, 0.30, 0.015), bevel_offset=0.005, loc=(0, -0.15, 0),
                 parent=wing_e_l, mat_=M_SWALLOW_BLACK).rotation_euler = (0, 0, math.radians(-20))
    beveled_cube(f"sw{i}_wr", (0.12, 0.30, 0.015), bevel_offset=0.005, loc=(0, 0.15, 0),
                 parent=wing_e_r, mat_=M_SWALLOW_BLACK).rotation_euler = (0, 0, math.radians(20))
    # Tiny beak
    cyl(f"sw{i}_bk", r=0.012, depth=0.05, segs=6, loc=(0.18, 0, 0.02),
        parent=s_e, mat_=M_SWALLOW_BLACK).rotation_euler = (0, math.radians(90), 0)
    s_e["_phase"] = random.uniform(0, math.pi*2)
    s_e["_base_x"] = px; s_e["_base_y"] = py; s_e["_base_z"] = pz
    s_e["_speed"] = random.uniform(0.8, 1.8)
    s_e["_radius"] = random.uniform(5, 14)
    s_e["_wl"] = wing_e_l; s_e["_wr"] = wing_e_r
    swallows.append(s_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Balloons rise/drift
for b in balloons:
    phase = b["root"]["_phase"]
    bx, by, bz_b = b["root"]["_base_x"], b["root"]["_base_y"], b["root"]["_base_z"]
    drift = b["root"]["_drift"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        b["root"].location = (bx + math.sin(t * 0.3 + phase) * 1.5 + t * drift,
                              by + math.cos(t * 0.3 + phase) * 1.0,
                              bz_b + math.sin(t * 0.5 + phase) * 0.8)
        b["root"].rotation_euler = (math.sin(t * 0.5 + phase) * math.radians(3),
                                     math.cos(t * 0.5 + phase) * math.radians(2), 0)
        b["root"].keyframe_insert("location", frame=f)
        b["root"].keyframe_insert("rotation_euler", frame=f)
    # Flame flicker
    flame_phase = b["flame"]["_phase"]
    for f in range(1, total_frames + 1, 2):
        ft = (f - 1) / fps
        sc_f = 1 + math.sin(ft * 10.0 + flame_phase) * 0.30
        b["flame"].scale = (sc_f, sc_f, sc_f * (1 + math.cos(ft * 8.0 + flame_phase) * 0.20))
        b["flame"].keyframe_insert("scale", frame=f)

# Tourists wave at balloons
for t in tourists:
    phase = t["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        ft = (f - 1) / fps
        t["root"].rotation_euler = (math.sin(ft * 1.5 + phase) * math.radians(3), 0,
                                     t["root"].rotation_euler.z)
        t["root"].keyframe_insert("rotation_euler", frame=f)
        t["he"].rotation_euler = (math.radians(-15) + math.sin(ft * 1.0 + phase) * math.radians(8), 0,
                                   math.cos(ft * 1.0 + phase) * math.radians(15))
        t["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 tulip petals fall + sway
for tl in tulips:
    phase = tl["_phase"]; drift = tl["_drift"]; fall = tl["_fall"]; swing = tl["_swing"]
    bx, bz = tl["_base_x"], tl["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.8 + t * drift
        z = bz - (t * fall) % 22
        tl.location = (x, tl.location.y, z)
        tl.rotation_euler = (t * 1.5 + phase, math.sin(t * 2.0 + phase) * math.radians(30), t * 1.0 + phase)
        tl.keyframe_insert("location", frame=f)
        tl.keyframe_insert("rotation_euler", frame=f)

# 400 swallows fly in circles with wing flap
for sw in swallows:
    phase = sw["_phase"]; speed = sw["_speed"]; radius = sw["_radius"]
    bx, by, bz_s = sw["_base_x"], sw["_base_y"], sw["_base_z"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * radius
        y = by + math.sin(t * speed + phase) * radius
        z = bz_s + math.sin(t * speed * 1.3 + phase) * 2
        sw.location = (x, y, z)
        sw.rotation_euler = (0, 0, math.atan2(math.cos(t * speed + phase),
                                                -math.sin(t * speed + phase)))
        sw.keyframe_insert("location", frame=f)
        sw.keyframe_insert("rotation_euler", frame=f)
        # Wing flap fast
        wing_a = math.sin(t * 18.0 + phase) * math.radians(35)
        sw["_wl"].rotation_euler = (0, wing_a, 0)
        sw["_wr"].rotation_euler = (0, -wing_a, 0)
        sw["_wl"].keyframe_insert("rotation_euler", frame=f)
        sw["_wr"].keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_turkey_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_turkish_cappadocia_hot_air_balloons] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Turkey Cappadocia: 12 fairy chimneys with mushroom basalt caps + 3 cave openings each + 8 hot air balloons with 12-panel stitched envelopes (alternating colors) + flame visible inside + wicker baskets with pilots + drifting/floating animation + 4 tourists with cameras + mosque with central dome + 4 minarets + 4 side domes + golden crescents + Turkey flag with crescent moon + 5-point star + huge sunrise sun")
print("🌷 FIXES: 1 tuf rock ground + 600 colorful tulip petals + 400 swallows with forked tails flying signature 🌷")
