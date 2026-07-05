"""
proc_tibetan_monastery_himalaya.py — 220e procédural AuroraIA (84e qualité)
Tibetan monastery Himalaya: ONE ground + 700 sky lanterns + 200 snowflakes + monastery + 4 stupas + 100 prayer flags + 8 monks + abbot + prayer wheel + 10 yaks + 3 eagles + Mt Everest
FIXES : 1 ground + 700 lanterns rising + 200 snowflakes thématiques signature
"""
import bpy, bmesh, math, random, os

random.seed(0x71B3220)

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

# Tibetan palette - cold dusk Himalaya
M_SKY = mat("sky", (0.35, 0.30, 0.55, 1.0), 0.0, 0.7, emission=(0.32,0.28,0.50), emission_strength=1.5)
M_MOON = mat("moon", (0.95, 0.92, 0.85, 1.0), 0.0, 0.20, emission=(0.95,0.92,0.85), emission_strength=10.0)
M_STAR = mat("star", (1.0, 1.0, 0.95, 1.0), 0.0, 0.20, emission=(1.0,1.0,0.95), emission_strength=10.0)

# Ground + snow
M_SNOW_GROUND = mat("snow_g", (0.92, 0.95, 1.0, 1.0), 0.0, 0.55, emission=(0.85,0.88,0.95), emission_strength=0.8)
M_SNOW_DEEP = mat("snow_d", (0.78, 0.82, 0.92, 1.0), 0.0, 0.65, emission=(0.72,0.76,0.85), emission_strength=0.6)
M_ROCK = mat("rock", (0.45, 0.42, 0.48, 1.0), 0.0, 0.85)
M_ROCK_DARK = mat("rock_d", (0.28, 0.25, 0.32, 1.0), 0.0, 0.85)
M_MOUNTAIN = mat("mountain", (0.55, 0.55, 0.65, 1.0), 0.0, 0.80)
M_MOUNTAIN_SNOW = mat("ms", (0.98, 0.98, 1.0, 1.0), 0.0, 0.45, emission=(0.92,0.94,0.98), emission_strength=1.0)

