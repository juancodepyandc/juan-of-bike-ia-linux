"""
proc_grandfather_clock_workshop.py — 194e procédural AuroraIA (58e qualité)
Horloge grand-père géante atelier : boîtier + cadran + aiguilles + pendule + carillon + engrenages + ressorts + table horloger
"""
import bpy, bmesh, math, random, os

random.seed(0xC10C420)

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
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free(); smooth_shade(me)
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

def gear(name, r_outer, r_inner, teeth, depth, loc=(0,0,0), parent=None, mat_=None):
    """Create a simple gear: cylinder + radial teeth + center hole indication"""
    g_e = empty(name + "_e", loc, parent)
    # Main disc
    cyl(name + "_disc", r=r_outer * 0.85, depth=depth, segs=max(20, teeth),
        loc=(0,0,0), parent=g_e, mat_=mat_)
    # Teeth (radial blocks)
    for i in range(teeth):
        a = (i / teeth) * math.pi * 2
        tooth = beveled_cube(f"{name}_t{i}", (r_outer * 0.18, r_outer * 0.10, depth * 0.95),
                            bevel_offset=0.015,
                            loc=(r_outer * 0.92 * math.cos(a), r_outer * 0.92 * math.sin(a), 0),
                            parent=g_e, mat_=mat_)
        tooth.rotation_euler = (0, 0, a)
    # Center hub (slightly raised)
    cyl(name + "_hub", r=r_inner, depth=depth * 1.3, segs=16,
        loc=(0,0,0), parent=g_e, mat_=mat_)
    return g_e

reset()
scene = bpy.context.scene
scene.frame_start = 1; scene.frame_end = 180; scene.render.fps = 30

# Materials
M_SKY = mat("sky", (0.15, 0.10, 0.20, 1.0), 0.0, 0.7, emission=(0.20,0.15,0.30), emission_strength=1.0)
M_LIGHTNING = mat("lightning", (1.0, 0.95, 0.80, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.85), emission_strength=18.0)
M_FLOOR = mat("floor", (0.30, 0.20, 0.12, 1.0), 0.0, 0.80)
M_WOOD_DARK = mat("wood_dark", (0.18, 0.10, 0.05, 1.0), 0.0, 0.75)
M_WOOD_RICH = mat("wood_rich", (0.35, 0.18, 0.08, 1.0), 0.0, 0.55, emission=(0.30,0.15,0.05), emission_strength=0.3)
M_WOOD_WORN = mat("wood_worn", (0.45, 0.30, 0.18, 1.0), 0.0, 0.70)
M_GOLD = mat("gold", (1.0, 0.78, 0.25, 1.0), 0.95, 0.18, emission=(0.95,0.72,0.22), emission_strength=0.8)
M_GOLD_DIM = mat("gold_dim", (0.85, 0.65, 0.20, 1.0), 0.85, 0.30, emission=(0.75,0.58,0.18), emission_strength=0.5)
M_BRASS = mat("brass", (0.85, 0.62, 0.25, 1.0), 0.90, 0.25, emission=(0.78,0.55,0.22), emission_strength=0.6)
M_SILVER = mat("silver", (0.85, 0.85, 0.88, 1.0), 0.92, 0.20, emission=(0.78,0.78,0.80), emission_strength=0.4)
M_GLASS = mat("glass", (0.90, 0.93, 0.95, 0.4), 0.0, 0.05, emission=(0.85,0.88,0.92), emission_strength=0.5, alpha=0.4)
M_DIAL_WHITE = mat("dial", (0.95, 0.93, 0.85, 1.0), 0.0, 0.55, emission=(0.95,0.92,0.80), emission_strength=1.5)
M_HAND_BLACK = mat("hand", (0.05, 0.05, 0.05, 1.0), 0.4, 0.55)
M_HAND_HOUR = mat("hand_hour", (0.10, 0.10, 0.10, 1.0), 0.5, 0.45, emission=(0.20,0.18,0.15), emission_strength=0.4)
M_PENDULUM = mat("pendulum", (1.0, 0.82, 0.30, 1.0), 0.95, 0.18, emission=(0.95,0.78,0.30), emission_strength=1.2)
M_BELL = mat("bell", (0.80, 0.55, 0.18, 1.0), 0.92, 0.22, emission=(0.75,0.50,0.18), emission_strength=0.6)
M_SPRING = mat("spring", (0.65, 0.65, 0.68, 1.0), 0.85, 0.30, emission=(0.55,0.55,0.58), emission_strength=0.4)
M_GEAR_BRASS = mat("gear_brass", (0.85, 0.65, 0.25, 1.0), 0.88, 0.25, emission=(0.75,0.58,0.22), emission_strength=0.5)
M_GEAR_SILVER = mat("gear_silver", (0.75, 0.78, 0.80, 1.0), 0.88, 0.25, emission=(0.65,0.68,0.70), emission_strength=0.4)
M_GEAR_COPPER = mat("gear_copper", (0.85, 0.42, 0.18, 1.0), 0.88, 0.30, emission=(0.75,0.38,0.18), emission_strength=0.5)
M_TOOL = mat("tool", (0.30, 0.30, 0.32, 1.0), 0.6, 0.50)
M_TOOL_HANDLE = mat("tool_handle", (0.45, 0.25, 0.15, 1.0), 0.0, 0.70)
M_CANDLE = mat("candle", (0.95, 0.92, 0.80, 1.0), 0.0, 0.45, emission=(0.95,0.90,0.75), emission_strength=0.5)
M_CANDLE_FLAME = mat("candle_flame", (1.0, 0.70, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.75,0.25), emission_strength=14.0)
M_CANDLE_FLAME_I = mat("candle_flame_i", (1.0, 0.92, 0.50, 1.0), 0.0, 0.10, emission=(1.0,0.95,0.60), emission_strength=20.0)
M_PAPER = mat("paper", (0.92, 0.86, 0.70, 1.0), 0.0, 0.65, emission=(0.85,0.78,0.62), emission_strength=0.4)
M_INK = mat("ink", (0.15, 0.08, 0.05, 1.0), 0.0, 0.75)
M_DUST = mat("dust", (0.85, 0.78, 0.65, 1.0), 0.0, 0.45, emission=(0.90,0.85,0.72), emission_strength=4.0, alpha=0.6)
M_CAT_BLACK = mat("cat", (0.05, 0.05, 0.07, 1.0), 0.0, 0.60, emission=(0.10,0.10,0.12), emission_strength=0.3)
M_CAT_EYE_CLOSED = mat("cat_eye_c", (0.05, 0.05, 0.05, 1.0), 0.0, 0.7)
M_WALL = mat("wall", (0.35, 0.28, 0.20, 1.0), 0.0, 0.75)

