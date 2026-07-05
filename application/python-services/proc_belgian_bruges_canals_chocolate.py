"""
proc_belgian_bruges_canals_chocolate.py — 293e procédural AuroraIA (158e qualité)
Belgium Bruges canals chocolate: 8 medieval houses stepped gables + Belfried tower + canals + tourist boats + 4 chocolatiers + Belgium flag + 600 pralines + 400 white swans
FIXES : 1 ground cobblestone canal + signature pralines + swans
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB293)

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

# Sky overcast Flemish
M_SKY = mat("sky", (0.78, 0.82, 0.88, 1.0), 0.0, 0.7, emission=(0.78,0.82,0.88), emission_strength=1.5)
M_SKY_LOW = mat("sky_l", (0.92, 0.92, 0.92, 1.0), 0.0, 0.7, emission=(0.90,0.90,0.92), emission_strength=1.3)
M_SUN = mat("sun", (0.95, 0.85, 0.62, 1.0), 0.0, 0.1, emission=(0.92,0.85,0.62), emission_strength=10.0)
M_CLOUD = mat("cl", (0.95, 0.95, 0.92, 1.0), 0.0, 0.85, emission=(0.95,0.95,0.92), emission_strength=0.7, alpha=0.85)

# Cobblestone
M_COBBLE = mat("co", (0.55, 0.50, 0.45, 1.0), 0.0, 0.85, emission=(0.52,0.50,0.45), emission_strength=0.3)
M_COBBLE_DARK = mat("cod", (0.32, 0.30, 0.28, 1.0), 0.0, 0.92)
M_COBBLE_BROWN = mat("cob", (0.45, 0.38, 0.30, 1.0), 0.0, 0.85)

# Canal water
M_CANAL = mat("ca", (0.32, 0.48, 0.42, 1.0), 0.2, 0.20, emission=(0.30,0.48,0.42), emission_strength=1.3, alpha=0.78)
M_CANAL_DEEP = mat("cad", (0.18, 0.32, 0.28, 1.0), 0.2, 0.25, alpha=0.85)
M_CANAL_FOAM = mat("caf", (0.85, 0.92, 0.88, 1.0), 0.0, 0.30, emission=(0.82,0.92,0.88), emission_strength=1.0, alpha=0.55)

# Medieval house colors (signature Flemish brick)
M_BRICK_DARK = mat("brd", (0.42, 0.22, 0.15, 1.0), 0.0, 0.92)
M_BRICK_RED = mat("br", (0.62, 0.32, 0.22, 1.0), 0.0, 0.85, emission=(0.60,0.30,0.22), emission_strength=0.4)
M_BRICK_BROWN = mat("brn", (0.55, 0.35, 0.20, 1.0), 0.0, 0.85, emission=(0.52,0.35,0.20), emission_strength=0.4)
M_BRICK_WHITE = mat("brw", (0.92, 0.88, 0.78, 1.0), 0.0, 0.75, emission=(0.88,0.85,0.75), emission_strength=0.4)
M_BRICK_YELLOW = mat("bry", (0.95, 0.82, 0.55, 1.0), 0.0, 0.75, emission=(0.92,0.80,0.55), emission_strength=0.5)
M_BRICK_PINK = mat("brp", (0.95, 0.75, 0.68, 1.0), 0.0, 0.75, emission=(0.92,0.72,0.65), emission_strength=0.5)
M_BRICK_ORANGE = mat("bro", (0.85, 0.55, 0.32, 1.0), 0.0, 0.85, emission=(0.82,0.55,0.32), emission_strength=0.5)
BRICK_COLORS = [M_BRICK_RED, M_BRICK_BROWN, M_BRICK_WHITE, M_BRICK_YELLOW, M_BRICK_PINK, M_BRICK_ORANGE]

# Roof (signature red terracotta)
M_ROOF_RED = mat("rr", (0.55, 0.22, 0.18, 1.0), 0.0, 0.85, emission=(0.52,0.22,0.18), emission_strength=0.4)
M_ROOF_DARK = mat("rrd", (0.32, 0.15, 0.12, 1.0), 0.0, 0.92)

# Belfried tower
M_TOWER_STONE = mat("ts", (0.78, 0.72, 0.58, 1.0), 0.0, 0.85, emission=(0.75,0.70,0.58), emission_strength=0.3)
M_TOWER_DARK = mat("tsd", (0.55, 0.50, 0.42, 1.0), 0.0, 0.92)
M_GOLD = mat("g", (0.95, 0.78, 0.20, 1.0), 0.9, 0.10, emission=(0.92,0.75,0.20), emission_strength=1.5)

# Window
M_WINDOW = mat("wd", (0.85, 0.78, 0.55, 1.0), 0.0, 0.35, emission=(0.82,0.78,0.55), emission_strength=2.5)
M_WINDOW_FRAME = mat("wf", (0.22, 0.15, 0.10, 1.0), 0.0, 0.75)
M_DOOR_WOOD = mat("dw", (0.42, 0.22, 0.12, 1.0), 0.0, 0.75)
M_TIMBER = mat("tm", (0.55, 0.32, 0.15, 1.0), 0.0, 0.85)

# Tourist boat
M_BOAT_WHITE = mat("bw", (0.92, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.88,0.88,0.85), emission_strength=0.4)
M_BOAT_WOOD = mat("bwd", (0.62, 0.42, 0.20, 1.0), 0.0, 0.65, emission=(0.60,0.40,0.20), emission_strength=0.4)
M_BOAT_DARK = mat("bdw", (0.32, 0.20, 0.10, 1.0), 0.0, 0.85)

# Chocolatier clothing
M_SKIN = mat("sk", (0.92, 0.75, 0.55, 1.0), 0.0, 0.55, emission=(0.88,0.72,0.55), emission_strength=0.3)
M_HAIR_BROWN = mat("hbr", (0.42, 0.28, 0.18, 1.0), 0.0, 0.85)
M_HAIR_BLOND = mat("hbl", (0.85, 0.72, 0.42, 1.0), 0.0, 0.85)
M_APRON_WHITE = mat("aw", (0.95, 0.95, 0.92, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.90), emission_strength=0.5)
M_CHEF_HAT = mat("ch", (0.98, 0.98, 0.95, 1.0), 0.0, 0.55, emission=(0.95,0.95,0.92), emission_strength=0.6)
M_PANTS_BLACK = mat("pb", (0.10, 0.10, 0.12, 1.0), 0.1, 0.55)

# Chocolate
M_CHOCO_MILK = mat("cm", (0.55, 0.32, 0.20, 1.0), 0.2, 0.35, emission=(0.55,0.32,0.20), emission_strength=0.4)
M_CHOCO_DARK = mat("cd", (0.32, 0.15, 0.08, 1.0), 0.2, 0.30, emission=(0.32,0.15,0.08), emission_strength=0.3)
M_CHOCO_WHITE = mat("cw", (0.95, 0.88, 0.78, 1.0), 0.1, 0.40, emission=(0.92,0.85,0.78), emission_strength=0.5)
M_CHOCO_GOLD = mat("cgo", (0.95, 0.65, 0.30, 1.0), 0.4, 0.30, emission=(0.92,0.62,0.30), emission_strength=0.7)
CHOCO_COLORS = [M_CHOCO_MILK, M_CHOCO_DARK, M_CHOCO_WHITE, M_CHOCO_GOLD]

# Swan (signature white with orange beak)
M_SWAN_WHITE = mat("sw_w", (0.95, 0.95, 0.92, 1.0), 0.0, 0.55, emission=(0.92,0.92,0.90), emission_strength=0.5)
M_SWAN_BEAK = mat("sw_b", (1.0, 0.55, 0.18, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.18), emission_strength=1.0)
M_SWAN_BLACK = mat("sw_bk", (0.10, 0.10, 0.12, 1.0), 0.0, 0.45)

# Belgium flag (signature)
M_FLAG_BLACK = mat("fb", (0.10, 0.10, 0.12, 1.0), 0.0, 0.45)
M_FLAG_YELLOW = mat("fy", (1.0, 0.85, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.82,0.20), emission_strength=1.0)
M_FLAG_RED = mat("fr", (0.85, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.82,0.18,0.20), emission_strength=1.0)

# Bridge stone
M_BRIDGE_STONE = mat("bs_b", (0.55, 0.50, 0.45, 1.0), 0.0, 0.85, emission=(0.52,0.48,0.45), emission_strength=0.3)

# Eye
M_EYE = mat("ed", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# ============ SKY ============
sky = smooth_sphere("sky", r=320, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_l = smooth_sphere("sky_l", r=280, segs=28, rings=16, loc=(0,0,5), mat_=M_SKY_LOW)
sky_l.scale = (1,1,0.3)
sun = smooth_sphere("sun", r=8, segs=24, rings=18, loc=(-50, 110, 35), mat_=M_SUN)
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=8 + sh*1, segs=24, rings=18, loc=(-50, 110, 35), mat_=M_SUN)
# Overcast clouds
for ci in range(25):
    cx_c = random.uniform(-150, 150); cy_c = random.uniform(-100, 100); cz_c = random.uniform(45, 65)
    cloud_e = empty(f"cl{ci}_e", (cx_c, cy_c, cz_c))
    for cp in range(5):
        cpa = random.uniform(0, math.pi*2); cpr = random.uniform(0, 4)
        smooth_sphere(f"cl{ci}_p{cp}", r=random.uniform(2.5, 4.5), segs=14, rings=10,
                      loc=(math.cos(cpa)*cpr, math.sin(cpa)*cpr, random.uniform(-1, 1)),
                      parent=cloud_e, mat_=M_CLOUD, scale=(1.5, 1.5, 0.5))

# ============ ONE clean cobblestone + canal ground ============
ground = beveled_cube("ground", (220, 220, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_COBBLE_BROWN)
# Cobblestones
for cbi in range(40):
    for cbj in range(40):
        bx = -30 + cbi * 1.5
        by = -30 + cbj * 1.5
        if -28 < bx < 28 and -28 < by < 28 and random.random() > 0.30:
            cyl(f"cb{cbi}_{cbj}", r=0.42, depth=0.08, segs=10,
                loc=(bx, by, 0.10),
                mat_=M_COBBLE if (cbi + cbj) % 2 else M_COBBLE_DARK)

# ============ CANAL (signature winding waterway) ============
canal_e = empty("canal", (0, 5, 0))
# Main canal channel
beveled_cube("ca_m", (100, 12, 0.20), bevel_offset=0.08, loc=(0, 0, 0.20),
             parent=canal_e, mat_=M_CANAL)
beveled_cube("ca_md", (95, 10, 0.15), bevel_offset=0.06, loc=(0, 0, 0.25),
             parent=canal_e, mat_=M_CANAL_DEEP)
# Stone canal walls
for side in (-1, 1):
    beveled_cube(f"ca_w{side}", (100, 1, 1), bevel_offset=0.06,
                 loc=(0, side*6.5, 0.5), parent=canal_e, mat_=M_BRIDGE_STONE)
# Foam streaks
for fi in range(30):
    fx = random.uniform(-45, 45); fy = random.uniform(-5, 5)
    cyl(f"ca_f{fi}", r=random.uniform(0.3, 0.6), depth=0.05, segs=14,
        loc=(fx, fy, 0.30), parent=canal_e, mat_=M_CANAL_FOAM)

# ============ ARCHED STONE BRIDGE (signature Bruges) ============
bridge_e = empty("bridge", (0, 5, 0))
# Arch (curved stone)
for ai in range(10):
    aa = (ai / 10.0) * math.pi
    ax = math.cos(aa) * 7
    az = math.sin(aa) * 3 + 0.5
    cyl(f"br_a{ai}", r=0.40, depth=2.5, segs=10,
        loc=(ax, 0, az), parent=bridge_e, mat_=M_BRIDGE_STONE).rotation_euler = (math.radians(90), 0, 0)
# Bridge deck
beveled_cube("br_d", (15, 2.5, 0.40), bevel_offset=0.06, loc=(0, 0, 3.8),
             parent=bridge_e, mat_=M_BRIDGE_STONE)
# Railings
for side in (-1, 1):
    beveled_cube(f"br_rl{side}", (15, 0.10, 0.80), bevel_offset=0.04,
                 loc=(0, side*1.2, 4.5), parent=bridge_e, mat_=M_BRIDGE_STONE)
    # Posts
    for pi in range(6):
        cyl(f"br_p{side}_{pi}", r=0.10, depth=0.95, segs=8,
            loc=(-6 + pi*2.4, side*1.2, 4.4), parent=bridge_e, mat_=M_BRIDGE_STONE)

# ============ 8 MEDIEVAL HOUSES with STEPPED GABLES (signature Flemish) ============
def make_bruges_house(name, loc, width, height, depth, brick_col):
    base = empty(name, loc)
    # Main building
    beveled_cube(f"{name}_w", (width, depth, height), bevel_offset=0.10,
                 loc=(0, 0, height/2), parent=base, mat_=brick_col)
    # Brick texture lines
    for bi in range(int(height / 1.5)):
        beveled_cube(f"{name}_bl{bi}", (width + 0.02, 0.02, 0.10), bevel_offset=0.01,
                     loc=(0, -depth/2 - 0.02, 0.5 + bi*1.5), parent=base,
                     mat_=M_BRICK_DARK if bi % 2 else brick_col)
    # STEPPED GABLE (signature Flemish architecture - decorative pyramid steps)
    n_steps = 6
    for si_g in range(n_steps):
        step_w = width - si_g * 0.5
        step_h = 0.5
        beveled_cube(f"{name}_g{si_g}", (step_w, depth + 0.10, step_h), bevel_offset=0.04,
                     loc=(0, 0, height + si_g*0.5 + 0.25), parent=base, mat_=brick_col)
        # Curved step tops (signature)
        if si_g < n_steps - 1:
            smooth_sphere(f"{name}_gc{si_g}", r=0.30, segs=10, rings=8,
                          loc=(-step_w/2 + 0.15, -depth/2 - 0.05, height + si_g*0.5 + 0.50),
                          parent=base, mat_=brick_col, scale=(1, 1, 0.5))
            smooth_sphere(f"{name}_gc{si_g}r", r=0.30, segs=10, rings=8,
                          loc=(step_w/2 - 0.15, -depth/2 - 0.05, height + si_g*0.5 + 0.50),
                          parent=base, mat_=brick_col, scale=(1, 1, 0.5))
    # Roof tip
    smooth_cone(f"{name}_rt", r1=0.5, r2=0.05, depth=1.5, segs=4, loc=(0, 0, height + n_steps*0.5 + 0.75),
                parent=base, mat_=M_ROOF_RED).rotation_euler = (0, 0, math.radians(45))
    # WINDOWS (signature multi-story)
    win_rows = max(3, int(height / 2.5)); win_cols = max(2, int(width / 2))
    for r in range(win_rows):
        for c in range(win_cols):
            wx = -width/2 + (c + 0.5) * (width / win_cols)
            wz = (r + 0.5) * (height / win_rows)
            # Frame
            beveled_cube(f"{name}_wf{r}_{c}", (0.65, 0.04, 0.85), bevel_offset=0.02,
                         loc=(wx, -depth/2 - 0.05, wz), parent=base, mat_=M_WINDOW_FRAME)
            # Glass
            beveled_cube(f"{name}_wg{r}_{c}", (0.55, 0.02, 0.75), bevel_offset=0.02,
                         loc=(wx, -depth/2 - 0.07, wz), parent=base, mat_=M_WINDOW)
            # Cross frame (signature mullions)
            beveled_cube(f"{name}_wxv{r}_{c}", (0.04, 0.03, 0.75), bevel_offset=0.005,
                         loc=(wx, -depth/2 - 0.08, wz), parent=base, mat_=M_WINDOW_FRAME)
            beveled_cube(f"{name}_wxh{r}_{c}", (0.55, 0.03, 0.04), bevel_offset=0.005,
                         loc=(wx, -depth/2 - 0.08, wz), parent=base, mat_=M_WINDOW_FRAME)
    # Door (signature wooden)
    beveled_cube(f"{name}_d", (0.9, 0.06, 2.0), bevel_offset=0.05,
                 loc=(0, -depth/2 - 0.05, 1.0), parent=base, mat_=M_DOOR_WOOD)
    # Door arch
    cyl(f"{name}_da", r=0.45, depth=0.10, segs=14, loc=(0, -depth/2 - 0.05, 1.95),
        parent=base, mat_=M_DOOR_WOOD).rotation_euler = (math.radians(90), 0, 0)
    # Timber frame (signature dark wooden beams)
    for ti_b in range(3):
        beveled_cube(f"{name}_tb{ti_b}", (width + 0.05, 0.05, 0.12), bevel_offset=0.02,
                     loc=(0, -depth/2 - 0.06, 0.5 + ti_b*2), parent=base, mat_=M_TIMBER)
    return base

# Row of houses along canal (signature)
house_pos = [
    (-30, -8, 4, 8, 3), (-22, -8, 4.5, 9, 3), (-13, -8, 4, 7.5, 3),
    (-4, -8, 4.5, 10, 3), (5, -8, 4, 8.5, 3), (14, -8, 4.5, 9, 3),
    (23, -8, 4, 7, 3), (32, -8, 4.5, 8, 3)
]
for i, (hx, hy, hw, hh, hd) in enumerate(house_pos):
    make_bruges_house(f"bh{i}", (hx, hy, 0), hw, hh, hd, random.choice(BRICK_COLORS))

# ============ BELFRIED TOWER (signature 83m Bruges bell tower) ============
belfried_e = empty("belfried", (0, 40, 0))
# Square base
beveled_cube("bf_b", (8, 8, 12), bevel_offset=0.12, loc=(0, 0, 6),
             parent=belfried_e, mat_=M_TOWER_STONE)
# 2nd section
beveled_cube("bf_s2", (6.5, 6.5, 12), bevel_offset=0.12, loc=(0, 0, 18),
             parent=belfried_e, mat_=M_TOWER_STONE)
# 3rd section (octagonal)
n_oct = 8
oct_r = 3.5
for oi in range(n_oct):
    oa = (oi / n_oct) * math.pi * 2 + math.pi/n_oct
    beveled_cube(f"bf_o{oi}", (1.5, 1.5, 10), bevel_offset=0.08,
                 loc=(math.cos(oa)*oct_r, math.sin(oa)*oct_r, 29),
                 parent=belfried_e, mat_=M_TOWER_STONE).rotation_euler = (0, 0, oa + math.pi/n_oct)
# 4th tier (top)
cyl("bf_t4", r=3, depth=4, segs=16, loc=(0, 0, 36), parent=belfried_e, mat_=M_TOWER_STONE)
# Spire on top (signature)
smooth_cone("bf_sp", r1=3, r2=0.05, depth=10, segs=16, loc=(0, 0, 43),
            parent=belfried_e, mat_=M_TOWER_DARK)
# Decorative balconies
for bi in range(4):
    bz_b = 12 + bi * 6
    cyl(f"bf_ba{bi}", r=4 - bi*0.4, depth=0.30, segs=18, loc=(0, 0, bz_b),
        parent=belfried_e, mat_=M_TOWER_DARK)
# Stone block lines
for bi in range(24):
    bz = 0.5 + bi * 1.5
    beveled_cube(f"bf_bl{bi}", (8.05, 0.05, 0.30), bevel_offset=0.02,
                 loc=(0, -4.05, bz), parent=belfried_e, mat_=M_TOWER_DARK)
# Arched windows (signature)
for wi in range(6):
    wz = 6 + wi * 5
    for side in (-1, 1):
        beveled_cube(f"bf_w{wi}_{side}", (0.6, 0.10, 2), bevel_offset=0.04,
                     loc=(side*3.5, -4.10, wz), parent=belfried_e, mat_=M_WINDOW_FRAME)
        # Arch top
        cyl(f"bf_wa{wi}_{side}", r=0.30, depth=0.12, segs=12, loc=(side*3.5, -4.15, wz + 1.0),
            parent=belfried_e, mat_=M_WINDOW_FRAME).rotation_euler = (math.radians(90), 0, 0)
        # Glass
        beveled_cube(f"bf_wg{wi}_{side}", (0.50, 0.02, 1.8), bevel_offset=0.02,
                     loc=(side*3.5, -4.18, wz), parent=belfried_e, mat_=M_WINDOW)
# Gold cross/spire top
smooth_sphere("bf_top", r=0.5, loc=(0, 0, 53), parent=belfried_e, mat_=M_GOLD)
cyl("bf_topc", r=0.10, depth=2, segs=8, loc=(0, 0, 54.5), parent=belfried_e, mat_=M_GOLD)
beveled_cube("bf_topx", (0.6, 0.10, 0.10), bevel_offset=0.02, loc=(0, 0, 55.5),
             parent=belfried_e, mat_=M_GOLD)

# ============ 4 TOURIST BOATS (signature canal boats) ============
def make_canal_boat(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Hull (signature flat-bottom)
    beveled_cube(f"{name}_h", (5, 1.5, 0.50), bevel_offset=0.15, loc=(0, 0, 0),
                 parent=base, mat_=M_BOAT_WOOD)
    # Plank seating (3 benches)
    for bi in range(3):
        beveled_cube(f"{name}_se{bi}", (1.0, 1.4, 0.30), bevel_offset=0.05,
                     loc=(-1.5 + bi*1.5, 0, 0.30), parent=base, mat_=M_BOAT_WOOD)
    # Awning (white canopy)
    awning_e = empty(f"{name}_aw", (0, 0, 1.5), parent=base)
    beveled_cube(f"{name}_aw_t", (4, 1.6, 0.06), bevel_offset=0.04, loc=(0, 0, 0),
                 parent=awning_e, mat_=M_BOAT_WHITE)
    # Awning poles
    for ai_p in range(4):
        for ays in (-1, 1):
            cyl(f"{name}_ap{ai_p}_{ays}", r=0.04, depth=1.0, segs=8,
                loc=(-1.5 + ai_p*1.0, ays*0.7, -0.50),
                parent=awning_e, mat_=M_BOAT_DARK)
    # Bow point
    smooth_cone(f"{name}_bw", r1=0.6, r2=0.1, depth=1, segs=10, loc=(2.5, 0, 0),
                parent=base, mat_=M_BOAT_WOOD).rotation_euler = (0, math.radians(90), 0)
    # Tour guide silhouette (signature pilot in back)
    smooth_sphere(f"{name}_pl_b", r=0.25, segs=12, rings=10, loc=(-1.8, 0, 0.95),
                  parent=base, mat_=M_PANTS_BLACK, scale=(1, 1, 1.5))
    smooth_sphere(f"{name}_pl_h", r=0.15, segs=10, rings=8, loc=(-1.8, 0, 1.35),
                  parent=base, mat_=M_SKIN)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

boats = []
boat_pos = [(-25, 5, math.radians(0)), (-10, 5, math.radians(0)),
             (5, 5, math.radians(180)), (25, 5, math.radians(180))]
for i, (bx, by, fac) in enumerate(boat_pos):
    b = make_canal_boat(f"cb{i}", (bx, by, 0.40), facing=fac)
    boats.append(b)

# ============ 4 CHOCOLATIERS (signature white aprons + chef hats) ============
def make_chocolatier(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # White chef apron
    smooth_cone(f"{name}_ap", r1=0.30, r2=0.35, depth=1.0, segs=14, loc=(0, 0, 1.20),
                parent=base, mat_=M_APRON_WHITE)
    # Black pants underneath
    for side in (-1, 1):
        cyl(f"{name}_p{side}", r=0.11, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.45), parent=base, mat_=M_PANTS_BLACK)
    # Black shoes
    for side in (-1, 1):
        beveled_cube(f"{name}_s{side}", (0.13, 0.26, 0.05), bevel_offset=0.02,
                     loc=(side*0.13, 0.02, 0.03), parent=base, mat_=M_PANTS_BLACK)
    # Arms
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_a{side_idx}", (side*0.30, 0, 1.60), parent=base)
        sh.rotation_euler = (math.radians(-80), 0, math.radians(side*10))
        cyl(f"{name}_ua{side_idx}", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=sh, mat_=M_APRON_WHITE)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.30, segs=10, loc=(0, 0, -0.55),
            parent=sh, mat_=M_SKIN)
    # CHOCOLATE TRAY (signature)
    tray_e = empty(f"{name}_tr", (0, -0.30, 1.05), parent=base)
    beveled_cube(f"{name}_tr_p", (0.50, 0.30, 0.06), bevel_offset=0.02, loc=(0, 0, 0),
                 parent=tray_e, mat_=M_BOAT_WOOD)
    # Chocolates on tray (signature pralines)
    for cni in range(2):
        for cnj in range(3):
            smooth_sphere(f"{name}_cn{cni}_{cnj}", r=0.05,
                          loc=(-0.20 + cnj*0.20, -0.10 + cni*0.20, 0.05),
                          parent=tray_e, mat_=random.choice(CHOCO_COLORS))
    # Head
    head_c_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_h", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_c_e, mat_=M_SKIN)
    # Hair
    hair_col = random.choice([M_HAIR_BROWN, M_HAIR_BLOND])
    for hi in range(10):
        ha = random.uniform(0, math.pi*2)
        cyl(f"{name}_hr{hi}", r=0.04, depth=0.06, segs=6,
            loc=(math.cos(ha)*0.12, math.sin(ha)*0.10, 0.10),
            parent=head_c_e, mat_=hair_col)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_ey{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_c_e, mat_=M_EYE)
    # Smile
    beveled_cube(f"{name}_sm", (0.08, 0.04, 0.025), bevel_offset=0.005,
                 loc=(0, -0.17, -0.07), parent=head_c_e, mat_=M_SWAN_BEAK)
    # CHEF HAT (signature poofy white)
    hat_e = empty(f"{name}_ha", (0, 0, 0.20), parent=head_c_e)
    cyl(f"{name}_ha_c", r=0.18, depth=0.10, segs=14, loc=(0, 0, 0),
        parent=hat_e, mat_=M_CHEF_HAT)
    # Poofy top (signature)
    smooth_sphere(f"{name}_ha_t", r=0.22, segs=18, rings=14, loc=(0, 0, 0.25),
                  parent=hat_e, mat_=M_CHEF_HAT, scale=(1.1, 1.1, 0.95))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_c_e}

chocolatiers = []
choc_pos = [(-30, -16, math.radians(0)), (-10, -16, math.radians(0)),
             (10, -16, math.radians(0)), (30, -16, math.radians(0))]
for i, (cx, cy, fac) in enumerate(choc_pos):
    c = make_chocolatier(f"ch{i}", (cx, cy, 0), facing=fac)
    chocolatiers.append(c)

# ============ BELGIUM FLAG (signature 3 vertical stripes) ============
flag_e = empty("flag", (-55, -45, 0))
cyl("fl_p", r=0.10, depth=12, segs=10, loc=(0, 0, 6), parent=flag_e, mat_=M_BOAT_DARK)
# Vertical stripes
beveled_cube("fl_bk", (1.4, 0.05, 2.5), bevel_offset=0.06, loc=(0.7, 0, 10.5),
             parent=flag_e, mat_=M_FLAG_BLACK)
beveled_cube("fl_y", (1.4, 0.05, 2.5), bevel_offset=0.06, loc=(2.1, 0, 10.5),
             parent=flag_e, mat_=M_FLAG_YELLOW)
beveled_cube("fl_r", (1.4, 0.05, 2.5), bevel_offset=0.06, loc=(3.5, 0, 10.5),
             parent=flag_e, mat_=M_FLAG_RED)
flag_e["_phase"] = 0

# ============================================================
# 600 PRALINES + 400 WHITE SWANS (PARTICULES SIGNATURES)
# ============================================================
pralines = []
for i in range(600):
    px = random.uniform(-100, 100)
    py = random.uniform(-100, 100)
    pz = random.uniform(2, 25)
    pc = random.choice(CHOCO_COLORS)
    p_e = empty(f"pr{i}", (px, py, pz))
    # Praline (round chocolate)
    smooth_sphere(f"pr{i}_b", r=0.10, segs=12, rings=8, loc=(0, 0, 0),
                  parent=p_e, mat_=pc, scale=(1, 1, 0.85))
    # Gold foil wrapper top (signature)
    if random.random() > 0.5:
        cyl(f"pr{i}_t", r=0.08, depth=0.04, segs=10, loc=(0, 0, 0.08),
            parent=p_e, mat_=M_CHOCO_GOLD)
    # Decorative swirl
    smooth_sphere(f"pr{i}_s", r=0.03, loc=(0, 0, 0.08),
                  parent=p_e, mat_=random.choice([M_CHOCO_WHITE, M_CHOCO_MILK]))
    p_e["_phase"] = random.uniform(0, math.pi*2)
    p_e["_base_x"] = px; p_e["_base_y"] = py; p_e["_base_z"] = pz
    p_e["_amp_x"] = random.uniform(0.5, 1.5)
    p_e["_amp_y"] = random.uniform(0.5, 1.5)
    p_e["_amp_z"] = random.uniform(0.4, 1.0)
    p_e["_speed"] = random.uniform(0.4, 1.0)
    pralines.append(p_e)

# 400 white swans (signature Bruges Lake of Love swans)
swans = []
for i in range(400):
    px = random.uniform(-100, 100)
    py = random.uniform(-50, 50)
    pz = 0.50
    s_e = empty(f"sw{i}", (px, py, pz))
    # Body
    smooth_sphere(f"sw{i}_b", r=0.20, segs=12, rings=10, loc=(0, 0, 0),
                  parent=s_e, mat_=M_SWAN_WHITE, scale=(1.7, 0.85, 0.95))
    # Long curved neck (signature S-shape)
    neck_e = empty(f"sw{i}_ne", (0.15, 0, 0.10), parent=s_e)
    for ni in range(6):
        ni_t = ni / 6.0
        cyl(f"sw{i}_n{ni}", r=0.035, depth=0.10, segs=8,
            loc=(math.sin(ni_t * math.pi * 0.5) * 0.08,
                 0,
                 ni_t * 0.4 + math.cos(ni_t * math.pi * 0.5) * 0.05 + 0.05),
            parent=neck_e, mat_=M_SWAN_WHITE)
    # Head
    smooth_sphere(f"sw{i}_h", r=0.08, segs=10, rings=8, loc=(0.15, 0, 0.55),
                  parent=neck_e, mat_=M_SWAN_WHITE)
    # ORANGE BEAK (signature)
    cyl(f"sw{i}_bk", r=0.02, depth=0.12, segs=8, loc=(0.23, 0, 0.55),
        parent=neck_e, mat_=M_SWAN_BEAK).rotation_euler = (0, math.radians(95), 0)
    # Black knob on beak base (signature mute swan)
    smooth_sphere(f"sw{i}_kn", r=0.025, loc=(0.18, 0, 0.60),
                  parent=neck_e, mat_=M_SWAN_BLACK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"sw{i}_ey{side}", r=0.015, loc=(0.18, side*0.05, 0.58),
                      parent=neck_e, mat_=M_EYE)
    # Wings folded back (signature feather pattern)
    for side in (-1, 1):
        wing_e = empty(f"sw{i}_w{side}_e", (0, side*0.10, 0.05), parent=s_e)
        # Layered feather effect
        for fi in range(4):
            beveled_cube(f"sw{i}_w{side}_f{fi}", (0.15 - fi*0.025, 0.12, 0.02), bevel_offset=0.01,
                         loc=(-fi*0.08, 0, fi*0.02), parent=wing_e, mat_=M_SWAN_WHITE)
    # Tail
    beveled_cube(f"sw{i}_t", (0.10, 0.08, 0.04), bevel_offset=0.01,
                 loc=(-0.20, 0, 0.05), parent=s_e, mat_=M_SWAN_WHITE)
    s_e["_phase"] = random.uniform(0, math.pi*2)
    s_e["_base_x"] = px; s_e["_base_y"] = py; s_e["_base_z"] = pz
    s_e["_speed"] = random.uniform(0.2, 0.6)
    s_e["_radius"] = random.uniform(2, 8)
    swans.append(s_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Boats glide
for b in boats:
    phase = b["_phase"]
    bz_b = b.location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        b.location.z = bz_b + math.sin(t * 1.0 + phase) * 0.06
        b.rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2),
                             math.cos(t * 1.0 + phase) * math.radians(2),
                             b.rotation_euler.z)
        b.keyframe_insert("location", frame=f)
        b.keyframe_insert("rotation_euler", frame=f)

# Chocolatiers sway
for c in chocolatiers:
    phase = c["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        c["root"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(2), 0,
                                     c["root"].rotation_euler.z)
        c["root"].keyframe_insert("rotation_euler", frame=f)
        c["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(3), 0,
                                   math.cos(t * 0.8 + phase) * math.radians(10))
        c["he"].keyframe_insert("rotation_euler", frame=f)

# Flag wave
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    flag_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(12))
    flag_e.keyframe_insert("rotation_euler", frame=f)

# 600 pralines float multi-axis
for p in pralines:
    phase = p["_phase"]; speed = p["_speed"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    ax, ay, az = p["_amp_x"], p["_amp_y"], p["_amp_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.2 + phase) + t * 0.3
        p.location = (x, y, z)
        p.rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(20), 0,
                             t * 1.0 + phase)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

# 400 swans swim in circles
for sw in swans:
    phase = sw["_phase"]; speed = sw["_speed"]; radius = sw["_radius"]
    bx, by, bz_s = sw["_base_x"], sw["_base_y"], sw["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + math.cos(t * speed + phase) * radius
        y = by + math.sin(t * speed + phase) * radius
        z = bz_s + math.sin(t * speed * 1.5 + phase) * 0.08
        sw.location = (x, y, z)
        sw.rotation_euler = (0, 0, math.atan2(math.cos(t * speed + phase),
                                                -math.sin(t * speed + phase)))
        sw.keyframe_insert("location", frame=f)
        sw.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_belgium_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_belgian_bruges_canals_chocolate] DONE → {out_glb} ({size_mb:.2f} MB)")
print("Belgium Bruges: 8 medieval Flemish brick houses with signature stepped gables (6 steps with curved tops + decorative timber beams + arched doors + multi-story cross-mullion windows) + Belfried bell tower 53m signature with square base + octagonal middle + arched windows + gold cross top + canal waterway + stone arched bridge + 4 tourist boats with white awnings + tour guides + 4 chocolatiers (signature white aprons + poofy chef hats + chocolate trays with pralines) + Belgium flag tricolor + overcast Flemish sky + 600 pralines floating (4 chocolate colors with gold foil) + 400 white swans (signature S-curve necks + orange beaks + black knobs + folded feathered wings)")
print("🦢 FIXES: 1 cobblestone canal ground + 600 pralines + 400 white swans signature 🦢")
