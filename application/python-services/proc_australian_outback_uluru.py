"""
proc_australian_outback_uluru.py — 228e procédural AuroraIA (92e qualité)
Australian outback: ONE red ground + Uluru monolith + Kata Tjuta + 6 eucalyptus + 5 aborigenes + didgeridoo chief + woman+baby + 8 kangaroos + 5 koalas + 4 emus + 6 dingoes + 3 cockatoos + 2 wombats + python + campfire + Milky Way + 600 sand + 400 fireflies
FIXES : 1 ground + 600 sand grains + 400 fireflies signature outback night
"""
import bpy, bmesh, math, random, os

random.seed(0x07BAC228)

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
    if bsdf is None:
        m.node_tree.nodes.clear()
        bsdf = m.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        out = m.node_tree.nodes.new("ShaderNodeOutputMaterial")
        m.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
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

# Outback night palette
M_SKY = mat("sky", (0.08, 0.06, 0.20, 1.0), 0.0, 0.7, emission=(0.08,0.06,0.20), emission_strength=1.0)
M_MOON = mat("moon", (0.95, 0.92, 0.85, 1.0), 0.0, 0.20, emission=(0.95,0.92,0.85), emission_strength=12.0)
M_STAR = mat("star", (1.0, 1.0, 0.95, 1.0), 0.0, 0.20, emission=(1.0,1.0,0.95), emission_strength=14.0)
M_MILKY = mat("milky", (0.65, 0.70, 0.95, 1.0), 0.0, 0.30, emission=(0.65,0.70,0.95), emission_strength=4.0, alpha=0.55)
M_NEBULA_PURPLE = mat("nebula_p", (0.55, 0.30, 0.85, 1.0), 0.0, 0.30, emission=(0.55,0.30,0.85), emission_strength=2.5, alpha=0.55)
M_NEBULA_PINK = mat("nebula_pi", (0.95, 0.55, 0.85, 1.0), 0.0, 0.30, emission=(0.95,0.55,0.85), emission_strength=2.8, alpha=0.55)

# Red earth + sand
M_GROUND_RED = mat("ground_r", (0.78, 0.32, 0.18, 1.0), 0.0, 0.85, emission=(0.72,0.30,0.16), emission_strength=0.5)
M_SAND_RED = mat("sand_r", (0.85, 0.42, 0.22, 1.0), 0.0, 0.85, emission=(0.78,0.38,0.20), emission_strength=0.6)
M_SAND_DARK = mat("sand_d_b", (0.55, 0.22, 0.12, 1.0), 0.0, 0.85, emission=(0.50,0.20,0.10), emission_strength=0.4)
M_ROCK_RED = mat("rock_r", (0.65, 0.30, 0.18, 1.0), 0.0, 0.85)
M_SPINIFEX = mat("spinifex", (0.78, 0.65, 0.28, 1.0), 0.0, 0.80, emission=(0.72,0.60,0.25), emission_strength=0.5)

# Uluru (signature giant red monolith)
M_ULURU = mat("uluru", (0.85, 0.32, 0.15, 1.0), 0.0, 0.80, emission=(0.80,0.30,0.13), emission_strength=0.8)
M_ULURU_SHADOW = mat("uluru_s", (0.55, 0.22, 0.10, 1.0), 0.0, 0.85, emission=(0.50,0.20,0.10), emission_strength=0.4)

# Eucalyptus
M_EUCA_TRUNK = mat("euca_t", (0.85, 0.78, 0.65, 1.0), 0.0, 0.85, emission=(0.78,0.72,0.60), emission_strength=0.4)
M_EUCA_TRUNK_BROWN = mat("euca_tb", (0.55, 0.42, 0.28, 1.0), 0.0, 0.85)
M_EUCA_LEAF = mat("euca_l", (0.45, 0.55, 0.40, 1.0), 0.0, 0.65, emission=(0.40,0.50,0.35), emission_strength=0.4)
M_EUCA_LEAF_GRAY = mat("euca_lg", (0.62, 0.68, 0.55, 1.0), 0.0, 0.65, emission=(0.55,0.62,0.50), emission_strength=0.5)
M_BARK_PEEL = mat("bark_p", (0.62, 0.32, 0.18, 1.0), 0.0, 0.85)