# ============ SKY DOME / NIGHT STORM ============
sky = smooth_sphere("sky", r=80, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.55))
sky.scale = (1,1,0.55)
# 2 lightning bolts (zigzag bright émissif)
lightning_segs = []
for li in range(2):
    base_x = -25 + li * 50
    bolt_e = empty(f"bolt_e{li}", (base_x, 30, 25))
    for i in range(5):
        seg = beveled_cube(f"bolt{li}_{i}", (0.20, 0.10, 1.2), bevel_offset=0.02,
                          loc=((i%2)*0.8 - 0.4, 0, -i*1.0),
                          parent=bolt_e, mat_=M_LIGHTNING)
        seg.rotation_euler = (0, 0, math.radians(((i%2)*40 - 20)))
    bolt_e["_phase"] = li * 2.5
    lightning_segs.append(bolt_e)

# ============ FLOOR + WALLS ============
floor = beveled_cube("floor", (30, 30, 0.4), bevel_offset=0.05, loc=(0, 0, -0.2), mat_=M_FLOOR)
# Floor planks (12 visible)
for i in range(12):
    plank = beveled_cube(f"plank{i}", (28, 0.05, 0.02), loc=(0, (i-5.5)*2.0, 0.01), mat_=M_WOOD_DARK)

# Back wall
back_wall = beveled_cube("back_wall", (24, 0.4, 12), loc=(0, 12, 6), mat_=M_WALL)
# Wall trim
beveled_cube("wall_trim_b", (24, 0.45, 0.4), loc=(0, 11.95, 0.4), mat_=M_WOOD_RICH)
beveled_cube("wall_trim_t", (24, 0.45, 0.4), loc=(0, 11.95, 11.7), mat_=M_WOOD_RICH)

# ============ GRANDFATHER CLOCK CASE (massive 4m tall) ============
clock_base = empty("clock", loc=(0, 9.5, 0))

