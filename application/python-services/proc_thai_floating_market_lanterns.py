"""
proc_thai_floating_market_lanterns.py — 245e procédural AuroraIA (110e qualité)
Thai Loy Krathong floating market: pontoon + canal + 6 longtail boats + vendors + 8 stalls + Wat temple chedi + 4 monks + 600 krathongs + 400 sky lanterns
FIXES : 1 ground + 600 krathongs floating + 400 sky lanterns rising (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB245)

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

# Night palette
M_SKY = mat("sky", (0.05, 0.04, 0.12, 1.0), 0.0, 0.7, emission=(0.06,0.05,0.15), emission_strength=0.6)
M_STAR = mat("star", (1.0, 0.95, 0.70, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.70), emission_strength=10.0)
M_MOON = mat("moon", (0.95, 0.92, 0.78, 1.0), 0.0, 0.20, emission=(0.92,0.90,0.75), emission_strength=4.5)

# Water canal
M_WATER = mat("water", (0.12, 0.25, 0.35, 1.0), 0.1, 0.20, emission=(0.18,0.32,0.42), emission_strength=1.8, alpha=0.78)
M_WATER_DEEP_T = mat("water_d", (0.08, 0.18, 0.28, 1.0), 0.1, 0.25, alpha=0.88)
M_WATER_REFLECT = mat("water_r", (0.95, 0.78, 0.40, 1.0), 0.0, 0.10, emission=(0.92,0.75,0.40), emission_strength=3.0, alpha=0.55)

# Pontoon wood
M_PONTOON = mat("pontoon", (0.55, 0.35, 0.18, 1.0), 0.0, 0.75, emission=(0.50,0.32,0.18), emission_strength=0.4)
M_PONTOON_DARK = mat("pont_d", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)
M_BAMBOO = mat("bamboo", (0.62, 0.55, 0.20, 1.0), 0.0, 0.65, emission=(0.58,0.52,0.20), emission_strength=0.5)
M_BAMBOO_DARK = mat("bamboo_d", (0.40, 0.32, 0.10, 1.0), 0.0, 0.75)
M_THATCH = mat("thatch", (0.55, 0.40, 0.18, 1.0), 0.0, 0.85, emission=(0.50,0.38,0.18), emission_strength=0.3)

# Longtail boat (signature)
M_BOAT_WOOD = mat("bw", (0.55, 0.28, 0.12, 1.0), 0.0, 0.65, emission=(0.50,0.28,0.12), emission_strength=0.4)
M_BOAT_RED = mat("br", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.18), emission_strength=0.8)
M_BOAT_BLUE = mat("bb", (0.18, 0.42, 0.78, 1.0), 0.0, 0.55, emission=(0.18,0.42,0.75), emission_strength=0.8)
M_BOAT_GREEN_TH = mat("bg", (0.20, 0.55, 0.30, 1.0), 0.0, 0.55, emission=(0.20,0.55,0.30), emission_strength=0.8)
M_BOAT_YELLOW = mat("by", (0.95, 0.78, 0.20, 1.0), 0.0, 0.55, emission=(0.92,0.75,0.20), emission_strength=0.9)
M_BOAT_GOLD = mat("bg_gd", (1.0, 0.85, 0.30, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.30), emission_strength=1.5)
BOAT_COLORS = [M_BOAT_RED, M_BOAT_BLUE, M_BOAT_GREEN_TH, M_BOAT_YELLOW]

# Garlands ribbons signature
M_RIBBON_RED = mat("rb_r", (1.0, 0.20, 0.30, 1.0), 0.0, 0.45, emission=(1.0,0.20,0.30), emission_strength=2.0)
M_RIBBON_PINK = mat("rb_p", (1.0, 0.45, 0.65, 1.0), 0.0, 0.45, emission=(1.0,0.45,0.65), emission_strength=2.0)
M_RIBBON_GOLD = mat("rb_gd", (1.0, 0.85, 0.30, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.30), emission_strength=2.5)
M_RIBBON_GREEN = mat("rb_g", (0.30, 0.85, 0.40, 1.0), 0.0, 0.45, emission=(0.30,0.85,0.40), emission_strength=2.0)
RIBBON_COLORS = [M_RIBBON_RED, M_RIBBON_PINK, M_RIBBON_GOLD, M_RIBBON_GREEN]

# Skin
M_SKIN_THAI = mat("skin", (0.85, 0.65, 0.48, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.48), emission_strength=0.4)
M_HAIR_THAI = mat("hair", (0.10, 0.06, 0.04, 1.0), 0.0, 0.55)

# Thai outfits
M_DRESS_RED = mat("dr_r", (0.85, 0.15, 0.20, 1.0), 0.0, 0.55, emission=(0.80,0.15,0.20), emission_strength=0.8)
M_DRESS_GREEN = mat("dr_g", (0.18, 0.55, 0.32, 1.0), 0.0, 0.55, emission=(0.18,0.55,0.32), emission_strength=0.8)
M_DRESS_PURPLE = mat("dr_p", (0.55, 0.20, 0.78, 1.0), 0.0, 0.55, emission=(0.55,0.20,0.75), emission_strength=0.8)
M_DRESS_PINK = mat("dr_pk", (0.95, 0.30, 0.65, 1.0), 0.0, 0.55, emission=(0.92,0.30,0.62), emission_strength=0.8)
DRESS_COLORS = [M_DRESS_RED, M_DRESS_GREEN, M_DRESS_PURPLE, M_DRESS_PINK]

# Conical hat signature
M_HAT_STRAW = mat("hat_s", (0.78, 0.62, 0.32, 1.0), 0.0, 0.75, emission=(0.72,0.58,0.32), emission_strength=0.4)
M_HAT_BAND = mat("hat_b", (0.85, 0.20, 0.30, 1.0), 0.0, 0.55)

# Fruits
M_BANANA = mat("ban", (1.0, 0.85, 0.20, 1.0), 0.0, 0.55, emission=(0.92,0.78,0.20), emission_strength=0.8)
M_BANANA_SPOT = mat("ban_s", (0.55, 0.35, 0.10, 1.0), 0.0, 0.55)
M_MANGO = mat("mango", (0.95, 0.55, 0.18, 1.0), 0.0, 0.55, emission=(0.92,0.52,0.18), emission_strength=0.7)
M_DURIAN = mat("durian", (0.55, 0.45, 0.18, 1.0), 0.0, 0.75, emission=(0.50,0.42,0.18), emission_strength=0.5)
M_WATERMELON = mat("wm", (0.18, 0.55, 0.20, 1.0), 0.0, 0.55, emission=(0.18,0.55,0.20), emission_strength=0.6)
M_DRAGONFRUIT = mat("dragonfr", (0.95, 0.25, 0.55, 1.0), 0.0, 0.55, emission=(0.92,0.25,0.52), emission_strength=0.8)
M_COCONUT = mat("coco", (0.32, 0.20, 0.08, 1.0), 0.0, 0.85)
M_LIME = mat("lime", (0.55, 0.85, 0.20, 1.0), 0.0, 0.55, emission=(0.50,0.80,0.20), emission_strength=0.7)
M_PINEAPPLE = mat("pine", (0.95, 0.78, 0.25, 1.0), 0.0, 0.55, emission=(0.90,0.75,0.25), emission_strength=0.7)

# Spices (colored piles)
M_SPICE_RED = mat("sp_r", (0.85, 0.20, 0.15, 1.0), 0.0, 0.55, emission=(0.80,0.20,0.15), emission_strength=0.7)
M_SPICE_ORANGE = mat("sp_o", (1.0, 0.50, 0.15, 1.0), 0.0, 0.55, emission=(0.95,0.50,0.15), emission_strength=0.7)
M_SPICE_YELLOW = mat("sp_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.55, emission=(0.95,0.80,0.20), emission_strength=0.7)
M_SPICE_GREEN = mat("sp_g", (0.40, 0.65, 0.20, 1.0), 0.0, 0.65)
M_SPICE_BROWN = mat("sp_br", (0.42, 0.28, 0.15, 1.0), 0.0, 0.65)

# Wat temple
M_TEMPLE_GOLD = mat("temple_g", (1.0, 0.85, 0.25, 1.0), 0.9, 0.20, emission=(0.95,0.80,0.25), emission_strength=2.0)
M_TEMPLE_RED = mat("temple_r", (0.78, 0.18, 0.12, 1.0), 0.0, 0.45, emission=(0.72,0.18,0.12), emission_strength=0.9)
M_TEMPLE_WHITE = mat("temple_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.92,0.90,0.85), emission_strength=0.7)
M_TEMPLE_GREEN = mat("temple_gr", (0.18, 0.45, 0.25, 1.0), 0.0, 0.55)

# Monks (signature saffron orange)
M_MONK_ROBE = mat("monk", (1.0, 0.45, 0.10, 1.0), 0.0, 0.60, emission=(0.95,0.45,0.10), emission_strength=1.2)
M_MONK_DARK = mat("monk_d", (0.85, 0.40, 0.10, 1.0), 0.0, 0.65, emission=(0.80,0.40,0.10), emission_strength=0.8)

# Krathong (signature lotus flower boats)
M_KRATHONG_BASE = mat("kr_b", (0.40, 0.65, 0.22, 1.0), 0.0, 0.70, emission=(0.38,0.62,0.22), emission_strength=1.2)
M_KRATHONG_PETAL_PINK = mat("kr_pp", (1.0, 0.45, 0.65, 1.0), 0.0, 0.45, emission=(1.0,0.45,0.65), emission_strength=2.5)
M_KRATHONG_PETAL_WHITE = mat("kr_pw", (0.98, 0.95, 0.88, 1.0), 0.0, 0.45, emission=(0.95,0.92,0.85), emission_strength=2.0)
M_KRATHONG_CANDLE = mat("kr_c", (1.0, 0.85, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.85,0.30), emission_strength=12.0)
M_KRATHONG_FLAME = mat("kr_fl", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=15.0)
M_KRATHONG_INCENSE = mat("kr_in", (0.75, 0.45, 0.20, 1.0), 0.0, 0.70)
KRATHONG_PETAL_VARIANTS = [M_KRATHONG_PETAL_PINK, M_KRATHONG_PETAL_WHITE]

# Sky lantern (signature)
M_LANTERN_PAPER = mat("lan_p", (1.0, 0.85, 0.45, 1.0), 0.0, 0.30, emission=(1.0,0.85,0.45), emission_strength=8.0, alpha=0.85)
M_LANTERN_RED = mat("lan_r", (1.0, 0.45, 0.30, 1.0), 0.0, 0.30, emission=(1.0,0.45,0.30), emission_strength=7.0, alpha=0.85)
M_LANTERN_GOLD = mat("lan_g", (1.0, 0.78, 0.25, 1.0), 0.0, 0.30, emission=(1.0,0.78,0.25), emission_strength=8.0, alpha=0.85)
M_LANTERN_FRAME = mat("lan_f", (0.30, 0.20, 0.10, 1.0), 0.0, 0.70)
M_LANTERN_FLAME = mat("lan_fl", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=10.0)
LANTERN_PAPERS = [M_LANTERN_PAPER, M_LANTERN_RED, M_LANTERN_GOLD]

# Eye
M_EYE_DARK_T = mat("eye_d", (0.04, 0.03, 0.03, 1.0), 0.0, 0.20)
M_LIPS_TH = mat("lips", (0.85, 0.30, 0.30, 1.0), 0.0, 0.40)

# ============ SKY ============
sky = smooth_sphere("sky", r=250, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Moon
moon = smooth_sphere("moon", r=3.5, segs=24, rings=18, loc=(-40, 80, 50), mat_=M_MOON)
# Stars
for si in range(120):
    sa = random.uniform(0, math.pi*2); sr = random.uniform(60, 180)
    sh = random.uniform(20, 70)
    smooth_sphere(f"star{si}", r=random.uniform(0.10, 0.25), segs=8, rings=6,
                  loc=(sr*math.cos(sa), sr*math.sin(sa), sh), mat_=M_STAR)

# ============ ONE clean wood pontoon ground (signature floating market) ============
ground = beveled_cube("ground", (160, 160, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_WATER)

# Wood pontoon platforms (signature elevated walkways)
def make_pontoon_plank(x, y, z, sx, sy):
    p_e = empty(f"pont_{x}_{y}", (x, y, z))
    # Main planks
    for pi in range(int(sy * 2)):
        py_p = -sy / 2 + pi * 0.5
        beveled_cube(f"pp{x}_{y}_{pi}", (sx, 0.45, 0.15), bevel_offset=0.02,
                     loc=(0, py_p, 0), parent=p_e, mat_=M_PONTOON if pi % 2 == 0 else M_PONTOON_DARK)
    # Support posts
    for sx_i in (-1, 1):
        for sy_i in (-1, 1):
            cyl(f"pp_post{x}_{y}_{sx_i}_{sy_i}", r=0.12, depth=1.2, segs=10,
                loc=(sx_i*(sx/2-0.5), sy_i*(sy/2-0.5), -0.6),
                parent=p_e, mat_=M_PONTOON_DARK)
    return p_e

# 3 main pontoons along banks (2 sides + middle)
pontoon_left = make_pontoon_plank(-15, 0, 0.3, 6, 30)
pontoon_right = make_pontoon_plank(15, 0, 0.3, 6, 30)
pontoon_back = make_pontoon_plank(0, 18, 0.3, 25, 5)

# Canal water (central)
canal = beveled_cube("canal", (24, 60, 0.20), bevel_offset=0.05, loc=(0, 0, 0.05), mat_=M_WATER)
# Water reflections (signature lights on water)
for ri in range(20):
    rx_r = random.uniform(-10, 10); ry_r = random.uniform(-25, 25)
    cyl(f"refl{ri}", r=random.uniform(0.30, 0.60), depth=0.04, segs=14,
        loc=(rx_r, ry_r, 0.18), mat_=M_WATER_REFLECT)

# ============ 6 LONGTAIL BOATS (signature) ============
def make_longtail_boat(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    boat_color = random.choice(BOAT_COLORS)
    # Long hull (signature thin elongated)
    hull = smooth_cone(f"{name}_hull", r1=0.50*scale, r2=0.10*scale, depth=5.0*scale, segs=14,
                       loc=(0, 0, 0), parent=base, mat_=M_BOAT_WOOD)
    hull.rotation_euler = (0, math.radians(90), 0)
    # Top deck
    beveled_cube(f"{name}_deck", (4.5*scale, 0.8*scale, 0.10*scale), bevel_offset=0.04,
                 loc=(0, 0, 0.30*scale), parent=base, mat_=M_BOAT_WOOD)
    # Painted color stripe (signature)
    beveled_cube(f"{name}_stripe1", (5.0*scale, 0.85*scale, 0.06*scale), bevel_offset=0.02,
                 loc=(0, 0, 0.20*scale), parent=base, mat_=boat_color)
    # Decorative gold trim
    beveled_cube(f"{name}_trim", (5.2*scale, 0.10*scale, 0.04*scale), bevel_offset=0.01,
                 loc=(0, 0, 0.10*scale), parent=base, mat_=M_BOAT_GOLD)
    # RIBBONS at bow (signature offering)
    bow_e = empty(f"{name}_bow", (2.4*scale, 0, 0.30*scale), parent=base)
    for ri in range(6):
        ribbon = beveled_cube(f"{name}_ri{ri}", (0.04*scale, 0.04*scale, 0.6*scale), bevel_offset=0.01,
                              loc=(0, (ri-2.5)*0.06*scale, 0.30*scale), parent=bow_e,
                              mat_=random.choice(RIBBON_COLORS))
    # Garland of flowers at front
    for gi in range(8):
        ga = (gi / 8.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_gar{gi}", r=0.06*scale,
                      loc=(2.30*scale, math.sin(ga)*0.35*scale, 0.5 + math.cos(ga)*0.20*scale),
                      parent=base, mat_=random.choice(RIBBON_COLORS))
    # LONG REAR PROP SHAFT (signature longtail)
    shaft_e = empty(f"{name}_shaft", (-2.3*scale, 0, 0.25*scale), parent=base)
    shaft_e.rotation_euler = (math.radians(-25), 0, 0)
    # Engine
    beveled_cube(f"{name}_eng", (0.40*scale, 0.30*scale, 0.30*scale), bevel_offset=0.04,
                 loc=(0, 0, 0.15*scale), parent=shaft_e, mat_=M_BOAT_WOOD)
    # Long shaft
    cyl(f"{name}_shaft_p", r=0.05*scale, depth=2.0*scale, segs=10, loc=(-1.0*scale, 0, -0.10*scale),
        parent=shaft_e, mat_=M_BAMBOO_DARK).rotation_euler = (0, math.radians(90), 0)
    # Prop at end
    for pi in range(4):
        pa = (pi / 4.0) * math.pi * 2
        beveled_cube(f"{name}_prop{pi}", (0.04*scale, 0.12*scale, 0.04*scale), bevel_offset=0.01,
                     loc=(-2.0*scale, math.cos(pa)*0.15*scale, -0.10*scale + math.sin(pa)*0.15*scale),
                     parent=shaft_e, mat_=M_PIPE_SILVER if False else M_BOAT_GOLD)

    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "shaft": shaft_e}

boats = []
boat_pos = [(0, -22, math.radians(0)), (0, -12, math.radians(15)),
            (0, -2, math.radians(-10)), (0, 8, math.radians(5)),
            (-6, -7, math.radians(75)), (6, -15, math.radians(-75))]
for i, (bx, by, fac) in enumerate(boat_pos):
    b = make_longtail_boat(f"boat{i}", (bx, by, 0.4), scale=1.0, facing=fac)
    boats.append(b)

# ============ VENDORS (Thai women) in boats with fruits ============
def make_vendor(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    dress_col = random.choice(DRESS_COLORS)
    # Sitting position - lower body
    smooth_sphere(f"{name}_lap", r=0.30*scale, segs=18, rings=12, loc=(0, 0, 0.30*scale),
                  parent=base, mat_=dress_col, scale=(1.3, 0.9, 0.7))
    # Torso
    smooth_cone(f"{name}_torso", r1=0.25*scale, r2=0.28*scale, depth=0.6*scale, segs=14,
                loc=(0, 0, 0.85*scale), parent=base, mat_=dress_col)
    # Sash
    cyl(f"{name}_sash", r=0.29*scale, depth=0.10*scale, segs=14, loc=(0, 0, 0.55*scale),
        parent=base, mat_=random.choice(RIBBON_COLORS))
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.28*scale, 0, 1.10*scale), parent=base)
        sh.rotation_euler = (math.radians(-45), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side_idx}", r=0.05*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.18*scale), parent=sh, mat_=dress_col)
        cyl(f"{name}_fa{side_idx}", r=0.045*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.50*scale), parent=sh, mat_=M_SKIN_THAI)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.40*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.15*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_THAI)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.02*scale,
                      loc=(side*0.05*scale, -0.13*scale, 0.02*scale), parent=head_e, mat_=M_EYE_DARK_T)
    # Smile
    beveled_cube(f"{name}_smile", (0.07*scale, 0.03*scale, 0.02*scale), bevel_offset=0.005,
                 loc=(0, -0.13*scale, -0.05*scale), parent=head_e, mat_=M_LIPS_TH)
    # Long black hair tied back
    smooth_sphere(f"{name}_hair", r=0.16*scale, loc=(0, 0.05*scale, 0.02*scale),
                  parent=head_e, mat_=M_HAIR_THAI, scale=(1, 1.1, 1.0))
    # CONICAL HAT (signature)
    hat_e = empty(f"{name}_hat", (0, 0, 0.20*scale), parent=head_e)
    smooth_cone(f"{name}_hat_c", r1=0.30*scale, r2=0.02*scale, depth=0.30*scale, segs=20,
                loc=(0, 0, 0.15*scale), parent=hat_e, mat_=M_HAT_STRAW)
    # Hat brim
    cyl(f"{name}_hat_b", r=0.32*scale, depth=0.02*scale, segs=20, loc=(0, 0, 0),
        parent=hat_e, mat_=M_HAT_STRAW)
    # Chin strap
    cyl(f"{name}_strap", r=0.005*scale, depth=0.25*scale, segs=6, loc=(0.10*scale, -0.10*scale, -0.10*scale),
        parent=hat_e, mat_=M_HAT_BAND).rotation_euler = (math.radians(60), 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "hat": hat_e}

# Place vendor in each boat
vendors = []
for bi, b in enumerate(boats):
    vendor_loc_x = b["root"].location.x + math.cos(b["root"].rotation_euler.z) * 0.5
    vendor_loc_y = b["root"].location.y + math.sin(b["root"].rotation_euler.z) * 0.5
    v = make_vendor(f"vendor{bi}", (vendor_loc_x, vendor_loc_y, 0.6),
                    scale=0.7, facing=b["root"].rotation_euler.z)
    vendors.append(v)

# FRUITS in boats (piles signature)
for bi, b in enumerate(boats):
    boat_x = b["root"].location.x; boat_y = b["root"].location.y
    boat_rot = b["root"].rotation_euler.z
    for fi in range(6):
        # Position along boat axis
        fx_off = math.cos(boat_rot) * (fi - 2.5) * 0.5
        fy_off = math.sin(boat_rot) * (fi - 2.5) * 0.5
        fruit_type = fi % 8
        fx_p = boat_x + fx_off
        fy_p = boat_y + fy_off
        fz_p = 0.65
        if fruit_type == 0:
            # Banana bundle
            for ba in range(3):
                ba_a = (ba / 3.0) * math.pi * 2
                cyl(f"ban_b{bi}_{fi}_{ba}", r=0.04, depth=0.20, segs=8,
                    loc=(fx_p + math.cos(ba_a)*0.05, fy_p + math.sin(ba_a)*0.05, fz_p),
                    mat_=M_BANANA).rotation_euler = (math.radians(30), 0, ba_a)
        elif fruit_type == 1:
            # Mango
            smooth_sphere(f"mango_{bi}_{fi}", r=0.10, segs=14, rings=10,
                          loc=(fx_p, fy_p, fz_p), mat_=M_MANGO, scale=(1, 1.3, 1))
        elif fruit_type == 2:
            # Durian spiky
            durian_e = empty(f"dur_e_{bi}_{fi}", (fx_p, fy_p, fz_p))
            smooth_sphere(f"dur_b_{bi}_{fi}", r=0.18, segs=18, rings=12, loc=(0, 0, 0),
                          parent=durian_e, mat_=M_DURIAN)
            # Spikes signature
            for sp in range(20):
                spa = random.uniform(0, math.pi*2); spe = random.uniform(0, math.pi)
                spx = math.sin(spe)*math.cos(spa)*0.20
                spy = math.sin(spe)*math.sin(spa)*0.20
                spz = math.cos(spe)*0.20
                smooth_cone(f"dur_sp{bi}_{fi}_{sp}", r1=0.03, r2=0.005, depth=0.08, segs=6,
                            loc=(spx, spy, spz), parent=durian_e, mat_=M_DURIAN)
        elif fruit_type == 3:
            # Watermelon
            smooth_sphere(f"wm_{bi}_{fi}", r=0.18, segs=18, rings=12,
                          loc=(fx_p, fy_p, fz_p), mat_=M_WATERMELON, scale=(1.3, 1.1, 1))
        elif fruit_type == 4:
            # Dragonfruit
            smooth_sphere(f"df_{bi}_{fi}", r=0.10, segs=14, rings=10,
                          loc=(fx_p, fy_p, fz_p), mat_=M_DRAGONFRUIT)
            # Spikes pink
            for sp in range(8):
                spa = (sp / 8.0) * math.pi * 2
                smooth_cone(f"df_sp{bi}_{fi}_{sp}", r1=0.03, r2=0.005, depth=0.05, segs=6,
                            loc=(fx_p + math.cos(spa)*0.10, fy_p + math.sin(spa)*0.10, fz_p),
                            mat_=M_RIBBON_GREEN)
        elif fruit_type == 5:
            # Coconut
            smooth_sphere(f"coco_{bi}_{fi}", r=0.12, segs=16, rings=12,
                          loc=(fx_p, fy_p, fz_p), mat_=M_COCONUT)
        elif fruit_type == 6:
            # Lime cluster
            for li2 in range(3):
                la = (li2 / 3.0) * math.pi * 2
                smooth_sphere(f"lime{bi}_{fi}_{li2}", r=0.06,
                              loc=(fx_p + math.cos(la)*0.05, fy_p + math.sin(la)*0.05, fz_p),
                              mat_=M_LIME)
        else:
            # Pineapple
            pine_e = empty(f"pine_e{bi}_{fi}", (fx_p, fy_p, fz_p))
            smooth_sphere(f"pine_b{bi}_{fi}", r=0.10, loc=(0, 0, 0),
                          parent=pine_e, mat_=M_PINEAPPLE, scale=(1, 1, 1.4))
            # Crown leaves
            for pl in range(6):
                pla = (pl / 6.0) * math.pi * 2
                smooth_cone(f"pine_l{bi}_{fi}_{pl}", r1=0.02, r2=0.005, depth=0.12, segs=6,
                            loc=(math.cos(pla)*0.05, math.sin(pla)*0.05, 0.15),
                            parent=pine_e, mat_=M_LIME).rotation_euler = (math.radians(-20), 0, pla)

# ============ 8 STALLS bamboo + thatch (signature market) ============
def make_stall(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # 4 bamboo posts
    for x_p in (-1, 1):
        for y_p in (-1, 1):
            cyl(f"{name}_post_{x_p}_{y_p}", r=0.10, depth=2.5, segs=10,
                loc=(x_p*1.0*scale, y_p*1.0*scale, 1.55), parent=base, mat_=M_BAMBOO)
    # Roof (thatch signature)
    for ri in range(6):
        rw = 2.5 - ri * 0.10
        rd = 2.5 - ri * 0.10
        beveled_cube(f"{name}_r{ri}", (rw, rd, 0.10), bevel_offset=0.02,
                     loc=(0, 0, 2.7 + ri*0.20), parent=base, mat_=M_THATCH)
    # Roof peak
    smooth_cone(f"{name}_peak", r1=0.3, r2=0.01, depth=0.6, segs=12,
                loc=(0, 0, 4.0), parent=base, mat_=M_THATCH)
    # Counter/table
    beveled_cube(f"{name}_counter", (1.6*scale, 1.0*scale, 0.10), bevel_offset=0.03,
                 loc=(0, 0.5*scale, 1.0), parent=base, mat_=M_PONTOON)
    # Spice piles or fruits on counter (random)
    spice_choices = [M_SPICE_RED, M_SPICE_ORANGE, M_SPICE_YELLOW, M_SPICE_GREEN, M_SPICE_BROWN]
    for si in range(4):
        sx_p = -0.6 + si * 0.4
        sy_p = 0.5
        for h_pile in range(2):
            smooth_sphere(f"{name}_sp{si}_{h_pile}", r=0.12 - h_pile*0.04,
                          loc=(sx_p, sy_p, 1.10 + h_pile*0.08),
                          parent=base, mat_=spice_choices[si % len(spice_choices)],
                          scale=(1, 1, 0.7))
    # Hanging lanterns at corners
    for x_p in (-1, 1):
        for y_p in (-1, 1):
            lan_y = y_p*1.0*scale
            lan_x = x_p*1.0*scale
            # Lantern
            smooth_sphere(f"{name}_lan_{x_p}_{y_p}", r=0.18, segs=16, rings=12,
                          loc=(lan_x, lan_y, 2.5),
                          parent=base, mat_=M_LANTERN_RED, scale=(1, 1, 0.85))
            # Cord
            cyl(f"{name}_cord_{x_p}_{y_p}", r=0.01, depth=0.20, segs=6,
                loc=(lan_x, lan_y, 2.7), parent=base, mat_=M_LANTERN_FRAME)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

stalls = []
stall_pos = [(-18, -20, math.radians(0)), (-18, -8, math.radians(0)),
              (-18, 4, math.radians(0)), (-18, 16, math.radians(0)),
              (18, -20, math.radians(180)), (18, -8, math.radians(180)),
              (18, 4, math.radians(180)), (18, 16, math.radians(180))]
for i, (sx, sy, fac) in enumerate(stall_pos):
    s = make_stall(f"stall{i}", (sx, sy, 0.4), scale=1.0, facing=fac)
    stalls.append(s)

# ============ WAT TEMPLE CHEDI (signature gold spire) ============
wat_e = empty("wat", loc=(0, 45, 0))
# Stepped base (signature)
for li in range(5):
    lz = li * 1.0
    lw = 12 - li * 1.5
    beveled_cube(f"wat_b{li}", (lw, lw, 1.0), bevel_offset=0.10, loc=(0, 0, lz + 0.5),
                 parent=wat_e, mat_=M_TEMPLE_WHITE)
# Main shrine (red walls)
beveled_cube("wat_shrine", (5, 5, 4), bevel_offset=0.10, loc=(0, 0, 7),
             parent=wat_e, mat_=M_TEMPLE_RED)
# Gold roof tier 1
for tr in range(3):
    rw = 6 - tr * 1.2
    beveled_cube(f"wat_r{tr}", (rw, rw, 0.4), bevel_offset=0.04,
                 loc=(0, 0, 9 + tr*0.50), parent=wat_e, mat_=M_TEMPLE_GOLD)
# Tall CHEDI gold spire signature
chedi_e = empty("chedi", (0, 0, 11.5), parent=wat_e)
# Bell shape base
smooth_sphere("chedi_bell", r=2.5, segs=22, rings=16, loc=(0, 0, 0),
              parent=chedi_e, mat_=M_TEMPLE_GOLD, scale=(1, 1, 1.2))
# Stacked rings going up (signature)
for ri in range(12):
    rz = 2.5 + ri * 0.6
    rr_c = 1.5 - ri * 0.1
    cyl(f"chedi_r{ri}", r=rr_c, depth=0.30, segs=18, loc=(0, 0, rz),
        parent=chedi_e, mat_=M_TEMPLE_GOLD)
    # Decorative ring band
    cyl(f"chedi_b{ri}", r=rr_c + 0.05, depth=0.06, segs=18, loc=(0, 0, rz),
        parent=chedi_e, mat_=M_TEMPLE_RED)
# Sharp pointed top
smooth_cone("chedi_top", r1=0.3, r2=0.01, depth=2.5, segs=14, loc=(0, 0, 10),
            parent=chedi_e, mat_=M_TEMPLE_GOLD)
# Pinnacle umbrella stages
for ui in range(4):
    cyl(f"chedi_um{ui}", r=0.20 - ui*0.04, depth=0.04, segs=12, loc=(0, 0, 8 + ui*0.3),
        parent=chedi_e, mat_=M_TEMPLE_GOLD)
# Decorative naga serpents at corners of base
for corner in range(4):
    ca = (corner / 4.0) * math.pi * 2 + math.pi/4
    cx_n = math.cos(ca) * 6; cy_n = math.sin(ca) * 6
    cyl(f"naga{corner}", r=0.15, depth=1.5, segs=10, loc=(cx_n, cy_n, 1.0),
        parent=wat_e, mat_=M_TEMPLE_GOLD).rotation_euler = (math.radians(60), 0, ca)
    # Naga head
    smooth_sphere(f"naga_h{corner}", r=0.25, loc=(cx_n + math.cos(ca)*0.5,
                                                    cy_n + math.sin(ca)*0.5, 2.0),
                  parent=wat_e, mat_=M_TEMPLE_GOLD)

# ============ 4 MONKS sitting (signature saffron robes) ============
def make_monk(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sitting lotus position
    # Lower body folded
    smooth_sphere(f"{name}_legs", r=0.45*scale, segs=18, rings=12, loc=(0, 0, 0.25*scale),
                  parent=base, mat_=M_MONK_ROBE, scale=(1.3, 1.3, 0.5))
    # Torso
    smooth_cone(f"{name}_torso", r1=0.30*scale, r2=0.32*scale, depth=0.5*scale, segs=14,
                loc=(0, 0, 0.7*scale), parent=base, mat_=M_MONK_ROBE)
    # Sash over shoulder (signature darker)
    sash_e = empty(f"{name}_sa", (0, 0, 0.85*scale), parent=base)
    sash_e.rotation_euler = (0, math.radians(20), math.radians(40))
    beveled_cube(f"{name}_sash", (0.5*scale, 0.06*scale, 0.40*scale), bevel_offset=0.03,
                 loc=(0, 0, 0), parent=sash_e, mat_=M_MONK_DARK)
    # Hands on lap (mudra)
    for side in (-1, 1):
        sh = empty(f"{name}_sh{side}", (side*0.28*scale, 0, 0.85*scale), parent=base)
        sh.rotation_euler = (math.radians(-90), 0, math.radians(side*-20))
        cyl(f"{name}_uarm{side}", r=0.05*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.15*scale), parent=sh, mat_=M_MONK_ROBE)
        cyl(f"{name}_fa{side}", r=0.045*scale, depth=0.25*scale, segs=10,
            loc=(0, 0, -0.42*scale), parent=sh, mat_=M_SKIN_THAI)
        smooth_sphere(f"{name}_hand{side}", r=0.05*scale, loc=(0, 0, -0.55*scale),
                      parent=sh, mat_=M_SKIN_THAI)
    # Head (shaved signature)
    head_e = empty(f"{name}_he", (0, 0, 1.15*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.15*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_THAI)
    # Eyes closed (peaceful)
    for side in (-1, 1):
        beveled_cube(f"{name}_eyec{side}", (0.04*scale, 0.02*scale, 0.01*scale), bevel_offset=0.003,
                     loc=(side*0.05*scale, -0.13*scale, 0.02*scale), parent=head_e, mat_=M_EYE_DARK_T)
    # Small smile peaceful
    beveled_cube(f"{name}_smile", (0.05*scale, 0.02*scale, 0.01*scale), bevel_offset=0.003,
                 loc=(0, -0.13*scale, -0.06*scale), parent=head_e, mat_=M_LIPS_TH)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

monks = []
monk_pos = [(-3, 35, math.radians(0)), (-1, 35, math.radians(0)),
            (1, 35, math.radians(0)), (3, 35, math.radians(0))]
for i, (mx, my, fac) in enumerate(monk_pos):
    m = make_monk(f"monk{i}", (mx, my, 0.5), scale=1.0, facing=fac)
    monks.append(m)

# ============ SUSPENDED LANTERNS between bamboo posts (signature decorations) ============
# Strings of lanterns over canal
for row in range(3):
    row_y = -20 + row * 12
    row_z = 6 + row * 1
    for col in range(12):
        cx_l = -10 + col * 1.8
        lan_e = empty(f"sus_lan{row}_{col}", (cx_l, row_y, row_z))
        # Lantern sphere shape
        col_lan = random.choice([M_LANTERN_RED, M_LANTERN_GOLD, M_LANTERN_PAPER])
        smooth_sphere(f"sl_b{row}_{col}", r=0.25, segs=16, rings=12, loc=(0, 0, 0),
                      parent=lan_e, mat_=col_lan, scale=(1, 1, 0.85))
        # Top + bottom caps
        cyl(f"sl_t{row}_{col}", r=0.10, depth=0.04, segs=12, loc=(0, 0, 0.22),
            parent=lan_e, mat_=M_LANTERN_FRAME)
        cyl(f"sl_b2{row}_{col}", r=0.10, depth=0.04, segs=12, loc=(0, 0, -0.22),
            parent=lan_e, mat_=M_LANTERN_FRAME)
        # Tassel
        cyl(f"sl_ts{row}_{col}", r=0.015, depth=0.10, segs=6, loc=(0, 0, -0.30),
            parent=lan_e, mat_=M_LANTERN_RED)
        lan_e["_phase"] = random.uniform(0, math.pi*2)

# Strings between rows
for row in range(3):
    row_y = -20 + row * 12
    row_z = 6.25 + row * 1
    cyl(f"str_lan{row}", r=0.01, depth=24, segs=8, loc=(0, row_y, row_z),
        mat_=M_LANTERN_FRAME).rotation_euler = (0, math.radians(90), 0)

# ============================================================
# ⭐ 600 KRATHONGS + 400 SKY LANTERNS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 floating krathongs (small lotus flower boats with candles signature)
krathongs = []
for i in range(600):
    px = random.uniform(-12, 12)
    py = random.uniform(-28, 28)
    pz = 0.30
    kr_e = empty(f"kr{i}", (px, py, pz))
    # Banana leaf base
    cyl(f"kr_base{i}", r=0.15, depth=0.06, segs=12, loc=(0, 0, 0),
        parent=kr_e, mat_=M_KRATHONG_BASE)
    # Lotus petals around (signature)
    for pi in range(8):
        pa = (pi / 8.0) * math.pi * 2
        petal_col = random.choice(KRATHONG_PETAL_VARIANTS)
        smooth_sphere(f"kr_p{i}_{pi}", r=0.06,
                      loc=(math.cos(pa)*0.10, math.sin(pa)*0.10, 0.04),
                      parent=kr_e, mat_=petal_col, scale=(1, 1.5, 0.4))
    # Center candle flame
    cyl(f"kr_cd{i}", r=0.02, depth=0.10, segs=8, loc=(0, 0, 0.09),
        parent=kr_e, mat_=M_KRATHONG_CANDLE)
    # Flame
    smooth_cone(f"kr_fl{i}", r1=0.025, r2=0.005, depth=0.06, segs=8, loc=(0, 0, 0.17),
                parent=kr_e, mat_=M_KRATHONG_FLAME)
    # Incense sticks
    for ic in range(2):
        cyl(f"kr_ic{i}_{ic}", r=0.005, depth=0.15, segs=6,
            loc=((ic-0.5)*0.04, 0.03, 0.08), parent=kr_e, mat_=M_KRATHONG_INCENSE)
    kr_e["_phase"] = random.uniform(0, math.pi*2)
    kr_e["_base_x"] = px; kr_e["_base_y"] = py
    kr_e["_amp_x"] = random.uniform(0.2, 0.6)
    kr_e["_amp_y"] = random.uniform(0.2, 0.6)
    kr_e["_amp_z"] = random.uniform(0.05, 0.15)
    kr_e["_speed"] = random.uniform(0.2, 0.5)
    krathongs.append(kr_e)

# 400 sky lanterns rising (signature)
sky_lanterns = []
for i in range(400):
    px = random.uniform(-50, 50)
    py = random.uniform(-50, 50)
    pz = random.uniform(2, 30)
    lan_e = empty(f"sl{i}", (px, py, pz))
    # Paper balloon (signature elongated)
    col_lan = random.choice(LANTERN_PAPERS)
    smooth_sphere(f"sl_pb{i}", r=0.30, segs=16, rings=12, loc=(0, 0, 0.20),
                  parent=lan_e, mat_=col_lan, scale=(1, 1, 1.5))
    # Bamboo frame ring
    cyl(f"sl_fr{i}", r=0.30, depth=0.04, segs=14, loc=(0, 0, -0.30),
        parent=lan_e, mat_=M_LANTERN_FRAME)
    # Cross bars
    beveled_cube(f"sl_bar{i}_1", (0.55, 0.02, 0.02), bevel_offset=0.005,
                 loc=(0, 0, -0.32), parent=lan_e, mat_=M_LANTERN_FRAME)
    beveled_cube(f"sl_bar{i}_2", (0.02, 0.55, 0.02), bevel_offset=0.005,
                 loc=(0, 0, -0.32), parent=lan_e, mat_=M_LANTERN_FRAME)
    # Candle/flame underneath
    cyl(f"sl_c{i}", r=0.04, depth=0.06, segs=8, loc=(0, 0, -0.36),
        parent=lan_e, mat_=M_KRATHONG_CANDLE)
    smooth_cone(f"sl_fl{i}", r1=0.05, r2=0.01, depth=0.10, segs=8, loc=(0, 0, -0.42),
                parent=lan_e, mat_=M_LANTERN_FLAME)
    lan_e["_phase"] = random.uniform(0, math.pi*2)
    lan_e["_base_x"] = px; lan_e["_base_y"] = py; lan_e["_base_z"] = pz
    lan_e["_amp_x"] = random.uniform(0.5, 1.5)
    lan_e["_amp_y"] = random.uniform(0.5, 1.5)
    lan_e["_speed"] = random.uniform(0.4, 1.0)
    lan_e["_rise"] = random.uniform(1.0, 2.5)
    sky_lanterns.append(lan_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Boats sway in waves
for b in boats:
    phase = b["root"]["_phase"]
    bz_b = b["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        b["root"].location.z = bz_b + math.sin(t * 1.5 + phase) * 0.10
        b["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3),
                                     math.cos(t * 1.5 + phase) * math.radians(3),
                                     b["root"].rotation_euler.z)
        b["root"].keyframe_insert("location", frame=f)
        b["root"].keyframe_insert("rotation_euler", frame=f)
        # Shaft prop spin
        b["shaft"].rotation_euler = (math.radians(-25) + math.sin(t * 6.0 + phase) * 0.5,
                                      0, 0)
        b["shaft"].keyframe_insert("rotation_euler", frame=f)

# Vendors call out (gentle motion)
for v in vendors:
    phase = v["root"]["_phase"]
    bz_v = v["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        v["root"].location.z = bz_v + math.sin(t * 1.5 + phase) * 0.10
        v["root"].keyframe_insert("location", frame=f)
        v["he"].rotation_euler = (0, 0, math.sin(t * 1.2 + phase) * math.radians(15))
        v["he"].keyframe_insert("rotation_euler", frame=f)
        v["hat"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3),
                                    math.cos(t * 1.5 + phase) * math.radians(3), 0)
        v["hat"].keyframe_insert("rotation_euler", frame=f)

# Monks meditate (very slight breath)
for mk in monks:
    phase = mk["root"]["_phase"]
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        s_m = 1 + math.sin(t * 0.5 + phase) * 0.02
        mk["root"].scale = (s_m, s_m, s_m)
        mk["root"].keyframe_insert("scale", frame=f)

# Suspended lanterns sway
for row in range(3):
    for col in range(12):
        lan = bpy.data.objects.get(f"sus_lan{row}_{col}")
        if lan is None: continue
        phase = lan["_phase"]
        for f in range(1, total_frames + 1, 4):
            t = (f - 1) / fps
            lan.rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(10),
                                   math.cos(t * 1.5 + phase) * math.radians(8), 0)
            lan.keyframe_insert("rotation_euler", frame=f)

# 600 krathongs float (water surface bobbing signature)
for kr in krathongs:
    phase = kr["_phase"]; speed = kr["_speed"]
    bx, by = kr["_base_x"], kr["_base_y"]
    ax, ay = kr["_amp_x"], kr["_amp_y"]
    az = kr["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Slow drift on water
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        # Bob up/down on water
        z = 0.30 + az * math.sin(t * 2.0 + phase)
        kr.location = (x, y, z)
        # Slight rotation
        kr.rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3),
                              math.cos(t * 1.5 + phase) * math.radians(3),
                              t * 0.3 + phase)
        kr.keyframe_insert("location", frame=f)
        kr.keyframe_insert("rotation_euler", frame=f)

# 400 sky lanterns rising (signature - going up slowly)
for sl in sky_lanterns:
    phase = sl["_phase"]; speed = sl["_speed"]; rise = sl["_rise"]
    bx, by, bz = sl["_base_x"], sl["_base_y"], sl["_base_z"]
    ax, ay = sl["_amp_x"], sl["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Slow rise
        x = bx + ax * math.sin(t * speed + phase) * 0.3
        y = by + ay * math.cos(t * speed * 0.9 + phase) * 0.3
        z = bz + t * rise  # Rising up
        sl.location = (x, y, z)
        sl.rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(3),
                              math.cos(t * 1.0 + phase) * math.radians(3),
                              math.sin(t * 0.5 + phase) * math.radians(5))
        sl.keyframe_insert("location", frame=f)
        sl.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_thai_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_thai_floating_market_lanterns] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_thai_floating_market_lanterns] pontoon + canal + 6 longtail boats with vendors hats fruits + 8 bamboo stalls + Wat temple chedi gold + 4 monks saffron + 36 suspended lanterns + 600 krathongs + 400 sky lanterns")
print("⭐ FIXES: 1 ground + 600 krathongs + 400 sky lanterns (signature Loy Krathong thematic mandatory) ⭐")