# Aborigenes
M_SKIN_ABO = mat("skin_a", (0.45, 0.25, 0.15, 1.0), 0.0, 0.55, emission=(0.40,0.22,0.13), emission_strength=0.4)
M_LOIN_RED = mat("loin_r", (0.65, 0.35, 0.20, 1.0), 0.0, 0.70)
M_BEARD_DARK_A = mat("beard_da", (0.18, 0.10, 0.06, 1.0), 0.0, 0.85)
# Dot painting white/yellow/red signature
M_PAINT_WHITE = mat("paint_w", (1.0, 0.92, 0.85, 1.0), 0.0, 0.30, emission=(0.98,0.90,0.85), emission_strength=2.5)
M_PAINT_YELLOW = mat("paint_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.30, emission=(1.0,0.85,0.20), emission_strength=2.8)
M_PAINT_RED = mat("paint_r", (0.95, 0.20, 0.18, 1.0), 0.0, 0.30, emission=(0.90,0.20,0.18), emission_strength=2.5)
M_PAINT_BLACK = mat("paint_b", (0.10, 0.08, 0.06, 1.0), 0.0, 0.70)
M_DIDGE = mat("didge", (0.50, 0.35, 0.20, 1.0), 0.0, 0.80, emission=(0.45,0.32,0.18), emission_strength=0.4)
M_DIDGE_PATTERN = mat("didge_p", (1.0, 0.85, 0.25, 1.0), 0.0, 0.30, emission=(0.95,0.80,0.25), emission_strength=1.5)

# Kangaroos
M_KANGAROO = mat("kan", (0.65, 0.42, 0.25, 1.0), 0.0, 0.75, emission=(0.60,0.40,0.22), emission_strength=0.4)
M_KANGAROO_BELLY = mat("kan_b", (0.85, 0.72, 0.55, 1.0), 0.0, 0.70, emission=(0.78,0.68,0.52), emission_strength=0.4)
M_KAN_EYE = mat("kan_e", (0.10, 0.06, 0.04, 1.0), 0.0, 0.40, emission=(0.30,0.18,0.10), emission_strength=1.0)

# Koalas
M_KOALA = mat("koala", (0.62, 0.62, 0.62, 1.0), 0.0, 0.85, emission=(0.55,0.55,0.55), emission_strength=0.4)
M_KOALA_BELLY = mat("koala_b", (0.92, 0.88, 0.82, 1.0), 0.0, 0.85, emission=(0.85,0.82,0.78), emission_strength=0.4)
M_KOALA_EAR = mat("koala_e", (0.95, 0.92, 0.85, 1.0), 0.0, 0.80)
M_KOALA_NOSE = mat("koala_n", (0.15, 0.08, 0.05, 1.0), 0.0, 0.55)

# Emus
M_EMU_BROWN = mat("emu", (0.45, 0.32, 0.20, 1.0), 0.0, 0.80, emission=(0.40,0.30,0.18), emission_strength=0.4)
M_EMU_NECK = mat("emu_n", (0.55, 0.42, 0.30, 1.0), 0.0, 0.80)
M_EMU_BEAK = mat("emu_be", (0.30, 0.18, 0.10, 1.0), 0.0, 0.55)

# Dingoes
M_DINGO = mat("dingo", (0.85, 0.55, 0.25, 1.0), 0.0, 0.75, emission=(0.78,0.50,0.22), emission_strength=0.4)
M_DINGO_BELLY = mat("dingo_b", (0.95, 0.78, 0.55, 1.0), 0.0, 0.70)

# Cockatoos
M_COCK_WHITE = mat("cock_w", (0.98, 0.95, 0.92, 1.0), 0.0, 0.55, emission=(0.92,0.90,0.88), emission_strength=0.7)
M_COCK_CREST = mat("cock_c", (1.0, 0.85, 0.20, 1.0), 0.0, 0.40, emission=(1.0,0.85,0.20), emission_strength=2.0)
M_COCK_BEAK = mat("cock_be", (0.25, 0.18, 0.12, 1.0), 0.0, 0.55)

# Wombats
M_WOMBAT = mat("wombat", (0.55, 0.42, 0.30, 1.0), 0.0, 0.85, emission=(0.50,0.40,0.28), emission_strength=0.4)

# Python
M_PYTHON_PATTERN = mat("py_p", (0.85, 0.78, 0.32, 1.0), 0.3, 0.45, emission=(0.78,0.72,0.30), emission_strength=0.6)
M_PYTHON_DARK = mat("py_d", (0.30, 0.22, 0.12, 1.0), 0.0, 0.75)

# Campfire
M_FIRE_OUTER = mat("fire_o", (1.0, 0.55, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.15), emission_strength=14.0)
M_FIRE_CORE = mat("fire_c", (1.0, 0.92, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.92,0.30), emission_strength=20.0)
M_EMBER = mat("ember", (1.0, 0.30, 0.15, 1.0), 0.0, 0.20, emission=(1.0,0.30,0.15), emission_strength=15.0)
M_LOG = mat("log", (0.30, 0.18, 0.10, 1.0), 0.0, 0.85)
M_LOG_DARK = mat("log_d", (0.18, 0.10, 0.06, 1.0), 0.0, 0.85)

# Dot painting circles
M_DOT_W = mat("dot_w", (1.0, 0.92, 0.85, 1.0), 0.0, 0.40, emission=(0.98,0.90,0.85), emission_strength=2.0)
M_DOT_Y = mat("dot_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.40, emission=(1.0,0.85,0.20), emission_strength=2.5)
M_DOT_R = mat("dot_r", (0.95, 0.20, 0.20, 1.0), 0.0, 0.40, emission=(0.90,0.20,0.20), emission_strength=2.2)

# Particles
M_SAND_PARTICLE = mat("sandp", (0.85, 0.42, 0.20, 1.0), 0.0, 0.55, emission=(0.78,0.38,0.18), emission_strength=2.5, alpha=0.65)
M_FIREFLY_OUT = mat("ff_out", (1.0, 0.92, 0.40, 1.0), 0.0, 0.10, emission=(1.0,0.92,0.40), emission_strength=22.0)
M_FIREFLY_ORANGE = mat("ff_or", (1.0, 0.62, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.62,0.20), emission_strength=20.0)

# ============ SKY + MOON + MILKY WAY + NEBULA ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
moon_e = empty("moon_e", (30, -40, 35))
smooth_sphere("moon", r=4.0, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)
for i in range(3):
    smooth_sphere(f"moon_halo{i}", r=4.0 + (i+1)*1.3, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)

# Milky Way band (signature southern hemisphere)
milky_e = empty("milky", (0, 0, 40))
milky_e.rotation_euler = (0, 0, math.radians(30))
for i in range(15):
    seg_x = (i - 7) * 8
    for sty in range(3):
        beveled_cube(f"milky_{i}_{sty}", (8, 2, 0.5),
                     loc=(seg_x, (sty - 1)*3, math.sin(i*0.3)*2),
                     parent=milky_e, mat_=M_MILKY)
# 6 nebulas
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    rad = random.uniform(55, 75)
    cx = rad * math.cos(a)
    cy = rad * math.sin(a)
    cz = random.uniform(28, 42)
    n_e = empty(f"nebula_e{i}", (cx, cy, cz))
    col = M_NEBULA_PURPLE if i % 2 == 0 else M_NEBULA_PINK
    for j in range(4):
        smooth_sphere(f"neb{i}_{j}", r=random.uniform(3.5, 5.5),
                      loc=(random.uniform(-4,4), random.uniform(-3,3), random.uniform(-1,1)),
                      parent=n_e, mat_=col)
    n_e["_phase"] = random.uniform(0, math.pi*2)

# 300 stars dense
for i in range(300):
    a = random.uniform(0, math.pi*2)
    phi = random.uniform(math.pi/6, math.pi/2.2)
    r_star = 115
    sx = r_star * math.cos(phi) * math.cos(a)
    sy = r_star * math.cos(phi) * math.sin(a)
    sz = r_star * math.sin(phi) * 0.4
    smooth_sphere(f"star{i}", r=random.uniform(0.20, 0.55), segs=10, rings=8,
                  loc=(sx, sy, sz), mat_=M_STAR)

# ============ ULURU (signature giant red monolith) ============
uluru_e = empty("uluru", loc=(0, 35, 0))
# Massive flat-top mountain (signature Uluru)
beveled_cube("uluru_main", (40, 18, 12), bevel_offset=0.40, loc=(0, 0, 6.0),
             parent=uluru_e, mat_=M_ULURU)
# Top dome curve
smooth_sphere("uluru_top", r=20, segs=24, rings=18, loc=(0, 0, 12),
              parent=uluru_e, mat_=M_ULURU, scale=(1, 0.45, 0.30))
# Erosion channels (signature vertical lines)
for i in range(20):
    chan_x = (i - 9.5) * 2.0
    beveled_cube(f"uluru_chan{i}", (0.4, 18, 12), bevel_offset=0.10,
                 loc=(chan_x, 0.05, 6.0), parent=uluru_e, mat_=M_ULURU_SHADOW)
# Caves at base
for ci in range(3):
    cx = (ci - 1) * 8
    beveled_cube(f"uluru_cave{ci}", (3, 0.5, 4), bevel_offset=0.20,
                 loc=(cx, -8.5, 2), parent=uluru_e, mat_=M_ULURU_SHADOW)

# ============ KATA TJUTA (background domes) ============
kt_e = empty("kt", loc=(-40, 38, 0))
for i in range(7):
    a = (i / 7.0) * math.pi - math.pi/2
    dx = math.cos(a) * 18
    dz = math.sin(a) * 6 - 4
    smooth_sphere(f"kt{i}", r=random.uniform(8, 12), segs=24, rings=18,
                  loc=(dx, random.uniform(-3, 3), dz + 4),
                  parent=kt_e, mat_=M_ULURU, scale=(1, 0.9, 0.7))

# ============ ONE clean red ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND_RED)
# Sand dunes organic 3D variations
for i in range(50):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 42)
    smooth_sphere(f"dune{i}", r=random.uniform(0.8, 1.8),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_SAND_RED if i % 2 == 0 else M_SAND_DARK,
                  scale=(1.8, 1.5, 0.25))
# Rocks
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(12, 40)
    smooth_sphere(f"rock{i}", r=random.uniform(0.5, 1.2),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.35),
                  mat_=M_ROCK_RED,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.85)))
