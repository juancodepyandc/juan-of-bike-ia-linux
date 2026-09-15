"""
proc_chinese_great_wall_dragon.py — 258e procédural AuroraIA (123e qualité)
Great Wall of China dragon: serpentine wall + 6 watchtowers + golden dragon 20m + 6 dragon dancers + emperor + 4 archers + 8 musicians + tiger statues + 600 red lanterns + 400 peony petals
FIXES : 1 ground + 600 red lanterns + 400 peony petals (signature)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB258)

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

# Sunset red-gold sky
M_SKY = mat("sky", (0.85, 0.42, 0.28, 1.0), 0.0, 0.7, emission=(0.85,0.42,0.28), emission_strength=2.0)
M_SKY_GOLD = mat("sky_g", (1.0, 0.65, 0.30, 1.0), 0.0, 0.7, emission=(1.0,0.65,0.30), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.78, 0.30, 1.0), 0.0, 0.1, emission=(1.0,0.78,0.30), emission_strength=18.0)
M_CLOUD_RED = mat("cloud_r", (0.95, 0.55, 0.45, 1.0), 0.0, 0.7, emission=(0.92,0.55,0.45), emission_strength=1.5)

# Mountain
M_MOUNTAIN = mat("mt", (0.42, 0.32, 0.30, 1.0), 0.0, 0.85, emission=(0.40,0.30,0.28), emission_strength=0.4)
M_MOUNTAIN_DARK = mat("mt_d", (0.25, 0.20, 0.18, 1.0), 0.0, 0.85)
M_MOUNTAIN_MIST = mat("mt_m", (0.78, 0.65, 0.50, 1.0), 0.0, 0.80, emission=(0.72,0.62,0.50), emission_strength=0.5)

# Ground (stone)
M_STONE_GROUND = mat("stone", (0.62, 0.52, 0.40, 1.0), 0.0, 0.85, emission=(0.58,0.50,0.40), emission_strength=0.4)
M_STONE_DARK_GW = mat("stone_d", (0.40, 0.32, 0.25, 1.0), 0.0, 0.85)
M_GRASS_GW = mat("grass", (0.42, 0.55, 0.22, 1.0), 0.0, 0.80, emission=(0.40,0.52,0.22), emission_strength=0.4)

# Great Wall stone (signature)
M_WALL_STONE = mat("wall_s", (0.65, 0.55, 0.42, 1.0), 0.0, 0.85, emission=(0.60,0.52,0.42), emission_strength=0.5)
M_WALL_DARK_W = mat("wall_d", (0.42, 0.35, 0.28, 1.0), 0.0, 0.85)
M_WALL_BRICK = mat("wall_b", (0.55, 0.42, 0.32, 1.0), 0.0, 0.85)

# Tower
M_TOWER_ROOF = mat("tw_r", (0.18, 0.18, 0.22, 1.0), 0.5, 0.40, emission=(0.18,0.18,0.22), emission_strength=0.4)
M_TOWER_RED = mat("tw_rd", (0.78, 0.20, 0.20, 1.0), 0.0, 0.65, emission=(0.72,0.20,0.20), emission_strength=0.6)
M_TOWER_GOLD = mat("tw_g", (1.0, 0.85, 0.30, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.30), emission_strength=2.0)

# Dragon (signature gold/red serpentine)
M_DRAGON_GOLD = mat("dr_g", (1.0, 0.85, 0.25, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.25), emission_strength=2.5)
M_DRAGON_GOLD_DEEP = mat("dr_gd", (0.85, 0.62, 0.18, 1.0), 0.95, 0.20, emission=(0.80,0.58,0.18), emission_strength=2.0)
M_DRAGON_RED = mat("dr_r", (0.92, 0.20, 0.15, 1.0), 0.0, 0.45, emission=(0.88,0.20,0.15), emission_strength=1.5)
M_DRAGON_GREEN = mat("dr_gr", (0.30, 0.75, 0.30, 1.0), 0.0, 0.45, emission=(0.30,0.72,0.30), emission_strength=1.2)
M_DRAGON_EYE = mat("dr_e", (1.0, 0.30, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.30,0.20), emission_strength=15.0)
M_DRAGON_WHISKER = mat("dr_w", (0.85, 0.85, 0.85, 1.0), 0.5, 0.30, emission=(0.80,0.80,0.80), emission_strength=0.8)
M_DRAGON_BLACK = mat("dr_bk", (0.08, 0.06, 0.06, 1.0), 0.3, 0.40)
M_DRAGON_TEETH = mat("dr_t", (0.95, 0.92, 0.85, 1.0), 0.0, 0.40)

# Skin
M_SKIN_ASIAN = mat("skin", (0.92, 0.78, 0.62, 1.0), 0.0, 0.55, emission=(0.88,0.75,0.62), emission_strength=0.4)

# Hair
M_HAIR_BLACK_C = mat("h_bk", (0.08, 0.06, 0.05, 1.0), 0.0, 0.55)
M_HAIR_GREY_C = mat("h_g", (0.62, 0.55, 0.48, 1.0), 0.0, 0.60)

# Emperor robe (signature)
M_EMPEROR_GOLD = mat("emp_g", (1.0, 0.85, 0.20, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.20), emission_strength=1.5)
M_EMPEROR_RED = mat("emp_r", (0.78, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.72,0.15,0.15), emission_strength=0.6)
M_EMPEROR_BLACK = mat("emp_bk", (0.10, 0.08, 0.06, 1.0), 0.0, 0.65)
M_DRAGON_ROBE_PATTERN = mat("drp", (1.0, 0.92, 0.30, 1.0), 0.95, 0.10, emission=(0.95,0.88,0.30), emission_strength=2.5)

# Archer/soldier
M_SOLDIER_RED = mat("sld_r", (0.65, 0.15, 0.15, 1.0), 0.0, 0.65, emission=(0.60,0.15,0.15), emission_strength=0.5)
M_SOLDIER_BLACK = mat("sld_bk", (0.10, 0.08, 0.08, 1.0), 0.3, 0.40)
M_SOLDIER_GOLD = mat("sld_g", (0.92, 0.78, 0.20, 1.0), 0.85, 0.25, emission=(0.88,0.75,0.20), emission_strength=1.2)
M_BOW_WOOD = mat("bow_w", (0.42, 0.25, 0.10, 1.0), 0.0, 0.65, emission=(0.40,0.25,0.10), emission_strength=0.4)
M_BOW_STRING_C = mat("bow_s", (0.85, 0.78, 0.55, 1.0), 0.0, 0.55)
M_ARROW_C = mat("arr", (0.55, 0.32, 0.15, 1.0), 0.0, 0.70)
M_ARROW_FEATHER = mat("arr_f", (0.92, 0.30, 0.30, 1.0), 0.0, 0.45, emission=(0.88,0.30,0.30), emission_strength=0.6)

# Musician outfit
M_MUSICIAN_BLUE = mat("mus_b", (0.18, 0.32, 0.62, 1.0), 0.0, 0.65, emission=(0.18,0.30,0.60), emission_strength=0.6)

# Instruments
M_DRUM_RED = mat("drm_r", (0.85, 0.18, 0.15, 1.0), 0.0, 0.55, emission=(0.80,0.18,0.15), emission_strength=0.6)
M_DRUM_SKIN = mat("drm_s", (0.92, 0.78, 0.55, 1.0), 0.0, 0.55, emission=(0.85,0.72,0.52), emission_strength=0.5)
M_DRUM_GOLD = mat("drm_g", (1.0, 0.85, 0.30, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.30), emission_strength=1.5)
M_PIPA_WOOD = mat("pp_w", (0.55, 0.30, 0.15, 1.0), 0.0, 0.55, emission=(0.50,0.30,0.15), emission_strength=0.4)

# Tiger statue
M_TIGER_STONE = mat("tg_s", (0.42, 0.40, 0.38, 1.0), 0.0, 0.85, emission=(0.40,0.38,0.36), emission_strength=0.3)
M_TIGER_MOSS = mat("tg_m", (0.30, 0.45, 0.25, 1.0), 0.0, 0.80)

# Lantern red signature
M_LANTERN_RED = mat("lan_r", (1.0, 0.25, 0.20, 1.0), 0.0, 0.20, emission=(1.0,0.25,0.20), emission_strength=10.0, alpha=0.85)
M_LANTERN_FRAME = mat("lan_f", (0.20, 0.15, 0.10, 1.0), 0.7, 0.40, emission=(0.18,0.12,0.10), emission_strength=0.5)
M_LANTERN_TASSEL = mat("lan_t", (1.0, 0.85, 0.30, 1.0), 0.85, 0.20, emission=(0.95,0.80,0.30), emission_strength=1.5)

# Peony petals (signature pink)
M_PEONY_PINK = mat("po_p", (1.0, 0.55, 0.75, 1.0), 0.0, 0.45, emission=(0.95,0.55,0.72), emission_strength=1.8)
M_PEONY_DEEP = mat("po_d", (0.85, 0.30, 0.55, 1.0), 0.0, 0.45, emission=(0.80,0.30,0.52), emission_strength=1.5)
M_PEONY_WHITE = mat("po_w", (0.98, 0.92, 0.88, 1.0), 0.0, 0.40, emission=(0.92,0.88,0.85), emission_strength=1.5)
PEONY_COLORS = [M_PEONY_PINK, M_PEONY_DEEP, M_PEONY_WHITE]

# Flag (signature red with yellow stars)
M_FLAG_RED = mat("fl_r", (0.85, 0.10, 0.10, 1.0), 0.0, 0.55, emission=(0.80,0.10,0.10), emission_strength=0.8)
M_FLAG_STAR = mat("fl_st", (1.0, 0.92, 0.20, 1.0), 0.0, 0.30, emission=(0.95,0.88,0.20), emission_strength=2.5)

# Eye
M_EYE_DARK_C = mat("eye_d", (0.05, 0.04, 0.04, 1.0), 0.0, 0.20)

# ============ SKY ============
sky = smooth_sphere("sky", r=300, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.6)
sky_g = smooth_sphere("sky_g", r=250, segs=28, rings=16, loc=(0,0,8), mat_=M_SKY_GOLD)
sky_g.scale = (1,1,0.22)
# Sun
sun = smooth_sphere("sun", r=6, segs=24, rings=18, loc=(40, 90, 35), mat_=M_SUN)
# Sun halo
for sh in range(3):
    smooth_sphere(f"sun_h{sh}", r=6 + sh*0.8, segs=24, rings=18, loc=(40, 90, 35), mat_=M_SUN)
# Clouds tinted red
for ci in range(20):
    cax = random.uniform(-100, 100); cay = random.uniform(-100, 100)
    caz = random.uniform(30, 60)
    cloud_e = empty(f"cloud{ci}", (cax, cay, caz))
    for cli in range(random.randint(3, 5)):
        smooth_sphere(f"c{ci}_{cli}", r=random.uniform(2.5, 4.5), segs=16, rings=10,
                      loc=(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD_RED, scale=(1.4, 1.2, 0.7))
    cloud_e["_phase"] = random.uniform(0, math.pi*2)

# ============ MOUNTAINS background (signature) ============
for mi in range(10):
    mxa = (mi / 10.0) * math.pi * 2 + math.pi/8
    mxr = 80 + random.uniform(-10, 10)
    mx_p = math.cos(mxa) * mxr
    my_p = math.sin(mxa) * mxr
    if my_p < 30: continue
    height = random.uniform(20, 35)
    m_e = empty(f"mt{mi}", (mx_p, my_p, 0))
    for li in range(10):
        lz = li * (height / 10.0)
        lr = (1.0 - li/10.0) * random.uniform(15, 22)
        cyl(f"mt{mi}_{li}", r=lr, depth=height/10.0, segs=8,
            loc=(0, 0, lz + height/20.0), parent=m_e,
            mat_=M_MOUNTAIN if li < 6 else M_MOUNTAIN_MIST)
    smooth_cone(f"mt{mi}_p", r1=2, r2=0.2, depth=4, segs=8, loc=(0, 0, height),
                parent=m_e, mat_=M_MOUNTAIN_DARK)

# ============ ONE clean stone+grass ground ============
ground = beveled_cube("ground", (220, 220, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_STONE_GROUND)
# Grass + rock patches
for i in range(180):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 95)
    smooth_sphere(f"gr{i}", r=random.uniform(0.4, 1.0), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_GRASS_GW if i % 3 == 0 else M_STONE_DARK_GW,
                  scale=(1.5, 1.4, 0.22))

# ============ GREAT WALL (signature serpentine over mountains) ============
wall_segments = []
# Wall path snaking through landscape
wall_pts = []
for wi in range(30):
    wy = -50 + wi * 4
    wx = math.sin(wi * 0.3) * 12 + math.cos(wi * 0.15) * 8
    wz = abs(math.sin(wi * 0.4)) * 4  # elevation variation
    wall_pts.append((wx, wy, wz))

for wi in range(len(wall_pts) - 1):
    wx1, wy1, wz1 = wall_pts[wi]
    wx2, wy2, wz2 = wall_pts[wi+1]
    midx = (wx1 + wx2) / 2; midy = (wy1 + wy2) / 2; midz = (wz1 + wz2) / 2
    wlen = math.sqrt((wx2-wx1)**2 + (wy2-wy1)**2) + 0.3
    wang = math.atan2(wy2-wy1, wx2-wx1)
    # Wall section signature (thick + tall)
    seg = beveled_cube(f"wall{wi}", (wlen, 4, 4), bevel_offset=0.10,
                       loc=(midx, midy, midz + 2), mat_=M_WALL_STONE)
    seg.rotation_euler = (0, 0, wang)
    # Brick pattern
    for bi in range(int(wlen)):
        beveled_cube(f"w{wi}_b{bi}", (1, 4.1, 0.20), bevel_offset=0.04,
                     loc=(midx + (bi - wlen/2)*math.cos(wang), midy + (bi - wlen/2)*math.sin(wang),
                          midz + 2 + (bi % 2)*0.1), mat_=M_WALL_BRICK).rotation_euler = (0, 0, wang)
    # CRENELLATIONS signature (battlements)
    for ci in range(int(wlen/1.5)):
        cy_pos = (ci - wlen/3) * 1.5
        ccx = midx + cy_pos * math.cos(wang)
        ccy = midy + cy_pos * math.sin(wang)
        # Top crenellation
        cren = beveled_cube(f"w{wi}_cr{ci}", (1.0, 4.2, 1.2), bevel_offset=0.06,
                           loc=(ccx, ccy, midz + 4.6), mat_=M_WALL_STONE)
        cren.rotation_euler = (0, 0, wang)
    # Walkway top
    walk = beveled_cube(f"w{wi}_walk", (wlen, 3.8, 0.3), bevel_offset=0.06,
                       loc=(midx, midy, midz + 4.15), mat_=M_WALL_DARK_W)
    walk.rotation_euler = (0, 0, wang)
    wall_segments.append({"loc": (midx, midy, midz), "ang": wang})

# ============ 6 WATCH TOWERS (signature) ============
tower_positions = [(0, -40, 0), (-8, -25, 2), (5, -10, 1), (-3, 5, 3), (8, 20, 1.5), (-5, 35, 2.5)]
for ti, (tx, ty, tz) in enumerate(tower_positions):
    t_e = empty(f"tower{ti}", (tx, ty, tz))
    # Base
    beveled_cube(f"tw_b{ti}", (6, 6, 6), bevel_offset=0.15, loc=(0, 0, 3),
                 parent=t_e, mat_=M_WALL_STONE)
    # Brick pattern
    for bi in range(5):
        beveled_cube(f"tw_br{ti}_{bi}", (6.1, 6.1, 0.15), bevel_offset=0.04,
                     loc=(0, 0, 1 + bi*1.1), parent=t_e, mat_=M_WALL_BRICK)
    # Upper structure
    beveled_cube(f"tw_u{ti}", (5, 5, 3), bevel_offset=0.10, loc=(0, 0, 7.5),
                 parent=t_e, mat_=M_TOWER_RED)
    # Curved roof (signature Chinese)
    for ri in range(5):
        rw = 5.5 - ri * 0.20
        rd = 5.5 - ri * 0.20
        beveled_cube(f"tw_r{ti}_{ri}", (rw, rd, 0.30), bevel_offset=0.10,
                     loc=(0, 0, 9 + ri*0.30), parent=t_e, mat_=M_TOWER_ROOF)
    # Upturned eaves at corners (signature)
    for corner_x in (-1, 1):
        for corner_y in (-1, 1):
            corner_e = empty(f"tw_e{ti}_{corner_x}_{corner_y}",
                             (corner_x*2.7, corner_y*2.7, 9.3), parent=t_e)
            for cei in range(3):
                ca_c = cei * math.pi/6
                ce_x = corner_x * math.cos(ca_c) * 0.8
                ce_y = corner_y * math.sin(ca_c) * 0.8
                ce_z = cei * 0.30
                smooth_sphere(f"tw_eu{ti}_{corner_x}_{corner_y}_{cei}", r=0.20,
                              loc=(ce_x, ce_y, ce_z), parent=corner_e, mat_=M_TOWER_ROOF)
            # Decorative dragon on tip (signature)
            smooth_sphere(f"tw_dh{ti}_{corner_x}_{corner_y}", r=0.18,
                          loc=(corner_x*0.6, corner_y*0.6, 1), parent=corner_e,
                          mat_=M_DRAGON_GOLD, scale=(1, 1.2, 1))
    # Top spire with red lantern signature
    cyl(f"tw_s{ti}", r=0.20, depth=1.5, segs=12, loc=(0, 0, 10.5),
        parent=t_e, mat_=M_TOWER_GOLD)
    # Lantern at top
    smooth_sphere(f"tw_l{ti}", r=0.4, segs=14, rings=10, loc=(0, 0, 11.5),
                  parent=t_e, mat_=M_LANTERN_RED, scale=(1, 1, 1.2))
    # Windows
    for wi in range(3):
        wy_w = -2 + wi * 2
        beveled_cube(f"tw_w{ti}_{wi}", (0.4, 0.6, 1.2), bevel_offset=0.06,
                     loc=(2.55, wy_w, 8.0), parent=t_e, mat_=M_LANTERN_RED)
    # Door front
    beveled_cube(f"tw_d{ti}", (1.5, 0.6, 3), bevel_offset=0.10, loc=(0, -2.5, 1.5),
                 parent=t_e, mat_=M_EMPEROR_RED)

# ============ GIANT DRAGON (signature 20m serpentine) ============
dragon_e = empty("dragon", loc=(0, 0, 8))
# Body segments (20 segments serpentine)
dragon_body = []
for di in range(20):
    di_y = -15 + di * 1.5
    di_x = math.sin(di * 0.6) * 2
    di_z = math.cos(di * 0.4) * 0.8 + 2
    body_seg = empty(f"dr_seg{di}", (di_x, di_y, di_z), parent=dragon_e)
    # Body ball
    smooth_sphere(f"dr_b{di}", r=0.55 - abs(di-10)*0.012, segs=18, rings=14, loc=(0, 0, 0),
                  parent=body_seg, mat_=M_DRAGON_GOLD if di % 2 == 0 else M_DRAGON_GOLD_DEEP,
                  scale=(1.2, 1.0, 1.0))
    # Belly lighter
    smooth_sphere(f"dr_b_bel{di}", r=0.40 - abs(di-10)*0.010, loc=(0, 0, -0.15),
                  parent=body_seg, mat_=M_DRAGON_RED, scale=(1.2, 1, 0.6))
    # Spine fin (signature)
    for fi in range(3):
        beveled_cube(f"dr_fin{di}_{fi}", (0.04, 0.04, 0.15 + (fi-1)*0.03), bevel_offset=0.01,
                     loc=(0, (fi-1)*0.10, 0.50), parent=body_seg, mat_=M_DRAGON_RED)
    body_seg["_phase"] = di * 0.3
    dragon_body.append(body_seg)

# Dragon HEAD (signature)
head_dr_e = empty("dr_head", (4, 15, 5), parent=dragon_e)
head_dr_e.rotation_euler = (math.radians(-30), 0, 0)
# Skull
smooth_sphere("dr_sk", r=1.2, segs=22, rings=16, loc=(0, 0, 0),
              parent=head_dr_e, mat_=M_DRAGON_GOLD, scale=(1.3, 1.5, 1.1))
# Snout
smooth_sphere("dr_snout", r=0.8, loc=(0, 1.2, -0.20),
              parent=head_dr_e, mat_=M_DRAGON_GOLD, scale=(1, 1.3, 0.85))
# Open mouth (signature)
smooth_sphere("dr_mouth", r=0.5, loc=(0, 1.6, -0.30),
              parent=head_dr_e, mat_=M_DRAGON_RED, scale=(1.2, 0.85, 0.55))
# 10 teeth (signature)
for ti in range(10):
    cyl(f"dr_t{ti}", r=0.04, depth=0.15, segs=8,
        loc=((ti-4.5)*0.10, 1.55, -0.20), parent=head_dr_e, mat_=M_DRAGON_TEETH)
# Glowing red eyes (signature)
for side in (-1, 1):
    smooth_sphere(f"dr_eye{side}", r=0.18, loc=(side*0.45, 0.85, 0.40),
                  parent=head_dr_e, mat_=M_DRAGON_EYE)
# Eyeball detail
for side in (-1, 1):
    smooth_sphere(f"dr_pup{side}", r=0.08, loc=(side*0.45, 1.0, 0.40),
                  parent=head_dr_e, mat_=M_DRAGON_BLACK)
# 2 HORNS signature (curved up + back like deer)
for side in (-1, 1):
    horn_e = empty(f"dr_h{side}_e", (side*0.30, -0.40, 0.85), parent=head_dr_e)
    horn_e.rotation_euler = (math.radians(20), 0, math.radians(side*15))
    for hi in range(6):
        cyl(f"dr_h{side}_{hi}", r=0.12 - hi*0.012, depth=0.30, segs=10,
            loc=(0, math.sin(hi*0.5)*0.05, hi*0.30), parent=horn_e, mat_=M_DRAGON_GOLD_DEEP)
    # Pointed tip
    smooth_cone(f"dr_h{side}_tip", r1=0.06, r2=0.005, depth=0.20, segs=8,
                loc=(0, 0, 1.85), parent=horn_e, mat_=M_DRAGON_GOLD)
# WHISKERS (signature long flowing)
for side in (-1, 1):
    for wi in range(2):
        whisker_e = empty(f"dr_wh{side}_{wi}_e", (side*0.40, 1.40, -0.10 + wi*0.05), parent=head_dr_e)
        whisker_e.rotation_euler = (0, math.radians(side*-30 - wi*15), math.radians(side*60))
        for sg in range(8):
            sg_x = math.sin(sg * 0.6) * 0.10
            cyl(f"dr_w{side}_{wi}_{sg}", r=0.02, depth=0.30, segs=6,
                loc=(sg_x, sg*0.30, 0), parent=whisker_e, mat_=M_DRAGON_WHISKER)
# Beard tuft below chin
for bi in range(8):
    smooth_sphere(f"dr_bd{bi}", r=0.05, loc=((bi-4)*0.04, 1.5, -0.55 - (bi%2)*0.10),
                  parent=head_dr_e, mat_=M_DRAGON_WHISKER)
# Mane around head (signature)
for mi in range(15):
    ma = (mi / 15.0) * math.pi * 2
    smooth_sphere(f"dr_mn{mi}", r=0.18,
                  loc=(math.cos(ma)*0.85, -0.40 + math.sin(ma)*0.20, math.sin(ma)*0.85),
                  parent=head_dr_e, mat_=M_DRAGON_RED)
# Nose pearl signature
smooth_sphere("dr_pearl", r=0.15, loc=(0, 1.95, 0.10),
              parent=head_dr_e, mat_=M_DRAGON_TEETH)

# Dragon TAIL (signature pointed end)
tail_dr_e = empty("dr_tail", (-2, -16, 1.5), parent=dragon_e)
tail_dr_e.rotation_euler = (math.radians(30), 0, math.radians(20))
# Tail tapering
for ti2 in range(5):
    cyl(f"dr_tl{ti2}", r=0.30 - ti2*0.05, depth=0.45, segs=12,
        loc=(0, -ti2*0.4, 0), parent=tail_dr_e, mat_=M_DRAGON_GOLD)
# Pointed tip
smooth_cone("dr_tl_tip", r1=0.05, r2=0.005, depth=0.40, segs=8,
            loc=(0, -2.2, 0), parent=tail_dr_e, mat_=M_DRAGON_GOLD)
# Tail fin (signature)
beveled_cube("dr_tl_f", (0.20, 0.10, 0.50), bevel_offset=0.04, loc=(0, -2.3, 0.30),
             parent=tail_dr_e, mat_=M_DRAGON_RED)

# Dragon CLAWS (4 sets along body)
for ci in range(4):
    cy_c = -10 + ci * 6
    for side in (-1, 1):
        claw_e = empty(f"dr_claw{ci}_{side}", (side*0.5, cy_c, 1.0), parent=dragon_e)
        claw_e.rotation_euler = (math.radians(side*30), 0, math.radians(side*-30))
        # Arm
        cyl(f"dr_clawA{ci}_{side}", r=0.10, depth=0.40, segs=10, loc=(0, 0, -0.20),
            parent=claw_e, mat_=M_DRAGON_GOLD)
        # Hand
        smooth_sphere(f"dr_clawH{ci}_{side}", r=0.15, loc=(0, 0, -0.45),
                      parent=claw_e, mat_=M_DRAGON_GOLD)
        # 4 talons
        for tli in range(4):
            tla = (tli / 4.0) * math.pi * 2
            smooth_cone(f"dr_tl{ci}_{side}_{tli}", r1=0.03, r2=0.005, depth=0.15, segs=6,
                        loc=(math.cos(tla)*0.10, math.sin(tla)*0.10, -0.55),
                        parent=claw_e, mat_=M_DRAGON_BLACK)

# 6 DRAGON DANCERS underneath (signature)
def make_dragon_dancer(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Red outfit
    smooth_cone(f"{name}_body", r1=0.30*scale, r2=0.32*scale, depth=0.7*scale, segs=14,
                loc=(0, 0, 1.30*scale), parent=base, mat_=M_EMPEROR_RED)
    # Yellow sash
    cyl(f"{name}_sash", r=0.33*scale, depth=0.10*scale, segs=14, loc=(0, 0, 1.05*scale),
        parent=base, mat_=M_EMPEROR_GOLD)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.10*scale, depth=0.95*scale, segs=10,
            loc=(side*0.13*scale, 0, 0.47*scale), parent=base, mat_=M_EMPEROR_BLACK)
    # Arms raised (signature holding dragon poles)
    for side in (-1, 1):
        sh = empty(f"{name}_sh{side}", (side*0.30*scale, 0, 1.65*scale), parent=base)
        sh.rotation_euler = (math.radians(-160), 0, math.radians(side*-15))
        cyl(f"{name}_uarm{side}", r=0.06*scale, depth=0.40*scale, segs=10,
            loc=(0, 0, -0.20*scale), parent=sh, mat_=M_EMPEROR_RED)
        cyl(f"{name}_fa{side}", r=0.05*scale, depth=0.35*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_ASIAN)
        # Pole holding dragon (signature)
        cyl(f"{name}_pole{side}", r=0.04*scale, depth=2.0*scale, segs=8,
            loc=(0, 0, -1.5*scale), parent=sh, mat_=M_BOW_WOOD)
    # Head
    head_d_e = empty(f"{name}_he", (0, 0, 1.95*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_d_e, mat_=M_SKIN_ASIAN)
    # Hair black
    for hi in range(8):
        ha = (hi / 8.0) * math.pi * 2
        smooth_sphere(f"{name}_hr{hi}", r=0.05*scale,
                      loc=(math.cos(ha)*0.15*scale, math.sin(ha)*0.10*scale, 0.10*scale),
                      parent=head_d_e, mat_=M_HAIR_BLACK_C)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025*scale, loc=(side*0.06*scale, -0.15*scale, 0.03*scale),
                      parent=head_d_e, mat_=M_EYE_DARK_C)
    # Red headband signature
    cyl(f"{name}_band", r=0.19*scale, depth=0.08*scale, segs=14, loc=(0, 0, 0.10*scale),
        parent=head_d_e, mat_=M_EMPEROR_RED)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base}

dragon_dancers = []
for di in range(6):
    dy_d = -12 + di * 5
    dd = make_dragon_dancer(f"dd{di}", (math.sin(di*0.6)*2, dy_d, 0), scale=1.0,
                             facing=math.radians(90))
    dragon_dancers.append(dd)

# ============ EMPEROR on platform (signature) ============
emperor_e = empty("emperor", loc=(0, 40, 0))
# Stone platform
for li in range(3):
    lw = 8 - li * 1.0
    beveled_cube(f"emp_p{li}", (lw, lw, 0.5), bevel_offset=0.08, loc=(0, 0, 0.25 + li*0.5),
                 parent=emperor_e, mat_=M_WALL_STONE)
# Red carpet leading
beveled_cube("emp_carpet", (3, 8, 0.10), bevel_offset=0.04, loc=(0, -3, 1.55),
             parent=emperor_e, mat_=M_EMPEROR_RED)
# Throne signature
beveled_cube("emp_th_seat", (2.5, 2, 0.4), bevel_offset=0.06, loc=(0, 0.5, 2.0),
             parent=emperor_e, mat_=M_TOWER_GOLD)
beveled_cube("emp_th_back", (2.5, 0.3, 3), bevel_offset=0.06, loc=(0, 1.5, 3.5),
             parent=emperor_e, mat_=M_TOWER_GOLD)
# Dragon decorations on throne
for ti in range(5):
    smooth_sphere(f"emp_th_d{ti}", r=0.15,
                  loc=(-1 + ti*0.5, 1.65, 4.5), parent=emperor_e, mat_=M_DRAGON_GOLD)

# Emperor figure
emp_e = empty("emp_f", (0, 0.5, 2.4), parent=emperor_e)
# Royal robe gold with dragon pattern
smooth_cone("emp_r_b", r1=0.55, r2=0.45, depth=1.4, segs=14, loc=(0, 0, 0.7),
            parent=emp_e, mat_=M_EMPEROR_GOLD)
# Dragon pattern on robe (signature)
for di in range(8):
    da = (di / 8.0) * math.pi * 2
    beveled_cube(f"emp_drp{di}", (0.10, 0.10, 1.2), bevel_offset=0.02,
                 loc=(math.cos(da)*0.50, math.sin(da)*0.50, 0.7),
                 parent=emp_e, mat_=M_DRAGON_ROBE_PATTERN)
# Gold belt
cyl("emp_belt", r=0.50, depth=0.10, segs=18, loc=(0, 0, 0.95),
    parent=emp_e, mat_=M_DRAGON_GOLD_DEEP)
# Arms
for side in (-1, 1):
    sh = empty(f"emp_sh{side}", (side*0.45, 0, 1.30), parent=emp_e)
    sh.rotation_euler = (math.radians(-90 + side*15), 0, math.radians(side*-20))
    cyl(f"emp_uarm{side}", r=0.08, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh, mat_=M_EMPEROR_GOLD)
    cyl(f"emp_fa{side}", r=0.07, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh, mat_=M_SKIN_ASIAN)
# Head
emp_head_e = empty("emp_he", (0, 0, 1.65), parent=emp_e)
smooth_sphere("emp_head", r=0.20, segs=18, rings=14, loc=(0, 0, 0),
              parent=emp_head_e, mat_=M_SKIN_ASIAN)
# Long grey beard (signature emperor)
for bi in range(12):
    ba = (bi / 12.0) * math.pi - math.pi/2
    smooth_sphere(f"emp_bd{bi}", r=0.05,
                  loc=(math.sin(ba)*0.13, -0.16, -0.10 - (bi%3)*0.10),
                  parent=emp_head_e, mat_=M_HAIR_GREY_C)
# Long moustache
for side in (-1, 1):
    for mi in range(4):
        smooth_sphere(f"emp_mou{side}_{mi}", r=0.03,
                      loc=(side*0.06, -0.17, -0.06 - mi*0.05),
                      parent=emp_head_e, mat_=M_HAIR_GREY_C)
# Eyes
for side in (-1, 1):
    smooth_sphere(f"emp_eye{side}", r=0.03, loc=(side*0.07, -0.16, 0.03),
                  parent=emp_head_e, mat_=M_EYE_DARK_C)
# IMPERIAL CROWN signature (mianguan with beads)
crown_e = empty("emp_cr", (0, 0, 0.25), parent=emp_head_e)
# Flat top board
beveled_cube("emp_cr_t", (0.40, 0.50, 0.06), bevel_offset=0.02, loc=(0, 0, 0.10),
             parent=crown_e, mat_=M_EMPEROR_BLACK)
# Hanging strings of beads front + back (signature mianguan)
for fi in range(5):
    for si in (-0.18, 0.18):
        # String
        cyl(f"emp_str_f{fi}_{si}", r=0.005, depth=0.40, segs=4,
            loc=((fi-2)*0.06, si, 0.0), parent=crown_e, mat_=M_DRAGON_GOLD)
        # 5 beads on each string
        for bi in range(5):
            smooth_sphere(f"emp_be_{fi}_{si}_{bi}", r=0.02,
                          loc=((fi-2)*0.06, si, -0.05 - bi*0.07),
                          parent=crown_e, mat_=M_DRAGON_GOLD_DEEP)
# Center bun
smooth_sphere("emp_bun", r=0.10, loc=(0, 0, 0.15), parent=crown_e, mat_=M_EMPEROR_BLACK)

# ============ 4 ARCHERS soldiers (signature) ============
def make_archer(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body armor red
    smooth_cone(f"{name}_body", r1=0.32, r2=0.34, depth=0.65, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=M_SOLDIER_RED)
    # Armor plates (signature)
    for ai in range(4):
        cyl(f"{name}_ap{ai}", r=0.35, depth=0.10, segs=18, loc=(0, 0, 1.10 + ai*0.16),
            parent=base, mat_=M_SOLDIER_GOLD)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.11, depth=0.95, segs=10,
            loc=(side*0.13, 0, 0.47), parent=base, mat_=M_SOLDIER_BLACK)
    # Boots
    for side in (-1, 1):
        beveled_cube(f"{name}_bt{side}", (0.12, 0.22, 0.10), bevel_offset=0.02,
                     loc=(side*0.13, 0, 0), parent=base, mat_=M_SOLDIER_BLACK)
    # Arms holding bow
    sh_r = empty(f"{name}_sh_r", (0.30, -0.10, 1.65), parent=base)
    sh_r.rotation_euler = (math.radians(-80), 0, math.radians(-30))
    cyl(f"{name}_ua_r", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_r, mat_=M_SOLDIER_RED)
    cyl(f"{name}_fa_r", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_r, mat_=M_SKIN_ASIAN)
    sh_l = empty(f"{name}_sh_l", (-0.30, -0.20, 1.65), parent=base)
    sh_l.rotation_euler = (math.radians(-100), 0, math.radians(20))
    cyl(f"{name}_ua_l", r=0.07, depth=0.40, segs=10, loc=(0, 0, -0.20),
        parent=sh_l, mat_=M_SOLDIER_RED)
    cyl(f"{name}_fa_l", r=0.06, depth=0.35, segs=10, loc=(0, 0, -0.55),
        parent=sh_l, mat_=M_SKIN_ASIAN)
    # BOW signature (Chinese recurve)
    bow_e = empty(f"{name}_bow", (-0.7, -0.40, 1.0), parent=base)
    bow_e.rotation_euler = (math.radians(90), 0, 0)
    for bi in range(11):
        ba = math.pi * bi / 10.0
        bx_b = math.cos(ba) * 0.7
        bz_b = math.sin(ba) * 0.5 - 0.25
        cyl(f"{name}_b{bi}", r=0.03, depth=0.20, segs=8,
            loc=(bx_b, 0, bz_b), parent=bow_e, mat_=M_BOW_WOOD)
    # String
    cyl(f"{name}_str", r=0.005, depth=1.0, segs=6, loc=(0, 0, -0.25),
        parent=bow_e, mat_=M_BOW_STRING_C)
    # Arrow nocked
    cyl(f"{name}_arr", r=0.012, depth=0.8, segs=6, loc=(0.10, 0, -0.25),
        parent=bow_e, mat_=M_ARROW_C).rotation_euler = (0, math.radians(90), 0)
    # Arrowhead
    smooth_cone(f"{name}_arrh", r1=0.03, r2=0.005, depth=0.08, segs=6,
                loc=(0.5, 0, -0.25), parent=bow_e, mat_=M_SOLDIER_GOLD).rotation_euler = (0, math.radians(90), 0)
    # Feathers
    for ff in range(3):
        fa = (ff / 3.0) * math.pi * 2
        beveled_cube(f"{name}_arf{ff}", (0.04, 0.10, 0.04), bevel_offset=0.005,
                     loc=(-0.30, math.cos(fa)*0.02, -0.25 + math.sin(fa)*0.02),
                     parent=bow_e, mat_=M_ARROW_FEATHER)
    # Head + helmet
    head_a_e = empty(f"{name}_he", (0, 0, 2.0), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_a_e, mat_=M_SKIN_ASIAN)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_a_e, mat_=M_EYE_DARK_C)
    # CONICAL HELMET (signature)
    helmet_e = empty(f"{name}_helm", (0, 0, 0.20), parent=head_a_e)
    smooth_cone(f"{name}_h_b", r1=0.22, r2=0.05, depth=0.35, segs=14, loc=(0, 0, 0.18),
                parent=helmet_e, mat_=M_SOLDIER_GOLD)
    # Brim
    cyl(f"{name}_h_brim", r=0.24, depth=0.04, segs=14, loc=(0, 0, 0),
        parent=helmet_e, mat_=M_SOLDIER_RED)
    # Red plume
    smooth_cone(f"{name}_plume", r1=0.05, r2=0.005, depth=0.40, segs=8,
                loc=(0, 0, 0.55), parent=helmet_e, mat_=M_EMPEROR_RED)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_a_e}

archers = []
arch_pos = [(-8, 38, 0, math.radians(0)), (8, 38, 0, math.radians(0)),
             (-5, 43, 0, math.radians(0)), (5, 43, 0, math.radians(0))]
for i, (ax, ay, az, fac) in enumerate(arch_pos):
    a = make_archer(f"archer{i}", (ax, ay, az), scale=1.0, facing=fac)
    archers.append(a)

# ============ 8 MUSICIANS drums + pi pa (signature) ============
def make_musician_c(name, loc, instrument, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Blue tunic
    smooth_cone(f"{name}_body", r1=0.32, r2=0.35, depth=0.7, segs=14, loc=(0, 0, 1.30),
                parent=base, mat_=M_MUSICIAN_BLUE)
    # Belt
    cyl(f"{name}_belt", r=0.36, depth=0.08, segs=14, loc=(0, 0, 1.0),
        parent=base, mat_=M_EMPEROR_RED)
    # Pants
    for side in (-1, 1):
        cyl(f"{name}_leg{side}", r=0.10, depth=1.0, segs=10,
            loc=(side*0.13, 0, 0.5), parent=base, mat_=M_EMPEROR_BLACK)
    # Head
    head_m_e = empty(f"{name}_he", (0, 0, 1.95), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_m_e, mat_=M_SKIN_ASIAN)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.025, loc=(side*0.06, -0.15, 0.03),
                      parent=head_m_e, mat_=M_EYE_DARK_C)
    # Hair topknot signature
    smooth_sphere(f"{name}_topknot", r=0.08, loc=(0, 0.05, 0.20),
                  parent=head_m_e, mat_=M_HAIR_BLACK_C)
    inst_e = empty(f"{name}_inst", (0, -0.30, 1.0), parent=base)
    if instrument == "drum":
        # Large barrel drum (signature)
        smooth_cone(f"{name}_d_b", r1=0.30, r2=0.30, depth=0.50, segs=18, loc=(0, 0, 0),
                    parent=inst_e, mat_=M_DRUM_RED)
        # Top skin
        cyl(f"{name}_d_t", r=0.30, depth=0.04, segs=18, loc=(0, 0, 0.27),
            parent=inst_e, mat_=M_DRUM_SKIN)
        # Gold rim
        cyl(f"{name}_d_r", r=0.32, depth=0.04, segs=20, loc=(0, 0, 0.27),
            parent=inst_e, mat_=M_DRUM_GOLD)
        # Sticks raised
        for side in (-1, 1):
            cyl(f"{name}_st{side}", r=0.018, depth=0.30, segs=8,
                loc=(side*0.10, 0, 0.55), parent=inst_e, mat_=M_BOW_WOOD)
    elif instrument == "pipa":
        # Pipa lute (signature pear-shaped)
        smooth_sphere(f"{name}_p_b", r=0.22, segs=18, rings=12, loc=(0, 0, 0),
                      parent=inst_e, mat_=M_PIPA_WOOD, scale=(0.85, 0.30, 1.2))
        # Neck
        cyl(f"{name}_p_n", r=0.025, depth=0.50, segs=10, loc=(0, -0.10, 0.40),
            parent=inst_e, mat_=M_PIPA_WOOD)
        # 4 strings
        for st in range(4):
            cyl(f"{name}_p_st{st}", r=0.003, depth=0.65, segs=6,
                loc=((st-1.5)*0.012, -0.12, 0.25),
                parent=inst_e, mat_=M_BOW_STRING_C)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "inst": inst_e, "he": head_m_e}

musicians_c = []
mus_data_c = [("drum", -12, 30), ("drum", 12, 30),
               ("pipa", -10, 32), ("pipa", 10, 32),
               ("drum", -8, 34), ("drum", 8, 34),
               ("pipa", -6, 36), ("pipa", 6, 36)]
for i, (inst, mx, my) in enumerate(mus_data_c):
    m = make_musician_c(f"mus_c{i}", (mx, my, 0), instrument=inst, scale=1.0,
                        facing=math.radians(180))
    musicians_c.append(m)

# ============ TIGER STATUES (signature stone guardians) ============
def make_tiger(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Pedestal
    beveled_cube(f"{name}_ped", (1.5, 1.0, 0.6), bevel_offset=0.08, loc=(0, 0, 0.3),
                 parent=base, mat_=M_WALL_DARK_W)
    # Body sitting (signature)
    smooth_sphere(f"{name}_body", r=0.55, segs=20, rings=14, loc=(0, 0, 1.1),
                  parent=base, mat_=M_TIGER_STONE, scale=(1, 1.2, 1.3))
    # Front legs
    for side in (-1, 1):
        cyl(f"{name}_fl{side}", r=0.15, depth=0.60, segs=10,
            loc=(side*0.25, -0.30, 0.90), parent=base, mat_=M_TIGER_STONE)
    # Paws
    for side in (-1, 1):
        smooth_sphere(f"{name}_p{side}", r=0.15, loc=(side*0.25, -0.30, 0.65),
                      parent=base, mat_=M_TIGER_STONE, scale=(1, 1.3, 0.7))
    # Head
    head_t_e = empty(f"{name}_he", (0, -0.4, 1.5), parent=base)
    smooth_sphere(f"{name}_head", r=0.35, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_t_e, mat_=M_TIGER_STONE, scale=(1.2, 1.0, 1.0))
    # Open mouth (signature roaring)
    smooth_sphere(f"{name}_mouth", r=0.20, loc=(0, -0.20, -0.10),
                  parent=head_t_e, mat_=M_EMPEROR_RED, scale=(1.3, 0.7, 0.5))
    # Teeth
    for ti in range(6):
        beveled_cube(f"{name}_t{ti}", (0.03, 0.04, 0.10), bevel_offset=0.005,
                     loc=((ti-2.5)*0.05, -0.22, -0.05), parent=head_t_e, mat_=M_DRAGON_TEETH)
    # Eyes glowing red
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.06, loc=(side*0.15, -0.25, 0.10),
                      parent=head_t_e, mat_=M_DRAGON_EYE)
    # Ears small
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.10, loc=(-0.05, side*0.20, 0.20),
                      parent=head_t_e, mat_=M_TIGER_STONE, scale=(0.5, 1, 1.2))
    # Moss patches
    for mi in range(5):
        smooth_sphere(f"{name}_m{mi}", r=0.12, loc=(random.uniform(-0.4, 0.4),
                                                      random.uniform(-0.3, 0.3),
                                                      random.uniform(0.7, 1.4)),
                      parent=base, mat_=M_TIGER_MOSS, scale=(1, 1, 0.3))
    return base

tigers = []
for side in (-1, 1):
    t = make_tiger(f"tiger_{side}", (side*8, 30, 0), scale=1.0, facing=math.radians(0))
    tigers.append(t)

# ============ FLAGS (signature red with star) ============
flags = []
for fi in range(6):
    fx = -25 + fi * 10
    fy = -45
    flag_e = empty(f"flag{fi}", (fx, fy, 0))
    # Pole
    cyl(f"fl_p{fi}", r=0.06, depth=8, segs=10, loc=(0, 0, 4), parent=flag_e, mat_=M_EMPEROR_BLACK)
    # Top finial
    smooth_sphere(f"fl_t{fi}", r=0.10, loc=(0, 0, 8), parent=flag_e, mat_=M_TOWER_GOLD)
    # Flag fabric red
    beveled_cube(f"fl_f{fi}", (2, 0.05, 1.5), bevel_offset=0.04, loc=(1, 0, 7),
                 parent=flag_e, mat_=M_FLAG_RED)
    # Yellow star signature
    smooth_sphere(f"fl_s{fi}", r=0.20, loc=(1, -0.04, 7),
                  parent=flag_e, mat_=M_FLAG_STAR, scale=(1, 0.1, 1))
    # 4 smaller stars
    for si in range(4):
        sa = (si / 4.0) * math.pi
        smooth_sphere(f"fl_ss{fi}_{si}", r=0.08,
                      loc=(1 + math.cos(sa)*0.4, -0.04, 7 + math.sin(sa)*0.4),
                      parent=flag_e, mat_=M_FLAG_STAR)
    flag_e["_phase"] = random.uniform(0, math.pi*2)
    flags.append(flag_e)

# ============================================================
# ⭐ 600 RED LANTERNS + 400 PEONY PETALS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
rising_lanterns = []
for i in range(600):
    px = random.uniform(-60, 60)
    py = random.uniform(-60, 60)
    pz = random.uniform(1, 25)
    lan_e = empty(f"rl{i}", (px, py, pz))
    # Red lantern body
    smooth_sphere(f"rl_b{i}", r=random.uniform(0.15, 0.25), segs=14, rings=10,
                  loc=(0, 0, 0), parent=lan_e, mat_=M_LANTERN_RED, scale=(1, 1, 1.25))
    # Top frame
    cyl(f"rl_t{i}", r=0.08, depth=0.03, segs=10, loc=(0, 0, 0.18),
        parent=lan_e, mat_=M_LANTERN_FRAME)
    cyl(f"rl_bt{i}", r=0.08, depth=0.03, segs=10, loc=(0, 0, -0.18),
        parent=lan_e, mat_=M_LANTERN_FRAME)
    # Tassel
    cyl(f"rl_ts{i}", r=0.015, depth=0.10, segs=6, loc=(0, 0, -0.28),
        parent=lan_e, mat_=M_LANTERN_TASSEL)
    lan_e["_phase"] = random.uniform(0, math.pi*2)
    lan_e["_base_x"] = px; lan_e["_base_y"] = py; lan_e["_base_z"] = pz
    lan_e["_amp_x"] = random.uniform(0.5, 1.5)
    lan_e["_amp_y"] = random.uniform(0.5, 1.5)
    lan_e["_speed"] = random.uniform(0.3, 0.8)
    lan_e["_rise"] = random.uniform(0.5, 1.5)
    rising_lanterns.append(lan_e)

# 400 peony petals
peonies = []
for i in range(400):
    px = random.uniform(-50, 50)
    py = random.uniform(-50, 50)
    pz = random.uniform(2, 18)
    p_obj = smooth_sphere(f"po{i}", r=random.uniform(0.07, 0.10), segs=8, rings=6,
                          loc=(px, py, pz), mat_=random.choice(PEONY_COLORS),
                          scale=(1.4, 0.6, 0.3))
    p_obj["_phase"] = random.uniform(0, math.pi*2)
    p_obj["_base_x"] = px; p_obj["_base_y"] = py; p_obj["_base_z"] = pz
    p_obj["_amp_x"] = random.uniform(1.0, 2.5)
    p_obj["_amp_y"] = random.uniform(1.0, 2.5)
    p_obj["_speed"] = random.uniform(0.5, 1.0)
    p_obj["_fall"] = random.uniform(1.0, 2.5)
    peonies.append(p_obj)

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
        cloud.location.x = bx_c + math.sin(t * 0.3 + phase) * 3.0
        cloud.location.y = by_c + math.cos(t * 0.3 + phase) * 3.0
        cloud.keyframe_insert("location", frame=f)

# DRAGON undulates (signature wave motion)
for di in range(20):
    seg = dragon_body[di]
    phase = seg["_phase"]
    bx_s = seg.location.x; by_s = seg.location.y; bz_s = seg.location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Propagated wave motion
        seg.location.x = bx_s + math.sin(t * 2.0 + phase) * 1.5
        seg.location.z = bz_s + math.cos(t * 2.0 + phase) * 1.0
        seg.rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(15),
                                math.cos(t * 2.0 + phase) * math.radians(10), 0)
        seg.keyframe_insert("location", frame=f)
        seg.keyframe_insert("rotation_euler", frame=f)

# Dragon head with motion
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    head_dr_e.rotation_euler = (math.radians(-30) + math.sin(t * 1.5) * math.radians(8), 0,
                                  math.cos(t * 1.5) * math.radians(10))
    head_dr_e.keyframe_insert("rotation_euler", frame=f)

# Dragon dancers running underneath
for dd in dragon_dancers:
    phase = dd["root"]["_phase"]
    bx_d = dd["root"].location.x; by_d = dd["root"].location.y
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        dd["root"].location.x = bx_d + math.sin(t * 2.0 + phase) * 1.0
        dd["root"].location.y = by_d + math.cos(t * 2.0 + phase) * 0.5
        dd["root"].location.z = abs(math.sin(t * 4.0 + phase)) * 0.3
        dd["root"].keyframe_insert("location", frame=f)

# Emperor ceremonial slow nod
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    emp_head_e.rotation_euler = (math.sin(t * 0.5) * math.radians(5), 0,
                                   math.cos(t * 0.4) * math.radians(8))
    emp_head_e.keyframe_insert("rotation_euler", frame=f)

# Archers tense aiming + slight motion
for a in archers:
    phase = a["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        a["he"].rotation_euler = (0, 0, math.sin(t * 0.6 + phase) * math.radians(10))
        a["he"].keyframe_insert("rotation_euler", frame=f)

# Musicians rhythmic
for mu in musicians_c:
    phase = mu["root"]["_phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        mu["root"].rotation_euler = (math.sin(t * 4.0 + phase) * math.radians(5), 0,
                                       mu["root"].rotation_euler.z)
        mu["root"].keyframe_insert("rotation_euler", frame=f)
        sc_i = 1 + math.sin(t * 8.0 + phase) * 0.05
        mu["inst"].scale = (sc_i, sc_i, sc_i)
        mu["inst"].keyframe_insert("scale", frame=f)

# Flags wave
for fl in flags:
    phase = fl["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        fl.rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(10))
        fl.keyframe_insert("rotation_euler", frame=f)

# 600 red lanterns rising (signature)
for l in rising_lanterns:
    phase = l["_phase"]; speed = l["_speed"]; rise = l["_rise"]
    bx, by, bz = l["_base_x"], l["_base_y"], l["_base_z"]
    ax, ay = l["_amp_x"], l["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase) * 0.3
        y = by + ay * math.cos(t * speed * 0.9 + phase) * 0.3
        z = bz + t * rise
        l.location = (x, y, z)
        l.rotation_euler = (math.sin(t * speed + phase) * math.radians(5),
                             math.cos(t * speed + phase) * math.radians(5), 0)
        l.keyframe_insert("location", frame=f)
        l.keyframe_insert("rotation_euler", frame=f)

# 400 peony petals falling
for p in peonies:
    phase = p["_phase"]; speed = p["_speed"]; fall = p["_fall"]
    bx, by, bz = p["_base_x"], p["_base_y"], p["_base_z"]
    ax, ay = p["_amp_x"], p["_amp_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz - (t * fall) % (bz - 0.5)
        if z < 0.5: z = bz
        p.location = (x, y, max(0.3, z))
        p.rotation_euler = (t * 2.5 + phase, t * 2.0 + phase, t * 3.0 + phase)
        p.keyframe_insert("location", frame=f)
        p.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_china_wall_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_chinese_great_wall_dragon] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_chinese_great_wall_dragon] Great Wall serpentine 30 segments + 6 watchtowers + 10 mountains + GIANT GOLDEN DRAGON 20m signature serpentine + horns + whiskers + claws + 6 dragon dancers + emperor mianguan crown + throne + 4 archers + 8 musicians drums+pipa + 2 tigers stone + 6 flags + 600 rising lanterns + 400 peonies")
print("⭐ FIXES: 1 ground + 600 red lanterns + 400 peony petals (signature China mandatory) ⭐")