# Monastery
M_WALL_WHITE = mat("wall_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.70, emission=(0.85,0.82,0.75), emission_strength=0.5)
M_WALL_RED = mat("wall_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.65, emission=(0.70,0.18,0.16), emission_strength=0.6)
M_WALL_OCHRE = mat("wall_o", (0.85, 0.55, 0.20, 1.0), 0.0, 0.65, emission=(0.78,0.50,0.18), emission_strength=0.6)
M_ROOF_GOLD = mat("roof_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.92,0.78,0.28), emission_strength=1.2)
M_ROOF_RED = mat("roof_r", (0.60, 0.20, 0.18, 1.0), 0.0, 0.55, emission=(0.55,0.20,0.18), emission_strength=0.5)
M_DOOR_WOOD = mat("door", (0.40, 0.25, 0.15, 1.0), 0.0, 0.75, emission=(0.35,0.22,0.13), emission_strength=0.4)
M_WINDOW_GLOW = mat("win_g", (1.0, 0.78, 0.40, 1.0), 0.0, 0.10, emission=(1.0,0.78,0.40), emission_strength=6.0)

# Stupas
M_STUPA_WHITE = mat("stupa_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.45, emission=(0.88,0.85,0.82), emission_strength=0.7)
M_STUPA_GOLD = mat("stupa_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.92,0.78,0.28), emission_strength=1.0)

# Prayer flags (5 sacred colors)
M_FLAG_BLUE = mat("flag_b", (0.20, 0.45, 0.85, 1.0), 0.0, 0.55, emission=(0.18,0.42,0.78), emission_strength=0.9)
M_FLAG_WHITE = mat("flag_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.82), emission_strength=0.7)
M_FLAG_RED = mat("flag_r", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.78,0.18,0.16), emission_strength=0.9)
M_FLAG_GREEN = mat("flag_g", (0.25, 0.65, 0.30, 1.0), 0.0, 0.55, emission=(0.22,0.60,0.28), emission_strength=0.9)
M_FLAG_YELLOW = mat("flag_y", (1.0, 0.82, 0.25, 1.0), 0.0, 0.55, emission=(1.0,0.82,0.25), emission_strength=1.0)
M_ROPE = mat("rope", (0.45, 0.35, 0.20, 1.0), 0.0, 0.80)

# Monks
M_ROBE_DEEP_RED = mat("robe_r", (0.55, 0.15, 0.10, 1.0), 0.0, 0.70, emission=(0.50,0.15,0.10), emission_strength=0.5)
M_ROBE_ORANGE = mat("robe_o", (0.95, 0.45, 0.10, 1.0), 0.0, 0.60, emission=(0.90,0.45,0.10), emission_strength=0.8)
M_ROBE_GOLD = mat("robe_g", (1.0, 0.78, 0.30, 1.0), 0.4, 0.40, emission=(0.95,0.72,0.28), emission_strength=0.9)
M_SKIN_TIBET = mat("skin", (0.85, 0.60, 0.40, 1.0), 0.0, 0.55, emission=(0.78,0.55,0.38), emission_strength=0.4)
M_HAIR_SHAVED = mat("hair", (0.05, 0.04, 0.04, 1.0), 0.0, 0.85)

# Prayer wheel
M_WHEEL_GOLD = mat("wheel_g", (0.95, 0.72, 0.30, 1.0), 0.95, 0.20, emission=(0.92,0.72,0.28), emission_strength=1.2)
M_WHEEL_WOOD = mat("wheel_w", (0.50, 0.30, 0.20, 1.0), 0.0, 0.65)
M_WHEEL_GLYPH = mat("wheel_gl", (0.55, 0.18, 0.15, 1.0), 0.0, 0.45, emission=(0.50,0.18,0.15), emission_strength=0.8)

# Yaks
M_YAK_BLACK = mat("yak", (0.10, 0.08, 0.08, 1.0), 0.0, 0.85, emission=(0.08,0.06,0.06), emission_strength=0.3)
M_YAK_BROWN = mat("yak_b", (0.35, 0.22, 0.12, 1.0), 0.0, 0.80, emission=(0.30,0.20,0.10), emission_strength=0.3)
M_YAK_HORN = mat("yak_h", (0.85, 0.75, 0.55, 1.0), 0.2, 0.55)

# Eagles
M_EAGLE_BROWN = mat("eagle", (0.35, 0.22, 0.12, 1.0), 0.0, 0.65, emission=(0.30,0.20,0.10), emission_strength=0.4)
M_EAGLE_HEAD = mat("eagle_h", (0.92, 0.85, 0.65, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.60), emission_strength=0.5)
M_EAGLE_BEAK = mat("eagle_b", (1.0, 0.78, 0.20, 1.0), 0.5, 0.40, emission=(0.95,0.72,0.18), emission_strength=0.5)
M_EAGLE_EYE = mat("eagle_e", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.30), emission_strength=10.0)

# Incense + brazier
M_BRASS = mat("brass", (0.85, 0.62, 0.25, 1.0), 0.85, 0.25, emission=(0.80,0.58,0.22), emission_strength=0.6)
M_INCENSE_SMOKE = mat("smoke", (0.55, 0.75, 1.0, 1.0), 0.0, 0.30, emission=(0.55,0.75,1.0), emission_strength=2.5, alpha=0.55)

# Sky lanterns (signature rising)
M_LANTERN_PAPER = mat("lant_p", (1.0, 0.72, 0.30, 1.0), 0.0, 0.30, emission=(1.0,0.72,0.30), emission_strength=14.0, alpha=0.85)
M_LANTERN_FRAME = mat("lant_f", (0.55, 0.35, 0.18, 1.0), 0.0, 0.75)

# Snowflakes
M_SNOW_FLAKE = mat("snowflake", (0.95, 0.98, 1.0, 1.0), 0.0, 0.15, emission=(0.92,0.95,1.0), emission_strength=3.0)

# Singing bowls
M_BOWL = mat("bowl", (0.85, 0.62, 0.20, 1.0), 0.85, 0.25, emission=(0.80,0.58,0.18), emission_strength=0.5)

# ============ SKY + MOON + STARS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
moon_e = empty("moon_e", (25, 50, 35))
smooth_sphere("moon", r=4.0, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)
for i in range(3):
    smooth_sphere(f"moon_halo{i}", r=4.0 + (i+1)*1.2, loc=(0, 0, 0), parent=moon_e, mat_=M_MOON)

# 200 stars
for i in range(200):
    a = random.uniform(0, math.pi*2)
    phi = random.uniform(math.pi/6, math.pi/2.2)
    r_star = 115
    sx = r_star * math.cos(phi) * math.cos(a)
    sy = r_star * math.cos(phi) * math.sin(a)
    sz = r_star * math.sin(phi) * 0.4
    smooth_sphere(f"star{i}", r=random.uniform(0.18, 0.45), segs=10, rings=8,
                  loc=(sx, sy, sz), mat_=M_STAR)

# ============ MT EVEREST + HIMALAYA BACKGROUND ============
everest_e = empty("everest", loc=(0, 40, 8))
# Main pyramid peak (signature Everest)
everest_main = smooth_cone("everest_m", r1=18, r2=0.8, depth=20, segs=10,
                             loc=(0, 0, 0), parent=everest_e, mat_=M_MOUNTAIN)
everest_main.rotation_euler = (math.radians(8), 0, math.radians(10))
# Snow cap top
smooth_cone("everest_snow", r1=5.0, r2=0.6, depth=6, segs=12,
            loc=(0, 0, 7.5), parent=everest_e, mat_=M_MOUNTAIN_SNOW)
# Side peaks
for side, side_mul in zip(("L", "R"), (-1, 1)):
    smooth_cone(f"peak_{side}", r1=14, r2=1.5, depth=14, segs=18,
                loc=(side_mul*22, -4, -5), parent=everest_e, mat_=M_MOUNTAIN)
    smooth_cone(f"peak_snow_{side}", r1=5.0, r2=1.2, depth=4, segs=18,
                loc=(side_mul*22, -4, 4.5), parent=everest_e, mat_=M_MOUNTAIN_SNOW)
    smooth_cone(f"peak_far_{side}", r1=16, r2=2.5, depth=11, segs=16,
                loc=(side_mul*36, -2, -5), parent=everest_e, mat_=M_MOUNTAIN)
    smooth_cone(f"peak_far_snow_{side}", r1=5.5, r2=2.0, depth=2.5, segs=16,
                loc=(side_mul*36, -2, 3.5), parent=everest_e, mat_=M_MOUNTAIN_SNOW)

# ============ ONE clean snow ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_SNOW_GROUND)

# Snow drifts + rocks (organic 3D variations)
for i in range(40):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(10, 40)
    smooth_sphere(f"drift{i}", r=random.uniform(0.6, 1.6),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_SNOW_DEEP if i % 2 == 0 else M_SNOW_GROUND,
                  scale=(1.6, 1.4, 0.30))

for i in range(25):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(15, 38)
    smooth_sphere(f"rock{i}", r=random.uniform(0.5, 1.2),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.30),
                  mat_=M_ROCK if i % 2 == 0 else M_ROCK_DARK,
                  scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3),
                         random.uniform(0.5,0.85)))

# ============ TIBETAN MONASTERY (massive) ============
monastery_e = empty("monastery", loc=(0, 14, 0))
# Main stone base
beveled_cube("m_base", (18, 12, 1.5), bevel_offset=0.08, loc=(0, 0, 0.75),
             parent=monastery_e, mat_=M_WALL_WHITE)
# Lower walls (white)
beveled_cube("m_lower", (16, 11, 4), bevel_offset=0.06, loc=(0, 0, 3.5),
             parent=monastery_e, mat_=M_WALL_WHITE)
# Red band (signature Tibetan)
beveled_cube("m_red_band", (16.2, 11.2, 0.6), bevel_offset=0.04, loc=(0, 0, 5.8),
             parent=monastery_e, mat_=M_WALL_RED)
# Upper walls (ochre/red)
beveled_cube("m_upper", (14, 10, 3.5), bevel_offset=0.06, loc=(0, 0, 7.85),
             parent=monastery_e, mat_=M_WALL_OCHRE)
# Upper red band
beveled_cube("m_red_band2", (14.2, 10.2, 0.4), bevel_offset=0.03, loc=(0, 0, 9.80),
             parent=monastery_e, mat_=M_WALL_RED)
# Inclined pagoda roof (signature Tibetan/Chinese influence)
for side in (-1, 1):
    roof = beveled_cube(f"m_roof_{side}", (16, 6, 0.30), bevel_offset=0.04,
                       loc=(0, side*3.5, 11.0), parent=monastery_e, mat_=M_ROOF_GOLD)
    roof.rotation_euler = (math.radians(side*-30), 0, 0)
# Roof ridge
beveled_cube("m_ridge", (16, 0.4, 0.30), bevel_offset=0.03,
             loc=(0, 0, 12.2), parent=monastery_e, mat_=M_ROOF_GOLD)
# 4 corner roof horns curl up (signature pagoda)
for x_idx, x in enumerate((-1, 1)):
    for y_idx, y in enumerate((-1, 1)):
        horn = smooth_cone(f"m_horn{x_idx}{y_idx}", r1=0.15, r2=0.02, depth=0.80, segs=10,
                           loc=(x*7.5, y*3.0, 12.0), parent=monastery_e, mat_=M_ROOF_GOLD)
        horn.rotation_euler = (math.radians(y*30), math.radians(x*30), 0)
# Top spire/finial
smooth_cone("m_spire", r1=0.30, r2=0.05, depth=2.0, segs=14,
            loc=(0, 0, 13.5), parent=monastery_e, mat_=M_ROOF_GOLD)
smooth_sphere("m_spire_orb", r=0.25, loc=(0, 0, 14.8),
              parent=monastery_e, mat_=M_ROOF_GOLD)
# Massive entrance door (red)
beveled_cube("m_door", (2.5, 0.3, 4.0), bevel_offset=0.05, loc=(0, -5.6, 3.0),
             parent=monastery_e, mat_=M_DOOR_WOOD)
# Gold door handles
for side in (-1, 1):
    smooth_sphere(f"m_door_h{side}", r=0.12, loc=(side*0.5, -5.75, 3.0),
                  parent=monastery_e, mat_=M_ROOF_GOLD)
# Windows (glowing)
for i in range(8):
    wx = (i - 3.5) * 2.0
    beveled_cube(f"m_win{i}", (1.0, 0.20, 1.0), bevel_offset=0.03,
                 loc=(wx, -5.55, 2.5), parent=monastery_e, mat_=M_WINDOW_GLOW)
    # Frame
    for fi in range(2):
        beveled_cube(f"m_win_fr_h{i}_{fi}", (1.1, 0.05, 0.05),
                     loc=(wx, -5.60, 2.0 + fi*1.0), parent=monastery_e, mat_=M_DOOR_WOOD)
# Upper windows
for i in range(6):
    wx = (i - 2.5) * 2.5
    beveled_cube(f"m_win_up{i}", (0.80, 0.20, 0.80), bevel_offset=0.03,
                 loc=(wx, -5.05, 8.0), parent=monastery_e, mat_=M_WINDOW_GLOW)

# Steps in front
for i in range(5):
    beveled_cube(f"m_step{i}", (8, 0.50, 0.30), bevel_offset=0.04,
                 loc=(0, -7 - i*0.6, 0.15 + i*0.30), parent=monastery_e, mat_=M_WALL_WHITE)

# ============ 4 STUPAS ============
def make_stupa(name, loc, scale=1.0):
    base = empty(name, loc)
    # Base square platform
    beveled_cube(f"{name}_base", (1.8*scale, 1.8*scale, 0.6*scale), bevel_offset=0.06,
                 loc=(0, 0, 0.30*scale), parent=base, mat_=M_STUPA_WHITE)
    # Stepped pyramid base
    for s in range(3):
        beveled_cube(f"{name}_step{s}", (1.6*scale - s*0.25*scale, 1.6*scale - s*0.25*scale, 0.20*scale),
                     bevel_offset=0.04,
                     loc=(0, 0, 0.60*scale + s*0.25*scale), parent=base, mat_=M_STUPA_WHITE)
    # Bell-shaped dome (signature)
    smooth_sphere(f"{name}_dome", r=0.85*scale, segs=22, rings=14,
                  loc=(0, 0, 1.95*scale), parent=base, mat_=M_STUPA_WHITE,
                  scale=(1, 1, 0.95))
    # Harmika square box on top
    beveled_cube(f"{name}_harmika", (0.45*scale, 0.45*scale, 0.40*scale), bevel_offset=0.03,
                 loc=(0, 0, 2.90*scale), parent=base, mat_=M_STUPA_WHITE)
    # 13 ring spire (signature dharma wheel rings)
    for r in range(13):
        cyl(f"{name}_ring{r}", r=0.25*scale - r*0.01*scale, depth=0.10*scale, segs=14,
            loc=(0, 0, 3.20*scale + r*0.13*scale), parent=base, mat_=M_STUPA_GOLD)
    # Crown lotus
    smooth_sphere(f"{name}_lotus", r=0.20*scale, loc=(0, 0, 4.95*scale),
                  parent=base, mat_=M_STUPA_GOLD, scale=(1.2, 1.2, 0.8))
    # Top moon + sun + flame
    smooth_sphere(f"{name}_moon_sym", r=0.12*scale, loc=(0, 0, 5.20*scale),
                  parent=base, mat_=M_STUPA_GOLD, scale=(1.3, 1.3, 0.4))
    smooth_sphere(f"{name}_sun_sym", r=0.10*scale, loc=(0, 0, 5.35*scale),
                  parent=base, mat_=M_STUPA_GOLD)
    smooth_cone(f"{name}_flame_sym", r1=0.06*scale, r2=0.01*scale, depth=0.30*scale, segs=10,
                loc=(0, 0, 5.60*scale), parent=base, mat_=M_ROOF_GOLD)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

stupas = []
stupa_pos = [(-15, 6, 0), (15, 6, 0), (-12, -8, 0), (12, -8, 0)]
for i, (sx, sy, sz) in enumerate(stupa_pos):
    s = make_stupa(f"stupa{i}", (sx, sy, sz), scale=1.2)
    stupas.append(s)

# ============ 100 PRAYER FLAGS strung between poles ============
flag_colors = [M_FLAG_BLUE, M_FLAG_WHITE, M_FLAG_RED, M_FLAG_GREEN, M_FLAG_YELLOW]
# 5 strings of flags
flag_objs = []
for line in range(5):
    line_angle = (line / 5.0) * math.pi - math.pi/2
    cx = math.cos(line_angle) * 14
    cy = math.sin(line_angle) * 14
    # 2 poles per line
    pole1_pos = (cx - math.sin(line_angle) * 6, cy + math.cos(line_angle) * 6, 0)
    pole2_pos = (cx + math.sin(line_angle) * 6, cy - math.cos(line_angle) * 6, 0)
    # Poles
    cyl(f"flag_pole_{line}_a", r=0.10, depth=4.0, segs=10,
        loc=(pole1_pos[0], pole1_pos[1], 2.0), mat_=M_DOOR_WOOD)
    cyl(f"flag_pole_{line}_b", r=0.10, depth=4.0, segs=10,
        loc=(pole2_pos[0], pole2_pos[1], 2.0), mat_=M_DOOR_WOOD)
    # 20 flags per line
    for fi in range(20):
        t_param = fi / 20.0
        flag_x = pole1_pos[0] + (pole2_pos[0] - pole1_pos[0]) * t_param
        flag_y = pole1_pos[1] + (pole2_pos[1] - pole1_pos[1]) * t_param
        # Rope sag (parabolic)
        rope_sag = 0.5 * 4 * t_param * (1 - t_param)
        flag_z = 3.5 - rope_sag
        flag_e = empty(f"flag_e_{line}_{fi}", (flag_x, flag_y, flag_z))
        flag_e.rotation_euler = (0, 0, line_angle + math.pi/2)
        # Flag itself
        beveled_cube(f"flag_{line}_{fi}", (0.40, 0.04, 0.30), bevel_offset=0.02,
                     loc=(0, 0, -0.15), parent=flag_e,
                     mat_=flag_colors[fi % 5])
        flag_e["_phase"] = random.uniform(0, math.pi*2)
        flag_objs.append(flag_e)
    # Rope between poles
    rope_segs = 12
    for ri in range(rope_segs):
        t_p = ri / float(rope_segs - 1)
        rx = pole1_pos[0] + (pole2_pos[0] - pole1_pos[0]) * t_p
        ry = pole1_pos[1] + (pole2_pos[1] - pole1_pos[1]) * t_p
        rz = 3.8 - 0.5 * 4 * t_p * (1 - t_p)
        smooth_sphere(f"rope_{line}_{ri}", r=0.04, segs=8, rings=6,
                      loc=(rx, ry, rz), mat_=M_ROPE)

# ============ 8 MONKS + ABBOT chanting in semi-circle ============
def make_monk(name, loc, robe_mat, is_abbot=False, action="chant", facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Sitting body (cross-legged cone)
    smooth_cone(f"{name}_robe", r1=0.55*scale, r2=0.40*scale, depth=0.85*scale, segs=16,
                loc=(0, 0, 0.45*scale), parent=base, mat_=robe_mat)
    # Inner robe (orange showing)
    smooth_cone(f"{name}_inner", r1=0.42*scale, r2=0.35*scale, depth=0.50*scale, segs=14,
                loc=(0, 0, 0.40*scale), parent=base, mat_=M_ROBE_ORANGE)
    # Torso wrapped in robe
    beveled_cube(f"{name}_torso", (0.42*scale, 0.25*scale, 0.55*scale), bevel_offset=0.05,
                 loc=(0, 0, 1.15*scale), parent=base, mat_=robe_mat)
    # Shoulder drape (signature monk robe)
    drape = beveled_cube(f"{name}_drape", (0.45*scale, 0.10*scale, 0.55*scale), bevel_offset=0.03,
                         loc=(0, -0.18*scale, 1.15*scale), parent=base, mat_=M_ROBE_ORANGE)
    drape.rotation_euler = (0, 0, math.radians(15))
    # Neck
    cyl(f"{name}_neck", r=0.09*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 1.50*scale), parent=base, mat_=M_SKIN_TIBET)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 1.68*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_TIBET)
    # Bald shaved head (signature monk)
    smooth_sphere(f"{name}_bald", r=0.182*scale, loc=(0, 0, 0.01*scale),
                  parent=head_e, mat_=M_SKIN_TIBET)
    # Eyes (closed/serene)
    for side in (-1, 1):
        beveled_cube(f"{name}_eye{side}", (0.04*scale, 0.04*scale, 0.005*scale),
                     loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                     mat_=mat(f"{name}_eb{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Eyebrows
    for side in (-1, 1):
        beveled_cube(f"{name}_brow{side}", (0.06*scale, 0.02*scale, 0.02*scale),
                     loc=(side*0.06*scale, -0.13*scale, 0.06*scale), parent=head_e,
                     mat_=M_HAIR_SHAVED)
    # Earlobes (long signature Buddha)
    for side in (-1, 1):
        cyl(f"{name}_lobe{side}", r=0.04*scale, depth=0.15*scale, segs=10,
            loc=(side*0.18*scale, 0.04*scale, -0.06*scale), parent=head_e, mat_=M_SKIN_TIBET)
    # Abbot has tall ceremonial hat
    if is_abbot:
        # Yellow hat (Gelug school signature)
        cyl(f"{name}_hat_b", r=0.20*scale, depth=0.10*scale, segs=18,
            loc=(0, 0, 0.20*scale), parent=head_e, mat_=M_FLAG_YELLOW)
        # Crest fan
        for cf in range(7):
            cfa = (cf - 3) * 0.30
            f_obj = beveled_cube(f"{name}_crest{cf}", (0.04*scale, 0.05*scale, 0.30*scale), bevel_offset=0.02,
                                 loc=(math.sin(cfa)*0.20*scale, 0, 0.40*scale),
                                 parent=head_e, mat_=M_FLAG_YELLOW)
            f_obj.rotation_euler = (cfa*0.3, 0, 0)
    # Arms - prayer position
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.28*scale, 0, 1.45*scale), parent=base)
        sh.rotation_euler = (math.radians(-80), 0, math.radians(side*-30))
        # Sleeve
        beveled_cube(f"{name}_sleeve{side_idx}", (0.18*scale, 0.18*scale, 0.40*scale), bevel_offset=0.03,
                     loc=(0, 0, -0.20*scale), parent=sh, mat_=robe_mat)
        cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.55*scale), parent=sh, mat_=M_SKIN_TIBET)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08*scale, loc=(0, 0, -0.72*scale),
                      parent=sh, mat_=M_SKIN_TIBET)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

