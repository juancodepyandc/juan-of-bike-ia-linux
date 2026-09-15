"""
proc_vietnamese_halong_bay_junks.py — 269e procédural AuroraIA (134e qualité)
Vietnam Halong Bay junks karst: 12 limestone karst islands + 6 red-sail junks + 4 conical hat fishermen + 3 floating villages + cormorants + 600 mist wisps + 400 kingfisher birds
FIXES : 1 ground turquoise sea + signature mist + birds
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB269)

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

# Misty sky Halong
M_SKY = mat("sky", (0.78, 0.85, 0.90, 1.0), 0.0, 0.7, emission=(0.78,0.85,0.90), emission_strength=1.8)
M_SKY_LOW = mat("sky_l", (0.85, 0.82, 0.78, 1.0), 0.0, 0.7, emission=(0.85,0.82,0.78), emission_strength=1.5)
M_SUN_MISTY = mat("sun", (0.95, 0.92, 0.85, 1.0), 0.0, 0.1, emission=(0.95,0.92,0.85), emission_strength=12.0)

# Turquoise sea (signature)
M_SEA = mat("sea", (0.30, 0.78, 0.78, 1.0), 0.2, 0.20, emission=(0.30,0.75,0.75), emission_strength=1.5, alpha=0.75)
M_SEA_DEEP = mat("sea_d", (0.20, 0.55, 0.65, 1.0), 0.2, 0.25, alpha=0.85)
M_SEA_RIPPLE = mat("sea_r", (0.55, 0.85, 0.85, 1.0), 0.2, 0.18, emission=(0.55,0.82,0.85), emission_strength=2.0, alpha=0.65)

# Karst limestone (signature)
M_KARST = mat("k", (0.45, 0.50, 0.45, 1.0), 0.0, 0.85, emission=(0.42,0.48,0.42), emission_strength=0.2)
M_KARST_DARK = mat("kd", (0.32, 0.38, 0.35, 1.0), 0.0, 0.92)
M_KARST_LIGHT = mat("kl", (0.62, 0.65, 0.55, 1.0), 0.0, 0.75)
M_VEGETATION = mat("vg", (0.18, 0.45, 0.20, 1.0), 0.0, 0.65, emission=(0.18,0.42,0.20), emission_strength=0.4)
M_VEG_DARK = mat("vgd", (0.10, 0.32, 0.15, 1.0), 0.0, 0.75)
M_TREE = mat("tr", (0.25, 0.55, 0.25, 1.0), 0.0, 0.55, emission=(0.22,0.52,0.25), emission_strength=0.5)
M_TRUNK = mat("trk", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)

# Junk boat
M_JUNK_HULL = mat("jh", (0.55, 0.32, 0.15, 1.0), 0.0, 0.55, emission=(0.50,0.30,0.15), emission_strength=0.4)
M_JUNK_DARK = mat("jhd", (0.28, 0.16, 0.08, 1.0), 0.0, 0.75)
M_JUNK_TRIM = mat("jt", (0.92, 0.78, 0.30, 1.0), 0.3, 0.30, emission=(0.88,0.75,0.30), emission_strength=0.8)
# Red sails (signature)
M_SAIL_RED = mat("sr", (0.85, 0.18, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.18), emission_strength=0.7)
M_SAIL_RED_DARK = mat("srd", (0.55, 0.10, 0.10, 1.0), 0.0, 0.55)
M_ROPE = mat("rp", (0.65, 0.55, 0.30, 1.0), 0.0, 0.85)

# Fisherman
M_SKIN_VN = mat("sv", (0.85, 0.70, 0.55, 1.0), 0.0, 0.55, emission=(0.82,0.70,0.55), emission_strength=0.3)
M_CLOTH_BROWN = mat("cb", (0.55, 0.35, 0.18, 1.0), 0.0, 0.65)
M_CLOTH_BLUE = mat("cbl", (0.22, 0.42, 0.62, 1.0), 0.0, 0.65, emission=(0.22,0.42,0.60), emission_strength=0.3)
M_CONICAL = mat("co", (0.85, 0.72, 0.45, 1.0), 0.0, 0.75, emission=(0.82,0.70,0.45), emission_strength=0.4)
M_CONICAL_DARK = mat("cod", (0.55, 0.40, 0.20, 1.0), 0.0, 0.85)
M_HAIR_BLACK = mat("hb", (0.10, 0.06, 0.05, 1.0), 0.0, 0.85)
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Floating village houses
M_HOUSE_WOOD = mat("hw", (0.65, 0.42, 0.20, 1.0), 0.0, 0.65, emission=(0.62,0.40,0.20), emission_strength=0.3)
M_HOUSE_RED = mat("hr", (0.78, 0.30, 0.25, 1.0), 0.0, 0.55, emission=(0.75,0.30,0.25), emission_strength=0.6)
M_HOUSE_BLUE = mat("hbl2", (0.35, 0.55, 0.75, 1.0), 0.0, 0.55, emission=(0.35,0.55,0.72), emission_strength=0.5)
M_THATCH = mat("th", (0.55, 0.42, 0.18, 1.0), 0.0, 0.85)
HOUSE_COLORS = [M_HOUSE_WOOD, M_HOUSE_RED, M_HOUSE_BLUE]

# Fishing net
M_NET = mat("nt", (0.85, 0.82, 0.75, 1.0), 0.0, 0.75, alpha=0.65)

# Cormorant bird
M_CORMORANT = mat("cm", (0.08, 0.08, 0.10, 1.0), 0.0, 0.55, emission=(0.08,0.08,0.10), emission_strength=0.2)

# Mist wisp (signature)
M_MIST = mat("mi", (0.95, 0.95, 0.95, 1.0), 0.0, 0.95, emission=(0.95,0.95,0.95), emission_strength=1.5, alpha=0.30)
M_MIST_BLUE = mat("mib", (0.85, 0.92, 0.95, 1.0), 0.0, 0.95, emission=(0.85,0.92,0.95), emission_strength=1.3, alpha=0.28)

# Kingfisher bird (signature - colorful)
M_KING_BLUE = mat("kb", (0.20, 0.55, 0.95, 1.0), 0.0, 0.45, emission=(0.20,0.55,0.92), emission_strength=2.0)
M_KING_ORANGE = mat("ko", (1.0, 0.55, 0.18, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.18), emission_strength=2.0)
M_KING_BELLY = mat("kbe", (1.0, 0.75, 0.35, 1.0), 0.0, 0.45, emission=(0.95,0.72,0.35), emission_strength=1.5)

# Vietnam flag
M_FLAG_VN_RED = mat("fvr", (0.85, 0.10, 0.18, 1.0), 0.0, 0.45, emission=(0.82,0.10,0.18), emission_strength=1.0)
M_FLAG_VN_STAR = mat("fvs", (1.0, 0.92, 0.20, 1.0), 0.0, 0.30, emission=(0.95,0.88,0.20), emission_strength=3.0)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=240, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
# Sun behind mist
sun = smooth_sphere("sun", r=10, segs=24, rings=18, loc=(0, 100, 25), mat_=M_SUN_MISTY)
for sh in range(4):
    smooth_sphere(f"sun_h{sh}", r=10 + sh*1.5, segs=24, rings=18, loc=(0, 100, 25), mat_=M_SUN_MISTY)

# ============ ONE clean turquoise sea ground ============
ground = beveled_cube("ground", (220, 220, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_SEA_DEEP)
# Sea surface
beveled_cube("sea_s", (220, 220, 0.20), bevel_offset=0.08, loc=(0, 0, 0.15), mat_=M_SEA)
# Sea ripples
for ri in range(100):
    a = random.uniform(0, math.pi*2); rad = random.uniform(5, 100)
    cyl(f"rp{ri}", r=random.uniform(0.8, 1.5), depth=0.04, segs=14,
        loc=(rad*math.cos(a), rad*math.sin(a), 0.30), mat_=M_SEA_RIPPLE)

# ============ 12 KARST ISLANDS (signature) ============
def make_karst(name, loc, height, base_radius):
    base = empty(name, loc)
    # Irregular cylindrical pillar with multiple sections
    n_sections = max(4, int(height / 3))
    for si in range(n_sections):
        sz = si * (height / n_sections)
        sr = base_radius * (1 - si / n_sections * 0.4) + random.uniform(-0.3, 0.3)
        smooth_sphere(f"{name}_s{si}", r=sr, segs=14, rings=10,
                      loc=(random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5), sz + height/n_sections/2),
                      parent=base, mat_=M_KARST if si % 2 else M_KARST_DARK,
                      scale=(1.2, 1.1, 1.0))
    # Cap
    smooth_cone(f"{name}_cap", r1=base_radius * 0.4, r2=base_radius * 0.15, depth=2, segs=12,
                loc=(0, 0, height + 0.5), parent=base, mat_=M_KARST_LIGHT)
    # Vegetation green on top
    for vi in range(8):
        va = random.uniform(0, math.pi*2); vr = random.uniform(0.3, base_radius * 0.5)
        smooth_sphere(f"{name}_v{vi}", r=random.uniform(0.4, 0.8), segs=10, rings=8,
                      loc=(math.cos(va)*vr, math.sin(va)*vr, height - 0.3),
                      parent=base, mat_=M_VEGETATION, scale=(1.2, 1.1, 0.8))
    # Trees scattered
    for ti in range(5):
        ta = random.uniform(0, math.pi*2); tr = random.uniform(0.5, base_radius * 0.7)
        tx = math.cos(ta) * tr; ty = math.sin(ta) * tr
        cyl(f"{name}_t{ti}", r=0.08, depth=1.2, segs=8,
            loc=(tx, ty, height + 0.6), parent=base, mat_=M_TRUNK)
        smooth_sphere(f"{name}_tc{ti}", r=0.55, segs=12, rings=8,
                      loc=(tx, ty, height + 1.5), parent=base, mat_=M_TREE)
    # Cliff striations (vertical lines)
    for ci in range(12):
        ca = (ci / 12.0) * math.pi * 2
        cyl(f"{name}_cl{ci}", r=0.08, depth=height * 0.9, segs=6,
            loc=(math.cos(ca)*base_radius*0.95, math.sin(ca)*base_radius*0.95, height/2),
            parent=base, mat_=M_KARST_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

karst_pos = [
    (-40, 40, 18, 5), (-20, 50, 22, 6), (10, 55, 14, 4), (35, 45, 20, 5),
    (-55, 20, 16, 5), (50, 25, 19, 6), (-45, 0, 24, 7), (45, -5, 17, 5),
    (-30, -25, 21, 6), (5, -30, 15, 4), (30, -35, 23, 6), (-10, -50, 18, 5)
]
karsts = []
for i, (kx, ky, kh, kr) in enumerate(karst_pos):
    k = make_karst(f"karst{i}", (kx, ky, 0), kh, kr)
    karsts.append(k)

# ============ 6 JUNK BOATS with RED SAILS (signature) ============
def make_junk(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Hull (curved like junk)
    smooth_cone(f"{name}_h", r1=0.65, r2=0.35, depth=6, segs=16, loc=(0, 0, 0),
                parent=base, mat_=M_JUNK_HULL).rotation_euler = (0, math.radians(90), 0)
    # Hull plank top
    beveled_cube(f"{name}_pt", (6.5, 1.4, 0.25), bevel_offset=0.06, loc=(0, 0, 0.15),
                 parent=base, mat_=M_JUNK_DARK)
    # Upturned bow and stern (signature junk shape)
    bow_e = empty(f"{name}_bw", (3.5, 0, 0.4), parent=base)
    bow_e.rotation_euler = (0, math.radians(-20), 0)
    beveled_cube(f"{name}_bp", (0.8, 1.4, 0.4), bevel_offset=0.06, loc=(0, 0, 0),
                 parent=bow_e, mat_=M_JUNK_HULL)
    stern_e = empty(f"{name}_st", (-3.5, 0, 0.4), parent=base)
    stern_e.rotation_euler = (0, math.radians(20), 0)
    beveled_cube(f"{name}_sp", (0.8, 1.4, 0.4), bevel_offset=0.06, loc=(0, 0, 0),
                 parent=stern_e, mat_=M_JUNK_HULL)
    # Gold trim (signature)
    beveled_cube(f"{name}_tr_l", (6.0, 0.06, 0.08), bevel_offset=0.01, loc=(0, 0.70, 0.40),
                 parent=base, mat_=M_JUNK_TRIM)
    beveled_cube(f"{name}_tr_r", (6.0, 0.06, 0.08), bevel_offset=0.01, loc=(0, -0.70, 0.40),
                 parent=base, mat_=M_JUNK_TRIM)
    # Cabin
    beveled_cube(f"{name}_ca", (2.5, 1.3, 0.85), bevel_offset=0.10, loc=(-0.5, 0, 0.80),
                 parent=base, mat_=M_JUNK_DARK)
    # Cabin roof curved (signature pagoda style)
    cabin_roof_e = empty(f"{name}_cre", (-0.5, 0, 1.30), parent=base)
    smooth_cone(f"{name}_cr", r1=1.7, r2=0.4, depth=0.6, segs=4, loc=(0, 0, 0),
                parent=cabin_roof_e, mat_=M_SAIL_RED).rotation_euler = (0, 0, math.radians(45))
    # 3 MASTS with RED FAN SAILS (signature)
    sails_data = []
    for mi, (mx, mh) in enumerate([(-2.0, 4.5), (0.5, 5.5), (2.5, 4)]):
        mast_e = empty(f"{name}_m{mi}", (mx, 0, 0.30), parent=base)
        # Mast pole
        cyl(f"{name}_mp{mi}", r=0.08, depth=mh, segs=10, loc=(0, 0, mh/2),
            parent=mast_e, mat_=M_JUNK_DARK)
        # FAN SAIL (signature batten construction)
        sail_e = empty(f"{name}_sl{mi}", (0, 0, mh*0.55), parent=mast_e)
        # Bat ribs (horizontal battens)
        sail_w = mh * 0.65
        n_battens = 6
        for bi in range(n_battens):
            bz = -mh*0.35 + bi * (mh*0.55 / n_battens)
            bw = sail_w * (0.5 + (bi / n_battens) * 0.5)
            beveled_cube(f"{name}_sb{mi}_{bi}", (0.05, bw, 0.04), bevel_offset=0.005,
                         loc=(0.05, 0, bz), parent=sail_e, mat_=M_JUNK_DARK)
            # Sail fabric segment
            beveled_cube(f"{name}_sf{mi}_{bi}", (0.03, bw - 0.05, mh*0.55/n_battens * 0.95), bevel_offset=0.005,
                         loc=(0.10, 0, bz + (mh*0.55/n_battens)/2),
                         parent=sail_e, mat_=M_SAIL_RED if bi % 2 == 0 else M_SAIL_RED_DARK)
        # Rigging ropes
        for ri in range(4):
            cyl(f"{name}_rg{mi}_{ri}", r=0.01, depth=mh, segs=4,
                loc=(-0.05 + ri*0.04, 0, mh/2), parent=mast_e, mat_=M_ROPE)
        sails_data.append(sail_e)
    # Vietnam flag on stern
    flag_e = empty(f"{name}_fle", (-3.6, 0, 1.5), parent=base)
    cyl(f"{name}_flp", r=0.04, depth=1.5, segs=6, loc=(0, 0, 0.75),
        parent=flag_e, mat_=M_JUNK_DARK)
    beveled_cube(f"{name}_fl", (1.0, 0.04, 0.6), bevel_offset=0.04, loc=(0.5, 0, 1.30),
                 parent=flag_e, mat_=M_FLAG_VN_RED)
    # Yellow star
    star_e = empty(f"{name}_fls", (0.5, -0.04, 1.30), parent=flag_e)
    for sp in range(5):
        spa = (sp / 5.0) * math.pi * 2 + math.pi/2
        beveled_cube(f"{name}_fl_sp{sp}", (0.03, 0.10, 0.03), bevel_offset=0.005,
                     loc=(math.cos(spa)*0.06, 0, math.sin(spa)*0.06),
                     parent=star_e, mat_=M_FLAG_VN_STAR).rotation_euler = (spa - math.pi/2, 0, 0)
    smooth_sphere(f"{name}_fl_stc", r=0.04, loc=(0, 0, 0), parent=star_e, mat_=M_FLAG_VN_STAR)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "sails": sails_data}

junks = []
junk_pos = [(-25, 5, math.radians(20)), (-10, 15, math.radians(-10)),
             (10, 8, math.radians(15)), (25, -5, math.radians(-20)),
             (-5, -20, math.radians(40)), (5, -10, math.radians(-30))]
for i, (jx, jy, fac) in enumerate(junk_pos):
    j = make_junk(f"junk{i}", (jx, jy, 0.4), facing=fac)
    junks.append(j)

# ============ 4 FISHERMEN with CONICAL HATS (signature) ============
def make_fisherman(name, loc, in_boat=False, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body (brown work clothes)
    smooth_cone(f"{name}_bo", r1=0.28, r2=0.30, depth=0.6, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=M_CLOTH_BROWN)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.10, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=M_CLOTH_BLUE)
    # Bare feet
    for side in (-1, 1):
        beveled_cube(f"{name}_f{side}", (0.10, 0.20, 0.05), bevel_offset=0.01,
                     loc=(side*0.13, 0, 0), parent=base, mat_=M_SKIN_VN)
    # Arms (one extended with paddle/net)
    sh_l = empty(f"{name}_a0", (-0.28, 0, 1.55), parent=base)
    sh_l.rotation_euler = (math.radians(-70), 0, math.radians(40))
    cyl(f"{name}_ua0", r=0.06, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=M_CLOTH_BROWN)
    cyl(f"{name}_fa0", r=0.05, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_SKIN_VN)
    sh_r = empty(f"{name}_a1", (0.28, 0, 1.55), parent=base)
    sh_r.rotation_euler = (math.radians(-90), 0, math.radians(-30))
    cyl(f"{name}_ua1", r=0.06, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=M_CLOTH_BROWN)
    cyl(f"{name}_fa1", r=0.05, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_SKIN_VN)
    # Head
    head_f_e = empty(f"{name}_he", (0, 0, 1.85), parent=base)
    smooth_sphere(f"{name}_h", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_f_e, mat_=M_SKIN_VN)
    # Hair
    for hi in range(12):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.10, segs=6,
            loc=(math.cos(ha)*0.10, math.sin(ha)*0.10, 0.10),
            parent=head_f_e, mat_=M_HAIR_BLACK)
    # CONICAL HAT non-la (signature)
    hat_e = empty(f"{name}_ha", (0, 0, 0.18), parent=head_f_e)
    smooth_cone(f"{name}_ha_c", r1=0.35, r2=0.04, depth=0.40, segs=18, loc=(0, 0, 0.15),
                parent=hat_e, mat_=M_CONICAL)
    # Hat rings (signature woven)
    for ri in range(5):
        rz = -0.05 + ri * 0.10
        rr = 0.35 - ri * 0.06
        cyl(f"{name}_ha_r{ri}", r=rr, depth=0.015, segs=18, loc=(0, 0, rz + 0.20),
            parent=hat_e, mat_=M_CONICAL_DARK)
    # Strap
    cyl(f"{name}_ha_s", r=0.02, depth=0.30, segs=6, loc=(0, 0.08, 0), parent=hat_e, mat_=M_CLOTH_BROWN)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_f_e, mat_=M_EYE)
    # PADDLE (signature)
    paddle_e = empty(f"{name}_pa", (-0.20, -0.60, 0.30), parent=base)
    paddle_e.rotation_euler = (math.radians(-30), 0, math.radians(-15))
    cyl(f"{name}_pa_h", r=0.025, depth=2.5, segs=8, loc=(0, 0, 0),
        parent=paddle_e, mat_=M_JUNK_HULL)
    beveled_cube(f"{name}_pa_b", (0.30, 0.04, 0.50), bevel_offset=0.04,
                 loc=(0, 0, -1.35), parent=paddle_e, mat_=M_JUNK_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_f_e, "paddle": paddle_e}

# Small fisherman boats (sampan)
def make_sampan(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Curved hull
    smooth_cone(f"{name}_h", r1=0.45, r2=0.10, depth=4, segs=14, loc=(0, 0, 0),
                parent=base, mat_=M_JUNK_HULL).rotation_euler = (0, math.radians(90), 0)
    # Plank deck
    beveled_cube(f"{name}_pd", (3.8, 0.85, 0.10), bevel_offset=0.04, loc=(0, 0, 0.10),
                 parent=base, mat_=M_JUNK_DARK)
    # Curved canopy (signature)
    canopy_e = empty(f"{name}_ce", (0, 0, 0.85), parent=base)
    for csi in range(8):
        ca_p = -0.7 + csi * 0.2
        beveled_cube(f"{name}_cb{csi}", (0.15, 0.85, 0.05), bevel_offset=0.005,
                     loc=(ca_p, 0, math.cos(csi * 0.4) * 0.10),
                     parent=canopy_e, mat_=M_THATCH)
    # Nets (small piles)
    for ni in range(3):
        smooth_sphere(f"{name}_n{ni}", r=0.18, segs=12, rings=8,
                      loc=(1.2 - ni*0.4, 0, 0.30), parent=base, mat_=M_NET, scale=(1, 1, 0.5))
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

fishermen = []
fisher_sampans = []
for i in range(4):
    angle = (i / 4.0) * math.pi * 2 + math.pi/4
    sx = math.cos(angle) * 35
    sy = math.sin(angle) * 35
    sampan = make_sampan(f"sam{i}", (sx, sy, 0.4), facing=angle + math.pi/2)
    fisher_sampans.append(sampan)
    fm = make_fisherman(f"fm{i}", (sx, sy, 0.9), facing=angle + math.pi/2)
    fishermen.append(fm)

# ============ 3 FLOATING VILLAGES (signature) ============
def make_floating_house(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Floating platform with barrels
    beveled_cube(f"{name}_pl", (3.5, 3, 0.30), bevel_offset=0.08, loc=(0, 0, 0.15),
                 parent=base, mat_=M_HOUSE_WOOD)
    # Barrels underneath
    for bi in range(4):
        bx = -1.2 + (bi % 2) * 2.4
        by = -1 + (bi // 2) * 2
        cyl(f"{name}_b{bi}", r=0.35, depth=0.50, segs=12,
            loc=(bx, by, 0), parent=base, mat_=M_HOUSE_WOOD).rotation_euler = (math.radians(90), 0, 0)
    # House structure
    hcol = random.choice(HOUSE_COLORS)
    beveled_cube(f"{name}_w", (2.5, 2.2, 1.8), bevel_offset=0.08, loc=(0, 0, 1.20),
                 parent=base, mat_=hcol)
    # Roof (thatched pyramid)
    smooth_cone(f"{name}_r", r1=1.8, r2=0.2, depth=1.2, segs=4, loc=(0, 0, 2.7),
                parent=base, mat_=M_THATCH).rotation_euler = (0, 0, math.radians(45))
    # Door
    beveled_cube(f"{name}_d", (0.5, 0.06, 1.2), bevel_offset=0.04, loc=(0, -1.13, 0.95),
                 parent=base, mat_=M_HOUSE_WOOD)
    # Windows
    for side in (-1, 1):
        beveled_cube(f"{name}_wi{side}", (0.06, 0.5, 0.5), bevel_offset=0.02,
                     loc=(side*1.28, 0, 1.40), parent=base, mat_=M_FLAG_VN_STAR)
    # Drying nets on side
    for ni in range(3):
        beveled_cube(f"{name}_dn{ni}", (0.04, 0.7, 0.6), bevel_offset=0.005,
                     loc=(1.32, -0.7 + ni*0.7, 0.85), parent=base, mat_=M_NET)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

villages = []
for i, (vx, vy, vf) in enumerate([(-35, 30, math.radians(0)), (35, 35, math.radians(20)), (-30, -40, math.radians(-30))]):
    v = make_floating_house(f"vil{i}", (vx, vy, 0.3), facing=vf)
    villages.append(v)

# ============ CORMORANTS on rocks ============
def make_cormorant(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_bo", r=0.22, segs=14, rings=10, loc=(0, 0, 0.3),
                  parent=base, mat_=M_CORMORANT, scale=(1.5, 0.85, 1.0))
    # Long neck
    for ni in range(4):
        cyl(f"{name}_n{ni}", r=0.06 - ni*0.005, depth=0.18, segs=8,
            loc=(0.20 + ni*0.05, 0, 0.45 + ni*0.10),
            parent=base, mat_=M_CORMORANT).rotation_euler = (0, math.radians(45 - ni*5), 0)
    # Head
    smooth_sphere(f"{name}_h", r=0.10, segs=12, rings=10, loc=(0.55, 0, 0.85),
                  parent=base, mat_=M_CORMORANT)
    # Beak (hooked)
    cyl(f"{name}_be", r=0.025, depth=0.18, segs=8, loc=(0.72, 0, 0.85),
        parent=base, mat_=M_JUNK_TRIM).rotation_euler = (0, math.radians(90), 0)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_lg{side}", r=0.02, depth=0.15, segs=6,
            loc=(0, side*0.08, 0.10), parent=base, mat_=M_CORMORANT)
    return base

for i in range(6):
    a = random.uniform(0, math.pi*2); r = random.uniform(35, 55)
    cx = math.cos(a) * r; cy = math.sin(a) * r
    cz = random.uniform(15, 25)
    make_cormorant(f"corm{i}", (cx, cy, cz), facing=random.uniform(0, math.pi*2))

# ============================================================
# 600 MIST WISPS + 400 KINGFISHER BIRDS (PARTICULES SIGNATURES)
# ============================================================
mist_wisps = []
for i in range(600):
    px = random.uniform(-100, 100)
    py = random.uniform(-80, 80)
    pz = random.uniform(2, 28)
    s_col = M_MIST if i % 2 == 0 else M_MIST_BLUE
    s = smooth_sphere(f"mi{i}", r=random.uniform(0.6, 1.8), segs=10, rings=8,
                      loc=(px, py, pz), mat_=s_col, scale=(2.0, 2.0, 0.6))
    s["_phase"] = random.uniform(0, math.pi*2)
    s["_base_x"] = px; s["_base_y"] = py; s["_base_z"] = pz
    s["_drift_x"] = random.uniform(-0.3, 0.3)
    s["_drift_y"] = random.uniform(-0.3, 0.3)
    s["_speed"] = random.uniform(0.2, 0.6)
    mist_wisps.append(s)

# 400 kingfishers
birds = []
for i in range(400):
    px = random.uniform(-90, 90)
    py = random.uniform(-70, 70)
    pz = random.uniform(8, 35)
    b_e = empty(f"bd{i}", (px, py, pz))
    # Body
    body_col = M_KING_BLUE if i % 2 == 0 else M_KING_ORANGE
    smooth_sphere(f"bd{i}_bo", r=0.10, segs=10, rings=8, loc=(0, 0, 0),
                  parent=b_e, mat_=body_col, scale=(1.5, 0.85, 0.85))
    # Wings (signature flap)
    wing_e_l = empty(f"bd{i}_wl_e", (0, -0.06, 0), parent=b_e)
    wing_e_r = empty(f"bd{i}_wr_e", (0, 0.06, 0), parent=b_e)
    beveled_cube(f"bd{i}_wl", (0.16, 0.30, 0.02), bevel_offset=0.005, loc=(0, -0.15, 0),
                 parent=wing_e_l, mat_=body_col)
    beveled_cube(f"bd{i}_wr", (0.16, 0.30, 0.02), bevel_offset=0.005, loc=(0, 0.15, 0),
                 parent=wing_e_r, mat_=body_col)
    # Belly orange
    smooth_sphere(f"bd{i}_be", r=0.08, segs=10, rings=8, loc=(0, 0, -0.05),
                  parent=b_e, mat_=M_KING_BELLY, scale=(1.4, 0.7, 0.7))
    # Beak
    cyl(f"bd{i}_bk", r=0.015, depth=0.10, segs=6, loc=(0.13, 0, 0),
        parent=b_e, mat_=M_JUNK_TRIM).rotation_euler = (0, math.radians(90), 0)
    b_e["_phase"] = random.uniform(0, math.pi*2)
    b_e["_base_x"] = px; b_e["_base_y"] = py; b_e["_base_z"] = pz
    b_e["_speed"] = random.uniform(0.6, 1.5)
    b_e["_wl"] = wing_e_l; b_e["_wr"] = wing_e_r
    birds.append(b_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Junks bob + sails sway
for j in junks:
    phase = j["root"]["_phase"]
    bz_j = j["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        j["root"].location.z = bz_j + math.sin(t * 0.9 + phase) * 0.15
        j["root"].rotation_euler = (math.sin(t * 0.9 + phase) * math.radians(3),
                                     math.cos(t * 0.9 + phase) * math.radians(2),
                                     j["root"].rotation_euler.z)
        j["root"].keyframe_insert("location", frame=f)
        j["root"].keyframe_insert("rotation_euler", frame=f)
        # Sails sway
        for si, sail in enumerate(j["sails"]):
            sail.rotation_euler = (0, math.sin(t * 1.2 + phase + si) * math.radians(6), 0)
            sail.keyframe_insert("rotation_euler", frame=f)

# Sampans bob
for s in fisher_sampans:
    phase = s["_phase"]
    bz_s = s.location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s.location.z = bz_s + math.sin(t * 1.2 + phase) * 0.10
        s.rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(2),
                             math.cos(t * 1.2 + phase) * math.radians(2),
                             s.rotation_euler.z)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("rotation_euler", frame=f)

# Fishermen paddle
for fm in fishermen:
    phase = fm["root"]["_phase"]
    bz_f = fm["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        fm["root"].location.z = bz_f + math.sin(t * 1.2 + phase) * 0.10
        fm["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(3), 0,
                                       fm["root"].rotation_euler.z)
        fm["root"].keyframe_insert("location", frame=f)
        fm["root"].keyframe_insert("rotation_euler", frame=f)
        # Paddle rowing
        fm["paddle"].rotation_euler = (math.radians(-30 + math.sin(t * 3.0 + phase) * 20), 0,
                                         math.radians(-15))
        fm["paddle"].keyframe_insert("rotation_euler", frame=f)

# Villages bob
for v in villages:
    phase = v["_phase"]
    bz_v = v.location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        v.location.z = bz_v + math.sin(t * 0.6 + phase) * 0.06
        v.rotation_euler = (math.sin(t * 0.6 + phase) * math.radians(1.5), 0,
                             v.rotation_euler.z)
        v.keyframe_insert("location", frame=f)
        v.keyframe_insert("rotation_euler", frame=f)

# 600 mist wisps drift slowly
for s in mist_wisps:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    dx, dy = s["_drift_x"], s["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + dx * t * 2 + math.sin(t * speed + phase) * 0.5
        y = by + dy * t * 2 + math.cos(t * speed * 0.9 + phase) * 0.5
        z = bz + math.sin(t * speed * 0.7 + phase) * 0.5
        s.location = (x, y, z)
        sc_s = 1 + math.sin(t * 0.8 + phase) * 0.20
        s.scale = (sc_s * 2.0, sc_s * 2.0, sc_s * 0.6)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

# 400 kingfishers fly with wing flap
for b in birds:
    phase = b["_phase"]; speed = b["_speed"]
    bx, by, bz = b["_base_x"], b["_base_y"], b["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Circular flight pattern
        r = 8 + math.sin(t * speed * 0.3 + phase) * 3
        x = bx + math.cos(t * speed + phase) * r
        y = by + math.sin(t * speed + phase) * r
        z = bz + math.sin(t * speed * 1.2 + phase) * 2
        b.location = (x, y, z)
        b.rotation_euler = (0, 0, math.atan2(math.cos(t * speed + phase),
                                              -math.sin(t * speed + phase)))
        b.keyframe_insert("location", frame=f)
        b.keyframe_insert("rotation_euler", frame=f)
        # Wing flap
        wing_angle = math.sin(t * 15.0 + phase) * math.radians(45)
        b["_wl"].rotation_euler = (0, wing_angle, 0)
        b["_wr"].rotation_euler = (0, -wing_angle, 0)
        b["_wl"].keyframe_insert("rotation_euler", frame=f)
        b["_wr"].keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_vietnam_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_vietnamese_halong_bay_junks] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Vietnam Halong Bay: 12 limestone karst islands (irregular pillars + vegetation + trees + striations) + 6 junks with 3 masts each red fan sails 6-batten + pagoda cabin + Vietnam flag with yellow star + 4 fishermen conical hats + 4 sampans with thatched canopies + 3 floating villages + cormorants + 600 mist + 400 kingfishers")
print("🐦 FIXES: 1 turquoise sea ground + 600 mist + 400 kingfishers (signature Halong mandatory) 🐦")
