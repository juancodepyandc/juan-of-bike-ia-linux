"""
proc_hawaiian_luau_volcano_hula.py — 266e procédural AuroraIA (131e qualité)
Hawaii luau volcano hula: active volcano + 6 hula dancers leis + 4 ukulele musicians + tiki torches + 8 palms + outrigger + sunset + 600 plumeria petals + 400 fire sparks
FIXES : 1 ground + signature particles plumeria + fire sparks
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB266)

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

# Sunset sky tropical
M_SKY = mat("sky", (1.0, 0.55, 0.30, 1.0), 0.0, 0.7, emission=(1.0,0.55,0.30), emission_strength=2.2)
M_SKY_PURPLE = mat("sky_p", (0.55, 0.25, 0.55, 1.0), 0.0, 0.7, emission=(0.55,0.25,0.55), emission_strength=1.8)
M_SUN = mat("sun", (1.0, 0.70, 0.20, 1.0), 0.0, 0.1, emission=(1.0,0.70,0.20), emission_strength=20.0)

# Black volcanic sand
M_SAND = mat("sand", (0.18, 0.15, 0.13, 1.0), 0.0, 0.85, emission=(0.18,0.15,0.13), emission_strength=0.2)
M_ROCK = mat("rock", (0.12, 0.10, 0.10, 1.0), 0.0, 0.92)

# Ocean
M_OCEAN = mat("ocean", (0.20, 0.75, 0.82, 1.0), 0.1, 0.20, emission=(0.20,0.72,0.80), emission_strength=1.5, alpha=0.78)
M_FOAM = mat("foam", (0.95, 0.95, 0.92, 1.0), 0.0, 0.30, emission=(0.92,0.92,0.90), emission_strength=1.5, alpha=0.65)

# Volcano
M_VOLCANO_DARK = mat("vd", (0.18, 0.14, 0.12, 1.0), 0.0, 0.92)
M_VOLCANO_ROCK = mat("vr", (0.25, 0.20, 0.18, 1.0), 0.0, 0.85)
M_LAVA = mat("lava", (1.0, 0.35, 0.05, 1.0), 0.2, 0.30, emission=(1.0,0.35,0.05), emission_strength=8.0)
M_LAVA_HOT = mat("lava_h", (1.0, 0.85, 0.20, 1.0), 0.2, 0.20, emission=(1.0,0.85,0.20), emission_strength=15.0)
M_LAVA_FLOW = mat("lava_f", (1.0, 0.50, 0.15, 1.0), 0.2, 0.25, emission=(1.0,0.50,0.15), emission_strength=10.0)
M_SMOKE = mat("smk", (0.20, 0.18, 0.18, 1.0), 0.0, 0.95, emission=(0.20,0.18,0.18), emission_strength=0.5, alpha=0.55)

# Palms
M_PALM_TRUNK = mat("pt", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85, emission=(0.50,0.30,0.15), emission_strength=0.3)
M_PALM_LEAF = mat("pl", (0.30, 0.62, 0.25, 1.0), 0.0, 0.55, emission=(0.28,0.58,0.25), emission_strength=0.5)
M_COCONUT = mat("co", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)

# Hula skin/clothing
M_SKIN = mat("sk", (0.85, 0.62, 0.45, 1.0), 0.0, 0.55, emission=(0.80,0.60,0.45), emission_strength=0.4)
M_HAIR_BLACK = mat("hb", (0.10, 0.06, 0.05, 1.0), 0.0, 0.85)
M_HAIR_BROWN = mat("hbr", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)

# Grass skirt
M_GRASS_SKIRT = mat("gs", (0.55, 0.78, 0.28, 1.0), 0.0, 0.55, emission=(0.52,0.75,0.28), emission_strength=0.4)
M_GRASS_SKIRT_2 = mat("gs2", (0.78, 0.92, 0.45, 1.0), 0.0, 0.55, emission=(0.75,0.88,0.45), emission_strength=0.5)

# Lei flowers (plumeria signature)
M_LEI_WHITE = mat("lw", (0.98, 0.96, 0.92, 1.0), 0.0, 0.50, emission=(0.95,0.92,0.88), emission_strength=1.3)
M_LEI_YELLOW = mat("ly", (1.0, 0.92, 0.30, 1.0), 0.0, 0.50, emission=(0.95,0.88,0.30), emission_strength=1.5)
M_LEI_PINK = mat("lp", (1.0, 0.55, 0.75, 1.0), 0.0, 0.50, emission=(0.95,0.55,0.72), emission_strength=1.5)
M_LEI_RED = mat("lr", (0.95, 0.18, 0.35, 1.0), 0.0, 0.50, emission=(0.92,0.18,0.35), emission_strength=1.3)
M_LEI_ORANGE = mat("lo", (1.0, 0.55, 0.18, 1.0), 0.0, 0.50, emission=(0.95,0.55,0.18), emission_strength=1.3)
LEI_COLORS = [M_LEI_WHITE, M_LEI_YELLOW, M_LEI_PINK, M_LEI_RED, M_LEI_ORANGE]

# Top (coconut bra signature)
M_COCO_BRA = mat("cb", (0.45, 0.28, 0.12, 1.0), 0.0, 0.65)

# Ukulele
M_UKE_WOOD = mat("uw", (0.78, 0.55, 0.30, 1.0), 0.0, 0.35, emission=(0.75,0.55,0.30), emission_strength=0.5)
M_UKE_DARK = mat("ud", (0.32, 0.20, 0.10, 1.0), 0.0, 0.45)
M_STRING = mat("st", (0.85, 0.85, 0.85, 1.0), 0.5, 0.30)

# Tiki torch
M_TIKI_WOOD = mat("tw", (0.55, 0.32, 0.15, 1.0), 0.0, 0.65, emission=(0.50,0.30,0.15), emission_strength=0.5)
M_TIKI_CARVED = mat("tc", (0.45, 0.25, 0.10, 1.0), 0.0, 0.75)
M_FLAME = mat("fl", (1.0, 0.55, 0.15, 1.0), 0.2, 0.15, emission=(1.0,0.55,0.15), emission_strength=18.0, alpha=0.85)
M_FLAME_CORE = mat("flc", (1.0, 0.92, 0.30, 1.0), 0.2, 0.10, emission=(1.0,0.92,0.30), emission_strength=25.0, alpha=0.90)

# Outrigger canoe
M_CANOE_WOOD = mat("cw", (0.65, 0.42, 0.20, 1.0), 0.0, 0.55, emission=(0.62,0.42,0.20), emission_strength=0.4)
M_CANOE_DARK = mat("cwd", (0.35, 0.22, 0.10, 1.0), 0.0, 0.75)

# Petals
M_PETAL_PINK = mat("ppk", (1.0, 0.65, 0.78, 1.0), 0.0, 0.40, emission=(0.95,0.65,0.75), emission_strength=2.0)
M_PETAL_YELLOW = mat("ppy", (1.0, 0.92, 0.35, 1.0), 0.0, 0.40, emission=(0.95,0.88,0.35), emission_strength=2.0)
M_PETAL_WHITE = mat("ppw", (0.98, 0.95, 0.90, 1.0), 0.0, 0.40, emission=(0.95,0.92,0.88), emission_strength=1.8)
M_PETAL_ORANGE = mat("ppo", (1.0, 0.65, 0.25, 1.0), 0.0, 0.40, emission=(0.95,0.65,0.25), emission_strength=2.0)
PETAL_COLORS = [M_PETAL_PINK, M_PETAL_YELLOW, M_PETAL_WHITE, M_PETAL_ORANGE]

# Spark
M_SPARK = mat("sp", (1.0, 0.55, 0.15, 1.0), 0.2, 0.10, emission=(1.0,0.55,0.15), emission_strength=8.0)
M_SPARK_HOT = mat("spo", (1.0, 0.92, 0.30, 1.0), 0.2, 0.10, emission=(1.0,0.92,0.30), emission_strength=12.0)

# Eye/lips
M_EYE_DARK = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_LIPS = mat("li", (0.55, 0.18, 0.20, 1.0), 0.0, 0.45)

# Headband
M_HEADBAND = mat("hd", (1.0, 0.55, 0.78, 1.0), 0.0, 0.55, emission=(0.95,0.55,0.75), emission_strength=0.8)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_p = smooth_sphere("sky_p", r=240, segs=28, rings=16, loc=(0,0,10), mat_=M_SKY_PURPLE)
sky_p.scale = (1,1,0.3)
# Sun
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-50, 100, 12), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-50, 100, 12), mat_=M_SUN)

# ============ ONE clean black volcanic sand ground ============
ground = beveled_cube("ground", (220, 220, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_SAND)
# Rock outcrops scattered
for i in range(180):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 90)
    smooth_sphere(f"rk{i}", r=random.uniform(0.4, 1.1), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_ROCK if i % 3 == 0 else M_SAND, scale=(1.3, 1.2, 0.25))

# ============ OCEAN ============
ocean_e = empty("ocean", loc=(0, 70, 0))
beveled_cube("oc", (220, 80, 0.20), bevel_offset=0.08, loc=(0, 0, 0.20),
             parent=ocean_e, mat_=M_OCEAN)
for fi in range(50):
    fx = random.uniform(-100, 100); fy = random.uniform(-38, -28)
    cyl(f"foam{fi}", r=random.uniform(0.5, 1.0), depth=0.06, segs=14,
        loc=(fx, fy, 0.30), parent=ocean_e, mat_=M_FOAM)

# ============ ACTIVE VOLCANO (signature) ============
volcano_e = empty("volcano", loc=(0, -60, 0))
# Stratovolcano shape
for layer in range(8):
    lz = layer * 4
    lr1 = 30 - layer * 3
    lr2 = 28 - layer * 3
    smooth_cone(f"v_l{layer}", r1=lr1, r2=lr2, depth=4.5, segs=22,
                loc=(0, 0, lz + 2.25), parent=volcano_e,
                mat_=M_VOLCANO_DARK if layer % 2 == 0 else M_VOLCANO_ROCK)
# Crater
crater_r = 8
cyl("v_cr", r=crater_r, depth=2, segs=22, loc=(0, 0, 32),
    parent=volcano_e, mat_=M_VOLCANO_DARK)
# Lava pool
cyl("v_lp", r=crater_r - 0.5, depth=1.0, segs=22, loc=(0, 0, 33),
    parent=volcano_e, mat_=M_LAVA)
cyl("v_lp_h", r=crater_r - 2, depth=0.5, segs=22, loc=(0, 0, 33.5),
    parent=volcano_e, mat_=M_LAVA_HOT)
# Lava flows down slopes (4 streams)
for fl_i in range(4):
    fa = (fl_i / 4.0) * math.pi * 2
    flow_e = empty(f"v_fl{fl_i}", (math.cos(fa)*8, math.sin(fa)*8, 32), parent=volcano_e)
    flow_e.rotation_euler = (0, 0, fa)
    for seg in range(15):
        sz_f = -seg * 2
        sx_f = seg * 1.5
        cyl(f"v_fl{fl_i}_s{seg}", r=0.6 - seg*0.02, depth=2.0, segs=10,
            loc=(sx_f, 0, sz_f), parent=flow_e,
            mat_=M_LAVA_FLOW if seg < 5 else M_LAVA)
# Smoke plume
for sm_i in range(20):
    sm_z = 35 + sm_i * 2
    sm_r = 4 + sm_i * 0.4
    smooth_sphere(f"v_sm{sm_i}", r=sm_r, segs=14, rings=10,
                  loc=(random.uniform(-2, 2), random.uniform(-2, 2), sm_z),
                  parent=volcano_e, mat_=M_SMOKE)
# Magma boils
boils = []
for bi in range(8):
    ba = (bi / 8.0) * math.pi * 2
    bb_pos = empty(f"v_b{bi}_e", (math.cos(ba)*3, math.sin(ba)*3, 33.8), parent=volcano_e)
    smooth_sphere(f"v_b{bi}", r=0.6, segs=12, rings=10, loc=(0, 0, 0),
                  parent=bb_pos, mat_=M_LAVA_HOT)
    bb_pos["_phase"] = random.uniform(0, math.pi*2)
    boils.append(bb_pos)

# ============ 8 PALM TREES ============
def make_palm(name, loc, lean=0):
    base = empty(name, loc)
    base.rotation_euler = (0, math.radians(lean), 0)
    for ti in range(12):
        tz = ti * 0.5
        tilt = math.sin(ti * 0.3) * 0.10
        cyl(f"{name}_t{ti}", r=0.18 - ti*0.005, depth=0.50, segs=10,
            loc=(tilt, 0, tz + 0.25), parent=base, mat_=M_PALM_TRUNK)
    crown_e = empty(f"{name}_cr", (0, 0, 6.5), parent=base)
    for li in range(10):
        la = (li / 10.0) * math.pi * 2
        leaf_e = empty(f"{name}_le{li}", (0, 0, 0), parent=crown_e)
        leaf_e.rotation_euler = (math.radians(70), 0, la)
        cyl(f"{name}_lr{li}", r=0.025, depth=2.5, segs=8, loc=(0, 0, 1.25),
            parent=leaf_e, mat_=M_PALM_TRUNK)
        for sl in range(8):
            sl_z = sl * 0.30 + 0.30
            for ps in (-1, 1):
                beveled_cube(f"{name}_pn{li}_{sl}_{ps}", (0.03, 0.5, 0.04), bevel_offset=0.01,
                             loc=(ps*0.25, 0, sl_z), parent=leaf_e, mat_=M_PALM_LEAF)
    for ci in range(6):
        ca = (ci / 6.0) * math.pi * 2
        smooth_sphere(f"{name}_co{ci}", r=0.20, loc=(math.cos(ca)*0.30, math.sin(ca)*0.30, 6.3),
                      parent=base, mat_=M_COCONUT)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "crown": crown_e}

palms = []
palm_pos = [(-35, -10, 5), (-25, -15, -3), (-15, -8, 8), (-5, -12, -8),
             (5, -12, 8), (15, -8, -8), (25, -15, 3), (35, -10, -5)]
for i, (px, py, lean) in enumerate(palm_pos):
    p = make_palm(f"palm{i}", (px, py, 0), lean=lean)
    palms.append(p)

# ============ 6 HULA DANCERS (signature) ============
def make_hula(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Coconut bra
    for side in (-1, 1):
        smooth_sphere(f"{name}_cb{side}", r=0.16, segs=14, rings=12,
                      loc=(side*0.18, -0.18, 1.50), parent=base, mat_=M_COCO_BRA, scale=(1, 0.6, 0.9))
    # Torso skin
    smooth_cone(f"{name}_to", r1=0.30, r2=0.32, depth=0.55, segs=14, loc=(0, 0, 1.25),
                parent=base, mat_=M_SKIN)
    # GRASS SKIRT (signature - many strands)
    skirt_e = empty(f"{name}_sk", (0, 0, 1.05), parent=base)
    for gs_i in range(60):
        ga = (gs_i / 60.0) * math.pi * 2
        gx = math.cos(ga) * 0.32
        gy = math.sin(ga) * 0.32
        skirt_col = M_GRASS_SKIRT if gs_i % 2 == 0 else M_GRASS_SKIRT_2
        beveled_cube(f"{name}_g{gs_i}", (0.03, 0.03, 0.85), bevel_offset=0.005,
                     loc=(gx, gy, -0.40), parent=skirt_e, mat_=skirt_col).rotation_euler = (math.cos(ga)*0.05, math.sin(ga)*0.05, ga)
    skirt_e["_phase"] = random.uniform(0, math.pi*2)
    # Pants/legs skin
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.10, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=M_SKIN)
    # Arms gracefully raised (hula pose)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.65), parent=base)
        sh.rotation_euler = (math.radians(-90), 0, math.radians(side * 60))
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=M_SKIN)
        # Forearm
        fa_e = empty(f"{name}_fae{side_idx}", (0, 0, -0.40), parent=sh)
        fa_e.rotation_euler = (math.radians(20), 0, 0)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.18),
            parent=fa_e, mat_=M_SKIN)
        # Wrist lei
        for wl in range(6):
            wla = (wl / 6.0) * math.pi * 2
            smooth_sphere(f"{name}_wl{side_idx}_{wl}", r=0.05,
                          loc=(math.cos(wla)*0.08, math.sin(wla)*0.08, -0.38),
                          parent=fa_e, mat_=random.choice(LEI_COLORS))
    # Head
    head_h_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_h_e, mat_=M_SKIN)
    # Long flowing hair
    hair_col = random.choice([M_HAIR_BLACK, M_HAIR_BROWN])
    for hi in range(25):
        ha = random.uniform(0, math.pi*2)
        hx = math.cos(ha) * 0.15
        hy = math.sin(ha) * 0.15
        hair_len = random.uniform(0.6, 1.0)
        for hsi in range(int(hair_len * 8)):
            cyl(f"{name}_hr{hi}_{hsi}", r=0.025, depth=0.10, segs=6,
                loc=(hx + math.sin(hsi*0.2)*0.02, hy + math.cos(hsi*0.2)*0.02, -hsi*0.10 - 0.10),
                parent=head_h_e, mat_=hair_col)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_h_e, mat_=M_EYE_DARK)
    # Lips
    beveled_cube(f"{name}_lp", (0.08, 0.04, 0.025), bevel_offset=0.005,
                 loc=(0, -0.17, -0.07), parent=head_h_e, mat_=M_LIPS)
    # FLORAL HEADBAND signature
    hb_e = empty(f"{name}_hb", (0, 0, 0.18), parent=head_h_e)
    for fb in range(10):
        fba = (fb / 10.0) * math.pi * 2
        smooth_sphere(f"{name}_fb{fb}", r=0.06,
                      loc=(math.cos(fba)*0.20, math.sin(fba)*0.20, 0),
                      parent=hb_e, mat_=random.choice(LEI_COLORS))
        # Petals
        for pp in range(4):
            ppa = (pp / 4.0) * math.pi * 2
            beveled_cube(f"{name}_fp{fb}_{pp}", (0.03, 0.06, 0.02), bevel_offset=0.005,
                         loc=(math.cos(fba)*0.20 + math.cos(ppa)*0.05,
                              math.sin(fba)*0.20 + math.sin(ppa)*0.05, 0),
                         parent=hb_e, mat_=random.choice(LEI_COLORS))
    # NECK LEI signature (multi-color plumeria)
    lei_e = empty(f"{name}_lei", (0, 0, -0.20), parent=head_h_e)
    for lp_i in range(30):
        lpa = (lp_i / 30.0) * math.pi * 2
        smooth_sphere(f"{name}_lf{lp_i}", r=0.07,
                      loc=(math.cos(lpa)*0.32, math.sin(lpa)*0.32, -0.18 + math.sin(lpa*2)*0.05),
                      parent=lei_e, mat_=random.choice(LEI_COLORS))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "skirt": skirt_e, "he": head_h_e}

dancers = []
dancer_pos = [(-12, 8, math.radians(20)), (-7, 10, math.radians(10)),
               (-2, 8, math.radians(0)), (2, 8, math.radians(0)),
               (7, 10, math.radians(-10)), (12, 8, math.radians(-20))]
for i, (dx, dy, fac) in enumerate(dancer_pos):
    d = make_hula(f"hula{i}", (dx, dy, 0), facing=fac)
    dancers.append(d)

# ============ 4 UKULELE MUSICIANS ============
def make_uke(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sitting pose
    shirt_col = random.choice([M_LEI_RED, M_LEI_ORANGE, M_LEI_YELLOW, M_LEI_PINK])
    # Body
    smooth_cone(f"{name}_bo", r1=0.32, r2=0.34, depth=0.6, segs=14, loc=(0, 0, 1.20),
                parent=base, mat_=shirt_col)
    # Crossed legs
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.11, depth=0.50, segs=10,
            loc=(side*0.30, 0.20, 0.75), parent=base, mat_=M_SKIN).rotation_euler = (math.radians(80), 0, 0)
    # Head
    head_u_e = empty(f"{name}_he", (0, 0, 1.85), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_u_e, mat_=M_SKIN)
    # Hair
    for hi in range(15):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.05, depth=0.25, segs=6,
            loc=(math.cos(ha)*0.10, math.sin(ha)*0.10, 0.10), parent=head_u_e, mat_=M_HAIR_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_u_e, mat_=M_EYE_DARK)
    # Lei around neck
    for lp_i in range(20):
        lpa = (lp_i / 20.0) * math.pi * 2
        smooth_sphere(f"{name}_lf{lp_i}", r=0.05,
                      loc=(math.cos(lpa)*0.28, math.sin(lpa)*0.28, 1.60),
                      parent=base, mat_=random.choice(LEI_COLORS))
    # UKULELE
    uke_e = empty(f"{name}_uke", (0, -0.30, 1.20), parent=base)
    # Body (small)
    smooth_sphere(f"{name}_ub", r=0.18, segs=16, rings=12, loc=(0, 0, 0),
                  parent=uke_e, mat_=M_UKE_WOOD, scale=(0.85, 0.30, 1.1))
    # Sound hole
    cyl(f"{name}_uh", r=0.06, depth=0.02, segs=12, loc=(0, -0.08, 0),
        parent=uke_e, mat_=M_UKE_DARK)
    # Neck
    cyl(f"{name}_un", r=0.025, depth=0.45, segs=10, loc=(0, -0.08, 0.32),
        parent=uke_e, mat_=M_UKE_DARK)
    # Head/tuners
    beveled_cube(f"{name}_uhd", (0.10, 0.05, 0.10), bevel_offset=0.02,
                 loc=(0, -0.08, 0.58), parent=uke_e, mat_=M_UKE_WOOD)
    # 4 strings
    for st in range(4):
        cyl(f"{name}_us{st}", r=0.003, depth=0.75, segs=6,
            loc=((st-1.5)*0.015, -0.10, 0.20), parent=uke_e, mat_=M_STRING)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.50), parent=base)
        sh.rotation_euler = (math.radians(-100 if side_idx == 0 else -80), 0, 0)
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.30, segs=10, loc=(0, 0, -0.15),
            parent=sh, mat_=M_SKIN)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "uke": uke_e}

ukers = []
uke_pos = [(-18, 4, math.radians(15)), (-10, 2, math.radians(5)),
            (10, 2, math.radians(-5)), (18, 4, math.radians(-15))]
for i, (ux, uy, fac) in enumerate(uke_pos):
    u = make_uke(f"uke{i}", (ux, uy, 0.5), facing=fac)
    ukers.append(u)

# ============ TIKI TORCHES (signature) ============
def make_tiki(name, loc):
    base = empty(name, loc)
    # Pole
    cyl(f"{name}_p", r=0.10, depth=3.5, segs=10, loc=(0, 0, 1.75), parent=base, mat_=M_TIKI_WOOD)
    # Carved face
    face_e = empty(f"{name}_fe", (0, 0, 3.2), parent=base)
    beveled_cube(f"{name}_f", (0.32, 0.32, 0.50), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=face_e, mat_=M_TIKI_CARVED)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_e{side}", r=0.04, loc=(side*0.10, -0.17, 0.10),
                      parent=face_e, mat_=M_TIKI_WOOD)
    # Mouth (carved teeth)
    beveled_cube(f"{name}_m", (0.18, 0.04, 0.06), bevel_offset=0.01,
                 loc=(0, -0.17, -0.10), parent=face_e, mat_=M_TIKI_WOOD)
    # Bowl on top
    smooth_sphere(f"{name}_bo", r=0.22, segs=16, rings=10, loc=(0, 0, 3.7),
                  parent=base, mat_=M_TIKI_WOOD, scale=(1, 1, 0.5))
    # Flame
    flame_e = empty(f"{name}_fle", (0, 0, 3.85), parent=base)
    smooth_cone(f"{name}_fl_b", r1=0.20, r2=0.05, depth=0.50, segs=12, loc=(0, 0, 0.25),
                parent=flame_e, mat_=M_FLAME)
    smooth_cone(f"{name}_fl_c", r1=0.12, r2=0.02, depth=0.35, segs=12, loc=(0, 0, 0.18),
                parent=flame_e, mat_=M_FLAME_CORE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "flame": flame_e}

tikis = []
tiki_pos = [(-20, 0), (-10, 0), (-3, 5), (3, 5), (10, 0), (20, 0), (-15, 12), (15, 12)]
for i, (tx, ty) in enumerate(tiki_pos):
    t = make_tiki(f"tiki{i}", (tx, ty, 0))
    tikis.append(t)

# ============ OUTRIGGER CANOE (signature) ============
canoe_e = empty("canoe", (-30, 30, 0.4))
canoe_e.rotation_euler = (0, 0, math.radians(-15))
# Hull
smooth_cone("ca_h", r1=0.50, r2=0.15, depth=6, segs=14, loc=(0, 0, 0),
            parent=canoe_e, mat_=M_CANOE_WOOD).rotation_euler = (0, math.radians(90), 0)
# Top plank
beveled_cube("ca_p", (6.0, 0.95, 0.10), bevel_offset=0.04, loc=(0, 0, 0.10),
             parent=canoe_e, mat_=M_CANOE_DARK)
# Outrigger float (signature)
beveled_cube("ca_of", (5, 0.30, 0.30), bevel_offset=0.06, loc=(0, 1.8, -0.10),
             parent=canoe_e, mat_=M_CANOE_WOOD)
# Outrigger struts
for ost in (-1.5, 0, 1.5):
    cyl(f"ca_st{ost}", r=0.04, depth=1.8, segs=8, loc=(ost, 0.9, 0.0),
        parent=canoe_e, mat_=M_CANOE_DARK).rotation_euler = (math.radians(90), 0, 0)
# Paddles
for pi, px in enumerate((-1.5, 1.5)):
    cyl(f"ca_pa{pi}", r=0.04, depth=1.5, segs=8, loc=(px, -1.0, 0.3),
        parent=canoe_e, mat_=M_CANOE_WOOD).rotation_euler = (math.radians(75), 0, 0)
    beveled_cube(f"ca_pb{pi}", (0.30, 0.05, 0.50), bevel_offset=0.04,
                 loc=(px, -1.9, -0.30), parent=canoe_e, mat_=M_CANOE_DARK)

# ============================================================
# 600 PLUMERIA PETALS + 400 FIRE SPARKS (PARTICULES SIGNATURES)
# ============================================================
petals = []
for i in range(600):
    px = random.uniform(-80, 80)
    py = random.uniform(-50, 60)
    pz = random.uniform(2, 20)
    p_e = empty(f"pe{i}", (px, py, pz))
    pcol = random.choice(PETAL_COLORS)
    # 5-petal flower
    for pp in range(5):
        ppa = (pp / 5.0) * math.pi * 2
        beveled_cube(f"pe{i}_p{pp}", (0.04, 0.08, 0.02), bevel_offset=0.005,
                     loc=(math.cos(ppa)*0.06, math.sin(ppa)*0.06, 0),
                     parent=p_e, mat_=pcol).rotation_euler = (0, 0, ppa)
    smooth_sphere(f"pe{i}_c", r=0.025, loc=(0, 0, 0), parent=p_e, mat_=M_LEI_YELLOW)
    p_e["_phase"] = random.uniform(0, math.pi*2)
    p_e["_base_x"] = px; p_e["_base_z"] = pz
    p_e["_drift"] = random.uniform(0.3, 0.8)
    p_e["_fall"] = random.uniform(0.5, 1.2)
    p_e["_swing"] = random.uniform(0.8, 2.0)
    petals.append(p_e)

# 400 fire sparks
sparks = []
for i in range(400):
    # Concentrate around volcano + tikis
    if i < 250:
        # Volcano sparks
        px = random.uniform(-12, 12) + 0  # volcano at y=-60 actually
        py = -60 + random.uniform(-12, 12)
        pz = random.uniform(33, 50)
    else:
        # Tiki sparks (random tiki)
        tx, ty = random.choice(tiki_pos)
        px = tx + random.uniform(-0.5, 0.5)
        py = ty + random.uniform(-0.5, 0.5)
        pz = random.uniform(4, 8)
    s_col = random.choice([M_SPARK, M_SPARK_HOT])
    s = smooth_sphere(f"sp{i}", r=random.uniform(0.06, 0.12), segs=8, rings=6,
                      loc=(px, py, pz), mat_=s_col)
    s["_phase"] = random.uniform(0, math.pi*2)
    s["_base_x"] = px; s["_base_y"] = py; s["_base_z"] = pz
    s["_rise"] = random.uniform(2.5, 5.0)
    s["_spread"] = random.uniform(0.5, 1.5)
    sparks.append(s)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Palms sway
for p in palms:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        p["crown"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(5),
                                      math.cos(t * 0.8 + phase) * math.radians(5), 0)
        p["crown"].keyframe_insert("rotation_euler", frame=f)

# Hula dancers sway hips
for d in dancers:
    phase = d["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        d["root"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(4),
                                     math.cos(t * 2.0 + phase) * math.radians(8),
                                     d["root"].rotation_euler.z + math.sin(t * 1.5 + phase) * math.radians(15))
        d["root"].keyframe_insert("rotation_euler", frame=f)
        # Skirt sway
        d["skirt"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(10), 0,
                                      math.cos(t * 2.0 + phase) * math.radians(15))
        d["skirt"].keyframe_insert("rotation_euler", frame=f)
        # Head sway
        d["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0,
                                   math.cos(t * 1.5 + phase) * math.radians(20))
        d["he"].keyframe_insert("rotation_euler", frame=f)

# Ukers play
for u in ukers:
    phase = u["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        u["root"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(4), 0,
                                     u["root"].rotation_euler.z)
        u["root"].keyframe_insert("rotation_euler", frame=f)
        sc_u = 1 + math.sin(t * 6.0 + phase) * 0.04
        u["uke"].scale = (sc_u, sc_u, sc_u)
        u["uke"].keyframe_insert("scale", frame=f)

# Tiki torch flames flicker
for t in tikis:
    phase = t["root"]["_phase"]
    for f in range(1, total_frames + 1, 2):
        ft = (f - 1) / fps
        sc_f = 1 + math.sin(ft * 12.0 + phase) * 0.25
        t["flame"].scale = (sc_f, sc_f, sc_f * (1 + math.cos(ft * 10.0 + phase) * 0.20))
        t["flame"].keyframe_insert("scale", frame=f)

# Volcano boils
for b in boils:
    phase = b["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        sc_b = 1 + math.sin(t * 5.0 + phase) * 0.4
        b.scale = (sc_b, sc_b, sc_b)
        b.location.z = math.sin(t * 4.0 + phase) * 0.3
        b.keyframe_insert("scale", frame=f)
        b.keyframe_insert("location", frame=f)

# Canoe bob
canoe_e["_phase"] = 0
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    canoe_e.location.z = 0.4 + math.sin(t * 1.0) * 0.20
    canoe_e.rotation_euler = (math.sin(t * 1.0) * math.radians(3),
                               math.cos(t * 1.0) * math.radians(3),
                               math.radians(-15))
    canoe_e.keyframe_insert("location", frame=f)
    canoe_e.keyframe_insert("rotation_euler", frame=f)

# 600 petals fall + sway
for p in petals:
    phase = p["_phase"]; drift = p["_drift"]; fall = p["_fall"]; swing = p["_swing"]
    bx, bz = p["_base_x"], p["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.8 + t * drift
        z = bz - (t * fall) % 18
        p.location = (x, p.location.y, z)
        p.rotation_euler = (t * 1.5 + phase, math.sin(t * 2.0 + phase) * math.radians(20), t * 0.8 + phase)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# 400 sparks rise
for s in sparks:
    phase = s["_phase"]; rise = s["_rise"]; spread = s["_spread"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.sin(t * 3.0 + phase) * spread
        y = by + math.cos(t * 2.5 + phase) * spread
        z = bz + (t * rise) % 12
        s.location = (x, y, z)
        sc_s = 1 + math.sin(t * 8.0 + phase) * 0.4
        s.scale = (sc_s, sc_s, sc_s)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_hawaii_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_hawaiian_luau_volcano_hula] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Hawaii luau: active volcano + lava flows + smoke + 6 hula dancers grass skirts coconut bra leis flower crowns + 4 ukulele musicians + 8 tikis + 8 palms + outrigger canoe + 600 plumeria + 400 sparks")
print("🌺 FIXES: 1 black sand ground + 600 plumeria + 400 sparks (signature Hawaii mandatory) 🌺")