monks = []
monk_specs = [
    ("monk1", (-6, 4, 0), M_ROBE_DEEP_RED, False, math.radians(0)),
    ("monk2", (-3, 5, 0), M_ROBE_DEEP_RED, False, math.radians(-10)),
    ("monk3", (3, 5, 0), M_ROBE_DEEP_RED, False, math.radians(10)),
    ("monk4", (6, 4, 0), M_ROBE_DEEP_RED, False, math.radians(20)),
    ("monk5", (-7, 0, 0), M_ROBE_DEEP_RED, False, math.radians(45)),
    ("monk6", (-5, -3, 0), M_ROBE_DEEP_RED, False, math.radians(60)),
    ("monk7", (5, -3, 0), M_ROBE_DEEP_RED, False, math.radians(-60)),
    ("monk8", (7, 0, 0), M_ROBE_DEEP_RED, False, math.radians(-45)),
]
for spec in monk_specs:
    name, loc, robe, abbot, fac = spec
    m = make_monk(name, loc, robe, is_abbot=abbot, action="chant", facing=fac)
    monks.append(m)
# Abbot center (taller)
abbot = make_monk("abbot", (0, 3, 0), M_ROBE_GOLD, is_abbot=True,
                  action="chant", facing=math.radians(180), scale=1.2)
