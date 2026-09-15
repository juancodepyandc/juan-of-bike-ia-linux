"""
proc_ouzbekistan_samarkand_silk_road.py — 296e procédural AuroraIA (161e qualité EXPERT REALISM)
Uzbekistan Samarkand Silk Road: 4 madrasas with turquoise domes + 3 minarets + 4 merchants + camel caravan + 600 silk + 400 bactrian camels
REALISM RULES: smooth_sphere stretched anatomy, bevel_segments=5+, no naked cubes
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB296)

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
    """REALISM: defaults bumped to bevel_offset=0.15 + bevel_segments=5 (smoother edges)"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size_xyz, verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:],
                    offset=bevel_offset, segments=bevel_segments,
                    profile=0.7, affect='EDGES')
    return make_obj(name, bm, loc, parent, mat_)

def smooth_sphere(name, r=1.0, segs=28, rings=20, loc=(0,0,0), parent=None, mat_=None, scale=(1,1,1)):
    """REALISM: higher polycount defaults 28/20 instead of 24/16"""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    if scale != (1,1,1):
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    return make_obj(name, bm, loc, parent, mat_)

def smooth_cone(name, r1, r2, depth, segs=22, loc=(0,0,0), parent=None, mat_=None):
    """REALISM: 22 segs default"""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    return make_obj(name, bm, loc, parent, mat_)

def cyl(name, r, depth, segs=20, loc=(0,0,0), parent=None, mat_=None):
    """REALISM: 20 segs default"""
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

# Sky desert
M_SKY = mat("sky", (0.85, 0.65, 0.45, 1.0), 0.0, 0.7, emission=(0.82,0.62,0.45), emission_strength=2.0)
M_SKY_LOW = mat("sky_l", (1.0, 0.78, 0.55, 1.0), 0.0, 0.7, emission=(0.95,0.78,0.55), emission_strength=1.7)
M_SUN = mat("sun", (1.0, 0.85, 0.45, 1.0), 0.0, 0.1, emission=(1.0,0.85,0.45), emission_strength=18.0)

# Ground sand
M_SAND = mat("s", (0.85, 0.65, 0.42, 1.0), 0.0, 0.85, emission=(0.82,0.62,0.42), emission_strength=0.3)
M_SAND_DARK = mat("sd", (0.62, 0.45, 0.28, 1.0), 0.0, 0.92)

# Madrasa signature turquoise tiles
M_TURQUOISE = mat("tq", (0.20, 0.78, 0.85, 1.0), 0.3, 0.30, emission=(0.20,0.75,0.82), emission_strength=1.5)
M_TURQUOISE_DARK = mat("tqd", (0.10, 0.55, 0.65, 1.0), 0.3, 0.40, emission=(0.10,0.55,0.62), emission_strength=1.2)
M_TURQUOISE_LIGHT = mat("tql", (0.55, 0.92, 0.95, 1.0), 0.3, 0.25, emission=(0.55,0.90,0.95), emission_strength=1.8)
M_TILE_BLUE = mat("tb", (0.20, 0.45, 0.85, 1.0), 0.3, 0.30, emission=(0.20,0.45,0.82), emission_strength=1.5)
M_TILE_GOLD = mat("tg", (0.95, 0.78, 0.20, 1.0), 0.8, 0.20, emission=(0.92,0.75,0.20), emission_strength=1.5)
M_TILE_WHITE = mat("tw", (0.92, 0.88, 0.78, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.78), emission_strength=0.5)

# Madrasa walls
M_WALL_TAN = mat("wt", (0.78, 0.65, 0.45, 1.0), 0.0, 0.75, emission=(0.75,0.62,0.45), emission_strength=0.4)
M_WALL_DARK = mat("wtd", (0.55, 0.42, 0.28, 1.0), 0.0, 0.85)

