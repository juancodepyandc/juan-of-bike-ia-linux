"""
proc_iguazu_falls_rainforest_toucans.py — 280e MILESTONE procédural AuroraIA (145e qualité)
Iguazu Falls rainforest: 14 parallel waterfalls Garganta del Diablo + basalt cliffs + Iguazu river + 4 jaguars + 4 capybaras + 6 macaws + lianas + 1000 mist droplets + 500 toucans (DOUBLE MILESTONE)
FIXES : 1 ground rock river + DOUBLE signature mist + toucans
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB280)

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

# Sky tropical rainforest
M_SKY = mat("sky", (0.55, 0.78, 0.92, 1.0), 0.0, 0.7, emission=(0.55,0.75,0.90), emission_strength=1.7)
M_SKY_LOW = mat("sky_l", (0.85, 0.92, 0.95, 1.0), 0.0, 0.7, emission=(0.85,0.90,0.92), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.92, 0.65, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.65), emission_strength=15.0)
M_RAINBOW = mat("rb", (0.55, 0.85, 0.95, 1.0), 0.0, 0.10, emission=(0.55,0.85,0.95), emission_strength=3.0, alpha=0.50)
M_RAINBOW_RED = mat("rbr", (1.0, 0.30, 0.30, 1.0), 0.0, 0.10, emission=(0.95,0.30,0.30), emission_strength=3.5, alpha=0.45)
M_RAINBOW_YELLOW = mat("rby", (1.0, 0.92, 0.30, 1.0), 0.0, 0.10, emission=(0.95,0.88,0.30), emission_strength=3.5, alpha=0.45)
M_RAINBOW_GREEN = mat("rbg", (0.30, 0.92, 0.30, 1.0), 0.0, 0.10, emission=(0.30,0.88,0.30), emission_strength=3.5, alpha=0.45)
M_RAINBOW_PURPLE = mat("rbp", (0.75, 0.30, 0.95, 1.0), 0.0, 0.10, emission=(0.72,0.30,0.92), emission_strength=3.5, alpha=0.45)

# Rock river ground
M_ROCK_WET = mat("rw", (0.32, 0.30, 0.28, 1.0), 0.3, 0.45, emission=(0.30,0.28,0.28), emission_strength=0.2)
M_ROCK_DRY = mat("rd", (0.55, 0.50, 0.42, 1.0), 0.0, 0.85, emission=(0.52,0.50,0.42), emission_strength=0.3)
M_BASALT = mat("ba", (0.22, 0.20, 0.20, 1.0), 0.0, 0.92)
M_BASALT_LIGHT = mat("bal", (0.42, 0.40, 0.38, 1.0), 0.0, 0.85)

# Water (signature)
M_WATER = mat("wt", (0.55, 0.78, 0.85, 1.0), 0.2, 0.10, emission=(0.55,0.75,0.82), emission_strength=2.0, alpha=0.78)
M_WATER_WHITE = mat("wtw", (0.92, 0.95, 0.98, 1.0), 0.0, 0.10, emission=(0.90,0.92,0.95), emission_strength=2.5, alpha=0.75)
M_WATER_DEEP = mat("wtd", (0.30, 0.55, 0.75, 1.0), 0.2, 0.15, alpha=0.85)
M_FOAM = mat("fm", (0.95, 0.95, 0.95, 1.0), 0.0, 0.20, emission=(0.92,0.92,0.92), emission_strength=2.0, alpha=0.70)

# Rainforest vegetation
M_LEAF_GREEN = mat("lg", (0.20, 0.55, 0.25, 1.0), 0.0, 0.55, emission=(0.18,0.52,0.25), emission_strength=0.5)
M_LEAF_DARK = mat("ld", (0.10, 0.32, 0.15, 1.0), 0.0, 0.65)
M_LEAF_BRIGHT = mat("lb", (0.30, 0.78, 0.32, 1.0), 0.0, 0.55, emission=(0.28,0.75,0.32), emission_strength=0.6)
M_TRUNK = mat("tk", (0.42, 0.28, 0.18, 1.0), 0.0, 0.85, emission=(0.40,0.28,0.18), emission_strength=0.2)
M_LIANA = mat("ln", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)

# Jaguar (signature spotted)
M_JAGUAR_YELLOW = mat("jy", (0.85, 0.68, 0.30, 1.0), 0.0, 0.55, emission=(0.82,0.65,0.30), emission_strength=0.3)
M_JAGUAR_SPOT = mat("js", (0.18, 0.12, 0.08, 1.0), 0.0, 0.55)
M_JAGUAR_BELLY = mat("jb", (0.92, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.82,0.62), emission_strength=0.4)

# Capybara
M_CAPYBARA_BROWN = mat("cb", (0.55, 0.32, 0.18, 1.0), 0.0, 0.75, emission=(0.52,0.30,0.18), emission_strength=0.3)
M_CAPYBARA_DARK = mat("cbd", (0.32, 0.18, 0.10, 1.0), 0.0, 0.85)

# Macaw (signature scarlet)
M_MACAW_RED = mat("mr", (0.92, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.90,0.18,0.20), emission_strength=1.5)
M_MACAW_BLUE = mat("mb", (0.20, 0.45, 0.85, 1.0), 0.0, 0.45, emission=(0.20,0.42,0.82), emission_strength=1.2)
M_MACAW_YELLOW = mat("my", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.20), emission_strength=1.5)
M_MACAW_BEAK = mat("mbk", (0.92, 0.88, 0.78, 1.0), 0.0, 0.65)

# Toucan (signature huge orange beak)
M_TOUCAN_BLACK = mat("tb", (0.10, 0.10, 0.12, 1.0), 0.0, 0.55, emission=(0.10,0.10,0.12), emission_strength=0.3)
M_TOUCAN_WHITE = mat("tw", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.92,0.88,0.82), emission_strength=0.4)
M_TOUCAN_BEAK = mat("tbk", (1.0, 0.55, 0.18, 1.0), 0.0, 0.35, emission=(0.95,0.55,0.18), emission_strength=2.5)
M_TOUCAN_BEAK_TIP = mat("tbt", (0.85, 0.30, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.30,0.18), emission_strength=2.0)
M_TOUCAN_EYE = mat("tem", (0.20, 0.55, 0.85, 1.0), 0.0, 0.10, emission=(0.20,0.55,0.85), emission_strength=2.0)
M_TOUCAN_THROAT = mat("tth", (1.0, 0.85, 0.30, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.30), emission_strength=1.0)

# Eye/teeth
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_FANG = mat("fa", (0.95, 0.92, 0.85, 1.0), 0.0, 0.30)

# Mist droplet
M_MIST = mat("mi", (0.92, 0.95, 0.98, 1.0), 0.0, 0.10, emission=(0.90,0.92,0.95), emission_strength=2.5, alpha=0.45)
M_MIST_BLUE = mat("mib", (0.78, 0.92, 0.95, 1.0), 0.0, 0.10, emission=(0.78,0.92,0.95), emission_strength=2.2, alpha=0.40)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-40, 80, 45), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-40, 80, 45), mat_=M_SUN)

# RAINBOW arc over falls (signature)
rainbow_e = empty("rainbow", (0, 30, 18))
for ri in range(7):
    r_color = [M_RAINBOW_PURPLE, M_RAINBOW, M_RAINBOW_GREEN, M_RAINBOW_YELLOW, M_RAINBOW_RED, M_RAINBOW_RED, M_RAINBOW_YELLOW][ri]
    rr = 35 - ri * 1.2
    for ai in range(20):
        aang = math.pi * 0.3 + (ai / 20.0) * math.pi * 0.4
        beveled_cube(f"rb{ri}_{ai}", (1.0, 0.20, 1.0), bevel_offset=0.10,
                     loc=(math.cos(aang)*rr, 0, math.sin(aang)*rr),
                     parent=rainbow_e, mat_=r_color)

# ============ ONE clean rock + river ground ============
ground = beveled_cube("ground", (300, 300, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_ROCK_DRY)
# Wet rocks scattered
for ri in range(250):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 140)
    smooth_sphere(f"rk{ri}", r=random.uniform(0.5, 1.3), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.12),
                  mat_=M_ROCK_WET if ri % 3 == 0 else M_BASALT_LIGHT, scale=(1.4, 1.3, 0.25))

# ============ IGUAZU RIVER (signature) ============
river_e = empty("river", (0, 60, 0))
# Wide river upstream
beveled_cube("rv", (140, 50, 0.25), bevel_offset=0.10, loc=(0, 0, 0.20),
             parent=river_e, mat_=M_WATER)
beveled_cube("rv_d", (135, 48, 0.20), bevel_offset=0.08, loc=(0, 0, 0.30),
             parent=river_e, mat_=M_WATER_DEEP)
# River current foam streaks
for fi in range(30):
    fx = random.uniform(-65, 65); fy = random.uniform(-22, 22)
    cyl(f"rv_f{fi}", r=random.uniform(0.4, 0.8), depth=0.05, segs=14,
        loc=(fx, fy, 0.32), parent=river_e, mat_=M_FOAM)

# ============ 14 PARALLEL WATERFALLS (Garganta del Diablo signature) ============
# Cliff edge
cliff_e = empty("cliff", (0, 25, 0))
# Main basalt cliff wall (horseshoe shape signature)
for ci in range(14):
    ca = -math.pi * 0.7 + (ci / 14.0) * math.pi * 1.4
    cx_c = math.cos(ca) * 50
    cy_c = math.sin(ca) * 35 + 25
    # Basalt cliff column
    cliff_h = random.uniform(20, 25)
    cliff_col_e = empty(f"cl{ci}_e", (cx_c, cy_c, 0), parent=cliff_e)
    for li in range(int(cliff_h / 2)):
        smooth_sphere(f"cl{ci}_{li}", r=random.uniform(2.5, 3.2), segs=12, rings=10,
                      loc=(random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3),
                           li*2 + 1),
                      parent=cliff_col_e, mat_=M_BASALT if li % 2 == 0 else M_BASALT_LIGHT,
                      scale=(1.2, 1.1, 1.0))
    # Basalt columns (signature hexagonal)
    for hc in range(8):
        hca = (hc / 8.0) * math.pi * 2
        beveled_cube(f"cl{ci}_h{hc}", (0.40, 0.10, cliff_h * 0.85), bevel_offset=0.04,
                     loc=(math.cos(hca)*2.5, math.sin(hca)*2.5, cliff_h/2),
                     parent=cliff_col_e, mat_=M_BASALT)
    # WATERFALL DOWN (signature)
    wf_e = empty(f"wf{ci}_e", (0, 0, cliff_h - 0.5), parent=cliff_col_e)
    # Top of fall (water sheet)
    cyl(f"wf{ci}_t", r=2.5, depth=0.5, segs=14, loc=(0, 0, 0),
        parent=wf_e, mat_=M_WATER)
    # Cascade column (multi-segment falling water)
    n_segs = int(cliff_h / 1.5)
    for ws in range(n_segs):
        wz_w = -ws * 1.5
        wr_w = 2.3 + random.uniform(-0.3, 0.3)
        ws_col = M_WATER_WHITE if ws < 5 or ws > n_segs - 4 else M_WATER
        smooth_sphere(f"wf{ci}_w{ws}", r=wr_w * 0.8, segs=14, rings=10,
                      loc=(random.uniform(-0.4, 0.4), random.uniform(-0.2, 0.2), wz_w),
                      parent=wf_e, mat_=ws_col, scale=(1.1, 1.0, 1.5))
    # Splash at bottom (signature)
    splash_e = empty(f"wf{ci}_sp", (0, 0, -cliff_h + 0.5), parent=wf_e)
    for si in range(8):
        sa = random.uniform(0, math.pi*2)
        sr = random.uniform(0, 4)
        smooth_sphere(f"wf{ci}_spl{si}", r=random.uniform(0.8, 1.5), segs=12, rings=8,
                      loc=(math.cos(sa)*sr, math.sin(sa)*sr, random.uniform(0, 2)),
                      parent=splash_e, mat_=M_FOAM)
    cliff_col_e["_phase"] = random.uniform(0, math.pi*2)

# ============ RAINFOREST TREES dense ============
def make_jungle_tree(name, loc, scale=1.0):
    base = empty(name, loc)
    # Trunk
    h = random.uniform(8, 14)
    n_seg = int(h / 1.5)
    for ti in range(n_seg):
        tz = ti * 1.5
        cyl(f"{name}_t{ti}", r=0.35 - ti*0.015, depth=1.6, segs=10,
            loc=(random.uniform(-0.05, 0.05), random.uniform(-0.05, 0.05), tz + 0.75),
            parent=base, mat_=M_TRUNK)
    # Canopy
    canopy_e = empty(f"{name}_ce", (0, 0, h), parent=base)
    for ci in range(12):
        ca = random.uniform(0, math.pi*2); cr = random.uniform(0, 3)
        leaf_col = random.choice([M_LEAF_GREEN, M_LEAF_DARK, M_LEAF_BRIGHT])
        smooth_sphere(f"{name}_c{ci}", r=random.uniform(1.3, 2.5), segs=14, rings=10,
                      loc=(math.cos(ca)*cr, math.sin(ca)*cr, random.uniform(-0.5, 1.5)),
                      parent=canopy_e, mat_=leaf_col)
    # Lianas (signature hanging vines)
    for li in range(6):
        la_l = random.uniform(0, math.pi*2)
        for lsi in range(int(h * 0.7)):
            cyl(f"{name}_l{li}_{lsi}", r=0.04, depth=0.20, segs=6,
                loc=(math.cos(la_l)*0.30 + random.uniform(-0.10, 0.10),
                     math.sin(la_l)*0.30 + random.uniform(-0.10, 0.10),
                     h - lsi*0.40),
                parent=base, mat_=M_LIANA)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "canopy": canopy_e}

trees = []
# Dense jungle around the falls
for i in range(20):
    angle = random.uniform(0, math.pi*2)
    rad = random.uniform(70, 130)
    tx = math.cos(angle) * rad
    ty = math.sin(angle) * rad
    if ty < 80:  # Don't put trees in the water area
        trees.append(make_jungle_tree(f"tr{i}", (tx, ty, 0)))

# ============ 4 JAGUARS (signature spotted) ============
def make_jaguar(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body (signature stalking pose)
    smooth_sphere(f"{name}_bo", r=0.45, segs=14, rings=12, loc=(0, 0, 0.80),
                  parent=base, mat_=M_JAGUAR_YELLOW, scale=(1.8, 0.85, 0.85))
    # Belly cream
    smooth_sphere(f"{name}_be", r=0.40, segs=12, rings=10, loc=(0, 0, 0.65),
                  parent=base, mat_=M_JAGUAR_BELLY, scale=(1.6, 0.85, 0.55))
    # Black rosette spots (signature)
    for si in range(20):
        sa = random.uniform(0, math.pi*2)
        sc = math.cos(sa) * 0.45
        sd = math.sin(sa) * 0.30
        sz_s = random.uniform(0.65, 0.95)
        smooth_sphere(f"{name}_sp{si}", r=0.06, segs=10, rings=6,
                      loc=(sc, sd, sz_s), parent=base, mat_=M_JAGUAR_SPOT)
    # Long body extended
    smooth_sphere(f"{name}_bo2", r=0.40, segs=14, rings=12, loc=(0.60, 0, 0.80),
                  parent=base, mat_=M_JAGUAR_YELLOW, scale=(1.2, 0.85, 0.85))
    # Spots on extended body
    for si2 in range(8):
        smooth_sphere(f"{name}_sp2{si2}", r=0.05, segs=10, rings=6,
                      loc=(0.60 + random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3),
                           random.uniform(0.65, 0.95)),
                      parent=base, mat_=M_JAGUAR_SPOT)
    # Head
    head_j_e = empty(f"{name}_he", (1.10, 0, 0.85), parent=base)
    smooth_sphere(f"{name}_h", r=0.30, segs=14, rings=12, loc=(0, 0, 0),
                  parent=head_j_e, mat_=M_JAGUAR_YELLOW, scale=(1.3, 0.85, 0.85))
    # Snout
    smooth_sphere(f"{name}_sn", r=0.15, segs=10, rings=8, loc=(0.20, 0, -0.10),
                  parent=head_j_e, mat_=M_JAGUAR_YELLOW)
    # Eyes (signature predatory)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.05, loc=(0.06, side*0.13, 0.05),
                      parent=head_j_e, mat_=M_EYE_INTENSE if False else M_TOUCAN_THROAT)
        smooth_sphere(f"{name}_ep{side}", r=0.025, loc=(0.10, side*0.13, 0.05),
                      parent=head_j_e, mat_=M_EYE)
    # Ears (signature rounded)
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.08, segs=10, rings=8,
                      loc=(-0.08, side*0.18, 0.20), parent=head_j_e, mat_=M_JAGUAR_YELLOW)
        # Spot on ear
        smooth_sphere(f"{name}_er{side}_s", r=0.04, loc=(-0.10, side*0.18, 0.20),
                      parent=head_j_e, mat_=M_JAGUAR_SPOT)
    # Fangs (signature)
    for side in (-1, 1):
        cyl(f"{name}_fa{side}", r=0.018, depth=0.08, segs=6,
            loc=(0.25, side*0.05, -0.18), parent=head_j_e, mat_=M_FANG)
    # 4 legs (powerful)
    for li, (lx_j, ly_j) in enumerate([(0.45, 0.25), (0.45, -0.25), (-0.45, 0.25), (-0.45, -0.25)]):
        leg_e = empty(f"{name}_le{li}", (lx_j, ly_j, 0.55), parent=base)
        cyl(f"{name}_ul{li}", r=0.10, depth=0.30, segs=10, loc=(0, 0, -0.15),
            parent=leg_e, mat_=M_JAGUAR_YELLOW)
        cyl(f"{name}_ll{li}", r=0.09, depth=0.30, segs=10, loc=(0, 0, -0.40),
            parent=leg_e, mat_=M_JAGUAR_YELLOW)
        # Paw
        smooth_sphere(f"{name}_pw{li}", r=0.12, segs=12, rings=8,
                      loc=(0, 0, -0.55), parent=leg_e, mat_=M_JAGUAR_YELLOW, scale=(1, 1, 0.6))
    # Long tail (signature)
    tail_e = empty(f"{name}_te", (-0.60, 0, 0.85), parent=base)
    for ti in range(10):
        ta = (ti / 10.0) * math.pi * 0.4
        tx_t = -ti * 0.20
        tz_t = math.sin(ta) * 0.3 - 0.05
        cyl(f"{name}_t{ti}", r=0.10 - ti*0.005, depth=0.18, segs=10,
            loc=(tx_t, 0, tz_t), parent=tail_e, mat_=M_JAGUAR_YELLOW).rotation_euler = (0, math.radians(90), 0)
        if ti % 2 == 0:
            smooth_sphere(f"{name}_ts{ti}", r=0.05, loc=(tx_t, 0, tz_t),
                          parent=tail_e, mat_=M_JAGUAR_SPOT)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_j_e}

jaguars = []
jaguar_pos = [(-35, -30, math.radians(45)), (35, -35, math.radians(-30)),
               (-25, -45, math.radians(120)), (25, -45, math.radians(-150))]
for i, (jx, jy, fac) in enumerate(jaguar_pos):
    j = make_jaguar(f"jg{i}", (jx, jy, 0), facing=fac)
    jaguars.append(j)

# ============ 4 CAPYBARAS (signature) ============
def make_capybara(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body barrel-shaped (signature)
    smooth_sphere(f"{name}_bo", r=0.45, segs=14, rings=12, loc=(0, 0, 0.60),
                  parent=base, mat_=M_CAPYBARA_BROWN, scale=(1.6, 0.95, 0.85))
    # Head (signature blocky)
    head_c_e = empty(f"{name}_he", (0.75, 0, 0.70), parent=base)
    beveled_cube(f"{name}_h", (0.35, 0.40, 0.30), bevel_offset=0.08, loc=(0, 0, 0),
                 parent=head_c_e, mat_=M_CAPYBARA_BROWN)
    # Snout
    smooth_sphere(f"{name}_sn", r=0.10, segs=10, rings=8, loc=(0.18, 0, -0.05),
                  parent=head_c_e, mat_=M_CAPYBARA_DARK)
    # Beady eyes (signature small)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(0.10, side*0.13, 0.10),
                      parent=head_c_e, mat_=M_EYE)
    # Small ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.05, segs=8, rings=6,
                      loc=(-0.10, side*0.15, 0.16), parent=head_c_e, mat_=M_CAPYBARA_DARK)
    # 4 short stubby legs
    for li, (lx_c, ly_c) in enumerate([(0.30, 0.25), (0.30, -0.25), (-0.30, 0.25), (-0.30, -0.25)]):
        cyl(f"{name}_l{li}", r=0.10, depth=0.30, segs=10,
            loc=(lx_c, ly_c, 0.25), parent=base, mat_=M_CAPYBARA_BROWN)
        # Hoof-like foot
        beveled_cube(f"{name}_f{li}", (0.10, 0.14, 0.06), bevel_offset=0.02,
                     loc=(lx_c, ly_c, 0.05), parent=base, mat_=M_CAPYBARA_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_c_e}

capybaras = []
capy_pos = [(-12, 0, math.radians(20)), (-5, -5, math.radians(0)),
             (5, -5, math.radians(-15)), (12, 2, math.radians(45))]
for i, (cx_c, cy_c, fac) in enumerate(capy_pos):
    c = make_capybara(f"cp{i}", (cx_c, cy_c, 0), facing=fac)
    capybaras.append(c)

# ============ 6 SCARLET MACAWS (perched in trees) ============
def make_macaw(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body (red signature)
    smooth_sphere(f"{name}_bo", r=0.18, segs=14, rings=10, loc=(0, 0, 0),
                  parent=base, mat_=M_MACAW_RED, scale=(1.5, 0.85, 0.95))
    # Blue wing tops (signature)
    for side in (-1, 1):
        beveled_cube(f"{name}_w{side}", (0.15, 0.25, 0.05), bevel_offset=0.02,
                     loc=(-0.05, side*0.15, 0.04), parent=base, mat_=M_MACAW_BLUE)
        # Yellow wing band (signature)
        beveled_cube(f"{name}_wy{side}", (0.10, 0.15, 0.05), bevel_offset=0.02,
                     loc=(-0.05, side*0.15, 0.06), parent=base, mat_=M_MACAW_YELLOW)
    # Long tail (signature)
    for ti in range(5):
        beveled_cube(f"{name}_t{ti}", (0.04 - ti*0.003, 0.05, 0.30), bevel_offset=0.005,
                     loc=(-0.25 - ti*0.05, (ti-2)*0.03, 0),
                     parent=base, mat_=M_MACAW_RED if ti % 2 else M_MACAW_BLUE)
    # Head
    head_m_e = empty(f"{name}_he", (0.20, 0, 0.10), parent=base)
    smooth_sphere(f"{name}_h", r=0.10, segs=12, rings=10, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_MACAW_RED)
    # Beak (hooked signature)
    cyl(f"{name}_bk_t", r=0.04, depth=0.10, segs=8, loc=(0.10, 0, -0.02),
        parent=head_m_e, mat_=M_MACAW_BEAK).rotation_euler = (0, math.radians(110), 0)
    cyl(f"{name}_bk_b", r=0.025, depth=0.06, segs=8, loc=(0.12, 0, -0.06),
        parent=head_m_e, mat_=M_MACAW_BEAK).rotation_euler = (0, math.radians(140), 0)
    # White face patch
    smooth_sphere(f"{name}_fa", r=0.07, segs=10, rings=8, loc=(0.04, 0, 0),
                  parent=head_m_e, mat_=M_TOUCAN_WHITE)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(0.04, side*0.05, 0.02),
                      parent=head_m_e, mat_=M_EYE)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.02, depth=0.10, segs=6,
            loc=(0, side*0.05, -0.12), parent=base, mat_=M_MACAW_BEAK)
    return base

# Place macaws perched on trees
macaw_pos = [(-75, 75, 10), (75, 80, 9), (-90, 90, 11),
              (90, 85, 10), (-50, 95, 12), (50, 95, 11)]
for i, (mx, my, mz) in enumerate(macaw_pos):
    make_macaw(f"mw{i}", (mx, my, mz), facing=random.uniform(0, math.pi*2))

# ============================================================
# ⭐ 1000 MIST DROPLETS + 500 TOUCANS (DOUBLE MILESTONE PARTICLES)
# ============================================================
mist_drops = []
for i in range(1000):
    # Concentrate near falls
    region = i % 4
    if region < 3:
        # Around falls
        angle_m = random.uniform(-math.pi*0.7, math.pi*0.7)
        rad_m = random.uniform(30, 60)
        px = math.cos(angle_m) * rad_m
        py = math.sin(angle_m) * 30 + 25
        pz = random.uniform(2, 28)
    else:
        # Scattered around
        px = random.uniform(-100, 100)
        py = random.uniform(-50, 80)
        pz = random.uniform(2, 35)
    m_col = M_MIST if i % 2 == 0 else M_MIST_BLUE
    md = smooth_sphere(f"md{i}", r=random.uniform(0.20, 0.45), segs=10, rings=8,
                       loc=(px, py, pz), mat_=m_col, scale=(1.4, 1.4, 0.6))
    md["_phase"] = random.uniform(0, math.pi*2)
    md["_base_x"] = px; md["_base_y"] = py; md["_base_z"] = pz
    md["_rise"] = random.uniform(1.5, 4.0)
    md["_speed"] = random.uniform(0.5, 1.3)
    md["_drift_x"] = random.uniform(-0.4, 0.4)
    md["_drift_y"] = random.uniform(-0.4, 0.4)
    mist_drops.append(md)

# 500 toucans flying
toucans = []
for i in range(500):
    px = random.uniform(-130, 130)
    py = random.uniform(-100, 130)
    pz = random.uniform(15, 55)
    t_e = empty(f"tc{i}", (px, py, pz))
    # Body (black signature)
    smooth_sphere(f"tc{i}_bo", r=0.18, segs=12, rings=10, loc=(0, 0, 0),
                  parent=t_e, mat_=M_TOUCAN_BLACK, scale=(1.4, 0.85, 0.85))
    # White throat patch (signature)
    smooth_sphere(f"tc{i}_th", r=0.12, segs=10, rings=8, loc=(0.10, 0, -0.04),
                  parent=t_e, mat_=M_TOUCAN_WHITE, scale=(1.2, 0.85, 0.75))
    # Yellow throat band (signature)
    smooth_sphere(f"tc{i}_ty", r=0.10, segs=10, rings=8, loc=(0.12, 0, 0.02),
                  parent=t_e, mat_=M_TOUCAN_THROAT, scale=(1.0, 0.85, 0.55))
    # Head
    smooth_sphere(f"tc{i}_h", r=0.10, segs=10, rings=8, loc=(0.22, 0, 0.05),
                  parent=t_e, mat_=M_TOUCAN_BLACK)
    # HUGE ORANGE BEAK (signature toucan)
    beak_e = empty(f"tc{i}_be", (0.30, 0, 0.05), parent=t_e)
    # Upper beak (curved large)
    for bki in range(6):
        bkx = bki * 0.08
        bky = math.sin(bki * 0.3) * 0.02
        bkr = 0.06 - bki * 0.008
        smooth_sphere(f"tc{i}_bk{bki}", r=bkr, segs=10, rings=8,
                      loc=(bkx, bky, 0), parent=beak_e, mat_=M_TOUCAN_BEAK,
                      scale=(1.0, 0.7, 0.85))
    # Beak tip darker
    smooth_sphere(f"tc{i}_bkt", r=0.025, loc=(0.50, 0.10, 0),
                  parent=beak_e, mat_=M_TOUCAN_BEAK_TIP)
    # Eye ring (signature blue)
    smooth_sphere(f"tc{i}_er", r=0.035, loc=(0.18, 0.06, 0.06),
                  parent=t_e, mat_=M_TOUCAN_EYE)
    smooth_sphere(f"tc{i}_ep", r=0.018, loc=(0.20, 0.07, 0.06),
                  parent=t_e, mat_=M_EYE)
    # Wings
    wing_e_l = empty(f"tc{i}_wl_e", (0, -0.10, 0), parent=t_e)
    wing_e_r = empty(f"tc{i}_wr_e", (0, 0.10, 0), parent=t_e)
    beveled_cube(f"tc{i}_wl", (0.15, 0.32, 0.025), bevel_offset=0.008, loc=(0, -0.16, 0),
                 parent=wing_e_l, mat_=M_TOUCAN_BLACK)
    beveled_cube(f"tc{i}_wr", (0.15, 0.32, 0.025), bevel_offset=0.008, loc=(0, 0.16, 0),
                 parent=wing_e_r, mat_=M_TOUCAN_BLACK)
    # Tail
    beveled_cube(f"tc{i}_t", (0.15, 0.10, 0.03), bevel_offset=0.005,
                 loc=(-0.20, 0, 0), parent=t_e, mat_=M_TOUCAN_BLACK)
    # Red undertail (signature)
    beveled_cube(f"tc{i}_tu", (0.10, 0.06, 0.025), bevel_offset=0.005,
                 loc=(-0.20, 0, -0.04), parent=t_e, mat_=M_MACAW_RED)
    t_e["_phase"] = random.uniform(0, math.pi*2)
    t_e["_base_x"] = px; t_e["_base_y"] = py; t_e["_base_z"] = pz
    t_e["_speed"] = random.uniform(0.5, 1.3)
    t_e["_radius"] = random.uniform(5, 15)
    t_e["_wl"] = wing_e_l; t_e["_wr"] = wing_e_r
    toucans.append(t_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Jaguars sway/stalk
for j in jaguars:
    phase = j["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        j["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     j["root"].rotation_euler.z)
        j["root"].keyframe_insert("rotation_euler", frame=f)
        j["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                   math.cos(t * 1.0 + phase) * math.radians(20))
        j["he"].keyframe_insert("rotation_euler", frame=f)

# Capybaras chill
for c in capybaras:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        c["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3), 0,
                                   math.cos(t * 0.5 + phase) * math.radians(8))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Trees sway
for tr in trees:
    phase = tr["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        tr["canopy"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(4),
                                        math.cos(t * 0.8 + phase) * math.radians(4), 0)
        tr["canopy"].keyframe_insert("rotation_euler", frame=f)

# 1000 mist droplets rise
for md in mist_drops:
    phase = md["_phase"]; speed = md["_speed"]; rise = md["_rise"]
    bx, by, bz_m = md["_base_x"], md["_base_y"], md["_base_z"]
    dx, dy = md["_drift_x"], md["_drift_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + dx * t + math.sin(t * speed + phase) * 0.4
        y = by + dy * t + math.cos(t * speed * 0.9 + phase) * 0.4
        z = bz_m + (t * rise) % 20
        md.location = (x, y, z)
        sc_m = 1 + math.sin(t * 1.5 + phase) * 0.30 + t * 0.06
        md.scale = (sc_m * 1.4, sc_m * 1.4, sc_m * 0.6)
        md.keyframe_insert("location", frame=f)
        md.keyframe_insert("scale", frame=f)

# 500 toucans fly with wing flap
for tc in toucans:
    phase = tc["_phase"]; speed = tc["_speed"]; radius = tc["_radius"]
    bx, by, bz_t = tc["_base_x"], tc["_base_y"], tc["_base_z"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * radius
        y = by + math.sin(t * speed + phase) * radius
        z = bz_t + math.sin(t * speed * 1.4 + phase) * 2.5
        tc.location = (x, y, z)
        tc.rotation_euler = (0, 0, math.atan2(math.cos(t * speed + phase),
                                                -math.sin(t * speed + phase)))
        tc.keyframe_insert("location", frame=f)
        tc.keyframe_insert("rotation_euler", frame=f)
        wing_a = math.sin(t * 16.0 + phase) * math.radians(40)
        tc["_wl"].rotation_euler = (0, wing_a, 0)
        tc["_wr"].rotation_euler = (0, -wing_a, 0)
        tc["_wl"].keyframe_insert("rotation_euler", frame=f)
        tc["_wr"].keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_iguazu_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_iguazu_falls_rainforest_toucans] DONE → {out_glb} ({size_mb:.2f} MB)")
print("⭐ 280e MILESTONE 145e qualité ⭐")
print("Iguazu Falls Garganta del Diablo: 14 parallel waterfalls (signature horseshoe arrangement) with basalt cliff columns + cascade water columns + splash basins + Iguazu river upstream with foam streaks + 20 rainforest trees with canopies + lianas hanging + 4 jaguars (yellow with rosette spots signature + cream belly + fangs + spotted tail) + 4 capybaras (barrel bodies + blocky heads + small ears + stubby legs) + 6 scarlet macaws perched (red body + blue/yellow wing bands + long tail + hooked beak + white face patch) + rainbow arc (signature 5 colors) + 1000 MIST DROPLETS + 500 TOUCANS DOUBLE MILESTONE (black body + huge orange beak + yellow throat + white throat patch + blue eye ring + red undertail signature)")
print("⭐ DOUBLE PARTICLES MILESTONE: 1 rock river ground + 1000 mist droplets + 500 toucans signature Iguazu ⭐")