# Spinifex grass tufts (signature outback)
for i in range(40):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 38)
    sf_e = empty(f"sf{i}", (rad*math.cos(a), rad*math.sin(a), 0))
    # Multiple needle-like grass
    for ni in range(8):
        na = (ni / 8.0) * math.pi * 2
        nh = random.uniform(0.30, 0.50)
        cyl(f"sf{i}_n{ni}", r=0.015, depth=nh, segs=6,
            loc=(0.10*math.cos(na), 0.10*math.sin(na), nh/2 + 0.1),
            parent=sf_e, mat_=M_SPINIFEX)

# ============ DOT PAINTING CIRCLES on ground (signature aboriginal art) ============
for ci_idx in range(8):
    a = (ci_idx / 8.0) * math.pi * 2
    cx_c = 5 * math.cos(a)
    cy_c = 5 * math.sin(a)
    # Concentric rings of dots
    for ring in range(3):
        ring_r = 0.8 + ring * 0.4
        for dot in range(int(8 + ring * 4)):
            da = (dot / int(8 + ring * 4)) * math.pi * 2
            dx = cx_c + ring_r * math.cos(da)
            dy = cy_c + ring_r * math.sin(da)
            col = [M_DOT_W, M_DOT_Y, M_DOT_R][ring % 3]
            smooth_sphere(f"dot{ci_idx}_{ring}_{dot}", r=0.06,
                          loc=(dx, dy, 0.06), mat_=col, scale=(1, 1, 0.4))

# ============ 6 EUCALYPTUS TREES (signature ghostly white trunks) ============
def make_eucalyptus(name, loc, scale=1.0):
    base = empty(name, loc)
    # Tall white twisted trunk (signature ghost gum)
    for s in range(7):
        seg_x = math.sin(s * 0.3) * 0.10 * scale
        seg = smooth_cone(f"{name}_t{s}", r1=(0.30 - s*0.022)*scale, r2=(0.27 - s*0.022)*scale,
                          depth=0.9*scale, segs=12,
                          loc=(seg_x, math.cos(s * 0.3) * 0.10 * scale, (s+0.5)*0.9*scale),
                          parent=base, mat_=M_EUCA_TRUNK if s % 2 == 0 else M_EUCA_TRUNK_BROWN)
        seg.rotation_euler = (math.radians(random.uniform(-5,5)),
                              math.radians(random.uniform(-5,5)), 0)
    # Bark peels (signature shedding)
    for bp in range(6):
        bp_z = random.uniform(1, 5) * scale
        smooth_sphere(f"{name}_bp{bp}", r=random.uniform(0.10, 0.18) * scale,
                      loc=(0.30*math.cos(bp), 0.30*math.sin(bp), bp_z),
                      parent=base, mat_=M_BARK_PEEL, scale=(0.3, 1.5, 1))
    # 5 branches
    for j in range(5):
        a = (j / 5.0) * math.pi * 2
        b_e = empty(f"{name}_be{j}", (0, 0, 5.5*scale), parent=base)
        b_e.rotation_euler = (math.radians(50), 0, a)
        for k in range(3):
            cyl(f"{name}_b{j}_{k}", r=(0.13 - k*0.025)*scale, depth=0.8*scale, segs=10,
                loc=(0, (k+0.5)*0.8*scale, 0), parent=b_e,
                mat_=M_EUCA_TRUNK).rotation_euler = (math.radians(90), 0, 0)
        # Drooping leaf clusters (signature eucalyptus)
        for fl in range(6):
            la = (fl / 6.0) * math.pi * 2
            for sk in range(3):
                smooth_sphere(f"{name}_fl{j}_{fl}_{sk}", r=random.uniform(0.10, 0.18) * scale,
                              loc=(math.cos(la)*0.30*scale, 1.8*scale + sk*0.20,
                                   math.sin(la)*0.20 - sk*0.30),
                              parent=b_e,
                              mat_=M_EUCA_LEAF if sk % 2 == 0 else M_EUCA_LEAF_GRAY,
                              scale=(0.5, 1.4, 0.4))
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

eucalypti = []
euca_pos = [(-25, -10, 0, 1.0), (-20, -22, 0, 1.05),
            (22, -10, 0, 1.0), (25, -20, 0, 0.95),
            (-15, 5, 0, 1.05), (15, 5, 0, 1.0)]
for i, (tx, ty, tz, sc) in enumerate(euca_pos):
    e = make_eucalyptus(f"euca{i}", (tx, ty, tz), scale=sc)
    eucalypti.append(e)

# ============ CAMPFIRE (signature outback night) ============
fire_e = empty("fire", loc=(0, 0, 0))
# Stone ring
for ri in range(8):
    ra = (ri / 8.0) * math.pi * 2
    smooth_sphere(f"f_stone{ri}", r=0.30,
                  loc=(1.0*math.cos(ra), 1.0*math.sin(ra), 0.20),
                  parent=fire_e, mat_=M_ROCK_RED)
# Logs (crossed)
for li in range(4):
    la = (li / 4.0) * math.pi
    log = cyl(f"f_log{li}", r=0.10, depth=1.5, segs=12,
              loc=(math.cos(la)*0.2, math.sin(la)*0.2, 0.30),
              parent=fire_e, mat_=M_LOG)
    log.rotation_euler = (0, math.radians(90), la)
# Embers
for ei in range(8):
    ea = (ei / 8.0) * math.pi * 2
    smooth_sphere(f"f_ember{ei}", r=0.10,
                  loc=(0.3*math.cos(ea), 0.3*math.sin(ea), 0.35),
                  parent=fire_e, mat_=M_EMBER)
# Flames composite
flame_e = empty("flame", (0, 0, 0.5), parent=fire_e)
smooth_cone("flame_o", r1=0.55, r2=0.05, depth=1.8, segs=14,
            loc=(0, 0, 0.9), parent=flame_e, mat_=M_FIRE_OUTER)
smooth_cone("flame_c", r1=0.30, r2=0.02, depth=1.3, segs=14,
            loc=(0, 0, 0.65), parent=flame_e, mat_=M_FIRE_CORE)

