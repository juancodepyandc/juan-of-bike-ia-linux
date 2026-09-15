"""
proc_steampunk_railway_station.py — 197e procédural AuroraIA (61e qualité)
Gare steampunk vapeur : verrière fer + 3 quais + locomotive 4 essieux + 6 wagons + 30 voyageurs + chef + lampadaires gaz + télégraphe + horloge
"""
import bpy, bmesh, math, random, os

random.seed(0x57411197)

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

# Materials
M_SKY = mat("sky", (0.55, 0.30, 0.18, 1.0), 0.0, 0.7, emission=(0.65,0.35,0.20), emission_strength=1.5)
M_SUN_HALO = mat("sun_halo", (1.0, 0.65, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.70,0.35), emission_strength=10.0)
M_GROUND = mat("ground", (0.25, 0.20, 0.18, 1.0), 0.0, 0.80)
M_PLATFORM = mat("platform", (0.45, 0.40, 0.35, 1.0), 0.0, 0.70, emission=(0.40,0.35,0.30), emission_strength=0.3)
M_PLATFORM_EDGE = mat("platform_edge", (0.85, 0.75, 0.30, 1.0), 0.6, 0.35, emission=(0.78,0.68,0.28), emission_strength=0.5)

M_IRON = mat("iron", (0.15, 0.12, 0.10, 1.0), 0.85, 0.45, emission=(0.12,0.10,0.08), emission_strength=0.3)
M_IRON_DARK = mat("iron_dark", (0.08, 0.06, 0.05, 1.0), 0.85, 0.50)
M_BRASS = mat("brass", (0.85, 0.65, 0.25, 1.0), 0.92, 0.20, emission=(0.78,0.58,0.22), emission_strength=0.7)
M_COPPER = mat("copper", (0.85, 0.45, 0.20, 1.0), 0.88, 0.30, emission=(0.78,0.40,0.18), emission_strength=0.6)
M_STEEL = mat("steel", (0.55, 0.55, 0.58, 1.0), 0.90, 0.30, emission=(0.45,0.45,0.50), emission_strength=0.3)
M_GLASS = mat("glass", (0.75, 0.85, 0.95, 0.4), 0.0, 0.05, emission=(0.65,0.78,0.88), emission_strength=1.5, alpha=0.4)
M_GLASS_LIT = mat("glass_lit", (1.0, 0.78, 0.40, 1.0), 0.0, 0.05, emission=(1.0,0.75,0.40), emission_strength=8.0)
M_WOOD = mat("wood", (0.35, 0.20, 0.10, 1.0), 0.0, 0.75)
M_WOOD_RICH = mat("wood_rich", (0.45, 0.25, 0.15, 1.0), 0.0, 0.55, emission=(0.40,0.22,0.12), emission_strength=0.3)

# Locomotive
M_LOCO_BLACK = mat("loco_black", (0.08, 0.06, 0.05, 1.0), 0.6, 0.35, emission=(0.10,0.08,0.06), emission_strength=0.4)
M_LOCO_RED = mat("loco_red", (0.65, 0.10, 0.10, 1.0), 0.4, 0.40, emission=(0.55,0.10,0.08), emission_strength=0.5)
M_LOCO_GOLD = mat("loco_gold", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.85,0.70,0.28), emission_strength=0.9)
M_WHEEL = mat("wheel", (0.15, 0.12, 0.10, 1.0), 0.85, 0.45, emission=(0.18,0.15,0.12), emission_strength=0.3)
M_WHEEL_RIM = mat("wheel_rim", (0.55, 0.55, 0.55, 1.0), 0.90, 0.30, emission=(0.50,0.50,0.50), emission_strength=0.4)
M_FIREBOX = mat("firebox", (1.0, 0.55, 0.15, 1.0), 0.0, 0.10, emission=(1.0,0.60,0.20), emission_strength=18.0)
M_HEADLAMP = mat("headlamp", (1.0, 0.95, 0.65, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.65), emission_strength=20.0)

# Wagon
M_WAGON_GREEN = mat("wagon_green", (0.15, 0.35, 0.20, 1.0), 0.4, 0.45, emission=(0.12,0.30,0.18), emission_strength=0.4)
M_WAGON_BROWN = mat("wagon_brown", (0.45, 0.28, 0.18, 1.0), 0.3, 0.50, emission=(0.40,0.25,0.15), emission_strength=0.3)
M_WAGON_BLUE = mat("wagon_blue", (0.18, 0.30, 0.55, 1.0), 0.4, 0.45, emission=(0.15,0.25,0.48), emission_strength=0.4)

# Smoke
M_SMOKE_THICK = mat("smoke_thick", (0.45, 0.40, 0.38, 1.0), 0.0, 0.85, emission=(0.40,0.35,0.32), emission_strength=0.6, alpha=0.6)
M_SMOKE_LIGHT = mat("smoke_light", (0.65, 0.60, 0.55, 1.0), 0.0, 0.85, emission=(0.55,0.50,0.45), emission_strength=0.4, alpha=0.4)
M_STEAM = mat("steam", (0.92, 0.95, 1.0, 1.0), 0.0, 0.30, emission=(0.85,0.88,0.95), emission_strength=1.5, alpha=0.5)