# Merchant clothing
M_SKIN = mat("sk", (0.82, 0.62, 0.42, 1.0), 0.0, 0.55, emission=(0.80,0.62,0.42), emission_strength=0.3)
M_HAIR = mat("hr", (0.18, 0.12, 0.08, 1.0), 0.0, 0.85)
M_BEARD = mat("br", (0.32, 0.22, 0.15, 1.0), 0.0, 0.85)
M_ROBE_BLUE = mat("rb", (0.22, 0.42, 0.78, 1.0), 0.0, 0.65, emission=(0.22,0.42,0.75), emission_strength=0.5)
M_ROBE_PURPLE = mat("rp", (0.55, 0.20, 0.65, 1.0), 0.0, 0.65, emission=(0.52,0.20,0.62), emission_strength=0.6)
M_ROBE_GREEN = mat("rg", (0.20, 0.55, 0.32, 1.0), 0.0, 0.65, emission=(0.20,0.52,0.32), emission_strength=0.5)
M_ROBE_RED = mat("rr", (0.78, 0.18, 0.22, 1.0), 0.0, 0.65, emission=(0.75,0.18,0.22), emission_strength=0.6)
ROBE_COLORS = [M_ROBE_BLUE, M_ROBE_PURPLE, M_ROBE_GREEN, M_ROBE_RED]
M_TURBAN_WHITE = mat("tw_t", (0.95, 0.92, 0.85, 1.0), 0.0, 0.55, emission=(0.92,0.88,0.82), emission_strength=0.5)
M_BELT_GOLD = mat("bg", (0.92, 0.72, 0.20, 1.0), 0.7, 0.30, emission=(0.88,0.70,0.20), emission_strength=0.8)

# Carpet (signature persian patterns)
M_CARPET_RED = mat("cpr", (0.62, 0.18, 0.18, 1.0), 0.0, 0.85, emission=(0.60,0.18,0.18), emission_strength=0.5)
M_CARPET_BLUE = mat("cpb", (0.18, 0.32, 0.65, 1.0), 0.0, 0.85, emission=(0.18,0.32,0.62), emission_strength=0.5)
M_CARPET_GOLD = mat("cpg", (0.85, 0.62, 0.20, 1.0), 0.0, 0.75, emission=(0.82,0.62,0.20), emission_strength=0.6)
CARPET_COLORS = [M_CARPET_RED, M_CARPET_BLUE, M_CARPET_GOLD]

# Camel bactrian (signature 2 humps)
M_CAMEL = mat("cm", (0.78, 0.58, 0.35, 1.0), 0.0, 0.85, emission=(0.75,0.55,0.35), emission_strength=0.3)
M_CAMEL_DARK = mat("cmd", (0.55, 0.38, 0.20, 1.0), 0.0, 0.92)
M_HORN = mat("h_h", (0.32, 0.22, 0.18, 1.0), 0.2, 0.55)

# Uzbekistan flag colors
M_FLAG_BLUE = mat("fb", (0.18, 0.42, 0.78, 1.0), 0.0, 0.45, emission=(0.18,0.42,0.75), emission_strength=1.0)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_FLAG_GREEN = mat("fg", (0.18, 0.62, 0.30, 1.0), 0.0, 0.45, emission=(0.18,0.60,0.30), emission_strength=1.0)
M_FLAG_RED = mat("fr", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=1.0)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Silk particles (signature flowing blue silk)
M_SILK_BLUE = mat("slb", (0.22, 0.55, 0.92, 1.0), 0.0, 0.20, emission=(0.22,0.55,0.92), emission_strength=2.5, alpha=0.78)
M_SILK_TURQ = mat("slt", (0.30, 0.78, 0.92, 1.0), 0.0, 0.20, emission=(0.30,0.75,0.92), emission_strength=2.8, alpha=0.78)
M_SILK_PURPLE = mat("slp", (0.55, 0.30, 0.92, 1.0), 0.0, 0.20, emission=(0.55,0.30,0.90), emission_strength=2.5, alpha=0.75)
SILK_COLORS = [M_SILK_BLUE, M_SILK_TURQ, M_SILK_PURPLE]

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=10, segs=24, rings=18, loc=(-40, 100, 35), mat_=M_SUN)
for sh in range(4):
    smooth_sphere(f"sun_h{sh}", r=10 + sh*1.2, segs=24, rings=18, loc=(-40, 100, 35), mat_=M_SUN)

# ============ ONE clean sand ground (NO SANDWICH) ============
ground = beveled_cube("ground", (280, 280, 0.5), bevel_offset=0.15, bevel_segments=5, loc=(0, 0, -0.25), mat_=M_SAND)
# Dune bumps - organic spheres only
for hi in range(200):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 130)
    smooth_sphere(f"dn{hi}", r=random.uniform(1.2, 2.8), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_SAND_DARK if hi % 3 == 0 else M_SAND, scale=(1.5, 1.4, 0.20))