# ============ ABORIGINAL PEOPLE (5 + chief + woman with baby) ============
def make_aboriginal(name, loc, has_didge=False, with_baby=False, is_chief=False, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs (sitting cross-legged on ground)
    smooth_cone(f"{name}_legs_base", r1=0.40*scale, r2=0.30*scale, depth=0.40*scale, segs=14,
                loc=(0, 0, 0.20*scale), parent=base, mat_=M_SKIN_ABO)
    # Hips
    smooth_sphere(f"{name}_hips", r=0.28*scale, loc=(0, 0, 0.45*scale),
                  parent=base, mat_=M_SKIN_ABO, scale=(1.5, 1.4, 0.5))
    # Loincloth
    beveled_cube(f"{name}_loin", (0.30*scale, 0.20*scale, 0.25*scale), bevel_offset=0.03,
                 loc=(0, 0, 0.55*scale), parent=base, mat_=M_LOIN_RED)
    # Torso muscular bare
    beveled_cube(f"{name}_torso", (0.36*scale, 0.20*scale, 0.60*scale), bevel_offset=0.05,
                 loc=(0, 0, 0.95*scale), parent=base, mat_=M_SKIN_ABO)
    # DOT PAINTING on torso (signature)
    for dp in range(20):
        dpx = random.uniform(-0.15, 0.15)
        dpy = -0.11
        dpz = 0.7 + random.uniform(0, 0.5)
        col = [M_PAINT_WHITE, M_PAINT_YELLOW, M_PAINT_RED][dp % 3]
        smooth_sphere(f"{name}_dp{dp}", r=0.022,
                      loc=(dpx*scale, dpy*scale, dpz*scale),
                      parent=base, mat_=col)
    # Body paint stripes (signature)
    for sp in range(3):
        beveled_cube(f"{name}_stripe{sp}", (0.30*scale, 0.04*scale, 0.05*scale),
                     loc=(0, -0.12*scale, 0.95*scale + sp*0.18*scale),
                     parent=base, mat_=M_PAINT_WHITE)
    # Neck
    cyl(f"{name}_neck", r=0.08*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 1.32*scale), parent=base, mat_=M_SKIN_ABO)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.50*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_ABO)
    # Curly hair (signature)
    smooth_sphere(f"{name}_hair", r=0.22*scale, loc=(0, 0.03*scale, 0.08*scale),
                  parent=head_e, mat_=M_BEARD_DARK_A, scale=(1.05, 1.05, 0.95))
    # Hair curls
    for hi in range(8):
        ha = (hi / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_curl{hi}", r=0.06*scale,
                      loc=(0.20*scale*math.cos(ha), 0.10*scale + 0.15*scale*math.sin(ha), 0.18*scale),
                      parent=head_e, mat_=M_BEARD_DARK_A)
    # Beard (signature aboriginal man)
    smooth_sphere(f"{name}_beard", r=0.15*scale, loc=(0, -0.15*scale, -0.15*scale),
                  parent=head_e, mat_=M_BEARD_DARK_A, scale=(1.1, 0.8, 1.2))
    # FACE PAINTING (signature lines)
    for fp in range(3):
        beveled_cube(f"{name}_face_l{fp}", (0.15*scale, 0.04*scale, 0.02*scale),
                     loc=(0, -0.16*scale, 0.05*scale - fp*0.04*scale),
                     parent=head_e, mat_=M_PAINT_WHITE if fp % 2 == 0 else M_PAINT_YELLOW)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_w{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.13*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.95, 0.92, 0.85, 1), 0, 0.4,
                                emission=(0.85,0.82,0.78), emission_strength=0.3))
        smooth_sphere(f"{name}_eye_p{side}", r=0.012*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ep{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Chief headband (signature)
    if is_chief:
        cyl(f"{name}_headband", r=0.21*scale, depth=0.05*scale, segs=16,
            loc=(0, 0, 0.16*scale), parent=head_e, mat_=M_PAINT_YELLOW)
        # Feathers in headband
        for fei in range(3):
            fea = beveled_cube(f"{name}_feather{fei}", (0.04*scale, 0.04*scale, 0.30*scale), bevel_offset=0.01,
                              loc=(0, 0.18*scale, 0.30*scale), parent=head_e,
                              mat_=[M_PAINT_WHITE, M_PAINT_RED, M_PAINT_YELLOW][fei])
            fea.rotation_euler = ((fei-1)*0.3, 0, 0)
    # Arms (playing didge or sitting)
    arms_e = []
    if has_didge:
        # Holding didgeridoo to mouth
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25*scale, 0, 1.25*scale), parent=base)
            if side_idx == 0:
                sh.rotation_euler = (math.radians(-100), 0, math.radians(-30))
            else:
                sh.rotation_euler = (math.radians(-70), 0, math.radians(30))
            cyl(f"{name}_uarm{side_idx}", r=0.07*scale, depth=0.32*scale, segs=10,
                loc=(0, 0, -0.16*scale), parent=sh, mat_=M_SKIN_ABO)
            cyl(f"{name}_fa{side_idx}", r=0.06*scale, depth=0.30*scale, segs=10,
                loc=(0, 0, -0.45*scale), parent=sh, mat_=M_SKIN_ABO)
            smooth_sphere(f"{name}_hand{side_idx}", r=0.07*scale, loc=(0, 0, -0.62*scale),
                          parent=sh, mat_=M_SKIN_ABO)
            arms_e.append(sh)
        # DIDGERIDOO (signature long wooden tube)
        didge_e = empty(f"{name}_didge_e", (0.20*scale, -0.40*scale, 0.50*scale), parent=base)
        didge_e.rotation_euler = (math.radians(80), 0, math.radians(-15))
        cyl(f"{name}_didge_main", r=0.06*scale, depth=2.0*scale, segs=12,
            loc=(0, 0, 0), parent=didge_e, mat_=M_DIDGE)
        # Bell end (wider)
        smooth_cone(f"{name}_didge_bell", r1=0.10*scale, r2=0.07*scale, depth=0.30*scale, segs=12,
                    loc=(0, 0, 1.0*scale), parent=didge_e, mat_=M_DIDGE)
        # Dot pattern bands on didge
        for db in range(5):
            cyl(f"{name}_didge_b{db}", r=0.065*scale, depth=0.04*scale, segs=14,
                loc=(0, 0, -0.5 + db*0.30*scale), parent=didge_e, mat_=M_DIDGE_PATTERN)
    else:
        # Hands resting
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25*scale, 0, 1.25*scale), parent=base)
            sh.rotation_euler = (math.radians(-30), 0, math.radians(side*-20))
            cyl(f"{name}_uarm{side_idx}", r=0.07*scale, depth=0.32*scale, segs=10,
                loc=(0, 0, -0.16*scale), parent=sh, mat_=M_SKIN_ABO)
            cyl(f"{name}_fa{side_idx}", r=0.06*scale, depth=0.30*scale, segs=10,
                loc=(0, 0, -0.45*scale), parent=sh, mat_=M_SKIN_ABO)
            smooth_sphere(f"{name}_hand{side_idx}", r=0.07*scale, loc=(0, 0, -0.62*scale),
                          parent=sh, mat_=M_SKIN_ABO)
            arms_e.append(sh)
    # Baby in arms
    if with_baby:
        baby_e = empty(f"{name}_baby_e", (0, -0.35, 1.0), parent=base)
        # Baby body
        smooth_sphere(f"{name}_baby_body", r=0.14*scale, segs=14, rings=10,
                      loc=(0, 0, 0), parent=baby_e, mat_=M_SKIN_ABO)
        # Baby head
        smooth_sphere(f"{name}_baby_head", r=0.10*scale, loc=(0, 0, 0.18),
                      parent=baby_e, mat_=M_SKIN_ABO)
        # Curly hair tiny
        smooth_sphere(f"{name}_baby_hair", r=0.11*scale, loc=(0, 0.02, 0.20),
                      parent=baby_e, mat_=M_BEARD_DARK_A, scale=(1, 1, 0.8))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