# People
M_SKIN_L = mat("skin_l", (0.92, 0.78, 0.65, 1.0), 0.0, 0.55, emission=(0.82,0.70,0.58), emission_strength=0.25)
M_SKIN_D = mat("skin_d", (0.65, 0.48, 0.32, 1.0), 0.0, 0.6, emission=(0.55,0.40,0.28), emission_strength=0.25)
M_COAT_DARK = mat("coat_dark", (0.18, 0.15, 0.18, 1.0), 0.0, 0.65, emission=(0.15,0.12,0.15), emission_strength=0.3)
M_COAT_BROWN = mat("coat_brown", (0.35, 0.22, 0.15, 1.0), 0.0, 0.60, emission=(0.30,0.20,0.13), emission_strength=0.3)
M_COAT_RED = mat("coat_red", (0.55, 0.15, 0.15, 1.0), 0.0, 0.55, emission=(0.48,0.13,0.13), emission_strength=0.4)
M_DRESS = mat("dress", (0.55, 0.30, 0.45, 1.0), 0.0, 0.55, emission=(0.50,0.28,0.42), emission_strength=0.4)
M_DRESS_BLUE = mat("dress_blue", (0.20, 0.35, 0.60, 1.0), 0.0, 0.55, emission=(0.18,0.32,0.55), emission_strength=0.4)
M_HAT_TOP = mat("hat_top", (0.05, 0.05, 0.05, 1.0), 0.4, 0.45)
M_HAT_BOWLER = mat("hat_bowler", (0.25, 0.15, 0.10, 1.0), 0.0, 0.65)
M_BONNET = mat("bonnet", (0.85, 0.55, 0.70, 1.0), 0.0, 0.55, emission=(0.75,0.50,0.62), emission_strength=0.4)
M_HAIR = mat("hair", (0.20, 0.12, 0.08, 1.0), 0.0, 0.80)
M_HAIR_BLOND = mat("hair_blond", (0.85, 0.65, 0.30, 1.0), 0.0, 0.70, emission=(0.80,0.60,0.28), emission_strength=0.3)
M_MOUCHOIR = mat("mouchoir", (1.0, 0.95, 0.92, 1.0), 0.0, 0.50, emission=(0.95,0.92,0.88), emission_strength=0.5)
M_GAS_FLAME = mat("gas_flame", (1.0, 0.75, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.80,0.35), emission_strength=14.0)
M_GAS_INNER = mat("gas_inner", (1.0, 0.92, 0.55, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.65), emission_strength=20.0)
M_LAMP_GLOBE = mat("lamp_globe", (1.0, 0.85, 0.55, 0.7), 0.0, 0.10, emission=(1.0,0.85,0.55), emission_strength=10.0, alpha=0.7)
M_SUITCASE = mat("suitcase", (0.40, 0.25, 0.15, 1.0), 0.0, 0.55, emission=(0.35,0.22,0.13), emission_strength=0.3)
M_SUITCASE_HANDLE = mat("suitcase_h", (0.18, 0.10, 0.08, 1.0), 0.3, 0.55)
M_PAPER = mat("paper", (0.95, 0.88, 0.72, 1.0), 0.0, 0.65, emission=(0.85,0.80,0.65), emission_strength=0.4)
M_TELEGRAPH = mat("telegraph", (0.45, 0.30, 0.18, 1.0), 0.5, 0.40, emission=(0.40,0.28,0.16), emission_strength=0.5)
M_AIRSHIP = mat("airship", (0.65, 0.50, 0.35, 1.0), 0.0, 0.60, emission=(0.55,0.45,0.32), emission_strength=0.5)
M_AIRSHIP_GONDOLA = mat("airship_gond", (0.45, 0.28, 0.15, 1.0), 0.3, 0.50)

# ============ SKY + SUN ============
sky = smooth_sphere("sky", r=90, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.6))
sky.scale = (1,1,0.6)
# Sun (low, industrial orange)
sun = smooth_sphere("sun", r=4.5, loc=(0, 40, 18), mat_=M_SUN_HALO)
# 3 sun halos
for i in range(3):
    halo = smooth_sphere(f"sun_halo{i}", r=4.5 + i*1.5, loc=(0, 40, 18),
                        mat_=M_SUN_HALO, scale=(1,1,1))
    halo["_phase"] = i * 0.4

# 8 industrial smoke clouds drifting
ind_smokes = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    cx, cy = 32*math.cos(a) + random.uniform(-3,3), 32*math.sin(a) + random.uniform(-3,3)
    cz = random.uniform(20, 28)
    sm_e = empty(f"ind_smoke_e{i}", (cx, cy, cz))
    for j in range(4):
        smooth_sphere(f"ind_smoke{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-2.5,2.5), random.uniform(-1.5,1.5), random.uniform(-0.5,0.5)),
                      parent=sm_e, mat_=M_SMOKE_THICK)
    sm_e["_phase"] = random.uniform(0, math.pi*2)
    ind_smokes.append(sm_e)

# ============ GROUND ============
ground = beveled_cube("ground", (60, 60, 0.4), bevel_offset=0.05, loc=(0, 0, -0.2), mat_=M_GROUND)

# ============ VERRIÈRE (FER FORGÉ + GLASS) ============
# Large arched roof structure over 3 platforms
# Main arched ribs (10 iron arches across 30m length)
station_e = empty("station", loc=(0, 0, 0))

# Floor stations
beveled_cube("station_floor", (40, 24, 0.30), bevel_offset=0.05,
             loc=(0, 0, 0.15), parent=station_e, mat_=M_PLATFORM)

# Track bays (2 sunken tracks separating 3 platforms)
for ti in range(2):
    ty = (ti - 0.5) * 6.0
    # Track depression
    beveled_cube(f"track_pit{ti}", (40, 3.0, 0.40),
                 loc=(0, ty, -0.10), parent=station_e, mat_=M_GROUND)
    # 2 rails (steel)
    for r in (-1, 1):
        cyl(f"rail{ti}_{r}", r=0.06, depth=40, segs=10,
            loc=(0, ty + r*0.65, 0.05), parent=station_e, mat_=M_STEEL).rotation_euler = (0, math.radians(90), 0)
    # Sleepers (every 1m)
    for s in range(40):
        beveled_cube(f"sleeper{ti}_{s}", (0.30, 2.0, 0.10),
                     loc=(-20 + s, ty, -0.05), parent=station_e, mat_=M_WOOD)

# 3 PLATFORMS
platform_ys = [-9, 0, 9]
for pi, py in enumerate(platform_ys):
    plat = beveled_cube(f"platform{pi}", (40, 3.5, 0.50), bevel_offset=0.05,
                       loc=(0, py, 0.25), parent=station_e, mat_=M_PLATFORM)
    # Platform yellow edge stripe
    for side in (-1, 1):
        beveled_cube(f"plat_edge{pi}_{side}", (40, 0.2, 0.10),
                     loc=(0, py + side*1.65, 0.50), parent=station_e, mat_=M_PLATFORM_EDGE)

