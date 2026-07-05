"""
proc_bavarian_oktoberfest_beerhall.py — 229e procédural AuroraIA (93e qualité)
Oktoberfest Bavaria: ONE wood floor + beer tent + 10 tables + 8 lederhosen men + 8 dirndl women + 4 oompah musicians + waitresses + pretzels + sausages + Alps + church + 600 beer foam + 400 confetti
FIXES : 1 ground + 600 foam + 400 confetti signature Oktoberfest
"""
import bpy, bmesh, math, random, os

random.seed(0xB47229)

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

# Oktoberfest evening palette
M_SKY = mat("sky", (0.95, 0.65, 0.42, 1.0), 0.0, 0.7, emission=(0.92,0.62,0.40), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.78, 0.40, 1.0), 0.0, 0.10, emission=(1.0,0.78,0.40), emission_strength=20.0)
M_CLOUD = mat("cloud", (1.0, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.95,0.80,0.62), emission_strength=2.0, alpha=0.85)

# Wood floor (signature beerhall)
M_FLOOR = mat("floor", (0.45, 0.30, 0.18, 1.0), 0.0, 0.75, emission=(0.42,0.28,0.16), emission_strength=0.5)
M_PLANK = mat("plank", (0.55, 0.38, 0.20, 1.0), 0.0, 0.70, emission=(0.50,0.35,0.18), emission_strength=0.5)
M_GROUND = mat("ground", (0.35, 0.28, 0.20, 1.0), 0.0, 0.85)