aboriginals = []
# Chief with didgeridoo
chief_a = make_aboriginal("chief_a", (-1.5, 0, 0), has_didge=True, is_chief=True,
                          facing=math.radians(60), scale=1.1)
aboriginals.append(chief_a)
# 4 sitting around fire
abo_specs = [
    ("abo1", (2, 0, 0), False, False, math.radians(-120)),
    ("abo2", (-2, -2, 0), False, False, math.radians(30)),
    ("abo3", (2, -2, 0), False, False, math.radians(150)),
    ("abo4", (0, 2.5, 0), False, False, math.radians(180)),
]
for spec in abo_specs:
    name, loc, did, baby, fac = spec
    a = make_aboriginal(name, loc, has_didge=did, with_baby=baby, facing=fac, scale=1.0)
    aboriginals.append(a)
# Woman with baby (sit further from fire)
woman_abo = make_aboriginal("woman_abo", (-4, 1, 0), has_didge=False, with_baby=True,
                              facing=math.radians(45), scale=1.0)
aboriginals.append(woman_abo)

# ============ 8 KANGAROOS ============
def make_kangaroo(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body (lean back)
    body = smooth_sphere(f"{name}_body", r=0.45, segs=20, rings=14, loc=(0, 0, 1.20),
                         parent=base, mat_=M_KANGAROO, scale=(1.0, 1, 1.4))
    # Belly white
    smooth_sphere(f"{name}_belly", r=0.30, loc=(0, -0.15, 1.05),
                  parent=base, mat_=M_KANGAROO_BELLY, scale=(1.0, 0.7, 1.2))
    # Powerful hind legs (signature)
    for side in (-1, 1):
        # Upper thigh
        thigh = beveled_cube(f"{name}_thigh{side}", (0.18, 0.30, 0.65), bevel_offset=0.04,
                            loc=(side*0.18, 0, 0.85), parent=base, mat_=M_KANGAROO)
        # Lower leg (very long signature)
        leg = beveled_cube(f"{name}_leg{side}", (0.12, 0.15, 0.85), bevel_offset=0.04,
                          loc=(side*0.18, 0.1, 0.40), parent=base, mat_=M_KANGAROO)
        # Massive foot (signature)
        foot = beveled_cube(f"{name}_foot{side}", (0.14, 0.45, 0.10), bevel_offset=0.03,
                           loc=(side*0.18, 0.18, 0.05), parent=base, mat_=M_KANGAROO)
    # Small front arms (signature short)
    for side in (-1, 1):
        beveled_cube(f"{name}_arm{side}", (0.06, 0.06, 0.30), bevel_offset=0.02,
                     loc=(side*0.22, -0.30, 1.35), parent=base, mat_=M_KANGAROO)
        # Hand
        smooth_sphere(f"{name}_hand{side}", r=0.05, loc=(side*0.22, -0.36, 1.18),
                      parent=base, mat_=M_KANGAROO)
    # Long thick tail (signature counterbalance)
    tail_e = empty(f"{name}_tail_e", (-0.30, 0, 1.0), parent=base)
    for ti in range(6):
        cyl(f"{name}_tail{ti}", r=0.10 - ti*0.012, depth=0.30, segs=10,
            loc=(0, 0, -ti*0.20 + 0.10), parent=tail_e, mat_=M_KANGAROO)
        tail_e.rotation_euler = (math.radians(70), 0, 0)
    # Head
    head_e = empty(f"{name}_he", (0, -0.10, 1.85), parent=base)
    smooth_sphere(f"{name}_head", r=0.22, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_KANGAROO, scale=(0.9, 1.2, 0.9))
    # Long pointed snout
    smooth_cone(f"{name}_snout", r1=0.13, r2=0.08, depth=0.30, segs=12,
                loc=(0, -0.22, -0.05), parent=head_e,
                mat_=M_KANGAROO).rotation_euler = (math.radians(-90), 0, 0)
    # Nose
    smooth_sphere(f"{name}_nose", r=0.04, loc=(0, -0.35, -0.05),
                  parent=head_e, mat_=M_PAINT_BLACK)
    # Tall pointed ears (signature)
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.05, r2=0.01, depth=0.30, segs=10,
                          loc=(0, side*0.12, 0.25), parent=head_e, mat_=M_KANGAROO)
        ear.rotation_euler = (math.radians(-10), 0, math.radians(side*15))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04,
                      loc=(0.04, -0.18 + side*0, 0.10), parent=head_e, mat_=M_KAN_EYE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

kangaroos = []
kang_pos = [(-8, 12, 0), (-6, 15, 0), (-3, 18, 0), (0, 15, 0),
            (4, 18, 0), (8, 15, 0), (-10, 8, 0), (10, 8, 0)]
for i, (kx, ky, kz) in enumerate(kang_pos):
    fac = math.radians(random.uniform(-30, 30) + 90)
    k = make_kangaroo(f"kang{i}", (kx, ky, kz), facing=fac)
    kangaroos.append(k)

# ============ 5 KOALAS on eucalyptus ============
def make_koala(name, loc, parent_obj=None):
    base = empty(name, loc, parent=parent_obj)
    smooth_sphere(f"{name}_body", r=0.25, segs=18, rings=12, loc=(0, 0, 0),
                  parent=base, mat_=M_KOALA, scale=(1, 1, 1.2))
    # Belly
    smooth_sphere(f"{name}_belly", r=0.20, loc=(0, -0.08, 0),
                  parent=base, mat_=M_KOALA_BELLY, scale=(1, 0.7, 1.1))
    # Head (large)
    head_e = empty(f"{name}_he", (0, -0.05, 0.30), parent=base)
    smooth_sphere(f"{name}_head", r=0.22, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_KOALA)
    # Large fluffy ears (signature)
    for side in (-1, 1):
        ear = smooth_sphere(f"{name}_ear{side}", r=0.12,
                            loc=(side*0.18, 0.05, 0.05), parent=head_e,
                            mat_=M_KOALA_EAR, scale=(1.2, 0.8, 1.2))
    # Big black nose (signature)
    smooth_sphere(f"{name}_nose", r=0.08, loc=(0, -0.18, -0.05),
                  parent=head_e, mat_=M_KOALA_NOSE, scale=(1, 0.7, 1.2))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04,
                      loc=(side*0.08, -0.16, 0.06), parent=head_e, mat_=M_PAINT_BLACK)
    # Arms holding branch
    for side in (-1, 1):
        beveled_cube(f"{name}_arm{side}", (0.05, 0.05, 0.20), bevel_offset=0.02,
                     loc=(side*0.20, 0, 0.05), parent=base, mat_=M_KOALA)
    return base