# ============ REGISTAN MADRASAS (signature 3 madrasas with turquoise domes + portal iwans) ============
def make_madrasa(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Main rectangular building (smoothed via heavy bevel)
    beveled_cube(f"{name}_b", (14, 10, 8), bevel_offset=0.30, bevel_segments=6,
                 loc=(0, 0, 4), parent=base, mat_=M_WALL_TAN)
    # IWAN PORTAL (signature giant arched entrance)
    portal_e = empty(f"{name}_pt", (0, -5.05, 4.5), parent=base)
    # Arched frame (sphere half scaled)
    smooth_sphere(f"{name}_pt_a", r=3, segs=22, rings=18, loc=(0, 0, 0),
                  parent=portal_e, mat_=M_TURQUOISE, scale=(1.2, 0.20, 1.4))
    # Inner darker shadow
    smooth_sphere(f"{name}_pt_i", r=2.4, segs=20, rings=16, loc=(0, 0.10, 0),
                  parent=portal_e, mat_=M_WALL_DARK, scale=(1.0, 0.18, 1.2))
    # Decorative tile band around portal (signature blue/gold tilework)
    for ti_b in range(20):
        tia = (ti_b / 20.0) * math.pi
        beveled_cube(f"{name}_pt_t{ti_b}", (0.40, 0.06, 0.40), bevel_offset=0.08, bevel_segments=4,
                     loc=(math.cos(tia)*3.3, -0.10, math.sin(tia)*3.3),
                     parent=portal_e, mat_=M_TILE_BLUE if ti_b % 2 else M_TILE_GOLD)
    # 2 SMALLER ARCHED WINDOWS flanking portal
    for side in (-1, 1):
        side_arch_e = empty(f"{name}_sa{side}_e", (side*5.5, -5.05, 4.5), parent=base)
        smooth_sphere(f"{name}_sa{side}", r=1.5, segs=18, rings=14, loc=(0, 0, 0),
                      parent=side_arch_e, mat_=M_TURQUOISE_DARK, scale=(1.0, 0.20, 1.3))
        smooth_sphere(f"{name}_sa{side}_i", r=1.2, segs=16, rings=12, loc=(0, 0.08, 0),
                      parent=side_arch_e, mat_=M_WALL_DARK, scale=(0.9, 0.15, 1.1))
    # Tile pattern on facade (signature geometric)
    for fi in range(30):
        fx = random.uniform(-6.5, 6.5); fz = random.uniform(0.5, 7.5)
        # Avoid portal area
        if abs(fx) < 4 and 2 < fz < 7:
            continue
        col = random.choice([M_TILE_BLUE, M_TILE_GOLD, M_TURQUOISE, M_TURQUOISE_LIGHT])
        smooth_sphere(f"{name}_fct{fi}", r=0.20, segs=12, rings=10,
                      loc=(fx, -5.10, fz), parent=base, mat_=col, scale=(1, 0.3, 1))
    # MAIN DOME (signature massive turquoise onion bulb)
    dome_e = empty(f"{name}_d", (0, 0, 8.5), parent=base)
    # Drum (cylinder base)
    cyl(f"{name}_d_dr", r=3.5, depth=2, segs=24, loc=(0, 0, 1), parent=dome_e, mat_=M_WALL_TAN)
    # Decorative tile band on drum
    for di in range(24):
        dia = (di / 24.0) * math.pi * 2
        beveled_cube(f"{name}_d_dt{di}", (0.40, 0.20, 0.50), bevel_offset=0.06, bevel_segments=4,
                     loc=(math.cos(dia)*3.6, math.sin(dia)*3.6, 1),
                     parent=dome_e, mat_=M_TILE_BLUE if di % 2 else M_TILE_GOLD).rotation_euler = (0, 0, dia)
    # Onion dome shape (using stacked spheres for organic curve)
    for di in range(10):
        di_t = di / 9.0
        # Signature curve: pinch + bulb + taper
        if di_t < 0.3:
            r_d = 3.5 * (1 + math.sin(di_t * math.pi * 1.8) * 0.15)
        elif di_t < 0.7:
            r_d = 3.5 * (1 + math.sin(0.3 * math.pi * 1.8) * 0.15 - (di_t - 0.3) / 0.4 * 0.20)
        else:
            r_d = 3.5 * 0.95 * (1 - (di_t - 0.7) / 0.3 * 0.95)
        smooth_sphere(f"{name}_d_o{di}", r=max(0.1, r_d), segs=24, rings=18,
                      loc=(0, 0, 2 + di_t * 5.5), parent=dome_e,
                      mat_=M_TURQUOISE, scale=(1, 1, 0.7))
    # Gold finial pinnacle (signature)
    smooth_cone(f"{name}_d_p", r1=0.30, r2=0.05, depth=1.2, segs=14, loc=(0, 0, 8.5),
                parent=dome_e, mat_=M_TILE_GOLD)
    smooth_sphere(f"{name}_d_pb", r=0.30, segs=14, rings=10, loc=(0, 0, 8),
                  parent=dome_e, mat_=M_TILE_GOLD)
    return base

# 3 madrasas Registan arrangement
madrasa_pos = [(-22, 35, math.radians(15)), (22, 35, math.radians(-15)), (0, 50, math.radians(0))]
for i, (mx, my, fac) in enumerate(madrasa_pos):
    make_madrasa(f"mad{i}", (mx, my, 0), facing=fac)

# ============ 3 MINARETS (signature tall slender towers with bands) ============
def make_minaret(name, loc, height=20, base_r=1.2):
    base = empty(name, loc)
    # Tapered shaft (cylinder stacks for organic taper)
    n_seg = int(height / 1.5)
    for si in range(n_seg):
        sz = si * (height / n_seg)
        sr = base_r * (1 - si / n_seg * 0.30)
        cyl(f"{name}_s{si}", r=sr, depth=height/n_seg + 0.05, segs=22,
            loc=(0, 0, sz + (height/n_seg)/2), parent=base,
            mat_=M_WALL_TAN if si % 3 != 0 else M_TURQUOISE)
    # Decorative tile bands every 4 segments
    for bi in range(int(n_seg / 4)):
        bz = bi * (height / int(n_seg/4)) + 2
        for di in range(20):
            dia = (di / 20.0) * math.pi * 2
            beveled_cube(f"{name}_bt{bi}_{di}", (0.20, 0.20, 0.30), bevel_offset=0.05, bevel_segments=4,
                         loc=(math.cos(dia)*base_r*0.92, math.sin(dia)*base_r*0.92, bz),
                         parent=base, mat_=M_TILE_BLUE if (bi+di) % 2 else M_TILE_GOLD).rotation_euler = (0, 0, dia)
    # Balcony (signature wider ring near top)
    balcony_e = empty(f"{name}_ba", (0, 0, height - 3), parent=base)
    cyl(f"{name}_ba_p", r=base_r * 1.3, depth=0.40, segs=22, loc=(0, 0, 0), parent=balcony_e, mat_=M_TURQUOISE)
    # Balcony railings (carved openings)
    for ri in range(16):
        ria = (ri / 16.0) * math.pi * 2
        cyl(f"{name}_ba_r{ri}", r=0.08, depth=0.50, segs=8,
            loc=(math.cos(ria)*base_r*1.32, math.sin(ria)*base_r*1.32, 0.15),
            parent=balcony_e, mat_=M_TILE_GOLD)
    # Onion top dome
    smooth_sphere(f"{name}_top", r=base_r * 0.8, segs=20, rings=16,
                  loc=(0, 0, height + 0.2), parent=base, mat_=M_TURQUOISE, scale=(1, 1, 1.3))
    # Pinnacle
    smooth_cone(f"{name}_p", r1=0.20, r2=0.03, depth=1.0, segs=12, loc=(0, 0, height + 1.5),
                parent=base, mat_=M_TILE_GOLD)
    return base

for i, (mx, my, mh) in enumerate([(-28, 28, 24), (28, 28, 24), (0, 60, 28)]):
    make_minaret(f"min{i}", (mx, my, 0), height=mh)

# ============ 4 BACTRIAN CAMELS (signature 2 humps) - all smooth_sphere anatomy ============
def make_bactrian_camel(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body - stretched sphere
    smooth_sphere(f"{name}_bo", r=0.85, segs=18, rings=14, loc=(0, 0, 2.0),
                  parent=base, mat_=M_CAMEL, scale=(1.7, 0.85, 0.85))
    # TWO HUMPS (signature bactrian)
    smooth_sphere(f"{name}_hp1", r=0.50, segs=18, rings=14, loc=(0.4, 0, 2.55),
                  parent=base, mat_=M_CAMEL_DARK, scale=(0.9, 0.85, 1.15))
    smooth_sphere(f"{name}_hp2", r=0.50, segs=18, rings=14, loc=(-0.4, 0, 2.55),
                  parent=base, mat_=M_CAMEL_DARK, scale=(0.9, 0.85, 1.15))
    # Belly lighter
    smooth_sphere(f"{name}_be", r=0.80, segs=16, rings=12, loc=(0, 0, 1.70),
                  parent=base, mat_=M_CAMEL, scale=(1.6, 0.85, 0.50))
    # Long curved neck (cylinders + sphere joints, no naked cylinder ends)
    neck_e = empty(f"{name}_ne", (0.95, 0, 2.40), parent=base)
    neck_e.rotation_euler = (0, math.radians(-35), 0)
    for ni in range(6):
        ni_t = ni / 6.0
        cyl(f"{name}_n{ni}", r=0.20 - ni*0.012, depth=0.22, segs=14,
            loc=(0, 0, ni*0.22 + 0.15), parent=neck_e, mat_=M_CAMEL)
        # Joint sphere (avoid naked cylinder ends)
        smooth_sphere(f"{name}_nj{ni}", r=0.20 - ni*0.012, segs=12, rings=10,
                      loc=(0, 0, ni*0.22 + 0.05), parent=neck_e, mat_=M_CAMEL)
    # Head
    head_c_e = empty(f"{name}_he", (0, 0, 1.55), parent=neck_e)
    smooth_sphere(f"{name}_h", r=0.22, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_c_e, mat_=M_CAMEL, scale=(1.4, 0.85, 0.85))
    # Snout
    smooth_sphere(f"{name}_sn", r=0.15, segs=12, rings=10, loc=(0.20, 0, -0.10),
                  parent=head_c_e, mat_=M_CAMEL_DARK, scale=(1.3, 0.85, 0.85))
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.08, segs=10, rings=8,
                      loc=(-0.05, side*0.13, 0.18), parent=head_c_e, mat_=M_CAMEL, scale=(0.4, 1.0, 1.4))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.04, loc=(0.07, side*0.14, 0.05),
                      parent=head_c_e, mat_=M_EYE)
    # Eyelashes (signature long camel lashes)
    for side in (-1, 1):
        for li in range(3):
            cyl(f"{name}_el{side}_{li}", r=0.005, depth=0.05, segs=4,
                loc=(0.09, side*0.14, 0.10 + li*0.01), parent=head_c_e,
                mat_=M_CAMEL_DARK).rotation_euler = (0, math.radians(40), 0)
    # 4 long legs with joint spheres
    for li, (lx_c, ly_c) in enumerate([(0.65, 0.30), (0.65, -0.30), (-0.65, 0.30), (-0.65, -0.30)]):
        leg_e = empty(f"{name}_le{li}", (lx_c, ly_c, 1.50), parent=base)
        # Upper segment
        cyl(f"{name}_ul{li}", r=0.13, depth=0.65, segs=14, loc=(0, 0, -0.32),
            parent=leg_e, mat_=M_CAMEL)
        # KNEE JOINT (sphere, not naked cylinder end)
        smooth_sphere(f"{name}_kn{li}", r=0.14, segs=14, rings=10, loc=(0, 0, -0.65),
                      parent=leg_e, mat_=M_CAMEL)
        # Lower segment
        cyl(f"{name}_ll{li}", r=0.11, depth=0.60, segs=14, loc=(0, 0, -0.95),
            parent=leg_e, mat_=M_CAMEL)
        # Foot (signature wide pad)
        smooth_sphere(f"{name}_ft{li}", r=0.15, segs=12, rings=8, loc=(0, 0, -1.28),
                      parent=leg_e, mat_=M_CAMEL_DARK, scale=(1.1, 1.3, 0.4))
    # Tail with tuft
    tail_e = empty(f"{name}_te", (-1.0, 0, 1.95), parent=base)
    tail_e.rotation_euler = (0, math.radians(100), 0)
    for ti in range(4):
        cyl(f"{name}_t{ti}", r=0.07 - ti*0.008, depth=0.12, segs=10,
            loc=(0, 0, ti*0.12), parent=tail_e, mat_=M_CAMEL)
    smooth_sphere(f"{name}_tt", r=0.10, segs=10, rings=8, loc=(0, 0, 0.55),
                  parent=tail_e, mat_=M_CAMEL_DARK)
    # Decorative saddle blanket (signature persian carpet)
    saddle_e = empty(f"{name}_sa", (0, 0, 2.95), parent=base)
    beveled_cube(f"{name}_sa_b", (1.4, 1.05, 0.10), bevel_offset=0.08, bevel_segments=4,
                 loc=(0, 0, 0), parent=saddle_e, mat_=random.choice(CARPET_COLORS))
    # Tassels hanging (signature decorative)
    for ti in range(8):
        ta = (ti / 8.0) * math.pi * 2
        cyl(f"{name}_ts{ti}", r=0.015, depth=0.20, segs=6,
            loc=(math.cos(ta)*0.65, math.sin(ta)*0.45, -0.10),
            parent=saddle_e, mat_=M_TILE_GOLD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "neck": neck_e, "he": head_c_e}