# Tent (signature blue-white Bavarian stripes)
M_TENT_WHITE = mat("tent_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.60, emission=(0.88,0.85,0.82), emission_strength=0.6)
M_TENT_BLUE = mat("tent_b", (0.30, 0.55, 0.85, 1.0), 0.0, 0.60, emission=(0.28,0.50,0.80), emission_strength=0.7)
M_TENT_POLE = mat("tent_p", (0.55, 0.38, 0.20, 1.0), 0.0, 0.75, emission=(0.50,0.35,0.18), emission_strength=0.4)

# Tables
M_TABLE_WOOD = mat("table_w", (0.55, 0.32, 0.18, 1.0), 0.0, 0.70, emission=(0.50,0.30,0.16), emission_strength=0.5)
M_TABLE_DARK = mat("table_d", (0.35, 0.22, 0.12, 1.0), 0.0, 0.75)

# Beer mugs + foam
M_BEER = mat("beer", (1.0, 0.75, 0.20, 1.0), 0.0, 0.20, emission=(0.95,0.70,0.20), emission_strength=2.5, alpha=0.85)
M_BEER_DARK = mat("beer_d", (0.65, 0.42, 0.15, 1.0), 0.0, 0.25, emission=(0.60,0.40,0.13), emission_strength=2.0, alpha=0.90)
M_FOAM = mat("foam", (1.0, 1.0, 0.95, 1.0), 0.0, 0.30, emission=(0.98,0.95,0.92), emission_strength=2.5)
M_MUG_GLASS = mat("mug", (0.92, 0.95, 1.0, 0.65), 0.4, 0.10, emission=(0.85,0.92,1.0), emission_strength=1.5, alpha=0.65)
M_MUG_HANDLE = mat("mug_h", (0.85, 0.85, 0.92, 0.65), 0.4, 0.15, alpha=0.75)

# Food
M_PRETZEL = mat("pretzel", (0.78, 0.45, 0.20, 1.0), 0.0, 0.55, emission=(0.72,0.42,0.18), emission_strength=0.7)
M_SAUSAGE = mat("sausage", (0.85, 0.45, 0.30, 1.0), 0.0, 0.55, emission=(0.78,0.42,0.28), emission_strength=0.6)
M_CHICKEN = mat("chicken", (0.92, 0.65, 0.30, 1.0), 0.0, 0.55, emission=(0.85,0.60,0.28), emission_strength=0.6)
M_BREAD = mat("bread", (0.85, 0.65, 0.35, 1.0), 0.0, 0.75, emission=(0.78,0.62,0.32), emission_strength=0.5)

# People skin + hair
M_SKIN_BAVARIAN = mat("skin", (0.95, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.72,0.62), emission_strength=0.4)
M_HAIR_BLOND = mat("hair_bl", (0.85, 0.65, 0.30, 1.0), 0.0, 0.65)
M_HAIR_BROWN = mat("hair_br", (0.42, 0.25, 0.12, 1.0), 0.0, 0.85)

# Lederhosen
M_LEATHER_BROWN = mat("leather", (0.40, 0.20, 0.10, 1.0), 0.0, 0.75, emission=(0.38,0.20,0.10), emission_strength=0.4)
M_SUSPENDERS = mat("susp", (0.30, 0.18, 0.10, 1.0), 0.0, 0.80)
M_EMBROIDERY_GREEN = mat("emb_g", (0.40, 0.65, 0.30, 1.0), 0.0, 0.55, emission=(0.38,0.60,0.28), emission_strength=0.7)
M_SHIRT_WHITE = mat("shirt", (0.95, 0.92, 0.88, 1.0), 0.0, 0.65, emission=(0.88,0.85,0.82), emission_strength=0.5)
M_SOCKS_WHITE = mat("socks", (0.92, 0.88, 0.82, 1.0), 0.0, 0.75)

# Dirndl
M_DIRNDL_RED = mat("dirndl_r", (0.85, 0.20, 0.20, 1.0), 0.0, 0.65, emission=(0.78,0.20,0.20), emission_strength=0.7)
M_DIRNDL_GREEN = mat("dirndl_g", (0.30, 0.55, 0.30, 1.0), 0.0, 0.65, emission=(0.28,0.50,0.28), emission_strength=0.7)
M_DIRNDL_BLUE = mat("dirndl_b", (0.25, 0.42, 0.65, 1.0), 0.0, 0.65, emission=(0.22,0.40,0.60), emission_strength=0.7)
M_DIRNDL_PURPLE = mat("dirndl_p", (0.55, 0.30, 0.65, 1.0), 0.0, 0.65, emission=(0.50,0.28,0.60), emission_strength=0.7)
M_APRON_WHITE = mat("apron_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.70, emission=(0.88,0.85,0.82), emission_strength=0.6)
M_APRON_RED = mat("apron_r", (0.85, 0.20, 0.20, 1.0), 0.0, 0.65, emission=(0.78,0.20,0.20), emission_strength=0.7)
M_APRON_GREEN = mat("apron_g", (0.30, 0.55, 0.30, 1.0), 0.0, 0.65, emission=(0.28,0.50,0.28), emission_strength=0.7)
M_RIBBON_RED = mat("ribbon_r", (0.78, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.72,0.15,0.15), emission_strength=0.8)

# Hats
M_HAT_GREEN = mat("hat_g", (0.20, 0.45, 0.20, 1.0), 0.0, 0.75, emission=(0.18,0.42,0.18), emission_strength=0.5)
M_HAT_BLACK = mat("hat_b", (0.10, 0.08, 0.06, 1.0), 0.0, 0.80)
M_FEATHER_HAT = mat("f_hat", (0.85, 0.55, 0.20, 1.0), 0.0, 0.65, emission=(0.78,0.50,0.18), emission_strength=0.7)

# Instruments
M_TUBA_BRASS = mat("tuba", (0.95, 0.72, 0.25, 1.0), 0.95, 0.18, emission=(0.90,0.68,0.22), emission_strength=1.2)
M_ACCORDION = mat("accord", (0.55, 0.18, 0.18, 1.0), 0.3, 0.45, emission=(0.50,0.18,0.18), emission_strength=0.7)
M_ACCORDION_KEYS = mat("acc_k", (0.95, 0.92, 0.88, 1.0), 0.0, 0.40, emission=(0.88,0.85,0.82), emission_strength=0.5)
M_DRUM = mat("drum_b", (0.65, 0.35, 0.20, 1.0), 0.0, 0.65, emission=(0.60,0.32,0.18), emission_strength=0.5)
M_DRUM_SKIN = mat("drum_sk", (0.92, 0.85, 0.75, 1.0), 0.0, 0.55, emission=(0.85,0.80,0.72), emission_strength=0.5)

# Alps + church
M_ALPS = mat("alps", (0.65, 0.62, 0.65, 1.0), 0.0, 0.80)
M_ALPS_SNOW = mat("alps_s", (0.98, 0.98, 1.0, 1.0), 0.0, 0.45, emission=(0.92,0.94,0.98), emission_strength=1.0)
M_CHURCH_WALL = mat("church", (0.92, 0.88, 0.78, 1.0), 0.0, 0.65, emission=(0.85,0.82,0.72), emission_strength=0.6)
M_CHURCH_ROOF = mat("church_r", (0.40, 0.32, 0.45, 1.0), 0.3, 0.55, emission=(0.38,0.32,0.42), emission_strength=0.5)
M_ONION_DOME = mat("onion", (0.55, 0.45, 0.35, 1.0), 0.5, 0.40, emission=(0.50,0.42,0.32), emission_strength=0.5)

# Lanterns + flags
M_LANTERN_FEST = mat("lant_f", (1.0, 0.78, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.78,0.30), emission_strength=12.0)
M_FLAG_BLUE = mat("flag_b", (0.30, 0.55, 0.85, 1.0), 0.0, 0.55, emission=(0.28,0.50,0.80), emission_strength=0.7)
M_FLAG_WHITE = mat("flag_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.82), emission_strength=0.6)

# Particles (signature foam + confetti)
M_FOAM_PARTICLE = mat("foam_p", (1.0, 1.0, 0.95, 1.0), 0.0, 0.20, emission=(0.98,0.95,0.92), emission_strength=3.5, alpha=0.85)
M_CONFETTI_RED = mat("c_red", (1.0, 0.30, 0.30, 1.0), 0.0, 0.30, emission=(0.95,0.30,0.30), emission_strength=3.0)
M_CONFETTI_BLUE = mat("c_blue", (0.30, 0.55, 1.0, 1.0), 0.0, 0.30, emission=(0.30,0.55,1.0), emission_strength=3.0)
M_CONFETTI_YELLOW = mat("c_yellow", (1.0, 0.92, 0.30, 1.0), 0.0, 0.30, emission=(1.0,0.92,0.30), emission_strength=3.2)
M_CONFETTI_GREEN = mat("c_green", (0.30, 1.0, 0.55, 1.0), 0.0, 0.30, emission=(0.30,1.0,0.55), emission_strength=3.0)
M_CONFETTI_PINK = mat("c_pink", (1.0, 0.55, 0.85, 1.0), 0.0, 0.30, emission=(1.0,0.55,0.85), emission_strength=3.0)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (25, 45, 28))
smooth_sphere("sun", r=5.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=5.0 + (i+1)*1.7, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

clouds = []
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    rad = random.uniform(32, 45)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(22, 30)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ ALPS BACKGROUND ============
alps_e = empty("alps", loc=(0, 35, 4))
for i in range(5):
    px = (i - 2) * 12
    py = random.uniform(-3, 3)
    pz = random.uniform(-1, 2)
    h = random.uniform(8, 14)
    smooth_cone(f"alp{i}", r1=10, r2=1.5, depth=h, segs=14,
                loc=(px, py, pz), parent=alps_e, mat_=M_ALPS)
    smooth_cone(f"alp_snow{i}", r1=3.0, r2=0.8, depth=2.5, segs=14,
                loc=(px, py, pz + h/2 - 1), parent=alps_e, mat_=M_ALPS_SNOW)

# ============ CHURCH WITH ONION DOME (signature Bavarian) ============
church_e = empty("church", loc=(-22, 25, 0))
# Main body
beveled_cube("ch_body", (4, 5, 5), bevel_offset=0.06, loc=(0, 0, 2.5),
             parent=church_e, mat_=M_CHURCH_WALL)
# Steeple tower
beveled_cube("ch_steeple", (2.5, 2.5, 6), bevel_offset=0.06, loc=(0, -2.5, 5.5),
             parent=church_e, mat_=M_CHURCH_WALL)
# Roof
for side, side_mul in zip(("L", "R"), (-1, 1)):
    roof = beveled_cube(f"ch_roof_{side}", (4.5, 2.7, 0.20), bevel_offset=0.04,
                       loc=(0, side_mul*1.5, 5.5), parent=church_e, mat_=M_CHURCH_ROOF)
    roof.rotation_euler = (math.radians(side_mul*-30), 0, 0)
# ONION DOME (signature Bavarian)
smooth_sphere("ch_dome", r=1.6, segs=22, rings=16, loc=(0, -2.5, 9.5),
              parent=church_e, mat_=M_ONION_DOME, scale=(1, 1, 1.1))
# Onion top spike
smooth_cone("ch_dome_top", r1=0.50, r2=0.10, depth=1.2, segs=14,
            loc=(0, -2.5, 10.8), parent=church_e, mat_=M_ONION_DOME)
smooth_sphere("ch_dome_ball", r=0.25, loc=(0, -2.5, 11.5),
              parent=church_e, mat_=M_TUBA_BRASS)
# Cross top
beveled_cube("ch_cross_v", (0.06, 0.06, 0.6), loc=(0, -2.5, 12.0),
             parent=church_e, mat_=M_TUBA_BRASS)
beveled_cube("ch_cross_h", (0.4, 0.06, 0.06), loc=(0, -2.5, 12.10),
             parent=church_e, mat_=M_TUBA_BRASS)
# Bell openings (4 arches)
for side in (-1, 1):
    beveled_cube(f"ch_bell{side}", (0.4, 0.10, 0.8), bevel_offset=0.03,
                 loc=(side*1.0, -3.80, 7.5), parent=church_e, mat_=M_HAT_BLACK)
# Clock face
smooth_sphere("ch_clock", r=0.50, loc=(0, -3.80, 6.0),
              parent=church_e, mat_=M_LANTERN_FEST, scale=(1, 0.2, 1))
# Clock hands
beveled_cube("ch_h_hour", (0.05, 0.05, 0.30), loc=(0, -3.85, 6.0),
             parent=church_e, mat_=M_HAT_BLACK)
beveled_cube("ch_h_min", (0.05, 0.05, 0.45), loc=(0, -3.85, 6.0),
             parent=church_e, mat_=M_HAT_BLACK)
# Stained glass windows
for wi in range(2):
    beveled_cube(f"ch_win{wi}", (1.0, 0.10, 2.0), bevel_offset=0.03,
                 loc=((wi*2 - 1)*1.0, -2.55, 2.5), parent=church_e, mat_=M_LANTERN_FEST)

# ============ ONE clean wood floor ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)
# Wood plank floor area (where festival happens)
floor_main = beveled_cube("floor_main", (40, 30, 0.30), bevel_offset=0.06,
                          loc=(0, 0, 0.10), mat_=M_FLOOR)
# Plank lines (organic 3D variation)
for i in range(40):
    px = (i - 20) * 1.0
    plank = beveled_cube(f"plank{i}", (0.95, 30, 0.04), bevel_offset=0.01,
                         loc=(px, 0, 0.27), mat_=M_PLANK if i % 2 == 0 else M_FLOOR)

# ============ BEER TENT (signature blue-white striped) ============
tent_e = empty("tent", loc=(0, 0, 0))
# Central pole
cyl("tent_pole_c", r=0.30, depth=12, segs=16, loc=(0, 0, 6),
    parent=tent_e, mat_=M_TENT_POLE)
# 4 corner poles
for x in (-1, 1):
    for y in (-1, 1):
        cyl(f"tent_pole_{x}{y}", r=0.20, depth=8, segs=14,
            loc=(x*15, y*10, 4), parent=tent_e, mat_=M_TENT_POLE)
# Tent canvas (sloped roof with stripes signature)
for stripe in range(15):
    sx = (stripe - 7) * 2.0
    col = M_TENT_WHITE if stripe % 2 == 0 else M_TENT_BLUE
    # Front slope
    front = beveled_cube(f"tent_f_{stripe}", (1.9, 12, 0.10), bevel_offset=0.03,
                        loc=(sx, -8, 9), parent=tent_e, mat_=col)
    front.rotation_euler = (math.radians(-15), 0, 0)
    # Back slope
    back = beveled_cube(f"tent_b_{stripe}", (1.9, 12, 0.10), bevel_offset=0.03,
                       loc=(sx, 8, 9), parent=tent_e, mat_=col)
    back.rotation_euler = (math.radians(15), 0, 0)
# Side walls open (festival vibe)
# Decorative tent edges (signature scalloped)
for ei in range(20):
    ex = (ei - 9.5) * 1.6
    smooth_sphere(f"tent_edge{ei}", r=0.25,
                  loc=(ex, -10.5, 8), parent=tent_e,
                  mat_=M_TENT_WHITE if ei % 2 == 0 else M_TENT_BLUE, scale=(1, 0.5, 1))
    smooth_sphere(f"tent_edge_b{ei}", r=0.25,
                  loc=(ex, 10.5, 8), parent=tent_e,
                  mat_=M_TENT_WHITE if ei % 2 == 0 else M_TENT_BLUE, scale=(1, 0.5, 1))

# Lantern strings inside tent
for li in range(20):
    lx = (li - 9.5) * 1.5
    lant_e = empty(f"lant{li}", (lx, 0, 9.5))
    smooth_sphere(f"lant_b{li}", r=0.18, loc=(0, 0, 0),
                  parent=lant_e, mat_=M_LANTERN_FEST)
    cyl(f"lant_t{li}", r=0.02, depth=0.30, segs=6,
        loc=(0, 0, 0.30), parent=lant_e, mat_=M_TABLE_DARK)
# 4 Bavarian flags
for fi in range(4):
    f_e = empty(f"bflag{fi}", ((fi*2 - 3)*4, 0, 11))
    cyl(f"bflag_p{fi}", r=0.04, depth=1.5, segs=8, loc=(0, 0, 0),
        parent=f_e, mat_=M_HAT_BLACK)
    for stripe in range(4):
        col = M_FLAG_BLUE if stripe % 2 == 0 else M_FLAG_WHITE
        beveled_cube(f"bflag_s{fi}_{stripe}", (0.6, 0.04, 0.20), bevel_offset=0.02,
                     loc=(0.30, 0, 0.5 - stripe*0.20), parent=f_e, mat_=col)

# ============ 10 LONG BEER TABLES with benches ============
tables = []
table_positions = [
    (-10, -6), (-10, 0), (-10, 6),
    (0, -7), (0, 7),
    (10, -6), (10, 0), (10, 6),
    (-5, -1), (5, -1),
]
for ti, (tx, ty) in enumerate(table_positions):
    t_e = empty(f"table{ti}", (tx, ty, 0))
    # Long table top (signature beerhall)
    beveled_cube(f"t_top{ti}", (3.5, 0.8, 0.10), bevel_offset=0.03,
                 loc=(0, 0, 0.90), parent=t_e, mat_=M_TABLE_WOOD)
    # 4 legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"t_leg{ti}_{x}{y}", r=0.06, depth=0.85, segs=10,
                loc=(x*1.5, y*0.30, 0.42), parent=t_e, mat_=M_TABLE_DARK)
    # 2 benches (one each side)
    for side in (-1, 1):
        beveled_cube(f"t_bench{ti}_{side}", (3.5, 0.4, 0.08), bevel_offset=0.02,
                     loc=(0, side*0.65, 0.55), parent=t_e, mat_=M_TABLE_WOOD)
        for x in (-1, 1):
            cyl(f"t_bench_leg{ti}_{side}_{x}", r=0.04, depth=0.5, segs=10,
                loc=(x*1.4, side*0.65, 0.25), parent=t_e, mat_=M_TABLE_DARK)
    # Place 4 beer mugs + 2 pretzels on table
    for mi in range(4):
        mx_m = (mi - 1.5) * 0.7
        mug_e = empty(f"mug{ti}_{mi}", (mx_m, 0, 1.10), parent=t_e)
        # Glass mug
        cyl(f"m_glass{ti}_{mi}", r=0.10, depth=0.35, segs=18,
            loc=(0, 0, 0.18), parent=mug_e, mat_=M_MUG_GLASS)
        # Beer inside (yellow signature)
        cyl(f"m_beer{ti}_{mi}", r=0.085, depth=0.28, segs=16,
            loc=(0, 0, 0.16), parent=mug_e, mat_=M_BEER if mi % 2 == 0 else M_BEER_DARK)
        # FOAM TOP (signature)
        cyl(f"m_foam_b{ti}_{mi}", r=0.10, depth=0.06, segs=18,
            loc=(0, 0, 0.34), parent=mug_e, mat_=M_FOAM)
        for fb in range(5):
            fa = (fb / 5.0) * math.pi * 2
            smooth_sphere(f"m_foam{ti}_{mi}_{fb}", r=0.04,
                          loc=(0.06*math.cos(fa), 0.06*math.sin(fa), 0.38),
                          parent=mug_e, mat_=M_FOAM)
        # Handle (signature stein handle)
        for hi in range(4):
            ha = math.pi * 0.5 + (hi - 1.5) * 0.4
            cyl(f"m_handle{ti}_{mi}_{hi}", r=0.015, depth=0.10, segs=6,
                loc=(0.12 + math.cos(ha)*0.04, 0, 0.18 + math.sin(ha)*0.05),
                parent=mug_e, mat_=M_MUG_HANDLE)
    # 2 pretzels per table (signature)
    for pi in range(2):
        pretzel_e = empty(f"pretzel{ti}_{pi}", ((pi*2-1)*1.2, 0.20, 1.0), parent=t_e)
        # Pretzel shape (knotted)
        for ki in range(8):
            ka = (ki / 8.0) * math.pi * 2
            kx = 0.10 * math.cos(ka)
            ky = 0.10 * math.sin(ka)
            kz = math.sin(ka * 2) * 0.04
            smooth_sphere(f"p_seg{ti}_{pi}_{ki}", r=0.04,
                          loc=(kx, ky, kz), parent=pretzel_e, mat_=M_PRETZEL,
                          scale=(1.5, 0.7, 1))
    tables.append(t_e)

# ============ 8 MEN in LEDERHOSEN ============
def make_lederhosen_man(name, loc, facing=0, action="cheer", scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs (knee-high socks)
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_hip{side_idx}", (side*0.15*scale, 0, 0.85*scale), parent=base)
        # Upper leg (lederhosen leather)
        cyl(f"{name}_thigh{side_idx}", r=0.11*scale, depth=0.45*scale, segs=12,
            loc=(0, 0, -0.22*scale), parent=hip, mat_=M_LEATHER_BROWN)
        # Calf (white socks signature)
        cyl(f"{name}_calf{side_idx}", r=0.09*scale, depth=0.40*scale, segs=12,
            loc=(0, 0, -0.65*scale), parent=hip, mat_=M_SOCKS_WHITE)
        # Sock band top
        cyl(f"{name}_sock_band{side_idx}", r=0.095*scale, depth=0.05*scale, segs=12,
            loc=(0, 0, -0.45*scale), parent=hip, mat_=M_LEATHER_BROWN)
        # Shoe
        beveled_cube(f"{name}_shoe{side_idx}", (0.14*scale, 0.30*scale, 0.10*scale), bevel_offset=0.02,
                     loc=(0, 0.05*scale, -0.85*scale), parent=hip, mat_=M_HAT_BLACK)
    # LEDERHOSEN SHORTS (signature leather + embroidery)
    smooth_cone(f"{name}_short", r1=0.32*scale, r2=0.28*scale, depth=0.45*scale, segs=14,
                loc=(0, 0, 1.05*scale), parent=base, mat_=M_LEATHER_BROWN)
    # Front pocket flap with embroidery (signature edelweiss)
    beveled_cube(f"{name}_pocket", (0.28*scale, 0.06*scale, 0.20*scale), bevel_offset=0.02,
                 loc=(0, -0.27*scale, 1.05*scale), parent=base, mat_=M_LEATHER_BROWN)
    # Embroidery flower
    smooth_sphere(f"{name}_emb", r=0.05*scale, loc=(0, -0.30*scale, 1.05*scale),
                  parent=base, mat_=M_EMBROIDERY_GREEN, scale=(1, 0.2, 1))
    # White shirt
    beveled_cube(f"{name}_shirt", (0.42*scale, 0.24*scale, 0.55*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.55*scale), parent=base, mat_=M_SHIRT_WHITE)
    # SUSPENDERS (signature crossing X)
    for side in (-1, 1):
        # Vertical strap
        susp = beveled_cube(f"{name}_susp_v{side}", (0.05*scale, 0.05*scale, 0.65*scale), bevel_offset=0.01,
                           loc=(side*0.10*scale, -0.13*scale, 1.50*scale),
                           parent=base, mat_=M_SUSPENDERS)
    # Cross horizontal strap with embroidery (signature)
    beveled_cube(f"{name}_susp_h", (0.30*scale, 0.06*scale, 0.06*scale), bevel_offset=0.02,
                 loc=(0, -0.14*scale, 1.65*scale), parent=base, mat_=M_SUSPENDERS)
    # Edelweiss embroidery on chest strap
    smooth_sphere(f"{name}_chest_emb", r=0.05*scale, loc=(0, -0.16*scale, 1.65*scale),
                  parent=base, mat_=M_EMBROIDERY_GREEN)
    # Neck
    cyl(f"{name}_neck", r=0.09*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 1.92*scale), parent=base, mat_=M_SKIN_BAVARIAN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.10*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_BAVARIAN)
    # Hair
    hair_col = M_HAIR_BLOND if hash(name) % 2 == 0 else M_HAIR_BROWN
    smooth_sphere(f"{name}_hair", r=0.20*scale, loc=(0, 0.04*scale, 0.05*scale),
                  parent=head_e, mat_=hair_col, scale=(1, 1, 0.85))
    # Mustache (signature Bavarian)
    smooth_sphere(f"{name}_must", r=0.10*scale, loc=(0, -0.15*scale, -0.05*scale),
                  parent=head_e, mat_=hair_col, scale=(1.5, 0.7, 0.4))
    # BAVARIAN HAT (signature green with feather)
    cyl(f"{name}_hat_b", r=0.30*scale, depth=0.04*scale, segs=18,
        loc=(0, 0, 0.20*scale), parent=head_e, mat_=M_HAT_GREEN)
    cyl(f"{name}_hat_c", r=0.20*scale, depth=0.18*scale, segs=16,
        loc=(0, 0, 0.32*scale), parent=head_e, mat_=M_HAT_GREEN)
    # Hat band
    cyl(f"{name}_hat_band", r=0.21*scale, depth=0.04*scale, segs=16,
        loc=(0, 0, 0.24*scale), parent=head_e, mat_=M_LEATHER_BROWN)
    # FEATHER (signature)
    for fi in range(3):
        feather = beveled_cube(f"{name}_feather{fi}", (0.02*scale, 0.04*scale, 0.25*scale), bevel_offset=0.01,
                              loc=(0.20*scale, 0.05*scale, 0.45*scale - fi*0.02*scale),
                              parent=head_e, mat_=M_FEATHER_HAT)
        feather.rotation_euler = (math.radians(-30 + fi*5), 0, math.radians(45))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Arms (holding mug raised cheer pose)
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.32*scale, 0, 1.80*scale), parent=base)
        if action == "cheer":
            # One arm raised with mug
            if side_idx == 0:
                sh.rotation_euler = (math.radians(-120), 0, math.radians(-30))
            else:
                sh.rotation_euler = (math.radians(-20), 0, math.radians(20))
        elif action == "dance":
            sh.rotation_euler = (math.radians(-90), 0, math.radians(side*-60))
        else:
            sh.rotation_euler = (math.radians(-20), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side_idx}", r=0.08*scale, depth=0.35*scale, segs=12,
            loc=(0, 0, -0.18*scale), parent=sh, mat_=M_SHIRT_WHITE)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.32*scale, segs=10,
            loc=(0, 0, -0.52*scale), parent=sh, mat_=M_SKIN_BAVARIAN)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08*scale, loc=(0, 0, -0.72*scale),
                      parent=sh, mat_=M_SKIN_BAVARIAN)
        arms_e.append(sh)
    # If cheer, add mug in hand
    if action == "cheer":
        mug_e = empty(f"{name}_mug_e", (-0.5*scale, -0.3*scale, 2.6*scale), parent=base)
        cyl(f"{name}_mug_glass", r=0.10*scale, depth=0.35*scale, segs=16,
            loc=(0, 0, 0), parent=mug_e, mat_=M_MUG_GLASS)
        cyl(f"{name}_mug_beer", r=0.085*scale, depth=0.28*scale, segs=14,
            loc=(0, 0, -0.02*scale), parent=mug_e, mat_=M_BEER)
        cyl(f"{name}_mug_foam", r=0.10*scale, depth=0.06*scale, segs=16,
            loc=(0, 0, 0.20*scale), parent=mug_e, mat_=M_FOAM)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

