"""
proc_hongkong_night_skyline_skyscrapers.py — 290e MILESTONE procédural AuroraIA (155e qualité)
Hong Kong night skyline: 15 skyscrapers Bank of China + IFC + Victoria Harbour + 4 red junks + 4 businessmen + Star Ferry + Hong Kong flag + 1000 neon lights + 500 chinese lanterns (DOUBLE MILESTONE)
FIXES : 1 ground harbour water + DOUBLE signature neons + lanterns
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB290)

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

# Night sky
M_SKY = mat("sky", (0.05, 0.05, 0.18, 1.0), 0.0, 0.7, emission=(0.05,0.05,0.18), emission_strength=1.0)
M_SKY_LOW = mat("sky_l", (0.30, 0.18, 0.45, 1.0), 0.0, 0.7, emission=(0.30,0.18,0.45), emission_strength=1.3)
M_MOON = mat("mn", (0.92, 0.92, 0.85, 1.0), 0.0, 0.1, emission=(0.90,0.90,0.85), emission_strength=12.0)
M_STAR = mat("st", (1.0, 0.95, 0.85, 1.0), 0.0, 0.1, emission=(1.0,0.95,0.85), emission_strength=6.0)

# Victoria Harbour water (signature dark with reflections)
M_HARBOUR = mat("hb", (0.10, 0.15, 0.25, 1.0), 0.3, 0.15, emission=(0.10,0.15,0.25), emission_strength=1.2, alpha=0.85)
M_HARBOUR_REFLECT = mat("hbr", (0.42, 0.55, 0.78, 1.0), 0.3, 0.10, emission=(0.42,0.55,0.78), emission_strength=2.5, alpha=0.60)

# Skyscraper materials
M_GLASS_BLUE = mat("gb", (0.20, 0.45, 0.85, 1.0), 0.5, 0.15, emission=(0.20,0.45,0.82), emission_strength=2.5, alpha=0.70)
M_GLASS_DARK = mat("gd", (0.32, 0.32, 0.42, 1.0), 0.6, 0.10, emission=(0.30,0.30,0.40), emission_strength=0.5, alpha=0.85)
M_GLASS_GOLD = mat("gg", (0.92, 0.78, 0.30, 1.0), 0.7, 0.10, emission=(0.88,0.75,0.30), emission_strength=2.0, alpha=0.75)
M_GLASS_WARM = mat("gw", (0.95, 0.82, 0.55, 1.0), 0.4, 0.15, emission=(0.92,0.80,0.55), emission_strength=2.2, alpha=0.75)
M_STEEL = mat("st_m", (0.55, 0.55, 0.60, 1.0), 0.7, 0.30)
M_STEEL_DARK = mat("std", (0.32, 0.32, 0.35, 1.0), 0.6, 0.40)
M_CONCRETE = mat("co", (0.65, 0.65, 0.62, 1.0), 0.0, 0.85, emission=(0.62,0.62,0.62), emission_strength=0.3)

# Building windows (signature lit at night)
M_WIN_WARM = mat("ww", (1.0, 0.85, 0.45, 1.0), 0.0, 0.10, emission=(0.95,0.82,0.45), emission_strength=5.0)
M_WIN_BLUE = mat("wbl", (0.45, 0.78, 1.0, 1.0), 0.0, 0.10, emission=(0.42,0.75,0.95), emission_strength=4.5)
M_WIN_DARK = mat("wdk", (0.18, 0.18, 0.22, 1.0), 0.4, 0.30)
WIN_COLORS = [M_WIN_WARM, M_WIN_BLUE, M_WIN_DARK]

# Neon sign colors
M_NEON_RED = mat("nr", (1.0, 0.20, 0.20, 1.0), 0.0, 0.05, emission=(0.95,0.18,0.18), emission_strength=12.0)
M_NEON_PINK = mat("npk", (1.0, 0.30, 0.85, 1.0), 0.0, 0.05, emission=(0.95,0.30,0.82), emission_strength=12.0)
M_NEON_CYAN = mat("ncy", (0.30, 1.0, 1.0, 1.0), 0.0, 0.05, emission=(0.30,0.95,0.95), emission_strength=12.0)
M_NEON_GREEN = mat("ngn", (0.30, 1.0, 0.30, 1.0), 0.0, 0.05, emission=(0.30,0.95,0.30), emission_strength=12.0)
M_NEON_PURPLE = mat("npu", (0.75, 0.30, 1.0, 1.0), 0.0, 0.05, emission=(0.72,0.30,0.95), emission_strength=12.0)
M_NEON_YELLOW = mat("ny", (1.0, 0.92, 0.30, 1.0), 0.0, 0.05, emission=(0.95,0.88,0.30), emission_strength=12.0)
M_NEON_ORANGE = mat("no", (1.0, 0.55, 0.18, 1.0), 0.0, 0.05, emission=(0.95,0.55,0.18), emission_strength=12.0)
NEON_COLORS = [M_NEON_RED, M_NEON_PINK, M_NEON_CYAN, M_NEON_GREEN, M_NEON_PURPLE, M_NEON_YELLOW, M_NEON_ORANGE]

# Junk boat
M_JUNK_RED = mat("jr", (0.85, 0.20, 0.20, 1.0), 0.0, 0.55, emission=(0.82,0.20,0.20), emission_strength=0.7)
M_JUNK_DARK = mat("jrd", (0.42, 0.10, 0.10, 1.0), 0.0, 0.65)
M_SAIL_RED = mat("sr", (0.85, 0.18, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.18), emission_strength=0.8)
M_ROPE = mat("rp", (0.55, 0.42, 0.20, 1.0), 0.0, 0.85)

# Star Ferry (signature green)
M_FERRY_GREEN = mat("fg", (0.20, 0.55, 0.32, 1.0), 0.0, 0.55, emission=(0.20,0.52,0.30), emission_strength=0.6)
M_FERRY_WHITE = mat("fw", (0.92, 0.90, 0.85, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.82), emission_strength=0.4)
M_FERRY_DARK = mat("fd", (0.18, 0.42, 0.22, 1.0), 0.0, 0.65)

# Businessman clothing
M_SKIN = mat("sk", (0.85, 0.65, 0.45, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.45), emission_strength=0.3)
M_SUIT_BLACK = mat("sb", (0.08, 0.08, 0.10, 1.0), 0.2, 0.45)
M_SUIT_GRAY = mat("sg", (0.32, 0.32, 0.35, 1.0), 0.2, 0.50)
M_SUIT_NAVY = mat("sn_b", (0.10, 0.15, 0.32, 1.0), 0.2, 0.50)
SUIT_COLORS = [M_SUIT_BLACK, M_SUIT_GRAY, M_SUIT_NAVY]
M_SHIRT_WHITE = mat("shw", (0.92, 0.90, 0.85, 1.0), 0.0, 0.35, emission=(0.88,0.85,0.82), emission_strength=0.4)
M_TIE_RED = mat("tr", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45)
M_TIE_BLUE = mat("tb", (0.18, 0.32, 0.65, 1.0), 0.0, 0.45)
M_BRIEFCASE = mat("br", (0.32, 0.18, 0.10, 1.0), 0.2, 0.55)
M_HAIR_BLACK = mat("hb", (0.10, 0.08, 0.06, 1.0), 0.0, 0.85)

# Hong Kong flag (signature red with bauhinia)
M_FLAG_RED = mat("fr_hk", (0.85, 0.10, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.10,0.18), emission_strength=1.0)
M_FLAG_WHITE_HK = mat("fwhk", (0.95, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.90), emission_strength=1.5)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Chinese lantern (signature)
M_LANTERN_RED = mat("ltr", (1.0, 0.30, 0.18, 1.0), 0.0, 0.20, emission=(0.95,0.30,0.18), emission_strength=5.0)
M_LANTERN_GOLD = mat("ltg", (1.0, 0.78, 0.20, 1.0), 0.3, 0.20, emission=(0.95,0.75,0.20), emission_strength=5.5)
M_LANTERN_PINK = mat("ltpk", (1.0, 0.55, 0.75, 1.0), 0.0, 0.20, emission=(0.95,0.55,0.72), emission_strength=4.5)
LANTERN_COLORS = [M_LANTERN_RED, M_LANTERN_GOLD, M_LANTERN_PINK]

# Neon light particles (signature)
M_NEON_PT_RED = mat("nptr", (1.0, 0.30, 0.30, 1.0), 0.0, 0.05, emission=(0.95,0.30,0.30), emission_strength=8.0)
M_NEON_PT_CYAN = mat("nptc", (0.30, 1.0, 1.0, 1.0), 0.0, 0.05, emission=(0.30,0.95,0.95), emission_strength=8.0)
M_NEON_PT_PINK = mat("nptp", (1.0, 0.30, 0.85, 1.0), 0.0, 0.05, emission=(0.95,0.30,0.82), emission_strength=8.0)
M_NEON_PT_YELLOW = mat("npty", (1.0, 0.95, 0.45, 1.0), 0.0, 0.05, emission=(0.95,0.92,0.45), emission_strength=8.0)
M_NEON_PT_GREEN = mat("nptg", (0.45, 1.0, 0.45, 1.0), 0.0, 0.05, emission=(0.42,0.95,0.42), emission_strength=8.0)
NEON_PT_COLORS = [M_NEON_PT_RED, M_NEON_PT_CYAN, M_NEON_PT_PINK, M_NEON_PT_YELLOW, M_NEON_PT_GREEN]

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Moon
smooth_sphere("moon", r=6, segs=24, rings=18, loc=(80, 100, 60), mat_=M_MOON)
# Stars
for si in range(150):
    sa = random.uniform(0, math.pi*2); se = random.uniform(0.3, 0.9)
    sx_st = math.cos(sa) * 250 * math.cos(se)
    sy_st = math.sin(sa) * 250 * math.cos(se)
    sz_st = math.sin(se) * 200 + 50
    smooth_sphere(f"star{si}", r=random.uniform(0.4, 0.9), segs=8, rings=6,
                  loc=(sx_st, sy_st, sz_st), mat_=M_STAR)

# ============ ONE clean Victoria Harbour water ground ============
ground = beveled_cube("ground", (300, 300, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_HARBOUR)
# Reflective water ripples (signature)
for ri in range(120):
    a = random.uniform(0, math.pi*2); rad = random.uniform(5, 140)
    cyl(f"rp{ri}", r=random.uniform(1.0, 2.0), depth=0.04, segs=14,
        loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
        mat_=M_HARBOUR_REFLECT)
# Light reflection streaks
for li in range(40):
    lx = random.uniform(-100, 100); ly = random.uniform(-50, 50)
    beveled_cube(f"lr{li}", (random.uniform(2, 4), 0.3, 0.05), bevel_offset=0.02,
                 loc=(lx, ly, 0.18), mat_=random.choice([M_NEON_PT_RED, M_NEON_PT_CYAN, M_NEON_PT_YELLOW])).rotation_euler = (0, 0, random.uniform(0, math.pi))

# ============ 15 SKYSCRAPERS (signature Hong Kong skyline) ============
def make_skyscraper(name, loc, width, depth, height, style="modern"):
    base = empty(name, loc)
    if style == "bank_of_china":
        # Bank of China style (signature triangular geometric)
        # Tapered with triangular sections
        for li in range(int(height / 6)):
            lz = li * 6
            lh = 6
            lw = width * (1 - li / (height / 6) * 0.5)
            beveled_cube(f"{name}_l{li}", (lw, lw, lh), bevel_offset=0.15,
                         loc=(0, 0, lz + lh/2), parent=base, mat_=M_GLASS_BLUE)
        # 2 antenna spires (signature)
        cyl(f"{name}_an1", r=0.40, depth=15, segs=8, loc=(0, 0, height + 7.5),
            parent=base, mat_=M_STEEL)
        cyl(f"{name}_an2", r=0.20, depth=8, segs=8, loc=(0, 0, height + 19),
            parent=base, mat_=M_STEEL)
    elif style == "ifc":
        # IFC tower (signature tapered with crown)
        for li in range(int(height / 5)):
            lz = li * 5
            ww = width * (1 - li / (height / 5) * 0.35)
            beveled_cube(f"{name}_l{li}", (ww, ww * 0.85, 5), bevel_offset=0.15,
                         loc=(0, 0, lz + 2.5), parent=base, mat_=M_GLASS_WARM)
        # Crown signature (segmented top)
        for ci in range(8):
            beveled_cube(f"{name}_cr{ci}", (width * 0.4, width * 0.05, 1.5), bevel_offset=0.05,
                         loc=(0, 0, height + ci*0.4), parent=base, mat_=M_STEEL).rotation_euler = (0, 0, ci * math.radians(20))
    else:
        # Standard rectangular skyscraper
        beveled_cube(f"{name}_b", (width, depth, height), bevel_offset=0.15,
                     loc=(0, 0, height/2), parent=base, mat_=random.choice([M_GLASS_BLUE, M_GLASS_DARK, M_GLASS_GOLD]))
        # Antenna
        cyl(f"{name}_an", r=0.20, depth=8, segs=8, loc=(0, 0, height + 4),
            parent=base, mat_=M_STEEL)
    # WINDOW PATTERN (signature lit at night)
    n_floors = int(height / 2)
    n_cols = max(2, int(width / 1.5))
    for fi in range(n_floors):
        fz = 1 + fi * 2
        for ci in range(n_cols):
            cx = -width/2 + (ci + 0.5) * (width / n_cols)
            # Front
            beveled_cube(f"{name}_wf{fi}_{ci}", (0.5, 0.05, 0.6), bevel_offset=0.02,
                         loc=(cx, -depth/2 - 0.02, fz), parent=base,
                         mat_=random.choice(WIN_COLORS))
            # Side (left)
            cy_w = -depth/2 + (ci + 0.5) * (depth / n_cols)
            beveled_cube(f"{name}_wl{fi}_{ci}", (0.05, 0.5, 0.6), bevel_offset=0.02,
                         loc=(-width/2 - 0.02, cy_w, fz), parent=base,
                         mat_=random.choice(WIN_COLORS))
    # NEON SIGN at bottom (signature)
    if random.random() > 0.3:
        sign_e = empty(f"{name}_sg_e", (0, -depth/2 - 0.3, height * 0.15), parent=base)
        neon_col = random.choice(NEON_COLORS)
        # Vertical bars (Chinese characters look)
        for ti in range(4):
            beveled_cube(f"{name}_sg_t{ti}", (0.30, 0.15, 0.80), bevel_offset=0.04,
                         loc=(-1.5 + ti*1.0, 0, 0), parent=sign_e, mat_=neon_col)
    return base

# Skyline arrangement (signature Victoria Harbour view)
skyscraper_data = [
    (-50, 30, 6, 6, 50, "bank_of_china"),  # Bank of China
    (-35, 35, 8, 8, 70, "ifc"),  # IFC
    (-20, 30, 5, 5, 45, "modern"),
    (-10, 35, 6, 6, 55, "modern"),
    (0, 30, 5, 5, 40, "modern"),
    (10, 35, 7, 7, 60, "modern"),
    (22, 32, 6, 6, 48, "modern"),
    (35, 30, 8, 8, 65, "modern"),
    (50, 32, 6, 6, 50, "modern"),
    # Background row (smaller)
    (-45, 60, 4, 4, 35, "modern"),
    (-30, 60, 5, 5, 38, "modern"),
    (-15, 60, 6, 6, 42, "modern"),
    (0, 60, 5, 5, 36, "modern"),
    (15, 60, 4, 4, 30, "modern"),
    (30, 60, 5, 5, 33, "modern"),
]
for i, (sx, sy, sw, sd, sh, ss) in enumerate(skyscraper_data):
    make_skyscraper(f"sky{i}", (sx, sy, 0), sw, sd, sh, ss)

# ============ 4 RED JUNK BOATS in harbour (signature) ============
def make_junk(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Hull (signature curved)
    smooth_cone(f"{name}_h", r1=0.50, r2=0.20, depth=5, segs=14, loc=(0, 0, 0),
                parent=base, mat_=M_JUNK_RED).rotation_euler = (0, math.radians(90), 0)
    # Plank deck
    beveled_cube(f"{name}_pd", (4.5, 1.4, 0.20), bevel_offset=0.06, loc=(0, 0, 0.15),
                 parent=base, mat_=M_JUNK_DARK)
    # Upturned bow signature
    bow_e = empty(f"{name}_bw", (2.5, 0, 0.30), parent=base)
    bow_e.rotation_euler = (0, math.radians(-20), 0)
    beveled_cube(f"{name}_bp", (0.6, 1.4, 0.30), bevel_offset=0.05, loc=(0, 0, 0),
                 parent=bow_e, mat_=M_JUNK_RED)
    # Cabin
    beveled_cube(f"{name}_ca", (2, 1.2, 0.85), bevel_offset=0.08, loc=(-0.5, 0, 0.65),
                 parent=base, mat_=M_JUNK_DARK)
    # Red fan sails (signature 3 masts)
    for mi, mx in enumerate([-1.5, 0.5, 1.8]):
        mast_e = empty(f"{name}_m{mi}", (mx, 0, 0.30), parent=base)
        cyl(f"{name}_mp{mi}", r=0.06, depth=4, segs=8, loc=(0, 0, 2),
            parent=mast_e, mat_=M_JUNK_DARK)
        # Fan sail
        sail_e = empty(f"{name}_s{mi}", (0, 0, 2.2), parent=mast_e)
        for bi in range(5):
            bz_s = -1 + bi * 0.7
            bw = 1.5 + bi * 0.20
            beveled_cube(f"{name}_sf{mi}_{bi}", (0.04, bw, 0.55), bevel_offset=0.02,
                         loc=(0.08, 0, bz_s), parent=sail_e, mat_=M_SAIL_RED)
    # Lanterns hanging (signature)
    for li in range(4):
        lx = -1.5 + li * 1.0
        smooth_sphere(f"{name}_lt{li}", r=0.15, segs=12, rings=8, loc=(lx, 0.65, 1.5),
                      parent=base, mat_=M_LANTERN_RED)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

junks = []
junk_pos = [(-30, -20, math.radians(20)), (-10, -25, math.radians(-15)),
             (15, -22, math.radians(10)), (35, -25, math.radians(-25))]
for i, (jx, jy, fac) in enumerate(junk_pos):
    j = make_junk(f"jk{i}", (jx, jy, 0.5), facing=fac)
    junks.append(j)

# ============ STAR FERRY (signature green ferry) ============
ferry_e = empty("ferry", (0, -10, 0.6))
ferry_e.rotation_euler = (0, 0, math.radians(10))
# Hull
smooth_cone("sf_h", r1=0.85, r2=0.35, depth=10, segs=14, loc=(0, 0, 0),
            parent=ferry_e, mat_=M_FERRY_GREEN).rotation_euler = (0, math.radians(90), 0)
# Deck
beveled_cube("sf_d", (9, 2.5, 0.30), bevel_offset=0.08, loc=(0, 0, 0.20),
             parent=ferry_e, mat_=M_FERRY_WHITE)
# Upper cabin with windows
beveled_cube("sf_uc", (7, 2.2, 1.5), bevel_offset=0.10, loc=(0, 0, 1.20),
             parent=ferry_e, mat_=M_FERRY_GREEN)
# Cabin windows (signature glow)
for wi in range(10):
    beveled_cube(f"sf_w{wi}", (0.50, 2.25, 0.6), bevel_offset=0.04,
                 loc=(-3 + wi*0.7, 0, 1.30), parent=ferry_e, mat_=M_WIN_WARM)
# Upper deck
beveled_cube("sf_ud", (6, 2, 0.30), bevel_offset=0.06, loc=(0, 0, 2.10),
             parent=ferry_e, mat_=M_FERRY_WHITE)
# Funnel/smokestack (signature)
cyl("sf_fn", r=0.30, depth=2, segs=14, loc=(-1, 0, 3.0),
    parent=ferry_e, mat_=M_FERRY_DARK)
# Wheelhouse
beveled_cube("sf_wh", (1.5, 1.5, 1), bevel_offset=0.10, loc=(2.5, 0, 2.8),
             parent=ferry_e, mat_=M_FERRY_GREEN)
# Wheelhouse window
beveled_cube("sf_whw", (1.4, 0.05, 0.7), bevel_offset=0.04, loc=(2.5, -0.76, 2.9),
             parent=ferry_e, mat_=M_WIN_BLUE)
# Star Ferry name plate (signature)
beveled_cube("sf_np", (4, 0.06, 0.4), bevel_offset=0.04, loc=(0, -1.30, 1.50),
             parent=ferry_e, mat_=M_FERRY_WHITE)
# White stars on plate
for si_p in range(3):
    smooth_sphere(f"sf_st{si_p}", r=0.10, loc=(-1 + si_p*1.0, -1.34, 1.50),
                  parent=ferry_e, mat_=M_FERRY_GREEN)
# Life rings
for lr in range(4):
    cyl(f"sf_lr{lr}", r=0.18, depth=0.06, segs=12, loc=(-3 + lr*2, -1.30, 0.50),
        parent=ferry_e, mat_=M_FLAG_WHITE_HK).rotation_euler = (math.radians(90), 0, 0)
ferry_e["_phase"] = 0

# ============ 4 BUSINESSMEN (signature suits + briefcases) ============
def make_businessman(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    suit_col = random.choice(SUIT_COLORS)
    # Suit jacket
    smooth_cone(f"{name}_j", r1=0.32, r2=0.34, depth=0.85, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=suit_col)
    # White shirt collar
    beveled_cube(f"{name}_sh_c", (0.18, 0.06, 0.50), bevel_offset=0.02,
                 loc=(0, -0.30, 1.50), parent=base, mat_=M_SHIRT_WHITE)
    # Tie
    tie_col = random.choice([M_TIE_RED, M_TIE_BLUE])
    beveled_cube(f"{name}_ti", (0.06, 0.03, 0.40), bevel_offset=0.005,
                 loc=(0, -0.32, 1.40), parent=base, mat_=tie_col)
    beveled_cube(f"{name}_tk", (0.08, 0.04, 0.06), bevel_offset=0.01,
                 loc=(0, -0.32, 1.62), parent=base, mat_=tie_col)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.11, depth=0.95, segs=10,
            loc=(side*0.13, 0, 0.50), parent=base, mat_=suit_col)
    # Dress shoes
    for side in (-1, 1):
        beveled_cube(f"{name}_b{side}", (0.13, 0.28, 0.06), bevel_offset=0.02,
                     loc=(side*0.13, 0, 0.03), parent=base, mat_=M_SUIT_BLACK)
    # Arms
    sh_l = empty(f"{name}_a0", (-0.32, 0, 1.60), parent=base)
    sh_l.rotation_euler = (math.radians(-80), 0, math.radians(15))
    cyl(f"{name}_ua0", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=suit_col)
    cyl(f"{name}_fa0", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_SHIRT_WHITE)
    # BRIEFCASE in left hand (signature)
    beveled_cube(f"{name}_bc", (0.30, 0.15, 0.25), bevel_offset=0.04,
                 loc=(0, 0, -0.85), parent=sh_l, mat_=M_BRIEFCASE)
    # Briefcase handle
    cyl(f"{name}_bch", r=0.02, depth=0.10, segs=8,
        loc=(0, 0, -0.70), parent=sh_l, mat_=M_BRIEFCASE)
    # Right arm
    sh_r = empty(f"{name}_a1", (0.32, 0, 1.60), parent=base)
    sh_r.rotation_euler = (math.radians(-70), 0, math.radians(-15))
    cyl(f"{name}_ua1", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=suit_col)
    cyl(f"{name}_fa1", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_SHIRT_WHITE)
    # Head
    head_b_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_b_e, mat_=M_SKIN)
    # Hair short
    for hi in range(10):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.06, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.12),
            parent=head_b_e, mat_=M_HAIR_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_b_e, mat_=M_EYE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_b_e}

businessmen = []
business_pos = [(-15, -45, math.radians(15)), (-5, -48, math.radians(0)),
                 (5, -48, math.radians(0)), (15, -45, math.radians(-15))]
for i, (bx, by, fac) in enumerate(business_pos):
    b = make_businessman(f"bm{i}", (bx, by, 0), facing=fac)
    businessmen.append(b)

# ============ HONG KONG FLAG (signature red with bauhinia) ============
flag_e = empty("flag", (-60, -55, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_STEEL_DARK)
# Red field
beveled_cube("fl_r", (4, 0.05, 2.5), bevel_offset=0.06, loc=(2, 0, 10.5),
             parent=flag_e, mat_=M_FLAG_RED)
# BAUHINIA flower (signature 5-petal white)
bauh_e = empty("fl_bh", (2, -0.06, 10.5), parent=flag_e)
# 5 petals
for pi in range(5):
    pia = (pi / 5.0) * math.pi * 2 + math.pi/2
    # Petal
    petal_e = empty(f"fl_bh_p{pi}_e", (0, 0, 0), parent=bauh_e)
    petal_e.rotation_euler = (0, pia, 0)
    beveled_cube(f"fl_bh_p{pi}", (0.04, 0.10, 0.30), bevel_offset=0.02,
                 loc=(0.30, 0, 0), parent=petal_e, mat_=M_FLAG_WHITE_HK)
# Center
smooth_sphere("fl_bh_c", r=0.08, loc=(0, 0, 0), parent=bauh_e, mat_=M_FLAG_RED)
# Stars on each petal
for pi in range(5):
    pia = (pi / 5.0) * math.pi * 2 + math.pi/2
    star_e = empty(f"fl_bh_s{pi}", (math.cos(pia)*0.32, -0.07, math.sin(pia)*0.32), parent=flag_e)
    smooth_sphere(f"fl_bh_sc{pi}", r=0.04, loc=(0, 0, 0), parent=star_e, mat_=M_FLAG_RED)
flag_e["_phase"] = 0

# ============================================================
# ⭐ 1000 NEON LIGHTS + 500 CHINESE LANTERNS (DOUBLE MILESTONE PARTICLES)
# ============================================================
neons = []
for i in range(1000):
    # Concentrate around skyscrapers
    region = i % 4
    if region < 3:
        px = random.uniform(-60, 60)
        py = random.uniform(20, 80)
        pz = random.uniform(5, 70)
    else:
        # Scattered
        px = random.uniform(-130, 130)
        py = random.uniform(-130, 130)
        pz = random.uniform(2, 60)
    n_col = random.choice(NEON_PT_COLORS)
    # Neon bar shape
    n = beveled_cube(f"ne{i}", (random.uniform(0.05, 0.10), random.uniform(0.10, 0.20), random.uniform(0.04, 0.10)),
                    bevel_offset=0.01, loc=(px, py, pz), mat_=n_col)
    n["_phase"] = random.uniform(0, math.pi*2)
    n["_base_x"] = px; n["_base_y"] = py; n["_base_z"] = pz
    n["_blink"] = random.uniform(3, 8)
    n["_amp_x"] = random.uniform(0.3, 0.8)
    n["_amp_y"] = random.uniform(0.3, 0.8)
    n["_amp_z"] = random.uniform(0.2, 0.6)
    n["_speed"] = random.uniform(0.4, 1.0)
    neons.append(n)

# 500 chinese lanterns floating
lanterns = []
for i in range(500):
    px = random.uniform(-130, 130)
    py = random.uniform(-100, 100)
    pz = random.uniform(8, 55)
    l_col = random.choice(LANTERN_COLORS)
    l_e = empty(f"lt{i}", (px, py, pz))
    # Lantern body (signature oval)
    smooth_sphere(f"lt{i}_b", r=0.25, segs=14, rings=10, loc=(0, 0, 0),
                  parent=l_e, mat_=l_col, scale=(1, 1, 1.2))
    # Top cap
    cyl(f"lt{i}_t", r=0.10, depth=0.08, segs=10, loc=(0, 0, 0.30),
        parent=l_e, mat_=M_LANTERN_GOLD)
    # Bottom cap
    cyl(f"lt{i}_bc", r=0.10, depth=0.08, segs=10, loc=(0, 0, -0.30),
        parent=l_e, mat_=M_LANTERN_GOLD)
    # Tassel (signature)
    cyl(f"lt{i}_ts", r=0.012, depth=0.20, segs=6, loc=(0, 0, -0.45),
        parent=l_e, mat_=M_LANTERN_GOLD)
    # Tassel fringes
    for fri in range(5):
        fra = (fri / 5.0) * math.pi * 2
        cyl(f"lt{i}_fr{fri}", r=0.008, depth=0.15, segs=4,
            loc=(math.cos(fra)*0.03, math.sin(fra)*0.03, -0.55),
            parent=l_e, mat_=M_LANTERN_GOLD)
    # Hanging string
    cyl(f"lt{i}_st", r=0.005, depth=0.40, segs=4, loc=(0, 0, 0.55),
        parent=l_e, mat_=M_LANTERN_GOLD)
    l_e["_phase"] = random.uniform(0, math.pi*2)
    l_e["_base_x"] = px; l_e["_base_y"] = py; l_e["_base_z"] = pz
    l_e["_rise"] = random.uniform(0.8, 2.0)
    l_e["_sway"] = random.uniform(0.5, 1.5)
    lanterns.append(l_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Junks bob
for j in junks:
    phase = j["_phase"]
    bz_j = j.location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        j.location.z = bz_j + math.sin(t * 1.0 + phase) * 0.12
        j.rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(3),
                             math.cos(t * 1.0 + phase) * math.radians(2),
                             j.rotation_euler.z)
        j.keyframe_insert("location", frame=f)
        j.keyframe_insert("rotation_euler", frame=f)

# Star Ferry bob
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    ferry_e.location.z = 0.6 + math.sin(t * 0.8) * 0.10
    ferry_e.rotation_euler = (math.sin(t * 0.8) * math.radians(2), 0, math.radians(10))
    ferry_e.keyframe_insert("location", frame=f)
    ferry_e.keyframe_insert("rotation_euler", frame=f)

# Businessmen walk
for b in businessmen:
    phase = b["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        b["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(2), 0,
                                     b["root"].rotation_euler.z)
        b["root"].location.z = abs(math.sin(t * 2.5 + phase)) * 0.05
        b["root"].keyframe_insert("rotation_euler", frame=f)
        b["root"].keyframe_insert("location", frame=f)
        b["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3), 0, 0)
        b["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(10))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 1000 neon lights blink + drift
for n in neons:
    phase = n["_phase"]; blink = n["_blink"]; speed = n["_speed"]
    bx, by, bz_n = n["_base_x"], n["_base_y"], n["_base_z"]
    ax, ay, az = n["_amp_x"], n["_amp_y"], n["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz_n + az * math.sin(t * speed * 1.2 + phase)
        n.location = (x, y, z)
        # Blink scale
        sc = 0.4 + abs(math.sin(t * blink + phase)) * 1.4
        n.scale = (sc, sc, sc)
        n.keyframe_insert("location", frame=f)
        n.keyframe_insert("scale", frame=f)

# 500 chinese lanterns rise + sway
for l in lanterns:
    phase = l["_phase"]; rise = l["_rise"]; sway = l["_sway"]
    bx, by, bz_l = l["_base_x"], l["_base_y"], l["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * sway + phase) * 1.5
        y = by + math.cos(t * sway * 0.8 + phase) * 1.2
        z = bz_l + (t * rise) % 12
        l.location = (x, y, z)
        l.rotation_euler = (math.sin(t * sway + phase) * math.radians(10),
                             math.cos(t * sway * 0.7 + phase) * math.radians(8),
                             t * 0.3 + phase)
        l.keyframe_insert("location", frame=f)
        l.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_hongkong_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_hongkong_night_skyline_skyscrapers] DONE → {out_glb} ({size_mb:.2f} MB)")
print("⭐ 290e MILESTONE 155e qualité ⭐")
print("Hong Kong night skyline: Victoria Harbour reflective water + 15 skyscrapers (signature Bank of China geometric tapered with 2 antennas + IFC tapered with segmented crown + 13 standard towers with lit windows blue/warm/dark + neon signs Chinese characters style) + 4 red junks with signature 3-mast fan red sails + hanging lanterns + Star Ferry signature green with 10 lit windows + funnel + wheelhouse + star nameplate + 4 businessmen (signature suits + ties + briefcases + black hair) + Hong Kong flag with bauhinia 5-petal white + Night sky moon + 150 stars + 1000 NEON LIGHTS (5 colors) blinking + 500 CHINESE LANTERNS (red/gold/pink) rising signature DOUBLE MILESTONE")
print("⭐ DOUBLE PARTICLES MILESTONE: 1 harbour ground + 1000 neon lights + 500 chinese lanterns signature Hong Kong ⭐")
