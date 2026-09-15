"""
proc_amsterdam_canals_dutch_houses.py — 261e procédural AuroraIA (126e qualité)
Amsterdam canals: 12 narrow tall Dutch houses with stepped gables + 6 arched bridges + canals + 4 bicycles + boats + windmill + 6 people cycling + dogs + 4 swans + 600 tulip petals + 400 bubbles
FIXES : 1 ground + 600 tulip petals + 400 soap bubbles (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB261)

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

# Pastel sky
M_SKY = mat("sky", (0.85, 0.82, 0.88, 1.0), 0.0, 0.7, emission=(0.85,0.82,0.88), emission_strength=1.8)
M_CLOUD_W = mat("cloud", (0.98, 0.98, 0.98, 1.0), 0.0, 0.7, emission=(0.95,0.95,0.95), emission_strength=1.5)
M_SUN_AM = mat("sun", (1.0, 0.95, 0.75, 1.0), 0.0, 0.1, emission=(1.0,0.95,0.75), emission_strength=10.0)

# Ground brick pavement
M_BRICK = mat("brick", (0.55, 0.32, 0.22, 1.0), 0.0, 0.85, emission=(0.50,0.32,0.22), emission_strength=0.4)
M_BRICK_DARK = mat("brick_d", (0.35, 0.22, 0.15, 1.0), 0.0, 0.85)
M_PAVEMENT = mat("pave", (0.62, 0.55, 0.48, 1.0), 0.0, 0.85, emission=(0.55,0.52,0.48), emission_strength=0.4)

# Canal water (signature dark green)
M_CANAL = mat("canal", (0.18, 0.32, 0.30, 1.0), 0.1, 0.20, emission=(0.18,0.32,0.30), emission_strength=1.0, alpha=0.78)
M_CANAL_DEEP = mat("canal_d", (0.10, 0.22, 0.20, 1.0), 0.1, 0.25, alpha=0.85)

# Dutch house colors (signature varied)
M_HOUSE_DARK_RED = mat("h_dr", (0.55, 0.20, 0.18, 1.0), 0.0, 0.85, emission=(0.52,0.20,0.18), emission_strength=0.4)
M_HOUSE_CREAM = mat("h_cr", (0.92, 0.85, 0.65, 1.0), 0.0, 0.80, emission=(0.85,0.80,0.62), emission_strength=0.5)
M_HOUSE_BROWN = mat("h_br", (0.55, 0.35, 0.20, 1.0), 0.0, 0.85, emission=(0.50,0.32,0.20), emission_strength=0.4)
M_HOUSE_OCHRE = mat("h_oc", (0.85, 0.62, 0.32, 1.0), 0.0, 0.80, emission=(0.78,0.58,0.32), emission_strength=0.5)
M_HOUSE_GREEN = mat("h_g", (0.18, 0.42, 0.30, 1.0), 0.0, 0.80, emission=(0.18,0.40,0.30), emission_strength=0.4)
M_HOUSE_GREY = mat("h_gr", (0.55, 0.55, 0.55, 1.0), 0.0, 0.85)
M_HOUSE_BLACK = mat("h_bk", (0.15, 0.15, 0.18, 1.0), 0.0, 0.85)
HOUSE_COLORS_AM = [M_HOUSE_DARK_RED, M_HOUSE_CREAM, M_HOUSE_BROWN, M_HOUSE_OCHRE,
                    M_HOUSE_GREEN, M_HOUSE_GREY, M_HOUSE_BLACK]

# Roof tiles
M_ROOF_DARK_AM = mat("roof_d", (0.32, 0.22, 0.15, 1.0), 0.0, 0.80, emission=(0.30,0.22,0.15), emission_strength=0.3)
M_ROOF_RED = mat("roof_r", (0.62, 0.22, 0.15, 1.0), 0.0, 0.80, emission=(0.58,0.22,0.15), emission_strength=0.5)

# White trim signature
M_TRIM_WHITE = mat("trim_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.65, emission=(0.92,0.90,0.85), emission_strength=0.6)
M_WINDOW_LIT_AM = mat("win", (1.0, 0.88, 0.55, 1.0), 0.0, 0.20, emission=(1.0,0.88,0.55), emission_strength=4.0)
M_WINDOW_DARK = mat("win_d", (0.18, 0.22, 0.28, 1.0), 0.3, 0.20, alpha=0.65)
M_FRAME_DARK = mat("frame", (0.18, 0.15, 0.12, 1.0), 0.0, 0.80)

# Bicycle (signature Dutch black)
M_BIKE_BLACK = mat("bike_bk", (0.10, 0.08, 0.08, 1.0), 0.4, 0.30, emission=(0.10,0.08,0.08), emission_strength=0.4)
M_BIKE_CHROME = mat("bike_c", (0.85, 0.85, 0.85, 1.0), 0.9, 0.20, emission=(0.80,0.80,0.80), emission_strength=0.5)
M_BIKE_LEATHER = mat("bike_l", (0.42, 0.25, 0.15, 1.0), 0.0, 0.65)

# Boat
M_BOAT_WHITE = mat("bt_w", (0.92, 0.88, 0.82, 1.0), 0.0, 0.70, emission=(0.88,0.85,0.80), emission_strength=0.5)
M_BOAT_WOOD = mat("bt_w_w", (0.55, 0.32, 0.18, 1.0), 0.0, 0.75)

# Windmill
M_WINDMILL_BODY = mat("wm_b", (0.78, 0.65, 0.42, 1.0), 0.0, 0.80, emission=(0.72,0.62,0.42), emission_strength=0.5)
M_WINDMILL_ROOF = mat("wm_r", (0.42, 0.32, 0.20, 1.0), 0.0, 0.80)
M_WINDMILL_BLADE = mat("wm_bl", (0.42, 0.28, 0.15, 1.0), 0.0, 0.65)
M_WINDMILL_SAIL = mat("wm_s", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65, emission=(0.90,0.88,0.85), emission_strength=0.5)

# Tulip colors signature
M_TULIP_RED = mat("tu_r", (0.95, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.92,0.18,0.20), emission_strength=2.0)
M_TULIP_PINK = mat("tu_p", (0.95, 0.55, 0.78, 1.0), 0.0, 0.45, emission=(0.92,0.52,0.75), emission_strength=1.8)
M_TULIP_YELLOW = mat("tu_y", (1.0, 0.92, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.88,0.20), emission_strength=2.0)
M_TULIP_ORANGE = mat("tu_o", (1.0, 0.55, 0.18, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.18), emission_strength=2.0)
M_TULIP_PURPLE = mat("tu_pu", (0.62, 0.25, 0.85, 1.0), 0.0, 0.45, emission=(0.60,0.25,0.82), emission_strength=1.8)
M_TULIP_WHITE = mat("tu_w", (0.98, 0.95, 0.92, 1.0), 0.0, 0.40, emission=(0.95,0.92,0.90), emission_strength=1.5)
TULIP_COLORS = [M_TULIP_RED, M_TULIP_PINK, M_TULIP_YELLOW, M_TULIP_ORANGE, M_TULIP_PURPLE, M_TULIP_WHITE]
M_TULIP_STEM = mat("tu_st", (0.20, 0.55, 0.22, 1.0), 0.0, 0.65, emission=(0.18,0.52,0.22), emission_strength=0.5)
M_TULIP_LEAF = mat("tu_lf", (0.30, 0.65, 0.25, 1.0), 0.0, 0.65, emission=(0.28,0.60,0.25), emission_strength=0.5)

# Skin
M_SKIN_PALE_NL = mat("skin", (0.95, 0.85, 0.72, 1.0), 0.0, 0.55, emission=(0.90,0.82,0.72), emission_strength=0.4)

# Hair Dutch
M_HAIR_BLOND_NL = mat("h_bl", (0.92, 0.75, 0.30, 1.0), 0.0, 0.55)
M_HAIR_BROWN_NL = mat("h_br", (0.42, 0.25, 0.12, 1.0), 0.0, 0.60)
M_HAIR_RED_NL = mat("h_r", (0.78, 0.32, 0.10, 1.0), 0.0, 0.60)
HAIR_NL = [M_HAIR_BLOND_NL, M_HAIR_BROWN_NL, M_HAIR_RED_NL]

# Cyclist clothes
M_COAT_NAVY = mat("co_n", (0.18, 0.28, 0.45, 1.0), 0.0, 0.75, emission=(0.18,0.28,0.45), emission_strength=0.4)
M_COAT_RED_NL = mat("co_r", (0.78, 0.18, 0.20, 1.0), 0.0, 0.70, emission=(0.72,0.18,0.20), emission_strength=0.5)
M_COAT_YELLOW = mat("co_y", (0.95, 0.78, 0.18, 1.0), 0.0, 0.65, emission=(0.90,0.75,0.20), emission_strength=0.7)
M_COAT_GREEN_NL = mat("co_g", (0.20, 0.55, 0.32, 1.0), 0.0, 0.70, emission=(0.18,0.52,0.30), emission_strength=0.5)
M_COAT_PURPLE_NL = mat("co_p", (0.55, 0.30, 0.78, 1.0), 0.0, 0.70, emission=(0.52,0.30,0.75), emission_strength=0.5)
M_JEANS_BLUE = mat("jeans", (0.18, 0.32, 0.55, 1.0), 0.0, 0.80)
COAT_NL = [M_COAT_NAVY, M_COAT_RED_NL, M_COAT_YELLOW, M_COAT_GREEN_NL, M_COAT_PURPLE_NL]

# Dog
M_DOG_BROWN = mat("dg_b", (0.55, 0.32, 0.18, 1.0), 0.0, 0.75, emission=(0.50,0.30,0.18), emission_strength=0.4)
M_DOG_WHITE = mat("dg_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.75)
M_DOG_BLACK = mat("dg_bk", (0.12, 0.10, 0.10, 1.0), 0.0, 0.80)

# Swan
M_SWAN_WHITE = mat("sw_w", (0.95, 0.95, 0.92, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.90), emission_strength=0.6)
M_SWAN_BEAK = mat("sw_b", (1.0, 0.55, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.20), emission_strength=1.0)

# Eye
M_EYE_DARK_NL = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_BLUE_NL = mat("eye_b", (0.30, 0.55, 0.85, 1.0), 0.0, 0.20, emission=(0.28,0.55,0.85), emission_strength=1.0)

# Cheeks
M_CHEEK = mat("cheek", (0.95, 0.65, 0.55, 1.0), 0.0, 0.55)

# Trees (small linden)
M_TREE_TRUNK = mat("tt", (0.42, 0.28, 0.15, 1.0), 0.0, 0.85)
M_TREE_LEAF = mat("tl", (0.32, 0.65, 0.30, 1.0), 0.0, 0.70, emission=(0.30,0.62,0.30), emission_strength=0.4)

# Bubble
M_BUBBLE_AM = mat("bub", (0.85, 0.92, 0.95, 1.0), 0.0, 0.10, emission=(0.85,0.92,0.95), emission_strength=2.0, alpha=0.45)

# Bell + flag
M_FLAG_RED_NL = mat("fl_r", (0.78, 0.15, 0.15, 1.0), 0.0, 0.55)
M_FLAG_WHITE_NL = mat("fl_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55)
M_FLAG_BLUE_NL = mat("fl_b", (0.18, 0.32, 0.62, 1.0), 0.0, 0.55)

# ============ SKY ============
sky = smooth_sphere("sky", r=280, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
# Sun soft
sun = smooth_sphere("sun", r=4, segs=24, rings=18, loc=(-40, 80, 60), mat_=M_SUN_AM)
# Fluffy clouds
for ci in range(20):
    cax = random.uniform(-100, 100); cay = random.uniform(-100, 100)
    caz = random.uniform(30, 60)
    cloud_e = empty(f"cloud{ci}", (cax, cay, caz))
    for cli in range(random.randint(3, 5)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(2.5, 4.5), segs=16, rings=10,
                      loc=(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD_W, scale=(1.4, 1.2, 0.7))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)

# ============ ONE clean brick pavement ground ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_PAVEMENT)
# Brick paving signature pattern
for ti in range(40):
    for tj in range(40):
        tx_g = -58 + ti * 3
        ty_g = -58 + tj * 3
        # Avoid canal area
        if -25 < ty_g < 5: continue
        bc = M_BRICK if (ti + tj) % 3 == 0 else M_BRICK_DARK if (ti + tj) % 3 == 1 else M_PAVEMENT
        beveled_cube(f"bk{ti}_{tj}", (2.8, 0.8, 0.04), bevel_offset=0.01,
                     loc=(tx_g, ty_g, 0.12), mat_=bc)

# ============ CANAL (signature serpentine) ============
canal_e = empty("canal", (0, -10, 0))
beveled_cube("c_main", (120, 18, 0.20), bevel_offset=0.08, loc=(0, 0, 0.10),
             parent=canal_e, mat_=M_CANAL)
beveled_cube("c_deep", (115, 16, 0.15), bevel_offset=0.06, loc=(0, 0, 0.15),
             parent=canal_e, mat_=M_CANAL_DEEP)
# Stone canal walls
for side in (-1, 1):
    beveled_cube(f"c_w{side}", (120, 0.6, 1.2), bevel_offset=0.06,
                 loc=(0, side*9.3, 0.4), parent=canal_e, mat_=M_BRICK_DARK)
# Sunset reflections
for ri in range(25):
    rx = random.uniform(-55, 55); ry = random.uniform(-7, 7)
    cyl(f"refl{ri}", r=random.uniform(0.30, 0.60), depth=0.04, segs=14,
        loc=(rx, ry, 0.18), parent=canal_e, mat_=M_CLOUD_W)

# ============ 12 DUTCH HOUSES (signature narrow tall stepped gables) ============
def make_dutch_house(name, loc, scale=1.0, facing=0, h_color=None, gable_type="step"):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    if h_color is None:
        h_color = random.choice(HOUSE_COLORS_AM)
    # Narrow tall body (signature 3m wide)
    width = 3.5
    depth = 5
    height = random.uniform(10, 14)
    beveled_cube(f"{name}_body", (width, depth, height), bevel_offset=0.10,
                 loc=(0, 0, height/2), parent=base, mat_=h_color)
    # White trim around windows/door
    # Floors visible by horizontal trim lines
    for fi in range(int(height/2.5)):
        fz = 2.5 + fi * 2.5
        if fz > height: break
        cyl(f"{name}_fl_trim{fi}", r=0.06, depth=width+0.1, segs=8,
            loc=(0, -depth/2, fz), parent=base, mat_=M_TRIM_WHITE).rotation_euler = (0, math.radians(90), 0)
    # 3 windows per floor (signature large)
    for fi in range(int(height/2.5)):
        fz = 1.5 + fi * 2.5
        if fz > height - 1.5: break
        for wi in range(3):
            wx_w = -1.2 + wi * 1.2
            # Window glow
            beveled_cube(f"{name}_w{fi}_{wi}", (0.8, 0.10, 1.2), bevel_offset=0.04,
                         loc=(wx_w, -depth/2 + 0.02, fz), parent=base, mat_=M_WINDOW_LIT_AM)
            # White frame
            beveled_cube(f"{name}_wf{fi}_{wi}", (0.9, 0.12, 1.3), bevel_offset=0.04,
                         loc=(wx_w, -depth/2, fz), parent=base, mat_=M_TRIM_WHITE)
            # Cross pattern
            beveled_cube(f"{name}_wcv{fi}_{wi}", (0.06, 0.14, 1.2), bevel_offset=0.005,
                         loc=(wx_w, -depth/2 - 0.01, fz), parent=base, mat_=M_TRIM_WHITE)
            beveled_cube(f"{name}_wch{fi}_{wi}", (0.9, 0.14, 0.06), bevel_offset=0.005,
                         loc=(wx_w, -depth/2 - 0.01, fz), parent=base, mat_=M_TRIM_WHITE)
    # Door front signature
    beveled_cube(f"{name}_door", (1.0, 0.20, 2.2), bevel_offset=0.06,
                 loc=(0, -depth/2, 1.1), parent=base, mat_=M_FRAME_DARK)
    # Steps to door
    for si in range(3):
        beveled_cube(f"{name}_st{si}", (1.4, 0.30, 0.15), bevel_offset=0.04,
                     loc=(0, -depth/2 - 0.20 - si*0.30, 0.08 + si*0.15),
                     parent=base, mat_=M_HOUSE_GREY)
    # GABLE TOP (signature stepped or bell)
    if gable_type == "step":
        # STEPPED GABLE signature
        for ti in range(6):
            tw = width - ti * 0.50
            beveled_cube(f"{name}_g{ti}", (tw, depth + 0.10, 0.50), bevel_offset=0.06,
                         loc=(0, 0, height + 0.25 + ti*0.40), parent=base, mat_=h_color)
            # Decorative trim
            cyl(f"{name}_gt{ti}", r=0.06, depth=tw+0.1, segs=8,
                loc=(0, -depth/2 - 0.05, height + 0.5 + ti*0.40), parent=base,
                mat_=M_TRIM_WHITE).rotation_euler = (0, math.radians(90), 0)
        # Top finial
        smooth_cone(f"{name}_fin", r1=0.20, r2=0.02, depth=0.8, segs=10,
                    loc=(0, 0, height + 3.0), parent=base, mat_=h_color)
    elif gable_type == "bell":
        # BELL GABLE signature (curved S-shape)
        for ti in range(8):
            tw = width * (1 - ti*0.10 + math.sin(ti*0.5)*0.20)
            if tw < 0.5: tw = 0.5
            beveled_cube(f"{name}_bg{ti}", (tw, depth + 0.10, 0.30), bevel_offset=0.10,
                         loc=(0, 0, height + 0.15 + ti*0.30), parent=base, mat_=h_color)
        # Top
        smooth_sphere(f"{name}_bt", r=0.30, loc=(0, 0, height + 2.7), parent=base, mat_=h_color)
    else:  # neck
        # NECK GABLE signature (narrow on top with shoulders)
        beveled_cube(f"{name}_n_s", (width-0.5, depth+0.10, 0.80), bevel_offset=0.08,
                     loc=(0, 0, height + 0.40), parent=base, mat_=h_color)
        # Narrow neck
        for ti in range(4):
            beveled_cube(f"{name}_n_n{ti}", (1.5, depth+0.10, 0.50), bevel_offset=0.06,
                         loc=(0, 0, height + 0.95 + ti*0.50), parent=base, mat_=h_color)
        # Triangular top
        smooth_cone(f"{name}_n_t", r1=0.80, r2=0.05, depth=1.2, segs=3,
                    loc=(0, 0, height + 3.0), parent=base, mat_=h_color).rotation_euler = (0, 0, math.radians(30))
    # HOIST BEAM signature (Amsterdam houses have these for furniture)
    beveled_cube(f"{name}_hoist", (0.30, 1.0, 0.20), bevel_offset=0.06,
                 loc=(0, -depth/2 - 0.5, height + 0.5), parent=base, mat_=M_FRAME_DARK)
    # Hook
    cyl(f"{name}_hook", r=0.05, depth=0.20, segs=8, loc=(0, -depth/2 - 0.95, height + 0.3),
        parent=base, mat_=M_BIKE_CHROME)
    # Decorative house plate
    beveled_cube(f"{name}_plate", (0.40, 0.06, 0.40), bevel_offset=0.04, loc=(0, -depth/2 - 0.05, 4.5),
                 parent=base, mat_=M_TRIM_WHITE)
    # FLOWER BOXES on windows (signature)
    if random.random() > 0.4:
        for fbi in range(3):
            for wbi in range(3):
                wbz = 1.5 + fbi * 2.5
                wbx = -1.2 + wbi * 1.2
                if wbz > height - 1.5: continue
                # Box
                beveled_cube(f"{name}_fb{fbi}_{wbi}", (0.7, 0.20, 0.15), bevel_offset=0.04,
                             loc=(wbx, -depth/2 - 0.10, wbz - 0.7), parent=base, mat_=M_HOUSE_BROWN)
                # Tulip flowers in box
                for tui in range(3):
                    tu_x = wbx - 0.25 + tui * 0.25
                    smooth_sphere(f"{name}_tu{fbi}_{wbi}_{tui}", r=0.06,
                                  loc=(tu_x, -depth/2 - 0.10, wbz - 0.55),
                                  parent=base, mat_=random.choice(TULIP_COLORS))
                    # Stem
                    cyl(f"{name}_tu_st{fbi}_{wbi}_{tui}", r=0.01, depth=0.15, segs=6,
                        loc=(tu_x, -depth/2 - 0.10, wbz - 0.65), parent=base, mat_=M_TULIP_STEM)
    return base

houses = []
# Houses along canal on both sides
gable_types = ["step", "bell", "neck"]
house_pos = []
# Front row 6 houses
for hi in range(6):
    house_pos.append((-25 + hi*10, -25, math.radians(0), gable_types[hi % 3]))
# Back row 6 houses
for hi in range(6):
    house_pos.append((-25 + hi*10, 5, math.radians(180), gable_types[(hi+1) % 3]))

for i, (hx, hy, fac, gt) in enumerate(house_pos):
    h = make_dutch_house(f"house{i}", (hx, hy, 0), scale=1.0, facing=fac,
                          h_color=HOUSE_COLORS_AM[i % len(HOUSE_COLORS_AM)], gable_type=gt)
    houses.append(h)

# ============ 6 ARCHED BRIDGES (signature brick) ============
def make_bridge(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Main arched span
    for ai in range(15):
        aa = math.pi * ai / 14.0
        ax_b = math.cos(aa) * 5
        az_b = math.sin(aa) * 3
        # Arch stones
        smooth_sphere(f"{name}_a{ai}", r=0.5, segs=14, rings=10,
                      loc=(ax_b, 0, az_b - 1), parent=base, mat_=M_BRICK)
    # Bridge deck (signature)
    deck_e = empty(f"{name}_deck_e", (0, 0, 2.5), parent=base)
    for di in range(11):
        beveled_cube(f"{name}_d{di}", (1.0, 3.5, 0.30), bevel_offset=0.06,
                     loc=(-5 + di*1.0, 0, 0), parent=deck_e, mat_=M_BRICK_DARK)
    # Railings signature
    for side in (-1, 1):
        beveled_cube(f"{name}_r{side}", (10, 0.10, 0.50), bevel_offset=0.04,
                     loc=(0, side*1.7, 3.0), parent=base, mat_=M_TRIM_WHITE)
        # Posts
        for pi in range(6):
            cyl(f"{name}_rp{side}_{pi}", r=0.06, depth=0.6, segs=8,
                loc=(-5 + pi*2, side*1.7, 2.9), parent=base, mat_=M_TRIM_WHITE)
    # Lamps on bridge corners (signature)
    for corner_x in (-1, 1):
        for corner_y in (-1, 1):
            lamp_e = empty(f"{name}_l{corner_x}_{corner_y}_e",
                            (corner_x*4.5, corner_y*1.7, 2.8), parent=base)
            cyl(f"{name}_l_p{corner_x}_{corner_y}", r=0.05, depth=1.5, segs=8,
                loc=(0, 0, 0.75), parent=lamp_e, mat_=M_FRAME_DARK)
            # Lamp head
            smooth_sphere(f"{name}_l_h{corner_x}_{corner_y}", r=0.20,
                          loc=(0, 0, 1.6), parent=lamp_e, mat_=M_WINDOW_LIT_AM, scale=(1, 1, 1.2))
    return base

bridges = []
bridge_pos = [(-40, -10, math.radians(90)), (-20, -10, math.radians(90)),
              (0, -10, math.radians(90)), (20, -10, math.radians(90)),
              (40, -10, math.radians(90)), (-50, -10, math.radians(90))]
for i, (bx, by, fac) in enumerate(bridge_pos):
    b = make_bridge(f"bridge{i}", (bx, by, 0), scale=1.0, facing=fac)
    bridges.append(b)

# ============ 4 BICYCLES (signature Dutch parked) ============
def make_bicycle(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # 2 wheels
    for side in (-1, 1):
        wheel_e = empty(f"{name}_w{side}_e", (side*0.6, 0, 0.35), parent=base)
        wheel_e.rotation_euler = (math.radians(90), 0, 0)
        # Tire
        cyl(f"{name}_t{side}", r=0.35, depth=0.05, segs=18, loc=(0, 0, 0),
            parent=wheel_e, mat_=M_BIKE_BLACK)
        # Rim signature
        cyl(f"{name}_r{side}", r=0.30, depth=0.04, segs=18, loc=(0, 0, 0.025),
            parent=wheel_e, mat_=M_BIKE_CHROME)
        # Spokes
        for sp in range(8):
            spa = (sp / 8.0) * math.pi * 2
            beveled_cube(f"{name}_sp{side}_{sp}", (0.02, 0.02, 0.25), bevel_offset=0.005,
                         loc=(0, 0, 0.025), parent=wheel_e,
                         mat_=M_BIKE_CHROME).rotation_euler = (0, 0, spa)
    # Frame (signature double tube diamond)
    # Top tube
    cyl(f"{name}_tt", r=0.04, depth=1.0, segs=8, loc=(0, 0, 0.70),
        parent=base, mat_=M_BIKE_BLACK).rotation_euler = (0, math.radians(90), 0)
    # Down tube
    cyl(f"{name}_dt", r=0.04, depth=1.0, segs=8, loc=(0, 0, 0.45),
        parent=base, mat_=M_BIKE_BLACK).rotation_euler = (0, math.radians(80), 0)
    # Seat tube
    cyl(f"{name}_seat_t", r=0.04, depth=0.50, segs=8, loc=(-0.5, 0, 0.65),
        parent=base, mat_=M_BIKE_BLACK)
    # Seat post
    cyl(f"{name}_sp_t", r=0.025, depth=0.20, segs=8, loc=(-0.5, 0, 0.95),
        parent=base, mat_=M_BIKE_CHROME)
    # Leather saddle (signature)
    beveled_cube(f"{name}_sad", (0.30, 0.15, 0.05), bevel_offset=0.04,
                 loc=(-0.5, 0, 1.05), parent=base, mat_=M_BIKE_LEATHER)
    # Handlebars
    cyl(f"{name}_hb_p", r=0.025, depth=0.40, segs=8, loc=(0.5, 0, 0.85),
        parent=base, mat_=M_BIKE_CHROME)
    # Handlebar bar
    cyl(f"{name}_hb_b", r=0.025, depth=0.50, segs=8, loc=(0.5, 0, 1.05),
        parent=base, mat_=M_BIKE_CHROME).rotation_euler = (math.radians(90), 0, 0)
    # Handles black
    for side in (-1, 1):
        cyl(f"{name}_hd{side}", r=0.03, depth=0.10, segs=8,
            loc=(0.5, side*0.25, 1.05), parent=base, mat_=M_BIKE_BLACK).rotation_euler = (math.radians(90), 0, 0)
    # Bell (signature on right handle)
    smooth_sphere(f"{name}_bell", r=0.04, loc=(0.5, 0.20, 1.10), parent=base, mat_=M_BIKE_CHROME)
    # FRONT BASKET (signature Dutch)
    beveled_cube(f"{name}_basket", (0.30, 0.30, 0.20), bevel_offset=0.04,
                 loc=(0.7, 0, 0.95), parent=base, mat_=M_TREE_TRUNK)
    # Basket grid
    for gi in range(4):
        beveled_cube(f"{name}_bg{gi}", (0.30, 0.04, 0.02), bevel_offset=0.005,
                     loc=(0.7, -0.13 + gi*0.10, 1.00), parent=base, mat_=M_TREE_TRUNK)
    # Tulips in basket
    for tui in range(5):
        tua = (tui / 5.0) * math.pi * 2
        smooth_sphere(f"{name}_btu{tui}", r=0.06,
                      loc=(0.7 + math.cos(tua)*0.10, math.sin(tua)*0.10, 1.10),
                      parent=base, mat_=random.choice(TULIP_COLORS))
    # Chain guard
    beveled_cube(f"{name}_chain", (0.50, 0.04, 0.20), bevel_offset=0.04,
                 loc=(-0.25, 0, 0.30), parent=base, mat_=M_BIKE_BLACK)
    # Mudguards over wheels (signature curved)
    for side in (-1, 1):
        for mi in range(5):
            ma = math.pi * mi / 4.0
            mx_p = side*0.6 + math.cos(ma) * 0.40
            mz_p = math.sin(ma) * 0.40 + 0.45
            cyl(f"{name}_mg{side}_{mi}", r=0.03, depth=0.20, segs=8,
                loc=(mx_p, 0, mz_p), parent=base, mat_=M_BIKE_BLACK).rotation_euler = (math.radians(90), 0, 0)
    return base

bikes = []
bike_pos = [(-15, -22, math.radians(0)), (10, -22, math.radians(20)),
             (-10, 2, math.radians(15)), (15, 2, math.radians(-25))]
for i, (bx, by, fac) in enumerate(bike_pos):
    b = make_bicycle(f"bike{i}", (bx, by, 0), scale=1.0, facing=fac)
    bikes.append(b)

# ============ 4 CANAL BOATS (signature long flat) ============
def make_canal_boat(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Long flat hull
    beveled_cube(f"{name}_hull", (6, 2, 0.4), bevel_offset=0.10, loc=(0, 0, 0.2),
                 parent=base, mat_=M_BOAT_WHITE)
    # Wood deck
    beveled_cube(f"{name}_deck", (5.8, 1.8, 0.10), bevel_offset=0.04, loc=(0, 0, 0.45),
                 parent=base, mat_=M_BOAT_WOOD)
    # Cabin
    beveled_cube(f"{name}_cabin", (3, 1.8, 1.5), bevel_offset=0.10, loc=(0, 0, 1.2),
                 parent=base, mat_=M_BOAT_WHITE)
    # Windows
    for wi in range(3):
        beveled_cube(f"{name}_w{wi}", (0.5, 1.9, 0.6), bevel_offset=0.06,
                     loc=(-1 + wi*1, 0, 1.5), parent=base, mat_=M_WINDOW_LIT_AM)
    # Roof
    beveled_cube(f"{name}_roof", (3.2, 2, 0.20), bevel_offset=0.06, loc=(0, 0, 2.0),
                 parent=base, mat_=M_HOUSE_DARK_RED)
    # FLAG signature Dutch tricolor
    cyl(f"{name}_fp", r=0.04, depth=2, segs=8, loc=(-2.8, 0, 2.5),
        parent=base, mat_=M_FRAME_DARK)
    # Flag fabric
    beveled_cube(f"{name}_fl_r", (0.8, 0.04, 0.20), bevel_offset=0.02, loc=(-2.4, 0, 3.4),
                 parent=base, mat_=M_FLAG_RED_NL)
    beveled_cube(f"{name}_fl_w", (0.8, 0.04, 0.20), bevel_offset=0.02, loc=(-2.4, 0, 3.2),
                 parent=base, mat_=M_FLAG_WHITE_NL)
    beveled_cube(f"{name}_fl_b", (0.8, 0.04, 0.20), bevel_offset=0.02, loc=(-2.4, 0, 3.0),
                 parent=base, mat_=M_FLAG_BLUE_NL)
    # Plants on deck signature
    for pi in range(4):
        smooth_sphere(f"{name}_pl{pi}", r=0.12,
                      loc=(1.5 + pi*0.30, 0, 0.5), parent=base, mat_=M_TREE_LEAF)
    # Tulips on deck
    for tui in range(6):
        tu_x = -2.5 + tui * 0.30
        smooth_sphere(f"{name}_tu{tui}", r=0.05, loc=(tu_x, -0.7, 0.55),
                      parent=base, mat_=random.choice(TULIP_COLORS))
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

boats = []
boat_pos = [(-30, -10, math.radians(5)), (-10, -10, math.radians(0)),
             (10, -10, math.radians(-5)), (30, -10, math.radians(10))]
for i, (bx, by, fac) in enumerate(boat_pos):
    b = make_canal_boat(f"boat{i}", (bx, by, 0.5), scale=1.0, facing=fac)
    boats.append(b)

# ============ WINDMILL (signature) ============
windmill_e = empty("windmill", loc=(-40, 30, 0))
# Stone base
for li in range(5):
    lz = li * 1.5
    lr = 3 - li * 0.15
    cyl(f"wm_b{li}", r=lr, depth=1.5, segs=18, loc=(0, 0, lz + 0.75),
        parent=windmill_e, mat_=M_WINDMILL_BODY if li % 2 == 0 else M_BRICK)
# Top cap (signature)
cyl("wm_cap", r=2.4, depth=1.5, segs=18, loc=(0, 0, 8.25), parent=windmill_e, mat_=M_WINDMILL_ROOF)
smooth_cone("wm_top", r1=2.0, r2=0.1, depth=2, segs=18, loc=(0, 0, 10),
            parent=windmill_e, mat_=M_WINDMILL_ROOF)
# Door
beveled_cube("wm_door", (1.0, 0.3, 2), bevel_offset=0.10, loc=(0, -3, 1),
             parent=windmill_e, mat_=M_FRAME_DARK)
# Windows
for wi in range(3):
    wz = 2.5 + wi * 2
    beveled_cube(f"wm_w{wi}", (0.6, 0.3, 0.8), bevel_offset=0.06, loc=(0, -2.5, wz),
                 parent=windmill_e, mat_=M_WINDOW_LIT_AM)
# BLADES SHAFT (signature 4 sails)
shaft_e = empty("wm_shaft", (0, -2.5, 8.5), parent=windmill_e)
cyl("wm_sh", r=0.15, depth=1, segs=12, loc=(0, 0, 0), parent=shaft_e,
    mat_=M_WINDMILL_BLADE).rotation_euler = (math.radians(90), 0, 0)
# 4 BLADES (signature lattice cross)
blades_e = empty("wm_blades", (0, -3, 8.5), parent=windmill_e)
for bi in range(4):
    ba = (bi / 4.0) * math.pi * 2
    blade_one_e = empty(f"wm_b{bi}_e", (0, 0, 0), parent=blades_e)
    blade_one_e.rotation_euler = (ba, 0, 0)
    # Main blade arm
    beveled_cube(f"wm_b{bi}_a", (0.06, 0.10, 5.5), bevel_offset=0.02, loc=(0, 0, 2.75),
                 parent=blade_one_e, mat_=M_WINDMILL_BLADE)
    # Lattice frame
    for li in range(8):
        cyl(f"wm_b{bi}_l{li}", r=0.025, depth=0.50, segs=6,
            loc=(0, 0, 1.0 + li*0.55), parent=blade_one_e,
            mat_=M_WINDMILL_BLADE).rotation_euler = (math.radians(90), 0, 0)
    # Sail fabric (signature white canvas)
    beveled_cube(f"wm_b{bi}_s", (0.05, 0.50, 4.0), bevel_offset=0.02, loc=(0, 0.25, 3),
                 parent=blade_one_e, mat_=M_WINDMILL_SAIL)

# ============ TULIP FIELDS (signature next to windmill) ============
# 30 tulip rows
for ri in range(8):
    for ci in range(15):
        tx_t = -55 + ci * 1.0
        ty_t = 30 + ri * 1.0
        if -45 < tx_t < -35: continue  # avoid windmill
        # Stem
        cyl(f"tu_st{ri}_{ci}", r=0.02, depth=0.45, segs=6, loc=(tx_t, ty_t, 0.22),
            mat_=M_TULIP_STEM)
        # Flower
        smooth_sphere(f"tu_fl{ri}_{ci}", r=0.10, segs=12, rings=10, loc=(tx_t, ty_t, 0.50),
                      mat_=TULIP_COLORS[(ri + ci) % len(TULIP_COLORS)], scale=(1, 1, 1.3))
        # Leaves
        for li in range(2):
            beveled_cube(f"tu_lv{ri}_{ci}_{li}", (0.10, 0.04, 0.20), bevel_offset=0.02,
                         loc=(tx_t + (li-0.5)*0.10, ty_t, 0.30), mat_=M_TULIP_LEAF).rotation_euler = (0, math.radians((li-0.5)*30), 0)

# ============ 6 PEOPLE on bicycles ============
def make_cyclist(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    coat_col = random.choice(COAT_NL)
    hair_col = random.choice(HAIR_NL)
    # Body
    smooth_cone(f"{name}_t", r1=0.30, r2=0.32, depth=0.7, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=coat_col)
    # Sitting pose - legs forward
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.09, depth=0.7, segs=10,
            loc=(side*0.12, 0, 0.85), parent=base, mat_=M_JEANS_BLUE).rotation_euler = (math.radians(45), 0, 0)
    # Shoes
    for side in (-1, 1):
        beveled_cube(f"{name}_sh{side}", (0.10, 0.20, 0.06), bevel_offset=0.02,
                     loc=(side*0.12, 0.25, 0.5), parent=base, mat_=M_BIKE_BLACK)
    # Arms forward (holding handles)
    for side in (-1, 1):
        sh = empty(f"{name}_sh{side}", (side*0.30, 0, 1.55), parent=base)
        sh.rotation_euler = (math.radians(-80), 0, math.radians(side*-5))
        cyl(f"{name}_uarm{side}", r=0.06, depth=0.35, segs=10,
            loc=(0, 0, -0.18), parent=sh, mat_=coat_col)
        cyl(f"{name}_fa{side}", r=0.05, depth=0.30, segs=10,
            loc=(0, 0, -0.48), parent=sh, mat_=M_SKIN_PALE_NL)
    # Head
    head_c_e = empty(f"{name}_he", (0, 0, 1.85), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_c_e, mat_=M_SKIN_PALE_NL)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_c_e, mat_=M_EYE_BLUE_NL)
    # Hair
    for hi in range(8):
        ha = (hi / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.06,
                      loc=(math.cos(ha)*0.15, math.sin(ha)*0.10, 0.10),
                      parent=head_c_e, mat_=hair_col)
    # Cheek pink cold
    for side in (-1, 1):
        smooth_sphere(f"{name}_ch{side}", r=0.05,
                      loc=(side*0.13, -0.16, -0.05), parent=head_c_e, mat_=M_CHEEK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_c_e}

cyclists = []
# Place 6 cyclists on bicycles (using bike positions)
cyclist_pos = [(-15, -22, math.radians(0)), (10, -22, math.radians(20)),
                (-10, 2, math.radians(15)), (15, 2, math.radians(-25)),
                (0, -22, math.radians(0)), (25, -22, math.radians(-10))]
for i, (cx, cy, fac) in enumerate(cyclist_pos):
    c = make_cyclist(f"cyclist{i}", (cx, cy, 0.5), scale=1.0, facing=fac)
    cyclists.append(c)

# ============ DOGS (signature street dogs) ============
def make_dog(name, loc, scale=0.6, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    dog_col = random.choice([M_DOG_BROWN, M_DOG_WHITE, M_DOG_BLACK])
    # Body
    smooth_sphere(f"{name}_b", r=0.30, segs=16, rings=12, loc=(0, 0, 0.40),
                  parent=base, mat_=dog_col, scale=(1.7, 0.9, 1))
    # 4 legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}_{y}", r=0.05, depth=0.35, segs=8,
                loc=(x*0.25, y*0.15, 0.20), parent=base, mat_=dog_col)
    # Head
    head_d = empty(f"{name}_he", (0.40, 0, 0.55), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=14, rings=10, loc=(0, 0, 0),
                  parent=head_d, mat_=dog_col, scale=(1.4, 0.9, 1))
    # Snout
    smooth_sphere(f"{name}_s", r=0.13, loc=(0.18, 0, -0.05), parent=head_d, mat_=dog_col,
                  scale=(1.3, 0.7, 0.7))
    # Nose
    smooth_sphere(f"{name}_n", r=0.04, loc=(0.30, 0, -0.02), parent=head_d, mat_=M_DOG_BLACK)
    # Floppy ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_e{side}", r=0.10,
                      loc=(0, side*0.18, 0.05), parent=head_d, mat_=dog_col, scale=(0.5, 1, 1.5))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(0.10, side*0.10, 0.04),
                      parent=head_d, mat_=M_EYE_DARK_NL)
    # Tail wagging
    cyl(f"{name}_tail", r=0.04, depth=0.35, segs=8, loc=(-0.40, 0, 0.50),
        parent=base, mat_=dog_col).rotation_euler = (math.radians(60), 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base}

dogs = []
dog_pos = [(-5, -25, math.radians(45)), (8, -25, math.radians(-30)),
            (-3, 3, math.radians(120))]
for i, (dx, dy, fac) in enumerate(dog_pos):
    d = make_dog(f"dog{i}", (dx, dy, 0), scale=0.6, facing=fac)
    dogs.append(d)

# ============ 4 SWANS in canal (signature) ============
def make_swan(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_b", r=0.50, segs=18, rings=14, loc=(0, 0, 0.20),
                  parent=base, mat_=M_SWAN_WHITE, scale=(1.5, 1, 0.85))
    # CURVED NECK (signature S-curve)
    neck_e = empty(f"{name}_n", (0.6, 0, 0.35), parent=base)
    for ni in range(6):
        nx_s = math.sin(ni * 0.6) * 0.10
        nz_s = math.cos(ni * 0.4) * 0.15 + ni * 0.10
        cyl(f"{name}_ns{ni}", r=0.08 - ni*0.005, depth=0.18, segs=10,
            loc=(nx_s, 0, nz_s), parent=neck_e, mat_=M_SWAN_WHITE)
    # Head
    head_s_e = empty(f"{name}_he", (0.2, 0, 0.95), parent=neck_e)
    smooth_sphere(f"{name}_h", r=0.12, segs=14, rings=10, loc=(0, 0, 0),
                  parent=head_s_e, mat_=M_SWAN_WHITE, scale=(1, 0.9, 1.0))
    # ORANGE BEAK (signature)
    smooth_cone(f"{name}_bk", r1=0.06, r2=0.005, depth=0.15, segs=10,
                loc=(0.10, 0, -0.02), parent=head_s_e,
                mat_=M_SWAN_BEAK).rotation_euler = (math.radians(-90), 0, 0)
    # Black knob at base of beak (signature)
    smooth_sphere(f"{name}_kb", r=0.05, loc=(0.04, 0, 0.05),
                  parent=head_s_e, mat_=M_HOUSE_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.02, loc=(0.06, side*0.07, 0.04),
                      parent=head_s_e, mat_=M_EYE_DARK_NL)
    # Tail
    smooth_sphere(f"{name}_tail", r=0.20, loc=(-0.55, 0, 0.30),
                  parent=base, mat_=M_SWAN_WHITE, scale=(0.8, 1, 0.8))
    # Wing folded
    for side in (-1, 1):
        smooth_sphere(f"{name}_w{side}", r=0.30, loc=(0, side*0.30, 0.30),
                      parent=base, mat_=M_SWAN_WHITE, scale=(1, 0.4, 0.7))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "neck": neck_e}

swans = []
swan_pos = [(-25, -8, math.radians(30)), (0, -10, math.radians(0)),
             (15, -12, math.radians(-30)), (-15, -12, math.radians(60))]
for i, (sx, sy, fac) in enumerate(swan_pos):
    s = make_swan(f"swan{i}", (sx, sy, 0.3), scale=1.0, facing=fac)
    swans.append(s)

# ============ TREES (signature linden) ============
for ti in range(6):
    ta = (ti / 6.0) * math.pi * 2
    tx_t = math.cos(ta) * 35 + random.uniform(-3, 3)
    ty_t = math.sin(ta) * 35 + random.uniform(-3, 3)
    if -10 < ty_t < 5 and -55 < tx_t < 55: continue
    t_e = empty(f"tree{ti}", (tx_t, ty_t, 0))
    cyl(f"tt{ti}", r=0.30, depth=4, segs=12, loc=(0, 0, 2), parent=t_e, mat_=M_TREE_TRUNK)
    # Foliage
    for fi in range(15):
        fa = random.uniform(0, math.pi*2)
        fz = random.uniform(3, 6)
        fr = random.uniform(0.5, 1.5)
        smooth_sphere(f"tf{ti}_{fi}", r=random.uniform(0.6, 1.0),
                      loc=(math.cos(fa)*fr, math.sin(fa)*fr, fz),
                      parent=t_e, mat_=M_TREE_LEAF)

# ============================================================
# ⭐ 600 TULIP PETALS + 400 SOAP BUBBLES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
tulip_petals_part = []
for i in range(600):
    px = random.uniform(-70, 70)
    py = random.uniform(-70, 70)
    pz = random.uniform(1, 18)
    p = smooth_sphere(f"tp{i}", r=random.uniform(0.06, 0.10), segs=8, rings=6,
                      loc=(px, py, pz), mat_=random.choice(TULIP_COLORS),
                      scale=(1.4, 0.7, 0.3))
    p["_phase"] = random.uniform(0, math.pi*2)
    p["_base_x"] = px; p["_base_y"] = py; p["_base_z"] = pz
    p["_amp_x"] = random.uniform(1.0, 2.5)
    p["_amp_y"] = random.uniform(1.0, 2.5)
    p["_speed"] = random.uniform(0.4, 1.0)
    p["_fall"] = random.uniform(1.0, 2.5)
    tulip_petals_part.append(p)

# 400 soap bubbles
bubbles = []
for i in range(400):
    px = random.uniform(-55, 55)
    py = random.uniform(-55, 55)
    pz = random.uniform(1, 15)
    b = smooth_sphere(f"bub{i}", r=random.uniform(0.10, 0.20), segs=10, rings=8,
                      loc=(px, py, pz), mat_=M_BUBBLE_AM)
    b["_phase"] = random.uniform(0, math.pi*2)
    b["_base_x"] = px; b["_base_y"] = py; b["_base_z"] = pz
    b["_amp_x"] = random.uniform(0.5, 1.5)
    b["_amp_y"] = random.uniform(0.5, 1.5)
    b["_speed"] = random.uniform(0.5, 1.2)
    b["_rise"] = random.uniform(1.0, 2.5)
    bubbles.append(b)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Clouds drift
for ci in range(20):
    cloud = bpy.data.objects.get(f"cloud{ci}")
    if cloud is None: continue
    phase = cloud["_phase"]
    bx_c = cloud.location.x; by_c = cloud.location.y
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        cloud.location.x = bx_c + math.sin(t * 0.3 + phase) * 2.0
        cloud.location.y = by_c + math.cos(t * 0.3 + phase) * 2.0
        cloud.keyframe_insert("location", frame=f)

# Boats sway
for b in boats:
    phase = b["_phase"]
    bz_b = b.location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        b.location.z = bz_b + math.sin(t * 1.0 + phase) * 0.10
        b.rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2),
                             math.cos(t * 1.0 + phase) * math.radians(2),
                             b.rotation_euler.z)
        b.keyframe_insert("location", frame=f)
        b.keyframe_insert("rotation_euler", frame=f)

# Windmill blades rotate
for f in range(1, total_frames + 1, 2):
    t = (f - 1) / fps
    blades_e.rotation_euler = (t * 1.5, 0, 0)
    blades_e.keyframe_insert("rotation_euler", frame=f)

# Cyclists head turn
for c in cyclists:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        c["he"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(10))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Dogs walk
for d in dogs:
    phase = d["root"]["_phase"]
    bx_d = d["root"].location.x; by_d = d["root"].location.y
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        d["root"].location.x = bx_d + math.sin(t * 1.5 + phase) * 0.8
        d["root"].location.y = by_d + math.cos(t * 1.5 + phase) * 0.5
        d["root"].keyframe_insert("location", frame=f)

# Swans glide + neck curve
for s in swans:
    phase = s["root"]["_phase"]
    bx_s = s["root"].location.x; by_s = s["root"].location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s["root"].location.x = bx_s + math.sin(t * 0.5 + phase) * 1.0
        s["root"].location.y = by_s + math.cos(t * 0.5 + phase) * 0.3
        s["root"].keyframe_insert("location", frame=f)
        s["neck"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(8), 0,
                                       math.cos(t * 0.8 + phase) * math.radians(15))
        s["neck"].keyframe_insert("rotation_euler", frame=f)

# 600 tulip petals fall
for p in tulip_petals_part:
    phase = p["_phase"]; speed = p["_speed"]; fall = p["_fall"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    ax, ay = p["_amp_x"], p["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.3)
        if z < 0.3: z = bz
        p.location = (x, y, max(0.2, z))
        p.rotation_euler = (t * 2.5 + phase, t * 2.0 + phase, t * 3.0 + phase)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# 400 bubbles rise (signature)
for b in bubbles:
    phase = b["_phase"]; speed = b["_speed"]; rise = b["_rise"]
    bx, by, bz = b["_base_x"], b["_base_y"], b["_base_z"]
    ax, ay = b["_amp_x"], b["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase) * 0.3
        y = by + ay * math.cos(t * speed * 0.9 + phase) * 0.3
        z = bz + (t * rise) % 6
        b.location = (x, y, z)
        sc_b = 1 + math.sin(t * 2.0 + phase) * 0.10
        b.scale = (sc_b, sc_b, sc_b)
        b.keyframe_insert("location", frame=f)
        b.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_amsterdam_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_amsterdam_canals_dutch_houses] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_amsterdam_canals_dutch_houses] 12 Dutch narrow tall houses (step/bell/neck gables) signature + 6 arched bridges + canals + 4 bicycles + 4 boats Dutch flag + windmill 4 sails + 30 tulip rows + 6 cyclists + 3 dogs + 4 swans + 600 tulip petals + 400 bubbles")
print("⭐ FIXES: 1 ground + 600 tulip petals + 400 soap bubbles (signature Amsterdam mandatory) ⭐")
