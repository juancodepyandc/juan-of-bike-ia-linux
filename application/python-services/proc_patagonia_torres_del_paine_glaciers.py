"""
proc_patagonia_torres_del_paine_glaciers.py — 278e procédural AuroraIA (143e qualité)
Patagonia Torres del Paine glaciers: 3 granite towers + Perito Moreno glacier + turquoise lake + 6 guanacos + 4 hikers + tent + Chile flag + 600 Andean snowflakes + 400 condors
FIXES : 1 ground tundra grass + signature snow + condors
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB278)

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

# Sky dramatic Patagonia
M_SKY = mat("sky", (0.42, 0.62, 0.85, 1.0), 0.0, 0.7, emission=(0.42,0.60,0.82), emission_strength=1.7)
M_SKY_LOW = mat("sky_l", (0.78, 0.85, 0.92, 1.0), 0.0, 0.7, emission=(0.78,0.85,0.92), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.92, 0.65, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.65), emission_strength=15.0)
M_CLOUD = mat("cl", (0.95, 0.95, 0.92, 1.0), 0.0, 0.85, emission=(0.95,0.95,0.92), emission_strength=1.0, alpha=0.85)
M_CLOUD_DARK = mat("cld", (0.72, 0.72, 0.78, 1.0), 0.0, 0.90, emission=(0.72,0.72,0.78), emission_strength=0.7, alpha=0.80)

# Tundra grass
M_TUNDRA = mat("tn", (0.62, 0.65, 0.42, 1.0), 0.0, 0.85, emission=(0.60,0.62,0.42), emission_strength=0.3)
M_TUNDRA_DARK = mat("tnd", (0.42, 0.45, 0.28, 1.0), 0.0, 0.92)
M_TUNDRA_DRY = mat("tdy", (0.78, 0.72, 0.45, 1.0), 0.0, 0.75, emission=(0.75,0.70,0.45), emission_strength=0.4)
M_ROCK_GRAY = mat("rg", (0.42, 0.42, 0.45, 1.0), 0.0, 0.85)

# Granite towers (signature Torres del Paine)
M_GRANITE = mat("gr", (0.62, 0.62, 0.60, 1.0), 0.0, 0.80, emission=(0.60,0.60,0.58), emission_strength=0.3)
M_GRANITE_DARK = mat("grd", (0.35, 0.35, 0.38, 1.0), 0.0, 0.90)
M_GRANITE_PINK = mat("grp", (0.78, 0.65, 0.55, 1.0), 0.0, 0.80, emission=(0.75,0.62,0.55), emission_strength=0.3)
M_SNOW = mat("sn", (0.95, 0.95, 0.95, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.92), emission_strength=0.5)
M_SNOW_BLUE = mat("snb", (0.92, 0.95, 1.0, 1.0), 0.0, 0.45, emission=(0.90,0.92,0.98), emission_strength=0.7)

# Glacier
M_GLACIER = mat("gl", (0.78, 0.92, 0.95, 1.0), 0.0, 0.20, emission=(0.75,0.92,0.92), emission_strength=1.0)
M_GLACIER_BLUE = mat("glb", (0.45, 0.85, 0.95, 1.0), 0.0, 0.15, emission=(0.42,0.82,0.92), emission_strength=1.5)
M_GLACIER_DEEP = mat("gld", (0.30, 0.65, 0.85, 1.0), 0.0, 0.20, emission=(0.30,0.62,0.82), emission_strength=1.3)

# Lake turquoise
M_LAKE = mat("lk", (0.32, 0.78, 0.82, 1.0), 0.2, 0.20, emission=(0.30,0.75,0.80), emission_strength=1.7, alpha=0.78)
M_LAKE_DEEP = mat("lkd", (0.18, 0.55, 0.72, 1.0), 0.2, 0.25, alpha=0.85)
M_LAKE_FOAM = mat("lkf", (0.92, 0.95, 0.95, 1.0), 0.0, 0.30, emission=(0.90,0.92,0.92), emission_strength=1.5, alpha=0.65)

# Guanaco (signature llama-like)
M_GUANACO_BROWN = mat("gb", (0.78, 0.55, 0.32, 1.0), 0.0, 0.65, emission=(0.75,0.55,0.32), emission_strength=0.3)
M_GUANACO_CREAM = mat("gc", (0.92, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.82,0.62), emission_strength=0.4)
M_GUANACO_DARK = mat("gd", (0.32, 0.20, 0.10, 1.0), 0.0, 0.75)

# Hikers
M_SKIN = mat("sk", (0.85, 0.65, 0.45, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.45), emission_strength=0.3)
M_HAIR_BROWN = mat("hbr", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)

# Hiking gear
M_HIKER_RED = mat("hr", (0.85, 0.25, 0.20, 1.0), 0.0, 0.55, emission=(0.82,0.25,0.20), emission_strength=0.5)
M_HIKER_BLUE = mat("hb", (0.20, 0.45, 0.78, 1.0), 0.0, 0.55, emission=(0.20,0.42,0.75), emission_strength=0.5)
M_HIKER_GREEN = mat("hg", (0.30, 0.65, 0.40, 1.0), 0.0, 0.55, emission=(0.30,0.62,0.40), emission_strength=0.5)
M_HIKER_YELLOW = mat("hy", (1.0, 0.78, 0.20, 1.0), 0.0, 0.55, emission=(0.95,0.75,0.20), emission_strength=0.7)
HIKER_COLORS = [M_HIKER_RED, M_HIKER_BLUE, M_HIKER_GREEN, M_HIKER_YELLOW]
M_PANTS_GRAY = mat("pg", (0.42, 0.42, 0.45, 1.0), 0.0, 0.65)
M_BOOT = mat("bt", (0.32, 0.18, 0.10, 1.0), 0.2, 0.45)
M_BACKPACK = mat("bp", (0.32, 0.30, 0.32, 1.0), 0.0, 0.75)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Tent
M_TENT_ORANGE = mat("to", (0.95, 0.55, 0.20, 1.0), 0.0, 0.65, emission=(0.92,0.55,0.20), emission_strength=0.7)
M_TENT_DARK = mat("td", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)

# Chile flag
M_FLAG_BLUE = mat("fb", (0.10, 0.32, 0.65, 1.0), 0.0, 0.45, emission=(0.10,0.32,0.62), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_FLAG_RED = mat("fr", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=1.0)
M_FLAG_STAR = mat("fs", (0.95, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.88), emission_strength=2.5)

# Snowflakes
M_FLAKE_WHITE = mat("flw", (0.98, 0.98, 0.95, 1.0), 0.0, 0.20, emission=(0.95,0.95,0.92), emission_strength=2.5)
M_FLAKE_BLUE = mat("flb", (0.85, 0.92, 0.98, 1.0), 0.0, 0.20, emission=(0.82,0.92,0.98), emission_strength=2.2)

# Condor (signature Andean)
M_CONDOR_BLACK = mat("cb", (0.10, 0.10, 0.12, 1.0), 0.0, 0.55, emission=(0.10,0.10,0.12), emission_strength=0.3)
M_CONDOR_WHITE = mat("cw", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.92,0.88,0.82), emission_strength=0.4)
M_CONDOR_HEAD = mat("ch", (0.85, 0.45, 0.25, 1.0), 0.0, 0.65, emission=(0.82,0.42,0.25), emission_strength=0.4)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Sun
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-50, 110, 35), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-50, 110, 35), mat_=M_SUN)
# Clouds (dramatic Patagonian)
for ci in range(25):
    cx_c = random.uniform(-160, 160); cy_c = random.uniform(-160, 160); cz_c = random.uniform(50, 75)
    cloud_e = empty(f"cl{ci}_e", (cx_c, cy_c, cz_c))
    cloud_mat = M_CLOUD if random.random() > 0.4 else M_CLOUD_DARK
    for cp in range(5):
        cpa = random.uniform(0, math.pi*2); cpr = random.uniform(0, 4)
        smooth_sphere(f"cl{ci}_p{cp}", r=random.uniform(2.5, 4.5), segs=14, rings=10,
                      loc=(math.cos(cpa)*cpr, math.sin(cpa)*cpr, random.uniform(-1, 1)),
                      parent=cloud_e, mat_=cloud_mat, scale=(1.5, 1.5, 0.5))

# ============ ONE clean tundra ground ============
ground = beveled_cube("ground", (280, 280, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_TUNDRA)
# Tundra grass bumps (organic 3D)
for hi in range(220):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 130)
    smooth_sphere(f"hl{hi}", r=random.uniform(1.2, 2.5), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_TUNDRA_DARK if hi % 3 == 0 else (M_TUNDRA if hi % 3 == 1 else M_TUNDRA_DRY),
                  scale=(1.5, 1.4, 0.20))
# Rock patches
for ri in range(80):
    a = random.uniform(0, math.pi*2); rad = random.uniform(5, 110)
    smooth_sphere(f"rk{ri}", r=random.uniform(0.5, 1.2), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.12),
                  mat_=M_ROCK_GRAY, scale=(1.4, 1.3, 0.25))

# ============ 3 TORRES DEL PAINE TOWERS (signature granite) ============
def make_torre(name, loc, height, base_radius):
    base = empty(name, loc)
    # Vertical fractured granite tower
    n_sections = max(8, int(height / 4))
    for si in range(n_sections):
        sz = si * (height / n_sections)
        sr = base_radius * (1 - si / n_sections * 0.25)  # Slight taper
        # Irregular vertical profile
        smooth_sphere(f"{name}_s{si}", r=sr, segs=16, rings=12,
                      loc=(random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2),
                           sz + height/n_sections/2),
                      parent=base, mat_=M_GRANITE if si % 2 == 0 else M_GRANITE_PINK,
                      scale=(1.0, 1.0, 1.2))
    # Sharp peak
    smooth_cone(f"{name}_pk", r1=base_radius*0.6, r2=0.1, depth=4, segs=10,
                loc=(0, 0, height + 1.5), parent=base, mat_=M_GRANITE_DARK)
    # Vertical striations (signature cracks)
    for ci in range(8):
        ca = (ci / 8.0) * math.pi * 2
        beveled_cube(f"{name}_cr{ci}", (0.20, 0.10, height*0.85), bevel_offset=0.04,
                     loc=(math.cos(ca)*base_radius*0.95, math.sin(ca)*base_radius*0.95, height/2),
                     parent=base, mat_=M_GRANITE_DARK)
    # Snow cap on top
    for sni in range(4):
        smooth_sphere(f"{name}_sn{sni}", r=base_radius*0.4 - sni*0.05, segs=14, rings=10,
                      loc=(0, 0, height - sni*0.6),
                      parent=base, mat_=M_SNOW, scale=(1.4, 1.3, 0.5))
    return base

# 3 iconic towers (Torres del Paine signature)
torres_pos = [(-12, 75, 45, 6), (0, 80, 50, 7), (12, 75, 42, 5.5)]
for i, (tx_t, ty_t, th, tr) in enumerate(torres_pos):
    make_torre(f"to{i}", (tx_t, ty_t, 0), th, tr)

# Surrounding mountain ridge (background)
for mi in range(8):
    mx = -120 + mi * 30
    my = random.uniform(85, 110)
    mh = random.uniform(20, 35)
    base_m = empty(f"mt{mi}", (mx, my, 0))
    for li in range(int(mh/3)):
        lz_m = li * 3
        lr1_m = 8 - li * 0.5
        lr2_m = 7 - (li+1) * 0.5
        smooth_cone(f"mt{mi}_l{li}", r1=lr1_m, r2=lr2_m, depth=3.5, segs=16,
                    loc=(0, 0, lz_m + 1.75), parent=base_m, mat_=M_GRANITE_DARK)
    # Snow cap
    smooth_cone(f"mt{mi}_sc", r1=3, r2=0.1, depth=2.5, segs=14,
                loc=(0, 0, mh + 0.5), parent=base_m, mat_=M_SNOW)

# ============ PERITO MORENO GLACIER (signature blue ice) ============
glacier_e = empty("glacier", (-50, 30, 0))
# Massive ice field (signature jagged surface)
for gi in range(40):
    a = random.uniform(0, math.pi*2); rad = random.uniform(0, 20)
    smooth_sphere(f"gl{gi}", r=random.uniform(1.5, 3.5), segs=14, rings=10,
                  loc=(math.cos(a)*rad, math.sin(a)*rad, random.uniform(1, 5)),
                  parent=glacier_e, mat_=M_GLACIER if gi % 2 else M_GLACIER_BLUE,
                  scale=(1.4, 1.3, 0.85))
# Ice cliffs (signature blue cracks)
for ci in range(15):
    ca = (ci / 15.0) * math.pi * 2
    cz_g = random.uniform(3, 8)
    beveled_cube(f"glc{ci}", (random.uniform(2, 4), 0.40, random.uniform(3, 6)), bevel_offset=0.10,
                 loc=(math.cos(ca)*16, math.sin(ca)*16, cz_g), parent=glacier_e,
                 mat_=M_GLACIER_DEEP).rotation_euler = (0, 0, ca)
# Crevasses (signature deep blue cracks)
for cri in range(8):
    cra = (cri / 8.0) * math.pi * 2
    beveled_cube(f"glcr{cri}", (4, 0.30, 1), bevel_offset=0.05,
                 loc=(math.cos(cra)*8, math.sin(cra)*8, 4), parent=glacier_e,
                 mat_=M_GLACIER_DEEP).rotation_euler = (0, 0, cra)
# Ice towers
for ti in range(6):
    ta = (ti / 6.0) * math.pi * 2
    smooth_cone(f"glti{ti}", r1=2, r2=0.5, depth=6, segs=12,
                loc=(math.cos(ta)*10, math.sin(ta)*10, 3), parent=glacier_e, mat_=M_GLACIER_BLUE)

# ============ TURQUOISE LAKE (signature) ============
lake_e = empty("lake", (40, 35, 0))
# Lake water
beveled_cube("lk", (60, 35, 0.20), bevel_offset=0.08, loc=(0, 0, 0.20),
             parent=lake_e, mat_=M_LAKE)
beveled_cube("lk_d", (55, 32, 0.15), bevel_offset=0.06, loc=(0, 0, 0.25),
             parent=lake_e, mat_=M_LAKE_DEEP)
# Foam at edges
for fi in range(25):
    fx = random.uniform(-28, 28); fy = random.uniform(-16, 16)
    cyl(f"lkf{fi}", r=random.uniform(0.4, 0.8), depth=0.06, segs=14,
        loc=(fx, fy, 0.30), parent=lake_e, mat_=M_LAKE_FOAM)
# Ice floes (signature)
for fli in range(8):
    fla = random.uniform(0, math.pi*2); flr = random.uniform(5, 20)
    beveled_cube(f"flo{fli}", (random.uniform(1, 2.5), random.uniform(0.8, 1.8), 0.30),
                 bevel_offset=0.06,
                 loc=(math.cos(fla)*flr, math.sin(fla)*flr, 0.35),
                 parent=lake_e, mat_=M_GLACIER_BLUE).rotation_euler = (0, 0, fla)

# ============ 6 GUANACOS (signature) ============
def make_guanaco(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_bo", r=0.45, segs=14, rings=12, loc=(0, 0, 1.30),
                  parent=base, mat_=M_GUANACO_BROWN, scale=(1.5, 0.85, 0.85))
    # Belly cream
    smooth_sphere(f"{name}_be", r=0.40, segs=12, rings=10, loc=(0, 0, 1.15),
                  parent=base, mat_=M_GUANACO_CREAM, scale=(1.4, 0.85, 0.55))
    # Long neck (signature)
    neck_e = empty(f"{name}_ne", (0.55, 0, 1.50), parent=base)
    neck_e.rotation_euler = (0, math.radians(-30), 0)
    for ni in range(5):
        cyl(f"{name}_n{ni}", r=0.13 - ni*0.005, depth=0.18, segs=10,
            loc=(0, 0, 0.10 + ni*0.18), parent=neck_e, mat_=M_GUANACO_BROWN)
    # Head
    head_g_e = empty(f"{name}_he", (0, 0, 1.05), parent=neck_e)
    smooth_sphere(f"{name}_h", r=0.18, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_g_e, mat_=M_GUANACO_BROWN, scale=(1.3, 0.85, 1.0))
    # Snout
    smooth_sphere(f"{name}_sn", r=0.10, segs=10, rings=8, loc=(0.18, 0, -0.05),
                  parent=head_g_e, mat_=M_GUANACO_DARK)
    # Pointy ears
    for side in (-1, 1):
        smooth_cone(f"{name}_er{side}", r1=0.04, r2=0.01, depth=0.18, segs=8,
                    loc=(-0.05, side*0.10, 0.22), parent=head_g_e, mat_=M_GUANACO_BROWN)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.03, loc=(0.08, side*0.13, 0.05),
                      parent=head_g_e, mat_=M_EYE)
    # 4 long thin legs (signature)
    for li_g, (lx_g, ly_g) in enumerate([(0.50, 0.25), (0.50, -0.25), (-0.50, 0.25), (-0.50, -0.25)]):
        leg_e = empty(f"{name}_le{li_g}", (lx_g, ly_g, 1.00), parent=base)
        # Upper leg
        cyl(f"{name}_ul{li_g}", r=0.07, depth=0.50, segs=10, loc=(0, 0, -0.25),
            parent=leg_e, mat_=M_GUANACO_BROWN)
        # Lower leg
        cyl(f"{name}_ll{li_g}", r=0.06, depth=0.50, segs=10, loc=(0, 0, -0.75),
            parent=leg_e, mat_=M_GUANACO_BROWN)
        # Hoof
        beveled_cube(f"{name}_hf{li_g}", (0.08, 0.10, 0.05), bevel_offset=0.01,
                     loc=(0, 0, -1.02), parent=leg_e, mat_=M_GUANACO_DARK)
    # Tail
    cyl(f"{name}_t", r=0.05, depth=0.20, segs=8, loc=(-0.60, 0, 1.40),
        parent=base, mat_=M_GUANACO_BROWN).rotation_euler = (0, math.radians(45), 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "neck": neck_e, "he": head_g_e}

guanacos = []
guanaco_pos = [(-25, 0, math.radians(0)), (-15, 5, math.radians(30)),
                (-5, -5, math.radians(-20)), (10, 0, math.radians(45)),
                (20, 8, math.radians(-30)), (30, -2, math.radians(15))]
for i, (gx, gy, fac) in enumerate(guanaco_pos):
    g = make_guanaco(f"gu{i}", (gx, gy, 0), facing=fac)
    guanacos.append(g)

# ============ 4 HIKERS (signature) ============
def make_hiker(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    jacket_col = random.choice(HIKER_COLORS)
    # Jacket
    smooth_cone(f"{name}_j", r1=0.30, r2=0.32, depth=0.85, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=jacket_col)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.11, depth=0.95, segs=10,
            loc=(side*0.13, 0, 0.50), parent=base, mat_=M_PANTS_GRAY)
    # Hiking boots
    for side in (-1, 1):
        beveled_cube(f"{name}_b{side}", (0.13, 0.30, 0.10), bevel_offset=0.02,
                     loc=(side*0.13, 0.04, 0.05), parent=base, mat_=M_BOOT)
    # Backpack (signature)
    backpack_e = empty(f"{name}_bp", (0, 0.35, 1.30), parent=base)
    beveled_cube(f"{name}_bp_b", (0.45, 0.20, 0.80), bevel_offset=0.06, loc=(0, 0, 0),
                 parent=backpack_e, mat_=M_BACKPACK)
    # Straps
    for side in (-1, 1):
        beveled_cube(f"{name}_bp_st{side}", (0.04, 0.10, 0.55), bevel_offset=0.01,
                     loc=(side*0.18, -0.20, 0), parent=backpack_e, mat_=M_BACKPACK)
    # Sleeping bag attached
    cyl(f"{name}_bp_sb", r=0.10, depth=0.40, segs=10, loc=(0, 0, 0.50),
        parent=backpack_e, mat_=M_HIKER_BLUE).rotation_euler = (0, math.radians(90), 0)
    # Trekking pole (signature)
    pole_e = empty(f"{name}_pl", (0.40, -0.10, 0.40), parent=base)
    pole_e.rotation_euler = (0, math.radians(15), 0)
    cyl(f"{name}_pl_p", r=0.015, depth=1.5, segs=8, loc=(0, 0, 0),
        parent=pole_e, mat_=M_PANTS_GRAY)
    # Pole grip
    cyl(f"{name}_pl_g", r=0.03, depth=0.15, segs=8, loc=(0, 0, 0.75),
        parent=pole_e, mat_=M_BOOT)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.60), parent=base)
        sh.rotation_euler = (math.radians(-30 if side_idx == 0 else -45), 0, math.radians(side*15))
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=jacket_col)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=M_SKIN)
    # Head
    head_h_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_h_e, mat_=M_SKIN)
    # Hair
    for hi in range(10):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.08, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.13),
            parent=head_h_e, mat_=M_HAIR_BROWN)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_h_e, mat_=M_EYE)
    # Beanie hat (signature)
    cyl(f"{name}_ha_c", r=0.19, depth=0.20, segs=14, loc=(0, 0, 0.16),
        parent=head_h_e, mat_=random.choice(HIKER_COLORS))
    smooth_sphere(f"{name}_ha_p", r=0.06, loc=(0, 0, 0.30),
                  parent=head_h_e, mat_=M_FLAG_WHITE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_h_e}

hikers = []
hiker_pos = [(-8, -25, math.radians(10)), (-2, -28, math.radians(0)),
              (4, -25, math.radians(-10)), (10, -28, math.radians(15))]
for i, (hx, hy, fac) in enumerate(hiker_pos):
    h = make_hiker(f"hk{i}", (hx, hy, 0), facing=fac)
    hikers.append(h)

# ============ CAMPING TENT (signature) ============
def make_tent(name, loc):
    base = empty(name, loc)
    # Tent body (A-frame signature)
    tent_e = empty(f"{name}_e", (0, 0, 0), parent=base)
    # 2 slanted sides
    for side in (-1, 1):
        slope_e = empty(f"{name}_sl{side}", (side*0.5, 0, 0.6), parent=tent_e)
        slope_e.rotation_euler = (0, side*math.radians(30), 0)
        beveled_cube(f"{name}_s{side}", (1.5, 3.0, 0.10), bevel_offset=0.04, loc=(0, 0, 0),
                     parent=slope_e, mat_=M_TENT_ORANGE)
    # Front triangle
    for side in (-1, 1):
        triangle_e = empty(f"{name}_tr{side}", (0, side*1.55, 0.6), parent=tent_e)
        triangle_e.rotation_euler = (math.radians(90), 0, 0)
        smooth_cone(f"{name}_tp{side}", r1=1.5, r2=0.05, depth=0.05, segs=3,
                    loc=(0, 0, 0), parent=triangle_e, mat_=M_TENT_ORANGE).rotation_euler = (0, 0, math.radians(30))
    # Ground sheet
    beveled_cube(f"{name}_g", (1.8, 3.2, 0.04), bevel_offset=0.02, loc=(0, 0, 0.02),
                 parent=tent_e, mat_=M_TENT_DARK)
    # Guy lines (ropes)
    for ri in (-1, 1):
        cyl(f"{name}_gl{ri}", r=0.01, depth=2, segs=4,
            loc=(0, ri*2.5, 0.4), parent=tent_e, mat_=M_FLAG_WHITE).rotation_euler = (math.radians(45*ri), 0, 0)
    return base

make_tent("tent1", (-15, -32, 0))
make_tent("tent2", (10, -35, 0))

# ============ CHILE FLAG (signature) ============
flag_e = empty("flag", (-55, -40, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_TENT_DARK)
# Blue square top-left (signature canton)
beveled_cube("fl_b", (1.2, 0.05, 1.2), bevel_offset=0.06, loc=(0.6, 0, 11.1),
             parent=flag_e, mat_=M_FLAG_BLUE)
# White stripe top
beveled_cube("fl_w", (2.8, 0.05, 1.2), bevel_offset=0.06, loc=(2.6, 0, 11.1),
             parent=flag_e, mat_=M_FLAG_WHITE)
# Red stripe bottom
beveled_cube("fl_r", (4, 0.05, 1.2), bevel_offset=0.06, loc=(2, 0, 9.9),
             parent=flag_e, mat_=M_FLAG_RED)
# White star (signature)
star_e = empty("fl_st", (0.6, -0.06, 11.1), parent=flag_e)
for sp in range(5):
    spa = (sp / 5.0) * math.pi * 2 + math.pi/2
    beveled_cube(f"fl_st_p{sp}", (0.04, 0.06, 0.30), bevel_offset=0.01,
                 loc=(math.cos(spa)*0.15, 0, math.sin(spa)*0.15),
                 parent=star_e, mat_=M_FLAG_STAR).rotation_euler = (spa - math.pi/2, 0, 0)
smooth_sphere("fl_stc", r=0.08, loc=(0, 0, 0), parent=star_e, mat_=M_FLAG_STAR)
flag_e["_phase"] = 0

# ============================================================
# 600 ANDEAN SNOWFLAKES + 400 CONDORS (PARTICULES SIGNATURES)
# ============================================================
flakes = []
for i in range(600):
    px = random.uniform(-110, 110)
    py = random.uniform(-110, 110)
    pz = random.uniform(3, 35)
    flake_e = empty(f"sf{i}", (px, py, pz))
    flake_col = M_FLAKE_WHITE if i % 2 == 0 else M_FLAKE_BLUE
    # 6-point snowflake
    for sp in range(6):
        spa = (sp / 6.0) * math.pi * 2
        beveled_cube(f"sf{i}_p{sp}", (0.03, 0.08, 0.01), bevel_offset=0.005,
                     loc=(math.cos(spa)*0.06, math.sin(spa)*0.06, 0),
                     parent=flake_e, mat_=flake_col).rotation_euler = (0, 0, spa)
    smooth_sphere(f"sf{i}_c", r=0.025, loc=(0, 0, 0), parent=flake_e, mat_=flake_col)
    flake_e["_phase"] = random.uniform(0, math.pi*2)
    flake_e["_base_x"] = px; flake_e["_base_z"] = pz
    flake_e["_drift"] = random.uniform(0.2, 0.5)
    flake_e["_fall"] = random.uniform(0.6, 1.4)
    flake_e["_swing"] = random.uniform(1.0, 2.0)
    flakes.append(flake_e)

# 400 condors
condors = []
for i in range(400):
    px = random.uniform(-130, 130)
    py = random.uniform(-130, 130)
    pz = random.uniform(20, 55)
    c_e = empty(f"co{i}", (px, py, pz))
    # Body
    smooth_sphere(f"co{i}_bo", r=0.25, segs=12, rings=10, loc=(0, 0, 0),
                  parent=c_e, mat_=M_CONDOR_BLACK, scale=(1.5, 0.85, 0.85))
    # White neck ruff (signature)
    cyl(f"co{i}_ru", r=0.18, depth=0.08, segs=14, loc=(0.18, 0, 0.05),
        parent=c_e, mat_=M_CONDOR_WHITE)
    # Bald head (signature pink-orange)
    smooth_sphere(f"co{i}_h", r=0.10, segs=10, rings=8, loc=(0.30, 0, 0.10),
                  parent=c_e, mat_=M_CONDOR_HEAD)
    # Beak hooked
    cyl(f"co{i}_be", r=0.018, depth=0.10, segs=6, loc=(0.42, 0, 0.05),
        parent=c_e, mat_=M_FLAG_WHITE).rotation_euler = (0, math.radians(100), 0)
    # MASSIVE wings (signature condor 3m wingspan)
    wing_e_l = empty(f"co{i}_wl_e", (0, -0.10, 0), parent=c_e)
    wing_e_r = empty(f"co{i}_wr_e", (0, 0.10, 0), parent=c_e)
    # Main wing
    beveled_cube(f"co{i}_wl", (0.45, 1.30, 0.04), bevel_offset=0.01, loc=(0, -0.70, 0),
                 parent=wing_e_l, mat_=M_CONDOR_BLACK)
    beveled_cube(f"co{i}_wr", (0.45, 1.30, 0.04), bevel_offset=0.01, loc=(0, 0.70, 0),
                 parent=wing_e_r, mat_=M_CONDOR_BLACK)
    # White wing patches (signature)
    beveled_cube(f"co{i}_wpl", (0.30, 0.65, 0.05), bevel_offset=0.01, loc=(0, -0.70, 0.01),
                 parent=wing_e_l, mat_=M_CONDOR_WHITE)
    beveled_cube(f"co{i}_wpr", (0.30, 0.65, 0.05), bevel_offset=0.01, loc=(0, 0.70, 0.01),
                 parent=wing_e_r, mat_=M_CONDOR_WHITE)
    # Primary feathers spread (signature)
    for fi_w in range(6):
        fa = (fi_w / 6.0 - 0.5) * math.radians(50)
        beveled_cube(f"co{i}_pfl{fi_w}", (0.12, 0.45, 0.02), bevel_offset=0.005,
                     loc=(math.sin(fa)*0.20, -1.35 + math.cos(fa)*0.30, 0),
                     parent=wing_e_l, mat_=M_CONDOR_BLACK).rotation_euler = (0, 0, fa)
        beveled_cube(f"co{i}_pfr{fi_w}", (0.12, 0.45, 0.02), bevel_offset=0.005,
                     loc=(math.sin(fa)*0.20, 1.35 - math.cos(fa)*0.30, 0),
                     parent=wing_e_r, mat_=M_CONDOR_BLACK).rotation_euler = (0, 0, fa)
    # Tail fan
    for ti in range(5):
        ta = (ti - 2) * math.radians(12)
        beveled_cube(f"co{i}_t{ti}", (0.04, 0.30, 0.02), bevel_offset=0.005,
                     loc=(-0.35, math.sin(ta)*0.12, 0), parent=c_e,
                     mat_=M_CONDOR_BLACK).rotation_euler = (0, 0, ta)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    c_e["_base_x"] = px; c_e["_base_y"] = py; c_e["_base_z"] = pz
    c_e["_speed"] = random.uniform(0.3, 0.9)
    c_e["_radius"] = random.uniform(8, 20)
    c_e["_wl"] = wing_e_l; c_e["_wr"] = wing_e_r
    condors.append(c_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Guanacos sway/look
for g in guanacos:
    phase = g["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        g["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(3), 0,
                                     g["root"].rotation_euler.z)
        g["root"].keyframe_insert("rotation_euler", frame=f)
        g["neck"].rotation_euler = (0, math.radians(-30) + math.sin(t * 0.8 + phase) * math.radians(15),
                                     math.cos(t * 0.7 + phase) * math.radians(10))
        g["neck"].keyframe_insert("rotation_euler", frame=f)

# Hikers wave
for h in hikers:
    phase = h["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        h["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     h["root"].rotation_euler.z)
        h["root"].keyframe_insert("rotation_euler", frame=f)
        h["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(4), 0,
                                   math.cos(t * 0.8 + phase) * math.radians(15))
        h["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(15))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 snowflakes fall
for sf in flakes:
    phase = sf["_phase"]; drift = sf["_drift"]; fall = sf["_fall"]; swing = sf["_swing"]
    bx, bz = sf["_base_x"], sf["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.6 + t * drift
        z = bz - (t * fall) % 30
        sf.location = (x, sf.location.y, z)
        sf.rotation_euler = (t * 2.0 + phase, math.sin(t * 2.5 + phase) * math.radians(20), t * 1.5 + phase)
        sf.keyframe_insert("location", frame=f)
        sf.keyframe_insert("rotation_euler", frame=f)

# 400 condors soar (signature slow circular glides)
for c in condors:
    phase = c["_phase"]; speed = c["_speed"]; radius = c["_radius"]
    bx, by, bz_c = c["_base_x"], c["_base_y"], c["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * radius
        y = by + math.sin(t * speed + phase) * radius
        z = bz_c + math.sin(t * speed * 1.3 + phase) * 3
        c.location = (x, y, z)
        c.rotation_euler = (0, 0, math.atan2(math.cos(t * speed + phase),
                                              -math.sin(t * speed + phase)))
        c.keyframe_insert("location", frame=f)
        c.keyframe_insert("rotation_euler", frame=f)
        # Wing soar (slow, condors mostly glide)
        wing_a = math.sin(t * 1.5 + phase) * math.radians(8)
        c["_wl"].rotation_euler = (0, wing_a, 0)
        c["_wr"].rotation_euler = (0, -wing_a, 0)
        c["_wl"].keyframe_insert("rotation_euler", frame=f)
        c["_wr"].keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_patagonia_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_patagonia_torres_del_paine_glaciers] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Patagonia Torres del Paine: 3 iconic granite towers 42-50m with vertical striations + sharp peaks + snow caps signature + 8 background mountains + Perito Moreno glacier (jagged ice field + 15 blue ice cliffs + 8 crevasses + 6 ice towers) + turquoise lake with ice floes + 6 guanacos (long necks + pointy ears + 4 thin legs) + 4 hikers with backpacks + trekking poles + beanies + 2 orange A-frame tents + Chile flag with star + 25 cloud formations + 600 snowflakes + 400 Andean condors with massive wings + white neck ruff + bald orange head signature")
print("🦅 FIXES: 1 tundra ground + 600 snowflakes + 400 condors soaring signature 🦅")