koalas = []
koala_loc_pos = [(eucalypti[0], (0, 0, 5)),
                 (eucalypti[1], (0.5, 0, 4.5)),
                 (eucalypti[2], (-0.5, 0, 5)),
                 (eucalypti[3], (0, 0.5, 4.5)),
                 (eucalypti[4], (0.3, 0, 5))]
for i, (p_obj, l_pos) in enumerate(koala_loc_pos):
    k = make_koala(f"koala{i}", l_pos, parent_obj=p_obj)
    koalas.append(k)

# ============ 4 EMUS (tall flightless birds) ============
def make_emu(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Massive feathered body
    smooth_sphere(f"{name}_body", r=0.45, segs=20, rings=14, loc=(0, 0, 1.0),
                  parent=base, mat_=M_EMU_BROWN, scale=(1.5, 1, 1.1))
    # Long neck (signature emu)
    neck_e = empty(f"{name}_neck_e", (0.40, 0, 1.20), parent=base)
    for ni in range(6):
        cyl(f"{name}_neck{ni}", r=0.10 - ni*0.008, depth=0.18, segs=10,
            loc=(0, 0, ni*0.18), parent=neck_e, mat_=M_EMU_NECK)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.20), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.12, segs=16, rings=10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_EMU_NECK)
    # Beak
    smooth_cone(f"{name}_beak", r1=0.05, r2=0.02, depth=0.18, segs=10,
                loc=(0.13, 0, -0.02), parent=head_e,
                mat_=M_EMU_BEAK).rotation_euler = (0, math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.03,
                      loc=(0.05, side*0.08, 0.05), parent=head_e, mat_=M_PAINT_BLACK)
    # Wings (small vestigial signature)
    for side in (-1, 1):
        beveled_cube(f"{name}_wing{side}", (0.08, 0.10, 0.20), bevel_offset=0.02,
                     loc=(0, side*0.25, 1.0), parent=base, mat_=M_EMU_BROWN)
    # 2 long legs (signature emu legs)
    for side in (-1, 1):
        leg_e = empty(f"{name}_leg_e{side}", (0, side*0.08, 0.65), parent=base)
        cyl(f"{name}_thigh{side}", r=0.07, depth=0.40, segs=10,
            loc=(0, 0, -0.20), parent=leg_e, mat_=M_EMU_BROWN)
        # Knee bend
        cyl(f"{name}_shin{side}", r=0.06, depth=0.50, segs=10,
            loc=(0, 0, -0.55), parent=leg_e, mat_=M_EMU_BEAK)
        # 3-toe foot
        for to in (-1, 0, 1):
            beveled_cube(f"{name}_toe{side}_{to}", (0.05, 0.10, 0.03), bevel_offset=0.01,
                         loc=(to*0.04, 0, -0.84), parent=leg_e, mat_=M_EMU_BEAK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

emus = []
emu_pos = [(-18, 15, 0), (-15, 10, 0), (16, 18, 0), (18, 12, 0)]
for i, (ex, ey, ez) in enumerate(emu_pos):
    fac = math.radians(random.uniform(-180, 180))
    e = make_emu(f"emu{i}", (ex, ey, ez), facing=fac)
    emus.append(e)

# ============ 6 DINGOES (golden wild dogs) ============
def make_dingo(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.30, segs=18, rings=12, loc=(0, 0, 0.55),
                  parent=base, mat_=M_DINGO, scale=(1.8, 1, 1))
    # Belly white
    smooth_sphere(f"{name}_belly", r=0.22, loc=(0, 0, 0.40),
                  parent=base, mat_=M_DINGO_BELLY, scale=(1.6, 0.9, 0.6))
    # Head
    head_e = empty(f"{name}_he", (0.50, 0, 0.70), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=16, rings=10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_DINGO)
    # Snout
    smooth_cone(f"{name}_snout", r1=0.10, r2=0.06, depth=0.20, segs=10,
                loc=(0.18, 0, -0.04), parent=head_e,
                mat_=M_DINGO).rotation_euler = (0, math.radians(90), 0)
    # Pointed ears
    for side in (-1, 1):
        ear = smooth_cone(f"{name}_ear{side}", r1=0.06, r2=0.005, depth=0.15, segs=10,
                          loc=(-0.05, side*0.10, 0.18), parent=head_e, mat_=M_DINGO)
        ear.rotation_euler = (math.radians(-20), 0, math.radians(side*15))
    # Glowing eyes (night signature)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.035,
                      loc=(0.06, side*0.08, 0.05), parent=head_e,
                      mat_=mat(f"{name}_e{side}", (1.0, 0.85, 0.30, 1), 0, 0.10,
                               emission=(1.0,0.85,0.30), emission_strength=8.0))
    # Nose
    smooth_sphere(f"{name}_nose", r=0.025, loc=(0.30, 0, -0.06), parent=head_e, mat_=M_PAINT_BLACK)
    # 4 legs
    for x_idx, x in enumerate((0.32, -0.32)):
        for y_idx, y in enumerate((-0.18, 0.18)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.05, depth=0.55, segs=10,
                loc=(x, y, 0.28), parent=base, mat_=M_DINGO)
    # Tail
    tail_e = empty(f"{name}_te", (-0.55, 0, 0.65), parent=base)
    for ti in range(5):
        cyl(f"{name}_tail{ti}", r=0.05 - ti*0.005, depth=0.15, segs=8,
            loc=(0, 0, ti*0.10), parent=tail_e, mat_=M_DINGO)
    tail_e.rotation_euler = (math.radians(-30), 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

dingoes = []
dingo_pos = [(-12, 20, 0), (12, 22, 0), (-8, -15, 0), (8, -15, 0), (-15, -8, 0), (15, -8, 0)]
for i, (dx, dy, dz) in enumerate(dingo_pos):
    fac = math.radians(random.uniform(-180, 180))
    d = make_dingo(f"dingo{i}", (dx, dy, dz), facing=fac)
    dingoes.append(d)

# ============ 3 COCKATOOS (white with yellow crest signature) ============
def make_cockatoo(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.22, segs=18, rings=12, loc=(0, 0, 0),
                  parent=base, mat_=M_COCK_WHITE, scale=(1.6, 1, 1.2))
    # Head
    head_e = empty(f"{name}_he", (0.35, 0, 0.10), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_COCK_WHITE)
    # CREST (signature yellow upright)
    for ci in range(6):
        ca = (ci / 6.0) * math.pi
        c_obj = beveled_cube(f"{name}_crest{ci}", (0.03, 0.04, 0.25), bevel_offset=0.01,
                            loc=(math.sin(ca-math.pi/2)*0.10, 0, 0.18),
                            parent=head_e, mat_=M_COCK_CREST)
        c_obj.rotation_euler = (math.radians(-10), 0, ca - math.pi/2)
    # Curved beak (signature)
    beak_e = empty(f"{name}_beak_e", (0.15, 0, -0.05), parent=head_e)
    smooth_cone(f"{name}_beak", r1=0.06, r2=0.02, depth=0.15, segs=10,
                loc=(0, 0, 0), parent=beak_e,
                mat_=M_COCK_BEAK).rotation_euler = (0, math.radians(70), 0)
    smooth_cone(f"{name}_beak_low", r1=0.04, r2=0.01, depth=0.08, segs=8,
                loc=(0.10, 0, -0.06), parent=beak_e,
                mat_=M_COCK_BEAK).rotation_euler = (math.radians(-30), math.radians(90), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.03,
                      loc=(0.06, side*0.10, 0.06), parent=head_e, mat_=M_PAINT_BLACK)
    # Wings spread (in flight)
    wings = []
    for side in (-1, 1):
        w_e = empty(f"{name}_we{side}", (0, side*0.20, 0.05), parent=base)
        beveled_cube(f"{name}_w{side}", (0.40, 0.65, 0.05), bevel_offset=0.02,
                     loc=(0, side*0.35, 0), parent=w_e, mat_=M_COCK_WHITE)
        # Wing tip yellow underside
        beveled_cube(f"{name}_w_tip{side}", (0.30, 0.30, 0.04),
                     loc=(0, side*0.65, 0), parent=w_e, mat_=M_COCK_CREST)
        wings.append((w_e, side))
    # Tail
    beveled_cube(f"{name}_tail", (0.30, 0.20, 0.05), loc=(-0.30, 0, 0),
                 parent=base, mat_=M_COCK_WHITE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "wings": wings}

cockatoos = [
    make_cockatoo("cock1", (-12, 6, 8), math.radians(45)),
    make_cockatoo("cock2", (12, 6, 10), math.radians(-45)),
    make_cockatoo("cock3", (0, 18, 12), math.radians(180)),
]

# ============ 2 WOMBATS ============
def make_wombat(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.30, segs=18, rings=12, loc=(0, 0, 0.30),
                  parent=base, mat_=M_WOMBAT, scale=(1.6, 1.2, 1))
    # Head (broad)
    head_e = empty(f"{name}_he", (0.40, 0, 0.35), parent=base)
    smooth_sphere(f"{name}_head", r=0.20, segs=16, rings=10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_WOMBAT)
    # Snout (broad signature wombat)
    smooth_cone(f"{name}_snout", r1=0.13, r2=0.09, depth=0.15, segs=10,
                loc=(0.18, 0, -0.05), parent=head_e,
                mat_=M_WOMBAT).rotation_euler = (0, math.radians(90), 0)
    # Tiny round ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.06,
                      loc=(-0.05, side*0.13, 0.18), parent=head_e, mat_=M_WOMBAT)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025,
                      loc=(0.08, side*0.09, 0.05), parent=head_e, mat_=M_PAINT_BLACK)
    # 4 stubby legs
    for x_idx, x in enumerate((0.30, -0.30)):
        for y_idx, y in enumerate((-0.20, 0.20)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.07, depth=0.25, segs=10,
                loc=(x, y, 0.13), parent=base, mat_=M_WOMBAT)
    return {"root": base}