men_oktober = []
men_specs = [
    ("man1", (-10, -4, 1.0), math.radians(0), "cheer"),
    ("man2", (-10, 2, 1.0), math.radians(0), "cheer"),
    ("man3", (-10, 8, 1.0), math.radians(0), "dance"),
    ("man4", (10, -4, 1.0), math.radians(180), "cheer"),
    ("man5", (10, 2, 1.0), math.radians(180), "dance"),
    ("man6", (10, 8, 1.0), math.radians(180), "cheer"),
    ("man7", (-3, -5, 1.0), math.radians(45), "dance"),
    ("man8", (3, -5, 1.0), math.radians(-45), "dance"),
]
for spec in men_specs:
    name, loc, fac, act = spec
    m = make_lederhosen_man(name, loc, facing=fac, action=act)
    men_oktober.append(m)

# ============ 8 WOMEN in DIRNDL ============
def make_dirndl_woman(name, loc, dress_mat, apron_mat, facing=0, action="serve", scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long full skirt (signature dirndl)
    smooth_cone(f"{name}_skirt", r1=0.60*scale, r2=0.42*scale, depth=1.5*scale, segs=18,
                loc=(0, 0, 0.85*scale), parent=base, mat_=dress_mat)
    # Pleats
    for pl in range(10):
        pa = (pl / 10.0) * math.pi * 2
        beveled_cube(f"{name}_pleat{pl}", (0.06*scale, 0.10*scale, 1.3*scale), bevel_offset=0.01,
                     loc=(0.50*scale*math.cos(pa), 0.50*scale*math.sin(pa), 0.85*scale),
                     parent=base, mat_=dress_mat)
    # APRON (signature white/colored)
    smooth_cone(f"{name}_apron", r1=0.45*scale, r2=0.35*scale, depth=1.2*scale, segs=14,
                loc=(0, -0.05*scale, 0.95*scale), parent=base, mat_=apron_mat)
    # Apron ribbon bow (signature)
    bow_e = empty(f"{name}_bow_e", (0, 0.45*scale, 1.50*scale), parent=base)
    beveled_cube(f"{name}_bow_l", (0.20*scale, 0.05*scale, 0.10*scale), bevel_offset=0.02,
                 loc=(-0.12*scale, 0, 0), parent=bow_e, mat_=M_RIBBON_RED)
    beveled_cube(f"{name}_bow_r", (0.20*scale, 0.05*scale, 0.10*scale), bevel_offset=0.02,
                 loc=(0.12*scale, 0, 0), parent=bow_e, mat_=M_RIBBON_RED)
    beveled_cube(f"{name}_bow_c", (0.05*scale, 0.05*scale, 0.10*scale), bevel_offset=0.01,
                 loc=(0, 0, 0), parent=bow_e, mat_=M_RIBBON_RED)
    # Bow tails hanging
    for ti in range(2):
        beveled_cube(f"{name}_bow_t{ti}", (0.04*scale, 0.04*scale, 0.40*scale),
                     loc=((ti*2-1)*0.05*scale, 0, -0.25*scale), parent=bow_e, mat_=M_RIBBON_RED)
    # WAIST CINCHED bodice
    cyl(f"{name}_waist", r=0.40*scale, depth=0.12*scale, segs=18,
        loc=(0, 0, 1.55*scale), parent=base, mat_=dress_mat)
    # CORSET BODICE (signature)
    beveled_cube(f"{name}_bodice", (0.42*scale, 0.25*scale, 0.50*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.85*scale), parent=base, mat_=dress_mat)
    # Lace front detail (white)
    beveled_cube(f"{name}_lace", (0.10*scale, 0.06*scale, 0.45*scale), bevel_offset=0.02,
                 loc=(0, -0.13*scale, 1.85*scale), parent=base, mat_=M_SHIRT_WHITE)
    # White blouse top + puffy sleeves
    smooth_sphere(f"{name}_blouse", r=0.30*scale, loc=(0, 0, 2.15*scale),
                  parent=base, mat_=M_SHIRT_WHITE, scale=(1.2, 0.75, 0.5))
    # Neck
    cyl(f"{name}_neck", r=0.08*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 2.30*scale), parent=base, mat_=M_SKIN_BAVARIAN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.48*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.17*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_BAVARIAN)
    # Hair (long flowing or braids)
    hair_col = M_HAIR_BLOND if hash(name) % 2 == 0 else M_HAIR_BROWN
    smooth_sphere(f"{name}_hair", r=0.20*scale, loc=(0, 0.04*scale, 0.05*scale),
                  parent=head_e, mat_=hair_col, scale=(1.05, 1, 1.1))
    # 2 braids (signature)
    for side in (-1, 1):
        for bi in range(4):
            cyl(f"{name}_braid{side}_{bi}", r=0.025*scale, depth=0.12*scale, segs=8,
                loc=(side*0.18*scale, 0.10*scale, -bi*0.10*scale - 0.05*scale),
                parent=head_e, mat_=hair_col)
    # Hair flowers (signature)
    for fi in range(2):
        smooth_sphere(f"{name}_flower{fi}", r=0.06*scale,
                      loc=(0.12*scale*(fi*2-1), 0.05*scale, 0.18*scale),
                      parent=head_e, mat_=M_RIBBON_RED if fi == 0 else M_EMBROIDERY_GREEN)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.13*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Arms (carrying mugs or dancing)
    arms_e = []
    mugs_held = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.35*scale, 0, 2.20*scale), parent=base)
        if action == "serve":
            # Both arms holding mugs forward
            sh.rotation_euler = (math.radians(-75), 0, math.radians(side*-25))
        elif action == "dance":
            sh.rotation_euler = (math.radians(-100), 0, math.radians(side*-50))
        else:
            sh.rotation_euler = (math.radians(-20), 0, math.radians(side*-15))
        # Puffy sleeve
        smooth_sphere(f"{name}_sleeve{side_idx}", r=0.18*scale, loc=(0, 0, -0.08*scale),
                      parent=sh, mat_=M_SHIRT_WHITE, scale=(1, 1, 1.3))
        cyl(f"{name}_fa{side_idx}", r=0.06*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.45*scale), parent=sh, mat_=M_SKIN_BAVARIAN)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07*scale, loc=(0, 0, -0.62*scale),
                      parent=sh, mat_=M_SKIN_BAVARIAN)
        arms_e.append(sh)
        # 3 mugs per hand if serving (signature waitress 6 beers)
        if action == "serve":
            for mi in range(3):
                mug_e_w = empty(f"{name}_mug_e{side_idx}_{mi}",
                                 ((mi-1)*0.18*scale, 0, -0.85*scale), parent=sh)
                cyl(f"{name}_m_g{side_idx}_{mi}", r=0.08*scale, depth=0.28*scale, segs=14,
                    loc=(0, 0, 0), parent=mug_e_w, mat_=M_MUG_GLASS)
                cyl(f"{name}_m_b{side_idx}_{mi}", r=0.07*scale, depth=0.22*scale, segs=12,
                    loc=(0, 0, -0.02*scale), parent=mug_e_w, mat_=M_BEER)
                cyl(f"{name}_m_f{side_idx}_{mi}", r=0.08*scale, depth=0.05*scale, segs=14,
                    loc=(0, 0, 0.16*scale), parent=mug_e_w, mat_=M_FOAM)
                mugs_held.append(mug_e_w)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

