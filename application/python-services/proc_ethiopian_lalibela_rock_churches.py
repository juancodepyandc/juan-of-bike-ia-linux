"""
proc_ethiopian_lalibela_rock_churches.py — 282e procédural AuroraIA (147e qualité)
Ethiopia Lalibela rock churches: Bete Giyorgis cross church + 4 other rock churches + 4 priests white turbans + 4 pilgrims shamma + Ethiopia flag + 600 gold crosses + 400 white pilgrims
FIXES : 1 ground red tuf rock + signature crosses + pilgrims
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB282)

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

# Sky African highlands
M_SKY = mat("sky", (0.55, 0.72, 0.92, 1.0), 0.0, 0.7, emission=(0.55,0.70,0.90), emission_strength=1.8)
M_SKY_LOW = mat("sky_l", (0.95, 0.82, 0.62, 1.0), 0.0, 0.7, emission=(0.92,0.80,0.62), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.90, 0.55, 1.0), 0.0, 0.1, emission=(1.0,0.90,0.55), emission_strength=18.0)

# Red volcanic tuf rock (signature carved from)
M_TUF_RED = mat("tr", (0.72, 0.40, 0.28, 1.0), 0.0, 0.85, emission=(0.70,0.40,0.28), emission_strength=0.4)
M_TUF_DARK = mat("td", (0.52, 0.28, 0.18, 1.0), 0.0, 0.92)
M_TUF_LIGHT = mat("tl", (0.85, 0.55, 0.40, 1.0), 0.0, 0.80, emission=(0.82,0.55,0.40), emission_strength=0.5)
M_TUF_ORANGE = mat("to", (0.82, 0.48, 0.30, 1.0), 0.0, 0.85, emission=(0.80,0.48,0.30), emission_strength=0.4)
M_TUF_DUST = mat("tdu", (0.92, 0.62, 0.45, 1.0), 0.0, 0.92, emission=(0.88,0.60,0.42), emission_strength=0.5)

# Pilgrim white robes (signature shamma)
M_SHAMMA_WHITE = mat("sw", (0.95, 0.93, 0.88, 1.0), 0.0, 0.55, emission=(0.92,0.90,0.85), emission_strength=0.5)
M_SHAMMA_CREAM = mat("sc", (0.92, 0.88, 0.78, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.78), emission_strength=0.4)
M_SHAMMA_BORDER = mat("sb", (0.55, 0.18, 0.20, 1.0), 0.0, 0.55, emission=(0.52,0.18,0.20), emission_strength=0.5)
M_SHAMMA_GREEN = mat("sg", (0.20, 0.55, 0.32, 1.0), 0.0, 0.55, emission=(0.20,0.52,0.30), emission_strength=0.5)
M_SHAMMA_GOLD = mat("sgo", (0.95, 0.78, 0.30, 1.0), 0.3, 0.30, emission=(0.92,0.75,0.30), emission_strength=0.7)

# Skin Ethiopian
M_SKIN_DARK = mat("sk", (0.42, 0.28, 0.20, 1.0), 0.0, 0.55, emission=(0.40,0.28,0.20), emission_strength=0.3)
M_HAIR_BLACK = mat("hb", (0.10, 0.08, 0.06, 1.0), 0.0, 0.85)

# Turban (signature priest)
M_TURBAN_WHITE = mat("tw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.88), emission_strength=0.5)
M_TURBAN_GOLD = mat("tg", (0.95, 0.78, 0.30, 1.0), 0.4, 0.30, emission=(0.92,0.75,0.30), emission_strength=0.8)

# Cross (signature gold processional)
M_CROSS_GOLD = mat("cg", (1.0, 0.82, 0.20, 1.0), 0.9, 0.10, emission=(0.95,0.80,0.20), emission_strength=2.5)
M_CROSS_DARK = mat("cd", (0.85, 0.62, 0.18, 1.0), 0.8, 0.20, emission=(0.82,0.62,0.18), emission_strength=1.5)
M_CROSS_SILVER = mat("cs", (0.85, 0.85, 0.85, 1.0), 0.9, 0.20, emission=(0.82,0.82,0.82), emission_strength=1.5)

# Stick/staff
M_STAFF_WOOD = mat("st", (0.42, 0.28, 0.18, 1.0), 0.0, 0.75)

# Ethiopia flag
M_FLAG_GREEN = mat("fg", (0.30, 0.68, 0.30, 1.0), 0.0, 0.45, emission=(0.30,0.65,0.30), emission_strength=1.0)
M_FLAG_YELLOW = mat("fy", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.20), emission_strength=1.2)
M_FLAG_RED = mat("fr2", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=1.0)
M_FLAG_BLUE = mat("fb2", (0.18, 0.42, 0.78, 1.0), 0.0, 0.45, emission=(0.18,0.42,0.75), emission_strength=1.0)
M_FLAG_STAR = mat("fs", (1.0, 0.85, 0.20, 1.0), 0.0, 0.30, emission=(0.95,0.82,0.20), emission_strength=3.0)

# Cross particles (orthodox signature)
M_CROSS_PT_GOLD = mat("cptg", (1.0, 0.82, 0.20, 1.0), 0.9, 0.10, emission=(0.95,0.80,0.20), emission_strength=3.0)
M_CROSS_PT_SILVER = mat("cpts", (0.92, 0.92, 0.92, 1.0), 0.9, 0.10, emission=(0.88,0.88,0.88), emission_strength=2.5)
M_CROSS_PT_ROSE = mat("cptr", (0.92, 0.72, 0.45, 1.0), 0.6, 0.20, emission=(0.88,0.70,0.45), emission_strength=2.0)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Smoke/incense
M_SMOKE = mat("sm", (0.92, 0.85, 0.78, 1.0), 0.0, 0.95, emission=(0.88,0.82,0.78), emission_strength=0.8, alpha=0.45)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-50, 100, 40), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-50, 100, 40), mat_=M_SUN)

# ============ ONE clean red tuf ground ============
ground = beveled_cube("ground", (280, 280, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_TUF_RED)
# Rock outcrops scattered
for ri in range(200):
    a = random.uniform(0, math.pi*2); rad = random.uniform(5, 130)
    smooth_sphere(f"rk{ri}", r=random.uniform(0.6, 1.5), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.12),
                  mat_=M_TUF_DARK if ri % 3 == 0 else (M_TUF_LIGHT if ri % 3 == 1 else M_TUF_ORANGE),
                  scale=(1.4, 1.3, 0.22))
# Dust patches
for di in range(50):
    smooth_sphere(f"dust{di}", r=random.uniform(0.5, 1.0), segs=10, rings=6,
                  loc=(random.uniform(-110, 110), random.uniform(-110, 110), 0.10),
                  mat_=M_TUF_DUST, scale=(1.5, 1.4, 0.18))

# ============ BETE GIYORGIS (signature monolithic cross-shaped church) ============
giyorgis_e = empty("giyorgis", (0, 0, 0))
# Carved sunken pit (signature - church is carved DOWN into rock)
# Outer trench rim
for ti in range(16):
    ta = (ti / 16.0) * math.pi * 2
    beveled_cube(f"gy_tr{ti}", (5, 3, 8), bevel_offset=0.20,
                 loc=(math.cos(ta)*15, math.sin(ta)*15, 0), parent=giyorgis_e,
                 mat_=M_TUF_RED).rotation_euler = (0, 0, ta)
# CROSS-SHAPED CHURCH (signature - perfect Greek cross plan)
cross_h = 10
# Vertical arm (north-south)
beveled_cube("gy_v", (4, 12, cross_h), bevel_offset=0.15, loc=(0, 0, -cross_h/2 + 2),
             parent=giyorgis_e, mat_=M_TUF_ORANGE)
# Horizontal arm (east-west)
beveled_cube("gy_h", (12, 4, cross_h), bevel_offset=0.15, loc=(0, 0, -cross_h/2 + 2),
             parent=giyorgis_e, mat_=M_TUF_ORANGE)
# Stepped roof (signature)
# 3 step pyramid pattern on top
# Top arm
for step in range(4):
    sw = 4 - step * 0.6
    sl = 12 - step * 2.5
    beveled_cube(f"gy_v_t{step}", (sw, sl, 0.3), bevel_offset=0.05,
                 loc=(0, 0, 2.5 + step*0.3), parent=giyorgis_e, mat_=M_TUF_ORANGE)
for step in range(4):
    sw = 12 - step * 2.5
    sl = 4 - step * 0.6
    beveled_cube(f"gy_h_t{step}", (sw, sl, 0.3), bevel_offset=0.05,
                 loc=(0, 0, 2.5 + step*0.3), parent=giyorgis_e, mat_=M_TUF_ORANGE)
# CROSS on top of roof (signature)
cross_top_e = empty("gy_ct", (0, 0, 5), parent=giyorgis_e)
# Vertical arm of top cross
beveled_cube("gy_ct_v", (0.4, 0.4, 1.5), bevel_offset=0.04, loc=(0, 0, 0.75),
             parent=cross_top_e, mat_=M_CROSS_GOLD)
beveled_cube("gy_ct_h", (1.5, 0.4, 0.4), bevel_offset=0.04, loc=(0, 0, 1.0),
             parent=cross_top_e, mat_=M_CROSS_GOLD)
# Window openings on facade (signature carved)
for wi in range(4):
    wa = wi * math.pi / 2
    win_e = empty(f"gy_w{wi}_e", (math.cos(wa)*6, math.sin(wa)*6, 0), parent=giyorgis_e)
    win_e.rotation_euler = (0, 0, wa)
    # Window frame
    beveled_cube(f"gy_w{wi}", (0.4, 0.4, 2), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=win_e, mat_=M_TUF_DARK)
    # Cross-window (signature)
    beveled_cube(f"gy_w{wi}_v", (0.10, 0.41, 1.8), bevel_offset=0.02, loc=(0, -0.01, 0),
                 parent=win_e, mat_=M_TUF_DARK)
    beveled_cube(f"gy_w{wi}_h", (0.10, 0.41, 0.5), bevel_offset=0.02, loc=(0, -0.01, 0.5),
                 parent=win_e, mat_=M_TUF_DARK)
# Doors at base of each arm
for di in range(4):
    da = di * math.pi / 2
    beveled_cube(f"gy_d{di}", (0.8, 0.30, 2), bevel_offset=0.05,
                 loc=(math.cos(da)*4.5, math.sin(da)*4.5, -3),
                 parent=giyorgis_e, mat_=M_TUF_DARK).rotation_euler = (0, 0, da)
# Decorative arches and lintels (signature)
for ai in range(8):
    ang = ai * math.pi / 4
    cyl(f"gy_ar{ai}", r=0.15, depth=1.5, segs=10,
        loc=(math.cos(ang)*5, math.sin(ang)*5, 0), parent=giyorgis_e, mat_=M_TUF_LIGHT)

# ============ 4 OTHER ROCK-HEWN CHURCHES (signature monolithic) ============
def make_rock_church(name, loc, size, height):
    base = empty(name, loc)
    # Sunken trench
    for ti in range(8):
        ta = (ti / 8.0) * math.pi * 2
        beveled_cube(f"{name}_tr{ti}", (size + 2, 2, height*0.8), bevel_offset=0.10,
                     loc=(math.cos(ta)*(size+2.5), math.sin(ta)*(size+2.5), -height/2),
                     parent=base, mat_=M_TUF_RED).rotation_euler = (0, 0, ta)
    # Main church body
    beveled_cube(f"{name}_b", (size, size, height), bevel_offset=0.20,
                 loc=(0, 0, -height/2 + 2), parent=base, mat_=M_TUF_ORANGE)
    # Roof tiers (signature)
    for ti_r in range(3):
        ts = size - ti_r * 1
        beveled_cube(f"{name}_rt{ti_r}", (ts, ts, 0.4), bevel_offset=0.06,
                     loc=(0, 0, 2.2 + ti_r * 0.4), parent=base, mat_=M_TUF_LIGHT)
    # Front pillars (signature)
    for ci in range(4):
        cyl(f"{name}_c{ci}", r=0.30, depth=height*0.7, segs=10,
            loc=(-size/2 + 0.5 + ci*((size-1)/3), -size/2 - 0.3, -height/2 + height*0.35),
            parent=base, mat_=M_TUF_ORANGE)
    # Windows
    for fi in (-1, 1):
        for wi in range(3):
            beveled_cube(f"{name}_w{fi}_{wi}", (0.4, 0.20, 1.2), bevel_offset=0.04,
                         loc=(fi*size/2, -size/2 + 0.5 + wi*((size-1)/2), 0.5),
                         parent=base, mat_=M_TUF_DARK)
    # Cross on top
    cross_e = empty(f"{name}_cr", (0, 0, 3.5), parent=base)
    beveled_cube(f"{name}_cr_v", (0.3, 0.3, 1.2), bevel_offset=0.03, loc=(0, 0, 0.6),
                 parent=cross_e, mat_=M_CROSS_GOLD)
    beveled_cube(f"{name}_cr_h", (1.2, 0.3, 0.3), bevel_offset=0.03, loc=(0, 0, 0.8),
                 parent=cross_e, mat_=M_CROSS_GOLD)
    return base

other_church_pos = [(-30, 35, 9, 8), (30, 35, 8, 7),
                     (-30, -35, 9, 8), (30, -35, 8, 7)]
for i, (cx, cy, csz, chh) in enumerate(other_church_pos):
    make_rock_church(f"rc{i}", (cx, cy, 0), csz, chh)

# ============ 4 ORTHODOX PRIESTS (signature white robes + turban) ============
def make_priest(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long white robe (signature kaba)
    smooth_cone(f"{name}_ro", r1=0.32, r2=0.50, depth=1.85, segs=14, loc=(0, 0, 0.95),
                parent=base, mat_=M_SHAMMA_WHITE)
    # Gold sash/embroidery
    cyl(f"{name}_sa", r=0.40, depth=0.10, segs=14, loc=(0, 0, 0.95),
        parent=base, mat_=M_SHAMMA_GOLD)
    # Red border on robe hem (signature)
    cyl(f"{name}_he", r=0.51, depth=0.08, segs=14, loc=(0, 0, 0.10),
        parent=base, mat_=M_SHAMMA_BORDER)
    # Sandals
    for side in (-1, 1):
        beveled_cube(f"{name}_sd{side}", (0.10, 0.22, 0.04), bevel_offset=0.01,
                     loc=(side*0.13, 0.04, 0.03), parent=base, mat_=M_HAIR_BLACK)
    # Arms holding processional cross
    sh_l = empty(f"{name}_a0", (-0.30, 0, 1.55), parent=base)
    sh_l.rotation_euler = (math.radians(-70), 0, math.radians(20))
    cyl(f"{name}_ua0", r=0.08, depth=0.45, segs=10, loc=(0, 0, -0.22),
        parent=sh_l, mat_=M_SHAMMA_WHITE)
    cyl(f"{name}_fa0", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_SKIN_DARK)
    sh_r = empty(f"{name}_a1", (0.30, 0, 1.55), parent=base)
    sh_r.rotation_euler = (math.radians(-100), 0, math.radians(-20))
    cyl(f"{name}_ua1", r=0.08, depth=0.45, segs=10, loc=(0, 0, -0.22),
        parent=sh_r, mat_=M_SHAMMA_WHITE)
    cyl(f"{name}_fa1", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_SKIN_DARK)
    # PROCESSIONAL CROSS (signature Ethiopian elaborate)
    cross_p_e = empty(f"{name}_pc", (0.25, 0, 0.30), parent=sh_r)
    # Staff
    cyl(f"{name}_pc_s", r=0.025, depth=2.0, segs=10, loc=(0, 0, 0),
        parent=cross_p_e, mat_=M_STAFF_WOOD)
    # Cross head (elaborate signature Lalibela)
    cross_h_e = empty(f"{name}_pc_h", (0, 0, 1.10), parent=cross_p_e)
    # Main cross
    beveled_cube(f"{name}_pc_v", (0.10, 0.10, 0.35), bevel_offset=0.02, loc=(0, 0, 0.18),
                 parent=cross_h_e, mat_=M_CROSS_GOLD)
    beveled_cube(f"{name}_pc_h2", (0.35, 0.10, 0.10), bevel_offset=0.02, loc=(0, 0, 0.20),
                 parent=cross_h_e, mat_=M_CROSS_GOLD)
    # Decorative arms (signature 4 corners with ornaments)
    for cri in range(4):
        cra = (cri / 4.0) * math.pi * 2 + math.pi/4
        smooth_sphere(f"{name}_pc_o{cri}", r=0.05,
                      loc=(math.cos(cra)*0.18, 0, math.sin(cra)*0.18 + 0.20),
                      parent=cross_h_e, mat_=M_CROSS_GOLD)
    # Circle of cross (signature)
    cyl(f"{name}_pc_c", r=0.22, depth=0.04, segs=14, loc=(0, 0, 0.20),
        parent=cross_h_e, mat_=M_CROSS_GOLD).rotation_euler = (math.radians(90), 0, 0)
    # Head
    head_p_e = empty(f"{name}_he", (0, 0, 2.0), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_p_e, mat_=M_SKIN_DARK)
    # Beard
    for bi in range(15):
        ba = random.uniform(-math.pi*0.4, math.pi*0.4)
        beard_len = random.uniform(0.15, 0.30)
        for bsi in range(int(beard_len * 6)):
            cyl(f"{name}_bd{bi}_{bsi}", r=0.02, depth=0.06, segs=6,
                loc=(math.sin(ba)*0.12, -0.10, -0.10 - bsi*0.06),
                parent=head_p_e, mat_=M_HAIR_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_p_e, mat_=M_EYE)
    # TURBAN (signature white)
    turban_e = empty(f"{name}_tu", (0, 0, 0.20), parent=head_p_e)
    cyl(f"{name}_tu_c", r=0.22, depth=0.18, segs=14, loc=(0, 0, 0),
        parent=turban_e, mat_=M_TURBAN_WHITE)
    # Top dome of turban
    smooth_sphere(f"{name}_tu_d", r=0.18, segs=14, rings=10, loc=(0, 0, 0.10),
                  parent=turban_e, mat_=M_TURBAN_WHITE, scale=(1, 1, 0.7))
    # Gold center signature
    smooth_sphere(f"{name}_tu_g", r=0.06, loc=(0, -0.20, 0.10),
                  parent=turban_e, mat_=M_TURBAN_GOLD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_p_e}

priests = []
priest_pos = [(-10, -12, math.radians(180)), (-3, -10, math.radians(180)),
               (3, -10, math.radians(180)), (10, -12, math.radians(180))]
for i, (px, py, fac) in enumerate(priest_pos):
    p = make_priest(f"pr{i}", (px, py, 0), facing=fac)
    priests.append(p)

# ============ 4 PILGRIMS (signature white shamma) ============
def make_pilgrim(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Shamma (white wrap)
    smooth_cone(f"{name}_sh", r1=0.32, r2=0.42, depth=1.65, segs=14, loc=(0, 0, 0.85),
                parent=base, mat_=random.choice([M_SHAMMA_WHITE, M_SHAMMA_CREAM]))
    # Red/green border (signature)
    cyl(f"{name}_he", r=0.43, depth=0.06, segs=14, loc=(0, 0, 0.05),
        parent=base, mat_=random.choice([M_SHAMMA_BORDER, M_SHAMMA_GREEN]))
    # Pants underneath
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.11, depth=0.55, segs=10,
            loc=(side*0.13, 0, 0.35), parent=base, mat_=M_TUF_DARK)
    # Bare feet
    for side in (-1, 1):
        beveled_cube(f"{name}_f{side}", (0.10, 0.22, 0.05), bevel_offset=0.01,
                     loc=(side*0.13, 0.04, 0.03), parent=base, mat_=M_SKIN_DARK)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.60), parent=base)
        sh.rotation_euler = (math.radians(-80), 0, math.radians(side*30))
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=M_SHAMMA_WHITE)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=M_SKIN_DARK)
    # Prayer book in hand
    beveled_cube(f"{name}_bk", (0.20, 0.04, 0.15), bevel_offset=0.02,
                 loc=(0.15, -0.20, 1.10), parent=base, mat_=M_TUF_DARK)
    # Head
    head_pl_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_pl_e, mat_=M_SKIN_DARK)
    # Hair
    for hi in range(12):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.08, segs=6,
            loc=(math.cos(ha)*0.13, math.sin(ha)*0.10, 0.12),
            parent=head_pl_e, mat_=M_HAIR_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_pl_e, mat_=M_EYE)
    # Forehead cross tattoo (signature)
    beveled_cube(f"{name}_tc_v", (0.025, 0.04, 0.10), bevel_offset=0.005,
                 loc=(0, -0.16, 0.08), parent=head_pl_e, mat_=M_HAIR_BLACK)
    beveled_cube(f"{name}_tc_h", (0.08, 0.04, 0.025), bevel_offset=0.005,
                 loc=(0, -0.16, 0.10), parent=head_pl_e, mat_=M_HAIR_BLACK)
    # White headcover (women signature)
    if random.random() > 0.5:
        cyl(f"{name}_cv", r=0.22, depth=0.30, segs=14, loc=(0, 0, 0.10),
            parent=head_pl_e, mat_=M_SHAMMA_WHITE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_pl_e}

pilgrims_main = []
pilgrim_pos = [(-15, 18, math.radians(180)), (-5, 20, math.radians(180)),
                (5, 20, math.radians(180)), (15, 18, math.radians(180))]
for i, (px, py, fac) in enumerate(pilgrim_pos):
    p = make_pilgrim(f"pl{i}", (px, py, 0), facing=fac)
    pilgrims_main.append(p)

# ============ ETHIOPIA FLAG (signature green/yellow/red + blue circle star) ============
flag_e = empty("flag", (-55, -50, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_HAIR_BLACK)
# 3 horizontal stripes
beveled_cube("fl_g", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 11.5),
             parent=flag_e, mat_=M_FLAG_GREEN)
beveled_cube("fl_y", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 10.65),
             parent=flag_e, mat_=M_FLAG_YELLOW)
beveled_cube("fl_r", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 9.80),
             parent=flag_e, mat_=M_FLAG_RED)
# Blue circle (signature)
smooth_sphere("fl_c", r=0.65, segs=18, rings=14, loc=(2, -0.06, 10.65),
              parent=flag_e, mat_=M_FLAG_BLUE)
# 5-point yellow star (signature)
star_e = empty("fl_st", (2, -0.10, 10.65), parent=flag_e)
for sp in range(5):
    spa = (sp / 5.0) * math.pi * 2 + math.pi/2
    beveled_cube(f"fl_st_p{sp}", (0.04, 0.06, 0.30), bevel_offset=0.005,
                 loc=(math.cos(spa)*0.20, 0, math.sin(spa)*0.20),
                 parent=star_e, mat_=M_FLAG_STAR).rotation_euler = (spa - math.pi/2, 0, 0)
smooth_sphere("fl_stc", r=0.10, loc=(0, 0, 0), parent=star_e, mat_=M_FLAG_STAR)
# Sun rays radiating from star
for ri in range(5):
    rang = (ri / 5.0) * math.pi * 2 + math.pi/2
    beveled_cube(f"fl_sr{ri}", (0.03, 0.05, 0.18), bevel_offset=0.005,
                 loc=(math.cos(rang)*0.40, -0.05, math.sin(rang)*0.40),
                 parent=star_e, mat_=M_FLAG_STAR).rotation_euler = (rang - math.pi/2, 0, 0)
flag_e["_phase"] = 0

# ============================================================
# 600 GOLD CROSSES + 400 WHITE PILGRIMS (PARTICULES SIGNATURES)
# ============================================================
crosses = []
for i in range(600):
    px = random.uniform(-110, 110)
    py = random.uniform(-110, 110)
    pz = random.uniform(3, 28)
    c_col = random.choice([M_CROSS_PT_GOLD, M_CROSS_PT_SILVER, M_CROSS_PT_ROSE])
    c_e = empty(f"cr{i}", (px, py, pz))
    # Vertical arm
    beveled_cube(f"cr{i}_v", (0.05, 0.05, 0.30), bevel_offset=0.01, loc=(0, 0, 0.05),
                 parent=c_e, mat_=c_col)
    # Horizontal arm
    beveled_cube(f"cr{i}_h", (0.22, 0.05, 0.05), bevel_offset=0.01, loc=(0, 0, 0.10),
                 parent=c_e, mat_=c_col)
    # Decorative orbs at tips (signature Lalibela cross style)
    for tp in range(4):
        tpa = (tp / 4.0) * math.pi * 2
        smooth_sphere(f"cr{i}_o{tp}", r=0.022,
                      loc=(math.cos(tpa)*0.13 if tp < 2 else math.cos(tpa)*0.03,
                           0,
                           math.sin(tpa)*0.13 + 0.10 if tp >= 2 else math.sin(tpa)*0.13 + 0.10),
                      parent=c_e, mat_=c_col)
    # Center jewel
    smooth_sphere(f"cr{i}_j", r=0.025, loc=(0, 0, 0.10),
                  parent=c_e, mat_=c_col)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    c_e["_base_x"] = px; c_e["_base_y"] = py; c_e["_base_z"] = pz
    c_e["_amp_x"] = random.uniform(0.5, 1.5)
    c_e["_amp_y"] = random.uniform(0.5, 1.5)
    c_e["_amp_z"] = random.uniform(0.4, 1.0)
    c_e["_speed"] = random.uniform(0.4, 1.0)
    crosses.append(c_e)

# 400 mini white pilgrims walking
mini_pilgrims = []
for i in range(400):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = 0.6
    mp_e = empty(f"mp{i}", (px, py, pz))
    # White robe figure
    smooth_cone(f"mp{i}_b", r1=0.10, r2=0.13, depth=0.40, segs=10, loc=(0, 0, 0.20),
                parent=mp_e, mat_=M_SHAMMA_WHITE)
    # Head
    smooth_sphere(f"mp{i}_h", r=0.07, segs=8, rings=6, loc=(0, 0, 0.50),
                  parent=mp_e, mat_=M_SKIN_DARK)
    # White head cover
    cyl(f"mp{i}_hc", r=0.08, depth=0.05, segs=10, loc=(0, 0, 0.55),
        parent=mp_e, mat_=M_SHAMMA_WHITE)
    # Glowing aura
    smooth_sphere(f"mp{i}_au", r=0.20, segs=10, rings=8, loc=(0, 0, 0.30),
                  parent=mp_e, mat_=M_SHAMMA_GOLD, scale=(1, 1, 0.6))
    mp_e["_phase"] = random.uniform(0, math.pi*2)
    mp_e["_base_x"] = px; mp_e["_base_y"] = py
    mp_e["_speed"] = random.uniform(0.4, 0.9)
    mp_e["_direction"] = random.uniform(0, math.pi*2)
    mini_pilgrims.append(mp_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Priests sway (chanting/processional)
for p in priests:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        p["root"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(2), 0,
                                     p["root"].rotation_euler.z)
        p["root"].location.z = abs(math.sin(t * 1.0 + phase)) * 0.10
        p["root"].keyframe_insert("rotation_euler", frame=f)
        p["root"].keyframe_insert("location", frame=f)
        p["he"].rotation_euler = (math.sin(t * 1.2 + phase) * math.radians(4), 0,
                                   math.cos(t * 1.0 + phase) * math.radians(10))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Pilgrims sway in prayer
for p in pilgrims_main:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        p["root"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(2), 0,
                                     p["root"].rotation_euler.z)
        p["root"].keyframe_insert("rotation_euler", frame=f)
        p["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3), 0, 0)
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 crosses float multi-axis with spin
for c in crosses:
    phase = c["_phase"]; speed = c["_speed"]
    bx, by, bz = c["_base_x"], c["_base_y"], c["_base_z"]
    ax, ay, az = c["_amp_x"], c["_amp_y"], c["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase) + t * 0.5
        c.location = (x, y, z)
        c.rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(15), 0,
                             t * 1.0 + phase)
        c.keyframe_insert("location", frame=f)
        c.keyframe_insert("rotation_euler", frame=f)

# 400 mini pilgrims walk
for mp in mini_pilgrims:
    phase = mp["_phase"]; speed = mp["_speed"]; direction = mp["_direction"]
    bx, by = mp["_base_x"], mp["_base_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.cos(direction) * t * speed * 2
        y = by + math.sin(direction) * t * speed * 2
        z = 0.6 + abs(math.sin(t * 4.0 + phase)) * 0.10
        mp.location = (x, y, z)
        mp.rotation_euler = (0, 0, direction)
        mp.keyframe_insert("location", frame=f)
        mp.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_ethiopia_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_ethiopian_lalibela_rock_churches] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Ethiopia Lalibela: Bete Giyorgis (signature monolithic Greek cross church carved DOWN into rock) with sunken trench rim + cross-shaped body + stepped roof + cross on top + 4 cross-windows + 4 door arms + 4 rock-hewn churches (sunken trenches + roof tiers + front pillars + windows + cross tops) + 4 Orthodox priests (white kaba robes + gold sash + red hem border + elaborate processional crosses with circle + 4 orb ornaments + signature white turbans with gold center + black beards) + 4 pilgrims with shamma white wraps + colored borders + forehead cross tattoos + prayer books + Ethiopia flag (green/yellow/red + blue circle + 5-point yellow star with rays signature) + 600 gold/silver/rose crosses floating + 400 mini white pilgrims walking with golden aura")
print("✝️ FIXES: 1 red tuf rock ground + 600 orthodox crosses + 400 white pilgrims with golden auras signature ✝️")
