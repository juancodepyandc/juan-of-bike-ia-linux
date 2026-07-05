"""
proc_madagascar_baobab_avenue_lemurs.py — 277e procédural AuroraIA (142e qualité)
Madagascar baobab avenue lemurs: 12 Adansonia baobabs + 4 indri sifaka lemurs + chameleon + 4 villagers + carved wood houses + Madagascar flag + 600 baobab petals + 400 jumping lemurs
FIXES : 1 ground laterite red + signature petals + lemurs
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB277)

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

# Sky African sunset
M_SKY = mat("sky", (1.0, 0.55, 0.30, 1.0), 0.0, 0.7, emission=(1.0,0.55,0.30), emission_strength=2.5)
M_SKY_LOW = mat("sky_l", (1.0, 0.78, 0.45, 1.0), 0.0, 0.7, emission=(1.0,0.78,0.45), emission_strength=2.0)
M_SKY_HIGH = mat("sky_h", (0.55, 0.32, 0.55, 1.0), 0.0, 0.7, emission=(0.55,0.32,0.55), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.78, 0.30, 1.0), 0.0, 0.1, emission=(1.0,0.78,0.30), emission_strength=22.0)

# Laterite red soil (signature)
M_LATERITE = mat("lt", (0.78, 0.42, 0.25, 1.0), 0.0, 0.85, emission=(0.75,0.40,0.25), emission_strength=0.4)
M_LATERITE_DARK = mat("ltd", (0.55, 0.28, 0.15, 1.0), 0.0, 0.92)
M_LATERITE_DUST = mat("ltdu", (0.85, 0.55, 0.32, 1.0), 0.0, 0.75, emission=(0.82,0.55,0.32), emission_strength=0.5)
M_DIRT_TRAIL = mat("dt", (0.62, 0.42, 0.25, 1.0), 0.0, 0.92)

# Baobab trunk (signature massive smooth)
M_BAOBAB_BARK = mat("bb", (0.65, 0.55, 0.42, 1.0), 0.0, 0.75, emission=(0.62,0.52,0.40), emission_strength=0.4)
M_BAOBAB_BARK_DARK = mat("bbd", (0.45, 0.38, 0.28, 1.0), 0.0, 0.85)
M_BAOBAB_TOP = mat("bt", (0.55, 0.45, 0.35, 1.0), 0.0, 0.85)
M_BAOBAB_LEAF = mat("bl", (0.45, 0.62, 0.30, 1.0), 0.0, 0.55, emission=(0.42,0.60,0.30), emission_strength=0.5)

# Sifaka lemur (signature white + dark face)
M_SIFAKA_WHITE = mat("sw", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.92,0.90,0.82), emission_strength=0.4)
M_SIFAKA_BROWN = mat("sbr", (0.55, 0.35, 0.20, 1.0), 0.0, 0.75, emission=(0.52,0.32,0.20), emission_strength=0.3)
M_SIFAKA_DARK = mat("sda", (0.18, 0.12, 0.10, 1.0), 0.0, 0.65)
M_SIFAKA_FACE = mat("sf", (0.18, 0.10, 0.08, 1.0), 0.0, 0.55)
# Indri lemur (signature black/white)
M_INDRI_BLACK = mat("ib", (0.12, 0.10, 0.10, 1.0), 0.0, 0.65)
M_INDRI_WHITE = mat("iw", (0.92, 0.90, 0.85, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.82), emission_strength=0.4)

# Eyes
M_EYE_AMBER = mat("ea", (0.95, 0.65, 0.18, 1.0), 0.2, 0.20, emission=(0.95,0.65,0.18), emission_strength=3.0)
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Chameleon panther (signature colorful)
M_CHAM_BLUE = mat("cb", (0.30, 0.55, 0.85, 1.0), 0.3, 0.30, emission=(0.30,0.55,0.82), emission_strength=1.0)
M_CHAM_RED = mat("cr", (0.92, 0.30, 0.20, 1.0), 0.3, 0.30, emission=(0.90,0.30,0.20), emission_strength=1.0)
M_CHAM_GREEN = mat("cg", (0.32, 0.78, 0.32, 1.0), 0.3, 0.30, emission=(0.30,0.75,0.30), emission_strength=1.0)
M_CHAM_YELLOW = mat("cy", (1.0, 0.85, 0.30, 1.0), 0.3, 0.30, emission=(0.95,0.82,0.30), emission_strength=1.2)
M_CHAM_DARK = mat("cd", (0.32, 0.22, 0.10, 1.0), 0.0, 0.65)

# Skin Malagasy
M_SKIN_DARK = mat("sk", (0.45, 0.30, 0.20, 1.0), 0.0, 0.55, emission=(0.42,0.28,0.20), emission_strength=0.3)
M_HAIR_BLACK = mat("hbl", (0.10, 0.08, 0.06, 1.0), 0.0, 0.85)

# Villager clothing
M_LAMBA_WHITE = mat("lw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.90), emission_strength=0.4)
M_LAMBA_RED = mat("lr", (0.85, 0.30, 0.22, 1.0), 0.0, 0.55, emission=(0.82,0.30,0.22), emission_strength=0.5)
M_LAMBA_BLUE = mat("lb", (0.20, 0.42, 0.78, 1.0), 0.0, 0.55, emission=(0.20,0.42,0.75), emission_strength=0.4)
M_LAMBA_GREEN = mat("lgr", (0.30, 0.65, 0.40, 1.0), 0.0, 0.55, emission=(0.30,0.62,0.40), emission_strength=0.5)
LAMBA_COLORS = [M_LAMBA_WHITE, M_LAMBA_RED, M_LAMBA_BLUE, M_LAMBA_GREEN]

# Zafimaniry carved wood house (signature)
M_HOUSE_WOOD = mat("hw", (0.65, 0.42, 0.20, 1.0), 0.0, 0.75, emission=(0.62,0.40,0.20), emission_strength=0.3)
M_HOUSE_DARK = mat("hd", (0.35, 0.22, 0.10, 1.0), 0.0, 0.85)
M_THATCH = mat("th", (0.65, 0.45, 0.20, 1.0), 0.0, 0.85)

# Madagascar flag
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)
M_FLAG_RED = mat("frd", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=1.0)
M_FLAG_GREEN = mat("fgr", (0.18, 0.55, 0.32, 1.0), 0.0, 0.45, emission=(0.18,0.52,0.30), emission_strength=1.0)

# Petals
M_PETAL_WHITE = mat("pw", (0.98, 0.95, 0.92, 1.0), 0.0, 0.40, emission=(0.95,0.92,0.90), emission_strength=2.0)
M_PETAL_PINK = mat("ppk", (1.0, 0.70, 0.78, 1.0), 0.0, 0.40, emission=(0.95,0.70,0.75), emission_strength=2.0)
M_PETAL_CREAM = mat("pcm", (0.95, 0.92, 0.65, 1.0), 0.0, 0.40, emission=(0.92,0.90,0.62), emission_strength=2.0)
PETAL_COLORS = [M_PETAL_WHITE, M_PETAL_PINK, M_PETAL_CREAM]

# Lemur particles (small jumping)
M_LEMUR_PT_WHITE = mat("lpw", (0.92, 0.88, 0.82, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.80), emission_strength=1.0)
M_LEMUR_PT_BROWN = mat("lpb", (0.55, 0.35, 0.20, 1.0), 0.0, 0.65, emission=(0.52,0.32,0.20), emission_strength=0.8)
M_LEMUR_PT_GRAY = mat("lpg", (0.55, 0.55, 0.55, 1.0), 0.0, 0.65)
LEMUR_PT_COLORS = [M_LEMUR_PT_WHITE, M_LEMUR_PT_BROWN, M_LEMUR_PT_GRAY]

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sky_h = smooth_sphere("sky_h", r=240, segs=28, rings=16, loc=(0,0,15), mat_=M_SKY_HIGH)
sky_h.scale = (1,1,0.2)
# Sun
sun = smooth_sphere("sun", r=12, segs=24, rings=18, loc=(0, 110, 22), mat_=M_SUN)
for sh in range(4):
    smooth_sphere(f"sun_h{sh}", r=12 + sh*1.3, segs=24, rings=18, loc=(0, 110, 22), mat_=M_SUN)

# ============ ONE clean laterite red ground ============
ground = beveled_cube("ground", (280, 280, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_LATERITE)
# Dust patches (organic 3D bumps)
for hi in range(200):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 130)
    smooth_sphere(f"hl{hi}", r=random.uniform(1.0, 2.5), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_LATERITE_DARK if hi % 3 == 0 else M_LATERITE_DUST, scale=(1.5, 1.4, 0.18))
# Dirt trail (signature avenue)
for di in range(40):
    beveled_cube(f"trail{di}", (random.uniform(3, 6), 4, 0.10), bevel_offset=0.04,
                 loc=(0, -60 + di*3, 0.05), mat_=M_DIRT_TRAIL)

# ============ 12 GIANT BAOBAB TREES (signature Adansonia) ============
def make_baobab(name, loc, height=25, trunk_radius=2.5, scale=1.0):
    base = empty(name, loc)
    # Massive smooth trunk (bottle-shaped signature)
    n_sections = int(height / 2)
    for si in range(n_sections):
        sz = si * (height / n_sections)
        # Tapered profile (fat in middle, narrower at top)
        if si < n_sections * 0.3:
            sr = trunk_radius * (0.8 + si / (n_sections * 0.3) * 0.2)
        elif si < n_sections * 0.85:
            sr = trunk_radius * (1.0 - (si - n_sections * 0.3) / (n_sections * 0.55) * 0.35)
        else:
            sr = trunk_radius * (0.65 - (si - n_sections * 0.85) / (n_sections * 0.15) * 0.15)
        smooth_sphere(f"{name}_s{si}", r=sr, segs=20, rings=14,
                      loc=(0, 0, sz + height/n_sections/2),
                      parent=base, mat_=M_BAOBAB_BARK if si % 2 == 0 else M_BAOBAB_BARK_DARK,
                      scale=(1, 1, 1.4))
    # Bark vertical lines
    for bri in range(16):
        ba = (bri / 16.0) * math.pi * 2
        cyl(f"{name}_br{bri}", r=0.04, depth=height*0.95, segs=6,
            loc=(math.cos(ba)*trunk_radius*0.95, math.sin(ba)*trunk_radius*0.95, height/2),
            parent=base, mat_=M_BAOBAB_BARK_DARK)
    # CROWN with sparse spreading branches (signature)
    crown_e = empty(f"{name}_ce", (0, 0, height), parent=base)
    # Stocky branches (5-8 radiating)
    n_branches = 7
    for bi in range(n_branches):
        ba_b = (bi / n_branches) * math.pi * 2
        branch_e = empty(f"{name}_b{bi}_e", (0, 0, 0), parent=crown_e)
        branch_e.rotation_euler = (math.radians(60 + random.uniform(-15, 15)), 0, ba_b)
        # Branch stub
        cyl(f"{name}_b{bi}", r=0.6, depth=4, segs=12, loc=(0, 0, 2),
            parent=branch_e, mat_=M_BAOBAB_BARK)
        # Sub-branches
        for sbi in range(3):
            sb_e = empty(f"{name}_sb{bi}_{sbi}_e", (0, 0, 4), parent=branch_e)
            sb_e.rotation_euler = (math.radians(random.uniform(-30, 30)), 0, sbi * math.pi * 2 / 3)
            cyl(f"{name}_sb{bi}_{sbi}", r=0.20, depth=2.5, segs=8, loc=(0, 0, 1.25),
                parent=sb_e, mat_=M_BAOBAB_BARK_DARK)
            # Leaf clusters at branch tips (signature small leaves)
            smooth_sphere(f"{name}_lc{bi}_{sbi}", r=0.55, segs=14, rings=10,
                          loc=(0, 0, 2.6), parent=sb_e, mat_=M_BAOBAB_LEAF)
            for li in range(5):
                la = random.uniform(0, math.pi*2)
                smooth_sphere(f"{name}_lf{bi}_{sbi}_{li}", r=0.30,
                              loc=(math.cos(la)*0.35, math.sin(la)*0.35, 2.7),
                              parent=sb_e, mat_=M_BAOBAB_LEAF)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "crown": crown_e}

baobabs = []
# Avenue of baobabs (signature double row)
baobab_pos = [
    # Left row
    (-12, -50, 28, 3.0), (-12, -35, 25, 2.8), (-12, -20, 30, 3.2),
    (-12, -5, 26, 2.7), (-12, 10, 32, 3.5), (-12, 25, 24, 2.6),
    # Right row
    (12, -50, 27, 2.9), (12, -35, 30, 3.2), (12, -20, 26, 2.7),
    (12, -5, 28, 3.0), (12, 10, 32, 3.4), (12, 25, 25, 2.8),
]
for i, (bx, by, bh, br) in enumerate(baobab_pos):
    b = make_baobab(f"bao{i}", (bx, by, 0), height=bh, trunk_radius=br)
    baobabs.append(b)

# ============ 4 INDRI/SIFAKA LEMURS (signature) ============
def make_sifaka(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body white fluffy
    smooth_sphere(f"{name}_bo", r=0.30, segs=14, rings=12, loc=(0, 0, 0.85),
                  parent=base, mat_=M_SIFAKA_WHITE, scale=(0.85, 0.85, 1.3))
    # Brown back (signature)
    smooth_sphere(f"{name}_ba", r=0.28, segs=12, rings=10, loc=(0, 0.08, 0.85),
                  parent=base, mat_=M_SIFAKA_BROWN, scale=(0.85, 0.50, 1.2))
    # Long legs (signature jumping)
    for side in (-1, 1):
        # Upper leg
        leg_e = empty(f"{name}_le{side}", (side*0.15, 0, 0.50), parent=base)
        cyl(f"{name}_l{side}", r=0.08, depth=0.50, segs=10, loc=(0, 0, -0.25),
            parent=leg_e, mat_=M_SIFAKA_WHITE)
        # Lower leg
        cyl(f"{name}_ll{side}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.65),
            parent=leg_e, mat_=M_SIFAKA_WHITE)
        # Foot (long for jumping)
        beveled_cube(f"{name}_f{side}", (0.08, 0.18, 0.05), bevel_offset=0.01,
                     loc=(0, 0.04, -0.85), parent=leg_e, mat_=M_SIFAKA_DARK)
    # Arms
    for side_a in (-1, 1):
        arm_e = empty(f"{name}_a{side_a}", (side_a*0.28, 0, 1.10), parent=base)
        arm_e.rotation_euler = (math.radians(-70), 0, math.radians(side_a*40))
        cyl(f"{name}_ua{side_a}", r=0.07, depth=0.30, segs=10, loc=(0, 0, -0.15),
            parent=arm_e, mat_=M_SIFAKA_WHITE)
        cyl(f"{name}_fa{side_a}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.45),
            parent=arm_e, mat_=M_SIFAKA_WHITE)
        # Long fingers
        for fi in range(3):
            beveled_cube(f"{name}_fn{side_a}_{fi}", (0.02, 0.04, 0.10), bevel_offset=0.003,
                         loc=(fi*0.02 - 0.02, 0, -0.65), parent=arm_e, mat_=M_SIFAKA_DARK)
    # Head
    head_s_e = empty(f"{name}_he", (0, 0, 1.45), parent=base)
    smooth_sphere(f"{name}_h", r=0.20, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_s_e, mat_=M_SIFAKA_WHITE)
    # Dark face mask (signature)
    smooth_sphere(f"{name}_fc", r=0.18, segs=14, rings=10, loc=(0, -0.08, 0),
                  parent=head_s_e, mat_=M_SIFAKA_FACE, scale=(0.85, 0.85, 0.85))
    # Huge amber eyes (signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.055,
                      loc=(side*0.07, -0.16, 0.04),
                      parent=head_s_e, mat_=M_EYE_AMBER)
        smooth_sphere(f"{name}_ep{side}", r=0.025,
                      loc=(side*0.07, -0.20, 0.04),
                      parent=head_s_e, mat_=M_EYE)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.06, segs=10, rings=8,
                      loc=(side*0.18, 0, 0.10), parent=head_s_e, mat_=M_SIFAKA_DARK)
    # Long fluffy tail (signature ring-tail)
    tail_e = empty(f"{name}_te", (0, 0.18, 0.85), parent=base)
    tail_e.rotation_euler = (math.radians(45), 0, 0)
    for ti in range(8):
        cyl(f"{name}_t{ti}", r=0.10 - ti*0.008, depth=0.18, segs=10,
            loc=(0, 0, ti*0.18), parent=tail_e,
            mat_=M_SIFAKA_WHITE if ti % 2 == 0 else M_SIFAKA_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_s_e, "tail": tail_e}

sifakas = []
sifaka_pos = [(-15, -30, math.radians(0), 5), (15, -25, math.radians(0), 4),
               (-15, 5, math.radians(0), 6), (15, 15, math.radians(0), 5)]
for i, (sx_s, sy_s, fac, sz_s) in enumerate(sifaka_pos):
    s = make_sifaka(f"sf{i}", (sx_s, sy_s, sz_s), facing=fac)
    sifakas.append(s)

# ============ PANTHER CHAMELEON (signature colorful) ============
def make_chameleon(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body elongated
    cham_col = random.choice([M_CHAM_BLUE, M_CHAM_RED, M_CHAM_GREEN])
    smooth_sphere(f"{name}_bo", r=0.30, segs=14, rings=10, loc=(0, 0, 0.30),
                  parent=base, mat_=cham_col, scale=(2.0, 0.65, 0.85))
    # Stripes (multicolor signature)
    for stri in range(8):
        stripe_col = random.choice([M_CHAM_BLUE, M_CHAM_RED, M_CHAM_YELLOW, M_CHAM_GREEN])
        beveled_cube(f"{name}_st{stri}", (0.05, 0.15, 0.18), bevel_offset=0.01,
                     loc=(-0.45 + stri*0.13, 0, 0.32), parent=base, mat_=stripe_col)
    # Crest along back
    for ci in range(10):
        cz_c = -0.50 + ci*0.10
        beveled_cube(f"{name}_cr{ci}", (0.03, 0.04, 0.08 - abs(ci-5)*0.01), bevel_offset=0.005,
                     loc=(cz_c, 0, 0.45), parent=base, mat_=M_CHAM_DARK)
    # Head triangular (signature horn-like)
    head_c_e = empty(f"{name}_he", (0.55, 0, 0.32), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=12, rings=10, loc=(0, 0, 0),
                  parent=head_c_e, mat_=cham_col, scale=(1.3, 0.85, 1.0))
    # Helmet crest on head
    beveled_cube(f"{name}_hcr", (0.10, 0.06, 0.18), bevel_offset=0.02,
                 loc=(-0.05, 0, 0.08), parent=head_c_e, mat_=M_CHAM_DARK)
    # Eyes (signature rotating)
    eye_l_e = empty(f"{name}_el", (-0.02, -0.14, 0.04), parent=head_c_e)
    eye_r_e = empty(f"{name}_er", (-0.02, 0.14, 0.04), parent=head_c_e)
    smooth_sphere(f"{name}_el_b", r=0.07, segs=12, rings=10, loc=(0, 0, 0),
                  parent=eye_l_e, mat_=cham_col)
    smooth_sphere(f"{name}_er_b", r=0.07, segs=12, rings=10, loc=(0, 0, 0),
                  parent=eye_r_e, mat_=cham_col)
    # Pupils
    smooth_sphere(f"{name}_elp", r=0.025, loc=(0, -0.05, 0), parent=eye_l_e, mat_=M_EYE)
    smooth_sphere(f"{name}_erp", r=0.025, loc=(0, 0.05, 0), parent=eye_r_e, mat_=M_EYE)
    # CURLED TAIL (signature)
    tail_e = empty(f"{name}_te", (-0.55, 0, 0.30), parent=base)
    for ti in range(12):
        ta = (ti / 12.0) * math.pi * 1.8
        tx_t = -math.cos(ta) * 0.3 - 0.2
        tz_t = math.sin(ta) * 0.3
        cyl(f"{name}_t{ti}", r=0.07 - ti*0.004, depth=0.10, segs=8,
            loc=(tx_t, 0, tz_t), parent=tail_e, mat_=cham_col)
    # 4 grasping feet
    for fi, (fx_c, fy_c) in enumerate([(0.30, 0.25), (0.30, -0.25), (-0.30, 0.25), (-0.30, -0.25)]):
        # Leg
        cyl(f"{name}_l{fi}", r=0.05, depth=0.20, segs=8, loc=(fx_c, fy_c, 0.15),
            parent=base, mat_=cham_col).rotation_euler = (math.radians(70 if fy_c > 0 else -70), 0, 0)
        # Foot (zygodactyl - 2+3 toes)
        for tof in range(2):
            beveled_cube(f"{name}_to{fi}_{tof}", (0.04, 0.06, 0.03), bevel_offset=0.005,
                         loc=(fx_c + tof*0.03 - 0.015, fy_c*1.3, 0.02),
                         parent=base, mat_=M_CHAM_DARK)
    eye_l_e["_phase"] = random.uniform(0, math.pi*2)
    eye_r_e["_phase"] = random.uniform(0, math.pi*2)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "eye_l": eye_l_e, "eye_r": eye_r_e}

chameleon = make_chameleon("ch1", (5, -38, 3.5), facing=math.radians(0))

# ============ 4 ZAFIMANIRY VILLAGERS (signature) ============
def make_villager(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    lamba_col = random.choice(LAMBA_COLORS)
    # Body (lamba wrap - signature)
    smooth_cone(f"{name}_to", r1=0.30, r2=0.35, depth=0.95, segs=14, loc=(0, 0, 1.20),
                parent=base, mat_=lamba_col)
    # Lamba over shoulder
    beveled_cube(f"{name}_la", (0.50, 0.08, 0.85), bevel_offset=0.04,
                 loc=(0, -0.30, 1.40), parent=base, mat_=lamba_col)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.11, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=M_HOUSE_DARK)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.60), parent=base)
        sh.rotation_euler = (math.radians(-60 if side_idx == 0 else -30), 0, math.radians(side*20))
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=M_SKIN_DARK)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=M_SKIN_DARK)
    # Bare feet
    for side in (-1, 1):
        beveled_cube(f"{name}_f{side}", (0.10, 0.22, 0.05), bevel_offset=0.01,
                     loc=(side*0.13, 0.04, 0.03), parent=base, mat_=M_SKIN_DARK)
    # Head
    head_v_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.17, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_v_e, mat_=M_SKIN_DARK)
    # Hair short
    for hi in range(15):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.06, segs=6,
            loc=(math.cos(ha)*0.13, math.sin(ha)*0.10, 0.12),
            parent=head_v_e, mat_=M_HAIR_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_v_e, mat_=M_EYE)
    # Wide brim hat (signature woven)
    hat_e = empty(f"{name}_ha", (0, 0, 0.20), parent=head_v_e)
    cyl(f"{name}_ha_c", r=0.16, depth=0.10, segs=14, loc=(0, 0, 0),
        parent=hat_e, mat_=M_THATCH)
    cyl(f"{name}_ha_b", r=0.32, depth=0.04, segs=18, loc=(0, 0, -0.08),
        parent=hat_e, mat_=M_THATCH)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_v_e}

villagers = []
villager_pos = [(-25, 35, math.radians(-30)), (25, 35, math.radians(30)),
                 (-30, -10, math.radians(45)), (30, -10, math.radians(-45))]
for i, (vx, vy, fac) in enumerate(villager_pos):
    v = make_villager(f"vl{i}", (vx, vy, 0), facing=fac)
    villagers.append(v)

# ============ 2 ZAFIMANIRY CARVED WOOD HOUSES (signature) ============
def make_house(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Wooden walls
    beveled_cube(f"{name}_w", (4, 5, 2.8), bevel_offset=0.08, loc=(0, 0, 1.65),
                 parent=base, mat_=M_HOUSE_WOOD)
    # Vertical planks (signature)
    for pi in range(12):
        beveled_cube(f"{name}_p{pi}", (0.30, 0.05, 2.8), bevel_offset=0.02,
                     loc=(-1.85 + pi*0.32, -2.55, 1.65), parent=base, mat_=M_HOUSE_DARK)
    # Thatched roof (signature steep)
    roof_e = empty(f"{name}_re", (0, 0, 3.05), parent=base)
    smooth_cone(f"{name}_r", r1=3.5, r2=0.1, depth=2, segs=4, loc=(0, 0, 1),
                parent=roof_e, mat_=M_THATCH).rotation_euler = (0, 0, math.radians(45))
    # Thatch tufts
    for ti in range(30):
        ta = random.uniform(0, math.pi*2); tr = random.uniform(0.3, 2.5)
        smooth_sphere(f"{name}_th{ti}", r=random.uniform(0.10, 0.20), segs=10, rings=6,
                      loc=(math.cos(ta)*tr, math.sin(ta)*tr, random.uniform(0.5, 1.8)),
                      parent=roof_e, mat_=M_THATCH, scale=(1.2, 1.2, 0.7))
    # Carved door (signature)
    beveled_cube(f"{name}_d", (1.0, 0.08, 1.8), bevel_offset=0.04,
                 loc=(0, -2.60, 1.10), parent=base, mat_=M_HOUSE_DARK)
    # Door carvings (geometric pattern)
    for ki in range(8):
        kz = 0.4 + ki * 0.18
        beveled_cube(f"{name}_dk{ki}", (0.20, 0.05, 0.05), bevel_offset=0.01,
                     loc=(0, -2.65, kz), parent=base, mat_=M_HOUSE_WOOD)
    # Window
    for side in (-1, 1):
        beveled_cube(f"{name}_wi{side}", (0.5, 0.06, 0.5), bevel_offset=0.03,
                     loc=(side*1.20, -2.55, 1.95), parent=base, mat_=M_HOUSE_DARK)
        # Window cross
        beveled_cube(f"{name}_wxv{side}", (0.04, 0.07, 0.5), bevel_offset=0.01,
                     loc=(side*1.20, -2.58, 1.95), parent=base, mat_=M_HOUSE_WOOD)
        beveled_cube(f"{name}_wxh{side}", (0.5, 0.07, 0.04), bevel_offset=0.01,
                     loc=(side*1.20, -2.58, 1.95), parent=base, mat_=M_HOUSE_WOOD)
    return base

for i, (hx, hy, hf) in enumerate([(-30, 40, math.radians(0)), (30, 40, math.radians(0))]):
    make_house(f"ho{i}", (hx, hy, 0), facing=hf)

# ============ MADAGASCAR FLAG (signature) ============
flag_e = empty("flag", (-50, -50, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_HOUSE_DARK)
# White vertical band (signature - left third)
beveled_cube("fl_w", (1.4, 0.05, 2.4), bevel_offset=0.06, loc=(0.7, 0, 10.5),
             parent=flag_e, mat_=M_FLAG_WHITE)
# Red horizontal stripe top
beveled_cube("fl_r", (2.7, 0.05, 1.2), bevel_offset=0.06, loc=(2.75, 0, 11.1),
             parent=flag_e, mat_=M_FLAG_RED)
# Green horizontal stripe bottom
beveled_cube("fl_g", (2.7, 0.05, 1.2), bevel_offset=0.06, loc=(2.75, 0, 9.9),
             parent=flag_e, mat_=M_FLAG_GREEN)
flag_e["_phase"] = 0

# ============================================================
# 600 BAOBAB PETALS + 400 JUMPING LEMURS (PARTICULES SIGNATURES)
# ============================================================
petals = []
for i in range(600):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = random.uniform(2, 28)
    p_col = random.choice(PETAL_COLORS)
    p_e = empty(f"pe{i}", (px, py, pz))
    # Long thin petal (baobab signature)
    for pp in range(5):
        ppa = (pp / 5.0) * math.pi * 2
        beveled_cube(f"pe{i}_p{pp}", (0.04, 0.18, 0.02), bevel_offset=0.005,
                     loc=(math.cos(ppa)*0.05, math.sin(ppa)*0.05, 0),
                     parent=p_e, mat_=p_col).rotation_euler = (0, 0, ppa)
    # Yellow center stamens
    for sti in range(8):
        sta = (sti / 8.0) * math.pi * 2
        cyl(f"pe{i}_st{sti}", r=0.005, depth=0.12, segs=4,
            loc=(math.cos(sta)*0.04, math.sin(sta)*0.04, 0.04),
            parent=p_e, mat_=M_SUN)
    p_e["_phase"] = random.uniform(0, math.pi*2)
    p_e["_base_x"] = px; p_e["_base_z"] = pz
    p_e["_drift"] = random.uniform(0.2, 0.6)
    p_e["_fall"] = random.uniform(0.5, 1.3)
    p_e["_swing"] = random.uniform(1.0, 2.2)
    petals.append(p_e)

# 400 jumping lemurs
lemurs = []
for i in range(400):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = random.uniform(1, 10)
    l_col = random.choice(LEMUR_PT_COLORS)
    l_e = empty(f"lm{i}", (px, py, pz))
    # Body
    smooth_sphere(f"lm{i}_bo", r=0.15, segs=10, rings=8, loc=(0, 0, 0),
                  parent=l_e, mat_=l_col, scale=(0.85, 0.85, 1.2))
    # Head
    smooth_sphere(f"lm{i}_h", r=0.10, segs=10, rings=8, loc=(0, 0, 0.18),
                  parent=l_e, mat_=l_col)
    # Long tail (signature)
    tail_e = empty(f"lm{i}_te", (0, 0.10, 0.05), parent=l_e)
    tail_e.rotation_euler = (math.radians(30), 0, 0)
    for ti in range(5):
        cyl(f"lm{i}_t{ti}", r=0.04 - ti*0.005, depth=0.12, segs=6,
            loc=(0, 0, ti*0.10 + 0.10), parent=tail_e,
            mat_=l_col if ti % 2 == 0 else M_LEMUR_PT_GRAY)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"lm{i}_er{side}", r=0.03, loc=(side*0.08, 0, 0.24),
                      parent=l_e, mat_=l_col)
    # Eyes (amber)
    for side in (-1, 1):
        smooth_sphere(f"lm{i}_ey{side}", r=0.025, loc=(side*0.04, -0.08, 0.18),
                      parent=l_e, mat_=M_EYE_AMBER)
    # Legs (long for jumping)
    for side in (-1, 1):
        cyl(f"lm{i}_l{side}", r=0.025, depth=0.20, segs=6,
            loc=(side*0.06, 0, -0.15), parent=l_e, mat_=l_col)
    # Arms
    for side in (-1, 1):
        cyl(f"lm{i}_a{side}", r=0.02, depth=0.12, segs=6,
            loc=(side*0.12, 0, 0.05), parent=l_e, mat_=l_col).rotation_euler = (0, math.radians(side*30), 0)
    l_e["_phase"] = random.uniform(0, math.pi*2)
    l_e["_base_x"] = px; l_e["_base_y"] = py; l_e["_base_z"] = pz
    l_e["_speed"] = random.uniform(0.6, 1.4)
    l_e["_jump_h"] = random.uniform(2, 5)
    lemurs.append(l_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Baobab branches sway slightly
for b in baobabs:
    phase = b["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        b["crown"].rotation_euler = (math.sin(t * 0.5 + phase) * math.radians(2),
                                      math.cos(t * 0.5 + phase) * math.radians(2), 0)
        b["crown"].keyframe_insert("rotation_euler", frame=f)

# Sifakas sway/look around (on baobab branches)
for s in sifakas:
    phase = s["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(3), 0,
                                     s["root"].rotation_euler.z)
        s["root"].location.z = s["root"].location.z + math.sin(t * 1.0 + phase) * 0.05
        s["root"].keyframe_insert("rotation_euler", frame=f)
        s["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(10), 0,
                                   math.cos(t * 1.2 + phase) * math.radians(25))
        s["he"].keyframe_insert("rotation_euler", frame=f)
        s["tail"].rotation_euler = (math.radians(45) + math.sin(t * 1.0 + phase) * math.radians(15), 0,
                                     math.cos(t * 0.8 + phase) * math.radians(20))
        s["tail"].keyframe_insert("rotation_euler", frame=f)

# Chameleon eye independent rotation
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    chameleon["eye_l"].rotation_euler = (0, 0, math.sin(t * 2.0) * math.radians(40))
    chameleon["eye_l"].keyframe_insert("rotation_euler", frame=f)
    chameleon["eye_r"].rotation_euler = (0, 0, math.cos(t * 1.8) * math.radians(40))
    chameleon["eye_r"].keyframe_insert("rotation_euler", frame=f)
    chameleon["root"].rotation_euler = (math.sin(t * 0.5) * math.radians(2), 0,
                                          chameleon["root"].rotation_euler.z)
    chameleon["root"].keyframe_insert("rotation_euler", frame=f)

# Villagers sway
for v in villagers:
    phase = v["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        v["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     v["root"].rotation_euler.z)
        v["root"].keyframe_insert("rotation_euler", frame=f)
        v["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(3), 0,
                                   math.cos(t * 0.8 + phase) * math.radians(15))
        v["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(10))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 baobab petals fall
for p in petals:
    phase = p["_phase"]; drift = p["_drift"]; fall = p["_fall"]; swing = p["_swing"]
    bx, bz = p["_base_x"], p["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.8 + t * drift
        z = bz - (t * fall) % 25
        p.location = (x, p.location.y, z)
        p.rotation_euler = (t * 1.5 + phase, math.sin(t * 2.0 + phase) * math.radians(30), t * 1.0 + phase)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# 400 lemurs jump in patterns
for lm in lemurs:
    phase = lm["_phase"]; speed = lm["_speed"]; jh = lm["_jump_h"]
    bx, by, bz_l = lm["_base_x"], lm["_base_y"], lm["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * 4
        y = by + math.sin(t * speed + phase) * 4
        z = bz_l + abs(math.sin(t * speed * 2.0 + phase)) * jh
        lm.location = (x, y, z)
        lm.rotation_euler = (math.sin(t * speed * 2.0 + phase) * math.radians(20), 0,
                              math.atan2(math.cos(t * speed + phase),
                                          -math.sin(t * speed + phase)))
        lm.keyframe_insert("location", frame=f)
        lm.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_madagascar_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_madagascar_baobab_avenue_lemurs] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Madagascar: 12 giant baobab trees (Avenue of Baobabs signature double row) with bottle-shaped tapered trunks + 16 bark lines + 7 stocky branches + leaf clusters at tips + 4 sifaka lemurs (white fluffy body + brown back + dark face + huge amber eyes + long ring tail + jumping pose) + panther chameleon with multicolor stripes + independent rotating eyes + curled tail + 4 zafimaniry villagers with lamba wraps + woven hats + 2 carved wood houses with thatched roofs + carved doors with geometric patterns + Madagascar flag + 600 baobab flower petals + 400 jumping lemur particles")
print("🐒 FIXES: 1 laterite red ground + 600 baobab petals (white/pink/cream) + 400 jumping lemurs signature 🐒")