# Bottom plinth (wide base)
beveled_cube("clock_plinth", (1.6, 0.95, 0.50), bevel_offset=0.06,
             loc=(0, 0, 0.25), parent=clock_base, mat_=M_WOOD_RICH)
# Decorative carved base trim
beveled_cube("plinth_top", (1.7, 1.0, 0.10), loc=(0, 0, 0.55), parent=clock_base, mat_=M_WOOD_DARK)
# 2 columns flanking plinth
for side in (-1, 1):
    cyl(f"plinth_col_{side}", r=0.10, depth=0.4, segs=16,
        loc=(side*0.65, -0.35, 0.30), parent=clock_base, mat_=M_WOOD_RICH)
    smooth_sphere(f"plinth_col_top_{side}", r=0.10, loc=(side*0.65, -0.35, 0.55),
                  parent=clock_base, mat_=M_GOLD_DIM)

# Main case body (tall middle section with pendulum window)
beveled_cube("clock_case", (1.3, 0.55, 2.6), bevel_offset=0.04,
             loc=(0, 0, 2.0), parent=clock_base, mat_=M_WOOD_RICH)
# Pendulum glass window (front face)
beveled_cube("case_window_frame", (1.0, 0.05, 2.0), bevel_offset=0.02,
             loc=(0, -0.30, 2.0), parent=clock_base, mat_=M_WOOD_DARK)
# Glass pane
beveled_cube("case_glass", (0.85, 0.04, 1.85), bevel_offset=0.02,
             loc=(0, -0.31, 2.0), parent=clock_base, mat_=M_GLASS)
# Side carved columns
for side in (-1, 1):
    cyl(f"case_col_{side}", r=0.05, depth=2.4, segs=12,
        loc=(side*0.62, -0.30, 2.0), parent=clock_base, mat_=M_GOLD_DIM)

# ============ CLOCK FACE (top of case) ============
face_base = empty("face_e", (0, -0.30, 3.85), parent=clock_base)
# Face housing (rounded crown)
beveled_cube("face_housing", (1.4, 0.30, 1.1), bevel_offset=0.10,
             loc=(0, 0.10, 0), parent=face_base, mat_=M_WOOD_RICH)
# Decorative top arch
smooth_sphere("face_arch", r=0.65, loc=(0, 0.10, 0.50),
              parent=face_base, mat_=M_WOOD_RICH, scale=(1.1, 0.3, 0.7))
# Clock dial (white disc)
dial = cyl("dial", r=0.50, depth=0.04, segs=40,
            loc=(0, -0.10, 0.05), parent=face_base, mat_=M_DIAL_WHITE)