monks.append(abbot)

# ============ GIANT PRAYER WHEEL ============
pwheel_e = empty("pwheel", loc=(-10, -2, 0))
# Stone base
beveled_cube("pw_base", (1.8, 1.8, 0.5), bevel_offset=0.05,
             loc=(0, 0, 0.25), parent=pwheel_e, mat_=M_WALL_WHITE)
# Wooden frame upright posts
for side in (-1, 1):
    cyl(f"pw_post_{side}", r=0.10, depth=3.0, segs=12,
        loc=(side*0.7, 0, 2.0), parent=pwheel_e, mat_=M_WHEEL_WOOD)
# Top crossbeam
beveled_cube("pw_cross", (1.6, 0.15, 0.20), bevel_offset=0.03,
             loc=(0, 0, 3.5), parent=pwheel_e, mat_=M_WHEEL_WOOD)
# Axle
cyl("pw_axle", r=0.05, depth=1.5, segs=10,
    loc=(0, 0, 2.0), parent=pwheel_e, mat_=M_WHEEL_WOOD).rotation_euler = (0, math.radians(90), 0)
# WHEEL ITSELF (cylindrical drum)
wheel_drum = empty("pw_drum", (0, 0, 2.0), parent=pwheel_e)
wheel_drum.rotation_euler = (0, math.radians(90), 0)
cyl("pw_drum_main", r=0.45, depth=1.0, segs=24, loc=(0, 0, 0),
    parent=wheel_drum, mat_=M_WHEEL_GOLD)
