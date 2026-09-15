"""
proc_australian_outback_aboriginal_uluru.py — 248e procédural AuroraIA (113e qualité)
Australian Outback Uluru: Uluru sacred rock + 4 aborigines body-painted + didgeridoo + 6 kangaroos + 4 wallabies + 3 emus + 4 koalas + 8 eucalyptus + dingo + python + Milky Way + bonfire + dot paintings
FIXES : 1 ground + 600 Milky Way stars + 400 red sand drift (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB248)

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

# Night sky palette
M_SKY = mat("sky", (0.03, 0.02, 0.10, 1.0), 0.0, 0.7, emission=(0.04,0.03,0.13), emission_strength=0.5)
M_STAR_BRIGHT = mat("star_b", (1.0, 0.95, 0.85, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.85), emission_strength=12.0)
M_STAR_BLUE = mat("star_bl", (0.85, 0.92, 1.0, 1.0), 0.0, 0.10, emission=(0.85,0.92,1.0), emission_strength=10.0)
M_STAR_RED = mat("star_r", (1.0, 0.85, 0.70, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.70), emission_strength=9.0)
M_STAR_VARIANTS = [M_STAR_BRIGHT, M_STAR_BLUE, M_STAR_RED]
M_MOON = mat("moon", (0.92, 0.88, 0.78, 1.0), 0.0, 0.20, emission=(0.88,0.85,0.78), emission_strength=4.0)

# Milky Way colors signature
M_MILKY_WHITE = mat("mw_w", (0.85, 0.85, 0.95, 1.0), 0.0, 0.30, emission=(0.85,0.85,0.95), emission_strength=4.0, alpha=0.45)
M_MILKY_PURPLE = mat("mw_p", (0.65, 0.45, 0.95, 1.0), 0.0, 0.30, emission=(0.65,0.45,0.95), emission_strength=3.5, alpha=0.45)
M_MILKY_PINK = mat("mw_pk", (0.95, 0.65, 0.85, 1.0), 0.0, 0.30, emission=(0.92,0.65,0.85), emission_strength=3.5, alpha=0.45)

# Red ocher desert ground
M_RED_OCHER = mat("ocher", (0.65, 0.25, 0.10, 1.0), 0.0, 0.85, emission=(0.62,0.25,0.10), emission_strength=0.4)
M_OCHER_DARK = mat("ocher_d", (0.42, 0.18, 0.08, 1.0), 0.0, 0.85, emission=(0.40,0.16,0.08), emission_strength=0.3)
M_OCHER_BRIGHT = mat("ocher_b", (0.85, 0.35, 0.15, 1.0), 0.0, 0.80, emission=(0.80,0.35,0.15), emission_strength=0.5)
M_SAND_RED = mat("sand_r", (0.78, 0.32, 0.15, 1.0), 0.0, 0.75, emission=(0.72,0.30,0.15), emission_strength=0.4)

# Uluru rock (signature massive red sacred)
M_ULURU_BASE = mat("uluru", (0.75, 0.28, 0.12, 1.0), 0.0, 0.85, emission=(0.72,0.28,0.12), emission_strength=0.5)
M_ULURU_BRIGHT = mat("uluru_b", (0.85, 0.35, 0.18, 1.0), 0.0, 0.80, emission=(0.82,0.35,0.18), emission_strength=0.6)
M_ULURU_DARK = mat("uluru_d", (0.55, 0.22, 0.10, 1.0), 0.0, 0.85, emission=(0.52,0.22,0.10), emission_strength=0.4)
M_ULURU_SHADOW = mat("uluru_sh", (0.30, 0.15, 0.08, 1.0), 0.0, 0.85)

# Aboriginal skin
M_ABO_SKIN = mat("abo", (0.42, 0.25, 0.15, 1.0), 0.0, 0.65, emission=(0.40,0.25,0.15), emission_strength=0.3)
M_ABO_HAIR = mat("abo_h", (0.10, 0.06, 0.04, 1.0), 0.0, 0.55)
# Body paint signature (white dots)
M_PAINT_WHITE = mat("paint_w", (0.92, 0.90, 0.82, 1.0), 0.0, 0.45, emission=(0.85,0.85,0.78), emission_strength=1.5)
M_PAINT_YELLOW = mat("paint_y", (0.95, 0.78, 0.20, 1.0), 0.0, 0.50, emission=(0.92,0.75,0.20), emission_strength=1.8)
M_PAINT_OCHER = mat("paint_o", (0.85, 0.45, 0.18, 1.0), 0.0, 0.55, emission=(0.80,0.42,0.18), emission_strength=1.3)
PAINT_VARIANTS = [M_PAINT_WHITE, M_PAINT_YELLOW, M_PAINT_OCHER]

# Loincloth
M_LOIN = mat("loin", (0.62, 0.45, 0.22, 1.0), 0.0, 0.80)
M_LOIN_DARK = mat("loin_d", (0.40, 0.25, 0.12, 1.0), 0.0, 0.85)

# Didgeridoo wood
M_DIDGE_WOOD = mat("didge", (0.40, 0.25, 0.12, 1.0), 0.0, 0.75, emission=(0.38,0.25,0.12), emission_strength=0.4)
M_DIDGE_DARK = mat("didge_d", (0.20, 0.12, 0.06, 1.0), 0.0, 0.85)
M_DIDGE_PAINT = mat("didge_p", (0.95, 0.78, 0.25, 1.0), 0.0, 0.55, emission=(0.92,0.75,0.25), emission_strength=1.0)

# Boomerang
M_BOOMERANG_LIGHT = mat("boom_l", (0.78, 0.55, 0.30, 1.0), 0.0, 0.75, emission=(0.72,0.52,0.28), emission_strength=0.5)
M_BOOMERANG_DARK = mat("boom_d", (0.45, 0.28, 0.15, 1.0), 0.0, 0.85)

# Kangaroo brown
M_KANGAROO = mat("kang", (0.72, 0.45, 0.20, 1.0), 0.0, 0.75, emission=(0.68,0.42,0.20), emission_strength=0.3)
M_KANGAROO_BELLY = mat("kang_b", (0.92, 0.72, 0.45, 1.0), 0.0, 0.70)
M_KANGAROO_NOSE = mat("kang_n", (0.20, 0.12, 0.08, 1.0), 0.0, 0.55)

# Wallaby
M_WALLABY = mat("wall", (0.55, 0.35, 0.18, 1.0), 0.0, 0.75, emission=(0.52,0.33,0.18), emission_strength=0.3)
M_WALLABY_LIGHT = mat("wall_l", (0.78, 0.55, 0.32, 1.0), 0.0, 0.70)

# Emu
M_EMU_DARK = mat("emu_d", (0.32, 0.22, 0.18, 1.0), 0.0, 0.80, emission=(0.30,0.22,0.18), emission_strength=0.3)
M_EMU_LIGHT = mat("emu_l", (0.55, 0.45, 0.32, 1.0), 0.0, 0.80)
M_EMU_NECK = mat("emu_n", (0.45, 0.35, 0.20, 1.0), 0.0, 0.65)
M_EMU_BEAK = mat("emu_bk", (0.30, 0.22, 0.15, 1.0), 0.0, 0.65)

# Koala
M_KOALA_GREY = mat("koala", (0.55, 0.55, 0.52, 1.0), 0.0, 0.80, emission=(0.50,0.50,0.50), emission_strength=0.3)
M_KOALA_WHITE = mat("koala_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.75)
M_KOALA_NOSE = mat("koala_n", (0.10, 0.08, 0.06, 1.0), 0.0, 0.45)
M_KOALA_EAR_PINK = mat("koala_e", (0.85, 0.55, 0.55, 1.0), 0.0, 0.65)

# Eucalyptus
M_EUCAL_LEAF = mat("euc_l", (0.45, 0.55, 0.30, 1.0), 0.0, 0.70, emission=(0.42,0.52,0.28), emission_strength=0.4)
M_EUCAL_LEAF_BL = mat("euc_lb", (0.55, 0.65, 0.45, 1.0), 0.0, 0.70, emission=(0.52,0.62,0.42), emission_strength=0.5)
M_EUCAL_TRUNK = mat("euc_t", (0.85, 0.78, 0.65, 1.0), 0.0, 0.85, emission=(0.80,0.75,0.62), emission_strength=0.4)
M_EUCAL_BARK = mat("euc_b", (0.55, 0.42, 0.30, 1.0), 0.0, 0.85)

# Dingo
M_DINGO = mat("dingo", (0.85, 0.55, 0.28, 1.0), 0.0, 0.75, emission=(0.80,0.52,0.28), emission_strength=0.3)
M_DINGO_LIGHT = mat("dingo_l", (0.95, 0.78, 0.55, 1.0), 0.0, 0.70)

# Python snake
M_PYTHON_GREEN = mat("py_g", (0.30, 0.55, 0.22, 1.0), 0.0, 0.65, emission=(0.28,0.50,0.22), emission_strength=0.4)
M_PYTHON_BROWN = mat("py_br", (0.55, 0.35, 0.15, 1.0), 0.0, 0.70)
M_PYTHON_BELLY = mat("py_b", (0.92, 0.85, 0.65, 1.0), 0.0, 0.65)

# Fire
M_FIRE_OUTER = mat("fire_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=18.0)
M_FIRE_CORE = mat("fire_c", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=22.0)
M_LOG_FIRE = mat("log_f", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)
M_EMBER = mat("ember", (1.0, 0.30, 0.10, 1.0), 0.0, 0.20, emission=(1.0,0.30,0.10), emission_strength=8.0)

# Dot painting colors
M_DOT_RED = mat("dot_r", (0.92, 0.30, 0.20, 1.0), 0.0, 0.55, emission=(0.88,0.30,0.20), emission_strength=1.2)
M_DOT_YELLOW = mat("dot_y", (0.95, 0.85, 0.20, 1.0), 0.0, 0.55, emission=(0.92,0.82,0.20), emission_strength=1.5)
M_DOT_WHITE = mat("dot_w", (0.92, 0.90, 0.85, 1.0), 0.0, 0.50, emission=(0.88,0.88,0.82), emission_strength=1.2)
M_DOT_BLACK = mat("dot_bk", (0.10, 0.08, 0.06, 1.0), 0.0, 0.65)
DOT_COLORS = [M_DOT_RED, M_DOT_YELLOW, M_DOT_WHITE, M_DOT_BLACK]

# Eye
M_EYE_DARK_O = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_GLOW_RED = mat("eye_gl", (1.0, 0.20, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.20,0.10), emission_strength=6.0)

# ============ SKY ============
sky = smooth_sphere("sky", r=300, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Moon
moon = smooth_sphere("moon", r=3, segs=24, rings=18, loc=(-50, 90, 70), mat_=M_MOON)

# MILKY WAY BAND (signature huge diagonal across sky)
mw_e = empty("milky_way", (0, 0, 60))
mw_e.rotation_euler = (0, 0, math.radians(30))
# Many bright clusters
for mwi in range(80):
    mw_x = -100 + mwi * 2.5
    mw_y = math.sin(mwi * 0.3) * 8 + random.uniform(-3, 3)
    mw_z = math.cos(mwi * 0.15) * 5
    cluster_col = [M_MILKY_WHITE, M_MILKY_PURPLE, M_MILKY_PINK][mwi % 3]
    smooth_sphere(f"mw{mwi}", r=random.uniform(0.5, 1.8), segs=12, rings=8,
                  loc=(mw_x, mw_y, mw_z), parent=mw_e, mat_=cluster_col,
                  scale=(2.5, 1.5, 1.2))

# Background stars
for si in range(200):
    sa = random.uniform(0, math.pi*2); sr = random.uniform(80, 220)
    sh = random.uniform(15, 110)
    smooth_sphere(f"star{si}", r=random.uniform(0.10, 0.30), segs=8, rings=6,
                  loc=(sr*math.cos(sa), sr*math.sin(sa), sh),
                  mat_=random.choice(M_STAR_VARIANTS))

# ============ ONE clean red ocher desert ground ============
ground = beveled_cube("ground", (180, 180, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_RED_OCHER)
# Organic dunes
for i in range(180):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 75)
    smooth_sphere(f"dune{i}", r=random.uniform(0.4, 1.0), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=[M_OCHER_DARK, M_OCHER_BRIGHT, M_SAND_RED][i % 3],
                  scale=(1.5, 1.4, 0.22))
# Scattered red rocks
for ri in range(30):
    rx = random.uniform(-60, 60); ry = random.uniform(-60, 60)
    smooth_sphere(f"rock{ri}", r=random.uniform(0.40, 1.20), segs=12, rings=10,
                  loc=(rx, ry, 0.30), mat_=M_ULURU_DARK, scale=(1.2, 1.1, 0.7))

# ============ ULURU (signature massive sacred rock) ============
uluru_e = empty("uluru", loc=(0, 30, 0))
# Layered shape (irregular but recognizable)
for li in range(10):
    lz = li * 1.2
    lr_x = 25 - li * 1.5
    lr_y = 15 - li * 0.9
    # Each layer slightly irregular
    beveled_cube(f"ul_b{li}", (lr_x, lr_y, 1.5), bevel_offset=0.30,
                 loc=(random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), lz + 0.75),
                 parent=uluru_e, mat_=M_ULURU_BASE if li % 2 == 0 else M_ULURU_BRIGHT)
# Top rounded dome
smooth_sphere("ul_top", r=10, segs=22, rings=16, loc=(0, 0, 11),
              parent=uluru_e, mat_=M_ULURU_BASE, scale=(2.0, 1.2, 0.7))
# Erosion features (vertical channels signature)
for ei in range(20):
    ea = random.uniform(0, math.pi*2)
    ex_e = math.cos(ea) * 14
    ey_e = math.sin(ea) * 8
    beveled_cube(f"ul_er{ei}", (0.40, 0.80, 8), bevel_offset=0.06,
                 loc=(ex_e, ey_e, 5), parent=uluru_e,
                 mat_=M_ULURU_SHADOW)
# Surface texture variations
for ti in range(40):
    ta = random.uniform(0, math.pi*2)
    tr = random.uniform(0, 14)
    tz = random.uniform(2, 11)
    smooth_sphere(f"ul_t{ti}", r=random.uniform(0.4, 0.9),
                  loc=(tr*math.cos(ta), tr*math.sin(ta), tz),
                  parent=uluru_e, mat_=M_ULURU_DARK, scale=(1, 1, 0.5))

# ============ 4 ABORIGINES (body painted signature) ============
def make_aboriginal(name, loc, scale=1.0, facing=0, role="hunter"):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body dark skin
    smooth_cone(f"{name}_torso", r1=0.30*scale, r2=0.32*scale, depth=0.6*scale, segs=14,
                loc=(0, 0, 1.3*scale), parent=base, mat_=M_ABO_SKIN)
    # Loincloth
    smooth_cone(f"{name}_loin", r1=0.32*scale, r2=0.28*scale, depth=0.40*scale, segs=14,
                loc=(0, 0, 0.95*scale), parent=base, mat_=M_LOIN)
    # Belt
    cyl(f"{name}_belt", r=0.31*scale, depth=0.05*scale, segs=14, loc=(0, 0, 1.10*scale),
        parent=base, mat_=M_LOIN_DARK)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.10*scale, depth=0.85*scale, segs=10,
            loc=(side*0.13*scale, 0, 0.42*scale), parent=base, mat_=M_ABO_SKIN)
        # White dot paint on legs (signature)
        for di in range(6):
            dz = 0.15 + di * 0.12
            smooth_sphere(f"{name}_lp{side}_{di}", r=0.02*scale,
                          loc=(side*0.13*scale + 0.10*scale, 0, dz*scale),
                          parent=base, mat_=M_PAINT_WHITE)
    # Foot
    for side in (-1, 1):
        beveled_cube(f"{name}_ft{side}", (0.09*scale, 0.18*scale, 0.05*scale), bevel_offset=0.01,
                     loc=(side*0.13*scale, 0, 0), parent=base, mat_=M_ABO_SKIN)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        if role == "didgeridoo" and side == 1:
            # Right arm holds didgeridoo
            sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.65*scale), parent=base)
            sh.rotation_euler = (math.radians(-90), 0, math.radians(-15))
        elif role == "boomerang" and side == 1:
            # Right arm extended holding boomerang
            sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.65*scale), parent=base)
            sh.rotation_euler = (math.radians(-130), 0, math.radians(-30))
        else:
            sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.65*scale), parent=base)
            sh.rotation_euler = (math.radians(-40 + side*15), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side_idx}", r=0.06*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=M_ABO_SKIN)
        # White dot paint on arm
        for di in range(3):
            smooth_sphere(f"{name}_ap{side_idx}_{di}", r=0.025*scale,
                          loc=(0, 0, -0.10 - di*0.10*scale), parent=sh, mat_=M_PAINT_WHITE)
        cyl(f"{name}_fa{side_idx}", r=0.05*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_ABO_SKIN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_ABO_SKIN)
    # Face dot paint (signature)
    # Horizontal band of dots forehead
    for di in range(7):
        smooth_sphere(f"{name}_fp{di}", r=0.02*scale,
                      loc=((di-3)*0.04*scale, -0.18*scale, 0.10*scale), parent=head_e, mat_=M_PAINT_WHITE)
    # Cheek dots
    for side in (-1, 1):
        for di in range(3):
            smooth_sphere(f"{name}_cp{side}_{di}", r=0.018*scale,
                          loc=(side*0.10*scale, -0.16*scale, -0.05 - di*0.04*scale),
                          parent=head_e, mat_=random.choice(PAINT_VARIANTS))
    # Eyes piercing
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.03*scale), parent=head_e, mat_=M_EYE_DARK_O)
    # Hair tufts (curly afro signature)
    for hi in range(12):
        ha = random.uniform(0, math.pi*2)
        smooth_sphere(f"{name}_hr{hi}", r=0.05*scale,
                      loc=(math.cos(ha)*0.18*scale, math.sin(ha)*0.10*scale, 0.10*scale + random.uniform(0, 0.10)*scale),
                      parent=head_e, mat_=M_ABO_HAIR)
    # Beard if elder
    if role == "shaman" or random.random() > 0.4:
        for bi in range(8):
            ba = (bi / 8.0) * math.pi - math.pi/2
            smooth_sphere(f"{name}_bd{bi}", r=0.04*scale,
                          loc=(math.sin(ba)*0.12*scale, -0.16*scale, -0.10*scale),
                          parent=head_e, mat_=M_ABO_HAIR)
    # Chest paint (signature designs)
    for ci in range(8):
        ca = (ci / 8.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_chp{ci}", r=0.04*scale,
                      loc=(math.sin(ca)*0.25*scale, -0.30*scale, 1.45*scale),
                      parent=base, mat_=random.choice(PAINT_VARIANTS))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "role": role}

# Aboriginal characters
aborigines = []
abo_data = [
    ("abo_hunter", (-5, -8, 0), math.radians(20), "boomerang"),
    ("abo_didge1", (3, -10, 0), math.radians(-20), "didgeridoo"),
    ("abo_didge2", (7, -8, 0), math.radians(-30), "didgeridoo"),
    ("abo_shaman", (-3, -12, 0), math.radians(0), "shaman"),
]
for name, loc, fac, role in abo_data:
    a = make_aboriginal(name, loc, scale=1.0, facing=fac, role=role)
    aborigines.append(a)

# BOOMERANG in hunter's hand (signature curved)
boom_e = empty("boomerang", (-5 + math.cos(math.radians(20))*0.8, -8 + math.sin(math.radians(20))*0.8, 2.5))
boom_e.rotation_euler = (math.radians(60), 0, math.radians(45))
# Curved L-shape
for bi in range(10):
    ba = (bi / 9.0) * math.radians(60) - math.radians(30)
    bx_b = math.sin(ba) * 0.30
    bz_b = math.cos(ba) * 0.30
    beveled_cube(f"boom{bi}", (0.06, 0.18, 0.04), bevel_offset=0.01,
                 loc=(bx_b, 0, bz_b), parent=boom_e,
                 mat_=M_BOOMERANG_LIGHT if bi % 2 == 0 else M_BOOMERANG_DARK)
# Decorative dots
for di in range(6):
    smooth_sphere(f"boom_dot{di}", r=0.02,
                  loc=(0.05 - di*0.05, 0.05, 0.20 - di*0.08), parent=boom_e,
                  mat_=M_PAINT_WHITE)

# DIDGERIDOOS (signature long carved instruments)
def make_didgeridoo(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long tube (signature 1.5m+)
    for di in range(15):
        di_y = di * 0.20
        d_r = 0.05 + di * 0.005  # gradually widening
        cyl(f"{name}_t{di}", r=d_r, depth=0.20, segs=10, loc=(0, di_y, 0),
            parent=base, mat_=M_DIDGE_WOOD if di % 2 == 0 else M_DIDGE_DARK)
    # Bell end
    smooth_cone(f"{name}_bell", r1=0.18, r2=0.08, depth=0.30, segs=14, loc=(0, 3.15, 0),
                parent=base, mat_=M_DIDGE_WOOD)
    # Painted dot patterns along length
    for paint_i in range(12):
        py_p = 0.30 + paint_i * 0.25
        for pa in range(4):
            paa = (pa / 4.0) * math.pi * 2
            smooth_sphere(f"{name}_p{paint_i}_{pa}", r=0.02,
                          loc=(math.cos(paa)*0.08, py_p, math.sin(paa)*0.08),
                          parent=base, mat_=random.choice(DOT_COLORS))
    # Mouthpiece
    cyl(f"{name}_mp", r=0.04, depth=0.06, segs=8, loc=(0, -0.04, 0),
        parent=base, mat_=M_DIDGE_DARK)
    return base

# Position didgeridoos at the didge players
didge1_e = make_didgeridoo("didge1", (3, -10 + 0.3, 1.10), scale=1.0,
                            facing=math.radians(-20 + 90))
didge2_e = make_didgeridoo("didge2", (7, -8 + 0.3, 1.10), scale=1.0,
                            facing=math.radians(-30 + 90))

# ============ 6 KANGAROOS (signature) ============
def make_kangaroo(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body main
    smooth_sphere(f"{name}_body", r=0.5*scale, segs=18, rings=12, loc=(0, 0, 1.0*scale),
                  parent=base, mat_=M_KANGAROO, scale=(1.0, 1.4, 1.2))
    # Belly white
    smooth_sphere(f"{name}_belly", r=0.4*scale, loc=(0, -0.15*scale, 0.8*scale),
                  parent=base, mat_=M_KANGAROO_BELLY, scale=(0.85, 1.3, 0.6))
    # Powerful hind legs (signature)
    for side in (-1, 1):
        leg_e = empty(f"{name}_l{side}_e", (side*0.20*scale, -0.10*scale, 0.55*scale), parent=base)
        # Thigh
        cyl(f"{name}_th{side}", r=0.15*scale, depth=0.55*scale, segs=10,
            loc=(0, 0, -0.10*scale), parent=leg_e, mat_=M_KANGAROO)
        # Shin
        cyl(f"{name}_sh{side}", r=0.10*scale, depth=0.50*scale, segs=10,
            loc=(0, 0.10*scale, -0.45*scale), parent=leg_e, mat_=M_KANGAROO)
        # Foot LONG (signature)
        beveled_cube(f"{name}_ft{side}", (0.10*scale, 0.40*scale, 0.08*scale), bevel_offset=0.02,
                     loc=(0, 0.20*scale, -0.55*scale), parent=leg_e, mat_=M_KANGAROO)
    # Small front arms
    for side in (-1, 1):
        arm_e = empty(f"{name}_a{side}_e", (side*0.20*scale, 0.10*scale, 1.20*scale), parent=base)
        arm_e.rotation_euler = (math.radians(40), 0, math.radians(side*15))
        cyl(f"{name}_uarm{side}", r=0.05*scale, depth=0.25*scale, segs=8,
            loc=(0, 0, -0.13*scale), parent=arm_e, mat_=M_KANGAROO)
        cyl(f"{name}_fa{side}", r=0.04*scale, depth=0.20*scale, segs=8,
            loc=(0, 0, -0.35*scale), parent=arm_e, mat_=M_KANGAROO)
        # Paw
        smooth_sphere(f"{name}_paw{side}", r=0.05*scale, loc=(0, 0, -0.48*scale),
                      parent=arm_e, mat_=M_KANGAROO)
    # Long thick tail (signature for balance)
    tail_e = empty(f"{name}_tl", (0, 0.60*scale, 0.80*scale), parent=base)
    tail_e.rotation_euler = (math.radians(-30), 0, 0)
    for ti in range(5):
        cyl(f"{name}_t{ti}", r=0.15*scale - ti*0.02, depth=0.35*scale, segs=10,
            loc=(0, ti*0.30*scale, 0), parent=tail_e, mat_=M_KANGAROO)
    # Head
    head_e = empty(f"{name}_he", (0, -0.50*scale, 1.55*scale), parent=base)
    head_e.rotation_euler = (math.radians(-30), 0, 0)
    smooth_sphere(f"{name}_head", r=0.20*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_KANGAROO, scale=(1.0, 1.5, 0.9))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.13*scale, loc=(0, -0.20*scale, -0.06*scale),
                  parent=head_e, mat_=M_KANGAROO_BELLY, scale=(1.0, 1.2, 0.7))
    # Nose
    smooth_sphere(f"{name}_nose", r=0.04*scale, loc=(0, -0.30*scale, -0.02*scale),
                  parent=head_e, mat_=M_KANGAROO_NOSE)
    # Long pointed ears (signature)
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.06*scale, r2=0.01*scale, depth=0.30*scale, segs=10,
                          loc=(side*0.10*scale, 0.10*scale, 0.20*scale), parent=head_e, mat_=M_KANGAROO)
        ear.rotation_euler = (math.radians(-15), 0, math.radians(side*15))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.035*scale,
                      loc=(side*0.10*scale, -0.13*scale, 0.05*scale), parent=head_e, mat_=M_EYE_DARK_O)
    base["_phase"] = random.uniform(0, math.pi*2)
    base["_speed"] = random.uniform(1.0, 2.0)
    return {"root": base, "he": head_e, "tail": tail_e}

kangaroos = []
kangaroo_pos = [(-15, -15, math.radians(45)), (-20, -10, math.radians(60)),
                 (-25, -18, math.radians(30)), (15, -20, math.radians(-45)),
                 (22, -15, math.radians(-60)), (18, -10, math.radians(-30))]
for i, (kx, ky, fac) in enumerate(kangaroo_pos):
    k = make_kangaroo(f"kangaroo{i}", (kx, ky, 0), scale=1.0, facing=fac)
    kangaroos.append(k)

# ============ 4 WALLABIES (smaller cousins) ============
def make_wallaby(name, loc, scale=0.65, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.5*scale, segs=18, rings=12, loc=(0, 0, 1.0*scale),
                  parent=base, mat_=M_WALLABY, scale=(1.0, 1.3, 1.0))
    smooth_sphere(f"{name}_belly", r=0.4*scale, loc=(0, -0.15*scale, 0.8*scale),
                  parent=base, mat_=M_WALLABY_LIGHT, scale=(0.85, 1.3, 0.6))
    for side in (-1, 1):
        cyl(f"{name}_th{side}", r=0.12*scale, depth=0.45*scale, segs=10,
            loc=(side*0.20*scale, -0.10*scale, 0.45*scale), parent=base, mat_=M_WALLABY)
        beveled_cube(f"{name}_ft{side}", (0.08*scale, 0.30*scale, 0.06*scale), bevel_offset=0.01,
                     loc=(side*0.20*scale, 0.10*scale, 0), parent=base, mat_=M_WALLABY)
    # Tail
    cyl(f"{name}_tail", r=0.10*scale, depth=0.8*scale, segs=10, loc=(0, 0.60*scale, 0.70*scale),
        parent=base, mat_=M_WALLABY).rotation_euler = (math.radians(-30), 0, 0)
    # Head
    head_e = empty(f"{name}_he", (0, -0.50*scale, 1.45*scale), parent=base)
    head_e.rotation_euler = (math.radians(-30), 0, 0)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_WALLABY, scale=(1.0, 1.4, 0.9))
    for side in (-1, 1):
        smooth_cone(f"{name}_ear{side}", r1=0.05*scale, r2=0.01*scale, depth=0.25*scale, segs=10,
                    loc=(side*0.10*scale, 0.10*scale, 0.20*scale), parent=head_e,
                    mat_=M_WALLABY).rotation_euler = (math.radians(-15), 0, math.radians(side*15))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

wallabies = []
wallaby_pos = [(-18, 15, math.radians(120)), (18, 15, math.radians(60)),
                (-22, 18, math.radians(150)), (22, 18, math.radians(30))]
for i, (wx, wy, fac) in enumerate(wallaby_pos):
    w = make_wallaby(f"wallaby{i}", (wx, wy, 0), scale=0.65, facing=fac)
    wallabies.append(w)

# ============ 3 EMUS (signature flightless birds) ============
def make_emu(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body (signature fluffy oval)
    smooth_sphere(f"{name}_body", r=0.55*scale, segs=18, rings=12, loc=(0, 0, 1.1*scale),
                  parent=base, mat_=M_EMU_DARK, scale=(1.0, 1.4, 1.2))
    # Feather tufts
    for fi in range(15):
        fa = random.uniform(0, math.pi*2); fe = random.uniform(0, math.pi)
        fx_f = math.sin(fe)*math.cos(fa)*0.6*scale
        fy_f = math.sin(fe)*math.sin(fa)*0.85*scale
        fz_f = math.cos(fe)*0.7*scale + 1.1*scale
        smooth_sphere(f"{name}_ft{fi}", r=0.10*scale,
                      loc=(fx_f, fy_f, fz_f), parent=base,
                      mat_=M_EMU_DARK if fi % 2 == 0 else M_EMU_LIGHT,
                      scale=(0.8, 1.5, 0.5))
    # 2 long legs (signature)
    for side in (-1, 1):
        cyl(f"{name}_th{side}", r=0.08*scale, depth=0.50*scale, segs=10,
            loc=(side*0.12*scale, 0, 0.65*scale), parent=base, mat_=M_EMU_DARK)
        cyl(f"{name}_sh{side}", r=0.06*scale, depth=0.55*scale, segs=10,
            loc=(side*0.12*scale, 0, 0.15*scale), parent=base, mat_=M_EMU_LIGHT)
        # 3-toed feet (signature)
        for ti in range(3):
            ta = (ti - 1) * 0.3
            beveled_cube(f"{name}_t{side}_{ti}", (0.04*scale, 0.10*scale, 0.04*scale), bevel_offset=0.01,
                         loc=(side*0.12*scale + ta*0.05*scale, 0.05*scale, -0.10*scale),
                         parent=base, mat_=M_EMU_DARK)
    # Long S-curved neck (signature)
    neck_e = empty(f"{name}_neck", (0, 0, 1.5*scale), parent=base)
    for ni in range(7):
        ni_z = ni * 0.20
        nx_s = math.sin(ni * 0.4) * 0.10
        cyl(f"{name}_n{ni}", r=0.08*scale - ni*0.004, depth=0.22, segs=10,
            loc=(0, nx_s*scale, ni_z*scale), parent=neck_e, mat_=M_EMU_NECK)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.55*scale), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.12*scale, segs=16, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_EMU_NECK, scale=(1.0, 1.3, 1.0))
    # Beak
    smooth_cone(f"{name}_beak", r1=0.04*scale, r2=0.01*scale, depth=0.18*scale, segs=10,
                loc=(0, -0.15*scale, 0), parent=head_e,
                mat_=M_EMU_BEAK).rotation_euler = (math.radians(-90), 0, 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.10*scale, 0.04*scale), parent=head_e, mat_=M_EYE_DARK_O)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "neck": neck_e, "he": head_e}

emus = []
emu_pos = [(-30, -3, math.radians(45)), (-32, 5, math.radians(-30)), (32, -2, math.radians(135))]
for i, (ex, ey, fac) in enumerate(emu_pos):
    e = make_emu(f"emu{i}", (ex, ey, 0), scale=1.0, facing=fac)
    emus.append(e)

# ============ 8 EUCALYPTUS TREES (signature white trunks) ============
def make_eucalyptus(name, loc, scale=1.0):
    base = empty(name, loc)
    # Trunk (signature white peeling bark)
    for ti in range(8):
        tz = ti * 0.55
        cyl(f"{name}_t{ti}", r=0.20 - ti*0.012, depth=0.55, segs=12, loc=(0, 0, tz + 0.27),
            parent=base, mat_=M_EUCAL_TRUNK if ti % 2 == 0 else M_EUCAL_BARK)
    # Bark patches peeling
    for bi in range(8):
        ba = random.uniform(0, math.pi*2); bz = random.uniform(0.5, 4)
        beveled_cube(f"{name}_bk{bi}", (0.08, 0.20, 0.40), bevel_offset=0.02,
                     loc=(math.cos(ba)*0.18, math.sin(ba)*0.18, bz),
                     parent=base, mat_=M_EUCAL_BARK)
    # Branches splitting
    for bi in range(5):
        ba = (bi / 5.0) * math.pi * 2 + random.uniform(-0.2, 0.2)
        br_e = empty(f"{name}_br{bi}_e", (0, 0, 4.5), parent=base)
        br_e.rotation_euler = (math.radians(random.uniform(35, 55)), 0, ba)
        cyl(f"{name}_br{bi}", r=0.10, depth=1.5, segs=10, loc=(0, 0, 0.75),
            parent=br_e, mat_=M_EUCAL_BARK)
        # Leaves cluster at branch end
        for li in range(8):
            la = random.uniform(0, math.pi*2); lz = random.uniform(0.8, 1.5)
            lx_l = math.cos(la) * random.uniform(0.2, 0.6)
            ly_l = math.sin(la) * random.uniform(0.2, 0.6)
            # Leaf shape long oval
            beveled_cube(f"{name}_l{bi}_{li}", (0.10, 0.04, 0.30), bevel_offset=0.03,
                         loc=(lx_l, ly_l, lz), parent=br_e,
                         mat_=M_EUCAL_LEAF if li % 2 == 0 else M_EUCAL_LEAF_BL)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base}

eucalyptus = []
euc_pos = [(-35, -25, 0), (35, -25, 0), (-40, 0, 0), (40, 0, 0),
            (-35, 25, 0), (35, 25, 0), (-20, 40, 0), (20, 40, 0)]
for i, (ex, ey, ez) in enumerate(euc_pos):
    e = make_eucalyptus(f"eucal{i}", (ex, ey, ez), scale=1.0)
    eucalyptus.append(e)

# ============ 4 KOALAS in eucalyptus trees (signature) ============
def make_koala(name, loc, scale=0.6, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Round body grey
    smooth_sphere(f"{name}_body", r=0.45*scale, segs=18, rings=12, loc=(0, 0, 0.5*scale),
                  parent=base, mat_=M_KOALA_GREY, scale=(1.0, 1.0, 1.1))
    # White chest
    smooth_sphere(f"{name}_chest", r=0.35*scale, loc=(0, -0.15*scale, 0.5*scale),
                  parent=base, mat_=M_KOALA_WHITE, scale=(0.85, 1.0, 0.7))
    # Round head (signature)
    head_e = empty(f"{name}_he", (0, 0, 1.0*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.32*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_KOALA_GREY, scale=(1.3, 1.0, 1.1))
    # Big fluffy ears (signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.18*scale,
                      loc=(side*0.30*scale, 0, 0.20*scale), parent=head_e,
                      mat_=M_KOALA_GREY, scale=(1.3, 0.5, 1.0))
        # Inner pink
        smooth_sphere(f"{name}_ear_p{side}", r=0.12*scale,
                      loc=(side*0.30*scale, -0.04*scale, 0.20*scale), parent=head_e,
                      mat_=M_KOALA_EAR_PINK, scale=(1.0, 0.3, 0.8))
    # Big nose signature
    smooth_sphere(f"{name}_nose", r=0.10*scale, loc=(0, -0.30*scale, -0.05*scale),
                  parent=head_e, mat_=M_KOALA_NOSE, scale=(1.2, 0.8, 0.7))
    # Eyes closed/sleeping (signature)
    for side in (-1, 1):
        beveled_cube(f"{name}_eye{side}", (0.05*scale, 0.02*scale, 0.01*scale), bevel_offset=0.005,
                     loc=(side*0.10*scale, -0.27*scale, 0.05*scale), parent=head_e, mat_=M_KOALA_NOSE)
    # Arms gripping branch
    for side in (-1, 1):
        cyl(f"{name}_arm{side}", r=0.10*scale, depth=0.40*scale, segs=10,
            loc=(side*0.28*scale, -0.10*scale, 0.5*scale), parent=base, mat_=M_KOALA_GREY).rotation_euler = (math.radians(-30), 0, math.radians(side*-20))
    return {"root": base}

koalas = []
# Place koalas in trees
koala_in_trees = [(-35, -25, 4.5), (35, -25, 4.5), (-40, 0, 4.5), (-20, 40, 4.5)]
for i, (kx, ky, kz) in enumerate(koala_in_trees):
    k = make_koala(f"koala{i}", (kx, ky, kz), scale=0.6, facing=math.radians(random.uniform(0, 360)))
    koalas.append(k)

# ============ DINGO (signature wild dog) ============
dingo_e = empty("dingo", loc=(-10, 18, 0))
dingo_e.rotation_euler = (0, 0, math.radians(45))
# Body
smooth_sphere("d_body", r=0.40, segs=18, rings=12, loc=(0, 0, 0.85),
              parent=dingo_e, mat_=M_DINGO, scale=(1.6, 1.0, 1.0))
# Belly
smooth_sphere("d_belly", r=0.32, loc=(0, 0, 0.65), parent=dingo_e, mat_=M_DINGO_LIGHT,
              scale=(1.3, 0.8, 0.6))
# 4 legs
for x in (-1, 1):
    for y in (-1, 1):
        cyl(f"d_l{x}{y}", r=0.06, depth=0.85, segs=10, loc=(x*0.4, y*0.30, 0.42),
            parent=dingo_e, mat_=M_DINGO)
# Head
head_d_e = empty("d_he", (0.8, 0, 0.95), parent=dingo_e)
smooth_sphere("d_head", r=0.22, segs=18, rings=14, loc=(0, 0, 0),
              parent=head_d_e, mat_=M_DINGO, scale=(1.5, 0.9, 0.9))
# Pointed snout
smooth_sphere("d_snout", r=0.15, loc=(0.30, 0, -0.05),
              parent=head_d_e, mat_=M_DINGO, scale=(1.4, 0.7, 0.7))
# Nose
smooth_sphere("d_nose", r=0.05, loc=(0.45, 0, -0.02), parent=head_d_e, mat_=M_KOALA_NOSE)
# Pointed ears (signature)
for side in (-1, 1):
    ear = smooth_cone(f"d_ear{side}", r1=0.10, r2=0.01, depth=0.30, segs=10,
                      loc=(-0.05, side*0.15, 0.25), parent=head_d_e, mat_=M_DINGO)
    ear.rotation_euler = (math.radians(-10), 0, math.radians(side*15))
# Eyes (glowing red signature predator)
for side in (-1, 1):
    smooth_sphere(f"d_eye{side}", r=0.04, loc=(0.05, side*0.15, 0.10),
                  parent=head_d_e, mat_=M_EYE_GLOW_RED)
# Tail
cyl("d_tail", r=0.04, depth=0.7, segs=8, loc=(-0.8, 0, 0.95),
    parent=dingo_e, mat_=M_DINGO).rotation_euler = (math.radians(60), 0, 0)

# ============ PYTHON SNAKE coiled (signature) ============
python_e = empty("python", loc=(8, 5, 0))
# Coiled segments (signature spiral)
for ci in range(15):
    ca = ci * 0.5
    radius_p = 1.5 - ci * 0.08
    cx_p = math.cos(ca) * radius_p
    cy_p = math.sin(ca) * radius_p
    cz_p = ci * 0.08
    smooth_sphere(f"py_c{ci}", r=0.18, segs=14, rings=10,
                  loc=(cx_p, cy_p, cz_p + 0.15),
                  parent=python_e, mat_=M_PYTHON_GREEN if ci % 2 == 0 else M_PYTHON_BROWN)
# Head raised
py_head_e = empty("py_he", (1.5, 0, 1.5), parent=python_e)
smooth_sphere("py_head", r=0.25, segs=18, rings=14, loc=(0, 0, 0),
              parent=py_head_e, mat_=M_PYTHON_GREEN, scale=(1.4, 0.85, 0.7))
# Forked tongue
beveled_cube("py_tongue", (0.04, 0.10, 0.02), bevel_offset=0.005, loc=(0.20, 0, -0.05),
             parent=py_head_e, mat_=M_DOT_RED)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"py_eye{side}", r=0.04, loc=(0.08, side*0.15, 0.06),
                  parent=py_head_e, mat_=M_EYE_GLOW_RED)

# ============ BONFIRE CAMP (signature) ============
fire_e = empty("camp_fire", (0, -5, 0))
# Stone ring
for si in range(10):
    sa = (si / 10.0) * math.pi * 2
    smooth_sphere(f"fs{si}", r=0.30, loc=(math.cos(sa)*1.5, math.sin(sa)*1.5, 0.20),
                  parent=fire_e, mat_=M_ULURU_DARK)
# Burning logs
for li in range(5):
    la = (li / 5.0) * math.pi
    cyl(f"fl{li}", r=0.10, depth=1.5, segs=10, loc=(0, 0, 0.25),
        parent=fire_e, mat_=M_LOG_FIRE).rotation_euler = (math.radians(90), 0, la*math.pi/2.5)
# Flames (signature)
flame_e = empty("cf_flame", (0, 0, 0.4), parent=fire_e)
smooth_cone("cf_fo", r1=0.6, r2=0.08, depth=2.5, segs=14, loc=(0, 0, 1.2), parent=flame_e, mat_=M_FIRE_OUTER)
smooth_cone("cf_fc", r1=0.4, r2=0.03, depth=2.0, segs=14, loc=(0, 0, 1.0), parent=flame_e, mat_=M_FIRE_CORE)

# Embers floating up
embers_anim = []
for ei in range(20):
    eax = random.uniform(-0.5, 0.5); eay = random.uniform(-0.5, 0.5)
    eaz = random.uniform(0.5, 2.0)
    e = smooth_sphere(f"ember{ei}", r=0.04, segs=8, rings=6,
                      loc=(eax, eay, eaz), parent=fire_e, mat_=M_EMBER)
    e["_phase"] = random.uniform(0, math.pi*2)
    embers_anim.append(e)

# ============ DOT PAINTING on ground signature ============
# Aboriginal rock art pattern (concentric circles signature)
art_e = empty("art", (-5, -2, 0))
# Concentric rings of dots
for ring in range(5):
    rr = 0.5 + ring * 0.4
    n_dots = 8 + ring * 4
    for di in range(n_dots):
        da = (di / n_dots) * math.pi * 2
        smooth_sphere(f"art_r{ring}_{di}", r=0.06,
                      loc=(math.cos(da)*rr, math.sin(da)*rr, 0.20),
                      parent=art_e, mat_=DOT_COLORS[ring % len(DOT_COLORS)])
# Center
smooth_sphere("art_c", r=0.12, loc=(0, 0, 0.20), parent=art_e, mat_=M_DOT_RED)
# Path of dots (dreamtime line)
for pi in range(15):
    pa = (pi / 15.0) * math.pi * 2
    pr = 3 + pi * 0.5
    smooth_sphere(f"art_p{pi}", r=0.05,
                  loc=(math.cos(pa)*pr, math.sin(pa)*pr, 0.20),
                  parent=art_e, mat_=random.choice(DOT_COLORS))

# ============================================================
# ⭐ 600 MILKY WAY STARS + 400 RED SAND (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
mw_particles = []
for i in range(600):
    px = random.uniform(-150, 150)
    py = random.uniform(-150, 150)
    pz = random.uniform(35, 100)
    star_col = random.choice(M_STAR_VARIANTS)
    star_obj = smooth_sphere(f"mw_st{i}", r=random.uniform(0.10, 0.25), segs=8, rings=6,
                             loc=(px, py, pz), mat_=star_col)
    star_obj["_phase"] = random.uniform(0, math.pi*2)
    star_obj["_base_x"] = px; star_obj["_base_y"] = py; star_obj["_base_z"] = pz
    star_obj["_amp"] = random.uniform(0.5, 1.2)
    star_obj["_speed"] = random.uniform(0.8, 2.5)
    mw_particles.append(star_obj)

# 400 red sand drifting
sand_particles = []
for i in range(400):
    px = random.uniform(-60, 60)
    py = random.uniform(-60, 60)
    pz = random.uniform(0.3, 6)
    s_obj = smooth_sphere(f"sand{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6,
                          loc=(px, py, pz), mat_=M_OCHER_BRIGHT, scale=(1.2, 1, 0.5))
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(1.5, 3.5)
    s_obj["_amp_y"] = random.uniform(1.5, 3.5)
    s_obj["_amp_z"] = random.uniform(0.3, 0.8)
    s_obj["_speed"] = random.uniform(0.4, 1.0)
    sand_particles.append(s_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Aborigines dance
for a in aborigines:
    phase = a["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        a["root"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(5), 0,
                                     a["root"].rotation_euler.z)
        a["root"].location.z = abs(math.sin(t * 2.5 + phase)) * 0.10
        a["root"].keyframe_insert("rotation_euler", frame=f)
        a["root"].keyframe_insert("location", frame=f)
        # Head bob
        a["he"].rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(15))
        a["he"].keyframe_insert("rotation_euler", frame=f)

# Didgeridoos vibrate (signature deep tone)
for didge in [didge1_e, didge2_e]:
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        sc_d = 1 + math.sin(t * 8.0) * 0.03
        didge.scale = (sc_d, 1, sc_d)
        didge.keyframe_insert("scale", frame=f)

# Boomerang spinning
for f in range(1, total_frames + 1, 2):
    t = (f - 1) / fps
    boom_e.rotation_euler = (math.radians(60), 0, math.radians(45) + t * 8)
    boom_e.keyframe_insert("rotation_euler", frame=f)

# Kangaroos hop
for k in kangaroos:
    phase = k["root"]["_phase"]; speed = k["root"]["_speed"]
    bx_k = k["root"].location.x; by_k = k["root"].location.y
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Hop forward + bounce
        k["root"].location.x = bx_k + math.sin(t * speed + phase) * 1.5
        k["root"].location.y = by_k + math.cos(t * speed + phase) * 1.5
        k["root"].location.z = abs(math.sin(t * speed * 2.0 + phase)) * 0.8
        k["root"].rotation_euler = (math.sin(t * speed * 2.0 + phase) * math.radians(15), 0,
                                     k["root"].rotation_euler.z)
        k["root"].keyframe_insert("location", frame=f)
        k["root"].keyframe_insert("rotation_euler", frame=f)
        # Tail counter-balance
        k["tail"].rotation_euler = (math.radians(-30) + math.sin(t * speed * 2.0 + phase) * math.radians(20), 0, 0)
        k["tail"].keyframe_insert("rotation_euler", frame=f)

# Wallabies hop
for w in wallabies:
    phase = w["root"]["_phase"]
    bx_w = w["root"].location.x; by_w = w["root"].location.y
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        w["root"].location.z = abs(math.sin(t * 3.0 + phase)) * 0.5
        w["root"].location.x = bx_w + math.sin(t * 1.5 + phase) * 1.0
        w["root"].location.y = by_w + math.cos(t * 1.5 + phase) * 0.8
        w["root"].keyframe_insert("location", frame=f)

# Emus head pick + walk
for e in emus:
    phase = e["root"]["_phase"]
    bx_e = e["root"].location.x; by_e = e["root"].location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        e["root"].location.x = bx_e + math.sin(t * 0.8 + phase) * 0.5
        e["root"].location.y = by_e + math.cos(t * 0.8 + phase) * 0.5
        e["root"].keyframe_insert("location", frame=f)
        e["neck"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(20), 0,
                                     math.cos(t * 1.5 + phase) * math.radians(15))
        e["neck"].keyframe_insert("rotation_euler", frame=f)

# Eucalyptus sway
for eu in eucalyptus:
    phase = eu["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        eu["root"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3),
                                      math.cos(t * 0.8 + phase) * math.radians(3), 0)
        eu["root"].keyframe_insert("rotation_euler", frame=f)

# Fire flames flicker
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    sc_fl = 1 + math.sin(t * 6.0) * 0.15
    flame_e.scale = (1 + math.cos(t * 5.0) * 0.10, 1 + math.sin(t * 5.0) * 0.10, sc_fl)
    flame_e.rotation_euler = (0, 0, math.sin(t * 4.0) * 0.2)
    flame_e.keyframe_insert("scale", frame=f)
    flame_e.keyframe_insert("rotation_euler", frame=f)

# Embers float up
for em in embers_anim:
    phase = em["_phase"]
    bx_e2 = em.location.x; by_e2 = em.location.y; bz_e2 = em.location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        em.location.x = bx_e2 + math.sin(t * 2.0 + phase) * 0.3
        em.location.y = by_e2 + math.cos(t * 2.0 + phase) * 0.3
        em.location.z = bz_e2 + (t * 2.0) % 5
        em.keyframe_insert("location", frame=f)

# 600 Milky Way stars twinkle (signature)
for s in mw_particles:
    phase = s["_phase"]; speed = s["_speed"]; amp = s["_amp"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        # Twinkle scale
        s_t = 0.5 + abs(math.sin(t * speed + phase)) * 1.5
        s.scale = (s_t, s_t, s_t)
        s.keyframe_insert("scale", frame=f)

# 400 red sand drift
for sa in sand_particles:
    phase = sa["_phase"]; speed = sa["_speed"]
    bx, by, bz = sa["_base_x"], sa["_base_y"], sa["_base_z"]
    ax, ay, az = sa["_amp_x"], sa["_amp_y"], sa["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        sa.location = (x, y, max(0.2, z))
        sa.keyframe_insert("location", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_outback_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_australian_outback_aboriginal_uluru] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_australian_outback_aboriginal_uluru] Uluru sacred rock + Milky Way + 4 aborigines body-painted + 2 didgeridoos + boomerang + 6 kangaroos + 4 wallabies + 3 emus + 4 koalas + dingo + python + 8 eucalyptus + bonfire + dot painting + 600 MW stars + 400 red sand")
print("⭐ FIXES: 1 ground + 600 Milky Way stars + 400 red sand (signature Outback thematic mandatory) ⭐")