# 10 iron arches forming verrière (curve roof)
arches = []
for ai in range(10):
    ax = (ai - 4.5) * 4.0
    arch_e = empty(f"arch_e{ai}", (ax, 0, 0), parent=station_e)
    # Left + right pillars (vertical)
    for side in (-1, 1):
        cyl(f"arch_pillar{ai}_{side}", r=0.20, depth=10, segs=12,
            loc=(0, side*11, 5), parent=arch_e, mat_=M_IRON)
        # Base footing
        beveled_cube(f"arch_base{ai}_{side}", (0.45, 0.45, 0.35), bevel_offset=0.05,
                     loc=(0, side*11, 0.20), parent=arch_e, mat_=M_IRON_DARK)
    # Arch top (curved, approximated by 8 segments forming arc)
    for j in range(8):
        t = (j - 3.5) / 7.5  # -0.5 to 0.5
        a = t * math.pi  # -pi/2 to pi/2
        seg_y = 11 * math.sin(a)
        seg_z = 10 + 4 * math.cos(a) - 4  # arc top at z=10+4=14, sides at z=10
        # Direction tangent
        prev_t = (j - 4.5) / 7.5
        prev_a = prev_t * math.pi
        py_prev = 11 * math.sin(prev_a)
        pz_prev = 10 + 4 * math.cos(prev_a) - 4
        dy = seg_y - py_prev
        dz = seg_z - pz_prev
        length = math.sqrt(dy*dy + dz*dz)
        mid_y = (seg_y + py_prev) / 2
        mid_z = (seg_z + pz_prev) / 2
        seg = cyl(f"arch_top{ai}_{j}", r=0.15, depth=max(length, 0.5), segs=10,
                 loc=(0, mid_y, mid_z), parent=arch_e, mat_=M_IRON)
        # Orient
        seg.rotation_euler = (math.atan2(dy, dz), 0, 0)
    # 6 decorative tracery elements per arch (small spheres + crosses)
    for j in range(6):
        t = (j - 2.5) / 5.5
        a = t * math.pi
        ty = 11 * math.sin(a)
        tz = 10 + 4 * math.cos(a) - 4
        smooth_sphere(f"arch_dec{ai}_{j}", r=0.18,
                      loc=(0, ty, tz - 0.5), parent=arch_e, mat_=M_BRASS)
    arches.append(arch_e)

# Glass panels between arches (8 long panels)
for gi in range(8):
    gx = (gi - 3.5) * 4.0 + 2.0
    # Top arched glass band
    for j in range(6):
        t = (j - 2.5) / 5.5
        a = t * math.pi
        ty = 11 * math.sin(a)
        tz = 10 + 4 * math.cos(a) - 4
        beveled_cube(f"glass{gi}_{j}", (3.5, 0.05, 1.8), bevel_offset=0.02,
                     loc=(gx, ty, tz - 0.5), parent=station_e, mat_=M_GLASS)

# Longitudinal beams (4 along length)
for bi, bz_off in enumerate([3, 5.5, 8, 12]):
    by = 0
    if bi < 2:
        # Side beams
        for side in (-1, 1):
            beveled_cube(f"long_beam_l{bi}_{side}", (40, 0.20, 0.30),
                         loc=(0, side*10, bz_off + 2), parent=station_e, mat_=M_IRON)
    else:
        # Center top beam
        beveled_cube(f"long_beam_c{bi}", (40, 0.20, 0.30),
                     loc=(0, by, bz_off), parent=station_e, mat_=M_IRON)

# Roof ridge (top of arch)
beveled_cube("roof_ridge", (40, 0.40, 0.40), loc=(0, 0, 14.2),
             parent=station_e, mat_=M_IRON)
# Ridge ornamental finials (5)
for i in range(5):
    smooth_cone(f"finial{i}", r1=0.20, r2=0.05, depth=0.80, segs=10,
                loc=((i-2)*8, 0, 14.85), parent=station_e, mat_=M_BRASS)

# Central station building (signature back wall)
beveled_cube("station_wall", (40, 0.5, 9.0), bevel_offset=0.05,
             loc=(0, 13, 4.5), parent=station_e, mat_=M_WOOD_RICH)
# Big windows in wall
for wi in range(8):
    wx = (wi - 3.5) * 4.5
    beveled_cube(f"wall_win{wi}", (3.5, 0.5, 4.0), bevel_offset=0.05,
                 loc=(wx, 12.9, 4.0), parent=station_e, mat_=M_GLASS_LIT)

# Central station building TOWER
tower_e = empty("tower", (0, 13.5, 9), parent=station_e)
beveled_cube("tower_body", (5.0, 3.5, 8.0), bevel_offset=0.05,
             loc=(0, 0, 4.0), parent=tower_e, mat_=M_WOOD_RICH)
# Tower windows
for wi in range(3):
    beveled_cube(f"tower_win{wi}", (1.0, 3.7, 1.4), bevel_offset=0.03,
                 loc=((wi-1)*1.5, 0, 5.5), parent=tower_e, mat_=M_GLASS_LIT)
# Tower roof (pyramidal)
smooth_cone("tower_roof", r1=3.5, r2=0.3, depth=2.5, segs=14,
            loc=(0, 0, 9.3), parent=tower_e, mat_=M_IRON_DARK)
# Tower finial + ball
smooth_sphere("tower_orb", r=0.30, loc=(0, 0, 10.7),
              parent=tower_e, mat_=M_BRASS)
smooth_cone("tower_spike", r1=0.10, r2=0.02, depth=0.80, segs=10,
            loc=(0, 0, 11.4), parent=tower_e, mat_=M_BRASS)

# CENTRAL CLOCK on tower
clock_e = empty("clock_central", (0, -1.85, 9.2), parent=tower_e)
# Face
cyl("clock_face", r=1.4, depth=0.15, segs=32,
    loc=(0, 0, 0), parent=clock_e, mat_=M_PAPER)
cyl("clock_face_rim", r=1.45, depth=0.10, segs=32,
    loc=(0, -0.10, 0), parent=clock_e, mat_=M_BRASS)
clock_e.rotation_euler = (math.radians(90), 0, 0)
# 12 hour markers
for i in range(12):
    a = i * math.pi / 6
    mark = beveled_cube(f"clock_m{i}", (0.10, 0.04, 0.15),
                       loc=(1.10*math.cos(a), -0.18, 1.10*math.sin(a)),
                       parent=clock_e, mat_=M_IRON)
# Hour + minute hands
hand_pivot = empty("clock_hands", (0, -0.18, 0), parent=clock_e)
hour_hand = beveled_cube("clock_hour", (0.10, 0.02, 0.65),
                         loc=(0, 0, 0.30), parent=hand_pivot, mat_=M_IRON)
min_e = empty("clock_min_e", (0, 0, 0), parent=clock_e)
min_hand = beveled_cube("clock_min", (0.06, 0.02, 1.00),
                        loc=(0, -0.02, 0.45), parent=min_e, mat_=M_IRON)
# Initial pose
hand_pivot.rotation_euler = (0, math.radians(80), 0)
min_e.rotation_euler = (0, math.radians(-20), 0)

# ============ LOCOMOTIVE VAPEUR 4 essieux (track 0, y=-3) ============
loco_base = empty("locomotive", loc=(8, -3, 0.55))

# Frame (chassis bottom)
beveled_cube("loco_chassis", (7.5, 1.8, 0.30), bevel_offset=0.05,
             loc=(0, 0, 0), parent=loco_base, mat_=M_LOCO_BLACK)