women_oktober = []
dirndl_cols = [(M_DIRNDL_RED, M_APRON_WHITE), (M_DIRNDL_GREEN, M_APRON_WHITE),
               (M_DIRNDL_BLUE, M_APRON_RED), (M_DIRNDL_PURPLE, M_APRON_GREEN)]
women_specs = [
    ("woman1", (-3, 2, 1.0), 0, math.radians(0), "serve"),
    ("woman2", (3, 2, 1.0), 1, math.radians(0), "serve"),
    ("woman3", (-7, 5, 1.0), 2, math.radians(45), "dance"),
    ("woman4", (7, 5, 1.0), 3, math.radians(-45), "dance"),
    ("woman5", (-13, 0, 1.0), 0, math.radians(90), "serve"),
    ("woman6", (13, 0, 1.0), 1, math.radians(-90), "serve"),
    ("woman7", (-5, -10, 1.0), 2, math.radians(180), "dance"),
    ("woman8", (5, -10, 1.0), 3, math.radians(180), "dance"),
]
for spec in women_specs:
    name, loc, col_idx, fac, act = spec
    dress, apron = dirndl_cols[col_idx]
    w = make_dirndl_woman(name, loc, dress, apron, facing=fac, action=act)
    women_oktober.append(w)

# ============ 4 OOMPAH MUSICIANS ============
def make_musician(name, loc, instrument, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sitting on bench, body
    smooth_cone(f"{name}_pants", r1=0.28, r2=0.22, depth=0.50, segs=14,
                loc=(0, 0, 0.30), parent=base, mat_=M_LEATHER_BROWN)
    # Torso
    beveled_cube(f"{name}_torso", (0.40, 0.22, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 0.95), parent=base, mat_=M_SHIRT_WHITE)
    # Suspenders X
    for side in (-1, 1):
        beveled_cube(f"{name}_susp{side}", (0.04, 0.04, 0.55), bevel_offset=0.01,
                     loc=(side*0.10, -0.12, 0.95), parent=base, mat_=M_SUSPENDERS)
    # Neck + Head
    cyl(f"{name}_neck", r=0.08, depth=0.15, segs=10, loc=(0, 0, 1.30),
        parent=base, mat_=M_SKIN_BAVARIAN)
    head_e = empty(f"{name}_he", (0, 0, 1.48), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_BAVARIAN)
    smooth_sphere(f"{name}_hair", r=0.20, loc=(0, 0.04, 0.05),
                  parent=head_e, mat_=M_HAIR_BROWN, scale=(1, 1, 0.85))
    smooth_sphere(f"{name}_must", r=0.10, loc=(0, -0.15, -0.05),
                  parent=head_e, mat_=M_HAIR_BROWN, scale=(1.5, 0.7, 0.4))
    # Bavarian hat
    cyl(f"{name}_hat_b", r=0.30, depth=0.04, segs=18, loc=(0, 0, 0.20),
        parent=head_e, mat_=M_HAT_GREEN)
    cyl(f"{name}_hat_c", r=0.18, depth=0.18, segs=16, loc=(0, 0, 0.32),
        parent=head_e, mat_=M_HAT_GREEN)
    for fi in range(3):
        beveled_cube(f"{name}_feather{fi}", (0.02, 0.04, 0.25),
                     loc=(0.20, 0.05, 0.45 - fi*0.02), parent=head_e, mat_=M_FEATHER_HAT).rotation_euler = (0, 0, math.radians(45))
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.14, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Arms playing instrument
    arms_e = []
    inst_e = empty(f"{name}_inst_e", (0, -0.50, 0.85), parent=base)
    if instrument == "tuba":
        # Massive brass tuba (signature oompah)
        smooth_sphere(f"{name}_tuba_body", r=0.45, segs=22, rings=16,
                      loc=(0, 0, 0.30), parent=inst_e, mat_=M_TUBA_BRASS,
                      scale=(1.2, 1, 1.4))
        # Bell (huge flare upward signature)
        smooth_cone(f"{name}_tuba_bell", r1=0.55, r2=0.20, depth=0.50, segs=20,
                    loc=(0, 0, 0.85), parent=inst_e, mat_=M_TUBA_BRASS)
        # Mouthpiece
        cyl(f"{name}_tuba_mp", r=0.05, depth=0.20, segs=10,
            loc=(0.30, -0.30, 0.50), parent=inst_e, mat_=M_TUBA_BRASS)
        # Valves
        for v in range(3):
            cyl(f"{name}_tuba_v{v}", r=0.04, depth=0.20, segs=8,
                loc=(0.25, -0.05 + v*0.08, 0.25), parent=inst_e, mat_=M_TUBA_BRASS)
        # Coiled tubing
        for c in range(6):
            ca = (c / 6.0) * math.pi * 2
            cyl(f"{name}_tuba_c{c}", r=0.04, depth=0.30, segs=8,
                loc=(0.25*math.cos(ca), 0.25*math.sin(ca), 0.30),
                parent=inst_e, mat_=M_TUBA_BRASS)
        # Arms hold tuba
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.20), parent=base)
            sh.rotation_euler = (math.radians(-80), 0, math.radians(side*-30))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_SHIRT_WHITE)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_BAVARIAN)
            arms_e.append(sh)
    elif instrument == "accordion":
        # Accordion (signature bellows)
        for bi in range(10):
            beveled_cube(f"{name}_acc_b{bi}", (0.30, 0.04, 0.40), bevel_offset=0.02,
                         loc=(0, (bi - 4.5)*0.05, 0), parent=inst_e, mat_=M_ACCORDION)
        # End boards
        beveled_cube(f"{name}_acc_l", (0.30, 0.06, 0.50), bevel_offset=0.02,
                     loc=(0, -0.30, 0), parent=inst_e, mat_=M_HAT_BLACK)
        beveled_cube(f"{name}_acc_r", (0.30, 0.06, 0.50), bevel_offset=0.02,
                     loc=(0, 0.30, 0), parent=inst_e, mat_=M_HAT_BLACK)
        # Keys (signature)
        for ki in range(10):
            beveled_cube(f"{name}_acc_k{ki}", (0.02, 0.05, 0.06), bevel_offset=0.005,
                         loc=(0.05 + (ki%5)*0.04 - 0.10, 0.32, -0.15 + (ki//5)*0.10),
                         parent=inst_e, mat_=M_ACCORDION_KEYS)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.20), parent=base)
            sh.rotation_euler = (math.radians(-90), 0, math.radians(side*-15))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_SHIRT_WHITE)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_BAVARIAN)
            arms_e.append(sh)
    elif instrument == "trumpet":
        # Trumpet brass
        cyl(f"{name}_tp_main", r=0.04, depth=0.50, segs=10,
            loc=(0, 0, 0), parent=inst_e, mat_=M_TUBA_BRASS)
        smooth_cone(f"{name}_tp_bell", r1=0.12, r2=0.05, depth=0.25, segs=14,
                    loc=(0, 0, 0.35), parent=inst_e, mat_=M_TUBA_BRASS)
        for v in range(3):
            cyl(f"{name}_tp_v{v}", r=0.03, depth=0.10, segs=8,
                loc=(0, (v-1)*0.08, 0.05), parent=inst_e, mat_=M_TUBA_BRASS)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.20), parent=base)
            sh.rotation_euler = (math.radians(-110), 0, math.radians(side*-15))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_SHIRT_WHITE)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_BAVARIAN)
            arms_e.append(sh)
    else:  # drum
        # Bavarian drum
        cyl(f"{name}_dr_body", r=0.30, depth=0.40, segs=20,
            loc=(0, 0, 0), parent=inst_e, mat_=M_DRUM)
        cyl(f"{name}_dr_skin_t", r=0.28, depth=0.03, segs=20,
            loc=(0, 0, 0.22), parent=inst_e, mat_=M_DRUM_SKIN)
        cyl(f"{name}_dr_skin_b", r=0.28, depth=0.03, segs=20,
            loc=(0, 0, -0.22), parent=inst_e, mat_=M_DRUM_SKIN)
        # Drum bands
        for db in range(4):
            ba = (db / 4.0) * math.pi * 2
            beveled_cube(f"{name}_dr_band{db}", (0.04, 0.04, 0.46),
                         loc=(0.30*math.cos(ba), 0.30*math.sin(ba), 0),
                         parent=inst_e, mat_=M_TUBA_BRASS)
        # Sticks
        for side in (-1, 1):
            cyl(f"{name}_stick{side}", r=0.015, depth=0.30, segs=6,
                loc=(side*0.20, 0, 0.30), parent=inst_e, mat_=M_TABLE_DARK)
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.25, 0, 1.20), parent=base)
            sh.rotation_euler = (math.radians(-90), 0, math.radians(side*-30))
            cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
                loc=(0, 0, -0.15), parent=sh, mat_=M_SHIRT_WHITE)
            cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
                loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_BAVARIAN)
            arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