wombats = [
    make_wombat("wombat1", (-10, -3, 0), math.radians(60)),
    make_wombat("wombat2", (10, -3, 0), math.radians(-60)),
]

# ============ PYTHON (signature carpet python) ============
python_e = empty("python", loc=(5, 5, 0))
python_e.rotation_euler = (0, 0, math.radians(120))
# 18 body segments curved
for si in range(18):
    t_param = si / 17.0
    sx = math.sin(t_param * math.pi * 2.5) * 1.0
    sy = -t_param * 2.5
    sr = 0.13 - si * 0.005
    seg = smooth_sphere(f"py_s{si}", r=sr, segs=14, rings=10,
                        loc=(sx, sy, 0.15 + math.sin(t_param * math.pi) * 0.05),
                        parent=python_e, mat_=M_PYTHON_PATTERN if si % 3 != 0 else M_PYTHON_DARK,
                        scale=(1.2, 1, 0.8))
# Head
head_loc_x = math.sin(0) * 1.0
smooth_sphere("py_head", r=0.18, segs=16, rings=12,
              loc=(head_loc_x, 0.3, 0.2), parent=python_e, mat_=M_PYTHON_PATTERN,
              scale=(1.2, 1.4, 0.8))
# Eyes
for side in (-1, 1):
    smooth_sphere(f"py_eye{side}", r=0.03,
                  loc=(head_loc_x + side*0.08, 0.42, 0.25), parent=python_e,
                  mat_=mat(f"py_eye_m{side}", (1.0, 0.85, 0.30, 1), 0, 0.1,
                           emission=(1.0,0.85,0.30), emission_strength=6.0))
# Tongue
beveled_cube("py_tongue", (0.02, 0.04, 0.10), loc=(head_loc_x, 0.55, 0.20),
             parent=python_e, mat_=M_PAINT_RED)

# ============================================================
# ⭐ 600 SAND GRAINS + 400 FIREFLIES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 sand grains drift
sand_particles = []
for i in range(600):
    px = random.uniform(-40, 40)
    py = random.uniform(-40, 40)
    pz = random.uniform(0.3, 4)
    s_obj = smooth_sphere(f"sand_p{i}", r=random.uniform(0.05, 0.12), segs=8, rings=6,
                          loc=(px, py, pz), mat_=M_SAND_PARTICLE)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(0.6, 1.6)
    s_obj["_amp_y"] = random.uniform(0.6, 1.6)
    s_obj["_amp_z"] = random.uniform(0.3, 0.8)
    s_obj["_speed"] = random.uniform(0.4, 0.9)
    sand_particles.append(s_obj)