# Main boiler (large cylinder)
boiler = cyl("loco_boiler", r=1.0, depth=4.5, segs=24,
              loc=(-1.0, 0, 1.30), parent=loco_base, mat_=M_LOCO_BLACK)
boiler.rotation_euler = (0, math.radians(90), 0)

# Boiler bands (3 brass rings)
for i in range(3):
    b = cyl(f"boiler_band{i}", r=1.02, depth=0.08, segs=24,
           loc=(-2.5 + i*1.5, 0, 1.30), parent=loco_base, mat_=M_BRASS)
    b.rotation_euler = (0, math.radians(90), 0)

# Smokebox (front of boiler)
smb = cyl("smokebox", r=1.05, depth=0.8, segs=24,
          loc=(1.8, 0, 1.30), parent=loco_base, mat_=M_LOCO_BLACK)
smb.rotation_euler = (0, math.radians(90), 0)
# Smokebox door (round)
cyl("smokebox_door", r=0.95, depth=0.10, segs=24,
    loc=(2.25, 0, 1.30), parent=loco_base, mat_=M_LOCO_BLACK).rotation_euler = (0, math.radians(90), 0)
# Smokebox handle
smooth_sphere("door_handle", r=0.10, loc=(2.30, 0, 1.30),
              parent=loco_base, mat_=M_BRASS)

# Headlamp (front)
cyl("headlamp_housing", r=0.30, depth=0.30, segs=18,
    loc=(2.4, 0, 1.85), parent=loco_base, mat_=M_BRASS).rotation_euler = (0, math.radians(90), 0)
cyl("headlamp_lens", r=0.25, depth=0.08, segs=18,
    loc=(2.55, 0, 1.85), parent=loco_base, mat_=M_HEADLAMP).rotation_euler = (0, math.radians(90), 0)
# Headlamp beam (cone forward)
beam = smooth_cone("headlamp_beam", r1=0.20, r2=1.5, depth=8, segs=14,
                   loc=(6.55, 0, 1.85), parent=loco_base,
                   mat_=mat("beam", (1.0, 0.95, 0.65, 0.3), 0, 0.05,
                            emission=(1.0,0.95,0.65), emission_strength=2.0, alpha=0.3))
beam.rotation_euler = (0, math.radians(90), 0)

# CHIMNEY (smokestack tall)
chimney_e = empty("chimney", (1.5, 0, 2.30), parent=loco_base)
cyl("chimney_body", r=0.35, depth=1.4, segs=18,
    loc=(0, 0, 0.7), parent=chimney_e, mat_=M_LOCO_BLACK)
# Chimney brass top
cyl("chimney_brass", r=0.42, depth=0.20, segs=18,
    loc=(0, 0, 1.45), parent=chimney_e, mat_=M_BRASS)
cyl("chimney_inner", r=0.28, depth=0.18, segs=18,
    loc=(0, 0, 1.45), parent=chimney_e, mat_=M_FIREBOX)

# Steam dome (over boiler)
smooth_sphere("steam_dome", r=0.45, loc=(-0.5, 0, 2.10),
              parent=loco_base, mat_=M_LOCO_GOLD, scale=(1,1,0.7))
cyl("steam_dome_base", r=0.48, depth=0.20, segs=18,
    loc=(-0.5, 0, 1.90), parent=loco_base, mat_=M_LOCO_BLACK)

# Sand dome (smaller, mid-boiler)
smooth_sphere("sand_dome", r=0.35, loc=(-2.0, 0, 2.05),
              parent=loco_base, mat_=M_LOCO_BLACK, scale=(1,1,0.7))

# Whistle (next to chimney - vertical)
cyl("whistle", r=0.05, depth=0.45, segs=10,
    loc=(0.9, 0.4, 2.30), parent=loco_base, mat_=M_BRASS)
smooth_sphere("whistle_top", r=0.08, loc=(0.9, 0.4, 2.60),
              parent=loco_base, mat_=M_BRASS)

# Bell (front-top)
cyl("bell_yoke", r=0.04, depth=0.30, segs=8,
    loc=(2.0, 0, 2.25), parent=loco_base, mat_=M_BRASS)
smooth_cone("bell", r1=0.18, r2=0.12, depth=0.20, segs=14,
            loc=(2.0, 0, 2.0), parent=loco_base, mat_=M_BRASS)

# CAB (back, where driver stands)
cab_e = empty("cab", (-3.7, 0, 1.30), parent=loco_base)
beveled_cube("cab_body", (1.5, 2.0, 1.6), bevel_offset=0.06,
             loc=(0, 0, 0.6), parent=cab_e, mat_=M_LOCO_BLACK)
# Cab roof
beveled_cube("cab_roof", (1.8, 2.3, 0.15), loc=(0, 0, 1.45),
             parent=cab_e, mat_=M_LOCO_RED)
# Cab windows (2 sides + front)
for side in (-1, 1):
    beveled_cube(f"cab_win_side{side}", (0.05, 0.7, 0.6),
                 loc=(0, side*1.02, 0.9), parent=cab_e, mat_=M_GLASS_LIT)
# Firebox glow (visible from back)
smooth_sphere("firebox_glow", r=0.45, loc=(0.5, 0, 0.4),
              parent=cab_e, mat_=M_FIREBOX, scale=(1, 1.8, 1))

# 4 ESSIEUX (drive wheels) - 4 pairs of big wheels
wheels = []
for wi in range(4):
    wx = -1.5 + wi * 1.4
    for side_idx, side in enumerate((-1, 1)):
        w_e = empty(f"wheel_e{wi}_{side_idx}", (wx, side*1.0, 0.55), parent=loco_base)
        # Wheel disc
        cyl(f"wheel{wi}_{side_idx}", r=0.65, depth=0.10, segs=24,
            loc=(0, 0, 0), parent=w_e, mat_=M_WHEEL).rotation_euler = (math.radians(90), 0, 0)
        # Wheel rim
        cyl(f"wheel_rim{wi}_{side_idx}", r=0.68, depth=0.08, segs=24,
            loc=(0, 0, 0), parent=w_e, mat_=M_WHEEL_RIM).rotation_euler = (math.radians(90), 0, 0)
        # 8 spokes
        for s in range(8):
            a = (s / 8.0) * math.pi * 2
            beveled_cube(f"spoke{wi}_{side_idx}_{s}", (0.08, 0.02, 0.55),
                         loc=(0, 0, 0), parent=w_e, mat_=M_WHEEL_RIM).rotation_euler = (math.radians(90), a, 0)
        # Center hub
        cyl(f"wheel_hub{wi}_{side_idx}", r=0.15, depth=0.13, segs=14,
            loc=(0, 0, 0), parent=w_e, mat_=M_LOCO_GOLD).rotation_euler = (math.radians(90), 0, 0)
        wheels.append(w_e)