# Glyphs on drum
for gi in range(8):
    ga = (gi / 8.0) * math.pi * 2
    glyph = beveled_cube(f"pw_glyph{gi}", (0.10, 0.06, 0.20), bevel_offset=0.02,
                         loc=(0.47*math.cos(ga), 0.20, 0.47*math.sin(ga)),
                         parent=wheel_drum, mat_=M_WHEEL_GLYPH)
    glyph.rotation_euler = (ga, math.radians(90), 0)
# Top decorations on drum
cyl("pw_drum_top", r=0.50, depth=0.10, segs=24, loc=(0, 0.55, 0),
    parent=wheel_drum, mat_=M_WHEEL_GOLD)
cyl("pw_drum_btm", r=0.50, depth=0.10, segs=24, loc=(0, -0.55, 0),
    parent=wheel_drum, mat_=M_WHEEL_GOLD)

# ============ 10 TIBETAN YAKS ============
def make_yak(name, loc, body_mat=M_YAK_BLACK, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # MASSIVE body (signature yak)
    smooth_sphere(f"{name}_body", r=0.70, segs=20, rings=14, loc=(0, 0, 1.20),
                  parent=base, mat_=body_mat, scale=(1.9, 1.1, 1.0))
    # Long shaggy fur skirt (signature yak coat)
    for fi in range(8):
        fa = (fi / 8.0) * math.pi * 2
        for sk_idx in range(3):
            beveled_cube(f"{name}_fur{fi}_{sk_idx}", (0.10, 0.06, 0.65), bevel_offset=0.02,
                         loc=(0.75*math.cos(fa), 0.50*math.sin(fa) - sk_idx*0.08,
                              0.50 - sk_idx*0.10), parent=base, mat_=body_mat)
    # Hump shoulders
    smooth_sphere(f"{name}_hump", r=0.40, loc=(0.30, 0, 1.55),
                  parent=base, mat_=body_mat, scale=(1.2, 1.0, 1.2))
    # Neck
    neck = beveled_cube(f"{name}_neck", (0.45, 0.40, 0.50), bevel_offset=0.05,
                       loc=(0.95, 0, 1.30), parent=base, mat_=body_mat)
    # Head
    head_e = empty(f"{name}_he", (1.35, 0, 1.40), parent=base)
    beveled_cube(f"{name}_head", (0.50, 0.32, 0.35), bevel_offset=0.05,
                 loc=(0, 0, 0), parent=head_e, mat_=body_mat)
    # Muzzle
    smooth_sphere(f"{name}_muzzle", r=0.20, loc=(0.35, 0, -0.10),
                  parent=head_e, mat_=body_mat, scale=(1, 1, 0.7))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04,
                      loc=(0.10, side*0.16, 0.08), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.4))
    # Horns (signature long curved)
    for side in (-1, 1):
        horn = smooth_cone(f"{name}_horn{side}", r1=0.06, r2=0.02, depth=0.60, segs=10,
                           loc=(-0.05, side*0.20, 0.25), parent=head_e, mat_=M_YAK_HORN)
        horn.rotation_euler = (math.radians(-15), math.radians(side*35), math.radians(side*-10))
    # Ears
    for side in (-1, 1):
        ear = beveled_cube(f"{name}_ear{side}", (0.06, 0.15, 0.04),
                          loc=(-0.10, side*0.25, 0.15), parent=head_e, mat_=body_mat)
        ear.rotation_euler = (0, 0, math.radians(side*30))
    # 4 legs (short stocky)
    for x_idx, x in enumerate((0.55, -0.55)):
        for y_idx, y in enumerate((-0.40, 0.40)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.13, depth=0.75, segs=10,
                loc=(x, y, 0.40), parent=base, mat_=body_mat)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.14, depth=0.10, segs=10,
                loc=(x, y, 0.05), parent=base, mat_=M_YAK_HORN)
    # Tail (tufted)
    cyl(f"{name}_tail", r=0.06, depth=0.70, segs=10,
        loc=(-0.95, 0, 1.10), parent=base, mat_=body_mat)
    smooth_sphere(f"{name}_tail_tuft", r=0.20, loc=(-1.0, 0, 0.50),
                  parent=base, mat_=body_mat)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

