"""
proc_bhutan_tigers_nest_cliff_monastery.py — 298e procédural AuroraIA (163e qualité stylisé low-poly)
Bhutan Paro Taktsang Tiger's Nest cliff monastery: monastery on cliff + 4 monks + prayer wheels + Mt Jomolhari + 600 prayer flags + 400 black-necked cranes
Honest: stylized low-poly procedural (not photoreal). Applies bevel 0.15+ / segs 5+ + smooth_sphere stretched + joint spheres.
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB298)

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
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size_xyz, verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:],
                    offset=bevel_offset, segments=bevel_segments,
                    profile=0.7, affect='EDGES')
    return make_obj(name, bm, loc, parent, mat_)

def smooth_sphere(name, r=1.0, segs=28, rings=20, loc=(0,0,0), parent=None, mat_=None, scale=(1,1,1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    if scale != (1,1,1):
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    return make_obj(name, bm, loc, parent, mat_)

def smooth_cone(name, r1, r2, depth, segs=22, loc=(0,0,0), parent=None, mat_=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    return make_obj(name, bm, loc, parent, mat_)

def cyl(name, r, depth, segs=20, loc=(0,0,0), parent=None, mat_=None):
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

# Sky Himalayan dawn
M_SKY = mat("sky", (0.55, 0.72, 0.92, 1.0), 0.0, 0.7, emission=(0.55,0.70,0.90), emission_strength=1.7)
M_SKY_LOW = mat("sky_l", (0.95, 0.85, 0.65, 1.0), 0.0, 0.7, emission=(0.92,0.82,0.65), emission_strength=1.5)
M_SUN = mat("sun", (1.0, 0.92, 0.65, 1.0), 0.0, 0.1, emission=(1.0,0.92,0.65), emission_strength=15.0)
M_MIST = mat("mi", (0.92, 0.95, 0.95, 1.0), 0.0, 0.95, emission=(0.92,0.95,0.95), emission_strength=1.0, alpha=0.45)

# Ground - rocky cliff
M_CLIFF = mat("cl", (0.55, 0.50, 0.42, 1.0), 0.0, 0.88, emission=(0.52,0.48,0.42), emission_strength=0.3)
M_CLIFF_DARK = mat("cld", (0.32, 0.30, 0.28, 1.0), 0.0, 0.92)
M_CLIFF_LIGHT = mat("cll", (0.78, 0.70, 0.58, 1.0), 0.0, 0.80)

# Pine trees
M_PINE = mat("pn", (0.18, 0.38, 0.20, 1.0), 0.0, 0.75)
M_PINE_DARK = mat("pnd", (0.10, 0.25, 0.12, 1.0), 0.0, 0.85)
M_TRUNK = mat("tr", (0.32, 0.20, 0.12, 1.0), 0.0, 0.85)

# Mountain (Mt Jomolhari)
M_MOUNTAIN_DARK = mat("md", (0.32, 0.32, 0.35, 1.0), 0.0, 0.92)
M_MOUNTAIN_GRAY = mat("mg", (0.52, 0.52, 0.55, 1.0), 0.0, 0.85)
M_SNOW = mat("sn", (0.95, 0.95, 0.95, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.92), emission_strength=0.5)

# Monastery (signature white walls + red roof + gold ornaments)
M_WALL_WHITE = mat("ww", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.92,0.88,0.82), emission_strength=0.5)
M_ROOF_RED = mat("rr", (0.65, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.62,0.18,0.18), emission_strength=0.5)
M_ROOF_DARK = mat("rrd", (0.42, 0.12, 0.12, 1.0), 0.0, 0.75)
M_GOLD = mat("g", (0.95, 0.78, 0.20, 1.0), 0.8, 0.20, emission=(0.92,0.75,0.20), emission_strength=1.3)
M_WINDOW_DARK = mat("wdk", (0.20, 0.15, 0.10, 1.0), 0.0, 0.75)
M_WINDOW_GLOW = mat("wgw", (1.0, 0.85, 0.45, 1.0), 0.0, 0.10, emission=(0.95,0.82,0.45), emission_strength=4.0)
M_DOOR_RED = mat("dr", (0.55, 0.15, 0.18, 1.0), 0.0, 0.65, emission=(0.52,0.15,0.18), emission_strength=0.6)

# Monk drukpa (signature dark red robe)
M_ROBE_DRUKPA = mat("rdp", (0.55, 0.18, 0.22, 1.0), 0.0, 0.75, emission=(0.52,0.18,0.22), emission_strength=0.4)
M_ROBE_PURPLE = mat("rpu", (0.42, 0.18, 0.55, 1.0), 0.0, 0.75, emission=(0.40,0.18,0.52), emission_strength=0.4)
M_ROBE_DEEP = mat("rdp_d", (0.32, 0.10, 0.18, 1.0), 0.0, 0.85)
M_SKIN_ASIA = mat("sk", (0.85, 0.65, 0.45, 1.0), 0.0, 0.55, emission=(0.82,0.62,0.45), emission_strength=0.3)
M_HEAD_SHAVED = mat("hs", (0.78, 0.55, 0.40, 1.0), 0.0, 0.65, emission=(0.75,0.55,0.40), emission_strength=0.3)
M_HAIR_BLACK = mat("hb", (0.08, 0.06, 0.05, 1.0), 0.0, 0.85)

# Prayer wheel (signature)
M_PRAYER_GOLD = mat("pg", (0.92, 0.72, 0.20, 1.0), 0.7, 0.30, emission=(0.88,0.70,0.20), emission_strength=1.0)
M_PRAYER_RED = mat("pr", (0.65, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.62,0.18,0.18), emission_strength=0.5)
M_WOOD = mat("w", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85)

# Buddha statue
M_BUDDHA_GOLD = mat("bg", (1.0, 0.82, 0.30, 1.0), 0.9, 0.10, emission=(0.95,0.80,0.30), emission_strength=1.5)
M_BUDDHA_DARK = mat("bd", (0.55, 0.42, 0.15, 1.0), 0.5, 0.40)

# Bhutan flag
M_FLAG_YELLOW = mat("fy", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.20), emission_strength=1.0)
M_FLAG_ORANGE = mat("fo", (1.0, 0.55, 0.18, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.18), emission_strength=1.0)
M_DRAGON_WHITE = mat("dw", (0.95, 0.95, 0.92, 1.0), 0.2, 0.30, emission=(0.92,0.92,0.90), emission_strength=1.2)

# Prayer flag colors (signature 5)
M_PF_BLUE = mat("pfb", (0.20, 0.45, 0.85, 1.0), 0.0, 0.45, emission=(0.20,0.42,0.82), emission_strength=2.5)
M_PF_WHITE = mat("pfw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=2.0)
M_PF_RED = mat("pfr", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=2.5)
M_PF_GREEN = mat("pfg", (0.30, 0.78, 0.32, 1.0), 0.0, 0.45, emission=(0.30,0.75,0.30), emission_strength=2.5)
M_PF_YELLOW = mat("pfy", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.20), emission_strength=2.8)
PF_COLORS = [M_PF_BLUE, M_PF_WHITE, M_PF_RED, M_PF_GREEN, M_PF_YELLOW]

# Black-necked crane (signature endangered Bhutanese)
M_CRANE_BODY = mat("cb", (0.85, 0.85, 0.85, 1.0), 0.0, 0.55, emission=(0.82,0.82,0.82), emission_strength=0.4)
M_CRANE_BLACK = mat("cbk", (0.10, 0.10, 0.12, 1.0), 0.0, 0.55, emission=(0.10,0.10,0.12), emission_strength=0.3)
M_CRANE_RED = mat("cr", (0.92, 0.20, 0.22, 1.0), 0.0, 0.30, emission=(0.88,0.20,0.22), emission_strength=1.5)
M_BEAK = mat("bk", (0.32, 0.20, 0.10, 1.0), 0.2, 0.45)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-50, 100, 40), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-50, 100, 40), mat_=M_SUN)
# Himalayan mist
for mi in range(25):
    mx = random.uniform(-130, 130); my = random.uniform(-100, 100); mz = random.uniform(15, 45)
    smooth_sphere(f"mst{mi}", r=random.uniform(3, 6), segs=14, rings=10,
                  loc=(mx, my, mz), mat_=M_MIST, scale=(2, 2, 0.4))

# ============ ONE clean rocky cliff ground ============
ground = beveled_cube("ground", (280, 280, 0.5), bevel_offset=0.15, bevel_segments=5, loc=(0, 0, -0.25), mat_=M_CLIFF)
# Rock outcrops + lichen patches via organic spheres only
for hi in range(220):
    a = random.uniform(0, math.pi*2); rad = random.uniform(3, 130)
    smooth_sphere(f"rk{hi}", r=random.uniform(0.8, 2.2), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_CLIFF_DARK if hi % 3 == 0 else (M_CLIFF_LIGHT if hi % 3 == 1 else M_CLIFF),
                  scale=(1.4, 1.3, 0.20))
# Pine trees scattered
for pi in range(40):
    a = random.uniform(0, math.pi*2); rad = random.uniform(40, 110)
    px_p = math.cos(a) * rad
    py_p = math.sin(a) * rad
    # Trunk
    cyl(f"pt{pi}", r=0.18, depth=4, segs=12, loc=(px_p, py_p, 2), mat_=M_TRUNK)
    # Conical pine layers
    for li in range(4):
        smooth_cone(f"pc{pi}_{li}", r1=1.5 - li*0.30, r2=0.8 - li*0.20, depth=1.2, segs=14,
                    loc=(px_p, py_p, 3.5 + li*0.9), mat_=M_PINE_DARK if li % 2 == 0 else M_PINE)

# ============ CLIFF FACE for monastery (signature dramatic vertical) ============
cliff_face_e = empty("cliff_face", (0, 50, 0))
# Big vertical cliff via stacked stretched spheres for organic rock
for fi in range(30):
    smooth_sphere(f"cf{fi}", r=random.uniform(3, 5), segs=16, rings=12,
                  loc=(random.uniform(-12, 12), random.uniform(-3, 3), random.uniform(2, 35)),
                  parent=cliff_face_e, mat_=M_CLIFF_DARK if fi % 2 else M_CLIFF, scale=(1.4, 1.3, 1.6))
# Cliff striations
for ci in range(15):
    ca = (ci / 15.0) * math.pi * 2
    cyl(f"cf_s{ci}", r=0.20, depth=30, segs=10,
        loc=(math.cos(ca)*9, math.sin(ca)*3, 15), parent=cliff_face_e, mat_=M_CLIFF_DARK)

# ============ MT JOMOLHARI backdrop ============
def make_mountain(name, loc, height, base_radius):
    base = empty(name, loc)
    n_layers = int(height / 4)
    for li in range(n_layers):
        lz = li * 4
        lr1 = base_radius * (1 - li / n_layers * 0.85)
        lr2 = base_radius * (1 - (li+1) / n_layers * 0.85)
        smooth_cone(f"{name}_l{li}", r1=lr1, r2=lr2, depth=4.5, segs=20,
                    loc=(0, 0, lz + 2.25), parent=base,
                    mat_=M_MOUNTAIN_DARK if li < n_layers//2 else M_MOUNTAIN_GRAY)
    # Snow cap
    snow_e = empty(f"{name}_se", (0, 0, height * 0.60), parent=base)
    for si in range(5):
        sz = si * 3
        sr = base_radius * (0.45 - si / 5 * 0.40)
        smooth_cone(f"{name}_s{si}", r1=sr + 0.3, r2=sr - 0.1, depth=3, segs=16,
                    loc=(0, 0, sz), parent=snow_e, mat_=M_SNOW)
    smooth_cone(f"{name}_pk", r1=0.4, r2=0.04, depth=2.5, segs=14,
                loc=(0, 0, height - 0.5), parent=base, mat_=M_SNOW)
    return base

make_mountain("jomolhari", (0, 110, 0), 55, 16)
make_mountain("p2", (-55, 100, 0), 38, 12)
make_mountain("p3", (55, 100, 0), 42, 13)

# ============ TIGER'S NEST MONASTERY (signature clinging to cliff) ============
monastery_e = empty("monastery", (0, 40, 25))
# Main rectangular building (white wall, smooth bevel)
beveled_cube("ms_m", (8, 5, 4), bevel_offset=0.25, bevel_segments=6, loc=(0, 0, 2), parent=monastery_e, mat_=M_WALL_WHITE)
# Lower extension
beveled_cube("ms_l", (10, 4, 3), bevel_offset=0.20, bevel_segments=5, loc=(0, -0.5, -2), parent=monastery_e, mat_=M_WALL_WHITE)
# Side building
beveled_cube("ms_s", (5, 4, 3.5), bevel_offset=0.20, bevel_segments=5, loc=(6, 0.5, -0.5), parent=monastery_e, mat_=M_WALL_WHITE)
# Wood beam bands (signature)
for bi in range(3):
    bz = -1 + bi * 1.8
    beveled_cube(f"ms_wb{bi}", (10.1, 4.1, 0.20), bevel_offset=0.06, bevel_segments=4,
                 loc=(0, 0, bz), parent=monastery_e, mat_=M_TRUNK)
# Signature RED ROOFS with golden trim
# Main roof
roof_m_e = empty("ms_rm", (0, 0, 4.5), parent=monastery_e)
beveled_cube("ms_rm_b", (9, 6, 0.50), bevel_offset=0.15, bevel_segments=5, loc=(0, 0, 0), parent=roof_m_e, mat_=M_ROOF_RED)
# Curved roof eaves (signature Bhutanese upturned)
for side in (-1, 1):
    beveled_cube(f"ms_re{side}", (1.5, 6.5, 0.30), bevel_offset=0.10, bevel_segments=4,
                 loc=(side*5.0, 0, 0.30), parent=roof_m_e, mat_=M_ROOF_DARK).rotation_euler = (0, math.radians(side*-20), 0)
# Gold decorations
for gi in range(4):
    ga = (gi / 4.0) * math.pi * 2 + math.pi/4
    smooth_sphere(f"ms_gd{gi}", r=0.30, segs=14, rings=10,
                  loc=(math.cos(ga)*3.5, math.sin(ga)*2.5, 4.8),
                  parent=monastery_e, mat_=M_GOLD)
# Gold finial centerpiece (signature)
smooth_cone("ms_fc", r1=0.40, r2=0.05, depth=2, segs=14, loc=(0, 0, 5.8), parent=monastery_e, mat_=M_GOLD)
smooth_sphere("ms_fcb", r=0.50, segs=14, rings=10, loc=(0, 0, 4.8), parent=monastery_e, mat_=M_GOLD)
# Side building roof
beveled_cube("ms_sr", (5.2, 4.2, 0.40), bevel_offset=0.10, bevel_segments=4, loc=(6, 0.5, 1.5), parent=monastery_e, mat_=M_ROOF_RED)
# Windows with glowing interior
for wi in range(8):
    wx_w = -3 + wi * 0.85
    if abs(wx_w) > 0.5:  # Skip center for door
        beveled_cube(f"ms_w{wi}", (0.50, 0.06, 0.85), bevel_offset=0.04, bevel_segments=3,
                     loc=(wx_w, -2.55, 1.5), parent=monastery_e, mat_=M_WINDOW_GLOW)
# Main door
beveled_cube("ms_d", (1.0, 0.10, 1.8), bevel_offset=0.06, bevel_segments=4,
             loc=(0, -2.55, 0.9), parent=monastery_e, mat_=M_DOOR_RED)
# Lower building windows
for wi in range(6):
    beveled_cube(f"ms_lw{wi}", (0.50, 0.06, 0.80), bevel_offset=0.04, bevel_segments=3,
                 loc=(-3.5 + wi*1.4, -2.05, -1.7), parent=monastery_e, mat_=M_WINDOW_GLOW)
# Staircase carved into cliff (signature pilgrimage path)
for si_st in range(20):
    sz_st = -25 + si_st * 1.5
    beveled_cube(f"ms_st{si_st}", (1.5, 0.8, 0.30), bevel_offset=0.06, bevel_segments=4,
                 loc=(-8 + si_st*0.5, -8 + si_st*0.4, sz_st), parent=monastery_e, mat_=M_CLIFF_LIGHT)

# Prayer flag string from monastery to cliff
pf_string_e = empty("pf_str", (0, 40, 30))
for pfi in range(40):
    pfi_t = pfi / 40.0
    # Long arc from monastery left to right
    pfx = -25 + pfi_t * 50
    pfy = math.sin(pfi_t * math.pi) * -8 - 5
    pfz = math.sin(pfi_t * math.pi) * 8
    beveled_cube(f"pf_str_{pfi}", (0.30, 0.04, 0.5), bevel_offset=0.04, bevel_segments=3,
                 loc=(pfx, pfy, pfz), parent=pf_string_e, mat_=PF_COLORS[pfi % 5])

# ============ 4 PRAYER WHEELS (signature gold cylinders) ============
def make_prayer_wheel(name, loc):
    base = empty(name, loc)
    # Wood frame
    beveled_cube(f"{name}_fr", (1.2, 0.6, 1.6), bevel_offset=0.10, bevel_segments=5,
                 loc=(0, 0, 0.8), parent=base, mat_=M_WOOD)
    # Wheel body (gold cylinder)
    cyl(f"{name}_wh", r=0.40, depth=1.0, segs=20, loc=(0, 0, 1.0),
        parent=base, mat_=M_PRAYER_GOLD)
    # Mantra inscriptions (red bands)
    for bi in range(3):
        cyl(f"{name}_b{bi}", r=0.42, depth=0.08, segs=20, loc=(0, 0, 0.7 + bi*0.30),
            parent=base, mat_=M_PRAYER_RED)
    # Top knob
    smooth_sphere(f"{name}_top", r=0.18, segs=14, rings=10, loc=(0, 0, 1.6), parent=base, mat_=M_PRAYER_GOLD)
    # Bottom knob
    smooth_sphere(f"{name}_bot", r=0.18, segs=14, rings=10, loc=(0, 0, 0.4), parent=base, mat_=M_PRAYER_GOLD)
    # Side handle bumps
    for hi in range(4):
        ha = (hi / 4.0) * math.pi * 2
        smooth_sphere(f"{name}_h{hi}", r=0.06, segs=10, rings=8,
                      loc=(math.cos(ha)*0.45, math.sin(ha)*0.45, 1.0), parent=base, mat_=M_PRAYER_GOLD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

prayer_wheels = []
for i, (px, py) in enumerate([(-20, -15), (-10, -18), (10, -18), (20, -15)]):
    pw = make_prayer_wheel(f"pw{i}", (px, py, 0))
    prayer_wheels.append(pw)

# ============ 4 BUDDHIST MONKS DRUKPA (signature dark red robes) ============
def make_monk(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body wrapped in robe (cone shape)
    smooth_cone(f"{name}_ro", r1=0.32, r2=0.42, depth=1.2, segs=18, loc=(0, 0, 0.95),
                parent=base, mat_=M_ROBE_DRUKPA)
    # Cross-body drape (signature kasaya)
    beveled_cube(f"{name}_dr", (0.55, 0.10, 0.80), bevel_offset=0.06, bevel_segments=4,
                 loc=(0, -0.30, 1.40), parent=base, mat_=M_ROBE_PURPLE)
    # Bare shoulder
    smooth_sphere(f"{name}_sh_b", r=0.16, segs=14, rings=12, loc=(0.30, 0, 1.65),
                  parent=base, mat_=M_SKIN_ASIA)
    # Lower robe band
    cyl(f"{name}_b", r=0.42, depth=0.20, segs=18, loc=(0, 0, 0.45),
        parent=base, mat_=M_ROBE_DEEP)
    # Legs (knee joints)
    for side in (-1, 1):
        leg_e = empty(f"{name}_le{side}", (side*0.12, 0, 0.60), parent=base)
        cyl(f"{name}_ul{side}", r=0.10, depth=0.40, segs=14, loc=(0, 0, -0.20),
            parent=leg_e, mat_=M_ROBE_DRUKPA)
        smooth_sphere(f"{name}_kn{side}", r=0.10, segs=12, rings=10, loc=(0, 0, -0.40),
                      parent=leg_e, mat_=M_ROBE_DRUKPA)
        cyl(f"{name}_ll{side}", r=0.08, depth=0.18, segs=14, loc=(0, 0, -0.55),
            parent=leg_e, mat_=M_ROBE_DRUKPA)
        # Foot
        smooth_sphere(f"{name}_ft{side}", r=0.10, segs=12, rings=8, loc=(0, 0.04, -0.66),
                      parent=leg_e, mat_=M_SKIN_ASIA, scale=(1, 1.4, 0.5))
    # Arms in prayer mudra (signature) - hands at chest
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.55), parent=base)
        sh.rotation_euler = (math.radians(-100), 0, math.radians(side*30))
        smooth_sphere(f"{name}_sh{side_idx}", r=0.09, segs=12, rings=10, loc=(0, 0, 0),
                      parent=sh, mat_=M_ROBE_DRUKPA)
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.35, segs=14, loc=(0, 0, -0.18),
            parent=sh, mat_=M_ROBE_DRUKPA)
        smooth_sphere(f"{name}_el{side_idx}", r=0.07, segs=12, rings=10, loc=(0, 0, -0.36),
                      parent=sh, mat_=M_ROBE_DRUKPA)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.32, segs=14, loc=(0, 0, -0.52),
            parent=sh, mat_=M_SKIN_ASIA)
        smooth_sphere(f"{name}_hd{side_idx}", r=0.07, segs=12, rings=10, loc=(0, 0, -0.70),
                      parent=sh, mat_=M_SKIN_ASIA)
    # Prayer hands together at chest (signature anjali mudra)
    smooth_sphere(f"{name}_pr", r=0.10, segs=14, rings=10, loc=(0, -0.40, 1.15),
                  parent=base, mat_=M_SKIN_ASIA, scale=(1, 0.5, 1.5))
    # Head (shaved bald)
    head_m_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=22, rings=18, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_HEAD_SHAVED)
    # Eyes (meditation closed)
    for side in (-1, 1):
        beveled_cube(f"{name}_ey{side}", (0.05, 0.04, 0.008), bevel_offset=0.005, bevel_segments=3,
                     loc=(side*0.06, -0.15, 0.03), parent=head_m_e, mat_=M_EYE)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_er{side}", r=0.05, segs=12, rings=8,
                      loc=(side*0.17, 0, 0), parent=head_m_e, mat_=M_SKIN_ASIA)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_m_e}

monks = []
for i, (mx, my, fac) in enumerate([(-12, -8, math.radians(0)), (-4, -10, math.radians(0)),
                                     (4, -10, math.radians(0)), (12, -8, math.radians(0))]):
    m = make_monk(f"mk{i}", (mx, my, 0), facing=fac)
    monks.append(m)

# ============ BUDDHA STATUE (signature seated golden Buddha) ============
def make_buddha(name, loc, size=2):
    base = empty(name, loc)
    # Lotus pedestal
    cyl(f"{name}_pd", r=size*0.75, depth=size*0.25, segs=20, loc=(0, 0, size*0.13), parent=base, mat_=M_BUDDHA_DARK)
    # Lotus petals
    for pi in range(14):
        pa = (pi / 14.0) * math.pi * 2
        beveled_cube(f"{name}_lp{pi}", (size*0.22, size*0.10, size*0.08), bevel_offset=0.05, bevel_segments=4,
                     loc=(math.cos(pa)*size*0.70, math.sin(pa)*size*0.70, size*0.22),
                     parent=base, mat_=M_BUDDHA_GOLD).rotation_euler = (0, 0, pa)
    # Body
    smooth_sphere(f"{name}_bo", r=size*0.42, segs=18, rings=14, loc=(0, 0, size*0.55),
                  parent=base, mat_=M_BUDDHA_GOLD, scale=(1, 1, 0.95))
    # Crossed legs lotus
    cyl(f"{name}_lap", r=size*0.62, depth=size*0.22, segs=20, loc=(0, 0, size*0.32),
        parent=base, mat_=M_BUDDHA_GOLD)
    # Arms folded
    for side in (-1, 1):
        cyl(f"{name}_a{side}", r=size*0.10, depth=size*0.55, segs=14,
            loc=(side*size*0.32, 0, size*0.50), parent=base, mat_=M_BUDDHA_GOLD).rotation_euler = (math.radians(90), 0, math.radians(side*40))
    # Hands in dhyana mudra
    smooth_sphere(f"{name}_hd", r=size*0.10, segs=14, rings=10, loc=(0, 0, size*0.35),
                  parent=base, mat_=M_BUDDHA_GOLD)
    # Head
    head_b_e = empty(f"{name}_he", (0, 0, size*1.10), parent=base)
    smooth_sphere(f"{name}_h", r=size*0.22, segs=22, rings=18, loc=(0, 0, 0),
                  parent=head_b_e, mat_=M_BUDDHA_GOLD)
    # Ushnisha
    smooth_sphere(f"{name}_us", r=size*0.10, segs=16, rings=12, loc=(0, 0, size*0.22),
                  parent=head_b_e, mat_=M_BUDDHA_DARK)
    # Hair curls
    for hi in range(40):
        ha = random.uniform(0, math.pi*2)
        he_h = random.uniform(0.2, 0.85)
        smooth_sphere(f"{name}_hr{hi}", r=size*0.022,
                      loc=(math.cos(ha)*math.sin(he_h)*size*0.22,
                           math.sin(ha)*math.sin(he_h)*size*0.22,
                           math.cos(he_h)*size*0.15),
                      parent=head_b_e, mat_=M_BUDDHA_DARK)
    # Long ears (signature)
    for side in (-1, 1):
        cyl(f"{name}_er{side}", r=size*0.04, depth=size*0.22, segs=10,
            loc=(side*size*0.22, 0, -size*0.05), parent=head_b_e, mat_=M_BUDDHA_GOLD)
    return base

make_buddha("buddha1", (0, 38, 26), size=1.6)

# ============ BHUTAN FLAG (signature yellow/orange with white dragon) ============
flag_e = empty("flag", (-55, -35, 0))
cyl("fl_p", r=0.10, depth=12, segs=12, loc=(0, 0, 6), parent=flag_e, mat_=M_TRUNK)
# Diagonal yellow + orange (signature)
# Yellow top-left triangle
yt_e = empty("fl_yt", (0.5, -0.06, 10.5), parent=flag_e)
for ti in range(10):
    ti_t = ti / 10.0
    tw_y = 4 - ti_t * 4
    beveled_cube(f"fl_yt_t{ti}", (tw_y, 0.05, 0.25), bevel_offset=0.03, bevel_segments=3,
                 loc=(tw_y/2 - 0.5, 0, (ti - 5) * 0.25 + 1.25), parent=yt_e, mat_=M_FLAG_YELLOW)
# Orange bottom-right triangle
ot_e = empty("fl_ot", (0.5, -0.06, 10.5), parent=flag_e)
for ti in range(10):
    ti_t = ti / 10.0
    tw_o = 4 - ti_t * 4
    beveled_cube(f"fl_ot_t{ti}", (tw_o, 0.05, 0.25), bevel_offset=0.03, bevel_segments=3,
                 loc=(4 - tw_o/2 - 0.5, 0, -(ti - 5) * 0.25 - 0.25), parent=ot_e, mat_=M_FLAG_ORANGE)
# White dragon (simplified silhouette in center signature)
dragon_e = empty("fl_dr", (2, -0.07, 10.5), parent=flag_e)
# Dragon body
smooth_sphere("fl_dr_bo", r=0.35, segs=14, rings=10, loc=(0, 0, 0),
              parent=dragon_e, mat_=M_DRAGON_WHITE, scale=(1.7, 0.10, 0.85))
# Head
smooth_sphere("fl_dr_h", r=0.18, segs=12, rings=10, loc=(0.50, 0, 0.10),
              parent=dragon_e, mat_=M_DRAGON_WHITE, scale=(1.3, 0.10, 0.85))
# Tail curl
for ti in range(5):
    ta = (ti / 5.0) * math.pi * 0.6
    smooth_sphere(f"fl_dr_t{ti}", r=0.06 - ti*0.005, segs=8, rings=6,
                  loc=(-0.40 - ti*0.10, 0, math.sin(ta)*0.10),
                  parent=dragon_e, mat_=M_DRAGON_WHITE, scale=(1, 0.10, 1))
flag_e["_phase"] = 0

# ============================================================
# 600 PRAYER FLAGS 5-COLOR + 400 BLACK-NECKED CRANES (signature)
# ============================================================
prayer_flags = []
# Multiple strings of prayer flags across landscape
n_strings = 30
for str_i in range(n_strings):
    str_angle = (str_i / n_strings) * math.pi * 2
    str_x_s = math.cos(str_angle) * 25
    str_y_s = math.sin(str_angle) * 25
    str_x_e = math.cos(str_angle + 0.5) * 35
    str_y_e = math.sin(str_angle + 0.5) * 35
    for fi in range(20):
        t = fi / 20.0
        fx = str_x_s + (str_x_e - str_x_s) * t
        fy = str_y_s + (str_y_e - str_y_s) * t
        fz = random.uniform(8, 18)
        flag_col = PF_COLORS[fi % 5]
        pf = empty(f"pf{str_i}_{fi}", (fx, fy, fz))
        beveled_cube(f"pf{str_i}_{fi}_b", (0.35, 0.05, 0.50), bevel_offset=0.03, bevel_segments=3,
                     loc=(0, 0, 0), parent=pf, mat_=flag_col)
        pf["_phase"] = random.uniform(0, math.pi*2)
        pf["_speed"] = random.uniform(1.0, 2.5)
        prayer_flags.append(pf)

# 400 black-necked cranes flying
cranes = []
for i in range(400):
    px = random.uniform(-130, 130)
    py = random.uniform(-130, 130)
    pz = random.uniform(15, 50)
    c_e = empty(f"cn{i}", (px, py, pz))
    # White body
    smooth_sphere(f"cn{i}_bo", r=0.22, segs=14, rings=10, loc=(0, 0, 0),
                  parent=c_e, mat_=M_CRANE_BODY, scale=(1.6, 0.85, 0.95))
    # BLACK NECK (signature)
    neck_e = empty(f"cn{i}_ne", (0.18, 0, 0.10), parent=c_e)
    for ni in range(4):
        ni_t = ni / 4.0
        cyl(f"cn{i}_n{ni}", r=0.025, depth=0.10, segs=8,
            loc=(0, 0, ni_t * 0.30), parent=neck_e, mat_=M_CRANE_BLACK)
    # Head black with red crown (signature)
    smooth_sphere(f"cn{i}_h", r=0.08, segs=12, rings=10, loc=(0.05, 0, 0.40),
                  parent=neck_e, mat_=M_CRANE_BLACK)
    # Red crown patch
    smooth_sphere(f"cn{i}_cr", r=0.05, segs=10, rings=8, loc=(0.05, 0, 0.45),
                  parent=neck_e, mat_=M_CRANE_RED)
    # Long beak
    cyl(f"cn{i}_bk", r=0.015, depth=0.15, segs=8, loc=(0.14, 0, 0.38),
        parent=neck_e, mat_=M_BEAK).rotation_euler = (0, math.radians(95), 0)
    # WIDE WINGS (signature crane wings extended)
    wing_e_l = empty(f"cn{i}_wl", (0, -0.15, 0), parent=c_e)
    wing_e_r = empty(f"cn{i}_wr", (0, 0.15, 0), parent=c_e)
    beveled_cube(f"cn{i}_wl_b", (0.30, 0.50, 0.04), bevel_offset=0.03, bevel_segments=3,
                 loc=(0, -0.25, 0), parent=wing_e_l, mat_=M_CRANE_BODY)
    beveled_cube(f"cn{i}_wr_b", (0.30, 0.50, 0.04), bevel_offset=0.03, bevel_segments=3,
                 loc=(0, 0.25, 0), parent=wing_e_r, mat_=M_CRANE_BODY)
    # Wing primary feathers (signature black tips)
    for fi_w in range(4):
        fa = (fi_w / 4.0 - 0.5) * math.radians(40)
        beveled_cube(f"cn{i}_wlf{fi_w}", (0.08, 0.18, 0.02), bevel_offset=0.01, bevel_segments=2,
                     loc=(math.sin(fa)*0.10, -0.55, 0), parent=wing_e_l, mat_=M_CRANE_BLACK).rotation_euler = (0, 0, fa)
        beveled_cube(f"cn{i}_wrf{fi_w}", (0.08, 0.18, 0.02), bevel_offset=0.01, bevel_segments=2,
                     loc=(math.sin(fa)*0.10, 0.55, 0), parent=wing_e_r, mat_=M_CRANE_BLACK).rotation_euler = (0, 0, fa)
    # Long legs trailing
    for side in (-1, 1):
        cyl(f"cn{i}_l{side}", r=0.012, depth=0.45, segs=8,
            loc=(-0.10, side*0.05, -0.25), parent=c_e, mat_=M_CRANE_BLACK)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    c_e["_base_x"] = px; c_e["_base_y"] = py; c_e["_base_z"] = pz
    c_e["_speed"] = random.uniform(0.4, 1.0)
    c_e["_radius"] = random.uniform(8, 20)
    c_e["_wl"] = wing_e_l; c_e["_wr"] = wing_e_r
    cranes.append(c_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Monks meditate sway
for m in monks:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 0.6 + phase) * math.radians(2), 0,
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 0.6 + phase) * math.radians(3), 0, 0)
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Prayer wheels spin
for pw in prayer_wheels:
    phase = pw["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        pw.rotation_euler = (0, 0, t * 2.0 + phase)
        pw.keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 prayer flags flutter (multi-axis)
for pf in prayer_flags:
    phase = pf["_phase"]; speed = pf["_speed"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        pf.rotation_euler = (math.sin(t * speed + phase) * math.radians(30),
                              math.cos(t * speed * 0.8 + phase) * math.radians(20),
                              math.sin(t * speed * 1.2 + phase) * math.radians(15))
        pf.keyframe_insert("rotation_euler", frame=f)

# 400 cranes soar with wing flap
for c in cranes:
    phase = c["_phase"]; speed = c["_speed"]; radius = c["_radius"]
    bx, by, bz_c = c["_base_x"], c["_base_y"], c["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * radius
        y = by + math.sin(t * speed + phase) * radius
        z = bz_c + math.sin(t * speed * 1.2 + phase) * 2.5
        c.location = (x, y, z)
        c.rotation_euler = (0, 0, math.atan2(math.cos(t * speed + phase),
                                              -math.sin(t * speed + phase)))
        c.keyframe_insert("location", frame=f)
        c.keyframe_insert("rotation_euler", frame=f)
        # Wing flap (slow graceful)
        wing_a = math.sin(t * 3.0 + phase) * math.radians(25)
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
out_glb = os.path.join(out_dir, "pbr_bhutan_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_bhutan_tigers_nest_cliff_monastery] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Bhutan stylized low-poly: cliff face + Paro Taktsang monastery white/red with gold trim + 4 prayer wheels spinning + 4 drukpa monks anjali mudra + golden Buddha + Mt Jomolhari + prayer flag string arc + Bhutan dragon flag + 600 5-color prayer flags + 400 black-necked cranes")
print("Honest scope: procedural primitives, stylized aesthetic — not photoreal.")