# Connecting rods (between wheels - red)
for side in (-1, 1):
    rod = beveled_cube(f"conn_rod_{side}", (4.4, 0.10, 0.10), bevel_offset=0.02,
                       loc=(-0.1, side*1.0, 0.55), parent=loco_base, mat_=M_LOCO_RED)

# Cylinder steam pistons (front sides)
for side in (-1, 1):
    cyl(f"piston_cyl_{side}", r=0.25, depth=1.0, segs=14,
        loc=(2.0, side*1.0, 0.55), parent=loco_base, mat_=M_LOCO_BLACK).rotation_euler = (0, math.radians(90), 0)

# COW CATCHER (front)
catcher_e = empty("catcher", (2.65, 0, 0.40), parent=loco_base)
catcher_e.rotation_euler = (math.radians(-30), 0, 0)
for ci in range(5):
    bar = beveled_cube(f"catcher_bar{ci}", (0.50, 0.05, 0.05),
                       loc=(0, (ci-2)*0.30, 0), parent=catcher_e, mat_=M_LOCO_RED)

# Loco number plate (gold)
beveled_cube("loco_plate", (0.40, 0.05, 0.50), loc=(2.05, 0, 0.7),
             parent=loco_base, mat_=M_LOCO_GOLD)

# Steam puffs from chimney (10 large)
steam_puffs = []
for i in range(10):
    sp = smooth_sphere(f"steam_puff{i}", r=random.uniform(0.50, 0.90),
                      loc=(1.5 + random.uniform(-0.3, 0.3),
                           random.uniform(-0.3, 0.3),
                           3.5 + i*0.7), parent=loco_base, mat_=M_STEAM)
    sp["_phase"] = random.uniform(0, math.pi*2)
    sp["_base_z"] = sp.location.z
    steam_puffs.append(sp)

# ============ 6 WAGONS (behind locomotive) ============
wagons = []
wagon_colors = [M_WAGON_GREEN, M_WAGON_BROWN, M_WAGON_BLUE, M_WAGON_GREEN, M_WAGON_BROWN, M_WAGON_BLUE]
for wi in range(6):
    wx = -5.5 - 3.0 - wi * 4.5  # behind cab
    w_e = empty(f"wagon{wi}", (wx + 8, -3, 0.55))  # adjust with loco_base offset 8
    # Body
    beveled_cube(f"wagon_body{wi}", (3.8, 1.8, 1.6), bevel_offset=0.05,
                 loc=(0, 0, 0.85), parent=w_e, mat_=wagon_colors[wi])
    # Roof (slightly raised)
    beveled_cube(f"wagon_roof{wi}", (4.0, 2.0, 0.15), loc=(0, 0, 1.75),
                 parent=w_e, mat_=M_LOCO_BLACK)
    # Windows (4 along side)
    for s in range(4):
        for side in (-1, 1):
            beveled_cube(f"wagon_win{wi}_{s}_{side}", (0.75, 0.04, 0.55), bevel_offset=0.02,
                         loc=((s-1.5)*0.85, side*0.92, 1.10), parent=w_e, mat_=M_GLASS_LIT)
    # Door (mid wagon)
    beveled_cube(f"wagon_door{wi}", (0.40, 0.04, 1.30),
                 loc=(0, -0.92, 0.95), parent=w_e, mat_=M_WOOD)
    # Wheels (4 per wagon - 2 axes)
    for ax_idx, ax_x in enumerate((-1.2, 1.2)):
        for side_idx, side in enumerate((-1, 1)):
            w_e2 = empty(f"wag_wheel_e{wi}_{ax_idx}_{side_idx}", (ax_x, side*1.0, 0), parent=w_e)
            cyl(f"wag_wheel{wi}_{ax_idx}_{side_idx}", r=0.40, depth=0.08, segs=20,
                loc=(0,0,0), parent=w_e2, mat_=M_WHEEL).rotation_euler = (math.radians(90), 0, 0)
            cyl(f"wag_wheel_rim{wi}_{ax_idx}_{side_idx}", r=0.42, depth=0.06, segs=20,
                loc=(0,0,0), parent=w_e2, mat_=M_WHEEL_RIM).rotation_euler = (math.radians(90), 0, 0)
            wagons.append(w_e2)  # used for spin
    # Couplings (front + back)
    for end in (-1, 1):
        cyl(f"wag_coup{wi}_{end}", r=0.06, depth=0.30, segs=10,
            loc=(end*2.0, 0, 0.40), parent=w_e, mat_=M_IRON).rotation_euler = (0, math.radians(90), 0)
    wagons.append(w_e)