camels = []
for i, (cx, cy, fac) in enumerate([(-15, -20, math.radians(0)), (-5, -25, math.radians(15)),
                                     (8, -22, math.radians(-10)), (20, -18, math.radians(20))]):
    c = make_bactrian_camel(f"cm{i}", (cx, cy, 0), facing=fac)
    camels.append(c)

# ============ 4 MERCHANTS (signature turbans + flowing robes - smooth anatomy) ============
def make_merchant(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    robe_col = random.choice(ROBE_COLORS)
    # Body - stretched sphere not cube
    smooth_sphere(f"{name}_bo", r=0.35, segs=18, rings=14, loc=(0, 0, 1.30),
                  parent=base, mat_=robe_col, scale=(1, 0.85, 1.5))
    # Long flowing robe (cone shape)
    smooth_cone(f"{name}_ro", r1=0.32, r2=0.55, depth=1.4, segs=18, loc=(0, 0, 0.70),
                parent=base, mat_=robe_col)
    # Belt gold sash
    cyl(f"{name}_be", r=0.36, depth=0.12, segs=18, loc=(0, 0, 1.10),
        parent=base, mat_=M_BELT_GOLD)
    # Arms with shoulder/elbow joints
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.32, 0, 1.65), parent=base)
        sh.rotation_euler = (math.radians(-70), 0, math.radians(side*20))
        # Shoulder joint sphere
        smooth_sphere(f"{name}_sh{side_idx}", r=0.10, segs=12, rings=10, loc=(0, 0, 0),
                      parent=sh, mat_=robe_col)
        # Upper arm
        cyl(f"{name}_ua{side_idx}", r=0.08, depth=0.40, segs=14, loc=(0, 0, -0.20),
            parent=sh, mat_=robe_col)
        # Elbow joint
        smooth_sphere(f"{name}_el{side_idx}", r=0.085, segs=12, rings=10, loc=(0, 0, -0.40),
                      parent=sh, mat_=robe_col)
        # Forearm (skin showing - sleeves rolled)
        cyl(f"{name}_fa{side_idx}", r=0.07, depth=0.35, segs=14, loc=(0, 0, -0.60),
            parent=sh, mat_=M_SKIN)
        # Hand
        smooth_sphere(f"{name}_hd{side_idx}", r=0.07, segs=12, rings=10, loc=(0, 0, -0.80),
                      parent=sh, mat_=M_SKIN)
    # CARPET held in hands (signature merchant displaying wares)
    carpet_e = empty(f"{name}_cr", (0, -0.50, 1.0), parent=base)
    beveled_cube(f"{name}_cr_b", (1.2, 0.04, 0.85), bevel_offset=0.08, bevel_segments=4,
                 loc=(0, 0, 0), parent=carpet_e, mat_=random.choice(CARPET_COLORS))
    # Carpet edge fringe
    for fri in range(12):
        cyl(f"{name}_cr_f{fri}", r=0.012, depth=0.10, segs=4,
            loc=(-0.55 + fri*0.10, -0.04, -0.45), parent=carpet_e, mat_=M_TILE_GOLD)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 1.92), parent=base)
    smooth_sphere(f"{name}_h", r=0.16, segs=20, rings=16, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN)
    # Beard (signature)
    for bi in range(20):
        ba = random.uniform(-math.pi*0.4, math.pi*0.4)
        beard_len = random.uniform(0.12, 0.22)
        for bsi in range(int(beard_len * 6)):
            smooth_sphere(f"{name}_bd{bi}_{bsi}", r=0.018, segs=8, rings=6,
                          loc=(math.sin(ba)*0.10, -0.10, -0.10 - bsi*0.05),
                          parent=head_m_e, mat_=M_BEARD)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.13, 0.03),
                      parent=head_m_e, mat_=M_EYE)
    # TURBAN (signature wrapped white)
    turban_e = empty(f"{name}_tb", (0, 0, 0.18), parent=head_m_e)
    # Wrapped layers (sphere stack for organic wrap)
    for tli in range(5):
        tla = tli * math.radians(50)
        smooth_sphere(f"{name}_tb{tli}", r=0.22 - tli*0.005, segs=18, rings=14,
                      loc=(math.cos(tla)*0.02, math.sin(tla)*0.02, tli*0.05),
                      parent=turban_e, mat_=M_TURBAN_WHITE, scale=(1, 1, 0.6))
    # Decorative jewel on turban (signature)
    smooth_sphere(f"{name}_tj", r=0.06, segs=12, rings=10, loc=(0, -0.18, 0.20),
                  parent=turban_e, mat_=M_TILE_GOLD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_m_e}

