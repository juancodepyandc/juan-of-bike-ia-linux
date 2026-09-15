"""
proc_korean_jeju_haenyeo_volcanic.py — 295e procédural AuroraIA (160e qualité EXPERT MESHY)
Korea Jeju Island: Hallasan volcano + harubang stone grandfathers + haenyeo women divers + tangerine groves + 600 mandarines + 400 dolphin spouts
RULES: 1 SEUL ground unique + particules prominentes signature
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB295)

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

# Sky tropical Korean
M_SKY = mat("sky", (0.55, 0.78, 0.95, 1.0), 0.0, 0.7, emission=(0.55,0.75,0.92), emission_strength=1.7)
M_SKY_LOW = mat("sky_l", (0.95, 0.85, 0.78, 1.0), 0.0, 0.7, emission=(0.92,0.82,0.78), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.92, 0.55, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.55), emission_strength=15.0)
M_CLOUD = mat("cl", (0.95, 0.95, 0.92, 1.0), 0.0, 0.85, emission=(0.95,0.95,0.92), emission_strength=0.8, alpha=0.85)

# Ground: 1 SEUL volcanic basalt (signature Jeju black rock)
M_BASALT = mat("ba", (0.20, 0.18, 0.18, 1.0), 0.0, 0.92, emission=(0.20,0.18,0.18), emission_strength=0.2)
M_BASALT_GRAY = mat("bag", (0.35, 0.32, 0.32, 1.0), 0.0, 0.85)
M_GREEN_FIELD = mat("gf", (0.42, 0.62, 0.32, 1.0), 0.0, 0.65, emission=(0.40,0.60,0.32), emission_strength=0.4)

# Ocean (SUNKEN below ground per renforced rule, no sandwich)
M_OCEAN = mat("oc", (0.18, 0.55, 0.72, 1.0), 0.2, 0.20, emission=(0.18,0.52,0.70), emission_strength=1.5, alpha=0.78)
M_OCEAN_DEEP = mat("ocd", (0.10, 0.32, 0.55, 1.0), 0.2, 0.25, alpha=0.85)
M_FOAM = mat("fm", (0.92, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.95,0.92), emission_strength=1.8, alpha=0.55)

# Hallasan volcano
M_VOLCANO_DARK = mat("vd", (0.32, 0.30, 0.28, 1.0), 0.0, 0.92)
M_VOLCANO_GREEN = mat("vg", (0.30, 0.55, 0.30, 1.0), 0.0, 0.75)
M_SNOW = mat("sn", (0.95, 0.95, 0.95, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.92), emission_strength=0.5)

# Harubang stone (signature volcanic basalt grandfather)
M_HARUBANG = mat("hr", (0.32, 0.30, 0.28, 1.0), 0.0, 0.88, emission=(0.30,0.28,0.28), emission_strength=0.3)
M_HARUBANG_DARK = mat("hrd", (0.18, 0.16, 0.16, 1.0), 0.0, 0.92)

# Haenyeo (signature female diver black wetsuit)
M_WETSUIT_BLACK = mat("wb", (0.10, 0.10, 0.12, 1.0), 0.3, 0.45)
M_WETSUIT_ORANGE = mat("wo", (0.92, 0.55, 0.20, 1.0), 0.0, 0.55, emission=(0.88,0.55,0.20), emission_strength=0.7)
M_GOGGLES = mat("go", (0.18, 0.18, 0.22, 1.0), 0.5, 0.20)
M_BUOY_ORANGE = mat("bo_o", (1.0, 0.55, 0.18, 1.0), 0.0, 0.30, emission=(0.95,0.55,0.18), emission_strength=1.2)
M_BUOY_WHITE = mat("bow", (0.92, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.88,0.88,0.85), emission_strength=0.4)
M_NET = mat("nt", (0.85, 0.78, 0.62, 1.0), 0.0, 0.85, alpha=0.65)
M_SKIN = mat("sk", (0.92, 0.78, 0.62, 1.0), 0.0, 0.55, emission=(0.88,0.78,0.62), emission_strength=0.3)
M_HAIR_BLACK = mat("hb", (0.10, 0.08, 0.06, 1.0), 0.0, 0.85)

# Tangerine
M_TANG_ORANGE = mat("to_o", (1.0, 0.55, 0.18, 1.0), 0.0, 0.40, emission=(0.95,0.55,0.18), emission_strength=1.5)
M_TANG_LIGHT = mat("tol", (1.0, 0.72, 0.30, 1.0), 0.0, 0.40, emission=(0.95,0.72,0.30), emission_strength=1.8)
M_TANG_DARK = mat("tod", (0.85, 0.42, 0.15, 1.0), 0.0, 0.50, emission=(0.82,0.42,0.15), emission_strength=1.2)
TANG_COLORS = [M_TANG_ORANGE, M_TANG_LIGHT, M_TANG_DARK]
M_TANG_LEAF = mat("tl", (0.20, 0.52, 0.22, 1.0), 0.0, 0.55, emission=(0.20,0.50,0.22), emission_strength=0.4)
M_TRUNK = mat("tk", (0.42, 0.28, 0.18, 1.0), 0.0, 0.85)

# Korea flag colors
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_FLAG_RED = mat("fr", (0.78, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.75,0.18,0.20), emission_strength=1.0)
M_FLAG_BLUE = mat("fb", (0.18, 0.32, 0.62, 1.0), 0.0, 0.45, emission=(0.18,0.32,0.60), emission_strength=1.0)
M_FLAG_BLACK = mat("fbk", (0.10, 0.10, 0.12, 1.0), 0.0, 0.45)

# Dolphin
M_DOLPHIN = mat("dl", (0.42, 0.48, 0.55, 1.0), 0.2, 0.45, emission=(0.40,0.48,0.55), emission_strength=0.3)
M_DOLPHIN_BELLY = mat("dlb", (0.85, 0.88, 0.92, 1.0), 0.0, 0.45)
M_SPOUT = mat("sp", (0.92, 0.95, 0.98, 1.0), 0.0, 0.10, emission=(0.90,0.95,0.98), emission_strength=2.5, alpha=0.55)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-50, 110, 35), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-50, 110, 35), mat_=M_SUN)
# Clouds
for ci in range(15):
    cx_c = random.uniform(-150, 150); cy_c = random.uniform(-100, 100); cz_c = random.uniform(45, 70)
    cloud_e = empty(f"cl{ci}_e", (cx_c, cy_c, cz_c))
    for cp in range(5):
        cpa = random.uniform(0, math.pi*2); cpr = random.uniform(0, 3)
        smooth_sphere(f"cl{ci}_p{cp}", r=random.uniform(2, 3.5), segs=14, rings=10,
                      loc=(math.cos(cpa)*cpr, math.sin(cpa)*cpr, random.uniform(-1, 1)),
                      parent=cloud_e, mat_=M_CLOUD, scale=(1.5, 1.5, 0.5))

# ============ ONE clean basalt ground (NO SANDWICH) ============
ground = beveled_cube("ground", (260, 260, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_BASALT)
# Ground bumps via scattered geometry only (no flat overlays)
for hi in range(180):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 130)
    smooth_sphere(f"hl{hi}", r=random.uniform(0.8, 2.0), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_BASALT_GRAY if hi % 3 == 0 else M_BASALT, scale=(1.4, 1.3, 0.20))
# Green grass patches (scattered organic, NOT flat plane)
for gi in range(100):
    a = random.uniform(0, math.pi*2); rad = random.uniform(15, 100)
    smooth_sphere(f"gr{gi}", r=random.uniform(0.5, 1.2), segs=10, rings=6,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.25),
                  mat_=M_GREEN_FIELD, scale=(1.4, 1.3, 0.85))

# ============ OCEAN SUNKEN (per renforced rule: z below ground, not sandwich) ============
ocean_e = empty("ocean", (0, -85, 0))
# Recessed below ground level (z < ground top)
beveled_cube("oc", (300, 50, 0.40), bevel_offset=0.10, loc=(0, 0, -0.50),
             parent=ocean_e, mat_=M_OCEAN)
# Foam waves above water surface
for fi in range(35):
    fx = random.uniform(-140, 140); fy = random.uniform(15, 22)
    smooth_sphere(f"fm{fi}", r=random.uniform(0.6, 1.2), segs=10, rings=6,
                  loc=(fx, fy, -0.30), parent=ocean_e, mat_=M_FOAM, scale=(1.4, 1.3, 0.4))

# ============ HALLASAN VOLCANO (signature distant peak) ============
def make_hallasan(name, loc, height, base_radius):
    base = empty(name, loc)
    n_layers = int(height / 4)
    for li in range(n_layers):
        lz = li * 4
        lr1 = base_radius * (1 - li / n_layers * 0.80)
        lr2 = base_radius * (1 - (li+1) / n_layers * 0.80)
        smooth_cone(f"{name}_l{li}", r1=lr1, r2=lr2, depth=4.5, segs=20,
                    loc=(0, 0, lz + 2.25), parent=base,
                    mat_=M_VOLCANO_DARK if li < n_layers*0.4 else (M_VOLCANO_GREEN if li < n_layers*0.75 else M_SNOW))
    # Crater
    cyl(f"{name}_cr", r=base_radius*0.25, depth=1.5, segs=16,
        loc=(0, 0, height - 0.75), parent=base, mat_=M_VOLCANO_DARK)
    return base

make_hallasan("hallasan", (0, 80, 0), 45, 14)
make_hallasan("h2", (-50, 75, 0), 25, 8)
make_hallasan("h3", (45, 80, 0), 28, 9)

# ============ 4 HARUBANG STONE GRANDFATHERS (signature mushroom-shape) ============
def make_harubang(name, loc, scale=1.0):
    base = empty(name, loc)
    # Pedestal
    cyl(f"{name}_pd", r=0.55, depth=0.30, segs=14, loc=(0, 0, 0.15), parent=base, mat_=M_HARUBANG_DARK)
    # Body (tapered cylinder)
    smooth_cone(f"{name}_bo", r1=0.50, r2=0.45, depth=1.6, segs=14, loc=(0, 0, 1.10),
                parent=base, mat_=M_HARUBANG)
    # Head (mushroom cap signature)
    smooth_sphere(f"{name}_h", r=0.55, segs=18, rings=14, loc=(0, 0, 2.05),
                  parent=base, mat_=M_HARUBANG, scale=(1.1, 1.1, 0.85))
    # MUSHROOM HAT (signature pointed)
    smooth_cone(f"{name}_ha", r1=0.55, r2=0.20, depth=0.55, segs=14, loc=(0, 0, 2.55),
                parent=base, mat_=M_HARUBANG_DARK)
    # Big bulbous nose (signature)
    smooth_sphere(f"{name}_no", r=0.10, segs=12, rings=10, loc=(0, -0.45, 2.05),
                  parent=base, mat_=M_HARUBANG)
    # Eyes carved (signature deep set)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.04, loc=(side*0.18, -0.42, 2.20),
                      parent=base, mat_=M_HARUBANG_DARK)
    # Folded hands carved in front (signature)
    smooth_sphere(f"{name}_hn", r=0.20, segs=12, rings=10, loc=(0, -0.45, 1.10),
                  parent=base, mat_=M_HARUBANG, scale=(1.2, 0.6, 0.5))
    return base

for i, (hx, hy) in enumerate([(-35, -20), (-15, -15), (15, -15), (35, -20)]):
    make_harubang(f"hb{i}", (hx, hy, 0))

# ============ 4 HAENYEO WOMEN DIVERS (signature wetsuit + buoy) ============
def make_haenyeo(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Black wetsuit body (signature)
    smooth_cone(f"{name}_bo", r1=0.30, r2=0.34, depth=0.85, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=M_WETSUIT_BLACK)
    # Orange chest stripe (signature visibility)
    cyl(f"{name}_cs", r=0.35, depth=0.18, segs=14, loc=(0, 0, 1.40),
        parent=base, mat_=M_WETSUIT_ORANGE)
    # Pants wetsuit
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.11, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=M_WETSUIT_BLACK)
    # Bare feet
    for side in (-1, 1):
        beveled_cube(f"{name}_f{side}", (0.10, 0.20, 0.05), bevel_offset=0.01,
                     loc=(side*0.13, 0.04, 0.03), parent=base, mat_=M_SKIN)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.32, 0, 1.60), parent=base)
        sh.rotation_euler = (math.radians(-70), 0, math.radians(side*20))
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=M_WETSUIT_BLACK)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=M_WETSUIT_BLACK)
    # Head
    head_h_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_h_e, mat_=M_SKIN)
    # Diving hood (black covering head)
    cyl(f"{name}_hd", r=0.20, depth=0.30, segs=14, loc=(0, 0, 0),
        parent=head_h_e, mat_=M_WETSUIT_BLACK)
    smooth_sphere(f"{name}_hd_t", r=0.20, segs=14, rings=10, loc=(0, 0, 0.12),
                  parent=head_h_e, mat_=M_WETSUIT_BLACK, scale=(1, 1, 0.7))
    # GOGGLES (signature large)
    goggles_e = empty(f"{name}_gg", (0, -0.16, 0), parent=head_h_e)
    for side in (-1, 1):
        cyl(f"{name}_gg{side}", r=0.06, depth=0.06, segs=12,
            loc=(side*0.07, 0, 0.03), parent=goggles_e, mat_=M_GOGGLES).rotation_euler = (math.radians(90), 0, 0)
        # Lens
        smooth_sphere(f"{name}_gl{side}", r=0.05, segs=10, rings=8,
                      loc=(side*0.07, -0.02, 0.03), parent=goggles_e, mat_=M_OCEAN)
    # Strap
    cyl(f"{name}_gst", r=0.015, depth=0.40, segs=8, loc=(0, 0, 0.03),
        parent=goggles_e, mat_=M_WETSUIT_BLACK).rotation_euler = (0, math.radians(90), 0)
    # ORANGE BUOY beside (signature haenyeo tewak)
    buoy_e = empty(f"{name}_by", (0.45, 0.25, 0.50), parent=base)
    smooth_sphere(f"{name}_by_b", r=0.30, segs=14, rings=12, loc=(0, 0, 0),
                  parent=buoy_e, mat_=M_BUOY_ORANGE)
    # White stripe
    cyl(f"{name}_by_s", r=0.31, depth=0.06, segs=14, loc=(0, 0, 0),
        parent=buoy_e, mat_=M_BUOY_WHITE)
    # Mesh net hanging
    cyl(f"{name}_by_n", r=0.20, depth=0.40, segs=10, loc=(0, 0, -0.40),
        parent=buoy_e, mat_=M_NET)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_h_e}

haenyeos = []
for i, (hx, hy, fac) in enumerate([(-20, -45, math.radians(20)), (-5, -50, math.radians(0)),
                                      (10, -48, math.radians(-15)), (25, -45, math.radians(-30))]):
    h = make_haenyeo(f"hy{i}", (hx, hy, 0), facing=fac)
    haenyeos.append(h)

# ============ TANGERINE GROVE (signature Jeju) ============
def make_tangerine_tree(name, loc):
    base = empty(name, loc)
    # Trunk
    cyl(f"{name}_t", r=0.18, depth=2.5, segs=10, loc=(0, 0, 1.25), parent=base, mat_=M_TRUNK)
    # Canopy
    canopy_e = empty(f"{name}_ce", (0, 0, 2.8), parent=base)
    for ci in range(12):
        ca = random.uniform(0, math.pi*2); cr = random.uniform(0, 1.2)
        smooth_sphere(f"{name}_c{ci}", r=random.uniform(0.55, 0.85), segs=12, rings=8,
                      loc=(math.cos(ca)*cr, math.sin(ca)*cr, random.uniform(-0.3, 0.5)),
                      parent=canopy_e, mat_=M_TANG_LEAF)
    # Tangerine fruits (signature orange clusters)
    for fi in range(15):
        fa = random.uniform(0, math.pi*2); fr_d = random.uniform(0.6, 1.3)
        smooth_sphere(f"{name}_fr{fi}", r=0.12, segs=10, rings=8,
                      loc=(math.cos(fa)*fr_d, math.sin(fa)*fr_d, random.uniform(2.4, 3.3)),
                      parent=base, mat_=random.choice(TANG_COLORS))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "canopy": canopy_e}

tangerine_trees = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    tx = math.cos(a) * 40
    ty = math.sin(a) * 25 + 20
    t = make_tangerine_tree(f"tg{i}", (tx, ty, 0))
    tangerine_trees.append(t)

# ============ KOREA FLAG (Taegukgi - signature trigrams + yin yang) ============
flag_e = empty("flag", (-55, -35, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_HARUBANG_DARK)
# White field
beveled_cube("fl_w", (4, 0.05, 2.5), bevel_offset=0.06, loc=(2, 0, 10.5),
             parent=flag_e, mat_=M_FLAG_WHITE)
# Yin Yang circle (signature taeguk - red top, blue bottom curving)
yy_e = empty("fl_yy", (2, -0.06, 10.5), parent=flag_e)
# Red half (top curving)
smooth_sphere("fl_yy_r", r=0.50, segs=18, rings=14, loc=(0, 0, 0.15),
              parent=yy_e, mat_=M_FLAG_RED, scale=(1, 0.10, 0.7))
# Blue half (bottom curving)
smooth_sphere("fl_yy_b", r=0.50, segs=18, rings=14, loc=(0, 0, -0.15),
              parent=yy_e, mat_=M_FLAG_BLUE, scale=(1, 0.10, 0.7))
# Trigrams at corners (signature)
for tg_i, (tx_g, tz_g, n_b, gaps) in enumerate([
    (-1.30, 0.85, 3, []),  # Top left - 3 solid bars (heaven)
    (1.30, 0.85, 3, [1]),   # Top right - 1 gap (water)
    (-1.30, -0.85, 3, [0, 2]),  # Bottom left - 2 gaps (fire)
    (1.30, -0.85, 3, [0, 1, 2])  # Bottom right - all gaps (earth)
]):
    tg_e = empty(f"fl_tg{tg_i}", (2 + tx_g, -0.06, 10.5 + tz_g), parent=flag_e)
    for bi_t in range(n_b):
        bz_t = (bi_t - 1) * 0.10
        if bi_t in gaps:
            # 2 halves with gap
            beveled_cube(f"fl_tg{tg_i}_b{bi_t}_l", (0.18, 0.05, 0.05), bevel_offset=0.005,
                         loc=(-0.13, 0, bz_t), parent=tg_e, mat_=M_FLAG_BLACK)
            beveled_cube(f"fl_tg{tg_i}_b{bi_t}_r", (0.18, 0.05, 0.05), bevel_offset=0.005,
                         loc=(0.13, 0, bz_t), parent=tg_e, mat_=M_FLAG_BLACK)
        else:
            # Solid bar
            beveled_cube(f"fl_tg{tg_i}_b{bi_t}", (0.50, 0.05, 0.05), bevel_offset=0.005,
                         loc=(0, 0, bz_t), parent=tg_e, mat_=M_FLAG_BLACK)
flag_e["_phase"] = 0

# ============================================================
# 600 MANDARINES + 400 DOLPHIN SPOUTS (PARTICULES SIGNATURES PROMINENT)
# ============================================================
mandarines = []
for i in range(600):
    px = random.uniform(-110, 110)
    py = random.uniform(-100, 100)
    pz = random.uniform(2, 25)
    m_col = random.choice(TANG_COLORS)
    m_e = empty(f"md{i}", (px, py, pz))
    # Tangerine ball (prominent size + bright)
    smooth_sphere(f"md{i}_b", r=0.13, segs=12, rings=10, loc=(0, 0, 0),
                  parent=m_e, mat_=m_col)
    # Small leaf on top
    beveled_cube(f"md{i}_l", (0.04, 0.06, 0.02), bevel_offset=0.005,
                 loc=(0.02, 0, 0.10), parent=m_e, mat_=M_TANG_LEAF)
    m_e["_phase"] = random.uniform(0, math.pi*2)
    m_e["_base_x"] = px; m_e["_base_y"] = py; m_e["_base_z"] = pz
    m_e["_amp_x"] = random.uniform(0.5, 1.5)
    m_e["_amp_y"] = random.uniform(0.5, 1.5)
    m_e["_amp_z"] = random.uniform(0.4, 1.0)
    m_e["_speed"] = random.uniform(0.4, 1.0)
    mandarines.append(m_e)

# 400 dolphin spouts (signature in ocean area)
dolphins = []
for i in range(400):
    px = random.uniform(-130, 130)
    py = random.uniform(-110, -50)  # In ocean area
    pz = -0.30
    d_e = empty(f"dl{i}", (px, py, pz))
    # Dolphin body (visible arc above water)
    smooth_sphere(f"dl{i}_b", r=0.20, segs=12, rings=10, loc=(0, 0, 0.15),
                  parent=d_e, mat_=M_DOLPHIN, scale=(2.0, 0.85, 0.55))
    # Belly
    smooth_sphere(f"dl{i}_be", r=0.18, segs=10, rings=8, loc=(0, 0, 0.05),
                  parent=d_e, mat_=M_DOLPHIN_BELLY, scale=(1.9, 0.85, 0.45))
    # Dorsal fin
    beveled_cube(f"dl{i}_df", (0.04, 0.06, 0.15), bevel_offset=0.01,
                 loc=(-0.05, 0, 0.32), parent=d_e, mat_=M_DOLPHIN)
    # SPOUT (signature water plume from blowhole)
    spout_e = empty(f"dl{i}_sp", (0.15, 0, 0.30), parent=d_e)
    for spi in range(8):
        spi_t = spi / 8.0
        cyl(f"dl{i}_sp{spi}", r=0.04 - spi*0.004, depth=0.20, segs=8,
            loc=(0, 0, 0.30 + spi*0.20), parent=spout_e, mat_=M_SPOUT)
    d_e["_phase"] = random.uniform(0, math.pi*2)
    d_e["_base_x"] = px; d_e["_base_y"] = py
    d_e["_speed"] = random.uniform(0.4, 1.0)
    d_e["_pulse"] = random.uniform(2, 5)
    d_e["_spout"] = spout_e
    dolphins.append(d_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Haenyeos sway
for h in haenyeos:
    phase = h["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        h["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(3), 0,
                                     h["root"].rotation_euler.z)
        h["root"].keyframe_insert("rotation_euler", frame=f)
        h["he"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(5), 0,
                                   math.cos(t * 1.0 + phase) * math.radians(15))
        h["he"].keyframe_insert("rotation_euler", frame=f)

# Tangerine trees sway
for t in tangerine_trees:
    phase = t["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        ft = (f - 1) / fps
        t["canopy"].rotation_euler = (math.sin(ft * 0.8 + phase) * math.radians(4),
                                       math.cos(ft * 0.8 + phase) * math.radians(4), 0)
        t["canopy"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 mandarines float multi-axis prominent
for m in mandarines:
    phase = m["_phase"]; speed = m["_speed"]
    bx, by, bz = m["_base_x"], m["_base_y"], m["_base_z"]
    ax, ay, az = m["_amp_x"], m["_amp_y"], m["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase) + t * 0.3
        m.location = (x, y, z)
        m.rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(15), 0,
                             t * 1.0 + phase)
        m.keyframe_insert("location", frame=f)
        m.keyframe_insert("rotation_euler", frame=f)

# 400 dolphins arc + spout
for d in dolphins:
    phase = d["_phase"]; speed = d["_speed"]; pulse = d["_pulse"]
    bx, by = d["_base_x"], d["_base_y"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * 3
        y = by + math.sin(t * speed + phase) * 2
        # Arc motion (out of water + back)
        z = -0.30 + abs(math.sin(t * speed * 1.5 + phase)) * 0.4
        d.location = (x, y, z)
        d.rotation_euler = (math.sin(t * speed * 1.5 + phase) * math.radians(20), 0,
                             math.atan2(math.cos(t * speed + phase),
                                         -math.sin(t * speed + phase)))
        d.keyframe_insert("location", frame=f)
        d.keyframe_insert("rotation_euler", frame=f)
        # Spout pulse
        sc = 0.5 + abs(math.sin(t * pulse + phase)) * 1.5
        d["_spout"].scale = (1, 1, sc)
        d["_spout"].keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_jeju_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_korean_jeju_haenyeo_volcanic] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Jeju Island EXPERT MESHY: 1 SEUL basalt ground + ocean SUNKEN no sandwich + Hallasan volcano 45m + 4 harubang stone grandfathers (signature mushroom hat + bulbous nose + carved eyes + folded hands) + 4 haenyeo female divers (signature black wetsuit + orange chest stripe + goggles + orange buoy tewak + mesh net) + 8 tangerine trees with fruits + Korea Taegukgi flag with yin yang + 4 trigrams + 600 mandarines prominent + 400 dolphins arc + spouts pulse signature")
print("🍊 FIXES EXPERT: 1 ground unique + ocean sunken + 600 mandarines + 400 dauphins signature Jeju 🍊")