# ============ PEOPLE (30 voyageurs + chef de gare) ============
def make_person(name, loc, coat_mat, hat_mat=M_HAT_TOP, hat_type="top", skin_mat=M_SKIN_L,
                hair_mat=M_HAIR, dress=False, dress_mat=M_DRESS, bonnet_mat=M_BONNET,
                action="stand"):
    base = empty(name, loc)
    # Legs
    if dress:
        # Long dress (flared cone)
        smooth_cone(f"{name}_dress", r1=0.40, r2=0.18, depth=1.2, segs=14,
                    loc=(0, 0, 0.6), parent=base, mat_=dress_mat)
    else:
        # Trouser legs
        for side_idx, side in enumerate((-1, 1)):
            cyl(f"{name}_leg{side_idx}", r=0.10, depth=0.85, segs=10,
                loc=(side*0.12, 0, 0.42), parent=base, mat_=M_COAT_DARK)
            beveled_cube(f"{name}_shoe{side_idx}", (0.16, 0.28, 0.10),
                         loc=(side*0.12, 0.05, 0.08), parent=base, mat_=M_HAT_TOP)
    # Torso
    beveled_cube(f"{name}_torso", (0.40, 0.28, 0.80), bevel_offset=0.05,
                 loc=(0, 0, 1.30), parent=base, mat_=coat_mat)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 1.85), parent=base)
    smooth_sphere(f"{name}_head", r=0.16, segs=18, rings=12, loc=(0,0,0),
                  parent=head_e, mat_=skin_mat)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye_{side}", r=0.02,
                      loc=(side*0.05, -0.13, 0.02), parent=head_e,
                      mat_=mat(f"{name}_e_w", (1,1,1,1), 0, 0.3))
    # Hat
    if hat_type == "top":
        cyl(f"{name}_hat_brim", r=0.20, depth=0.03, segs=14,
            loc=(0, 0, 0.16), parent=head_e, mat_=hat_mat)
        cyl(f"{name}_hat_body", r=0.13, depth=0.25, segs=14,
            loc=(0, 0, 0.30), parent=head_e, mat_=hat_mat)
    elif hat_type == "bowler":
        smooth_sphere(f"{name}_hat_body", r=0.17, loc=(0, 0, 0.18),
                      parent=head_e, mat_=hat_mat, scale=(1, 1, 0.7))
        cyl(f"{name}_hat_brim", r=0.21, depth=0.02, segs=14,
            loc=(0, 0, 0.14), parent=head_e, mat_=hat_mat)
    elif hat_type == "bonnet":
        smooth_sphere(f"{name}_bonnet", r=0.20, loc=(0, 0.03, 0.10),
                      parent=head_e, mat_=bonnet_mat, scale=(1, 1, 0.75))
        # Ribbon
        beveled_cube(f"{name}_ribbon", (0.05, 0.04, 0.20),
                     loc=(0, -0.20, -0.05), parent=head_e, mat_=bonnet_mat)
    elif hat_type == "cap":
        # Conductor cap (chef de gare)
        cyl(f"{name}_cap_body", r=0.18, depth=0.10, segs=14,
            loc=(0, 0, 0.18), parent=head_e, mat_=hat_mat)
        # Visor
        beveled_cube(f"{name}_cap_visor", (0.30, 0.18, 0.04),
                     loc=(0, -0.10, 0.12), parent=head_e, mat_=hat_mat)
    # Hair visible
    if hat_type in ("bonnet", "cap"):
        smooth_sphere(f"{name}_hair", r=0.17, loc=(0, 0.05, 0),
                      parent=head_e, mat_=hair_mat, scale=(1, 0.7, 0.95))
    # ARMS
    if action == "wave":
        # Right arm raised, holding mouchoir
        r_sh = empty(f"{name}_r_sh", (0.22, 0, 1.65), parent=base)
        r_sh.rotation_euler = (math.radians(-160), 0, 0)
    elif action == "carry":
        # Both arms forward with suitcase
        r_sh = empty(f"{name}_r_sh", (0.22, 0, 1.65), parent=base)
        r_sh.rotation_euler = (math.radians(-60), 0, math.radians(-15))
    elif action == "point":
        # Right arm extended
        r_sh = empty(f"{name}_r_sh", (0.22, 0, 1.65), parent=base)
        r_sh.rotation_euler = (math.radians(-90), 0, math.radians(-25))
    else:
        r_sh = empty(f"{name}_r_sh", (0.22, 0, 1.65), parent=base)
        r_sh.rotation_euler = (math.radians(-10), 0, 0)
    cyl(f"{name}_r_up", r=0.07, depth=0.35, segs=8,
        loc=(0, 0, -0.18), parent=r_sh, mat_=coat_mat)
    cyl(f"{name}_r_fa", r=0.06, depth=0.32, segs=8,
        loc=(0, 0, -0.50), parent=r_sh, mat_=coat_mat)
    # Right hand with mouchoir (if waving)
    if action == "wave":
        beveled_cube(f"{name}_mouchoir", (0.10, 0.10, 0.02),
                     loc=(0, 0, -0.70), parent=r_sh, mat_=M_MOUCHOIR)
    # Left arm
    l_sh = empty(f"{name}_l_sh", (-0.22, 0, 1.65), parent=base)
    l_sh.rotation_euler = (math.radians(-10), 0, 0)
    cyl(f"{name}_l_up", r=0.07, depth=0.35, segs=8,
        loc=(0, 0, -0.18), parent=l_sh, mat_=coat_mat)
    cyl(f"{name}_l_fa", r=0.06, depth=0.32, segs=8,
        loc=(0, 0, -0.50), parent=l_sh, mat_=coat_mat)
    return {"root": base, "head_e": head_e, "r_sh": r_sh, "l_sh": l_sh}

# CHEF DE GARE (red coat, cap, holds whistle, points)
chef = make_person("chef", (0, -1.5, 0.5), M_COAT_RED, M_COAT_RED, "cap",
                   M_SKIN_L, M_HAIR_GREY := M_HAIR, action="point")
# Whistle in hand (small cylinder)
cyl("chef_whistle", r=0.04, depth=0.10, segs=10,
    loc=(0, 0, -0.80), parent=chef["r_sh"], mat_=M_BRASS)

# 30 voyageurs
people = [chef]
for i in range(30):
    # Random platform
    plat_y = random.choice(platform_ys)
    px = random.uniform(-18, 18)
    py = plat_y + random.uniform(-1.2, 1.2)
    # Random outfit
    is_woman = random.random() < 0.4
    actions = ["stand", "wave", "carry", "point"]
    act = random.choice(actions)
    if is_woman:
        p = make_person(f"voy{i}", (px, py, 0.5),
                        M_DRESS if random.random() < 0.5 else M_DRESS_BLUE,
                        M_BONNET, "bonnet",
                        M_SKIN_L if random.random() < 0.7 else M_SKIN_D,
                        M_HAIR_BLOND if random.random() < 0.3 else M_HAIR,
                        dress=True,
                        dress_mat=M_DRESS if random.random() < 0.5 else M_DRESS_BLUE,
                        action=act)
    else:
        coat_choice = random.choice([M_COAT_DARK, M_COAT_BROWN])
        hat_choice = "top" if random.random() < 0.5 else "bowler"
        p = make_person(f"voy{i}", (px, py, 0.5), coat_choice,
                        M_HAT_TOP if hat_choice == "top" else M_HAT_BOWLER,
                        hat_choice,
                        M_SKIN_L if random.random() < 0.7 else M_SKIN_D,
                        M_HAIR_BLOND if random.random() < 0.2 else M_HAIR,
                        action=act)
    p["root"].rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    p["_action"] = act
    people.append(p)

# ============ 12 LAMPADAIRES GAZ ============
lamps = []
lamp_positions = []
for pi in range(3):
    for i in range(4):
        lamp_positions.append((-15 + i * 10, platform_ys[pi], 0))