merchants = []
for i, (mx, my, fac) in enumerate([(-12, 8, math.radians(20)), (-2, 12, math.radians(0)),
                                     (8, 12, math.radians(-15)), (18, 8, math.radians(-30))]):
    m = make_merchant(f"mr{i}", (mx, my, 0), facing=fac)
    merchants.append(m)

# ============ UZBEKISTAN FLAG (signature blue/white/green stripes with crescent) ============
flag_e = empty("flag", (-55, -40, 0))
cyl("fl_p", r=0.10, depth=12, segs=12, loc=(0, 0, 6), parent=flag_e, mat_=M_WALL_DARK)
# 3 horizontal stripes with red separators
beveled_cube("fl_b", (4, 0.05, 0.85), bevel_offset=0.08, bevel_segments=4, loc=(2, 0, 11.45), parent=flag_e, mat_=M_FLAG_BLUE)
beveled_cube("fl_r1", (4, 0.05, 0.10), bevel_offset=0.03, bevel_segments=3, loc=(2, 0, 10.95), parent=flag_e, mat_=M_FLAG_RED)
beveled_cube("fl_w", (4, 0.05, 0.75), bevel_offset=0.08, bevel_segments=4, loc=(2, 0, 10.50), parent=flag_e, mat_=M_FLAG_WHITE)
beveled_cube("fl_r2", (4, 0.05, 0.10), bevel_offset=0.03, bevel_segments=3, loc=(2, 0, 10.05), parent=flag_e, mat_=M_FLAG_RED)
beveled_cube("fl_g", (4, 0.05, 0.85), bevel_offset=0.08, bevel_segments=4, loc=(2, 0, 9.55), parent=flag_e, mat_=M_FLAG_GREEN)
# Crescent moon (signature)
crescent_e = empty("fl_cr", (0.6, -0.06, 11.45), parent=flag_e)
smooth_sphere("fl_cr_o", r=0.30, segs=18, rings=14, loc=(0, 0, 0),
              parent=crescent_e, mat_=M_FLAG_WHITE)
