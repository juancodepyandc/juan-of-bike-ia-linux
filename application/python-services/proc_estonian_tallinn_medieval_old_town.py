"""
proc_estonian_tallinn_medieval_old_town.py — 289e procédural AuroraIA (154e qualité)
Estonia Tallinn medieval old town: 8 Hanseatic houses red roofs + Pikk Hermann tower + Alexander Nevsky onion domes + walls + 4 merchants + Estonia flag + 600 snow + 400 gold stars
FIXES : 1 ground Toompea cobblestone + signature snow + stars
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB289)

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

# Sky winter Baltic
M_SKY = mat("sky", (0.55, 0.65, 0.78, 1.0), 0.0, 0.7, emission=(0.55,0.65,0.78), emission_strength=1.5)
M_SKY_LOW = mat("sky_l", (0.85, 0.88, 0.92, 1.0), 0.0, 0.7, emission=(0.85,0.88,0.92), emission_strength=1.3)
M_SUN = mat("sun", (0.95, 0.90, 0.78, 1.0), 0.0, 0.1, emission=(0.92,0.88,0.78), emission_strength=10.0)

# Cobblestone Toompea
M_COBBLE_GRAY = mat("cg", (0.55, 0.55, 0.55, 1.0), 0.0, 0.85, emission=(0.52,0.52,0.52), emission_strength=0.3)
M_COBBLE_DARK = mat("cgd", (0.32, 0.32, 0.32, 1.0), 0.0, 0.92)
M_COBBLE_BROWN = mat("cb", (0.42, 0.38, 0.32, 1.0), 0.0, 0.85)

# Snow
M_SNOW = mat("sn", (0.95, 0.95, 0.95, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.92), emission_strength=0.6)
M_SNOW_DIRT = mat("snd", (0.78, 0.78, 0.78, 1.0), 0.0, 0.65)

# Hanseatic house colors (signature pastel)
M_HOUSE_YELLOW = mat("hy", (1.0, 0.85, 0.55, 1.0), 0.0, 0.65, emission=(0.95,0.82,0.55), emission_strength=0.6)
M_HOUSE_PINK = mat("hp", (1.0, 0.75, 0.78, 1.0), 0.0, 0.65, emission=(0.95,0.72,0.75), emission_strength=0.6)
M_HOUSE_BLUE = mat("hb", (0.62, 0.78, 0.85, 1.0), 0.0, 0.65, emission=(0.62,0.75,0.82), emission_strength=0.6)
M_HOUSE_GREEN = mat("hg", (0.62, 0.85, 0.62, 1.0), 0.0, 0.65, emission=(0.62,0.82,0.62), emission_strength=0.6)
M_HOUSE_ORANGE = mat("ho", (1.0, 0.78, 0.55, 1.0), 0.0, 0.65, emission=(0.95,0.75,0.55), emission_strength=0.7)
M_HOUSE_PEACH = mat("hpe", (1.0, 0.82, 0.65, 1.0), 0.0, 0.65, emission=(0.95,0.78,0.62), emission_strength=0.6)
M_HOUSE_WHITE = mat("hw", (0.92, 0.92, 0.88, 1.0), 0.0, 0.65, emission=(0.88,0.88,0.85), emission_strength=0.5)
HOUSE_COLORS = [M_HOUSE_YELLOW, M_HOUSE_PINK, M_HOUSE_BLUE, M_HOUSE_GREEN, M_HOUSE_ORANGE, M_HOUSE_PEACH, M_HOUSE_WHITE]

# Roof (signature red terracotta)
M_ROOF_RED = mat("rr", (0.65, 0.30, 0.25, 1.0), 0.0, 0.75, emission=(0.62,0.30,0.25), emission_strength=0.5)
M_ROOF_DARK = mat("rrd", (0.42, 0.20, 0.15, 1.0), 0.0, 0.85)

# Castle wall stone
M_CASTLE_GRAY = mat("cag", (0.55, 0.55, 0.50, 1.0), 0.0, 0.85, emission=(0.52,0.52,0.50), emission_strength=0.3)
M_CASTLE_DARK = mat("cad", (0.32, 0.32, 0.32, 1.0), 0.0, 0.92)
M_CASTLE_RED_BRICK = mat("crb", (0.55, 0.30, 0.20, 1.0), 0.0, 0.85, emission=(0.52,0.30,0.20), emission_strength=0.4)

# Window
M_WINDOW_GLOW = mat("wg", (1.0, 0.85, 0.42, 1.0), 0.0, 0.10, emission=(0.95,0.82,0.42), emission_strength=4.5)
M_WINDOW_DARK = mat("wd", (0.18, 0.15, 0.13, 1.0), 0.0, 0.75)
M_DOOR_WOOD = mat("dw", (0.32, 0.18, 0.10, 1.0), 0.0, 0.75)
M_TIMBER = mat("tm", (0.42, 0.28, 0.18, 1.0), 0.0, 0.85)

# Onion dome colors (signature Alexander Nevsky)
M_DOME_BLACK = mat("db", (0.10, 0.10, 0.12, 1.0), 0.2, 0.45)
M_DOME_GOLD = mat("dgo", (0.95, 0.78, 0.20, 1.0), 0.9, 0.10, emission=(0.92,0.75,0.20), emission_strength=1.8)
M_CROSS_GOLD = mat("crg", (1.0, 0.85, 0.20, 1.0), 0.9, 0.10, emission=(0.95,0.82,0.20), emission_strength=2.2)

# Merchant clothing
M_SKIN = mat("sk", (0.92, 0.78, 0.58, 1.0), 0.0, 0.55, emission=(0.88,0.78,0.58), emission_strength=0.3)
M_HAIR_BROWN = mat("hbr", (0.32, 0.18, 0.08, 1.0), 0.0, 0.85)
M_HAIR_BLOND = mat("hbl", (0.78, 0.65, 0.30, 1.0), 0.0, 0.85)

# Wool clothing (signature merchant)
M_WOOL_GREEN = mat("wgr", (0.30, 0.55, 0.32, 1.0), 0.0, 0.85, emission=(0.30,0.52,0.30), emission_strength=0.4)
M_WOOL_BURGUNDY = mat("wbg", (0.55, 0.18, 0.20, 1.0), 0.0, 0.85, emission=(0.52,0.18,0.20), emission_strength=0.5)
M_WOOL_BROWN = mat("wbr", (0.42, 0.28, 0.18, 1.0), 0.0, 0.85)
M_WOOL_NAVY = mat("wnv", (0.18, 0.22, 0.42, 1.0), 0.0, 0.85, emission=(0.18,0.22,0.42), emission_strength=0.4)
WOOL_COLORS = [M_WOOL_GREEN, M_WOOL_BURGUNDY, M_WOOL_BROWN, M_WOOL_NAVY]
M_FUR_TRIM = mat("ft", (0.55, 0.42, 0.28, 1.0), 0.0, 0.90)
M_LEATHER = mat("le", (0.32, 0.18, 0.10, 1.0), 0.2, 0.55)

# Estonia flag
M_FLAG_BLUE = mat("fb", (0.18, 0.42, 0.78, 1.0), 0.0, 0.45, emission=(0.18,0.42,0.75), emission_strength=1.0)
M_FLAG_BLACK = mat("fbk", (0.10, 0.10, 0.12, 1.0), 0.0, 0.45)
M_FLAG_WHITE = mat("fw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.45, emission=(0.92,0.92,0.90), emission_strength=0.8)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# Snow particles (signature 6-point)
M_FLAKE_WHITE = mat("flw", (0.98, 0.98, 0.95, 1.0), 0.0, 0.20, emission=(0.95,0.95,0.92), emission_strength=2.0)
M_FLAKE_BLUE = mat("flb", (0.85, 0.92, 0.98, 1.0), 0.0, 0.20, emission=(0.82,0.92,0.98), emission_strength=1.8)

# Gold stars
M_STAR_GOLD = mat("sg", (1.0, 0.85, 0.20, 1.0), 0.95, 0.05, emission=(0.95,0.82,0.20), emission_strength=3.0)
M_STAR_BRIGHT = mat("sb_st", (1.0, 0.92, 0.45, 1.0), 0.95, 0.05, emission=(0.95,0.88,0.45), emission_strength=3.5)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-50, 110, 25), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-50, 110, 25), mat_=M_SUN)

# ============ ONE clean Toompea cobblestone ground (snow-dusted) ============
ground = beveled_cube("ground", (200, 200, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_COBBLE_BROWN)
# Cobblestones
for cbi in range(40):
    for cbj in range(40):
        bx = -30 + cbi * 1.5
        by = -30 + cbj * 1.5
        if -28 < bx < 28 and -28 < by < 28 and random.random() > 0.30:
            cyl(f"cb{cbi}_{cbj}", r=0.45, depth=0.08, segs=10,
                loc=(bx, by, 0.10),
                mat_=M_COBBLE_GRAY if (cbi + cbj) % 2 else M_COBBLE_DARK)
# Snow patches (signature winter)
for si in range(80):
    a = random.uniform(0, math.pi*2); rad = random.uniform(8, 100)
    smooth_sphere(f"sn{si}", r=random.uniform(0.5, 1.2), segs=10, rings=6,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.15),
                  mat_=M_SNOW if si % 2 else M_SNOW_DIRT, scale=(1.4, 1.3, 0.10))

# ============ 8 HANSEATIC HOUSES (signature pastel + red roofs) ============
def make_hanseatic_house(name, loc, width, height, depth, color):
    base = empty(name, loc)
    # Main building (signature tall narrow)
    beveled_cube(f"{name}_w", (width, depth, height), bevel_offset=0.10,
                 loc=(0, 0, height/2), parent=base, mat_=color)
    # Stepped gable (signature Hanseatic top)
    n_steps = 4
    for si_g in range(n_steps):
        step_w = width - si_g * 0.4
        step_h = 0.4
        # Top each step
        beveled_cube(f"{name}_g{si_g}", (step_w, depth + 0.1, step_h), bevel_offset=0.05,
                     loc=(0, 0, height + si_g*0.4), parent=base, mat_=color)
    # STEEP RED TILED ROOF (signature)
    roof_e = empty(f"{name}_re", (0, 0, height + n_steps*0.4 + 0.5), parent=base)
    smooth_cone(f"{name}_r", r1=width*0.5 + 0.3, r2=0.1, depth=2.0, segs=4, loc=(0, 0, 1.0),
                parent=roof_e, mat_=M_ROOF_RED).rotation_euler = (0, 0, math.radians(45))
    # Roof tiles (signature horizontal lines)
    for ti in range(8):
        ti_t = ti / 8.0
        tw = (width + 0.4) * (1 - ti_t)
        beveled_cube(f"{name}_rt{ti}", (tw, depth + 0.4, 0.10), bevel_offset=0.02,
                     loc=(0, 0, 0.2 + ti*0.20), parent=roof_e, mat_=M_ROOF_DARK)
    # Roof snow cap (signature winter)
    smooth_cone(f"{name}_rs", r1=width*0.45, r2=0.05, depth=1.5, segs=4, loc=(0, 0, 1.2),
                parent=roof_e, mat_=M_SNOW).rotation_euler = (0, 0, math.radians(45))
    # WINDOWS (signature small with glow)
    win_rows = 3; win_cols = max(2, int(width / 2))
    for r in range(win_rows):
        for c in range(win_cols):
            wx = -width/2 + (c + 0.5) * (width / win_cols)
            wz = (r + 1) * (height / (win_rows + 1))
            # Window frame
            beveled_cube(f"{name}_wf{r}_{c}", (0.6, 0.06, 0.8), bevel_offset=0.03,
                         loc=(wx, -depth/2 - 0.05, wz), parent=base, mat_=M_TIMBER)
            # Glass (glow signature)
            beveled_cube(f"{name}_wg{r}_{c}", (0.50, 0.02, 0.70), bevel_offset=0.02,
                         loc=(wx, -depth/2 - 0.08, wz), parent=base, mat_=M_WINDOW_GLOW)
            # Window cross
            beveled_cube(f"{name}_wxv{r}_{c}", (0.04, 0.04, 0.70), bevel_offset=0.01,
                         loc=(wx, -depth/2 - 0.09, wz), parent=base, mat_=M_TIMBER)
            beveled_cube(f"{name}_wxh{r}_{c}", (0.50, 0.04, 0.04), bevel_offset=0.01,
                         loc=(wx, -depth/2 - 0.09, wz), parent=base, mat_=M_TIMBER)
    # Door (signature wooden with timber frame)
    beveled_cube(f"{name}_d", (0.8, 0.10, 1.8), bevel_offset=0.05,
                 loc=(0, -depth/2 - 0.05, 0.9), parent=base, mat_=M_DOOR_WOOD)
    # Door frame timber
    beveled_cube(f"{name}_df_l", (0.10, 0.06, 1.8), bevel_offset=0.02,
                 loc=(-0.50, -depth/2 - 0.08, 0.9), parent=base, mat_=M_TIMBER)
    beveled_cube(f"{name}_df_r", (0.10, 0.06, 1.8), bevel_offset=0.02,
                 loc=(0.50, -depth/2 - 0.08, 0.9), parent=base, mat_=M_TIMBER)
    beveled_cube(f"{name}_df_t", (1.0, 0.06, 0.10), bevel_offset=0.02,
                 loc=(0, -depth/2 - 0.08, 1.85), parent=base, mat_=M_TIMBER)
    # Signature timber framing (decorative crossbeams)
    for ti_b in range(3):
        beveled_cube(f"{name}_tb{ti_b}", (width + 0.05, 0.05, 0.15), bevel_offset=0.02,
                     loc=(0, -depth/2 - 0.05, 1.5 + ti_b*1.8), parent=base, mat_=M_TIMBER)
    return base

# Houses arranged in a row (signature Hanseatic street)
house_pos = [
    (-20, -8, 4, 7, 2.5), (-13, -8, 4, 8, 2.5), (-6, -8, 4, 6.5, 2.5),
    (1, -8, 4, 9, 2.5), (8, -8, 4, 7.5, 2.5), (15, -8, 4, 8.5, 2.5),
    (-15, 5, 4, 7, 2.5), (15, 5, 4, 8, 2.5)
]
for i, (hx, hy, hw, hh, hd) in enumerate(house_pos):
    fac_h = make_hanseatic_house(f"hh{i}", (hx, hy, 0), hw, hh, hd, random.choice(HOUSE_COLORS))
    if hy > 0:
        fac_h.rotation_euler = (0, 0, math.radians(180))

# ============ PIKK HERMANN TOWER (signature tall medieval tower) ============
hermann_e = empty("hermann", (-35, -10, 0))
# Tall square tower
beveled_cube("ph_b", (4, 4, 30), bevel_offset=0.12, loc=(0, 0, 15),
             parent=hermann_e, mat_=M_CASTLE_GRAY)
# Stone block lines
for bi in range(12):
    bz = 1 + bi * 2.5
    beveled_cube(f"ph_bl{bi}", (4.05, 0.05, 0.30), bevel_offset=0.02,
                 loc=(0, -2.05, bz), parent=hermann_e, mat_=M_CASTLE_DARK)
# Crenellations top
for ci in range(8):
    ca = (ci / 8.0) * math.pi * 2 + math.pi/8
    beveled_cube(f"ph_cr{ci}", (0.5, 0.5, 1.5), bevel_offset=0.06,
                 loc=(math.cos(ca)*2.0, math.sin(ca)*2.0, 30.75),
                 parent=hermann_e, mat_=M_CASTLE_GRAY)
# Arrow slits
for asi in range(6):
    asz = 8 + asi * 3
    beveled_cube(f"ph_as{asi}", (0.08, 4.1, 1.0), bevel_offset=0.005,
                 loc=(0, 0, asz), parent=hermann_e, mat_=M_CASTLE_DARK)
# Estonia flag on top (signature)
cyl("ph_fp", r=0.10, depth=8, segs=10, loc=(0, 0, 35), parent=hermann_e, mat_=M_LEATHER)
flag_main_e = empty("ph_fl", (1, 0, 36), parent=hermann_e)
# Estonia flag
beveled_cube("ph_fl_b", (0.04, 2, 0.85), bevel_offset=0.04, loc=(0, 0, 0.5),
             parent=flag_main_e, mat_=M_FLAG_BLUE)
beveled_cube("ph_fl_bk", (0.04, 2, 0.85), bevel_offset=0.04, loc=(0, 0, -0.35),
             parent=flag_main_e, mat_=M_FLAG_BLACK)
beveled_cube("ph_fl_w", (0.04, 2, 0.85), bevel_offset=0.04, loc=(0, 0, -1.20),
             parent=flag_main_e, mat_=M_FLAG_WHITE)
# Snow cap on tower
smooth_sphere("ph_sn", r=2.5, segs=14, rings=10, loc=(0, 0, 31.2), parent=hermann_e, mat_=M_SNOW, scale=(1.2, 1.2, 0.4))

# ============ ALEXANDER NEVSKY CATHEDRAL (signature 5 onion domes) ============
nevsky_e = empty("nevsky", (30, 30, 0))
# Main building
beveled_cube("nv_b", (8, 8, 8), bevel_offset=0.15, loc=(0, 0, 4),
             parent=nevsky_e, mat_=M_CASTLE_RED_BRICK)
# Brick pattern lines
for bi in range(8):
    beveled_cube(f"nv_br{bi}", (8.05, 0.05, 0.30), bevel_offset=0.02,
                 loc=(0, -4.05, 0.5 + bi*1.0), parent=nevsky_e, mat_=M_CASTLE_DARK)
# 5 ONION DOMES (signature)
# Central tallest
dome_central_e = empty("nv_dc", (0, 0, 12), parent=nevsky_e)
cyl("nv_dc_drum", r=1.5, depth=2.5, segs=18, loc=(0, 0, 0), parent=dome_central_e, mat_=M_CASTLE_GRAY)
# Onion bulb (signature curved)
for di in range(8):
    ti = di / 7.0
    # Tapered curve
    if ti < 0.4:
        r_d = 2.5 * (1 + math.sin(ti * math.pi * 1.5) * 0.3)
    else:
        r_d = 2.5 * (1 - (ti - 0.4) / 0.6 * 0.95)
    smooth_sphere(f"nv_dc_d{di}", r=r_d, segs=18, rings=12,
                  loc=(0, 0, 1.5 + ti*4), parent=dome_central_e,
                  mat_=M_DOME_BLACK, scale=(1, 1, 0.7))
# Gold cross top
cyl("nv_dc_c", r=0.05, depth=1.5, segs=8, loc=(0, 0, 6.5),
    parent=dome_central_e, mat_=M_CROSS_GOLD)
beveled_cube("nv_dc_cv", (0.50, 0.05, 0.06), bevel_offset=0.01, loc=(0, 0, 6.8),
             parent=dome_central_e, mat_=M_CROSS_GOLD)
# Cross base sphere
smooth_sphere("nv_dc_cb", r=0.20, loc=(0, 0, 5.5),
              parent=dome_central_e, mat_=M_DOME_GOLD)
# 4 corner domes (smaller)
for ci_d, (cx_d, cy_d) in enumerate([(-2.5, -2.5), (2.5, -2.5), (-2.5, 2.5), (2.5, 2.5)]):
    dome_e = empty(f"nv_d{ci_d}_e", (cx_d, cy_d, 9), parent=nevsky_e)
    cyl(f"nv_d{ci_d}_drum", r=1.0, depth=1.8, segs=14, loc=(0, 0, 0),
        parent=dome_e, mat_=M_CASTLE_GRAY)
    # Smaller onion
    for di in range(6):
        ti = di / 5.0
        if ti < 0.4:
            r_d = 1.5 * (1 + math.sin(ti * math.pi * 1.5) * 0.3)
        else:
            r_d = 1.5 * (1 - (ti - 0.4) / 0.6 * 0.95)
        smooth_sphere(f"nv_d{ci_d}_o{di}", r=r_d, segs=14, rings=10,
                      loc=(0, 0, 1.2 + ti*2.5), parent=dome_e,
                      mat_=M_DOME_BLACK, scale=(1, 1, 0.7))
    # Cross
    cyl(f"nv_d{ci_d}_c", r=0.04, depth=1.0, segs=6, loc=(0, 0, 4.5),
        parent=dome_e, mat_=M_CROSS_GOLD)
    beveled_cube(f"nv_d{ci_d}_cv", (0.35, 0.04, 0.05), bevel_offset=0.01,
                 loc=(0, 0, 4.8), parent=dome_e, mat_=M_CROSS_GOLD)
    smooth_sphere(f"nv_d{ci_d}_cb", r=0.15, loc=(0, 0, 3.8),
                  parent=dome_e, mat_=M_DOME_GOLD)
# Entrance arches
for ai in range(3):
    aa = (ai - 1) * math.radians(30)
    beveled_cube(f"nv_a{ai}", (1.2, 0.30, 2.5), bevel_offset=0.06,
                 loc=(math.cos(math.pi/2 + aa)*3.95, -4.05, 1.25),
                 parent=nevsky_e, mat_=M_DOOR_WOOD)

# ============ MEDIEVAL WALLS + TOWERS (signature) ============
wall_e = empty("walls", (0, 0, 0))
# Outer walls (4 sides forming square around old town)
wall_radius = 40
for wi in range(4):
    wa = wi * math.pi / 2
    if wi % 2 == 0:
        beveled_cube(f"ww{wi}", (60, 2, 5), bevel_offset=0.10,
                     loc=(0, math.sin(wa) * wall_radius, 2.5), parent=wall_e, mat_=M_CASTLE_GRAY)
    else:
        beveled_cube(f"ww{wi}", (2, 60, 5), bevel_offset=0.10,
                     loc=(math.cos(wa) * wall_radius, 0, 2.5), parent=wall_e, mat_=M_CASTLE_GRAY)
# Crenellations on walls
for wi in range(60):
    wx = -wall_radius + wi * (wall_radius * 2 / 60)
    beveled_cube(f"wcs{wi}", (0.5, 2.2, 1.0), bevel_offset=0.04,
                 loc=(wx, -wall_radius, 5.5), parent=wall_e, mat_=M_CASTLE_DARK)
    beveled_cube(f"wcn{wi}", (0.5, 2.2, 1.0), bevel_offset=0.04,
                 loc=(wx, wall_radius, 5.5), parent=wall_e, mat_=M_CASTLE_DARK)
for wi in range(60):
    wy = -wall_radius + wi * (wall_radius * 2 / 60)
    beveled_cube(f"wcw{wi}", (2.2, 0.5, 1.0), bevel_offset=0.04,
                 loc=(-wall_radius, wy, 5.5), parent=wall_e, mat_=M_CASTLE_DARK)
    beveled_cube(f"wce{wi}", (2.2, 0.5, 1.0), bevel_offset=0.04,
                 loc=(wall_radius, wy, 5.5), parent=wall_e, mat_=M_CASTLE_DARK)
# Corner towers (signature round)
for ci, (cx, cy) in enumerate([(-wall_radius, -wall_radius), (wall_radius, -wall_radius),
                                  (-wall_radius, wall_radius), (wall_radius, wall_radius)]):
    tower_e = empty(f"wt{ci}", (cx, cy, 0), parent=wall_e)
    cyl(f"wt{ci}_b", r=3, depth=10, segs=18, loc=(0, 0, 5),
        parent=tower_e, mat_=M_CASTLE_GRAY)
    # Conical roof (signature pointed red)
    smooth_cone(f"wt{ci}_r", r1=3.3, r2=0.1, depth=4, segs=18, loc=(0, 0, 12),
                parent=tower_e, mat_=M_ROOF_RED)
    # Snow on roof
    smooth_cone(f"wt{ci}_rs", r1=3.0, r2=0.05, depth=3.5, segs=18, loc=(0, 0, 12.2),
                parent=tower_e, mat_=M_SNOW)

# ============ 4 MERCHANTS (signature Hanseatic) ============
def make_merchant(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    wool_col = random.choice(WOOL_COLORS)
    # Long fur-trimmed cloak (signature merchant)
    smooth_cone(f"{name}_cl", r1=0.45, r2=0.55, depth=1.5, segs=14, loc=(0, 0, 0.95),
                parent=base, mat_=wool_col)
    # FUR COLLAR (signature)
    cyl(f"{name}_fc", r=0.42, depth=0.20, segs=14, loc=(0, 0, 1.70),
        parent=base, mat_=M_FUR_TRIM)
    # Belt
    cyl(f"{name}_be", r=0.45, depth=0.10, segs=14, loc=(0, 0, 1.0),
        parent=base, mat_=M_LEATHER)
    # Belt pouch (money signature)
    beveled_cube(f"{name}_po", (0.20, 0.10, 0.20), bevel_offset=0.04, loc=(0, -0.40, 0.95),
                 parent=base, mat_=M_LEATHER)
    # Legs
    for side in (-1, 1):
        cyl(f"{name}_l{side}", r=0.10, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=M_WOOL_BROWN)
    # Leather boots
    for side in (-1, 1):
        beveled_cube(f"{name}_b{side}", (0.13, 0.28, 0.10), bevel_offset=0.02,
                     loc=(side*0.13, 0.04, 0.05), parent=base, mat_=M_LEATHER)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.42, 0, 1.50), parent=base)
        sh.rotation_euler = (math.radians(-70), 0, math.radians(side*15))
        cyl(f"{name}_ua{side_idx}", r=0.08, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=wool_col)
        cyl(f"{name}_fa{side_idx}", r=0.07, depth=0.30, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=M_FUR_TRIM)
    # Hands carrying parcel (right)
    parcel_e = empty(f"{name}_pr", (0.30, -0.10, 1.05), parent=base)
    beveled_cube(f"{name}_pr_b", (0.30, 0.25, 0.25), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=parcel_e, mat_=M_LEATHER)
    # Wrapped rope around parcel
    cyl(f"{name}_pr_r", r=0.32, depth=0.04, segs=10, loc=(0, 0, 0),
        parent=parcel_e, mat_=M_LEATHER)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN)
    # Beard signature merchant
    for bi in range(15):
        ba = random.uniform(-math.pi*0.4, math.pi*0.4)
        beard_len = random.uniform(0.10, 0.25)
        for bsi in range(int(beard_len * 6)):
            cyl(f"{name}_bd{bi}_{bsi}", r=0.02, depth=0.06, segs=6,
                loc=(math.sin(ba)*0.10, -0.10, -0.08 - bsi*0.06),
                parent=head_m_e, mat_=random.choice([M_HAIR_BROWN, M_HAIR_BLOND]))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_m_e, mat_=M_EYE)
    # FUR HAT (signature)
    hat_e = empty(f"{name}_ha", (0, 0, 0.18), parent=head_m_e)
    cyl(f"{name}_ha_c", r=0.20, depth=0.22, segs=14, loc=(0, 0, 0),
        parent=hat_e, mat_=M_FUR_TRIM)
    smooth_sphere(f"{name}_ha_t", r=0.18, segs=14, rings=10, loc=(0, 0, 0.13),
                  parent=hat_e, mat_=M_FUR_TRIM, scale=(1, 1, 0.6))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_m_e}

merchants = []
merchant_pos = [(-15, 18, math.radians(180)), (-5, 18, math.radians(180)),
                 (5, 18, math.radians(180)), (15, 18, math.radians(180))]
for i, (mx, my, fac) in enumerate(merchant_pos):
    m = make_merchant(f"me{i}", (mx, my, 0), facing=fac)
    merchants.append(m)

# ============ ESTONIA FLAG main (signature) ============
flag_e = empty("flag", (-55, -40, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_LEATHER)
# 3 horizontal stripes (signature)
beveled_cube("fl_b", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 11.45),
             parent=flag_e, mat_=M_FLAG_BLUE)
beveled_cube("fl_bk", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 10.60),
             parent=flag_e, mat_=M_FLAG_BLACK)
beveled_cube("fl_w", (4, 0.05, 0.85), bevel_offset=0.06, loc=(2, 0, 9.75),
             parent=flag_e, mat_=M_FLAG_WHITE)
flag_e["_phase"] = 0

# ============================================================
# 600 SNOWFLAKES + 400 GOLD STARS (PARTICULES SIGNATURES)
# ============================================================
flakes = []
for i in range(600):
    px = random.uniform(-130, 130)
    py = random.uniform(-130, 130)
    pz = random.uniform(3, 40)
    flake_col = M_FLAKE_WHITE if i % 2 == 0 else M_FLAKE_BLUE
    flake_e = empty(f"sf{i}", (px, py, pz))
    # 6-point snowflake
    for sp in range(6):
        spa = (sp / 6.0) * math.pi * 2
        beveled_cube(f"sf{i}_p{sp}", (0.025, 0.08, 0.01), bevel_offset=0.005,
                     loc=(math.cos(spa)*0.05, math.sin(spa)*0.05, 0),
                     parent=flake_e, mat_=flake_col).rotation_euler = (0, 0, spa)
    smooth_sphere(f"sf{i}_c", r=0.02, loc=(0, 0, 0), parent=flake_e, mat_=flake_col)
    flake_e["_phase"] = random.uniform(0, math.pi*2)
    flake_e["_base_x"] = px; flake_e["_base_z"] = pz
    flake_e["_drift"] = random.uniform(0.2, 0.5)
    flake_e["_fall"] = random.uniform(0.5, 1.3)
    flake_e["_swing"] = random.uniform(1.0, 2.0)
    flakes.append(flake_e)

# 400 gold stars
stars = []
for i in range(400):
    px = random.uniform(-120, 120)
    py = random.uniform(-120, 120)
    pz = random.uniform(3, 35)
    s_col = M_STAR_GOLD if i % 2 == 0 else M_STAR_BRIGHT
    s_e = empty(f"st{i}", (px, py, pz))
    # 5-point star
    for sp in range(5):
        spa = (sp / 5.0) * math.pi * 2 + math.pi/2
        beveled_cube(f"st{i}_p{sp}", (0.025, 0.04, 0.10), bevel_offset=0.005,
                     loc=(math.cos(spa)*0.05, math.sin(spa)*0.05, 0),
                     parent=s_e, mat_=s_col).rotation_euler = (0, 0, spa - math.pi/2)
    smooth_sphere(f"st{i}_c", r=0.03, loc=(0, 0, 0), parent=s_e, mat_=s_col)
    s_e["_phase"] = random.uniform(0, math.pi*2)
    s_e["_base_x"] = px; s_e["_base_y"] = py; s_e["_base_z"] = pz
    s_e["_amp"] = random.uniform(0.5, 1.2)
    s_e["_speed"] = random.uniform(0.4, 1.0)
    s_e["_twinkle"] = random.uniform(2, 5)
    stars.append(s_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Merchants sway/walk
for m in merchants:
    phase = m["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        m["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(3), 0,
                                   math.cos(t * 0.8 + phase) * math.radians(12))
        m["he"].keyframe_insert("rotation_euler", frame=f)

# Main flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)
# Hermann tower flag
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_main_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(20))
    flag_main_e.keyframe_insert("rotation_euler", frame=f)

# 600 snowflakes fall
for sf in flakes:
    phase = sf["_phase"]; drift = sf["_drift"]; fall = sf["_fall"]; swing = sf["_swing"]
    bx, bz = sf["_base_x"], sf["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * swing + phase) * 0.6 + t * drift
        z = bz - (t * fall) % 30
        sf.location = (x, sf.location.y, z)
        sf.rotation_euler = (t * 2.0 + phase, math.sin(t * 2.5 + phase) * math.radians(25), t * 1.5 + phase)
        sf.keyframe_insert("location", frame=f)
        sf.keyframe_insert("rotation_euler", frame=f)

# 400 gold stars twinkle
for s in stars:
    phase = s["_phase"]; speed = s["_speed"]; amp = s["_amp"]; tw = s["_twinkle"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * amp
        y = by + math.cos(t * speed * 0.9 + phase) * amp
        z = bz + math.sin(t * speed * 1.3 + phase) * 0.8
        s.location = (x, y, z)
        # Twinkle
        sc = 0.5 + abs(math.sin(t * tw + phase)) * 1.2
        s.scale = (sc, sc, sc)
        s.rotation_euler = (0, 0, t * 2.0 + phase)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)
        s.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_estonia_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_estonian_tallinn_medieval_old_town] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Tallinn medieval old town: 8 Hanseatic houses (signature pastel facades + stepped gables + steep red tiled roofs + snow caps + 3 floors of windows with timber frames + crossbeams + wooden doors) + Pikk Hermann Tower 30m signature with Estonia flag + Alexander Nevsky Cathedral with 5 onion domes (signature central + 4 corner + gold crosses + brick body) + medieval walls 80m square with crenellations + 4 round corner towers with red conical roofs + 4 Hanseatic merchants (signature fur-trimmed cloaks + fur hats + leather pouches + parcels) + Estonia flag + 600 snowflakes + 400 gold stars twinkling")
print("❄️ FIXES: 1 Toompea cobblestone ground + 600 snowflakes + 400 gold stars signature ❄️")