for i, (lx, ly, lz) in enumerate(lamp_positions):
    l_e = empty(f"lamp_e{i}", (lx, ly, lz))
    # Pole
    cyl(f"lamp_pole{i}", r=0.08, depth=3.5, segs=12,
        loc=(0, 0, 1.75), parent=l_e, mat_=M_IRON)
    # Decorative knobs
    smooth_sphere(f"lamp_knob{i}", r=0.12, loc=(0, 0, 2.5),
                  parent=l_e, mat_=M_BRASS)
    smooth_sphere(f"lamp_knob2{i}", r=0.10, loc=(0, 0, 3.0),
                  parent=l_e, mat_=M_BRASS)
    # Top cross arm
    beveled_cube(f"lamp_arm{i}", (0.04, 0.4, 0.04),
                 loc=(0, 0, 3.4), parent=l_e, mat_=M_IRON)
    # Lamp globe
    smooth_sphere(f"lamp_globe{i}", r=0.20, loc=(0, 0, 3.6),
                  parent=l_e, mat_=M_LAMP_GLOBE)
    # Gas flame inside
    flame_o = smooth_cone(f"lamp_flame{i}", r1=0.07, r2=0.005, depth=0.18, segs=8,
                          loc=(0, 0, 3.6), parent=l_e, mat_=M_GAS_FLAME)
    flame_i = smooth_cone(f"lamp_flame_i{i}", r1=0.04, r2=0.003, depth=0.12, segs=8,
                          loc=(0, 0, 3.62), parent=l_e, mat_=M_GAS_INNER)
    # Decorative crown
    cyl(f"lamp_crown{i}", r=0.25, depth=0.05, segs=14,
        loc=(0, 0, 3.85), parent=l_e, mat_=M_IRON)
    smooth_cone(f"lamp_top{i}", r1=0.20, r2=0.03, depth=0.30, segs=10,
                loc=(0, 0, 4.05), parent=l_e, mat_=M_IRON)
    lamps.append({"e": l_e, "flame_o": flame_o, "flame_i": flame_i,
                  "phase": random.uniform(0, math.pi*2)})

# ============ TELEGRAPH STATION (next to platform) ============
tel_base = empty("telegraph", loc=(-18, -9, 0))
# Pole
cyl("tel_pole", r=0.10, depth=5.0, segs=12, loc=(0,0,2.5),
    parent=tel_base, mat_=M_WOOD)
# Cross arms (3 levels)
for i in range(3):
    z = 3.5 + i * 0.7
    beveled_cube(f"tel_arm{i}", (0.05, 1.4, 0.05),
                 loc=(0, 0, z), parent=tel_base, mat_=M_WOOD)
    # 4 isolators (insulators - small ceramic globes)
    for j in range(4):
        smooth_sphere(f"tel_iso{i}_{j}", r=0.06,
                      loc=(0, (j-1.5)*0.40, z+0.05),
                      parent=tel_base, mat_=M_PAPER)
# Telegraph box at base
beveled_cube("tel_box", (0.55, 0.40, 0.50), bevel_offset=0.04,
             loc=(0, 0.30, 0.6), parent=tel_base, mat_=M_TELEGRAPH)
# Box brass details
cyl("tel_dial", r=0.10, depth=0.04, segs=14,
    loc=(0, 0.55, 0.7), parent=tel_base, mat_=M_BRASS).rotation_euler = (math.radians(90), 0, 0)
# Tapper
beveled_cube("tel_tapper", (0.05, 0.15, 0.03), loc=(0, 0.55, 0.85),
             parent=tel_base, mat_=M_BRASS)