musicians = []
mus_pos = [(-4, 12, 0.6), (-1, 13, 0.6), (2, 13, 0.6), (5, 12, 0.6)]
mus_inst = ["tuba", "accordion", "trumpet", "drum"]
for i, (mx, my, mz) in enumerate(mus_pos):
    m = make_musician(f"mus{i}", (mx, my, mz), mus_inst[i], facing=math.radians(180))
    musicians.append(m)

# Stage platform
beveled_cube("stage", (8, 3, 0.6), bevel_offset=0.05, loc=(0, 13, 0.30), mat_=M_TABLE_WOOD)

# ============ FOOD on tables (extra sausages, chickens) ============
for ti, (tx, ty) in enumerate(table_positions[:6]):
    # Plate with sausages
    plate_e = empty(f"plate{ti}", (tx, ty - 0.25, 0.95))
    cyl(f"plate_b{ti}", r=0.18, depth=0.03, segs=18, loc=(0, 0, 0),
        parent=plate_e, mat_=M_SHIRT_WHITE)
    # 3 sausages
    for si_food in range(3):
        cyl(f"sausage{ti}_{si_food}", r=0.04, depth=0.20, segs=12,
            loc=((si_food-1)*0.07, 0, 0.04), parent=plate_e, mat_=M_SAUSAGE).rotation_euler = (math.radians(90), 0, 0)