yaks = []
yak_pos = [(-22, -2, 0), (-19, 0, 0), (-21, -5, 0), (-25, -8, 0), (-18, -10, 0),
           (22, -2, 0), (19, 0, 0), (21, -5, 0), (25, -8, 0), (18, -10, 0)]
for i, (yx, yy, yz) in enumerate(yak_pos):
    yak_col = M_YAK_BLACK if i % 2 == 0 else M_YAK_BROWN
    yak_fac = math.radians(random.uniform(-30, 30) + (90 if yx > 0 else -90))
    y = make_yak(f"yak{i}", (yx, yy, yz), body_mat=yak_col, facing=yak_fac)
    yaks.append(y)

# ============ 3 HIMALAYAN EAGLES ============
def make_eagle(name, loc):
    base = empty(name, loc)
    # Body
    smooth_sphere(f"{name}_body", r=0.40, segs=20, rings=14, loc=(0, 0, 0),
                  parent=base, mat_=M_EAGLE_BROWN, scale=(1.8, 1, 1))
    # Head
    head_e = empty(f"{name}_he", (0.60, 0, 0.10), parent=base)
    smooth_sphere(f"{name}_head", r=0.25, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_EAGLE_HEAD)
    # Hooked beak
    beak_e = empty(f"{name}_be", (0.20, 0, -0.05), parent=head_e)
    smooth_cone(f"{name}_beak_main", r1=0.10, r2=0.02, depth=0.20, segs=10,
                loc=(0, 0, 0), parent=beak_e, mat_=M_EAGLE_BEAK).rotation_euler = (0, math.radians(90), 0)
    smooth_cone(f"{name}_beak_hook", r1=0.05, r2=0.005, depth=0.10, segs=8,
                loc=(0.18, 0, -0.05), parent=beak_e,
                mat_=M_EAGLE_BEAK).rotation_euler = (math.radians(-30), math.radians(90), 0)
    # Eyes (golden glow)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.05,
                      loc=(0.08, side*0.12, 0.10), parent=head_e, mat_=M_EAGLE_EYE)
    # Wings spread wide (signature eagle)
    wings = []
    for side in (-1, 1):
        w_e = empty(f"{name}_we{side}", (0, side*0.30, 0.05), parent=base)
        # Wing main
        beveled_cube(f"{name}_w_m{side}", (0.60, 1.30, 0.06), bevel_offset=0.03,
                     loc=(0, side*0.70, 0), parent=w_e, mat_=M_EAGLE_BROWN)
        # Wing tip primary feathers (5 fingers - signature)
        for fi in range(5):
            beveled_cube(f"{name}_wf{side}_{fi}", (0.40, 0.10, 0.04),
                         loc=(0.15 + (fi-2)*0.10, side*1.40, 0),
                         parent=w_e, mat_=M_EAGLE_BROWN)
        wings.append((w_e, side))
    # Tail fan
    for ti in range(5):
        ta = (ti - 2) * 0.20
        tail_f = beveled_cube(f"{name}_tail{ti}", (0.40, 0.10, 0.04),
                              loc=(-0.55 - ti*0.05, math.sin(ta)*0.25, 0),
                              parent=base, mat_=M_EAGLE_BROWN)
        tail_f.rotation_euler = (0, 0, ta)
    # Talons
    for side in (-1, 1):
        cyl(f"{name}_talon{side}", r=0.04, depth=0.20, segs=8,
            loc=(0, side*0.10, -0.30), parent=base, mat_=M_EAGLE_BEAK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "wings": wings}