smooth_sphere("fl_cr_i", r=0.26, segs=18, rings=14, loc=(0.10, -0.04, 0),
              parent=crescent_e, mat_=M_FLAG_BLUE)
# 12 stars (signature)
for si in range(12):
    sx_st = 1.2 + (si % 6) * 0.30
    sz_st = 11.55 - (si // 6) * 0.30
    smooth_sphere(f"fl_st{si}", r=0.05, segs=10, rings=8, loc=(sx_st, -0.07, sz_st),
                  parent=flag_e, mat_=M_FLAG_WHITE)
flag_e["_phase"] = 0

# ============================================================
# 600 PERSIAN BLUE SILK + 400 WALKING BACTRIAN CAMELS (signature)
# ============================================================
silks = []
for i in range(600):
    px = random.uniform(-110, 110)
    py = random.uniform(-100, 100)
    pz = random.uniform(2, 28)
    s_col = random.choice(SILK_COLORS)
    s_e = empty(f"sl{i}", (px, py, pz))
    # Flowing silk ribbon (multi-segment for organic flow)
    for ssi in range(6):
        ssa = (ssi / 6.0) * math.pi
        beveled_cube(f"sl{i}_s{ssi}", (0.10, 0.05, 0.20), bevel_offset=0.04, bevel_segments=3,
                     loc=(math.sin(ssa)*0.15, 0, ssi*0.10 - 0.25),
                     parent=s_e, mat_=s_col).rotation_euler = (0, ssa*0.5, 0)
    s_e["_phase"] = random.uniform(0, math.pi*2)
    s_e["_base_x"] = px; s_e["_base_y"] = py; s_e["_base_z"] = pz
    s_e["_amp_x"] = random.uniform(0.8, 2.0)
    s_e["_amp_y"] = random.uniform(0.8, 2.0)
    s_e["_amp_z"] = random.uniform(0.5, 1.2)
    s_e["_speed"] = random.uniform(0.4, 1.0)
    silks.append(s_e)

# 400 mini bactrian camels walking caravan
mini_camels = []
for i in range(400):
    px = random.uniform(-110, 110)
    py = random.uniform(-100, 100)
    pz = 1.0
    mc_e = empty(f"mc{i}", (px, py, pz))
    # Body
    smooth_sphere(f"mc{i}_bo", r=0.20, segs=12, rings=10, loc=(0, 0, 0),
                  parent=mc_e, mat_=M_CAMEL, scale=(1.6, 0.85, 0.85))
    # 2 humps
    smooth_sphere(f"mc{i}_h1", r=0.10, segs=10, rings=8, loc=(0.10, 0, 0.13),
                  parent=mc_e, mat_=M_CAMEL_DARK, scale=(0.9, 0.85, 1.1))
    smooth_sphere(f"mc{i}_h2", r=0.10, segs=10, rings=8, loc=(-0.10, 0, 0.13),
                  parent=mc_e, mat_=M_CAMEL_DARK, scale=(0.9, 0.85, 1.1))
    # Neck
    cyl(f"mc{i}_n", r=0.05, depth=0.25, segs=10, loc=(0.20, 0, 0.18),
        parent=mc_e, mat_=M_CAMEL).rotation_euler = (0, math.radians(50), 0)
    # Head
    smooth_sphere(f"mc{i}_h", r=0.08, segs=10, rings=8, loc=(0.32, 0, 0.30),
                  parent=mc_e, mat_=M_CAMEL, scale=(1.3, 0.85, 0.85))
    # Legs
    for side in (-1, 1):
        for fr in (-1, 1):
            cyl(f"mc{i}_l{side}_{fr}", r=0.03, depth=0.30, segs=8,
                loc=(fr*0.15, side*0.12, -0.15), parent=mc_e, mat_=M_CAMEL)
    mc_e["_phase"] = random.uniform(0, math.pi*2)
    mc_e["_base_x"] = px; mc_e["_base_y"] = py
    mc_e["_speed"] = random.uniform(0.3, 0.6)
    mc_e["_direction"] = random.uniform(0, math.pi*2)
    mini_camels.append(mc_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Camels sway + neck movement
for c in camels:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        c["root"].location.z = abs(math.sin(t * 1.5 + phase)) * 0.10
        c["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3), 0,
                                     c["root"].rotation_euler.z)
        c["root"].keyframe_insert("location", frame=f)
        c["root"].keyframe_insert("rotation_euler", frame=f)
        c["neck"].rotation_euler = (0, math.radians(-35) + math.sin(t * 1.2 + phase) * math.radians(10), 0)
        c["neck"].keyframe_insert("rotation_euler", frame=f)
        c["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(6), 0,
                                   math.cos(t * 1.0 + phase) * math.radians(15))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Merchants sway
for m in merchants:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(4), 0,
                                   math.cos(t * 0.8 + phase) * math.radians(12))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(10))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 silks flow multi-axis prominently