# 4 roasted chickens on bigger plates
for ti, (tx, ty) in enumerate(table_positions[6:10]):
    smooth_sphere(f"chicken{ti}", r=0.18, segs=18, rings=12,
                  loc=(tx, ty + 0.30, 1.05), mat_=M_CHICKEN, scale=(1.4, 1, 1))
    smooth_cone(f"chicken_leg{ti}", r1=0.06, r2=0.03, depth=0.15, segs=10,
                loc=(tx, ty + 0.30, 1.10), mat_=M_CHICKEN).rotation_euler = (math.radians(60), 0, 0)

# ============================================================
# ⭐ 600 BEER FOAM + 400 CONFETTI (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 600 beer foam particles (around mugs + floating)
foam_particles = []
for i in range(600):
    # Concentrate near mugs (tables area)
    if i < 300:
        # Near table area
        tx_idx = i % len(table_positions)
        tx, ty = table_positions[tx_idx]
        px = tx + random.uniform(-2, 2)
        py = ty + random.uniform(-1, 1)
        pz = random.uniform(1.2, 3)
    else:
        px = random.uniform(-15, 15)
        py = random.uniform(-12, 12)
        pz = random.uniform(0.5, 8)
    f_obj = smooth_sphere(f"foam{i}", r=random.uniform(0.06, 0.12), segs=8, rings=6,
                          loc=(px, py, pz), mat_=M_FOAM_PARTICLE)
    f_obj["_phase"] = random.uniform(0, math.pi*2)
    f_obj["_base_x"] = px; f_obj["_base_y"] = py; f_obj["_base_z"] = pz
    f_obj["_amp_x"] = random.uniform(0.4, 1.2)
    f_obj["_amp_y"] = random.uniform(0.4, 1.2)
    f_obj["_amp_z"] = random.uniform(0.3, 0.8)
    f_obj["_speed"] = random.uniform(0.4, 1.0)
    foam_particles.append(f_obj)