# 400 fireflies vortex around campfire
fireflies_out = []
for i in range(400):
    # Concentrate around fire + scatter
    if i < 200:
        angle = random.uniform(0, math.pi*2)
        rad = random.uniform(0.5, 4.0)
        px = rad * math.cos(angle)
        py = rad * math.sin(angle)
        pz = random.uniform(0.5, 5)
    else:
        px = random.uniform(-30, 30)
        py = random.uniform(-30, 30)
        pz = random.uniform(0.5, 8)
    col = M_FIREFLY_OUT if i % 2 == 0 else M_FIREFLY_ORANGE
    f_obj = smooth_sphere(f"ff{i}", r=random.uniform(0.06, 0.10), segs=8, rings=6,
                          loc=(px, py, pz), mat_=col)
    f_obj["_phase"] = random.uniform(0, math.pi*2)
    f_obj["_base_x"] = px; f_obj["_base_y"] = py; f_obj["_base_z"] = pz
    f_obj["_amp_x"] = random.uniform(0.8, 2.0)
    f_obj["_amp_y"] = random.uniform(0.8, 2.0)
    f_obj["_amp_z"] = random.uniform(0.5, 1.5)
    f_obj["_speed"] = random.uniform(0.7, 1.4)
    fireflies_out.append(f_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Eucalyptus sway
for e in eucalypti:
    phase = e["_phase"]
    for f in range(1, total_frames + 1, 5):
        t_v = (f - 1) / fps
        e.rotation_euler = (math.sin(t_v * 0.8 + phase) * math.radians(2),
                             math.cos(t_v * 0.7 + phase) * math.radians(1.5), 0)
        e.keyframe_insert("rotation_euler", frame=f)

# Aboriginal people movement
for a in aboriginals:
    phase = a["root"]["_phase"]
    base_z = a["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        a["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.03
        a["root"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3),
                                     math.cos(t * 0.6 + phase) * math.radians(2),
                                     a["root"].rotation_euler.z)
        a["root"].keyframe_insert("location", frame=f)
        a["root"].keyframe_insert("rotation_euler", frame=f)
        a["he"].rotation_euler = (math.sin(t * 0.7 + phase) * math.radians(5), 0,
                                    math.sin(t * 0.5 + phase) * math.radians(10))
        a["he"].keyframe_insert("rotation_euler", frame=f)

# Kangaroos bound (signature high jump)
for k in kangaroos:
    phase = k["root"]["_phase"]
    base_z = k["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Massive vertical bound
        k["root"].location.z = base_z + abs(math.sin(t * 2.5 + phase)) * 0.50
        # Lean forward in flight
        k["root"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(15),
                                     k["root"].rotation_euler.y,
                                     k["root"].rotation_euler.z)
        k["root"].keyframe_insert("location", frame=f)
        k["root"].keyframe_insert("rotation_euler", frame=f)
        k["he"].rotation_euler = (math.sin(t * 2.5 + phase) * math.radians(8), 0,
                                    math.sin(t * 1.5 + phase) * math.radians(10))
        k["he"].keyframe_insert("rotation_euler", frame=f)

# Emus walk + bob heads
for e in emus:
    phase = e["root"]["_phase"]
    base_z = e["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        e["root"].location.z = base_z + abs(math.sin(t * 2.0 + phase)) * 0.10
        e["root"].keyframe_insert("location", frame=f)
        e["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(10), 0,
                                    math.sin(t * 1.5 + phase) * math.radians(15))
        e["he"].keyframe_insert("rotation_euler", frame=f)

# Dingoes prowl
for d in dingoes:
    phase = d["root"]["_phase"]
    base_z = d["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        d["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        d["root"].keyframe_insert("location", frame=f)
        d["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(10), 0,
                                    math.sin(t * 1.0 + phase) * math.radians(25))
        d["he"].keyframe_insert("rotation_euler", frame=f)

# Cockatoos flap + orbit
for c in cockatoos:
    phase = c["root"]["_phase"]
    base_x = c["root"].location.x
    base_y = c["root"].location.y
    base_z = c["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        a = t * 0.6 + phase
        rad = 14 + math.sin(t * 0.4) * 2
        c["root"].location = (rad * math.cos(a), rad * math.sin(a) + 6,
                                base_z + math.sin(t * 1.2 + phase) * 1.5)
        c["root"].rotation_euler = (0, 0, a + math.pi/2)
        c["root"].keyframe_insert("location", frame=f)
        c["root"].keyframe_insert("rotation_euler", frame=f)
        flap = math.sin(t * 6.0 + phase) * math.radians(40)
        for w_e, side in c["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)

# Campfire flames flicker
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 5.0) * 0.15
    flame_e.scale = (1 + math.sin(t * 4.0) * 0.12,
                      1 + math.cos(t * 4.5) * 0.12, s)
    flame_e.rotation_euler = (0, 0, math.sin(t * 3.0) * 0.20)
    flame_e.keyframe_insert("scale", frame=f)
    flame_e.keyframe_insert("rotation_euler", frame=f)

# Nebulas drift
for obj in bpy.data.objects:
    if obj.name.startswith("nebula_e"):
        phase = obj["_phase"]
        bx, by = obj.location.x, obj.location.y
        for f in range(1, total_frames + 1, 8):
            t = (f - 1) / fps
            obj.location = (bx + math.sin(t * 0.3 + phase) * 1.5,
                            by + math.cos(t * 0.25 + phase) * 1.5,
                            obj.location.z)
            obj.keyframe_insert("location", frame=f)

# Moon halos
for obj in bpy.data.objects:
    if obj.name.startswith("moon_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.7) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# Python undulates
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    python_e.rotation_euler = (math.sin(t * 1.2) * math.radians(5), 0,
                                math.radians(120) + math.cos(t * 0.8) * math.radians(8))
    python_e.keyframe_insert("rotation_euler", frame=f)

# ============================================================
# ⭐⭐⭐ 600 SAND drift + 400 FIREFLIES vortex (signature outback night)
# ============================================================
for s in sand_particles:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        s.location = (x, y, max(0.1, z))
        sc = 1 + math.sin(t * 2.0 + phase) * 0.20
        s.scale = (sc, sc, sc)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

# 400 FIREFLIES vortex around campfire + scatter
for ff in fireflies_out:
    phase = ff["_phase"]; speed = ff["_speed"]
    bx, by, bz = ff["_base_x"], ff["_base_y"], ff["_base_z"]
    ax, ay, az = ff["_amp_x"], ff["_amp_y"], ff["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.85 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase * 1.5)
        ff.location = (x, y, max(0.3, z))
        sc = 1 + math.sin(t * 4.0 + phase) * 0.4
        ff.scale = (sc, sc, sc)
        ff.keyframe_insert("location", frame=f)
        ff.keyframe_insert("scale", frame=f)

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
print(f"[proc_australian_outback_uluru] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_australian_outback_uluru] ONE red ground + Uluru monolith + Kata Tjuta + 6 eucalyptus + 6 aboriginals + didge chief + woman+baby + 8 kangaroos + 5 koalas + 4 emus + 6 dingoes + 3 cockatoos + 2 wombats + python + campfire + Milky Way + 600 SAND + 400 FIREFLIES")
print("⭐ FIXES: 1 ground + 600 sand drift + 400 fireflies vortex (signature outback Australia mandatory) ⭐")