for s in silks:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase) + t * 0.4
        s.location = (x, y, z)
        s.rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(30),
                             math.cos(t * 1.5 + phase) * math.radians(25),
                             t * 0.8 + phase)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("rotation_euler", frame=f)

# 400 mini camels walk in caravan patterns
for mc in mini_camels:
    phase = mc["_phase"]; speed = mc["_speed"]; direction = mc["_direction"]
    bx, by = mc["_base_x"], mc["_base_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.cos(direction) * t * speed * 2
        y = by + math.sin(direction) * t * speed * 2
        z = 1.0 + abs(math.sin(t * 3.0 + phase)) * 0.10
        mc.location = (x, y, z)
        mc.rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(3), 0, direction)
        mc.keyframe_insert("location", frame=f)
        mc.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_uzbekistan_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_ouzbekistan_samarkand_silk_road] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Samarkand REALISM EXPERT: 1 ground unique sable + 3 madrasas Registan with signature massive turquoise onion domes (10-sphere organic curve) + iwan portal arches + tile decoration + 3 tapered minarets with balconies + 4 bactrian camels (2 humps + saddle blankets + tassels + organic sphere anatomy + knee/foot joints) + 4 merchants (turbans wrapped sphere stack + flowing robe cones + carpets held + beards) + Uzbekistan flag with crescent + 12 stars + 600 silk ribbons multi-axis flowing + 400 mini bactrian camels walking caravan")
print("🐪 REALISM RULES APPLIED: bevel_offset>=0.15 bevel_segments>=5 + smooth_sphere stretched anatomy + joint spheres on limbs + onion domes via sphere stacks 🐪")
