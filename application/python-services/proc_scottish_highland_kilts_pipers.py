"""
proc_scottish_highland_kilts_pipers.py — 243e procédural AuroraIA (108e qualité)
Scottish Highlands: castle + 6 pipers tartan + 4 highlanders + 2 highland cows + stag + 4 sheep + lochs + standing stones + thistles + 600 mist + 400 thistle petals
FIXES : 1 ground + 600 mist drift + 400 thistle petals (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB243)

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

# Stormy sky palette
M_SKY_GREY = mat("sky", (0.40, 0.42, 0.48, 1.0), 0.0, 0.7, emission=(0.38,0.40,0.46), emission_strength=1.2)
M_CLOUD_DARK = mat("cloud_d", (0.30, 0.32, 0.38, 1.0), 0.0, 0.8, emission=(0.28,0.30,0.36), emission_strength=0.8)
M_CLOUD_LIGHT = mat("cloud_l", (0.65, 0.65, 0.70, 1.0), 0.0, 0.7, emission=(0.60,0.60,0.65), emission_strength=1.0)

# Rainbow
M_RAINBOW_R = mat("rb_r", (1.0, 0.30, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.30,0.20), emission_strength=4.0, alpha=0.65)
M_RAINBOW_O = mat("rb_o", (1.0, 0.55, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.55,0.20), emission_strength=4.0, alpha=0.65)
M_RAINBOW_Y = mat("rb_y", (1.0, 0.95, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.95,0.30), emission_strength=4.0, alpha=0.65)
M_RAINBOW_G = mat("rb_g", (0.30, 0.95, 0.30, 1.0), 0.0, 0.20, emission=(0.30,0.95,0.30), emission_strength=4.0, alpha=0.65)
M_RAINBOW_B = mat("rb_b", (0.20, 0.45, 1.0, 1.0), 0.0, 0.20, emission=(0.20,0.45,1.0), emission_strength=4.0, alpha=0.65)
M_RAINBOW_V = mat("rb_v", (0.65, 0.25, 1.0, 1.0), 0.0, 0.20, emission=(0.65,0.25,1.0), emission_strength=4.0, alpha=0.65)

# Ground - heather moss highland
M_HEATHER = mat("heather", (0.45, 0.40, 0.35, 1.0), 0.0, 0.85, emission=(0.42,0.38,0.34), emission_strength=0.4)
M_MOSS_GREEN = mat("moss", (0.30, 0.45, 0.22, 1.0), 0.0, 0.85, emission=(0.28,0.42,0.22), emission_strength=0.4)
M_HEATHER_PURPLE = mat("heather_p", (0.55, 0.30, 0.45, 1.0), 0.0, 0.80, emission=(0.50,0.28,0.42), emission_strength=0.7)
M_BRACKEN = mat("bracken", (0.55, 0.40, 0.15, 1.0), 0.0, 0.80)
M_ROCK = mat("rock", (0.45, 0.45, 0.42, 1.0), 0.0, 0.85)

# Castle stone signature
M_CASTLE_STONE = mat("castle", (0.55, 0.52, 0.48, 1.0), 0.0, 0.85, emission=(0.50,0.48,0.45), emission_strength=0.3)
M_CASTLE_DARK = mat("castle_d", (0.38, 0.36, 0.34, 1.0), 0.0, 0.85)
M_CASTLE_MOSS = mat("castle_m", (0.42, 0.50, 0.30, 1.0), 0.0, 0.80)
M_CASTLE_WOOD = mat("c_wood", (0.38, 0.22, 0.10, 1.0), 0.0, 0.80)
M_WINDOW = mat("window", (0.18, 0.22, 0.35, 1.0), 0.1, 0.20, emission=(0.85,0.65,0.30), emission_strength=4.0)

# Tartan colors signature (red/green/blue royal stewart variant)
M_TARTAN_RED = mat("tt_r", (0.78, 0.18, 0.15, 1.0), 0.0, 0.60, emission=(0.72,0.18,0.15), emission_strength=0.4)
M_TARTAN_GREEN = mat("tt_g", (0.18, 0.42, 0.20, 1.0), 0.0, 0.65, emission=(0.18,0.40,0.20), emission_strength=0.3)
M_TARTAN_BLUE = mat("tt_b", (0.18, 0.30, 0.55, 1.0), 0.0, 0.65, emission=(0.18,0.30,0.55), emission_strength=0.3)
M_TARTAN_YELLOW = mat("tt_y", (0.85, 0.78, 0.30, 1.0), 0.0, 0.55, emission=(0.78,0.72,0.30), emission_strength=0.5)
M_TARTAN_BLACK = mat("tt_bk", (0.10, 0.10, 0.10, 1.0), 0.0, 0.75)
M_TARTAN_WHITE = mat("tt_w", (0.85, 0.82, 0.75, 1.0), 0.0, 0.70)
TARTAN_COLORS = [M_TARTAN_RED, M_TARTAN_GREEN, M_TARTAN_BLUE, M_TARTAN_YELLOW, M_TARTAN_BLACK, M_TARTAN_WHITE]

# Skin
M_SKIN_PALE = mat("skin", (0.92, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.62), emission_strength=0.4)
M_HAIR_RED = mat("h_r", (0.72, 0.30, 0.10, 1.0), 0.0, 0.60, emission=(0.65,0.28,0.10), emission_strength=0.4)
M_HAIR_GINGER = mat("h_gn", (0.85, 0.45, 0.20, 1.0), 0.0, 0.60, emission=(0.78,0.40,0.18), emission_strength=0.4)
M_HAIR_BROWN_S = mat("h_brs", (0.30, 0.18, 0.10, 1.0), 0.0, 0.60)
M_HAIR_BLOND_S = mat("h_bls", (0.82, 0.65, 0.30, 1.0), 0.0, 0.55)
HAIR_VARIANTS_S = [M_HAIR_RED, M_HAIR_GINGER, M_HAIR_BROWN_S, M_HAIR_BLOND_S]

# Bagpipes signature
M_BAG = mat("bag", (0.55, 0.18, 0.20, 1.0), 0.0, 0.55, emission=(0.50,0.18,0.20), emission_strength=0.4)
M_BAG_TARTAN = mat("bag_t", (0.45, 0.20, 0.25, 1.0), 0.0, 0.60)
M_PIPE_WOOD = mat("pipe_w", (0.20, 0.12, 0.08, 1.0), 0.0, 0.55, emission=(0.18,0.12,0.08), emission_strength=0.3)
M_PIPE_SILVER = mat("pipe_s", (0.85, 0.85, 0.85, 1.0), 0.85, 0.25, emission=(0.80,0.80,0.80), emission_strength=0.8)
M_PIPE_CHANTER = mat("pipe_c", (0.30, 0.18, 0.10, 1.0), 0.0, 0.50)

# Drum highland
M_DRUM_HL = mat("drum_hl", (0.85, 0.78, 0.55, 1.0), 0.0, 0.55, emission=(0.78,0.72,0.52), emission_strength=0.5)

# Highland cow signature (ginger fur + long horns)
M_COW_GINGER = mat("cow_g", (0.62, 0.32, 0.10, 1.0), 0.0, 0.85, emission=(0.58,0.30,0.10), emission_strength=0.3)
M_COW_DARK = mat("cow_d", (0.42, 0.22, 0.08, 1.0), 0.0, 0.85)
M_COW_HORN = mat("cow_h", (0.85, 0.80, 0.70, 1.0), 0.0, 0.40, emission=(0.78,0.75,0.65), emission_strength=0.3)
M_COW_NOSE = mat("cow_n", (0.30, 0.18, 0.12, 1.0), 0.0, 0.55)

# Stag royal signature
M_STAG_BROWN = mat("stag_b", (0.45, 0.25, 0.12, 1.0), 0.0, 0.70, emission=(0.42,0.25,0.12), emission_strength=0.4)
M_STAG_LIGHT = mat("stag_l", (0.85, 0.65, 0.40, 1.0), 0.0, 0.65)
M_ANTLER = mat("antler", (0.62, 0.42, 0.18, 1.0), 0.0, 0.55, emission=(0.58,0.40,0.18), emission_strength=0.4)

# Sheep
M_WOOL_WHITE = mat("wool", (0.90, 0.88, 0.82, 1.0), 0.0, 0.85, emission=(0.85,0.85,0.82), emission_strength=0.4)
M_SHEEP_FACE = mat("sh_f", (0.30, 0.28, 0.25, 1.0), 0.0, 0.55)

# Eye
M_EYE_DARK_S = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)
M_EYE_GLOW = mat("eye_gl", (0.30, 0.45, 0.20, 1.0), 0.0, 0.10, emission=(0.30,0.45,0.20), emission_strength=4.0)

# Loch
M_LOCH = mat("loch", (0.18, 0.30, 0.45, 1.0), 0.1, 0.20, emission=(0.16,0.28,0.42), emission_strength=1.0, alpha=0.78)
M_LOCH_DEEP = mat("loch_d", (0.12, 0.22, 0.35, 1.0), 0.1, 0.25, alpha=0.85)

# Saint Andrew flag
M_FLAG_BLUE_SA = mat("fl_sa", (0.12, 0.30, 0.62, 1.0), 0.0, 0.45, emission=(0.10,0.28,0.60), emission_strength=1.8)
M_FLAG_WHITE_S = mat("fl_ws", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.90,0.90,0.88), emission_strength=1.5)

# Claymore sword
M_SWORD_STEEL = mat("sw_st", (0.85, 0.85, 0.88, 1.0), 0.92, 0.18, emission=(0.80,0.80,0.85), emission_strength=1.2)
M_SWORD_GRIP = mat("sw_gr", (0.25, 0.15, 0.08, 1.0), 0.0, 0.75)
M_SWORD_GOLD = mat("sw_gd", (0.95, 0.78, 0.25, 1.0), 0.85, 0.25, emission=(0.92,0.75,0.25), emission_strength=1.5)

# Standing stone
M_STANDING = mat("standing", (0.40, 0.42, 0.45, 1.0), 0.0, 0.85)

# Thistle signature
M_THISTLE_PURPLE = mat("th_p", (0.62, 0.28, 0.78, 1.0), 0.0, 0.45, emission=(0.62,0.28,0.78), emission_strength=2.2)
M_THISTLE_GREEN = mat("th_g", (0.30, 0.50, 0.22, 1.0), 0.0, 0.60)
M_THISTLE_LIGHT = mat("th_l", (0.75, 0.45, 0.92, 1.0), 0.0, 0.40, emission=(0.75,0.45,0.92), emission_strength=2.5)

# Mist
M_MIST = mat("mist", (0.85, 0.88, 0.92, 1.0), 0.0, 0.50, emission=(0.82,0.85,0.92), emission_strength=2.5, alpha=0.30)

# ============ SKY (stormy clouds) ============
sky = smooth_sphere("sky", r=220, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY_GREY)
sky.scale = (1,1,0.55)

# Storm clouds
for ci in range(25):
    cax = random.uniform(-80, 80); cay = random.uniform(-80, 80)
    caz = random.uniform(25, 50)
    cloud_e = empty(f"cloud{ci}", (cax, cay, caz))
    cloud_color = M_CLOUD_DARK if ci % 2 == 0 else M_CLOUD_LIGHT
    for cli in range(random.randint(3, 6)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(2, 4), segs=14, rings=10,
                      loc=(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=cloud_color, scale=(1.2, 1.2, 0.6))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)

# ============ RAINBOW (signature Highland) ============
rainbow_e = empty("rainbow", (30, -20, 0))
RAINBOW_COLS = [M_RAINBOW_R, M_RAINBOW_O, M_RAINBOW_Y, M_RAINBOW_G, M_RAINBOW_B, M_RAINBOW_V]
for ri, rcol in enumerate(RAINBOW_COLS):
    arc_r = 30 + ri * 0.8
    for ai in range(40):
        aa = math.pi * ai / 40.0
        ax_r = math.cos(aa) * arc_r
        az_r = math.sin(aa) * arc_r * 0.7
        smooth_sphere(f"rb{ri}_{ai}", r=0.6, segs=10, rings=8,
                      loc=(ax_r, 0, az_r), parent=rainbow_e, mat_=rcol,
                      scale=(1, 1, 1))

# ============ ONE clean ground heather moss ============
ground = beveled_cube("ground", (180, 180, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_HEATHER)
# Organic moss bumps
for i in range(180):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 75)
    smooth_sphere(f"bump{i}", r=random.uniform(0.4, 1.0), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_MOSS_GREEN if i % 3 == 0 else M_HEATHER_PURPLE if i % 3 == 1 else M_BRACKEN,
                  scale=(1.5, 1.4, 0.20))
# Scattered rocks
for ri in range(40):
    rx = random.uniform(-60, 60); ry = random.uniform(-60, 60)
    smooth_sphere(f"rock{ri}", r=random.uniform(0.5, 1.5), segs=14, rings=10,
                  loc=(rx, ry, 0.25), mat_=M_ROCK, scale=(1.2, 1.1, 0.7))

# ============ CASTLE (signature medieval Highland) ============
castle_e = empty("castle", loc=(0, 35, 0))
# Foundation/base
beveled_cube("c_base", (16, 16, 1.5), bevel_offset=0.12, loc=(0, 0, 0.75),
             parent=castle_e, mat_=M_CASTLE_DARK)
# Main walls
beveled_cube("c_w_b", (14, 0.8, 8), bevel_offset=0.10, loc=(0, -7, 5.5),
             parent=castle_e, mat_=M_CASTLE_STONE)
beveled_cube("c_w_f", (14, 0.8, 8), bevel_offset=0.10, loc=(0, 7, 5.5),
             parent=castle_e, mat_=M_CASTLE_STONE)
beveled_cube("c_w_l", (0.8, 14, 8), bevel_offset=0.10, loc=(-7, 0, 5.5),
             parent=castle_e, mat_=M_CASTLE_STONE)
beveled_cube("c_w_r", (0.8, 14, 8), bevel_offset=0.10, loc=(7, 0, 5.5),
             parent=castle_e, mat_=M_CASTLE_STONE)

# Crenellations on walls (signature)
for wall_y, wall_y_mul in zip([7, -7], [1, -1]):
    for ci in range(11):
        cx_c = -6 + ci * 1.2
        beveled_cube(f"cren_yw{wall_y_mul}_{ci}", (0.9, 1.0, 0.7), bevel_offset=0.05,
                     loc=(cx_c, wall_y, 9.8), parent=castle_e, mat_=M_CASTLE_STONE)
for wall_x, wall_x_mul in zip([7, -7], [1, -1]):
    for ci in range(11):
        cy_c = -6 + ci * 1.2
        beveled_cube(f"cren_xw{wall_x_mul}_{ci}", (1.0, 0.9, 0.7), bevel_offset=0.05,
                     loc=(wall_x, cy_c, 9.8), parent=castle_e, mat_=M_CASTLE_STONE)

# 4 corner TOWERS (signature)
for tx in (-1, 1):
    for ty in (-1, 1):
        t_e = empty(f"tower_{tx}_{ty}", (tx*7, ty*7, 0), parent=castle_e)
        # Round tower body
        cyl(f"t_b_{tx}_{ty}", r=1.5, depth=14, segs=20, loc=(0, 0, 7),
            parent=t_e, mat_=M_CASTLE_STONE)
        # Top ring
        cyl(f"t_top_{tx}_{ty}", r=1.7, depth=0.4, segs=20, loc=(0, 0, 14),
            parent=t_e, mat_=M_CASTLE_DARK)
        # Crenellated top
        for ci in range(8):
            ca = (ci / 8.0) * math.pi * 2
            beveled_cube(f"t_cren_{tx}_{ty}_{ci}", (0.4, 0.4, 0.6), bevel_offset=0.04,
                         loc=(math.cos(ca)*1.5, math.sin(ca)*1.5, 14.5),
                         parent=t_e, mat_=M_CASTLE_STONE)
        # Conical roof
        smooth_cone(f"t_roof_{tx}_{ty}", r1=1.7, r2=0.1, depth=3.5, segs=20,
                    loc=(0, 0, 16.5), parent=t_e, mat_=M_CASTLE_DARK)
        # Spire
        cyl(f"t_spire_{tx}_{ty}", r=0.05, depth=1, segs=8, loc=(0, 0, 18.7),
            parent=t_e, mat_=M_CASTLE_DARK)
        # Window slits
        for wi in range(3):
            wz = 4 + wi * 3
            beveled_cube(f"t_w_{tx}_{ty}_{wi}", (0.5, 0.4, 0.15), bevel_offset=0.02,
                         loc=(0, -1.6, wz), parent=t_e, mat_=M_WINDOW)
# Center keep (taller)
cyl("keep", r=2.5, depth=20, segs=22, loc=(0, 0, 10), parent=castle_e, mat_=M_CASTLE_STONE)
# Keep crenellations
for ci in range(12):
    ca = (ci / 12.0) * math.pi * 2
    beveled_cube(f"keep_cren{ci}", (0.5, 0.5, 0.8), bevel_offset=0.05,
                 loc=(math.cos(ca)*2.5, math.sin(ca)*2.5, 20.2),
                 parent=castle_e, mat_=M_CASTLE_STONE)
# Keep flag pole + Saint Andrew flag (signature)
cyl("flag_pole", r=0.05, depth=4, segs=8, loc=(0, 0, 22), parent=castle_e, mat_=M_CASTLE_DARK)
flag_sa_e = empty("flag_sa", (0, 0, 23), parent=castle_e)
# Blue field
beveled_cube("fl_sa_b", (2.5, 0.05, 1.8), bevel_offset=0.04, loc=(1.25, 0, 0), parent=flag_sa_e, mat_=M_FLAG_BLUE_SA)
# White X cross (signature Saint Andrew)
for diag in (0, 1):
    diag_e = empty(f"sa_diag{diag}_e", (1.25, -0.05, 0), parent=flag_sa_e)
    diag_e.rotation_euler = (0, math.radians(35 if diag == 0 else -35), 0)
    beveled_cube(f"sa_d{diag}", (3.0, 0.04, 0.30), bevel_offset=0.02, loc=(0, 0, 0), parent=diag_e, mat_=M_FLAG_WHITE_S)

# Gate (drawbridge front)
beveled_cube("gate_top", (3, 0.9, 1), bevel_offset=0.05, loc=(0, -7, 4), parent=castle_e, mat_=M_CASTLE_WOOD)
beveled_cube("gate_body", (2.5, 0.6, 3), bevel_offset=0.05, loc=(0, -7, 2.5), parent=castle_e, mat_=M_CASTLE_WOOD)
# Iron bands
for bi in range(3):
    beveled_cube(f"g_band{bi}", (2.6, 0.65, 0.10), bevel_offset=0.02,
                 loc=(0, -7, 1.5 + bi*0.8), parent=castle_e, mat_=M_PIPE_SILVER)
# Windows on main walls
for wi in range(4):
    wx = -4.5 + wi * 3
    beveled_cube(f"c_win{wi}", (0.5, 0.85, 0.8), bevel_offset=0.04,
                 loc=(wx, -7, 6.5), parent=castle_e, mat_=M_WINDOW)
# Moss on castle stones
for mi in range(20):
    mx_c = random.uniform(-7, 7); my_c = random.choice([-7, 7])
    smooth_sphere(f"c_moss{mi}", r=random.uniform(0.20, 0.40),
                  loc=(mx_c, my_c, random.uniform(0.5, 8)),
                  parent=castle_e, mat_=M_CASTLE_MOSS, scale=(1, 0.3, 1))

# ============ 6 PIPERS (signature kilts tartan + bagpipes) ============
def make_piper(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    tartan_main = random.choice([M_TARTAN_RED, M_TARTAN_BLUE, M_TARTAN_GREEN])
    hair = random.choice(HAIR_VARIANTS_S)

    # Kilt (signature pleated tartan)
    smooth_cone(f"{name}_kilt", r1=0.42*scale, r2=0.35*scale, depth=0.8*scale, segs=18,
                loc=(0, 0, 0.7*scale), parent=base, mat_=tartan_main)
    # Tartan stripes (cross pattern)
    for ks in range(8):
        ka = (ks / 8.0) * math.pi * 2
        beveled_cube(f"{name}_ks{ks}", (0.03*scale, 0.10*scale, 0.7*scale), bevel_offset=0.005,
                     loc=(math.cos(ka)*0.38*scale, math.sin(ka)*0.38*scale, 0.7*scale),
                     parent=base, mat_=M_TARTAN_BLACK)
    # Belt
    cyl(f"{name}_belt", r=0.35*scale, depth=0.08*scale, segs=16, loc=(0, 0, 1.10*scale),
        parent=base, mat_=M_TARTAN_BLACK)
    # Sporran (signature pouch)
    smooth_sphere(f"{name}_sporran", r=0.10*scale, loc=(0, -0.35*scale, 0.90*scale),
                  parent=base, mat_=M_COW_DARK, scale=(1.4, 0.5, 1.3))
    # Sporran tassels
    for ts in range(3):
        cyl(f"{name}_tas{ts}", r=0.015*scale, depth=0.12*scale, segs=6,
            loc=((ts-1)*0.06*scale, -0.40*scale, 0.78*scale), parent=base, mat_=M_COW_GINGER)

    # White shirt
    smooth_cone(f"{name}_shirt", r1=0.30*scale, r2=0.32*scale, depth=0.55*scale, segs=14,
                loc=(0, 0, 1.40*scale), parent=base, mat_=M_FLAG_WHITE_S)
    # Vest tartan
    smooth_cone(f"{name}_vest", r1=0.32*scale, r2=0.34*scale, depth=0.40*scale, segs=14,
                loc=(0, 0, 1.45*scale), parent=base, mat_=tartan_main)

    # Knee socks (signature tartan)
    for side in (-1, 1):
        # Lower leg
        cyl(f"{name}_sock{side}", r=0.10*scale, depth=0.45*scale, segs=10,
            loc=(side*0.13*scale, 0, 0.22*scale), parent=base, mat_=M_TARTAN_WHITE)
        # Sock pattern
        for so in range(3):
            cyl(f"{name}_sps{side}_{so}", r=0.11*scale, depth=0.04*scale, segs=12,
                loc=(side*0.13*scale, 0, 0.05*scale + so*0.13*scale), parent=base, mat_=M_TARTAN_BLACK)
        # Top tassel signature
        cyl(f"{name}_sk{side}", r=0.04*scale, depth=0.08*scale, segs=8,
            loc=(side*0.13*scale, 0.10*scale, 0.45*scale), parent=base, mat_=M_TARTAN_RED)
        # Shoe
        beveled_cube(f"{name}_sh{side}", (0.10*scale, 0.20*scale, 0.05*scale), bevel_offset=0.01,
                     loc=(side*0.13*scale, 0, 0), parent=base, mat_=M_TARTAN_BLACK)

    # Arms (holding bagpipe)
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_shr{side_idx}", (side*0.30*scale, 0, 1.65*scale), parent=base)
        if side == -1:
            sh.rotation_euler = (math.radians(-90), 0, math.radians(20))
        else:
            sh.rotation_euler = (math.radians(-100), 0, math.radians(-15))
        cyl(f"{name}_uarm{side_idx}", r=0.06*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=M_FLAG_WHITE_S)
        cyl(f"{name}_fa{side_idx}", r=0.05*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_PALE)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_PALE)
    # Hair beard (signature Scottish)
    if random.random() > 0.4:
        for bi in range(8):
            ba = (bi / 8.0) * math.pi - math.pi/2
            smooth_sphere(f"{name}_bd{bi}", r=0.04*scale,
                          loc=(math.sin(ba)*0.12*scale, -0.15*scale, -0.12*scale),
                          parent=head_e, mat_=hair)
    # Hair top + tufts
    for hi in range(6):
        ha = (hi / 6.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.05*scale,
                      loc=(math.cos(ha)*0.12*scale, math.sin(ha)*0.10*scale, 0.10*scale),
                      parent=head_e, mat_=hair)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.03*scale), parent=head_e, mat_=M_EYE_DARK_S)
    # GLENGARRY/Balmoral BONNET (signature)
    bonnet_e = empty(f"{name}_bn", (0, 0, 0.18*scale), parent=head_e)
    # Bonnet body felt
    cyl(f"{name}_bn_b", r=0.20*scale, depth=0.10*scale, segs=16, loc=(0, 0, 0),
        parent=bonnet_e, mat_=M_TARTAN_BLACK)
    smooth_sphere(f"{name}_bn_t", r=0.20*scale, loc=(0, 0, 0.05*scale),
                  parent=bonnet_e, mat_=M_TARTAN_BLACK, scale=(1, 1, 0.5))
    # Red pom (signature)
    smooth_sphere(f"{name}_pom", r=0.06*scale, loc=(0, 0, 0.15*scale),
                  parent=bonnet_e, mat_=M_TARTAN_RED)
    # Tartan band
    cyl(f"{name}_bn_band", r=0.21*scale, depth=0.04*scale, segs=16, loc=(0, 0, -0.02*scale),
        parent=bonnet_e, mat_=M_TARTAN_RED)
    # Feather/cap badge
    smooth_sphere(f"{name}_bn_bd", r=0.04*scale, loc=(0.18*scale, -0.05*scale, 0),
                  parent=bonnet_e, mat_=M_SWORD_GOLD)

    # BAGPIPE (signature)
    bp_e = empty(f"{name}_bp", (0.25*scale, -0.30*scale, 1.50*scale), parent=base)
    # BAG (signature tartan covered)
    smooth_sphere(f"{name}_bag", r=0.30*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=bp_e, mat_=M_BAG_TARTAN, scale=(1, 0.85, 1.3))
    # Drone pipes 3 (signature)
    for dpi in range(3):
        dp_y = -0.10 + dpi * 0.10
        # Drone pipe
        cyl(f"{name}_dp{dpi}", r=0.025*scale, depth=0.7*scale, segs=8,
            loc=(0.05*scale*dpi, dp_y*scale, 0.50*scale), parent=bp_e, mat_=M_PIPE_WOOD)
        # Tasseled top
        smooth_sphere(f"{name}_dp_t{dpi}", r=0.05*scale,
                      loc=(0.05*scale*dpi, dp_y*scale, 0.90*scale), parent=bp_e, mat_=M_PIPE_SILVER)
    # Chanter (signature)
    chanter_e = empty(f"{name}_ch", (0.10*scale, 0.20*scale, -0.20*scale), parent=bp_e)
    chanter_e.rotation_euler = (math.radians(20), 0, 0)
    cyl(f"{name}_ch_b", r=0.025*scale, depth=0.50*scale, segs=8, loc=(0, 0, -0.25*scale),
        parent=chanter_e, mat_=M_PIPE_CHANTER)
    # Blowpipe
    cyl(f"{name}_blow", r=0.015*scale, depth=0.35*scale, segs=8, loc=(-0.10*scale, -0.25*scale, 0.05*scale),
        parent=bp_e, mat_=M_PIPE_WOOD).rotation_euler = (math.radians(40), 0, math.radians(-20))

    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "bag": bp_e, "bp": bp_e}

pipers = []
piper_pos = [(-8, 0, math.radians(180)), (-6, -2, math.radians(180)),
             (-4, 0, math.radians(180)), (4, 0, math.radians(180)),
             (6, -2, math.radians(180)), (8, 0, math.radians(180))]
for i, (px, py, fac) in enumerate(piper_pos):
    p = make_piper(f"piper{i}", (px, py, 0), scale=1.0, facing=fac)
    pipers.append(p)

# Highland drummer (1 - signature)
def make_drummer(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    tartan_main = random.choice([M_TARTAN_RED, M_TARTAN_BLUE, M_TARTAN_GREEN])
    # Kilt
    smooth_cone(f"{name}_kilt", r1=0.42*scale, r2=0.35*scale, depth=0.8*scale, segs=18,
                loc=(0, 0, 0.7*scale), parent=base, mat_=tartan_main)
    # Shirt
    smooth_cone(f"{name}_shirt", r1=0.30*scale, r2=0.32*scale, depth=0.55*scale, segs=14,
                loc=(0, 0, 1.40*scale), parent=base, mat_=M_FLAG_WHITE_S)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_PALE)
    # Bonnet
    cyl(f"{name}_bn", r=0.20*scale, depth=0.10*scale, segs=16, loc=(0, 0, 0.18*scale),
        parent=head_e, mat_=M_TARTAN_BLACK)
    smooth_sphere(f"{name}_bn_pom", r=0.06*scale, loc=(0, 0, 0.30*scale), parent=head_e, mat_=M_TARTAN_RED)
    # Drum (signature highland snare)
    drum_e = empty(f"{name}_drum", (0.30*scale, -0.30*scale, 1.20*scale), parent=base)
    cyl(f"{name}_d_body", r=0.30*scale, depth=0.30*scale, segs=20, loc=(0, 0, 0),
        parent=drum_e, mat_=M_DRUM_HL).rotation_euler = (math.radians(90), 0, 0)
    # Tartan rim
    cyl(f"{name}_d_rim1", r=0.32*scale, depth=0.06*scale, segs=22, loc=(0, 0.17*scale, 0),
        parent=drum_e, mat_=tartan_main).rotation_euler = (math.radians(90), 0, 0)
    cyl(f"{name}_d_rim2", r=0.32*scale, depth=0.06*scale, segs=22, loc=(0, -0.17*scale, 0),
        parent=drum_e, mat_=tartan_main).rotation_euler = (math.radians(90), 0, 0)
    # Sticks held above
    for side in (-1, 1):
        cyl(f"{name}_stick{side}", r=0.015*scale, depth=0.30*scale, segs=6,
            loc=(side*0.10*scale, -0.10*scale, 0.20*scale), parent=drum_e, mat_=M_PIPE_WOOD).rotation_euler = (math.radians(side*30), 0, 0)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "drum": drum_e, "he": head_e}

drummer = make_drummer("drummer", (0, 2, 0), scale=1.0, facing=math.radians(180))

# ============ 4 HIGHLANDERS with claymore swords ============
def make_highlander(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    tartan_main = random.choice([M_TARTAN_RED, M_TARTAN_BLUE, M_TARTAN_GREEN])
    hair = random.choice(HAIR_VARIANTS_S)
    # Kilt
    smooth_cone(f"{name}_kilt", r1=0.42*scale, r2=0.35*scale, depth=0.8*scale, segs=18,
                loc=(0, 0, 0.7*scale), parent=base, mat_=tartan_main)
    # Belt
    cyl(f"{name}_belt", r=0.35*scale, depth=0.08*scale, segs=16, loc=(0, 0, 1.10*scale),
        parent=base, mat_=M_TARTAN_BLACK)
    # Bare chest with sash (signature)
    smooth_cone(f"{name}_chest", r1=0.32*scale, r2=0.36*scale, depth=0.55*scale, segs=14,
                loc=(0, 0, 1.40*scale), parent=base, mat_=M_SKIN_PALE)
    # Tartan sash diagonal
    sash_e = empty(f"{name}_sa", (0, -0.10*scale, 1.55*scale), parent=base)
    sash_e.rotation_euler = (0, math.radians(20), math.radians(30))
    beveled_cube(f"{name}_sash", (0.6*scale, 0.06*scale, 0.20*scale), bevel_offset=0.03,
                 loc=(0, 0, 0), parent=sash_e, mat_=tartan_main)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_PALE)
    # Beard
    for bi in range(8):
        ba = (bi / 8.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_bd{bi}", r=0.04*scale,
                      loc=(math.sin(ba)*0.12*scale, -0.15*scale, -0.12*scale),
                      parent=head_e, mat_=hair)
    # Hair
    for hi in range(8):
        ha = (hi / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.06*scale,
                      loc=(math.cos(ha)*0.15*scale, math.sin(ha)*0.10*scale, 0.15*scale),
                      parent=head_e, mat_=hair)
    # CLAYMORE SWORD raised (signature large two-handed)
    # Sword e at right hand
    sw_e = empty(f"{name}_sword", (0.30*scale, -0.15*scale, 1.50*scale), parent=base)
    sw_e.rotation_euler = (math.radians(-20), 0, math.radians(15))
    # Long blade
    beveled_cube(f"{name}_sw_b", (0.04*scale, 0.10*scale, 1.8*scale), bevel_offset=0.005,
                 loc=(0, 0, 1.0*scale), parent=sw_e, mat_=M_SWORD_STEEL)
    # Point
    smooth_cone(f"{name}_sw_p", r1=0.05*scale, r2=0.002*scale, depth=0.30*scale, segs=8,
                loc=(0, 0, 2.05*scale), parent=sw_e, mat_=M_SWORD_STEEL)
    # Crossguard
    cyl(f"{name}_sw_cg", r=0.025*scale, depth=0.40*scale, segs=8, loc=(0, 0, 0.10*scale),
        parent=sw_e, mat_=M_SWORD_GOLD).rotation_euler = (0, math.radians(90), 0)
    # Grip
    cyl(f"{name}_sw_gr", r=0.025*scale, depth=0.25*scale, segs=8, loc=(0, 0, -0.10*scale),
        parent=sw_e, mat_=M_SWORD_GRIP)
    # Pommel
    smooth_sphere(f"{name}_sw_pm", r=0.05*scale, loc=(0, 0, -0.25*scale), parent=sw_e, mat_=M_SWORD_GOLD)
    # Arms hold sword
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, -0.10*scale, 1.70*scale), parent=base)
        sh.rotation_euler = (math.radians(-30), 0, math.radians(side*-10))
        cyl(f"{name}_uarm{side_idx}", r=0.07*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=M_SKIN_PALE)
        cyl(f"{name}_fa{side_idx}", r=0.06*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_PALE)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_calf{side}", r=0.10*scale, depth=0.50*scale, segs=10,
            loc=(side*0.13*scale, 0, 0.25*scale), parent=base, mat_=M_SKIN_PALE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "sword": sw_e, "he": head_e}

highlanders = []
hl_pos = [(-14, -5, math.radians(45)), (14, -5, math.radians(-45)),
           (-14, 10, math.radians(120)), (14, 10, math.radians(-120))]
for i, (hx, hy, fac) in enumerate(hl_pos):
    h = make_highlander(f"highlander{i}", (hx, hy, 0), scale=1.0, facing=fac)
    highlanders.append(h)

# ============ 2 HIGHLAND COWS (signature ginger fur + horns) ============
def make_highland_cow(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.85*scale, segs=20, rings=14, loc=(0, 0, 1.1*scale),
                  parent=base, mat_=M_COW_GINGER, scale=(1.7, 1.0, 1.0))
    # Long shaggy fur tufts (signature)
    for ft in range(50):
        fa = random.uniform(0, math.pi*2)
        fe = random.uniform(0, math.pi)
        fx_c = math.sin(fe) * math.cos(fa) * 1.0*scale
        fy_c = math.sin(fe) * math.sin(fa) * 0.6*scale
        fz_c = math.cos(fe) * 0.7*scale + 1.1*scale
        smooth_sphere(f"{name}_fur{ft}", r=random.uniform(0.10, 0.16)*scale,
                      loc=(fx_c, fy_c, fz_c), parent=base,
                      mat_=M_COW_GINGER if ft % 2 == 0 else M_COW_DARK)
    # 4 legs
    for x in (-1, 1):
        for y in (-1, 1):
            l_e = empty(f"{name}_l{x}{y}_e", (x*0.55*scale, y*0.45*scale, 1.1*scale), parent=base)
            cyl(f"{name}_l{x}{y}", r=0.15*scale, depth=1.1*scale, segs=10, loc=(0, 0, -0.55*scale),
                parent=l_e, mat_=M_COW_DARK)
    # Head
    head_e = empty(f"{name}_he", (1.4*scale, 0, 1.4*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.45*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_COW_GINGER, scale=(1.3, 0.9, 1.0))
    # SHAGGY FACE FUR (signature covering eyes)
    for ff in range(20):
        ffa = (ff / 20.0) * math.pi - math.pi/2
        smooth_sphere(f"{name}_ff{ff}", r=0.12*scale,
                      loc=(0.15*scale, math.sin(ffa)*0.35*scale, 0.20*scale),
                      parent=head_e, mat_=M_COW_GINGER, scale=(0.8, 1, 1.5))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.25*scale, loc=(0.35*scale, 0, -0.10*scale),
                  parent=head_e, mat_=M_COW_DARK, scale=(1.2, 0.9, 0.8))
    # Nose
    smooth_sphere(f"{name}_nose", r=0.06*scale, loc=(0.55*scale, 0, -0.05*scale),
                  parent=head_e, mat_=M_COW_NOSE)
    # LONG HORNS (signature wide curved)
    for side in (-1, 1):
        h_e = empty(f"{name}_h{side}_e", (-0.10*scale, side*0.30*scale, 0.10*scale), parent=head_e)
        h_e.rotation_euler = (math.radians(side*-30), 0, math.radians(side*70))
        # Horn segments curved
        for hi in range(6):
            hi_l = 0.10*scale
            cyl(f"{name}_h{side}_{hi}", r=0.06*scale - hi*0.008, depth=hi_l, segs=10,
                loc=(math.sin(hi*0.4)*0.05*scale, 0, hi*0.10*scale), parent=h_e, mat_=M_COW_HORN)
        # Pointed tip
        smooth_cone(f"{name}_h{side}_tip", r1=0.03*scale, r2=0.005*scale, depth=0.15*scale, segs=8,
                    loc=(0, 0, 0.65*scale), parent=h_e, mat_=M_COW_HORN)
    # Tail
    cyl(f"{name}_tail", r=0.05*scale, depth=0.8*scale, segs=8, loc=(-1.3*scale, 0, 1.1*scale),
        parent=base, mat_=M_COW_GINGER)
    # Tail tuft
    smooth_sphere(f"{name}_tt", r=0.10*scale, loc=(-1.3*scale, 0, 0.6*scale),
                  parent=base, mat_=M_COW_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

highland_cows = []
cow_pos = [(-22, -15, math.radians(60)), (22, -15, math.radians(-60))]
for i, (cx, cy, fac) in enumerate(cow_pos):
    c = make_highland_cow(f"hcow{i}", (cx, cy, 0), scale=1.0, facing=fac)
    highland_cows.append(c)

# ============ ROYAL STAG (signature antlers) ============
stag_e = empty("stag", loc=(20, 5, 0))
stag_e.rotation_euler = (0, 0, math.radians(-30))
# Body
smooth_sphere("stag_body", r=0.65, segs=20, rings=14, loc=(0, 0, 1.3),
              parent=stag_e, mat_=M_STAG_BROWN, scale=(1.7, 1.0, 1.0))
# Belly
smooth_sphere("stag_belly", r=0.55, loc=(0, 0, 1.10),
              parent=stag_e, mat_=M_STAG_LIGHT, scale=(1.5, 0.9, 0.5))
# 4 long legs
for x in (-1, 1):
    for y in (-1, 1):
        l_e = empty(f"stag_l{x}{y}_e", (x*0.55, y*0.30, 1.3), parent=stag_e)
        cyl(f"stag_l{x}{y}", r=0.06, depth=1.3, segs=10, loc=(0, 0, -0.65),
            parent=l_e, mat_=M_STAG_BROWN)
# Neck up
neck_e = empty("stag_neck", (1.0, 0, 1.6), parent=stag_e)
neck_e.rotation_euler = (0, math.radians(-30), 0)
cyl("stag_neck_b", r=0.18, depth=0.8, segs=14, loc=(0, 0, 0.4),
    parent=neck_e, mat_=M_STAG_BROWN)
# Head
head_e = empty("stag_he", (0, 0, 0.85), parent=neck_e)
smooth_sphere("stag_head", r=0.22, segs=18, rings=14, loc=(0.10, 0, 0),
              parent=head_e, mat_=M_STAG_BROWN, scale=(1.5, 0.9, 1.0))
# Snout
smooth_sphere("stag_snout", r=0.18, loc=(0.32, 0, -0.05),
              parent=head_e, mat_=M_STAG_BROWN, scale=(1.2, 0.7, 0.7))
smooth_sphere("stag_nose", r=0.05, loc=(0.45, 0, -0.02), parent=head_e, mat_=M_EYE_DARK_S)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"stag_eye{side}", r=0.04, loc=(0.10, side*0.15, 0.05),
                  parent=head_e, mat_=M_EYE_DARK_S)
# Ears
for side in (-1, 1):
    smooth_sphere(f"stag_ear{side}", r=0.10, loc=(-0.05, side*0.18, 0.15),
                  parent=head_e, mat_=M_STAG_BROWN, scale=(0.5, 1.2, 1.5))

# MAJESTIC ANTLERS (signature huge royal stag)
for side in (-1, 1):
    ant_e = empty(f"stag_a{side}_e", (-0.10, side*0.10, 0.30), parent=head_e)
    ant_e.rotation_euler = (0, 0, math.radians(side*30))
    # Main beam
    cyl(f"stag_a{side}_main", r=0.05, depth=0.8, segs=10, loc=(0, side*0.10, 0.4),
        parent=ant_e, mat_=M_ANTLER).rotation_euler = (math.radians(side*-20), 0, 0)
    # Branch tines (signature multiple points)
    for bri in range(5):
        b_z = 0.20 + bri * 0.15
        bra_e = empty(f"stag_a{side}_br{bri}_e", (0, side*(0.10 + bri*0.05), b_z), parent=ant_e)
        bra_e.rotation_euler = (math.radians(side*-30), math.radians(side*20 + bri*5), math.radians(side*40))
        cyl(f"stag_a{side}_br{bri}", r=0.03, depth=0.30, segs=8, loc=(0, 0, 0.15),
            parent=bra_e, mat_=M_ANTLER)
        # Pointed tip
        smooth_cone(f"stag_a{side}_br{bri}_tip", r1=0.02, r2=0.005, depth=0.10, segs=6,
                    loc=(0, 0, 0.35), parent=bra_e, mat_=M_ANTLER)

# Tail
cyl("stag_tail", r=0.04, depth=0.3, segs=8, loc=(-1.0, 0, 1.4),
    parent=stag_e, mat_=M_STAG_LIGHT)

# ============ 4 SHEEP ============
def make_sheep(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Wool body (puffy signature)
    smooth_sphere(f"{name}_wool", r=0.45*scale, segs=20, rings=14, loc=(0, 0, 0.7*scale),
                  parent=base, mat_=M_WOOL_WHITE, scale=(1.6, 1.0, 1.1))
    # Wool tufts
    for wt in range(20):
        wa = random.uniform(0, math.pi*2)
        we = random.uniform(0, math.pi)
        wx_s = math.sin(we)*math.cos(wa)*0.5*scale
        wy_s = math.sin(we)*math.sin(wa)*0.5*scale
        wz_s = math.cos(we)*0.5*scale + 0.7*scale
        smooth_sphere(f"{name}_wt{wt}", r=0.13*scale,
                      loc=(wx_s, wy_s, wz_s), parent=base, mat_=M_WOOL_WHITE)
    # 4 thin legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}{y}", r=0.04*scale, depth=0.5*scale, segs=8,
                loc=(x*0.30*scale, y*0.20*scale, 0.25*scale), parent=base, mat_=M_SHEEP_FACE)
    # Head dark face
    head_e = empty(f"{name}_he", (0.65*scale, 0, 0.85*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=16, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SHEEP_FACE, scale=(1.3, 0.9, 1.0))
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.06*scale,
                      loc=(-0.05*scale, side*0.18*scale, 0.05*scale), parent=head_e,
                      mat_=M_SHEEP_FACE, scale=(0.6, 1.2, 0.8))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.02*scale,
                      loc=(0.15*scale, side*0.10*scale, 0.05*scale), parent=head_e, mat_=M_EYE_DARK_S)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

sheep = []
sheep_pos = [(-25, 15, math.radians(0)), (-22, 18, math.radians(45)),
              (28, 20, math.radians(180)), (32, 16, math.radians(135))]
for i, (sx, sy, fac) in enumerate(sheep_pos):
    sh = make_sheep(f"sheep{i}", (sx, sy, 0), scale=1.0, facing=fac)
    sheep.append(sh)

# ============ LOCHS (serpentine signature) ============
loch_pts = []
for ri in range(35):
    loch_y = -45 + ri * 2.5
    loch_x = math.sin(ri * 0.25) * 10 - 35
    loch_pts.append((loch_x, loch_y, 0))

for ri in range(len(loch_pts) - 1):
    lx1, ly1, lz1 = loch_pts[ri]
    lx2, ly2, lz2 = loch_pts[ri+1]
    lmidx = (lx1 + lx2) / 2; lmidy = (ly1 + ly2) / 2
    llen = math.sqrt((lx2-lx1)**2 + (ly2-ly1)**2) + 0.5
    lang = math.atan2(ly2-ly1, lx2-lx1)
    seg = beveled_cube(f"loch{ri}", (llen, 5, 0.18), bevel_offset=0.04,
                       loc=(lmidx, lmidy, 0.18), mat_=M_LOCH)
    seg.rotation_euler = (0, 0, lang)
    seg2 = beveled_cube(f"loch_d{ri}", (llen*0.95, 4, 0.12), bevel_offset=0.03,
                        loc=(lmidx, lmidy, 0.22), mat_=M_LOCH_DEEP)
    seg2.rotation_euler = (0, 0, lang)

# ============ 4 STANDING STONES (signature) ============
standing_pos = [(-35, 25, 0), (-40, 30, 0), (-32, 30, 0), (-37, 35, 0)]
for si, (sx, sy, sz) in enumerate(standing_pos):
    s_e = empty(f"standing{si}", (sx, sy, sz))
    # Tall irregular stone
    for li in range(4):
        lz = li * 1.5
        beveled_cube(f"st{si}_{li}", (1.0 + random.uniform(-0.1, 0.1),
                                        0.8 + random.uniform(-0.1, 0.1),
                                        1.5), bevel_offset=0.06,
                     loc=(random.uniform(-0.1, 0.1), random.uniform(-0.1, 0.1), lz + 0.75),
                     parent=s_e, mat_=M_STANDING)
    # Moss/lichen
    for mi in range(5):
        smooth_sphere(f"st{si}_m{mi}", r=0.12,
                      loc=(random.uniform(-0.5, 0.5), random.uniform(-0.4, 0.4),
                           random.uniform(0.5, 5)),
                      parent=s_e, mat_=M_CASTLE_MOSS, scale=(1.5, 0.3, 1))

# ============ THISTLES (signature Scotland) ============
for ti in range(25):
    tx = random.uniform(-60, 60); ty = random.uniform(-60, 60)
    t_e = empty(f"thistle{ti}", (tx, ty, 0))
    # Stem
    cyl(f"th{ti}_st", r=0.025, depth=0.8, segs=8, loc=(0, 0, 0.4),
        parent=t_e, mat_=M_THISTLE_GREEN)
    # Spiky bulb
    smooth_sphere(f"th{ti}_bulb", r=0.15, segs=16, rings=12, loc=(0, 0, 0.8),
                  parent=t_e, mat_=M_THISTLE_GREEN, scale=(1, 1, 1.2))
    # Purple spikes top
    for sp in range(15):
        spa = (sp / 15.0) * math.pi * 2
        smooth_cone(f"th{ti}_sp{sp}", r1=0.03, r2=0.005, depth=0.20, segs=6,
                    loc=(math.cos(spa)*0.08, math.sin(spa)*0.08, 1.0 + random.uniform(-0.05, 0.05)),
                    parent=t_e, mat_=M_THISTLE_PURPLE)
    # Top tuft
    smooth_sphere(f"th{ti}_top", r=0.18, loc=(0, 0, 1.10),
                  parent=t_e, mat_=M_THISTLE_LIGHT, scale=(1, 1, 0.7))

# ============================================================
# ⭐ 600 MIST + 400 THISTLE PETALS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
mist_particles = []
for i in range(600):
    px = random.uniform(-70, 70)
    py = random.uniform(-70, 70)
    pz = random.uniform(0.3, 8)
    m_obj = smooth_sphere(f"mist{i}", r=random.uniform(0.50, 1.20), segs=10, rings=8,
                          loc=(px, py, pz), mat_=M_MIST, scale=(1.5, 1.3, 0.8))
    m_obj["_phase"] = random.uniform(0, math.pi*2)
    m_obj["_base_x"] = px; m_obj["_base_y"] = py; m_obj["_base_z"] = pz
    m_obj["_amp_x"] = random.uniform(1.0, 2.5)
    m_obj["_amp_y"] = random.uniform(1.0, 2.5)
    m_obj["_amp_z"] = random.uniform(0.3, 0.7)
    m_obj["_speed"] = random.uniform(0.15, 0.4)
    mist_particles.append(m_obj)

# 400 thistle petals
thistle_petals = []
for i in range(400):
    px = random.uniform(-50, 50)
    py = random.uniform(-50, 50)
    pz = random.uniform(1, 12)
    pcol = M_THISTLE_PURPLE if i % 2 == 0 else M_THISTLE_LIGHT
    p_obj = smooth_sphere(f"thp{i}", r=random.uniform(0.06, 0.10), segs=8, rings=6,
                          loc=(px, py, pz), mat_=pcol, scale=(1.4, 1, 0.4))
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_amp_x"] = random.uniform(1.5, 3.0)
    p_obj["_amp_y"] = random.uniform(1.5, 3.0)
    p_obj["_amp_z"] = random.uniform(0.5, 1.2)
    p_obj["_speed"] = random.uniform(0.5, 1.2)
    p_obj["_fall"] = random.uniform(1.0, 2.0)
    thistle_petals.append(p_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Clouds drift
for ci in range(25):
    cloud = bpy.data.objects.get(f"cloud{ci}")
    if cloud is None: continue
    phase = cloud["_phase"]
    bx_c = cloud.location.x; by_c = cloud.location.y; bz_c = cloud.location.z
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        cloud.location.x = bx_c + math.sin(t * 0.3 + phase) * 2.0
        cloud.location.y = by_c + math.cos(t * 0.3 + phase) * 2.0
        cloud.keyframe_insert("location", frame=f)

# Pipers play (bag pulse + head bob)
for p in pipers:
    phase = p["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Bag pulse breath
        s_b = 1 + math.sin(t * 1.5 + phase) * 0.10
        p["bag"].scale = (s_b, s_b, s_b)
        p["bag"].keyframe_insert("scale", frame=f)
        # Head bob
        p["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(4),
                                   math.cos(t * 1.5 + phase) * math.radians(3), 0)
        p["he"].keyframe_insert("rotation_euler", frame=f)
        # Body sway
        p["root"].rotation_euler = (0, math.sin(t * 0.8 + phase) * math.radians(2),
                                     p["root"].rotation_euler.z)
        p["root"].keyframe_insert("rotation_euler", frame=f)

# Drummer drum vibrate + head bob
phase = drummer["root"]["_phase"]
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    drummer["root"].rotation_euler = (math.sin(t * 4.0 + phase) * math.radians(4), 0,
                                       drummer["root"].rotation_euler.z)
    drummer["root"].keyframe_insert("rotation_euler", frame=f)
    s_d = 1 + math.sin(t * 8.0 + phase) * 0.06
    drummer["drum"].scale = (s_d, s_d, 1)
    drummer["drum"].keyframe_insert("scale", frame=f)

# Highlanders sword brandish
for h in highlanders:
    phase = h["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        h["sword"].rotation_euler = (math.radians(-20) + math.sin(t * 1.5 + phase) * math.radians(10),
                                       math.cos(t * 1.5 + phase) * math.radians(15),
                                       math.radians(15))
        h["sword"].keyframe_insert("rotation_euler", frame=f)
        h["he"].rotation_euler = (0, 0, math.sin(t * 1.2 + phase) * math.radians(10))
        h["he"].keyframe_insert("rotation_euler", frame=f)

# Highland cows graze + sway
for hc in highland_cows:
    phase = hc["root"]["_phase"]
    bx_hc = hc["root"].location.x; by_hc = hc["root"].location.y
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        hc["root"].location.x = bx_hc + math.sin(t * 0.4 + phase) * 0.5
        hc["root"].location.y = by_hc + math.cos(t * 0.4 + phase) * 0.3
        hc["root"].keyframe_insert("location", frame=f)
        # Head down grazing
        hc["he"].rotation_euler = (math.radians(-20) + math.sin(t * 0.8 + phase) * math.radians(20),
                                    0, math.cos(t * 0.8 + phase) * math.radians(10))
        hc["he"].keyframe_insert("rotation_euler", frame=f)

# Stag head proud turn + tail
phase_st = random.uniform(0, math.pi*2)
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    head_e.rotation_euler = (math.sin(t * 0.6 + phase_st) * math.radians(8),
                              0, math.cos(t * 0.6 + phase_st) * math.radians(15))
    head_e.keyframe_insert("rotation_euler", frame=f)

# Sheep nibble grass
for s in sheep:
    phase = s["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s["he"].rotation_euler = (math.radians(-30) + math.sin(t * 1.5 + phase) * math.radians(15), 0, 0)
        s["he"].keyframe_insert("rotation_euler", frame=f)
        s_b = 1 + math.sin(t * 0.5 + phase) * 0.03
        s["root"].scale = (s_b, s_b, s_b)
        s["root"].keyframe_insert("scale", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_sa_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(8))
    flag_sa_e.keyframe_insert("rotation_euler", frame=f)

# 600 mist drift
for m in mist_particles:
    phase = m["_phase"]; speed = m["_speed"]
    bx, by, bz = m["_base_x"], m["_base_y"], m["_base_z"]
    ax, ay, az = m["_amp_x"], m["_amp_y"], m["_amp_z"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        m.location = (x, y, max(0.2, z))
        sc = 1 + math.sin(t * 1.0 + phase) * 0.15
        m.scale = (sc * 1.5, sc * 1.3, sc * 0.8)
        m.keyframe_insert("location", frame=f)
        m.keyframe_insert("scale", frame=f)

# 400 thistle petals tumble
for p in thistle_petals:
    phase = p["_phase"]; speed = p["_speed"]; fall = p["_fall"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    ax, ay, az = p["_amp_x"], p["_amp_y"], p["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.3)
        if z < 0.3: z = bz
        p.location = (x, y, max(0.2, z))
        p.rotation_euler = (t * 3.0 + phase, t * 2.5 + phase, t * 4.0 + phase)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_highland_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_scottish_highland_kilts_pipers] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_scottish_highland_kilts_pipers] castle + 6 pipers kilts + drummer + 4 highlanders + 2 highland cows + royal stag + 4 sheep + lochs + 4 standing stones + 25 thistles + rainbow + 600 mist + 400 thistle petals")
print("⭐ FIXES: 1 ground + 600 mist + 400 thistle petals (signature Highlands mandatory) ⭐")