dial.rotation_euler = (math.radians(90), 0, 0)
# Roman numerals (12 positions)
roman_nums_pos = list(range(12))
for i in roman_nums_pos:
    a = i * math.pi * 2 / 12 - math.pi/2  # XII at top
    rx = 0.40 * math.cos(a + math.pi/2)
    rz = 0.40 * math.sin(a + math.pi/2)
    # Roman numeral as small box (we approximate I, II, III, etc visually)
    num_size = 0.06
    nm = beveled_cube(f"num_{i}", (num_size, 0.01, num_size * 1.6),
                     loc=(rx, -0.12, 0.05 + rz), parent=face_base, mat_=M_INK)
    # Add bars for IV/VI etc - simple 2-3 bars representation
    for j in range(min(3, (i % 12 + 1) // 4 + 1)):
        beveled_cube(f"num_bar{i}_{j}", (0.012, 0.005, 0.05),
                     loc=(rx + (j-1)*0.025, -0.13, 0.05 + rz), parent=face_base, mat_=M_INK)

# Center hub
smooth_sphere("hub_center", r=0.05, loc=(0, -0.13, 0.05), parent=face_base, mat_=M_GOLD)

# Clock hands (hour + minute)
hand_pivot = empty("hand_pivot", (0, -0.13, 0.05), parent=face_base)
# Hour hand (shorter, fatter)
hour_e = empty("hour_e", (0, 0, 0), parent=hand_pivot)
hour_hand = beveled_cube("hour_hand", (0.05, 0.02, 0.30), bevel_offset=0.01,
                         loc=(0, 0, 0.13), parent=hour_e, mat_=M_HAND_HOUR)
# Decorative tip
smooth_sphere("hour_tip", r=0.04, loc=(0, 0, 0.30), parent=hour_e, mat_=M_HAND_HOUR)
# Minute hand (longer, thinner)
min_e = empty("min_e", (0, 0, 0), parent=hand_pivot)
min_hand = beveled_cube("min_hand", (0.03, 0.018, 0.45), bevel_offset=0.005,
                        loc=(0, -0.002, 0.20), parent=min_e, mat_=M_HAND_BLACK)
smooth_cone("min_tip", r1=0.025, r2=0.005, depth=0.08, segs=8,
            loc=(0, -0.002, 0.43), parent=min_e, mat_=M_HAND_BLACK)

# Initial positions
hour_e.rotation_euler = (0, math.radians(-100), 0)  # ~10 o'clock
min_e.rotation_euler = (0, math.radians(50), 0)

# Top crown ornament (above face)
top_crown = empty("top_crown", (0, 0, 4.55), parent=clock_base)
# Pediment (triangular)
for i in range(2):
    side = (-1) ** i
    p = beveled_cube(f"pediment_{side}", (0.50, 0.50, 0.10), bevel_offset=0.03,
                    loc=(side*0.30, 0.10, 0.05), parent=top_crown, mat_=M_WOOD_DARK)
    p.rotation_euler = (0, math.radians(side * 25), 0)
# Top finial sphere + spike
smooth_sphere("crown_orb", r=0.18, loc=(0, 0.10, 0.30), parent=top_crown, mat_=M_GOLD)
smooth_cone("crown_spike", r1=0.06, r2=0.01, depth=0.50, segs=12,
            loc=(0, 0.10, 0.70), parent=top_crown, mat_=M_GOLD)

# ============ PENDULUM ============
pendulum_e = empty("pendulum_pivot", (0, -0.30, 3.30), parent=clock_base)
# Pendulum rod
cyl("pend_rod", r=0.025, depth=2.0, segs=12,
    loc=(0, 0, -1.0), parent=pendulum_e, mat_=M_BRASS)
# Pendulum bob (heavy disc with chevrons)
pend_bob = cyl("pend_bob", r=0.32, depth=0.10, segs=28,
                loc=(0, 0, -2.05), parent=pendulum_e, mat_=M_PENDULUM)
pend_bob.rotation_euler = (math.radians(90), 0, 0)
# Bob rim
cyl("pend_bob_rim", r=0.34, depth=0.04, segs=28,
    loc=(0, 0, -2.05), parent=pendulum_e, mat_=M_GOLD).rotation_euler = (math.radians(90), 0, 0)
# Sun face on bob (radial)
for i in range(8):
    a = i * math.pi / 4
    beveled_cube(f"sun_ray{i}", (0.04, 0.02, 0.18),
                 loc=(0.20*math.cos(a), 0, -2.05 + 0.20*math.sin(a)),
                 parent=pendulum_e, mat_=M_GOLD)
# Bob center
smooth_sphere("bob_center", r=0.10, loc=(0, -0.02, -2.05),
              parent=pendulum_e, mat_=M_GOLD)

# ============ CLOCK INTERIOR GEARS (visible through glass) ============
# 6 gears in mechanism, rates coupled
gears = []
gear_specs = [
    # name, r_outer, r_inner, teeth, depth, loc, mat, speed
    ("g1", 0.20, 0.04, 20, 0.06, (-0.30, -0.20, 3.5), M_GEAR_BRASS, 1.0),
    ("g2", 0.15, 0.03, 14, 0.06, (-0.05, -0.20, 3.42), M_GEAR_SILVER, -1.5),
    ("g3", 0.22, 0.04, 22, 0.06, (0.25, -0.20, 3.5), M_GEAR_COPPER, 0.7),
    ("g4", 0.13, 0.03, 12, 0.06, (-0.25, -0.20, 2.95), M_GEAR_BRASS, 2.0),
    ("g5", 0.18, 0.04, 18, 0.06, (0.10, -0.20, 2.90), M_GEAR_SILVER, -1.2),
    ("g6", 0.15, 0.03, 14, 0.06, (-0.10, -0.20, 1.60), M_GEAR_COPPER, 1.8),
]
for spec in gear_specs:
    name, r_o, r_i, teeth, depth, loc, mat_, speed = spec
    g = gear(name, r_o, r_i, teeth, depth, loc=loc, parent=clock_base, mat_=mat_)
    g.rotation_euler = (math.radians(90), 0, 0)
    g["_speed"] = speed
    gears.append(g)

# ============ SPRINGS (3 coil springs inside) ============
springs = []
def make_spring(name, loc, r_outer=0.10, height=0.6, turns=10, parent=None):
    s_e = empty(name, loc, parent)
    pts_per_turn = 8
    total = turns * pts_per_turn
    prev = None
    # Build helix using small cylinders connected segment by segment
    for i in range(total):
        t = i / total
        a = t * turns * 2 * math.pi
        x = r_outer * math.cos(a)
        z = -height * t
        y = r_outer * math.sin(a)
        sph = smooth_sphere(f"{name}_p{i}", r=0.012, segs=8, rings=6,
                            loc=(x, y, z), parent=s_e, mat_=M_SPRING)
    return s_e

# Spring 1
sp1 = make_spring("spring1", (-0.35, -0.20, 2.55), r_outer=0.08, height=0.5, turns=8, parent=clock_base)
sp2 = make_spring("spring2", (0.05, -0.20, 2.55), r_outer=0.08, height=0.5, turns=8, parent=clock_base)
sp3 = make_spring("spring3", (0.30, -0.20, 2.55), r_outer=0.08, height=0.5, turns=8, parent=clock_base)
springs = [sp1, sp2, sp3]

# ============ CARILLON BELL (top right of clock) ============
bell_e = empty("bell_e", (0.85, -0.30, 4.0), parent=clock_base)
# Bell body (cone-like)
smooth_cone("bell_body", r1=0.20, r2=0.15, depth=0.35, segs=20,
            loc=(0, 0, 0), parent=bell_e, mat_=M_BELL)
smooth_sphere("bell_top", r=0.16, loc=(0, 0, 0.18),
              parent=bell_e, mat_=M_BELL, scale=(1, 1, 0.5))
# Bell clapper (small sphere inside)
smooth_sphere("bell_clapper", r=0.05, loc=(0, 0, -0.10),
              parent=bell_e, mat_=M_GOLD)
# Hanging bracket
beveled_cube("bell_bracket", (0.04, 0.04, 0.30), loc=(0, 0, 0.40),
             parent=bell_e, mat_=M_BRASS)
beveled_cube("bell_bar", (0.30, 0.04, 0.04), loc=(0, 0, 0.55),
             parent=bell_e, mat_=M_BRASS)

# ============ HORLOGER TABLE (workbench) ============
table_base = empty("workbench", loc=(-5, 3, 0))
# Top
beveled_cube("bench_top", (3.5, 1.6, 0.10), bevel_offset=0.04,
             loc=(0, 0, 1.10), parent=table_base, mat_=M_WOOD_WORN)
# 4 legs
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        cyl(f"bench_leg_{x_idx}{y_idx}", r=0.08, depth=1.10, segs=10,
            loc=(x*1.55, y*0.70, 0.55), parent=table_base, mat_=M_WOOD_DARK)
# Stretchers between legs
beveled_cube("bench_str_f", (3.0, 0.04, 0.04), loc=(0, 0.65, 0.30),
             parent=table_base, mat_=M_WOOD_DARK)
beveled_cube("bench_str_b", (3.0, 0.04, 0.04), loc=(0, -0.65, 0.30),
             parent=table_base, mat_=M_WOOD_DARK)

# ===== TOOLS ON BENCH =====
# Wrench
wr = beveled_cube("wrench_handle", (0.04, 0.30, 0.04), bevel_offset=0.01,
                  loc=(-0.5, 0.3, 1.18), parent=table_base, mat_=M_TOOL)
cyl("wrench_head", r=0.06, depth=0.04, segs=10, loc=(-0.5, 0.48, 1.18),
    parent=table_base, mat_=M_TOOL)
# Screwdriver
sd = cyl("screwdriver_handle", r=0.025, depth=0.20, segs=10,
         loc=(-0.2, 0.2, 1.18), parent=table_base, mat_=M_TOOL_HANDLE)
sd.rotation_euler = (math.radians(90), 0, 0)
cyl("screwdriver_blade", r=0.008, depth=0.20, segs=8,
    loc=(-0.2, 0.40, 1.18), parent=table_base, mat_=M_SILVER).rotation_euler = (math.radians(90), 0, 0)

# Tweezers
beveled_cube("tweezers_l", (0.01, 0.18, 0.005), loc=(0.15, 0.25, 1.18),
             parent=table_base, mat_=M_SILVER).rotation_euler = (0, 0, math.radians(3))
beveled_cube("tweezers_r", (0.01, 0.18, 0.005), loc=(0.17, 0.25, 1.18),
             parent=table_base, mat_=M_SILVER).rotation_euler = (0, 0, math.radians(-3))

# Magnifying glass (loupe)
loupe_e = empty("loupe", (0.7, 0.30, 1.22), parent=table_base)
loupe_e.rotation_euler = (0, math.radians(35), 0)
cyl("loupe_handle", r=0.025, depth=0.35, segs=10,
    loc=(0, 0, -0.20), parent=loupe_e, mat_=M_TOOL_HANDLE)
cyl("loupe_ring", r=0.12, depth=0.04, segs=20,
    loc=(0, 0, 0), parent=loupe_e, mat_=M_BRASS)
cyl("loupe_lens", r=0.10, depth=0.02, segs=20,
    loc=(0, 0, 0), parent=loupe_e, mat_=M_GLASS)

# Open clock on bench (disassembled - 4 small gears + 2 hands)
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    g_x = 1.3 + 0.20*math.cos(a)
    g_y = 0.2 + 0.20*math.sin(a)
    small_g = gear(f"work_gear{i}", r_outer=0.08, r_inner=0.02, teeth=12, depth=0.02,
                   loc=(g_x, g_y, 1.16), parent=table_base, mat_=M_GEAR_BRASS)

# Small disassembled clock face
cyl("work_face", r=0.12, depth=0.015, segs=24, loc=(1.3, 0.2, 1.18),
    parent=table_base, mat_=M_DIAL_WHITE).rotation_euler = (0, 0, 0)

# 3 ressorts in jar
for i, x_off in enumerate((-1.0, -0.95, -0.85)):
    sp_jar = cyl(f"sp_jar{i}", r=0.05, depth=0.15, segs=10,
                 loc=(x_off, -0.30, 1.25), parent=table_base, mat_=M_GLASS)

# Notebook with sketches (open)
notebook_e = empty("notebook", (-1.3, 0.40, 1.18), parent=table_base)
notebook_e.rotation_euler = (0, 0, math.radians(-15))
beveled_cube("notebook_page_l", (0.35, 0.40, 0.01), loc=(-0.18, 0, 0.005),
             parent=notebook_e, mat_=M_PAPER)
beveled_cube("notebook_page_r", (0.35, 0.40, 0.01), loc=(0.18, 0, 0.005),
             parent=notebook_e, mat_=M_PAPER)
# Sketch lines on page
for i in range(4):
    beveled_cube(f"sketch_l{i}", (0.20, 0.02, 0.001),
                 loc=(-0.18, 0.15 - i*0.08, 0.012), parent=notebook_e, mat_=M_INK)
# Circle sketches
for i in range(3):
    cyl(f"sketch_circ{i}", r=0.05, depth=0.001, segs=14,
        loc=(0.10 + (i%2)*0.15, 0.10 - i*0.10, 0.012),
        parent=notebook_e, mat_=M_INK)

# CANDLE on bench
candle_e = empty("candle", (1.0, -0.30, 1.20), parent=table_base)
# Holder
cyl("candle_holder", r=0.06, depth=0.06, segs=12, loc=(0,0,0),
    parent=candle_e, mat_=M_BRASS)
cyl("candle_stick", r=0.04, depth=0.40, segs=12, loc=(0,0,0.22),
    parent=candle_e, mat_=M_CANDLE)
# Flame (outer + inner)
flame_outer = smooth_cone("c_flame_o", r1=0.05, r2=0.005, depth=0.16, segs=10,
                          loc=(0, 0, 0.50), parent=candle_e, mat_=M_CANDLE_FLAME)
flame_inner = smooth_cone("c_flame_i", r1=0.03, r2=0.003, depth=0.10, segs=8,
                          loc=(0, 0, 0.52), parent=candle_e, mat_=M_CANDLE_FLAME_I)

# ============ 12 WALL CLOCKS (on back wall) ============
wall_clocks = []
for i in range(12):
    row = i // 4
    col = i % 4
    wx = (col - 1.5) * 4
    wz = 3 + row * 2.5
    wc_e = empty(f"wallclock_e{i}", (wx, 11.8, wz))
    # Case (round)
    cyl(f"wc_case{i}", r=0.55, depth=0.20, segs=24,
        loc=(0, 0.05, 0), parent=wc_e, mat_=M_WOOD_RICH).rotation_euler = (math.radians(90), 0, 0)
    # Face dial
    cyl(f"wc_dial{i}", r=0.48, depth=0.04, segs=24,
        loc=(0, -0.10, 0), parent=wc_e, mat_=M_DIAL_WHITE).rotation_euler = (math.radians(90), 0, 0)
    # Center hub
    smooth_sphere(f"wc_hub{i}", r=0.05, loc=(0, -0.13, 0), parent=wc_e, mat_=M_GOLD)
    # 12 dot markers
    for j in range(12):
        a = j * math.pi * 2 / 12
        smooth_sphere(f"wc_dot{i}_{j}", r=0.025,
                      loc=(0.38*math.cos(a), -0.13, 0.38*math.sin(a)),
                      parent=wc_e, mat_=M_INK)
    # Hands
    hp = empty(f"wc_hp{i}", (0, -0.13, 0), parent=wc_e)
    hour_h = beveled_cube(f"wc_hour{i}", (0.025, 0.015, 0.25),
                         loc=(0, 0, 0.10), parent=hp, mat_=M_HAND_BLACK)
    # Set random start rotation
    hp.rotation_euler = (0, random.uniform(0, math.pi*2), 0)
    min_e_local = empty(f"wc_min_e{i}", (0, -0.13, 0), parent=wc_e)
    min_h = beveled_cube(f"wc_min{i}", (0.018, 0.012, 0.35),
                        loc=(0, 0, 0.15), parent=min_e_local, mat_=M_HAND_BLACK)
    min_e_local.rotation_euler = (0, random.uniform(0, math.pi*2), 0)
    wall_clocks.append({"hp": hp, "min_e": min_e_local,
                        "hour_speed": random.uniform(0.05, 0.10),
                        "min_speed": random.uniform(0.6, 1.0)})

# ============ CAT SLEEPING (on bench) ============
cat_base = empty("cat", loc=(0.5, 0.2, 1.20), parent=table_base)
cat_base.rotation_euler = (0, 0, math.radians(35))
# Body (curled sleeping)
smooth_sphere("cat_body", r=0.25, segs=22, rings=14, loc=(0, 0, 0.10),
              parent=cat_base, mat_=M_CAT_BLACK, scale=(1.8, 1.5, 0.9))
# Head tucked
cat_head = empty("cat_head_e", (0.35, 0.20, 0.10), parent=cat_base)
smooth_sphere("cat_h", r=0.18, segs=18, rings=12, loc=(0, 0, 0),
              parent=cat_head, mat_=M_CAT_BLACK, scale=(1, 0.9, 0.9))
# Ears
for side in (-1, 1):
    ear = smooth_cone(f"cat_ear_{side}", r1=0.06, r2=0.005, depth=0.14, segs=8,
                     loc=(side*0.10, 0.04, 0.16), parent=cat_head, mat_=M_CAT_BLACK)
    ear.rotation_euler = (math.radians(-15), math.radians(side*15), 0)
# Closed eyes (lines)
for side in (-1, 1):
    beveled_cube(f"cat_eye_{side}", (0.06, 0.01, 0.01),
                 loc=(side*0.06, -0.14, 0.02), parent=cat_head, mat_=M_CAT_EYE_CLOSED)
# Nose
smooth_sphere("cat_nose", r=0.02, loc=(0, -0.18, -0.04),
              parent=cat_head, mat_=mat("cat_pink", (0.85, 0.40, 0.55, 1.0), 0, 0.55))
# Tail (curled around body)
tail_e = empty("cat_tail_e", (-0.20, 0.15, 0.15), parent=cat_base)
for i in range(5):
    tseg = cyl(f"cat_tail{i}", r=0.04, depth=0.15, segs=10,
              loc=(0.15*math.sin(i*0.6), 0.15*math.cos(i*0.6), 0),
              parent=tail_e, mat_=M_CAT_BLACK)
    tseg.rotation_euler = (math.radians(i*15), 0, math.radians(i*30))

# ============ 30 DUST PARTICLES drift ============
dusts = []
for i in range(30):
    dx = random.uniform(-8, 8)
    dy = random.uniform(-2, 6)
    dz = random.uniform(1, 8)
    d = smooth_sphere(f"dust{i}", r=random.uniform(0.04, 0.08), segs=8, rings=6,
                     loc=(dx, dy, dz), mat_=M_DUST)
    d["_phase"] = random.uniform(0, math.pi*2)
    d["_base_x"] = dx; d["_base_y"] = dy; d["_base_z"] = dz
    d["_speed"] = random.uniform(0.3, 0.8)
    dusts.append(d)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Pendulum swing (X rotation around pivot, 30° amplitude)
for f in range(1, total_frames + 1, 2):
    t = (f - 1) / fps
    # Realistic pendulum motion ~1 Hz
    angle = math.sin(t * math.pi) * math.radians(25)
    pendulum_e.rotation_euler = (angle, 0, 0)
    pendulum_e.keyframe_insert("rotation_euler", frame=f)

# Hour hand spin (slow, 1 full turn in 6s for visual)
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    hour_e.rotation_euler = (0, math.radians(-100) - t * math.radians(60), 0)
    hour_e.keyframe_insert("rotation_euler", frame=f)
    # Minute hand fast
    min_e.rotation_euler = (0, math.radians(50) - t * math.radians(360), 0)
    min_e.keyframe_insert("rotation_euler", frame=f)

# Gears rotation (coupled rates - some positive, some negative)
for g in gears:
    speed = g["_speed"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Rotation around local Z (gear axis = world Y since rotated 90°)
        g.rotation_euler = (math.radians(90), t * speed, 0)
        g.keyframe_insert("rotation_euler", frame=f)

# Bell carillon swing
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    bell_e.rotation_euler = (math.sin(t * 3.0) * math.radians(15), 0, 0)
    bell_e.keyframe_insert("rotation_euler", frame=f)

# Candle flame flicker
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    s_o = 1 + math.sin(t * 7.0) * 0.20
    flame_outer.scale = (s_o, s_o, s_o)
    flame_outer.keyframe_insert("scale", frame=f)
    s_i = 1 + math.sin(t * 9.0 + 0.3) * 0.30
    flame_inner.scale = (s_i, s_i, s_i)
    flame_inner.keyframe_insert("scale", frame=f)

# Wall clocks tick (différentielles rates)
for wc in wall_clocks:
    hp = wc["hp"]; min_e_local = wc["min_e"]
    hour_speed = wc["hour_speed"]; min_speed = wc["min_speed"]
    base_hour = hp.rotation_euler.y
    base_min = min_e_local.rotation_euler.y
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        hp.rotation_euler = (0, base_hour + t * hour_speed, 0)
        hp.keyframe_insert("rotation_euler", frame=f)
        min_e_local.rotation_euler = (0, base_min + t * min_speed, 0)
        min_e_local.keyframe_insert("rotation_euler", frame=f)

# Lightning flashes (scale pulse, mostly off, flash bright)
for bolt in lightning_segs:
    phase = bolt["_phase"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Pulse on briefly, then off (peak around specific t values)
        flash_factor = max(0, math.sin(t * 0.8 + phase) - 0.7) * 3.3  # 0 to 1
        s = flash_factor * 1.0 + 0.001  # near zero when not flashing
        bolt.scale = (s, s, s)
        bolt.keyframe_insert("scale", frame=f)

# Dust drift
for d in dusts:
    phase = d["_phase"]; speed = d["_speed"]
    bx, by, bz = d["_base_x"], d["_base_y"], d["_base_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * 1.5
        y = by + math.cos(t * speed + phase) * 1.0
        z = bz + math.sin(t * speed * 0.7 + phase) * 1.2 + (t * 0.2) % 4.0
        s = 1 + math.sin(t * 4.0 + phase) * 0.3
        d.location = (x, y, z)
        d.scale = (s, s, s)
        d.keyframe_insert("location", frame=f)
        d.keyframe_insert("scale", frame=f)

# Cat sleeping breath (subtle scale)
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 1.2) * 0.025
    cat_base.scale = (s, s, s)
    cat_base.keyframe_insert("scale", frame=f)

# Springs subtle compression
for si, sp in enumerate(springs):
    phase = si * 0.7
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 1.8 + phase) * 0.05
        sp.scale = (1, 1, s)
        sp.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_grandfather_clock_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_grandfather_clock_workshop] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_grandfather_clock_workshop] Grandfather clock 4m + dial + 12 roman + 2 hands + pendulum sun face + 6 gears coupled + 3 springs + bell + carved case + workbench + tools + notebook + candle + 12 wall clocks + cat sleeping + 30 dust particles + lightning")