# ============ SUITCASES STACK (next to platform) ============
suitcase_e = empty("suitcases", loc=(-12, -9, 0))
for i in range(8):
    sx = (i % 2) * 0.7 - 0.35
    sz = (i // 2) * 0.40
    sc = beveled_cube(f"suitcase{i}", (0.65, 0.45, 0.30), bevel_offset=0.04,
                      loc=(sx, 0, 0.20 + sz), parent=suitcase_e,
                      mat_=random.choice([M_SUITCASE, M_COAT_BROWN, M_WOOD]))
    sc.rotation_euler = (0, 0, random.uniform(-0.2, 0.2))
    # Handle
    beveled_cube(f"suitcase_h{i}", (0.20, 0.04, 0.06),
                 loc=(sx, 0, 0.42 + sz), parent=suitcase_e, mat_=M_SUITCASE_HANDLE)
    # Buckles (2)
    for j in range(2):
        smooth_sphere(f"suitcase_b{i}_{j}", r=0.025,
                      loc=(sx + (j-0.5)*0.30, -0.22, 0.20 + sz),
                      parent=suitcase_e, mat_=M_BRASS)

# ============ DIRIGEABLE (in sky background) ============
airship_e = empty("airship", loc=(22, 15, 20))
airship_e.rotation_euler = (0, 0, math.radians(15))
# Body envelope (large elongated)
smooth_sphere("airship_body", r=2.5, segs=28, rings=18,
              loc=(0, 0, 0), parent=airship_e, mat_=M_AIRSHIP, scale=(2.5, 1, 1))
# 4 fins at tail
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    fin = beveled_cube(f"air_fin{i}", (0.05, 0.8, 1.0), bevel_offset=0.03,
                       loc=(-5.5, 0.4*math.cos(a), 0.4*math.sin(a)),
                       parent=airship_e, mat_=M_AIRSHIP)
    fin.rotation_euler = (a, 0, 0)
# Gondola underneath
beveled_cube("airship_gond", (3.0, 0.8, 0.6), bevel_offset=0.05,
             loc=(0, 0, -2.0), parent=airship_e, mat_=M_AIRSHIP_GONDOLA)
# Gondola windows
for i in range(4):
    beveled_cube(f"airship_win{i}", (0.4, 0.85, 0.25),
                 loc=((i-1.5)*0.7, 0, -1.95), parent=airship_e, mat_=M_GLASS_LIT)
# Connecting cables (4)
for i in range(4):
    cyl(f"air_cable{i}", r=0.02, depth=1.5, segs=6,
        loc=((i-1.5)*0.8, 0, -1.0), parent=airship_e, mat_=M_IRON_DARK)
# Propeller back
cyl("air_prop_hub", r=0.10, depth=0.10, segs=12,
    loc=(-5.8, 0, 0), parent=airship_e, mat_=M_BRASS).rotation_euler = (0, math.radians(90), 0)
# 3 prop blades
prop_e = empty("air_prop", (-5.85, 0, 0), parent=airship_e)
for i in range(3):
    a = i * math.pi * 2 / 3
    beveled_cube(f"air_blade{i}", (0.04, 0.05, 0.70),
                 loc=(0, 0.35*math.cos(a), 0.35*math.sin(a)),
                 parent=prop_e, mat_=M_AIRSHIP_GONDOLA).rotation_euler = (a, 0, 0)

# ============ 50 ASH PARTICLES + STEAM PARTICLES ============
ashes = []
for i in range(50):
    ax = random.uniform(-25, 25)
    ay = random.uniform(-15, 15)
    az = random.uniform(5, 15)
    a = smooth_sphere(f"ash{i}", r=random.uniform(0.05, 0.12), segs=8, rings=6,
                     loc=(ax, ay, az),
                     mat_=mat(f"ash_p{i}", (0.55, 0.50, 0.48, 1.0), 0, 0.5,
                              emission=(0.45,0.40,0.38), emission_strength=2.5))
    a["_phase"] = random.uniform(0, math.pi*2)
    a["_base_x"] = ax; a["_base_y"] = ay; a["_base_z"] = az
    a["_speed"] = random.uniform(0.4, 1.0)
    ashes.append(a)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Locomotive subtle bob (idling at platform)
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    loco_base.location.z = 0.55 + math.sin(t * 2.5) * 0.02
    loco_base.keyframe_insert("location", frame=f)

# 4 essieux wheels spin (slow - locomotive standing/idling, slight movement)
for wi, w in enumerate(wheels):
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        w.rotation_euler = (t * 0.8, 0, 0)
        w.keyframe_insert("rotation_euler", frame=f)

# Wagon wheels spin (same as loco)
for wn in wagons:
    if wn.name.startswith("wag_wheel_e"):
        for f in range(1, total_frames + 1, 3):
            t = (f - 1) / fps
            wn.rotation_euler = (t * 0.8, 0, 0)
            wn.keyframe_insert("rotation_euler", frame=f)

# Steam puffs rise up from chimney
for sp in steam_puffs:
    phase = sp["_phase"]
    base_z = sp["_base_z"]
    base_x = sp.location.x
    base_y = sp.location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        z = base_z + (t * 1.5) % 8.0
        x = base_x + math.sin(t * 1.0 + phase) * 0.4
        y = base_y + math.cos(t * 1.0 + phase) * 0.4
        s = 1 + math.sin(t * 1.5 + phase) * 0.20
        sp.location = (x, y, z)
        sp.scale = (s, s, s)
        sp.keyframe_insert("location", frame=f)
        sp.keyframe_insert("scale", frame=f)

# Gas lamp flames pulse différentielles
for l in lamps:
    phase = l["phase"]
    flame_o = l["flame_o"]; flame_i = l["flame_i"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        s_o = 1 + math.sin(t * 6.0 + phase) * 0.25
        flame_o.scale = (s_o, s_o, s_o)
        flame_o.keyframe_insert("scale", frame=f)
        s_i = 1 + math.sin(t * 8.0 + phase + 0.3) * 0.30
        flame_i.scale = (s_i, s_i, s_i)
        flame_i.keyframe_insert("scale", frame=f)

# Voyageurs animations (wave mouchoir, walk, point)
for p in people:
    if "_action" not in p.keys():
        continue
    act = p["_action"]
    base_z = p["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Subtle Z bob (breathing)
        p["root"].location.z = base_z + math.sin(t * 1.0 + hash(p["root"].name) % 100) * 0.02
        p["root"].keyframe_insert("location", frame=f)
        # Head turn
        p["head_e"].rotation_euler = (0, 0, math.sin(t * 0.7) * math.radians(15))
        p["head_e"].keyframe_insert("rotation_euler", frame=f)
        if act == "wave":
            # Right arm wave
            p["r_sh"].rotation_euler = (math.radians(-160) + math.sin(t * 4.0) * math.radians(15),
                                        0,
                                        math.sin(t * 4.0 + 0.5) * math.radians(20))
            p["r_sh"].keyframe_insert("rotation_euler", frame=f)
        elif act == "point":
            # Subtle pointing oscillation
            p["r_sh"].rotation_euler = (math.radians(-90) + math.sin(t * 1.5) * math.radians(5),
                                        0,
                                        math.radians(-25))
            p["r_sh"].keyframe_insert("rotation_euler", frame=f)

# Clock hands (slow rotation)
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    hand_pivot.rotation_euler = (0, math.radians(80) + t * 0.05, 0)
    hand_pivot.keyframe_insert("rotation_euler", frame=f)
    min_e.rotation_euler = (0, math.radians(-20) + t * 0.8, 0)
    min_e.keyframe_insert("rotation_euler", frame=f)

# Whistle steam (the whistle vibrates + steam)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    # Whistle small Z motion
    pass  # already in base

# Dirigeable bob + prop spin
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    airship_e.location.z = 20 + math.sin(t * 0.8) * 0.4
    airship_e.location.x = 22 + math.sin(t * 0.3) * 1.5
    airship_e.keyframe_insert("location", frame=f)
    prop_e.rotation_euler = (t * 15.0, 0, 0)
    prop_e.keyframe_insert("rotation_euler", frame=f)

# Sun halos breathe
for obj in bpy.data.objects:
    if obj.name.startswith("sun_halo"):
        if "_phase" in obj.keys():
            phase = obj["_phase"]
            for f in range(1, total_frames + 1, 5):
                t = (f - 1) / fps
                s = 1 + math.sin(t * 1.2 + phase) * 0.10
                obj.scale = (s, s, s)
                obj.keyframe_insert("scale", frame=f)

# Industrial smoke drift
for sm_e in ind_smokes:
    phase = sm_e["_phase"]
    base_x = sm_e.location.x; base_y = sm_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        sm_e.location = (base_x + math.sin(t * 0.3 + phase) * 0.6,
                         base_y + math.cos(t * 0.25 + phase) * 0.6,
                         sm_e.location.z)
        s = 1 + math.sin(t * 0.5 + phase) * 0.1
        sm_e.scale = (s, s, s)
        sm_e.keyframe_insert("location", frame=f)
        sm_e.keyframe_insert("scale", frame=f)

# Ash particles drift + twinkle
for a in ashes:
    phase = a["_phase"]; speed = a["_speed"]
    bx, by, bz = a["_base_x"], a["_base_y"], a["_base_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * 1.5
        y = by + math.cos(t * speed * 0.9 + phase) * 1.2
        z = bz + (t * 0.4) % 6.0
        s = 1 + math.sin(t * 3.0 + phase) * 0.3
        a.location = (x, y, z)
        a.scale = (s, s, s)
        a.keyframe_insert("location", frame=f)
        a.keyframe_insert("scale", frame=f)

# Firebox glow pulse
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 4.0) * 0.15
    # Firebox is inside cab - find it
    for obj in bpy.data.objects:
        if obj.name == "firebox_glow":
            obj.scale = (s, 1.8 * s, s)
            obj.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_railway_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_steampunk_railway_station] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_steampunk_railway_station] Verrière fer + 3 quais + 2 voies + locomotive 4-essieux + 6 wagons + chef + 30 voyageurs + 12 lampadaires gas + télégraphe + 8 valises + tower clock + dirigeable + 50 ash particles")