eagles = [
    make_eagle("eagle1", (-12, 18, 15)),
    make_eagle("eagle2", (12, 18, 18)),
    make_eagle("eagle3", (0, -20, 20)),
]

# ============ 4 BRAZIERS WITH INCENSE SMOKE ============
braziers = []
brazier_pos = [(-7, -8, 0), (7, -8, 0), (-3, -10, 0), (3, -10, 0)]
for i, (bx, by, bz) in enumerate(brazier_pos):
    b_e = empty(f"brazier{i}", (bx, by, bz))
    # Brass body
    cyl(f"br_body{i}", r=0.30, depth=0.50, segs=18,
        loc=(0, 0, 0.50), parent=b_e, mat_=M_BRASS)
    # Wider top rim
    cyl(f"br_rim{i}", r=0.40, depth=0.10, segs=18,
        loc=(0, 0, 0.80), parent=b_e, mat_=M_BRASS)
    # Glyphs
    for gi in range(6):
        ga = (gi / 6.0) * math.pi * 2
        smooth_sphere(f"br_g{i}_{gi}", r=0.06,
                      loc=(0.30*math.cos(ga), 0.30*math.sin(ga), 0.50),
                      parent=b_e, mat_=M_WHEEL_GLYPH, scale=(1, 0.3, 1))
    # Incense sticks bundle
    for st in range(5):
        sa = (st / 5.0) * math.pi * 2
        st_obj = cyl(f"br_st{i}_{st}", r=0.015, depth=0.50, segs=6,
                     loc=(0.05*math.cos(sa), 0.05*math.sin(sa), 1.10),
                     parent=b_e, mat_=M_DOOR_WOOD)
    # Smoke column (signature spiral)
    smoke_e = empty(f"br_smoke_e{i}", (0, 0, 1.40), parent=b_e)
    for si in range(8):
        s_z = si * 0.5
        s_x = math.sin(si * 0.7) * 0.20
        s_y = math.cos(si * 0.7) * 0.20
        smooth_sphere(f"br_smoke{i}_{si}", r=0.20 + si*0.04,
                      loc=(s_x, s_y, s_z), parent=smoke_e, mat_=M_INCENSE_SMOKE)
    b_e["_phase"] = random.uniform(0, math.pi*2)
    braziers.append({"e": b_e, "smoke": smoke_e})

# ============ SINGING BOWLS ROW ============
bowls = []
for bi in range(5):
    bx = (bi - 2) * 0.8
    b_e = empty(f"bowl{bi}", (bx, 7, 0))
    # Bowl
    smooth_sphere(f"bowl_b{bi}", r=0.25, segs=18, rings=12,
                  loc=(0, 0, 0.10), parent=b_e, mat_=M_BOWL,
                  scale=(1, 1, 0.65))
    # Cushion
    smooth_sphere(f"bowl_cush{bi}", r=0.25, loc=(0, 0, -0.05),
                  parent=b_e, mat_=M_ROBE_DEEP_RED, scale=(1, 1, 0.30))
    # Mallet
    cyl(f"bowl_mal{bi}", r=0.020, depth=0.20, segs=8,
        loc=(0.20, 0, 0.20), parent=b_e, mat_=M_WHEEL_WOOD)
    smooth_sphere(f"bowl_mal_top{bi}", r=0.05, loc=(0.30, 0, 0.20),
                  parent=b_e, mat_=M_WHEEL_WOOD)
    bowls.append(b_e)

# ============================================================
# ⭐ 700 SKY LANTERNS rising + 200 SNOWFLAKES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
# 700 paper sky lanterns rising (signature)
lanterns = []
for i in range(700):
    px = random.uniform(-42, 42)
    py = random.uniform(-42, 42)
    pz = random.uniform(0.5, 32)
    l_e = empty(f"lant{i}", (px, py, pz))
    # Paper lantern body
    smooth_sphere(f"lant_b{i}", r=random.uniform(0.10, 0.18),
                  segs=12, rings=8, loc=(0, 0, 0),
                  parent=l_e, mat_=M_LANTERN_PAPER, scale=(1, 1, 1.4))
    # Bottom frame
    cyl(f"lant_fr{i}", r=0.06, depth=0.02, segs=8,
        loc=(0, 0, -0.10), parent=l_e, mat_=M_LANTERN_FRAME)
    # Flame inside
    smooth_sphere(f"lant_fl{i}", r=0.04, loc=(0, 0, -0.06),
                  parent=l_e, mat_=M_FLAG_YELLOW if i % 3 == 0 else M_LANTERN_PAPER)
    l_e["_phase"] = random.uniform(0, math.pi*2)
    l_e["_base_x"] = px; l_e["_base_y"] = py; l_e["_base_z"] = pz
    l_e["_speed"] = random.uniform(0.3, 1.0)
    l_e["_drift_x"] = random.uniform(-0.6, 0.6)
    l_e["_drift_y"] = random.uniform(-0.6, 0.6)
    lanterns.append(l_e)

# 200 snowflakes falling
snowflakes = []
for i in range(200):
    px = random.uniform(-42, 42)
    py = random.uniform(-42, 42)
    pz = random.uniform(2, 28)
    sf = smooth_sphere(f"sf{i}", r=random.uniform(0.06, 0.12), segs=10, rings=6,
                       loc=(px, py, pz), mat_=M_SNOW_FLAKE,
                       scale=(1.5, 1.5, 0.3))
    sf["_phase"] = random.uniform(0, math.pi*2)
    sf["_base_x"] = px; sf["_base_y"] = py; sf["_base_z"] = pz
    sf["_speed"] = random.uniform(0.8, 1.8)
    sf["_drift_x"] = random.uniform(-1.0, 1.0)
    sf["_drift_y"] = random.uniform(-1.0, 1.0)
    snowflakes.append(sf)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Prayer flags flap in wind (signature)