# 400 confetti (signature multicolor falling/floating)
confetti_colors = [M_CONFETTI_RED, M_CONFETTI_BLUE, M_CONFETTI_YELLOW, M_CONFETTI_GREEN, M_CONFETTI_PINK]
confetti = []
for i in range(400):
    px = random.uniform(-18, 18)
    py = random.uniform(-15, 15)
    pz = random.uniform(2, 10)
    col = confetti_colors[i % 5]
    c_obj = beveled_cube(f"conf{i}", (random.uniform(0.06, 0.10),
                                         random.uniform(0.04, 0.08),
                                         random.uniform(0.005, 0.012)), bevel_offset=0.002,
                          loc=(px, py, pz), mat_=col)
    c_obj.rotation_euler = (random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2))
    c_obj["_phase"] = random.uniform(0, math.pi*2)
    c_obj["_base_x"] = px; c_obj["_base_y"] = py; c_obj["_base_z"] = pz
    c_obj["_speed"] = random.uniform(0.5, 1.2)
    c_obj["_drift_x"] = random.uniform(-1.0, 1.0)
    c_obj["_drift_y"] = random.uniform(-1.0, 1.0)
    confetti.append(c_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Men cheers (raise mug + body sway)
for m in men_oktober:
    phase = m["root"]["_phase"]
    base_z = m["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        m["root"].location.z = base_z + abs(math.sin(t * 2.0 + phase)) * 0.10
        m["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(6),
                                     math.cos(t * 1.2 + phase) * math.radians(4),
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("location", frame=f)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        # Cheer arm raise/lower
        base_rx = m["arms"][0].rotation_euler.x
        m["arms"][0].rotation_euler = (base_rx + math.sin(t * 1.5 + phase) * math.radians(20), 0,
                                          m["arms"][0].rotation_euler.z)
        m["arms"][0].keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                    math.sin(t * 1.2 + phase) * math.radians(15))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Women dance/serve (twirl + body sway)
for w in women_oktober:
    phase = w["root"]["_phase"]
    base_z = w["root"].location.z
    base_rz = w["root"].rotation_euler.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        w["root"].location.z = base_z + abs(math.sin(t * 2.0 + phase)) * 0.08
        # Twirl
        w["root"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5),
                                     math.cos(t * 1.2 + phase) * math.radians(4),
                                     base_rz + math.sin(t * 0.8 + phase) * math.radians(20))
        w["root"].keyframe_insert("location", frame=f)
        w["root"].keyframe_insert("rotation_euler", frame=f)
        for ai, arm in enumerate(w["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 2.0 + phase + ai * math.pi) * math.radians(10)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        w["he"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                    math.sin(t * 1.2 + phase) * math.radians(15))
        w["he"].keyframe_insert("rotation_euler", frame=f)

# Musicians play (arms move)
for m in musicians:
    phase = m["root"]["_phase"]
    base_z = m["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        m["root"].location.z = base_z + math.sin(t * 2.0 + phase) * 0.05
        m["root"].keyframe_insert("location", frame=f)
        for ai, arm in enumerate(m["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 5.0 + phase + ai * math.pi) * math.radians(15)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0,
                                    math.sin(t * 1.5 + phase) * math.radians(10))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Clouds drift
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 0.7,
                        by + math.cos(t * 0.25 + phase) * 0.7,
                        c_e.location.z)
        c_e.keyframe_insert("location", frame=f)

# Sun halos
for obj in bpy.data.objects:
    if obj.name.startswith("sun_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.7) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 600 BEER FOAM + 400 CONFETTI (signature Oktoberfest)
# ============================================================
for f_p in foam_particles:
    phase = f_p["_phase"]; speed = f_p["_speed"]
    bx, by, bz = f_p["_base_x"], f_p["_base_y"], f_p["_base_z"]
    ax, ay, az = f_p["_amp_x"], f_p["_amp_y"], f_p["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        # Rise upward (foam)
        z = bz + (speed * t * 0.5) % 6
        f_p.location = (x, y, min(8, z))
        sc = 1 + math.sin(t * 3.0 + phase) * 0.25
        f_p.scale = (sc, sc, sc)
        f_p.keyframe_insert("location", frame=f)
        f_p.keyframe_insert("scale", frame=f)

# 400 CONFETTI fall + drift
for c in confetti:
    phase = c["_phase"]; speed = c["_speed"]
    bx, by, bz = c["_base_x"], c["_base_y"], c["_base_z"]
    drift_x = c["_drift_x"]; drift_y = c["_drift_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Slow descent
        z = bz - (speed * t * 0.5) % 8
        x = bx + drift_x * math.sin(t * 1.5 + phase) * 0.8
        y = by + drift_y * math.cos(t * 1.3 + phase) * 0.8
        c.location = (x, y, max(0.5, z))
        # Tumble
        c.rotation_euler = (phase + t * 2.0, phase + t * 1.6, phase + t * 2.2)
        c.keyframe_insert("location", frame=f)
        c.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_bavaria_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_bavarian_oktoberfest_beerhall] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_bavarian_oktoberfest_beerhall] ONE wood floor + Bavarian tent + 10 tables 40+ mugs + 8 lederhosen + 8 dirndl + 4 oompah musicians + Alps + church onion dome + lanterns + 600 FOAM + 400 CONFETTI")
print("⭐ FIXES: 1 ground + 600 beer foam + 400 confetti (signature Oktoberfest mandatory) ⭐")