for fl in flag_objs:
    phase = fl["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        fl.rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(20),
                              math.cos(t * 2.5 + phase) * math.radians(15),
                              math.sin(t * 2.0 + phase) * math.radians(10))
        fl.keyframe_insert("rotation_euler", frame=f)

# Monks chant (body sway + arms join prayer)
for m in monks:
    phase = m["root"]["_phase"]
    base_z = m["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        m["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.04
        m["root"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(5),
                                     math.cos(t * 0.6 + phase) * math.radians(4),
                                     m["root"].rotation_euler.z)
        m["root"].keyframe_insert("location", frame=f)
        m["root"].keyframe_insert("rotation_euler", frame=f)
        m["he"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(6), 0,
                                    math.sin(t * 0.5 + phase) * math.radians(8))
        m["he"].keyframe_insert("rotation_euler", frame=f)
        # Hands stay in prayer with subtle motion
        for ai, arm in enumerate(m["arms"]):
            wave = math.sin(t * 1.5 + phase + ai * math.pi) * math.radians(5)
            arm.rotation_euler = (math.radians(-80) + wave, 0, math.radians((-1 if ai==0 else 1)*-30))
            arm.keyframe_insert("rotation_euler", frame=f)

# Prayer wheel spins (signature)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    wheel_drum.rotation_euler = (0, math.radians(90), t * 2.5)
    wheel_drum.keyframe_insert("rotation_euler", frame=f)

# Yaks bob heads + body
for y in yaks:
    phase = y["root"]["_phase"]
    base_z = y["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        y["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.03
        y["root"].keyframe_insert("location", frame=f)
        y["he"].rotation_euler = (math.sin(t * 0.7 + phase) * math.radians(8), 0,
                                    math.sin(t * 0.5 + phase) * math.radians(15))
        y["he"].keyframe_insert("rotation_euler", frame=f)

# Eagles orbit + flap wings
for e in eagles:
    phase = e["root"]["_phase"]
    base_x = e["root"].location.x
    base_y = e["root"].location.y
    base_z = e["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Wide orbit
        a = t * 0.5 + phase
        rad = 18 + math.sin(t * 0.3) * 4
        e["root"].location = (rad * math.cos(a), rad * math.sin(a) - 5,
                               base_z + math.sin(t * 0.8 + phase) * 2.5)
        e["root"].rotation_euler = (0, 0, a + math.pi/2)
        e["root"].keyframe_insert("location", frame=f)
        e["root"].keyframe_insert("rotation_euler", frame=f)
        # Wing flap (signature eagle slow majestic)
        flap = math.sin(t * 2.0 + phase) * math.radians(35)
        for w_e, side in e["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)

# Brazier smoke rises + rotates
for br in braziers:
    phase = br["e"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        br["smoke"].rotation_euler = (0, 0, t * 0.8 + phase)
        br["smoke"].scale = (1 + math.sin(t * 1.5 + phase) * 0.05,
                              1 + math.cos(t * 1.5 + phase) * 0.05,
                              1 + math.sin(t * 1.0 + phase) * 0.10)
        br["smoke"].keyframe_insert("rotation_euler", frame=f)
        br["smoke"].keyframe_insert("scale", frame=f)

# Stupas pulse slow (sacred glow)
for s in stupas:
    phase = s["_phase"]
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        sc = 1 + math.sin(t * 0.8 + phase) * 0.02
        s.scale = (sc, sc, sc)
        s.keyframe_insert("scale", frame=f)

# Moon halos
for obj in bpy.data.objects:
    if obj.name.startswith("moon_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.7) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 700 SKY LANTERNS RISING (signature Tibet ceremony)
# ============================================================
for l in lanterns:
    phase = l["_phase"]; speed = l["_speed"]
    bx, by, bz = l["_base_x"], l["_base_y"], l["_base_z"]
    drift_x = l["_drift_x"]; drift_y = l["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        # Rise gently
        z = bz + (speed * t) % 30
        # Slight drift
        x = bx + drift_x * math.sin(t * 0.5 + phase)
        y = by + drift_y * math.cos(t * 0.4 + phase)
        l.location = (x, y, min(35, z))
        # Subtle pulse
        sc = 1 + math.sin(t * 1.5 + phase) * 0.10
        l.scale = (sc, sc, sc)
        l.keyframe_insert("location", frame=f)
        l.keyframe_insert("scale", frame=f)

# 200 SNOWFLAKES falling
for sf in snowflakes:
    phase = sf["_phase"]; speed = sf["_speed"]
    bx, by, bz = sf["_base_x"], sf["_base_y"], sf["_base_z"]
    drift_x = sf["_drift_x"]; drift_y = sf["_drift_y"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        z = bz - (speed * t) % 28
        x = bx + drift_x * math.sin(t * 1.5 + phase) * 0.5
        y = by + drift_y * math.cos(t * 1.3 + phase) * 0.5
        sf.location = (x, y, max(0.2, z))
        sf.rotation_euler = (t * 1.5, t * 1.2, t * 1.8)
        sf.keyframe_insert("location", frame=f)
        sf.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_tibet_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_tibetan_monastery_himalaya] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_tibetan_monastery_himalaya] ONE snow ground + Mt Everest + monastery 3-tier roof + 4 stupas + 100 prayer flags 5 strings + 9 monks (8 + abbot yellow hat) + prayer wheel + 10 yaks + 3 eagles + 4 braziers + bowls + 700 LANTERNS + 200 SNOWFLAKES")
print("⭐ FIXES: 1 ground + 700 lanterns rising + 200 snowflakes falling (signature Tibet ceremony mandatory) ⭐")
